"""Spine v2, week 2: FIT the season engine to history, and verify it in-model.

Spec: ``docs/superpowers/specs/2026-08-17-spine-v2-exam.md`` (SEALED).
Pre-registration: ``docs/superpowers/specs/spine-v2-prereg.json``. **Nothing this
module touches is hashed by that seal.** It reads the seal, imports the sealed
grader (``scripts/spine_v2_grader.py``) and the sealed judges
(``scripts/spine_v2_report.py``), and writes only two new files:

- ``docs/superpowers/specs/spine-v2-fitted-params.json`` -- the fitted parameters,
- ``docs/superpowers/specs/2026-08-17-spine-v2-fit-report.md`` -- the write-up
  (authored by hand from this script's own printed output).

What is fitted
--------------
A **discrete-time monthly hazard for season transitions**, over the four
investment-clock seasons of ``grader_v2``. The season is
``(growth axis, inflation axis)``, exactly as on the history side, so the model
has two dials and only one of them is a free chain:

- the **inflation axis** ("hot") is read off the simulated inflation path, the
  same way history's is read off observed trailing CPI -- it is not sampled;
- the **growth axis** ("contracting" = the ``grader_v2`` set ``{REC, CRI, STAG}``)
  is the chain. Its monthly flip hazard is what this module fits.

That factorisation is not a convenience: it is what makes the generated side and
the history side the *same measurement*. On history the season is a function of
(``regime_ruleset_v1`` label, trailing CPI); in the simulator it is a function of
(the chain's growth axis, the simulated inflation path), and the sealed judge does
the classifying on both sides through the same ``season_cells`` call.

The hazard, and its likelihood
------------------------------
For every at-risk month ``t`` (defined below), with ``s_t`` the season, ``d_t``
the months elapsed in the current SEASON spell (1-based) and ``z_t`` the four
covariates::

    logit h_t = a_{s_t} + b_{s_t} * log(d_t) + z_t' g_{dir(s_t)}
    y_t       = 1[growth axis at t+1 differs from growth axis at t]
    log L     = sum_t w_t * [ y_t log h_t + (1 - y_t) log(1 - h_t) ]

-- an ordinary weighted Bernoulli (logistic) likelihood over months, maximised by
IRLS. ``w_t`` is 1 in the primary fit; the label-stability arms use it to
down-weight borderline months and, in the escalation, to carry soft labels.

**Duration dependence** is the ``b_s log(d_t)`` term: a discrete-time
log-logistic/Weibull-style aging term, one slope per season, fitted JOINTLY with
the covariate effects (they share one design matrix and one Fisher information,
so their standard errors and their trade-off are the same object). It is the
simplest form that can bend a season's dwell distribution without adding a state:
one extra parameter per season, monotone in the direction its sign says, and it
collapses to a memoryless geometric chain at ``b_s = 0`` -- so "no duration
dependence" is nested inside it and is testable by a t-ratio rather than by
argument.

``dir(s)`` is the growth axis of ``s``: the four covariate loadings are estimated
separately for expanding-origin months (where a flip STARTS a downturn) and
contracting-origin months (where a flip ENDS one), because the exam's causal
story is directional -- tight policy is supposed to bring downturns ON, not to
end them sooner. A single shared loading would force those two into one number
and make T1 untestable by construction.

At-risk months (the completed-transition rule)
----------------------------------------------
A month contributes to the likelihood only if: its season is defined (trailing
inflation exists); it is not in the panel's FIRST season spell (whose start is
unobserved, so ``d_t`` is unknown -- left truncation); and month ``t+1`` exists
and has a defined season. The panel's last month is therefore dropped, which is
the right-censoring half of the same rule.

The covariates, and the ATTENUATION this fit exists to remove
--------------------------------------------------------------
``z = (curve_slope, credit_gap, pi_gap, drawdown_state)`` -- DN-1.1's list, the
same four the pilot's L2 used.

**The pilot's attenuation, cited.** ``src/ah/gen/regimes/semimarkov.py``'s module
docstring states it in its own words: the historical fit used the observed
``GS10 - TB3MS`` slope, while at simulation time the covariate becomes
``psi0 - phi_c0 * c(R_t)`` -- a deterministic function of the regime's cycle
value alone. "The proxy carries the level of the historical slope but compresses
its variance (no simulated inversions), so the inversion channel of the fitted
hazards is attenuated at generation time -- recorded as a v1 limitation in
regime-fit-report.md." On the pinned artifact that proxy takes **three** values
(``psi0 = 0.6938``, ``phi_c0 = 0.0930``, ``cycle_by_regime`` in
``{-1, 0.04, 1}``), spanning 0.60 to 0.79 -- it never once goes below zero, so a
hazard fitted on a covariate that inverts 18% of the time is asked to generate
worlds in which it inverts 0% of the time.

**What this module does instead.** Every covariate is supplied at generation time
by a quantity on the SAME scale and with the SAME dispersion as the one it was
fitted on, and the module measures that rather than asserting it (see
``simulated_vs_historical_covariates`` in the output):

- ``curve_slope`` is the exam's own signal, the panel's ``ust_10y - ust_2y``. At
  generation time it is L1's **policy-deviation state** ``u`` -- the OU deviation
  from the Taylor anchor, which is where the curve's variance actually lives in
  L1 -- put through a fitted linear link plus a fitted AR(1) residual, so the
  simulated curve carries history's mean, history's variance and history's
  persistence, and therefore inverts at roughly history's rate. ``u`` is
  standardised by its OWN stationary moments on both sides, which is what stops
  the L1 posterior's dispersion mismatch leaking into the link.
- ``credit_gap`` and ``pi_gap`` are L1 contract states on both sides (posterior-
  mean smoothed path historically, the simulated path at generation time).
- ``drawdown_state`` is a 36-month trailing drawdown of L1's valuation state
  ``v``, computed by the identical formula on both sides, with its single
  threshold calibrated so that its firing RATE on history equals the firing rate
  of the equity-drawdown dummy the ruleset itself uses. The equity dummy has no
  generation-time counterpart in a no-flesh simulation, so fitting on it would
  have re-created exactly the attenuation this campaign is trying to remove.

Determinism and stream discipline
---------------------------------
Every random draw comes from ``numpy.random.Generator(PCG64(seed))``. The fit
itself draws nothing (IRLS is deterministic). The verification loop opens four
disjoint per-decade streams by fixed byte offsets plus ``.jumped(k)``, and its
premise-attempt loop advances by :data:`SPINE2_ATTEMPT_STRIDE` -- a large prime,
coprime to the platform's ``SEED_STRIDE`` (7919) and distinct from
``ah.gen.spine.ATTEMPT_STRIDE`` (104395301), because the platform has already
paid twice for reusing a stride on a new axis. :func:`assert_distinct_tapes`
proves the separation numerically at import of ``main``, not by assertion in
prose.

Run (offline, no network):

    uv run python scripts/spine_v2_fit.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_grader import season_cells  # noqa: E402
from spine_v2_report import Batch, Decade, judge_all, load_sealed  # noqa: E402

from ah.gen.bootstrap import (  # noqa: E402
    CAMPAIGN_VINTAGE_ID,
    INDPRO_SERIES_ID,
    USREC_SERIES_ID,
    _catalog_access,
    _monthly,
    _read_series,
    _yoy_percent,
    campaign_source,
)
from ah.gen.climate.model import PARAM_NAMES  # noqa: E402
from ah.gen.climate.simulate import simulate_decades  # noqa: E402
from ah.gen.spine import QUADRANTS, panel_yoy  # noqa: E402
from ah.gen.systems import _pinned_layers  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
PARAMS_PATH = SPECS_DIR / "spine-v2-fitted-params.json"

#: Season index -> the growth axis (True = expanding). QUADRANTS is
#: ("recession", "stagflation", "recovery", "expansion") and the encoding is
#: (expanding << 1) | hot, so seasons 2 and 3 are the expanding ones.
EXPANDING = (False, False, True, True)
#: Season index -> the inflation axis (True = hot). Same encoding.
HOT = (False, True, False, True)

#: The four covariates, in DN-1.1's order.
COVARIATES = ("curve_slope", "credit_gap", "pi_gap", "drawdown_state")

#: The trailing window, in months, of the valuation-drawdown covariate. Three
#: years: the same window the exam's own rolling correlation uses, and long
#: enough that a peak is a peak rather than last quarter's high.
V_DRAWDOWN_WINDOW_MONTHS = 36

#: The L1 inflation target the pi_gap covariate is measured against. Read from
#: the pinned L2 artifact's meta rather than restated, so there is one copy.
#: (Assigned in :func:`build_panel`; this is the name, not a second value.)

# --------------------------------------------------------------------------- #
# seeds and streams -- one literal per consumer, no seed derived from another
# --------------------------------------------------------------------------- #

#: The verification loop's base seed.
VERIFY_SEED = 20260821
#: The premise-attempt stride for the verification loop. Prime; coprime to the
#: platform's SEED_STRIDE (7919) and distinct from ah.gen.spine.ATTEMPT_STRIDE
#: (104395301). See the module docstring for why a new axis gets a new stride.
SPINE2_ATTEMPT_STRIDE = 32452843
#: Per-decade byte offsets, one disjoint stream per consumer. Chosen distinct
#: from ah.gen.spine.LAYER_OFFSETS' five values so a stream here can never be
#: bit-identical to one there at the same base seed.
LAYER_OFFSETS = {
    "seasons": 601387,
    "slope": 715393,
    "inflnoise": 829417,
    "labels": 1063441,
}
#: L1's own offset. Zero, exactly as ``ah.gen.spine.LAYER_OFFSETS["climate"]``
#: is zero, because this is the SAME call into ``simulate_decades`` and that
#: function owns its own per-decade stream discipline. It is deliberately kept
#: out of :data:`LAYER_OFFSETS` and out of the platform-ladder disjointness
#: check: at attempt 0 the climate stream IS the platform ladder's first rung,
#: which is not a collision but the intended reuse of one generator's tape.
CLIMATE_OFFSET = 0
#: The platform's ensemble stride, restated for the distinctness assertion only.
PLATFORM_SEED_STRIDE = 7919

#: The verification batch size, owner-ruled in the seal (n_seeds = 50).
#: Read from the seal at run time; this is the fallback used only if absent.
DEFAULT_N_DECADES = 50
DECADE_MONTHS = 120
#: The attempt budget per accepted decade, matching ah.gen.spine.
MAX_ATTEMPTS_PER_DECADE = 200

#: The label-stability perturbation, in percentage points of each dial's own
#: units -- the exam's section 11 size (0.50 pp), not a new choice.
STABILITY_PERTURBATION_PP = 0.5
#: The nine arms: (name, inflation-line delta, growth-line delta). Sign
#: convention as in scripts/spine_v2_anchors.py: a POSITIVE inflation delta
#: raises the hot line; a POSITIVE growth delta raises the contraction line.
STABILITY_ARMS: tuple[tuple[str, float, float], ...] = (
    ("baseline", 0.0, 0.0),
    ("inflation_line_minus_50bp", -STABILITY_PERTURBATION_PP, 0.0),
    ("inflation_line_plus_50bp", +STABILITY_PERTURBATION_PP, 0.0),
    ("growth_line_minus_50bp", 0.0, -STABILITY_PERTURBATION_PP),
    ("growth_line_plus_50bp", 0.0, +STABILITY_PERTURBATION_PP),
    ("both_minus_50bp", -STABILITY_PERTURBATION_PP, -STABILITY_PERTURBATION_PP),
    ("inflation_minus_growth_plus", -STABILITY_PERTURBATION_PP, +STABILITY_PERTURBATION_PP),
    ("inflation_plus_growth_minus", +STABILITY_PERTURBATION_PP, -STABILITY_PERTURBATION_PP),
    ("both_plus_50bp", +STABILITY_PERTURBATION_PP, +STABILITY_PERTURBATION_PP),
)
#: A month is "borderline" if either dial sits within this many percentage
#: points of its own line. The same 0.50 pp as the perturbation, so the
#: down-weighting arm and the perturbation arms are asking the same question
#: from two directions.
BORDERLINE_BAND_PP = 0.5


class FitError(RuntimeError):
    """A malformed input or an unsatisfiable fit request."""


# --------------------------------------------------------------------------- #
# stream hygiene
# --------------------------------------------------------------------------- #


def assert_distinct_tapes(base_seed: int = VERIFY_SEED, n: int = 64) -> dict[str, Any]:
    """Prove the new axis's streams collide with nothing, numerically.

    Three claims, each checked by drawing the first 8 float64s of every stream
    and comparing whole tapes:

    1. the four per-decade offsets give disjoint tapes for every decade index;
    2. no attempt index in the budget lands a season stream on the platform's
       own ``base_seed + 7919*k`` ladder (the collision that cost spine-02 a
       fix, module docstring of ``ah.gen.spine``);
    3. ``SPINE2_ATTEMPT_STRIDE`` shares no factor with 7919 and is not
       ``ah.gen.spine.ATTEMPT_STRIDE``.
    """
    from math import gcd

    from ah.gen.spine import ATTEMPT_STRIDE as SPINE_ATTEMPT_STRIDE

    if gcd(SPINE2_ATTEMPT_STRIDE, PLATFORM_SEED_STRIDE) != 1:
        raise FitError("SPINE2_ATTEMPT_STRIDE must be coprime to the platform SEED_STRIDE")
    if SPINE2_ATTEMPT_STRIDE == SPINE_ATTEMPT_STRIDE:
        raise FitError("SPINE2_ATTEMPT_STRIDE must differ from ah.gen.spine.ATTEMPT_STRIDE")

    def tape(seed: int, jump: int) -> tuple[float, ...]:
        rng = np.random.Generator(np.random.PCG64(int(seed)).jumped(int(jump)))
        return tuple(float(x) for x in rng.random(8))

    tapes: dict[tuple[str, int], tuple[float, ...]] = {}
    for name, offset in LAYER_OFFSETS.items():
        for k in range(n):
            tapes[(name, k)] = tape(base_seed + offset, k)
    if len(set(tapes.values())) != len(tapes):
        raise FitError("two per-decade streams share a tape")

    # the platform ladder, as opened by simulate_decades / simulate_regimes
    platform = {
        tuple(
            float(x)
            for x in np.random.Generator(
                np.random.PCG64(base_seed + PLATFORM_SEED_STRIDE * k)
            ).random(8)
        )
        for k in range(n)
    }
    attempts = {
        tuple(
            float(x)
            for x in np.random.Generator(
                np.random.PCG64(base_seed + LAYER_OFFSETS["seasons"] + SPINE2_ATTEMPT_STRIDE * a)
            ).random(8)
        )
        for a in range(MAX_ATTEMPTS_PER_DECADE)
    }
    if platform & attempts:
        raise FitError("an attempt-strided season stream collides with the platform ladder")
    return {
        "n_streams_checked": len(tapes) + len(platform) + len(attempts),
        "per_decade_streams_distinct": True,
        "attempt_ladder_disjoint_from_platform_ladder": True,
        "spine2_attempt_stride": SPINE2_ATTEMPT_STRIDE,
        "platform_seed_stride": PLATFORM_SEED_STRIDE,
        "spine_attempt_stride": SPINE_ATTEMPT_STRIDE,
    }


# --------------------------------------------------------------------------- #
# the historical panel and its covariates
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Panel:
    """Everything the fit reads off history, on one monthly grid."""

    dates: pd.DatetimeIndex
    labels: np.ndarray  # regime_ruleset_v1 labels, (T,)
    yoy: np.ndarray  # trailing 12-month CPI inflation, pp, NaN in the warm-up
    growth_yoy: np.ndarray  # trailing INDPRO growth, pp (the growth dial's input)
    era_threshold_pp: float
    z_raw: np.ndarray  # (T, 4) unstandardised covariates
    z_mean: np.ndarray  # (4,)
    z_sd: np.ndarray  # (4,)
    slope: np.ndarray  # (T,) ust_10y - ust_2y
    u_hat: np.ndarray  # (T,) L1 policy deviation, standardised
    link: dict[str, float]  # the fitted slope <- u link
    v_threshold: float  # the calibrated valuation-drawdown threshold
    diagnostics: dict[str, Any]

    @property
    def z(self) -> np.ndarray:
        return (self.z_raw - self.z_mean) / self.z_sd

    def z_lagged(self, lag: int) -> np.ndarray:
        """The standardised covariates with the CURVE column lagged ``lag`` months.

        Only the curve is lagged: it is the only one the exam gives a lead time
        for. Credit, inflation and the drawdown state enter contemporaneously,
        as they do in DN-1.1's own z(s).
        """
        z = self.z
        z[:, 0] = lag_column(z[:, 0], int(lag))
        return z


def trailing_drawdown(x: np.ndarray, window: int) -> np.ndarray:
    """``x_t`` minus its trailing ``window``-month running maximum (<= 0).

    The window is inclusive of ``t`` and truncated at the start of the array, so
    the same code runs on a 813-month panel and on a 120-month decade and neither
    borrows information from outside itself.
    """
    arr = np.asarray(x, dtype=np.float64)
    out = np.empty(arr.size, dtype=np.float64)
    for t in range(arr.size):
        lo = max(0, t - window + 1)
        out[t] = arr[t] - float(np.max(arr[lo : t + 1]))
    return out


def build_panel() -> Panel:
    """Assemble the historical panel, the four covariates, and the two links."""
    source = campaign_source()
    dates = pd.DatetimeIndex(source.dates)
    values = np.asarray(source.values, dtype=np.float64)
    names = list(source.factor_names)
    labels = np.asarray(source.labels)
    yoy = panel_yoy(source)

    climate, regimes = _pinned_layers()
    pi_target = float(regimes.meta["pi_target"])
    locs = climate.dates.get_indexer(dates)
    if (locs < 0).any():
        raise FitError("the panel leaves the climate artifact's monthly grid")
    smoothed = climate.states.mean(axis=0)  # (T_climate, 5) posterior mean
    pi_star = smoothed[locs, 0]
    r_star = smoothed[locs, 1]
    valuation = smoothed[locs, 3]
    credit_gap = smoothed[locs, 4]
    theta_bar = {name: float(np.mean(climate.params[name])) for name in PARAM_NAMES}

    _catalog, access = _catalog_access(_REPO_ROOT / "data", CAMPAIGN_VINTAGE_ID)
    usrec_frame = _read_series(access, USREC_SERIES_ID)
    indpro_frame = _read_series(access, INDPRO_SERIES_ID)
    if usrec_frame is None or indpro_frame is None:
        raise FitError("the fit needs fred.USREC and fred.INDPRO from the campaign vintage")
    usrec = _monthly(usrec_frame).reindex(dates).to_numpy(dtype=np.float64)
    growth_yoy = _yoy_percent(_monthly(indpro_frame)).reindex(dates).to_numpy(dtype=np.float64)
    cycle_hist = 1.0 - 2.0 * usrec

    # ---- the curve, and the L1 state its variance actually lives in ---------
    slope = values[:, names.index("ust_10y")] - values[:, names.index("ust_2y")]
    policy = values[:, names.index("policy_rate")]
    # The Taylor anchor's residual IS the policy-deviation state u (model.py's
    # m_policy channel, up to its observation noise): u = i_obs - anchor.
    pi_obs = np.where(np.isnan(yoy), pi_star, yoy)  # the warm-up months use pi*
    anchor = (
        r_star
        + pi_star
        + theta_bar["phi_pi"] * (pi_obs - pi_star)
        + theta_bar["phi_c"] * cycle_hist
    )
    u_hist = policy - anchor
    u_mean, u_sd = float(np.mean(u_hist)), float(np.std(u_hist))
    u_hat = (u_hist - u_mean) / u_sd  # standardised: mean 0, sd 1 on both sides

    # slope = a + b * u_hat + e, e AR(1). Ordinary least squares; b carries the
    # sign of the economics (u up = policy above its own anchor = curve flatter),
    # and the fit is reported with its R^2 rather than asserted.
    design = np.column_stack([np.ones(u_hat.size), u_hat])
    coef, *_ = np.linalg.lstsq(design, slope, rcond=None)
    resid = slope - design @ coef
    rho = float(np.corrcoef(resid[1:], resid[:-1])[0, 1])
    eta_sd = float(np.std(resid[1:] - rho * resid[:-1]))
    link = {
        "intercept": float(coef[0]),
        "u_hat_loading": float(coef[1]),
        "residual_ar1_rho": rho,
        "residual_innovation_sd": eta_sd,
        "residual_sd": float(np.std(resid)),
        "r_squared": float(1.0 - np.var(resid) / np.var(slope)),
        "u_mean_historical": u_mean,
        "u_sd_historical": u_sd,
    }

    # ---- the valuation-drawdown covariate, calibrated to the ruleset's rate --
    equity = values[:, names.index("equity_mkt")]
    index = np.cumprod(1.0 + equity)
    equity_dd = index / np.maximum.accumulate(index) - 1.0
    from ah.data.derive import regime_thresholds

    dd_crisis = float(dict(regime_thresholds())["drawdown_crisis"])
    equity_dummy = (equity_dd <= dd_crisis).astype(np.float64)
    v_dd = trailing_drawdown(valuation, V_DRAWDOWN_WINDOW_MONTHS)
    target_rate = float(equity_dummy.mean())
    # the threshold whose firing rate matches, to the resolution of the sample
    v_threshold = float(np.quantile(v_dd, target_rate))
    v_dummy = (v_dd <= v_threshold).astype(np.float64)

    z_raw = np.column_stack([slope, credit_gap, pi_star - pi_target, v_dummy])
    z_mean = z_raw.mean(axis=0)
    z_sd = z_raw.std(axis=0)
    z_mean[3] = 0.0  # a standardised 0/1 dummy has no cleaner meaning
    z_sd[3] = 1.0
    z_sd[z_sd == 0.0] = 1.0

    era_threshold_pp = float(np.nanmedian(yoy) + 0.5)  # ah.gen.spine.fit_hazard's own rule

    diagnostics = {
        "vintage_id": CAMPAIGN_VINTAGE_ID,
        "panel_months": int(dates.size),
        "panel_span": [str(dates[0])[:10], str(dates[-1])[:10]],
        "climate_artifact_sha256": str(climate.meta["content_sha256"]),
        "regimes_artifact_sha256": str(regimes.meta["content_sha256"]),
        "pi_target": pi_target,
        "era_threshold_pp": era_threshold_pp,
        "theta_bar": {k: theta_bar[k] for k in ("psi", "phi_pi", "phi_c", "s_m_pi")},
        "curve": {
            "slope_mean_pp": float(np.mean(slope)),
            "slope_sd_pp": float(np.std(slope)),
            "inverted_share": float(np.mean(slope < 0.0)),
            "slope_ar1": float(np.corrcoef(slope[1:], slope[:-1])[0, 1]),
        },
        "valuation_drawdown_calibration": {
            "equity_drawdown_threshold": dd_crisis,
            "equity_dummy_rate": target_rate,
            "v_drawdown_threshold": v_threshold,
            "v_dummy_rate": float(v_dummy.mean()),
            "agreement_with_equity_dummy": float(np.mean(v_dummy == equity_dummy)),
        },
        "pi_star_tracks_observed_cpi": {
            "correlation": float(np.corrcoef(pi_star[~np.isnan(yoy)], yoy[~np.isnan(yoy)])[0, 1]),
            "residual_sd_pp": float(np.std(yoy[~np.isnan(yoy)] - pi_star[~np.isnan(yoy)])),
        },
    }
    return Panel(
        dates=dates,
        labels=labels,
        yoy=yoy,
        growth_yoy=growth_yoy,
        era_threshold_pp=era_threshold_pp,
        z_raw=z_raw,
        z_mean=z_mean,
        z_sd=z_sd,
        slope=slope,
        u_hat=u_hat,
        link=link,
        v_threshold=v_threshold,
        diagnostics=diagnostics,
    )


# --------------------------------------------------------------------------- #
# the design matrix and the likelihood
# --------------------------------------------------------------------------- #

#: Parameter block layout: 4 season intercepts, 4 season log-dwell slopes,
#: 4 covariate loadings for expanding-origin months, 4 for contracting-origin.
N_PARAMS = 16
PARAM_LABELS: tuple[str, ...] = (
    *(f"intercept[{s}]" for s in QUADRANTS),
    *(f"log_dwell[{s}]" for s in QUADRANTS),
    *(f"cov_expanding[{c}]" for c in COVARIATES),
    *(f"cov_contracting[{c}]" for c in COVARIATES),
)


def season_dwell(cells: np.ndarray) -> np.ndarray:
    """Months elapsed in the current season spell, 1-based; ``0`` where undefined.

    A run of undefined months (``-1``) resets the counter, so a spell can never
    be credited with months whose season nobody knows.
    """
    arr = np.asarray(cells, dtype=np.int64)
    out = np.zeros(arr.size, dtype=np.int64)
    run = 0
    previous = -2
    for t in range(arr.size):
        if arr[t] < 0:
            run = 0
            previous = -2
            continue
        run = run + 1 if arr[t] == previous else 1
        previous = arr[t]
        out[t] = run
    return out


#: The lags, in months, the curve covariate is offered at. The exam's own
#: causal story is a LEAD relationship -- "when monetary policy is tight, a
#: downturn is more likely to begin over the FOLLOWING YEAR" -- so a
#: contemporaneous covariate cannot represent it, and the lag is selected by
#: maximum likelihood over this grid at a constant parameter count (so the
#: comparison is on equal degrees of freedom and is a fit criterion, never a
#: bar criterion). The whole profile is published beside the selection.
CURVE_LAG_GRID: tuple[int, ...] = (0, 3, 6, 9, 12, 15, 18, 24)


def lag_column(x: np.ndarray, lag: int) -> np.ndarray:
    """``x`` shifted ``lag`` months later; the head is filled with ``NaN``.

    ``NaN`` rather than an invented value: the months with no lagged reading are
    dropped from the at-risk set instead of being fitted against a fabricated
    covariate.
    """
    out = np.full(x.shape[0], np.nan, dtype=np.float64)
    if lag == 0:
        return np.asarray(x, dtype=np.float64).copy()
    out[lag:] = np.asarray(x, dtype=np.float64)[:-lag]
    return out


def build_design(
    cells: np.ndarray, dwell: np.ndarray, z: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(X, y, at_risk)`` for the monthly hazard.

    ``at_risk`` implements the completed-transition rule: a defined season now, a
    defined season next month, every covariate readable, and not inside the
    panel's first (left-truncated) season spell.
    """
    arr = np.asarray(cells, dtype=np.int64)
    n = arr.size
    defined = arr >= 0
    at_risk = np.zeros(n, dtype=bool)
    at_risk[:-1] = defined[:-1] & defined[1:]
    at_risk &= ~np.isnan(z).any(axis=1)
    # drop the first spell outright -- its start is unobserved
    first_defined = int(np.flatnonzero(defined)[0])
    first_spell_end = first_defined
    while (
        first_spell_end + 1 < n
        and defined[first_spell_end + 1]
        and arr[first_spell_end + 1] == arr[first_defined]
    ):
        first_spell_end += 1
    at_risk[: first_spell_end + 1] = False

    expanding_now = np.array([EXPANDING[c] if c >= 0 else False for c in arr])
    y = np.zeros(n, dtype=np.float64)
    y[:-1] = (expanding_now[:-1] != expanding_now[1:]).astype(np.float64)

    x = np.zeros((n, N_PARAMS), dtype=np.float64)
    z_clean = np.nan_to_num(z, nan=0.0)  # the NaN rows are already out of at_risk
    for s in range(4):
        mask = arr == s
        x[mask, s] = 1.0
        x[mask, 4 + s] = np.log(np.maximum(dwell[mask], 1))
    block = np.where(expanding_now, 8, 12)
    for j in range(4):
        rows = np.arange(n)
        x[rows, block + j] = z_clean[:, j]
    return x, y, at_risk


