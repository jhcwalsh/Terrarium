"""Leaderboard repository (retrofit R-1, DN-5) — scoped by the triple key.

The scope key is ``(world_id, seed, decision_alpha_version)`` from birth:
scores produced under different decision-alpha definitions are different
competitions and never share a board. ``decision_alpha_version`` is a
REQUIRED argument on every function here — there is no default and no
query path that omits it, by construction rather than by review.

Created at the retrofit, before any row exists anywhere. Row semantics
(what a score IS) arrive with WP4.7's comparative scoring; this module is
shape only.
"""

from __future__ import annotations

import sqlite3
from typing import Any


class LeaderboardError(ValueError):
    """A submission the repository refuses."""


def submit_score(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    seed: int,
    decision_alpha_version: str,
    participant: str,
    score: float,
    created_at: str,
) -> int:
    """Insert one score; duplicate (world, seed, alpha-version, participant)
    is a refusal, not an upsert — resubmission semantics are WP4.7's call."""
    if not decision_alpha_version:
        raise LeaderboardError("decision_alpha_version is required (scope key)")
    if not participant:
        raise LeaderboardError("participant is required")
    try:
        cur = conn.execute(
            "INSERT INTO leaderboard(world_id, seed, decision_alpha_version, "
            "participant, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (world_id, seed, decision_alpha_version, participant, score, created_at),
        )
    except sqlite3.IntegrityError as exc:
        raise LeaderboardError(
            f"duplicate score for ({world_id}, {seed}, {decision_alpha_version}, {participant})"
        ) from exc
    conn.commit()
    return int(cur.lastrowid or 0)


def scores(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    seed: int,
    decision_alpha_version: str,
) -> list[dict[str, Any]]:
    """The board for one (world, seed, decision-alpha-version), best first."""
    rows = conn.execute(
        "SELECT participant, score, created_at FROM leaderboard "
        "WHERE world_id = ? AND seed = ? AND decision_alpha_version = ? "
        "ORDER BY score DESC, participant",
        (world_id, seed, decision_alpha_version),
    ).fetchall()
    return [dict(r) for r in rows]
