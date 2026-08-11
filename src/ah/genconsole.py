"""The generator console (port 8797) — watch a decade get built, layer by layer.

Read-only, internal console family (hub 8795, data 8796, THIS 8798-adjacent
slot, build 8798, QA 8799). Two instruments:

* a four-stage step-through of ONE hier-flow decade — climate, seasons,
  weather, joinery — from the campaign-2 checkpoints (hash-verified), and
* an artifact-based monitor of live campaign runs under ``experiments/``.

RECORDED DEPENDENCY: this module consumes the joinery's per-decade private
classes (``_DecadeFactory``) and module-level filter helpers READ-ONLY. A
generator refactor may break this console; the console must never push back
on the generator. Nothing in ``ah/gen/`` is edited, and nothing shown here
is a score.

Run:  uv run uvicorn ah.genconsole:app --port 8797
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECKPOINT_MANIFEST = _REPO_ROOT / "configs" / "campaign2-checkpoints.json"

StageEvent = tuple[str, dict[str, Any]]

#: step-through stage order — the DN-1.1 layer names
STAGES: tuple[str, ...] = ("climate", "seasons", "weather", "joinery")


def _rle(labels: list[str]) -> list[dict[str, Any]]:
    """Run-length encode a label path into spells."""
    spells: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        if spells and spells[-1]["label"] == label:
            spells[-1]["months"] += 1
        else:
            spells.append({"label": label, "start": i, "months": 1})
    return spells


def build_decade(
    seed: int,
    checkpoint_index: int,
    *,
    on_stage: Callable[[str, dict[str, Any]], None],
    block_batch: int = 16,
    device: str = "cpu",
    sampler_override: Any = None,
) -> dict[str, Any]:
    """Build ONE decade through the real four layers, emitting each stage.

    Assembly mirrors ``campaign2_promotion._build_campaign_flow`` exactly:
    checkpoint hash verified against the committed campaign manifest, climate
    and regimes artifacts checked against the WP2.7 sha pins. Any pin
    mismatch raises ``ValueError`` — the app layer renders it as a page
    error; there is no fallback checkpoint. Deterministic: the platform seed
    rule makes this decade bit-identical to decade 0 of a batched ensemble
    with the same base seed.
    """
    import torch

    from ah.gen.blocks.flow import FlowBlockSampler, load_checkpoint
    from ah.gen.bootstrap import CAMPAIGN2_VINTAGE_ID, campaign_source
    from ah.gen.climate.model import STATE_NAMES
    from ah.gen.climate.simulate import load_artifact as load_climate
    from ah.gen.joinery import assemble as ja
    from ah.gen.joinery import support as sp
    from ah.gen.joinery import waypoints as wpts
    from ah.gen.regimes.semimarkov import REGIME_LABELS
    from ah.gen.regimes.semimarkov import load_artifact as load_regimes

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    manifest_doc = json.loads(_CHECKPOINT_MANIFEST.read_text("utf-8"))
    key = f"flow:{checkpoint_index}"
    entry = manifest_doc.get(key)
    if entry is None:
        raise ValueError(f"no campaign checkpoint manifest entry for {key}")
    model, std, meta = load_checkpoint(_REPO_ROOT / entry["checkpoint"])
    if meta["checkpoint_hash"] != entry["checkpoint_hash"]:
        raise ValueError(
            f"checkpoint hash mismatch for {key}: manifest "
            f"{entry['checkpoint_hash'][:16]}..., loaded {meta['checkpoint_hash'][:16]}..."
        )
    # CAMPAIGN-2 layer pins: this whole path is a campaign-2 checkpoint replay
    # (the manifest above is campaign2-checkpoints.json), so it names the
    # frozen pins -- the live ja.PINNED_* moved to campaign-3 at
    # AM-2026-08-10-001 and would refuse these checkpoints' lineage.
    climate = load_climate(ja.CAMPAIGN2_DEFAULT_CLIMATE_ARTIFACT)
    regimes = load_regimes(ja.CAMPAIGN2_DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != ja.CAMPAIGN2_PINNED_CLIMATE_SHA256:
        raise ValueError("climate artifact sha256 != WP2.7 pin")
    if regimes.meta["content_sha256"] != ja.CAMPAIGN2_PINNED_REGIMES_SHA256:
        raise ValueError("regimes artifact sha256 != WP2.7 pin")

    # A campaign-2 checkpoint replay: the vintage is pinned to the record the
    # checkpoint was trained against, not the live campaign default -- the
    # trained feature dimensions are a fact about that vintage.
    source = campaign_source(vintage_id=CAMPAIGN2_VINTAGE_ID)
    sampler = sampler_override or FlowBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device=device,
        block_batch=block_batch,
    )
    config = ja.JoineryConfig()
    stats = wpts.source_stats(source, climate)
    support_ref = sp.build_support_reference(source, climate, quantile=config.support_quantile)
    factory = ja._DecadeFactory(
        climate=climate,
        regimes_artifact=regimes,
        source=source,
        stats=stats,
        support_ref=support_ref,
        sampler=sampler,
        config=config,
        months=120,
        seed=seed,
        world=None,
        guidance=None,
    )

    prep = factory.prepare(0)
    months = list(range(prep.sim.months))
    on_stage(
        "climate",
        {
            "months": months,
            "states": {
                name: [float(v) for v in prep.sim.states[0, :, i]]
                for i, name in enumerate(STATE_NAMES)
            },
            "theta_index": int(prep.sim.theta_index[0]),
        },
    )

    labels = [str(REGIME_LABELS[int(c)]) for c in prep.waypoints.labels]
    on_stage("seasons", {"labels": labels, "durations": _rle(labels)})

    result = factory.assemble([prep])[0]
    names = list(source.factor_names)
    block_starts = list(range(0, len(months), config.block_months))
    on_stage(
        "weather",
        {
            "block_months": int(config.block_months),
            "factors": {
                name: [float(v) for v in result.path[:, i]] for i, name in enumerate(names)
            },
            "blocks": [{"start": s, "regime": labels[s]} for s in block_starts],
        },
    )

    filter_stats: dict[str, dict[str, dict[str, float]]] = {}
    for name in ja.FILTER_FACTORS:
        if name not in names:
            continue
        col = names.index(name)
        filter_stats[name] = {
            metric: {
                "decade": float(ja._FILTER_FUNCS[metric](result.path[:, col])),
                "historical": float(ja._FILTER_FUNCS[metric](source.values[:, col])),
            }
            for metric in ja.FILTER_METRICS
        }
    on_stage(
        "joinery",
        {
            "reconciliation": result.reconciliation.summary(),
            "filter_stats": filter_stats,
            "filter_note": (
                "accept/reject is an ensemble-relative decision over many decades; "
                "a single decade has statistics, not a verdict"
            ),
        },
    )

    return {
        "months": len(months),
        "checkpoint_hash": str(meta["checkpoint_hash"]),
        "stages": list(STAGES),
    }


def scan_runs(experiments_root: Path) -> list[dict[str, Any]]:
    """Campaign runs as the artifacts on disk tell them, newest first.

    Every filesystem read is fallible by design (cells vanish, JSON is
    mid-write): failures become states ("unreadable"), never exceptions.
    """
    campaigns: list[dict[str, Any]] = []
    try:
        campaign_dirs = [d for d in experiments_root.iterdir() if (d / "cells").is_dir()]
    except OSError:
        return []
    campaign_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    for cdir in campaign_dirs:
        cells: list[dict[str, Any]] = []
        try:
            cell_dirs = sorted((cdir / "cells").iterdir())
        except OSError:
            continue
        for cell_dir in cell_dirs:
            if not cell_dir.is_dir():
                continue
            row: dict[str, Any] = {"slug": cell_dir.name, "status": "running"}
            summary_path = cell_dir / "summary.json"
            if summary_path.exists():
                try:
                    summary = json.loads(summary_path.read_text("utf-8"))
                    row.update(
                        {
                            "status": "done",
                            "system_id": summary.get("system_id"),
                            "seed_index": summary.get("seed_index"),
                            "timings": summary.get("timings", {}),
                            "criterion_bearing": summary.get("criterion_bearing"),
                            "passed_unfiltered": summary.get("passed_unfiltered"),
                        }
                    )
                except (OSError, ValueError):
                    row["status"] = "unreadable"
            cells.append(row)
        campaigns.append({"campaign": cdir.name, "cells": cells})
    return campaigns


# --------------------------------------------------------------------------- #
# the app
# --------------------------------------------------------------------------- #

import html  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

WATERMARK = "GENERATOR CONSOLE - how a decade gets built; nothing here is a score"

_CSS = """
body{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#fafafa;color:#222}
nav{background:#1a237e;padding:8px 16px}nav a{color:#fff;margin-right:16px;text-decoration:none}
.wm{background:#fff3cd;padding:4px 16px;font-size:12px;color:#664d03}
main{padding:16px;max-width:1080px}
table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;padding:3px 8px;font-size:13px}
.stage{background:#fff;border:1px solid #ddd;border-radius:6px;padding:12px;margin:12px 0}
.ribbon{display:flex;height:28px}.ribbon div{flex:1}
.err{background:#f8d7da;padding:8px;border-radius:4px}
.small{font-size:12px;color:#555}
form{background:#fff;border:1px solid #ddd;padding:12px;border-radius:6px;display:inline-block}
.done{color:#0a6e0a}.running{color:#b36b00}.unreadable{color:#a00}
"""

_REGIME_COLORS = {
    "EXP": "#7dc87d",
    "SLOW": "#e6d97a",
    "REC": "#e8a44a",
    "CRI": "#d9534f",
    "STAG": "#a678c8",
    "REF": "#6fa8dc",
}


def _e(x: Any) -> str:
    return html.escape(str(x))


def _page(title: str, body: str, *, refresh: int | None = None) -> HTMLResponse:
    meta = f"<meta http-equiv='refresh' content='{refresh}'>" if refresh else ""
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{_e(title)}</title>"
        f"{meta}<style>{_CSS}</style></head><body>"
        f'<div class="wm">{_e(WATERMARK)}</div>'
        f'<nav><a href="/">build a decade</a><a href="/runs">live runs</a>'
        f'<a href="http://127.0.0.1:8795/">hub (8795)</a></nav>'
        f"<main>{body}</main></body></html>"
    )


def _poly_svg(series: list[float], *, title: str, width: int = 560, height: int = 120) -> str:
    if not series:
        return f"<p class='small'>{_e(title)}: no data</p>"
    lo, hi = min(series), max(series)
    span = (hi - lo) or 1.0
    pts = " ".join(
        f"{i * width / max(1, len(series) - 1):.1f},{height - (v - lo) / span * height:.1f}"
        for i, v in enumerate(series)
    )
    return (
        f"<div><b class='small'>{_e(title)}</b> "
        f"<span class='small'>[{lo:.4g} .. {hi:.4g}]</span><br>"
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
        f"<rect width='{width}' height='{height}' fill='#fff' stroke='#ddd'/>"
        f"<polyline points='{pts}' fill='none' stroke='#1a237e' stroke-width='1'/></svg></div>"
    )


def _ribbon_svg(labels: list[str]) -> str:
    cells = "".join(
        f"<div style='background:{_REGIME_COLORS.get(label, '#ccc')}' title='{_e(label)} m{i}'></div>"
        for i, label in enumerate(labels)
    )
    legend = " ".join(
        f"<span style='background:{c};padding:1px 6px'>{_e(name)}</span>"
        for name, c in _REGIME_COLORS.items()
    )
    return f"<div class='ribbon'>{cells}</div><p class='small'>{legend}</p>"


#: run records: run_id -> {"stages": [(name, payload)], "error", "done", "summary"}
_RUNS: dict[str, dict[str, Any]] = {}
_RUNS_LOCK = threading.Lock()
_RUN_COUNTER = 0
_MAX_RUNS = 8

#: test seam: when set, passed straight through to build_decade
TESTING_SAMPLER: Any = None

app = FastAPI(title="generator console")


def _start_run(seed: int, checkpoint: int) -> str:
    global _RUN_COUNTER
    with _RUNS_LOCK:
        _RUN_COUNTER += 1
        run_id = f"{seed}-{checkpoint}-{_RUN_COUNTER}"
        _RUNS[run_id] = {"stages": [], "error": None, "done": False, "summary": None}
        while len(_RUNS) > _MAX_RUNS:
            _RUNS.pop(next(iter(_RUNS)))

    def work() -> None:
        record = _RUNS.get(run_id)
        if record is None:
            return
        try:
            summary = build_decade(
                seed,
                checkpoint,
                on_stage=lambda name, payload: record["stages"].append((name, payload)),
                sampler_override=TESTING_SAMPLER,
            )
            record["summary"] = summary
        except Exception as exc:  # a pin mismatch is a page error, never a 500
            record["error"] = str(exc)
        finally:
            record["done"] = True

    threading.Thread(target=work, daemon=True).start()
    return run_id


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    body = (
        "<h1>Build a decade</h1>"
        "<p>One decade, the real four layers, the campaign-2 checkpoint "
        "(hash-verified). Same seed, same page - always.</p>"
        "<form method='get' action='/decade/start'>"
        "seed <input name='seed' type='number' value='0'> "
        "checkpoint <select name='checkpoint'><option>0</option><option>1</option>"
        "<option>2</option></select> "
        "<button type='submit'>build</button></form>"
    )
    return _page("generator console", body)


class DecadeRequest(BaseModel):
    seed: int = 0
    checkpoint: int = 0


@app.get("/decade/start", response_class=HTMLResponse)
def start_decade(seed: int = 0, checkpoint: int = 0) -> HTMLResponse:
    """Form target. A side-effecting GET is tolerated on this internal console
    because HTML forms cannot POST without the python-multipart dependency,
    which is not in the plan's dependency budget."""
    run_id = _start_run(seed, checkpoint)
    return HTMLResponse(status_code=303, headers={"Location": f"/decade/{run_id}"}, content="")


@app.post("/api/decade")
def api_start(req: DecadeRequest) -> JSONResponse:
    return JSONResponse({"run_id": _start_run(req.seed, req.checkpoint)})


@app.get("/api/decade/{run_id}")
def api_run(run_id: str) -> JSONResponse:
    record = _RUNS.get(run_id)
    if record is None:
        raise HTTPException(404, "no such run")
    return JSONResponse(
        {
            "done": record["done"],
            "error": record["error"],
            "stages": [name for name, _ in record["stages"]],
            "summary": record["summary"],
        }
    )


def _render_stage(name: str, payload: dict[str, Any]) -> str:
    if name == "climate":
        charts = "".join(
            _poly_svg(series, title=f"L1 slow state: {state}")
            for state, series in payload["states"].items()
        )
        return f"<div class='stage'><h2>1 - Climate (L1)</h2>{charts}</div>"
    if name == "seasons":
        rows = "".join(
            f"<tr><td>{_e(s['label'])}</td><td>m{s['start']}</td><td>{s['months']}</td></tr>"
            for s in payload["durations"]
        )
        return (
            f"<div class='stage'><h2>2 - Seasons (L2)</h2>{_ribbon_svg(payload['labels'])}"
            f"<table><tr><th>regime</th><th>starts</th><th>months</th></tr>{rows}</table></div>"
        )
    if name == "weather":
        charts = "".join(
            _poly_svg(series, title=f"factor: {factor}")
            for factor, series in payload["factors"].items()
        )
        seams = ", ".join(f"m{b['start']} ({_e(b['regime'])})" for b in payload["blocks"])
        return (
            f"<div class='stage'><h2>3 - Weather (L3)</h2>"
            f"<p class='small'>block seams every {payload['block_months']} months: {seams}. "
            "The pipeline does not retain raw pre-stitch blocks; seams and conditioning "
            "are shown on the stitched stream, and the stitching corrections are the "
            "next panel.</p>"
            f"{charts}</div>"
        )
    if name == "joinery":
        recon_rows = "".join(
            f"<tr><td>{_e(factor)}</td><td>{_e(info)}</td></tr>"
            for factor, info in payload["reconciliation"].items()
        )
        stat_rows = "".join(
            f"<tr><td>{_e(factor)}</td><td>{_e(metric)}</td>"
            f"<td>{vals['decade']:.4f}</td><td>{vals['historical']:.4f}</td></tr>"
            for factor, metrics in payload["filter_stats"].items()
            for metric, vals in metrics.items()
        )
        return (
            f"<div class='stage'><h2>4 - Joinery (L4)</h2>"
            f"<h3>reconciliation</h3><table>{recon_rows}</table>"
            f"<h3>filter statistics</h3><p class='small'>{_e(payload['filter_note'])}</p>"
            f"<table><tr><th>factor</th><th>metric</th><th>this decade</th>"
            f"<th>historical</th></tr>{stat_rows}</table></div>"
        )
    return f"<div class='stage'>{_e(name)}</div>"


@app.get("/decade/{run_id}", response_class=HTMLResponse)
def decade_page(run_id: str) -> HTMLResponse:
    record = _RUNS.get(run_id)
    if record is None:
        raise HTTPException(404, "no such run")
    parts = [f"<h1>Decade run {_e(run_id)}</h1>"]
    if record["error"]:
        parts.append(f"<div class='err'>run failed: {_e(record['error'])}</div>")
    for name, payload in list(record["stages"]):
        parts.append(_render_stage(name, payload))
    if not record["done"]:
        done = len(record["stages"])
        parts.append(f"<p class='small'>building... stage {done + 1} of {len(STAGES)}</p>")
    elif record["summary"]:
        parts.append(
            f"<p class='small'>done - checkpoint {_e(record['summary']['checkpoint_hash'][:16])}"
            "...</p>"
        )
    return _page(f"decade {run_id}", "".join(parts), refresh=None if record["done"] else 3)


@app.get("/runs", response_class=HTMLResponse)
def runs_page() -> HTMLResponse:
    campaigns = scan_runs(_REPO_ROOT / "experiments")
    parts = ["<h1>Live runs</h1><p class='small'>what the artifacts on disk say; 30s refresh</p>"]
    if not campaigns:
        parts.append("<p>no campaign artifacts found under experiments/</p>")
    for c in campaigns:
        rows = "".join(
            f"<tr><td>{_e(cell['slug'])}</td>"
            f"<td class='{_e(cell['status'])}'>{_e(cell['status'])}</td>"
            f"<td>{_e(cell.get('timings', {}).get('total_s', ''))}</td>"
            f"<td>{_e(cell.get('criterion_bearing', ''))}</td>"
            f"<td>{_e(cell.get('passed_unfiltered', ''))}</td></tr>"
            for cell in c["cells"]
        )
        parts.append(
            f"<h2>{_e(c['campaign'])}</h2><table><tr><th>cell</th><th>status</th>"
            f"<th>total s</th><th>criterion</th><th>passed</th></tr>{rows}</table>"
        )
    return _page("live runs", "".join(parts), refresh=30)
