"""Anti-test sweeps for the two NEW stage-2 judges (exam obligation 6.1).

**Why this file exists.** Round two's B1 v2 reaction-function judge produced a
clean FAIL on all five seeds that carried **zero information about the model**:
its pass fraction *decreased* monotonically in the reaction strength it claimed
to measure, so a model with no reaction function at all scored best and the bar
was unreachable by any model, including a perfect one. §6.1 of the sealed exam
therefore requires, before a judge is sealed, a sweep of the model property the
judge claims to measure with the judge's pass rate shown to **increase** in it.

The stage-2 delta adds four obligations per bar on top of that (design document
§3.1 and §3.2), and every one of them is implemented here rather than described:

``P1``
  1. **Sweep the coupling.** Scale the growth -> inflation channel from absent to
     total, re-judge, and require the measured departure to rise and the pass
     rate not to fall. Where it saturates is reported, because both prior
     campaigns found bars that rise and then fall in their own mechanism's
     strength and saturation must be visible rather than discovered.
  2. **The null engine must FAIL.** At zero coupling the dials are independent by
     construction and P1 must return FAIL. If it does not, the judge is broken.
  3. **The retro anti-test.** Every engine on the record must fail. A new bar
     that passes an engine already established as uncoupled is void.
  4. **The scramble control.** Phase-scramble a batch that PASSES and confirm the
     statistic falls back to its null -- proof the bar measures alignment and not
     some other property of the batch.

``P2``
  1. **Sweep the endogenous loadings.** The measured economic share must rise and
     the pass rate must not fall over the range where the share is inside the
     band.
  2. **The noise-shrink control must FAIL from above.** Hold the loadings and
     scale the drawn residual down until the share exceeds the band's upper
     edge; the judge must return FAIL, and it must fail on the UPPER side. This
     is the specific gaming route a one-sided share bar would leave open and the
     design document requires it demonstrated closed, so the check asserts the
     side and not merely the verdict.
  3. **The retro anti-test.** Week 2 and week 3 must both fail below the band --
     re-scored here **through the sealed judge from their committed component
     standard deviations**, not by quoting their published shares.
  4. **Same-definition proof.** Discharged structurally: ``stage2_report.judge_p2``
     calls ``stage2_anchors.strict_economic_share``, the same function that
     scored history, so the two sides differ only in their input array. The
     retro sweep is the demonstration that the call path works on real engine
     inputs.

**Two shapes of sweep, and the rule for each.** P1's bar is one-sided from below
("more phase coupling is better, up to history's"), so its sweep runs the effect
from absent to total and the pass rate must not fall. P2's bar is **two-sided**,
so a raw sweep of its effect would correctly fall at the top and prove nothing:
its loading sweep is therefore evaluated over the sub-range where the share is
still inside the band (the design document's own wording), and a separate
**closeness** sweep -- half the batches above the anchor and half below, in the
v2 D-bar pattern -- carries the two-sided claim. The noise-shrink control is a
CONTROL, not a monotone sweep: its pass rate is *required* to fall, so it is
excluded from the monotonicity gate and carries its own required boolean.

**Determinism.** Every sweep draws from ``numpy.random.Generator(PCG64(seed))``
with its own literal seed below; no seed is derived from another by a stride (the
platform's seed-stride lesson), and a module-level assertion holds them distinct.
Re-running writes byte-identical output.

**The judges are the real ones.** Nothing here re-implements a judge or a
threshold: the sweeps import ``scripts/stage2_report``'s judges and build their
threshold block with ``sealed_from_anchors``, the same single assembly path the
seal writes. A sweep cannot pass against numbers that differ from the sealed
ones.

Invocation (from the worktree root, no network needed):

    uv run python scripts/stage2_antitest.py
"""

from __future__ import annotations

import itertools
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from stage2_anchors import P1_MOVE_TYPES  # noqa: E402
from stage2_report import (  # noqa: E402
    ANCHORS_PATH,
    Batch,
    Decade,
    judge_p1,
    judge_p2,
    sealed_from_anchors,
)

_REPO_ROOT = _SCRIPTS_DIR.parent
OUT_JSON = _REPO_ROOT / "docs" / "superpowers" / "specs" / "stage2-antitest-results.json"
OUT_MD = _REPO_ROOT / "docs" / "superpowers" / "specs" / "stage2-antitest-results.md"

#: One literal seed per sweep, all distinct. They continue the run 20260821-25
#: that ``scripts/stage2_anchors.py`` occupies, so no stage-2 tape is shared.
SEED_P1_COUPLING = 20260831
SEED_P1_SCRAMBLE = 20260832
SEED_P2_LOADINGS = 20260833
SEED_P2_NOISE = 20260834
SEED_P2_CLOSENESS = 20260835
SEED_P1_NULL_ENGINE = 20260836
_SEEDS = (
    SEED_P1_COUPLING,
    SEED_P1_SCRAMBLE,
    SEED_P2_LOADINGS,
    SEED_P2_NOISE,
    SEED_P2_CLOSENESS,
    SEED_P1_NULL_ENGINE,
)
assert len(set(_SEEDS)) == len(_SEEDS), "every sweep must draw from its own seed"

#: Batches per grid point, and decades per batch. The decade count is the
#: campaign's own sealed batch size, so a sweep measures each judge at the size
#: it will actually be run at.
N_REPLICATES = 24
#: The two P1 controls are measuring a RATE rather than a direction, so they get
#: their own, much larger replicate count. Twenty-four batches cannot separate a
#: 2% false-positive rate from a 10% one, and the difference between those two is
#: the single most consequential number this file produces.
N_CONTROL_REPLICATES = 300
N_DECADES = 50
DECADE_MONTHS = 120
WARMUP_MONTHS = 12

#: A synthetic month's inflation, either side of the sealed era line
#: (3.3513 pp) so that "hot" and "cool" are unambiguous under ``grader_v2``.
_HOT_YOY_PP = 6.0
_COOL_YOY_PP = 1.0
#: The two labels the P1 sweep uses. ``REC`` is contracting under the sealed
#: grader and ``EXP`` is not; nothing else about the label matters to P1.
_CONTRACTING_LABEL = "REC"
_EXPANDING_LABEL = "EXP"

