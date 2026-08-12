"""WP3.1 — the runtime state objects and their invariants.

The plan's property tests, as tests: values non-negative, weights sum to one,
unfunded never negative, recallable balance bounded — plus the contract
round-trip (an object that cannot serialize to the frozen v1.0 contract is a
bug at mutation time, not at save time) and the accounting identities of the
liquidity-spine §4 recursions.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ah.port.cohort import ClosedEndCohort, CohortError
from ah.port.portfolio import Portfolio, PortfolioError
from ah.port.sleeves import EvergreenVehicle, LiquidSleeve, OpenEndedSleeve

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "fixtures" / "state"


def _doc(name: str) -> dict:
    return json.loads((STATE / name).read_text(encoding="utf-8"))


@pytest.fixture
def cohort() -> ClosedEndCohort:
    return ClosedEndCohort.from_document(_doc("closed-end-cohort.example.json"))


class TestCohort:
    def test_round_trip_reflects_mutations_and_revalidates(self, cohort):
        cohort.step(0.02)
        document = cohort.to_document()  # re-validates internally
        assert document["commitment"]["paid_in"] == pytest.approx(cohort.paid_in)
        assert document["flows"]["calls"] == pytest.approx(cohort._last.call)
        again = ClosedEndCohort.from_document(document)
        assert again.unfunded == pytest.approx(cohort.unfunded)

    def test_step_accounting_identity(self, cohort):
        nav0, pic0, unf0, cum0 = (
            cohort.nav_true,
            cohort.paid_in,
            cohort.unfunded,
            cohort.cumulative_distributions,
        )
        flows = cohort.step(0.03)
        assert cohort.nav_true == pytest.approx(nav0 * 1.03 + flows.call - flows.distribution_total)
        assert cohort.paid_in == pytest.approx(pic0 + flows.call)
        assert cohort.unfunded == pytest.approx(unf0 - flows.call)
        assert cohort.cumulative_distributions == pytest.approx(cum0 + flows.distribution_total)

    def test_full_life_never_breaks_invariants(self, cohort):
        """Property sweep: 15 years of quarterly steps under wild returns —
        unfunded never negative, PIC never above committed, NAV never negative,
        every intermediate state contract-valid."""
        rng = np.random.default_rng(20260801)
        for r in rng.normal(0.02, 0.12, size=60):
            cohort.step(
                float(r), f_call=float(rng.uniform(0.3, 1.7)), f_dist=float(rng.uniform(0.3, 1.7))
            )
            assert cohort.unfunded >= -1e-9
            assert cohort.paid_in <= cohort.committed + 1e-9
            assert cohort.nav_true >= 0.0
        cohort.to_document()  # final state still serializes

    def test_recall_unwinds_paid_in_and_stays_bounded(self, cohort):
        cohort.mark_recallable(2.0)
        pic0, unf0 = cohort.paid_in, cohort.unfunded
        cohort.recall(1.5)
        assert cohort.paid_in == pytest.approx(pic0 - 1.5)
        assert cohort.unfunded == pytest.approx(unf0 + 1.5)
        with pytest.raises(CohortError, match="exceeds recallable"):
            cohort.recall(10.0)

    def test_recallable_bounded_by_cumulative_distributions(self, cohort):
        with pytest.raises(CohortError, match="cumulative distributions"):
            cohort.mark_recallable(cohort.cumulative_distributions + 1.0)

    def test_new_commitment_starts_clean(self, cohort):
        fresh = ClosedEndCohort.new_commitment(
            _doc("closed-end-cohort.example.json"),
            committed=50.0,
            vintage_year=2026,
            cohort_id="pm_buyout-2026",
        )
        assert fresh.paid_in == 0.0 and fresh.nav_true == 0.0 and fresh.age_years == 0.0
        assert fresh.unfunded == 50.0
        with pytest.raises(CohortError, match="positive"):
            ClosedEndCohort.new_commitment(
                _doc("closed-end-cohort.example.json"),
                committed=0.0,
                vintage_year=2026,
                cohort_id="x",
            )

    def test_called_fraction_lands_in_the_practitioner_band(self):
        """ER-6 close-out (owner D1: option A). A fresh commitment stepped
        quarterly to year 10 at neutral linkage must pay in 85-95% of what
        it committed — the practitioner band the placeholder curve missed by
        ~20 points (70.75% called; ~29% silently never drawn)."""
        fresh = ClosedEndCohort.new_commitment(
            _doc("closed-end-cohort.example.json"),
            committed=100.0,
            vintage_year=2026,
            cohort_id="er6-band",
        )
        for _ in range(40):
            fresh.step(0.0, f_call=1.0, f_dist=1.0, years_per_period=0.25)
        assert 85.0 <= fresh.paid_in <= 95.0, fresh.paid_in

    def test_lapse_expires_residual_unfunded_with_a_ledger_line(self):
        """ER-6 close-out (owner D1: option C). At terminal lapse the
        residual commitment EXPIRES visibly: the step reports it and the
        unfunded balance goes to zero, instead of haunting the totals
        forever as a silent never-called tail."""
        fresh = ClosedEndCohort.new_commitment(
            _doc("closed-end-cohort.example.json"),
            committed=100.0,
            vintage_year=2026,
            cohort_id="er6-expiry",
        )
        for _ in range(40):  # to age 10 = contractual life; all non-terminal
            fresh.step(0.0, f_call=1.0, f_dist=1.0, years_per_period=0.25)
        residual_before = fresh.unfunded
        last = fresh.step(0.0, f_call=1.0, f_dist=1.0, years_per_period=0.25)  # terminal
        assert last.expired_undrawn == pytest.approx(residual_before)
        assert last.expired_undrawn > 0.0  # some tail exists even at the new curve
        assert fresh.unfunded == 0.0

    def test_negative_linkage_refused(self, cohort):
        with pytest.raises(CohortError, match="non-negative"):
            cohort.step(0.01, f_call=-0.1)


class TestSleeves:
    def test_open_ended_gate_caps_redemption(self):
        sleeve = OpenEndedSleeve.from_document(_doc("open-ended-sleeve.example.json"))
        sleeve.gated_flag = True  # gate_pct 0.25 in the fixture
        paid = sleeve.redeem(sleeve.nav_true)  # ask for everything
        assert paid == pytest.approx(54.2 * 0.25)
        assert sleeve.nav_true >= 0.0

    def test_open_ended_round_trip(self):
        sleeve = OpenEndedSleeve.from_document(_doc("open-ended-sleeve.example.json"))
        sleeve.apply_return(-0.04)
        sleeve.report(sleeve.nav_reported, -0.01)
        sleeve.to_document()

    def test_evergreen_queue_cap_binds_and_rolls(self):
        vehicle = EvergreenVehicle.from_document(_doc("evergreen-vehicle.example.json"))
        vehicle.request_redemption(10.0)
        pending0 = vehicle.pending_redemption
        fulfilled = vehicle.roll_queue()
        # cap = 5% of NAV(25.0) = 1.25 — far below the queue
        assert fulfilled == pytest.approx(0.05 * 25.0)
        assert vehicle.pending_redemption == pytest.approx(pending0 - fulfilled)
        assert vehicle.queue_age_periods >= 1.0  # the queue AGES: locked, no gate declared
        assert 0.0 <= vehicle.fulfilled_pct_history[-1] <= 1.0
        vehicle.to_document()

    def test_liquid_sell_bounded(self):
        liquid = LiquidSleeve.from_document(_doc("liquid-sleeve.example.json"))
        proceeds = liquid.sell(1e9)
        assert proceeds == pytest.approx(180.0)
        assert liquid.value == 0.0
        liquid.to_document()


class TestRefusals:
    """Every guard rail fires, and fires with its own message."""

    def test_wrong_vehicle_type_refused_everywhere(self):
        from ah.port.cohort import CohortError
        from ah.port.sleeves import SleeveError

        with pytest.raises(CohortError, match="closed_end"):
            ClosedEndCohort.from_document(_doc("liquid-sleeve.example.json"))
        with pytest.raises(SleeveError, match="open_ended"):
            OpenEndedSleeve.from_document(_doc("closed-end-cohort.example.json"))
        with pytest.raises(SleeveError, match="evergreen"):
            EvergreenVehicle.from_document(_doc("open-ended-sleeve.example.json"))
        with pytest.raises(SleeveError, match="liquid"):
            LiquidSleeve.from_document(_doc("evergreen-vehicle.example.json"))

    def test_negative_amounts_refused(self, cohort):
        from ah.port.sleeves import SleeveError

        sleeve = OpenEndedSleeve.from_document(_doc("open-ended-sleeve.example.json"))
        vehicle = EvergreenVehicle.from_document(_doc("evergreen-vehicle.example.json"))
        liquid = LiquidSleeve.from_document(_doc("liquid-sleeve.example.json"))
        with pytest.raises(SleeveError):
            sleeve.subscribe(-1.0)
        with pytest.raises(SleeveError):
            sleeve.redeem(-1.0)
        with pytest.raises(SleeveError):
            sleeve.report(-1.0, 0.0)
        with pytest.raises(SleeveError):
            vehicle.request_redemption(-1.0)
        with pytest.raises(SleeveError):
            vehicle.report(-1.0, 0.0)
        with pytest.raises(SleeveError):
            liquid.sell(-1.0)
        with pytest.raises(SleeveError):
            liquid.buy(-1.0)
        with pytest.raises(CohortError):
            cohort.report(-1.0)
        with pytest.raises(CohortError):
            cohort.recall(-1.0)
        with pytest.raises(CohortError):
            cohort.mark_recallable(-1.0)
        with pytest.raises(CohortError, match="positive"):
            cohort.step(0.01, years_per_period=0.0)
        with pytest.raises(PortfolioError, match="negative"):
            Portfolio(cash=-1.0)

    def test_subscribe_buy_and_reported_paths(self):
        sleeve = OpenEndedSleeve.from_document(_doc("open-ended-sleeve.example.json"))
        sleeve.subscribe(5.0)
        assert sleeve.nav_true == pytest.approx(54.2 + 5.0)
        vehicle = EvergreenVehicle.from_document(_doc("evergreen-vehicle.example.json"))
        vehicle.apply_return(0.01)
        vehicle.report(vehicle.nav_reported, 0.005)
        liquid = LiquidSleeve.from_document(_doc("liquid-sleeve.example.json"))
        liquid.buy(20.0)
        assert liquid.value == pytest.approx(200.0)


class TestPortfolio:
    def _build(self) -> Portfolio:
        p = Portfolio(cash=12.5)
        p.add(
            "pm_buyout-2019", ClosedEndCohort.from_document(_doc("closed-end-cohort.example.json"))
        )
        p.add("hf_macro", OpenEndedSleeve.from_document(_doc("open-ended-sleeve.example.json")))
        p.add("pm_re_core", EvergreenVehicle.from_document(_doc("evergreen-vehicle.example.json")))
        p.add(
            "liquid_public_equity", LiquidSleeve.from_document(_doc("liquid-sleeve.example.json"))
        )
        return p

    def test_weights_sum_to_one(self):
        weights = self._build().weights_true()
        assert sum(weights.values()) == pytest.approx(1.0)
        assert all(w >= 0.0 for w in weights.values())

    def test_denominator_effect_reported_coverage_looks_healthier(self):
        """The spec's stated property: in a drawdown, true NAV falls more than
        reported NAV, so reported coverage understates the squeeze."""
        p = self._build()
        p.liquid["liquid_public_equity"].apply_return(-0.30)
        p.cohorts["pm_buyout-2019"].step(-0.25)  # true basis falls; reported stays
        assert p.nav_true() < p.nav_reported()
        assert p.coverage_true() > p.coverage_reported()

    def test_private_weight_breaches_on_the_reported_basis_last(self):
        """The 2022 mechanic itself: a public drawdown raises the TRUE private
        weight immediately (denominator falls), while the REPORTED weight lags —
        the breach an allocator sees arrives late."""
        p = self._build()
        p.liquid["liquid_public_equity"].apply_return(-0.30)
        assert p.private_weight_true() > p.private_weight_reported()

    def test_weights_undefined_for_valueless_book(self):
        with pytest.raises(PortfolioError, match="valueless"):
            Portfolio(cash=0.0).weights_true()

    def test_coverage_liquid_is_the_binding_ratio(self):
        p = self._build()
        assert p.coverage_liquid() > p.coverage_true()  # private-heavy book

    def test_duplicate_key_refused(self):
        p = self._build()
        with pytest.raises(PortfolioError, match="duplicate"):
            p.add("hf_macro", OpenEndedSleeve.from_document(_doc("open-ended-sleeve.example.json")))

    def test_institution_round_trip(self):
        from ah.port.portfolio import Institution

        inst = Institution.from_document(
            self._build(), json.loads((STATE / "institution-stub.json").read_text("utf-8"))
        )
        inst.to_document()