def irls_logit(
    x: np.ndarray, y: np.ndarray, w: np.ndarray, *, max_iter: int = 200, tol: float = 1e-11
) -> dict[str, Any]:
    """Weighted logistic ML by iteratively reweighted least squares.

    Deterministic (no random start, no random tie-break) and returns the inverse
    Fisher information, so every coefficient ships with the standard error the
    label-stability obligation compares against.
    """
    beta = np.zeros(x.shape[1], dtype=np.float64)
    loglik = -np.inf
    for _ in range(max_iter):
        eta = x @ beta
        p = 1.0 / (1.0 + np.exp(-eta))
        p = np.clip(p, 1e-12, 1.0 - 1e-12)
        weight = w * p * (1.0 - p)
        gradient = x.T @ (w * (y - p))
        hessian = x.T @ (x * weight[:, None])
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError as exc:  # pragma: no cover - singular design
            raise FitError(f"the hazard design is singular: {exc}") from exc
        beta = beta + step
        new_loglik = float(np.sum(w * (y * np.log(p) + (1.0 - y) * np.log(1.0 - p))))
        if abs(new_loglik - loglik) < tol:
            loglik = new_loglik
            break
        loglik = new_loglik
    eta = x @ beta
    p = np.clip(1.0 / (1.0 + np.exp(-eta)), 1e-12, 1.0 - 1e-12)
    hessian = x.T @ (x * (w * p * (1.0 - p))[:, None])
    covariance = np.linalg.inv(hessian)
    return {
        "beta": beta,
        "se": np.sqrt(np.diag(covariance)),
        "loglik": float(np.sum(w * (y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))),
        "n_obs": float(w.sum()),
        "n_events": float((w * y).sum()),
    }