#: The synthetic growth axis's run length, in months. A property of the
#: SYNTHETIC MODEL -- not a judge, not a bar, and not fitted to anything. Chosen
#: near the panel's own growth-spell scale so a decade carries several flips.
_GROWTH_RUN_MEAN = 14.0
_GROWTH_RUN_SD = 5.0
#: The lag at which the coupled inflation dial follows the growth axis. M3
#: measures ten months on the panel and says the panel does not pin it; the
#: sweep only needs SOME lag inside the hump, and its result must not depend on
#: which -- ``_LAG_SENSITIVITY`` re-runs the head of the sweep at seven and
#: thirteen to show that it does not.
_COUPLING_LAG_MONTHS = 10
_LAG_SENSITIVITY = (7, 13)
#: The block at which the coupling switches on and off. Mixing per MONTH would
#: chatter the inflation dial into one-month spells and measure the mixer rather
#: than the coupling; a block is the run scale the dial actually moves on.
_COUPLING_BLOCK_MONTHS = 24
#: P2's synthetic curve. The three economic components carry M4's own measured
#: standard deviations -- so scale 1.0 is history's decomposition, and the sweep
#: is calibrated to the anchor rather than to a convenient number -- and the one
#: exogenous component carries a week-3-sized policy deviation, which is what
#: makes the noise-shrink attack reachable at all rather than trivially capped.
_P2_ECONOMIC_SD_PP = {
    "policy_rule": 0.83618954205,
    "inflation_gap": 0.078326489103,
    "season_term": 0.053794025741,
}
_P2_EXOGENOUS_SD_PP = {"u_hat": 0.148625032509}
_P2_RESIDUAL_SD_PP = 0.747992998622
#: The persistence every generated curve component carries. rho = 0.98 is M4's
#: own fitted residual persistence, and it is what gives a 6000-month batch an
#: effective sample of a few dozen -- i.e. what makes these pass rates carry real
#: sampling noise instead of collapsing to a step function.
_P2_COMPONENT_RHO = 0.98


# --------------------------------------------------------------------------- #
# P1's synthetic engine
# --------------------------------------------------------------------------- #


def _runs(rng: np.random.Generator, n: int, mean: float, sd: float) -> np.ndarray:
    """A 0/1 series of alternating runs, lengths drawn normal and clipped at 2."""
    out = np.zeros(n, dtype=np.int64)
    state = int(rng.integers(0, 2))
    t = 0
    while t < n:
        length = int(max(2, round(float(rng.normal(mean, sd)))))
        out[t : t + length] = state
        t += length
        state = 1 - state
    return out


def _p1_decade(
    rng: np.random.Generator, coupling: float, lag: int = _COUPLING_LAG_MONTHS
) -> Decade:
    """A decade whose inflation dial follows its growth axis to a stated degree.

    The synthetic model has exactly one knob, ``coupling``: the fraction of the
    decade over which the hot/cool dial is a lagged copy of the growth axis
    rather than an independent process of its own. At ``0.0`` the two dials are
    independent by construction -- the null engine P1 must fail -- and at ``1.0``
    inflation follows growth everywhere, which is history's mechanism taken to
    its limit.

    **Why a lagged copy is the right synthetic coupling, in the clock's own
    terms.** The clock runs recovery -> expansion -> stagflation -> recession.
    A downward growth flip is clockwise when inflation is hot; an upward one when
    it is cool; a cool-to-hot crossing is clockwise while expanding and a
    hot-to-cool crossing while contracting. Setting ``hot(t) = expanding(t - m)``
    satisfies all four at once, which is exactly the plain-language mechanism:
    inflation runs hot at the end of expansions and cools during downturns.

    Neither the run lengths nor the lag are fitted to anything -- they are
    properties of the SYNTHETIC MODEL, and the sweep's claim is about the
    judge's response to the knob, not about the model.
    """
    n = DECADE_MONTHS
    expanding = _runs(rng, n, _GROWTH_RUN_MEAN, _GROWTH_RUN_SD)
    coupled = np.roll(expanding, lag)
    coupled[:lag] = expanding[0]  # the wrap would invent an alignment; the head is censored
    independent = _runs(rng, n, _GROWTH_RUN_MEAN, _GROWTH_RUN_SD)
    n_blocks = int(np.ceil(n / _COUPLING_BLOCK_MONTHS))
    take = np.repeat(rng.random(n_blocks) < coupling, _COUPLING_BLOCK_MONTHS)[:n]
    hot = np.where(take, coupled, independent)
    return _decade_from_dials(expanding, hot)


def _decade_from_dials(expanding: np.ndarray, hot: np.ndarray) -> Decade:
    """The two dials as the raw series a judge is handed -- labels and inflation."""
    labels = np.where(
        np.asarray(expanding).astype(bool), _EXPANDING_LABEL, _CONTRACTING_LABEL
    ).astype(object)
    yoy = np.where(np.asarray(hot).astype(bool), _HOT_YOY_PP, _COOL_YOY_PP).astype(np.float64)
    yoy[:WARMUP_MONTHS] = np.nan
    return Decade(labels=labels, yoy=yoy)


def _p1_batch(rng: np.random.Generator, coupling: float, lag: int) -> Batch:
    return Batch(tuple(_p1_decade(rng, coupling, lag) for _ in range(N_DECADES)))


def _scramble(rng: np.random.Generator, batch: Batch) -> Batch:
    """The same batch with each decade's inflation dial rolled off its growth axis.

    The control from obligation 4: if the statistic measures ALIGNMENT, this must
    collapse it to the null. Note what is preserved -- every decade's growth
    spells, its hot share, its inflation run lengths -- and what is destroyed:
    only the phase between them.

    **Two construction choices, both of which were got wrong first and both of
    which move the answer by more than the effect being measured.**

    1. **An INDEPENDENT shift per decade, not one shift for the batch.** A
       synthetic growth axis is quasi-periodic (alternating runs of a common
       mean), so one fixed shift applied to every decade does not destroy the
       alignment -- it moves every decade to the SAME new phase, and a shift near
       a whole number of cycles re-aligns them. Measured, that version left a
       fully coupled batch at a mean departure of 0.054 with a 58% pass rate.
    2. **The shift is drawn over the FULL circle, deliberately UNGUARDED.** The
       sealed guard belongs to the null, where it exists to stop a one-month
       shift -- which destroys almost no alignment -- from dragging the null
       toward the measured value. A control whose job is to destroy alignment
       wants the uniform randomisation whose average the null estimates, and
       restricting it to the guarded set samples phases non-uniformly relative to
       that average: measured, the guarded version leaves a systematic +0.019 /
       +0.023 residual and a 23% pass rate, against -0.005 / -0.005 and 11%
       unguarded. That residual is a property of the guarded shift set, not of
       the judge, and it is exactly the kind of construct artifact this campaign
       has now been caught by three times.
    """
    out: list[Decade] = []
    for decade in batch.decades:
        yoy = np.asarray(decade.yoy, dtype=np.float64)
        hot = np.nan_to_num(yoy, nan=_COOL_YOY_PP) > 0.5 * (_HOT_YOY_PP + _COOL_YOY_PP)
        rolled = np.roll(hot, int(rng.integers(1, DECADE_MONTHS)))
        scrambled = np.where(rolled, _HOT_YOY_PP, _COOL_YOY_PP).astype(np.float64)
        scrambled[:WARMUP_MONTHS] = np.nan
        out.append(Decade(labels=decade.labels, yoy=scrambled))
    return Batch(tuple(out))


