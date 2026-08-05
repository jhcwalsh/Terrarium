"""Declared bands and the statistics they judge.

The bands are one allocator's priors, editable by design — these tests pin the
ARITHMETIC, never the priors, so re-declaring a band never breaks a test.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ah.play import PlayResult
from ah.programme import (
    PROGRAMME_PLAUSIBLE,
    ProgrammeQuarter,
    path_stats,
    programme_stats,
    vintage_stats,
)


def _pq(**overrides: Any) -> ProgrammeQuarter:
    """A hand-constructed quarter row, with every field defaulted except the
    ones a test cares about. Keeps path_stats tests focused on the field(s)
    under test rather than restating 17 irrelevant values each time."""
    fields: dict[str, Any] = {
        "quarter": 0,
        "month": 0,
        "drawdown_depth": 0.0,
        "spread_ratio": 1.0,
        "f_dist": 1.0,
        "f_call": 1.0,
        "calls": 0.0,
        "distributions": 0.0,
        "distributions_unlinked": 0.0,
        "cash": 0.0,
        "nav_true": 0.0,
        "nav_reported": 0.0,
        "private_nav": 0.0,
        "unfunded": 0.0,
        "private_weight_true": 0.0,
        "coverage_true": 0.0,
        "coverage_reported": 0.0,
        "forced_sale_total": 0.0,
    }
    fields.update(overrides)
    return ProgrammeQuarter(**fields)


def _play_result(forced_secondaries: int = 0) -> PlayResult:
    """A PlayResult with no quarters -- path_stats never reads them, only
    ``forced_secondaries``, so an empty ladder is a legitimate stand-in."""
    return PlayResult(
        quarters=[],
        final_value=0.0,
        forced_sale_quarters=0,
        total_forced_sales=0.0,
        forced_secondaries=forced_secondaries,
    )


def test_every_band_has_a_question_and_a_valid_range():
    assert PROGRAMME_PLAUSIBLE
    for name, band in PROGRAMME_PLAUSIBLE.items():
        assert band.lo < band.hi, name
        assert band.question.strip(), name


def test_stats_flag_only_outside_the_band():
    per_path = [{"dpi_age9": v} for v in (0.9, 1.0, 1.1)]
    stats = programme_stats(per_path, {"dpi_age9": 1.0})
    dpi = next(s for s in stats if s.name == "dpi_age9")
    assert not dpi.flagged
    per_path = [{"dpi_age9": v} for v in (0.1, 0.2, 0.3)]
    stats = programme_stats(per_path, {"dpi_age9": 0.2})
    dpi = next(s for s in stats if s.name == "dpi_age9")
    assert dpi.flagged


def test_stats_report_median_and_the_ten_ninety_spread():
    per_path = [{"dpi_age9": float(v)} for v in range(11)]  # 0..10, median 5
    stats = programme_stats(per_path, {"dpi_age9": 3.0})
    dpi = next(s for s in stats if s.name == "dpi_age9")
    assert dpi.median == 5.0
    assert dpi.p10 == 1.0
    assert dpi.p90 == 9.0
    assert dpi.path0 == 3.0


def test_a_missing_statistic_does_not_crash_the_report():
    """A world too short to define a statistic omits it rather than raising."""
    stats = programme_stats([{}, {}], {})
    assert stats == []


def test_vintage_stats_at_tier0_benchmark_growth_are_hand_checkable():
    """No market drama (dd=0, spread=1 throughout, so the linkage is 1.0),
    and NAV grows at tier 0's own frozen constant g_annual -- not zero --
    because these are questions about the model's cashflow SHAPE, and tier
    0's constant growth is what "the model's own shape" means. Zero growth
    makes the J-curve crossover arithmetically impossible (NAV can never
    outgrow calls net of distributions without growth) and caps DPI below
    1.0 structurally -- an artifact of a lazy test tape, not a finding
    about the model."""
    n = 36
    calm_dd = np.zeros(n)
    calm_spread = np.ones(n)
    out = vintage_stats(calm_dd, calm_spread, n)
    # rc_curve[0] = 0.25 annual on unfunded, quarterly => 6.25% of 1.0
    # committed. Returns don't affect the first call, so this is unchanged
    # by the growth basis.
    assert np.isclose(out["first_call"], 0.0625, rtol=1e-6)
    # paid_in=0.6924, cumulative distributions=0.7729 over 36 quarters of
    # tier-0 constant growth => dpi_age9 = 0.7729 / 0.6924 = 1.116.
    assert np.isclose(out["dpi_age9"], 1.116, atol=1e-3)
    assert 0.0 < out["call_rate_y1_3"] < 1.0
    # cumulative (distributions - calls) first turns positive at quarter
    # index 34 (0-based) => crossover_years = (34 + 1) / 4 = 8.75.
    assert out["crossover_years"] == 8.75


def test_path_stats_linkage_bite_is_a_rate_not_a_level():
    """A rate-based bite is ~1.0 when the distribution RATE is constant even
    as private NAV (and hence the distribution LEVEL) grows across the
    decade -- the ladder's own growth must not be able to masquerade as a
    linkage effect. A level-based implementation would instead compare the
    raw distribution amounts and land far from 1.0.

    private_nav = 1, 2, 3, 4, 5; rate is constant at 0.2, so
    distributions = 0.2, 0.4, 0.6, 0.8, 1.0. Deepest drawdown is quarter 3
    (private_nav=4, distribution=0.8), NOT the median-value quarter.

    Rate-based: every quarter's rate is exactly 0.2, so worst rate (0.2) /
    median rate (0.2) = 1.0 exactly, regardless of which quarter is "worst".
    Level-based (wrong): median distribution level = median(0.2,0.4,0.6,0.8,
    1.0) = 0.6; worst-quarter (deepest drawdown, q3) level = 0.8;
    0.8 / 0.6 = 1.333..., far from 1.0.
    """
    private_navs = [1.0, 2.0, 3.0, 4.0, 5.0]
    rate = 0.2
    depths = [0.10, 0.05, 0.02, 0.50, 0.01]  # deepest at index 3
    rows = [
        _pq(quarter=i, private_nav=nav, distributions=rate * nav, drawdown_depth=dd)
        for i, (nav, dd) in enumerate(zip(private_navs, depths, strict=True))
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["linkage_bite"], 1.0, atol=1e-9)


def test_path_stats_worst_quarter_is_selected_by_drawdown_not_distribution():
    """The "worst" quarter for linkage_bite must be the one with the
    DEEPEST DRAWDOWN, not the one with the lowest (or highest) distribution
    rate -- selecting on the distribution value instead would make the
    statistic circular ("the quarter with the lowest distributions has a
    low distribution rate").

    private_nav is constant at 1.0 so rate == distributions exactly, with
    no rate-vs-level confound. Rates (in quarter order): 0.5, 0.1, 0.9, 0.05.
    Deepest drawdown is quarter 2 (depth 0.9), whose rate (0.9) is the
    HIGHEST, not the lowest -- so a bug that picked the min-distribution
    quarter (quarter 3, rate 0.05) would be caught by this test.

    median(0.5, 0.1, 0.9, 0.05) = (0.1 + 0.5) / 2 = 0.3.
    linkage_bite = worst (0.9, picked by depth) / median (0.3) = 3.0.
    A min-distribution-selecting bug would instead compute 0.05 / 0.3 = 0.1667.
    """
    rates = [0.5, 0.1, 0.9, 0.05]
    depths = [0.01, 0.02, 0.90, 0.01]  # deepest at index 2
    rows = [
        _pq(quarter=i, private_nav=1.0, distributions=rate, drawdown_depth=dd)
        for i, (rate, dd) in enumerate(zip(rates, depths, strict=True))
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["linkage_bite"], 3.0, atol=1e-9)


def test_path_stats_linkage_shortfall_is_the_share_of_the_unlinked_total():
    """linked distributions = 1.0 + 2.0 + 3.0 = 6.0.
    unlinked distributions = 2.0 + 3.0 + 5.0 = 10.0.
    shortfall = (unlinked - linked) / unlinked = (10.0 - 6.0) / 10.0 = 0.4.
    """
    rows = [
        _pq(quarter=0, distributions=1.0, distributions_unlinked=2.0),
        _pq(quarter=1, distributions=2.0, distributions_unlinked=3.0),
        _pq(quarter=2, distributions=3.0, distributions_unlinked=5.0),
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["linkage_shortfall"], 0.4, atol=1e-9)


def test_path_stats_peak_unfunded_ratio_need_not_be_the_last_quarter():
    """unfunded/private_nav per quarter: 1/10=0.1, 5/10=0.5, 2/10=0.2.
    The peak (0.5) falls on the MIDDLE quarter -- a "last value" bug would
    wrongly report 0.2.
    """
    rows = [
        _pq(quarter=0, private_nav=10.0, unfunded=1.0),
        _pq(quarter=1, private_nav=10.0, unfunded=5.0),
        _pq(quarter=2, private_nav=10.0, unfunded=2.0),
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["peak_unfunded_ratio"], 0.5, atol=1e-9)


def test_path_stats_forced_secondaries_passes_through_the_play_result():
    rows = [_pq(quarter=0)]
    out = path_stats(rows, _play_result(forced_secondaries=3))
    assert out["forced_secondaries"] == 3.0


def test_path_stats_omits_ratio_keys_when_private_nav_is_always_zero():
    """A wiped-out or never-funded programme has no defined coverage or
    bite ratios -- the statistic must be OMITTED, not raised or set to a
    nonsense placeholder like 0.0 or inf."""
    rows = [
        _pq(quarter=0, private_nav=0.0, unfunded=0.0, distributions=0.0),
        _pq(quarter=1, private_nav=0.0, unfunded=0.0, distributions=0.0),
    ]
    out = path_stats(rows, _play_result())
    assert "peak_unfunded_ratio" not in out
    assert "linkage_bite" not in out
    assert "linkage_shortfall" not in out  # distributions_unlinked also all 0.0
    assert out["forced_secondaries"] == 0.0  # this key has no such guard
