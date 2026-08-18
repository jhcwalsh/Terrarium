"""Spine v2, week 3: give the curve a SEASON, refit jointly, re-verify.

Spec: ``docs/superpowers/specs/2026-08-17-spine-v2-exam.md`` (SEALED).
Pre-registration: ``docs/superpowers/specs/spine-v2-prereg.json``, as amended by
**AM-SPV2-2026-08-17-001** (post-hoc, 2026-08-17): T1 and O1 are judged on an
UNCONDITIONAL 50-decade batch; every other bar keeps the premise-accepted batch.
**Nothing this module touches is hashed by that seal.** It reads the seal,
imports the sealed grader and the sealed judges, and imports week 2's fitted
model (``scripts/spine_v2_fit.py``) rather than re-implementing it -- that module
is left BYTE-IDENTICAL, so ``spine-v2-fitted-params.json`` remains the week-2
record and every "before" number in the report below can be re-derived from it.

Why this module exists
----------------------
Week 2's engine reached the campaign's frontier for a measured reason
(``docs/superpowers/specs/2026-08-17-spine-v2-fit-report.md`` section 8): it has
causation running **curve -> season** and **no feedback running season -> curve**.
Its generated curve is L1's policy-deviation state plus a fitted AR(1) residual,
and nothing in a contraction makes it steepen. The consequence is measurable and
it is the whole of the T1 failure:

    share of inverted-curve months that are EXPANDING
        history   0.7651   (against a 0.7364 base rate -- concentrated AHEAD of the turn)
        week 2    0.4015   (against a 0.5339 base rate -- concentrated INSIDE the turn)

In a real economy the curve inverts because policy is tightening into a mature
expansion, and it steepens because the downturn arrives and policy is cut. This
module puts that second half into the curve process and **fits it**.

The model, in full
------------------
Week 2's curve equation was ``slope_t = c0 + c_u u_hat_t + e_t`` with ``e``
AR(1), fitted by OLS plus a moment-matched residual. This one adds a
**season-state term** and fits the whole equation by exact Gaussian maximum
likelihood::

    slope_t = c0 + c_u*u_hat_t
                 + c_C*(C_t - Cbar) + c_E*(E_t - Ebar) + c_K*(K_t - Kbar)
                 + e_t ,        e_t = rho*e_{t-1} + eta_t ,  eta ~ N(0, sigma^2)

with, at month ``t``, ``g_t`` the growth axis (``grader_v2``'s contracting set
``{REC, CRI, STAG}``) and ``a_t`` the months elapsed in the current
**growth-axis** spell (1-based):

    C_t = 1[contracting]                 the level shift a contraction puts in the curve
    E_t = log(a_t) if expanding else 0   how an EXPANSION's age bends it
    K_t = log(a_t) if contracting else 0 how a CONTRACTION's age bends it

Three new coefficients, every one estimated. The economics they are allowed to
find, and the signs that would confirm it: ``c_C > 0`` (policy cuts into a
downturn, so the curve steepens), ``c_E < 0`` (policy tightens into a maturing
expansion, so the curve flattens and eventually inverts), ``c_K > 0`` (the longer
the downturn runs the more has been cut). **No sign is imposed** -- the
likelihood is free to return any of them with the opposite sign, and the report
prints them with standard errors and t-ratios either way.

``C``, ``E`` and ``K`` are **centred on their own sample means**, so the season
term has mean exactly zero on the fitted panel. That is not cosmetic: it is what
lets a simulated decade's nine-month pre-history -- which has no season path,
because the decade has not started -- carry the term at precisely its
unconditional mean rather than at an invented value.

Why ``log(a)`` and not ``a``: the same reason the hazard's duration dependence is
``b_s log(d)``. It is the one-parameter shape that bends with age without
imposing a scale, it is what the hazard block already uses so the two blocks
speak the same language about age, and ``c = 0`` nests "age does nothing"
exactly, so the question is a t-ratio rather than an argument.

"Jointly with the existing hazard parameters" -- and what that does and does not mean
------------------------------------------------------------------------------------
The joint log-likelihood of the two observed processes is

    L(beta, c, rho, sigma) = L_hazard(beta) + L_curve(c, rho, sigma)

and :func:`fit_joint` maximises exactly that object. It **block-diagonalises**,
and the honest statement is that this is a property rather than an achievement:
on the historical panel BOTH paths are observed -- the season path comes from
``grader_v2``'s labels and the slope path from the panel's own ``ust_10y -
ust_2y`` -- so the season enters the curve block as an observed regressor and the
slope enters the hazard block as an observed regressor, and neither block
contains the other's parameters. The cross-block information is therefore exactly
zero, the joint maximum is attained blockwise, and the joint Fisher information
is block-diagonal. Three consequences, all of which matter for reading the result:

1. **The hazard coefficients are numerically UNCHANGED from week 2.** That is
   checked against the committed week-2 artifact, not asserted
   (``hazard_block_identical_to_week_2`` in the output). The transmission channel
   was not re-tuned to reach a bar; the feedback is a pure addition.
2. **The coupling is at GENERATION time, not at estimation time.** In simulation
   the season is not observed -- it is produced by the hazard, which reads the
   curve, which now reads the season. The joint fit is what supplies both halves
   of that loop from one likelihood.
3. **The restriction is testable inside the same object.** ``c_C = c_E = c_K = 0``
   is week 2's no-feedback curve, nested exactly, so the likelihood-ratio
   statistic against chi-squared on 3 degrees of freedom is a real test and is
   reported.

Simulation: the loop, and why it closes without circularity
-----------------------------------------------------------
The hazard reads the curve at a **9-month lag** (week 2's likelihood-selected
lead time) and the curve reads the season **contemporaneously**, so the recursion
is well-posed: at month ``t`` the season is already fixed by the hazard drawn at
``t-1``, which used ``slope_{t-9}``, which was generated at least nine months
ago. Month by month::

    season_t   is known           (drawn at t-1 from the hazard)
    slope_t    = c0 + c_u u_hat_t + season_term(g_t, a_t) + e_t
    z_t        carries slope_{t-9} in its curve column
    season_t+1 ~ Bernoulli(h(season_t, dwell_t, z_t))

``u_hat`` (L1's policy-deviation OU) and ``e`` (the AR(1) residual) are drawn as
whole exogenous paths first, exactly as in week 2 and from the same streams, so
the ONLY difference between week 2's curve and this one is the season term.

Two initial conditions the loop needs and week 2 did not:

- **the pre-history** (the nine months before the decade, whose only job is to
  supply the lagged curve reading for the decade's first nine months) carries the
  season term at zero, which is its unconditional mean by the centring above;
- **the opening growth-spell age** is drawn from history's own empirical
  distribution of "age at a randomly chosen month", conditioned on the opening
  axis. Setting it to 1 would open every decade at the birth of a spell, which is
  a real bias in a term that is a function of age. This is read off the panel,
  not chosen: it is the length-biased age distribution a random calendar month
  actually sees. (The SEASON dwell that drives the hazard still starts at 1,
  exactly as in week 2, so the hazard's own behaviour is untouched. The two
  counters are different objects -- a season can change inside a growth spell
  when inflation crosses its line -- and the mild inconsistency at ``t = 0`` is
  stated here rather than hidden.) That draw comes from a **fifth stream of its
  own** (``openage``), never from the ``seasons`` stream, so the season tape is
  consumed exactly as week 2 consumed it -- which is what makes the ``week2``
  engine below week 2's engine rather than a re-realisation of it on a tape
  shifted by one draw.

Four engines are simulated and judged, so the change can be attributed
---------------------------------------------------------------------
Exact ML and week 2's OLS-plus-moment-matched-AR(1) do **not** agree about the
L1 link, and by a lot: the ``u_hat`` loading is about -0.15 under exact ML
against -0.54 under OLS. That is a property of the data rather than of the
season term -- with a residual at ``rho`` near 0.97 the Prais-Winsten transform
is close to differencing, and the levels relation between two persistent series
largely disappears in differences -- and it would confound any before/after
reading taken across it. So both estimators are run, each with and without the
feedback:

    week2          OLS link,       no feedback   (week 2's engine, reproduced exactly)
    ml_link        exact-ML link,  no feedback
    ols_feedback   OLS link,       season term fitted by that same OLS
    feedback       exact-ML link,  season term fitted by exact ML   <- THE PRIMARY

**Declared before any bar was read, and binding:** the verdict is taken on
``feedback``, the exact-ML joint fit, because that is the estimator the joint
likelihood names -- chosen for that reason and not for a reading.
``ols_feedback`` is an **estimator-sensitivity disclosure and cannot supply a
verdict**, however it reads. Running two estimators and reporting whichever
passes would be tuning past a conflict, which the campaign's frontier discipline
forbids; running two and pre-committing to one is attribution.

Determinism: same base seed, same layer offsets and same attempt stride as week
2 (proved distinct by ``spine_v2_fit.assert_distinct_tapes``, extended here for
the fifth stream), so the L1 tapes are shared across the four engines and a
difference between them is the model. ``week2`` reproduces week 2's published
readings bit-for-bit, which is the check that the shared tape really is shared.
Every float is rounded to twelve places on output, so re-runs are byte-identical.

Run (offline, no network):

    uv run python scripts/spine_v2_feedback.py
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_fit import (  # noqa: E402
    CLIMATE_OFFSET,
    COVARIATES,
    DECADE_MONTHS,
    DEFAULT_N_DECADES,
    EXPANDING,
    HOT,
    LAYER_OFFSETS,
    MAX_ATTEMPTS_PER_DECADE,
    PARAM_LABELS,
    SPINE2_ATTEMPT_STRIDE,
    STABILITY_ARMS,
    TRANSMISSION_KEY,
    V_DRAWDOWN_WINDOW_MONTHS,
    VERIFY_SEED,
    FitError,
    FittedEngine,
    Panel,
    SimulatedDecade,
    _load_premise,
    _round,
    ar1_path,
    assert_distinct_tapes,
    bar_readings,
    borderline_weights,
    build_engine,
    build_panel,
    emit_labels,
    fit_arm,
    hazard_probability,
    judge_batch,
    measure_stag_spell_rate,
    ou_standardised,
    reject_reason,
    relabel,
    select_curve_lag,
    soft_label_weights,
    to_decade,
    trailing_drawdown,
)
from spine_v2_grader import CONTRACTING_LABELS, season_cells  # noqa: E402
from spine_v2_report import load_sealed  # noqa: E402

from ah.gen.climate.model import PARAM_NAMES  # noqa: E402
from ah.gen.climate.simulate import simulate_decades  # noqa: E402
from ah.gen.spine import CLOCKWISE, QUADRANTS  # noqa: E402
from ah.gen.systems import _pinned_layers  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
PARAMS_PATH = SPECS_DIR / "spine-v2-feedback-params.json"
#: Week 2's committed artifact. Read only -- it is the "before" side of every
#: comparison in this module and the source of the hazard-block identity check.
WEEK2_PARAMS_PATH = SPECS_DIR / "spine-v2-fitted-params.json"

#: Week 2's four per-decade streams plus a fifth for the opening growth-spell
#: age. The new offset is checked against every other offset in play -- week 2's
#: four and the platform's five -- by :func:`assert_feedback_tapes_distinct`.
#: Adding it as a NEW stream rather than as one more draw on ``seasons`` is what
#: keeps the season tape byte-for-byte week 2's.
OPENAGE_OFFSET = 1298743
FEEDBACK_LAYER_OFFSETS: dict[str, int] = {**LAYER_OFFSETS, "openage": OPENAGE_OFFSET}

#: The amendment this module's judging construct comes from.
AMENDMENT_ID = "AM-SPV2-2026-08-17-001"
#: Bars judged on the unconditional batch, per that amendment.
UNCONDITIONAL_BARS = ("T1", "O1")
#: Bars judged on the premise-accepted batch, per that amendment (of the six
#: that a no-flesh spine can measure at all).
PREMISE_BARS = ("D1", "D2", "D3", "D4")

#: The curve equation's parameter names, in design-matrix column order.
CURVE_PARAM_LABELS: tuple[str, ...] = (
    "intercept",
    "u_hat_loading",
    "contracting",
    "expansion_age",
    "contraction_age",
)
#: The three the season term is made of -- the restriction the LR test sets to
#: zero, and week 2's model when it holds.
FEEDBACK_KEYS: tuple[str, ...] = ("contracting", "expansion_age", "contraction_age")

#: The AR(1) coefficient's search bracket. Bounded away from the unit circle
#: because the exact likelihood carries ``0.5*log(1-rho^2)`` and is -inf at 1.
RHO_BRACKET = (-0.99, 0.999)
#: Points in the coarse profile scan before the golden-section refinement. Both
#: are deterministic; the coarse scan exists so the refinement cannot be trapped
#: by a local maximum at the bracket's edge.
RHO_SCAN_POINTS = 199
#: Golden-section tolerance on rho. Far below any reported precision.
RHO_TOL = 1e-12
#: Relative step for the central-difference Hessian the standard errors come
#: from. 1e-5 is the usual compromise: large enough that float64 cancellation
#: does not dominate, small enough that the third-order term does not.
HESSIAN_REL_STEP = 1e-5


# --------------------------------------------------------------------------- #
# stream hygiene -- the new fifth stream
# --------------------------------------------------------------------------- #


def assert_feedback_tapes_distinct(base_seed: int = VERIFY_SEED, n: int = 64) -> dict[str, Any]:
    """Week 2's proof, extended to the ``openage`` stream.

    Same method and the same reason (the platform has paid twice for reusing a
    stride on a new axis): draw the first eight float64s of every stream and
    compare whole tapes, rather than arguing that two integers differ.
    """
    from ah.gen.spine import LAYER_OFFSETS as PLATFORM_LAYER_OFFSETS

    base = assert_distinct_tapes(base_seed, n)
    if OPENAGE_OFFSET in set(LAYER_OFFSETS.values()) | set(PLATFORM_LAYER_OFFSETS.values()):
        raise FitError("the openage offset collides with an existing layer offset")

    def tape(seed: int, jump: int) -> tuple[float, ...]:
        rng = np.random.Generator(np.random.PCG64(int(seed)).jumped(int(jump)))
        return tuple(float(x) for x in rng.random(8))

    tapes: dict[tuple[str, int], tuple[float, ...]] = {}
    for name, offset in FEEDBACK_LAYER_OFFSETS.items():
        for k in range(n):
            tapes[(name, k)] = tape(base_seed + offset, k)
    if len(set(tapes.values())) != len(tapes):
        raise FitError("two per-decade streams share a tape once openage is added")
    return {
        **base,
        "openage_offset": OPENAGE_OFFSET,
        "n_streams_checked_with_openage": len(tapes),
        "openage_disjoint_from_every_other_layer": True,
    }


# --------------------------------------------------------------------------- #
# the growth axis, its age, and the curve design matrix
# --------------------------------------------------------------------------- #


def growth_axis(labels: np.ndarray) -> np.ndarray:
    """``True`` where the month is EXPANDING under ``grader_v2``.

    Read off the label alone, through the sealed grader's own contracting set,
    so it is defined for every month of the panel -- including the twelve
    warm-up months where trailing inflation, and therefore the *season*, is not.
    The curve equation needs the growth axis, not the season, so it can use them.
    """
    return ~np.isin(np.asarray(labels), list(CONTRACTING_LABELS))


def spell_age(expanding: np.ndarray) -> np.ndarray:
    """Months elapsed in the current growth-axis spell, 1-based."""
    arr = np.asarray(expanding, dtype=bool)
    out = np.empty(arr.size, dtype=np.int64)
    run = 0
    previous: bool | None = None
    for t in range(arr.size):
        run = run + 1 if arr[t] == previous else 1
        previous = bool(arr[t])
        out[t] = run
    return out


def first_spell_end(expanding: np.ndarray) -> int:
    """Index of the last month of the panel's FIRST growth-axis spell.

    That spell's start is unobserved, so its age is unknown -- the same left
    truncation the hazard's at-risk rule already drops, applied to the same
    object, so the two blocks of the joint likelihood are fitted on months whose
    age means the same thing.
    """
    arr = np.asarray(expanding, dtype=bool)
    end = 0
    while end + 1 < arr.size and arr[end + 1] == arr[0]:
        end += 1
    return end


def curve_design(u_hat: np.ndarray, expanding: np.ndarray, age: np.ndarray) -> np.ndarray:
    """``(T, 5)`` -- ``[1, u_hat, C, E, K]``, uncentred.

    ``C`` is the contracting indicator, ``E`` is ``log(age)`` on expanding months
    and zero elsewhere, ``K`` is ``log(age)`` on contracting months and zero
    elsewhere. The three are linearly independent given the intercept: an
    expanding month contributes ``c_E log a``, a contracting one ``c_C +
    c_K log a``.
    """
    exp_arr = np.asarray(expanding, dtype=bool)
    log_age = np.log(np.maximum(np.asarray(age, dtype=np.float64), 1.0))
    return np.column_stack(
        [
            np.ones(exp_arr.size, dtype=np.float64),
            np.asarray(u_hat, dtype=np.float64),
            (~exp_arr).astype(np.float64),
            np.where(exp_arr, log_age, 0.0),
            np.where(~exp_arr, log_age, 0.0),
        ]
    )


# --------------------------------------------------------------------------- #
# the curve block: exact Gaussian AR(1) maximum likelihood
# --------------------------------------------------------------------------- #


def ar1_innovations(y: np.ndarray, x: np.ndarray, beta: np.ndarray, rho: float) -> np.ndarray:
    """The Prais-Winsten transform's residuals: ``sqrt(1-rho^2) r_0`` then ``r_t - rho r_{t-1}``.

    The first observation enters through its own stationary law rather than being
    thrown away, which is what makes the likelihood below EXACT rather than
    conditional -- so ``rho`` is identified by the whole sample.
    """
    resid = y - x @ beta
    out = np.empty(y.size, dtype=np.float64)
    out[0] = math.sqrt(1.0 - rho * rho) * resid[0]
    out[1:] = resid[1:] - rho * resid[:-1]
    return out


def ar1_loglik(
    y: np.ndarray,
    x: np.ndarray,
    beta: np.ndarray,
    rho: float,
    sigma: float,
    weights: np.ndarray,
) -> float:
    """The exact Gaussian (quasi-)log-likelihood of ``y = X beta + e``, ``e`` AR(1).

    ``weights`` are 1 everywhere in the primary fit, in which case this is the
    ordinary exact AR(1) likelihood. The label-stability arms use them exactly as
    the hazard block does -- a month's contribution scaled by the confidence of
    its classification -- which makes it a weighted quasi-likelihood on those
    arms, the same object and the same caveat as the hazard's weighted Bernoulli.
    """
    if not (-1.0 < rho < 1.0) or sigma <= 0.0:
        return -np.inf
    innovations = ar1_innovations(y, x, beta, rho)
    total_weight = float(np.sum(weights))
    return (
        -0.5 * total_weight * math.log(2.0 * math.pi * sigma * sigma)
        + 0.5 * math.log(1.0 - rho * rho)
        - float(np.sum(weights * innovations**2)) / (2.0 * sigma * sigma)
    )


def _profile_at_rho(
    y: np.ndarray, x: np.ndarray, rho: float, weights: np.ndarray
) -> tuple[np.ndarray, float, float]:
    """``(beta, sigma, loglik)`` maximising the likelihood at fixed ``rho``.

    The Prais-Winsten transform makes it a (weighted) least-squares problem, so
    ``beta`` and ``sigma`` are closed-form at every ``rho`` and only ``rho``
    itself needs searching.
    """
    n = int(y.size)
    scale = math.sqrt(1.0 - rho * rho)
    yt = np.empty(n, dtype=np.float64)
    xt = np.empty_like(x)
    yt[0] = scale * y[0]
    xt[0] = scale * x[0]
    yt[1:] = y[1:] - rho * y[:-1]
    xt[1:] = x[1:] - rho * x[:-1]
    root = np.sqrt(weights)[:, None]
    beta, *_ = np.linalg.lstsq(xt * root, yt * root[:, 0], rcond=None)
    total_weight = float(np.sum(weights))
    wss = float(np.sum(weights * (yt - xt @ beta) ** 2))
    sigma = math.sqrt(wss / total_weight)
    loglik = -0.5 * total_weight * (
        math.log(2.0 * math.pi) + math.log(wss / total_weight) + 1.0
    ) + 0.5 * math.log(1.0 - rho * rho)
    return beta, sigma, loglik


def _maximise_over_rho(y: np.ndarray, x: np.ndarray, weights: np.ndarray) -> float:
    """The profile maximiser of ``rho``: coarse scan, then golden section.

    Deterministic end to end -- no random start, no tie-break. The coarse scan
    brackets the maximum so the refinement cannot converge onto a bracket edge;
    the golden section then refines it to :data:`RHO_TOL`.
    """
    lo, hi = RHO_BRACKET
    grid = np.linspace(lo, hi, RHO_SCAN_POINTS)
    values = np.array([_profile_at_rho(y, x, float(r), weights)[2] for r in grid])
    k = int(np.argmax(values))
    left = float(grid[max(k - 1, 0)])
    right = float(grid[min(k + 1, grid.size - 1)])
    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = left, right
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc = _profile_at_rho(y, x, c, weights)[2]
    fd = _profile_at_rho(y, x, d, weights)[2]
    while abs(b - a) > RHO_TOL:
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - inv_phi * (b - a)
            fc = _profile_at_rho(y, x, c, weights)[2]
        else:
            a, c, fc = c, d, fd
            d = a + inv_phi * (b - a)
            fd = _profile_at_rho(y, x, d, weights)[2]
    return 0.5 * (a + b)


def _numerical_hessian(fn: Callable[[np.ndarray], float], theta: np.ndarray) -> np.ndarray:
    """Central-difference Hessian of ``fn`` at ``theta``, symmetrised.

    Used for the curve block's standard errors. The hazard block gets its
    information analytically from IRLS; this block's likelihood is not a GLM, and
    a numerical second derivative at a converged maximum is the standard answer.
    """
    n = int(theta.size)
    steps = np.array([HESSIAN_REL_STEP * max(1.0, abs(float(v))) for v in theta])
    hessian = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i, n):
            if i == j:
                plus = theta.copy()
                minus = theta.copy()
                plus[i] += steps[i]
                minus[i] -= steps[i]
                hessian[i, i] = (fn(plus) - 2.0 * fn(theta) + fn(minus)) / (steps[i] ** 2)
            else:
                pp, pm, mp, mm = (theta.copy() for _ in range(4))
                pp[i] += steps[i]
                pp[j] += steps[j]
                pm[i] += steps[i]
                pm[j] -= steps[j]
                mp[i] -= steps[i]
                mp[j] += steps[j]
                mm[i] -= steps[i]
                mm[j] -= steps[j]
                value = (fn(pp) - fn(pm) - fn(mp) + fn(mm)) / (4.0 * steps[i] * steps[j])
                hessian[i, j] = value
                hessian[j, i] = value
    return 0.5 * (hessian + hessian.T)


@dataclass(frozen=True)
class CurveFit:
    """One fitted curve equation, with everything the simulator and the report need."""

    beta: np.ndarray  # (5,) in CURVE_PARAM_LABELS order, on the CENTRED design
    se: np.ndarray  # (5,)
    centers: np.ndarray  # (3,) the means of C, E, K on the fitted sample
    rho: float
    rho_se: float
    innovation_sd: float
    innovation_sd_se: float
    loglik: float
    n_months: int
    r_squared: float
    feedback_free: bool

    @property
    def coefficients(self) -> dict[str, float]:
        return {k: float(v) for k, v in zip(CURVE_PARAM_LABELS, self.beta, strict=True)}

    @property
    def standard_errors(self) -> dict[str, float]:
        return {k: float(v) for k, v in zip(CURVE_PARAM_LABELS, self.se, strict=True)}


def fit_curve(
    slope: np.ndarray,
    design: np.ndarray,
    *,
    feedback: bool,
    centers: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> CurveFit:
    """Exact-ML fit of the curve equation on the panel's own months.

    ``feedback=False`` zeroes the three season columns, which is week 2's model
    nested exactly inside this one -- the restricted arm of the likelihood-ratio
    test, fitted by the identical estimator so the two log-likelihoods are
    comparable.
    """
    y = np.asarray(slope, dtype=np.float64)
    raw = np.asarray(design, dtype=np.float64)
    means = raw[:, 2:5].mean(axis=0) if centers is None else np.asarray(centers, dtype=np.float64)
    x = raw.copy()
    x[:, 2:5] -= means
    if not feedback:
        x = x[:, :2]
    w = np.ones(y.size, dtype=np.float64) if weights is None else np.asarray(weights, np.float64)

    rho = _maximise_over_rho(y, x, w)
    beta, sigma, loglik = _profile_at_rho(y, x, rho, w)

    def negative(theta: np.ndarray) -> float:
        return -ar1_loglik(
            y, x, theta[: x.shape[1]], float(theta[-2]), math.exp(float(theta[-1])), w
        )

    theta = np.concatenate([beta, [rho, math.log(sigma)]])
    hessian = _numerical_hessian(negative, theta)
    covariance = np.linalg.inv(hessian)
    errors = np.sqrt(np.abs(np.diag(covariance)))

    full_beta = np.zeros(5, dtype=np.float64)
    full_se = np.zeros(5, dtype=np.float64)
    full_beta[: x.shape[1]] = beta
    full_se[: x.shape[1]] = errors[: x.shape[1]]
    resid = y - x @ beta
    return CurveFit(
        beta=full_beta,
        se=full_se,
        centers=means,
        rho=float(rho),
        rho_se=float(errors[-2]),
        innovation_sd=float(sigma),
        # d sigma / d log sigma = sigma, so the delta method is one multiply
        innovation_sd_se=float(errors[-1] * sigma),
        loglik=float(loglik),
        n_months=int(y.size),
        r_squared=float(1.0 - np.var(resid) / np.var(y)),
        feedback_free=not feedback,
    )


def fit_curve_ols(
    slope: np.ndarray, design: np.ndarray, centers: np.ndarray | None = None
) -> CurveFit:
    """WEEK 2's estimator, extended by the three season columns.

    Ordinary least squares in levels, then an AR(1) matched to the residual's
    lag-1 autocorrelation and innovation standard deviation -- the exact
    procedure ``spine_v2_fit.build_panel`` used for the two-column link, applied
    to the five-column design so the two estimators can be compared on the same
    model rather than on two different ones.

    **This arm is a disclosure and cannot supply a verdict** (module docstring).
    Its standard errors are the plain OLS ones and are UNDERSTATED, because they
    ignore the residual autocorrelation that is the whole reason exact ML
    disagrees with it; they are reported so the two coefficient vectors can be
    read side by side, not as inference.
    """
    y = np.asarray(slope, dtype=np.float64)
    raw = np.asarray(design, dtype=np.float64)
    means = raw[:, 2:5].mean(axis=0) if centers is None else np.asarray(centers, dtype=np.float64)
    x = raw.copy()
    x[:, 2:5] -= means

    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    rho = float(np.corrcoef(resid[1:], resid[:-1])[0, 1])
    innovation_sd = float(np.std(resid[1:] - rho * resid[:-1]))
    sigma2 = float(np.sum(resid**2) / (y.size - x.shape[1]))
    errors = np.sqrt(np.abs(np.diag(np.linalg.inv(x.T @ x)) * sigma2))
    return CurveFit(
        beta=beta,
        se=errors,
        centers=means,
        rho=rho,
        rho_se=float("nan"),
        innovation_sd=innovation_sd,
        innovation_sd_se=float("nan"),
        loglik=float("nan"),  # not a likelihood fit; no comparable log-likelihood
        n_months=int(y.size),
        r_squared=float(1.0 - np.var(resid) / np.var(y)),
        feedback_free=False,
    )


def chi2_sf_df3(x: float) -> float:
    """``P(X > x)`` for chi-squared on 3 degrees of freedom, in closed form.

    Written out rather than imported so the module keeps its dependency list at
    numpy: for odd degrees of freedom the survival function is elementary, and
    for df = 3 it is ``erfc(sqrt(x/2)) + sqrt(2x/pi) exp(-x/2)``.
    """
    if x <= 0.0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0)) + math.sqrt(2.0 * x / math.pi) * math.exp(-x / 2.0)


@dataclass(frozen=True)
class JointFit:
    """The joint fit: one hazard block, one curve block, one log-likelihood."""

    hazard: dict[str, Any]
    curve: CurveFit
    curve_restricted: CurveFit
    curve_ols: CurveFit
    lag_months: int
    cells: np.ndarray
    expanding: np.ndarray
    age: np.ndarray
    fitted_from: int

    @property
    def joint_loglik(self) -> float:
        return float(self.hazard["loglik"]) + float(self.curve.loglik)

    @property
    def lr_statistic(self) -> float:
        return 2.0 * (self.curve.loglik - self.curve_restricted.loglik)


def fit_joint(panel: Panel, cells: np.ndarray, lag: int) -> JointFit:
    """Maximise ``L_hazard(beta) + L_curve(c, rho, sigma)``.

    It block-diagonalises -- see the module docstring for why, and why that is a
    property of both paths being observed rather than a shortcut taken here --
    so each block is maximised by its own exact maximiser and the sum is the
    joint maximum. The at-risk convention is shared: both blocks drop the panel's
    first (left-truncated) growth spell, so a month's age means the same thing in
    both halves of the likelihood.
    """
    hazard = fit_arm(cells, panel.z_lagged(lag))
    expanding = growth_axis(panel.labels)
    age = spell_age(expanding)
    start = first_spell_end(expanding) + 1
    design = curve_design(panel.u_hat, expanding, age)[start:]
    slope = panel.slope[start:]
    curve = fit_curve(slope, design, feedback=True)
    restricted = fit_curve(slope, design, feedback=False, centers=curve.centers)
    ols = fit_curve_ols(slope, design, centers=curve.centers)
    return JointFit(
        hazard=hazard,
        curve=curve,
        curve_restricted=restricted,
        curve_ols=ols,
        lag_months=int(lag),
        cells=np.asarray(cells),
        expanding=expanding,
        age=age,
        fitted_from=int(start),
    )


# --------------------------------------------------------------------------- #
# the simulator: the loop closed
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CurveModel:
    """The curve process the simulator runs, as fitted."""

    intercept: float
    u_hat_loading: float
    contracting: float
    expansion_age: float
    contraction_age: float
    center_contracting: float
    center_expansion_age: float
    center_contraction_age: float
    rho: float
    innovation_sd: float
    #: History's empirical distribution of growth-spell age at a randomly chosen
    #: month, split by axis. Two arrays, drawn from directly -- not a parametric
    #: fit, and not a chosen constant.
    opening_age_expanding: np.ndarray
    opening_age_contracting: np.ndarray

    def season_term(self, expanding: bool, age: int) -> float:
        """The centred season contribution to ``slope_t``."""
        log_age = math.log(max(int(age), 1))
        c = 0.0 if expanding else 1.0
        e = log_age if expanding else 0.0
        k = 0.0 if expanding else log_age
        return (
            self.contracting * (c - self.center_contracting)
            + self.expansion_age * (e - self.center_expansion_age)
            + self.contraction_age * (k - self.center_contraction_age)
        )


def curve_model_from_fit(fit: CurveFit, joint: JointFit) -> CurveModel:
    """Bundle a :class:`CurveFit` plus history's opening-age distribution."""
    expanding = joint.expanding[joint.fitted_from :]
    age = joint.age[joint.fitted_from :]
    coefficients = fit.coefficients
    return CurveModel(
        intercept=coefficients["intercept"],
        u_hat_loading=coefficients["u_hat_loading"],
        contracting=coefficients["contracting"],
        expansion_age=coefficients["expansion_age"],
        contraction_age=coefficients["contraction_age"],
        center_contracting=float(fit.centers[0]),
        center_expansion_age=float(fit.centers[1]),
        center_contraction_age=float(fit.centers[2]),
        rho=fit.rho,
        innovation_sd=fit.innovation_sd,
        opening_age_expanding=age[expanding].astype(np.int64),
        opening_age_contracting=age[~expanding].astype(np.int64),
    )


