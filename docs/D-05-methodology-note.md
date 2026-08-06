# How Terrarium Works — and How You'd Catch It Being Wrong
## D-05 · Methodology note · Draft v0.3 · August 2026 · v0.3 fills the G2 results slots in §6, adds §6.1 and two results figures

*Audience: the sceptical practitioner. Register: plain, per the wire but flatter. As of v0.3 the G2 results slots in §6 are filled from the sealed battery; the remaining [[double brackets]] are cross-references to sibling documents that are not yet public, not missing results. Where a result does not exist, §6 says so explicitly rather than leaving a bracket. Anchors are stable; the help agent cites into this document.*

---

## 1. Start with the two hardest questions {#hardest-questions}

Two parts of this system have no direct precedent, and you will find them faster than we can hide them — so they go first.

**Can anything generate a believable decade?** Honest answer: coherent decade-length generation is an open research problem. Nobody has solved it, including us. What we have is a specific architectural answer — four nested layers, from slow to fast, each constraining the one below — and a battery of tests it must pass before any world reaches you. The architecture is our proposal; the tests are your protection. Both are documented, and the tests were fixed before the models were trained (§6).

**A language model writes the scenarios. Why should you trust that?** You shouldn't, and the system is built so you don't have to. The compiler translates a described scenario into generator parameters and a narrative. The narrative — headlines, actors, the wire — is display only. **It cannot touch a number.** Every numeric path comes from the calibrated generator, passes the same validation battery as every other world, and is rejected if it fails economic-coherence checks. The nearest precedent for scenario compilation is in defence-sector wargaming; in financial markets, to our knowledge, this is first — which is exactly why it is caged this way.

![The compiler cage: the scenario compiler writes parameters and narrative on separate tracks; a wall separates them, and the narrative path into the world is display-only.](d05-figB-compiler-cage.svg)

*The cage, drawn. Words and numbers leave the compiler on separate tracks and never rejoin: parameters go through coherence checks into the calibrated generator; the narrative reaches you as display only.*

If those two answers hold up under the rest of this note, the rest is detail.

## 2. What a world is {#what-a-world-is}

A world is a complete, invented, month-by-month decade: rates, inflation, market returns, private-fund cashflows, news. It is generated from a versioned specification — a WorldSpec — plus a seed. Same spec, same seed, same decade, bit for bit, forever. That guarantee is not marketing; it is a property of the engine you can test yourself (§7).

A world is not a forecast. Worlds are built to be *plausible* — statistically indistinguishable from the kind of decade markets produce — not *probable*. Nothing in this system predicts anything, and any use of it as a prediction is a misuse.

One spec generates many decades. The scenario "inflation stays stubborn" is a distribution; each seed draws one decade from it. Your score on one decade contains luck. Your score across the ensemble does not — which is why the two are reported separately (§8).

## 3. How a decade is generated {#four-layers}

Four layers, slow to fast. Each layer constrains the one below it, which is what makes 120 months hang together as one decade rather than 120 unrelated draws.

| Layer | What it sets | Where it comes from |
|---|---|---|
| **Climate** | The slow level — where real rates, inflation, growth sit over decades | Century-scale macro history (Jordà–Schularick–Taylor panel) |
| **Seasons** | Multi-year regimes — expansion, stress, recovery — and transitions between them | A documented rule set. This is a human modelling choice, stated as such, and varied in robustness testing rather than presented as discovered truth |
| **Weather** | Monthly market returns, conditioned on the regime | The one machine-learned layer. Constrained so it cannot produce negative prices or broken rates, and trained with an explicit penalty for getting tail risk wrong |
| **Events** | Named events and the news wire riding on the regime spine | Generated; display and colour only. Never touches the path |

The lineage is older than it looks. The cascade idea — slow variables driving fast ones — is the Wilkie model from 1984, the ancestor of most regulatory scenario generators. Its known weakness was unrealistic month-to-month behaviour; the machine-learned weather layer is the repair, confined to the one place it is needed.

![The four layers, slow to fast: climate, seasons, weather, events. Weather is the single machine-learned layer, caged by the specified layers around it.](d05-figA-layers.svg)

*The four layers. One is machine-learned, and it is fenced above by the regime it must obey and below by the events that cannot touch it.*

## 4. The inputs are corrected before anything trains on them {#desmoothing}

Private-asset returns are appraised, not traded, and appraisals anchor on last quarter's value. The result — established in the academic literature for over thirty years (Geltner 1991; Getmansky, Lo & Makarov 2004) — is that reported private-asset series understate volatility and market exposure. Materially.

