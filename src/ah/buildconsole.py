"""The scenario build console (WP-B): type a scenario, watch it compile, keep or discard.

**Contract.** Compiling is a dry-run: the five-stage pipeline (prompt -> model ->
extract -> validate -> stamp) persists nothing. The keep handler is the module's
ONLY write path into ``data/ah.db`` (a guard test scans the source to enforce
this). This surface is a sibling of the read-only QA inspection console
(``ah/console.py``, port 8799) — deliberately a separate module so that
console's read-only guarantee stays intact.

Run it with::

    uv run uvicorn ah.buildconsole:app --port 8798

The offline path replays ``fixtures/compiler/`` documents by scenario slug; the
live path (checkbox) calls the Anthropic compiler and requires
``ANTHROPIC_API_KEY``. Tests exercise only the offline path (no network in
tests); the live adapter is imported lazily inside the request handler.
"""

from __future__ import annotations

import html
import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ah.battery.report import BATTERY_VERSION
from ah.compiler.fixture_adapter import slugify
from ah.compiler.interface import CompileError
from ah.compiler.pipeline import process
from ah.compiler.postprocess import extract_json, stamp_envelope
from ah.compiler.prompt_v2 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages
from ah.core.digest import digest_ensemble
from ah.core.engine import TOY_ENGINE_VERSION, run_ensemble
from ah.core.institution import hold_course_twin
from ah.core.numericworld import project_numeric
from ah.core.validator import VALIDATOR_VERSION, stamp_validation
from ah.core.worldspec import WorldSpec
from ah.store import chronicle as chronicle_store
from ah.store import runrecords as run_store
from ah.store import worlds as worlds_store
from ah.store.db import connect

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"
FIXTURES_DIR = _REPO_ROOT / "fixtures" / "compiler"
ATTEMPT_LOG_DIR = _REPO_ROOT / "data" / "buildconsole"
WATERMARK = "BUILD SURFACE — WRITES ONLY ON KEEP — simulated data"
QA_CONSOLE_URL = "http://127.0.0.1:8799"

# Same chrome technique as ah/console.py (not imported from it: that module's
# read-only guarantee is guarded and this one must not couple to its internals).
_CSS = """
:root { --ink:#151a1f; --mut:#5c6874; --line:#e2e6ea; --bg:#f7f8fa; --card:#fff;
        --ok:#1f6b3a; --bad:#a3282f; --warn:#8a6d1f; }
* { box-sizing:border-box; }
body { margin:0; font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;
       color:var(--ink); background:var(--bg); }
.wm { background:#4a2b36; color:#fff; font-size:11px; letter-spacing:.06em;
      padding:5px 14px; text-transform:uppercase; position:sticky; top:0; z-index:9; }
nav { background:#fff; border-bottom:1px solid var(--line); padding:8px 14px; }
nav a { margin-right:14px; color:#1f4e79; text-decoration:none; font-weight:600; }
main { padding:14px; max-width:1100px; }
h1 { font-size:19px; margin:10px 0 4px; }
table { border-collapse:collapse; width:100%; background:var(--card); margin:6px 0 14px; font-size:12px; }
th,td { border:1px solid var(--line); padding:4px 7px; text-align:left; }
th { background:#eef1f4; font-weight:600; }
.ok { color:var(--ok); font-weight:600; }
.bad { color:var(--bad); font-weight:700; }
.warn { color:var(--warn); font-weight:600; }
.card { background:var(--card); border:1px solid var(--line); padding:10px 12px; margin:8px 0; }
.prov { color:var(--mut); font-size:11px; font-style:italic; margin:2px 0 10px; }
pre { background:#f2f5f8; border-left:2px solid #9fb4c7; padding:6px 8px;
      font-size:11px; overflow-x:auto; white-space:pre-wrap; }
button { font:inherit; padding:4px 12px; }
textarea, input { font:inherit; }
"""


def _e(x: Any) -> str:
    return html.escape(str(x))


def _page(title: str, body: str, *, refresh: bool = False) -> HTMLResponse:
    meta = '<meta http-equiv="refresh" content="1.5">' if refresh else ""
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'>{meta}"
        f"<title>{_e(title)}</title><style>{_CSS}</style></head><body>"
        f'<div class="wm">{_e(WATERMARK)}</div>'
        f'<nav><a href="/">compose</a>'
        f'<a href="{QA_CONSOLE_URL}/worlds">QA shelf (8799)</a>'
        f'<span class="prov" style="float:right">dry-run by default · '
        f"writes only on keep</span></nav>"
        f"<main>{body}</main></body></html>"
    )


