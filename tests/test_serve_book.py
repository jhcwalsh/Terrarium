"""The book entry endpoints (su-app-06).

The server is the authority: it serves the default, validates what comes
back, and decides ranked eligibility. The app is not trusted to do any of it.

Socket opt-in, same reason as ``tests/test_serve.py``: FastAPI's TestClient
drives the ASGI app in-process (no bytes leave the interpreter) but asyncio's
Windows event loop needs an internal ``socket.socketpair`` as its wakeup
pipe, which pytest-socket blocks by default.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from ah.cioview import WATCH_FRACTION
from ah.core.institution import decision_months

# reuse this module's established app/client fixtures — see tests/test_serve.py.
# Import ONLY the fixture names (plus the plain `_play_through` helper), never
# the Test* classes (that would collect their tests a second time).
from test_serve import _play_through, gen_service, service  # noqa: F401  (pytest fixtures)

pytestmark = pytest.mark.enable_socket


def _shifted_book(default_book: dict, amount: float = 15.0) -> dict:
    """A materially different book: `amount` points off equity onto bonds."""
    book = dict(default_book)
    book["liquid"] = dict(default_book["liquid"])
    book["liquid"]["equity"] -= amount
    book["liquid"]["bonds"] += amount
    return book


def _retargeted_book(default_book: dict, **moves: float) -> dict:
    """The served default book with its POLICY targets moved and its VALUES
    left exactly as served (su-app-07). Nothing the institution holds changes."""
    return {**default_book, "targets": {**default_book["targets"], **moves}}


def _replanned(default_plan: dict, sleeve: str, value: float) -> dict:
    """The served default plan with one sleeve flattened to `value` everywhere."""
    plan = {**default_plan, "points": {k: list(v) for k, v in default_plan["points"].items()}}
    plan["points"][sleeve] = [value] * len(plan["points"][sleeve])
    return plan


#: A band no realized weight can leave — used to READ the served weights back
#: before placing a real band relative to them (su-app-07 task 3).
_WIDE: tuple[float, float] = (0.0, 100.0)

#: TIGHT, OFF-CENTRE bands — one per sleeve of the toy world, each at most two
#: points wide and each placed AWAY from that sleeve's own `START_TARGETS`
#: value (33/12/5/5/8/20/8/7). This is the book the inertness test plays.
#:
#: `_WIDE` will not do there, and the first version of that test was wrong to
#: use it. The most plausible way a range could leak into the engine is as a
#: rebalance or clamp bound, and `[0, 100]` is a no-op clamp on every
#: reachable weight — the test would have stayed green straight through
#: exactly the defect it exists to catch. Every band below EXCLUDES its
#: sleeve's own policy target, so a bound derived from one would have to move
#: that sleeve on the very first rebalance, in the first quarter.
#:
#: A target outside its own declared range is legal — `validate_book` returns
#: a warning string rather than raising (su-app-07's deliberate choice) —
#: which is what makes this book postable at all. The test asserts the 201
#: rather than assuming it.
_TIGHT: dict[str, tuple[float, float]] = {
    "equity": (30.0, 32.0),
    "bonds": (13.0, 15.0),
    "hy": (2.0, 3.0),
    "commodities": (6.0, 7.0),
    "reits": (9.0, 10.0),
    "pe": (5.0, 7.0),
    "pc": (10.0, 11.0),
    "re": (3.0, 4.0),
}


def _banded_book(default_book: dict, ranges: dict[str, tuple[float, float]]) -> dict:
    """The served default book with reporting bands declared and NOTHING else
    touched — same values, same policy targets, same cash (su-app-07 task 3).
    A range is a read-layer declaration; it must not move a number."""
    return {**default_book, "ranges": {k: list(v) for k, v in ranges.items()}}


def _banded_session(
    client,
    rid: str,
    default: dict,
    ranges: dict[str, tuple[float, float]],
    to_month: int = 24,
    basis: str = "reported",
) -> dict:
    """Open a session on the default book plus `ranges`, reveal to `to_month`,
    and return the session document."""
    body = {
        "run_id": rid,
        "basis": basis,
        "book": _banded_book(default["book"], ranges),
        "plan": default["plan"],
    }
    r = client.post("/sessions", json=body)
    assert r.status_code == 201, r.text
    sid, months = r.json()["session_id"], r.json()["months"]
    _reveal_mid_decade(client, sid, months, to_month)
    return client.get(f"/sessions/{sid}").json()


def _all_sleeves(default: dict) -> list[str]:
    return [*default["liquid_sleeves"], "pe", "pc", "re"]


def _weights(doc: dict, plane: str) -> dict[str, float]:
    return {s["sleeve"]: s[plane]["weight"] for s in doc["band_report"]["sleeves"]}


def _entry(doc: dict, sleeve: str) -> dict:
    return next(s for s in doc["band_report"]["sleeves"] if s["sleeve"] == sleeve)


def _reveal_mid_decade(client, sid: str, months: int, to_month: int) -> None:
    """Decide every window strictly before `to_month` (holding), then reveal
    up to it — `advance_reveal` blocks revealing past an undecided window."""
    for m in decision_months(months):
        if m >= to_month:
            break
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1}).status_code == 200
        r = client.post(f"/sessions/{sid}/decisions", json={"month": m, "action": "hold"})
        assert r.status_code == 200, r.text
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": to_month}).status_code == 200


class TestDefaultBookEndpoint:
    def test_it_serves_a_book_a_plan_and_the_worlds_sleeve_set(self, service):
        client, _db, rid = service
        r = client.get(f"/book/default?run_id={rid}")
        assert r.status_code == 200
        body = r.json()
        # su-app-07 Ruling D: default_opening_book now populates `targets`,
        # at the new state_version ("opening-book-0.2").
        assert body["book"]["state_version"] == "opening-book-0.2"
        assert body["plan"]["state_version"] == "commitment-plan-0.1"
        assert set(body["book"]["liquid"]) == set(body["liquid_sleeves"])
        assert len(body["book_digest"]) == 64

    def test_an_unknown_run_is_404(self, service):
        client, _db, _rid = service
        assert client.get("/book/default?run_id=nope").status_code == 404

    def test_the_generated_worlds_sleeve_set_has_no_reits(self, gen_service):
        """A toy-v0 world's book carries a `reits` sleeve; a generated
        world's does not (GEN_START_TARGETS folds reits into equity). This
        exercises the engine-dependent branch of `_world_book`."""
        client, _db, rid = gen_service
        r = client.get(f"/book/default?run_id={rid}")
        assert r.status_code == 200
        body = r.json()
        assert "reits" not in body["book"]["liquid"]
        assert set(body["book"]["liquid"]) == set(body["liquid_sleeves"])


class TestCreateSessionWithABook:
    def test_the_default_book_submitted_back_keeps_ranked(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        r = client.post(
            "/sessions",
            json={
                "run_id": rid,
                "ranked": True,
                "participant": "alice",
                "book": default["book"],
                "plan": default["plan"],
            },
        )
        assert r.status_code == 201
        assert r.json()["ranked"] is True

    def test_an_edited_book_is_demoted_to_practice(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = default["book"]
        book["liquid"]["equity"] -= 5.0
        book["liquid"]["bonds"] += 5.0
        r = client.post(
            "/sessions",
            json={
                "run_id": rid,
                "ranked": True,
                "participant": "alice",
                "book": book,
                "plan": default["plan"],
            },
        )
        assert r.status_code == 201
        assert r.json()["ranked"] is False, "a custom book must never be ranked"

    def test_an_edited_plan_is_also_demoted(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        plan["points"]["pe"][3] = 0.0  # a cut year
        r = client.post(
            "/sessions",
            json={
                "run_id": rid,
                "ranked": True,
                "participant": "alice",
                "book": default["book"],
                "plan": plan,
            },
        )
        assert r.json()["ranked"] is False

    def test_a_book_that_does_not_total_one_hundred_is_422_naming_the_rule(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = default["book"]
        book["cash"] += 3.0
        r = client.post("/sessions", json={"run_id": rid, "book": book})
        assert r.status_code == 422
        assert "must total 100" in r.json()["detail"]

    def test_a_foreign_sleeve_is_422(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = default["book"]
        book["liquid"]["gold"] = 0.0
        r = client.post("/sessions", json={"run_id": rid, "book": book})
        assert r.status_code == 422
        assert "gold" in r.json()["detail"]

    def test_a_plan_year_over_the_cap_is_422(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        plan["points"]["pe"][0] = 999.0
        r = client.post(
            "/sessions",
            json={"run_id": rid, "book": default["book"], "plan": plan},
        )
        assert r.status_code == 422
        assert "declared bound" in r.json()["detail"]

    def test_a_duplicate_cohort_id_is_422_at_the_door_not_a_500_later(self, service):
        """I4: ``Portfolio.add`` raises on a repeated key, so this book was
        accepted with a 201 and then 500'd on every read of the session."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = default["book"]
        book["private"]["pe"][1]["identity"]["cohort_id"] = book["private"]["pe"][0]["identity"][
            "cohort_id"
        ]
        r = client.post("/sessions", json={"run_id": rid, "book": book})
        assert r.status_code == 422
        assert "repeats cohort_id" in r.json()["detail"]

    def test_a_reserved_vintage_cohort_id_is_422_at_the_door(self, service):
        """I4's slower half: `{sleeve}-v{year}` is what the pacing plan mints
        during play, so the collision did not fire until mid-decade."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = default["book"]
        book["private"]["pe"][0]["identity"]["cohort_id"] = "pe-v3"
        r = client.post("/sessions", json={"run_id": rid, "book": book})
        assert r.status_code == 422
        assert "reserved cohort_id" in r.json()["detail"]

    def test_a_session_with_a_stored_book_replays_it(self, service):
        """The book is the book of record: reading the session back and
        marking to market must use the stored book, not the default."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = default["book"]
        book["liquid"]["equity"] -= 5.0
        book["liquid"]["bonds"] += 5.0
        sid = client.post(
            "/sessions",
            json={"run_id": rid, "book": book, "plan": default["plan"]},
        ).json()["session_id"]
        client.post(f"/sessions/{sid}/advance", json={"to_month": 6})
        custom = client.get(f"/sessions/{sid}").json()

        plain = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        client.post(f"/sessions/{plain}/advance", json={"to_month": 6})
        derived = client.get(f"/sessions/{plain}").json()

        assert custom["value"] != derived["value"]
        # the SAME stored book must go to both simulate_play calls — active
        # and twin — or alpha stops isolating decisions. `value` alone
        # cannot see the twin call at all; assert on `twin_value` directly.
        assert custom["twin_value"] != derived["twin_value"]

    def test_the_served_default_plan_round_trips_without_a_422(self, service):
        """`_world_book`'s plan and `create_session`'s entry-count check must
        agree on how many windows this world has — the server's own default
        must never 422 when it is POSTed straight back."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        r = client.post(
            "/sessions",
            json={"run_id": rid, "book": default["book"], "plan": default["plan"]},
        )
        assert r.status_code == 201, r.text

    def test_a_plan_with_the_wrong_entry_count_is_422_naming_the_rule(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        for sleeve in plan["points"]:
            plan["points"][sleeve] = plan["points"][sleeve][:-1]  # drop one window
        r = client.post(
            "/sessions",
            json={"run_id": rid, "book": default["book"], "plan": plan},
        )
        assert r.status_code == 422
        assert "expected" in r.json()["detail"]
        assert "decision window" in r.json()["detail"]


class TestBookThreadedThroughReplaySurfaces:
    """Task 5b: every session replay surface must use the stored book, not
    the derived default — `_mark_to_market` already gets this right; these
    tests pin down `/outcome` and `/cio`, which did not (task 5's gap)."""

    # actual decisions, identical on both sessions: with "hold" everywhere
    # the active replay is definitionally equal to its twin (both are the
    # hold-course institution), so alpha and every window contribution stay
    # at 0.0 regardless of the book — that would falsely look like the bug
    # persisted. Real actions are needed to make alpha and the per-window
    # attribution sensitive to which institution (book) played them.
    _ACTIONS: ClassVar[dict[int, str]] = {11: "derisk", 23: "leanin"}

    def test_outcome_differs_on_a_custom_book(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _shifted_book(default["book"])

        custom_sid = _play_through(client, rid, self._ACTIONS, book=book, plan=default["plan"])
        plain_sid = _play_through(client, rid, self._ACTIONS)

        custom_out = client.get(f"/sessions/{custom_sid}/outcome").json()
        plain_out = client.get(f"/sessions/{plain_sid}/outcome").json()

        # a half-threaded fix (active gets the book, twin does not) would
        # still move final_value while leaving twin_final_value/alpha fixed
        # to the derived twin — assert on both so it cannot hide.
        assert custom_out["final_value"] != pytest.approx(plain_out["final_value"])
        assert custom_out["twin_final_value"] != pytest.approx(plain_out["twin_final_value"])
        assert custom_out["alpha"] != pytest.approx(plain_out["alpha"])

    def test_window_attribution_differs_on_a_custom_book(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _shifted_book(default["book"])

        custom_sid = _play_through(client, rid, self._ACTIONS, book=book, plan=default["plan"])
        plain_sid = _play_through(client, rid, self._ACTIONS)

        custom_out = client.get(f"/sessions/{custom_sid}/outcome").json()
        plain_out = client.get(f"/sessions/{plain_sid}/outcome").json()

        assert custom_out["window_contributions"] != pytest.approx(
            plain_out["window_contributions"]
        )

    def test_cio_mid_decade_differs_on_a_custom_book(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _shifted_book(default["book"])

        r = client.post("/sessions", json={"run_id": rid, "book": book, "plan": default["plan"]})
        assert r.status_code == 201, r.text
        custom_sid = r.json()["session_id"]
        custom_months = r.json()["months"]
        plain_r = client.post("/sessions", json={"run_id": rid})
        plain_sid = plain_r.json()["session_id"]
        plain_months = plain_r.json()["months"]

        _reveal_mid_decade(client, custom_sid, custom_months, 24)
        _reveal_mid_decade(client, plain_sid, plain_months, 24)

        custom_cio = client.get(f"/sessions/{custom_sid}/cio").json()
        plain_cio = client.get(f"/sessions/{plain_sid}/cio").json()

        assert custom_cio["plan"]["totalValue"] != pytest.approx(plain_cio["plan"]["totalValue"])

    def test_session_value_agrees_with_its_own_outcome_at_decade_end(self, service):
        """The point of the whole task: what `GET /sessions/{sid}` reports
        during play (`_mark_to_market`, already correct) must agree with
        what `/outcome` reports once the decade is complete. Today those two
        surfaces disagree for a custom-book session — this is the
        consistency test that fails before the fix and passes after."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _shifted_book(default["book"])

        custom_sid = _play_through(client, rid, {}, book=book, plan=default["plan"])

        doc = client.get(f"/sessions/{custom_sid}").json()
        outcome = client.get(f"/sessions/{custom_sid}/outcome").json()

        assert doc["value"] == pytest.approx(outcome["final_value"])


class TestPlanDrivenLever:
    """su-app-06 section 4.3, and its fence: the lever's pre-fill measures
    deviation from the player's OWN stored plan, not the pacing rule — but
    only for a session that actually carries one."""

    def test_a_session_without_a_plan_keeps_todays_behaviour(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 11}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]  # recomputed from the reported weight
        assert doc["next_plan_basis"] is not None  # the F4 caveat still declared
        assert doc["plan_pace"] is None  # only meaningful when a plan is stored

    def test_a_plan_carrying_session_pre_fills_the_players_own_number(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        # a deliberate, flat, non-default plan
        plan["points"]["pe"] = [5.0] * len(plan["points"]["pe"])
        sid = client.post(
            "/sessions",
            json={"run_id": rid, "book": default["book"], "plan": plan},
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 11}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]["pe"] == pytest.approx(5.0)
        assert doc["next_plan_basis"] is None  # nothing is being approximated

    def test_the_pacing_rules_view_is_shown_beside_it_not_applied(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        plan["points"]["pe"] = [5.0] * len(plan["points"]["pe"])
        sid = client.post(
            "/sessions",
            json={"run_id": rid, "book": default["book"], "plan": plan},
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 11}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["plan_pace"] is not None
        assert doc["plan_pace"]["pe"] != pytest.approx(5.0), (
            "the flex must be a displayed comparison, not the applied number"
        )

    def test_the_pre_fill_tracks_the_window_not_just_the_plan(self, service):
        """A flat plan cannot tell a right window index from a wrong one:
        every entry is 5.0, so any in-bounds index passes. Give each window a
        distinct value and the index itself becomes the thing under test."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        n = len(plan["points"]["pe"])
        # Values must stay under the lever's declared bound (0..2x the
        # sleeve's plan pace, `validate_plan`), so scale the ramp off the
        # server's OWN default pace instead of a magic constant: the max
        # point (step * (n - 1)) stays below the default pace itself, which
        # is in turn below the 2x cap.
        step = default["plan"]["points"]["pe"][0] / n
        plan["points"]["pe"] = [round(step * i, 4) for i in range(n)]  # 0.0, step, 2*step, ...
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": default["book"], "plan": plan}
        ).json()["session_id"]

        # first window: months 0..11 revealed, last closed quarter is 2 -> window 0
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 11}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]["pe"] == pytest.approx(0.0)

        # deciding month 11 requires the pointer past it first
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        # decide window 0, then reveal into window 1: quarter 6 -> window 1
        r = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"})
        assert r.status_code == 200, r.text
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 23}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]["pe"] == pytest.approx(step)

    def test_the_pre_fill_indexes_the_window_the_player_is_actually_standing_at(self, service):
        """C1b. ``record_decision`` refuses a window until the pointer has
        passed it (``revealed_months >= month + 1``), and ``Play.tsx`` opens
        the lever on exactly that state (``revealed_months === nextWindow +
        1``). So at window 0 the real pointer is 12, not 11 — and the
        quarter-derived index ``(quarter + 1) // 4`` reads 1 there, showing
        the player NEXT year's plan number while the engine commits this
        year's. The window ordinal has to come from the window, not the
        pointer.

        The sibling test above reveals to 11, which is a state no player can
        decide from; this one stands where the lever is actually rendered.
        """
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = default["plan"]
        n = len(plan["points"]["pe"])
        step = default["plan"]["points"]["pe"][0] / n
        plan["points"]["pe"] = [round(step * i, 4) for i in range(n)]
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": default["book"], "plan": plan}
        ).json()["session_id"]

        # window 0 is open: the pointer sits one month past month 11
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]["pe"] == pytest.approx(0.0)

        # decide it, walk to window 1, and stand where the lever opens again
        r = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"})
        assert r.status_code == 200, r.text
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 24}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]["pe"] == pytest.approx(step)


