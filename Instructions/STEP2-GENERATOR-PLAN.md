# STEP2-GENERATOR-PLAN.md — Build the Scenario Generator
## Implementation plan for Claude Code · Alternate Histories Platform · Step 2 (WS-B) · runs to Gate G2
### v1.1 · July 2026 — revision after independent review

**v1.1 changes (all from review):** reference statistics and thresholds computed on train+validation only (closes a holdout leak); new conditional-generation metric suite; negative-control validation of the battery itself; multi-seed G2 decision rule with variance-aware margins; conditioning-support diagnostic in the joinery; severe-test protocol pinned in pre-registration; single frozen data vintage for the whole campaign; acceptance-filter metrics disjoint from enforce tier with filtered/unfiltered reporting; formal tuning protocol; calibration tier; seal extended to cover decision-rule and enforce-metric code; signature-deferral and regime-label-sensitivity honesty notes.

**How to use this file:** work in the existing `alternate-histories/` repo (Step 0 tagged `v0.1.0-g0`; Step 1 complete — factor panel, de-smoothed sleeves, episode packs, vintage store live). Place at repo root beside the prior plans. Work through WP2.1 → WP2.11 in order, one PR per work package. Vendor into `docs/`: **DN-1.1 design note**, `tier1-synthesis-and-decisions.md`, `data-requirements-register.md`. If DN-1.1 is missing, halt and request it.

---

## 0. Mission

Build the generator layer: a frozen transparent **benchmark**, the four-layer **hierarchical generator** of DN-1.1 (climate → seasons → weather → joinery), a complete **horizon-stratified validation battery that has itself been validated**, and the **pre-registered, noise-aware G2 decision** that promotes the challenger or ships the benchmark. The order is not negotiable: battery, negative controls, benchmark, and sealed thresholds all precede any generative training. **No cashflow modeling, no institution twin, no artifact/LLM work.**

### Definition of done (Gate G2 — every item is a command that produces evidence)
1. `ah eval battery --system <id>` runs the full battery (monthly, horizon, tails, utility, memorization, economics, **conditional**, **calibration** tiers) for every registered system and writes a report embedding the pre-registration hash.
2. `pre-registration.yaml` is **sealed before the first training run**; the seal (`pre-registration.lock`) hashes the YAML **and** the enforce-tier metric implementations **and** `g2.py` — thresholds and the code that judges them are frozen together. Amendments only via `pre-registration-amendments.md` (date, section, reason, post-training flag), machine-checked.
3. All reference statistics and acceptance bands are computed on **train+validation only**; a test proves the holdout span never enters `reference.py`.
4. The **negative-control suite** passes: the battery rejects every known-bad generator (§WP2.2b) at enforce level. The battery has a validation record of its own.
5. All five ablation systems (A–E) are registered and evaluated on identical seeds, splits, and the **single frozen campaign vintage** recorded in `pre-registration.yaml`.
6. The touch-once holdout is unreachable from training/tuning code paths (explicit-purpose token + import-graph test) and is evaluated exactly once, by WP2.11.
7. Neural systems are trained with **≥3 seeds**; `ah eval g2` executes the pre-registered decision rule over the multi-seed evidence and emits `G2-EVIDENCE.md` with a PROMOTE or SHIP-BENCHMARK verdict and the per-criterion arithmetic, including Monte-Carlo error bars.
8. Every ensemble is reproducible: generator_id + checkpoint hash + seed + config hash + vintage id pinned in the RunRecord; digest-identical on re-run (or within documented tolerance for GPU-nondeterministic ops, per model card).
9. The held-out-regime severe test runs under its **pinned protocol** and its result — pass or fail — is written up in `G2-EVIDENCE.md`.
10. Lint, types, tests green; coverage ≥85% on `ah/gen/` and `ah/eval/`; every battery metric unit-tested against closed-form or simulated ground truth.

---

## 1. Tech decisions (fixed — do not relitigate)

