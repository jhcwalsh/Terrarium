# DN-5 — Factor → Sleeve Mapping Specification

*Draft v0.1 · July 2026 · Companion to DN-1.1, the Tier-1 decision register (D1–D10), and WP2.1b. Specifies the object that turns a generated factor path into an asset-class performance path. Sections marked ⚑ are decisions required before the Step 2 pre-registration seal.*

---

## 1. What this document is for

The engine generates **factors**. Users hold **sleeves**. Nothing currently written down says how one becomes the other, and three separate things depend on it:

1. **D4 tail objective.** The frozen benchmark-strategy set includes the endowment mix, which is specified in sleeve space. The tail loss cannot be computed without a mapping. *The mapping is therefore inside the pre-registration perimeter, one step ahead of its own build.*
2. **Phase A public product.** WP3.2–3.3 are pulled forward; asset-class performance ships with the public beta.
3. **The reported-vs-true toggle.** The product's most demonstrable feature is the *difference* between two mappings of the same factor path. That difference is the smoothing kernel specified in §5.

The mapping is not one object. It is three, and they fail in different ways:

```
factor path  ──▶ [ β · sparsity pattern ]  ──▶ systematic sleeve return
                          +
                 [ residual model ]        ──▶ TRUE sleeve return
                          ▼
                 [ smoothing kernel ]      ──▶ REPORTED sleeve return
```

Most of what follows is about the second and third boxes, because the first is the one everybody already knows they need.

**Status of the numbers below:** loadings are *structural priors* — they specify sign, rough magnitude, and which cells are forbidden. Point estimates come from the Step 1 de-smoothed panel. The decision to be ratified is the **pattern and the constraints**, not the values.

---

## 2. Factor blocks (restated from D2, WP2.1b block structure)

| Block | Factors | Nature |
|---|---|---|
| **B1 Equity** | MKT (global DM), SMB, HML, EM | Return factors |
| **B2 Rates** | Level (duration), Slope, Real rate | Return factors |
| **B3 Inflation** | Realised CPI, Breakeven | One return, one state |
| **B4 Credit** | IG spread change, HY spread change | Return factors |
| **B5 Real assets** | Commodity, REIT-orthogonal residual | Return factors |
| **B6 State** | Funding/liquidity, Vol regime, Exit-market state | **Conditioning only — never a linear loading** |

**B6 is the block that causes trouble.** It conditions the generator (DN-1 L2/L3) and it drives the cashflow tier (D7). The open question in §4.3 is whether it is also permitted to modulate sleeve betas. Under the v0 recommendation it is not, and §7 explains what that costs.

---

## 3. Sleeve taxonomy and the mapping pattern

Notation: **▪** pinned by construction (zero estimated degrees of freedom) · **●** estimated, unconstrained · **○** estimated, sign-constrained · **—** forbidden (structural zero) · **⟳** path-dependent, not a beta · **✦** event-layer driven.

### 3.1 Public plane — pass-through by construction

The generator already produces these. Re-estimating a beta of a sleeve on the factor that *is* that sleeve introduces error for no information.

| Sleeve | Construction |
|---|---|
| Global DM equity | ▪ MKT |
| EM equity | ▪ MKT + EM |
| Nominal govt (duration bucketed) | ▪ Level × modified duration, + Slope × key-rate weight |
| Index-linked | ▪ Real rate × duration, + Breakeven |
| IG credit | ▪ Level × dur + IG × spread dur |
| HY credit | ▪ Level × dur + HY × spread dur |
| Commodities | ▪ Commodity |
| Listed REITs | ▪ MKT + Level + REIT-orthogonal |
| Cash | ▪ Short rate |

Zero free parameters in this plane. ⚑ SM-2.

### 3.2 Hedge fund sleeves — contemporaneous, de-smoothed

Estimated on GLM MA(2)-corrected series (D1). Residual vols are annualised, post-de-smoothing.

