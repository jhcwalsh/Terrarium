"""SQLite connection + migrations for the append-only stores (STEP0-PLAN §WP0.6).

One file (``data/ah.db`` in production; ``:memory:`` or a tmp file in tests). WAL
mode and foreign keys are enabled per connection. The chronicle is made append-only
by triggers *and* by the repository surface (see ``chronicle.py``) — both layers are
tested. The repository pattern keeps callers ignorant of SQLite so Postgres can
replace it later.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    world_id    TEXT PRIMARY KEY,
    spec_version TEXT NOT NULL,
    status      TEXT NOT NULL,
    json        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_records (
    run_id        TEXT PRIMARY KEY,
    world_id      TEXT NOT NULL REFERENCES worlds(world_id),
    resolved_engine TEXT NOT NULL,
    seed          INTEGER NOT NULL,
    n_paths       INTEGER NOT NULL,
    overrides     TEXT NOT NULL,
    outputs_digest TEXT NOT NULL,
    summary_stats TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chronicle (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id   TEXT NOT NULL,
    run_id     TEXT,
    seq        INTEGER NOT NULL,
    month      INTEGER,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Append-only: updates and deletes are refused at the storage layer.
CREATE TRIGGER IF NOT EXISTS chronicle_no_update
BEFORE UPDATE ON chronicle
BEGIN
    SELECT RAISE(ABORT, 'chronicle is append-only: UPDATE is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS chronicle_no_delete
BEFORE DELETE ON chronicle
BEGIN
    SELECT RAISE(ABORT, 'chronicle is append-only: DELETE is forbidden');
END;
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open (and migrate) a database connection with WAL + foreign keys enabled."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # no-op for :memory:
    conn.execute("PRAGMA foreign_keys=ON;")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Create tables and triggers if absent (idempotent)."""
    conn.executescript(_SCHEMA)
    conn.commit()
