"""One interface behind every voice, and the template backend that fills it.

``Voice.render(event, context) -> Artifact``. Two backends exist:

* ``template`` — deterministic selection from a variant bank held as **data**
  (``templates/*.yaml``). A copy change must not be a code change; that is the
  whole point of the tweak loop.
* ``llm`` — an interface and a stub that raises. Wiring it is a later task, and
  the golden set already establishes that only one of the five voices in this
  build needs it (the outlier columnist).

**Where a bank has no string for a case, the marker
``[[NO TEMPLATE: class=EXX sev=N]]`` is emitted.** Prose is never improvised to
fill a gap — the marker is a measurement, and the coverage panel counts it.

**Selection is seeded, so it replays.** The index into a variant bank is a hash
of ``(world_id, month, class, key)`` — not a counter, not RNG state, not dict
order — so rendering one slate cannot change the copy in another.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from ah.narration.constants import (
    HASH_DRAW_HEX_DIGITS,
    HEX_BASE,
    MONTHS_PER_YEAR,
    NO_TEMPLATE,
    PERCENT,
)
from ah.narration.errors import NarrationError
from ah.narration.events import Event

__all__ = [
    "Artifact",
    "LlmBackend",
    "TemplateBank",
    "Voice",
    "slot_values",
    "stable_index",
]

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class Artifact:
    """One rendered item. ``template_ids`` is the audit trail back to the bank."""

    voice: str
    kind: str
    headline: str
    body: tuple[str, ...] = ()
    chips: tuple[str, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)
    template_ids: tuple[str, ...] = ()
    missing_template: bool = False

    def text(self) -> str:
        """Everything renderable as one string — what the repetition panel reads."""
        return " ".join((self.headline, *self.body))


class Voice(Protocol):
    """The one interface. Every voice is behind it, template- or llm-backed."""

    name: str
    backend: str

    def render(self, event: Event, context: dict[str, Any]) -> Artifact: ...


class LlmBackend:
    """The Tier-2 interface. A stub that raises — wiring it is a later task."""

    def __init__(self, voice: str) -> None:
        self.voice = voice
        self.backend = "llm"
        self.name = voice

    def render(self, event: Event, context: dict[str, Any]) -> Artifact:
        raise NotImplementedError(
            f"the '{self.voice}' voice is configured with the llm backend. Tier-2 generation is "
            "explicitly out of scope for the narration workbench (task non-goals: 'Any LLM "
            "call. The llm backend raises NotImplementedError')."
        )


def stable_index(n: int, *parts: Any) -> int:
    """A deterministic index into a bank of ``n`` variants.

    A hash of the parts rather than a counter: selection for one event must not
    depend on how many other events were rendered first, or a copy change in
    quarter 3 would move the copy in quarter 30.
    """
    if n <= 0:
        raise NarrationError("stable_index called on an empty bank")
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest, HEX_BASE) % n


def stable_unit(*parts: Any) -> float:
    """A deterministic draw in [0, 1) from the same hash, for rate-based rules."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    head = digest[:HASH_DRAW_HEX_DIGITS]
    return int(head, HEX_BASE) / float(HEX_BASE ** len(head))


