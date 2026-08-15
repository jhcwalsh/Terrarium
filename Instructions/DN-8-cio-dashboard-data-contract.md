# DN-8 — CIO Dashboard Data Contract

*Design note · Draft v0.2 · August 2026 · Companion to `cioView.ts` and `terrarium-cio-dashboard.jsx` v0.3*

*Status: **ratified 2026-08-14** for the generic-portfolio tier — see Resolutions section. ⛔ O-3 resolved: conditions never ship.*

---

## 1. What this settles

The CIO dashboard is the institutional-tier surface described in the launch strategy §3 as "the institution plane". This note fixes the boundary between the engine and the screen so that the two can be built independently and so that nothing displayed to a CIO is computed anywhere except in the engine.

**The rule the whole note rests on:** the dashboard is a pure renderer. It formats, positions and colours. It does not compute a return, a weight, a ratio, a coverage figure, or a forecast. If a number appears on screen it appears in `CioView`, and the engine owns it.

This is not a style preference. Three things depend on it:

| Depends on | Why |
|---|---|
| **Replay guarantee (D-07)** | A screenshot is only replayable if every number on it derives from the RunRecord by a pure function. A ratio computed in the browser is outside the record. |
| **Plane discipline (DN-5 §3)** | Reported and true are engine states, not display modes. A UI that could compute a true-plane weight from reported inputs would be inventing the second plane. |
| **Evidence pack (M6)** | The model documentation pack must be able to say what produced each figure. "The front end divided two other figures" is not an answer a validator accepts. |

The component in its current form obeys this. `validateCioView()` is the enforcement.

---

## 2. Architecture

```
RunRecord ──► buildCioView(runRecord, { plane, asOfMonth, forecastQuarters })
                     │  pure, deterministic, no I/O
                     ▼
                  CioView ──► <CIODashboard view={…} onPlaneChange={…} />
```

**Determinism requirement.** Same RunRecord + same options ⇒ byte-identical `CioView`. No clocks, no locale, no random ordering of object keys where order is displayed. This is testable and belongs in the Step-4 test suite.

**Plane changes are a refetch, not a toggle.** `onPlaneChange` asks the host for a different payload; the component does not transform anything. Hosts on the public tier pass `planesAvailable: ["reported"]` and the control does not render.

**Optional blocks degrade, they do not break.** `markets` may be absent; `liquidity.sourcing`, `coverageDanger`, `performance.benchmark` may be absent. Each renders as omitted rather than as zero. `initialTab` allows deep-linking.

---

## 3. Field contract and provenance

Full types in `cioView.ts`. Provenance below — the second column is what has to exist before the block can be filled.

| Block | Fed by | Notes |
|---|---|---|
| `meta` | RunRecord header | `linkageVersion` and `decisionAlphaVersion` are rendered on screen. Not optional, per A2 §5. |
| `plan.history` | WP3.7 portfolio state, monthly | Plane-sensitive. `worldStartIndex` is the pre-history question, ⚑ O-1. |
| `allocation` | WP3.7 weights, WP3.3 smoothing | Plane-sensitive throughout. Goal mapping is a policy input, not an engine output — see ⚑ O-5. |
| `performance` | WP3.2 returns, twin engine for the benchmark | `benchmark` is the policy twin's path, so the twin must be running to populate it. |
| `liquidity.tiers` | WP3.7 weights + a tier mapping | The mapping is a policy input. ⚑ O-4. |
| `liquidity.forecast12m` | WP3.9 spine, WP3.10 linkage | Mechanical roll-forward. See §6. |
| `liquidity.sourcing` | WP3.9 §6 waterfall | Must reconcile to the gross outflow; the waterfall already produces the ordering. |
| `privateCashflows` | WP3.9 recursions, WP3.10 linkage, WP3.11 cohort model | Per-class series require the cohort model to resolve at class level. ⚑ O-6, ⚑ O-7. |
| `markets.returns` | WP3.2 factor paths | |
| `markets.conditions` | L1 macro states, L2 regime spine | ⛔ O-3 before this reaches any player-facing build. |
| `markets.correlations` | WP3.2 realised covariance | Window length is a display parameter and must be stated in `correlationNote`. |

### Conventions

