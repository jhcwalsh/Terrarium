"""su-eng-02 acceptance, HTTP layer: the session service end to end.

Socket opt-in, stated: TestClient drives the ASGI app IN-PROCESS — no bytes
leave the interpreter — but asyncio's Windows event loop needs an internal
``socket.socketpair`` as its wakeup pipe, which pytest-socket blocks by
default. ``enable_socket`` is the invariant's sanctioned loopback opt-in
(pyproject: "tests that need a loopback socket can opt in explicitly");
the no-NETWORK rule stands untouched.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from ah.cli import app as cli_app
from ah.core.engine import run_path
from ah.core.institution import decision_months, simulate_institution
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.serve import create_app
from ah.store.db import connect
from ah.store.runrecords import get_run_record
from ah.store.worlds import get_world

RUNNER = CliRunner()

pytestmark = pytest.mark.enable_socket


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("serve")
    db = tmp / "ah.db"
    assert (
        RUNNER.invoke(
            cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation"]
        ).exit_code
        == 0
    )
    run = RUNNER.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
    assert run.exit_code == 0
    client = TestClient(create_app(db))
    return client, db, run.stdout.strip()


def _play_through(client, rid: str, actions: dict[int, str], **create_kwargs):
    r = client.post("/sessions", json={"run_id": rid, **create_kwargs})
    assert r.status_code == 201, r.text
    sid = r.json()["session_id"]
    months = r.json()["months"]
    for m in decision_months(months):
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1}).status_code == 200
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={
                "month": m,
                "action": actions.get(m, "hold"),
                "client_log": {"time_on_window_ms": 1000},
            },
        )
        assert r.status_code == 200, r.text
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": months}).status_code == 200
    assert client.post(f"/sessions/{sid}/complete").status_code == 200
    return sid


class TestEndpoints:
    def test_create_and_get(self, service):
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 201
        doc = r.json()
        got = client.get(f"/sessions/{doc['session_id']}").json()
        assert got["status"] == "active"
        assert got["decision_windows"] == decision_months(got["months"])

    def test_unknown_run_404(self, service):
        client, _db, _rid = service
        assert client.post("/sessions", json={"run_id": "nope"}).status_code == 404

    def test_unknown_session_404(self, service):
        client, _db, _rid = service
        assert client.get("/sessions/nope").status_code == 404

    def test_invariant_violations_are_409(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(120)[0]
        # deciding an unrevealed window
        r = client.post(f"/sessions/{sid}/decisions", json={"month": first, "action": "hold"})
        assert r.status_code == 409
        # revealing past an undecided window
        r = client.post(f"/sessions/{sid}/advance", json={"to_month": first + 2})
        assert r.status_code == 409
        # outcome before completion
        assert client.get(f"/sessions/{sid}/outcome").status_code == 409


class TestOutcome:
    def test_outcome_matches_institution_sim_exactly(self, service):
        client, db, rid = service
        actions = {11: "derisk", 35: "leanin"}
        sid = _play_through(client, rid, actions)
        out = client.get(f"/sessions/{sid}/outcome").json()

        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        world = get_world(conn, rec["world_id"])
        assert world is not None
        nw = project_numeric(WorldSpec.model_validate(world))
        paths = run_path(nw, rec["seed"])
        decisions = {m: actions.get(m, "hold") for m in decision_months(paths.months)}
        active = simulate_institution(paths, decisions, use_reported=True)
        twin = simulate_institution(paths, None, use_reported=True)

        assert out["final_value"] == pytest.approx(active.final_value)
        assert out["twin_final_value"] == pytest.approx(twin.final_value)
        assert out["alpha"] == pytest.approx(active.final_value - twin.final_value)
        # DN-5 chain-link: the windows telescope exactly to the terminal alpha
        assert sum(w["contribution"] for w in out["windows"]) == pytest.approx(out["alpha"])
        assert [w["action"] for w in out["windows"]][:1] == ["derisk"]

    def test_ranked_completion_writes_the_board_once(self, service):
        client, db, rid = service
        sid = _play_through(client, rid, {11: "leanin"}, ranked=True, participant="james")
        out1 = client.get(f"/sessions/{sid}/outcome").json()
        out2 = client.get(f"/sessions/{sid}/outcome").json()  # re-read, no dup
        assert out1["alpha"] == out2["alpha"]
        conn = connect(db)
        rows = conn.execute(
            "SELECT participant, score, decision_alpha_version FROM leaderboard"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["participant"] == "james"
        assert rows[0]["score"] == pytest.approx(out1["alpha"])

    def test_practice_never_touches_the_board(self, service):
        client, db, rid = service
        before = connect(db).execute("SELECT COUNT(*) c FROM leaderboard").fetchone()["c"]
        sid = _play_through(client, rid, {})
        client.get(f"/sessions/{sid}/outcome")
        after = connect(db).execute("SELECT COUNT(*) c FROM leaderboard").fetchone()["c"]
        assert after == before