# --------------------------------------------------------------------------- #
# P2's synthetic engine
# --------------------------------------------------------------------------- #


def _ar1(rng: np.random.Generator, sd: float, rho: float) -> float:
    """The MEASURED standard deviation of a batch-sized draw of an AR(1) component.

    The generated side's economic components are measured on the batch while the
    residual is a model parameter -- exactly how ``stage2_anchors._p2_power``
    scores a generated batch -- so this returns a measurement, complete with the
    sampling error a persistent series at this batch size actually carries.
    """
    if sd <= 0.0:
        return 0.0
    draw = rng.normal(0.0, sd * np.sqrt(1.0 - rho * rho), size=(N_DECADES, DECADE_MONTHS))
    series = np.empty_like(draw)
    series[:, 0] = rng.normal(0.0, sd, size=N_DECADES)
    for t in range(1, DECADE_MONTHS):
        series[:, t] = rho * series[:, t - 1] + draw[:, t]
    return float(np.std(series))


def _p2_measured(rng: np.random.Generator, economic_scale: float) -> dict[str, float]:
    """One generated batch's component standard deviations, as the judge sees them."""
    out = {
        name: _ar1(rng, sd * economic_scale, _P2_COMPONENT_RHO)
        for name, sd in _P2_ECONOMIC_SD_PP.items()
    }
    out.update({name: _ar1(rng, sd, _P2_COMPONENT_RHO) for name, sd in _P2_EXOGENOUS_SD_PP.items()})
    return out


def _p2_scale_for_share(target_share: float) -> float:
    """The economic loading scale that would place the share at ``target_share``.

    Pure algebra on the sealed accounting, so the closeness sweep can be stated
    in the units the bar is written in (a share) rather than in a loading nobody
    can read. Inverting ``share = E s^2 / (E s^2 + X + R)`` for ``s``.
    """
    economic = sum(sd * sd for sd in _P2_ECONOMIC_SD_PP.values())
    other = sum(sd * sd for sd in _P2_EXOGENOUS_SD_PP.values()) + _P2_RESIDUAL_SD_PP**2
    share = float(min(max(target_share, 0.0), 0.999))
    return float(np.sqrt(share * other / (economic * (1.0 - share))))


# --------------------------------------------------------------------------- #
# sweep machinery
# --------------------------------------------------------------------------- #


