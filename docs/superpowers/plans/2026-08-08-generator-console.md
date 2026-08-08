# Generator Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port-8797 read-only console: a four-stage step-through of one hier-flow
decade (climate → seasons → weather → joinery) plus an artifact-based monitor of
live campaign runs.

**Architecture:** `src/ah/genconsole.py` holds a pure stage runner
(`build_decade`) and the FastAPI app over it, the `dataconsole.py` shape. No
generator file is edited; the joinery's per-decade private classes are consumed
read-only (a recorded dependency).

**Tech Stack:** existing deps only (FastAPI, numpy, torch via the flow sampler).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-08-generator-console-design.md` — read first.
- **Do not edit** anything in `src/ah/gen/`, anything hashed by either lock, or
  `schemas/`. New code: `src/ah/genconsole.py`, `tests/test_genconsole.py`,
  one hub card in `src/ah/hub.py`.
- Read-only console: no route writes anything anywhere.
- Checkpoint hash + climate/regimes sha pins verified on every step-through run;
  a mismatch is a displayed error, never a fallback.
- ASCII in CLI-echoed strings. TestClient tests need `pytest.mark.enable_socket`.
- Branch `genconsole-01` from main AFTER campaign-r1-b-generator merges. Full
  gate (background, read the `EXIT:` line) + ruff + pyright + CHANGELOG before
  the `--no-ff` merge; plain push after.

---

### Task 1: The stage runner — assembly and the four stages

**Files:**
- Create: `src/ah/genconsole.py`
- Test: `tests/test_genconsole.py`

**Interfaces:**
- Produces:
  `StageEvent = tuple[str, dict[str, Any]]` (name in `("climate", "seasons",
  "weather", "joinery")`, JSON-safe payload),
  `build_decade(seed: int, checkpoint_index: int, *, on_stage:
  Callable[[str, dict], None], block_batch: int = 16, device: str = "cpu") ->
  dict[str, Any]` (returns the final run summary: months, checkpoint_hash,
  stage names in order).
- Consumes (exact, from `campaign2_promotion._build_campaign_flow` and
  `ah.gen.joinery.assemble`):

```python
from ah.gen.blocks.flow import FlowBlockSampler, load_checkpoint
from ah.gen.climate.simulate import load_artifact as load_climate
from ah.gen.joinery import assemble as ja
from ah.gen.bootstrap import campaign_source
# regimes loader + artifact pins: import the same names campaign2_promotion.py
# imports (load_regimes, DEFAULT_CLIMATE_ARTIFACT, DEFAULT_REGIMES_ARTIFACT,
# PINNED_CLIMATE_SHA256, PINNED_REGIMES_SHA256 — resolve them from
# scripts/campaign2_promotion.py's import block and import from the SAME
# ah.gen modules it does; do not re-declare the pins as new literals)
```

- [ ] **Step 1: Failing test** — stage order, shapes, determinism:

```python
"""Generator console: the four-stage decade build and the runs monitor."""

from __future__ import annotations

import json

import pytest

from ah import genconsole as gc


def _run(seed: int = 3) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    gc.build_decade(seed, 0, on_stage=lambda name, payload: events.append((name, payload)))
    return events


def test_stages_arrive_in_order_with_real_shapes():
    events = _run()
    assert [e[0] for e in events] == ["climate", "seasons", "weather", "joinery"]
    climate = events[0][1]
    assert len(climate["months"]) == 120 and climate["states"], "L1 slow states missing"
    seasons = events[1][1]
    assert len(seasons["labels"]) == 120
    weather = events[2][1]
    assert weather["block_months"] >= 1 and weather["factors"]
    joinery = events[3][1]
    assert "reconciliation" in joinery and "filter_stats" in joinery


def test_same_seed_is_bit_identical():
    a, b = _run(7), _run(7)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
        b, sort_keys=True, default=str
    )
