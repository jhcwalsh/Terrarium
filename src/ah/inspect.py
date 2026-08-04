"""The ``--inspect`` renderer (wp5-02; MPP-A1's build item, labeled WP2R.4 there).

ONE code path: any RunRecord id -> a static, self-contained HTML figure page.
The page is derived from the RunRecord ALONE: the ensemble is REGENERATED from
the stored world + seed + n_paths (exactly :func:`ah.store.runrecords.verify_run`'s
path) and the recomputed digest is compared against the stored one on every
render -- so a figure page is simultaneously a reproducibility check, which is
the property wp5-07's appendix ("every figure regenerable from a RunRecord id")
needs. No separate state is read or written.

Panels (the kickoff's list, verbatim): factor panel (per-asset fan of
cumulative growth percentiles), sleeve panel (the hold-course twin's value and
weights), reported-vs-true toggle (the smoothed sleeves' two return series),
episode annotations (the world's regime sequence, plus the narrative
dispatches -- this module is a DISPLAY surface, where narrative reads are
allowed; the blindness invariant restricts the engine and institution only),
and a correlogram (pooled monthly-return correlations).

Rendering follows ``scripts/build_artifact.py``'s precedent: inline SVG built
in pure Python, zero new dependencies, no external assets (self-contained by
construction). Deterministic: two renders of the same RunRecord are
byte-identical (no clocks; the only timestamp shown is the record's own
``created_at``).
"""

from __future__ import annotations

import html
import sqlite3
from typing import Any

import numpy as np

from ah.core.digest import digest_ensemble
from ah.core.engine import ASSETS, REPORTED_SLEEVES, EnsembleResult, run_ensemble
from ah.core.institution import SLEEVES, InstitutionResult, hold_course_twin
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.store.runrecords import get_run_record
from ah.store.worlds import get_world

__all__ = ["InspectError", "render_inspect_page"]

# Deliberately small and mechanical: distinct fills for regime strips and sleeve
# weight bands, assigned by position, stable across renders.
_PALETTE = (
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
)

_W, _H = 640, 220  # per-chart viewbox
_PL, _PR, _PT, _PB = 46, 10, 10, 22  # plot paddings


class InspectError(RuntimeError):
    """A RunRecord that cannot be rendered (missing record, missing world)."""


# --------------------------------------------------------------------------- #
# small SVG helpers (pure string assembly; float formatting fixed at 2dp
# coordinates so output is byte-stable)
# --------------------------------------------------------------------------- #


def _f(v: float) -> str:
    return f"{v:.2f}"


def _x(i: int, n: int) -> float:
    return _PL + (_W - _PL - _PR) * (i / max(n - 1, 1))