def fit_arm(cells: np.ndarray, z: np.ndarray, weights: np.ndarray | None = None) -> dict[str, Any]:
    """One fitted hazard: design, IRLS, and the named coefficients."""
    dwell = season_dwell(cells)
    x, y, at_risk = build_design(cells, dwell, z)
    w = np.ones(cells.size, dtype=np.float64) if weights is None else np.asarray(weights, float)
    w = np.where(at_risk, w, 0.0)
    result = irls_logit(x, y, w)
    result["coefficients"] = {
        name: float(v) for name, v in zip(PARAM_LABELS, result["beta"], strict=True)
    }
    result["standard_errors"] = {
        name: float(v) for name, v in zip(PARAM_LABELS, result["se"], strict=True)
    }
    return result


def select_curve_lag(panel: Panel, cells: np.ndarray) -> dict[str, Any]:
    """Choose the curve's lead time by maximum likelihood over :data:`CURVE_LAG_GRID`.

    Every arm has the SAME 16 parameters and the same at-risk rule (a month is
    dropped when its lagged reading does not exist, on every arm alike, so the
    likelihoods are comparable), which makes this a plain likelihood comparison
    rather than a model-complexity trade. The full profile is reported.
    """
    profile: list[dict[str, Any]] = []
    common = max(CURVE_LAG_GRID)
    for lag in CURVE_LAG_GRID:
        z = panel.z_lagged(lag)
        z[:common, 0] = np.nan  # same at-risk months on every arm
        fit = fit_arm(cells, z)
        profile.append(
            {
                "lag_months": int(lag),
                "loglik": float(fit["loglik"]),
                "transmission": float(fit["coefficients"][TRANSMISSION_KEY]),
                "standard_error": float(fit["standard_errors"][TRANSMISSION_KEY]),
                "n_obs": float(fit["n_obs"]),
                "n_events": float(fit["n_events"]),
            }
        )
    best = max(profile, key=lambda row: row["loglik"])
    return {
        "grid_months": list(CURVE_LAG_GRID),
        "selected_lag_months": int(best["lag_months"]),
        "criterion": "maximum likelihood at constant parameter count and a common at-risk set",
        "profile": profile,
    }


