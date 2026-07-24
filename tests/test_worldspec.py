"""WP0.2 acceptance: WorldSpec models + loader.

* round-trip: the canonical example loads, dumps, and reloads identically;
* agreement: on fuzzed near-valid documents, the pydantic mirror accepts a
  document iff the JSON Schema does (STEP0-PLAN §WP0.2 property test);
* a handful of explicit valid/invalid cases as readable anchors.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from ah.core.loader import (
    WorldSpecSchemaError,
    is_schema_valid,
    load_worldspec,
    validate_against_schema,
)
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "schemas" / "example-long-stagflation.worldspec.json"
EXAMPLE: dict[str, Any] = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# round-trip + basic loader behaviour
# --------------------------------------------------------------------------- #


def test_example_is_accepted_by_both_engines() -> None:
    assert is_schema_valid(EXAMPLE)
    WorldSpec.model_validate(EXAMPLE)  # must not raise


def test_example_round_trips_identically() -> None:
    ws = load_worldspec(EXAMPLE_PATH)
    dumped = ws.model_dump(mode="json", exclude_none=True)
    ws2 = load_worldspec(dumped)
    # object equality is the "reloads identically" guarantee
    assert ws == ws2
    # and the dump is a fixed point (stable under re-dump)
    assert dumped == ws2.model_dump(mode="json", exclude_none=True)
    # a dumped WorldSpec is still schema-valid
    assert is_schema_valid(dumped)


def test_loader_accepts_dict_and_path_equivalently() -> None:
    assert load_worldspec(EXAMPLE_PATH) == load_worldspec(copy.deepcopy(EXAMPLE))


def test_loader_rejects_schema_violation_before_pydantic() -> None:
    bad = copy.deepcopy(EXAMPLE)
    del bad["horizon"]
    with pytest.raises(WorldSpecSchemaError):
        load_worldspec(bad)


def test_extension_keys_must_be_namespaced() -> None:
    bad = copy.deepcopy(EXAMPLE)
    bad["extensions"] = {"not_namespaced": 1}
    assert not is_schema_valid(bad)
    with pytest.raises(ValidationError):
        WorldSpec.model_validate(bad)


def test_out_of_bounds_is_rejected_by_both() -> None:
    bad = copy.deepcopy(EXAMPLE)
    bad["horizon"]["quarters"] = 5  # min is 8
    assert not is_schema_valid(bad)
    with pytest.raises(WorldSpecSchemaError):
        validate_against_schema(bad)


# --------------------------------------------------------------------------- #
# agreement property test: pydantic accepts  <=>  jsonschema accepts
# --------------------------------------------------------------------------- #


def _pydantic_accepts(doc: dict[str, Any]) -> bool:
    try:
        WorldSpec.model_validate(doc)
        return True
    except ValidationError:
        return False


def _valid_dispatch() -> dict[str, str]:
    return {"date": "2027", "headline": "h"}


# Each mutator takes (doc, data) and mutates doc in place, using hypothesis to
# draw specifics. Mutators are TYPE-PRESERVING (numbers stay numbers, strings
# stay strings, no nulls) so the only source of accept/reject divergence would
# be a genuine schema<->pydantic disagreement — which is what we are testing.


def _m_spec_version(doc: dict[str, Any], data: st.DataObject) -> None:
    doc["spec_version"] = data.draw(
        st.sampled_from(["1.0.0", "1.0.5", "2.0.0", "1.0", "1.0.0.0", "x"])
    )


def _m_status(doc: dict[str, Any], data: st.DataObject) -> None:
    doc["status"] = data.draw(
        st.sampled_from(["draft", "validated", "approved", "archived", "nope", ""])
    )


def _m_quarters(doc: dict[str, Any], data: st.DataObject) -> None:
    doc.setdefault("horizon", {})["quarters"] = data.draw(st.integers(-10, 200))


def _m_extra_key_top(doc: dict[str, Any], data: st.DataObject) -> None:
    doc[data.draw(st.sampled_from(["__bogus__", "surprise"]))] = 1


def _m_extra_key_nested(doc: dict[str, Any], data: st.DataObject) -> None:
    doc.setdefault("engine_defaults", {})["bogus"] = 1


def _m_policy_rate_start(doc: dict[str, Any], data: st.DataObject) -> None:
    fc = doc.setdefault("factor_conditions", {})
    fc.setdefault("policy_rate", {})["start_pct"] = data.draw(
        st.floats(-50, 50, allow_nan=False, allow_infinity=False)
    )


def _m_path_shape(doc: dict[str, Any], data: st.DataObject) -> None:
    fc = doc.setdefault("factor_conditions", {})
    fc.setdefault("policy_rate", {})["path_shape"] = data.draw(
        st.sampled_from(["linear", "front_loaded", "spike_and_settle", "sideways"])
    )


def _m_title_length(doc: dict[str, Any], data: st.DataObject) -> None:
    doc.setdefault("narrative", {})["title"] = "x" * data.draw(st.integers(0, 200))


def _m_dispatch_count(doc: dict[str, Any], data: st.DataObject) -> None:
    n = data.draw(st.integers(0, 12))
    doc.setdefault("narrative", {})["dispatches"] = [_valid_dispatch() for _ in range(n)]


def _m_n_paths(doc: dict[str, Any], data: st.DataObject) -> None:
    doc.setdefault("engine_defaults", {})["n_paths"] = data.draw(st.integers(-10, 200_000))


def _m_drop_required_top(doc: dict[str, Any], data: st.DataObject) -> None:
    key = data.draw(
        st.sampled_from(
            [
                "spec_version",
                "world_id",
                "status",
                "provenance",
                "narrative",
                "horizon",
                "regimes",
                "factor_conditions",
                "structural",
                "engine_defaults",
            ]
        )
    )
    doc.pop(key, None)


def _m_extensions_key(doc: dict[str, Any], data: st.DataObject) -> None:
    doc["extensions"] = {data.draw(st.sampled_from(["x_ok", "x_", "bad", "y_no"])): 1}


def _m_credit_peak(doc: dict[str, Any], data: st.DataObject) -> None:
    fc = doc.setdefault("factor_conditions", {})
    fc.setdefault("credit", {})["hy_spread_peak_bps"] = data.draw(
        st.floats(0, 5000, allow_nan=False, allow_infinity=False)
    )


_MUTATORS = [
    _m_spec_version,
    _m_status,
    _m_quarters,
    _m_extra_key_top,
    _m_extra_key_nested,
    _m_policy_rate_start,
    _m_path_shape,
    _m_title_length,
    _m_dispatch_count,
    _m_n_paths,
    _m_drop_required_top,
    _m_extensions_key,
    _m_credit_peak,
]


@settings(max_examples=400)
@given(data=st.data())
def test_pydantic_accepts_iff_jsonschema_accepts(data: st.DataObject) -> None:
    doc = copy.deepcopy(EXAMPLE)
    for _ in range(data.draw(st.integers(0, 4))):
        data.draw(st.sampled_from(_MUTATORS))(doc, data)
    assert _pydantic_accepts(doc) == is_schema_valid(doc), doc
