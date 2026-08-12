"""Generator→engine adapter (su-gen-01) — factor slabs into the toy contracts.

The Task 0 survey's smallest seam, implemented: resolve the world's generator
through ``ah.gen.registry``, sample it, and translate the 16-factor
``Ensemble`` into the SAME ``EnsembleResult``/``EnginePaths`` dataclasses the
toy engine emits — so digest, replay, twin, play, and bundle need no new
contracts. Everything downstream keys off ``asset_order``.

Stated conventions (each is a modelling choice recorded here, not a fact):

* **Assets** (`GEN_ASSETS`): the toy tuple minus ``reits`` — OD-3: the 16
  factor set has no REIT factor and we do not invent a proxy.
* **equity / commodities**: the factor IS the asset; decimal→percent (x100).
* **bonds**: the duration-8.5 first-order convention, verbatim from
  ``ah.port.mapping._bond_total_return`` (the sealed ``govt_tr_10y`` shape).
* **hy**: carry net of losses + spread duration —
  ``(y10 + (1-LOSS)*hs)/12 - DUR_HY*delta(y10+hs)`` in percent, with
  ``LOSS = 0.45`` mirroring the toy's ``_HY_LOSS_SHARE`` and ``DUR_HY = 4.0``.
* **pe / pc / re** (true): the sealed PM sleeve loadings
  (``mappings/sleeve-mappings-v1.0.yaml``) applied at MONTHLY frequency with
  ``alpha_quarterly/3`` — systematic only, quarterly-estimated betas on
  monthly regressors; a stated convention pending a monthly re-estimate.
  Sleeve choice: ``PM_SLEEVE_FOR_ASSET``.
* **reported pe/pc/re**: the toy's quarter-end appraisal shape
  (``engine._reported_marks``), driven by the WorldSpec's own smoothing
  weights — the world stays the authority for its reporting behaviour.
* **rate**: ``policy_rate`` as-is (percent, the toy scale).
* **spread**: ``hy_spread`` percent→bps — the toy spread channel IS the HY
  spread in bps (play's 400bp reference, the feed's 800bp threshold).
* **inflation**: trailing YoY from the resampled ``cpi`` LEVEL; months with
  under a year of history annualize the available window. Block seams make
  this a synthetic composite (survey S4) — the channel is display-bearing,
  never scored, and the caveat ships with the plan.
* **crisis**: months whose realized regime label is ``CRI``
  (``RegimeRecord``) — bootstrap ignores ``factor_conditions`` by seal.
* **Seed rule**: path ``k`` is ``sample(world, 1, base_seed + 7919*k)`` — the
  platform stride, so ``run_gen_path(base+7919k)`` IS ensemble path ``k``
  and a path's identity is independent of ``n_paths`` (the toy invariant).
"""

from __future__ import annotations

import numpy as np

from ah.core.engine import (
    ASSETS,
    REPORTED_SLEEVES,
    EnginePaths,
    EnsembleResult,
    _reported_marks,
)
from ah.core.numericworld import NumericWorld
from ah.gen import registry
from ah.gen.base import Ensemble
from ah.port.mapping import _bond_total_return, _regressor_slabs, load_artifact

SEED_STRIDE = 7919  # the platform rule; asserted equal to the engine's in tests

GEN_ASSETS: tuple[str, ...] = tuple(a for a in ASSETS if a != "reits")

PM_SLEEVE_FOR_ASSET: dict[str, str] = {
    "pe": "pm_buyout",
    "pc": "pm_direct_lending",
    "re": "pm_re_value_add",
}

_HY_LOSS_SHARE = 0.45  # mirrors the toy engine's convention
_HY_SPREAD_DURATION = 4.0  # stated; HY duration is shorter than govt 8.5


class AdapterError(ValueError):
    """A world or ensemble the adapter cannot translate honestly."""


def _pm_true_monthly(ensemble: Ensemble, sleeve_id: str) -> np.ndarray:
    """Monthly TRUE percent returns for one PM sleeve: alpha_quarterly/3 +
    quarterly-estimated loadings applied to the monthly regressor slabs."""
    artifact = load_artifact()
    spec = artifact["pm_sleeves"][sleeve_id]
    slabs = _regressor_slabs(ensemble)
    out = np.full((ensemble.n_paths, ensemble.months), float(spec["alpha_quarterly"]) / 3.0)
    for name, beta in spec["loadings"].items():
        if float(beta) != 0.0:
            out = out + float(beta) * slabs[name]
    return out * 100.0


def _hy_monthly(ensemble: Ensemble) -> np.ndarray:
    """HY percent returns: carry net of losses plus spread duration (stated)."""
    y10 = ensemble.factor("ust_10y")
    hs = ensemble.factor("hy_spread")
    carry = np.empty_like(y10)
    all_in = y10 + (1.0 - _HY_LOSS_SHARE) * hs
    carry[:, 0] = all_in[:, 0] / 12.0
    carry[:, 1:] = all_in[:, :-1] / 12.0
    wide = y10 + hs
    change = np.zeros_like(y10)
    change[:, 1:] = _HY_SPREAD_DURATION * (wide[:, :-1] - wide[:, 1:])
    return carry + change


