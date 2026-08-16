"""Ruth Calloway, House Economist — the narrative state, and the strain score.

The golden set is explicit that this voice is Tier-2 (`[L]`): "stateful,
revises, admits error. Not templatable and should not be attempted." So what is
built here is not Calloway's prose. It is the two things that are structured
data and that the workbench needs *now*:

* **the narrative state and the reversal cycle** (§D.3, §D.4) — thesis, primary
  risk, confidence, accumulated contradiction, and the HOLD THE LINE → DEFEND →
  QUALIFY → CAPITULATE transitions. Stickiness is modelled as a threshold on
  accumulated contradiction rather than a per-meeting update, because a
  narrative that flips on one print is not a committee, it is a weathervane;
* **the strain score** (§D.6), logged per meeting. **This is the reason the
  voice is in scope at all.** Aggregate strain is a realism diagnostic on the
  *generated policy path*, not on the narration: a path whose decisions cannot
  be explained contemporaneously by an agent holding all the contemporaneous
  evidence is a path with unexplainable policy in it. High strain does not prove
  the generator wrong; it localises where prose cannot follow the numbers.

The filtered state ``s^_t`` is estimated from **revealed observables only**
(§D.1) — the agent never reads the true latent, so it cannot leak what it was
never given. Only the EWMA candidate is implemented; the others raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.narration.constants import DISPLAY_PRECISION, PERCENT, RECORD_PRECISION
from ah.narration.errors import NarrationError
from ah.narration.events import Event
from ah.narration.voices.base import Artifact, TemplateBank, fill, no_template, stable_unit

__all__ = ["EconomistParams", "EconomistVoice", "NarrativeState"]

_RISK_KEYS = ("inflation", "growth", "financial_stability", "funding")


@dataclass(frozen=True)
class EconomistParams:
    backend: str
    name: str
    stickiness_meetings: int
    confidence_start: float
    confidence_decay: float
    capitulation_floor: float
    risk_book_size: int
    risk_materialisation_rate: float
    filtered_state: str
    strain_weights: dict[str, float]


@dataclass
class NarrativeState:
    """The small structured view carried between meetings (§D.3)."""

    thesis: str
    primary_risk: str
    confidence: float
    age_meetings: int = 0
    contradicted_by: list[str] = field(default_factory=list)
    state: str = "HOLD_THE_LINE"
    r_star_estimate: float = 0.0

    def as_record(self) -> dict[str, Any]:
        return {
            "thesis": self.thesis,
            "primary_risk": self.primary_risk,
            "confidence": round(self.confidence, DISPLAY_PRECISION),
            "age_meetings": self.age_meetings,
            "contradicted_by": list(self.contradicted_by),
            "state": self.state,
            "r_star_estimate": round(self.r_star_estimate, DISPLAY_PRECISION),
        }


def filtered_r_star(
    policy_rate: np.ndarray, cpi_yoy: np.ndarray, spec: str, span_months: int
) -> np.ndarray:
    """A contemporaneous estimate of the neutral real rate from revealed data.

    ``ewma_on_revealed`` is the only built candidate: an exponentially weighted
    mean of the realised real policy rate over ``span_months``. It has the right
    *serial structure* — slow, realistic revisions rather than jitter, which is
    the property DN-9 §D.1 says matters — and no uncertainty estimate, which is
    the property it lacks.

    ``span_months`` comes from ``voices.economist.filter_span_months`` and is an
    open decision. It was previously a bare ``1 / len(series)``: an undisclosed
    tunable, and one that made the filter depend on how long the world happened
    to be, so the same decade narrated over a different horizon filtered
    differently. An earlier docstring claimed the span was bound to the meeting
    stickiness; it never was, and it should not be — how fast an estimate of r*
    revises and how long a thesis survives are two questions.
    """
    if spec != "ewma_on_revealed":
        raise NarrationError(
            f"voices.economist.filtered_state is '{spec}', which is not built. A Kalman filter "
            "needs a state-space specification that is Quant's to write (N-s); "
            "'true_plus_noise' is the candidate DN-9 explicitly recommends against, because it "
            "gets the error magnitude right and its serial structure wrong. The workbench "
            "implements the EWMA candidate only and does not approximate the others."
        )
    real = np.where(np.isfinite(cpi_yoy), policy_rate - cpi_yoy, np.nan)
    out = np.full(real.shape, np.nan)
    running: float | None = None
    if span_months < 1:
        raise NarrationError(
            f"voices.economist.filter_span_months is {span_months}; an EWMA span shorter than "
            "one month is not a filter."
        )
    alpha = 1.0 / float(span_months)
    for index, value in enumerate(real):
        if not np.isfinite(value):
            continue
        running = value if running is None else (1.0 - alpha) * running + alpha * value
        out[index] = running
    return out


class EconomistVoice:
    """The rationale agent's Tier-1 half: narrative state, strain, risk book."""

    name = "economist"

    def __init__(self, bank: TemplateBank, params: EconomistParams) -> None:
        self.bank = bank
        self.params = params
        self.backend = params.backend
        self.narrative: NarrativeState | None = None
        self.strain_log: list[dict[str, Any]] = []
        self.risk_book: list[dict[str, Any]] = []

    # -- narrative ---------------------------------------------------------
    def _thesis_text(self, risk: str, seed: tuple[Any, ...]) -> str:
        variant = self.bank.pick(("thesis", risk), seed_parts=seed)
        return str(variant["text"]) if variant else f"[[NO TEMPLATE: thesis={risk}]]"

    def _primary_risk(self, event: Event, context: dict[str, Any]) -> str:
        terms = event.anchor_terms
        if terms is None:
            raise NarrationError("the economist was handed an E01 event with no anchor terms")
        if context.get("credit_stress"):
            return "financial_stability"
        if terms.gap_term > 0.0:
            return "inflation"
        if terms.cycle_term < 0.0:
            return "growth"
        return "funding"

    def _update(self, event: Event, context: dict[str, Any]) -> str:
        """Advance the reversal cycle and return the state this meeting is in."""
        risk = self._primary_risk(event, context)
        seed = (context["world_id"], event.month, "thesis")
        if self.narrative is None:
            self.narrative = NarrativeState(
                thesis=self._thesis_text(risk, seed),
                primary_risk=risk,
                confidence=self.params.confidence_start,
            )
            return self.narrative.state

        narrative = self.narrative
        narrative.age_meetings += 1
        contradicted = risk != narrative.primary_risk
        if contradicted:
            narrative.contradicted_by.append(f"m{event.month}: reading now points to {risk}")
            narrative.confidence -= self.params.confidence_decay

        if (
            narrative.confidence < self.params.capitulation_floor
            and narrative.age_meetings >= self.params.stickiness_meetings
        ):
            narrative.state = "CAPITULATE"
            self.narrative = NarrativeState(
                thesis=self._thesis_text(risk, seed),
                primary_risk=risk,
                confidence=self.params.confidence_start,
                state="HOLD_THE_LINE",
            )
            return "CAPITULATE"
        if contradicted and narrative.confidence < self.params.confidence_start:
            narrative.state = "QUALIFY" if len(narrative.contradicted_by) > 1 else "DEFEND"
        else:
            narrative.state = "HOLD_THE_LINE"
        return narrative.state

    # -- strain ------------------------------------------------------------
    def _strain(self, event: Event, contradiction_count: int, unmodelled: bool) -> float:
        """``strain_t = f(|eps_narr|, contradiction, unmodelled motive, retries)``.

        ``retries`` is structurally zero here: the coherence gate is a Tier-2
        mechanism and no generation happens in the workbench. It is kept in the
        sum so the weights carry across when Tier-2 lands, rather than being
        renumbered later.
        """
        terms = event.anchor_terms
        if terms is None:
            raise NarrationError("strain was asked for on an event with no anchor terms")
        weights = self.params.strain_weights
        missing = {"epsilon", "contradiction", "unmodelled_motive", "retries"} - set(weights)
        if missing:
            raise NarrationError(
                f"voices.economist.strain_weights is missing {sorted(missing)}. Strain is "
                "proposed for the sealed battery (N-v); a term with no weight would silently "
                "drop out of a metric someone is about to pre-register."
            )
        return (
            weights["epsilon"] * abs(terms.epsilon)
            + weights["contradiction"] * float(contradiction_count)
            + weights["unmodelled_motive"] * (1.0 if unmodelled else 0.0)
            + weights["retries"] * 0.0
        )

    # -- risk book ---------------------------------------------------------
    def _refresh_risks(self, event: Event, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Three-to-five live concerns, most of which must not happen (§D.14).

        Materialisation is decided by a hash draw against the configured rate
        and **not** by what the world does next. That is the honesty condition
        stated literally: ``P(flag | materialises) = P(flag | does not)`` holds
        by construction, because the flag never consults the outcome.
        """
        pool = self.bank.variants("risks")
        if len(pool) < self.params.risk_book_size:
            raise NarrationError(
                f"the risk bank holds {len(pool)} entries; voices.economist.risk_book_size asks "
                f"for {self.params.risk_book_size}"
            )
        # Drawn WITHOUT replacement: a risk book that names the same concern
        # twice in one month is not a risk book. Ordering the whole pool by a
        # per-month hash and taking the head keeps the draw deterministic and
        # keeps the book turning over between meetings.
        ordered = sorted(
            pool, key=lambda entry: stable_unit(context["world_id"], event.month, entry["id"])
        )
        book: list[dict[str, Any]] = []
        for entry in ordered[: self.params.risk_book_size]:
            book.append(
                {
                    "id": str(entry["id"]),
                    "text": str(entry["text"]),
                    "raised_month": event.month,
                    "materialises": stable_unit(context["world_id"], entry["id"], "materialise")
                    < self.params.risk_materialisation_rate,
                }
            )
        return book

    # -- interface ---------------------------------------------------------
    def render(self, event: Event, context: dict[str, Any]) -> Artifact:
        if self.backend != "template":
            raise NotImplementedError(
                f"voices.economist.backend is '{self.backend}'; only the template backend is "
                "built, and the golden set says Calloway's prose should not be templated at "
                "all. What is built is the narrative state, the strain score and the ledger."
            )
        terms = event.anchor_terms
        if terms is None:
            raise NarrationError("the economist was handed an E01 event with no anchor terms")

        state = self._update(event, context)
        narrative = self.narrative
        assert narrative is not None
        narrative.r_star_estimate = float(context.get("r_star_hat", 0.0))

        contradictions = len(narrative.contradicted_by)
        unmodelled = state in {"QUALIFY", "CAPITULATE"}
        strain = self._strain(event, contradictions, unmodelled)
        self.strain_log.append(
            {
                "month": event.month,
                "strain": round(strain, RECORD_PRECISION),
                "state": state,
                "epsilon": round(terms.epsilon, RECORD_PRECISION),
                "contradictions": contradictions,
            }
        )
        self.risk_book = self._refresh_risks(event, context)

        variant = self.bank.pick(
            ("rationale", state), seed_parts=(context["world_id"], event.month, "rationale")
        )
        slots = {
            "pi_fmt": f"{terms.pi:.1f}",
            "pi_star_fmt": f"{terms.pi_star:.1f}",
            "smoothed_pct": f"{terms.smoothed:.2f}",
            "target_pct": f"{terms.realised:.2f}",
            "epsilon_bp": f"{terms.epsilon * PERCENT:+.0f}",
            "contradiction_count": contradictions,
            "age_meetings": narrative.age_meetings,
            "prior_thesis": narrative.thesis,
        }
        text = (
            fill(str(variant["text"]), slots, source=self.bank.source)
            if variant
            else no_template(event)
        )
        watching = "; ".join(risk["text"] for risk in self.risk_book)
        return Artifact(
            voice=self.name,
            kind="rationale",
            headline=f"{self.params.name} — {state.replace('_', ' ').lower()}",
            body=(text, f"What I am watching: {watching}."),
            chips=(f"STRAIN {strain:.2f}", f"CONFIDENCE {narrative.confidence:.2f}"),
            extras={
                "narrative": narrative.as_record(),
                "strain": round(strain, RECORD_PRECISION),
                "risk_book": self.risk_book,
            },
            template_ids=(str(variant["id"]),) if variant else (),
            missing_template=variant is None,
        )
