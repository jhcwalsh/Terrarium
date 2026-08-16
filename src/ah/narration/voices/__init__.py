"""The newsroom — the three voices assembled over the slate stream.

Every voice is behind :class:`~ah.narration.voices.base.Voice`. This module is
the only place that knows which voice speaks to which slot, and it holds no
tunables of its own: everything it consults arrives already resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ah.narration.constants import MONTH_NAMES, MONTHS_PER_YEAR
from ah.narration.errors import NarrationError
from ah.narration.events import Event
from ah.narration.slate import Announcement, Slate
from ah.narration.voices.base import (
    Artifact,
    LlmBackend,
    TemplateBank,
    Voice,
    fill,
    no_template,
    slot_values,
)
from ah.narration.voices.columnists import ColumnistsParams, ColumnistsVoice
from ah.narration.voices.economist import EconomistParams, EconomistVoice, filtered_r_star
from ah.narration.voices.fomc import FomcParams, FomcVoice

__all__ = [
    "Artifact",
    "ColumnistsParams",
    "ColumnistsVoice",
    "EconomistParams",
    "EconomistVoice",
    "FomcParams",
    "FomcVoice",
    "LlmBackend",
    "Newsroom",
    "RenderedSlate",
    "TemplateBank",
    "Voice",
    "filtered_r_star",
]


def dateline(month: int) -> str:
    """``"March, Year 4"`` — the in-world dateline (DN-9 §5.1)."""
    return (
        f"{MONTH_NAMES[(month - 1) % MONTHS_PER_YEAR]}, Year {(month - 1) // MONTHS_PER_YEAR + 1}"
    )


@dataclass(frozen=True)
class RenderedItem:
    """One announcement, rendered: the paper's own copy plus any voice pieces."""

    announcement: Announcement
    report: Artifact
    voices: tuple[Artifact, ...] = ()

    def texts(self) -> tuple[str, ...]:
        """Every *copy* segment, one per element, markers excluded.

        Segments rather than one joined string so an n-gram cannot straddle a
        headline and a body — that would report the join as a repeated phrase.
        ``[[...]]`` markers are excluded because they are measurements, not
        copy, and the coverage panel counts them separately.
        """
        segments: list[str] = []
        for artifact in (self.report, *self.voices):
            segments.append(artifact.headline)
            segments.extend(artifact.body)
        return tuple(segment for segment in segments if segment and "[[" not in segment)


@dataclass(frozen=True)
class RenderedSlate:
    slate: Slate
    items: tuple[RenderedItem, ...]
    layout_state: str
    dateline: str
    notes: tuple[str, ...] = field(default_factory=tuple)


class Newsroom:
    """Renders slates. Holds the voices; holds no parameters of its own."""

    def __init__(
        self,
        *,
        events_bank: TemplateBank,
        fomc: FomcVoice,
        columnists: ColumnistsVoice,
        economist: EconomistVoice,
        cross_firing: dict[str, float],
        layout_states: dict[str, str],
        world_id: str,
    ) -> None:
        self.events_bank = events_bank
        self.fomc = fomc
        self.columnists = columnists
        self.economist = economist
        self.cross_firing = cross_firing
        self.layout_states = layout_states
        self.world_id = world_id

    def _report(self, event: Event, context: dict[str, Any]) -> Artifact:
        """The paper's own copy for one event, from the per-class bank."""
        variant = self.events_bank.pick(
            (event.cls, str(event.severity)),
            seed_parts=(self.world_id, event.month, event.cls),
            cross_firing=self.cross_firing,
        )
        slots = slot_values(event, context)
        if variant is None:
            marker = no_template(event)
            return Artifact(
                voice="wire",
                kind="report",
                headline=marker,
                body=(marker,),
                missing_template=True,
            )
        return Artifact(
            voice="wire",
            kind="report",
            headline=fill(str(variant["headline"]), slots, source=self.events_bank.source),
            body=(fill(str(variant["body"]), slots, source=self.events_bank.source),),
            chips=(event.delta["label"],),
            template_ids=(str(variant["id"]),),
        )

    def render(
        self,
        slates: list[Slate],
        *,
        regime: tuple[str, ...],
        severity_by_month: dict[int, int],
        r_star_hat: Any,
        unemployment: Any,
        credit_stress_months: set[int],
    ) -> list[RenderedSlate]:
        rendered: list[RenderedSlate] = []
        for slate in slates:
            last_month = slate.months[-1]
            label = regime[last_month - 1]
            if label not in self.layout_states:
                raise NarrationError(
                    f"style.layout_states has no entry for regime '{label}'. DN-9 §5.2 maps six "
                    "regimes onto four layout states and does not say which share; an "
                    "unmapped regime cannot be laid out."
                )
            items: list[RenderedItem] = []
            for announcement in slate.announcements:
                event = announcement.event
                context: dict[str, Any] = {
                    "world_id": self.world_id,
                    "cross_firing": self.cross_firing,
                    "month_name": dateline(event.month),
                    "severity_by_month": severity_by_month,
                    "credit_stress": event.month in credit_stress_months,
                    "unemployment_rising": bool(
                        event.month > 1
                        and unemployment[event.month - 1] > unemployment[event.month - 2]
                    ),
                    "r_star_hat": float(r_star_hat[event.month - 1])
                    if r_star_hat[event.month - 1] == r_star_hat[event.month - 1]
                    else 0.0,
                }
                voices: list[Artifact] = []
                if event.cls == "E01":
                    # The FOMC set piece IS the paper's report of the meeting,
                    # not a sidebar next to one. Rendering both would print two
                    # headlines for one decision -- and, before the template
                    # `requires:` binding, two headlines that could disagree
                    # about whether a sentence had been deleted.
                    report = self.fomc.render(event, context)
                    voices.append(self.economist.render(event, context))
                else:
                    report = self._report(event, context)
                voices.append(self.columnists.render(event, context))
                items.append(
                    RenderedItem(
                        announcement=announcement,
                        report=report,
                        voices=tuple(voices),
                    )
                )
            rendered.append(
                RenderedSlate(
                    slate=slate,
                    items=tuple(items),
                    layout_state="dislocated" if slate.special else self.layout_states[label],
                    dateline=dateline(last_month),
                    notes=slate.omission_notes,
                )
            )
        return rendered
