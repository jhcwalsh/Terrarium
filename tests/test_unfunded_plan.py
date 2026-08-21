"""app-open-04 Item C — unfunded commitments bite the pacing plan.

Before this change ``book_commitment_plan`` read the book's reported NAV and
ignored the entered book's UNFUNDED commitments entirely: an analyst could
enter a book carrying twice the unfunded the pacing model would ever hold at
the target weight, and the derived kickoff plan kept stacking new vintages on
top at full pace.

The rule under test, in one sentence: **each window's pace is reduced by the
sleeve's remaining excess unfunded — the amount by which the book's projected
unfunded still exceeds the pacing model's own steady-state stock for the
target — floored at zero**, where

* the steady-state stock is the unfunded held by ``_seed_ladder`` — the
  model's OWN staggered opening book at the target weight (the declared
  rc_curve, ~90% called by year 10, ER-6 expiry at lapse; no invented
  constants), and
* the remaining excess is the book's rungs and that steady ladder projected
  side by side on the declared call curve with ``f_call = 1`` (the kickoff
  plan cannot see the tape — the same leak-free reasoning that keeps
  ``default_commitment_plan`` on the FIXED rule). Unfunded is
  return-independent in the cohort recursion, so the projection is exact,
  not an approximation.

A sleeve at or under its steady-state stock keeps today's plan BIT-IDENTICAL
(the regression pins below); a sleeve over it gets windows scaled down —
zero while the excess works off, partial as it approaches typical — so an
over-committed entered book gets a plan that pauses rather than keeps
stacking.
"""

from __future__ import annotations

import json
from typing import ClassVar

import pytest

from ah.play import (
    PRIVATE_ASSETS,
    START_TARGETS,
    book_commitment_plan,
    default_opening_book,
    steady_state_unfunded,
    unfunded_plan_note,
)
from ah.port.adapter import GEN_START_TARGETS
from ah.port.book import OpeningBook, validate_plan

# reuse the established app/client fixture — see tests/test_serve.py. Import
# ONLY the fixture name, never the Test* classes.
from test_serve import service  # noqa: F401  (pytest fixture)


def _sleeve_unfunded(book: OpeningBook, sleeve: str) -> float:
    return sum(float(r["commitment"]["unfunded"]) for r in book.private[sleeve])


def _overcommitted(book: OpeningBook, sleeve: str, extra_per_rung: float) -> OpeningBook:
    """The book with `extra_per_rung` more UNFUNDED on every rung of one
    sleeve. `committed` rises by the same amount so the recycling identity
    (paid_in + unfunded = committed + recycled) still holds exactly, and NAV
    is untouched — the book still totals 100 and its reported private weight
    (the DN-5 flex input) does not move, so any plan change is the unfunded
    channel and nothing else."""
    doc = json.loads(book.model_dump_json())
    for rung in doc["private"][sleeve]:
        rung["commitment"]["unfunded"] += extra_per_rung
        rung["commitment"]["committed"] += extra_per_rung
    return OpeningBook.model_validate(doc)


class TestSteadyStateUnfunded:
    @pytest.mark.parametrize("targets", [START_TARGETS, GEN_START_TARGETS])
    def test_the_default_books_unfunded_is_the_steady_state_exactly(self, targets):
        """The derived default book IS the model's steady state — its ladder
        is built by the same ``_seed_ladder`` the steady-state derivation
        reads, so per-sleeve unfunded matches to the float. This is also why
        the pause can never fire on the untouched default."""
        book = default_opening_book(targets)
        steady = steady_state_unfunded(dict(targets))
        for sleeve in PRIVATE_ASSETS:
            assert _sleeve_unfunded(book, sleeve) == steady[sleeve]

    def test_the_steady_state_scales_linearly_with_the_target(self):
        # _seed_ladder scales every rung by target/total, so the implied
        # steady-state stock is linear in the target weight — a doubled
        # target holds double the typical unfunded.
        one = steady_state_unfunded({**START_TARGETS, "pe": 10.0})
        two = steady_state_unfunded({**START_TARGETS, "pe": 20.0})
        assert two["pe"] == pytest.approx(2.0 * one["pe"], rel=1e-9)

    def test_a_zero_target_implies_zero_steady_unfunded(self):
        steady = steady_state_unfunded({**START_TARGETS, "pe": 0.0})
        assert steady["pe"] == 0.0


