# Changelog

All notable changes to this project are documented here. The project follows
[Conventional Commits](https://www.conventionalcommits.org/) and
[Keep a Changelog](https://keepachangelog.com/) conventions.

## [Unreleased] — Step 1 (data layer)

### Added
- **WP1.10 — Refresh orchestration, scheduling, CLI.** `refresh.py`: `plan`
  (manifest ∩ due-by-SLA ∩ source, auto-intake only) → provider fetch/parse → QC →
  vintage commit or quarantine → reports; idempotent (re-running a vintage id is a
  detected no-op). `ah data` CLI: `refresh [--fixtures --vintage --source --asof
  --dry-run]`, `status`, `asof DATE`, `episode YEAR`, `intake validate <file>`.
  GitHub Actions `data-monthly.yml` (cron public refresh, status artifact, issue on
  QC failure) and `data-reminders.yml` (calendar issues for manual intakes); local/dev
  works without cloud.
- **WP1.9 — Gap register & reports.** `reports.py`: `gap_register` computes per
  required series coverage %, missing head/tail, staleness, and license blockers from
  the manifest vs the catalog; `generate_gaps_md` emits GAPS.md with an "anticipated
  additions" section (MSCI World, commodities, HFRI, EDHECinfra, PitchBook/LCD,
  dry-powder, Green Street, SOA mortality, daily equity) and the emergent-requirements
  rule. `generate_data_status_md` emits DATA-STATUS.md (vintage, per-source freshness,
  QC summary, revision-diff highlights).
- **WP1.8 — Episode packs.** `episode.py`: builders for 2008-10, 2020, 2022-23 that
  resolve inputs **through the catalog** (no ad-hoc reads), slice to the episode
  window, add reported-vs-de-smoothed private-markets sleeves, attach the cited
  secondary-pricing table (`docs/data/secondaries.md`, incl. the ~81% NAV 2022 anchor),
  and render a markdown brief. These are the fixtures Gate G1's reproduction test will
  consume.
- **WP1.7 — De-smoothing module.** `desmooth.py`: Geltner AR(1) reversal
  (r_true = (r_obs − (1−a)·r_obs,lag)/a, a = 1−phi); GLM MA(k) — θ≥0, Σθ=1 estimated
  on the simplex by whitening the recovered truth, k∈{1,2,3} by AIC (default 2), with
  a boundary-solution fallback to Geltner (+warning) when θ₀≥0.9; experimental
  regime-split `regime_glm`. Diagnostics (σ ratio, β to equity before/after, mean
  difference, Ljung-Box) rendered to `DESMOOTHING.md`. Hypothesis property:
  smooth-then-de-smooth recovers volatility within tolerance. numpy-only, deterministic.
- **WP1.6 — Derived metrics & factor panel.** `derive.py` primitives (spreads/excess
  returns via `difference`, `yoy`, `realized_vol`, `drawdown_state`,
  `demeaned_log_cape` = DN-1 v_t, `credit_to_gdp_gap` = L_t with JST pre-1961
  extension, `funding_stress` with TED→SOFR cutover). Regime labels v1: a single pure
  `label_regime` + `regime_thresholds.yaml` stamped `regime_ruleset_v1`, `label_series`,
  and an NBER confusion report. Panel assembly (`assemble_panel`) asserts no monthly
  gaps after each column's start, carries a `UNITS_REGISTRY`, and `generate_panel_md`
  produces the data dictionary.
- **WP1.5 — Splice & proxy framework.** `splice.py`: `ProxyRule` + fitted transforms
  (regression/level_map/ratio/scale), backward extension to `<target>__extended` with
  per-obs `is_proxy` + rule id (actuals never overwritten), `overlap_error`. Register
  rules: HY OAS pre-1996, long-Treasury TR pre-1973, private credit pre-2004, Nareit
  de-levered RE.
- **WP1.4 — QC framework.** `qc.py`: per-series checks (schema/dtype, monotonic
  non-duplicate dates, frequency conformance, unit-class bounds — rates [-5,30],
  spreads ≥0, index >0, returns [-80%,+200%], staleness vs SLA, jump detection using
  the prior window's σ, revision diff vs prior vintage with source-based severity:
  public revisions warn, licensed rewrites enforce) + cross-series identities
  (Baa ≥ Aaa). Severity inherits the manifest `enforce` flag. `run_qc` persists
  `qc_results` and quarantines the vintage on any enforce failure — the pointer then
  cannot advance. `Requirement` is now frozen/hashable.
- **WP1.3 — Manual-intake framework + licensed schemas.** `schemas/base.py`
  (declarative `IntakeSchema`: required columns, dtype/bounds, duplicate-period and
  silent-gap detection, human-readable rejection report) + concrete schemas:
  Albourne PM returns, Albourne HF returns, Albourne derived cashflow groups A-E
  (lifecycle p25/p75, calendar rates, age×calendar with fund counts, vintage
  quartiles, episode cuts), Cliffwater CDLI, Nareit, NCREIF. `intake.py`:
  `<series-group>_<asof>` filename convention, checksum, validate (never partially
  ingested), `to_series_frames` (strategy→canonical series), `ingest_file` records
  provenance to `intake_log`. Corrupted fixtures (dup/out-of-bounds/missing/gap)
  rejected with a report; clean fixtures round-trip to parquet.
- **WP1.2 — Public connectors.** `connectors/base.py` (Connector protocol,
  RawArtifact, D->M aggregation: monthly mean for rates/spreads, month-end for VIX;
  retrying fetch helper) plus FRED (observations JSON), Ken French (zip/CSV,
  monthly-block/annual-block quirk), Shiller (xlsx, content-located header, fractional
  dates), JST (.dta, USA filter), BIS (credit-gap CSV), Treasury HQM (xlsx, 10y spot).
  `fetch()` is network-only (never tested); `parse()` covered by golden tests over
  format-faithful offline fixtures (`scripts/gen_data_fixtures.py`). `docs/data/<source>.md`
  per source (URL, license, quirks). Added `openpyxl`.
- **WP1.1 — Manifest, catalog, vintage store.** `requirements.yaml` (normalized seed
  of STEP1-DATA-PLAN §3) + `ah/data/manifest.py` (typed `Requirement`/`Requirements`,
  redistributable = FREE only). `ah/data/catalog.py`: DuckDB catalog
  (`series`, `vintages`, `observations_index`, `current_pointer`, `intake_log`,
  `qc_results`) with an immutable Parquet vintage store — canonical schema
  `(date, value, series_id, vintage)`, re-writing a (vintage, series) raises,
  the `current` pointer is append-only and advances only when a vintage is not
  quarantined (QC gate), and `as_of` reads resolve through the pointer history.
  Added `duckdb` + `pyarrow` deps.

## [Unreleased] — Step 2 (generator layer)

### Added
- **WP2.1 — Experiment infra, splits, leakage guards, registry.** `splits.py`:
  train/validation/holdout spans with a `DataAccess` guard — the holdout is reachable
  only via a `FinalEvaluationToken` minted solely in `ah.eval.g2`, proven by an
  import-graph test that no `ah.gen` module imports that mint; `train_val()` is the
  reference/normalization surface (holdout excluded). `experiment.py` + `ah exp`
  (list/show/diff): deterministic config hashing, git SHA, seed, `experiments/<id>/`.
  `gen/base.py` (`Generator` protocol + `Ensemble` with full lineage metadata),
  `gen/registry.py` (resolve WorldSpec `generator_id`; unknown ids error).
- **WP2.1b Task 1 — Factor manifest with a block layer (pre-seal patch).**
  `factors.yaml` (repo root): `factor_blocks` (`global`, `us`, `uk`) +
  `active_blocks: [global, us]`; a jurisdiction addition later is an additive
  `block_addition` amendment, never a re-seal of existing blocks. `factors.py`
  (top-level, peer of `splits.py` — not under `gen/` or `eval/`, so `ah.gen` keeps
  no dependency on `ah.eval`): `FactorManifest` (`active_factors()`, `block_of()`,
  `cross_block_pairs()`, `is_active()`) + `load_manifest()`, `lru_cache`'d by resolved
  path so repeated calls return the same object; validates active-block references,
  no factor in two blocks, no empty block. `EnsembleMeta` gains `active_blocks:
  tuple[str, ...] = ()`; `battery/report.py`'s `BatteryReport` gains the same field,
  populated from `load_manifest()`.
- **WP2.1b Task 1 review fixes.** `FactorManifest.blocks` is now wrapped in
  `types.MappingProxyType` before being stored on the frozen dataclass, so the
  identity-cached `load_manifest()` object can no longer be mutated through its
  `blocks` mapping (the frozen dataclass only blocked attribute reassignment, not
  mutation of the dict's contents). `active_blocks` non-string/empty-entry errors
  now interpolate the offending value, matching the two parallel checks nearby.
  Added tests for the previously-untested "factor names and block ids must be
  non-empty strings" validation branches (empty-string factor, non-string factor,
  empty-string `active_blocks` entry) and for the new `blocks` immutability.
- **WP2.1b Task 2 — D4 benchmark-strategy set over generator outputs only (pre-seal
  patch).** The D4 set (VaR/ES tail fidelity, and the WP2.8 tail auxiliary loss)
  previously included an "endowment mix" defined over portfolio sleeves, which the
  battery could not compute without Step-3 machinery and an unfrozen sleeve
  taxonomy. `strategies.py` (top-level, peer of `factors.py`/`splits.py` — not under
  `eval/`, so `ah.gen.blocks.losses` (WP2.8) can import the same `Strategy`
  definitions without `ah.gen` depending on `ah.eval`): `Strategy` (frozen dataclass:
  static-weight or rule-based, factor id -> weight, rebalance/lookback/rule/params/
  notes) + `load_d4_strategies()`, `lru_cache`'d by resolved path so every caller
  gets the same object; validates every weight against `ah.factors.load_manifest()
  .active_factors()`, static weights sum to 1.0 within 1e-9, rule ids are known.
  `pre-registration.yaml` (repo root, new, marked UNSEALED — Task 4 adds thresholds
  and the seal machinery) now carries the `d4_strategies` block: `eqw_factors`
  (equal-weight across the return-bearing active factors), `sixty_forty`
  (equity_mkt/ust_10y), `endowment_proxy` (equity/govt/credit/commodities/REITs with
  an explicit `proxy_mapping` for private sleeves — private equity and REITs to
  equity_mkt, private credit to hy_spread, real assets to commodities), `momentum`
  (12-1 on equity_mkt, stated warm-up), and `carry` (static long ust_10y / short
  policy_rate — a funded long-short whose exposures sum to 0.0, which is why it is
  `kind: rule` rather than `static_weights`). `eval/metrics/tails.py` (new package):
  `strategy_returns()` (weighted sum of factor slabs, or rule dispatch for
  momentum/carry), `var_es()` (historical VaR/ES as positive loss magnitudes),
  `d4_tail_table()`. Elicitability, Kupiec/Christoffersen backtests, and
  tail-dependence coefficients remain WP2.2 scope (named, not stubbed).
  `tests/test_tails_import_graph.py` walks the AST of both new modules and asserts
  no import names a portfolio/sleeve/institution module.

## [v0.1.0-g0] — 2026-07-24

Gate G0 ("lay the rails") complete. All seven G0 criteria pass — see `G0-EVIDENCE.md`.
The toy world round-trips `compile → validate → run → record → replay` bit-identically.

### Added
- **WP0.9 — CLI, governance, docs, G0 end-to-end.** `ah` CLI (typer):
  `world build --preset|--scenario [--live]`, `world validate|show`, `run
  [--seed --paths]`, `replay` (recompute+compare digest), `verify`, `battery`,
  `chronicle`; SQLite state at `data/ah.db` (`--db` to override). Four preset worlds
  (`src/ah/presets/`, via `scripts/gen_presets.py`). Governance: `model-inventory.yaml`,
  `decision-register.md` (D1-D10, OPEN), `genai-track.md`. README loop + G0 checklist.
  `tests/test_g0_end_to_end.py` executes the seven G0 criteria programmatically.
- **WP0.8 — Validation battery skeleton.** `battery/stylized.py`: excess kurtosis,
  skew, Hill tail index (5% tail), ACF of returns (lags 1-5) and |returns| (lags
  1-12), max-drawdown distribution, cross-correlation matrix + Frobenius distance.
  `battery/thresholds.yaml`: per-metric {min?,max?,status} (all `todo` in Step 0).
  `battery/report.py`: `run_battery` → markdown + JSON, exits non-zero only on
  `enforce` failures; `BATTERY_VERSION = "battery-0.1"`. CI runs
  `python -m ah.battery.report` on the stagflation preset.
- **WP0.7 — Compiler interface + offline regression harness.** `CompilerProtocol`
  with `FixtureCompiler` (offline, slug→`fixtures/compiler/{slug}.json`) and
  `AnthropicCompiler` (live, CLI `--live` only; lazy `anthropic` import; never
  imported by tests). `postprocess.extract_json` (fence-strip + outermost-`{}` +
  parse); `prompt_v1` (`compile-world-v1.0`, JSON-only + fictional-entities rule);
  `pipeline.process` (validate→clamp→construct). 50 checked-in fixtures
  (`scripts/gen_fixtures.py`): 40 valid, 5 clamp, 5 reject — harness asserts valid+
  clamp build and run 12+ months, clamp records clamps, reject is rejected.
- **WP0.6 — Stores + digest.** `core/digest.py`: canonical JSON (sorted keys,
  compact, shortest-round-trip floats) and SHA-256 over float64 path tensors rounded
  to 12 decimals (`digest_paths`, `digest_ensemble`). `store/db.py`: SQLite (WAL,
  foreign keys) with `worlds`, `run_records`, `chronicle` tables and append-only
  chronicle triggers. `store/worlds.py`: engine-field immutability (edits under an
  existing world_id are rejected; narrative/provenance edits allowed in place).
  `store/runrecords.py`: save/get + `verify_run` (recompute digest from stored
  world+seed and compare) — tamper of stored digest or world is detected.
  `store/chronicle.py`: append/read only (no mutators), trigger-enforced at the DB.
- **WP0.5 — Institution simulator + decisions.** `simulate_institution(paths,
  decisions)` runs the start mix through an engine path with annual decision points
  (month `12*year-1`, years 1-9) and actions `hold|derisk|leanin|secondary`
  (10pt growth↔defensive shifts preserving proportions; secondary sells ≤8pts PE at
  0.82 with a total haircut and a pe→bonds target move). Returns are read as percent
  with per-sleeve limited liability, so weights sum to 1 and no sleeve goes negative
  by construction. `hold_course_twin` (passive benchmark) and `decision_alpha`
  (active − twin). Golden hold-course value + hypothesis invariants.

### Changed
- **Engine (WP0.4) HY spread-shock scaling.** WP0.5 surfaced that the HY
  `3.5·Δspread` term used Δspread in bps, producing ±300%/month returns; the spread
  path is bps but that coefficient only yields sane monthly returns with Δspread in
  percentage points. Δspread is now converted bps→pp; HY is now ±6-9%/month, in line
  with its own vol term and every other asset. The WP0.4 golden digest was
  regenerated accordingly.

### Added (earlier)
- **WP0.4 — Deterministic toy engine (`toy-v0`).** Monthly, pure-function engine
  (`run_path`, `run_ensemble`) over a `NumericWorld`: policy-rate AR path, HY-spread
  rise/decay, inflation AR, binary crisis mask, common-factor asset returns, and
  quarterly appraisal-smoothed reported marks for pe/pc/re. All randomness from one
  `Generator(PCG64(seed))`, drawn up front in fixed order; ensemble seeds
  `base_seed + 7919*k`; errors clearly on non-`toy-v0` generators. Tests: frozen
  golden digest (seed 42 stagflation), determinism, hypothesis invariants
  (finite / rate>=0.1 / spread>=150 / reported flat off quarter-ends), ensemble
  seeding, and the narrative-blindness guard (now access-pattern based).
- **WP0.3 — Validator (V-rules).** `validate(world) -> ValidationResult`
  {clamped_world, clamps, warnings, blocking}, implementing V1-V12 (WORLDSPEC.md §3).
  Bounds clamps (V9) are driven from the JSON Schema itself (one home for bounds),
  recorded as {path, submitted, applied}; >3 clamps warns. V2 clamps windows/peaks
  into the horizon; V3 swaps inverted spreads; V1/V4/V5/V6/V7/V8 warn on coherence;
  V10/V11 and custom-vintage-without-sleeves (V12) block. `validate` is pure (no wall
  clock); `stamp_validation` writes `provenance.validation` and flips draft→validated
  with a caller-supplied `validated_at`. 51 tests: one per rule, edge cases, and a
  table-driven sweep; canonical example is the clean baseline.
- **WP0.2 — WorldSpec models + loader.** pydantic v2 models mirroring
  `worldspec-v1.0.schema.json` exactly (required⇔required, `extra="forbid"`⇔
  `additionalProperties:false`, bounds/patterns/lengths). `load_worldspec(path|dict)`
  validates against the JSON Schema (Draft 2020-12) first, then constructs the model.
  Property test (hypothesis, 400 examples) asserts pydantic accepts ⇔ jsonschema
  accepts on fuzzed near-valid documents; canonical example round-trips identically.
  Narrative-blindness enforced structurally via a `NumericWorld` projection that
  omits `narrative`/`provenance`, plus a source-scan guard over engine/institution.
- **WP0.1 — Scaffold, tooling, CI.** Single-package `src/ah` layout; `pyproject.toml`
  pinned to Python 3.12 with the STEP0-PLAN §1 dependency set; uv workflow; ruff
  (lint+format), pyright (basic), pytest with `--disable-socket` (pytest-socket),
  coverage on `ah.core`; pre-commit hooks; GitHub Actions `ci.yml`
  (lint → typecheck → tests) with no network access; minimal `ah` CLI entry point.

### Contracts
- `worldspec 1.0.0` — vendored under `schemas/` (read-only): `worldspec-v1.0.schema.json`,
  `example-long-stagflation.worldspec.json`, `world-bible-v1.0.schema.json`, `WORLDSPEC.md`.
