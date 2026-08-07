"""Live compiler over the Anthropic Messages API (STEP0-PLAN §WP0.7).

Exercised ONLY via the CLI ``--live`` flag and the build console; **never
imported by tests** and never run in CI (pytest-socket blocks the network). The
``anthropic`` SDK is imported lazily inside ``fetch_raw_text`` so importing
this module has no side effects.

The model id is the Step-0 pinned value from the plan and the canonical example's
``compiler_model``. Bump it deliberately (and re-run the fixture regression) when
going live against a newer model.
"""

from __future__ import annotations

from typing import Any, cast

from ah.compiler.postprocess import extract_json, stamp_envelope
from ah.compiler.prompt_v2 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages

COMPILER_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def fetch_raw_text(model: str, scenario_text: str) -> str:  # pragma: no cover - live only
    """One live model call; returns the raw text before any JSON extraction.

    Split out of ``AnthropicCompiler.compile`` so the build console can show
    the raw model text as its own pipeline stage.
    """
    import anthropic  # lazy: keep import off the test/CI path

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=cast("Any", build_messages(scenario_text)),
    )
    return "".join(
        getattr(block, "text", "")
        for block in message.content
        if getattr(block, "type", "") == "text"
    )


class AnthropicCompiler:
    """Compile scenarios with a live model call. Requires ANTHROPIC_API_KEY."""

    def __init__(self, model: str = COMPILER_MODEL) -> None:
        self.model = model
        self.prompt_version = PROMPT_VERSION

    def compile(
        self, scenario_text: str, *, created_at: str = "1970-01-01T00:00:00Z"
    ) -> dict[str, Any]:  # pragma: no cover - live only
        """Compile a scenario, then stamp the envelope the system owns.

        ``created_at`` is a caller argument, never a clock read, so this path
        obeys the repo's no-time-based-defaults rule like every other. The CLI
        passes the same timestamp it stamps validation with.
        """
        return stamp_envelope(
            extract_json(fetch_raw_text(self.model, scenario_text)),
            scenario_text=scenario_text,
            created_at=created_at,
            compiler_model=self.model,
            prompt_version=self.prompt_version,
        )