#: The single number the label-stability obligation tracks: how strongly a
#: flattening curve raises the hazard of an expanding season turning
#: contracting. Negative = tighter policy brings downturns on, which is the
#: exam's causal story.
TRANSMISSION_KEY = "cov_expanding[curve_slope]"


# --------------------------------------------------------------------------- #
# label-stability arms
# --------------------------------------------------------------------------- #


def relabel(panel: Panel, inflation_delta_pp: float, growth_delta_pp: float) -> np.ndarray:
    """Season cells under a perturbed pair of classifier dials.

    The inflation dial moves the era line directly (the ``grader_v2`` "hot"
    test). The growth dial has no threshold of its own at this layer -- it is
    ``regime_ruleset_v1``'s ``growth_weak``, one layer down -- so a perturbation
    is applied by re-running the platform's own labeller with the moved
    threshold, exactly as ``scripts/spine_v2_anchors.section_i`` does, rather
    than by a second implementation written here.
    """
    labels = panel.labels if growth_delta_pp == 0.0 else _relabel_growth(panel, growth_delta_pp)
    return season_cells(labels, panel.yoy, panel.era_threshold_pp + inflation_delta_pp)


def _relabel_growth(panel: Panel, growth_delta_pp: float) -> np.ndarray:
    """``regime_ruleset_v1`` labels with ``growth_weak`` moved by ``delta``."""
    from ah.data.derive import label_regime, regime_thresholds
    from ah.gen.bootstrap import _drawdown_fraction, _monthly, _read_series

    _catalog, access = _catalog_access(_REPO_ROOT / "data", CAMPAIGN_VINTAGE_ID)
    thresholds = dict(regime_thresholds())
    thresholds["growth_weak"] = float(thresholds["growth_weak"]) + growth_delta_pp
    source = campaign_source()
    values = np.asarray(source.values, dtype=np.float64)
    names = list(source.factor_names)
    usrec_frame = _read_series(access, USREC_SERIES_ID)
    assert usrec_frame is not None
    usrec = _monthly(usrec_frame).reindex(panel.dates).to_numpy(dtype=np.float64)
    equity = pd.Series(values[:, names.index("equity_mkt")], index=panel.dates)
    drawdown = _drawdown_fraction(equity).reindex(panel.dates).to_numpy(dtype=np.float64)
    out = []
    for i in range(panel.dates.size):
        out.append(
            label_regime(
                usrec=float(usrec[i]),
                cpi_yoy=float(panel.yoy[i]) if not np.isnan(panel.yoy[i]) else 0.0,
                growth_yoy=float(panel.growth_yoy[i]),
                drawdown=float(drawdown[i]),
                hy_oas=float("nan"),
                thr=thresholds,
            )
        )
    return np.asarray(out)


def borderline_weights(panel: Panel) -> np.ndarray:
    """Down-weight months whose classification is close to either dial's line.

    ``w = min(1, |yoy - era| / band) * min(1, |growth - growth_weak| / band)``
    with ``band`` = :data:`BORDERLINE_BAND_PP`. A month sitting exactly on a line
    gets weight 0; a month half a point clear of both gets weight 1. This is the
    second half of the sealed obligation's stability check -- the perturbation
    arms ask "does the answer move when the line moves", and this asks "does the
    answer rest on the months the line is closest to".
    """
    from ah.data.derive import regime_thresholds

    growth_weak = float(dict(regime_thresholds())["growth_weak"])
    d_inf = np.abs(panel.yoy - panel.era_threshold_pp)
    d_grw = np.abs(panel.growth_yoy - growth_weak)
    w_inf = np.clip(np.nan_to_num(d_inf, nan=0.0) / BORDERLINE_BAND_PP, 0.0, 1.0)
    w_grw = np.clip(np.nan_to_num(d_grw, nan=0.0) / BORDERLINE_BAND_PP, 0.0, 1.0)
    return w_inf * w_grw


def soft_label_weights(panel: Panel) -> np.ndarray:
    """The ESCALATION's weights: each month weighted by classification confidence.

    A logistic confidence in each dial, ``2*|sigma(d/band) - 0.5|``, multiplied.
    Unlike :func:`borderline_weights` this never reaches exactly zero, so no
    month is dropped -- which is what "soft membership" means in the sealed
    escalation path (exam section 12's declared limitation: every season is a
    HARD label, and the agreed response to threshold instability is soft
    membership).
    """
    from ah.data.derive import regime_thresholds

    growth_weak = float(dict(regime_thresholds())["growth_weak"])
    d_inf = np.nan_to_num(panel.yoy - panel.era_threshold_pp, nan=0.0)
    d_grw = np.nan_to_num(panel.growth_yoy - growth_weak, nan=0.0)
    conf_inf = 2.0 * np.abs(1.0 / (1.0 + np.exp(-d_inf / BORDERLINE_BAND_PP)) - 0.5)
    conf_grw = 2.0 * np.abs(1.0 / (1.0 + np.exp(-d_grw / BORDERLINE_BAND_PP)) - 0.5)
    return conf_inf * conf_grw


def label_stability(panel: Panel, primary: dict[str, Any], lag: int) -> dict[str, Any]:
    """The sealed section's obligation: refit under every arm, report movement.

    The verdict rule is the one the task states: if the fitted transmission
    strength moves by more than ITS OWN standard error across arms, escalate to
    soft labels and report both.
    """
    base = float(primary["coefficients"][TRANSMISSION_KEY])
    base_se = float(primary["standard_errors"][TRANSMISSION_KEY])
    arms: dict[str, Any] = {}
    for name, d_inf, d_grw in STABILITY_ARMS:
        cells = relabel(panel, d_inf, d_grw)
        fit = fit_arm(cells, panel.z_lagged(lag))
        arms[name] = _arm_row(fit, base, base_se, name)
    for name, weights in (
        ("borderline_downweighted", borderline_weights(panel)),
        ("soft_labels_escalation", soft_label_weights(panel)),
    ):
        fit = fit_arm(relabel(panel, 0.0, 0.0), panel.z_lagged(lag), weights=weights)
        arms[name] = _arm_row(fit, base, base_se, name)

    threshold_arms = [arms[name] for name, _, _ in STABILITY_ARMS if name != "baseline"]
    worst = max(threshold_arms, key=lambda r: abs(r["moves_by_se"]))
    downweighted = arms["borderline_downweighted"]
    escalate = bool(abs(worst["moves_by_se"]) > 1.0 or abs(downweighted["moves_by_se"]) > 1.0)
    return {
        "statistic": TRANSMISSION_KEY,
        "baseline_value": base,
        "baseline_standard_error": base_se,
        "arms": arms,
        "worst_threshold_arm": worst["arm"],
        "worst_threshold_arm_moves_by_se": worst["moves_by_se"],
        "borderline_downweighted_moves_by_se": downweighted["moves_by_se"],
        "escalated": escalate,
        "escalation_rule": (
            "the sealed escalation path: if the fitted transmission strength moves by "
            "more than its own standard error across arms, refit with soft labels "
            "(each month weighted by classification confidence) and report both"
        ),
        "verdict": (
            "UNSTABLE -- escalated to soft labels, both reported"
            if escalate
            else "STABLE -- every arm moves the transmission coefficient by less "
            "than one of its own standard errors"
        ),
    }


def _arm_row(fit: dict[str, Any], base: float, base_se: float, name: str) -> dict[str, Any]:
    value = float(fit["coefficients"][TRANSMISSION_KEY])
    return {
        "arm": name,
        "transmission": value,
        "standard_error": float(fit["standard_errors"][TRANSMISSION_KEY]),
        "moves_by_se": (value - base) / base_se if base_se else float("nan"),
        "n_events": float(fit["n_events"]),
        "n_obs": float(fit["n_obs"]),
        "loglik": float(fit["loglik"]),
    }


# --------------------------------------------------------------------------- #
# the simulator: L1 + the fitted season chain, standalone (no flesh, no sampler)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SimulatedDecade:
    """One generated decade's spine, and the judge-facing series it implies."""

    season: np.ndarray  # (months,) season index, always defined internally
    labels: np.ndarray  # (months,) regime_ruleset_v1 labels, as the judge sees them
    expanding: np.ndarray  # (months,) bool
    yoy: np.ndarray  # (months,) simulated trailing inflation, pp
    slope: np.ndarray  # (months,) simulated 10y-2y spread, pp
    z: np.ndarray  # (months, 4) standardised covariates
    states: np.ndarray  # (months, 5) L1 contract states
    attempts: int


