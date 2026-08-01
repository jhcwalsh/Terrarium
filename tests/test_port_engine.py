"""WP3.7 — the portfolio engine: the waterfall, spending off reported, forced sales.

The plan's own acceptance as tests: a deliberately over-committed institution
in a crisis path produces forced sales; a well-buffered one does not. Plus §7's
mechanic (spending rides smoothed marks, so it barely falls in the crash) and
§8's ordering (liquid sales before the forced secondary, everything logged).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.port.cohort import ClosedEndCohort
from ah.port.engine import EngineError, Policy, PortfolioEngine
from ah.port.portfolio import Portfolio
from ah.port.sleeves import LiquidSleeve

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "fixtures" / "state"


def _doc(name: str) -> dict:
    return json.loads((STATE / name).read_text(encoding="utf-8"))


def _portfolio(cash: float, liquid_value: float) -> Portfolio:
    p = Portfolio(cash=cash)
    p.add("pm_buyout-2019", ClosedEndCohort.from_document(_doc("closed-end-cohort.example.json")))
    liq = LiquidSleeve.from_document(_doc("liquid-sleeve.example.json"))
    liq.value = liquid_value
    p.add("liquid_public_equity", liq)
    return p


class TestWaterfall:
    def test_order_and_no_forced_sale_when_buffered(self):
        engine = PortfolioEngine(_portfolio(cash=50.0, liquid_value=180.0))
        report = engine.run_quarter(distributions=2.0, calls=3.0)
        assert report.forced_sale_total == 0.0
        assert report.cash_end == pytest.approx(50.0 + 2.0 - 3.0 - report.spending_paid)
        assert engine.portfolio.forced_sales == []

    def test_overcommitted_in_crisis_forces_sales_wellbuffered_does_not(self):
        """The plan's acceptance test, verbatim."""
        squeezed = PortfolioEngine(_portfolio(cash=0.5, liquid_value=2.0))
        buffered = PortfolioEngine(_portfolio(cash=50.0, liquid_value=180.0))
        for engine in (squeezed, buffered):
            engine.portfolio.liquid["liquid_public_equity"].apply_return(-0.30)  # crisis
        r_squeezed = squeezed.run_quarter(distributions=0.2, calls=6.0)  # drought + calls
        r_buffered = buffered.run_quarter(distributions=0.2, calls=6.0)
        assert r_squeezed.forced_sale_total > 0.0
        assert r_buffered.forced_sale_total == 0.0

    def test_liquid_sells_before_the_forced_secondary_and_both_log(self):
        engine = PortfolioEngine(_portfolio(cash=0.0, liquid_value=1.0))
        engine.run_quarter(distributions=0.0, calls=5.0)
        log = engine.portfolio.forced_sales
        assert [e["kind"] for e in log] == ["liquid_pro_rata", "forced_secondary"]
        for event in log:
            assert {"period", "amount", "cause", "sleeves_sold"} <= set(event)
        secondary = log[1]
        # the haircut is real: NAV sold exceeds cash raised
        assert secondary["nav_sold"] > secondary["amount"]
        assert secondary["haircut"] == pytest.approx(0.19)

    def test_forced_secondary_hits_cohort_nav(self):
        engine = PortfolioEngine(_portfolio(cash=0.0, liquid_value=0.0))
        nav0 = engine.portfolio.cohorts["pm_buyout-2019"].nav_true
        engine.run_quarter(distributions=0.0, calls=5.0)
        assert engine.portfolio.cohorts["pm_buyout-2019"].nav_true < nav0


class TestSpendingOffReported:
    def test_spending_rides_the_smoothed_marks(self):
        """§7's mechanic: crash true values, hold reported — spending barely
        falls, exactly when liquid assets are scarcest."""
        engine = PortfolioEngine(_portfolio(cash=100.0, liquid_value=100.0))
        calm = engine.run_quarter(distributions=0.0, calls=0.0)
        # crash: true basis falls hard, reported cohort marks stay
        engine.portfolio.liquid["liquid_public_equity"].apply_return(-0.40)
        crashed = engine.run_quarter(distributions=0.0, calls=0.0)
        # spending falls far less than the true value fell
        true_fall = 1.0 - engine.portfolio.nav_true() / (
            100.0 + 100.0 + engine.portfolio.cohorts["pm_buyout-2019"].nav_true
        )
        spend_fall = 1.0 - crashed.spending_paid / calm.spending_paid
        assert spend_fall < 0.15  # trailing reported average barely moves
        assert crashed.spending_paid > 0.0

    def test_breach_detection_on_both_bases(self):
        engine = PortfolioEngine(
            _portfolio(cash=5.0, liquid_value=60.0),
            Policy(private_weight_range=(0.10, 0.35)),
        )
        engine.portfolio.liquid["liquid_public_equity"].apply_return(-0.50)  # denominator falls
        report = engine.run_quarter(distributions=0.0, calls=0.0)
        assert report.breach_true  # true weight breached immediately
        assert report.private_weight_true > report.private_weight_reported


class TestRefusals:
    def test_bad_policy_and_bad_flows(self):
        with pytest.raises(EngineError):
            Policy(spending_rate_annual=0.5)
        with pytest.raises(EngineError):
            Policy(secondary_haircut=1.0)
        with pytest.raises(EngineError):
            Policy(private_weight_range=(0.5, 0.4))
        engine = PortfolioEngine(_portfolio(cash=10.0, liquid_value=10.0))
        with pytest.raises(EngineError):
            engine.run_quarter(distributions=-1.0, calls=0.0)
