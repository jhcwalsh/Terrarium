"""The stress-scenario compiler (bootstrap-stratified)."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.stress import eligible_rows, join_candidates, severity_score

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
