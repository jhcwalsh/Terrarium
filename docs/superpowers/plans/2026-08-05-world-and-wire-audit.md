# World Register and Wire Audit (`ah audit`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `ah audit` command producing one self-contained HTML page that lists every world that exists, checks each against its own declarations, and reconciles every generated wire item against the tape it claims to describe.

**Architecture:** A new package `src/ah/audit/` with three computing/rendering modules (`register.py`, `wire.py`, `page.py`) plus a thin `__init__.py` public API. Two read-only helpers are added to the store. Nothing else in the repo changes.

**Tech Stack:** Python 3.12, numpy, dataclasses, `re` for parsing rendered artifact text, inline HTML/CSS (no JS, no external assets), pytest, Typer for the CLI.

**Design spec:** `docs/superpowers/specs/2026-08-05-world-and-wire-audit-design.md`

## Building a world in a test — the verified idiom

There is **no `ah.presets` module and no `build_preset` helper**; presets are JSON files under `src/ah/presets/`. Every test that needs a world opens with this block:

```python
import json
from pathlib import Path

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 771204


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))
```

The four preset stems are exactly `stagflation`, `goldilocks`, `deflation_bust`, `reflation_boom` — note `reflation_boom`, not `reflation`.

## Reference: exact formats the templates emit

Every check in Tasks 4-5 depends on these. All verified against `src/ah/artifacts/templates.py` and `src/ah/feed.py`:

| producer | exact rendered form | tape source |
|---|---|---|
| `fmt_pct(x, d=1)` | `f"{x*100:+.1f}%"` — **always signed** | — |
| `fmt_level_pct(x, d)` | `f"{x*100:.{d}f}%"` — unsigned | — |
| `fmt_money(x)` | `f"{x:,.1f}"` — thousands separators | — |
| CPI release row | `value=f"{v:.1f}%"`, `prior` same | `paths.inflation[m]` (already percent) |
| spread release row | `value=f"{v:.0f}bp"`, `prior` same | `paths.spread[m]` (already bp) |
| CB statement, quiet | `f"The policy rate stands at {fmt_level_pct(r,2)}, little changed over the quarter."` | `r = paths.rate[m]/100.0` |
| CB statement, move | `f"Policy conditions {verb} over the quarter; the rate stands at {fmt_level_pct(r,2)} ({direction} {bp}bp)."` | `bp = round(abs(r - r_prev)*10000)`, `verb` = tightened/eased, `direction` = up/down |
| quarterly statement | `lines[0] = f"Return for the quarter: {fmt_pct(q)} ({phrase})."`, `lines[1] = f"Year to date: {fmt_pct(ytd)}."`, `lines[2] = f"Total value: {fmt_money(v)}."`, `lines[3] = f"Net flow for the quarter: {fmt_money(0.0)}."` | hold-course `simulate_institution(paths, None)` |
| crisis digest | `title = f"Morning digest — {dateline}"`, `lines = ["- Stress regime begins: crisis window opens"]` | `paths.crisis` 0→1 transition |
| newspaper | `lead` + up to 3 `stories` | `headline_events(paths)` |

Other facts the checks rely on:

- `_dateline(m) = f"Y{m//12+1}M{m%12+1}"`
- quarter-closing months are `[m for m in range(nm) if (m+1) % 3 == 0]`
- CB previous rate is `paths.rate[m-3]/100.0`, falling back to the current rate when `m-3 < 0`
- quarterly `return_q` uses `twin.total[m-3]` as the base, falling back to `100.0` when `m-3 < 0`; YTD uses `twin.total[(m//12)*12 - 1]`, falling back to `100.0` when that index is negative
- peer bands are `np.percentile(peer_q, (5, 25, 50, 75, 95))` over `n_peer_paths` sibling paths at `base_seed + 7919*k`, where `peer_q = peer_totals[:, m] / peer_totals[:, m-3] - 1`
- `_percentile_from_bands` returns exactly one of six phrases: `"below the 5th percentile of peers"`, `"in the bottom quartile of peers (5th-25th percentile)"`, `"below the peer median (25th-50th percentile)"`, `"above the peer median (50th-75th percentile)"`, `"in the top quartile of peers (75th-95th percentile)"`, `"above the 95th percentile of peers"`
- the eight legal regime names are `expansion, slowdown, recession, crisis, recovery, stagflation, reflation, deflation_boom`
- a regime segment `{regime, from_quarter, to_quarter}` is **inclusive**, so it covers months `from_quarter*3` through `(to_quarter+1)*3 - 1`

## Global Constraints

- **Admin only.** The package reads and computes; it writes nothing except the output file the CLI names. Not in the pre-registration seal. Never touches the scored path. No number it computes reaches a player.
- **Determinism.** Same worlds and seed → byte-identical page. No RNG in this package, no clock, no iteration over an unordered set. Ensemble seeds are `base_seed + 7919*k`.
- **No network** anywhere in tests (`pytest-socket`, `--disable-socket`).
- **No pandas** — numpy only.
- **Do not edit `schemas/` or `mappings/`** — read-only vendored and sealed truth.
- **Do not edit any artifact template.** A failing reconciliation is recorded as a finding; changing the template is a separate, owner-decided change.
- **Do not bump** `PLAY_ALPHA_VERSION` or `ah.eval.decision_metrics.DECISION_ALPHA_VERSION`.
- **The page must be entirely self-contained:** no external stylesheet, CDN, `<script>`, `src=`, or any network reference.
- **All text reaching HTML must be escaped.**
- **`src/ah/cli.py` must NOT gain `from __future__ import annotations`** — Typer resolves parameter hints at runtime and it breaks the CLI.
- **CLI-echoed strings stay ASCII** (Windows console is cp1252). The HTML file may use Unicode freely. Write the page with `newline="\n"`.
- Every task ends: `uv run ruff check . --fix`, `uv run ruff format .`, `uv run pyright` clean before commit.
- `uv run ruff format .` mangles embedded Python code fences in tracked markdown under `docs/` (it rewrites keyword arguments as tuple assignments). **`git restore` those; never stage them.**
- One WP, one branch; `--no-ff` merge to `main` only when the full gate is green.

---

### Task 1: Read-only store helpers

**Files:**
- Modify: `src/ah/store/worlds.py` (append)
- Modify: `src/ah/store/runrecords.py` (append)
- Test: `tests/test_store_listing.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `list_worlds(conn) -> list[dict[str, Any]]` with keys `world_id`, `spec_version`, `status`, `created_at`, `doc`; and `latest_run_seed(conn, world_id) -> int | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_store_listing.py`:

```python
"""Listing helpers for the audit register.

The store could fetch a world by id and save one, and nothing else — there
was no way to ask what worlds exist, which is why the register needed these.
Both are read-only by construction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ah.store.db import connect, init_db
from ah.store.runrecords import latest_run_seed, save_run_record
from ah.store.worlds import list_worlds, save_world

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "src" / "ah" / "presets" / "stagflation.json"


def _doc(world_id: str) -> dict[str, Any]:
    doc = json.loads(PRESET.read_text(encoding="utf-8"))
    doc["world_id"] = world_id
    return doc


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    init_db(c)
    return c


def test_list_worlds_is_empty_on_a_fresh_store(conn):
    assert list_worlds(conn) == []


def test_list_worlds_returns_every_world_with_its_parsed_document(conn):
    save_world(conn, _doc("00000000-0000-4000-9000-00000000000a"), created_at="2026-01-01T00:00:00+00:00")
    save_world(conn, _doc("00000000-0000-4000-9000-00000000000b"), created_at="2026-01-02T00:00:00+00:00")
    rows = list_worlds(conn)
    assert len(rows) == 2
    assert set(rows[0]) == {"world_id", "spec_version", "status", "created_at", "doc"}
    assert rows[0]["doc"]["world_id"] == rows[0]["world_id"]


def test_list_worlds_is_ordered_oldest_first_and_stable(conn):
    save_world(conn, _doc("00000000-0000-4000-9000-00000000000b"), created_at="2026-01-02T00:00:00+00:00")
    save_world(conn, _doc("00000000-0000-4000-9000-00000000000a"), created_at="2026-01-01T00:00:00+00:00")
    ids = [r["world_id"] for r in list_worlds(conn)]
    assert ids == sorted(ids)  # created_at ordering coincides with id order here
    assert ids == [r["world_id"] for r in list_worlds(conn)]  # stable across calls


def test_latest_run_seed_is_none_when_a_world_has_never_been_run(conn):
    save_world(conn, _doc("00000000-0000-4000-9000-00000000000a"), created_at="2026-01-01T00:00:00+00:00")
    assert latest_run_seed(conn, "00000000-0000-4000-9000-00000000000a") is None
```

The `save_run_record` import and a `latest_run_seed` positive-path test are added in Step 3 once you have read that function's real signature — do not guess it.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_store_listing.py -v`
Expected: FAIL — `cannot import name 'list_worlds' from 'ah.store.worlds'`.

- [ ] **Step 3: Read the neighbouring signatures before implementing**

```bash
grep -n "^def \|^from \|^import " src/ah/store/runrecords.py | head -20
grep -n "def connect\|def init_db" src/ah/store/db.py
```

Use the real `save_run_record` signature to add one positive test: save a world, save two run records for it with different `created_at`, and assert `latest_run_seed` returns the seed of the newer one. If `save_run_record` needs arguments the test cannot easily supply, insert the two rows with a direct `conn.execute` against the `run_records` columns (`run_id, world_id, resolved_engine, seed, n_paths, overrides, outputs_digest, summary_stats, created_at`) and say so in a comment.

- [ ] **Step 4: Implement `list_worlds`**

Append to `src/ah/store/worlds.py`:

```python
def list_worlds(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every world in the store, oldest first, with its document parsed.

    Read-only. Exists because the repository could fetch a world by id and
    save one, and nothing could ask what worlds exist — which made the
    population invisible to any review surface. Ordering is
    ``(created_at, world_id)`` so the result is stable across calls even
    when two worlds share a timestamp; a register whose row order moved
    between runs could not be diffed.
    """
    rows = conn.execute(
        "SELECT world_id, spec_version, status, json, created_at FROM worlds "
        "ORDER BY created_at, world_id"
    ).fetchall()
    return [
        {
            "world_id": row["world_id"],
            "spec_version": row["spec_version"],
            "status": row["status"],
            "created_at": row["created_at"],
            "doc": json.loads(row["json"]),
        }
        for row in rows
    ]
