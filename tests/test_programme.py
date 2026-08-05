"""The private-programme diagnostic (credibility console section).

Arithmetic is checked against numbers computed by hand, never against the
module's own output.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import simulate_play
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
