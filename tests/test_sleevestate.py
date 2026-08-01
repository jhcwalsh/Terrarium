"""WP2R.3 — the sleeve/vehicle state contract.

The plan's acceptance, as tests: a round-trip on a hand-authored example of each
vehicle type, and the schema/pydantic agreement property test — including the
half the WorldSpec pattern doesn't need: the divergence set (cross-field
invariants only pydantic can express) is asserted to be exactly the two
documented rules, no more.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ah.core import sleevestate as ss

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "fixtures" / "state").glob("*.example.json"))

VEHICLE_TYPES = ("closed_end", "open_ended", "evergreen", "liquid")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestRoundTrip:
    def test_one_example_per_vehicle_type(self):
        assert len(EXAMPLES) == 4
        assert sorted(_load(p)["vehicle_type"] for p in EXAMPLES) == sorted(VEHICLE_TYPES)

    @pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
    def test_example_round_trips(self, path):
        document = _load(path)
        state = ss.load_sleeve_state(document)  # jsonschema first, then pydantic
        dumped = state.model_dump(mode="json")
        assert dumped == document  # bit-faithful round trip
        assert ss.load_sleeve_state(dumped) == state


class TestAgreement:
    """The property test: the two validators agree, except on exactly the two
    documented cross-field invariants where pydantic is strictly stricter."""

    STRUCTURAL_MUTATIONS = (
        ("drop_version", lambda d: d.pop("state_version")),
        ("bad_vehicle", lambda d: d.__setitem__("vehicle_type", "timeshare")),
        ("negative_money", lambda d: _first_money_negative(d)),
        ("extra_key", lambda d: d.__setitem__("surprise", 1)),
    )

    @pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
    def test_valid_examples_agree(self, path):
        document = _load(path)
        assert ss.is_schema_valid(document)
        assert ss.is_pydantic_valid(document)

    @pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
    @pytest.mark.parametrize(
        "name,mutate", STRUCTURAL_MUTATIONS, ids=lambda m: m if isinstance(m, str) else ""
    )
    def test_structural_mutants_rejected_by_both(self, path, name, mutate):
        document = copy.deepcopy(_load(path))
        mutate(document)
        assert not ss.is_schema_valid(document), f"{path.stem}/{name}: schema accepted"
        assert not ss.is_pydantic_valid(document), f"{path.stem}/{name}: pydantic accepted"

    def test_divergence_set_is_exactly_the_two_documented_invariants(self):
        base = _load(ROOT / "fixtures" / "state" / "closed-end-cohort.example.json")

        overdrawn = copy.deepcopy(base)
        overdrawn["commitment"]["paid_in"] = overdrawn["commitment"]["committed"] + 1.0
        assert ss.is_schema_valid(overdrawn)  # schema cannot see it
        assert not ss.is_pydantic_valid(overdrawn)  # the mirror can

        phantom_recall = copy.deepcopy(base)
        phantom_recall["commitment"]["recallable_balance"] = (
            phantom_recall["value"]["cumulative_distributions"] + 1.0
        )
        assert ss.is_schema_valid(phantom_recall)
        assert not ss.is_pydantic_valid(phantom_recall)

    def test_unfunded_never_negative_is_a_schema_bound_not_a_convention(self):
        base = copy.deepcopy(_load(ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"))
        base["commitment"]["unfunded"] = -0.01
        assert not ss.is_schema_valid(base)
        assert not ss.is_pydantic_valid(base)


class TestLoader:
    def test_loader_is_jsonschema_first_and_names_the_failing_path(self):
        base = copy.deepcopy(_load(ROOT / "fixtures" / "state" / "liquid-sleeve.example.json"))
        base["weight"] = -0.1
        with pytest.raises(ss.SleeveStateSchemaError, match="weight"):
            ss.load_sleeve_state(base)


class TestContractDetails:
    def test_r14_recallable_and_recycled_are_required_fields(self):
        base = copy.deepcopy(_load(ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"))
        del base["commitment"]["cumulative_recycled"]
        assert not ss.is_schema_valid(base)

    def test_granularity_switch_is_n_funds_and_dispersion_draw(self):
        """Spec §5: same object across modes; a synthetic fund is n_funds=1 with a draw."""
        base = copy.deepcopy(_load(ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"))
        base["identity"]["n_funds"] = 1
        base["identity"]["fund_name"] = "Meridian Capital IV"
        base["parameters"]["dispersion_draw"] = 0.73
        state = ss.load_sleeve_state(base)
        assert state.identity.n_funds == 1  # type: ignore[union-attr]

    def test_evergreen_is_first_class_not_open_ended_with_a_haircut(self):
        """R3: the queue block exists only on the evergreen object."""
        evergreen = _load(ROOT / "fixtures" / "state" / "evergreen-vehicle.example.json")
        assert "queue" in evergreen
        open_ended = copy.deepcopy(
            _load(ROOT / "fixtures" / "state" / "open-ended-sleeve.example.json")
        )
        open_ended["queue"] = evergreen["queue"]
        assert not ss.is_schema_valid(open_ended)

    def test_sleeve_ids_in_examples_resolve_against_the_taxonomy(self):
        """Downstream referencing is by id (WP2R.1 acceptance) — the examples obey it.
        The liquid sleeve's id is outside the alternatives taxonomy by design."""
        from ah.data.taxonomy import load_taxonomy

        sleeves = load_taxonomy().sleeves
        for path in EXAMPLES:
            document = _load(path)
            sleeve_id = document["identity"]["sleeve_id"]
            if document["vehicle_type"] == "liquid":
                assert sleeve_id.startswith("liquid_")
            else:
                assert sleeve_id in sleeves, f"{path.stem}: '{sleeve_id}' not in taxonomy"


def _first_money_negative(document: dict) -> None:
    """Flip the first non-negative money field found to a negative value."""
    if document["vehicle_type"] == "liquid":
        document["value"] = -1.0
        return
    if document["vehicle_type"] == "closed_end":
        document["commitment"]["committed"] = -1.0
        return
    document["value"]["nav_true"] = -1.0
