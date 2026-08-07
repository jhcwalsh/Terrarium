# Generator-Input Data Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only HTML dashboard (port 8796) over the vintage store: raw series (coverage, gaps, freshness, proxy provenance, QC) and the derived factor panel the generator trains on, including reported-vs-de-smoothed privates.

**Architecture:** One new FastAPI module `src/ah/dataconsole.py` in the established console idiom (server-rendered HTML, inline SVG, no JS). All reads go through `ah.data.catalog.Catalog`, `ah.data.manifest.load_requirements()`, and mechanical recomputation via the sealed `ah.data.derive` / `ah.data.desmooth` / `ah.factors` surfaces. Zero write call sites — enforced by a guard test.

**Tech Stack:** FastAPI + uvicorn, duckdb, pandas, numpy (all existing). **No new dependencies.**

## Global Constraints

- Branch `data-console-01` (already created; spec committed `004f95f`).
- **Edit nothing sealed.** `derive.py`, `splice.py`, `factors.py`, `splits.py`, `eval/*` are in `pre-registration.lock` `hashed_files` — import-only. `schemas/` untouched.
- No network in tests; TestClient tests carry `pytestmark = pytest.mark.enable_socket` with the standard justification docstring (see `tests/test_serve.py`).
- CLI-echoed strings ASCII; HTML may use Unicode.
- Done = plan tests pass, full suite green, ruff/format/pyright clean, CHANGELOG updated, `--no-ff` merge + plain push.

**Interfaces consumed (verified 2026-08-07):**

```python
from ah.data.catalog import Catalog          # Catalog(root); .current_vintage() -> str|None;
#  .get_series(sid) -> dict|None (has is_proxy, freshness_sla, notes, first/last_date);
#  .read_observations(vintage_id, sid) -> DataFrame(date, value, series_id, vintage);
#  .con (duckdb) for read SQL over vintages/observations_index/qc_results/current_pointer
from ah.data.manifest import load_requirements   # -> Requirements (iterable of Requirement:
#  series_id, source, code, frequency, units, min_start, sla_days, license_tier,
#  priority, intake, enforce, notes)
from ah.data import derive                   # per-factor helpers named by FactorSource.expr
from ah.data.desmooth import glm_ma          # (obs: np.ndarray) -> DesmoothResult (.truth? read the
#  dataclass fields at line ~49 before use; label the method on the page)
from ah.factors import load_factor_manifest  # read factors.py for the exact loader name; the
#  manifest exposes blocks/active_blocks and factor_sources: dict[str, FactorSource]
#  FactorSource: kind in {series, derived, unavailable}; series_id | (expr, inputs) | reason;
#  proxy/proxy_for; numeraire
from ah.splits import HOLDOUT, TRAIN, VALIDATION   # Split(name, start, end):
#  train 1871-01-01..2011-01-01, validation ..2021-01-01, holdout ..2026-08-01 (SPENT)
```

Data root default: `_REPO_ROOT / "data"` (as `ah/data/cli.py` `DEFAULT_DATA_ROOT`). Spliced-series proxy runs: a stored frame MAY carry an `is_proxy` column (splice output `date,value,is_proxy,rule_id`); series-level `is_proxy` also lives on the catalog `series` row. Treat a missing `is_proxy` column as all-actual.

Two implementer notes where a name must be read before use (both bounded, neither a design decision): the exact `DesmoothResult` field for the recovered series (`desmooth.py:49`), and the exact factor-manifest loader name (`factors.py`, near `FactorManifest`). Use what the file says; do not guess.

---

### Task 1: Module skeleton, pure analytics, and the `/` inventory page

**Files:**
- Create: `src/ah/dataconsole.py`
- Test: `tests/test_dataconsole.py`

**Interfaces produced:** `create_app(data_root=DEFAULT_DATA_ROOT) -> FastAPI`; module `app`; pure functions `gap_ranges(dates: pd.Series) -> list[tuple[str, str]]` (missing calendar months between first and last obs, as YYYY-MM ranges), `coverage_pct(dates: pd.Series) -> float`, `staleness_days(last_date: str, as_of: str) -> int`, `proxy_pct(frame: pd.DataFrame) -> float`, `moments(values: np.ndarray) -> dict` (mean, vol, skew, excess_kurtosis; ddof=1; scipy-free — implement skew/kurtosis with numpy).

- [ ] **Step 1: Failing tests** — in `tests/test_dataconsole.py`:

```python
"""Tests for the generator-input data console. Read-only; no network.

``enable_socket`` is the sanctioned TestClient opt-in (see test_serve.py).
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ah.dataconsole import (
    coverage_pct,
    create_app,
    gap_ranges,
    moments,
    proxy_pct,
    staleness_days,
)

pytestmark = pytest.mark.enable_socket


def test_gap_ranges_finds_missing_months():
    dates = pd.Series(pd.to_datetime(["2020-01-01", "2020-02-01", "2020-05-01"]))
    assert gap_ranges(dates) == [("2020-03", "2020-04")]
    assert coverage_pct(dates) == pytest.approx(3 / 5)


def test_staleness_and_proxy_pct():
    assert staleness_days("2026-06-01", "2026-08-07") == 67
    f = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0], "is_proxy": [True, True, False, False]})
    assert proxy_pct(f) == pytest.approx(0.5)
    assert proxy_pct(pd.DataFrame({"value": [1.0]})) == 0.0  # no column -> all actual


def test_moments_shapes():
    m = moments(np.array([0.01, -0.02, 0.03, 0.005, -0.01]))
    assert set(m) == {"mean", "vol", "skew", "excess_kurtosis"}


def _tiny_store(tmp_path):
    """A real Catalog with two series across one vintage; built with the
    store's own API (writing happens in the TEST, never in the module)."""
    from ah.data.catalog import Catalog
    from ah.data.manifest import load_requirements

    cat = Catalog(tmp_path)
    reqs = load_requirements()
    cat.create_vintage("v1", created_at="2026-08-07T00:00:00Z", status="pending")
    for sid, vals in [("fred.CPI", [100.0, 101.0, 102.0]), ("french.mkt_rf", [0.01, -0.02, 0.03])]:
        cat.register_series(reqs[sid])
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
                "value": vals,
                "series_id": sid,
                "vintage": "v1",
            }
        )
        cat.write_observations("v1", sid, frame)
    cat.record_qc(vintage_id="v1", series_id="fred.CPI", rule="bounds", severity="enforce",
                  passed=True, detail="", created_at="2026-08-07")
    cat.advance_pointer("v1", when="2026-08-07T00:00:00Z")
    cat.close()
    return tmp_path


def test_inventory_page(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/")
    assert r.status_code == 200
    assert "DATA INSPECTION" in r.text          # watermark
    assert "v1" in r.text                        # current vintage
    assert "fred.CPI" in r.text and "french.mkt_rf" in r.text
    assert "registered, never fetched" in r.text  # the ~90 other manifest series


def test_empty_store_is_a_card_not_a_traceback(tmp_path):
    c = TestClient(create_app(data_root=tmp_path / "empty"))
    r = c.get("/")
    assert r.status_code == 200
    assert "Not available" in r.text
```

- [ ] **Step 2:** `uv run pytest tests/test_dataconsole.py -q` → ImportError. 
- [ ] **Step 3: Implement.** Copy the `_CSS`/`_e`/`_page` chrome technique from `console.py` (do not import). `WATERMARK = "DATA INSPECTION — read-only over the vintage store — simulated/licensed data"`. Nav: `data | QA shelf (8799) | build (8798)`. `create_app` stores `data_root`; every route opens `Catalog(data_root)` in a `try/finally: cat.close()` and renders the empty-state card if `current_vintage()` is None. Inventory row per manifest series: joined against `observations_index` for the current vintage (first/last/n_obs), `gap_ranges`/`staleness_days`/`proxy_pct` (read the current-vintage frame per series — ~100 series, DuckDB handles it; render is one request, not hot-path). QC summary: `SELECT severity, passed, COUNT(*) FROM qc_results WHERE vintage_id = ? GROUP BY 1, 2`. Warn-only registrations (`enforce: false`) render their staleness in the muted style with the manifest note, never red. Asset-class cards from the Task 3 `CLASSES` mapping (define it in this task):

```python
CLASSES: dict[str, dict[str, list[str]]] = {
    "equities": {
        "raw": ["french.mkt_rf", "french.smb", "french.hml", "french.mom", "french.rf",
                 "shiller.price", "shiller.dividend"],
        "factors": ["equity", "value", "momentum", "size"],
    },
    "rates-bonds": {
        "raw": ["fred.DGS10", "fred.DGS2", "fred.GS10", "fred.FEDFUNDS", "fred.TB3MS"],
        "factors": ["policy_rate", "term_10y2y", "bond_return"],
    },
    "credit": {
        "raw": ["fred.BAA", "fred.AAA", "fred.HY_OAS"],
        "factors": ["ig_spread", "hy_spread"],
    },
    "inflation-macro": {
        "raw": ["fred.CPI", "fred.CPI_CORE", "fred.UNRATE", "fred.INDPRO", "fred.USREC",
                 "fred.VIX", "fred.GDPC1"],
        "factors": ["inflation_yoy", "growth", "vol_regime"],
    },
    "fx": {"raw": ["fred.DTWEXBGS", "fred.DTWEXM"], "factors": ["fx_usd"]},
    "privates": {
        "raw": ["albourne.pm_buyout_ret_q", "albourne.pm_growth_ret_q", "albourne.pm_vc_ret_q",
                 "albourne.pm_dl_ret_q", "albourne.pm_mezz_ret_q", "albourne.pm_re_va_ret_q"],
        "factors": [],
    },
}
```

