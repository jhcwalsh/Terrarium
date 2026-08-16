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
from typing import Any

import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    PRIVATE_ASSETS,
    START_TARGETS,
    PlayResult,
    default_opening_book,
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
