# Sleeve & Vehicle State Specification — v1.0-r

*Companion to the Model Parameter Register and the Data Requirements Register v1.1. Defines the strategy taxonomy, the three vehicle types, the state each carries, the flows between them, and the granularity switch (sleeve → cohort → synthetic fund). Step 3 builds against this contract.*

> **Reconstruction status.** The v1.0 original was authored 28 July 2026 and exists only in that session's transcript. §1 (status note, private-markets table, scope decision), §2, §3, §4, §5 and §6 are recovered verbatim or near-verbatim. §1.1's hedge-fund table is recovered with two rows partially truncated in the source and completed from the surrounding text — check those. §7 is recovered for items 1–3 only; item 4 and any beyond it are lost. **Verify before treating this as the frozen contract, since WP2R.3 freezes a schema against §3.**

---

## 1. Taxonomy layer

**Status note — read first.** The strategy lists below are a *candidate* taxonomy assembled from standard industry classification. Albourne's own classification is proprietary and must be taken from the scope inventory (already a week-1 action in the data register). The design principle: the platform's `sleeve_id` namespace is **its own**, with an explicit `albourne_code → sleeve_id` mapping table populated on delivery. Never hard-code a vendor's taxonomy into model code; map it at the boundary. This also means a taxonomy change is a mapping-file change, not a refactor.

### 1.1 Hedge fund strategies (candidate breadth)

| Group | Strategies | Vehicle type | Notes for modeling |
|---|---|---|---|
| Equity | Fundamental long/short; quantitative equity; sector specialist; equity market neutral | Open-ended | Beta to equity factors varies hugely by sub-strategy — model separately, not as one sleeve |
| Event driven | Merger arbitrage; special situations; activist; distressed securities | Open-ended | Distressed overlaps private credit; document the boundary |
| Relative value | Fixed income arbitrage; convertible arbitrage; volatility arbitrage; capital structure arbitrage | Open-ended | Leverage-sensitive; funding-spread factor matters |
| Credit | Long/short credit; structured credit; specialty finance | Open-ended / hybrid | Some vehicles are drawdown-structured — vehicle type is per-fund, not per-strategy |
| Macro | Discretionary macro; systematic macro | Open-ended | Often the crisis diversifier — validate that behavior explicitly |
| Managed futures | Trend-following; non-trend/short-term | Open-ended | Convex payoff profile; check crisis-conditional correlation |
| Multi-strategy | Platform multi-strat; internal allocators | Open-ended | Pass-through leverage; redemption terms often the tightest |
| Insurance-linked | Cat bonds; collateralized reinsurance; ILS multi-strat | Open-ended / side-pocket heavy | Near-zero market beta, event-driven tails; side pockets are the norm not the exception |
| Commodities | Discretionary; systematic commodity | Open-ended | Distinct from CTA trend |

### 1.2 Private markets strategies (candidate breadth)

| Group | Strategies | Vehicle type | Cashflow modeling |
|---|---|---|---|
| Private equity | Large buyout; mid-market buyout; small buyout; growth equity; venture (early); venture (late) | Closed-end | Full TA; bow varies materially by sub-strategy |
| Secondaries | PE secondaries; credit secondaries; GP-led/continuation | Closed-end | **Faster J-curve, earlier distributions** — separate TA parameters, not a buyout clone |
| Private credit | Senior direct lending; unitranche; mezzanine; opportunistic/special situations; distressed for control; specialty/asset-backed finance; venture debt | Closed-end + evergreen | Income-heavy distributions; split income vs capital return |
| Real estate | Core; core-plus; value-add; opportunistic; RE debt | Evergreen (core) + closed-end (VA/opp) | Core is typically open-ended — a genuinely different vehicle |
| Infrastructure | Core; core-plus; value-add; greenfield/development; infra debt | Evergreen + closed-end | Long lives; extension behavior matters |
| Natural resources | Energy; mining/metals; timberland; agriculture | Closed-end | Commodity factor exposure explicit |
| Niche/royalties | Pharma royalties; music/media royalties; litigation finance | Closed-end | Low correlation claims — validate, don't assume |
| Multi-manager | Fund-of-funds; co-investment vehicles | Closed-end | Fee layering; call/distribution profile differs from direct funds |

