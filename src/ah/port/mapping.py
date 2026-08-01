"""Apply the estimated factor -> sleeve mappings to an ensemble (WP3.2 runtime).

Loads the versioned artifact (``mappings/sleeve-mappings-v1.0.yaml``, the file
WorldSpec's ``mapping_version`` names) and turns a generated ensemble into TRUE
sleeve returns: linear loadings + correlated residuals for six HF sleeves, and
the CTA RULE (DN-5 §3.4 — a 12-month time-series-momentum overlay computed on
the generated paths themselves, vol-targeted, with a cost drag) for the
seventh. No estimation happens here; the artifact is the frozen output of
``scripts/estimate_sleeve_mappings.py`` and carries its own provenance.

Determinism: path ``k`` draws its residuals from ``PCG64(seed + 7919 * k)`` —
the platform seed rule — so a sleeve panel is bit-reproducible from
``(ensemble, mapping_version, seed)`` alone. The CTA rule consumes no RNG.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ah.gen.base import Ensemble

_REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.0.yaml"

SEED_STRIDE = 7919
BOND_DURATION_YEARS = 8.5  # matches the sealed govt_tr_10y derived-series convention


class MappingError(ValueError):
    """An artifact or ensemble that cannot produce sleeve returns honestly."""


@lru_cache(maxsize=1)
def load_artifact(path: Path | None = None) -> dict[str, Any]:
    p = path or ARTIFACT_PATH
    if not p.exists():
        raise MappingError(
            f"{p}: mapping artifact not found — run scripts/estimate_sleeve_mappings.py"
        )
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    for key in ("mapping_version", "sleeves", "residual_correlation", "cta_rule"):
        if key not in doc:
            raise MappingError(f"mapping artifact missing '{key}'")
    return doc


def _regressor_slabs(ensemble: Ensemble) -> dict[str, np.ndarray]:
    """The estimator's regressors, rebuilt from ensemble factor slabs.

    Level/slope/spread changes use a zero first-month change (no prior month
    exists inside a generated path; a zero change is the neutral statement).
    """

    def diff(slab: np.ndarray) -> np.ndarray:
        d = np.diff(slab, axis=1)
        return np.concatenate([np.zeros((slab.shape[0], 1)), d], axis=1)

    ust10 = ensemble.factor("ust_10y")
    ust2 = ensemble.factor("ust_2y")
    return {
        "equity_mkt": ensemble.factor("equity_mkt"),
        "smb": ensemble.factor("smb"),
        "hml": ensemble.factor("hml"),
        "mom": ensemble.factor("mom"),
        "d_level": diff(ust10),
        "d_slope": diff(ust10 - ust2),
        "d_ig": diff(ensemble.factor("ig_spread")),
    }


def _bond_total_return(ust10: np.ndarray) -> np.ndarray:
    """Monthly 10y govt total-return proxy from the yield path (duration approx).

    ``r_t = carry + D * (y_{t-1} - y_t)``, yields in percent — the same
    first-order convention the sealed ``govt_tr_10y`` derived series uses.
    First month carries only carry (no prior yield inside the path).
    """
    y = ust10 / 100.0
    carry = np.empty_like(y)
    carry[:, 0] = y[:, 0] / 12.0
    carry[:, 1:] = y[:, :-1] / 12.0
    change = np.zeros_like(y)
    change[:, 1:] = BOND_DURATION_YEARS * (y[:, :-1] - y[:, 1:])
    return carry + change


def _cta_rule(ensemble: Ensemble, rule: dict[str, Any]) -> np.ndarray:
    """DN-5 §3.4's overlay: 12m TSM across the instruments, vol-targeted, net of drag.

    Causal throughout: month ``t`` uses signals and vol estimated on months
    ``< t``. Warm-up months (before one full lookback) hold flat at zero.
    """
    lookback = int(rule["lookback_months"])
    vol_target = float(rule["vol_target_annual"])
    drag_m = float(rule["tc_drag_annual"]) / 12.0
    instruments = [
        ensemble.factor("equity_mkt")
        if name == "equity_mkt"
        else _bond_total_return(ensemble.factor("ust_10y"))
        for name in rule["instruments"]
    ]
    n_paths, months = instruments[0].shape
    out = np.zeros((n_paths, months))
    per_inst_target = vol_target / (np.sqrt(12.0) * len(instruments))
    for r in instruments:
        for t in range(lookback, months):
            window = r[:, t - lookback : t]
            signal = np.sign(window.sum(axis=1))
            sigma = window.std(axis=1, ddof=1)
            sigma[sigma <= 1e-8] = 1e-8
            out[:, t] += signal * (per_inst_target / sigma) * r[:, t]
    out[:, lookback:] -= drag_m
    return out


def sleeve_returns(
    ensemble: Ensemble, *, seed: int, artifact_path: Path | None = None
) -> dict[str, np.ndarray]:
    """TRUE sleeve returns per modeled HF sleeve: ``dict[sleeve_id, (n_paths, months)]``.

    Linear sleeves: ``alpha + X @ beta + eps`` with ``eps`` drawn correlated
    across sleeves (the artifact's residual correlation, Cholesky) at each
    sleeve's residual sigma. ``hf_cta`` comes from the rule, RNG-free.
    """
    artifact = load_artifact(artifact_path)
    slabs = _regressor_slabs(ensemble)
    regressors = list(artifact["regressors"])
    sleeves = artifact["sleeves"]
    names = sorted(sleeves)
    n_paths, months = ensemble.n_paths, ensemble.months

    corr = np.array(
        [[float(artifact["residual_correlation"][a][b]) for b in names] for a in names]
    )
    sigmas = np.array(
        [float(sleeves[name]["residual_sigma_annual"]) / np.sqrt(12.0) for name in names]
    )
    try:
        chol = np.linalg.cholesky(corr)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - artifact defect
        raise MappingError("residual correlation matrix is not positive definite") from exc

    systematic = {}
    for name in names:
        spec = sleeves[name]
        beta = np.array([float(spec["loadings"][r]) for r in regressors])
        x = np.stack([slabs[r] for r in regressors], axis=-1)  # (paths, months, k)
        systematic[name] = float(spec["alpha_monthly"]) + x @ beta

    out = {name: np.empty((n_paths, months)) for name in names}
    for k in range(n_paths):
        rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
        shocks = rng.standard_normal((months, len(names))) @ chol.T  # correlated
        for j, name in enumerate(names):
            out[name][k] = systematic[name][k] + shocks[:, j] * sigmas[j]

    out["hf_cta"] = _cta_rule(ensemble, artifact["cta_rule"])
    return out
