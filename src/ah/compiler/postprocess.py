"""Turn raw model text into a JSON object: strip fences, extract the outermost
``{...}``, parse (STEP0-PLAN §WP0.7). Kept separate so it is testable without any
network or model dependency.
"""

from __future__ import annotations

import json
from typing import Any

from ah.compiler.interface import CompileError

_FENCE = "```"


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
