"""The internal QA inspection console (Task 3) — read-only, real output only.

An operator instrument for eyeball-testing what the engine actually produces,
world by world. **Not the player product**: information density over polish.

**Stack, and why.** FastAPI (already a dependency, per ``ah/serve.py``) serving
HTML built in pure Python. That is this repository's established pattern for
inspection surfaces — ``ah/inspect.py``, ``ah/credibility.py`` and
``ah/programme.py`` all render self-contained HTML with inline SVG and zero
template engine. Adding Jinja, Streamlit or a JS build step would introduce a
dependency the repo's conventions require justifying, to produce a page the
existing technique already produces.

**Read-only, structurally.** The SQLite connection is opened in SQLite
``mode=ro`` so a write is refused by the driver rather than by discipline. This
module imports no writer: an import-graph test (``tests/test_console_guard.py``)
asserts it cannot reach ``ah.store.worlds.save_world``,
``ah.store.runrecords.save_run_record``, ``ah.store.chronicle.append`` or
``ah.serve``. The replay check runs against a temporary copy of the database in
a scratch directory and never touches the original.

**Real output only.** Every page reads the world store, the run records, or a
recorded battery artifact. Where an artifact does not exist the page renders an
explicit empty state naming the command that would produce it. No fixture is
imported anywhere in this module; nothing is mocked.

**No LLM calls.** The console renders what exists.

Run it::

    uv run uvicorn ah.console:app --port 8799

Pages: ``/worlds`` · ``/world/{id}/path`` · ``/world/{id}/ensemble`` ·
``/world/{id}/cashflows`` · ``/run/{run_id}`` · ``/battery/{report_id}`` ·
``/diff``.
"""

from __future__ import annotations

import contextlib
import html
import json
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ah.core.engine import ASSETS, REPORTED_SLEEVES, EnginePaths, run_ensemble, run_path
from ah.core.numericworld import project_numeric
from ah.core.validator import validate
from ah.core.worldspec import WorldSpec
from ah.play import START_CASH, simulate_play

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"

WATERMARK = "INTERNAL QA CONSOLE — simulated data — not investment advice"

#: Structural floors the engine asserts (D5 constraints). A breach is a
#: generator defect surfaced, which is the console doing its job.
#: ``engine.py:207`` floors the policy rate; ``engine.py:241`` floors the spread.
RATE_FLOOR_PCT = 0.1
SPREAD_FLOOR_BPS = 150.0

# --------------------------------------------------------------------------- #
# chrome
# --------------------------------------------------------------------------- #

_CSS = """
:root { --ink:#151a1f; --mut:#5c6874; --line:#e2e6ea; --bg:#f7f8fa; --card:#fff;
        --ok:#1f6b3a; --bad:#a3282f; --warn:#8a6d1f; }
* { box-sizing:border-box; }
body { margin:0; font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;
       color:var(--ink); background:var(--bg); }
.wm { background:#2b2f36; color:#fff; font-size:11px; letter-spacing:.06em;
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
.card { background:var(--card); border:1px solid var(--line); padding:10px 12px; margin:8px 0; }
.empty { background:#fffdf5; border:1px solid #e6d9a8; padding:12px 14px; margin:8px 0; }
.empty code { background:#f2ecd8; padding:1px 5px; }
.prov { color:var(--mut); font-size:11px; font-style:italic; margin:2px 0 10px; }
details.src { display:inline; }
details.src summary { cursor:help; color:var(--mut); font-size:11px; list-style:none; }
details.src[open] summary { color:#1f4e79; }
details.src p { background:#f2f5f8; border-left:2px solid #9fb4c7; margin:3px 0;
                padding:4px 7px; font-size:11px; color:#333; font-style:normal; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(430px,1fr)); gap:10px; }
svg { background:#fff; border:1px solid var(--line); }
.pill { display:inline-block; padding:1px 7px; border-radius:9px; font-size:11px;
        border:1px solid var(--line); background:#f0f3f6; }
"""


def _e(x: Any) -> str:
    return html.escape(str(x))


def _src(label: str, detail: str) -> str:
    """A traceability disclosure: where this number came from."""
    return f'<details class="src"><summary>{_e(label)}</summary><p>{_e(detail)}</p></details>'


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{_e(title)}</title>"
        f"<style>{_CSS}</style></head><body>"
        f'<div class="wm">{_e(WATERMARK)}</div>'
        f'<nav><a href="/worlds">shelf</a><a href="/diff">diff</a>'
        f'<span class="prov" style="float:right">read-only · renders recorded output only</span></nav>'
        f"<main>{body}</main></body></html>"
    )


def _empty(what: str, command: str) -> str:
    return (
        f'<div class="empty"><b>Not available:</b> {_e(what)}<br>'
        f"Produce it with <code>{_e(command)}</code></div>"
    )


# --------------------------------------------------------------------------- #
# tiny SVG primitives (same technique as ah/inspect.py — no plotting library)
# --------------------------------------------------------------------------- #


def _scale(v: float, lo: float, hi: float, a: float, b: float) -> float:
    if hi == lo:
        return (a + b) / 2.0
    return a + (v - lo) * (b - a) / (hi - lo)


