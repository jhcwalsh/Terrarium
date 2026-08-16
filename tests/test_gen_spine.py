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


@pytest.fixture(scope="module")
def spine_world():
    import json
    from pathlib import Path

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(Path("src/ah/presets/stress_1990.json").read_text(encoding="utf-8"))
    doc["extensions"]["x_spine"] = _spec()
    return project_numeric(WorldSpec.model_validate(doc))


def test_spine_bootstrap_sample_contract(spine_world):
    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import SpineBootstrap

    gen = SpineBootstrap()
    gen.fit(campaign_source())
    ens = gen.sample(spine_world, 3, 90210)
    assert ens.paths.shape[0] == 3 and ens.row_indices is not None
    cond = ens.meta.conditioning
    assert cond["mode"] == "spine-conditioned-stress"
    assert len(cond["hazard"]["rates"]) == 4
    assert cond["quadrant_legend"] == ["recession", "stagflation", "recovery", "expansion"]
    assert ens.slow_states is not None and not hasattr(ens.slow_states, "reason")


def test_every_month_is_verbatim_history(spine_world):
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import SpineBootstrap

    src = campaign_source()
    gen = SpineBootstrap()
    gen.fit(src)
    ens = gen.sample(spine_world, 2, 90210)
    assert np.array_equal(ens.paths, np.asarray(src.values)[ens.row_indices])  # R1


def test_no_era_teleports_at_joins(spine_world):
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import SpineBootstrap, panel_yoy

    src = campaign_source()
    gen = SpineBootstrap()
    gen.fit(src)
    ens = gen.sample(spine_world, 3, 90210)
    yoy = panel_yoy(src)
    bound = spine_world.spine.join_yoy_max_pp
    rows = np.asarray(ens.row_indices)
    for p in range(rows.shape[0]):
        for m in range(1, rows.shape[1]):
            if rows[p, m] != rows[p, m - 1] + 1:  # a join
                assert abs(yoy[rows[p, m]] - yoy[rows[p, m - 1]]) <= bound


def test_hazard_and_block_streams_are_independent(spine_world):
    """Path 0's tape must not change when the hazard stream is consumed more
    (a different premise-month firing pattern) -- proven by construction:
    the two Generators are seeded from different offsets. Assert the offsets
    differ and that a re-sample is bit-identical (stream discipline holds)."""
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import LAYER_OFFSETS, SpineBootstrap

    # four consumers, four disjoint streams (FIX3: blocks is no longer the
    # bare seed -- that collided with spine attempt 0's climate stream,
    # since climate sits at offset 0).
    assert len(set(LAYER_OFFSETS.values())) == len(LAYER_OFFSETS) == 4
    assert LAYER_OFFSETS["hazard"] != 0
    assert LAYER_OFFSETS["blocks"] not in (0, LAYER_OFFSETS["hazard"])
    gen = SpineBootstrap()
    gen.fit(campaign_source())
    a = gen.sample(spine_world, 2, 4242)
    b = gen.sample(spine_world, 2, 4242)
    assert np.array_equal(a.row_indices, b.row_indices)


def test_refusal_on_empty_pool():
    from ah.gen.spine import QUADRANTS, SpineRefusal, _build_pools

    scores = np.array([1.0, 2.0, 3.0])
    cells = np.array([0, 0, 0], dtype=np.int8)  # every row is quadrant 0
    with pytest.raises(SpineRefusal) as excinfo:
        _build_pools({}, scores, cells, from_quarter=5, quadrant=1, pct=50.0)
    msg = str(excinfo.value)
    assert "5" in msg
    assert QUADRANTS[1] in msg  # "stagflation"
    assert "50" in msg


def test_percentile_for_floor_and_halving():
    from ah.gen.spine import percentile_for

    assert percentile_for(35, 0) == 35
    assert percentile_for(35, 1) == 17.5
    assert percentile_for(35, 2) == 8.75
    assert percentile_for(8, 2) == 5.0  # floored: 8 * 0.25 = 2.0 < STRATUM_FLOOR_PCT


def test_correction_dwell_and_refire():
    from ah.gen.spine import _correction_expire, _correction_onset

    spine = SpineSpec.model_validate(_spec())  # both: shift 2, dwell_shift_quarters 2
    expected_dwell = (2 + 2) * 3  # BASE_DWELL_QUARTERS(2) + dwell_shift_quarters(2), *3

    in_correction, dwell_left, shift = False, 0, 0
    flags: list[bool] = []
    for m in range(expected_dwell + 3):
        fires = m == 0  # fire once, at month 0; never again on its own
        in_correction, dwell_left, shift = _correction_onset(
            spine, in_correction, dwell_left, shift, fires=fires, infl=True, credit=True
        )
        flags.append(in_correction)  # state a pct lookup would see THIS month
        in_correction, dwell_left, shift = _correction_expire(in_correction, dwell_left, shift)

    # dwell covers exactly (2+shift)*3 = 12 months, INCLUDING the firing month
    assert flags[:expected_dwell] == [True] * expected_dwell
    assert flags[expected_dwell] is False  # expired exactly on schedule
    assert shift == 0  # baseline pool (unshifted percentile) is back after expiry

    # a second firing is possible afterwards, from the now-expired state
    in_correction, dwell_left, shift = _correction_onset(
        spine, in_correction, dwell_left, shift, fires=True, infl=True, credit=True
    )
    assert in_correction is True
    assert dwell_left == expected_dwell
    assert shift == 2


