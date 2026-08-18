"""Stage 2, week C: the four never-yet-measured bars -- A1, A2, R1 and R2.

Spec: ``docs/superpowers/specs/2026-08-18-stage2-exam-delta.md`` (which carries
the ten v2 bars byte-frozen from
``docs/superpowers/specs/2026-08-17-spine-v2-exam.md``). The engine is week A's,
frozen: ``docs/superpowers/specs/stage2-fitted-params.json``. The flesh is
composed by ``scripts/stage2_worlds.py``.

**What this script measures, and nothing else.** Four bars have never been run
in any round of this campaign. Week A read the other eight and left these
explicitly absent, because ``A1`` and ``A2`` need real months of asset returns,
``R2`` needs a compiled ensemble and the panel source, and ``R1`` needs the
institutional twin driven off a compiled world. All four are read here **by the
sealed judges, imported and never re-implemented**: ``A1``/``A2`` through
``scripts/spine_v2_report``'s own ``judge_all``, ``R1`` through
``scripts/stage2_report.judge_r1`` (which delegates to ``spine_pilot_b3._judge``
on the b3 block carried byte-verbatim), ``R2`` through
``scripts/stage2_report.judge_r2`` (which delegates to
``spine_pilot_report.judge_b2``).

**The batches, and which construct each bar's seal demands.**

* ``A1``, ``A2``, ``R2`` -- the **unconditional 50-decade batch at seed
  20260821**, which is week A's own verification batch, fleshed. The seed is
  week A's deliberately: the spine is then bit-identical to the one the eight
  pre-flesh bars were read on, so a week-C verdict is attributable to the flesh
  and to nothing else. That identity is not asserted in prose -- the eight
  pre-flesh bars are re-judged on this batch and checked against the frozen
  artifact's own values before any week-C bar is reported.
* ``R1`` -- the **b3 over-commitment ladder**, byte-frozen: world ...802's own
  premise, its base seed 199002, the platform's per-path stride (20 rungs at
  ``199002 + 7919*k``), the four allocation arms ``[15, 35, 40, 55]``, the same
  book construction and the same hold-course institution run. The 20 rungs are
  verified pairwise distinct -- both their spines and their compiled month
  tapes -- because a ladder whose rungs collide measures one storyline twenty
  times (the round-one seed-stride defect, on the record).

**No bar is invented and no threshold is touched.** Everything below the four
verdicts is a **disclosure**: A1 at the 3% and 5% inflation lines (the exam
publishes both and judges neither), A1/A2 re-read on the flesh's own realised
panel inflation instead of the spine's, and all four bars re-read on the
premise-accepted batch. None of them can supply a verdict.

**D-SP-10 does not run here.** The conditioning-reach fix (owner ruling
2026-08-18) changed the block sampler's default design, and this script is the
*record* of the arm that was measured before it: every batch below is compiled
under ``stage2_worlds.REACH_BASELINE``, named explicitly at each of the three
call sites, so ``stage2-weekc-results.json`` still regenerates byte-identically.
The re-run under the fix is ``scripts/stage2_reach.py``, which writes its own
artifact and leaves this one alone.

Run (from the worktree root, no network):

    uv run python scripts/stage2_weekc.py
"""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import spine_pilot_b3 as b3  # noqa: E402
import stage2_fit as weeka  # noqa: E402
import stage2_worlds as worlds  # noqa: E402
from spine_v2_anchors import _asset_returns  # noqa: E402
from spine_v2_fit import to_decade  # noqa: E402
from spine_v2_report import Batch as V2Batch  # noqa: E402
from spine_v2_report import Decade as V2Decade  # noqa: E402
from stage2_report import Batch as P1Batch  # noqa: E402
from stage2_report import Decade as P1Decade  # noqa: E402
from stage2_report import (  # noqa: E402
    judge_carried_v2,
    judge_p1,
    judge_p2,
    judge_r1,
    judge_r2,
    load_sealed,
    load_v2_sealed,
)

from ah.gen.spine import panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
RESULTS_PATH = SPECS_DIR / "stage2-weekc-results.json"

#: The four bars week C exists to measure.
WEEK_C_BARS = ("A1", "A2", "R1", "R2")
#: The eight week A read, re-judged here only as an identity check on the spine.
PRE_FLESH_BARS = weeka.PRE_FLESH_BARS

