"""Versioned prompt templates (WP4.4) — T-LETTER and T-NOTE, spec-verbatim.

The template TEXT is the vendored authoring spec §3 verbatim; the version
ids are the ones the spec names (``author-prompt/letter@1.0``,
``author-prompt/note@1.0``). Any edit to a template bumps the version and
re-runs the authoring regression set — that rule is FROZEN (G4-pre,
AM-2026-08-02-002), and a test hashes the strings so a silent edit fails
loudly. Rendering is pure string substitution: every ``{{...}}``
placeholder must resolve, unresolved placeholders refuse.
"""

from __future__ import annotations

import re
from typing import Any

from ah.artifacts.payloads import fmt_claims_for_prompt

PROMPT_VERSIONS = {
    # 1.3: the role-not-name rule for real institutions joins the exemplars
    # (run-7 true positive: a letter named The Federal Reserve).
    # 1.2: contrastive micro-exemplars for the three run-5 residual failure
    # modes (the 95% chase, lever 1) - demonstrated form, no full example
    # letter to copy numbers from.
    # 1.1: hard rules sharpened where run-4 first drafts actually slipped
    # (in-character 'guarantee' language; number reformatting) — the sealed
    # rules restated concretely, nothing weakened.
    "letter": "author-prompt/letter@1.4",
    # 1.1: sentence-case titles (run-2: headline Title Case defeated the G4
    # closed-world scan; sentence case keeps real entities catchable).
    # 1.2: inherits letter@1.1's sharpened hard rules by reference.
    # 1.3: the same micro-exemplars, IN the note template explicitly - a
    # textual 'identical to T-LETTER' is invisible to a model writing a note.
    "note": "author-prompt/note@1.5",
}

PRIOR_GLOSS = {
    "structurally_constructive": "growth and policy support resolve stress over time",
    "structurally_cautious": "fragilities compound and marks lag reality",
    "valuation_disciplined": "everything mean-reverts; entry price is destiny",
    "flow_and_momentum": "price trend leads fundamentals; respect the tape",
}

T_LETTER = """\
You are ghost-writing an in-world fictional document for a market simulation.
Write the quarterly investor letter of {{entity.name}}, a {{entity.one_liner}}.

VOICE: {{entity.voice.register}}. Stylistic habits to honor: {{entity.voice.tics}}.
CHARACTER: honor these traits without naming them: {{entity.signature_traits}}.
CONTINUITY: your firm's story so far (do not contradict; do not foreshadow anything beyond it):
{{arc_beats_to_date}}

THE QUARTER'S FACTS (the only numbers you may use — copy them verbatim, never derive new ones):
{{checkable_claims_table}}
Recent relevant newsflow: {{chronicle_extracts}}

WRITE: 350-550 words. Structure: (1) brief market commentary in-voice; (2) portfolio/marks
discussion — you MUST address the quarter's reported return and, if the public-comp gap
exceeds 3pts, you MUST address the gap in your firm's characteristic way (defend, deflect,
or acknowledge, per voice/traits — but never misstate a number); (3) outlook consistent
with your character, hedged as a real GP hedges.


THE THREE COMMON FAILURES, WITH FIXES (follow the RIGHT form exactly):
- WRONG: "we guarantee recovery" / "assured returns" -> RIGHT: "we believe recovery is likely"
- WRONG: restating +9.0% as "9%" or "nine percent" -> RIGHT: "+9.0%" character-for-character
- WRONG: "defaults rose across the market" when the newsflow above reports no defaults
  -> RIGHT: discuss such events only if the newsflow reports them; otherwise stay
  hypothetical ("should defaults rise...")
- WRONG: naming real institutions ("The Federal Reserve") -> RIGHT: role only
  ("the central bank", "the regulator")
- WRONG: any digit not in the facts table, even casually ("0.2 turns of
  leverage") -> RIGHT: numbers appear ONLY if copied from the facts table
- Your outlook MUST contain at least one cautious word (may / could / risk /
  watch / prudent) - a letter with no hedging anywhere will be rejected

HARD RULES: Mention only these named entities: {{allowed_entities}}. No real firms or people.
No dates or events after {{dateline}}. No promises of returns — never write 'guarantee',
'assure', or 'will deliver' in any form, however in-character it feels. Copy every number
EXACTLY as the facts table formats it (sign, decimals, units); never restate '+9.0%' as '9%'.
Name an event (a default, a gating, a rate move) only if the newsflow above reports it.
Do not mention that this is a simulation. Output the letter body only, no headers.
"""

