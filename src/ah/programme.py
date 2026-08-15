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

import html as _html
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ah.core.engine import run_path
from ah.core.numericworld import NumericWorld
from ah.play import PlayResult, simulate_play
from ah.port.cashflow_tier0 import load_spec
from ah.port.cashflow_tier1 import load_linkage, run_tier1

__all__ = [
    "PROGRAMME_CSS",
    "PROGRAMME_PATHS",
    "PROGRAMME_PLAUSIBLE",
    "Band",
    "LadderYear",
    "ProgrammeQuarter",
    "ProgrammeReport",
    "ProgrammeStat",
    "build_programme_report",
    "ladder_years",
    "model_block",
    "path_stats",
    "programme_quarters",
    "programme_stats",
    "render_programme_section",
    "vintage_stats",
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
    #: Undrawn commitment cancelled at terminal lapse (ER-6 / audit F2).
    expired_undrawn: float = 0.0
    #: The part of ``distributions`` that was a fund winding up (ER-12).
    terminal_distributions: float = 0.0


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
    #: Commitment that left the ladder WITHOUT being called, this year. The
    #: unfunded balance falls by this much with no cash moving — the one
    #: column that explains a drop in ``unfunded_end`` that ``called`` does
    #: not account for (ER-6's visible expiry; surfaced by audit F2).
    expired: float = 0.0


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
                expired_undrawn=q.expired_undrawn,
                terminal_distributions=q.terminal_distributions,
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
        # Slice the source run by the BLOCK's own length, not a fixed stride:
        # ``quarters`` and ``linked.quarters`` are the same length today, but
        # if a caller ever passes a truncated rows list (as
        # ``test_ladder_years_handles_partial_blocks`` does) a fixed stride
        # would take four source quarters against a two-row block and desync
        # the ``committed`` column from ``called``/``distributed`` in the same
        # table row -- review round 2, M-a.
        source = linked.quarters[start : start + len(block)]
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
                expired=sum(r.expired_undrawn for r in block),
            )
        )
    return years


_REPO_ROOT = Path(__file__).resolve().parents[2]
_COHORT_DOC = _REPO_ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"