def _y(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return _H - _PB
    return _PT + (_H - _PT - _PB) * (1.0 - (v - lo) / (hi - lo))


def _polyline(ys: np.ndarray, lo: float, hi: float, cls: str) -> str:
    n = ys.shape[0]
    pts = " ".join(f"{_f(_x(i, n))},{_f(_y(float(ys[i]), lo, hi))}" for i in range(n))
    return f'<polyline points="{pts}" class="{cls}"/>'


def _band(lo_ys: np.ndarray, hi_ys: np.ndarray, lo: float, hi: float, cls: str) -> str:
    n = lo_ys.shape[0]
    fwd = [f"{_f(_x(i, n))},{_f(_y(float(hi_ys[i]), lo, hi))}" for i in range(n)]
    bwd = [f"{_f(_x(i, n))},{_f(_y(float(lo_ys[i]), lo, hi))}" for i in reversed(range(n))]
    return f'<polygon points="{" ".join(fwd + bwd)}" class="{cls}"/>'


def _axes(lo: float, hi: float, months: int) -> str:
    parts = []
    for v in (lo, (lo + hi) / 2.0, hi):
        y = _y(v, lo, hi)
        parts.append(
            f'<line x1="{_PL}" y1="{_f(y)}" x2="{_W - _PR}" y2="{_f(y)}" class="grid"/>'
            f'<text x="{_PL - 4}" y="{_f(y + 3)}" class="ylab">{v:.2f}</text>'
        )
    for m in range(0, months, 24):
        x = _x(m, months)
        parts.append(f'<text x="{_f(x)}" y="{_H - 6}" class="xlab">m{m}</text>')
    return "".join(parts)


def _svg(body: str, title: str) -> str:
    return (
        f"<figure><figcaption>{html.escape(title)}</figcaption>"
        f'<svg viewBox="0 0 {_W} {_H}" role="img">{body}</svg></figure>'
    )


def _regime_strip(segments: list[dict[str, Any]], months: int) -> str:
    """The episode-annotation strip: regime sequence segments as colored bands."""
    if not segments:
        return ""
    names = sorted({str(s["regime"]) for s in segments})
    color = {name: _PALETTE[i % len(_PALETTE)] for i, name in enumerate(names)}
    parts = []
    for seg in segments:
        m0 = int(seg["from_quarter"]) * 3
        m1 = min((int(seg["to_quarter"]) + 1) * 3, months)
        if m1 <= m0:
            continue
        x0, x1 = _x(m0, months), _x(min(m1, months - 1), months)
        parts.append(
            f'<rect x="{_f(x0)}" y="{_PT}" width="{_f(max(x1 - x0, 1.0))}" '
            f'height="{_H - _PT - _PB}" fill="{color[str(seg["regime"])]}" opacity="0.85">'
            f"<title>{html.escape(str(seg['regime']))} q{seg['from_quarter']}-q{seg['to_quarter']}</title></rect>"
        )
    legend = " ".join(
        f'<tspan fill="{color[name]}">&#9632;</tspan> {html.escape(name)}' for name in names
    )
    parts.append(f'<text x="{_PL}" y="{_H - 6}" class="xlab">{legend}</text>')
    return _svg("".join(parts), "Episode annotations: regime sequence")


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #


def _cumulative(returns: np.ndarray) -> np.ndarray:
    """(n_paths, NM) engine PERCENT returns -> (n_paths, NM) growth of 1.0.

    The divide-by-100 lives here because every caller feeds engine output,
    which is in percent (the same live-found scale bug as the bundle bands:
    compounding percent as decimal renders empty/negative cones).
    """
    return np.cumprod(1.0 + returns / 100.0, axis=1)


def _factor_panel(ensemble: EnsembleResult) -> str:
    parts = []
    for asset in ASSETS:
        growth = _cumulative(ensemble.returns[asset])
        p5, p25, p50, p75, p95 = (np.percentile(growth, q, axis=0) for q in (5, 25, 50, 75, 95))
        lo = float(min(p5.min(), 0.9))
        hi = float(p95.max() * 1.02)
        body = (
            _axes(lo, hi, growth.shape[1])
            + _band(p5, p95, lo, hi, "band905")
            + _band(p25, p75, lo, hi, "band50")
            + _polyline(p50, lo, hi, "median")
        )
        parts.append(_svg(body, f"{asset}: growth of 1.0 (p5-p95, p25-p75, median)"))
    return "".join(parts)


def _sleeve_panel(twin: InstitutionResult) -> str:
    total = twin.total
    lo = float(min(total.min() * 0.98, 90.0))
    hi = float(total.max() * 1.02)
    months = total.shape[0]
    value_body = _axes(lo, hi, months) + _polyline(total, lo, hi, "median")
    out = _svg(value_body, "Hold-course twin: portfolio value (growth of 100)")

    # stacked weights: cumulative sums bottom-up, one band per sleeve
    weights = twin.weights  # (NM, n_sleeves)
    cum = np.cumsum(weights, axis=1)
    base = np.zeros(months)
    bands = []
    for j, sleeve in enumerate(SLEEVES):
        top = cum[:, j]
        n = months
        fwd = [f"{_f(_x(i, n))},{_f(_y(float(top[i]), 0.0, 1.0))}" for i in range(n)]
        bwd = [f"{_f(_x(i, n))},{_f(_y(float(base[i]), 0.0, 1.0))}" for i in reversed(range(n))]
        color = _PALETTE[j % len(_PALETTE)]
        bands.append(
            f'<polygon points="{" ".join(fwd + bwd)}" fill="{color}" opacity="0.8">'
            f"<title>{html.escape(sleeve)}</title></polygon>"
        )
        base = top
    legend = " ".join(
        f'<tspan fill="{_PALETTE[j % len(_PALETTE)]}">&#9632;</tspan> {html.escape(s)}'
        for j, s in enumerate(SLEEVES)
    )
    weights_body = "".join(bands) + f'<text x="{_PL}" y="{_H - 6}" class="xlab">{legend}</text>'
    out += _svg(weights_body, "Hold-course twin: sleeve weights (stacked)")
    return out


def _reported_true_panel(ensemble: EnsembleResult) -> str:
    """The toggle: true vs reported cumulative growth for the smoothed sleeves.

    Pure-CSS toggle (a checkbox the stylesheet reads); path 0 of the ensemble,
    which is the seed the RunRecord names first.
    """
    parts = [
        '<input type="checkbox" id="rt" checked><label for="rt"> show reported '
        "(smoothed) alongside true</label>"
    ]
    for sleeve in REPORTED_SLEEVES:
        true_g = _cumulative(ensemble.returns[sleeve][:1])[0]
        rep_g = _cumulative(ensemble.reported[sleeve][:1])[0]
        lo = float(min(true_g.min(), rep_g.min()) * 0.98)
        hi = float(max(true_g.max(), rep_g.max()) * 1.02)
        months = true_g.shape[0]
        body = (
            _axes(lo, hi, months)
            + _polyline(true_g, lo, hi, "median")
            + _polyline(rep_g, lo, hi, "reported")
        )
        parts.append(_svg(body, f"{sleeve}: true (solid) vs reported (dashed), path 0"))
    return "".join(parts)


def _correlogram(ensemble: EnsembleResult) -> str:
    n = len(ASSETS)
    pooled = np.stack([ensemble.returns[a].reshape(-1) for a in ASSETS])  # (n_assets, paths*months)
    corr = np.corrcoef(pooled)
    cell = (_W - _PL - _PR) / n
    ch = (_H - _PT - _PB) / n
    parts = []
    for i in range(n):
        for j in range(n):
            v = float(corr[i, j])
            # blue (-1) .. white (0) .. red (+1), mechanical
            r = int(255 * max(v, 0.0) + 255 * (1 - abs(v)) * 0.9)
            b = int(255 * max(-v, 0.0) + 255 * (1 - abs(v)) * 0.9)
            g = int(255 * (1 - abs(v)) * 0.9)
            x0, y0 = _PL + j * cell, _PT + i * ch
            parts.append(
                f'<rect x="{_f(x0)}" y="{_f(y0)}" width="{_f(cell)}" height="{_f(ch)}" '
                f'fill="rgb({r},{g},{b})"/>'
                f'<text x="{_f(x0 + cell / 2)}" y="{_f(y0 + ch / 2 + 3)}" class="cell">{v:.2f}</text>'
            )
    for i, a in enumerate(ASSETS):
        parts.append(
            f'<text x="{_PL - 4}" y="{_f(_PT + i * ch + ch / 2 + 3)}" class="ylab">'
            f"{html.escape(a)}</text>"
            f'<text x="{_f(_PL + i * cell + cell / 2)}" y="{_H - 6}" class="xlab">'
            f"{html.escape(a)}</text>"
        )
    return _svg("".join(parts), "Correlogram: pooled monthly-return correlations")


def _dispatches(world_doc: dict[str, Any]) -> str:
    """Narrative dispatches -- DISPLAY ONLY, and this is a display surface."""
    dispatches = (world_doc.get("narrative") or {}).get("dispatches") or []
    if not dispatches:
        return "<p>(world carries no dispatches)</p>"
    items = "".join(
        f"<li><b>{html.escape(str(d.get('date', '')))}</b> "
        f"{html.escape(str(d.get('headline', '')))}"
        + (f" &mdash; {html.escape(str(d['detail']))}" if d.get("detail") else "")
        + "</li>"
        for d in dispatches
    )
    return f"<ul>{items}</ul>"


_CSS = """
body{font:14px/1.45 system-ui,sans-serif;margin:24px auto;max-width:720px;color:#222}
h1{font-size:20px} h2{font-size:16px;margin-top:28px}
figure{margin:12px 0} figcaption{font-size:12px;color:#555;margin-bottom:2px}
svg{width:100%;height:auto;background:#fafafa;border:1px solid #e5e5e5}
.grid{stroke:#ddd;stroke-width:1} .ylab{font-size:9px;text-anchor:end;fill:#666}
.xlab{font-size:9px;fill:#666} .cell{font-size:7px;text-anchor:middle;fill:#333}
.median{fill:none;stroke:#1a4f8b;stroke-width:1.6}
.reported{fill:none;stroke:#c2571a;stroke-width:1.4;stroke-dasharray:5 3}
.band905{fill:#1a4f8b;opacity:0.12} .band50{fill:#1a4f8b;opacity:0.22}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;color:#fff;font-size:12px}
.ok{background:#2e7d32} .bad{background:#c62828}
table.meta{border-collapse:collapse;font-size:13px}
table.meta td{border:1px solid #e0e0e0;padding:3px 8px}
#rt:not(:checked)~figure .reported{display:none}
input#rt{margin-right:4px}
"""


def render_inspect_page(conn: sqlite3.Connection, run_id: str) -> str:
    """Regenerate ``run_id``'s ensemble from its stored inputs and render the page.

    Raises :class:`InspectError` for a missing record or world. A digest
    mismatch does NOT raise: the page renders with a loud MISMATCH badge,
    because "this stored run no longer reproduces" is exactly what an
    inspection exists to surface.
    """
    rec = get_run_record(conn, run_id)
    if rec is None:
        raise InspectError(f"no run_record with run_id={run_id}")
    world_doc = get_world(conn, rec["world_id"])
    if world_doc is None:
        raise InspectError(f"run {run_id} references missing world {rec['world_id']}")

    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    ensemble = run_ensemble(nw, rec["n_paths"], base_seed=rec["seed"])
    recomputed = digest_ensemble(ensemble)
    verified = recomputed == rec["outputs_digest"]
    twin = hold_course_twin(nw, rec["seed"])

    regimes = world_doc.get("regimes") or {}
    segments = regimes.get("sequence") or []
    months = ensemble.months

    badge = (
        '<span class="badge ok">DIGEST VERIFIED</span>'
        if verified
        else '<span class="badge bad">DIGEST MISMATCH &mdash; stored run does not reproduce</span>'
    )
    narrative = world_doc.get("narrative") or {}
    title = str(narrative.get("title") or rec["world_id"])
    engine = rec["resolved_engine"]

    meta_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td><code>{html.escape(str(v))}</code></td></tr>"
        for k, v in (
            ("run_id", run_id),
            ("world_id", rec["world_id"]),
            ("generator", f"{engine.get('generator_id')} / {engine.get('generator_version')}"),
            ("validator", engine.get("validator_version")),
            ("seed / n_paths", f"{rec['seed']} / {rec['n_paths']}"),
            ("outputs_digest (stored)", rec["outputs_digest"]),
            ("outputs_digest (recomputed)", recomputed),
            ("created_at", rec["created_at"]),
            (
                "decision stamps",
                f"schema {rec.get('decision_schema_version')} / "
                f"alpha {rec.get('decision_alpha_version')} / twin {rec.get('twin_definition')}",
            ),
        )
    )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>inspect {html.escape(run_id[:8])} &mdash; {html.escape(title)}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"<h1>Run inspection &mdash; {html.escape(title)}</h1>"
        f"<p>{badge}</p><table class='meta'>{meta_rows}</table>"
        "<h2>Episode annotations</h2>"
        + _regime_strip(segments, months)
        + _dispatches(world_doc)
        + "<h2>Factor panel</h2>"
        + _factor_panel(ensemble)
        + "<h2>Sleeve panel (hold-course twin)</h2>"
        + _sleeve_panel(twin)
        + "<h2>Reported vs true (smoothed sleeves)</h2>"
        + _reported_true_panel(ensemble)
        + "<h2>Correlogram</h2>"
        + _correlogram(ensemble)
        + "</body></html>"
    )