```

- [ ] **Step 2: Run to fail** (`uv run pytest tests/test_genconsole.py -q`).
- [ ] **Step 3: Implement.** `build_decade`:
  1. Verify + load the checkpoint via `configs/campaign2-checkpoints.json`
     (`load_checkpoint`, compare `meta["checkpoint_hash"]`, raise `ValueError`
     with the mismatch text on failure — the app layer turns it into a page
     error).
  2. Load climate/regimes, check both sha pins.
  3. `source = campaign_source()`; `sampler = FlowBlockSampler(model, std,
     tuple(source.factor_names), trained_fingerprint=meta["cb_fingerprint"],
     device=device, block_batch=block_batch)`.
  4. `stats = ja.wp.source_stats(source, climate)`; `support_ref =
     ja.sp.build_support_reference(source, climate,
     quantile=config.support_quantile)`; `factory = ja._DecadeFactory(...)`
     with `months=120`, the given `seed`, `world=None`, `guidance=None`,
     `config=ja.JoineryConfig()`.
  5. `prep = factory.prepare(0)` → emit `climate` (monthly slow-state rows,
     `STATE_NAMES` keys) and `seasons` (`prep.waypoints.labels` as strings +
     a durations table computed by run-length encoding).
  6. `result = factory.assemble([prep])[0]` → emit `weather` (per-factor
     monthly returns from `result.path`, `block_months` from the config,
     per-block regime = the label at each block's first month) and `joinery`
     (waypoint targets vs delivered from `result.reconciliation`'s dict form,
     plus filter statistics per filtered factor via the same skew /
     excess-kurtosis / Hill helpers `assemble.py` exposes at module level).
  7. Every payload JSON-safe (lists of floats, not ndarrays).
- [ ] **Step 4: Run to pass.** If the flow sampler makes the test unreasonably
  slow (> ~120 s), swap the TEST (only) to
  `ja.bridge.BootstrapBlockSampler(source, block_months=config.block_months)`
  via a `sampler_override` keyword on `build_decade`, and say so in the test
  docstring — the layer structure stays real, per the spec's testing section.
- [ ] **Step 5: Commit** — `feat(genconsole): the four-stage decade runner`

### Task 2: The runs monitor scanner

**Files:**
- Modify: `src/ah/genconsole.py`
- Test: `tests/test_genconsole.py`

**Interfaces:**
- Produces: `scan_runs(experiments_root: Path) -> list[dict]` — one dict per
  campaign directory that HAS a `cells/` child: `{"campaign": str, "cells":
  [{"slug", "status" ("done"|"running"|"unreadable"), "system_id",
  "seed_index", "timings", "criterion_bearing", "passed_unfiltered"}]}`,
  campaigns sorted by directory mtime descending.

- [ ] **Step 1: Failing test** — `tmp_path` with three cells: one complete
  `summary.json`, one empty dir, one corrupt JSON:

```python
def test_scan_runs_renders_states_not_exceptions(tmp_path):
    cells = tmp_path / "campaign-x" / "cells"
    done = cells / "B-bootstrap-v1-s0"
    done.mkdir(parents=True)
    (done / "summary.json").write_text(
        json.dumps(
            {
                "system_id": "bootstrap-v1",
                "seed_index": 0,
                "timings": {"total_s": 60.0},
                "criterion_bearing": True,
                "passed_unfiltered": True,
            }
        ),
        encoding="utf-8",
    )
    (cells / "F-hier-flow-v1-s1").mkdir()
    corrupt = cells / "F-hier-flow-v1-s2"
    corrupt.mkdir()
    (corrupt / "summary.json").write_text("{not json", encoding="utf-8")
    [campaign] = gc.scan_runs(tmp_path)
    by_slug = {c["slug"]: c["status"] for c in campaign["cells"]}
    assert by_slug == {
        "B-bootstrap-v1-s0": "done",
        "F-hier-flow-v1-s1": "running",
        "F-hier-flow-v1-s2": "unreadable",
    }
