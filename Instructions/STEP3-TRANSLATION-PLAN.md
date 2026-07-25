# STEP3-TRANSLATION-PLAN.md — Factors → Strategies → Cashflows → Portfolio → Twin
## Implementation plan for Claude Code · Step 3 (WS-C + WS-D) · completes Gate G1, runs to Gate G3

**Prerequisite:** `v0.3.0-contracts` (Step 2R) — sleeve/vehicle schema, generator-output schema, and taxonomy all frozen. **Companion docs to vendor:** `sleeve-vehicle-state-spec.md`, `model-parameter-register.md`, `albourne-derived-measures-spec.md`.

**Mission.** Turn generated factor paths into what an investor actually experiences: strategy returns (true and reported), fund cashflows, portfolio liquidity, and a funded institutional balance sheet. **No LLM, no artifacts, no actors** — Step 4 owns those. This step completes the engine half of Gate G1 (the 2022 reproduction) and supplies the decision surface Steps 4 and 5 depend on.

### Definition of done (Gate G3 engine portion)
1. `ah run --world X --with-portfolio` produces, per path: strategy returns (true + reported), cohort cashflows, portfolio state, and institution state — all schema-valid and RunRecord-pinned.
2. The **2022 episode reproduces end-to-end**: public drawdown → stale private marks → private-weight breach → distribution drought → pacing stress → (where triggered) forced sale at a state-dependent discount. Reproduction scored against the episode pack, pass/fail pre-stated.
3. Cashflow tier 1 (market-sensitive TA) **beats or matches** the transparent benchmark tier (historical simulation) on episode reproduction, or the result is reported honestly.
4. Twin proxy models pass **capital-region validation** (worst-1% funding outcomes) within pre-stated error bounds.
5. Every parameter in `model-parameter-register.md` is either estimated with diagnostics, chosen with a recorded rationale and sensitivity range, or explicitly marked out-of-scope.
6. Hero funds exist and are numerically consistent with their cohort aggregates (Step 4 prerequisite).
7. Coverage ≥85% on `ah/port/` and `ah/twin/`; full suite green.

---

## Work packages

**WP3.1 — State implementation.** Implement the frozen sleeve/vehicle schema as runtime objects: closed-end cohort, open-ended HF sleeve, evergreen vehicle, liquid sleeve, portfolio, institution. Pure state + transitions, no I/O. Property tests: values non-negative, weights sum to one, unfunded never negative, recallable balance bounded.

**WP3.2 — Factor → strategy mappings.** Per sleeve: loadings on the frozen factor set, estimated on **de-smoothed** series; regime-varying or structural-break treatment (decide and document); residual volatility and cross-sleeve residual correlation. Mapping diagnostics: in-sample fit, stability across regimes, out-of-sample check on the validation span, and a comparison of smoothed-vs-de-smoothed betas (the D1 exhibit). *Guard:* mappings are estimated on train+validation only — the holdout remains untouched until Step 5.

**WP3.3 — Forward smoothing model.** The inverse of Step 1's de-smoothing: given true strategy returns, produce the reported marks an investor sees, per vehicle type (quarterly lag for closed-end, monthly for HF, vehicle-specific for evergreen). Uses the θ weights estimated in Step 1/2R. *Test:* de-smooth(smooth(x)) ≈ x within tolerance; reported series exhibit the serial correlation observed in history.

**WP3.4 — Cashflow tier 1: market-sensitive Takahashi–Alexander.** Per cohort: RC(t), B, Y, L from ALB-A; market-linked growth (β_G, α_G, λ_G); exit-market multiplier k_D and call multiplier k_C from ALB-B; residual dispersion. Plus the structural parameters: fees with basis change, carry with waterfall type, hurdle and catch-up, **recycling/recallable**, **subscription-line call deferral**, extension behavior. Emit calls, distributions (income vs capital), NAV, and the full performance metric set (TVPI/DPI/RVPI, IRR, PME against the generated public path).

**WP3.5 — Cashflow tier 0: the transparent benchmark.** Historical-simulation cashflows (assumption-free: replay observed rate profiles by age from ALB-A/C), plus classic constant-G TA. These are what tier 1 must beat; freeze their specification before tier 1 is tuned.

**WP3.6 — Vehicle mechanics.** HF: notice periods, lockups, gates (with base rates from ALB-F), side pockets, and the **realizable-liquidity-by-horizon** calculation. Evergreen: redemption caps, queues that lengthen under stress, expected-time-to-exit. *Test:* stress scenarios produce queue extension and gating at rates consistent with the 2022–23 open-ended real estate reference episode.

**WP3.7 — Portfolio engine.** Cash account; commitment plan and pacing rules; rebalancing with **transaction costs**; the shortfall-resolution hierarchy (cash → liquid sales per policy → secondary sale at the state-dependent discount) with the **forced-sale flag** as a headline output; private-weight breach detection against ranges; portfolio fee-drag aggregation. *Test:* a deliberately over-committed institution in a crisis path produces forced sales; a well-buffered one does not.

**WP3.8 — Institutional twin (DB pension first).** Liability cashflow projection from member cohorts, benefit rules, salary/pension increases, mortality with improvement; discount curve construction; funding ratio and surplus; contribution policy (fixed / funding-linked / statutory recovery); **hedge ratios** for rates and inflation and the **collateral pool** with haircuts, posting, and headroom; leverage where used. *Test:* a rate shock moves liabilities and collateral in the directions and magnitudes an actuary would expect; an under-hedged plan shows funding volatility dominated by the liability side.

**WP3.9 — Proxy models for interactivity.** LSMC-style neural proxies for liability PV under rate/inflation states, with the discipline from Krah et al.: separate fitting and validation scenario sets, and dedicated test points in the **capital region** (worst 1% funding outcomes). Portfolio metrics run direct. *Acceptance:* proxy error inside pre-stated bounds in the capital region specifically, not merely on average.

**WP3.10 — Hero funds.** Three to five synthetic individual funds per world, sampled from cohort distributions using the dispersion parameters, with names bound to the World Bible cast. Their aggregate must reconcile to the cohort totals (a test). This is Step 4's prerequisite: manager letters need numbers behind them.

**WP3.11 — The 2022 end-to-end reproduction (Gate G1 completion).** Wire the episode pack to a full run: score the reproduction against pre-stated criteria (drawdown magnitudes, mark-lag length, weight-breach timing and size, distribution shortfall, secondary pricing). Produce `G1-EVIDENCE.md` covering both data and engine halves.

**WP3.12 — Neural cashflow tier (conditional).** Only if ALB-C (age×calendar matrices) arrived: a macro-conditioned sequence model for call/distribution rate surfaces, evaluated against tiers 0 and 1 on the same episodes. If ALB-C did not arrive, record the deferral and move on — tier 1 is sufficient for G3.

---

## Sequencing, non-goals, pitfalls
**Order:** 3.1 → 3.2/3.3 → 3.5 (benchmark first, per the standing rule) → 3.4 → 3.6 → 3.7 → 3.8 → 3.9 → 3.10 → 3.11 → 3.12. **Non-goals:** artifacts, actors, live mode, decision evaluation (Step 5 — but its metric definitions are frozen here). **Pitfalls:** mapping betas estimated on smoothed data (the whole point of Step 1 — assert de-smoothed inputs in code); cashflow parameters tuned on the same episodes used to validate them (freeze the episode criteria first); fee/carry modeled on gross returns when the data are net (double-counting — check the Albourne metadata); liability projections that silently assume a static membership; proxy models validated on average error rather than in the capital region; and the temptation to make tier 1 beat tier 0 by tuning rather than by structure.
