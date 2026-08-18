"""D-SP-11: the sealed re-measurement -- twelve old bars, the new seam bar, A1 re-founded.

Charter: ``governance/decision-register.md`` **D-SP-11** (owner ruling
2026-08-18). Seal: ``docs/superpowers/specs/stage2-prereg-2.json``, written and
committed before this script was allowed to run.

**What moved and what did not.** The engine moved by exactly one rule: a seam may
now cross the inflation line at a month where the spine's own inflation path
crosses it (``stage2_worlds.ERA_CONDITIONAL_REACH``). Nothing else moved. The
twelve sealed bars are the sealed judges, imported by name and never
re-implemented, judged against thresholds neither this campaign nor D-SP-10
touched. The fitted engine is week A's frozen artifact and is re-checked
coefficient by coefficient before a batch is compiled. No file inside any of the
three pre-registrations was edited.

**What this script reports, in the order a reader needs it.**

1. **REACH** -- the three arms of the lineage on one batch: the pre-D-SP-10
   baseline, the D-SP-10 adopted engine, and the era-rule engine.
2. **THE ERA AUDIT** -- every bucket-changing seam re-derived from the compiled
   row tape (not from the engine's counters) and checked against the spine's own
   crossings. Under the rule the count of unlicensed crossings must be zero, and
   that is a stop rather than a line in a table.
3. **THE TWELVE SEALED BARS** -- before (D-SP-10) and after (the era rule), by
   the sealed judges. The eight pre-flesh bars come through
   ``stage2_weekc.spine_identity``, which **raises** unless each reproduces week
   A's committed value to 1e-12.
4. **S1** -- the new seam/texture bar, read on all three arms.
5. **A1R** -- A1 re-founded, at the sealed batch size, on both engines.
6. **THE OLD RULERS BESIDE THE NEW** -- A1's and R2's sealed verdicts are
   reported unchanged, because the charter says the rulers change only forward.

Run (from the worktree root, no network; about fifteen minutes):

    uv run python scripts/stage2_rulers_run.py
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
import stage2_reach as reach  # noqa: E402
import stage2_rulers as rulers  # noqa: E402
import stage2_weekc as weekc  # noqa: E402
import stage2_worlds as worlds  # noqa: E402
from spine_v2_report import judge_a1  # noqa: E402
from stage2_report import judge_carried_v2, judge_r2  # noqa: E402

from ah.gen.spine import fit_hazard, panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
RESULTS_PATH = SPECS_DIR / "stage2-rulers-results.json"
REACH_PATH = SPECS_DIR / "stage2-reach-results.json"
WEEKC_PATH = SPECS_DIR / "stage2-weekc-results.json"

#: The three arms of the lineage, oldest first. Named at every call site rather
#: than left to a module default, because the default has moved once already.
BASELINE = worlds.reach_design(worlds.REACH_BASELINE)
DSP10 = worlds.ADOPTED_REACH
DSP11 = worlds.ERA_CONDITIONAL_REACH


def _era_bucket(source: Any) -> np.ndarray:
    """The panel's era bucket, exactly as ``SpineBootstrap.sample_months`` cuts it."""
    yoy = panel_yoy(source)
    hazard = fit_hazard(source)
    return np.where(np.isnan(yoy), -1, (yoy > hazard.era_threshold_pp).astype(np.int64))


def _audit(fx: Any, arm: dict[str, Any], era_bucket: np.ndarray) -> dict[str, Any]:
    seasons = np.stack([np.asarray(d.season, dtype=np.int64) for d in arm["decades"]])
    return rulers.era_crossing_audit(
        arm["rows"], seasons, era_bucket, n_panel_rows=fx.source.n_rows
    )


def _s1(arm: dict[str, Any], yoy: np.ndarray, sealed: dict[str, Any]) -> dict[str, Any]:
    verdict = rulers.judge_s1(arm["rows"], yoy, sealed)
    verdict["self_referential_disclosure"] = rulers.self_referential_seam_check(
        arm["rows"], yoy, sealed
    )
    return verdict


