"""Compiler prompt library, version ``compile-world-v1.0`` (STEP0-PLAN §WP0.7).

Pure strings + a builder — no network, safe to import in tests. The live adapter
consumes these; the version string is recorded into
``provenance.source.compiler_prompt_version``.
"""

from __future__ import annotations

PROMPT_VERSION = "compile-world-v1.0"

SYSTEM_PROMPT = """\
You compile a user's counterfactual macro/market scenario into a single WorldSpec
JSON document (schema version 1.0.x). Rules:

- Output JSON ONLY. No prose, no Markdown, no code fences — just the object.
- Populate narrative (title, tagline, summary, lesson, 3-10 dispatches) AND the
  structured parameters (horizon, regimes, factor_conditions, structural,
  engine_defaults) so they agree. The engine reads only the structured parameters.
- Set only the factor_conditions the scenario actually implies; omit the rest
  (an omitted condition means "let the generator decide").
- FICTIONAL ENTITIES ONLY: never name a real firm, fund, or person in the
  narrative. Reference real institutions only generically ("the central bank").
- Keep every value within the schema's bounds; the validator will clamp overflows
  and record them, but you should not rely on that.
"""


def build_messages(scenario_text: str) -> list[dict[str, str]]:
    """Return the messages payload for the Messages API (user turn only)."""
    return [
        {
            "role": "user",
            "content": (
                f"Compile this scenario into a WorldSpec JSON document:\n\n{scenario_text}"
            ),
        }
    ]
