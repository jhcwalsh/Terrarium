"""``ah`` command-line interface.

WP0.1 provides only the app object and a ``--version`` flag so the entry point
resolves and the loop can be proved end-to-end later. The full command surface
(``world``, ``run``, ``replay``, ``verify``, ``battery``, ``chronicle``) is built
in WP0.9; those subcommands hang off this same app.
"""

from __future__ import annotations

import typer

from ah import __version__

app = typer.Typer(
    help="Alternate Histories platform CLI.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", help="Show the platform version and exit."),
) -> None:
    """Root command group. Global options live here; subcommands arrive in WP0.9."""
    if version:
        typer.echo(__version__)
        raise typer.Exit()


if __name__ == "__main__":  # pragma: no cover
    app()
