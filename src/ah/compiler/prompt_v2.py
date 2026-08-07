"""Compiler prompt library v2: the field contract is DERIVED from the vendored
schema at import time, so prompt and ``schemas/`` cannot drift apart (v1
drifted: it was a hand-written field list against a superseded schema
generation, and by 2026-08-06 live output carried 38 extra keys and missed 6
required fields).

Pure strings + builders — no network, safe to import in tests. The version
string is recorded into ``provenance.source.compiler_prompt_version`` by
``postprocess.stamp_envelope``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPT_VERSION = "compile-world-v2.0"

#: The six substantive blocks the model owns. The envelope (world_id,
#: provenance, status, spec_version, extensions) is stamped by the system in
#: ``postprocess.stamp_envelope`` — the model is asked for economics, not
#: identity.
MODEL_OWNED = (
    "narrative",
    "horizon",
    "regimes",
    "factor_conditions",
    "structural",
    "engine_defaults",
)

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "worldspec-v1.2.schema.json"
_EXAMPLE_PATH = _SCHEMA_PATH.parent / "example-long-stagflation.worldspec.json"


def _field_line(name: str, spec: dict[str, Any], required: bool, indent: int) -> str:
    bits = [str(spec.get("type", "object"))]
    if "enum" in spec:
        bits.append("one of " + ", ".join(map(str, spec["enum"])))
    if "minimum" in spec or "maximum" in spec:
        bits.append(f"range [{spec.get('minimum', '-inf')}, {spec.get('maximum', 'inf')}]")
    if "minItems" in spec or "maxItems" in spec:
        bits.append(f"items {spec.get('minItems', 0)}..{spec.get('maxItems', 'n')}")
    flag = "REQUIRED" if required else "optional"
    return f"{'  ' * indent}- {name} ({flag}: {'; '.join(bits)})"


def _walk(lines: list[str], name: str, spec: dict[str, Any], required: bool, indent: int) -> None:
    """Render a field and recurse into nested objects (and array items).

    Depth-limited to 3 levels below the block. The first live run against a
    one-level digest failed exactly here: the model wrote
    ``structural.infrastructure.inflation_linkage: "strong"`` because the
    nested numeric constraint was never shown to it.
    """
    lines.append(_field_line(name, spec, required, indent))
    if indent >= 4:
        return
    inner = spec.get("items", spec) if spec.get("type") == "array" else spec
    req = set(inner.get("required", []))
    for fname, fspec in sorted(inner.get("properties", {}).items()):
        _walk(lines, fname, fspec, fname in req, indent + 1)


def schema_digest() -> str:
    """A compact, deterministic text rendering of the six model-owned blocks."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    lines: list[str] = []
    for block in MODEL_OWNED:
        spec = schema["properties"][block]
        req = set(spec.get("required", []))
        lines.append(f"{block}:")
        inner = spec.get("items", spec) if spec.get("type") == "array" else spec
        inner_req = req | set(inner.get("required", []))
        for fname, fspec in sorted(inner.get("properties", {}).items()):
            _walk(lines, fname, fspec, fname in inner_req, 1)
    return "\n".join(lines)


def _example_blocks() -> str:
    doc = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    return json.dumps({k: doc[k] for k in MODEL_OWNED if k in doc}, indent=1)


SYSTEM_PROMPT = f"""\
You compile a user's counterfactual macro/market scenario into WorldSpec JSON
(vendored schema worldspec-v1.2).

Output a JSON object with EXACTLY these six top-level keys and no others:
{", ".join(MODEL_OWNED)}. The platform stamps identity and origin metadata
itself; do not output any other top-level key.

Rules:
- Output JSON ONLY. No prose, no Markdown, no code fences.
- The engine reads only the structured parameters; narrative must agree with them.
- Set only the factor_conditions the scenario implies; omit the rest.
- FICTIONAL ENTITIES ONLY: never name a real firm, fund, or person.
- Keep every value inside the bounds below; do not rely on downstream clamping.

Field contract (derived from the vendored schema):
{schema_digest()}

Canonical example (the six blocks of the vendored long-stagflation world):
{_example_blocks()}
"""


def build_messages(scenario_text: str) -> list[dict[str, str]]:
    """Return the messages payload for the Messages API (user turn only)."""
    return [
        {
            "role": "user",
            "content": (
                f"Compile this scenario into the six-block JSON document:\n\n{scenario_text}"
            ),
        }
    ]
