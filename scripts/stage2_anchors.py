"""Stage-2 pre-seal measurements: M4 (curve endogeneity) and P1's phase re-derivation.

**What this script is for.** Decision ``D-SP-9`` funded a stage-2 campaign whose
two new bars -- ``P1`` (the phase-coupling bar) and ``P2`` (the curve-endogeneity
bar) -- cannot be sealed as written, because neither exists as a number.
``docs/superpowers/specs/2026-08-17-stage2-coupled-system-design.md`` §3.3 lists
what must be measured first. This module measures two of those items, and each
one is capable of killing the bar it anchors:

* **M4** -- history's own curve decomposition, computed the way the engine's is,
  but with the **rule-implied policy rate** in place of the observed policy
  deviation. The design document names this substitution as the decisive one:
  on history the observed deviation carries real economic content (the
  zero-bound decade, credit conditions, everything the Taylor rule missed),
  while in simulation it is a stand-alone mean-reverting process with no inputs.
  Anchoring ``P2`` on a regressor the simulator does not possess would be the
  same class of definition mismatch the exam's §6.2 review exists to catch.
  The **pre-declared acceptance rule**, quoted from §3.3: *"if it comes back with
  an interval so wide that the engines on record sit inside it, P2 should be
  dropped rather than narrowed -- the precedent is A2's low-inflation ceiling,
  dropped pre-seal rather than moved once its cost was visible."* This module
  applies that rule mechanically and records the verdict either way.

* **The windowing-symmetric phase anchor** -- ``P1``'s re-derivation, demanded by
  the verdict-integrity review's finding C1
  (``docs/superpowers/specs/2026-08-17-spine-v2-results.md`` §8.1). The sealed
  ``O1`` judge censors the first twelve months of every generated decade (their
  trailing-inflation warm-up, 12 of every 120) while the historical side loses
  one warm-up in 813 months. Every phase anchor on the record -- 0.6176 on
  growth flips, 0.6111 on inflation crossings -- was measured on the uncensored
  panel. §8.1 rules that *"any stage-2 seal must re-derive the phase anchor
  under windowing-symmetric constructs -- both sides losing the same fraction of
  their months -- before P1's threshold is cut"*. Both symmetric treatments are
  computed here: history put through the generated side's own windowing machine,
  and both sides uncensored.

**What this script is NOT.** It fits nothing new about the engine, simulates no
decades, and touches no sealed file. Every sealed v2 artifact it reads --
``spine-v2-prereg.json``, ``spine-v2-anchors.json``,
``spine-v2-feedback-params.json`` -- is opened read-only and its recorded values
are used as inputs, never recomputed and never overwritten. The two new bars are
**not** sealed by running this; sealing is a separate step after the owner has
read the ``P2`` verdict.

**Determinism.** ``scripts/spine_v2_anchors.py``'s rules, unchanged: one literal
seed per new random section, no global RNG, no time-based default, every float
rounded before it is written so re-runs are byte-identical. Two of this module's
three estimators need no seed at all -- the phase-scramble null enumerates
*every* admissible shift rather than sampling a few, which is both exact and
seedless -- so the only tapes in play are the two block-bootstrap seeds below.

**No network.** Everything is read from the pinned campaign vintage through the
same accessors ``scripts/spine_v2_fit.py`` uses.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_anchors import (  # noqa: E402
    STABILITY_ARMS,
    STABILITY_PERTURBATION_PP,
    _stationary_bootstrap_indices,
)
from spine_v2_feedback import (  # noqa: E402
    ENGINE_NAMES,
    PRIMARY_ENGINE,
    _profile_at_rho,
    curve_design,
    curve_model_from_fit,
    first_spell_end,
    fit_joint,
    growth_axis,
    simulate_batch_feedback,
    spell_age,
    week2_curve_model,
)
from spine_v2_fit import (  # noqa: E402
    DEFAULT_N_DECADES,
    VERIFY_SEED,
    Panel,
    _load_premise,
    _relabel_growth,
    _round,
    build_engine,
    build_panel,
    measure_stag_spell_rate,
    relabel,
    select_curve_lag,
)
from spine_v2_grader import CONTRACTING_LABELS, season_cells  # noqa: E402
from spine_v2_report import load_sealed  # noqa: E402

from ah.gen.bootstrap import (  # noqa: E402
    CAMPAIGN_VINTAGE_ID,
    USREC_SERIES_ID,
    _catalog_access,
    _monthly,
    _read_series,
    campaign_source,
)
from ah.gen.climate.model import PARAM_NAMES  # noqa: E402
from ah.gen.spine import CLOCKWISE, QUADRANTS, fit_hazard, panel_yoy  # noqa: E402
from ah.gen.systems import _pinned_layers  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
OUT_PATH = SPECS_DIR / "stage2-anchors.json"

#: Read-only inputs. The first two are inside the v2 seal's hash list; this
#: module opens them and never writes them, which is why running it cannot
#: invalidate the seal.
V2_PREREG_PATH = SPECS_DIR / "spine-v2-prereg.json"
V2_ANCHORS_PATH = SPECS_DIR / "spine-v2-anchors.json"
#: Week 3's committed fit. Not sealed, but it is the record of both engines'
#: curve decompositions and the source of every "engine on the record" number
#: below -- read, never restated by hand.
FEEDBACK_PARAMS_PATH = SPECS_DIR / "spine-v2-feedback-params.json"

# --------------------------------------------------------------------------- #
# constants -- every one of them a declared choice, with its reason
# --------------------------------------------------------------------------- #

#: The campaign's standard interval machinery, carried verbatim from
#: ``scripts/spine_v2_anchors.py`` so that a stage-2 interval and a v2 interval
#: are the same object measured on different statistics.
N_BOOTSTRAP = 2000
BLOCK_LENGTHS_MONTHS = (12, 24, 36)
PRIMARY_BLOCK_MONTHS = 24
CI_PERCENTILES = (2.5, 97.5)

#: One literal seed per random section. 20260816-20260820 are spoken for by
#: ``spine_v2_anchors``; these two continue the run and are used nowhere else.
M4_BOOTSTRAP_SEED = 20260821
PHASE_BOOTSTRAP_SEED = 20260822

#: The generated side's windowing, from the sealed judge: a decade is 120 months
#: and its first 12 carry no trailing inflation. Both numbers are re-read from
#: the sealed artifact in :func:`_check_sealed_inputs` rather than trusted here.
DECADE_MONTHS = 120
YOY_WARMUP_MONTHS = 12

#: The AR(1) coefficient's search bracket and scan resolution, identical to
#: ``scripts/spine_v2_feedback.py``'s, so the M4 curve equation is maximised by
#: the same procedure week 3's was.
RHO_BRACKET = (-0.99, 0.999)
RHO_SCAN_POINTS = 199
RHO_TOL = 1e-12

#: The phase-scramble null's guard band, in months. A circular shift of the
#: inflation dial destroys its alignment with the growth dial while preserving
#: each dial's own dynamics -- but a shift of one or two months destroys almost
#: nothing, so including tiny shifts drags the "independent dials" null back
#: toward the measured value and flatters the departure. 60 months is five
#: years: an order of magnitude beyond the several-quarter lag the growth ->
#: inflation channel is supposed to operate at, and beyond the panel's longest
#: median season dwell. 0 (no guard) and 120 (ten years) are both reported as
#: sensitivity, and on this panel the three agree to about 0.001.
SCRAMBLE_GUARD_MONTHS = 60
SCRAMBLE_GUARD_SENSITIVITY_MONTHS = (0, 120)

#: Move types, in the order they are reported. ``diagonal`` moves change both
#: dials at once; no diagonal pair is in ``CLOCKWISE``, so they are counter-
#: clockwise by construction and are reported separately rather than folded in.
MOVE_TYPES = ("growth_flip", "inflation_crossing", "diagonal")
#: The two move types P1 is written on.
P1_MOVE_TYPES = ("growth_flip", "inflation_crossing")

#: P1's tolerance, from the design document §3.1(c): half of history's own
#: measured departure from the batch's phase-scrambled null. The fraction is a
#: declared constant here so that changing it is a visible edit.
P1_TOLERANCE_FRACTION_OF_HISTORY = 0.5

#: The engines already on the record, whose strict-accounting economic shares
#: the P2 acceptance rule is applied against. The VALUES are computed from
#: ``spine-v2-feedback-params.json``; only the names live here.
RECORDED_ENGINES = ("week2", "feedback")

# --- M3: the growth -> inflation coupling, and the power calculation -------- #

#: The lag grid for ``m`` in the design document's inflation equation, in
#: months. Nothing is searched outside it and the whole profile is published,
#: which is the discipline §2.3 names ("chosen by likelihood over a stated grid
#: at constant parameter count"). Two years of monthly lags brackets the
#: "several quarters" the mechanism is claimed to operate at with room on both
#: sides, and every lag costs the same one parameter, so the profile is
#: comparable across it.
M3_LAG_GRID_MONTHS = tuple(range(0, 25))
#: One literal seed per random section, continuing the run.
M3_BOOTSTRAP_SEED = 20260823
M3_POWER_SEED = 20260824
#: Replicates for the power calculation. 2000 puts the Monte Carlo error on a
#: pass rate near 1.0 below 0.005, which is far finer than any decision the
#: number is used for.
M3_POWER_REPLICATES = 2000

#: The phase scramble's guard band when the batch is a set of DECADES rather
#: than one long panel, in months. 60 months cannot be used inside a 120-month
#: decade: ``min(k, 120-k) >= 60`` admits exactly one shift. 24 months is the
#: largest guard that still leaves a usable enumeration (73 of the 119 shifts)
#: and it is more than twice the ten-month lag M3 measures for the growth ->
#: inflation channel, so no plausible alignment survives it.
DECADE_SCRAMBLE_GUARD_MONTHS = 24
DECADE_SCRAMBLE_GUARD_SENSITIVITY_MONTHS = (12, 36)

# --- the floor-noise study -------------------------------------------------- #

#: Independent bootstrap tapes for the noise study, and the stride between
#: their seeds. The stride is NOT the platform's 7919: that stride is already
#: spoken for on the ensemble axis, and re-using a stride on a new axis is how
#: 20 spines once collapsed to 2. 10007 is prime, coprime to everything in
#: play, and the tapes are checked for distinctness rather than assumed.
NOISE_TAPE_SEED_BASE = 20260825
NOISE_TAPE_STRIDE = 10007
#: Twelve tapes puts the 95% interval on a standard deviation at roughly
#: [0.66x, 1.52x] of the estimate -- coarse, and reported as such beside every
#: one of them, because a check whose own resolution is hidden is not a check.
NOISE_TAPE_COUNT = 12
#: The ladder of draw counts the noise is MEASURED at, quadrupling each rung.
#: The answer is the smallest rung that meets the rule -- measured, not
#: extrapolated -- because one of the two floors is a ratio of small counts and
#: therefore lattice-valued, and a lattice-valued statistic's noise does not
#: fall as a smooth power of the draw count.
NOISE_DRAW_LADDER = (2000, 8000, 32000, 128000, 512000)
#: The rungs both constructs are measured on. Above this the ladder is climbed
#: only on the binding one, because a 512,000-draw tape costs about half a
#: minute and there are twelve of them.
NOISE_BOTH_CONSTRUCT_RUNGS = (2000, 8000, 32000)
#: If the ladder's top rung still misses, refinement rungs are taken at the
#: count the fitted law implies -- but never less than this multiple of the last
#: rung, because a standard deviation from twelve tapes is only known to about
#: plus-or-minus a half and a refinement that barely moved would be measuring
#: its own error. Rounded up to a multiple of the rounding constant so the
#: answer is a number a seal can quote, and capped so the run cannot wander.
NOISE_REFINEMENT_MIN_GROWTH = 1.25
NOISE_REFINEMENT_ROUNDING = 20000
NOISE_MAX_REFINEMENTS = 2
#: The pre-declared sizing rule: tape noise must be at most this fraction of
#: the smallest margin the floor has to resolve. One fifth is the campaign's
#: usual "an order of magnitude is overkill, a factor of two is not enough"
#: setting -- at one fifth, a two-standard-deviation tape excursion is still
#: under half the margin, so no recorded verdict can flip on the draw.
NOISE_MARGIN_FRACTION = 0.2
#: Draws per chunk when a tape is longer than memory likes. A quarter-million
#: draws over 813 months would be a 1.6 GB index in one array; at 2000 draws a
#: chunk is 13 MB. **Chunking changes the tape** -- the generator is consumed
#: in a different order than one big call would consume it -- so the chunk size
#: is a declared constant and every tape in the study uses the same one, which
#: is what makes the tapes comparable with each other and the study
#: reproducible.
NOISE_CHUNK_DRAWS = 2000


# --------------------------------------------------------------------------- #
# small shared helpers
# --------------------------------------------------------------------------- #


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _f(x: Any) -> float | None:
    """A float that survives JSON: NaN and infinities become null."""
    v = float(x)
    return v if np.isfinite(v) else None


def _quantiles(values: np.ndarray) -> dict[str, float | None]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {"lo": None, "hi": None, "median": None, "sd": None}
    lo, hi = np.percentile(finite, CI_PERCENTILES)
    # the sd is carried because M5 needs a yardstick: the campaign's stability
    # rule asks whether a dial moves a statistic by more than its OWN sampling
    # error, and for a bootstrapped statistic that error is this sd.
    return {
        "lo": _f(lo),
        "hi": _f(hi),
        "median": _f(np.median(finite)),
        "sd": _f(finite.std(ddof=1)) if finite.size > 1 else None,
    }


def _chi2_sf_df1(x: float) -> float:
    """Upper tail of a chi-square with one degree of freedom.

    ``P(X > x) = erfc(sqrt(x/2))`` exactly. Written out rather than imported so
    the M3 gate has no scipy dependency, and checked against the two textbook
    points in :func:`_assert_chi2_df1`.
    """
    return math.erfc(math.sqrt(max(float(x), 0.0) / 2.0))


def _assert_chi2_df1() -> dict[str, Any]:
    """The one-line tail function must hit the two values everyone knows.

    A property check, not a restatement: 3.841459 is the 95th percentile of a
    chi-square on one degree of freedom and 6.634897 is its 99th. If the
    formula were wrong, M3's nominal p-values would be wrong in the direction
    nobody checks.
    """
    p95 = _chi2_sf_df1(3.8414588206941236)
    p99 = _chi2_sf_df1(6.634896601021214)
    if abs(p95 - 0.05) > 1e-9 or abs(p99 - 0.01) > 1e-9:
        raise Stage2Error(f"the chi-square(1) tail is wrong: {p95!r}, {p99!r}")
    return {
        "p_at_3_841459": _f(p95),
        "p_at_6_634897": _f(p99),
        "matches_the_textbook_percentiles": True,
    }


# --------------------------------------------------------------------------- #
# the historical panel's economic states, reconstructed and CHECKED
# --------------------------------------------------------------------------- #


class Stage2Error(RuntimeError):
    """A stage-2 measurement could not be made on the inputs it was given."""


def rule_implied_states(panel: Panel) -> dict[str, np.ndarray]:
    """The Taylor rule's implied policy rate and inflation gap, on history.

    ``scripts/spine_v2_fit.build_panel`` computes the same anchor internally and
    keeps only its RESIDUAL (``u_hat``, the policy deviation), which is exactly
    the regressor M4 exists to replace. The anchor itself is not exposed on
    :class:`Panel`, so it is rebuilt here from the same three sources -- the
    pinned L1 climate artifact's posterior-mean states, its posterior-mean
    parameters, and the campaign vintage's ``fred.USREC`` cycle input -- and
    then **proved identical** to the one ``build_panel`` used, by reconstructing
    ``u_hat`` from it and requiring a bit-for-bit match. That check is the point
    of this function: without it, "the rule-implied rate" would be a second
    definition of an object the campaign already has one of.

    Returns the rule-implied policy rate ``i_rule``, the inflation gap ``x_gap``
    (actual trailing inflation minus its slow trend), and the pieces they are
    made of, all on the panel's monthly grid.
    """
    source = campaign_source()
    dates = pd.DatetimeIndex(source.dates)
    yoy = panel_yoy(source)
    climate, _regimes = _pinned_layers()
    locs = climate.dates.get_indexer(dates)
    if (locs < 0).any():
        raise Stage2Error("the panel leaves the climate artifact's monthly grid")
    smoothed = climate.states.mean(axis=0)
    pi_star = smoothed[locs, 0]
    r_star = smoothed[locs, 1]
    theta_bar = {name: float(np.mean(climate.params[name])) for name in PARAM_NAMES}

    _catalog, access = _catalog_access(_REPO_ROOT / "data", CAMPAIGN_VINTAGE_ID)
    usrec_frame = _read_series(access, USREC_SERIES_ID)
    if usrec_frame is None:
        raise Stage2Error("the rule-implied rate needs fred.USREC from the campaign vintage")
    usrec = _monthly(usrec_frame).reindex(dates).to_numpy(dtype=np.float64)
    cycle = 1.0 - 2.0 * usrec

    # The warm-up months have no trailing inflation, so the rule reads the trend
    # there. This is build_panel's own convention, not a new one.
    pi_obs = np.where(np.isnan(yoy), pi_star, yoy)
    x_gap = pi_obs - pi_star
    i_rule = r_star + pi_star + theta_bar["phi_pi"] * x_gap + theta_bar["phi_c"] * cycle

    values = np.asarray(source.values, dtype=np.float64)
    names = list(source.factor_names)
    policy = values[:, names.index("policy_rate")]
    u_hist = policy - i_rule
    u_hat_rebuilt = (u_hist - float(np.mean(u_hist))) / float(np.std(u_hist))
    drift = float(np.max(np.abs(u_hat_rebuilt - panel.u_hat)))
    if drift != 0.0:
        raise Stage2Error(
            "the rebuilt rule anchor is not build_panel's: u_hat differs by "
            f"{drift:.3e}, so M4's regressor is not the residual's complement"
        )
    return {
        "i_rule": i_rule,
        "x_gap": x_gap,
        "pi_star": pi_star,
        "r_star": r_star,
        "cycle": cycle,
        "policy_observed": policy,
        "u_hat_rebuild_max_abs_diff": np.array([drift]),
        "phi_pi": np.array([theta_bar["phi_pi"]]),
        "phi_c": np.array([theta_bar["phi_c"]]),
    }


# --------------------------------------------------------------------------- #
# M4 -- the curve decomposition, block-aware exact AR(1) maximum likelihood
# --------------------------------------------------------------------------- #


def _profile_blocks(
    y: np.ndarray, x: np.ndarray, rho: float, is_start: np.ndarray
) -> tuple[np.ndarray, float, float]:
    """``(beta, sigma, loglik)`` at fixed ``rho``, with independent AR(1) blocks.

    ``is_start[i]`` marks a row that opens a new contiguous stretch of real
    months. Inside a stretch the Prais-Winsten transform is the usual
    ``r_t - rho r_{t-1}``; the row that opens one enters through its own
    stationary law, ``sqrt(1-rho^2) r_t``, and contributes its own
    ``0.5 log(1-rho^2)`` to the log-determinant.

    Why this exists rather than reusing ``spine_v2_feedback._profile_at_rho``
    unchanged: a block-bootstrap draw is a *spliced* series. Pretending its
    joins are genuine month-to-month steps would let a resample invent
    autocorrelation across a join, which is exactly the corruption
    ``spine_v2_anchors.section_e`` refuses for transitions. With a single block
    covering the whole sample this reduces to ``_profile_at_rho`` exactly, and
    :func:`_assert_single_block_identity` proves it rather than asserting it.
    """
    n = int(y.size)
    scale = math.sqrt(1.0 - rho * rho)
    yt = np.empty(n, dtype=np.float64)
    xt = np.empty_like(x)
    yt[1:] = y[1:] - rho * y[:-1]
    xt[1:] = x[1:] - rho * x[:-1]
    yt[0] = y[0]
    xt[0] = x[0]
    yt[is_start] = scale * y[is_start]
    xt[is_start] = scale * x[is_start]
    beta, *_ = np.linalg.lstsq(xt, yt, rcond=None)
    wss = float(np.sum((yt - xt @ beta) ** 2))
    sigma = math.sqrt(wss / n)
    n_blocks = int(np.count_nonzero(is_start))
    loglik = -0.5 * n * (
        math.log(2.0 * math.pi) + math.log(wss / n) + 1.0
    ) + 0.5 * n_blocks * math.log(1.0 - rho * rho)
    return beta, sigma, loglik


def _maximise_rho_blocks(y: np.ndarray, x: np.ndarray, is_start: np.ndarray) -> float:
    """Profile maximiser of ``rho``: coarse scan then golden section.

    Byte-for-byte the search ``spine_v2_feedback._maximise_over_rho`` performs,
    with the block-aware profile substituted. Deterministic end to end -- no
    random start, no tie-break.
    """
    lo, hi = RHO_BRACKET
    grid = np.linspace(lo, hi, RHO_SCAN_POINTS)
    values = np.array([_profile_blocks(y, x, float(r), is_start)[2] for r in grid])
    k = int(np.argmax(values))
    a = float(grid[max(k - 1, 0)])
    b = float(grid[min(k + 1, grid.size - 1)])
    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc = _profile_blocks(y, x, c, is_start)[2]
    fd = _profile_blocks(y, x, d, is_start)[2]
    while abs(b - a) > RHO_TOL:
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - inv_phi * (b - a)
            fc = _profile_blocks(y, x, c, is_start)[2]
        else:
            a, c, fc = c, d, fd
            d = a + inv_phi * (b - a)
            fd = _profile_blocks(y, x, d, is_start)[2]
    return 0.5 * (a + b)


def _assert_single_block_identity(y: np.ndarray, x: np.ndarray) -> dict[str, Any]:
    """The block-aware profile must reduce to week 3's when there is one block.

    A property check, not a restatement: it compares two independently written
    code paths at a rho the maximiser did not choose, so a sign slip or a
    misplaced log-determinant term in either one shows up as a difference.
    """
    single = np.zeros(y.size, dtype=bool)
    single[0] = True
    weights = np.ones(y.size, dtype=np.float64)
    worst_beta = 0.0
    worst_ll = 0.0
    worst_sigma = 0.0
    for rho in (-0.5, 0.0, 0.5, 0.9, 0.99):
        b1, s1, l1 = _profile_blocks(y, x, rho, single)
        b2, s2, l2 = _profile_at_rho(y, x, rho, weights)
        worst_beta = max(worst_beta, float(np.max(np.abs(b1 - b2))))
        worst_sigma = max(worst_sigma, abs(s1 - s2))
        worst_ll = max(worst_ll, abs(l1 - l2))
    ok = worst_beta < 1e-10 and worst_sigma < 1e-12 and worst_ll < 1e-9
    if not ok:
        raise Stage2Error(
            "the block-aware AR(1) profile does not reduce to spine_v2_feedback's "
            f"single-block profile (beta {worst_beta:.3e}, sigma {worst_sigma:.3e}, "
            f"loglik {worst_ll:.3e})"
        )
    return {
        "rho_grid": [-0.5, 0.0, 0.5, 0.9, 0.99],
        "max_abs_beta_difference": _f(worst_beta),
        "max_abs_sigma_difference": _f(worst_sigma),
        "max_abs_loglik_difference": _f(worst_ll),
        "reduces_to_week3_profile": bool(ok),
    }


def strict_economic_share(
    components: dict[str, tuple[float, bool]], residual_stationary_sd: float
) -> dict[str, Any]:
    """The decomposition BOTH sides are scored by -- one function, one definition.

    ``components`` maps a name to ``(standard deviation in pp, is_economic)``.
    The share is

        sum of squares of the ECONOMIC component sds
        ---------------------------------------------------------------
        sum of squares of ALL component sds, plus the AR(1) residual's
        stationary variance

    which is exactly the accounting the week-3 report published and the design
    document quotes as ``0.0%`` for week 2 and ``2.2%`` for week 3: a component
    that is a stand-alone mean-reverting process with no economic inputs (the
    policy deviation ``u``) sits in the denominator and not in the numerator.
    The naive share -- everything that is not residual noise -- is reported
    beside it, because that is the number (40.4% / 6.1%) an unqualified reading
    of the same fit would produce, and the gap between the two IS §1.2's finding.

    **The one honest caveat, stated here because it is where the number is
    made.** Summing squares treats the components as uncorrelated. On the
    GENERATED side they are, by construction -- ``u``, the season term and the
    residual are separate draws. On HISTORY they are not: the rule-implied rate
    and the inflation gap share the inflation trend by definition. So on history
    the denominator is not the slope's own variance, and the caller reports the
    two side by side rather than silently normalising one into the other.
    """
    economic_ss = sum(sd * sd for sd, econ in components.values() if econ)
    exogenous_ss = sum(sd * sd for sd, econ in components.values() if not econ)
    residual_ss = float(residual_stationary_sd) ** 2
    total = economic_ss + exogenous_ss + residual_ss
    return {
        "component_sd_pp": {name: _f(sd) for name, (sd, _e) in components.items()},
        "component_is_economic": {name: bool(e) for name, (_sd, e) in components.items()},
        "residual_stationary_sd_pp": _f(residual_stationary_sd),
        "economic_sum_of_squares": _f(economic_ss),
        "exogenous_sum_of_squares": _f(exogenous_ss),
        "residual_sum_of_squares": _f(residual_ss),
        "total_sum_of_squares": _f(total),
        "economic_share": _f(economic_ss / total) if total > 0.0 else None,
        "naive_explained_share": _f((economic_ss + exogenous_ss) / total) if total > 0.0 else None,
        "residual_share": _f(residual_ss / total) if total > 0.0 else None,
    }


def _m4_design(
    panel: Panel, states: dict[str, np.ndarray], labels: np.ndarray | None = None
) -> dict[str, Any]:
    """The M4 curve equation's response, design matrix and column meanings.

    The equation is the design document's §2.2 curve line, read on history::

        slope_t = c0 + c_i (i_rule_t - ibar) + c_x (x_t - xbar)
                     + season_term(g_t, age_t) + e_t,   e_t AR(1)

    Two conventions are inherited rather than chosen. The season block is week
    3's, unchanged -- a contracting indicator and log-age on each growth axis,
    from ``spine_v2_feedback.curve_design``. And the fit opens after the panel's
    first, left-truncated growth spell, which is where week 3's curve block
    opens, so a month's ``age`` means the same thing in both fits and the two
    R-squareds are comparable.
    """
    expanding = growth_axis(panel.labels if labels is None else np.asarray(labels))
    age = spell_age(expanding)
    start = int(first_spell_end(expanding) + 1)
    week3 = curve_design(panel.u_hat, expanding, age)  # [1, u_hat, C, E, K]
    raw = np.column_stack(
        [
            np.ones(panel.slope.size, dtype=np.float64),
            states["i_rule"],
            states["x_gap"],
            week3[:, 2],
            week3[:, 3],
            week3[:, 4],
        ]
    )[start:]
    y = np.asarray(panel.slope[start:], dtype=np.float64)
    centers = raw[:, 1:].mean(axis=0)
    x = raw.copy()
    x[:, 1:] -= centers
    return {
        "y": y,
        "x": x,
        "centers": centers,
        "start_row": start,
        "labels": ("intercept", "c_i_policy_rule", "c_x_inflation_gap", "C", "E", "K"),
    }


def _m4_statistics(
    y: np.ndarray, x: np.ndarray, is_start: np.ndarray, rho: float | None = None
) -> dict[str, Any]:
    """One M4 fit and the numbers cut from it, on whatever sample is passed in.

    ``rho=None`` maximises it; passing a value pins it, which is how the
    ``rho_pinned`` bootstrap arm isolates the coefficients' sampling error from
    the AR(1) coefficient's.
    """
    fitted_rho = _maximise_rho_blocks(y, x, is_start) if rho is None else float(rho)
    beta, sigma, loglik = _profile_blocks(y, x, fitted_rho, is_start)
    policy_term = beta[1] * x[:, 1]
    inflation_term = beta[2] * x[:, 2]
    season_term = beta[3] * x[:, 3] + beta[4] * x[:, 4] + beta[5] * x[:, 5]
    residual = y - x @ beta
    residual_stationary_sd = float(sigma / math.sqrt(max(1.0 - fitted_rho * fitted_rho, 1e-12)))
    components = {
        "policy_rule": (float(np.std(policy_term)), True),
        "inflation_gap": (float(np.std(inflation_term)), True),
        "season_term": (float(np.std(season_term)), True),
    }
    strict = strict_economic_share(components, residual_stationary_sd)
    economic_fitted = policy_term + inflation_term + season_term
    slope_variance = float(np.var(y))
    return {
        "rho": float(fitted_rho),
        "innovation_sd_pp": float(sigma),
        "loglik": float(loglik),
        "beta": [float(v) for v in beta],
        "residual_realised_sd_pp": float(np.std(residual)),
        "residual_stationary_sd_pp": residual_stationary_sd,
        "slope_sd_pp": float(np.sqrt(slope_variance)),
        "r_squared_realised": float(1.0 - np.var(residual) / slope_variance),
        "strict": strict,
        "economic_share": float(strict["economic_share"] or 0.0),
        "covariance_aware_share": float(np.var(economic_fitted) / slope_variance),
        "strict_share_on_realised_residual": float(
            strict_economic_share(components, float(np.std(residual)))["economic_share"] or 0.0
        ),
        # The size of the covariance caveat, as a number rather than a warning:
        # if the components were uncorrelated this ratio would be 1.
        "sum_of_squares_over_slope_variance": float(
            (strict["total_sum_of_squares"] or 0.0) / slope_variance
        ),
        "correlation_policy_rule_inflation_gap": float(
            np.corrcoef(x[:, 1], x[:, 2])[0, 1] if x[:, 2].std() > 0.0 else np.nan
        ),
    }


def recorded_engine_shares(feedback_params: dict[str, Any]) -> dict[str, Any]:
    """The engines on the record, scored by :func:`strict_economic_share`.

    The design document's ``0.0%`` and ``2.2%`` are reproduced here from week 3's
    committed artifact through the SAME function that scores history -- which is
    P2's fourth anti-test obligation ("the decomposition function must be a
    single piece of code called on both sides, with the sides differing only in
    their input array") discharged in advance, on the only two generated batches
    that exist. Their component sds are read from the artifact; nothing is
    re-simulated and nothing is restated by hand.
    """
    out: dict[str, Any] = {}
    engines = feedback_params["verification"]["engines"]
    for name in RECORDED_ENGINES:
        for arm, row in sorted(engines[name].items()):
            # Each engine also carries an ``amended_verdict`` block, which is a
            # verdict record and not a batch; only the two BATCH arms carry a
            # decomposition, and only those two are scored.
            if not isinstance(row, dict) or "curve_variance_decomposition" not in row:
                continue
            decomposition = row["curve_variance_decomposition"]
            components = {
                # u_hat is L1's policy DEVIATION: in the simulator it is a
                # stand-alone mean-reverting process with no inputs at all, so
                # it is exogenous noise wearing an economic name. That
                # classification is the whole content of the strict accounting.
                "u_hat": (float(decomposition["u_hat_contribution_sd_pp"]), False),
                "season_term": (float(decomposition["season_term_sd_on_generated_pp"]), True),
            }
            share = strict_economic_share(
                components, float(decomposition["residual_stationary_sd_pp"])
            )
            out[f"{name}__{arm}"] = share
    return out


def section_m4(
    panel: Panel, states: dict[str, np.ndarray], recorded: dict[str, Any]
) -> dict[str, Any]:
    """M4: history's curve decomposition on the rule-implied policy rate.

    The point estimate, the block-bootstrap interval at three block lengths and
    two AR(1) treatments, and then the design document's own acceptance rule
    applied mechanically to the result.
    """
    design = _m4_design(panel, states)
    y: np.ndarray = design["y"]
    x: np.ndarray = design["x"]
    n = int(y.size)

    identity = _assert_single_block_identity(y, x)
    single = np.zeros(n, dtype=bool)
    single[0] = True
    point = _m4_statistics(y, x, single)

    # The comparison that says WHY the substitution matters: the same equation
    # with the observed policy deviation in place of the rule-implied rate, i.e.
    # week 3's regressor set plus the inflation gap.
    x_observed = x.copy()
    x_observed[:, 1] = panel.u_hat[design["start_row"] :] - float(
        np.mean(panel.u_hat[design["start_row"] :])
    )
    observed = _m4_statistics(y, x_observed, single)

    rng = np.random.Generator(np.random.PCG64(M4_BOOTSTRAP_SEED))
    bootstrap: dict[str, Any] = {}
    for block in sorted(BLOCK_LENGTHS_MONTHS):
        index = _stationary_bootstrap_indices(rng, n, block, N_BOOTSTRAP)
        refit_shares = np.empty(N_BOOTSTRAP, dtype=np.float64)
        pinned_shares = np.empty(N_BOOTSTRAP, dtype=np.float64)
        rhos = np.empty(N_BOOTSTRAP, dtype=np.float64)
        r_squared = np.empty(N_BOOTSTRAP, dtype=np.float64)
        covariance_aware = np.empty(N_BOOTSTRAP, dtype=np.float64)
        for draw in range(N_BOOTSTRAP):
            row = index[draw]
            is_start = np.empty(n, dtype=bool)
            is_start[0] = True
            is_start[1:] = row[1:] != (row[:-1] + 1)
            yb, xb = y[row], x[row]
            refit = _m4_statistics(yb, xb, is_start)
            refit_shares[draw] = refit["economic_share"]
            rhos[draw] = refit["rho"]
            r_squared[draw] = refit["r_squared_realised"]
            covariance_aware[draw] = refit["covariance_aware_share"]
            pinned_shares[draw] = _m4_statistics(yb, xb, is_start, rho=point["rho"])[
                "economic_share"
            ]
        bootstrap[f"block_{block}m"] = {
            "rho_refitted": {
                "economic_share_ci95": _quantiles(refit_shares),
                "rho_median": _f(float(np.median(rhos))),
                "rho_ci95": _quantiles(rhos),
            },
            "rho_pinned_at_point_estimate": {
                "economic_share_ci95": _quantiles(pinned_shares),
            },
            # Two other ways of summarising the same fit, carried so the P2
            # verdict can be checked against a different summary rather than
            # resting on the strict share alone.
            "r_squared_realised_ci95": _quantiles(r_squared),
            "covariance_aware_share_ci95": _quantiles(covariance_aware),
        }

    primary = bootstrap[f"block_{PRIMARY_BLOCK_MONTHS}m"]
    verdict = _p2_acceptance(primary, bootstrap, recorded)
    return {
        "question": (
            "how much of the yield curve's movement is made of the economy the engine "
            "simulates, measured on history the way the engine will be measured"
        ),
        "equation": (
            "slope_t = c0 + c_i (i_rule_t - ibar) + c_x (x_t - xbar) "
            "+ season_term(g_t, age_t) + e_t, with e_t AR(1); exact Gaussian maximum "
            "likelihood, the first observation of every contiguous block entering "
            "through its own stationary law"
        ),
        "regressor_substitution": (
            "i_rule is the Taylor rule's IMPLIED policy rate -- r* + pi* + phi_pi (pi - "
            "pi*) + phi_c c -- not the observed rate and not its residual. Week 2 and "
            "week 3 both regressed the curve on u_hat, the observed rate MINUS that "
            "anchor. On history u_hat carries real economic content the rule missed; in "
            "simulation it is a stand-alone mean-reverting process with no inputs, so a "
            "bar anchored on it would compare two different objects"
        ),
        "sample": {
            "months": n,
            "opens_at_panel_row": design["start_row"],
            "why": (
                "week 3's curve block drops the panel's first, left-truncated growth "
                "spell so that a month's spell age means the same thing in the hazard "
                "and the curve blocks; the same rule is applied here so the two fits' "
                "samples are identical"
            ),
        },
        "coefficient_labels": list(design["labels"]),
        "coefficient_centers": [_f(v) for v in design["centers"]],
        "single_block_identity_check": identity,
        "point_estimate": point,
        "same_equation_on_the_observed_deviation": {
            "note": (
                "the identical design with u_hat in column 1 instead of the rule-implied "
                "rate. Reported so the substitution's cost is visible rather than argued"
            ),
            **observed,
        },
        "phi_pi": _f(float(states["phi_pi"][0])),
        "phi_c": _f(float(states["phi_c"][0])),
        "u_hat_rebuild_max_abs_diff": _f(float(states["u_hat_rebuild_max_abs_diff"][0])),
        "bootstrap_method": (
            "stationary (Politis-Romano) block bootstrap over the fitted sample's month "
            "sequence, the same machinery and the same three block lengths every v2 "
            "interval uses. Each draw is refitted; a draw's contiguous stretches are "
            "treated as independent AR(1) blocks, so a splice join cannot invent "
            "persistence. 2.5/97.5 percentile interval"
        ),
        "bootstrap_seed": M4_BOOTSTRAP_SEED,
        "n_bootstrap": N_BOOTSTRAP,
        "primary_block_months": PRIMARY_BLOCK_MONTHS,
        "bootstrap_ci95": bootstrap,
        "recorded_engine_shares": recorded,
        "p2_acceptance": verdict,
        "covariance_caveat": (
            "the strict share sums squared component standard deviations, which assumes "
            "the components are uncorrelated. They are on the generated side, by "
            "construction; they are NOT on history, where the rule-implied rate and the "
            "inflation gap share the inflation trend by definition (their correlation is "
            "reported in point_estimate). So history's total_sum_of_squares exceeds the "
            "slope's own variance, and covariance_aware_share -- the variance of the "
            "summed economic terms over the variance of the slope -- is published beside "
            "it. The strict share is the primary because it is the SAME function the "
            "engine is scored by, which is P2's fourth anti-test obligation; the "
            "covariance-aware number is the disclosure that the two sides' components "
            "are not equally independent"
        ),
    }


def _p2_acceptance(
    primary: dict[str, Any], bootstrap: dict[str, Any], recorded: dict[str, Any]
) -> dict[str, Any]:
    """The pre-declared drop rule for P2, applied mechanically.

    From the design document §3.3, quoted: *"if it comes back with an interval so
    wide that the engines on record sit inside it, P2 should be dropped rather
    than narrowed -- the precedent is A2's low-inflation ceiling, dropped
    pre-seal rather than moved once its cost was visible."*

    Applied on every arm, not only the favourable one. The refitted-rho arm is
    the primary; the pinned-rho arm is checked too, because a rule that only
    holds on the arm that suits the bar is not a rule.
    """
    engine_shares = {
        name: float(row["economic_share"] or 0.0) for name, row in sorted(recorded.items())
    }

    def _check(label: str, ci: dict[str, Any], into: dict[str, Any]) -> bool:
        lo, hi = ci["lo"], ci["hi"]
        inside = {
            engine: bool(lo is not None and hi is not None and lo <= share <= hi)
            for engine, share in engine_shares.items()
        }
        into[label] = {
            "ci95": [lo, hi],
            "engines_inside_interval": inside,
            "margin_below_lower_edge": {
                engine: _f(lo - share) if lo is not None else None
                for engine, share in engine_shares.items()
            },
        }
        return any(inside.values())

    arms: dict[str, Any] = {}
    alternatives: dict[str, Any] = {}
    any_inside = False
    any_inside_alternative = False
    for block_name, block in sorted(bootstrap.items()):
        for arm_name in ("rho_refitted", "rho_pinned_at_point_estimate"):
            any_inside = (
                _check(
                    f"{block_name}__{arm_name}",
                    block[arm_name]["economic_share_ci95"],
                    arms,
                )
                or any_inside
            )
        # The same test on two other summaries of the same fit. These are NOT
        # the pre-declared statistic -- the strict share is, because it is the
        # function the engine is scored by -- but a verdict that held only on
        # the primary summary would be a verdict about the summary.
        for alt in ("r_squared_realised_ci95", "covariance_aware_share_ci95"):
            any_inside_alternative = (
                _check(f"{block_name}__{alt}", block[alt], alternatives) or any_inside_alternative
            )
    primary_ci = primary["rho_refitted"]["economic_share_ci95"]
    return {
        "rule": (
            "P2 is DROPPED if history's interval is so wide that the engines already on "
            "the record sit inside it. Pre-declared in "
            "2026-08-17-stage2-coupled-system-design.md section 3.3, on the A2 "
            "low-inflation-ceiling precedent; applied here without adjustment"
        ),
        "engine_strict_economic_shares": {k: _f(v) for k, v in engine_shares.items()},
        "primary_interval": [primary_ci["lo"], primary_ci["hi"]],
        "per_arm": arms,
        "any_recorded_engine_inside_any_arm": bool(any_inside),
        "verdict": "P2_DROPPED" if any_inside else "P2_KEPT",
        "alternative_summaries": alternatives,
        "any_recorded_engine_inside_any_alternative_summary": bool(any_inside_alternative),
        "verdict_robust_to_the_summary": bool(not any_inside and not any_inside_alternative),
        "reading": (
            "P2 survives only if EVERY arm puts both recorded engines outside history's "
            "interval. One arm placing an engine inside is enough to drop the bar: the "
            "rule is a floor on how informative the anchor is, and it is not negotiated "
            "after the number is seen"
        ),
    }


# --------------------------------------------------------------------------- #
# P1 -- the phase anchors, under both windowing treatments
# --------------------------------------------------------------------------- #

#: ``CLOCKWISE`` as a 4x4 lookup, built FROM the imported frozenset so the clock
#: is never restated by hand.
_CLOCKWISE_MATRIX = np.zeros((len(QUADRANTS), len(QUADRANTS)), dtype=bool)
for _a, _b in CLOCKWISE:
    _CLOCKWISE_MATRIX[_a, _b] = True

#: Which dial a transition moved, as a 4x4 lookup. Codes index :data:`MOVE_TYPES`;
#: ``-1`` is "not a transition". The quadrant encoding is the incumbent's,
#: ``(expanding << 1) | hot``, so the two dials are read straight off the bits.
_EXPANDING_BIT = [((code >> 1) & 1) == 1 for code in range(len(QUADRANTS))]
_HOT_BIT = [(code & 1) == 1 for code in range(len(QUADRANTS))]
_MOVE_MATRIX = np.full((len(QUADRANTS), len(QUADRANTS)), -1, dtype=np.int8)
for _a in range(len(QUADRANTS)):
    for _b in range(len(QUADRANTS)):
        if _a == _b:
            continue
        _dg = _EXPANDING_BIT[_a] != _EXPANDING_BIT[_b]
        _dh = _HOT_BIT[_a] != _HOT_BIT[_b]
        _MOVE_MATRIX[_a, _b] = 2 if (_dg and _dh) else (0 if _dg else 1)


def overlapping_window_weights(n_rows: int) -> np.ndarray:
    """Per-transition weight under EVERY 120-month window of the panel.

    The generated side's construct is: cut into 120-month decades, drop each
    decade's first 12 months (no trailing inflation there), count the
    transitions that survive, pool. Applied to history with one window per start
    row, the pooled fraction is a WEIGHTED fraction over the panel's own
    transitions -- the transition between rows ``t`` and ``t+1`` is counted once
    per window that contains both of them outside the warm-up::

        w(t) = #{s : s <= t - 12 and s >= t - 118, 0 <= s <= n - 120}

    which is what this returns. Computing it this way is exact -- ``main``
    checks it against a literal window-by-window count -- and it makes the
    bootstrap and the phase scramble cheap enough to run at full resolution.
    """
    t = np.arange(n_rows - 1)
    hi = np.minimum(n_rows - DECADE_MONTHS, t - YOY_WARMUP_MONTHS)
    lo = np.maximum(0, t - (DECADE_MONTHS - 2))
    return np.maximum(0, hi - lo + 1).astype(np.float64)


def disjoint_window_weights(n_rows: int) -> np.ndarray:
    """The same, over NON-overlapping decades starting at row 0.

    Uses every month at most once, so it is the sensitivity check on the
    overlapping version's uneven month weighting -- ``spine_v2_anchors.section_k``
    makes the same pair of choices for the same reason, and for the same reason
    this one rests on a handful of decades and is a check, not the anchor.
    """
    weights = np.zeros(n_rows - 1, dtype=np.float64)
    for start in range(0, n_rows - DECADE_MONTHS + 1, DECADE_MONTHS):
        weights[start + YOY_WARMUP_MONTHS : start + DECADE_MONTHS - 1] += 1.0
    return weights


def score_transitions(cells: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    """Weighted clockwise counts, overall and split by which dial moved.

    The transition rule is the pilot's, unchanged and imported: a pair counts
    when both quadrants are defined (``>= 0``) and DIFFER. The split is week 3's
    ``o1_decomposition``: a growth flip changes the growth bit only, an
    inflation crossing the inflation bit only, a diagonal both. No diagonal pair
    is in ``CLOCKWISE``, so diagonals are counter-clockwise by construction and
    are reported rather than folded into either move type.
    """
    arr = np.asarray(cells, dtype=np.int64)
    prev, nxt = arr[:-1], arr[1:]
    valid = (prev >= 0) & (nxt >= 0) & (prev != nxt)
    safe_prev = np.where(valid, prev, 0)
    safe_next = np.where(valid, nxt, 0)
    clockwise = valid & _CLOCKWISE_MATRIX[safe_prev, safe_next]
    move = np.where(valid, _MOVE_MATRIX[safe_prev, safe_next], -1)
    out: dict[str, Any] = {}
    for code, name in enumerate(MOVE_TYPES):
        mask = valid & (move == code)
        total = float(np.sum(weights * mask))
        cw = float(np.sum(weights * (mask & clockwise)))
        out[name] = {
            "weighted_transitions": _f(total),
            "weighted_clockwise": _f(cw),
            "clockwise_fraction": _f(cw / total) if total > 0.0 else None,
        }
    total = float(np.sum(weights * valid))
    cw = float(np.sum(weights * clockwise))
    out["overall"] = {
        "weighted_transitions": _f(total),
        "weighted_clockwise": _f(cw),
        "clockwise_fraction": _f(cw / total) if total > 0.0 else None,
    }
    return out


def _fractions(cells: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    scored = score_transitions(cells, weights)
    return {k: float(v["clockwise_fraction"] or np.nan) for k, v in scored.items()}


def phase_scrambled_null(
    expanding_bit: np.ndarray,
    hot_bit: np.ndarray,
    defined: np.ndarray,
    weights: np.ndarray,
    guard_months: int,
) -> dict[str, Any]:
    """The independence null, measured rather than assumed.

    The construction is the design document's §3.1: circularly shift the
    inflation dial relative to the growth axis, which preserves each dial's own
    dynamics -- its run lengths, its hot share, its persistence -- and destroys
    only their alignment, then rescore. What that produces is the value an
    engine with independent dials would give ON THIS BATCH, so the bar cannot be
    passed or failed by a base-rate accident.

    Two deliberate departures from "many times", both in the direction of
    exactness. Every admissible shift is enumerated rather than sampled, so the
    null needs no seed and has no Monte Carlo error at all. And shifts smaller
    than ``guard_months`` are excluded: a one-month shift destroys almost none
    of the alignment, so including tiny shifts pulls the null toward the
    measured value and flatters the departure the bar is cut from.

    The definedness mask does NOT travel with the shift. A month is undefined
    because the WINDOW it sits in has no trailing inflation there, which is a
    property of the windowing, not of the inflation series -- so the censoring
    stays put and only the hot/cool values move.
    """
    n = int(hot_bit.size)
    shifts = [k for k in range(1, n) if min(k, n - k) >= max(int(guard_months), 1)]
    per_shift: dict[str, list[float]] = {k: [] for k in (*MOVE_TYPES, "overall")}
    for shift in shifts:
        rolled = np.roll(hot_bit, shift)
        cells = np.full(n, -1, dtype=np.int8)
        cells[defined] = (expanding_bit[defined] << 1) | rolled[defined]
        for key, value in _fractions(cells, weights).items():
            per_shift[key].append(value)
    summary: dict[str, Any] = {}
    for key, values in per_shift.items():
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        summary[key] = {
            "null_clockwise_fraction": _f(float(arr.mean())) if arr.size else None,
            "across_shift_sd": _f(float(arr.std())) if arr.size else None,
            "across_shift_ci95": _quantiles(arr),
            "standard_error_of_the_mean": (
                _f(float(arr.std() / math.sqrt(arr.size))) if arr.size else None
            ),
        }
    return {
        "guard_months": int(guard_months),
        "n_shifts": len(shifts),
        "method": (
            "exhaustive circular shift of the hot/cool dial against the growth axis; "
            "every shift of at least guard_months in either direction is scored and the "
            "null is their mean. No seed: the enumeration is complete"
        ),
        "per_move_type": summary,
    }


def bootstrap_fractions(cells: np.ndarray, weights: np.ndarray, seed: int) -> dict[str, Any]:
    """Block-bootstrap intervals for every clockwise fraction, all three lengths.

    The resampling unit is the panel's month sequence, as in
    ``spine_v2_anchors.section_e``, and the same refusal applies: a pair of
    adjacent drawn months is scored ONLY when it is a genuine consecutive pair
    of the real panel, because a join between two unrelated months would invent
    a transition that never happened. The window weight attaches to the pair's
    POSITION in the drawn pseudo-panel, which is what makes the interval an
    interval on the windowed statistic rather than on the panel-wide one.
    """
    n = int(cells.size)
    arr = np.asarray(cells, dtype=np.int64)
    rng = np.random.Generator(np.random.PCG64(seed))
    out: dict[str, Any] = {}
    for block in sorted(BLOCK_LENGTHS_MONTHS):
        index = _stationary_bootstrap_indices(rng, n, block, N_BOOTSTRAP)
        prev_idx, next_idx = index[:, :-1], index[:, 1:]
        genuine = next_idx == (prev_idx + 1)
        prev_cells = np.where(genuine, arr[prev_idx], -1)
        next_cells = np.where(genuine, arr[next_idx], -1)
        valid = (prev_cells >= 0) & (next_cells >= 0) & (prev_cells != next_cells)
        safe_prev = np.where(valid, prev_cells, 0)
        safe_next = np.where(valid, next_cells, 0)
        clockwise = valid & _CLOCKWISE_MATRIX[safe_prev, safe_next]
        move = np.where(valid, _MOVE_MATRIX[safe_prev, safe_next], -1)
        row = {}
        for code, name in ((0, "growth_flip"), (1, "inflation_crossing"), (2, "diagonal")):
            mask = valid & (move == code)
            totals = (mask * weights).sum(axis=1)
            cws = ((mask & clockwise) * weights).sum(axis=1)
            fractions = np.where(totals > 0.0, cws / np.maximum(totals, 1e-12), np.nan)
            row[name] = {
                "clockwise_fraction_ci95": _quantiles(fractions),
                "mean_weighted_transitions_per_draw": _f(float(totals.mean())),
                "draws_used": int(np.isfinite(fractions).sum()),
            }
        totals = (valid * weights).sum(axis=1)
        cws = (clockwise * weights).sum(axis=1)
        fractions = np.where(totals > 0.0, cws / np.maximum(totals, 1e-12), np.nan)
        row["overall"] = {
            "clockwise_fraction_ci95": _quantiles(fractions),
            "mean_weighted_transitions_per_draw": _f(float(totals.mean())),
            "draws_used": int(np.isfinite(fractions).sum()),
        }
        out[f"block_{block}m"] = row
    return out


def _construct(
    name: str,
    description: str,
    cells: np.ndarray,
    weights: np.ndarray,
    expanding_bit: np.ndarray,
    hot_bit: np.ndarray,
    defined: np.ndarray,
) -> dict[str, Any]:
    """One windowing treatment, measured end to end."""
    scored = score_transitions(cells, weights)
    null = phase_scrambled_null(expanding_bit, hot_bit, defined, weights, SCRAMBLE_GUARD_MONTHS)
    null_sensitivity = {
        f"guard_{guard}m": phase_scrambled_null(expanding_bit, hot_bit, defined, weights, guard)
        for guard in SCRAMBLE_GUARD_SENSITIVITY_MONTHS
    }
    intervals = bootstrap_fractions(cells, weights, PHASE_BOOTSTRAP_SEED)
    primary = intervals[f"block_{PRIMARY_BLOCK_MONTHS}m"]

    departures: dict[str, Any] = {}
    for move in (*MOVE_TYPES, "overall"):
        measured = scored[move]["clockwise_fraction"]
        null_value = null["per_move_type"][move]["null_clockwise_fraction"]
        if measured is None or null_value is None:
            departures[move] = {"departure": None}
            continue
        departure = measured - null_value
        ci = primary[move]["clockwise_fraction_ci95"]
        departures[move] = {
            "measured_clockwise_fraction": _f(measured),
            "scrambled_null": _f(null_value),
            "departure": _f(departure),
            "departure_ci95_from_the_fraction_interval": [
                _f(ci["lo"] - null_value) if ci["lo"] is not None else None,
                _f(ci["hi"] - null_value) if ci["hi"] is not None else None,
            ],
            "candidate_p1_threshold": (
                _f(P1_TOLERANCE_FRACTION_OF_HISTORY * departure) if move in P1_MOVE_TYPES else None
            ),
        }
    return {
        "name": name,
        "description": description,
        "clockwise_fractions": scored,
        "scrambled_null": null,
        "scrambled_null_guard_sensitivity": null_sensitivity,
        "bootstrap_ci95": intervals,
        "departures_and_candidate_thresholds": departures,
    }


def _window_starts(n_rows: int, rule: str) -> np.ndarray:
    """Window start rows under the two window rules, from one definition."""
    if rule == "overlapping":
        return np.arange(n_rows - DECADE_MONTHS + 1)
    return np.arange(0, n_rows - DECADE_MONTHS + 1, DECADE_MONTHS)


def within_window_null_constructs(
    cells: np.ndarray,
    expanding_bit: np.ndarray,
    hot_bit: np.ndarray,
    defined: np.ndarray,
) -> dict[str, Any]:
    """The null a batch of decades admits, measured on history's own decades.

    **The correction this section exists to make.** ``P1``'s null is defined as
    *the batch's own* phase scramble. A generated batch is fifty independent
    120-month decades, so the only scramble it admits is a shift INSIDE each
    decade. Every null in :func:`phase_scrambled_null` shifts one 813-month
    panel instead, which is a different operation, and the two disagree by
    enough to move ``P1``'s candidate thresholds -- so the choice is part of the
    bar and not a footnote.

    Both nulls are kept and reported side by side. The within-window one is the
    like-for-like construction, because it is the operation both sides can
    perform on the object each of them actually has.
    """
    n = int(np.asarray(cells).size)
    out: dict[str, Any] = {}
    for rule, name in (("overlapping", "windowed_overlapping"), ("disjoint", "windowed_disjoint")):
        starts = _window_starts(n, rule)
        offsets = np.arange(DECADE_MONTHS)
        windows = np.asarray(cells, dtype=np.int64)[starts[:, None] + offsets[None, :]][
            :, YOY_WARMUP_MONTHS:
        ]
        counts = _window_counts(windows)
        measured = {key: _pooled(counts, key) for key in (*MOVE_TYPES, "overall")}
        # the window-by-window count and the weighted shortcut are two
        # independent ways of pooling the same transitions; if they ever
        # disagree, one of the two constructs is not what it says it is
        weights = (
            overlapping_window_weights(n) if rule == "overlapping" else disjoint_window_weights(n)
        )
        shortcut = _fractions(cells, weights)
        drift = max(abs(measured[key] - shortcut[key]) for key in (*MOVE_TYPES, "overall"))
        if drift > 1e-12:
            raise Stage2Error(
                f"the {rule} window loop and the weighted shortcut disagree by {drift:.3e}"
            )
        null = within_window_scramble_null(
            expanding_bit, hot_bit, defined, starts, DECADE_SCRAMBLE_GUARD_MONTHS
        )
        sensitivity = {
            f"guard_{guard}m": within_window_scramble_null(
                expanding_bit, hot_bit, defined, starts, guard
            )
            for guard in DECADE_SCRAMBLE_GUARD_SENSITIVITY_MONTHS
        }
        departures = {}
        thresholds: dict[str, float | None] = {}
        for move in (*MOVE_TYPES, "overall"):
            null_value = null["per_move_type"][move]["null_clockwise_fraction"]
            if null_value is None or not np.isfinite(measured[move]):
                departures[move] = None
                thresholds[move] = None
                continue
            departure = measured[move] - float(null_value)
            departures[move] = _f(departure)
            thresholds[move] = (
                _f(P1_TOLERANCE_FRACTION_OF_HISTORY * departure) if move in P1_MOVE_TYPES else None
            )
        out[name] = {
            "window_rule": rule,
            "n_windows": int(starts.size),
            "measured_clockwise_fraction": {k: _f(v) for k, v in measured.items()},
            "within_window_null": null,
            "within_window_null_guard_sensitivity": sensitivity,
            "departure": departures,
            "candidate_p1_threshold": thresholds,
        }
    return {
        "why": (
            "P1's null is the BATCH's own scramble, and a batch of independent decades "
            "admits only a shift inside a decade. The panel-wide null shifts one "
            "813-month series, which is a different operation on a different object"
        ),
        "recommendation": (
            "cut P1's threshold from the within-window null, because it is the operation "
            "both sides can perform on the object each of them actually has. The "
            "panel-wide numbers are kept beside it so the size of the choice is visible"
        ),
        **out,
    }


def section_phase(
    cells: np.ndarray,
    labels: np.ndarray,
    yoy: np.ndarray,
    era_threshold_pp: float,
    v2_anchors: dict[str, Any],
) -> dict[str, Any]:
    """P1's re-derivation under both windowing treatments, applied symmetrically."""
    n = int(cells.size)
    contracting = np.isin(np.asarray(labels), list(CONTRACTING_LABELS))
    expanding_bit = (~contracting).astype(np.int8)
    hot_bit = (
        np.nan_to_num(np.asarray(yoy, dtype=np.float64), nan=-np.inf) > era_threshold_pp
    ).astype(np.int8)
    defined = np.asarray(cells) >= 0

    # The scramble machinery must reproduce the panel's own cells at shift 0, or
    # it is scrambling something other than the classifier's inputs.
    rebuilt = np.full(n, -1, dtype=np.int8)
    rebuilt[defined] = (expanding_bit[defined] << 1) | hot_bit[defined]
    if not np.array_equal(rebuilt, np.asarray(cells, dtype=np.int8)):
        raise Stage2Error(
            "the phase scramble's own reconstruction of the panel cells differs from "
            "grader_v2's, so the null would be measured on a different classifier"
        )

    flat = np.ones(n - 1, dtype=np.float64)
    overlapping = overlapping_window_weights(n)
    disjoint = disjoint_window_weights(n)

    constructs = {
        "uncensored_both_sides": _construct(
            "uncensored_both_sides",
            (
                "history read as one 813-month run, which is what every anchor on the "
                "record was measured on. Its symmetric partner on the generated side is "
                "the simulator's INTERNAL season index -- the object the week-3 "
                "o1_decomposition scored, and the one that reads 0.5241 overall"
            ),
            cells,
            flat,
            expanding_bit,
            hot_bit,
            defined,
        ),
        "windowed_overlapping": _construct(
            "windowed_overlapping",
            (
                "history put through the generated side's own machine: every 120-month "
                "window, each losing its first 12 months to the trailing-inflation "
                "warm-up, transitions pooled. One window per start row, so every month "
                "the panel has is used. This is section K's primary window rule, applied "
                "to the ordering statistic instead of to dwell lengths"
            ),
            cells,
            overlapping,
            expanding_bit,
            hot_bit,
            defined,
        ),
        "windowed_disjoint": _construct(
            "windowed_disjoint",
            (
                "the same windowing over NON-overlapping decades, so every month is used "
                "at most once. The sensitivity check on the overlapping version's uneven "
                "month weighting; it rests on a handful of decades and is a check, not "
                "an anchor"
            ),
            cells,
            disjoint,
            expanding_bit,
            hot_bit,
            defined,
        ),
    }

    sealed_ordering = v2_anchors["l_grader_v2"]["full_ordering_v2"]
    uncensored = constructs["uncensored_both_sides"]["clockwise_fractions"]
    reproduces = bool(
        uncensored["overall"]["weighted_transitions"] == float(sealed_ordering["n_transitions"])
        and uncensored["overall"]["weighted_clockwise"]
        == float(sealed_ordering["n_clockwise_transitions"])
    )
    if not reproduces:
        raise Stage2Error(
            "the uncensored construct does not reproduce the sealed grader_v2 ordering "
            f"anchor ({sealed_ordering['n_clockwise_transitions']}/"
            f"{sealed_ordering['n_transitions']}), so the re-derivation is not measuring "
            "the same statistic the bar was cut from"
        )

    # Provenance, and the separation of construct from tape. Re-running the
    # UNCENSORED construct on the SEALED ordering seed must reproduce O1's sealed
    # floor exactly; if it does, then every difference between the sealed floor
    # and the windowed floor below is the construct and not the random draw, and
    # the gap between this and the PHASE_BOOTSTRAP_SEED reading is the Monte
    # Carlo resolution of any floor at N_BOOTSTRAP draws -- which is worth
    # knowing, because O1's margins are of the same order.
    sealed_seed = int(v2_anchors["e_ordering"]["bootstrap_seed"])
    on_sealed_tape = bootstrap_fractions(cells, flat, sealed_seed)[
        f"block_{PRIMARY_BLOCK_MONTHS}m"
    ]["overall"]["clockwise_fraction_ci95"]
    own_tape = constructs["uncensored_both_sides"]["bootstrap_ci95"][
        f"block_{PRIMARY_BLOCK_MONTHS}m"
    ]["overall"]["clockwise_fraction_ci95"]
    tape_check = {
        "sealed_ordering_bootstrap_seed": sealed_seed,
        "o1_floor_recomputed_on_the_sealed_tape": on_sealed_tape["lo"],
        "sealed_o1_floor": sealed_ordering["ci95_lower_edge"],
        "reproduces_sealed_floor_exactly": bool(
            on_sealed_tape["lo"] == sealed_ordering["ci95_lower_edge"]
        ),
        "o1_floor_on_this_module_s_tape": own_tape["lo"],
        "monte_carlo_resolution_between_the_two_tapes": _f(
            float(own_tape["lo"] or np.nan) - float(on_sealed_tape["lo"] or np.nan)
        ),
        "why_this_matters": (
            "the same statistic, the same construct, two different bootstrap tapes at "
            "2000 draws. Their difference is the resolution any floor cut this way has, "
            "and O1's recorded margins are the same size -- so a floor quoted to four "
            "decimals is quoting its tape as much as its data"
        ),
    }

    within = within_window_null_constructs(cells, expanding_bit, hot_bit, defined)

    return {
        "question": (
            "history's clockwise fraction by move type -- P1's anchor -- re-derived under "
            "windowing treatments applied SYMMETRICALLY to both sides, as the "
            "verdict-integrity review's finding C1 requires before P1's threshold is cut"
        ),
        "sealed_tape_provenance_check": tape_check,
        "within_window_null_constructs": within,
        "why": (
            "the sealed O1 judge censors the first 12 months of every generated decade "
            "(10% of them) and the historical side loses one warm-up in 813 months "
            "(1.5%). Every phase anchor on the record was measured on the uncensored "
            "panel. 2026-08-17-spine-v2-results.md section 8.1 rules that a stage-2 seal "
            "must re-derive the anchor with both sides losing the same fraction of their "
            "months before P1's threshold is cut"
        ),
        "grader": "grader_v2 (scripts/spine_v2_grader.py), the sealed classifier",
        "era_threshold_pp": _f(era_threshold_pp),
        "panel_months": n,
        "decade_months": DECADE_MONTHS,
        "warmup_months": YOY_WARMUP_MONTHS,
        "reproduces_sealed_ordering_anchor": reproduces,
        "sealed_ordering_anchor": {
            "clockwise_fraction": sealed_ordering["clockwise_fraction"],
            "n_transitions": sealed_ordering["n_transitions"],
            "n_clockwise_transitions": sealed_ordering["n_clockwise_transitions"],
            "o1_floor": sealed_ordering["ci95_lower_edge"],
        },
        "bootstrap_seed": PHASE_BOOTSTRAP_SEED,
        "n_bootstrap": N_BOOTSTRAP,
        "primary_block_months": PRIMARY_BLOCK_MONTHS,
        "p1_tolerance_fraction_of_history": P1_TOLERANCE_FRACTION_OF_HISTORY,
        "constructs": constructs,
    }