*Modeling scope decision (D2/D7 workshop): which of these become modeled sleeves versus aggregated. Recommend 8–10 PM and 7–9 HF sleeves for v1; the taxonomy above is the full namespace, not the v1 build list.*

---

## 2. The three vehicle types

Vehicle type is a property of the **fund/cohort**, not the strategy — a credit strategy can be offered in all three wrappers.

| | **Closed-end drawdown** | **Open-ended NAV** | **Evergreen / semi-liquid** |
|---|---|---|---|
| Capital in | Capital calls against unfunded commitment | Subscription at dealing date | Subscription, possibly queued |
| Capital out | Distributions (income + capital) | Redemption subject to notice/lockup/gate | Redemption subject to queue, cap (e.g. 5%/quarter), gate |
| Life | Finite (L years + extensions) | Perpetual | Perpetual |
| Marks | Quarterly, smoothed, lagged | Monthly, smoothed (HF smoothing is real) | Quarterly/monthly, smoothed, plus queue-dependent realizability |
| Key risk modeled | Liquidity demand (calls) and drought (distributions) | Gating, side pockets, realizable-vs-stated liquidity | **Queue risk** — exit denied precisely when wanted |
| Typical strategies | Buyout, VC, closed-end credit, VA/opp RE | Most HF | Core RE, open-ended infra, evergreen PE/credit, BDCs, interval funds |

**Why evergreen deserves first-class treatment:** it is where much of the recent capital has gone, and its failure mode is distinct from both others — a redemption queue that lengthens in stress, converting a "liquid" allocation into a locked one without any formal gate being declared. Modeling it as "core RE = a sleeve with a return series" loses the entire lesson.

---

## 3. State objects

### 3.1 Closed-end cohort (or synthetic fund — same object, `n_funds = 1`)

```
identity:      sleeve_id, vintage_year, vehicle_type, cohort_id, n_funds,
               fund_name (nullable — populated for narrative "hero funds")
commitment:    committed, paid_in, unfunded, recallable_balance
value:         nav_true, nav_reported, cumulative_distributions
lifecycle:     age_years, contractual_life L, extension_status
performance:   tvpi, dpi, rvpi, irr_to_date, pme (vs generated public path)
parameters:    RC(t) curve, B, Y, G-linkage (β_G, α_G, λ_G), k_D, k_C, σ_ε,
               quartile_draw (for dispersion when synthetic)
fees:          mgmt_fee_rate, fee_basis_state, carry_rate, hurdle,
               catch_up, waterfall_type, accrued_carry
flows (per q): calls, distributions_income, distributions_capital,
               nav_growth, fees_paid, carry_crystallized
```

### 3.2 Open-ended HF sleeve (or individual synthetic fund)

```
identity:      sleeve_id, vehicle_type, fund_name (nullable)
value:         nav_true, nav_reported
terms:         notice_days, lockup_remaining, gate_pct, redemption_frequency,
               side_pocket_share
liquidity:     realizable_30d, realizable_90d, realizable_180d, gated_flag,
               gated_share, queue_position (if applicable)
flows:         subscriptions, redemptions_requested, redemptions_paid,
               return_true, return_reported, fees, performance_fee_crystallized
```

### 3.3 Evergreen / semi-liquid vehicle

```
identity:      sleeve_id, vehicle_type, fund_name (nullable)
value:         nav_true, nav_reported
terms:         redemption_cap_pct_per_period, notice, queue_policy
queue:         pending_redemption_amount, queue_age_periods, fulfilled_pct_history
liquidity:     realizable_this_period, expected_time_to_full_exit
flows:         subscriptions, redemptions_requested, redemptions_fulfilled,
               return_true, return_reported, income_distributed
```

### 3.4 Liquid sleeve (equities, bonds, credit, commodities, REITs)

`value, weight, target_weight, return, transaction_cost_bps` — deliberately simple; these are the funding source for everything above.

---

## 4. Flow mechanics per period

