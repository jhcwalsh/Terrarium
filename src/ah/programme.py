"""The private-programme section of the credibility console.

The commitment lever is the next thing the product needs, and nobody has
looked at what the pacing model does. ``ah/port/`` runs a real cohort
recursion and ``ah/play.py`` runs a ladder — a new vintage every year in every
private sleeve — and both are correct as far as any test goes without anyone
having seen their shape.

This module puts that shape on a page, with the market linkage first-class:
the two continuous states tier 1 consumes, the multipliers they produce, and
what the distributions would have been on the same tape with the linkage off.
The asymmetry it exists to show is that ``f_call`` is bounded near-flat while
``f_dist`` can reach its floor — calls keep coming while distributions stop,
and that is what empties the cash account.

Admin tooling, on the credibility console's contract: reads worlds, writes
nothing, not in the pre-registration seal, never touches the scored path, and
no number here reaches a player. Deterministic — same world, same seed, same
bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from ah.play import PlayResult

__all__ = [
    "LadderYear",
    "ProgrammeQuarter",
    "ladder_years",
    "programme_quarters",
]

_QUARTERS_PER_YEAR = 4


@dataclass(frozen=True)
class ProgrammeQuarter:
    """One quarter of the programme, with the market state that drove it."""

    quarter: int
    month: int
    drawdown_depth: float
    spread_ratio: float
    f_dist: float
    f_call: float
    calls: float
    distributions: float
    distributions_unlinked: float
    cash: float
    nav_true: float
    nav_reported: float
    private_nav: float
    unfunded: float
    private_weight_true: float
    coverage_true: float
    coverage_reported: float
    forced_sale_total: float


@dataclass(frozen=True)
class LadderYear:
    """One year of the commitment pacing plan."""

    year: int
    committed: float
    called: float
    distributed: float
    net: float
    called_to_date: float
    unfunded_end: float
    private_nav_end: float


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Coverage ratio matching Portfolio.coverage_true()'s convention.

    When denominator > 0, returns numerator / denominator.
    When denominator <= 0, returns float("inf").

    An institution with unfunded obligations and no assets is infinitely
    uncovered, not perfectly covered (0.0). This matches the established
    convention in src/ah/port/portfolio.py:79-85, which is also used by
    QuarterReport.coverage_true in src/ah/port/engine.py:169. Returning
    infinity when the book is wiped preserves the distinction between a
    healthy institution and one that has failed.
    """
    return numerator / denominator if denominator > 0.0 else float("inf")


def programme_quarters(linked: PlayResult, unlinked: PlayResult) -> list[ProgrammeQuarter]:
    """Pair the linked run with its linkage-off counterfactual, quarter by quarter."""
    rows: list[ProgrammeQuarter] = []
    for q, u in zip(linked.quarters, unlinked.quarters, strict=True):
        private_nav = q.private_weight_true * q.nav_true
        rows.append(
            ProgrammeQuarter(
                quarter=q.quarter,
                month=q.month,
                drawdown_depth=q.drawdown_depth,
                spread_ratio=q.spread_ratio,
                f_dist=q.f_dist,
                f_call=q.f_call,
                calls=q.calls_paid,
                distributions=q.distributions_received,
                distributions_unlinked=u.distributions_received,
                cash=q.cash,
                nav_true=q.nav_true,
                nav_reported=q.nav_reported,
                private_nav=private_nav,
                unfunded=q.unfunded_total,
                private_weight_true=q.private_weight_true,
                coverage_true=_safe_ratio(q.unfunded_total, q.nav_true),
                coverage_reported=_safe_ratio(q.unfunded_total, q.nav_reported),
                forced_sale_total=q.forced_sale_total,
            )
        )
    return rows


def ladder_years(quarters: list[ProgrammeQuarter], linked: PlayResult) -> list[LadderYear]:
    """Aggregate the quarterly programme into the pacing plan's own unit: years."""
    years: list[LadderYear] = []
    running_called = 0.0
    for start in range(0, len(quarters), _QUARTERS_PER_YEAR):
        block = quarters[start : start + _QUARTERS_PER_YEAR]
        if not block:
            continue
        source = linked.quarters[start : start + _QUARTERS_PER_YEAR]
        called = sum(r.calls for r in block)
        distributed = sum(r.distributions for r in block)
        running_called += called
        years.append(
            LadderYear(
                year=start // _QUARTERS_PER_YEAR,
                committed=sum(q.new_commitments for q in source),
                called=called,
                distributed=distributed,
                net=distributed - called,
                called_to_date=running_called,
                unfunded_end=block[-1].unfunded,
                private_nav_end=block[-1].private_nav,
            )
        )
    return years