- **Two runtimes, no interop.** L1/L2: **numpyro + JAX** (NUTS, mixed-frequency state space). L3: **PyTorch 2.x**. Communication only through versioned artifacts (parquet/npz); never one process.
- **Config:** YAML → pydantic settings, one config per experiment, hashed into the run record.
- **Experiment tracking:** local-first `experiments/<exp_id>/` (config, seed, git SHA, metrics, checkpoints, logs); `ah exp list|show|diff`. No external service.
- **Campaign vintage freeze:** the entire Step-2 campaign runs on **one** Step-1 data vintage, named in `pre-registration.yaml`. Monthly refreshes continue but are not consumed here; any deliberate vintage change restarts the campaign with an amendment entry.
- **Determinism:** JAX explicit PRNG keys; PyTorch manual seed + `use_deterministic_algorithms(True)` + fixed cuDNN flags; residual GPU nondeterminism documented per model card, digests then asserted within stated tolerance — never waved away.
- **Checkpoint identity:** SHA-256 over state dict + config hash; recorded in registry and RunRecords.
- **Data access:** only through `ah/data` catalog reads pinned to the campaign vintage. No ad-hoc parquet paths.
- **No network in tests; no training in CI** (CI: battery unit tests, negative-control smoke subset, 30-second smoke train, bootstrap system end-to-end).

## 2. Package layout (create in WP2.1)

```
src/ah/
├── gen/
│   ├── registry.py            # generator plugin registry; resolves WorldSpec generator_id
│   ├── base.py                # Generator protocol: fit(), sample(world, n_paths, seed) -> Ensemble
│   ├── bootstrap.py           # regime-stratified stationary block bootstrap (benchmark)
│   ├── climate/  model.py fit.py simulate.py          # L1 (DN-1.1 §II.2)
│   ├── regimes/  semimarkov.py fit.py                 # L2
│   ├── blocks/   data.py constraints.py losses.py diffusion.py flow.py train.py tuning.py   # L3
│   ├── joinery/  waypoints.py bridge.py reconcile.py assemble.py support.py                 # L4
│   └── systems.py             # ablation systems A–E as named compositions
├── eval/
│   ├── metrics/  monthly.py horizon.py tails.py utility.py memorization.py economics.py
│   │             conditional.py calibration.py
│   ├── negative_controls.py   # known-bad generators the battery must reject
│   ├── battery.py             # orchestrates tiers -> BatteryReport (filtered & unfiltered)
│   ├── reference.py           # train+val-only reference stats + block-bootstrap CIs
│   ├── prereg.py              # seal/verify: YAML + enforce-metric code + g2.py hashes
│   ├── g2.py                  # the multi-seed G2 decision rule, executable
│   └── report.py
├── splits.py                  # train / validation / touch-once holdout guard
pre-registration.yaml          # sealed thresholds + protocols (WP2.3)
experiments/                   # gitignored except manifests
```

## 3. Work packages

### WP2.1 — Experiment infrastructure, splits, leakage guards
`splits.py`: named spans — `train`, `validation` (rolling/expanding folds per D9), `holdout` (final 3–5 years; dates in pre-registration). The guard: `DataAccess` returns frames only for a requested split; `holdout` requires an explicit `purpose="final-evaluation"` token constructible only in `eval/g2.py` (separate module; **import-graph test** proves training modules cannot reach it). Experiment scaffolding, config hashing, git SHA capture, seed recording, `ah exp` CLI. Generator registry + `base.Generator` protocol; `Ensemble` container (paths, factor names, metadata: generator_id, checkpoint_hash, config_hash, vintage_id, seed, conditioning record). Wire registry to WorldSpec `engine_defaults.generator_id`.
*Acceptance:* import-graph test green; identical configs → identical hashes; unknown generator ids error clearly.

