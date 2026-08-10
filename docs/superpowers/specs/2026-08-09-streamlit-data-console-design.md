# Streamlit data console ("datalab") — design

*Drafted 2026-08-09 while the H.10 waiter runs. Status: for owner review —
no implementation until approved. Companion surfaces: `ah.dataconsole`
(8796, static read-only pages), the QA inspection console (8799), the build
console (8798), `ah.credibility` (admin).*

## What it is, and why it is not the existing dataconsole

`ah.dataconsole` renders **fixed** pages: per-asset-class series summaries,
one chart per series, current vintage only. The repeated interrogation
pattern it cannot serve — and tonight's campaign-3 work made acute — is
**interactive**: "show me equity_vol extended vs unextended on THIS
vintage", "which months of fx_usd are parity proxy and what is the proxy
share over 1953–1972", "what changed between vintage 2026-08-02.4 and the
campaign-3 vintage", "overlay the pinned HAR draw on the full ensemble
fan". A Streamlit app is the right shape for that: widgets → pandas →
chart, no route plumbing per question.

The two consoles coexist: dataconsole stays the stable, dependency-free
reference surface; datalab is the interrogation bench. Nothing moves out of
dataconsole.

## Goals

1. Interrogate any **registered series**: coverage, gaps, staleness vs SLA,
   QC/quarantine state, vintage time-travel (as-of reads through pointer
   history), source provenance.
2. Interrogate any **factor** as the generator actually reads it: the
   sealed `read_factor_frames` surface on a chosen vintage, extended vs
   unextended overlay, proxy months shaded **by rule_id**, live per-factor
   proxy share (AM-2026-08-09-002's disclosure quantity).
3. Interrogate the **seven extension families**: donor-vs-target overlap
   fits, junction close-ups (fx 1973-01, vol 1986-01), and the pinned HAR
   draw against the regenerated full ensemble fan (owner decision D2: tail
   readers regenerate from the provenance artifact).
4. **Vintage diff**: two vintage ids → series added/removed, observation
   count deltas, pointer history, quarantine log.
5. **Spans page**: train/validation shading, holdout marked SPENT, the
   campaign-2 vs live sealed block_draw_span, the severe-test excluded
   decade.

Non-goals: any write to the store (hard contract, guard-tested); any value
or scoring computation (the server-authority rule); any network fetch (the
app reads the local catalog only); replacing dataconsole or the hub.

## Approaches considered

- **A. Grow `ah.dataconsole`** (no new dependency). Rejected: every
  interactive question becomes a route + query-param page; the FastAPI/HTML
  string idiom is the wrong tool for linked widgets, and the owner asked
  for Streamlit.
- **B. Streamlit app + a pure helper module inside the package
  (recommended).** All data logic lives in `src/ah/datalab.py` — pure
  pandas over `Catalog`/`load_requirements`/`read_factor_frames`, **no
  streamlit import** — so it is fully testable offline under the existing
  no-network CI. The Streamlit file itself lives OUTSIDE the package
  (`apps/datalab/app.py`), is presentation-only, and is never imported by
  tests.
- **C. marimo/Jupyter notebook.** Rejected: not what was asked; notebooks
  drift and are not a shareable console.

## Dependency ruling (needs the stated justification)

`streamlit` (+ its bundled `altair` for charts — no separate chart dep) as
a **new optional dependency group `console`** in `pyproject.toml`:

- never imported by `src/ah` modules or tests → the test environment, the
  no-network invariant, and the CI gate are untouched;
- installed only via `uv sync --group console`;
- justification: owner-directed ("design a data console using streamlit",
  2026-08-09); the interrogation use-cases above.

Launch: `uv run --group console streamlit run apps/datalab/app.py --server.port 8795`
(joining the 879x console family; ASCII-only terminal output).

## Architecture

```
apps/datalab/app.py          # streamlit shell: sidebar, pages, widgets, charts
src/ah/datalab.py            # PURE data layer (no streamlit), all logic below
tests/test_datalab.py        # offline tests over a fixture catalog + zero-write guard
```

`src/ah/datalab.py` public surface (all read-only, all returning plain
frames/dataclasses):

- `open_catalog(data_root) -> Catalog` — thin, and the ONLY place the app
  touches the store.
- `series_inventory(catalog, reqs, asof) -> DataFrame` — one row per
  registered series: coverage, n_obs, last obs, staleness vs SLA, enforce
  level, license tier, intake mode, current-vintage QC state.
- `series_frame(catalog, series_id, vintage=None, asof=None) -> DataFrame`
  — vintage-pinned or as-of read through pointer history.
- `factor_read(catalog, factor, vintage) -> FactorRead` — the factor's
  frame via the SEALED `ah.eval.panel.read_factor_frames` on a
  vintage-pinned `DataAccess`, plus: the unextended fallback frame (donor
  inputs blanked), per-month `rule_id` provenance recomputed through the
  extension modules (the dataconsole:456 lesson: the panel strips per-row
  proxy flags, so provenance is recomputed at display, never invented),
  and `proxy_share` (overall + per rule + over an arbitrary window).
- `extension_overlay(catalog, family, vintage) -> ExtensionOverlay` —
  donor/target frames, overlap window, fit stats from the family's own
  `fit_*`/`overlap_stats`, junction month.
- `har_fan(n_draws, seed) -> DataFrame` — the full ensemble quantile fan
  regenerated from the provenance artifact via `vol_backcast`, beside the
  pinned draw (labeled MODEL OUTPUT; sha shown).
- `vintage_diff(catalog, a, b) -> VintageDiff` — series added/removed,
  per-series obs deltas, pointer/quarantine history between two ids.
- `span_annotations() -> SpanAnnotations` — split boundaries from
  `ah.splits`, holdout SPENT flag, CAMPAIGN2_DRAW_SPAN vs live sealed span,
  the severe-test exclusion decade — read from the code/sealed constants,
  never restated by hand.

Streamlit pages (sidebar radio): **Series · Factors · Extensions ·
Vintages · Spans**. Every chart carries the dataconsole watermark line and
the split shading; holdout months render with the SPENT label. Caching via
`st.cache_data` keyed on `(vintage_id, series_id/factor)` — sound because
vintages are immutable by construction.

## Honesty rails (each carried into implementation as a test or a visible label)

- **Zero writes**: `tests/test_datalab.py` scans `ah/datalab.py` and
  `apps/datalab/app.py` for the store's write call names (the existing
  dataconsole guard pattern, reused).