def engines_on_the_record(phase: dict[str, Any], feedback_params: dict[str, Any]) -> dict[str, Any]:
    """P1's retro-anti-test and O1's construct reconciliation, on committed numbers.

    Two obligations are discharged here as far as they can be without
    re-simulating anything.

    **P1's anti-test 3** requires that both engines on the record FAIL the new
    bar -- *"a new bar that passes an engine on the record as uncoupled is
    void"*. Their by-move-type clockwise fractions are committed in week 3's
    artifact (the ``o1_decomposition`` blocks), so each engine's departure can be
    compared with the candidate threshold now, before any stage-2 code is
    written.

    **§8.1's reconciliation** is completed by putting each engine's sealed O1
    reading beside the O1 floor that each construct would cut, so "which
    construct" stops being a framing question and becomes a table.

    **The honest limit, stated where the number is made.** The engine's OWN
    phase-scrambled null is not measured -- it would need the generated batches
    re-simulated, which this module does not do -- so each engine's departure is
    taken against HISTORY's null. On this panel both per-move nulls sit within
    0.001 of 0.500 under every construct and guard band, and the argument for
    0.500 is structural rather than empirical, so the substitution is small; but
    it IS a substitution, and measuring the generated side's own null is a
    prerequisite for sealing P1 rather than an optional extra.
    """
    constructs = phase["constructs"]
    thresholds = {
        name: {
            move: constructs[name]["departures_and_candidate_thresholds"][move][
                "candidate_p1_threshold"
            ]
            for move in P1_MOVE_TYPES
        }
        for name in constructs
    }
    nulls = {
        name: {
            move: constructs[name]["scrambled_null"]["per_move_type"][move][
                "null_clockwise_fraction"
            ]
            for move in P1_MOVE_TYPES
        }
        for name in constructs
    }
    o1_floors = {
        name: constructs[name]["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["overall"][
            "clockwise_fraction_ci95"
        ]["lo"]
        for name in constructs
    }

    rows: dict[str, Any] = {}
    engines = feedback_params["verification"]["engines"]
    for name in sorted(engines):
        for arm, row in sorted(engines[name].items()):
            if not isinstance(row, dict) or "o1_decomposition" not in row:
                continue
            batch = row["o1_decomposition"]["generated_batch"]
            sealed_value = float(row["verdicts_full"]["O1"]["value"])
            sealed_threshold = float(row["verdicts_full"]["O1"]["threshold"])
            internal = float(batch["clockwise_fraction"])
            # The internal path is the uncensored reading; the sealed value is
            # the censored one. Which history anchor each belongs beside is the
            # whole content of the symmetry question.
            o1_by_construct = {
                "uncensored_both_sides": {
                    "generated_value": _f(internal),
                    "generated_construct": "simulator's internal season index (uncensored)",
                    "history_floor": o1_floors["uncensored_both_sides"],
                    "clears": bool(internal >= float(o1_floors["uncensored_both_sides"] or 1.0)),
                },
                "windowed_overlapping": {
                    "generated_value": _f(sealed_value),
                    "generated_construct": "the sealed judge's censored decades (unchanged)",
                    "history_floor": o1_floors["windowed_overlapping"],
                    "clears": bool(sealed_value >= float(o1_floors["windowed_overlapping"] or 1.0)),
                },
                "windowed_disjoint": {
                    "generated_value": _f(sealed_value),
                    "generated_construct": "the sealed judge's censored decades (unchanged)",
                    "history_floor": o1_floors["windowed_disjoint"],
                    "clears": bool(sealed_value >= float(o1_floors["windowed_disjoint"] or 1.0)),
                },
            }
            p1_rows: dict[str, Any] = {}
            for construct in constructs:
                per_move = {}
                for move in P1_MOVE_TYPES:
                    fraction = float(batch["by_move"][move]["clockwise_fraction"])
                    null = float(nulls[construct][move] or 0.5)
                    threshold = float(thresholds[construct][move] or 0.0)
                    departure = fraction - null
                    per_move[move] = {
                        "generated_clockwise_fraction": _f(fraction),
                        "history_null_used": _f(null),
                        "departure": _f(departure),
                        "candidate_threshold": _f(threshold),
                        "passes": bool(departure >= threshold),
                    }
                p1_rows[construct] = {
                    "per_move": per_move,
                    "passes_both_move_types": bool(all(v["passes"] for v in per_move.values())),
                }
            rows[f"{name}__{arm}"] = {
                "sealed_o1_value": _f(sealed_value),
                "sealed_o1_threshold": _f(sealed_threshold),
                "sealed_o1_pass": bool(sealed_value >= sealed_threshold),
                "internal_path_o1_value": _f(internal),
                "o1_under_each_history_construct": o1_by_construct,
                "p1_retro_anti_test": p1_rows,
            }

    any_pass = any(
        row["p1_retro_anti_test"][construct]["passes_both_move_types"]
        for row in rows.values()
        for construct in constructs
    )
    return {
        "p1_anti_test_3": {
            "requirement": (
                "every engine on the record must FAIL the candidate P1 bar; a new bar "
                "that passes an engine known to be uncoupled is void"
            ),
            "any_recorded_engine_passes_under_any_construct": bool(any_pass),
            "holds": bool(not any_pass),
        },
        "null_substitution_disclosure": (
            "each engine's departure is taken against HISTORY's phase-scrambled null, not "
            "its own. Measuring the generated side's own null needs the batches "
            "re-simulated and is a prerequisite for SEALING P1, not for anchoring it"
        ),
        "per_engine_arm": rows,
    }


