"""The stage-2 exam's SEALED judging code -- one pure judge per NEW bar.

Spec: ``docs/superpowers/specs/2026-08-18-stage2-exam-delta.md``, which is the
delta on ``docs/superpowers/specs/2026-08-17-spine-v2-exam.md``. Thresholds are
sealed in ``docs/superpowers/specs/stage2-prereg.json`` and this module reads
them from there; **no threshold is written as a literal in this file**, the rule
``scripts/spine_v2_report.py`` states for itself and inherits from
``scripts/spine_pilot_report.py``.

**Two new bars and ten carried ones.**

* ``P1`` -- the phase-coupling bar. Do the growth dial and the inflation dial
  keep time with each other, or wander independently?
* ``P2`` -- the curve-endogeneity bar. Is the generated yield curve made of the
  economy the engine is simulating, or of drawn noise?
* ``T1 O1 D1 D2 D3 D4 A1 A2 R1 R2`` -- the ten v2 bars, **byte-frozen**. They are
  not re-implemented here and not re-derived: :func:`judge_carried_v2` imports
  ``scripts/spine_v2_report``'s own judges and hands them the v2 seal, loaded
  whole. A change in one of those ten verdicts is therefore attributable to the
  engine and to nothing else, which is the only reason a carried bar is worth
  having.

**Nothing is re-implemented on the anchor side either.** The classifier is the
sealed ``grader_v2`` (``scripts/spine_v2_grader.season_cells``); the transition
counting, the within-decade scramble null and the strict economic share are
``scripts/stage2_anchors.py``'s own functions, imported rather than copied, so
the judged side and the anchor side are provably the same code. That identity is
``P2``'s fourth anti-test obligation ("the decomposition function must be a
single piece of code called on both sides") discharged structurally rather than
by inspection, and ``P1`` gets the same treatment for free.

**Import-safe.** Importing this module reads no data, samples no ensemble, draws
no random number and writes no file, so the tests and the anti-test sweeps can
import the judges directly (the round-one precedent, kept through three rounds).

**What a judge is handed.**

* ``P1`` takes a :class:`Batch` of :class:`Decade` records -- raw monthly
  ``regime_ruleset_v1`` labels and trailing 12-month CPI inflation, nothing else.
  **The judge does the classifying itself**, so a caller cannot bypass the sealed
  mapping fix by handing in its own season labels, and it computes **the batch's
  own** independence null rather than inheriting history's (the correction the
  anchors' §5 measured and demanded: the substitution is sound to 0.0016 in the
  median and 0.0126 at worst, which is a fifth of a threshold).
* ``P2`` takes the generated curve's component standard deviations and the
  model's residual standard deviation -- the same five numbers, in the same
  units, that ``scripts/stage2_anchors.recorded_engine_shares`` reads off a
  committed fit. The economic components are measured on the batch; the residual
  is a model parameter, which is exactly how the anchors' power calculation
  scored the generated side.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_grader import season_cells  # noqa: E402
from spine_v2_report import Batch as V2Batch  # noqa: E402
from spine_v2_report import judge_all as _judge_v2_all  # noqa: E402
from spine_v2_report import judge_r1 as _judge_v2_r1  # noqa: E402
from spine_v2_report import judge_r2 as _judge_v2_r2  # noqa: E402
from stage2_anchors import (  # noqa: E402
    P1_MOVE_TYPES,
    P1_TOLERANCE_FRACTION_OF_HISTORY,
    PRIMARY_BLOCK_MONTHS,
    YOY_WARMUP_MONTHS,
    _pooled,
    _window_counts,
    strict_economic_share,
)

_REPO_ROOT = _SCRIPTS_DIR.parent
_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
SEALED_PATH = _SPECS / "stage2-prereg.json"
ANCHORS_PATH = _SPECS / "stage2-anchors.json"
V2_SEAL_PATH = _SPECS / "spine-v2-prereg.json"

#: The bar codes this module judges, in exam order: the two new ones first,
#: then the ten carried byte-frozen.
NEW_BAR_CODES = ("P1", "P2")
CARRIED_BAR_CODES = ("T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2", "R1", "R2")
BAR_CODES = NEW_BAR_CODES + CARRIED_BAR_CODES

#: The engine-side component names ``P2`` scores, and whether each is economic.
#: **The names are the anchors' own** (``m4_curve_endogeneity.point_estimate.strict``
#: and ``recorded_engine_shares``), so a committed fit artifact's component block
#: can be handed to :func:`judge_p2` unchanged -- which is how the retro
#: anti-test re-scores week 2 and week 3 through the sealed judge itself instead
#: of quoting their published shares. An engine that adds a component must say
#: which side of the line it falls on; the judge refuses a name it has never
#: heard of rather than defaulting, because the strict share IS that
#: classification (week 2 scores 40.4% naively and 0.0% here on the same fit).
P2_ECONOMIC_COMPONENTS = ("policy_rule", "inflation_gap", "season_term")
P2_EXOGENOUS_COMPONENTS = ("u_hat",)


# --------------------------------------------------------------------------- #
# the object a P1 judge is handed
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Decade:
    """One generated decade's raw monthly series. 120 months in the campaign.

    ``labels`` are ``regime_ruleset_v1`` month labels; ``yoy`` is trailing
    12-month CPI inflation in percentage points, ``NaN`` for the decade's own
    warm-up. Deliberately narrower than ``spine_v2_report.Decade`` -- P1 reads
    the two dials and nothing else -- and :func:`from_v2_batch` converts, so a
    caller holding one batch can run both exams on it.
    """

    labels: np.ndarray
    yoy: np.ndarray

    def __post_init__(self) -> None:
        if self.labels.shape[0] != self.yoy.shape[0]:
            raise ValueError(
                f"Decade.labels has {self.labels.shape[0]} months and yoy has "
                f"{self.yoy.shape[0]}; they must agree"
            )

    @property
    def months(self) -> int:
        return int(self.labels.shape[0])


@dataclass(frozen=True)
class Batch:
    """The generated batch a P1 verdict is taken over -- ``n_seeds`` decades."""

    decades: tuple[Decade, ...]

    @property
    def n_decades(self) -> int:
        return len(self.decades)


def from_v2_batch(batch: V2Batch) -> Batch:
    """The same decades, seen through P1's narrower window."""
    return Batch(tuple(Decade(labels=d.labels, yoy=d.yoy) for d in batch.decades))


