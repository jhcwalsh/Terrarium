"""The stress-scenario compiler (bootstrap-stratified)."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.stress import (
    StressBootstrap,
    StressError,
    eligible_rows,
    join_candidates,
    severity_score,
)

NAMES = ["equity_mkt", "hy_spread", "ust_10y", "cpi"]


def _panel() -> np.ndarray:
    """Four hand-built months. Row 0 calm; row 1 equity crash WITH a bond rally
    (2008-shaped); row 2 everything down together (2022-shaped); row 3 mild."""
    return np.array([
        [+0.01, 3.0, 4.0, 100.0],   # calm
        [-0.15, 9.0, 2.0, 100.0],   # equity -15%, spreads wide, yields FALL (rally)
        [-0.08, 7.0, 6.0, 100.0],   # equity -8%, spreads wide, yields RISE (no bid)
        [-0.01, 3.5, 4.1, 100.0],   # mild
    ])


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
    assert eligible_rows(scores, 40.0).tolist() == [1, 4]     # worst two of five
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
    assert 1 not in got.tolist()   # 9.0 vs 3.0 is a 6.0 jump
    assert 3 in got.tolist()       # 3.5 vs 3.0 is within tolerance


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
    statistically — the technique tests/test_bootstrap.py uses."""
    import pandas as pd

    from ah.gen.bootstrap import BootstrapSource

    n = 60
    rows = np.arange(n, dtype=np.float64)
    values = np.column_stack([rows, rows + 1000.0, rows + 2000.0, rows + 3000.0])
    return BootstrapSource(
        factor_names=("equity_mkt", "hy_spread", "ust_10y", "cpi"),
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
        segments=[StressSegment(from_quarter=0, to_quarter=39,
                                entry_percentile=entry_percentile,
                                mean_block_months=mean_block_months)],
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
    pool = set(eligible_rows(
        severity_score(source.values, source.factor_names, "all_down"), 20.0).tolist())
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
    ens = gen.sample_months(60, 4, seed=5,
                            stress=_spec(entry_percentile=20.0, tolerance={"hy_spread": 0.0}))
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
    assert c["provenance"] == "declared"   # spec v0.2 S5: never search-derived here


def test_a_quarter_outside_every_segment_raises_a_named_stress_error():
    """StressSpec only checks that segments tile with no gap/overlap; it never
    checks against the world's horizon (parked finding from Task 1's review).
    A spec that tiles quarters 0-19 sampled for 40 quarters (120 months) must
    raise, naming the offending quarter, rather than silently running past the
    declared scenario."""
    from ah.core.worldspec import StressSegment, StressSpec

    short_spec = StressSpec(
        functional="all_down",
        segments=[StressSegment(from_quarter=0, to_quarter=19,
                                entry_percentile=100.0, mean_block_months=6)],
        join_tolerance={},
        precedent=["test"],
    )
    gen = StressBootstrap(_tiny_source())
    with pytest.raises(StressError, match="quarter 20 is covered by no stress segment; segments end at quarter 19"):
        gen.sample_months(120, 2, seed=1, stress=short_spec)