def _line_svg(
    series: dict[str, np.ndarray],
    title: str,
    *,
    bands: list[tuple[int, int, str]] | None = None,
    markers: list[tuple[int, str]] | None = None,
    fill_between: tuple[str, str] | None = None,
    w: int = 620,
    h: int = 230,
) -> str:
    if not series:
        return ""
    pad_l, pad_r, pad_t, pad_b = 52, 12, 26, 22
    n = max(len(v) for v in series.values())
    lo = min(float(np.nanmin(v)) for v in series.values())
    hi = max(float(np.nanmax(v)) for v in series.values())
    if lo == hi:
        lo, hi = lo - 1.0, hi + 1.0
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad

    def X(i: int) -> float:
        return _scale(i, 0, max(1, n - 1), pad_l, w - pad_r)

    def Y(v: float) -> float:
        return _scale(v, lo, hi, h - pad_b, pad_t)

    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">']
    for x0, x1, label in bands or []:
        out.append(
            f'<rect x="{X(x0):.1f}" y="{pad_t}" width="{max(1.0, X(x1) - X(x0)):.1f}" '
            f'height="{h - pad_t - pad_b}" fill="#3b6ea5" opacity="0.07"/>'
        )
        out.append(
            f'<text x="{X(x0) + 3:.1f}" y="{pad_t + 10}" font-size="9" fill="#5c6874">{_e(label)}</text>'
        )
    # axes
    out.append(
        f'<line x1="{pad_l}" y1="{h - pad_b}" x2="{w - pad_r}" y2="{h - pad_b}" stroke="#c9d1d8"/>'
    )
    out.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{h - pad_b}" stroke="#c9d1d8"/>')
    for frac in (0.0, 0.5, 1.0):
        v = lo + (hi - lo) * frac
        out.append(
            f'<text x="{pad_l - 5}" y="{Y(v) + 3:.1f}" font-size="9" fill="#5c6874" '
            f'text-anchor="end">{v:,.2f}</text>'
        )
    if fill_between and all(k in series for k in fill_between):
        a, b = series[fill_between[0]], series[fill_between[1]]
        top = " ".join(f"{X(i):.1f},{Y(float(a[i])):.1f}" for i in range(len(a)))
        bot = " ".join(f"{X(i):.1f},{Y(float(b[i])):.1f}" for i in reversed(range(len(b))))
        out.append(f'<polygon points="{top} {bot}" fill="#a3282f" opacity="0.16"/>')
    colours = ("#1f4e79", "#a3282f", "#1f6b3a", "#8a6d1f", "#6b3fa0", "#0f6f78", "#8a4b2f", "#444")
    for k, (name, vals) in enumerate(series.items()):
        pts = " ".join(f"{X(i):.1f},{Y(float(v)):.1f}" for i, v in enumerate(vals))
        col = colours[k % len(colours)]
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.4"/>')
        out.append(
            f'<rect x="{pad_l + 4 + k * 108}" y="6" width="8" height="8" fill="{col}"/>'
            f'<text x="{pad_l + 15 + k * 108}" y="14" font-size="9.5" fill="#333">{_e(name)}</text>'
        )
    for i, label in markers or []:
        out.append(
            f'<line x1="{X(i):.1f}" y1="{pad_t}" x2="{X(i):.1f}" y2="{h - pad_b}" '
            f'stroke="#a3282f" stroke-width="0.8" stroke-dasharray="3 2"><title>{_e(label)}</title></line>'
        )
    out.append(f'<text x="{pad_l}" y="{h - 6}" font-size="10" fill="#5c6874">{_e(title)}</text>')
    out.append("</svg>")
    return "".join(out)


def _fan_svg(paths: np.ndarray, title: str, w: int = 430, h: int = 200) -> str:
    """p5/p25/p50/p75/p95 cone of cumulative growth across seeds."""
    qs = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    pad_l, pad_r, pad_t, pad_b = 48, 10, 22, 20
    n = paths.shape[1]
    lo, hi = float(np.min(qs)), float(np.max(qs))
    if lo == hi:
        lo, hi = lo - 1, hi + 1

    def X(i: int) -> float:
        return _scale(i, 0, max(1, n - 1), pad_l, w - pad_r)

    def Y(v: float) -> float:
        return _scale(v, lo, hi, h - pad_b, pad_t)

    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">']
    for a, b, op in ((0, 4, 0.10), (1, 3, 0.20)):
        top = " ".join(f"{X(i):.1f},{Y(float(qs[b][i])):.1f}" for i in range(n))
        bot = " ".join(f"{X(i):.1f},{Y(float(qs[a][i])):.1f}" for i in reversed(range(n)))
        out.append(f'<polygon points="{top} {bot}" fill="#1f4e79" opacity="{op}"/>')
    med = " ".join(f"{X(i):.1f},{Y(float(qs[2][i])):.1f}" for i in range(n))
    out.append(f'<polyline points="{med}" fill="none" stroke="#1f4e79" stroke-width="1.4"/>')
    for frac in (0.0, 1.0):
        v = lo + (hi - lo) * frac
        out.append(
            f'<text x="{pad_l - 4}" y="{Y(v) + 3:.1f}" font-size="9" fill="#5c6874" '
            f'text-anchor="end">{v:,.2f}</text>'
        )
    out.append(f'<text x="{pad_l}" y="{h - 5}" font-size="10" fill="#5c6874">{_e(title)}</text>')
    out.append("</svg>")
    return "".join(out)


