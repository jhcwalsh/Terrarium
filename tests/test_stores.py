"""WP0.6 acceptance (store side): worlds immutability, RunRecords + tamper, chronicle."""

from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import ah.store.chronicle as chronicle
from ah.store.db import connect
from ah.store.runrecords import (
    compute_outputs_digest,
    get_run_record,
    save_run_record,
    verify_run,
)
from ah.store.worlds import ImmutableWorldError, get_world, save_world

ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE: dict[str, Any] = json.loads(
    (ROOT / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
)
NOW = "2026-07-24T00:00:00Z"


def toy_world_dict() -> dict[str, Any]:
    doc = copy.deepcopy(_EXAMPLE)
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    return doc


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    c = connect(":memory:")
    yield c
    c.close()


# --------------------------------------------------------------------------- #
# db / worlds
# --------------------------------------------------------------------------- #


def test_migrate_creates_tables(conn: sqlite3.Connection) -> None:
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"worlds", "run_records", "chronicle"} <= names


def test_wal_mode_on_file_db(tmp_path: Path) -> None:
    c = connect(tmp_path / "ah.db")
    mode = c.execute("PRAGMA journal_mode;").fetchone()[0]
    assert mode.lower() == "wal"
    c.close()


def test_world_roundtrip(conn: sqlite3.Connection) -> None:
    w = toy_world_dict()
    save_world(conn, w, created_at=NOW)
    assert get_world(conn, w["world_id"]) == w


def test_engine_field_edit_is_rejected(conn: sqlite3.Connection) -> None:
    w = toy_world_dict()
    save_world(conn, w, created_at=NOW)
    edited = copy.deepcopy(w)
    edited["factor_conditions"]["equity"]["drift_annual_pct"] = 1.23  # engine field
    with pytest.raises(ImmutableWorldError):
        save_world(conn, edited, created_at=NOW)


def test_narrative_edit_allowed_in_place(conn: sqlite3.Connection) -> None:
    w = toy_world_dict()
    save_world(conn, w, created_at=NOW)
    edited = copy.deepcopy(w)
    edited["narrative"]["title"] = "A Fixed Typo"  # display-only
    save_world(conn, edited, created_at=NOW)  # must not raise
    stored = get_world(conn, w["world_id"])
    assert stored is not None
    assert stored["narrative"]["title"] == "A Fixed Typo"


def test_new_world_id_with_parent_is_allowed(conn: sqlite3.Connection) -> None:
    w = toy_world_dict()
    save_world(conn, w, created_at=NOW)
    child = copy.deepcopy(w)
    child["world_id"] = "00000000-0000-0000-0000-000000000abc"
    child["factor_conditions"]["equity"]["drift_annual_pct"] = 1.23
    child["provenance"]["source"] = {"kind": "derived", "parent_world_id": w["world_id"]}
    save_world(conn, child, created_at=NOW)  # different id -> allowed
    stored_child = get_world(conn, child["world_id"])
    assert stored_child is not None
    assert stored_child["world_id"] == child["world_id"]


# --------------------------------------------------------------------------- #
# run records + verify + tamper
# --------------------------------------------------------------------------- #


def _save_run(conn: sqlite3.Connection, seed: int = 42, n_paths: int = 3) -> str:
    w = toy_world_dict()
    save_world(conn, w, created_at=NOW)
    digest = compute_outputs_digest(w, seed, n_paths)
    run_id = "run-0001"
    save_run_record(
        conn,
        run_id=run_id,
        world_id=w["world_id"],
        resolved_engine={"generator_id": "toy-v0", "generator_version": "0"},
        seed=seed,
        n_paths=n_paths,
        overrides={"n_paths": n_paths},
        outputs_digest=digest,
        summary_stats={"final_of_100": 65.2},
        created_at=NOW,
    )
    return run_id


def test_run_record_roundtrip_and_verify(conn: sqlite3.Connection) -> None:
    run_id = _save_run(conn)
    rec = get_run_record(conn, run_id)
    assert rec is not None
    assert rec["resolved_engine"]["generator_id"] == "toy-v0"
    assert rec["seed"] == 42
    assert verify_run(conn, run_id) is True


def test_tamper_with_stored_digest_is_detected(conn: sqlite3.Connection) -> None:
    run_id = _save_run(conn)
    conn.execute(
        "UPDATE run_records SET outputs_digest = ? WHERE run_id = ?",
        ("sha256:deadbeef", run_id),
    )
    conn.commit()
    assert verify_run(conn, run_id) is False


def test_tamper_with_stored_world_is_detected(conn: sqlite3.Connection) -> None:
    run_id = _save_run(conn)
    rec = get_run_record(conn, run_id)
    assert rec is not None
    world = get_world(conn, rec["world_id"])
    assert world is not None
    world["factor_conditions"]["equity"]["drift_annual_pct"] = 5.0  # tamper (in-bounds)
    conn.execute(
        "UPDATE worlds SET json = ? WHERE world_id = ?",
        (json.dumps(world), rec["world_id"]),
    )
    conn.commit()
    assert verify_run(conn, run_id) is False


def test_verify_missing_run_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(KeyError):
        verify_run(conn, "nope")


# --------------------------------------------------------------------------- #
# chronicle append-only (both layers)
# --------------------------------------------------------------------------- #


def test_chronicle_append_and_read_ordered(conn: sqlite3.Connection) -> None:
    wid = "w1"
    chronicle.append(conn, world_id=wid, seq=1, type="decision", payload={"a": 1}, created_at=NOW)
    chronicle.append(conn, world_id=wid, seq=0, type="birth", payload={"b": 2}, created_at=NOW)
    rows = chronicle.read(conn, wid)
    assert [r["seq"] for r in rows] == [0, 1]  # ordered by seq
    assert rows[0]["payload"] == {"b": 2}


def test_chronicle_update_is_blocked_by_trigger(conn: sqlite3.Connection) -> None:
    rid = chronicle.append(conn, world_id="w", seq=0, type="x", payload={}, created_at=NOW)
    with pytest.raises(sqlite3.Error):
        conn.execute("UPDATE chronicle SET type = 'y' WHERE id = ?", (rid,))


def test_chronicle_delete_is_blocked_by_trigger(conn: sqlite3.Connection) -> None:
    rid = chronicle.append(conn, world_id="w", seq=0, type="x", payload={}, created_at=NOW)
    with pytest.raises(sqlite3.Error):
        conn.execute("DELETE FROM chronicle WHERE id = ?", (rid,))


def test_chronicle_repository_has_no_mutators() -> None:
    for forbidden in ("update", "delete", "remove", "edit"):
        assert not hasattr(chronicle, forbidden)