# --------------------------------------------------------------------------- #
# small pure helpers (no thresholds live here)
# --------------------------------------------------------------------------- #


def _stack(batch: Batch, sealed: Mapping[str, Any]) -> dict[str, np.ndarray]:
    """The batch as three aligned ``(n_decades, months)`` arrays.

    ``cells`` are the sealed grader's season codes (``-1`` where trailing
    inflation is undefined, which is every decade's first twelve months);
    ``expanding`` and ``hot`` are the two dials as 0/1, derived exactly as
    ``stage2_anchors.section_m3_power`` derives them so that the judged side and
    the power calculation are the same construction.
    """
    params = sealed["parameters"]
    era = float(params["era_threshold_pp"])
    contracting_labels = tuple(params["contracting_labels"])
    months = int(params["decade_months"])
    if not batch.decades:
        raise ValueError("P1 needs at least one decade")

    cells_rows: list[np.ndarray] = []
    expanding_rows: list[np.ndarray] = []
    hot_rows: list[np.ndarray] = []
    for decade in batch.decades:
        if decade.months != months:
            raise ValueError(
                f"every decade must be {months} months (the sealed decade length); got "
                f"{decade.months}"
            )
        labels = np.asarray(decade.labels)
        yoy = np.asarray(decade.yoy, dtype=np.float64)
        cells_rows.append(
            np.asarray(
                season_cells(labels, yoy, era, contracting_labels=contracting_labels),
                dtype=np.int64,
            )
        )
        contracting = np.isin(labels, list(contracting_labels))
        expanding_rows.append((~contracting).astype(np.int64))
        hot_rows.append((np.nan_to_num(yoy, nan=-np.inf) > era).astype(np.int64))
    return {
        "cells": np.vstack(cells_rows),
        "expanding": np.vstack(expanding_rows),
        "hot": np.vstack(hot_rows),
    }


def _admissible_shifts(months: int, guard_months: int) -> list[int]:
    """Every circular shift a decade admits at the sealed guard.

    ``min(k, months - k) >= guard`` is the anchors' own rule: a one-month shift
    destroys almost none of the alignment, so tiny shifts drag the null toward
    the measured value and flatter the departure the bar is cut from.
    """
    return [k for k in range(1, months) if min(k, months - k) >= max(int(guard_months), 1)]


