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
from typing import ClassVar

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


def _rung(committed: float, paid_in: float, nav: float, cohort_id: str = "rung") -> dict:
    """A minimal closed_end document that the state contract accepts.

    ``cohort_id`` is explicit because it is a PORTFOLIO KEY. The committed
    fixture ships exactly one id ("pm_buyout-2019"), so before su-app-06's I4
    fix this helper built a book whose three rungs all shared it — accepted at
    the door, then a 500 out of ``Portfolio.add`` on every read. Callers give
    each rung its own.
    """
    from ah.play import _doc  # the committed fixture is the shape of truth

    doc = copy.deepcopy(_doc("closed-end-cohort.example.json"))
    doc["identity"] = {**doc["identity"], "cohort_id": cohort_id}
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
            "pe": [_rung(40.0, 20.0, 20.0, "pe-0")],
            "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
            "re": [_rung(14.0, 7.0, 7.0, "re-0")],
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
        bad = _rung(40.0, 20.0, 20.0, "pe-0")
        bad["commitment"]["unfunded"] = 25.0  # 20 + 25 != 40 + 0
        with pytest.raises(BookError, match="recycling identity"):
            validate_book(
                _book(
                    private={
                        "pe": [bad],
                        "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                        "re": [_rung(14.0, 7.0, 7.0, "re-0")],
                    }
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_an_empty_sleeve_ladder_is_refused(self):
        with pytest.raises(BookError, match="no rungs"):
            validate_book(
                _book(
                    private={
                        "pe": [],
                        "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                        "re": [_rung(14.0, 7.0, 7.0, "re-0")],
                    }
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_a_rung_that_breaks_the_state_contract_is_refused_as_a_book_error(self):
        # A malformed rung must surface as BookError naming the sleeve and index,
        # not as the state contract's own exception type: the HTTP layer catches
        # BookError to build a 422, so a leaked SleeveStateSchemaError becomes a 500.
        bad = _rung(40.0, 20.0, 20.0, "pe-0")
        bad["vehicle_type"] = "open_ended"
        with pytest.raises(BookError, match="pe rung 0"):
            validate_book(
                _book(
                    private={
                        "pe": [bad],
                        "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                        "re": [_rung(14.0, 7.0, 7.0, "re-0")],
                    }
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
                "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                "re": [_rung(14.0, 7.0, 7.0, "re-0")],
            }
        )
        assert a.digest() != b.digest()


class TestCohortIdsAreThePortfoliosKeys:
    """I4 — a rung's ``cohort_id`` becomes a ``Portfolio`` key at
    ``_build_portfolio``, and ``Portfolio.add`` raises ``PortfolioError`` on a
    repeat. Both of these books were accepted with a 201 and then 500'd on
    every read; the vintage collision did not even fire until mid-decade, when
    the pacing plan reached the year whose id the analyst had taken."""

    def test_two_rungs_sharing_an_id_are_refused(self):
        with pytest.raises(BookError, match="repeats cohort_id"):
            validate_book(
                _book(
                    private={
                        "pe": [_rung(20.0, 10.0, 10.0, "same"), _rung(20.0, 10.0, 10.0, "same")],
                        "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                        "re": [_rung(14.0, 7.0, 7.0, "re-0")],
                    }
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_the_clash_is_caught_ACROSS_sleeves_not_just_within_one(self):
        """``Portfolio``'s cohort registry is flat — one dict for the whole
        book — so a pe rung and a re rung sharing an id collide exactly as
        two pe rungs would. A per-sleeve check would miss this."""
        with pytest.raises(BookError, match="repeats cohort_id"):
            validate_book(
                _book(
                    private={
                        "pe": [_rung(40.0, 20.0, 20.0, "shared")],
                        "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                        "re": [_rung(14.0, 7.0, 7.0, "shared")],
                    }
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_an_id_reserved_for_a_future_vintage_is_refused(self):
        # ah.play commits `f"{asset}-v{year}"` once a year during play
        with pytest.raises(BookError, match="reserved cohort_id"):
            validate_book(
                _book(
                    private={
                        "pe": [_rung(40.0, 20.0, 20.0, "pe-v3")],
                        "pc": [_rung(16.0, 8.0, 8.0, "pc-0")],
                        "re": [_rung(14.0, 7.0, 7.0, "re-0")],
                    }
                ),
                liquid_sleeves=TOY_LIQUID,
            )

    def test_the_derived_books_own_ids_are_not_in_the_reserved_namespace(self):
        """The rule must not refuse the default book the screen opens with —
        ``_seed_ladder`` names its rungs ``{asset}-s{k}``. A regex that caught
        `-s` too would break every session ever created."""
        from ah.play import default_opening_book

        book = default_opening_book()
        validate_book(book, liquid_sleeves=TOY_LIQUID)
        ids = [r["identity"]["cohort_id"] for rungs in book.private.values() for r in rungs]
        assert len(ids) == len(set(ids))


class TestTargetsAndRanges:
    """su-app-07 Task 1: policy targets and reporting bands are additive to
    the su-app-06 book contract — a book naming neither must validate and
    behave exactly as it did before (deletability)."""

    # the book's own weights (liquid + private target NAV): 63 + 35, so with
    # cash 2.0 this is a valid `targets` document too (totals 100).
    _TARGETS: ClassVar[dict[str, float]] = {
        "equity": 33.0,
        "bonds": 12.0,
        "hy": 5.0,
        "commodities": 5.0,
        "reits": 8.0,
        "pe": 20.0,
        "pc": 8.0,
        "re": 7.0,
    }

    def test_a_state_version_0_1_document_still_validates(self):
        # the deletability fence at the contract level: a book with no
        # targets and no ranges, explicitly stamped at the old version.
        book = _book(state_version="opening-book-0.1")
        assert book.targets is None
        assert book.ranges is None
        assert validate_book(book, liquid_sleeves=TOY_LIQUID) == []

    def test_effective_targets_falls_back_to_the_books_own_weights(self):
        book = _book()
        assert book.targets is None
        assert book.effective_targets() == {**book.liquid, **book.target_nav()}

    def test_effective_targets_returns_the_entered_targets_when_present(self):
        book = _book(targets=self._TARGETS)
        assert book.effective_targets() == self._TARGETS

    def test_targets_that_do_not_sum_with_cash_to_one_hundred_are_refused(self):
        bad = {**self._TARGETS, "equity": 30.0}  # 95 + cash 2 = 97
        book = _book(targets=bad)
        with pytest.raises(BookError, match="targets total 97"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_targets_naming_a_sleeve_outside_the_worlds_set_are_refused(self):
        bad = {**self._TARGETS, "gold": 0.0}
        book = _book(targets=bad)
        with pytest.raises(BookError, match="gold"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_a_negative_target_is_refused(self):
        bad = {**self._TARGETS, "equity": -1.0}
        book = _book(targets=bad)
        with pytest.raises(BookError, match="target 'equity' is negative"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_a_range_with_lo_gte_hi_is_refused(self):
        book = _book(ranges={"equity": (50.0, 50.0)})
        with pytest.raises(BookError, match="range"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_a_range_on_an_unknown_sleeve_is_refused(self):
        book = _book(ranges={"gold": (10.0, 20.0)})
        with pytest.raises(BookError, match="gold"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_a_target_outside_its_own_range_is_accepted_and_returned_as_a_warning(self):
        book = _book(targets=self._TARGETS, ranges={"equity": (40.0, 50.0)})
        warnings = validate_book(book, liquid_sleeves=TOY_LIQUID)  # must not raise
        assert any("equity" in w for w in warnings)

    def test_a_derived_target_outside_its_range_is_also_warned(self):
        # no `targets` entered: effective_targets() falls back to the book's
        # own weights, and a range still applies to that fallback — the
        # single-source-of-truth point of effective_targets().
        book = _book(ranges={"equity": (40.0, 50.0)})  # book's own equity is 33.0
        warnings = validate_book(book, liquid_sleeves=TOY_LIQUID)
        assert any("equity" in w for w in warnings)

    def test_a_clean_book_returns_no_warnings(self):
        assert validate_book(_book(), liquid_sleeves=TOY_LIQUID) == []


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