class TestRegressionPinTheDefaultPlan:
    """Pinned BEFORE the unfunded adjustment landed (2026-08-20, HEAD
    2a20d77): the default derived book is at its steady state, so the
    adjustment must be exactly inactive and these literals must not move."""

    #: window 0 and window 8 of the derived plan for the served default book,
    #: per sleeve — captured from book_commitment_plan at 2a20d77.
    _PIN: ClassVar[dict[str, tuple[float, float]]] = {
        "pe": (3.6, 5.7378530683),
        "pc": (1.44, 2.2951412273),
        "re": (0.9, 1.4344632671),
        "infra": (0.9, 1.4344632671),
    }

    @pytest.mark.parametrize("targets", [START_TARGETS, GEN_START_TARGETS])
    def test_the_default_books_plan_is_unchanged(self, targets):
        plan = book_commitment_plan(default_opening_book(targets))
        for sleeve, (first, last) in self._PIN.items():
            assert plan.points[sleeve][0] == pytest.approx(first, abs=1e-9)
            assert plan.points[sleeve][8] == pytest.approx(last, abs=1e-9)

    def test_the_default_books_note_is_inactive(self):
        note = unfunded_plan_note(default_opening_book(START_TARGETS))
        assert note["active"] is False
        assert all(not s["paused"] for s in note["sleeves"].values())


class TestUnfundedPause:
    def test_a_heavy_unfunded_book_pauses_that_sleeves_plan(self):
        """FAIL-FIRST (app-open-04 Item C): the default pe ladder carries
        ~8.99 unfunded at steady state; +1.0 per rung (+10 points, more than
        double) is an over-committed book. Today the plan ignores it — after
        the fix the early windows must fall, window 0 to a full pause."""
        book = default_opening_book(START_TARGETS)
        heavy = _overcommitted(book, "pe", 1.0)
        base = book_commitment_plan(book)
        adjusted = book_commitment_plan(heavy)
        assert adjusted.points["pe"][0] == 0.0, "an over-doubled unfunded stock must pause"
        assert sum(adjusted.points["pe"]) < sum(base.points["pe"])

    def test_the_untriggered_sleeves_are_bit_identical(self):
        # the trigger is per sleeve: pc/re/infra sit at their steady state
        # and keep the exact floats they had.
        book = default_opening_book(START_TARGETS)
        heavy = _overcommitted(book, "pe", 1.0)
        base = book_commitment_plan(book)
        adjusted = book_commitment_plan(heavy)
        for sleeve in ("pc", "re", "infra"):
            assert adjusted.points[sleeve] == base.points[sleeve]

    def test_the_plan_resumes_once_the_excess_works_off(self):
        """A moderate overhang pauses the near windows and resumes later —
        the plan pauses, it does not abandon the programme (the rc_curve
        works a ~+3-point excess off within a few years)."""
        book = default_opening_book(START_TARGETS)
        moderate = _overcommitted(book, "pe", 0.3)  # +3.0 points of unfunded
        adjusted = book_commitment_plan(moderate)
        base = book_commitment_plan(book)
        pts = adjusted.points["pe"]
        assert pts[0] < base.points["pe"][0]
        assert pts[-1] > 0.0, "the pause must end once unfunded is back to typical"
        # and it resumes TOWARD THE BASE PLAN, not toward some re-anchored
        # pace: by the last window the remaining excess is dust, so the
        # window is within a few percent of the unadjusted number.
        assert pts[-1] > 0.9 * base.points["pe"][-1]

    def test_a_mild_overhang_scales_down_without_a_full_stop(self):
        book = default_opening_book(START_TARGETS)
        mild = _overcommitted(book, "pe", 0.05)  # +0.5 points
        base = book_commitment_plan(book).points["pe"][0]
        got = book_commitment_plan(mild).points["pe"][0]
        assert 0.0 < got < base

    def test_the_adjusted_plan_still_validates_and_is_deterministic(self):
        book = default_opening_book(START_TARGETS)
        heavy = _overcommitted(book, "pe", 1.0)
        plan = book_commitment_plan(heavy)
        validate_plan(plan, heavy.effective_targets())  # must not raise
        again = book_commitment_plan(heavy)
        assert plan.points == again.points

    def test_more_overhang_never_means_more_commitment(self):
        # monotone in the overhang: window for a heavier book is <= the
        # window for a lighter one, for every window.
        book = default_opening_book(START_TARGETS)
        lighter = book_commitment_plan(_overcommitted(book, "pe", 0.2))
        heavier = book_commitment_plan(_overcommitted(book, "pe", 0.6))
        for light, heavy in zip(lighter.points["pe"], heavier.points["pe"], strict=True):
            assert heavy <= light + 1e-12