A model trained on reported series learns that private assets are smooth. They are not; the smoothness is an artefact of how they are measured. So every private-asset series is **de-smoothed** — passed through the standard correction from that literature — before anything is calibrated on it. The smoothing is then put back, deliberately and visibly, as the *reported* plane inside the simulation, with the corrected series as the *true* plane beneath it.

That gap between the two planes is not a modelling nuisance. It is the thing the product exists to show you. [[Cross-reference: interpretation guide §reported-vs-true.]]

![The de-smoothing pipeline: reported series are corrected before calibration; inside the simulation the smoothing is reinstated as a visible reported plane alongside the true plane.](d05-figC-desmoothing.svg)

*Corrected on the way in, reinstated where you can see it. Calibration never touches a smoothed series; the simulation then carries both planes, with a toggle between them.*

## 5. Cashflows follow the framework you already use {#cashflows}

Capital calls, distributions and NAV follow the Takahashi–Alexander model — the same pacing framework most institutions already run — extended in one direction: call and distribution rates respond to market conditions instead of following a fixed schedule.

The extension is calibrated on public, allocator-side data (Robinson & Sensoy 2016: quarterly cashflows for 837 funds, taken from a limited partner's own accounting records, free of self-reporting bias), patched with recent industry aggregates for the post-2020 period. Three calibration facts worth knowing because they are counterintuitive:

- **In the GFC, buyout capital calls did not slow down.** Distributions collapsed; calls kept arriving. The self-funding breakdown that squeezes portfolios is a distribution-side phenomenon, and the engine reflects that.
- **Fund age explains far more cashflow variation than market conditions do** — the market linkage is a modest systematic tilt on a lifecycle backbone, and it is presented as such, not as a dominant driver.
- **At the level of a single fund, most cashflow variation is idiosyncratic.** A portfolio holds many funds across many vintages, so the idiosyncratic part largely diversifies away; the systematic part is what survives to portfolio level, and that is what the engine models. This is why a linkage with a modest fund-level fit is the right tool for a portfolio simulator — a point we make here before a reviewer makes it for us.

The published engine's calibration uses **public sources only** and is independently reproducible. Work with proprietary datasets is confined to a separately versioned institutional calibration, and every run record discloses which calibration produced it.

## 6. The tests it must pass — fixed before the models were trained {#battery}

Every generator, and every published world's ensemble, passes a validation battery. The thresholds were pre-registered — written down numerically before any model was trained — so the tests are capable of failing. A battery specified after seeing results is a description, not a test.

**There are two batteries, and they do not have the same standing.** They are reported separately below and never combined, because averaging them would misstate both.

| Battery | What it covers | Seal status | Evidentiary weight |
|---|---|---|---|
| **Generator battery** (Step 2) | The hierarchical generator: stylised facts, tails, utility, memorisation, economics, calibration, conditional behaviour, and the benchmark kill criterion | Thresholds hashed **together with the code that judges them**; first sealed 2026-07-26, re-sealed 2026-07-31 and 2026-08-02 | **Pre-registered.** Results below are pass/fail against bounds fixed in advance |
| **Stylised panel** (Step 0) | Seven summary statistics on the toy engine's own output | Drafted 2026-07-24; **never ratified** — all seven gates still carry `status: todo` | **Descriptive only.** No pass/fail claim is made; see the note at the end of this section |

What is tested, in plain terms:

| Test | The question it answers |
|---|---|
| Stylised facts (Cont 2001) | Do generated returns have the statistical signature real markets have — fat tails, volatility clustering, the right decay of autocorrelation? |
| Tail accuracy | Are value-at-risk and expected shortfall correct at the 95th and 99th percentile, on a frozen set of benchmark portfolios? |
| Discriminability | Can a trained classifier tell synthetic paths from real ones? |
| Train-synthetic, test-real | Does a model trained on synthetic data still work on real data? |
| Memorisation | Is the generator producing genuinely new paths rather than replaying its training data? |
| Benchmark comparison | Does the generator beat a pre-specified statistical bootstrap — and if it does not, the bootstrap ships instead. That kill criterion was written before training began. |

### The results {#battery-results}

**Provenance.** Generator `hier-flow-v1` against benchmark `bootstrap-v1`; data vintage `2026-08-02.4`; sampling seed `20260727` (seed index 0 of three); ensemble 1024 paths × 120 months; battery version `eval-battery-0.1`; pre-registration digest `sha256:e50e18f300aba8dd…f85d92`, matching `pre-registration.lock` sealed 2026-08-02. Every cell recorded `prereg_verified: true` and `criterion_bearing: true`. Figures: `docs/figures/results/`. Read 2026-08-05.

**The gates that can fail.** The sealed battery's enforce surface is exactly five names — a deliberate restriction recorded in the pre-registration itself, on the grounds that the other bounds rest on an unmeasured null. All five passed, for both systems. Margins are shown because a pass with no margin is not the same result as a pass with a wide one.

| Gate | Bound | `hier-flow-v1` | Margin | `bootstrap-v1` | Margin |
|---|---|---|---|---|---|
| `moment_band_exceedance_fraction` | ≤ 0.5 | 0.2333 | inside by 0.2667 | 0.0667 | inside by 0.4333 |
| `dependence_band_exceedance_fraction` | ≤ 0.5 | 0.2667 | inside by 0.2333 | 0.4222 | **inside by 0.0778** |
| `near_duplicate_fraction` | ≤ 0.5 | 0.0913 | inside by 0.4087 | 0.0566 | inside by 0.4434 |
| `money_pump_violations` | ≤ 0.0 | 0.0 | at the bound | 0.0 | at the bound |
| `floor_violations` | ≤ 0.0 | 0.0 | at the bound | 0.0 | at the bound |

Two things a reader should take from that table rather than from a summary of it. The benchmark clears the dependence gate by 0.0778 — the narrowest margin anywhere in the battery, and closer to failing than anything the challenger produced. And the two systems are not ordered consistently: the benchmark is further inside on moments, the challenger is further inside on dependence. Neither dominates.

**Memorisation.** Bounds sealed; severity `report`, so these do not gate.

| Statistic | Bound | `hier-flow-v1` | Margin | `bootstrap-v1` |
|---|---|---|---|---|
| `nn_distance_p05` | ≥ 0.0279 | 0.5541 | above by 0.5262 | 0.6423 |
| `nn_distance_p50` | ≥ 1.0371 | 1.3918 | above by 0.3547 | 2.3641 |
| `membership_inference_auc` | ≤ 0.75 | 0.4237 | inside by 0.3263 | 0.2939 |

The generator is not replaying its training data. It also sits consistently closer to the training set than the bootstrap does on every one of these three, which is what one would expect of a learned model against a resampler of history, and is stated rather than left for a reader to notice.

**Discriminability and train-synthetic-test-real — descriptive, no threshold exists.** This document's previous draft promised these "against a pre-registered ceiling" and "against a limit". **There is no such ceiling and no such limit.** Both statistics are computed and recorded, but they were sealed at severity `report` with no bound, so no pass/fail claim can honestly be made about them.

| Statistic | Bound | `hier-flow-v1` | `bootstrap-v1` |
|---|---|---|---|
| `discriminative_score` (\|balanced accuracy − 0.5\|; 0 = indistinguishable) | **none sealed** | 0.0310 | 0.1472 |
| `predictive_score` (TSTR one-step-ahead error) | **none sealed** | 0.5302 | 0.5206 |
| `tstr_degradation` (MSE ratio, synthetic-trained ÷ real-trained) | **none sealed** | 1.0846 | 1.0649 |

Descriptively, a classifier separates `hier-flow-v1` from real data less well than it separates the bootstrap from real data (0.031 against 0.147), and a model trained on either synthetic source loses about 6–8% of its accuracy against a real-trained model. Those are observations, not passes.

**The kill criterion — outcome, either way.** The pre-specified rule was that the generator must beat `bootstrap-v1`, and that if it did not, the bootstrap would ship instead. It beat it, on the per-seed route, in all three seeds:

| Seed index | Challenger elicitability | Benchmark elicitability | Difference | Band exceedances (C vs B) |
|---|---|---|---|---|
| 0 | −2.5591 | −2.2131 | −0.3461 | 12 vs 13 |
| 1 | −2.5163 | −2.2132 | −0.3031 | 5 vs 11 |
| 2 | −2.5116 | −2.2139 | −0.2978 | 8 vs 12 |

Pooled: mean difference −0.3157, standard deviation 0.0265 (n = 3), the absolute mean exceeding the standard deviation as the sealed rule requires. Verdict: **PROMOTE**. Four of the five systems evaluated earned the opposite verdict — SHIP-BENCHMARK — and that was a legitimate outcome of the exercise, not a failure of it.

**The caveat the pre-registration recorded against its own result.** The sealed rule carries a disclosure, `multi_seed_decision_rule.benchmark_draw_span_bias`, recorded in the governance register as RFR-66: *the head-to-head is biased toward promotion by the benchmark's data window.* `bootstrap-v1` can only resample 1990–2020, whose worst equity drawdowns are 2000–02, 2008–09 and 2020, while the challenger was fitted on a span that includes 1929–33, 1937, 1973–74 and 1987 — and both are scored against realisations that include all of it. On any statistic rewarding reproduction of the deep pre-1990 left tail, the benchmark is handicapped by its window rather than by its form. The direction matters: the project's stated posture is that SHIP-BENCHMARK is a successful outcome, so this bias runs against the conservative verdict. It was written into the seal before the comparison was run, not added afterwards.

**And the seal required the re-run that tests it.** The same disclosure binds the evidence document to report the comparison restricted to the 1990–2020 realisations both systems are scored against — the common window, where the benchmark's handicap disappears. On that restriction `hier-flow-v1`'s mean difference moves from −0.2967 to −0.3634 and the challenger still beats the benchmark: the promotion survives the restriction and the margin widens. (G2-era figures, vintage `2026-07-26.1`.) The bias is real, it was declared in advance, and it was then measured rather than left as a caveat.

![Benchmark comparison: per-seed elicitability for challenger and benchmark, the sealed decision rule's pooled statistic, and the band-exceedance counts.](figures/results/fig-benchmark-comparison.svg)

*Benchmark comparison, `hier-flow-v1` vs `bootstrap-v1`. Generator version `hier-flow-v1` (campaign-2 checkpoints, `c6addb54…`); battery version `eval-battery-0.1`; vintage `2026-08-02.4`.*

**What the decade-scale tier does not show.** Sixteen of twenty-two metrics in the ten-year tier are structurally unavailable for every generator — fourteen because no generator emits a path longer than its own horizon, two because no valuation factor is mapped. The negative control designed to fail this tier, whose time ordering is destroyed outright, produces zero substantive failures in it. **No decade-scale pass is claimed.** A generator whose decade behaviour was wrong while its monthly behaviour was right would not be caught by this battery.

**The stylised panel (Step 0) — descriptive, gates open.** Its thresholds were drafted 2026-07-24 and have never been ratified; all seven remain `status: todo`. Six of the seven have never been observed at all. The seventh has:

| Statistic | Drafted band | Observed | Result |
|---|---|---|---|
| `acf_r_lag1`, pooled equity | [−0.2, +0.2] | **0.364** | **outside by 0.164** |

Ordering, stated in full: the band was drafted 2026-07-24 and never ratified; the statistic was observed 2026-08-04. The statistic was therefore observed **before** ratification, and this is reported as descriptive — *threshold post-hoc / pending ratification; pre-registered evaluation of this metric applies from the next generator version.* It is a miss, and it is reported here with the prominence a pass would have had. The cause is known and recorded: the toy engine's crisis is a rectangular block of months in which every path takes the same deterministic hit, which is exactly what lag-1 autocorrelation measures.

The remaining six statistics — excess kurtosis, skewness, Hill tail index, `acf_abs_lag1`, median maximum drawdown, correlation distance — are *awaiting post-ratification battery run; thresholds ratification recommended 2026-08-05 — see evidence inventory*. They have never been observed, which means pre-registration for six of the seven is still intact and is preserved by ratifying now rather than by waiting.

![Pre-registration timeline: the two batteries on one axis, showing seal and re-seal dates, the 2026-08-04 stylised-panel run, and ratification status per gate.](figures/results/fig-preregistration-timeline.svg)

*Pre-registration timeline. Generator version `hier-flow-v1`; battery versions `eval-battery-0.1` (Step 2) and `battery-0.1` (Step 0).*

A severe test we impose on ourselves and flag as our own invention: training with an entire historical regime excluded — the 1970s — and testing on it. Self-designed tests are weaker evidence than field-agreed ones, which is why the full battery is published as an open standard others can run and extend. [[Link: TERRARIUM-Bench when public.]]

**The severe test's outcome: inconclusive, and the reason is structural.** Excluding the 1970s and regenerating from the 1965 state moved the era-frequency gap by roughly 6–8% of a gap that exists with the decade in sample. That is not a pass and not a failure; it is a test that did not discriminate. One leg of it was vacuous by construction — the block-sampler exclusion dropped zero blocks — so the test as run did not exercise the thing it was designed to exercise. Recorded as a human judgement, not a computed verdict.

### 6.1 What the results establish, and what they don't {#what-results-establish}

What they establish is narrow and worth stating precisely. On the sealed generator battery, the hierarchical generator cleared every gate capable of failing it, did not memorise its training data, and beat the pre-specified bootstrap on the tail criterion in all three seeds — under thresholds and judging code hashed together before the comparison was run, and verified by content address on every cell. That is a real result and it is the kind of result the pre-registration discipline was built to produce.

What they do not establish is nearly everything a reader might want next. No decade-scale claim is made, because sixteen of twenty-two decade-tier metrics are structurally unavailable and the negative control designed to fail that tier does not fail it. Two of the tests this document previously advertised — discriminability and train-synthetic-test-real — turn out to have no sealed threshold at all, so their numbers are descriptive. The stylised panel is unratified, and its one observed statistic is a miss. The severe test was inconclusive. And the promotion carries a bias disclosure written into the seal itself, running in the direction of promotion. Read together, these say the generator survived the tests that existed, and that several tests a sceptic would want either do not exist yet or did not discriminate.

None of this reaches the question the platform is for. **Statistical realism is not decision-relevance, and neither is prediction.** A generator that reproduces the statistical signature of market returns has been shown to reproduce that signature — not to produce decades whose *decisions* resemble the decisions real markets demand, and not to forecast anything whatsoever. Whether simulated experience in this environment improves judgement is an open empirical question that this battery cannot answer and was never designed to; it is the human study's question, and it has not been run. Any use of these results as evidence of predictive validity is a misuse of them.

![The validation gauntlet: six pre-registered gates in sequence, ending at the kill criterion — if the generator does not beat the pre-specified bootstrap, the bootstrap ships instead.](d05-figD-gauntlet.svg)

*The gauntlet. Every gate's threshold predates training; the final gate is the kill criterion, and its outcome is published either way.*

## 7. Everything replays {#reproducibility}

Every run writes a record sufficient to reproduce it exactly: world, seed, engine version, every decision you took. Any score on any leaderboard, any chart in any shared card, any claim in any publication resolves to a record that you — not we — can replay and verify. The replay guide [[link D-07]] shows how in a few minutes.

This is an unusual claim for something that looks like a game, and it is the same property that makes the engine auditable as an institutional tool. There is one system, with one discipline, wearing two interfaces.

## 8. How scoring works {#scoring}

Your result is measured against a **policy twin**: the portfolio that would have existed had you done nothing discretionary — policy weights maintained within normal rebalancing bands, commitment pacing following its plan, all computed off *reported* values, exactly as a real institution operates. Decision alpha is your terminal outcome against the twin's, on the identical decade, decomposed decision by decision.

The twin is deliberately hard to beat. It follows its policy faithfully — and because it acts on reported values, it responds late to what smoothing conceals, exactly as real governance does. Beating it means seeing through the reported plane sooner than the process did. The full construction, including the per-decision decomposition and its disclosed limitations, is in the interpretation guide [[link D-03]].

![Scoring against the twin: two portfolio paths through the identical decade, diverging at the year-4 decision; the terminal gap is decision alpha.](d05-figE-twin.svg)

*Same decade, twice. The dashed line is the policy running faithfully off reported values; the solid line is you. The gap at the end is decision alpha — and every point of it is attributed to a specific decision.*

## 9. What this system cannot do {#limitations}

Stated here, not discovered by you later. The standalone limitations page [[link D-06]] carries the full list; the four that matter most:

1. **It cannot predict.** Plausible is the claim; probable is not.
2. **It cannot exceed its specification.** A specified model only produces worlds its designers imagined. A future crisis with a mechanism we did not author will not be in the library until someone authors it.
3. **The regime taxonomy is a choice.** Defensible, documented, varied in robustness testing — but chosen, not discovered.
4. **Simulated experience is not proven to improve decisions.** The research literature shows simulation changes *risk-taking*; whether it improves *judgement* is an open question. This platform is built to be able to test that question properly — it does not assume the answer, and neither should you.

## 10. The provenance of every component {#provenance}

Every load-bearing component cites a published ancestor; the mapping is maintained as a build artifact, and a component without a citation fails internal review. The bibliography with the component mapping attached is available at [[link: literature-to-build map, public version]]. Where a component has *no* ancestor — the scenario compiler, the decade horizon, the regime labels — it is named in §1 and §9 of this note rather than left for you to find.

---

*Not investment advice. Version 0.3, applies to WorldSpec `1.2.0`–`1.3.0`, battery versions `eval-battery-0.1` (generator battery, sealed) and `battery-0.1` (stylised panel, gates unratified). Results read 2026-08-05 from vintage `2026-08-02.4`. Changelog at [[link D-10]].*
