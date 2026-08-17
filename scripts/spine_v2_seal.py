"""Seal the spine v2, stage 1 exam. Run ONCE; commit the JSON in the SAME commit
as this script, per the platform's pre-registration invariant: thresholds AND
the code that judges them are hashed together **before any fitting run**.

COMMIT-ORDER, stated because it is the whole point: this commit lands before any
v2 engine work and before any v2 ensemble is drawn. After it, the bars, the
judges, the grader, the anchor script and the exam document itself can only
change through the amendment log recorded inside
``docs/superpowers/specs/spine-v2-prereg.json`` -- never by editing a file.

Writes ``docs/superpowers/specs/spine-v2-prereg.json``:

- ``bars`` / ``parameters``: assembled by
  ``scripts/spine_v2_report.sealed_from_anchors``, NOT retyped here. That is the
  same function the anti-test sweeps judged with, so the numbers that were swept
  and the numbers that are sealed are provably the same object. They come from
  ``spine-v2-anchors.json``, where each one is derived in the anchor script from
  the measurement it is cut from.
- ``carried``: R1's ``b3`` and R2's ``b2``, loaded whole from
  ``spine02-prereg.json`` (which itself carried them verbatim from round one).
  Loading the object is what "byte-frozen" means; a hand-retype could drift a
  digit.
- ``campaign_record``: the funding ruling, the owner rulings with their dates,
  the batch size, and the declared limitations -- so a reader of the seal alone
  knows what was decided, by whom and when.
- ``prior_rounds``: pointers to both prior seals with their commits, following
  ``scripts/spine02_seal.py``'s ``round_one_record`` pattern (round one has TWO
  commits that matter and they are not the same thing -- see below).
- ``anti_test_record``: the §6.1 obligation's result, per sweep, plus the hash of
  the results file. A judge whose sweep was not monotone does not get sealed,
  and this script refuses to write if one is not.
- ``amendments`` + ``amendment_procedure``: the machine-checked log.
  ``tests/test_spine_v2_seal.py`` enforces it -- if a hashed file's current
  sha256 differs from the sealed one, there must be an amendment entry naming
  that path, or the test fails.
- ``hashes``: sha256 over the working tree for every file that can change a
  verdict -- the judges, the grader, the anchor script and its JSON, the
  anti-test script and its results, the two byte-frozen round-two judge files,
  both prior seals, this script, and **the exam document itself**, which is the
  specification the bars are stated in.

Deterministic: no randomness is drawn, no network is touched and no wall clock is
read -- ``sealed_at_utc`` comes from git HEAD's own commit metadata, the same
convention as ``scripts/spine_pilot_seal.py`` and ``scripts/spine02_seal.py``.
HEAD at the moment this runs is the anti-test commit, i.e. the last commit before
the seal, which is exactly the state being sealed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_report import sealed_from_anchors  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
OUT_PATH = _SPECS / "spine-v2-prereg.json"
ANTITEST_PATH = _SPECS / "spine-v2-antitest-results.json"

#: Round one has TWO commits that matter and they are not the same thing: the
#: pre-registration itself (the seal commit b97450a, completed by the amendment
#: commit c9bd036) versus the tree state the round-one gate certified and
#: measured against (233b70d). Both are recorded, under names that say which is
#: which -- the distinction ``scripts/spine02_seal.py`` established.
ROUND_ONE_SEAL_COMMIT = "b97450a74f5e0ed884977a07091408029d8d3b40"
ROUND_ONE_PREREG_COMMIT = "c9bd03621424becf24dcb603ac7ef725ff9a53ab"
ROUND_ONE_MEASURED_STATE_COMMIT = "233b70d30157e2e06e80e447f410c03afc5d1f68"
ROUND_TWO_PREREG_COMMIT = "fef995ff8ebcc8eea76c6b6c08aa991a18bda967"

#: Every file whose bytes can change a v2 verdict. Kept as an explicit list so a
#: reader can see the boundary of the seal, and so the test can iterate it
#: independently of this script's own dict.
HASHED_FILES: tuple[str, ...] = (
    "docs/superpowers/specs/2026-08-17-spine-v2-exam.md",
    "docs/superpowers/specs/spine-v2-anchors.json",
    "docs/superpowers/specs/spine-v2-antitest-results.json",
    "docs/superpowers/specs/spine-pilot-prereg.json",
    "docs/superpowers/specs/spine02-prereg.json",
    "scripts/spine_v2_anchors.py",
    "scripts/spine_v2_antitest.py",
    "scripts/spine_v2_grader.py",
    "scripts/spine_v2_report.py",
    "scripts/spine_v2_seal.py",
    "scripts/spine_pilot_b3.py",
    "scripts/spine_pilot_report.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def build_seal() -> dict[str, Any]:
    """The sealed object. Pure apart from reading files and git metadata."""
    sealed = sealed_from_anchors()
    antitest = json.loads(ANTITEST_PATH.read_text(encoding="utf-8"))
    if not antitest["all_monotone"]:
        raise SystemExit(
            "REFUSING TO SEAL: these anti-test sweeps are not monotone in the effect their "
            f"bar claims to measure: {antitest['non_monotone_sweeps']}. Exam section 6.1 -- "
            "a judge whose pass rate does not increase in that effect does not get sealed."
        )

    committer_date = _git("log", "-1", "--format=%cI")
    head_sha = _git("rev-parse", "HEAD")

    return {
        "schema": "spine-v2-prereg-1",
        "sealed_at_utc": f"{committer_date} (as of HEAD commit {head_sha})",
        "purpose": (
            "The spine v2, stage 1 exam's pre-registration: the ten bars' thresholds and "
            "the sha256 of the code that judges them, hashed together BEFORE any engine "
            "work or any generated ensemble. Specification: "
            "docs/superpowers/specs/2026-08-17-spine-v2-exam.md"
        ),
        "bars": sealed["bars"],
        "parameters": sealed["parameters"],
        "carried": sealed["carried"],
        "carried_note": (
            "R1 is spine02's b3 and R2 is spine02's b2, loaded whole from that seal (which "
            "carried them verbatim from round one) and judged by the SAME functions round "
            "two ran -- scripts/spine_pilot_b3._judge and "
            "scripts/spine_pilot_report.judge_b2, imported rather than copied, both hashed "
            "below. A change in an R verdict is therefore attributable to the engine and "
            "to nothing else, which is the only reason a no-regression bar is worth having"
        ),
        "bar_codes": ["T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2", "R1", "R2"],
        "campaign_record": {
            "funding_ruling": (
                "governance/decision-register.md D-SP-6, 2026-08-16 (evening): 'go on the "
                "engine work, include the allocation tests'. Scope, stage 1 only: the "
                "generation-time hazard link, the recovery-duration refit to the historical "
                "event chronology, and join-constraint tightening. The flesh stays "
                "selection-only. Stage 2 (model-implied conditional means) and any L3 "
                "generator are explicitly NOT funded"
            ),
            "n_seeds": sealed["bars"]["n_seeds"],
            "n_seeds_note": (
                "50 decades per premise, owner-ruled 2026-08-17. At that size a true engine "
                "clears every retained bar with at least 90% probability (the weakest is D2 "
                "at 0.921); the pilot's 20 would have left A1 at 0.83 and D2 at 0.81, so "
                "either could have recorded a FAIL from ensemble size alone. R1's b3 grid "
                "stays byte-frozen at its own n_seeds = 20"
            ),
            "owner_rulings": [
                {
                    "date": "2026-08-17",
                    "ruling": "tight policy means an inverted yield curve, applied identically "
                    "on both sides; the pass band is the block-bootstrap 95% interval for the "
                    "recession-or-crisis definition; crisis-only must NOT be a bar because its "
                    "interval contains 1.0 on six events",
                    "where": "T1",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "duration anchors from completed spells only, censored spells "
                    "disclosed; four season bars, one per quadrant; stagflation is first-class; "
                    "tolerance +-1 quarter, justified as the game's smallest play unit",
                    "where": "D1-D4",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "the high-inflation line is 4% trailing CPI, with the 3% "
                    "sensitivity published in the same document including the sign flip",
                    "where": "A1, A2",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "2021-22 is excluded from anchor-setting (it lies in the spent "
                    "holdout); no monthly real-asset series exists, so A1 is "
                    "commodities-minus-bonds and real-assets-minus-bonds is null and disclosed",
                    "where": "A1, scope",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "regime identification must be shown robust before the seal -- "
                    "both dials perturbed 50 bp each way, and a richer five-input "
                    "identification compared under a decision rule declared in advance",
                    "where": "exam section 11",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "PRE-SEAL 1 of 4: D1-D4 grade the POOLED completed spells of the "
                    "batch, against the panel's completed-spell distribution measured on the "
                    "same 120-month window -- pooling fixes the small-sample-per-decade "
                    "defect, the shared window fixes the censoring mismatch that made D3 "
                    "unpassable by a correct engine",
                    "where": "D1-D4",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "PRE-SEAL 2 of 4: stagflation months sit on the NON-EXPANDING "
                    "side for transition/ordering purposes (grader_v2, the mapping fix); O1, "
                    "D2 and D4 re-anchored under it, D1 and D3 unchanged, T1 not re-anchored",
                    "where": "O1, D2, D4",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "PRE-SEAL 3 of 4: A2's low-inflation share-positive ceiling is "
                    "DROPPED (it alone demanded ~400 decades on 2.8 points of headroom); A2 "
                    "keeps the correlation gap >= the measured interval's lower edge, the "
                    "positive level, and the 80% high-inflation share floor",
                    "where": "A2",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "PRE-SEAL 4 of 4: the industrial-production-only recession dial "
                    "is declared as a known limitation of the sealed grader, and the two "
                    "omissions -- no reaction-function bar, no hazard-frequency bar -- are "
                    "confirmed as intended rather than left as open questions",
                    "where": "exam section 12",
                },
                {
                    "date": "2026-08-17",
                    "ruling": "NOT taken: O1's stricter one-standard-error variant. The bar "
                    "stays at the block-bootstrap interval's lower edge",
                    "where": "O1",
                },
            ],
            "declared_limitations": [
                "the sealed grader inherits regime_ruleset_v1's industrial-production-only "
                "recessions: a month is labelled REC on trailing INDPRO at or below zero "
                "alone, and a richer five-input classifier reassigns 37 of the 109 months "
                "the sealed one calls recession -- clusters 2015-03..2015-08, "
                "2016-04..2017-02 and 2019-04..2020-02. Not fixable inside this exam, "
                "because regime_ruleset_v1 is sealed platform-wide",
                "T1's downturn union is REC-or-CRI and is NOT re-anchored under grader_v2, "
                "so a STAG month is contracting for the clock and is still not a downturn "
                "onset for T1",
                "T1 tests transmission and flesh-alignment together under selection-only "
                "compilation; a FAIL does not say which broke",
                "D3 is much weaker against round two's engine than the draft's version was: "
                "round two's failing recovery medians of 2-3 months would now pass or sit on "
                "the band's lower edge",
                "D2 is threshold-fragile under the sealed grader: 7 of 8 perturbed arms put "
                "history's own pooled stagflation median outside D2's band",
                "the D anchors are measured on overlapping 120-month windows, which weights "
                "the panel's interior months more than its ends; the disjoint-decade "
                "sensitivity is published beside them",
                "the D bars' power calculation is close to tautological, because the anchor "
                "is cut from the same object the power model's true engine emits",
                "A2 no longer tests a contrast in the share statistic, only in the "
                "correlation levels",
                "A1's containment half is nearly a plumbing assertion under selection-only "
                "compilation; the directional half is the real test",
                "A1 is commodities-minus-bonds, never real-assets-minus-bonds -- no monthly "
                "real-asset total-return series exists in the catalog",
                "no 2021-22 anchor anywhere: the episode lies inside the spent holdout",
                "ER-14 is untouched by a clean pass on A1 and A2 -- inflation does not reach "
                "the private book at all, and this exam measures asset returns",
                "every season is a HARD label; the agreed response if week-2 fitting proves "
                "threshold-unstable is the escalation to soft (weighted) membership",
            ],
            "confirmed_omissions": [
                "no reaction-function bar: B1 v2's construct was found uninformative and no "
                "v3 is specified, so the exam does not test whether policy responds to "
                "inflation at all (owner-confirmed 2026-08-17)",
                "no hazard-frequency bar: B5 v2's construct changes once the hazard becomes "
                "generation-time, which is the central thing D-SP-6 funds, so that change is "
                "graded only through its consequences (owner-confirmed 2026-08-17)",
            ],
        },
        "prior_rounds": {
            "round_one": {
                "seal": "docs/superpowers/specs/spine-pilot-prereg.json",
                "seal_commit": ROUND_ONE_SEAL_COMMIT,
                "prereg_commit": ROUND_ONE_PREREG_COMMIT,
                "measured_state_commit": ROUND_ONE_MEASURED_STATE_COMMIT,
                "verdicts": "docs/superpowers/specs/2026-08-15-spine-pilot-results.md",
                "note": (
                    "two commits matter and they are not the same thing: the "
                    "pre-registration (seal_commit, completed by prereg_commit) and the tree "
                    "state the round-one gate certified and measured against "
                    "(measured_state_commit)"
                ),
            },
            "round_two": {
                "seal": "docs/superpowers/specs/spine02-prereg.json",
                "prereg_commit": ROUND_TWO_PREREG_COMMIT,
                "verdicts": "docs/superpowers/specs/2026-08-16-spine02-results.md",
                "note": (
                    "R1 and R2 are this round's b3 and b2, carried from here unchanged and "
                    "judged by the same code, so a flip is attributable to the engine. R2 is "
                    "expected to flip from FAIL to PASS: join-constraint tightening is inside "
                    "D-SP-6's funded scope"
                ),
            },
            "prior_verdicts_are_frozen": True,
        },
        "anti_test_record": {
            "obligation": (
                "exam section 6.1: every NEW judge ships with an anti-test sweep run on the "
                "judge itself, and a judge whose pass rate does not increase in the effect "
                "its bar claims to measure does not get sealed"
            ),
            "script": "scripts/spine_v2_antitest.py",
            "results": "docs/superpowers/specs/spine-v2-antitest-results.json",
            "readable": "docs/superpowers/specs/spine-v2-antitest-results.md",
            "all_monotone": bool(antitest["all_monotone"]),
            "per_sweep_monotone": {
                name: bool(sweep["monotone_non_decreasing"])
                for name, sweep in antitest["sweeps"].items()
            },
            "per_sweep_pass_rate": {
                name: sweep["pass_rate"] for name, sweep in antitest["sweeps"].items()
            },
            "not_swept": (
                "R1 and R2 are byte-frozen and are deliberately NOT re-swept: changing them "
                "is the thing a no-regression bar exists to prevent"
            ),
        },
        "amendments": [],
        "amendment_procedure": {
            "rule": (
                "after this commit, no file listed in hashes may change without an entry "
                "appended to `amendments` naming its path. Editing a hashed file and "
                "re-running this script is NOT an amendment -- it is a re-seal, and it "
                "erases the record this file exists to keep"
            ),
            "entry_keys": ["amendment_id", "date", "type", "rationale", "post_hoc", "paths"],
            "types": {
                "threshold_change": "a sealed pass/fail value changes",
                "protocol_change": "how a metric is computed or judged changes (not just its "
                "value) -- e.g. a judge, the grader, or the anchor script",
                "documentation": "a hashed document changes without any threshold or judging "
                "rule changing",
            },
            "machine_check": (
                "tests/test_spine_v2_seal.py recomputes every hash against the working tree "
                "and fails unless each mismatch is named by an amendment entry, so the log "
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
    print(f"n_seeds = {sealed['bars']['n_seeds']}")
    print(f"O1 >= {sealed['bars']['O1_clockwise_min']!r}")
    print(f"T1 band = {sealed['bars']['T1_lift_band']!r}")
    print(f"D bands = {sealed['bars']['D_median_bands_months']!r}")
    print(f"A2 margin = {sealed['bars']['A2_correlation_margin']!r}")
    print(f"A2 low-inflation ceiling = {sealed['bars']['A2_share_low_ceiling']!r} (dropped)")
    print(f"anti-tests all monotone: {sealed['anti_test_record']['all_monotone']}")
    for rel, digest in sealed["hashes"].items():
        print(f"  {digest}  {rel}")


if __name__ == "__main__":
    main()
