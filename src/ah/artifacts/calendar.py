"""The artifact calendar (WP4.1) — which types this world emits, and when.

The declaration lives in the WorldSpec at ``extensions.x_temporal_delivery``
— the schema's sanctioned ``x_`` escape hatch, because the vendored
worldspec schema (read-only truth) has no top-level ``temporal_delivery``
block. Engines must ignore unknown extensions per the schema's own text, so
the calendar is structurally invisible to the numeric path. Promotion to a
core block is an owner decision requiring a schema minor bump; flagged in
the WP4.1 record.

Scheduling is pure arithmetic: a world, a horizon, a deterministic list of
slots. Event-triggered artifacts (spread breach, gating) are declared here
with cadence ``event`` but scheduled at runtime by the wire (WP4.6/4.7);
``schedule`` excludes them by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ARTIFACT_TYPES = ("wire_item", "release_page", "statement", "letterhead", "board_pack")
CADENCES = ("monthly", "quarterly", "event")
AUTHOR_TIERS = (1, 2)


class CalendarError(ValueError):
    """A calendar declaration that violates the WP4.1 contract."""


@dataclass(frozen=True)
class CalendarEntry:
    artifact_type: str
    cadence: str
    author_tier: int
    offset_weeks: int = 0  # within-month placement (e.g. board pack T-2 world-weeks)

    def __post_init__(self) -> None:
        if self.artifact_type not in ARTIFACT_TYPES:
            raise CalendarError(f"unknown artifact_type '{self.artifact_type}'")
        if self.cadence not in CADENCES:
            raise CalendarError(f"unknown cadence '{self.cadence}'")
        if self.author_tier not in AUTHOR_TIERS:
            raise CalendarError(f"author_tier must be 1 or 2, got {self.author_tier}")
        if not -4 <= self.offset_weeks <= 4:
            raise CalendarError("offset_weeks must be within [-4, 4]")


@dataclass(frozen=True)
class Slot:
    """One deterministic emission slot: month index (0-based) + type + tier."""

    month: int
    week: int
    artifact_type: str
    author_tier: int


def read_calendar(worldspec_doc: dict[str, Any]) -> list[CalendarEntry]:
    """Parse ``extensions.x_temporal_delivery.artifact_calendar``.

    A world that declares nothing emits nothing — an absent block is an empty
    calendar, not an error. A malformed block raises: silence never swallows
    a typo'd declaration.
    """
    block = worldspec_doc.get("extensions", {}).get("x_temporal_delivery")
    if block is None:
        return []
    if not isinstance(block, dict) or "artifact_calendar" not in block:
        raise CalendarError("x_temporal_delivery must carry an 'artifact_calendar' list")
    entries = []
    for raw in block["artifact_calendar"]:
        unknown = set(raw) - {"artifact_type", "cadence", "author_tier", "offset_weeks"}
        if unknown:
            raise CalendarError(f"unknown calendar entry keys: {sorted(unknown)}")
        entries.append(
            CalendarEntry(
                artifact_type=raw["artifact_type"],
                cadence=raw["cadence"],
                author_tier=int(raw["author_tier"]),
                offset_weeks=int(raw.get("offset_weeks", 0)),
            )
        )
    return entries


def schedule(entries: list[CalendarEntry], horizon_months: int) -> list[Slot]:
    """All calendar-driven slots over the horizon, deterministically ordered.

    Monthly entries fire every month; quarterly entries fire in the third
    month of each quarter (indices 2, 5, 8, ...). ``event`` entries are
    runtime-triggered and never appear here. Order: month, then the entry's
    position in ARTIFACT_TYPES, so identical calendars always schedule
    identically.
    """
    if horizon_months <= 0:
        raise CalendarError("horizon_months must be positive")
    slots: list[Slot] = []
    for month in range(horizon_months):
        for entry in sorted(entries, key=lambda e: ARTIFACT_TYPES.index(e.artifact_type)):
            if entry.cadence == "event":
                continue
            if entry.cadence == "quarterly" and month % 3 != 2:
                continue
            slots.append(
                Slot(
                    month=month,
                    week=entry.offset_weeks,
                    artifact_type=entry.artifact_type,
                    author_tier=entry.author_tier,
                )
            )
    return slots
