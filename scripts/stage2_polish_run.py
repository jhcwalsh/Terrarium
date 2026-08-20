"""D-SP-12 -- the polish engine, and the whole sealed exam re-read on it.

Charter: ``governance/decision-register.md`` **D-SP-12** (owner ruling
2026-08-19). This is the round's **run entry point**: the one place where the
polish engine is configured, so that "which engine was measured" is a single
readable object rather than a set of arguments repeated at call sites.

The engine, stated once:

* **reach design** -- :data:`stage2_polish.POLISH_REACH`, i.e.
  ``stage2_worlds.ERA_CONDITIONAL_REACH``: D-SP-10's path-matched entries, the
  mid-block divergence break and the anticipating re-entry, **plus the
  conditional era-crossing rule, which this round ADOPTS** (change 2);
* **join selection** -- :data:`stage2_polish.SELECTION_MIN_GAP`: among the
  era-safe candidates, the smallest inflation gap at the seam wins, earliest
  panel row breaking ties (change 1);
* **slow climate** -- the L1 recalibration (change 3), read from
  ``docs/superpowers/specs/stage2-fitted-params-2.json`` rather than retyped.

WHAT THIS SCRIPT REPORTS, IN THE ORDER A READER NEEDS IT
--------------------------------------------------------
1. **THE LINEAGE** -- reach, agreement and the licence audit on four arms: the
   D-SP-11 engine (the round's "before"), each change on its own, and the two
   together (the round's "after"). The licence audit is live on every one of
   them and an unlicensed crossing is a **stop**: the join-selection change
   alters which candidate is taken at a crossing month, so D-SP-11's
   104-of-104 reading is retaken rather than inherited.
2. **THE BEFORE ARM REPRODUCES THE COMMITTED RECORD** -- the D-SP-11 arm is
   recompiled here and every flesh reading is checked against
   ``stage2-rulers-results.json`` at 1e-12. A drift is a stop, because the
   before/after comparison would otherwise be meaningless.
3. **THE TWELVE SEALED BARS**, before and after, by the sealed judges imported
   by name. The eight pre-flesh bars come through ``stage2_weekc.spine_identity``
   on every arm whose slow climate is **not** recalibrated -- where it still
   raises above 1e-12 -- and are re-judged and reported on the arms where it is,
   because change 3 moves the spine on purpose and a check that forbids that
   would be a check against the round.
4. **S1** -- the round's headline. Are the seams findable?
5. **A1R** -- 514 sub-batches of fifty decades on the polished engine; the
   D-SP-11 reading is carried from its committed artifact rather than recomputed,
   because that artifact is the record and re-running it would only re-derive it.

Run (from the worktree root, no network; about fifteen minutes):

    uv run python scripts/stage2_polish_run.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_fit as weeka  # noqa: E402
import stage2_polish as polish  # noqa: E402
import stage2_reach as reach  # noqa: E402
import stage2_rulers as rulers  # noqa: E402
import stage2_weekc as weekc  # noqa: E402
import stage2_worlds as worlds  # noqa: E402
from spine_v2_report import judge_a1  # noqa: E402

from ah.gen.spine import fit_hazard, panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
RESULTS_PATH = SPECS_DIR / "stage2-polish-results.json"
RULERS_PATH = SPECS_DIR / "stage2-rulers-results.json"
FROZEN_PARAMS_PATH = SPECS_DIR / "stage2-fitted-params.json"

#: The lineage, oldest first. Named at every call site rather than left to a
#: module default, because the default has moved twice already.
DSP11 = worlds.ERA_CONDITIONAL_REACH
POLISH = polish.POLISH_REACH

BEFORE = "D-SP-11 (era rule, platform join selection)"
JOIN_ONLY = "+ join selection by inflation distance"
L1_ONLY = "+ L1 dispersion recalibration"
POLISHED = "POLISHED (both changes)"
GAP_ONLY = "disclosure: gap-only selection (never adopted)"


def adopted_calibration() -> polish.L1Calibration:
    """Change 3's factors, read from the artifact that derived them."""
    doc = json.loads(polish.POLISH_PARAMS_PATH.read_text(encoding="utf-8"))
    factors = doc["l1_dispersion_calibration"]["adopted_factors"]
    return polish.L1Calibration(
        sigma_pi=float(factors["sigma_pi"]), sigma_r=float(factors["sigma_r"])
    )


