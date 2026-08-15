"""The inherited decade (cio-04) — what the plan did before the world began.

DISPLAY ONLY, by ruling. The opening book at world month 0 is exactly what
``ah.play._build_portfolio`` constructs and is not touched here; this module
produces the path that LEADS to it, scaled so it terminates on that book. The
alternative — an opening book that is the output of a simulated pre-decade —
would change every scored run and is a separate release decision.

Determinism: one integer seed, offset by a declared prime, through the same
toy engine as any other world. The replay is hold-course (no player
decisions): the inherited past is the plan's own, not anyone's play of it.

Scaling is the whole safety argument, so it earns saying twice: the replay
produces a SHAPE (a stochastic path from the toy engine, run through the same
institution the game plays), and every level in that shape is multiplied by
``terminal_nav / path[-1]`` so it lands EXACTLY on the NAV the game's month 0
already opens at. Nothing about the opening book changes; the chart is simply
given somewhere to have come from. The exported NAV levels (``nav_true_months``/
``nav_reported_months``) are pure scaled levels with nothing else added to
them, so a constant rescale still cannot change the SHAPE the player sees —
the chart is the shape the toy engine actually drew, never a stretched or
compressed one.

Quarterly returns are a separate exported quantity and are computed off the
UNSCALED replay, before the terminal scale factor is ever applied — full
stop. That is NOT the same "a rescale cannot change a ratio" argument that
protects the chart's shape: the return formula adds a quarter's payout into
the numerator (see below), and a scale factor no longer cancels out of a
ratio once one side carries an additive term the other side doesn't share.
The returns are safe only because they are computed once, before scaling
touches anything, and never revisited — not because they would tolerate a
rescale if one were applied after the fact.

Return convention: payout is added back to each quarter's closing level
before the ratio is taken — time-weighted, exactly ``ah.cioview``'s own
``_quarterly_returns`` convention (``performance.footnote``: "Payout added
back; time-weighted"). The replay is run under the default policy spend like
any other hold-course quarter, so leaving the add-back out would silently
switch conventions mid-window the moment a prehistory quarter enters a long
return column next to world quarters computed the other way.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from ah.core.engine import EnginePaths, run_path
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.play import LIQUID_ASSETS, simulate_play

__all__ = [
    "PREHISTORY_QUARTERS",
    "PREHISTORY_SEED_OFFSET",
    "PreHistory",
    "build_prehistory",
]

_PRESETS = Path(__file__).resolve().parent / "presets"

PREHISTORY_QUARTERS = 40
#: Declared offset. Prime, and not a multiple of the ensemble stride (7919),
#: so an inherited decade can never coincide with an ensemble member's tape.
PREHISTORY_SEED_OFFSET = 999983


@dataclass(frozen=True)
class PreHistory:
    """One inherited decade: a replayed shape, pinned to the opening book."""

    months: int
    nav_true_months: tuple[float, ...]
    nav_reported_months: tuple[float, ...]
    quarterly_returns_true: tuple[float, ...]
    quarterly_returns_reported: tuple[float, ...]
    #: Per liquid asset, monthly returns in PERCENT (the toy tape's own
    #: units) — not levels, and never scaled: market shape is not a NAV.
    market_paths: dict[str, tuple[float, ...]]


def _prehistory_paths(seed: int) -> EnginePaths:
    doc = json.loads((_PRESETS / "prehistory.json").read_text(encoding="utf-8"))
    spec = load_worldspec(doc)
    nw = project_numeric(spec)
    if nw.horizon.quarters != PREHISTORY_QUARTERS:
        raise ValueError(
            f"prehistory preset has {nw.horizon.quarters} quarters, expected "
            f"{PREHISTORY_QUARTERS} — PREHISTORY_QUARTERS is out of sync with "
            "src/ah/presets/prehistory.json"
        )
    return run_path(nw, seed + PREHISTORY_SEED_OFFSET)


def _require_finite_nonzero(name: str, value: float) -> None:
    if not math.isfinite(value) or value == 0.0:
        raise ValueError(f"{name} must be a finite, nonzero NAV, got {value!r}")


def _quarterly_returns(
    opening: float, closes: Sequence[float], spending: Sequence[float]
) -> tuple[float, ...]:
    """Decimal returns between successive quarter-end NAV levels, with that
    quarter's payout added back — time-weighted, matching
    ``ah.cioview._quarterly_returns`` exactly (same formula, same operand
    order): ``(close + spending_paid) / prior_level - 1``.

    ``opening`` is the pre-quarter-0 book (``PlayResult.opening``); each
    subsequent level in ``closes`` is a quarter's closing NAV, and
    ``spending[i]`` is that same quarter's ``PlayQuarter.spending_paid`` —
    the replay is hold-course under the default policy spend, so every
    quarter pays one out. Guards a zero or non-finite level rather than
    letting a ratio silently produce infinity or NaN.
    """
    if len(closes) != len(spending):
        raise ValueError(
            f"closes and spending must be the same length, got {len(closes)} and {len(spending)}"
        )
    levels = (opening, *closes)
    out: list[float] = []
    for i, (prev, cur) in enumerate(pairwise(levels)):
        if not math.isfinite(prev) or prev == 0.0 or not math.isfinite(cur):
            raise ValueError(
                "prehistory replay produced a zero or non-finite NAV level "
                f"({prev!r} -> {cur!r}); cannot form a return"
            )
        out.append((cur + spending[i]) / prev - 1.0)
    return tuple(out)


def build_prehistory(
    seed: int,
    terminal_nav_true: float,
    terminal_nav_reported: float,
    *,
    start_targets: Mapping[str, float] | None = None,
) -> PreHistory:
    """Replay the inherited decade hold-course, scaled to end at the book
    the game's month 0 actually opens with.

    ``seed`` is offset by :data:`PREHISTORY_SEED_OFFSET` before it reaches
    the engine, so an inherited decade never shares a tape with an ensemble
    member of the world it precedes. ``terminal_nav_true``/
    ``terminal_nav_reported`` are the exact opening-book NAVs the scaled path
    must land on; both must be finite and nonzero, or this raises rather
    than manufacture an infinity.
    """
    _require_finite_nonzero("terminal_nav_true", terminal_nav_true)
    _require_finite_nonzero("terminal_nav_reported", terminal_nav_reported)

    paths = _prehistory_paths(seed)
    # Hold-course: no decisions map, so the inherited decade is the plan's
    # own path, not anyone's play of it.
    result = simulate_play(paths, None, start_targets=start_targets)
    if not result.quarters:
        raise ValueError("prehistory replay produced no quarters")

    true_months = tuple(m for q in result.quarters for m in q.nav_true_months)
    rep_months = tuple(m for q in result.quarters for m in q.nav_reported_months)

    if not math.isfinite(true_months[-1]) or true_months[-1] == 0.0:
        raise ValueError("prehistory replay ended at a zero or non-finite true NAV; cannot scale")
    if not math.isfinite(rep_months[-1]) or rep_months[-1] == 0.0:
        raise ValueError(
            "prehistory replay ended at a zero or non-finite reported NAV; cannot scale"
        )

    # Quarterly returns off the UNSCALED replay, computed once here, before
    # the terminal scale factor below is applied to anything, and never
    # revisited (asserted scale-invariant in tests/test_prehistory.py). Safe
    # because scaling never touches them, not because a rescale "cannot
    # change a ratio" — the payout add-back puts an additive term in the
    # numerator, so that argument no longer holds if this were ever
    # recomputed from already-scaled levels instead.
    # ``spending_paid`` is plane-agnostic (ah.play.PlayQuarter carries one
    # figure, not a per-plane pair) and feeds both calls unchanged — same as
    # ah.cioview._quarterly_returns, which reuses it for both planes too.
    spending = [q.spending_paid for q in result.quarters]
    quarterly_true = _quarterly_returns(
        result.opening["nav_true"], [q.nav_true for q in result.quarters], spending
    )
    quarterly_reported = _quarterly_returns(
        result.opening["nav_reported"], [q.nav_reported for q in result.quarters], spending
    )

    scale_true = terminal_nav_true / true_months[-1]
    scale_reported = terminal_nav_reported / rep_months[-1]

    market_paths = {
        asset: tuple(float(x) for x in paths.returns[asset][: paths.months])
        for asset in LIQUID_ASSETS
        if asset in paths.returns
    }

    return PreHistory(
        months=paths.months,
        nav_true_months=tuple(v * scale_true for v in true_months),
        nav_reported_months=tuple(v * scale_reported for v in rep_months),
        quarterly_returns_true=quarterly_true,
        quarterly_returns_reported=quarterly_reported,
        market_paths=market_paths,
    )