| Sleeve | MKT | SMB | HML | Level | Slope | IG | HY | Cmdty | Resid σ | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Equity L/S directional | ○+ ~0.45 | ○+ | ● | — | — | — | ○+ | — | ~6% | Beta asymmetry is the known omission (§7) |
| Equity market neutral | ○ \|β\|≤0.15 | ● | ● | — | — | — | — | — | ~4% | Crowding events via ✦ |
| Event driven / merger arb | ○+ ~0.25 | — | ○+ | — | — | ○+ | ○+ ~0.20 | — | ~5% | Short-vol payoff; linear β understates deal-break tail |
| Distressed credit | ○+ ~0.35 | ○+ | ○+ | — | — | ○+ | ○+ ~0.55 | — | ~7% | |
| Credit L/S | ○+ | — | — | ○ | — | ○+ | ○+ ~0.35 | — | ~5% | |
| Fixed income RV | — | — | — | ○ | ● | ○+ | ○+ | — | ~4% | Funding state is the whole risk; linear map cannot see it |
| Discretionary macro | ● | — | — | ● | ● | — | ● | ● | ~7% | Low R² by nature; residual carries most variance |
| **Managed futures / CTA** | ⟳ | — | — | ⟳ | ⟳ | — | — | ⟳ | ~8% | **Not a regression.** See §3.4 |
| Multi-strategy | ○+ ~0.20 | — | — | ○ | — | ○+ | ○+ ~0.20 | — | ~4% | Funding state drives gating, not return |
| Insurance-linked | — | — | — | — | — | — | — | — | ~5% + ✦ | **Zero beta by construction**; jumps from the Hawkes layer |
| Quant equity MN | ○ ≈0 | ● | ● | — | — | — | — | — | ~4% + ✦ | Deleveraging cascades are events, not betas |

### 3.3 Private markets sleeves — lagged, then re-smoothed

Estimated on de-smoothed series against **contemporaneous** factors; the observed lag is reconstructed *forward* by the §5 kernel. This is the single most error-prone cell in the whole spec — see ⚑ SM-3.

| Sleeve | Primary loadings | Secondary | Lag source | Resid σ | Notes |
|---|---|---|---|---|---|
| Buyout | ○+ MKT ~1.1–1.3 | ○+ SMB, ○+ HML, ○− HY (financing cost) | Kernel | ~8% | Levered beta; HY sign is the financing channel |
| Growth equity | ○+ MKT ~1.3 | ○− HML | Kernel | ~11% | |
| Venture | ○+ MKT ~1.2 | ○− HML, B6 exit-state ✦ | Kernel (longest) | ~18% | Largest de-smoothing correction, least reliable. Flag in model card |
| Direct lending | ○+ HY ~0.35 | ▪ Level ≈ 0 (floating) | Kernel (short) | ~4% + ✦ | Credit losses are ✦ events, not residual noise |
| Opportunistic credit | ○+ HY ~0.60 | ○+ MKT | Kernel | ~7% | |
| Real estate core | ○+ REIT-orth ~0.6 | ○− Level, ○+ Realised CPI | **Appraisal cycle** | ~5% | Different smoothing mechanism to HF — §5.2 |
| RE value-add / opp | ○+ REIT-orth ~0.9 | ○+ MKT, ○− HY | Appraisal cycle | ~9% | |
| Infrastructure core | ○+ Realised CPI | ○− Level, ○ MKT low | Appraisal cycle | ~5% | |
| Natural resources | ○+ Commodity | ○+ MKT | Kernel | ~10% | |
| Secondaries | ○+ Buyout systematic | **B6 discount state** ✦ | Kernel (short) | ~7% | NAV discount widening is the 2022 mechanism |
| Co-investment | = Buyout systematic | — | Kernel | ~13% | Higher idio, no double fee (§6) |

### 3.4 The two sleeves that are not regressions

**Managed futures.** A CTA's payoff is convex and path-dependent; a linear beta on any factor reproduces neither the crisis-alpha profile nor the whipsaw losses that make the sleeve behave the way allocators experience it. Fitting one produces a sleeve that is quietly wrong in exactly the states the product is about.

*Specification:* the CTA sleeve is a **rule applied to the generated factor paths** — a 12-month time-series-momentum overlay across the B1/B2/B5 factor set, vol-targeted, with a transaction-cost drag. It consumes the generator output rather than a regression of it. This costs one small module and buys a sleeve that is right for structural reasons.

**Insurance-linked.** Zero systematic loading, with losses arriving from the Hawkes event layer. This is the cleanest possible demonstration that the two-layer event architecture is load-bearing rather than decorative, and it is worth keeping in Phase A for that reason alone.

