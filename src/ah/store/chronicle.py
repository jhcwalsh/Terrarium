"""Append-only chronicle repository (STEP0-PLAN §WP0.6).

The repository exposes only ``append`` and ``read`` — there is deliberately no
update or delete function. The database enforces the same invariant with triggers
(see ``db.py``); both layers are covered by tests.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def append(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    seq: int,
    type: str,
    payload: dict[str, Any],
    created_at: str,
    run_id: str | None = None,
    month: int | None = None,
) -> int:
    """Append one chronicle entry; returns its row id."""
    cur = conn.execute(
        "INSERT INTO chronicle(world_id, run_id, seq, month, type, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (world_id, run_id, seq, month, type, json.dumps(payload, sort_keys=True), created_at),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def read(conn: sqlite3.Connection, world_id: str) -> list[dict[str, Any]]:
    """Read all chronicle entries for a world, ordered by sequence then id."""
    rows = conn.execute(
        "SELECT id, world_id, run_id, seq, month, type, payload, created_at "
        "FROM chronicle WHERE world_id = ? ORDER BY seq, id",
        (world_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        entry = dict(r)
        entry["payload"] = json.loads(entry["payload"])
        out.append(entry)
    return out
