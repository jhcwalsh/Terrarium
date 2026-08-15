# CIO-04: Pre-history Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The plan-growth chart opens on an inherited decade and the 3Y/5Y/10Y columns hold real numbers from the first quarter of play — DN-8's O-1 Option A, delivered without touching a single scored number.

**Architecture:** A separate, validated *calm decade* WorldSpec is run through the same toy engine under a declared seed offset, producing a market pre-history. The institution is replayed over that tape hold-course and the resulting path is scaled to terminate exactly at the opening book the game already starts from — the same shape-not-level trick `_seed_ladder` uses today. `build_cio_view` prepends the result to `plan.history` and the market paths, sets `worldStartIndex`, and extends the return windows backwards so the long columns fill.

**Tech Stack:** Python 3.12, numpy, pytest. No new dependencies. **No app changes at all** — the renderer has supported `worldStartIndex`, `preRunLabel` and `worldStartLabel` since it was vendored.

**Spec:** `docs/superpowers/specs/2026-08-14-cio-dashboard-design.md` §2 (O-1 row) and §8 (the cio-04 WP row). Contract: `Instructions/DN-8-cio-dashboard-data-contract.md` §5.

## Global Constraints

- Branch `cio-04-prehistory`, merged `--no-ff` into `main` only after the full gate is green and `scripts/check_gate.py` stamps `.gate-ok`. Controller runs the gate and the merge.
- **The scoring surface does not move.** `PLAY_ALPHA_VERSION` is NOT bumped; `TOY_ENGINE_VERSION` is NOT bumped; `tests/test_engine.py`'s `GOLDEN_DIGEST` must still pass untouched; `_mark_to_market`'s values, the outcome endpoint, and every leaderboard row keep their exact meaning. If any change you are about to make would alter a scored number, STOP and report it — that is a different work package and an owner's release decision.
  - Concretely: **`ah/core/engine.py` and `ah/play.py` are not modified by this WP** except where a step below says so explicitly (Task 2 adds one optional keyword to `simulate_play` with a default that preserves current behavior byte-for-byte).