---

## 4. What the pattern above encodes

Three constraints are doing real work and should be ratified explicitly rather than absorbed.

**4.1 Structural zeros are assertions.** A "—" claims the exposure does not exist. Most are safe (ILS has no equity beta). Some are conventions that a sceptical practitioner will test: fixed income RV has no equity loading *on average*, but in September 2008 it had a large one. The zero is a statement about the mean, and the tail is being delegated to the residual and event layers. Say so in the model card.

**4.2 Sign constraints plus shrinkage.** Sleeve panels are short and overlapping; unconstrained OLS will produce sign-flipped betas on some sleeve-factor pairs. Recommend sign constraints as tabled, plus shrinkage toward the block prior with intensity set by panel length. ⚑ SM-4.

**4.3 Betas are constant.** The B6 state block conditions the generator but does not modulate the mapping. This is the most consequential simplification in the document and §7 is about what it costs.

---

## 5. The smoothing kernel — the product feature

### 5.1 The consistency requirement

The forward smoothing operator applied to sleeve *i* must be **exactly the inverse of the D1 de-smoothing operator estimated for sleeve *i***. If it is not, then `reported` and `true` in the toggle are two different models rather than one model seen two ways, and the single most demonstrable idea in the product is quietly incoherent. This binds the mapping to `desmoothing_method` and it belongs in the WorldSpec as a paired version, not two independent ones. ⚑ SM-10.

### 5.2 Two mechanisms, not one

| Mechanism | Sleeves | Form |
|---|---|---|
| Return smoothing (GLM) | HF sleeves, private credit | MA(2) on true returns, MLE weights |
| Appraisal lag (Geltner) | Real estate, infrastructure | AR(1) partial adjustment on *levels*, tied to a valuation calendar |

Applying one form to all sleeves is the common shortcut and it produces real estate that reacts a quarter too fast.

### 5.3 State-dependent stickiness ⚑

Marks get stickier when markets fall. Appraisers anchor harder, GPs defer write-downs, and the gap between reported and true widens precisely in the drawdown. **A constant kernel understates the denominator effect** — which is the flagship narrative of the 2022 curated worlds *and* the acceptance criterion for the D7 cashflow tier.

*Recommendation:* one scalar stickiness parameter per smoothing family, increasing the lag weight as a function of the B6 drawdown state, calibrated on the 2021–2023 episode. It is a single number, it is defensible, and without it the two most important worlds in the launch library do not reproduce their own headline mechanic.

---

## 6. Fees ⚑

The mapping produces gross-of-fee sleeve returns. Someone must decide where net happens.

Decision alpha is *approximately* fee-invariant — the hold-course twin pays the same fees — so the growth-loop metric survives either choice. Level outcomes and the endowment-mix tail do not, and the D4 strategy set is defined on levels.

*Recommendation for v0:* deterministic net-of-fee sleeve returns — management fee drag plus a simple carry accrual on gains above a hurdle, no waterfall, no clawback. The full waterfall belongs with the Step 3 cashflow engine where the distribution schedule exists to support it. Freeze the v0 fee assumptions in the pre-registration; a tail threshold pre-registered on gross returns and evaluated on net is not a threshold.

---

## 7. The tension worth naming before it is discovered

**The generator is scored on tail fidelity in sleeve space, using a mapping that cannot produce tails.**

D4 evaluates VaR/ES on strategies including the endowment mix. Under a constant-beta linear mapping with symmetric residuals, every non-Gaussian feature of a sleeve's tail is inherited from the factor path. So:

- If the mapping is thin, the generator must carry the entire tail burden — and passing D4 becomes a statement about the *factors*, not about the asset classes the user actually holds.
- If the mapping is later enriched in WP3.2 with beta asymmetry and fat-tailed residuals, sleeve-level tails change materially **after** the seal, and the pre-registered thresholds no longer describe the shipped system.

Neither is acceptable silently. Three ways out, in order of preference:

