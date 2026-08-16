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


def _replanned(default_plan: dict, sleeve: str, value: float) -> dict:
    """The served default plan with one sleeve flattened to `value` everywhere."""
    plan = {**default_plan, "points": {k: list(v) for k, v in default_plan["points"].items()}}
    plan["points"][sleeve] = [value] * len(plan["points"][sleeve])
    return plan


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
        assert body["book"]["state_version"] == "opening-book-0.1"
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
    """I1 — ``validate_plan`` caps a plan entry against the ENTERED book's
    per-sleeve NAV (``_plan_targets``); ``validate_commitments`` at the
    decision door capped against ``START_TARGETS``. With C1 in place the
    server would fill in a number it then refuses itself."""

    def test_a_plan_legal_under_the_entered_book_plays_through_its_window(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        book = dict(default["book"])
        book["liquid"] = dict(default["book"]["liquid"])
        book["private"] = {k: [dict(r) for r in v] for k, v in default["book"]["private"].items()}
        # move 10 points of NAV from equity into the pe ladder's first rung:
        # the book still totals 100, and pe's target NAV is now ~30, so the
        # plan cap is 2 x 30 x 0.18 = 10.8 rather than START_TARGETS' 7.2.
        book["liquid"]["equity"] -= 10.0
        rung = dict(book["private"]["pe"][0])
        rung["value"] = {**rung["value"], "nav_true": rung["value"]["nav_true"] + 10.0}
        book["private"]["pe"][0] = rung

        plan = _replanned(default["plan"], "pe", 9.0)  # legal at 30 NAV, illegal at 20
        created = client.post("/sessions", json={"run_id": rid, "book": book, "plan": plan})
        assert created.status_code == 201, created.text
        sid = created.json()["session_id"]

        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        r = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"})
        assert r.status_code == 200, r.text
        assert r.json()["decisions"]["11"]["commitments"]["pe"] == pytest.approx(9.0)

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