def batch_own_null(stacked: Mapping[str, np.ndarray], guard_months: int) -> dict[str, float]:
    """The independence null **this batch** produces, per move type.

    The construction is ``stage2_anchors.within_window_scramble_null``'s, applied
    to a batch of decades instead of to history's windows: circularly shift the
    hot/cool dial inside each decade -- the same shift in every decade, every
    admissible shift enumerated, so there is **no seed and no Monte Carlo
    error** -- rescore, average. The definedness mask does not travel with the
    shift: a month is undefined because its decade has no trailing inflation
    there, which is a property of the windowing and not of the inflation series.
    """
    cells = stacked["cells"]
    expanding = stacked["expanding"]
    hot = stacked["hot"]
    defined = cells >= 0
    months = int(cells.shape[1])
    per_move: dict[str, list[float]] = {move: [] for move in P1_MOVE_TYPES}
    for shift in _admissible_shifts(months, guard_months):
        rolled = np.roll(hot, shift, axis=1)
        scrambled = np.where(defined, (expanding << 1) | rolled, -1)[:, YOY_WARMUP_MONTHS:]
        counts = _window_counts(scrambled)
        for move in P1_MOVE_TYPES:
            per_move[move].append(_pooled(counts, move))
    out: dict[str, float] = {}
    for move, values in per_move.items():
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        out[move] = float(arr.mean()) if arr.size else float("nan")
    return out


def _p2_components(
    component_sd_pp: Mapping[str, float],
) -> dict[str, tuple[float, bool]]:
    """Map an engine's component standard deviations onto the sealed accounting.

    Every component must be named in :data:`P2_ECONOMIC_COMPONENTS` or in
    :data:`P2_EXOGENOUS_COMPONENTS`. An unknown name is an error rather than a
    default, because the whole content of the strict share is **which side of the
    line a component sits on** -- week 2 scored 40.4% on a naive accounting and
    0.0% on this one, and the difference is one component's classification.
    """
    known = set(P2_ECONOMIC_COMPONENTS) | set(P2_EXOGENOUS_COMPONENTS)
    unknown = sorted(set(component_sd_pp) - known)
    if unknown:
        raise KeyError(
            f"P2 was handed components it has no classification for: {unknown}. Every "
            "component must be declared economic or exogenous in the sealed judge, never "
            "defaulted -- the strict share IS that classification"
        )
    return {
        name: (float(sd), name in P2_ECONOMIC_COMPONENTS)
        for name, sd in sorted(component_sd_pp.items())
    }


# --------------------------------------------------------------------------- #
# the judges
# --------------------------------------------------------------------------- #


