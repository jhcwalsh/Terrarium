"""Live mode (WP4.6) — sealed reveal, tape selection, the information wall.

The decade is precomputed and SEALED at world build: a hash written into
provenance proves nobody rewrote history mid-game. The reveal pointer is
pure arithmetic over a caller-supplied "now" (no clock reads — the repo
invariant holds even here; wall-clock is the caller's business). The
three tape-selection rules record their provenance choice-by-choice, and
the percentile rule's parameter is PRE-STATED in the WorldSpec — chosen
before anyone has seen a path, recorded verbatim.

The information wall is structural: ``RevealedTape`` is constructed from
the sealed tape and a pointer, holds ONLY the revealed slice, and cannot
answer questions beyond it because the data past the pointer never
enters the object. Chaptered generation exists behind a flag (default
OFF) with its waypoints sealed at t0; the flag's default is a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.core.digest import canonical_json, sha256_of_arrays

CHAPTERED_GENERATION_DEFAULT = False  # behind a flag, per the plan


class LiveModeError(ValueError):
    """A live-mode operation the contract refuses."""


# -- sealing ---------------------------------------------------------------- #


def seal_tape(tape: np.ndarray) -> str:
    """The t0 seal: SHA-256 over the float64 tape (months x series)."""
    if tape.ndim != 2:
        raise LiveModeError("a tape is months x series")
    return "sha256:" + sha256_of_arrays([np.asarray(tape, dtype=np.float64)])


def verify_tape(tape: np.ndarray, sealed_hash: str) -> bool:
    return seal_tape(tape) == sealed_hash


def seal_waypoints(waypoints: list[dict[str, Any]]) -> str:
    """Chaptered mode's t0 commitment: the waypoint list, hashed before
    the first chapter is generated."""
    import hashlib

    return "sha256:" + hashlib.sha256(canonical_json(waypoints).encode("utf-8")).hexdigest()


# -- tape selection --------------------------------------------------------- #


def select_tape(
    ensemble: np.ndarray,
    *,
    rule: str,
    base_seed: int,
    percentile: float | None = None,
    pinned_path_id: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """Which path becomes the tape. Returns (path_id, provenance record).

    ``ensemble``: paths x months x series. The three rules, per the plan:
    random (seeded — deterministic given the world's seed), pre-stated
    percentile of terminal wealth, or a pinned id. The CHOICE is recorded
    in provenance either way.
    """
    n_paths = ensemble.shape[0]
    if rule == "random":
        rng = np.random.Generator(np.random.PCG64(base_seed + 7919))
        path_id = int(rng.integers(0, n_paths))
    elif rule == "percentile":
        if percentile is None:
            raise LiveModeError("percentile rule requires the PRE-STATED percentile")
        terminal = np.prod(1.0 + ensemble[:, :, 0], axis=1)  # series 0 = the stated metric
        target = np.percentile(terminal, percentile)
        path_id = int(np.argmin(np.abs(terminal - target)))
    elif rule == "pinned":
        if pinned_path_id is None:
            raise LiveModeError("pinned rule requires pinned_path_id")
        if not 0 <= pinned_path_id < n_paths:
            raise LiveModeError(f"pinned_path_id {pinned_path_id} outside [0, {n_paths})")
        path_id = pinned_path_id
    else:
        raise LiveModeError(f"unknown tape-selection rule '{rule}'")
    provenance = {
        "rule": rule,
        "path_id": path_id,
        "base_seed": base_seed,
        "percentile": percentile,
        "pinned_path_id": pinned_path_id,
        "metric": "terminal_wealth" if rule == "percentile" else None,
        "sealed_hash": seal_tape(ensemble[path_id]),
    }
    return path_id, provenance


# -- the reveal pointer and the wall ---------------------------------------- #


def reveal_pointer(*, days_elapsed: float, cadence_days: float, horizon_months: int) -> int:
    """How many world months are revealed after ``days_elapsed`` wall-clock
    days. Pure arithmetic; the caller supplies elapsed time (no clock here)."""
    if cadence_days <= 0:
        raise LiveModeError("cadence_days must be positive")
    if days_elapsed < 0:
        raise LiveModeError("days_elapsed cannot be negative")
    return min(horizon_months, int(days_elapsed / cadence_days))


@dataclass(frozen=True)
class RevealedTape:
    """The revealed slice, and ONLY the revealed slice.

    The wall is structural: construction copies months [0, pointer) and
    the rest of the tape never enters the object — there is nothing
    beyond the wall to leak, however the object is later misused.
    """

    months_revealed: int
    data: np.ndarray

    @classmethod
    def cut(cls, tape: np.ndarray, months_revealed: int) -> RevealedTape:
        if not 0 <= months_revealed <= tape.shape[0]:
            raise LiveModeError("months_revealed outside the tape")
        return cls(months_revealed=months_revealed, data=tape[:months_revealed].copy())

    def month(self, index: int) -> np.ndarray:
        if index >= self.months_revealed:
            raise LiveModeError(
                f"month {index} is beyond the reveal pointer ({self.months_revealed}): "
                "the information wall refuses"
            )
        return self.data[index]


# -- notification policy ---------------------------------------------------- #

PUSH_EVENT_TYPES = ("regime_event",)


def classify_notification(event_type: str) -> str:
    """Push only regime events; everything else lands in the digest."""
    return "push" if event_type in PUSH_EVENT_TYPES else "digest"
