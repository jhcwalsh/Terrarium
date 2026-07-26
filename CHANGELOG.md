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

### Fixed
- **WP2.2 Task 3 review fix pass 1 — two sealable bands that could not do their job.**
  - *The two decade-frequency statistics had a Bernoulli band, i.e. no band at all.*
    `lost_decade_frequency` and `long_inflation_era_frequency` were a single 0.0/1.0
    indicator over the whole input, so every bootstrap replicate returned 0 or 1 and the
    percentile band could only be `[0, 1]` (admits every possible value) or
    `[0,0]`/`[1,1]` (fails every generator with a non-zero rate) — and the historical
    frequency, the *mean* of that resample distribution, was never formed anywhere
    (`block_bootstrap_band` takes percentiles, not a mean). Both are now genuine
    frequencies: the fraction of the input's own **overlapping 120-month windows**
    satisfying the property. Stated consequence: a 120-month replicate holds exactly one
    window, so both are registered `length_matched=False` (`RegisteredStat`) and their
    replicates are drawn at the **full train+validation length**, recorded as
    `resample_length: null` on the band — the correct reading of
    `conventions.estimator_length_matching` (which exists because the ACF estimator is
    length-biased) rather than an exception to it. The band is consequently wide,
    reflecting history's ~9-14 independent decades, which is DN-1.1 §II.6's "honestly
    reported (n≈14)" for this tier. Non-degeneracy (`0 < lo < hi < 1`) is now asserted on
    a century-long `compute_reference` run.
  - *`ergodicity_gap` was algebraically `|variance_ratio_120m − 1|`.* At production path
    length the pooled variance ratio at k=months yields one sum per path, making the old
    gap the same number under a second sealed name — the duplication this file already
    refused when it dropped `agg_gaussianity` horizon 1 for being `excess_kurtosis`. Its
    `Var(pooled)/months` null was also iid-within-path, under which a *correct* generator
    of a persistent factor (φ=0.9 AR(1) → ≈18) read as catastrophically non-ergodic.
    Redefined as DN-1.1's actual metric — long-path time average vs ensemble
    cross-sectional average, in units of pooled dispersion, with no iid null in it — and
    marked `structurally_unavailable` because `run_battery` is handed no long path
    (RFR-20). The estimator is built and tested against ergodic, persistent-ergodic and
    genuinely non-ergodic processes, ready to wire.
  - *Drawdown metrics could be gamed by generating less, twice over.* Added
    `DRAWDOWN_MIN_EPISODES = 10` (shared by the reference and ensemble sides), and an
    overflowed path — `wealth/cummax = inf/inf = nan`, and `nan < 0.0` is `False`, so it
    was silently recorded as having **no drawdowns**, the favourable answer, then dropped
    from the pooled concatenation — now NaNs the metric. Same fix for
    `lost_decade_frequency`'s overflowing product.
  - *Guards and markers.* The 10yr MC-error guard is now exercised **through**
    `run_battery` (no code path could trigger it before); `MetricSpec` gains `status`
    (`structurally_unavailable`) and `metadata`, both surfaced in `to_dict()` and the
    markdown, so a platform gap is distinguishable from a generator failure and
    `REGIME_RULESET_VERSION` finally reaches the report; `StatBand` gains
    `n_valid_resamples`, making RFR-19's NaN-band degeneracy visible in the artifact.
  - *Governance.* Ten new `conventions.<stat>_estimator` blocks in
    `pre-registration.yaml` (plus `elementary_moment_estimators`,
    `crisis_corr_lift_estimator` and `mc_error_is_not_the_small_n_band`), with
    `prereg.ESTIMATOR_CONVENTION_KEYS` + a two-way machine check so no statistic can be
    registered without a sealed definition; the two ensemble pooling conventions moved to
    `ah/eval/metrics/_pooling.py` (and added to the sealed judged-source set); RFR-20
    (ergodicity), RFR-21 (the nominal-not-real lost-decade row `reference.py` claimed
    existed but did not), RFR-22 (§WP1.9 considered and inapplicable to RFR-17/18).
- **WP2.2 Task 1 review fix pass — the mapping is now actually read, the policy rate is
  a policy rate, and there is one numeraire.**
  - *The mapping was not wired in.* `compute_reference` took a `series_id_for` callable
    defaulting to identity and nothing ever passed it the manifest, so every factor id
    went to the catalog verbatim, every factor landed in `missing_factors`, and the
    reference came back **empty with no error** — while `build_panel`, which did read
    the mapping, had zero production callers. The two surfaces were also structurally
    incompatible (`FactorManifest.series_id_for` *raises* for `kind: derived`). Fixed by
    extracting `ah.eval.panel.read_factor_frames` as the single factor-id → series
    resolution surface; `build_panel` assembles on top of it and `compute_reference`
    computes statistics on top of it, so the panel a generator is fitted against and the
    bands WP2.3 seals can never resolve a factor differently.
  - *`policy_rate` → `fred.TB3MS` (a 3-month bill) replaced by `fred.FEDFUNDS`*, the
    administered rate, registered in `requirements.yaml` under the §WP1.9
    emergent-requirements rule with a `fedfunds_pre1954` splice rule backfilling
    pre-1954-07 history from `fred.TB3MS` (`is_proxy`) and an offline connector fixture.
    The bill was wrong twice over: it is a market yield that decouples from the funds
    rate in exactly the crisis months the tail/severe tiers judge, and it is also the
    short leg of `funding_spread`'s TED — so the two factors would have shared a
    construction-driven stress component and the cross-block correlation and
    crisis-correlation-lift bands would have been sealed over an artifact of the mapping.
  - *One numeraire.* `equity_mkt` mapped to Fama-French `Mkt-RF` (an **excess** return)
    while `govt_tr_10y` is a **total** return, and `sixty_forty`/`endowment_proxy`
    weighted them together. `equity_mkt` is now `kind: derived`,
    `add(french.mkt_rf, french.rf)` — a genuine total return. `conventions.numeraire:
    total_return` is sealed data, and `ah.strategies` now rejects a D4 strategy whose
    legs do not all resolve to it (or to an explicitly declared, self-financing
    `zero_cost` overlay: `smb`/`hml`/`mom`/`credit_xs_hy`). `FactorSource` gains
    `numeraire`, and `proxy`/`proxy_for` so a splice-backed backfill is machine-visible
    rather than free text in `notes`.
  - *One NaN rule.* `ah/battery/report.py::evaluate` treated a NaN metric as PASS while
    `ah/eval/battery.py::_passed` treated it as FAIL — two rules, both inside the seal.
    Now **NaN = FAIL** in both, stated in both modules and in
    `conventions.nan_metric_rule`. This is a deliberate behaviour change to Step 0's
    battery: an uncomputable metric has not demonstrated compliance.
  - *`mc_error` sub-ensembles no longer lie about their size* (`dataclasses.replace(
    meta, n_paths=len(idx))`); `Panel`/`ReferenceStats` split `missing_declared` from
    `missing_no_data`; `ReferenceStats.coverage` records each factor's train+validation
    span and observation count; `BatteryReport` gains missing-factor accounting,
    per-factor coverage, `enforce_failures` and an aggregate `.passed`; `run_battery`
    calls `prereg.verify()` whenever the pre-registration is sealed (TODO(WP2.3): drop
    the guard); derived factors' declared `units` are checked against their inputs'
    registered units; `seal()`'s `out_path` is optional for a dry run.
- **`.gitignore`: `data/` → `/data/`.** The unanchored pattern matched any directory
  named `data` at any depth, so the **entire `src/ah/data/` package** (all of Step 1's
  data layer), every synthetic connector fixture under `tests/fixtures/data/`, and
  `docs/data/` were untracked — a fresh clone could not run the test suite. 54 files
  added. `ruff` respects `.gitignore` by default, so those sources had never been
  linted; 13 pre-existing lint findings surfaced and are fixed here. See
  `governance/retrofit-register.md` RFR-11.
