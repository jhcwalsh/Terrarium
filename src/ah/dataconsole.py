"""The generator-input data console: read-only inspection of the vintage store.

**Contract.** This surface has ZERO write call sites — no vintage creation, no
observation writes, no QC recording, no pointer advancement (a guard test
scans the source). It renders what the Step-1 data layer has already recorded:
raw registered series (coverage, gaps, freshness vs SLA, proxy-splice
provenance, QC results) and the derived factor panel the Step-2 generator
trains on, recomputed mechanically through the sealed ``ah.data.derive`` /
``ah.data.desmooth`` / ``ah.factors`` surfaces. Third sibling of the QA
inspection console (8799) and the scenario build console (8798).

Run it with::

    uv run uvicorn ah.dataconsole:app --port 8796

Leakage posture: a display surface reading the catalog directly, exactly like
``ah data episode``. Train/validation/holdout windows are drawn as labeled
shading; the holdout is marked SPENT (WP5.6).
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement, load_requirements


def _manifest_table(r: Requirement) -> str:
    rows = [
        ("source", r.source),
        ("code", r.code or "—"),
        ("frequency", r.frequency),
        ("units", r.units),
        ("min_start", r.min_start or "—"),
        ("sla_days", r.sla_days),
        ("license", r.license_tier),
        ("priority", r.priority),
        ("intake", r.intake),
        ("level", "enforce" if r.enforce else "warn"),
        ("notes", r.notes or "—"),
    ]
    body = "".join(
        f'<tr><th class="l">{_e(k)}</th><td class="l">{_e(v)}</td></tr>' for k, v in rows
    )
    return f"<table>{body}</table>"


_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = _REPO_ROOT / "data"
WATERMARK = "DATA INSPECTION — read-only over the vintage store — simulated/licensed data"

#: Display grouping of registered series and declared factors into asset-class
#: pages. Reconciled against factors.yaml (active_blocks: global, us, fx,
#: valuation) on 2026-08-07 — factors.yaml is the truth for factor names; this
#: mapping invents no data. `uk` block factors are inert (not in active_blocks)
#: and are shown only on /factors.
CLASSES: dict[str, dict[str, list[str]]] = {
    "equities": {
        "raw": [
            "french.mkt_rf",
            "french.smb",
            "french.hml",
            "french.mom",
            "french.rf",
            "shiller.price",
            "shiller.dividend",
        ],
        "factors": ["equity_mkt", "smb", "hml", "mom", "equity_vol", "cape_v"],
    },
    "rates-bonds": {
        "raw": ["fred.DGS10", "fred.DGS2", "fred.GS10", "fred.FEDFUNDS", "fred.TB3MS"],
        "factors": ["policy_rate", "ust_2y", "ust_10y", "hqm_curve", "funding_spread"],
    },
    "credit": {
        "raw": ["fred.BAA", "fred.AAA", "fred.HY_OAS"],
        "factors": ["ig_spread", "hy_spread"],
    },
    "inflation-macro": {
        "raw": [
            "fred.CPI",
            "fred.CPI_CORE",
            "fred.UNRATE",
            "fred.INDPRO",
            "fred.USREC",
            "fred.VIX",
            "fred.GDPC1",
        ],
        "factors": ["cpi"],
    },
    "fx": {"raw": ["fred.DTWEXBGS", "fred.DTWEXM"], "factors": ["fx_usd"]},
    "privates": {
        "raw": [
            "albourne.pm_buyout_ret_q",
            "albourne.pm_growth_ret_q",
            "albourne.pm_vc_ret_q",
            "albourne.pm_dl_ret_q",
            "albourne.pm_mezz_ret_q",
            "albourne.pm_re_va_ret_q",
        ],
        "factors": [],
    },
}

# --------------------------------------------------------------------------- #
# pure analytics
# --------------------------------------------------------------------------- #


def _col(frame: pd.DataFrame, name: str) -> pd.Series:
    """A typed column accessor: the pandas stubs give ``frame[name]`` a union
    type this module's full-strictness pyright environment rejects."""
    return cast("pd.Series", frame[name])


def gap_ranges(dates: pd.Series) -> list[tuple[str, str]]:
    """Missing calendar months between the first and last observation, as
    inclusive (YYYY-MM, YYYY-MM) ranges. Empty/singleton input -> no gaps."""
    if len(dates) < 2:
        return []
    observed = pd.PeriodIndex(pd.DatetimeIndex(dates), freq="M").unique()
    full = pd.period_range(observed.min(), observed.max(), freq="M")
    missing = full.difference(observed)
    if missing.empty:
        return []
    ranges: list[tuple[str, str]] = []
    start = prev = missing[0]
    for p in missing[1:]:
        if (p - prev).n == 1:
            prev = p
            continue
        ranges.append((str(start), str(prev)))
        start = prev = p
    ranges.append((str(start), str(prev)))
    return ranges