def judge_p1(batch: Batch, sealed: Mapping[str, Any]) -> dict[str, Any]:
    """P1 -- do the two dials keep time with each other? (the phase bar)

    The statistic is the clockwise fraction computed **separately for growth
    flips and for inflation crossings**, each reported as its departure from the
    batch's own phase-scrambled null. The bar asks that **both** departures reach
    the sealed minimum. Both move types must clear because the shortfall the bar
    exists against was spread evenly across the two (about 0.06 each), which is
    the signature of a missing link rather than of one broken dial; a
    one-move-type version could be passed by an engine that couples the dials in
    one direction only.

    The batch is judged in the construct the sealed pipeline actually emits:
    each decade's first twelve months carry no trailing inflation and are
    therefore uncounted, on the judged side and inside the null alike.
    """
    params = sealed["parameters"]
    guard = int(params["decade_scramble_guard_months"])
    thresholds = {move: float(sealed["bars"]["P1_departure_min"][move]) for move in P1_MOVE_TYPES}

    stacked = _stack(batch, sealed)
    censored = stacked["cells"][:, YOY_WARMUP_MONTHS:]
    observed = _window_counts(censored)
    nulls = batch_own_null(stacked, guard)

    per_move: dict[str, Any] = {}
    passes = True
    for move in P1_MOVE_TYPES:
        fraction = _pooled(observed, move)
        departure = fraction - nulls[move]
        move_pass = bool(departure >= thresholds[move])
        passes = passes and move_pass
        per_move[move] = {
            "clockwise_fraction": fraction,
            "own_null": nulls[move],
            "departure": departure,
            "threshold": thresholds[move],
            "pass": move_pass,
            "n_transitions": int(observed[move][0].sum()),
            "n_clockwise": int(observed[move][1].sum()),
        }

    return {
        "bar": "P1",
        "pass": bool(passes),
        "value": min(per_move[move]["departure"] - thresholds[move] for move in P1_MOVE_TYPES),
        "value_note": (
            "the binding margin -- the smaller of the two move types' (departure minus "
            "threshold). Positive on a PASS, and it is the number a sweep is monotone in"
        ),
        "per_move_type": per_move,
        "n_decades": batch.n_decades,
        "n_shifts_in_the_own_null": len(_admissible_shifts(int(params["decade_months"]), guard)),
        "null_construction": (
            "the BATCH's own within-decade phase scramble, exhaustively enumerated at the "
            "sealed guard -- seedless, and not history's null substituted in (the anchors' "
            "section 5 measured that substitution wrong by up to 0.0126, a fifth of a "
            "threshold)"
        ),
        "diagonal_disclosure": {
            "n_transitions": int(observed["diagonal"][0].sum()),
            "n_clockwise": int(observed["diagonal"][1].sum()),
            "judged": False,
            "note": (
                "no diagonal pair is in the clock, so diagonals are counter-clockwise by "
                "construction. They are reported, never folded into either move type, and "
                "they are the reason the OVERALL clockwise null is not 0.500"
            ),
        },
        "reading_note": (
            "P1 asks a generated engine to reproduce the minimum defensible fraction of a "
            "departure history itself can only just distinguish from zero (anchors 2.9). A "
            "PASS is evidence of SOME unambiguous phase coupling, not of history's amount"
        ),
    }


def judge_p2(
    component_sd_pp: Mapping[str, float],
    residual_stationary_sd_pp: float,
    sealed: Mapping[str, Any],
) -> dict[str, Any]:
    """P2 -- is the generated curve made of economics? (the endogeneity bar)

    The statistic is the **strict economic share** of the generated 10y-2y
    slope's variance: the summed squares of the economic components over the
    summed squares of everything, with exogenous shocks excluded from the
    numerator and left in the denominator. It is computed by
    ``stage2_anchors.strict_economic_share`` -- the same function, not a
    reimplementation, that scored history and both recorded engines.

    The bar is **two-sided**, and the upper edge is not decoration: a share can
    be driven to 1.0 by shrinking the drawn noise, so a one-sided "more
    economics is better" bar would be passed by an engine that simply removes
    the surprise the product needs. Anti-test 2 demonstrates that route closed.
    """
    band = [float(x) for x in sealed["bars"]["P2_economic_share_band"]]
    decomposition = strict_economic_share(
        _p2_components(component_sd_pp), float(residual_stationary_sd_pp)
    )
    share = decomposition["economic_share"]
    share = float("nan") if share is None else float(share)
    lo, hi = band
    below = bool(share < lo)
    above = bool(share > hi)
    return {
        "bar": "P2",
        "pass": bool(lo <= share <= hi),
        "value": share,
        "band": band,
        "below_band": below,
        "above_band": above,
        "failure_side": ("below" if below else ("above" if above else None)),
        "decomposition": decomposition,
        "naive_explained_share_disclosure": {
            "value": decomposition["naive_explained_share"],
            "judged": False,
            "note": (
                "everything that is not drawn noise, which is the number an unqualified "
                "reading of the same fit produces (40.4% for week 2 against a strict 0.0%). "
                "The gap between the two IS the finding P2 exists to bar"
            ),
        },
        "reading_note": (
            "below the band the curve a player reads is noise wearing an economic label and "
            "the exam's own definition of tight policy is a coin toss; above it the curve is "
            "a deterministic readout of the state and a player can learn a rule no real "
            "market would reward"
        ),
    }


