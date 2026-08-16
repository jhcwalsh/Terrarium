"""The quarterly slate — the unit of publication (DN-9 Appendix B).

One slot per CIO-dashboard panel: POLICY, DATA, MARKETS, CAPITAL. Each slot runs
a contest among the quarter's events for that panel; the winner is the
announcement, the losers become one-line notes rather than disappearing (§B.1).

Three rules from §B.11 are enforced here rather than described:

* **Slate size is a function of that quarter's own realised events and nothing
  else.** A builder that could save a slot for something coming would make slate
  size a forward signal in the same way a planted thread is (§2.4). Nothing in
  this module can see a later quarter: the events are bucketed first and each
  bucket is assembled in isolation.
* **Every announcement names the panel and the delta it explains.** No anchor,
  no announcement.
* **Determinism.** Ties resolve by a rule read from config and documented in
  ``UNRESOLVED.md``, never by dict ordering or set iteration.

The CAPITAL slot is omitted — not stubbed — when the world carries no book, and
the omission is carried on the slate so the artifact can state it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ah.narration.constants import (
    MONTHS_PER_QUARTER,
    PANEL_OF_SLOT,
    QUARTERS_PER_YEAR,
    SLOTS,
)
from ah.narration.errors import NarrationError
from ah.narration.events import Event

__all__ = ["Announcement", "Slate", "SlateParams", "build_slates"]


@dataclass(frozen=True)
class SlateParams:
    """Resolved slate parameters."""

    contest_rule: str
    tie_break: str
    min_slots: int
    capital_drop_rule: str | None
    special_edition_severity: int
    capital_absent_message: str
    book_available: bool


@dataclass(frozen=True)
class Announcement:
    """One slot's winning event, with the losers it beat."""

    slot: str
    panel: str
    delta: dict[str, Any]
    event: Event
    also_this_quarter: tuple[Event, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "panel": self.panel,
            "delta": self.delta,
            "event": self.event.as_record(),
            "also_this_quarter": [e.as_record() for e in self.also_this_quarter],
        }


@dataclass(frozen=True)
class Slate:
    """One quarter's publication."""

    quarter: int
    year: int
    quarter_of_year: int
    months: tuple[int, ...]
    announcements: tuple[Announcement, ...]
    special: bool
    omitted_slots: tuple[str, ...]
    omission_notes: tuple[str, ...]
    below_minimum: bool

    @property
    def lead(self) -> Announcement | None:
        """The announcement that leads the page: highest severity, then slot order."""
        if not self.announcements:
            return None
        return max(
            self.announcements,
            key=lambda a: (a.event.severity, -SLOTS.index(a.slot)),
        )


def _primary(rule: str, event: Event) -> float:
    if rule == "severity_then_abs_delta":
        return abs(float(event.delta["value"]))
    if rule == "severity_then_latest_month":
        return float(event.month)
    if rule == "severity_then_earliest_month":
        return -float(event.month)
    raise NarrationError(
        f"slate.contest_rule: unknown rule '{rule}'. The contest is not defaulted — DN-9 §B.1 "
        "gives four per-slot rules in words and no general one, which is decision N-o."
    )


def _tie_break(rule: str, event: Event) -> tuple[float, float]:
    """Tie-break components, larger is better, so the whole key is a max."""
    class_rank = -float(int(event.cls[1:]))
    if rule == "lowest_class_id_then_lowest_month":
        return class_rank, -float(event.month)
    if rule == "lowest_month_then_lowest_class_id":
        return -float(event.month), class_rank
    if rule == "highest_abs_delta_then_lowest_class_id":
        return abs(float(event.delta["value"])), class_rank
    raise NarrationError(
        f"slate.tie_break: unknown rule '{rule}'. A tie resolved by dict ordering or set "
        "iteration is a determinism defect, which is why this has no default."
    )


def _contest(candidates: list[Event], params: SlateParams) -> tuple[Event, tuple[Event, ...]]:
    def key(event: Event) -> tuple[float, ...]:
        return (
            float(event.severity),
            _primary(params.contest_rule, event),
            *_tie_break(params.tie_break, event),
        )

    ordered = sorted(candidates, key=key, reverse=True)
    return ordered[0], tuple(sorted(ordered[1:], key=lambda e: (e.month, e.cls)))


def _capital_dropped(candidates: list[Event], params: SlateParams) -> bool:
    rule = params.capital_drop_rule
    if rule is None or rule == "never_drop":
        return False
    top = max(event.severity for event in candidates)
    if rule == "drop_when_max_severity_zero":
        return top == 0
    if rule == "drop_when_max_severity_below_one":
        return top < 1
    raise NarrationError(f"slate.capital_drop_rule: unknown rule '{rule}'")


def build_slates(events: list[Event], params: SlateParams, *, months: int) -> list[Slate]:
    """Assemble every quarter's slate. Each quarter is assembled in isolation."""
    buckets: dict[int, list[Event]] = {}
    total_quarters = months // MONTHS_PER_QUARTER
    for quarter in range(1, total_quarters + 1):
        buckets[quarter] = []
    for event in events:
        quarter = (event.month - 1) // MONTHS_PER_QUARTER + 1
        if quarter in buckets:
            buckets[quarter].append(event)

    slates: list[Slate] = []
    for quarter in range(1, total_quarters + 1):
        quarter_events = buckets[quarter]
        announcements: list[Announcement] = []
        omitted: list[str] = []
        notes: list[str] = []

        for slot in SLOTS:
            candidates = [event for event in quarter_events if event.slot == slot]
            if slot == "CAPITAL" and not params.book_available:
                omitted.append(slot)
                notes.append(params.capital_absent_message)
                continue
            if not candidates:
                omitted.append(slot)
                notes.append(f"{slot} omitted — nothing in the quarter anchors to this panel")
                continue
            if slot == "CAPITAL" and _capital_dropped(candidates, params):
                omitted.append(slot)
                notes.append("CAPITAL dropped — nothing in the book moved beyond routine")
                continue
            winner, losers = _contest(candidates, params)
            announcements.append(
                Announcement(
                    slot=slot,
                    panel=PANEL_OF_SLOT[slot],
                    delta=winner.delta,
                    event=winner,
                    also_this_quarter=losers,
                )
            )

        top = max((event.severity for event in quarter_events), default=0)
        slates.append(
            Slate(
                quarter=quarter,
                year=(quarter - 1) // QUARTERS_PER_YEAR + 1,
                quarter_of_year=(quarter - 1) % QUARTERS_PER_YEAR + 1,
                months=tuple(
                    range((quarter - 1) * MONTHS_PER_QUARTER + 1, quarter * MONTHS_PER_QUARTER + 1)
                ),
                announcements=tuple(announcements),
                special=top >= params.special_edition_severity,
                omitted_slots=tuple(omitted),
                omission_notes=tuple(notes),
                below_minimum=len(announcements) < params.min_slots,
            )
        )
    return slates
