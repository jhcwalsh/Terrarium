# Stage 2 — the exam delta

**Date:** 2026-08-18 · **Branch:** `stage2-01-anchors` · **Decision:** `D-SP-9` (stage 2
funded, owner ruling 2026-08-17)
**Status: THE STAGE-2 EXAM.** This document is the specification the stage-2 bars are
stated in. It is sealed together with the code that judges them in
`docs/superpowers/specs/stage2-prereg.json`, **before the coupled fit is run** — because a
bar written after a coupling is fitted is a description, not a test.

**What it is a delta on.** `docs/superpowers/specs/2026-08-17-spine-v2-exam.md`, sealed at
`docs/superpowers/specs/spine-v2-prereg.json` and amended once
(`AM-SPV2-2026-08-17-001`). The ten bars of that exam **carry over byte-frozen** — same
thresholds, same judging code, imported and never re-implemented — and this document adds
**two** new bars, `P1` and `P2`, which the stage-2 design document proposed and could not
seal because neither existed as a number.

**What made them numbers.** `docs/superpowers/specs/2026-08-17-stage2-anchors.md` and its
artifact `docs/superpowers/specs/stage2-anchors.json`, produced by
`scripts/stage2_anchors.py`: `M3` (the coupling gate and the power calculation), `M4`
(history's curve decomposition), `M5` (both anchors under the classifier's threshold
dials), the windowing-symmetric phase re-derivation the verdict-integrity review's finding
`C1` demanded, the generated side's own scrambled null, and the draw count a sealed floor
needs.

