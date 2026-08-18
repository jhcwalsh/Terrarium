"""Stage 2, week A: the COUPLED macro system, fitted jointly and verified.

Spec: ``docs/superpowers/specs/2026-08-17-stage2-coupled-system-design.md`` (the
model class), judged by the sealed exam
``docs/superpowers/specs/2026-08-18-stage2-exam-delta.md`` and its seal
``docs/superpowers/specs/stage2-prereg.json``.

**What this script is.** Weeks 2 and 3 of the spine-v2 campaign built a set of
independent dials with a hazard bolted on. Stage 2 turns on the couplings that
were zero: inflation responds to growth at a lag chosen by the sealed selection
rule, policy leans on inflation and the cycle, and the yield curve reads the
policy rate the model implies rather than the rule's leftovers. The four blocks
are fitted as one likelihood on one panel, the system is simulated for fifty
unconditional decades, and the eight pre-flesh bars are read by the SEALED
judges, imported and never re-implemented.

**Nothing sealed is touched.** Every file in ``stage2-prereg.json`` and in
``spine-v2-prereg.json`` is opened read-only; ``src/`` and ``schemas/`` are not
touched by this campaign at all. The judges come from ``scripts/stage2_report``
and ``scripts/spine_v2_report``; the anchor-side machinery (the M3 coupling
equation, the M4 curve design, the strict economic share) comes from
``scripts/stage2_anchors``, imported rather than copied, so the judged side and
the anchor side are provably the same code.

**A1, A2, R1 and R2 are NOT measurable here and are not measured.** A1 and A2
need the flesh (real months of asset returns compiled onto the spine); R1 needs
the institutional twin's over-commitment grid and R2 needs an ensemble and the
panel source. All four are week C's, and this script reports them as absent
rather than as anything else.

---

The system, as fitted (the design document's §2.2 block, with every deviation
named in :data:`DEVIATIONS`)::

    growth chain   season_{t+1} ~ Bernoulli(h(season_t, dwell_t, z_t))
    cycle input    c_t   = the WP2.6 contract, produced INSIDE the system
    inflation gap  x_{t+1} = k0 + a x_t + lam_x (c_{t-m} - cbar) + sig_x e_t   [NEW]
    inflation      pi_t  = pi*_t + x_t
    policy dev     u_{t+1} = u0 + phi_u u_t + lam_u x_t + lam_c c_t + sig_u e_t [NEW loadings]
    policy rate    i_t   = r*_t + pi*_t + phi_pi x_t + phi_c c_t     [L1's rule]
    curve slope    slope_t = c0 + c_i (i_t - ibar) + c_x (x_t - xbar)
                             + season_term(g_t, age_t) + e_t,  e AR(1)

**The primary estimator and every primary construct are declared in code, at
module level, before any bar is read** -- week 3's precedent, and the specific
mitigation the design document's risk table names for "the 93.9% trap".
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_feedback import (  # noqa: E402
    FEEDBACK_LAYER_OFFSETS,
    CurveModel,
    _numerical_hessian,
    _perturbed_labels,
    ar1_loglik,
    chi2_sf_df3,
    curve_model_from_fit,
    first_spell_end,
    fit_joint,
    growth_axis,
    spell_age,
)
from spine_v2_fit import (  # noqa: E402
    CLIMATE_OFFSET,
    DECADE_MONTHS,
    DEFAULT_N_DECADES,
    MAX_ATTEMPTS_PER_DECADE,
    PLATFORM_SEED_STRIDE,
    SPINE2_ATTEMPT_STRIDE,
    STABILITY_ARMS,
    TRANSMISSION_KEY,
    V_DRAWDOWN_WINDOW_MONTHS,
    VERIFY_SEED,
    FitError,
    FittedEngine,
    Panel,
    SimulatedDecade,
    ar1_path,
    build_engine,
    build_panel,
    emit_labels,
    fit_arm,
    hazard_probability,
    measure_stag_spell_rate,
    reject_reason,
    relabel,
    select_curve_lag,
    to_decade,
    trailing_drawdown,
)
from spine_v2_grader import season_cells  # noqa: E402
from spine_v2_report import Batch as V2Batch  # noqa: E402
from stage2_anchors import (  # noqa: E402
    M3_LAG_GRID_MONTHS,
    _chi2_sf_df1,
    _m3_fit,
    _m3_month_index,
    _m3_rows,
    _m4_design,
    _m4_statistics,
    _maximise_rho_blocks,
    _profile_blocks,
    rule_implied_states,
    strict_economic_share,
)
from stage2_report import Batch as P1Batch  # noqa: E402
from stage2_report import Decade as P1Decade  # noqa: E402
from stage2_report import (  # noqa: E402
    disclose_o1_symmetric,
    judge_carried_v2,
    judge_p1,
    judge_p2,
    load_sealed,
    load_v2_sealed,
)

from ah.gen.bootstrap import (  # noqa: E402
    CAMPAIGN_VINTAGE_ID,
    USREC_SERIES_ID,
    _catalog_access,
    _monthly,
    _read_series,
)
from ah.gen.climate.simulate import simulate_decades  # noqa: E402
from ah.gen.systems import _pinned_layers  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
PARAMS_PATH = SPECS_DIR / "stage2-fitted-params.json"
FEEDBACK_PARAMS_PATH = SPECS_DIR / "spine-v2-feedback-params.json"

# --------------------------------------------------------------------------- #
# seeds and streams -- one literal per NEW consumer, no seed derived from another
# --------------------------------------------------------------------------- #

#: The verification loop's base seed. **Deliberately week 3's**, so the stage-2
#: batch is the same batch identity as the one on the record and a change of
#: verdict is attributable to the engine rather than to a different tape. The
#: anchors made the same choice for the same reason (``generated_side_scrambled
#: _null.seed_note``).
STAGE2_VERIFY_SEED = VERIFY_SEED

#: The policy-deviation stream's per-decade offset. NEW: stage 2 gives ``u`` its
#: own equation with two loadings, so it can no longer be drawn on the ``slope``
#: stream after the OU that week 2 opened there. Distinct from the four offsets
#: in ``spine_v2_fit.LAYER_OFFSETS``, from ``spine_v2_feedback``'s ``openage``,
#: and from every value in ``ah.gen.spine.LAYER_OFFSETS`` -- proved by drawing
#: whole tapes in :func:`assert_stage2_tapes_distinct`, not by observing that
#: two integers differ.
POLICYDEV_OFFSET = 1674811

#: Every per-decade stream stage 2 opens.
STAGE2_LAYER_OFFSETS: dict[str, int] = {**FEEDBACK_LAYER_OFFSETS, "policydev": POLICYDEV_OFFSET}

# --------------------------------------------------------------------------- #
# THE PRIMARY CONSTRUCTS -- declared here, before any bar is read
# --------------------------------------------------------------------------- #

#: The curve equation the fit and the judge both use. ``m4`` is the sealed
#: anchor's own equation: the curve reads the RULE-IMPLIED policy rate
#: ``i_rule = r* + pi* + phi_pi x + phi_c c`` and the inflation gap, and the
#: policy deviation ``u`` does not enter it at all. That is the substitution the
#: design document named as decisive and the anchors then measured
#: (``m4_curve_endogeneity.regressor_substitution``), and it is what makes P2's
#: fourth obligation -- one decomposition function on both sides -- structural.
PRIMARY_CURVE_ARM = "m4_rule_implied"

#: The cycle input the coupling reads on the GENERATED side. ``axis_calibrated``
#: is the panel mean of the WP2.6 contract ``1 - 2*USREC`` inside each of the
#: classifier's two growth axes -- ``spine_v2_fit.cycle_by_season``'s own
#: construction, moved from the four seasons to the two axes.
#:
#: **Why this and not the design document's literal ``+1 / -1``.** ``lam_x`` is
#: fitted against ``1 - 2*USREC``, whose mean on the panel is +0.73 and which
#: fires on NBER recessions (13.5% of months). The engine's contracting axis is
#: ``grader_v2``'s ``{REC, CRI, STAG}`` and fires on 27.5%. Feeding a literal
#: ``-1`` into a coefficient fitted on that regressor both doubles its range and
#: moves its mean, which shifts the generated inflation LEVEL by a quarter of a
#: percentage point as a side effect of a phase change. The calibrated map has
#: the law of total expectation on its side: averaged over the panel's own axis
#: shares it reproduces ``cbar`` exactly, so it adds phase without re-levelling.
#: **And why not the four-season map v2 already uses to force L1**: that one is
#: indexed by season, so it would make the cycle input a function of the hot/cool
#: dial -- injecting an inflation-to-inflation channel of the wrong sign into the
#: very statistic P1 measures. The design document's ``c_t`` is the growth axis.
PRIMARY_CYCLE_INPUT = "axis_calibrated"

#: The hazard block's form. ``v2_unchanged`` keeps week 2's four covariates,
#: including ``pi_gap = pi* - pi_target`` (the TREND gap). The design document's
#: §2.2 hazard line writes ``x_t`` in that slot, which is a different object (the
#: gap of actual inflation around the trend). The ambiguity is resolved toward
#: "unchanged in form" -- the same sentence's own words, and week 3's discipline
#: that the transmission channel is never re-tuned to reach a bar -- and the
#: substitution is fitted as a DISCLOSURE so the cost of the choice is a number.
PRIMARY_HAZARD_ARM = "v2_unchanged"

#: Deviations from the design document's §2.2 block, each with its reason. They
#: are in the artifact, not only in this docstring.
DEVIATIONS: tuple[tuple[str, str], ...] = (
    (
        "the curve reads i_rule, not i = i_rule + u",
        "the sealed P2 anchor (exam delta 4.3) decomposes history on the rule-implied "
        "rate and classifies u_hat as exogenous. Keeping u out of the curve makes the "
        "generated and historical decompositions the same object with an empty exogenous "
        "block on both sides. The i_rule + u arm is fitted and reported as a disclosure",
    ),
    (
        "the hazard's third covariate stays pi* - pi_target",
        "the design document writes x_t there and calls the chain 'unchanged in form' in "
        "the same paragraph; the substitution is fitted as a disclosure rather than taken",
    ),
    (
        "the generated cycle input is the axis-calibrated WP2.6 contract, not +1/-1",
        "see PRIMARY_CYCLE_INPUT: a literal +-1 applies a USREC-fitted coefficient to a "
        "regressor with a different mean and twice the range, which moves the inflation "
        "LEVEL as a side effect. Both alternatives are simulated and reported",
    ),
    (
        "the inflation innovation is drawn i.i.d.",
        "that is the equation as fitted. Its residual carries a lag-1 autocorrelation of "
        "0.198 from the trailing-12-month construction; simulating that structure would "
        "be simulating a model that was not estimated. Declared as a limitation",
    ),
)

#: The frontier's coupling multipliers -- the design document's own sweep.
COUPLING_MULTIPLIERS: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0, 4.0)
#: The frontier's curve-loading multipliers, applied to ``c_i``, ``c_x`` and the
#: season block together (P2's first anti-test obligation, on the fitted engine).
LOADING_MULTIPLIERS: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)

#: The eight bars a no-flesh spine can be judged on at all.
PRE_FLESH_BARS = ("T1", "O1", "D1", "D2", "D3", "D4", "P1", "P2")
#: The four that need the flesh or the twin. Week C's, and reported as absent.
WEEK_C_BARS = ("A1", "A2", "R1", "R2")

#: A coefficient is called UNIDENTIFIED when its 95% interval spans both signs.
IDENTIFIABILITY_Z = 1.959963984540054

#: The one identifiability condition that STOPS the campaign, and it is
#: pre-declared -- the design document's **Cheap Exit A**, quoted: "If ``lam_x``
#: -- inflation's response to growth -- is not significant on the panel, stop.
#: The mechanism O1 needs is then not identifiable at this resolution on 68
#: years, which is a finding worth having for one week's spend." No other
#: coefficient carries a pre-declared stop, so no other one is allowed to
#: acquire one after the estimates are visible: the rest are REPORTED, plainly,
#: whichever way they come out.
STOP_COEFFICIENT = "lam_x"

#: Coefficients whose identification the design document's §1 makes load-bearing
#: -- the two missing mechanisms it measured, plus the policy block §2.2 adds.
LOAD_BEARING = ("lam_x", "lam_u", "lam_c", "c_i_policy_rule", "c_x_inflation_gap")

#: How large a refit tolerance the committed artifacts' own rounding allows.
ANCHOR_TOLERANCE = 1e-11


# --------------------------------------------------------------------------- #
# stream hygiene
# --------------------------------------------------------------------------- #


def assert_stage2_tapes_distinct(
    base_seed: int = STAGE2_VERIFY_SEED, n: int = 64
) -> dict[str, Any]:
    """Prove stage 2's streams collide with nothing, numerically.

    The same three claims ``spine_v2_fit.assert_distinct_tapes`` makes, extended
    to the new ``policydev`` stream and additionally checked against every
    per-decade offset the platform's own spine uses -- whole tapes drawn and
    compared, never a comparison of two integers.
    """
    from math import gcd

    from ah.gen.spine import ATTEMPT_STRIDE as SPINE_ATTEMPT_STRIDE
    from ah.gen.spine import LAYER_OFFSETS as PLATFORM_LAYER_OFFSETS

    if gcd(SPINE2_ATTEMPT_STRIDE, PLATFORM_SEED_STRIDE) != 1:
        raise FitError("SPINE2_ATTEMPT_STRIDE must be coprime to the platform SEED_STRIDE")
    if SPINE2_ATTEMPT_STRIDE == SPINE_ATTEMPT_STRIDE:
        raise FitError("SPINE2_ATTEMPT_STRIDE must differ from ah.gen.spine.ATTEMPT_STRIDE")
    if len(set(STAGE2_LAYER_OFFSETS.values())) != len(STAGE2_LAYER_OFFSETS):
        raise FitError("two stage-2 per-decade offsets are equal")

    def tape(seed: int, jump: int) -> tuple[float, ...]:
        rng = np.random.Generator(np.random.PCG64(int(seed)).jumped(int(jump)))
        return tuple(float(x) for x in rng.random(8))

    tapes: dict[tuple[str, int], tuple[float, ...]] = {}
    for name, offset in STAGE2_LAYER_OFFSETS.items():
        for k in range(n):
            tapes[(name, k)] = tape(base_seed + offset, k)
    if len(set(tapes.values())) != len(tapes):
        raise FitError("two stage-2 per-decade streams share a tape")

    platform_streams = {
        tape(base_seed + offset, k)
        for offset in PLATFORM_LAYER_OFFSETS.values()
        for k in range(n)
        # the climate stream at offset 0 IS the intended shared call into
        # simulate_decades, exactly as spine_v2_fit documents; it is not a
        # collision and is excluded from the disjointness set
        if offset != 0
    }
    if platform_streams & set(tapes.values()):
        raise FitError("a stage-2 per-decade stream collides with ah.gen.spine's own ladder")

    ladder = {
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
                np.random.PCG64(
                    base_seed + STAGE2_LAYER_OFFSETS["policydev"] + SPINE2_ATTEMPT_STRIDE * a
                )
            ).random(8)
        )
        for a in range(MAX_ATTEMPTS_PER_DECADE)
    }
    if ladder & attempts:
        raise FitError("an attempt-strided policydev stream collides with the platform ladder")
    return {
        "n_streams_checked": len(tapes) + len(platform_streams) + len(ladder) + len(attempts),
        "per_decade_streams_distinct": True,
        "disjoint_from_platform_layer_offsets": True,
        "attempt_ladder_disjoint_from_platform_ladder": True,
        "new_offset_this_campaign": {"policydev": POLICYDEV_OFFSET},
        "offsets": dict(sorted(STAGE2_LAYER_OFFSETS.items())),
        "spine2_attempt_stride": SPINE2_ATTEMPT_STRIDE,
        "platform_seed_stride": PLATFORM_SEED_STRIDE,
    }


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def _f(x: Any) -> float | None:
    """A JSON-safe float: ``None`` where the value is not finite."""
    value = float(x)
    return value if math.isfinite(value) else None


def _round(obj: Any, digits: int = 12) -> Any:
    """Round every float in a nested structure, for a byte-stable artifact."""
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _round(v, digits) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_round(v, digits) for v in obj]
    if isinstance(obj, np.floating):
        return _round(float(obj), digits)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return _round(obj.tolist(), digits)
    return obj


def _usrec_cycle(panel: Panel) -> np.ndarray:
    """The WP2.6 cycle contract on the panel: ``1 - 2*USREC``."""
    _catalog, access = _catalog_access(_REPO_ROOT / "data", CAMPAIGN_VINTAGE_ID)
    frame = _read_series(access, USREC_SERIES_ID)
    if frame is None:
        raise FitError("the coupling needs fred.USREC from the campaign vintage")
    usrec = _monthly(frame).reindex(panel.dates).to_numpy(dtype=np.float64)
    return 1.0 - 2.0 * usrec


def cycle_by_axis(cycle: np.ndarray, expanding: np.ndarray) -> np.ndarray:
    """``[c_contracting, c_expanding]`` -- the panel mean of ``c`` inside each axis.

    ``spine_v2_fit.cycle_by_season``'s construction, moved from the four seasons
    to the two growth axes because the design document's ``c_t`` is a function of
    the growth axis alone. Averaged over the panel's own axis shares this
    reproduces ``mean(c)`` exactly, which is what keeps the generated inflation
    level where the fitted equation put it.
    """
    axis = np.asarray(expanding, dtype=bool)
    out = np.empty(2, dtype=np.float64)
    for i, mask in enumerate((~axis, axis)):
        out[i] = float(np.clip(cycle[mask].mean(), -1.0, 1.0)) if mask.any() else 0.0
    return out


# --------------------------------------------------------------------------- #
# BLOCK 2 -- the inflation gap: the arrow O1 needs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InflationBlock:
    """``x_{t+1} = k0 + a x_t + lam_x (c_{t-m} - cbar) + sig_x e_t``, as fitted."""

    intercept: float
    persistence: float
    lam_x: float
    lam_x_se: float
    cbar: float
    innovation_sd: float
    lag_months: int
    loglik: float
    loglik_no_coupling: float
    n_rows: int
    cycle_input: str
    profile: dict[int, dict[str, float]]

    @property
    def lr_statistic(self) -> float:
        return 2.0 * (self.loglik - self.loglik_no_coupling)

    @property
    def stationary_sd(self) -> float:
        return float(
            self.innovation_sd / math.sqrt(max(1.0 - self.persistence * self.persistence, 1e-12))
        )

    @property
    def unconditional_mean(self) -> float:
        gap = 1.0 - self.persistence
        return float(self.intercept / gap) if abs(gap) > 1e-12 else 0.0


def fit_inflation_block(
    x_gap: np.ndarray, cycle: np.ndarray, observed: np.ndarray, cycle_input: str
) -> InflationBlock:
    """The inflation block, by the SEALED lag-selection rule.

    Ruling `SQ9` seals the RULE and the GRID, never a value: maximum likelihood
    on the declared 25-lag grid (0 to 24 months), one parameter at every lag, a
    common sample so the likelihoods are comparable, the highest likelihood wins,
    and the whole profile is published beside whatever it picks. Both the grid
    and the estimator are ``scripts/stage2_anchors``'s own, imported -- so the
    fit that goes into the engine and the fit the anchor was cut from are the
    same code on the same equation.
    """
    months = _m3_month_index(x_gap, observed)
    profile: dict[int, dict[str, float]] = {}
    for lag in M3_LAG_GRID_MONTHS:
        y, x_t, c_lag = _m3_rows(x_gap, cycle, months, lag)
        profile[int(lag)] = _m3_fit(y, x_t, c_lag, float(c_lag.mean()))
    selected = int(max(profile, key=lambda k: profile[k]["loglik"]))
    best = profile[selected]
    _y, _x, c_lag = _m3_rows(x_gap, cycle, months, selected)
    return InflationBlock(
        intercept=float(best["intercept"]),
        persistence=float(best["persistence_a"]),
        lam_x=float(best["lam_x"]),
        lam_x_se=float(best["standard_error_lam_x"]),
        cbar=float(c_lag.mean()),
        innovation_sd=float(best["residual_sd"]),
        lag_months=selected,
        loglik=float(best["loglik"]),
        loglik_no_coupling=float(best["loglik_no_coupling"]),
        n_rows=int(best["n_rows"]),
        cycle_input=cycle_input,
        profile=profile,
    )


# --------------------------------------------------------------------------- #
# BLOCK 3 -- the policy deviation: it stops being noise
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PolicyBlock:
    """``u_{t+1} = u0 + phi_u u_t + lam_u x_t + lam_c c_t + sig_u e_t``, as fitted."""

    intercept: float
    persistence: float
    lam_u: float
    lam_c: float
    standard_errors: dict[str, float]
    innovation_sd: float
    loglik: float
    loglik_no_loadings: float
    n_rows: int

    @property
    def lr_statistic(self) -> float:
        return 2.0 * (self.loglik - self.loglik_no_loadings)

    @property
    def stationary_sd(self) -> float:
        return float(
            self.innovation_sd / math.sqrt(max(1.0 - self.persistence * self.persistence, 1e-12))
        )


def fit_policy_block(u_hat: np.ndarray, x_gap: np.ndarray, cycle: np.ndarray) -> PolicyBlock:
    """The policy block and its no-loadings restriction, both by ML.

    Least squares is the Gaussian maximum likelihood here, so the restriction
    ``lam_u = lam_c = 0`` is the same equation with two columns removed and the
    likelihood ratio is a function of the two residual sums of squares. ``u`` is
    OBSERVED on the panel (it is ``build_panel``'s standardised policy deviation,
    the residual of L1's own Taylor anchor), which is why this block adds nothing
    to the cross-block information and everything to what the simulator can do.
    """
    y = u_hat[1:]
    design = np.column_stack([np.ones(y.size), u_hat[:-1], x_gap[:-1], cycle[:-1]])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    rss = float(resid @ resid)
    restricted = design[:, :2]
    beta0, *_ = np.linalg.lstsq(restricted, y, rcond=None)
    resid0 = y - restricted @ beta0
    rss0 = float(resid0 @ resid0)
    n = int(y.size)
    dof = max(n - design.shape[1], 1)
    covariance = (rss / dof) * np.linalg.inv(design.T @ design)
    errors = np.sqrt(np.abs(np.diag(covariance)))
    names = ("intercept", "persistence", "lam_u", "lam_c")
    return PolicyBlock(
        intercept=float(beta[0]),
        persistence=float(beta[1]),
        lam_u=float(beta[2]),
        lam_c=float(beta[3]),
        standard_errors={k: float(v) for k, v in zip(names, errors, strict=True)},
        innovation_sd=math.sqrt(rss / n),
        loglik=-0.5 * n * (math.log(2.0 * math.pi) + math.log(rss / n) + 1.0),
        loglik_no_loadings=-0.5 * n * (math.log(2.0 * math.pi) + math.log(rss0 / n) + 1.0),
        n_rows=n,
    )


# --------------------------------------------------------------------------- #
# BLOCK 4 -- the curve: it reads the rule
# --------------------------------------------------------------------------- #

#: The stage-2 curve equation's parameter names, in design-matrix column order.
#: ``_m4_design``'s own labels, restated nowhere -- imported through the design.
CURVE_LABELS: tuple[str, ...] = ("intercept", "c_i_policy_rule", "c_x_inflation_gap", "C", "E", "K")
#: The three columns the season block is made of.
SEASON_KEYS: tuple[str, ...] = ("C", "E", "K")


@dataclass(frozen=True)
class Stage2Curve:
    """The stage-2 curve process, as fitted and as the simulator runs it."""

    beta: np.ndarray  # (6,) on the CENTRED design, CURVE_LABELS order
    se: np.ndarray  # (6,)
    correlation: np.ndarray  # (6, 6) of the coefficient estimates
    centers: np.ndarray  # (5,) means of the five non-intercept columns
    rho: float
    rho_se: float
    innovation_sd: float
    loglik: float
    n_months: int
    r_squared: float
    statistics: dict[str, Any]

    @property
    def coefficients(self) -> dict[str, float]:
        return {k: float(v) for k, v in zip(CURVE_LABELS, self.beta, strict=True)}

    @property
    def standard_errors(self) -> dict[str, float]:
        return {k: float(v) for k, v in zip(CURVE_LABELS, self.se, strict=True)}

    @property
    def residual_stationary_sd(self) -> float:
        return float(self.innovation_sd / math.sqrt(max(1.0 - self.rho * self.rho, 1e-12)))

    def season_term(self, expanding: bool, age: int) -> float:
        """The centred season contribution to ``slope_t`` -- week 3's, unchanged."""
        log_age = math.log(max(int(age), 1))
        raw = np.array(
            [
                0.0 if expanding else 1.0,
                log_age if expanding else 0.0,
                0.0 if expanding else log_age,
            ]
        )
        return float((raw - self.centers[2:5]) @ self.beta[3:6])


def _curve_errors(
    y: np.ndarray, x: np.ndarray, beta: np.ndarray, rho: float, sigma: float
) -> tuple[np.ndarray, float, np.ndarray]:
    """``(se, rho_se, correlation)`` from the exact likelihood's Hessian.

    Central-difference Hessian of the negative exact AR(1) log-likelihood over
    ``(beta, rho, log sigma)`` at the optimum -- week 3's estimator for the same
    object, on a six-column design instead of five. The correlation matrix of the
    coefficient estimates is returned with it, because on a panel with twelve
    recessions the correlation structure is as much of the answer as the
    standard errors are.
    """
    weights = np.ones(y.size, dtype=np.float64)

    def negative(theta: np.ndarray) -> float:
        return -ar1_loglik(
            y, x, theta[: x.shape[1]], float(theta[-2]), math.exp(float(theta[-1])), weights
        )

    theta = np.concatenate([beta, [rho, math.log(sigma)]])
    hessian = _numerical_hessian(negative, theta)
    covariance = np.linalg.inv(hessian)
    errors = np.sqrt(np.abs(np.diag(covariance)))
    k = x.shape[1]
    block = covariance[:k, :k]
    scale = np.sqrt(np.abs(np.diag(block)))
    scale[scale == 0.0] = 1.0
    correlation = block / np.outer(scale, scale)
    return errors[:k], float(errors[-2]), correlation


def fit_stage2_curve(panel: Panel, states: dict[str, np.ndarray]) -> Stage2Curve:
    """The curve block: M4's equation, fitted by exact AR(1) maximum likelihood.

    The design matrix and the statistics come from ``stage2_anchors`` -- the same
    two functions that produced the sealed P2 anchor -- so the generated side and
    the historical side are decomposed by one piece of code with only the input
    array differing. That is P2's fourth anti-test obligation, discharged
    structurally rather than argued.
    """
    design = _m4_design(panel, states)
    y = np.asarray(design["y"], dtype=np.float64)
    x = np.asarray(design["x"], dtype=np.float64)
    is_start = np.zeros(y.size, dtype=bool)
    is_start[0] = True
    stats = _m4_statistics(y, x, is_start)
    beta = np.asarray(stats["beta"], dtype=np.float64)
    errors, rho_se, correlation = _curve_errors(
        y, x, beta, float(stats["rho"]), float(stats["innovation_sd_pp"])
    )
    return Stage2Curve(
        beta=beta,
        se=errors,
        correlation=correlation,
        centers=np.asarray(design["centers"], dtype=np.float64),
        rho=float(stats["rho"]),
        rho_se=rho_se,
        innovation_sd=float(stats["innovation_sd_pp"]),
        loglik=float(stats["loglik"]),
        n_months=int(y.size),
        r_squared=float(stats["r_squared_realised"]),
        statistics=stats,
    )


def ar1_block_fit(y: np.ndarray, x: np.ndarray) -> dict[str, Any]:
    """``(beta, rho, sigma, loglik)`` for an arbitrary column set, same estimator.

    ``stage2_anchors._m4_statistics`` is hard-wired to the six-column stage-2
    design because that is the object the sealed anchor is cut from. The nested
    restrictions and the ``u_hat`` disclosure need the identical estimator on a
    different number of columns, so they call the anchors' own profile and
    maximiser directly rather than a second implementation of them.
    """
    is_start = np.zeros(y.size, dtype=bool)
    is_start[0] = True
    rho = _maximise_rho_blocks(y, x, is_start)
    beta, sigma, loglik = _profile_blocks(y, x, rho, is_start)
    return {"beta": beta, "rho": float(rho), "sigma": float(sigma), "loglik": float(loglik)}


def curve_restrictions(panel: Panel, states: dict[str, np.ndarray]) -> dict[str, Any]:
    """Every "no coupling" restriction on the curve, as a likelihood-ratio test.

    Each is the same equation with columns removed, fitted by the same estimator,
    so each is a test rather than an argument -- the property the design document
    claims for the joint fit and the only thing it claims that is not already a
    property of the data.
    """
    design = _m4_design(panel, states)
    y = np.asarray(design["y"], dtype=np.float64)
    x = np.asarray(design["x"], dtype=np.float64)
    full = ar1_block_fit(y, x)
    arms = {
        "no_inflation_gap": ([2], 1),
        "no_season_block": ([3, 4, 5], 3),
        "no_policy_rule": ([1], 1),
        "no_economics_at_all": ([1, 2, 3, 4, 5], 5),
    }
    out: dict[str, Any] = {}
    for name, (columns, df) in arms.items():
        keep = [j for j in range(x.shape[1]) if j not in columns]
        restricted = ar1_block_fit(y, x[:, keep])
        statistic = 2.0 * (float(full["loglik"]) - float(restricted["loglik"]))
        out[name] = {
            "columns_zeroed": [CURVE_LABELS[j] for j in columns],
            "degrees_of_freedom": df,
            "lr_statistic": _f(statistic),
            "p_value": _f(_chi2_sf_df1(statistic) if df == 1 else chi2_sf_df3(statistic))
            if df in (1, 3)
            else None,
            "restricted_loglik": _f(restricted["loglik"]),
        }
    out["full_loglik"] = _f(full["loglik"])
    return out


# --------------------------------------------------------------------------- #
# the fitted system
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CoupledSystem:
    """Everything the simulator needs: four blocks and one set of constants."""

    engine: FittedEngine
    inflation: InflationBlock
    policy: PolicyBlock
    curve: Stage2Curve
    axis_cycle: np.ndarray  # [c_contracting, c_expanding]
    phi_pi: float
    phi_c: float
    curve_lag_months: int
    opening_age_expanding: np.ndarray
    opening_age_contracting: np.ndarray
    hazard_loglik: float
    cycle_input: str = PRIMARY_CYCLE_INPUT
    #: ``stage2`` -- the curve reads the rule-implied rate and the inflation gap.
    #: ``week3`` -- the curve reads L1's policy DEVIATION, week 3's equation,
    #: fitted by the same estimator. The second exists only for the attribution
    #: table: it is the arm that says whether the coupling or the curve moved a
    #: bar, and it is never a candidate engine.
    curve_mode: str = "stage2"
    legacy_curve: CurveModel | None = None

    @property
    def joint_loglik(self) -> float:
        return float(
            self.hazard_loglik + self.inflation.loglik + self.policy.loglik + self.curve.loglik
        )

    @property
    def residual_rho(self) -> float:
        if self.curve_mode == "week3" and self.legacy_curve is not None:
            return float(self.legacy_curve.rho)
        return float(self.curve.rho)

    @property
    def residual_innovation_sd(self) -> float:
        if self.curve_mode == "week3" and self.legacy_curve is not None:
            return float(self.legacy_curve.innovation_sd)
        return float(self.curve.innovation_sd)

    def cycle_value(self, expanding: bool) -> float:
        if self.cycle_input == "plus_minus_one":
            return 1.0 if expanding else -1.0
        return float(self.axis_cycle[1] if expanding else self.axis_cycle[0])


def build_system(
    panel: Panel,
    hazard: dict[str, Any],
    cells: np.ndarray,
    lag: int,
    inflation: InflationBlock,
    policy: PolicyBlock,
    curve: Stage2Curve,
    states: dict[str, np.ndarray],
    cycle: np.ndarray,
) -> CoupledSystem:
    """Bundle the four fitted blocks into the object the simulator consumes."""
    stag = measure_stag_spell_rate(panel, cells)
    engine = build_engine(panel, hazard, cells, lag, stag)
    expanding = growth_axis(panel.labels)
    age = spell_age(expanding)
    start = int(first_spell_end(expanding) + 1)
    return CoupledSystem(
        engine=engine,
        inflation=inflation,
        policy=policy,
        curve=curve,
        axis_cycle=cycle_by_axis(cycle, expanding),
        phi_pi=float(states["phi_pi"][0]),
        phi_c=float(states["phi_c"][0]),
        curve_lag_months=int(lag),
        opening_age_expanding=age[start:][expanding[start:]].astype(np.int64),
        opening_age_contracting=age[start:][~expanding[start:]].astype(np.int64),
        hazard_loglik=float(hazard["loglik"]),
    )


# --------------------------------------------------------------------------- #
# the simulator: the coupled loop
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Stage2Decade(SimulatedDecade):
    """A generated decade, plus the four series stage 2's own bars are cut from."""

    x_gap: np.ndarray
    i_rule: np.ndarray
    policy_dev: np.ndarray
    season_component: np.ndarray


def run_chain_coupled(
    system: CoupledSystem,
    states: np.ndarray,
    infl_innovations: np.ndarray,
    policy_innovations: np.ndarray,
    residual: np.ndarray,
    rng: np.random.Generator,
    rng_age: np.random.Generator,
) -> dict[str, np.ndarray]:
    """The coupled loop over one decade -- every arrow closed, one month at a time.

    The order inside a month is forced by the equations and there is no
    simultaneity anywhere in it:

    1. the season is already fixed (drawn last month from the hazard, which read
       ``slope`` at the curve's own lead);
    2. ``x_t`` is already fixed (computed last month from ``c_{t-m}``, ``m`` >= 0
       months old);
    3. inflation ``pi_t = pi*_t + x_t`` sets the hot dial, so the season code is
       complete;
    4. the rule-implied rate ``i_t`` reads ``x_t`` and ``c_t``; the curve reads
       ``i_t``, ``x_t`` and the season term;
    5. the hazard draws next month's growth axis from ``slope`` at the lead;
    6. ``x_{t+1}`` is computed from ``c_{t-m}``, and ``u_{t+1}`` from ``x_t``
       and ``c_t``.

    ``residual`` is ``months + lag`` long: its head is the decade's pre-history,
    drawn on the same tape, so the lagged curve reading for the decade's first
    ``lag`` months is a real earlier month rather than a value invented at the
    edge. The pre-history carries the season term and the economic terms at their
    unconditional means, which is zero by the centring of the design.
    """
    months = int(states.shape[0])
    lag = int(system.curve_lag_months)
    m = int(system.inflation.lag_months)
    if residual.shape[0] != months + lag:
        raise FitError(f"residual must carry {months + lag} months (lag {lag})")

    engine = system.engine
    curve = system.curve
    legacy = system.legacy_curve
    week3_mode = system.curve_mode == "week3"
    if week3_mode and legacy is None:
        raise FitError("curve_mode 'week3' needs the legacy curve it is meant to run")
    pi_star = states[:, 0]
    r_star = states[:, 1]
    v_dd = trailing_drawdown(states[:, 3], V_DRAWDOWN_WINDOW_MONTHS)
    dummy = (v_dd <= engine.v_threshold).astype(np.float64)

    intercept = float(legacy.intercept) if week3_mode and legacy else float(curve.beta[0])
    slope_full = np.empty(months + lag, dtype=np.float64)
    slope_full[:lag] = intercept + residual[:lag]

    expanding = np.empty(months, dtype=bool)
    season = np.empty(months, dtype=np.int64)
    z = np.empty((months, 4), dtype=np.float64)
    x_gap = np.empty(months, dtype=np.float64)
    i_rule = np.empty(months, dtype=np.float64)
    policy_dev = np.empty(months, dtype=np.float64)
    season_component = np.empty(months, dtype=np.float64)
    yoy = np.empty(months, dtype=np.float64)

    is_expanding = bool(rng.random() < engine.initial_expanding_rate)
    pool = system.opening_age_expanding if is_expanding else system.opening_age_contracting
    age = int(pool[int(rng_age.integers(0, pool.size))])
    # the decade opens inside a spell of the drawn age, so the months BEFORE it
    # carried the same growth axis -- which is what supplies c_{t-m} for the
    # first m months rather than an invented value
    opening_cycle = system.cycle_value(is_expanding)

    x = system.inflation.unconditional_mean + float(infl_innovations[0])
    u = float(policy_innovations[0])
    dwell = 1
    previous = -1
    for t in range(months):
        expanding[t] = is_expanding
        x_gap[t] = x
        policy_dev[t] = u
        yoy[t] = pi_star[t] + x
        season[t] = (int(is_expanding) << 1) | int(yoy[t] > engine.era_threshold_pp)
        dwell = dwell + 1 if int(season[t]) == previous else 1
        previous = int(season[t])

        c_now = system.cycle_value(is_expanding)
        i_rule[t] = r_star[t] + pi_star[t] + system.phi_pi * x + system.phi_c * c_now
        if week3_mode and legacy is not None:
            season_component[t] = legacy.season_term(is_expanding, age)
            slope_full[lag + t] = (
                legacy.intercept
                + legacy.u_hat_loading * u
                + season_component[t]
                + residual[lag + t]
            )
        else:
            season_component[t] = curve.season_term(is_expanding, age)
            slope_full[lag + t] = (
                curve.beta[0]
                + curve.beta[1] * (i_rule[t] - curve.centers[0])
                + curve.beta[2] * (x - curve.centers[1])
                + season_component[t]
                + residual[lag + t]
            )

        z_raw = np.array(
            [slope_full[t], states[t, 4], pi_star[t] - engine.pi_target, dummy[t]],
            dtype=np.float64,
        )
        z[t] = (z_raw - engine.z_mean) / engine.z_sd
        flipped = rng.random() < hazard_probability(engine.beta, int(season[t]), dwell, z[t])

        if t + 1 < months:
            c_lag = system.cycle_value(bool(expanding[t - m])) if t - m >= 0 else opening_cycle
            x = (
                system.inflation.intercept
                + system.inflation.persistence * x
                + system.inflation.lam_x * (c_lag - system.inflation.cbar)
                + float(infl_innovations[t + 1])
            )
            u = (
                system.policy.intercept
                + system.policy.persistence * u
                + system.policy.lam_u * x_gap[t]
                + system.policy.lam_c * c_now
                + float(policy_innovations[t + 1])
            )
        if flipped:
            is_expanding = not is_expanding
            age = 1
        else:
            age += 1
    return {
        "season": season,
        "expanding": expanding,
        "z": z,
        "slope_full": slope_full,
        "yoy": yoy,
        "x_gap": x_gap,
        "i_rule": i_rule,
        "policy_dev": policy_dev,
        "season_component": season_component,
    }


def _stationary_start(
    rng: np.random.Generator, persistence: float, sigma: float, n: int
) -> np.ndarray:
    """``n`` draws: the first from the stationary law, the rest innovations.

    The same tape shape ``spine_v2_fit.ar1_path`` consumes, so the innovation
    stream is used exactly as week 3 used it and the two engines' tapes differ
    only in what the draws are fed into.
    """
    stationary_sd = sigma / math.sqrt(max(1.0 - persistence * persistence, 1e-12))
    out = np.empty(n, dtype=np.float64)
    out[0] = rng.normal(0.0, stationary_sd)
    out[1:] = rng.normal(0.0, sigma, size=n - 1)
    return out


def simulate_batch_coupled(
    system: CoupledSystem,
    climate: Any,
    *,
    n_decades: int,
    seed: int,
    months: int = DECADE_MONTHS,
    premise: Any | None = None,
) -> tuple[list[Stage2Decade], dict[str, int]]:
    """``n_decades`` decades of the coupled system. No flesh, no block sampler.

    The two-pass joinery is week 2's and week 3's, unchanged: pass one runs the
    climate under a neutral cycle, the coupled chain reads it, and pass two
    re-runs the SAME seed with the chain's own ``c_t`` forcing the credit-gap
    norm, after which the chain is re-run on pass two's states from the SAME
    re-opened streams -- so the accepted decade is a fixed point of one tape
    rather than a splice of two.
    """
    kept: list[Stage2Decade] = []
    tally: dict[str, int] = {}
    attempt = 0
    budget = MAX_ATTEMPTS_PER_DECADE * n_decades
    lag = int(system.curve_lag_months)
    engine = system.engine
    while len(kept) < n_decades and attempt < budget:
        step = SPINE2_ATTEMPT_STRIDE * attempt
        l1_seed = seed + CLIMATE_OFFSET + step
        sim1 = simulate_decades(climate, 1, seed=l1_seed, months=months)

        def _stream(name: str, offset_step: int = step) -> np.random.Generator:
            return np.random.Generator(
                np.random.PCG64(seed + STAGE2_LAYER_OFFSETS[name] + offset_step)
            )

        residual = ar1_path(
            _stream("slope"), system.residual_rho, system.residual_innovation_sd, months + lag
        )
        infl = _stationary_start(
            _stream("inflnoise"),
            system.inflation.persistence,
            system.inflation.innovation_sd,
            months,
        )
        policy = _stationary_start(
            _stream("policydev"),
            system.policy.persistence,
            system.policy.innovation_sd,
            months,
        )

        first = run_chain_coupled(
            system, sim1.states[0], infl, policy, residual, _stream("seasons"), _stream("openage")
        )
        cycle = engine.season_cycle[first["season"]].reshape(1, -1)
        sim2 = simulate_decades(climate, 1, seed=l1_seed, months=months, cycle=cycle)
        run = run_chain_coupled(
            system, sim2.states[0], infl, policy, residual, _stream("seasons"), _stream("openage")
        )
        labels = emit_labels(run["season"], run["yoy"], engine.stag_spell_rate, _stream("labels"))

        reason = (
            None
            if premise is None
            else reject_reason(
                premise, sim2.states[0], run["expanding"], float(sim2.params["mu_pi"][0])
            )
        )
        if reason is None:
            kept.append(
                Stage2Decade(
                    season=run["season"],
                    labels=labels,
                    expanding=run["expanding"],
                    yoy=run["yoy"],
                    slope=run["slope_full"][lag:],
                    z=run["z"],
                    states=sim2.states[0],
                    attempts=attempt,
                    x_gap=run["x_gap"],
                    i_rule=run["i_rule"],
                    policy_dev=run["policy_dev"],
                    season_component=run["season_component"],
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


# --------------------------------------------------------------------------- #
# the verification loop -- SEALED judges, imported and unmodified
# --------------------------------------------------------------------------- #


def judge_batch(
    decades: list[Stage2Decade],
    system: CoupledSystem,
    sealed: dict[str, Any],
    v2_sealed: dict[str, Any],
) -> dict[str, Any]:
    """The eight pre-flesh bars, by the sealed judges. Nothing is re-implemented."""
    v2_batch = V2Batch(tuple(to_decade(d) for d in decades))
    verdicts: dict[str, Any] = dict(judge_carried_v2(v2_batch, v2_sealed))
    p1_batch = P1Batch(tuple(P1Decade(labels=d.labels, yoy=d.yoy) for d in v2_batch.decades))
    verdicts["P1"] = judge_p1(p1_batch, sealed)
    components, residual_sd = p2_components(decades, system)
    verdicts["P2"] = judge_p2(components, residual_sd, sealed)
    for code in WEEK_C_BARS:
        verdicts.pop(code, None)
    return verdicts


def p2_components(
    decades: list[Stage2Decade], system: CoupledSystem
) -> tuple[dict[str, float], float]:
    """The generated curve's component standard deviations, pooled over the batch.

    The exam's own construction, restated nowhere: "the economic components are
    measured on the batch; the residual standard deviation is a model parameter".
    ``u_hat`` is absent because under the primary curve arm the policy deviation
    does not enter the curve at all -- so the generated decomposition has an
    empty exogenous block, exactly as history's does. On the ``week3`` curve arm
    it is the only non-season component, which is week 3's own accounting and
    the reason that engine scored 2.2%.
    """
    curve = system.curve
    season = np.concatenate([d.season_component for d in decades])
    if system.curve_mode == "week3" and system.legacy_curve is not None:
        legacy = system.legacy_curve
        u = np.concatenate([d.policy_dev for d in decades])
        return (
            {
                "u_hat": float(abs(legacy.u_hat_loading) * np.std(u)),
                "season_term": float(np.std(season)),
            },
            float(legacy.innovation_sd / math.sqrt(max(1.0 - legacy.rho * legacy.rho, 1e-12))),
        )
    i_rule = np.concatenate([d.i_rule for d in decades])
    x_gap = np.concatenate([d.x_gap for d in decades])
    return (
        {
            "policy_rule": float(abs(curve.beta[1]) * np.std(i_rule)),
            "inflation_gap": float(abs(curve.beta[2]) * np.std(x_gap)),
            "season_term": float(np.std(season)),
        },
        curve.residual_stationary_sd,
    )


def bar_readings(verdicts: dict[str, Any]) -> list[dict[str, Any]]:
    """One flat row per bar, in exam order: value, band or floor, verdict."""
    rows: list[dict[str, Any]] = []
    for code in PRE_FLESH_BARS:
        verdict = verdicts.get(code)
        if verdict is None:
            rows.append({"bar": code, "measured": False})
            continue
        row: dict[str, Any] = {
            "bar": code,
            "measured": True,
            "pass": bool(verdict["pass"]),
            "value": _f(verdict["value"]),
        }
        if "band" in verdict:
            row["band"] = [_f(v) for v in verdict["band"]]
        if "threshold" in verdict:
            row["threshold"] = _f(verdict["threshold"])
        if code == "P1":
            row["per_move_type"] = {
                move: {
                    "departure": _f(block["departure"]),
                    "threshold": _f(block["threshold"]),
                    "clockwise_fraction": _f(block["clockwise_fraction"]),
                    "own_null": _f(block["own_null"]),
                    "n_transitions": int(block["n_transitions"]),
                    "pass": bool(block["pass"]),
                }
                for move, block in verdict["per_move_type"].items()
            }
        if code == "P2":
            row["failure_side"] = verdict["failure_side"]
            row["decomposition"] = verdict["decomposition"]
        rows.append(row)
    for code in WEEK_C_BARS:
        rows.append(
            {
                "bar": code,
                "measured": False,
                "why": (
                    "needs the flesh (A1, A2), the institutional twin's over-commitment grid "
                    "(R1) or an ensemble and the panel source (R2). Week C, not week A"
                ),
            }
        )
    return rows


def batch_diagnostics(
    decades: list[Stage2Decade],
    system: CoupledSystem,
    panel: Panel,
    cycle: np.ndarray,
    states: dict[str, np.ndarray],
) -> dict[str, Any]:
    """What the coupling did to the generated world, against history's own numbers."""
    x_gap = np.concatenate([d.x_gap for d in decades])
    yoy = np.concatenate([d.yoy for d in decades])
    slope = np.concatenate([d.slope for d in decades])
    expanding = np.concatenate([d.expanding for d in decades])
    i_rule = np.concatenate([d.i_rule for d in decades])
    era = float(system.engine.era_threshold_pp)

    # the phase relation in its rawest form: the mean inflation gap by how long
    # the current growth spell has run, which is what lam_x is supposed to bend
    ages = np.concatenate([spell_age(d.expanding) for d in decades])
    buckets: dict[str, Any] = {}
    for name, lo, hi in (
        ("months_1_12", 1, 12),
        ("months_13_36", 13, 36),
        ("months_37_plus", 37, 10**6),
    ):
        mask = (ages >= lo) & (ages <= hi)
        buckets[name] = {
            "expanding_mean_x_gap_pp": _f(np.mean(x_gap[mask & expanding]))
            if (mask & expanding).any()
            else None,
            "contracting_mean_x_gap_pp": _f(np.mean(x_gap[mask & ~expanding]))
            if (mask & ~expanding).any()
            else None,
        }

    panel_defined = ~np.isnan(panel.yoy)
    return {
        "generated": {
            "months": int(x_gap.size),
            "x_gap_mean_pp": _f(np.mean(x_gap)),
            "x_gap_sd_pp": _f(np.std(x_gap)),
            "yoy_mean_pp": _f(np.mean(yoy)),
            "hot_share": _f(np.mean(yoy > era)),
            "expanding_share": _f(np.mean(expanding)),
            "slope_sd_pp": _f(np.std(slope)),
            "inverted_share": _f(np.mean(slope < 0.0)),
            "i_rule_sd_pp": _f(np.std(i_rule)),
            "mean_x_gap_expanding_pp": _f(np.mean(x_gap[expanding])),
            "mean_x_gap_contracting_pp": _f(np.mean(x_gap[~expanding])),
        },
        "history": {
            "months": int(panel_defined.sum()),
            "x_gap_sd_pp": _f(
                np.std(
                    panel.yoy[panel_defined]
                    - panel.z_raw[panel_defined, 2]
                    - panel.diagnostics["pi_target"]
                )
            ),
            "yoy_mean_pp": _f(np.nanmean(panel.yoy)),
            "hot_share": _f(np.mean(panel.yoy[panel_defined] > era)),
            "expanding_share": _f(np.mean(growth_axis(panel.labels))),
            "slope_sd_pp": _f(np.std(panel.slope)),
            "inverted_share": _f(np.mean(panel.slope < 0.0)),
            "i_rule_sd_pp": _f(np.std(states["i_rule"])),
            "usrec_cycle_mean": _f(np.mean(cycle)),
        },
        "dispersion_ratios_generated_over_history": {
            "i_rule": _f(float(np.std(i_rule)) / float(np.std(states["i_rule"]))),
            "slope": _f(float(np.std(slope)) / float(np.std(panel.slope))),
            "x_gap": _f(
                float(np.std(x_gap))
                / float(
                    np.std(
                        panel.yoy[panel_defined]
                        - panel.z_raw[panel_defined, 2]
                        - panel.diagnostics["pi_target"]
                    )
                )
            ),
            "why_it_is_here": (
                "P2 is a SHARE, so it moves with the numerator's dispersion as much as with "
                "the coefficients. If the generated rule-implied rate is more dispersed than "
                "history's, the economic share rises without any coupling changing -- and "
                "these three ratios are how a reader tells the two apart"
            ),
        },
        "inflation_gap_by_growth_spell_age": buckets,
        "note": (
            "the last block is the coupling's own signature: if inflation follows growth, "
            "the gap should climb the longer an expansion has run and fall the longer a "
            "contraction has. It is a diagnostic, never a bar"
        ),
    }


# --------------------------------------------------------------------------- #
# identifiability
# --------------------------------------------------------------------------- #


def identifiability(system: CoupledSystem, hazard: dict[str, Any]) -> dict[str, Any]:
    """Standard errors, t-ratios, and which coefficients are not identified.

    A coefficient is called **unidentified** here when its 95% interval spans
    both signs -- applied uniformly and without exception, and reported for every
    coefficient rather than only for the ones that survive it.

    **Exactly one of them stops the campaign, and which one was pre-declared.**
    The design document's Cheap Exit A names ``lam_x`` and nothing else. A
    coefficient that comes back unidentified is therefore a FINDING, reported in
    full; only ``lam_x`` is a blocker. Deciding after the fact that some other
    coefficient was the real stop condition would be a goalpost move in the
    direction this campaign has twice refused to move in.
    """
    entries: dict[str, dict[str, Any]] = {}

    def _add(name: str, value: float, se: float, load_bearing: bool) -> None:
        span = bool(se > 0.0 and abs(value) < IDENTIFIABILITY_Z * se)
        entries[name] = {
            "estimate": _f(value),
            "standard_error": _f(se),
            "t_ratio": _f(value / se) if se > 0.0 else None,
            "ci95": [_f(value - IDENTIFIABILITY_Z * se), _f(value + IDENTIFIABILITY_Z * se)],
            "interval_spans_both_signs": span,
            "load_bearing": load_bearing,
        }

    _add("lam_x", system.inflation.lam_x, system.inflation.lam_x_se, True)
    _add("lam_u", system.policy.lam_u, system.policy.standard_errors["lam_u"], True)
    _add("lam_c", system.policy.lam_c, system.policy.standard_errors["lam_c"], True)
    coefficients = system.curve.coefficients
    errors = system.curve.standard_errors
    for name in CURVE_LABELS[1:]:
        _add(name, coefficients[name], errors[name], name in LOAD_BEARING)
    _add(
        TRANSMISSION_KEY,
        float(hazard["coefficients"][TRANSMISSION_KEY]),
        float(hazard["standard_errors"][TRANSMISSION_KEY]),
        True,
    )

    unidentified = sorted(name for name, row in entries.items() if row["interval_spans_both_signs"])
    load_bearing_unidentified = sorted(
        name
        for name, row in entries.items()
        if row["interval_spans_both_signs"] and row["load_bearing"]
    )
    stops = bool(entries[STOP_COEFFICIENT]["interval_spans_both_signs"])
    return {
        "coefficients": entries,
        "stop_coefficient": STOP_COEFFICIENT,
        "stop_condition_triggered": stops,
        "stop_condition": (
            "the design document's Cheap Exit A, pre-declared: 'If lam_x -- inflation's "
            "response to growth -- is not significant on the panel, stop.' It is the only "
            "pre-declared identifiability stop in this campaign and no other coefficient "
            "was allowed to acquire one after the estimates were visible"
        ),
        "curve_block_correlation": {
            "labels": list(CURVE_LABELS),
            "matrix": _round(system.curve.correlation.tolist()),
            "largest_off_diagonal_abs": _f(
                np.max(np.abs(system.curve.correlation - np.eye(system.curve.correlation.shape[0])))
            ),
        },
        "unidentified": unidentified,
        "load_bearing_unidentified": load_bearing_unidentified,
        "verdict": (
            "IDENTIFIED -- every load-bearing coefficient's 95% interval excludes zero"
            if not load_bearing_unidentified
            else "PARTIALLY IDENTIFIED -- these load-bearing coefficients' 95% intervals "
            "span both signs and their SIZE is not established by this panel: "
            + ", ".join(load_bearing_unidentified)
        ),
        "cross_block_information_is_zero": True,
        "cross_block_note": (
            "the four blocks share no parameters and every path they read is OBSERVED on "
            "the panel, so the joint information matrix is block-diagonal and there are no "
            "cross-block correlations to report. That is a property of the data, not an "
            "achievement of the design -- week 3's own statement, and it applies again. The "
            "correlation structure that DOES exist is inside the curve block, where c_i and "
            "c_x both read the inflation trend, and it is reported above"
        ),
        "definition": (
            "a coefficient is UNIDENTIFIED when its 95% interval spans both signs. The "
            "panel carries 12 completed stagflation spells and 35 growth-axis flips, and "
            "stage 2 adds five parameters to a system already fitted on those events"
        ),
    }


# --------------------------------------------------------------------------- #
# the frontier -- mapped by scaling, never by tuning
# --------------------------------------------------------------------------- #


def attribution(
    system: CoupledSystem,
    legacy: CurveModel,
    climate: Any,
    sealed: dict[str, Any],
    v2_sealed: dict[str, Any],
    *,
    n_decades: int,
) -> dict[str, Any]:
    """Which of the two new arrows moved which bar -- the 2x2, measured.

    Stage 2 turns on two mechanisms at once, and the design document attributes
    ``O1`` to the first of them (§1.1, growth -> inflation) and the curve's
    noisiness to the second (§1.2). A verdict that reported only the fitted point
    could not tell the two apart, and a campaign that has twice stopped at a
    frontier has no business shipping an unattributed pass. So both are switched
    independently, from the same seed:

    * **curve** -- ``stage2`` (the curve reads the rule-implied rate and the
      inflation gap) against ``week3`` (the curve reads L1's policy deviation,
      week 3's equation, refitted by the same estimator);
    * **coupling** -- ``lam_x`` at its fitted value against exactly zero.

    The ``week3`` curve arm is week 3's *equation* inside the stage-2 loop, not
    week 3's engine reproduced bit for bit: it runs on the stage-2 policy
    deviation (which has loadings) rather than on week 2's input-free OU, and its
    tape differs. Week 3's engine itself is on the record and was retro-judged in
    the anchors; this arm exists to isolate an arrow, not to re-measure an engine.
    """
    rows: list[dict[str, Any]] = []
    for curve_mode in ("week3", "stage2"):
        for coupling in (0.0, 1.0):
            arm = replace(
                system,
                curve_mode=curve_mode,
                legacy_curve=legacy,
                inflation=replace(system.inflation, lam_x=system.inflation.lam_x * float(coupling)),
            )
            decades, _tally = simulate_batch_coupled(
                arm, climate, n_decades=n_decades, seed=STAGE2_VERIFY_SEED
            )
            verdicts = judge_batch(decades, arm, sealed, v2_sealed)
            rows.append(
                {
                    "curve": curve_mode,
                    "coupling_multiplier": float(coupling),
                    "bars": {code: bool(verdicts[code]["pass"]) for code in PRE_FLESH_BARS},
                    "n_passing": int(sum(bool(verdicts[code]["pass"]) for code in PRE_FLESH_BARS)),
                    "O1": _f(verdicts["O1"]["value"]),
                    "T1": _f(verdicts["T1"]["value"]),
                    "P2_share": _f(verdicts["P2"]["value"]),
                    "P1_departures": {
                        move: _f(block["departure"])
                        for move, block in verdicts["P1"]["per_move_type"].items()
                    },
                    "generated_slope_sd_pp": _f(np.std(np.concatenate([d.slope for d in decades]))),
                }
            )
    by_key = {(r["curve"], r["coupling_multiplier"]): r for r in rows}
    o1 = {k: float(v["O1"] or 0.0) for k, v in by_key.items()}
    coupling_effect = o1[("stage2", 1.0)] - o1[("stage2", 0.0)]
    curve_effect = o1[("stage2", 0.0)] - o1[("week3", 0.0)]
    return {
        "rows": rows,
        "o1_moved_by_the_coupling": _f(coupling_effect),
        "o1_moved_by_the_curve": _f(curve_effect),
        "reading": (
            "the two numbers above are the whole attribution: how much of O1's move is the "
            "growth -> inflation arrow lam_x, and how much is the curve reading the "
            "rule-implied policy rate. They are read at the same seed on the same tape"
        ),
    }


def scale_coupling(system: CoupledSystem, multiplier: float) -> CoupledSystem:
    """The same system with ``lam_x`` scaled. Nothing is refitted."""
    return replace(
        system,
        inflation=replace(system.inflation, lam_x=system.inflation.lam_x * float(multiplier)),
    )


def scale_loadings(system: CoupledSystem, multiplier: float) -> CoupledSystem:
    """The same system with the curve's three economic loadings scaled together."""
    beta = system.curve.beta.copy()
    beta[1:] *= float(multiplier)
    return replace(system, curve=replace(system.curve, beta=beta))


def frontier(
    system: CoupledSystem,
    climate: Any,
    sealed: dict[str, Any],
    v2_sealed: dict[str, Any],
    *,
    n_decades: int,
    axis: str,
    multipliers: tuple[float, ...],
) -> list[dict[str, Any]]:
    """Re-simulate from the SAME seed at each multiplier and re-judge.

    **This maps the frontier; it does not tune.** The fitted point is the
    verdict; every other row exists to say which bars trade off against which,
    and no row is ever adopted. That is week 2's and week 3's discipline and it
    must hold a third time.
    """
    rows: list[dict[str, Any]] = []
    for multiplier in multipliers:
        scaled = (
            scale_coupling(system, multiplier)
            if axis == "lam_x"
            else scale_loadings(system, multiplier)
        )
        decades, tally = simulate_batch_coupled(
            scaled, climate, n_decades=n_decades, seed=STAGE2_VERIFY_SEED
        )
        verdicts = judge_batch(decades, scaled, sealed, v2_sealed)
        rows.append(
            {
                "axis": axis,
                "multiplier": float(multiplier),
                "attempts": int(tally.get("attempts", 0)),
                "bars": {code: bool(verdicts[code]["pass"]) for code in PRE_FLESH_BARS},
                "n_passing": int(sum(bool(verdicts[code]["pass"]) for code in PRE_FLESH_BARS)),
                "values": {code: _f(verdicts[code]["value"]) for code in PRE_FLESH_BARS},
                "P1_departures": {
                    move: _f(block["departure"])
                    for move, block in verdicts["P1"]["per_move_type"].items()
                },
                "P2_share": _f(verdicts["P2"]["value"]),
                "O1_value": _f(verdicts["O1"]["value"]),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# label stability, on every new coefficient
# --------------------------------------------------------------------------- #


def label_stability(
    panel: Panel, states: dict[str, np.ndarray], lag: int, system: CoupledSystem
) -> dict[str, Any]:
    """Refit the whole system on the nine dial arms; report every coefficient's move.

    The sealed rule: a statistic that moves by more than **its own standard
    error** across arms escalates. It is applied to each of the campaign's new
    coefficients separately, because they do not all depend on the classifier in
    the same way -- and the way they differ is itself the finding (§ the report).
    """
    base_cells = season_cells(panel.labels, panel.yoy, panel.era_threshold_pp)
    base_hazard = fit_arm(base_cells, panel.z_lagged(lag))
    coefficients = system.curve.coefficients
    errors = system.curve.standard_errors
    baselines = {
        "lam_x_usrec": (system.inflation.lam_x, system.inflation.lam_x_se),
        "c_i_policy_rule": (coefficients["c_i_policy_rule"], errors["c_i_policy_rule"]),
        "c_x_inflation_gap": (coefficients["c_x_inflation_gap"], errors["c_x_inflation_gap"]),
        TRANSMISSION_KEY: (
            float(base_hazard["coefficients"][TRANSMISSION_KEY]),
            float(base_hazard["standard_errors"][TRANSMISSION_KEY]),
        ),
    }
    x_gap = states["x_gap"]
    observed = ~np.isnan(panel.yoy)
    base_axis = fit_inflation_block(
        x_gap, 1.0 - 2.0 * (~growth_axis(panel.labels)).astype(np.float64), observed, "grader_axis"
    )
    baselines["lam_x_grader_axis"] = (base_axis.lam_x, base_axis.lam_x_se)

    arms: dict[str, Any] = {}
    for name, d_inf, d_grw in STABILITY_ARMS:
        cells = relabel(panel, d_inf, d_grw)
        labels = _perturbed_labels(panel, d_grw)
        hazard = fit_arm(cells, panel.z_lagged(lag))
        design = _m4_design(panel, states, labels=labels)
        y = np.asarray(design["y"], dtype=np.float64)
        x = np.asarray(design["x"], dtype=np.float64)
        is_start = np.zeros(y.size, dtype=bool)
        is_start[0] = True
        stats = _m4_statistics(y, x, is_start)
        axis_block = fit_inflation_block(
            x_gap, 1.0 - 2.0 * (~growth_axis(labels)).astype(np.float64), observed, "grader_axis"
        )
        values = {
            "lam_x_usrec": system.inflation.lam_x,  # not a function of the labels
            "lam_x_grader_axis": axis_block.lam_x,
            "c_i_policy_rule": float(stats["beta"][1]),
            "c_x_inflation_gap": float(stats["beta"][2]),
            TRANSMISSION_KEY: float(hazard["coefficients"][TRANSMISSION_KEY]),
        }
        arms[name] = {
            "arm": name,
            "values": {k: _f(v) for k, v in values.items()},
            "moves_by_se": {
                k: _f((values[k] - baselines[k][0]) / baselines[k][1]) if baselines[k][1] else None
                for k in values
            },
            "grader_axis_selected_lag_months": int(axis_block.lag_months),
            "economic_share_on_history": _f(stats["economic_share"]),
        }

    worst: dict[str, Any] = {}
    for key in baselines:
        rows = [
            (arm, arms[arm]["moves_by_se"][key])
            for arm, _d, _g in STABILITY_ARMS
            if arm != "baseline" and arms[arm]["moves_by_se"][key] is not None
        ]
        if not rows:
            continue
        name, value = max(rows, key=lambda r: abs(float(r[1])))
        worst[key] = {
            "arm": name,
            "moves_by_se": _f(value),
            "escalated": bool(abs(float(value)) > 1.0),
            "baseline": _f(baselines[key][0]),
            "baseline_standard_error": _f(baselines[key][1]),
        }
    return {
        "arms": arms,
        "worst_arm_per_coefficient": worst,
        "escalated": sorted(k for k, v in worst.items() if v["escalated"]),
        "escalation_rule": (
            "the sealed rule: a statistic that moves by more than its own standard error "
            "across the nine dial arms escalates to soft labels and both are reported"
        ),
        "coupling_coefficient_verdict": (
            "the PRIMARY lam_x is fitted against 1 - 2*USREC, which is not a function of "
            "the classifier's dials at all, so it is INVARIANT under the whole grid by "
            "construction -- a real stability property and not a measurement. The dial "
            "sensitivity that exists is carried by lam_x_grader_axis, the same equation "
            "refitted on the classifier's own growth axis, and that is the number to read"
        ),
    }


# --------------------------------------------------------------------------- #
# the arms that are disclosures rather than verdicts
# --------------------------------------------------------------------------- #


def disclosure_arms(
    panel: Panel, states: dict[str, np.ndarray], cells: np.ndarray, lag: int
) -> dict[str, Any]:
    """Every construct the primary did NOT take, fitted and reported.

    None of these can supply a verdict. They exist so the cost of each primary
    choice is a number rather than an argument -- week 3's rule for its own OLS
    arm, applied to the three ambiguities §2.2 of the design document leaves.
    """
    observed = ~np.isnan(panel.yoy)
    x_gap = states["x_gap"]
    grader_cycle = 1.0 - 2.0 * (~growth_axis(panel.labels)).astype(np.float64)
    grader = fit_inflation_block(x_gap, grader_cycle, observed, "grader_axis")

    # the hazard with the design document's literal x_t in the pi_gap slot
    z_substituted = panel.z_lagged(lag)
    z_substituted[:, 2] = (x_gap - float(np.mean(x_gap))) / float(np.std(x_gap))
    substituted = fit_arm(cells, z_substituted)
    baseline_hazard = fit_arm(cells, panel.z_lagged(lag))

    # the curve with u_hat restored beside the rule-implied rate
    design = _m4_design(panel, states)
    x = np.asarray(design["x"], dtype=np.float64)
    y = np.asarray(design["y"], dtype=np.float64)
    start = int(design["start_row"])
    u = panel.u_hat[start:]
    x_with_u = np.column_stack([x, u - float(np.mean(u))])
    with_u = ar1_block_fit(y, x_with_u)
    without_u = ar1_block_fit(y, x)
    with_u_beta = np.asarray(with_u["beta"], dtype=np.float64)
    with_u_residual_sd = float(
        with_u["sigma"] / math.sqrt(max(1.0 - with_u["rho"] * with_u["rho"], 1e-12))
    )
    with_u_share = strict_economic_share(
        {
            "policy_rule": (float(abs(with_u_beta[1]) * np.std(x_with_u[:, 1])), True),
            "inflation_gap": (float(abs(with_u_beta[2]) * np.std(x_with_u[:, 2])), True),
            "season_term": (float(np.std(x_with_u[:, 3:6] @ with_u_beta[3:6])), True),
            "u_hat": (float(abs(with_u_beta[6]) * np.std(x_with_u[:, 6])), False),
        },
        with_u_residual_sd,
    )["economic_share"]

    return {
        "inflation_block_on_the_grader_axis": {
            "why": (
                "M3's own cycle-input sensitivity arm: the same equation with the "
                "classifier's growth axis in place of fred.USREC. It is the object the "
                "ENGINE generates, which is the argument for it; it is not the design "
                "document's c_t and not the sealed anchor's, which is the argument against"
            ),
            "selected_lag_months": int(grader.lag_months),
            "lam_x": _f(grader.lam_x),
            "standard_error": _f(grader.lam_x_se),
            "t_ratio": _f(grader.lam_x / grader.lam_x_se) if grader.lam_x_se else None,
            "persistence_a": _f(grader.persistence),
            "lr_statistic": _f(grader.lr_statistic),
            "long_run_gap_per_unit_cycle_pp": _f(
                grader.lam_x / (1.0 - grader.persistence)
                if grader.persistence < 1.0
                else float("nan")
            ),
            "judged": False,
        },
        "hazard_with_the_inflation_gap_substituted": {
            "why": (
                "the design document's §2.2 hazard line writes x_t where week 2's third "
                "covariate is pi* - pi_target. This is that substitution, at the same "
                "parameter count, so the two log-likelihoods are directly comparable"
            ),
            "loglik_baseline": _f(baseline_hazard["loglik"]),
            "loglik_substituted": _f(substituted["loglik"]),
            "loglik_difference": _f(
                float(substituted["loglik"]) - float(baseline_hazard["loglik"])
            ),
            "transmission_baseline": _f(baseline_hazard["coefficients"][TRANSMISSION_KEY]),
            "transmission_substituted": _f(substituted["coefficients"][TRANSMISSION_KEY]),
            "judged": False,
        },
        "curve_with_u_hat_restored": {
            "why": (
                "the design document's curve line reads i_t = i_rule + u. The sealed P2 "
                "anchor decomposes history on i_rule alone and classifies u_hat as "
                "EXOGENOUS, so restoring it adds a term to the denominator and none to the "
                "numerator. Fitted here so the cost of the primary choice is a number"
            ),
            "loglik_without_u": _f(without_u["loglik"]),
            "loglik_with_u": _f(with_u["loglik"]),
            "lr_statistic": _f(2.0 * (float(with_u["loglik"]) - float(without_u["loglik"]))),
            "c_u_estimate": _f(with_u_beta[6]),
            "c_i_with_u_present": _f(with_u_beta[1]),
            "economic_share_on_history_with_u_as_exogenous": _f(with_u_share),
            "judged": False,
        },
    }


# --------------------------------------------------------------------------- #
# property checks against the sealed anchors
# --------------------------------------------------------------------------- #


def anchor_agreement(
    inflation: InflationBlock, curve: Stage2Curve, hazard: dict[str, Any]
) -> dict[str, Any]:
    """Prove the fit reproduces the sealed anchors and week 3's committed hazard.

    Three identities, each a bit-level comparison rather than an assertion:

    * the inflation block IS `M3`'s equation, so its selected lag and its
      ``lam_x`` must match ``stage2-anchors.json`` exactly;
    * the curve block IS `M4`'s equation, so its coefficients, ``rho`` and
      history's strict share must match the anchor `P2` was cut from;
    * the hazard block is week 2's, unchanged, so its coefficients must match
      the committed week-3 artifact.

    If any of these drifts, every verdict in this report is void -- which is why
    they are checked in code and not claimed in prose.

    **The tolerance is 1e-11 and that is not slack.** Both artifacts are written
    with twelve-decimal rounding, so an exact refit of the identical equation
    lands within a few units in the thirteenth decimal by construction. A
    tolerance of zero would be asserting that the committed JSON carries more
    digits than it does; 1e-11 is one order looser than the rounding and eleven
    orders tighter than any quantity that could change a verdict.
    """
    anchors = json.loads((SPECS_DIR / "stage2-anchors.json").read_text(encoding="utf-8"))
    feedback = json.loads(FEEDBACK_PARAMS_PATH.read_text(encoding="utf-8"))

    m3 = anchors["m3_growth_to_inflation_coupling"]
    m4 = anchors["m4_curve_endogeneity"]["point_estimate"]
    committed = feedback["fit"]["hazard"]["coefficients"]

    lam_drift = abs(inflation.lam_x - float(m3["point_estimate"]["lam_x"]))
    lag_matches = int(inflation.lag_months) == int(m3["selected_lag_months"])
    beta_drift = max(abs(float(a) - float(b)) for a, b in zip(curve.beta, m4["beta"], strict=True))
    rho_drift = abs(curve.rho - float(m4["rho"]))
    share_drift = abs(float(curve.statistics["economic_share"]) - float(m4["economic_share"]))
    hazard_drift = max(
        abs(float(hazard["coefficients"][k]) - float(v)) for k, v in committed.items()
    )
    ok = (
        lam_drift < ANCHOR_TOLERANCE
        and lag_matches
        and beta_drift < ANCHOR_TOLERANCE
        and rho_drift < ANCHOR_TOLERANCE
        and share_drift < ANCHOR_TOLERANCE
        and hazard_drift < ANCHOR_TOLERANCE
    )
    if not ok:
        raise FitError(
            "the stage-2 fit does not reproduce the sealed anchors: "
            f"lam_x drift {lam_drift:.3e}, lag matches {lag_matches}, curve beta drift "
            f"{beta_drift:.3e}, rho drift {rho_drift:.3e}, share drift {share_drift:.3e}, "
            f"hazard drift {hazard_drift:.3e}"
        )
    # reported as formatted strings, not floats: every one of these is smaller
    # than the artifact's own twelve-digit rounding, so storing them as numbers
    # would print a row of zeros and hide the size of the agreement
    return {
        "m3_selected_lag_matches": lag_matches,
        "m3_lam_x_max_abs_drift": f"{lam_drift:.3e}",
        "m4_curve_beta_max_abs_drift": f"{beta_drift:.3e}",
        "m4_rho_abs_drift": f"{rho_drift:.3e}",
        "m4_history_strict_share_abs_drift": f"{share_drift:.3e}",
        "week3_hazard_coefficients_max_abs_drift": f"{hazard_drift:.3e}",
        "tolerance": ANCHOR_TOLERANCE,
        "tolerance_note": (
            "both artifacts round to twelve decimals, so an exact refit of the identical "
            "equation agrees to a few units in the thirteenth. The tolerance is one order "
            "looser than that rounding and eleven orders tighter than anything that could "
            "move a verdict"
        ),
        "all_identities_hold": bool(ok),
        "why_it_matters": (
            "the inflation block IS M3's equation and the curve block IS M4's, so the "
            "engine's own fit and the sealed anchors are the same numbers. A drift here "
            "would mean the bar and the engine were cut from different objects"
        ),
    }


# --------------------------------------------------------------------------- #
# the entry point
# --------------------------------------------------------------------------- #


def main() -> int:
    streams = assert_stage2_tapes_distinct()
    sealed = load_sealed()
    v2_sealed = load_v2_sealed()
    n_decades = int(v2_sealed["bars"].get("n_seeds", DEFAULT_N_DECADES))

    panel = build_panel()
    cells = season_cells(panel.labels, panel.yoy, panel.era_threshold_pp)
    lag = int(select_curve_lag(panel, cells)["selected_lag_months"])
    hazard = fit_arm(cells, panel.z_lagged(lag))

    states = rule_implied_states(panel)
    cycle = _usrec_cycle(panel)
    observed = ~np.isnan(panel.yoy)

    inflation = fit_inflation_block(states["x_gap"], cycle, observed, "usrec")
    policy = fit_policy_block(panel.u_hat, states["x_gap"], cycle)
    curve = fit_stage2_curve(panel, states)
    agreement = anchor_agreement(inflation, curve, hazard)
    restrictions = curve_restrictions(panel, states)

    system = build_system(panel, hazard, cells, lag, inflation, policy, curve, states, cycle)
    climate, _regimes = _pinned_layers()

    decades, tally = simulate_batch_coupled(
        system, climate, n_decades=n_decades, seed=STAGE2_VERIFY_SEED
    )
    verdicts = judge_batch(decades, system, sealed, v2_sealed)
    readings = bar_readings(verdicts)
    o1_disclosure = disclose_o1_symmetric(verdicts["O1"], sealed)

    frontier_rows = frontier(
        system,
        climate,
        sealed,
        v2_sealed,
        n_decades=n_decades,
        axis="lam_x",
        multipliers=COUPLING_MULTIPLIERS,
    ) + frontier(
        system,
        climate,
        sealed,
        v2_sealed,
        n_decades=n_decades,
        axis="curve_loadings",
        multipliers=LOADING_MULTIPLIERS,
    )

    legacy_joint = fit_joint(panel, cells, lag)
    legacy_curve = curve_model_from_fit(legacy_joint.curve, legacy_joint)
    attribution_table = attribution(
        system, legacy_curve, climate, sealed, v2_sealed, n_decades=n_decades
    )

    stability = label_stability(panel, states, lag, system)
    disclosures = disclosure_arms(panel, states, cells, lag)
    identity = identifiability(system, hazard)

    all_pass = all(bool(verdicts[code]["pass"]) for code in PRE_FLESH_BARS)
    if identity["stop_condition_triggered"]:
        status = "STOPPED"
    else:
        status = "FIT-VERIFIED" if all_pass else "FRONTIER"

    payload: dict[str, Any] = {
        "schema": "stage2-fitted-params-1",
        "purpose": (
            "stage 2 week A: the coupled monthly macro system -- growth, inflation, policy "
            "and the curve -- fitted jointly on the campaign panel by maximum likelihood, "
            "and the eight pre-flesh bars read by the sealed judges. A1/A2/R1/R2 need the "
            "flesh or the twin and are week C"
        ),
        "spec": "docs/superpowers/specs/2026-08-17-stage2-coupled-system-design.md",
        "exam": "docs/superpowers/specs/2026-08-18-stage2-exam-delta.md",
        "seal": "docs/superpowers/specs/stage2-prereg.json",
        "seal_files_untouched": sorted(
            set(sealed["hashed_files"]) | set(v2_sealed["hashed_files"])
        ),
        "status": status,
        "primary_constructs": {
            "declared_before_any_bar_was_read": True,
            "curve_arm": PRIMARY_CURVE_ARM,
            "cycle_input": PRIMARY_CYCLE_INPUT,
            "hazard_arm": PRIMARY_HAZARD_ARM,
            "deviations_from_the_design_document": [
                {"deviation": a, "reason": b} for a, b in DEVIATIONS
            ],
        },
        "streams": streams,
        "panel": panel.diagnostics,
        "anchor_agreement": agreement,
        "model": {
            "system": (
                "x_{t+1} = k0 + a x_t + lam_x (c_{t-m} - cbar) + sig_x e; "
                "pi_t = pi*_t + x_t; "
                "u_{t+1} = u0 + phi_u u_t + lam_u x_t + lam_c c_t + sig_u e; "
                "i_t = r*_t + pi*_t + phi_pi x_t + phi_c c_t; "
                "slope_t = c0 + c_i (i_t - ibar) + c_x (x_t - xbar) + season_term(g_t, a_t) "
                "+ e_t, e AR(1); season_{t+1} ~ Bernoulli(h(season_t, dwell_t, z_t)) with "
                "z carrying slope at the curve's own lead"
            ),
            "joint_likelihood": (
                "L = L_hazard(beta) + L_inflation(k0, a, lam_x, sig_x) + L_policy(u0, phi_u, "
                "lam_u, lam_c, sig_u) + L_curve(c, rho, sigma), maximised as one object. It "
                "block-diagonalises because every path is OBSERVED on the panel -- the "
                "season from grader_v2's labels, the slope from the panel's own 10y-2y, the "
                "inflation gap from CPI minus L1's trend, the policy deviation from the "
                "observed rate minus L1's own anchor. That is a property of the data and "
                "not an achievement of the design; what the joint fit buys is that every "
                "'no coupling' restriction nests exactly and is a likelihood-ratio test"
            ),
            "lag_selection_rule": (
                "SEALED (ruling SQ9): maximum likelihood on the declared 25-lag grid, 0 to "
                "24 months, one parameter at every lag, a common sample at every lag, the "
                "highest likelihood wins, the whole profile published"
            ),
        },
        "fit": {
            "hazard": {
                "form": "unchanged from week 2 and week 3",
                "curve_lag_months": lag,
                "coefficients": {k: _f(v) for k, v in hazard["coefficients"].items()},
                "standard_errors": {k: _f(v) for k, v in hazard["standard_errors"].items()},
                "loglik": _f(hazard["loglik"]),
                "n_events": _f(hazard["n_events"]),
                "n_obs": _f(hazard["n_obs"]),
            },
            "inflation": {
                "cycle_input": inflation.cycle_input,
                "selected_lag_months": inflation.lag_months,
                "intercept": _f(inflation.intercept),
                "persistence_a": _f(inflation.persistence),
                "lam_x": _f(inflation.lam_x),
                "lam_x_standard_error": _f(inflation.lam_x_se),
                "lam_x_t_ratio": _f(inflation.lam_x / inflation.lam_x_se),
                "cbar": _f(inflation.cbar),
                "innovation_sd_pp": _f(inflation.innovation_sd),
                "stationary_sd_pp": _f(inflation.stationary_sd),
                "unconditional_mean_pp": _f(inflation.unconditional_mean),
                "half_life_months": _f(
                    math.log(2.0) / -math.log(inflation.persistence)
                    if 0.0 < inflation.persistence < 1.0
                    else float("nan")
                ),
                "long_run_gap_per_unit_cycle_pp": _f(
                    inflation.lam_x / (1.0 - inflation.persistence)
                    if inflation.persistence < 1.0
                    else float("nan")
                ),
                "lr_statistic_against_no_coupling": _f(inflation.lr_statistic),
                "n_rows": inflation.n_rows,
                "lag_profile": {
                    str(k): {
                        "loglik": _f(v["loglik"]),
                        "lam_x": _f(v["lam_x"]),
                        "standard_error": _f(v["standard_error_lam_x"]),
                        "t_ratio": _f(v["t_ratio"]),
                        "persistence_a": _f(v["persistence_a"]),
                    }
                    for k, v in sorted(inflation.profile.items())
                },
            },
            "policy": {
                "intercept": _f(policy.intercept),
                "persistence_phi_u": _f(policy.persistence),
                "lam_u": _f(policy.lam_u),
                "lam_c": _f(policy.lam_c),
                "standard_errors": {k: _f(v) for k, v in policy.standard_errors.items()},
                "innovation_sd": _f(policy.innovation_sd),
                "stationary_sd": _f(policy.stationary_sd),
                "lr_statistic_against_no_loadings": _f(policy.lr_statistic),
                "n_rows": policy.n_rows,
                "units_note": (
                    "u is build_panel's STANDARDISED policy deviation (mean 0, sd 1 on the "
                    "panel), so lam_u and lam_c are in standard deviations of u per "
                    "percentage point of inflation gap and per unit of cycle input"
                ),
            },
            "curve": {
                "form": (
                    "M4's equation: slope_t = c0 + c_i (i_rule_t - ibar) + c_x (x_t - xbar) "
                    "+ c_C (C - Cbar) + c_E (E - Ebar) + c_K (K - Kbar) + e_t, e AR(1), "
                    "exact Gaussian maximum likelihood"
                ),
                "coefficients": {k: _f(v) for k, v in curve.coefficients.items()},
                "standard_errors": {k: _f(v) for k, v in curve.standard_errors.items()},
                "t_ratios": {
                    k: _f(curve.coefficients[k] / curve.standard_errors[k])
                    if curve.standard_errors[k]
                    else None
                    for k in CURVE_LABELS
                },
                "centers": _round(curve.centers.tolist()),
                "rho": _f(curve.rho),
                "rho_standard_error": _f(curve.rho_se),
                "innovation_sd_pp": _f(curve.innovation_sd),
                "residual_stationary_sd_pp": _f(curve.residual_stationary_sd),
                "loglik": _f(curve.loglik),
                "n_months": curve.n_months,
                "r_squared_realised": _f(curve.r_squared),
                "history_strict_economic_share": _f(curve.statistics["economic_share"]),
                "restrictions": restrictions,
            },
            "joint_loglik": _f(system.joint_loglik),
            "axis_calibrated_cycle": {
                "contracting": _f(system.axis_cycle[0]),
                "expanding": _f(system.axis_cycle[1]),
                "panel_mean_of_the_wp26_contract": _f(np.mean(cycle)),
                "note": (
                    "the panel mean of 1 - 2*USREC inside each of the classifier's growth "
                    "axes. Averaged over the panel's own axis shares this reproduces the "
                    "panel mean exactly, which is what keeps the generated inflation LEVEL "
                    "where the fitted equation put it"
                ),
            },
        },
        "identifiability": identity,
        "verification": {
            "seed": STAGE2_VERIFY_SEED,
            "seed_note": (
                "week 3's verification seed, re-used deliberately: the same batch identity, "
                "so a change of verdict is attributable to the engine and not to a tape"
            ),
            "n_decades": n_decades,
            "arm": "unconditional",
            "attempts": int(tally.get("attempts", 0)),
            "bars": readings,
            "all_eight_pass": all_pass,
            "n_passing": int(sum(1 for r in readings if r.get("pass"))),
            "o1_symmetric_disclosure": o1_disclosure,
            "p2_components": {
                "component_sd_pp": {k: _f(v) for k, v in p2_components(decades, system)[0].items()},
                "residual_stationary_sd_pp": _f(curve.residual_stationary_sd),
            },
            "diagnostics": batch_diagnostics(decades, system, panel, cycle, states),
        },
        "attribution": attribution_table,
        "frontier": frontier_rows,
        "label_stability": stability,
        "disclosure_arms": disclosures,
        "week_c": {
            "bars": list(WEEK_C_BARS),
            "why": (
                "A1 and A2 need the flesh -- verbatim real months of asset returns compiled "
                "onto the spine, which this loop does not run. R1 needs the institutional "
                "twin's over-commitment grid and R2 needs an ensemble and the panel source. "
                "None of the four is measured here and none is estimated"
            ),
        },
        "standing_caveat": (
            "nothing built on this generator line is a convincing model of history, the "
            "holdout is spent, and no appeal to held-out data is available to any result "
            "stage 2 produces"
        ),
    }

    # newline="\n" so the file on disk IS the file git stores -- stage2_anchors.py's
    # own convention, and it is what makes "byte-identical on a re-run" a claim a
    # reader can check with sha256 rather than one that depends on the platform.
    PARAMS_PATH.write_text(
        json.dumps(_round(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"status: {status}")
    print(f"wrote {PARAMS_PATH.relative_to(_REPO_ROOT)}")
    for row in readings:
        if row.get("measured"):
            print(f"  {row['bar']:<3} {'PASS' if row['pass'] else 'FAIL'}  value={row['value']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
