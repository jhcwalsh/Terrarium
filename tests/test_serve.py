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
from ah.core.institution import decision_months
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.serve import create_app
from ah.store import sessions as session_store
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


@pytest.fixture(scope="module")
def gen_service(tmp_path_factory):
    """A session service over the GENERATED 1974 world (su-gen-03), against
    the synthetic bootstrap source — no vintage store, no network."""
    import ah.gen.bootstrap as bs
    from ah.gen import registry
    from conftest import make_synthetic_source_16

    saved = registry.snapshot()
    registry.register("bootstrap-v1", lambda: bs.BootstrapV1(make_synthetic_source_16()))
    tmp = tmp_path_factory.mktemp("gen-serve")
    db = tmp / "ah.db"
    try:
        assert (
            RUNNER.invoke(
                cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation_1974"]
            ).exit_code
            == 0
        )
        run = RUNNER.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
        assert run.exit_code == 0
        client = TestClient(create_app(db))
        yield client, db, run.stdout.strip().splitlines()[-1]
    finally:
        registry.restore(saved)


class TestGeneratedSessions:
    """su-gen-03: the server is the authority for generated worlds too."""

    def test_generated_session_plays_end_to_end(self, gen_service):
        client, _db, rid = gen_service
        sid = _play_through(client, rid, {})
        outcome = client.get(f"/sessions/{sid}/outcome").json()
        assert outcome["alpha"] == pytest.approx(0.0, abs=1e-9)  # hold == twin
        assert outcome["final_value"] > 0

    def test_generated_outcome_carries_its_own_alpha_version(self, gen_service):
        """Scores from generated worlds must never share a leaderboard row
        with toy scores: a DISTINCT alpha version, not a bump (survey S3)."""
        from ah.port.adapter import GEN_PLAY_ALPHA_VERSION

        client, _db, rid = gen_service
        sid = _play_through(client, rid, {23: "derisk"})
        outcome = client.get(f"/sessions/{sid}/outcome").json()
        assert outcome["decision_alpha_version"] == GEN_PLAY_ALPHA_VERSION
        from ah.play import PLAY_ALPHA_VERSION

        assert outcome["decision_alpha_version"] != PLAY_ALPHA_VERSION

    def test_generated_book_marks_to_market(self, gen_service):
        client, _db, rid = gen_service
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 201, r.text
        sid = r.json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 11}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["value"] is not None and doc["value"] > 0
        assert doc["twin_value"] is not None


def test_request_survives_a_threadpool_thread_hop(service):
    """Regression (found live, not by tests): FastAPI's threadpool can open
    the per-request connection on one worker thread and run the endpoint on
    another; SQLite's default same-thread guard then 500s the first real
    browser request while sequential tests pass. Force the hop explicitly."""
    from concurrent.futures import ThreadPoolExecutor

    _client, db, rid = service
    conn = connect(db, check_same_thread=False)
    with ThreadPoolExecutor(max_workers=1) as pool:
        row = pool.submit(
            lambda: conn.execute(
                "SELECT run_id FROM run_records WHERE run_id = ?", (rid,)
            ).fetchone()
        ).result()
    assert row["run_id"] == rid