def panel_era_bucket(source: Any) -> np.ndarray:
    """The panel's era bucket, exactly as ``SpineBootstrap.sample_months`` cuts it."""
    yoy = panel_yoy(source)
    hazard = fit_hazard(source)
    return np.where(np.isnan(yoy), -1, (yoy > hazard.era_threshold_pp).astype(np.int64))


def compile_and_audit(
    fx: Any,
    design: Any,
    seed: int,
    era_bucket: np.ndarray,
    *,
    arm: str,
    selection: str = polish.SELECTION_MIN_GAP,
    calibration: polish.L1Calibration | None = None,
) -> dict[str, Any]:
    """One arm of the polish engine, compiled and licence-audited."""
    with polish.polish_engine(selection=selection, calibration=calibration):
        armed = reach.compile_arm(fx, design, seed)
    seasons = np.stack([np.asarray(d.season, dtype=np.int64) for d in armed["decades"]])
    audit = rulers.era_crossing_audit(
        armed["rows"], seasons, era_bucket, n_panel_rows=fx.source.n_rows
    )
    armed["era_crossing_audit"] = polish.assert_licensed_crossings(audit, arm=arm)
    armed["selection"] = selection
    armed["calibration"] = (calibration or polish.L1_UNIT).factors
    return armed


def seam_jump_composition(
    rows: np.ndarray, yoy: np.ndarray, era_bucket: np.ndarray
) -> dict[str, Any]:
    """``S1``'s seam half, split by whether the seam crossed the era line.

    The one question the round has to answer about its own change 2: the
    conditional era-crossing rule licenses seams that move trailing inflation
    ACROSS the era threshold, and such a seam is a large-|dYoY| seam almost by
    construction. If the seam tail that keeps ``S1`` failing is made of licensed
    crossings, then changes 1 and 2 are pulling against each other and that is a
    frontier to map rather than a defect to tune past. Counted on the distinct
    ordered row-pairs ``S1`` itself judges.
    """
    rows = np.asarray(rows, dtype=np.int64)
    a, b = rows[:, :-1].ravel(), rows[:, 1:].ravel()
    pairs = np.unique(np.stack([a, b], axis=1), axis=0)
    pa, pb = pairs[:, 0], pairs[:, 1]
    seam = pb != pa + 1
    jump = np.abs(yoy[pb] - yoy[pa])[seam]
    crossed = (era_bucket[pb] != era_bucket[pa])[seam]
    out: dict[str, Any] = {"distinct_seam_pairs": int(seam.sum())}
    for name, mask in (("era_crossing", crossed), ("same_bucket", ~crossed)):
        values = jump[mask]
        out[name] = {
            "n": int(values.size),
            "share_of_seam_pairs": float(values.size / max(int(seam.sum()), 1)),
            "median": float(np.median(values)) if values.size else None,
            "p95": float(np.quantile(values, 0.95)) if values.size else None,
            "max": float(values.max()) if values.size else None,
        }
    if jump.size:
        cut = float(np.quantile(jump, 0.95))
        tail = jump >= cut
        out["above_the_seam_p95"] = {
            "cut_pp": cut,
            "n": int(tail.sum()),
            "share_that_crossed_the_era_line": float(crossed[tail].mean()),
        }
    return out


def spine_bars(fx: Any, arm: dict[str, Any], *, recalibrated: bool) -> dict[str, Any]:
    """The eight pre-flesh bars, by the sealed judges.

    On an arm whose slow climate is **not** recalibrated the week-C identity
    check still applies and still raises: a compiler change cannot move a bar
    cut from the spine, and that is checked rather than assumed. On a
    recalibrated arm it cannot apply -- change 3 moves the spine deliberately --
    so the eight are re-judged and reported beside week A's committed values,
    with the drift printed rather than barred.
    """
    if not recalibrated:
        identity = weekc.spine_identity(
            arm["decades"], arm["batch"], fx.frozen.system, fx.sealed, fx.v2
        )
        identity["identity_asserted"] = True
        return identity
    verdicts = weeka.judge_batch(arm["decades"], fx.frozen.system, fx.sealed, fx.v2)
    committed = {
        row["bar"]: row
        for row in json.loads(FROZEN_PARAMS_PATH.read_text(encoding="utf-8"))["verification"][
            "bars"
        ]
        if row.get("measured")
    }
    rows = []
    for code in weeka.PRE_FLESH_BARS:
        got = float(verdicts[code]["value"])
        want = float(committed[code]["value"])
        rows.append(
            {
                "bar": code,
                "week_a": want,
                "polish_reread": got,
                "abs_drift": abs(got - want),
                "pass": bool(verdicts[code]["pass"]),
                "week_a_pass": bool(committed[code]["pass"]),
            }
        )
    return {
        "identity_asserted": False,
        "why_not": (
            "change 3 recalibrates L1's two level-carrying volatilities, so the spine moves BY "
            "DESIGN. stage2_weekc.spine_identity raises above 1e-12 and would therefore forbid "
            "the round's own third change; the eight bars are re-judged and reported instead"
        ),
        "max_abs_drift": max(r["abs_drift"] for r in rows),
        "bars": rows,
    }