@lru_cache(maxsize=1)
def _cohort_doc() -> dict[str, Any]:
    """The frozen cohort fixture, read once.

    ``vintage_stats`` re-reads this per path (20 paths/world) and
    ``_model_curves``/``model_block`` read it again per report; none of it
    ever changes within a process, so ``lru_cache`` is safe -- the fixture is
    a committed, read-only file (``fixtures/state/closed-end-cohort.example.json``),
    not something a running console could mutate underneath itself.
    """
    return json.loads(_COHORT_DOC.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Band:
    """A declared plausible range. A prior written down for argument, not truth."""

    lo: float
    hi: float
    question: str


#: DECLARED PRIORS — edit them, that is the point. A flag is an invitation to
#: look; nothing here can fail a build. Single-cohort statistics are defined
#: against the vintage committed in YEAR 1, at the stated age: "DPI at year 10"
#: is meaningless in a ten-year decade, because that vintage only reaches 9.
PROGRAMME_PLAUSIBLE: dict[str, Band] = {
    "peak_unfunded_ratio": Band(0.25, 0.75, "is the ladder over- or under-committed"),
    "call_rate_y1_3": Band(0.15, 0.45, "do funds draw at a realistic speed"),
    "crossover_years": Band(4.0, 8.0, "the J-curve crossover"),
    "dpi_age9": Band(0.7, 2.0, "does a fund actually return capital"),
    # RE-DECLARED, review round 2 C2, when linkage_bite became a TRAILING
    # four-quarter rate with cohort wind-ups excluded. The old 0.30-0.80 was a
    # prior about a SINGLE quarter's rate; a four-quarter window necessarily
    # reads closer to 1.0 than the quarter at its end, because three of its
    # four quarters are the approach to the trough rather than the trough. Two
    # further effects push the ratio up and are properties of the programme,
    # not the linkage: the decade's median trailing rate includes the opening
    # years, when the ladder has barely begun distributing, and the deepest
    # drawdown usually falls late, when the bow curve has the cohorts at their
    # most productive. 0.50-1.20 keeps teeth in both directions -- below 0.50
    # the programme's capital return has more than halved at the trough, above
    # 1.20 the worst market of the decade left distributions untouched and the
    # linkage is not doing the job it exists to do. The four presets currently
    # read 0.74-0.85 (unflagged); the old band split them arbitrarily across
    # its 0.80 edge on indistinguishable behaviour.
    "linkage_bite": Band(0.50, 1.20, "how hard the linkage bites, as a trailing rate not a level"),
    "linkage_shortfall": Band(0.05, 0.35, "the linkage's total decade cost"),
    "forced_secondaries": Band(0.0, 1.0, "is distress rare enough to mean something"),
}


@dataclass(frozen=True)
class ProgrammeStat:
    """One statistic across the ensemble, against its declared band.

    ``n_present``/``n_total`` carry HOW MANY of the ensemble's paths the
    median was actually computed from. ``vintage_stats`` and ``path_stats``
    both omit keys they cannot compute (e.g. no crossover ever happens, or a
    path is too short) rather than substituting a placeholder, so a
    statistic can be present on a small, non-representative slice of the
    lineage. If presence correlates with outcome -- a crossover key that
    only exists on fast-crossing paths, say -- the median over the present
    subset silently describes a biased sample, not the world. Showing the
    count as "n of N paths" on the page makes that visible instead of
    hidden behind a single clean-looking number.

    ``path0`` is ``None`` when path 0 itself never computed this statistic.
    Review round 1, I3: it used to fall back to the median, which -- now
    that the adjacent column can read "1 of 20" -- would silently show a
    made-up "path 0" value for a statistic path 0 never had.

    ``median``/``p10``/``p90`` are ``None`` when NO path computed the
    statistic. Review round 2, I2: the row used to be dropped entirely in
    that case, which is precisely backwards -- partial presence was made
    visible by the count column while TOTAL absence, the case a reader most
    needs to see, vanished without trace and left "this never happened"
    indistinguishable from "somebody forgot to compute it". A row reading
    "0 of 20" with dashes and a flag says which.
    """

    name: str
    median: float | None
    p10: float | None
    p90: float | None
    path0: float | None
    band: Band
    flagged: bool
    n_present: int
    n_total: int


def vintage_stats(
    drawdown_depth: np.ndarray, spread_ratio: np.ndarray, quarters: int
) -> dict[str, float]:
    """The single-cohort statistics for a vintage committed in year 1.

    Run through ``run_tier1`` rather than read out of the play run: these are
    questions about the MODEL's own cashflow shape, not about any particular
    world's market luck. So the cohort's sleeve returns are held at tier 0's
    own frozen constant growth (``g_annual`` in
    ``mappings/cashflow-tier0-v1.0.yaml``, converted to a quarterly rate) --
    that constant is what "tier 0" means -- rather than at zero. Zero growth
    made the J-curve crossover arithmetically impossible (NAV cannot outgrow
    calls net of distributions without growth) and left DPI structurally
    capped below 1.0, which is a defect of the test harness, not a question
    about the model. Committed is 1.0 so every output is a ratio.

    ``drawdown_depth``/``spread_ratio`` are the WORLD's full market-state path,
    world quarter 0 first -- the same convention ``ProgrammeQuarter`` uses
    everywhere else on this page. A vintage "committed in year 1" is not
    committed until the programme's own year-1 anniversary (world quarter
    index ``_QUARTERS_PER_YEAR``, matching ``ah.play``'s own annual
    commitment cadence), so ITS quarters are the world's quarters
    ``_QUARTERS_PER_YEAR`` through ``_QUARTERS_PER_YEAR + quarters - 1`` --
    NOT the world's first ``quarters`` quarters, which is mostly the
    programme's opening years, before this vintage exists at all.
    """
    base = _cohort_doc()
    start = _QUARTERS_PER_YEAR
    n = min(quarters, max(0, len(drawdown_depth) - start))
    if n < _QUARTERS_PER_YEAR:
        return {}
    g_quarterly = (1.0 + float(load_spec()["g_annual"])) ** 0.25 - 1.0
    result = run_tier1(
        base,
        committed=1.0,
        vintage_year=int(base["identity"]["vintage_year"]) + 1,
        sleeve_returns=np.full(n, g_quarterly),
        drawdown_depth=np.asarray(drawdown_depth[start : start + n], dtype=float),
        spread_ratio=np.asarray(spread_ratio[start : start + n], dtype=float),
        fees_on=False,
    )
    calls = np.array([f.call for f in result.flows])
    dists = np.array([f.distribution_total for f in result.flows])
    paid_in = float(calls.sum())
    out: dict[str, float] = {"first_call": float(calls[0])}
    if paid_in > 0.0:
        out["dpi_age9"] = float(dists.sum()) / paid_in
        first_three = calls[: 3 * _QUARTERS_PER_YEAR].sum()
        out["call_rate_y1_3"] = float(first_three) / 3.0  # committed = 1.0
    cum = np.cumsum(dists - calls)
    crossed = np.flatnonzero(cum > 0.0)
    if crossed.size:
        out["crossover_years"] = float(crossed[0] + 1) / _QUARTERS_PER_YEAR
    return out


#: ``linkage_bite``'s trailing window, in quarters. Review round 2, C2: a
#: single-quarter distribution rate is dominated by cohort wind-ups -- a whole
#: cohort's NAV pays out in one quarter, against a private NAV the payout has
#: itself just collapsed. Measured on deflation_bust path 0, quarter 19: rate
#: 1.8167 against a median of 0.0164, reporting a 110x INCREASE in
#: distributions at the exact quarter f_dist was pinned to its 0.300 floor.
_BITE_WINDOW = 4


def _trailing_distribution_rates(
    quarters: list[ProgrammeQuarter],
) -> list[tuple[float, float]]:
    """``(trailing distribution rate, that quarter's drawdown depth)`` pairs.

    The rate is ``_BITE_WINDOW`` quarters of distributions (this quarter and
    the three before it), NET of any fund winding up, over the private NAV at
    the START of that window -- the closing private NAV of the quarter before
    the window, falling back to the window's own first quarter when the window
    starts at quarter 0 and there is no earlier close to read. A trailing
    figure means one large quarter is at most a quarter of the numerator
    instead of all of it. Quarters without a full window of history are
    excluded rather than computed on a short one.

    **The terminal lump is netted by AMOUNT, not by index (ER-12 follow-up).**
    A fund reaching the end of its life pays its whole remaining NAV out in
    one quarter; that is a contractual event on the FUND's clock and says
    nothing about the market linkage, but it lands in the same
    ``distributions`` field as ordinary yield. Review round 2 (C2) handled it
    by dropping every window that overlapped a wind-up, correctly reasoning
    that a lump three quarters back pollutes a trailing numerator as much as
    one in the quarter itself. That rule assumed wind-ups are RARE. Once the
    opening book became a staggered ladder (ER-12) a rung retires every year,
    every four-quarter window overlapped one, and the statistic went undefined
    on 20 of 20 paths -- the console's only linkage diagnostic, dead.

    Subtracting the lump keeps the same protection without discarding the
    window, and is strictly more precise than the old inference: it uses the
    amount the cohort model REPORTED as terminal
    (``CohortStep.is_terminal``), so a forced secondary -- which also drives a
    cohort's NAV to zero but pays no distribution -- is no longer mistaken for
    a wind-up.
    """
    out: list[tuple[float, float]] = []
    for i in range(_BITE_WINDOW - 1, len(quarters)):
        first = i - _BITE_WINDOW + 1
        opening = quarters[first - 1].private_nav if first > 0 else quarters[first].private_nav
        if opening <= 0.0:
            continue
        total = sum(
            quarters[j].distributions - quarters[j].terminal_distributions
            for j in range(first, i + 1)
        )
        out.append((total / opening, quarters[i].drawdown_depth))
    return out


def path_stats(quarters: list[ProgrammeQuarter], result: PlayResult) -> dict[str, float]:
    """The programme-level statistics for ONE path."""
    out: dict[str, float] = {}
    ratios = [q.unfunded / q.private_nav for q in quarters if q.private_nav > 0.0]
    if ratios:
        out["peak_unfunded_ratio"] = max(ratios)

    # linkage_bite: the TRAILING four-quarter distribution rate in the
    # deepest-drawdown quarter, over the median trailing rate of the decade,
    # with cohort wind-up windows excluded from both. It asks "when the market
    # was at its worst, how did the rate at which the programme returned
    # capital compare with a normal quarter" -- below 1.0 means the linkage
    # suppressed distributions, above 1.0 means it did not. The worst quarter
    # is chosen on DRAWDOWN DEPTH and never on the distribution value, or the
    # statistic would be circular.
    rates = _trailing_distribution_rates(quarters)
    if rates:
        worst = max(rates, key=lambda pair: pair[1])[0]
        median = float(np.median([r for r, _ in rates]))
        if median > 0.0:
            out["linkage_bite"] = worst / median

    unlinked_total = sum(q.distributions_unlinked for q in quarters)
    if unlinked_total > 0.0:
        linked_total = sum(q.distributions for q in quarters)
        out["linkage_shortfall"] = (unlinked_total - linked_total) / unlinked_total

    out["forced_secondaries"] = float(result.forced_secondaries)
    return out


def _e(s: object) -> str:
    return _html.escape(str(s))


def _f(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}"


#: f_call's clip bounds are NOT separate keys in mappings/cashflow-tier1-v1.0.yaml
#: (they live inside the `form` string and in cashflow_tier1.py's own clip call) --
#: named here explicitly so the duplication is visible rather than silent.
#: Source of truth: src/ah/port/cashflow_tier1.py:66, `np.clip(1 - c*dd, 0.5, 1.2)`.
_F_CALL_LO = 0.5
_F_CALL_HI = 1.2

_DD_DOMAIN = [i / 40.0 for i in range(41)]  # 0 .. 1.0 drawdown, the x-axis both f_* share


def _sparkline(
    values: list[float],
    *,
    width: int = 150,
    height: int = 34,
    color: str,
    domain: tuple[float, float] | None = None,
    extra: str = "",
) -> str:
    """A minimal polyline. No axes: these curves are about SHAPE, and every
    one of them has its numbers printed beside it.

    ``domain``, when given, fixes the y-range to the model's OWN declared
    bounds (e.g. a linkage function's floor/ceiling) instead of the values'
    realised min/max -- two curves plotted against their own min/max look
    equally steep regardless of how far either actually moves, which is
    exactly the asymmetry this block exists to show. ``None`` keeps the
    auto-scaling behaviour, used for curves with no declared bound (the call
    rate, the bow).

    ``extra`` is rendered inside the ``<svg>``, after the polyline — the rug
    overlay (Task 4 ambiguity #2) uses it instead of string-splicing the
    closing tag.
    """
    if not values:
        return ""
    lo, hi = domain if domain is not None else (min(values), max(values))
    span = (hi - lo) or 1.0
    step = width / max(1, len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{height - (v - lo) / span * (height - 2) - 1:.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg class="spark" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{points}"/>'
        f"{extra}"
        "</svg>"
    )


def _rug(
    xs: list[float],
    ys: list[float],
    *,
    width: int = 150,
    height: int = 34,
    domain: tuple[float, float] | None = None,
    x_domain: tuple[float, float] | None = None,
) -> str:
    """Where this world's quarters actually landed on a response curve.

    BOTH axes must match the curve underneath, and for the same reason: a rug
    plotted on a different range than its curve lands its dots in the wrong
    place, which is worse than no rug at all -- a reader checks a dot against
    the curve it sits on, and a dot that disagrees with the curve is a lie
    told in ink.

    ``domain`` is the Y range and MUST match the ``domain`` passed to the
    ``_sparkline`` call for the curve this rug overlays. ``x_domain`` is the X
    range and MUST match the domain the curve's own values were SAMPLED over
    (``_DD_DOMAIN`` for both linkage responses), because ``_sparkline`` spreads
    those samples evenly across the full width. Review round 2, C1: ``x_domain``
    did not exist and X auto-scaled to ``max(xs)``, so every dot was stretched
    horizontally by ``1 / max(drawdown)`` -- on goldilocks (max drawdown 0.278)
    a quarter whose drawdown was 0.109 landed where the curve reads 0.392.
    ``None`` on either axis keeps that auto-scaling, and is only safe for a
    rug over an auto-scaled curve.
    """
    if not xs:
        return ""
    x_lo, x_hi = x_domain if x_domain is not None else (min(xs), max(xs))
    x_span = (x_hi - x_lo) or 1.0
    y_lo, y_hi = domain if domain is not None else (min(ys), max(ys))
    span = (y_hi - y_lo) or 1.0
    dots = "".join(
        f'<circle cx="{(x - x_lo) / x_span * width:.1f}" '
        f'cy="{height - (y - y_lo) / span * (height - 2) - 1:.1f}" r="1.6"/>'
        for x, y in zip(xs, ys, strict=True)
    )
    return f'<g class="rug" fill="var(--brass)" opacity="0.75">{dots}</g>'


def _model_curves() -> dict[str, list[float]]:
    """The four curves ``model_block`` renders, isolated so their VALUES are
    directly testable -- not just their presence as substrings in HTML.

    Keys: ``call_rate`` (RC(age), from the cohort's own ``rc_curve``),
    ``bow`` (the distribution bow Y(age/L)^B), ``f_dist`` and ``f_call``
    (the two linkage responses over drawdown depth, at spread_ratio = 1).
    """
    doc = _cohort_doc()
    params = doc["parameters"]
    life = float(doc["lifecycle"]["contractual_life_years"])
    rc_curve = [float(v) for v in params["rc_curve"]]
    bow, yield_rate = float(params["bow"]), float(params["yield_rate"])
    link = load_linkage()
    fd_spec, fc_spec = link["f_dist"], link["f_call"]

    ages = [i * 0.25 for i in range(int(life * 4) + 1)]
    bow_curve = [yield_rate * (min(1.0, a / life) ** bow) for a in ages]
    fd_curve = [
        min(
            fd_spec["ceiling"],
            max(fd_spec["floor"], float(np.exp(-fd_spec["a_drawdown"] * d))),
        )
        for d in _DD_DOMAIN
    ]
    fc_curve = [min(_F_CALL_HI, max(_F_CALL_LO, 1.0 - fc_spec["c"] * d)) for d in _DD_DOMAIN]
    return {"call_rate": rc_curve, "bow": bow_curve, "f_dist": fd_curve, "f_call": fc_curve}


def model_block(
    realised: list[ProgrammeQuarter] | None = None, realised_title: str | None = None
) -> str:
    """The model's own curves, before any world touches them.

    World-independent except for the optional rug, which marks where ONE
    world's quarters landed on the two response curves.

    ``realised_title`` names the world the rug came from. Review round 2, I1:
    this block is rendered ONCE, above every world's section, but the console
    is routinely invoked multi-world (``ah credibility --preset stagflation
    --preset goldilocks``), so a reader in the second world's section who
    scrolls up is looking at the FIRST world's rug. The caption said "this
    world's quarters", which is false for every world but the first; naming
    the world makes the rug's provenance impossible to misread.
    """
    doc = _cohort_doc()
    params = doc["parameters"]
    life = float(doc["lifecycle"]["contractual_life_years"])
    bow, yield_rate = float(params["bow"]), float(params["yield_rate"])
    link = load_linkage()
    fd_spec, fc_spec = link["f_dist"], link["f_call"]
    fd_domain = (float(fd_spec["floor"]), float(fd_spec["ceiling"]))
    fc_domain = (_F_CALL_LO, _F_CALL_HI)

    curves = _model_curves()
    rc_curve, bow_curve = curves["call_rate"], curves["bow"]
    fd_curve, fc_curve = curves["f_dist"], curves["f_call"]

    # The x-axis both response curves are SAMPLED over -- the rug must use the
    # same one or its dots sit at drawdowns the curve never had (C1).
    dd_domain = (_DD_DOMAIN[0], _DD_DOMAIN[-1])

    rug_dist = rug_call = ""
    if realised:
        rug_dist = _rug(
            [q.drawdown_depth for q in realised],
            [q.f_dist for q in realised],
            domain=fd_domain,
            x_domain=dd_domain,
        )
        rug_call = _rug(
            [q.drawdown_depth for q in realised],
            [q.f_call for q in realised],
            domain=fc_domain,
            x_domain=dd_domain,
        )

    rows = [
        (
            "call rate RC(age)",
            _sparkline(rc_curve, color="var(--jade)"),
            "annual, on unfunded: " + ", ".join(_f(v) for v in rc_curve),
        ),
        (
            "distribution bow Y(age/L)^B",
            _sparkline(bow_curve, color="var(--jade)"),
            f"Y={_f(yield_rate)}, B={_f(bow, 1)}, L={_f(life, 0)} yrs; "
            "terminal liquidation at age >= L",
        ),
        (
            "f_dist(drawdown)",
            _sparkline(fd_curve, color="var(--clay)", domain=fd_domain, extra=rug_dist),
            f"a={_f(fd_spec['a_drawdown'], 6)}, b={_f(fd_spec['b_log_spread'], 6)} "
            "(log spread), "
            f"floor {fd_spec['floor']}, ceiling {fd_spec['ceiling']} "
            "- shown at spread_ratio = 1, plotted against its own declared bounds",
        ),
        (
            "f_call(drawdown)",
            _sparkline(fc_curve, color="var(--clay)", domain=fc_domain, extra=rug_call),
            f"c={fc_spec['c']}, clipped to [{_F_CALL_LO}, {_F_CALL_HI}] "
            "(cashflow_tier1.py:66) - plotted against its own declared bounds",
        ),
    ]
    body = "".join(
        f"<tr><td>{_e(name)}</td><td>{svg}</td><td class='note'>{_e(note)}</td></tr>"
        for name, svg, note in rows
    )
    whose = f"{_e(realised_title)}'s" if realised_title else "this world's"
    return (
        "<h3>The model, before any world touches it</h3>"
        f"<table><tbody>{body}</tbody></table>"
        "<p class='note'>Both linkage functions consume <strong>continuous</strong> "
        "market states only - drawdown depth and a spread ratio - and never a regime "
        "label (DN-5 Delta 3, structural). Both are drawn against their own declared "
        "clip bounds, not their realised min/max, so the vertical scale is the "
        "model's own range: f_dist spans floor to ceiling, f_call spans "
        f"[{_F_CALL_LO}, {_F_CALL_HI}]. The asymmetry is the mechanic: f_call is "
        "clipped near-flat while f_dist can fall to its floor, so calls keep arriving "
        "while distributions stop. That, not the drawdown itself, is what empties the "
        f"cash account. Brass dots mark where {whose} quarters actually landed - one "
        "world only, on both axes of the curve they sit on (drawdown across, "
        "multiplier up), even when several worlds are rendered below. Expect the "
        "f_call dots to lie exactly ON their curve and the f_dist dots to scatter "
        "vertically around theirs: f_call is a function of drawdown alone, while "
        "f_dist also responds to the spread ratio, which the curve holds at 1. That "
        "vertical spread IS the spread term, not a plotting artefact. Dots stopping "
        "short of the right-hand edge mean the world never reached those "
        "drawdowns.</p>"
    )


def programme_stats(
    per_path: list[dict[str, float]], path0: dict[str, float]
) -> list[ProgrammeStat]:
    """Median and 10-90 spread across paths, flagged against the declared band.

    One path can be unlucky; a flag should mean the WORLD does this, so the
    flag fires on the median, with path 0's own value shown beside it.

    A statistic no path could compute still gets a row -- "0 of N", dashes,
    flagged (review round 2, I2). It is flagged because a declared band with
    nothing to judge against it is an unanswered question, and an unanswered
    question is exactly what a flag is an invitation to go and look at.
    """
    n_total = len(per_path)
    stats: list[ProgrammeStat] = []
    for name, band in PROGRAMME_PLAUSIBLE.items():
        values = [row[name] for row in per_path if name in row]
        if not values:
            stats.append(
                ProgrammeStat(
                    name=name,
                    median=None,
                    p10=None,
                    p90=None,
                    path0=None,
                    band=band,
                    flagged=True,
                    n_present=0,
                    n_total=n_total,
                )
            )
            continue
        median = float(np.median(values))
        stats.append(
            ProgrammeStat(
                name=name,
                median=median,
                p10=float(np.percentile(values, 10)),
                p90=float(np.percentile(values, 90)),
                path0=float(path0[name]) if name in path0 else None,
                band=band,
                flagged=not (band.lo <= median <= band.hi),
                n_present=len(values),
                n_total=n_total,
            )
        )
    return stats


#: 20 full waterfall simulations per world, against the console's 400
#: vectorised return paths — each of these runs the whole quarterly waterfall.
#: Raise it if it turns out cheap.
PROGRAMME_PATHS = 20


@dataclass(frozen=True)
class ProgrammeReport:
    """Everything the section shows for one world."""

    world_id: str
    title: str
    quarters: list[ProgrammeQuarter]
    ladder: list[LadderYear]
    stats: list[ProgrammeStat]
    vintage_stack: list[tuple[str, list[float]]]
    forced_sales: list[dict[str, object]]

    @property
    def flag_count(self) -> int:
        return sum(1 for s in self.stats if s.flagged)


def _vintage_stack(result: PlayResult) -> list[tuple[str, list[float]]]:
    """Every cohort's NAV over the decade, zero before it was committed."""
    names: list[str] = []
    for q in result.quarters:
        for key in q.vintage_nav:
            if key not in names:
                names.append(key)
    return [(name, [q.vintage_nav.get(name, 0.0) for q in result.quarters]) for name in names]


def build_programme_report(
    world: NumericWorld,
    *,
    base_seed: int,
    n_paths: int = PROGRAMME_PATHS,
    title: str | None = None,
) -> ProgrammeReport:
    """Detail from path 0; statistics across the seed lineage.

    Dispatches on the world's generator (sp-04): generated worlds walk the
    programme exactly as toy ones, on the adapter tape with the generated
    opening book — the console's pending note retires.
    """
    if world.engine_defaults.generator_id == "toy-v0":
        path_fn, targets = run_path, None
    else:
        from ah.port.adapter import GEN_START_TARGETS, run_gen_path

        path_fn, targets = run_gen_path, GEN_START_TARGETS

    per_path: list[dict[str, float]] = []
    path0_rows: list[ProgrammeQuarter] = []
    path0_result: PlayResult | None = None
    path0_stats: dict[str, float] = {}

    for k in range(max(1, n_paths)):
        paths = path_fn(world, base_seed + 7919 * k)
        linked = simulate_play(paths, start_targets=targets)
        unlinked = simulate_play(paths, linkage=False, start_targets=targets)
        rows = programme_quarters(linked, unlinked)
        stats = path_stats(rows, linked)
        stats.update(
            vintage_stats(
                np.array([r.drawdown_depth for r in rows]),
                np.array([r.spread_ratio for r in rows]),
                len(rows) - _QUARTERS_PER_YEAR,
            )
        )
        per_path.append(stats)
        if k == 0:
            path0_rows, path0_result, path0_stats = rows, linked, stats

    assert path0_result is not None  # n_paths >= 1 by construction
    return ProgrammeReport(
        world_id=world.world_id,
        title=title or world.world_id,
        quarters=path0_rows,
        ladder=ladder_years(path0_rows, path0_result),
        stats=programme_stats(per_path, path0_stats),
        vintage_stack=_vintage_stack(path0_result),
        forced_sales=list(path0_result.sale_log),
    )


PROGRAMME_CSS = """
.spark{vertical-align:middle}
.prog td.pos{color:var(--jade)}
.prog td.neg{color:var(--clay)}
.stack{display:flex;height:38px;align-items:flex-end;gap:1px}
.stack i{display:block;flex:1;background:var(--jade);opacity:.55}
"""


def _ladder_table(rep: ProgrammeReport) -> str:
    head = (
        "<tr><th>year</th><th>committed</th><th>called</th><th>distributed</th>"
        "<th>net</th><th>called to date</th><th>expired</th><th>unfunded end</th>"
        "<th>private NAV end</th></tr>"
    )
    rows = "".join(
        f"<tr><td>{y.year}</td><td>{_f(y.committed)}</td><td>{_f(y.called)}</td>"
        f"<td>{_f(y.distributed)}</td>"
        f"<td class='{'pos' if y.net >= 0 else 'neg'}'>{_f(y.net)}</td>"
        f"<td>{_f(y.called_to_date)}</td>"
        f"<td class='{'neg' if y.expired > 0 else ''}'>{_f(y.expired)}</td>"
        f"<td>{_f(y.unfunded_end)}</td>"
        f"<td>{_f(y.private_nav_end)}</td></tr>"
        for y in rep.ladder
    )
    note = (
        "<p class='note'><strong>expired</strong> is undrawn commitment "
        "CANCELLED at the end of a cohort's contractual life (ER-6's visible "
        "lapse) — it leaves <em>unfunded end</em> without any cash being "
        "called, so a year where <em>unfunded end</em> falls by more than "
        "<em>called</em> is explained here and nowhere else.</p>"
    )
    return f"<table class='prog'><thead>{head}</thead><tbody>{rows}</tbody></table>{note}"


def _linkage_effect(q: ProgrammeQuarter) -> float:
    """``distributions_unlinked - distributions``, matching the sign
    ``path_stats``'s ``linkage_shortfall`` uses (``(unlinked - linked) /
    unlinked``, sealed in the declared bands): positive means the linkage
    SUPPRESSED distributions below the unlinked counterfactual (a cost),
    negative means it RAISED them above it (a benefit).

    ``f_dist``'s ceiling is 1.5 (``mappings/cashflow-tier1-v1.0.yaml``), so
    the linkage routinely raises distributions rather than only ever
    cutting them -- review round 1, C1: the previous
    ``distributions - distributions_unlinked`` rendered unconditionally
    under a "shortfall" header painted that benefit red and disagreed in
    sign with ``linkage_shortfall`` on the very same page.
    """
    return q.distributions_unlinked - q.distributions


def _linkage_table(rep: ProgrammeReport) -> str:
    head = (
        "<tr><th>qtr</th><th>drawdown</th><th>spread ratio</th><th>f_dist</th>"
        "<th>f_call</th><th>distributions</th><th>linkage off</th>"
        "<th>unlinked minus linked</th></tr>"
    )
    rows = "".join(
        f"<tr><td>{q.quarter}</td><td>{_f(q.drawdown_depth, 3)}</td>"
        f"<td>{_f(q.spread_ratio, 3)}</td><td>{_f(q.f_dist, 3)}</td>"
        f"<td>{_f(q.f_call, 3)}</td><td>{_f(q.distributions)}</td>"
        f"<td>{_f(q.distributions_unlinked)}</td>"
        # positive == the linkage suppressed cash (a cost, painted clay);
        # negative == it raised cash above the unlinked counterfactual (a
        # benefit, painted jade) -- inverted from _ladder_table's net
        # column because here positive is the unwelcome direction.
        f"<td class='{'neg' if _linkage_effect(q) > 0.0 else 'pos'}'>"
        f"{_f(_linkage_effect(q))}</td></tr>"
        for q in rep.quarters
    )
    linked = sum(q.distributions for q in rep.quarters)
    unlinked = sum(q.distributions_unlinked for q in rep.quarters)
    if unlinked > linked:
        direction = "suppressed distributions below"
    elif unlinked < linked:
        direction = "raised distributions above"
    else:
        direction = "left distributions level with"
    return (
        f"<table class='prog'><thead>{head}</thead><tbody>{rows}</tbody></table>"
        f"<p class='note'>Decade total: {_f(linked)} received against {_f(unlinked)} "
        f"with the linkage off - over the decade the linkage {direction} "
        "what an unlinked tape would have paid; it can go either way, since "
        "f_dist has a ceiling (1.5) as well as a floor. Positive cells: the "
        "linkage suppressed that quarter's cash (a cost). Negative cells: it "
        "raised it (a benefit) -- the same sign convention as the stats "
        "table's linkage_shortfall. Caveat: 'linkage off' is a SEPARATE "
        "simulate_play run on the same tape, not the linked run with the "
        "linkage subtracted out -- so the decade total is a sound comparison, "
        "but each quarter's 'unlinked minus linked' cell mixes the linkage's "
        "direct effect with however far the two runs' NAV paths have already "
        "diverged by that quarter, and is approximate for that reason.</p>"
    )


def _coverage_str(value: float) -> str:
    """Render a coverage ratio, spelling out the NAV-wiped case.

    ``_safe_ratio`` returns ``float("inf")`` when NAV <= 0 -- unfunded
    obligations against no assets left to cover them, not a ratio with a
    numeric value. Handing that straight to ``_f`` would print the literal
    string "inf", which reads as a formatting bug rather than the
    institution's actual state (an infinitely uncovered book, matching
    ``Portfolio.coverage_true``'s own convention).
    """
    return "NAV wiped" if value == float("inf") else _f(value)


def _sale_row(s: dict[str, object]) -> str:
    """One forced-sale table row. ``s`` is a logged event (spec §8): period,
    amount, cause, and the sleeves sold -- typed as ``object`` because the log
    is a heterogeneous dict, so the values are narrowed here rather than at
    the call site.

    ``PortfolioEngine._period`` (``src/ah/port/engine.py:75,90``) starts at 0
    and increments at the TOP of ``run_quarter``, before that quarter's own
    work -- so it is 1-based (the first quarter logs period 1). Every other
    quarter number on this page is ``PlayQuarter.quarter``/
    ``ProgrammeQuarter.quarter``, 0-based. Review round 1, I1: rendering the
    sale log's period unconverted made a forced sale line up one quarter
    early against the linkage table's row for the same event.
    """
    sleeves_sold = s.get("sleeves_sold", [])
    sleeves = ", ".join(str(x) for x in sleeves_sold) if isinstance(sleeves_sold, list) else ""
    amount = s.get("amount", 0.0)
    amount_f = float(amount) if isinstance(amount, int | float) else 0.0
    period = s.get("period", 0)
    period0 = int(period) - 1 if isinstance(period, int | float) else period
    return (
        f"<tr><td>Q{_e(period0)}</td><td>{_e(s.get('kind'))}</td>"
        f"<td>{_e(s.get('cause'))}</td><td>{_e(sleeves)}</td>"
        f"<td>{_f(amount_f)}</td></tr>"
    )


def _liquidity_block(rep: ProgrammeReport) -> str:
    cash_series = [q.cash for q in rep.quarters]
    cash = _sparkline(cash_series, color="var(--jade)")
    # Review round 2, M-b: the cash spark auto-scales, so its line touches the
    # bottom of the plot at its own minimum whatever the level -- a decade
    # ending at 0.000 and one ending at 12.0 draw the same shape. _sparkline's
    # docstring is only true of axis-less curves whose numbers are printed
    # beside them, so print them.
    # The peak is printed alongside the low and the final because the plot is
    # auto-scaled: its top edge IS the peak and its bottom edge IS the low, so
    # without both numbers the curve's shape carries no level at all. Every
    # preset happens to end the decade at 0.000, which makes the low and the
    # final identical and the peak the only number that says how far it fell.
    levels = (
        f" &nbsp; cash: peak {_f(max(cash_series))}, low {_f(min(cash_series))}, "
        f"final {_f(cash_series[-1])} (the plot is auto-scaled between peak and low)"
        if cash_series
        else ""
    )
    worst = max(rep.quarters, key=lambda q: q.coverage_true)
    sales = "".join(_sale_row(s) for s in rep.forced_sales)
    table = (
        "<table class='prog'><thead><tr><th>when</th><th>kind</th><th>cause</th>"
        f"<th>sold</th><th>raised</th></tr></thead><tbody>{sales}</tbody></table>"
        if sales
        else "<p class='note'>No forced sales this decade.</p>"
    )
    return (
        f"<p>cash {cash}{levels} &nbsp; worst coverage: "
        f"{_coverage_str(worst.coverage_true)} true vs "
        f"{_coverage_str(worst.coverage_reported)} reported (quarter {worst.quarter})</p>"
        # Review round 2, I3: "coverage 0.58" reads to a newcomer as "58%
        # covered", which is the opposite of what it says. It is the
        # Portfolio.coverage_true convention -- unfunded over NAV -- so it must
        # say so, and say which way is bad.
        "<p class='note'><strong>Coverage</strong> here is unfunded obligations "
        "divided by NAV (the <code>Portfolio.coverage_true</code> convention), so "
        "<strong>higher is worse</strong>: 0.58 means undrawn commitments worth 58% "
        "of the whole book, not a book 58% covered. 'True' uses true NAV, "
        "'reported' the smoothed NAV a committee would actually be shown; the "
        "reported figure flatters the institution exactly when the true one is "
        "moving. Selling liquid holdings to fund a call is ordinary funding; "
        "a forced <em>secondary</em> at the policy haircut is distress. They are "
        "listed apart because collapsing them teaches the reader to ignore the "
        "words.</p>" + table
    )


def _stack_block(rep: ProgrammeReport) -> str:
    bars = "".join(
        f"<i style='height:{min(100.0, series[-1] * 4.0):.0f}%'></i>"
        for _, series in rep.vintage_stack
    )
    # ``_vintage_stack`` collects every cohort id ``play.py`` ever wrote a
    # ``vintage_nav`` entry for, including ones fully liquidated (terminal
    # distribution or a forced secondary sold to zero) long before the
    # decade's end -- review round 1, C2: the heading's own "alive" claim
    # must count only cohorts with a positive final NAV, not every cohort
    # ever committed.
    alive = sum(1 for _, series in rep.vintage_stack if series and series[-1] > 0.0)
    return (
        f"<div class='stack'>{bars}</div>"
        f"<p class='note'>{alive} of {len(rep.vintage_stack)} cohorts ever committed are "
        "still alive (positive NAV) at the decade's end, newest on the right. A "
        "programme with nothing on the right has stopped committing; one with "
        "nothing on the left has run its openers to term.</p>"
    )


def _dash(value: float | None, places: int = 3) -> str:
    """A value, or "-" when there is none. Never a substituted zero: an
    absent statistic and a statistic that came out at 0.000 are different
    findings and must not print the same."""
    return _f(value, places) if value is not None else "-"


def _stat_row(s: ProgrammeStat) -> str:
    # "-" rather than a value when path 0 never computed this statistic --
    # review round 1, I3: falling back to the median here silently invented
    # a "path 0" number for a statistic path 0 didn't have, right beside a
    # present-count column that would otherwise make the gap visible.
    # Review round 2, I2: median/p10/p90 dash out the same way on a "0 of N"
    # row, which is rendered rather than dropped.
    spread = f"{_dash(s.p10)} - {_dash(s.p90)}" if s.p10 is not None or s.p90 is not None else "-"
    return (
        f"<tr class='{'flagged' if s.flagged else ''}'><td>{_e(s.name)}</td>"
        f"<td>{_dash(s.median)}</td><td>{spread}</td>"
        f"<td>{_dash(s.path0)}</td>"
        f"<td>{s.n_present} of {s.n_total}</td>"
        f"<td>{_f(s.band.lo, 2)} - {_f(s.band.hi, 2)}</td>"
        f"<td class='note'>{_e(s.band.question)}</td></tr>"
    )


def _stats_table(rep: ProgrammeReport) -> str:
    head = (
        "<tr><th>statistic</th><th>median</th><th>p10-p90</th><th>path 0</th>"
        "<th>paths</th><th>declared</th><th>the question</th></tr>"
    )
    rows = "".join(_stat_row(s) for s in rep.stats)
    return (
        f"<table class='prog'><thead>{head}</thead><tbody>{rows}</tbody></table>"
        "<p class='note'>Bands are declared priors, not truth; a flag is an "
        "invitation to look. <strong>linkage_bite</strong> is a ratio of "
        "<em>trailing four-quarter</em> distribution rates - four quarters of "
        "distributions over the private NAV the window opened with - taken in "
        "the deepest-drawdown quarter and divided by the decade's median. Below "
        "1.0 means the linkage cut the rate at which capital came back when the "
        "market was at its worst. Read above 1.0 with care rather than as a "
        "benefit: the median is taken over the whole decade including the opening "
        "years, when the ladder has barely started distributing, so a deep "
        "drawdown that lands late - against mature cohorts - can clear the median "
        "on the programme's own age curve alone. Windows containing a cohort's terminal "
        "liquidation are excluded from both ends of that comparison: a wind-up "
        "pays a whole cohort's NAV out at once on the fund's contractual clock, "
        "which would otherwise swamp the market signal the statistic is asking "
        "about. A row reading <strong>0 of N</strong> with dashes is a statistic "
        "NO path could compute - not a zero, and not a statistic that was "
        "forgotten.</p>"
    )


def render_programme_section(reports: list[ProgrammeReport]) -> str:
    """The whole section: the model once, then each world."""
    if not reports:
        return ""
    blocks = []
    for rep in reports:
        blocks.append(
            f"<section class='world'><h2>{_e(rep.title)} - the private programme</h2>"
            "<h3>The commitment ladder, year by year</h3>"
            + _ladder_table(rep)
            + "<h3>Cohorts alive at the decade's end</h3>"
            + _stack_block(rep)
            + "<h3>The market, and what it did to the cash</h3>"
            + _linkage_table(rep)
            + "<h3>Liquidity and the waterfall</h3>"
            + _liquidity_block(rep)
            + "<h3>Against the declared bands</h3>"
            + _stats_table(rep)
            + "</section>"
        )
    return (
        "<h1>The private programme</h1>"
        "<p class='lede'>What the cashflow model and the commitment pacing actually "
        "do, before the commitment lever asks a player to set them. Detail is path 0; "
        "statistics are the median across the world's own seed lineage.</p>"
        + model_block(reports[0].quarters, reports[0].title)
        + "".join(blocks)
    )
