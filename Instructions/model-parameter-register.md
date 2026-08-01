# Model Parameter Register — What Must Be Compiled, and From Where

*Companion to the Data Requirements Register v1.1 and the Albourne Derived-Measures Spec · v1.0-r · reconstructed July 2026. Purpose: enumerate every parameter the platform must estimate, choose, or receive as input — starting with the Takahashi–Alexander cashflow model — with its source, units, and default. This is the checklist that turns the data layer into working models.*

> **Reconstruction status.** The v1.0 original was authored 28 July 2026 and exists only in that session's transcript. §0, §1, §9 and §10 are recovered verbatim. §2–§8 are rebuilt from the register's own summary, the Step 3 work-package plan, and the sleeve/vehicle spec; they preserve the parameter set and the kind/source discipline but the wording is new. **Verify §2–§8 against the original before treating this as the frozen artifact.** Appendix A carries amendments that accrued after v1.0 and have not yet been ratified into the register.

---

## 0. How to read this

Every parameter carries a **kind**, which determines who is responsible for it:

| Kind | Meaning | Who owns it |
|---|---|---|
| **E** — Estimated | Fitted from data; has a standard error; changes when the data vintage changes | Quant researcher |
| **C** — Chosen | A modeling decision, defensible but not estimable; belongs in the decision register and the robustness grid | D-workshop, then config |
| **I** — Institution input | Supplied per world/institution by the user or the WorldSpec | Product / user |
| **W** — World-conditional | Set by the scenario; the counterfactual switch | Compiler → WorldSpec |

**Sourcing shorthand:** `ALB-A/B/C/D/E` = Albourne derived-measure groups per the spec; `PANEL` = the Step-1 factor panel; `PUB` = public documents (consultant/industry reports, cited); `INST` = the institution's own data; `LIT` = literature default.

---

## 1. Takahashi–Alexander core (the six, per strategy)

The classic deterministic model. Per period *t* (years since first close), with commitment **CC** and paid-in capital **PIC**:

- Capital call: `Call(t) = RC(t) × [CC − PIC(t−1)]`
- Distribution: `Dist(t) = RD(t) × [NAV(t−1) × (1 + G)]`
- Distribution rate (the "bow"): `RD(t) = Y × (t / L)^B`
- NAV roll-forward: `NAV(t) = NAV(t−1) × (1 + G) + Call(t) − Dist(t)`

*(Verify the exact functional form and terminal-year liquidation convention against the original paper during implementation; several published variants differ in how the final year is forced to zero NAV.)*

| Symbol | Parameter | Kind | Units | Source | Default / note |
|---|---|---|---|---|---|
| **CC** | Commitment | I | currency | INST / world | Per fund or per vintage line in the pacing plan |
| **RC(t)** | Rate of contribution schedule, by fund age | E | % of unfunded per year | **ALB-A item 1** (call rate on unfunded, by age) | Estimate the full age curve, not a 3-point schedule; store as a vector with p25/p75 |
| **G** | Annual NAV growth (net) | E→W | %/yr | ALB-A item 4 + ALB-D (TVPI by age); becomes market-linked in §2 | Constant G is the *benchmark* tier only |
| **L** | Fund life | E/C | years | ALB-A item 5 (time-to-breakeven, terminal age), ALB-D | Typically 10–14; strategy-specific; include extension behavior |
| **B** | Bow factor | E | dimensionless | **ALB-A item 2** (distribution rate on NAV by age) — fit B to the empirical curve | The bow *is* the empirical distribution-rate profile; do not adopt a literature default when data exist |
| **Y** | Yield / terminal distribution rate | E | % of NAV per year | ALB-A item 2 (level of the curve at maturity) | Fitted jointly with B |

**Estimation note.** With ALB-A in hand, four of the six are estimated rather than assumed. The empirical distribution-rate-by-age curve *is* the bow, so B and Y are fitted jointly to it rather than adopted from a paper, and RC(t) becomes a full age curve with quartile bands instead of the traditional three-point schedule.

---

## 2. Market-sensitive extension (D7 tier 1) — seven more per strategy

*Reconstructed.* This is where the TA model stops being deterministic and starts responding to the generated world. It is also where the calibration burden sits.

| Symbol | Parameter | Kind | Units | Source | Note |
|---|---|---|---|---|---|
| **β_G** | Growth beta to the public factor path | E | dimensionless | De-smoothed strategy returns on PANEL | Estimated on de-smoothed series only — smoothed marks understate beta (D1) |
| **α_G** | Growth intercept | E | %/yr | Same regression | Carries the strategy's unexplained return; sanity-check against ALB-D |
| **λ_G** | Growth lag | E/C | quarters | Same regression | Private marks lag public moves; this is distinct from the smoothing kernel and must not double-count it |
| **k_D(·)** | Exit-market multiplier on the distribution rate | E | dimensionless | **ALB-B** (calendar-time rate series) | Function of the exit-market state (equity drawdown + HY spread per D7) |
| **k_C(·)** | Call-rate multiplier | E | dimensionless | ALB-B | See Appendix A.2 — the public evidence says this is near-flat for buyout |
| **σ_ε** | Residual cashflow dispersion | E | %/period | Residuals from the above; quartile bands ALB-A/D | Currently the weakest-evidenced parameter on the public route |
| **ρ_ε** | Cross-strategy residual correlation | C | dimensionless | Chosen, with sensitivity grid | No data source supplies this; document as C and vary it |