#: A1's judged line is 4.0 pp and comes from the v2 seal. These two are the
#: exam's own published sensitivities: 3% is the line at which HISTORY's own
#: ordering reverses, and the exam prints it precisely so it cannot be
#: discovered later. Both are DISCLOSURES and neither is ever judged.
A1_DISCLOSURE_LINES_PP = (3.0, 5.0)

#: The arm this script records: the block sampler as it stood before D-SP-10.
#: Named at every call site rather than left to the module default, so the
#: default moving (it has, once) can never silently rewrite this record.
_BASELINE = worlds.reach_design(worlds.REACH_BASELINE)


# --------------------------------------------------------------------------- #
# building the judge-facing batch
# --------------------------------------------------------------------------- #


def fleshed_batch(
    decades: list[weeka.Stage2Decade],
    rows: np.ndarray,
    assets: dict[str, Any],
    *,
    inflation_from: str = "spine",
) -> V2Batch:
    """The compiled batch in the judges' own ``Decade`` contract.

    ``spine_v2_fit.to_decade`` builds week A's judge-facing record -- the sealed
    grader's labels, the decade's own 12-month inflation warm-up NaN'd, and the
    tight-policy flag from the generated slope -- with the three asset series
    NaN because week A has no flesh. This function calls it unchanged and fills
    in exactly those three series from the panel months the compiler drew.

    ``inflation_from`` is a DISCLOSURE switch and the primary is ``spine``:

    * ``spine`` -- the coupled system's own trailing inflation ``pi* + x``. This
      is the series every other bar in the exam is judged on (the seasons are
      cut from it, T1's eligibility is cut from it, P1's hot dial IS it), and it
      is the only one that satisfies the sealed 12-month warm-up rule, because
      the panel months a decade draws carry a defined trailing inflation from
      their first month by construction.
    * ``panel`` -- the trailing inflation of the real months actually drawn. It
      is the honest alternative reading and it is reported beside the verdict,
      never judged. The warm-up mask is held identical so the two differ in one
      thing only.
    """
    if inflation_from not in ("spine", "panel"):
        raise ValueError(f"inflation_from must be 'spine' or 'panel'; got {inflation_from!r}")
    equities = np.asarray(assets["equities"], dtype=np.float64)
    bonds = np.asarray(assets["bonds"], dtype=np.float64)
    commodities = np.asarray(assets["commodities"], dtype=np.float64)
    panel_trailing = np.asarray(assets["panel_yoy"], dtype=np.float64)

    out: list[V2Decade] = []
    for p, decade in enumerate(decades):
        base = to_decade(decade)
        index = np.asarray(rows[p], dtype=np.int64)
        yoy = base.yoy
        if inflation_from == "panel":
            yoy = panel_trailing[index].copy()
            yoy[np.isnan(base.yoy)] = np.nan  # the sealed warm-up, held identical
        out.append(
            replace(
                base,
                yoy=yoy,
                equities=equities[index],
                bonds=bonds[index],
                commodities=commodities[index],
            )
        )
    return V2Batch(tuple(out))


def asset_block(source: Any) -> dict[str, Any]:
    """The three monthly total-return series, from the anchors' own function.

    ``scripts/spine_v2_anchors._asset_returns`` is the code that built the A1/A2
    historical anchors: equities are the panel's ``equity_mkt``, commodities the
    panel's ``commodities``, and bonds the platform's SEALED ``govt_tr_10y``
    transform applied to the panel's 10-year yield. Imported rather than
    rewritten, so the generated side and the anchor side are the same code --
    the identity A1 and A2 would otherwise rest on an argument for.
    """
    returns = _asset_returns(source)
    if returns["real_assets"] is not None:  # pragma: no cover - the panel has none
        raise weeka.FitError(
            "a real-asset series has appeared in the panel; A1 is sealed as "
            "commodities-minus-bonds and adding a leg is an amendment, not a silent change"
        )
    return {
        "equities": returns["equities"],
        "bonds": returns["bonds"],
        "commodities": returns["commodities"],
        "panel_yoy": panel_yoy(source),
        "real_assets": None,
    }


def _sealed_at_line(v2_sealed: dict[str, Any], line_pp: float) -> dict[str, Any]:
    """The v2 seal with A1/A2's inflation line moved -- for DISCLOSURES only."""
    out = copy.deepcopy(v2_sealed)
    out["parameters"]["inflation_high_line_pp"] = float(line_pp)
    return out