def test_forced_reentry_at_panel_edge():
    from types import SimpleNamespace

    from ah.core.worldspec import StressSpec
    from ah.gen.spine import HazardTable, SpineBootstrap, SpinePaths, _DrawInputs

    n = 4
    months = 5  # m // 3 -> quarters 0,0,0,1,1
    pool = np.array([n - 1], dtype=np.int64)  # only the panel's LAST row
    pools = {(0, 0, 50.0): pool}
    source = SimpleNamespace(n_rows=n, values=np.zeros((n, 1)), factor_names=["x"])
    hazard = HazardTable(
        rates=np.zeros(4),
        era_threshold_pp=0.0,
        cell_months=np.zeros(4, dtype=np.int64),
        fallback_rate=0.0,
    )
    scores = np.zeros(n)
    cells = np.zeros(n, dtype=np.int8)
    yoy = np.zeros(n)
    era_bucket = np.zeros(n, dtype=np.int64)
    sp = SpinePaths(
        states=np.zeros((1, months, 5)),
        labels=np.full((1, months), 2, dtype=np.int64),  # REC -> contracting -> quadrant 0
        cycle=np.zeros((1, months)),
        policy=np.zeros((1, months)),
        mu_pi=np.zeros(1),
        attempts=1,
        seed=123,
    )
    stress = StressSpec.model_validate(
        {
            "functional": "equity",
            "segments": [
                {
                    "from_quarter": 0,
                    "to_quarter": 1,
                    "entry_percentile": 50.0,
                    "mean_block_months": 6,
                }
            ],
            "join_tolerance": {},
            "precedent": ["x"],
        }
    )
    spine = SpineSpec.model_validate(_spec())

    gen = SpineBootstrap()
    index, corrections = gen._draw(
        _DrawInputs(
            source=source,
            sp=sp,
            hazard=hazard,
            scores=scores,
            cells=cells,
            yoy=yoy,
            era_bucket=era_bucket,
            months=months,
            n_paths=1,
            seed=999,
            stress=stress,
            spine=spine,
            pools=pools,
        )
    )
    # the pool contains ONLY row n-1: if the old (previous + 1) % n wrap were
    # still live, row 0 would appear the month after every visit to row n-1.
    # It never can here, because 0 is not even in the pool.
    assert 0 not in index
    assert np.all(index == n - 1)
    # every month after the first lands on row n-1 again -> forced re-entry
    # every time, and always unfiltered (the pool's only OTHER member,
    # excluding the previous row itself, is empty).
    assert corrections["forced_reentries"] == months - 1
    assert corrections["unfiltered_reentries"] == months - 1


def test_dispatcher_routes_spine_worlds(spine_world):
    from ah.gen import registry, stress
    from ah.gen import spine as _spine  # noqa: F401 - side-effect: registers the dispatcher hook

    gen = registry.resolve_for_world(spine_world)
    ens = gen.sample(spine_world, 1, 5150)
    assert ens.meta.conditioning["mode"] == "spine-conditioned-stress"

    # Test error case: spine world sampled with factory unregistered (blocks/flow
    # pattern guards against accidental import — raises StressError mentioning
    # 'import ah.gen.spine'). Registry pollution discipline: save/restore.
    old_factory = stress._SPINE_FACTORY
    try:
        stress._SPINE_FACTORY = None
        gen_unregistered = registry.resolve_for_world(spine_world)
        with pytest.raises(stress.StressError, match=r"import ah\.gen\.spine"):
            gen_unregistered.sample(spine_world, 1, 5150)
    finally:
        stress._SPINE_FACTORY = old_factory


def test_dispatcher_still_routes_stress_and_legacy_bit_identically():
    import json
    from pathlib import Path

    import numpy as np

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec
    from ah.gen import registry
    from ah.gen.bootstrap import campaign_source
    from ah.gen.stress import StressBootstrap

    doc = json.loads(Path("src/ah/presets/stress_1990.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    via_dispatch = registry.resolve_for_world(nw).sample(nw, 2, 199001)
    direct = StressBootstrap()
    direct.fit(campaign_source())
    assert np.array_equal(via_dispatch.row_indices, direct.sample(nw, 2, 199001).row_indices)


def test_judging_entry_points_leave_the_spine_hook_unregistered():
    """Fail-closed runtime proof (owner ruling 2026-08-16): a process that
    imports only the judging entry points must find no spine factory -- a
    judging path that tried to sample a spine world would refuse loudly
    (StressError) rather than silently executing unsealed spine code."""
    import subprocess
    import sys

    code = (
        "import ah.eval.g2\n"
        "import ah.battery.report\n"
        "from ah.gen import stress\n"
        "import sys\n"
        "sys.exit(0 if stress._SPINE_FACTORY is None else 1)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
