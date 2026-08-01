# WP3.10 — Cashflow Linkage Estimation
## Public-source calibration and the Albourne upgrade template

*Draft v0.1 · July 2026 · Supplies `f_call` and `f_dist` for WP3.9 v0.2, and closes ⛔P-A and ⛔P-B with provisional public-source values. Companion §7 specifies exactly what data would strengthen each parameter, in a form that keeps the public engine free of licensed inputs.*

---

## 1. Purpose and the licence constraint

WP3.9 needs the market linkage of call and distribution rates estimated, not judged. Estimating it on the Albourne panel would embed derived parameters from licensed data into the **public** product, which is the H2 data-licence question already flagged three times in the programme plan and would move it onto the M4 critical path.

**The split adopted here:** Phase A calibrates on public sources. The institutional tier recalibrates on the panel, client-resident, where the governance already exists. This keeps Path B clean, and it lets the methodology note make a claim worth having — *the public engine is calibrated on public data and independently reproducible.*

---

## 2. The primary source

Robinson & Sensoy (2016, *JFE* 122:3) is close to purpose-built for this. Quarterly cash flows, 837 buyout and VC funds, 1984–2010, ~$600bn committed, taken <cite index="20-1">directly from a large limited partner's internal accounting system and therefore free of the self-reporting and survivorship biases affecting standard commercial databases</cite>. Allocator-side, not manager-reported — the same quality argument as the Albourne panel, in the public domain.

Their specification is almost exactly ours: predictive regressions of calls and distributions on lagged market conditions, with fund-age fixed effects. Age plus market state, which is `(age, S_t)`.

**The conditioning variables map cleanly onto D2.** They use log price/dividend on the S&P and the log Moody's Baa–Aaa spread, orthogonalised to P/D. Our equity block gives the first, our IG credit block the second. No new factor is required — a real convenience, and it means `f_call` and `f_dist` are expressible directly in generator output space.

---

## 3. The evidence

**Base rates.**

| Quantity | Value | Source |
|---|---|---|
| Buyout call rate | <cite index="20-1">10–15% of unfunded commitments called per quarter, consistent with capital deployed over a 2–5 year window</cite> | R&S Fig. 3 |
| VC call rate | Higher than buyout in early life | R&S Fig. 3 |
| Buyout distributions, boom | <cite index="20-1">Around 5–6% of committed capital per quarter through the buyout boom, collapsing to near zero after the crisis</cite> | R&S Fig. 4 |
| Buyout distributions / NAV, normal | <cite index="29-1">Averaged 29% annually across 2014–2017</cite> | Bain 2025 |
| Buyout distributions / NAV, trough | <cite index="29-1">Fell to 11%</cite> | Bain 2025 |
| European trough and rebound | <cite index="26-1">Bottomed at 13.7% in early 2024 and recovered to 24.3% by year-end</cite> | PitchBook |

**Elasticities.** Log-log, fund-age fixed effects, predictive (conditioning variables lagged one quarter):

| | ln(P/D) | ln(Baa–Aaa) |
|---|---|---|
| Buyout distributions | **+0.37** | **−0.30** |
| Buyout calls | **+0.33** | **−0.08** |
| VC distributions | **+1.38** | **−0.62** |
| VC calls | **+0.82 to +0.90** | **−0.19 to −0.27** |

Buyout call and distribution elasticities look similar, but <cite index="20-1">because distributions are much larger on average than calls, distributions have a substantially higher sensitivity to P/D despite comparable elasticities</cite>. Net cash flow is procyclical, and the funds are liquidity sinks when valuations are low.

**The crisis episode**, 2007Q3–2009Q1, age fixed effects only:

| | Buyout | VC |
|---|---|---|
| Net cash flow | **−1.27%** of committed per quarter | −1.10% |
| Distributions (log) | −0.34 | −0.80 |
| Calls (log) | **−0.07, not significant** | **+0.47, significant** |

---

## 4. Five findings that change the design

**4.1 A correction to my earlier prior — calls did not fall.** I told you deployment slows for two to four quarters in stress. That is wrong for buyout at the aggregate level: <cite index="20-1">buyout crisis-period calls were about the same as in normal times, while venture calls actually rose, possibly to exploit depressed asset values and the absence of other funding for small businesses</cite>. The self-funding breakdown is therefore driven almost entirely by the distribution side. `f_call` should be close to flat, with a modest positive P/D loading — not a slowdown-then-acceleration shape.

