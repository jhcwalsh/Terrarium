"""``ah data`` CLI (STEP1-DATA-PLAN §WP1.10).

Local/dev commands over the data layer; no cloud dependency. ``refresh`` uses a
provider (a directory of canonical ``<series_id>.csv`` files via ``--fixtures``, or a
no-op when offline). The scheduled GitHub Actions call the same orchestration.
"""

from datetime import UTC, datetime
from pathlib import Path

import typer

from ah.data.catalog import Catalog
from ah.data.episode import build_episode, episode_years
from ah.data.intake import ingest_file, parse_intake_filename, to_series_frames, validate_file
from ah.data.manifest import requirements
from ah.data.refresh import (
    Provider,
    apply_intake_frames,
    connector_provider,
    csv_dir_provider,
    refresh,
)
from ah.data.reports import generate_data_status_md
from ah.data.schemas import SCHEMAS, get_schema

data_app = typer.Typer(
    help="Data layer: refresh, status, asof, episode, intake.", no_args_is_help=True
)
intake_app = typer.Typer(help="Manual intake.", no_args_is_help=True)
data_app.add_typer(intake_app, name="intake")

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = _REPO_ROOT / "data"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _catalog(data_root: Path) -> Catalog:
    data_root.mkdir(parents=True, exist_ok=True)
    return Catalog(data_root)


def _live_provider() -> Provider:  # pragma: no cover - network
    from ah.data.connectors.bis import BisConnector
    from ah.data.connectors.fred import FredConnector
    from ah.data.connectors.french import FrenchConnector
    from ah.data.connectors.jst import JstConnector
    from ah.data.connectors.shiller import ShillerConnector
    from ah.data.connectors.treasury_hqm import TreasuryHqmConnector

    return connector_provider(
        {
            "fred": FredConnector(),
            "french": FrenchConnector(),
            "shiller": ShillerConnector(),
            "jst": JstConnector(),
            "bis": BisConnector(),
            "treasury_hqm": TreasuryHqmConnector(),
        }
    )