T_NOTE = """\
You are ghost-writing an in-world fictional research note for a market simulation.
House: {{house.name}}. Structural prior: {{house.prior}} — {{prior_gloss}}.
VOICE: {{house.voice.register}}; habits: {{house.voice.tics}}.

SUBJECT: {{subject}} as of {{dateline}}.
DATA PANEL (only numbers permitted, verbatim): {{checkable_claims_table}}
NEWSFLOW: {{chronicle_extracts}}
THE OTHER HOUSE most recently said: "{{rival_stance_summary}}" — you may engage with it.

WRITE: 220-350 words: title (<=12 words, sentence case — capitalize only the first word
and named entities), rating from {overweight|neutral|underweight|no_rating},
2-4 paragraphs of argument READING THE SAME DATA THROUGH YOUR PRIOR, one explicitly stated
risk to your own view. Your interpretation should plausibly differ from the rival's;
your facts cannot.


THE THREE COMMON FAILURES, WITH FIXES (follow the RIGHT form exactly):
- WRONG: "we guarantee recovery" / "assured returns" -> RIGHT: "we believe recovery is likely"
- WRONG: restating +9.0% as "9%" or "nine percent" -> RIGHT: "+9.0%" character-for-character
- WRONG: "defaults rose across the market" when the newsflow above reports no defaults
  -> RIGHT: discuss such events only if the newsflow reports them; otherwise stay
  hypothetical ("should defaults rise...")
- WRONG: naming real institutions ("The Federal Reserve") -> RIGHT: role only
  ("the central bank", "the regulator")
- WRONG: any digit not in the facts table, even casually ("0.2 turns of
  leverage") -> RIGHT: numbers appear ONLY if copied from the facts table
- Your outlook MUST contain at least one cautious word (may / could / risk /
  watch / prudent) - a letter with no hedging anywhere will be rejected

HARD RULES: identical to T-LETTER (entities, dateline, exact number formats, no promises,
events only from the newsflow, no simulation references, body only).
"""

_PLACEHOLDER = re.compile(r"\{\{([a-z_.]+)\}\}")


class PromptError(ValueError):
    """A render the template refuses (unresolved placeholder, bad payload)."""


def _lookup(payload: dict[str, Any], dotted: str) -> str:
    node: Any = payload
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise PromptError(f"placeholder '{{{{{dotted}}}}}' unresolved by payload")
        node = node[part]
    if isinstance(node, list):
        return "\n".join(f"- {item}" for item in node) if node else "(none)"
    if isinstance(node, dict):
        raise PromptError(f"placeholder '{{{{{dotted}}}}}' resolves to an object, not text")
    return str(node)


def render_prompt(kind: str, payload: dict[str, Any], *, allowed_entities: list[str]) -> str:
    """Fill a template from a payload. Deterministic; refusals over guesses."""
    if kind not in ("letter", "note"):
        raise PromptError(f"unknown template kind '{kind}'")
    template = T_LETTER if kind == "letter" else T_NOTE
    view = dict(payload)
    view["allowed_entities"] = ", ".join(sorted(allowed_entities))
    view["checkable_claims_table"] = fmt_claims_for_prompt(payload["checkable_claims_table"])
    if kind == "note":
        house = payload.get("house")
        if not isinstance(house, dict) or "prior" not in house:
            raise PromptError("placeholder '{{house.prior}}' unresolved by payload")
        prior = house["prior"]
        if prior not in PRIOR_GLOSS:
            raise PromptError(f"no gloss for prior '{prior}'")
        view["prior_gloss"] = PRIOR_GLOSS[prior]

    def replace(match: re.Match[str]) -> str:
        return _lookup(view, match.group(1))

    return _PLACEHOLDER.sub(replace, template)
