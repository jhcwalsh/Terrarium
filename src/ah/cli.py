"""``ah`` command-line interface (STEP0-PLAN §WP0.9).

Proves the whole loop: ``ah world build`` -> ``ah world validate`` -> ``ah run``
-> ``ah replay`` (bit-identical digest) plus ``verify``, ``battery``, ``chronicle``,
``world show``. The live Anthropic compiler is imported lazily only under
``--live`` so importing this module (as tests do) never pulls the network path.

Note: no ``from __future__ import annotations`` here — Typer resolves parameter
type hints at runtime and that import breaks it.
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import typer

from ah import __version__
from ah.battery.report import BATTERY_VERSION, render_markdown, run_battery
from ah.compiler.fixture_adapter import FixtureCompiler
from ah.compiler.pipeline import process
from ah.core.digest import digest_ensemble
from ah.core.engine import TOY_GENERATOR_ID, run_ensemble
from ah.core.institution import hold_course_twin
from ah.core.numericworld import project_numeric
from ah.core.validator import VALIDATOR_VERSION, stamp_validation, validate
from ah.core.worldspec import WorldSpec
from ah.store import chronicle as chronicle_store
from ah.store import runrecords as run_store
from ah.store import worlds as worlds_store
from ah.store.db import connect

_REPO_ROOT = Path(__file__).resolve().parents[2]
PRESETS_DIR = Path(__file__).resolve().parent / "presets"
FIXTURES_DIR = _REPO_ROOT / "fixtures" / "compiler"
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"

app = typer.Typer(
    help="Alternate Histories platform CLI.", no_args_is_help=True, add_completion=False
)
world_app = typer.Typer(help="World lifecycle: build, validate, show.", no_args_is_help=True)
app.add_typer(world_app, name="world")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _db(ctx: typer.Context) -> sqlite3.Connection:
    path = ctx.obj["db"]
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return connect(path)


def _next_seq(conn: sqlite3.Connection, world_id: str) -> int:
    return len(chronicle_store.read(conn, world_id))


def _latest_world(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT world_id FROM worlds ORDER BY rowid DESC LIMIT 1").fetchone()
    if row is None:
        raise typer.BadParameter("no worlds in the database yet")
    return str(row[0])


def _latest_run(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT run_id FROM run_records ORDER BY rowid DESC LIMIT 1").fetchone()
    if row is None:
        raise typer.BadParameter("no run records in the database yet")
    return str(row[0])


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite database path."),
) -> None:
    """Global options; subcommands do the work."""
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    ctx.obj = {"db": db}


@world_app.command("build")
def world_build(
    ctx: typer.Context,
    preset: str | None = typer.Option(None, "--preset", help="Preset world name."),
    scenario: str | None = typer.Option(None, "--scenario", help="Scenario text."),
    live: bool = typer.Option(False, "--live", help="Use the live Anthropic compiler."),
) -> None:
    """Build a world from a preset or a scenario; validate, stamp, and store it."""
    if bool(preset) == bool(scenario):
        raise typer.BadParameter("provide exactly one of --preset or --scenario")

    if preset:
        path = PRESETS_DIR / f"{preset}.json"
        if not path.exists():
            available = ", ".join(p.stem for p in sorted(PRESETS_DIR.glob("*.json")))
            raise typer.BadParameter(f"unknown preset '{preset}'. Available: {available}")
        raw = json.loads(path.read_text(encoding="utf-8"))
    elif live:
        from ah.compiler.anthropic_adapter import AnthropicCompiler

        raw = AnthropicCompiler().compile(scenario or "")
    else:
        raw = FixtureCompiler(FIXTURES_DIR).compile(scenario or "")

    outcome = process(raw)
    if outcome.rejected:
        typer.echo(f"REJECTED: {outcome.reject_reason}", err=True)
        raise typer.Exit(1)

    now = _now()
    stamped = stamp_validation(
        outcome.result, validated_at=now, validator_version=VALIDATOR_VERSION
    )
    conn = _db(ctx)
    worlds_store.save_world(conn, stamped, created_at=now)
    wid = stamped["world_id"]
    chronicle_store.append(
        conn,
        world_id=wid,
        seq=_next_seq(conn, wid),
        type="birth",
        payload={"status": stamped["status"], "clamps": len(outcome.result.clamps)},
        created_at=now,
    )
    typer.echo(wid)


@world_app.command("validate")
def world_validate(ctx: typer.Context, world_id: str | None = typer.Argument(None)) -> None:
    """Re-run the validator on a stored world and report clamps/warnings/blocking."""
    conn = _db(ctx)
    wid = world_id or _latest_world(conn)
    world = worlds_store.get_world(conn, wid)
    if world is None:
        raise typer.BadParameter(f"no world with id {wid}")
    result = validate(world)
    typer.echo(
        f"world {wid}: clamps={len(result.clamps)} "
        f"warnings={[f.rule for f in result.warnings]} "
        f"blocking={[f.rule for f in result.blocking]}"
    )
    if result.blocking:
        raise typer.Exit(1)


@world_app.command("show")
def world_show(ctx: typer.Context, world_id: str | None = typer.Argument(None)) -> None:
    """Print a stored world as JSON."""
    conn = _db(ctx)
    wid = world_id or _latest_world(conn)
    world = worlds_store.get_world(conn, wid)
    if world is None:
        raise typer.BadParameter(f"no world with id {wid}")
    typer.echo(json.dumps(world, indent=2, sort_keys=True))


@app.command("run")
def run_cmd(
    ctx: typer.Context,
    world_id: str | None = typer.Argument(None),
    seed: int | None = typer.Option(None, "--seed"),
    paths: int | None = typer.Option(None, "--paths"),
) -> None:
    """Run the engine on a world and record a RunRecord (prints the run_id)."""
    conn = _db(ctx)
    wid = world_id or _latest_world(conn)
    world = worlds_store.get_world(conn, wid)
    if world is None:
        raise typer.BadParameter(f"no world with id {wid}")

    ws = WorldSpec.model_validate(world)
    nw = project_numeric(ws)
    ed = ws.engine_defaults
    resolved_seed = seed if seed is not None else (ed.base_seed if ed.base_seed is not None else 0)
    resolved_paths = paths if paths is not None else ed.n_paths

    ensemble = run_ensemble(nw, resolved_paths, base_seed=resolved_seed)
    digest = digest_ensemble(ensemble)
    twin = hold_course_twin(nw, resolved_seed)

    overrides: dict[str, int] = {}
    if seed is not None:
        overrides["seed"] = seed
    if paths is not None:
        overrides["n_paths"] = paths

    run_id = str(uuid.uuid4())
    now = _now()
    run_store.save_run_record(
        conn,
        run_id=run_id,
        world_id=wid,
        resolved_engine={
            "generator_id": ed.generator_id,
            "generator_version": TOY_GENERATOR_ID,
            "validator_version": VALIDATOR_VERSION,
            "battery_version": BATTERY_VERSION,
        },
        seed=resolved_seed,
        n_paths=resolved_paths,
        overrides=overrides,
        outputs_digest=digest,
        summary_stats={"final_of_100": twin.final_value},
        created_at=now,
    )
    chronicle_store.append(
        conn,
        world_id=wid,
        run_id=run_id,
        seq=_next_seq(conn, wid),
        type="run",
        payload={"digest": digest, "seed": resolved_seed, "n_paths": resolved_paths},
        created_at=now,
    )
    typer.echo(run_id)


@app.command("replay")
def replay_cmd(ctx: typer.Context, run_id: str | None = typer.Argument(None)) -> None:
    """Recompute a run's output digest and compare it to the stored digest."""
    conn = _db(ctx)
    rid = run_id or _latest_run(conn)
    rec = run_store.get_run_record(conn, rid)
    if rec is None:
        raise typer.BadParameter(f"no run with id {rid}")
    world = worlds_store.get_world(conn, rec["world_id"])
    assert world is not None
    recomputed = run_store.compute_outputs_digest(world, rec["seed"], rec["n_paths"])
    match = recomputed == rec["outputs_digest"]
    typer.echo(f"stored : {rec['outputs_digest']}")
    typer.echo(f"replay : {recomputed}")
    typer.echo("MATCH" if match else "MISMATCH")
    if not match:
        raise typer.Exit(1)