1. **Freeze a deliberately thin mapping now, pre-register its thinness, and pre-register the sleeve-level tail battery as a *separate* Step 3 gate.** The D4 seal then honestly covers factor-space tails only, and sleeve-space tails get their own pre-registration when the mapping is real. Recommended.
2. Pull downside-beta asymmetry and t-distributed residuals into the v0 mapping so the sealed object resembles the shipped one. More faithful, but it moves estimation work in front of the seal and delays G2.
3. Define the D4 strategy set purely in factor space, dropping the endowment mix. Cleanest technically, weakest rhetorically — the endowment mix is the strategy the target buyer recognises, and losing it costs the tail objective its interpretability.

Option 1 with the drift note recorded against D4 per the literature-map §5.4 rule.

---

## 8. Where this spec runs out

**Currency.** D2 has no FX factor. v0 implicitly assumes fully-hedged or single-currency exposure. This is survivable for the US endowment segment and **not survivable for the UK**: DN-4 targets DB schemes, the gilt crisis is a named launch world, and a GBP-denominated scheme with unhedged global equity has an FX exposure that was one of the largest contributors to that episode's funding-level path. Either an FX block enters D2 before the seal, or the UK worlds ship with a documented limitation on a mechanic central to their own story. ⚑ SM-13 — **this is the item most likely to be regretted.**

**Manager dispersion.** No within-sleeve dispersion in v0 (per prior recommendation). Selection alpha would contaminate decision alpha as a headline metric.

**Vintage effects.** Private sleeves in Phase A are continuous exposures, not vintage cohorts. Cohort structure arrives with the Step 3 cashflow engine; nothing in Phase A should imply it exists.

**Illiquidity as a constraint.** The mapping produces returns, not tradability. Gating, lockups, and secondary-market discounts are consumption-layer objects. Worth stating so that the Phase A generic portfolio is not read as claiming rebalanceable private sleeves.

---

## 9. Decision register — SM-1 to SM-13

Recommended defaults given so this can be ratified rather than re-argued. Seal-blocking items must close before the Step 2 pre-registration.

| # | Decision | Recommendation | Ratify by | Code lands |
|---|---|---|---|---|
| **SM-1** | Sleeve taxonomy freeze; which sleeves are first-class in Phase A | Full taxonomy defined; Phase A ships public plane + 6 HF + 6 PM sleeves | **Seal** | **WP2.1b** (registry) → 2R (metadata) |
| **SM-2** | Public sleeves pinned pass-through vs estimated | Pinned. Zero free parameters | **Seal** | **WP2.1b** |
| **SM-3** | Lag convention: de-smooth-then-contemporaneous **or** reported-with-lagged-betas | De-smooth then contemporaneous; lag reconstructed forward by the kernel. **Never both** — the failure mode is a silent double lag | **Seal** | WP3.2 · *double-lag test written at WP2.1b, pending* |
| **SM-4** | Sign constraints and shrinkage intensity | Constraints as tabled; shrink to block prior, intensity ∝ 1/panel length | **Seal** | WP3.2 |
| **SM-5** | State-dependent (asymmetric) betas in v0 | **Out** of v0; in scope for WP3.2 with its own gate. See §7 | **Seal** | Post-Phase-A (own gate) |
| **SM-6** | CTA as rule-on-paths vs regression | Rule on paths, vol-targeted TSMOM overlay | 2R | WP3.2 — *unless the D4 endowment mix holds a CTA sleeve; then WP2.1b* |
| **SM-7** | ILS / QEMN wired to Hawkes event layer | Yes — cheapest proof the event layer is load-bearing | 2R | WP3.2 |
| **SM-8** | Residual distribution and cross-sectional correlation | Student-t, df ≈ 5; block correlation within style family and within PM asset type | **Seal** | WP3.2 · *v0 stub has no residual at all — see §11* |
| **SM-9** | Manager dispersion in Phase A | Out | 2R | Deferred, no Phase A code |
| **SM-10** | Forward kernel = exact inverse of D1 operator; paired versioning | Yes, enforced as a test not a convention | **Seal** | WP3.3 · *paired-version check at 2R* |
| **SM-11** | State-dependent mark stickiness | In — one scalar per smoothing family, calibrated on 2021–23 | **Seal** | WP3.3 |
| **SM-12** | Gross vs net; fee model scope | Net, deterministic drag + simple carry accrual. Pre-register on net | **Seal** | **WP2.1b** (drag) → WP3.2 (carry accrual) |
| **SM-13** | FX factor block | **Add to D2 before seal** or accept a documented UK limitation | **Seal** | **Step 2 proper** — factor block + retrain |

