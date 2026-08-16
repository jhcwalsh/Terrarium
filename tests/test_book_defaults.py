"""The default book is today's derived book (su-app-06).

The screen opens pre-filled and the pre-fill must BE the current product,
or the round-trip test in test_book_override.py is comparing two different
institutions and proving nothing.
"""

from __future__ import annotations

import pytest

from ah.play import (
    PRIVATE_ASSETS,
    START_CASH,
    START_TARGETS,
    default_commitment_plan,
    default_opening_book,
)
from ah.port.adapter import GEN_START_TARGETS
from ah.port.book import BOOK_TOTAL, validate_book, validate_plan


def _liquid_of(targets) -> tuple[str, ...]:
    return tuple(a for a in targets if a not in PRIVATE_ASSETS)


class TestDefaultBook:
    @pytest.mark.parametrize("targets", [START_TARGETS, GEN_START_TARGETS])
    def test_the_default_book_is_valid_and_totals_one_hundred(self, targets):
        book = default_opening_book(targets)
        validate_book(book, liquid_sleeves=_liquid_of(targets))
        total = sum(book.liquid.values()) + book.cash + book.private_nav()
        assert total == pytest.approx(BOOK_TOTAL, abs=1e-6)

    def test_the_toy_book_carries_reits_and_the_generated_book_does_not(self):
        assert "reits" in default_opening_book(START_TARGETS).liquid
        assert "reits" not in default_opening_book(GEN_START_TARGETS).liquid

    def test_each_private_sleeve_gets_a_ten_rung_ladder(self):
        book = default_opening_book(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            assert len(book.private[sleeve]) == 10

    def test_each_sleeve_opens_at_its_target_nav(self):
        book = default_opening_book(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            nav = sum(r["value"]["nav_true"] for r in book.private[sleeve])
            assert nav == pytest.approx(START_TARGETS[sleeve], abs=1e-9)

    def test_cash_is_the_balance(self):
        assert default_opening_book(START_TARGETS).cash == START_CASH

    def test_the_seeded_ladder_opens_converged(self):
        # ER-14: the derived book can never open with nav_reported != nav_true.
        # An ENTERED book can, and that is the state the calibration never saw.
        book = default_opening_book(START_TARGETS)
        for rungs in book.private.values():
            for rung in rungs:
                assert rung["value"]["nav_reported"] == pytest.approx(rung["value"]["nav_true"])

    def test_the_default_is_reproducible(self):
        assert default_opening_book(START_TARGETS).digest() == (
            default_opening_book(START_TARGETS).digest()
        )


class TestDefaultPlan:
    def test_the_default_plan_has_one_entry_per_decision_window(self):
        # NOT one per calendar year. decision_months(120) is nine windows, and
        # the engine fires nine commitments (q = 4, 8, ... 36; `q > 0 and
        # q % 4 == 0`). A tenth entry would be dead.
        from ah.core.institution import decision_months

        plan = default_commitment_plan(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            assert len(plan.points[sleeve]) == len(decision_months(120)) == 9

    def test_the_default_plan_is_flat_at_the_fixed_rule_pace(self):
        plan = default_commitment_plan(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            pace = plan.points[sleeve]
            assert len(set(pace)) == 1  # flat: the kickoff default, section 10
            assert pace[0] == pytest.approx(START_TARGETS[sleeve] * 0.18)

    def test_the_default_plan_is_inside_the_declared_bound(self):
        validate_plan(default_commitment_plan(START_TARGETS), dict(START_TARGETS))
