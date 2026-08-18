"""The stage-2 seal: hashes, threshold literals, and the amendment log's check.

Self-contained -- no catalog, no network, no ensemble. The jobs are the v2 seal
test's, one round on, plus two the stage-2 delta needs that no prior round did:

1. ``test_stage2_seal_exists_and_hashes_match`` recomputes every sealed hash
   against the working tree. It catches a hashed file changing at all.
2. ``test_stage2_thresholds_are_pinned_by_literals`` asserts every sealed value as
   a literal, copied from the committed JSON. It catches what the hash test
   cannot: a seal script that recomputes a DIFFERENT number into the SAME schema.
   (Round one's ``test_prereg_thresholds_are_pinned_by_literals`` is the pattern
   and its rationale is quoted there.)
3. ``test_amendment_log_is_well_formed_and_covers_every_mismatch`` is the machine
   check behind the amendment procedure: a hashed file may differ from its sealed
   hash ONLY if an amendment entry names it.
4. ``test_the_carried_v2_block_is_byte_identical_to_the_v2_seal`` is what
   "byte-frozen" has to mean to be worth anything.
5. **New here:** ``test_the_sealed_p1_pair_is_the_minimum_of_the_published_candidate_set``
   pins ruling SQ7 as arithmetic rather than as prose. The literals test would
   still pass if the ruling had been applied to the wrong set; this one fails if
   any published candidate sits below the sealed number.
6. **New here:** ``test_the_o1_disclosure_is_a_disclosure_and_not_a_bar`` pins
   ruling SQ1's other half. The symmetric floor is in ``parameters`` precisely so
   it can be reported, and the one way that ruling can be broken quietly is for
   the symmetric floor to start being judged -- so the carried O1 threshold is
   asserted to be the v2 one and NOT the symmetric one.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load(name: str) -> Any:
    """Load a ``scripts/`` module by file path.

    ``tests/test_gen_spine.py``'s fixture pattern, kept for the same reason
    ``tests/test_spine_v2_judges.py`` keeps it: ``importlib`` rather than a bare
    ``import`` after a ``sys.path`` insert, which pyright's static resolver
    cannot see. The path insert above stays because the loaded module does its
    own ``sys.path``-based imports.
    """
    path = _SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
SEAL_PATH = _SPECS / "stage2-prereg.json"
V2_SEAL_PATH = _SPECS / "spine-v2-prereg.json"
ANCHORS_PATH = _SPECS / "stage2-anchors.json"
ANTITEST_PATH = _SPECS / "stage2-antitest-results.json"

#: The exact files scripts/stage2_seal.py hashes. Kept here independently of the
#: seal script's own tuple, so a seal-script edit that silently DROPS a path from
#: the hash set is caught by the set comparison below rather than passing
#: unnoticed (round two's SPINE02_HASHED_FILES pattern, kept through two rounds).
STAGE2_HASHED_FILES = [
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
]

P1_MOVES = ("growth_flip", "inflation_crossing")


def _sealed() -> dict[str, Any]:
    return json.loads(SEAL_PATH.read_text(encoding="utf-8"))


def _amended_paths(sealed: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for entry in sealed["amendments"]:
        out.update(entry["paths"])
    return out


def test_stage2_seal_exists_and_hashes_match() -> None:
    sealed = _sealed()
    assert set(sealed["hashes"]) == set(STAGE2_HASHED_FILES)
    assert sealed["hashed_files"] == STAGE2_HASHED_FILES
    amended = _amended_paths(sealed)
    for rel in STAGE2_HASHED_FILES:
        if rel in amended:
            continue
        got = hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest()
        assert got == sealed["hashes"][rel], (
            f"stage-2 seal hash mismatch for {rel}: the working tree no longer matches the "
            "sealed hash. Either the file changed since the seal (a pre-registration "
            "violation) or the change needs an amendment entry naming this path"
        )


def test_amendment_log_is_well_formed_and_covers_every_mismatch() -> None:
    """The machine check the amendment procedure promises.

    Written while the log is still empty, because a check added after the first
    amendment would be a check written by the thing it is meant to police.
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

    amended = _amended_paths(sealed)
    mismatched = {
        rel
        for rel in STAGE2_HASHED_FILES
        if hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest() != sealed["hashes"][rel]
    }
    assert mismatched <= amended, (
        f"these hashed files changed with no amendment entry naming them: "
        f"{sorted(mismatched - amended)}"
    )


