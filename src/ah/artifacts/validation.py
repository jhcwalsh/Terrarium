"""Actor validation study machinery (WP4.9) — measure, publish, defer honestly.

What runs NOW: the ablation arms (heuristic, seeded random-within-bounds,
hold-course) and the model committee on identical worlds and seeds, with
the documented pathology measurements the plan names — persona/prompt
sensitivity, action-level fidelity, and effect sizes reported with
dispersion across worlds (the anti-inflation discipline). What is
DEFERRED, by the owner's kickoff decision D-K4-5: the human-cohort arm —
the owner is the first cohort when the app exists, external cohorts
later. The too-rational pathology is DEFINED against human cohorts, so
it is recorded as not-yet-measurable rather than proxied into a number
that would be quoted without its caveat.

Standing rule, unchanged: NO client-facing actor claim precedes the full
study. This module computes; the sealed Step 5 metrics judge outcomes;
nothing here scores itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ah.artifacts import committee as com
from ah.artifacts.live import RevealedTape

DECIDER_ARMS = ("heuristic", "random_within_bounds", "hold_course")


class ValidationError(ValueError):
    """A study configuration the harness refuses."""


@dataclass(frozen=True)
class DecisionRecord:
    world_seed: int
    window_id: int
    arm: str  # heuristic | random_within_bounds | hold_course | model:<persona>
    n_actions: int
    target_weight: float | None  # rebalance target if any
    decided_by: str  # rule | model | heuristic_fallback


def _drifted_weights(tape: np.ndarray, months: int, start_public: float = 0.60) -> dict[str, float]:
    """The reported public weight after the revealed span's drift — the same
    world state every arm sees at a window (identical or it means nothing)."""
    public_growth = float(np.prod(1.0 + tape[:months, 0]))
    private_growth = float(np.prod(1.0 + 0.5 * tape[:months, 0] + 0.002))
    p = start_public * public_growth
    q = (1.0 - start_public) * private_growth
    return {"public_equity": p / (p + q), "pm_buyout": q / (p + q)}


def run_ablation_arms(
    tape: np.ndarray,
    *,
    world_seed: int,
    window_quarters: tuple[int, ...] = (0, 4, 8),
) -> list[DecisionRecord]:
    """The three ablation arms over one world's decision windows."""
    records: list[DecisionRecord] = []
    for window_id, quarter in enumerate(window_quarters, start=1):
        months = max(1, quarter * 3)
        weights = _drifted_weights(tape, months)
        for arm in DECIDER_ARMS:
            if arm == "heuristic":
                actions, _ = com.heuristic_decision(weights_reported=weights)
            elif arm == "random_within_bounds":
                actions, _ = com.random_within_bounds(base_seed=world_seed, window_id=window_id)
            else:
                actions, _ = com.hold_course()
            target = actions[0]["payload"]["target_weights"]["public_equity"] if actions else None
            records.append(
                DecisionRecord(
                    world_seed=world_seed,
                    window_id=window_id,
                    arm=arm,
                    n_actions=len(actions),
                    target_weight=target,
                    decided_by="rule",
                )
            )
    return records


def run_model_arm(
    tape: np.ndarray,
    *,
    world_seed: int,
    personas: list[com.Persona],
    decider: Callable[[str], str],
    model_id: str,
    window_quarters: tuple[int, ...] = (0, 4, 8),
) -> list[DecisionRecord]:
    """The committee across personas — same worlds, same windows, same data."""
    records: list[DecisionRecord] = []
    for window_id, quarter in enumerate(window_quarters, start=1):
        months = max(1, quarter * 3)
        weights = _drifted_weights(tape, months)
        briefing = com.build_briefing(
            revealed=RevealedTape.cut(tape, months),
            weights_reported=weights,
            coverage_liquid=0.40,
            wire_items=["(study world: synthetic wire)"],
        )
        for persona in personas:
            decision = com.committee_decide(
                persona=persona,
                briefing=briefing,
                decider=decider,
                model_id=model_id,
                window_id=window_id,
                submitted_at="2026-08-02T00:00:00+00:00",
                weights_reported=weights,
            )
            first = decision.window.actions[0] if decision.window.actions else None
            target = first.payload.get("target_weights", {}).get("public_equity") if first else None
            records.append(
                DecisionRecord(
                    world_seed=world_seed,
                    window_id=window_id,
                    arm=f"model:{persona.persona_id}",
                    n_actions=len(decision.window.actions),
                    target_weight=target,
                    decided_by=decision.decided_by,
                )
            )
    return records


# -- pathology measurements -------------------------------------------------- #


def action_rates(records: list[DecisionRecord]) -> dict[str, float]:
    """Fraction of windows each arm acted in — action-level fidelity's base."""
    arms: dict[str, list[int]] = {}
    for r in records:
        arms.setdefault(r.arm, []).append(1 if r.n_actions > 0 else 0)
    return {arm: float(np.mean(v)) for arm, v in sorted(arms.items())}


def fallback_rate(records: list[DecisionRecord]) -> float:
    """Of the model-arm decisions, how many fell back to the heuristic —
    the validity half of action-level fidelity."""
    model = [r for r in records if r.arm.startswith("model:")]
    if not model:
        raise ValidationError("no model-arm records")
    return float(np.mean([r.decided_by == "heuristic_fallback" for r in model]))


def persona_sensitivity(records: list[DecisionRecord]) -> float:
    """Fraction of (world, window) cells where personas DISAGREE.

    Disagreement = differing action counts or rebalance targets differing
    by more than 1pt. The plan's framing holds: this is measured as PROMPT
    SENSITIVITY, a pathology to report — not persona insight to sell.
    """
    cells: dict[tuple[int, int], list[DecisionRecord]] = {}
    for r in records:
        if r.arm.startswith("model:"):
            cells.setdefault((r.world_seed, r.window_id), []).append(r)
    if not cells:
        raise ValidationError("no model-arm records")
    disagreements = 0
    for cell in cells.values():
        counts = {r.n_actions for r in cell}
        targets = {round(r.target_weight, 2) for r in cell if r.target_weight is not None}
        if len(counts) > 1 or len(targets) > 1:
            disagreements += 1
    return disagreements / len(cells)


def effect_size_with_dispersion(
    records: list[DecisionRecord], arm_a: str, arm_b: str
) -> dict[str, float]:
    """Per-world action-rate difference between two arms, WITH dispersion.

    The anti-inflation rule made mechanical: the mean difference never
    travels without its across-world standard deviation and world count —
    a single decade's difference is an anecdote, and this function will
    not emit one without saying so (n_worlds rides in the result).
    """
    per_world: dict[int, dict[str, list[int]]] = {}
    for r in records:
        if r.arm in (arm_a, arm_b):
            per_world.setdefault(r.world_seed, {}).setdefault(r.arm, []).append(
                1 if r.n_actions > 0 else 0
            )
    diffs = [
        float(np.mean(arms[arm_a]) - np.mean(arms[arm_b]))
        for arms in per_world.values()
        if arm_a in arms and arm_b in arms
    ]
    if not diffs:
        raise ValidationError(f"no worlds carry both arms {arm_a!r} and {arm_b!r}")
    return {
        "mean_diff": float(np.mean(diffs)),
        "sd_across_worlds": float(np.std(diffs, ddof=1)) if len(diffs) > 1 else float("nan"),
        "n_worlds": float(len(diffs)),
    }
