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
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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
    return ""


def create_app(
    db_path: str | Path = DEFAULT_DB,
    fixtures_dir: str | Path = FIXTURES_DIR,
    synchronous: bool = False,
) -> FastAPI:
    app = FastAPI(title="ah build console", version="0.1.0")
    app.state.db_path = Path(db_path)
    app.state.fixtures_dir = Path(fixtures_dir)
    app.state.synchronous = synchronous
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

    return app


app = create_app()
