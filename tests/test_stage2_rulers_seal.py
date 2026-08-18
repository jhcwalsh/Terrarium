"""The D-SP-11 seal: hashes, sealed literals, the carried records, the amendment log.

Self-contained -- no catalog, no network, no ensemble. The jobs are
``tests/test_stage2_seal.py``'s, one round on, plus three this campaign needs
that no prior round did:

1. ``test_rulers_seal_exists_and_hashes_match`` recomputes every sealed hash
   against the working tree.
2. ``test_rulers_thresholds_are_pinned_by_literals`` asserts every sealed value
   as a literal copied from the committed JSON. It catches what the hash test
   cannot: a seal script that recomputes a DIFFERENT number into the SAME schema.
3. ``test_amendment_log_is_well_formed_and_covers_every_mismatch`` is the machine
   check behind the amendment procedure.
4. **New here:** ``test_both_prior_preregs_are_carried_byte_identical`` -- the
   charter's condition, mechanised. "The rulers change only forward" is worth
   nothing unless a moved earlier threshold is a loud failure, so both prior
   seals' bar blocks, parameter blocks, amendment logs and hash sets are asserted
   equal to the files they came from.
5. **New here:** ``test_the_era_rule_is_sealed_with_a_zero_month_window`` -- the
   one way ruler 2 could be widened quietly is for its window to stop being zero,
   so the window and the file its implementation lives in are both pinned.
6. **New here:** ``test_the_a1r_batch_size_is_the_power_calculation_it_claims``
   re-derives the adopted sub-batch count from the sealed literals. The literals
   test would still pass if the plan had been computed from the wrong margin.
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
    path = _SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
SEAL_PATH = _SPECS / "stage2-prereg-2.json"
STAGE2_SEAL_PATH = _SPECS / "stage2-prereg.json"
V2_SEAL_PATH = _SPECS / "spine-v2-prereg.json"
ANTITEST_PATH = _SPECS / "stage2-rulers-antitest-results.json"

#: The exact files ``scripts/stage2_rulers_seal.py`` hashes. Kept here
#: independently of the seal script's own tuple, so a seal-script edit that
#: silently DROPS a path from the hash set is caught by the set comparison rather
#: than passing unnoticed (round two's pattern, kept through three rounds).
RULERS_HASHED_FILES = [
    "docs/superpowers/specs/stage2-prereg.json",
    "docs/superpowers/specs/spine-v2-prereg.json",
    "docs/superpowers/specs/spine-v2-anchors.json",
    "docs/superpowers/specs/stage2-reach-results.json",
    "docs/superpowers/specs/stage2-rulers-antitest-results.json",
    "scripts/stage2_rulers.py",
    "scripts/stage2_rulers_antitest.py",
    "scripts/stage2_rulers_seal.py",
    "scripts/stage2_worlds.py",
]


def _sealed() -> dict[str, Any]:
    return json.loads(SEAL_PATH.read_text(encoding="utf-8"))


def _amended_paths(sealed: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for entry in sealed["amendments"]:
        out.update(entry["paths"])
    return out


def test_rulers_seal_exists_and_hashes_match() -> None:
    sealed = _sealed()
    assert set(sealed["hashes"]) == set(RULERS_HASHED_FILES)
    assert sealed["hashed_files"] == RULERS_HASHED_FILES
    amended = _amended_paths(sealed)
    for rel in RULERS_HASHED_FILES:
        if rel in amended:
            continue
        got = hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest()
        assert got == sealed["hashes"][rel], (
            f"D-SP-11 seal hash mismatch for {rel}: the working tree no longer matches the "
            "sealed hash. Either the file changed since the seal (a pre-registration "
            "violation) or the change needs an amendment entry naming this path"
        )


def test_amendment_log_is_well_formed_and_covers_every_mismatch() -> None:
    """Written while the log is still empty, because a check added after the
    first amendment would be a check written by the thing it polices."""
    sealed = _sealed()
    required = set(sealed["amendment_procedure"]["entry_keys"])
    types = set(sealed["amendment_procedure"]["types"])
    seen: set[str] = set()
    for entry in sealed["amendments"]:
        assert required <= set(entry), f"amendment {entry} is missing {required - set(entry)}"
        assert entry["type"] in types
        assert entry["amendment_id"] not in seen
        seen.add(entry["amendment_id"])
        assert isinstance(entry["paths"], list) and entry["paths"]
        for path in entry["paths"]:
            assert path in sealed["hashes"], f"amendment names an unhashed path: {path}"
    amended = _amended_paths(sealed)
    mismatched = {
        rel
        for rel in RULERS_HASHED_FILES
        if hashlib.sha256((_REPO_ROOT / rel).read_bytes()).hexdigest() != sealed["hashes"][rel]
    }
    assert mismatched <= amended, (
        f"these hashed files changed with no amendment entry naming them: "
        f"{sorted(mismatched - amended)}"
    )


def test_rulers_thresholds_are_pinned_by_literals() -> None:
    """Every sealed value, copied byte-for-byte from the committed JSON.

    The hash test alone catches a BYTE change; it cannot catch a seal script
    recomputing a different number into the same schema. These literals can.
    """
    bars = _sealed()["bars"]
    params = _sealed()["parameters"]

    assert bars["S1_quantiles"] == [0.5, 0.95]
    assert bars["S1_band_level"] == 0.95
    assert bars["S1_conditions"] == [
        "contiguous_q0.5",
        "contiguous_q0.95",
        "seam_q0.5",
        "seam_q0.95",
    ]
    assert bars["S1_both_halves_required"] is True

    assert bars["A1R_alpha"] == 0.05
    assert bars["A1R_power"] == 0.9
    assert bars["A1R_history_difference_pp"] == 3.4932826800308607
    assert bars["A1R_history_spread_high_pp"] == 4.871958498950341
    assert bars["A1R_history_spread_low_pp"] == 1.37867581891948
    assert bars["A1R_pilot_mean_pp"] == -0.974800566398
    assert bars["A1R_pilot_sd_pp"] == 3.866342110522
    assert bars["A1R_pilot_n_seeds"] == 6
    assert bars["A1R_sub_batches"] == 514
    assert bars["A1R_decades"] == 25700
    assert bars["A1R_seed_stride"] == 15485863

    assert params["band_level"] == 0.95
    assert params["band_draws"] == 2000
    assert params["band_block_months"] == 24
    assert params["band_seed"] == 20260821
    assert params["min_tail_count"] == 5
    assert params["deduplicate_transitions"] is True
    assert params["a1r_alpha"] == 0.05
    assert params["a1r_decades_per_sub_batch"] == 50
    assert params["era_crossing_window_months"] == 0


def test_the_sealed_bars_are_what_the_one_assembly_path_produces() -> None:
    """The seal writes what ``sealed_from_sources`` builds, and the anti-tests
    judged with the same object. A second assembly path is how a sweep ends up
    run against numbers that differ from the sealed ones."""
    rulers = _load("stage2_rulers")
    built = rulers.sealed_from_sources()
    sealed = _sealed()
    assert built["bars"] == sealed["bars"]
    assert built["parameters"] == sealed["parameters"]
    assert built["a1r_power_plan"] == sealed["a1r_power_plan"]


def test_both_prior_preregs_are_carried_byte_identical() -> None:
    """The charter's own condition -- 'the rulers change only forward' -- as a
    check rather than a promise. A moved earlier threshold must be loud."""
    carried = _sealed()["carried_records"]
    stage2 = json.loads(STAGE2_SEAL_PATH.read_text(encoding="utf-8"))
    v2 = json.loads(V2_SEAL_PATH.read_text(encoding="utf-8"))
    for key, source in (("stage2", stage2), ("spine_v2", v2)):
        block = carried[key]
        for field in ("bar_codes", "bars", "parameters", "amendments", "hashed_files", "hashes"):
            assert block[field] == source[field], (
                f"the carried {key} seal's {field} no longer matches "
                f"{block['seal']}; a D-SP-11 result would then rest on a moved threshold"
            )
        assert block["sealed_at_utc"] == source["sealed_at_utc"]
    assert carried["prior_verdicts_are_frozen"] is True
    assert "R2" in carried["explicitly_not_re_graded"]
    assert "A1" in carried["explicitly_not_re_graded"]
    # the twelve sealed bars are still named as the ones that keep being reported
    reported = _sealed()["bar_codes"]["carried_and_still_reported"]
    assert sorted(reported) == sorted(
        ["P1", "P2", "T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2", "R1", "R2"]
    )
    assert _sealed()["bar_codes"]["new"] == ["S1", "A1R"]


def test_the_era_rule_is_sealed_with_a_zero_month_window() -> None:
    """Ruler 2's one quiet widening route is its window, so the window and the
    file its implementation lives in are both pinned."""
    sealed = _sealed()
    rule = sealed["era_crossing_rule"]
    assert rule["month_window_months"] == 0
    assert sealed["parameters"]["era_crossing_window_months"] == 0
    assert rule["implementation"].startswith("scripts/stage2_worlds.py")
    assert "scripts/stage2_worlds.py" in sealed["hashes"], (
        "the era rule's implementation must be inside the seal: a rule whose code can move "
        "without an amendment is not sealed"
    )
    assert "only ADDS candidates" in rule["why_this_is_a_faithfulness_test_and_not_a_relaxation"]


def test_the_a1r_batch_size_is_the_power_calculation_it_claims() -> None:
    """Re-derive the adopted count from the sealed literals alone.

    ``B >= (z_(1-a/2) + z_power)^2 * sd^2 / delta^2``, at the upper 90%
    chi-square bound on a six-draw standard deviation. The literals test would
    still pass if the plan had been computed against the wrong margin.
    """
    import math

    sealed = _sealed()
    plan = sealed["a1r_power_plan"]
    bars = sealed["bars"]

    assert plan["alpha"] == bars["A1R_alpha"]
    assert plan["power"] == bars["A1R_power"]
    assert plan["pilot_sd_pp"] == bars["A1R_pilot_sd_pp"]
    assert plan["pilot_n_seeds"] == bars["A1R_pilot_n_seeds"]

    vs_zero = plan["per_margin"]["vs_zero"]
    vs_history = plan["per_margin"]["vs_history"]
    assert vs_zero["delta_pp"] == abs(bars["A1R_pilot_mean_pp"])
    assert math.isclose(
        vs_history["delta_pp"],
        abs(bars["A1R_pilot_mean_pp"] - bars["A1R_history_difference_pp"]),
        rel_tol=1e-12,
    )

    z_sum = plan["z_sum"]
    assert math.isclose(z_sum, 1.959963984540054 + 1.2815515655446004, rel_tol=1e-9)
    for row in (vs_zero, vs_history):
        for key, sd in (
            ("sub_batches_at_the_point_estimate", plan["pilot_sd_pp"]),
            ("sub_batches_at_the_upper_90pct_bound_on_sd", plan["pilot_sd_upper_90pct_bound_pp"]),
        ):
            want = math.ceil(z_sum**2 * sd**2 / row["delta_pp"] ** 2)
            assert row[key] == want, f"{key} is not the formula's own answer"

    assert plan["sub_batches_adopted"] == min(
        vs_zero["sub_batches_at_the_upper_90pct_bound_on_sd"], plan["cap_sub_batches"]
    )
    assert plan["sub_batches_adopted"] == bars["A1R_sub_batches"]
    assert plan["decades_adopted"] == bars["A1R_sub_batches"] * plan["decades_per_sub_batch"]
    assert plan["cap_binds"] is False
    assert plan["achieved_power_at_the_adopted_size"] >= bars["A1R_power"]


def test_the_s1_anchor_and_its_reference_bands_are_recorded_and_coherent() -> None:
    """The band is a function of the panel and of n, so both have to be visible
    in the seal: the anchor by digest, the bands by table."""
    derivation = _sealed()["s1_derivation"]
    assert derivation["anchor_n_jumps"] == 800
    assert len(derivation["anchor_digest_sha256"]) == 64
    # the p95 IS R2's own sealed anchor -- S1 does not open a second one
    assert derivation["anchor_quantiles"]["0.95"] == 0.7433911963542538
    v2 = json.loads(V2_SEAL_PATH.read_text(encoding="utf-8"))
    assert (
        v2["carried"]["b2"]["panel_p95_adjacent_yoy_pp"] == derivation["anchor_quantiles"]["0.95"]
    )

    table = derivation["band_reference_table"]
    sizes = sorted(int(n) for n in table)
    for q in ("q0.5", "q0.95"):
        widths = [table[str(n)][q][1] - table[str(n)][q][0] for n in sizes]
        for n in sizes:
            lo, hi = table[str(n)][q]
            assert lo < hi
        assert widths[0] > widths[-1], f"the {q} band must narrow as n grows"


def test_every_new_judge_was_anti_tested_and_every_sweep_and_control_held() -> None:
    """The seal refuses to write on a non-monotone sweep or a broken control, so
    this checks the record it wrote agrees with the artifact it read."""
    sealed = _sealed()
    record = sealed["anti_test_record"]
    antitest = json.loads(ANTITEST_PATH.read_text(encoding="utf-8"))
    assert record["all_monotone"] is True
    assert record["all_controls_hold"] is True
    assert record["per_sweep_monotone"] == {
        name: sweep["monotone_non_decreasing"] for name, sweep in antitest["sweeps"].items()
    }
    assert record["per_control_holds"] == {
        name: control["holds"] for name, control in antitest["controls"].items()
    }
    assert set(record["per_sweep_monotone"]) == {
        "S1_seam_inflation",
        "S1_seam_oversmoothing",
        "S1_texture_roughening",
    }
    assert set(record["per_control_holds"]) == {
        "S1_noise_inflation_attack",
        "S1_history_identity",
    }
    # both directions of the charter's obligation are covered, and the bar is
    # demonstrably reachable rather than cut so nothing can clear it
    assert antitest["sweeps"]["S1_seam_inflation"]["pass_rate"][-1] == 1.0
    assert antitest["sweeps"]["S1_seam_oversmoothing"]["pass_rate"][-1] == 1.0
    assert antitest["controls"]["S1_history_identity"]["pass_rate"] == 1.0
    attack = antitest["controls"]["S1_noise_inflation_attack"]
    assert attack["pass_rate"] == 0.0
    assert attack["self_referential_bar_pass_rate"] > 0.0, (
        "the attack must actually fool the self-anchored bar, or barring it proves nothing"
    )
    assert attack["texture_fails_above_rate"] == 1.0


def test_the_limitations_are_declared_including_that_the_bar_was_not_blind() -> None:
    """The one thing a reader most needs to know about S1's provenance."""
    sealed = _sealed()
    text = " ".join(sealed["declared_limitations"])
    assert "NOT cut blind" in text
    assert "de-duplication" in text
    assert "under-powered" in text
    assert "ER-14" in text
    assert "holdout is spent" in text
    assert "not_blind" in sealed["anti_test_record"]