def disclose_o1_symmetric(
    o1_verdict: Mapping[str, Any], sealed: Mapping[str, Any]
) -> dict[str, Any]:
    """O1's reading under the stage-2 PRIMARY construct -- a DISCLOSURE, not a bar.

    Ruling SQ1: the v2 ``O1`` bar carries byte-frozen (its sealed floor is
    unchanged and it is judged by the imported v2 judge), **and** the stage-2
    primary ordering/phase measurement is the windowing-symmetric
    windowed-overlapping construct. Those two are compatible precisely because
    the symmetric construct changes only the historical side: the generated
    statistic is bit-identical under both, so this function re-reads the SAME
    generated value against the floor the symmetric construct implies, and
    reports it beside the sealed verdict without touching it.

    The symmetric floor is cut from 2000 draws and carries about 0.003 of tape
    noise on a margin of the same size (anchors 2.6, 6.3). That is exactly why
    it is a disclosure: a bar cut from it would need the 640,000-draw rule, and
    re-cutting a sealed threshold is a different act from anchoring a new bar.
    """
    floor = float(sealed["parameters"]["o1_symmetric_floor"])
    value = float(o1_verdict["value"])
    return {
        "disclosure": "O1_under_the_stage2_primary_construct",
        "judged": False,
        "generated_value": value,
        "sealed_floor": float(o1_verdict["threshold"]),
        "sealed_pass": bool(o1_verdict["pass"]),
        "symmetric_floor": floor,
        "would_clear_the_symmetric_floor": bool(value >= floor),
        "margin_against_the_symmetric_floor": value - floor,
        "note": (
            "the generated statistic is unchanged between the two constructs -- symmetrising "
            "windows HISTORY, not the engine -- so this is the same number read against a "
            "different floor. The symmetric floor is under-resolved at 2000 draws and is "
            "reported, never judged"
        ),
    }