@data_app.command("refresh")
def data_refresh(
    fixtures: Path | None = typer.Option(None, "--fixtures", help="Dir of <series_id>.csv."),
    vintage: str | None = typer.Option(None, "--vintage", help="Vintage id (default: today)."),
    source: str | None = typer.Option(None, "--source", help="Restrict to one source."),
    asof: str | None = typer.Option(None, "--asof", help="As-of date (default: today)."),
    live: bool = typer.Option(False, "--live", help="Fetch real data via source connectors."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    data_root: Path = typer.Option(DEFAULT_DATA_ROOT, "--data-root"),
) -> None:
    """Plan -> fetch/parse -> QC -> vintage commit/quarantine -> reports."""
    cat = _catalog(data_root)
    reqs = requirements()
    asof = asof or _today()
    if live:
        provider = _live_provider()
    elif fixtures:
        provider = csv_dir_provider(fixtures)
    else:
        provider = lambda _req: None  # noqa: E731 - offline no-op
    result = refresh(
        cat,
        reqs,
        vintage=vintage or _today(),
        asof=asof,
        provider=provider,
        created_at=_now(),
        sources=[source] if source else None,
        dry_run=dry_run,
    )
    if result.dry_run:
        typer.echo(f"[dry-run] {len(result.planned)} series due: {result.planned}")
        return
    if result.already_exists:
        typer.echo(f"vintage {result.vintage} already exists -- no-op (idempotent).")
        return
    if result.gaps_md:
        (data_root / "GAPS.md").write_text(result.gaps_md, encoding="utf-8")
    if result.status_md:
        (data_root / "DATA-STATUS.md").write_text(result.status_md, encoding="utf-8")
    status = "QUARANTINED" if result.quarantined else "committed"
    typer.echo(
        f"vintage {result.vintage} {status}: wrote {len(result.written)} series, "
        f"carried forward {len(result.carried_forward)}."
    )
    if result.warnings:
        typer.echo(f"  skipped {len(result.warnings)} series (fetch/parse failed):")
        for w in result.warnings:
            typer.echo(f"    - {w}")
    if result.quarantined and result.qc is not None:
        for f in result.qc.enforce_failures:
            typer.echo(f"  QC enforce: {f.series_id} {f.rule} ({f.detail})")
        raise typer.Exit(1)


@data_app.command("status")
def data_status(data_root: Path = typer.Option(DEFAULT_DATA_ROOT, "--data-root")) -> None:
    """Print DATA-STATUS.md for the current vintage."""
    cat = _catalog(data_root)
    typer.echo(generate_data_status_md(cat, requirements(), asof=_today()))


@data_app.command("asof")
def data_asof(
    date: str = typer.Argument(...),
    data_root: Path = typer.Option(DEFAULT_DATA_ROOT, "--data-root"),
) -> None:
    """Show which vintage was current as of DATE."""
    cat = _catalog(data_root)
    vintage = cat.asof(date)
    typer.echo(vintage or "(no vintage current as of that date)")


@data_app.command("episode")
def data_episode(
    year: int = typer.Argument(...),
    data_root: Path = typer.Option(DEFAULT_DATA_ROOT, "--data-root"),
) -> None:
    """Emit the episode pack brief for YEAR."""
    if year not in episode_years():
        raise typer.BadParameter(f"unknown episode {year}; known: {episode_years()}")
    cat = _catalog(data_root)
    series = [r.series_id for r in requirements() if r.source in ("fred", "albourne")]
    pack = build_episode(cat, year, series)
    typer.echo(pack.brief)


@intake_app.command("validate")
def intake_validate(
    file: Path = typer.Argument(...),
    schema: str | None = typer.Option(None, "--schema", help="Schema name (default: infer)."),
    data_root: Path = typer.Option(DEFAULT_DATA_ROOT, "--data-root"),
) -> None:
    """Validate a manual-intake drop file and print the report."""
    name = schema
    if name is None:  # infer from filename group
        group, _ = parse_intake_filename(file.name)
        name = next((s for s in SCHEMAS if group.replace("-", "_") in s), None)
    resolved = get_schema(name) if name else None
    if resolved is None:
        raise typer.BadParameter(f"could not resolve a schema (got '{name}'); pass --schema")
    cat = _catalog(data_root)
    result = ingest_file(cat, file, resolved, received_at=_now())
    typer.echo(result.report)
    if not result.accepted:
        raise typer.Exit(1)


@intake_app.command("apply")
def intake_apply(
    file: Path = typer.Argument(...),
    vintage: str = typer.Option(..., "--vintage", help="Vintage id to write (e.g. 2026-08-01.1)."),
    schema: str | None = typer.Option(None, "--schema", help="Schema name (default: infer)."),
    data_root: Path = typer.Option(DEFAULT_DATA_ROOT, "--data-root"),
) -> None:
    """Validate a drop AND apply it: write the vintage, run QC, advance on pass.

    The manual-intake last mile (WP2R.2). Rejected drops apply nothing; an
    accepted drop that fails QC leaves the vintage quarantined with the current
    pointer unmoved - same discipline as `ah data refresh`.
    """
    name = schema
    if name is None:
        group, _ = parse_intake_filename(file.name)
        name = next((s for s in SCHEMAS if group.replace("-", "_") in s), None)
    resolved = get_schema(name) if name else None
    if resolved is None:
        raise typer.BadParameter(f"could not resolve a schema (got '{name}'); pass --schema")
    cat = _catalog(data_root)
    result = ingest_file(cat, file, resolved, received_at=_now())
    typer.echo(result.report)
    if not result.accepted or result.frame is None:
        raise typer.Exit(1)
    frames = to_series_frames(resolved, result.frame)
    outcome = apply_intake_frames(
        cat, requirements(), frames=frames, vintage=vintage, asof=_today(), created_at=_now()
    )
    if outcome.already_exists:
        typer.echo(f"vintage {vintage} already exists; nothing applied")
        raise typer.Exit(1)
    status = "QUARANTINED" if outcome.quarantined else "current"
    typer.echo(
        f"vintage {vintage} {status}: wrote {len(outcome.written)} series, "
        f"carried forward {len(outcome.carried_forward)}."
    )
    if outcome.quarantined and outcome.qc is not None:
        for f in outcome.qc.enforce_failures:
            typer.echo(f"  QC enforce: {f.series_id} {f.rule} ({f.detail})")
        raise typer.Exit(1)


# convenience for tests / programmatic validation without a catalog
__all__ = ["data_app", "validate_file"]