- **Proxy months are never silent**: any chart of a factor with proxy
  provenance shades them and prints the share; HAR months additionally
  carry "MODEL OUTPUT (PROXY-EQUITY-VOL-HAR-V1, pinned draw sha 53a378a4…)".
- **The holdout is visible but labeled SPENT** — a display surface reads
  full history (the `ah data episode` posture), and says so on screen.
- **No number invented in the app**: every statistic shown comes from a
  sealed surface, an extension module's own fit function, or plain pandas
  aggregation of store rows; `datalab.py` docstrings name the source of
  each.

## Testing

Offline fixture catalog (the existing `gen_data_fixtures` machinery):
inventory shape and staleness arithmetic; factor_read equivalence with a
direct `read_factor_frames` call; proxy-share arithmetic on a constructed
frame with known proxy months; vintage_diff on two synthetic vintages;
har_fan determinism in `(n_draws, seed)`; the zero-write guard. The
Streamlit file gets no tests (presentation-only, thin by construction).

## Open questions for the owner

1. Port 8795 and the name "datalab" acceptable?
2. Should the Factors page offer a CSV download button (trivial in
   Streamlit; the store is licensed data — REG series would need the
   attribution string embedded in the download)?
3. Any appetite for a "campaign lens" toggle (campaign-2 vintage vs
   campaign-3 vintage side-by-side) as a first-class page, or is the
   Vintages diff page sufficient?