Then **reconcile this mapping against `factors.yaml`'s real factor names in the same step** (open it, correct the `factors` lists to the declared names — the lists above are the plan's best guess and the yaml is the truth; a factor named here that the manifest lacks must be dropped, and every `active_blocks` factor must appear in exactly one class or in `/factors` only). A raw series named here but absent from the manifest is a plan bug — fix the list, not the manifest.
- [ ] **Step 4:** Tests pass; `uv run ruff check` + `format` + targeted pyright clean.
- [ ] **Step 5:** `git add src/ah/dataconsole.py tests/test_dataconsole.py && git commit -m "feat(dataconsole): inventory page + pure analytics (task 1)"`

---

### Task 2: SVG helpers and `/series/{id}`

**Files:** Modify `src/ah/dataconsole.py`; test `tests/test_dataconsole.py`.

**Interfaces produced:** `line_svg(frame, *, title, proxy_col="is_proxy") -> str` (600×160, proxy stretches as a shaded band behind the line), `hist_svg(values, *, title, bins=30) -> str`, `bar_svg(pcts: dict[str, float]) -> str` (coverage bar); route `GET /series/{sid}`.

- [ ] **Step 1: Failing tests**

```python
def test_series_page_renders_chart_gaps_and_manifest(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/series/fred.CPI")
    assert r.status_code == 200
    assert "<svg" in r.text
    assert "CPIAUCNS" in r.text            # manifest entry verbatim (code)
    assert "bounds" in r.text              # its QC finding
    assert c.get("/series/no.such").status_code == 404


def test_proxy_shading_present_when_flagged(tmp_path):
    from ah.dataconsole import line_svg

    f = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
            "value": [1.0, 2.0, 3.0],
            "is_proxy": [True, False, False],
        }
    )
    out = line_svg(f, title="t")
    assert "proxy" in out                   # shaded region carries a class/label
    assert line_svg(f.drop(columns=["is_proxy"]), title="t").count("proxy") == 0
```

- [ ] **Step 2:** run → fail. 
- [ ] **Step 3: Implement.** SVG primitives in the `console.py`/`inspect.py` style (`_scale`, polyline points, no library). Proxy shading: contiguous `is_proxy` runs → `<rect class="proxy">` behind the polyline plus a small "proxy-spliced" legend chip; histogram = value counts over `bins` equal-width buckets as `<rect>`s. `/series/{sid}`: 404 unknown sid; sections = chart (full current-vintage history), vintage list (`observations_index` rows for sid + `current_pointer` history), gap list from `gap_ranges`, QC findings rows for sid, manifest entry table (all `Requirement` fields, notes verbatim).
- [ ] **Step 4:** tests+lint. **Step 5:** commit `"feat(dataconsole): series drill-down + svg primitives (task 2)"`.

---

### Task 3: `/class/{name}` lineage pages with de-smoothing overlay

**Files:** Modify `src/ah/dataconsole.py`; test `tests/test_dataconsole.py`.

- [ ] **Step 1: Failing tests**

```python
def test_class_page_lists_raw_and_factors(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/class/equities")
    assert r.status_code == 200
    assert "french.mkt_rf" in r.text
    assert "registered, never fetched" in r.text   # shiller series absent from tiny store
    assert c.get("/class/no-such").status_code == 404


def test_privates_page_shows_desmoothing_overlay(tmp_path):
    root = _tiny_store(tmp_path)
    # append a quarterly albourne series to the same vintage… (build in-test via
    # Catalog API exactly as _tiny_store does; ≥24 obs so glm_ma has data)
    _add_albourne(root, "albourne.pm_buyout_ret_q", n=40)
    c = TestClient(create_app(data_root=root))
    r = c.get("/class/privates")
    assert "de-smoothed" in r.text
    assert "reported" in r.text
    assert r.text.count("<table") >= 1      # side-by-side moments table
```

(`_add_albourne` is a test helper: seeded `numpy.random.Generator(PCG64(0))`, AR(1)-smoothed returns so de-smoothing has something to recover; quarterly dates.)

- [ ] **Step 2:** run → fail. 
- [ ] **Step 3: Implement.** `GET /class/{name}` over `CLASSES`; raw section = per-series `line_svg` + coverage bar + "registered, never fetched" placeholders; factor section renders each factor via the Task 4 factor-loading helper if the factor's inputs exist in the store, else the empty-state card naming what's missing (write `_factor_frame` in THIS task since both pages need it — see Task 4 for its definition; Task 4 only adds the page). Privates: for each albourne series present, chart reported and `glm_ma(values).{recovered-series field}` overlaid (two polylines, legend), moments table with reported vs de-smoothed columns, method labeled (`glm_ma`, k chosen by its own default), quarterly x-axis.
- [ ] **Step 4:** tests+lint. **Step 5:** commit `"feat(dataconsole): asset-class lineage pages + de-smoothing overlay (task 3)"`.

