# Scenario Build Console (WP-B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-page internal console (port 8798) where the owner types a scenario, watches it compile stage-by-stage, and explicitly keeps (or discards) the result.

**Architecture:** One new FastAPI module `src/ah/buildconsole.py` following `ah/console.py`'s server-rendered-HTML idiom. A compile is a dry-run pipeline of five stages (prompt → model → extract → validate → stamp) recorded in an in-memory `Attempt` ledger and appended to a jsonl log; nothing touches `data/ah.db` except the Keep handler, which reuses the exact store calls `ah/cli.py` makes.

**Tech Stack:** FastAPI + uvicorn (existing deps), stdlib threading/urllib; tests via fastapi TestClient (httpx already present). **No new dependencies** — form posts are parsed with `urllib.parse.parse_qs`, NOT `fastapi.Form` (which would require python-multipart).

## Global Constraints

- Work in a **git worktree** on branch `build-console-01` cut from `main` — the primary tree may be running a gate at any time and must not be touched.
- **Do not edit `src/ah/console.py`** (its read-only guarantee is guarded) or anything in `schemas/` (vendored truth) or any file named in `pre-registration.lock` `hashed_files` (none are touched by this plan — keep it that way).
- **No network in tests** (pytest-socket enforces). The live path (`AnthropicCompiler`, `fetch_raw_text`) is never imported at module top of any test-imported path — lazy import inside the request handler only.
- Writes to `data/ah.db` happen in exactly one function (the keep handler); a guard test enforces this by source scan.
- HTML may use Unicode; anything echoed to a terminal stays ASCII.
- Definition of done: plan's tests pass, full suite green, `ruff check`/`ruff format`/`pyright` clean, `CHANGELOG.md` updated, commit bodies state what/deviations/discoveries.

**Interfaces consumed from the existing codebase (verified 2026-08-06):**

```python
from ah.compiler.interface import CompileError                       # ValueError subclass
from ah.compiler.postprocess import extract_json                     # (str) -> dict
from ah.compiler.prompt_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages
from ah.compiler.fixture_adapter import slugify                      # (str) -> str
from ah.compiler.pipeline import process                             # (dict) -> CompileOutcome(raw, result, world, rejected, reject_reason)
from ah.core.validator import VALIDATOR_VERSION, stamp_validation    # stamp_validation(result, validated_at=..., validator_version=...) -> dict with world_id/status
from ah.core.digest import digest_ensemble
from ah.core.engine import TOY_ENGINE_VERSION, run_ensemble
from ah.core.institution import hold_course_twin
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.store import chronicle as chronicle_store                    # .append(conn, world_id=, seq=, type=, payload=, created_at=)  (+run_id= for runs)
from ah.store import runrecords as run_store                         # .save_run_record(conn, run_id=, world_id=, resolved_engine=, seed=, n_paths=, overrides=, outputs_digest=, summary_stats=, created_at=)
from ah.store import worlds as worlds_store                          # .save_world(conn, stamped, created_at=)
from ah.battery.report import BATTERY_VERSION
```

`FIXTURES_DIR = _REPO_ROOT / "fixtures" / "compiler"`; `DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"`; chronicle next-seq is `len(chronicle_store.read(conn, world_id))` (mirrors `cli._next_seq`).

---

### Task 1: Worktree, module skeleton, compose page

**Files:**
- Create: `src/ah/buildconsole.py`
- Test: `tests/test_buildconsole.py`

**Interfaces:**
- Produces: `create_app(db_path=DEFAULT_DB, fixtures_dir=FIXTURES_DIR, synchronous=False) -> FastAPI`; module-level `app = create_app()`; `WATERMARK` constant; `_page(title, body) -> HTMLResponse`.

- [ ] **Step 1: Create the worktree and branch**

```bash
git worktree add ../Terrarium-wpb -b build-console-01 main
cd ../Terrarium-wpb && uv sync --dev
```

- [ ] **Step 2: Write the failing test**

