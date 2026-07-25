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
- **WP2.1b Task 2 review fixes (fix pass 1) — derived series, and a sealed file that
  stands alone.** Review returned Spec: FAIL. Three defects mattered most.
  *(1) Levels are not returns.* `sixty_forty`, `endowment_proxy` and `carry` weighted
  rate/spread **levels** (`ust_10y`, `hy_spread`, `policy_rate`) as if they were period
  returns and summed them with `equity_mkt`: the 60/40 bond leg *rose* when yields
  rose, the endowment credit leg booked spread widening as a gain, and `carry`'s pooled
  loss distribution was dominated by a positive constant, so `var_es` returned a
  negative number in violation of its own positive-loss-magnitude convention.
  `pre-registration.yaml` gains a `derived_series:` block, declared before
  `d4_strategies`, in which a level factor is converted to a monthly decimal return by
  a named transform with every parameter, the closed-form formula, the
  percent-to-decimal conversion, the lag and the warm-up all stated: `govt_tr_10y`
  (`bond_total_return` on `ust_10y`, `duration_years: 8.5`), `credit_xs_hy`
  (`spread_excess_return` on `hy_spread`, `spread_duration_years: 4.0`) and
  `cash_tr_1m` (`bond_total_return` on `policy_rate` with `duration_years: 0.0` — cash
  is a zero-duration bond, so `carry`'s funding leg needs no bespoke arithmetic and no
  third transform). One convention throughout: levels are percent, `r_t = 0.01 * (
  x_{t-1}/12 - D*(x_t - x_{t-1}) )`, and month 0 is 0.0 under the file's single
  warm-up rule (the same rule `momentum` uses). `strategies.py` gains `DerivedSeries`,
  `load_derived_series()` (memoized by resolved path, like `load_d4_strategies()`) and
  `KNOWN_TRANSFORMS`; a strategy weight key may now name an active factor **or** a
  declared derived series, and nothing else. `sixty_forty` is now
  `{equity_mkt: 0.6, govt_tr_10y: 0.4}`; `endowment_proxy`'s govt/credit legs are
  `govt_tr_10y`/`credit_xs_hy` at unchanged sleeve weights; `carry` is long
  `govt_tr_10y` funded at `cash_tr_1m`. `eqw_factors` is unchanged.
  *(2) The sealed file no longer incorporates unsealed code by reference.* `carry`'s
  units convention and `momentum`'s warm-up were defined by pointing at
  `tails.py`'s module docstring; both are now stated in full in a `conventions:` block
  inside the file, and `tails.py`'s "factor-slab convention" paragraph is deleted and
  replaced by the levels-only-through-a-derived-series rule.
  *(3) The import-graph acceptance test passed without protecting.* It appended only
  `node.module` for `ast.ImportFrom`, so `from ah.core import institution` (and the
  `as`-aliased and relative forms) were missed — and `ah/core/institution.py` really
  exists and really holds `SLEEVES`. The checker now also emits
  `f"{node.module}.{alias.name}"` per alias and handles `node.module is None`, with a
  parametrized test proving it catches all five forms from parsed strings.
  Also: rule lookbacks are declared exactly once (`Strategy.lookback` drives the rule;
  `lookback_months` inside `params` is rejected); sealed parameters have no code-side
  defaults (a missing one raises `StrategyError` naming it); unknown keys and duplicate
  YAML mapping keys are hard errors (`_UniqueKeyLoader`); rule target series are sealed
  data (`params` keys ending `_series`, validated against the active factors plus the
  declared derived series at load, not at metric time); `endowment_proxy`'s
  `proxy_mapping` is loaded and its sleeve weights must roll up to the flat `weights`
  within 1e-9; `KNOWN_RULES`/`KNOWN_TRANSFORMS` are asserted equal to `tails.py`'s
  dispatch tables (and the `# pragma: no cover` that hid the gap is gone); the analytic
  VaR/ES tolerance drops from 2e-3 to 5e-4 (~8x the MC standard error at n=2e6, not
  ~33x); `Ensemble.factor` raises a named `UnknownFactorError` identifying the factor
  and the available set; and the seal now states, once, that `commodities` has no
  registered series and therefore **two of the five D4 strategies have no computable
  reference statistics at seal time**. Tests use plausible *level* magnitudes (a 10y
  yield near 4, a HY OAS near 4.5) for the rate/spread factors — the previous
  zero-mean N(0, 0.02) fixture is precisely why the sign inversion survived review.
