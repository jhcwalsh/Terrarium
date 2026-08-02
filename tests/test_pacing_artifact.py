"""WI-I6-1 — the pacing table is the source of truth, and nothing may drift.

The owner's requirement verbatim: the distribution rates live in an
accessible table, updatable and inspectable, not buried in the code. The
drift guard is what makes that true over time: any fixture that disagrees
with ``mappings/pacing-parameters-v1.0.yaml`` fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "mappings" / "pacing-parameters-v1.0.yaml"
FIXTURE = ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"


def _table() -> dict:
    return yaml.safe_load(ARTIFACT.read_text("utf-8"))


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text("utf-8"))


class TestDriftGuard:
    def test_fixture_matches_the_table_exactly(self):
        row = _table()["sleeves"]["pm_buyout"]
        params = _fixture()["parameters"]
        life = _fixture()["lifecycle"]["contractual_life_years"]
        assert params["yield_rate"] == row["yield_rate"]
        assert params["bow"] == row["bow"]
        assert params["rc_curve"] == row["rc_curve"]
        assert life == row["contractual_life_years"]

    def test_table_carries_its_governance_surface(self):
        table = _table()
        assert table["artifact_version"] == "pacing-1.0"
        assert "drift_guard" in table and "inspect_with" in table
        assert {q["id"] for q in table["open_questions"]} >= {"PQ-1", "PQ-2"}


class TestImpliedCurve:
    def test_curve_is_monotone_and_in_the_stated_range(self):
        row = _table()["sleeves"]["pm_buyout"]
        y, b, life = row["yield_rate"], row["bow"], row["contractual_life_years"]
        rates = {age: y * (age / life) ** b for age in (3, 5, 7, 8, 10)}
        assert list(rates.values()) == sorted(rates.values())  # monotone in age
        # the aggregate anchors stated in the artifact's own comments
        assert 0.05 <= rates[5] <= 0.15
        assert 0.15 <= rates[7] <= 0.30
        assert rates[10] == pytest.approx(y)  # Y IS the terminal rate

    def test_fixture_snapshot_reconciles_with_its_own_parameters(self):
        """The WI-I6-1 inconsistency, closed: the flows snapshot's implied
        annual rate now matches the table's curve at the cohort's age."""
        doc = _fixture()
        age = doc["lifecycle"]["age_years"]
        life = doc["lifecycle"]["contractual_life_years"]
        row = _table()["sleeves"]["pm_buyout"]
        implied_annual = row["yield_rate"] * (age / life) ** row["bow"]
        dist_q = doc["flows"]["distributions_income"] + doc["flows"]["distributions_capital"]
        snapshot_annual = 4.0 * dist_q / doc["value"]["nav_true"]
        assert snapshot_annual == pytest.approx(implied_annual, rel=0.02)
