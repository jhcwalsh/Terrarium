"""Artifact publications in the chronicle (WP4.1) — the G9 record.

Publications ride the EXISTING append-only chronicle (Step 0's table and
triggers, both already tested) as ``type='artifact'`` entries, so there is
exactly one immutability story in the repo. The payload carries the record
the sealed G9 rule demands: artifact type, dateline, author tier, gate
result, payload hash, prompt version, model id, retry count. An incomplete
record refuses to publish — G9 verbatim: absence of a complete record
blocks publication.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ah.artifacts.calendar import ARTIFACT_TYPES, AUTHOR_TIERS
from ah.store import chronicle as store_chronicle

CHRONICLE_TYPE = "artifact"
GATE_RESULTS = ("pass", "fail", "fallback", "tier1_deterministic")


class PublicationError(ValueError):
    """A publication record that G9 refuses."""


def record_publication(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    seq: int,
    created_at: str,
    artifact_type: str,
    dateline: str,
    author_tier: int,
    gate_result: str,
    payload_hash: str,
    month: int | None = None,
    prompt_version: str | None = None,
    model_id: str | None = None,
    retry_count: int = 0,
) -> int:
    """Append one publication record; returns its chronicle row id.

    Tier-1 artifacts record ``gate_result='tier1_deterministic'`` (they are
    rule-generated; the consistency gate judges Tier-2 prose). Tier-2
    records must carry the prompt version and model id — a Tier-2
    publication with no provenance is exactly what G9 exists to block.
    """
    if artifact_type not in ARTIFACT_TYPES:
        raise PublicationError(f"unknown artifact_type '{artifact_type}'")
    if author_tier not in AUTHOR_TIERS:
        raise PublicationError("author_tier must be 1 or 2")
    if gate_result not in GATE_RESULTS:
        raise PublicationError(f"gate_result must be one of {GATE_RESULTS}")
    if not payload_hash.startswith("sha256:"):
        raise PublicationError("payload_hash must be a 'sha256:' digest")
    if not dateline:
        raise PublicationError("dateline is required")
    if retry_count < 0:
        raise PublicationError("retry_count cannot be negative")
    if author_tier == 2 and (prompt_version is None or model_id is None):
        raise PublicationError("a tier-2 publication must record prompt_version and model_id (G9)")
    payload: dict[str, Any] = {
        "artifact_type": artifact_type,
        "dateline": dateline,
        "author_tier": author_tier,
        "gate_result": gate_result,
        "payload_hash": payload_hash,
        "prompt_version": prompt_version,
        "model_id": model_id,
        "retry_count": retry_count,
    }
    return store_chronicle.append(
        conn,
        world_id=world_id,
        seq=seq,
        type=CHRONICLE_TYPE,
        payload=payload,
        created_at=created_at,
        month=month,
    )


def read_publications(conn: sqlite3.Connection, world_id: str) -> list[dict[str, Any]]:
    """All publication records for a world, in chronicle order."""
    return [e for e in store_chronicle.read(conn, world_id) if e["type"] == CHRONICLE_TYPE]