```python
"""Tests for the scenario build console (WP-B). All offline; live path never imported."""

from fastapi.testclient import TestClient

from ah.buildconsole import create_app


def _client(tmp_path, fixtures_dir=None):
    app = create_app(
        db_path=tmp_path / "test.db",
        fixtures_dir=fixtures_dir or tmp_path / "fixtures",
        synchronous=True,
    )
    return TestClient(app)


def test_compose_page_renders(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "BUILD SURFACE" in r.text          # watermark
    assert "WRITES ONLY ON KEEP" in r.text
    assert "<textarea" in r.text
```

- [ ] **Step 3: Run it, verify it fails** — `uv run pytest tests/test_buildconsole.py -q` → ImportError.

- [ ] **Step 4: Write the skeleton**

Module docstring must state the contract: *dry-run by default; the keep handler is the only write path; sibling of the read-only QA console, not part of it.* Reuse `console.py`'s chrome technique (copy `_CSS`, `_e`, adapt `_page`) — do not import from `ah.console`.

```python
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"
FIXTURES_DIR = _REPO_ROOT / "fixtures" / "compiler"
ATTEMPT_LOG_DIR = _REPO_ROOT / "data" / "buildconsole"      # gitignored (under data/)
WATERMARK = "BUILD SURFACE — WRITES ONLY ON KEEP — simulated data"
QA_CONSOLE_URL = "http://127.0.0.1:8799"


def create_app(
    db_path: str | Path = DEFAULT_DB,
    fixtures_dir: str | Path = FIXTURES_DIR,
    synchronous: bool = False,
) -> FastAPI:
    app = FastAPI(title="ah build console", version="0.1.0")
    app.state.db_path = Path(db_path)
    app.state.fixtures_dir = Path(fixtures_dir)
    app.state.synchronous = synchronous
    app.state.attempts = {}          # attempt_id -> Attempt
    app.state.lock = threading.Lock()

    @app.get("/", response_class=HTMLResponse)
    def compose() -> HTMLResponse:
        body = (
            "<h1>Compile a scenario</h1>"
            '<form method="post" action="/compile" class="card">'
            '<textarea name="scenario" rows="6" style="width:100%"></textarea><br>'
            '<label><input type="checkbox" name="live" value="on"> '
            "live model call (needs ANTHROPIC_API_KEY; otherwise fixture replay)</label> "
            '<button type="submit">Compile (dry-run)</button></form>'
            + _recent_attempts_html(app)
        )
        return _page("compose", body)

    return app


app = create_app()
```

`_recent_attempts_html(app)` returns `""` for now (Task 5 fills it in).

- [ ] **Step 5: Run test, verify pass; lint** — `uv run pytest tests/test_buildconsole.py -q && uv run ruff check src/ah/buildconsole.py tests/test_buildconsole.py && uv run ruff format --check .`

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat(buildconsole): module skeleton + compose page (WP-B task 1)"`

---

### Task 2: Attempt model and the five-stage dry-run pipeline (pure + fixture path)

**Files:**
- Modify: `src/ah/buildconsole.py`
- Test: `tests/test_buildconsole.py`

**Interfaces:**
- Produces: `@dataclass Stage(name, status, detail, payload="", elapsed_ms=0)` with status in `{"running","ok","fail"}`; `@dataclass Attempt(attempt_id, scenario_text, live, created_at, stages, done=False, stamped=None, kept_world_id=None, error=None)`; `run_stages(att: Attempt, *, fetch_text: Callable[[str], str]) -> None` (mutates `att` in place); `ledger_html(att) -> str` (pure).

- [ ] **Step 1: Write the failing tests**

