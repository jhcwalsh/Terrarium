"""cio-01: the CIO view builder and the play-state exposure it rides on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.cioview import validate_cio_view
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


def _pq(label: str, forecast: bool) -> dict[str, Any]:
    return {
        "label": label,
        "forecast": forecast,
        "calls": 1.0,
        "distributions": 1.5,
        "net": 0.5,
        "navOpen": 30.0,
        "navClose": 30.5,
        "unfundedOpen": 15.0,
        "unfundedClose": 14.0,
        "callRateUnfunded": 0.0667,
        "callRateNav": 0.0333,
        "coverage": 0.459,
    }


def _minimal_view() -> dict[str, Any]:
    """Smallest payload that passes every check — the seed for defect tests."""
    return {
        "meta": {
            "runId": "r1",
            "seed": "42",
            "worldTitle": "t",
            "worldVersion": "toy-v0.6",
            "linkageVersion": "public-0.1",
            "decisionAlphaVersion": "port-v4-ladder",
            "asOfLabel": "Y1 Q1",
            "asOfMonth": 2,
            "plane": "reported",
            "planesAvailable": ["reported", "true"],
            "unitLabel": "$m",
            "unitSuffix": "m",
            "currency": "USD",
            "watermark": "w",
            "disclaimer": "d",
        },
        "plan": {
            "totalValue": 100.0,
            "growthPct": None,
            "netOfFlows": None,
            "windowLabel": "Since inception",
            "history": {"values": [100.0, 100.5, 100.0 + 1e-9], "worldStartIndex": 0},
        },
        "allocation": {
            "goals": [{"id": "growth", "label": "Growth", "tolerancePct": 5.0}],
            "classes": [
                {
                    "id": "equity",
                    "label": "Equity",
                    "goalId": "growth",
                    "targetPct": 100.0,
                    "bandPct": 5.0,
                    "currentPct": 100.0,
                    "value": 100.0,
                    "returns": [1.0],
                }
            ],
            "alertPolicy": {"watchFraction": 0.75},
        },
        "performance": {
            "periods": ["1Q"],
            "annualisedFromIndex": 1,
            "total": [1.2],
            "benchmark": [1.1],
        },
        "liquidity": {
            "tiers": [{"id": "t1", "tier": 1, "label": "T1", "note": "", "value": 100.0}],
            "forecast12m": {
                "distributions": 2.0,
                "income": 0.0,
                "calls": 3.0,
                "payout": 1.0,
                "net": -2.0,
            },
        },
        "privateCashflows": {
            "histCount": 1,
            "classes": [{"id": "pe", "label": "PE"}],
            "series": {
                "aggregate": [_pq("Y1Q1", False)],
                "pe": [_pq("Y1Q1", False)],
            },
        },
    }


def test_validator_passes_a_well_formed_view():
    assert validate_cio_view(_minimal_view()) == []


def test_validator_catches_unbalanced_weights():
    v = _minimal_view()
    v["allocation"]["classes"][0]["currentPct"] = 90.0
    assert any("currentPct sums" in e for e in validate_cio_view(v))


def test_validator_catches_forecast_flag_mismatch():
    v = _minimal_view()
    v["privateCashflows"]["series"]["pe"][0]["forecast"] = True
    assert any("forecast flag" in e for e in validate_cio_view(v))


def test_validator_catches_net_identity_break():
    v = _minimal_view()
    v["liquidity"]["forecast12m"]["net"] = 5.0
    assert any("components imply" in e for e in validate_cio_view(v))


def test_validator_catches_plane_not_available():
    v = _minimal_view()
    v["meta"]["plane"] = "true"
    v["meta"]["planesAvailable"] = ["reported"]
    assert any("planesAvailable" in e for e in validate_cio_view(v))