```

- [ ] **Step 5: Implement `latest_run_seed`**

Append to `src/ah/store/runrecords.py` (add `import sqlite3` and `from typing import Any` only if they are not already imported):

```python
def latest_run_seed(conn: sqlite3.Connection, world_id: str) -> int | None:
    """The seed of a world's most recent run, or None if it has never run.

    The audit reconciles wire text against a tape, so it must name the tape
    it used. Where a world has been run, the honest tape is the one that was
    actually played; where it has not, the caller supplies a default.
    """
    row = conn.execute(
        "SELECT seed FROM run_records WHERE world_id = ? "
        "ORDER BY created_at DESC, run_id DESC LIMIT 1",
        (world_id,),
    ).fetchone()
    return int(row["seed"]) if row is not None else None
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_store_listing.py -v`
Expected: PASS.

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/store/worlds.py src/ah/store/runrecords.py tests/test_store_listing.py
git commit -m "feat: list_worlds and latest_run_seed, read-only store helpers

The store could fetch a world by id and save one, and nothing could ask
what worlds exist. The audit register needs the population, and needs to
name the tape each row was checked against."
```

---

### Task 2: World discovery — the register rows

**Files:**
- Create: `src/ah/audit/__init__.py`, `src/ah/audit/register.py`
- Test: `tests/test_audit_register.py` (create)

**Interfaces:**
- Consumes: `list_worlds`, `latest_run_seed` from Task 1.
- Produces:
  - `WorldRow` frozen dataclass: `world_id, title, source, status, spec_version, created_at, generator_id, horizon_months, regime_mode, seed, error`
  - `discover_worlds(conn, *, presets_dir: Path, default_seed: int) -> list[WorldRow]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_register.py`:

```python
"""World discovery for the audit register.

Two populations that nobody had ever seen as one: the SQLite store, and the
preset JSON files the app actually plays.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.audit.register import WorldRow, discover_worlds
from ah.store.db import connect, init_db
from ah.store.worlds import save_world

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 771204


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    init_db(c)
    return c


def test_presets_are_discovered_even_with_an_empty_store(conn):
    rows = discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED)
    assert {r.source for r in rows} == {"preset"}
    assert {r.title for r in rows}  # every preset has a narrative title
    assert len(rows) == 4


def test_store_worlds_and_presets_appear_in_one_register(conn):
    doc = json.loads((PRESETS / "stagflation.json").read_text(encoding="utf-8"))
    doc["world_id"] = "00000000-0000-4000-9000-00000000000a"
    save_world(conn, doc, created_at="2026-01-01T00:00:00+00:00")
    rows = discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED)
    assert {r.source for r in rows} == {"store", "preset"}
    assert len(rows) == 5


def test_a_world_with_no_run_record_uses_the_default_seed(conn):
    rows = discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED)
    assert all(r.seed == SEED for r in rows)


def test_a_malformed_preset_is_listed_with_its_error_not_raised(conn, tmp_path):
    bad = tmp_path / "presets"
    bad.mkdir()
    (bad / "broken.json").write_text('{"world_id": "nope"}', encoding="utf-8")
    rows = discover_worlds(conn, presets_dir=bad, default_seed=SEED)
    assert len(rows) == 1
    assert rows[0].error is not None
    assert rows[0].source == "preset"
    # a malformed world is exactly what the register exists to show
    assert rows[0].world_id == "broken.json"


def test_rows_are_ordered_deterministically(conn):
    a = discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED)
    b = discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED)
    assert [r.world_id for r in a] == [r.world_id for r in b]


def test_row_carries_the_engine_and_horizon_facts_a_reviewer_needs(conn):
    row = next(r for r in discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED) if r.error is None)
    assert isinstance(row, WorldRow)
    assert row.generator_id
    assert row.horizon_months > 0
    assert row.regime_mode in {"sequence", "transition_matrix", "unconditional"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_audit_register.py -v`
Expected: FAIL — `No module named 'ah.audit'`.

- [ ] **Step 3: Create the package**

Create `src/ah/audit/__init__.py`:

```python
"""The world register and wire audit — `ah audit`.

Admin tooling: it reads worlds and the artifacts they generate, computes,
and writes nothing but the page the CLI names. Not in the pre-registration
seal, never on the scored path, and no number here reaches a player.

Two panes, two references, neither of which any existing surface uses:

- the **register** checks a world against ITS OWN declarations — the regime
  segments its spec pins, and how distinguishable it is from its siblings;
- the **wire audit** checks each generated artifact against the tape it
  claims to describe.

`ah credibility` judges a world's numbers against declared priors, `ah
inspect` draws one run's figures, and `ah battery` tests stylized facts
against sealed thresholds. None of them reads what the wire actually says.
"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 4: Implement `register.py`'s discovery half**

Create `src/ah/audit/register.py`:

```python
"""World discovery and cross-world comparison for the audit page."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ah.core.numericworld import NumericWorld, project_numeric
from ah.core.worldspec import WorldSpec
from ah.store.runrecords import latest_run_seed
from ah.store.worlds import list_worlds

__all__ = ["WorldRow", "discover_worlds"]


@dataclass(frozen=True)
class WorldRow:
    """One row of the register: a world that exists, and where it came from.

    ``error`` is set when the document could not be validated. Such a row is
    still listed — a malformed world is precisely what a register exists to
    surface, and dropping it would hide the only case that matters.
    """

    world_id: str
    title: str
    source: str  # "store" | "preset"
    status: str
    spec_version: str
    created_at: str
    generator_id: str
    horizon_months: int
    regime_mode: str
    seed: int
    error: str | None = None
    world: NumericWorld | None = None
    doc: dict[str, Any] | None = None


def _row_from_doc(
    doc: dict[str, Any], *, source: str, created_at: str, seed: int, fallback_id: str
) -> WorldRow:
    try:
        spec = WorldSpec.model_validate(doc)
        world = project_numeric(spec)
    except Exception as exc:  # noqa: BLE001 - the register reports, never raises
        return WorldRow(
            world_id=str(doc.get("world_id") or fallback_id),
            title=str((doc.get("narrative") or {}).get("title") or ""),
            source=source,
            status=str(doc.get("status") or ""),
            spec_version=str(doc.get("spec_version") or ""),
            created_at=created_at,
            generator_id="",
            horizon_months=0,
            regime_mode="",
            seed=seed,
            error=f"{type(exc).__name__}: {exc}",
        )
    narrative = doc.get("narrative") or {}
    horizon = doc.get("horizon") or {}
    quarters = int(horizon.get("quarters") or 0)
    return WorldRow(
        world_id=doc["world_id"],
        title=str(narrative.get("title") or ""),
        source=source,
        status=str(doc.get("status") or ""),
        spec_version=str(doc.get("spec_version") or ""),
        created_at=created_at,
        generator_id=str((doc.get("engine_defaults") or {}).get("generator_id") or ""),
        horizon_months=quarters * 3,
        regime_mode=str((doc.get("regimes") or {}).get("mode") or ""),
        seed=seed,
        world=world,
        doc=doc,
    )


def discover_worlds(
    conn: sqlite3.Connection, *, presets_dir: Path, default_seed: int
) -> list[WorldRow]:
    """Every world that exists: store rows first, then preset files.

    Order is deterministic — the store's own ``(created_at, world_id)``
    ordering, then presets sorted by filename — so two runs of the page can
    be diffed.
    """
    rows: list[WorldRow] = []
    for record in list_worlds(conn):
        seed = latest_run_seed(conn, record["world_id"])
        rows.append(
            _row_from_doc(
                record["doc"],
                source="store",
                created_at=record["created_at"],
                seed=default_seed if seed is None else seed,
                fallback_id=record["world_id"],
            )
        )
    for path in sorted(presets_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rows.append(
                WorldRow(
                    world_id=path.name,
                    title="",
                    source="preset",
                    status="",
                    spec_version="",
                    created_at="",
                    generator_id="",
                    horizon_months=0,
                    regime_mode="",
                    seed=default_seed,
                    error=f"JSONDecodeError: {exc}",
                )
            )
            continue
        rows.append(
            _row_from_doc(
                doc,
                source="preset",
                created_at="",
                seed=default_seed,
                fallback_id=path.name,
            )
        )
    return rows
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_register.py -v`
Expected: PASS, 6 tests. If `test_a_malformed_preset_is_listed_with_its_error_not_raised` fails because the fallback id is not used, check that `doc.get("world_id")` is falsy for that fixture — the test writes `{"world_id": "nope"}`, so adjust the assertion to `rows[0].world_id == "nope"` and note it in a comment. Do not weaken the error assertion.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/audit/ tests/test_audit_register.py
git commit -m "feat: world discovery across both populations

The store and the preset files, in one register, with malformed worlds
listed rather than raised."
```

---

### Task 3: Declared-versus-realized, and distinguishability

**Files:**
- Modify: `src/ah/audit/register.py` (append)
- Test: `tests/test_audit_compare.py` (create)

**Interfaces:**
- Consumes: `WorldRow` from Task 2.
- Produces:
  - `RegimeExpectation` frozen dataclass: `inflation, spread, crisis_share, why`
  - `REGIME_EXPECTATIONS: dict[str, RegimeExpectation]`
  - `SegmentCheck` frozen dataclass: `regime, from_month, to_month, inflation, spread, crisis_share, verdict, note`
  - `declared_vs_realized(row: WorldRow, paths: EnginePaths) -> list[SegmentCheck]`
  - `WORLD_SCALES: dict[str, float]`, `DISTINGUISHABILITY_THRESHOLD: float`
  - `world_vector(paths: EnginePaths) -> dict[str, float]`
  - `PairDistance` frozen dataclass: `a, b, distance, expected_lineage, flagged`
  - `distinguishability(rows, vectors) -> list[PairDistance]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_compare.py`:

```python
"""Worlds checked against their own declarations, and against each other."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ah.audit.register import (
    DISTINGUISHABILITY_THRESHOLD,
    REGIME_EXPECTATIONS,
    WORLD_SCALES,
    declared_vs_realized,
    discover_worlds,
    distinguishability,
    world_vector,
)
from ah.core.engine import run_path
from ah.store.db import connect, init_db

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 771204


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    init_db(c)
    return c