**House rules this document is written under** (D-SP-6's standing communication rule):
plain language; every pass/fail bar states the real quantity that anchors it and why its
tolerance is the size it is; no term used without being defined once.

---

## 0. The one-paragraph answer

Two bars are added and ten are carried. **`P1`** asks whether the generated economy's
growth dial and inflation dial keep time with each other, and it is sealed at the
**minimum defensible threshold across the published candidate set** — a departure of
**0.040330** on growth flips and **0.031446** on inflation crossings, from each batch's
own phase-scrambled null. **`P2`** asks whether the generated yield curve is made of the
economy the engine simulates, and it is sealed as a **two-sided band, [0.391707,
0.673371]**, on the strict economic share of the slope's variance. Both are judged by
`scripts/stage2_report.py`, which classifies with the sealed `grader_v2` and computes both
statistics through `scripts/stage2_anchors.py`'s own functions, so the judged side and the
anchor side are provably the same code. Four anti-test sweeps and five controls were run
before the seal and all nine hold — including the two the design document names as the
gaming routes (an uncoupled engine, and an engine that shrinks its noise to buy an
economic share). The price of sealing `P1` at the softest candidate is measured and is
**not small**: against an engine whose dials are independent by construction, `P1` returns
a PASS **9.0%** of the time at fifty decades, against **1.3%** at the recommended
construct's own candidate. That number is the single most important thing in this document
after the thresholds themselves, and it is in the limitations register, not in a footnote.

---

## 1. The ten v2 bars, byte-frozen

**All ten carry over unchanged.** Not re-derived, not re-anchored, not re-implemented:
`scripts/stage2_report.judge_carried_v2` imports `scripts/spine_v2_report`'s own judges and
hands them the v2 seal loaded whole, and `judge_r1` / `judge_r2` delegate to the round-one
and round-two functions the v2 seal already hashes. A change in one of these ten verdicts
is therefore attributable to the engine and to nothing else, which is the only reason a
carried bar is worth having.

| code | what it asks | sealed threshold | v2 status |
|---|---|---|---|
| **T1** | does tightening cause downturns? | lift inside **[1.7752827491108736, 3.3473622102535145]** | PASS (on the amended arm) |
| **O1** | do the seasons turn the right way round? | clockwise fraction **≥ 0.5180669104991394** | FAIL everywhere |
| **D1** | recession spell length | pooled median inside **[0.0, 5.0]** months | PASS |
| **D2** | stagflation spell length | pooled median inside **[1.0, 7.0]** months | PASS |
| **D3** | recovery spell length | pooled median inside **[2.0, 8.0]** months | PASS |
| **D4** | expansion spell length | pooled median inside **[1.0, 7.0]** months | PASS |
| **A1** | does the inflation hedge pay when inflation is high? | directional, and spread inside **[−5.053054679081145, 32.31605649965673]** pp | **never measured** |
| **A2** | do stocks and bonds fall together when inflation is high? | correlation gap **≥ 0.13609378139729844**, positive level, share floor **0.80** | **never measured** |
| **R1** | severity still bites the book | b3 grid, byte-frozen from round two | **never measured** in v2 |
| **R2** | eras don't teleport at the seams | b2, byte-frozen from round two | **never measured** in v2 |

Two consequences to carry, both stated in the design document and neither softened here:
the persistence tier has never been the binding constraint and probably will not become
one; and **four of the ten have never been run at all**, so any sentence of the form "five
of six passed" is a statement about six bars, not about the exam.

**The byte-frozen set, by hash.** These are the files whose bytes define the ten carried
verdicts. Every one is inside the v2 seal's own hash list as well, so a change breaks two
tests rather than one.

| sha256 | file |
|---|---|
| `81ef5c7f5c895ecfa234a50cd68420c4d437751972a4b1beaecabef04f0a707f` | `docs/superpowers/specs/spine-v2-prereg.json` |
| `5e43614032095b32bfe9d1efb861d4a328a4b79476917de35b029d977c5248ea` | `docs/superpowers/specs/spine-v2-anchors.json` |
| `4fdf7c0ae6afb97764a6633f09f186ddfcc9b740509e64342eba94a38ab6f568` | `docs/superpowers/specs/2026-08-17-spine-v2-exam.md` |
| `fb6d48af01b9c2524d80ba9dfd713a701d577eb9900ee81db90d60975923cef1` | `scripts/spine_v2_report.py` |
| `cd08f39a7c50f217cd85eed64a709cc2aac3beffd1b992e744fd1b2dd5791ae4` | `scripts/spine_v2_grader.py` |
| `4ead157e2ea88e5505fd228f6636056361d9e5cde91ee2474797fbff46507e97` | `scripts/spine_pilot_b3.py` |
| `a78411fe2c3a288c6ac773964ee7133b5a9fb6ce15d77b54f143b48d3ae4d8a8` | `scripts/spine_pilot_report.py` |

The stage-2 seal hashes the first five directly. The two pilot files are reached through
the v2 seal, which is itself hashed, and through `tests/test_spine_v2_seal.py`, which
recomputes them on every run — so the chain is closed by a machine check and not by a
convention.

---

## 2. The rulings this exam is sealed under

Six stop-questions were open when the measurements landed. All six are ruled below, each
**recorded verbatim with its reasoning**, and all six were disclosed to the owner as
cheap-veto rulings — the standing convention that a ruling taken to keep work moving is
stated in full so that vetoing it costs one sentence rather than a re-derivation.

### SQ1 — which construct, for `O1` and for `P1`

> **RULING.** The v2 `O1` bar carries **BYTE-FROZEN** (comparability with the closed
> campaign); the stage-2 PRIMARY ordering/phase measurement is the
> **windowed-overlapping symmetric construct** (the only one that leaves the judged object
> unchanged — the first-pass agent's own recommendation).

**Why these two are compatible rather than contradictory**, because that is the part a
reader will stumble on. Symmetrising the windowing changes what is done to **history**,
not to the engine: it cuts the panel into 120-month windows and drops each window's first
twelve months, which is exactly what a generated decade does to itself for free. So the
generated statistic is **bit-identical** under both constructs, and adopting the symmetric
construct as primary costs nothing that `O1`'s frozen floor protects. `O1` keeps its
sealed floor of 0.5180669104991394 and its sealed verdict; the symmetric construct's own
floor, **0.515672**, is published beside every `O1` reading as a disclosure
(`stage2_report.disclose_o1_symmetric`) and is **never judged**. Under it week 3's engine
still fails, by 62% of the recorded margin.

**And the reason it stays a disclosure rather than becoming a bar:** the symmetric floor is
cut from 2000 draws and carries about 0.003 of tape noise on margins of 0.001–0.006
(anchors §2.6, §6.3). Re-cutting a sealed threshold is a different act from anchoring a new
bar, and it would need the 640,000-draw rule below applied to it first.

### SQ6 — which summary `P2` seals on

> **RULING.** `P2` seals on the **STRICT ECONOMIC-SHARE** summary; the realised-R²
> non-robustness is a **declared limitation**, not a second bar.

The strict share is primary because **it is the function the engine is scored by** — that
identity is `P2`'s fourth anti-test obligation and it outranks elegance. The realised R²
of the same fit has a bootstrap interval of `[−0.2203, 0.5616]` that spans zero at every
block length, which would have dropped `P2` under the pre-declared rule; the anchors'
§1.5 shows that this is an R²-under-GLS pathology at `rho` = 0.98 rather than a statement
about the yield curve. Making it a second bar would mean judging the engine by a statistic
whose own interval cannot exclude zero. It is in the limitations register instead.

### SQ7 — where `P1`'s threshold sits

> **RULING.** `P1` seals at the **MINIMUM defensible threshold across the published
> candidate set** (all candidates and the 2–2.5× dial-sensitivity range published beside
> it; a bar that asks "is there ANY unambiguous phase coupling" is the economic question,
> every recorded engine fails even this softest bar, and demanding more would risk failing
> a correct engine given the anchor's own uncertainty).

The candidate set is published in the seal as `bars.P1_candidate_set` — eleven candidates
per move type, being the two windowed history constructs and the nine arms of the sealed
label-stability grid. The minimum is attained at the **inflation dial −50 bp** arm on both
move types. What the ruling buys and what it costs are both measured, and §6 carries the
cost.

### SQ8 — which null the threshold is cut from

> **RULING.** The **WITHIN-WINDOW** scramble is the null on **BOTH** sides (like-for-like);
> recompute `P1`'s thresholds under it (the +9%/+8% corrected candidates) before taking the
> SQ7 minimum.

A generated batch is fifty independent decades with no time axis between them, so the only
scramble it admits is a shift **inside** each decade. Shifting one 813-month panel is a
different operation on a different object and gives a different number. Every candidate in
the sealed set is cut from the within-window null; the superseded panel-wide candidates are
excluded, and the seal asserts that excluding them moves no sealed number (they sit above
the minimum anyway).

### SQ9 — the coupling lag

> **RULING.** The coupling lag is chosen by a **SEALED SELECTION RULE** (maximum likelihood
> on the declared 25-lag grid, profile published in the fit report), **not a fixed value**;
> the bootstrap lag-dispersion is a declared limitation.

`M3` selects ten months on the panel and says in the same breath that the panel does not
pin it: only 57% of bootstrap draws select within three months of ten, and the
classifier-cycle sensitivity arm selects **two**. Sealing "ten" would seal the half of the
measurement that is not solid. What is sealed is the **rule and the grid** — 0 to 24
months, one parameter at every lag, the highest likelihood wins, the whole profile
published beside whatever it picks.

### Floors — the draw count

> **RULING.** Every sealed floor is computed at **640,000 draws** (the measured
> requirement: tape noise 0.000148 ≤ one fifth of the smallest 0.000761 margin).

**How that applies here, stated precisely, because the answer is not "re-cut everything".**
The rule is adopted as binding, and neither stage-2 threshold needed it:

- **`P1`'s thresholds carry no tape at all.** They are half a departure, and both halves —
  the measured clockwise fraction and the within-window null — are **exhaustively
  enumerated**, not sampled. There is no bootstrap anywhere in `P1`'s anchor, so its tape
  noise is exactly zero and the rule is met a fortiori.
- **`P2`'s band is a bootstrap interval, cut at 2000 draws**, and the smallest margin it
  has to resolve is **0.369** — the distance from its lower edge to the closer of the two
  recorded engines. One fifth of that is 0.0738, against the 0.000152 the O1-class rule
  demands, because an O1-class floor resolves margins of 0.00076. `P2`'s tape noise has
  **not been measured**, and the anchors' §6.5 prices measuring it: the share refits an
  AR(1) profile on every draw, about two hundred times the work per draw, so a 640,000-draw
  re-cut is hours rather than the thirty seconds a clockwise-fraction floor costs. It is a
  declared limitation and a stop-question rather than a silent assumption.

The 640,000 figure therefore enters the seal as the **standing requirement for any
`O1`-class (clockwise-fraction) floor cut in stage 2** — including the symmetric `O1` floor
above, if it is ever promoted from disclosure to bar.

---

## 3. P1 — the phase-coupling bar

### 3.1 The plain question

In history, downturns tend to begin while inflation is still hot, and inflation cools
during them. Does the generated world do the same, or do its growth dial and its inflation
dial wander independently?

### 3.2 The statistic, and why it is two numbers rather than one

The clock runs recovery → expansion → stagflation → recession → recovery, and **it
alternates**: one step changes the growth answer, the next changes the inflation answer. So
a growth flip is "clockwise" only if it happens on the matching side of the inflation axis,
and an inflation crossing only if it happens on the matching growth axis. `P1` therefore
computes the clockwise fraction **separately for growth flips and for inflation crossings**,
and each one is reported as its **departure from the batch's own phase-scrambled null**.

**Both must clear.** The shortfall the bar exists against was spread evenly across the two
move types (about 0.06 each), which is the signature of a missing *link* rather than of one
broken dial; a one-move-type version could be passed by an engine that couples the dials in
one direction only.

**How the null is computed — this is part of the bar, not a footnote.** The judge shifts
each decade's inflation dial circularly against its growth axis, the same shift in every
decade, **every admissible shift enumerated** at a 24-month guard — which preserves each
dial's own dynamics (its run lengths, its hot share, its persistence) and destroys only
their alignment. It is exhaustive, so it needs **no seed and has no Monte Carlo error**.
Two properties follow and both matter: the bar cannot be passed or failed by a base-rate
accident, and the null is computed on **the batch being judged** rather than substituted
from history — the anchors' §5 measured that substitution wrong by up to **0.0126**, which
is a fifth of a threshold.

**Diagonal moves** — a transition that changes both answers at once — are in the clock
nowhere, so they are counter-clockwise by construction. They are reported and never folded
into either move type. They are also the reason the *overall* clockwise null is not 0.500.

### 3.3 The anchor

History's clockwise fractions under the sealed construct (SQ1: windowed, overlapping), its
own within-window null (SQ8), and the departure between them:

| move type | history | within-window null | departure |
|---|---|---|---|
| growth flips | 0.626416 | 0.488248 | **0.138168** |
| inflation crossings | 0.615814 | 0.490721 | **0.125093** |

### 3.4 The threshold, and why it is the size it is

| move type | **SEALED minimum departure** | attained at | recommended construct's own candidate |
|---|---|---|---|
| growth flips | **0.040330202948** | inflation dial −50 bp arm | 0.069084 |
| inflation crossings | **0.031445706759** | inflation dial −50 bp arm | 0.062547 |

Three things stack up to make that number, and they should be read in order.

**First, the tolerance is half of history's departure, and the halving is the anchor's own
uncertainty made into a rule.** Each move type rests on about 35 uncensored transitions.
The sampling error on a fraction measured over 35 transitions is about 0.083 — *larger than
the entire departure being measured*. Demanding history's point value would fail a correct
engine roughly half the time, which is the exact defect `O1`'s own §2(c) was rewritten to
avoid. Half is the widest tolerance that keeps an uncoupled engine failing in expectation
and an engine reproducing history's phase relation passing with room.

**Second, that half is not one number but eleven**, because the departure it is cut from
moves under a conventional 50 bp move of the classifier's threshold dials — by **1.35 of
its own standard error** on inflation crossings, which is an escalation under the campaign's
sealed stability rule. Across the nine arms the candidate threshold ranges over
[0.040330, 0.082822] and [0.031446, 0.078601]: **a factor of 2.05× and 2.50×**.

**Third, ruling SQ7 takes the minimum of those eleven**, and the reason is the economic
question the bar is for: *is there ANY unambiguous phase coupling in this engine?* At the
minimum, every engine on the record still fails — by 0.026 at the closest cell rather than
by 0.010 — so the bar is not made vacuous by softening it. Demanding more would risk
failing a correct engine on an anchor that a dial move halves.

**What the minimum costs is measured in §6 and it is 9.0%.** That is the price of the
ruling and it is the number to argue with if the ruling is to be vetoed.

### 3.5 What a FAIL means in product terms

The seasons keep arriving in an order the player cannot learn from, because knowing the
economy has turned tells them nothing about what inflation will do next — the "slot machine
with economic vocabulary" failure `O1` was written against, localised to its cause.

---

## 4. P2 — the curve-endogeneity bar

### 4.1 The plain question

How much of the generated yield curve's movement comes from the economy the engine is
simulating, and how much is drawn noise?

### 4.2 The statistic

The **strict economic share** of the generated 10y−2y slope's variance: the summed squares
of the economic components (the rule-implied policy rate, the inflation gap, the growth
season term) divided by the summed squares of everything, with **exogenous shocks in the
denominator and excluded from the numerator**. The exclusion is the whole point: on a naive
accounting week 2 scores 40.4% and week 3 scores 6.1%, but week 2's entire "explained" share
is a stand-alone mean-reverting process with no economic inputs at all — so under this
accounting week 2 scores **0.0%** and week 3 scores **2.2%**, and the gap between the two
numbers *is* the finding the bar exists to prevent recurring.

The economic components are measured on the batch; the residual standard deviation is a
model parameter. That is exactly how the anchors' own power calculation scored the
generated side, and it is stated here so an engine cannot choose which of the two it
reports.

### 4.3 The anchor

History's own curve, decomposed by **the same function**, on the **rule-implied policy
rate** rather than on the observed policy deviation — the substitution the design document
named as decisive before any of it was measured, because the simulator has no observed rate
and therefore no such object:

| component | sd (pp) | economic? |
|---|---|---|
| rule-implied policy rate | 0.836190 | yes |
| inflation gap | 0.078326 | yes |
| season term | 0.053794 | yes |
| AR(1) residual (stationary) | 0.747993 | no |

> **history's strict economic share = 0.558667 — 55.9%**, on 809 months of the campaign
> vintage, by exact AR(1) maximum likelihood.

### 4.4 The band, and why it is two-sided

> **SEALED: the generated economic share must land inside [0.391706974667,
> 0.673370849738]** — the block-bootstrap 95% interval for the same statistic on history, at
> the primary 24-month block, on the `rho`-refitted arm.

**Why the width is history's own interval.** It is the sampling interval of a statistic
measured on 68 years of one country's history — the same construction and the same
justification as `T1`'s band, which is wide for the same reason: it is what the data
supports, and narrowing it would be a modelling preference dressed as a measurement.

**Why the `rho`-refitted arm is primary.** `rho` sits at 0.981, where the residual's
stationary variance is extremely sensitive to small moves in it, so refitting `rho` on every
draw is the arm that carries the AR(1) coefficient's own sampling error into the share. The
pinned arm is narrower and is published beside it so a verdict resting on the wider arm
cannot be mistaken for one resting on the narrower.

**Why two-sided, and why the upper edge is load-bearing.** A share statistic can be driven
to 1.0 by shrinking the noise, so a one-sided "more economics is better" bar is gameable by
an engine that simply removes the surprise the product needs. And a curve 100% determined by
three macro states would be wrong in the other direction: an AR(1) residual at `rho` = 0.981
is doing a great deal of work and part of it is genuine term-premium movement that no macro
state should be asked to explain. **Anti-test 2 demonstrates the gaming route closed** and
it is not a formality: holding the loadings and shrinking the residual from 0.748 to 0.500
takes the share from 0.540 to 0.723, past the upper edge, and the judge fails it **on the
upper side** in 12 of 12 batches.

### 4.5 The pre-declared drop rule, applied

The design document pre-declared that if history's interval came back so wide that the
engines on record sat inside it, `P2` should be **dropped rather than narrowed** — the A2
low-inflation-ceiling precedent. Applied mechanically on all six arms, the closer of the two
recorded engines sits **0.359 to 0.415 below** the lower edge. **`P2` is KEPT**, and it is
not close to being uninformative.

### 4.6 What a FAIL means in product terms

Below the band, the curve a player is reading is noise wearing an economic label, and the
exam's own definition of "tight policy" is a coin toss. Above it, the curve is a
deterministic readout of the state and a player can learn a rule that no real market would
ever reward.

---

## 5. The anti-test obligations, and their results

§6.1 of the sealed exam applies to every new judge: **a judge whose pass rate does not
increase in the effect its bar claims to measure does not get sealed.** The stage-2 design
document adds four obligations per bar on top of it. All are implemented in
`scripts/stage2_antitest.py`, which imports the real judges and builds its thresholds
through the same single assembly path the seal writes, so a sweep cannot pass against
numbers that differ from the sealed ones. Full results:
`docs/superpowers/specs/stage2-antitest-results.md` (and `.json`).

**Verdict: four sweeps, all monotone non-decreasing; five controls, all hold.**

| sweep | effect swept | pass rate along the grid | monotone |
|---|---|---|---|
| `P1_coupling` | the fraction of a decade over which inflation is a lagged copy of growth | 0.17 → 0.54 → 0.96 → 1.00 → 1.00 → 1.00 → 1.00 | **yes**, saturates at 0.5 |
| `P1_coupling_lag_sensitivity` | the same sweep at 7 and 13 months instead of 10 | 1.00, 1.00 at full coupling | **yes** |
| `P2_loadings` | the scale on the three economic curve loadings, absent → history's own | 0.00 → 0.00 → 0.00 → 0.62 → 1.00 → 1.00 | **yes** |
| `P2_closeness` | closeness of the share to history's 0.5587, half above and half below | 0.00 → 0.00 → 0.46 → 1.00 → 1.00 → 1.00 | **yes** |

The mean departure keeps rising past the point `P1`'s pass rate saturates (0.006 → 0.043 →
0.086 → 0.132 → 0.204 → 0.254 → 0.291 on growth flips), so the bar is not sitting on a
plateau it could slide off — the saturation disclosure the design document requires,
because both prior campaigns found bars that rise and then fall in their own mechanism's
strength.

| control | requirement | result |
|---|---|---|
| `P1_null_engine` | at zero coupling the judge is centred on the null | mean departure **−0.00008 / −0.00011** against thresholds of 0.0403 / 0.0314 — 0.2% and 0.3% of the threshold, inside one standard error of zero — **HOLDS** |
| `P1_scramble` | scramble a passing batch and the statistic falls back to the null | departure **0.290 → −0.001** and **0.285 → −0.001**, pass rate **1.000 → 0.123** — **HOLDS** |
| `P1_retro` | every engine on the record fails | all five engine-arms fail on both move types, judged against their own nulls — **HOLDS** |
| `P2_noise_shrink` | shrinking the noise must FAIL, and fail from ABOVE | at residual 0.500 the share is 0.723 and 12 of 12 fail above the band — **HOLDS** |
| `P2_retro` | week 2 (0.0%) and week 3 (2.2%) both fail below the band | all four engine-arms fail below, and each reproduces the share the anchors recorded for it to 1e-9 — **HOLDS** |

**Two construction defects were found by these controls and both are recorded rather than
quietly fixed**, because each moved the answer by more than the residual it was measuring.
The scramble control was first written with **one shift for the whole batch**: a synthetic
growth axis is quasi-periodic, so a single shift moves every decade to the same new phase
and a shift near a whole number of cycles re-aligns them — that version left a fully coupled
batch at a mean departure of 0.054 with a 58% pass rate. Rewritten with an independent shift
per decade but **restricted to the sealed guard**, it still left +0.019 / +0.023 and 23%,
because the guard belongs to the *null* (where it stops a one-month shift from flattering the
departure) and restricting a control that must destroy alignment to that set samples phases
non-uniformly relative to the average the null estimates. Only the unguarded per-decade shift
— the uniform randomisation whose average the null *is* — collapses the statistic. Both
artifacts are properties of the shift set, not of the judge, and the docstring on
`_scramble` keeps the history.

**`P2`'s fourth obligation — one decomposition function called on both sides — is
discharged structurally rather than argued.** `judge_p2` calls
`stage2_anchors.strict_economic_share`, the same function that scored history, and the retro
control feeds it the recorded engines' committed component standard deviations and checks
that it reproduces the shares the anchors published for them.

**The ten carried bars are deliberately NOT re-swept.** Changing them is the thing a carried
bar exists to prevent, and each was anti-tested before the v2 seal.

---

## 6. The limitations register

Every entry here is measured, and every one of them would change how a stage-2 verdict
should be read. They are in the seal as `campaign_record.declared_limitations`.

**L1 — `P1`'s size is 9.0%, and that is what ruling SQ7 costs.** Against a synthetic engine
whose two dials are independent by construction, `P1` returns a PASS in **9.0% of 300
batches of fifty decades** at the sealed thresholds — against **1.3%** at the recommended
construct's own candidate (0.069084 / 0.062547) and 0.3% at the strictest published one. The
judge is not broken: its mean departure at zero coupling is +0.0006, inside one standard
error of zero. This is the bar's **size**, and every bar in this exam has one — but a 9%
size means a single PASS on `P1` is evidence of *some* phase coupling at about the
conventional strength of one significance test, not proof of it. **The size at every
published candidate is in the anti-test artifact so the trade the ruling made is visible in
numbers** — it runs 0.003, 0.007, 0.010, 0.013, 0.013, 0.013, 0.027, 0.047, 0.060, 0.090
across the eleven, and the sealed pair sits at the top of that list by construction.

**L2 — `P1`'s thresholds are pinned only to a factor of two to two and a half.** A 50 bp
move of the classifier's inflation dial — the platform's own `BACKDROP_MARGIN_PP`, not an
exotic perturbation — moves the inflation-crossing departure by 1.35 of its own standard
error, which is an **escalation** under the campaign's sealed stability rule, and the
candidate thresholds range over [0.0403, 0.0828] and [0.0314, 0.0786] across the nine arms.
A threshold sealed to six decimals under that range is quoting its dial as much as its data.

**L3 — the escalation path for a counting statistic does not exist.** The sealed rule for an
escalated statistic is "refit with soft labels and report both", which is written for
*fitted coefficients*. A clockwise fraction is a **count**, and there is no agreed
soft-label version of one. Inventing a weighting after seeing which way it moved would be a
goalpost move, so nothing was invented and L2 stands unresolved rather than papered over.

**L4 — `P1` asks for a fraction of a departure history can only just establish.** On the
uncensored construct history's own growth-flip departure has a 95% interval of
[−0.000283, 0.233050] — **not distinguishable from zero**. On the sealed construct it just
is, by 0.0066 at the lower edge, and at 12-month blocks it is not. `M3`'s gate closes the
question of whether the *channel* exists (`lam_x` = +0.00633, t = +5.95, and no shift in 694
reaches the observed likelihood ratio) but not the question of how precisely its *size* is
known.

**L5 — the engine-null substitution error is 0.0126 at worst.** Every number on the record
before the anchors' §5 substituted history's null for the batch's own. Measured on
re-simulated batches, the substitution is sound to 0.0016 in the median across the ten
judged cells and wrong by **+0.012638** at worst (`ml_link`, growth flips) — a fifth of a
candidate threshold. The sealed judge therefore computes the batch's own null, which is what
makes this a closed limitation on the anchoring rather than an open one on the judging.

**L6 — the `M4` asterisk: `P2` is kept on the pre-declared statistic and would be dropped on
one alternative summary of the identical fit.** The strict share says keep with a margin of
0.37 and the covariance-aware share agrees; the **realised R²**, whose bootstrap interval is
`[−0.2203, 0.5616]` and spans zero at every block length, says drop. The artifact records
`verdict_robust_to_the_summary = false`. The reason the R² is rejected is an estimator
pathology — an R² is ill-behaved under a GLS fit at `rho` = 0.98, because GLS minimises the
Prais–Winsten sum of squares and not the plain one, so on a resample where `rho` moves the
plain residual variance can exceed the response's — **and that reasoning is the author's and
should be checked rather than accepted.** It is the one place in the anchoring where a
defensible alternative choice flips a verdict.

**L7 — the strict share is not an explained-variance figure.** It sums squared component
standard deviations, which treats the components as uncorrelated. On the generated side they
are, by construction. On history they are not — the rule-implied rate and the inflation gap
share the inflation trend by definition and correlate at 0.705, and history's total sum of
squares is 1.78× the slope's own variance. Anyone quoting 55.9% as "56% of the curve's
movement is explained" is quoting it wrong; the number that answers *that* question is the
realised R², 0.2464.

**L8 — the ten-month lag is not pinned, and stage 2 has to choose one.** Only 57% of
bootstrap draws select within three months of ten and the classifier-cycle arm selects two.
Ruling SQ9 seals the selection rule rather than the value; whatever the fit picks must be
published with the profile beside it and never as a determined quantity.

**L9 — `P2`'s tape noise has not been measured.** Its band is cut from 2000 draws. The
adopted rule is met by an enormous margin on the arithmetic (its smallest margin is 0.369
against an O1-class 0.00076), but the check is a bound rather than a measurement, and the
anchors' §6.5 prices the measurement at hours because the share refits an AR(1) profile on
every draw.

**L10 — `P2`'s power is sampling adequacy only.** The power calculation places history's
*own* components inside history's interval at fifty decades in 2000 of 2000 replicates. It
cannot say whether a coupled engine would produce components of that size — that is week
1's question.

**L11 — history is the most favourable engine there is.** Both power figures use history
itself as the true engine, resampling the same 813 months the thresholds are cut from. They
can see sampling noise and **not** estimation error, so they are **upper bounds** on any
real engine's power. A power of 1.000 says the bar is reachable, not that it will be
reached.

**L12 — the v2 exam's own limitations are inherited whole**, including the
industrial-production-only recession dial, `T1`'s un-re-anchored downturn union, and the
absence of any 2021–22 anchor (the episode lies inside the spent holdout). None of them is
touched by anything here.

**L13 — nothing here reaches the private book.** ER-14 stands: inflation does not reach
private markets at all. Stage 2 couples the macro spine and this exam measures the macro
path and asset returns. A clean pass on both new bars leaves the translation layer's
blindness exactly where it was — and, if anything, more visible.

---

## 7. Determinism, and what is NOT sealed

- **One command per artifact.** `uv run python scripts/stage2_antitest.py` writes the
  anti-test results; `uv run python scripts/stage2_seal.py` writes the seal. Neither reads
  the network. Both are byte-identical on a re-run, verified.
- **Six literal seeds**, each used nowhere else: `SEED_P1_COUPLING = 20260831`,
  `SEED_P1_SCRAMBLE = 20260832`, `SEED_P2_LOADINGS = 20260833`, `SEED_P2_NOISE = 20260834`,
  `SEED_P2_CLOSENESS = 20260835`, `SEED_P1_NULL_ENGINE = 20260836`. They continue the run
  20260821–25 that `scripts/stage2_anchors.py` occupies. No seed is derived from another by
  a stride, and a module-level assertion holds them distinct.
- **The judges' own nulls need no seed at all.** `P1`'s within-decade scramble enumerates
  every admissible shift, so it has no Monte Carlo error whatsoever.
- **Nothing sealed was edited.** `spine-v2-prereg.json`, `spine-v2-anchors.json` and
  `stage2-anchors.json` are opened read-only and hashed into the stage-2 seal. `src/` and
  `schemas/` are untouched by everything in this campaign so far.
- **What is NOT sealed by this document:** any statement about a coupled engine. No stage-2
  fit exists. `M3` establishes the channel *in history*; the power calculation uses *history*
  as the true engine. Whether a fitted coupled system reproduces either is week 1's question.

**The standing caveat is unchanged and applies to every number above:** nothing built on
this generator line is a convincing model of history, the holdout is spent, and no appeal to
held-out data is available to any result stage 2 produces.

---

## 8. Stop-questions for the owner

1. **`P1`'s size is 9.0% at the sealed threshold and 1.3% at the recommended construct's own
   candidate.** Ruling SQ7 took the softest candidate deliberately, to keep the bar reachable
   under an anchor that a 50 bp dial move halves. The cost is now measured rather than
   assumed. If a 9% false-positive rate against an uncoupled engine is too high a price, the
   veto is one line and the alternative — 0.069084 / 0.062547 — is already in the sealed
   candidate set, so the change is an amendment naming two numbers rather than a
   re-derivation.

2. **`P2`'s tape noise is not measured (L9).** The 640,000-draw rule was adopted as binding
   and is met by arithmetic rather than by measurement on the one sealed floor that has a
   tape. Measuring it is hours. Is the bound accepted, or is the measurement bought?

3. **`P2`'s verdict is not robust to the choice of summary (L6).** Carried forward from the
   anchors' stop-question 6, untouched: the rejection of the realised R² is an
   estimator-pathology argument and it is the author's. It should be checked rather than
   accepted, because it is the one place a defensible alternative choice flips a verdict.

4. **The escalation path for a counting statistic still does not exist (L3).** `P1`'s
   inflation-crossing anchor escalates under the sealed stability rule and there is no agreed
   meaning for a soft-label weighted transition count. Nothing was invented. The owner must
   rule on what escalation means for a count, or accept L2 as permanent.

5. **`O1` stays byte-frozen and the symmetric construct is a disclosure (SQ1).** That is
   ruled, but the consequence is worth seeing once more: under the construct this exam calls
   primary, `O1`'s floor would be 0.515672 rather than 0.518067, and week 3's engine would
   still fail — by 62% of the recorded margin rather than by all of it. If stage 2's engine
   lands in that gap, the two constructs will disagree about the campaign's headline bar and
   the ruling will be worth having in writing.
