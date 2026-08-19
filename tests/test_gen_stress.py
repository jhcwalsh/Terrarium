"""The stress-scenario compiler (bootstrap-stratified)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.gen.stress import (
    StressBootstrap,
    StressError,
    eligible_rows,
    join_candidates,
    severity_score,
)

NAMES = ["equity_mkt", "hy_spread", "ust_10y", "cpi"]
ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _load_script(name: str):
    """Load a scripts/ module by path (the test_prereg.py pattern -- resolvable
    without putting scripts/ on pyright's import path)."""
    spec = importlib.util.spec_from_file_location(f"_{name}", ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stress_report = _load_script("stress_report")
depth_report = _stress_report.depth_report
coherence_report = _stress_report.coherence_report
plausibility_report = _stress_report.plausibility_report


def _panel() -> np.ndarray:
    """Four hand-built months. Row 0 calm; row 1 equity crash WITH a bond rally
    (2008-shaped); row 2 everything down together (2022-shaped); row 3 mild."""
    return np.array(
        [
            [+0.01, 3.0, 4.0, 100.0],  # calm
            [-0.15, 9.0, 2.0, 100.0],  # equity -15%, spreads wide, yields FALL (rally)
            [-0.08, 7.0, 6.0, 100.0],  # equity -8%, spreads wide, yields RISE (no bid)
            [-0.01, 3.5, 4.1, 100.0],  # mild
        ]
    )


def test_equity_functional_ranks_the_deepest_equity_month_worst():
    s = severity_score(_panel(), NAMES, "equity")
    assert int(np.argmin(s)) == 1  # -15% is the worst equity month


def test_all_down_prefers_the_month_with_no_flight_to_quality_bid():
    """The point of the default. Row 1 is a deeper equity fall, but bonds
    rallied, so the institution can still sell its liquid leg. Row 2 is
    shallower and has no hiding place, which is what breaks an illiquid book."""
    s = severity_score(_panel(), NAMES, "all_down")
    assert int(np.argmin(s)) == 2
    assert s[2] < s[1]


def test_joint_risk_uses_equity_and_credit_only_and_ignores_the_bond_leg():
    s = severity_score(_panel(), NAMES, "joint_risk")
    assert int(np.argmin(s)) == 1  # deepest equity + widest spread


def test_severity_is_deterministic():
    a = severity_score(_panel(), NAMES, "all_down")
    b = severity_score(_panel(), NAMES, "all_down")
    np.testing.assert_array_equal(a, b)


def test_eligible_rows_are_the_worst_share_and_100_is_unrestricted():
    scores = np.array([5.0, 1.0, 3.0, 4.0, 2.0])
    assert eligible_rows(scores, 40.0).tolist() == [1, 4]  # worst two of five
    assert eligible_rows(scores, 100.0).tolist() == [0, 1, 2, 3, 4]


def test_eligible_rows_never_returns_an_empty_pool():
    """A percentile so tight it selects nothing would make the segment
    unsamplable. The floor is one row — the single worst."""
    scores = np.array([5.0, 1.0, 3.0])
    assert eligible_rows(scores, 0.001).tolist() == [1]


def test_unknown_functional_is_refused_by_name():
    with pytest.raises(ValueError, match="vibes"):
        severity_score(_panel(), NAMES, "vibes")


def test_join_candidates_exclude_a_spread_teleport():
    """From a 3.0 spread with a 1.5 tolerance, a 9.0 row is unreachable."""
    values, names = _panel(), NAMES
    pool = np.array([0, 1, 2, 3], dtype=np.int64)
    got = join_candidates(values, names, current_row=0, tolerance={"hy_spread": 1.5}, pool=pool)
    assert 1 not in got.tolist()  # 9.0 vs 3.0 is a 6.0 jump
    assert 3 in got.tolist()  # 3.5 vs 3.0 is within tolerance


def test_join_candidates_apply_every_named_factor():
    values, names = _panel(), NAMES
    pool = np.array([0, 1, 2, 3], dtype=np.int64)
    loose = join_candidates(values, names, 0, {"hy_spread": 10.0}, pool)
    tight = join_candidates(values, names, 0, {"hy_spread": 10.0, "ust_10y": 0.5}, pool)
    assert set(tight.tolist()) < set(loose.tolist())


def test_an_untoleranced_factor_does_not_constrain():
    values, names = _panel(), NAMES
    pool = np.array([0, 1, 2, 3], dtype=np.int64)
    got = join_candidates(values, names, 0, {}, pool)
    np.testing.assert_array_equal(got, pool)


def test_join_candidates_may_be_empty_and_the_caller_decides():
    """An empty candidate set is a real state: nothing severe is reachable from
    here without teleporting. The sampler CONTINUES the block rather than
    jumping (Task 4) — severity is a preference over entries, never a licence
    to teleport."""
    values, names = _panel(), NAMES
    pool = np.array([1], dtype=np.int64)
    got = join_candidates(values, names, 0, {"hy_spread": 0.1}, pool)
    assert got.size == 0


# --------------------------------------------------------------------------- #
# Task 4: the sampler (StressBootstrap)
# --------------------------------------------------------------------------- #


def _tiny_source():
    """A BootstrapSource whose every column is injective in the row index, so
    'this month IS that historical month' can be checked exactly rather than
    statistically — the technique tests/test_bootstrap.py uses.

    Carries a fifth column, policy_rate, alongside the original four: the
    stress_1974 preset's join_tolerance names policy_rate (Task 5), and a
    restart is all but certain over a 120-month sample, so join_candidates
    must find every factor its tolerance names."""
    import pandas as pd

    from ah.gen.bootstrap import BootstrapSource

    n = 60
    rows = np.arange(n, dtype=np.float64)
    values = np.column_stack([rows, rows + 1000.0, rows + 2000.0, rows + 3000.0, rows + 4000.0])
    return BootstrapSource(
        factor_names=("equity_mkt", "hy_spread", "ust_10y", "cpi", "policy_rate"),
        dates=pd.date_range("1960-01-31", periods=n, freq="ME"),
        values=values,
        labels=tuple(["EXP"] * n),
        ruleset_version="test",
        vintage_id="test-vintage",
        active_blocks=("global",),
    )


def _spec(entry_percentile=100.0, mean_block_months=6, tolerance=None):
    from ah.core.worldspec import StressSegment, StressSpec

    return StressSpec(
        functional="all_down",
        segments=[
            StressSegment(
                from_quarter=0,
                to_quarter=39,
                entry_percentile=entry_percentile,
                mean_block_months=mean_block_months,
            )
        ],
        join_tolerance=tolerance or {},
        precedent=["test"],
    )


def test_every_emitted_month_is_a_real_panel_row():
    """THE claim. Bit-exact on the whole factor vector, not approximately."""
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(120, 8, seed=11, stress=_spec())
    assert ens.row_indices is not None
    src = gen.source.values
    for p in range(ens.n_paths):
        for m in range(ens.months):
            row = int(ens.row_indices[p, m])
            np.testing.assert_array_equal(ens.paths[p, m, :], src[row, :])


def test_blocks_are_contiguous_runs_of_whole_rows():
    """Co-movement is real because a block is ONE shared row index across every
    factor, advancing by one month at a time."""
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(120, 8, seed=11, stress=_spec())
    assert ens.row_indices is not None
    idx = ens.row_indices
    n = gen.source.n_rows
    steps = (idx[:, 1:] - idx[:, :-1]) % n
    continued = steps == 1
    assert continued.mean() > 0.5, "most months must continue a block, not restart it"


def test_same_seed_same_tape():
    gen = StressBootstrap(_tiny_source())
    a = gen.sample_months(60, 4, seed=7, stress=_spec())
    b = gen.sample_months(60, 4, seed=7, stress=_spec())
    np.testing.assert_array_equal(a.paths, b.paths)
    c = gen.sample_months(60, 4, seed=8, stress=_spec())
    assert not np.array_equal(a.paths, c.paths)


def test_restarts_land_in_the_severity_pool():
    """Severity binds where it is supposed to: on ENTRY. Every restart row must
    be in the declared pool; continuation rows need not be."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    spec = _spec(entry_percentile=20.0)
    ens = gen.sample_months(120, 8, seed=3, stress=spec)
    assert ens.row_indices is not None
    pool = set(
        eligible_rows(severity_score(source.values, source.factor_names, "all_down"), 20.0).tolist()
    )
    idx = ens.row_indices
    n = source.n_rows
    for p in range(idx.shape[0]):
        assert int(idx[p, 0]) in pool
        for m in range(1, idx.shape[1]):
            if (int(idx[p, m]) - int(idx[p, m - 1])) % n != 1:
                assert int(idx[p, m]) in pool, "a restart landed outside the severity pool"


def test_a_block_continues_rather_than_teleporting_when_no_join_is_reachable():
    """With an impossibly tight tolerance nothing is reachable, so the sampler
    must keep advancing through real history rather than jumping."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    ens = gen.sample_months(
        60, 4, seed=5, stress=_spec(entry_percentile=20.0, tolerance={"hy_spread": 0.0})
    )
    assert ens.row_indices is not None
    idx = ens.row_indices
    n = source.n_rows
    steps = (idx[:, 1:] - idx[:, :-1]) % n
    assert bool(np.all(steps == 1)), "no join was reachable; every month must continue"


def test_the_ensemble_stamps_the_scenario_for_audit():
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(60, 4, seed=5, stress=_spec(entry_percentile=15.0))
    c = ens.meta.conditioning
    assert ens.meta.generator_id == "bootstrap-stratified"
    assert c["functional"] == "all_down"
    assert c["segments"][0]["entry_percentile"] == 15.0
    assert c["pool_sizes"][0] > 0
    assert c["factor_conditions_honoured"] is False
    assert c["provenance"] == "declared"  # spec v0.2 S5: never search-derived here


def test_a_quarter_outside_every_segment_raises_a_named_stress_error():
    """StressSpec only checks that segments tile with no gap/overlap; it never
    checks against the world's horizon (parked finding from Task 1's review).
    A spec that tiles quarters 0-19 sampled for 40 quarters (120 months) must
    raise, naming the offending quarter, rather than silently running past the
    declared scenario."""
    from ah.core.worldspec import StressSegment, StressSpec

    short_spec = StressSpec(
        functional="all_down",
        segments=[
            StressSegment(
                from_quarter=0, to_quarter=19, entry_percentile=100.0, mean_block_months=6
            )
        ],
        join_tolerance={},
        precedent=["test"],
    )
    gen = StressBootstrap(_tiny_source())
    with pytest.raises(
        StressError, match="quarter 20 is covered by no stress segment; segments end at quarter 19"
    ):
        gen.sample_months(120, 2, seed=1, stress=short_spec)


def test_a_paths_tape_does_not_depend_on_how_many_paths_ride_along():
    """Path 0's tape must be a pure function of (seed, path index) -- never of
    n_paths. A shared RNG stream consumed path-major would make an earlier
    path's outcome depend on how many later paths are drawn alongside it,
    because the entry draw and every restart's destination draw consume a
    variable, path-count-dependent number of stream words. Reviewed finding:
    reproduced with the pre-fix code (seed=7, 60 months, empty tolerance) as
    path 0 = [59, 0, 1, 2, ...] at n_paths=4 but [59, 0, 52, 53, ...] at
    n_paths=8 -- the SAME logical path, different outcomes."""
    gen = StressBootstrap(_tiny_source())
    a = gen.sample_months(60, 4, seed=7, stress=_spec())
    b = gen.sample_months(60, 8, seed=7, stress=_spec())
    assert a.row_indices is not None
    assert b.row_indices is not None
    np.testing.assert_array_equal(a.row_indices[0], b.row_indices[0])


def test_pool_sizes_are_stamped_for_every_declared_segment_even_unvisited_ones():
    """pool_sizes describes the DECLARED spec, not a trace of what the draw
    happened to visit. A two-segment spec sampled for fewer months than needed
    to reach the second segment must still succeed and stamp both segments'
    pool sizes, rather than KeyError on the segment the draw never touched."""
    from ah.core.worldspec import StressSegment, StressSpec

    two_segment_spec = StressSpec(
        functional="all_down",
        segments=[
            StressSegment(
                from_quarter=0, to_quarter=19, entry_percentile=100.0, mean_block_months=6
            ),
            StressSegment(
                from_quarter=20, to_quarter=39, entry_percentile=50.0, mean_block_months=6
            ),
        ],
        join_tolerance={},
        precedent=["test"],
    )
    gen = StressBootstrap(_tiny_source())
    # 60 months = quarters 0-19 only; the second segment (quarters 20-39) is
    # never reached by the draw.
    ens = gen.sample_months(60, 2, seed=1, stress=two_segment_spec)
    pool_sizes = ens.meta.conditioning["pool_sizes"]
    assert len(pool_sizes) == 2
    assert all(size > 0 for size in pool_sizes)


def test_sample_raises_when_the_world_declares_no_x_stress():
    """sample() (not sample_months()) is the Generator-protocol entry point;
    it must refuse a world that selects bootstrap-stratified but never
    declared extensions.x_stress, naming x_stress in the error."""
    doc = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    world = project_numeric(WorldSpec.model_validate(doc))
    assert world.stress is None  # this preset declares no x_stress

    gen = StressBootstrap(_tiny_source())
    with pytest.raises(StressError, match="x_stress"):
        gen.sample(world, n_paths=2, seed=1)


# --------------------------------------------------------------------------- #
# Task 5: registration -- the first declared scenario, and the dispatcher
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "preset",
    [
        "stress_1974.json",
        "stress_1990.json",
        # er14-06: the successors (701/703 retired with no playable successor
        # in the picker's declared-stress family; the third is a new
        # demonstration world, not a rebuild) exercise the same path.
        "stress_1974_successor.json",
        "stress_1990_successor.json",
    ],
)
def test_the_stress_preset_builds_samples_and_replays(tmp_path, preset):
    doc = json.loads((PRESETS / preset).read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.engine_defaults.generator_id == "bootstrap-stratified"
    assert nw.stress is not None and nw.stress.functional == "all_down"
    gen = StressBootstrap(_tiny_source())
    a = gen.sample(nw, n_paths=4, seed=197400)
    b = gen.sample(nw, n_paths=4, seed=197400)
    np.testing.assert_array_equal(a.paths, b.paths)


def test_the_lost_decade_declares_persistence_not_deeper_percentiles():
    """The D-SC-1 discipline, pinned: stress_1990's extra severity comes ONLY
    from the declared SHAPE (a 21-month crisis, no recovery segment, 40/40
    quarters restricted) - its percentiles are byte-for-byte stress_1974's
    (10 crisis / 35 squeeze). If a future edit tightens a percentile, this
    test asks for the precedent."""
    d74 = json.loads((PRESETS / "stress_1974.json").read_text(encoding="utf-8"))
    d90 = json.loads((PRESETS / "stress_1990.json").read_text(encoding="utf-8"))
    p74 = {s["entry_percentile"] for s in d74["extensions"]["x_stress"]["segments"]}
    segs90 = d90["extensions"]["x_stress"]["segments"]
    p90 = {s["entry_percentile"] for s in segs90}
    assert p90 == p74 - {100.0}, "only the unrestricted tail may disappear"
    assert max(s["to_quarter"] for s in segs90) == 39
    assert all(s["entry_percentile"] <= 35 for s in segs90), "no recovery segment"
    crisis = [s for s in segs90 if s["entry_percentile"] == 10]
    assert len(crisis) == 1
    months = (crisis[0]["to_quarter"] - crisis[0]["from_quarter"] + 1) * 3
    assert months == 21, "the crisis length IS the 1973-74 precedent"


def test_a_stress_world_without_a_declared_rule_is_refused():
    doc = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    doc["engine_defaults"]["generator_id"] = "bootstrap-stratified"
    nw = project_numeric(WorldSpec.model_validate(doc))
    with pytest.raises(StressError, match="x_stress"):
        StressBootstrap(_tiny_source()).sample(nw, n_paths=2, seed=1)


def test_the_shared_id_routes_a_legacy_world_to_bootstrap_v1():
    """Sealed 1.0.x worlds carry bootstrap-stratified with no x_stress and must
    keep resolving to the legacy generator (spec v0.2 erratum)."""
    import ah.gen  # noqa: F401  - trigger both registrations in order
    from ah.gen import registry

    gen = registry.resolve("bootstrap-stratified")
    doc = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    doc["engine_defaults"]["generator_id"] = "bootstrap-stratified"
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.stress is None
    # the dispatcher exists precisely so this world does NOT hit StressError;
    # resolving the legacy route needs the catalog, so assert on the routing
    # object rather than sampling (no data/ dependency in unit tests)
    assert type(gen).__name__ == "_StressOrLegacyDispatch"


def test_the_shared_id_routes_a_stress_world_to_the_compiler(monkeypatch):
    """A world WITH x_stress must reach StressBootstrap through the dispatcher."""
    from ah.gen import stress as stress_mod

    captured = {}

    def fake_campaign_source():
        captured["called"] = True
        return _tiny_source()

    monkeypatch.setattr("ah.gen.bootstrap.campaign_source", fake_campaign_source)
    doc = json.loads((PRESETS / "stress_1974.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    dispatcher = stress_mod.stress_or_legacy_factory()
    ens = dispatcher.sample(nw, n_paths=2, seed=3)
    assert captured.get("called") is True
    assert ens.meta.generator_id == "bootstrap-stratified"
    assert ens.meta.conditioning["mode"] == "declared-stress-scenario"


def test_the_dispatcher_exposes_the_campaign_panel_as_its_source(monkeypatch):
    """ah/port/adapter.py's _source_of reads .source off the resolved generator
    (adapter.py:166); without this property every generated-world surface
    (ah run, the bundle, the programme console) fails with AdapterError."""
    from ah.gen import stress as stress_mod

    calls = {"n": 0}

    def fake_campaign_source():
        calls["n"] += 1
        return _tiny_source()

    monkeypatch.setattr("ah.gen.bootstrap.campaign_source", fake_campaign_source)
    d = stress_mod.stress_or_legacy_factory()
    # narrow from the Generator protocol: .source is the dispatcher's own seam
    assert isinstance(d, stress_mod._StressOrLegacyDispatch)
    a = d.source
    b = d.source
    assert a is b and calls["n"] == 1  # lazy, cached


# --------------------------------------------------------------------------- #
# Task 6: the reports -- emergent depth, coherence, plausibility
# --------------------------------------------------------------------------- #


def test_depth_report_reads_the_ensemble_it_is_given():
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(120, 8, seed=2, stress=_spec())
    d = depth_report(ens)
    assert set(d) >= {"median_peak_to_trough", "median_drawdown_months", "hy_spread_peak"}
    assert d["median_peak_to_trough"] <= 0.0


def test_coherence_report_compares_autocorrelation_against_the_panel():
    """A shuffle of the same months would score far below the panel; a block
    resample should land near it. This is the test that catches (a)/(b) of the
    design note breaking."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    ens = gen.sample_months(120, 8, seed=2, stress=_spec(mean_block_months=24))
    c = coherence_report(ens, source)
    assert c["join_count"] >= 0
    assert abs(c["ac1_generated"] - c["ac1_panel"]) < 0.35


def test_plausibility_report_measures_sequence_novelty_and_never_gates():
    """Spec v0.2 A2: real months, invented sequence -- the Mahalanobis statistic
    measures the novelty of the assembled sequence in rolling-12m space. The
    assertions here check the statistic COMPUTES and is self-consistent; no
    assertion bounds its value, because it is reported, never gating."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    ens = gen.sample_months(120, 8, seed=2, stress=_spec())
    p = plausibility_report(ens, source)
    assert set(p) >= {"mahalanobis_median", "mahalanobis_max", "panel_mahalanobis_p95"}
    assert 0.0 <= p["mahalanobis_median"] <= p["mahalanobis_max"]
    assert p["panel_mahalanobis_p95"] > 0.0
