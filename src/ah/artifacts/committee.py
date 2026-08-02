"""The AI committee (WP4.8) — bounded, briefed, filed, and always beatable.

Four disciplines, from the plan verbatim:

1. **Bounded**: whatever the model proposes is parsed through the typed
   decision contract — an action outside the allowed menu (or a declared-
   but-unimplemented verb) is rejected, never coerced.
2. **Briefed**: the briefing is deterministic code over the REVEALED
   slice only — it consumes :class:`ah.artifacts.live.RevealedTape`, so
   the information wall is inherited structurally, plus the portfolio
   view on the marks in view and the last N wire items.
3. **Filed**: every decision produces a rationale as a wire-item payload
   for the chronicle, and carries prompt version + model id (the G9
   discipline applied to decisions).
4. **Beatable**: the heuristic ablation is always available — as the
   fallback when the model fails to produce a valid decision, and as the
   comparison baseline wp4-09 scores against. Same for
   random-within-bounds and hold-course.

Personas are CONFIGURATION (a dataclass rendered into the prompt), never
code paths — persona differences are measured as prompt sensitivity, not
celebrated as insight (the plan's pitfall list).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.artifacts.decisions import (
    DecisionError,
    DecisionWindow,
    action_from_client,
)
from ah.artifacts.live import RevealedTape

COMMITTEE_PROMPT_VERSION = "committee-prompt@1.0"

COMMITTEE_PROMPT = """\
You are the investment committee of a simulated institution in a market
simulation. Persona: {persona}.

REVEALED STATE (everything you may know; nothing beyond it exists for you):
{briefing}

ALLOWED ACTIONS (the complete menu; anything else is rejected):
- rebalance_public: payload {{"target_weights": {{"<sleeve>": <fraction>}}}}
- an empty list: reaching the window and choosing to do nothing is a decision