def flesh_bars(fx: Any, arm: dict[str, Any]) -> dict[str, Any]:
    """``A1``, ``A2``, ``R2`` and both ``A2`` halves, by the sealed judges."""
    block = reach.bars_block(fx, arm)
    verdict = block.pop("_r2_verdict")
    block["_R2_value"] = verdict["value"]
    block["_R2_verdict_for_diagnostics"] = verdict
    return block


def run_r1(fx: Any, design: Any, *, selection: str, calibration: Any) -> dict[str, Any]:
    """``R1``'s byte-frozen b3 ladder -- attempted, and its failure recorded.

    The ladder does not run on this repository state and the reason is outside
    this round: ``ah.play.PRIVATE_ASSETS`` gained ``infra`` (er14-04b/05, merged
    into main on 2026-08-19) while ``scripts/spine_pilot_b3.py`` -- hashed by
    ``spine-v2-prereg.json``, and therefore uneditable under this charter --
    still declares its book over ``pe``/``pc``/``re`` only, so
    ``ah.play._build_portfolio`` raises ``KeyError: 'infra'``. Fixing the
    harness would edit a sealed file; adding ``infra`` to the book would change
    a construct. Both are forbidden here, so the attempt is made, the exception
    is recorded verbatim, and ``R1``'s D-SP-11 verdict is carried.
    """
    try:
        with polish.polish_engine(selection=selection, calibration=calibration):
            return {"measured": True, **reach.run_r1(fx, design)}
    except Exception as exc:
        return {
            "measured": False,
            "bar": "R1",
            "error": f"{type(exc).__name__}: {exc}",
            "diagnosis": (
                "ah.play.PRIVATE_ASSETS gained 'infra' (er14-04b/05, merged into main "
                "2026-08-19); scripts/spine_pilot_b3._PRIVATE_BASE still declares the book over "
                "pe/pc/re, so ah.play._build_portfolio raises on targets['infra']. The b3 script "
                "is hashed by spine-v2-prereg.json and cannot be edited under this charter, and "
                "changing the declared book would be a construct change, which this charter also "
                "forbids. R1 is therefore NOT RE-MEASURED this round"
            ),
        }


def run_a1r(
    fx: Any, design: Any, sealed: dict[str, Any], *, label: str, selection: str, calibration: Any
) -> dict[str, Any]:
    """``A1R`` on one engine: the sealed judge per sub-batch, then the pooled verdict.

    ``stage2_rulers_run.run_a1r``'s own structure, with the polish substitutions
    installed around the compilation. The pooling and the verdict are the sealed
    module's and are not re-implemented here.
    """
    n = int(sealed["bars"]["A1R_sub_batches"])
    per_batch = int(sealed["parameters"]["a1r_decades_per_sub_batch"])
    seeds = rulers.a1r_seeds(n, int(weeka.STAGE2_VERIFY_SEED))
    started = time.time()
    verdicts: list[dict[str, Any]] = []
    with (
        polish.polish_engine(selection=selection, calibration=calibration),
        worlds.stage2_flesh(
            fx.frozen, premise_mode=worlds.PREMISE_UNCONDITIONAL, design=design
        ) as run,
    ):
        for k, seed in enumerate(seeds):
            ens = worlds.compile_world(fx.world, per_batch, int(seed))
            batch = weekc.fleshed_batch(
                run.decades[int(seed)], np.asarray(ens.row_indices), fx.assets
            )
            verdicts.append(judge_a1(batch, dict(fx.v2)))
            run.decades.pop(int(seed), None)
            if (k + 1) % 100 == 0:
                print(f"  [{label}] {k + 1}/{n} sub-batches, {time.time() - started:.0f}s")
    pooled = rulers.pool_a1_verdicts(verdicts)
    values = [float(v["difference_pp"]) for v in verdicts]
    verdict = rulers.judge_a1_refounded(pooled, values, sealed)
    verdict["arm"] = label
    verdict["per_sub_batch_difference_pp"] = values
    # NOT in the artifact: the wall clock (D-SP-11's own determinism incident).
    print(f"  [{label}] {n} sub-batches in {time.time() - started:.0f}s")
    return verdict


