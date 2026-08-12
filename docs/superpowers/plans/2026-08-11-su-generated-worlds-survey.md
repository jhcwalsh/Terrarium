# SU generated worlds — Task 0 survey findings (2026-08-11)

Four read-only surveys against the working tree at `2d00470`. File:line
references verified at survey time. This is the evidence base for the answers
recorded in `2026-08-11-su-generated-worlds.md`; nothing here changed code.

## S1 — How `ah world build` / `ah run` handle `bootstrap-stratified` today

- `ah world build` (`cli.py:99-142`) never touches `ah.gen`: no registry call,
  no catalog, no `--generator` flag. `generator_id` is carried as an opaque
  field. Validator V1–V12 never inspect it — **a bootstrap world builds and
  validates green today.**
- `ah run` is hardwired toy: `cli.py:194` calls `ah.core.engine.run_ensemble`
  unconditionally; `engine._require_toy` (engine.py:179-185) raises
  `UnsupportedGeneratorError` for any non-toy id (verified live). Every
  downstream surface goes through it: replay/verify
  (`runrecords.compute_outputs_digest`), battery, bundle, inspect,
  credibility, buildconsole.
- The stamp would lie: `cli.py:210-218` writes
  `generator_version=TOY_ENGINE_VERSION` unconditionally (same in
  `buildconsole.py:452-456`). No field carries `vintage_id` /
  `checkpoint_hash` / `conditioning`, all of which `EnsembleMeta` produces.
- Contract mismatch: `Generator.sample` returns an `Ensemble` of
  `(n_paths, months, 16)` factor slabs (`gen/base.py:108-163`); the entire
  consumer chain wants `EnsembleResult` — `dict[asset -> (n_paths, months)]`
  over the 8-asset `ASSETS` tuple — plus, per revealed path, `EnginePaths`
  with `rate/spread/inflation/crisis`. **No adapter exists anywhere.**
  `ah/port/mapping.py` converts to a different namespace (HF/PM sleeves).
- Seed rule mismatch: toy loops `base + 7919*k` per path;
  `BootstrapV1.sample` consumes ONE seed for the whole draw
  (`_draw_indices`, bootstrap.py:875); `ensemble_seed` (:767-770) exists but
  is not the sampler's default contract.
- Schemas: v1.3 enum admits `bootstrap-stratified` (deprecated alias) AND
  first-class `bootstrap-v1`. `engine_defaults` has **no vintage field** —
  the campaign vintage is baked into `bootstrap_v1_factory()`; the only
  WorldSpec escape hatch is an `^x_` extension key.
- Conditioning: `regimes.mode == "sequence"` stratification is the ONLY
  channel; all `factor_conditions` are structurally ignored
  (`conditioning["factor_conditions_honoured"] = False`, bootstrap.py:820).
- Training read: `campaign_source()` → local DuckDB catalog over `data/`
  (uncommitted, gitignored), `DataAccess.train_val` only — the K1 fence
  holds structurally; no network.

**Verdict: an adapter WP is required.** Smallest seam: a generator-backed
`run_ensemble`/`run_path` pair that resolves via `ah.gen.registry`, maps 16
factors → the 8 `ASSETS` + `rate/spread/inflation/crisis`, and returns the
identical `EnsembleResult`/`EnginePaths` dataclasses so digest, replay, twin,
play, and bundle are untouched. CLI dispatch is one line each at
`cli.py:194`/`:215` plus `runrecords.py:33`; the seed rule must be
reconciled explicitly.

## S2 — Bundle gaps (16 enumerated; the load-bearing ones)

- Version/loader: `world-bundle-0.4` (bundle.py:56); app allowlist
  `SUPPORTED_BUNDLE_VERSIONS` ends at 0.4 (`bundle.ts:18-28`) — 0.5 must be
  added or load fails.