| | Rule |
|---|---|
| **Percent** | Percentage points as numbers. `26.1`, not `0.261`, not `"26.1%"`. |
| **Ratio** | Fields typed `Ratio` are decimals: coverage `0.51`, call rate `0.070`. |
| **Money** | In `meta.unitLabel`. Default `$m`. The renderer promotes to `bn` above 1000. |
| **Signs** | `calls`, `distributions`, `payout`, `income` are **positive magnitudes**. The renderer applies direction. `net = distributions − calls`. Sending a negative call figure double-negates and the chart silently inverts. |
| **Missing** | `null`. Never `0`, never a short array. The renderer prints an em dash for `null` and `+0.0` for `0` — a zero where a null belongs is a plausible-looking lie, which is worse than a gap. The validator flags exact zeros in return arrays for confirmation. |
| **Order** | Arrays render in the order supplied. `allocation.classes` must be grouped in `allocation.goals` order; the donut walks them sequentially and will produce a scrambled ring otherwise. |

### Alert levels

Weights carry a band status: `ok`, `watch` (amber), `breach` (red). Rendered as a triangle beside the bar — filled for breach, hollow for watch, pointing up when above target and down when below — with the band's outer margin shaded amber inside the bar itself, a rim on the donut's outer ring, and a count in the panel header.

**Where the threshold lives matters.** A breach needs no parameter: `|dev| > band`, a comparison of two supplied figures, which the renderer may make. A *watch* needs a threshold, and a threshold is a parameter. So:

| Source | Precedence | Behaviour |
|---|---|---|
| `class.alert` / `goal.alert` | Wins | Engine states the level outright. Use for any rule richer than a threshold on current deviation — persistence across periods, direction of travel, asymmetric treatment of over- and under-weight. |
| `allocation.alertPolicy.watchFraction` | Fallback | `0.75` means amber inside the last quarter of the band: a ±3 band flags at 2.25 points. |
| Neither supplied | — | **Amber never fires.** Only breaches flag. The renderer carries no default threshold, and the validator warns when neither is present. |

⚑ The fallback rule is deliberately thin, because the interesting alert rules are not thresholds on a snapshot. Three worth considering, all of which require the engine to emit `alert` directly:

- **Persistence.** A weight one day outside its band is noise; four quarters outside is a governance failure. Bands exist precisely to absorb the former.
- **Direction of travel.** Approaching the band from inside is a different signal from returning to it from outside, and the flag currently cannot tell them apart.
- **Actionability.** A private class outside its band cannot be rebalanced within the period — the only levers are pacing, which bites in years, and secondaries. Flagging it identically to a public class implies an action that does not exist. This is the strongest argument for engine-supplied levels, and it interacts with DN-5 §2.2: the policy twin faces the same constraint and does not escape it either.

---

## 4. Plane semantics

`meta.plane` states which plane the payload is on. Every field is one of three kinds:

| Kind | Fields |
|---|---|
| **Plane-sensitive** | `plan.totalValue`, `plan.history.values`, all `allocation` weights and values, private `navOpen`/`navClose`, `coverage`, `callRateNav`, `liquidity.tiers[].value` for private tiers, `unfundedToNav`, drawdown figures |
| **Plane-invariant** | `calls`, `distributions`, `unfunded*`, `callRateUnfunded`, cash, `forecast12m.payout` and `.calls`, all public-market series |
| **Plane-independent** | `meta`, labels, footnotes, colours |

**Alert counts are plane-sensitive, and the difference is the headline.** On the sample payload the reported plane shows 3 classes outside band and 2 approaching; the true plane shows 5 outside and 1 approaching, with every additional breach on the private side and the publics flattered by the rescaling. The number of red flags on a CIO's screen depends on which set of books is open. That is the product's argument delivered as a count rather than an essay, and it is the single clearest demonstration the dashboard produces.

The second row is the useful one and it is worth stating in the interpretation guide: **the cash account does not have two planes.** Calls, distributions and the payout are the same numbers whichever plane you look at. Smoothing changes what the portfolio appears to be worth, not what leaves the bank. That is the product's argument reduced to a schema.

⚑ **O-2 · Plane availability by tier.** The individual tier plays a generic portfolio and the true plane is a genuine teaching device there. The institutional tier renders a client's own portfolio and a "true value" figure on a CIO's screen is a number their auditor did not produce. Decide whether `planesAvailable` is `["reported","true"]` on the institutional build, and if so what the true plane is labelled — "de-smoothed estimate" is defensible; "true value" invites a conversation nobody wants.

---

## 5. The 10-year column problem

⚑ **O-1 · Pre-run history.** The dashboard shows a five-year plan-growth window and 3Y/5Y/10Y return columns. At Y4 Q3 of a ten-year world, none of those windows exists inside the world. There are three answers and they are not interchangeable:

| Option | Consequence |
|---|---|
| **A. Generate pre-history.** The world starts with an inherited plan and a market history. | The plan-growth chart's hatched band and the long columns are real. Costs a pre-run generation pass; the pre-history must pass the same V-rules or it is an unvalidated artefact sitting inside a validated product. |
| **B. Null the unreached columns.** Show `—` until Year 3, Year 5, Year 10. | Honest, cheap, and the table is visibly thin for the first third of a decade — which is itself an accurate depiction of a new plan. |
| **C. Reference-portfolio splice.** Long columns computed from a static reference history. | Do not. It puts a number in a column that no run produced and it cannot be replayed. |

The mockup shows option A because it renders more legibly. **The renderer supports B today** — nulls print as em dashes and the hatched band collapses when `worldStartIndex` is 0. This is a decision for the D-series, not a rendering detail, because it determines whether the generator has a pre-run pass at all.

---

## 6. Forecast discipline

Every forecast quarter carries `forecast: true`. The renderer draws it at reduced opacity behind a shaded panel captioned **"FORECAST · ROLL-FORWARD, NOT A PROJECTION"**. That caption is part of the contract, not decoration.

What the forecast is: the pacing schedule held fixed, the current linkage calibration applied, the WP3.9 recursions rolled forward. What it is not: a distribution, a probability, or a statement about what will happen in this world.

⚑ This is the sharpest tension in the dashboard with the "not a forecast" position. A CIO looking at forward capital calls will reason about them as an expectation, whatever the caption says. Two mitigations worth considering before beta:

- Render forward bars as a **range** from the linkage residual dispersion rather than as point estimates. This depends on A-2 in the Albourne needs register, which is currently guesswork — so the range would be honest about being wide.
- Allow `forecastQuarters: 0`, which the contract already supports, and default the public tier to it.

---

## 7. Open items

| # | Item | Owner | Blocks |
|---|---|---|---|
| ⚑ O-1 | Pre-run history: option A, B or C (§5) | Governance | Plan tab, long return columns |
| ⚑ O-2 | Plane availability and labelling on the institutional tier (§4) | Governance + Counsel | Header control |
| ⛔ O-3 | Whether `markets.conditions` — the L1/L2 macro state — is shown to a player at all. Reading the regime directly is materially easier than inferring it from the portfolio, and the help agent is already information-walled against unrevealed data. The same wall arguably applies here. | Governance | Markets tab |
| ⚑ O-4 | Tier membership is static in the payload, but tier 3 is defined by *behaviour* — and the correlation panel shows those correlations converging in exactly the drawdown where the tiering matters. Either tiers are re-assigned per period, or the panel must show which sleeves are drifting toward tier 3. | Quant | Liquidity tab |
| ⚑ O-5 | Goal mapping (growth / real return / income / diversifiers) is a policy input. Decide whether it ships as a fixed taxonomy or is client-configurable, and where it is stored. | Product | Allocation block |
| ⚑ O-6 | `coverageDanger` is P-B and is unfilled. Until it is, coverage renders against the 0.50 anchor only and no alert state fires. | Quant | Liquidity, private tabs |
| ⚑ O-7 | Per-class private series require pooling over **asset class × cashflow archetype**, not asset class alone. Real estate debt, infrastructure debt, distressed credit and secondaries do not belong in their asset-class series. The contract's flat `series` map cannot express a crossed key — if the pooling stands, the key becomes `classId × archetype` and the class selector needs a second dimension. | Quant | Private tab |
| ⚑ O-8 | Open-end vehicles (core RE, core infrastructure) have no drawdown recursion and no unfunded commitment. They will render as `coverage: 0` and a flat call rate, which is misleading rather than empty. They need either a separate block or explicit exclusion from the private tab with a stated reason. | Quant | Private tab |
| ⚑ O-10 | Alert rule beyond the snapshot threshold: persistence, direction of travel, and the actionability problem for private classes that cannot be rebalanced within a period (§3). Requires engine-supplied `alert` rather than the fallback. | Quant + Governance | Alert levels |
| ⚑ O-9 | **WP3.9 §7 and DN-5 §3.1 describe the same episode with opposite signs.** WP3.9 has reported private weight rising while true weight falls; DN-5 has reported understating true. Both are realisable — the sign depends on whether privates truly fell more or less than publics — but the plane transform in `buildCioView` has to pick one per world state, and the interpretation guide has to explain which. | Quant + Governance | Plane transform |

O-9 is the one to resolve first. It is a genuine inconsistency in ratified documents, it is invisible until someone builds the plane transform, and it determines what the flagship screen actually says.