class TestTheStoredPlanReachesTheEngine:
    """C1 — spec sections 2 and 4.3: on a plan-carrying session an UNTOUCHED
    lever commits the plan's number for that window, exactly.

    Before this fix the stored plan reached the display and stopped there.
    The client sends no ``commitments`` while the lever is untouched, and
    ``simulate_play`` then falls through to the policy pacing rule — so the
    window showed the analyst's 5.00 and the simulator committed ~3.18.

    Every test here asserts on the DECADE. Asserting on the pre-fill is what
    let the defect through the first time: the pre-fill was always right.
    """

    def test_an_untouched_lever_plays_the_plan_not_the_pacing_rule(self, service):
        """Two sessions on the SAME book, differing only in the plan, played
        through with the lever untouched at every window. Any difference in
        the decade can only have come from the plan reaching the engine."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        cut = _replanned(default["plan"], "pe", 0.0)  # commit nothing to pe, ever

        held_sid = _play_through(client, rid, {}, book=default["book"], plan=default["plan"])
        cut_sid = _play_through(client, rid, {}, book=default["book"], plan=cut)

        held = client.get(f"/sessions/{held_sid}/outcome").json()
        starved = client.get(f"/sessions/{cut_sid}/outcome").json()
        assert starved["final_value"] != pytest.approx(held["final_value"]), (
            "a nine-year pe commitment freeze changed nothing — the stored "
            "plan never reached simulate_play"
        )
        # and it is the whole decade, not one quarter: the two NAV series
        # diverge rather than touching at a single point.
        assert starved["series"]["active"] != pytest.approx(held["series"]["active"])

    def test_a_plan_carrying_decade_differs_from_the_no_plan_decade(self, service):
        """Spec section 4.3's behavioural change, stated as an outcome: the
        default plan is the FIXED rule, while a session with no plan paces
        with the POLICY flex. Same derived book, same holds — so if the two
        decades match, the plan was never applied."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()

        plan_sid = _play_through(client, rid, {}, book=default["book"], plan=default["plan"])
        plain_sid = _play_through(client, rid, {})

        planned = client.get(f"/sessions/{plan_sid}/outcome").json()
        paced = client.get(f"/sessions/{plain_sid}/outcome").json()
        assert planned["final_value"] != pytest.approx(paced["final_value"])

    def test_only_the_untouched_sleeves_are_filled_from_the_plan(self, service):
        """The client sends ONLY the sleeves the player edited (audit F4).
        The server fills the rest from the plan — not from the pacing rule,
        and not over the top of what the player typed."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        plan = _replanned(default["plan"], "pc", 1.0)
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": default["book"], "plan": plan}
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": 11, "action": "hold", "commitments": {"pe": 2.0}},
        )
        assert r.status_code == 200, r.text
        recorded = r.json()["decisions"]["11"]["commitments"]
        assert recorded["pe"] == pytest.approx(2.0), "the player's own number must survive"
        assert recorded["pc"] == pytest.approx(1.0), "an untouched sleeve is the plan's number"
        assert recorded["re"] == pytest.approx(plan["points"]["re"][0])

    def test_a_session_with_no_plan_records_the_bare_action_it_always_did(self, service):
        """The Task 6 scope fence, mechanically. Nothing is filled in for a
        session with no stored plan, so the decision is recorded as the plain
        string it has always been — not a structured commit."""
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        doc = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"}).json()
        assert doc["decisions"]["11"] == "hold"
        assert doc["window_log"][-1]["commitments"] is None


class TestTheTwoCapsAgree:
    """I1 — ``validate_plan`` caps a plan entry against the ENTERED book;
    ``validate_commitments`` at the decision door capped against
    ``START_TARGETS``. With C1 in place the server would fill in a number it
    then refuses itself.

    su-app-07 moved the basis both of them read from the book's opening NAV
    to the book's POLICY targets, so the book below now declares the
    allocation it holds instead of leaving the world default in place. The
    property under test is unchanged: the cap comes from the book the
    analyst entered, never from ``START_TARGETS``."""

    def test_a_plan_legal_under_the_entered_book_plays_through_its_window(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = dict(default["book"])
        book["liquid"] = dict(default["book"]["liquid"])
        book["private"] = {k: [dict(r) for r in v] for k, v in default["book"]["private"].items()}
        # move 10 points from equity into the pe ladder's first rung, in BOTH
        # the values and the policy targets: this institution is at its
        # target weights and holds 30 points of pe, so the plan cap is
        # 2 x 30 x 0.18 = 10.8 rather than START_TARGETS' 7.2.
        book["liquid"]["equity"] -= 10.0
        book["targets"] = {**default["book"]["targets"], "equity": 23.0, "pe": 30.0}
        rung = dict(book["private"]["pe"][0])
        rung["value"] = {**rung["value"], "nav_true": rung["value"]["nav_true"] + 10.0}
        book["private"]["pe"][0] = rung

        plan = _replanned(default["plan"], "pe", 9.0)  # legal at a 30 target, illegal at 20
        created = client.post("/sessions", json={"run_id": rid, "book": book, "plan": plan})
        assert created.status_code == 201, created.text
        sid = created.json()["session_id"]

        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        r = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"})
        assert r.status_code == 200, r.text
        assert r.json()["decisions"]["11"]["commitments"]["pe"] == pytest.approx(9.0)

    def test_a_policy_target_carries_the_cap_through_all_three_enforcement_points(self, service):
        """su-app-07 task 2. The book HOLDS 20 points of pe (old cap 7.20) and
        DECLARES a 30-point pe target (new cap 10.80). One number, 9.0, sits
        between them, so each of the three gates has to be reading the target:

        * ``validate_plan`` at ``POST /sessions`` — a 201, not a 422;
        * the decision door at ``POST /sessions/{sid}/decisions`` — the server
          fills 9.0 in from the stored plan and must not then refuse it;
        * ``simulate_play``'s own ``_validate_commit_decisions`` — that same
          request marks the session to market, so a 200 here is the simulator
          accepting the commitment, not merely the door doing so.
        """
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _retargeted_book(default["book"], equity=23.0, pe=30.0)
        plan = _replanned(default["plan"], "pe", 9.0)

        created = client.post("/sessions", json={"run_id": rid, "book": book, "plan": plan})
        assert created.status_code == 201, created.text
        sid = created.json()["session_id"]

        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        r = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"})
        assert r.status_code == 200, r.text
        assert r.json()["decisions"]["11"]["commitments"]["pe"] == pytest.approx(9.0)

        # and the commitment quarter actually closes rather than 500ing.
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 23}).status_code == 200
        doc = client.get(f"/sessions/{sid}")
        assert doc.status_code == 200, doc.text
        assert doc.json()["value"] is not None

    def test_a_plan_over_the_policy_target_is_refused_at_the_kickoff_door(self, service):
        """The bound is re-based, not removed: 11.0 is over the 10.80 the
        30-point pe target allows."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _retargeted_book(default["book"], equity=23.0, pe=30.0)
        r = client.post(
            "/sessions",
            json={"run_id": rid, "book": book, "plan": _replanned(default["plan"], "pe", 11.0)},
        )
        assert r.status_code == 422
        assert "declared bound" in r.json()["detail"]

    def test_a_commit_over_the_policy_target_is_422_at_the_decision_door(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _retargeted_book(default["book"], equity=23.0, pe=30.0)
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": book, "plan": default["plan"]}
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": 11, "action": "hold", "commitments": {"pe": 11.0}},
        )
        assert r.status_code == 422, r.text
        assert "declared bound" in r.json()["detail"]

    def test_the_door_still_refuses_a_number_over_the_entered_books_own_cap(self, service):
        """Reconciling the caps must not remove the bound — only re-base it."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": default["book"], "plan": default["plan"]}
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": 11, "action": "hold", "commitments": {"pe": 999.0}},
        )
        assert r.status_code == 422
        assert "declared bound" in r.json()["detail"]


class TestBandReport:
    """su-app-07 task 3: per-sleeve band status on the session document.

    A READ layer. Every band here is placed relative to a weight the server
    itself served back under a band no weight can leave (``_WIDE``), so the
    thing under test is the CLASSIFICATION of a known weight, not the weight
    — and every state asserted is one a player can actually be in: a real
    band around a real policy target, with the institution drifting inside
    it, at its edge, or out of it.
    """

    #: Real decisions, so the decade is not the degenerate hold-course twin.
    _ACTIONS: ClassVar[dict[int, str]] = {11: "derisk", 23: "leanin"}

    def test_the_key_is_present_and_null_for_a_session_with_no_book(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert "band_report" in doc, "the key is always on the document, never conditional"
        assert doc["band_report"] is None

    def test_the_key_is_null_for_a_book_that_declares_no_ranges(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": default["book"], "plan": default["plan"]}
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["band_report"] is None

    def test_the_key_is_present_and_null_before_the_first_quarter_closes(self, service):
        """The nulled-key list runs BEFORE the early return, so a banded
        session serves the key from month 0 rather than growing it at 3."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = _banded_book(default["book"], {"equity": _WIDE})
        sid = client.post(
            "/sessions", json={"run_id": rid, "book": book, "plan": default["plan"]}
        ).json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 2}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert "band_report" in doc
        assert doc["band_report"] is None

    def test_a_sleeve_with_no_range_is_absent_from_the_report_entirely(self, service):
        """Absent, not present-with-nulls: the app never has to tell "no band
        declared" from "band declared and unmet"."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        doc = _banded_session(client, rid, default, {"equity": _WIDE, "pe": _WIDE})
        assert [s["sleeve"] for s in doc["band_report"]["sleeves"]] == ["equity", "pe"]

    def test_the_sleeves_are_listed_in_the_worlds_own_order(self, service):
        """Liquid in the engine's ``asset_order``, then pe/pc/re — regardless
        of the order the analyst happened to type the ranges in."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        scrambled = {s: _WIDE for s in reversed(_all_sleeves(default))}
        doc = _banded_session(client, rid, default, scrambled)
        assert [s["sleeve"] for s in doc["band_report"]["sleeves"]] == [
            "equity",
            "bonds",
            "hy",
            "commodities",
            "reits",
            "pe",
            "pc",
            "re",
        ]

    def test_a_sleeve_comfortably_inside_its_band_reports_ok(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        probe = _banded_session(client, rid, default, {"equity": _WIDE})
        w = _weights(probe, "true")["equity"]
        target = default["book"]["targets"]["equity"]
        # twenty points of room on the near edge: the weight is nowhere close
        lo = max(0.0, min(w, target) - 20.0)
        hi = min(100.0, max(w, target) + 20.0)

        doc = _banded_session(client, rid, default, {"equity": (lo, hi)})
        entry = _entry(doc, "equity")
        assert entry["true"]["weight"] == pytest.approx(w)
        assert entry["true"]["alert"] == "ok"

    def test_a_sleeve_outside_its_band_reports_breach(self, service):
        """A band that CONTAINS the declared policy target and excludes the
        realized weight — the breach an allocator would actually report, not
        a band nobody would enter."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        probe = _banded_session(client, rid, default, {"equity": _WIDE})
        w = _weights(probe, "true")["equity"]
        target = default["book"]["targets"]["equity"]
        assert w != pytest.approx(target), "the drifted weight must differ from the target"
        edge = (w + target) / 2.0
        lo, hi = (edge, target + 5.0) if w < target else (target - 5.0, edge)
        assert lo <= target <= hi, "the target itself stays inside its own band"
        assert not lo <= w <= hi

        doc = _banded_session(client, rid, default, {"equity": (lo, hi)})
        assert _entry(doc, "equity")["true"]["alert"] == "breach"

    def test_a_sleeve_within_the_alert_threshold_of_an_edge_reports_watch(self, service):
        """Amber: inside the band, but 90% of the way out to the near edge —
        past ``WATCH_FRACTION`` (0.75) and short of the edge itself. Widening
        that same band puts the identical weight back at ``ok``, so the
        threshold is the thing doing the work."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        probe = _banded_session(client, rid, default, {"equity": _WIDE})
        w = _weights(probe, "true")["equity"]
        target = default["book"]["targets"]["equity"]
        assert w != pytest.approx(target)
        room = abs(w - target) / 0.9  # the weight sits 0.9 of the way out
        # `validate_book` refuses lo < 0, so an unclamped near edge would turn
        # a drift this test does not control into a 422 at the door instead of
        # a clean failure on the level it is actually about. Clamped — but the
        # clamp is NOT silent: flooring the near edge would enlarge `room` and
        # quietly turn the expected `watch` into an `ok`, so the pre-clamp
        # value is asserted non-negative and this test fails on its own
        # subject if a future tape ever pushes it under.
        if w < target:
            assert target - room >= 0.0, (
                f"equity drifted far enough ({w:g} vs target {target:g}) that the "
                "watch edge falls below zero; this test needs room beneath the "
                "target, not a clamp that would silently relabel watch as ok"
            )
        lo, hi = (
            (max(0.0, target - room), target + 5.0)
            if w < target
            else (max(0.0, target - 5.0), target + room)
        )
        assert lo <= w <= hi

        doc = _banded_session(client, rid, default, {"equity": (lo, hi)})
        assert doc["band_report"]["watch_fraction"] == WATCH_FRACTION
        assert _entry(doc, "equity")["true"]["alert"] == "watch"

        # the same weight, twice the room: 0.45 of the way out is `ok`.
        wide = (
            (max(0.0, target - 2.0 * room), target + 5.0)
            if w < target
            else (max(0.0, target - 5.0), target + 2.0 * room)
        )
        relaxed = _banded_session(client, rid, default, {"equity": wide})
        assert _entry(relaxed, "equity")["true"]["weight"] == pytest.approx(w)
        assert _entry(relaxed, "equity")["true"]["alert"] == "ok"

    def test_both_planes_are_reported_and_a_private_sleeve_can_disagree(self, service):
        """Appraisal smoothing is the whole reason both planes are served: a
        private sleeve can be outside its band on the engine's true state and
        inside it on the marks the committee actually sees."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        probe = _banded_session(client, rid, default, {"pe": _WIDE})
        w_true = _weights(probe, "true")["pe"]
        w_rep = _weights(probe, "reported")["pe"]
        assert w_true != pytest.approx(w_rep)

        edge = (w_true + w_rep) / 2.0
        band = (edge, 100.0) if w_true < w_rep else (0.0, edge)
        doc = _banded_session(client, rid, default, {"pe": band})
        entry = _entry(doc, "pe")
        assert entry["true"]["alert"] == "breach"
        assert entry["reported"]["alert"] != "breach"
        assert entry["true"]["weight"] != pytest.approx(entry["reported"]["weight"])

    # the session's `basis` enum is "reported" | "actual"; "actual" is the
    # engine's TRUE plane, which is the name the band report serves it under.
    @pytest.mark.parametrize(("basis", "plane"), [("reported", "reported"), ("actual", "true")])
    def test_the_served_weights_and_cash_close_on_one_hundred(self, service, basis, plane):
        """The units answer, at the served layer: weights are points out of
        100 against THAT PLANE'S NAV, so every sleeve plus the cash account
        accounts for the whole book. (``tests/test_cioview.py::
        test_per_asset_values_close_against_the_book`` pins the same identity
        one layer down, to 1e-9, on both planes.)"""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        doc = _banded_session(
            client, rid, default, {s: _WIDE for s in _all_sleeves(default)}, basis=basis
        )
        served = sum(_weights(doc, plane).values())
        # `doc["value"]` is the NAV on the session's own basis — the same
        # denominator the report divided by.
        cash_pct = doc["cash"] / doc["value"] * 100.0
        assert served + cash_pct == pytest.approx(100.0, abs=1e-3)

    def test_ranges_do_not_move_a_single_number(self, service):
        """THE load-bearing test of this task. The same book, the same plan
        and the same decisions, played twice — differing only in whether the
        book declares reporting ranges. If a range can reach ``simulate_play``
        at all, the two decades separate here.

        The bands are ``_TIGHT``: two points wide and deliberately placed off
        the sleeve's own policy target. A wide band would not do — a leak that
        surfaced as a rebalance or clamp bound would be a no-op under
        ``[0, 100]`` and this test would have certified the defect. Under
        ``_TIGHT`` every sleeve's target sits OUTSIDE its band, so any bound
        derived from a range has to move a weight in quarter 1."""
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        assert set(_TIGHT) == set(_all_sleeves(default)), (
            "_TIGHT must cover every sleeve of this world, or the uncovered "
            "ones are not testing anything"
        )
        for sleeve, (lo, hi) in _TIGHT.items():
            target = default["book"]["targets"][sleeve]
            assert not lo <= target <= hi, (
                f"{sleeve}'s band [{lo}, {hi}] contains its target {target} — a "
                "leaked bound would be satisfied already and the test would not bite"
            )
        banded = _banded_book(default["book"], _TIGHT)
        assert banded["ranges"], "the banded book really does declare ranges"

        plain_sid = _play_through(
            client, rid, self._ACTIONS, book=default["book"], plan=default["plan"]
        )
        banded_sid = _play_through(client, rid, self._ACTIONS, book=banded, plan=default["plan"])

        plain = client.get(f"/sessions/{plain_sid}/outcome").json()
        with_bands = client.get(f"/sessions/{banded_sid}/outcome").json()
        assert plain.pop("session_id") != with_bands.pop("session_id")

        # the decade first, named explicitly, then the whole verdict
        assert with_bands["series"] == plain["series"]
        assert with_bands["window_contributions"] == plain["window_contributions"]
        assert with_bands == plain
