"""The multi-agent comparative harness (WP5.4).

Same world, same seed, N decision-makers, independent institutions: every
participant faces the IDENTICAL revealed path (one ``run_path`` of the toy
engine at the run's seed), decides at the same annual windows
(:func:`ah.core.institution.decision_months`), and is scored against the same
hold-course twin -- so the leaderboard differences are decisions and nothing
else (DN-6 SS4.1's clean-comparison property, here made a harness invariant).

**The three temporal formats are CONFIGURATION** (owner decision D-K5-5:
"probably solo to start, then MMO, then multi-player at the same time"):

- ``solo``          -- each participant plays start-to-finish independently;
- ``cohort-cadence``-- the cohort advances window-by-window in lockstep (the
                       real-time month-long MMO cadence);
- ``simultaneous``  -- everyone in the room at once (the facilitated format).

The format changes ITERATION ORDER and export framing, never scores: a test
pins score invariance across formats, because a competition whose outcome
depended on scheduling would be measuring the harness, not the players.

**Information basis** is likewise configuration -- ``reported`` (the
institutional status quo; smoothed sleeve marks) or ``true`` -- which is
exactly DN-6 SS4.2's toggle arms surfaced where the tournament can randomize
them later. Policies only ever see the revealed state through
:class:`WindowState`; nothing hands them the future (the state at window w is
computed from a run whose post-w windows default to hold, and depends only on
actions at or before w -- causality the engine guarantees and a test asserts).

Scores land on the retrofit R-1 leaderboard under its triple key
``(world_id, seed, decision_alpha_version)``; the cohort-exercise export is
what a wargame produces afterward: each participant's decisions, rationales,
value path, alpha vs the twin, and the cohort dispersion statistics.

Machine participants mirror wp4-07's committee trio at this layer (band-rule
heuristic, seeded luck baseline, hold-course); LLM/committee personas plug in
through the same :data:`DecisionPolicy` protocol at the port layer later --
a named extension point, not a hidden one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.core.engine import run_path
from ah.core.institution import (
    ACTIONS,
    InstitutionResult,
    decision_months,
    simulate_institution,
)
from ah.core.numericworld import NumericWorld, project_numeric
from ah.core.worldspec import WorldSpec
from ah.store.leaderboard import submit_score
from ah.store.runrecords import DECISION_ALPHA_VERSION, get_run_record
from ah.store.worlds import get_world

__all__ = [
    "FORMATS",
    "DecisionPolicy",
    "ParticipantResult",
    "TournamentError",
    "TournamentResult",
    "WindowState",
    "band_rule_policy",
    "hold_course_policy",
    "random_policy",
    "run_tournament",
]

FORMATS: tuple[str, ...] = ("solo", "cohort-cadence", "simultaneous")


class TournamentError(RuntimeError):
    """A tournament request the harness refuses."""


@dataclass(frozen=True)
class WindowState:
    """What a participant knows at a decision window -- and nothing more.

    ``weights``/``total`` come from the participant's OWN institution run with
    their decisions so far applied (and every later window defaulting to
    hold); ``basis`` names the information regime the sleeve marks are on.
    """

    window: int  # 0-based window index
    month: int  # the decision month (12*year - 1)
    total: float  # portfolio value at the window month
    weights: dict[str, float]  # post-month sleeve weights at the window month
    trailing_12m_total_return: float
    basis: str  # "reported" | "true"


DecisionPolicy = Callable[[WindowState], tuple[str, str]]
"""Maps the revealed window state to ``(action, rationale)``;
``action`` must be one of :data:`ah.core.institution.ACTIONS`."""


@dataclass(frozen=True)
class ParticipantResult:
    participant: str
    final_value: float
    alpha_vs_twin: float
    decisions: dict[int, str]  # decision month -> action
    rationales: dict[int, str]  # decision month -> stated reason
    total_path: np.ndarray  # (months,) portfolio value


@dataclass(frozen=True)
class TournamentResult:
    world_id: str
    seed: int
    fmt: str
    basis: str
    decision_alpha_version: str
    twin_final: float
    participants: tuple[ParticipantResult, ...]
    dispersion: dict[str, float]
    leaderboard_rows: int = 0
    export: dict[str, Any] = field(default_factory=dict)


def _window_state(result: InstitutionResult, window: int, month: int, basis: str) -> WindowState:
    from ah.core.institution import SLEEVES

    total = float(result.total[month])
    prev = float(result.total[month - 12]) if month >= 12 else 100.0
    return WindowState(
        window=window,
        month=month,
        total=total,
        weights={s: float(result.weights[month, j]) for j, s in enumerate(SLEEVES)},
        trailing_12m_total_return=total / prev - 1.0,
        basis=basis,
    )


def _play_one(
    paths: Any, policy: DecisionPolicy, months_list: list[int], basis: str
) -> tuple[dict[int, str], dict[int, str]]:
    """Sequentially reveal windows to one policy; return its decisions/rationales.

    The state shown at window w is computed from a run with the decisions so
    far applied -- which, by the engine's causality, equals the state of the
    participant's final run at that month (post-w actions cannot reach it).
    """
    use_reported = basis == "reported"
    decisions: dict[int, str] = {}
    rationales: dict[int, str] = {}
    for w, month in enumerate(months_list):
        so_far = simulate_institution(paths, decisions, use_reported=use_reported)
        state = _window_state(so_far, w, month, basis)
        action, rationale = policy(state)
        if action not in ACTIONS:
            raise TournamentError(
                f"policy returned unknown action {action!r}; known: {sorted(ACTIONS)}"
            )
        decisions[month] = action
        rationales[month] = str(rationale)
    return decisions, rationales


def run_tournament(
    conn: sqlite3.Connection,
    run_id: str,
    participants: Mapping[str, DecisionPolicy],
    *,
    fmt: str = "solo",
    basis: str = "reported",
    submit: bool = True,
    created_at: str | None = None,
) -> TournamentResult:
    """Run N participants over one RunRecord's revealed path; score; export.

    The world and seed come from the stored run (the same regenerate-from-
    lineage discipline as ``verify_run`` and the inspect renderer). ``submit``
    writes each participant's alpha to the leaderboard under the triple key;
    it then requires ``created_at`` (caller-supplied -- the no-clock-reads
    invariant holds here as everywhere).
    """
    if fmt not in FORMATS:
        raise TournamentError(f"unknown format {fmt!r}; known: {FORMATS}")
    if basis not in ("reported", "true"):
        raise TournamentError(f"unknown basis {basis!r}; known: reported, true")
    if not participants:
        raise TournamentError("a tournament needs at least one participant")
    if submit and not created_at:
        raise TournamentError("submit=True requires created_at (no clock reads here)")

    rec = get_run_record(conn, run_id)
    if rec is None:
        raise TournamentError(f"no run_record with run_id={run_id}")
    world_doc = get_world(conn, rec["world_id"])
    if world_doc is None:
        raise TournamentError(f"run {run_id} references missing world {rec['world_id']}")
    nw: NumericWorld = project_numeric(WorldSpec.model_validate(world_doc))
    paths = run_path(nw, rec["seed"])
    months_list = decision_months(paths.months)
    use_reported = basis == "reported"

    twin = simulate_institution(paths, None, use_reported=use_reported)

    # The format is scheduling, not physics: solo iterates participants
    # outer-loop; the cohort formats iterate windows outer-loop in lockstep.
    # Policies are pure functions of revealed state, so the two orders produce
    # identical decisions -- asserted by test, relied on here for simplicity:
    # decisions are collected per participant either way.
    names = list(participants)
    played: dict[str, tuple[dict[int, str], dict[int, str]]] = {}
    if fmt == "solo":
        for name in names:
            played[name] = _play_one(paths, participants[name], months_list, basis)
    else:
        # lockstep: reveal window w to every participant before any sees w+1
        state_runs: dict[str, dict[int, str]] = {name: {} for name in names}
        notes: dict[str, dict[int, str]] = {name: {} for name in names}
        for w, month in enumerate(months_list):
            for name in names:
                so_far = simulate_institution(paths, state_runs[name], use_reported=use_reported)
                state = _window_state(so_far, w, month, basis)
                action, rationale = participants[name](state)
                if action not in ACTIONS:
                    raise TournamentError(f"policy {name!r} returned unknown action {action!r}")
                state_runs[name][month] = action
                notes[name][month] = str(rationale)
        played = {name: (state_runs[name], notes[name]) for name in names}

    results = []
    for name in names:
        decisions, rationales = played[name]
        final = simulate_institution(paths, decisions, use_reported=use_reported)
        results.append(
            ParticipantResult(
                participant=name,
                final_value=float(final.final_value),
                alpha_vs_twin=float(final.final_value - twin.final_value),
                decisions=decisions,
                rationales=rationales,
                total_path=final.total,
            )
        )

    alphas = np.array([r.alpha_vs_twin for r in results])
    dispersion = {
        "n": float(alphas.size),
        "mean": float(alphas.mean()),
        "std": float(alphas.std(ddof=1)) if alphas.size > 1 else 0.0,
        "iqr": float(np.percentile(alphas, 75) - np.percentile(alphas, 25)),
        "min": float(alphas.min()),
        "max": float(alphas.max()),
        "spread": float(alphas.max() - alphas.min()),
    }

    rows = 0
    if submit:
        assert created_at is not None
        for r in results:
            submit_score(
                conn,
                world_id=rec["world_id"],
                seed=rec["seed"],
                decision_alpha_version=DECISION_ALPHA_VERSION,
                participant=r.participant,
                score=r.alpha_vs_twin,
                created_at=created_at,
            )
            rows += 1

    export = {
        "kind": "cohort-exercise-export",
        "world_id": rec["world_id"],
        "run_id": run_id,
        "seed": rec["seed"],
        "format": fmt,
        "information_basis": basis,
        "decision_alpha_version": DECISION_ALPHA_VERSION,
        "twin_final_value": float(twin.final_value),
        "dispersion": dispersion,
        "participants": [
            {
                "participant": r.participant,
                "final_value": r.final_value,
                "alpha_vs_twin": r.alpha_vs_twin,
                "decisions": {str(m): a for m, a in sorted(r.decisions.items())},
                "rationales": {str(m): s for m, s in sorted(r.rationales.items())},
                "value_path": [round(float(v), 6) for v in r.total_path],
            }
            for r in sorted(results, key=lambda r: -r.alpha_vs_twin)
        ],
    }

    return TournamentResult(
        world_id=rec["world_id"],
        seed=rec["seed"],
        fmt=fmt,
        basis=basis,
        decision_alpha_version=DECISION_ALPHA_VERSION,
        twin_final=float(twin.final_value),
        participants=tuple(results),
        dispersion=dispersion,
        leaderboard_rows=rows,
        export=export,
    )


# --------------------------------------------------------------------------- #
# machine participants (wp4-07's committee trio, at this layer)
# --------------------------------------------------------------------------- #


def band_rule_policy(threshold: float = 0.05) -> DecisionPolicy:
    """The rules-based committee: derisk after a strong trailing year, lean in
    after a weak one, hold inside the band -- the toy-layer mirror of
    ``ah.artifacts.committee.heuristic_decision``'s band rule."""

    def policy(state: WindowState) -> tuple[str, str]:
        r = state.trailing_12m_total_return
        if r > threshold:
            return "derisk", f"Band rule: trailing year {r:+.1%} above +{threshold:.0%}; derisk."
        if r < -threshold:
            return "leanin", f"Band rule: trailing year {r:+.1%} below -{threshold:.0%}; lean in."
        return "hold", f"Band rule: trailing year {r:+.1%} within the band; hold."

    return policy


def random_policy(base_seed: int) -> DecisionPolicy:
    """The luck baseline: a seeded uniform action per window, reproducible."""
    choices = sorted(ACTIONS)

    def policy(state: WindowState) -> tuple[str, str]:
        rng = np.random.Generator(np.random.PCG64(base_seed + 7919 * state.window))
        action = choices[int(rng.integers(len(choices)))]
        return action, f"Luck baseline: seeded draw -> {action}."

    return policy


def hold_course_policy() -> DecisionPolicy:
    """The do-nothing participant: reached every window, chose nothing, on the
    record -- scores exactly zero alpha against the twin by construction."""

    def policy(state: WindowState) -> tuple[str, str]:
        return "hold", "Hold-course: no action by construction."

    return policy
