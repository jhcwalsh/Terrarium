"""cio-04: the inherited decade that renders before a world's month 0.

Display-only by ruling (see the plan and DN-8's O-1 resolution): the opening
book is unchanged, and the pre-history is pinned to terminate at it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.validator import validate

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _doc(name: str) -> dict[str, Any]:
    return json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))


def test_prehistory_preset_passes_the_v_rules():
    """DN-8 O-1's stated cost of option A: an unvalidated pre-history would be
    an unvalidated artefact sitting inside a validated product.

    The interface this WP promises (task-1-brief.md) is a document that
    "loads, validates (V1-V12), and projects" -- so all three are exercised
    here rather than just the V-rules: ``load_worldspec`` runs the JSON
    Schema and pydantic construction, ``validate`` runs V1-V12 against the
    raw document (its real signature takes ``dict``, not a ``WorldSpec``),
    and ``project_numeric`` proves the loaded spec turns into an engine-ready
    ``NumericWorld``.
    """
    doc = _doc("prehistory")
    spec = load_worldspec(doc)  # schema + pydantic: proves it *loads*
    report = validate(doc)  # V1-V12 against the raw document
    assert report.ok, [f.message for f in report.blocking]
    project_numeric(spec)  # proves it *projects*


def test_prehistory_preset_is_a_decade_and_is_calm():
    doc = _doc("prehistory")
    assert doc["horizon"]["quarters"] == 40
    # no crisis windows: the inherited past is unremarkable by construction,
    # so the decade the player actually plays is the one with the weather in
    # it. Crisis windows live at factor_conditions.crisis_windows in this
    # schema (there is no top-level "stress" field) -- checked there so the
    # assertion is actually load-bearing rather than vacuously true.
    assert not doc.get("factor_conditions", {}).get("crisis_windows"), (
        "the inherited decade carries no crisis"
    )