def reproduces_the_committed_rulers_reading(
    before_bars: dict[str, Any], committed: dict[str, Any]
) -> dict[str, Any]:
    """The before arm must be the committed D-SP-11 arm, field by field."""
    out: dict[str, Any] = {}
    for code in ("A1", "A2", "R2"):
        want, got = committed["twelve_sealed_bars"]["flesh_bars"]["after"][code], before_bars[code]
        keys = [k for k in want if isinstance(want[k], float)]
        drift = max((abs(float(got[k]) - float(want[k])) for k in keys), default=0.0)
        out[code] = {
            "max_abs_drift_vs_committed": drift,
            "pass_matches": got["pass"] == want["pass"],
        }
        if drift > 1e-12 or got["pass"] != want["pass"]:
            raise weeka.FitError(
                f"the before arm no longer reproduces the committed D-SP-11 reading for {code} "
                f"(drift {drift:.3e}); the before/after comparison would be meaningless"
            )
    return out


def main() -> int:
    fx = reach._Fixtures()
    sealed = rulers.load_sealed()
    seed = int(weeka.STAGE2_VERIFY_SEED)
    yoy = panel_yoy(fx.source)
    era_bucket = panel_era_bucket(fx.source)
    calibration = adopted_calibration()
    committed_rulers = json.loads(RULERS_PATH.read_text(encoding="utf-8"))

    arms_spec = (
        (BEFORE, DSP11, polish.SELECTION_PLATFORM, None),
        (JOIN_ONLY, DSP11, polish.SELECTION_MIN_GAP, None),
        (L1_ONLY, DSP11, polish.SELECTION_PLATFORM, calibration),
        (POLISHED, POLISH, polish.SELECTION_MIN_GAP, calibration),
        (GAP_ONLY, POLISH, polish.SELECTION_GAP_ONLY, calibration),
    )

    arms: dict[str, dict[str, Any]] = {}
    lineage: dict[str, Any] = {}
    for label, design, selection, cal in arms_spec:
        arm = compile_and_audit(
            fx, design, seed, era_bucket, arm=label, selection=selection, calibration=cal
        )
        diag = weekc.a_bar_diagnostics(arm["decades"], arm["rows"], fx.assets, fx.v2, fx.source)
        arms[label] = arm
        lineage[label] = {
            "design": design.name,
            "join_selection": selection,
            "l1_calibration": arm["calibration"],
            "reach": arm["reach"],
            "reach_stamp": arm["stamp"],
            "dial_agreement": diag["agreement"],
            "dial_agreement_if_independent": diag[
                "agreement_expected_if_the_two_dials_were_independent"
            ],
            "era_crossing_audit": arm["era_crossing_audit"],
            "seams": int(np.sum(arm["rows"][:, 1:] != arm["rows"][:, :-1] + 1)),
            "forced_reentries": int(arm["ens"].meta.conditioning["forced_reentries"]),
            "unfiltered_reentries": int(arm["ens"].meta.conditioning["unfiltered_reentries"]),
        }
        print(
            f"  {label:48s} reach {arm['reach']['conditioning_reach']:.4f}  "
            f"agree {diag['agreement']:.4f}  seams {lineage[label]['seams']:5d}  "
            f"crossings {arm['era_crossing_audit']['crossing_seams']:4d} "
            f"(unlicensed {arm['era_crossing_audit']['unlicensed_crossing_seams']})"
        )

    scoreboard: dict[str, Any] = {}
    for label, _design, _selection, cal in arms_spec:
        block = flesh_bars(fx, arms[label])
        scoreboard[label] = {
            "spine": spine_bars(fx, arms[label], recalibrated=cal is not None),
            "A1": block["A1"],
            "A2": block["A2"],
            "R2": block["R2"],
            "R2_value": block["_R2_value"],
            "A1_on_the_drawn_months_inflation": block["A1_on_the_drawn_months_inflation"],
            "A2_on_the_drawn_months_inflation": block["A2_on_the_drawn_months_inflation"],
            "S1": rulers.judge_s1(arms[label]["rows"], yoy, sealed),
            "S1_seam_composition": seam_jump_composition(arms[label]["rows"], yoy, era_bucket),
            "R2_failure_characterisation": weekc.r2_diagnostics(
                arms[label]["ens"], fx.source, block["_R2_verdict_for_diagnostics"]
            ),
        }
    reproduced = reproduces_the_committed_rulers_reading(scoreboard[BEFORE], committed_rulers)

    r1 = run_r1(fx, POLISH, selection=polish.SELECTION_MIN_GAP, calibration=calibration)
    a1r_after = run_a1r(
        fx,
        POLISH,
        sealed,
        label="polished",
        selection=polish.SELECTION_MIN_GAP,
        calibration=calibration,
    )

    payload: dict[str, Any] = {
        "schema": "stage2-polish-results-1",
        "purpose": (
            "D-SP-12: three improvements to the coupled engine -- join selection by inflation "
            "distance, the conditional era-crossing rule adopted, and the slow climate's "
            "dispersion recalibrated -- and the whole sealed exam re-read on the result. The "
            "exam does not move; the engine does"
        ),
        "charter": "governance/decision-register.md D-SP-12 (owner ruling 2026-08-19)",
        "seals": [
            "docs/superpowers/specs/stage2-prereg-2.json",
            "docs/superpowers/specs/stage2-prereg.json",
            "docs/superpowers/specs/spine-v2-prereg.json",
        ],
        "sealed_files_edited": [],
        "amendments_added": [],
        "src_untouched": True,
        "engine": {
            "reach_design": POLISH.name,
            "era_conditional_crossing": bool(POLISH.era_conditional_crossing),
            "join_selection": polish.SELECTION_MIN_GAP,
            "l1_calibration": calibration.factors,
            "l1_calibration_artifact": "docs/superpowers/specs/stage2-fitted-params-2.json",
            "stage2_coefficients": (
                "docs/superpowers/specs/stage2-fitted-params.json (FROZEN INPUT -- all 42 "
                "re-checked before any batch is compiled; nothing refitted)"
            ),
        },
        "frozen_engine_agreement": fx.frozen.agreement,
        "before_reproduces_the_committed_dsp11_reading": reproduced,
        "lineage": lineage,
        "scoreboard": scoreboard,
        "R1": r1,
        "A1R": {
            "polished": a1r_after,
            "before (D-SP-11, carried from the committed artifact)": committed_rulers["A1R"][
                "after (D-SP-11 engine)"
            ],
            "carry_note": (
                "the D-SP-11 reading is quoted from stage2-rulers-results.json rather than "
                "recomputed: that artifact is the record, it regenerates byte-identically, and "
                "re-running 25,700 decades to re-derive a committed number buys nothing"
            ),
        },
        "standing_caveat": (
            "nothing built on this generator line is a convincing model of history, the holdout "
            "is spent, and no appeal to held-out data is available"
        ),
    }
    RESULTS_PATH.write_text(
        json.dumps(weeka._round(payload), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print()
    for label in (BEFORE, POLISHED):
        block = scoreboard[label]
        print(f"  {label}")
        print(
            "    spine: "
            + " ".join(f"{r['bar']}={'P' if r['pass'] else 'F'}" for r in block["spine"]["bars"])
        )
        print(
            f"    A1 {'PASS' if block['A1']['pass'] else 'FAIL'} "
            f"({block['A1']['value_difference_pp']:+.4f})  "
            f"A2 {'PASS' if block['A2']['pass'] else 'FAIL'}  "
            f"R2 {'PASS' if block['R2']['pass'] else 'FAIL'} "
            f"({block['R2_value']['max_join_jump_pp']:.4f}/"
            f"{block['R2_value']['p95_adjacent_yoy_pp']:.4f})  "
            f"S1 {'PASS' if block['S1']['pass'] else 'FAIL'} ({block['S1']['value']:+.4f})"
        )
    ci = a1r_after["confidence_interval"]
    print(
        f"  A1R polished: {'PASS' if a1r_after['pass'] else 'FAIL'} "
        f"{a1r_after['pooled_difference_pp']:+.4f} pp CI [{ci[0]:+.4f}, {ci[1]:+.4f}]"
    )
    print(f"  R1: {'measured' if r1['measured'] else 'NOT MEASURED -- ' + r1['error']}")
    print(f"wrote {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
