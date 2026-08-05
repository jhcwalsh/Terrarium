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
    """A declared plausible range for a decade-long annualized statistic."""

    ret_lo: float
    ret_hi: float
    vol_lo: float
    vol_hi: float
    note: str


# One allocator's priors, in annualized percent, for a TEN-YEAR holding period
# in a stressed world. Deliberately wide: the job is to catch numbers that are
# not arguable, not to enforce a house view.
PLAUSIBLE: dict[str, Band] = {
    "equity": Band(-8.0, 14.0, 12.0, 28.0, "public equity, stressed decade"),
    "bonds": Band(-2.0, 9.0, 3.0, 12.0, "duration; rising rates can dominate"),
    "hy": Band(0.0, 11.0, 6.0, 18.0, "carry NET of defaults, not gross spread"),
    "commodities": Band(-6.0, 16.0, 12.0, 28.0, "wide by nature"),
    "reits": Band(-8.0, 12.0, 12.0, 26.0, "levered real assets"),
    "pe": Band(-10.0, 16.0, 15.0, 32.0, "true marks, not appraisals"),
    "pc": Band(2.0, 11.0, 3.0, 12.0, "carry net of losses"),
    "re": Band(-6.0, 11.0, 6.0, 18.0, "direct property, true marks"),
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
    """Per-asset decade statistics, with plausibility flags against PLAUSIBLE."""
    out: list[AssetStats] = []
    for a in ASSETS:
        r = ens.returns[a]
        ann = _annualized(r, ens.months) * 100.0
        p5, med, p95 = (float(v) for v in np.percentile(ann, [5, 50, 95]))
        vol = float(np.std(r, ddof=1)) * math.sqrt(12.0)
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
        if vol > 0 and med / vol > MAX_PLAUSIBLE_SHARPE:
            flags.append(f"return/vol {med / vol:.2f} - a decade Sharpe above 1.0 needs a reason")
        out.append(
            AssetStats(
                asset=a,
                ann_p5=p5,
                ann_median=med,
                ann_p95=p95,
                vol=vol,
                worst_drawdown=_worst_drawdown(r) * 100.0,
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
    stacked = np.vstack([ens.returns[a].ravel() for a in ASSETS])
    c = np.corrcoef(stacked)
    return {a: {b: float(c[i, j]) for j, b in enumerate(ASSETS)} for i, a in enumerate(ASSETS)}


# factor summaries are path-shaped, and 200 paths is plenty for a mean
_MAX_FACTOR_PATHS = 200


def build_report(
    world: NumericWorld,
    *,
    base_seed: int,
    n_paths: int,
    title: str | None = None,
) -> WorldReport:
    """Everything the console shows for one world, from its own seed lineage."""
    from ah.core.engine import run_path

    ens = run_ensemble(world, n_paths, base_seed=base_seed)
    paths = [run_path(world, base_seed + 7919 * k) for k in range(min(n_paths, _MAX_FACTOR_PATHS))]
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
    )


# --------------------------------------------------------------------------- #
# the page (self-contained, no external assets, byte-stable)
# --------------------------------------------------------------------------- #

_CSS = """
:root{--ink:#0d2226;--pane:#0f282b;--line:#20464b;--ice:#d7e6e3;--dim:#7c9b99;
--jade:#4fc3a1;--clay:#d2624f;--brass:#d6a24a}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--ink);color:var(--ice);
font:14px/1.5 -apple-system,Segoe UI,sans-serif}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:30px 0 8px}
h3{font-size:15px;margin:20px 0 6px;color:var(--dim);text-transform:uppercase;
letter-spacing:.12em;font-weight:600}
.lede{color:var(--dim);max-width:74ch;margin:0 0 20px}
.world{border:1px solid var(--line);border-radius:12px;background:var(--pane);
padding:20px 22px;margin:0 0 22px;overflow-x:auto}
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
.corr td.hi{color:var(--brass)}
footer{color:var(--dim);font-size:12px;margin-top:32px;border-top:1px solid
var(--line);padding-top:12px}
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
        rows.append(
            f"<tr{cls}><td>{_e(a.asset)}{flags}</td>"
            f"<td>{a.ann_median:+.1f}</td><td>{a.ann_p5:+.1f}</td><td>{a.ann_p95:+.1f}</td>"
            f"<td>{a.vol:.1f}</td><td>{a.worst_drawdown:.0f}</td>"
            f'<td class="note">{_e(ret_band)}</td>'
            f'<td class="note">{_e(vol_band)}</td>'
            f'<td class="note">{_e(band.note) if band else ""}</td></tr>'
        )
    return (
        "<table><thead><tr><th>asset</th><th>median %/yr</th><th>p5</th><th>p95</th>"
        "<th>vol %/yr</th><th>worst DD %</th><th>declared return</th>"
        "<th>declared vol</th><th>prior</th></tr></thead><tbody>"
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
    head = "".join(f"<th>{_e(a)}</th>" for a in ASSETS)
    rows = []
    for a in ASSETS:
        cells = []
        for b in ASSETS:
            v = rep.correlations[a][b]
            cls = ' class="hi"' if a != b and abs(v) >= 0.7 else ""
            cells.append(f"<td{cls}>{v:+.2f}</td>")
        rows.append(f"<tr><td>{_e(a)}</td>{''.join(cells)}</tr>")
    return (
        f'<table class="corr"><thead><tr><th></th>{head}</tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def render_credibility_page(
    reports: list[WorldReport], programme: list[ProgrammeReport] | None = None
) -> str:
    """A self-contained HTML page: one section per world, flags in the open."""
    total = sum(r.flag_count for r in reports)
    tag = (
        f'<span class="tag bad">{total} flags to look at</span>'
        if total
        else '<span class="tag good">nothing flagged</span>'
    )
    blocks = []
    for r in reports:
        rtag = (
            f'<span class="tag bad">{r.flag_count} flags</span>'
            if r.flag_count
            else '<span class="tag good">clean</span>'
        )
        blocks.append(
            f'<section class="world"><h2>{_e(r.title)}</h2>'
            f'<p>{rtag}<span class="tag">{r.months} months</span>'
            f'<span class="tag">{r.n_paths} paths</span>'
            f'<span class="tag">base seed {r.base_seed}</span>'
            f'<span class="tag">{_e(r.world_id)}</span></p>'
            f"<h3>Per-asset, annualized over the horizon</h3>{_asset_table(r)}"
            f"<h3>Factor paths - where they spend their time</h3>{_factor_table(r)}"
            f"<h3>Reported vs true (appraisal smoothing, in quarter space)</h3>{_smoothing_table(r)}"
            f"<h3>Pooled monthly correlations</h3>{_corr_table(r)}"
            "</section>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>Terrarium - credibility console</title>"
        f"<style>{_CSS}{PROGRAMME_CSS}</style></head><body>"
        "<h1>Credibility console</h1>"
        f'<p class="lede">{tag}<br>Every figure is regenerated from the world\'s own '
        "seed lineage, so it is what a player would get. The declared columns are "
        "priors written down for argument, not truth - a flagged row is an "
        "invitation to look, and nothing here can fail a build. Judgements that "
        "survive review belong in <code>docs/engine-realism-register.md</code>.</p>"
        + "".join(blocks)
        + render_programme_section(programme or [])
        + "<footer>Admin surface. Not sealed, not scored, never shown to a player."
        "</footer></body></html>"
    )