def _hist_svg(values: np.ndarray, title: str, w: int = 430, h: int = 190, bins: int = 18) -> str:
    if values.size == 0:
        return ""
    counts, edges = np.histogram(values, bins=bins)
    pad_l, pad_r, pad_t, pad_b = 40, 10, 20, 22
    mx = max(1, int(counts.max()))
    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">']
    bw = (w - pad_l - pad_r) / len(counts)
    for i, c in enumerate(counts):
        bh = (h - pad_t - pad_b) * (c / mx)
        out.append(
            f'<rect x="{pad_l + i * bw:.1f}" y="{h - pad_b - bh:.1f}" width="{bw - 1.5:.1f}" '
            f'height="{bh:.1f}" fill="#1f4e79" opacity="0.75"><title>{c} of {values.size}, '
            f"[{edges[i]:.3f}, {edges[i + 1]:.3f}]</title></rect>"
        )
    out.append(
        f'<text x="{pad_l}" y="{h - 6}" font-size="10" fill="#5c6874">{_e(title)} '
        f"(n={values.size}, min {values.min():.3f}, max {values.max():.3f})</text>"
    )
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# read-only data access
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# the two checks, as pure functions
#
# They are module-level and side-effect-free ON PURPOSE: the acceptance walk
# feeds a deliberately corrupted copy through these exact functions to show the
# strip and the footer recompute rather than printing a stored verdict. A check
# that cannot be made to go red has not been shown to work.
# --------------------------------------------------------------------------- #

SanityRow = tuple[str, float, float, float, float, str]


def sanity_rows(p: EnginePaths) -> list[SanityRow]:
    """min/max/first/last per series, with the D5 structural verdict.

    Returns ``(name, min, max, first, last, breach)``; ``breach`` is empty when
    the series is within its structural constraint. Floors are the engine's own:
    policy rate ``engine.py:207``, HY spread ``engine.py:241``, and cumulative
    growth must stay strictly positive for every asset (a non-positive value is
    a negative price).
    """
    rows: list[SanityRow] = []
    for name, arr, floor in (
        ("policy rate (%)", p.rate, RATE_FLOOR_PCT),
        ("HY spread (bps)", p.spread, SPREAD_FLOOR_BPS),
    ):
        rows.append(
            (
                name,
                float(arr.min()),
                float(arr.max()),
                float(arr[0]),
                float(arr[-1]),
                "" if arr.min() >= floor - 1e-9 else f"below floor {floor}",
            )
        )
    for a in ASSETS:
        growth = np.cumprod(1.0 + p.returns[a] / 100.0)
        rows.append(
            (
                f"{a} growth",
                float(growth.min()),
                float(growth.max()),
                float(growth[0]),
                float(growth[-1]),
                "" if growth.min() > 0.0 else "negative price (cumulative growth <= 0)",
            )
        )
    return rows


def cash_identity(quarters: list[Any], opening_cash: float) -> list[float]:
    """Per-quarter residual of the waterfall's cash identity.

    ``cash_q = cash_{q-1} + distributions - calls - spending + forced-sale proceeds``

    which is the order ``ah.port.engine.PortfolioEngine.run_quarter`` applies.
    Returns one residual per quarter; a non-zero entry means the displayed
    numbers and the engine disagree, and either is a finding.

    Note the identity holds exactly only for a decision-free ledger. A voluntary
    secondary sale credits cash outside ``run_quarter``, so a played session
    would show a residual equal to those proceeds — which is why the cashflow
    page renders the hold-course twin.
    """
    residuals: list[float] = []
    prev = opening_cash
    for q in quarters:
        expected = (
            prev + q.distributions_received - q.calls_paid - q.spending_paid + q.forced_sale_total
        )
        residuals.append(float(q.cash - expected))
        prev = q.cash
    return residuals


