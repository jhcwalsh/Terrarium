"""Seal the stage-2 exam. Run ONCE; commit the JSON in the SAME commit as this
script, per the platform's pre-registration invariant: thresholds AND the code
that judges them are hashed together **before any fitting run**.

COMMIT-ORDER, stated because it is the whole point: this commit lands **before
the coupled fit is written** and before any stage-2 batch is simulated. After it,
the two new bars, their judges, the anchor script, the anti-test results and the
exam document itself can only change through the amendment log recorded inside
``docs/superpowers/specs/stage2-prereg.json`` -- never by editing a file.

Writes ``docs/superpowers/specs/stage2-prereg.json``:

- ``bars`` / ``parameters``: assembled by ``scripts/stage2_report.sealed_from_anchors``,
  NOT retyped here. That is the same function the anti-test sweeps judged with, so
  the numbers that were swept and the numbers that are sealed are provably the
  same object. They are **derived by the rulings, in code**, from
  ``stage2-anchors.json``, where each measurement is cut from the thing it
  anchors: ``P1``'s pair is the MINIMUM of the published candidate set (SQ7) cut
  from the within-window null (SQ8) on the windowed-overlapping construct (SQ1),
  and ``P2``'s band is the strict share's primary block-bootstrap interval (SQ6).
- ``carried_v2``: the ten v2 bars, their parameters and R1/R2's frozen blocks,
  loaded whole from ``spine-v2-prereg.json``. Loading the object is what
  "byte-frozen" means; a hand-retype could drift a digit.
- ``campaign_record``: the funding ruling, the six coordinator rulings **verbatim
  with their reasoning**, the batch size, the floor-resolution rule and its
  application, and the declared limitations -- so a reader of the seal alone knows
  what was decided, by whom, when, and what was already known to be wrong with it.
- ``prior_rounds``: pointers to all three prior seals with their commits,
  following ``scripts/spine_v2_seal.py``'s own pattern.
- ``anti_test_record``: §6.1's obligation plus the design document's four
  per-bar obligations, per sweep and per control. A judge whose sweep was not
  monotone does not get sealed, and neither does one whose control was broken;
  this script refuses to write in either case.
- ``amendments`` + ``amendment_procedure``: the machine-checked log.
  ``tests/test_stage2_seal.py`` enforces it -- if a hashed file's current sha256
  differs from the sealed one, there must be an amendment entry naming that path,
  or the test fails.
- ``hashes``: sha256 over the working tree for every file that can change a
  stage-2 verdict -- the new judges, the anti-test script and its results, the
  anchor script and its JSON, the v2 seal and its anchors, the sealed grader, the
  v2 judge module, this script, and **the exam document itself**, which is the
  specification the bars are stated in.

Deterministic: no randomness is drawn, no network is touched and no wall clock is
read -- ``sealed_at_utc`` comes from git HEAD's own commit metadata, the same
convention as ``spine_pilot_seal.py``, ``spine02_seal.py`` and ``spine_v2_seal.py``.
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

from stage2_anchors import P1_MOVE_TYPES  # noqa: E402
from stage2_report import sealed_from_anchors  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
OUT_PATH = _SPECS / "stage2-prereg.json"
ANTITEST_PATH = _SPECS / "stage2-antitest-results.json"
ANCHORS_PATH = _SPECS / "stage2-anchors.json"

#: The three prior seals. Round one has TWO commits that matter and they are not
#: the same thing -- the pre-registration itself versus the tree state its gate
#: certified and measured against -- the distinction ``spine02_seal.py``
#: established and every seal since has carried.
ROUND_ONE_SEAL_COMMIT = "b97450a74f5e0ed884977a07091408029d8d3b40"
ROUND_ONE_PREREG_COMMIT = "c9bd03621424becf24dcb603ac7ef725ff9a53ab"
ROUND_ONE_MEASURED_STATE_COMMIT = "233b70d30157e2e06e80e447f410c03afc5d1f68"
ROUND_TWO_PREREG_COMMIT = "fef995ff8ebcc8eea76c6b6c08aa991a18bda967"

#: Every file whose bytes can change a stage-2 verdict. Kept as an explicit list
#: so a reader can see the boundary of the seal, and so the test can iterate it
#: independently of this script's own dict.
#:
#: ``spine_pilot_b3.py`` and ``spine_pilot_report.py`` -- R1's and R2's judges --
#: are deliberately NOT here. They are inside the v2 seal, which IS here, and
#: ``tests/test_spine_v2_seal.py`` recomputes them on every run; hashing them
#: twice would create two places for the same fact and no extra protection.
HASHED_FILES: tuple[str, ...] = (
    "docs/superpowers/specs/2026-08-18-stage2-exam-delta.md",
    "docs/superpowers/specs/stage2-anchors.json",
    "docs/superpowers/specs/stage2-antitest-results.json",
    "docs/superpowers/specs/spine-v2-prereg.json",
    "docs/superpowers/specs/spine-v2-anchors.json",
    "scripts/stage2_anchors.py",
    "scripts/stage2_antitest.py",
    "scripts/stage2_report.py",
    "scripts/stage2_seal.py",
    "scripts/spine_v2_grader.py",
    "scripts/spine_v2_report.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _floor_resolution(anchors: dict[str, Any], bars: dict[str, Any]) -> dict[str, Any]:
    """The 640,000-draw ruling, applied to each sealed floor and recorded.

    The rule is adopted as binding. Applying it is not the same as re-cutting
    everything at 640,000 draws, and the difference is worth stating in the seal
    rather than in a commit message:

    * ``P1``'s thresholds carry **no tape at all**. Both halves of the departure
      they are cut from -- the measured clockwise fraction and the within-window
      null -- are exhaustively enumerated, not sampled, so their tape noise is
      exactly zero and the rule is met a fortiori.
    * ``P2``'s band **is** a bootstrap interval, cut at 2000 draws, and its
      smallest margin is the distance from its lower edge to the closer recorded
      engine. The rule's requirement scales with that margin, and the margin here
      is 485x the O1-class one the 640,000 was measured against. The tape noise
      itself is NOT measured -- the anchors' section 6.5 prices that at hours,
      because the share refits an AR(1) profile on every draw -- so this is a
      bound and is declared as one.
    """
    floor = anchors["floor_noise_and_the_draw_count"]
    band = [float(x) for x in bars["P2_economic_share_band"]]
    engines = anchors["m4_curve_endogeneity"]["p2_acceptance"]["engine_strict_economic_shares"]
    p2_margin = min(abs(band[0] - float(share)) for share in engines.values())
    return {
        "rule": floor["rule"],
        "required_draws_for_an_o1_class_floor": floor["required_draws"],
        "o1_class_smallest_margin": floor["smallest_margin"],
        "o1_class_required_tape_noise": floor["required_tape_noise"],
        "o1_class_measured_tape_noise_at_that_count": floor["verification"]["tape_noise_sd"],
        "applies_to": (
            "every floor cut in stage 2. It binds on any O1-class clockwise-fraction floor "
            "-- including the symmetric O1 floor this exam publishes as a disclosure, if it "
            "is ever promoted to a bar"
        ),
        "P1": {
            "has_a_tape": False,
            "tape_noise": 0.0,
            "meets_the_rule": True,
            "why": (
                "P1's thresholds are half a departure and both halves are EXHAUSTIVELY "
                "ENUMERATED rather than sampled -- the measured clockwise fraction is a "
                "count and the within-window null scores every admissible shift -- so there "
                "is no bootstrap anywhere in the anchor and no tape to be noisy"
            ),
        },
        "P2": {
            "has_a_tape": True,
            "draws": anchors["m4_curve_endogeneity"]["n_bootstrap"],
            "smallest_margin_the_band_must_resolve": p2_margin,
            "required_tape_noise_under_the_same_rule": floor["noise_margin_fraction"] * p2_margin,
            "tape_noise_measured": False,
            "meets_the_rule": None,
            "why": (
                "the requirement scales with the margin the floor has to resolve, and P2's "
                "smallest margin is the distance from its lower edge to the closer recorded "
                "engine -- roughly 485x the O1-class margin the 640,000 was measured "
                "against. The tape noise itself is NOT measured: the anchors' section 6.5 "
                "prices it at hours because the share refits an AR(1) profile on every draw. "
                "This is a BOUND, it is declared as one, and it is stop-question 2"
            ),
        },
    }


def build_seal() -> dict[str, Any]:
    """The sealed object. Pure apart from reading files and git metadata."""
    sealed = sealed_from_anchors()
    anchors = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
    antitest = json.loads(ANTITEST_PATH.read_text(encoding="utf-8"))

    if not antitest["all_monotone"]:
        raise SystemExit(
            "REFUSING TO SEAL: these anti-test sweeps are not monotone in the effect their "
            f"bar claims to measure: {antitest['non_monotone_sweeps']}. Exam section 6.1 -- "
            "a judge whose pass rate does not increase in that effect does not get sealed."
        )
    if not antitest["all_controls_hold"]:
        raise SystemExit(
            "REFUSING TO SEAL: these anti-test controls are broken: "
            f"{antitest['broken_controls']}. The stage-2 design document's per-bar "
            "obligations are conditions on sealing, not diagnostics."
        )

    # The SQ8 exclusion must cost nothing, and that is asserted rather than said:
    # the superseded panel-wide-null candidates are left out of the candidate set,
    # and every one of them sits ABOVE the minimum the seal takes, so the sealed
    # number would be identical had they been included.
    superseded = anchors["recommended_construct"]["candidate_p1_thresholds"]
    for move in P1_MOVE_TYPES:
        floor_value = float(sealed["bars"]["P1_departure_min"][move])
        for construct, row in superseded.items():
            if float(row[move]) < floor_value:
                raise SystemExit(
                    "REFUSING TO SEAL: the SQ8 exclusion of the panel-wide-null candidates "
                    f"is not cost-free -- {construct}/{move} at {row[move]} sits BELOW the "
                    f"sealed minimum {floor_value}, so excluding it changed a sealed number "
                    "rather than only a published one."
                )

    committer_date = _git("log", "-1", "--format=%cI")
    head_sha = _git("rev-parse", "HEAD")
    null_engine = antitest["controls"]["P1_null_engine"]["reading_b_the_size_of_the_bar"]

    return {
        "schema": "stage2-prereg-1",
        "sealed_at_utc": f"{committer_date} (as of HEAD commit {head_sha})",
        "purpose": (
            "The stage-2 exam's pre-registration: the two NEW bars' thresholds, the ten "
            "carried v2 bars loaded byte-frozen, and the sha256 of the code that judges "
            "them -- hashed together BEFORE the coupled fit is written and before any "
            "stage-2 batch is simulated. Specification: "
            "docs/superpowers/specs/2026-08-18-stage2-exam-delta.md"
        ),
        "bars": sealed["bars"],
        "parameters": sealed["parameters"],
        "carried_v2": sealed["carried_v2"],
        "carried_note": (
            "the ten v2 bars are loaded whole from spine-v2-prereg.json and judged by the "
            "SAME functions the v2 campaign ran -- scripts/spine_v2_report's judges, and "
            "through them spine_pilot_b3._judge and spine_pilot_report.judge_b2 for R1 and "
            "R2 -- imported rather than copied, every one of them hashed below or inside the "
            "v2 seal that is hashed below. A change in one of those ten verdicts is "
            "therefore attributable to the engine and to nothing else, which is the only "
            "reason a carried bar is worth having"
        ),
        "bar_codes": {
            "new": ["P1", "P2"],
            "carried_byte_frozen": sealed["carried_v2"]["bar_codes"],
        },
        "campaign_record": {
            "funding_ruling": (
                "governance/decision-register.md D-SP-9, 2026-08-17: stage 2 funded -- one "
                "coupled monthly system over growth, inflation, policy and the curve, fitted "
                "jointly on the campaign panel by the machinery already in the repo. The "
                "flesh, R1 selection-only and the severity discipline are unchanged; the ten "
                "existing bars carry byte-frozen; the two new bars are sealed BEFORE the fit. "
                "Stage 3 (model-implied conditional means for ASSET returns) is named, not "
                "proposed, and would require amending R1"
            ),
            "n_seeds": sealed["bars"]["n_seeds"],
            "n_seeds_note": (
                "50 decades per premise, carried unchanged from the v2 seal. Both new bars' "
                "power was measured at that size on a true engine and both cleared in 2000 "
                "of 2000 replicates, so the batch size is not the binding constraint on "
                "either -- the anchor's own width is"
            ),
            "coordinator_rulings": [
                {
                    "id": "SQ1",
                    "date": "2026-08-18",
                    "ruling": (
                        "the v2 O1 bar carries BYTE-FROZEN (comparability with the closed "
                        "campaign); the stage-2 PRIMARY ordering/phase measurement is the "
                        "windowed-overlapping symmetric construct (the only one that leaves "
                        "the judged object unchanged -- the first-pass agent's own "
                        "recommendation)"
                    ),
                    "reasoning": (
                        "the two are compatible because symmetrising windows HISTORY, not the "
                        "engine: the generated statistic is bit-identical under both "
                        "constructs, so adopting the symmetric one as primary costs nothing "
                        "that O1's frozen floor protects. The symmetric floor (0.515672) is "
                        "published beside every O1 reading as a disclosure and never judged, "
                        "because it is cut from 2000 draws and carries about 0.003 of tape "
                        "noise on margins of 0.001-0.006, and because re-cutting a sealed "
                        "threshold is a different act from anchoring a new bar"
                    ),
                    "where": "O1 (disclosure), P1 (construct)",
                    "cheap_veto_disclosed": True,
                },
                {
                    "id": "SQ6",
                    "date": "2026-08-18",
                    "ruling": (
                        "P2 seals on the STRICT ECONOMIC-SHARE summary; the realised-R2 "
                        "non-robustness is a declared limitation, not a second bar"
                    ),
                    "reasoning": (
                        "the strict share is primary because it is the function the engine is "
                        "scored by -- that identity is P2's fourth anti-test obligation and it "
                        "outranks elegance. The realised R2 of the same fit has a bootstrap "
                        "interval of [-0.2203, 0.5616] that spans zero at every block length, "
                        "so making it a second bar would mean judging the engine by a "
                        "statistic whose own interval cannot exclude zero"
                    ),
                    "where": "P2",
                    "cheap_veto_disclosed": True,
                },
                {
                    "id": "SQ7",
                    "date": "2026-08-18",
                    "ruling": (
                        "P1 seals at the MINIMUM defensible threshold across the published "
                        "candidate set (all candidates and the 2-2.5x dial-sensitivity range "
                        "published beside it; a bar that asks 'is there ANY unambiguous phase "
                        "coupling' is the economic question, every recorded engine fails even "
                        "this softest bar, and demanding more would risk failing a correct "
                        "engine given the anchor's own uncertainty)"
                    ),
                    "reasoning": (
                        "the candidate threshold moves by a factor of 2.05x and 2.50x under a "
                        "conventional 50 bp move of a classifier dial, and the "
                        "inflation-crossing departure escalates at 1.35 of its own standard "
                        "error, so no single candidate is privileged by the measurement. The "
                        "minimum keeps every recorded engine failing -- by 0.026 at the "
                        "closest cell -- so softening does not make the bar vacuous. What it "
                        "costs is measured and declared: P1's size against an engine whose "
                        "dials are independent by construction is 0.090 at the sealed "
                        "thresholds against 0.013 at the recommended construct's own candidate"
                    ),
                    "where": "P1",
                    "cheap_veto_disclosed": True,
                },
                {
                    "id": "SQ8",
                    "date": "2026-08-18",
                    "ruling": (
                        "the WITHIN-WINDOW scramble is the null on BOTH sides (like-for-like); "
                        "recompute P1's thresholds under it (the +9%/+8% corrected candidates) "
                        "before taking the SQ7 minimum"
                    ),
                    "reasoning": (
                        "a generated batch is fifty independent decades with no time axis "
                        "between them, so the only scramble it admits is a shift inside each "
                        "decade. Shifting one 813-month panel is a different operation on a "
                        "different object and gives a different number. Every candidate in the "
                        "sealed set is cut from the within-window null; this script asserts "
                        "that excluding the superseded panel-wide candidates moves no sealed "
                        "number"
                    ),
                    "where": "P1",
                    "cheap_veto_disclosed": True,
                },
                {
                    "id": "SQ9",
                    "date": "2026-08-18",
                    "ruling": (
                        "the coupling lag is chosen by a SEALED SELECTION RULE (maximum "
                        "likelihood on the declared 25-lag grid, profile published in the fit "
                        "report), not a fixed value; the bootstrap lag-dispersion is a declared "
                        "limitation"
                    ),
                    "reasoning": (
                        "M3 selects ten months and says in the same breath that the panel does "
                        "not pin it -- only 57% of bootstrap draws select within three months "
                        "of ten, and the classifier-cycle arm selects two. Sealing 'ten' would "
                        "seal the half of the measurement that is not solid; sealing the rule "
                        "and the grid seals the half that is"
                    ),
                    "where": "the coupled fit, not a bar",
                    "cheap_veto_disclosed": True,
                },
                {
                    "id": "floors",
                    "date": "2026-08-18",
                    "ruling": (
                        "every sealed floor computed at 640,000 draws (the measured "
                        "requirement: tape noise 0.000148 <= one-fifth of the smallest 0.000761 "
                        "margin)"
                    ),
                    "reasoning": (
                        "the rule is adopted as binding on every stage-2 floor. Applying it is "
                        "not the same as re-cutting everything: P1's thresholds carry no tape "
                        "at all (both halves are exhaustively enumerated) and P2's band "
                        "resolves margins 485x larger than the O1-class one the count was "
                        "measured against, so its 2000-draw tape meets the rule on the "
                        "arithmetic while its tape noise remains UNMEASURED and declared. See "
                        "floor_resolution"
                    ),
                    "where": "P1, P2, and any O1-class floor cut in stage 2",
                    "cheap_veto_disclosed": True,
                },
            ],
            "floor_resolution": _floor_resolution(anchors, sealed["bars"]),
            "p1_size_disclosure": {
                "size_at_the_sealed_thresholds": null_engine["size_at_the_sealed_thresholds"],
                "size_at_every_published_candidate": null_engine[
                    "size_at_every_published_candidate"
                ],
                "measured_by": "scripts/stage2_antitest._p1_null_engine",
                "reading": (
                    "the false-positive rate against a synthetic engine whose two dials are "
                    "independent by construction, at the sealed batch size. This is the price "
                    "of ruling SQ7 and it is the number to argue with if the ruling is to be "
                    "vetoed -- the alternative threshold pair is already inside "
                    "bars.P1_candidate_set, so the change would be an amendment naming two "
                    "numbers rather than a re-derivation"
                ),
            },
            "declared_limitations": [
                "L1 -- P1's SIZE is 0.090 at the sealed thresholds: against a synthetic "
                "engine whose dials are independent by construction, P1 returns a PASS in 9% "
                "of 300 batches of fifty decades, against 1.3% at the recommended construct's "
                "own candidate and 0.3% at the strictest published one. The judge is centred "
                "on the null (mean departure within one standard error of zero), so this is "
                "the bar's size and not a defect -- but a single PASS on P1 is evidence of "
                "SOME phase coupling at about the strength of one conventional significance "
                "test, not proof of it",
                "L2 -- P1's thresholds are pinned only to a factor of 2.05x and 2.50x by a "
                "50 bp move of a classifier threshold dial (the platform's own "
                "BACKDROP_MARGIN_PP), and the inflation-crossing departure escalates at 1.35 "
                "of its own standard error under the campaign's sealed stability rule",
                "L3 -- the escalation path for a COUNTING statistic does not exist. The sealed "
                "rule is 'refit with soft labels and report both', which is written for fitted "
                "coefficients; a clockwise fraction is a count and there is no agreed "
                "soft-label version of one. Nothing was invented, so L2 stands unresolved",
                "L4 -- P1 asks for a fraction of a departure history can only just establish: "
                "on the uncensored construct history's own growth-flip departure has a 95% "
                "interval of [-0.000283, 0.233050], which does not exclude zero, and on the "
                "sealed construct it clears zero by 0.0066 at the lower edge and fails to at "
                "12-month blocks",
                "L5 -- the engine-null substitution error is +0.012638 at worst (ml_link, "
                "growth flips), a fifth of a candidate threshold, and 0.0016 in the median "
                "across the ten judged cells. The sealed judge therefore computes the batch's "
                "OWN null rather than inheriting history's",
                "L6 -- the M4 asterisk: P2 is kept on the pre-declared strict share and would "
                "be DROPPED on the realised-R2 summary of the identical fit, whose bootstrap "
                "interval [-0.2203, 0.5616] spans zero at every block length. The artifact "
                "records verdict_robust_to_the_summary = false. The reason the R2 is rejected "
                "is an estimator pathology (an R2 is ill-behaved under a GLS fit at rho = "
                "0.98), and that reasoning is the author's and should be checked rather than "
                "accepted",
                "L7 -- the strict share is NOT an explained-variance figure. It sums squared "
                "component standard deviations, which treats the components as uncorrelated; "
                "on history the rule-implied rate and the inflation gap correlate at 0.705 and "
                "the total sum of squares is 1.78x the slope's own variance. The number that "
                "answers 'how much of the curve does this equation explain' is the realised "
                "R2, 0.2464",
                "L8 -- the ten-month coupling lag is not pinned: only 57% of bootstrap draws "
                "select within three months of it and the classifier-cycle arm selects two. "
                "SQ9 seals the selection rule rather than the value, and whatever the fit picks "
                "must be published with the profile beside it",
                "L9 -- P2's tape noise has NOT been measured. Its band is cut from 2000 draws "
                "and the adopted floor rule is met by arithmetic rather than by measurement; "
                "the anchors' section 6.5 prices the measurement at hours",
                "L10 -- P2's power is sampling adequacy only. The power calculation places "
                "HISTORY's own components inside history's interval; whether a coupled engine "
                "produces components of that size is week 1's question",
                "L11 -- history is the most favourable engine there is, and both power figures "
                "use it as the true engine while resampling the same 813 months the thresholds "
                "are cut from. They see sampling noise and NOT estimation error, so they are "
                "upper bounds: a power of 1.000 says the bar is reachable, not that it will be "
                "reached",
                "L12 -- the v2 exam's own declared limitations are inherited whole, including "
                "the industrial-production-only recession dial, T1's un-re-anchored downturn "
                "union, and the absence of any 2021-22 anchor (the episode lies inside the "
                "spent holdout)",
                "L13 -- nothing here reaches the private book. ER-14 stands: inflation does not "
                "reach private markets at all. A clean pass on both new bars leaves the "
                "translation layer's blindness exactly where it was",
            ],
            "not_sealed_by_this": (
                "any statement about a coupled engine. No stage-2 fit exists: M3 establishes "
                "the growth -> inflation channel IN HISTORY and the power calculation uses "
                "HISTORY as the true engine. Whether a fitted coupled system reproduces either "
                "is week 1's question and this seal cannot touch it"
            ),
            "standing_caveat": (
                "nothing built on this generator line is a convincing model of history, the "
                "holdout is spent, and no appeal to held-out data is available to any result "
                "stage 2 produces"
            ),
        },
        "prior_rounds": {
            "round_one": {
                "seal": "docs/superpowers/specs/spine-pilot-prereg.json",
                "seal_commit": ROUND_ONE_SEAL_COMMIT,
                "prereg_commit": ROUND_ONE_PREREG_COMMIT,
                "measured_state_commit": ROUND_ONE_MEASURED_STATE_COMMIT,
                "verdicts": "docs/superpowers/specs/2026-08-15-spine-pilot-results.md",
            },
            "round_two": {
                "seal": "docs/superpowers/specs/spine02-prereg.json",
                "prereg_commit": ROUND_TWO_PREREG_COMMIT,
                "verdicts": "docs/superpowers/specs/2026-08-16-spine02-results.md",
            },
            "spine_v2": {
                "seal": "docs/superpowers/specs/spine-v2-prereg.json",
                "exam": "docs/superpowers/specs/2026-08-17-spine-v2-exam.md",
                "verdicts": "docs/superpowers/specs/2026-08-17-spine-v2-results.md",
                "amendments": ["AM-SPV2-2026-08-17-001"],
                "note": (
                    "the campaign CLOSED at its second frontier. Its ten bars are carried here "
                    "byte-frozen, and its own seal is hashed below -- so a stage-2 verdict "
                    "cannot quietly rest on a moved v2 threshold"
                ),
            },
            "prior_verdicts_are_frozen": True,
        },
        "anti_test_record": {
            "obligation": (
                "exam section 6.1: every NEW judge ships with an anti-test sweep run on the "
                "judge itself, and a judge whose pass rate does not increase in the effect its "
                "bar claims to measure does not get sealed. The stage-2 design document adds "
                "four per-bar obligations on top of it, sections 3.1 and 3.2"
            ),
            "script": "scripts/stage2_antitest.py",
            "results": "docs/superpowers/specs/stage2-antitest-results.json",
            "readable": "docs/superpowers/specs/stage2-antitest-results.md",
            "all_monotone": bool(antitest["all_monotone"]),
            "all_controls_hold": bool(antitest["all_controls_hold"]),
            "per_sweep_monotone": {
                name: bool(sweep["monotone_non_decreasing"])
                for name, sweep in antitest["sweeps"].items()
            },
            "per_sweep_pass_rate": {
                name: sweep["pass_rate"] for name, sweep in antitest["sweeps"].items()
            },
            "per_control_holds": {
                name: bool(control["holds"]) for name, control in antitest["controls"].items()
            },
            "controls_are_not_sweeps": (
                "a control's pass rate is REQUIRED to behave in a particular way rather than "
                "to be monotone -- the noise-shrink attack must make the pass rate FALL, and "
                "fall on the upper side -- so controls are gated on their own booleans and "
                "excluded from the monotonicity gate. Both gates block this script"
            ),
            "not_swept": (
                "the ten carried v2 bars are byte-frozen and are deliberately NOT re-swept: "
                "changing them is the thing a carried bar exists to prevent, and each was "
                "anti-tested before the v2 seal"
            ),
        },
        "amendments": [],
        "amendment_procedure": {
            "rule": (
                "after this commit, no file listed in hashes may change without an entry "
                "appended to `amendments` naming its path. Editing a hashed file and "
                "re-running this script is NOT an amendment -- it is a re-seal, and it erases "
                "the record this file exists to keep"
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
                "tests/test_stage2_seal.py recomputes every hash against the working tree and "
                "fails unless each mismatch is named by an amendment entry, so the log cannot "
                "be skipped by editing quietly"
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
    print(f"P1 departure >= {sealed['bars']['P1_departure_min']!r}")
    print(f"P1 attained at {sealed['bars']['P1_departure_min_source']!r}")
    print(f"P2 band = {sealed['bars']['P2_economic_share_band']!r}")
    print(f"O1 symmetric floor (DISCLOSURE) = {sealed['parameters']['o1_symmetric_floor']!r}")
    print(f"anti-tests all monotone: {sealed['anti_test_record']['all_monotone']}")
    print(f"anti-test controls all hold: {sealed['anti_test_record']['all_controls_hold']}")
    print(
        "P1 size at the sealed thresholds: "
        f"{sealed['campaign_record']['p1_size_disclosure']['size_at_the_sealed_thresholds']}"
    )
    for rel, digest in sealed["hashes"].items():
        print(f"  {digest}  {rel}")


if __name__ == "__main__":
    main()
