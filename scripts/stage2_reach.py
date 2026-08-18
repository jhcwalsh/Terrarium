"""D-SP-10: the conditioning-reach fix, and the full sealed 12-bar exam re-run.

Charter: ``governance/decision-register.md`` **D-SP-10** (owner ruling
2026-08-18) -- "extend conditioning to reach every month (design owned by the
campaign; era-safe joins and severity discipline preserved; R1 selection-only
stands), then re-run the FULL sealed 12-bar exam unchanged -- the exam does not
move, the engine does."

**What moved and what did not.** The engine moved: ``scripts/stage2_worlds.py``
now composes a block sampler that consults the spine at every month rather than
only where a block opens (``stage2_worlds.ADOPTED_REACH``). Nothing else moved.
The seal is untouched, the thresholds are untouched, the judges are the sealed
ones imported by name, the world is the same world, the batches are the ones the
sealed constructs demand, the fitted engine is week A's frozen artifact and is
re-checked coefficient by coefficient before a batch is compiled, and no file
inside either pre-registration is edited. ``scripts/stage2_weekc.py`` still runs
the pre-fix arm and still writes its own artifact byte-identically.

**What this script reports.**

1. **BEFORE** -- the pre-fix arm recompiled here, so the two reach numbers are
   measured by the same code on both sides, and the four flesh bars are checked
   against the committed week-C artifact rather than quoted from it.
2. **AFTER** -- all twelve bars under the fix. The eight pre-flesh bars come
   through ``stage2_weekc.spine_identity``, which re-judges them on this batch
   and **raises** unless every one reproduces week A's committed value to 1e-12:
   the spine is untouched by a compiler change and that is checked, not assumed.
   ``A1``, ``A2`` and ``R2`` are read on the unconditional 50-decade batch at
   week A's own verification seed; ``R1`` on the byte-frozen b3 ladder under the
   declared premise. Both ``A2`` halves are reported -- the sealed primary (the
   spine's inflation) and the drawn-month disclosure arm.
3. **THE FRONTIER** -- every candidate design measured on the same batch, so a
   trade between bars is mapped rather than tuned past.
4. **DISPERSION** -- six seeds per arm, because a bar that swings by more than
   the verdict gap between seeds is not carrying a verdict, and D-SP-10's
   headline turns on exactly that (see ``A1``).

Run (from the worktree root, no network):

    uv run python scripts/stage2_reach.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import spine_pilot_b3 as b3  # noqa: E402
import stage2_fit as weeka  # noqa: E402
import stage2_weekc as weekc  # noqa: E402
import stage2_worlds as worlds  # noqa: E402
from stage2_report import (  # noqa: E402
    judge_carried_v2,
    judge_r1,
    judge_r2,
    load_sealed,
    load_v2_sealed,
)

from ah.gen.spine import fit_hazard, panel_quadrant, panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
RESULTS_PATH = SPECS_DIR / "stage2-reach-results.json"
WEEKC_PATH = SPECS_DIR / "stage2-weekc-results.json"

BEFORE = worlds.reach_design(worlds.REACH_BASELINE)
AFTER = worlds.ADOPTED_REACH

#: Every candidate on the same batch. (a), (b), (c) are the charter's own three;
#: (d) is (b)+(c) with the resolution rule the era filter forces; (e) is the
#: disclosure arm that prices the era filter itself and is never adopted.
FRONTIER = (
    ("baseline (pre-fix)", BEFORE),
    ("(a) short blocks, 3m", worlds.reach_design(worlds.REACH_SHORT_BLOCKS, block_months=3)),
    ("(a) short blocks, 2m", worlds.reach_design(worlds.REACH_SHORT_BLOCKS, block_months=2)),
    ("(b) path match, h=6", worlds.reach_design(worlds.REACH_PATH_MATCH)),
    ("(b) path match, h=12", worlds.reach_design(worlds.REACH_PATH_MATCH, match_horizon=12)),
    ("(c) divergence break", worlds.reach_design(worlds.REACH_DIVERGENCE_BREAK)),
    ("(b)+(c), h=6", worlds.reach_design(worlds.REACH_PATH_MATCH_BREAK)),
    ("(b)+(c), h=12", worlds.reach_design(worlds.REACH_PATH_MATCH_BREAK, match_horizon=12)),
    ("(d) +anticipate, h=6 [ADOPTED]", AFTER),
    ("(d) +anticipate, h=12", worlds.reach_design(worlds.REACH_ANTICIPATE, match_horizon=12)),
    ("(d) +anticipate, h=24", worlds.reach_design(worlds.REACH_ANTICIPATE, match_horizon=24)),
    ("(e) era-relaxed [DISCLOSURE]", worlds.reach_design(worlds.REACH_ERA_RELAXED)),
)

#: Seeds for the dispersion disclosure. The first is the sealed one; the other
#: five are consecutive and were fixed before any of them was read. They judge
#: nothing -- they say how much of a verdict is the engine and how much is the
#: draw.
DISPERSION_SEEDS = tuple(weeka.STAGE2_VERIFY_SEED + k for k in range(6))


class _Fixtures:
    """Everything read once and shared by every arm below."""

    def __init__(self) -> None:
        self.sealed = load_sealed()
        self.v2 = load_v2_sealed()
        self.frozen = worlds.build_frozen_system()
        self.world = worlds.load_world()
        self.source = worlds.campaign_panel_source()
        self.assets = weekc.asset_block(self.source)
        self.n_decades = int(self.v2["bars"]["n_seeds"])
        hazard = fit_hazard(self.source)
        self.cells = panel_quadrant(self.source, panel_yoy(self.source), hazard.era_threshold_pp)


def compile_arm(
    fx: _Fixtures, design: Any, seed: int, premise_mode: str = worlds.PREMISE_UNCONDITIONAL
):
    """One compiled batch under one design, with everything the judges need."""
    with worlds.stage2_flesh(fx.frozen, premise_mode=premise_mode, design=design) as run:
        ens = worlds.compile_world(fx.world, fx.n_decades, seed)
        decades = run.last_decades
        rows = np.asarray(ens.row_indices)
        seasons = np.stack([np.asarray(d.season, dtype=np.int64) for d in decades])
        return {
            "ens": ens,
            "decades": decades,
            "rows": rows,
            "batch": weekc.fleshed_batch(decades, rows, fx.assets),
            "panel_batch": weekc.fleshed_batch(decades, rows, fx.assets, inflation_from="panel"),
            "reach": worlds.reach_metrics(rows, seasons, fx.cells),
            "stamp": run.reach.get(int(seed), {"design": design.name}),
        }


def _seam_split(rows: np.ndarray, yoy: np.ndarray) -> dict[str, Any]:
    """``R2``'s p95, split by the kind of month pair it is taken over.

    ``R2``'s second half is the 95th percentile of |change in trailing YoY|
    between adjacent months. Under the pre-fix engine 7.5% of adjacent pairs
    were seams and the percentile sat inside the contiguous panel's own
    distribution; conditioning that reaches every month is bought with joins,
    and a join is allowed to move inflation by up to the declared bound. So the
    two halves of R2 pull against each other by construction, and this is the
    arithmetic of it rather than an assertion about it.
    """
    changes: list[tuple[float, bool]] = []
    for p in range(rows.shape[0]):
        for m in range(1, rows.shape[1]):
            a, b_ = int(rows[p, m - 1]), int(rows[p, m])
            changes.append((abs(float(yoy[b_]) - float(yoy[a])), b_ != a + 1))
    vals = np.array([c for c, _ in changes])
    seam = np.array([s for _, s in changes])
    return {
        "adjacent_pairs": int(vals.size),
        "seam_pairs": int(seam.sum()),
        "seam_share": float(seam.mean()),
        "p95_all": float(np.nanpercentile(vals, 95)),
        "p95_contiguous_pairs_only": float(np.nanpercentile(vals[~seam], 95)),
        "p95_seam_pairs_only": float(np.nanpercentile(vals[seam], 95)) if seam.any() else None,
    }


def _column(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    """One field of the dispersion rows, as an array."""
    return np.array([float(r[key]) for r in rows], dtype=np.float64)


def bars_block(fx: _Fixtures, arm: dict[str, Any]) -> dict[str, Any]:
    """``A1``, ``A2``, ``R2`` and both ``A2`` halves, by the sealed judges."""
    carried = judge_carried_v2(arm["batch"], fx.v2)
    panel_carried = judge_carried_v2(arm["panel_batch"], fx.v2)
    r2 = judge_r2(arm["ens"], fx.source, fx.v2)
    return {
        "A1": weekc._bar_row("A1", carried["A1"]),
        "A2": weekc._bar_row("A2", carried["A2"]),
        "R2": weekc._bar_row("R2", r2),
        "A1_on_the_drawn_months_inflation": weekc._bar_row("A1", panel_carried["A1"]),
        "A2_on_the_drawn_months_inflation": weekc._bar_row("A2", panel_carried["A2"]),
        "_r2_verdict": r2,
    }


def run_r1(fx: _Fixtures, design: Any) -> dict[str, Any]:
    """``R1``'s byte-frozen b3 ladder, compiled under ``design``."""
    b3_block = fx.v2["carried"]["b3"]
    grid = [float(p) for p in b3_block["grid_private_pct"]]
    n_rungs = int(b3_block["n_seeds"])
    base_seed = int(fx.world.engine_defaults.base_seed or 0)
    ladder_seeds = [base_seed + b3.SEED_STRIDE * k for k in range(n_rungs)]
    with worlds.stage2_flesh(fx.frozen, premise_mode=worlds.PREMISE_DECLARED, design=design) as run:
        rung_rows = [
            np.asarray(worlds.compile_world(fx.world, 1, seed).row_indices)[0]
            for seed in ladder_seeds
        ]
        rung_seasons = [run.decades[seed][0].season for seed in ladder_seeds]
        ladder = {
            "seeds": [int(s) for s in ladder_seeds],
            "stride": int(b3.SEED_STRIDE),
            "month_tapes": weekc._distinctness(rung_rows, "compiled month tapes"),
            "spines": weekc._distinctness(rung_seasons, "spine season paths"),
        }
        verdict = judge_r1(fx.v2, grid, b3._run_all(fx.world, ladder_seeds, grid))
    row = weekc._bar_row("R1", verdict)
    row["ladder"] = ladder
    row["arm"] = "declared premise"
    return row


