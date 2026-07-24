"""``ah exp`` CLI — inspect local experiments (STEP2 §1)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import typer

from ah.experiment import ExperimentStore

exp_app = typer.Typer(help="Experiment tracking: list, show, diff.", no_args_is_help=True)
_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "experiments"


def _store(root: Path) -> ExperimentStore:
    return ExperimentStore(root)


@exp_app.command("list")
def exp_list(root: Path = typer.Option(_DEFAULT_ROOT, "--root")) -> None:
    """List experiments with their config hash, seed and git SHA."""
    store = _store(root)
    for exp_id in store.list():
        meta, _ = store.load(exp_id)
        typer.echo(
            f"{exp_id:24} {meta.config_hash} seed={meta.seed} git={meta.git_sha} v={meta.vintage_id}"
        )


@exp_app.command("show")
def exp_show(exp_id: str, root: Path = typer.Option(_DEFAULT_ROOT, "--root")) -> None:
    """Print an experiment's metadata and config."""
    store = _store(root)
    if not store.exists(exp_id):
        raise typer.BadParameter(f"no experiment '{exp_id}'")
    meta, config = store.load(exp_id)
    typer.echo(
        json.dumps({"meta": dataclasses.asdict(meta), "config": config}, indent=2, sort_keys=True)
    )


@exp_app.command("diff")
def exp_diff(exp_a: str, exp_b: str, root: Path = typer.Option(_DEFAULT_ROOT, "--root")) -> None:
    """Show config differences between two experiments."""
    store = _store(root)
    diff = store.diff(exp_a, exp_b)
    if not diff:
        typer.echo("configs identical")
        return
    for key, (va, vb) in diff.items():
        typer.echo(f"{key}: {va!r} -> {vb!r}")
