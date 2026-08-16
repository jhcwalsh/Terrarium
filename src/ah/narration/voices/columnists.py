"""The columnists — consensus-hugging, fallible, and formulaic on purpose.

The golden set corrects an earlier spec here and the correction is the design:
**columnists speak from the latest print and land with consensus.** They are not
fixed-prior contrarians. Halloran is the tell — he restates consensus and
adjusts a forecast, and the reader is meant to learn to skim him. Three of the
four template cleanly *because* consensus-hugging voices are formulaic in life;
rendering them formulaically is accurate rather than cheap.

**Ferrers is the retained outlier and his backend is ``llm``.** He is not
templated and must not be: "six good lines a decade, and they must not repeat".
The workbench records him as deferred rather than inventing him, and the
coverage panel counts the deferral. Calling his backend raises.

Dispersion collapses when consensus is strong and widens at turning points
(§D.11). The model behind that is an open parameter and only one of its three
candidates is implemented — see :meth:`ColumnistsVoice.dispersion`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ah.narration.constants import DISPLAY_PRECISION, SEVERITY_MAX
from ah.narration.errors import NarrationError
from ah.narration.events import Event
from ah.narration.voices.base import Artifact, TemplateBank, fill, no_template, slot_values

__all__ = ["ColumnistsParams", "ColumnistsVoice"]


@dataclass(frozen=True)
class ColumnistsParams:
    backend: str
    count: int
    consensus_lag_months: int
    dispersion_model: str
    hit_rate_target: tuple[float, float]
    outlier_backend: str


class ColumnistsVoice:
    """The standing cast. One artifact per announcement, one line per columnist."""

    name = "columnists"

    def __init__(self, bank: TemplateBank, params: ColumnistsParams) -> None:
        self.bank = bank
        self.params = params
        self.backend = params.backend
        cast = list(bank.document.get("cast", []))
        if len(cast) < params.count:
            raise NarrationError(
                f"the columnist cast holds {len(cast)} names but voices.columnists.count asks "
                f"for {params.count}. The golden set fixes four by name; adding a fifth needs a "
                "fifth register, which does not exist."
            )
        self.cast = cast[: params.count]
        self.deferred = tuple(
            str(member["name"]) for member in self.cast if member.get("backend") == "llm"
        )

    def dispersion(self, event: Event, context: dict[str, Any]) -> float | None:
        """How far apart the columnists are this quarter, in [0, 1].

        Only ``surprise_scaled`` and ``fixed`` are built. ``regime_conditional``
        raises, and deliberately: it would key the visible dispersion of the
        commentary off the L2 label, which is the non-injectivity failure DN-9
        §3.1 warns about, and it needs a regime -> dispersion map that is a
        further open decision nobody has taken.
        """
        model = self.params.dispersion_model
        if model == "surprise_scaled":
            return round(event.severity / SEVERITY_MAX, DISPLAY_PRECISION)
        if model == "fixed":
            return None
        if model == "regime_conditional":
            raise NarrationError(
                "voices.columnists.dispersion is 'regime_conditional', which is not built. It "
                "needs a regime -> dispersion map that is itself an open parameter, and it "
                "would make columnist dispersion a readout of the L2 label — the §3.1 hazard. "
                "Choose another candidate or resolve the map first."
            )
        raise NarrationError(f"voices.columnists.dispersion: unknown model '{model}'")

    def _band(self, event: Event, context: dict[str, Any], member: dict[str, Any]) -> str:
        """The severity band a columnist writes to.

        The consensus-hugging voices turn LATE: ``consensus_lag_months`` behind
        the print, they are still writing to the severity of the earlier one.
        That lag is what makes the herding visible inside one decade.
        """
        if member.get("beat") != "consensus":
            return str(event.severity)
        history: dict[int, int] = context.get("severity_by_month", {})
        lagged = event.month - self.params.consensus_lag_months
        return str(history.get(lagged, event.severity))

    def render(self, event: Event, context: dict[str, Any]) -> Artifact:
        if self.backend != "template":
            raise NotImplementedError(
                f"voices.columnists.backend is '{self.backend}'; only the template backend is "
                "built. The golden set finds three of the four template cleanly."
            )
        slots = slot_values(event, context)
        lines: list[str] = []
        ids: list[str] = []
        missing = False
        for member in self.cast:
            name = str(member["name"])
            if member.get("backend") == "llm":
                lines.append(
                    f"{name}: [[TIER-2 DEFERRED: the outlier columnist is llm-backed; "
                    "generation is a task non-goal]]"
                )
                continue
            variant = self.bank.pick(
                (name, event.slot, self._band(event, context, member)),
                seed_parts=(context["world_id"], event.month, name),
                cross_firing=context["cross_firing"],
            )
            if variant is None:
                lines.append(f"{name}: {no_template(event)}")
                missing = True
                continue
            lines.append(f"{name}: {fill(str(variant['text']), slots, source=self.bank.source)}")
            ids.append(str(variant["id"]))

        spread = self.dispersion(event, context)
        return Artifact(
            voice=self.name,
            kind="columnists",
            headline="Who thinks what",
            body=tuple(lines),
            chips=() if spread is None else (f"DISPERSION {spread:.2f}",),
            extras={
                "dispersion": spread,
                "dispersion_model": self.params.dispersion_model,
                "deferred": list(self.deferred),
                "hit_rate_target": list(self.params.hit_rate_target),
                "calls": self._calls(event),
            },
            template_ids=tuple(ids),
            missing_template=missing,
        )

    def _calls(self, event: Event) -> list[dict[str, Any]]:
        """Each templated columnist's directional call, from revealed state only.

        Consensus-hugging voices extrapolate the latest move; the policy and
        flows voices lean against a large one. The realised hit rate is measured
        in diagnostics against ``hit_rate_target`` — the point of the parameter
        is that they must be *fallible*, so a build outside the band is a finding
        about the bank rather than a bug.
        """
        direction = 1 if float(event.delta["value"]) > 0 else -1
        calls: list[dict[str, Any]] = []
        for member in self.cast:
            if member.get("backend") == "llm":
                continue
            beat = str(member.get("beat"))
            call = (
                direction if beat == "consensus" else -direction if beat == "flows" else direction
            )
            calls.append({"name": str(member["name"]), "call": call, "month": event.month})
        return calls
