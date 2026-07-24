"""Live compiler over the Anthropic Messages API (STEP0-PLAN §WP0.7).

Exercised ONLY via the CLI ``--live`` flag; **never imported by tests** and never
run in CI (pytest-socket blocks the network). The ``anthropic`` SDK is imported
lazily inside ``compile`` so importing this module has no side effects.

The model id is the Step-0 pinned value from the plan and the canonical example's
``compiler_model``. Bump it deliberately (and re-run the fixture regression) when
going live against a newer model.
"""

from __future__ import annotations

from typing import Any, cast

from ah.compiler.postprocess import extract_json
from ah.compiler.prompt_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages

COMPILER_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


class AnthropicCompiler:
    """Compile scenarios with a live model call. Requires ANTHROPIC_API_KEY."""

    def __init__(self, model: str = COMPILER_MODEL) -> None:
        self.model = model
        self.prompt_version = PROMPT_VERSION

    def compile(self, scenario_text: str) -> dict[str, Any]:  # pragma: no cover - live only
        import anthropic  # lazy: keep import off the test/CI path

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.model,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=cast("Any", build_messages(scenario_text)),
        )
        text = "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", "") == "text"
        )
        return extract_json(text)