#: The ruleset's own stagflation dial: ``STAG`` fires at or above 4.0 pp
#: trailing CPI (``ah.data.derive.regime_thresholds``'s ``cpi_high``), which is
#: ABOVE the era line (3.3513 pp) the season classifier splits hot from cool on.
#: The two lines are different objects and this module keeps them different.
STAG_CPI_LINE_PP = 4.0


def emit_labels(
    season: np.ndarray, yoy: np.ndarray, stag_spell_rate: float, rng: np.random.Generator
) -> np.ndarray:
    """``regime_ruleset_v1`` labels for a simulated season path.

    The judge re-derives the season from ``(label, yoy)`` through the sealed
    grader, so this mapping must invert ``grader_v2``'s contracting set exactly:
    ``REC`` and ``STAG`` are contracting, ``EXP`` is not.

    **Why it is not simply one label per season.** T1's downturn union is
    ``REC``-or-``CRI`` and is deliberately NOT re-anchored under the mapping fix
    (the seal's own note on ``downturn_labels``), so whether a contracting month
    is labelled ``REC`` or ``STAG`` decides whether it is a downturn onset for
    T1 -- and on the panel the split is neither all one nor all the other: of the
    95 contracting months with trailing CPI at or above 4.0 pp, **31 are ``STAG``
    and 64 are ``REC``/``CRI``**. Mapping the whole stagflation season to
    ``STAG`` would put 111 of history's contracting months outside T1's numerator
    when history puts only 31 there; mapping it all to ``REC`` would make every
    generated contraction a T1 downturn when 14% of history's are not. So the
    split is reproduced at its measured rate, drawn ONCE PER CONTRACTING SPELL
    rather than per month, because ``STAG`` months clump in history and a
    per-month coin would chop ``REC`` runs into spurious extra onsets -- which
    would manufacture T1 structure out of labelling noise.

    ``CRI`` is never emitted: a no-flesh spine has no equity drawdown to fire the
    ruleset's crisis disjunct on, so T1's crisis-only DISCLOSURE is empty in this
    loop and is reported as empty rather than faked.
    """
    arr = np.asarray(season, dtype=np.int64)
    out = np.array(["EXP"] * arr.size, dtype=object)
    contracting = np.array([not EXPANDING[int(s)] for s in arr])
    t = 0
    while t < arr.size:
        if not contracting[t]:
            t += 1
            continue
        end = t
        while end + 1 < arr.size and contracting[end + 1]:
            end += 1
        window = slice(t, end + 1)
        hot_enough = yoy[window] >= STAG_CPI_LINE_PP
        is_stag_spell = bool(hot_enough.any()) and bool(rng.random() < stag_spell_rate)
        out[window] = np.where(hot_enough & is_stag_spell, "STAG", "REC")
        t = end + 1
    return out


def measure_stag_spell_rate(panel: Panel, cells: np.ndarray) -> dict[str, float]:
    """History's own ``STAG``-versus-``REC`` split, at the spell level.

    Among the panel's contracting spells that contain at least one month at or
    above the ruleset's 4.0 pp CPI line, the share that actually carry a ``STAG``
    label. That is the number :func:`emit_labels` draws against.
    """
    contracting = np.array([(c >= 0) and (not EXPANDING[int(c)]) for c in cells])
    labels = np.asarray(panel.labels)
    eligible = 0
    stagged = 0
    months_eligible = 0
    months_stag = 0
    t = 0
    while t < contracting.size:
        if not contracting[t]:
            t += 1
            continue
        end = t
        while end + 1 < contracting.size and contracting[end + 1]:
            end += 1
        window = slice(t, end + 1)
        hot_enough = panel.yoy[window] >= STAG_CPI_LINE_PP
        if bool(np.nan_to_num(hot_enough, nan=0.0).any()):
            eligible += 1
            if (labels[window] == "STAG").any():
                stagged += 1
        months_eligible += int(np.nan_to_num(hot_enough, nan=0.0).sum())
        months_stag += int((labels[window] == "STAG").sum())
        t = end + 1
    return {
        "spells_eligible": float(eligible),
        "spells_with_stag": float(stagged),
        "spell_rate": float(stagged / eligible) if eligible else 0.0,
        "months_at_or_above_cpi_line": float(months_eligible),
        "months_labelled_stag": float(months_stag),
        "month_rate": float(months_stag / months_eligible) if months_eligible else 0.0,
    }


def cycle_by_season(panel: Panel, cells: np.ndarray) -> np.ndarray:
    """``c_t`` per season: the panel mean of ``1 - 2*USREC`` inside each season.

    The identical construction ``ah.gen.regimes.fit.build_fit_data`` uses per
    regime, applied to the four seasons instead -- so the L1 parameters
    ``phi_c``/``delta_L`` keep the meaning they were fitted with when this
    layer's ``c_t`` replaces the USREC proxy they were fitted against.
    """
    _catalog, access = _catalog_access(_REPO_ROOT / "data", CAMPAIGN_VINTAGE_ID)
    usrec_frame = _read_series(access, USREC_SERIES_ID)
    if usrec_frame is None:
        raise FitError("fred.USREC is absent from the campaign vintage")
    usrec = _monthly(usrec_frame).reindex(panel.dates).to_numpy(dtype=np.float64)
    proxy = 1.0 - 2.0 * usrec
    out = np.empty(4, dtype=np.float64)
    for s in range(4):
        mask = cells == s
        out[s] = float(np.clip(proxy[mask].mean(), -1.0, 1.0)) if mask.any() else 0.0
    return out


@dataclass(frozen=True)
class FittedEngine:
    """Everything the simulator needs, and nothing it does not."""

    beta: np.ndarray
    z_mean: np.ndarray
    z_sd: np.ndarray
    era_threshold_pp: float
    pi_target: float
    link: dict[str, float]
    v_threshold: float
    season_cycle: np.ndarray
    infl_residual_rho: float
    infl_residual_innovation_sd: float
    initial_expanding_rate: float
    curve_lag_months: int
    stag_spell_rate: float
    stag_cpi_line_pp: float


def hazard_probability(beta: np.ndarray, season: int, dwell: int, z_row: np.ndarray) -> float:
    """``h_t`` for one month -- the fitted logit, evaluated."""
    logit = float(beta[season]) + float(beta[4 + season]) * float(np.log(max(dwell, 1)))
    block = 8 if EXPANDING[season] else 12
    logit += float(z_row @ beta[block : block + 4])
    return float(1.0 / (1.0 + np.exp(-logit)))


def ar1_path(rng: np.random.Generator, rho: float, innovation_sd: float, n: int) -> np.ndarray:
    """A stationary AR(1) path: the first draw comes from the stationary law."""
    stationary_sd = innovation_sd / np.sqrt(max(1.0 - rho * rho, 1e-12))
    out = np.empty(n, dtype=np.float64)
    out[0] = rng.normal(0.0, stationary_sd)
    for t in range(1, n):
        out[t] = rho * out[t - 1] + rng.normal(0.0, innovation_sd)
    return out


def ou_standardised(
    rng: np.random.Generator, half_life_years: float, sigma: float, n: int
) -> np.ndarray:
    """L1's policy-deviation OU, standardised by its OWN stationary moments.

    ``du = -kappa u dt + sigma dW`` with ``kappa = ln2 / half_life``; the
    stationary sd is ``sigma / sqrt(2 kappa)``. Dividing the simulated path by
    that sd -- rather than by the historical path's sample sd -- is what keeps
    the link's loading meaning the same thing on both sides even though the L1
    posterior's implied dispersion and its smoothed path's realised dispersion
    disagree (they do, and by a factor of two on the pinned artifact).
    """
    kappa = float(np.log(2.0) / half_life_years)
    dt = 1.0 / 12.0
    stationary_sd = sigma / np.sqrt(2.0 * kappa)
    u = float(rng.normal(0.0, stationary_sd))
    out = np.empty(n, dtype=np.float64)
    for t in range(n):
        out[t] = u
        u = u - kappa * u * dt + sigma * np.sqrt(dt) * float(rng.standard_normal())
    return out / stationary_sd


