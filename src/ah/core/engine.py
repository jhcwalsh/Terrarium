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

# The generator FAMILY is pinned by schemas/worldspec-*.schema.json's enum and
# cannot change; the exact version is resolved at run time and recorded on the
# RunRecord as `resolved_engine.generator_version` (the schema's own words:
# "Exact trained version is resolved and pinned at run time"). Bump this
# whenever the numbers a world produces change, so a RunRecord always says
# which engine made it.
#   v0.1  Step 0's original constants
#   v0.2  unit coherence: carry/vol constants moved into percent space
#   v0.3  register ER-1 + ER-4: credit losses, a spread cycle that clears,
#         and a policy rate with enough innovation to make duration risky
#   v0.4  register ER-7: market innovations are standardized Student-t, so
#         monthly returns have tails. Declared volatility is unchanged.
#         NEVER MERGED: its gate exposed the missing limited-liability floor
#         below, so v0.4 numbers exist only in that branch's diagnosis.
#   v0.5  ER-7 close-out: the fat tails v0.4 introduced could push a levered
#         stream (pe = 1.4x equity) below -100% in a month (measured -127.7%,
#         ~2 paths per 600 on stagflation), which no long-only asset can do
#         and which NaN-poisons cumulative growth. Every monthly return is
#         floored at -99% (limited liability). Tails otherwise unchanged.
#   v0.6  ER-10: the quarter-end appraisal mark filtered only the closing
#         MONTH's return, silently discarding the quarter's other two months
#         (reported PM cumulated ~1/3 of truth). Now filters the whole
#         quarter's compounded true return, so cumulative reported catches
#         up to cumulative true.
TOY_ENGINE_VERSION = "toy-v0.6"

# -- register ER-7 close-out: limited liability ----------------------------- #
# A holder of a long-only asset cannot lose more than everything: monthly
# total returns are floored here, in percent units. -99 rather than -100 so a
# floored month leaves a positive (1 + r/100) factor and cumulative growth
# stays finite. The floor binds on ~0.3% of stagflation paths at t(6); it is a
# truncation of the constructed return, not of the innovation, so the declared
# vol/correlation structure above the floor is untouched.
_MONTHLY_RETURN_FLOOR_PCT = -99.0

# -- register ER-7: monthly returns had no tails --------------------------- #
# Degrees of freedom for the market innovations. CHOSEN, from the empirical
# literature on monthly equity index returns, which puts fitted t degrees of
# freedom in the 4-8 region; 6 sits mid-range and gives the innovation an excess
# kurtosis of 6/(df-4) = 3.0. Deliberately NOT tuned to land the battery's
# `excess_kurtosis` gate inside its band: picking df by what makes the gate pass
# would be the mirror image of moving the threshold, and the realized pooled
# statistic is reported wherever it falls.
_INNOVATION_DF = 6.0

_ENSEMBLE_SEED_STRIDE = 7919  # run_ensemble uses base_seed + 7919*k

# -- ER-14 close-out (D-ER14-2, 2026-08-18): the inflation channel's shared
# state. K = 24 months is C1's declared cpi_trail_k (8 quarters) at the
# engine's monthly resolution - inherited from AM-2026-08-15-001, not chosen
# here. The anchor is the engine's own: _RATE_SHOCK_INFLATION_ANCHOR and
# _DEF["infl_avg"], so a 2% world gets essentially no new drift and adoption
# adds STATE-DEPENDENCE, not return.
INFLATION_TRAIL_MONTHS = 24
INFLATION_ANCHOR_PCT = 2.0

# -- register ER-4: the policy rate has to move for duration to be a risk --- #
_RATE_KAPPA = 0.08  # monthly pull back to the glide path
_RATE_SHOCK_PCT = 0.22  # baseline monthly innovation, in percentage points
# ...scaled by the inflation regime. A world fighting 6% inflation has a far
# noisier policy path than one sitting at target, and if the shock is a global
# constant then bond volatility comes out identical in every world - which is
# the same tell ER-4 was opened for, one level further down.
_RATE_SHOCK_INFLATION_SENSITIVITY = 0.10
_RATE_SHOCK_INFLATION_ANCHOR = 2.0

# -- register ER-1: the credit cycle -------------------------------------- #
_SPREAD_KAPPA = 0.12  # monthly pull of the deviation back to zero
_SPREAD_SHOCK_BPS = 35.0  # monthly innovation on the deviation
_SPREAD_PULSE_WIDTH_DIVISOR = 20.0  # pulse width = horizon / this, in months
_SPREAD_REFERENCE_BPS = 400.0  # the spread a "normal" credit market prices

