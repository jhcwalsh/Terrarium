"""Human actor windows (WP4.7) — calendars, triggers, playbooks, wargames.

Real decisions are not uniformly spaced: calendar windows carry the
routine cadence, and EVENT windows open when the world demands one
(spread breach, gating, mark catch-up, collateral call — the plan's
list, closed). Windows carry the retrofit's typed decision contract
(``ah.artifacts.decisions``) — a LIST of actions per window, and the
RFR-89 re-check lives in this WP's tests: nothing here assumes a
singleton.

The pre-commitment playbook is written at t₀ and FROZEN (hashed): a
committee states its conditional rules before the decade starts, the
world fires triggers, executions are recorded, and the output shapes
match the SEALED adherence metric's input format exactly — but this
module never imports the metric: the defendant produces evidence, the
Step 5 harness judges it (the same judge/defendant separation as the
episode scorer).

Wargame mode: same world, same seed, N independent institutions.
Anything else refuses — the sealed comparison rule says identical or it
means nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from ah.artifacts.decisions import DecisionWindow
from ah.core.digest import canonical_json

EVENT_TRIGGERS = ("spread_breach", "gating", "mark_catch_up", "collateral_call")


class WindowError(ValueError):
    """A window, playbook, or wargame operation the contract refuses."""


# -- window scheduling ------------------------------------------------------ #


@dataclass(frozen=True)
class WindowSlot:
    window_id: int
    quarter: int
    kind: str  # calendar | event
    trigger: str | None = None


def calendar_windows(horizon_quarters: int, *, cadence_quarters: int = 4) -> list[WindowSlot]:
    """The routine cadence: window 1 at t₀, then every ``cadence_quarters``."""
    if horizon_quarters <= 0 or cadence_quarters <= 0:
        raise WindowError("horizon and cadence must be positive")
    return [
        WindowSlot(window_id=i + 1, quarter=q, kind="calendar")
        for i, q in enumerate(range(0, horizon_quarters, cadence_quarters))
    ]


def event_window(*, window_id: int, quarter: int, trigger: str) -> WindowSlot:
    """An unscheduled window, opened because the world demanded one."""
    if trigger not in EVENT_TRIGGERS:
        raise WindowError(f"unknown trigger '{trigger}'; the closed list is {EVENT_TRIGGERS}")
    return WindowSlot(window_id=window_id, quarter=quarter, kind="event", trigger=trigger)


# -- the window log --------------------------------------------------------- #


class WindowLog:
    """Decisions as they were made, in order, typed, append-only in use."""

    def __init__(self) -> None:
        self._windows: dict[int, DecisionWindow] = {}
        self._slots: dict[int, WindowSlot] = {}

    def record(self, slot: WindowSlot, window: DecisionWindow) -> None:
        if window.window_id != slot.window_id:
            raise WindowError("window/slot id mismatch")
        if slot.window_id in self._windows:
            raise WindowError(f"window {slot.window_id} already recorded — the log is append-only")
        self._windows[slot.window_id] = window
        self._slots[slot.window_id] = slot

    def windows(self) -> list[DecisionWindow]:
        return [self._windows[k] for k in sorted(self._windows)]

    def actions_total(self) -> int:
        """Total actions across all windows — a LIST sum, never a count of
        windows (the RFR-89 distinction, load-bearing here)."""
        return sum(len(w.actions) for w in self.windows())


# -- the pre-commitment playbook -------------------------------------------- #


@dataclass
class PlaybookRule:
    rule_id: str
    trigger: str  # one of EVENT_TRIGGERS
    intent: str  # the committee's own words, written at t0

    def __post_init__(self) -> None:
        if self.trigger not in EVENT_TRIGGERS:
            raise WindowError(f"rule '{self.rule_id}': unknown trigger '{self.trigger}'")
        if not self.intent.strip():
            raise WindowError(f"rule '{self.rule_id}': an empty intent is not a rule")


class Playbook:
    """Conditional rules written at t₀, frozen by hash, measured when fired.

    ``planned()`` / ``executed()`` emit exactly the shapes the SEALED
    adherence metric consumes (`rule_id`/`triggered`, `rule_id`/`followed`)
    — evidence in the judge's format, produced without importing the judge.
    """

    def __init__(self, rules: list[PlaybookRule]) -> None:
        if not rules:
            raise WindowError("a playbook with no rules is not a playbook")
        ids = [r.rule_id for r in rules]
        if len(set(ids)) != len(ids):
            raise WindowError("duplicate rule_ids")
        self._rules = {r.rule_id: r for r in rules}
        self._triggered: set[str] = set()
        self._followed: dict[str, bool] = {}
        self.t0_hash = (
            "sha256:"
            + hashlib.sha256(
                canonical_json(
                    [
                        {"rule_id": r.rule_id, "trigger": r.trigger, "intent": r.intent}
                        for r in rules
                    ]
                ).encode("utf-8")
            ).hexdigest()
        )

    def fire(self, trigger: str) -> list[str]:
        """The world fires a trigger; every rule conditioned on it is now live."""
        if trigger not in EVENT_TRIGGERS:
            raise WindowError(f"unknown trigger '{trigger}'")
        fired = [r.rule_id for r in self._rules.values() if r.trigger == trigger]
        self._triggered.update(fired)
        return sorted(fired)

    def record_execution(self, rule_id: str, *, followed: bool) -> None:
        if rule_id not in self._rules:
            raise WindowError(f"unknown rule '{rule_id}'")
        if rule_id not in self._triggered:
            raise WindowError(
                f"rule '{rule_id}' never triggered — adherence is measured when the "
                "moment comes, not on paper"
            )
        self._followed[rule_id] = followed

    def planned(self) -> list[dict[str, Any]]:
        return [
            {"rule_id": rid, "triggered": rid in self._triggered} for rid in sorted(self._rules)
        ]

    def executed(self) -> list[dict[str, Any]]:
        return [
            {"rule_id": rid, "followed": followed}
            for rid, followed in sorted(self._followed.items())
        ]


# -- wargame mode ----------------------------------------------------------- #


@dataclass
class WargameSession:
    """Same world, same seed, independent institutions — or nothing."""

    world_id: str
    seed: int
    decision_alpha_version: str
    teams: dict[str, WindowLog] = field(default_factory=dict)

    def add_team(self, name: str) -> WindowLog:
        if not name:
            raise WindowError("a team needs a name")
        if name in self.teams:
            raise WindowError(f"duplicate team '{name}'")
        log = WindowLog()
        self.teams[name] = log
        return log

    def export(self) -> dict[str, Any]:
        """The cohort-exercise export: every team's path through the decade.

        Scores are NOT computed here — the sealed Step 5 metrics judge;
        this export is their evidence, plus the leaderboard's scope key.
        """
        from ah.artifacts.decisions import window_to_document

        return {
            "world_id": self.world_id,
            "seed": self.seed,
            "decision_alpha_version": self.decision_alpha_version,
            "teams": {
                name: {
                    "windows": [window_to_document(w) for w in log.windows()],
                    "actions_total": log.actions_total(),
                }
                for name, log in sorted(self.teams.items())
            },
        }
