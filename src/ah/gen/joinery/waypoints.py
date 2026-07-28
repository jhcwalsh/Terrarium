"""WP2.7 waypoints — the year-by-year skeleton of each decade (DN-1.1 §II.5).

Per calendar year y of a decade, L1 (slow states + posterior theta) and L2 (regime
path + cycle) emit:

(i)   the annual mean of the policy anchor i_t (:func:`ah.gen.climate.simulate.
      policy_anchor` under L2's cycle) and of trend inflation pi*_t;
(ii)  the cumulative log equity drift implied by valuation dynamics + the regime
      path — the stated mapping (see :func:`build_waypoints`):

          drift_y = (a_val - b_val·v̄_y)/100 + π̄*_y/100 + Σ_{m∈y}(μ_R(m) - μ̄)

      where a_val/b_val are that decade's posterior draw (DN-1.1: E[r_equity(10y)]
      = a - b·v, fitted on 10-year forward REAL log equity returns in log-percent,
      so the nominal annual log drift adds expected inflation π̄*), v̄_y/π̄*_y are the
      year's state means, and μ_R is the train+validation mean monthly log equity
      return within regime R over the bootstrap draw span (μ̄ its unconditional
      mean) — the regime path contributes texture around the valuation anchor;
(iii) a year-end spread level BAND, not a point — the stated mapping:

          center_y = μ_spread(R_yend) + β_L·credit_gap_yend,
          half-width = sigma_resid(R_yend)

      with μ_spread(R) the train+validation mean ig_spread by regime, β_L the OLS
      loading of the regime-demeaned historical spread on the L1 posterior-mean
      credit-gap path over the same months, and sigma_resid(R) that regression's
      REGIME-CONDITIONAL residual sd (all from :func:`source_stats`, train+validation
      only; :func:`_spread_band_widths` states the estimator and WP2.7b records why
      the single pooled width it replaced was refuted by the reference data itself);
(iv)  the regime path itself (with WorldSpec ``crisis_windows`` overlaid as CRI).

WorldSpec ``factor_conditions`` bind HERE, as overrides/tilts on w — the single
binding point for authored worlds (STEP2 §WP2.7). Every schema field is
implemented; fields that name factors the generated set does not carry
(``credit.*`` binds ``hy_spread``; ``commodities.*`` binds ``commodities`` — both
in the sealed ``reference_run.missing_factors``) are recorded on the waypoint
record as explicit UNBOUND overrides rather than silently remapped onto a
different factor (schemas/ wins on field definitions). ``correlation`` and
``equity.vol_annual_pct`` cannot bind an annual aggregate; they pass through to
the conditioning record for L3.

Waypoints are per-decade and deterministic given (states, regimes, conditions,
source statistics): no RNG anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.core.worldspec import FactorConditions
from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.simulate import ClimateArtifact, SimulatedClimate, policy_anchor
from ah.gen.regimes.semimarkov import REGIME_LABELS, RegimePaths

__all__ = [
    "BAND_PRIOR_DF",
    "BAND_RHO_CLIP",
    "RATE_FLOOR_FACTORS",
    "RATE_FLOOR_PCT",
    "REGIME_LABELS",
    "SPREAD_FLOOR_FACTORS",
    "SPREAD_FLOOR_PCT",
    "DecadeWaypoints",
    "JoineryError",
    "MonthlyTargets",
    "SourceStats",
    "build_waypoints",
    "monthly_targets",
    "source_stats",
    "year_spans",
]


class JoineryError(RuntimeError):
    """Raised for an input the joinery cannot honestly assemble from."""


# --------------------------------------------------------------------------- #
# hard floors (DN-1.1 §II.4 coordinates, as sealed)
#
# These restate — deliberately, because ah.gen must never import ah.eval — the
# floors `pre-registration.yaml`'s sealed `floor_violations_estimator` convention
# states and `ah.eval.metrics.economics` enforces (RATE_FLOOR_FACTORS at -1.0
# percentage points; SPREAD_FLOOR_FACTORS at 0.0, the sealed WP2.2c correction of
# DN-1.1's literal 100bp). tests/test_joinery_reconcile.py pins these four
# constants to the ah.eval originals so the two statements cannot drift — the
# same machine-check-over-refactor pattern ah.gen.bootstrap uses for the factor
# resolver.
# --------------------------------------------------------------------------- #

RATE_FLOOR_FACTORS: tuple[str, ...] = ("policy_rate", "ust_2y", "ust_10y", "hqm_curve")
RATE_FLOOR_PCT = -1.0
SPREAD_FLOOR_FACTORS: tuple[str, ...] = ("ig_spread", "hy_spread", "funding_spread")
SPREAD_FLOOR_PCT = 0.0

_LABEL_INDEX = {label: i for i, label in enumerate(REGIME_LABELS)}
_CRI = _LABEL_INDEX["CRI"]
#: The c_t value crisis-window overlay months carry: by ruleset construction CRI
#: months always have USREC=1, i.e. c = -1 (see ah.gen.regimes.semimarkov).
_CRI_CYCLE = -1.0

# --------------------------------------------------------------------------- #
# WP2.7b band-width estimator constants.
#
# Both are properties of the ESTIMATOR, chosen from the reference data alone and
# never from any generator's score (see _spread_band_widths).
# --------------------------------------------------------------------------- #

#: Prior strength of the variance shrinkage, in degrees of freedom — one degree of
#: freedom of prior information, the weakest proper shrinkage. The empirical-Bayes
#: marginal MLE on the campaign vintage brackets it (nu0 = 1.25 with the prior
#: centred on the pooled variance, 1.78 jointly), but that hyperparameter is not
#: robustly identified from six groups — dropping CRI alone moves it from 1.4 to
#: 17.8 — so the weak stated value is used and the fit is reported as corroboration.
BAND_PRIOR_DF = 1.0

#: The lag-1 autocorrelation entering the effective-sample-size correction is
#: clipped to [0, BAND_RHO_CLIP]: the correction diverges as rho -> 1, and a
#: negative estimate would claim MORE information than the month count.
BAND_RHO_CLIP = 0.95

#: The four factors waypoints bind, and the state-vector indices they read.
WAYPOINT_FACTORS: tuple[str, ...] = ("policy_rate", "cpi", "equity_mkt", "ig_spread")
_STATE_PI_STAR = 0
_STATE_V = 3
_STATE_CREDIT_GAP = 4


def year_spans(months: int) -> list[slice]:
    """Calendar-year month slices of a decade: [0:12), [12:24), ... (last may be short)."""
    if months < 1:
        raise JoineryError("months must be >= 1")
    return [slice(s, min(s + 12, months)) for s in range(0, months, 12)]


# --------------------------------------------------------------------------- #
# train+validation source statistics (through the sanctioned surface: the
# BootstrapSource was built via DataAccess.train_val; the climate artifact's
# smoothed states are the L1 posterior over the same train+validation panel)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceStats:
    """Regime-conditional statistics the waypoint mappings need, train+val only.

    ``absent_regimes`` names labels with no month in the draw span (STAG is the
    expected member on the real 1990-2020 span): their per-regime means fall back
    to the unconditional mean, VISIBLY — support.py's regime-frequency check is
    what flags decades that lean on them.
    """

    equity_mean_log_by_regime: np.ndarray  # (6,) mean monthly log1p(equity_mkt) by label
    equity_mean_log_overall: float
    spread_mean_by_regime: np.ndarray  # (6,) mean ig_spread level by label
    spread_beta_credit_gap: float
    spread_resid_sd: float  # POOLED residual sd: the absent-regime fallback, and the
    # number WP2.7/WP2.8's published artifacts quote. NOT the band width any more.
    spread_band_half_width_by_regime: np.ndarray  # (6,) the band half-width per label
    spread_band_diagnostics: dict[str, Any]  # JSON-safe estimator report (see below)
    h0_equity_ret_12m: float  # unconditional trailing-12m log equity return
    h0_equity_vol_12m: float  # unconditional monthly log-return sd
    h0_spread_level: float  # unconditional ig_spread level
    absent_regimes: tuple[str, ...]


def _contiguous_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[(start, stop), ...] for each maximal run of True in ``mask``."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    stops = np.concatenate((idx[breaks], [idx[-1]])) + 1
    return [(int(a), int(b)) for a, b in zip(starts, stops, strict=True)]


def _spread_band_widths(
    resid: np.ndarray, codes: np.ndarray, pooled_sd: float
) -> tuple[np.ndarray, dict[str, Any]]:
    """The regime-conditional band half-width sigma_resid(R). WP2.7b.

    ``resid`` is the spread residual the band is built on — historical ig_spread
    minus its regime mean minus beta_L * credit_gap — and ``codes`` its regime
    labels. Train+validation only: the caller has already sourced both through the
    sanctioned surface.

    WHY THIS IS NOT A SINGLE POOLED NUMBER. The pooled residual sd this replaces
    was refuted by the reference data on its own terms, before any generator was
    consulted: on the campaign vintage the six within-regime variances span a
    201x range (a run-permutation test that preserves the serial structure gives
    p = 0.003 against homoskedasticity), and the pooled width it implies is
    simultaneously 1.2x-2.4x wider than the four quiet regimes support and far too
    narrow for CRI — real 1990-2020 spreads sit OUTSIDE their own pooled CRI band
    in 16 of 17 months (94.1%), while never leaving the STAG or REF band at all. A
    width the reference itself cannot sit inside is not an estimate of the reference.

    THE ESTIMATOR, stated in full:

    1. Within each regime, s_R^2 is the residual variance about that regime's own
       mean (ddof=1).
    2. Months are serially dependent, so a regime's month count overstates its
       information. rho_R is the lag-1 autocorrelation measured over CONTIGUOUS
       month pairs inside the regime (a regime's months are not contiguous in
       calendar time), clipped to [0, BAND_RHO_CLIP], and gives the two standard
       AR(1) effective sizes: n_eff = n(1-rho)/(1+rho) for a MEAN and
       n_eff_var = n(1-rho^2)/(1+rho^2) for a VARIANCE. On the campaign vintage
       every regime has between 1.6 and 11.8 effective observations, EXP's 231
       months included; the independent count of contiguous episodes agrees within
       a factor of two, and both are reported.
    3. s_R^2 is shrunk toward a typical within-regime variance s0^2 with
       nu_R = n_eff_var - 1 degrees of freedom against BAND_PRIOR_DF, which is what
       stops a thin regime's few months from asserting a near-zero width.
    4. s0^2 is the INFORMATION-WEIGHTED GEOMETRIC MEAN of the group variances, not
       the arithmetic pool: on the campaign vintage 51% of the pooled residual
       variance comes from CRI's 17 months, so the arithmetic pool is a crisis
       statistic and shrinking the quiet regimes toward it would re-import exactly
       the contamination this estimator exists to remove.
    5. The half-width is a PREDICTIVE sd: sigma_R * sqrt(1 + 1/n_eff_R). The band's
       centre mu_spread(R) is itself estimated on n_eff_R observations, and a
       year-end level deviates from the ESTIMATED centre by that much more. This
       is why the centre is left alone (see build_waypoints): centre noise is
       carried as width, not as a shift of the crisis target toward normal times.

    Regimes with fewer than two months (an absent regime falls back to the
    unconditional mean, visibly) fall back to ``pooled_sd`` and are flagged.
    Everything is a deterministic function of the inputs — no RNG, no fitting to
    any generated quantity.
    """
    n_lab = len(REGIME_LABELS)
    n = np.array([int(np.count_nonzero(codes == c)) for c in range(n_lab)])
    group_mean = np.array([float(resid[codes == c].mean()) if n[c] else 0.0 for c in range(n_lab)])
    e = resid - group_mean[codes]

    s2 = np.zeros(n_lab)
    rho = np.zeros(n_lab)
    n_runs = np.zeros(n_lab, dtype=np.int64)
    for c in range(n_lab):
        runs = _contiguous_runs(codes == c)
        n_runs[c] = len(runs)
        if n[c] < 2:
            continue
        ec = e[codes == c]
        s2[c] = float(np.var(ec, ddof=1))
        lag = [(e[a : b - 1], e[a + 1 : b]) for a, b in runs if b - a >= 2]
        denom = float(ec @ ec)
        if lag and denom > 0.0:
            first = np.concatenate([p[0] for p in lag])
            second = np.concatenate([p[1] for p in lag])
            rho[c] = min(max(float(first @ second) / denom, 0.0), BAND_RHO_CLIP)

    n_eff = np.maximum(n * (1.0 - rho) / (1.0 + rho), 1.0)
    n_eff_var = np.maximum(n * (1.0 - rho**2) / (1.0 + rho**2), 2.0)
    nu = n_eff_var - 1.0

    usable = (n >= 2) & (s2 > 0.0)
    if np.any(usable):
        s0_2 = float(np.exp(np.sum(nu[usable] * np.log(s2[usable])) / np.sum(nu[usable])))
    else:
        s0_2 = float(pooled_sd**2)

    sigma2 = (nu * s2 + BAND_PRIOR_DF * s0_2) / (nu + BAND_PRIOR_DF)
    half = np.sqrt(sigma2) * np.sqrt(1.0 + 1.0 / n_eff)
    fallback = n < 2
    half = np.where(fallback, pooled_sd, half)
    half = np.maximum(half, 1e-6)

    diagnostics: dict[str, Any] = {
        "estimator": (
            "regime-conditional predictive residual sd: variance shrunk toward the "
            "information-weighted geometric-mean within-regime variance with "
            "BAND_PRIOR_DF degrees of prior freedom, then inflated by "
            "sqrt(1 + 1/n_eff) for the band centre's own estimation error"
        ),
        "prior_df": float(BAND_PRIOR_DF),
        "rho_clip": float(BAND_RHO_CLIP),
        "typical_sd": float(np.sqrt(s0_2)),
        "pooled_sd": float(pooled_sd),
        "by_regime": {
            REGIME_LABELS[c]: {
                "n": int(n[c]),
                "n_runs": int(n_runs[c]),
                "rho": float(rho[c]),
                "n_eff_mean": float(n_eff[c]),
                "n_eff_var": float(n_eff_var[c]),
                "raw_sd": float(np.sqrt(s2[c])),
                "shrunk_sd": float(np.sqrt(sigma2[c])),
                "half_width": float(half[c]),
                "fallback": bool(fallback[c]),
            }
            for c in range(n_lab)
        },
    }
    return half, diagnostics


def _column(source: BootstrapSource, name: str) -> np.ndarray:
    try:
        return source.values[:, list(source.factor_names).index(name)]
    except ValueError:
        raise JoineryError(
            f"joinery needs factor '{name}' in the block source; source carries "
            f"{list(source.factor_names)}"
        ) from None


def source_stats(source: BootstrapSource, climate: ClimateArtifact) -> SourceStats:
    """Compute the waypoint mappings' statistics from the draw span + L1 posterior.

    Deterministic: pure functions of the (immutable) source and artifact. The
    credit-gap regressor is the posterior MEAN smoothed credit-gap path at the
    source's dates — the artifact's fit span must cover the draw span.
    """
    for name in WAYPOINT_FACTORS:
        _column(source, name)  # raise early, with the factor named

    codes = np.array([_LABEL_INDEX[label] for label in source.labels], dtype=np.int64)
    eq_log = np.log1p(_column(source, "equity_mkt"))
    spread = _column(source, "ig_spread")

    idx = climate.dates.get_indexer(source.dates)
    if np.any(idx < 0):
        first = source.dates[int(np.flatnonzero(idx < 0)[0])]
        raise JoineryError(
            f"climate artifact grid ({climate.dates[0].date()}..{climate.dates[-1].date()}) "
            f"does not cover source month {first.date()}"
        )
    credit_gap = climate.states.mean(axis=0)[idx, _STATE_CREDIT_GAP]

    n = len(REGIME_LABELS)
    eq_by = np.full(n, np.nan)
    sp_by = np.full(n, np.nan)
    for code in range(n):
        mask = codes == code
        if np.any(mask):
            eq_by[code] = float(eq_log[mask].mean())
            sp_by[code] = float(spread[mask].mean())
    absent = tuple(REGIME_LABELS[code] for code in range(n) if np.isnan(eq_by[code]))
    eq_overall = float(eq_log.mean())
    sp_overall = float(spread.mean())
    eq_by = np.where(np.isnan(eq_by), eq_overall, eq_by)
    sp_by = np.where(np.isnan(sp_by), sp_overall, sp_by)

    resid = spread - sp_by[codes]
    var = float(np.var(credit_gap))
    beta = float(np.cov(resid, credit_gap)[0, 1] / var) if var > 1e-12 else 0.0
    band_resid = resid - beta * credit_gap
    resid_sd = max(float(np.std(band_resid, ddof=1)) if resid.size > 1 else 0.0, 1e-6)
    band_half, band_diag = _spread_band_widths(band_resid, codes, resid_sd)

    return SourceStats(
        equity_mean_log_by_regime=eq_by,
        equity_mean_log_overall=eq_overall,
        spread_mean_by_regime=sp_by,
        spread_beta_credit_gap=beta,
        spread_resid_sd=resid_sd,
        spread_band_half_width_by_regime=band_half,
        spread_band_diagnostics=band_diag,
        h0_equity_ret_12m=12.0 * eq_overall,
        h0_equity_vol_12m=float(np.std(eq_log, ddof=1)),
        h0_spread_level=sp_overall,
        absent_regimes=absent,
    )


# --------------------------------------------------------------------------- #
# the waypoint record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DecadeWaypoints:
    """One decade's annual waypoints w (all arrays length ``n_years``) + regime path.

    ``record`` is the JSON-safe conditioning record: which WorldSpec overrides
    bound, which could not (and why), and the pass-through fields L3 will consume
    (correlation regime, equity vol target, crisis-window severities).
    """

    policy_pct: np.ndarray
    inflation_pct: np.ndarray
    equity_log_drift: np.ndarray  # per-year log drift (flow); cumulative via cumsum
    spread_center_pct: np.ndarray
    spread_lo_pct: np.ndarray
    spread_hi_pct: np.ndarray
    labels: np.ndarray  # (months,) int codes, crisis windows overlaid
    cycle: np.ndarray  # (months,) the c_t used for the anchor (overlay applied)
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def n_years(self) -> int:
        return int(self.policy_pct.shape[0])

    @property
    def months(self) -> int:
        return int(self.labels.shape[0])


def _overlay_crisis_windows(
    labels: np.ndarray, cycle: np.ndarray, conditions: FactorConditions | None, months: int
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """WorldSpec crisis_windows overlaid as CRI months (deterministic stress episodes)."""
    labels = labels.copy()
    cycle = cycle.copy()
    windows: list[dict[str, Any]] = []
    if conditions is None or not conditions.crisis_windows:
        return labels, cycle, windows
    for window in conditions.crisis_windows:
        lo = min(int(window.start_quarter) * 3, months)
        hi = min((int(window.start_quarter) + int(window.length_quarters)) * 3, months)
        labels[lo:hi] = _CRI
        cycle[lo:hi] = _CRI_CYCLE
        windows.append(
            {
                "start_month": lo,
                "end_month": hi,
                "severity": float(window.severity),
                "clipped_to_horizon": hi
                < (int(window.start_quarter) + int(window.length_quarters)) * 3,
            }
        )
    return labels, cycle, windows


def _policy_shape(start: float, end: float, shape: str, tau: np.ndarray) -> np.ndarray:
    """The authored policy path at decade fractions ``tau`` (year midpoints).

    Shapes (stated here because the schema names but does not define them):
    ``linear`` interpolates; ``front_loaded`` covers 1-(1-tau)^2 of the move by
    tau; ``back_loaded`` covers tau^2; ``spike_and_settle`` rises linearly to a
    peak of ``max(start, end) + 0.5*max(|end-start|, 1.0)`` at tau=0.25, then
    settles linearly to ``end``.
    """
    if shape == "linear":
        return start + (end - start) * tau
    if shape == "front_loaded":
        return start + (end - start) * (1.0 - (1.0 - tau) ** 2)
    if shape == "back_loaded":
        return start + (end - start) * tau**2
    if shape == "spike_and_settle":
        peak = max(start, end) + 0.5 * max(abs(end - start), 1.0)
        tau_p = 0.25
        rising = start + (peak - start) * (tau / tau_p)
        settling = peak + (end - peak) * ((tau - tau_p) / (1.0 - tau_p))
        return np.where(tau <= tau_p, rising, settling)
    raise JoineryError(f"unknown policy path_shape '{shape}'")


def _bind_policy(
    policy: np.ndarray, conditions: FactorConditions | None, record: dict[str, Any]
) -> np.ndarray:
    if conditions is None or conditions.policy_rate is None:
        return policy
    pr = conditions.policy_rate
    if pr.start_pct is None and pr.end_pct is None:
        return policy
    n_years = policy.shape[0]
    start = float(policy[0]) if pr.start_pct is None else float(pr.start_pct)
    end = float(policy[-1]) if pr.end_pct is None else float(pr.end_pct)
    tau = (np.arange(n_years) + 0.5) / n_years
    shaped = np.maximum(_policy_shape(start, end, str(pr.path_shape), tau), RATE_FLOOR_PCT)
    record["policy_override"] = {
        "bound": True,
        "start_pct": start,
        "end_pct": end,
        "path_shape": str(pr.path_shape),
    }
    return shaped


def _bind_inflation(
    inflation: np.ndarray, conditions: FactorConditions | None, record: dict[str, Any]
) -> np.ndarray:
    if conditions is None or conditions.inflation is None:
        return inflation
    spec = conditions.inflation
    if spec.average_pct is None and spec.peak_pct is None:
        return inflation
    out = inflation.copy()
    n_years = out.shape[0]
    entry: dict[str, Any] = {"bound": True}
    if spec.average_pct is not None:
        out = out + (float(spec.average_pct) - float(out.mean()))
        entry["average_pct"] = float(spec.average_pct)
    if spec.peak_pct is not None:
        # Place the peak: a triangular bump (radius 2 years) centered on the peak
        # year lifts (or lowers) the peak year to exactly peak_pct; when an average
        # is also authored, the years OUTSIDE the bump absorb the bump's mass so the
        # decade average is preserved exactly (peak untouched). peak_quarter beyond
        # the horizon clamps to the last year, recorded.
        quarter = 0 if spec.peak_quarter is None else int(spec.peak_quarter)
        y_peak = min(quarter // 4, n_years - 1)
        entry["peak_pct"] = float(spec.peak_pct)
        entry["peak_year"] = y_peak
        entry["peak_quarter_clipped"] = quarter // 4 > n_years - 1
        bump = np.maximum(0.0, 1.0 - np.abs(np.arange(n_years) - y_peak) / 2.0)
        amp = float(spec.peak_pct) - float(out[y_peak])
        out = out + amp * bump
        if spec.average_pct is not None:
            outside = bump == 0.0
            if np.any(outside):
                out[outside] -= amp * float(bump.sum()) / int(np.count_nonzero(outside))
            else:
                entry["average_not_recentered"] = True
    record["inflation_override"] = entry
    return out


def _bind_equity(
    drift: np.ndarray,
    regime_term: np.ndarray,
    spans: list[slice],
    conditions: FactorConditions | None,
    record: dict[str, Any],
) -> np.ndarray:
    if conditions is not None and conditions.equity is not None:
        if conditions.equity.vol_annual_pct is not None:
            # An annual aggregate cannot bind a volatility; pass through for L3.
            record["equity_vol_target_annual_pct"] = float(conditions.equity.vol_annual_pct)
        if conditions.equity.drift_annual_pct is not None:
            annual = float(np.log1p(conditions.equity.drift_annual_pct / 100.0))
            year_frac = np.array([(s.stop - s.start) / 12.0 for s in spans])
            centered = regime_term - regime_term.mean()
            record["equity_override"] = {
                "bound": True,
                "drift_annual_pct": float(conditions.equity.drift_annual_pct),
            }
            return annual * year_frac + centered
    return drift


def _record_unbindable(conditions: FactorConditions | None, record: dict[str, Any]) -> None:
    """Overrides whose target factor carries no train+validation data — recorded, not bound.

    ``credit.*`` binds ``hy_spread`` and ``commodities.*`` binds ``commodities``;
    both are in the sealed ``reference_run.missing_factors``, so no generated path
    exists to reconcile against them. Remapping the authored hy numbers onto
    ``ig_spread`` would violate the schema's field definition (schemas/ wins), so
    the override is carried on the record — visible to a reader and to L3 — and the
    structural ig_spread band stands.
    """
    if conditions is None:
        return
    if conditions.credit is not None and any(
        v is not None
        for v in (
            conditions.credit.hy_spread_start_bps,
            conditions.credit.hy_spread_peak_bps,
            conditions.credit.peak_quarter,
        )
    ):
        record["credit_override"] = {
            "bound": False,
            "reason": "hy_spread has no train+validation data on the sealed campaign "
            "vintage (reference_run.missing_factors); the authored values are recorded, "
            "not remapped onto ig_spread",
            "hy_spread_start_bps": conditions.credit.hy_spread_start_bps,
            "hy_spread_peak_bps": conditions.credit.hy_spread_peak_bps,
            "peak_quarter": conditions.credit.peak_quarter,
        }
    if conditions.commodities is not None and conditions.commodities.drift_annual_pct is not None:
        record["commodities_override"] = {
            "bound": False,
            "reason": "commodities has no Step-1 source (sealed missing_factors)",
            "drift_annual_pct": float(conditions.commodities.drift_annual_pct),
        }
    if conditions.correlation is not None:
        record["correlation"] = {
            "equity_bond_regime": str(conditions.correlation.equity_bond_regime),
            "crisis_correlation_boost": conditions.correlation.crisis_correlation_boost,
            "note": "pass-through to L3 conditioning; a correlation cannot bind a waypoint",
        }


def build_waypoints(
    sim: SimulatedClimate,
    regimes: RegimePaths,
    stats: SourceStats,
    *,
    conditions: FactorConditions | None = None,
) -> list[DecadeWaypoints]:
    """Waypoints for every decade of ``sim``/``regimes`` (DN-1.1 §II.5 step 3).

    Structural waypoints first (the module docstring's mappings i-iv), then
    WorldSpec ``factor_conditions`` applied as overrides/tilts. Deterministic:
    no RNG. The policy waypoint is floored at :data:`RATE_FLOOR_PCT` and the
    spread band at :data:`SPREAD_FLOOR_PCT` at construction, so reconciliation
    targets are always feasible under the hard floors.
    """
    if sim.n_decades != regimes.n_decades or sim.months != regimes.months:
        raise JoineryError(
            f"L1/L2 shape mismatch: climate is ({sim.n_decades}, {sim.months}), "
            f"regimes is ({regimes.n_decades}, {regimes.months})"
        )
    months = sim.months
    spans = year_spans(months)

    # Crisis windows overlay labels AND the cycle before anything reads either.
    labels_all = np.empty_like(regimes.labels)
    cycle_all = np.empty_like(regimes.cycle)
    windows_record: list[dict[str, Any]] = []
    for k in range(sim.n_decades):
        labels_all[k], cycle_all[k], windows_record = _overlay_crisis_windows(
            regimes.labels[k], regimes.cycle[k], conditions, months
        )

    anchor = policy_anchor(sim, cycle=cycle_all)
    pi_star = sim.state("pi_star")
    v_state = sim.state("v")
    credit_gap = sim.state("credit_gap")

    out: list[DecadeWaypoints] = []
    for k in range(sim.n_decades):
        labels = labels_all[k]
        a_val = float(sim.params["a_val"][k])
        b_val = float(sim.params["b_val"][k])

        policy = np.array([max(float(anchor[k, s].mean()), RATE_FLOOR_PCT) for s in spans])
        inflation = np.array([float(pi_star[k, s].mean()) for s in spans])

        regime_dev = stats.equity_mean_log_by_regime[labels] - stats.equity_mean_log_overall
        regime_term = np.array([float(regime_dev[s].sum()) for s in spans])
        drift = np.array(
            [
                (a_val - b_val * float(v_state[k, s].mean())) / 100.0
                + float(pi_star[k, s].mean()) / 100.0
                + regime_term[y]
                for y, s in enumerate(spans)
            ]
        )

        yends = np.array([s.stop - 1 for s in spans])
        center = np.maximum(
            stats.spread_mean_by_regime[labels[yends]]
            + stats.spread_beta_credit_gap * credit_gap[k, yends],
            SPREAD_FLOOR_PCT,
        )
        # WP2.7b: the half-width is the year-end REGIME's width. The centre is
        # deliberately unchanged — mu_spread(R) is the estimand DN-1.1 II.5 names,
        # it is unbiased, and shrinking it toward the unconditional mean would bias
        # the crisis target toward normal-times levels. Its estimation error is
        # carried in the width instead (the sqrt(1 + 1/n_eff) term).
        half = stats.spread_band_half_width_by_regime[labels[yends]]
        lo = np.maximum(center - half, SPREAD_FLOOR_PCT)
        hi = np.maximum(center + half, lo + 1e-9)

        record: dict[str, Any] = {}
        if stats.absent_regimes:
            record["absent_regimes"] = list(stats.absent_regimes)
        if windows_record:
            record["crisis_windows"] = windows_record
        policy = _bind_policy(policy, conditions, record)
        inflation = _bind_inflation(inflation, conditions, record)
        drift = _bind_equity(drift, regime_term, spans, conditions, record)
        _record_unbindable(conditions, record)

        out.append(
            DecadeWaypoints(
                policy_pct=policy,
                inflation_pct=inflation,
                equity_log_drift=drift,
                spread_center_pct=center,
                spread_lo_pct=lo,
                spread_hi_pct=hi,
                labels=labels,
                cycle=cycle_all[k],
                record=record,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# monthly target curves (block conditioning; NOT the reconciliation targets —
# reconcile.py binds the annual aggregates exactly)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MonthlyTargets:
    """Monthly interpolations of the annual waypoints, for Δw block conditioning."""

    policy_pct: np.ndarray
    log_cpi: np.ndarray  # relative to month 0 (waypoints constrain inflation, not P0)
    equity_cum_log: np.ndarray
    spread_center_pct: np.ndarray


def cum_log_cpi_targets(wp: DecadeWaypoints) -> np.ndarray:
    """Year-end log CPI relative to month 0.

    Year 0 spans month 0..11: eleven monthly increments, so it carries
    (n_months-1)/12 of its annual inflation; later years carry n_months/12.
    """
    spans = year_spans(wp.months)
    increments = np.array(
        [
            ((s.stop - s.start) - (1 if y == 0 else 0)) / 12.0 * wp.inflation_pct[y] / 100.0
            for y, s in enumerate(spans)
        ]
    )
    return np.cumsum(increments)


def monthly_targets(wp: DecadeWaypoints, months: int) -> MonthlyTargets:
    """Piecewise-linear monthly curves through the annual waypoint anchors."""
    if months != wp.months:
        raise JoineryError(f"months mismatch: waypoints cover {wp.months}, asked for {months}")
    spans = year_spans(months)
    m = np.arange(months, dtype=np.float64)
    centers = np.array([(s.start + s.stop - 1) / 2.0 for s in spans])
    ends = np.array([float(s.stop - 1) for s in spans])

    policy = np.interp(m, centers, wp.policy_pct)
    log_cpi = np.interp(
        m, np.concatenate(([0.0], ends)), np.concatenate(([0.0], cum_log_cpi_targets(wp)))
    )
    equity = np.interp(
        m, np.concatenate(([-1.0], ends)), np.concatenate(([0.0], np.cumsum(wp.equity_log_drift)))
    )
    spread = np.interp(m, ends, wp.spread_center_pct)
    return MonthlyTargets(
        policy_pct=policy, log_cpi=log_cpi, equity_cum_log=equity, spread_center_pct=spread
    )