# Share of the gross spread that is expected DEFAULT LOSS rather than risk
# premium. A spread is compensation for losses that arrive; booking it all as
# carry is what let high yield print a decade Sharpe over 1.5.
_HY_LOSS_SHARE = 0.45
# Realized losses LAG the spreads that price them — the market marks the risk
# roughly a year before the defaults land.
_CREDIT_LOSS_LAG_MONTHS = 12
# Defaults cluster: the same loss rate hurts more when everything else is
# breaking too.
_CRISIS_LOSS_AMPLIFIER = 1.6

# ER-14 close-out coefficients (D-ER14-2 A1, ratified 2026-08-18). Every value is
# the owner's, with its anchor recorded in the design's 2.1/2.2/2.3/2.6.
_LAMBDA_RE = 0.30  # income escalation: C1's declared pm_re_value_add
_GAMMA_RE = 0.50  # cap-rate repricing: partial Fisher, 0.64 x 72% at K=8
_D_RE = 4.0  # NOT new: the property rate duration already in -4.0*d_rate

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
    """One simulated history (single seed).

    ``asset_order`` is the digest/tape iteration order. It defaults to the toy
    ``ASSETS`` tuple so every pre-existing digest is byte-identical; generated
    worlds carry their own order (su-gen-01: reits dropped per OD-3).
    """

    months: int
    seed: int
    rate: np.ndarray
    spread: np.ndarray
    inflation: np.ndarray
    crisis: np.ndarray
    returns: dict[str, np.ndarray]
    reported: dict[str, np.ndarray]
    asset_order: tuple[str, ...] = ASSETS


@dataclass(frozen=True)
class EnsembleResult:
    """An ensemble of histories with returns stacked as ``(n_paths, months)``.

    ``asset_order``: see :class:`EnginePaths` — same contract, same default.
    """

    months: int
    n_paths: int
    seeds: list[int]
    returns: dict[str, np.ndarray]
    reported: dict[str, np.ndarray]
    asset_order: tuple[str, ...] = ASSETS


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
    """Policy rate: a glide from start to end, with REAL monthly innovation.

    Register ER-4. The innovation used to be 0.06%/month (6bp), which against
    a mean reversion of 0.15 left the rate pinned within ~11bp of its glide
    path. Duration risk is in the bond formula (``-6.0 * d_rate``) but with a
    rate that never moves it could not reach the numbers: bond volatility came
    out at 2.7%/yr in ALL FOUR presets, identical to two significant figures
    across completely different rate paths, because what was actually being
    measured was the fixed idiosyncratic term.

    ``_RATE_SHOCK_BPS`` monthly innovation with slower reversion gives a
    stationary spread of about 55bp around the glide — a decade in which the
    rate wanders a point either side of its trend, which is what makes a bond
    a risky asset. The rate remains a CONTINUOUS drift with no meeting
    calendar and no 25bp quantisation; that is ER-2 and still open.
    """
    pr = world.factor_conditions.policy_rate
    start = _f(pr, "start_pct", _DEF["policy_start"])
    end = _f(pr, "end_pct", _DEF["policy_end"])
    infl_avg = _f(world.factor_conditions.inflation, "average_pct", _DEF["infl_avg"])
    shock = _RATE_SHOCK_PCT * (
        1.0 + _RATE_SHOCK_INFLATION_SENSITIVITY * max(0.0, infl_avg - _RATE_SHOCK_INFLATION_ANCHOR)
    )
    rate = np.empty(nm)
    r = start
    for m in range(nm):
        target = start if nm == 1 else start + (end - start) * m / (nm - 1)
        r = max(0.1, r + _RATE_KAPPA * (target - r) + shock * z[m])
        rate[m] = r
    return rate