def run_a1r(fx: Any, design: Any, sealed: dict[str, Any], *, label: str) -> dict[str, Any]:
    """``A1R``: the sealed judge on every sub-batch, then the pooled verdict.

    Each sub-batch is one ordinary fifty-decade A1 reading at its own declared
    seed; the pooled statistic is the count-weighted identity over those
    verdicts, which is algebra rather than a re-implementation and is tested
    against ``judge_a1`` on the concatenated batch. Sub-batch 0 is the sealed
    verification seed, so the old single-batch A1 is literally the first rung.
    """
    n = int(sealed["bars"]["A1R_sub_batches"])
    per_batch = int(sealed["parameters"]["a1r_decades_per_sub_batch"])
    seeds = rulers.a1r_seeds(n, int(weeka.STAGE2_VERIFY_SEED))
    started = time.time()
    verdicts: list[dict[str, Any]] = []
    with worlds.stage2_flesh(
        fx.frozen, premise_mode=worlds.PREMISE_UNCONDITIONAL, design=design
    ) as run:
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
    verdict["seeds"] = {
        "base": int(weeka.STAGE2_VERIFY_SEED),
        "stride": rulers.A1R_SEED_STRIDE,
        "n": n,
        "first": seeds[:3],
        "last": seeds[-3:],
        "sub_batch_zero_is_the_sealed_seed": seeds[0] == int(weeka.STAGE2_VERIFY_SEED),
    }
    verdict["per_sub_batch_difference_pp"] = values
    # NOT in the artifact: the wall clock. A results file that carries one cannot
    # make a determinism claim -- the first pair of runs of this script differed in
    # exactly two keys, both of them elapsed seconds, and nothing else. It is
    # printed instead.
    print(f"  [{label}] {n} sub-batches in {time.time() - started:.0f}s")
    return verdict


def stream_hygiene(sealed: dict[str, Any]) -> dict[str, Any]:
    """The A1R ladder's own seed check -- the collision this campaign paid for once.

    Two claims, checked separately because they cost differently. The **whole**
    ladder's per-rung block and hazard tapes are drawn and compared pairwise --
    514 rungs, cheap. The **stage-2 attempt-stream disjointness** is then checked
    on a declared subsample of the first thirty rungs, because the full check is
    514 x 6 x 200 tapes and the property it establishes is arithmetic in the
    stride rather than a fact about any particular rung.
    """
    from math import gcd

    from ah.gen.spine import LAYER_OFFSETS

    n = int(sealed["bars"]["A1R_sub_batches"])
    seeds = rulers.a1r_seeds(n, int(weeka.STAGE2_VERIFY_SEED))

    def tape(seed: int) -> tuple[float, ...]:
        rng = np.random.Generator(np.random.PCG64(int(seed)))
        return tuple(float(x) for x in rng.random(8))

    rung_tapes = {tape(s + LAYER_OFFSETS[layer]) for s in seeds for layer in ("blocks", "hazard")}
    if len(rung_tapes) != 2 * n:
        raise weeka.FitError("two A1R rungs share a block or hazard tape")
    subsample = 30
    worlds.assert_flesh_streams_distinct(seeds[:subsample], n_paths=8)
    return {
        "n_rungs": n,
        "stride": rulers.A1R_SEED_STRIDE,
        "rung_tapes_pairwise_distinct": True,
        "coprime_with_the_platform_stride": gcd(rulers.A1R_SEED_STRIDE, 7919) == 1,
        "coprime_with_the_attempt_stride": gcd(rulers.A1R_SEED_STRIDE, 32452843) == 1,
        "larger_than_every_layer_offset": max(
            max(LAYER_OFFSETS.values()), max(weeka.STAGE2_LAYER_OFFSETS.values())
        )
        < rulers.A1R_SEED_STRIDE,
        "attempt_stream_disjointness_checked_on_the_first_n_rungs": subsample,
        "note": (
            "the stride is larger than every layer offset, so seed_i + offset_a == seed_j + "
            "offset_b is impossible for i != j -- the pairwise check is the demonstration and "
            "the arithmetic is the reason"
        ),
    }