def week2_curve_model(panel: Panel) -> CurveModel:
    """Week 2's curve, rebuilt as a :class:`CurveModel` with the season term OFF.

    Its four numbers are read from ``panel.link`` -- the OLS intercept and
    loading and the moment-matched AR(1) -- so the ``week2`` engine below is
    week 2's engine and not an approximation of it.
    """
    return CurveModel(
        intercept=float(panel.link["intercept"]),
        u_hat_loading=float(panel.link["u_hat_loading"]),
        contracting=0.0,
        expansion_age=0.0,
        contraction_age=0.0,
        center_contracting=0.0,
        center_expansion_age=0.0,
        center_contraction_age=0.0,
        rho=float(panel.link["residual_ar1_rho"]),
        innovation_sd=float(panel.link["residual_innovation_sd"]),
        opening_age_expanding=np.ones(1, dtype=np.int64),
        opening_age_contracting=np.ones(1, dtype=np.int64),
    )


def run_chain_feedback(
    engine: FittedEngine,
    curve: CurveModel,
    states: np.ndarray,
    yoy: np.ndarray,
    u_hat: np.ndarray,
    residual: np.ndarray,
    rng: np.random.Generator,
    rng_age: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The closed loop over one decade. ``(season, expanding, z, slope_full)``.

    ``u_hat`` and ``residual`` are ``months + lag`` long: their heads are the
    decade's pre-history, drawn on the same tape, so the lagged curve reading for
    the decade's first ``lag`` months is a real earlier month rather than a value
    invented at the edge. The pre-history's season term is zero, which is its
    unconditional mean by the centring of the design.
    """
    months = int(states.shape[0])
    lag = int(engine.curve_lag_months)
    if u_hat.shape[0] != months + lag or residual.shape[0] != months + lag:
        raise FitError(f"u_hat and residual must carry {months + lag} months (lag {lag})")

    hot = (yoy > engine.era_threshold_pp).astype(np.int64)
    v_dd = trailing_drawdown(states[:, 3], V_DRAWDOWN_WINDOW_MONTHS)
    dummy = (v_dd <= engine.v_threshold).astype(np.float64)

    slope_full = np.empty(months + lag, dtype=np.float64)
    base = curve.intercept + curve.u_hat_loading * u_hat + residual
    slope_full[:lag] = base[:lag]  # season term at its unconditional mean = 0

    expanding = np.empty(months, dtype=bool)
    season = np.empty(months, dtype=np.int64)
    z = np.empty((months, 4), dtype=np.float64)

    is_expanding = bool(rng.random() < engine.initial_expanding_rate)
    # from its OWN stream: the seasons tape must be consumed exactly as week 2
    # consumed it, or the week2 engine below stops being week 2's engine
    pool = curve.opening_age_expanding if is_expanding else curve.opening_age_contracting
    age = int(pool[int(rng_age.integers(0, pool.size))])
    dwell = 1
    previous = -1
    for t in range(months):
        expanding[t] = is_expanding
        season[t] = (int(is_expanding) << 1) | int(hot[t])
        dwell = dwell + 1 if int(season[t]) == previous else 1
        previous = int(season[t])

        slope_full[lag + t] = base[lag + t] + curve.season_term(is_expanding, age)

        z_raw = np.array(
            [slope_full[t], states[t, 4], states[t, 0] - engine.pi_target, dummy[t]],
            dtype=np.float64,
        )
        z[t] = (z_raw - engine.z_mean) / engine.z_sd
        if rng.random() < hazard_probability(engine.beta, int(season[t]), dwell, z[t]):
            is_expanding = not is_expanding
            age = 1
        else:
            age += 1
    return season, expanding, z, slope_full


def simulate_batch_feedback(
    engine: FittedEngine,
    curve: CurveModel,
    climate: Any,
    *,
    n_decades: int,
    seed: int,
    months: int = DECADE_MONTHS,
    premise: Any | None = None,
) -> tuple[list[SimulatedDecade], dict[str, int]]:
    """``n_decades`` standalone L1+season+curve decades. No flesh, no sampler.

    The two-pass joinery is week 2's, unchanged: pass one runs the climate under
    a neutral cycle, the chain reads it, and pass two re-runs the SAME seed with
    the chain's own ``c_t`` forcing the credit-gap norm, after which the chain is
    re-run on pass two's states from the SAME re-opened stream -- so the accepted
    decade is a fixed point of one tape rather than a splice of two.
    """
    kept: list[SimulatedDecade] = []
    tally: dict[str, int] = {}
    attempt = 0
    budget = MAX_ATTEMPTS_PER_DECADE * n_decades
    lag = int(engine.curve_lag_months)
    while len(kept) < n_decades and attempt < budget:
        step = SPINE2_ATTEMPT_STRIDE * attempt
        l1_seed = seed + CLIMATE_OFFSET + step
        sim1 = simulate_decades(climate, 1, seed=l1_seed, months=months)
        theta = {name: float(sim1.params[name][0]) for name in PARAM_NAMES}

        def _stream(name: str, offset_step: int = step) -> np.random.Generator:
            return np.random.Generator(
                np.random.PCG64(seed + FEEDBACK_LAYER_OFFSETS[name] + offset_step)
            )

        rng_slope = _stream("slope")
        u_hat = ou_standardised(rng_slope, theta["hl_u"], theta["sigma_u"], months + lag)
        residual = ar1_path(rng_slope, curve.rho, curve.innovation_sd, months + lag)
        eps = ar1_path(
            _stream("inflnoise"),
            engine.infl_residual_rho,
            engine.infl_residual_innovation_sd,
            months,
        )

        yoy1 = sim1.states[0, :, 0] + eps
        season1, _expanding1, _z1, _slope1 = run_chain_feedback(
            engine,
            curve,
            sim1.states[0],
            yoy1,
            u_hat,
            residual,
            _stream("seasons"),
            _stream("openage"),
        )
        cycle = engine.season_cycle[season1].reshape(1, -1)
        sim2 = simulate_decades(climate, 1, seed=l1_seed, months=months, cycle=cycle)
        yoy2 = sim2.states[0, :, 0] + eps
        season, expanding, z, slope_full = run_chain_feedback(
            engine,
            curve,
            sim2.states[0],
            yoy2,
            u_hat,
            residual,
            _stream("seasons"),
            _stream("openage"),
        )
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
                    slope=slope_full[lag:],
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


# --------------------------------------------------------------------------- #
# the headline diagnostic
# --------------------------------------------------------------------------- #


def inverted_month_composition(
    labels: np.ndarray,
    yoy: np.ndarray,
    tight: np.ndarray,
    expanding: np.ndarray,
    sealed: dict[str, Any],
) -> dict[str, Any]:
    """One side of the diagnostic that identified the frontier.

    ``share_of_tight_months_that_are_expanding`` against
    ``share_of_all_months_that_are_expanding``. In history the first is ABOVE the
    second -- the inverted curve sits ahead of the turn. Week 2's engine put it
    far below, which is the whole of its T1 shortfall. Eligibility is the judge's
    own: a defined trailing inflation, and the last ``k`` months dropped because
    T1's lookahead cannot see past the window's end.
    """
    k = int(sealed["parameters"]["k_months"])
    n = int(np.asarray(labels).size)
    eligible = ~np.isnan(np.asarray(yoy, dtype=np.float64))
    eligible[max(n - k, 0) :] = False
    exp_arr = np.asarray(expanding, dtype=bool)
    tight_arr = np.asarray(tight, dtype=bool)
    n_tight = int((eligible & tight_arr).sum())
    return {
        "months": int(eligible.sum()),
        "tight_months": n_tight,
        "share_of_tight_months_that_are_expanding": (
            float((eligible & tight_arr & exp_arr).sum() / n_tight) if n_tight else float("nan")
        ),
        "share_of_all_months_that_are_expanding": (
            float((eligible & exp_arr).sum() / eligible.sum()) if eligible.sum() else float("nan")
        ),
    }


def composition_history(panel: Panel, joint: JointFit, sealed: dict[str, Any]) -> dict[str, Any]:
    """The historical side, measured exactly as week 2 measured it."""
    return inverted_month_composition(
        np.asarray(panel.labels),
        panel.yoy,
        np.asarray(panel.slope < 0.0),
        joint.expanding,
        sealed,
    )


def composition_generated(decades: list[SimulatedDecade], sealed: dict[str, Any]) -> dict[str, Any]:
    """The generated side, pooled decade by decade so no lookahead crosses an edge."""
    per = [
        inverted_month_composition(
            np.asarray(d.labels),
            to_decade(d).yoy,
            d.slope < 0.0,
            np.array([EXPANDING[int(s)] for s in d.season], dtype=bool),
            sealed,
        )
        for d in decades
    ]
    months = sum(r["months"] for r in per)
    tight = sum(r["tight_months"] for r in per)
    tight_expanding = sum(
        r["share_of_tight_months_that_are_expanding"] * r["tight_months"]
        for r in per
        if r["tight_months"]
    )
    all_expanding = sum(r["share_of_all_months_that_are_expanding"] * r["months"] for r in per)
    return {
        "months": months,
        "tight_months": tight,
        "share_of_tight_months_that_are_expanding": (
            float(tight_expanding / tight) if tight else float("nan")
        ),
        "share_of_all_months_that_are_expanding": (
            float(all_expanding / months) if months else float("nan")
        ),
    }


def growth_spell_lengths(joint: JointFit, decades: list[SimulatedDecade]) -> dict[str, Any]:
    """Growth-axis spell lengths, history beside the generated batch.

    The season term is a function of ``log(age)``, so it can only express itself
    over the ages the simulator actually visits. If the generated engine's
    expansions are a fraction of history's length, a coefficient fitted on
    history's long expansions arrives at generation time with nothing to act on
    -- and that would be a fact about the CHAIN's flip rate, not about the curve
    equation. Measured here rather than inferred, and the statistic that matters
    is the mean of ``log(age)`` per axis: that is literally what the fitted
    loading multiplies.
    """

    def _rows(blocks: list[np.ndarray]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for axis, want in (("expanding", True), ("contracting", False)):
            spells: list[int] = []
            log_ages: list[float] = []
            for block in blocks:
                age = spell_age(block)
                log_ages.extend(
                    float(np.log(max(int(a), 1)))
                    for a, e in zip(age, block, strict=True)
                    if bool(e) == want
                )
                run = 0
                for t in range(block.size):
                    if bool(block[t]) == want:
                        run += 1
                    elif run:
                        spells.append(run)
                        run = 0
                if run:
                    spells.append(run)
            arr = np.asarray(spells, dtype=np.float64)
            out[axis] = {
                "n_spells": int(arr.size),
                "months": len(log_ages),
                "mean_spell_months": float(arr.mean()) if arr.size else float("nan"),
                "median_spell_months": float(np.median(arr)) if arr.size else float("nan"),
                "max_spell_months": float(arr.max()) if arr.size else float("nan"),
                "mean_log_age": float(np.mean(log_ages)) if log_ages else float("nan"),
            }
        return out

    return {
        "historical_panel": _rows([np.asarray(joint.expanding, dtype=bool)]),
        "generated_batch": _rows(
            [np.array([EXPANDING[int(s)] for s in d.season], dtype=bool) for d in decades]
        ),
        "reading": (
            "compare mean_log_age: it is exactly what the fitted expansion-age and "
            "contraction-age loadings multiply, so a shortfall there is a ceiling on how "
            "much of the season term can ever reach a generated curve"
        ),
    }


def o1_decomposition(joint: JointFit, decades: list[SimulatedDecade]) -> dict[str, Any]:
    """Where O1's clockwise fraction comes from, split by the axis that moved.

    The clock is ``recovery -> expansion -> stagflation -> recession -> recovery``
    and it ALTERNATES axes: two of its four steps are inflation crossings
    (recovery->expansion, stagflation->recession) and two are growth flips
    (expansion->stagflation, recession->recovery). So a growth flip is clockwise
    if and only if it happens while inflation is HOT, and an inflation crossing is
    clockwise if and only if it happens while the economy is EXPANDING for the
    upward crossing and CONTRACTING for the downward one.

    That makes O1 a test of the PHASE between the two dials, not of either dial
    alone -- and this splits the fraction by move type on both sides so a
    shortfall can be attributed to one of them instead of to "the ordering".
    """

    def _rows(cells: np.ndarray) -> dict[str, Any]:
        arr = np.asarray(cells, dtype=np.int64)
        counts = {"growth_flip": [0, 0], "inflation_crossing": [0, 0], "diagonal": [0, 0]}
        for t in range(1, arr.size):
            a, b = int(arr[t - 1]), int(arr[t])
            if a < 0 or b < 0 or a == b:
                continue
            dg = EXPANDING[a] != EXPANDING[b]
            dh = HOT[a] != HOT[b]
            kind = "diagonal" if (dg and dh) else ("growth_flip" if dg else "inflation_crossing")
            counts[kind][0] += 1
            if (a, b) in CLOCKWISE:
                counts[kind][1] += 1
        total = sum(v[0] for v in counts.values())
        clockwise = sum(v[1] for v in counts.values())
        return {
            "transitions": total,
            "clockwise": clockwise,
            "clockwise_fraction": float(clockwise / total) if total else float("nan"),
            "by_move": {
                kind: {
                    "transitions": v[0],
                    "clockwise": v[1],
                    "clockwise_fraction": float(v[1] / v[0]) if v[0] else float("nan"),
                    "share_of_all_transitions": float(v[0] / total) if total else float("nan"),
                }
                for kind, v in counts.items()
            },
        }

    per = [_rows(d.season) for d in decades]
    pooled: dict[str, Any] = {
        "transitions": sum(r["transitions"] for r in per),
        "clockwise": sum(r["clockwise"] for r in per),
        "by_move": {},
    }
    pooled["clockwise_fraction"] = (
        float(pooled["clockwise"] / pooled["transitions"])
        if pooled["transitions"]
        else float("nan")
    )
    for kind in ("growth_flip", "inflation_crossing", "diagonal"):
        n = sum(r["by_move"][kind]["transitions"] for r in per)
        c = sum(r["by_move"][kind]["clockwise"] for r in per)
        pooled["by_move"][kind] = {
            "transitions": n,
            "clockwise": c,
            "clockwise_fraction": float(c / n) if n else float("nan"),
            "share_of_all_transitions": (
                float(n / pooled["transitions"]) if pooled["transitions"] else float("nan")
            ),
        }
    return {
        "historical_panel": _rows(joint.cells),
        "generated_batch": pooled,
        "reading": (
            "a growth flip is clockwise iff inflation is hot when it happens, and an "
            "inflation crossing is clockwise iff it happens on the matching growth axis. So "
            "O1 measures the PHASE between the growth dial and the inflation dial. Compare "
            "the per-move clockwise fractions: a shortfall concentrated in growth flips says "
            "downturns do not begin hot, which is a growth->inflation channel and NOT the "
            "season->curve channel this module fits"
        ),
    }


def curve_variance_decomposition(
    curve: CurveModel, joint: JointFit, decades: list[SimulatedDecade]
) -> dict[str, Any]:
    """How much of the curve the season term can actually move.

    The question the frontier turns on: the feedback is fitted, significant and
    signed correctly, so why does the generated curve only travel part of the way
    to history's season-conditional shape? The answer is a ratio of standard
    deviations, and it is measured on both sides -- the season term against the
    AR(1) residual it has to compete with. A term worth a fifth of a residual
    standard deviation cannot reorganise a curve however right its sign is.
    """
    hist_term = np.array(
        [
            curve.season_term(bool(e), int(a))
            for e, a in zip(
                joint.expanding[joint.fitted_from :], joint.age[joint.fitted_from :], strict=True
            )
        ]
    )
    sim_terms: list[float] = []
    for d in decades:
        exp_arr = np.array([EXPANDING[int(s)] for s in d.season], dtype=bool)
        age = spell_age(exp_arr)
        sim_terms.extend(
            curve.season_term(bool(e), int(a)) for e, a in zip(exp_arr, age, strict=True)
        )
    residual_stationary_sd = float(
        curve.innovation_sd / math.sqrt(max(1.0 - curve.rho * curve.rho, 1e-12))
    )
    sim_sd = float(np.std(sim_terms))
    return {
        "season_term_sd_on_history_pp": float(np.std(hist_term)),
        "season_term_sd_on_generated_pp": sim_sd,
        "season_term_range_on_generated_pp": [float(np.min(sim_terms)), float(np.max(sim_terms))],
        "u_hat_contribution_sd_pp": abs(float(curve.u_hat_loading)),
        "residual_stationary_sd_pp": residual_stationary_sd,
        "season_term_sd_over_residual_sd": (
            sim_sd / residual_stationary_sd if residual_stationary_sd else float("nan")
        ),
        "reading": (
            "u_hat is simulated with unit stationary variance, so its contribution's sd IS "
            "the absolute loading. Set the season term's sd beside the residual's: that "
            "ratio is the ceiling on how far a correctly-signed, significant feedback can "
            "reorganise the generated curve"
        ),
    }


def curve_by_season(
    panel: Panel, joint: JointFit, decades: list[SimulatedDecade]
) -> dict[str, Any]:
    """History's season-conditional curve distribution, beside the simulated one.

    Mean slope and inverted share, per season and per growth axis -- the object
    the season term is supposed to reproduce, reported so the fix can be read
    directly rather than only through T1.
    """

    def _rows(cells: np.ndarray, slope: np.ndarray, expanding: np.ndarray) -> dict[str, Any]:
        out: dict[str, Any] = {"by_season": {}, "by_growth_axis": {}}
        for s in range(4):
            mask = np.asarray(cells) == s
            out["by_season"][QUADRANTS[s]] = {
                "months": int(mask.sum()),
                "mean_slope_pp": float(slope[mask].mean()) if mask.any() else float("nan"),
                "inverted_share": float((slope[mask] < 0.0).mean()) if mask.any() else float("nan"),
            }
        for name, mask in (
            ("expanding", np.asarray(expanding, dtype=bool)),
            ("contracting", ~np.asarray(expanding, dtype=bool)),
        ):
            out["by_growth_axis"][name] = {
                "months": int(mask.sum()),
                "mean_slope_pp": float(slope[mask].mean()) if mask.any() else float("nan"),
                "inverted_share": float((slope[mask] < 0.0).mean()) if mask.any() else float("nan"),
            }
        return out

    hist = _rows(joint.cells, panel.slope, joint.expanding)
    gen_cells = np.concatenate([d.season for d in decades])
    gen_slope = np.concatenate([d.slope for d in decades])
    gen_expanding = np.array([EXPANDING[int(s)] for s in gen_cells], dtype=bool)
    return {"historical_panel": hist, "generated_batch": _rows(gen_cells, gen_slope, gen_expanding)}


# --------------------------------------------------------------------------- #
# label stability, on the JOINT fit
# --------------------------------------------------------------------------- #


def label_stability_joint(panel: Panel, joint: JointFit) -> dict[str, Any]:
    """The sealed obligation's perturbation grid, re-run on the joint fit.

    Week 2 tracked one statistic, ``cov_expanding[curve_slope]``. The joint model
    has three more coefficients that the classifier's dials can move -- the
    season term is a function OF the labels -- so every arm now refits both
    blocks and every arm reports all four, each in units of its own baseline
    standard error. The verdict rule is unchanged and is the campaign's:
    a statistic that moves by more than its own standard error across arms
    escalates to soft labels, and both are reported.
    """
    base_values = {
        TRANSMISSION_KEY: float(joint.hazard["coefficients"][TRANSMISSION_KEY]),
        **{k: joint.curve.coefficients[k] for k in FEEDBACK_KEYS},
    }
    base_errors = {
        TRANSMISSION_KEY: float(joint.hazard["standard_errors"][TRANSMISSION_KEY]),
        **{k: joint.curve.standard_errors[k] for k in FEEDBACK_KEYS},
    }

    def _arm(cells: np.ndarray, labels: np.ndarray, weights: np.ndarray | None) -> dict[str, Any]:
        hazard = fit_arm(cells, panel.z_lagged(joint.lag_months), weights=weights)
        expanding = growth_axis(labels)
        age = spell_age(expanding)
        start = first_spell_end(expanding) + 1
        # the same weights reach the curve block, so the two down-weighting arms
        # cannot report a spurious zero movement for the feedback coefficients
        curve = fit_curve(
            panel.slope[start:],
            curve_design(panel.u_hat, expanding, age)[start:],
            feedback=True,
            weights=None if weights is None else np.asarray(weights, np.float64)[start:],
        )
        values = {
            TRANSMISSION_KEY: float(hazard["coefficients"][TRANSMISSION_KEY]),
            **{k: curve.coefficients[k] for k in FEEDBACK_KEYS},
        }
        return {
            "values": values,
            "standard_errors": {
                TRANSMISSION_KEY: float(hazard["standard_errors"][TRANSMISSION_KEY]),
                **{k: curve.standard_errors[k] for k in FEEDBACK_KEYS},
            },
            "moves_by_se": {
                k: (values[k] - base_values[k]) / base_errors[k] if base_errors[k] else float("nan")
                for k in values
            },
            "curve_loglik": curve.loglik,
            "hazard_loglik": float(hazard["loglik"]),
        }

    arms: dict[str, Any] = {}
    for name, d_inf, d_grw in STABILITY_ARMS:
        cells = relabel(panel, d_inf, d_grw)
        labels = panel.labels if d_grw == 0.0 else _perturbed_labels(panel, d_grw)
        arms[name] = _arm(cells, labels, None)
    for name, weights in (
        ("borderline_downweighted", borderline_weights(panel)),
        ("soft_labels_escalation", soft_label_weights(panel)),
    ):
        arms[name] = _arm(relabel(panel, 0.0, 0.0), panel.labels, weights)

    threshold_arms = [arms[name] for name, _, _ in STABILITY_ARMS if name != "baseline"]
    per_statistic: dict[str, Any] = {}
    for key in base_values:
        worst = max(threshold_arms, key=lambda r, k=key: abs(r["moves_by_se"][k]))
        worst_name = next(n for n, row in arms.items() if row is worst)
        downweighted = arms["borderline_downweighted"]["moves_by_se"][key]
        escalate = bool(abs(worst["moves_by_se"][key]) > 1.0 or abs(downweighted) > 1.0)
        per_statistic[key] = {
            "baseline_value": base_values[key],
            "baseline_standard_error": base_errors[key],
            "worst_threshold_arm": worst_name,
            "worst_threshold_arm_moves_by_se": worst["moves_by_se"][key],
            "borderline_downweighted_moves_by_se": downweighted,
            "soft_labels_moves_by_se": arms["soft_labels_escalation"]["moves_by_se"][key],
            "range_across_arms": [
                min(row["values"][key] for row in arms.values()),
                max(row["values"][key] for row in arms.values()),
            ],
            "escalated": escalate,
            "verdict": (
                "UNSTABLE -- escalated to soft labels, both reported"
                if escalate
                else "STABLE -- every arm moves it by less than one of its own standard errors"
            ),
        }
    return {
        "statistics": list(base_values),
        "arms": arms,
        "per_statistic": per_statistic,
        "escalation_rule": (
            "the sealed escalation path: if a tracked statistic moves by more than its own "
            "standard error across arms, refit with soft labels (each month weighted by "
            "classification confidence) and report both"
        ),
        "any_escalated": bool(any(r["escalated"] for r in per_statistic.values())),
    }


def _perturbed_labels(panel: Panel, growth_delta_pp: float) -> np.ndarray:
    """``regime_ruleset_v1`` labels under a moved growth dial.

    ``spine_v2_fit.relabel`` returns season CELLS; the curve block needs the
    LABELS behind them, because its growth axis is defined on the warm-up months
    too. This calls the same private helper rather than writing a second
    labeller.
    """
    from spine_v2_fit import _relabel_growth

    return _relabel_growth(panel, growth_delta_pp)


# --------------------------------------------------------------------------- #
# the frontier over FEEDBACK strength
# --------------------------------------------------------------------------- #

#: Multipliers applied to the three FITTED season coefficients together. 1.0 is
#: the fit and 0.0 switches the feedback off. The rest map the trade-off the
#: campaign's frontier discipline requires when a bar cannot be reached -- every
#: row is a COUNTERFACTUAL and none of them is a fitted value.
#:
#: **What x0.0 is, and what it is NOT.** It is the primary engine with its three
#: season loadings set to zero, so it keeps the UNRESTRICTED fit's intercept,
#: ``u_hat`` loading and residual AR(1). It is therefore NOT bit-identical to
#: ``ml_link``, which refits those three under the restriction; the two are
#: reported side by side rather than conflated, and the gap between them is the
#: nuisance-parameter difference, not a feedback effect. What x0.0 does buy is
#: the sweep's own baseline on a held tape: every other row differs from it in
#: the three loadings and in nothing else.
FEEDBACK_MULTIPLIERS: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def scale_feedback(curve: CurveModel, multiplier: float) -> CurveModel:
    """The same curve with all three season loadings scaled, and nothing else."""
    return replace(
        curve,
        contracting=curve.contracting * float(multiplier),
        expansion_age=curve.expansion_age * float(multiplier),
        contraction_age=curve.contraction_age * float(multiplier),
    )


def feedback_frontier(
    engine: FittedEngine,
    curve: CurveModel,
    climate: Any,
    sealed: dict[str, Any],
    *,
    n_decades: int,
    premise: Any | None,
    arm: str,
) -> list[dict[str, Any]]:
    """T1, O1 and the four dwell medians across the feedback frontier.

    Week 2 mapped its frontier along transmission strength and found T1 and O1 in
    direct opposition. This maps the new axis: how much season-to-curve feedback
    the engine carries. Only the three season loadings move; the hazard, the L1
    link, the residual and every seed are held.
    """
    rows: list[dict[str, Any]] = []
    for multiplier in FEEDBACK_MULTIPLIERS:
        scaled = scale_feedback(curve, multiplier)
        decades, tally = simulate_batch_feedback(
            engine, scaled, climate, n_decades=n_decades, seed=VERIFY_SEED, premise=premise
        )
        verdicts = judge_batch(decades, sealed)
        composition = composition_generated(decades, sealed)
        rows.append(
            {
                "arm": arm,
                "feedback_multiplier": float(multiplier),
                "coefficients": {
                    "contracting": scaled.contracting,
                    "expansion_age": scaled.expansion_age,
                    "contraction_age": scaled.contraction_age,
                },
                "T1_lift": float(verdicts["T1"]["value"]),
                "T1_pass": bool(verdicts["T1"]["pass"]),
                "O1_clockwise": float(verdicts["O1"]["value"]),
                "O1_pass": bool(verdicts["O1"]["pass"]),
                "D1_recession_median": float(verdicts["D1"]["value"]),
                "D2_stagflation_median": float(verdicts["D2"]["value"]),
                "D3_recovery_median": float(verdicts["D3"]["value"]),
                "D4_expansion_median": float(verdicts["D4"]["value"]),
                "D_all_pass": bool(all(verdicts[c]["pass"] for c in ("D1", "D2", "D3", "D4"))),
                "all_six_pass": bool(
                    all(verdicts[c]["pass"] for c in UNCONDITIONAL_BARS + PREMISE_BARS)
                ),
                "share_of_tight_months_that_are_expanding": composition[
                    "share_of_tight_months_that_are_expanding"
                ],
                "attempts": int(tally.get("attempts", n_decades)),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #

#: The four engines, in the order the report reads them. ``feedback`` is the
#: PRIMARY -- declared in the module docstring before any bar was read.
ENGINE_NAMES = ("week2", "ml_link", "ols_feedback", "feedback")
#: The one the verdict is taken on. The other three are attribution.
PRIMARY_ENGINE = "feedback"


def _engine_rows(
    engine: FittedEngine,
    curve: CurveModel,
    climate: Any,
    sealed: dict[str, Any],
    panel: Panel,
    joint: JointFit,
    *,
    n_decades: int,
    premise: Any,
) -> dict[str, Any]:
    """One engine, both arms, six bars, and the composition diagnostic."""
    accepted, tally = simulate_batch_feedback(
        engine, curve, climate, n_decades=n_decades, seed=VERIFY_SEED, premise=premise
    )
    unconditional, tally_u = simulate_batch_feedback(
        engine, curve, climate, n_decades=n_decades, seed=VERIFY_SEED, premise=None
    )
    verdicts_p = judge_batch(accepted, sealed)
    verdicts_u = judge_batch(unconditional, sealed)
    return {
        "premise_accepted": {
            "premise_acceptance": tally,
            "readings": bar_readings(verdicts_p),
            "verdicts_full": verdicts_p,
            "inverted_month_composition": composition_generated(accepted, sealed),
            "curve_by_season": curve_by_season(panel, joint, accepted),
            "growth_spell_lengths": growth_spell_lengths(joint, accepted),
            "curve_variance_decomposition": curve_variance_decomposition(curve, joint, accepted),
            "o1_decomposition": o1_decomposition(joint, accepted),
        },
        "unconditional": {
            "premise_acceptance": tally_u,
            "readings": bar_readings(verdicts_u),
            "verdicts_full": verdicts_u,
            "inverted_month_composition": composition_generated(unconditional, sealed),
            "curve_by_season": curve_by_season(panel, joint, unconditional),
            "growth_spell_lengths": growth_spell_lengths(joint, unconditional),
            "curve_variance_decomposition": curve_variance_decomposition(
                curve, joint, unconditional
            ),
            "o1_decomposition": o1_decomposition(joint, unconditional),
        },
        "amended_verdict": {
            **{code: bool(verdicts_u[code]["pass"]) for code in UNCONDITIONAL_BARS},
            **{code: bool(verdicts_p[code]["pass"]) for code in PREMISE_BARS},
        },
    }


def _amended_summary(rows: dict[str, Any]) -> dict[str, Any]:
    """The six bars under AM-SPV2-2026-08-17-001, one row each."""
    out: list[dict[str, Any]] = []
    for code in UNCONDITIONAL_BARS + PREMISE_BARS:
        arm = "unconditional" if code in UNCONDITIONAL_BARS else "premise_accepted"
        row = next(r for r in rows[arm]["readings"] if r["bar"] == code)
        out.append(
            {
                "bar": code,
                "arm": arm,
                "sealed_band": row["sealed_band"],
                "measured": row["measured"],
                "pass": row["pass"],
            }
        )
    return {
        "amendment": AMENDMENT_ID,
        "rows": out,
        "all_six_pass": bool(all(r["pass"] for r in out)),
    }


def _hazard_identity_check(joint: JointFit) -> dict[str, Any]:
    """Is the hazard block bit-for-bit week 2's? It has to be, and this says so.

    The joint likelihood block-diagonalises, so adding the season term cannot
    move a hazard coefficient. If this check ever fails, the feedback has been
    implemented as a re-fit of the transmission channel and every frontier claim
    in the report is void.
    """
    week2 = json.loads(WEEK2_PARAMS_PATH.read_text(encoding="utf-8"))
    before = week2["fit"]["coefficients"]
    now = joint.hazard["coefficients"]
    diffs = {k: abs(float(now[k]) - float(before[k])) for k in PARAM_LABELS}
    worst = max(diffs.values())
    return {
        "week_2_artifact": str(WEEK2_PARAMS_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "max_absolute_difference": worst,
        # week 2's artifact is rounded to 12 places on output, so that is the
        # resolution this comparison can possibly have
        "identical_to_the_committed_rounding": bool(worst <= 5e-13),
        "why_it_must_hold": (
            "the joint log-likelihood is L_hazard(beta) + L_curve(c, rho, sigma) and the "
            "season path is OBSERVED on the panel, so no curve parameter appears in the "
            "hazard block; adding the feedback cannot move a hazard coefficient"
        ),
    }


def main() -> int:
    streams = assert_feedback_tapes_distinct()
    sealed = load_sealed()
    n_decades = int(sealed["bars"].get("n_seeds", DEFAULT_N_DECADES))

    panel = build_panel()
    cells = season_cells(panel.labels, panel.yoy, panel.era_threshold_pp)
    lag = int(select_curve_lag(panel, cells)["selected_lag_months"])
    joint = fit_joint(panel, cells, lag)
    stag = measure_stag_spell_rate(panel, cells)
    engine = build_engine(panel, joint.hazard, cells, lag, stag)

    curves = {
        "week2": week2_curve_model(panel),
        "ml_link": replace(
            curve_model_from_fit(joint.curve_restricted, joint),
            contracting=0.0,
            expansion_age=0.0,
            contraction_age=0.0,
        ),
        "ols_feedback": curve_model_from_fit(joint.curve_ols, joint),
        "feedback": curve_model_from_fit(joint.curve, joint),
    }

    climate, _regimes = _pinned_layers()
    premise = _load_premise()
    engines = {
        name: _engine_rows(
            engine,
            curves[name],
            climate,
            sealed,
            panel,
            joint,
            n_decades=n_decades,
            premise=premise,
        )
        for name in ENGINE_NAMES
    }
    summary = _amended_summary(engines[PRIMARY_ENGINE])
    stability = label_stability_joint(panel, joint)
    history_composition = composition_history(panel, joint, sealed)
    frontier_rows = feedback_frontier(
        engine,
        curves[PRIMARY_ENGINE],
        climate,
        sealed,
        n_decades=n_decades,
        premise=None,
        arm="unconditional",
    ) + feedback_frontier(
        engine,
        curves[PRIMARY_ENGINE],
        climate,
        sealed,
        n_decades=n_decades,
        premise=premise,
        arm="premise_accepted",
    )

    lr = joint.lr_statistic
    payload: dict[str, Any] = {
        "schema": "spine-v2-feedback-params-1",
        "purpose": (
            "spine v2 week 3: a season-state term added to the curve process and fitted "
            "jointly with the season-transition hazard by maximum likelihood, and the "
            "sealed in-model verification re-run under AM-SPV2-2026-08-17-001. A1/A2/R1/R2 "
            "need the flesh and are week 4."
        ),
        "spec": "docs/superpowers/specs/2026-08-17-spine-v2-exam.md",
        "seal": "docs/superpowers/specs/spine-v2-prereg.json",
        "amendment": {
            "id": AMENDMENT_ID,
            "post_hoc": True,
            "judged_on_unconditional_batch": list(UNCONDITIONAL_BARS),
            "judged_on_premise_accepted_batch": list(PREMISE_BARS),
        },
        "primary_engine": {
            "name": PRIMARY_ENGINE,
            "declared_before_any_bar_was_read": True,
            "why": (
                "the exact-ML joint fit is the estimator the joint likelihood names. The "
                "OLS arm is an estimator-sensitivity disclosure and cannot supply a verdict, "
                "however it reads -- reporting whichever of two estimators passes would be "
                "tuning past a conflict"
            ),
        },
        "week_2_record": str(WEEK2_PARAMS_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "seal_files_untouched": sorted(sealed["hashed_files"]),
        "status": "FIT-VERIFIED" if summary["all_six_pass"] else "FRONTIER",
        "panel": panel.diagnostics,
        "model": {
            "curve_form": (
                "slope_t = c0 + c_u*u_hat_t + c_C*(C_t - Cbar) + c_E*(E_t - Ebar) "
                "+ c_K*(K_t - Kbar) + e_t, e_t = rho*e_{t-1} + eta_t, eta ~ N(0, sigma^2); "
                "C = 1[contracting], E = log(growth-spell age) on expanding months, "
                "K = log(growth-spell age) on contracting months; C, E, K centred on their "
                "own sample means so the season term has mean zero on the panel"
            ),
            "hazard_form": (
                "unchanged from week 2: logit h_t = a_[season] + b_[season]*log(dwell_t) "
                "+ z_t' g_[growth axis]"
            ),
            "joint_likelihood": (
                "L(beta, c, rho, sigma) = L_hazard(beta) + L_curve(c, rho, sigma), maximised "
                "as one object; it block-diagonalises because BOTH paths are observed on the "
                "panel (the season enters the curve block as a regressor and the slope enters "
                "the hazard block as a regressor), so the cross-block information is exactly "
                "zero and the joint maximum is attained blockwise"
            ),
            "curve_estimator": (
                "exact Gaussian AR(1) maximum likelihood: the first observation enters "
                "through its own stationary law, beta and sigma are closed-form at each rho "
                "by the Prais-Winsten transform, and rho is found by a coarse scan plus "
                "golden section -- deterministic, no random start"
            ),
            "curve_at_risk_rule": (
                "the panel's first growth-axis spell is dropped: its start is unobserved so "
                "its age is unknown, the same left truncation the hazard block already "
                "applies, so a month's age means the same thing in both blocks"
            ),
            "opening_age_rule": (
                "a simulated decade's opening growth-spell age is drawn from history's own "
                "empirical distribution of age at a randomly chosen month, conditioned on "
                "the opening axis -- length-biased exactly as a random calendar month is"
            ),
            "state_space": list(QUADRANTS),
            "covariates": list(COVARIATES),
            "curve_parameter_labels": list(CURVE_PARAM_LABELS),
            "curve_lag_months": lag,
        },
        "fit": {
            "hazard": {
                "coefficients": joint.hazard["coefficients"],
                "standard_errors": joint.hazard["standard_errors"],
                "t_ratios": {
                    k: joint.hazard["coefficients"][k] / joint.hazard["standard_errors"][k]
                    for k in PARAM_LABELS
                },
                "loglik": joint.hazard["loglik"],
                "n_at_risk_months": joint.hazard["n_obs"],
                "n_growth_axis_flips": joint.hazard["n_events"],
            },
            "hazard_block_identical_to_week_2": _hazard_identity_check(joint),
            "curve": {
                "coefficients": joint.curve.coefficients,
                "standard_errors": joint.curve.standard_errors,
                "t_ratios": {
                    k: (
                        joint.curve.coefficients[k] / joint.curve.standard_errors[k]
                        if joint.curve.standard_errors[k]
                        else None
                    )
                    for k in CURVE_PARAM_LABELS
                },
                "centers": {
                    "contracting": float(joint.curve.centers[0]),
                    "expansion_age": float(joint.curve.centers[1]),
                    "contraction_age": float(joint.curve.centers[2]),
                },
                "residual_ar1_rho": joint.curve.rho,
                "residual_ar1_rho_se": joint.curve.rho_se,
                "residual_innovation_sd": joint.curve.innovation_sd,
                "residual_innovation_sd_se": joint.curve.innovation_sd_se,
                "loglik": joint.curve.loglik,
                "r_squared": joint.curve.r_squared,
                "n_months": joint.curve.n_months,
                "fitted_from_month_index": joint.fitted_from,
            },
            "curve_restricted_no_feedback": {
                "coefficients": joint.curve_restricted.coefficients,
                "standard_errors": joint.curve_restricted.standard_errors,
                "residual_ar1_rho": joint.curve_restricted.rho,
                "residual_innovation_sd": joint.curve_restricted.innovation_sd,
                "loglik": joint.curve_restricted.loglik,
                "r_squared": joint.curve_restricted.r_squared,
            },
            "curve_ols_disclosure_not_a_verdict": {
                "estimator": (
                    "week 2's own: OLS in levels plus an AR(1) matched to the residual's "
                    "lag-1 autocorrelation and innovation sd, applied to the SAME five-column "
                    "design so the two estimators are compared on one model"
                ),
                "cannot_supply_a_verdict": True,
                "standard_errors_understated": (
                    "plain OLS errors; they ignore the residual autocorrelation that is the "
                    "whole reason exact ML disagrees, so they are for side-by-side reading "
                    "of the coefficient vectors and not for inference"
                ),
                "coefficients": joint.curve_ols.coefficients,
                "standard_errors": joint.curve_ols.standard_errors,
                "residual_ar1_rho": joint.curve_ols.rho,
                "residual_innovation_sd": joint.curve_ols.innovation_sd,
                "r_squared": joint.curve_ols.r_squared,
            },
            "week_2_curve_link_for_reference": panel.link,
            "joint_loglik": joint.joint_loglik,
            "likelihood_ratio_no_season_feedback": {
                "restriction": "c_C = c_E = c_K = 0 (week 2's curve, nested exactly)",
                "statistic": lr,
                "degrees_of_freedom": 3,
                "p_value": chi2_sf_df3(lr),
            },
        },
        "engine": {
            "season_cycle": engine.season_cycle,
            "initial_expanding_rate": engine.initial_expanding_rate,
            "inflation_residual_ar1_rho": engine.infl_residual_rho,
            "inflation_residual_innovation_sd": engine.infl_residual_innovation_sd,
            "valuation_drawdown_threshold": engine.v_threshold,
            "curve_lag_months": engine.curve_lag_months,
            "stag_spell_rate": engine.stag_spell_rate,
            "covariate_standardisation": {"mean": panel.z_mean, "sd": panel.z_sd},
        },
        "label_stability": stability,
        "verification": {
            "n_decades": n_decades,
            "months_per_decade": DECADE_MONTHS,
            "seed": VERIFY_SEED,
            "streams": streams,
            "premise": premise.model_dump(),
            "bars_measured": list(UNCONDITIONAL_BARS + PREMISE_BARS),
            "bars_deferred_to_week_4": ["A1", "A2", "R1", "R2"],
            "amended_summary": summary,
            "engines": engines,
            "feedback_frontier": {
                "multipliers": list(FEEDBACK_MULTIPLIERS),
                "what_moves": (
                    "ONLY the three fitted season loadings, scaled together; the hazard, the "
                    "L1 link, the AR(1) residual and every seed are held, so a row is a "
                    "counterfactual about feedback strength and nothing else"
                ),
                "what_x0_is": (
                    "the primary engine with the three loadings zeroed, keeping the "
                    "UNRESTRICTED fit's intercept, u_hat loading and residual AR(1). It is "
                    "NOT ml_link, which refits those under the restriction -- the two are "
                    "reported side by side and the gap between them is the nuisance "
                    "parameters, not a feedback effect"
                ),
                "rows": frontier_rows,
            },
            "inverted_month_composition_history": history_composition,
            "headline_diagnostic": {
                "statistic": "share of inverted-curve months that are EXPANDING",
                "history": history_composition["share_of_tight_months_that_are_expanding"],
                "history_base_rate": history_composition["share_of_all_months_that_are_expanding"],
                **{
                    name: {
                        arm: engines[name][arm]["inverted_month_composition"][
                            "share_of_tight_months_that_are_expanding"
                        ]
                        for arm in ("premise_accepted", "unconditional")
                    }
                    for name in ENGINE_NAMES
                },
            },
        },
    }
    payload = _round(payload)
    PARAMS_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {PARAMS_PATH.relative_to(_REPO_ROOT)}")
    print(f"status: {payload['status']}  (amendment {AMENDMENT_ID})")
    print("curve equation (exact AR(1) ML):")
    for name in CURVE_PARAM_LABELS:
        b = joint.curve.coefficients[name]
        se = joint.curve.standard_errors[name]
        print(f"  {name:20s} {b:+9.4f}  se {se:7.4f}  t {b / se if se else float('nan'):+6.2f}")
    print(
        f"  rho {joint.curve.rho:+.4f} (se {joint.curve.rho_se:.4f})  "
        f"innovation sd {joint.curve.innovation_sd:.4f} "
        f"(se {joint.curve.innovation_sd_se:.4f})  R^2 {joint.curve.r_squared:.4f}"
    )
    print(
        f"  LR against no feedback: {lr:.4f} on 3 df, p = {chi2_sf_df3(lr):.3e}  "
        f"(restricted loglik {joint.curve_restricted.loglik:.4f}, "
        f"full {joint.curve.loglik:.4f})"
    )
    check = payload["fit"]["hazard_block_identical_to_week_2"]
    print(
        f"  hazard block identical to week 2: {check['identical_to_the_committed_rounding']} "
        f"(max |diff| {check['max_absolute_difference']:.3e})"
    )
    print("headline diagnostic -- share of inverted months that are EXPANDING:")
    hd = payload["verification"]["headline_diagnostic"]
    print(f"  history {hd['history']:.4f} (base rate {hd['history_base_rate']:.4f})")
    for name in ENGINE_NAMES:
        print(
            f"  {name:9s} premise {hd[name]['premise_accepted']:.4f}   "
            f"unconditional {hd[name]['unconditional']:.4f}"
        )
    print("bars under the amendment (T1/O1 unconditional, D1-D4 premise-accepted):")
    for row in summary["rows"]:
        print(
            f"  {row['bar']}: [{row['arm']}] band {row['sealed_band']}  "
            f"measured {row['measured']:.6f}  {'PASS' if row['pass'] else 'FAIL'}"
        )
    print("both arms, all three engines:")
    for name in ENGINE_NAMES:
        for arm in ("premise_accepted", "unconditional"):
            cells_txt = "  ".join(
                f"{r['bar']} {r['measured']:.4f}{'P' if r['pass'] else 'F'}"
                for r in engines[name][arm]["readings"]
            )
            print(f"  {name:9s} {arm:17s} {cells_txt}")
    print("growth-axis spell lengths (mean months / mean log age):")
    for side, block in (
        (
            "history",
            engines[PRIMARY_ENGINE]["unconditional"]["growth_spell_lengths"]["historical_panel"],
        ),
        (
            "generated",
            engines[PRIMARY_ENGINE]["unconditional"]["growth_spell_lengths"]["generated_batch"],
        ),
    ):
        for axis in ("expanding", "contracting"):
            row = block[axis]
            print(
                f"  {side:9s} {axis:12s} n {row['n_spells']:4d}  mean "
                f"{row['mean_spell_months']:6.2f}  median {row['median_spell_months']:5.1f}  "
                f"mean log age {row['mean_log_age']:.4f}"
            )
    vd = engines[PRIMARY_ENGINE]["unconditional"]["curve_variance_decomposition"]
    print(
        "curve variance: season term sd "
        f"{vd['season_term_sd_on_generated_pp']:.4f} pp (history {vd['season_term_sd_on_history_pp']:.4f})"
        f"  u_hat contribution sd {vd['u_hat_contribution_sd_pp']:.4f}"
        f"  residual stationary sd {vd['residual_stationary_sd_pp']:.4f}"
        f"  ratio {vd['season_term_sd_over_residual_sd']:.4f}"
    )
    print("O1 by move type (clockwise fraction, share of transitions):")
    o1d = engines[PRIMARY_ENGINE]["unconditional"]["o1_decomposition"]
    for side in ("historical_panel", "generated_batch"):
        block = o1d[side]
        parts = "  ".join(
            f"{kind} {row['clockwise_fraction']:.4f} ({row['share_of_all_transitions']:.3f})"
            for kind, row in block["by_move"].items()
        )
        print(f"  {side:17s} overall {block['clockwise_fraction']:.4f}  {parts}")
    print("feedback frontier (multiplier | T1 | O1 | D1 D2 D3 D4 | tight-and-expanding):")
    for row in frontier_rows:
        print(
            f"  {row['arm']:17s} x{row['feedback_multiplier']:<4} "
            f"T1 {row['T1_lift']:.4f} {'P' if row['T1_pass'] else 'F'}  "
            f"O1 {row['O1_clockwise']:.4f} {'P' if row['O1_pass'] else 'F'}  "
            f"D {row['D1_recession_median']:.0f} {row['D2_stagflation_median']:.0f} "
            f"{row['D3_recovery_median']:.0f} {row['D4_expansion_median']:.0f} "
            f"{'all-D-pass' if row['D_all_pass'] else 'D-FAIL'}  "
            f"tight-exp {row['share_of_tight_months_that_are_expanding']:.4f}"
            f"{'  ALL SIX PASS' if row['all_six_pass'] else ''}"
        )
    print("label stability (joint fit):")
    for key, row in stability["per_statistic"].items():
        print(
            f"  {key:24s} baseline {row['baseline_value']:+.4f} se "
            f"{row['baseline_standard_error']:.4f}  worst {row['worst_threshold_arm']} "
            f"{row['worst_threshold_arm_moves_by_se']:+.3f} SE  -> {row['verdict']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