Respond with JSON only:
{{"actions": [...], "rationale": "<3-6 sentences, your reasoning on the record>"}}
"""


class CommitteeError(ValueError):
    """A committee operation the contract refuses."""


@dataclass(frozen=True)
class Persona:
    """Configuration, not code: rendered into the prompt, recorded per decision."""

    persona_id: str
    description: str


@dataclass
class CommitteeDecision:
    window: DecisionWindow
    rationale: str
    decided_by: str  # model | heuristic_fallback
    persona_id: str
    prompt_version: str
    model_id: str

    def rationale_wire_payload(self, *, world_id: str, dateline: str) -> dict[str, Any]:
        """The filed rationale: a wire-item payload for the chronicle."""
        return {
            "world_id": world_id,
            "dateline": dateline,
            "headline": (
                f"Committee minutes, window {self.window.window_id}: "
                f"{len(self.window.actions)} action(s)"
            ),
            "body": self.rationale,
        }


def build_briefing(
    *,
    revealed: RevealedTape,
    weights_reported: dict[str, float],
    coverage_liquid: float,
    wire_items: list[str],
    n_wire: int = 8,
) -> str:
    """Deterministic briefing text over the revealed slice ONLY.

    The wall is inherited: ``revealed`` cannot answer beyond its pointer,
    and this function computes summary statistics only from what it holds
    (trailing returns, drawdown-to-date, latest levels). Weights are the
    REPORTED plane — the committee sees the marks in view, like a real one.
    """
    if revealed.months_revealed == 0:
        raise CommitteeError("a briefing needs at least one revealed month")
    series = revealed.data[:, 0]
    wealth = np.cumprod(1.0 + series)
    peaks = np.maximum.accumulate(np.concatenate([[1.0], wealth]))[1:]
    dd_to_date = float(np.max(1.0 - wealth / peaks))
    trailing_12 = float(np.prod(1.0 + series[-12:]) - 1.0)
    lines = [
        f"months revealed: {revealed.months_revealed}",
        f"trailing 12m public return: {trailing_12:+.1%}",
        f"max drawdown to date: {dd_to_date:.1%}",
        "reported weights: "
        + ", ".join(f"{k} {v:.1%}" for k, v in sorted(weights_reported.items())),
        f"coverage (unfunded / liquid): {coverage_liquid:.2f}",
        "recent wire:",
        *[f"  - {item}" for item in wire_items[-n_wire:]],
    ]
    return "\n".join(lines)


def render_committee_prompt(persona: Persona, briefing: str) -> str:
    return COMMITTEE_PROMPT.format(persona=persona.description, briefing=briefing)


def _parse_model_response(
    text: str, *, window_id: int, submitted_at: str
) -> tuple[DecisionWindow, str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise CommitteeError("no JSON object in the model response")
    try:
        doc = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise CommitteeError(f"unparseable JSON: {exc}") from exc
    raw_actions = doc.get("actions")
    rationale = doc.get("rationale")
    if not isinstance(raw_actions, list):
        raise CommitteeError("actions must be a list (empty is a decision; absent is not)")
    if not isinstance(rationale, str) or not rationale.strip():
        raise CommitteeError("a decision without a rationale is not filed")
    actions = tuple(action_from_client(a) for a in raw_actions)  # bounded menu enforced
    window = DecisionWindow(
        window_id=window_id, actions=actions, submitted_at=submitted_at, status="reached"
    )
    return window, rationale.strip()


# -- the ablation deciders (always available) -------------------------------- #


def heuristic_decision(
    *, weights_reported: dict[str, float], target_public: float = 0.60, band: float = 0.05
) -> tuple[list[dict[str, Any]], str]:
    """The rules-based committee: rebalance when outside the band, else hold."""
    current = weights_reported.get("public_equity", 0.0)
    if abs(current - target_public) > band:
        return (
            [
                {
                    "verb": "rebalance_public",
                    "payload": {"target_weights": {"public_equity": target_public}},
                }
            ],
            f"Heuristic rule: public weight {current:.1%} outside the "
            f"{target_public:.0%} +/- {band:.0%} band; rebalancing to target.",
        )
    return [], "Heuristic rule: within band; hold."


def random_within_bounds(
    *, base_seed: int, window_id: int, lo: float = 0.40, hi: float = 0.75
) -> tuple[list[dict[str, Any]], str]:
    """The luck baseline: a bounded random target, seeded and reproducible."""
    rng = np.random.Generator(np.random.PCG64(base_seed + 7919 * window_id))
    target = float(rng.uniform(lo, hi))
    return (
        [{"verb": "rebalance_public", "payload": {"target_weights": {"public_equity": target}}}],
        f"Random-within-bounds baseline: target {target:.1%} (seeded).",
    )


def hold_course() -> tuple[list[dict[str, Any]], str]:
    """The do-nothing baseline: reached, chose nothing, on the record."""
    return [], "Hold-course baseline: no action by construction."


# -- the committee ----------------------------------------------------------- #


def committee_decide(
    *,
    persona: Persona,
    briefing: str,
    decider: Callable[[str], str],
    model_id: str,
    window_id: int,
    submitted_at: str,
    weights_reported: dict[str, float],
) -> CommitteeDecision:
    """One committee decision: model first, heuristic fallback always.

    A model response that fails to parse, names an action off the menu, or
    files no rationale falls back to the HEURISTIC decision — recorded as
    ``heuristic_fallback`` with the model id kept (the failure is part of
    the record, not erased).
    """
    prompt = render_committee_prompt(persona, briefing)
    try:
        window, rationale = _parse_model_response(
            decider(prompt), window_id=window_id, submitted_at=submitted_at
        )
        decided_by = "model"
    except (CommitteeError, DecisionError) as exc:
        raw_actions, rationale = heuristic_decision(weights_reported=weights_reported)
        rationale = f"{rationale} [model output rejected: {exc}]"
        window = DecisionWindow(
            window_id=window_id,
            actions=tuple(action_from_client(a) for a in raw_actions),
            submitted_at=submitted_at,
            status="reached",
        )
        decided_by = "heuristic_fallback"
    return CommitteeDecision(
        window=window,
        rationale=rationale,
        decided_by=decided_by,
        persona_id=persona.persona_id,
        prompt_version=COMMITTEE_PROMPT_VERSION,
        model_id=model_id,
    )
