"""Compile-to-world pipeline: raw dict -> validate (clamp) -> construct WorldSpec.

Shared by the offline regression harness (WP0.7) and the CLI ``world build`` path
(WP0.9). A world is *rejected* if the validator returns a blocking finding or if the
clamped document still fails schema/pydantic construction (e.g., a missing field).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ah.core.validator import ValidationResult, validate
from ah.core.worldspec import WorldSpec


@dataclass
class CompileOutcome:
    raw: dict[str, Any]
    result: ValidationResult
    world: WorldSpec | None
    rejected: bool
    reject_reason: str | None


def process(raw: dict[str, Any]) -> CompileOutcome:
    """Validate (and clamp) a raw compiled world, then try to construct a WorldSpec."""
    result = validate(raw)
    if result.blocking:
        reason = "; ".join(f"{f.rule}: {f.message}" for f in result.blocking)
        return CompileOutcome(raw, result, None, True, reason)
    try:
        world = WorldSpec.model_validate(result.clamped_world)
    except ValidationError as exc:
        return CompileOutcome(raw, result, None, True, str(exc))
    return CompileOutcome(raw, result, world, False, None)