def test_stage2_thresholds_are_pinned_by_literals() -> None:
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

    # P1 -- the MINIMUM of the published candidate set (SQ7), cut from the
    # within-window null (SQ8), on the windowed-overlapping construct (SQ1)
    assert bars["P1_departure_min"] == {
        "growth_flip": 0.040330202948,
        "inflation_crossing": 0.031445706759,
    }
    assert bars["P1_departure_min_source"] == {
        "growth_flip": "label_dial_arm__inflation_line_minus_50bp",
        "inflation_crossing": "label_dial_arm__inflation_line_minus_50bp",
    }
    assert bars["P1_candidate_tolerance_fraction"] == 0.5
    assert bars["P1_both_move_types_required"] is True
    # the recommended construct's own candidate, the pair a veto of SQ7 would
    # move to -- pinned so "already inside the candidate set" stays true
    assert bars["P1_candidate_set"]["growth_flip"]["construct__windowed_overlapping"] == (
        0.069084093309
    )
    assert bars["P1_candidate_set"]["inflation_crossing"]["construct__windowed_overlapping"] == (
        0.062546712278
    )

    # P2 -- the strict share's 95% interval, 24-month block, rho refitted
    assert bars["P2_economic_share_band"] == [0.391706974667, 0.673370849738]
    assert bars["P2_summary"] == "strict_economic_share"

    # judge parameters -- definitions, not bars, but sealed for the same reason
    assert params["era_threshold_pp"] == 3.351323828920571
    assert params["contracting_labels"] == ["REC", "CRI", "STAG"]
    assert params["decade_months"] == 120
    assert params["yoy_warmup_months"] == 12
    assert params["phase_construct"] == "windowed_overlapping"
    assert params["phase_null"] == "within_window"
    assert params["decade_scramble_guard_months"] == 24
    assert params["o1_symmetric_floor"] == 0.515671717177
    assert params["p2_block_months"] == 24
    assert params["p2_arm"] == "rho_refitted"
    assert params["p2_economic_components"] == ["policy_rule", "inflation_gap", "season_term"]
    assert params["p2_exogenous_components"] == ["u_hat"]


def test_the_sealed_p1_pair_is_the_minimum_of_the_published_candidate_set() -> None:
    """Ruling SQ7, pinned as arithmetic rather than as prose.

    The literals test would pass just as happily if the ruling had been applied
    to the wrong set -- to the construct candidates alone, say, or with the
    superseded panel-wide-null candidates mixed back in. This one fails if any
    published candidate sits below the sealed number, and it also fails if the
    candidate set stops containing what SQ8 says it must: the two windowed
    constructs and all nine label-dial arms, all cut from the within-window null.
    """
    sealed = _sealed()
    candidates = sealed["bars"]["P1_candidate_set"]
    anchors = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))

    for move in P1_MOVES:
        published = candidates[move]
        assert len(published) == 11, (
            "the candidate set must be the two windowed constructs plus the nine "
            f"label-dial arms; got {sorted(published)}"
        )
        assert sum(1 for k in published if k.startswith("construct__")) == 2
        assert sum(1 for k in published if k.startswith("label_dial_arm__")) == 9
        sealed_value = sealed["bars"]["P1_departure_min"][move]
        assert sealed_value == min(published.values())
        assert published[sealed["bars"]["P1_departure_min_source"][move]] == sealed_value

        # every candidate must be the within-window number, not the superseded
        # panel-wide one -- SQ8's whole content
        within = anchors["p1_phase_anchor"]["within_window_null_constructs"]
        for construct in ("windowed_overlapping", "windowed_disjoint"):
            assert (
                published[f"construct__{construct}"]
                == (within[construct]["candidate_p1_threshold"][move])
            )

        # and the exclusion of the panel-wide candidates must be cost-free
        superseded = anchors["recommended_construct"]["candidate_p1_thresholds"]
        for row in superseded.values():
            assert row[move] >= sealed_value, (
                "a superseded panel-wide-null candidate sits BELOW the sealed minimum, so "
                "excluding it changed a sealed number rather than only a published one"
            )


