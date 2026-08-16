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
    assert a.pi_actual.shape == (2, 120)
    assert np.array_equal(a.states, b.states) and np.array_equal(a.labels, b.labels)
    # (b) determinism unchanged: pi_actual (the new field, drawn on its own
    # per-attempt inflnoise stream) is bit-identical across two calls too.
    assert np.array_equal(a.pi_actual, b.pi_actual)
    assert np.array_equal(a.policy, b.policy)


def test_pi_actual_feeds_the_policy_anchor(layers):
    """(a) spine-02 Task 10: pi_actual = pi_star + eps differs from pi_star,
    and the policy anchor responds to it. Isolate the response from the
    slow-moving r_star/pi_star trend by looking at dpol := policy - (pi_star
    + r_star), the anchor's deviation from the flat "no cycle, no inflation
    gap" baseline -- by the Taylor-anchor algebra (policy_anchor's
    phi_pi*(pi_actual - pi_star) + phi_c*cycle terms) dpol = phi_pi*eps +
    phi_c*cycle exactly. A strong CONTEMPORANEOUS correlation between dpol
    and eps (month t against month t, not diffed/lagged) on this decade is
    therefore direct evidence pi_actual is wired into the anchor and not
    silently defaulting to pi_star (which would zero eps's contribution and
    the correlation with it)."""
    from ah.gen.spine import sample_spine

    climate, regimes = layers
    sp = sample_spine(climate, regimes, _premise(), n_decades=1, seed=2026, months=120)
    pi_star = sp.states[0, :, 0]
    r_star = sp.states[0, :, 1]
    eps = sp.pi_actual[0] - pi_star
    assert not np.allclose(eps, 0.0)  # pi_actual != pi_star

    dpol = sp.policy[0] - (pi_star + r_star)
    corr = float(np.corrcoef(dpol, eps)[0, 1])
    assert corr > 0.3, f"contemporaneous corr(dpol, eps) = {corr}"


def test_attempt_stride_decouples_from_platform_stride(layers):
    """(c) stride bite: seeds 199002 and 199002+7919 previously collided.
    Under SEED_STRIDE-based attempt streams (round one), sample_spine(seed=
    199002, n_decades=1) accepted its lone decade at attempt index 18, and
    sample_spine(seed=199002+7919, n_decades=1) accepted at attempt index 17
    -- both compute the SAME l1_seed (199002 + 7919*18 == 206921 + 7919*17),
    so their first-decade states were bit-identical (empirically confirmed
    pre-fix, final-review F3). With ATTEMPT_STRIDE decoupled from the
    platform's 7919 per-path stride, no attempt index in the budget can
    realign the two, so the states must now differ."""
    from ah.gen.spine import sample_spine

    climate, regimes = layers
    a = sample_spine(climate, regimes, _premise(), n_decades=1, seed=199002, months=120)
    b = sample_spine(climate, regimes, _premise(), n_decades=1, seed=199002 + 7919, months=120)
    assert not np.array_equal(a.states, b.states)


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
    """Ordinary joins stay within the YoY bound.

    Caveat (owner ruling): the UNFILTERED forced-re-entry path (panel-edge
    re-entry with no other pool member to filter to -- see
    test_forced_reentry_at_panel_edge) may legitimately exceed this bound;
    the Task-7 measurement recorded 5.70pp and 9.59pp cases under that
    mechanism. This test passes today because seed 90210 with 3 paths
    produces no unfiltered re-entry, which is deterministic given the fixed
    seed and campaign source. If it ever fails at a join flagged as an
    unfiltered re-entry, that is the disclosed mechanism above firing, not
    a regression.
    """
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

    # five consumers, five disjoint streams (FIX3: blocks is no longer the
    # bare seed -- that collided with spine attempt 0's climate stream,
    # since climate sits at offset 0. spine-02 Task 10 adds inflnoise, the
    # per-attempt stream that draws pi_actual's fitted CPI observation
    # noise).
    assert len(set(LAYER_OFFSETS.values())) == len(LAYER_OFFSETS) == 5
    assert LAYER_OFFSETS["hazard"] != 0
    assert LAYER_OFFSETS["blocks"] not in (0, LAYER_OFFSETS["hazard"])
    gen = SpineBootstrap()
    gen.fit(campaign_source())
    a = gen.sample(spine_world, 2, 4242)
    b = gen.sample(spine_world, 2, 4242)
    assert a.row_indices is not None
    assert b.row_indices is not None
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
    from typing import cast

    from ah.core.worldspec import StressSpec
    from ah.gen.bootstrap import BootstrapSource
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
        pi_actual=np.zeros((1, months)),  # unread by this draw path; same shape as states[:,:,0]
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
            # synthetic stub: carries exactly the fields the draw path reads
            # (n_rows, values, factor_names) -- not a real BootstrapSource.
            source=cast(BootstrapSource, source),
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
    direct_ens = direct.sample(nw, 2, 199001)
    assert via_dispatch.row_indices is not None
    assert direct_ens.row_indices is not None
    assert np.array_equal(via_dispatch.row_indices, direct_ens.row_indices)


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


