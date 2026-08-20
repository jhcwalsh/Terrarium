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


def test_a_retired_world_cannot_be_built_under_the_new_engine(tmp_path: Path) -> None:
    """D-ER14-2: the campaign and spine worlds are RETIRED, not renumbered.
    Their world_ids are records of what a campaign actually executed -
    gen_presets.py states the principle for the G0 world ('a record of what
    G0 actually ran, and must not be rewritten') - and adding infra changes
    the SHAPE of the tape, so a re-run would return nine return series where
    the recorded evidence describes eight. Retirement is the only option
    that keeps the record meaning what it says."""
    db = tmp_path / "ah.db"
    result = _invoke(db, "world", "build", "--preset", "stress_1974")
    assert result.exit_code != 0
    assert "retired" in result.output.lower()
    assert result.output.isascii()  # Windows console is cp1252


def test_the_retired_presets_are_still_readable_and_byte_unchanged() -> None:
    from ah.cli import PRESETS_DIR, RETIRED_WORLD_IDS

    for stem in ("stress_1974", "stress_1990", "narration_1974", "spine_pilot"):
        doc = json.loads((PRESETS_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        assert doc["world_id"] in RETIRED_WORLD_IDS
        # the record is untouched: the authored multiple drift is STILL -2.0 here
        assert doc["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] == -2.0


def test_the_successor_stress_presets_are_not_retired_and_load_clean() -> None:
    """er14-06: retiring 701/703 (D-ER14-2) left the app's declared-stress
    picker family (SHOWN_GENERATOR_IDS = ["bootstrap-stratified"]) with no
    playable world. The fix is NOT to re-block the retired files in place --
    ``test_the_retired_presets_are_still_readable_and_byte_unchanged`` above
    and CHANGELOG's R3 ("byte-unchanged JSON records") both pin
    stress_1974.json/stress_1990.json as the permanent record, and
    RETIRED_WORLD_IDS is a hardcoded frozenset independent of file content --
    a rename in place would still leave the OLD id fenced forever while
    quietly rewriting the record's own file out from under it. So: three new
    files, three new world_ids in a new 71x sub-block (the same tens-digit
    move used for 51x -> 52x), none of them in RETIRED_WORLD_IDS, all loading
    clean through the same WorldSpec loader the retired ids are checked
    against here."""
    from ah.cli import PRESETS_DIR, RETIRED_WORLD_IDS
    from ah.core import loader

    for stem in ("stress_1974_successor", "stress_1990_successor", "gulf_decade"):
        doc = json.loads((PRESETS_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        assert doc["world_id"] not in RETIRED_WORLD_IDS
        world = loader.load_worldspec(doc)
        assert world.world_id == doc["world_id"]
        assert world.engine_defaults.generator_id == "bootstrap-stratified"


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


def test_replay_refuses_a_version_mismatched_record(tmp_path: Path) -> None:
    """Chosen-PE fix round (2026-08-20): a RunRecord whose stamped engine
    version is not the current one used to be recomputed under CURRENT code
    and printed MISMATCH — a false corruption alarm (the stored inputs are
    intact; the code that turns them into numbers moved). The verdict is now
    split: MATCH/MISMATCH is reserved for same-version records; otherwise a
    plain not-replayable statement, claiming neither, exit code 3
    (``ah.cli.NOT_REPLAYABLE_EXIT``). Same-version verification is proven
    unweakened here (the real record still MATCHes) and by
    ``test_replay_detects_tampered_digest`` above (a same-version tamper
    still MISMATCHes)."""
    from ah.cli import NOT_REPLAYABLE_EXIT
    from ah.core.engine import TOY_ENGINE_VERSION
    from ah.store.db import connect
    from ah.store.runrecords import get_run_record, save_run_record

    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    rid = _invoke(db, "run", "--paths", "8").stdout.strip()

    # a synthetic record stamped by an EARLIER toy engine: same world, same
    # digest bytes, only the version stamp differs (append-only: a NEW row)
    synthetic_rid = "00000000-dead-4bee-8f00-000000000001"
    conn = connect(db)
    rec = get_run_record(conn, rid)
    assert rec is not None
    stamped_old = dict(rec["resolved_engine"])
    stamped_old["generator_version"] = "toy-v0.0-synthetic"
    save_run_record(
        conn,
        run_id=synthetic_rid,
        world_id=rec["world_id"],
        resolved_engine=stamped_old,
        seed=rec["seed"],
        n_paths=rec["n_paths"],
        overrides={},
        outputs_digest=rec["outputs_digest"],
        summary_stats={},
        created_at="2026-08-20T00:00:00+00:00",
    )
    conn.close()

    for cmd in ("replay", "verify"):
        r = _invoke(db, cmd, synthetic_rid)
        assert r.exit_code == NOT_REPLAYABLE_EXIT
        assert "not replayable under current code" in r.stdout
        assert "toy-v0.0-synthetic" in r.stdout
        assert TOY_ENGINE_VERSION in r.stdout
        assert "MATCH" not in r.stdout  # covers MISMATCH too (substring)
        assert "True" not in r.stdout and "False" not in r.stdout
        assert r.stdout.isascii()  # Windows console is cp1252

    # the untouched same-version record still gets the full verdict
    ok = _invoke(db, "replay", rid)
    assert ok.exit_code == 0
    assert "MATCH" in ok.stdout


def test_replay_refuses_a_retired_worlds_record(tmp_path: Path) -> None:
    """The other half of the not-replayable verdict. The generated plane's
    play-alpha version is NOT stamped on RunRecords (``gen_lineage`` pins the
    generator family + campaign vintage, neither of which moves when the
    sleeve-mappings equation moves; the play-alpha stamp lives on session
    outcomes), so for translation-layer releases the retired-world fence IS
    the version signal a record can be checked against. Measured live before
    this fix: retired 712's stored run recomputed to its 722 successor's
    digest under v1.3 and printed MISMATCH — a false corruption alarm."""
    from ah.cli import NOT_REPLAYABLE_EXIT, RETIRED_WORLD_IDS
    from ah.store import worlds as worlds_store
    from ah.store.db import connect
    from ah.store.runrecords import get_run_record, save_run_record

    db = tmp_path / "ah.db"
    _invoke(db, "world", "build", "--preset", "stagflation")
    rid = _invoke(db, "run", "--paths", "8").stdout.strip()

    retired_id = "00000000-0000-4000-9000-000000000712"
    assert retired_id in RETIRED_WORLD_IDS
    retired_rid = "00000000-dead-4bee-8f00-000000000002"
    conn = connect(db)
    rec = get_run_record(conn, rid)
    assert rec is not None
    world = json.loads(conn.execute("SELECT json FROM worlds").fetchone()[0])
    world["world_id"] = retired_id  # plant a world under a retired id
    worlds_store.save_world(conn, world, created_at="2026-08-19T00:00:00+00:00")
    save_run_record(
        conn,
        run_id=retired_rid,
        world_id=retired_id,
        resolved_engine=dict(rec["resolved_engine"]),  # current version stamp
        seed=rec["seed"],
        n_paths=rec["n_paths"],
        overrides={},
        outputs_digest=rec["outputs_digest"],
        summary_stats={},
        created_at="2026-08-19T00:00:00+00:00",
    )
    conn.close()

    for cmd in ("replay", "verify"):
        r = _invoke(db, cmd, retired_rid)
        assert r.exit_code == NOT_REPLAYABLE_EXIT
        assert "not replayable under current code" in r.stdout
        assert "retired" in r.stdout
        assert "MATCH" not in r.stdout
        assert r.stdout.isascii()


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