# --------------------------------------------------------------------------- #
# the identity check: the spine week C fleshes IS the spine week A judged
# --------------------------------------------------------------------------- #


def spine_identity(
    decades: list[weeka.Stage2Decade],
    batch: V2Batch,
    system: weeka.CoupledSystem,
    sealed: dict[str, Any],
    v2_sealed: dict[str, Any],
) -> dict[str, Any]:
    """Re-read week A's eight bars on this batch and check the frozen values.

    Week C claims that the batch it fleshes is week A's batch. That claim decides
    whether an A1/A2/R2 reading is attributable to the flesh, so it is checked
    rather than stated: the eight pre-flesh bars are re-judged here and every
    value must equal the committed artifact's to 1e-12. A drift means the spine
    moved, and then nothing below it can be read as week C's own result.
    """
    verdicts: dict[str, Any] = dict(judge_carried_v2(batch, v2_sealed))
    p1_batch = P1Batch(tuple(P1Decade(labels=d.labels, yoy=d.yoy) for d in batch.decades))
    verdicts["P1"] = judge_p1(p1_batch, sealed)
    components, residual_sd = weeka.p2_components(decades, system)
    verdicts["P2"] = judge_p2(components, residual_sd, sealed)

    frozen = json.loads(worlds.PARAMS_PATH.read_text(encoding="utf-8"))["verification"]["bars"]
    committed = {row["bar"]: row for row in frozen if row.get("measured")}
    rows: list[dict[str, Any]] = []
    worst = 0.0
    for code in PRE_FLESH_BARS:
        got = float(verdicts[code]["value"])
        want = float(committed[code]["value"])
        drift = abs(got - want)
        worst = max(worst, drift)
        rows.append(
            {
                "bar": code,
                "week_a": want,
                "week_c_reread": got,
                "abs_drift": drift,
                "pass": bool(verdicts[code]["pass"]),
                "week_a_pass": bool(committed[code]["pass"]),
            }
        )
        if bool(verdicts[code]["pass"]) != bool(committed[code]["pass"]):
            raise weeka.FitError(
                f"{code} changed verdict between week A and week C's re-read; the spine is "
                "supposed to be identical, so this is a stop"
            )
    if worst > 1e-12:
        raise weeka.FitError(
            f"the fleshed batch's spine differs from week A's: worst pre-flesh bar drift "
            f"{worst:.3e}. A1/A2/R2 would not be attributable to the flesh"
        )
    return {"holds": True, "max_abs_drift": worst, "bars": rows}


# --------------------------------------------------------------------------- #
# R2's failure characterisation (obligation 6.2 -- characterise every FAIL)
# --------------------------------------------------------------------------- #


def r2_diagnostics(ens: Any, source: Any, verdict: dict[str, Any]) -> dict[str, Any]:
    """Where the largest inflation jump at a seam actually comes from.

    R2 has two halves and they fail for different reasons, so a bare FAIL is not
    a reading. Every seam is classified: a **forced re-entry** is the panel-edge
    rule (the block reaches the last panel row and a fresh entry is drawn rather
    than wrapping -- owner ruling 2026-08-16), and it is the only seam the era
    filter is allowed to miss, because with nothing reachable it draws
    unfiltered. Every other seam went through the join filter and is bounded by
    ``join_yoy_max_pp`` by construction.
    """
    rows = np.asarray(ens.row_indices)
    yoy = panel_yoy(source)
    n_rows = int(np.asarray(source.values).shape[0])
    jumps: list[float] = []
    edge_jumps: list[float] = []
    for p in range(rows.shape[0]):
        for m in range(1, rows.shape[1]):
            if rows[p, m] == rows[p, m - 1] + 1:
                continue
            jump = abs(float(yoy[rows[p, m]]) - float(yoy[rows[p, m - 1]]))
            jumps.append(jump)
            if int(rows[p, m - 1]) + 1 >= n_rows:
                edge_jumps.append(jump)
    conditioning = ens.meta.conditioning
    ordinary = [j for j in jumps if j not in edge_jumps] if edge_jumps else jumps
    return {
        "n_seams": len(jumps),
        "n_forced_reentry_seams": len(edge_jumps),
        "forced_reentries_stamped": int(conditioning["forced_reentries"]),
        "unfiltered_reentries_stamped": int(conditioning["unfiltered_reentries"]),
        "max_jump_pp": max(jumps) if jumps else 0.0,
        "max_jump_at_a_forced_reentry_pp": max(edge_jumps) if edge_jumps else None,
        "max_jump_at_an_ordinary_join_pp": max(ordinary) if ordinary else None,
        "bound_pp": float(verdict["threshold"]["join_yoy_max_pp"]),
        "reading": (
            "an ordinary join is filtered on the era bucket AND on |dYoY| <= the bound, so it "
            "cannot exceed it; a forced re-entry at the panel's last row draws unfiltered "
            "when no candidate matches, and that is the only seam that can"
        ),
    }