def _spread_path(world: NumericWorld, nm: int, z: np.ndarray) -> np.ndarray:
    """HY spread: a long-run level, a credit event that CLEARS, and noise.

    Register ER-1's second half. This used to be a triangle — a straight ramp
    to ``hy_spread_peak_bps`` at ``peak_quarter``, then a straight glide back
    over the whole remaining horizon. On the stagflation preset that meant a
    spread starting at 401bp, ending at 358bp, and *averaging 1279bp*: years
    spent at levels that in reality clear in months. A decade-long plateau at
    crisis spreads is not a credit cycle, and it was most of why high yield
    printed 18.7%/yr.

    The peak is now a Gaussian pulse centred on ``peak_quarter``: spreads blow
    out to the declared level and come back in over a few quarters, on top of
    a mean-reverting deviation around the long-run level. The WorldSpec fields
    keep their meaning — the declared peak is still reached, at the declared
    quarter — but the decade average now sits near the start level, where it
    belongs.
    """
    credit = world.factor_conditions.credit
    start = _f(credit, "hy_spread_start_bps", _DEF["hy_start"])
    peak = _f(credit, "hy_spread_peak_bps", _DEF["hy_peak"])
    peak_q = int(getattr(credit, "peak_quarter", None) or _DEF["hy_peak_q"])
    peak_m = min(max(0, peak_q * 3), nm - 1)
    width = max(3.0, nm / _SPREAD_PULSE_WIDTH_DIVISOR)
    spread = np.empty(nm)
    dev = 0.0
    for m in range(nm):
        pulse = (peak - start) * math.exp(-0.5 * ((m - peak_m) / width) ** 2)
        dev = dev * (1.0 - _SPREAD_KAPPA) + _SPREAD_SHOCK_BPS * z[m]
        spread[m] = max(150.0, start + pulse + dev)
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


def _t_draws(rng: np.random.Generator, nm: int, df: float = _INNOVATION_DF) -> np.ndarray:
    """Standardized Student-t innovations: unit variance, excess kurtosis 6/(df-4).

    Register ER-7. Dividing by ``sqrt(df/(df-2))`` rescales the draw to unit
    variance, so swapping this in for ``standard_normal`` adds tail weight
    WITHOUT changing any volatility the WorldSpec declares — a world asking for
    16% equity vol still gets 16% equity vol, it just gets there with occasional
    large months instead of uniformly middling ones. That separation is the whole
    point: the defect was the shape of the tail, not the size of the variance.
    """
    return rng.standard_t(df, nm) / math.sqrt(df / (df - 2.0))


def inflation_excess(
    inflation: np.ndarray,
    *,
    k: int = INFLATION_TRAIL_MONTHS,
    anchor: float = INFLATION_ANCHOR_PCT,
) -> np.ndarray:
    """Trailing-mean inflation less the anchor, in ANNUAL percentage points.

    Warm-up: for m < k-1 the mean is over the months available, not held at
    zero - a decade world is 120 months and two years of dead channel would be
    a fifth of the game. Consumes no RNG.
    """
    infl = np.asarray(inflation, dtype=np.float64)
    csum = np.concatenate([[0.0], np.cumsum(infl)])
    idx = np.arange(infl.size)
    lo = np.maximum(0, idx - k + 1)
    trail = (csum[idx + 1] - csum[lo]) / (idx - lo + 1)
    return trail - anchor


