"""D-QC-1 acceptance criteria 4 and 5: stamps govern, boards never mix.

A LEGACY session here is a store-layer row created WITHOUT the two new
columns -- byte-for-byte what every pre-release session looks like. That
shape is first-class forever: it resolves to the annual grid and to the
frozen legacy alpha stamps, and its scores land on the annual board even
when completed AFTER the quarterly release.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from ah.cli import app as cli_app
from ah.core.institution import decision_months
from ah.play import PLAY_ALPHA_VERSION
from ah.port.adapter import GEN_PLAY_ALPHA_VERSION
from ah.serve import _LEGACY_PLAY_ALPHA, create_app
from ah.store import leaderboard
from ah.store import sessions as session_store
from ah.store.db import connect

RUNNER = CliRunner()
pytestmark = pytest.mark.enable_socket


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("qc-versions")
    db = tmp / "ah.db"
    assert (
        RUNNER.invoke(
            cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation"]
        ).exit_code
        == 0
    )
    run = RUNNER.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
    assert run.exit_code == 0
    return TestClient(create_app(db)), db, run.stdout.strip()


def _finish(client, sid: str) -> dict:
    """Hold every window the session itself declares, reveal the horizon,
    complete, return the outcome."""
    doc = client.get(f"/sessions/{sid}").json()
    for m in doc["decision_windows"]:
        assert (
            client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1}).status_code == 200
        )
        assert (
            client.post(
                f"/sessions/{sid}/decisions", json={"month": m, "action": "hold"}
            ).status_code
            == 200
        )
    assert (
        client.post(f"/sessions/{sid}/advance", json={"to_month": doc["months"]}).status_code
        == 200
    )
    assert client.post(f"/sessions/{sid}/complete").status_code == 200
    r = client.get(f"/sessions/{sid}/outcome")
    assert r.status_code == 200, r.text
    return r.json()


def _legacy_ranked_session(db, rid: str, participant: str) -> str:
    """A pre-release row: no decision_windows, no play_alpha_version."""
    conn = connect(db)
    try:
        doc = session_store.create_session(
            conn, run_id=rid, months=120, ranked=True, participant=participant
        )
        return doc["session_id"]
    finally:
        conn.close()


class TestVersionSeparation:
    def test_new_sessions_stamp_the_quarterly_version(self, service):
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 201, r.text
        assert r.json()["play_alpha_version"] == "port-v7-quarterly"

    def test_legacy_session_replays_and_scores_under_its_own_version(self, service):
        client, db, rid = service
        sid = _legacy_ranked_session(db, rid, "legacy-ann")
        doc = client.get(f"/sessions/{sid}").json()
        # the NULL-stamped row resolves to the annual grid...
        assert doc["decision_windows"] == decision_months(120)
        outcome = _finish(client, sid)
        # ...and scores under the frozen legacy stamp, not the live one
        assert outcome["decision_alpha_version"] == "port-v5-inflation"
        assert outcome["decision_alpha_version"] != PLAY_ALPHA_VERSION
        # nine windows in the review, not thirty-nine
        assert len(outcome["windows"]) == 9

    def test_quarterly_and_legacy_rows_never_share_a_board(self, service):
        client, db, rid = service
        conn = connect(db)
        try:
            rec = conn.execute(
                "SELECT world_id, seed FROM run_records WHERE run_id = ?", (rid,)
            ).fetchone()
            wid, seed = rec["world_id"], rec["seed"]
        finally:
            conn.close()
        # one legacy ranked session (store-layer row) ...
        legacy_sid = _legacy_ranked_session(db, rid, "board-legacy")
        _finish(client, legacy_sid)
        # ... and one quarterly ranked session on the SAME (world, seed)
        r = client.post(
            "/sessions",
            json={"run_id": rid, "ranked": True, "participant": "board-q"},
        )
        assert r.status_code == 201
        _finish(client, r.json()["session_id"])

        def board(version: str) -> list[str]:
            r = client.get(
                f"/leaderboard/{wid}", params={"seed": seed, "alpha_version": version}
            )
            assert r.status_code == 200
            return [row["participant"] for row in r.json()["rows"]]

        assert "board-legacy" in board("port-v5-inflation")
        assert "board-q" not in board("port-v5-inflation")
        assert "board-q" in board("port-v7-quarterly")
        assert "board-legacy" not in board("port-v7-quarterly")
        # the version key is REQUIRED: no query path can aggregate
        assert client.get(f"/leaderboard/{wid}", params={"seed": seed}).status_code == 422

    def test_no_ranking_surface_can_aggregate_across_versions(self, service):
        _client, db, rid = service
        conn = connect(db)
        try:
            rec = conn.execute(
                "SELECT world_id, seed FROM run_records WHERE run_id = ?", (rid,)
            ).fetchone()
            a = leaderboard.scores(
                conn,
                world_id=rec["world_id"],
                seed=rec["seed"],
                decision_alpha_version="port-v5-inflation",
            )
            b = leaderboard.scores(
                conn,
                world_id=rec["world_id"],
                seed=rec["seed"],
                decision_alpha_version="port-v7-quarterly",
            )
            assert not ({r["participant"] for r in a} & {r["participant"] for r in b})
            with pytest.raises(leaderboard.LeaderboardError, match="required"):
                leaderboard.submit_score(
                    conn,
                    world_id=rec["world_id"],
                    seed=rec["seed"],
                    decision_alpha_version="",
                    participant="x",
                    score=0.0,
                    created_at="2026-08-20T00:00:00+00:00",
                )
        finally:
            conn.close()

    def test_g5_research_definition_did_not_move(self):
        """decision_alpha_version names Step 5's SEALED research definition
        (pre-registration-g5.lock hashes decision_metrics.py); the quarterly
        clock moves the PRODUCT stamps only. If this fails, someone bumped
        the sealed constant -- that needs an amendment, not a fix to this
        test."""
        from ah.eval.decision_metrics import DECISION_ALPHA_VERSION

        assert DECISION_ALPHA_VERSION == "1.0"

    def test_frozen_legacy_literals_are_not_the_live_constants(self):
        """If this fails, someone 'simplified' the legacy fallback to the
        live constants and re-created the exact mixing defect the stamp
        column exists to prevent: a pre-release session completing after a
        future bump would score under the wrong definition."""
        assert _LEGACY_PLAY_ALPHA["toy"] == "port-v5-inflation"
        assert _LEGACY_PLAY_ALPHA["gen"] == "port-v6-chosen-pe-gen"
        assert _LEGACY_PLAY_ALPHA["toy"] != PLAY_ALPHA_VERSION
        assert _LEGACY_PLAY_ALPHA["gen"] != GEN_PLAY_ALPHA_VERSION
