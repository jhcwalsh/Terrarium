"""The forward smoothing kernel (WP3.3) — reported marks from true returns.

The inverse of Step 1's de-smoothing, per SM-10: ``reported`` and ``true`` are
ONE model seen two ways. For a GLM-family sleeve with weights θ (from the
frozen kernel artifact, fitted by the D1 primary on that sleeve's reported
composite):

    reported_t = θ0·true_t + θ1·true_{t-1} + ... + θk·true_{t-k}

so running the D1 de-smoother on the smoothed series recovers the true one —
asserted by test through the sealed public API, not assumed.

State-dependent stickiness (DN-5 §5.3's mechanism): ``θ0_eff = θ0·(1 - s·D_t)``
with the shortfall renormalized onto the lagged weights, where ``D_t in [0,1]``
is a drawdown-depth state. The calibrated ``s`` in the artifact is **0.0 as
measured** on in-sample stress (the artifact records the evidence and why
2021-23 was off-limits); the mechanism ships so the parameter is a number, not
a code change, if later evidence moves it.

The Geltner appraisal family (RE/infrastructure) is deliberately ABSENT here:
unparameterized in the artifact (no PM data), and an unparameterized family
raises rather than pretending. Engines don't seal; estimates do — this module
is lineage-pinned by ``kernel_version``, the artifact is inside the G3 lock.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = _REPO_ROOT / "mappings" / "smoothing-kernel-v1.0.yaml"


class SmoothingError(ValueError):
    """A kernel artifact or input that cannot produce reported marks honestly."""


@lru_cache(maxsize=1)
def load_kernel(path: Path | None = None) -> dict[str, Any]:
    p = path or ARTIFACT_PATH
    if not p.exists():
        raise SmoothingError(
            f"{p}: kernel artifact not found — run scripts/estimate_smoothing_kernel.py"
        )
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if "families" not in doc or "glm" not in doc["families"]:
        raise SmoothingError("kernel artifact missing families.glm")
    return doc


def theta_for(sleeve_id: str, *, artifact_path: Path | None = None) -> np.ndarray:
    """MA(k) weights for a GLM-family sleeve — HF (monthly) or PM (quarterly).

    Appraisal-calendar sleeves are NOT here by design: they carry an AR(1)
    partial adjustment, a different functional form, served by
    :func:`geltner_for`. Asking this function for one is an error, not a
    fallback.
    """
    doc = load_kernel(artifact_path)
    glm = doc["families"]["glm"]
    known = {**glm.get("sleeves", {}), **(glm.get("pm_sleeves") or {})}
    if sleeve_id not in known:
        geltner = doc["families"].get("geltner", {})
        in_geltner = sleeve_id in (geltner.get("sleeves") or {})
        detail = (
            f"'{sleeve_id}' is an APPRAISAL-CALENDAR sleeve — use geltner_for()"
            if in_geltner
            else f"known GLM sleeves: {sorted(known)}; the geltner family is "
            f"{geltner.get('status', 'absent')}"
        )
        raise SmoothingError(f"no GLM kernel for sleeve '{sleeve_id}'. {detail}.")
    return np.asarray(known[sleeve_id]["theta"], dtype=float)


def geltner_for(sleeve_id: str, *, artifact_path: Path | None = None) -> tuple[float, float]:
    """``(a, phi)`` for an appraisal-calendar sleeve: the AR(1) partial
    adjustment where reported marks track truth at rate ``a = 1 - phi``.

    Added 2026-08-08 when the first PriMaRS delivery parameterized the family
    this artifact had carried as UNPARAMETERIZED with a trigger. A sleeve the
    family does not cover still raises — delivery for two sleeves is not
    delivery for all of them.
    """
    doc = load_kernel(artifact_path)
    geltner = doc["families"].get("geltner", {})
    if geltner.get("status") != "PARAMETERIZED":
        raise SmoothingError(
            f"the geltner family is {geltner.get('status', 'absent')} — an "
            "unparameterized family raises rather than pretending."
        )
    sleeves = geltner.get("sleeves") or {}
    if sleeve_id not in sleeves:
        raise SmoothingError(
            f"no geltner kernel for sleeve '{sleeve_id}' (known: {sorted(sleeves)}). "
            "PM delivery covers the modeled sleeves only."
        )
    entry = sleeves[sleeve_id]
    return float(entry["a"]), float(entry["phi"])


def stickiness(*, family: str = "glm", artifact_path: Path | None = None) -> float:
    """State-dependent mark stickiness for a smoothing family (DN-5 SM-11).

    Defaults to ``glm`` so existing callers are unaffected. The two families
    are calibrated on different frequencies and are NOT interchangeable — see
    the kernel artifact's header.
    """
    value = load_kernel(artifact_path)["families"][family]["stickiness"]
    if value is None:
        raise SmoothingError(f"family '{family}' has no fitted stickiness on this artifact")
    return float(value)


def smooth(
    true_returns: np.ndarray,
    theta: np.ndarray,
    *,
    s: float = 0.0,
    drawdown_state: np.ndarray | None = None,
) -> np.ndarray:
    """Reported returns from true returns, along the last axis.

    ``true_returns`` is ``(months,)`` or ``(n_paths, months)``. Pre-history
    lags are backfilled with the first observation (the honest neutral start —
    a cohort's first reported mark can only reflect what has happened).
    ``drawdown_state`` (same shape, values in [0, 1]) drives the stickiness
    mechanism; with ``s = 0`` (the calibrated value) it is inert.
    """
    theta = np.asarray(theta, dtype=float)
    if theta.ndim != 1 or theta.size < 1:
        raise SmoothingError("theta must be a non-empty 1-D weight vector")
    if not np.isclose(theta.sum(), 1.0, atol=1e-6):
        raise SmoothingError(f"theta must sum to 1 (got {theta.sum():.6f})")
    if not 0.0 <= s <= 1.0:
        raise SmoothingError("stickiness s must be in [0, 1]")

    x = np.atleast_2d(np.asarray(true_returns, dtype=float))
    n_paths, months = x.shape
    if drawdown_state is None:
        d = np.zeros_like(x)
    else:
        d = np.atleast_2d(np.asarray(drawdown_state, dtype=float))
        if d.shape != x.shape:
            raise SmoothingError("drawdown_state must match true_returns' shape")
        if d.min() < 0.0 or d.max() > 1.0:
            raise SmoothingError("drawdown_state values must be in [0, 1]")

    k = theta.size - 1
    # lagged matrix with first-observation backfill for pre-history
    lags = np.empty((k + 1, n_paths, months))
    for i in range(k + 1):
        if i == 0:
            lags[0] = x
        else:
            lags[i, :, i:] = x[:, :-i]
            lags[i, :, :i] = x[:, [0]]

    out = np.empty_like(x)
    for t in range(months):
        # θ0 sheds weight into the lags in proportion to their own θ mass —
        # stickier marks lean harder on the past, exactly DN-5 §5.3's shape.
        theta0_eff = theta[0] * (1.0 - s * d[:, t])
        shed = theta[0] - theta0_eff
        if k > 0 and theta[1:].sum() > 0:
            scale = 1.0 + shed / theta[1:].sum()
            weights = np.concatenate(
                [theta0_eff[:, None], theta[None, 1:] * scale[:, None]], axis=1
            )
        else:
            weights = np.concatenate([theta0_eff[:, None] + shed[:, None]], axis=1)
        out[:, t] = np.einsum("pi,ip->p", weights, lags[:, :, t])

    return out[0] if np.asarray(true_returns).ndim == 1 else out


def drawdown_state_from_returns(returns: np.ndarray, *, floor: float = -0.5) -> np.ndarray:
    """A [0, 1] drawdown-depth state from a reference return path (last axis).

    Depth is the running peak-to-current drawdown of the cumulated path,
    scaled so ``floor`` (default -50%) maps to 1. Purely causal.
    """
    x = np.atleast_2d(np.asarray(returns, dtype=float))
    cum = np.cumprod(1.0 + x, axis=1)
    peak = np.maximum.accumulate(cum, axis=1)
    dd = cum / peak - 1.0
    state = np.clip(dd / floor, 0.0, 1.0)
    return state[0] if np.asarray(returns).ndim == 1 else state
