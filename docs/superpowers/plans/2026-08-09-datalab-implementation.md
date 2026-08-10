# Datalab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The approved streamlit data console (spec:
`docs/superpowers/specs/2026-08-09-streamlit-data-console-design.md`, owner
rulings 1–3 all YES).

**Architecture:** pure data layer `src/ah/datalab.py` (pandas over Catalog /
manifest / panel surfaces, zero streamlit imports, zero store writes) +
presentation-only `apps/datalab/app.py` + offline tests. Streamlit lives in
an optional `console` dependency group only.

**Tech stack:** streamlit (+ bundled altair) — console group only; pandas;
the existing Catalog / load_requirements / load_manifest /
ah.eval.panel._DERIVED_EXPRS surfaces.

## Global constraints

- Zero write call sites in datalab.py and app.py (guard-tested, the
  dataconsole pattern).
- No network anywhere; the app reads the local catalog only.
- No value/alpha computation (server-authority rule).
- streamlit never imported by src/ah or tests.
- Proxy months never silent; REG downloads carry attribution bytes.
- ASCII in terminal output.

### Task 1: dependency group
- [ ] pyproject.toml: `[dependency-groups] console = ["streamlit>=1.40"]`
      (justification comment: owner-directed 2026-08-09; display-only).
- [ ] `uv sync --group console`; verify `uv run --group console python -c
      "import streamlit, altair"`.

### Task 2: `src/ah/datalab.py` (pure layer)
- [ ] Dataclasses: `FactorRead(factor, frame, unextended, note, share)`,
      `VintageDiff(a, b, status_a, status_b, table)`,
      `SpanAnnotations(train, validation, holdout, holdout_spent,
      campaign2_span, live_span, severe_exclusion)`.
- [ ] `open_catalog`, `series_inventory` (coverage/staleness vs SLA/QC
      state per registered series), `series_frame` (vintage- or as-of-
      pinned).
- [ ] `factor_read`: manifest dispatch; derived inputs read with
      `ah.eval.panel._DERIVED_EXPRS[expr].optional_inputs` blanked-if-
      absent; `unextended` = same read with optional inputs FORCED empty
      (None when the expr has none); `is_proxy` = date absent from
      inputs[0] (the dataconsole:456 rule); `rule_id` labels from a
      per-factor `FACTOR_RULE_LABELS` cutoff table (equity_vol HAR<1986-01
      then VXO<1990-01; fx parity<1973-01 then fx_usd_pre2006<2006-01;
      single-rule families dated by their primary's first observation).
- [ ] `proxy_share(frame, start=None, end=None)` -> overall + by-rule.
- [ ] `har_fan(n_draws, seed, quantiles)`: mu recovered OFFLINE as
      `log(pinned) - paths(fit, 393, 1, PINNED_DRAW_SEED)[0]` (fit from
      the committed provenance artifact), fan = exp(mu + paths(...)),
      per-month quantiles beside the pinned path.
- [ ] `vintage_diff(cat, a, b)`: per-registered-series obs counts in each,
      added/removed/changed, vintage statuses.
- [ ] `span_annotations()`: from ah.splits.TRAIN/VALIDATION/HOLDOUT +
      bootstrap CAMPAIGN2_DRAW_SPAN / live BLOCK_DRAW_SPAN_* constants +
      severe exclusion 1970-01..1979-12; holdout_spent=True (WP5.6).
- [ ] `csv_bytes(frame, contributing_reqs)`: `# licence:` header lines per
      series; `# ATTRIBUTION:` (cmdty_close.ATTRIBUTION) whenever any
      contributing series is REG-tier.

### Task 3: tests (`tests/test_datalab.py`, offline)
- [ ] Tiny-store fixture (test_dataconsole pattern) covering a series +
      equity_mkt inputs + two vintages.
- [ ] series_inventory shape + staleness arithmetic; factor_read
      equity_mkt equals derive.add of its inputs; optional-donor blanking
      (equity_vol with VXO absent -> plain VIX, unextended is None-or-
      equal); proxy_share arithmetic on a constructed frame; har_fan
      determinism + its pinned column == vol_backcast.pinned_draw_series();
      vintage_diff on the two synthetic vintages; span_annotations values;
      csv_bytes REG attribution presence; ZERO-WRITE guard scanning both
      files.
- [ ] Run: `uv run pytest tests/test_datalab.py -q` -> all pass.

### Task 4: `apps/datalab/app.py`
- [ ] Sidebar: page radio (Series / Factors / Extensions / Campaign lens /
      Vintages / Spans), data-root text input (default repo `data/`),
      vintage selectbox (pointer history via current + explicit id entry).
- [ ] Series page: inventory dataframe with staleness highlighting; series
      picker -> altair line + gap markers + split shading + CSV download.
- [ ] Factors page: factor picker -> extended vs unextended overlay, proxy
      shading by rule_id, share table, CSV download (attribution bytes).
- [ ] Extensions page: family picker -> donor/target overlap chart + fit
      stats (family module's own overlap_stats), junction close-up; vol
      family additionally: har_fan quantile band + pinned path, MODEL
      OUTPUT caption with both shas.
- [ ] Campaign lens page: two vintage pickers (defaults 2026-08-02.4 vs
      current), factor multiselect, side-by-side charts + share tables.
- [ ] Vintages page: two ids -> diff table + statuses. Spans page: the
      annotations rendered as a labeled timeline.
- [ ] Every page: WATERMARK caption; holdout shaded with "SPENT (WP5.6)".
- [ ] Smoke: launch headless on 8795, HTTP 200 on /, kill; note in commit.

### Task 5: gate + ship
- [ ] ruff check/format; pyright (datalab.py in the strict tree; app.py
      excluded via pyproject if streamlit stubs noise — record choice).
- [ ] Full suite NOT required (no sealed file touched) — targeted:
      test_datalab + test_dataconsole + test_panel green.
- [ ] CHANGELOG entry; commit; push (standing green-merge authorization;
      work is on main directly? NO — branch `su-eng-datalab`, merge
      --no-ff on green per convention).
