# STEP1-DATA-PLAN.md — Build the Data Layer
## Implementation plan for Claude Code · Alternate Histories Platform · Step 1 (WS-A + WS-C cleaning) · feeds Gate G1

**How to use this file:** work in the existing `alternate-histories/` repo (Step 0 complete: WorldSpec, stores, CLI, CI all live). Place this file at the repo root beside `STEP0-PLAN.md`. Work through WP1.1 → WP1.10 in order, one PR per work package, tests green at every merge. The plan is self-contained; two companion documents are referenced for *content* (series lists, Albourne measure definitions) and should be vendored into `docs/`: `data-requirements-register.md` and `albourne-derived-measures-spec.md`. If they are missing, halt and request them.

---

## 0. Mission

Build the platform's data layer: automated sourcing of public series, disciplined manual intake for licensed series, point-in-time vintage storage, quality control with quarantine, an *auto-generated gap register*, documented proxy extensions for known holes, the de-smoothing module with its diagnostics, derived-metric construction (including everything Design Note DN-1's climate/regime layers require), and scheduled refresh that keeps all of it current without human attention. **No modeling beyond de-smoothing and derived metrics; no generator work; no UI.**

### Definition of done (feeds Gate G1 — all become CI checks or generated reports)
1. `ah data refresh` is idempotent, writes an immutable vintage, runs QC, and updates `DATA-STATUS.md` + `GAPS.md` without manual edits.
2. The monthly **factor panel** assembles 1926→present (core series; deep annual panel 1870→ from JST) into `panel/factors_monthly.parquet` with zero QC violations at `enforce` level.
3. Every series in the catalog carries: source, license tier, methodology link/doc, first/last date, freshness SLA, `is_proxy` flag and splice documentation where applicable.
4. De-smoothing runs on every private-markets series with diagnostics passing: reported vs de-smoothed volatility ratio > 1, beta-to-equity rises, sample mean unchanged within tolerance; results written as derived series with full lineage.
5. Point-in-time integrity: `ah data asof 2026-03-31` reproduces exactly what the panel looked like at that vintage (test: build panel at vintage k, refresh, rebuild at vintage k → identical digest).
6. The **2022 episode pack** exists as a dataset artifact (see WP1.8) and loads via one call.
7. Licensed/manual intakes (Albourne, Nareit, Cliffwater, NCREIF when it arrives) validate against explicit schemas; a malformed drop is rejected with a human-readable report, never partially ingested.
8. Scheduled automation: monthly auto-refresh of public sources; calendar-driven reminder issues for manual intakes; a stale series past its SLA turns CI yellow (warning) or red (enforce), per manifest.

---

## 1. Tech decisions (fixed)

- Extend the Step-0 stack: **Python 3.12, uv, pydantic v2, typer, pytest(+hypothesis, pytest-socket)**.
- **Storage:** raw downloads immutable in `data/raw/<source>/<sha256>.<ext>`; normalized series as **Parquet** in `data/parquet/<vintage>/<source>/<series_id>.parquet`; **DuckDB** (`data/catalog.duckdb`) for the catalog + convenient SQL over parquet; the Step-0 SQLite remains for RunRecords/chronicle only. pandas allowed in `ah/data/` (unlike `core/`).
- **Vintages:** a vintage is a dated snapshot label `YYYY-MM-DD[.n]`. Refresh = new vintage directory + catalog rows; `current` is a pointer (catalog table), advanced **only** if QC passes. Nothing is ever overwritten or deleted. `as_of` reads resolve through the pointer history.
- **Series identity:** `series_id = "<source>.<code>"` (e.g., `fred.DGS10`, `french.mkt_rf`, `jst.usa_ltrate`, `albourne.pm_buyout_ret_q`). One canonical schema for observations: `(date, value, series_id, vintage)`; frequency and units live in the catalog, not the frame.
- **Secrets:** `FRED_API_KEY` from env; no keys in code or fixtures. All connectors retry (exponential, max 5) and rate-limit politely.
- **No network in tests** (pytest-socket): every connector has recorded fixtures (`tests/fixtures/data/<source>/`) captured by a `--record` dev flag.
- **Licensing discipline in code:** catalog column `license_tier ∈ {FREE, REG, COMM}` + `redistributable: bool`; the repo's `.gitignore` excludes `data/` entirely; intake docs state that licensed raw files never leave the machine/bucket.

