"""WP3.6 — vehicle mechanics: notice, gates, side pockets, queue stress.

The acceptance shape: stress produces queue extension and gating; nothing pays
inside its notice period; realizable-by-horizon is the terms' arithmetic, not
the stated NAV; the 2022-23 evergreen mechanic (queue lengthens, no gate ever
declared) emerges from the rules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.port.sleeves import EvergreenVehicle, OpenEndedSleeve
from ah.port.vehicles import OpenEndedMechanics, evergreen_stress_quarter

ROOT = Path(__file__).resolve().parents[1]


def _sleeve() -> OpenEndedSleeve:
    doc = json.loads(
        (ROOT / "fixtures" / "state" / "open-ended-sleeve.example.json").read_text("utf-8")
    )
    return OpenEndedSleeve.from_document(doc)


def _vehicle() -> EvergreenVehicle:
    doc = json.loads(
        (ROOT / "fixtures" / "state" / "evergreen-vehicle.example.json").read_text("utf-8")
    )
    return EvergreenVehicle.from_document(doc)


class TestNoticeAndGate:
    def test_notice_shorter_than_a_quarter_pays_at_the_first_dealing_date(self):
        mech = OpenEndedMechanics(_sleeve())  # notice 60d < one quarter
        mech.request(5.0)
        assert mech.dealing_date() > 0.0  # notice elapsed by the dealing date

    def test_notice_longer_than_a_quarter_defers(self):
        sleeve = _sleeve()
        sleeve._contract = sleeve._contract.model_copy(
            update={"terms": sleeve._contract.terms.model_copy(update={"notice_days": 120})}
        )
        mech = OpenEndedMechanics(sleeve)  # 120d -> 2 quarters
        mech.request(5.0)
        assert mech.dealing_date() == 0.0  # still inside notice
        assert mech.dealing_date() > 0.0  # matured

    def test_gate_prorates_and_rolls_the_excess(self):
        sleeve = _sleeve()
        sleeve.gated_flag = False
        mech = OpenEndedMechanics(sleeve)
        mech.request(sleeve.nav_true)  # everyone runs for the door
        mech.dealing_date()  # notice matures
        cash = mech.dealing_date()
        # gate_pct 0.25: at most a quarter of NAV paid, flag raised, rest rolls
        assert sleeve.gated_flag
        assert cash > 0.0
        assert sum(p.amount for p in mech.pending) > 0.0  # the roll

    def test_side_pocket_withholds_and_resolves(self):
        sleeve = _sleeve()  # side_pocket_share 0.03
        mech = OpenEndedMechanics(sleeve)
        mech.request(10.0)
        cash = mech.dealing_date()  # 60d notice matures at the first date
        assert mech.side_pocketed == pytest.approx(10.0 * 0.03)
        assert cash == pytest.approx(10.0 * 0.97)
        recovered = mech.resolve_side_pocket(recovery_rate=0.8)
        assert recovered == pytest.approx(0.8 * 10.0 * 0.03)
        assert mech.side_pocketed == 0.0


class TestRealizableByHorizon:
    def test_realizable_is_terms_arithmetic_not_stated_nav(self):
        sleeve = _sleeve()  # notice 60d, quarterly dealing, gate 0.25, side 0.03
        mech = OpenEndedMechanics(sleeve)
        r = mech.realizable_by_horizon()
        assert r["30d"] == 0.0  # inside notice: nothing
        assert 0.0 < r["90d"] < sleeve.nav_true  # one gated tranche
        assert r["90d"] == pytest.approx(0.25 * sleeve.nav_true * 0.97, rel=1e-6)
        assert r["90d"] < r["180d"] < sleeve.nav_true  # more dates, still gated

    def test_lockup_zeroes_the_horizon(self):
        sleeve = _sleeve()
        sleeve._contract = sleeve._contract.model_copy(
            update={
                "terms": sleeve._contract.terms.model_copy(update={"lockup_remaining_months": 12.0})
            }
        )
        r = OpenEndedMechanics(sleeve).realizable_by_horizon()
        assert r == {"30d": 0.0, "90d": 0.0, "180d": 0.0}


class TestEvergreenStress:
    def test_stress_lengthens_the_queue_with_no_gate_declared(self):
        """THE 2022-23 mechanic: same rules, stressed demand -> the queue ages
        and fulfilment collapses, while no gate exists to point at."""
        calm = _vehicle()
        stressed = _vehicle()
        for _ in range(4):
            evergreen_stress_quarter(calm, calm_redemption_demand=0.5, stress=False)
            evergreen_stress_quarter(stressed, calm_redemption_demand=0.5, stress=True)
        assert stressed.pending_redemption > calm.pending_redemption * 2
        assert stressed.queue_age_periods >= calm.queue_age_periods
        assert stressed.fulfilled_pct_history[-1] < calm.fulfilled_pct_history[-1]
        # and NOWHERE in the evergreen state is there a gate flag to declare —
        # the lock-in is emergent, which is the whole point
        assert not hasattr(stressed, "gated_flag")
