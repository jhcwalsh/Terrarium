"""Private-market pacing: commitments, calls and distributions (display-only).

Owner's ask: "we need to be able to look at the commitments, calls and
distributions for each of the private assets - these, with the payout and
returns will drive actions such as secondary sales."

**What this is.** A deterministic toy pacing ledger, derived from the tape at
BUILD time (PD-4) and carried in the bundle. It gives the player the numbers
that make a secondary sale a real decision rather than a slider: what is
committed, what is still unfunded, what has been called, what has come back,
and where DPI and TVPI stand.

**What this is NOT.** It does not move money. The engine emits returns only;
there is no cash account, calls cannot go unmet, and nothing here can force a
sale. Scoring, `decision_alpha` and the institution simulation are untouched —
this ledger is read, not applied. Binding cashflows to the portfolio is Step
3's institutional twin (CLAUDE.md's cashflow/TA calibration; registered as
ER-3), and doing it changes the alpha definition.

Saying that plainly matters more than the numbers: a player who thinks these
calls are being funded from somewhere is being misled, so the panel that
renders this says "informational" on its face.

**The model.** Classic pacing, quarterly, with no RNG anywhere:

- Commit ``COMMITMENT_MULTIPLE`` times the target weight — over-commitment is
  what real programmes do, because capital comes back before it is all drawn.
- Call a fixed fraction of REMAINING unfunded each quarter, faster in the
  first three years than after (the front-loaded draw of a young programme).
- Distribute nothing until the J-curve turns, then a fixed fraction of NAV.
- NAV grows on the asset's own REPORTED marks, because NAV is an appraisal —
  the same plane the wire quotes, not the true return the player cannot see.

Every constant is stated here rather than derived, and all of them are toy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ah.core.engine import REPORTED_SLEEVES, EnginePaths
from ah.core.institution import START_MIX

__all__ = [
    "CALL_RATE_EARLY",
    "CALL_RATE_LATE",
    "COMMITMENT_MULTIPLE",
    "DISTRIBUTION_RATE",
    "J_CURVE_QUARTERS",
    "SleeveLedger",
    "build_ledgers",
]

# Over-commitment: a programme targeting 25pts of NAV commits more than 25,
# because distributions return capital before the commitment is fully drawn.
COMMITMENT_MULTIPLE = 1.5
# Fraction of REMAINING unfunded drawn each quarter.
CALL_RATE_EARLY = 0.09
CALL_RATE_LATE = 0.045
# Quarters before the J-curve turns and capital starts coming back.
J_CURVE_QUARTERS = 10
# Fraction of NAV distributed each quarter, once distributing.
DISTRIBUTION_RATE = 0.05
# Quarter at which the early call rate steps down to the late one.
_EARLY_QUARTERS = 12


@dataclass(frozen=True)
class SleeveLedger:
    """One private asset's programme, quarter by quarter.

    All amounts are in points of the institution's starting book (which is
    100), so they read directly against the allocation panel's percentages.
    ``quarter_months`` gives the month index each quarter closes on, so the
    app can reveal a row exactly when the pointer passes it.
    """

    asset: str
    commitment: float
    quarter_months: list[int]
    called: list[float]
    distributed: list[float]
    unfunded: list[float]
    nav: list[float]
    dpi: list[float]
    tvpi: list[float]


def _quarter_ends(nm: int) -> list[int]:
    return [m for m in range(nm) if (m + 1) % 3 == 0]


def build_ledgers(paths: EnginePaths) -> dict[str, SleeveLedger]:
    """A pacing ledger per private asset, keyed off the tape's reported marks.

    Pure and deterministic: same tape, same ledger, always.
    """
    qends = _quarter_ends(paths.months)
    out: dict[str, SleeveLedger] = {}
    for asset in REPORTED_SLEEVES:
        commitment = START_MIX[asset] * 100.0 * COMMITMENT_MULTIPLE
        reported = np.asarray(paths.reported[asset], dtype=float)

        unfunded = commitment
        nav = 0.0
        cum_called = 0.0
        cum_dist = 0.0
        called_l: list[float] = []
        dist_l: list[float] = []
        unfunded_l: list[float] = []
        nav_l: list[float] = []
        dpi_l: list[float] = []
        tvpi_l: list[float] = []

        for q, m in enumerate(qends):
            rate = CALL_RATE_EARLY if q < _EARLY_QUARTERS else CALL_RATE_LATE
            call = unfunded * rate
            unfunded -= call
            cum_called += call

            # the quarter's reported mark, applied to NAV already in the ground
            nav *= 1.0 + float(reported[m]) / 100.0
            nav += call

            dist = nav * DISTRIBUTION_RATE if q >= J_CURVE_QUARTERS else 0.0
            nav -= dist
            cum_dist += dist

            # exact here; rounding happens once, at the bundle boundary, so the
            # ledger's own arithmetic stays self-consistent (independently
            # rounding unfunded and called let their difference drift by 1e-6)
            called_l.append(call)
            dist_l.append(dist)
            unfunded_l.append(unfunded)
            nav_l.append(nav)
            dpi_l.append(cum_dist / cum_called if cum_called > 0 else 0.0)
            tvpi_l.append((nav + cum_dist) / cum_called if cum_called > 0 else 0.0)

        out[asset] = SleeveLedger(
            asset=asset,
            commitment=commitment,
            quarter_months=list(qends),
            called=called_l,
            distributed=dist_l,
            unfunded=unfunded_l,
            nav=nav_l,
            dpi=dpi_l,
            tvpi=tvpi_l,
        )
    return out