def _recent_attempts_html(app: FastAPI) -> str:
    """The last 20 logged attempts, newest first. Tolerates a missing log."""
    log = Path(app.state.log_dir) / "attempts.jsonl"
    if not log.exists():
        return ""
    lines = log.read_text(encoding="utf-8").splitlines()[-20:]
    rows = []
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        stages = rec.get("stages") or []
        last = stages[-1] if stages else {"name": "-", "status": "-"}
        cls = {"ok": "ok", "fail": "bad"}.get(last.get("status", ""), "warn")
        kept = rec.get("kept_world_id") or "—"
        rows.append(
            f"<tr><td>{_e(rec.get('created_at', ''))}</td>"
            f"<td>{_e(rec.get('scenario_text', '')[:80])}</td>"
            f"<td>{'live' if rec.get('live') else 'fixture'}</td>"
            f'<td class="{cls}">{_e(last.get("name", ""))}: {_e(last.get("status", ""))}</td>'
            f"<td>{_e(kept)}</td></tr>"
        )
    if not rows:
        return ""
    return (
        "<h2>Recent attempts</h2><table>"
        "<tr><th>when</th><th>scenario</th><th>path</th><th>last stage</th><th>kept</th></tr>"
        + "".join(rows)
        + "</table>"
    )


# --------------------------------------------------------------------------- #
# the dry-run pipeline
# --------------------------------------------------------------------------- #


@dataclass
class Stage:
    name: str
    status: str  # "running" | "ok" | "fail"
    detail: str
    payload: str = ""  # raw evidence shown on failure (or verbose detail)
    elapsed_ms: int = 0


@dataclass
class Attempt:
    attempt_id: str
    scenario_text: str
    live: bool
    created_at: str
    stages: list[Stage]
    done: bool = False
    stamped: dict[str, Any] | None = None
    kept_world_id: str | None = None
    error: str | None = None
    #: Set by the live route from the adapter's pinned model id; stays "" on
    #: the fixture path and in pure tests, so run_stages never has to import
    #: the live adapter (tests/test_compiler.py guards that import).
    compiler_model: str = ""
    _thread: Any = field(default=None, repr=False, compare=False)


def _stage(att: Attempt, name: str, detail: str) -> Stage:
    s = Stage(name=name, status="running", detail=detail)
    att.stages.append(s)
    return s


def run_stages(att: Attempt, *, fetch_text: Callable[[str], str]) -> None:
    """Dry-run compile pipeline. Persists nothing; mutates ``att`` in place.

    ``fetch_text`` returns raw compiler text for the scenario — a fixture read
    offline, a live model call online. Every failure ends the ledger at its
    stage with the evidence in ``payload``.
    """
    try:
        t0 = time.perf_counter()
        s = _stage(att, "prompt", "")
        messages = build_messages(att.scenario_text)
        s.detail = (
            f"prompt {PROMPT_VERSION}: system {len(SYSTEM_PROMPT)} chars, "
            f"user {len(messages[0]['content'])} chars"
        )
        s.status, s.elapsed_ms = "ok", int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        s = _stage(att, "model", "live call" if att.live else "fixture replay")
        try:
            text = fetch_text(att.scenario_text)
        except Exception as exc:
            s.status, s.payload = "fail", f"{type(exc).__name__}: {exc}"
            return
        s.detail += f" — {len(text)} chars received"
        s.status, s.elapsed_ms = "ok", int((time.perf_counter() - t0) * 1000)

        s = _stage(att, "extract", "outermost JSON object")
        try:
            raw = extract_json(text)
        except CompileError as exc:
            s.status, s.payload = "fail", f"{exc}\n--- raw text ---\n{text[:4000]}"
            return
        s.detail = f"{len(raw)} top-level keys"
        s.status = "ok"

        s = _stage(att, "envelope", "")
        if att.live:
            raw = stamp_envelope(
                raw,
                scenario_text=att.scenario_text,
                created_at=att.created_at,
                compiler_model=att.compiler_model or "unknown",
                prompt_version=PROMPT_VERSION,
            )
            s.detail = f"stamped world_id {raw['world_id']} (system-owned envelope)"
        else:
            s.detail = "fixture carries its own envelope — carried through"
        s.status = "ok"

        s = _stage(att, "validate", "ah.core.validator via pipeline.process")
        outcome = process(raw)
        clamps = len(outcome.result.clamps)
        if outcome.rejected:
            s.status = "fail"
            s.detail = f"REJECTED ({clamps} clamp(s) before rejection)"
            s.payload = str(outcome.reject_reason)[:4000]
            return
        s.detail = f"passed — {clamps} clamp(s), 0 blocking"
        s.status = "ok"

        s = _stage(att, "stamp", "stamp_validation (preview — nothing stored)")
        att.stamped = stamp_validation(
            outcome.result,
            validated_at=att.created_at,
            validator_version=VALIDATOR_VERSION,
        )
        s.detail = f"world_id {att.stamped['world_id']} — status {att.stamped['status']}"
        s.status = "ok"
    except Exception as exc:  # a defect in the console itself, not the compile
        att.error = f"{type(exc).__name__}: {exc}"
    finally:
        att.done = True
        for st in att.stages:
            if st.status == "running":
                st.status = "fail"


