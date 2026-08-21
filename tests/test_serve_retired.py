"""app-open-04 Item D — the pe-chosen release's named I-1 follow-up.

The retired-world fence was picker-deep: ``/worlds`` marks retired worlds and
the app hides them, but ``POST /sessions`` still accepted a retired world's
run if a client asked directly (a stale browser cache does exactly that —
see Item A of the same work package). CREATION is now fenced with a 422 and
a plain message; history is history — existing sessions on retired worlds
stay fully readable (GET / advance / cio untouched).

The fence is exercised by monkeypatching ``ah.serve.RETIRED_WORLD_IDS`` to
contain the test world's own id: the real frozenset names only shipped
world ids (701/703/711/712/713/604/80x), none of which the toy test store
can rebuild — ``ah.cli`` itself refuses to rebuild retired worlds, which is
the other half of the same platform fence. Patching the module global the
endpoint reads at call time proves the mechanism (the fence is consulted at
the door) without duplicating the fence's contents into a fixture.

Socket opt-in, same reason as ``tests/test_serve.py``: TestClient drives the
ASGI app in-process; asyncio's Windows loop needs an internal socketpair.
"""

from __future__ import annotations

import pytest

from ah.store.db import connect
from ah.store.runrecords import get_run_record

# reuse the established app/client fixture — see tests/test_serve.py. Import
# ONLY the fixture name (plus the plain `_hold_through` helper), never the
# Test* classes.
from test_serve import _hold_through, service  # noqa: F401

pytestmark = pytest.mark.enable_socket


def _world_of(db, rid: str) -> str:
    conn = connect(db)
    try:
        rec = get_run_record(conn, rid)
        assert rec is not None
        return rec["world_id"]
    finally:
        conn.close()


class TestRetiredWorldSessionFence:
    def test_a_new_session_on_a_retired_world_is_422_with_a_plain_message(
        self, service, monkeypatch
    ):
        client, db, rid = service
        monkeypatch.setattr("ah.serve.RETIRED_WORLD_IDS", frozenset({_world_of(db, rid)}))
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 422, r.text
        assert r.json()["detail"] == (
            "this world is retired - its successor appears in the world list"
        )

    def test_an_entered_book_does_not_bypass_the_fence(self, service, monkeypatch):
        # the fence must sit before book validation, not inside the
        # book-carrying branch — a bare POST and a book-carrying POST are
        # refused alike.
        client, db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        monkeypatch.setattr("ah.serve.RETIRED_WORLD_IDS", frozenset({_world_of(db, rid)}))
        r = client.post(
            "/sessions",
            json={"run_id": rid, "book": default["book"], "plan": default["plan"]},
        )
        assert r.status_code == 422, r.text
        assert "retired" in r.json()["detail"]

    def test_an_unknown_run_is_still_404_not_422(self, service, monkeypatch):
        # the fence reads the run's world, so a missing run keeps its own,
        # more informative refusal.
        client, db, rid = service
        monkeypatch.setattr("ah.serve.RETIRED_WORLD_IDS", frozenset({_world_of(db, rid)}))
        assert client.post("/sessions", json={"run_id": "nope"}).status_code == 404

    def test_existing_sessions_on_a_retired_world_stay_fully_readable(self, service, monkeypatch):
        """History is history: only CREATION is fenced. A session opened
        before the world retired must keep working — GET, advance, cio."""
        client, db, rid = service
        created = client.post("/sessions", json={"run_id": rid})
        assert created.status_code == 201, created.text
        sid = created.json()["session_id"]

        monkeypatch.setattr("ah.serve.RETIRED_WORLD_IDS", frozenset({_world_of(db, rid)}))

        assert client.get(f"/sessions/{sid}").status_code == 200
        # D-QC-1 (found by the S7 full-suite run, outside the plan's named
        # S7 file list): reach month 6 by holding the quarterly windows
        # ahead of it (2, 5) first.
        _hold_through(client, sid, 6)
        assert client.get(f"/sessions/{sid}/cio").status_code == 200

    def test_the_fence_is_the_platform_list_not_a_local_copy(self):
        # the endpoint must consult ah.retired_worlds' single fence — the
        # same import the CLI and /worlds read — not a serve-local list that
        # could drift from it.
        import ah.retired_worlds
        import ah.serve

        assert ah.serve.RETIRED_WORLD_IDS is ah.retired_worlds.RETIRED_WORLD_IDS