def recommended_construct(phase: dict[str, Any], v2_anchors: dict[str, Any]) -> dict[str, Any]:
    """Which construct the stage-2 seal should adopt, with the numbers behind it."""
    windowed = phase["constructs"]["windowed_overlapping"]
    uncensored = phase["constructs"]["uncensored_both_sides"]
    disjoint = phase["constructs"]["windowed_disjoint"]
    o1_floor_candidates = {
        name: phase["constructs"][name]["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"][
            "overall"
        ]["clockwise_fraction_ci95"]["lo"]
        for name in ("uncensored_both_sides", "windowed_overlapping", "windowed_disjoint")
    }
    return {
        "recommendation": "windowed_overlapping",
        "candidate_p1_thresholds": {
            name: {
                move: phase["constructs"][name]["departures_and_candidate_thresholds"][move][
                    "candidate_p1_threshold"
                ]
                for move in P1_MOVE_TYPES
            }
            for name in ("uncensored_both_sides", "windowed_overlapping", "windowed_disjoint")
        },
        "o1_floor_under_each_construct": o1_floor_candidates,
        "sealed_o1_floor": v2_anchors["l_grader_v2"]["full_ordering_v2"]["ci95_lower_edge"],
        "measured_effect_of_symmetrising": {
            move: {
                "uncensored": uncensored["clockwise_fractions"][move]["clockwise_fraction"],
                "windowed_overlapping": windowed["clockwise_fractions"][move]["clockwise_fraction"],
                "windowed_disjoint": disjoint["clockwise_fractions"][move]["clockwise_fraction"],
                "windowed_minus_uncensored": _f(
                    float(windowed["clockwise_fractions"][move]["clockwise_fraction"] or np.nan)
                    - float(uncensored["clockwise_fractions"][move]["clockwise_fraction"] or np.nan)
                ),
            }
            for move in (*MOVE_TYPES, "overall")
        },
        "why": (
            "the censoring is a property of what the engine EMITS, not of how it is "
            "judged: a generated decade genuinely has no trailing inflation for its "
            "first twelve months, and the alternative -- scoring the simulator's "
            "internal season index -- judges an object the sealed pipeline never "
            "produces and the product never shows. Putting history through the same "
            "windowing machine is the same remedy PRE-SEAL RULING 1 applied to D1-D4 "
            "and section K applied to the dwell anchors, and it is the only one of the "
            "two symmetric constructs that leaves the judged object unchanged"
        ),
    }


