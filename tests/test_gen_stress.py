"""The stress-scenario compiler (bootstrap-stratified)."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.stress import eligible_rows, severity_score

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
