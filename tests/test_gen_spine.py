"""Spine-conditioned compiler (pilot). Spec:
docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md"""

import numpy as np
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


@pytest.fixture(scope="module")
def layers():
    from ah.gen.systems import _pinned_layers

    return _pinned_layers()


def _premise(**over):
    from ah.core.worldspec import SpinePremise

    doc = {
        "shock": "supply",
        "arrives_quarter": 8,
        "backdrop": "inflation_above_trend",
        "recovery": "slow",
    }
    doc.update(over)
    return SpinePremise.model_validate(doc)


def test_sample_spine_shapes_and_determinism(layers):
    from ah.gen.spine import sample_spine

    climate, regimes = layers
    a = sample_spine(climate, regimes, _premise(), n_decades=2, seed=41, months=120)
    b = sample_spine(climate, regimes, _premise(), n_decades=2, seed=41, months=120)
    assert a.states.shape == (2, 120, 5) and a.policy.shape == (2, 120)
    assert np.array_equal(a.states, b.states) and np.array_equal(a.labels, b.labels)


def test_accepted_spines_satisfy_the_premise(layers):
    from ah.gen.spine import (
        BACKDROP_MARGIN_PP,
        CONTRACTION_CODES,
        sample_spine,
    )

    climate, regimes = layers
    p = _premise()
    sp = sample_spine(climate, regimes, p, n_decades=3, seed=7, months=120)
    arrive = 3 * p.arrives_quarter
    for k in range(3):
        pi_pre = sp.states[k, :arrive, 0].mean()  # STATE_NAMES[0] == pi_star
        assert pi_pre > sp.mu_pi[k] + BACKDROP_MARGIN_PP
        in_c = np.isin(sp.labels[k], list(CONTRACTION_CODES))
        starts = np.flatnonzero(in_c & ~np.roll(in_c, 1))
        if in_c[0]:
            starts = np.unique(np.concatenate([[0], starts]))
        window = (starts >= arrive - 3) & (starts <= arrive + 6)
        assert window.any(), f"decade {k}: no contraction onset near quarter {p.arrives_quarter}"
        assert in_c.sum() >= 24  # recovery == slow


def test_unfillable_premise_refuses_with_a_named_reason(layers):
    from ah.gen.spine import SpineRefusal, sample_spine

    climate, regimes = layers
    # a backdrop essentially impossible under the fitted posterior: benign
    # inflation AND an immediate crash AND a slow decade is rare enough at a
    # tiny attempt budget to refuse deterministically.
    p = _premise(backdrop="benign", arrives_quarter=1)
    with pytest.raises(SpineRefusal, match="premise unfillable"):
        sample_spine(
            climate, regimes, p, n_decades=50, seed=11, months=120, max_attempts_per_decade=1
        )
