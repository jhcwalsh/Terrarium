"""The credibility console — walk a world's numbers before anyone plays it.

Owner's ask, verbatim: "an admin page that I can walk through the numbers for
a set of worlds so I can check that they are credible."

This is ADMIN tooling and nothing else. It reads worlds, regenerates ensembles
from stored seeds, and writes nothing. It is not in the pre-registration seal,
it never touches the scored path, and no number it computes reaches a player.
Its whole job is to put what a world actually produces in front of a human,
next to the range a human said was plausible, and mark the gaps.

The bands in :data:`PLAUSIBLE` are DECLARED PRIORS, not truth. They are one
allocator's view of what a decade of each asset class can plausibly do,
written down so that disagreement is about a number rather than about a vibe.
Edit them; that is the point. A flagged row is an invitation to look, not a
failure — nothing here can fail a build.

Provenance for the sceptical: every statistic is computed from the same
``run_ensemble`` path the engine uses in production, over the world's own seed
lineage (``base_seed + 7919*k``), so what you read is what a player would get.
The page is deterministic — same world, same seed, same bytes.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.core.engine import ASSETS, REPORTED_SLEEVES, EnsembleResult, run_ensemble
from ah.core.numericworld import NumericWorld
from ah.programme import PROGRAMME_CSS, ProgrammeReport, render_programme_section

__all__ = [
    "PLAUSIBLE",
    "AssetStats",
    "Band",
    "FactorStats",
    "SmoothingStats",
    "WorldReport",
    "asset_stats",
    "build_report",
    "factor_stats",
    "render_credibility_page",
    "smoothing_stats",
]


@dataclass(frozen=True)
class Band:
    """A declared plausible range for a decade-long annualized statistic.

    ``month_lo`` and ``dd_hi`` (register ER-9) bound the tails: the worst
    single month any path may print and the deepest peak-to-trough fall any
    path may take. The defaults are inert so an ad-hoc band without a tail
    view flags nothing it did not declare.
    """

    ret_lo: float
    ret_hi: float
    vol_lo: float
    vol_hi: float
    note: str
    month_lo: float = -100.0
    dd_hi: float = 100.0


# One allocator's priors, in annualized percent, for a TEN-YEAR holding period
# in a stressed world. Deliberately wide: the job is to catch numbers that are
# not arguable, not to enforce a house view. Tail anchors: the worst recorded
# US equity month is about -30 (September 1931) and the worst equity drawdown
# about -89 (1929-32); a WORST path may approach history's worst, but a month
# that outdoes the whole Depression is not an extreme outcome, it is ER-9.
PLAUSIBLE: dict[str, Band] = {
    "equity": Band(-8.0, 14.0, 12.0, 28.0, "public equity, stressed decade", -30.0, 90.0),
    "bonds": Band(-2.0, 9.0, 3.0, 12.0, "duration; rising rates can dominate", -12.0, 45.0),
    "hy": Band(0.0, 11.0, 6.0, 18.0, "carry NET of defaults, not gross spread", -20.0, 60.0),
    "commodities": Band(-6.0, 16.0, 12.0, 28.0, "wide by nature", -35.0, 85.0),
    "reits": Band(-8.0, 12.0, 12.0, 26.0, "levered real assets", -35.0, 80.0),
    "pe": Band(-10.0, 16.0, 15.0, 32.0, "true marks, not appraisals", -40.0, 90.0),
    "pc": Band(2.0, 11.0, 3.0, 12.0, "carry net of losses", -20.0, 55.0),
    "re": Band(-6.0, 11.0, 6.0, 18.0, "direct property, true marks", -25.0, 65.0),
}

# A decade Sharpe above this needs an explanation, whatever the asset.
MAX_PLAUSIBLE_SHARPE = 1.0


@dataclass(frozen=True)
class AssetStats:
    asset: str
    ann_p5: float
    ann_median: float
    ann_p95: float
    vol: float
    worst_drawdown: float
    worst_month: float
    flags: tuple[str, ...]


@dataclass(frozen=True)
class FactorStats:
    name: str
    start: float
    end: float
    mean: float
    lo: float
    hi: float
    flags: tuple[str, ...]


@dataclass(frozen=True)
class SmoothingStats:
    sleeve: str
    true_vol: float
    reported_vol: float
    vol_ratio: float
    reported_autocorr: float
    flags: tuple[str, ...]


@dataclass(frozen=True)
class WorldReport:
    world_id: str
    title: str
    months: int
    n_paths: int
    base_seed: int
    assets: list[AssetStats]
    factors: list[FactorStats]
    smoothing: list[SmoothingStats]
    correlations: dict[str, dict[str, float]] = field(default_factory=dict)
    # v2 chart payloads (rounded for byte-stability; empty = charts omitted)
    asset_order: tuple[str, ...] = ()
    equity_fan: dict[str, list[float]] = field(default_factory=dict)
    factor_lines: dict[str, dict[str, list[float]]] = field(default_factory=dict)

    @property
    def flag_count(self) -> int:
        return (
            sum(len(a.flags) for a in self.assets)
            + sum(len(f.flags) for f in self.factors)
            + sum(len(s.flags) for s in self.smoothing)
        )


# --------------------------------------------------------------------------- #
# statistics (over the ensemble; returns are engine PERCENT)
# --------------------------------------------------------------------------- #


def _annualized(returns_pct: np.ndarray, months: int) -> np.ndarray:
    growth = np.prod(1.0 + returns_pct / 100.0, axis=1)
    return growth ** (12.0 / months) - 1.0


def _worst_drawdown(returns_pct: np.ndarray) -> float:
    growth = np.cumprod(1.0 + returns_pct / 100.0, axis=1)
    peak = np.maximum.accumulate(growth, axis=1)
    return float(np.max(1.0 - growth / peak))


def _autocorr(x: np.ndarray) -> float:
    """Lag-1 autocorrelation, pooled across paths."""
    a = x[:, :-1].ravel()
    b = x[:, 1:].ravel()
    if a.size < 2:
        return 0.0
    sa, sb = float(np.std(a)), float(np.std(b))
    if sa <= 0 or sb <= 0:
        return 0.0
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def _quarterly_true(returns_pct: np.ndarray) -> np.ndarray:
    """Compound monthly true returns into the quarters the privates report on."""
    n, nm = returns_pct.shape
    q = nm // 3
    g = (1.0 + returns_pct[:, : q * 3] / 100.0).reshape(n, q, 3)
    return (np.prod(g, axis=2) - 1.0) * 100.0


def _quarterly_reported(reported_pct: np.ndarray) -> np.ndarray:
    """The marks themselves: private assets report at quarter ends only, so
    the monthly series is two zeros and a number. Comparing that series to a
    monthly true one measures the reporting CALENDAR, not the smoothing —
    a mistake this console made on its first run and now cannot make again."""
    nm = reported_pct.shape[1]
    return reported_pct[:, 2 : (nm // 3) * 3 : 3]


def asset_stats(ens: EnsembleResult) -> list[AssetStats]:
    """Per-asset decade statistics, with plausibility flags against PLAUSIBLE.

    Iterates the ensemble's own ``asset_order`` — the toy tuple for toy
    worlds, the generated set (no reits, OD-3) for generated ones.
    """
    out: list[AssetStats] = []
    for a in ens.asset_order:
        r = ens.returns[a]
        ann = _annualized(r, ens.months) * 100.0
        p5, med, p95 = (float(v) for v in np.percentile(ann, [5, 50, 95]))
        vol = float(np.std(r, ddof=1)) * math.sqrt(12.0)
        worst_dd = _worst_drawdown(r) * 100.0
        worst_month = float(r.min())
        flags: list[str] = []
        band = PLAUSIBLE.get(a)
        if band is not None:
            if med < band.ret_lo:
                flags.append(f"median {med:.1f}%/yr below the declared floor {band.ret_lo:.1f}%")
            if med > band.ret_hi:
                flags.append(f"median {med:.1f}%/yr above the declared ceiling {band.ret_hi:.1f}%")
            if vol < band.vol_lo:
                flags.append(f"vol {vol:.1f}%/yr below the declared floor {band.vol_lo:.1f}%")
            if vol > band.vol_hi:
                flags.append(f"vol {vol:.1f}%/yr above the declared ceiling {band.vol_hi:.1f}%")
            if worst_month < band.month_lo:
                flags.append(
                    f"worst month {worst_month:.1f}% breaches the declared "
                    f"monthly floor {band.month_lo:.1f}%"
                )
            if worst_dd > band.dd_hi:
                flags.append(
                    f"worst path drawdown {worst_dd:.1f}% beyond the declared "
                    f"ceiling {band.dd_hi:.1f}%"
                )
        if vol > 0 and med / vol > MAX_PLAUSIBLE_SHARPE:
            flags.append(f"return/vol {med / vol:.2f} - a decade Sharpe above 1.0 needs a reason")
        out.append(
            AssetStats(
                asset=a,
                ann_p5=p5,
                ann_median=med,
                ann_p95=p95,
                vol=vol,
                worst_drawdown=worst_dd,
                worst_month=worst_month,
                flags=tuple(flags),
            )
        )
    return out


def factor_stats(paths: list[Any]) -> list[FactorStats]:
    """Where the factor paths actually spend their time.

    The mean matters as much as the endpoints: a spread that starts and ends
    near 400bp but averages 1278bp spent the decade somewhere nobody looked
    (docs/engine-realism-register.md, ER-1).
    """
    out: list[FactorStats] = []
    specs = (
        ("policy rate (%)", "rate", 15.0),
        ("HY spread (bp)", "spread", 1000.0),
        ("inflation (%)", "inflation", 15.0),
    )
    for label, attr, sane_mean in specs:
        v = np.array([getattr(p, attr) for p in paths], dtype=float)
        start, end = float(v[:, 0].mean()), float(v[:, -1].mean())
        mean, lo, hi = float(v.mean()), float(v.min()), float(v.max())
        flags: list[str] = []
        if mean > sane_mean:
            flags.append(f"mean {mean:.0f} is implausibly high to sustain for a decade")
        edge = max(abs(start), abs(end), 1e-9)
        if mean > 2.0 * edge:
            flags.append(
                f"mean {mean:.0f} is more than twice its start/end ({start:.0f}/{end:.0f}) - "
                "the path spends the decade far from where it begins and ends"
            )
        out.append(FactorStats(label, start, end, mean, lo, hi, tuple(flags)))
    crisis = np.array([p.crisis for p in paths], dtype=float)
    out.append(
        FactorStats(
            "crisis months (share)",
            0.0,
            0.0,
            float(crisis.mean()),
            0.0,
            1.0,
            # NOT a flag: a benign world may legitimately declare no crisis
            # window, and flagging that taught the reader to skip the row.
            (),
        )
    )
    return out


def smoothing_stats(ens: EnsembleResult) -> list[SmoothingStats]:
    """Does the reported plane look like appraisal smoothing should?

    Two signatures, both measured in QUARTER space because that is when
    private assets actually mark: lower volatility than the truth, and
    POSITIVE autocorrelation. The second is the one that matters — a damped
    series is not the same thing as a smoothed one, and it is the trending
    that de-smoothing (``ah.data.desmooth``) exists to undo.
    """
    out: list[SmoothingStats] = []
    for s in REPORTED_SLEEVES:
        true_q = _quarterly_true(ens.returns[s])
        rep_q = _quarterly_reported(ens.reported[s])
        tv = float(np.std(true_q, ddof=1)) * math.sqrt(4.0)
        rv = float(np.std(rep_q, ddof=1)) * math.sqrt(4.0)
        ratio = rv / tv if tv > 0 else float("nan")
        ac = _autocorr(rep_q)
        flags: list[str] = []
        if not ratio < 0.95:
            flags.append(f"reported vol is {ratio:.2f}x true - the smoothing is not smoothing")
        if ac <= 0.0:
            flags.append(f"reported autocorrelation {ac:+.2f} - appraisals should trend")
        out.append(SmoothingStats(s, tv, rv, ratio, ac, tuple(flags)))
    return out


def _correlations(ens: EnsembleResult) -> dict[str, dict[str, float]]:
    order = ens.asset_order
    stacked = np.vstack([ens.returns[a].ravel() for a in order])
    c = np.corrcoef(stacked)
    return {a: {b: float(c[i, j]) for j, b in enumerate(order)} for i, a in enumerate(order)}


# factor summaries are path-shaped, and 200 paths is plenty for a mean
_MAX_FACTOR_PATHS = 200


def build_report(
    world: NumericWorld,
    *,
    base_seed: int,
    n_paths: int,
    title: str | None = None,
) -> WorldReport:
    """Everything the console shows for one world, from its own seed lineage.

    Dispatches on ``generator_id``: toy worlds through the toy engine,
    generated worlds through the su-gen-01 adapter (the Task 3 console
    criterion — a generated world walks exactly as a preset one).
    """
    n_factor_paths = min(n_paths, _MAX_FACTOR_PATHS)
    if world.engine_defaults.generator_id == "toy-v0":
        from ah.core.engine import run_path

        ens = run_ensemble(world, n_paths, base_seed=base_seed)
        paths = [run_path(world, base_seed + 7919 * k) for k in range(n_factor_paths)]
    else:
        from ah.port.adapter import run_gen_ensemble, run_gen_path

        ens = run_gen_ensemble(world, n_paths, base_seed=base_seed)
        paths = [run_gen_path(world, base_seed + 7919 * k) for k in range(n_factor_paths)]

    growth = np.cumprod(1.0 + ens.returns["equity"] / 100.0, axis=1)
    fan_qs = np.percentile(growth, [5, 25, 50, 75, 95], axis=0)
    equity_fan = {
        f"p{p}": [round(float(v), 4) for v in row]
        for p, row in zip((5, 25, 50, 75, 95), fan_qs, strict=True)
    }
    factor_lines: dict[str, dict[str, list[float]]] = {}
    for label, attr in (
        ("policy rate (%)", "rate"),
        ("HY spread (bp)", "spread"),
        ("inflation (%)", "inflation"),
    ):
        v = np.array([getattr(p, attr) for p in paths], dtype=float)
        p10, p50, p90 = np.percentile(v, [10, 50, 90], axis=0)
        factor_lines[label] = {
            "p10": [round(float(x), 3) for x in p10],
            "p50": [round(float(x), 3) for x in p50],
            "p90": [round(float(x), 3) for x in p90],
        }

    return WorldReport(
        world_id=world.world_id,
        title=title or world.world_id,
        months=ens.months,
        n_paths=ens.n_paths,
        base_seed=base_seed,
        assets=asset_stats(ens),
        factors=factor_stats(paths),
        smoothing=smoothing_stats(ens),
        correlations=_correlations(ens),
        asset_order=ens.asset_order,
        equity_fan=equity_fan,
        factor_lines=factor_lines,
    )


# --------------------------------------------------------------------------- #
# the page (self-contained, no external assets, byte-stable)
# --------------------------------------------------------------------------- #

# A committed single dark theme on the console's own surface. The three series
# hues were run through the dataviz validator on #0d2226 (all six checks pass):
# jade #2fa183 carries "true", brass #b9842b carries "reported" - the app's own
# color language - and blue #3987e5 is the neutral accent for bands and paths.
# #d03b3b is the reserved status color for flags, never a series.
_CSS = """
:root{--ink:#0d2226;--pane:#0f282b;--line:#20464b;--ice:#d7e6e3;--dim:#7c9b99;
--jade:#2fa183;--brass:#b9842b;--blue:#3987e5;--clay:#d03b3b;
--grid:#1b3d41;--muted:#6f8d8b}
*{box-sizing:border-box}
body{margin:0;padding:24px 28px;background:var(--ink);color:var(--ice);
font:14px/1.5 -apple-system,Segoe UI,sans-serif}
h1{font-size:24px;margin:0 0 4px}
h3{font-size:13px;margin:22px 0 8px;color:var(--dim);text-transform:uppercase;
letter-spacing:.12em;font-weight:600}
.lede{color:var(--dim);max-width:78ch;margin:0 0 16px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:5px 10px;border-bottom:1px solid #18383c}
th{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.1em;
font-weight:600}
th:first-child,td:first-child{text-align:left}
tr.flagged td{background:#33201c}
.flag{color:var(--clay);font-size:12.5px;margin:2px 0 0}
.tag{display:inline-block;border:1px solid var(--line);border-radius:99px;
padding:2px 10px;font-size:11px;color:var(--dim);margin-right:6px}
.tag.bad{border-color:var(--clay);color:var(--clay)}
.tag.good{border-color:var(--jade);color:var(--jade)}
.note{color:var(--dim);font-size:12.5px}
.corr td{font-size:12px;padding:3px 7px}
.corr td.c-hot{background:#153a5e;color:var(--ice)}
.corr td.c-warm{background:#11304d66}
.corr td.c-cool{background:#4a1e1e}
footer{color:var(--dim);font-size:12px;margin-top:32px;border-top:1px solid
var(--line);padding-top:12px}
/* -- v2: scenario tabs (script-free: radio + sibling selectors) ------------ */
.tabs>input{position:absolute;opacity:0;pointer-events:none}
.tabbar{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 0}
label.tab{padding:8px 16px;border:1px solid var(--line);cursor:pointer;
color:var(--dim);border-radius:10px 10px 0 0;background:transparent;
font-size:13.5px}
label.tab .tag{margin-left:8px;margin-right:0}
.panel{display:none;border:1px solid var(--line);border-radius:0 12px 12px 12px;
background:var(--pane);padding:20px 22px;overflow-x:auto}
/* -- charts ---------------------------------------------------------------- */
.chartrow{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-start}
.chart{margin:0 0 6px}
.chart figcaption{color:var(--dim);font-size:12px;margin:4px 0 0}
svg text{font:11px -apple-system,Segoe UI,sans-serif;fill:var(--muted)}
svg .axis{stroke:#2a4d52;stroke-width:1}
svg .grid{stroke:var(--grid);stroke-width:1}
.tiles{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0 4px}
.tile{border:1px solid var(--line);border-radius:10px;padding:10px 16px;
min-width:130px}
.tile .v{font-size:22px;font-variant-numeric:tabular-nums}
.tile .k{color:var(--dim);font-size:11px;text-transform:uppercase;
letter-spacing:.1em}
.tile.bad .v{color:var(--clay)}
details{margin:6px 0 14px}
details summary{cursor:pointer;color:var(--dim);font-size:12.5px}
.legend{color:var(--dim);font-size:12px;margin:2px 0 8px}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:3px;
margin:0 4px 0 12px;vertical-align:-1px}
"""


def _e(s: object) -> str:
    return html.escape(str(s))


def _asset_table(rep: WorldReport) -> str:
    rows = []
    for a in rep.assets:
        band = PLAUSIBLE.get(a.asset)
        cls = ' class="flagged"' if a.flags else ""
        flags = "".join(f'<p class="flag">{_e(f)}</p>' for f in a.flags)
        ret_band = f"{band.ret_lo:+.0f}..{band.ret_hi:+.0f}" if band else ""
        vol_band = f"{band.vol_lo:.0f}..{band.vol_hi:.0f}" if band else ""
        tail_band = f"mo {band.month_lo:+.0f} / dd {band.dd_hi:.0f}" if band else ""
        rows.append(
            f"<tr{cls}><td>{_e(a.asset)}{flags}</td>"
            f"<td>{a.ann_median:+.1f}</td><td>{a.ann_p5:+.1f}</td><td>{a.ann_p95:+.1f}</td>"
            f"<td>{a.vol:.1f}</td><td>{a.worst_drawdown:.0f}</td>"
            f"<td>{a.worst_month:+.1f}</td>"
            f'<td class="note">{_e(ret_band)}</td>'
            f'<td class="note">{_e(vol_band)}</td>'
            f'<td class="note">{_e(tail_band)}</td>'
            f'<td class="note">{_e(band.note) if band else ""}</td></tr>'
        )
    return (
        "<table><thead><tr><th>asset</th><th>median %/yr</th><th>p5</th><th>p95</th>"
        "<th>vol %/yr</th><th>worst DD %</th><th>worst month %</th><th>declared return</th>"
        "<th>declared vol</th><th>declared tail</th><th>prior</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _factor_table(rep: WorldReport) -> str:
    rows = []
    for f in rep.factors:
        cls = ' class="flagged"' if f.flags else ""
        flags = "".join(f'<p class="flag">{_e(x)}</p>' for x in f.flags)
        rows.append(
            f"<tr{cls}><td>{_e(f.name)}{flags}</td><td>{f.start:.2f}</td>"
            f"<td>{f.end:.2f}</td><td>{f.mean:.2f}</td><td>{f.lo:.2f}</td>"
            f"<td>{f.hi:.2f}</td></tr>"
        )
    return (
        "<table><thead><tr><th>factor</th><th>start</th><th>end</th><th>mean</th>"
        "<th>min</th><th>max</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _smoothing_table(rep: WorldReport) -> str:
    rows = []
    for s in rep.smoothing:
        cls = ' class="flagged"' if s.flags else ""
        flags = "".join(f'<p class="flag">{_e(x)}</p>' for x in s.flags)
        rows.append(
            f"<tr{cls}><td>{_e(s.sleeve)}{flags}</td><td>{s.true_vol:.1f}</td>"
            f"<td>{s.reported_vol:.1f}</td><td>{s.vol_ratio:.2f}</td>"
            f"<td>{s.reported_autocorr:+.2f}</td></tr>"
        )
    return (
        "<table><thead><tr><th>private asset</th><th>true vol %/yr</th>"
        "<th>reported vol %/yr</th><th>ratio</th><th>reported lag-1 autocorr (quarters)</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _corr_table(rep: WorldReport) -> str:
    order = rep.asset_order or tuple(ASSETS)
    head = "".join(f"<th>{_e(a)}</th>" for a in order)
    rows = []
    for a in order:
        cells = []
        for b in order:
            v = rep.correlations[a][b]
            if a == b:
                cls = ""
            elif v >= 0.7:
                cls = ' class="c-hot"'
            elif v >= 0.4:
                cls = ' class="c-warm"'
            elif v <= -0.4:
                cls = ' class="c-cool"'
            else:
                cls = ""
            cells.append(f"<td{cls}>{v:+.2f}</td>")
        rows.append(f"<tr><td>{_e(a)}</td>{''.join(cells)}</tr>")
    return (
        f'<table class="corr"><thead><tr><th></th>{head}</tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


# --------------------------------------------------------------------------- #
# v2 charts: hand-authored SVG, deterministic, byte-stable, script-free.
# Hover uses native SVG <title> tooltips (the no-script invariant is a test).
# --------------------------------------------------------------------------- #


def _sx(v: float) -> str:
    return f"{v:.1f}"


def _fan_chart(rep: WorldReport) -> str:
    """The equity decade: growth-of-1 percentile fan (p5/25/50/75/95)."""
    fan = rep.equity_fan
    if not fan:
        return ""
    w, h, pl, pb = 560.0, 180.0, 44.0, 18.0
    months = len(fan["p50"])
    lo = min(min(fan["p5"]), 1.0)
    hi = max(max(fan["p95"]), 1.0)
    span = (hi - lo) or 1.0

    def pt(i: int, v: float) -> str:
        x = pl + (w - pl - 8) * (i / max(months - 1, 1))
        y = (h - pb) - (h - pb - 10) * ((v - lo) / span)
        return f"{_sx(x)},{_sx(y)}"

    def band(upper: list[float], lower: list[float], opacity: str) -> str:
        pts = [pt(i, v) for i, v in enumerate(upper)]
        pts += [pt(i, v) for i, v in reversed(list(enumerate(lower)))]
        return f'<polygon points="{" ".join(pts)}" fill="var(--blue)" opacity="{opacity}"/>'

    median = " ".join(pt(i, v) for i, v in enumerate(fan["p50"]))
    gridlines = []
    for gv in (1.0, (lo + hi) / 2.0, hi):
        gy = (h - pb) - (h - pb - 10) * ((gv - lo) / span)
        gridlines.append(
            f'<line class="grid" x1="{_sx(pl)}" y1="{_sx(gy)}" x2="{_sx(w - 8)}" y2="{_sx(gy)}"/>'
            f'<text x="2" y="{_sx(gy + 4)}">{gv:.1f}x</text>'
        )
    final = fan["p50"][-1]
    tip = (
        f"equity, growth of 1 over {months} months - median ends {final:.2f}x, "
        f"p5 {fan['p5'][-1]:.2f}x, p95 {fan['p95'][-1]:.2f}x"
    )
    return (
        f'<figure class="chart"><svg class="fan" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}" role="img"><title>{_e(tip)}</title>'
        + "".join(gridlines)
        + band(fan["p95"], fan["p5"], "0.18")
        + band(fan["p75"], fan["p25"], "0.28")
        + f'<polyline points="{median}" fill="none" stroke="var(--blue)" stroke-width="2"/>'
        f'<line class="axis" x1="{_sx(pl)}" y1="{_sx(h - pb)}" x2="{_sx(w - 8)}" '
        f'y2="{_sx(h - pb)}"/></svg>'
        "<figcaption>equity, growth of 1 - median line, p25-p75 and p5-p95 bands"
        "</figcaption></figure>"
    )


def _interval_chart(rep: WorldReport) -> str:
    """Per-asset annualized outcome: p5..p95 interval + median dot, drawn over
    the declared plausible band. The chart form of the big table."""
    rows = rep.assets
    if not rows:
        return ""
    rh, pl, w = 27.0, 96.0, 560.0
    h = rh * len(rows) + 26.0
    lo = min(min(a.ann_p5 for a in rows), min(b.ret_lo for b in PLAUSIBLE.values())) - 2.0
    hi = max(max(a.ann_p95 for a in rows), max(b.ret_hi for b in PLAUSIBLE.values())) + 2.0
    span = hi - lo

    def x(v: float) -> float:
        return pl + (w - pl - 10) * ((v - lo) / span)

    parts = []
    zx = x(0.0)
    parts.append(
        f'<line class="grid" x1="{_sx(zx)}" y1="6" x2="{_sx(zx)}" y2="{_sx(h - 18)}"/>'
        f'<text x="{_sx(zx - 8)}" y="{_sx(h - 5)}">0%</text>'
    )
    for i, a in enumerate(rows):
        cy = 16.0 + rh * i
        band = PLAUSIBLE.get(a.asset)
        color = "var(--clay)" if a.flags else "var(--jade)"
        tip = (
            f"{a.asset}: median {a.ann_median:+.1f}%/yr, p5 {a.ann_p5:+.1f}, "
            f"p95 {a.ann_p95:+.1f}; declared {band.ret_lo:+.0f}..{band.ret_hi:+.0f}"
            if band
            else a.asset
        )
        parts.append(f"<g><title>{_e(tip)}</title>")
        if band:
            parts.append(
                f'<rect x="{_sx(x(band.ret_lo))}" y="{_sx(cy - 7)}" '
                f'width="{_sx(x(band.ret_hi) - x(band.ret_lo))}" height="14" '
                'fill="var(--grid)" rx="3"/>'
            )
        parts.append(
            f'<line x1="{_sx(x(a.ann_p5))}" y1="{_sx(cy)}" x2="{_sx(x(a.ann_p95))}" '
            f'y2="{_sx(cy)}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>'
            f'<circle cx="{_sx(x(a.ann_median))}" cy="{_sx(cy)}" r="4.5" fill="{color}" '
            'stroke="var(--pane)" stroke-width="2"/>'
            f'<text x="2" y="{_sx(cy + 4)}">{_e(a.asset)}</text>'
            f'<text x="{_sx(x(a.ann_p95) + 8)}" y="{_sx(cy + 4)}">{a.ann_median:+.1f}</text>'
            "</g>"
        )
    return (
        f'<figure class="chart"><svg class="intervals" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}" role="img">' + "".join(parts) + "</svg>"
        "<figcaption>annualized %/yr - p5..p95 interval, median dot, declared "
        "band behind; flagged assets in red</figcaption></figure>"
    )


def _factor_small_multiples(rep: WorldReport) -> str:
    """Median path with p10-p90 band, one small panel per factor channel."""
    if not rep.factor_lines:
        return ""
    panels = []
    for label, lines in rep.factor_lines.items():
        w, h, pl = 250.0, 110.0, 8.0
        months = len(lines["p50"])
        lo, hi = min(lines["p10"]), max(lines["p90"])
        span = (hi - lo) or 1.0

        def pt(i: int, v: float, w=w, h=h, pl=pl, lo=lo, span=span, months=months) -> str:
            x = pl + (w - pl - 6) * (i / max(months - 1, 1))
            y = (h - 16) - (h - 30) * ((v - lo) / span)
            return f"{_sx(x)},{_sx(y)}"

        band_pts = [pt(i, v) for i, v in enumerate(lines["p90"])]
        band_pts += [pt(i, v) for i, v in reversed(list(enumerate(lines["p10"])))]
        median = " ".join(pt(i, v) for i, v in enumerate(lines["p50"]))
        tip = f"{label}: median path, p10-p90 band; range {lo:.2f}..{hi:.2f}"
        panels.append(
            f'<figure class="chart"><svg class="factorline" width="{w:.0f}" '
            f'height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}" role="img">'
            f"<title>{_e(tip)}</title>"
            f'<polygon points="{" ".join(band_pts)}" fill="var(--blue)" opacity="0.16"/>'
            f'<polyline points="{median}" fill="none" stroke="var(--blue)" '
            'stroke-width="2"/>'
            f'<text x="{_sx(pl)}" y="11">{_e(label)}</text>'
            f'<text x="{_sx(pl)}" y="{_sx(h - 4)}">{lo:.1f}..{hi:.1f}</text></svg></figure>'
        )
    return '<div class="chartrow">' + "".join(panels) + "</div>"


def _smoothing_chart(rep: WorldReport) -> str:
    """True vs reported vol per private asset: paired bars, jade vs brass."""
    rows = rep.smoothing
    if not rows:
        return ""
    rh, pl, w = 40.0, 40.0, 400.0
    h = rh * len(rows) + 14.0
    hi = max(max(s.true_vol for s in rows), 1e-9) * 1.08

    def bw(v: float) -> float:
        return max((w - pl - 46) * (v / hi), 1.0)

    parts = []
    for i, s in enumerate(rows):
        cy = 8.0 + rh * i
        tip = (
            f"{s.sleeve}: true vol {s.true_vol:.1f}%/yr, reported {s.reported_vol:.1f} "
            f"({s.vol_ratio:.2f}x), reported lag-1 autocorr {s.reported_autocorr:+.2f}"
        )
        parts.append(
            f"<g><title>{_e(tip)}</title>"
            f'<text x="2" y="{_sx(cy + 12)}">{_e(s.sleeve)}</text>'
            f'<rect x="{_sx(pl)}" y="{_sx(cy)}" width="{_sx(bw(s.true_vol))}" height="9" '
            'fill="var(--jade)" rx="3"/>'
            f'<rect x="{_sx(pl)}" y="{_sx(cy + 12)}" width="{_sx(bw(s.reported_vol))}" '
            'height="9" fill="var(--brass)" rx="3"/>'
            f'<text x="{_sx(pl + bw(s.true_vol) + 6)}" y="{_sx(cy + 9)}">'
            f"{s.true_vol:.1f}</text>"
            f'<text x="{_sx(pl + bw(s.reported_vol) + 6)}" y="{_sx(cy + 21)}">'
            f"{s.reported_vol:.1f}</text></g>"
        )
    legend = (
        '<p class="legend">vol %/yr, quarter space'
        '<span class="sw" style="background:var(--jade)"></span>true'
        '<span class="sw" style="background:var(--brass)"></span>as reported</p>'
    )
    return (
        f'<figure class="chart"><svg class="pairs" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}" role="img">' + "".join(parts) + "</svg>"
        f"{legend}</figure>"
    )


def _stat_tiles(rep: WorldReport) -> str:
    eq = next((a for a in rep.assets if a.asset == "equity"), None)
    infl = next((f for f in rep.factors if f.name.startswith("inflation")), None)
    tiles = []
    if eq:
        tiles.append(("equity median", f"{eq.ann_median:+.1f}%/yr", ""))
        tiles.append(("equity worst DD", f"{eq.worst_drawdown:.0f}%", ""))
    if infl:
        tiles.append(("inflation mean", f"{infl.mean:.1f}%", ""))
    tiles.append(("flags", str(rep.flag_count), " bad" if rep.flag_count else ""))
    return (
        '<div class="tiles">'
        + "".join(
            f'<div class="tile{cls}"><div class="v">{_e(v)}</div><div class="k">{_e(k)}</div></div>'
            for k, v, cls in tiles
        )
        + "</div>"
    )


def _details(summary: str, table_html: str) -> str:
    return f"<details><summary>{_e(summary)}</summary>{table_html}</details>"


def _panel(rep: WorldReport, prog: ProgrammeReport | None) -> str:
    rtag = (
        f'<span class="tag bad">{rep.flag_count} flags</span>'
        if rep.flag_count
        else '<span class="tag good">clean</span>'
    )
    prog_html = (
        render_programme_section([prog])
        if prog is not None
        else '<p class="note">programme walk pending the generated-world play layer (su-gen-03)</p>'
    )
    return (
        f'<p>{rtag}<span class="tag">{rep.months} months</span>'
        f'<span class="tag">{rep.n_paths} paths</span>'
        f'<span class="tag">base seed {rep.base_seed}</span>'
        f'<span class="tag">{_e(rep.world_id)}</span></p>'
        + _stat_tiles(rep)
        + "<h3>The decade, and where each asset lands</h3>"
        + '<div class="chartrow">'
        + _fan_chart(rep)
        + _interval_chart(rep)
        + "</div>"
        + _details("per-asset table (worst DD, worst month, declared bands)", _asset_table(rep))
        + "<h3>Factor paths - where they spend their time</h3>"
        + _factor_small_multiples(rep)
        + _details("factor table", _factor_table(rep))
        + "<h3>Reported vs true (appraisal smoothing, in quarter space)</h3>"
        + _smoothing_chart(rep)
        + _details("smoothing table", _smoothing_table(rep))
        + "<h3>Pooled monthly correlations</h3>"
        + _corr_table(rep)
        + "<h3>The private programme</h3>"
        + prog_html
    )


def render_credibility_page(
    reports: list[WorldReport], programme: list[ProgrammeReport | None] | None = None
) -> str:
    """A self-contained, script-free page: one TAB per world (v2), flags in
    the open, every chart backed by its table in a collapsible view."""
    total = sum(r.flag_count for r in reports)
    tag = (
        f'<span class="tag bad">{total} flags to look at</span>'
        if total
        else '<span class="tag good">nothing flagged</span>'
    )
    progs: list[ProgrammeReport | None] = list(programme or [])
    progs += [None] * (len(reports) - len(progs))

    inputs, labels, panels, tabcss = [], [], [], []
    for i, r in enumerate(reports):
        checked = " checked" if i == 0 else ""
        badge = (
            f'<span class="tag bad">{r.flag_count}</span>'
            if r.flag_count
            else '<span class="tag good">ok</span>'
        )
        inputs.append(f'<input type="radio" name="world-tab" id="w{i}"{checked}>')
        labels.append(f'<label class="tab" for="w{i}">{_e(r.title)}{badge}</label>')
        panels.append(f'<section class="panel" id="p{i}">{_panel(r, progs[i])}</section>')
        tabcss.append(
            f"#w{i}:checked~.tabbar label[for=w{i}]{{color:var(--ice);"
            f"background:var(--pane);border-bottom-color:var(--pane)}}"
            f"#w{i}:checked~#p{i}{{display:block}}"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>Terrarium - credibility console</title>"
        f"<style>{_CSS}{PROGRAMME_CSS}{''.join(tabcss)}</style></head><body>"
        "<h1>Credibility console</h1>"
        f'<p class="lede">{tag}<br>Every figure is regenerated from the world\'s own '
        "seed lineage, so it is what a player would get. The declared columns are "
        "priors written down for argument, not truth - a flagged row is an "
        "invitation to look, and nothing here can fail a build. Judgements that "
        "survive review belong in <code>docs/engine-realism-register.md</code>.</p>"
        '<div class="tabs">'
        + "".join(inputs)
        + '<div class="tabbar">'
        + "".join(labels)
        + "</div>"
        + "".join(panels)
        + "</div>"
        "<footer>Admin surface. Not sealed, not scored, never shown to a player."
        "</footer></body></html>"
    )