@pytest.fixture()
def rows(conn):
    return [r for r in discover_worlds(conn, presets_dir=PRESETS, default_seed=SEED) if r.error is None]


def test_every_expectation_names_a_legal_regime_and_says_why():
    legal = {
        "expansion", "slowdown", "recession", "crisis",
        "recovery", "stagflation", "reflation", "deflation_boom",
    }
    assert set(REGIME_EXPECTATIONS) <= legal
    for name, exp in REGIME_EXPECTATIONS.items():
        assert exp.why.strip(), name
        assert any((exp.inflation, exp.spread, exp.crisis_share)), name


def test_segments_tile_the_horizon_and_report_realized_numbers(rows):
    row = next(r for r in rows if r.regime_mode == "sequence")
    paths = run_path(row.world, row.seed)
    checks = declared_vs_realized(row, paths)
    assert checks
    assert checks[0].from_month == 0
    assert checks[-1].to_month == row.horizon_months - 1
    for c in checks:
        assert c.verdict in {"consistent", "inconsistent", "not asserted"}


def test_a_regime_with_no_tape_signature_is_stated_not_silently_skipped(rows):
    """expansion/slowdown/recovery/reflation carry no unambiguous signature at
    this engine's fidelity — the row must say so rather than render blank."""
    row = next(r for r in rows if r.regime_mode == "sequence")
    paths = run_path(row.world, row.seed)
    for c in declared_vs_realized(row, paths):
        if c.regime not in REGIME_EXPECTATIONS:
            assert c.verdict == "not asserted"
            assert c.note.strip()


def test_a_stagflation_segment_over_a_cold_tape_is_inconsistent(rows):
    """The check must be able to FAIL — drive it with a tape that contradicts
    the label rather than only with one that agrees."""
    row = next(r for r in rows if r.regime_mode == "sequence")
    paths = run_path(row.world, row.seed)
    cold = type(paths)(
        months=paths.months,
        seed=paths.seed,
        rate=paths.rate,
        spread=paths.spread,
        inflation=np.zeros_like(paths.inflation),
        crisis=paths.crisis,
        returns=paths.returns,
        reported=paths.reported,
    )
    checks = declared_vs_realized(row, cold)
    stag = [c for c in checks if c.regime == "stagflation"]
    if stag:
        assert all(c.verdict == "inconsistent" for c in stag)


def test_world_vector_covers_every_declared_scale(rows):
    paths = run_path(rows[0].world, rows[0].seed)
    assert set(world_vector(paths)) == set(WORLD_SCALES)


def test_a_world_is_zero_distance_from_itself(rows):
    paths = run_path(rows[0].world, rows[0].seed)
    v = world_vector(paths)
    pairs = distinguishability([rows[0], rows[0]], [v, v])
    assert pairs[0].distance == pytest.approx(0.0)
    assert pairs[0].flagged


def test_distinct_presets_are_not_flagged_as_duplicates(rows):
    vectors = [world_vector(run_path(r.world, r.seed)) for r in rows]
    pairs = distinguishability(rows, vectors)
    flagged = [p for p in pairs if p.flagged and not p.expected_lineage]
    assert not flagged, f"presets should be distinguishable: {flagged}"
    assert DISTINGUISHABILITY_THRESHOLD > 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_audit_compare.py -v`
Expected: FAIL — `cannot import name 'REGIME_EXPECTATIONS'`.

- [ ] **Step 3: Implement the declared-versus-realized half**

Append to `src/ah/audit/register.py` (add `import numpy as np` and `from ah.core.engine import EnginePaths` to the imports):

```python
@dataclass(frozen=True)
class RegimeExpectation:
    """What the TAPE must show for a declared regime label to be believable.

    Declared priors, editable — the same idiom as ``credibility.PLAUSIBLE``.
    Ranges are inclusive and in the tape's own units: inflation and rate in
    percent, spread in bp, ``crisis_share`` as a fraction of the segment's
    months with the crisis flag on.
    """

    inflation: tuple[float, float] | None = None
    spread: tuple[float, float] | None = None
    crisis_share: tuple[float, float] | None = None
    why: str = ""


#: Only regimes with a signature this engine's tape can actually witness are
#: asserted. expansion / slowdown / recovery / reflation differ from one
#: another mainly in growth, which the tape does not carry as a series, so
#: they are reported with their realized numbers and explicitly NOT judged.
#: Saying so beats inventing a threshold that would flag noise.
REGIME_EXPECTATIONS: dict[str, RegimeExpectation] = {
    "stagflation": RegimeExpectation(
        inflation=(4.0, 25.0),
        why="a segment labelled stagflation must actually run hot inflation",
    ),
    "deflation_boom": RegimeExpectation(
        inflation=(-5.0, 1.5),
        why="deflation means falling or near-zero prices",
    ),
    "crisis": RegimeExpectation(
        crisis_share=(0.5, 1.0),
        spread=(600.0, 5000.0),
        why="a declared crisis segment should carry the crisis flag and wide spreads",
    ),
    "recession": RegimeExpectation(
        spread=(450.0, 5000.0),
        why="recessionary credit is repriced wider",
    ),
}


@dataclass(frozen=True)
class SegmentCheck:
    """One declared regime segment, against what the tape did over its months."""

    regime: str
    from_month: int
    to_month: int
    inflation: float
    spread: float
    crisis_share: float
    verdict: str  # "consistent" | "inconsistent" | "not asserted"
    note: str


def _within(value: float, band: tuple[float, float] | None) -> bool:
    return band is None or band[0] <= value <= band[1]


