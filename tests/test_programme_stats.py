"""Declared bands and the statistics they judge.

The bands are one allocator's priors, editable by design — these tests pin the
ARITHMETIC, never the priors, so re-declaring a band never breaks a test.
"""

from __future__ import annotations

import numpy as np

from ah.programme import (
    PROGRAMME_PLAUSIBLE,
    programme_stats,
    vintage_stats,
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