def _ro_conn(db_path: Path) -> sqlite3.Connection:
    """Open the store READ-ONLY. A write raises OperationalError from the driver."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@dataclass(frozen=True)
class WorldRow:
    world_id: str
    spec_version: str
    status: str
    created_at: str
    doc: dict[str, Any]


def _worlds(conn: sqlite3.Connection) -> list[WorldRow]:
    rows = conn.execute(
        "SELECT world_id, spec_version, status, json, created_at FROM worlds ORDER BY created_at"
    ).fetchall()
    return [
        WorldRow(
            r["world_id"], r["spec_version"], r["status"], r["created_at"], json.loads(r["json"])
        )
        for r in rows
    ]


def _world(conn: sqlite3.Connection, world_id: str) -> WorldRow | None:
    for w in _worlds(conn):
        if w.world_id == world_id:
            return w
    return None


def _runs(conn: sqlite3.Connection, world_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM run_records"
    args: tuple[Any, ...] = ()
    if world_id:
        sql += " WHERE world_id = ?"
        args = (world_id,)
    sql += " ORDER BY created_at"
    out = []
    for r in conn.execute(sql, args).fetchall():
        d = dict(r)
        for k in ("resolved_engine", "overrides", "summary_stats"):
            if isinstance(d.get(k), str):
                with contextlib.suppress(json.JSONDecodeError):
                    d[k] = json.loads(d[k])
        out.append(d)
    return out


def _battery_reports() -> list[tuple[str, Path]]:
    """Every recorded Step-2 battery report on disk, newest path last.

    Both ``artifacts/`` (partly committed) and ``experiments/`` (gitignored) are
    scanned, because the campaign-2 cells that carry the sealed digest live in
    the latter — a fact the evidence chain depends on and the console should
    not hide.
    """
    found: list[tuple[str, Path]] = []
    for root in (_REPO_ROOT / "artifacts", _REPO_ROOT / "experiments"):
        if not root.exists():
            continue
        for p in sorted(root.rglob("battery*.json")):
            rel = p.relative_to(_REPO_ROOT).as_posix()
            found.append((rel.replace("/", "~"), p))
    return found


# --------------------------------------------------------------------------- #
# the app
# --------------------------------------------------------------------------- #


def create_app(db_path: str | Path = DEFAULT_DB) -> FastAPI:
    db = Path(db_path)
    app = FastAPI(title="ah QA console", version="0.1.0")

    def conn() -> sqlite3.Connection:
        return _ro_conn(db)

    # ---------------------------------------------------------------- shelf --
    @app.get("/", response_class=HTMLResponse)
    @app.get("/worlds", response_class=HTMLResponse)
    def worlds_page() -> HTMLResponse:
        if not db.exists():
            return _page(
                "worlds",
                "<h1>The shelf</h1>"
                + _empty(
                    f"no world store at {db}",
                    "uv run ah world build --preset stagflation",
                ),
            )
        c = conn()
        ws = _worlds(c)
        if not ws:
            return _page(
                "worlds",
                "<h1>The shelf</h1>"
                + _empty("the store has no worlds", "uv run ah world build --preset stagflation"),
            )
        reports = {r for r, _ in _battery_reports()}
        rows = []
        for w in ws:
            res = validate(w.doc)
            n_block, n_warn, n_clamp = len(res.blocking), len(res.warnings), len(res.clamps)
            gate = (
                f'<span class="bad">{n_block} blocking</span>'
                if n_block
                else '<span class="ok">V1–V12 clear</span>'
            )
            gate += f' <span class="pill">{n_warn} warn · {n_clamp} clamp</span>'
            runs = _runs(c, w.world_id)
            seeds = sorted({r["seed"] for r in runs})
            ed = w.doc.get("engine_defaults", {})
            batt = (
                f'<a href="/battery/{sorted(reports)[0]}">recorded reports ({len(reports)})</a>'
                if reports
                else '<span class="warn">not run for this world</span>'
            )
            rows.append(
                f'<tr><td class="l"><a href="/world/{_e(w.world_id)}/path">'
                f"{_e((w.doc.get('narrative') or {}).get('title') or w.world_id)}</a><br>"
                f'<span class="prov">{_e(w.world_id)}</span></td>'
                f'<td class="l">{_e(w.spec_version)}</td>'
                f'<td class="l">{_e(w.status)}</td>'
                f'<td class="l">{_e(ed.get("generator_id"))}</td>'
                f"<td>{_e(ed.get('n_paths'))}</td>"
                f'<td class="l">{_e(seeds) if seeds else "—"}</td>'
                f'<td class="l">{_e(w.created_at[:19])}</td>'
                f'<td class="l">{gate}</td>'
                f'<td class="l">{batt}</td>'
                f'<td class="l">{len(runs)} run(s)'
                + "".join(
                    f'<br><a href="/run/{_e(r["run_id"])}">{_e(r["run_id"][:8])}</a>' for r in runs
                )
                + "</td>"
                f'<td class="l"><a href="/world/{_e(w.world_id)}/path">path</a> · '
                f'<a href="/world/{_e(w.world_id)}/ensemble">ensemble</a> · '
                f'<a href="/world/{_e(w.world_id)}/cashflows">cashflows</a></td></tr>'
            )
        body = (
            "<h1>The shelf</h1>"
            f'<div class="prov">Source: {_e(db)} table <code>worlds</code>; coherence recomputed '
            f"live by <code>ah.core.validator.validate</code> (read-only).</div>"
            "<table><tr><th class='l'>world</th><th class='l'>spec</th><th class='l'>status</th>"
            "<th class='l'>generator</th><th>n_paths</th><th class='l'>seeds run</th>"
            "<th class='l'>created</th><th class='l'>coherence gate</th>"
            "<th class='l'>battery</th><th class='l'>runs</th><th class='l'>pages</th></tr>"
            + "".join(rows)
            + "</table>"
        )
        return _page("worlds", body)

    # ----------------------------------------------------------------- path --
    @app.get("/world/{world_id}/path", response_class=HTMLResponse)
    def path_page(world_id: str, seed: int | None = None) -> HTMLResponse:
        c = conn()
        w = _world(c, world_id)
        if w is None:
            return _page(
                "path", _empty(f"no world {world_id}", "uv run ah world build --preset stagflation")
            )
        runs = _runs(c, world_id)
        ed = w.doc.get("engine_defaults", {})
        use_seed = (
            seed if seed is not None else (runs[0]["seed"] if runs else ed.get("base_seed", 0))
        )
        nw = project_numeric(WorldSpec.model_validate(w.doc))
        p = run_path(nw, int(use_seed))

        bands = []
        for ep in (w.doc.get("regimes") or {}).get("sequence") or []:
            bands.append((ep["from_quarter"] * 3, (ep["to_quarter"] + 1) * 3, ep["regime"]))
        markers: list[tuple[int, str]] = []
        for m in range(p.months):
            if p.crisis[m] == 1.0 and (m == 0 or p.crisis[m - 1] == 0.0):
                markers.append((m, "crisis window opens (factor_conditions.crisis_windows[0])"))
            if p.crisis[m] == 0.0 and m and p.crisis[m - 1] == 1.0:
                markers.append((m, "crisis window closes"))

        factors = _line_svg(
            {"policy rate %": p.rate, "inflation %": p.inflation},
            "factor paths — monthly",
            bands=bands,
            markers=markers,
        )
        spread = _line_svg(
            {"HY spread bps": p.spread}, "credit spread — monthly", bands=bands, markers=markers
        )
        liquid = _line_svg(
            {
                a: np.cumprod(1.0 + p.returns[a] / 100.0)
                for a in ("equity", "bonds", "hy", "commodities", "reits")
            },
            "liquid assets — cumulative growth of 1",
            bands=bands,
            markers=markers,
        )

        # two-plane view: reported vs true, with the gap filled
        planes = []
        for s in REPORTED_SLEEVES:
            true_c = np.cumprod(1.0 + p.returns[s] / 100.0)
            rep_c = np.cumprod(1.0 + p.reported[s] / 100.0)
            planes.append(
                "<div>"
                + _line_svg(
                    {f"{s} true": true_c, f"{s} reported": rep_c},
                    f"{s} — two planes, gap filled",
                    bands=bands,
                    fill_between=(f"{s} true", f"{s} reported"),
                )
                + f'<div class="prov">Gap = true − reported. '
                f"terminal true {true_c[-1]:.4f} vs reported {rep_c[-1]:.4f}, "
                f"difference {true_c[-1] - rep_c[-1]:+.4f}. "
                + _src(
                    "source",
                    f"ah.core.engine.run_path(world={world_id}, seed={use_seed}).returns['{s}'] "
                    f"and .reported['{s}']; smoothing weight from structural.smoothing.weights_on_truth",
                )
                + "</div></div>"
            )

        # sanity strip — recomputed by a pure function so a corrupted copy can
        # be fed through the identical code path (README-console.md §Acceptance)
        checks = sanity_rows(p)
        strip_rows = "".join(
            f'<tr><td class="l">{_e(n)}</td><td>{lo:,.4f}</td><td>{hi:,.4f}</td>'
            f"<td>{f0:,.4f}</td><td>{f1:,.4f}</td>"
            f'<td class="l">{"<span class=ok>ok</span>" if not b else f"<span class=bad>{_e(b)}</span>"}</td></tr>'
            for n, lo, hi, f0, f1, b in checks
        )
        n_breach = sum(1 for c in checks if c[5])
        verdict = (
            f'<span class="bad">{n_breach} structural breach(es) — generator defect surfaced</span>'
            if n_breach
            else '<span class="ok">no structural breach</span>'
        )

        body = (
            f"<h1>Decade viewer — {_e((w.doc.get('narrative') or {}).get('title') or world_id)}</h1>"
            f'<div class="prov">world <code>{_e(world_id)}</code> · seed <code>{use_seed}</code> · '
            f"engine <code>{_e(ed.get('generator_id'))}</code> · {p.months} months. "
            + _src(
                "how these numbers were produced",
                f"ah.core.engine.run_path(project_numeric(WorldSpec(worlds[{world_id}].json)), {use_seed}); "
                f"pure function, no store write. Regime bands from regimes.sequence.",
            )
            + "</div>"
            + (
                '<div class="prov">seeds: '
                + " · ".join(
                    f'<a href="/world/{_e(world_id)}/path?seed={r["seed"]}">{r["seed"]}</a>'
                    for r in runs
                )
                + "</div>"
                if runs
                else _empty(
                    "no RunRecord for this world; showing engine_defaults.base_seed",
                    f"uv run ah run {world_id}",
                )
            )
            + "<h2>Sanity strip</h2>"
            + f"<div>{verdict}</div>"
            + "<table><tr><th class='l'>series</th><th>min</th><th>max</th><th>first</th>"
            "<th>last</th><th class='l'>structural check</th></tr>"
            + strip_rows
            + "</table>"
            + '<div class="prov">Floors: policy rate ≥ '
            + f"{RATE_FLOOR_PCT} (engine.py:207), HY spread ≥ {SPREAD_FLOOR_BPS} (engine.py:241), "
            "cumulative growth &gt; 0 for every asset.</div>"
            "<h2>Factor paths and the regime spine</h2>"
            f'<div class="grid"><div>{factors}</div><div>{spread}</div><div>{liquid}</div></div>'
            "<h2>The two planes — reported against true</h2>"
            f'<div class="grid">{"".join(planes)}</div>'
        )
        return _page("path", body)

    # ------------------------------------------------------------- ensemble --
    @app.get("/world/{world_id}/ensemble", response_class=HTMLResponse)
    def ensemble_page(world_id: str, paths: int = 200) -> HTMLResponse:
        c = conn()
        w = _world(c, world_id)
        if w is None:
            return _page(
                "ensemble",
                _empty(f"no world {world_id}", "uv run ah world build --preset stagflation"),
            )
        runs = _runs(c, world_id)
        ed = w.doc.get("engine_defaults", {})
        base = runs[0]["seed"] if runs else ed.get("base_seed", 0)
        declared = int(ed.get("n_paths") or 0)
        n = int(paths)
        nw = project_numeric(WorldSpec.model_validate(w.doc))
        ens = run_ensemble(nw, n, base_seed=int(base))

        note = (
            f'<span class="warn">n={n} is below the world\'s declared ensemble size '
            f"{declared}</span>"
            if declared and n < declared
            else f"n={n}"
        )
        fans = "".join(
            f"<div>{_fan_svg(np.cumprod(1.0 + ens.returns[a] / 100.0, axis=1), f'{a} — cumulative growth')}</div>"
            for a in ASSETS
        )
        terminal = np.array([np.prod(1.0 + ens.returns["equity"][i] / 100.0) for i in range(n)])
        growth = np.cumprod(1.0 + ens.returns["equity"] / 100.0, axis=1)
        peak = np.maximum.accumulate(growth, axis=1)
        dd = 1.0 - growth / peak
        max_dd = dd.max(axis=1)

        # forced-sale incidence needs the institution; bounded to keep the page responsive
        k = min(n, 40)
        forced, secondaries, drought = [], [], []
        for i in range(k):
            r = simulate_play(run_path(nw, int(base) + 7919 * i), None)
            forced.append(r.forced_sale_quarters)
            secondaries.append(r.forced_secondaries)
            dist = np.array([q.distributions_received for q in r.quarters])
            base_rate = float(np.median(dist)) if dist.size else 0.0
            drought.append(float(np.sum(dist < 0.5 * base_rate)) if base_rate > 0 else 0.0)

        body = (
            f"<h1>Ensemble — {_e(world_id)}</h1>"
            f'<div class="prov">seed lineage <code>{base} + 7919·k</code> · {note} · '
            f"{ens.months} months. "
            + _src(
                "how",
                f"ah.core.engine.run_ensemble(project_numeric(world), n_paths={n}, base_seed={base}); "
                f"forced-sale incidence from ah.play.simulate_play over the first {k} seeds "
                f"(bounded for page responsiveness, stated rather than silently truncated).",
            )
            + "</div>"
            "<h2>Fan charts, per asset</h2>"
            f'<div class="grid">{fans}</div>'
            "<h2>Distributions</h2>"
            f'<div class="grid">'
            f"<div>{_hist_svg(terminal, 'equity terminal growth of 1')}</div>"
            f"<div>{_hist_svg(max_dd, 'equity max drawdown (depth)')}</div>"
            f"<div>{_hist_svg(np.array(forced, dtype=float), f'forced-sale quarters per path (first {k} seeds)')}</div>"
            f"<div>{_hist_svg(np.array(drought, dtype=float), f'distribution-drought quarters (first {k} seeds)')}</div>"
            "</div>"
            f'<div class="prov">Forced secondaries across the {k} sampled paths: '
            f"{int(np.sum(secondaries))} total; "
            f"{sum(1 for s in secondaries if s)} of {k} paths had at least one.</div>"
        )
        return _page("ensemble", body)

    # ------------------------------------------------------------ cashflows --
    @app.get("/world/{world_id}/cashflows", response_class=HTMLResponse)
    def cashflows_page(world_id: str, seed: int | None = None) -> HTMLResponse:
        c = conn()
        w = _world(c, world_id)
        if w is None:
            return _page(
                "cashflows",
                _empty(f"no world {world_id}", "uv run ah world build --preset stagflation"),
            )
        runs = _runs(c, world_id)
        ed = w.doc.get("engine_defaults", {})
        use_seed = (
            seed if seed is not None else (runs[0]["seed"] if runs else ed.get("base_seed", 0))
        )
        nw = project_numeric(WorldSpec.model_validate(w.doc))
        p: EnginePaths = run_path(nw, int(use_seed))
        res = simulate_play(p, None)  # the hold-course twin: decision-free ledger

        # recomputed live, by the same pure function the acceptance walk drives
        # a corrupted copy through
        residuals = cash_identity(res.quarters, START_CASH)
        rows, checks_ok, checks_bad = [], 0, 0
        for q, delta in zip(res.quarters, residuals, strict=True):
            ok = abs(delta) < 1e-6
            checks_ok += ok
            checks_bad += not ok
            rows.append(
                f'<tr><td class="l">Q{q.quarter + 1} (m{q.month})</td>'
                f"<td>{q.calls_paid:,.4f}</td><td>{q.distributions_received:,.4f}</td>"
                f"<td>{q.spending_paid:,.4f}</td>"
                f"<td>{'—' if q.forced_sale_total == 0 else f'{q.forced_sale_total:,.4f}'}</td>"
                f"<td>{q.cash:,.4f}</td><td>{q.nav_true:,.4f}</td><td>{q.nav_reported:,.4f}</td>"
                f"<td>{q.unfunded_total:,.4f}</td><td>{q.private_weight_true:,.4f}</td>"
                f'<td class="l">{"<span class=ok>ok</span>" if ok else f"<span class=bad>Δ {delta:+.2e}</span>"}</td>'
                "</tr>"
            )

        sales = (
            "".join(
                f'<tr><td class="l">period {e["period"]}</td><td class="l">{_e(e["kind"])}</td>'
                f"<td>{float(e['amount']):,.4f}</td>"
                f"<td>{format(float(e['haircut']), '.2f') if 'haircut' in e else '—'}</td>"
                f'<td class="l">{_e(e["cause"])}</td></tr>'
                for e in res.sale_log
            )
            or '<tr><td colspan="5" class="l">no forced sale on this path</td></tr>'
        )

        recon = (
            f'<span class="ok">cash identity holds on all {checks_ok} quarters</span>'
            if not checks_bad
            else f'<span class="bad">cash identity FAILS on {checks_bad} of '
            f"{checks_ok + checks_bad} quarters — display or engine disagrees with itself</span>"
        )
        body = (
            f"<h1>Ledger — {_e(world_id)}</h1>"
            f'<div class="prov">seed <code>{use_seed}</code> · hold-course twin (no decisions), '
            f"so the ledger is decision-free and reproducible. "
            + _src(
                "how",
                "ah.play.simulate_play(run_path(world, seed), None) — the Step-3 institution: "
                "cash account, commitment ladder, tier-1 linkage, forced-sale waterfall. "
                "Quarterly resolution is the engine's own (ah.port.engine.PortfolioEngine.run_quarter).",
            )
            + "</div>"
            "<h2>Per-quarter ledger</h2>"
            "<table><tr><th class='l'>quarter</th><th>calls</th><th>distributions</th>"
            "<th>spending</th><th>forced sale</th><th>cash</th><th>NAV true</th>"
            "<th>NAV reported</th><th>unfunded</th><th>private wt</th>"
            "<th class='l'>cash identity</th></tr>" + "".join(rows) + "</table>"
            "<h2>Forced-sale events</h2>"
            "<table><tr><th class='l'>period</th><th class='l'>kind</th><th>amount</th>"
            "<th>haircut</th><th class='l'>cause</th></tr>" + sales + "</table>"
            "<h2>Reconciliation footer</h2>"
            f'<div class="card">{recon}<br>'
            "<span class='prov'>Identity recomputed live from the displayed numbers: "
            "cash<sub>q</sub> = cash<sub>q−1</sub> + distributions − calls − spending + forced-sale proceeds. "
            "Opening cash 2.0 (ah.play.START_CASH). This is the waterfall order in "
            "ah.port.engine.run_quarter; a red row means the table and the engine disagree.</span></div>"
        )
        return _page("cashflows", body)

    # ------------------------------------------------------------------ run --
    @app.get("/run/{run_id}", response_class=HTMLResponse)
    def run_page(run_id: str, replay: int = 0) -> HTMLResponse:
        c = conn()
        recs = [r for r in _runs(c) if r["run_id"] == run_id]
        if not recs:
            return _page("run", _empty(f"no RunRecord {run_id}", "uv run ah run"))
        rec = recs[0]
        sess = c.execute(
            "SELECT session_id, basis, ranked, participant, status, decisions, revealed_months "
            "FROM sessions WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        ).fetchall()

        dec_rows = []
        for s in sess:
            d = json.loads(s["decisions"] or "{}")
            dec_rows.append(
                f'<tr><td class="l">{_e(s["session_id"][:8])}</td><td class="l">{_e(s["basis"])}</td>'
                f'<td class="l">{_e(s["status"])}</td><td>{s["revealed_months"]}</td>'
                f'<td class="l">{_e(json.dumps(d)) if d else "—"}</td>'
                f'<td class="l">{"—" if not d else "cost_charged not stored on this record"}</td></tr>'
            )
        decisions_tbl = (
            "<table><tr><th class='l'>session</th><th class='l'>basis</th><th class='l'>status</th>"
            "<th>revealed</th><th class='l'>decisions (window → verb)</th>"
            "<th class='l'>payload / cost</th></tr>" + "".join(dec_rows) + "</table>"
            if dec_rows
            else _empty(
                "no session has been played against this run, so there is no decision list",
                f"POST /sessions with run_id={run_id} against ah.serve",
            )
        )

        replay_block = (
            f'<div class="card"><a href="/run/{_e(run_id)}?replay=1"><b>Run replay check</b></a>'
            "<div class='prov'>Copies the store to a scratch directory and recomputes the digest "
            "there. The original database is never opened for writing.</div></div>"
        )
        if replay:
            with tempfile.TemporaryDirectory() as tmp:
                scratch = Path(tmp) / "replay.db"
                shutil.copy2(db, scratch)
                from ah.store.runrecords import verify_run  # local: read path only

                sconn = sqlite3.connect(scratch)
                sconn.row_factory = sqlite3.Row
                try:
                    ok = verify_run(sconn, run_id)
                    stored = rec["outputs_digest"]
                    from ah.store.runrecords import compute_outputs_digest
                    from ah.store.worlds import get_world

                    wdoc = get_world(sconn, rec["world_id"])
                    recomputed = (
                        compute_outputs_digest(wdoc, rec["seed"], rec["n_paths"]) if wdoc else "—"
                    )
                finally:
                    sconn.close()
            replay_block = (
                '<div class="card"><b>Replay result: </b>'
                + (
                    '<span class="ok">✔ bit-identical</span>'
                    if ok
                    else '<span class="bad">✘ MISMATCH</span>'
                )
                + f"<table><tr><th class='l'>stored digest</th><td class='l'>{_e(stored)}</td></tr>"
                f"<tr><th class='l'>recomputed</th><td class='l'>{_e(recomputed)}</td></tr></table>"
                "<span class='prov'>Recomputed by ah.store.runrecords.verify_run against a "
                "temporary copy of the store.</span></div>"
            )

        eng = rec.get("resolved_engine") or {}
        body = (
            f"<h1>Run inspector — {_e(run_id[:8])}</h1>"
            f'<div class="prov">Source: table <code>run_records</code> in {_e(db)}. '
            + _src("full record", json.dumps(dict(rec), default=str)[:1200])
            + "</div>"
            "<table>"
            f"<tr><th class='l'>run_id</th><td class='l'>{_e(rec['run_id'])}</td></tr>"
            f"<tr><th class='l'>world</th><td class='l'><a href=\"/world/{_e(rec['world_id'])}/path\">"
            f"{_e(rec['world_id'])}</a></td></tr>"
            f"<tr><th class='l'>seed / n_paths</th><td class='l'>{rec['seed']} / {rec['n_paths']}</td></tr>"
            f"<tr><th class='l'>engine</th><td class='l'>{_e(eng.get('generator_id'))} "
            f"{_e(eng.get('generator_version'))}</td></tr>"
            f"<tr><th class='l'>validator / battery</th><td class='l'>{_e(eng.get('validator_version'))}"
            f" / {_e(eng.get('battery_version'))}</td></tr>"
            f"<tr><th class='l'>digest</th><td class='l'>{_e(rec['outputs_digest'])}</td></tr>"
            f"<tr><th class='l'>decision_alpha_version</th><td class='l'>"
            f"{_e(rec.get('decision_alpha_version') or 'not stamped on this record')}</td></tr>"
            f"<tr><th class='l'>twin_definition</th><td class='l'>"
            f"{_e(rec.get('twin_definition') or 'not stamped on this record')}</td></tr>"
            "</table>"
            "<h2>Decisions as stored</h2>"
            + decisions_tbl
            + "<h2>The three series</h2>"
            + _empty(
                "player / policy twin / drift twin are computed by the session service at "
                "outcome time and are not stored on the RunRecord. The drift twin is null by "
                "contract in ah.serve (its slot exists before its data)",
                f"GET /sessions/<sid>/outcome on ah.serve for a completed session of run {run_id}",
            )
            + "<h2>Replay</h2>"
            + replay_block
        )
        return _page("run", body)

    # -------------------------------------------------------------- battery --
    @app.get("/battery/{report_id}", response_class=HTMLResponse)
    def battery_page(report_id: str) -> HTMLResponse:
        wanted = dict(_battery_reports())
        if report_id not in wanted:
            listing = "".join(
                f'<li><a href="/battery/{_e(k)}">{_e(k.replace("~", "/"))}</a></li>'
                for k in sorted(wanted)
            )
            return _page(
                "battery",
                "<h1>Evidence viewer</h1>"
                + (
                    f"<div class='card'><b>Recorded reports on disk</b><ul>{listing}</ul></div>"
                    if listing
                    else _empty(
                        "no recorded battery report found under artifacts/ or experiments/",
                        "uv run python scripts/run_bootstrap_battery.py",
                    )
                ),
            )
        doc = json.loads(wanted[report_id].read_text(encoding="utf-8"))
        tiers = (doc.get("unfiltered") or {}).get("tiers") or {}
        rows = []
        for tname, entries in tiers.items():
            for e in entries:
                sev = e.get("severity")
                status = e.get("status")
                band = e.get("band") or {}
                if sev == "enforce":
                    rat = '<span class="ok">pre-registered (enforce)</span>'
                elif sev == "report":
                    rat = '<span class="warn">report severity — descriptive, not a gate</span>'
                else:
                    rat = '<span class="warn">unclassified</span>'
                if status == "structurally_unavailable":
                    rat = '<span class="warn">structurally unavailable</span>'
                passed = e.get("passed")
                verdict = (
                    '<span class="ok">pass</span>'
                    if passed is True
                    else '<span class="bad">fail</span>'
                    if passed is False
                    else "—"
                )
                margin = band.get("band_distance")
                rows.append(
                    f'<tr><td class="l">{_e(tname)}</td><td class="l">{_e(e.get("suite"))}</td>'
                    f'<td class="l">{_e(e.get("name"))}</td><td>{_e(e.get("value"))}</td>'
                    f'<td class="l">{_e(band.get("lo"))} … {_e(band.get("hi"))}</td>'
                    f"<td>{'' if margin is None else f'{float(margin):+.5f}'}</td>"
                    f'<td class="l">{verdict}</td><td class="l">{rat}</td></tr>'
                )
        enforce_n = sum(1 for t in tiers.values() for e in t if e.get("severity") == "enforce")
        body = (
            f"<h1>Evidence viewer — {_e(report_id.replace('~', '/'))}</h1>"
            f'<div class="prov">battery <code>{_e(doc.get("battery_version"))}</code> · system '
            f"<code>{_e(doc.get('system_id'))}</code> · vintage <code>{_e(doc.get('vintage_id'))}</code> · "
            f"seed <code>{_e(doc.get('seed'))}</code><br>"
            f"prereg digest <code>{_e(doc.get('prereg_digest'))}</code> · "
            f"verified <b>{_e(doc.get('prereg_verified'))}</b> · "
            f"criterion-bearing <b>{_e(doc.get('criterion_bearing'))}</b></div>"
            f'<div class="card">No aggregate pass/fail badge is shown. The enforce surface of this '
            f"report is {enforce_n} metric(s); every other row is <b>descriptive</b>. "
            f"The per-gate table below is the truth.</div>"
            "<table><tr><th class='l'>tier</th><th class='l'>suite</th><th class='l'>metric</th>"
            "<th>value</th><th class='l'>band</th><th>margin</th><th class='l'>verdict</th>"
            "<th class='l'>ratification</th></tr>"
            + "".join(rows[:400])
            + "</table>"
            + (
                f'<div class="prov">Showing first 400 of {len(rows)} rows.</div>'
                if len(rows) > 400
                else ""
            )
        )
        return _page("battery", body)

    # ----------------------------------------------------------------- diff --
    @app.get("/diff", response_class=HTMLResponse)
    def diff_page() -> HTMLResponse:
        return _page(
            "diff",
            "<h1>World comparison</h1>"
            + _empty(
                "NOT BUILT. The stretch page was descoped so the six core pages could be "
                "finished and verified against real output. Nothing here is stubbed or faked — "
                "the page simply does not exist yet",
                "not applicable — this is unbuilt work, not missing data",
            ),
        )

    return app


app = create_app()