def a_bar_diagnostics(
    decades: list[weeka.Stage2Decade],
    rows: np.ndarray,
    assets: dict[str, Any],
    v2_sealed: dict[str, Any],
    source: Any,
) -> dict[str, Any]:
    """How well the dial A1/A2 condition on lines up with the months drawn.

    A1 and A2 pair a **simulated** inflation dial with **real** asset months, so
    the bars can only see history's inflation behaviour to the extent that the
    compiler's conditioning puts genuinely high-inflation months where the spine
    says inflation is high. That alignment is a measurable quantity and it is
    measured here, because a bare A2 FAIL is not a reading: it does not say
    whether the flesh failed to carry the flip or the dial failed to find it.

    The structural reason the two can drift apart, stated once: pool membership
    is conditioned on the panel's own hot/cool split at the **era line** (the
    compiler's ``fit_hazard`` threshold), while A1 and A2 condition at the
    exam's own **4.0 pp** line. Those are different lines on different series,
    and this block prices the difference rather than asserting it is small.
    """
    from ah.gen.spine import fit_hazard

    line = float(v2_sealed["parameters"]["inflation_high_line_pp"])
    panel_trailing = np.asarray(assets["panel_yoy"], dtype=np.float64)
    spine_yoy = np.concatenate([np.asarray(d.yoy)[12:] for d in decades])
    drawn = np.concatenate([panel_trailing[np.asarray(rows[p])[12:]] for p in range(len(decades))])
    spine_high = spine_yoy >= line
    drawn_high = drawn >= line
    agree = float(np.mean(spine_high == drawn_high))
    chance = float(
        np.mean(spine_high) * np.mean(drawn_high)
        + (1.0 - np.mean(spine_high)) * (1.0 - np.mean(drawn_high))
    )
    # how many months the quadrant conditioning actually reaches: a month is
    # SELECTED for its quadrant only when it opens a block (the decade's first
    # month, a join, or a forced re-entry). Every other month is the panel's own
    # next row, drawn for no reason but contiguity.
    selected = 0
    for p in range(len(decades)):
        index = np.asarray(rows[p], dtype=np.int64)
        selected += 1 + int(np.sum(index[1:] != index[:-1] + 1))
    total_months = int(rows.shape[0] * rows.shape[1])
    return {
        "inflation_line_pp": line,
        "era_line_the_pools_condition_on_pp": float(fit_hazard(source).era_threshold_pp),
        "era_line_the_grader_splits_on_pp": float(v2_sealed["parameters"]["era_threshold_pp"]),
        "months": int(spine_yoy.size),
        "share_high_on_the_spine_dial": float(np.mean(spine_high)),
        "share_high_on_the_months_drawn": float(np.mean(drawn_high)),
        "agreement": agree,
        "agreement_expected_if_the_two_dials_were_independent": chance,
        "quadrant_selected_months": selected,
        "months_in_the_batch": total_months,
        "share_of_months_selected_for_their_quadrant": selected / total_months,
        "mean_drawn_inflation_when_the_spine_says_high_pp": float(np.mean(drawn[spine_high]))
        if spine_high.any()
        else float("nan"),
        "mean_drawn_inflation_when_the_spine_says_low_pp": float(np.mean(drawn[~spine_high]))
        if (~spine_high).any()
        else float("nan"),
        "reading": (
            "the two dials agree on this share of judged months. Where they disagree, A1 and "
            "A2 are reading real months whose own inflation is on the other side of the line "
            "from the dial the bar conditions on"
        ),
    }


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def _bar_row(code: str, verdict: dict[str, Any]) -> dict[str, Any]:
    """One flat row per bar. The PASS/FAIL word is always the judge's own.

    ``R1`` is the one bar whose judge returns more than the exam asks for.
    ``spine_pilot_b3._judge`` ANDs a third check -- hold-course drawdown depth
    inside a band the script itself CONSTRUCTS -- into its ``overall``, and both
    the script's own docstring and the round-two record say that third check is
    outside the sealed b3 bars ("constructed post-seal, disclosed, not judged").
    The exam's R1 statement quotes two conditions and only two. So this row's
    ``pass`` is the judge's (a) AND (b) -- both of them the judge's own booleans,
    neither recomputed here -- and the judge's own ``overall`` is carried beside
    it under ``judge_overall_including_depth`` so nothing is hidden either way.
    """
    if code == "R1":
        sealed_pass = bool(verdict["monotone"]["pass"] and verdict["breach"]["pass"])
        row = {"bar": code, "pass": sealed_pass}
    else:
        row = {"bar": code, "pass": bool(verdict["pass"])}
    if code == "A1":
        row.update(
            {
                "value_difference_pp": float(verdict["difference_pp"]),
                "spread_high_pp": float(verdict["spread_high_pp"]),
                "spread_low_pp": float(verdict["spread_low_pp"]),
                "containment_pp": [float(x) for x in verdict["containment_pp"]],
                "directional_pass": bool(verdict["directional_pass"]),
                "containment_pass": bool(verdict["containment_pass"]),
                "inflation_line_pp": float(verdict["inflation_line_pp"]),
                "months_high": int(verdict["months_high"]),
                "months_low": int(verdict["months_low"]),
            }
        )
    elif code == "A2":
        row.update(
            {
                "correlation_high": float(verdict["correlation_high"]),
                "correlation_low": float(verdict["correlation_low"]),
                "correlation_difference": float(verdict["correlation_difference"]),
                "margin": float(verdict["margin"]),
                "share_positive_high": float(verdict["share_positive_high"]),
                "share_high_floor": float(verdict["share_high_floor"]),
                "share_positive_low_disclosure": float(verdict["share_positive_low"]),
                "level_positive": bool(verdict["level_positive"]),
                "margin_pass": bool(verdict["margin_pass"]),
                "share_high_pass": bool(verdict["share_high_pass"]),
                "windows_high": int(verdict["windows_high"]),
                "windows_low": int(verdict["windows_low"]),
            }
        )
    elif code == "R1":
        row.update(
            {
                "monotone_pass": bool(verdict["monotone"]["pass"]),
                "coverage_medians": [float(x) for x in verdict["monotone"]["medians"]],
                "breach_count": int(verdict["breach"]["breach_count"]),
                "breach_n": int(verdict["breach"]["n"]),
                "breach_threshold": int(verdict["breach"]["threshold"]),
                "breach_pass": bool(verdict["breach"]["pass"]),
                "depth_pass_disclosure": bool(verdict["depth"]["pass"]),
                "median_depth_disclosure": float(verdict["depth"]["median_depth"]),
                "depth_band_disclosure": [float(x) for x in verdict["depth"]["band"]],
                "judge_overall_including_depth": bool(verdict["overall"]),
            }
        )
    elif code == "R2":
        row.update(
            {
                "max_join_jump_pp": float(verdict["value"]["max_join_jump_pp"]),
                "join_bound_pp": float(verdict["threshold"]["join_yoy_max_pp"]),
                "p95_adjacent_yoy_pp": float(verdict["value"]["p95_adjacent_yoy_pp"]),
                "p95_bound_pp": float(verdict["threshold"]["p95_bound_pp"]),
                "ok_join": bool(verdict["ok_join"]),
                "ok_p95": bool(verdict["ok_p95"]),
                "n_joins": int(verdict["n_joins"]),
            }
        )
    return row


