"""WP0.2 acceptance: the narrative-blindness guarantee, enforced structurally.

The engine consumes a ``NumericWorld`` that has no ``narrative`` attribute, so a
narrative dependency is a construction error, not a review miss. A source scan of
the engine/institution modules is the belt-and-suspenders guard for later WPs.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from ah.core.loader import load_worldspec
from ah.core.numericworld import NumericWorld, project_numeric

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "schemas" / "example-long-stagflation.worldspec.json"
CORE = ROOT / "src" / "ah" / "core"

# The two modules that STEP0-PLAN.md §WP0.2 forbids from reading `narrative`.
ENGINE_MODULES = ("engine.py", "institution.py")


def test_numericworld_has_no_narrative_field() -> None:
    fields = {f.name for f in dataclasses.fields(NumericWorld)}
    assert "narrative" not in fields
    assert "provenance" not in fields
    # positive: it carries the engine-visible fields
    assert {"horizon", "regimes", "factor_conditions", "structural"} <= fields


def test_projection_omits_narrative_at_runtime() -> None:
    ws = load_worldspec(EXAMPLE_PATH)
    nw = project_numeric(ws)
    assert not hasattr(nw, "narrative")
    assert nw.world_id == ws.world_id
    assert nw.horizon == ws.horizon


def test_engine_modules_never_reference_narrative() -> None:
    """If/when engine.py or institution.py exist, they must not mention narrative."""
    for name in ENGINE_MODULES:
        path = CORE / name
        if not path.exists():
            continue  # arrives in WP0.4 / WP0.5; guard activates automatically
        source = path.read_text(encoding="utf-8")
        assert "narrative" not in source, (
            f"{name} references 'narrative' — the engine must be narrative-blind "
            "(consume NumericWorld, never WorldSpec.narrative)."
        )


def test_example_json_actually_has_narrative() -> None:
    """Sanity: the guard is meaningful because the source WorldSpec does carry it."""
    doc = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert "narrative" in doc and doc["narrative"]["title"]