- **WP2.1b Task 2 review fixes (fix pass 2) — sealed conventions the loader actually
  reads.** A re-review found the file's self-description ("the code is checked against
  it by tests") was still false in two places, plus six minor gaps. *(1)
  `conventions.percent_to_decimal` had no code reading it, and `tails.py`'s
  `_MONTHS_PER_YEAR` had no sealed key at all — an amendment to either would have been
  a silent no-op. `pre-registration.yaml` gains `conventions.months_per_year`; `tails.py`
  now sets `_PCT_TO_DECIMAL`/`_MONTHS_PER_YEAR` *from* `ah.strategies.load_conventions()`
  at import time, not as independent literals. *(2)* "a level factor never appears in
  `weights`" was enforced only by a hand-maintained frozenset in
  `tests/test_strategies.py` that had already drifted from the YAML prose (9 factors
  vs. 7) and covered nothing the loader itself checked. `conventions` gains
  `return_bearing_factors` / `level_factors` — sealed, exhaustive and disjoint over
  every active factor in `factors.yaml` (checked at load time) — and
  `ah.strategies.Conventions` / `load_conventions()` load them; `_validate_weights`
  now raises `StrategyError` naming any level factor weighted directly; the
  hand-maintained frozenset is deleted. This also fixes the missing `cpi`/`equity_vol`
  classification (both are now correctly `level_factors`, matching what the deleted
  frozenset already had right). Six minor items: `conventions.rebalance_cadences`
  (`[monthly]`) is now sealed and enforced — an undeclared `rebalance` value raises;
  `conventions.static_weights_composition` states the arithmetic-weighted-sum, no-
  compounding rule the three `static_weights` strategies were relying on implicitly;
  `d4_tail_table` gains an explicit `derived` parameter and raises if `strategies` is
  passed without it, instead of silently pairing an explicitly-loaded strategy set with
  the *default* file's derived-series transforms; two `derived_series.*.notes` entries
  that pointed at test function names by name now describe the sign property directly;
  `_lagged_carry_minus_duration` casts its whole input to float64 before any arithmetic
  (previously only `out` was float64 — under NumPy's NEP 50 promotion rules a float32
  input's carry/duration terms would have stayed float32) and raises a named
  `StrategyError` for non-2-D input instead of an `IndexError` from `level.shape[1]`.
- **WP2.1b Task 3 — Block-aware reference statistics and bootstrap bands (pre-seal
  patch).** `eval/reference.py` (new): the skeleton `reference.py` computes every
  reference statistic **on train+validation only** (`ah.splits.DataAccess.train_val`
  is the only surface it touches; it imports neither `ah.eval.g2` nor
  `FinalEvaluationToken` in code — an AST-based test proves it, matching
  `tests/test_leakage_guard.py`'s style), per active `FactorManifest` block and
  separately for cross-block joint metrics, with the block pair recorded on
  `CrossBlockReference.pair`. Public surface: `StatBand` (point + block-bootstrap
  band + `n_resamples`/`level`/`tier`), `BlockReference`, `CrossBlockReference`,
  `ReferenceStats` (`blocks`, `cross_blocks`, `active_blocks`, `vintage_id`,
  `n_resamples`, `seed`, `missing_factors`, `to_dict()` for JSON — cross-block pair
  keys render `"global|us"`), `compute_reference()`. `SINGLE_FACTOR_STATS` registers
  `mean`/`std`/`skew`/`excess_kurtosis`/`acf_1`/`acf_abs_1` (plain numpy, closed-form
  definitions documented in each docstring — `acf_1` uses the overall-mean,
  n-denominator Box-Jenkins estimator, not `numpy.corrcoef`), each paired with its
  DN-1.1 Sec.II.6 horizon tier (all `monthly` for this task — `1_5yr`/`10yr`/
  `economic`/`severe` are WP2.2 scope, named not stubbed, alongside the eight full
  metric suites `monthly.py`...`calibration.py`). `CROSS_BLOCK_STATS` registers
  `correlation` and `crisis_corr_lift` (correlation on a block-A factor's worst decile
  minus the unconditional correlation, precisely defined in its docstring).
  `block_bootstrap_band()`: a moving-block bootstrap over the time axis of an aligned
  ``(T, k)`` panel — row-blocks are drawn jointly across every column (never
  per-factor resampling), so calling it with the same `seed` and the same whole-block
  panel for every statistic in a block gives every one of that block's stats the same
  resampled time positions, the "joint" property the patch requires. All randomness
  from `numpy.random.Generator(PCG64(seed))`, constructed fresh per call — same seed,
  bit-identical band. `compute_reference()` reads each active factor via
  `access.train_val(series_id_for(factor))` (`series_id_for` defaults to identity —
  the factor-id -> catalog-series-id mapping doesn't exist yet; that's WP2.2/Step-2R
  scope) and inner-joins them on date before computing anything; a factor with no data
  (`commodities` — no Step-1 series sources it yet, per `factors.yaml`'s header note)
  is recorded in `missing_factors` rather than raising or producing `NaN`. Every
  active block gets a `BlockReference` entry even if all its factors are missing, so
  callers can always find a block by key.
  `tests/test_reference.py` (12 tests): the leakage proof reads dates from a
  `DataAccess` subclass that records every date/series id actually reaching
  `compute_reference` through `train_val` (not from the return value, and not by
  trusting `train_val`'s own exclusion — this closes the leak channel a caller could
  open by reading the raw `Reader` directly); the inactive-block proof does the same
  for `uk` (declared in the real `factors.yaml`, inactive) using a reader that *has*
  uk data available, so a bug iterating `manifest.blocks` instead of
  `manifest.active_blocks` would be caught rather than masked by a missing-data path.
  Also: same-seed/different-seed band (non-)identity; `blocks`/`cross_blocks` shape
  matches `manifest.active_blocks`/`cross_block_pairs()`; `mean`/`std` against
  closed-form values; `acf_1` recovers a known AR(1) phi; `excess_kurtosis` near zero
  for a normal sample and clearly positive for a Student-t sample; every band brackets
  its point estimate; `to_dict()` round-trips through `json.dumps`.
- **WP2.1b Task 3 review fixes (fix pass 1).** Addresses one Critical and four
  Important/Minor findings against `eval/reference.py`. *Critical:* the leakage-guard
  test's `_RecordingAccess` recorded dates from `DataAccess.train_val()`, which is
  already holdout-clean by construction and proven so independently
  (`test_leakage_guard.py::test_train_val_excludes_holdout`) — the offenders assertion
  could never fire, so it detected no new leak channel; a direct/parallel holdout read
  (`access.frame(sid, "holdout", token=...)`) bypassed it entirely and also escaped the
  AST guard, whose `ast.Name`/`ast.ImportFrom` checks don't cover qualified access like
  `ah.splits.FinalEvaluationToken`. Fixed by re-pointing `_RecordingAccess` at
  `frame()` (the method `train_val()` calls internally) and broadening the AST guard to
  flag `ast.Attribute` nodes too; both fixes are proven with mutation tests that apply
  the exact leak quoted in the review and show the (pre-fix) guard missing it and the
  (post-fix) guard catching it. *Important — alignment was global, not scoped:*
  `compute_reference` inner-joined every active factor onto one shared date axis before
  computing anything, so one short-history factor silently truncated every other
  factor's own reference window (real Step-1 series make this likely: spread/vol
  indices start decades after the equity series in the same `global` block), and a
  zero-overlap cross-block pair raised an unhandled `ValueError` from inside
  `block_bootstrap_band`. Alignment is now scoped to what each statistic needs: a
  single-factor stat reads only that factor's own train+validation observations (no
  join with any other factor, same block or not); a cross-block stat aligns only its
  own factor pair. A pair with zero overlap is recorded in the new
  `CrossBlockReference.zero_overlap_pairs` (surfaced in `to_dict()`) instead of
  raising. *Important — error messages didn't name the offender:* `_read_train_val`
  now validates the `date`/`value` columns itself and raises a new
  `ReferenceComputationError` naming the factor and series id for a malformed frame
  (previously an anonymous `KeyError` could propagate from deep in the alignment code);
  `block_bootstrap_band` gained a `context` parameter threaded from every call site
  (`block=... factor=...`/`pair=... factors=...`) so any of its `ValueError`s name what
  failed. *Important — `skew`/`acf_abs_1` had no ground-truth test:* added hand-computed
  exact-arithmetic tests for both (a 4-point sample for `skew`, a 6-point sample for
  `acf_abs_1` whose lag-1 autocorrelation of `|x - mean(x)|` works out to exactly
  `1/4`). *Minor:* the moving-block resample draw is now an explicit, reusable step
  (`_draw_moving_block_indices`, drawn once per factor/pair and passed into every stat
  sharing that panel via `block_bootstrap_band`'s new `resample_indices` parameter)
  instead of an emergent side effect of separate calls sharing `(seed, T, block_length,
  n_resamples)`; `CROSS_BLOCK_STATS` now carries `tier` on a `RegisteredCrossStat`
  record, symmetric with `SINGLE_FACTOR_STATS`'s `RegisteredStat`, instead of
  hardcoding `tier="monthly"` at the call site; `block_bootstrap_band` validates
  `block_length >= 1` instead of silently clamping a non-positive value to 1; the
  same-seed determinism test now compares the whole `ReferenceStats` object instead of
  just `.blocks`/`.cross_blocks` separately; `test_band_brackets_point_estimate_for_
  every_stat`'s expected count is now derived from the fixture's manifest shape instead
  of two hardcoded, coincidentally-equal `4`s. `tests/test_reference.py` grew from 12
  to 28 tests; no existing test was weakened or deleted. Full suite, ruff, and pyright
  clean.
- **WP2.1b Task 4 — Pre-registration seal machinery: block-nested thresholds,
  seal/verify, `block_addition` (pre-seal patch).** `eval/prereg.py` (new): builds the
  WP2.3 seal machinery with the block structure already in it — **nothing here seals
  for real**; `pre-registration.yaml`'s `sealed` flag stays `false`, and the
  acceptance bar is a dry-run `seal()` + `verify()` passing end to end (Instructions/
  WP2.1b-PRE-SEAL-PATCH.md Definition of done item 4). Public surface: `Threshold`
  (`min`/`max`/`severity`), `Decision`, `PreRegistration` (`sealed`, `active_blocks`,
  `block_thresholds`, `cross_block_thresholds`, `decisions`, `raw`), `Amendment`
  (`amendment_id`/`type`/`date`/`rationale`/`post_hoc`/`payload`), `PreRegError`,
  `load()`, `verify()`, `seal()`, `load_amendments()`, `append_amendment()`,
  `apply_block_addition()`. `verify()` checks: every active block has a
  `thresholds.blocks` entry and no entry names an inactive block; every active
  cross-block pair (`FactorManifest.cross_block_pairs()`) has a
  `thresholds.cross_blocks` entry and no entry names an inactive block;
  `prereg.active_blocks == manifest.active_blocks`; every threshold's `severity` is
  `enforce`/`report` and `min <= max`; and, closing a hole found in review, that the
  `conventions:` block is present and declares every key `ah.strategies.
  load_conventions()` reads (`percent_to_decimal`, `months_per_year`,
  `return_bearing_factors`, `level_factors`, `rebalance_cadences`,
  `static_weights_composition`), with `return_bearing_factors`/`level_factors`
  together classifying every active factor and none in both — `ah.strategies`
  deliberately treats a *missing* `conventions:` block as "none declared" (a
  concession for minimal test fixtures), which would otherwise let a misspelled
  `conventons:` key silently disable enforcement in the very file the seal hashes;
  `verify()` re-checks this unconditionally, reading `PreRegistration.raw` directly
  rather than re-reading the file through `ah.strategies` (which needs a path this
  module isn't guaranteed to have post-amendment). `seal()` hashes, canonically
  (reusing `ah.core.digest.canonical_json` + `hashlib.sha256` — no second hashing
  scheme), the pre-registration YAML, the `factors.yaml` it references, and the
  source text of every file in `judged_sources` (default: the WP2.2 metric-suite
  modules that exist yet, plus `eval/g2.py`, resolved lazily so files WP2.2 hasn't
  added don't block this task); writes a JSON lock (`digest`, `hashed_files`,
  `sealed_at`) unless `dry_run`. `sealed_at` is a required keyword argument — never
  `date.today()` (no-clock-reads invariant) — and plays no part in the digest itself
  (sealing the same inputs at two different `sealed_at` values gives the same
  digest). `governance/amendment-log.yaml` (new): append-only log, starting empty;
  header documents the four amendment types and states `block_addition`'s additive
  property verbatim (WP2.1b-PRE-SEAL-PATCH.md's required wording) — it adds new
  per-block and new cross-block thresholds for the newly-active block without
  invalidating any existing block's thresholds, so it is not a re-seal.
  `append_amendment()` opens the log in file-append mode, so every byte already on
  disk is provably untouched (not merely unchanged in content) by a later append.
  `apply_block_addition()` merges a `block_addition` amendment's new per-block and
  new cross-block thresholds into a `PreRegistration`, carrying every pre-existing
  block's/pair's thresholds over by reference (same `Threshold` objects) so they are
  byte-identical (via canonical-JSON serialization) before and after — the patch's
  acceptance criterion. `pre-registration.yaml` extended (not replaced): `schema_
  version`, `sealed: false`, a provisional `campaign_vintage_id`, `factor_manifest:
  factors.yaml`, `active_blocks: [global, us]`, a block-nested `thresholds:` section
  (one enforce- and one report-severity entry per active block, one cross-block entry
  — every value explicitly commented as a provisional placeholder pending WP2.2's
  reference statistics), and a `decisions:` block carrying R5 (FX) and J3 (UK block)
  from Item 3, both `CLOSED-deferred`, with their consequence strings verbatim (Task
  5 records the same strings in `governance/decision-register.md`). `battery/
  report.py`: `run_battery()` gained a `manifest: FactorManifest | None = None`
  parameter (same injection pattern as Task 3's `series_id_for`), defaulting to
  `load_manifest()`, so a synthetic block configuration can be run through the
  battery without a real campaign's `factors.yaml` (Item 2 acceptance: "a synthetic
  two-block configuration passes the battery"). `tests/test_prereg.py` (new, 35
  tests): the 13 tests named in the Task 4 brief plus dedicated coverage of the
  `conventions` closure (missing block, missing key, double-classified factor,
  unclassified active factor, and the block-addition-safe case of a conventions
  block pre-classifying a not-yet-active block's factors) and threshold sanity
  (invalid severity, `min > max`). `tests/test_battery.py` gained the synthetic-
  manifest acceptance test. Full suite (516 tests), ruff, and pyright clean.
- **WP2.1b Task 4 review fixes (fix pass 1).** Addresses one Critical, four
  Important and five Minor findings, plus a project-owner scope ruling on what the
  seal covers. **Scope ruling (Decision 0):** `CLAUDE.md`'s invariant ("thresholds
  *and the code that judges them*") governs over STEP2-GENERATOR-PLAN §WP2.3's
  narrower wording, so `_default_judged_sources()` now covers every module that can
  move a pass/fail verdict — the enforce-tier metric suites that exist, plus
  `eval/g2.py`, `eval/reference.py`, `eval/prereg.py` itself (non-circular: the
  digest lands in the lock, never back in the module), `strategies.py`, `factors.py`,
  `battery/report.py` and `battery/stylized.py`. Those seven are *required* to exist:
  a missing one raises rather than silently shrinking the seal. Documented at the top
  of `prereg.py` and in `pre-registration.yaml`, including the consequence that after
  WP2.3 seals, an edit to any of them is a dated amendment. **Critical:** the seal
  digest keyed on absolute filesystem paths, so a committed lock verified only on the
  machine that produced it — it would have failed in CI, in a reviewer's clone, and
  under WSL2. The digest is now keyed on relative, forward-slashed paths resolved
  against two roots (the repository root for judged code; the pre-registration's own
  directory at seal time / the lock's at verify time for the sealed documents), the
  lock stores them in that form, and a path under neither root is rejected at seal
  time. **Important:** `verify()` now validates threshold *keys*, not just their
  values — a per-block key must be `"<factor>.<stat>"` with the factor in that block
  and the stat registered in `reference.SINGLE_FACTOR_STATS`, a cross-block key
  `"<factorA>~<factorB>.<stat>"` with the factors drawn in the pair key's sorted order
  and the stat in `CROSS_BLOCK_STATS`, so a sealed `enforce` threshold can no longer
  name a statistic nothing computes. `append_amendment()` validates at *write* time
  (unknown type, empty `amendment_id`/`date`/`rationale`, non-boolean `post_hoc`,
  duplicate id) and writes nothing on failure — on an append-only artifact a bad entry
  is permanent, and a duplicate id previously produced a log `load_amendments()`
  refused forever. The lock now records `prereg_path` and `verify()` requires it to
  name the pre-registration being verified (`PreRegistration` gained `source_path`),
  so a lock sealed for a different document is rejected even when contents match.
  **Minor:** `verify()`'s conventions check adopts `ah.strategies`' full rule
  (classification must cover *exactly* the active factor set, nothing outside it), so
  it can no longer green-light a file `load_conventions()` raises on — a real
  `block_addition` therefore requires a hand edit to `conventions:` alongside the
  amendment's thresholds, now stated in the amendment log's header and exercised by
  the round-trip fixture; `verify()` requires `schema_version == "1.0"` and a present
  `decisions` block (a misspelled `decisons:` previously dropped R5/J3 silently);
  `read_text` failures in `seal()`/`verify()` are wrapped in `PreRegError` naming the
  file; two weak test matchers tightened (`FrozenInstanceError`, the full
  missing-pair message) and the report-all-failures test now draws its two faults from
  different `verify()` sections. Full suite 541 tests, ruff + pyright clean.

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