def main() -> int:
    fx = _Fixtures()
    seed = int(weeka.STAGE2_VERIFY_SEED)
    committed = json.loads(WEEKC_PATH.read_text(encoding="utf-8"))
    committed_bars = {row["bar"]: row for row in committed["bars"]}

    # ------------------------------------------------------------------ #
    # BEFORE -- the pre-fix arm, recompiled here
    # ------------------------------------------------------------------ #
    before = compile_arm(fx, BEFORE, seed)
    before_bars = bars_block(fx, before)
    before_diag = weekc.a_bar_diagnostics(
        before["decades"], before["rows"], fx.assets, fx.v2, fx.source
    )
    reproduced = {}
    for code in ("A1", "A2", "R2"):
        want, got = committed_bars[code], before_bars[code]
        keys = [k for k in want if k not in ("bar", "ladder", "arm") and isinstance(want[k], float)]
        drift = max((abs(float(got[k]) - float(want[k])) for k in keys), default=0.0)
        reproduced[code] = {
            "max_abs_drift_vs_committed": drift,
            "pass_matches": got["pass"] == want["pass"],
        }
        if drift > 1e-12 or got["pass"] != want["pass"]:
            raise weeka.FitError(
                f"the pre-fix arm no longer reproduces the committed week-C reading for {code} "
                f"(drift {drift:.3e}); the before/after comparison would be meaningless"
            )

    # ------------------------------------------------------------------ #
    # AFTER -- the fix, and the whole exam
    # ------------------------------------------------------------------ #
    after = compile_arm(fx, AFTER, seed)
    identity = weekc.spine_identity(
        after["decades"], after["batch"], fx.frozen.system, fx.sealed, fx.v2
    )
    after_bars = bars_block(fx, after)
    after_diag = weekc.a_bar_diagnostics(
        after["decades"], after["rows"], fx.assets, fx.v2, fx.source
    )
    r2_diag = weekc.r2_diagnostics(after["ens"], fx.source, after_bars["_r2_verdict"])
    yoy = panel_yoy(fx.source)
    r2_split = {
        "before": _seam_split(before["rows"], yoy),
        "after": _seam_split(after["rows"], yoy),
    }
    r1_after = run_r1(fx, AFTER)
    premise_after = compile_arm(fx, AFTER, seed, premise_mode=worlds.PREMISE_DECLARED)
    premise_bars = bars_block(fx, premise_after)

    # ------------------------------------------------------------------ #
    # THE FRONTIER -- every candidate, same batch, same judges
    # ------------------------------------------------------------------ #
    frontier: list[dict[str, Any]] = []
    for label, design in FRONTIER:
        arm = compile_arm(fx, design, seed)
        bars = bars_block(fx, arm)
        diag = weekc.a_bar_diagnostics(arm["decades"], arm["rows"], fx.assets, fx.v2, fx.source)
        r2v = bars["_r2_verdict"]
        frontier.append(
            {
                "arm": label,
                "design": arm["stamp"].get("design", design.name),
                "conditioning_reach": arm["reach"]["conditioning_reach"],
                "share_selected_for_their_quadrant": arm["reach"][
                    "share_of_months_selected_for_their_quadrant"
                ],
                "dial_agreement": diag["agreement"],
                "dial_agreement_if_independent": diag[
                    "agreement_expected_if_the_two_dials_were_independent"
                ],
                "seams": int(np.sum(arm["rows"][:, 1:] != arm["rows"][:, :-1] + 1)),
                "forced_reentries": int(arm["ens"].meta.conditioning["forced_reentries"]),
                "unfiltered_reentries": int(arm["ens"].meta.conditioning["unfiltered_reentries"]),
                "distinct_panel_rows_visited": arm["reach"]["distinct_panel_rows_visited"],
                "unresolved_divergences": arm["stamp"].get("unresolved_divergences"),
                "unresolved_blocked_by_the_era_filter": arm["stamp"].get(
                    "unresolved_divergences_blocked_by_the_era_filter"
                ),
                "anticipating_moves": arm["stamp"].get("anticipating_moves"),
                "A1_difference_pp": bars["A1"]["value_difference_pp"],
                "A1_pass": bars["A1"]["pass"],
                "A2_correlation_high": bars["A2"]["correlation_high"],
                "A2_gap": bars["A2"]["correlation_difference"],
                "A2_share_positive_high": bars["A2"]["share_positive_high"],
                "A2_pass": bars["A2"]["pass"],
                "R2_max_join_jump_pp": r2v["value"]["max_join_jump_pp"],
                "R2_p95_pp": r2v["value"]["p95_adjacent_yoy_pp"],
                "R2_pass": bars["R2"]["pass"],
            }
        )

    # ------------------------------------------------------------------ #
    # DISPERSION -- six seeds per arm, judging nothing
    # ------------------------------------------------------------------ #
    dispersion: dict[str, Any] = {}
    for label, design in (("before", BEFORE), ("after", AFTER)):
        rows_out = []
        for s in DISPERSION_SEEDS:
            arm = compile_arm(fx, design, int(s))
            bars = bars_block(fx, arm)
            rows_out.append(
                {
                    "seed": int(s),
                    "sealed_seed": int(s) == seed,
                    "conditioning_reach": arm["reach"]["conditioning_reach"],
                    "A1_difference_pp": bars["A1"]["value_difference_pp"],
                    "A2_correlation_high": bars["A2"]["correlation_high"],
                    "A2_share_positive_high": bars["A2"]["share_positive_high"],
                    "R2_p95_pp": bars["R2"]["p95_adjacent_yoy_pp"],
                    "R2_max_join_jump_pp": bars["R2"]["max_join_jump_pp"],
                }
            )
        a1 = _column(rows_out, "A1_difference_pp")
        dispersion[label] = {
            "seeds": rows_out,
            "A1_difference_pp_mean": float(a1.mean()),
            "A1_difference_pp_sd": float(a1.std(ddof=1)),
            "A1_difference_pp_positive_of_6": int((a1 > 0).sum()),
            "A2_correlation_high_positive_of_6": int(
                (_column(rows_out, "A2_correlation_high") > 0).sum()
            ),
            "conditioning_reach_mean": float(_column(rows_out, "conditioning_reach").mean()),
        }

    for block in (before_bars, after_bars, premise_bars):
        block.pop("_r2_verdict", None)

    payload: dict[str, Any] = {
        "schema": "stage2-reach-results-1",
        "purpose": (
            "D-SP-10: the conditioning-reach fix to the stage-2 compiler, and the full sealed "
            "12-bar exam re-run on it. The exam does not move -- the engine does"
        ),
        "charter": "governance/decision-register.md D-SP-10 (owner ruling 2026-08-18)",
        "spec": "docs/superpowers/specs/2026-08-18-stage2-exam-delta.md",
        "seal": "docs/superpowers/specs/stage2-prereg.json",
        "engine": "docs/superpowers/specs/stage2-fitted-params.json (FROZEN INPUT -- nothing refitted)",
        "world": str(worlds.WORLD_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "src_untouched": True,
        "adopted_design": {
            "name": AFTER.name,
            "match_horizon": AFTER.match_horizon,
            "break_on_divergence": AFTER.break_on_divergence,
            "anticipate": AFTER.anticipate,
            "era_relaxed_joins": AFTER.era_relaxed_joins,
            "block_months_override": AFTER.block_months_override,
            "note": (
                "path-matched entries + a mid-block break when the next month's quadrant is not "
                "the spine's + an anticipating re-entry when the era filter leaves that break "
                "unjoinable. Era-safe joins, the forced-re-entry rule, the declared block length, "
                "the severity strata and premise refusal are all unchanged"
            ),
        },
        "frozen_engine_agreement": fx.frozen.agreement,
        "spine_identity_after_the_fix": identity,
        "batches": {
            "A1_A2_R2": {"arm": "unconditional", "n_decades": fx.n_decades, "seed": seed},
            "R1": {"arm": "declared premise", "n_rungs": int(fx.v2["carried"]["b3"]["n_seeds"])},
        },
        "before": {
            "design": BEFORE.name,
            "reach": before["reach"],
            "dial": before_diag,
            "bars": before_bars,
            "R1": committed_bars["R1"],
            "R1_note": (
                "quoted from the committed week-C artifact: R1's ladder is the pre-fix arm's "
                "own and was not recompiled here"
            ),
            "reproduces_the_committed_weekc_reading": reproduced,
        },
        "after": {
            "design": AFTER.name,
            "reach": after["reach"],
            "reach_stamp": after["stamp"],
            "dial": after_diag,
            "bars": after_bars,
            "R1": r1_after,
            "r2_diagnostics": r2_diag,
            "r2_p95_by_pair_kind": r2_split,
            "premise_accepted_disclosure": premise_bars,
        },
        "frontier": frontier,
        "seed_dispersion_disclosure": dispersion,
        "standing_caveat": (
            "nothing built on this generator line is a convincing model of history, the holdout "
            "is spent, and no appeal to held-out data is available"
        ),
    }
    # newline="\n" so the file on disk IS the file git stores (stage2_fit.py's own
    # note, and the reason commit 0c7aa7e exists): a sha256 quoted in a results
    # document has to be checkable, and a CRLF working copy under `* text=auto
    # eol=lf` is not the blob anyone else will see.
    RESULTS_PATH.write_text(
        json.dumps(weeka._round(payload), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"D-SP-10 -- conditioning reach. adopted design: {AFTER.name} (h={AFTER.match_horizon})")
    print(
        f"reach {before['reach']['conditioning_reach']:.4f} -> "
        f"{after['reach']['conditioning_reach']:.4f}   "
        f"selected-at-a-block-start {before['reach']['share_of_months_selected_for_their_quadrant']:.4f} -> "
        f"{after['reach']['share_of_months_selected_for_their_quadrant']:.4f}"
    )
    print(f"dial agreement {before_diag['agreement']:.4f} -> {after_diag['agreement']:.4f}")
    print(f"spine identity vs week A: max drift {identity['max_abs_drift']:.3e}")
    print()
    for code in ("A1", "A2", "R2"):
        b, a = before_bars[code], after_bars[code]
        print(f"{code}: {'PASS' if b['pass'] else 'FAIL'} -> {'PASS' if a['pass'] else 'FAIL'}")
    print(
        f"R1: {'PASS' if committed_bars['R1']['pass'] else 'FAIL'} -> "
        f"{'PASS' if r1_after['pass'] else 'FAIL'}"
    )
    print()
    print(f"wrote {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