def judge_carried_v2(batch: V2Batch, v2_sealed: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The eight batch-judgeable v2 bars, by the v2 judges, on the v2 seal.

    Imported and unmodified. ``R1`` and ``R2`` are not here for the same reason
    they are not in ``spine_v2_report.judge_all``: they need an ensemble and the
    panel source rather than a batch of decades, and their callers hand those in
    through :func:`judge_r1` / :func:`judge_r2` below.
    """
    return _judge_v2_all(batch, dict(v2_sealed))


def judge_r1(
    v2_sealed: Mapping[str, Any], grid: list[float], run: dict[str, Any]
) -> dict[str, Any]:
    """R1, byte-frozen through two rounds. Delegates; re-derives nothing."""
    return _judge_v2_r1(dict(v2_sealed), grid, run)


def judge_r2(ens: Any, source: Any, v2_sealed: Mapping[str, Any]) -> dict[str, Any]:
    """R2, byte-frozen through two rounds. Delegates; re-derives nothing."""
    return _judge_v2_r2(ens, source, dict(v2_sealed))


# --------------------------------------------------------------------------- #
# the threshold block: one assembly path, from the measurements
# --------------------------------------------------------------------------- #


def p1_candidate_set(anchors: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """Every PUBLISHED candidate P1 threshold, per move type.

    Two families, and both are cut from the **within-window** null that ruling
    SQ8 requires -- the only scramble a batch of independent decades can perform
    on itself:

    * ``construct__*`` -- the two windowed history constructs (the recommended
      overlapping one and the disjoint sensitivity), from the anchors' section
      2.10 table.
    * ``label_dial_arm__*`` -- the nine arms of the sealed label-stability grid,
      from section 4.3. The baseline arm is the recommended construct's own
      candidate, so the two families agree where they overlap and the check is
      free.

    The superseded panel-wide-null candidates (anchors 2.7) are deliberately NOT
    in the set: SQ8 rules the within-window null on both sides, and those
    candidates are cut from a different operation. They sit above the minimum
    anyway, so the exclusion moves no number -- which is asserted in the seal
    rather than asserted here.
    """
    out: dict[str, dict[str, float]] = {move: {} for move in P1_MOVE_TYPES}
    within = anchors["p1_phase_anchor"]["within_window_null_constructs"]
    for construct in sorted(k for k in within if k.startswith("windowed_")):
        for move in P1_MOVE_TYPES:
            out[move][f"construct__{construct}"] = float(
                within[construct]["candidate_p1_threshold"][move]
            )
    for arm, block in sorted(anchors["m5_label_dial_stability"]["arms"].items()):
        for move in P1_MOVE_TYPES:
            out[move][f"label_dial_arm__{arm}"] = float(
                block["p1_per_move"][move]["candidate_p1_threshold"]
            )
    return out


def sealed_from_anchors(
    anchors_path: Path | None = None, v2_seal_path: Path | None = None
) -> dict[str, Any]:
    """Assemble the judge-readable threshold block from its two sources.

    There is exactly ONE assembly path and this is it -- ``spine_v2_report``'s
    own rule, one round on. The seal script calls this function to build what it
    writes and the anti-test sweeps call it to build what they judge with, so a
    sweep can never be run against numbers that differ from the sealed ones.
    Nothing is retyped: the new bars are **derived by the rulings, in code**,
    from ``stage2-anchors.json``, and the carried block is loaded whole from
    ``spine-v2-prereg.json``.

    The two derivations, each one ruling applied mechanically:

    * ``P1_departure_min`` = the **minimum** of the published candidate set
      (SQ7), which is cut from the within-window null (SQ8), on the
      windowed-overlapping construct (SQ1).
    * ``P2_economic_share_band`` = the strict economic share's block-bootstrap
      interval at the primary block length on the rho-refitted arm (SQ6).
    """
    anchors = json.loads((anchors_path or ANCHORS_PATH).read_text(encoding="utf-8"))
    v2 = json.loads((v2_seal_path or V2_SEAL_PATH).read_text(encoding="utf-8"))

    candidates = p1_candidate_set(anchors)
    p2_block_key = f"block_{PRIMARY_BLOCK_MONTHS}m"
    p2_ci = anchors["m4_curve_endogeneity"]["bootstrap_ci95"][p2_block_key]["rho_refitted"][
        "economic_share_ci95"
    ]
    recommended = anchors["recommended_construct"]["recommendation"]

    bars = {
        "grader": v2["bars"]["grader"],
        "n_seeds": v2["bars"]["n_seeds"],
        "P1_departure_min": {move: min(candidates[move].values()) for move in P1_MOVE_TYPES},
        "P1_departure_min_source": {
            move: min(candidates[move], key=lambda k, m=move: candidates[m][k])
            for move in P1_MOVE_TYPES
        },
        "P1_candidate_set": candidates,
        "P1_candidate_tolerance_fraction": P1_TOLERANCE_FRACTION_OF_HISTORY,
        "P1_both_move_types_required": True,
        "P2_economic_share_band": [float(p2_ci["lo"]), float(p2_ci["hi"])],
        "P2_summary": "strict_economic_share",
    }
    parameters = {
        # carried from the v2 seal, loaded whole -- the classifier the P1 judge
        # runs and the era line it splits hot from cool on
        "era_threshold_pp": v2["parameters"]["era_threshold_pp"],
        "contracting_labels": v2["parameters"]["contracting_labels"],
        "decade_months": v2["parameters"]["decade_months"],
        # stage-2's own
        "yoy_warmup_months": YOY_WARMUP_MONTHS,
        "phase_construct": recommended,
        "phase_null": "within_window",
        "decade_scramble_guard_months": int(
            anchors["p1_phase_anchor"]["within_window_null_constructs"][recommended][
                "within_window_null"
            ]["guard_months"]
        ),
        "o1_symmetric_floor": float(
            anchors["recommended_construct"]["o1_floor_under_each_construct"][recommended]
        ),
        "p2_block_months": PRIMARY_BLOCK_MONTHS,
        "p2_arm": "rho_refitted",
        "p2_economic_components": list(P2_ECONOMIC_COMPONENTS),
        "p2_exogenous_components": list(P2_EXOGENOUS_COMPONENTS),
    }
    return {
        "bars": bars,
        "parameters": parameters,
        "carried_v2": {
            "bar_codes": v2["bar_codes"],
            "bars": v2["bars"],
            "parameters": v2["parameters"],
            "carried": v2["carried"],
        },
    }


def load_sealed(path: Path | None = None) -> dict[str, Any]:
    """The sealed pre-registration. Read-only; nothing here ever writes it."""
    return json.loads((path or SEALED_PATH).read_text(encoding="utf-8"))


def load_v2_sealed(path: Path | None = None) -> dict[str, Any]:
    """The v2 seal, for the ten carried bars. Read-only, and never edited."""
    return json.loads((path or V2_SEAL_PATH).read_text(encoding="utf-8"))