def _pass_rate(
    seed: int,
    grid: list[Any],
    judge_point: Callable[[np.random.Generator, Any], dict[str, Any]],
) -> tuple[list[float], list[float]]:
    """Pass rate and mean judged statistic at each grid point."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rates: list[float] = []
    values: list[float] = []
    for point in grid:
        passes = 0
        stats: list[float] = []
        for _ in range(N_REPLICATES):
            verdict = judge_point(rng, point)
            passes += int(bool(verdict["pass"]))
            stats.append(float(verdict["value"]))
        rates.append(passes / N_REPLICATES)
        values.append(float(np.nanmean(stats)))
    return rates, values


def _monotone(rates: list[float]) -> bool:
    return all(b >= a - 1e-12 for a, b in itertools.pairwise(rates))


def _saturation_point(grid: list[Any], rates: list[float]) -> Any:
    """The first grid point at which the pass rate reaches 1.0, or ``None``."""
    for point, rate in zip(grid, rates, strict=True):
        if rate >= 1.0:
            return point
    return None


# --------------------------------------------------------------------------- #
# the sweeps
# --------------------------------------------------------------------------- #


def run_sweeps(sealed: dict[str, Any], anchors: dict[str, Any]) -> dict[str, Any]:
    """Every anti-test sweep and control, as a JSON-ready record."""
    sweeps: dict[str, Any] = {}
    controls: dict[str, Any] = {}

    # ---- P1 obligation 1: sweep the coupling ---------------------------------
    grid = [0.0, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0]
    departures: dict[str, list[float]] = {move: [] for move in P1_MOVE_TYPES}

    def _p1_point(rng: np.random.Generator, coupling: float) -> dict[str, Any]:
        verdict = judge_p1(_p1_batch(rng, coupling, _COUPLING_LAG_MONTHS), sealed)
        for move in P1_MOVE_TYPES:
            departures[move].append(float(verdict["per_move_type"][move]["departure"]))
        return verdict

    rates, values = _pass_rate(SEED_P1_COUPLING, grid, _p1_point)
    per_move_mean = {
        move: [
            float(np.mean(departures[move][i * N_REPLICATES : (i + 1) * N_REPLICATES]))
            for i in range(len(grid))
        ]
        for move in P1_MOVE_TYPES
    }
    sweeps["P1_coupling"] = {
        "bar": "P1",
        "shape": "one-sided sweep of the effect itself",
        "effect": (
            "the fraction of a decade over which the inflation dial is a lagged copy of "
            f"the growth axis rather than an independent process ({_COUPLING_LAG_MONTHS}-month lag)"
        ),
        "grid": grid,
        "pass_rate": rates,
        "mean_statistic": values,
        "statistic": "binding margin: min over move types of (departure - threshold)",
        "mean_departure_by_move_type": per_move_mean,
        "monotone_non_decreasing": _monotone(rates),
        "saturates_at": _saturation_point(grid, rates),
        "departure_is_non_decreasing": {
            move: _monotone(per_move_mean[move]) for move in P1_MOVE_TYPES
        },
        "note": (
            "the design document requires the SATURATION point reported, because both "
            "prior campaigns found bars that rise and then fall in their own mechanism's "
            "strength. Here the departure keeps rising past the point the pass rate "
            "saturates, so the bar is not on a plateau it could slide off"
        ),
    }

    # ---- P1: the same head of the sweep at two other lags ---------------------
    lag_rows: dict[str, Any] = {}
    for lag in _LAG_SENSITIVITY:
        sub_grid = [0.0, 0.3, 0.7, 1.0]
        sub_rates, sub_values = _pass_rate(
            SEED_P1_COUPLING,
            sub_grid,
            lambda rng, c, m=lag: judge_p1(_p1_batch(rng, c, m), sealed),
        )
        lag_rows[f"lag_{lag}m"] = {
            "grid": sub_grid,
            "pass_rate": sub_rates,
            "mean_statistic": sub_values,
            "monotone_non_decreasing": _monotone(sub_rates),
        }
    sweeps["P1_coupling_lag_sensitivity"] = {
        "bar": "P1",
        "shape": "one-sided sweep of the effect itself",
        "effect": (
            "the same coupling sweep at seven and thirteen months instead of ten -- M3 "
            "measures ten and says the panel does not pin it, so the judge's response must "
            "not depend on which lag inside the hump the engine happens to use"
        ),
        "grid": [f"lag_{lag}m" for lag in _LAG_SENSITIVITY],
        "pass_rate": [row["pass_rate"][-1] for row in lag_rows.values()],
        "mean_statistic": [row["mean_statistic"][-1] for row in lag_rows.values()],
        "statistic": "binding margin at full coupling",
        "per_lag": lag_rows,
        "monotone_non_decreasing": all(row["monotone_non_decreasing"] for row in lag_rows.values()),
    }

    # ---- P1 obligation 2: the null engine must FAIL ---------------------------
    controls["P1_null_engine"] = _p1_null_engine(sealed)

    # ---- P1 obligation 4: the scramble control -------------------------------
    controls["P1_scramble"] = _p1_scramble_control(sealed)

    # ---- P1 obligation 3: the retro anti-test --------------------------------
    controls["P1_retro"] = _p1_retro(sealed, anchors)

    # ---- P2 obligation 1: sweep the endogenous loadings ----------------------
    # The grid runs from ABSENT to HISTORY'S OWN LEVEL, which is the sealed v2
    # rule for a one-sided sweep, quoted: "the sweep runs the effect from absent
    # to history's own value and the pass rate must not fall along it". Beyond
    # history the share starts crossing the band's UPPER edge and the pass rate
    # correctly falls -- that is the two-sided bar working, it is measured in
    # `above_history_disclosure` below rather than hidden, and the sweep that
    # carries the two-sided claim is P2_closeness.
    grid = [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]
    shares: list[float] = []

    def _p2_point(rng: np.random.Generator, scale: float) -> dict[str, Any]:
        verdict = judge_p2(_p2_measured(rng, scale), _P2_RESIDUAL_SD_PP, sealed)
        shares.append(float(verdict["value"]))
        return verdict

    rates, values = _pass_rate(SEED_P2_LOADINGS, grid, _p2_point)
    mean_share = [
        float(np.mean(shares[i * N_REPLICATES : (i + 1) * N_REPLICATES])) for i in range(len(grid))
    ]
    band = [float(x) for x in sealed["bars"]["P2_economic_share_band"]]
    inside_range = [i for i, share in enumerate(mean_share) if share <= band[1]]
    rates_inside = [rates[i] for i in inside_range]
    sweeps["P2_loadings"] = {
        "bar": "P2",
        "shape": "one-sided sweep, evaluated over the sub-range the design document names",
        "effect": (
            "the scale on the three economic curve loadings, from none to history's own "
            "level -- the endogenous loadings c_i, c_x and lam_u swept together"
        ),
        "grid": grid,
        "pass_rate": rates,
        "mean_statistic": values,
        "mean_economic_share": mean_share,
        "statistic": "strict economic share of the generated slope's variance",
        "band": band,
        "grid_points_inside_or_below_the_band": inside_range,
        "pass_rate_over_that_range": rates_inside,
        "share_is_non_decreasing": _monotone(mean_share),
        "monotone_non_decreasing": _monotone(rates_inside) and _monotone(mean_share),
        "saturates_at": _saturation_point(grid, rates),
        "above_history_disclosure": _p2_above_history(sealed),
        "note": (
            "the obligation is stated as 'the measured economic share must rise "
            "monotonically and the pass rate must be non-decreasing OVER THE RANGE WHERE "
            "THE SHARE IS INSIDE THE BAND', because the bar is two-sided and a raw sweep "
            "would correctly fall once the share leaves the band from above. Both halves "
            "are checked separately and both are recorded"
        ),
    }

    # ---- P2: the two-sided closeness sweep -----------------------------------
    anchor_share = float(anchors["m4_curve_endogeneity"]["point_estimate"]["economic_share"])
    misses = [0.35, 0.25, 0.15, 0.08, 0.03, 0.0]
    rng = np.random.Generator(np.random.PCG64(SEED_P2_CLOSENESS))
    closeness_rates: list[float] = []
    closeness_values: list[float] = []
    for miss in misses:
        passes = 0
        stats: list[float] = []
        for k in range(N_REPLICATES):
            target = anchor_share + miss if k % 2 == 0 else anchor_share - miss
            verdict = judge_p2(
                _p2_measured(rng, _p2_scale_for_share(target)), _P2_RESIDUAL_SD_PP, sealed
            )
            passes += int(bool(verdict["pass"]))
            stats.append(float(verdict["value"]))
        closeness_rates.append(passes / N_REPLICATES)
        closeness_values.append(float(np.mean(stats)))
    sweeps["P2_closeness"] = {
        "bar": "P2",
        "shape": "two-sided closeness sweep",
        "effect": (
            f"closeness of the generated economic share to history's {anchor_share:.4f}, "
            "half the batches that far above it and half that far below"
        ),
        "grid": misses,
        "grid_miss_months": misses,
        "pass_rate": closeness_rates,
        "mean_statistic": closeness_values,
        "statistic": "strict economic share of the generated slope's variance",
        "anchor_share": anchor_share,
        "monotone_non_decreasing": _monotone(closeness_rates),
        "note": (
            "the v2 D-bar pattern, applied to a two-sided share: a judge that is not "
            "maximised at the anchor fails this, which is the B1 v2 defect translated to a "
            "two-sided bar. The grid is ordered largest-miss-first, so a correct judge's "
            "rates are non-decreasing"
        ),
    }

    # ---- P2 obligation 2: the noise-shrink control ---------------------------
    controls["P2_noise_shrink"] = _p2_noise_shrink(sealed)

    # ---- P2 obligation 3: the retro anti-test --------------------------------
    controls["P2_retro"] = _p2_retro(sealed, anchors)

    return {"sweeps": sweeps, "controls": controls}


def _departures(sealed: dict[str, Any], batches: list[Batch]) -> dict[str, np.ndarray]:
    """Each batch's departure, per move type, in one array per move type."""
    out: dict[str, list[float]] = {move: [] for move in P1_MOVE_TYPES}
    for batch in batches:
        verdict = judge_p1(batch, sealed)
        for move in P1_MOVE_TYPES:
            out[move].append(float(verdict["per_move_type"][move]["departure"]))
    return {move: np.asarray(values, dtype=np.float64) for move, values in out.items()}


