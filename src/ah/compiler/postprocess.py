"""Turn raw model text into a JSON object: strip fences, extract the outermost
``{...}``, parse (STEP0-PLAN §WP0.7). Kept separate so it is testable without any
network or model dependency.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from ah.compiler.interface import CompileError

_FENCE = "```"

#: The WorldSpec version this compiler emits against.
SPEC_VERSION = "1.2.0"

#: Envelope keys the SYSTEM owns and the model must never supply. Each is a fact
#: the platform knows and a model can only guess at: a compiler that invents its
#: own ``world_id`` is a compiler that can collide with a stored world, and one
#: that writes its own ``provenance`` is asserting its own trustworthiness.
#: Measured 2026-08-06 against `claude-sonnet-4-6`: the live compiler returned
#: `meta` and `schema_version` and omitted all five of these, so every live build
#: failed at pydantic construction while all 50 offline fixtures passed — the
#: fixtures were generated against an older envelope and could not catch it.
_SYSTEM_OWNED = ("world_id", "provenance", "status", "spec_version", "extensions")

#: Envelope keys the model tends to invent instead. Dropped, not merged: the
#: contract forbids extras, and silently keeping a key the schema rejects would
#: only move the failure later.
_MODEL_INVENTED = ("meta", "schema_version")


def strip_fences(text: str) -> str:
    """Remove a leading/trailing Markdown code fence (```json ... ```), if present."""
    s = text.strip()
    if s.startswith(_FENCE):
        s = s[len(_FENCE) :]
        # optional language tag on the first line
        newline = s.find("\n")
        if newline != -1 and s[:newline].strip().isalpha():
            s = s[newline + 1 :]
        if s.rstrip().endswith(_FENCE):
            s = s.rstrip()[: -len(_FENCE)]
    return s.strip()


def extract_json(text: str) -> dict[str, Any]:
    """Extract and parse the outermost JSON object from model text."""
    s = strip_fences(text)
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise CompileError("no JSON object found in compiler output")
    blob = s[start : end + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise CompileError(f"compiler output is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise CompileError("compiler output JSON is not an object")
    return obj


def stamp_envelope(
    obj: dict[str, Any],
    *,
    scenario_text: str,
    created_at: str,
    compiler_model: str,
    prompt_version: str,
    world_id: str | None = None,
) -> dict[str, Any]:
    """Fill the envelope the SYSTEM owns, and drop the one the model invents.

    The model is asked for economics, not for identity. It supplies the six
    substantive blocks -- ``engine_defaults``, ``factor_conditions``,
    ``horizon``, ``narrative``, ``regimes``, ``structural`` -- and this function
    supplies ``world_id``, ``provenance``, ``status``, ``spec_version`` and
    ``extensions``, none of which a model is in a position to know.

    ``created_at`` is a caller argument rather than a clock read, so the whole
    compile path stays testable and the repo's no-time-based-defaults rule holds
    here as everywhere else.

    Returns a new dict; the input is not mutated.
    """
    out = {k: v for k, v in obj.items() if k not in _MODEL_INVENTED}
    out["world_id"] = world_id or str(uuid.uuid4())
    out["spec_version"] = SPEC_VERSION
    out["status"] = "draft"  # the validator promotes it to `validated`
    out.setdefault("extensions", {})
    out["provenance"] = {
        "created_at": created_at,
        "author": "compiler",
        "source": {
            "kind": "compiler",
            "user_scenario_text": scenario_text[:2000],
            "compiler_model": compiler_model,
            "compiler_prompt_version": prompt_version,
        },
    }
    return out
