"""The private-programme diagnostic (credibility console section).

Arithmetic is checked against numbers computed by hand, never against the
module's own output.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import PlayResult, simulate_play
from ah.programme import ladder_years, path_stats, programme_quarters

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


@pytest.fixture(scope="module")
def runs():
    paths = run_path(_world("stagflation"), 771204)
    return simulate_play(paths), simulate_play(paths, linkage=False)


def test_peak_unfunded_ratio_no_longer_pathological(runs):
    """ER-6 close-out acceptance, recalibrated against measurement.

    The design note hoped the declared curve alone would bring the overhang
    into the 0.25-0.75 band; measured, the curve change moved stagflation's
    peak from 3.26 to ~1.22 (goldilocks ~0.97) and the RESIDUAL excess is
    attributable to the hold-course COMMITMENT PACE (18%/yr, the E1 lever's
    default), not the call curve — plus the denominator effect in crash
    decades. Neither the band nor the pace is tuned here: the band stays a
    true flag about the default pacing policy, and the pace is the player's
    lever. This pin asserts the ER-6 pathology itself is gone: the overhang
    is bounded far below the placeholder's 2.4-3.3 regime.

    Regenerated for ER-10 (toy-v0.6): reported marks now track crashes, so
    the counter-cyclical pacing rule commits MORE in the trough - the
    measured peak moved 1.22 -> 1.52 on this seed (quarter 20, the
    stagflation trough; numerator up via the leaned-in multiplier,
    denominator down via depressed true NAV). The pathology band 2.4-3.3
    remains far away; the old ceiling was 1.5."""
    from ah.programme import path_stats, programme_quarters

    linked, unlinked = runs
    quarters = programme_quarters(linked, unlinked)
    stat = path_stats(quarters, linked)["peak_unfunded_ratio"]
    assert stat < 1.6, stat  # placeholder-curve worlds read 2.4-3.3


def test_quarters_pair_linked_and_unlinked_distributions(runs):
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    assert len(rows) == len(linked.quarters)
    assert rows[3].distributions == linked.quarters[3].distributions_received
    assert rows[3].distributions_unlinked == unlinked.quarters[3].distributions_received


def test_coverage_is_unfunded_over_assets_on_both_bases(runs):
    linked, unlinked = runs
    row = programme_quarters(linked, unlinked)[10]
    q = linked.quarters[10]
    assert np.isclose(row.coverage_true, q.unfunded_total / q.nav_true)
    assert np.isclose(row.coverage_reported, q.unfunded_total / q.nav_reported)


def test_private_nav_is_weight_times_total(runs):
    linked, unlinked = runs
    row = programme_quarters(linked, unlinked)[10]
    q = linked.quarters[10]
    assert np.isclose(row.private_nav, q.private_weight_true * q.nav_true)


def test_ladder_aggregates_four_quarters_into_each_year(runs):
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    years = ladder_years(rows, linked)
    assert len(years) == 10
    hand_called = sum(r.calls for r in rows[4:8])
    assert np.isclose(years[1].called, hand_called)
    hand_net = sum(r.distributions - r.calls for r in rows[4:8])
    assert np.isclose(years[1].net, hand_net)


def test_ladder_year_zero_commits_nothing_and_later_years_do(runs):
    linked, unlinked = runs
    years = ladder_years(programme_quarters(linked, unlinked), linked)
    assert years[0].committed == 0.0
    assert years[1].committed > 0.0


def test_expired_commitment_explains_the_unfunded_drop_calls_cannot(runs):
    """Audit F2: ER-6's terminal lapse was computed and dropped before any
    surface could show it, so the console's ladder had a year where unfunded
    fell by far more than the year called — with nothing on the page to say
    why. The seed cohorts lapse together in year 4 (age 5.25 + 4.75 = the
    10-year contractual life).

    Arithmetic by hand, per this file's rule: the year's expiry is the sum of
    its own quarters' expiries, and the drop it explains is real.
    """
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    years = ladder_years(rows, linked)

    lapse = [y for y in years if y.expired > 0.0]
    assert lapse, "no year expires any commitment — ER-6's lapse never fires"

    # HISTORY: this asserted ONE lapse year whose unfunded drop EXCEEDED that
    # year's calls. That was true only while the opening book was three clones
    # of a single mid-life cohort, so the whole ladder lapsed in one quarter.
    # The seed ladder is staggered now (one vintage per year of a fund's life,
    # `ladder-01`), so a rung retires every year and none of them dominates.
    # The clause that survives is the substantive one — the expiry is the term
    # without which the unfunded balance cannot be reconciled — and it is now
    # checked on EVERY lapse year rather than the one big one.
    assert len(lapse) > 1, "a staggered ladder retires a rung a year, not all at once"
    for y in lapse:
        hand = sum(r.expired_undrawn for r in rows[y.year * 4 : y.year * 4 + 4])
        assert np.isclose(y.expired, hand) and hand > 0.0
        if y.year == 0:
            continue  # no prior year to difference against
        drop = years[y.year - 1].unfunded_end - y.unfunded_end
        assert np.isclose(drop, y.called + y.expired - y.committed, atol=1e-6)


def test_linkage_bite_survives_a_ladder_that_retires_a_rung_every_year(runs):
    """ER-12's casualty, and the reason the statistic was redefined.

    linkage_bite used to drop any trailing four-quarter window that OVERLAPPED
    a cohort wind-up. That was affordable while the opening book was three
    clones of one cohort and wind-ups happened once a decade. A staggered
    ladder retires a rung every year, so with a four-quarter window EVERY
    window overlapped one and the statistic went undefined on 20 of 20 paths —
    the console's only linkage diagnostic, dead.

    It is now netted by AMOUNT rather than by index: the terminal lump is
    subtracted from the window's numerator and the window is kept. This pins
    the property that failed — on the real programme, the statistic exists.
    """
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    stats = path_stats(rows, linked)
    assert "linkage_bite" in stats, "the linkage diagnostic is undefined on a real path"
    assert stats["linkage_bite"] > 0.0

    # and the lumps are real on this path — the netting is doing work, not
    # quietly subtracting zero
    assert sum(r.terminal_distributions for r in rows) > 0.0


def test_called_to_date_is_cumulative(runs):
    linked, unlinked = runs
    years = ladder_years(programme_quarters(linked, unlinked), linked)
    assert np.isclose(years[2].called_to_date, years[0].called + years[1].called + years[2].called)


def test_coverage_infinite_when_nav_zero(runs):
    """Wipeout: NAV=0 with non-zero unfunded yields infinite coverage.

    Matches Portfolio.coverage_true()'s convention: an institution with
    obligations and no assets is infinitely uncovered, not perfectly covered.
    """
    linked, unlinked = runs
    # Take real quarters and create wipeout variants
    q_linked_real = linked.quarters[10]
    q_unlinked_real = unlinked.quarters[10]

    # Create wipeout versions (nav_true=0, nav_reported=0, but unfunded_total > 0)
    q_linked_wipeout_true = replace(q_linked_real, nav_true=0.0, unfunded_total=1.0)
    q_linked_wipeout_reported = replace(q_linked_real, nav_reported=0.0, unfunded_total=1.0)
    q_linked_both_zero = replace(q_linked_real, nav_true=0.0, nav_reported=0.0, unfunded_total=1.0)

    # Create minimal PlayResult instances with matching wipeout quarters
    # (unlinked stays the same as a baseline)
    result_true_zero_linked = PlayResult(
        quarters=[q_linked_wipeout_true],
        final_value=0.0,
        forced_sale_quarters=0,
        total_forced_sales=0.0,
    )
    result_true_zero_unlinked = PlayResult(
        quarters=[q_unlinked_real],
        final_value=0.0,
        forced_sale_quarters=0,
        total_forced_sales=0.0,
    )

    result_reported_zero_linked = PlayResult(
        quarters=[q_linked_wipeout_reported],
        final_value=0.0,
        forced_sale_quarters=0,
        total_forced_sales=0.0,
    )

    result_both_zero_linked = PlayResult(
        quarters=[q_linked_both_zero],
        final_value=0.0,
        forced_sale_quarters=0,
        total_forced_sales=0.0,
    )

    # Test true NAV wipeout
    rows_true = programme_quarters(result_true_zero_linked, result_true_zero_unlinked)
    assert math.isinf(rows_true[0].coverage_true)

    # Test reported NAV wipeout
    rows_reported = programme_quarters(result_reported_zero_linked, result_true_zero_unlinked)
    assert math.isinf(rows_reported[0].coverage_reported)

    # Test both wipeout
    rows_both = programme_quarters(result_both_zero_linked, result_true_zero_unlinked)
    assert math.isinf(rows_both[0].coverage_true)
    assert math.isinf(rows_both[0].coverage_reported)


def test_ladder_years_handles_partial_blocks(runs):
    """Partial final block: a quarter count not divisible by 4 yields ceil(n/4) years.

    The final year covers the remaining quarters, with unfunded_end and
    private_nav_end from the true last row.
    """
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    # Truncate to 38 quarters (not divisible by 4; should yield 10 years)
    partial_rows = rows[:38]
    years = ladder_years(partial_rows, linked)

    # 38 quarters = 9 full years (36 quarters) + 1 partial year (2 quarters)
    # ceil(38/4) = 10
    assert len(years) == math.ceil(38 / 4)
    assert len(years) == 10

    # The last year (year 9) should cover quarters 36-37
    last_year = years[-1]
    assert last_year.year == 9
    # unfunded_end and private_nav_end should come from the true last row (index 37)
    assert last_year.unfunded_end == partial_rows[37].unfunded
    assert last_year.private_nav_end == partial_rows[37].private_nav

    # Review round 2, M-a: `committed` is the one column read from
    # linked.quarters rather than from the rows list, and it was sliced with a
    # fixed four-quarter stride while every other column came from the block.
    # On this shape -- a two-row final block -- the old code summed FOUR
    # source quarters' commitments into a row whose called/distributed cover
    # two, so the columns of one table row described different spans. This
    # test exercised exactly that shape and asserted nothing about committed.
    assert last_year.called == pytest.approx(sum(r.calls for r in partial_rows[36:38]))
    assert last_year.committed == pytest.approx(
        sum(q.new_commitments for q in linked.quarters[36:38])
    )
    # NOTE: on this real tape the assertion above cannot by itself fail the
    # old code -- ah.play commits only when q % 4 == 0 (src/ah/play.py:371),
    # so quarters 38 and 39 contribute nothing whether they are summed or
    # not. The test with teeth is
    # test_ladder_committed_comes_from_as_many_source_quarters_as_the_block,
    # below, which uses a source run carrying commitments in every quarter.


def test_ladder_committed_comes_from_as_many_source_quarters_as_the_block(runs):
    """Review round 2, M-a, with teeth.

    ``committed`` is the only ladder column read from the source PlayResult
    rather than from the rows list, and it was sliced with a fixed
    four-quarter stride. Give the source run a commitment in EVERY quarter
    (ah.play's own ladder only commits one quarter in four, which is why the
    real-tape assertion above cannot see the bug) and truncate the rows to
    six: year 1's block is two rows long, so its committed must cover two
    source quarters (10 + 100 = 110), not four (10 + 100 + 1000 + 10000).
    """
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)[:6]
    amounts = [1.0, 2.0, 3.0, 4.0, 10.0, 100.0, 1000.0, 10000.0]
    source = replace(
        linked,
        quarters=[
            replace(q, new_commitments=a) for q, a in zip(linked.quarters[:8], amounts, strict=True)
        ],
    )
    years = ladder_years(rows, source)
    assert len(years) == 2
    assert years[0].committed == pytest.approx(1.0 + 2.0 + 3.0 + 4.0)
    assert years[1].committed == pytest.approx(110.0)