def test_the_o1_disclosure_is_a_disclosure_and_not_a_bar() -> None:
    """Ruling SQ1's other half: O1 carries byte-frozen, the symmetric floor is reported.

    The quiet way to break that ruling is for the symmetric floor to become the
    thing O1 is judged against, so the carried threshold is asserted to be the v2
    one, the symmetric floor is asserted to be a different number, and the
    symmetric floor is asserted to live in ``parameters`` (reported) rather than
    in ``bars`` (judged).
    """
    sealed = _sealed()
    v2 = json.loads(V2_SEAL_PATH.read_text(encoding="utf-8"))
    symmetric = sealed["parameters"]["o1_symmetric_floor"]
    carried = sealed["carried_v2"]["bars"]["O1_clockwise_min"]

    assert carried == v2["bars"]["O1_clockwise_min"] == 0.5180669104991394
    assert symmetric == 0.515671717177
    assert symmetric != carried, "the disclosure must not become the bar"
    assert symmetric < carried, (
        "symmetrising lowers the floor (the windowed statistic's bootstrap distribution is "
        "wider), which is why the ruling had to be taken explicitly rather than inherited"
    )
    assert not any(key.startswith("O1") for key in sealed["bars"]), (
        "no O1 threshold may live in the stage-2 bars block -- O1 is judged from carried_v2"
    )


def test_the_carried_v2_block_is_byte_identical_to_the_v2_seal() -> None:
    """The ten v2 bars must be the prior exam's, loaded whole rather than retyped
    -- the spine02 and spine-v2 precedent, one round on."""
    v2 = json.loads(V2_SEAL_PATH.read_text(encoding="utf-8"))
    sealed = _sealed()
    carried = sealed["carried_v2"]
    for key in ("bars", "parameters", "carried", "bar_codes"):
        assert json.dumps(carried[key], sort_keys=True) == json.dumps(v2[key], sort_keys=True)
    assert carried["bar_codes"] == ["T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2", "R1", "R2"]
    assert sealed["bar_codes"]["new"] == ["P1", "P2"]
    assert sealed["bar_codes"]["carried_byte_frozen"] == carried["bar_codes"]
    assert set(sealed["bar_codes"]["new"]) & set(carried["bar_codes"]) == set()


def test_the_seal_records_the_campaign_and_every_ruling() -> None:
    """A reader of the seal alone must be able to say what was decided, by whom,
    when, on what reasoning, and what was already known to be wrong with it."""
    sealed = _sealed()
    record = sealed["campaign_record"]
    assert "D-SP-9" in record["funding_ruling"]
    assert record["n_seeds"] == 50

    rulings = {r["id"]: r for r in record["coordinator_rulings"]}
    assert set(rulings) == {"SQ1", "SQ6", "SQ7", "SQ8", "SQ9", "floors"}
    for ruling in rulings.values():
        assert {"id", "date", "ruling", "reasoning", "where"} <= set(ruling)
        assert ruling["date"] == "2026-08-18"
        assert ruling["cheap_veto_disclosed"] is True
        assert len(ruling["reasoning"]) > 100, "a ruling without its reasoning is a decree"

    # the limitations register, and the four the delta was told to carry by name
    limitations = record["declared_limitations"]
    assert len(limitations) >= 13
    joined = " ".join(limitations)
    assert "0.090" in joined, "P1's measured size must be in the register"
    assert "2.05x" in joined and "2.50x" in joined, "P1's dial sensitivity must be in it"
    assert "0.012638" in joined, "the engine-null substitution error must be in it"
    assert "realised-R2" in joined or "realised R2" in joined, "the M4 asterisk must be in it"
    assert "57%" in joined, "the lag dispersion must be in it"


def test_the_floor_rule_is_recorded_and_applied_to_each_sealed_floor() -> None:
    """The 640,000-draw ruling, and the honest half of applying it.

    Neither sealed floor was re-cut at 640,000 draws and the seal must say so in
    terms a reader can check: P1 because it has no tape at all, P2 because its
    tape noise is UNMEASURED and the rule is met by arithmetic. A seal that
    quietly claimed both were re-cut would be the failure this test exists for.
    """
    sealed = _sealed()
    floor = sealed["campaign_record"]["floor_resolution"]
    assert floor["required_draws_for_an_o1_class_floor"] == 640000
    assert floor["o1_class_smallest_margin"] == 0.000761180398
    assert floor["o1_class_required_tape_noise"] == 0.00015223608
    assert floor["o1_class_measured_tape_noise_at_that_count"] == 0.00014801959
    assert (
        floor["o1_class_measured_tape_noise_at_that_count"] <= floor["o1_class_required_tape_noise"]
    )

    assert floor["P1"]["has_a_tape"] is False
    assert floor["P1"]["tape_noise"] == 0.0
    assert floor["P1"]["meets_the_rule"] is True

    assert floor["P2"]["has_a_tape"] is True
    assert floor["P2"]["draws"] == 2000
    assert floor["P2"]["tape_noise_measured"] is False
    assert floor["P2"]["meets_the_rule"] is None, (
        "P2's tape noise was not measured, so the seal must record 'unknown' rather than "
        "'yes' -- an unmeasured bound is not a measurement"
    )
    # ...and the bound the rule reduces to must be true of the numbers it quotes
    band_lo = sealed["bars"]["P2_economic_share_band"][0]
    assert floor["P2"]["smallest_margin_the_band_must_resolve"] < band_lo
    assert (
        floor["P2"]["required_tape_noise_under_the_same_rule"]
        > floor["o1_class_required_tape_noise"] * 100
    ), (
        "P2's margins are orders of magnitude larger than an O1-class floor's, and that is "
        "the whole reason its 2000-draw tape is defensible at all"
    )


