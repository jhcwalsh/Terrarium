"""The tier-1 bundle feed (su-app-03) — wire items generated from the tape.

Bundle v0.2 carries a pre-authored artifact feed (PD-4: authored at BUILD
time, never live). Everything here is Tier-1 — WP4.2's rule-generated
templates, pure functions of the tape, zero LLM, zero RNG, zero clock —
so a bundle build stays byte-deterministic. Tier-2 letters join only at
the frozen >=95% first-pass bar, and their absence is recorded in
``meta.artifact_tier`` rather than implied.

Each feed item carries its ``month`` so the app reveals it WITH the
pointer (E2: the wire lands in-timeline, not as a lump).

The calendar, after the second live-play round:

- **monthly** data releases (CPI and the HY credit spread, each with its
  prior), because a player advancing a quarter at a time should find three
  releases waiting, not one;
- **monthly** newspaper front pages, but only when the tape actually did
  something — an inflation threshold crossed, a year-on-year policy swing,
  spreads blowing out or coming back in, an equity drawdown deepening, a
  crisis opening or closing. Quiet months get no paper, which is itself
  information;
- **quarterly** central-bank statements. A real committee meets eight times
  a year, but the toy engine's policy rate is a continuous drift with no
  meeting calendar, so quarterly stance narration is the honest cadence
  until the engine quantises policy into decisions (docs/engine-realism-
  register.md, ER-2). Recorded rather than faked;
- **quarterly** institution statements with peer bands computed from the
  run's own ensemble (each ensemble path run through the same hold-course
  institution — peers are alternate histories, which is the honest peer
  group this product HAS);
- crisis-onset digests, unchanged.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ah.artifacts.templates import (
    board_pack,
    central_bank_statement,
    morning_digest,
    newspaper_front_page,
    quarterly_statement,
    release_page,
)
from ah.core.engine import EnginePaths, run_path
from ah.core.institution import decision_months, simulate_institution
from ah.core.numericworld import NumericWorld

__all__ = ["build_tier1_feed"]

_QUANTS = (5, 25, 50, 75, 95)

# Front-page triggers. Levels are chosen to be the ones a desk would actually
# remark on, and each fires only on the month it is CROSSED, in either
# direction — so a decade spent above 8% inflation yields one headline, not
# ninety.
_INFLATION_LEVELS = (5.0, 8.0, 10.0)
_SPREAD_LEVELS_BPS = (800.0, 1200.0, 1600.0)
_DRAWDOWN_LEVELS = (0.10, 0.20, 0.30)
_RATE_SWING_BPS = 100.0
_MAX_SECONDARY_STORIES = 3


def _dateline(month: int) -> str:
    """World-relative dateline: months since t0 (worlds are counterfactual —
    they get no calendar years, and the app renders Y2M3 style)."""
    return f"Y{month // 12 + 1}M{month % 12 + 1}"


def _quarter_ends(nm: int) -> list[int]:
    return [m for m in range(nm) if (m + 1) % 3 == 0]


def _crossings(series: np.ndarray, level: float) -> list[tuple[int, str]]:
    """Months where ``series`` crosses ``level``, with the direction.

    Strict on the way up, inclusive on the way down, so a value sitting
    exactly on the level cannot fire both.
    """
    out: list[tuple[int, str]] = []
    for m in range(1, len(series)):
        if series[m - 1] < level <= series[m]:
            out.append((m, "up"))
        elif series[m - 1] >= level > series[m]:
            out.append((m, "down"))
    return out


def _drawdown(returns_pct: np.ndarray) -> np.ndarray:
    """Cumulative drawdown from the running peak, as a positive fraction."""
    growth = np.cumprod(1.0 + returns_pct / 100.0)
    peak = np.maximum.accumulate(growth)
    return 1.0 - growth / peak


def headline_events(paths: EnginePaths) -> dict[int, list[str]]:
    """Every front-page story the tape earns, keyed by month.

    Pure function of the tape: same paths, same words, always. Order within
    a month is fixed by the order the rules run, so the lead story is
    deterministic too.
    """
    nm = paths.months
    out: dict[int, list[str]] = {}

    def add(m: int, text: str) -> None:
        if 0 <= m < nm:
            out.setdefault(m, []).append(text)

    # the loudest structural event first, so it always leads its month
    for m in range(nm):
        on = paths.crisis[m] == 1.0
        was = m > 0 and paths.crisis[m - 1] == 1.0
        if on and (m == 0 or not was):
            add(m, "Markets enter a stress regime as conditions deteriorate sharply")
        elif was and not on:
            add(m, "Stress regime declared over; conditions normalise")

    for level in _INFLATION_LEVELS:
        for m, direction in _crossings(paths.inflation, level):
            if direction == "up":
                add(m, f"Inflation tops {level:.0f}% as price pressure broadens")
            else:
                add(m, f"Inflation falls back below {level:.0f}%")

    # policy swing measured year-on-year, reported on the month it crosses
    rate = np.asarray(paths.rate, dtype=float)
    for m in range(13, nm):
        now_bp = (rate[m] - rate[m - 12]) * 100.0
        prev_bp = (rate[m - 1] - rate[m - 13]) * 100.0
        if now_bp >= _RATE_SWING_BPS > prev_bp:
            add(m, f"Policy rate up {now_bp:.0f}bp over the year as the stance tightens")
        elif now_bp <= -_RATE_SWING_BPS < prev_bp:
            add(m, f"Policy rate down {abs(now_bp):.0f}bp over the year as the stance eases")

    for level in _SPREAD_LEVELS_BPS:
        for m, direction in _crossings(paths.spread, level):
            if direction == "up":
                add(m, f"Credit spreads blow through {level:.0f}bp; borrowers priced out")
            else:
                add(m, f"Credit spreads narrow back inside {level:.0f}bp")

    dd = _drawdown(np.asarray(paths.returns["equity"], dtype=float))
    # A drawdown level is a MILESTONE, not a crossing: only the first time
    # equities go 20% down is news. Reporting every re-crossing printed the
    # same headline three times in one decade as the market oscillated around
    # the threshold, which is how you teach a player to stop reading.
    for level in _DRAWDOWN_LEVELS:
        ups = [m for m, direction in _crossings(dd, level) if direction == "up"]
        if ups:
            add(ups[0], f"Equities {level * 100:.0f}% off their peak")

    return out


def build_tier1_feed(
    world: NumericWorld,
    paths: EnginePaths,
    *,
    base_seed: int,
    n_peer_paths: int,
    run_path_fn: Any = None,
    start_mix: Any = None,
) -> list[dict[str, Any]]:
    """The deterministic wire for one revealed path.

    Peer bands: every peer path is generated with the run's own seed
    lineage (``base_seed + 7919*k`` — the ensemble convention) and pushed
    through the SAME hold-course institution, so "peers" means "the same
    institution in the sibling histories of this very run".

    ``run_path_fn``/``start_mix`` (su-gen-02) let a generated world supply
    its own path generator and opening mix; defaults are the toy engine's.
    """
    nm = paths.months
    wid = world.world_id
    path_fn = run_path_fn or run_path
    twin = simulate_institution(paths, None, start_mix=start_mix)

    peer_totals = np.empty((n_peer_paths, nm))
    for k in range(n_peer_paths):
        peer = path_fn(world, base_seed + 7919 * k)
        peer_totals[k] = simulate_institution(peer, None, start_mix=start_mix).total

    items: list[dict[str, Any]] = []

    # crisis onset: the loudest structural event the toy tape carries
    for m in range(nm):
        if paths.crisis[m] == 1.0 and (m == 0 or paths.crisis[m - 1] == 0.0):
            items.append(
                {
                    "month": m,
                    "type": "wire_digest",
                    "payload": morning_digest(
                        world_id=wid,
                        dateline=_dateline(m),
                        items=[{"headline": "Stress regime begins: crisis window opens"}],
                    ),
                }
            )

    # monthly: the data release. Two rows off the tape, each with its prior —
    # the revision culture of a real release page.
    for m in range(nm):
        prev = m - 1
        infl_now = float(paths.inflation[m])
        infl_prev = float(paths.inflation[prev]) if prev >= 0 else infl_now
        spread_now = float(paths.spread[m])
        spread_prev = float(paths.spread[prev]) if prev >= 0 else spread_now
        items.append(
            {
                "month": m,
                "type": "release_page",
                "payload": release_page(
                    world_id=wid,
                    dateline=_dateline(m),
                    release_name="Monthly economic release",
                    rows=[
                        {
                            "series": "CPI inflation",
                            "value": f"{infl_now:.1f}%",
                            "prior": f"{infl_prev:.1f}%",
                        },
                        {
                            "series": "High yield spread",
                            "value": f"{spread_now:.0f}bp",
                            "prior": f"{spread_prev:.0f}bp",
                        },
                    ],
                ),
            }
        )

    # monthly, when earned: the front page
    for m, stories in sorted(headline_events(paths).items()):
        items.append(
            {
                "month": m,
                "type": "newspaper",
                "payload": newspaper_front_page(
                    world_id=wid,
                    dateline=_dateline(m),
                    lead=stories[0],
                    stories=stories[1 : 1 + _MAX_SECONDARY_STORIES],
                ),
            }
        )

    for m in _quarter_ends(nm):
        prev = m - 3
        rate_now = float(paths.rate[m]) / 100.0  # engine percent -> template decimal
        rate_prev = float(paths.rate[prev]) / 100.0 if prev >= 0 else rate_now
        items.append(
            {
                "month": m,
                "type": "cb_statement",
                "payload": central_bank_statement(
                    world_id=wid,
                    dateline=_dateline(m),
                    policy_rate=rate_now,
                    previous_rate=rate_prev,
                ),
            }
        )

        # the institution's own paper, peer-banded against sibling histories
        q_start = float(twin.total[prev]) if prev >= 0 else 100.0
        year_start_m = (m // 12) * 12 - 1
        y_start = float(twin.total[year_start_m]) if year_start_m >= 0 else 100.0
        peer_q = peer_totals[:, m] / (peer_totals[:, prev] if prev >= 0 else 100.0) - 1.0
        qs = np.percentile(peer_q, _QUANTS)
        items.append(
            {
                "month": m,
                "type": "quarterly_statement",
                "payload": quarterly_statement(
                    world_id=wid,
                    dateline=_dateline(m),
                    quarter_label=f"Y{m // 12 + 1}Q{(m % 12) // 3 + 1}",
                    return_q=float(twin.total[m]) / q_start - 1.0,
                    return_ytd=float(twin.total[m]) / y_start - 1.0,
                    total_value=float(twin.total[m]),
                    net_flow=0.0,
                    peer_bands={f"p{q}": float(v) for q, v in zip(_QUANTS, qs, strict=True)},
                ),
            }
        )

    # sp-04: the board pack — one per decision window, assembled at build
    # from the quarter's own numbers and the wire above (PD-4). The
    # consultant section states process, never a trade (the E5 rule).
    def _headline(it: dict[str, Any]) -> str | None:
        p = it["payload"]
        if p.get("lines"):
            return str(p["lines"][0])
        if p.get("headline"):
            return str(p["headline"])
        rows = p.get("rows")
        if rows:
            return f"{rows[0]['series']} {rows[0]['value']}"
        return None

    order = list(paths.asset_order)
    for m in decision_months(nm):
        if m >= nm:
            continue
        eq = np.asarray(paths.returns["equity"][max(0, m - 11) : m + 1]) / 100.0
        trailing = float(np.prod(1.0 + eq) - 1.0)
        weights = twin.weights[m]
        recent = [
            h
            for it_month, h in ((i["month"], _headline(i)) for i in items)
            if it_month <= m and h is not None
        ][-6:]
        items.append(
            {
                "month": m,
                "type": "board_pack",
                "payload": board_pack(
                    world_id=wid,
                    dateline=_dateline(m),
                    performance=[
                        f"Trailing 12-month public equity return: {trailing:+.1%}.",
                        f"Hold-course book value: {float(twin.total[m]):.1f} against 100.0 at t0.",
                    ],
                    allocation=[f"{name}: {float(weights[i]):.1%}" for i, name in enumerate(order)],
                    liquidity=[
                        f"High-yield spread: {float(paths.spread[m]):.0f}bp.",
                        f"Crisis months to date: {int(paths.crisis[: m + 1].sum())} of {m + 1}.",
                    ],
                    wire_digest=recent or ["A quiet stretch on the wire."],
                    consultant_recommendation=[
                        "Review coverage on both bases before deciding; the "
                        "reported basis flatters exactly when values move.",
                        "Holding to the pacing plan remains available as an "
                        "explicit committed choice.",
                    ],
                ),
            }
        )

    items.sort(key=lambda it: (it["month"], it["type"]))
    return items