**Sequencing.** SM-1 → SM-3 → SM-4 is a strict chain. SM-5 and SM-8 jointly determine sleeve tail behaviour and must be taken together, not separately. SM-13 is the only item that reaches back into D2 and therefore has the longest lead time — take it first.

---

## 10. When each decision becomes code

Ratifying a decision and shipping its code are separate events, and conflating them is how a pre-registration ends up describing an object that was never executed. There are four code moments.

### C1 · WP2.1b — the thin mapping, before the seal

**Non-negotiable, because the D4 loss function calls it.** A tail threshold on the endowment mix cannot be computed from a document. What must be executable at the seal is the minimum that makes the D4 strategy set well-defined and nothing more:

- **SM-1** sleeve registry — names and identifiers only; the D4 strategies reference them
- **SM-2** public-plane transforms — identity, duration and spread-duration scaling. Cheap, and 60/40 and the endowment mix are mostly public sleeves
- **SM-12** deterministic fee drag — if thresholds are pre-registered on net, net must exist at pre-registration time
- Static de-smoothed betas for the HF and PM sleeves in the D4 mix, **zero residual, no smoothing, no dispersion**
- **SM-3** double-lag assertion, written now as a pending test so WP3.2 cannot land without satisfying it

Deliberately ugly. It exists to make a number computable, not to be believed. Tag it `sleeve_mapping_version = 0.1-preseal` and state in the pre-registration that it is residual-free — this is the honest form of §7 option 1, and it is what makes the D4 seal a claim about factor-space tails rather than an unmarked claim about sleeve-space ones.

### C2 · Step 2R — the contract layer

No modelling. Versioning, bindings, and the tests that keep the pieces honest:

- the five `*_version` fields in §11 into WorldSpec and RunRecord
- **SM-10** paired-version check: a kernel version that does not pair with its `desmoothing_method` fails the build
- **SM-1** full taxonomy metadata; **SM-6/7/9** recorded as ratified with their code deferred

### C3 · WP3.2–3.3 — the real mapping, inside Phase A

The bulk of the register. WP3.2 carries **SM-3** (estimation under the ratified convention), **SM-4**, **SM-6**, **SM-7**, **SM-8**, and the carry half of **SM-12**. WP3.3 carries **SM-10** and **SM-11**. This is where `sleeve_mapping_version` goes to 1.0 and supersedes the pre-seal stub — logged against **D4**, not against this note.

The sleeve-level tail battery is pre-registered *here*, before WP3.2 estimation begins, on the same terms as G2. It is a second pre-registration, and treating it as one is the whole substance of the §7 resolution.

### C4 · After Phase A

**SM-5** asymmetric betas with its own gate. **SM-9** dispersion. Vintage cohorts and illiquidity constraints with the Step 3 cashflow engine.

### The two that do not fit this shape

**SM-13 (FX)** is not a mapping change. It adds a factor block to D2, which means generator retraining and a G2 re-run. It is Step 2 proper, it is the most expensive item in the register, and its cost only rises after the seal. Take it first or accept the UK limitation explicitly — do not leave it undecided while Step 2 continues.

**SM-6 (CTA)** is conditionally seal-blocking. Check the D4 endowment mix: if it holds a managed-futures allocation, the thin stub cannot represent it, and the choice is to build the TSMOM overlay early or remove the sleeve from the mix. Worth resolving in the same sitting as the D4 strategy-set freeze.

---

## 11. WorldSpec bindings

Everything above surfaces as:

```
sleeve_mapping_version      # §3 pattern + estimated coefficients hash
smoothing_kernel_version    # §5, paired to desmoothing_method (D1)
fee_model_version           # §6
residual_model_version      # §8 distribution + correlation structure
sleeve_taxonomy_version     # SM-1
```

`sleeve_mapping_version` enters the RunRecord so any shared score resolves to the mapping that produced it. When WP3.2 supersedes the v0 mapping, the supersession is recorded against **D4** in the changelog, not against this note — the drift rule in the literature map §5.4 applies because the D4 tail thresholds were pre-registered under the superseded object.

---

*Not investment advice. Loadings are structural priors pending Step 1 estimation output; the object for ratification is the pattern and the constraint set.*
