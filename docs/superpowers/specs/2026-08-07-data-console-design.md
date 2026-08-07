# Generator-input data console — design

**Date:** 2026-08-07
**Status:** design approved by owner (this conversation); HTML over Streamlit
confirmed by owner; implementation not started.
**Decisions taken with the owner:** full raw→factor lineage per asset class;
all four check families (coverage/gaps/freshness, splice/proxy provenance,
de-smoothing for privates, distribution sanity); server-rendered HTML, no new
dependencies.

## What this is

A read-only dashboard for inspecting the data that goes INTO the generator —
the equities, bonds/rates, credit, macro and private-markets (PE/PC/RE) series
— at both layers: the raw registered series (with their splice/proxy history
and QC state) and the derived factor panel the generator actually trains on.

Third sibling in the console family, one module per surface per port:

| port | module | contract |
|---|---|---|
| 8799 | `ah/console.py` | QA inspection — read-only over recorded outputs |
| 8798 | `ah/buildconsole.py` | scenario building — writes only on Keep |
| **8796** | **`ah/dataconsole.py`** | **data inspection — read-only over the vintage store** |

Same chrome and SVG idiom as the other two (copied technique, not imported —
each console's guarantee stands alone). Every nav bar cross-links the three.

## What it reads (and never writes)

- The immutable Parquet vintage store via `ah/data/catalog.py` (DuckDB reads,
  `as_of`/current-pointer resolution as the CLI reports use it).
- `requirements.yaml` via `ah/data/manifest.py` — the series registry with
  SLA, min_start, enforce level, and the notes that carry splice/retirement
  history.
- QC results as recorded by the data layer.
- The sealed derivation surfaces — `ah/data/derive.py`, the de-smoothing
  module, `factors.yaml` — **imported to recompute display views only**.
  Several are named in `pre-registration.lock`; this project edits none of
  them (verified against the lock's `hashed_files` before implementation).

**Read-only guard:** a source-scan/import-graph test in the style of
`tests/test_programme_guard.py` asserts the module has no store-writing call
sites at all (no `save_*`, no SQL INSERT/UPDATE, no parquet writes, no
pointer advancement). This console has no keep button and no cache.

**Leakage posture:** a display surface reading the catalog directly, exactly
like `ah data episode`. It creates no new normalization/reference surface;
train/validation windows are drawn as labeled shading so the viewer can see
what the generator trained on. The holdout window, where shown, is labeled
"holdout — SPENT at WP5.6".

## Pages

### `/` — the inventory
- Header: current vintage id, as-of date.
- Per-source freshness vs SLA: latest observation per source, red where any
  series breaches its `sla_days` (the manifest's warn-only registrations —
  discontinued/retired series — show their documented permanent-staleness
  note instead of red).
- QC summary: enforce/warn pass-fail counts as recorded.
- Series inventory: one row per registered series — start, end, months of
  gap, staleness, **% of history proxy-spliced**, enforce level; row links to
  `/series/{id}`.
- Asset-class cards linking to `/class/{name}`.

### `/class/{name}` — lineage per asset class
Classes: `equities`, `rates-bonds`, `credit`, `inflation-macro`, `fx`,
`privates` (PE/PC/RE together). Grouping is defined in the dashboard module
as a display mapping over registered series ids — it invents no data.
- Top: each raw series feeding the class — line chart with **proxy-spliced
  stretches shaded** and a coverage bar (observed vs gap months).
- Bottom: the derived factor(s) consumed by the generator — line chart,
  histogram, moments table (mean, vol, skew, excess kurtosis; monthly and
  annualized where meaningful).
- `privates` page additionally overlays **reported vs de-smoothed** series
  per sleeve with both moment sets side by side, sourced from the same
  de-smoothing code the data layer runs — recomputed, never restyled.

### `/series/{id}` — drill-down
Full-history chart (proxy shading), vintage list with current pointer, gap
list (explicit month ranges), QC findings for the series, and the manifest
entry verbatim (source, code, frequency, units, SLA, notes).

### `/factors` — the panel as the generator sees it
One row per factor in `factors.yaml`: sparkline over full history,
moments, source-series links, with train/validation/holdout windows shaded
and labeled. Display only.

## Error handling

A missing or empty local vintage store renders the same "Not available —
produce it with `uv run ah data refresh ...`" empty-state cards the QA
console uses, never a traceback. A series registered in the manifest but
absent from the store is listed with status "registered, never fetched".

## Testing

- Pure functions (gap detection, proxy-run detection, coverage %, moments,
  staleness-vs-SLA) unit-tested directly.
- Pages end-to-end with TestClient against a tiny synthetic vintage store
  built in `tmp_path` (same `enable_socket` opt-in as the other console
  tests; no network).
- The read-only guard test.
- Acceptance walk: open all four page types against the real local store
  (vintage `2026-08-02.4`), confirm the privates page shows the de-smoothing
  overlay and the credit page shades the pre-1996 HY-spread proxy stretch.

## Out of scope (deliberate)

- Streamlit or any new dependency (owner-confirmed; revisit only if
  link/query-param interactivity proves insufficient).
- Editing anything sealed; triggering refreshes from the browser (refresh
  stays `ah data refresh` on the CLI).
- Intake of new series; QC re-runs (display of recorded results only).

## Sequencing

One WP, branch `data-console-01`, full gate, `--no-ff` merge, plain push.