**Boundary rule.** `k_D` and `k_C` are the D7 content. WP3.9 (liquidity spine) runs with both set to unity; Step 3 turns them on. A RunRecord must disclose which.

---

## 3. Structural fund parameters — all kind C

*Reconstructed.* None of these is estimable from a derived-measures panel; all are chosen, documented, and carried in the sensitivity grid. Their aggregate effect on net outcomes is large enough that "chosen" must not mean "unexamined."

| Parameter | Units | Note |
|---|---|---|
| `mgmt_fee_rate` | %/yr | With the **basis change** at the end of the investment period — commitment basis → invested-capital basis. Getting this wrong flatters late-life net returns |
| `fee_basis_state` | enum | Which basis is currently in force |
| `carry_rate` | % | |
| `hurdle` | %/yr | |
| `catch_up` | % | |
| `waterfall_type` | enum | Deal-by-deal vs whole-fund — materially different timing of carry crystallisation |
| `recycling_rate` / `recallable_balance` | % of distributions | R14 in the Step 2R register; a first-class schema field, not a footnote |
| `subscription_line_deferral` | quarters | Deferred by decision in the WP3.9 line of work; parameter reserved |
| `extension_behavior` | years + trigger | Interacts with `L`; the tail of a fund life is where pacing plans break |

---

## 4. Vehicle mechanics parameters

*Reconstructed.* Per the sleeve/vehicle spec's three vehicle types.

**Open-ended (HF):** `notice_days`, `lockup_remaining`, `gate_pct`, `redemption_frequency`, `side_pocket_share` — kind I where the institution's actuals exist, otherwise C from Albourne metadata norms by strategy. Gating base rates from **ALB-F**.

**Evergreen / semi-liquid:** `redemption_cap_pct_per_period` (e.g. 5%/quarter), `notice`, `queue_policy` — kind C, anchored to vehicle documents and PUB. The 2022–23 open-ended real estate queue episode is the reference calibration.

**Realizable liquidity by horizon:** the 30/90/180-day realizable fractions are derived from the above, not independently parameterised.

---

## 5. De-smoothing and forward-smoothing parameters

*Reconstructed.* D1 governs the method; this register holds the fitted objects.

| Parameter | Kind | Source | Note |
|---|---|---|---|
| `desmoothing_method` | C | D1 enum | GLM MA(2) per sleeve, MLE-fit, is the recommended default; Geltner AR(1) and the regime-aware variant are robustness axes |
| θ weights per sleeve | E | Step 1 / WP2R.2 | The same weights drive the forward smoothing kernel in WP3.3 — **one kernel, inverted, never two** |
| Smoothing frequency per vehicle type | C | Sleeve/vehicle spec | Quarterly lag closed-end, monthly HF, vehicle-specific evergreen |

---

## 6. Generator parameters

Not enumerated here. The generator's parameters are governed by D2–D6 and live in the WorldSpec, the pre-registration seal, and the generator output schema. This register's only claim on them is the **factor namespace**, since every `β_G` and every `k_D(·)` is expressed in generator output space and breaks silently if the namespace moves.

---

## 7. Portfolio and policy parameters

*Reconstructed.* Kind I for an institution, C for the generic Phase-A portfolio.

| Parameter | Kind | Note |
|---|---|---|
| Annual commitment rate per sleeve | I / C | In Phase A a generic fixed schedule; in Step 3 a **decision variable**, which is the point |
| Spending rate | I / C | Applied to a trailing twelve-quarter average of **reported** total value — reported, not true |
| Smoothing window for the spending rule | C | Twelve quarters default |
| Rebalancing rule and bands | I / C | |
| `transaction_cost_bps` per liquid sleeve | C | |
| Shortfall-resolution hierarchy | C | Cash → liquid sales per policy → secondary sale |
| Forced-secondary haircut | C | Two-state (normal / stressed) from PUB in Phase A; state-dependent function in Step 3 |
| Private-weight target and breach bands | I | Drives the denominator narrative |

---

## 8. Institutional twin parameters (Step 3, WP3.8)

*Reconstructed.* DB pension first; endowment as the near-zero-cost special case.

Member cohort structure; benefit rules; salary and pension increase assumptions; mortality with improvement; discount curve construction; contribution policy (fixed / funding-linked / statutory recovery); rate and inflation hedge ratios; collateral pool with haircuts, posting rules and headroom; leverage where used. Kind I throughout for a real client, C for the demonstration institution.