---

## 8. Acceptance

1. `validateCioView(buildCioView(golden, { plane: "reported" }))` returns no errors. Same for `"true"`.
2. `buildCioView` called twice with identical arguments produces byte-identical JSON.
3. Rendering with `forecastQuarters: 0` produces no forecast region and no caption.
4. Rendering with `markets` absent, `benchmark` absent, and `sourcing` absent produces a complete page with those panels omitted, no empty frames.
5. A payload with `worldStartIndex: 0` renders the plan chart with no hatched band and no divider.
6. A payload with `null` in every 10Y position renders em dashes, not `+0.0`.
7. Weights sum to 100.0 ± 0.1 on both planes; tier values sum to plan total ± 0.5%.
8. Aggregate private series equals the sum of class series at every quarter, to 0.1%.
8b. A payload with no `alertPolicy` and no explicit `alert` renders breach flags only, no amber, and no amber legend entry. A payload with `watchFraction` outside (0,1) fails validation.
9. Every rendered figure traces to a `CioView` field. Grep the component for arithmetic outside `formatting`; the only permitted computations are ratios of two supplied money figures for display (`share of plan`, `cover of outflow`), and those are listed in §9.

### Permitted in-renderer arithmetic

Exhaustive. Anything else is a contract violation.

- tier share of total = `tier.value / Σ tiers`
- cover of outflow = `tier.value / |forecast12m.net|`
- share of plan = `value / plan.totalValue`
- goal totals = Σ `currentPct` over member classes
- deviation = `currentPct − targetPct`
- excess = `total[i] − benchmark[i]`
- breach test = `|currentPct − targetPct| > bandPct`
- watch test = `|currentPct − targetPct| ≥ watchFraction × bandPct`, only where `watchFraction` is supplied
- LTM and next-4q sums over supplied quarterly figures

Each is a sum or a ratio of supplied figures with no model content. Anything with a parameter in it belongs in the engine.

---

## 9. Files

| File | Role |
|---|---|
| `cioView.ts` | Types, conventions, `validateCioView()` |
| `terrarium-cio-dashboard.jsx` | Renderer v0.3. Mock block at the foot is deleted on wire-up. |
| `DN-8` (this note) | Contract, provenance, open items |

**Wire-up sequence:** implement `buildCioView` → run the validator against a golden RunRecord in CI → replace `view={undefined}` with the real payload → delete the mock block → confirm acceptance tests 1–9.

---

## Resolutions — 2026-08-14 (owner decisions, spec §2)

Ratified against `docs/superpowers/specs/2026-08-14-cio-dashboard-design.md`.
The dashboard is the in-session play surface (the cockpit).

| Item | Resolution |
|---|---|
| ⚑ O-1 | **Option A**, built as its own WP (cio-04). Dashboard ships first with `worldStartIndex: 0` and nulled long columns (B behaviour as a transitional state). |
| ⚑ O-2 | `planesAvailable: ["reported","true"]`. Generic-portfolio tier; true plane labelled "engine true state". |
| ⛔ O-3 | **Observables only.** `markets.conditions` is never emitted to a player build. |
| ⚑ O-4 | Static class→tier mapping, footnoted. Behavioural re-tiering deferred. |
| ⚑ O-5 | Fixed goal taxonomy, shipped as a policy constant in `ah/cioview.py`. |
| ⚑ O-6 | `coverageDanger` stays unset until P-B is filled. |
| ⚑ O-7 | v1 series = `aggregate` + closed-end classes only. |
| ⚑ O-8 | Open-end/evergreen sleeves excluded from the private tab with a stated footnote. |
| ⚑ O-9 | Dissolves: reported-vs-true is the engine's `_reported_marks` output; the builder reports it, never picks a sign. |
| ⚑ O-10 | v1 uses `alertPolicy.watchFraction = 0.75`; engine-supplied `alert` deferred (additive upgrade). |

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 0.2 | Aug 2026 | Added alert levels (`ok` / `watch` / `breach`), `AlertPolicy`, and the threshold-provenance rule. Renderer v0.3 gains flags on the allocation and performance tables, watch zones inside the bars, donut rims and panel roll-ups. O-10 logged. |
| 0.1 | Aug 2026 | First draft. Contract extracted from dashboard mockup v0.2; renderer refactored to v0.3 as a pure renderer over `CioView`. Nine open items logged. |

---

*Not investment advice. Generic parameters; not representative of any institution's policy portfolio, liquidity policy or pacing plan.*