- **Ruled (2026-08-14, controller):** the pre-history is *display-only*. The opening book at world month 0 stays exactly what `_build_portfolio` produces today, and the pre-history path is scaled to terminate at it. The alternative — an opening book that is the *output* of a simulated pre-decade — is more faithful and is deliberately NOT built here: it changes every scored run, forces an alpha-version bump, and restarts leaderboards, which is a release event and the owner's call. Record this in DN-8 when Task 5 amends it.
- Determinism: same world + same seed ⇒ byte-identical pre-history. All randomness flows from `numpy.random.Generator(PCG64(seed))` via the declared offset; no clocks, no globals.
- The pre-history must **pass the V-rules** (DN-8 §5's stated cost of Option A): it is a real `WorldSpec`, loaded and validated through the normal loader, and a test asserts it.
- Sealed files: none of `ah/cioview.py`, `ah/play.py`, `ah/core/engine.py` appear in any `pre-registration*.lock` (verified). Do not touch any file that does.
- Gate: full pytest suite, ruff, pyright clean, coverage ≥ 90 on `ah.core`.

---

### Task 1: The inherited decade — a validated calm world

**Files:**
- Create: `src/ah/presets/prehistory.json`
- Create: `scripts/gen_prehistory_preset.py`
- Test: `tests/test_prehistory.py` (new file; houses this WP's tests)

**Interfaces:**
- Produces: a 40-quarter `WorldSpec` document that loads, validates (V1–V12), and projects; used by Task 2 as the structure of every world's inherited past.

Why a separate world rather than the world's own spec extended backwards: the engine's draws are a function of the total month count, and its rate glide, spread pulse, crisis mask and regime tiling are all indexed from quarter 0 — a longer run is not a superset of a shorter one, and re-anchoring the world's own crisis schedule onto the pre-history would put this world's crash in its past. The inherited decade is therefore its own world: the same structural machinery, a deliberately unremarkable decade.

- [ ] **Step 1: Write the failing test**

Create `tests/test_prehistory.py`:

```python
"""cio-04: the inherited decade that renders before a world's month 0.

Display-only by ruling (see the plan and DN-8's O-1 resolution): the opening
book is unchanged, and the pre-history is pinned to terminate at it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.validator import validate

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _doc(name: str) -> dict[str, Any]:
    return json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))


def test_prehistory_preset_passes_the_v_rules():
    """DN-8 O-1's stated cost of option A: an unvalidated pre-history would be
    an unvalidated artefact sitting inside a validated product."""
    spec = load_worldspec(_doc("prehistory"))
    report = validate(spec)
    assert report.ok, [f.message for f in report.failures]


def test_prehistory_preset_is_a_decade_and_is_calm():
    doc = _doc("prehistory")
    assert doc["horizon"]["quarters"] == 40
    # no crisis windows: the inherited past is unremarkable by construction,
    # so the decade the player actually plays is the one with the weather in it
    assert not doc.get("stress", {}).get("windows"), "the inherited decade carries no crisis"
```

(Adapt `load_worldspec` / `validate` to the real names in `src/ah/core/loader.py` and `src/ah/core/validator.py` — read them first; the two assertions are the contract.)

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_prehistory.py -v`; expected FAIL (no preset file).

- [ ] **Step 3: Build the preset**

Write `scripts/gen_prehistory_preset.py` in the style of the sibling `scripts/gen_presets.py` (read it first and follow its idiom — same JSON layout, same key order, deterministic, `newline="\n"`). Derive the document from an existing preset (e.g. `goldilocks`) and change exactly:
- `horizon.quarters` → 40, `horizon.start` → a quarter that reads as "before" (state your choice in the report);
- `world_id` → a fresh UUID in the presets' own block convention — read the other presets' ids and follow the pattern; the id must not collide with any existing preset;
- narrative title/summary → make plain what this is (e.g. title "The Inherited Decade", and a summary saying it is the plan's own past, not a playable world);
- regimes / factor conditions → a benign tiling that spans the horizon (V10/V11 require the regime structure to tile; V2 requires windows inside the horizon);
- stress windows → none;
- `engine_defaults.base_seed` → leave whatever the source preset had; Task 2 overrides the seed per world anyway.

Run it, commit the generated preset, and confirm the test passes.

- [ ] **Step 4: Verify** — `uv run pytest tests/test_prehistory.py -v` PASS; `uv run ruff check . --fix && uv run ruff format . && uv run pyright` clean.

- [ ] **Step 5: Commit**

```bash
git add src/ah/presets/prehistory.json scripts/gen_prehistory_preset.py tests/test_prehistory.py
git commit -m "feat(cio-04): the inherited decade - a validated calm world for pre-history"
```

---

### Task 2: The pre-history module

**Files:**
- Create: `src/ah/prehistory.py`
- Modify: `src/ah/play.py` (one optional keyword, default-preserving)
- Test: `tests/test_prehistory.py` (extend)

**Interfaces:**
- Consumes: `ah.core.engine.run_path`, `ah.core.numericworld.project_numeric`, `ah.play.simulate_play`, the Task 1 preset.
- Produces (Task 3 relies on these exact names):
  - `PREHISTORY_QUARTERS: int = 40`
  - `PREHISTORY_SEED_OFFSET: int = 999983` (a prime, deliberately not a multiple of the ensemble stride 7919, so a pre-history never collides with an ensemble member's tape)
  - `@dataclass(frozen=True) class PreHistory:` fields `months: int`, `nav_true_months: tuple[float, ...]`, `nav_reported_months: tuple[float, ...]`, `quarterly_returns_true: tuple[float, ...]`, `quarterly_returns_reported: tuple[float, ...]`, `market_paths: dict[str, tuple[float, ...]]` (per liquid asset, monthly *returns in percent*, not levels), `label: str`
  - `def build_prehistory(seed: int, terminal_nav_true: float, terminal_nav_reported: float, *, start_targets: Mapping[str, float] | None = None) -> PreHistory`

Scaling is what keeps this honest and cheap: the replayed institution produces a *shape*; multiplying the whole path by `terminal_nav / path[-1]` pins its endpoint to the book the game actually starts from, so the chart is continuous and month 0 is untouched. Same device as `_seed_ladder`'s rung scaling, and it must be stated on screen (Task 3's `preRunLabel`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_prehistory.py`)

```python
from ah.prehistory import PREHISTORY_QUARTERS, build_prehistory


def test_prehistory_is_deterministic_and_terminates_at_the_opening_book():
    a = build_prehistory(771204, 100.0, 98.0)
    b = build_prehistory(771204, 100.0, 98.0)
    assert a == b
    assert a.months == PREHISTORY_QUARTERS * 3
    assert abs(a.nav_true_months[-1] - 100.0) < 1e-9
    assert abs(a.nav_reported_months[-1] - 98.0) < 1e-9
    assert len(a.quarterly_returns_true) == PREHISTORY_QUARTERS


def test_prehistory_differs_by_seed():
    a = build_prehistory(771204, 100.0, 98.0)
    b = build_prehistory(19740101, 100.0, 98.0)
    assert a.nav_true_months != b.nav_true_months


def test_prehistory_market_paths_are_monthly_and_complete():
    p = build_prehistory(771204, 100.0, 98.0)
    assert p.market_paths, "no market series"
    for series in p.market_paths.values():
        assert len(series) == p.months


def test_prehistory_returns_are_not_degenerate():
    """The validator flags an exact zero in a return column as a possible
    unreached period; a flat pre-history would manufacture those."""
    p = build_prehistory(771204, 100.0, 98.0)
    assert len({round(r, 6) for r in p.quarterly_returns_true}) > 20
    assert all(r != 0.0 for r in p.quarterly_returns_true)
```

- [ ] **Step 2: Run to verify failure** — expected `ModuleNotFoundError: ah.prehistory`.

- [ ] **Step 3: Implement `src/ah/prehistory.py`**

```python
"""The inherited decade (cio-04) - what the plan did before the world began.

DISPLAY ONLY, by ruling. The opening book at world month 0 is exactly what
``ah.play._build_portfolio`` constructs and is not touched here; this module
produces the path that LEADS to it, scaled so it terminates on that book. The
alternative - an opening book that is the output of a simulated pre-decade -
would change every scored run and is a separate release decision.

Determinism: one integer seed, offset by a declared prime, through the same
toy engine as any other world.
"""
```

Implementation shape:

```python
PREHISTORY_QUARTERS = 40
#: Declared offset. Prime, and not a multiple of the ensemble stride (7919),
#: so an inherited decade can never coincide with an ensemble member's tape.
PREHISTORY_SEED_OFFSET = 999983


def _prehistory_paths(seed: int) -> EnginePaths:
    doc = json.loads((_PRESETS / "prehistory.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, seed + PREHISTORY_SEED_OFFSET)


def build_prehistory(seed, terminal_nav_true, terminal_nav_reported, *, start_targets=None):
    paths = _prehistory_paths(seed)
    result = simulate_play(paths, None, start_targets=start_targets)
    # monthly marks, both planes, straight off the replay
    true_months = [m for q in result.quarters for m in q.nav_true_months]
    rep_months = [m for q in result.quarters for m in q.nav_reported_months]
    # ... scale each series by terminal / series[-1] ...
    # ... quarterly returns from the UNSCALED series (scaling is level-only,
    #     so returns are identical either way - assert this in a test) ...
    # ... market_paths: {asset: tuple(paths.returns[asset])} for liquid assets ...
```

Guard the degenerate cases: a zero or non-finite terminal value, or a replay whose final NAV is zero, raises `ValueError` with a clear message rather than producing infinities.

The one `play.py` change: `simulate_play` currently always builds its own portfolio. This module needs nothing more than the default behavior, so **no change is required** — if you find you need one, stop and report rather than adding a parameter speculatively.

- [ ] **Step 4: Verify** — `uv run pytest tests/test_prehistory.py tests/test_play.py tests/test_engine.py -q` all green (the engine golden digest is the proof that nothing scored moved); ruff + pyright clean.

- [ ] **Step 5: Commit**

```bash
git add src/ah/prehistory.py tests/test_prehistory.py
git commit -m "feat(cio-04): build the inherited decade, pinned to the opening book"
```

---

### Task 3: Wire it into the view

**Files:**
- Modify: `src/ah/cioview.py`
- Test: `tests/test_cioview.py` (update the two tests that pin the old behavior), `tests/test_prehistory.py` (extend)

**Interfaces:**
- Consumes: Task 2's `build_prehistory`.
- Produces: `build_cio_view(..., prehistory: bool = True)`; `plan.history.values` prepended; `plan.history.worldStartIndex` set; `plan.preRunLabel` / `plan.worldStartLabel` emitted; market paths prepended and re-based; long return columns filled.

The five places to touch (all in `build_cio_view` / its helpers):

1. **`plan.history`** — prepend `PreHistory.nav_*_months` for the requested plane; `worldStartIndex = len(prehistory months)`.
2. **`plan.growthPct` / `netOfFlows`** — these must stay measured **from world month 0**, not from the inherited decade's start. Read them off the world-start index, not `values[0]`.
3. **`plan.windowLabel` / `preRunLabel` / `worldStartLabel`** — the window label stops being "Since inception"; `preRunLabel` states plainly what the hatched band is (e.g. "Inherited decade - simulated, scaled to the opening book"), `worldStartLabel` names the world's own start.
4. **`_markets`** — every series' `path` must stay exactly as long as `plan.history.values` (the validator couples them). Prepend the pre-history's monthly returns for each liquid asset and index the **combined** series to 100 **at the world-start index**, so the inherited decade reads as "where the plan came from" rather than silently re-basing the world's own charts. Update `returnsFootnote` to say so. Leave the correlation window computed on the **world's own** revealed months only (do not let the inherited decade into a correlation the player reads as this world's) — state that in `correlationNote`.
5. **Return windows** — `_quarterly_returns` currently starts at the run's opening NAV; extend the series it produces by prepending `PreHistory.quarterly_returns_*` so `_window_return`'s tail slicing fills 3Y/5Y/10Y. `_period_row`'s `last_q` must stay **world-relative** (YTD is a world-year concept). Do the same for `_class_returns`, whose per-class 3Y/5Y/10Y columns need the pre-history's per-asset tape.

Generated (non-toy) worlds: `build_prehistory` runs the toy engine on the calm preset. Rather than splice a toy past onto a `hier-flow` world, **skip pre-history when the world is not toy-v0** — `worldStartIndex` stays 0 there and the long columns stay null. Take the flag from the caller (Task 4 passes it); do not sniff the engine inside `cioview.py`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_prehistory.py`)

```python
from ah.cioview import build_cio_view, validate_cio_view


def test_view_with_prehistory_validates_and_fills_the_long_columns():
    v = _view(prehistory=True, revealed=12)   # one year into the world
    assert validate_cio_view(v) == []
    h = v["plan"]["history"]
    assert h["worldStartIndex"] == PREHISTORY_QUARTERS * 3
    assert len(h["values"]) == h["worldStartIndex"] + 12
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    for period in ("3Y", "5Y", "10Y"):
        assert v["performance"]["total"][idx[period]] is not None, period


def test_prehistory_is_continuous_at_the_world_boundary():
    """No step at month 0: the inherited path terminates on the opening book."""
    v = _view(prehistory=True, revealed=12)
    values = v["plan"]["history"]["values"]
    i = v["plan"]["history"]["worldStartIndex"]
    joint = abs(values[i] / values[i - 1] - 1.0)
    typical = median(abs(values[k] / values[k - 1] - 1.0) for k in range(1, i))
    assert joint < 5 * typical, "visible discontinuity at the world boundary"


def test_market_paths_stay_coupled_to_plan_history():
    v = _view(prehistory=True, revealed=12)
    n = len(v["plan"]["history"]["values"])
    for s in v["markets"]["returns"]:
        assert len(s["path"]) == n


def test_prehistory_off_reproduces_the_old_shape():
    v = _view(prehistory=False, revealed=60)
    assert v["plan"]["history"]["worldStartIndex"] == 0
    assert len(v["plan"]["history"]["values"]) == 60
```

(Write a local `_view(...)` helper mirroring the one in `tests/test_cioview.py`, with a `prehistory` argument.)

- [ ] **Step 2: Update the two tests that pin the superseded behavior**

In `tests/test_cioview.py`, `test_plan_history_is_monthly_and_truncated_at_the_pointer` and the `worldStartIndex == 0` assertions now describe the `prehistory=False` path. Update them to pass `prehistory=False` explicitly and extend each docstring with one line recording that cio-04 made pre-history the default and that this test now pins the opt-out. Do not delete them.

- [ ] **Step 3: Run to verify failure**, then implement the five touch points above.

- [ ] **Step 4: Verify** — `uv run pytest tests/test_prehistory.py tests/test_cioview.py tests/test_serve.py -q` green; ruff + pyright clean.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cio-04): the inherited decade lands on the plan chart and fills the long columns"
```

---

### Task 4: Endpoint, fixtures, and the app's committed goldens

**Files:**
- Modify: `src/ah/serve.py` (pass the toy-only flag)
- Modify: `scripts/gen_cio_fixture.py`
- Modify: `app/fixtures/cio-sample.*.json` (regenerated)
- Test: `tests/test_serve.py` (extend), `tests/test_cioview.py` (regeneration guard already exists)

- [ ] **Step 1: Write the failing endpoint test** (append to `tests/test_serve.py`, reusing the module `service` fixture)

```python
def test_cio_view_carries_the_inherited_decade(service):
    client, _db, rid = service
    sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
    v = client.get(f"/sessions/{sid}/cio").json()
    assert v["plan"]["history"]["worldStartIndex"] > 0
    assert v["plan"]["preRunLabel"]
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    assert v["performance"]["total"][idx["10Y"]] is not None
```

- [ ] **Step 2: Implement** — in `serve.py`'s `/sessions/{sid}/cio` handler, pass `prehistory=(ws.engine_defaults.generator_id == "toy-v0")` to `build_cio_view`, with a one-line comment saying why generated worlds opt out (a toy past spliced onto a generated world would be two engines in one chart).

- [ ] **Step 3: Regenerate the app fixtures** — `uv run python scripts/gen_cio_fixture.py`, then run the regeneration guard and the app suite:

```bash
uv run pytest tests/test_cioview.py -k fixtures -v
cd app && npm run test && npm run typecheck && npm run build
```

If an app test asserts a history length or a null long column, update it deliberately, with a docstring line recording that cio-04 changed the fixture — and report each one. The renderer itself must need no change; if you find yourself editing `CioDashboard.tsx`, STOP and report (the spec's promise for this WP is "dashboard unchanged").

- [ ] **Step 4: Verify** — the four commands above, all green.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cio-04): serve the inherited decade for toy worlds; regenerate the goldens"
```

---

### Task 5: DN-8's O-1 resolution, the realism register, and CHANGELOG

**Files:**
- Modify: `Instructions/DN-8-cio-dashboard-data-contract.md`
- Modify: `docs/engine-realism-register.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: DN-8** — in the Resolutions table, replace the O-1 row's "built as its own WP (cio-04)" with what was actually built, verbatim:

```markdown
| ⚑ O-1 | **DELIVERED 2026-08-14 (cio-04), display-only.** A validated calm
decade (`src/ah/presets/prehistory.json`) is run through the same engine under
a declared seed offset, the institution is replayed over it hold-course, and
the path is **scaled to terminate exactly on the opening book** - so the
chart is continuous and the game's month 0 is untouched. `worldStartIndex`
and the long return columns are live for toy worlds; generated worlds opt out
(a toy past spliced onto a generated world would be two engines in one chart).
**Not built, deliberately:** an opening book that is the *output* of the
pre-decade. That changes every scored run and restarts leaderboards - a
release event and the owner's call, not a rendering decision. |
```

- [ ] **Step 2: The realism register** — `docs/engine-realism-register.md` records where the engine is faithful to its plan but not to an allocator's expectations. Add an entry in the file's own format for the standing gap: the inherited decade is a *consistent simulated* past scaled to an endpoint, not the actual history that produced this book, and the opening weights are still at target by construction rather than drifted. Say what a fix would invalidate (leaderboards; `PLAY_ALPHA_VERSION`).

- [ ] **Step 3: CHANGELOG** — under `[Unreleased]` → `### Added`:

```markdown
- **The inherited decade (cio-04), 2026-08-14.** The CIO dashboard's plan
  chart now opens ten years before the world does, and the 3Y/5Y/10Y columns
  hold real numbers from the first quarter of play - DN-8's O-1 option A.
  A validated calm world (`prehistory.json`) runs through the same engine
  under a declared seed offset (999983, prime, never colliding with the
  ensemble stride); the institution is replayed over it and the path scaled
  to terminate on the opening book, so the join is continuous and **no scored
  number moves**: `PLAY_ALPHA_VERSION` and `TOY_ENGINE_VERSION` unchanged, the
  golden digest untouched, every leaderboard row still comparable. Market
  paths prepend in lockstep with the plan history (the validator couples
  their lengths) and index to 100 at world start, not at the inherited
  decade's start. Generated worlds opt out. The renderer needed no change -
  it has supported `worldStartIndex` since it was vendored.
```

- [ ] **Step 4: Commit**

```bash
git add Instructions/DN-8-cio-dashboard-data-contract.md docs/engine-realism-register.md CHANGELOG.md
git commit -m "docs(cio-04): O-1 resolved as delivered - display-only, scored surface untouched"
```

---

## Controller-owned closing steps

1. Full pytest gate to a log → read the `EXIT:` line and pass count → `check_gate.py` → battery report.
2. Browser check: the hatched pre-run band renders, the join is visually continuous, the long columns hold numbers at Y1 Q1.
3. Re-verify `main`, `--no-ff` merge, plain push.

## Self-review notes (applied)

- The spec's cio-04 row promises "dashboard unchanged" — Task 4 makes that a stop condition rather than a hope.
- The engine's horizon-coupled draws are why Task 1 builds a separate world instead of lengthening the world's own; the plan says so where an implementer would otherwise try the cheaper thing.
- The validator's plan-history↔market-path length coupling is called out in Task 3 as the one hard constraint, and Task 3's tests pin it.
- `zeroWhereNull` would fire on a flat pre-history; Task 2's degenerate-returns test prevents one being built.