1. **Returns applied**: liquid sleeves from generated factors; private/HF sleeves from strategy mappings (true), then the smoothing model produces reported marks.
2. **Closed-end cohorts**: calls and distributions computed per TA with market-linked parameters; fees and carry accrue; NAV rolls forward; recallable balance updates.
3. **HF and evergreen**: subscriptions/redemptions processed subject to notice, lockup, gate, or queue; unfulfilled redemptions roll forward and *lengthen the queue*.
4. **Cash account**: receives distributions, income, redemption proceeds; pays calls, subscriptions, fees, benefits/spending.
5. **Shortfall resolution**: if cash is insufficient — sell liquid sleeves per a stated policy hierarchy; if still short, secondary sale at the state-dependent discount; record forced-sale flag (a headline metric, not a footnote).
6. **Aggregation**: sleeve totals → portfolio value → weights vs targets → breach flags → private weight vs denominator (from the twin).

---

## 5. Granularity switch

| Mode | Unit | When | Data need |
|---|---|---|---|
| **Sleeve** | strategy aggregate | Fast ensembles, early phases | Strategy returns only |
| **Cohort** | strategy × vintage | **Default from Step 3** — required for TA | ALB-A/B profiles |
| **Synthetic fund** | individual fund | Phase 3; plus "hero funds" early | + dispersion (ALB-A quartiles, ALB-D vintage quartiles) + assumed intra-vintage correlation |

Same state object across modes; `n_funds` and a `dispersion_draw` are the only differences. **Hero-fund exception:** 3–5 synthetic funds per world, named to match the World Bible cast, simulated individually from Phase 2–3 onward so that manager letters and gating events have real numbers behind them (required for the artifact layer's numeric-fidelity gate).

---

## 6. Data and parameter requirements by component

| Component | Needs | Source |
|---|---|---|
| HF strategy returns | Monthly, per strategy, longest history | Albourne (primary), HFRI cross-check |
| HF de-smoothing | MA weights per strategy | Run in Step 1 — HF smoothing is real (GLM was built on HF data) |
| HF liquidity terms | Notice, lockup, gate, side-pocket norms by strategy | Albourne metadata + INST actuals; gating base rates from ALB-F |
| PM strategy returns | Quarterly, per strategy | Albourne |
| PM cashflow profiles | RC(t), B, Y, L per strategy | ALB-A |
| PM market linkage | β_G, λ_G, k_D, k_C | ALB-B + generated factors |
| Dispersion (for synthetic funds) | Quartile bands, intra-vintage correlation | ALB-A/D; correlation is a **chosen** parameter with sensitivity |
| Evergreen queue behavior | Redemption caps, historical fulfillment in stress | Vehicle documents + PUB; 2022–23 open-ended RE fund queues are the reference episode |

---

## 7. Open decisions for the workshop

1. **v1 sleeve list** — which of §1's namespace becomes modeled (recommend 8–10 PM, 7–9 HF).
2. **Evergreen treatment** — first-class vehicle type (recommended) or approximate as open-ended with a haircut.
3. **Secondaries as sleeve** — model buying secondaries as its own strategy with its own TA parameters (recommended) as distinct from selling stakes.
4. *[Item 4 and any subsequent items were not recovered. Reconstruct from the workshop record or re-derive.]*

---

## Appendix — Amendments arising since v1.0

Recorded as **proposed**, not ratified.

**AM-1 · Public-source calibration path.** WP3.10 supplies `f_call` and `f_dist` from Robinson–Sensoy (2016) for the public engine, with the Albourne panel reserved for the institutional tier. §6's source column is therefore two-valued for the PM linkage row; the discriminator is `linkage_version`.

**AM-2 · Phase-A subset.** WP3.9 runs the §3.1 object with market-linkage coefficients at zero and a single synthetic cohort per sleeve. This is a *subset*, not a prototype — the same state object, the same recursions, coefficients off.

**AM-3 · Commitment as a decision variable.** Later work established that commitment is a per-sleeve decision rather than an exogenous schedule, which makes vintage cohorts structural rather than deferrable. §5's "Cohort — default from Step 3" is therefore firmer than v1.0 stated it.

**AM-4 · Work-package numbering collision.** The Step 3 plan of 28 July assigns WP3.9 to proxy models, WP3.10 to hero funds and WP3.11 to the 2022 end-to-end reproduction. The 29 July work packages assign WP3.9 to the liquidity spine and WP3.10 to linkage estimation. Two different documents currently claim the same two numbers. Resolve before either is cited in a gate evidence pack.

---

*Not investment advice.*
