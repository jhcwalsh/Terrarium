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
from ah.programme import ladder_years, programme_quarters

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


@pytest.fixture(scope="module")
def runs():
    paths = run_path(_world("stagflation"), 771204)
    return simulate_play(paths), simulate_play(paths, linkage=False)


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
