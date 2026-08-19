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
from ah.core.engine import TOY_ENGINE_VERSION, run_ensemble
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

# ER-14 close-out (D-ER14-2, 2026-08-18). These worlds' numbers - and, with the
# infrastructure sleeve, the SHAPE of their tapes - changed under toy-v0.7, but
# their ids are records of what a campaign actually executed. Renumbering would
# not reproduce those campaigns, only produce differently-shaped new ones under
# new ids; leaving them runnable would invite exactly the leaderboard collision
# the fences exist to prevent. So: readable forever, never re-runnable.
RETIRED_WORLD_IDS = frozenset(
    {
        "00000000-0000-4000-9000-000000000701",  # stress_1974
        "00000000-0000-4000-9000-000000000703",  # stress_1990
        "00000000-0000-4000-9000-000000000801",  # narration_1974
        "00000000-0000-4000-9000-000000000802",  # spine_pilot
    }
)

app = typer.Typer(
    help="Alternate Histories platform CLI.", no_args_is_help=True, add_completion=False
)
world_app = typer.Typer(help="World lifecycle: build, validate, show.", no_args_is_help=True)
app.add_typer(world_app, name="world")

# Step 1 data-layer commands (ah data ...)
from ah.data.cli import data_app  # noqa: E402

app.add_typer(data_app, name="data")

# Step 2 experiment tracking (ah exp ...)
from ah.exp_cli import exp_app  # noqa: E402

app.add_typer(exp_app, name="exp")


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

    now = _now()
    if preset:
        path = PRESETS_DIR / f"{preset}.json"
        if not path.exists():
            available = ", ".join(p.stem for p in sorted(PRESETS_DIR.glob("*.json")))
            raise typer.BadParameter(f"unknown preset '{preset}'. Available: {available}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("world_id") in RETIRED_WORLD_IDS:
            typer.echo(
                f"RETIRED: world {raw['world_id']} is a campaign record and cannot be "
                "rebuilt under toy-v0.7 (ER-14 close-out, D-ER14-2). Read it, do not run it.",
                err=True,
            )
            raise typer.Exit(1)
    elif live:
        from ah.compiler.anthropic_adapter import AnthropicCompiler

        raw = AnthropicCompiler().compile(scenario or "", created_at=now)
    else:
        raw = FixtureCompiler(FIXTURES_DIR).compile(scenario or "")

    outcome = process(raw)
    if outcome.rejected:
        typer.echo(f"REJECTED: {outcome.reject_reason}", err=True)
        raise typer.Exit(1)
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

    if ed.generator_id == "toy-v0":
        ensemble = run_ensemble(nw, resolved_paths, base_seed=resolved_seed)
        twin = hold_course_twin(nw, resolved_seed)
        engine_stamp = {
            "generator_id": ed.generator_id,
            # the resolved VERSION, not the family — so a RunRecord always
            # says which engine produced its numbers (schema: "Exact trained
            # version is resolved and pinned at run time")
            "generator_version": TOY_ENGINE_VERSION,
        }
    else:
        # su-gen-01: generated worlds run through the adapter and stamp the
        # generator + campaign vintage that actually produced the numbers.
        from ah.port.adapter import gen_hold_course_twin, gen_lineage, run_gen_ensemble

        ensemble = run_gen_ensemble(nw, resolved_paths, base_seed=resolved_seed)
        twin = gen_hold_course_twin(nw, resolved_seed)
        engine_stamp = gen_lineage(nw)
    digest = digest_ensemble(ensemble)

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
            **engine_stamp,
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


@app.command("inspect")
def inspect_cmd(
    ctx: typer.Context,
    run_id: str | None = typer.Argument(None),
    out: Path | None = typer.Option(None, "--out", help="Output HTML path (default <run_id>.html)"),
) -> None:
    """Render a RunRecord's static figure page (wp5-02; regenerates + verifies)."""
    from ah.inspect import render_inspect_page

    conn = _db(ctx)
    rid = run_id or _latest_run(conn)
    page = render_inspect_page(conn, rid)
    target = out if out is not None else Path(f"{rid}.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8", newline="\n")
    typer.echo(str(target))


@app.command("bundle")
def bundle_cmd(
    ctx: typer.Context,
    run_id: str | None = typer.Argument(None),
    out: Path | None = typer.Option(None, "--out", help="Output path (default <run_id>.bundle.gz)"),
) -> None:
    """Build the world bundle for a RunRecord (su-eng-01; DN-3 W2 contract)."""
    from ah.bundle import build_bundle, write_bundle

    conn = _db(ctx)
    rid = run_id or _latest_run(conn)
    doc = build_bundle(conn, rid)
    target = out if out is not None else Path(f"{rid}.bundle.gz")
    size = write_bundle(doc, target)
    typer.echo(f"{target} ({size} bytes compressed)")


@app.command("credibility")
def credibility_cmd(
    ctx: typer.Context,
    run_ids: list[str] = typer.Argument(None, help="RunRecord ids (default: the latest run)"),
    preset: list[str] = typer.Option(
        [], "--preset", help="Also report a preset by name, built fresh (repeatable)"
    ),
    paths: int = typer.Option(400, "--paths", help="Ensemble size for the statistics"),
    seed: int = typer.Option(771204, "--seed", help="Base seed for preset-built worlds"),
    out: Path | None = typer.Option(
        None, "--out", help="Output HTML path (default credibility.html)"
    ),
) -> None:
    """Walk a set of worlds' numbers and flag what is not credible (admin).

    Reports every named run plus every named preset. Nothing is written to the
    store, nothing is scored, and a flag never fails: the page is for a human
    to read before a world reaches a player.
    """
    from ah.credibility import build_report, render_credibility_page
    from ah.programme import build_programme_report

    conn = _db(ctx)
    reports = []
    programme = []

    ids = list(run_ids or [])
    if not ids and not preset:
        ids = [_latest_run(conn)]
    for rid in ids:
        rec = run_store.get_run_record(conn, rid)
        if rec is None:
            raise typer.BadParameter(f"no run with id {rid}")
        world_doc = worlds_store.get_world(conn, rec["world_id"])
        if world_doc is None:
            raise typer.BadParameter(f"run {rid} references missing world {rec['world_id']}")
        ws = WorldSpec.model_validate(world_doc)
        narrative = world_doc.get("narrative") or {}
        world = project_numeric(ws)
        title = f"{narrative.get('title') or rec['world_id']} - run {rid[:8]}"
        reports.append(build_report(world, base_seed=rec["seed"], n_paths=paths, title=title))
        programme.append(build_programme_report(world, base_seed=rec["seed"], title=title))

    for name in preset:
        src = PRESETS_DIR / f"{name}.json"
        if not src.exists():
            raise typer.BadParameter(f"no preset named {name}")
        doc = json.loads(src.read_text(encoding="utf-8"))
        ws = WorldSpec.model_validate(doc)
        narrative = doc.get("narrative") or {}
        world = project_numeric(ws)
        title = f"{narrative.get('title') or name} - preset {name}"
        reports.append(build_report(world, base_seed=seed, n_paths=paths, title=title))
        programme.append(build_programme_report(world, base_seed=seed, title=title))

    target = out if out is not None else Path("credibility.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_credibility_page(reports, programme), encoding="utf-8", newline="\n")
    flags = sum(r.flag_count for r in reports)
    typer.echo(f"{target} ({len(reports)} worlds, {flags} flags)")


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