def declared_vs_realized(row: WorldRow, paths: EnginePaths) -> list[SegmentCheck]:
    """What the spec pinned, against what the tape delivered over those months.

    Only meaningful in ``regimes.mode == "sequence"``: a transition-matrix
    world draws its own regime sequence per path, so there is no single
    declared assignment to compare against, and an unconditional world has no
    regimes at all. Both return an empty list; the page states the reason.
    """
    doc = row.doc or {}
    regimes = doc.get("regimes") or {}
    if regimes.get("mode") != "sequence":
        return []
    out: list[SegmentCheck] = []
    for segment in regimes.get("sequence") or []:
        lo = int(segment["from_quarter"]) * 3
        hi = min((int(segment["to_quarter"]) + 1) * 3 - 1, paths.months - 1)
        if hi < lo:
            continue
        window = slice(lo, hi + 1)
        infl = float(np.mean(paths.inflation[window]))
        spread = float(np.mean(paths.spread[window]))
        crisis = float(np.mean(paths.crisis[window]))
        name = str(segment["regime"])
        expectation = REGIME_EXPECTATIONS.get(name)
        if expectation is None:
            verdict, note = (
                "not asserted",
                f"'{name}' has no signature this tape can witness "
                "(it differs from its neighbours mainly in growth, which the "
                "engine does not emit as a series) - reported, not judged",
            )
        else:
            ok = (
                _within(infl, expectation.inflation)
                and _within(spread, expectation.spread)
                and _within(crisis, expectation.crisis_share)
            )
            verdict = "consistent" if ok else "inconsistent"
            note = expectation.why
        out.append(
            SegmentCheck(
                regime=name,
                from_month=lo,
                to_month=hi,
                inflation=infl,
                spread=spread,
                crisis_share=crisis,
                verdict=verdict,
                note=note,
            )
        )
    return out
```

- [ ] **Step 4: Implement distinguishability**

Append to `src/ah/audit/register.py`:

```python
#: Each statistic is divided by a DECLARED scale in its own units, not
#: z-scored across the population. Six worlds is far too small a sample for a
#: z-score to mean anything, and a fixed scale keeps the distance
#: interpretable and stable as worlds are added. A scale is "how much of this
#: statistic constitutes one unit of difference between two worlds".
WORLD_SCALES: dict[str, float] = {
    "mean_inflation": 2.0,        # percentage points
    "terminal_rate": 1.5,         # percentage points
    "mean_spread": 150.0,         # bp
    "crisis_months": 6.0,         # months
    "worst_equity_drawdown": 0.10,  # fraction
    "equity_annualized": 0.03,    # fraction per year
}

#: Below this normalised Euclidean distance two worlds are near-duplicates.
DISTINGUISHABILITY_THRESHOLD = 1.0


def world_vector(paths: EnginePaths) -> dict[str, float]:
    """The decade statistics that make one world different from another."""
    equity = np.asarray(paths.returns["equity"], dtype=float)
    growth = np.cumprod(1.0 + equity / 100.0)
    peak = np.maximum.accumulate(growth)
    years = max(paths.months / 12.0, 1e-9)
    return {
        "mean_inflation": float(np.mean(paths.inflation)),
        "terminal_rate": float(paths.rate[-1]),
        "mean_spread": float(np.mean(paths.spread)),
        "crisis_months": float(np.sum(paths.crisis)),
        "worst_equity_drawdown": float(np.max(1.0 - growth / peak)),
        "equity_annualized": float(growth[-1] ** (1.0 / years) - 1.0),
    }


@dataclass(frozen=True)
class PairDistance:
    """How far apart two worlds are, and whether that is expected."""

    a: str
    b: str
    distance: float
    expected_lineage: bool
    flagged: bool


def _is_lineage_pair(x: WorldRow, y: WorldRow) -> bool:
    """Two rows that are the same scenario in different engine-version blocks.

    The repo deliberately mints a new ``world_id`` block when the engine's
    numbers change (so scores from two engines cannot share a leaderboard
    row), which means near-identical siblings are the CONVENTION, not drift.
    A register that reported its own versioning scheme as a defect would be
    ignored within a week.
    """
    if x.doc is None or y.doc is None:
        return False
    parents = {
        ((x.doc.get("provenance") or {}).get("source") or {}).get("parent_world_id"),
        ((y.doc.get("provenance") or {}).get("source") or {}).get("parent_world_id"),
    }
    if x.world_id in parents or y.world_id in parents:
        return True
    return bool(x.title) and x.title == y.title and x.world_id != y.world_id


def distinguishability(
    rows: list[WorldRow], vectors: list[dict[str, float]]
) -> list[PairDistance]:
    """Pairwise normalised distance between every pair of worlds."""
    out: list[PairDistance] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            total = 0.0
            for key, scale in WORLD_SCALES.items():
                delta = (vectors[i][key] - vectors[j][key]) / scale
                total += delta * delta
            distance = float(np.sqrt(total))
            lineage = _is_lineage_pair(rows[i], rows[j])
            out.append(
                PairDistance(
                    a=rows[i].world_id,
                    b=rows[j].world_id,
                    distance=distance,
                    expected_lineage=lineage,
                    flagged=distance < DISTINGUISHABILITY_THRESHOLD,
                )
            )
    return out
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_compare.py -v`
Expected: PASS, 7 tests.

`test_a_world_is_zero_distance_from_itself` passes the same row twice, so `_is_lineage_pair` sees equal `world_id` values; the title branch requires `x.world_id != y.world_id`, so `expected_lineage` is False and `flagged` is True — assert only what the test above asserts.

If `test_distinct_presets_are_not_flagged_as_duplicates` fails, do **not** raise the threshold to silence it. Print each pair's distance and per-component contribution, decide from the numbers whether two presets are genuinely near-duplicates (a real finding worth reporting to the owner) or whether a scale is badly chosen, and record the reasoning in your report.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/audit/register.py tests/test_audit_compare.py
git commit -m "feat: declared-vs-realized regime checks and distinguishability

Only regimes with a signature the tape can witness are judged; the rest
are reported and explicitly not asserted. Distances use declared scales
rather than z-scores, and same-scenario engine-version pairs are labelled
as lineage rather than reported as drift."
```

---

### Task 4: Wire parsers, and the release/CB checks