### WP2.2 — The validation battery (full implementation, train+val referenced)
Replace Step 0's skeleton. **`reference.py` computes every historical reference statistic and block-bootstrap band on train+validation only** — a dedicated test asserts the holdout span is absent from its inputs (leak channel closed at the source, so WP2.3's bands inherit cleanness).
Metric suites (each unit-tested against closed-form or simulated ground truth):
- **monthly.py** — excess kurtosis, skew, Hill tail index (5%/1%), ACF r (1–5), ACF |r| (1–24) with fitted decay, aggregational Gaussianity (1/3/12-month sums), leverage correlation, correlation-matrix distance, crisis-conditional correlation lift.
- **horizon.py** — variance ratios (12/36/60/120m), mean-reversion half-lives, regime duration distributions, drawdown depth×duration joint distribution, lost-decade frequency, long-inflation-era frequency, 10y return vs starting valuation (slope, R²), ergodicity (long-path vs ensemble moments).
- **tails.py** — VaR/ES 95%/99% on the frozen D4 strategy set, elicitability score, Kupiec/Christoffersen backtests, tail-dependence coefficients.
- **utility.py** — discriminative score, predictive score, TSTR degradation.
- **memorization.py** — nearest-neighbor distances vs train, membership-inference AUC, near-duplicate block detection.
- **economics.py** — implied Sharpes by regime, term premium, ERP, no-money-pump audit, floor violations (must be zero), policy-anchor sanity.
- **conditional.py** *(new)* — **condition adherence**: for a battery of WorldSpec test worlds (authored set, checked in), measure realized ensemble statistics vs specified conditions (inflation average, crisis timing/severity, rate endpoints) — error distributions per condition type; **off-support degradation**: sweep conditions from historical-typical to counterfactual extremes, report battery-pass-rate and adherence as functions of distance from support. The bootstrap runs this suite too — its structural inability to honor novel conditions becomes measured evidence, not an aside.
- **calibration.py** *(new)* — rolling-origin probabilistic calibration on train+validation: PIT histograms and interval coverage at 1y and 5y horizons for factor aggregates. Cheap here; gives Step 5 a baseline.
**Metric MC error:** every ensemble-level metric reports a Monte-Carlo error bar via ensemble subsampling; `pre-registration.yaml` will set minimum ensemble sizes per tier such that MC error ≪ band width.
`battery.py` emits `BatteryReport` (JSON+markdown) with battery version, prereg hash, system id, vintage id — and, where an acceptance filter was applied upstream, **both filtered and unfiltered results**.
*Acceptance:* all metric unit tests pass; battery runs on the Step-0 toy engine end-to-end in CI.

### WP2.2b — Negative controls: validating the battery itself
`negative_controls.py` registers deliberately broken generators: **NC1** iid Gaussian with matched means/covariance (kills tails/clustering — monthly tier must fail it); **NC2** temporally shuffled real data (kills dynamics — ACF/horizon tiers must fail it); **NC3** mean/vol-shifted bootstrap (drifted marginals — bands must fail it); **NC4** memorizer replaying training decades with noise (memorization tier must fail it); **NC5** condition-ignoring generator (conditional tier must fail it). A test asserts each control fails at least its designated tier at enforce level. This suite is the battery's own validation record and is cited in `G2-EVIDENCE.md`.
*Acceptance:* all five controls rejected; a report table shows which tier caught which control.

