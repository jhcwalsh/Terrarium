"""su-eng-02 acceptance, store layer: the session invariants."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ah.cli import app
from ah.core.institution import decision_months
from ah.store import sessions as ss
from ah.store.db import connect

RUNNER = CliRunner()


@pytest.fixture(scope="module")
def stored_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sessions")
    db = tmp / "ah.db"
    assert (
        RUNNER.invoke(app, ["--db", str(db), "world", "build", "--preset", "stagflation"]).exit_code
        == 0
    )
    run = RUNNER.invoke(app, ["--db", str(db), "run", "--paths", "8"])
    assert run.exit_code == 0
    return db, run.stdout.strip()


@pytest.fixture()
def session(stored_run):
    db, rid = stored_run
    conn = connect(db)
    doc = ss.create_session(conn, run_id=rid, months=120)
    return conn, doc


class TestLifecycle:
    def test_create_defaults(self, session):
        _conn, doc = session
        assert doc["status"] == "active"
        assert doc["revealed_months"] == 0
        assert doc["basis"] == "reported"
        assert doc["ranked"] is False
        assert doc["decisions"] == {} and doc["window_log"] == []

    def test_unknown_run_refused(self, stored_run):
        db, _rid = stored_run
        with pytest.raises(ss.SessionError, match="no run_record"):
            ss.create_session(connect(db), run_id="nope", months=120)

    def test_bad_basis_refused(self, stored_run):
        db, rid = stored_run
        with pytest.raises(ss.SessionError, match="basis"):
            ss.create_session(connect(db), run_id=rid, months=120, basis="vibes")


class TestRevealInvariants:
    def test_pointer_never_rewinds(self, session):
        conn, doc = session
        sid = doc["session_id"]
        ss.advance_reveal(conn, sid, 6)
        with pytest.raises(ss.SessionError, match="never rewinds"):
            ss.advance_reveal(conn, sid, 3)

    def test_pointer_blocked_by_undecided_window(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first = decision_months(120)[0]  # month 11
        ss.advance_reveal(conn, sid, first + 1)  # the window itself is visible
        with pytest.raises(ss.SessionError, match="undecided"):
            ss.advance_reveal(conn, sid, first + 2)  # the future is not

    def test_decide_then_advance(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first, second = decision_months(120)[:2]
        ss.advance_reveal(conn, sid, first + 1)
        ss.record_decision(conn, sid, month=first, action="derisk")
        after = ss.advance_reveal(conn, sid, second + 1)
        assert after["revealed_months"] == second + 1


class TestDecisionInvariants:
    def _at_first_window(self, conn, sid):
        first = decision_months(120)[0]
        ss.advance_reveal(conn, sid, first + 1)
        return first

    def test_decisions_are_final(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        ss.record_decision(conn, sid, month=first, action="hold")
        with pytest.raises(ss.SessionError, match="already decided"):
            ss.record_decision(conn, sid, month=first, action="leanin")

    def test_windows_decided_in_order(self, session):
        conn, doc = session
        sid = doc["session_id"]
        self._at_first_window(conn, sid)
        second = decision_months(120)[1]
        with pytest.raises(ss.SessionError, match="in order"):
            ss.record_decision(conn, sid, month=second, action="hold")

    def test_unrevealed_window_refused(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first = decision_months(120)[0]
        with pytest.raises(ss.SessionError, match="not yet revealed"):
            ss.record_decision(conn, sid, month=first, action="hold")

    def test_unknown_action_refused(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        with pytest.raises(ss.SessionError, match="unknown action"):
            ss.record_decision(conn, sid, month=first, action="yolo")

    def test_dn6_log_row_recorded(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        after = ss.record_decision(
            conn,
            sid,
            month=first,
            action="secondary",
            client_log={"time_on_window_ms": 4200, "basis_toggles": 1},
        )
        (row,) = after["window_log"]
        assert row["month"] == first and row["action"] == "secondary"
        assert row["server_received_at"]  # server clock is the authoritative stamp
        assert row["basis"] == "reported" and row["ranked"] is False
        assert row["client"]["time_on_window_ms"] == 4200

    def test_complete_requires_full_play(self, session):
        conn, doc = session
        sid = doc["session_id"]
        with pytest.raises(ss.SessionError, match="undecided"):
            ss.complete_session(conn, sid)


def test_full_play_completes(stored_run):
    db, rid = stored_run
    conn = connect(db)
    doc = ss.create_session(conn, run_id=rid, months=120)
    sid = doc["session_id"]
    for m in decision_months(120):
        ss.advance_reveal(conn, sid, m + 1)
        ss.record_decision(conn, sid, month=m, action="hold")
    ss.advance_reveal(conn, sid, 120)
    done = ss.complete_session(conn, sid)
    assert done["status"] == "completed"
    with pytest.raises(ss.SessionError, match="not active"):
        ss.record_decision(conn, sid, month=11, action="hold")
