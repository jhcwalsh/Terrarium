"""The default book is today's derived book (su-app-06).

The screen opens pre-filled and the pre-fill must BE the current product,
or the round-trip test in test_book_override.py is comparing two different
institutions and proving nothing.
"""

from __future__ import annotations

import pytest

from ah.play import (
    EXPECTED_PLAN_GROWTH,
    PRIVATE_ASSETS,
    START_CASH,
    START_TARGETS,
    default_commitment_plan,
    default_opening_book,
    plan_commitments,
)
from ah.port.adapter import GEN_START_TARGETS
from ah.port.book import BOOK_TOTAL, default_band, validate_book, validate_plan


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
        # ER-15: the derived book can never open with nav_reported != nav_true.
        # An ENTERED book can, and that is the state the calibration never saw.
        book = default_opening_book(START_TARGETS)
        for rungs in book.private.values():
            for rung in rungs:
                assert rung["value"]["nav_reported"] == pytest.approx(rung["value"]["nav_true"])

    def test_the_default_is_reproducible(self):
        assert default_opening_book(START_TARGETS).digest() == (
            default_opening_book(START_TARGETS).digest()
        )

    @pytest.mark.parametrize("targets", [START_TARGETS, GEN_START_TARGETS])
    def test_the_default_book_carries_a_default_band_per_sleeve(self, targets):
        # app-open-01 delta 1: the derived default now declares a +/-10%
        # reporting band for every sleeve it names a target for — cash
        # excepted, since cash carries no target and no band.
        book = default_opening_book(targets)
        assert book.ranges is not None
        assert set(book.ranges) == set(targets)
        for sleeve, target in targets.items():
            assert book.ranges[sleeve] == default_band(float(target))

    def test_the_default_bands_still_pass_validation(self):
        # a book straight off default_opening_book must still validate clean
        # (no warnings) — every default target sits inside its own default
        # band by construction.
        book = default_opening_book(START_TARGETS)
        liquid = tuple(a for a in START_TARGETS if a not in PRIVATE_ASSETS)
        assert validate_book(book, liquid_sleeves=liquid) == []


class TestDefaultPlan:
    def test_the_default_plan_has_one_entry_per_decision_window(self):
        # NOT one per calendar year. decision_months(120) is nine windows, and
        # the engine fires nine commitments (q = 4, 8, ... 36; `q > 0 and
        # q % 4 == 0`). A tenth entry would be dead.
        from ah.core.institution import decision_months

        plan = default_commitment_plan(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            assert len(plan.points[sleeve]) == len(decision_months(120)) == 9

    def test_the_default_plan_escalates_at_the_owner_ruled_growth_rate(self):
        # INVERTED 2026-08-16 (owner-ruled, D-SP-6 session; app-open-02 task
        # 11): the default plan used to be flat across all nine windows
        # (`len(set(pace)) == 1`, `pace[0] == target * 0.18`) — see
        # `default_commitment_plan`'s docstring for why, and for the history
        # this test now pins instead. The rule is now window k = the FIXED-
        # rule base times (1 + EXPECTED_PLAN_GROWTH) ** k, so the programme
        # keeps pace with the plan's own expected growth instead of shrinking
        # relative to it. `base` is derived from the same
        # `plan_commitments(..., pacing_rule="fixed")` call
        # `default_commitment_plan` itself makes — not a re-derived magic
        # float.
        plan = default_commitment_plan(START_TARGETS)
        base = plan_commitments(0.0, START_TARGETS, pacing_rule="fixed")
        for sleeve in PRIVATE_ASSETS:
            pace = plan.points[sleeve]
            assert pace[0] == pytest.approx(base[sleeve])  # k=0: no escalation yet
            for k, points in enumerate(pace):
                assert points == pytest.approx(base[sleeve] * (1.0 + EXPECTED_PLAN_GROWTH) ** k)
            assert len(set(pace)) == len(pace)  # flat retired: every window differs

    def test_the_default_plan_is_inside_the_declared_bound(self):
        validate_plan(default_commitment_plan(START_TARGETS), dict(START_TARGETS))
