"""The compiler contract: scenario text in, a WorldSpec-shaped dict out.

Two implementations satisfy it: :class:`~ah.compiler.fixture_adapter.FixtureCompiler`
(offline, used everywhere in tests) and
:class:`~ah.compiler.anthropic_adapter.AnthropicCompiler` (live, CLI ``--live`` only,
never imported by tests). The returned dict is *raw*: it may violate bounds or omit
fields — the validator (WP0.3) clamps or rejects it downstream.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class CompileError(ValueError):
    """Raised when compiler output cannot be turned into a JSON object."""


@runtime_checkable
class CompilerProtocol(Protocol):
    def compile(self, scenario_text: str) -> dict[str, Any]:
        """Compile a scenario into a (possibly raw) WorldSpec dict."""
        ...
