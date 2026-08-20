"""Regenerate the committed app/fixtures bundles (su-eng-01 / su-gen-02).

Two fixtures, both deterministic (same presets, seeds, and path counts):

- ``toy.bundle.gz`` — the stagflation preset at its own defaults (1000 paths),
  the bundle both suites verify for the toy contract.
- ``gen.bundle.gz`` — the stagflation_1974 GENERATED world at 100 paths: the
  su-gen-02 fixture carrying factors + credibility sections. Building it
  requires the local vintage store (OD-4); CI only ever VERIFIES the
  committed bytes, never rebuilds.

Run whenever the engine, the adapter, or the bundle contract changes:

    uv run python scripts/gen_bundle_fixtures.py

NEITHER fixture is byte-reproducible (chosen-PE release review, 2026-08-20):
every run mints a fresh ``meta.run_id``/``created_at`` and the chronicle
carries wall-clock timestamps, so two builds of the same code differ in those
fields while every tape byte is identical. "Regenerate and diff the .gz" is
therefore NOT a stability test -- it fails on identical code. To check
stability, decompress both and compare the tape content (paths, factors,
credibility sections), ignoring run identity and timestamps; and do not
rewrite the OTHER fixture as a side effect of rebuilding one (this script
always rebuilds both -- restore the untouched plane's committed bytes).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "app" / "fixtures"


def main() -> None:
    from ah.cli import app

    runner = CliRunner()
    # ignore_cleanup_errors: the CLI's sqlite handle outlives the runner on
    # Windows and the temp db can't be unlinked; the OS reaps it later.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Path(tmp) / "fixtures.db"

        def invoke(*args: str) -> str:
            r = runner.invoke(app, ["--db", str(db), *args])
            if r.exit_code != 0:
                raise SystemExit(f"ah {' '.join(args)} failed:\n{r.output}")
            return r.stdout.strip().splitlines()[-1]

        invoke("world", "build", "--preset", "stagflation")
        toy_run = invoke("run")
        invoke("bundle", toy_run, "--out", str(FIXTURES / "toy.bundle.gz"))
        print(f"toy.bundle.gz <- run {toy_run[:8]} (stagflation, preset defaults)")

        invoke("world", "build", "--preset", "stagflation_1974")
        gen_run = invoke("run", "--paths", "100")
        invoke("bundle", gen_run, "--out", str(FIXTURES / "gen.bundle.gz"))
        print(f"gen.bundle.gz <- run {gen_run[:8]} (stagflation_1974, 100 paths)")


if __name__ == "__main__":
    main()