def _distinctness(tapes: list[np.ndarray], what: str) -> dict[str, Any]:
    keys = [tuple(int(x) for x in np.asarray(t).ravel()) for t in tapes]
    distinct = len(set(keys))
    if distinct != len(keys):
        raise weeka.FitError(
            f"{len(keys) - distinct} of {len(keys)} {what} collide -- a ladder whose rungs "
            "share a storyline measures one world many times (the round-one stride defect)"
        )
    return {"n": len(keys), "distinct": distinct, "all_distinct": True}


def main() -> int:
    sealed = load_sealed()
    v2_sealed = load_v2_sealed()
    n_decades = int(v2_sealed["bars"]["n_seeds"])
    b3_block = v2_sealed["carried"]["b3"]
    grid = [float(p) for p in b3_block["grid_private_pct"]]
    n_rungs = int(b3_block["n_seeds"])

    frozen = worlds.build_frozen_system()
    world = worlds.load_world()
    source = worlds.campaign_panel_source()
    assets = asset_block(source)
    declared_seed = world.engine_defaults.base_seed
    if declared_seed is None:  # pragma: no cover - the preset declares one
        raise weeka.FitError(
            f"world '{world.world_id}' declares no base seed; R1's ladder is defined as "
            "the world's own base seed plus the platform stride and cannot be invented here"
        )
    base_seed = int(declared_seed)
    ladder_seeds = [base_seed + b3.SEED_STRIDE * k for k in range(n_rungs)]

    streams = weeka.assert_stage2_tapes_distinct()
    flesh_streams = worlds.assert_flesh_streams_distinct([weeka.STAGE2_VERIFY_SEED, *ladder_seeds])

    # ------------------------------------------------------------------ #
    # A1, A2, R2 -- the unconditional 50-decade batch, fleshed
    # ------------------------------------------------------------------ #
    with worlds.stage2_flesh(
        frozen, premise_mode=worlds.PREMISE_UNCONDITIONAL, design=_BASELINE
    ) as run:
        ens = worlds.compile_world(world, n_decades, weeka.STAGE2_VERIFY_SEED)
        decades = run.last_decades
        rows = np.asarray(ens.row_indices)
        batch = fleshed_batch(decades, rows, assets)
        identity = spine_identity(decades, batch, frozen.system, sealed, v2_sealed)
        carried = judge_carried_v2(batch, v2_sealed)
        a1, a2 = carried["A1"], carried["A2"]
        r2 = judge_r2(ens, source, v2_sealed)
        r2_diag = r2_diagnostics(ens, source, r2)
        a_diag = a_bar_diagnostics(decades, rows, assets, v2_sealed, source)

        panel_batch = fleshed_batch(decades, rows, assets, inflation_from="panel")
        panel_carried = judge_carried_v2(panel_batch, v2_sealed)
        line_disclosures = {}
        for line in A1_DISCLOSURE_LINES_PP:
            moved = judge_carried_v2(batch, _sealed_at_line(v2_sealed, line))
            line_disclosures[f"{line:g}pp"] = {
                "A1": _bar_row("A1", moved["A1"]),
                "A2": _bar_row("A2", moved["A2"]),
            }
        unconditional_pool = dict(ens.meta.conditioning["pool_occupancy"])
        unconditional_stamp = {
            "forced_reentries": int(ens.meta.conditioning["forced_reentries"]),
            "unfiltered_reentries": int(ens.meta.conditioning["unfiltered_reentries"]),
            "spine_attempts": int(ens.meta.conditioning["spine_attempts"]),
            "n_pools_built": len(unconditional_pool),
            "smallest_pool": min(unconditional_pool.values()),
            "distinct_panel_rows_visited": int(np.unique(rows).size),
        }

    # ------------------------------------------------------------------ #
    # the same three bars on the PREMISE-ACCEPTED batch -- a disclosure
    # ------------------------------------------------------------------ #
    with worlds.stage2_flesh(frozen, premise_mode=worlds.PREMISE_DECLARED, design=_BASELINE) as run:
        p_ens = worlds.compile_world(world, n_decades, weeka.STAGE2_VERIFY_SEED)
        p_rows = np.asarray(p_ens.row_indices)
        p_batch = fleshed_batch(run.last_decades, p_rows, assets)
        p_carried = judge_carried_v2(p_batch, v2_sealed)
        p_r2 = judge_r2(p_ens, source, v2_sealed)
        premise_disclosure = {
            "A1": _bar_row("A1", p_carried["A1"]),
            "A2": _bar_row("A2", p_carried["A2"]),
            "R2": _bar_row("R2", p_r2),
            "attempts": int(run.calls[-1]["attempts"]),
            "note": (
                "the same three bars on the premise-accepted batch. A DISCLOSURE: the exam's "
                "own arm for the eight pre-flesh bars is the unconditional one and week C "
                "keeps its batch identical to week A's"
            ),
        }

    # ------------------------------------------------------------------ #
    # R1 -- the b3 over-commitment ladder, byte-frozen
    # ------------------------------------------------------------------ #
    with worlds.stage2_flesh(frozen, premise_mode=worlds.PREMISE_DECLARED, design=_BASELINE) as run:
        rung_rows = [
            np.asarray(worlds.compile_world(world, 1, seed).row_indices)[0] for seed in ladder_seeds
        ]
        rung_seasons = [run.decades[seed][0].season for seed in ladder_seeds]
        rung_attempts = {int(seed): int(run.decades[seed][0].attempts) for seed in ladder_seeds}
        ladder = {
            "seeds": [int(s) for s in ladder_seeds],
            "stride": int(b3.SEED_STRIDE),
            "month_tapes": _distinctness(rung_rows, "compiled month tapes"),
            "spines": _distinctness(rung_seasons, "spine season paths"),
            "attempts_per_rung": rung_attempts,
        }
        b3_run = b3._run_all(world, ladder_seeds, grid)
        r1 = judge_r1(v2_sealed, grid, b3_run)

    verdicts = {"A1": a1, "A2": a2, "R1": r1, "R2": r2}
    payload: dict[str, Any] = {
        "schema": "stage2-weekc-results-1",
        "purpose": (
            "stage 2 week C: the four bars that had never been measured in any round -- A1 "
            "and A2 (the flesh), R1 (the institutional twin's over-commitment ladder) and "
            "R2 (era coherence at the seams) -- read by the sealed judges on the coupled "
            "engine of week A, fleshed with verbatim real panel months"
        ),
        "spec": "docs/superpowers/specs/2026-08-18-stage2-exam-delta.md",
        "seal": "docs/superpowers/specs/stage2-prereg.json",
        "engine": "docs/superpowers/specs/stage2-fitted-params.json (FROZEN INPUT)",
        "world": str(worlds.WORLD_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "src_untouched": True,
        "promotion_note": (
            "the stage-2 world assembly is COMPOSED in scripts/ (stage2_worlds.py) and "
            "installs its spine sampler at runtime; the platform's own flesh machinery runs "
            "byte-verbatim underneath it. Promoting the stage-2 sampler into src/ is a "
            "SEPARATE OWNER RELEASE EVENT, after a pass, and is not done by this campaign"
        ),
        "frozen_engine_agreement": frozen.agreement,
        "streams": {"stage2": streams, "flesh": flesh_streams},
        "batches": {
            "A1_A2_R2": {
                "arm": "unconditional",
                "n_decades": n_decades,
                "seed": int(weeka.STAGE2_VERIFY_SEED),
                "seed_note": (
                    "week A's own verification seed, so the spine is bit-identical to the "
                    "one the eight pre-flesh bars were read on"
                ),
                "compiler": unconditional_stamp,
            },
            "R1": {
                "arm": "declared premise",
                "n_rungs": n_rungs,
                "grid_private_pct": grid,
                "ladder": ladder,
            },
        },
        "spine_identity": identity,
        "bars": [_bar_row(code, verdicts[code]) for code in WEEK_C_BARS],
        "r2_diagnostics": r2_diag,
        "a_bar_diagnostics": a_diag,
        "disclosures": {
            "A1_A2_at_other_inflation_lines": line_disclosures,
            "A1_A2_on_the_flesh_realised_inflation": {
                "A1": _bar_row("A1", panel_carried["A1"]),
                "A2": _bar_row("A2", panel_carried["A2"]),
                "note": (
                    "the same batch judged on the trailing inflation of the real months "
                    "drawn, instead of the coupled system's own. Reported, never judged"
                ),
            },
            "premise_accepted_batch": premise_disclosure,
        },
        "standing_caveat": (
            "nothing built on this generator line is a convincing model of history, the "
            "holdout is spent, and no appeal to held-out data is available"
        ),
    }
    RESULTS_PATH.write_text(
        json.dumps(weeka._round(payload), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"stage 2 week C -- four bars, sealed judges, engine frozen at {worlds.PARAMS_PATH.name}")
    print(f"frozen-engine agreement: max drift {frozen.agreement['max_abs_drift']:.3e}")
    print(f"spine identity vs week A: max drift {identity['max_abs_drift']:.3e}")
    print()
    for code in WEEK_C_BARS:
        row = _bar_row(code, verdicts[code])
        print(f"{code}: {'PASS' if row['pass'] else 'FAIL'}")
        for key, value in row.items():
            if key in ("bar", "pass"):
                continue
            print(f"    {key}: {value}")
    print()
    print(f"wrote {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
