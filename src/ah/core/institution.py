"""Institution simulator + allocator decisions (STEP0-PLAN §WP0.5).

An institution starts from a fixed sleeve mix and, at each annual decision point
(month ``12*year - 1`` for years 1-9), takes one action —
``hold | derisk | leanin | secondary`` — then rebalances to its target mix.

Engine returns are in *percent* (see ``engine`` module notes); this simulator
converts them to decimal and applies **limited liability**: a sleeve's monthly
gross factor is floored at 0, so a sleeve value can never go negative (a toy but
economically sound stance that also guarantees the WP0.5 invariants — weights sum
to 1, no negative sleeves — for any engine magnitude).

Like the engine, this module is narrative-blind: it consumes ``EnginePaths`` and a
``NumericWorld``, never a WorldSpec narrative field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ah.core.engine import REPORTED_SLEEVES, EnginePaths, run_path
from ah.core.numericworld import NumericWorld

# Sleeve order matches the engine's ASSETS (weights_over_time columns).
SLEEVES: tuple[str, ...] = (
    "equity",
    "bonds",
    "hy",
    "commodities",
    "reits",
    "pe",
    "pc",
    "re",
)

START_MIX: dict[str, float] = {
    "equity": 0.30,
    "bonds": 0.10,
    "hy": 0.05,
    "commodities": 0.05,
    "reits": 0.05,
    "pe": 0.25,
    "pc": 0.10,
    "re": 0.10,
}

GROWTH: tuple[str, ...] = ("equity", "pe")
DEFENSIVE: tuple[str, ...] = ("bonds", "pc")
ACTIONS: frozenset[str] = frozenset({"hold", "derisk", "leanin", "secondary"})

_SHIFT_PTS = 0.10  # derisk/leanin move 10 percentage points
_SECONDARY_SELL_CAP = 0.08  # sell up to 8pts of PE
_SECONDARY_DISCOUNT = 0.18  # PE sold at 0.82 -> 18% haircut on the sold portion
_SECONDARY_TARGET_MOVE = 0.08  # target pe -.08 -> bonds +.08
_INITIAL_VALUE = 100.0  # growth of 100


@dataclass(frozen=True)
class InstitutionResult:
    months: int
    total: np.ndarray  # (NM,) portfolio value over time (growth of 100)
    weights: np.ndarray  # (NM, len(SLEEVES)) post-month sleeve weights
    final_value: float
    decisions: list[tuple[int, str]]
    use_reported: bool


def decision_months(nm: int) -> list[int]:
    """Annual decision points: month 12*year - 1 for years 1-9, within the horizon."""
    return [12 * y - 1 for y in range(1, 10) if 12 * y - 1 < nm]


def _shift(
    targets: dict[str, float], frm: tuple[str, ...], to: tuple[str, ...], amount: float
) -> None:
    """Move ``amount`` from group ``frm`` to group ``to``, preserving in-group proportions."""
    fsum = sum(targets[k] for k in frm)
    tsum = sum(targets[k] for k in to)
    amt = min(amount, fsum)
    if fsum <= 0 or tsum <= 0 or amt <= 0:
        return
    for k in frm:
        targets[k] -= amt * (targets[k] / fsum)
    for k in to:
        targets[k] += amt * (targets[k] / tsum)


def _renormalize(targets: dict[str, float]) -> None:
    total = sum(targets.values())
    if total > 0:
        for k in targets:
            targets[k] /= total


def simulate_institution(
    paths: EnginePaths,
    decisions: Mapping[int, str] | None = None,
    *,
    use_reported: bool = False,
) -> InstitutionResult:
    """Run the institution over one engine path with a per-decision-month action map.

    ``decisions`` maps a decision month to an action; unmapped decision months
    default to ``hold``. Unknown actions are treated as ``hold``.
    """
    nm = paths.months
    dmap = dict(decisions or {})
    dmonths = set(decision_months(nm))
    targets = dict(START_MIX)
    value = {s: START_MIX[s] * _INITIAL_VALUE for s in SLEEVES}

    total_series = np.empty(nm)
    weights_series = np.empty((nm, len(SLEEVES)))
    decision_log: list[tuple[int, str]] = []

    for m in range(nm):
        # Apply the month's returns (percent -> decimal), limited-liability floor.
        for s in SLEEVES:
            use_rep = use_reported and s in REPORTED_SLEEVES
            r = paths.reported[s][m] if use_rep else paths.returns[s][m]
            value[s] *= max(0.0, 1.0 + r / 100.0)
        total = sum(value.values())

        if m in dmonths:
            action = dmap.get(m, "hold")
            if action not in ACTIONS:
                action = "hold"
            decision_log.append((m, action))
            if action == "derisk":
                _shift(targets, GROWTH, DEFENSIVE, _SHIFT_PTS)
            elif action == "leanin":
                _shift(targets, DEFENSIVE, GROWTH, _SHIFT_PTS)
            elif action == "secondary":
                w_pe = value["pe"] / total if total > 0 else 0.0
                sold = min(_SECONDARY_SELL_CAP, w_pe)
                total *= 1.0 - sold * _SECONDARY_DISCOUNT
                removed = min(_SECONDARY_TARGET_MOVE, targets["pe"])
                targets["pe"] -= removed
                targets["bonds"] += removed
                _renormalize(targets)
            # annual rebalance to target mix
            for s in SLEEVES:
                value[s] = targets[s] * total

        total_series[m] = total
        for i, s in enumerate(SLEEVES):
            weights_series[m, i] = (value[s] / total) if total > 0 else 0.0

    return InstitutionResult(
        months=nm,
        total=total_series,
        weights=weights_series,
        final_value=float(total_series[-1]),
        decisions=decision_log,
        use_reported=use_reported,
    )


def hold_course_twin(
    world: NumericWorld, seed: int, *, use_reported: bool = False
) -> InstitutionResult:
    """The passive benchmark: rebalance to the start mix every year, never deviate."""
    return simulate_institution(run_path(world, seed), None, use_reported=use_reported)


def decision_alpha(
    world: NumericWorld,
    seed: int,
    decisions: Mapping[int, str],
    *,
    use_reported: bool = False,
) -> float:
    """Final-value difference between an active decision set and the hold-course twin."""
    paths = run_path(world, seed)
    active = simulate_institution(paths, decisions, use_reported=use_reported)
    twin = simulate_institution(paths, None, use_reported=use_reported)
    return active.final_value - twin.final_value