def ledger_html(att: Attempt) -> str:
    """Render the stage ledger. Pure function of the attempt."""
    rows = []
    for s in att.stages:
        cls = {"ok": "ok", "fail": "bad"}.get(s.status, "warn")
        rows.append(
            f'<tr><td>{_e(s.name)}</td><td class="{cls}">{_e(s.status)}</td>'
            f"<td>{_e(s.detail)}</td><td>{s.elapsed_ms} ms</td></tr>"
        )
        if s.payload:
            rows.append(f'<tr><td colspan="4"><pre>{_e(s.payload)}</pre></td></tr>')
    if att.error:
        rows.append(
            f'<tr><td colspan="4" class="bad">console defect (not a compile result): '
            f"{_e(att.error)}</td></tr>"
        )
    return (
        "<table><tr><th>stage</th><th>status</th><th>detail</th><th>elapsed</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _fixture_fetch(fixtures_dir: Path) -> Callable[[str], str]:
    def fetch(scenario_text: str) -> str:
        p = fixtures_dir / f"{slugify(scenario_text)}.json"
        if not p.exists():
            raise CompileError(f"no fixture for scenario (looked for {p.name})")
        return p.read_text(encoding="utf-8")

    return fetch


def _append_attempt_log(att: Attempt, log_dir: Path) -> None:
    """One json line per completed attempt — including failures; this is the
    debugging record. Payloads are already truncated at capture time."""
    rec = {
        "attempt_id": att.attempt_id,
        "scenario_text": att.scenario_text,
        "live": att.live,
        "created_at": att.created_at,
        "stages": [asdict(s) for s in att.stages],
        "done": att.done,
        "kept_world_id": att.kept_world_id,
        "error": att.error,
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "attempts.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def create_app(
    db_path: str | Path = DEFAULT_DB,
    fixtures_dir: str | Path = FIXTURES_DIR,
    synchronous: bool = False,
    log_dir: str | Path = ATTEMPT_LOG_DIR,
) -> FastAPI:
    app = FastAPI(title="ah build console", version="0.1.0")
    app.state.db_path = Path(db_path)
    app.state.fixtures_dir = Path(fixtures_dir)
    app.state.synchronous = synchronous
    app.state.log_dir = Path(log_dir)
    app.state.attempts = {}
    app.state.lock = threading.Lock()

    @app.get("/", response_class=HTMLResponse)
    def compose() -> HTMLResponse:
        body = (
            "<h1>Compile a scenario</h1>"
            '<p class="prov">Compiling is a dry-run: nothing is stored until you '
            "explicitly keep the result.</p>"
            '<form method="post" action="/compile" class="card">'
            '<textarea name="scenario" rows="6" style="width:100%" '
            'placeholder="Describe the counterfactual world..."></textarea><br>'
            '<label><input type="checkbox" name="live" value="on"> '
            "live model call (needs ANTHROPIC_API_KEY; otherwise fixture replay)"
            "</label> "
            '<button type="submit">Compile (dry-run)</button></form>' + _recent_attempts_html(app)
        )
        return _page("compose", body)

    @app.post("/compile")
    async def compile_post(request: Request) -> RedirectResponse:
        form = parse_qs((await request.body()).decode("utf-8"))
        scenario = (form.get("scenario") or [""])[0].strip()
        live = (form.get("live") or [""])[0] == "on"
        if not scenario:
            return RedirectResponse(url="/", status_code=303)
        att = Attempt(
            attempt_id=uuid.uuid4().hex[:12],
            scenario_text=scenario,
            live=live,
            created_at=datetime.now(UTC).isoformat(),
            stages=[],
        )
        fetch: Callable[[str], str]
        if live:  # pragma: no cover - live only (lazy: keeps the adapter off the test path)
            from ah.compiler.anthropic_adapter import COMPILER_MODEL, fetch_raw_text

            att.compiler_model = COMPILER_MODEL

            def _live_fetch(text: str) -> str:
                return fetch_raw_text(COMPILER_MODEL, text)

            fetch = _live_fetch
        else:
            fetch = _fixture_fetch(app.state.fixtures_dir)
        with app.state.lock:
            app.state.attempts[att.attempt_id] = att
        if app.state.synchronous:
            run_stages(att, fetch_text=fetch)
            _append_attempt_log(att, app.state.log_dir)
        else:
            t = threading.Thread(
                target=lambda: (
                    run_stages(att, fetch_text=fetch),
                    _append_attempt_log(att, app.state.log_dir),
                ),
                daemon=True,
            )
            att._thread = t
            t.start()
        return RedirectResponse(url=f"/attempt/{att.attempt_id}", status_code=303)

    @app.get("/attempt/{aid}", response_class=HTMLResponse)
    def attempt_page(aid: str) -> HTMLResponse:
        with app.state.lock:
            att = app.state.attempts.get(aid)
        if att is None:
            raise HTTPException(404, "no such attempt")
        head = (
            f"<h1>Attempt {_e(att.attempt_id)}</h1>"
            f'<div class="card"><b>{"live" if att.live else "fixture"}</b> · '
            f"{_e(att.created_at)}<br><i>{_e(att.scenario_text[:500])}</i></div>"
        )
        body = head + ledger_html(att)
        if not att.done:
            return _page("compiling…", body + '<p class="prov">compiling…</p>', refresh=True)
        if att.kept_world_id is not None:
            body += (
                f'<p class="ok">kept as <code>{_e(att.kept_world_id)}</code> — '
                f'<a href="{QA_CONSOLE_URL}/worlds">open the QA shelf</a></p>'
            )
        elif att.stamped is not None:
            body += (
                f'<form method="post" action="/attempt/{_e(aid)}/keep" class="card">'
                '<label><input type="checkbox" name="run" value="on" checked> '
                "also run the engine</label> "
                'seed <input name="seed" value="42" size="6"> '
                'n_paths <input name="n_paths" value="1000" size="6"> '
                '<button type="submit">Keep this world</button></form>'
                '<p><a href="/">discard (nothing was stored)</a></p>'
            )
        else:
            body += '<p><a href="/">discard (nothing was stored)</a></p>'
        return _page("attempt", body)

    @app.post("/attempt/{aid}/keep")
    async def keep_post(aid: str, request: Request) -> HTMLResponse:
        """THE module's only write path into the store (guard test enforces)."""
        form = parse_qs((await request.body()).decode("utf-8"))
        with app.state.lock:
            att = app.state.attempts.get(aid)
        if att is None or not att.done or att.stamped is None:
            raise HTTPException(404, "no completed, valid attempt with that id")
        if att.kept_world_id is not None:
            raise HTTPException(409, "already kept")

        now = datetime.now(UTC).isoformat()
        conn = connect(app.state.db_path)
        try:
            worlds_store.save_world(conn, att.stamped, created_at=now)
            wid = att.stamped["world_id"]
            chronicle_store.append(
                conn,
                world_id=wid,
                seq=len(chronicle_store.read(conn, wid)),
                type="birth",
                payload={"status": att.stamped["status"], "source": "buildconsole"},
                created_at=now,
            )
            run_note = ""
            if (form.get("run") or [""])[0] == "on":
                ws = WorldSpec.model_validate(att.stamped)
                nw = project_numeric(ws)
                seed = int((form.get("seed") or ["42"])[0])
                n_paths = int((form.get("n_paths") or ["1000"])[0])
                ensemble = run_ensemble(nw, n_paths, base_seed=seed)
                digest = digest_ensemble(ensemble)
                twin = hold_course_twin(nw, seed)
                run_id = str(uuid.uuid4())
                run_store.save_run_record(
                    conn,
                    run_id=run_id,
                    world_id=wid,
                    resolved_engine={
                        "generator_id": ws.engine_defaults.generator_id,
                        "generator_version": TOY_ENGINE_VERSION,
                        "validator_version": VALIDATOR_VERSION,
                        "battery_version": BATTERY_VERSION,
                    },
                    seed=seed,
                    n_paths=n_paths,
                    overrides={"seed": seed, "n_paths": n_paths},
                    outputs_digest=digest,
                    summary_stats={"final_of_100": twin.final_value},
                    created_at=now,
                )
                chronicle_store.append(
                    conn,
                    world_id=wid,
                    run_id=run_id,
                    seq=len(chronicle_store.read(conn, wid)),
                    type="run",
                    payload={"digest": digest, "seed": seed, "n_paths": n_paths},
                    created_at=now,
                )
                run_note = f"<p>run recorded: <code>{_e(run_id)}</code></p>"
            conn.commit()
        finally:
            conn.close()
        att.kept_world_id = wid
        body = (
            f"<h1>Kept</h1><p>world <code>{_e(wid)}</code> stored.</p>{run_note}"
            f'<p><a href="{QA_CONSOLE_URL}/worlds">open the QA shelf</a> · '
            f'<a href="/">compile another</a></p>'
        )
        return _page("kept", body)

    return app


app = create_app()
