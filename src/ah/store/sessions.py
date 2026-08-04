"""Session store (su-eng-02) — the server-authoritative game state.

A session binds one player run to one RunRecord: the reveal pointer, the
decision log, and the DN-6 §8 research log all live HERE, not in the client
(DN-3 W3/W5: the bundle is display-only; anything that scores must round-trip
the server). Sessions are mutable rows — unlike the chronicle they are game
state, not history — but the repository enforces the two invariants that make
them trustworthy:

- ``revealed_months`` is **monotonic** (never rewinds), and never advances
  past the earliest decision window that has no recorded decision — the
  commitment mechanic is enforced at the storage surface, not by UI honesty.
- ``decisions`` is **append-only within the row**: one decision per window,
  recorded with the server's wall-clock timestamp. Re-deciding a window is
  refused.

Wall-clock note, stated because the repo's determinism invariant forbids it
elsewhere: the ENGINE stays clock-free; the service layer records server
timestamps because DN-6 §8's research schema requires them. That is the one
sanctioned use.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from ah.core.institution import ACTIONS, decision_months

__all__ = [
    "SessionError",
    "advance_reveal",
    "complete_session",
    "create_session",
    "get_session",
    "record_decision",
]


class SessionError(ValueError):
    """A session operation that violates the reveal/commitment invariants."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_doc(row: sqlite3.Row) -> dict[str, Any]:
    doc = dict(row)
    doc["decisions"] = json.loads(doc["decisions"])
    doc["window_log"] = json.loads(doc["window_log"])
    doc["ranked"] = bool(doc["ranked"])
    return doc


def create_session(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    months: int,
    basis: str = "reported",
    ranked: bool = False,
    participant: str | None = None,
) -> dict[str, Any]:
    """Open a session over a RunRecord. ``months`` comes from the verified run."""
    if basis not in ("reported", "actual"):
        raise SessionError(f"basis must be 'reported' or 'actual', got {basis!r}")
    rec = conn.execute("SELECT world_id FROM run_records WHERE run_id = ?", (run_id,)).fetchone()
    if rec is None:
        raise SessionError(f"no run_record with run_id={run_id}")

    session_id = str(uuid.uuid4())
    now = _now()
    conn.execute(
        """INSERT INTO sessions
           (session_id, run_id, world_id, months, revealed_months, basis, ranked,
            participant, decisions, window_log, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 0, ?, ?, ?, '{}', '[]', 'active', ?, ?)""",
        (session_id, run_id, rec["world_id"], months, basis, int(ranked), participant, now, now),
    )
    conn.commit()
    return get_session(conn, session_id)


def get_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        raise SessionError(f"no session with session_id={session_id}")
    return _row_to_doc(row)


def _reveal_ceiling(doc: dict[str, Any]) -> int:
    """The furthest month the pointer may reveal: one past the last decided
    window, or the horizon if every window is decided.

    A window at month m blocks revelation of months > m until decided (you
    commit BEFORE seeing what happens next — E1's commitment mechanic).
    """
    decided = {int(k) for k in doc["decisions"]}
    for m in decision_months(doc["months"]):
        if m not in decided:
            return m + 1  # month m itself is visible; the future is not
    return doc["months"]


def advance_reveal(conn: sqlite3.Connection, session_id: str, to_month: int) -> dict[str, Any]:
    """Advance the reveal pointer (monotonic, capped by undecided windows)."""
    doc = get_session(conn, session_id)
    if doc["status"] != "active":
        raise SessionError(f"session {session_id} is {doc['status']}, not active")
    if to_month < doc["revealed_months"]:
        raise SessionError(f"reveal pointer never rewinds ({doc['revealed_months']} -> {to_month})")
    ceiling = _reveal_ceiling(doc)
    if to_month > ceiling:
        raise SessionError(
            f"cannot reveal month {to_month}: window at month {ceiling - 1} "
            f"is undecided (ceiling {ceiling})"
        )
    conn.execute(
        "UPDATE sessions SET revealed_months = ?, updated_at = ? WHERE session_id = ?",
        (to_month, _now(), session_id),
    )
    conn.commit()
    return get_session(conn, session_id)


def record_decision(
    conn: sqlite3.Connection,
    session_id: str,
    *,
    month: int,
    action: str,
    client_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record one decision at one window — validated, timestamped, final.

    The DN-6 §8 row: the client's self-reported fields (time_on_window_ms,
    basis_toggles) ride along verbatim; the server adds its own received-at
    timestamp and the session's arm fields (basis, ranked). Server fields are
    authoritative; client fields are research telemetry, never trusted for
    scoring.
    """
    doc = get_session(conn, session_id)
    if doc["status"] != "active":
        raise SessionError(f"session {session_id} is {doc['status']}, not active")
    if action not in ACTIONS:
        raise SessionError(f"unknown action {action!r} (allowed: {sorted(ACTIONS)})")
    windows = decision_months(doc["months"])
    if month not in windows:
        raise SessionError(f"month {month} is not a decision window (windows: {windows})")
    if str(month) in doc["decisions"]:
        raise SessionError(f"window at month {month} already decided — decisions are final")
    undecided = [m for m in windows if str(m) not in doc["decisions"]]
    if month != undecided[0]:
        raise SessionError(
            f"windows are decided in order: next undecided is month {undecided[0]}, got {month}"
        )
    if doc["revealed_months"] < month + 1:
        raise SessionError(
            f"window at month {month} is not yet revealed (pointer at {doc['revealed_months']})"
        )

    decisions = dict(doc["decisions"])
    decisions[str(month)] = action
    log_row = {
        "month": month,
        "action": action,
        "server_received_at": _now(),
        "basis": doc["basis"],
        "ranked": doc["ranked"],
        "client": dict(client_log or {}),
    }
    window_log = [*doc["window_log"], log_row]
    conn.execute(
        "UPDATE sessions SET decisions = ?, window_log = ?, updated_at = ? WHERE session_id = ?",
        (json.dumps(decisions), json.dumps(window_log), _now(), session_id),
    )
    conn.commit()
    return get_session(conn, session_id)


def complete_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    """Close a session once every month is revealed and every window decided."""
    doc = get_session(conn, session_id)
    if doc["status"] != "active":
        raise SessionError(f"session {session_id} is {doc['status']}, not active")
    windows = decision_months(doc["months"])
    undecided = [m for m in windows if str(m) not in doc["decisions"]]
    if undecided:
        raise SessionError(f"cannot complete: windows undecided at months {undecided}")
    if doc["revealed_months"] < doc["months"]:
        raise SessionError(
            f"cannot complete: only {doc['revealed_months']}/{doc['months']} months revealed"
        )
    conn.execute(
        "UPDATE sessions SET status = 'completed', updated_at = ? WHERE session_id = ?",
        (_now(), session_id),
    )
    conn.commit()
    return get_session(conn, session_id)