def _inflation_yoy(cpi: np.ndarray) -> np.ndarray:
    """Trailing YoY percent from a CPI level path; short windows annualize."""
    months = cpi.shape[0]
    out = np.empty(months)
    for t in range(months):
        back = min(t, 12)
        if back == 0:
            continue  # filled after the loop from t=1
        out[t] = ((cpi[t] / cpi[t - back]) ** (12.0 / back) - 1.0) * 100.0
    out[0] = out[1] if months > 1 else 0.0
    return out


def _crisis_mask(ensemble: Ensemble, k: int) -> np.ndarray:
    regimes = ensemble.regimes
    labels = getattr(regimes, "labels", None)
    legend = getattr(regimes, "legend", None)
    if labels is None or legend is None:
        raise AdapterError("ensemble carries no regime record; the crisis channel would be a guess")
    legend = tuple(legend)
    if "CRI" not in legend:
        return np.zeros(ensemble.months)
    return (np.asarray(labels)[k] == legend.index("CRI")).astype(float)


def _asset_returns(ensemble: Ensemble) -> dict[str, np.ndarray]:
    """All GEN_ASSETS as (n_paths, months) percent returns."""
    out = {
        "equity": ensemble.factor("equity_mkt") * 100.0,
        "commodities": ensemble.factor("commodities") * 100.0,
        "bonds": _bond_total_return(ensemble.factor("ust_10y")) * 100.0,
        "hy": _hy_monthly(ensemble),
    }
    for asset, sleeve_id in PM_SLEEVE_FOR_ASSET.items():
        out[asset] = _pm_true_monthly(ensemble, sleeve_id)
    return out


def run_gen_path(world: NumericWorld, seed: int) -> EnginePaths:
    """One generated history in the toy ``EnginePaths`` contract."""
    gen = registry.resolve_for_world(world)
    if gen.generator_id == "toy-v0":  # pragma: no cover - guarded upstream
        raise AdapterError("the adapter is for generated worlds; toy-v0 has its own engine")
    ensemble = gen.sample(world, 1, seed)
    slab = _asset_returns(ensemble)
    returns = {a: slab[a][0] for a in GEN_ASSETS}
    reported = _reported_marks(world, returns)
    return EnginePaths(
        months=ensemble.months,
        seed=seed,
        rate=ensemble.factor("policy_rate")[0].copy(),
        spread=ensemble.factor("hy_spread")[0] * 100.0,
        inflation=_inflation_yoy(ensemble.factor("cpi")[0]),
        crisis=_crisis_mask(ensemble, 0),
        returns=returns,
        reported=reported,
        asset_order=GEN_ASSETS,
    )


# OD-3: the reits start weight moves to equity — its 0.84-correlated public
# neighbour — leaving the private allocation exactly as designed.
GEN_START_MIX: dict[str, float] = {
    "equity": 0.35,
    "bonds": 0.10,
    "hy": 0.05,
    "commodities": 0.05,
    "pe": 0.25,
    "pc": 0.10,
    "re": 0.10,
}


def gen_hold_course_twin(world: NumericWorld, seed: int):
    """The passive benchmark over a generated path (institution unchanged)."""
    from ah.core.institution import simulate_institution

    return simulate_institution(run_gen_path(world, seed), None, start_mix=GEN_START_MIX)


def gen_lineage(world: NumericWorld) -> dict[str, str]:
    """The honest ``resolved_engine`` stamp for a generated run: what actually
    produced the numbers, pinned per OD-4 (generator + campaign vintage)."""
    gen = registry.resolve_for_world(world)
    meta = gen.sample(world, 1, 0).meta
    return {
        "generator_id": world.engine_defaults.generator_id,
        "generator_version": meta.generator_id,
        "campaign_vintage_id": meta.vintage_id,
    }


def run_gen_ensemble(world: NumericWorld, n_paths: int, *, base_seed: int) -> EnsembleResult:
    """A generated ensemble in the toy ``EnsembleResult`` contract.

    Stacked from per-path ``run_gen_path`` calls at the platform stride, so
    path identity is independent of ensemble size.
    """
    seeds = [base_seed + SEED_STRIDE * k for k in range(n_paths)]
    paths = [run_gen_path(world, s) for s in seeds]
    months = paths[0].months
    returns = {a: np.stack([p.returns[a] for p in paths], axis=0) for a in GEN_ASSETS}
    reported = {s: np.stack([p.reported[s] for p in paths], axis=0) for s in REPORTED_SLEEVES}
    return EnsembleResult(
        months=months,
        n_paths=n_paths,
        seeds=seeds,
        returns=returns,
        reported=reported,
        asset_order=GEN_ASSETS,
    )
