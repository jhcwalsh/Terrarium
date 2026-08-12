"""Declared bands and the statistics they judge.

The bands are one allocator's priors, editable by design — these tests pin the
ARITHMETIC, never the priors, so re-declaring a band never breaks a test.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ah.play import PlayQuarter, PlayResult
from ah.programme import (
    _QUARTERS_PER_YEAR,
    PROGRAMME_PLAUSIBLE,
    ProgrammeQuarter,
    _terminal_liquidation_quarters,
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


def test_a_statistic_no_path_could_compute_is_rendered_as_zero_of_n_not_dropped():
    """Review round 2, I2: this used to assert ``stats == []`` -- the row was
    dropped when NO path computed the statistic.

    That is backwards. Partial presence was already visible through the
    "n of N" count column; TOTAL absence, the case a reader most needs to
    see, disappeared without trace and left "this never happened in any of
    the 20 paths" indistinguishable from "somebody forgot to compute it".
    Confirmed live before the fix: deflation_bust rendered no
    ``crossover_years`` row at all.

    The "does not crash" half of the original test is preserved -- an empty
    per-path lineage still returns cleanly rather than raising -- while the
    assertion is inverted to the behaviour the fix requires.
    """
    stats = programme_stats([{}, {}], {})
    assert len(stats) == len(PROGRAMME_PLAUSIBLE)
    for s in stats:
        assert s.n_present == 0
        assert s.n_total == 2
        assert s.median is None
        assert s.p10 is None
        assert s.p90 is None
        assert s.path0 is None
        assert s.flagged, "a band with nothing to judge is an unanswered question"


def test_vintage_stats_at_tier0_benchmark_growth_are_hand_checkable():
    """No market drama (dd=0, spread=1 throughout, so the linkage is 1.0),
    and NAV grows at tier 0's own frozen constant g_annual -- not zero --
    because these are questions about the model's cashflow SHAPE, and tier
    0's constant growth is what "the model's own shape" means. Zero growth
    makes the J-curve crossover arithmetically impossible (NAV can never
    outgrow calls net of distributions without growth) and caps DPI below
    1.0 structurally -- an artifact of a lazy test tape, not a finding
    about the model.

    The input arrays are 40 quarters long, not 36: ``vintage_stats`` reads
    world quarters ``_QUARTERS_PER_YEAR`` (4) through ``4 + quarters - 1``
    (the vintage's own life, starting at the programme's year-1 anniversary),
    not the world's first ``quarters`` quarters (review round 1, M1 -- a
    36-length array was silently truncated to 32 usable quarters by the
    fix, shifting every statistic below). The four padding quarters at the
    front stand in for the world's OWN opening year, before this vintage
    exists.

    The padding is uniform (dd=0, spread=1), same as the rest of the array,
    so -- verified directly, not assumed -- the pinned numbers below are
    UNCHANGED from before the alignment fix: a uniform sequence is
    invariant to which contiguous 36-quarter window of it you take. Only a
    genuinely non-uniform tape (see
    ``test_vintage_stats_uses_the_vintage_s_own_window_not_the_world_s_opening_years``
    below) can actually distinguish the fixed alignment from the bug.
    """
    n = 36
    calm_dd = np.zeros(_QUARTERS_PER_YEAR + n)
    calm_spread = np.ones(_QUARTERS_PER_YEAR + n)
    out = vintage_stats(calm_dd, calm_spread, n)
    # rc_curve[0] = 0.25 annual on unfunded, quarterly => 6.25% of 1.0
    # committed. Returns don't affect the first call, so this is unchanged
    # by the growth basis.
    # rc_curve[0] = 0.35 annual on unfunded (the ER-6 declared curve,
    # owner D1 2026-08-12), quarterly => 8.75% of 1.0 committed. The
    # placeholder curve's value was 0.0625 (0.25/4).
    assert np.isclose(out["first_call"], 0.0875, rtol=1e-6)
    # under the declared curve: paid_in and cumulative distributions over 36
    # quarters of tier-0 constant growth give dpi_age9 = 1.1127 (was 1.116
    # under the placeholder — faster early calls raise paid_in slightly
    # ahead of the distributions they fund).
    assert np.isclose(out["dpi_age9"], 1.1127, atol=1e-3)
    # years 1-3 average annual call rate on the declining unfunded balance:
    # 0.2223 (curve entries 0.35/0.40/0.30 average 0.35, but each applies to
    # a balance the prior calls already shrank).
    assert np.isclose(out["call_rate_y1_3"], 0.2223, atol=1e-3)
    # cumulative (distributions - calls) still first turns positive at
    # quarter index 34 (0-based, within the vintage's OWN 36-quarter
    # window) => crossover_years = (34 + 1) / 4 = 8.75 — faster calls
    # front-load the J-curve's trough but tier-0's constant growth pays it
    # back on the same schedule.
    assert out["crossover_years"] == 8.75


def test_vintage_stats_uses_the_vintage_s_own_window_not_the_world_s_opening_years():
    """Review round 1, M1: a shock placed in the world's first 4 quarters --
    BEFORE the year-1 vintage is even committed -- must be invisible to this
    statistic, and the identical shock placed in the vintage's own final
    quarters (the world's last 4, still inside its 36-quarter life) must
    move it. This is the only kind of tape that can actually tell the
    fixed alignment apart from the ``[:36]`` bug it replaced -- the
    hand-checkable calm test above uses a uniform tape and is provably
    insensitive to the window's position, only its length.
    """
    n = 36
    baseline = vintage_stats(np.zeros(_QUARTERS_PER_YEAR + n), np.ones(_QUARTERS_PER_YEAR + n), n)

    dd_front_shock = np.zeros(_QUARTERS_PER_YEAR + n)
    dd_front_shock[:_QUARTERS_PER_YEAR] = 0.9  # world quarters 0-3: pre-commitment
    out_front = vintage_stats(dd_front_shock, np.ones(_QUARTERS_PER_YEAR + n), n)
    assert out_front == baseline

    dd_back_shock = np.zeros(_QUARTERS_PER_YEAR + n)
    dd_back_shock[-_QUARTERS_PER_YEAR:] = 0.9  # the vintage's own last 4 quarters
    out_back = vintage_stats(dd_back_shock, np.ones(_QUARTERS_PER_YEAR + n), n)
    assert out_back["dpi_age9"] != baseline["dpi_age9"]


def test_path_stats_linkage_bite_is_a_rate_not_a_level():
    """A rate-based bite is ~1.0 when the distribution RATE is constant even
    as private NAV (and hence the distribution LEVEL) grows across the
    decade -- the ladder's own growth must not be able to masquerade as a
    linkage effect. A level-based implementation would instead compare the
    raw distribution amounts and land far from 1.0.

    Review round 2, C2: the tape is now 12 quarters of GEOMETRIC growth
    rather than 5 of linear growth. The assertion (bite == 1.0 exactly) and
    the property it pins are unchanged; the tape had to change because
    ``linkage_bite`` now compares TRAILING four-quarter rates, and a
    trailing rate is only exactly constant under a constant NAV growth
    RATE. Four quarters of distributions over the NAV the window opened
    with is ``0.2 * (g + g^2 + g^3 + g^4)`` at every quarter, independent
    of where in the decade the window sits.

    private_nav = 1.05^i, distributions = 0.2 * private_nav, deepest
    drawdown at the LAST quarter (not the middle one) so a level-based
    implementation cannot accidentally agree: comparing raw trailing SUMS
    would give the last window's sum over the median window's sum =
    1.05^4 = 1.2155, not 1.0.
    """
    g = 1.05
    n = 12
    navs = [g**i for i in range(n)]
    depths = [0.01] * n
    depths[-1] = 0.9  # deepest at the last quarter
    rows = [
        _pq(quarter=i, private_nav=nav, distributions=0.2 * nav, drawdown_depth=dd)
        for i, (nav, dd) in enumerate(zip(navs, depths, strict=True))
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["linkage_bite"], 1.0, atol=1e-9)


def test_path_stats_worst_quarter_is_selected_by_drawdown_not_distribution():
    """The "worst" quarter for linkage_bite must be the one with the
    DEEPEST DRAWDOWN, not the one with the lowest (or highest) distribution
    rate -- selecting on the distribution value instead would make the
    statistic circular ("the quarter with the lowest distributions has a
    low distribution rate").

    Review round 2, C2: the tape is now 12 quarters rather than 4. The
    property and the pinned answer (3.0) are unchanged; four quarters no
    longer produce more than one trailing window, so the old tape could not
    express "worst" and "median" as different quarters at all.

    private_nav is constant at 1.0, so a trailing rate is just the sum of
    its four quarters' distributions. Distributions are 0.05 everywhere
    except quarter 5, which pays 0.45 -- so trailing rates are 0.20 for the
    windows that miss quarter 5 (i = 3, 4, 9, 10, 11) and 0.60 for the four
    that contain it (i = 5, 6, 7, 8). median(0.20 x5, 0.60 x4) = 0.20.

    The deepest drawdown is at quarter 5, whose trailing rate (0.60) is the
    HIGHEST, not the lowest: linkage_bite = 0.60 / 0.20 = 3.0. A bug that
    selected the minimum-distribution window instead would compute
    0.20 / 0.20 = 1.0.
    """
    n = 12
    dists = [0.05] * n
    dists[5] = 0.45
    depths = [0.01] * n
    depths[5] = 0.90  # deepest at index 5
    rows = [
        _pq(quarter=i, private_nav=1.0, distributions=d, drawdown_depth=dd)
        for i, (d, dd) in enumerate(zip(dists, depths, strict=True))
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["linkage_bite"], 3.0, atol=1e-9)


def _play_result_with_navs(navs: list[dict[str, float]]) -> PlayResult:
    """A PlayResult carrying per-cohort NAV, which is all
    ``_terminal_liquidation_quarters`` reads."""
    return PlayResult(
        quarters=[
            PlayQuarter(
                quarter=i,
                month=i * 3 + 2,
                cash=0.0,
                nav_true=0.0,
                nav_reported=0.0,
                calls_paid=0.0,
                distributions_received=0.0,
                spending_paid=0.0,
                forced_sale_total=0.0,
                private_weight_true=0.0,
                unfunded_total=0.0,
                vintage_nav=dict(nav),
            )
            for i, nav in enumerate(navs)
        ],
        final_value=0.0,
        forced_sale_quarters=0,
        total_forced_sales=0.0,
    )


def test_terminal_liquidation_quarters_finds_the_quarter_a_cohort_wound_up():
    """A cohort with positive NAV in one quarter and zero (or no entry) in
    the next has wound up IN that next quarter -- review round 2, C2."""
    navs: list[dict[str, float]] = [{"c0": 10.0}] * 6 + [{"c0": 0.0}] * 6
    assert _terminal_liquidation_quarters(_play_result_with_navs(navs)) == {6}

    # a cohort that simply vanishes from the dict counts the same way
    dropped: list[dict[str, float]] = [{"c0": 10.0}] * 3 + [{}] * 3
    assert _terminal_liquidation_quarters(_play_result_with_navs(dropped)) == {3}

    # a programme where nothing ever winds up has no such quarters
    steady: list[dict[str, float]] = [{"c0": 10.0}] * 8
    assert _terminal_liquidation_quarters(_play_result_with_navs(steady)) == set()


def test_path_stats_linkage_bite_excludes_a_cohort_wind_up_lump():
    """Review round 2, C2: the defect this exists to prevent.

    A cohort winds up in quarter 6, paying its whole remaining NAV out as a
    10.0 lump against a baseline of 0.05 a quarter -- and quarter 6 is also
    the deepest drawdown, exactly the coincidence that produced
    linkage_bite = 110.65 on deflation_bust path 0 before the fix.

    With the lump included, the trailing windows containing quarter 6
    (i = 6, 7, 8, 9) read 0.15 + 10.0 = 10.15 against 0.20 elsewhere;
    median(0.20 x5, 10.15 x4) = 0.20 and the worst-drawdown window is the
    lump's own, giving 10.15 / 0.20 = 50.75 -- a report that distributions
    ROSE fifty-fold in the worst quarter of the decade.

    With those four windows excluded, every surviving window reads 0.20,
    the deepest REMAINING drawdown is quarter 5, and the answer is 1.0.
    """
    n = 12
    dists = [0.05] * n
    dists[6] = 10.0  # the wind-up lump
    depths = [0.01] * n
    depths[6] = 0.90  # deepest drawdown lands on the wind-up
    depths[5] = 0.50  # deepest of what survives the exclusion
    rows = [
        _pq(quarter=i, private_nav=1.0, distributions=d, drawdown_depth=dd)
        for i, (d, dd) in enumerate(zip(dists, depths, strict=True))
    ]
    navs: list[dict[str, float]] = [{"c0": 10.0}] * 6 + [{"c0": 0.0}] * 6
    out = path_stats(rows, _play_result_with_navs(navs))
    assert np.isclose(out["linkage_bite"], 1.0, atol=1e-9)
    assert out["linkage_bite"] < 2.0, "the 50.75 the lump would have produced is gone"

    # and the lump is only excluded because it was DETECTED: hand the same
    # tape a PlayResult in which nothing winds up, and it comes straight back.
    steady: list[dict[str, float]] = [{"c0": 10.0}] * n
    unguarded = path_stats(rows, _play_result_with_navs(steady))
    assert np.isclose(unguarded["linkage_bite"], 50.75, atol=1e-9)


def test_path_stats_linkage_bite_averages_a_spike_rather_than_propagating_it():
    """The trailing window's other half: a single loud quarter that is NOT a
    wind-up is diluted to a quarter of the numerator rather than becoming
    all of it -- review round 2, C2.

    private_nav is constant at 1.0. Distributions are 0.1 a quarter except
    quarter 5, which pays 1.6, and quarter 5 is the deepest drawdown.

    Single-quarter (the old definition): worst rate = 1.6, median rate =
    0.1, bite = 16.0.
    Trailing four-quarter: the windows containing quarter 5 (i = 5, 6, 7, 8)
    read 0.3 + 1.6 = 1.9, the other five read 0.4, median = 0.4, and
    bite = 1.9 / 0.4 = 4.75 -- the spike still shows, at a quarter of the
    weight, which is the point.
    """
    n = 12
    dists = [0.1] * n
    dists[5] = 1.6
    depths = [0.01] * n
    depths[5] = 0.90
    rows = [
        _pq(quarter=i, private_nav=1.0, distributions=d, drawdown_depth=dd)
        for i, (d, dd) in enumerate(zip(dists, depths, strict=True))
    ]
    out = path_stats(rows, _play_result())
    assert np.isclose(out["linkage_bite"], 4.75, atol=1e-9)
    single_quarter_equivalent = 1.6 / 0.1
    assert out["linkage_bite"] < single_quarter_equivalent / 3.0


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