- Everything is asset-shaped: `series_order`/`bands` derive from
  `engine.ASSETS` (bundle.py:102,112); band math hardcodes percent
  (`/100.0`, :116). **Units split:** only 5 of 16 factors are returns and
  they are DECIMAL (prereg:676-677); 11 are levels — cumulative-growth fans
  are meaningless for them, and the app has no level renderer and no units
  field to dispatch on (`FanChart.tsx:222-230`). Bundle 0.5 needs per-series
  units/kind.
- App render filter is a hardcoded toy list (`ASSET_LABELS`,
  `Play.tsx:43-52`): a 16-factor bundle silently renders exactly one chart
  (`commodities`).
- Proxy disclosure (sealed `proxy_share_disclosure`, requires per-factor
  share + HAR-vs-VXO split): 8 of 16 factors carry proxy months;
  **per-month attribution is unrecoverable post-generation** — bootstrap
  discards drawn row indices (bootstrap.py:793 vs `Ensemble` fields);
  per-factor shares are computable only via `ah.datalab.proxy_share`
  against the uncommitted `data/` catalog; NO committed machine-readable
  proxy-share artifact exists (reference-run.json has none). Either carry
  row indices on the Ensemble (upstream change) or compute+commit a
  per-factor share artifact at build time.
- Reproducibility posture breaks: today's bundle rebuilds from a RunRecord
  alone; a bootstrap ensemble regeneration needs the licensed vintage store
  (`data/` gitignored) — a clean checkout/CI cannot rebuild. A decision is
  needed (OD-4): require `data/` at build, or persist the needed slice.
- Credibility pointers: `artifacts/campaign3/promotion-verdict.json`
  (verdict SHIP-BENCHMARK, severe flags, k3 block) + vintage
  `2026-08-10.1` from reference-run.json; nothing under `src/` reads it
  today; new bundle section needed — and note `tape_seal` covers only the
  tape, so new sections need their own integrity story.
- Realized regimes: bootstrap worlds have per-path per-month labels
  (`RegimeRecord`) — neither stored nor carried; `summary.episodes` assumes
  authored quarter-indexed sequences.
- Size: not a constraint — current bundles use 3.1% of the 1MB budget;
  16 factors add ~+12KB gz.
- Fixture claim: "both suites verify `app/fixtures/toy.bundle.gz`" is FALSE
  today — only the vitest suite reads it (`bundle.test.ts:22`);
  `tests/test_bundle.py` builds its own and pins `ASSETS` directly
  (already recorded in BUILD-SUMMARY.md:572 contra CLAUDE.md). Task 2's
  acceptance line is new work.

## S3 — Twin / mapping / OD-2

- Two disjoint sleeve layers, connected by no code path: (A) the sealed
  mapping layer (`port/mapping.py` → HF/PM sleeves; consumes a generator
  `Ensemble` natively; ZERO callers in src/) and (B) the played twin
  (`play.py` + `port/engine.py`; consumes toy `EnginePaths`; wired into
  bundle/serve/console).
- **The played twin already runs a commodities `LiquidSleeve` at 5 points**
  (`play.py:96-105`); bands and console display exist. The commodities data
  blocker (RFR-8) is formally discharged at campaign-3 (`factors.yaml`
  AQR-derived total return; `pre-registration.yaml:348 missing_factors: []`).