def _size_at(departures: dict[str, np.ndarray], thresholds: dict[str, float]) -> float:
    """The fraction of batches that would PASS at the given thresholds."""
    both = np.ones(next(iter(departures.values())).shape, dtype=bool)
    for move in P1_MOVE_TYPES:
        both &= departures[move] >= thresholds[move]
    return float(np.mean(both))


def _p1_null_engine(sealed: dict[str, Any]) -> dict[str, Any]:
    """Obligation 2 -- the null engine must fail. Both readings of it, measured.

    **The obligation is ambiguous and the ambiguity is not resolvable by picking
    the convenient reading, so both are computed and the choice is argued.**

    * **(a) The judge is centred on the null.** At zero coupling the measured
      departure must be indistinguishable from zero -- within its own Monte
      Carlo standard error. This is the reading that can detect the failure the
      obligation exists against (B1 v2's judge was not centred on anything; its
      pass rate *fell* in the effect), and it is the one the control is
      REQUIRED on.
    * **(b) The null engine never passes.** This is the literal wording, and it
      is arithmetically unreachable for any counting statistic at a finite batch
      size: a bar's false-positive rate against a wrong engine is its SIZE, and
      requiring zero size would void T1, O1 and D1-D4 as well, none of which was
      ever asked for it. It is therefore **measured and disclosed** -- at the
      sealed thresholds and at every published candidate -- rather than required.

    Reading (b)'s number is the most consequential thing in this file and it
    belongs in the seal's limitations register, not in a footnote: it is what the
    ruling to seal at the softest candidate costs.
    """
    rng = np.random.Generator(np.random.PCG64(SEED_P1_NULL_ENGINE))
    batches = [_p1_batch(rng, 0.0, _COUPLING_LAG_MONTHS) for _ in range(N_CONTROL_REPLICATES)]
    departures = _departures(sealed, batches)
    sealed_thresholds = {
        move: float(sealed["bars"]["P1_departure_min"][move]) for move in P1_MOVE_TYPES
    }
    candidates = sealed["bars"]["P1_candidate_set"]
    size_by_candidate = {
        name: _size_at(
            departures,
            {move: float(candidates[move][name]) for move in P1_MOVE_TYPES},
        )
        for name in sorted(candidates[P1_MOVE_TYPES[0]])
    }
    centred: dict[str, Any] = {}
    is_centred = True
    for move in P1_MOVE_TYPES:
        mean = float(np.mean(departures[move]))
        sd = float(np.std(departures[move], ddof=1))
        stderr = sd / np.sqrt(N_CONTROL_REPLICATES)
        ok = bool(abs(mean) <= stderr)
        is_centred = is_centred and ok
        centred[move] = {
            "mean_departure": mean,
            "sd_across_batches": sd,
            "standard_error": stderr,
            "threshold": sealed_thresholds[move],
            "mean_as_a_fraction_of_the_threshold": mean / sealed_thresholds[move],
            "within_one_standard_error_of_zero": ok,
        }
    return {
        "bar": "P1",
        "obligation": (
            "at zero coupling the dials are independent by construction and P1 must return "
            "a FAIL; if it does not, the judge is broken"
        ),
        "shape": "control -- a rate, measured at its own replicate count",
        "n_replicates": N_CONTROL_REPLICATES,
        "requirement": (
            "reading (a): the measured departure at zero coupling is within its own Monte "
            "Carlo standard error of zero, on both move types. Reading (b) -- that the null "
            "engine never passes -- is arithmetically unreachable for a counting statistic "
            "at a finite batch size (it is the bar's SIZE, and no bar in this exam was ever "
            "asked for zero size), so it is measured and disclosed rather than required"
        ),
        "reading_a_the_judge_is_centred_on_the_null": centred,
        "reading_b_the_size_of_the_bar": {
            "size_at_the_sealed_thresholds": _size_at(departures, sealed_thresholds),
            "size_at_every_published_candidate": size_by_candidate,
            "note": (
                "the false-positive rate against an engine whose dials are independent by "
                "construction, at the sealed batch size of 50 decades. Sealing at the "
                "SOFTEST candidate (ruling SQ7) buys reach against a correct engine and "
                "pays for it here; the number at the recommended construct's own candidate "
                "is published beside it so the trade is visible"
            ),
        },
        "holds": bool(is_centred),
    }


