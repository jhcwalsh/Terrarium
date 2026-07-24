"""Gate G0 — the Definition of Done, executed programmatically (STEP0-PLAN §0).

Each test maps to one of the seven G0 criteria. This file is the platform's first
gate-evidence artifact in code; ``G0-EVIDENCE.md`` records the same run narratively.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from ah.battery.report import run_battery
from ah.cli import app
from ah.compiler.fixture_adapter import FixtureCompiler
from ah.compiler.pipeline import process
from ah.core.engine import run_ensemble
from ah.core.numericworld import project_numeric as _project
from ah.core.worldspec import WorldSpec
from ah.store.db import connect
from ah.store.runrecords import get_run_record, verify_run
from ah.store.worlds import get_world

RUNNER = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "compiler"
MANIFEST = json.loads((FIXTURES / "_manifest.json").read_text(encoding="utf-8"))


def _invoke(db: Path, *args: str):
    return RUNNER.invoke(app, ["--db", str(db), *args])


# --------------------------------------------------------------------------- #
# G0.1 — the loop completes and replay is bit-identical
# --------------------------------------------------------------------------- #


def test_g0_1_loop_and_bit_identical_replay(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    assert _invoke(db, "world", "build", "--preset", "stagflation").exit_code == 0
    assert _invoke(db, "world", "validate").exit_code == 0
    run = _invoke(db, "run", "--paths", "50")
    assert run.exit_code == 0
    replay = _invoke(db, "replay")
    assert replay.exit_code == 0
    assert "MATCH" in replay.stdout

    # build at vintage k, "refresh" (run again), rebuild -> identical digest
    rid = run.stdout.strip()
    conn = connect(db)
    first = get_run_record(conn, rid)
    assert first is not None
    _invoke(db, "run", "--paths", "50")  # refresh
    rid2 = _invoke(db, "run", "--paths", "50").stdout.strip()
    third = get_run_record(conn := connect(db), rid2)
    assert third is not None
    assert first["outputs_digest"] == third["outputs_digest"]


# --------------------------------------------------------------------------- #
# G0.2 — schema + V-rule validation; clamps/warnings recorded in provenance
# --------------------------------------------------------------------------- #


def test_g0_2_validation_recorded_in_provenance(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    conn = connect(db)
    row = conn.execute("SELECT world_id FROM worlds").fetchone()
    world = get_world(conn, row[0])
    assert world is not None
    val = world["provenance"]["validation"]
    assert val["validator_version"] == "1.0.0"
    assert "clamps" in val and "warnings" in val
    assert world["status"] == "validated"


def test_g0_2_clamp_fixture_records_clamps() -> None:
    clamp = next(e for e in MANIFEST if e["kind"] == "clamp")
    raw = FixtureCompiler(FIXTURES).compile(clamp["scenario"])
    outcome = process(raw)
    assert not outcome.rejected
    assert outcome.result.clamps  # bounds were clamped and recorded


# --------------------------------------------------------------------------- #
# G0.3 — RunRecords store engine/seed/digest; tamper detected
# --------------------------------------------------------------------------- #


def test_g0_3_runrecord_fields_and_tamper(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    rid = _invoke(db, "run", "--paths", "40").stdout.strip()

    conn = connect(db)
    rec = get_run_record(conn, rid)
    assert rec is not None
    assert rec["resolved_engine"]["generator_version"]
    assert rec["resolved_engine"]["validator_version"] == "1.0.0"
    assert rec["resolved_engine"]["battery_version"]
    assert rec["outputs_digest"].startswith("sha256:")
    assert verify_run(conn, rid) is True

    conn.execute("UPDATE run_records SET outputs_digest='sha256:bad' WHERE run_id=?", (rid,))
    conn.commit()
    assert verify_run(connect(db), rid) is False


# --------------------------------------------------------------------------- #
# G0.4 — chronicle is append-only
# --------------------------------------------------------------------------- #


def test_g0_4_chronicle_append_only(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    _invoke(db, "run", "--paths", "10")
    conn = connect(db)
    with pytest.raises(sqlite3.Error):
        conn.execute("UPDATE chronicle SET type='x'")
    with pytest.raises(sqlite3.Error):
        conn.execute("DELETE FROM chronicle")


# --------------------------------------------------------------------------- #
# G0.5 — offline compiler harness: 50 fixtures, schema-valid, bounds-clamped
# --------------------------------------------------------------------------- #


def test_g0_5_compiler_harness_offline() -> None:
    compiler = FixtureCompiler(FIXTURES)
    assert len(MANIFEST) == 50
    rejects = 0
    for entry in MANIFEST:
        outcome = process(compiler.compile(entry["scenario"]))
        if entry["kind"] == "reject":
            assert outcome.rejected
            rejects += 1
        else:
            assert not outcome.rejected
            assert outcome.world is not None
            paths = run_ensemble(_project(outcome.world), 2, base_seed=1)
            assert paths.months >= 12  # runs at least 12 months
    assert rejects == 5


# --------------------------------------------------------------------------- #
# G0.6 — battery skeleton computes the panel and evaluates thresholds
# --------------------------------------------------------------------------- #


def test_g0_6_battery_plumbing(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    conn = connect(db)
    world = get_world(conn, conn.execute("SELECT world_id FROM worlds").fetchone()[0])
    assert world is not None
    ensemble = run_ensemble(_project(WorldSpec.model_validate(world)), 32, base_seed=42)
    report = run_battery(ensemble)
    assert report.checks  # thresholds evaluated
    assert set(report.scalars) >= {"excess_kurtosis", "acf_abs_lag1", "corr_distance"}
    assert all(np.isfinite(v) or np.isnan(v) for v in report.scalars.values())
