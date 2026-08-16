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
    #: How the flows columnist's directional call is formed. The only built
    #: value is ``complement_of_consensus``, and it is a PLACEHOLDER with a
    #: known measurement defect — see :meth:`ColumnistsVoice.calls`.
    flows_call_rule: str


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

        ``severity_band`` — the built value — is exactly what its name says: the
        announcement's severity normalised by the top of the grammar. It is a
        readout of the severity band and **not** a surprise in sigma units; the
        registry entry says so, because an entry that described it as the latter
        would be describing something nobody built.

        ``surprise_sd_scaled`` is the reading DN-9 §D.11 more naturally
        suggests and is a live candidate, but only E02/E03/E04 carry a
        ``surprise_sd`` — POLICY carries an epsilon and MARKETS carries neither
        — so it raises rather than silently falling back for two slots in four.
        ``regime_conditional`` raises deliberately: it would key the visible
        dispersion of the commentary off the L2 label, the non-injectivity
        failure §3.1 warns about, and it needs a map nobody has agreed.
        """
        model = self.params.dispersion_model
        if model == "severity_band":
            return round(event.severity / SEVERITY_MAX, DISPLAY_PRECISION)
        if model == "fixed":
            return None
        if model == "surprise_sd_scaled":
            raise NarrationError(
                "voices.columnists.dispersion is 'surprise_sd_scaled', which is not built. "
                "Only the DATA classes (E02/E03/E04) carry a surprise_sd; POLICY carries an "
                "epsilon and MARKETS carries neither, so adopting it needs a stated rule for "
                "the other two slots rather than a silent fallback."
            )
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
                "flows_call_rule": self.params.flows_call_rule,
                "calls_are_degenerate": self.calls_are_degenerate,
            },
            template_ids=tuple(ids),
            missing_template=missing,
        )

    @property
    def calls_are_degenerate(self) -> bool:
        """True while the flows call is the exact complement of the other two.

        Read by the diagnostics panel, which must disclose it: under the
        placeholder rule the three hit rates are always ``(h, h, 1-h)``, so the
        panel is reporting an identity and cannot distinguish a well-calibrated
        cast from a badly calibrated one.
        """
        return self.params.flows_call_rule == "complement_of_consensus"

    def _calls(self, event: Event) -> list[dict[str, Any]]:
        """Each templated columnist's directional call, from revealed state only.

        Consensus-hugging voices extrapolate the latest move. What the *flows*
        voice does is ``voices.columnists.flows_call_rule``, and the only built
        value is the **placeholder** ``complement_of_consensus`` — the exact
        negation of the other two. That is a measurement defect, not a voice: it
        forces the three hit rates to ``(h, h, 1-h)``. It is kept, labelled and
        disclosed on the panel rather than replaced, because inventing a third
        call rule would be taking the decision the registry entry exists to
        record.
        """
        rule = self.params.flows_call_rule
        if rule != "complement_of_consensus":
            raise NarrationError(
                f"voices.columnists.flows_call_rule is '{rule}', which is not built. "
                "'trailing_momentum' needs a window length and 'independent_of_the_print' "
                "needs a bible; both are further decisions rather than a code path away."
            )
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
