"""Worlds repository with engine-field immutability (STEP0-PLAN §WP0.6).

``world_id`` is immutable. Editing any engine-consumed field (horizon, regimes,
factor_conditions, structural, engine_defaults) under the same ``world_id`` is
refused — the caller must mint a new ``world_id`` with ``provenance.source.
parent_world_id`` pointing back. Narrative/provenance/status edits are allowed
in place (they cannot change simulated behavior).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ah.core.digest import canonical_json

# Fields the engine consumes — i.e., the NumericWorld projection.
ENGINE_FIELDS: tuple[str, ...] = (
    "horizon",
    "regimes",
    "factor_conditions",
    "structural",
    "engine_defaults",
)


class ImmutableWorldError(ValueError):
    """Raised when an engine-consumed field is edited under an existing world_id."""


def get_world(conn: sqlite3.Connection, world_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT json FROM worlds WHERE world_id = ?", (world_id,)).fetchone()
    return json.loads(row["json"]) if row is not None else None


def save_world(conn: sqlite3.Connection, world: dict[str, Any], *, created_at: str) -> None:
    """Insert a new world, or update narrative/provenance in place.

    Raises :class:`ImmutableWorldError` if any engine-consumed field differs from
    the stored version under the same ``world_id``.
    """
    world_id = world["world_id"]
    existing = get_world(conn, world_id)
    payload = canonical_json(world)

    if existing is None:
        conn.execute(
            "INSERT INTO worlds(world_id, spec_version, status, json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (world_id, world["spec_version"], world["status"], payload, created_at),
        )
        conn.commit()
        return

    for field in ENGINE_FIELDS:
        if canonical_json(existing.get(field)) != canonical_json(world.get(field)):
            raise ImmutableWorldError(
                f"engine-consumed field '{field}' changed for world_id={world_id}; "
                "create a new world_id with provenance.source.parent_world_id set."
            )

    # engine fields unchanged -> narrative/provenance/status edit allowed in place
    conn.execute(
        "UPDATE worlds SET spec_version = ?, status = ?, json = ? WHERE world_id = ?",
        (world["spec_version"], world["status"], payload, world_id),
    )
    conn.commit()