```

- [ ] **Step 2–4: fail → implement → pass.** Every read inside try/except;
  no exception escapes `scan_runs`.
- [ ] **Step 5: Commit** — `feat(genconsole): artifact-based runs monitor`

### Task 3: The FastAPI app

**Files:**
- Modify: `src/ah/genconsole.py`
- Test: `tests/test_genconsole.py` (TestClient, `pytestmark`-style
  `enable_socket` on these tests)

**Routes** (the `dataconsole.py` shape — module-level `app`, `_page()` chrome):
- `GET /` — the two-tab shell: seed + checkpoint form, runs tab.
- `POST /api/decade` — form (`seed`, `checkpoint`); spawns a daemon thread
  running `build_decade` with an `on_stage` that appends into a run record
  `{"stages": [...], "error": None, "done": bool}` in a module dict capped at
  8 entries (evict oldest); returns `{"run_id": ...}`. Run ids are
  `f"{seed}-{checkpoint}-{n}"` with a module counter — no clock, no uuid.
- `GET /api/decade/{run_id}` — the record as JSON (404 for unknown).
- `GET /decade/{run_id}` — the stage page: renders whatever stages have
  landed as inline SVG (line charts for climate/weather via the dataconsole
  `line_svg` idiom, a colored ribbon for seasons, tables for joinery), plus a
  `<meta http-equiv="refresh" content="3">` while `done` is false.
- `GET /runs` — the monitor page over `scan_runs(REPO_ROOT / "experiments")`,
  30s meta refresh.

- [ ] **Step 1: Failing tests** — `POST /api/decade` returns a run id and the
  poll endpoint eventually reports `done` with four stages (use the Task-1
  fast path / `sampler_override` wiring via a `TESTING_SAMPLER` module hook if
  the real sampler is slow); `/runs` renders the tmp_path fixture through a
  monkeypatched root; unknown run id → 404; a pin-mismatch run surfaces
  `error` on the page rather than a 500.
- [ ] **Step 2–4: fail → implement → pass.**
- [ ] **Step 5: Commit** — `feat(genconsole): the 8797 app - step-through + runs pages`

### Task 4: Hub card + port note

**Files:**
- Modify: `src/ah/hub.py` (the consoles card list — follow how 8796/8798/8799
  are presented there), `tests/test_genconsole.py`

- [ ] Failing test: the hub names port 8797 and the generator console.
- [ ] Implement: one card ("Generator console — watch a decade get built,
  layer by layer, and follow live campaign runs"; `http://127.0.0.1:8797`).
- [ ] Tests pass. Commit — `feat(hub): generator console card`

### Task 5: Close-out

- [ ] Launch check by hand: `uv run uvicorn ah.genconsole:app --port 8797`,
  build one decade at seed 0, eyeball all four stages and the runs tab
  against the live campaign-r1 cells; kill the server.
- [ ] `uv run ruff check . --fix && uv run ruff format .`; `uv run pyright` —
  clean.
- [ ] CHANGELOG entry under `### Added`.
- [ ] Full gate in the background to a log; read `EXIT:` and the pass count.
- [ ] Merge `--no-ff` into main, push. Commit body: built / deviations /
  discoveries.

## Self-review notes

- Spec coverage: step-through (T1+T3), monitor (T2+T3), hub (T4), pins-as-
  errors (T1 step 3.1 + T3 error test), read-only (no write route exists),
  determinism (T1 test), private-API dependency recorded (module docstring, T1).
- Type consistency: `build_decade(seed, checkpoint_index, *, on_stage,
  block_batch=16, device="cpu", sampler_override=None)` is the one signature;
  T3 consumes it through the thread wrapper only. `scan_runs(Path) ->
  list[dict]` used in T2/T3.
- The only sanctioned test-reality gap (bootstrap sampler substitution when
  the flow sampler is too slow for the suite) is bounded to test code and
  must be declared in the docstring where used.