def coverage_pct(dates: pd.Series) -> float:
    """Observed months / calendar months spanned. 1.0 for gap-free; 0.0 empty."""
    if len(dates) == 0:
        return 0.0
    observed = pd.PeriodIndex(pd.DatetimeIndex(dates), freq="M").unique()
    span = len(pd.period_range(observed.min(), observed.max(), freq="M"))
    return len(observed) / span if span else 0.0


def staleness_days(last_date: str, as_of: str) -> int:
    """Whole days between the last observation and the as-of date."""
    return int((pd.Timestamp(as_of) - pd.Timestamp(last_date)).days)


def proxy_pct(frame: pd.DataFrame) -> float:
    """Share of observations flagged proxy-spliced; no column means all-actual."""
    if "is_proxy" not in frame.columns or len(frame) == 0:
        return 0.0
    return float(_col(frame, "is_proxy").astype(bool).mean())


def moments(values: np.ndarray) -> dict[str, float]:
    """Mean, vol (ddof=1), skew, excess kurtosis — plain numpy, no scipy."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return {
            "mean": float("nan"),
            "vol": float("nan"),
            "skew": float("nan"),
            "excess_kurtosis": float("nan"),
        }
    mu = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    if sd == 0.0:
        return {"mean": mu, "vol": 0.0, "skew": 0.0, "excess_kurtosis": 0.0}
    z = (x - mu) / sd
    return {
        "mean": mu,
        "vol": sd,
        "skew": float(np.mean(z**3)),
        "excess_kurtosis": float(np.mean(z**4) - 3.0),
    }


# --------------------------------------------------------------------------- #
# chrome (same technique as ah/console.py; not imported — each console's
# guarantee stands alone)
# --------------------------------------------------------------------------- #

_CSS = """
:root { --ink:#151a1f; --mut:#5c6874; --line:#e2e6ea; --bg:#f7f8fa; --card:#fff;
        --ok:#1f6b3a; --bad:#a3282f; --warn:#8a6d1f; }
* { box-sizing:border-box; }
body { margin:0; font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;
       color:var(--ink); background:var(--bg); }
.wm { background:#1f4030; color:#fff; font-size:11px; letter-spacing:.06em;
      padding:5px 14px; text-transform:uppercase; position:sticky; top:0; z-index:9; }
nav { background:#fff; border-bottom:1px solid var(--line); padding:8px 14px; }
nav a { margin-right:14px; color:#1f4e79; text-decoration:none; font-weight:600; }
main { padding:14px; max-width:1500px; }
h1 { font-size:19px; margin:10px 0 4px; }
h2 { font-size:15px; margin:20px 0 6px; border-bottom:1px solid var(--line); padding-bottom:3px; }
table { border-collapse:collapse; width:100%; background:var(--card); margin:6px 0 14px; font-size:12px; }
th,td { border:1px solid var(--line); padding:4px 7px; text-align:right; }
th { background:#eef1f4; text-align:left; font-weight:600; }
td.l,th.l { text-align:left; }
tr:hover td { background:#fbfcfd; }
.ok { color:var(--ok); font-weight:600; }
.bad { color:var(--bad); font-weight:700; }
.warn { color:var(--warn); font-weight:600; }
.mut { color:var(--mut); }
.card { background:var(--card); border:1px solid var(--line); padding:10px 12px; margin:8px 0; }
.empty { background:#fffdf5; border:1px solid #e6d9a8; padding:12px 14px; margin:8px 0; }
.empty code { background:#f2ecd8; padding:1px 5px; }
.prov { color:var(--mut); font-size:11px; font-style:italic; margin:2px 0 10px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(430px,1fr)); gap:10px; }
svg { background:#fff; border:1px solid var(--line); }
.pill { display:inline-block; padding:1px 7px; border-radius:9px; font-size:11px;
        border:1px solid var(--line); background:#f0f3f6; }
"""


def _e(x: Any) -> str:
    return html.escape(str(x))


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{_e(title)}</title>"
        f"<style>{_CSS}</style></head><body>"
        f'<div class="wm">{_e(WATERMARK)}</div>'
        f'<nav><a href="/">data</a><a href="/factors">factors</a>'
        f'<a href="http://127.0.0.1:8799/worlds">QA shelf (8799)</a>'
        f'<a href="http://127.0.0.1:8798/">build (8798)</a>'
        f'<span class="prov" style="float:right">read-only · renders the recorded store only</span>'
        f"</nav><main>{body}</main></body></html>"
    )


def _empty(what: str, command: str) -> str:
    return (
        f'<div class="empty"><b>Not available:</b> {_e(what)}<br>'
        f"Produce it with <code>{_e(command)}</code></div>"
    )


# --------------------------------------------------------------------------- #
# tiny SVG primitives (same technique as ah/console.py — no plotting library)
# --------------------------------------------------------------------------- #


def _scale(v: float, lo: float, hi: float, a: float, b: float) -> float:
    if hi == lo:
        return (a + b) / 2.0
    return a + (v - lo) * (b - a) / (hi - lo)


def _proxy_runs(flags: pd.Series) -> list[tuple[int, int]]:
    """Contiguous [start, end] index runs where the proxy flag is set."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    vals = list(flags.astype(bool))
    for i, v in enumerate(vals):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(vals) - 1))
    return runs


def line_svg(
    frame: pd.DataFrame,
    *,
    title: str,
    proxy_col: str = "is_proxy",
    width: int = 600,
    height: int = 160,
    series2: pd.Series | None = None,
    label1: str = "",
    label2: str = "",
) -> str:
    """One series as a polyline; proxy-flagged stretches shaded behind it.

    ``series2`` overlays a second polyline on the same x/y scale (used for the
    reported vs de-smoothed privates view).
    """
    pad_l, pad_r, pad_t, pad_b = 46, 8, 20, 18
    if len(frame) == 0:
        return f'<svg width="{width}" height="{height}"><text x="8" y="20">{_e(title)}: no data</text></svg>'
    ys = frame["value"].to_numpy(dtype=float)
    all_y = ys if series2 is None else np.concatenate([ys, series2.to_numpy(dtype=float)])
    lo, hi = float(np.nanmin(all_y)), float(np.nanmax(all_y))
    n = len(frame)
    xs = [_scale(i, 0, max(n - 1, 1), pad_l, width - pad_r) for i in range(n)]

    parts = [f'<svg width="{width}" height="{height}" role="img">']
    parts.append(f'<text x="8" y="14" font-size="12" font-weight="600">{_e(title)}</text>')
    if proxy_col in frame.columns:
        for i0, i1 in _proxy_runs(_col(frame, proxy_col)):
            x0 = xs[i0] - (2 if i0 else 0)
            x1 = xs[i1]
            parts.append(
                f'<rect class="proxy" x="{x0:.1f}" y="{pad_t}" width="{max(x1 - x0, 2):.1f}" '
                f'height="{height - pad_t - pad_b}" fill="#f3e2c7" opacity="0.8">'
                f"<title>proxy-spliced stretch</title></rect>"
            )
        if _proxy_runs(_col(frame, proxy_col)):
            parts.append(
                f'<text x="{width - pad_r - 4}" y="14" font-size="10" text-anchor="end" '
                f'fill="#8a6d1f">shaded = proxy-spliced</text>'
            )

    def _poly(values: np.ndarray, color: str) -> str:
        pts = " ".join(
            f"{x:.1f},{_scale(float(v), lo, hi, height - pad_b, pad_t):.1f}"
            for x, v in zip(xs, values, strict=True)
            if np.isfinite(v)
        )
        return f'<polyline fill="none" stroke="{color}" stroke-width="1.4" points="{pts}"/>'

    parts.append(_poly(ys, "#1f4e79"))
    if series2 is not None:
        parts.append(_poly(series2.to_numpy(dtype=float), "#a3282f"))
        parts.append(
            f'<text x="{pad_l}" y="{height - 4}" font-size="10" fill="#1f4e79">{_e(label1)}</text>'
            f'<text x="{pad_l + 120}" y="{height - 4}" font-size="10" fill="#a3282f">{_e(label2)}</text>'
        )
    for v in (lo, hi):
        y = _scale(v, lo, hi, height - pad_b, pad_t)
        parts.append(f'<text x="4" y="{y + 4:.1f}" font-size="10" fill="#5c6874">{v:.3g}</text>')
    d0, d1 = str(frame["date"].iloc[0])[:7], str(frame["date"].iloc[-1])[:7]
    parts.append(
        f'<text x="{pad_l}" y="{height - pad_b + 12}" font-size="9" fill="#5c6874">{d0}</text>'
        f'<text x="{width - pad_r}" y="{height - pad_b + 12}" font-size="9" '
        f'text-anchor="end" fill="#5c6874">{d1}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def hist_svg(
    values: np.ndarray, *, title: str, bins: int = 30, width: int = 300, height: int = 160
) -> str:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return f'<svg width="{width}" height="{height}"><text x="8" y="20">{_e(title)}: no data</text></svg>'
    counts, edges = np.histogram(x, bins=bins)
    pad_t, pad_b = 20, 14
    top = counts.max() or 1
    bw = (width - 16) / bins
    parts = [f'<svg width="{width}" height="{height}">']
    parts.append(f'<text x="8" y="14" font-size="12" font-weight="600">{_e(title)}</text>')
    for i, c in enumerate(counts):
        h = _scale(float(c), 0, float(top), 0, height - pad_t - pad_b)
        parts.append(
            f'<rect x="{8 + i * bw:.1f}" y="{height - pad_b - h:.1f}" '
            f'width="{max(bw - 1, 1):.1f}" height="{h:.1f}" fill="#9fb4c7"/>'
        )
    parts.append(
        f'<text x="8" y="{height - 2}" font-size="9" fill="#5c6874">{edges[0]:.3g}</text>'
        f'<text x="{width - 8}" y="{height - 2}" font-size="9" text-anchor="end" '
        f'fill="#5c6874">{edges[-1]:.3g}</text></svg>'
    )
    return "".join(parts)


def coverage_bar(pct: float, *, width: int = 220) -> str:
    filled = int(pct * (width - 2))
    color = "#1f6b3a" if pct >= 0.999 else ("#8a6d1f" if pct >= 0.9 else "#a3282f")
    return (
        f'<svg width="{width}" height="14"><rect x="0" y="0" width="{width}" height="14" '
        f'fill="#eef1f4"/><rect x="1" y="1" width="{filled}" height="12" fill="{color}"/>'
        f"<title>{pct:.1%} of spanned months observed</title></svg>"
    )


# --------------------------------------------------------------------------- #
# store access (reads only)
# --------------------------------------------------------------------------- #


def _index_rows(cat: Catalog, vintage: str) -> dict[str, dict[str, Any]]:
    rows = cat.con.execute(
        "SELECT series_id, source, n_obs, first_date, last_date "
        "FROM observations_index WHERE vintage_id = ?",
        [vintage],
    ).fetchall()
    return {
        r[0]: {"source": r[1], "n_obs": r[2], "first_date": str(r[3]), "last_date": str(r[4])}
        for r in rows
    }


def _qc_summary(cat: Catalog, vintage: str) -> list[tuple[str, bool, int]]:
    rows = cat.con.execute(
        "SELECT severity, passed, COUNT(*) FROM qc_results WHERE vintage_id = ? "
        "GROUP BY severity, passed ORDER BY severity, passed",
        [vintage],
    ).fetchall()
    return [(str(r[0]), bool(r[1]), int(r[2])) for r in rows]


def _read_current(cat: Catalog, vintage: str, sid: str) -> pd.DataFrame | None:
    try:
        frame = cat.read_observations(vintage, sid)
    except Exception:
        return None
    return frame if len(frame) else None


def _factor_frame(cat: Catalog, vintage: str, fs: Any) -> tuple[pd.DataFrame | None, str]:
    """Mechanically recompute one factor for display. Returns (frame, note).

    kind=series  -> the series frame verbatim.
    kind=derived -> getattr(ah.data.derive, fs.expr)(*[frame(sid) for sid in fs.inputs])
    kind=unavailable -> (None, the sealed reason).
    Missing input series -> (None, naming what is absent).
    """
    from ah.data import derive

    if fs.kind == "unavailable":
        return None, f"unavailable — {fs.reason}"
    if fs.kind == "series":
        frame = _read_current(cat, vintage, str(fs.series_id))
        return (
            (frame, "") if frame is not None else (None, f"input {fs.series_id} absent from store")
        )
    inputs = []
    for sid in fs.inputs:
        frame = _read_current(cat, vintage, sid)
        if frame is None:
            return None, f"input {sid} absent from store"
        inputs.append(frame)
    try:
        out = getattr(derive, str(fs.expr))(*inputs)
    except Exception as exc:
        return None, f"derive.{fs.expr} failed: {type(exc).__name__}: {exc}"
    if getattr(fs, "proxy", False) and "is_proxy" not in out.columns:
        # The sealed derive keeps the panel's canonical (date, value) shape and
        # strips per-row proxy flags (derive.hy_oas_spliced docstring). Recompute
        # the mask from the splice contract itself: actuals are never touched,
        # so any factor date absent from the target series (inputs[0] by the
        # splice convention) is proxy by construction.
        target_dates = set(pd.DatetimeIndex(_col(inputs[0], "date")))
        out = out.copy()
        out["is_proxy"] = [d not in target_dates for d in pd.DatetimeIndex(_col(out, "date"))]
    return out, ""


# --------------------------------------------------------------------------- #
# the app
# --------------------------------------------------------------------------- #


def create_app(data_root: str | Path = DEFAULT_DATA_ROOT) -> FastAPI:
    app = FastAPI(title="ah data console", version="0.1.0")
    app.state.data_root = Path(data_root)

    def _cat() -> Catalog:
        return Catalog(app.state.data_root)

    @app.get("/", response_class=HTMLResponse)
    def inventory() -> HTMLResponse:
        cat = _cat()
        try:
            vintage = cat.current_vintage()
            if vintage is None:
                return _page(
                    "data inventory",
                    "<h1>The vintage store</h1>"
                    + _empty(
                        "no current vintage in this store",
                        "uv run ah data refresh --fixtures <dir> --asof YYYY-MM-DD",
                    ),
                )
            as_of = str(pd.Timestamp.now().date())
            reqs = load_requirements()
            index = _index_rows(cat, vintage)

            # per-source freshness
            src_rows = []
            for source in sorted(reqs.sources()):
                latest = max(
                    (
                        index[r.series_id]["last_date"]
                        for r in reqs.by_source(source)
                        if r.series_id in index
                    ),
                    default=None,
                )
                breaches = []
                for r in reqs.by_source(source):
                    if r.series_id in index and r.enforce:
                        st = staleness_days(index[r.series_id]["last_date"], as_of)
                        if st > r.sla_days:
                            breaches.append(f"{r.series_id} ({st}d > SLA {r.sla_days}d)")
                cls = "bad" if breaches else "ok"
                note = "; ".join(breaches) if breaches else "within SLA (enforced series)"
                src_rows.append(
                    f'<tr><td class="l">{_e(source)}</td><td>{_e(latest or "—")}</td>'
                    f'<td class="l {cls}">{_e(note)}</td></tr>'
                )

            qc_rows = "".join(
                f'<tr><td class="l">{_e(sev)}</td>'
                f'<td class="{"ok" if passed else ("bad" if sev == "enforce" else "warn")}">{passed}</td>'
                f"<td>{n}</td></tr>"
                for sev, passed, n in _qc_summary(cat, vintage)
            )

            cards = "".join(
                f'<div class="card"><b><a href="/class/{_e(name)}">{_e(name)}</a></b><br>'
                f'<span class="mut">{len(spec["raw"])} raw series · '
                f"{len(spec['factors'])} factor(s)</span></div>"
                for name, spec in CLASSES.items()
            )

            inv_rows = []
            for r in sorted(reqs, key=lambda q: q.series_id):
                if r.series_id in index:
                    frame = _read_current(cat, vintage, r.series_id)
                    meta = index[r.series_id]
                    gaps = gap_ranges(_col(frame, "date")) if frame is not None else []
                    st = staleness_days(meta["last_date"], as_of)
                    stale_cls = "mut" if not r.enforce else ("bad" if st > r.sla_days else "ok")
                    ppct = proxy_pct(frame) if frame is not None else 0.0
                    inv_rows.append(
                        f'<tr><td class="l"><a href="/series/{_e(r.series_id)}">{_e(r.series_id)}</a></td>'
                        f"<td>{_e(meta['first_date'])}</td><td>{_e(meta['last_date'])}</td>"
                        f"<td>{meta['n_obs']}</td><td>{len(gaps)}</td>"
                        f'<td class="{stale_cls}">{st}d / SLA {r.sla_days}d</td>'
                        f"<td>{ppct:.0%}</td>"
                        f'<td class="l">{"enforce" if r.enforce else "warn"}</td></tr>'
                    )
                else:
                    inv_rows.append(
                        f'<tr><td class="l">{_e(r.series_id)}</td>'
                        f'<td colspan="6" class="l mut">registered, never fetched'
                        f" (intake: {_e(r.intake)}, {_e(r.license_tier)})</td>"
                        f'<td class="l">{"enforce" if r.enforce else "warn"}</td></tr>'
                    )

            body = (
                f"<h1>The vintage store</h1>"
                f'<p class="prov">root {_e(app.state.data_root)} · current vintage '
                f"<b>{_e(vintage)}</b> · as of {_e(as_of)} · "
                f"coherence recomputed from the store, nothing cached</p>"
                f"<h2>Asset classes</h2><div class='grid'>{cards}</div>"
                f"<h2>Per-source freshness</h2>"
                f'<table><tr><th class="l">source</th><th>latest obs</th><th class="l">SLA state</th></tr>'
                + "".join(src_rows)
                + "</table>"
                f"<h2>QC summary (recorded)</h2>"
                f'<table><tr><th class="l">severity</th><th>passed</th><th>count</th></tr>{qc_rows}</table>'
                f"<h2>Series inventory ({len(reqs)} registered)</h2>"
                f'<table><tr><th class="l">series</th><th>first</th><th>last</th><th>obs</th>'
                f"<th>gaps</th><th>staleness</th><th>proxy %</th><th class='l'>level</th></tr>"
                + "".join(inv_rows)
                + "</table>"
            )
            return _page("data inventory", body)
        finally:
            cat.close()

    @app.get("/series/{sid}", response_class=HTMLResponse)
    def series_page(sid: str) -> HTMLResponse:
        reqs = load_requirements()
        req = reqs.get(sid)
        if req is None:
            raise HTTPException(404, f"no registered series {sid}")
        cat = _cat()
        try:
            vintage = cat.current_vintage()
            if vintage is None:
                return _page(
                    sid,
                    f"<h1>{_e(sid)}</h1>"
                    + _empty("no current vintage", "uv run ah data refresh ..."),
                )
            frame = _read_current(cat, vintage, sid)
            if frame is None:
                body = (
                    f"<h1>{_e(sid)}</h1>"
                    f'<p class="prov">registered, never fetched (intake: {_e(req.intake)})</p>'
                    + _manifest_table(req)
                )
                return _page(sid, body)

            gaps = gap_ranges(_col(frame, "date"))
            gap_rows = "".join(
                f'<tr><td class="l">{a}</td><td class="l">{b}</td></tr>' for a, b in gaps
            )
            vint_rows = "".join(
                f'<tr><td class="l">{_e(r[0])}</td><td>{r[1]}</td><td>{_e(str(r[2]))}</td>'
                f'<td>{_e(str(r[3]))}</td><td class="l">{"&larr; current" if r[0] == vintage else ""}</td></tr>'
                for r in cat.con.execute(
                    "SELECT vintage_id, n_obs, first_date, last_date FROM observations_index "
                    "WHERE series_id = ? ORDER BY vintage_id",
                    [sid],
                ).fetchall()
            )
            qc_rows = "".join(
                f'<tr><td class="l">{_e(r[0])}</td><td class="l">{_e(r[1])}</td>'
                f'<td class="{"ok" if r[2] else "bad"}">{bool(r[2])}</td><td class="l">{_e(r[3])}</td></tr>'
                for r in cat.con.execute(
                    "SELECT rule, severity, passed, detail FROM qc_results "
                    "WHERE series_id = ? AND vintage_id = ? ORDER BY rule",
                    [sid, vintage],
                ).fetchall()
            )
            m = moments(frame["value"].to_numpy())
            body = (
                f"<h1>{_e(sid)}</h1>"
                f'<p class="prov">vintage {_e(vintage)} · {len(frame)} obs · '
                f"coverage {coverage_pct(_col(frame, 'date')):.1%} · proxy {proxy_pct(frame):.0%}</p>"
                + line_svg(
                    frame, title=f"{sid} — full history (current vintage)", width=900, height=220
                )
                + f"<div class='grid'>{hist_svg(frame['value'].to_numpy(), title='distribution')}"
                + "<table><tr><th class='l'>moment</th><th>value</th></tr>"
                + "".join(f'<tr><td class="l">{k}</td><td>{v:.6g}</td></tr>' for k, v in m.items())
                + "</table></div>"
                + "<h2>Gaps</h2>"
                + (
                    f'<table><tr><th class="l">from</th><th class="l">to</th></tr>{gap_rows}</table>'
                    if gaps
                    else '<p class="ok">no missing months in span</p>'
                )
                + "<h2>Vintages carrying this series</h2>"
                + f'<table><tr><th class="l">vintage</th><th>obs</th><th>first</th><th>last</th><th class="l"></th></tr>{vint_rows}</table>'
                + "<h2>QC findings (current vintage)</h2>"
                + (
                    f'<table><tr><th class="l">rule</th><th class="l">severity</th><th>passed</th><th class="l">detail</th></tr>{qc_rows}</table>'
                    if qc_rows
                    else '<p class="mut">none recorded</p>'
                )
                + "<h2>Manifest entry</h2>"
                + _manifest_table(req)
            )
            return _page(sid, body)
        finally:
            cat.close()

    @app.get("/class/{name}", response_class=HTMLResponse)
    def class_page(name: str) -> HTMLResponse:
        from ah.factors import load_manifest

        spec = CLASSES.get(name)
        if spec is None:
            raise HTTPException(404, f"no asset class {name}")
        cat = _cat()
        try:
            vintage = cat.current_vintage()
            if vintage is None:
                return _page(
                    name,
                    f"<h1>{_e(name)}</h1>"
                    + _empty("no current vintage", "uv run ah data refresh ..."),
                )
            reqs = load_requirements()

            raw_parts = []
            for sid in spec["raw"]:
                frame = _read_current(cat, vintage, sid)
                if frame is None:
                    raw_parts.append(
                        f'<div class="card"><b><a href="/series/{_e(sid)}">{_e(sid)}</a></b> '
                        f'<span class="mut">registered, never fetched'
                        f" (intake: {_e(reqs[sid].intake if sid in reqs else '?')})</span></div>"
                    )
                    continue
                raw_parts.append(
                    f'<div class="card"><b><a href="/series/{_e(sid)}">{_e(sid)}</a></b> '
                    f"coverage {coverage_bar(coverage_pct(_col(frame, 'date')))} "
                    f'<span class="mut">proxy {proxy_pct(frame):.0%}</span><br>'
                    + line_svg(frame, title=sid)
                    + "</div>"
                )

            factor_parts = []
            if spec["factors"]:
                sources = load_manifest().sources
                for fname in spec["factors"]:
                    fs = sources.get(fname)
                    if fs is None:
                        continue
                    frame, note = _factor_frame(cat, vintage, fs)
                    if frame is None:
                        factor_parts.append(
                            f'<div class="card"><b>{_e(fname)}</b> '
                            f'<span class="warn">{_e(note)}</span></div>'
                        )
                        continue
                    m = moments(frame["value"].to_numpy())
                    proxy_chip = (
                        f'<span class="pill warn" title="{_e(fs.proxy_for or "")}">'
                        "proxy-spliced backfill</span>"
                        if getattr(fs, "proxy", False)
                        else ""
                    )
                    factor_parts.append(
                        f'<div class="card"><b>{_e(fname)}</b> '
                        f'<span class="pill">{_e(fs.kind)}</span>{proxy_chip}<br>'
                        + line_svg(frame, title=f"factor: {fname}")
                        + hist_svg(frame["value"].to_numpy(), title="distribution")
                        + "<table><tr>"
                        + "".join(f'<th class="l">{k}</th>' for k in m)
                        + "</tr><tr>"
                        + "".join(f"<td>{v:.6g}</td>" for v in m.values())
                        + "</tr></table></div>"
                    )

            desmooth_parts = []
            if name == "privates":
                from ah.data.desmooth import glm_ma

                for sid in spec["raw"]:
                    frame = _read_current(cat, vintage, sid)
                    if frame is None or len(frame) < 12:
                        continue
                    reported = frame["value"].to_numpy(dtype=float)
                    res = glm_ma(reported)
                    truth = pd.Series(res.truth)
                    m_rep, m_true = moments(reported), moments(res.truth)
                    rows = "".join(
                        f'<tr><td class="l">{k}</td><td>{m_rep[k]:.6g}</td><td>{m_true[k]:.6g}</td></tr>'
                        for k in m_rep
                    )
                    desmooth_parts.append(
                        f'<div class="card"><b>{_e(sid)}</b> '
                        f'<span class="pill">method {_e(res.method)} (k={res.k})</span><br>'
                        + line_svg(
                            frame,
                            title=f"{sid}: reported vs de-smoothed",
                            series2=truth,
                            label1="reported",
                            label2="de-smoothed",
                            width=900,
                            height=200,
                        )
                        + f'<table><tr><th class="l">moment</th><th>reported</th><th>de-smoothed</th></tr>{rows}</table>'
                        + "</div>"
                    )
                if not desmooth_parts:
                    desmooth_parts.append(
                        _empty(
                            "no private-markets series in the store (or too few observations)",
                            "uv run ah data intake validate <file> --schema albourne_pm_returns",
                        )
                    )

            body = (
                f"<h1>{_e(name)}</h1>"
                f'<p class="prov">vintage {_e(vintage)} · raw series first, then the derived '
                f"factor(s) the generator consumes</p>"
                f"<h2>Raw series</h2>{''.join(raw_parts)}"
                + (f"<h2>Derived factors</h2>{''.join(factor_parts)}" if factor_parts else "")
                + (
                    f"<h2>Reported vs de-smoothed (appraisal-smoothing correction)</h2>{''.join(desmooth_parts)}"
                    if name == "privates"
                    else ""
                )
            )
            return _page(name, body)
        finally:
            cat.close()

    @app.get("/factors", response_class=HTMLResponse)
    def factors_page() -> HTMLResponse:
        from ah.factors import load_manifest
        from ah.splits import HOLDOUT, TRAIN, VALIDATION

        cat = _cat()
        try:
            vintage = cat.current_vintage()
            if vintage is None:
                return _page(
                    "factors",
                    "<h1>The factor panel</h1>"
                    + _empty("no current vintage", "uv run ah data refresh ..."),
                )
            manifest = load_manifest()
            splits_note = (
                f'<div class="card"><b>Sealed splits</b> (ah.splits): '
                f"train {TRAIN.start}..{TRAIN.end} · "
                f"validation {VALIDATION.start}..{VALIDATION.end} · "
                f'<span class="warn">holdout {HOLDOUT.start}..{HOLDOUT.end} — '
                f"SPENT at WP5.6</span>. The generator trains on train+validation "
                f"only; shading below marks the windows.</div>"
            )

            def _split_shading(frame: pd.DataFrame, width: int = 600, height: int = 160) -> str:
                """Vertical bands for validation and holdout over a chart's x-range."""
                if len(frame) < 2:
                    return ""
                d0 = pd.Timestamp(frame["date"].iloc[0])
                d1 = pd.Timestamp(frame["date"].iloc[-1])
                span = (d1 - d0).days or 1
                out = []
                for split, color, label in (
                    (VALIDATION, "#dce8f2", "validation"),
                    (HOLDOUT, "#f2dcdc", "holdout (SPENT)"),
                ):
                    s = max(pd.Timestamp(split.start), d0)
                    e = min(pd.Timestamp(split.end), d1)
                    if s >= e:
                        continue
                    x0 = 46 + (s - d0).days / span * (width - 54)
                    x1 = 46 + (e - d0).days / span * (width - 54)
                    out.append(
                        f'<rect x="{x0:.1f}" y="20" width="{x1 - x0:.1f}" height="{height - 38}" '
                        f'fill="{color}" opacity="0.7"><title>{label}</title></rect>'
                    )
                return "".join(out)

            rows = []
            for block in manifest.blocks:
                active = manifest.is_active(block)
                rows.append(
                    f"<h2>block: {_e(block)} {'' if active else '(inert — not in active_blocks)'}</h2>"
                )
                for fname in manifest.blocks[block]:
                    fs = manifest.sources[fname]
                    frame, note = (None, "") if not active else _factor_frame(cat, vintage, fs)
                    head = (
                        f"<b>{_e(fname)}</b> "
                        f'<span class="pill">{_e(fs.kind)}</span> '
                        f'<span class="pill">{_e(fs.units or "—")}</span>'
                        + (f' <span class="pill">{_e(fs.numeraire)}</span>' if fs.numeraire else "")
                        + (
                            f' <span class="pill warn" title="{_e(fs.proxy_for or "")}">'
                            "proxy-spliced backfill</span>"
                            if fs.proxy
                            else ""
                        )
                    )
                    if not active:
                        rows.append(
                            f'<div class="card">{head} <span class="mut">inert block — not rendered</span></div>'
                        )
                        continue
                    if fs.kind == "unavailable":
                        rows.append(
                            f'<div class="card">{head}<br><span class="warn">unavailable — '
                            f"{_e(fs.reason)}</span></div>"
                        )
                        continue
                    if frame is None:
                        rows.append(
                            f'<div class="card">{head}<br><span class="warn">{_e(note)}</span></div>'
                        )
                        continue
                    m = moments(frame["value"].to_numpy())
                    chart = line_svg(frame, title=f"factor: {fname}")
                    # inject split shading right after the opening svg content
                    shading = _split_shading(frame)
                    if shading:
                        chart = chart.replace("</svg>", shading + "</svg>")
                    srcs = (
                        f'source: <a href="/series/{_e(fs.series_id)}">{_e(fs.series_id)}</a>'
                        if fs.kind == "series"
                        else "inputs: "
                        + " · ".join(f'<a href="/series/{_e(s)}">{_e(s)}</a>' for s in fs.inputs)
                        + f" via derive.{_e(fs.expr)}"
                    )
                    rows.append(
                        f'<div class="card">{head}<br>{chart}'
                        + "<table><tr>"
                        + "".join(f'<th class="l">{k}</th>' for k in m)
                        + "</tr><tr>"
                        + "".join(f"<td>{v:.6g}</td>" for v in m.values())
                        + "</tr></table>"
                        + f'<span class="mut">{srcs}</span></div>'
                    )

            body = (
                "<h1>The factor panel — what the generator sees</h1>"
                f'<p class="prov">vintage {_e(vintage)} · every factor recomputed mechanically '
                f"from factors.yaml's factor_sources (kind=series verbatim; kind=derived via "
                f"ah.data.derive); nothing hand-drawn</p>" + splits_note + "".join(rows)
            )
            return _page("factors", body)
        finally:
            cat.close()

    return app


app = create_app()
