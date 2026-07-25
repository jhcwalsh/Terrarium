# DN-4 · Jurisdiction Scope and the Institution Plugin

*Design note · July 2026 · Decisions J1–J8. Written to unblock coding: §7 lists what to build this week, §2 flags the one thing that must be settled before the Step-2 pre-registration seal.*

---

## 1. Why this is urgent rather than interesting

The twin's discount basis is **built from generated factors**. A UK scheme discounts on gilts and indexes on RPI/CPI; a US plan discounts on a high-quality corporate curve. If the factor set sealed at Step 2's pre-registration contains only US rates and inflation, a UK twin is not merely unbuilt — it is *unbuildable* until the battery is re-sealed.

So this decision sits upstream of code you are about to write, not downstream of it. It is the same coupling as the FX item (R5), and the two should be resolved in one sitting.

## 2. The unlock: factor **blocks**, not a monolithic factor set (J2)

Rather than choosing one jurisdiction's factors and living with it, structure the factor set as blocks:

| Block | Contents |
|---|---|
| **Global** | Equity market/size/value/momentum, commodities, credit spreads (IG/HY), equity vol state |
| **US** | Policy rate, 2y/10y Treasury, CPI, HQM corporate curve, funding spread |
| **UK** | Bank Rate, nominal gilt curve, **real gilt curve**, RPI, CPI |
| **EUR** (later) | Policy rate, Bund curve, HICP |

Pre-register the battery **per block**, so adding a block adds thresholds rather than amending existing ones. Honest caveat: cross-block correlation tests *are* new joint tests, so adding a block is an additive amendment — which is exactly what the amendment log exists to record, and far cheaper than re-sealing everything.

This converts jurisdiction from an architectural commitment into a configuration choice, which is what you want given that the commercial answer may not be the technical one.

## 3. Candidate institutions

| | **UK DB** | **US DB** | **US endowment** | **NL fund** | **Insurer** |
|---|---|---|---|---|---|
| Liability side | Gilts + margin; TPR funding code; multiple bases | ERISA/PPA; HQM/segment rates | None — spending rule | Wtp transition; UFR | Solvency II; matching adjustment |
| Hedging character | **Leveraged LDI, collateral waterfalls** | LDI, less levered | n/a | Sophisticated, high hedging | Extensive |
| 2022 episode | **Gilt crisis: collateral calls → forced selling** | Rates up, funding improved; denominator effect | Denominator effect | Similar to UK, less levered | Rate-driven |
| Free validation series | **PPF 7800 index** (monthly aggregate funding, 2003–) | Milliman 100 PFI (monthly) | NACUBO (annual) | DNB statistics | Limited |
| Data cost | Free (BoE curves, ONS); CMI mortality via IFoA | Free (FRED, HQM, SOA) | Free | Free | Free-ish |
| Complexity | High | High | **Low** | High + regime in flux | Highest |

## 4. Recommendation (J1)

**UK DB as the flagship v1 twin; US endowment retained as the trivial special case; US DB as v2.**

The reasoning is that the UK is where your distinctive machinery actually earns out. Hedge ratios and the collateral pool (retrofit R6) are optional decoration for an endowment and central for a UK scheme. The 2022 gilt crisis is the single best-documented instance of the exact cascade the platform models — a rate shock triggering collateral calls, forcing sales of whatever is liquid, breaching private-asset ranges on stale marks, and pushing schemes into the secondary market. Reproducing it end-to-end would be a far more distinctive Gate-G3 claim than reproducing the US denominator-effect story alone. The PPF 7800 index gives you a free monthly aggregate funding-ratio series back to 2003 to validate against, and the endgame decisions UK schemes face right now — run-on versus buyout, and the pacing of illiquid assets against a buyout horizon — are live, expensive, and under-served by existing tools.

The endowment stays because it costs nothing: it is a jurisdiction plugin with no liability model, and it keeps the existing prototype and the thin-slice rule alive. US DB follows because it reuses perhaps 80% of the UK machinery with different plumbing.