## 2. Package layout (create in WP1.1)

```
src/ah/data/
├── manifest.py            # loads requirements.yaml → typed Requirements
├── catalog.py             # DuckDB catalog: series registry, vintages, current-pointer
├── connectors/
│   ├── base.py            # Connector protocol: fetch() -> RawArtifact; parse() -> ObsFrame
│   ├── fred.py            # REST, batched, API key
│   ├── french.py          # Ken French zip/CSV parser (research factors, momentum, industry)
│   ├── shiller.py         # ie_data.xls parser (prices, dividends, earnings, CAPE, GS10, CPI)
│   ├── jst.py             # macrohistory .dta parser (annual panel 1870–)
│   ├── bis.py             # credit-to-GDP gap CSV
│   ├── nareit.py          # xlsx parser (manual-drop mode + fetch-if-permitted)
│   ├── treasury_hqm.py    # HQM corporate spot curve xlsx
│   └── intake.py          # generic manual-intake loader (Albourne, Cliffwater, NCREIF)
├── schemas/               # pydantic schemas for each manual-intake file type
│   ├── albourne_pm_returns.py   albourne_hf_returns.py   albourne_derived_cf.py
│   ├── cliffwater_cdli.py       nareit_returns.py        ncreif_returns.py
├── qc.py                  # check framework: per-series + cross-series rules, quarantine
├── splice.py              # documented proxy extensions; is_proxy lineage
├── desmooth.py            # Geltner AR(1), GLM MA(k) MLE, regime-aware stub + diagnostics
├── derive.py              # factor panel assembly + derived metrics (see WP1.6)
├── episode.py             # 2022 (and 2008/2020) episode pack builders
├── refresh.py             # orchestration: plan → fetch → parse → QC → vintage → reports
└── reports.py             # DATA-STATUS.md, GAPS.md, revision diffs
requirements.yaml          # the machine-readable requirements manifest (seed in §3)
docs/data/                 # per-source notes: license, methodology links, quirks
```

## 3. The requirements manifest (seed `requirements.yaml` with this; it is the single source of truth)

Each entry: `series_id, source, code, frequency, units, min_start, sla_days, license_tier, priority, notes`. Seed set (extend via PR whenever a downstream WP discovers a need — see §WP1.9):

```yaml
# — rates & inflation (FRED unless noted) —
fred.DGS10:    {code: DGS10,  freq: D→M, units: pct, min_start: 1962-01, sla: 7}
fred.DGS2:     {code: DGS2,   freq: D→M, units: pct, min_start: 1976-06, sla: 7}
fred.TB3MS:    {code: TB3MS,  freq: M,   units: pct, min_start: 1934-01, sla: 35}
fred.GS10:     {code: GS10,   freq: M,   units: pct, min_start: 1953-04, sla: 35}
fred.BAA:      {code: BAA,    freq: M,   units: pct, min_start: 1919-01, sla: 35}
fred.AAA:      {code: AAA,    freq: M,   units: pct, min_start: 1919-01, sla: 35}
fred.HY_OAS:   {code: BAMLH0A0HYM2, freq: D→M, units: pct, min_start: 1996-12, sla: 7}
fred.CPI:      {code: CPIAUCNS, freq: M, units: index, min_start: 1913-01, sla: 40}
fred.CPI_CORE: {code: CPILFENS, freq: M, units: index, min_start: 1957-01, sla: 40}
fred.T5YIE:    {code: T5YIE,  freq: D→M, units: pct, min_start: 2003-01, sla: 7}
fred.T10YIE:   {code: T10YIE, freq: D→M, units: pct, min_start: 2003-01, sla: 7}
fred.VIX:      {code: VIXCLS, freq: D→M, units: idx, min_start: 1990-01, sla: 7}
fred.UNRATE:   {code: UNRATE, freq: M,   units: pct, min_start: 1948-01, sla: 40}
fred.GDPC1:    {code: GDPC1,  freq: Q,   units: lvl, min_start: 1947-01, sla: 100}
fred.INDPRO:   {code: INDPRO, freq: M,   units: idx, min_start: 1919-01, sla: 40}
fred.USREC:    {code: USREC,  freq: M,   units: 0/1, min_start: 1854-12, sla: 40}
# — equity & factors —
french.mkt_rf / french.smb / french.hml / french.mom / french.rf:
               {source: french, freq: M, min_start: 1926-07, sla: 60}
shiller.price / shiller.dividend / shiller.earnings / shiller.cape:
               {source: shiller, freq: M, min_start: 1871-01, sla: 60}
nareit.all_equity_tr: {source: nareit, freq: M, min_start: 1972-01, sla: 45, license: REG, intake: manual}
# — deep history & credit cycle —
jst.<country>_<var>: {source: jst, freq: A, min_start: 1870, sla: 400, vars: [ltrate, stir, cpi, gdp, tloans, eq_tr, housing_tr, crisis]}
bis.credit_gap_us: {source: bis, freq: Q, min_start: 1961-03, sla: 120}
treasury.hqm_curve: {source: treasury_hqm, freq: M, min_start: 1984-01, sla: 45}
# — alternatives (manual intake; schemas in src/ah/data/schemas) —
albourne.pm_<strategy>_ret_q: {intake: manual, freq: Q, sla: 120, license: COMM, strategies: [buyout, growth, vc, secondaries, dl, mezz, distressed, re_va, infra]}
albourne.hf_<strategy>_ret_m: {intake: manual, freq: M, sla: 60,  license: COMM, strategies: [els, macro, rv, event, credit, cta, multi]}
albourne.cf_<group>:          {intake: manual, freq: per-spec, sla: 200, groups: [A_lifecycle, B_calendar_rates, C_age_calendar, D_vintage, E_episodes]}
cliffwater.cdli_ret_q: {intake: manual, freq: Q, min_start: 2004-09, sla: 130, license: REG}
ncreif.npi_ret_q / ncreif.odce_ret_q: {intake: manual, freq: Q, min_start: 1978-03, sla: 130, license: COMM, status: pending-license}
```

