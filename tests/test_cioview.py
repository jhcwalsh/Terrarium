"""cio-01: the CIO view builder and the play-state exposure it rides on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import PRIVATE_ASSETS, simulate_play

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


def test_per_asset_private_flows_sum_to_totals():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert abs(sum(q.private_calls.values()) - q.calls_paid) < 1e-9
        assert abs(sum(q.private_distributions.values()) - q.distributions_received) < 1e-9
        assert abs(sum(q.private_unfunded.values()) - q.unfunded_total) < 1e-9
        assert set(q.private_calls) == set(PRIVATE_ASSETS)


def test_per_asset_values_close_against_the_book():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        total = q.cash + sum(q.liquid_values.values()) + sum(q.private_true.values())
        assert abs(total - q.nav_true) < 1e-9
        total_rep = q.cash + sum(q.liquid_values.values()) + sum(q.private_reported.values())
        assert abs(total_rep - q.nav_reported) < 1e-9


def test_monthly_marks_close_on_the_quarter():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert len(q.nav_true_months) == 3
        assert len(q.nav_reported_months) == 3
        assert abs(q.nav_true_months[2] - q.nav_true) < 1e-9
        assert abs(q.nav_reported_months[2] - q.nav_reported) < 1e-9
        assert all(v > 0 for v in q.nav_true_months)


def test_opening_book_recorded():
    result = simulate_play(_paths(), None)
    op = result.opening
    total = op["cash"] + sum(op["liquid_values"].values()) + sum(op["private_true"].values())
    assert abs(total - op["nav_true"]) < 1e-9
    assert set(op["private_unfunded"]) == set(PRIVATE_ASSETS)
