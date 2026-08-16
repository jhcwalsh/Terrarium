"""An entered book replaces the derived ladder (su-app-06).

Two properties matter and they pull in opposite directions:
DELETABILITY  - opening_book=None must reproduce today's institution exactly,
                so every session that exists keeps replaying as it did;
EQUIVALENCE   - the DEFAULT book fed back in as an entered book must produce
                an identical decade, so the entry path and the derived path
                are the same institution and not merely similar ones.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    _ANNUAL_COMMITMENT_RATE,
    PACING_BAND,
    PACING_SENSITIVITY,
    PRIVATE_ASSETS,
    START_CASH,
    START_TARGETS,
    PlayResult,
    default_opening_book,
    plan_commitments,
    simulate_play,
)
from ah.port.book import OpeningBook

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


@pytest.fixture(scope="module")
def stagflation():
    return _paths()


def _quarters_equal(a: PlayResult, b: PlayResult) -> bool:
    """Every field of every quarter, exactly. Comparing a subset would let a
    bad reconstruction pass while the aggregates happened to match."""
    return [dataclasses.astuple(q) for q in a.quarters] == [
        dataclasses.astuple(q) for q in b.quarters
    ]


class TestEquivalence:
    def test_the_default_book_reproduces_the_derived_decade_exactly(self, stagflation):
        """The load-bearing test. Serve the default, feed it back, compare."""
        derived = simulate_play(stagflation, None)
        entered = simulate_play(stagflation, None, opening_book=default_opening_book(START_TARGETS))
        assert _quarters_equal(derived, entered)
        assert derived.final_value == entered.final_value
        assert derived.forced_secondaries == entered.forced_secondaries
        assert derived.total_forced_sales == entered.total_forced_sales
        assert derived.forced_sale_quarters == entered.forced_sale_quarters

    def test_equivalence_holds_with_decisions_too(self, stagflation):
        decisions = {11: "derisk", 23: "leanin", 35: "secondary"}
        derived = simulate_play(stagflation, decisions)
        entered = simulate_play(
            stagflation, decisions, opening_book=default_opening_book(START_TARGETS)
        )
        assert _quarters_equal(derived, entered)

    def test_the_book_round_trips_through_json(self, stagflation):
        """What the session row stores is JSON, not a Python object."""
        book = default_opening_book(START_TARGETS)
        revived = OpeningBook.model_validate(json.loads(book.model_dump_json()))
        assert revived.digest() == book.digest()
        assert _quarters_equal(
            simulate_play(stagflation, None, opening_book=book),
            simulate_play(stagflation, None, opening_book=revived),
        )


class TestAnEnteredBookActuallyChangesThings:
    def test_a_different_allocation_gives_a_different_decade(self, stagflation):
        """Guards against the override being silently ignored — the failure
        mode that would make every test above pass for the wrong reason."""
        book = default_opening_book(START_TARGETS)
        moved = book.model_copy(deep=True)
        moved.liquid["equity"] -= 5.0
        moved.liquid["bonds"] += 5.0
        entered = simulate_play(stagflation, None, opening_book=moved)
        derived = simulate_play(stagflation, None)
        assert not _quarters_equal(derived, entered)

    def test_the_opening_cash_comes_from_the_book(self, stagflation):
        book = default_opening_book(START_TARGETS)
        moved = book.model_copy(deep=True)
        moved.cash += 1.0
        moved.liquid["equity"] -= 1.0
        result = simulate_play(stagflation, None, opening_book=moved)
        derived = simulate_play(stagflation, None)
        assert result.quarters[0].cash != derived.quarters[0].cash

    def test_a_changed_rung_gives_a_different_decade(self, stagflation):
        """The private ladder is the substantive half of an entered book. Without
        this, deleting `rungs = book.cohorts(asset)` and always deriving the
        ladder leaves every other test in this file green.

        Only the rung's NAV moves; cash and liquid stay exactly as the default
        book has them, so any divergence can only have come from the private
        ladder being consulted, not from the (separately-guarded) cash path.
        """
        book = default_opening_book(START_TARGETS)
        moved = book.model_copy(deep=True)
        rung = moved.private["pe"][0]["value"]
        rung["nav_true"] *= 0.5
        rung["nav_reported"] = rung["nav_true"]
        entered = simulate_play(stagflation, None, opening_book=moved)
        derived = simulate_play(stagflation, None)
        assert not _quarters_equal(derived, entered)


class TestDeletability:
    def test_none_is_the_derived_path(self, stagflation):
        """opening_book=None must not merely resemble the old behaviour."""
        result = simulate_play(stagflation, None, opening_book=None)
        for sleeve in PRIVATE_ASSETS:
            assert result.quarters[0].private_true[sleeve] > 0.0
        assert result.quarters[0].nav_true > 0.0


# --------------------------------------------------------------------------
# su-app-07 task 2: the POLICY target is a second, independent number.
# --------------------------------------------------------------------------


def _decades_equal(a: PlayResult, b: PlayResult) -> bool:
    """The WHOLE result, field by field — quarters, aggregates, sale log and
    opening snapshot. Stronger than ``_quarters_equal`` above, which stops at
    the quarter list and so cannot see a divergence that only reaches
    ``final_value`` or ``sale_log``."""
    return dataclasses.asdict(a) == dataclasses.asdict(b)


def _retargeted(book: OpeningBook, **moves: float) -> OpeningBook:
    """A copy of ``book`` whose POLICY targets moved and whose VALUES did not.

    This is the whole su-app-07 separation in one helper: nothing the
    institution HOLDS changes, only what it is aiming at.
    """
    out = book.model_copy(deep=True)
    targets = dict(out.effective_targets())
    targets.update(moves)
    out.targets = targets
    return out


class TestPolicyTargetsReachTheEngine:
    """The load-bearing property of su-app-07: ``OpeningBook.targets`` is what
    the programme paces against, and it is not the same number as the opening
    values. Every assertion here is on the DECADE — a pre-fill that displays
    the target while the engine paces off something else is exactly the defect
    (su-app-06 C1) these tests exist to catch."""

    def test_a_policy_target_that_differs_from_the_values_changes_the_decade(self, stagflation):
        """THE separation test. Two runs of the SAME opening values — same
        liquid, same cash, same rungs — differing only in the policy targets
        the book declares. If ``effective_targets()`` never reaches
        ``simulate_play`` the two decades are bit-identical."""
        book = default_opening_book(START_TARGETS)
        tilted = _retargeted(book, equity=27.0, pe=26.0)

        # the values really are untouched; only the aim moved.
        assert tilted.liquid == book.liquid
        assert tilted.private == book.private
        assert tilted.cash == book.cash
        assert sum(tilted.effective_targets().values()) + tilted.cash == pytest.approx(100.0)
        assert tilted.effective_targets() != book.effective_targets()

        flat = simulate_play(stagflation, None, opening_book=book)
        moved = simulate_play(stagflation, None, opening_book=tilted)

        assert not _decades_equal(flat, moved)
        assert moved.final_value != pytest.approx(flat.final_value)
        # and name the mechanism: the first commitment quarter paces off the
        # target, so a bigger private target commits more into the ladder.
        assert moved.quarters[4].new_commitments > flat.quarters[4].new_commitments

    def test_a_book_with_no_entered_targets_paces_off_its_own_values(self, stagflation):
        """Ruling B's fence. ``targets=None`` means "the book's own values are
        the policy", so the DERIVED default book — whose values are
        ``START_TARGETS`` — still plays su-app-06's decade.

        ``_decades_equal(derived, entered)`` here depends on ``_seed_ladder``
        scaling each private sleeve's rungs to a NAV that sums back to
        ``START_TARGETS`` with ZERO float dust — that is what makes
        ``effective_targets()``'s fallback (``{**liquid, **target_nav()}``)
        bit-identical to the derived path's targets. It holds today and is
        worth pinning. But a future rounding change inside the ladder would
        break this test for a reason that has nothing to do with policy
        targets: read a failure here as "the ladder's NAVs moved", not as
        "the targets fallback regressed", and check ``target_nav()`` against
        ``START_TARGETS`` before touching anything in ``book.py``."""
        book = default_opening_book(START_TARGETS)
        untargeted = book.model_copy(deep=True)
        untargeted.targets = None
        assert untargeted.effective_targets() == pytest.approx(START_TARGETS)

        derived = simulate_play(stagflation, None)
        entered = simulate_play(stagflation, None, opening_book=untargeted)
        assert _decades_equal(derived, entered)

    def test_the_commit_cap_follows_the_policy_target_not_the_opening_nav(self, stagflation):
        """``simulate_play``'s own enforcement point, the third of three. The
        book holds 20 points of pe NAV (old cap 7.20) and declares a 26-point
        pe target (new cap 9.36), so 9.0 is legal only if the cap reads the
        target."""
        book = _retargeted(default_opening_book(START_TARGETS), equity=27.0, pe=26.0)
        cap = 2.0 * 26.0 * _ANNUAL_COMMITMENT_RATE
        assert book.target_nav()["pe"] * 2.0 * _ANNUAL_COMMITMENT_RATE < 9.0 < cap

        result = simulate_play(
            stagflation, {11: {"action": "hold", "commitments": {"pe": 9.0}}}, opening_book=book
        )
        assert result.quarters[4].new_commitments > 9.0  # pe's 9.0 plus pc and re

    def test_a_commit_over_the_policy_target_is_still_refused(self, stagflation):
        """Re-basing the bound must not remove it."""
        book = _retargeted(default_opening_book(START_TARGETS), equity=27.0, pe=26.0)
        with pytest.raises(ValueError, match="declared bound"):
            simulate_play(
                stagflation,
                {11: {"action": "hold", "commitments": {"pe": 9.4}}},
                opening_book=book,
            )


class TestThePacingDenominatorFollowsTheBooksCash:
    """Ruling C. ``_policy_private_weight`` divides by ``sum(targets) + cash``.
    Once ``targets`` are a book's own numbers they sum to ``100 - book.cash``,
    so a book holding cash other than 2.0 gets the wrong denominator unless
    its own cash is threaded through."""

    #: values: 31 + 12 + 5 + 5 + 8 liquid, 35 private NAV, 4 cash = 100.
    _CASH = 4.0
    _TARGETS_HI: ClassVar[dict[str, float]] = {  # private total 35, all targets total 96
        "equity": 31.0,
        "bonds": 12.0,
        "hy": 5.0,
        "commodities": 5.0,
        "reits": 8.0,
        "pe": 20.0,
        "pc": 8.0,
        "re": 7.0,
    }
    _TARGETS_LO: ClassVar[dict[str, float]] = {  # private total 29
        **_TARGETS_HI,
        "equity": 37.0,
        "pe": 14.0,
    }

    def test_plan_commitments_reads_the_cash_it_is_given(self):
        """The public pre-fill, at a reported weight that leaves the
        multiplier strictly inside the band so nothing is hidden by a clip."""
        private = sum(self._TARGETS_HI[a] for a in PRIVATE_ASSETS)
        total = sum(self._TARGETS_HI.values())
        w = 0.35
        own = plan_commitments(w, self._TARGETS_HI, cash=self._CASH)
        default_cash = plan_commitments(w, self._TARGETS_HI)

        m_own = 1.0 + PACING_SENSITIVITY * (private / (total + self._CASH) - w)
        m_default = 1.0 + PACING_SENSITIVITY * (private / (total + START_CASH) - w)
        assert PACING_BAND[0] < m_own < PACING_BAND[1]
        assert PACING_BAND[0] < m_default < PACING_BAND[1]

        assert own["pe"] == pytest.approx(20.0 * _ANNUAL_COMMITMENT_RATE * m_own)
        assert default_cash["pe"] == pytest.approx(20.0 * _ANNUAL_COMMITMENT_RATE * m_default)
        assert own["pe"] != pytest.approx(default_cash["pe"])

    def _book(self, targets: dict[str, float]) -> OpeningBook:
        book = default_opening_book(START_TARGETS).model_copy(deep=True)
        book.cash = self._CASH
        book.liquid["equity"] -= 2.0  # values still total 100
        book.targets = dict(targets)
        return book

    def test_simulate_play_paces_on_the_books_own_cash(self, stagflation):
        """The reported private weight at the first commitment quarter is
        unknowable from the outside, so it is CANCELLED rather than guessed.

        Two books with byte-identical VALUES differ only in their declared
        targets. No commitment is made before quarter 4, so the portfolio each
        one presents to the pacing rule at that quarter is the same, and the
        same reported weight ``w`` enters both multipliers. Running each book
        under the fixed rule recovers its own base pace exactly, so the ratio
        is the multiplier itself; subtracting the two multipliers cancels
        ``w`` and leaves ``PACING_SENSITIVITY x (P_hi - P_lo) / (S + cash)`` —
        a closed form that names the denominator and nothing else.
        """
        hi, lo = self._book(self._TARGETS_HI), self._book(self._TARGETS_LO)
        assert hi.liquid == lo.liquid and hi.cash == lo.cash and hi.private == lo.private

        def _multiplier(book: OpeningBook) -> float:
            policy = simulate_play(stagflation, None, opening_book=book)
            fixed = simulate_play(stagflation, None, opening_book=book, pacing_rule="fixed")
            return policy.quarters[4].new_commitments / fixed.quarters[4].new_commitments

        m_hi, m_lo = _multiplier(hi), _multiplier(lo)
        # self-guard: a clipped multiplier would make the difference below
        # meaningless, so prove neither sits on the band.
        assert PACING_BAND[0] < m_lo < m_hi < PACING_BAND[1]

        private_hi = sum(self._TARGETS_HI[a] for a in PRIVATE_ASSETS)
        private_lo = sum(self._TARGETS_LO[a] for a in PRIVATE_ASSETS)
        total = sum(self._TARGETS_HI.values())
        own = PACING_SENSITIVITY * (private_hi - private_lo) / (total + self._CASH)
        wrong = PACING_SENSITIVITY * (private_hi - private_lo) / (total + START_CASH)

        assert m_hi - m_lo == pytest.approx(own, abs=1e-9)
        assert m_hi - m_lo != pytest.approx(wrong, abs=1e-9)