Notes encoded per entry where relevant: `fred.TEDRATE` is **deliberately included as retired** (discontinued 2022-01) to exercise series-retirement handling; funding-stress post-2022 uses a documented SOFR-based replacement — mark that computation in `derive.py`, not a fake continuation.

## 4. Work packages

### WP1.1 — Manifest, catalog, vintage store
`requirements.yaml` (seed above) + `manifest.py`; DuckDB catalog with tables `series`, `vintages`, `observations_index`, `current_pointer`, `intake_log`, `qc_results`; vintage write path + as-of read path. Tests: vintage immutability (second write to same vintage fails), pointer-advance-only-on-QC-pass, as-of determinism.

### WP1.2 — Public connectors: FRED, French, Shiller, JST, BIS, Treasury HQM
One connector per source implementing the protocol; D→M aggregation rule fixed (monthly mean for rates/spreads, month-end for VIX — state it in code and docs); French zip parsing incl. the trailing annual-block quirk; Shiller xls column drift guarded by header assertions; JST .dta with country filter (start: USA; keep all countries in raw). Fixtures for each; golden parse tests. `docs/data/<source>.md` per source: exact URL, license position, methodology link, known quirks. **Verify all URLs at build time; if any endpoint has moved, fix the connector and note it in the source doc — do not hardcode workarounds silently.**

### WP1.3 — Manual-intake framework + licensed schemas
`intake.py`: drop directory `data/intake/<source>/`, file naming convention `<series-group>_<asof>.csv|xlsx`, checksum, schema validation (pydantic, per file type in `schemas/`), rejection report on any violation (missing columns, unit anomalies, duplicate periods, silent gaps), provenance record (who/when/file hash) into `intake_log`. Implement schemas for: Albourne PM strategy returns, Albourne HF strategy returns, **Albourne derived cashflow measures groups A–E exactly per `albourne-derived-measures-spec.md`** (lifecycle profiles with p25/p75; quarterly calendar rate series; age×calendar matrices with fund counts; vintage quartiles; episode cuts), Cliffwater CDLI, Nareit, NCREIF (schema now, data later). Acceptance: a deliberately corrupted fixture of each type is rejected with a useful report; a clean fixture round-trips to parquet.