```python
import json

GOOD = "the long stagflation"   # slug: the-long-stagflation


def _write_fixture(tmp_path, name, doc):
    d = tmp_path / "fixtures"
    d.mkdir(exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    return d


def _good_doc():
    # reuse a real committed compiler fixture as the known-good document
    import json as _j
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "fixtures" / "compiler"
    return _j.loads(sorted(src.glob("*.json"))[0].read_text(encoding="utf-8"))


def test_run_stages_all_ok(tmp_path):
    from ah.buildconsole import Attempt, run_stages
    doc = _good_doc()
    att = Attempt(attempt_id="a1", scenario_text=GOOD, live=False,
                  created_at="2026-08-06T00:00:00+00:00", stages=[])
    run_stages(att, fetch_text=lambda s: json.dumps(doc))
    assert att.done
    assert [s.name for s in att.stages] == ["prompt", "model", "extract", "validate", "stamp"]
    assert all(s.status == "ok" for s in att.stages)
    assert att.stamped is not None and "world_id" in att.stamped


def test_run_stages_rejection_is_first_class(tmp_path):
    from ah.buildconsole import Attempt, run_stages
    att = Attempt(attempt_id="a2", scenario_text="x", live=False,
                  created_at="2026-08-06T00:00:00+00:00", stages=[])
    run_stages(att, fetch_text=lambda s: json.dumps({"schema_version": "1.0.0"}))
    assert att.done and att.stamped is None
    validate_stage = next(s for s in att.stages if s.name == "validate")
    assert validate_stage.status == "fail"
    assert validate_stage.payload            # evidence preserved
    assert not any(s.name == "stamp" for s in att.stages)   # later stages not run


def test_ledger_html_marks_failures(tmp_path):
    from ah.buildconsole import Attempt, ledger_html, run_stages
    att = Attempt(attempt_id="a3", scenario_text="x", live=False,
                  created_at="2026-08-06T00:00:00+00:00", stages=[])
    run_stages(att, fetch_text=lambda s: "not json at all")
    out = ledger_html(att)
    assert 'class="bad"' in out and "extract" in out
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/test_buildconsole.py -q` → ImportError on `Attempt`.

- [ ] **Step 3: Implement**

```python
@dataclass
class Stage:
    name: str
    status: str                 # "running" | "ok" | "fail"
    detail: str
    payload: str = ""           # raw evidence shown on failure (or verbose detail)
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
            outcome.result, validated_at=att.created_at,
            validator_version=VALIDATOR_VERSION,
        )
        s.detail = (
            f"world_id {att.stamped['world_id']} — status {att.stamped['status']}"
        )
        s.status = "ok"
    except Exception as exc:  # a defect in the console itself, not the compile
        att.error = f"{type(exc).__name__}: {exc}"
    finally:
        att.done = True
        for st in att.stages:
            if st.status == "running":
                st.status = "fail"
```

`ledger_html(att)` renders one `<table>` row per stage: name (left), status pill (`ok`/`bad`/`warn` CSS classes already in `_CSS`), detail, elapsed; a failed stage adds a full-width `<tr>` containing `<pre>{_e(s.payload)}</pre>`. Pure function of `att`, no app state.

