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
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_anchors import _stationary_bootstrap_indices  # noqa: E402
from spine_v2_feedback import (  # noqa: E402
    _profile_at_rho,
    curve_design,
    first_spell_end,
    growth_axis,
    spell_age,
)
from spine_v2_fit import Panel, _round, build_panel  # noqa: E402
from spine_v2_grader import CONTRACTING_LABELS, season_cells  # noqa: E402

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
        return {"lo": None, "hi": None, "median": None}
    lo, hi = np.percentile(finite, CI_PERCENTILES)
    return {"lo": _f(lo), "hi": _f(hi), "median": _f(np.median(finite))}


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


def _m4_design(panel: Panel, states: dict[str, np.ndarray]) -> dict[str, Any]:
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
    expanding = growth_axis(panel.labels)
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

    return {
        "question": (
            "history's clockwise fraction by move type -- P1's anchor -- re-derived under "
            "windowing treatments applied SYMMETRICALLY to both sides, as the "
            "verdict-integrity review's finding C1 requires before P1's threshold is cut"
        ),
        "sealed_tape_provenance_check": tape_check,
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

    payload = {
        "schema": "stage2-anchors-0.1",
        "purpose": (
            "the two stage-2 pre-seal measurements that can kill the bars they anchor: "
            "M4 (history's curve decomposition on the rule-implied policy rate, P2's "
            "anchor and its pre-declared drop rule) and the windowing-symmetric phase "
            "re-derivation (P1's anchor, demanded by the verdict-integrity review's C1). "
            "NOT a seal: no threshold here is binding until it is entered through the "
            "amendment log with its judge code hashed in"
        ),
        "status": "MEASURED, NOT SEALED",
        "produced_by": "scripts/stage2_anchors.py",
        "decision": "D-SP-9 (stage 2 funded, owner ruling 2026-08-17)",
        "campaign_vintage_id": CAMPAIGN_VINTAGE_ID,
        "sealed_input_integrity": integrity,
        "m4_curve_endogeneity": m4,
        "p1_phase_anchor": phase,
        "recommended_construct": recommendation,
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


if __name__ == "__main__":
    main()