**Files:**
- Create: `src/ah/audit/wire.py`
- Test: `tests/test_audit_wire_parsing.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `Finding` frozen dataclass: `month, item_type, check, ok, expected, actual, detail`
  - `parse_level_pct(text) -> float | None`, `parse_signed_pct(text) -> float | None`, `parse_bp(text) -> float | None`, `parse_money(text) -> float | None`
  - `close_enough(parsed, expected, decimals) -> bool`
  - `check_release_page(item, paths) -> list[Finding]`
  - `check_cb_statement(item, paths) -> list[Finding]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_wire_parsing.py`:

```python
"""Parsing rendered wire text, and reconciling it against the tape.

Every template renders its numbers into prose - central_bank_statement
returns sentences, release_page rows carry pre-formatted strings, and no
payload carries a raw float. So the audit re-parses what was rendered. That
is forced by the data, and it is also the check worth having: the template
inputs come straight off EnginePaths and are trivially correct, while both
real defects found so far (ER-2's phantom decisions, the percent/decimal
unit bug) lived in the formatting.

Every check below is proved to FAIL against a corrupted item, not merely to
pass against a good one.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.artifacts.templates import central_bank_statement, release_page
from ah.audit.wire import (
    check_cb_statement,
    check_release_page,
    close_enough,
    parse_bp,
    parse_level_pct,
    parse_money,
    parse_signed_pct,
)
from ah.core.engine import EnginePaths


def _paths(months: int = 12) -> EnginePaths:
    return EnginePaths(
        months=months,
        seed=1,
        rate=np.linspace(2.0, 5.0, months),
        spread=np.linspace(400.0, 700.0, months),
        inflation=np.linspace(2.0, 9.0, months),
        crisis=np.zeros(months),
        returns={"equity": np.zeros(months)},
        reported={"equity": np.zeros(months)},
    )


def test_parsers_read_the_exact_forms_the_templates_emit():
    assert parse_level_pct("The policy rate stands at 5.74%, little changed.") == pytest.approx(5.74)
    assert parse_signed_pct("Return for the quarter: +2.3% (x).") == pytest.approx(2.3)
    assert parse_signed_pct("Return for the quarter: -1.8% (x).") == pytest.approx(-1.8)
    assert parse_bp("626bp") == pytest.approx(626.0)
    assert parse_money("Total value: 1,234.5.") == pytest.approx(1234.5)


def test_an_unparseable_string_returns_none_rather_than_guessing():
    assert parse_level_pct("no number here") is None
    assert parse_bp("no number here") is None


def test_close_enough_derives_its_tolerance_from_the_printed_precision():
    assert close_enough(5.74, 5.7449, decimals=2)
    assert not close_enough(5.74, 5.75, decimals=2)
    assert close_enough(626.0, 626.4, decimals=0)


def test_a_correct_release_page_passes():
    paths = _paths()
    m = 5
    item = {
        "month": m,
        "type": "release_page",
        "payload": release_page(
            world_id="w",
            dateline="Y1M6",
            release_name="Monthly economic release",
            rows=[
                {"series": "CPI inflation", "value": f"{paths.inflation[m]:.1f}%", "prior": f"{paths.inflation[m-1]:.1f}%"},
                {"series": "High yield spread", "value": f"{paths.spread[m]:.0f}bp", "prior": f"{paths.spread[m-1]:.0f}bp"},
            ],
        ),
    }
    assert all(f.ok for f in check_release_page(item, paths))


def test_a_release_page_carrying_last_months_value_as_this_month_FAILS():
    paths = _paths()
    m = 5
    item = {
        "month": m,
        "type": "release_page",
        "payload": release_page(
            world_id="w",
            dateline="Y1M6",
            release_name="Monthly economic release",
            rows=[
                {"series": "CPI inflation", "value": f"{paths.inflation[m-1]:.1f}%", "prior": f"{paths.inflation[m-1]:.1f}%"},
                {"series": "High yield spread", "value": f"{paths.spread[m]:.0f}bp", "prior": f"{paths.spread[m-1]:.0f}bp"},
            ],
        ),
    }
    findings = check_release_page(item, paths)
    assert any(not f.ok and f.check == "cpi_value" for f in findings)


def test_a_correct_cb_statement_passes():
    paths = _paths()
    m = 5
    item = {
        "month": m,
        "type": "cb_statement",
        "payload": central_bank_statement(
            world_id="w",
            dateline="Y1M6",
            policy_rate=float(paths.rate[m]) / 100.0,
            previous_rate=float(paths.rate[m - 3]) / 100.0,
        ),
    }
    assert all(f.ok for f in check_cb_statement(item, paths))


def test_a_cb_statement_quoting_the_rate_in_the_wrong_UNIT_FAILS():
    """The historical bug: percent where the template expects a decimal."""
    paths = _paths()
    m = 5
    item = {
        "month": m,
        "type": "cb_statement",
        "payload": central_bank_statement(
            world_id="w",
            dateline="Y1M6",
            policy_rate=float(paths.rate[m]),          # NOT divided by 100
            previous_rate=float(paths.rate[m - 3]),
        ),
    }
    findings = check_cb_statement(item, paths)
    assert any(not f.ok and f.check == "policy_rate" for f in findings)


def test_a_cb_statement_saying_little_changed_across_a_big_move_FAILS():
    paths = _paths(24)
    m = 12
    good = central_bank_statement(
        world_id="w",
        dateline="Y2M1",
        policy_rate=float(paths.rate[m]) / 100.0,
        previous_rate=float(paths.rate[m - 3]) / 100.0,
    )
    tampered = dict(good)
    tampered["lines"] = [
        f"The policy rate stands at {paths.rate[m]:.2f}%, little changed over the quarter.",
        good["lines"][1],
    ]
    findings = check_cb_statement({"month": m, "type": "cb_statement", "payload": tampered}, paths)
    assert any(not f.ok and f.check == "move_wording" for f in findings)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_audit_wire_parsing.py -v`
Expected: FAIL — `No module named 'ah.audit.wire'`.

- [ ] **Step 3: Implement the parsers and `Finding`**

Create `src/ah/audit/wire.py`:

```python
"""Reconciling generated wire artifacts against the tape they describe.

Every artifact template renders its numbers into prose, so there is no
numeric field to check: ``central_bank_statement`` returns sentences,
``release_page`` rows carry pre-formatted strings like "626bp". The audit
therefore re-parses the rendered text. That is forced by the data, and it is
the check worth having — the templates' inputs are read straight off
``EnginePaths`` and are trivially correct, while the defects actually found
in this surface (ER-2's phantom rate decisions, the percent/decimal unit
bug) were both failures of formatting.

Nothing here fixes a template. A failure is recorded as a finding; changing
the artifact is a separate, owner-decided change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.core.engine import EnginePaths

__all__ = [
    "Finding",
    "check_cb_statement",
    "check_release_page",
    "close_enough",
    "parse_bp",
    "parse_level_pct",
    "parse_money",
    "parse_signed_pct",
]

_LEVEL_PCT = re.compile(r"(?<![+\-\d])(\d+(?:\.\d+)?)%")
_SIGNED_PCT = re.compile(r"([+-]\d+(?:\.\d+)?)%")
_BP = re.compile(r"(\d+(?:\.\d+)?)bp")
_MONEY = re.compile(r"(\d[\d,]*\.\d)")


@dataclass(frozen=True)
class Finding:
    """One reconciliation, and what it saw.

    ``expected`` and ``actual`` are recorded even on a pass, so a reader can
    audit the auditor without rerunning it.
    """

    month: int
    item_type: str
    check: str
    ok: bool
    expected: str
    actual: str
    detail: str = ""