def run_chain(
    engine: FittedEngine,
    states: np.ndarray,
    yoy: np.ndarray,
    slope: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The fitted growth-axis chain over one decade. ``(season, expanding, z)``.

    ``slope`` is ``curve_lag_months + months`` long: its head is the decade's
    PRE-history, simulated on the same tape, so the lagged curve covariate is a
    real earlier reading rather than a value invented at the decade's edge.
    """
    months = states.shape[0]
    lag = int(engine.curve_lag_months)
    if slope.shape[0] != months + lag:
        raise FitError(f"slope must carry {months + lag} months (lag {lag}); got {slope.shape[0]}")
    hot = (yoy > engine.era_threshold_pp).astype(np.int64)
    v_dd = trailing_drawdown(states[:, 3], V_DRAWDOWN_WINDOW_MONTHS)
    dummy = (v_dd <= engine.v_threshold).astype(np.float64)
    z_raw = np.column_stack([slope[:months], states[:, 4], states[:, 0] - engine.pi_target, dummy])
    z = (z_raw - engine.z_mean) / engine.z_sd

    expanding = np.empty(months, dtype=bool)
    season = np.empty(months, dtype=np.int64)
    is_expanding = bool(rng.random() < engine.initial_expanding_rate)
    dwell = 1
    previous = -1
    for t in range(months):
        expanding[t] = is_expanding
        season[t] = (int(is_expanding) << 1) | int(hot[t])
        dwell = dwell + 1 if int(season[t]) == previous else 1
        previous = int(season[t])
        if rng.random() < hazard_probability(engine.beta, int(season[t]), dwell, z[t]):
            is_expanding = not is_expanding
    return season, expanding, z


def reject_reason(
    premise: Any, states: np.ndarray, expanding: np.ndarray, mu_pi: float
) -> str | None:
    """``ah.gen.spine._reject_reason``'s clauses, read off THIS layer's spine.

    Identical arithmetic and identical constants (imported, not restated); the
    only substitution is that "in a contraction" is the fitted chain's
    contracting axis rather than the six-label engine's ``{REC, CRI}`` codes,
    because that is this layer's own contraction.
    """
    from ah.gen.spine import (
        ARRIVAL_LATE_SLACK_MONTHS,
        BACKDROP_MARGIN_PP,
        SLOW_RECOVERY_MIN_MONTHS,
    )

    arrive = 3 * int(premise.arrives_quarter)
    pi_pre = float(states[:arrive, 0].mean())
    if premise.backdrop == "inflation_above_trend":
        if not pi_pre > mu_pi + BACKDROP_MARGIN_PP:
            return "backdrop:inflation_above_trend"
    elif pi_pre > mu_pi + BACKDROP_MARGIN_PP:
        return "backdrop:benign"
    in_c = ~expanding
    starts = np.flatnonzero(in_c & ~np.roll(in_c, 1))
    if in_c[0]:
        starts = np.unique(np.concatenate([[0], starts]))
    lo, hi = arrive - 3, arrive + ARRIVAL_LATE_SLACK_MONTHS
    if not ((starts >= lo) & (starts <= hi)).any():
        return "arrival"
    months_c = int(in_c.sum())
    if premise.recovery == "slow" and months_c < SLOW_RECOVERY_MIN_MONTHS:
        return "recovery:slow"
    if premise.recovery == "normal" and months_c >= SLOW_RECOVERY_MIN_MONTHS:
        return "recovery:normal"
    return None


def simulate_batch(
    engine: FittedEngine,
    climate: Any,
    *,
    n_decades: int,
    seed: int,
    months: int = DECADE_MONTHS,
    premise: Any | None = None,
) -> tuple[list[SimulatedDecade], dict[str, int]]:
    """``n_decades`` standalone L1+season decades. No flesh, no block sampler.

    Two L1 passes per attempt, the joinery/assemble pattern the pilot already
    uses: pass one runs the climate under a neutral cycle, the chain reads it,
    and pass two re-runs the SAME seed (so theta, s0 and the innovation tape are
    unchanged) with the chain's own ``c_t`` forcing the credit-gap norm. The
    chain is then re-run on pass two's states from the SAME re-opened stream, so
    the accepted decade is a fixed point of one tape rather than a splice of two.
    """
    kept: list[SimulatedDecade] = []
    tally: dict[str, int] = {}
    attempt = 0
    budget = MAX_ATTEMPTS_PER_DECADE * n_decades
    while len(kept) < n_decades and attempt < budget:
        step = SPINE2_ATTEMPT_STRIDE * attempt
        l1_seed = seed + CLIMATE_OFFSET + step
        sim1 = simulate_decades(climate, 1, seed=l1_seed, months=months)
        theta = {name: float(sim1.params[name][0]) for name in PARAM_NAMES}

        def _stream(name: str, offset_step: int = step) -> np.random.Generator:
            return np.random.Generator(np.random.PCG64(seed + LAYER_OFFSETS[name] + offset_step))

        lag = int(engine.curve_lag_months)
        rng_slope = _stream("slope")
        u_hat = ou_standardised(rng_slope, theta["hl_u"], theta["sigma_u"], months + lag)
        resid = ar1_path(
            rng_slope,
            float(engine.link["residual_ar1_rho"]),
            float(engine.link["residual_innovation_sd"]),
            months + lag,
        )
        slope = (
            float(engine.link["intercept"]) + float(engine.link["u_hat_loading"]) * u_hat + resid
        )
        eps = ar1_path(
            _stream("inflnoise"),
            engine.infl_residual_rho,
            engine.infl_residual_innovation_sd,
            months,
        )

        yoy1 = sim1.states[0, :, 0] + eps
        season1, _expanding1, _z1 = run_chain(
            engine, sim1.states[0], yoy1, slope, _stream("seasons")
        )
        cycle = engine.season_cycle[season1].reshape(1, -1)
        sim2 = simulate_decades(climate, 1, seed=l1_seed, months=months, cycle=cycle)
        yoy2 = sim2.states[0, :, 0] + eps
        season, expanding, z = run_chain(engine, sim2.states[0], yoy2, slope, _stream("seasons"))
        labels = emit_labels(season, yoy2, engine.stag_spell_rate, _stream("labels"))

        reason = (
            None
            if premise is None
            else reject_reason(premise, sim2.states[0], expanding, float(sim2.params["mu_pi"][0]))
        )
        if reason is None:
            kept.append(
                SimulatedDecade(
                    season=season,
                    labels=labels,
                    expanding=expanding,
                    yoy=yoy2,
                    slope=slope[lag:],
                    z=z,
                    states=sim2.states[0],
                    attempts=attempt,
                )
            )
        else:
            tally[reason] = tally.get(reason, 0) + 1
        attempt += 1
    if len(kept) < n_decades:
        raise FitError(
            f"premise unfillable at budget {budget}: accepted {len(kept)}/{n_decades}; "
            f"rejections {dict(sorted(tally.items()))}"
        )
    tally["attempts"] = attempt
    return kept, tally


def to_decade(sim: SimulatedDecade) -> Decade:
    """The judge-facing record. Asset returns are NaN: A1/A2 need the flesh."""
    months = int(sim.season.size)
    labels = np.asarray(sim.labels, dtype=object)
    yoy = sim.yoy.copy()
    yoy[:12] = np.nan  # the decade's own trailing-inflation warm-up
    nan = np.full(months, np.nan)
    return Decade(
        labels=labels,
        yoy=yoy,
        tight=(sim.slope < 0.0),
        equities=nan,
        bonds=nan,
        commodities=nan,
    )


# --------------------------------------------------------------------------- #
# the in-model verification loop -- SEALED judges, imported and unmodified
# --------------------------------------------------------------------------- #

#: The six bars this loop can measure. A1, A2, R1 and R2 need the flesh (asset
#: returns and the block sampler) and are WEEK 4; they are not measured here and
#: not guessed at.
PRE_SAMPLER_BARS = ("T1", "O1", "D1", "D2", "D3", "D4")
WEEK_FOUR_BARS = ("A1", "A2", "R1", "R2")


def judge_batch(decades: list[SimulatedDecade], sealed: dict[str, Any]) -> dict[str, Any]:
    """Every pre-sampler bar, judged by ``scripts/spine_v2_report``'s own judges."""
    batch = Batch(decades=tuple(to_decade(d) for d in decades))
    verdicts = judge_all(batch, sealed)
    return {code: verdicts[code] for code in PRE_SAMPLER_BARS}


def covariate_comparison(panel: Panel, decades: list[SimulatedDecade]) -> dict[str, Any]:
    """The anti-attenuation check: does each simulated covariate carry history's
    dispersion?

    A covariate whose generated-side spread is a fraction of its historical
    spread is attenuated, whatever the fitted coefficient says -- that is the
    defect this campaign's week 2 exists to remove, so it is measured rather
    than asserted.
    """
    hist = panel.z_raw
    sim = np.concatenate([d.z * panel.z_sd + panel.z_mean for d in decades], axis=0)
    out: dict[str, Any] = {}
    for j, name in enumerate(COVARIATES):
        h, s = hist[:, j], sim[:, j]
        out[name] = {
            "historical_mean": float(np.mean(h)),
            "historical_sd": float(np.std(h)),
            "simulated_mean": float(np.mean(s)),
            "simulated_sd": float(np.std(s)),
            "sd_ratio_simulated_over_historical": float(np.std(s) / np.std(h)),
        }
    slope_sim = np.concatenate([d.slope for d in decades])
    out["curve_slope"]["historical_inverted_share"] = float(np.mean(panel.slope < 0.0))
    out["curve_slope"]["simulated_inverted_share"] = float(np.mean(slope_sim < 0.0))
    out["curve_slope"]["pilot_proxy_inverted_share"] = 0.0
    out["curve_slope"]["pilot_proxy_note"] = (
        "the pilot's simulation-time slope is psi0 - phi_c0*c(R_t): three values on the "
        "pinned artifact, spanning 0.60 to 0.79 pp, never below zero (semimarkov.py's own "
        "recorded v1 limitation) -- this is the attenuation week 2 was funded to remove"
    )
    return out


def season_summary(
    panel: Panel, cells: np.ndarray, decades: list[SimulatedDecade]
) -> dict[str, Any]:
    """Occupancy and transition composition, history beside the generated batch."""

    def _split(season: np.ndarray) -> dict[str, Any]:
        arr = np.asarray(season, dtype=np.int64)
        valid = arr >= 0
        growth = 0
        hot_moves = 0
        both = 0
        for t in range(1, arr.size):
            a, b = int(arr[t - 1]), int(arr[t])
            if a < 0 or b < 0 or a == b:
                continue
            dg = EXPANDING[a] != EXPANDING[b]
            dh = HOT[a] != HOT[b]
            if dg and dh:
                both += 1
            elif dg:
                growth += 1
            else:
                hot_moves += 1
        return {
            "occupancy": {QUADRANTS[s]: float(np.mean(arr[valid] == s)) for s in range(4)},
            "transitions_total": growth + hot_moves + both,
            "growth_axis_flips": growth,
            "inflation_crossings": hot_moves,
            "diagonal_moves": both,
        }

    per_decade = [_split(d.season) for d in decades]
    return {
        "historical_panel": _split(cells),
        "generated_batch_pooled": {
            "occupancy": {
                QUADRANTS[s]: float(np.mean(np.concatenate([d.season for d in decades]) == s))
                for s in range(4)
            },
            "transitions_total": sum(r["transitions_total"] for r in per_decade),
            "growth_axis_flips": sum(r["growth_axis_flips"] for r in per_decade),
            "inflation_crossings": sum(r["inflation_crossings"] for r in per_decade),
            "diagonal_moves": sum(r["diagonal_moves"] for r in per_decade),
        },
    }


def bar_readings(verdicts: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per pre-sampler bar: the sealed band, and where the fit landed."""
    rows: list[dict[str, Any]] = []
    for code in PRE_SAMPLER_BARS:
        v = verdicts[code]
        band = v.get("band") or [v.get("threshold"), None]
        rows.append(
            {
                "bar": code,
                "sealed_band": band,
                "measured": v["value"],
                "pass": bool(v["pass"]),
                "detail": {
                    k: v[k]
                    for k in (
                        "n_transitions",
                        "n_clockwise",
                        "n_pooled_spells",
                        "tight_months",
                        "eligible_months",
                        "conditional_rate",
                        "unconditional_rate",
                        "tight_base_rate",
                        "quartiles_months",
                        "spells_per_decade",
                    )
                    if k in v
                },
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# the trade-off frontier, and the T1 decomposition that explains it
# --------------------------------------------------------------------------- #

#: Multipliers applied to the FITTED transmission coefficient. 1.0 is the fit;
#: 0.0 is the null engine with no policy-to-downturn channel at all (which the
#: exam says must fail T1, and which is therefore also an anti-test of this
#: sweep); the rest are the frontier the task asks to be mapped when the joint
#: fit cannot reach the transmission band and the dwell bands at once.
FRONTIER_MULTIPLIERS: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def scale_transmission(engine: FittedEngine, multiplier: float) -> FittedEngine:
    """The same engine with the expanding-side curve loading scaled.

    ONLY that one coefficient moves. Nothing is re-fitted, no other parameter is
    touched, and the multiplier is reported beside every row -- so a frontier row
    is a counterfactual about transmission strength and about nothing else.
    """
    from dataclasses import replace

    beta = engine.beta.copy()
    beta[8] = engine.beta[8] * float(multiplier)
    return replace(engine, beta=beta)


def t1_decomposition(
    panel: Panel, cells: np.ndarray, decades: list[SimulatedDecade], sealed: dict[str, Any]
) -> dict[str, Any]:
    """Where T1's lift comes from on each side: tight months by growth axis.

    History's inverted-curve months sit disproportionately in LATE EXPANSIONS --
    the curve inverts because policy is tightening into a boom, and it steepens
    once the downturn arrives. The fitted engine's curve is driven by L1's
    policy-deviation state and its own AR(1) residual, with NO feedback from the
    season, so its inverted months are spread across the seasons instead of
    concentrated ahead of a turn. This function measures that difference rather
    than asserting it, because it is the single largest reason the in-model T1
    lift falls short of history's.
    """
    k = int(sealed["parameters"]["k_months"])
    downturn = tuple(sealed["parameters"]["downturn_labels"])

    def _side(labels: np.ndarray, yoy: np.ndarray, tight: np.ndarray, season: np.ndarray):
        n = labels.shape[0]
        is_down = np.isin(labels, list(downturn))
        onset = np.zeros(n, dtype=bool)
        onset[0] = bool(is_down[0])
        onset[1:] = is_down[1:] & ~is_down[:-1]
        followed = np.zeros(n, dtype=bool)
        for t in range(n - k):
            followed[t] = bool(onset[t + 1 : t + 1 + k].any())
        eligible = ~np.isnan(yoy)
        eligible[max(n - k, 0) :] = False
        expanding = np.array([EXPANDING[int(s)] if s >= 0 else False for s in season], dtype=bool)
        out: dict[str, Any] = {}
        for name, mask in (
            ("all", eligible),
            ("expanding_only", eligible & expanding),
            ("contracting_only", eligible & ~expanding),
        ):
            t_mask = mask & tight
            out[name] = {
                "months": int(mask.sum()),
                "tight_months": int(t_mask.sum()),
                "tight_share": float(t_mask.sum() / mask.sum()) if mask.sum() else float("nan"),
                "conditional_rate": (
                    float(followed[t_mask].mean()) if t_mask.sum() else float("nan")
                ),
                "unconditional_rate": (
                    float(followed[mask].mean()) if mask.sum() else float("nan")
                ),
            }
            out[name]["lift"] = (
                out[name]["conditional_rate"] / out[name]["unconditional_rate"]
                if out[name]["unconditional_rate"]
                else float("nan")
            )
        out["tight_months_that_are_expanding"] = (
            float((eligible & tight & expanding).sum() / (eligible & tight).sum())
            if (eligible & tight).sum()
            else float("nan")
        )
        out["all_months_that_are_expanding"] = (
            float((eligible & expanding).sum() / eligible.sum()) if eligible.sum() else float("nan")
        )
        return out

    hist = _side(
        np.asarray(panel.labels),
        panel.yoy,
        np.asarray(panel.slope < 0.0),
        np.asarray(cells, dtype=np.int64),
    )
    gen_labels = np.concatenate([np.asarray(d.labels) for d in decades])
    gen_yoy = np.concatenate([to_decade(d).yoy for d in decades])
    gen_tight = np.concatenate([d.slope < 0.0 for d in decades])
    gen_season = np.concatenate([d.season for d in decades])
    # the per-decade lookahead must not run across a decade boundary, so the
    # generated side is decomposed decade by decade and pooled by counts
    per_decade = [
        _side(np.asarray(d.labels), to_decade(d).yoy, d.slope < 0.0, d.season) for d in decades
    ]
    pooled: dict[str, Any] = {}
    for name in ("all", "expanding_only", "contracting_only"):
        months = sum(r[name]["months"] for r in per_decade)
        tight_months = sum(r[name]["tight_months"] for r in per_decade)
        cond = sum(
            r[name]["conditional_rate"] * r[name]["tight_months"]
            for r in per_decade
            if r[name]["tight_months"]
        )
        unc = sum(
            r[name]["unconditional_rate"] * r[name]["months"]
            for r in per_decade
            if r[name]["months"]
        )
        pooled[name] = {
            "months": months,
            "tight_months": tight_months,
            "tight_share": tight_months / months if months else float("nan"),
            "conditional_rate": cond / tight_months if tight_months else float("nan"),
            "unconditional_rate": unc / months if months else float("nan"),
        }
        pooled[name]["lift"] = (
            pooled[name]["conditional_rate"] / pooled[name]["unconditional_rate"]
            if pooled[name]["unconditional_rate"]
            else float("nan")
        )
    expanding_gen = np.array([EXPANDING[int(s)] for s in gen_season], dtype=bool)
    defined = ~np.isnan(gen_yoy)
    pooled["tight_months_that_are_expanding"] = float(
        (defined & gen_tight & expanding_gen).sum() / (defined & gen_tight).sum()
    )
    pooled["all_months_that_are_expanding"] = float((defined & expanding_gen).sum() / defined.sum())
    _ = gen_labels
    return {
        "historical_panel": hist,
        "generated_batch": pooled,
        "reading": (
            "compare tight_months_that_are_expanding on the two sides: history's inverted "
            "curve is concentrated in expansions (it inverts ahead of a turn and steepens "
            "once the turn arrives); the fitted engine's curve is exogenous to the season, "
            "so its inverted months are spread across all four seasons and T1's tight "
            "population is diluted by months that are already contracting"
        ),
    }


def frontier(
    engine: FittedEngine,
    climate: Any,
    sealed: dict[str, Any],
    *,
    n_decades: int,
    premise: Any | None,
    arm: str,
) -> list[dict[str, Any]]:
    """T1 and the four dwell medians (and O1) across the transmission frontier.

    This is the table the campaign's two-week cheap-failure exit calls for: it
    shows, at a glance, whether ANY transmission strength puts T1 inside its band
    while the dwell medians stay inside theirs -- and if none does, where the two
    requirements cross.
    """
    rows: list[dict[str, Any]] = []
    for multiplier in FRONTIER_MULTIPLIERS:
        scaled = scale_transmission(engine, multiplier)
        decades, tally = simulate_batch(
            scaled, climate, n_decades=n_decades, seed=VERIFY_SEED, premise=premise
        )
        verdicts = judge_batch(decades, sealed)
        rows.append(
            {
                "arm": arm,
                "transmission_multiplier": float(multiplier),
                "transmission_coefficient": float(scaled.beta[8]),
                "T1_lift": float(verdicts["T1"]["value"]),
                "T1_pass": bool(verdicts["T1"]["pass"]),
                "T1_conditional_rate": float(verdicts["T1"]["conditional_rate"]),
                "T1_unconditional_rate": float(verdicts["T1"]["unconditional_rate"]),
                "T1_tight_base_rate": float(verdicts["T1"]["tight_base_rate"]),
                "O1_clockwise": float(verdicts["O1"]["value"]),
                "O1_pass": bool(verdicts["O1"]["pass"]),
                "D1_recession_median": float(verdicts["D1"]["value"]),
                "D2_stagflation_median": float(verdicts["D2"]["value"]),
                "D3_recovery_median": float(verdicts["D3"]["value"]),
                "D4_expansion_median": float(verdicts["D4"]["value"]),
                "D_all_pass": bool(all(verdicts[c]["pass"] for c in ("D1", "D2", "D3", "D4"))),
                "all_six_pass": bool(all(verdicts[c]["pass"] for c in PRE_SAMPLER_BARS)),
                "attempts": int(tally.get("attempts", n_decades)),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def _load_premise() -> Any:
    """The standard premise: the one spine preset the platform carries."""
    from ah.core.worldspec import SpineSpec

    doc = json.loads(
        (_REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json").read_text(encoding="utf-8")
    )
    return SpineSpec.model_validate(doc["extensions"]["x_spine"]).premise


def build_engine(
    panel: Panel, primary: dict[str, Any], cells: np.ndarray, lag: int, stag: dict[str, float]
) -> FittedEngine:
    """Bundle the fitted numbers into the object the simulator consumes."""
    defined = ~np.isnan(panel.yoy)
    resid = panel.yoy[defined] - panel.z_raw[defined, 2] - panel.diagnostics["pi_target"]
    rho = float(np.corrcoef(resid[1:], resid[:-1])[0, 1])
    innovation_sd = float(np.std(resid[1:] - rho * resid[:-1]))
    expanding_rate = float(np.mean([EXPANDING[int(c)] for c in cells[cells >= 0]]))
    return FittedEngine(
        beta=np.asarray(primary["beta"], dtype=np.float64),
        z_mean=panel.z_mean,
        z_sd=panel.z_sd,
        era_threshold_pp=panel.era_threshold_pp,
        pi_target=float(panel.diagnostics["pi_target"]),
        link=panel.link,
        v_threshold=panel.v_threshold,
        season_cycle=cycle_by_season(panel, cells),
        infl_residual_rho=rho,
        infl_residual_innovation_sd=innovation_sd,
        initial_expanding_rate=expanding_rate,
        curve_lag_months=int(lag),
        stag_spell_rate=float(stag["spell_rate"]),
        stag_cpi_line_pp=STAG_CPI_LINE_PP,
    )


def _round(obj: Any, digits: int = 12) -> Any:
    """Round every float to ``digits`` places so re-runs are byte-identical.

    IRLS converges to a fixed point rather than to an exact rational, and BLAS
    is free to reassociate; rounding the OUTPUT at a resolution far below any
    reported precision is what makes ``json.dumps`` reproducible without
    pretending the twelfth decimal is meaningful.
    """
    if isinstance(obj, dict):
        return {k: _round(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v, digits) for v in obj]
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return None if np.isnan(value) else round(value, digits)
    if isinstance(obj, (np.integer, int)) and not isinstance(obj, bool):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _round(obj.tolist(), digits)
    return obj


def main() -> int:
    streams = assert_distinct_tapes()
    sealed = load_sealed()
    n_decades = int(sealed["bars"].get("n_seeds", DEFAULT_N_DECADES))

    panel = build_panel()
    cells = season_cells(panel.labels, panel.yoy, panel.era_threshold_pp)
    lag_selection = select_curve_lag(panel, cells)
    lag = int(lag_selection["selected_lag_months"])
    primary = fit_arm(cells, panel.z_lagged(lag))
    stability = label_stability(panel, primary, lag)
    stag = measure_stag_spell_rate(panel, cells)
    engine = build_engine(panel, primary, cells, lag, stag)

    climate, _regimes = _pinned_layers()
    premise = _load_premise()
    accepted, tally = simulate_batch(
        engine, climate, n_decades=n_decades, seed=VERIFY_SEED, premise=premise
    )
    unconditional, _ = simulate_batch(
        engine, climate, n_decades=n_decades, seed=VERIFY_SEED, premise=None
    )

    verdicts = judge_batch(accepted, sealed)
    verdicts_unconditional = judge_batch(unconditional, sealed)
    rows = bar_readings(verdicts)
    rows_unconditional = bar_readings(verdicts_unconditional)
    all_pass = all(r["pass"] for r in rows)
    frontier_rows = frontier(
        engine, climate, sealed, n_decades=n_decades, premise=premise, arm="premise_accepted"
    ) + frontier(engine, climate, sealed, n_decades=n_decades, premise=None, arm="unconditional")
    decomposition = t1_decomposition(panel, cells, accepted, sealed)

    payload: dict[str, Any] = {
        "schema": "spine-v2-fitted-params-1",
        "purpose": (
            "spine v2 week 2: the season-transition hazard fitted to history by maximum "
            "likelihood, with duration dependence, and its in-model verification against "
            "the six pre-sampler bars of the SEALED exam. A1/A2/R1/R2 need the flesh and "
            "are week 4."
        ),
        "spec": "docs/superpowers/specs/2026-08-17-spine-v2-exam.md",
        "seal": "docs/superpowers/specs/spine-v2-prereg.json",
        "seal_files_untouched": sorted(sealed["hashed_files"]),
        "status": "FIT-VERIFIED" if all_pass else "FRONTIER",
        "panel": panel.diagnostics,
        "curve_link": panel.link,
        "model": {
            "form": (
                "logit h_t = a_[season] + b_[season]*log(dwell_t) + z_t' g_[growth axis]; "
                "y_t = 1[growth axis flips between t and t+1]; weighted Bernoulli "
                "log-likelihood over at-risk months, maximised by IRLS"
            ),
            "state_space": list(QUADRANTS),
            "covariates": list(COVARIATES),
            "parameter_labels": list(PARAM_LABELS),
            "duration_dependence": (
                "one log(dwell) slope per season, fitted jointly with the covariate "
                "loadings in one design matrix; b_s = 0 is a memoryless geometric chain, "
                "so no-duration-dependence is nested and testable by a t-ratio"
            ),
            "at_risk_rule": (
                "a defined season this month and next, every covariate readable, and not "
                "inside the panel's first (left-truncated) season spell; the panel's last "
                "month is right-censored out"
            ),
            "curve_lag_selection": lag_selection,
            "label_emission": {
                "rule": (
                    "expanding -> EXP; a contracting SPELL draws once at the measured rate "
                    "and, if it draws STAG, its months at or above the ruleset's 4.0 pp CPI "
                    "line are STAG and the rest REC; CRI is never emitted"
                ),
                "measured_on_history": stag,
                "why_not_one_label_per_season": (
                    "T1's downturn union is REC-or-CRI and is NOT re-anchored under the "
                    "mapping fix, so the REC/STAG split inside the contracting side decides "
                    "T1's numerator; on the panel it is 64 REC-or-CRI against 31 STAG among "
                    "the 95 contracting months at or above 4.0 pp"
                ),
            },
        },
        "fit": {
            "coefficients": primary["coefficients"],
            "standard_errors": primary["standard_errors"],
            "t_ratios": {
                k: primary["coefficients"][k] / primary["standard_errors"][k] for k in PARAM_LABELS
            },
            "n_at_risk_months": primary["n_obs"],
            "n_growth_axis_flips": primary["n_events"],
            "loglik": primary["loglik"],
        },
        "engine": {
            "season_cycle": engine.season_cycle,
            "initial_expanding_rate": engine.initial_expanding_rate,
            "inflation_residual_ar1_rho": engine.infl_residual_rho,
            "inflation_residual_innovation_sd": engine.infl_residual_innovation_sd,
            "valuation_drawdown_threshold": engine.v_threshold,
            "curve_lag_months": engine.curve_lag_months,
            "stag_spell_rate": engine.stag_spell_rate,
            "stag_cpi_line_pp": engine.stag_cpi_line_pp,
            "covariate_standardisation": {
                "mean": panel.z_mean,
                "sd": panel.z_sd,
            },
        },
        "label_stability": stability,
        "verification": {
            "n_decades": n_decades,
            "months_per_decade": DECADE_MONTHS,
            "seed": VERIFY_SEED,
            "streams": streams,
            "premise": premise.model_dump(),
            "premise_acceptance": tally,
            "bars_measured": list(PRE_SAMPLER_BARS),
            "bars_deferred_to_week_4": list(WEEK_FOUR_BARS),
            "bars_deferred_reason": (
                "A1 and A2 are measured on asset returns and R1/R2 on a compiled "
                "ensemble; a no-flesh spine has none of those, so they are NOT measured "
                "here and NOT estimated"
            ),
            "readings": rows,
            "verdicts_full": verdicts,
            "readings_unconditional_disclosure": rows_unconditional,
            "verdicts_unconditional_full": verdicts_unconditional,
            "t1_decomposition": decomposition,
            "transmission_frontier": {
                "multipliers": list(FRONTIER_MULTIPLIERS),
                "what_moves": (
                    "ONLY cov_expanding[curve_slope], scaled; nothing is re-fitted and no "
                    "other parameter is touched, so a row is a counterfactual about "
                    "transmission strength and nothing else"
                ),
                "rows": frontier_rows,
            },
            "covariate_dispersion": covariate_comparison(panel, accepted),
            "season_composition": season_summary(panel, cells, accepted),
        },
    }
    payload = _round(payload)
    PARAMS_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {PARAMS_PATH.relative_to(_REPO_ROOT)}")
    print(f"status: {payload['status']}")
    print(
        f"fit: {primary['n_events']:.0f} growth-axis flips in "
        f"{primary['n_obs']:.0f} at-risk months, loglik {primary['loglik']:.4f}"
    )
    for name in PARAM_LABELS:
        b = primary["coefficients"][name]
        se = primary["standard_errors"][name]
        print(f"  {name:34s} {b:+9.4f}  se {se:7.4f}  t {b / se:+6.2f}")
    print(f"curve lag selected by likelihood: {lag} months")
    for row in lag_selection["profile"]:
        print(
            f"   lag {row['lag_months']:2d}  loglik {row['loglik']:10.4f}  "
            f"transmission {row['transmission']:+.4f} (se {row['standard_error']:.4f})"
        )
    print(f"label stability: {stability['verdict']}")
    print(
        f"  worst threshold arm {stability['worst_threshold_arm']} moves it by "
        f"{stability['worst_threshold_arm_moves_by_se']:+.3f} SE; borderline-downweighted "
        f"{stability['borderline_downweighted_moves_by_se']:+.3f} SE"
    )
    print("bars (sealed band -> measured):")
    for row in rows:
        print(
            f"  {row['bar']}: band {row['sealed_band']}  measured {row['measured']:.6f}  "
            f"{'PASS' if row['pass'] else 'FAIL'}"
        )
    print("covariate dispersion (simulated sd / historical sd):")
    for name, entry in payload["verification"]["covariate_dispersion"].items():
        print(f"  {name:16s} {entry['sd_ratio_simulated_over_historical']:.3f}")
    print(
        "  curve inverted share: historical "
        f"{payload['verification']['covariate_dispersion']['curve_slope']['historical_inverted_share']:.4f}"
        "  simulated "
        f"{payload['verification']['covariate_dispersion']['curve_slope']['simulated_inverted_share']:.4f}"
        "  pilot proxy 0.0000"
    )
    print(
        "season composition:", json.dumps(payload["verification"]["season_composition"], indent=1)
    )
    print("unconditional disclosure (the same engine with no premise acceptance):")
    for row in rows_unconditional:
        print(
            f"  {row['bar']}: band {row['sealed_band']}  measured {row['measured']:.6f}  "
            f"{'PASS' if row['pass'] else 'FAIL'}"
        )
    print("transmission frontier (multiplier | T1 | O1 | D1 D2 D3 D4):")
    for row in frontier_rows:
        print(
            f"  {row['arm']:17s} x{row['transmission_multiplier']:<4} "
            f"T1 {row['T1_lift']:.4f} {'P' if row['T1_pass'] else 'F'}  "
            f"O1 {row['O1_clockwise']:.4f} {'P' if row['O1_pass'] else 'F'}  "
            f"D {row['D1_recession_median']:.0f} {row['D2_stagflation_median']:.0f} "
            f"{row['D3_recovery_median']:.0f} {row['D4_expansion_median']:.0f} "
            f"{'all-D-pass' if row['D_all_pass'] else 'D-FAIL'}"
            f"{'  ALL SIX PASS' if row['all_six_pass'] else ''}"
        )
    print("T1 decomposition:", json.dumps(payload["verification"]["t1_decomposition"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
