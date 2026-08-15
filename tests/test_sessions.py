"""su-eng-02 acceptance, store layer: the session invariants."""

from __future__ import annotations

import sqlite3

import pytest
from typer.testing import CliRunner

from ah.cli import app
from ah.core.institution import decision_months
from ah.store import sessions as ss
from ah.store.db import connect, migrate

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


class TestRationale:
    """narr-02 (DN-9 N-af): the optional per-window rationale, mapped onto
    the session store's window_log row (not the ``decisions`` dict, which
    ``simulate_play`` consumes verbatim and must never carry it)."""

    def _at_first_window(self, conn, sid):
        first = decision_months(120)[0]
        ss.advance_reveal(conn, sid, first + 1)
        return first

    def test_new_session_stamps_schema_version(self, session):
        _conn, doc = session
        assert doc["rationale_schema_version"] == "1.0"

    def test_no_rationale_key_when_not_supplied(self, session):
        """Acceptance 2: a window decided with no rationale must not gain a
        ``rationale`` key at all -- not even ``null`` -- so a session with
        rationale absent everywhere differs from the pre-change format by
        exactly the top-level schema-version stamp."""
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        after = ss.record_decision(conn, sid, month=first, action="hold")
        (row,) = after["window_log"]
        assert "rationale" not in row

    def test_rationale_round_trips_unicode_and_newlines(self, session):
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        text = "café — reasoning line one\nline two: 日本語のテキスト\ttabbed"
        after = ss.record_decision(
            conn,
            sid,
            month=first,
            action="derisk",
            rationale={"free_text": text, "tags": ["valuation", "pacing"]},
        )
        (row,) = after["window_log"]
        assert row["rationale"]["free_text"] == text
        assert row["rationale"]["tags"] == ["valuation", "pacing"]
        assert row["rationale"]["recorded_at"]
        # and it survives a fresh read from the store, not just the return value
        reread = ss.get_session(conn, sid)
        assert reread["window_log"][0]["rationale"]["free_text"] == text

    def test_rationale_supplied_but_empty_is_still_recorded(self, session):
        """An explicitly-submitted empty rationale ({}) is distinct from no
        rationale at all: the player opened the box and said nothing, vs.
        never being asked. Both fields land null, but the key is present and
        timestamped."""
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        after = ss.record_decision(conn, sid, month=first, action="hold", rationale={})
        (row,) = after["window_log"]
        assert "rationale" in row
        assert row["rationale"]["free_text"] is None
        assert row["rationale"]["tags"] is None
        assert row["rationale"]["recorded_at"]

    def test_decisions_dict_never_carries_rationale(self, session):
        """The dict simulate_play consumes must stay exactly the action/
        commitments shape -- rationale lives only in window_log."""
        conn, doc = session
        sid = doc["session_id"]
        first = self._at_first_window(conn, sid)
        after = ss.record_decision(
            conn,
            sid,
            month=first,
            action="hold",
            commitments=None,
            rationale={"free_text": "should not reach decisions", "tags": ["other"]},
        )
        assert after["decisions"][str(first)] == "hold"
        assert "rationale" not in str(after["decisions"])

    def test_a_pre_change_database_upgrades_in_place(self):
        """The retrofit-r1 precedent (tests/test_retrofit_r1.py:127-152),
        applied to the sessions table: simulate a database created before
        narr-02 -- a ``sessions`` table with no ``rationale_schema_version``
        column, one legacy row. ``migrate()`` adds the column; the old row
        reads back stampless (NULL) and otherwise unchanged. No version
        break, no rewrite of existing bytes."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE worlds (world_id TEXT PRIMARY KEY, spec_version TEXT NOT NULL,
                status TEXT NOT NULL, json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE run_records (run_id TEXT PRIMARY KEY, world_id TEXT NOT NULL,
                resolved_engine TEXT NOT NULL, seed INTEGER NOT NULL,
                n_paths INTEGER NOT NULL, overrides TEXT NOT NULL,
                outputs_digest TEXT NOT NULL, summary_stats TEXT NOT NULL,
                created_at TEXT NOT NULL);
            CREATE TABLE sessions (
                session_id      TEXT PRIMARY KEY,
                run_id          TEXT NOT NULL REFERENCES run_records(run_id),
                world_id        TEXT NOT NULL REFERENCES worlds(world_id),
                months          INTEGER NOT NULL,
                revealed_months INTEGER NOT NULL DEFAULT 0,
                basis           TEXT NOT NULL,
                ranked          INTEGER NOT NULL DEFAULT 0,
                participant     TEXT,
                decisions       TEXT NOT NULL DEFAULT '{}',
                window_log      TEXT NOT NULL DEFAULT '[]',
                status          TEXT NOT NULL DEFAULT 'active',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );
            INSERT INTO worlds VALUES ('w0', '1.0.0', 'active', '{}', 't0');
            INSERT INTO run_records VALUES ('legacy-run', 'w0', '{}', 1, 2, '{}',
                'sha256:legacy', '{}', 't0');
            INSERT INTO sessions VALUES ('legacy-session', 'legacy-run', 'w0', 120, 0,
                'reported', 0, NULL, '{}', '[]', 'active', 't0', 't0');
            """
        )
        migrate(conn)
        migrate(conn)  # idempotent
        legacy = ss.get_session(conn, "legacy-session")
        assert legacy["rationale_schema_version"] is None
        assert legacy["basis"] == "reported" and legacy["status"] == "active"
        assert legacy["decisions"] == {} and legacy["window_log"] == []
        # the next session created against this same (now migrated) connection
        # carries the stamp -- the migration only spares rows already written
        new_doc = ss.create_session(conn, run_id="legacy-run", months=120)
        assert new_doc["rationale_schema_version"] == "1.0"


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