class TestUnfundedPlanNote:
    """The payload behind the Cashflow-projections tab's one plain sentence:
    "commitments pause while existing unfunded works off - your unfunded is
    X vs Y typical for this target". X and Y are served, never derived
    client-side (DN-3 W5)."""

    def test_the_note_carries_the_books_own_numbers(self):
        book = default_opening_book(START_TARGETS)
        heavy = _overcommitted(book, "pe", 1.0)
        note = unfunded_plan_note(heavy)
        assert note["active"] is True
        assert note["sleeves"]["pe"]["paused"] is True
        assert note["sleeves"]["pe"]["unfunded"] == pytest.approx(
            _sleeve_unfunded(heavy, "pe"), abs=1e-4
        )
        assert note["sleeves"]["pe"]["steady_state"] == pytest.approx(
            steady_state_unfunded(heavy.effective_targets())["pe"], abs=1e-4
        )
        assert note["unfunded_total"] == pytest.approx(
            sum(_sleeve_unfunded(heavy, s) for s in PRIVATE_ASSETS), abs=1e-3
        )
        assert note["steady_state_total"] == pytest.approx(
            sum(steady_state_unfunded(heavy.effective_targets()).values()), abs=1e-3
        )

    def test_a_steady_book_reports_inactive_with_matching_totals(self):
        note = unfunded_plan_note(default_opening_book(START_TARGETS))
        assert note["active"] is False
        assert note["unfunded_total"] == pytest.approx(note["steady_state_total"], abs=1e-3)


@pytest.mark.enable_socket
class TestServedUnfundedNote:
    """`POST /book/plan` carries the note beside the plan (app-open-04 Item
    C): the entry screen renders the served numbers, it derives none of them
    (DN-3 W5). Uses tests/test_serve.py's established service fixture."""

    @staticmethod
    def _overcommitted_doc(book_doc: dict, sleeve: str, extra: float) -> dict:
        doc = json.loads(json.dumps(book_doc))
        for rung in doc["private"][sleeve]:
            rung["commitment"]["unfunded"] += extra
            rung["commitment"]["committed"] += extra
        return doc

    def test_the_default_book_serves_an_inactive_note(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        r = client.post("/book/plan", json={"run_id": rid, "book": default["book"]})
        assert r.status_code == 200, r.text
        note = r.json()["unfunded"]
        assert note["active"] is False
        assert set(note["sleeves"]) == set(PRIVATE_ASSETS)

    def test_a_heavy_book_serves_the_pause_and_a_paused_plan(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        heavy = self._overcommitted_doc(default["book"], "pe", 1.0)
        r = client.post("/book/plan", json={"run_id": rid, "book": heavy})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["unfunded"]["active"] is True
        assert body["unfunded"]["sleeves"]["pe"]["paused"] is True
        assert body["unfunded"]["unfunded_total"] > body["unfunded"]["steady_state_total"]
        assert body["plan"]["points"]["pe"][0] == 0.0
        # the served plan is book_commitment_plan exactly — one derivation
        expected = book_commitment_plan(OpeningBook.model_validate(heavy))
        assert body["plan"]["points"]["pe"] == pytest.approx(expected.points["pe"])

    def test_the_paused_plan_round_trips_through_the_session_door(self, service):
        # the plan the server itself derives for an over-committed book must
        # never 422 when POSTed straight back with that book.
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        heavy = self._overcommitted_doc(default["book"], "pe", 1.0)
        plan = client.post("/book/plan", json={"run_id": rid, "book": heavy}).json()["plan"]
        r = client.post("/sessions", json={"run_id": rid, "book": heavy, "plan": plan})
        assert r.status_code == 201, r.text