---

### Task 4: `/factors` — the panel as the generator sees it

**Files:** Modify `src/ah/dataconsole.py`; test `tests/test_dataconsole.py`.

**Interface (defined in Task 3, page added here):**

```python
def _factor_frame(cat: Catalog, vintage: str, fs: "FactorSource") -> pd.DataFrame | None:
    """Mechanically recompute one factor for display.

    kind=series  -> the series frame verbatim.
    kind=derived -> getattr(ah.data.derive, fs.expr)(*[frame(sid) for sid in fs.inputs])
    kind=unavailable -> None (page shows fs.reason).
    Missing input series -> None (page shows which input is absent).
    """
```

- [ ] **Step 1: Failing tests**

```python
def test_factors_page_renders_every_declared_factor(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/factors")
    assert r.status_code == 200
    assert "train" in r.text and "validation" in r.text
    assert "SPENT" in r.text                       # holdout labeling
    assert "unavailable" in r.text or "absent" in r.text  # tiny store lacks most inputs


def test_factor_frame_derived_matches_derive(tmp_path):
    """inflation factor recomputed through _factor_frame == calling derive directly."""
    from ah.data import derive
    from ah.dataconsole import _factor_frame
    # build catalog with fred.CPI; look up the factor whose expr is "yoy" in the
    # real manifest; assert frames equal via pd.testing.assert_frame_equal
```

- [ ] **Step 2:** run → fail. 
- [ ] **Step 3: Implement.** Load the factor manifest once per request; row per factor in declared block order: sparkline (`line_svg` small variant), moments, kind/units/numeraire, `proxy_for` chip when set, source-series links, `unavailable` reason verbatim (commodities and hy_spread will show their sealed `missing_factors` state on the real store — that is correct display, not an error). Split shading from `ah.splits.TRAIN/VALIDATION/HOLDOUT` date bounds; holdout band labeled "holdout — SPENT at WP5.6".
- [ ] **Step 4:** tests+lint. **Step 5:** commit `"feat(dataconsole): factor panel page with split shading (task 4)"`.

---

### Task 5: Read-only guard, docs, gate, acceptance, merge

**Files:** Modify `tests/test_dataconsole.py`, `CHANGELOG.md`, `docs/USER-MANUAL.md`, `docs/BUILD-SUMMARY.md`.

- [ ] **Step 1: Guard test** (style of `test_only_keep_handler_writes_to_store` / `test_programme_guard.py`):

```python
def test_dataconsole_is_read_only():
    """The data console's contract: zero write call sites, ever."""
    import inspect

    import ah.dataconsole as dc

    src = inspect.getsource(dc)
    for needle in (
        "write_observations(", "create_vintage(", "advance_pointer(",
        "quarantine_vintage(", "record_qc(", "record_intake(", "register_series(",
        "INSERT", "UPDATE", "DELETE", "to_parquet(", ".save_",
    ):
        assert needle not in src, f"read-only surface contains {needle}"
```

- [ ] **Step 2:** Docs — CHANGELOG entry (third console, port, the four check families, read-only guard); USER-MANUAL subsection "Inspect the generator's input data" with the uvicorn command and what each page answers; BUILD-SUMMARY capability row (postdates-survey note, same as the build console's).
- [ ] **Step 3:** Full gate in the background to a file; **read the log's `EXIT:` line and pass count — the task wrapper's exit code is not the verdict.** Repo-wide ruff/format/pyright.
- [ ] **Step 4: Acceptance walk** against the real store: `/` shows vintage `2026-08-02.4` and the six sources; `/class/credit` shades the pre-1996 HY proxy stretch; `/class/privates` shows the de-smoothing overlay; `/factors` shows commodities+hy_spread as sealed-unavailable and the holdout band labeled SPENT. Screenshot the privates page.
- [ ] **Step 5:** `--no-ff` merge to main with the standard body (built/deviations/discoveries), plain push.

---

## Self-review notes

- Spec coverage: inventory+freshness+QC (T1), drill-down+provenance (T2), lineage+de-smoothing (T3), factor panel+splits (T4), guard+empty-states+acceptance (T5). All four owner-selected check families present.
- Named judgment calls: `CLASSES` factor lists are reconciled against `factors.yaml` in T1 (yaml wins); de-smoothing method pinned to `glm_ma` with the method labeled on the page; two read-before-use names flagged in the interfaces block.
- Type consistency: `_factor_frame` defined once (T3), consumed by T3/T4; SVG helpers defined in T2, reused after.