def _p1_scramble_control(sealed: dict[str, Any]) -> dict[str, Any]:
    """Obligation 4 -- scramble a PASSING batch; the statistic must fall to the null."""
    rng = np.random.Generator(np.random.PCG64(SEED_P1_SCRAMBLE))
    before_batches = [
        _p1_batch(rng, 1.0, _COUPLING_LAG_MONTHS) for _ in range(N_CONTROL_REPLICATES)
    ]
    after_batches = [_scramble(rng, batch) for batch in before_batches]
    before = _departures(sealed, before_batches)
    after = _departures(sealed, after_batches)
    thresholds = {move: float(sealed["bars"]["P1_departure_min"][move]) for move in P1_MOVE_TYPES}
    collapsed: dict[str, Any] = {}
    all_collapsed = True
    for move in P1_MOVE_TYPES:
        mean_before = float(np.mean(before[move]))
        mean = float(np.mean(after[move]))
        ok = bool(abs(mean) < thresholds[move] and abs(mean) <= 0.1 * abs(mean_before))
        all_collapsed = all_collapsed and ok
        collapsed[move] = {
            "mean_departure_before": mean_before,
            "mean_departure_after": mean,
            "standard_error_after": float(np.std(after[move], ddof=1))
            / np.sqrt(N_CONTROL_REPLICATES),
            "residual_as_a_fraction_of_the_pre_scramble_departure": mean / mean_before,
            "threshold": thresholds[move],
            "collapsed": ok,
        }
    rate_before = _size_at(before, thresholds)
    rate_after = _size_at(after, thresholds)
    return {
        "bar": "P1",
        "obligation": (
            "phase-scramble a generated batch that PASSES and confirm the statistic falls "
            "back to the null -- proof the bar measures alignment and not some other "
            "property of the batch"
        ),
        "shape": "control -- its pass rate is REQUIRED to fall, so it is not a monotone sweep",
        "n_replicates": N_CONTROL_REPLICATES,
        "scramble": (
            "an INDEPENDENT shift per decade, drawn uniformly over the full circle. The "
            "sealed guard belongs to the NULL and is deliberately not applied here"
        ),
        "pass_rate_before": rate_before,
        "pass_rate_after": rate_after,
        "bar_size_for_comparison": (
            "P1_null_engine.reading_b_the_size_of_the_bar.size_at_the_sealed_thresholds -- "
            "what a scrambled batch's pass rate should fall TO, since a scrambled batch is "
            "an uncoupled batch and an uncoupled batch's pass rate is the bar's size"
        ),
        "per_move_type": collapsed,
        "requirement": (
            "the coupled batch passes; after the scramble the mean departure is below the "
            "sealed threshold on both move types and is at most one tenth of its "
            "pre-scramble value; and the pass rate falls. NOT 'to exactly zero': a "
            "scrambled batch is an uncoupled batch, so what its pass rate must fall to is "
            "the bar's own size, and demanding third-decimal agreement would be demanding "
            "the control prove something the obligation never claimed"
        ),
        "holds": bool(rate_before == 1.0 and all_collapsed and rate_after < rate_before),
        "note": (
            "both construction choices in this control were got wrong first and each moved "
            "the answer by more than the residual it was measuring -- one shift for the "
            "whole batch left a mean departure of 0.054 and a 58% pass rate, and a guarded "
            "per-decade shift left +0.019 / +0.023 and 23%. Both artifacts are the shift "
            "SET, not the judge; the docstring on _scramble records why"
        ),
    }


def _p1_retro(sealed: dict[str, Any], anchors: dict[str, Any]) -> dict[str, Any]:
    """Every engine on the record, judged against ITS OWN null, must fail P1.

    The departures are the anchors' §5.3 measurements -- each recorded batch
    re-simulated from its committed engine and scrambled inside its own decades,
    on the judged (censored) construct, which is the construct this judge scores.
    They are read from the artifact rather than restated, and the comparison is
    against the SEALED thresholds rather than the candidates §5.3 quoted.
    """
    thresholds = {move: float(sealed["bars"]["P1_departure_min"][move]) for move in P1_MOVE_TYPES}
    rows: dict[str, Any] = {}
    any_passes = False
    for name, block in sorted(anchors["generated_side_scrambled_null"]["per_engine_arm"].items()):
        per_move = block["constructs"]["judged_censored"]["per_move"]
        departures = {
            move: float(per_move[move]["departure_against_own_null"]) for move in P1_MOVE_TYPES
        }
        passes = all(departures[move] >= thresholds[move] for move in P1_MOVE_TYPES)
        any_passes = any_passes or passes
        rows[name] = {
            "departure_against_own_null": departures,
            "passes": bool(passes),
            "shortfall": {move: thresholds[move] - departures[move] for move in P1_MOVE_TYPES},
        }
    return {
        "bar": "P1",
        "obligation": (
            "judge every engine on the record with the new judge; all must fail. A new bar "
            "that passes an engine already established as uncoupled is void"
        ),
        "thresholds": thresholds,
        "per_engine_arm": rows,
        "requirement": "no recorded engine passes",
        "holds": bool(not any_passes),
        "note": (
            "judged against each engine's OWN within-decade null on the censored construct "
            "it actually ships -- the anchors' section 5.3 measurement, not the earlier "
            "section 2.8 one that substituted history's null and read 0.010 margins"
        ),
    }


def _p2_above_history(sealed: dict[str, Any]) -> dict[str, Any]:
    """What the loading sweep does PAST history's own level -- reported, not swept.

    A one-sided sweep is defined to run from absent to history's own value, so
    this is outside its range by construction. It is measured anyway because a
    reader is entitled to see that the pass rate falls beyond history rather than
    plateauing, and to see WHERE: that is the upper edge of a two-sided bar doing
    its job, and it is the same behaviour the noise-shrink control provokes by a
    different route.
    """
    grid = [1.2, 1.5, 2.0]
    rates, values = _pass_rate(
        SEED_P2_LOADINGS,
        grid,
        lambda rng, scale: judge_p2(_p2_measured(rng, scale), _P2_RESIDUAL_SD_PP, sealed),
    )
    return {
        "grid": grid,
        "pass_rate": rates,
        "mean_economic_share": values,
        "band": [float(x) for x in sealed["bars"]["P2_economic_share_band"]],
        "note": (
            "outside the one-sided sweep's declared range (absent -> history's own level). "
            "The pass rate falls here because the share crosses the band's UPPER edge, "
            "which is the two-sided bar working as intended"
        ),
    }


def _p2_noise_shrink(sealed: dict[str, Any]) -> dict[str, Any]:
    """The gaming route: hold the loadings, shrink the drawn noise, must FAIL ABOVE."""
    rng = np.random.Generator(np.random.PCG64(SEED_P2_NOISE))
    grid = [_P2_RESIDUAL_SD_PP, 0.6, 0.5, 0.35, 0.2, 0.1]
    rows: list[dict[str, Any]] = []
    for residual in grid:
        passes = 0
        above = 0
        stats: list[float] = []
        for _ in range(N_REPLICATES):
            verdict = judge_p2(_p2_measured(rng, 1.0), residual, sealed)
            passes += int(bool(verdict["pass"]))
            above += int(bool(verdict["above_band"]))
            stats.append(float(verdict["value"]))
        rows.append(
            {
                "residual_sd_pp": residual,
                "pass_rate": passes / N_REPLICATES,
                "mean_economic_share": float(np.mean(stats)),
                "fails_above_the_band_rate": above / N_REPLICATES,
            }
        )
    last = rows[-1]
    return {
        "bar": "P2",
        "obligation": (
            "hold the loadings and scale the residual innovation down until the share "
            "exceeds the band's upper edge; the judge must return FAIL, and it must fail "
            "on the UPPER side. This is the specific gaming route a one-sided share bar "
            "would leave open and the design document requires it demonstrated closed"
        ),
        "shape": "control -- its pass rate is REQUIRED to fall, so it is not a monotone sweep",
        "grid_residual_sd_pp": grid,
        "rows": rows,
        "requirement": "pass rate 0.0 at the smallest residual, and every failure there is from ABOVE",
        "holds": bool(last["pass_rate"] == 0.0 and last["fails_above_the_band_rate"] == 1.0),
        "note": (
            "an engine that removes the surprise the product needs scores a HIGHER economic "
            "share, which is why the bar is two-sided and why this control, not the loading "
            "sweep, is the one that proves the upper edge is load-bearing"
        ),
    }


