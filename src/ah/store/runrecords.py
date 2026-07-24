"""RunRecords repository + reproducibility verification (STEP0-PLAN §WP0.6).

A RunRecord pins world_id, resolved engine, seed, n_paths, and the SHA-256
``outputs_digest`` of the run's output tensor. ``verify_run`` re-runs the engine
from the stored world + seed + n_paths and checks the recomputed digest against the
stored one — this is the reproducibility anchor behind G0's bit-identical replay and
the tamper test (mutating the stored digest is detected).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ah.core.digest import digest_ensemble
from ah.core.engine import run_ensemble
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.store.worlds import get_world


def compute_outputs_digest(world: dict[str, Any], seed: int, n_paths: int) -> str:
    """Digest the ensemble a run would produce from ``world`` at ``seed``/``n_paths``."""
    nw = project_numeric(WorldSpec.model_validate(world))
    return digest_ensemble(run_ensemble(nw, n_paths, base_seed=seed))


def save_run_record(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    world_id: str,
    resolved_engine: dict[str, Any],
    seed: int,
    n_paths: int,
    overrides: dict[str, Any],
    outputs_digest: str,
    summary_stats: dict[str, Any],
    created_at: str,
) -> None:
    conn.execute(
        "INSERT INTO run_records(run_id, world_id, resolved_engine, seed, n_paths, "
        "overrides, outputs_digest, summary_stats, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            world_id,
            json.dumps(resolved_engine, sort_keys=True),
            seed,
            n_paths,
            json.dumps(overrides, sort_keys=True),
            outputs_digest,
            json.dumps(summary_stats, sort_keys=True),
            created_at,
        ),
    )
    conn.commit()


def get_run_record(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM run_records WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    rec = dict(row)
    for field in ("resolved_engine", "overrides", "summary_stats"):
        rec[field] = json.loads(rec[field])
    return rec


def verify_run(conn: sqlite3.Connection, run_id: str) -> bool:
    """Recompute the run's output digest from stored inputs; True iff it matches."""
    rec = get_run_record(conn, run_id)
    if rec is None:
        raise KeyError(f"no run_record with run_id={run_id}")
    world = get_world(conn, rec["world_id"])
    if world is None:
        raise KeyError(f"run {run_id} references missing world {rec['world_id']}")
    recomputed = compute_outputs_digest(world, rec["seed"], rec["n_paths"])
    return recomputed == rec["outputs_digest"]