@app.command("verify")
def verify_cmd(ctx: typer.Context, run_id: str | None = typer.Argument(None)) -> None:
    """Verify a run reproduces its stored digest (prints True/False)."""
    conn = _db(ctx)
    rid = run_id or _latest_run(conn)
    ok = run_store.verify_run(conn, rid)
    typer.echo(str(ok))
    if not ok:
        raise typer.Exit(1)


@app.command("battery")
def battery_cmd(ctx: typer.Context, run_id: str | None = typer.Argument(None)) -> None:
    """Run the validation battery on a run's ensemble."""
    conn = _db(ctx)
    rid = run_id or _latest_run(conn)
    rec = run_store.get_run_record(conn, rid)
    if rec is None:
        raise typer.BadParameter(f"no run with id {rid}")
    world = worlds_store.get_world(conn, rec["world_id"])
    assert world is not None
    nw = project_numeric(WorldSpec.model_validate(world))
    ensemble = run_ensemble(nw, rec["n_paths"], base_seed=rec["seed"])
    report = run_battery(ensemble)
    typer.echo(render_markdown(report))
    if not report.passed:
        raise typer.Exit(1)


@app.command("chronicle")
def chronicle_cmd(ctx: typer.Context, world_id: str | None = typer.Argument(None)) -> None:
    """Print the append-only chronicle for a world."""
    conn = _db(ctx)
    wid = world_id or _latest_world(conn)
    for entry in chronicle_store.read(conn, wid):
        typer.echo(f"[{entry['seq']:>3}] {entry['type']:<8} {json.dumps(entry['payload'])}")


if __name__ == "__main__":  # pragma: no cover
    app()