Proxy-model parameters (LSMC-style, per Krah et al.) are model artifacts rather than register entries, but the **capital-region definition** — worst 1% funding outcomes — is a register entry, because the acceptance bound is stated against it.

---

## 9. Gap table — what Albourne supplies vs what must be assumed

| Need | Covered by | If unavailable |
|---|---|---|
| Age-indexed call/distribution rates | ALB-A | Industry aggregates from consultant reports; wider priors |
| Calendar-time rate series (market linkage) | ALB-B | **This is the critical one** — without it, D7 reverts to literature betas and the 2022 test cannot be run properly |
| Age×calendar surface | ALB-C | Neural cashflow tier deferred; TA tiers unaffected |
| Vintage dispersion | ALB-D | Public vintage benchmark quartiles |
| Episode cuts | ALB-E | Reconstruct approximately from B if delivered with sufficient history |
| Fee/carry/recycling/sub-lines | Not a data question | Chosen parameters + sensitivity grid; document as C |
| Secondary pricing function | PUB only | Public reports are adequate; cite them |
| Fund-level cashflows | Not available | Dispersion sampling from A/D bands substitutes |

---

## 10. Minimum viable parameter set (to build the market-sensitive TA tier and pass the 2022 test)

Per strategy: **RC(t), B, Y, L** from ALB-A; **β_G, α_G, λ_G** from de-smoothed returns on PANEL; **k_D(·)** from ALB-B; **σ_ε** from residuals; fee/carry/recycling as chosen defaults with a stated sensitivity range; secondary pricing as a two-state function (normal / stressed) from public reports. Everything else in this register is refinement — valuable, but not on the critical path to a working, testable cashflow layer.

---

## Appendix A — Amendments pending ratification

These arose after v1.0 and currently have nowhere to land. They are recorded here as **proposed**, not ratified; folding them in makes this v1.1 and should be a deliberate act with a changelog entry.

**A.1 · The public/panel calibration split (WP3.10 §7.4).** Every linkage parameter now carries a `linkage_version` discriminator: `public-0.1` (Robinson–Sensoy elasticities, public base rates) or `panel-1.0` (Albourne recalibration, institutional tier only). The register's source column is therefore two-valued for §2, and any RunRecord discloses which calibration produced it. This is what keeps the H2 licence question off the M4 critical path.

**A.2 · `k_C` is near-flat, and the earlier prior was wrong (WP3.10 §4.1).** Buyout crisis-period calls were about unchanged through the GFC; venture calls rose. `f_call` should be close to flat with a modest positive P/D loading, not a slowdown-then-acceleration shape. The register's default for `k_C` must reflect this.

**A.3 · Provisional public-source values, ⛔P-A closed (WP3.10 §5).** `dist_rate_normal ≈ 25%` of NAV p.a.; trough ≈ 11–14%; depth ≈ 0.45–0.55 of normal; duration ≈ 3 years near trough. Implemented through elasticities (+0.37 on log P/D, −0.30 on the log spread for buyout), not as a scripted path — with the reproduction check as an acceptance test rather than a calibration adjustment.

**A.4 · Provisional coverage thresholds, ⛔P-B closed (WP3.10 §5).** Unfunded/NAV ≈ 0.5 steady state, 0.6–0.8 elevated, >1.0 distress. Headline metric is unfunded/NAV; the **warning trigger** computes against unfunded/liquid, which is the ratio that actually binds.

**A.5 · No crisis regime term (WP3.10 §4.2).** Smooth monotone functions of P/D and the spread are sufficient; a crisis dummy adds no explanatory power. This removes a class of regime-override parameters that would otherwise have appeared in §2.

**A.6 · Empirical anchor for the bow (WP3.10 §4.5).** Net cash flow crosses zero at 3–4 years, rises to about year eight, flat thereafter. This calibrates `B` and `L` directly and should be stated as the estimation target for §1.

**A.7 · WP3.9 §9 freeze list.** `RC`, `L`, `B`, `Y`, annual commitment rate per sleeve, spending rate, smoothing window, forced-secondary haircut — the Phase-A generic defaults, documented as generic and not representative of any institution. These are the same symbols as §1 and §7 with `k_D = k_C = 1`; register them as a named parameter *set*, not as duplicate entries.

---

## Appendix B — Provenance of this reconstruction

Recovered verbatim: §0, §1 (including the equations, the six-parameter table and the estimation note), §9, §10.
Rebuilt from the register's own summary and adjacent artifacts: §2–§8. The parameter *names* in §2 are recovered (β_G, α_G, λ_G, k_D, k_C, σ_ε, plus cross-strategy residual correlation); their units, kinds and notes are reconstructed.
Not recovered: any worked default values the original may have carried in §2–§8, and the original's section numbering between §2 and §8 — this reconstruction imposes its own.

---

*Not investment advice. Generic parameters; not representative of any institution.*
