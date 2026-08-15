"""Regenerate the app's committed CioView fixtures (cio-02, plus cio-03's
decisions-bearing fixture).

The app's renderer tests consume these; a Python test asserts regeneration
reproduces the committed bytes, so the fixture can never drift from the
builder. Deterministic: stagflation preset, its own base_seed, revealed=60,
forecast_quarters=4.

cio-03 Task 6: cio-02's two fixtures are built with ``{}`` decisions, so
``performance.benchmark`` (the twin) is identical to ``performance.total``
and every Excess cell the dashboard prints is a degenerate ``+0.0`` — the
one number that argues the product's case is pinned by nothing. A third
fixture, ``cio-sample.decided.json``, plays a small deterministic decision
map at real decision months (``ah.core.institution.decision_months``) so
total genuinely diverges from the twin.

cio-04: stagflation is a ``toy-v0`` world, so the fixtures now carry the
inherited decade (``prehistory=True``, passed explicitly here to mirror the
endpoint's explicit flag in ``ah/serve.py`` rather than relying on the
builder's default) — the fixtures are substantially larger as a result.
"""

from __future__ import annotations

import json
from pathlib import Path

from ah.cioview import build_cio_view
from ah.core.engine import run_path
from ah.core.institution import decision_months
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
OUT = ROOT / "app" / "fixtures"

REVEALED_MONTHS = 60
FORECAST_QUARTERS = 4


def build(plane: str, decisions: dict[int, str] | None = None) -> str:
    doc = json.loads((PRESETS / "stagflation.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    paths = run_path(nw, doc["engine_defaults"]["base_seed"])
    view = build_cio_view(
        paths,
        decisions or {},
        run_id="fixture-stagflation",
        seed=doc["engine_defaults"]["base_seed"],
        world_title="Stagflation",
        world_version="fixture",
        alpha_version="fixture",
        start_targets=None,
        plane=plane,
        revealed_months=REVEALED_MONTHS,
        forecast_quarters=FORECAST_QUARTERS,
        prehistory=True,
    )
    return json.dumps(view, sort_keys=True, indent=1) + "\n"


def _decided_map() -> dict[int, str]:
    """The first two annual decision points inside the frozen horizon
    (``revealed_months`` + ``forecast_quarters`` * 3 months, the same
    horizon ``build_cio_view`` freezes the paths to) take derisk / leanin
    instead of hold. Both land inside the revealed window (months 11 and
    23, well under the 60-month/20-quarter cut), so they show up in
    performance.total rather than only in the unreached forecast tail.
    """
    nm = REVEALED_MONTHS + FORECAST_QUARTERS * 3
    months = decision_months(nm)
    assert len(months) >= 2, (
        f"need at least two decision months inside a {nm}-month horizon to "
        f"build a derisk/leanin map, got {months}"
    )
    first, second = months[0], months[1]
    return {first: "derisk", second: "leanin"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for plane in ("reported", "true"):
        target = OUT / f"cio-sample.{plane}.json"
        target.write_text(build(plane), encoding="utf-8", newline="\n")
        print(f"wrote {target}")
    target = OUT / "cio-sample.decided.json"
    target.write_text(build("reported", _decided_map()), encoding="utf-8", newline="\n")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