- The sealed artifact `mappings/sleeve-mappings-v1.0.yaml` (G3 lock) still
  records `structural_omissions: {hy_spread, commodities}` ("unestimable,
  NOT zero") — estimated on vintage `2026-08-07.5`, superseded on data but
  not on seal. Re-estimating = a named G3 amendment (deferred, disclosed).
  `mapping.py` runtime is deliberately OUTSIDE the seal.
- Asset construction for the adapter: `equity`←`equity_mkt` (×100),
  `commodities`←`commodities` (×100), `bonds`←`ust_10y` duration-8.5
  (`_bond_total_return`, mapping.py:76-89, reusable verbatim),
  `hy`←`hy_spread`+`ust_10y`+a stated loss convention,
  `spread`←`ig_spread` (**units: percent, but play.py:342 and
  feed.py:61 expect bps** — explicit conversion),
  **`reits`← NO FACTOR (OD-3: needs a stated construction or removal)**,
  `pe/pc/re`← the PM sleeve mappings + smoothing kernel — the real adapter
  work, where the sealed mapping table finally becomes load-bearing on the
  play path.
- ER-6 inherited whole: `rc_curve` lives in cohort age arithmetic
  (`cohort.py:183-185`), market enters only via near-flat `f_call` —
  generator-independent, confirmed.
- Alpha stamp: generated worlds should carry a NEW `PLAY_ALPHA_VERSION`
  value (e.g. `port-v1-cashflow-gen`), not a bump of the toy one — toy
  leaderboard rows untouched.
- **OD-2 survey recommendation: PLAYABLE** (Option A). Binding the sleeve to
  the factor is a units-stated 1:1 in the adapter; no seal touched;
  display-only is strictly MORE work (weight redistribution → alpha bump →
  every golden moves) or a silent-proxy move the project refuses. Disclose
  the PM-loading omission; defer re-estimation to a named G3 amendment.

## S4 — Artifacts (PD-4) + the ER-9 bound

- Tier-1 templates are generator-agnostic (plain strings/floats; datelines
  are world-relative Y{n}M{n}). The coupling is the producer `feed.py`,
  which reads `EnginePaths.rate/spread/inflation/crisis` + asset returns.
- Needed derived inputs for a bootstrap world: YoY inflation (the `cpi`
  factor is an INDEX LEVEL, and a resampled level is discontinuous at every
  block seam — derive YoY within blocks or from a derived factor), spread
  in bps (`hy_spread` is percent; feed thresholds 800/1200/1600bp can never
  fire on a percent series), crisis mask from `RegimeRecord` CRI labels
  (bootstrap ignores `factor_conditions.crisis_windows`).
- `quarterly_statement` peer bands re-run the institution per peer path —
  needs the factor→sleeve adapter first. `board_pack` has NO producer at
  all today (toy included). `central_bank_statement` works unchanged
  (`policy_rate` same scale).
- Landmine: `committee.py:116` treats tape column 0 as an equity return; on
  a factor-ordered bootstrap tape column 0 is `cape_v` — silently renders
  nonsense. Must be keyed by name, not position.
- PD-4 reality: artifacts are pre-authored at BUNDLE build from a RunRecord
  (`bundle.py:166`), not at `ah world build`. The plan's Task 4 wording
  should follow the existing seam.
- **ER-9 moot check: PROVEN, bound exact and attained.** The ensemble is a
  row-copy of the panel (bootstrap.py:794) — no scaling, no innovation.
  Empirical: 512×120 ensemble min/max equalled panel min/max to the bit.
  Worst equity month any bootstrap world can print: **−22.59% (Oct 1987)**
  vs the toy's −86.3% artifact. hy_spread max 9.968% (Dec 2008);
  equity_vol max 59.89 (Oct 2008); policy_rate range 0.05–19.10%.
  Qualifiers: pre-1986 `equity_vol` months are HAR model output (one pinned
  draw); `hy_spread` is 100% proxy on train+val; stratification pins only
  block START months — blocks walk out of their stratum, so the all-months
  bound is the world-level bound (never quote the STAG-stratum column as a
  bound). Stale note found: bootstrap.py:593 hard-codes `hy_oas=NaN` into
  regime labels while the panel now carries hy_spread — the CRI high-yield
  disjunct is dead; docstring documents it but is stale vs the data.
- Per-factor bound table (1953-04..2020-12, vintage 2026-08-10.1), the five
  return factors, monthly fraction: equity_mkt −0.2259/+0.1662,
  commodities −0.2086/+0.2340, mom −0.3436/+0.1802, smb −0.1741/+0.2125,
  hml −0.1383/+0.1224. Full table including level factors in the survey
  transcripts; regime strata of the 813 months:
  EXP 405, REC 159, REF 111, SLOW 69, CRI 38, STAG 31.