**The one caveat worth taking seriously:** this is partly a commercial question. If your relationships and pipeline are US, invert the order — the architecture below makes that a configuration change rather than a rebuild, which is the entire point of specifying it this way.

## 5. The design insight that shapes the code: funding is a *set* of numbers (J4)

A twin that tracks one funding ratio misses the actual decision problem. UK schemes simultaneously track technical provisions, low-dependency, buyout, and accounting (IAS 19) bases. US plans track the ERISA funding target, the PBGC premium basis, and ASC 715. **Which basis binds** — and how the gaps between them move under a scenario — is frequently the decision, not a reporting detail.

So `funding_metric` returns a mapping of basis → {liability PV, funding ratio, surplus}, with the jurisdiction plugin declaring which bases exist and which triggers attach to which.

## 6. The plugin interface (the thing to build)

```
InstitutionProfile          # one per jurisdiction × institution type
├── liability_model         # member cohorts → projected benefit cashflows
├── discount_bases          # {basis_id: (factor path → discount curve)}
├── mortality_basis         # base table + improvement projection
├── indexation_rules        # RPI/CPI/capped/none, by benefit tranche
├── funding_metrics         # → {basis_id: {pv, ratio, surplus}}
├── regulatory_constraints  # contribution triggers, recovery plans, levies
├── hedging_instruments     # available instruments + collateral eligibility/haircuts
└── endgame_options         # buyout pricing, PRT, run-off (J8)
```

Everything above the line is jurisdiction-specific; **everything else in the twin is generic** — portfolio engine, cashflow engine, liquidity cascade, decision surface. Get that boundary right and the second jurisdiction is a week, not a quarter.

## 7. What to code this week

1. **Resolve J2/J3 before the Step-2 seal.** Restructure the factor manifest into blocks; decide whether the UK block enters now (recommended if J1 is UK) or is deferred with the additive-amendment cost documented. Resolve FX (R5) in the same sitting.
2. **Add the UK block to the Step-1 data layer** if J1 is confirmed: BoE nominal/real/inflation curves, ONS RPI/CPI/CPIH, FTSE gilt indices, PPF 7800 (as a validation series, not a factor). All free, all connector-shaped like the existing FRED work.
3. **Write `InstitutionProfile` as an interface now**, even though Step 3 implements it — so no Step-3 module hard-codes a discount curve or a single funding ratio. Same discipline as the narrative-blindness guarantee: enforce structurally, not by convention.
4. **Make `funding_metric` return a mapping from day one.** Retrofitting multi-basis into scalar-shaped code touches every call site.
5. **Register the 2022 UK gilt-crisis episode pack** alongside the existing 2022 US episode. Two different 2022s, two different lessons, and the UK one exercises the collateral machinery.

## 8. Decisions J1–J8

| # | Decision | Recommended default | Blocks |
|---|---|---|---|
| **J1** | Flagship jurisdiction and institution type | UK DB; endowment as special case; US DB v2 | Step 3 twin |
| **J2** | Factor-set architecture | Blocks with per-block pre-registration | **Step 2 seal** |
| **J3** | Which blocks in Step 2 | Global + US + UK | **Step 2 seal** |
| **J4** | Funding metric shape | Set of bases, jurisdiction-declared | Step 3 twin |
| **J5** | Mortality sourcing | CMI/S3 via IFoA membership (UK); SOA free (US) | Step 3; fractional actuary owns |
| **J6** | Validation targets | PPF 7800 (UK), Milliman PFI (US) | Step 3 acceptance criteria |
| **J7** | Currency and FX treatment | Resolve with R5; base currency per institution, hedge ratio as a portfolio variable | Step 2R |
| **J8** | Endgame/buyout modeling | Defer to v1.1; expose the hook in the interface now | Step 3 scope |

---

*Two things to note about this note. First, it deliberately makes jurisdiction a plugin rather than a decision you can only make once — because the commercial answer may arrive after the technical one. Second, J2 and J3 are on the critical path for a seal you are days away from; everything else here can wait a fortnight without cost.*