def test_spine_pilot_world_loads_with_both_extensions():
    import json
    from pathlib import Path

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(Path("src/ah/presets/spine_pilot.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.world_id.endswith("802")
    assert nw.spine is not None and nw.stress is not None
    assert nw.spine.premise.backdrop == "inflation_above_trend"


#: The commit run_gate.py/check_gate.py stamped for round one's G-pilot seal
#: measurement. Round one's seal binds the files AS THEY WERE at the sealed
#: measurement (this commit); spine-02 (Task 10 onward) edits the tree freely
#: under its own seal, to be minted at Task 12. Re-hashing the WORKING TREE
#: against round-one's recorded hashes would therefore fail for every file
#: this round touches -- correctly, but uninformatively, since round one's
#: seal was never a claim about the spine-02 tree. Hash the round-one BLOB
#: instead, via `git show <sha>:<path>`, so this test verifies what it always
#: meant to verify (round one's seal is an honest record of round one) without
#: being coupled to files this round is authorized to change.
ROUND_ONE_SEAL_COMMIT = "233b70d"


def test_prereg_seal_exists_and_hashes_match():
    import hashlib
    import json
    import subprocess
    from pathlib import Path

    sealed = json.loads(
        Path("docs/superpowers/specs/spine-pilot-prereg.json").read_text(encoding="utf-8")
    )
    for key in ("b1", "b2", "b3", "b4", "b5", "b6"):
        assert key in sealed, f"sealed bars missing {key}"
    for rel, want in sealed["hashes"].items():
        if want == "unbuilt":
            continue
        blob = subprocess.run(
            ["git", "show", f"{ROUND_ONE_SEAL_COMMIT}:{rel}"],
            capture_output=True,
            check=True,
        ).stdout
        got = hashlib.sha256(blob).hexdigest()
        assert got == want, (
            f"sealed hash mismatch for {rel} at {ROUND_ONE_SEAL_COMMIT}: "
            "round one's own recorded blob no longer matches its recorded hash"
        )


def test_prereg_thresholds_are_pinned_by_literals():
    """Every sealed B1-B6 value, copied byte-for-byte from
    docs/superpowers/specs/spine-pilot-prereg.json as committed at the Task-6
    pre-registration (amended once, pre-measurement, in the same-day fix
    round). This is the lock the seal-hash test alone does not provide: a
    hash mismatch only fires if the JSON's BYTES change, so a seal-script bug
    that recomputes a DIFFERENT number into the SAME schema would sail
    through the hash check just as easily as a correct re-run would. These
    literals catch that: a re-run of the seal script that changes any
    panel-derived number, or a hand-edit of any threshold, fails HERE.

    Every comparison is `==`, not approx: these are sealed values, not
    measurements with tolerance of their own -- exact byte-for-byte
    reproduction is the whole point of a pre-registration lock.
    """
    import json
    from pathlib import Path

    sealed = json.loads(
        Path("docs/superpowers/specs/spine-pilot-prereg.json").read_text(encoding="utf-8")
    )

    assert sealed["b1"]["min_sign_fraction"] == 0.90
    assert sealed["b1"]["lag_months"] == [3, 12]

    assert sealed["b2"]["join_yoy_max_pp"] == 2.5
    assert sealed["b2"]["p95_ratio_max"] == 1.25
    assert sealed["b2"]["panel_p95_adjacent_yoy_pp"] == 0.7433911963542538

    assert sealed["b3"]["grid_private_pct"] == [15, 35, 40, 55]
    assert sealed["b3"]["min_breach_seeds_at_55"] == 1
    assert sealed["b3"]["n_seeds"] == 20
    assert sealed["b3"]["coverage_must_be_monotone"] is True

    assert sealed["b4"]["dwell_median_ratio_band"] == [0.6, 1.4]
    assert sealed["b4"]["panel_dwell_medians"] == [5.0, 4.0, 9.0, 6.0]
    assert sealed["b4"]["clockwise_fraction_tolerance"] == 0.15
    assert sealed["b4"]["panel_clockwise_fraction"] == 0.6029411764705882

    assert sealed["b5"]["rel_tolerance"] == 0.5
    assert sealed["b5"]["panel_rates"] == [
        0.010752688172043012,  # 1/93
        0.07017543859649122,  # 4/57
        0.0,
        0.004273504273504274,  # 1/234
    ]
    assert sealed["b5"]["panel_cell_months"] == [93, 57, 378, 234]
    assert sealed["b5"]["min_cell_months"] == 24

    assert sealed["b6"]["k_months"] == 12
    assert sealed["b6"]["spine_policy_gap_threshold_pp"] == 0.0
    assert sealed["b6"]["panel_conditional_onset_rate"] == 0.2214765100671141
    assert sealed["b6"]["panel_unconditional_onset_rate"] == 0.07731305449936629
    assert sealed["b6"]["rel_tolerance"] == 0.5

    assert sealed["sensitivity_seeds"] == [199002, 1199005, 2199008, 3199011, 4199014]


# --------------------------------------------------------------------------- #
# Task 7: the pilot report's pure judge functions (imported from the script,
# not duplicated here -- see scripts/spine_pilot_report.py's import-safety
# guard: importing it draws no data, samples no ensemble, writes no file).
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def report():
    """Loads scripts/spine_pilot_report.py by file path (the
    ``test_the_reference_run_script_agrees_with_the_sealed_parameters``
    pattern from tests/test_prereg.py) rather than ``sys.path.insert`` +
    ``import``, which pyright's static resolver cannot see and flags as a
    missing import."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "spine_pilot_report.py"
    spec = importlib.util.spec_from_file_location("_spine_pilot_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_judge_b1_detects_policy_chasing_inflation(report):
    from ah.gen.spine import SpinePaths

    months = 40
    t = np.arange(months)
    mu_pi = 2.0
    gap_true = 2.0 * np.sin(2 * np.pi * t / 20)
    pi_star = mu_pi + gap_true

    # dpol[i] (policy change from month i to i+1) tracks gap_true 6 months
    # earlier: dpol[i] = gap_true[i - 6] for i >= 6, else 0.
    dpol = np.array([gap_true[i - 6] if i >= 6 else 0.0 for i in range(months - 1)])
    policy = np.concatenate([[0.0], np.cumsum(dpol)])

    states = np.zeros((1, months, 5))
    states[0, :, 0] = pi_star
    labels = np.zeros((1, months), dtype=np.int64)
    cycle = np.zeros((1, months))
    sealed = {"lag_months": [3, 12], "min_sign_fraction": 0.9}

    sp = SpinePaths(
        states=states,
        labels=labels,
        cycle=cycle,
        policy=policy.reshape(1, months),
        mu_pi=np.array([mu_pi]),
        pi_actual=states[:, :, 0].copy(),  # no noise in this synthetic build
        attempts=1,
        seed=1,
    )
    result = report.judge_b1(sp, sealed)
    assert result["pass"] is True
    assert result["value"] == 1.0

    sp_flat = SpinePaths(
        states=states,
        labels=labels,
        cycle=cycle,
        policy=np.zeros((1, months)),  # constant policy -> zero-variance dpol
        mu_pi=np.array([mu_pi]),
        pi_actual=states[:, :, 0].copy(),  # no noise in this synthetic build
        attempts=1,
        seed=1,
    )
    result_flat = report.judge_b1(sp_flat, sealed)
    assert result_flat["pass"] is False
    assert result_flat["value"] == 0.0


def test_judge_b4_fails_short_spells(report):
    from ah.gen.spine import CONTRACTION_CODES, SpinePaths

    rec_code = next(iter(CONTRACTION_CODES))
    exp_code = max(CONTRACTION_CODES) + 1000  # certainly not in CONTRACTION_CODES

    months = 40  # 5 full 8-month cycles -> five 2-month spells per quadrant
    labels = np.zeros(months, dtype=np.int64)
    pi = np.zeros(months)
    for i in range(months):
        phase = (i // 2) % 4
        if phase == 0:  # recession: contracting, cool
            labels[i], pi[i] = rec_code, 0.0
        elif phase == 1:  # stagflation: contracting, hot
            labels[i], pi[i] = rec_code, 1.0
        elif phase == 2:  # recovery: expanding, cool
            labels[i], pi[i] = exp_code, 0.0
        else:  # expansion: expanding, hot
            labels[i], pi[i] = exp_code, 1.0

    states = np.zeros((1, months, 5))
    states[0, :, 0] = pi
    sp = SpinePaths(
        states=states,
        labels=labels.reshape(1, months),
        cycle=np.zeros((1, months)),
        policy=np.zeros((1, months)),
        mu_pi=np.zeros(1),
        pi_actual=states[:, :, 0].copy(),  # no noise in this synthetic build
        attempts=1,
        seed=1,
    )
    sealed = {
        "panel_dwell_medians": [5.0, 4.0, 9.0, 6.0],
        "dwell_median_ratio_band": [0.6, 1.4],
        "quadrants": ["recession", "stagflation", "recovery", "expansion"],
        "clockwise_fraction_tolerance": 0.15,
        "panel_clockwise_fraction": 0.6029411764705882,
    }
    result = report.judge_b4(sp, sealed)
    assert result["pass"] is False
    for row in result["dwell"]:
        assert row["median"] == 2.0
        assert row["ratio"] < 0.6
        assert row["pass"] is False


def test_judge_b5_zero_rate_convention(report):
    sealed = {
        "panel_rates": [0.010752688172043012, 0.07017543859649122, 0.0, 0.004273504273504274],
        "panel_cell_months": [93, 57, 378, 234],
        "min_cell_months": 24,
        "rel_tolerance": 0.5,
    }
    # quadrant 2's sealed rate is exactly 0; one realized onset there must fail.
    cond_fail = {
        "corrections": {
            "per_quadrant_onsets": [1, 4, 1, 1],
            "per_quadrant_months": [93, 57, 378, 234],
        }
    }
    result_fail = report.judge_b5(cond_fail, sealed)
    assert result_fail["pass"] is False
    assert result_fail["table"][2]["pass"] is False

    # zero realized onsets in quadrant 2 satisfies the zero-rate convention;
    # the other three quadrants match their sealed rates closely.
    cond_pass = {
        "corrections": {
            "per_quadrant_onsets": [1, 4, 0, 1],
            "per_quadrant_months": [93, 57, 378, 234],
        }
    }
    result_pass = report.judge_b5(cond_pass, sealed)
    assert result_pass["pass"] is True
    assert result_pass["table"][2]["pass"] is True


def test_judge_b6_three_way_outcome(report):
    from ah.gen.spine import CONTRACTION_CODES, SpinePaths

    rec_code = next(iter(CONTRACTION_CODES))
    exp_code = max(CONTRACTION_CODES) + 1000

    def build(months: int, tight_idx: list[int], onset_idx: list[int]) -> "SpinePaths":
        policy = np.full(months, -1.0)
        for i in tight_idx:
            policy[i] = 1.0
        labels = np.full(months, exp_code, dtype=np.int64)
        for i in onset_idx:
            labels[i] = rec_code
        states = np.zeros((1, months, 5))  # pi_star = r_star = 0 -> gap == policy
        return SpinePaths(
            states=states,
            labels=labels.reshape(1, months),
            cycle=np.zeros((1, months)),
            policy=policy.reshape(1, months),
            mu_pi=np.zeros(1),
            pi_actual=states[:, :, 0].copy(),  # no noise in this synthetic build
            attempts=1,
            seed=1,
        )

    sealed = {
        "k_months": 12,
        "spine_policy_gap_threshold_pp": 0.0,
        "panel_conditional_onset_rate": 0.2214765100671141,
        "panel_unconditional_onset_rate": 0.07731305449936629,
        "rel_tolerance": 0.5,
        "base_rate_disclosure": (
            "panel conditioning (curve inversion) covers 149/813 months; the "
            "spine-side conditioning fraction is unpinned; the Task-7 report MUST "
            "print both base rates, and a B6 FAIL with base rates differing by more "
            "than 2x is recorded as INCONCLUSIVE (construct mismatch), not a "
            "compiler defect"
        ),
    }

    months = 40
    tight_idx = [0, 6, 12, 18, 24]  # all < months - k_months(12) == 28

    # PASS: exactly one of five tight months is followed by an onset -> 0.2,
    # within 50% relative of the sealed 0.2215 and above the 0.0773 unconditional.
    r_pass = report.judge_b6(build(months, tight_idx, [3]), sealed)
    assert r_pass["verdict"] == "PASS"
    assert r_pass["pass"] is True

    # FAIL: same tight pattern, zero onsets ever -> value 0.0 (both magnitude
    # and sign miss), but the spine's own base rate (5/28) sits close to the
    # panel's (149/813) -- a real construct match, so a genuine FAIL.
    r_fail = report.judge_b6(build(months, tight_idx, []), sealed)
    assert r_fail["verdict"] == "FAIL"
    assert r_fail["pass"] is False

    # INCONCLUSIVE: every eligible month is "tight" -> spine base rate 1.0,
    # more than 2x the panel's ~0.183 -- a would-be FAIL reclassified because
    # the two constructs aren't comparable at this base rate.
    eligible = months - sealed["k_months"]
    r_inc = report.judge_b6(build(months, list(range(eligible)), []), sealed)
    assert r_inc["verdict"] == "INCONCLUSIVE (construct mismatch)"
    assert r_inc["pass"] is False


# --------------------------------------------------------------------------- #
# spine-02 (Task 11): v2 judges, and the freeze test protecting the round-one
# record (B2/B3/B4 judges above are untouched by this task).
# --------------------------------------------------------------------------- #


def test_v1_judges_are_frozen(report):
    """B1/B2/B4/B5/B6 above are the round-one record; v2 lives beside them,
    never inside them. Hashes captured 2026-08-16 from the file as it stood
    immediately before Task 11 added the v2 judges -- any future edit to a
    v1 judge's body (even a no-op refactor) changes its source text and
    trips this test."""
    import hashlib
    import inspect

    expected = {
        "judge_b1": "5bc4bbffbf31f98755aba6789a0ead051f9c0ccb5285617d8fd9ab393753cd9a",
        "judge_b2": "bbd1287effb7a6435b5981a39d72cea584685af207429e0de6178fe40dfe7f6b",
        "judge_b4": "9935e5ab09fdbe1ca30df7f5cbae25e0a808d500138387cb030897924b7072fa",
        "judge_b5": "c88d0644144d672f67d0361400952a1f1602c72b23b367cde248354e97b8293b",
        "judge_b6": "cb091ca0b1411ab3b056bdaa47b3956d93999f8f167c8c0ed7b19b5f6abc0f0e",
    }
    for name, want in expected.items():
        fn = getattr(report, name)
        got = hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()
        assert got == want, f"{name}'s source changed -- v1 judges must stay byte-identical"


def test_judge_b1_v2_responds_at_the_contemporaneous_lag(report):
    from ah.gen.spine import SpinePaths

    months = 40
    t = np.arange(months)
    gap_true = 2.0 * np.sin(2 * np.pi * t / 20)  # the transitory surprise, pi_actual - pi_star
    pi_star = np.zeros(months)
    pi_actual = pi_star + gap_true
    sealed = {"min_sign_fraction": 0.9}

    # a responder: dpol[i] == gap_true[i - 1] for i >= 1 -- the anchor moves
    # ONE month after the surprise, inside v2's 0..2 window (v1's 3..12
    # window would have missed this lag entirely).
    lag = 1
    g = gap_true[:-1]
    dpol = np.zeros(months - 1)
    dpol[lag:] = g[: len(g) - lag]
    policy = np.concatenate([[0.0], np.cumsum(dpol)])

    states = np.zeros((1, months, 5))
    states[0, :, 0] = pi_star
    labels = np.zeros((1, months), dtype=np.int64)
    cycle = np.zeros((1, months))

    sp = SpinePaths(
        states=states,
        labels=labels,
        cycle=cycle,
        policy=policy.reshape(1, months),
        mu_pi=np.zeros(1),
        pi_actual=pi_actual.reshape(1, months),
        attempts=1,
        seed=1,
    )
    result = report.judge_b1_v2(sp, sealed)
    assert result["pass"] is True
    assert result["value"] == 1.0
    assert result["decades"][0]["lag"] == lag
    assert result["decades"][0]["corr"] == pytest.approx(1.0)

    # a non-responder: a constant policy anchor -> zero-variance dpol at
    # every lag -> corr guarded to 0.0 at all three lags -> fails.
    sp_flat = SpinePaths(
        states=states,
        labels=labels,
        cycle=cycle,
        policy=np.zeros((1, months)),
        mu_pi=np.zeros(1),
        pi_actual=pi_actual.reshape(1, months),
        attempts=1,
        seed=1,
    )
    result_flat = report.judge_b1_v2(sp_flat, sealed)
    assert result_flat["pass"] is False
    assert result_flat["value"] == 0.0


def test_judge_b5_v2_interval_arithmetic(report):
    # hand-computed: expected = 100*.01 + 50*.07 + 300*0 + 200*.004 = 5.3;
    # var = 100*.01*.99 + 50*.07*.93 + 0 + 200*.004*.996 = .99+3.255+0+.7968
    # = 5.0418 -> sd ~= 2.2454; band = 1.959963984540054*sd + 0.5 ~= 4.901.
    sealed = {"panel_rates": [0.01, 0.07, 0.0, 0.004]}
    months = [100, 50, 300, 200]

    def cond(onsets: list[int]) -> dict:
        return {"corrections": {"per_quadrant_onsets": onsets, "per_quadrant_months": months}}

    # observed 5: |5 - 5.3| = 0.3 <= ~4.901 -> inside the band -> pass.
    r_pass = report.judge_b5_v2(cond([2, 2, 0, 1]), sealed)
    assert r_pass["expected"] == pytest.approx(5.3)
    assert r_pass["sd"] == pytest.approx(2.2454, abs=1e-3)
    assert r_pass["margin"] == pytest.approx(4.9013, abs=1e-3)
    assert r_pass["observed"] == 5
    assert r_pass["aggregate_pass"] is True
    assert r_pass["pass"] is True

    # observed 12: |12 - 5.3| = 6.7 > ~4.901 -> outside the band -> fail.
    r_fail = report.judge_b5_v2(cond([5, 5, 0, 2]), sealed)
    assert r_fail["observed"] == 12
    assert r_fail["aggregate_pass"] is False
    assert r_fail["pass"] is False

    # the sealed zero-rate quadrant (index 2) firing even once is a wiring
    # violation and fails b5_v2 outright, regardless of the aggregate.
    r_wiring = report.judge_b5_v2(cond([1, 1, 1, 1]), sealed)  # observed 4, well inside the band
    assert r_wiring["aggregate_pass"] is True
    assert r_wiring["zero_rate_ok"] is False
    assert r_wiring["pass"] is False


def test_judge_b6_v2_quantile_matched_base_rate(report):
    from ah.gen.spine import CONTRACTION_CODES, SpinePaths

    rec_code = next(iter(CONTRACTION_CODES))
    exp_code = max(CONTRACTION_CODES) + 1000

    eligible_end = 100
    k = 12
    months = eligible_end + k
    positions = [0, 15, 30, 45, 60]  # spaced > k apart -> disjoint k-month onset windows

    def build(spike: bool, onset_idx: list[int]) -> "SpinePaths":
        g = np.zeros(eligible_end)
        if spike:
            g[positions] = 100.0
        g = np.concatenate([g, np.zeros(k)])
        labels = np.full(months, exp_code, dtype=np.int64)
        for i in onset_idx:
            labels[i] = rec_code
        states = np.zeros((1, months, 5))  # pi_star = r_star = 0 -> g == policy
        return SpinePaths(
            states=states,
            labels=labels.reshape(1, months),
            cycle=np.zeros((1, months)),
            policy=g.reshape(1, months),
            mu_pi=np.zeros(1),
            pi_actual=states[:, :, 0].copy(),
            attempts=1,
            seed=1,
        )

    sealed = {
        "k_months": k,
        "panel_base_rate": 0.05,  # 5/100 -> exactly the 5 spikes above the 95th percentile
        "panel_conditional_onset_rate": 0.4,
        "panel_unconditional_onset_rate": 0.05,
        "rel_tolerance": 0.5,
    }

    # PASS: 2 of the 5 tight (spike) months are followed by an onset within
    # k -> value 2/5 == the sealed 0.4 exactly; base rate matches by
    # construction (quantile-matched to panel_base_rate).
    r_pass = report.judge_b6_v2(build(True, [16, 46]), sealed)
    assert r_pass["tight_months"] == 5
    assert r_pass["spine_base_rate"] == pytest.approx(0.05)
    assert r_pass["value"] == pytest.approx(0.4)
    assert r_pass["verdict"] == "PASS"
    assert r_pass["pass"] is True

    # FAIL: same 5 tight months, zero followed by any onset -> value 0.0
    # (both magnitude and sign miss), but the base rates still match (both
    # 0.05) -- a real construct match, so a genuine FAIL, not INCONCLUSIVE.
    r_fail = report.judge_b6_v2(build(True, []), sealed)
    assert r_fail["value"] == 0.0
    assert r_fail["base_rate_ratio"] == pytest.approx(1.0)
    assert r_fail["verdict"] == "FAIL"
    assert r_fail["pass"] is False

    # INCONCLUSIVE: a degenerate, tie-saturated g (no spikes at all) collapses
    # every quantile threshold to the tie value itself, so nothing is ever
    # strictly greater than it -- tight_months == 0, spine base rate 0.0 vs
    # the sealed 0.05 -> base_rate_ratio == inf -> reclassified INCONCLUSIVE.
    # This path should be unreachable on a real spine (the quantile match
    # holds there by construction); it stays exercised here so the three-way
    # structure is proven, not just asserted in prose.
    r_inc = report.judge_b6_v2(build(False, []), sealed)
    assert r_inc["tight_months"] == 0
    assert r_inc["base_rate_ratio"] == float("inf")
    assert r_inc["verdict"] == "INCONCLUSIVE (construct mismatch)"
    assert r_inc["pass"] is False


# --------------------------------------------------------------------------- #
# Task 12: THE SPINE-02 SEAL -- the re-run's pre-registration. After this
# commit, only measurement is allowed (COMMIT-ORDER: before any Task-13
# ensemble is drawn). docs/superpowers/specs/spine02-prereg.json carries
# b2/b3/b4 verbatim from round one (unchanged by the Task-11 judge respec)
# and locks the new b1_v2/b5_v2/b6_v2 bars the v2 judges above read.
# --------------------------------------------------------------------------- #

SPINE02_SEAL_PATH = "docs/superpowers/specs/spine02-prereg.json"

#: The exact ten paths scripts/spine02_seal.py hashes (nine tracked files
#: plus itself). Kept here, independent of the seal script's own dict, so a
#: seal-script edit that silently drops a path from the hash set is still
#: caught by test_spine02_seal_hashes_match iterating this list.
SPINE02_HASHED_FILES = [
    "src/ah/gen/spine.py",
    "src/ah/gen/stress.py",
    "src/ah/gen/bootstrap.py",
    "src/ah/gen/regimes/semimarkov.py",
    "src/ah/gen/climate/model.py",
    "src/ah/gen/climate/simulate.py",
    "scripts/spine_pilot_report.py",
    "scripts/spine_pilot_b3.py",
    "src/ah/presets/spine_pilot.json",
    "scripts/spine02_seal.py",
]


def test_spine02_seal_carries_round_one_bars_verbatim():
    """b2/b3/b4 are unchanged by the Task-11 judge respec (only B1/B5/B6 were
    respecified), so the spine02 seal must carry them byte-for-byte from the
    round-one seal -- not recompute or hand-retype them. Compared via
    ``json.dumps(..., sort_keys=True)`` rather than raw ``==`` so the check
    is about VALUE equality, not incidental key-order equality (both files
    are in fact sort_keys-serialized already, but the comparison shouldn't
    depend on that)."""
    import json
    from pathlib import Path

    round_one = json.loads(
        Path("docs/superpowers/specs/spine-pilot-prereg.json").read_text(encoding="utf-8")
    )
    spine02 = json.loads(Path(SPINE02_SEAL_PATH).read_text(encoding="utf-8"))

    for key in ("b2", "b3", "b4"):
        assert key in spine02, f"spine02 seal missing {key}"
        assert json.dumps(spine02[key], sort_keys=True) == json.dumps(
            round_one[key], sort_keys=True
        ), f"spine02 seal's {key} block is not byte-identical to round one's"


def test_spine02_seal_hashes_match():
    """Same pattern as round one's test_prereg_seal_exists_and_hashes_match,
    but against the CURRENT working tree, not a historical git blob: this
    seal binds THIS round's tree (spine-02 has been editing it freely since
    Task 10; this seal is the point where that editing stops), so the sealed
    hashes must match the files as they sit on disk right now, not as they
    stood at some earlier commit."""
    import hashlib
    import json
    from pathlib import Path

    sealed = json.loads(Path(SPINE02_SEAL_PATH).read_text(encoding="utf-8"))
    for key in ("b2", "b3", "b4", "b1_v2", "b5_v2", "b6_v2"):
        assert key in sealed, f"spine02 seal missing {key}"

    assert set(sealed["hashes"]) == set(SPINE02_HASHED_FILES)
    for rel in SPINE02_HASHED_FILES:
        want = sealed["hashes"][rel]
        got = hashlib.sha256(Path(rel).read_bytes()).hexdigest()
        assert got == want, (
            f"spine02 seal hash mismatch for {rel}: the working tree no longer "
            "matches the sealed hash -- either the file changed since Task 12's "
            "seal (a real pre-registration violation) or the seal needs re-cutting"
        )


def test_spine02_thresholds_are_pinned_by_literals():
    """Every sealed b1_v2/b5_v2/b6_v2 value, asserted as a literal (same
    rationale as round one's test_prereg_thresholds_are_pinned_by_literals:
    the hash test alone only catches a BYTE change, not a seal-script bug
    that recomputes a DIFFERENT number into the SAME schema). b2/b3/b4 are
    covered by test_spine02_seal_carries_round_one_bars_verbatim above, not
    repeated here.

    ``panel_base_rate`` gets both a literal (the value actually observed in
    the committed JSON) and an exact-equality check against ``149 / 813``,
    per the Task-12 brief -- so this test also pins the ARITHMETIC, not just
    whatever float happened to land in the file.
    """
    import json
    from pathlib import Path

    sealed = json.loads(Path(SPINE02_SEAL_PATH).read_text(encoding="utf-8"))

    assert sealed["b1_v2"]["min_sign_fraction"] == 0.90
    assert sealed["b1_v2"]["lag_months"] == [0, 2]

    assert sealed["b5_v2"]["panel_rates"] == [
        0.010752688172043012,
        0.07017543859649122,
        0.0,
        0.004273504273504274,
    ]
    assert sealed["b5_v2"]["method"] == "aggregate-binomial-normal-approx-cc"
    assert sealed["b5_v2"]["alpha"] == 0.05
    assert sealed["b5_v2"]["z"] == 1.959963984540054
    assert sealed["b5_v2"]["per_quadrant"] == "disclosure-only"
    assert sealed["b5_v2"]["zero_rate_convention"] == (
        "a panel rate of exactly 0 passes iff the realized rate is exactly 0; "
        "note the recovery cell is tautological (the sampler cannot fire at rate "
        "0), so a PASS there is a plumbing assertion, not evidence about the model"
    )

    assert sealed["b6_v2"]["k_months"] == 12
    assert sealed["b6_v2"]["panel_base_rate"] == 0.18327183271832717
    assert abs(sealed["b6_v2"]["panel_base_rate"] - 149 / 813) == 0.0
    assert sealed["b6_v2"]["rel_tolerance"] == 0.5
    assert sealed["b6_v2"]["panel_conditional_onset_rate"] == 0.2214765100671141
    assert sealed["b6_v2"]["panel_unconditional_onset_rate"] == 0.07731305449936629
    assert sealed["b6_v2"]["conditioning"] == (
        "per-decade quantile-matched to the panel inversion base rate"
    )

    assert sealed["sensitivity_seeds"] == [199002, 1199005, 2199008, 3199011, 4199014]

    assert sealed["round_one_record"] == {
        "seal": "docs/superpowers/specs/spine-pilot-prereg.json",
        "prereg_commit": "c9bd03621424becf24dcb603ac7ef725ff9a53ab",
        "measured_state_commit": "233b70d30157e2e06e80e447f410c03afc5d1f68",
        "verdicts": "docs/superpowers/specs/2026-08-15-spine-pilot-results.md",
    }
