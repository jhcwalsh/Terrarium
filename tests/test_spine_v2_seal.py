"""The spine v2 seal: hashes, threshold literals, and the amendment log's check.

Self-contained -- no catalog, no network, no ensemble. Four jobs, and they catch
different failures:

1. ``test_spine_v2_seal_hashes_match`` recomputes every sealed hash against the
   working tree. It catches a hashed file changing at all.
2. ``test_spine_v2_thresholds_are_pinned_by_literals`` asserts every sealed value
   as a literal, copied from the committed JSON. It catches what the hash test
   cannot: a seal script that recomputes a DIFFERENT number into the SAME schema.
   (Round one's ``test_prereg_thresholds_are_pinned_by_literals`` is the pattern
   and its rationale is quoted there.)
3. ``test_amendment_log_covers_every_hash_mismatch`` is the machine check behind
   the amendment procedure: a hashed file may differ from its sealed hash ONLY if
   an amendment entry names it. That is what makes "amendments go through the log,
   never by editing a file" enforceable rather than aspirational.
4. ``test_the_construct_amendment_is_pinned_by_literals`` and
   ``test_the_amended_exam_document_is_still_byte_identical_to_its_sealed_hash``
   do for AM-SPV2-2026-08-17-001 what (2) does for the thresholds. Naming a path
   in the log makes job (1) skip that path, so an amendment written in order to
   leave a file ALONE needs its own check that the file was in fact left alone --
   and an amendment that decides which batch two bars are judged on needs its
   scope pinned by literals, not by prose.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
SEAL_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-prereg.json"

#: The exact files scripts/spine_v2_seal.py hashes. Kept here independently of
#: the seal script's own tuple, so a seal-script edit that silently DROPS a path
#: from the hash set is caught by the set comparison below rather than passing
#: unnoticed (round two's SPINE02_HASHED_FILES pattern).
SPINE_V2_HASHED_FILES = [
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
]


def _sealed() -> dict[str, Any]:
    return json.loads(SEAL_PATH.read_text(encoding="utf-8"))


def _amended_paths(sealed: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for entry in sealed["amendments"]:
        out.update(entry["paths"])
    return out


def test_spine_v2_seal_exists_and_hashes_match() -> None:
    sealed = _sealed()
    assert set(sealed["hashes"]) == set(SPINE_V2_HASHED_FILES)
    assert sealed["hashed_files"] == SPINE_V2_HASHED_FILES
    amended = _amended_paths(sealed)
    for rel in SPINE_V2_HASHED_FILES:
        if rel in amended:
            continue
        got = hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest()
        assert got == sealed["hashes"][rel], (
            f"spine v2 seal hash mismatch for {rel}: the working tree no longer matches "
            "the sealed hash. Either the file changed since the seal (a pre-registration "
            "violation) or the change needs an amendment entry naming this path"
        )


def test_amendment_log_is_well_formed_and_covers_every_mismatch() -> None:
    """The machine check the amendment procedure promises.

    Written while the log was still empty, because a check added after the first
    amendment would be a check written by the thing it is meant to police. The
    log is no longer empty (AM-SPV2-2026-08-17-001) and this check now has work
    to do.
    """
    sealed = _sealed()
    required = set(sealed["amendment_procedure"]["entry_keys"])
    types = set(sealed["amendment_procedure"]["types"])
    seen_ids: set[str] = set()
    for entry in sealed["amendments"]:
        assert required <= set(entry), f"amendment {entry} is missing {required - set(entry)}"
        assert entry["type"] in types, f"unknown amendment type {entry['type']}"
        assert entry["amendment_id"] not in seen_ids, "amendment ids must be unique"
        seen_ids.add(entry["amendment_id"])
        assert isinstance(entry["paths"], list) and entry["paths"]
        for path in entry["paths"]:
            assert path in sealed["hashes"], f"amendment names an unhashed path: {path}"

    # every mismatch must be named by an amendment -- the converse of the hash test
    amended = _amended_paths(sealed)
    mismatched = {
        rel
        for rel in SPINE_V2_HASHED_FILES
        if hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest() != sealed["hashes"][rel]
    }
    assert mismatched <= amended, (
        f"these hashed files changed with no amendment entry naming them: "
        f"{sorted(mismatched - amended)}"
    )


def test_the_construct_amendment_is_pinned_by_literals() -> None:
    """AM-SPV2-2026-08-17-001, the D-SP-8 measurement-arm amendment.

    Pinned the same way the thresholds are, and for the same reason: the hash
    test cannot see a rationale being softened or a bar quietly added to the
    amended arm, and this is the one entry that decides which batch two of the
    six bars are judged on. The three claims that make it a *narrow* amendment
    are asserted, not merely described -- no threshold moved, no hashed file was
    edited, and the arm change reaches only T1 and O1.
    """
    sealed = _sealed()
    entries = [e for e in sealed["amendments"] if e["amendment_id"] == "AM-SPV2-2026-08-17-001"]
    assert len(entries) == 1, "the D-SP-8 construct amendment must be logged exactly once"
    entry = entries[0]

    assert entry["date"] == "2026-08-17"
    assert entry["type"] == "protocol_change"
    assert entry["post_hoc"] is True
    assert entry["paths"] == ["docs/superpowers/specs/2026-08-17-spine-v2-exam.md"]

    payload = entry["payload"]
    assert payload["judged_on_unconditional_batch"] == ["T1", "O1"]
    assert payload["judged_on_premise_accepted_batch"] == [
        "D1",
        "D2",
        "D3",
        "D4",
        "A1",
        "A2",
        "R1",
        "R2",
    ]
    assert (
        set(payload["judged_on_unconditional_batch"])
        & set(payload["judged_on_premise_accepted_batch"])
        == set()
    ), "a bar cannot be judged on both arms"
    assert set(payload["judged_on_unconditional_batch"]) | set(
        payload["judged_on_premise_accepted_batch"]
    ) == set(sealed["bar_codes"]), "every sealed bar must be assigned to exactly one arm"
    assert payload["thresholds_changed"] == []
    assert payload["hashed_files_edited"] == []
    assert payload["n_seeds_unchanged"] == 50
    assert payload["exam_document_left_byte_identical"] is True

    # the disclosure the amendment is required to carry: at the time it was
    # written the amended arm was already known to read more favourably
    known = payload["readings_known_at_amendment_time"]
    assert known["T1_band"] == sealed["bars"]["T1_lift_band"]
    assert known["O1_floor"] == sealed["bars"]["O1_clockwise_min"]
    assert known["T1_unconditional"] == 1.763633
    assert known["T1_premise_accepted"] == 1.230161
    assert known["O1_unconditional"] == 0.514911
    assert known["O1_premise_accepted"] == 0.500707
    assert known["amended_arm_reads_more_favourably"] is True
    assert known["both_arms_fail_both_bars_at_amendment_time"] is True
    # ...and the disclosure must be TRUE of the numbers it quotes, not just present
    lo, hi = sealed["bars"]["T1_lift_band"]
    floor = sealed["bars"]["O1_clockwise_min"]
    assert known["T1_unconditional"] > known["T1_premise_accepted"]
    assert known["O1_unconditional"] > known["O1_premise_accepted"]
    assert not (lo <= known["T1_unconditional"] <= hi)
    assert not (lo <= known["T1_premise_accepted"] <= hi)
    assert known["O1_unconditional"] < floor and known["O1_premise_accepted"] < floor


def test_the_amended_exam_document_is_still_byte_identical_to_its_sealed_hash() -> None:
    """The compensating check for naming a path in the amendment log.

    ``test_spine_v2_seal_exists_and_hashes_match`` SKIPS any path an amendment
    names -- which is right in general (an amendment exists to permit a change)
    and would be a hole here, because AM-SPV2-2026-08-17-001 names the exam
    document precisely in order to leave it untouched. The exam's own rule is
    "an amendment goes through the machine-checked log, never by editing this
    file", so the file must still hash to its sealed value, and that is asserted
    here rather than trusted.
    """
    sealed = _sealed()
    rel = "docs/superpowers/specs/2026-08-17-spine-v2-exam.md"
    got = hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest()
    assert got == sealed["hashes"][rel], (
        "the exam document was edited. AM-SPV2-2026-08-17-001 states it was left "
        "byte-identical, and the exam itself forbids amending by editing it"
    )


def test_spine_v2_thresholds_are_pinned_by_literals() -> None:
    """Every sealed value, copied byte-for-byte from the committed JSON.

    The hash test alone only catches a BYTE change; it cannot catch a seal script
    that recomputes a different number into the same schema. These literals can.
    Every comparison is ``==``, not approx: these are sealed values, not
    measurements to be reproduced within a tolerance.
    """
    sealed = _sealed()
    bars = sealed["bars"]
    params = sealed["parameters"]

    assert bars["grader"] == "grader_v2"
    assert bars["n_seeds"] == 50

    # T1 -- the block-bootstrap 95% interval for the recession-or-crisis lift
    assert bars["T1_lift_band"] == [1.7752827491108736, 3.3473622102535145]

    # O1 -- the interval's lower edge, measured under grader_v2
    assert bars["O1_clockwise_min"] == 0.5180669104991394

    # D1-D4 -- each season's decade-pooled median +- 1 quarter
    assert bars["D_tolerance_months"] == 3.0
    assert bars["D_anchor_medians_months"] == {
        "recession": 2.0,
        "stagflation": 4.0,
        "recovery": 5.0,
        "expansion": 4.0,
    }
    assert bars["D_median_bands_months"] == {
        "recession": [0.0, 5.0],
        "stagflation": [1.0, 7.0],
        "recovery": [2.0, 8.0],
        "expansion": [1.0, 7.0],
    }
    assert bars["D_statistic"] == "median of the completed spells POOLED over the whole batch"

    # A1 -- the min and max commodities-minus-bonds spread across the five
    # in-panel episodes
    assert bars["A1_containment_pp"] == [-5.053054679081145, 32.31605649965673]

    # A2 -- the measured interval's lower edge, the surviving share floor, and
    # the ceiling the owner dropped
    assert bars["A2_correlation_margin"] == 0.13609378139729844
    assert bars["A2_share_high_floor"] == 0.80
    assert bars["A2_share_low_ceiling"] is None
    assert bars["A2_share_low_ceiling_dropped_value"] == 0.65

    # judge parameters -- definitions, not bars, but sealed for the same reason
    assert params["k_months"] == 12
    assert params["inflation_high_line_pp"] == 4.0
    assert params["rolling_window_months"] == 36
    assert params["decade_months"] == 120
    assert params["era_threshold_pp"] == 3.351323828920571
    assert params["contracting_labels"] == ["REC", "CRI", "STAG"]
    assert params["downturn_labels"] == ["REC", "CRI"]
    assert params["crisis_only_labels"] == ["CRI"]

    # R1 and R2 -- byte-frozen from round two
    assert sealed["carried"]["b2"]["join_yoy_max_pp"] == 2.5
    assert sealed["carried"]["b2"]["p95_ratio_max"] == 1.25
    assert sealed["carried"]["b2"]["panel_p95_adjacent_yoy_pp"] == 0.7433911963542538
    assert sealed["carried"]["b3"]["grid_private_pct"] == [15, 35, 40, 55]
    assert sealed["carried"]["b3"]["min_breach_seeds_at_55"] == 1
    assert sealed["carried"]["b3"]["n_seeds"] == 20
    assert sealed["carried"]["b3"]["coverage_must_be_monotone"] is True


def test_carried_bars_are_byte_identical_to_the_round_two_seal() -> None:
    """R1 and R2 must be the prior round's bars, loaded whole rather than
    retyped -- the spine02 precedent's own check, one round on."""
    spine02 = json.loads(
        (_REPO_ROOT / "docs" / "superpowers" / "specs" / "spine02-prereg.json").read_text(
            encoding="utf-8"
        )
    )
    sealed = _sealed()
    for key in ("b2", "b3"):
        assert json.dumps(sealed["carried"][key], sort_keys=True) == json.dumps(
            spine02[key], sort_keys=True
        )