def test_every_new_judge_was_anti_tested_and_every_sweep_and_control_held() -> None:
    """Exam section 6.1 plus the design document's four per-bar obligations.

    A judge whose pass rate does not increase in the effect its bar claims to
    measure does not get sealed -- and neither does one whose controls are broken,
    because the noise-shrink attack and the null engine are the two named gaming
    routes. The seal must carry the evidence for both new bars.
    """
    sealed = _sealed()
    record = sealed["anti_test_record"]
    assert record["all_monotone"] is True
    assert record["all_controls_hold"] is True
    assert all(record["per_sweep_monotone"].values())
    assert all(record["per_control_holds"].values())

    for bar in ("P1", "P2"):
        assert any(name.startswith(bar) for name in record["per_sweep_monotone"]), (
            f"{bar} has no anti-test sweep"
        )
        assert any(name.startswith(bar) for name in record["per_control_holds"]), (
            f"{bar} has no anti-test control"
        )
    # the four obligations the design document names, each by its control
    assert {"P1_null_engine", "P1_scramble", "P1_retro", "P2_noise_shrink", "P2_retro"} <= set(
        record["per_control_holds"]
    )
    # the ten carried bars are byte-frozen and deliberately not re-swept
    assert not any(
        name.startswith(("T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2", "R1", "R2"))
        for name in record["per_sweep_monotone"]
    )

    # the recorded sweeps must be the ones actually committed
    committed = json.loads(ANTITEST_PATH.read_text(encoding="utf-8"))
    assert set(committed["sweeps"]) == set(record["per_sweep_monotone"])
    assert set(committed["controls"]) == set(record["per_control_holds"])
    for name, sweep in committed["sweeps"].items():
        assert sweep["monotone_non_decreasing"] == record["per_sweep_monotone"][name]
        assert sweep["pass_rate"] == record["per_sweep_pass_rate"][name]
    for name, control in committed["controls"].items():
        assert control["holds"] == record["per_control_holds"][name]

    # the size disclosure must be the number the control actually measured
    disclosure = sealed["campaign_record"]["p1_size_disclosure"]
    measured = committed["controls"]["P1_null_engine"]["reading_b_the_size_of_the_bar"]
    assert (
        disclosure["size_at_the_sealed_thresholds"] == (measured["size_at_the_sealed_thresholds"])
    )
    assert (
        disclosure["size_at_every_published_candidate"]
        == (measured["size_at_every_published_candidate"])
    )
    assert disclosure["size_at_the_sealed_thresholds"] > 0.0, (
        "a bar with zero measured size at 300 batches would mean the control never ran"
    )


def test_the_sealed_bars_are_what_the_one_assembly_path_produces() -> None:
    """The seal must not be able to drift from the anchors it quotes.

    ``stage2_report.sealed_from_anchors`` is the single assembly path: the seal
    script calls it to build what it writes and the anti-test sweeps call it to
    build what they judge with. Re-running it here and comparing is what makes
    "the numbers that were swept are the numbers that were sealed" checkable
    rather than asserted.
    """
    rebuilt = _load("stage2_report").sealed_from_anchors()
    sealed = _sealed()
    assert sealed["bars"] == rebuilt["bars"]
    assert sealed["parameters"] == rebuilt["parameters"]
    assert sealed["carried_v2"] == rebuilt["carried_v2"]

    committed = json.loads(ANTITEST_PATH.read_text(encoding="utf-8"))
    assert committed["thresholds_judged_against"] == sealed["bars"], (
        "the anti-test sweeps were judged against a different threshold block from the one "
        "that got sealed"
    )
