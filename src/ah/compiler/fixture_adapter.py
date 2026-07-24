"""Offline compiler: replay a checked-in fixture for a scenario (STEP0-PLAN §WP0.7).

Scenario text maps deterministically to a slug and a ``fixtures/compiler/{slug}.json``
file. This is the only compiler used in tests (no network).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ah.compiler.interface import CompileError

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(scenario_text: str) -> str:
    """Deterministic slug for a scenario: lowercase, non-alphanumerics -> hyphen."""
    return _SLUG_RE.sub("-", scenario_text.strip().lower()).strip("-")


class FixtureCompiler:
    """Return the pre-compiled world JSON for a scenario, by slug lookup."""

    def __init__(self, fixtures_dir: str | Path) -> None:
        self.dir = Path(fixtures_dir)

    def compile(self, scenario_text: str) -> dict[str, Any]:
        path = self.dir / f"{slugify(scenario_text)}.json"
        if not path.exists():
            raise CompileError(f"no fixture for scenario (looked for {path.name})")
        return json.loads(path.read_text(encoding="utf-8"))