# --------------------------------------------------------------------------- #
# M3 -- the growth -> inflation coupling, tested as a GATE on P1
# --------------------------------------------------------------------------- #


def _m3_month_index(x_gap: np.ndarray, observed: np.ndarray) -> np.ndarray:
    """The months every lag in the grid can be evaluated on -- ONE sample.

    Two rules, and the second is the one that matters. Months whose trailing
    12-month inflation does not exist yet are dropped: ``build_panel`` fills
    those with the trend, which sets the gap to exactly zero, and twelve
    manufactured zeros at the head of a persistence regression would read as
    persistence. And the sample opens at the LONGEST lag in the grid, so every
    lag is fitted on exactly the same months -- without that, selecting a lag by
    likelihood would be comparing likelihoods computed on different samples,
    which is not a comparison at all.
    """
    n = int(x_gap.size)
    longest = int(max(M3_LAG_GRID_MONTHS))
    t = np.arange(n - 1)
    keep = observed[t] & observed[t + 1] & (t >= longest)
    return t[keep]


def _m3_rows(
    x_gap: np.ndarray, cycle: np.ndarray, months: np.ndarray, lag: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The equation's response and its two regressors, at lag ``m``.

    The design document's inflation line, with ``dt`` one month::

        x_{t+1} = (1 - k_x) x_t + lam_x (c_{t-m} - cbar) + sig_x e_t

    so a row needs the inflation gap at ``t`` and ``t+1`` and the cycle input at
    ``t - m``. ``months`` is the common index from :func:`_m3_month_index`, so
    row ``i`` is the same calendar month at every lag.
    """
    return x_gap[months + 1], x_gap[months], cycle[months - int(lag)]


def _m3_fit(y: np.ndarray, x_t: np.ndarray, c_lag: np.ndarray, cbar: float) -> dict[str, float]:
    """The coupled equation and its no-coupling restriction, both by ML.

    Least squares IS the Gaussian maximum likelihood here, so the likelihood
    ratio is a function of the two residual sums of squares and nothing else.
    Both fits are returned from one call so the restriction is guaranteed to be
    the same equation with one column removed rather than a separately written
    model.
    """
    design = np.column_stack([np.ones(y.size), x_t, c_lag - cbar])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    rss = float(resid @ resid)
    restricted = design[:, :2]
    beta0, *_ = np.linalg.lstsq(restricted, y, rcond=None)
    resid0 = y - restricted @ beta0
    rss0 = float(resid0 @ resid0)
    n = int(y.size)
    loglik = -0.5 * n * (math.log(2.0 * math.pi) + math.log(rss / n) + 1.0)
    loglik0 = -0.5 * n * (math.log(2.0 * math.pi) + math.log(rss0 / n) + 1.0)
    dof = max(n - design.shape[1], 1)
    covariance = (rss / dof) * np.linalg.inv(design.T @ design)
    se = math.sqrt(float(covariance[2, 2]))
    persistence = float(beta[1])
    return {
        "lam_x": float(beta[2]),
        "persistence_a": persistence,
        "intercept": float(beta[0]),
        "standard_error_lam_x": se,
        "t_ratio": float(beta[2]) / se if se > 0.0 else float("nan"),
        "loglik": loglik,
        "loglik_no_coupling": loglik0,
        "lr_statistic": 2.0 * (loglik - loglik0),
        "residual_sd": math.sqrt(rss / n),
        "n_rows": float(n),
        # the level the gap settles at while the economy sits at c = +1, i.e.
        # what the channel is worth once it has finished working
        "long_run_gap_at_full_expansion_pp": (
            float(beta[2]) * (1.0 - cbar) / (1.0 - persistence)
            if abs(1.0 - persistence) > 1e-9
            else float("nan")
        ),
        "residual_autocorrelation_lag1": (
            float(np.corrcoef(resid[:-1], resid[1:])[0, 1]) if n > 2 else float("nan")
        ),
    }


def _m3_profile(
    x_gap: np.ndarray, cycle: np.ndarray, months: np.ndarray
) -> tuple[dict[int, dict[str, float]], int]:
    """The whole lag profile on one sample, and the lag the likelihood selects."""
    profile = {}
    for lag in M3_LAG_GRID_MONTHS:
        y, x_t, c_lag = _m3_rows(x_gap, cycle, months, lag)
        profile[int(lag)] = _m3_fit(y, x_t, c_lag, float(c_lag.mean()))
    selected = max(profile, key=lambda k: profile[k]["loglik"])
    return profile, int(selected)


def _m3_shift_null(
    x_gap: np.ndarray, cycle: np.ndarray, months: np.ndarray, guard_months: int
) -> dict[str, Any]:
    """The significance test that survives the residual's own structure.

    **Why the nominal p-value is not enough, stated before the number is used.**
    The inflation gap is built from a TRAILING 12-month inflation rate, so
    consecutive months share eleven of their twelve price changes and the
    equation's residual carries a moving-average structure by construction. A
    chi-square read off a likelihood ratio assumes independent innovations, so
    it will overstate the evidence. Two devices are therefore applied and the
    gate requires both: a block bootstrap of the coefficient (which resamples
    runs of months and so carries the dependence), and this one.

    **The construction.** Circularly shift the cycle input against the
    inflation gap, which preserves each series' own dynamics -- the cycle keeps
    its run lengths and its expanding share, the gap keeps its persistence and
    its variance -- and destroys only their alignment. Refit the whole lag grid
    on the shifted pair and keep the BEST likelihood ratio it reaches. The
    distribution of that maximum over every admissible shift is what a
    25-lag search finds on two series with no relationship, so comparing the
    observed maximum with it prices the search as well as the coefficient.
    Every admissible shift is enumerated, so this needs no seed.
    """
    n = int(x_gap.size)
    shifts = [k for k in range(1, n) if min(k, n - k) >= max(int(guard_months), 1)]
    per_shift_max = np.empty(len(shifts), dtype=np.float64)
    per_lag: dict[int, list[float]] = {int(lag): [] for lag in M3_LAG_GRID_MONTHS}
    for i, shift in enumerate(shifts):
        rolled = np.roll(cycle, shift)
        best = -np.inf
        for lag in M3_LAG_GRID_MONTHS:
            y, x_t, c_lag = _m3_rows(x_gap, rolled, months, lag)
            statistic = _m3_fit(y, x_t, c_lag, float(c_lag.mean()))["lr_statistic"]
            per_lag[int(lag)].append(statistic)
            best = max(best, statistic)
        per_shift_max[i] = best
    return {
        "guard_months": int(guard_months),
        "n_shifts": len(shifts),
        "max_over_the_lag_grid": per_shift_max,
        "per_lag": {lag: np.asarray(v, dtype=np.float64) for lag, v in per_lag.items()},
    }


def _m3_bootstrap(
    x_gap: np.ndarray, cycle: np.ndarray, months: np.ndarray, selected_lag: int
) -> dict[str, Any]:
    """Block-bootstrap intervals for ``lam_x``, both with the lag held and re-chosen.

    The resampling unit is the equation's own ROW -- a complete
    ``(x_{t+1}, x_t, c_{t-m})`` triple -- because the dynamics this equation
    claims are inside a row, not between rows. Runs of consecutive rows still
    travel together, which is what carries the trailing-inflation residual's
    moving-average structure into the interval. Because every lag is fitted on
    the same months, one drawn index means the same set of real months at every
    lag, so the two arms below share one tape.

    The second arm re-selects the lag on every draw. That is the honest one for
    a coefficient whose lag was chosen by likelihood: an interval computed at a
    lag the full sample chose cannot know how much of its own position came
    from that choice.
    """
    rows = {int(lag): _m3_rows(x_gap, cycle, months, lag) for lag in M3_LAG_GRID_MONTHS}
    y, x_t, c_lag = rows[int(selected_lag)]
    n = int(y.size)
    rng = np.random.Generator(np.random.PCG64(M3_BOOTSTRAP_SEED))
    out: dict[str, Any] = {}
    for block in sorted(BLOCK_LENGTHS_MONTHS):
        index = _stationary_bootstrap_indices(rng, n, block, N_BOOTSTRAP)
        held = np.empty(N_BOOTSTRAP, dtype=np.float64)
        reselected = np.empty(N_BOOTSTRAP, dtype=np.float64)
        chosen = np.empty(N_BOOTSTRAP, dtype=np.float64)
        for draw in range(N_BOOTSTRAP):
            row = index[draw]
            held[draw] = _m3_fit(y[row], x_t[row], c_lag[row], float(c_lag[row].mean()))["lam_x"]
            best_lag, best_ll, best_lam = int(selected_lag), -np.inf, float("nan")
            for lag in M3_LAG_GRID_MONTHS:
                yb, xb, cb = rows[int(lag)]
                fit = _m3_fit(yb[row], xb[row], cb[row], float(cb[row].mean()))
                if fit["loglik"] > best_ll:
                    best_lag, best_ll, best_lam = int(lag), fit["loglik"], fit["lam_x"]
            reselected[draw] = best_lam
            chosen[draw] = float(best_lag)
        held_ci = _quantiles(held)
        reselected_ci = _quantiles(reselected)
        out[f"block_{block}m"] = {
            "lam_x_ci95_lag_held": held_ci,
            "lam_x_ci95_lag_reselected": reselected_ci,
            "selected_lag_median_across_draws": _f(float(np.median(chosen))),
            "share_of_draws_selecting_within_3_months": _f(
                float(np.mean(np.abs(chosen - float(selected_lag)) <= 3.0))
            ),
            "excludes_zero_lag_held": bool(
                held_ci["lo"] is not None and float(held_ci["lo"]) > 0.0
            ),
            "excludes_zero_lag_reselected": bool(
                reselected_ci["lo"] is not None and float(reselected_ci["lo"]) > 0.0
            ),
        }
    return out


def section_m3(
    panel: Panel, states: dict[str, np.ndarray], yoy: np.ndarray, cells: np.ndarray
) -> dict[str, Any]:
    """M3 as a gate: can history establish the channel P1 exists to test?

    **The pre-declared rule, written down before the number was read and
    applied here without adjustment.** ``P1`` asks a generated engine to
    reproduce half of history's growth/inflation phase relation. If history
    itself cannot establish that inflation responds to growth at all, then the
    bar demands of the engine a fact the panel does not contain, and the
    precedent is the one the design document names for ``P2``: ``A2``'s
    low-inflation ceiling, **dropped pre-seal rather than moved** once its cost
    was visible. So:

        P1 is DROPPED unless all three hold ---
          (i)   the likelihood ratio against no coupling rejects at 95% under
                the SELECTION-AWARE null, which prices the 25-lag search;
          (ii)  the block-bootstrap 95% interval for lam_x excludes zero at
                EVERY one of the three block lengths, on both the held-lag and
                the re-selected-lag arm;
          (iii) the coefficient has the sign the mechanism requires -- positive,
                inflation rising after expansions -- because a significant
                coefficient of the wrong sign is not the channel.

    Three conditions rather than one because each covers a different way of
    being wrong: (i) the search, (ii) the residual's dependence, (iii) the
    direction. Any one failing drops the bar.
    """
    x_gap = np.asarray(states["x_gap"], dtype=np.float64)
    cycle = np.asarray(states["cycle"], dtype=np.float64)
    observed = np.isfinite(np.asarray(yoy, dtype=np.float64))
    months = _m3_month_index(x_gap, observed)
    profile, selected = _m3_profile(x_gap, cycle, months)
    point = profile[selected]

    null = _m3_shift_null(x_gap, cycle, months, SCRAMBLE_GUARD_MONTHS)
    maxima = null["max_over_the_lag_grid"]
    at_lag = null["per_lag"][selected]
    # the conservative plug-in p-value: the observed statistic is counted as one
    # of the draws, so a p-value can never be exactly zero on a finite null
    p_selection_aware = float((np.sum(maxima >= point["lr_statistic"]) + 1) / (maxima.size + 1))
    p_at_selected_lag = float((np.sum(at_lag >= point["lr_statistic"]) + 1) / (at_lag.size + 1))

    bootstrap = _m3_bootstrap(x_gap, cycle, months, selected)

    # the sensitivity the classifier's own growth axis gives, reported because
    # the cycle input is a CONTRACT (1 - 2*USREC, the WP2.6 array L1 consumes)
    # and a reader is entitled to know whether the channel depends on it
    contracting = np.isin(np.asarray(panel.labels), list(CONTRACTING_LABELS))
    classifier_cycle = 1.0 - 2.0 * contracting.astype(np.float64)
    classifier_profile, classifier_lag = _m3_profile(x_gap, classifier_cycle, months)

    rejects = p_selection_aware <= 0.05
    excludes_zero = all(
        row["excludes_zero_lag_held"] and row["excludes_zero_lag_reselected"]
        for row in bootstrap.values()
    )
    right_sign = point["lam_x"] > 0.0
    established = bool(rejects and excludes_zero and right_sign)
    return {
        "question": (
            "does history establish the growth -> inflation channel at all? P1 asks an "
            "engine for half of history's phase relation, and a bar cannot demand of the "
            "engine a fact history cannot establish"
        ),
        "equation": (
            "x_{t+1} = a x_t + lam_x (c_{t-m} - cbar) + e_t, the design document's "
            "inflation line at dt = one month, where x is the inflation gap (trailing "
            "12-month CPI minus L1's trend) and c is the cycle input, +1 expanding and "
            "-1 contracting, from fred.USREC -- the WP2.6 contract L1 already consumes"
        ),
        "model_class": (
            "the spec's own: one row of the coupled monthly system, estimated on the "
            "historical panel where both sides are observed. Least squares is the "
            "Gaussian ML for it, so the no-coupling restriction lam_x = 0 is nested "
            "exactly and the test is a likelihood ratio rather than an argument"
        ),
        "sample": {
            "panel_months": int(x_gap.size),
            "months_with_trailing_inflation": int(observed.sum()),
            "rows_in_the_common_sample": int(months.size),
            "why_the_warmup_is_dropped": (
                "build_panel fills the first twelve months' inflation with the trend, "
                "which sets the gap to exactly zero; twelve manufactured zeros at the "
                "head of a persistence regression would read as persistence"
            ),
            "why_one_common_sample": (
                "every lag is fitted on the SAME months -- the sample opens at the "
                "longest lag in the grid -- because selecting a lag by likelihood across "
                "samples of different lengths is not a comparison. It costs the "
                "twenty-four rows the longest lag cannot reach"
            ),
        },
        "lag_grid_months": list(M3_LAG_GRID_MONTHS),
        "lag_profile": {
            str(lag): {k: _f(v) for k, v in row.items()} for lag, row in sorted(profile.items())
        },
        "selected_lag_months": selected,
        "selection_rule": (
            "the lag with the highest likelihood on the stated grid, at constant "
            "parameter count -- the same discipline that chose the curve's nine-month "
            "lead, with the whole profile published above"
        ),
        "point_estimate": {k: _f(v) for k, v in point.items()},
        "nominal_chi2_p_value": _f(_chi2_sf_df1(point["lr_statistic"])),
        "nominal_p_value_is_not_the_test": (
            "the inflation gap is built from a TRAILING 12-month rate, so consecutive "
            "months share eleven of their twelve price changes and the residual carries "
            "a moving-average structure by construction. A chi-square off a likelihood "
            "ratio assumes independent innovations and will overstate the evidence; the "
            "measured lag-1 residual autocorrelation is in point_estimate. The gate "
            "therefore rests on the shift null and the block bootstrap, both of which "
            "carry the dependence, and the nominal value is reported only for scale"
        ),
        "selection_aware_null": {
            "method": (
                "circular shift of the cycle input against the inflation gap, every "
                "admissible shift enumerated (no seed), the whole 25-lag grid refitted on "
                "each shifted pair and its BEST likelihood ratio kept. That maximum's "
                "distribution is what a 25-lag search finds on two unrelated series, so "
                "the comparison prices the search as well as the coefficient"
            ),
            "guard_months": int(null["guard_months"]),
            "n_shifts": int(null["n_shifts"]),
            "max_lr_null_percentiles": {
                "p50": _f(float(np.percentile(maxima, 50))),
                "p95": _f(float(np.percentile(maxima, 95))),
                "p99": _f(float(np.percentile(maxima, 99))),
                "max": _f(float(maxima.max())),
            },
            "observed_max_lr": _f(point["lr_statistic"]),
            "p_value_selection_aware": _f(p_selection_aware),
            "p_value_at_the_selected_lag_only": _f(p_at_selected_lag),
            "rejects_at_95": bool(rejects),
        },
        "block_bootstrap": bootstrap,
        "bootstrap_seed": M3_BOOTSTRAP_SEED,
        "n_bootstrap": N_BOOTSTRAP,
        "cycle_input_sensitivity": {
            "note": (
                "the same equation with the classifier's own growth axis (grader_v2's "
                "contracting labels) in place of fred.USREC. The primary is USREC "
                "because it is the contract L1 consumes; this arm exists so a reader can "
                "see whether the channel is a property of the economy or of the labeller"
            ),
            "selected_lag_months": classifier_lag,
            "point_estimate": {k: _f(v) for k, v in classifier_profile[classifier_lag].items()},
            "same_sign_as_primary": bool(
                classifier_profile[classifier_lag]["lam_x"] * point["lam_x"] > 0.0
            ),
        },
        "chi2_df1_check": _assert_chi2_df1(),
        "cells_reference": {
            "n_defined_cells": int(np.sum(np.asarray(cells) >= 0)),
            "note": (
                "carried so the reader can see this section reads the same panel the "
                "phase section does; the coupling test itself does not use the cells"
            ),
        },
        "gate": {
            "rule": (
                "P1 is DROPPED unless (i) the likelihood ratio rejects at 95% under the "
                "SELECTION-AWARE null, (ii) the block-bootstrap 95% interval for lam_x "
                "excludes zero at every block length on both arms, and (iii) lam_x is "
                "POSITIVE, the sign the mechanism requires. Pre-declared before the "
                "number was read; the precedent for dropping rather than narrowing is "
                "A2's low-inflation ceiling"
            ),
            "condition_i_selection_aware_rejection": bool(rejects),
            "condition_ii_bootstrap_excludes_zero_everywhere": bool(excludes_zero),
            "condition_iii_sign_is_positive": bool(right_sign),
            "coupling_established_on_the_panel": established,
            "verdict": "P1_KEPT" if established else "P1_DROPPED",
            "reading": (
                "a KEEP means only that the channel P1 tests for is present in history at "
                "95%, which is the floor for the bar being askable at all. It is NOT a "
                "statement that the engine can reach the bar -- that is the power "
                "calculation below -- and it is not a verdict on any engine"
            ),
        },
    }


# --------------------------------------------------------------------------- #
# M3's second half -- the power calculation, on history as the true engine
# --------------------------------------------------------------------------- #


def _window_counts(block: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per-row ``(transitions, clockwise)`` counts for a stack of month runs.

    ``block`` is ``(rows, months)`` of season cells. The transition rule is the
    one :func:`score_transitions` uses, unchanged -- both quadrants defined and
    different -- and the split is the same ``_MOVE_MATRIX``. This form exists
    because the power calculation needs the counts PER WINDOW so that a
    replicate is a sum over selected windows rather than a rescoring.
    """
    arr = np.asarray(block, dtype=np.int64)
    prev, nxt = arr[..., :-1], arr[..., 1:]
    valid = (prev >= 0) & (nxt >= 0) & (prev != nxt)
    safe_prev = np.where(valid, prev, 0)
    safe_next = np.where(valid, nxt, 0)
    clockwise = valid & _CLOCKWISE_MATRIX[safe_prev, safe_next]
    move = np.where(valid, _MOVE_MATRIX[safe_prev, safe_next], -1)
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for code, name in enumerate(MOVE_TYPES):
        mask = valid & (move == code)
        out[name] = (mask.sum(axis=-1), (mask & clockwise).sum(axis=-1))
    out["overall"] = (valid.sum(axis=-1), clockwise.sum(axis=-1))
    return out


def _pooled(counts: dict[str, tuple[np.ndarray, np.ndarray]], key: str) -> float:
    total = float(np.sum(counts[key][0]))
    return float(np.sum(counts[key][1]) / total) if total > 0.0 else float("nan")


def within_window_scramble_null(
    expanding_bit: np.ndarray,
    hot_bit: np.ndarray,
    defined: np.ndarray,
    starts: np.ndarray,
    guard_months: int,
    censor: bool = True,
) -> dict[str, Any]:
    """The phase-scramble null a batch of DECADES actually admits.

    **Why this exists and why it is not the same as the panel-wide null.** P1's
    null is defined as *the batch's own* scramble. A generated batch is fifty
    120-month decades with no time axis between them, so the only shift it
    admits is a shift INSIDE each decade. The panel-wide null already computed
    in :func:`phase_scrambled_null` shifts one 813-month series, which is a
    different operation on a different object -- and the two do not agree, so
    which one P1's threshold is cut from is a real choice and not a detail.

    The same shift is applied to every window, and every admissible shift is
    enumerated, so this needs no seed either. ``censor`` drops each window's
    first ``YOY_WARMUP_MONTHS`` months, which is what the sealed judge does to
    a generated decade.
    """
    offsets = np.arange(DECADE_MONTHS)
    index = np.asarray(starts, dtype=np.int64)[:, None] + offsets[None, :]
    hot_win = np.asarray(hot_bit, dtype=np.int64)[index]
    expanding_win = np.asarray(expanding_bit, dtype=np.int64)[index]
    defined_win = np.asarray(defined, dtype=bool)[index]
    shifts = [
        k for k in range(1, DECADE_MONTHS) if min(k, DECADE_MONTHS - k) >= max(int(guard_months), 1)
    ]
    per_shift: dict[str, list[float]] = {k: [] for k in (*MOVE_TYPES, "overall")}
    for shift in shifts:
        rolled = np.roll(hot_win, shift, axis=1)
        cells = np.where(defined_win, (expanding_win << 1) | rolled, -1)
        if censor:
            cells = cells[:, YOY_WARMUP_MONTHS:]
        counts = _window_counts(cells)
        for key in per_shift:
            per_shift[key].append(_pooled(counts, key))
    summary: dict[str, Any] = {}
    for key, values in per_shift.items():
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        summary[key] = {
            "null_clockwise_fraction": _f(float(arr.mean())) if arr.size else None,
            "across_shift_sd": _f(float(arr.std())) if arr.size else None,
            "across_shift_ci95": _quantiles(arr),
        }
    return {
        "guard_months": int(guard_months),
        "n_shifts": len(shifts),
        "n_windows": int(np.asarray(starts).size),
        "censored": bool(censor),
        "method": (
            "circular shift of the hot/cool dial WITHIN each window, the same shift in "
            "every window, every admissible shift enumerated. This is the only scramble "
            "a batch of independent decades admits, and it is not the same operation as "
            "shifting one long panel"
        ),
        "per_move_type": summary,
    }


def section_m3_power(
    cells: np.ndarray,
    labels: np.ndarray,
    yoy: np.ndarray,
    era_threshold_pp: float,
    phase: dict[str, Any],
    m4: dict[str, Any],
    states: dict[str, np.ndarray],
    panel: Panel,
    n_decades: int,
) -> dict[str, Any]:
    """Can a CORRECT engine clear P1 and P2 at fifty decades?

    The exam's standing rule is that a bar a correct engine cannot clear is a
    bar-design defect, and two bars were caught that way pre-seal. The design
    document says this needs "a true engine emitting real 120-month stretches".
    There is no stage-2 engine yet, so the true engine used here is **history
    itself**: each replicate draws ``n_decades`` 120-month stretches of the real
    panel, with replacement, and puts them through the judge exactly as a
    generated batch would go through it -- the first twelve months of each
    stretch censored, the rest pooled.

    **What that measures and what it does not.** History is the most favourable
    engine there is: its phase relation is the anchor, by definition. So the
    pass rate below is an UPPER BOUND on the power of any real engine, and its
    only content is whether the bar is reachable at all at this batch size --
    which is exactly what the standing rule asks. Two honest limits: the
    stretches are drawn from the same 813 months the threshold is cut from, so
    this cannot see the anchor's own estimation error (§2.9 is where that lives,
    and it is the larger risk); and overlapping stretches are positively
    correlated, which widens a replicate's spread relative to a real engine's
    independent decades and therefore makes this if anything conservative.
    """
    n = int(np.asarray(cells).size)
    starts = np.arange(n - DECADE_MONTHS + 1)
    contracting = np.isin(np.asarray(labels), list(CONTRACTING_LABELS))
    expanding_bit = (~contracting).astype(np.int64)
    hot_bit = (
        np.nan_to_num(np.asarray(yoy, dtype=np.float64), nan=-np.inf) > era_threshold_pp
    ).astype(np.int64)
    defined = np.asarray(cells) >= 0

    offsets = np.arange(DECADE_MONTHS)
    index = starts[:, None] + offsets[None, :]
    window_cells = np.asarray(cells, dtype=np.int64)[index][:, YOY_WARMUP_MONTHS:]
    observed_counts = _window_counts(window_cells)

    # the null, per shift and per window, precomputed once so a replicate is a
    # sum over the windows it drew rather than a rescoring of them
    hot_win = hot_bit[index]
    expanding_win = expanding_bit[index]
    defined_win = defined[index]
    shifts = [
        k
        for k in range(1, DECADE_MONTHS)
        if min(k, DECADE_MONTHS - k) >= DECADE_SCRAMBLE_GUARD_MONTHS
    ]
    null_totals = {name: [] for name in P1_MOVE_TYPES}
    null_clockwise = {name: [] for name in P1_MOVE_TYPES}
    for shift in shifts:
        rolled = np.roll(hot_win, shift, axis=1)
        scrambled = np.where(defined_win, (expanding_win << 1) | rolled, -1)[:, YOY_WARMUP_MONTHS:]
        counts = _window_counts(scrambled)
        for name in P1_MOVE_TYPES:
            null_totals[name].append(counts[name][0])
            null_clockwise[name].append(counts[name][1])
    null_totals = {k: np.asarray(v, dtype=np.float64) for k, v in null_totals.items()}
    null_clockwise = {k: np.asarray(v, dtype=np.float64) for k, v in null_clockwise.items()}

    thresholds = {
        move: float(
            phase["constructs"]["windowed_overlapping"]["departures_and_candidate_thresholds"][
                move
            ]["candidate_p1_threshold"]
            or 0.0
        )
        for move in P1_MOVE_TYPES
    }
    within_window_thresholds = {
        move: float(
            phase["within_window_null_constructs"]["windowed_overlapping"][
                "candidate_p1_threshold"
            ][move]
            or 0.0
        )
        for move in P1_MOVE_TYPES
    }

    rng = np.random.Generator(np.random.PCG64(M3_POWER_SEED))
    drawn = rng.integers(0, starts.size, size=(M3_POWER_REPLICATES, int(n_decades)))
    departures = {move: np.empty(M3_POWER_REPLICATES) for move in P1_MOVE_TYPES}
    own_nulls = {move: np.empty(M3_POWER_REPLICATES) for move in P1_MOVE_TYPES}
    fractions = {move: np.empty(M3_POWER_REPLICATES) for move in P1_MOVE_TYPES}
    for replicate in range(M3_POWER_REPLICATES):
        pick = drawn[replicate]
        for move in P1_MOVE_TYPES:
            total = float(observed_counts[move][0][pick].sum())
            clockwise = float(observed_counts[move][1][pick].sum())
            fraction = clockwise / total if total > 0.0 else np.nan
            null_t = null_totals[move][:, pick].sum(axis=1)
            null_c = null_clockwise[move][:, pick].sum(axis=1)
            own = float(np.mean(np.where(null_t > 0, null_c / np.maximum(null_t, 1.0), np.nan)))
            fractions[move][replicate] = fraction
            own_nulls[move][replicate] = own
            departures[move][replicate] = fraction - own

    per_move: dict[str, Any] = {}
    passes_own = np.ones(M3_POWER_REPLICATES, dtype=bool)
    passes_history_null = np.ones(M3_POWER_REPLICATES, dtype=bool)
    for move in P1_MOVE_TYPES:
        history_null = float(
            phase["constructs"]["windowed_overlapping"]["scrambled_null"]["per_move_type"][move][
                "null_clockwise_fraction"
            ]
            or 0.5
        )
        own_pass = departures[move] >= within_window_thresholds[move]
        hist_pass = (fractions[move] - history_null) >= thresholds[move]
        passes_own &= own_pass
        passes_history_null &= hist_pass
        per_move[move] = {
            "mean_clockwise_fraction": _f(float(np.mean(fractions[move]))),
            "clockwise_fraction_ci95": _quantiles(fractions[move]),
            "mean_own_within_window_null": _f(float(np.mean(own_nulls[move]))),
            "history_panel_wide_null": _f(history_null),
            "mean_departure_against_own_null": _f(float(np.mean(departures[move]))),
            "departure_ci95_against_own_null": _quantiles(departures[move]),
            "threshold_against_own_null": _f(within_window_thresholds[move]),
            "threshold_against_panel_wide_null": _f(thresholds[move]),
            "power_against_own_null": _f(float(np.mean(own_pass))),
            "power_against_panel_wide_null": _f(float(np.mean(hist_pass))),
        }

    p2_power = _p2_power(m4, states, panel, drawn, starts.size, n_decades)
    return {
        "question": (
            "the exam's standing rule: is a bar a CORRECT engine can clear? Measured at "
            f"{n_decades} decades, the sealed batch size, on a true engine"
        ),
        "true_engine": (
            "history itself, emitting real 120-month stretches drawn with replacement "
            "from the campaign panel and judged exactly as a generated batch is -- first "
            "twelve months of each stretch censored, the rest pooled. It is the most "
            "favourable engine that exists, so these pass rates are an UPPER BOUND on any "
            "real engine's"
        ),
        "limits": (
            "the stretches come from the same 813 months the threshold is cut from, so "
            "this cannot see the ANCHOR's own estimation error -- that is section 2.9 and "
            "it is the larger risk. Overlapping stretches are positively correlated, "
            "which widens a replicate's spread relative to independent decades and makes "
            "the pass rate if anything conservative"
        ),
        "n_decades": int(n_decades),
        "n_replicates": M3_POWER_REPLICATES,
        "seed": M3_POWER_SEED,
        "decade_scramble_guard_months": DECADE_SCRAMBLE_GUARD_MONTHS,
        "n_shifts_in_the_own_null": len(shifts),
        "p1_per_move_type": per_move,
        "p1_power_both_move_types_against_own_null": _f(float(np.mean(passes_own))),
        "p1_power_both_move_types_against_panel_wide_null": _f(float(np.mean(passes_history_null))),
        "p2_power": p2_power,
        "verdict": (
            "P1 is REACHABLE by a correct engine at this batch size"
            if float(np.mean(passes_own)) >= 0.95
            else "P1 is NOT reliably reachable by a correct engine at this batch size"
        ),
    }


def _p2_power(
    m4: dict[str, Any],
    states: dict[str, np.ndarray],
    panel: Panel,
    drawn: np.ndarray,
    n_starts: int,
    n_decades: int,
) -> dict[str, Any]:
    """The same question for P2, on the same true engine and the same draws.

    A replicate measures the three economic components' standard deviations on
    ``n_decades`` real 120-month stretches, using the M4 point estimate's own
    loadings, and holds the residual at the fitted stationary sd -- which is
    exactly how the generated side is scored, where the residual sd is a model
    parameter and only the economic components are measured on the batch. The
    replicate passes if the resulting strict share lands inside history's
    24-month interval.

    **The honest limit, and it is a large one.** The components here are
    history's own, so this measures whether a batch of fifty decades is long
    enough to place the share inside the interval -- sampling adequacy, nothing
    more. It cannot say whether a COUPLED engine would produce components of
    this size; only the fit can, and that is week 1's work.
    """
    design = _m4_design(panel, states)
    x: np.ndarray = design["x"]
    beta = [float(v) for v in m4["point_estimate"]["beta"]]
    policy = beta[1] * x[:, 1]
    inflation = beta[2] * x[:, 2]
    season = beta[3] * x[:, 3] + beta[4] * x[:, 4] + beta[5] * x[:, 5]
    residual_sd = float(m4["point_estimate"]["residual_stationary_sd_pp"])
    rows = int(x.shape[0])
    usable = rows - DECADE_MONTHS + 1
    if usable <= 0:
        raise Stage2Error("the M4 sample is shorter than one decade")
    offsets = np.arange(DECADE_MONTHS)
    ci = m4["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["rho_refitted"][
        "economic_share_ci95"
    ]
    lo, hi = float(ci["lo"] or 0.0), float(ci["hi"] or 1.0)
    shares = np.empty(drawn.shape[0], dtype=np.float64)
    for replicate in range(drawn.shape[0]):
        # the same drawn window positions, mapped into the M4 sample's own row
        # count so the two power calculations share one tape
        pick = (drawn[replicate] % usable).astype(np.int64)
        index = (pick[:, None] + offsets[None, :]).ravel()
        components = {
            "policy_rule": (float(np.std(policy[index])), True),
            "inflation_gap": (float(np.std(inflation[index])), True),
            "season_term": (float(np.std(season[index])), True),
        }
        shares[replicate] = float(
            strict_economic_share(components, residual_sd)["economic_share"] or 0.0
        )
    inside = (shares >= lo) & (shares <= hi)
    return {
        "n_decades": int(n_decades),
        "n_replicates": int(drawn.shape[0]),
        "history_interval_used": [_f(lo), _f(hi)],
        "share_mean": _f(float(shares.mean())),
        "share_ci95": _quantiles(shares),
        "power": _f(float(inside.mean())),
        "note": (
            "the residual is held at the fitted stationary sd because that is how the "
            "generated side is scored -- there the residual sd IS a model parameter and "
            "only the economic components are measured on the batch"
        ),
        "limit": (
            "these components are history's own, so this measures sampling adequacy at "
            f"{n_decades} decades and nothing else. Whether a coupled engine produces "
            "components of this size is week 1's question, not this one"
        ),
        "windows_available": int(usable),
        "seed_shared_with": "the P1 power calculation, deliberately: one tape, one set of "
        "drawn stretches, so the two pass rates are not two different resamplings",
    }


# --------------------------------------------------------------------------- #
# M5 -- both anchors under the classifier's two threshold dials
# --------------------------------------------------------------------------- #


def section_m5(
    panel: Panel,
    states: dict[str, np.ndarray],
    m4: dict[str, Any],
    phase: dict[str, Any],
) -> dict[str, Any]:
    """M5: how far do the anchors move when the two classifier dials are nudged?

    **The grid is the sealed obligation's, unchanged and imported** --
    ``spine_v2_anchors.STABILITY_ARMS``: the baseline, each dial moved 50 basis
    points each way on its own, and the four joint corners. The perturbation
    size is the platform's own ``BACKDROP_MARGIN_PP`` and is not re-argued here.

    **The verdict rule is the campaign's, unchanged:** a statistic that moves by
    more than one of its own standard errors across the arms is UNSTABLE and
    escalates. The yardstick for each statistic is its own block-bootstrap
    standard deviation at the primary block length, measured above.

    **One structural fact, checked rather than asserted.** M4's regressors are
    the rule-implied policy rate and the inflation gap, neither of which the
    classifier touches: the cycle input inside the rule is ``1 - 2*USREC``, the
    WP2.6 contract, not the classifier's growth axis. The only part of M4 either
    dial can reach is the season block, and only through the GROWTH dial. So the
    four inflation-dial-only arms must return M4's share bit-for-bit, and the
    run aborts if they do not -- which turns "the inflation dial cannot reach
    M4" from a claim into a test.
    """
    baseline_share_sd = m4["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["rho_refitted"][
        "economic_share_ci95"
    ]["sd"]
    windowed = phase["constructs"]["windowed_overlapping"]
    phase_sd = {
        move: windowed["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"][move][
            "clockwise_fraction_ci95"
        ]["sd"]
        for move in P1_MOVE_TYPES
    }
    baseline_share = float(m4["point_estimate"]["economic_share"])
    baseline_departure = {
        move: float(
            phase["within_window_null_constructs"]["windowed_overlapping"]["departure"][move] or 0.0
        )
        for move in P1_MOVE_TYPES
    }

    n = int(panel.labels.size)
    starts = _window_starts(n, "overlapping")
    arms: dict[str, Any] = {}
    for name, d_inflation, d_growth in STABILITY_ARMS:
        labels = panel.labels if d_growth == 0.0 else _relabel_growth(panel, d_growth)
        cells = relabel(panel, d_inflation, d_growth)
        design = _m4_design(panel, states, labels)
        single = np.zeros(int(design["y"].size), dtype=bool)
        single[0] = True
        fit = _m4_statistics(design["y"], design["x"], single)

        contracting = np.isin(np.asarray(labels), list(CONTRACTING_LABELS))
        expanding_bit = (~contracting).astype(np.int8)
        hot_bit = (
            np.nan_to_num(np.asarray(panel.yoy, dtype=np.float64), nan=-np.inf)
            > panel.era_threshold_pp + d_inflation
        ).astype(np.int8)
        defined = np.asarray(cells) >= 0
        offsets = np.arange(DECADE_MONTHS)
        windows = np.asarray(cells, dtype=np.int64)[starts[:, None] + offsets[None, :]][
            :, YOY_WARMUP_MONTHS:
        ]
        counts = _window_counts(windows)
        null = within_window_scramble_null(
            expanding_bit, hot_bit, defined, starts, DECADE_SCRAMBLE_GUARD_MONTHS
        )
        per_move = {}
        for move in P1_MOVE_TYPES:
            fraction = _pooled(counts, move)
            null_value = float(null["per_move_type"][move]["null_clockwise_fraction"] or 0.5)
            departure = fraction - null_value
            per_move[move] = {
                "clockwise_fraction": _f(fraction),
                "within_window_null": _f(null_value),
                "departure": _f(departure),
                "candidate_p1_threshold": _f(P1_TOLERANCE_FRACTION_OF_HISTORY * departure),
                "departure_moves_by_sd": (
                    _f((departure - baseline_departure[move]) / float(phase_sd[move]))
                    if phase_sd[move]
                    else None
                ),
            }
        arms[name] = {
            "inflation_line_delta_pp": _f(d_inflation),
            "growth_line_delta_pp": _f(d_growth),
            "m4_economic_share": _f(fit["economic_share"]),
            "m4_share_moves_by_sd": (
                _f((fit["economic_share"] - baseline_share) / float(baseline_share_sd))
                if baseline_share_sd
                else None
            ),
            "m4_rho": _f(fit["rho"]),
            "m4_beta": [_f(v) for v in fit["beta"]],
            "m4_season_component_sd_pp": fit["strict"]["component_sd_pp"]["season_term"],
            "m4_r_squared_realised": _f(fit["r_squared_realised"]),
            "p1_per_move": per_move,
        }

    # the baseline arm must reproduce the phase section's own measurement. The
    # two reach the panel by different routes -- this one through Panel, that
    # one through campaign_source -- so agreement is a real check that M5 is
    # perturbing the same classifier the anchors were measured on.
    for move in P1_MOVE_TYPES:
        here = float(arms["baseline"]["p1_per_move"][move]["clockwise_fraction"] or 0.0)
        there = float(
            phase["within_window_null_constructs"]["windowed_overlapping"][
                "measured_clockwise_fraction"
            ][move]
            or 0.0
        )
        if here != there:
            raise Stage2Error(
                f"M5's baseline arm reads {move} at {here!r} where the phase section reads "
                f"{there!r}; the two are not measuring the same classifier"
            )

    inflation_only = [name for name, d_i, d_g in STABILITY_ARMS if d_g == 0.0 and d_i != 0.0]
    worst_inflation_only = max(
        abs(float(arms[name]["m4_economic_share"] or 0.0) - baseline_share)
        for name in inflation_only
    )
    if worst_inflation_only != 0.0:
        raise Stage2Error(
            "an inflation-dial-only arm moved M4's economic share by "
            f"{worst_inflation_only:.3e}; M4's regressors do not read the era line, so "
            "either the design has acquired a dependence on it or the arm is mislabelled"
        )

    threshold_arms = [name for name, _d_i, _d_g in STABILITY_ARMS if name != "baseline"]
    share_moves = {
        name: float(arms[name]["m4_share_moves_by_sd"] or 0.0) for name in threshold_arms
    }
    worst_share = max(share_moves, key=lambda k: abs(share_moves[k]))
    per_statistic: dict[str, Any] = {
        "m4_economic_share": {
            "baseline_value": _f(baseline_share),
            "baseline_bootstrap_sd": baseline_share_sd,
            "worst_arm": worst_share,
            "worst_arm_moves_by_sd": _f(share_moves[worst_share]),
            "range_across_arms": [
                _f(min(float(arms[a]["m4_economic_share"] or 0.0) for a in arms)),
                _f(max(float(arms[a]["m4_economic_share"] or 0.0) for a in arms)),
            ],
            "escalated": bool(abs(share_moves[worst_share]) > 1.0),
        }
    }
    for move in P1_MOVE_TYPES:
        moves = {
            name: float(arms[name]["p1_per_move"][move]["departure_moves_by_sd"] or 0.0)
            for name in threshold_arms
        }
        worst = max(moves, key=lambda k: abs(moves[k]))
        per_statistic[f"p1_departure_{move}"] = {
            "baseline_value": _f(baseline_departure[move]),
            "baseline_bootstrap_sd": phase_sd[move],
            "worst_arm": worst,
            "worst_arm_moves_by_sd": _f(moves[worst]),
            "range_across_arms": [
                _f(min(float(arms[a]["p1_per_move"][move]["departure"] or 0.0) for a in arms)),
                _f(max(float(arms[a]["p1_per_move"][move]["departure"] or 0.0) for a in arms)),
            ],
            "candidate_threshold_range_across_arms": [
                _f(
                    min(
                        float(arms[a]["p1_per_move"][move]["candidate_p1_threshold"] or 0.0)
                        for a in arms
                    )
                ),
                _f(
                    max(
                        float(arms[a]["p1_per_move"][move]["candidate_p1_threshold"] or 0.0)
                        for a in arms
                    )
                ),
            ],
            "escalated": bool(abs(moves[worst]) > 1.0),
        }
    return {
        "question": (
            "M5, from the design document's section 3.3: how stable is the decomposition "
            "-- and, added here because it is anchored on the same labels, the phase "
            "departure -- under the classifier's two threshold dials"
        ),
        "grid": (
            "spine_v2_anchors.STABILITY_ARMS, imported unchanged: the baseline, each dial "
            f"moved {STABILITY_PERTURBATION_PP} pp each way on its own, and the four joint "
            "corners. A positive inflation delta raises the hot line (fewer hot months); a "
            "positive growth delta raises the contraction line (more contracting months)"
        ),
        "verdict_rule": (
            "the campaign's, unchanged: a statistic that moves by more than one of its own "
            "standard errors across the arms is UNSTABLE and escalates. The yardstick is "
            "each statistic's own block-bootstrap sd at the primary block length"
        ),
        "dependency_on_m3": (
            "none for the M4 half: M5 anchors P2 and M3 gates P1, so the two are "
            "independent. The P1 half of this section is only meaningful if M3 keeps P1 -- "
            "which it does -- and would be moot, not wrong, if it had not"
        ),
        "inflation_dial_cannot_reach_m4": {
            "checked": True,
            "worst_absolute_move_on_inflation_only_arms": _f(worst_inflation_only),
            "why": (
                "M4's regressors are the rule-implied policy rate and the inflation gap. "
                "The cycle input inside the rule is 1 - 2*USREC, the WP2.6 contract, not "
                "the classifier's growth axis, and the era line appears nowhere in the "
                "equation. So only the GROWTH dial can reach M4, and only through the "
                "season block -- the smallest of its three economic components"
            ),
        },
        "arms": arms,
        "per_statistic": per_statistic,
        "any_escalated": bool(any(row["escalated"] for row in per_statistic.values())),
    }


# --------------------------------------------------------------------------- #
# the GENERATED side's own phase-scrambled null
# --------------------------------------------------------------------------- #


def _rebuild_engines(panel: Panel, cells: np.ndarray) -> tuple[Any, dict[str, Any], Any]:
    """Week 3's four curve models and the fitted engine behind them.

    Every line is ``spine_v2_feedback.main``'s, in its order, so the objects
    below are the committed engines rather than approximations of them. The
    check that this worked is not an argument: each batch's transition counts
    are compared with the counts week 3 committed, and the run aborts on a
    mismatch.
    """
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
    return engine, curves, joint


def section_generated_null(
    panel: Panel,
    cells: np.ndarray,
    phase: dict[str, Any],
    feedback_params: dict[str, Any],
    v2_prereg: dict[str, Any],
) -> dict[str, Any]:
    """Stop-question 5, closed: the generated side's OWN phase-scrambled null.

    ``P1``'s null is defined as *the batch's own* scramble. Everything on the
    record so far has substituted history's, on the argument that every
    per-move null sits within 0.001 of 0.500. This section stops arguing and
    measures it, by re-simulating the recorded batches -- they reproduce bit for
    bit, which is checked here against week 3's committed transition counts --
    and scrambling each decade's inflation dial against its own growth axis.

    **Two constructs, because the engine emits one object and the judge scores
    another.** The ``judged`` construct is the sealed judge's: each decade's
    first twelve months censored. The ``internal`` construct is the simulator's
    own season index over all 120 months, which is what week 3's
    ``o1_decomposition`` scored and therefore what every by-move-type number on
    the record was measured on. Both are reported; the judged one is the one a
    stage-2 seal would use, because it is the object the pipeline ships.
    """
    engine, curves, _joint = _rebuild_engines(panel, cells)
    sealed = load_sealed()
    n_decades = int(sealed["bars"].get("n_seeds", DEFAULT_N_DECADES))
    climate, _regimes = _pinned_layers()
    premise = _load_premise()
    recorded_engines = feedback_params["verification"]["engines"]

    history = phase["within_window_null_constructs"]["windowed_overlapping"]
    history_panel_wide = phase["constructs"]["windowed_overlapping"]["scrambled_null"][
        "per_move_type"
    ]

    rows: dict[str, Any] = {}
    for name in ENGINE_NAMES:
        arms = [("unconditional", None)]
        if name == PRIMARY_ENGINE:
            arms.append(("premise_accepted", premise))
        for arm, arm_premise in arms:
            decades, _tally = simulate_batch_feedback(
                engine,
                curves[name],
                climate,
                n_decades=n_decades,
                seed=VERIFY_SEED,
                premise=arm_premise,
            )
            season = np.stack([np.asarray(d.season, dtype=np.int64) for d in decades])
            hot = np.stack(
                [
                    (np.asarray(d.yoy, dtype=np.float64) > engine.era_threshold_pp).astype(np.int64)
                    for d in decades
                ]
            )
            expanding = np.stack([np.asarray(d.expanding).astype(np.int64) for d in decades])
            if not np.array_equal(season, (expanding << 1) | hot):
                raise Stage2Error(
                    f"{name}/{arm}: the season index is not (expanding << 1) | hot, so the "
                    "scramble would not be scrambling the classifier's own inputs"
                )

            recorded = recorded_engines[name][arm]
            internal_counts = _window_counts(season)
            committed = recorded["o1_decomposition"]["generated_batch"]
            if int(internal_counts["overall"][0].sum()) != int(committed["transitions"]) or int(
                internal_counts["overall"][1].sum()
            ) != int(committed["clockwise"]):
                raise Stage2Error(
                    f"{name}/{arm}: the re-simulated batch does not reproduce week 3's "
                    f"committed counts ({committed['clockwise']}/{committed['transitions']})"
                )
            judged_counts = _window_counts(season[:, YOY_WARMUP_MONTHS:])
            sealed_o1 = float(recorded["verdicts_full"]["O1"]["value"])
            if abs(_pooled(judged_counts, "overall") - sealed_o1) > 5e-12:
                raise Stage2Error(
                    f"{name}/{arm}: the censored batch reads "
                    f"{_pooled(judged_counts, 'overall')!r} where the sealed judge recorded "
                    f"{sealed_o1!r}"
                )

            flat_hot = hot.ravel()
            flat_expanding = expanding.ravel()
            flat_defined = np.ones(flat_hot.size, dtype=bool)
            starts = np.arange(len(decades), dtype=np.int64) * DECADE_MONTHS
            per_construct: dict[str, Any] = {}
            for construct, counts, censor in (
                ("judged_censored", judged_counts, True),
                ("internal_uncensored", internal_counts, False),
            ):
                null = within_window_scramble_null(
                    flat_expanding,
                    flat_hot,
                    flat_defined,
                    starts,
                    DECADE_SCRAMBLE_GUARD_MONTHS,
                    censor=censor,
                )
                sensitivity = {
                    f"guard_{guard}m": within_window_scramble_null(
                        flat_expanding, flat_hot, flat_defined, starts, guard, censor=censor
                    )["per_move_type"]["overall"]["null_clockwise_fraction"]
                    for guard in DECADE_SCRAMBLE_GUARD_SENSITIVITY_MONTHS
                }
                per_move: dict[str, Any] = {}
                for move in P1_MOVE_TYPES:
                    fraction = _pooled(counts, move)
                    own = float(null["per_move_type"][move]["null_clockwise_fraction"] or 0.5)
                    substituted = float(history_panel_wide[move]["null_clockwise_fraction"] or 0.5)
                    threshold = float(history["candidate_p1_threshold"][move] or 0.0)
                    per_move[move] = {
                        "generated_clockwise_fraction": _f(fraction),
                        "own_null": _f(own),
                        "substituted_history_panel_wide_null": _f(substituted),
                        "null_substitution_error": _f(own - substituted),
                        "departure_against_own_null": _f(fraction - own),
                        "departure_against_substituted_null": _f(fraction - substituted),
                        "candidate_threshold": _f(threshold),
                        "passes_against_own_null": bool((fraction - own) >= threshold),
                    }
                per_construct[construct] = {
                    "overall_clockwise_fraction": _f(_pooled(counts, "overall")),
                    "overall_own_null": null["per_move_type"]["overall"]["null_clockwise_fraction"],
                    "overall_own_null_guard_sensitivity": sensitivity,
                    "n_shifts": null["n_shifts"],
                    "per_move": per_move,
                }
            rows[f"{name}__{arm}"] = {
                "n_decades": len(decades),
                "reproduces_committed_counts": True,
                "reproduces_sealed_o1_value": True,
                "constructs": per_construct,
            }

    judged_overall = {
        key: row["constructs"]["judged_censored"]["overall_own_null"] for key, row in rows.items()
    }
    substitution_errors = [
        abs(float(row["constructs"][c]["per_move"][move]["null_substitution_error"] or 0.0))
        for row in rows.values()
        for c in row["constructs"]
        for move in P1_MOVE_TYPES
    ]
    any_passes = any(
        row["constructs"]["judged_censored"]["per_move"][move]["passes_against_own_null"]
        for row in rows.values()
        for move in P1_MOVE_TYPES
    )
    return {
        "question": (
            "stop-question 5: P1's null is the BATCH's own phase scramble, and every "
            "number on the record substituted history's. Is the substitution sound?"
        ),
        "method": (
            "each recorded batch is re-simulated from the committed engine (bit for bit, "
            "checked against week 3's transition counts and against the sealed O1 value), "
            "and its inflation dial is circularly shifted against its growth axis INSIDE "
            "each decade -- the only scramble a batch of independent decades admits. "
            "Every admissible shift is enumerated, so this needs no seed"
        ),
        "guard_months": DECADE_SCRAMBLE_GUARD_MONTHS,
        "why_the_guard_is_smaller_than_history_s": (
            "history's panel-wide guard is 60 months on 813; inside a 120-month decade "
            "min(k, 120-k) >= 60 admits exactly ONE shift, so the guard must come down. "
            "24 months is more than twice the ten-month lag M3 measures for this channel "
            "and still leaves 73 of the 119 shifts"
        ),
        "seed": VERIFY_SEED,
        "seed_note": "week 3's verification seed, re-used deliberately: a different seed "
        "would be a different batch and would not be the recorded engine's null",
        "sealed_at_utc": v2_prereg["sealed_at_utc"],
        "per_engine_arm": rows,
        "judged_overall_null_by_engine": judged_overall,
        "history_overall_null_panel_wide": phase["constructs"]["windowed_overlapping"][
            "scrambled_null"
        ]["per_move_type"]["overall"]["null_clockwise_fraction"],
        "history_overall_null_within_window": history["within_window_null"]["per_move_type"][
            "overall"
        ]["null_clockwise_fraction"],
        "worst_null_substitution_error": _f(max(substitution_errors)),
        "any_recorded_engine_passes_p1_against_its_own_null": bool(any_passes),
        "reading": (
            "the substitution is sound per MOVE TYPE -- every generated null sits close to "
            "a coin flip, as the structural argument says it must -- and the retro "
            "anti-test survives it: no recorded engine clears a candidate threshold when "
            "it is judged against its own null. What the substitution does NOT survive is "
            "the OVERALL statistic, where diagonals pull every null below 0.500, and it is "
            "not the same number on the two sides"
        ),
    }


# --------------------------------------------------------------------------- #
# how many draws should a sealed floor be cut from?
# --------------------------------------------------------------------------- #


def _floor_on_tape(
    cells: np.ndarray, weights: np.ndarray, seed: int, draws: int, block: int
) -> float:
    """One O1-class floor: the 2.5th percentile of the pooled clockwise fraction.

    The scoring is :func:`bootstrap_fractions`'s, unchanged in substance -- only
    genuine consecutive pairs of the real panel count, and the window weight
    attaches to the pair's position in the drawn pseudo-panel -- but the draws
    are taken in chunks, because a quarter-million-draw index over 813 months
    does not fit anywhere sensible. Chunking changes the tape; the chunk size is
    a declared constant and every tape in this study uses the same one, so the
    tapes are comparable with each other, which is the only property the study
    needs.
    """
    arr = np.asarray(cells, dtype=np.int64)
    n = int(arr.size)
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    fractions = np.empty(int(draws), dtype=np.float64)
    done = 0
    while done < int(draws):
        size = min(NOISE_CHUNK_DRAWS, int(draws) - done)
        index = _stationary_bootstrap_indices(rng, n, block, size)
        prev_idx, next_idx = index[:, :-1], index[:, 1:]
        genuine = next_idx == (prev_idx + 1)
        prev_cells = np.where(genuine, arr[prev_idx], -1)
        next_cells = np.where(genuine, arr[next_idx], -1)
        valid = (prev_cells >= 0) & (next_cells >= 0) & (prev_cells != next_cells)
        clockwise = (
            valid
            & _CLOCKWISE_MATRIX[np.where(valid, prev_cells, 0), np.where(valid, next_cells, 0)]
        )
        totals = (valid * weights).sum(axis=1)
        clock = (clockwise * weights).sum(axis=1)
        fractions[done : done + size] = np.where(
            totals > 0.0, clock / np.maximum(totals, 1e-12), np.nan
        )
        done += size
    finite = fractions[np.isfinite(fractions)]
    return float(np.percentile(finite, CI_PERCENTILES[0]))


def _tape_seeds(count: int) -> list[int]:
    """Independent tape seeds: one base, one prime stride, no reuse.

    The stride is deliberately NOT the platform's 7919. That stride is spoken
    for on the ensemble axis, and re-using a stride on a new axis is how twenty
    spines once collapsed to two.
    """
    return [NOISE_TAPE_SEED_BASE + NOISE_TAPE_STRIDE * k for k in range(int(count))]


def section_floor_noise(cells: np.ndarray, phase: dict[str, Any]) -> dict[str, Any]:
    """Stop-question 2, answered with a number: how many draws does a floor need?

    **The margins the floor has to resolve, taken from this run's own
    reconciliation rather than restated.** Every cell of the O1 table is an
    engine reading placed beside a floor; the distance between them is what the
    floor must get right. If the tape noise is the size of that distance, the
    verdict is being decided by the random draw.

    **The pre-declared rule, and why the fraction is one fifth.** Tape noise --
    the standard deviation of the floor across independent bootstrap tapes -- must
    be at most one fifth of the smallest margin the floor has to resolve. One
    fifth means a two-standard-deviation excursion is still under half the
    margin, so no recorded verdict can flip on the draw; one half would leave a
    routine excursion able to flip one, and one tenth would quadruple the cost
    for a resolution nothing uses.

    **Why the count is measured on a ladder instead of extrapolated, which is
    the interesting part.** The textbook answer is that a bootstrap
    percentile's Monte Carlo standard deviation falls as one over the square
    root of the draw count, so one measurement and one multiplication give the
    requirement. That was tried first and it is wrong here, for a reason worth
    recording: **the floor is a ratio of small integers.** Each draw's clockwise
    fraction is a count over about seventy transitions, so the statistic lives
    on a lattice, and its 2.5th percentile does not drift smoothly toward a
    limit -- it collapses onto one lattice point. Noise therefore falls faster
    than any power law once a single lattice point owns the tail, and a law
    fitted at the cheap end mis-states the requirement in both directions
    depending where it is fitted. So the ladder is climbed and the answer is the
    smallest rung whose MEASURED noise meets the rule. The fitted law is still
    published, beside the rungs, as the thing that does not work.
    """
    n = int(np.asarray(cells).size)
    constructs = {
        "uncensored_both_sides": np.ones(n - 1, dtype=np.float64),
        "windowed_overlapping": overlapping_window_weights(n),
    }

    margins: dict[str, float] = {}
    for key, row in sorted(phase["engines_on_the_record"]["per_engine_arm"].items()):
        for construct, cell in sorted(row["o1_under_each_history_construct"].items()):
            value, floor = cell["generated_value"], cell["history_floor"]
            if value is None or floor is None:
                continue
            margins[f"{key}__{construct}"] = abs(float(value) - float(floor))
        margins[f"{key}__sealed"] = abs(
            float(row["sealed_o1_value"]) - float(row["sealed_o1_threshold"])
        )
    smallest_key = min(margins, key=lambda k: margins[k])
    smallest = margins[smallest_key]
    target = NOISE_MARGIN_FRACTION * smallest

    def _tape_noise(name: str, draws: int) -> dict[str, Any]:
        floors = np.array(
            [
                _floor_on_tape(cells, constructs[name], seed, draws, PRIMARY_BLOCK_MONTHS)
                for seed in _tape_seeds(NOISE_TAPE_COUNT)
            ]
        )
        sd = float(floors.std(ddof=1))
        # a standard deviation from T tapes is itself an estimate: log s is
        # approximately normal with standard deviation 1/sqrt(2(T-1)), which is
        # where this interval comes from. Reported everywhere the sd is,
        # because a check whose own resolution is hidden is not a check
        spread = math.exp(1.96 / math.sqrt(2.0 * (floors.size - 1)))
        distinct = np.unique(floors)
        return {
            "draws": int(draws),
            "n_tapes": int(floors.size),
            "tape_noise_sd": _f(sd),
            "tape_noise_sd_ci95": [_f(sd / spread), _f(sd * spread)],
            "tape_range": _f(float(floors.max() - floors.min())),
            "mean_floor": _f(float(floors.mean())),
            "distinct_floor_values": [_f(v) for v in distinct],
            "modal_share_of_tapes": _f(
                float(np.max(np.bincount(np.searchsorted(distinct, floors))) / floors.size)
            ),
            "meets_the_rule": bool(sd <= target),
        }

    ladder: dict[str, Any] = {}
    for name in constructs:
        rungs = {f"draws_{draws}": _tape_noise(name, draws) for draws in NOISE_BOTH_CONSTRUCT_RUNGS}
        ladder[name] = rungs
    cheap = NOISE_BOTH_CONSTRUCT_RUNGS[0]
    for name, rungs in ladder.items():
        if (
            int(rungs[f"draws_{cheap}"]["n_tapes"])
            > len(rungs[f"draws_{cheap}"]["distinct_floor_values"]) * 2
        ):
            raise Stage2Error(
                f"{name}: at {cheap} draws the tapes return too few distinct floors to be "
                "independent tapes of a continuous-enough statistic"
            )
    top = NOISE_BOTH_CONSTRUCT_RUNGS[-1]
    binding = max(ladder, key=lambda k: float(ladder[k][f"draws_{top}"]["tape_noise_sd"] or 0.0))
    for draws in NOISE_DRAW_LADDER:
        key = f"draws_{draws}"
        if key in ladder[binding]:
            continue
        ladder[binding][key] = _tape_noise(binding, draws)
        if ladder[binding][key]["meets_the_rule"]:
            break

    # If quadrupling has bracketed the target without meeting it, refine: take
    # the next rung at the count the law fitted on the rungs so far implies,
    # floored at a real step up and rounded to a quotable number.
    refinements: list[int] = []
    for _ in range(NOISE_MAX_REFINEMENTS):
        rows = sorted(ladder[binding].values(), key=lambda r: int(r["draws"]))
        if rows[-1]["meets_the_rule"]:
            break
        counts = np.array([float(r["draws"]) for r in rows])
        sds = np.array([float(r["tape_noise_sd"] or np.nan) for r in rows])
        usable = np.isfinite(sds) & (sds > 0.0)
        slope, _intercept = np.polyfit(np.log(counts[usable]), np.log(sds[usable]), 1)
        last_draws = float(counts[-1])
        last_sd = float(sds[-1])
        implied = last_draws * (last_sd / target) ** (-1.0 / float(slope))
        step = max(implied, last_draws * NOISE_REFINEMENT_MIN_GROWTH)
        nxt = int(math.ceil(step / NOISE_REFINEMENT_ROUNDING) * NOISE_REFINEMENT_ROUNDING)
        refinements.append(nxt)
        ladder[binding][f"draws_{nxt}"] = _tape_noise(binding, nxt)

    met = [int(row["draws"]) for row in ladder[binding].values() if row["meets_the_rule"]]
    required_draws = min(met) if met else None
    verified = ladder[binding][f"draws_{required_draws}"] if required_draws is not None else None
    largest_missing = max(
        (int(row["draws"]) for row in ladder[binding].values() if not row["meets_the_rule"]),
        default=None,
    )

    # the fitted power law, published as the thing that does NOT settle this
    fitted = {}
    for name, rungs in ladder.items():
        counts = np.array([float(row["draws"]) for row in rungs.values()])
        sds = np.array([float(row["tape_noise_sd"] or np.nan) for row in rungs.values()])
        usable = np.isfinite(sds) & (sds > 0.0)
        if int(usable.sum()) < 2:
            continue
        slope, intercept = np.polyfit(np.log(counts[usable]), np.log(sds[usable]), 1)
        fitted[name] = {
            "fitted_log_log_slope": _f(float(slope)),
            "slope_expected_by_theory": -0.5,
            "required_draws_by_the_fitted_law": int(
                math.ceil(float(np.exp((math.log(target) - intercept) / slope)) / NOISE_CHUNK_DRAWS)
                * NOISE_CHUNK_DRAWS
            ),
            "required_draws_by_the_square_root_law": int(
                math.ceil(
                    float(counts[usable][-1] * (sds[usable][-1] / target) ** 2) / NOISE_CHUNK_DRAWS
                )
                * NOISE_CHUNK_DRAWS
            ),
        }
    return {
        "question": (
            "stop-question 2: how many bootstrap draws should a sealed floor be cut from? "
            "At 2000 draws two honest tapes of the identical statistic differ in the third "
            "decimal, and the margins the floor decides are the same size"
        ),
        "rule": (
            "PRE-DECLARED: the tape noise -- the standard deviation of the floor across "
            "independent bootstrap tapes -- must be at most one fifth of the smallest "
            "margin the floor has to resolve. At one fifth a two-sd excursion is still "
            "under half the margin, so no recorded verdict can flip on the draw"
        ),
        "margins_measured_in_this_run": {k: _f(v) for k, v in sorted(margins.items())},
        "smallest_margin": _f(smallest),
        "smallest_margin_cell": smallest_key,
        "required_tape_noise": _f(target),
        "noise_margin_fraction": NOISE_MARGIN_FRACTION,
        "tape_seed_base": NOISE_TAPE_SEED_BASE,
        "tape_seed_stride": NOISE_TAPE_STRIDE,
        "tapes_per_draw_count": NOISE_TAPE_COUNT,
        "block_months": PRIMARY_BLOCK_MONTHS,
        "ladder": ladder,
        "ladder_rule": (
            "quadruple the draw count until the measured noise meets the rule; if the top "
            "rung still misses, refine at the count the law fitted on the rungs so far "
            "implies, floored at 1.25x the last rung and rounded up to a multiple of "
            f"{NOISE_REFINEMENT_ROUNDING}. The answer is the smallest rung that MEETS the "
            "rule, measured on its own tapes"
        ),
        "refinement_rungs_taken": refinements,
        "binding_construct": binding,
        "binding_construct_note": (
            "the WINDOWED floor is the noisier of the two and therefore sets the "
            "requirement. That is not an accident: it is a weighted fraction over re-used "
            "months, so it takes near-continuous values, while the unweighted floor is a "
            "ratio of small counts"
        ),
        "required_draws": required_draws,
        "largest_draw_count_that_still_missed": largest_missing,
        "verification": verified,
        "extrapolation_that_does_not_settle_it": fitted,
        "why_the_count_is_measured_and_not_extrapolated": (
            "the two floors behave differently and only one of them obeys a power law. The "
            "UNWEIGHTED floor -- the sealed O1 statistic -- is a count over about seventy "
            "transitions, so it lives on a lattice of ratios of small integers: "
            "distinct_floor_values shows twelve tapes collapsing onto six values by 32,000 "
            "draws, and its noise then falls faster than any power of the draw count "
            "because one lattice point takes the whole tail. The WINDOWED floor is a "
            "weighted fraction over re-used months, is effectively continuous, and does "
            "follow a power law -- with a fitted exponent near -0.56 rather than the "
            "textbook -0.50. Neither behaviour is safe to extrapolate two orders of "
            "magnitude, so the count is measured"
        ),
        "what_this_costs": (
            "a clockwise-fraction floor is cheap -- the draws are index arithmetic and "
            "nothing is refitted. A floor cut from a FITTED statistic is not: M4's share "
            "refits an AR(1) profile on every draw, which is about two hundred times the "
            "work per draw, so the same rule applied to M4's interval would be hours "
            "rather than minutes. The rule is stated for O1-class floors and the cost of "
            "extending it elsewhere should be priced before it is promised"
        ),
        "reading": (
            "this is a resolution requirement, not a claim that a floor cut from 2000 "
            "draws is wrong. It says what draw count makes a floor reproducible to better "
            "than a fifth of the smallest distance it has to measure, so that a "
            "re-derivation on another tape cannot move a verdict"
        ),
    }


# --------------------------------------------------------------------------- #
# input integrity
# --------------------------------------------------------------------------- #


def _check_sealed_inputs(v2_prereg: dict[str, Any], v2_anchors: dict[str, Any]) -> dict[str, Any]:
    """Prove this module's windowing constants ARE the sealed judge's.

    ``DECADE_MONTHS`` and ``YOY_WARMUP_MONTHS`` are the whole content of the
    symmetric construct. Carrying them as literals that nobody checks is how a
    re-derivation quietly stops re-deriving the thing it names.
    """
    sealed_decade = int(v2_anchors["judge_parameters"]["decade_months"])
    sealed_warmup = int(v2_anchors["k_pooled_decade_dwells"]["warmup_months"])
    if (sealed_decade, sealed_warmup) != (DECADE_MONTHS, YOY_WARMUP_MONTHS):
        raise Stage2Error(
            f"the sealed judge windows {sealed_decade} months with a {sealed_warmup}-month "
            f"warm-up; this module carries {DECADE_MONTHS}/{YOY_WARMUP_MONTHS}"
        )
    return {
        "decade_months_matches_sealed": True,
        "warmup_months_matches_sealed": True,
        "sealed_at_utc": v2_prereg["sealed_at_utc"],
        "input_sha256": {
            "docs/superpowers/specs/spine-v2-prereg.json": _sha256(V2_PREREG_PATH),
            "docs/superpowers/specs/spine-v2-anchors.json": _sha256(V2_ANCHORS_PATH),
            "docs/superpowers/specs/spine-v2-feedback-params.json": _sha256(FEEDBACK_PARAMS_PATH),
        },
        "note": (
            "all three inputs are opened read-only. The first two are inside the v2 "
            "seal's hash list; running this module cannot change them, and their hashes "
            "are recorded so a later reader can prove which versions were measured"
        ),
    }


def _check_window_weight_identity(cells: np.ndarray) -> dict[str, Any]:
    """The weighted shortcut must equal a literal window-by-window count.

    :func:`overlapping_window_weights` replaces a loop over 694 windows with a
    closed-form weight. If the two ever disagree the whole symmetric construct
    is measuring something nobody can reproduce, so the loop is run once, here,
    and compared.
    """
    arr = np.asarray(cells, dtype=np.int64)
    n = int(arr.size)
    total = 0
    clockwise = 0
    for start in range(0, n - DECADE_MONTHS + 1):
        window = arr[start + YOY_WARMUP_MONTHS : start + DECADE_MONTHS]
        prev, nxt = window[:-1], window[1:]
        valid = (prev >= 0) & (nxt >= 0) & (prev != nxt)
        total += int(valid.sum())
        clockwise += int(
            (valid & _CLOCKWISE_MATRIX[np.where(valid, prev, 0), np.where(valid, nxt, 0)]).sum()
        )
    scored = score_transitions(arr, overlapping_window_weights(n))["overall"]
    ok = (
        float(total) == scored["weighted_transitions"]
        and float(clockwise) == scored["weighted_clockwise"]
    )
    if not ok:
        raise Stage2Error(
            "the overlapping-window weights do not reproduce a literal window-by-window "
            f"count ({clockwise}/{total} vs {scored['weighted_clockwise']}/"
            f"{scored['weighted_transitions']})"
        )
    return {
        "literal_window_transitions": total,
        "literal_window_clockwise": clockwise,
        "weighted_shortcut_matches": bool(ok),
        "n_windows": n - DECADE_MONTHS + 1,
    }


# --------------------------------------------------------------------------- #


def main() -> None:
    v2_prereg = json.loads(V2_PREREG_PATH.read_text(encoding="utf-8"))
    v2_anchors = json.loads(V2_ANCHORS_PATH.read_text(encoding="utf-8"))
    feedback_params = json.loads(FEEDBACK_PARAMS_PATH.read_text(encoding="utf-8"))
    integrity = _check_sealed_inputs(v2_prereg, v2_anchors)

    panel = build_panel()
    states = rule_implied_states(panel)
    recorded = recorded_engine_shares(feedback_params)
    m4 = section_m4(panel, states, recorded)

    source = campaign_source()
    yoy = panel_yoy(source)
    era_threshold_pp = float(fit_hazard(source).era_threshold_pp)
    labels = np.asarray(source.labels)
    cells = season_cells(labels, yoy, era_threshold_pp)
    weight_check = _check_window_weight_identity(cells)
    phase = section_phase(cells, labels, yoy, era_threshold_pp, v2_anchors)
    phase["overlapping_weight_identity_check"] = weight_check
    phase["engines_on_the_record"] = engines_on_the_record(phase, feedback_params)
    recommendation = recommended_construct(phase, v2_anchors)

    m3 = section_m3(panel, states, yoy, cells)
    n_decades = int(load_sealed()["bars"].get("n_seeds", DEFAULT_N_DECADES))
    m3_power = section_m3_power(
        cells, labels, yoy, era_threshold_pp, phase, m4, states, panel, n_decades
    )
    m5 = section_m5(panel, states, m4, phase)
    generated_null = section_generated_null(panel, cells, phase, feedback_params, v2_prereg)
    floor_noise = section_floor_noise(cells, phase)

    payload = {
        "schema": "stage2-anchors-0.2",
        "purpose": (
            "the stage-2 pre-seal measurements, each capable of killing the bar it "
            "anchors: M4 (history's curve decomposition on the rule-implied policy rate, "
            "P2's anchor and its pre-declared drop rule), the windowing-symmetric phase "
            "re-derivation (P1's anchor, demanded by the verdict-integrity review's C1), "
            "M3 (the growth -> inflation coupling as a GATE on P1, plus the power "
            "calculation at 50 decades), M5 (both anchors under the classifier's two "
            "threshold dials), the generated side's own phase-scrambled null, and the "
            "draw count a sealed floor needs. NOT a seal: no threshold here is binding "
            "until it is entered through the amendment log with its judge code hashed in"
        ),
        "status": "MEASURED, NOT SEALED",
        "produced_by": "scripts/stage2_anchors.py",
        "decision": "D-SP-9 (stage 2 funded, owner ruling 2026-08-17)",
        "campaign_vintage_id": CAMPAIGN_VINTAGE_ID,
        "sealed_input_integrity": integrity,
        "m4_curve_endogeneity": m4,
        "p1_phase_anchor": phase,
        "recommended_construct": recommendation,
        "m3_growth_to_inflation_coupling": m3,
        "m3_power_at_the_sealed_batch_size": m3_power,
        "m5_label_dial_stability": m5,
        "generated_side_scrambled_null": generated_null,
        "floor_noise_and_the_draw_count": floor_noise,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(_round(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT_PATH}")

    point = m4["point_estimate"]
    primary_ci = m4["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["rho_refitted"][
        "economic_share_ci95"
    ]
    print(
        f"M4 history economic share {point['economic_share']:.4f}  "
        f"ci95 [{primary_ci['lo']:.4f}, {primary_ci['hi']:.4f}]  "
        f"(rho {point['rho']:.4f}, R^2 {point['r_squared_realised']:.4f})"
    )
    for name, share in sorted(m4["p2_acceptance"]["engine_strict_economic_shares"].items()):
        print(f"M4 recorded engine {name:26s} strict economic share {share:.4f}")
    print(
        f"M4 P2 VERDICT: {m4['p2_acceptance']['verdict']}  "
        f"(robust to the summary: {m4['p2_acceptance']['verdict_robust_to_the_summary']})"
    )
    for name, construct in sorted(phase["constructs"].items()):
        row = construct["departures_and_candidate_thresholds"]
        print(
            f"P1 {name:24s} growth {row['growth_flip']['measured_clockwise_fraction']:.4f} "
            f"(null {row['growth_flip']['scrambled_null']:.4f}, "
            f"threshold {row['growth_flip']['candidate_p1_threshold']:.4f})  "
            f"inflation {row['inflation_crossing']['measured_clockwise_fraction']:.4f} "
            f"(null {row['inflation_crossing']['scrambled_null']:.4f}, "
            f"threshold {row['inflation_crossing']['candidate_p1_threshold']:.4f})"
        )
    print(f"P1 recommended construct: {recommendation['recommendation']}")
    anti = phase["engines_on_the_record"]["p1_anti_test_3"]
    print(f"P1 anti-test 3 (every recorded engine must fail): holds = {anti['holds']}")
    for name, row in sorted(phase["engines_on_the_record"]["per_engine_arm"].items()):
        floors = row["o1_under_each_history_construct"]
        print(
            f"O1 {name:34s} sealed {row['sealed_o1_value']:.6f}  "
            f"symmetric-windowed floor {floors['windowed_overlapping']['history_floor']:.6f} "
            f"clears={floors['windowed_overlapping']['clears']}  |  "
            f"uncensored {row['internal_path_o1_value']:.6f} vs floor "
            f"{floors['uncensored_both_sides']['history_floor']:.6f} "
            f"clears={floors['uncensored_both_sides']['clears']}"
        )

    gate = m3["gate"]
    point = m3["point_estimate"]
    print(
        f"M3 coupling lam_x {point['lam_x']:+.6f} at lag {m3['selected_lag_months']}m  "
        f"t {point['t_ratio']:+.3f}  LR {point['lr_statistic']:.3f}  "
        f"selection-aware p {m3['selection_aware_null']['p_value_selection_aware']:.4f}"
    )
    for block, row in sorted(m3["block_bootstrap"].items()):
        held = row["lam_x_ci95_lag_held"]
        print(
            f"M3 {block:10s} lam_x ci95 [{held['lo']:+.6f}, {held['hi']:+.6f}] "
            f"excludes zero: held={row['excludes_zero_lag_held']} "
            f"reselected={row['excludes_zero_lag_reselected']}"
        )
    print(f"M3 GATE VERDICT: {gate['verdict']}")
    print(
        "M3 power at "
        f"{m3_power['n_decades']} decades: P1 both move types "
        f"{m3_power['p1_power_both_move_types_against_own_null']:.3f} (own null), "
        f"P2 {m3_power['p2_power']['power']:.3f}"
    )
    print(
        "M5 any statistic escalated: "
        f"{m5['any_escalated']}  worst M4 share move "
        f"{m5['per_statistic']['m4_economic_share']['worst_arm_moves_by_sd']:+.3f} sd"
    )
    for name, row in sorted(m5["per_statistic"].items()):
        print(
            f"M5 {name:32s} worst {row['worst_arm']:28s} "
            f"{row['worst_arm_moves_by_sd']:+.3f} sd  escalated={row['escalated']}"
        )
    within = phase["within_window_null_constructs"]["windowed_overlapping"]
    print(
        "P1 within-window null (windowed, overlapping): growth "
        f"{within['within_window_null']['per_move_type']['growth_flip']['null_clockwise_fraction']:.6f}"
        f" -> threshold {within['candidate_p1_threshold']['growth_flip']:.6f}  inflation "
        f"{within['within_window_null']['per_move_type']['inflation_crossing']['null_clockwise_fraction']:.6f}"
        f" -> threshold {within['candidate_p1_threshold']['inflation_crossing']:.6f}"
    )
    for name, row in sorted(generated_null["per_engine_arm"].items()):
        judged = row["constructs"]["judged_censored"]
        print(
            f"NULL {name:34s} engine overall null {judged['overall_own_null']:.6f} "
            f"vs history {generated_null['history_overall_null_panel_wide']:.6f}"
        )
    print(
        "NULL worst per-move substitution error "
        f"{generated_null['worst_null_substitution_error']:.6f}; any engine passes P1 on "
        f"its own null: {generated_null['any_recorded_engine_passes_p1_against_its_own_null']}"
    )
    print(
        f"FLOOR smallest margin {floor_noise['smallest_margin']:.6f} "
        f"({floor_noise['smallest_margin_cell']}) -> required noise "
        f"{floor_noise['required_tape_noise']:.6f}"
    )
    for name, rungs in sorted(floor_noise["ladder"].items()):
        for key, row in sorted(rungs.items(), key=lambda kv: kv[1]["draws"]):
            print(
                f"FLOOR {name:22s} {key:14s} sd {row['tape_noise_sd']:.6f} "
                f"range {row['tape_range']:.6f} distinct "
                f"{len(row['distinct_floor_values']):2d} modal "
                f"{row['modal_share_of_tapes']:.2f} meets={row['meets_the_rule']}"
            )
    print(
        f"FLOOR binding construct {floor_noise['binding_construct']}; REQUIRED DRAWS "
        f"{floor_noise['required_draws']} (measured; largest count that still missed: "
        f"{floor_noise['largest_draw_count_that_still_missed']}); refinements "
        f"{floor_noise['refinement_rungs_taken']}"
    )


if __name__ == "__main__":
    main()
