"""Seal D-SP-11's rulers. Run ONCE; commit the JSON in the SAME commit as this
script, per the platform's pre-registration invariant: thresholds AND the code
that judges them are hashed together **before any measurement run**.

COMMIT-ORDER, stated because it is the whole point: this commit lands **before
the era-rule engine is run and before A1R's ladder is compiled**. After it, the
new bar's rules, its judge, the anti-test results and the era rule's own
implementation can only change through the amendment log recorded inside
``docs/superpowers/specs/stage2-prereg-2.json`` -- never by editing a file.

Writes ``docs/superpowers/specs/stage2-prereg-2.json``:

- ``bars`` / ``parameters``: assembled by ``scripts/stage2_rulers.
  sealed_from_sources``, NOT retyped here -- the same function the anti-test
  sweeps judged with, so the numbers that were swept and the numbers that are
  sealed are provably the same object. ``S1`` seals a RULE rather than a number
  (its band is a function of the panel and of the sample size a world presents;
  see that function's docstring, and ruling SQ9 for the precedent), and the seal
  therefore carries the anchor's own sha256 plus a reference table of bands over a
  declared grid of sample sizes so any arm can be checked by hand.
- ``carried_records``: **both prior pre-registrations, carried whole.** The
  stage-2 seal and the v2 seal are loaded and their bar blocks, amendment logs
  and hash sets are recorded here, and both are hashed below. The twelve sealed
  bars keep being judged by their own code against their own thresholds; nothing
  in this seal re-grades or re-cuts one. **That is the charter's own condition:
  the rulers change only forward.**
- ``era_crossing_rule``: ruler 2 stated exactly, with its month-window semantics
  and the two properties that make it a faithfulness test rather than a
  relaxation.
- ``a1r_power_plan``: ruler 3's arithmetic in full -- the pilot it is computed
  from, alpha, power, the required sub-batches at the point estimate and at the
  upper bound on a six-draw standard deviation, the cap, the adopted size, the
  achieved power, and the seed rule.
- ``anti_test_record``: the three sweeps and two controls, per sweep and per
  control. A judge whose sweep was not monotone does not get sealed and neither
  does one whose control was broken; this script refuses to write in either case.
- ``amendments`` + ``amendment_procedure``: the machine-checked log.
  ``tests/test_stage2_rulers_seal.py`` enforces it.
- ``hashes``: sha256 over the working tree for every file that can change a
  D-SP-11 verdict -- the new judge, the composed engine that carries ruler 2, the
  anti-test script and its results, this script, **both prior seals**, and the
  D-SP-10 results artifact the power calculation reads its pilot out of.

Deterministic: no randomness drawn, no network, no wall clock -- ``sealed_at_utc``
comes from git HEAD's own commit metadata, the convention every seal in this
campaign has used. HEAD at the moment this runs is the anti-test commit.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_rulers as rulers  # noqa: E402

from ah.gen.bootstrap import campaign_source  # noqa: E402
from ah.gen.spine import panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
OUT_PATH = _SPECS / "stage2-prereg-2.json"
ANTITEST_PATH = _SPECS / "stage2-rulers-antitest-results.json"
STAGE2_SEAL_PATH = _SPECS / "stage2-prereg.json"
V2_SEAL_PATH = _SPECS / "spine-v2-prereg.json"

#: The stage-2 seal's own commit, and the reach round's. Recorded the way
#: ``spine02_seal.py`` established: a pre-registration and the tree state it was
#: measured against are different facts and both are worth keeping.
STAGE2_SEAL_COMMIT = "3b54a5814be3d5f3515cdfa4fc7e4d478b45134d"
REACH_MEASURED_STATE_COMMIT = "2a6ddd67f3a2f57000cd90c7ff395325b7d239a3"

#: Every file whose bytes can change a D-SP-11 verdict. Explicit, so a reader can
#: see the boundary of the seal and so the test can iterate it independently of
#: this script's own dict.
#:
#: ``scripts/stage2_worlds.py`` IS here, which is new for this campaign and
#: deliberate: ruler 2 is a rule about the ENGINE, its implementation lives in
#: that file, and a rule whose implementation can move without an amendment is
#: not sealed. ``spine_pilot_report.py`` and ``spine_pilot_b3.py`` are NOT here
#: for the reason ``stage2_seal.py`` gives: they sit inside the v2 seal, which is
#: hashed here, and ``tests/test_spine_v2_seal.py`` recomputes them every run.
HASHED_FILES: tuple[str, ...] = (
    "docs/superpowers/specs/stage2-prereg.json",
    "docs/superpowers/specs/spine-v2-prereg.json",
    "docs/superpowers/specs/spine-v2-anchors.json",
    "docs/superpowers/specs/stage2-reach-results.json",
    "docs/superpowers/specs/stage2-rulers-antitest-results.json",
    "scripts/stage2_rulers.py",
    "scripts/stage2_rulers_antitest.py",
    "scripts/stage2_rulers_seal.py",
    "scripts/stage2_worlds.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def build_seal() -> dict[str, Any]:
    """The sealed object. Pure apart from reading files, the panel and git."""
    sealed = rulers.sealed_from_sources()
    antitest = json.loads(ANTITEST_PATH.read_text(encoding="utf-8"))
    stage2 = json.loads(STAGE2_SEAL_PATH.read_text(encoding="utf-8"))
    v2 = json.loads(V2_SEAL_PATH.read_text(encoding="utf-8"))

    if not antitest["all_monotone"]:
        raise SystemExit(
            "REFUSING TO SEAL: these anti-test sweeps are not monotone in the effect the bar "
            f"claims to measure: {antitest['non_monotone_sweeps']}. Exam section 6.1 -- a judge "
            "whose pass rate does not increase in that effect does not get sealed."
        )
    if not antitest["all_controls_hold"]:
        raise SystemExit(
            "REFUSING TO SEAL: these anti-test controls are broken: "
            f"{antitest['broken_controls']}. D-SP-11's charter names the noise-inflation attack "
            "explicitly; its control is a condition on sealing, not a diagnostic."
        )

    jumps = rulers.panel_adjacent_jumps(panel_yoy(campaign_source()))
    committer_date = _git("log", "-1", "--format=%cI")
    head_sha = _git("rev-parse", "HEAD")

    return {
        "schema": "stage2-rulers-prereg-1",
        "sealed_at_utc": f"{committer_date} (as of HEAD commit {head_sha})",
        "purpose": (
            "D-SP-11's pre-registration: the new seam/texture bar S1, the conditional "
            "era-crossing rule, and the re-founded A1 -- their rules, their parameters and the "
            "sha256 of the code that judges them, hashed together BEFORE the era-rule engine is "
            "run and before A1R's ladder is compiled. Charter: "
            "governance/decision-register.md D-SP-11 (owner ruling 2026-08-18)"
        ),
        "charter": (
            "D-SP-11, 2026-08-18, 'all three': (1) a NEW seam/texture bar derived for a "
            "conditioned compiler, sealed fresh with anti-tests, the old R2 verdict standing in "
            "the record forever and reported beside it; (2) the CONDITIONAL era-crossing rule -- "
            "a seam may cross the inflation line only in a month where the spine itself crosses "
            "it, a faithfulness test and not a relaxation, precise rule sealed before use; "
            "(3) the inflation-hedge measurement A1 RE-FOUNDED, batch size computed from a power "
            "calculation at the engine's own measured margin, sealed, then re-measured. The "
            "rulers change only forward: no retroactive re-grading"
        ),
        "bars": sealed["bars"],
        "parameters": sealed["parameters"],
        "bar_codes": {
            "new": ["S1", "A1R"],
            "carried_and_still_reported": list(stage2["bar_codes"]["new"])
            + list(stage2["bar_codes"]["carried_byte_frozen"]),
        },
        "s1_derivation": {
            "principle": (
                "a seam should be statistically indistinguishable from an ordinary historical "
                "month-transition, so the bar asks 'can you FIND the seams?' rather than "
                "counting them"
            ),
            "statistic": (
                "the empirical quantiles of |change in trailing panel YoY| over the world's "
                "DISTINCT ordered adjacent row-pairs, split into seam pairs (the drawn row is "
                "not the panel's next row) and contiguous pairs"
            ),
            "anchor": (
                "history's own adjacent-month |dYoY| over the campaign panel. Its 95th "
                "percentile IS spine_pilot_report.judge_b2's sealed panel_p95_adjacent_yoy_pp, "
                "0.7433911963542538, so S1 stands on the exam's own anchor and does not open a "
                "second one"
            ),
            "anchor_n_jumps": int(jumps.size),
            "anchor_digest_sha256": rulers.anchor_digest(jumps),
            "anchor_quantiles": {
                # numpy's own quantile, the function the judge calls -- a hand
                # rolled order statistic here would print a number the bar never
                # compares anything to
                str(q): float(np.quantile(jumps, float(q)))
                for q in sealed["bars"]["S1_quantiles"]
            },
            "band_rule": (
                "the null-predictive band a sample of n historical transitions would put the "
                "quantile in: resample n values from the anchor by MOVING BLOCKS of "
                f"{sealed['parameters']['band_block_months']} months, take the quantile, repeat "
                f"{sealed['parameters']['band_draws']} times, keep the central "
                f"{sealed['parameters']['band_level']:.0%}. Deterministic in the sealed seed"
            ),
            "why_a_rule_and_not_a_number": (
                "the band is a function of the panel AND of the sample size the world presents, "
                "so a fixed number would be a band cut at one arbitrary n. Ruling SQ9's "
                "precedent: seal the selection rule when the value is not pinned. Everything "
                "that determines the band IS pinned here -- quantiles, level, draws, block "
                "length, seed, minimum tail count, de-duplication -- plus the anchor's own "
                "digest, so a moved panel is a loud failure"
            ),
            "house_rules": {
                "quantiles": (
                    "0.50 and 0.95. The median is the bar's ordinary-month anchor; the 95th is "
                    "its tail anchor and is NOT a new number -- it is the quantile R2's own "
                    "sealed bound is cut at. The 99th is excluded (800 anchor pairs means it "
                    "rests on eight order statistics) and so is the mean (|dYoY| is strongly "
                    "right-skewed, so its mean re-states the tail)"
                ),
                "band_level_and_draws": (
                    "95% at 2000 draws -- P2's own convention, reused rather than a third one "
                    "invented"
                ),
                "moving_blocks": (
                    "trailing 12-month YoY is a 12-month moving construct, so |dYoY| is strongly "
                    "serially dependent and an iid bootstrap would report a band far narrower "
                    "than history's own resolution. Blocks at the campaign's PRIMARY_BLOCK_"
                    "MONTHS. This is the CONSERVATIVE choice and conservative is the right "
                    "direction for a band that decides a FAIL"
                ),
                "deduplication": (
                    "judged on DISTINCT ordered row-pairs. A fifty-decade batch has 5,950 "
                    "adjacent pairs drawn from 800 distinct historical transitions, so counting "
                    "re-uses as independent evidence would cut the band below the panel's own "
                    "resolution and turn the bar into a test of repetition -- the FREQUENCY "
                    "question R2 already answers. The raw reading is published beside every "
                    "judged one"
                ),
                "min_tail_count": (
                    "a condition is judged only when at least 5 observations sit beyond the "
                    "quantile -- the standard expected-count rule. Below it a PASS would mean "
                    "'too few seams to tell'. A world with no seams passes the seam half "
                    "VACUOUSLY, which is correct: there is nothing to find"
                ),
                "two_sided": (
                    "all four conditions. Seams that are too big are findable; seams that are "
                    "unnaturally smooth are findable too, and a compiler that only joins "
                    "near-identical rows has stopped conditioning. The anti-test demonstrates "
                    "both edges bite"
                ),
            },
            "band_reference_table": rulers.band_reference_table(jumps, sealed),
            "relationship_to_R2": (
                "S1 judges SHAPE and is blind to seam FREQUENCY; R2 keeps judging both together "
                "and its verdicts are untouched. This is the separation D-SP-10's first "
                "stop-question asked for, offered as a new ruler rather than as a re-cut R2"
            ),
        },
        "era_crossing_rule": {
            "rule": (
                "a seam may land on a row whose era bucket differs from the row the block is "
                "standing on ONLY IF the spine's own inflation path crosses the era line "
                "between those same two months, AND only into the bucket the spine crosses into"
            ),
            "month_window_months": sealed["parameters"]["era_crossing_window_months"],
            "month_window_semantics": (
                "ZERO months wide. The licence is read at the month being drawn against the "
                "month the block is standing on -- the same two months the join connects. No "
                "tolerance, no lag, no look-ahead: a seam that crosses one month early or late "
                "is a seam that crosses at a month the story does not, which is the incoherence "
                "the era filter exists against. A +/- k window was available and NOT taken; it "
                "would need a tolerance nobody has anchored"
            ),
            "direction_clause": (
                "the row left must carry the spine's OLD bucket and the row entered its NEW "
                "one. Without it, 'the spine crossed this month' would license a crossing in "
                "either direction and a compiler could answer the story going hot by taking the "
                "flesh cool"
            ),
            "why_this_is_a_faithfulness_test_and_not_a_relaxation": (
                "the licence only ADDS candidates and never removes one, and it never widens "
                "the declared join_yoy_max_pp level bound. So it cannot lower conditioning "
                "reach, cannot empty a pool and cannot turn a joinable month into a refusal -- "
                "and every crossing it permits is one the world's own story makes"
            ),
            "implementation": "scripts/stage2_worlds.py::_era_crossing_licence (hashed below)",
            "audit": (
                "scripts/stage2_rulers.py::era_crossing_audit re-derives every bucket-changing "
                "seam from the compiled row tape rather than trusting the engine's counters. "
                "The one licensed exemption is the panel-edge forced re-entry (owner ruling "
                "2026-08-16), which draws UNFILTERED when nothing matches; it is COUNTED, never "
                "waived"
            ),
            "not_relaxed": (
                "the era-relaxed disclosure arm (D-SP-10's arm (e)) remains a disclosure and is "
                "NOT adopted. Dropping the era bucket outright is still an owner ruling"
            ),
        },
        "a1r_derivation": {
            "construct": (
                "A1's own statistic and A1's own carried containment band, POOLED across a batch "
                "of B sub-batches of "
                f"{sealed['parameters']['a1r_decades_per_sub_batch']} decades each. Pooling is "
                "the count-weighted identity over the SEALED judge's own per-sub-batch verdicts, "
                "which is algebra rather than a re-implementation and is tested against "
                "judge_a1 run on the genuinely concatenated batch"
            ),
            "decision_rule": (
                "A1R PASSES when (a) the two-sided 95% interval around the pooled difference "
                "lies ENTIRELY ABOVE ZERO, and (b) the pooled high-inflation spread sits inside "
                "A1's carried containment band. The interval's standard error is the spread of "
                "the sub-batches, which are independent by construction (disjoint seeds, "
                "disjoint streams), so it assumes nothing about months inside a decade"
            ),
            "also_reported_never_the_verdict": (
                "whether the interval excludes zero in EITHER direction -- a precise negative is "
                "a verdict and beats a coin flip, which is what the charter funded -- and "
                "whether it excludes history's own +3.4932826800308607"
            ),
            "seeds": {
                "rule": "base + A1R_SEED_STRIDE * k for k = 0 .. B-1",
                "base_seed": "stage2_fit.STAGE2_VERIFY_SEED (20260821)",
                "stride": rulers.A1R_SEED_STRIDE,
                "why_this_stride": (
                    "a NEW axis needs its own stride. 15,485,863 is prime, coprime with the "
                    "platform's 7919 and with spine_v2_fit.SPINE2_ATTEMPT_STRIDE, and larger "
                    "than every layer offset in ah.gen.spine.LAYER_OFFSETS and "
                    "stage2_fit.STAGE2_LAYER_OFFSETS -- so seed_i + offset_a == seed_j + "
                    "offset_b is impossible for i != j. Pairwise-distinct tapes are tested. "
                    "(The seed-stride collision this campaign already paid for once)"
                ),
                "sub_batch_zero_is_the_sealed_seed": True,
            },
            "runtime": (
                "0.71 s per fifty-decade batch on this machine with no institutional twin "
                "attached, measured before the plan was written. The adopted size is about six "
                "minutes of generation; the cap of "
                f"{sealed['a1r_power_plan']['cap_sub_batches']} sub-batches is about seven"
            ),
            "pilot_source": (
                "docs/superpowers/specs/stage2-reach-results.json, "
                "seed_dispersion_disclosure.after -- the six-seed disclosure D-SP-10 published, "
                "read out of the artifact rather than retyped. That artifact is hashed below"
            ),
        },
        "a1r_power_plan": sealed["a1r_power_plan"],
        "carried_records": {
            "rule": (
                "THE CHARTER'S OWN CONDITION: the rulers change only forward. Every prior "
                "verdict stands in the record, every prior threshold keeps its value, and the "
                "twelve sealed bars keep being judged by their own code. Both prior "
                "pre-registrations are carried here whole and hashed, so a D-SP-11 result can "
                "never quietly rest on a moved earlier threshold"
            ),
            "stage2": {
                "seal": "docs/superpowers/specs/stage2-prereg.json",
                "seal_commit": STAGE2_SEAL_COMMIT,
                "sealed_at_utc": stage2["sealed_at_utc"],
                "bar_codes": stage2["bar_codes"],
                "bars": stage2["bars"],
                "parameters": stage2["parameters"],
                "amendments": stage2["amendments"],
                "hashed_files": stage2["hashed_files"],
                "hashes": stage2["hashes"],
                "verdicts": [
                    "docs/superpowers/specs/2026-08-18-stage2-results.md",
                    "docs/superpowers/specs/2026-08-18-stage2-reach-results.md",
                ],
                "measured_state_commit": REACH_MEASURED_STATE_COMMIT,
            },
            "spine_v2": {
                "seal": "docs/superpowers/specs/spine-v2-prereg.json",
                "sealed_at_utc": v2["sealed_at_utc"],
                "bar_codes": v2["bar_codes"],
                "bars": v2["bars"],
                "parameters": v2["parameters"],
                "amendments": v2["amendments"],
                "hashed_files": v2["hashed_files"],
                "hashes": v2["hashes"],
                "verdicts": "docs/superpowers/specs/2026-08-17-spine-v2-results.md",
            },
            "prior_verdicts_are_frozen": True,
            "explicitly_not_re_graded": (
                "R2's two halves and A1's sealed single-batch verdict keep their words. S1 does "
                "not replace R2 and A1R does not replace A1; all four are reported side by side "
                "in every D-SP-11 report"
            ),
        },
        "anti_test_record": {
            "obligation": antitest["obligation"],
            "rule": antitest["rule"],
            "script": "scripts/stage2_rulers_antitest.py",
            "results": "docs/superpowers/specs/stage2-rulers-antitest-results.json",
            "readable": "docs/superpowers/specs/stage2-rulers-antitest-results.md",
            "all_monotone": bool(antitest["all_monotone"]),
            "all_controls_hold": bool(antitest["all_controls_hold"]),
            "per_sweep_monotone": {
                name: bool(s["monotone_non_decreasing"]) for name, s in antitest["sweeps"].items()
            },
            "per_sweep_pass_rate": {name: s["pass_rate"] for name, s in antitest["sweeps"].items()},
            "per_control_holds": {
                name: bool(c["holds"]) for name, c in antitest["controls"].items()
            },
            "reachability": (
                "S1 passes 12 of 12 at the fidelity point of both seam sweeps -- seam jumps "
                "drawn from history's own adjacent-jump distribution by construction. A bar no "
                "design can clear is not a bar and this is the evidence S1 is not one"
            ),
            "not_swept": antitest["not_swept"],
            "not_blind": antitest["not_blind"],
        },
        "declared_limitations": [
            "M1 -- S1 was NOT cut blind. D-SP-10's results document had already published this "
            "engine's seam and contiguous p95 (1.9143 and 0.6956 against a panel p95 of "
            "0.7434) before the bar was designed. The band is a pure function of the panel and "
            "of a sample size and no generated quantity enters its derivation, but a reader "
            "should know the designer knew the answer",
            "M2 -- S1's band is cut at the world's DISTINCT transition count and de-duplication "
            "is a judgement call. It removes a repetition artefact that would otherwise shrink "
            "the band far below the panel's own resolution; it also makes the bar blind to a "
            "world that uses one bad seam five hundred times. R2 sees that world and S1 does "
            "not, which is why both are reported",
            "M3 -- the moving-block bootstrap at 24 months is the campaign's primary block "
            "length, not a length fitted to |dYoY|'s own dependence. It is conservative (wider "
            "bands, more forgiving) and its adequacy is not measured",
            "M4 -- the era-crossing licence fires only where the spine crosses, and the spine "
            "crosses rarely. The rule can therefore buy only a bounded amount of reach and the "
            "residual gap stays what D-SP-10 measured it to be: the era filter, refusing to "
            "cross at every OTHER month",
            "M5 -- A1R's power calculation takes both its effect size and its variance from the "
            "same six-seed pilot. The variance is used at its upper 90% chi-square bound "
            "precisely because six draws pin it badly, but the EFFECT is used at its point "
            "estimate: if the engine's true margin is nearer zero than -0.97, the adopted batch "
            "is under-powered and the honest reading is 'cannot distinguish', not 'no effect'",
            "M6 -- A1R inherits every one of A1's own problems. D-SP-10's third stop-question "
            "stands untouched: history's high-inflation months pay +4.87 pp/yr on "
            "commodities-minus-bonds while the worst-10% all_down pool's high-inflation months "
            "pay -8.52, and A1 is a bar written on the whole panel read on a world drawn from "
            "the worst third of it. A precise verdict on a bar whose content is thin is still a "
            "verdict about a thin bar",
            "M7 -- nothing here reaches the private book. ER-14 stands",
            "M8 -- the standing caveat: nothing built on this generator line is a convincing "
            "model of history, the holdout is spent, and no appeal to held-out data is "
            "available to any result D-SP-11 produces",
        ],
        "amendments": [],
        "amendment_procedure": {
            "rule": (
                "after this commit, no file listed in hashes may change without an entry "
                "appended to `amendments` naming its path. Editing a hashed file and re-running "
                "this script is NOT an amendment -- it is a re-seal, and it erases the record "
                "this file exists to keep"
            ),
            "entry_keys": ["amendment_id", "date", "type", "rationale", "post_hoc", "paths"],
            "types": {
                "threshold_change": "a sealed pass/fail value or band RULE changes",
                "protocol_change": "how a metric is computed or judged changes (not just its "
                "value) -- e.g. the judge, the era rule's implementation, or the anti-test",
                "documentation": "a hashed document changes without any threshold or judging "
                "rule changing",
            },
            "machine_check": (
                "tests/test_stage2_rulers_seal.py recomputes every hash against the working "
                "tree and fails unless each mismatch is named by an amendment entry, so the log "
                "cannot be skipped by editing quietly"
            ),
            "post_hoc_flagging": (
                "every amendment is post-hoc-flagged in every report from its date forward, "
                "the platform's standing convention (ah.eval.prereg)"
            ),
        },
        "hashed_files": list(HASHED_FILES),
        "hashes": {rel: _sha256(_REPO_ROOT / rel) for rel in HASHED_FILES},
    }


def main() -> None:
    sealed = build_seal()
    OUT_PATH.write_text(
        json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUT_PATH}")
    print(f"sealed_at_utc = {sealed['sealed_at_utc']}")
    print(f"S1 quantiles = {sealed['bars']['S1_quantiles']} at {sealed['bars']['S1_band_level']}")
    print(
        f"S1 anchor    = {sealed['s1_derivation']['anchor_n_jumps']} jumps, digest "
        f"{sealed['s1_derivation']['anchor_digest_sha256'][:16]}..."
    )
    print(f"era window   = {sealed['parameters']['era_crossing_window_months']} months")
    plan = sealed["a1r_power_plan"]
    print(
        f"A1R          = {plan['sub_batches_adopted']} sub-batches x "
        f"{plan['decades_per_sub_batch']} decades = {plan['decades_adopted']} decades, "
        f"power {plan['achieved_power_at_the_adopted_size']:.4f}"
    )
    print(
        f"anti-tests monotone: {sealed['anti_test_record']['all_monotone']}  "
        f"controls hold: {sealed['anti_test_record']['all_controls_hold']}"
    )
    for rel, digest in sealed["hashes"].items():
        print(f"  {digest}  {rel}")


if __name__ == "__main__":
    main()