### WP2.3 — Pre-registration (sealing thresholds, protocols, and the judging code) — **must merge before WP2.5**
Populate `pre-registration.yaml` from WP2.2's train+val reference statistics: per-metric acceptance bands and severity (`enforce|report`), horizon tier, minimum ensemble sizes (from MC-error analysis). Also frozen here: D4 strategy-set definitions; holdout dates; the bootstrap benchmark's full spec (block-length distribution, stationary form, stratification = Step-1 regime ruleset version); the ablation system list; **the campaign vintage id**; **the tuning protocol** (WP2.8); **the severe-test protocol** (WP2.11): identical architectures and hyperparameters to the primary runs, refit/retrain only, no fresh search on the reduced sample; **the multi-seed decision rule in words**: ≥3 seeds per neural system; promote only if the challenger beats `bootstrap-v1` on the tail tier in *every* seed (or, pooled, by more than the cross-seed dispersion), with no enforce-tier regression on monthly/horizon tiers, memorization below floor, zero constraint violations; conditional-tier results reported alongside but not gating promotion (recorded rationale: the platform's purpose weighs conditioning, but historical tail fidelity remains the falsifiable criterion — revisit at G3).
`prereg.seal()` hashes the YAML **plus the source of every enforce-tier metric plus `g2.py`** into `pre-registration.lock`; `prereg.verify()` runs at every battery/G2 invocation. Amendments only via the machine-checked log.
*Acceptance:* modified YAML or modified enforce-metric code with a stale lock fails loudly; amendment log round-trips.
*Human gate:* merges only after the D6 workshop ratifies (or with provisional values pre-authorized in the amendment log).

### WP2.4 — The benchmark: regime-stratified stationary block bootstrap
Per the sealed spec: multivariate blocks (never per-factor resampling), geometric lengths, regime(+slow-state-bucket) stratification, WorldSpec conditioning (sequence pins the stratification path; unconditional samples historical regime frequencies). Register `bootstrap-v1`.
*Acceptance:* battery + conditional suite run; marginals match history; seeded reproducibility; becomes the standing comparison for every later PR.

### WP2.5 — Layer 1: the climate model
numpyro per DN-1.1 §II.2: five-state vector, dynamics equations, Taylor-type anchor, mixed-frequency observation fusing annual JST with the monthly panel, priors from config. NUTS diagnostics (R-hat, ESS, divergences, posterior predictive checks) → generated `climate-fit-report.md`. `simulate.py`: draws (θ, s₀) per decade — parameter uncertainty inside the ensemble, asserted by test. **All normalization train-only** (recompute the demeaned CAPE here on train span; test against full-sample leakage explicitly).
*Acceptance:* convergence on the real panel; plausible slow-state ranges/half-lives; deterministic artifact load.

### WP2.6 — Layer 2: the semi-Markov regime skeleton
Six states; NegBin sojourns and transition rows logit-linked to slow-state covariates; fitted on Step-1 `regime_ruleset_v1` labels (+NBER), ruleset version recorded. Sampling conditioned on slow states; WorldSpec modes (sequence/transition_matrix/unconditional); emits the cycle term for L1's anchor and L3's conditioning. **Sensitivity run:** refit under a variant labeling ruleset (`regime_ruleset_v1b`, thresholds perturbed) and report regime-dependent battery metrics under both — defuses the label-circularity concern with evidence.
*Acceptance:* simulated duration/frequency distributions inside train+val bootstrap bands (measured by the battery); sequence mode exact; sensitivity report generated.

### WP2.7 — Layer 4: waypoints, bridging, reconciliation, support monitoring (before L3; tested with bootstrap blocks)
`waypoints.py`: annual waypoints from L1/L2 + WorldSpec `factor_conditions` applied as overrides/tilts (the single binding point for authored worlds). `bridge.py`: block assembly, overlap cross-fade in state space, conditioning-vector construction, guidance hook (stubbed). `support.py` *(new)*: distance of each conditioning vector from the training conditioning distribution (Mahalanobis on the encoder features + regime-frequency check); per-decade **extrapolation share** logged into ensemble metadata and surfaced as a battery report line — conditional generators fail quietly off-support, so the interface is instrumented, not trusted. `reconcile.py`: Denton benchmarking to annual waypoints + floor re-application; **adjustment magnitude returned as a diagnostic** with its distribution reported per system. `assemble.py`: the 7-step algorithm; acceptance filter ≤10%, every rejection logged, and **filter metrics restricted to a named subset disjoint from all enforce-tier metrics** (asserted by test against the prereg manifest) — the filter may not teach to the exam; battery reports filtered and unfiltered.
Test all of L4 with bootstrap blocks as the stand-in generator (this is ablation system C's machinery, free).
*Acceptance:* waypoint tolerance met; deliberately inconsistent waypoints/blocks produce large, flagged reconciliation; filter/enforce disjointness test green; support diagnostic populates.

### WP2.8 — Layer 3a: conditional diffusion + the tuning protocol
`data.py`: overlapping L-month blocks (L=6 default) with regime, slow-state snapshot, trailing-12m summary, waypoint-increment targets; **train-only standardization**; block-aware validation splits (no straddling); effective-sample correction via subsampled epochs — never quote raw counts. `constraints.py`: softplus-space rates/spreads with floors, log-space prices — violations structurally impossible. `losses.py`: generative objective + tail elicitability auxiliary on the D4 set (λ in config). `diffusion.py`: EDM-style, temporal U-Net/transformer, cross-attention conditioning. `tuning.py` *(new — the forking-paths record)*: hyperparameter search on validation folds only, **capped trial budget stated in pre-registration**, every trial logged (config hash, fold scores) to the experiment store; final config selected by a pre-stated criterion; no post-holdout tuning of anything, ever. `train.py`: deterministic seeding, hashed checkpoints, early stopping on a validation battery subset.
*Acceptance:* trains in single-GPU budget; constraints exact; tuning log complete and within budget; monthly-tier neighborhood check on validation.

### WP2.9 — Layer 3b: the flow-matching variant (co-primary)
`flow.py`: conditional flow matching / rectified flow behind the identical interface, sharing data/constraints/losses/training/tuning. Bake-off harness: same data, seeds, conditioning, compute budget; report quality **and** sampling cost (NFE, wall-clock per 10k decades). Optionally activate the guidance hook for waypoint conditioning; evaluate as a joinery ablation with Denton retained as guarantee.
*Acceptance:* both samplers through one entry point; like-for-like bake-off table.

### WP2.10 — Assemble systems, run the ablation (multi-seed)
`systems.py`: **A** structure-only (L1+L2+Gaussian residuals), **B** neural-rollout (L3 chained, no waypoints), **C** neural-only (L3 blocks + naive chaining, no L1), **D** full hierarchy (`hier-diffusion-v1`, `hier-flow-v1`), **E** `bootstrap-v1`. Neural systems: ≥3 training seeds each; deterministic systems: ≥3 sampling seeds. Full battery (all tiers, filtered+unfiltered, support and reconciliation diagnostics) on the frozen campaign vintage; `ABLATION.md` generated with cross-seed dispersion shown per metric.
*Acceptance:* complete multi-seed reports for every system; tables generated, not hand-assembled.

### WP2.11 — The G2 gate: severe test, one-shot holdout, decision, disposition
Run the **severe test under its pinned protocol**: exclude the 1970s, refit L1/L2 and retrain L3 with the *frozen* architectures/hyperparameters, regenerate from the 1965 climate state, compare 1966–84 behavior via the horizon tier — result written up either way. Then the **one-shot holdout evaluation** through the explicit-purpose path — once, logged, never repeated. `g2.py` executes the sealed multi-seed rule and emits `G2-EVIDENCE.md`: per-criterion arithmetic with MC error bars, cross-seed consistency, the ablation table, negative-control citation, conditional-tier results (reported, non-gating, with the sealed rationale), support/reconciliation diagnostics, severe-test outcome, verdict. Model cards for every system into `governance/model-inventory.yaml` (owner, version, training vintage, checkpoint hashes, seeds, validation evidence, known limitations — including the **signature-variant deferral note**: DN-1.1's small-data tool is deferred because Step 2's panel is data-dense; it re-enters at Step 3's sparse strategy sleeves; registered id reserved). Tag `v0.2.0-g2`.
*Acceptance:* the verdict is produced by executing the sealed rule; a SHIP-BENCHMARK outcome leaves `bootstrap-v1` as the default generator_id and says so plainly.

## 4. PR sequence, compute, estimates
2.1 → 2.2 → 2.2b → **2.3 (sealed)** → 2.4 → 2.5 → 2.6 → 2.7 → 2.8 → 2.9 → 2.10 → 2.11. WP2.5/2.6 may run parallel to 2.7 after 2.4. Compute: L1 NUTS = CPU hours; L3 = single-GPU days per sampler **per seed** (≥3 seeds — budget accordingly; seeds can run sequentially overnight); 10k-decade ensemble = minutes once trained. Shape: ~6–8k LOC src + tests; ~5–7 weeks of focused sessions, WP2.8–2.10 dominating.

## 5. Explicit non-goals
Factor→strategy mappings, cashflows, TA calibration (Step 3); institutional twin (Step 3); artifacts/world bible/LLM (Step 4); decision-evaluation walk-forward (Step 5 — splits defined here); signature variant (reserved id; Step 3 re-entry per the deferral note); multi-country generation.

## 6. Foreseeable pitfalls (read before coding)
**Leakage remains the whole game**, and v1.1 closes the four known channels structurally: holdout guard (2.1), train+val-only references (2.2), train-only normalization (2.5, 2.8), and the seal over thresholds *and judging code* (2.3). Treat any new data path as a suspected fifth channel. **Overlapping blocks** inflate effective samples — subsampled epochs, block-aware splits, corrected counts only. **Denton can flatter a weak generator** — adjustment magnitude is a reported distribution per system; large means disagreement, and disagreement is a finding. **The acceptance filter** may not touch enforce-tier metrics (tested) and its effect is visible via filtered/unfiltered reporting. **Training-seed lottery** — the multi-seed rule exists because one seed's victory is noise; do not argue with it at G2 time. **Off-support conditioning fails silently** — the support diagnostic is the tripwire; investigate extrapolation shares above the prereg threshold before believing conditional results. **Small-n decade metrics** — bands or it didn't happen. **GPU determinism** — document per model card, assert within stated tolerance. **The temptation at G2** — if the challenger loses, shipping the bootstrap with an honest write-up is a successful outcome of this step; the plan was built so that either verdict is publishable.

## 7. Relationship to gates and decisions
Discharges Gate G2. Consumes D3 (architecture + frozen benchmark; sampler bake-off resolves DN-1.1's open item), D4 (tail objective + strategy set), D5 (state-space floors as WP2.8 coordinates), D6 (sealed thresholds — now including protocols, budgets, and judging-code hashes), D9's splits (holdout named, guarded, spent once). Produces: the generator plugin Step 3 consumes; the battery-with-negative-controls that becomes the standing acceptance harness; model cards and `G2-EVIDENCE.md` for the independent reviewer, whose review of the sealed pre-registration *before* training (WP2.3 human gate) is itself part of the effective-challenge record.
