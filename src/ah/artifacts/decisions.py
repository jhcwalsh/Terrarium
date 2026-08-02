"""The decision payload contract (retrofit R-1, DN-5) — shape only.

Defined BEFORE WP4.6/4.7 exist so the decision windows are born conforming:
a window carries a LIST of typed actions (a singleton is a list of one,
never a special case), an empty list is the meaningful "reached the window,
chose to do nothing" state — structurally distinct from a window that was
never reached — and the verb enum already declares the two DN-5 verbs the
engine does not implement yet, which are REJECTED loudly rather than
silently dropped.

``cost_charged`` is engine-written, never accepted from a client: the only
writer is :func:`engine_charge`. No behaviour lives here — validation and
round-trip only; the engine work that consumes these shapes is scheduled
later and a record written today replays identically when it lands.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

VERBS = ("rebalance_public", "set_pacing", "sell_secondary")
IMPLEMENTED_VERBS = ("rebalance_public",)
STATUSES = ("reached", "not_reached")


class DecisionError(ValueError):
    """A decision payload the contract refuses."""


class UnimplementedVerbError(DecisionError):
    """A declared verb whose engine work has not landed yet — rejected, not dropped."""


@dataclass(frozen=True)
class Action:
    verb: str
    payload: dict[str, Any]
    cost_charged: float | None = None  # engine-written, never client-supplied


@dataclass(frozen=True)
class DecisionWindow:
    window_id: int
    actions: tuple[Action, ...]
    submitted_at: str
    status: str


def action_from_client(doc: dict[str, Any]) -> Action:
    """Parse one client-supplied action; the contract's refusals live here."""
    if "cost_charged" in doc:
        raise DecisionError("cost_charged is engine-written and never accepted from the client")
    unknown = set(doc) - {"verb", "payload"}
    if unknown:
        raise DecisionError(f"unknown action keys: {sorted(unknown)}")
    verb = doc.get("verb")
    if verb not in VERBS:
        raise DecisionError(f"unknown verb {verb!r}; declared verbs: {VERBS}")
    if verb not in IMPLEMENTED_VERBS:
        raise UnimplementedVerbError(
            f"verb '{verb}' is declared but not yet implemented; it is rejected, not dropped"
        )
    payload = doc.get("payload")
    if not isinstance(payload, dict):
        raise DecisionError("payload must be an object (verb-specific)")
    return Action(verb=verb, payload=payload)


def window_from_client(doc: dict[str, Any]) -> DecisionWindow:
    unknown = set(doc) - {"window_id", "actions", "submitted_at", "status"}
    if unknown:
        raise DecisionError(f"unknown window keys: {sorted(unknown)}")
    window_id = doc.get("window_id")
    if not isinstance(window_id, int) or window_id < 1:
        raise DecisionError("window_id must be an int >= 1")
    status = doc.get("status")
    if status not in STATUSES:
        raise DecisionError(f"status must be one of {STATUSES}")
    raw_actions = doc.get("actions")
    if not isinstance(raw_actions, list):
        raise DecisionError("actions must be a list (a singleton is a list of one)")
    if status == "not_reached" and raw_actions:
        raise DecisionError("a not_reached window cannot carry actions")
    submitted_at = doc.get("submitted_at")
    if not isinstance(submitted_at, str) or not submitted_at:
        raise DecisionError("submitted_at is required (server timestamp, caller-supplied)")
    return DecisionWindow(
        window_id=window_id,
        actions=tuple(action_from_client(a) for a in raw_actions),
        submitted_at=submitted_at,
        status=status,
    )


def engine_charge(action: Action, cost: float) -> Action:
    """The ONLY writer of ``cost_charged`` — the engine's pen, not the client's."""
    if cost < 0.0:
        raise DecisionError("cost_charged cannot be negative")
    return replace(action, cost_charged=cost)


def window_to_document(window: DecisionWindow) -> dict[str, Any]:
    """Round-trip surface. ``cost_charged`` appears only once engine-written,
    so a client document parsed and re-emitted is byte-stable."""
    actions = []
    for a in window.actions:
        doc: dict[str, Any] = {"verb": a.verb, "payload": a.payload}
        if a.cost_charged is not None:
            doc["cost_charged"] = a.cost_charged
        actions.append(doc)
    return {
        "window_id": window.window_id,
        "actions": actions,
        "submitted_at": window.submitted_at,
        "status": window.status,
    }