def _first(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if match is None:
        return None
    return float(match.group(1).replace(",", ""))


def parse_level_pct(text: str) -> float | None:
    """An unsigned percentage as printed by ``fmt_level_pct`` (e.g. 5.74%)."""
    return _first(_LEVEL_PCT, text)


def parse_signed_pct(text: str) -> float | None:
    """A signed percentage as printed by ``fmt_pct`` (e.g. +2.3%)."""
    return _first(_SIGNED_PCT, text)


def parse_bp(text: str) -> float | None:
    """A basis-point figure (e.g. 626bp)."""
    return _first(_BP, text)


def parse_money(text: str) -> float | None:
    """A ``fmt_money`` figure with thousands separators (e.g. 1,234.5)."""
    return _first(_MONEY, text)


def close_enough(parsed: float | None, expected: float, *, decimals: int) -> bool:
    """Compare at the precision the value was PRINTED at, not at float equality.

    The tolerance is derived from the formatter's own decimal count, so a
    change to a format string cannot silently loosen a check.
    """
    if parsed is None:
        return False
    return abs(parsed - expected) <= 0.5 * (10.0**-decimals) + 1e-9
```

- [ ] **Step 4: Implement the release-page check**

Append to `src/ah/audit/wire.py`:

```python
def check_release_page(item: dict[str, Any], paths: EnginePaths) -> list[Finding]:
    """CPI and spread rows, each with its prior, against the tape."""
    m = int(item["month"])
    prev = max(m - 1, 0)
    rows = {r["series"]: r for r in item["payload"]["rows"]}
    out: list[Finding] = []

    spec = (
        ("CPI inflation", "cpi", parse_level_pct, paths.inflation, 1),
        ("High yield spread", "spread", parse_bp, paths.spread, 0),
    )
    for series, tag, parser, tape, decimals in spec:
        row = rows.get(series)
        if row is None:
            out.append(
                Finding(m, "release_page", f"{tag}_present", False, series, "missing")
            )
            continue
        for field, index in (("value", m), ("prior", prev)):
            parsed = parser(str(row[field]))
            expected = float(tape[index])
            out.append(
                Finding(
                    month=m,
                    item_type="release_page",
                    check=f"{tag}_{field}",
                    ok=close_enough(parsed, expected, decimals=decimals),
                    expected=f"{expected:.{decimals}f}",
                    actual=str(row[field]),
                )
            )
    return out
```

- [ ] **Step 5: Implement the CB-statement check**

Append to `src/ah/audit/wire.py`:

```python
def check_cb_statement(item: dict[str, Any], paths: EnginePaths) -> list[Finding]:
    """The rate, its unit convention, the stated move, and the wording.

    The template takes a DECIMAL rate and prints ``rate * 100``; the tape
    carries percent. So the printed figure must equal ``paths.rate[m]``
    directly. A statement built from the undivided tape value reads 100x
    high, which is exactly the unit bug this check exists to catch.
    """
    m = int(item["month"])
    prev = m - 3 if m - 3 >= 0 else m
    line = str(item["payload"]["lines"][0])
    expected_rate = float(paths.rate[m])
    parsed = parse_level_pct(line)
    out = [
        Finding(
            month=m,
            item_type="cb_statement",
            check="policy_rate",
            ok=close_enough(parsed, expected_rate, decimals=2),
            expected=f"{expected_rate:.2f}",
            actual=line,
        )
    ]

    move_bp = round(abs(float(paths.rate[m]) - float(paths.rate[prev])) * 100.0)
    quiet = "little changed" in line
    out.append(
        Finding(
            month=m,
            item_type="cb_statement",
            check="move_wording",
            ok=(quiet == (move_bp < 5)),
            expected=f"{'little changed' if move_bp < 5 else 'a stated move'} ({move_bp}bp)",
            actual=line,
            detail="the template says 'little changed' if and only if the move is under 5bp",
        )
    )

    if not quiet:
        stated = _first(re.compile(r"\((?:up|down) (\d+)bp\)"), line)
        out.append(
            Finding(
                month=m,
                item_type="cb_statement",
                check="move_magnitude",
                ok=stated is not None and abs(stated - move_bp) <= 1.0,
                expected=f"{move_bp}bp",
                actual=line,
            )
        )
    return out
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_wire_parsing.py -v`
Expected: PASS, 9 tests.

The `_LEVEL_PCT` negative lookbehind exists so a signed figure (`+2.3%`) is not read as an unsigned level. If `test_parsers_read_the_exact_forms_the_templates_emit` fails on that case, fix the pattern rather than the assertion.

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/audit/wire.py tests/test_audit_wire_parsing.py
git commit -m "feat: wire parsers and the release/CB reconciliations

Every template renders numbers into prose, so the audit re-parses the
rendered text. Each check is proved to fail against a corrupted item -
including a statement quoting the rate in the wrong unit, which is the
bug this surface actually shipped once."
```

---

### Task 5: The remaining wire checks, and the feed-level audit

**Files:**
- Modify: `src/ah/audit/wire.py` (append)
- Test: `tests/test_audit_wire_feed.py` (create)

**Interfaces:**
- Consumes: `Finding`, parsers, `close_enough`, `check_release_page`, `check_cb_statement` from Task 4.
- Produces:
  - `check_quarterly_statement(item, paths, twin, peer_bands) -> list[Finding]`
  - `check_crisis_digests(items, paths) -> list[Finding]`
  - `check_newspapers(items, paths) -> list[Finding]`
  - `check_feed_shape(items, months) -> list[Finding]`
  - `audit_wire(world, *, base_seed, n_peer_paths) -> list[Finding]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_wire_feed.py`:

```python
"""Feed-level reconciliation: shape, crisis onsets, headlines, determinism."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.audit.wire import audit_wire, check_crisis_digests, check_feed_shape
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 771204


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


@pytest.fixture(scope="module")
def findings():
    return audit_wire(_world(), base_seed=SEED, n_peer_paths=4)


def test_a_real_world_reconciles_completely(findings):
    failures = [f for f in findings if not f.ok]
    assert not failures, f"{len(failures)} wire items disagree with the tape: {failures[:5]}"


def test_the_audit_actually_checked_something(findings):
    """A vacuous pass is the failure mode here - assert coverage explicitly."""
    kinds = {f.check for f in findings}
    assert {"cpi_value", "spread_value", "policy_rate", "move_wording"} <= kinds
    assert len(findings) > 100


def test_a_crisis_digest_on_a_calm_month_FAILS():
    import numpy as np

    from ah.core.engine import run_path

    paths = run_path(_world("goldilocks"), SEED)
    fake = [{"month": 7, "type": "wire_digest", "payload": {"lines": ["- x"]}}]
    findings = check_crisis_digests(fake, paths)
    assert any(not f.ok for f in findings)
    assert float(np.sum(paths.crisis[:8])) == 0.0  # the month really is calm


def test_a_missing_crisis_digest_at_an_onset_FAILS():
    from ah.core.engine import run_path

    paths = run_path(_world("deflation_bust"), SEED)
    findings = check_crisis_digests([], paths)
    if float(paths.crisis.sum()) > 0:
        assert any(not f.ok for f in findings)


def test_an_item_outside_the_horizon_FAILS():
    items = [{"month": 999, "type": "release_page", "payload": {}}]
    findings = check_feed_shape(items, months=120)
    assert any(not f.ok and f.check == "month_in_horizon" for f in findings)


def test_a_quarterly_item_on_a_non_quarter_month_FAILS():
    items = [{"month": 4, "type": "cb_statement", "payload": {}}]
    findings = check_feed_shape(items, months=120)
    assert any(not f.ok and f.check == "quarter_cadence" for f in findings)


def test_the_audit_is_deterministic():
    a = audit_wire(_world("goldilocks"), base_seed=SEED, n_peer_paths=4)
    b = audit_wire(_world("goldilocks"), base_seed=SEED, n_peer_paths=4)
    assert [(f.check, f.month, f.ok, f.expected, f.actual) for f in a] == [
        (f.check, f.month, f.ok, f.expected, f.actual) for f in b
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_audit_wire_feed.py -v`
Expected: FAIL — `cannot import name 'audit_wire'`.

- [ ] **Step 3: Implement the quarterly-statement check**

Append to `src/ah/audit/wire.py` (add `from ah.artifacts.templates import _percentile_from_bands` — it is private but is the only definition of the six phrases, and duplicating them here would let the audit and the template drift apart, which is exactly the failure this module exists to prevent; state that in a comment):

```python
def check_quarterly_statement(
    item: dict[str, Any],
    paths: EnginePaths,
    twin_total: np.ndarray,
    peer_bands: dict[str, float],
) -> list[Finding]:
    """The institution's own statement, against the hold-course twin.

    ``twin_total`` is ``simulate_institution(paths, None).total`` — the same
    object ``ah.feed`` builds the statement from, re-derived. The audit
    checks the RENDERING, so it must not re-derive a different institution
    and compare apples to oranges.
    """
    m = int(item["month"])
    prev = m - 3
    lines = [str(x) for x in item["payload"]["lines"]]
    base_q = float(twin_total[prev]) if prev >= 0 else 100.0
    year_start = (m // 12) * 12 - 1
    base_y = float(twin_total[year_start]) if year_start >= 0 else 100.0
    expected_q = float(twin_total[m]) / base_q - 1.0
    expected_ytd = float(twin_total[m]) / base_y - 1.0
    expected_value = float(twin_total[m])

    out = [
        Finding(
            month=m,
            item_type="quarterly_statement",
            check="return_q",
            ok=close_enough(parse_signed_pct(lines[0]), expected_q * 100.0, decimals=1),
            expected=f"{expected_q * 100.0:+.1f}",
            actual=lines[0],
        ),
        Finding(
            month=m,
            item_type="quarterly_statement",
            check="return_ytd",
            ok=close_enough(parse_signed_pct(lines[1]), expected_ytd * 100.0, decimals=1),
            expected=f"{expected_ytd * 100.0:+.1f}",
            actual=lines[1],
        ),
        Finding(
            month=m,
            item_type="quarterly_statement",
            check="total_value",
            ok=close_enough(parse_money(lines[2]), expected_value, decimals=1),
            expected=f"{expected_value:,.1f}",
            actual=lines[2],
        ),
    ]

    ordered = [peer_bands[k] for k in ("p5", "p25", "p50", "p75", "p95")]
    out.append(
        Finding(
            month=m,
            item_type="quarterly_statement",
            check="peer_bands_monotone",
            ok=ordered == sorted(ordered),
            expected="p5 <= p25 <= p50 <= p75 <= p95",
            actual=", ".join(f"{v:.4f}" for v in ordered),
        )
    )
    phrase = _percentile_from_bands(expected_q, peer_bands)
    out.append(
        Finding(
            month=m,
            item_type="quarterly_statement",
            check="peer_phrase",
            ok=phrase in lines[0],
            expected=phrase,
            actual=lines[0],
        )
    )
    return out
```

- [ ] **Step 4: Implement the crisis, newspaper and shape checks**

Append to `src/ah/audit/wire.py` (add `from ah.feed import headline_events`):

```python
_MAX_SECONDARY_STORIES = 3


def _crisis_onsets(paths: EnginePaths) -> list[int]:
    return [
        m
        for m in range(paths.months)
        if paths.crisis[m] == 1.0 and (m == 0 or paths.crisis[m - 1] == 0.0)
    ]


def check_crisis_digests(items: list[dict[str, Any]], paths: EnginePaths) -> list[Finding]:
    """A digest exists at month m if and only if the crisis flag turns on there."""
    got = sorted(int(i["month"]) for i in items if i["type"] == "wire_digest")
    want = _crisis_onsets(paths)
    out = [
        Finding(
            month=m,
            item_type="wire_digest",
            check="digest_without_onset",
            ok=False,
            expected="no digest (crisis flag does not turn on this month)",
            actual="digest present",
        )
        for m in got
        if m not in want
    ]
    out.extend(
        Finding(
            month=m,
            item_type="wire_digest",
            check="onset_without_digest",
            ok=False,
            expected="a digest (crisis flag turns on this month)",
            actual="no digest",
        )
        for m in want
        if m not in got
    )
    if not out:
        out.append(
            Finding(
                month=-1,
                item_type="wire_digest",
                check="crisis_onsets",
                ok=True,
                expected=str(want),
                actual=str(got),
            )
        )
    return out


def check_newspapers(items: list[dict[str, Any]], paths: EnginePaths) -> list[Finding]:
    """Every front page traces to an earned trigger, and every trigger to a page."""
    earned = headline_events(paths)
    got = {int(i["month"]): i for i in items if i["type"] == "newspaper"}
    out: list[Finding] = []
    for m in sorted(set(earned) | set(got)):
        stories = earned.get(m)
        item = got.get(m)
        if stories and item is None:
            out.append(
                Finding(m, "newspaper", "story_without_page", False, stories[0], "no page")
            )
            continue
        if item is not None and not stories:
            out.append(
                Finding(m, "newspaper", "page_without_story", False, "no trigger", "page present")
            )
            continue
        assert stories is not None and item is not None
        payload = item["payload"]
        out.append(
            Finding(
                month=m,
                item_type="newspaper",
                check="lead_matches_trigger",
                ok=str(payload.get("lead")) == stories[0],
                expected=stories[0],
                actual=str(payload.get("lead")),
            )
        )
        expected_secondary = stories[1 : 1 + _MAX_SECONDARY_STORIES]
        out.append(
            Finding(
                month=m,
                item_type="newspaper",
                check="secondary_matches_triggers",
                ok=list(payload.get("stories") or []) == expected_secondary,
                expected=str(expected_secondary),
                actual=str(payload.get("stories")),
            )
        )
    return out


def check_feed_shape(items: list[dict[str, Any]], *, months: int) -> list[Finding]:
    """Horizon, cadence and ordering — properties of the feed as a whole."""
    quarter_ends = {m for m in range(months) if (m + 1) % 3 == 0}
    out: list[Finding] = []
    for item in items:
        m = int(item["month"])
        if not 0 <= m < months:
            out.append(
                Finding(m, str(item["type"]), "month_in_horizon", False, f"0..{months - 1}", str(m))
            )
        if item["type"] in {"cb_statement", "quarterly_statement"} and m not in quarter_ends:
            out.append(
                Finding(
                    m,
                    str(item["type"]),
                    "quarter_cadence",
                    False,
                    "a quarter-closing month",
                    str(m),
                )
            )
    keys = [(int(i["month"]), str(i["type"])) for i in items]
    out.append(
        Finding(
            month=-1,
            item_type="feed",
            check="sorted",
            ok=keys == sorted(keys),
            expected="sorted by (month, type)",
            actual="sorted" if keys == sorted(keys) else "out of order",
        )
    )
    monthly = {int(i["month"]) for i in items if i["type"] == "release_page"}
    missing = sorted(set(range(months)) - monthly)
    out.append(
        Finding(
            month=-1,
            item_type="release_page",
            check="monthly_coverage",
            ok=not missing,
            expected=f"a release for all {months} months",
            actual=f"missing {missing[:5]}" if missing else "complete",
        )
    )
    return out
```

- [ ] **Step 5: Implement `audit_wire`**

Append to `src/ah/audit/wire.py` (add `from ah.core.engine import run_path`, `from ah.core.institution import simulate_institution`, `from ah.core.numericworld import NumericWorld`, `from ah.feed import build_tier1_feed`):

```python
def audit_wire(
    world: NumericWorld, *, base_seed: int, n_peer_paths: int
) -> list[Finding]:
    """Build one world's wire and reconcile every item against its tape."""
    paths = run_path(world, base_seed)
    items = build_tier1_feed(world, paths, base_seed=base_seed, n_peer_paths=n_peer_paths)
    twin = simulate_institution(paths, None)

    peer_totals = np.empty((n_peer_paths, paths.months))
    for k in range(n_peer_paths):
        peer_totals[k] = simulate_institution(run_path(world, base_seed + 7919 * k), None).total

    out: list[Finding] = []
    out.extend(check_feed_shape(items, months=paths.months))
    out.extend(check_crisis_digests(items, paths))
    out.extend(check_newspapers(items, paths))
    for item in items:
        kind = item["type"]
        if kind == "release_page":
            out.extend(check_release_page(item, paths))
        elif kind == "cb_statement":
            out.extend(check_cb_statement(item, paths))
        elif kind == "quarterly_statement":
            m = int(item["month"])
            prev = m - 3
            base = peer_totals[:, prev] if prev >= 0 else 100.0
            peer_q = peer_totals[:, m] / base - 1.0
            bands = {
                f"p{q}": float(v)
                for q, v in zip((5, 25, 50, 75, 95), np.percentile(peer_q, (5, 25, 50, 75, 95)), strict=True)
            }
            out.extend(check_quarterly_statement(item, paths, twin.total, bands))
    return out
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_wire_feed.py -v`
Expected: PASS, 7 tests.

**If `test_a_real_world_reconciles_completely` fails, do not adjust the check to accommodate it.** A genuine mismatch between the wire and the tape is the finding this whole plan exists to surface. Record the failing check, month, expected and actual in your report and stop for the coordinator's decision.

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/audit/wire.py tests/test_audit_wire_feed.py
git commit -m "feat: quarterly, crisis, newspaper and feed-shape reconciliation

audit_wire rebuilds a world's wire and checks every item against the tape,
including the peer bands recomputed from the same seed lineage."
```

---

### Task 6: The page

**Files:**
- Create: `src/ah/audit/page.py`
- Modify: `src/ah/audit/__init__.py`
- Test: `tests/test_audit_page.py` (create)

**Interfaces:**
- Consumes: everything from Tasks 2-5.
- Produces: `AuditReport` frozen dataclass (`rows`, `segments`, `pairs`, `wire`), `build_audit(conn, *, presets_dir, default_seed, n_peer_paths, include_wire) -> AuditReport`, `render_audit_page(report) -> str`, both re-exported from `ah.audit`.

- [ ] **Step 1: Load the dataviz skill**

Before writing any markup, invoke the `dataviz` skill and follow its guidance. Reuse the console's existing palette variables rather than new hex values — they are defined in `src/ah/credibility.py`'s `_CSS` block: `--ink #0d2226`, `--pane #0f282b`, `--line #20464b`, `--ice #d7e6e3`, `--dim #7c9b99`, `--jade #4fc3a1`, `--clay #d2624f`, `--brass #d6a24a`. Read that block first so the three admin surfaces look like one system.

- [ ] **Step 2: Write the failing test**

Create `tests/test_audit_page.py`:

```python
"""The audit page: self-contained, deterministic, and honest about counts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ah.audit import build_audit, render_audit_page
from ah.store.db import connect, init_db

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 771204


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    init_db(c)
    return c


@pytest.fixture()
def report(conn):
    return build_audit(
        conn, presets_dir=PRESETS, default_seed=SEED, n_peer_paths=2, include_wire=True
    )


def test_the_page_is_self_contained(report):
    html = render_audit_page(report)
    for forbidden in ("http://", "https://", "<script", "src=", "@import"):
        assert forbidden not in html, f"page must not reference {forbidden}"


def test_the_page_is_deterministic(conn, report):
    again = build_audit(
        conn, presets_dir=PRESETS, default_seed=SEED, n_peer_paths=2, include_wire=True
    )
    assert render_audit_page(report) == render_audit_page(again)


def test_the_summary_states_the_counts_a_reader_needs(report):
    html = render_audit_page(report)
    assert str(len(report.rows)) in html
    assert "wire" in html.lower()


def test_every_registered_world_appears_by_title_or_id(report):
    html = render_audit_page(report)
    for row in report.rows:
        assert (row.title and row.title in html) or row.world_id in html


def test_skipping_the_wire_produces_a_page_with_no_wire_findings(conn):
    report = build_audit(
        conn, presets_dir=PRESETS, default_seed=SEED, n_peer_paths=2, include_wire=False
    )
    assert report.wire == {}
    assert render_audit_page(report)


def test_a_transition_matrix_world_states_why_it_has_no_segments(report):
    """A blank cell would read as 'checked and fine'. It must read as 'not
    applicable, and here is why'."""
    html = render_audit_page(report)
    for row in report.rows:
        if row.error is None and row.regime_mode != "sequence":
            assert "per path" in html or "no declared sequence" in html
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_audit_page.py -v`
Expected: FAIL — `cannot import name 'build_audit' from 'ah.audit'`.

- [ ] **Step 4: Implement `page.py`**

Create `src/ah/audit/page.py` with:

- `AuditReport` frozen dataclass carrying `rows: list[WorldRow]`, `segments: dict[str, list[SegmentCheck]]`, `pairs: list[PairDistance]`, `wire: dict[str, list[Finding]]` (keyed by `world_id`).
- `build_audit(conn, *, presets_dir, default_seed, n_peer_paths, include_wire)` which calls `discover_worlds`, then for each row with `error is None`: `run_path(row.world, row.seed)`, `declared_vs_realized`, `world_vector`, and (when `include_wire`) `audit_wire`. It then calls `distinguishability` over the successfully-loaded rows and their vectors.
- `_e(s)` escaping via `html.escape`, and `_f(v, places=2)`.
- `AUDIT_CSS` reusing the palette variables named in Step 1.
- `render_audit_page(report)` emitting, in order: a summary band (worlds registered, worlds in error, wire items checked, wire failures, pairs flagged); the register table (id, title, source, status, generator, horizon, regime mode, seed, error); the declared-vs-realized table per sequence-mode world, and for other modes a stated row reading `regimes are drawn per path — no declared sequence to check against`; the distinguishability table with lineage pairs labelled; and the wire findings, **failures first**, with expected and actual side by side.

Every value reaching markup goes through `_e`. Iterate `report.wire` in `report.rows` order, never in dict-insertion-by-accident order, so the page is byte-stable.

- [ ] **Step 5: Re-export from the package**

Replace the `__all__` line in `src/ah/audit/__init__.py`:

```python
from ah.audit.page import AuditReport, build_audit, render_audit_page

__all__ = ["AuditReport", "build_audit", "render_audit_page"]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_page.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/audit/ tests/test_audit_page.py
git commit -m "feat: the audit page - register, segments, distances, wire findings

Self-contained and byte-stable, with failures first and a summary band so
'is anything wrong' does not require scrolling."
```

---

### Task 7: CLI wiring, the read-only guard, timing, changelog

**Files:**
- Modify: `src/ah/cli.py`, `CHANGELOG.md`
- Test: `tests/test_audit_guard.py` (create), `tests/test_cli.py` (extend)

**Interfaces:**
- Consumes: `build_audit`, `render_audit_page` from Task 6.
- Produces: the `ah audit` command. No new public API.

- [ ] **Step 1: Measure before choosing a default**

```bash
uv run python -c "
import time, json
from pathlib import Path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.audit.wire import audit_wire
doc = json.loads(Path('src/ah/presets/stagflation.json').read_text(encoding='utf-8'))
w = project_numeric(WorldSpec.model_validate(doc))
for n in (2, 4, 8, 16):
    t0 = time.perf_counter()
    audit_wire(w, base_seed=771204, n_peer_paths=n)
    print(n, 'peer paths:', round(time.perf_counter() - t0, 2), 's')
"
```

Record the numbers in your report. Choose `--peer-paths`'s default so a full run over the whole register (store worlds plus four presets) stays under about 60 seconds, and state the arithmetic behind the choice. Do not exceed that without saying so.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_audit_guard.py`:

```python
"""ah.audit is read-only BY CONSTRUCTION, not by promise.

Same pattern as tests/test_programme_guard.py: an admin surface that claims
to write nothing should not be able to, and the cheapest enforcement is that
it cannot import anything that writes.
"""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "ah" / "audit"
FORBIDDEN = ("ah.serve", "ah.store.sessions", "ah.store.leaderboard")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_audit_never_imports_a_writer():
    files = sorted(PKG.glob("*.py"))
    assert files, "audit package missing?"
    offenders = [
        f"{path.name}: {module}"
        for path in files
        for module in _imported_modules(path)
        for bad in FORBIDDEN
        if module == bad or module.startswith(bad + ".")
    ]
    assert not offenders, f"ah.audit must not import a writer: {offenders}"


def test_audit_calls_no_write_helper():
    """It may read from ah.store.worlds, but must never call its writer."""
    for path in sorted(PKG.glob("*.py")):
        text = path.read_text("utf-8")
        assert "save_world" not in text, path.name
        assert "save_run_record" not in text, path.name
```

Append to `tests/test_cli.py` a test that invokes the command through Typer's `CliRunner` in a temp directory and asserts the output file exists, is non-empty, and contains no `<script`. Follow the file's existing runner idiom rather than inventing one — read it first.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_audit_guard.py tests/test_cli.py -v`
Expected: the guard tests PASS already; the CLI test FAILS with no such command `audit`.

- [ ] **Step 4: Add the command**

In `src/ah/cli.py`, add after `credibility_cmd`. Read the neighbouring commands first and match their `ctx`/`_db` idiom exactly:

```python
@app.command("audit")
def audit_cmd(
    ctx: typer.Context,
    seed: int = typer.Option(771204, "--seed", help="Tape seed for worlds with no run record"),
    peer_paths: int = typer.Option(4, "--peer-paths", help="Peer paths for wire peer bands"),
    no_wire: bool = typer.Option(False, "--no-wire", help="Register only; skip the wire audit"),
    out: Path | None = typer.Option(None, "--out", help="Output HTML path (default audit.html)"),
) -> None:
    """Review every world that exists, and reconcile the wire against its tape.

    Admin surface. Reads worlds and the artifacts they generate, writes only
    the page. Nothing here is sealed, scored, or shown to a player.
    """
    from ah.audit import build_audit, render_audit_page

    conn = _db(ctx)
    report = build_audit(
        conn,
        presets_dir=PRESETS_DIR,
        default_seed=seed,
        n_peer_paths=peer_paths,
        include_wire=not no_wire,
    )
    target = out if out is not None else Path("audit.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_audit_page(report), encoding="utf-8", newline="\n")
    failures = sum(1 for fs in report.wire.values() for f in fs if not f.ok)
    errors = sum(1 for r in report.rows if r.error is not None)
    typer.echo(
        f"{target} ({len(report.rows)} worlds, {errors} unreadable, {failures} wire failures)"
    )
```

Set `peer_paths`'s default to the number Step 1's measurement justified. Keep the echoed string ASCII.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_guard.py tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Generate the page and read it**

```bash
uv run ah audit --out audit-check.html
```

Open it and read it. This is the deliverable — every prior check was on strings and arrays. Confirm the register lists both populations, that the declared-vs-realized verdicts are legible, and that any wire failure states expected and actual clearly enough to act on. **If a wire item genuinely disagrees with its tape, that is a finding about the wire, not a bug in the audit** — record it for the owner rather than adjusting the check. Delete the file afterwards.

- [ ] **Step 7: Update the CHANGELOG**

Add an entry under `### Added` in the top `[Unreleased]` section covering: the two read-only store helpers and why they did not exist; the register's two references (a world against its own declarations, a wire item against its own tape) and how those differ from `credibility`/`inspect`/`battery`; the fact that reconciliation re-parses rendered prose because no template payload carries a raw float; the declared regime expectations and which regimes are deliberately not asserted; the distinguishability scales and the lineage-pair rule; the measured `--peer-paths` default; and the import-graph guard. State that no template changed and no scored path moved.

- [ ] **Step 8: Run the full gate**

```bash
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90 > gate-audit.log 2>&1; echo "EXIT: $?" >> gate-audit.log
```

Read `gate-audit.log` — the `EXIT:` line and the pass count, **from the file**. Never pipe it through `tail`, and never chain a merge onto one.

- [ ] **Step 9: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add -A
git commit -m "feat: ah audit - the world register and wire audit

Lists every world that exists across both populations, checks each
against its own declared regime segments, reports pairwise
distinguishability with lineage pairs labelled, and reconciles every
generated wire item against the tape it describes."
```

**Do not merge or push.** A whole-branch review runs first.

---

## Self-Review

**Spec coverage.** Store helpers → Task 1. Discovery across both populations, malformed presets listed → Task 2. Declared-vs-realized with the sequence-mode restriction, distinguishability with declared scales and the lineage rule → Task 3. Parsers and the release/CB checks including the unit convention → Task 4. Quarterly/crisis/newspaper/feed-shape and `audit_wire` → Task 5. Page assembly, self-containment, determinism, summary band → Task 6. CLI with all four flags, ASCII echo, `newline="\n"`, import guard, measured default, changelog, gate → Task 7. Error handling: malformed preset (Task 2), unparseable string as FAIL not skip (`close_enough` returns False on `None`, Task 4), short horizon (`check_feed_shape` bounds, Task 5).

**Known gap carried deliberately.** The spec's "a world whose horizon is too short to build a feed renders a stated 'no wire' note" is handled only implicitly — `audit_wire` on a very short world will produce shape findings rather than a clean note. If Task 6's `build_audit` hits a world with `horizon_months < 3`, it should skip the wire for that world and record the reason; that instruction is in Task 6 Step 4's description of `build_audit` but has no dedicated test. Add one if a short-horizon world ever enters the store.

**Type consistency.** `WorldRow`, `SegmentCheck`, `PairDistance`, `Finding`, `AuditReport` are each defined once and used with those exact field names throughout. `close_enough` takes `decimals` keyword-only in its definition and every call site passes it that way. `audit_wire(world, *, base_seed, n_peer_paths)` matches its three call sites (Tasks 5, 6, 7 Step 1).

**Names verified against the codebase while writing this plan**, not assumed: there is no `ah.presets` module; the four preset stems are `stagflation`, `goldilocks`, `deflation_bust`, `reflation_boom`; `_quarter_ends` is `(m+1) % 3 == 0`; `headline_events` is public in `ah.feed`; `_percentile_from_bands` is private in `ah.artifacts.templates` and returns one of six exact phrases; the eight regime names come from `schemas/worldspec-v1.0.schema.json`; `run_records` carries `seed` and `created_at`; the store's `worlds` table has exactly `world_id, spec_version, status, json, created_at`.

---

*Not investment advice.*
