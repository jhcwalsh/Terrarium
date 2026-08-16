"""Event detection and severity — the deterministic pass DN-9 §3.1 puts first.

The event stream exists *before* any copy does. It is what the tests inspect,
what ``events.jsonl`` carries, and what a second template pack would re-render in
a different voice.

**The point/state distinction is load-bearing.** A point event fires on the
period it occurs. A state event describes a sustained condition and fires on
**onset or milestone crossing only**, with consecutive periods grouped into one
episode carrying ``episode_id`` and ``episode_month``. A state class that fires
every period it holds is a defect: the spike hit it and produced 72 severity-3
events per decade against a target of 4-10.

**Every event carries a ``panel`` and a ``delta``** (DN-9 §B.2). An event that
explains nothing visible on the dashboard is not emitted — "no anchor, no
announcement" — and :func:`detect` asserts this rather than warning about it.

Detection rules are thresholds on *revealed state*, never on the regime label
(DN-9 §3.1): the player infers the regime, they are not told it. No detector in
this module reads ``world.regime``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.narration.adapters.world import WorldSeries
from ah.narration.anchor import AnchorParams, AnchorTerms, decompose
from ah.narration.constants import (
    BPS_PER_PP,
    KIND_OF_CLASS,
    MONTHS_PER_QUARTER,
    MONTHS_PER_YEAR,
    PANEL_OF_SLOT,
    PERCENT,
    RECORD_PRECISION,
    SLOT_OF_CLASS,
)
from ah.narration.errors import NarrationError

__all__ = [
    "AnchorParams",
    "ConsensusParams",
    "Event",
    "EventParams",
    "detect",
    "severity",
]

#: Vol-state names, in ascending order. Structural: the number of states is
#: ``len(cuts) + 1`` and the names are labels, not thresholds.
_VOL_STATES = ("quiet", "ordinary", "elevated", "extreme", "extreme+")

#: DN-9 §3.2 fixes E21 (anniversary / retrospective) at severity 1 flatly — it
#: is a calendar event with no trigger to score, so there is nothing to band.
_E21_SEVERITY = 1


@dataclass(frozen=True)
class ConsensusParams:
    """The fictional street forecast (DN-9 §4.2). All four are open decisions."""

    persistence_weight: float
    bias: float
    dispersion: float
    n_forecasters: int


@dataclass(frozen=True)
class EventParams:
    """Every value detection needs, already resolved from ``voices.yaml``."""

    cuts: tuple[float, float, float]
    class_scale: dict[str, float]
    hard_overrides: dict[str, int]
    z_window_months: int
    thresholds: dict[str, Any]
    milestones: tuple[float, ...]
    meeting_months: tuple[int, ...]
    anchor: AnchorParams
    consensus: ConsensusParams
    book_available: bool


@dataclass(frozen=True)
class Event:
    """One typed, timestamped, severity-scored event (DN-9 §3.1)."""

    month: int
    cls: str
    severity: int
    kind: str
    slot: str
    panel: str
    delta: dict[str, Any]
    trigger_values: dict[str, Any]
    entity_refs: tuple[str, ...] = ()
    release_month: int | None = None
    episode_id: str | None = None
    episode_month: int | None = None
    anchor_terms: AnchorTerms | None = field(default=None, repr=False)

    def as_record(self) -> dict[str, Any]:
        """The ``events.jsonl`` row. Ordered, rounded, JSON-safe."""
        return {
            "month": self.month,
            "class": self.cls,
            "kind": self.kind,
            "severity": self.severity,
            "slot": self.slot,
            "panel": self.panel,
            "delta": _round(self.delta),
            "trigger_values": _round(self.trigger_values),
            "entity_refs": list(self.entity_refs),
            "release_month": self.release_month if self.release_month is not None else self.month,
            "episode_id": self.episode_id,
            "episode_month": self.episode_month,
            "anchor": self.anchor_terms.as_record() if self.anchor_terms else None,
        }


def _round(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return round(float(value), RECORD_PRECISION)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


def severity(cls: str, z: float, params: EventParams) -> int:
    """Band a normalised trigger onto 0..3.

    Cut-points, per-class scales and hard overrides all come from config. The
    per-class scale is *required* rather than defaulted: a class with no entry
    would silently be scored on a different scale from every other class, which
    is exactly the kind of implicit decision this layer refuses.
    """
    if cls in params.hard_overrides:
        return int(params.hard_overrides[cls])
    if cls not in params.class_scale:
        raise NarrationError(
            f"severity.class_scale has no entry for {cls}. Every class that can fire needs a "
            "scale, or its severity is on a different footing from the others by accident."
        )
    scaled = abs(z) / float(params.class_scale[cls])
    low, mid, high = params.cuts
    if scaled < low:
        return 0
    if scaled < mid:
        return 1
    if scaled < high:
        return 2
    return 3


def _delta(label: str, value: float, units: str) -> dict[str, Any]:
    return {"label": label, "value": float(value), "units": units}


def _mk(
    month: int,
    cls: str,
    z: float,
    params: EventParams,
    delta: dict[str, Any],
    trigger: dict[str, Any],
    **extra: Any,
) -> Event:
    return Event(
        month=month,
        cls=cls,
        severity=severity(cls, z, params),
        kind=KIND_OF_CLASS[cls],
        slot=SLOT_OF_CLASS[cls],
        panel=PANEL_OF_SLOT[SLOT_OF_CLASS[cls]],
        delta=delta,
        trigger_values=trigger,
        **extra,
    )


def _window_stats(series: np.ndarray, index: int, window: int) -> tuple[float, float] | None:
    """``(mean, sd)`` over the trailing window, or ``None`` before it is full.

    Nothing z-scored fires until a full window of history exists. That is a
    consequence of ``severity.z_window_months``, stated in its registry entry,
    not a hidden warm-up.
    """
    if index < window:
        return None
    past = series[index - window : index]
    if not np.all(np.isfinite(past)):
        return None
    sd = float(np.std(past))
    if sd <= 0.0:
        return None
    return float(np.mean(past)), sd


def _consensus(series: np.ndarray, index: int, cp: ConsensusParams) -> float | None:
    """Persistence-weighted street forecast from revealed state only (§4.2)."""
    # 2, not MONTHS_PER_QUARTER - 1: the consensus reads month-1 and month-2, so
    # the guard is the arity of the expression rather than a fact about quarters.
    if index < 2:
        return None
    previous, before = series[index - 1], series[index - 2]
    if not (np.isfinite(previous) and np.isfinite(before) and np.isfinite(series[index])):
        return None
    return float(previous + cp.persistence_weight * (previous - before) + cp.bias)


# --------------------------------------------------------------------------- #
# point classes
# --------------------------------------------------------------------------- #


def _policy(
    world: WorldSeries, params: EventParams, terms: list[AnchorTerms | None]
) -> list[Event]:
    events: list[Event] = []
    previous_target: float | None = None
    threshold = float(params.thresholds["E01"])
    for index in range(world.months):
        month = index + 1
        if (index % MONTHS_PER_YEAR) + 1 not in params.meeting_months:
            continue
        decomposition = terms[index]
        if decomposition is None:
            continue
        move = 0.0 if previous_target is None else decomposition.realised - previous_target
        events.append(
            _mk(
                month,
                "E01",
                decomposition.epsilon / threshold,
                params,
                _delta(
                    "unchanged" if move == 0.0 else f"policy {move * BPS_PER_PP:+.0f}bp",
                    move * BPS_PER_PP,
                    "bp",
                ),
                {
                    "target": decomposition.realised,
                    "prior_target": previous_target,
                    "anchor_implied": decomposition.anchor,
                    "smoothed_anchor": decomposition.smoothed,
                    "epsilon": decomposition.epsilon,
                    "consensus_target": decomposition.smoothed,
                },
                anchor_terms=decomposition,
            )
        )
        previous_target = decomposition.realised
    return events


def _print_event(
    world: WorldSeries,
    params: EventParams,
    *,
    cls: str,
    series_name: str,
    quarterly: bool,
    units: str,
    label: str,
) -> list[Event]:
    """The three-beat data day (§4.2) for one scheduled release."""
    series = world.series[series_name]
    threshold = float(params.thresholds[cls])
    cp = params.consensus
    events: list[Event] = []
    for index in range(world.months):
        month = index + 1
        if quarterly and month % MONTHS_PER_QUARTER != 0:
            continue
        consensus = _consensus(series, index, cp)
        if consensus is None:
            continue
        actual = float(series[index])
        surprise = actual - consensus
        change = actual - float(series[index - 1])
        events.append(
            _mk(
                month,
                cls,
                surprise / threshold,
                params,
                _delta(f"{label} {change:+.1f}{units}", change, units),
                {
                    "actual": actual,
                    "consensus": consensus,
                    "surprise": surprise,
                    "surprise_sd": surprise / cp.dispersion,
                    "n_forecasters": cp.n_forecasters,
                    "series": series_name,
                },
            )
        )
    return events


def _equity_move(world: WorldSeries, params: EventParams) -> list[Event]:
    returns = world.series["equity_return"]
    k = float(params.thresholds["E05"])
    events: list[Event] = []
    for index in range(world.months):
        stats = _window_stats(returns, index, params.z_window_months)
        if stats is None:
            continue
        _, sigma = stats
        move = float(returns[index])
        if abs(move) <= k * sigma:
            continue
        events.append(
            _mk(
                index + 1,
                "E05",
                move / sigma,
                params,
                _delta(f"equities {move * PERCENT:+.1f}%", move * PERCENT, "%"),
                {"r_eq": move, "sigma_hat": sigma},
            )
        )
    return events


def _rate_move(world: WorldSeries, params: EventParams) -> list[Event]:
    yields_10y = world.series["ust_10y"]
    band_bp = float(params.thresholds["E06"])
    events: list[Event] = []
    for index in range(1, world.months):
        change_bp = float(yields_10y[index] - yields_10y[index - 1]) * BPS_PER_PP
        if abs(change_bp) <= band_bp:
            continue
        events.append(
            _mk(
                index + 1,
                "E06",
                change_bp / band_bp,
                params,
                _delta(f"10y {change_bp:+.0f}bp", change_bp, "bp"),
                {"delta_bp": change_bp, "level": float(yields_10y[index])},
            )
        )
    return events


def _credit_breach(world: WorldSeries, params: EventParams) -> list[Event]:
    oas = world.series["hy_oas"]
    tiers = sorted(float(t) for t in params.thresholds["E08"])

    def tier_of(value: float) -> int:
        return sum(1 for tier in tiers if value >= tier)

    events: list[Event] = []
    for index in range(1, world.months):
        before, now = tier_of(float(oas[index - 1])), tier_of(float(oas[index]))
        if before == now:
            continue
        stats = _window_stats(np.diff(oas, prepend=oas[0]), index, params.z_window_months)
        if stats is None:
            continue
        _, sigma = stats
        change_bp = float(oas[index] - oas[index - 1])
        events.append(
            _mk(
                index + 1,
                "E08",
                change_bp / sigma,
                params,
                _delta(f"HY OAS {change_bp:+.0f}bp", change_bp, "bp"),
                {
                    "hy_oas": float(oas[index]),
                    "delta_bp": change_bp,
                    "tier": now,
                    "prior_tier": before,
                    "direction": "wider" if now > before else "tighter",
                },
            )
        )
    return events


def _recovery(world: WorldSeries, params: EventParams) -> list[Event]:
    index_series = world.series["equity_index"]
    minimum_drawdown = float(params.thresholds["E11"])
    events: list[Event] = []
    peak = float(index_series[0])
    trough = peak
    for index in range(world.months):
        level = float(index_series[index])
        if level >= peak:
            depth = 1.0 - trough / peak if peak else 0.0
            if depth >= minimum_drawdown and index:
                events.append(
                    _mk(
                        index + 1,
                        "E11",
                        depth / minimum_drawdown,
                        params,
                        _delta(f"new high, {depth * PERCENT:.0f}% recovered", depth * PERCENT, "%"),
                        {"prior_drawdown": depth, "off_low": level / trough - 1.0},
                    )
                )
            peak = level
            trough = level
        else:
            trough = min(trough, level)
    return events


def _year_end(world: WorldSeries, params: EventParams) -> list[Event]:
    index_series = world.series["equity_index"]
    events: list[Event] = []
    for index in range(MONTHS_PER_YEAR - 1, world.months, MONTHS_PER_YEAR):
        start = index - MONTHS_PER_YEAR + 1
        change = float(index_series[index] / index_series[start] - 1.0) * PERCENT
        events.append(
            Event(
                month=index + 1,
                cls="E21",
                severity=_E21_SEVERITY,
                kind=KIND_OF_CLASS["E21"],
                slot=SLOT_OF_CLASS["E21"],
                panel=PANEL_OF_SLOT[SLOT_OF_CLASS["E21"]],
                delta=_delta(f"year {change:+.1f}%", change, "%"),
                trigger_values={"year": (index + 1) // MONTHS_PER_YEAR, "equity_year_pct": change},
            )
        )
    return events


# --------------------------------------------------------------------------- #
# state classes — onset and milestone crossings only
# --------------------------------------------------------------------------- #


def _curve(world: WorldSeries, params: EventParams) -> list[Event]:
    curve = world.series["curve_2s10s"]
    dead_zone = float(params.thresholds["E07"])
    events: list[Event] = []
    inverted: bool | None = None
    episode = 0
    for index in range(world.months):
        level = float(curve[index])
        if level < -dead_zone:
            state = True
        elif level > dead_zone:
            state = False
        else:
            continue
        if inverted is None:
            inverted = state
            continue
        if state == inverted:
            continue
        inverted = state
        stats = _window_stats(curve, index, params.z_window_months)
        if stats is None:
            continue
        mean, sigma = stats
        episode += 1
        events.append(
            _mk(
                index + 1,
                "E07",
                (level - mean) / sigma,
                params,
                _delta(f"2s10s {level:+.0f}bp", level, "bp"),
                {
                    "spread_2s10s": level,
                    "prior": float(curve[index - 1]),
                    "direction": "inversion" if state else "re-steepening",
                },
                episode_id=f"E07-{episode}",
                episode_month=1,
            )
        )
    return events


def _volatility(world: WorldSeries, params: EventParams) -> list[Event]:
    if "equity_vol" not in world.series:
        return []
    vol = world.series["equity_vol"]
    cuts = sorted(float(c) for c in params.thresholds["E09"])

    def state_of(value: float) -> str:
        return _VOL_STATES[sum(1 for cut in cuts if value >= cut)]

    events: list[Event] = []
    current = state_of(float(vol[0]))
    episode = 0
    run_start = 0
    for index in range(1, world.months):
        state = state_of(float(vol[index]))
        if state == current:
            continue
        stats = _window_stats(vol, index, params.z_window_months)
        current, run_start = state, index
        if stats is None:
            continue
        mean, sigma = stats
        episode += 1
        events.append(
            _mk(
                index + 1,
                "E09",
                (float(vol[index]) - mean) / sigma,
                params,
                _delta(f"vol -> {state}", float(vol[index]) - mean, "vol pts"),
                {
                    "state": state,
                    "vol": float(vol[index]),
                    "persistence_m": index - run_start + 1,
                },
                episode_id=f"E09-{episode}",
                episode_month=1,
            )
        )
    return events


def _drawdown(world: WorldSeries, params: EventParams) -> list[Event]:
    """E10. One event per milestone crossed, one episode per drawdown.

    A new high closes the episode; the next drawdown opens a new one. The
    deepest milestone reached is remembered inside the episode so a condition
    that merely *persists* fires nothing.
    """
    index_series = world.series["equity_index"]
    milestones = tuple(sorted(float(m) for m in params.milestones))
    scale = milestones[0]
    events: list[Event] = []
    peak = float(index_series[0])
    reached = 0
    episode = 0
    episode_open = False
    onset = 0
    for index in range(world.months):
        level = float(index_series[index])
        if level >= peak:
            peak = level
            reached = 0
            episode_open = False
            continue
        depth = 1.0 - level / peak
        crossed = sum(1 for milestone in milestones if depth >= milestone)
        if crossed <= reached:
            continue
        if not episode_open:
            episode += 1
            episode_open = True
            onset = index
        for rung in range(reached, crossed):
            events.append(
                _mk(
                    index + 1,
                    "E10",
                    depth / scale,
                    params,
                    _delta(f"{depth * PERCENT:.0f}% from peak", -depth * PERCENT, "%"),
                    {
                        "drawdown": -depth,
                        "milestone": milestones[rung],
                        "peak": peak,
                    },
                    episode_id=f"E10-{episode}",
                    episode_month=index - onset + 1,
                )
            )
        reached = crossed
    return events


# --------------------------------------------------------------------------- #


def detect(world: WorldSeries, params: EventParams) -> list[Event]:
    """The full event stream for one world, sorted by ``(month, class)``.

    Sorting is documented rather than incidental: two events in the same month
    are ordered by class id, which is stable across runs, platforms and Python
    versions — unlike dict insertion order or set iteration.
    """
    terms = decompose(
        policy_rate=world.series["policy_rate"],
        cpi_yoy=world.series["cpi_yoy"],
        l1_state=world.l1_state,
        params=params.anchor,
        z_window_months=params.z_window_months,
    )
    events: list[Event] = []
    events += _policy(world, params, terms)
    events += _print_event(
        world,
        params,
        cls="E02",
        series_name="headline_cpi",
        quarterly=False,
        units="pp",
        label="CPI",
    )
    events += _print_event(
        world,
        params,
        cls="E03",
        series_name="unemployment",
        quarterly=False,
        units="pp",
        label="unemployment",
    )
    events += _print_event(
        world,
        params,
        cls="E04",
        series_name="growth_print",
        quarterly=True,
        units="pp",
        label="growth",
    )
    events += _equity_move(world, params)
    events += _rate_move(world, params)
    events += _curve(world, params)
    events += _credit_breach(world, params)
    events += _volatility(world, params)
    events += _drawdown(world, params)
    events += _recovery(world, params)
    events += _year_end(world, params)

    for event in events:
        if not event.panel or event.delta is None or not event.delta.get("label"):
            raise NarrationError(
                f"{event.cls} at month {event.month} carries no anchor. DN-9 §B.2: an "
                "announcement that explains nothing visible is cut, and an announcement with "
                "no anchor is a defect, not a warning."
            )
    events.sort(key=lambda e: (e.month, e.cls))
    return events


def uncovered_classes(events: list[Event], *, book_available: bool) -> tuple[str, ...]:
    """Declared classes that never fired — the diagnostics coverage panel."""
    fired = {event.cls for event in events}
    return tuple(sorted(cls for cls in KIND_OF_CLASS if cls not in fired))