def test_the_seal_records_the_campaign_and_both_prior_rounds() -> None:
    """A reader of the seal alone must be able to say what was decided, by whom,
    when, and what was already known to be wrong with it."""
    sealed = _sealed()
    record = sealed["campaign_record"]
    assert "D-SP-6" in record["funding_ruling"]
    assert record["n_seeds"] == 50
    assert len(record["owner_rulings"]) >= 9
    assert all({"date", "ruling", "where"} <= set(r) for r in record["owner_rulings"])
    assert all(r["date"] == "2026-08-17" for r in record["owner_rulings"])
    assert len(record["declared_limitations"]) >= 10
    assert len(record["confirmed_omissions"]) == 2

    prior = sealed["prior_rounds"]
    assert prior["round_one"]["prereg_commit"] == "c9bd03621424becf24dcb603ac7ef725ff9a53ab"
    assert prior["round_one"]["measured_state_commit"] == "233b70d30157e2e06e80e447f410c03afc5d1f68"
    assert prior["round_two"]["prereg_commit"] == "fef995ff8ebcc8eea76c6b6c08aa991a18bda967"
    assert prior["prior_verdicts_are_frozen"] is True


def test_every_new_judge_was_anti_tested_and_every_sweep_was_monotone() -> None:
    """Exam section 6.1. A judge whose pass rate does not increase in the effect
    its bar claims to measure does not get sealed -- so the seal must carry the
    evidence that none of them does, for every new bar."""
    sealed = _sealed()
    record = sealed["anti_test_record"]
    assert record["all_monotone"] is True
    per_sweep = record["per_sweep_monotone"]
    assert all(per_sweep.values())
    for bar in ("T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2"):
        assert any(name.startswith(bar) for name in per_sweep), f"{bar} has no anti-test sweep"
    # R1 and R2 are byte-frozen and deliberately not re-swept
    assert not any(name.startswith(("R1", "R2")) for name in per_sweep)

    # the recorded sweeps must be the ones actually committed
    committed = json.loads(
        (
            _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-antitest-results.json"
        ).read_text(encoding="utf-8")
    )
    assert set(committed["sweeps"]) == set(per_sweep)
    for name, sweep in committed["sweeps"].items():
        assert sweep["monotone_non_decreasing"] == per_sweep[name]
        assert sweep["pass_rate"] == record["per_sweep_pass_rate"][name]


def test_the_sealed_bars_match_the_anchors_they_were_derived_from() -> None:
    """The seal must not be able to drift from the anchor file it quotes: every
    bar is loaded from ``exam_bars`` and every parameter from
    ``judge_parameters``, so the two are the same object or the seal is wrong."""
    anchors = json.loads(
        (_REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-anchors.json").read_text(
            encoding="utf-8"
        )
    )
    sealed = _sealed()
    assert sealed["bars"] == anchors["exam_bars"]
    assert sealed["parameters"] == anchors["judge_parameters"]