- **WP2.2 Task 1 review fix pass 2 — the numeraire defect survives at portfolio level;
  three documentation gaps closed; one defence-in-depth hole closed.** All
  documentation-only except the last item.
  - *The `zero_cost` leg taxonomy is sound at leg level but the sealed claim is
    portfolio-level.* Under `conventions.numeraire: total_return` with no cash leg, a
    strategy carrying uncommitted zero-cost notional, or flat under its own rule,
    realizes **zero** on that capital rather than the cash rate — three of five D4
    strategies are affected (`eqw_factors` at 0.6, `endowment_proxy` at 0.15, and
    `momentum` in its warm-up and every flat month, broken by this task's own numeraire
    switch and not previously recorded). `_validate_numeraires` cannot see this: it
    checks declared leg numeraires, not implied cash positions. Recorded as
    `governance/retrofit-register.md` RFR-12 (widens RFR-9) and a new paragraph in
    `pre-registration.yaml`'s `conventions.numeraire_statement`; WP2.3 must choose
    between an explicit `cash_tr_1m` residual leg or sealing the bias as-is. No code
    change — the fix is documenting the gap accurately before WP2.3 decides.
  - *`factors.yaml`'s `hy_spread`/`policy_rate` `proxy_for` entries overstated what
    `read_factor_frames` actually reads.* They read `fred.HY_OAS`/`fred.FEDFUNDS`
    directly, unextended; neither splice rule is applied by `ah.data.refresh` today
    (RFR-10, already known, but the manifest text implied otherwise). Reworded both
    `proxy_for` entries and their `notes` to say REGISTERED BUT NOT YET APPLIED, name
    WP2.3 as the owner, and cross-reference RFR-10; the same overstatement in
    `pre-registration.yaml`'s `units_of_level_factors` is corrected too.
  - *The RFR-1 circularity was only half-broken.* `factors.yaml`'s header already
    pointed at RFR-8, but `factor_sources.commodities.reason` and
    `pre-registration.yaml`'s `units_of_return_bearing_factors` still cited RFR-1
    directly. Both now point at RFR-8.
  - *`ah.eval.panel._compute_derived` validated input frames' columns but not its own
    output.* `_read_series` checks every input for `date`/`value`; the derived expr's
    return value went straight to `set_index("date")["value"]` with no check at all.
    Safe today only because every registered `_DERIVED_EXPRS` entry happens to return
    `ah.data.derive._frame()`'s exact two columns — a future transform need not. Now
    checked the same way, raising `PanelError` instead of a bare `KeyError` several
    frames inside pandas. New test
    `test_derived_expr_output_missing_columns_raises_panel_error` (monkeypatches a
    broken entry into `_DERIVED_EXPRS`; confirmed red — `KeyError: 'value'` — before
    the fix).
  - *`src/ah/data/cli.py` had two pre-existing lint violations, newly visible after the
    `.gitignore` fix.* Line 8's `from __future__ import annotations` violated
    `CLAUDE.md`'s documented rule for that exact file (Typer resolves parameter hints
    at runtime). Verified `ah data --help`, `ah data refresh --help` and `ah data
    status` all behave identically with and without it, then removed it — the file was
    simply never checked against the rule until the gitignore fix made it visible to
    `ruff`/review. Line 100's em dash in a CLI-echoed string (cp1252-safe today, but
    against the ASCII rule) replaced with `--`.

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
- **WP2.1b Task 5 — Governance: decision register, retrofit register, plan
  reconciliation (pre-seal patch, documentation only).** Records the decisions taken
  across WP2.1b Tasks 1-4 and reconciles two plan documents that now disagree with them.
  No production code changed. `governance/decision-register.md` gains a
  `## Step 2 decisions` section (D1-D10 in the existing platform table untouched): `S2-D4`
  (the D4 benchmark-strategy set, redefined over generated factors and their declared
  derived series — `govt_tr_10y`, `credit_xs_hy`, `cash_tr_1m`), `R5` and `J3` (FX and UK
  factor blocks, both CLOSED-deferred with their `pre-registration.yaml` consequence
  strings copied verbatim — a test (`test_decision_consequence_text_is_verbatim`) pins
  those strings, so the register and the YAML can never silently drift), and `S2-SEAL`
  (the seal-scope decision: CLAUDE.md's invariant — thresholds *and the code that judges
  them* — governs over STEP2-GENERATOR-PLAN §WP2.3's narrower wording, so the seal covers
  every module that can move a pass/fail verdict; consequence: post-seal, an edit to any
  judging module, including a no-op refactor, is an amendment). A footnote names the `D4`
  id collision with the platform table's D4 (correlation regime model) so a later reader
  isn't confused by two decisions sharing a number. `governance/retrofit-register.md` is
  new: a dated, append-only table for scope items surfaced but deferred during this work
  — seeded with `commodities`' missing Step-1 data source (declared in `factors.yaml`,
  weighted in two D4 strategies, reference statistics pending a connector under the
  requirements.yaml §WP1.9 rule; deferred to WP2.2) and the R5/J3 block-addition re-entry
  paths. Two plan reconciliations, each a dated note pointing at WP2.1b, minimal edits
  only: `Instructions/STEP2R-CONSOLIDATION-PLAN.md` §WP2R.4 no longer claims to resolve
  R5 (closed earlier, in WP2.1b) and its "one judgment call" note now records the answer;
  `Instructions/STEP2-GENERATOR-PLAN.md` §WP2.3's seal-scope sentence now matches
  `S2-SEAL` instead of disagreeing with it. Also commits six previously-untracked vendored
  design notes from `Instructions/` (separate preceding commit, project-owner approved):
  `DN1.1-multiyear-generator-design-note.md`/`.pdf` (discharges STEP2's halt condition),
  `DN2-hybrid-deployment-note.md`, `DN3-web-experience-architecture.md`,
  `DN4-jurisdiction-and-institution-plugin.md` (defines the `InstitutionProfile` interface
  the J3 consequence cites), `WP1.12-UK-CONNECTORS.md`. Decision register's acceptance
  check: no row in either the platform table or the new Step 2 section names WP2.3 or the
  pre-registration seal in its "Blocks" column. Full suite unchanged at 541 tests, ruff
  clean — this is a docs-only change and verified not to move either.
- **WP2.1b final branch review fixes (pre-seal patch, last commit before merge).**
  Closes the handful of gaps the whole-branch review found that would otherwise become
  post-hoc amendments once WP2.3 seals. `ah.eval.prereg._REQUIRED_JUDGED_SOURCES` now
  includes `src/ah/splits.py`: it hardcodes the train/validation/holdout boundaries, so
  moving `VALIDATION.end` changes every reference band with no lock violation unless the
  module defining "the reference data" is itself hashed — under Decision 0 (`governance
  /decision-register.md` row `S2-SEAL`, "the seal covers every module that can influence
  a pass/fail verdict") that was a miss. `ah.eval.prereg`'s "What the seal covers"
  docstring and `pre-registration.yaml`'s header comment both gain that category, plus a
  new "Considered and excluded" note explaining why `ah/gen/base.py`'s `Ensemble.factor()`
  (the generator layer's container, not the judge) and `src/ah/battery/thresholds.yaml`
  (Step-0 legacy `status: todo` data, WP2.3 must decide its fate) stay out of the hash on
  purpose. `_check_conventions` is brought into line with `ah.strategies._require_string_set`:
  it now rejects an empty, non-string-entry, or duplicate-entry
  `return_bearing_factors`/`level_factors` list the same way the loader would, closing an
  overclaim in `verify()`'s own docstring ("never green-lights a file `load_conventions`
  would raise on" — previously false in three ways). TDD, red first for each of the three
  rejection modes (`tests/test_prereg.py`); the two `block_addition` fixtures that
  previously used `level_factors: []` are reworked to carry a genuinely non-empty, valid
  classification (a second synthetic factor, `a1_lvl`) rather than relaxing the new check.
  `governance/retrofit-register.md` gains three rows (`RFR-4`..`RFR-6`, append-only): no
  producer yet exists for `EnsembleMeta.active_blocks` (lands on WP2.2/WP2.4); `verify()`
  doesn't yet cross-check threshold keys against `reference.py`'s `missing_factors`, so an
  `enforce` threshold on a factor with no data (e.g. `commodities.skew`) would seal cleanly
  (lands on WP2.3); `pre-registration.yaml` has no `splits:` section yet even though
  `splits.py`'s docstring promises one (lands on WP2.3, and now matters more since
  `splits.py` is hashed). `CLAUDE.md`'s halt-condition sentence is corrected: `DN-1.1` is
  vendored at `Instructions/DN1.1-multiyear-generator-design-note.md` and already cited as
  normative by `reference.py`, so that half of WP2.5+'s halt condition is discharged;
  `tier1-synthesis-and-decisions.md` remains genuinely missing from `docs/` and is not
  itself a halt condition. No production behaviour changes outside `_check_conventions`'s
  stricter validation and the widened judged-source set; `pre-registration.yaml` stays
  `sealed: false`. Full suite green (three new tests, two fixtures strengthened, none
  weakened), ruff/pyright clean.
- **WP2.2 Task 1 — Factor-source mapping, the reference panel reader, the battery
  orchestrator.** Closes the one genuinely blocking gap WP2.1b left open: no mapping
  anywhere in the repository bound a factor id (`equity_mkt`, `ust_10y`, ...) to a
  Step-1 catalog series, so reference statistics could not honestly be computed and
  `ah.eval.reference`'s `series_id_for` parameter had nothing real to supply. `factors.
  yaml` gains a `factor_sources:` section, one entry per factor in every block
  (including inactive `uk`): `kind: series` (one `requirements.yaml` series id,
  direct), `kind: derived` (one `ah.data.derive` helper over one or more series ids —
  `ig_spread` = `difference(fred.BAA, fred.AAA)`, `funding_spread` =
  `funding_stress(fred.TEDRATE)`, no SOFR-basis extension since no such series is
  registered), or `kind: unavailable` with a required `reason` (`commodities`, per
  `governance/retrofit-register.md` RFR-1; every `uk` factor, per decision J3 and
  `Instructions/WP1.12-UK-CONNECTORS.md`'s not-yet-landed connectors — never a
  fabricated proxy for either). `policy_rate` maps to `fred.TB3MS` (the 3-month T-bill;
  no FEDFUNDS/effective-funds-rate series is registered, and TB3MS is a real,
  registered series, not an invented one). `ah.factors.FactorManifest` gains
  `sources`, `series_id_for()`, and `is_available()`; `load_manifest()` now validates
  that every declared factor (every block) has exactly one entry and every entry names
  a real factor. `pre-registration.yaml`'s `conventions` prose is corrected now that
  the mapping is a fact rather than an assumption — `equity_mkt` is confirmed Mkt-RF,
  an *excess* return, not a total return, and every level factor's series is named
  explicitly instead of listed as "candidate". A new test
  (`test_factor_sources_units_agree_with_prereg_return_level_classification`) asserts
  `factor_sources`' units and `pre-registration.yaml`'s `return_bearing_factors`/
  `level_factors` classification can never disagree — a return-bearing factor's units
  must be exactly `ret`, a level factor's must never be — because these two files are
  sealed together and a divergence between them is exactly the defect class this
  project keeps finding; a second test cross-checks every `kind: series` entry's units
  against `requirements.yaml` itself.
  `src/ah/eval/panel.py` (new): `build_panel(access, manifest, *, split_reader=...)`
  turns a `FactorManifest` into one date-indexed `Panel` (`.frame`, `.missing`) over
  every available active factor, reusing `ah.data.derive`'s existing helpers (never
  reimplementing a transform) and `ah.data.derive.assemble_panel` for the join. Never
  reads the holdout — `split_reader` defaults to `DataAccess.train_val`, and the same
  recording-reader leakage test `tests/test_reference.py` uses (record at `frame()`,
  not `train_val()`) proves no holdout-era date reaches it.
  `src/ah/eval/battery.py` (new): the Step-2 battery orchestrator Tasks 2-6 register
  metric suites into. `MetricSpec`/`MetricResult` (frozen); `SUITES`, a module-level
  registry populated only via `register_suite()` — adding a suite never requires
  editing `run_battery()` (proved by a test that registers a throwaway suite and shows
  it in the next report). `mc_error(fn, ensemble, *, seed, n_subsamples)`: every
  ensemble-level metric's Monte-Carlo error bar, via disjoint path-subsampling from a
  fresh `PCG64(seed)` — the batch-means estimator recovers the standard error of a
  sample-mean metric to the right order of magnitude (tested against a known-variance
  synthetic ensemble) and is bit-identical for a fixed seed. `run_battery(ensemble, *,
  reference, prereg, manifest, seed, filtered=None)` looks up each metric's train+
  validation band (`ReferenceStats`) and sealed/provisional threshold
  (`PreRegistration`) by name, decides `severity`/`passed`, and emits a `BatteryReport`
  in both JSON and markdown carrying battery version, a dry-run prereg digest
  (`prereg.seal(dry_run=True)`), system/vintage ids, `active_blocks`, and per-tier
  (`monthly`/`1_5yr`/`10yr`/`economic`/`severe`, DN-1.1 §II.6) tables; a `filtered`
  ensemble's results are reported alongside the unfiltered ones, never replacing them
  (the acceptance filter may not teach to the exam). Runs end to end on the Step-0 toy
  engine's output with a throwaway test suite — the plan's own WP2.2 acceptance
  criterion; the real eight metric suites are Tasks 2-6's scope.
  Seal bookkeeping: `eval/battery.py` and `eval/panel.py` are judging code created
  outside `eval/metrics/`, so both join `ah.eval.prereg._REQUIRED_JUDGED_SOURCES` (and
  its docstring, and `pre-registration.yaml`'s mirrored header prose) in this same
  commit, with `tests/test_prereg.py`'s pinned judged-source set updated to match.
  Existing direct `FactorManifest(...)` constructions and hand-written `factors.yaml`
  fixtures across `tests/test_reference.py`, `tests/test_prereg.py` and
  `tests/test_battery.py` gained a `factor_sources`/`sources=` entry each (now
  required); no assertion in any of them was weakened. Full suite green (599 tests, up
  from 544 at branch start), ruff/pyright clean, coverage gate unaffected;
  `pre-registration.yaml` stays `sealed: false`.
- **WP2.2 Task 2 review fix pass 2 — closing the last findings before WP2.3 seals.**
  Everything here lands in files WP2.3 hashes, so it is cheap now and a dated
  post-hoc amendment afterwards.
  *Important 1, the panel metric could be gamed by omission.*
  `_paired_corr_matrices` intersected the reference's covered factor axis with
  `ensemble.factor_names`, so a generator that simply omitted a covered factor got a
  *smaller* matrix and a *smaller* (easier-to-pass) `cross_block_corr_matrix_distance`
  — generating less made an absolute-bound threshold easier to pass, exactly the
  instability the docstring already refused to tolerate for a degenerate factor
  (correctly NaN'd). An omitted covered factor now NaNs the metric identically to a
  degenerate one, never shrinks it. Tested: an ensemble that omits a covered factor
  from otherwise-identical draws must NaN, not merely differ.
  *Important 2, `resample_length` was dropped from the report.* `StatBand.
  resample_length` is load-bearing per `conventions.estimator_length_matching` (a
  length-matched band's `point` is not expected to lie inside `[lo, hi]`), but
  `_result_dict` and the markdown table emitted `point/lo/hi/n_resamples/level/tier`
  only — the battery JSON, the G2 evidence artifact, could not distinguish a
  length-matched band from an unmatched one. Now emitted in both, with an unmatched
  band rendering as `full` rather than an empty cell.
  *Minor 3, a threshold key with no producing metric was still uncaught.* `verify()`
  validates a threshold's `<stat>` against the *reference* registries, not against
  what any metric suite actually emits: `policy_rate.std` (enforce) and
  `equity_mkt~ust_10y.correlation` (report) were registered reference statistics with
  no producing monthly metric, so each would judge nothing, silently, at `enforce`
  or not. New converse test (every real threshold key must be produced by a
  registered metric) plus the mirror already in place (every metric name must be
  sealable). Repointed at metrics that exist: `policy_rate.excess_kurtosis`,
  `equity_mkt~ust_10y.crisis_corr_lift`.
  *Minor 4, the idempotent-replacement property was under-tested.* The existing
  repeatability test ran the same reference twice, proving only that no
  `BatteryError` is raised — it would pass under a regression to
  `SUITES.setdefault`. New test runs `run_full_battery` against two genuinely
  different references and asserts `cross_block_corr_matrix_distance` differs.
  The related `run_battery(reference=X)`-vs-what-the-specs-closed-over identity gap
  is recorded as `governance/retrofit-register.md` RFR-16 (WP2.3 to decide) rather
  than fixed here — it needs a `MetricSpec`/`register_suite` signature change.
  *Minor 5, a short-history factor could produce a silent zero-width band.*
  `_draw_moving_block_indices` now raises when `block_length >= t`: `max_start` would
  be forced to `0`, so every replicate is the identical whole-sample block (`lo ==
  hi`). Not reachable at today's 120-month paths and 1996+ shortest series, but
  reachable once a judged path length exceeds a factor's own history.
  *Minor 6, sealed numeric constants were unpinned.* New equality tests pin
  `_DECAY_RATE_MIN/_MAX`, `_DECAY_GRID_POINTS`, `_DECAY_GOLDEN_TOL`,
  `_DECAY_MAX_ITERATIONS`, `AGG_GAUSSIANITY_MIN_SUMS` and `DEFAULT_BLOCK_LENGTH`
  against the values `pre-registration.yaml`'s prose states, so pre-seal drift trips
  a test instead of a green suite hiding it.
  *Minor 7, a corrected false claim survived in an earlier report section.*
  Annotated in place in the WP2.2 Task 2 scratchpad report rather than only at the
  fix-pass section further down.
  *Minor 8, the block-length rule's actual scope was unstated.* At production
  defaults (`block_length=120`, `resample_length=ensemble.months <= 120`),
  `ceil(L/b) = 1`: every replicate is a single contiguous window, so the `(b-k)/b`
  seam-shrinkage argument that justifies `DEFAULT_BLOCK_LENGTH=120` does not bind on
  the length-matched production path at all — it governs only the unmatched
  (full-history) path. Also documented: `acf_abs_decay` is censored at the search
  bounds (a true rate above 5.0 returns `~5.0`, not NaN); both sides censor
  identically so it is not a correctness bug, but it belongs in the sealed
  definition. Both stated in `reference.py`'s docstrings and
  `pre-registration.yaml`'s sealed conventions, with a new test pinning the
  censoring behaviour.
  Full suite green (716 tests, up from 705), ruff/pyright clean, `ah.core` coverage
  96.54%; `pre-registration.yaml` stays `sealed: false`.
- **WP2.2 Task 2 review fix pass — the monthly panel becomes runnable and sealable.**
  The review returned Spec: FAIL with two Criticals, both blocking WP2.3.
  *Critical 1, the battery never ran.* No production code path called any
  `register_*_suite()`, so `battery.SUITES` was empty in every non-test run:
  `run_battery` computed zero metrics and returned a report whose `passed` was
  vacuously `True`. `ah.eval.battery.run_full_battery` is the orchestration step that
  was missing — compute the train+validation reference from the catalog, register every
  reference-dependent suite against it (`register_reference_dependent_suites`,
  idempotent by replacement so a second run is judged against its own reference), run
  the battery — with tests asserting a **non-empty** metric set, real bands and real
  coverage come back from an actual run. `battery.py`'s docstring no longer states an
  "at import time" registration rule that no code follows, since `battery.py` is a
  sealed judged source and a rule stated only in the seal is worse than none. The
  residual (no CLI/G2 caller yet; only `monthly` of the eight suites exists, so a real
  run's verdict is monthly-tier-only) is `governance/retrofit-register.md` RFR-13 plus
  a `TODO(WP2.2 Tasks 3-6)` at `SUITES`.
  *Critical 2, 34 of 37 monthly metric names were structurally un-sealable.*
  `prereg`'s threshold-key checker validates `<stat>` against `reference.py`'s
  registries, and once `sealed: true` lands `run_battery` calls `verify()`
  unconditionally — so a threshold under an unregistered name would not merely fail the
  seal, it would break every battery run. Every monthly statistic (Hill tail index at
  5%/1%, ACF of returns to lag 5, ACF of |deviation| to lag 24, the fitted decay,
  aggregational Gaussianity, leverage correlation) is now **defined in
  `ah.eval.reference` and registered in `SINGLE_FACTOR_STATS`**; `metrics/monthly.py`
  imports the estimators and contributes only the ensemble pooling conventions. The
  whole-panel `cross_block_corr_matrix_distance` belongs to no factor and no pair, so
  it gets a third registry (`PANEL_STATS`), a `thresholds.panel` section in
  `pre-registration.yaml`, a `_check_panel_threshold_key` in `verify()` and a
  `_lookup_threshold` branch — a deliberate extension of the checker, tested, not a
  key-shape workaround. The prior handoff's claim that WP2.3 could "seal a threshold
  under these exact names directly (thresholds don't require a `reference.py` band)"
  was **false** and is corrected here; there was exactly one path and this is it.
  *Estimator conventions, all now sealed in `pre-registration.yaml`.* The ACF estimator
  is length-dependent and the reference is a different length: the n-denominator
  shrinkage alone is ~20% at lag 24 on a 120-month path against ~2% on ~1100 months, so
  a generator reproducing history exactly would sit outside its own band at long lags.
  `compute_reference` gained `resample_length` and `run_full_battery` passes the
  ensemble's own path length, so both sides carry the same bias (the `(n-k)`-denominator
  alternative was rejected: it would have to change `_acf1` too and corrects only the
  shrinkage term). A test builds a near-deterministic 24-month volatility cycle and
  shows a generator reproducing it lands inside its length-matched band at lags 12 and
  24 while history's own full-sample estimate does not. Consequence stated on
  `StatBand`: a length-matched band's `point` is not expected to lie inside `[lo, hi]`.
  The residual for *pooled* statistics (matched in neither sample size nor bias) is
  RFR-15. Separately discovered and fixed: a moving-block bootstrap keeps only the
  `(b-k)/b` share of lag-k pairs, so at the old default block length of 24 every
  long-lag band was a resampling artifact — `DEFAULT_BLOCK_LENGTH` is now 120, with a
  test pinning both the rule and the artifact.
  `acf_abs_decay` is refitted **in levels** by profiled least squares (closed-form
  amplitude, 241-point grid then golden section, deterministic, no scipy) instead of OLS
  in log space over the positive values only: dropping non-positive ACF values was a
  one-sided selection that lifted the fitted tail and biased the rate downward. The
  levels fit consumes every lag whatever its sign, so no selection happens at all. The
  exponential form is kept over the canonically hyperbolic power law, with the
  justification now stated rather than assumed (comparative summary at a fixed lag
  window; a log-log fit is equally misspecified and weights low lags harder; every
  `acf_abs_lag{k}` is separately banded, so long memory is discriminated lag by lag).
  It is also now computed per path and averaged, like every other time-ordered
  statistic — a more biased estimator of the true rate, deliberately, because it is the
  one the reference band is built from.
  `agg_gaussianity_1m` is gone: at h=1 the aggregation is the identity, so it was
  bit-identical to `excess_kurtosis` — two sealed names, one number. `acf_1`/`acf_abs_1`
  became `acf_r_lag1`/`acf_abs_lag1` for the same reason (free while `sealed: false`;
  a dated amendment afterwards), resolving the naming question the prior task left open.
  `corr_matrix_distance` is renamed `cross_block_corr_matrix_distance` (it covers
  cross-block pairs only; the missing within-block pairwise correlation statistic is
  RFR-14), and `_paired_corr_matrices` returns an explicit mask so the two matrices —
  which carry 0.0 wherever the reference has no entry — cannot be misread as correlation
  matrices. `agg_gaussianity`'s `sums.size < 4` guard became a 30-sum floor (a
  fourth-moment statistic's standard error is `~sqrt(24/n)`: 2.4 at n=4). A judged-source
  pinning test now asserts every metric-suite module on disk resolves *into* the sealed
  set, not merely that its name is in `_METRIC_SUITE_NAMES`; the `acf_abs_lag1`
  agreement test calls `reference._acf_abs_1` instead of retyping it; `acf_abs_decay`
  gains an end-to-end numeric pin against `-ln(phi)` on a constructed AR(1)-volatility
  path; the Hill registration test checks its fixture's known `alpha=2.0`; and the
  global-`SUITES` mutation in `tests/test_monthly.py` uses a snapshot/restore fixture
  rather than a `finally`-pop. Full suite green (705 tests, up from 669), ruff/pyright
  clean, `ah.core` coverage 96.54%.
- **WP2.2 Task 2 — `eval/metrics/monthly.py`, the monthly-tier stylized-fact panel.**
  All nine STEP2-GENERATOR-PLAN §WP2.2 statistics (excess kurtosis, skew, Hill tail
  index at 5%/1%, ACF of returns lags 1-5, ACF of |deviation| lags 1-24 plus a fitted
  exponential-decay rate, aggregational Gaussianity at 1/3/12-month horizons, leverage
  correlation, correlation-matrix distance, crisis-conditional correlation lift), each
  unit-tested against a closed-form or simulated ground truth with a commented,
  justified tolerance. Reuses `ah.eval.reference`'s existing `_skew`,
  `_excess_kurtosis`, `_acf1`-generalization, `_correlation` and `_crisis_corr_lift`
  definitions verbatim rather than restating any of them (this project has already
  produced one sign-inverted, independently-restated metric defect); every reused
  definition has a test asserting numeric agreement with `reference.py` on the same
  input, not just a docstring claim. New statistics (Hill, ACF beyond lag 1,
  aggregational Gaussianity, leverage correlation, the decay fit, correlation-matrix
  distance) are each defined exactly once. Two pooling conventions, stated once in the
  module docstring and never mixed: pooled path×month observations for
  marginal-distribution statistics (kurtosis, skew, Hill, corr-matrix distance, crisis
  lift), and per-path-then-averaged for time-order-dependent ones (ACF, leverage,
  decay) — concatenating paths end to end before an ACF would manufacture a spurious
  correlation at every path seam. A factor absent from a given ensemble (e.g.
  `commodities`, `kind: unavailable`) returns NaN rather than raising, so one
  inapplicable metric cannot crash a whole battery run.
  Naming deviates from the brief's suggested identifiers in two stated, deliberate
  ways: `crisis_corr_lift` (not `crisis_conditional_corr_lift`) to match
  `CROSS_BLOCK_STATS`'s existing key exactly, so the historical band shows up next to
  the generated value automatically in every report; `acf_r_lag1`/`acf_abs_lag1` are
  **not** aliased to `reference.py`'s `acf_1`/`acf_abs_1` (uniform lag-1..N naming
  preferred over an asymmetric special case) — recorded as an open naming question for
  WP2.3, with numeric agreement still asserted by test regardless of the name.
  `corr_matrix_distance` (Frobenius norm of the difference, documented against the
  alternative Herdin et al. similarity measure) is scoped to the cross-block factor
  pairs `reference.py` actually computes a correlation for — `reference.py` has no
  within-block pairwise-correlation statistic yet, a gap recorded here, not silently
  worked around.
  Registration is a builder, `build_monthly_suite(manifest, reference) ->
  tuple[MetricSpec, ...]`, plus `register_monthly_suite(manifest, reference)` calling
  `register_suite("monthly", ...)` — a deliberate deviation from the "register at
  import" pattern `ah.eval.battery`'s docstring describes, because `corr_matrix_distance`
  structurally needs a computed `ReferenceStats` (unavailable at plain import, which has
  no live `DataAccess`) to even construct its specs; splitting the suite across two
  registration paths was rejected in favour of one uniform builder. No caller wires
  this into a real battery run yet (no CLI/G2 orchestration step exists to compute a
  real `ReferenceStats` and call `register_monthly_suite` — that wiring is a later
  task's job); `ah.eval.prereg._METRIC_SUITE_NAMES` already listed `"monthly"` (Task 1
  landed it defensively), so no seal-list edit was needed. Full suite green (669
  tests, up from 637 at task start — 32 new), ruff/pyright clean.
- **WP2.2 Task 3 — `eval/metrics/horizon.py`, the 1-5yr and 10yr tiers.** Eight DN-1.1
  §II.6-normative statistics, tier-tagged exactly as the design note's table states
  (`1_5yr`: `variance_ratio_{12,36,60,120}m`, `mean_reversion_halflife`,
  `drawdown_median_depth`/`_median_duration`/`_depth_duration_rank_corr`,
  `regime_duration_{mean,p50,p90}`; `10yr`: `lost_decade_frequency`,
  `long_inflation_era_frequency`, `ten_year_return_vs_valuation_{slope,r2}`,
  `ergodicity_gap`), each registered by name+tier into `ah.eval.reference`'s
  `SINGLE_FACTOR_STATS`/`PANEL_STATS` from the start (Task 2's structural lesson
  applied up front, not fixed in afterward) and wired into
  `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` in the same commit, with a passing
  `run_full_battery` acceptance test that fails without the wiring. Per-metric
  per-path/pooled convention stated in the module docstring (RFR-15's residual bites
  every pooled one, recorded rather than left to be discovered).
  Two structural gaps made honestly NaN rather than faked: `regime_duration_*` (the
  Step-1 regime ruleset needs `usrec`/`growth_yoy`, neither a `factors.yaml` factor —
  RFR-17) and `ten_year_return_vs_valuation_*` (no CAPE/valuation factor exists —
  RFR-18); both recorded in `governance/retrofit-register.md` with an owner and a
  consequence, exactly as the `commodities` gap (RFR-8) already is. `variance_ratio`
  reuses `nonoverlapping_sums` (no second windowing scheme); `mean_reversion_halflife`
  reuses the registered lag-1 ACF estimator directly (the population lag-1
  autocorrelation of an AR(1) process IS phi); `drawdown_episodes` and
  `long_inflation_era_frequency`/`lost_decade_frequency` reuse
  `ah.data.derive.drawdown_state`/`yoy`/`regime_thresholds` verbatim rather than
  reimplementing them. `battery._require_mc_error_reported` makes "10yr metrics carry
  a Monte-Carlo error, or the battery rejects them" structural (rejects `error is
  None`, not `NaN` — an honestly-uncomputable 10yr metric must not crash every real
  battery run). Discovered and fixed in the same commit: `drawdown_state`/`lost_decade
  _frequency`'s compounding step can overflow on adversarial/extreme-magnitude input
  (this repo's `filterwarnings = ["error"]` would otherwise turn that into a hard
  crash) — now settles at `+/-inf` under `np.errstate` instead of raising, since the
  WP2.2b negative-control suite's entire purpose is running the battery against
  broken generators. `block_bootstrap_band`'s `np.percentile` step is not NaN-robust
  for a statistic that can be undefined on a short resample (`drawdown_depth_duration
  _rank_corr`) — recorded as RFR-19, not fixed here (shared, sealed infrastructure).
  Full suite green (758 tests, up from 716 at task start — 42 new), ruff/pyright
  clean.
- **WP2.2 Task 4 — `eval/metrics/tails.py` completed, `eval/metrics/utility.py` added.**
  Both wired into `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` and
  `prereg._METRIC_SUITE_NAMES` (the latter already listed `utility`), with
  `run_full_battery` acceptance tests that fail without the wiring, exactly as Task 3
  set the precedent.
  `tails.py` (tier `monthly`, on the frozen D4 strategy set): `elicitability_score`,
  the Fissler-Ziegel (2016) strictly consistent joint (VaR, ES) scoring rule at level
  0.95 — lower is better, minimized in expectation exactly at the true (VaR, ES) pair
  (a first-order-conditions derivation is in the docstring and empirically checked: a
  mis-specified pair scores strictly worse on a fixed sample, not merely "finite").
  `kupiec_pof`/`christoffersen_independence`/`christoffersen_conditional_coverage`:
  the standard proportion-of-failures and Markov-chain independence LR backtests,
  df-1/df-2 chi-square p-values via a closed-form `_chi2_sf` (no scipy; verified
  against the textbook 3.841/5.991 critical values). All three score the GENERATED
  ensemble's realized exceedances against the HISTORICAL (train+validation) VaR
  forecast for that same D4 strategy — never the generated sample's own statistics,
  which would trivially optimize and prove nothing about tail fidelity.
  `_historical_strategy_returns` builds that historical series by inner-joining
  exactly one strategy's own legs from the new `ReferenceStats.historical_series`
  field (never a fresh catalog read) and wrapping them as a single-path `Ensemble`, so
  the SAME `strategy_returns` function evaluates history and the generator — no second
  route to the arithmetic. `tail_dependence_lower`/`_upper` (cross-block factor pairs,
  not D4 strategies — DN-1.1's own scoping): a nonparametric rank-based estimator at
  the sealed 5% tail fraction (matching `hill_tail_index`'s own convention), defined
  in `ah.eval.reference` (a real `CROSS_BLOCK_STATS` entry, so the existing
  block-bootstrap machinery gives it a genuine historical band for free) and
  re-exported into `tails.py` under the same name, exactly as `monthly.py` already
  does for `hill_tail_index`/`corr_matrix_distance`.
  A new small registry, `ah.eval.reference.STRATEGY_STATS` (11 names — the four
  `var_95`/`es_95`/`var_99`/`es_99` plus the seven backtest outputs), because a D4
  strategy is sealed *data*, not a `FactorManifest` factor/pair/panel axis; a new
  `pre-registration.yaml` `thresholds.strategies` section (`"<strategy_id>.<stat>"`,
  strategy id checked against *that document's own* `d4_strategies:` block, never a
  fresh `ah.strategies.load_d4_strategies()` read, mirroring how `_check_conventions`
  already avoids that trap) and `ah.eval.prereg._check_strategy_threshold_key`.
  `utility.py` (tier `monthly`, three whole-panel `PANEL_STATS` entries):
  `discriminative_score` (logistic regression, numpy gradient descent, on pooled
  `[mean, std]` window features of real vs. generated factor dynamics —
  `|test accuracy - 0.5|`), `predictive_score` (train-on-synthetic-test-on-real
  one-step-ahead linear-model MSE), `tstr_degradation` (`MSE_tstr / MSE_trtr` against
  a train-on-real-test-on-real baseline fit the same way). No sklearn/scipy. Every
  fit's only randomness (which examples are selected/split) flows from
  `numpy.random.Generator(PCG64(UTILITY_FIT_SEED))` — a sealed module constant, not
  the battery's own run seed, so re-running the battery at a different seed reports a
  bit-identical utility tier for an unchanged ensemble (asserted directly, both
  directions: identical seed bit-identical, different seed different). Real data
  read exclusively through `ReferenceStats.historical_series`; an AST guard proves
  neither module imports `ah.eval.g2`, in the style of `test_reference.py`'s own.
  Full suite green (850 tests, up from 776 at task start — 74 new), ruff/pyright
  clean.
- **WP2.2 Task 4 fix pass 1 — metrics that improved when the generator produced less.**
  Four findings shared one root and are fixed as a family, with
  `test_generating_less_never_improves_a_backtest_metric` extended from the one case
  that was already safe (omit a leg → NaN) to all four.
  **`elicitability_score`'s arguments were inverted (Critical).** The metric froze
  `(V, E)` at history's values and varied the *generated* losses, collapsing the score
  to `c1·mean((L−V)⁺) + c2` with `c1 > 0` — monotone increasing in generated tail
  heaviness, with a generator emitting **identically zero** as its global optimum
  (measured: −3.139 for zero output vs −2.856 for matching history). DN-1.1 line 95
  makes this WP2.8's auxiliary loss, so shipping it would have trained toward zero
  volatility. Now the Tail-GAN direction: `(VaR, ES)` estimated from the **generated**
  ensemble, scored against **real** realizations — coercive as ES→0 and minimized
  exactly when generated `(VaR, ES)` matches history's. The scoring rule itself is
  unchanged and its consistency test passes under either wiring, so the deliverable is
  the new test that varies the *sample* rather than the *forecast*.
  **`discriminative_score` measured class imbalance, not fidelity (Critical).** Real
  and generated windows were pooled unbalanced (~100:1 at production scale) and scored
  by raw accuracy, which the majority-class predictor maximizes: with the two
  distributions held identical the score read 0.008 at 1:1 but 0.493 at 150:1, and
  *improved* as the ensemble shrank. Now a class-stratified split, inverse-class-
  frequency weights in the fit, and **balanced** accuracy (exactly 0.5 for any constant
  predictor at any ratio).
  **The backtest statistics scaled with `n_paths`.** `LR = 2·T·KL(p̂‖α)` with
  `T = months × n_paths` meant halving the ensemble halved the statistic and raised the
  p-value. The pooled sample size is now fixed in the sealed definition at **one path**
  (`months`, or `months−1` transitions): pooling still sharpens `p̂`, but the reported
  statistic is what a single reference-length path with that rate would have produced —
  an effect size on a p-value scale, stated as such in the new
  `conventions.backtest_reference_sample_size`.
  **`christoffersen_independence` was perfect on zero exceedances** (every count 0 ⇒
  `LR = 0`, `p = 1.0` at every `T`); now a `BACKTEST_MIN_EXCEEDANCES = 10` floor → NaN,
  in the shape of `DRAWDOWN_MIN_EPISODES`. Kupiec is deliberately *not* floored.
  Also: `RegisteredCrossStat` gains `length_matched` (mirroring `RegisteredStat`) and
  both `tail_dependence_*` entries set it `False` — at the production `resample_length`
  of 120 their 5% tail held 6 observations, below the estimator's own floor, so every
  replicate was NaN and the band was empty; the three places claiming a "band for free"
  are corrected. `_fit_gd` gains a Lipschitz-bounded step (`min(0.1, 1/L)`) and a
  gradient-norm stopping criterion — it previously ran a fixed 200 epochs at `lr=0.1`
  and diverged to `inf`/`nan` on a design ~4.5× real volatility. `_historical_strategy
  _returns` now asserts its inner join is a contiguous run of months (adjacent rows are
  read as consecutive months and multiplied by a duration of 8.5). Historical VaR/ES is
  memoized per `(strategy_id, level)` (~735 redundant pandas joins per battery run).
  Both LR builders normalize `-0.0`. RFR-23's premise is corrected in place: the ~1.2
  expected exceedances at 99% is the *per-path* count and Kupiec pools, so the real
  constraint is Christoffersen's per-path transition counts. `conventions.warm_up`
  records the momentum warm-up asymmetry (a perfect generator's expected exceedance
  rate is ~4.57%, not 5%) and why the reference-sample-size fix bounds its consequence
  to `LR ≈ 0.049` from `≈ 49`. Full suite green (862 tests, up from 850 — 12 new),
  ruff/pyright clean.
- **WP2.2 Task 4 fix pass 2 — the reference sample size was still gameable, one axis
  over.** Fix pass 1 pinned the Kupiec/Christoffersen reference sample size against the
  `n_paths` axis but read it off the judged ensemble's own `months` — so `LR ~ months`
  survived: a 60-month ensemble reported half the statistic (tail 0.05 → 0.17) a
  120-month ensemble with the identical exceedance rate reported. **The dominant "the
  metric improves when the generator produces less" failure mode had moved, not
  closed.** Fixed by pinning a new constant, `BACKTEST_REFERENCE_MONTHS = 120`, as
  `reference_n` unconditionally. The six backtest names are renamed
  `..._stat`/`..._pvalue` → `..._lr_1path`/`..._chi2_tail_1path` — the sealed
  `backtest_reference_sample_size` convention explicitly disclaims the significance-level
  reading `_pvalue` implied, so the scope is now in the name (the same fix
  `corr_matrix_distance` → `cross_block_corr_matrix_distance` made pre-seal, RFR-14).
  `conventions.warm_up`'s "LR_pof ~ 0.049, i.e. nothing" is corrected: the normalization
  rescales every departure uniformly, so a genuine coverage defect of the same magnitude
  reads identically — the honest statement is that the warm-up bias sets a *floor* on
  the smallest real coverage error this family can detect, which WP2.3 must accept or
  close, not wave away. Also: `discriminative_score`'s ~0.05–0.10 noise floor (binomial
  SE at ~60 held-out real windows) is now stated in both the sealed prose and the
  function docstring; the three public LR functions now say they differ from the
  registered (reference-scaled) metrics; `estimator_length_matching`'s blanket claim is
  now "by default", with the three departures named; `_HistoricalCache` is warmed inside
  `build_tails_suite` so a non-contiguous historical join raises at registration, not
  mid-battery-run. `governance/retrofit-register.md` gains three rows (RFR-24: a
  coverage-band alternative for WP2.3 to weigh; RFR-25: every threshold must be derived
  from post-fix runs; RFR-26: extends RFR-15's pooled-length mismatch to
  `tail_dependence_*`'s three-way version, which RFR-15's remedy doesn't reach). Full
  suite green (864 tests, up from 862 — 2 new), ruff/pyright clean.
- **WP2.2 Task 5 — `eval/metrics/memorization.py`, `eval/metrics/economics.py`,
  `eval/metrics/calibration.py`.** Three smaller suites, wired into
  `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` and `prereg._METRIC_SUITE_NAMES`
  (already listed there) exactly as Task 3/4's suites were.
  - *`memorization.py` (tier `monthly`)* — `nn_distance_{p05,p50}`,
    `membership_inference_auc`, `near_duplicate_fraction`, the suite that makes "the
    generator did not memorize its training data" falsifiable for WP2.2b's NC4. A
    "block" is a non-overlapping 24-month window (`UTILITY_WINDOW_MONTHS`, reused, not
    restated) of one factor's own path, standardized by that factor's own TRAIN
    mean/std; distance is Euclidean, within one factor only. `nn_distance` is the
    pooled nearest-TRAIN-neighbour distance of every generated block;
    `membership_inference_auc` is a distance-to-nearest-synthetic-sample
    membership-inference attack (Mann-Whitney AUC, via `ah.eval.reference._rank`'s
    tie-averaging, reused not restated) distinguishing TRAIN from VALIDATION by
    proximity to the generated output; `near_duplicate_fraction` uses a data-driven
    epsilon (the 5th percentile of TRAIN's own leave-one-out nearest-neighbour
    distance). TRAIN/VALIDATION are split from `ReferenceStats.historical_series`
    (already train+validation combined) by the SEALED `ah.splits.TRAIN`/`VALIDATION`
    date boundaries, never a second `DataAccess` read — the only reference-dependent
    suite builder that needed this trick, since `register_reference_dependent_suites`'s
    `(manifest, reference)` call shape carries no live catalog access and the task
    brief asked not to touch it. Both directions tested: a literal
    training-decade replayer (with 1e-6 noise) scores `nn_distance < 1e-3`,
    `membership_inference_auc > 0.9`, `near_duplicate_fraction > 0.9`; an independent
    seeded draw scores `nn_distance > 0.5`, AUC `≈ 0.5`, fraction `< 0.05`.
  - *`economics.py` (tier `economic`)* — DN-1.1 §II.6's Economic row
    ("Implied Sharpe ratios, term premium, ERP by regime; no-money-pump audit;
    policy-anchor sanity — Defensible ranges, documented") judged as absolute
    literature-range bounds, never a bootstrap band, matching that row's own
    reference-data column. `implied_sharpe_{EXP,SLOW,REC,CRI,STAG,REF}` is a
    structural gap (RFR-27, mirroring RFR-17/18/20/22): `label_regime` needs `usrec`/
    `growth_yoy`, neither mapped in `factors.yaml`. `term_premium` =
    `mean(ust_10y - policy_rate)` (levels, no numeraire question); `equity_risk_premium`
    = `mean(equity_mkt - cash_tr_1m)`, subtracting the ALREADY-SEALED `cash_tr_1m`
    derived series (not a second, independently invented cash-rate decision — the
    exact numeraire trap RFR-12 already documents). `money_pump_violations` (enforce,
    max 0) audits every `conventions.numeraire_zero_cost_legs` leg per path for
    "never negative, sometimes positive" (a costless free lunch); a deliberately
    always-positive `smb` fixture proves a non-zero count, the deliverable Task 5's
    brief demanded. `floor_violations` (enforce, max 0) checks DN-1.1 §II.4's stated
    floors (`i >= -1%`, `spread >= 100bp`) directly against generated values, ahead of
    WP2.8's `constraints.py` making them structurally impossible. `policy_anchor_deviation`
    substitutes a stated, simplified Taylor rule (`TAYLOR_R_STAR`/`TAYLOR_PHI_PI` from
    DN-1.1 §II.2's own prior means; `TAYLOR_PI_TARGET` from the literature, since DN-1.1
    deliberately leaves π* undetermined) for the latent r*/π*/cycle-term anchor DN-1.1
    actually specifies, which no generated factor can supply. Every computable metric
    NaNs (poisons, never drops) below `ECONOMICS_MIN_OBS = 60` pooled observations or on
    any non-finite value — closing the "generate fewer months to dodge the audit" vector
    a raw count would otherwise open.
  - *`calibration.py` (tier `monthly`)* — `pit_ks_stat_{1y,5y}`,
    `interval_coverage_{50,90}_{1y,5y}`. Rolling-origin protocol stated in full: the
    predictive distribution is the generated ensemble's own pooled non-overlapping
    12/60-month sums (deliberately unconditional — no history-conditioned forecast
    exists below Step 3); the real side is every OVERLAPPING 1-month-spaced window of
    train+validation, fixed by history alone. PIT uses a mid-rank empirical CDF;
    `pit_ks_stat` is a closed-form one-sample Kolmogorov-Smirnov statistic against
    Uniform(0,1) (no scipy — verified against the hand-derivable `D = 1/(2n)` closed
    form for an evenly spaced sample, and cross-checked against the textbook sup-norm
    definition on a fine grid). Interval coverage brackets the nominal rate on BOTH
    sides (over-coverage is exactly as much a failure as under-coverage). Both floors
    (`CALIBRATION_MIN_GENERATED_SUMS`/`CALIBRATION_MIN_ORIGINS = 30`) NaN rather than
    report a small-sample-lucky number. A correctly-specified seeded forecast scores
    `pit_ks_stat < 0.08` and coverage within 0.08 of nominal; a deliberately
    over-confident (10x-too-narrow) forecast scores `pit_ks_stat > 0.2` and coverage
    more than 0.15 below nominal.
  - *Registration.* All three registered in `ah.eval.reference.PANEL_STATS` (no `fn` —
    every metric compares the generated ensemble against real data or a stated rule
    directly, the same shape `discriminative_score` already uses), eleven new
    `conventions.<name>_estimator` blocks in `pre-registration.yaml` (plus the
    `_CONVENTIONS_KEYS` allow-list entries in `ah/strategies.py` so the file still
    loads), `money_pump_violations`/`floor_violations` sealed `enforce, max: 0` in
    `thresholds.panel` (not a placeholder — the definition itself), and
    `test_every_real_threshold_key_is_produced_by_a_registered_metric` widened to union
    four of the seven reference-dependent suites' produced names (`monthly`,
    `memorization`, `economics`, `calibration`) rather than `monthly`'s alone (a
    pre-existing scope gap the new panel entries were the first to expose). Full suite
    green (934 tests, up from 864 — 70 new), ruff/pyright clean.
- **WP2.2 Task 5 review fix pass — the eighth "generator produces less" instance, two
  missing generated-side floors, and an unstated NaN-driven verdict.**
  - *Critical 1 — `policy_anchor_deviation` rewarded a degenerate generator.* A
    `policy_rate` path DETERMINISTICALLY equal to the simplified anchor every month
    scored exactly 0.0 — the numerically best value — under the old one-sided
    `{min: null, max: 10.0}` band, despite being LESS realistic than a generator with
    genuine idiosyncratic variation (real policy rates deviate from a Taylor-type
    anchor by ~1-2pp RMS). `pre-registration.yaml`'s threshold is now TWO-SIDED
    (`min: 0.3`), mirroring `interval_coverage`'s own "neither direction is free"
    precedent; `economics.py`'s module docstring and the `policy_anchor_deviation_estimator`
    convention state the caveat explicitly. `tests/test_economics.py` gains the
    deliverable: `test_policy_anchor_deviation_near_zero_is_not_automatically_good`
    shows the degenerate generator scoring strictly better than a realistic one, and
    `test_policy_anchor_deviation_degenerate_generator_fails_the_sealed_two_sided_band`
    shows the sealed band now catches it.
  - *Important 2 — `money_pump_violations` narrowed to a per-leg check.* DN-1.1's audit
    names a strictly dominating COMBINATION of factors; the implementation checks only
    single legs, with no search over weighted combinations. Stated in `economics.py`'s
    docstring and `pre-registration.yaml`'s `money_pump_estimator`, and recorded as
    `governance/retrofit-register.md` RFR-29.
  - *Important 3 — `memorization.py` had no generated-side floor.* Both sibling suites
    floor the generated side (`ECONOMICS_MIN_OBS`, `CALIBRATION_MIN_GENERATED_SUMS`);
    memorization only floored TRAIN. A one-path, 24-month ensemble collapsed
    `nn_distance_p05/p50` to a single observation and drifted
    `membership_inference_auc` toward its favourable 0.5 — "the generator produces
    less" reading as a pass. New `MEMORIZATION_MIN_GENERATED_BLOCKS = 30` (matching
    `CALIBRATION_MIN_GENERATED_SUMS`'s shape) NaNs all four names together below the
    floor; `test_memorization_nan_when_generated_side_is_too_small_even_with_ample_train`
    is the deliverable (TRAIN clears its own floor easily; the generated side does not).
  - *Important 4 — calibration tested only the under-confidence direction.* The
    over-wide (under-confident) direction — the likelier gaming route, a lazy
    huge-variance generator earning near-perfect coverage for free — was untested.
    `test_underconfident_forecast_shows_high_coverage_and_a_large_ks_statistic` adds it.
  - *Important 5 — `MEMORIZATION_BLOCK_MONTHS` silently followed `UTILITY_WINDOW_MONTHS`.*
    The sealed estimator states 24 as a literal; the code now raises `AssertionError`
    at import time if the two ever diverge, and a new test pins the value directly.
  - *Important 6 — `TAYLOR_PI_TARGET`'s literature substitution had no retrofit-register
    row.* RFR-27 covered only `implied_sharpe_*`'s structural gap. New RFR-28 records
    the substitution and the dropped `phi_c*c_t` term as the durable artifact WP2.3
    reads (an implementer's report is not).
  - *Important 7 — two new enforce gates changed the battery verdict, unstated.* On the
    `run_full_battery` orchestration fixture, `money_pump_violations`/`floor_violations`
    are both NaN (the fixture emits none of the audited factors), which FAILS both
    enforce thresholds under THE ONE NaN RULE — `report.passed` is `False`, previously
    unasserted anywhere. Decided explicitly rather than softened: NaN continues to fail
    (consistent with the platform's one uniform NaN rule; an ensemble that omits the
    audited factors has produced less, exactly the failure mode these gates exist to
    catch). `test_run_full_battery_orchestration_fixture_fails_on_the_money_pump_and_floor_gates`
    pins the verdict; `governance/retrofit-register.md` RFR-30 records the decision and
    its consequence for WP2.4 (the bootstrap generator must emit at least one audited
    factor from each set).
  - *Minor.* The three stray `np.random.default_rng(...)` call sites (two in
    `test_economics.py`, one in `test_calibration.py`) converted to
    `Generator(PCG64(seed))`, the repo's one seeded-RNG convention.
    `test_economics.py` gains the `ah.eval.g2`-import AST guard its two siblings
    already had. `test_every_real_threshold_key_is_produced_by_a_registered_metric`
    widened from four of the seven reference-dependent suites' produced names to all
    seven (adding `horizon`/`tails`/`utility`). `_pooled_memorization_signals` is now
    computed once per ensemble and cached (identity-keyed via a weak reference) across
    all four memorization metric closures, instead of four times. `pit_ks_stat_5y`/
    `interval_coverage_{50,90}_5y` re-tiered from `monthly` to `1_5yr` (DN-1.1's own
    tier for a 60-month horizon), reconsidered and corrected before the pre-registration
    seal rather than carried forward as a known-wrong assignment.
  - Full suite green, ruff/pyright clean.
- **WP2.2 Task 6 — `eval/metrics/conditional.py`, condition adherence + off-support
  degradation.** The last WP2.2 suite, and the only one whose metrics REGENERATE
  ensembles rather than reading the judged one: every metric resolves
  `ensemble.meta.generator_id` via `ah.gen.registry.resolve` and calls that SAME
  generator's `.sample(world, n_paths, seed)` fresh, once per authored/swept
  `NumericWorld` — "the bootstrap runs this suite too" is meaningful because the
  generator under test is re-invoked against conditions it may never have seen, not
  read off a stashed unconditional ensemble. Registered tier `monthly` (DN-1.1 names no
  "conditional" row); every threshold sealed `report`, never `enforce` — nothing here
  gates G2 (STEP2-GENERATOR-PLAN §WP2.3's own sealed rationale).
  - *Part A — condition adherence.* Four condition types mapped to
    `factor_conditions` (`inflation.average_pct`, `policy_rate.{start_pct,end_pct}`,
    `crisis_windows[0].{start_quarter,length_quarters}`,
    `crisis_windows[0].severity`), each backed by two checked-in authored worlds
    (mild/severe) under new `fixtures/worlds/conditional/*.json` (validated against the
    schema by both production code and a dedicated test). Two metrics per type —
    `condition_adherence_error_{type}` (pooled mean of every per-path error, across
    every path of every world of that type) and `condition_adherence_error_p90_{type}`
    (the pooled 90th percentile of the identical array), so a generator "usually right,
    occasionally wildly wrong" cannot hide behind a mean. `crisis_severity`'s target
    magnitude uses a stated, simplified linear map from the schema's own "1 =
    2008-scale" anchor (Q4 2008 S&P 500 TR ≈ -21.9%, `CRISIS_SEVERITY_REFERENCE_
    QUARTERLY_SHOCK_PCT = 22.0`) — the identical kind of substitution
    `economics.py`'s `TAYLOR_*` constants make, for the identical reason.
  - *Part B — off-support degradation.* Swept over `inflation`/`rate` only (the two
    condition types with a real train+validation quantity to define "distance from
    support" against — `crisis_timing`/`crisis_severity` have no real-valued analog
    under this simple definition; **WP2.7's `support.py` supersedes this placeholder
    for every condition type**). Distance is an ordinary z-score against
    `ReferenceStats.historical_series`; four levels (`typical` z=0, `p95`/`p99` the
    standard-normal quantiles, `beyond` z=4) construct the swept target
    `mean+z*std`, clipped to the schema's bounds. `off_support_adherence_at_{level}`
    (pooled mean error) and `off_support_pass_rate_at_{level}` (fraction within a
    stated 2pp tolerance) — "battery" here names this suite's own pooled checks, not
    the full cross-suite battery (that is WP2.9/WP2.11's severe-test-shaped
    evaluation).
  - *Anti-gaming, this work package's dominant failure mode, addressed from the
    start rather than by a fix pass.* Every pooled metric NaNs the WHOLE aggregate
    (never drops silently to a smaller surviving sample) on any single world's
    unresolvable `generator_id`, a generator exception during `.sample()`, an absent
    conditioned factor, or a non-finite value — `CONDITIONAL_MIN_OBS=20` is an
    additional floor. Tests prove both directions per condition type (a hand-built
    exact-tracking generator scores ~0; one mirroring WP2.2b's NC5 — ignores
    `factor_conditions` entirely — scores clearly worse), the p90-catches-a-tail case
    (88%-exact/12%-wildly-off generator: mean stays small, p90 does not), monotonic
    off-support degradation and a typical-vs-beyond pass-rate gap (both against a
    generator whose fidelity is a stated, known function of distance), and that
    omitting the conditioned factor NaNs rather than reading as a smaller error than a
    generator that emits it and adheres badly.
  - *Registration.* 16 names in `ah.eval.reference.PANEL_STATS` (no `fn`/band, the
    `economics`/`memorization`/`utility` shape — every metric compares a freshly
    generated ensemble to a WorldSpec's stated target, never a single-argument
    historical point estimate); `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS["conditional"]`
    (a test asserts a real `run_full_battery` call returns all 16 by name, confirmed to
    fail before the row was added); five new `conventions.<x>_estimator` blocks in
    `pre-registration.yaml` (one per condition type covering its mean/p90 pair, one
    shared across all eight off-support names), plus their five keys added to
    `ah.strategies._CONVENTIONS_KEYS`'s allow-list (missed the first pass — the sealed
    document otherwise fails to load at all). `ah.eval.metrics.economics._cpi_yoy`
    renamed to public `cpi_yoy_from_level` so `conditional.py` reuses the identical
    trailing-12m YoY transform rather than restating it.
  - *`mc_error` is honestly `0.0`, not NaN, for every metric here* — every metric
    ignores the passed ensemble's own paths (only `generator_id`/`seed` carry into the
    regeneration), so `ah.eval.battery.mc_error`'s subsampling recomputes the identical
    value on every subsample by construction. Stated in the module docstring and pinned
    by a test rather than left to be discovered. *(Superseded by the fix pass below:
    correct arithmetic, misleading number.)*
  - Full suite green, ruff/pyright clean.
- **WP2.2 Task 6 review fix pass 1 — two Criticals, and the seal widened to cover
  sealed input data.**
  - *Critical 1 — partial support silently shrank the off-support pool.* When
    `_support_mean_std` returned `None` for one of the two swept types, the level was
    built from the surviving type alone and reported under
    `off_support_adherence_at_{level}`, whose sealed definition says "across **both**
    swept types". Now all-or-nothing: if any `OFF_SUPPORT_TYPES` member lacks support,
    every level is empty and every Part B metric NaNs. The pre-existing guard tested
    only the both-absent case — holding fixed the exact axis the defect lived on; the
    one-present/one-absent case is now parametrized over both directions.
  - *Critical 2 — the off-support monotonicity test's inflation arm was inert.* The
    `cpi` test fixture was deterministic geometric growth, so its trailing-12m YoY was a
    **constant** and `std(ddof=1)` ≈ 1e-14: every swept inflation target collapsed onto
    the historical mean and the arm contributed ~zero error at every level (measured:
    `[1.32e-13, 1.20e-13, 1.13e-13, 9.37e-14]` — flat, and *decreasing*). The whole
    monotone trend came from `policy_rate`; the test would have passed with the
    inflation sweep deleted. `cpi` is now a log random walk with real YoY dispersion,
    degradation is asserted **per swept arm** (a pooled assertion is what let one dead
    arm hide), the pooled assertion is strict (it previously read `later >= earlier -
    1e-9` under a comment claiming "strictly increasing"), and a separate test pins that
    both support distributions have real dispersion so a future fixture edit cannot
    silence an arm again.
  - *`mc_error` now measured over regeneration seeds (Important 7).* Reporting `0.0`
    beside a value carrying real Monte-Carlo uncertainty is worse than reporting
    nothing — it is the exact number a WP2.3 threshold author reads to size a band.
    New `conditional_mc_error` recomputes each metric at
    `CONDITIONAL_MC_ERROR_REPLICATES = 8` further regeneration seeds and reports
    `std(replicates, ddof=1)` (no `/sqrt(k)`: each replicate is an independent re-draw
    of the whole statistic, and the reported value is one such draw). Wired through a
    new **additive** `ah.eval.battery.MetricSpec.mc_error_fn` hook — default `None`
    keeps the uniform path-subsampling estimator for every other suite.
  - *Regeneration memo (Important 8, closes RFR-31 via RFR-32).* `_regenerate` is now
    memoized on the world **document** (canonical JSON), `generator_id`, `n_paths` and
    `seed` — keyed on the document rather than `world_id` because Part B's sweep worlds
    reuse one id per (type, level) while their target is a function of the reference, so
    an id-keyed memo would serve a second battery run the first run's ensemble. Cleared
    on every `build_conditional_suite`, so it never outlives one registry state. A full
    evaluation drops from ~670 `.sample()` calls to ~144 — fewer calls than before, now
    buying a real error bar instead of a tautological zero.
  - *The authored worlds are now inside the seal (Important 5, RFR-33).*
    `conventions.condition_adherence_*_estimator` defines each statistic as "pooled
    across every checked-in `fixtures/worlds/conditional/*.json` world tagged X", but
    `prereg._default_judged_sources()` hashed only `.py` files plus two YAMLs — so
    editing a world's `average_pct` changed every inflation metric with no lock
    violation and no amendment. New `_REQUIRED_JUDGED_FIXTURE_GLOBS` seals the directory
    as input data, exactly as `factors.yaml` is; a test edits a world and asserts the
    digest changes.
  - *Two exception paths no longer abort the whole battery (Important 3).*
    `gen_registry.resolve` invokes the registered **factory** (WP2.4's bootstrap will
    load and fit in its factory) and `load_worldspec(doc)` sat outside the `try`, so a
    factory raising during construction, or a swept world failing schema/pydantic
    validation, propagated out of `spec.fn` and lost every other suite's results. Both
    are inside one guarded region now, with a test each.
  - *Schema bounds derived, not restated (Important 4).* `_off_support_bounds()` reads
    `factor_conditions.{inflation.average_pct, policy_rate.end_pct}`'s `minimum`/
    `maximum` from `schemas/worldspec-v1.0.schema.json`; a new test validates every
    **programmatically swept** world against the schema (the existing fixture test
    globbed `FIXTURES_DIR` only).
  - *Tag↔field consistency validated at load time (Important 6).* A world tagged
    `inflation` whose `factor_conditions` lacked an `inflation` block raised a raw
    `KeyError` at metric-evaluation time → battery abort, not NaN.
  - *Missing tests added.* A determinism pair (same seed ⇒ bit-identical, different seed
    ⇒ different — using the only test double that consumes `seed`), and the min-obs NaN
    branch, which was never exercised: the test carrying that name asserted
    `errors.size >= CONDITIONAL_MIN_OBS`, the **opposite** of its claim. It is renamed
    to what it actually checks and a real boundary test added (one short ⇒ NaN, exactly
    at the floor ⇒ reported), for the mean, the p90, and Part B.
  - *Minors.* Fixed a misattributed citation ("DN-1.1 §WP2.3" → STEP2-GENERATOR-PLAN
    §WP2.3) in a sealed source; `import copy` hoisted to module level; conditioning
    targets read off the `NumericWorld` projection the generator was handed rather than
    the raw JSON dict (`load_worldspec` now runs once per regeneration, not twice); the
    regeneration index `k` is globally unique instead of restarting per condition type
    (the docstring's `base_seed + 7919*k` claim is now true); `off_support_pass_rate_at_
    beyond`'s `min: 0.0` — a threshold on a `[0,1]` rate that can never be violated —
    raised to a non-vacuous provisional `0.05`; `tests/test_conditional.py` gained an
    autouse fixture restoring `ah.gen.registry`'s global table (seven registrations
    previously leaked into every later test module); and `rate_endpoints_mild`'s
    endpoints widened from 2.0→3.0 to 5.0→2.0, because a 3.0 endpoint was nearly free
    against the condition-ignoring generator's flat-3.0 output — the discrimination
    assertion is now a per-type margin scaled to each type's own fixture spread rather
    than a single flat `+1.0`.
  - 995 tests pass (was 972); ruff/pyright clean; coverage gate 96.54%.

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