### WP1.4 — QC framework
Rule types: schema/dtype; date monotonic, no duplicates; frequency conformance; bounds per units class (rates ∈ [−5, 30], spreads ≥ 0, index > 0, returns ∈ [−80%, +200%] monthly); staleness vs SLA; jump detection (|Δ| > k·rolling σ → warn); **revision diff** vs prior vintage (report all changed historical values; tolerance per source — FRED revisions normal, French rewrites normal, licensed files should not silently rewrite history → enforce-level alarm); cross-series identities (HY spread ≈ HY yield − Treasury where both exist; CPI yoy from index consistent; USREC dates match NBER doc). Severity `enforce|warn` from manifest. Failing enforce ⇒ vintage quarantined, pointer not advanced, `qc_results` written, CI red.

### WP1.5 — Splice & proxy framework (gap-filling that never lies)
`splice.py`: a `ProxyRule` = target series, donor series, transform (level map, regression on overlap, or ratio link), overlap-fit window, and documentation string; output written as a **new** series `<target>__extended` with per-observation `is_proxy` flag and rule id. Implement the known rules from the register: HY OAS pre-1996 from Baa−Aaa (regression on 1996–2005 overlap); long-Treasury TR pre-1973 constructed from yields (duration approximation, documented); private credit pre-2004 from BDC/HY blend (donor prep in derive); Nareit-derived de-levered RE proxy (for cross-checks). Property tests: on the overlap window, extended == donor-transformed within fit tolerance; no proxy observation ever overwrites an actual one.

### WP1.6 — Derived metrics & the factor panel (`derive.py`)
Build order matters; everything writes back as catalogued derived series with lineage (inputs + code version).
**(a) Panel primitives:** excess returns (mkt−rf etc.); term spread (GS10−TB3MS; 10y−2y where avail.); credit spreads (BAA−AAA, BAA−GS10); real 3m rate; CPI yoy + core yoy; realized equity vol (from daily where available, else |r| EWMA); equity drawdown state; dividend yield & payout (Shiller); **CAPE and demeaned log-CAPE (DN-1's v_t)**; **credit-to-GDP gap (DN-1's L_t; BIS primary, JST tloans/gdp for pre-1961)**; curve slope + inversion flag; funding-stress composite (TED to 2021-12, documented SOFR-basis after).
**(b) Regime labels v1 (rule-based, per D2 placeholder):** monthly label ∈ {EXP, SLOW, REC, CRI, STAG, REF} from USREC, drawdown, HY spread level/Δ, CPI yoy, growth proxy (INDPRO yoy); ruleset in one pure function + one YAML of thresholds; version stamped (`regime_ruleset_v1`); confusion table vs NBER as a report, not a test.
**(c) The panel:** `factors_monthly.parquet` 1926→ (columns: the D2 candidate list + primitives above) and `panel/deep_annual.parquet` 1870→ from JST. Panel assembly asserts: no gaps at monthly frequency after each series' start; all units annualized-% or monthly-decimal per a units registry; a `PANEL.md` data dictionary is generated, not hand-written.
**(d) Strategy sleeves:** Albourne PM/HF series normalized to common conventions (net-of-fees flag from metadata, USD, quarterly/monthly as delivered) — *not* mapped to factors here (that is Step 3); just clean, catalogued, de-smoothing-ready.

### WP1.7 — De-smoothing module (`desmooth.py`)
Implement: **Geltner AR(1)** reversal (per-series φ estimated, then r_true = (r_obs − (1−a)·r_obs,lag)/a form documented precisely); **GLM MA(k)** — observed = Σ θ_j r_true,t−j, θ nonneg, sum 1, MLE under Gaussian truth, k ∈ {1,2,3} selected by AIC (default report k=2); **regime-aware stub**: θ estimated separately in crisis vs normal months (regime labels from WP1.6b) behind the same interface, flagged experimental. Diagnostics per series, written to a generated `DESMOOTHING.md`: σ ratio (de-smoothed/reported), β to equity before/after, mean difference (must be ~0; test tolerance), Ljung–Box on residual autocorrelation, θ estimates + CIs. Applies to: every `albourne.pm_*`, `cliffwater.cdli`, `ncreif.*` (when present), `nareit`-based RE proxy for comparison. Hypothesis property test: smoothing-then-de-smoothing on simulated known-truth series recovers volatility within tolerance across parameter draws.