def _p2_retro(sealed: dict[str, Any], anchors: dict[str, Any]) -> dict[str, Any]:
    """Week 2 and week 3, re-scored THROUGH THE SEALED JUDGE, must fail below the band.

    Their component standard deviations are read from the anchors artifact and
    handed to :func:`stage2_report.judge_p2` unchanged. That is obligation 4
    ("the decomposition function must be a single piece of code called on both
    sides, with the sides differing only in their input array") demonstrated on
    real engine inputs rather than argued.
    """
    rows: dict[str, Any] = {}
    any_passes = False
    any_not_below = False
    for name, block in sorted(anchors["m4_curve_endogeneity"]["recorded_engine_shares"].items()):
        verdict = judge_p2(block["component_sd_pp"], block["residual_stationary_sd_pp"], sealed)
        recorded = float(block["economic_share"])
        rows[name] = {
            "component_sd_pp": block["component_sd_pp"],
            "residual_stationary_sd_pp": block["residual_stationary_sd_pp"],
            "share_through_the_sealed_judge": verdict["value"],
            "share_recorded_by_the_anchors": recorded,
            "reproduces_the_recorded_share": bool(abs(verdict["value"] - recorded) < 1e-9),
            "passes": bool(verdict["pass"]),
            "failure_side": verdict["failure_side"],
        }
        any_passes = any_passes or bool(verdict["pass"])
        any_not_below = any_not_below or verdict["failure_side"] != "below"
    return {
        "bar": "P2",
        "obligation": (
            "week 2 (0.0%) and week 3 (2.2%) must both be judged and both must fail BELOW "
            "the band. If either passes, the bar is not measuring what the finding found"
        ),
        "per_engine_arm": rows,
        "requirement": "no recorded engine passes, and every failure is from below",
        "holds": bool(not any_passes and not any_not_below),
        "same_definition_proof": bool(
            all(row["reproduces_the_recorded_share"] for row in rows.values())
        ),
        "note": (
            "each engine's share is recomputed by the sealed judge from its committed "
            "component standard deviations and must reproduce the share the anchors "
            "recorded for it -- which is what makes 'one decomposition function, called on "
            "both sides' a check rather than a claim"
        ),
    }


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def main() -> None:
    sealed = sealed_from_anchors()
    anchors = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
    result = run_sweeps(sealed, anchors)
    sweeps = result["sweeps"]
    controls = result["controls"]
    failures = [name for name, s in sweeps.items() if not s["monotone_non_decreasing"]]
    broken = [name for name, c in controls.items() if not c["holds"]]
    record = {
        "schema": "stage2-antitest-1",
        "obligation": (
            "exam section 6.1, carried into the stage-2 delta: before a judge is sealed, "
            "sweep the model property the judge claims to measure and confirm the judge's "
            "pass rate increases in it; plus the four per-bar obligations the stage-2 "
            "design document adds for P1 and for P2"
        ),
        "rule": (
            "P1's bar is one-sided from below, so its sweep runs the coupling from absent "
            "to total and the pass rate must not fall. P2's bar is TWO-SIDED, so its "
            "loading sweep is evaluated over the sub-range where the share is still inside "
            "the band -- the design document's own wording -- and a separate closeness "
            "sweep, half the batches above the anchor and half below, carries the "
            "two-sided claim. The noise-shrink attack is a CONTROL and not a sweep: its "
            "pass rate is required to FALL, and to fall on the upper side, so it is "
            "excluded from the monotonicity gate and carries its own required boolean"
        ),
        "n_replicates": N_REPLICATES,
        "n_decades_per_batch": N_DECADES,
        "decade_months": DECADE_MONTHS,
        "seeds": {
            "P1_coupling": SEED_P1_COUPLING,
            "P1_scramble": SEED_P1_SCRAMBLE,
            "P2_loadings": SEED_P2_LOADINGS,
            "P2_noise_shrink": SEED_P2_NOISE,
            "P2_closeness": SEED_P2_CLOSENESS,
        },
        "thresholds_judged_against": sealed["bars"],
        "sweeps": sweeps,
        "controls": controls,
        "all_monotone": not failures,
        "non_monotone_sweeps": failures,
        "all_controls_hold": not broken,
        "broken_controls": broken,
        "not_swept": (
            "the ten carried v2 bars are byte-frozen and are deliberately NOT re-swept: "
            "changing them is the thing a carried bar exists to prevent, and each was "
            "anti-tested before the v2 seal"
        ),
    }
    OUT_JSON.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    _write_markdown(record)
    for name, sweep in sweeps.items():
        rates = ", ".join(f"{r:.2f}" for r in sweep["pass_rate"])
        flag = "OK" if sweep["monotone_non_decreasing"] else "NOT MONOTONE"
        print(f"sweep   {name:32s} [{rates}]  {flag}")
    for name, control in controls.items():
        print(f"control {name:32s} {'OK' if control['holds'] else 'BROKEN'}")
    print(f"all monotone: {not failures} | all controls hold: {not broken}")
    if failures or broken:
        raise SystemExit(f"NOT SEALABLE: non-monotone sweeps {failures}, broken controls {broken}")