**4.2 No crisis regime is needed.** <cite index="20-1">Once the macro variables are included, the crisis indicator loses significance in every specification except venture capital calls</cite> — crisis-period behaviour is explained by the same fundamentals that explain normal times. Smooth monotone functions of P/D and the spread are sufficient. This removes a whole class of regime-override machinery from WP3.9, and is the single most useful design finding in the paper.

**4.3 Age dominates macro, by an order of magnitude.** <cite index="20-1">Fund age and calendar-quarter fixed effects together explain only 7.9% of buyout net-cash-flow variation, of which age fixed effects alone account for 7.2%; adding market variables in place of time effects brings the total only to 7.4%</cite>. Two consequences: the cohort stack is doing most of the work and was the right structural call, and the linkage must be presented as a modest systematic tilt rather than a dominant driver.

**4.4 The 92% idiosyncratic share is not a problem for us — but the reason must be stated.** At fund level almost all variation is idiosyncratic. A portfolio holds many funds across many vintages, so most of that diversifies away and the systematic component is what survives to portfolio level. This is precisely why a portfolio simulator can use a linkage with a 7% R², and it belongs in the methodology note before a reviewer raises it.

**4.5 The bow has an empirical anchor.** <cite index="20-1">Net cash flow starts negative, crosses zero at about three to four years of fund age, rises monotonically to about year eight, and is roughly flat thereafter</cite>. That shape calibrates `B` and `L` directly rather than by assertion. Separately, <cite index="20-1">funds that have called less capital for their age call more going forward</cite>, which validates drawing calls off the unfunded balance.

---

## 5. Provisional parameter values

### ⛔ P-A — distribution drought, now provisionally closed

```
dist_rate_normal    ≈ 25% of NAV per annum        (Bain 29% 2014–17; PitchBook 24.3% end-2024)
dist_rate_trough    ≈ 11–14% of NAV per annum     (Bain 11%; PitchBook 13.7%)
depth               ≈ 0.45–0.55 of normal
duration            ≈ 3 years at or near trough, gradual recovery
```

Implemented through the elasticities rather than as a scripted path: `f_dist` with a +0.37 loading on log P/D and −0.30 on the log spread reproduces roughly this magnitude under a 2022-shaped episode. **Verify that it does** — if the fitted function does not reproduce the observed trough, the functional form is wrong, and that check is an acceptance test rather than a calibration adjustment.

VC and growth carry roughly 3–4× the buyout elasticity. Private credit is materially less cyclical, since <cite index="28-1">the self-liquidating nature of loans has stabilised distributions</cite> — but no public elasticity exists for it (§6).

### ⛔ P-B — coverage thresholds, provisionally closed

Unfunded / NAV:

| Band | Level | Anchor |
|---|---|---|
| Steady state | **≈ 0.5** | <cite index="31-1">A useful rule of thumb is that half of an asset owner's private equity commitment is awaiting a capital call — for a 30% PE allocation, 15% of the portfolio</cite> |
| Elevated | **0.6–0.8** | Harvard, Sept 2008: $11bn unfunded against $18bn illiquid NAV ≈ 0.61 |
| Distress | **> 1.0** | <cite index="30-1">At Yale, Princeton and Columbia, illiquid allocations plus unfunded commitments exceeded 100% of total endowment value</cite> |

**One caveat on your choice of denominator.** Unfunded/NAV is the right headline — it is what appears in IC packs. But the binding constraint in 2008 was unfunded against *liquid* assets, which is what MPI uses in its endowment work, and it is the ratio that actually determines whether you are forced to sell. Recommend showing unfunded/NAV as the headline and computing unfunded/liquid as the warning trigger. The two diverge exactly when it matters.

---

## 6. What the public route cannot give

Stated plainly, because these are the gaps §7 is designed to fill.

| Gap | Consequence |
|---|---|
| **Buyout and VC only** | No elasticities for private credit, real estate, infrastructure, secondaries or natural resources. Currently these must be scaled from buyout by judgement — the weakest link in the calibration |
| **Sample ends 2010** | Covers the GFC but not 2022–25, which is the flagship episode. Base rates are patched from Bain and PitchBook; elasticities are not |
| **Fund-level, US-centric** | No LP-portfolio-level coverage dynamics; over 85% US funds |
| **No dispersion** | Point elasticities only, so the cross-sectional spread of call and distribution behaviour cannot be calibrated — the residual model in the cashflow layer is presently guesswork |
| **Aggregate distribution rates are survey- or vendor-sourced** | Bain and PitchBook figures are not reproducible from primary data |

