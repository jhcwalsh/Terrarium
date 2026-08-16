"""The Committee — decision, statement, statement diff, dissents, rule monitor.

DN-9 §4.1: **the path comes first, the statement second.** The policy rate is
already in the realised path; the statement explains a decision that has already
been made, which is why it is a natural-language rendering of the model's own
reaction function rather than decoration bolted on afterwards.

Four things this module builds, in DN-9's order of value:

* **the decision**, from the realised path;
* **the statement**, assembled from clause banks keyed by the anchor terms —
  and checked against the mandate boundary, which is a *hard constraint*
  (§D.13, N-aa) and the mechanism that produces mandate lag;
* **the statement diff**, a word-level redline against the previous meeting.
  DN-9 calls this the highest ratio of flavour to build cost in the note;
* **the dissents**, from a committee of fictional members with persistent
  hawk-dove priors, drawn once at world build. Dissent is a function of the
  distance between a member's prior and the realised move, so dissents cluster
  at turning points without being scripted to.

The golden set's finding is respected throughout: **the Committee needs no LLM.**
Its register is achieved by removing words, not adding them.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.narration.constants import DISPLAY_PRECISION, PERCENT
from ah.narration.errors import NarrationError
from ah.narration.events import Event
from ah.narration.voices.base import Artifact, TemplateBank, fill, no_template, slot_values

__all__ = ["FomcParams", "FomcVoice", "Member"]


@dataclass(frozen=True)
class Member:
    """One committee member with a standing hawk-dove prior, in percentage points."""

    name: str
    prior: float


@dataclass(frozen=True)
class FomcParams:
    backend: str
    committee_size: int
    prior_spread: float
    dissent_threshold: float
    may_not_speak_to: tuple[str, ...]
    base_seed: int


#: Words that would put a statement outside the mandate boundary. Keyed by the
#: ``may_not_speak_to`` entries in ``voices.yaml``; the boundary itself is the
#: config's, this is the vocabulary that would violate it.
_OUT_OF_MANDATE_MARKERS = {
    "asset_valuations": ("valuation", "overvalued", "expensive equities"),
    "private_market_functioning": ("private credit", "redemption queue", "secondary discount"),
    "fiscal_policy": ("fiscal", "deficit", "the budget"),
    "named_institutions": ("Calder Bridge", "Kestrel"),
}


class FomcVoice:
    """The Committee. Template backend only — see the module docstring."""

    name = "fomc"

    def __init__(self, bank: TemplateBank, events_bank: TemplateBank, params: FomcParams) -> None:
        self.bank = bank
        self.events_bank = events_bank
        self.params = params
        self.backend = params.backend
        self.members = self._draw_committee()
        self._previous_statement: list[str] | None = None

    # -- committee ---------------------------------------------------------
    def _draw_committee(self) -> tuple[Member, ...]:
        """Priors drawn once, from the world seed. No global RNG, no time."""
        roster = list(self.bank.document.get("committee_roster", []))
        if len(roster) < self.params.committee_size:
            raise NarrationError(
                f"the committee roster holds {len(roster)} names but "
                f"voices.fomc.dissent.committee_size asks for {self.params.committee_size}"
            )
        rng = np.random.Generator(np.random.PCG64(self.params.base_seed))
        priors = rng.normal(0.0, self.params.prior_spread, self.params.committee_size)
        return tuple(
            Member(name=str(name), prior=float(prior))
            for name, prior in zip(roster[: self.params.committee_size], priors, strict=True)
        )

    def _dissents(self, event: Event) -> list[dict[str, Any]]:
        """Members whose own reading is far enough from the realised move to vote against.

        Measured against the SMOOTHED anchor rather than the raw one: the
        smoothed anchor is the narration anchor (DN-9 §C.6) and is the quantity
        epsilon is defined against, so the committee disagrees about the same
        object the page calls the surprise.

        Note what this does NOT do: cap the number of dissents. When the anchor
        sits far from the realised path the whole committee votes against, which
        is mechanically correct per §4.1 and absurd on the page — and that is a
        finding about rho and the anchor coefficients, not a reason to add a cap
        the note does not have.
        """
        anchor = float(event.trigger_values["smoothed_anchor"])
        realised = float(event.trigger_values["target"])
        out: list[dict[str, Any]] = []
        for member in self.members:
            preferred = anchor + member.prior
            distance = preferred - realised
            if abs(distance) <= self.params.dissent_threshold:
                continue
            out.append(
                {
                    "name": member.name,
                    "direction": "hawkish" if distance > 0 else "dovish",
                    "wanted": round(preferred, DISPLAY_PRECISION),
                }
            )
        return sorted(out, key=lambda d: str(d["name"]))

    # -- statement ---------------------------------------------------------
    def _clause(self, section: str, key: str, slots: dict[str, Any], seed: tuple[Any, ...]) -> str:
        variant = self.bank.pick(("statement", section, key), seed_parts=seed)
        if variant is None:
            return ""
        return fill(str(variant["text"]), slots, source=self.bank.source)

    def _statement(self, event: Event, context: dict[str, Any], slots: dict[str, Any]) -> list[str]:
        terms = event.anchor_terms
        if terms is None:
            raise NarrationError("an E01 event reached the FOMC voice without anchor terms")
        seed = (context["world_id"], event.month, "statement")
        activity = "slowed" if terms.cycle_term < 0.0 else "expanding"
        if terms.gap_term > 0.0:
            inflation = "higher" if terms.epsilon >= 0.0 else "elevated"
        else:
            inflation = "declined"
        labour = "softening" if context.get("unemployment_rising") else "firm"
        move = float(event.delta["value"])
        decision = "raises" if move > 0 else "lowers" if move < 0 else "holds"

        if context.get("credit_stress"):
            risks = "financial_conditions"
        elif terms.gap_term >= abs(terms.cycle_term):
            risks = "price_stability"
        elif terms.cycle_term < 0.0:
            risks = "employment"
        else:
            risks = "balanced"

        # The deletion the golden set makes the news: a committee that departs
        # sharply from its own rule stops promising a return to target.
        commitment = "deleted" if (terms.epsilon > 0.0 and event.severity >= 3) else "retained"
        guidance = "firming" if move > 0 else "none"

        clauses = [
            self._clause("activity", activity, slots, seed),
            self._clause("labour", labour, slots, seed),
            self._clause("inflation", inflation, slots, seed),
            self._clause("decision", decision, slots, seed),
            self._clause("balance_of_risks", risks, slots, seed),
            self._clause("commitment", commitment, slots, seed),
            self._clause("guidance", guidance, slots, seed),
        ]
        return [clause for clause in clauses if clause]

    def _check_mandate(self, sentences: list[str]) -> None:
        text = " ".join(sentences).lower()
        for topic in self.params.may_not_speak_to:
            for marker in _OUT_OF_MANDATE_MARKERS.get(topic, ()):
                if marker.lower() in text:
                    raise NarrationError(
                        f"the Committee's statement mentions '{marker}', which falls under "
                        f"'{topic}' in voices.fomc.mandate_boundary.may_not_speak_to. The "
                        "boundary is a hard constraint, not prompt guidance (DN-9 §D.13): it "
                        "is the mechanism that produces mandate lag, and a Committee that "
                        "drifts outside its remit loses the lesson."
                    )

    @staticmethod
    def _diff(previous: list[str] | None, current: list[str]) -> list[dict[str, str]]:
        """A word-level redline of the statement against the previous meeting."""
        if previous is None:
            return []
        before = " ".join(previous).split()
        after = " ".join(current).split()
        out: list[dict[str, str]] = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=before, b=after).get_opcodes():
            if op == "equal":
                continue
            out.append(
                {
                    "op": op,
                    "removed": " ".join(before[i1:i2]),
                    "added": " ".join(after[j1:j2]),
                }
            )
        return out

    # -- interface ---------------------------------------------------------
    def render(self, event: Event, context: dict[str, Any]) -> Artifact:
        if self.backend != "template":
            raise NotImplementedError(
                f"voices.fomc.backend is '{self.backend}'. Only the template backend is built; "
                "the golden set establishes the Committee needs no LLM at all."
            )
        terms = event.anchor_terms
        if terms is None:
            raise NarrationError("an E01 event reached the FOMC voice without anchor terms")
        slots = slot_values(event, context)
        slots.update(
            {
                "neutral_pct": f"{terms.neutral:.2f}",
                "gap_pct": f"{terms.gap_term:+.2f}",
                "cycle_pct": f"{terms.cycle_term:+.2f}",
            }
        )

        headline_variant = self.events_bank.pick(
            (event.cls, str(event.severity)),
            seed_parts=(context["world_id"], event.month, event.cls),
            cross_firing=context["cross_firing"],
        )
        sentences = self._statement(event, context, slots)
        self._check_mandate(sentences)
        diff = self._diff(self._previous_statement, sentences)
        self._previous_statement = sentences

        dissents = self._dissents(event)
        key = "none" if not dissents else ("one" if len(dissents) == 1 else "many")
        dissent_variant = self.bank.pick(
            ("dissent", key), seed_parts=(context["world_id"], event.month, "dissent")
        )
        names = ", ".join(f"{d['name']}, who preferred {d['wanted']:.2f} percent" for d in dissents)
        dissent_line = (
            fill(str(dissent_variant["text"]), {**slots, "names": names}, source=self.bank.source)
            if dissent_variant
            else no_template(event)
        )

        monitor_variant = self.bank.pick(
            ("rule_monitor",), seed_parts=(context["world_id"], event.month, "monitor")
        )
        monitor = (
            fill(str(monitor_variant["text"]), slots, source=self.bank.source)
            if monitor_variant
            else no_template(event)
        )

        two_sided = len({d["direction"] for d in dissents}) > 1
        return Artifact(
            voice=self.name,
            kind="fomc_set_piece",
            headline=(
                fill(str(headline_variant["headline"]), slots, source=self.events_bank.source)
                if headline_variant
                else no_template(event)
            ),
            body=(*sentences, dissent_line),
            chips=(
                "SURPRISE"
                if abs(terms.epsilon) * PERCENT >= self.params.dissent_threshold * PERCENT
                else "IN LINE",
                "HAWKISH" if terms.epsilon > 0 else "DOVISH" if terms.epsilon < 0 else "NEUTRAL",
            ),
            extras={
                "statement": sentences,
                "statement_diff": diff,
                "dissents": dissents,
                "two_sided_dissent": two_sided,
                "rule_monitor": monitor,
                "anchor": terms.as_record(),
                "committee": [
                    {"name": m.name, "prior": round(m.prior, DISPLAY_PRECISION)}
                    for m in self.members
                ],
            },
            template_ids=tuple(
                str(v["id"])
                for v in (headline_variant, dissent_variant, monitor_variant)
                if v is not None
            ),
            missing_template=headline_variant is None,
        )