def _write_markdown(record: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Stage 2 - anti-test sweep results (run BEFORE the seal)")
    lines.append("")
    lines.append(
        "Produced by `scripts/stage2_antitest.py`, which imports the real judges from "
        "`scripts/stage2_report.py` and the real thresholds through `sealed_from_anchors` "
        "- the same single assembly path the seal writes. Machine-readable values: "
        "`docs/superpowers/specs/stage2-antitest-results.json`."
    )
    lines.append("")
    lines.append(f"**The obligation.** {record['obligation']}.")
    lines.append("")
    lines.append(f"**The rule.** {record['rule']}.")
    lines.append("")
    lines.append(
        f"**Size.** {record['n_replicates']} batches per grid point, "
        f"{record['n_decades_per_batch']} decades per batch (the campaign's own sealed batch "
        f"size), {record['decade_months']} months per decade. One literal seed per sweep, all "
        "distinct; re-running reproduces the JSON byte for byte."
    )
    lines.append("")
    verdict = (
        "every sweep is monotone non-decreasing and every control holds"
        if record["all_monotone"] and record["all_controls_hold"]
        else "NOT SEALABLE"
    )
    lines.append(f"**Verdict: {verdict}.**")
    lines.append("")
    lines.append("## Sweeps")
    lines.append("")
    for name, sweep in record["sweeps"].items():
        lines.append(f"### {name} - {sweep['effect']}")
        lines.append("")
        lines.append(f"| effect | pass rate | mean {sweep['statistic'].split(':')[0]} |")
        lines.append("|---|---|---|")
        for point, rate, value in zip(
            sweep["grid"], sweep["pass_rate"], sweep["mean_statistic"], strict=True
        ):
            label = point if isinstance(point, str) else f"{point:g}"
            lines.append(f"| {label} | **{rate:.2f}** | {value:.4f} |")
        lines.append("")
        if "mean_economic_share" in sweep:
            shares = ", ".join(f"{s:.4f}" for s in sweep["mean_economic_share"])
            lines.append(f"Mean economic share along the grid: [{shares}].")
            lines.append("")
        lines.append(
            f"Monotone non-decreasing: **{'yes' if sweep['monotone_non_decreasing'] else 'NO'}**"
            + (
                f"; saturates at **{sweep['saturates_at']}**."
                if sweep.get("saturates_at") is not None
                else "."
            )
        )
        if "note" in sweep:
            lines.append("")
            lines.append(sweep["note"][0].upper() + sweep["note"][1:] + ".")
        lines.append("")
    lines.append("## Controls")
    lines.append("")
    lines.append(
        "A control is not a sweep: its pass rate is *required* to behave in a particular "
        "way rather than to be monotone, so each carries its own requirement and its own "
        "boolean. The seal refuses to write if any of them is false."
    )
    lines.append("")
    for name, control in record["controls"].items():
        lines.append(f"### {name} - {'HOLDS' if control['holds'] else 'BROKEN'}")
        lines.append("")
        lines.append(f"**Obligation.** {control['obligation']}.")
        lines.append("")
        lines.append(f"**Requirement.** {control['requirement']}.")
        lines.append("")
        if "rows" in control:
            lines.append(
                "| residual sd (pp) | pass rate | mean economic share | fails from above |"
            )
            lines.append("|---|---|---|---|")
            for row in control["rows"]:
                lines.append(
                    f"| {row['residual_sd_pp']:g} | **{row['pass_rate']:.2f}** | "
                    f"{row['mean_economic_share']:.4f} | {row['fails_above_the_band_rate']:.2f} |"
                )
            lines.append("")
        if "per_engine_arm" in control:
            first = next(iter(control["per_engine_arm"].values()))
            if "departure_against_own_null" in first:
                lines.append("| engine / arm | growth flips | inflation crossings | passes? |")
                lines.append("|---|---|---|---|")
                for engine, row in control["per_engine_arm"].items():
                    dep = row["departure_against_own_null"]
                    lines.append(
                        f"| `{engine}` | {dep['growth_flip']:.6f} | "
                        f"{dep['inflation_crossing']:.6f} | "
                        f"**{'yes' if row['passes'] else 'no'}** |"
                    )
            else:
                lines.append("| engine / arm | share through the sealed judge | passes? | side |")
                lines.append("|---|---|---|---|")
                for engine, row in control["per_engine_arm"].items():
                    lines.append(
                        f"| `{engine}` | {row['share_through_the_sealed_judge']:.6f} | "
                        f"**{'yes' if row['passes'] else 'no'}** | {row['failure_side']} |"
                    )
            lines.append("")
        if "pass_rate_before" in control:
            lines.append(
                f"Pass rate before the scramble **{control['pass_rate_before']:.2f}**, after "
                f"**{control['pass_rate_after']:.3f}** over {control['n_replicates']} batches."
            )
            lines.append("")
            lines.append("| move type | mean departure before | after | its standard error |")
            lines.append("|---|---|---|---|")
            for move, row in control["per_move_type"].items():
                lines.append(
                    f"| {move} | {row['mean_departure_before']:.4f} | "
                    f"**{row['mean_departure_after']:.4f}** | {row['standard_error_after']:.4f} |"
                )
            lines.append("")
        if "reading_a_the_judge_is_centred_on_the_null" in control:
            lines.append("**Reading (a) -- is the judge centred on the null?**")
            lines.append("")
            lines.append(
                "| move type | mean departure | standard error | as a fraction of the threshold |"
            )
            lines.append("|---|---|---|---|")
            for move, row in control["reading_a_the_judge_is_centred_on_the_null"].items():
                lines.append(
                    f"| {move} | {row['mean_departure']:.5f} | {row['standard_error']:.5f} | "
                    f"{row['mean_as_a_fraction_of_the_threshold']:.3f} |"
                )
            lines.append("")
            size = control["reading_b_the_size_of_the_bar"]
            lines.append(
                "**Reading (b) -- the size of the bar.** False-positive rate against an "
                "engine whose dials are independent by construction, over "
                f"{control['n_replicates']} batches of {N_DECADES} decades: "
                f"**{size['size_at_the_sealed_thresholds']:.3f}** at the sealed thresholds."
            )
            lines.append("")
            lines.append("| candidate threshold | size |")
            lines.append("|---|---|")
            for name, value in size["size_at_every_published_candidate"].items():
                lines.append(f"| `{name}` | {value:.3f} |")
            lines.append("")
            lines.append(size["note"][0].upper() + size["note"][1:] + ".")
            lines.append("")
        if "note" in control:
            lines.append(control["note"][0].upper() + control["note"][1:] + ".")
            lines.append("")
    lines.append("## Not swept")
    lines.append("")
    lines.append(record["not_swept"][0].upper() + record["not_swept"][1:] + ".")
    lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
