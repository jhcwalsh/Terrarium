"""Regenerate the app's committed CioView fixtures (cio-02).

The app's renderer tests consume these; a Python test asserts regeneration
reproduces the committed bytes, so the fixture can never drift from the
builder. Deterministic: stagflation preset, its own base_seed, revealed=60,
forecast_quarters=4.
"""

from __future__ import annotations

import json
from pathlib import Path

from ah.cioview import build_cio_view
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
OUT = ROOT / "app" / "fixtures"


def build(plane: str) -> str:
    doc = json.loads((PRESETS / "stagflation.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    paths = run_path(nw, doc["engine_defaults"]["base_seed"])
    view = build_cio_view(
        paths,
        {},
        run_id="fixture-stagflation",
        seed=doc["engine_defaults"]["base_seed"],
        world_title="Stagflation",
        world_version="fixture",
        alpha_version="fixture",
        start_targets=None,
        plane=plane,
        revealed_months=60,
        forecast_quarters=4,
    )
    return json.dumps(view, sort_keys=True, indent=1) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for plane in ("reported", "true"):
        target = OUT / f"cio-sample.{plane}.json"
        target.write_text(build(plane), encoding="utf-8", newline="\n")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
