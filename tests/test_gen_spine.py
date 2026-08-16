"""Spine-conditioned compiler (pilot). Spec:
docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md"""

import pytest
from pydantic import ValidationError

from ah.core.worldspec import SpineSpec


def _table():
    return [
        {"condition": "baseline", "stratum_shift": 0, "dwell_shift_quarters": 0},
        {"condition": "either", "stratum_shift": 1, "dwell_shift_quarters": 1},
        {"condition": "both", "stratum_shift": 2, "dwell_shift_quarters": 2},
    ]


def _spec(**over):
    doc = {
        "premise": {
            "shock": "supply",
            "arrives_quarter": 8,
            "backdrop": "inflation_above_trend",
            "recovery": "slow",
        },
        "severity_table": _table(),
        "join_yoy_max_pp": 2.5,
        "precedent": ["pilot precedent line"],
    }
    doc.update(over)
    return doc


def test_spine_spec_parses():
    spec = SpineSpec.model_validate(_spec())
    assert spec.premise.shock == "supply"
    assert spec.premise.arrives_quarter == 8
    assert [r.condition for r in spec.severity_table] == ["baseline", "either", "both"]


def test_severity_table_must_cover_all_three_conditions_once():
    rows = _table()
    rows[2]["condition"] = "either"  # both missing, either twice
    with pytest.raises(ValidationError, match="baseline, either, both"):
        SpineSpec.model_validate(_spec(severity_table=rows))


def test_arrival_quarter_needs_a_backdrop_window():
    bad = _spec()
    bad["premise"]["arrives_quarter"] = 0
    with pytest.raises(ValidationError):
        SpineSpec.model_validate(bad)


def test_numericworld_projects_x_spine():
    import json
    from pathlib import Path

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(Path("src/ah/presets/stress_1990.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.spine is None  # a stress world has no spine
    doc["extensions"]["x_spine"] = _spec()
    nw2 = project_numeric(WorldSpec.model_validate(doc))
    assert nw2.spine is not None and nw2.spine.premise.recovery == "slow"