### WP1.8 — Episode packs (`episode.py`)
Dataset builders returning tidy frames + a generated markdown brief for: **2022–23** (rates shock: factor paths, HY spread path, reported-vs-de-smoothed PM sleeves, Albourne group-E cuts when present, secondary-pricing table hand-entered from public reports with citations in `docs/data/secondaries.md`); **2008–10** and **2020** (same shape). These are the fixtures Gate G1's reproduction test will consume. Acceptance: `ah data episode 2022` emits the pack; the brief renders; all inputs resolve through the catalog (no ad-hoc reads).

### WP1.9 — Gap register & emergent-requirements loop (`reports.py`)
`GAPS.md` generated per refresh from manifest vs catalog: per required series — coverage %, missing head/tail ranges, proxy rules applied (with is_proxy share), license blockers (e.g., NCREIF pending), staleness. Plus `DATA-STATUS.md`: vintage id, per-source freshness, QC summary, revision-diff highlights. **Emergent-requirements rule (process, enforced by convention + PR template):** any workstream needing an unregistered series adds it to `requirements.yaml` with priority + rationale in the same PR — the manifest stays the single source of truth. Seed the "anticipated additions" section of GAPS.md with known-likely needs: MSCI World (COMM pending), commodities index (COMM decision open), HFRI cross-check, EDHECinfra, PitchBook/LCD multiples & leverage series, dry-powder aggregates, Green Street cap rates, SOA mortality tables (Step 3 twin), daily equity returns for vol-state refinement.

### WP1.10 — Refresh orchestration, scheduling, CLI
`ah data refresh [--source S] [--vintage YYYY-MM-DD] [--dry-run]`: plan (manifest ∩ due-by-SLA) → fetch/parse (or intake scan) → QC → vintage commit or quarantine → derive (panel + de-smoothing re-run if inputs changed) → reports. Idempotent: re-running produces the same vintage content and detects it (no duplicate vintage). `ah data asof DATE`, `ah data status`, `ah data episode YEAR`, `ah data intake validate <file>`. **GitHub Actions:** `data-monthly.yml` (cron, public sources; commits nothing — runs against a data volume/bucket; posts status artifact + opens an issue on QC failure) and `data-reminders.yml` (opens calendar issues: Albourne quarterly drop due, Cliffwater CDLI due, Nareit monthly, JST annual check). Local/dev runs work without any cloud dependency.

## 5. PR sequence & estimates
WP1.1 → WP1.2 → WP1.3 → WP1.4 (framework can start after 1.1) → WP1.5 → WP1.6 → WP1.7 → WP1.8 → WP1.9 → WP1.10. Rough shape: 1.1–1.2 ≈ days 1–3; 1.3–1.4 ≈ days 3–5; 1.5–1.6 ≈ days 5–8; 1.7 ≈ days 8–9; 1.8–1.10 ≈ days 9–12 of focused sessions. ~3–4k LOC src + similar tests.

## 6. Explicit non-goals
Factor→strategy mappings, cashflow modeling, TA calibration (Step 3); any generator training (Step 2); Bayesian L1 estimation (Step 2 — but its *inputs* (CAPE, credit gap, JST panel) are in scope here and must be present); dashboards; cloud infra beyond the two Actions workflows; multi-country panels beyond keeping JST raw complete (model USA-first).

## 7. Foreseeable pitfalls (read before coding)
Ken French files change format at year boundaries — assert headers, don't index by position. Shiller's xls has merged headers and footnote rows — parse defensively, snapshot-test. FRED revisions rewrite history — that is what vintages are for; never diff-and-panic, diff-and-report. Daily→monthly aggregation choices change results — one documented rule per units class, tested. De-smoothing MLE can hit boundary solutions (θ→[1,0,0]) on short series — bound k by sample length, report CIs, and fall back to Geltner with a warning rather than fabricating precision. Licensed files will arrive with human-made column drift — schemas must fail loudly and kindly (say exactly what's wrong). Time zones and month-end conventions: standardize on period-end dates, UTC-naive, and test a February.

## 8. Relationship to gates and decisions
This plan discharges the data half of Gate G1 and produces the inputs for decisions D1 (de-smoothing method — the DESMOOTHING.md diagnostics are the workshop exhibit), D2 (factor list — the panel is the candidate set; regime ruleset v1 is the placeholder to ratify or replace), D6 (threshold pre-registration uses the panel's reference statistics), and D7 (Albourne groups A/B land here, ready for calibration in Step 3). The 2022 episode pack (WP1.8) is the shared fixture for the G1 end-to-end reproduction test.
