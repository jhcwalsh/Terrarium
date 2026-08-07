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
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement, load_requirements

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
    return float(frame["is_proxy"].astype(bool).mean())


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
                    gaps = gap_ranges(frame["date"]) if frame is not None else []
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

    return app


app = create_app()