def main() -> int:
    sealed = rulers.load_sealed()
    fx = reach._Fixtures()
    seed = int(weeka.STAGE2_VERIFY_SEED)
    yoy = panel_yoy(fx.source)
    era_bucket = _era_bucket(fx.source)
    committed_reach = json.loads(REACH_PATH.read_text(encoding="utf-8"))
    committed_weekc = json.loads(WEEKC_PATH.read_text(encoding="utf-8"))

    hygiene = stream_hygiene(sealed)

    # ------------------------------------------------------------------ #
    # the three arms of the lineage, on one batch
    # ------------------------------------------------------------------ #
    arms = {
        "week-C baseline (pre-D-SP-10)": (BASELINE, reach.compile_arm(fx, BASELINE, seed)),
        "D-SP-10 adopted": (DSP10, reach.compile_arm(fx, DSP10, seed)),
        "D-SP-11 +era-conditional crossing": (DSP11, reach.compile_arm(fx, DSP11, seed)),
    }
    lineage: dict[str, Any] = {}
    for label, (design, arm) in arms.items():
        diag = weekc.a_bar_diagnostics(arm["decades"], arm["rows"], fx.assets, fx.v2, fx.source)
        audit = _audit(fx, arm, era_bucket)
        lineage[label] = {
            "design": design.name,
            "reach": arm["reach"],
            "reach_stamp": arm["stamp"],
            "dial_agreement": diag["agreement"],
            "dial_agreement_if_independent": diag[
                "agreement_expected_if_the_two_dials_were_independent"
            ],
            "era_crossing_audit": audit,
            "seams": int(np.sum(arm["rows"][:, 1:] != arm["rows"][:, :-1] + 1)),
            "forced_reentries": int(arm["ens"].meta.conditioning["forced_reentries"]),
            "unfiltered_reentries": int(arm["ens"].meta.conditioning["unfiltered_reentries"]),
        }
        if not audit["holds"]:
            raise weeka.FitError(
                f"the {label} arm has {audit['unlicensed_crossing_seams']} bucket-changing "
                "seam(s) at months where the spine does not cross. The era-crossing rule is a "
                "rule and this is a stop, not a diagnostic"
            )

    before, after = arms["D-SP-10 adopted"][1], arms["D-SP-11 +era-conditional crossing"][1]

    # ------------------------------------------------------------------ #
    # the twelve sealed bars, before and after, by the sealed judges
    # ------------------------------------------------------------------ #
    identity = weekc.spine_identity(
        after["decades"], after["batch"], fx.frozen.system, fx.sealed, fx.v2
    )
    scoreboard: dict[str, Any] = {}
    for label, arm in (("before", before), ("after", after)):
        carried = judge_carried_v2(arm["batch"], fx.v2)
        r2 = judge_r2(arm["ens"], fx.source, fx.v2)
        scoreboard[label] = {
            "A1": weekc._bar_row("A1", carried["A1"]),
            "A2": weekc._bar_row("A2", carried["A2"]),
            "R2": weekc._bar_row("R2", r2),
        }
    r1 = {
        label: reach.run_r1(fx, design) for label, design in (("before", DSP10), ("after", DSP11))
    }

    # ------------------------------------------------------------------ #
    # the NEW bars
    # ------------------------------------------------------------------ #
    s1 = {label: _s1(arm, yoy, sealed) for label, (_d, arm) in arms.items()}
    a1r = {
        "before (D-SP-10 engine)": run_a1r(fx, DSP10, sealed, label="before"),
        "after (D-SP-11 engine)": run_a1r(fx, DSP11, sealed, label="after"),
    }

    payload: dict[str, Any] = {
        "schema": "stage2-rulers-results-1",
        "purpose": (
            "D-SP-11: the three ruler decisions measured. The twelve sealed bars re-run "
            "unchanged, the NEW seam/texture bar S1 read for the first time, A1 re-founded at "
            "a computed batch size, and the conditional era-crossing rule's reach measured and "
            "audited. The old rulers keep reporting beside the new ones"
        ),
        "charter": "governance/decision-register.md D-SP-11 (owner ruling 2026-08-18)",
        "seal": "docs/superpowers/specs/stage2-prereg-2.json",
        "carried_seals": [
            "docs/superpowers/specs/stage2-prereg.json",
            "docs/superpowers/specs/spine-v2-prereg.json",
        ],
        "engine": (
            "docs/superpowers/specs/stage2-fitted-params.json (FROZEN INPUT -- nothing refitted)"
        ),
        "src_untouched": True,
        "frozen_engine_agreement": fx.frozen.agreement,
        "spine_identity_after_the_era_rule": identity,
        "a1r_stream_hygiene": hygiene,
        "lineage": lineage,
        "twelve_sealed_bars": {
            "note": (
                "the eight pre-flesh bars are bit-unchanged by construction and that is checked, "
                "not assumed: stage2_weekc.spine_identity RAISES above 1e-12. Their values are "
                "in spine_identity_after_the_era_rule"
            ),
            "spine_bars": identity,
            "flesh_bars": scoreboard,
            "R1": r1,
            "weekC_committed": {
                row["bar"]: row
                for row in committed_weekc["bars"]
                if row["bar"] in ("A1", "A2", "R1", "R2")
            },
            "dsp10_committed": {
                "before": committed_reach["before"]["bars"],
                "after": committed_reach["after"]["bars"],
            },
        },
        "S1": s1,
        "A1R": a1r,
        "the_old_rulers_stand": (
            "A1's sealed single-batch verdict and R2's two halves are reported above exactly as "
            "the sealed judges return them, on both engines. S1 does not replace R2 and A1R does "
            "not replace A1 -- D-SP-11's charter says the rulers change only forward, and this "
            "artifact carries all four"
        ),
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
    print("D-SP-11 -- the three rulers, measured.")
    for label, block in lineage.items():
        print(
            f"  {label:36s} reach {block['reach']['conditioning_reach']:.4f}  "
            f"agreement {block['dial_agreement']:.4f}  seams {block['seams']:5d}  "
            f"crossing-seams {block['era_crossing_audit']['crossing_seams']:4d} "
            f"(unlicensed {block['era_crossing_audit']['unlicensed_crossing_seams']})"
        )
    print()
    print(f"spine identity vs week A: max drift {identity['max_abs_drift']:.3e}")
    for code in ("A1", "A2", "R2"):
        b, a = scoreboard["before"][code], scoreboard["after"][code]
        print(f"  {code}: {'PASS' if b['pass'] else 'FAIL'} -> {'PASS' if a['pass'] else 'FAIL'}")
    print(
        f"  R1: {'PASS' if r1['before']['pass'] else 'FAIL'} -> "
        f"{'PASS' if r1['after']['pass'] else 'FAIL'}"
    )
    print()
    for label, verdict in s1.items():
        print(
            f"  S1 [{label:36s}] {'PASS' if verdict['pass'] else 'FAIL'}  "
            f"texture {'PASS' if verdict['texture_pass'] else 'FAIL'}  "
            f"seams {'PASS' if verdict['seam_pass'] else 'FAIL'}  "
            f"margin {verdict['value']:+.3f}"
        )
    print()
    for label, verdict in a1r.items():
        ci = verdict["confidence_interval"]
        print(
            f"  A1R [{label:24s}] {'PASS' if verdict['pass'] else 'FAIL'}  "
            f"{verdict['pooled_difference_pp']:+.4f} pp  CI [{ci[0]:+.4f}, {ci[1]:+.4f}]  "
            f"excludes zero: {verdict['excludes_zero']}  "
            f"excludes history: {verdict['excludes_history']}"
        )
    print()
    print(f"wrote {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