---

## 7. The Albourne calibration interface — the upgrade template

**Design rule: derived measures only.** Every field is a ratio in an aggregated cell. No fund identifiers, no manager names, no fund-level series. This is what makes the interface transportable under Path A governance and is the same discipline as the derived-measures specification.

### 7.1 Cell definition

```
sleeve          buyout | growth | venture | direct_lending | opportunistic_credit
                | re_core | re_valueadd | infrastructure | nat_resources | secondaries
age_bucket      0–1y | 1–2y | 2–3y | 3–5y | 5–7y | 7–10y | 10y+
period          calendar quarter
region          US | Europe | UK | RoW
```

Minimum cell population applies; cells below it are suppressed rather than reported.

### 7.2 Fields

| Field | Definition | Fills |
|---|---|---|
| `call_rate` | Calls ÷ opening unfunded | `RC_base` per sleeve; replaces the buyout 10–15% proxy |
| `call_rate_p25/p75` | Cross-sectional quartiles | **Dispersion — nothing public supplies this** |
| `dist_rate` | Distributions ÷ opening NAV | `Y`, and the drought depth per sleeve |
| `dist_rate_p25/p75` | Cross-sectional quartiles | Dispersion |
| `net_cf_rate` | (Distributions − calls) ÷ committed | Direct check on the self-funding property |
| `nav_growth` | NAV change ex-flows | Cross-check against the WP3.2 sleeve return |
| `n_cells` | Count | Weighting and suppression |

### 7.3 Derived series the calibration consumes

| Series | Why it beats the public route |
|---|---|
| `dist_rate` by sleeve × age × quarter, 2000–2026 | Elasticities for every sleeve, and the 2022–25 episode at quarterly granularity |
| `call_rate` by sleeve × age × quarter | Confirms or refutes finding 4.1 outside buyout and outside the GFC |
| Quartile spreads on both | Calibrates cashflow residual dispersion — currently unfounded |
| LP-level `unfunded / NAV` distribution over time | Turns P-B from three anecdotes into a distribution with percentiles |
| Recallable proportion of distributions | Deferred by decision, but capture the field now — it is not recoverable later |

### 7.4 Governance

Calibration runs where the data sits; only fitted coefficients travel, and only into the institutional build. The public engine keeps its §5 public-source coefficients, and the two are versioned separately — `linkage_version = public-0.1` and `linkage_version = panel-1.0` — so any RunRecord discloses which calibration produced it. The H2 question is then confined to the institutional tier, where the answer is already understood.

---

## 8. Acceptance

| Test | Expectation |
|---|---|
| Episode reproduction — GFC | Fitted `f_dist` under 2008-shaped conditions reproduces the observed distribution collapse |
| Episode reproduction — 2022 | Reproduces a trough of roughly 11–14% of NAV, persisting about three years |
| Call flatness | `f_call` under buyout parameters shows no material stress decline, per finding 4.1 |
| No regime term | Adding a crisis dummy to the fitted model adds no significant explanatory power |
| Lifecycle | Modelled net cash flow crosses zero at 3–4 years and plateaus around year 8 |
| Steady-state coverage | Constant pacing converges to unfunded/NAV ≈ 0.5 |

The first two are the real tests. Everything else can be right while the episode shape is wrong, and the episode shape is what the product shows.

---

## 9. References

Robinson, D. T. & Sensoy, B. A. (2016). Cyclicality, performance measurement, and cash flow liquidity in private equity. *Journal of Financial Economics* 122(3), 521–543. NBER WP 17428.
Takahashi, D. & Alexander, S. (2002). Illiquid alternative asset fund modeling. *Journal of Portfolio Management*.
Bain & Company, *Global Private Equity Report* 2023 and 2025.
PitchBook, European distributions as a share of NAV, 2024–25.
MSCI, *Private Capital in Focus: Depressed Distributions*, 2025.
MPI, endowment liquidity analyses, 2024–25.

Add Robinson–Sensoy to Zotero as a Tier-1 paper — it belongs in the literature-to-build map against D7, where the current entry cites only Takahashi–Alexander.

---

*Not investment advice. Public-source calibration; parameters are generic and not representative of any institution.*
