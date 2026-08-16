# tests/test_book.py
"""The opening book contract (su-app-06).

A book is the institution's starting state as an analyst typed it: liquid
weights, cash, and a ladder of private vintages. The rungs are serialized
ClosedEndCohort documents, so the Step-3 state contract does the validating
and this module only adds the rules that are about the BOOK rather than
about one cohort.
"""

from __future__ import annotations

import copy

import pytest

from ah.port.book import (
    BOOK_TOTAL,
    BookError,
    CommitmentPlan,
    OpeningBook,
    validate_book,
    validate_plan,
)

TOY_LIQUID = ("equity", "bonds", "hy", "commodities", "reits")


def _rung(committed: float, paid_in: float, nav: float) -> dict:
    """A minimal closed_end document that the state contract accepts."""
    from ah.play import _doc  # the committed fixture is the shape of truth

    doc = copy.deepcopy(_doc("closed-end-cohort.example.json"))
    doc["commitment"] = {
        "committed": committed,
        "paid_in": paid_in,
        "unfunded": committed - paid_in,
        "recallable_balance": 0.0,
        "cumulative_recycled": 0.0,
    }
    doc["value"] = {
        "nav_true": nav,
        "nav_reported": nav,
        "cumulative_distributions": 0.0,
    }
    return doc


def _book(**overrides) -> OpeningBook:
    """A valid toy-shaped book: liquid 63 + private 35 + cash 2 = 100."""
    fields = {
        "liquid": {"equity": 33.0, "bonds": 12.0, "hy": 5.0, "commodities": 5.0, "reits": 8.0},
        "private": {
            "pe": [_rung(40.0, 20.0, 20.0)],
            "pc": [_rung(16.0, 8.0, 8.0)],
            "re": [_rung(14.0, 7.0, 7.0)],
        },
        "cash": 2.0,
    }
    fields.update(overrides)
    return OpeningBook(**fields)


class TestOpeningBook:
    def test_a_valid_book_passes_and_totals_one_hundred(self):
        book = _book()
        validate_book(book, liquid_sleeves=TOY_LIQUID)
        total = sum(book.liquid.values()) + book.cash
        total += sum(r["value"]["nav_true"] for rungs in book.private.values() for r in rungs)
        assert total == pytest.approx(BOOK_TOTAL)

    def test_a_book_that_does_not_total_one_hundred_is_refused(self):
        book = _book(cash=5.0)  # 63 + 35 + 5 = 103
        with pytest.raises(BookError, match="totals 103"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_a_sleeve_the_world_does_not_carry_is_refused(self):
        # reits exists in the toy book and NOT in generated worlds: entering it
        # against a generated world would create a sleeve the tape has no
        # returns for, which is the whole point of section 3.1.
        book = _book()
        gen_liquid = ("equity", "bonds", "hy", "commodities")
        with pytest.raises(BookError, match="reits"):
            validate_book(book, liquid_sleeves=gen_liquid)

    def test_a_rung_breaking_the_recycling_identity_is_refused(self):
        bad = _rung(40.0, 20.0, 20.0)
        bad["commitment"]["unfunded"] = 25.0  # 20 + 25 != 40 + 0
        with pytest.raises(BookError, match="recycling identity"):
            validate_book(
                _book(
                    private={
                        "pe": [bad],
                        "pc": [_rung(16.0, 8.0, 8.0)],
                        "re": [_rung(14.0, 7.0, 7.0)],
                    }
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_an_empty_sleeve_ladder_is_refused(self):
        with pytest.raises(BookError, match="no rungs"):
            validate_book(
                _book(
                    private={"pe": [], "pc": [_rung(16.0, 8.0, 8.0)], "re": [_rung(14.0, 7.0, 7.0)]}
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_negative_cash_is_refused_by_the_model_itself(self):
        with pytest.raises(ValueError):
            _book(cash=-1.0)

    def test_cohorts_round_trip_through_the_state_contract(self):
        book = _book()
        cohorts = book.cohorts("pe")
        assert len(cohorts) == 1
        assert cohorts[0].nav_true == pytest.approx(20.0)

    def test_digest_is_stable_and_order_independent(self):
        a = _book()
        b = _book(
            liquid={"reits": 8.0, "commodities": 5.0, "hy": 5.0, "bonds": 12.0, "equity": 33.0}
        )
        assert a.digest() == b.digest()

    def test_digest_changes_when_one_rung_changes(self):
        a = _book()
        b = _book(
            private={
                "pe": [_rung(40.0, 20.5, 20.0)],
                "pc": [_rung(16.0, 8.0, 8.0)],
                "re": [_rung(14.0, 7.0, 7.0)],
            }
        )
        assert a.digest() != b.digest()


class TestCommitmentPlan:
    def test_a_valid_plan_passes(self):
        plan = CommitmentPlan(points={"pe": [3.6] * 10, "pc": [1.44] * 10, "re": [1.26] * 10})
        validate_plan(plan, targets={"pe": 20.0, "pc": 8.0, "re": 7.0})

    def test_a_year_over_the_declared_cap_is_refused(self):
        # the bound is 0..COMMIT_CAP_MULTIPLE (2.0) x target x 0.18
        # pe: 2.0 * 20.0 * 0.18 = 7.2
        plan = CommitmentPlan(
            points={"pe": [7.3] + [3.6] * 9, "pc": [1.44] * 10, "re": [1.26] * 10}
        )
        with pytest.raises(BookError, match="year 0"):
            validate_plan(plan, targets={"pe": 20.0, "pc": 8.0, "re": 7.0})

    def test_a_negative_year_is_refused(self):
        with pytest.raises(ValueError):
            CommitmentPlan(points={"pe": [-1.0] * 10, "pc": [1.44] * 10, "re": [1.26] * 10})

    def test_sleeves_of_different_lengths_are_refused(self):
        with pytest.raises(ValueError):
            CommitmentPlan(points={"pe": [3.6] * 10, "pc": [1.44] * 9, "re": [1.26] * 10})
