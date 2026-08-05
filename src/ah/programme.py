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
from pathlib import Path

import numpy as np

from ah.play import PlayResult
from ah.port.cashflow_tier0 import load_spec
from ah.port.cashflow_tier1 import load_linkage, run_tier1

__all__ = [
    "PROGRAMME_PLAUSIBLE",
    "Band",
    "LadderYear",
    "ProgrammeQuarter",
    "ProgrammeStat",
    "ladder_years",
    "model_block",
    "path_stats",
    "programme_quarters",
    "programme_stats",
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


_REPO_ROOT = Path(__file__).resolve().parents[2]
_COHORT_DOC = _REPO_ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"


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
    "linkage_bite": Band(0.30, 0.80, "how hard the linkage bites, as a rate not a level"),
    "linkage_shortfall": Band(0.05, 0.35, "the linkage's total decade cost"),
    "forced_secondaries": Band(0.0, 1.0, "is distress rare enough to mean something"),
}


@dataclass(frozen=True)
class ProgrammeStat:
    """One statistic across the ensemble, against its declared band."""

    name: str
    median: float
    p10: float
    p90: float
    path0: float
    band: Band
    flagged: bool


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
    """
    base = json.loads(_COHORT_DOC.read_text(encoding="utf-8"))
    n = min(quarters, len(drawdown_depth))
    if n < _QUARTERS_PER_YEAR:
        return {}
    g_quarterly = (1.0 + float(load_spec()["g_annual"])) ** 0.25 - 1.0
    result = run_tier1(
        base,
        committed=1.0,
        vintage_year=int(base["identity"]["vintage_year"]) + 1,
        sleeve_returns=np.full(n, g_quarterly),
        drawdown_depth=np.asarray(drawdown_depth[:n], dtype=float),
        spread_ratio=np.asarray(spread_ratio[:n], dtype=float),
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


def path_stats(quarters: list[ProgrammeQuarter], result: PlayResult) -> dict[str, float]:
    """The programme-level statistics for ONE path."""
    out: dict[str, float] = {}
    ratios = [q.unfunded / q.private_nav for q in quarters if q.private_nav > 0.0]
    if ratios:
        out["peak_unfunded_ratio"] = max(ratios)

    rates = [
        (q.distributions / q.private_nav, q.drawdown_depth) for q in quarters if q.private_nav > 0.0
    ]
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
) -> str:
    """Where this world's quarters actually landed on a response curve.

    ``domain`` MUST match the ``domain`` passed to the ``_sparkline`` call for
    the curve this rug overlays -- a rug plotted on a different y-range than
    its curve lands its dots at the wrong height, which is worse than no rug.
    """
    if not xs:
        return ""
    x_hi = max(xs) or 1.0
    y_lo, y_hi = domain if domain is not None else (min(ys), max(ys))
    span = (y_hi - y_lo) or 1.0
    dots = "".join(
        f'<circle cx="{x / x_hi * width:.1f}" '
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
    doc = json.loads(_COHORT_DOC.read_text(encoding="utf-8"))
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


def model_block(realised: list[ProgrammeQuarter] | None = None) -> str:
    """The model's own curves, before any world touches them.

    World-independent except for the optional rug, which marks where the
    decade's quarters landed on the two response curves.
    """
    doc = json.loads(_COHORT_DOC.read_text(encoding="utf-8"))
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

    rug_dist = rug_call = ""
    if realised:
        rug_dist = _rug(
            [q.drawdown_depth for q in realised],
            [q.f_dist for q in realised],
            domain=fd_domain,
        )
        rug_call = _rug(
            [q.drawdown_depth for q in realised],
            [q.f_call for q in realised],
            domain=fc_domain,
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
        "cash account. Brass dots mark where this world's quarters actually landed.</p>"
    )


def programme_stats(
    per_path: list[dict[str, float]], path0: dict[str, float]
) -> list[ProgrammeStat]:
    """Median and 10-90 spread across paths, flagged against the declared band.

    One path can be unlucky; a flag should mean the WORLD does this, so the
    flag fires on the median, with path 0's own value shown beside it.
    """
    stats: list[ProgrammeStat] = []
    for name, band in PROGRAMME_PLAUSIBLE.items():
        values = [row[name] for row in per_path if name in row]
        if not values:
            continue
        median = float(np.median(values))
        stats.append(
            ProgrammeStat(
                name=name,
                median=median,
                p10=float(np.percentile(values, 10)),
                p90=float(np.percentile(values, 90)),
                path0=float(path0.get(name, median)),
                band=band,
                flagged=not (band.lo <= median <= band.hi),
            )
        )
    return stats