class TestEndpoints:
    def test_create_and_get(self, service):
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 201
        doc = r.json()
        got = client.get(f"/sessions/{doc['session_id']}").json()
        assert got["status"] == "active"
        assert got["decision_windows"] == decision_months(got["months"])

    def test_book_is_marked_to_market_on_the_real_twin(self, service):
        """The rail's headline number, now with a cash account behind it."""
        from ah.core.engine import run_path
        from ah.core.numericworld import project_numeric
        from ah.core.worldspec import WorldSpec
        from ah.play import simulate_play
        from ah.store.db import connect
        from ah.store.runrecords import get_run_record
        from ah.store.worlds import get_world

        client, db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.get(f"/sessions/{sid}").json()["value"] is None

        doc = client.post(f"/sessions/{sid}/advance", json={"to_month": 6}).json()
        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        world = get_world(conn, rec["world_id"])
        assert world is not None
        paths = run_path(project_numeric(WorldSpec.model_validate(world)), rec["seed"])
        twin = simulate_play(paths, None, use_reported=True)
        # month 6 revealed -> quarter index 1 closed (months 3,4,5)
        assert doc["value"] == pytest.approx(twin.quarters[1].nav_reported)
        assert doc["cash"] == pytest.approx(twin.quarters[1].cash)
        assert doc["calls_paid"] >= 0.0
        assert 0.0 <= doc["private_weight_true"] <= 1.0

    def test_session_carries_the_product_alpha_version(self, service):
        from ah.play import PLAY_ALPHA_VERSION

        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        for month in decision_months(120):
            client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1})
            client.post(f"/sessions/{sid}/decisions", json={"month": month, "action": "hold"})
        client.post(f"/sessions/{sid}/advance", json={"to_month": 120})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert out["decision_alpha_version"] == PLAY_ALPHA_VERSION
        assert out["alpha"] == pytest.approx(0.0, abs=1e-9)

    def test_attribution_sums_to_the_alpha_reported(self, service):
        """The reckoning must add up on the surface, not just in the library."""
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        windows = decision_months(120)
        for i, month in enumerate(windows):
            client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1})
            action = "derisk" if i == 0 else "hold"
            client.post(f"/sessions/{sid}/decisions", json={"month": month, "action": action})
        client.post(f"/sessions/{sid}/advance", json={"to_month": 120})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert sum(out["window_contributions"]) == pytest.approx(out["alpha"], abs=1e-9)

    def test_a_decision_moves_the_book_away_from_the_twin(self, service):
        """Hold-course and the twin agree by construction; acting must not."""
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(120)[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        doc = client.post(
            f"/sessions/{sid}/decisions", json={"month": first, "action": "derisk"}
        ).json()
        # at the window itself the rebalance has just happened
        after = client.post(f"/sessions/{sid}/advance", json={"to_month": first + 7}).json()
        assert after["value"] != pytest.approx(after["twin_value"])
        assert doc["value"] is not None

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
    def test_outcome_matches_the_twin_exactly(self, service):
        """Same claim as before (WP2's toy-engine version), on the real twin:
        the session's outcome must equal ``ah.play.simulate_play`` run
        independently over the same tape and decisions."""
        from ah.play import simulate_play

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
        active = simulate_play(paths, decisions, use_reported=True)
        twin = simulate_play(paths, None, use_reported=True)

        assert out["final_value"] == pytest.approx(active.final_value)
        assert out["twin_final_value"] == pytest.approx(twin.final_value)
        assert out["alpha"] == pytest.approx(active.final_value - twin.final_value)
        # DN-5 chain-link: the windows telescope exactly to the terminal alpha
        assert sum(w["contribution"] for w in out["windows"]) == pytest.approx(out["alpha"])
        assert [w["action"] for w in out["windows"]][:1] == ["derisk"]

    def test_outcome_series_carry_three_slots(self, service):
        """E7 (DN-5 R-1): active + twin value series, one point per CLOSED
        quarter (the twin's own cadence), with the drift twin's slot
        EXPLICITLY null until its engine work lands — the arrival must be a
        deliberate data change, not an interface change."""
        client, _db, rid = service
        sid = _play_through(client, rid, {11: "derisk"})
        out = client.get(f"/sessions/{sid}/outcome").json()
        series = out["series"]
        months = client.get(f"/sessions/{sid}").json()["months"]
        assert len(series["active"]) == months // 3
        assert len(series["twin"]) == months // 3
        assert series["active"][-1] == pytest.approx(out["final_value"], abs=1e-3)
        assert series["twin"][-1] == pytest.approx(out["twin_final_value"], abs=1e-3)
        assert series["drift_twin"] is None

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

    def test_leaderboard_reads_under_the_triple_key(self, service):
        """DN-5 R-1 read-side: the board query REQUIRES world+seed+alpha —
        and a different alpha version is a different (empty) board."""
        client, db, rid = service
        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        sid = _play_through(client, rid, {11: "derisk"}, ranked=True, participant="ada")
        out = client.get(f"/sessions/{sid}/outcome").json()
        board = client.get(
            f"/leaderboard/{rec['world_id']}",
            params={"seed": rec["seed"], "alpha_version": out["decision_alpha_version"]},
        ).json()
        assert any(r["participant"] == "ada" for r in board["rows"])
        scores = [r["score"] for r in board["rows"]]
        assert scores == sorted(scores, reverse=True)
        other = client.get(
            f"/leaderboard/{rec['world_id']}",
            params={"seed": rec["seed"], "alpha_version": "some-other-alpha"},
        ).json()
        assert other["rows"] == []  # boards never mix scoring versions
        missing_key = client.get(f"/leaderboard/{rec['world_id']}")
        assert missing_key.status_code == 422  # the triple key is not optional

    def test_dn6_s8_log_is_complete_on_a_ranked_run(self, service):
        """The register's requirement: full research logging from the FIRST
        ranked run. Every window row must carry the arm assignment (basis,
        ranked), the authoritative server timestamp, and the client telemetry
        fields — the analysis dataset is not recoverable retroactively."""
        client, db, rid = service
        sid = _play_through(client, rid, {}, ranked=True, participant="grace")
        conn = connect(db)
        doc = session_store.get_session(conn, sid)
        assert len(doc["window_log"]) == len(decision_months(doc["months"]))
        for row in doc["window_log"]:
            assert set(row) >= {"month", "action", "server_received_at", "basis", "ranked"}
            assert row["ranked"] is True and row["basis"] == "reported"
            assert row["server_received_at"]
            assert "time_on_window_ms" in row["client"]

    def test_practice_never_touches_the_board(self, service):
        client, db, rid = service
        before = connect(db).execute("SELECT COUNT(*) c FROM leaderboard").fetchone()["c"]
        sid = _play_through(client, rid, {})
        client.get(f"/sessions/{sid}/outcome")
        after = connect(db).execute("SELECT COUNT(*) c FROM leaderboard").fetchone()["c"]
        assert after == before
