"""The book entry endpoints (su-app-06).

The server is the authority: it serves the default, validates what comes
back, and decides ranked eligibility. The app is not trusted to do any of it.

Socket opt-in, same reason as ``tests/test_serve.py``: FastAPI's TestClient
drives the ASGI app in-process (no bytes leave the interpreter) but asyncio's
Windows event loop needs an internal ``socket.socketpair`` as its wakeup
pipe, which pytest-socket blocks by default.
"""

from __future__ import annotations

import pytest

# reuse this module's established app/client fixtures — see tests/test_serve.py.
# Import ONLY the fixture names, never the Test* classes (that would collect
# their tests a second time).
from test_serve import gen_service, service  # noqa: F401  (pytest fixtures)

pytestmark = pytest.mark.enable_socket


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
