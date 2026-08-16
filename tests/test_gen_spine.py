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
    # refusal driven by budget arithmetic: with max_attempts_per_decade=1 the
    # budget equals n_decades, so refusal requires all 50 independent attempts
    # to accept in a row (~0.5^50 at observed ~50 percent per-attempt acceptance),
    # which is deterministic-in-practice for any fixed seed.
    p = _premise(backdrop="benign", arrives_quarter=1)
    with pytest.raises(SpineRefusal, match="premise unfillable"):
        sample_spine(
            climate, regimes, p, n_decades=50, seed=11, months=120, max_attempts_per_decade=1
        )


def test_panel_quadrants_and_hazard_calibration():
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import MIN_CELL_MONTHS, fit_hazard, panel_yoy

    src = campaign_source()
    yoy = panel_yoy(src)
    assert yoy.shape == (src.n_rows,)
    assert np.isnan(yoy[:12]).all()  # no 12-month lookback at the panel's start
    table = fit_hazard(src)
    assert table.rates.shape == (4,)
    assert np.all((table.rates >= 0.0) & (table.rates <= 1.0))
    # quadrants with enough months carry their own rate; starved ones the fallback
    for c in range(4):
        if table.cell_months[c] < MIN_CELL_MONTHS:
            assert table.rates[c] == table.fallback_rate
    # the loaded-dice property: with both cells populated, stagflation (1) must
    # not be QUIETER than recovery (2) -- corrections cluster with hot
    # inflation, not benign recoveries.
    if table.cell_months[1] >= MIN_CELL_MONTHS and table.cell_months[2] >= MIN_CELL_MONTHS:
        assert table.rates[1] >= table.rates[2]
    # no structurally-silent quadrant: conditioning is on the month BEFORE the
    # onset, so calm markets can precede a crash (1987-pattern). At least one
    # EXPANDING quadrant (2 or 3) must carry a nonzero rate; if this fails it
    # is a finding about the panel -- STOP and report, do not weaken.
    assert table.rates[2] > 0.0 or table.rates[3] > 0.0


def test_spine_quadrant_encoding():
    import numpy as np

    from ah.gen.spine import CONTRACTION_CODES, spine_quadrant

    states = np.array([3.5, 1.0, 1.5, 0.0, 1.2])  # pi*, r*, g, v, L
    rec = next(iter(CONTRACTION_CODES))
    # pi gap = 3.5 - 2.0 > 0.5 -> hot; contracting -> stagflation (1)
    assert spine_quadrant(states, rec, mu_pi=2.0) == 1
    assert spine_quadrant(states, 0, mu_pi=2.0) == 3  # expanding + hot = expansion
    assert spine_quadrant(states, 0, mu_pi=4.0) == 2  # expanding + cool = recovery
    assert spine_quadrant(states, rec, mu_pi=4.0) == 0  # contracting + cool = recession
