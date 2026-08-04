"""The tier-1 bundle feed (su-app-03) — wire items generated from the tape.

Bundle v0.2 carries a pre-authored artifact feed (PD-4: authored at BUILD
time, never live). Everything here is Tier-1 — WP4.2's rule-generated
templates, pure functions of the tape, zero LLM, zero RNG, zero clock —
so a bundle build stays byte-deterministic. Tier-2 letters join only at
the frozen >=95% first-pass bar, and their absence is recorded in
``meta.artifact_tier`` rather than implied.

Each feed item carries its ``month`` so the app reveals it WITH the
pointer (E2: the wire lands in-timeline, not as a lump): quarterly
central-bank statements keyed on the tape's own rate moves, quarterly
inflation release pages (value, prior — the revision culture of real
releases), the institution's quarterly statement with peer bands computed
from the run's own ensemble (each ensemble path run through the same
hold-course institution — peers are alternate histories, which is the
honest peer group this product HAS), and crisis-onset digests.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ah.artifacts.templates import (
    central_bank_statement,
    morning_digest,
    quarterly_statement,
    release_page,
)
from ah.core.engine import EnginePaths, run_path
from ah.core.institution import simulate_institution
from ah.core.numericworld import NumericWorld

__all__ = ["build_tier1_feed"]

_QUANTS = (5, 25, 50, 75, 95)


def _dateline(month: int) -> str:
    """World-relative dateline: months since t0 (worlds are counterfactual —
    they get no calendar years, and the app renders Y2M3 style)."""
    return f"Y{month // 12 + 1}M{month % 12 + 1}"


def _quarter_ends(nm: int) -> list[int]:
    return [m for m in range(nm) if (m + 1) % 3 == 0]


def build_tier1_feed(
    world: NumericWorld,
    paths: EnginePaths,
    *,
    base_seed: int,
    n_peer_paths: int,
) -> list[dict[str, Any]]:
    """The deterministic wire for one revealed path.

    Peer bands: every peer path is generated with the run's own seed
    lineage (``base_seed + 7919*k`` — the ensemble convention) and pushed
    through the SAME hold-course institution, so "peers" means "the same
    institution in the sibling histories of this very run".
    """
    nm = paths.months
    wid = world.world_id
    twin = simulate_institution(paths, None)

    peer_totals = np.empty((n_peer_paths, nm))
    for k in range(n_peer_paths):
        peer = run_path(world, base_seed + 7919 * k)
        peer_totals[k] = simulate_institution(peer, None).total

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

        infl_now = float(paths.inflation[m])
        infl_prev = float(paths.inflation[prev]) if prev >= 0 else infl_now
        items.append(
            {
                "month": m,
                "type": "release_page",
                "payload": release_page(
                    world_id=wid,
                    dateline=_dateline(m),
                    release_name="Consumer prices (annualized)",
                    rows=[
                        {
                            "series": "CPI inflation",
                            "value": f"{infl_now:.1f}%",
                            "prior": f"{infl_prev:.1f}%",
                        }
                    ],
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

    items.sort(key=lambda it: (it["month"], it["type"]))
    return items
