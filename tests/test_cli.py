"""WP0.9 acceptance: the CLI surface."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from ah.cli import app

RUNNER = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "fixtures" / "compiler" / "_manifest.json").read_text(encoding="utf-8")
)
_VALID_SCENARIO = next(e["scenario"] for e in MANIFEST if e["kind"] == "valid")
_REJECT_SCENARIO = next(e["scenario"] for e in MANIFEST if e["kind"] == "reject")


def _invoke(db: Path, *args: str):
    return RUNNER.invoke(app, ["--db", str(db), *args])


def test_version() -> None:
    result = RUNNER.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_full_loop(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"

    build = _invoke(db, "world", "build", "--preset", "stagflation")
    assert build.exit_code == 0
    wid = build.stdout.strip()

    validate = _invoke(db, "world", "validate")
    assert validate.exit_code == 0
    assert "blocking=[]" in validate.stdout

    run = _invoke(db, "run", "--paths", "20")
    assert run.exit_code == 0
    rid = run.stdout.strip()

    replay = _invoke(db, "replay", rid)
    assert replay.exit_code == 0
    assert "MATCH" in replay.stdout

    verify = _invoke(db, "verify", rid)
    assert verify.exit_code == 0
    assert verify.stdout.strip() == "True"

    chronicle = _invoke(db, "chronicle", wid)
    assert "birth" in chronicle.stdout
    assert "run" in chronicle.stdout

    show = _invoke(db, "world", "show", wid)
    assert json.loads(show.stdout)["world_id"] == wid


def test_battery_command(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "goldilocks")
    _invoke(db, "run", "--paths", "16")
    result = _invoke(db, "battery")
    # HISTORY: asserted exit 0 (true only while every gate was `todo`), then
    # exit 1 (ratification made excess_kurtosis fail — ER-7). toy-v0.5 closed
    # ER-7 (Student-t innovations + the -99% floor) and the battery passes all
    # four ratified gates, so the honest exit is 0 again. The command's job is
    # unchanged: exit non-zero the moment a ratified gate breaks.
    assert result.exit_code == 0
    assert "battery-0.1" in result.stdout
    assert "excess_kurtosis" in result.stdout


def test_build_scenario_offline(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    result = _invoke(db, "world", "build", "--scenario", _VALID_SCENARIO)
    assert result.exit_code == 0
    assert result.stdout.strip()  # a world id


def test_build_reject_scenario_exits_nonzero(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    result = _invoke(db, "world", "build", "--scenario", _REJECT_SCENARIO)
    assert result.exit_code != 0


def test_build_requires_exactly_one_source(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    assert _invoke(db, "world", "build").exit_code != 0  # neither
    assert _invoke(db, "world", "build", "--preset", "x", "--scenario", "y").exit_code != 0  # both


def test_unknown_preset_errors(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    assert _invoke(db, "world", "build", "--preset", "nope").exit_code != 0


def test_replay_detects_tampered_digest(tmp_path: Path) -> None:
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    rid = _invoke(db, "run", "--paths", "16").stdout.strip()

    # tamper directly in the db, then replay
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE run_records SET outputs_digest = ? WHERE run_id = ?",
        ("sha256:deadbeef", rid),
    )
    conn.commit()
    conn.close()

    replay = _invoke(db, "replay", rid)
    assert replay.exit_code != 0
    assert "MISMATCH" in replay.stdout


def test_run_two_runs_same_digest(tmp_path: Path) -> None:
    """Determinism: the same world+seed+paths yields the same digest each run."""
    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "reflation_boom")
    r1 = _invoke(db, "run", "--paths", "20", "--seed", "5").stdout.strip()
    r2 = _invoke(db, "run", "--paths", "20", "--seed", "5").stdout.strip()

    from ah.store.db import connect
    from ah.store.runrecords import get_run_record

    conn = connect(db)
    d1 = get_run_record(conn, r1)
    d2 = get_run_record(conn, r2)
    assert d1 is not None and d2 is not None
    assert d1["outputs_digest"] == d2["outputs_digest"]
