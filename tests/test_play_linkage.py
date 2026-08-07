"""The market linkage, exposed and switchable (programme console, task 1).

``simulate_play`` computed the two continuous states tier 1 consumes and threw
them away, and had no way to run without the linkage — so nothing could show
what the market environment actually did to the cashflows. Both are now
records on the quarter and a keyword, with the default byte-identical to what
shipped.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import PRIVATE_ASSETS, simulate_play

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


def _paths():
    world = _world("stagflation")
    return run_path(world, 771204)


def test_quarters_carry_the_states_the_linkage_consumes():
    result = simulate_play(_paths())
    q = result.quarters[0]
    assert q.drawdown_depth >= 0.0
    assert q.spread_ratio > 0.0
    # the frozen artifact's bounds: f_dist clips to [0.3, 1.5], f_call to [0.5, 1.2]
    for quarter in result.quarters:
        assert 0.3 <= quarter.f_dist <= 1.5
        assert 0.5 <= quarter.f_call <= 1.2


def test_linkage_off_pins_both_multipliers_to_one():
    """Linkage off IS tier 0's recursion — the sealed 'one model' identity."""
    result = simulate_play(_paths(), linkage=False)
    assert all(q.f_dist == 1.0 for q in result.quarters)
    assert all(q.f_call == 1.0 for q in result.quarters)


def test_linkage_changes_the_distributions_it_is_supposed_to_change():
    linked = simulate_play(_paths())
    unlinked = simulate_play(_paths(), linkage=False)
    a = sum(q.distributions_received for q in linked.quarters)
    b = sum(q.distributions_received for q in unlinked.quarters)
    assert a != b, "the linkage must move distributions or it is not doing anything"


def test_default_run_is_unchanged_by_these_additions():
    """The additive fields and the new keyword must be inert on the scored path.

    Pinned against values recorded from the pre-change implementation, so a
    later edit that quietly moves a scored number fails here. Regenerated for
    toy-v0.5 (ER-7 closed): the engine moved underneath this test, not
    play.py — toy-v0.3's value was 76.71221387563882.
    """
    result = simulate_play(_paths())
    assert len(result.quarters) == 40
    assert result.final_value == 86.89058776172098
    assert result.forced_secondaries == 0


def test_new_commitments_land_once_a_year_after_the_first():
    result = simulate_play(_paths())
    committing = [q.quarter for q in result.quarters if q.new_commitments > 0.0]
    assert committing == [4, 8, 12, 16, 20, 24, 28, 32, 36]


def test_vintage_nav_covers_every_private_sleeve_and_sums_to_private_nav():
    result = simulate_play(_paths())
    last = result.quarters[-1]
    assert last.vintage_nav, "the per-vintage stack must be populated"
    for key in last.vintage_nav:
        assert key.split("-")[0] in PRIVATE_ASSETS
    total = sum(last.vintage_nav.values())
    expected = last.private_weight_true * last.nav_true
    assert np.isclose(total, expected, rtol=1e-6)