The fixture-path `fetch_text` (used by Task 3's route):

```python
def _fixture_fetch(fixtures_dir: Path) -> Callable[[str], str]:
    def fetch(scenario_text: str) -> str:
        p = fixtures_dir / f"{slugify(scenario_text)}.json"
        if not p.exists():
            raise CompileError(f"no fixture for scenario (looked for {p.name})")
        return p.read_text(encoding="utf-8")
    return fetch
```

- [ ] **Step 4: Run tests, verify pass; lint.** Same commands as Task 1 step 5.

- [ ] **Step 5: Commit** — `git commit -am "feat(buildconsole): five-stage dry-run pipeline + ledger (WP-B task 2)"`

---

### Task 3: POST /compile and the watching page

**Files:**
- Modify: `src/ah/buildconsole.py`
- Test: `tests/test_buildconsole.py`

**Interfaces:**
- Consumes: `run_stages`, `ledger_html`, `_fixture_fetch` (Task 2).
- Produces: routes `POST /compile` (303 → `/attempt/{id}`), `GET /attempt/{id}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_compile_flow_fixture_green(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    c = _client(tmp_path, fixtures_dir=fixtures)
    r = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False)
    assert r.status_code == 303
    page = c.get(r.headers["location"]).text
    for stage in ("prompt", "model", "extract", "validate", "stamp"):
        assert stage in page
    assert "world_id" in page
    assert "Keep" in page                       # done state offers keep
    assert "http-equiv" not in page             # done -> no meta refresh


def test_watching_page_polls_until_done(tmp_path):
    # non-synchronous app: the page must render mid-compile with a refresh tag
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    app = create_app(db_path=tmp_path / "t.db", fixtures_dir=fixtures, synchronous=False)
    c = TestClient(app)
    r = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False)
    aid = r.headers["location"].rsplit("/", 1)[1]
    with app.state.lock:
        thread = app.state.attempts[aid]._thread
    thread.join(timeout=30)
    assert "Keep" in c.get(f"/attempt/{aid}").text


def test_unknown_attempt_404(tmp_path):
    c = _client(tmp_path)
    assert c.get("/attempt/nope").status_code == 404
```

Note: `TestClient.post(..., data=...)` sends `application/x-www-form-urlencoded`, which the handler parses with `parse_qs` — no python-multipart involved.

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**

```python
@app.post("/compile")
async def compile_post(request: Request) -> RedirectResponse:
    form = parse_qs((await request.body()).decode("utf-8"))
    scenario = (form.get("scenario") or [""])[0].strip()
    live = (form.get("live") or [""])[0] == "on"
    if not scenario:
        return RedirectResponse(url="/", status_code=303)
    att = Attempt(
        attempt_id=uuid.uuid4().hex[:12], scenario_text=scenario, live=live,
        created_at=datetime.now(UTC).isoformat(), stages=[],
    )
    if live:
        def fetch(text: str) -> str:            # pragma: no cover - live only
            from ah.compiler.anthropic_adapter import AnthropicCompiler, fetch_raw_text
            return fetch_raw_text(AnthropicCompiler().model, text)
    else:
        fetch = _fixture_fetch(app.state.fixtures_dir)
    with app.state.lock:
        app.state.attempts[att.attempt_id] = att
    if app.state.synchronous:
        run_stages(att, fetch_text=fetch)
        _append_attempt_log(att)
    else:
        t = threading.Thread(
            target=lambda: (run_stages(att, fetch_text=fetch), _append_attempt_log(att)),
            daemon=True,
        )
        att._thread = t          # joinable by tests; underscore = not rendered
        t.start()
    return RedirectResponse(url=f"/attempt/{att.attempt_id}", status_code=303)
```

(`_append_attempt_log` is a no-op stub until Task 5; declare `_thread: Any = None` as a field default on `Attempt`.)

`GET /attempt/{aid}`: 404 if unknown; else `_page(...)` with the scenario text in a card, `ledger_html(att)`, and: while `not att.done`, prepend `<meta http-equiv="refresh" content="1.5">` (inject via a `refresh: bool` parameter on `_page`); when done and `att.stamped`, render the keep form (Task 4) and a discard link `<a href="/">discard (nothing was stored)</a>`; when done and failed, render the discard link only.

**`fetch_raw_text` refactor** (needed so the live path can show raw text before extraction): in `src/ah/compiler/anthropic_adapter.py`, move the body of `compile` into

```python
def fetch_raw_text(model: str, scenario_text: str) -> str:  # pragma: no cover - live only
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model, max_tokens=_MAX_TOKENS, system=SYSTEM_PROMPT,
        messages=cast("Any", build_messages(scenario_text)),
    )
    return "".join(
        getattr(block, "text", "") for block in message.content
        if getattr(block, "type", "") == "text"
    )
```

and have `AnthropicCompiler.compile` become `return extract_json(fetch_raw_text(self.model, scenario_text))`. Behavior-preserving; no test imports it.

- [ ] **Step 4: Run tests, verify pass; lint.**
- [ ] **Step 5: Commit** — `git commit -am "feat(buildconsole): compile route + watching page; expose fetch_raw_text (WP-B task 3)"`

---

### Task 4: The Keep handler (the only write path) + guard test

**Files:**
- Modify: `src/ah/buildconsole.py`
- Test: `tests/test_buildconsole.py`

**Interfaces:**
- Consumes: `att.stamped` (Task 2), store call signatures from Global Constraints.
- Produces: `POST /attempt/{aid}/keep` with optional `run=on`, `seed`, `n_paths` form fields.

- [ ] **Step 1: Write the failing tests**

```python
import sqlite3


def test_keep_stores_world_and_birth(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    c = _client(tmp_path, fixtures_dir=fixtures)
    loc = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False).headers["location"]
    aid = loc.rsplit("/", 1)[1]
    r = c.post(f"/attempt/{aid}/keep", data={}, follow_redirects=False)
    assert r.status_code == 200
    conn = sqlite3.connect(tmp_path / "test.db")
    from ah.store import chronicle as chronicle_store
    from ah.store import worlds as worlds_store
    from ah.buildconsole import create_app  # noqa: F401  (import for source scan below)
    app_attempt = None
    wid = None
    rows = conn.execute("SELECT world_id FROM worlds").fetchall()
    assert len(rows) == 1
    wid = rows[0][0]
    events = chronicle_store.read(conn, wid)
    assert [e["type"] for e in events] == ["birth"]


def test_keep_with_run_records_a_run(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    c = _client(tmp_path, fixtures_dir=fixtures)
    loc = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False).headers["location"]
    aid = loc.rsplit("/", 1)[1]
    c.post(f"/attempt/{aid}/keep", data={"run": "on", "seed": "42", "n_paths": "16"})
    conn = sqlite3.connect(tmp_path / "test.db")
    runs = conn.execute("SELECT n_paths, seed FROM run_records").fetchall()
    assert runs == [(16, 42)]


def test_keep_twice_is_rejected(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    c = _client(tmp_path, fixtures_dir=fixtures)
    loc = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False).headers["location"]
    aid = loc.rsplit("/", 1)[1]
    c.post(f"/attempt/{aid}/keep", data={})
    r = c.post(f"/attempt/{aid}/keep", data={})
    assert r.status_code == 409


def test_only_keep_handler_writes_to_store():
    """Guard: the module's sole store-writing call sites live inside keep_post.

    Same technique as the narrative-blindness scan: assert on source text so a
    future edit that adds a second write path fails loudly here.
    """
    import inspect

    import ah.buildconsole as bc

    src = inspect.getsource(bc)
    for needle in ("save_world(", "save_run_record(", "chronicle_store.append("):
        count = src.count(needle)
        keep_src = src[src.index("def keep_post") :]
        assert count == keep_src.count(needle), (
            f"{needle} called outside keep_post — the console's write "
            "guarantee is 'nothing persists except through Keep'"
        )
```

Adjust the `worlds` table column list to the real schema if `SELECT world_id FROM worlds` errors — check `src/ah/store/worlds.py` for the table name/columns and query accordingly (do not guess; read the file).

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement** — inside `create_app`:

```python
@app.post("/attempt/{aid}/keep")
async def keep_post(aid: str, request: Request) -> HTMLResponse:
    form = parse_qs((await request.body()).decode("utf-8"))
    with app.state.lock:
        att = app.state.attempts.get(aid)
    if att is None or not att.done or att.stamped is None:
        raise HTTPException(404, "no completed, valid attempt with that id")
    if att.kept_world_id is not None:
        raise HTTPException(409, "already kept")

    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(app.state.db_path)
    try:
        worlds_store.save_world(conn, att.stamped, created_at=now)
        wid = att.stamped["world_id"]
        chronicle_store.append(
            conn, world_id=wid, seq=len(chronicle_store.read(conn, wid)),
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
                conn, run_id=run_id, world_id=wid,
                resolved_engine={
                    "generator_id": ws.engine_defaults.generator_id,
                    "generator_version": TOY_ENGINE_VERSION,
                    "validator_version": VALIDATOR_VERSION,
                    "battery_version": BATTERY_VERSION,
                },
                seed=seed, n_paths=n_paths, overrides={"seed": seed, "n_paths": n_paths},
                outputs_digest=digest,
                summary_stats={"final_of_100": twin.final_value},
                created_at=now,
            )
            chronicle_store.append(
                conn, world_id=wid, run_id=run_id,
                seq=len(chronicle_store.read(conn, wid)), type="run",
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
```

The done-state keep form on the watching page (Task 3's placeholder):

```html
<form method="post" action="/attempt/{aid}/keep" class="card">
  <label><input type="checkbox" name="run" value="on" checked> also run the engine</label>
  seed <input name="seed" value="42" size="6">
  n_paths <input name="n_paths" value="1000" size="6">
  <button type="submit">Keep this world</button>
</form>
```

- [ ] **Step 4: Run tests, verify pass; lint.**
- [ ] **Step 5: Commit** — `git commit -am "feat(buildconsole): keep handler — the console's only write path (WP-B task 4)"`

---

### Task 5: Attempt log (jsonl) + recent-attempts list + failure-path test

**Files:**
- Modify: `src/ah/buildconsole.py`
- Test: `tests/test_buildconsole.py`

**Interfaces:**
- Produces: `_append_attempt_log(att, log_dir=None)` writing one json line per completed attempt to `<log_dir>/attempts.jsonl` (default `ATTEMPT_LOG_DIR`, overridable via `create_app(log_dir=...)` — add the parameter); `_recent_attempts_html(app)` rendering the last 20 lines newest-first.

- [ ] **Step 1: Write the failing tests**

```python
def test_attempt_log_records_failures_too(tmp_path):
    app = create_app(db_path=tmp_path / "t.db", fixtures_dir=tmp_path / "none",
                     synchronous=True, log_dir=tmp_path / "log")
    c = TestClient(app)
    c.post("/compile", data={"scenario": "no such fixture"})
    lines = (tmp_path / "log" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["scenario_text"] == "no such fixture"
    assert rec["stages"][-1]["status"] == "fail"      # model stage: missing fixture
    assert "no fixture" in rec["stages"][-1]["payload"]


def test_recent_attempts_on_compose_page(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    app = create_app(db_path=tmp_path / "t.db", fixtures_dir=fixtures,
                     synchronous=True, log_dir=tmp_path / "log")
    c = TestClient(app)
    c.post("/compile", data={"scenario": GOOD})
    assert GOOD in c.get("/").text
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** `_append_attempt_log` serializes `dataclasses.asdict(att)` minus `_thread`, truncating each stage payload to 4000 chars, `mkdir(parents=True, exist_ok=True)`, append with `"\n"`. `_recent_attempts_html` reads the last 20 lines (tolerate a missing file → `""`), renders a table: created_at, scenario (first 80 chars), live?, last stage + status, kept world_id or "—". The jsonl lives under `data/` (gitignored) — it is the console's permitted cache, and the debugging record for failed compiles.

- [ ] **Step 4: Run tests, verify pass; lint.**
- [ ] **Step 5: Commit** — `git commit -am "feat(buildconsole): attempt log + recent attempts (WP-B task 5)"`

---

### Task 6: Docs, changelog, full gate, merge

**Files:**
- Modify: `CHANGELOG.md`, `docs/BUILD-SUMMARY.md` (capability inventory: add the build console row), `docs/USER-MANUAL.md` (a short "compile a scenario in the browser" subsection pointing at `uv run uvicorn ah.buildconsole:app --port 8798`, noting the live path's known rejection until WP-A lands)

- [ ] **Step 1: Update the three docs.** CHANGELOG entry under Unreleased: what WP-B adds, the write-guarantee, the port, and that the live path still rejects pending WP-A (honest state).
- [ ] **Step 2: Full gate in the worktree, in the background, to a file** — `uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90` → read the `EXIT:` line and pass count from the log file (never a piped tail). Also `uv run ruff check . && uv run ruff format --check . && uv run pyright`.
- [ ] **Step 3: Manual acceptance walk (2 min).** `uv run uvicorn ah.buildconsole:app --port 8798`; compile the scenario matching a committed fixture; watch all five stages go green; Keep with run n_paths=16; confirm the world appears on the QA shelf (8799). Then compile gibberish; confirm the model stage goes red with the missing-fixture evidence.
- [ ] **Step 4: Merge per convention** — only when the gate log is green: `git checkout main && git merge --no-ff build-console-01` (commit body: what/deviations/discoveries), plain push. Remove the worktree afterwards: `git worktree remove ../Terrarium-wpb`.

---

## Self-review notes

- Spec coverage: compose/watch/done states (T1/T3/T4), five-stage ledger (T2), dry-run + keep-only writes (T2/T4 + guard), attempt jsonl incl. failures (T5), fixture-tested no-network (all), separate module/port + untouched QA console (T1/global), optional run on keep (T4), acceptance walk (T6). Live raw-text stage honored via the `fetch_raw_text` refactor (T3).
- Types consistent: `Attempt`/`Stage`/`run_stages`/`ledger_html` defined in T2 and consumed by T3-T5 with matching signatures; `create_app` gains `log_dir` in T5 (noted at both ends).
- Known judgment call: `test_keep_stores_world_and_birth` queries the worlds table directly; the implementer must read `src/ah/store/worlds.py` first and fix the query to the real schema — flagged inline.
