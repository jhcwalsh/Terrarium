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