def run_path(world: NumericWorld, seed: int) -> EnginePaths:
    """Simulate one monthly history from ``seed`` (PCG64). Pure & deterministic."""
    _require_toy(world)
    nm = world.horizon.quarters * 3
    rng = np.random.Generator(np.random.PCG64(seed))

    # Draw every stream up front, in a fixed order (determinism anchor).
    #
    # Register ER-7: the MARKET innovations are standardized Student-t, not
    # normal. The macro state innovations below stay Gaussian — the defect was
    # in return tails, and widening rate/inflation shocks would be a different
    # change wearing the same fix's clothes.
    z_rate = rng.standard_normal(nm)
    z_spread = rng.standard_normal(nm)
    z_infl = rng.standard_normal(nm)
    z_m = _t_draws(rng, nm)
    e_eq = _t_draws(rng, nm)
    e_hy = _t_draws(rng, nm)
    e_com = _t_draws(rng, nm)
    e_b = _t_draws(rng, nm)
    e_reit = _t_draws(rng, nm)
    e_pe = _t_draws(rng, nm)
    e_pc = _t_draws(rng, nm)
    e_re = _t_draws(rng, nm)

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
    #
    # Units audit (unit-coherence fix, found live): every return below is a
    # MONTHLY PERCENT (1.5 == 1.5%). STEP0-PLAN's formula set mixed decimal-
    # convention constants (0.007 vol, rate/1200 carry) into percent-space
    # expressions, leaving bonds/commodities with ~zero carry and vol — a
    # ruler-straight commodity line and a deterministic bond slide in the
    # first played decade. All carry terms are now annual-percent/12 and all
    # vol/drag constants are percent-scale; the drift/beta/duration terms
    # were already correct. Deliberate deviation from the plan's literal
    # constants, recorded in the WP commit; golden digest regenerated.
    d_rate = np.diff(rate, prepend=rate[0])
    d_spread = np.diff(spread, prepend=spread[0]) / 100.0

    # ER-14 close-out: the shared inflation-excess state, computed once
    # immediately after d_rate/d_spread; every mechanism below reads it.
    # Same convention as d_rate: month 0 has zero first-difference.
    x = inflation_excess(inflation)
    d_x = np.diff(x, prepend=x[0])

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

    # Register ER-1: credit assets earn their spread NET of the defaults that
    # spread is pricing. Losses key on the spread as it stood a year earlier —
    # the market marks the risk before the defaults land — and cluster inside
    # crisis months. Without this, high yield booked the full current spread as
    # carry every month and cleared a decade Sharpe of 1.54.
    lag = min(_CREDIT_LOSS_LAG_MONTHS, nm)
    spread_lagged = np.concatenate([np.full(lag, spread[0]), spread[:-lag]])[:nm]
    loss_amp = np.where(crisis > 0, _CRISIS_LOSS_AMPLIFIER, 1.0)
    # gross spread in annual percent (bps -> pct), as at the loss lag
    spread_ann = spread_lagged / 100.0
    hy_loss_m = _HY_LOSS_SHARE * spread_ann / 12.0 * loss_amp
    # Private credit is senior secured, so it loses less than high yield for
    # the same cycle — but it does lose, and it loses MORE when spreads are
    # wide. The old formula charged only 0.6x its own loss rate outside crisis
    # months, which is why it cleared a Sharpe near 2 in every world.
    pc_loss_m = (pc_loss / 12.0) * (0.7 + 0.6 * spread_lagged / _SPREAD_REFERENCE_BPS) * loss_amp

    eq = eq_drift / 12.0 + eq_vol_m * z_eq - 2.2 * crisis
    bonds = rate / 12.0 - 6.0 * d_rate + 0.7 * z_b
    hy = (
        rate / 12.0
        + spread / 1200.0
        - hy_loss_m
        - 3.5 * d_spread
        + 0.5 * eq_vol_m * z_hy
        - 0.6 * crisis
    )
    commodities = com_drift / 12.0 + max(0.0, infl_avg - 2.5) / 12.0 + 5.2 * z_com
    reits = 0.65 * eq - 2.5 * d_rate + 2.6 * e_reit
    pe = 1.4 * eq + (pe_illiq + pe_mult) / 12.0 + 2.0 * e_pe
    # A private credit book reprices when public credit does - less than high
    # yield, because it is senior secured, but it is not immune. Without a
    # credit-cycle beta its only risk was idiosyncratic noise.
    pc = (rate + 4.5) / 12.0 - pc_loss_m - 0.8 * d_spread + 0.18 * eq + 1.45 * e_pc
    # Property is rate-sensitive (cap rates move with rates) and reprices hard
    # in a crisis; both were missing, leaving it a near-riskless income stream.
    re = (
        4.5 / 12.0
        - re_cap / (100.0 * nm) * 2.2
        - _D_RE * d_rate
        + 0.35 * eq
        + 1.5 * e_re
        - 1.0 * crisis
        # ER-14: leases escalate with the price level (a LEVEL effect on x), while
        # nominal discount rates lift cap rates and mark a long-duration asset down
        # (a CHANGE effect on dx). Same duration the rate term already uses.
        + _LAMBDA_RE * x / 12.0
        - _D_RE * _GAMMA_RE * d_x
    )

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
    # Limited liability (ER-7 close-out): no long-only stream loses more than
    # everything in a month. See _MONTHLY_RETURN_FLOOR_PCT.
    returns = {k: np.maximum(v, _MONTHLY_RETURN_FLOOR_PCT) for k, v in returns.items()}

    reported = _reported_marks(world, returns)
    return EnginePaths(nm, seed, rate, spread, inflation, crisis, returns, reported)


def _reported_marks(world: NumericWorld, returns: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Appraisal-smoothed marks for pe/pc/re: nonzero only at quarter-ends.

    The quarter-end mark filters the WHOLE quarter's compounded true return:
    ``rep_q = w * q_true + (1 - w) * rep_{q-1}`` (Geltner partial
    adjustment, unit DC gain, so cumulative reported catches up to
    cumulative true). History: until toy-v0.6 this filtered only the
    closing MONTH's return, discarding the quarter's other two months —
    reported PM cumulated ~1/3 of truth (ER-10, found 2026-08-12 by the
    owner reading a chart)."""
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
                q_true = (
                    (1.0 + true[m - 2] / 100.0)
                    * (1.0 + true[m - 1] / 100.0)
                    * (1.0 + true[m] / 100.0)
                    - 1.0
                ) * 100.0
                prev = w * q_true + (1.0 - w) * prev
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