class TemplateBank:
    """A variant bank loaded from YAML. Data, never Python."""

    def __init__(self, document: dict[str, Any], *, source: str) -> None:
        self.document = document
        self.source = source
        self.status = str(document.get("STATUS", "UNSTATED"))

    @classmethod
    def load(cls, name: str) -> TemplateBank:
        path = TEMPLATES_DIR / f"{name}.yaml"
        if not path.exists():
            raise NarrationError(f"template bank not found: {path}")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise NarrationError(f"template bank {path} did not parse to a mapping")
        return cls(document, source=str(path.name))

    def variants(self, *path: str) -> list[dict[str, Any]]:
        node: Any = self.document
        for part in path:
            if not isinstance(node, dict) or part not in node:
                return []
            node = node[part]
        return list(node) if isinstance(node, list) else []

    def pick(
        self,
        path: tuple[str, ...],
        *,
        seed_parts: tuple[Any, ...],
        cross_firing: dict[str, float] | None = None,
        flags: frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        """One variant, chosen deterministically, or ``None`` if the bank is empty.

        A variant may declare ``requires: <flag>``, and is then only admissible
        when the caller passes that flag. This is what stops a headline from
        asserting something the record contradicts — the severity-3 policy
        headline that announces a deleted sentence is only available on meetings
        where the sentence was actually deleted. Copy that claims a fact is
        bound to the fact.

        A variant tagged with a regime-vocabulary cluster (``vocab:``) is only
        admissible at the configured cross-firing rate for that cluster, drawn
        from the same hash. The draw does **not** consult the regime label: the
        requirement in DN-9 §3.1 is that copy vocabulary must not map onto the
        L2 label, and admitting a word at a fixed rate independent of the label
        satisfies it more strongly than a calibrated cross-firing would. The
        rates themselves are still open (``style.vocabulary_cross_firing``).
        """
        candidates = self.variants(*path)
        if not candidates:
            return None
        if flags is not None:
            candidates = [
                variant
                for variant in candidates
                if variant.get("requires") is None or str(variant["requires"]) in flags
            ]
            if not candidates:
                return None
        if cross_firing is not None:
            admissible = []
            for variant in candidates:
                cluster = variant.get("vocab")
                if cluster is None:
                    admissible.append(variant)
                    continue
                rate = cross_firing.get(str(cluster))
                if rate is None:
                    raise NarrationError(
                        f"style.vocabulary_cross_firing has no rate for cluster '{cluster}', "
                        f"used by a variant in {self.source}."
                    )
                if stable_unit(*seed_parts, cluster) < float(rate):
                    admissible.append(variant)
            candidates = admissible or [v for v in candidates if v.get("vocab") is None]
            if not candidates:
                return None
        return candidates[stable_index(len(candidates), *seed_parts)]


def fill(template: str, slots: dict[str, Any], *, source: str) -> str:
    """Format a template string, refusing rather than papering over a missing slot."""
    try:
        return template.format(**slots)
    except KeyError as exc:
        raise NarrationError(
            f"template in {source} references slot {exc} which the event does not carry. "
            "Templates render from trigger values; a slot with no value is a bank defect."
        ) from exc


def no_template(event: Event) -> str:
    """The marker. Copy is never improvised to fill a gap."""
    return NO_TEMPLATE.format(cls=event.cls, sev=event.severity)


def slot_values(event: Event, context: dict[str, Any]) -> dict[str, Any]:
    """Every slot a template for this event may reference.

    Deliberately flat and deliberately pre-formatted: a template bank is edited
    by someone who is not reading Python, so ``{dd_pct}`` must already be
    ``24`` rather than ``-0.2431``.
    """
    trigger = event.trigger_values
    slots: dict[str, Any] = {
        "month": event.month,
        "year": (event.month - 1) // MONTHS_PER_YEAR + 1,
        "severity": event.severity,
        "panel": event.panel,
        "slot": event.slot,
        "delta_label": event.delta["label"],
        "delta_value": event.delta["value"],
        "delta_units": event.delta["units"],
        "month_name": context.get("month_name", ""),
    }
    for key, value in trigger.items():
        slots[key] = value
    if event.cls == "E01":
        move_bp = float(event.delta["value"])
        slots["move_bp"] = f"{abs(move_bp):.0f}"
        slots["verb"] = "raises" if move_bp > 0 else "lowers" if move_bp < 0 else "holds"
        slots["target_pct"] = f"{float(trigger['target']):.2f}"
        slots["anchor_pct"] = f"{float(trigger['anchor_implied']):.2f}"
        slots["smoothed_pct"] = f"{float(trigger['smoothed_anchor']):.2f}"
        slots["epsilon_bp"] = f"{float(trigger['epsilon']) * PERCENT:+.0f}"
    if event.cls in {"E02", "E03", "E04"}:
        slots["actual_fmt"] = f"{float(trigger['actual']):.1f}"
        slots["consensus_fmt"] = f"{float(trigger['consensus']):.1f}"
        slots["surprise_sd_fmt"] = f"{float(trigger['surprise_sd']):+.1f}"
        slots["direction"] = "above" if float(trigger["surprise"]) > 0 else "below"
    if event.cls == "E05":
        slots["r_pct"] = f"{float(trigger['r_eq']) * PERCENT:+.1f}"
        slots["abs_r_pct"] = f"{abs(float(trigger['r_eq'])) * PERCENT:.1f}"
        slots["verb"] = "add" if float(trigger["r_eq"]) > 0 else "give up"
    if event.cls == "E06":
        slots["delta_bp_fmt"] = f"{float(trigger['delta_bp']):+.0f}"
        slots["level_fmt"] = f"{float(trigger['level']):.2f}"
    if event.cls == "E07":
        slots["spread_fmt"] = f"{float(trigger['spread_2s10s']):+.0f}"
        slots["prior_fmt"] = f"{float(trigger['prior']):+.0f}"
    if event.cls == "E08":
        slots["oas_fmt"] = f"{float(trigger['hy_oas']):.0f}"
        slots["delta_bp_fmt"] = f"{float(trigger['delta_bp']):+.0f}"
    if event.cls == "E09":
        slots["vol_fmt"] = f"{float(trigger['vol']):.0f}"
    if event.cls == "E10":
        slots["dd_pct"] = f"{abs(float(trigger['drawdown'])) * PERCENT:.0f}"
        slots["milestone_pct"] = f"{float(trigger['milestone']) * PERCENT:.0f}"
    if event.cls == "E11":
        slots["prior_dd_pct"] = f"{float(trigger['prior_drawdown']) * PERCENT:.0f}"
        slots["off_low_pct"] = f"{float(trigger['off_low']) * PERCENT:.0f}"
    if event.cls == "E21":
        slots["equity_year_fmt"] = f"{float(trigger['equity_year_pct']):+.1f}"
    return slots
