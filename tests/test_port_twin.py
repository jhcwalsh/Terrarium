"""WP3.8 — the pension twin.

The plan's acceptance: a rate shock moves liabilities and collateral in the
directions and magnitudes an actuary would expect; an under-hedged plan shows
funding volatility dominated by the liability side. Plus the gilt mechanic
(headroom exhaustion force-unwinds the hedge, logged) and §5.1's hold-course
twin ignoring the crisis by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.core.institutionstate import load_institution_state
from ah.port.twin import (
    HoldCourseTwin,
    LiabilityProfile,
    LiabilityState,
    PensionTwin,
    TwinError,
)

ROOT = Path(__file__).resolve().parents[1]


def _contract(rates_hedge: float = 0.7):
    doc = json.loads((ROOT / "fixtures" / "state" / "institution-stub.json").read_text("utf-8"))
    doc["institution"]["hedging"]["rates_hedge_ratio"] = rates_hedge
    return load_institution_state(doc)


def _twin(rates_hedge: float = 0.7) -> PensionTwin:
    liabilities = LiabilityState(LiabilityProfile(), discount_rate=0.04)
    return PensionTwin(contract=_contract(rates_hedge), liabilities=liabilities, assets=100.0)


class TestActuarialDirections:
    def test_rate_rise_moves_everything_the_actuary_expects(self):
        twin = _twin()
        headroom0 = twin.collateral.headroom
        report = twin.rate_shock(+0.01)
        assert report["liability_pv_change"] < 0  # liabilities fall
        assert report["hedge_pnl"] < 0  # the hedge loses
        assert report["margin_call"] > 0  # margin posts
        assert twin.collateral.headroom < headroom0  # headroom falls
        # magnitude: |dPV|/PV ~ duration * dy, within first-order tolerance
        pv_now = twin.liabilities.pv()
        rel = -report["liability_pv_change"] / (pv_now - report["liability_pv_change"])
        assert rel == pytest.approx(report["duration"] * 0.01, rel=0.25)

    def test_rate_fall_rebuilds_headroom(self):
        twin = _twin()
        twin.rate_shock(+0.01)
        headroom_squeezed = twin.collateral.headroom
        twin.rate_shock(-0.01)
        assert twin.collateral.headroom > headroom_squeezed  # margin returns

    def test_duration_is_a_pension_duration(self):
        state = LiabilityState(LiabilityProfile(), discount_rate=0.04)
        assert 12.0 < state.duration() < 30.0  # a DB scheme, not a bond fund


class TestGiltMechanic:
    def test_headroom_exhaustion_force_unwinds_and_logs(self):
        """2022: rates gap up, margin calls exceed headroom, the hedge is cut
        at the worst moment — logged, never silent."""
        twin = _twin(rates_hedge=1.0)
        report = twin.rate_shock(+0.025)  # the gilt-crisis-sized move
        assert report["fraction_unwound"] > 0.0
        assert twin.hedge_ratio_effective < 1.0  # the hedge is genuinely smaller now
        assert twin.collateral.unwinds  # the event is on the record
        event = twin.collateral.unwinds[-1]
        assert event["margin_call"] > event["covered"]

    def test_underhedged_funding_volatility_is_liability_dominated(self):
        """The plan's second acceptance clause, as a comparison."""
        hedged = _twin(rates_hedge=0.9)
        unhedged = _twin(rates_hedge=0.1)
        fr_h0, fr_u0 = hedged.funding_ratio(), unhedged.funding_ratio()
        hedged.rate_shock(-0.01)  # rates FALL: liabilities balloon
        unhedged.rate_shock(-0.01)
        move_hedged = abs(hedged.funding_ratio() - fr_h0)
        move_unhedged = abs(unhedged.funding_ratio() - fr_u0)
        assert move_unhedged > 3.0 * move_hedged  # liability side dominates

    def test_inflation_shock_hits_the_linked_share(self):
        twin = _twin()
        pv0 = twin.liabilities.pv()
        twin.inflation_shock(1.05)
        pv1 = twin.liabilities.pv()
        assert pv1 > pv0  # linked benefits grew
        assert (pv1 / pv0 - 1.0) < 0.05  # but only the linked 70%, partially


class TestHoldCourseTwin:
    def test_the_twin_ignores_the_crisis_by_construction(self):
        plan = HoldCourseTwin(pacing_plan=(10.0, 12.0, 12.0, 8.0))
        calm = [plan.commitment_for_year(y, crisis_state=None) for y in range(4)]
        crisis = [
            plan.commitment_for_year(y, crisis_state={"drawdown": 0.4, "gates": True})
            for y in range(4)
        ]
        assert calm == crisis == [10.0, 12.0, 12.0, 8.0]

    def test_terminal_pace_continues_and_refusals(self):
        plan = HoldCourseTwin(pacing_plan=(10.0, 8.0))
        assert plan.commitment_for_year(7) == 8.0
        with pytest.raises(TwinError):
            plan.commitment_for_year(-1)
        with pytest.raises(TwinError):
            LiabilityState(LiabilityProfile(), discount_rate=0.9)
