"""The deterministic toy engine (``toy-v0``).

A monthly, pure-function engine that turns a :class:`NumericWorld` into factor
paths and per-asset return series. It is **narrative-blind by construction**: it
only ever sees a ``NumericWorld`` (no ``narrative`` attribute exists to read).

Determinism (STEP0-PLAN §1, §6): every random number flows from a single
``numpy.random.Generator(PCG64(seed))``. All draws are taken up front in a fixed
order so the byte layout of the output is stable across platforms; there is no
global RNG, no ``random``, no time-based default.

Units — the formulas port a prototype verbatim (STEP0-PLAN §WP0.4). The stated
convention is: *drift* tokens are annual-% ÷ 12, *vol* tokens are annual-% ÷ √12.
Rates are carried in percent and spreads in basis points; the ``/1200`` and
``/120000`` terms convert those to monthly units, and the ``Δrate`` / ``Δspread``
terms use the raw path units (percent / bps). Return magnitudes are therefore only
as realistic as this toy allows — calibration is explicitly out of scope for Step 0.
The value here is a stable, auditable, reproducible loop, not a realistic market.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ah.core.numericworld import NumericWorld

TOY_GENERATOR_ID = "toy-v0"
_ENSEMBLE_SEED_STRIDE = 7919  # run_ensemble uses base_seed + 7919*k

# Asset order is part of the contract (drives the golden digest); do not reorder.
ASSETS: tuple[str, ...] = (
    "equity",
    "bonds",
    "hy",
    "commodities",
    "reits",
    "pe",
    "pc",
    "re",
)
REPORTED_SLEEVES: tuple[str, ...] = ("pe", "pc", "re")

# Toy-engine defaults for absent (optional) factor/structural fields. The engine
# needs concrete numbers even where the WorldSpec leaves a field to "let the
# generator decide"; these are the toy's stand-ins and are documented as such.
_DEF = {
    "policy_start": 3.0,
    "policy_end": 3.0,
    "infl_avg": 2.0,
    "eq_drift": 6.0,
    "eq_vol": 16.0,
    "hy_start": 400.0,
    "hy_peak": 600.0,
    "hy_peak_q": 4,
    "com_drift": 2.0,
    "pe_illiq": 2.0,
    "pe_mult_drift": 0.0,
    "pc_loss": 2.0,
    "re_cap_shift": 0.0,
    "smooth_pe": 0.35,
    "smooth_pc": 0.30,
    "smooth_re": 0.35,
}


class UnsupportedGeneratorError(ValueError):
    """Raised when asked to run a world whose generator_id is not ``toy-v0``."""


@dataclass(frozen=True)
class EnginePaths:
    """One simulated history (single seed)."""

    months: int
    seed: int
    rate: np.ndarray
    spread: np.ndarray
    inflation: np.ndarray
    crisis: np.ndarray
    returns: dict[str, np.ndarray]
    reported: dict[str, np.ndarray]


@dataclass(frozen=True)
class EnsembleResult:
    """An ensemble of histories with returns stacked as ``(n_paths, months)``."""

    months: int
    n_paths: int
    seeds: list[int]
    returns: dict[str, np.ndarray]
    reported: dict[str, np.ndarray]


# --------------------------------------------------------------------------- #
# parameter extraction
# --------------------------------------------------------------------------- #


def _f(model: object, attr: str, default: float) -> float:
    """Return a numeric attribute of a (possibly None) pydantic sub-model."""
    if model is None:
        return default
    value = getattr(model, attr, None)
    return float(value) if isinstance(value, (int, float)) else default


def _require_toy(world: NumericWorld) -> None:
    gid = world.engine_defaults.generator_id
    if gid != TOY_GENERATOR_ID:
        raise UnsupportedGeneratorError(
            f"engine implements only '{TOY_GENERATOR_ID}', got '{gid}'. "
            "Other generators arrive in later steps."
        )


def _crisis_mask(world: NumericWorld, nm: int) -> np.ndarray:
    """Binary crisis indicator from the FIRST crisis window (severity unused here)."""
    mask = np.zeros(nm)
    windows = world.factor_conditions.crisis_windows or []
    if windows:
        w = windows[0]
        lo = w.start_quarter * 3
        hi = lo + w.length_quarters * 3
        lo, hi = max(0, lo), min(nm, hi)
        if hi > lo:
            mask[lo:hi] = 1.0
    return mask


# --------------------------------------------------------------------------- #
# factor paths
# --------------------------------------------------------------------------- #


def _rate_path(world: NumericWorld, nm: int, z: np.ndarray) -> np.ndarray:
    pr = world.factor_conditions.policy_rate
    start = _f(pr, "start_pct", _DEF["policy_start"])
    end = _f(pr, "end_pct", _DEF["policy_end"])
    rate = np.empty(nm)
    r = start
    for m in range(nm):
        target = start if nm == 1 else start + (end - start) * m / (nm - 1)
        r = max(0.1, r + 0.15 * (target - r) + 0.06 * z[m])
        rate[m] = r
    return rate


def _spread_path(world: NumericWorld, nm: int, z: np.ndarray) -> np.ndarray:
    credit = world.factor_conditions.credit
    start = _f(credit, "hy_spread_start_bps", _DEF["hy_start"])
    peak = _f(credit, "hy_spread_peak_bps", _DEF["hy_peak"])
    peak_q = int(getattr(credit, "peak_quarter", None) or _DEF["hy_peak_q"])
    peak_m = min(max(0, peak_q * 3), nm - 1)
    spread = np.empty(nm)
    for m in range(nm):
        if m <= peak_m:
            base = peak if peak_m == 0 else start + (peak - start) * (m / peak_m)
        else:
            denom = (nm - 1) - peak_m
            base = peak if denom == 0 else peak + (0.9 * start - peak) * ((m - peak_m) / denom)
        spread[m] = max(150.0, base + 14.0 * z[m])
    return spread


def _inflation_path(world: NumericWorld, nm: int, crisis: np.ndarray, z: np.ndarray) -> np.ndarray:
    avg = _f(world.factor_conditions.inflation, "average_pct", _DEF["infl_avg"])
    infl = np.empty(nm)
    x = avg
    for m in range(nm):
        target = avg * (1.15 if crisis[m] else 1.0)
        x = max(-2.0, x + 0.12 * (target - x) + 0.28 * z[m])
        infl[m] = x
    return infl


# --------------------------------------------------------------------------- #
# single path
# --------------------------------------------------------------------------- #


def run_path(world: NumericWorld, seed: int) -> EnginePaths:
    """Simulate one monthly history from ``seed`` (PCG64). Pure & deterministic."""
    _require_toy(world)
    nm = world.horizon.quarters * 3
    rng = np.random.Generator(np.random.PCG64(seed))

    # Draw every normal stream up front, in a fixed order (determinism anchor).
    z_rate = rng.standard_normal(nm)
    z_spread = rng.standard_normal(nm)
    z_infl = rng.standard_normal(nm)
    z_m = rng.standard_normal(nm)
    e_eq = rng.standard_normal(nm)
    e_hy = rng.standard_normal(nm)
    e_com = rng.standard_normal(nm)
    e_b = rng.standard_normal(nm)
    e_reit = rng.standard_normal(nm)
    e_pe = rng.standard_normal(nm)
    e_pc = rng.standard_normal(nm)
    e_re = rng.standard_normal(nm)

    crisis = _crisis_mask(world, nm)
    rate = _rate_path(world, nm, z_rate)
    spread = _spread_path(world, nm, z_spread)
    inflation = _inflation_path(world, nm, crisis, z_infl)

    # First-difference of the paths; no change on the first month. d_rate is in
    # percentage points (rate is already in percent). d_spread is converted from
    # bps to percentage points so the HY spread-shock term is on the same scale as
    # its own vol term and every other asset's monthly return (resolving a spec
    # inconsistency: the spread PATH is defined in bps, but the "3.5*Δspread"
    # coefficient only yields sane monthly returns when Δspread is in pp).
    d_rate = np.diff(rate, prepend=rate[0])
    d_spread = np.diff(spread, prepend=spread[0]) / 100.0

    fc = world.factor_conditions
    st = world.structural
    infl_avg = _f(fc.inflation, "average_pct", _DEF["infl_avg"])
    eq_drift = _f(fc.equity, "drift_annual_pct", _DEF["eq_drift"])
    eq_vol_m = _f(fc.equity, "vol_annual_pct", _DEF["eq_vol"]) / math.sqrt(12.0)
    com_drift = _f(fc.commodities, "drift_annual_pct", _DEF["com_drift"])
    pe_illiq = _f(st.private_equity, "illiquidity_premium_annual_pct", _DEF["pe_illiq"])
    pe_mult = _f(st.private_equity, "entry_multiple_drift_annual_pct", _DEF["pe_mult_drift"])
    pc_loss = _f(st.private_credit, "annual_loss_rate_pct", _DEF["pc_loss"])
    re_cap = _f(st.real_estate, "cap_rate_shift_bps", _DEF["re_cap_shift"])

    # Common-factor loadings: stronger co-movement inside crisis months.
    rho = np.where(crisis > 0, 0.85, 0.45)
    k = np.sqrt(1.0 - rho**2)
    z_eq = rho * z_m + k * e_eq
    z_hy = rho * z_m + k * e_hy
    z_com = rho * z_m + k * e_com

    # Equity-bond correlation flips sign with the inflation regime.
    corr_eb = 0.35 if infl_avg > 3.5 else -0.30
    z_b = corr_eb * z_m + math.sqrt(1.0 - corr_eb**2) * e_b

    loss_m = pc_loss / 1200.0

    eq = eq_drift / 12.0 + eq_vol_m * z_eq - 0.022 * crisis
    bonds = rate / 1200.0 - 6.0 * d_rate + 0.007 * z_b
    hy = rate / 1200.0 + spread / 120000.0 - 3.5 * d_spread + 0.5 * eq_vol_m * z_hy - 0.006 * crisis
    commodities = com_drift / 12.0 + max(0.0, infl_avg - 2.5) / 1200.0 + 0.052 * z_com
    reits = 0.65 * eq - 2.5 * d_rate + 0.026 * e_reit
    pe = 1.4 * eq + (pe_illiq + pe_mult) / 1200.0 + 0.02 * e_pe
    pc = (rate + 4.5) / 1200.0 - loss_m * np.where(crisis > 0, 3.2, 0.6) + 0.18 * eq + 0.007 * e_pc
    re = 0.045 / 12.0 - re_cap / (10000.0 * nm) * 2.2 + 0.35 * eq + 0.011 * e_re

    returns = {
        "equity": eq,
        "bonds": bonds,
        "hy": hy,
        "commodities": commodities,
        "reits": reits,
        "pe": pe,
        "pc": pc,
        "re": re,
    }

    reported = _reported_marks(world, returns)
    return EnginePaths(nm, seed, rate, spread, inflation, crisis, returns, reported)


def _reported_marks(world: NumericWorld, returns: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Appraisal-smoothed marks for pe/pc/re: nonzero only at quarter-ends."""
    smoothing = world.structural.smoothing
    weights_model = smoothing.weights_on_truth if smoothing else None
    weights = {
        "pe": _f(weights_model, "private_equity", _DEF["smooth_pe"]),
        "pc": _f(weights_model, "private_credit", _DEF["smooth_pc"]),
        "re": _f(weights_model, "real_estate", _DEF["smooth_re"]),
    }
    out: dict[str, np.ndarray] = {}
    for sleeve in REPORTED_SLEEVES:
        w = weights[sleeve]
        true = returns[sleeve]
        rep = np.zeros(len(true))
        prev = 0.0
        for m in range(len(true)):
            if (m + 1) % 3 == 0:  # quarter-end month
                prev = w * true[m] + (1.0 - w) * prev
                rep[m] = prev
        out[sleeve] = rep
    return out


# --------------------------------------------------------------------------- #
# ensemble
# --------------------------------------------------------------------------- #


def run_ensemble(world: NumericWorld, n_paths: int, base_seed: int | None = None) -> EnsembleResult:
    """Run ``n_paths`` histories with seeds ``base_seed + 7919*k``.

    ``base_seed`` defaults to ``engine_defaults.base_seed`` (or 0 if unset).
    """
    _require_toy(world)
    if n_paths < 1:
        raise ValueError("n_paths must be >= 1")
    if base_seed is None:
        base_seed = world.engine_defaults.base_seed
        if base_seed is None:
            base_seed = 0
    seeds = [base_seed + _ENSEMBLE_SEED_STRIDE * k for k in range(n_paths)]
    paths = [run_path(world, s) for s in seeds]
    nm = paths[0].months
    returns = {a: np.stack([p.returns[a] for p in paths]) for a in ASSETS}
    reported = {a: np.stack([p.reported[a] for p in paths]) for a in REPORTED_SLEEVES}
    return EnsembleResult(nm, n_paths, seeds, returns, reported)
