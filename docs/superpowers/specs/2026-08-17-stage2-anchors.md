# Stage 2 pre-seal measurements — M3, M4, M5, and the phase anchor

**Date:** 2026-08-17 · **Branch:** `stage2-01-anchors` · **Decision:** `D-SP-9` (stage 2
funded, owner ruling 2026-08-17)
**Status: MEASURED, NOT SEALED.** Nothing here is a bar. Every threshold below is a
*candidate*, and it becomes binding only when it is entered through the seal's
machine-checked amendment log with its judge code hashed in — which is a separate step,
after the owner has read the `P2` verdict.

> **Written in two passes, and the second one moved things.** §§1–2 are the first pass:
> `M4` and the windowing-symmetric phase re-derivation. §§3–6 are the second: `M3` as a
> gate, `M5`, the generated side's own scrambled null, and the draw count a sealed floor
> needs. The second pass **corrects a number in the first** — the null `P1`'s threshold
> should be cut from is not the one §2.4 measures, and the candidate thresholds move up
> by about 9% (§2.10, §5). Nothing in §§1–2 has been rewritten; the correction is stated
> where it belongs and cross-referenced from the affected table.

**What produced it.** `scripts/stage2_anchors.py`, one command, no network, byte-identical
re-runs verified. Its output artifact is
`docs/superpowers/specs/stage2-anchors.json`; every number quoted below is in that file
and this document adds only the derivation and the reasoning.

**House rules this document is written under** (D-SP-6's standing communication rule):
plain language; every proposed pass/fail bar states the real quantity that anchors it and
why its tolerance is the size it is; no term used without being defined once.

---

## The one-paragraph answer, after both passes

Five things were owed before either new bar could be sealed and four of them could have
killed a bar. **None did — and every one of them moved the ground.** `M3` asked whether
history establishes the growth → inflation channel at all, on a pre-declared drop rule, and
it does: inflation follows the cycle with a **ten-month lag**, coefficient **+0.00633** per
month, and **no** circular shift of the cycle out of 694 produces a likelihood ratio as
large, so **P1 is KEPT**. `M3`'s other half asks whether a correct engine could clear the
bar at fifty decades; using history itself as the true engine, **it clears it in 2000 of
2000 replicates**, and so does `P2` — so neither bar is a design defect, and the risk that
remains is the anchor's own width, not the bar's reach. `M5` moves both bars' honesty
rather than their verdicts: `M4`'s share is untouched by either classifier dial (0.038 of
its own sampling error at worst), but **`P1`'s candidate thresholds are pinned only to a
factor of two by a 50 bp move of the inflation dial**, and the inflation-crossing departure
escalates at 1.35 of its own standard error. The generated side's own scrambled null,
measured on re-simulated batches, **closes stop-question 5**: per move type the
substitution of history's null is sound to 0.013, every engine's overall null lands at
0.483–0.489 against history's 0.4884, and no recorded engine passes `P1` when judged
against its own null. And a sealed floor needs **far more draws than the campaign has ever
used**: **640,000**, measured, against the 2000 every floor on the record was cut from — the
2000-draw tape noise on the binding floor is 0.0029 against a smallest margin of 0.00076.
The first pass's answers stand: history's curve is **55.9% economics** with a
95% interval of **[0.392, 0.673]** and the two recorded engines score 0.0% and 2.2%, so
**P2 is KEPT**; symmetrising the windowing moves history's clockwise fractions **up**, not
down.

## The first pass's one-paragraph answer

Two measurements were owed before either new bar could be sealed, and each one was capable
of killing the bar it anchors. **Neither did — but each moved the ground under it.** M4
says history's yield curve, decomposed the way the engine's will be, is **55.9% economics**
with a 95% interval of **[0.392, 0.673]**; the two engines on the record score **0.0%** and
**2.2%**, far below the interval's lower edge on every one of six arms, so under the
pre-declared drop rule **P2 is KEPT** — with one honest asterisk about an alternative
summary that would have dropped it, in §1.5. The phase re-derivation says something the
verdict-integrity review did not anticipate: applying the generated side's censoring to
history moves history's clockwise fractions **up**, not down — 0.6264 and 0.6158 against
the recorded 0.6176 and 0.6111 — so **the windowing asymmetry was working in the engine's
favour, not against it**, and a symmetric comparison makes O1's shortfall larger rather
than smaller on the point estimate. The two symmetric constructs nevertheless disagree
about O1 at the margin, and the disagreement is smaller than the bootstrap's own tape
noise; that is the sharpest thing this document has to say and it is §2.6. Candidate P1
thresholds, under the construct the seal should adopt: **0.0632** on growth flips and
**0.0579** on inflation crossings.

---

## 0. What was measured, what was not, and what this is not

### What was measured

| # | item | design doc §3.3 | status |
|---|---|---|---|
| **M4** | history's curve decomposition on the **rule-implied** policy rate, with a block-bootstrap interval | listed, "the one with design content in it" | **done**, §1 |
| **M1** | history's clockwise fraction **by move type**, with its block-bootstrap interval | listed | **done**, §2.3 (all three constructs, three block lengths) |
| **M2** | history's own **phase-scrambled null** for both move types | listed | **done**, §2.4 (all three constructs, three guard bands) — **and corrected in §2.10** |
| — | the **windowing-symmetric** re-derivation the verdict's §8.1 requires | required by C1, before P1's threshold is cut | **done**, §2 |
| **M3** | the coupling's significance on the panel (**added as a gate**) and the **power calculation** at 50 decades | listed as the power calculation | **done**, §3 |
| **M5** | the decomposition's **stability under the classifier's two threshold dials** | listed | **done**, §4 — and extended to the phase anchor, which needed it more |
| — | the **generated side's own** phase-scrambled null | stop-question 5 | **done**, §5 |
| — | the **draw count** a sealed floor needs | stop-question 2 | **done**, §6 |

### What is still NOT measured

- **Anything about a coupled engine.** No stage-2 fit exists. `M3` establishes the channel
  *in history*; `M3`'s power calculation uses *history* as the true engine. Whether a fitted
  coupled system reproduces either is week 1's question and this document cannot touch it.
- **`P2`'s power against a coupled engine.** §3.7 measures whether fifty decades is enough
  months to place the share inside the interval — sampling adequacy — using history's own
  components. It cannot say whether a coupled engine would produce components of that size.
- **An escalation path for `P1` under soft labels.** §4 finds the inflation-crossing
  departure escalating under the sealed stability rule, and the sealed escalation path
  ("refit with soft labels, report both") is written for *fitted coefficients*. A clockwise
  fraction is a count, not a fit; what a soft-label version of it means is undecided, and
  that is a new stop-question rather than something this document invented an answer to.

### What this is not

It is not a fit, not a simulation and not a seal. No engine was run. No sealed file was
edited: `spine-v2-prereg.json` and `spine-v2-anchors.json` are opened read-only and their
SHA-256s are recorded in the output artifact so a later reader can prove which versions
were measured. `src/` and `schemas/` are untouched.

---

## 1. M4 — is the yield curve made of economics?

### 1.1 The plain question, and the substitution that makes it answerable

Week 3 measured that **93.9% of the generated yield curve's variance is drawn noise**, and
that the one economic-looking term in it — `û`, L1's policy *deviation* — is a stand-alone
mean-reverting process with no inputs at all. `P2` exists to turn that finding into a bar:
*how much of the curve comes from the economy the engine is simulating?*

To be a bar it needs an anchor: the same number, measured on history. The nearest thing on
the record is week 3's curve regression, `R² = 0.2223` over 809 months. The design document
says in its own words why that is not bar-grade, and the third of its four reasons is the
one M4 exists to fix:

> its main regressor is the **observed policy deviation**, which on history contains real
> economic content (the zero-bound decade, credit conditions, everything the rule missed)
> but in simulation is a synthetic process — so the two sides are **not the same object**.

So M4 changes the regressor. In place of the observed deviation it uses the **rule-implied
policy rate** — what the Taylor rule in L1 *says the rate should be*, given the economy:

```
i_rule(t)  =  r*(t)  +  pi*(t)  +  phi_pi · ( pi(t) - pi*(t) )  +  phi_c · c(t)
```

where `r*` and `pi*` are L1's slow real-rate and trend-inflation states, `pi` is trailing
12-month CPI inflation, `c` is the cycle input (+1 expanding, −1 contracting, from
`fred.USREC`), and the two coefficients are L1's own posterior means: **`phi_pi` =
0.624610**, **`phi_c` = 0.093015**.

**Why this is the decisive substitution, in one sentence.** The observed deviation is
*history minus the rule*; the simulator has no observed rate, so it has no such object —
what it has is the rule, which stage 2's coupled system will make a function of growth and
inflation. Anchoring `P2` on the deviation would compare a historical quantity full of real
economics against a simulated quantity that is noise by construction, which is the exact
mismatch the exam's §6.2 review exists to catch and the one B6's recession-or-crisis defect
already cost this campaign once.

**The reconstruction is proved, not asserted.** `scripts/spine_v2_fit.build_panel` computes
the same anchor internally and keeps only its residual. `stage2_anchors.rule_implied_states`
rebuilds it from the same three sources and then reconstructs `u_hat` from it; the maximum
absolute difference against the panel's own `u_hat` is **0.0 exactly**. Without that check
"the rule-implied rate" would be a second definition of something the campaign already has
one of.

### 1.2 The equation, and every convention in it

```
slope(t) = c0
         + c_i · ( i_rule(t) - ibar )        <- the rule-implied policy rate
         + c_x · ( x(t)      - xbar )        <- the inflation gap, pi - pi*
         + c_C·C(t) + c_E·E(t) + c_K·K(t)    <- week 3's season block, unchanged
         + e(t),      e(t) = rho·e(t-1) + eta(t)
```

Four conventions, all inherited rather than invented, and each stated so it can be
disagreed with:

1. **The season block is week 3's, unchanged** — a contracting indicator `C`, and
   `log(spell age)` on each growth axis (`E` expanding, `K` contracting), from
   `spine_v2_feedback.curve_design`. Changing its form here would make M4's anchor
   incomparable with the generated statistic it is supposed to anchor.
2. **The sample opens after the panel's first, left-truncated growth spell** — row 4,
   leaving **809 months**. That is where week 3's curve block opens, so a month's spell age
   means the same thing in both fits and the two R-squareds are comparable.
3. **The estimator is the exact Gaussian AR(1) maximum likelihood** week 3 used: a
   199-point profile scan over `rho` refined by golden section, the first observation
   entering through its own stationary law rather than being discarded. Deterministic end
   to end — no random start, no tie-break.
4. **Every regressor but the intercept is centred** on the fitted sample. Centring moves no
   variance and makes the intercept readable as the slope at the average economy.

**One extension of week 3's estimator, and why it is needed.** A block-bootstrap draw is a
*spliced* series: it pastes together randomly chosen runs of consecutive real months.
Pretending its joins are genuine month-to-month steps would let a resample invent
persistence across a join — the same corruption `spine_v2_anchors.section_e` refuses when
it drops transitions that straddle a block boundary. So the profile likelihood here treats
each contiguous stretch as its own stationary AR(1) block. **With a single block covering
the whole sample it must reduce to week 3's profile exactly, and the script proves it
rather than claiming it**: compared at five values of `rho` the maximiser did not choose,
the two independently written code paths agree on beta, sigma and the log-likelihood to
**0.0 exactly**.

### 1.3 What it says

The fit, on 809 months of the campaign vintage:

| quantity | value |
|---|---|
| `c0` (intercept, pp) | 0.602573 |
| `c_i` (per pp of rule-implied rate) | **−0.240320** |
| `c_x` (per pp of inflation gap) | **+0.492035** |
| `c_C` / `c_E` / `c_K` | −0.079260 / −0.038446 / +0.026812 |
| `rho` | 0.980949 |
| innovation sd (pp) | 0.145308 |
| realised residual sd (pp) | 0.733197 |
| implied stationary residual sd (pp) | 0.747993 |
| slope's own sd (pp) | 0.844584 |
| realised R² | **0.246374** |

Signs first, because a decomposition with the wrong signs is not worth decomposing: a
higher rule-implied policy rate **flattens** the curve (`c_i` negative) and a wider
inflation gap **steepens** it (`c_x` positive). Both are the textbook direction.

The decomposition — the same function that scores the engine, called on history:

| component | sd (pp) | economic? | squared |
|---|---|---|---|
| rule-implied policy rate | 0.836190 | yes | 0.699213 |
| inflation gap | 0.078326 | yes | 0.006135 |
| season term | 0.053794 | yes | 0.002894 |
| AR(1) residual (stationary) | 0.747993 | no | 0.559494 |
| **total** | | | **1.267735** |

> **history's economic share = 0.708242 / 1.267735 = 0.558667 — 55.9%.**

### 1.4 The interval, and why it is a block bootstrap

The interval is the campaign's standard machinery, unchanged: a stationary
(Politis–Romano) block bootstrap over the fitted sample's month sequence, 2000 draws,
2.5/97.5 percentiles, at all three block lengths the v2 anchors file uses. Seed
**20260821**, a literal used nowhere else. **Every draw is refitted from scratch** — the
`rho` search, the coefficients and the component standard deviations all move — because a
share is a fitted-model statistic and resampling only its inputs would understate its
error.

Two AR(1) treatments are reported, and the reason is that `rho` sits at 0.981, where the
residual's stationary variance `sigma²/(1−rho²)` is extremely sensitive to small moves in
`rho`:

| block | `rho` refitted per draw (**primary**) | `rho` pinned at the point estimate |
|---|---|---|
| 12 months | [0.4294, 0.6582] | [0.4371, 0.6195] |
| **24 months (primary)** | **[0.3917, 0.6734]** | [0.4348, 0.6284] |
| 36 months | [0.3819, 0.6841] | [0.4166, 0.6286] |

The refitted arm is the primary because it is the honest one: it carries the AR(1)
coefficient's own sampling error into the share. The pinned arm is reported so the reader
can see how much of the width is `rho` (about a fifth of it) and so that a verdict resting
only on the wider arm cannot be mistaken for a verdict resting on the narrower one. The
median refitted `rho` across draws is **0.979856** against the point estimate's 0.980949,
so the block resampling does **not** materially bias the persistence downward — which was
the one way this estimator could have flattered the share.

### 1.5 The pre-declared acceptance rule, applied

The rule, quoted from the design document §3.3 and applied without adjustment:

> if it comes back with an interval so wide that the engines on record sit inside it, **P2
> should be dropped rather than narrowed** — the precedent is A2's low-inflation ceiling,
> dropped pre-seal rather than moved once its cost was visible.

The engines on the record, scored by **the same function** that scored history — their
component standard deviations read from week 3's committed artifact, nothing restated by
hand and nothing re-simulated:

| engine / arm | `û` sd (pp) | season sd (pp) | residual sd (pp) | **strict economic share** |
|---|---|---|---|---|
| `week2`, unconditional | 0.535801 | 0.000000 | 0.650389 | **0.000000** |
| `week2`, premise-accepted | 0.535801 | 0.000000 | 0.650389 | **0.000000** |
| `feedback` (week 3), unconditional | 0.148625 | 0.113170 | 0.731445 | **0.022473** |
| `feedback` (week 3), premise-accepted | 0.148625 | 0.095368 | 0.731445 | **0.016108** |

Those reproduce the design document's `0.0%` and `2.2%` exactly, which is worth stating as
its own result: **P2's fourth anti-test obligation — "the decomposition function must be a
single piece of code called on both sides, with the sides differing only in their input
array" — is discharged in advance**, on the only two generated batches that exist.

**The test.** History's interval must exclude both. It does, on every arm:

| arm | interval | week 2 (0.0000) inside? | week 3 (0.0225) inside? | how far below the lower edge week 3 sits |
|---|---|---|---|---|
| 12m, refitted | [0.4294, 0.6582] | no | no | 0.4069 |
| 24m, refitted | [0.3917, 0.6734] | no | no | 0.3692 |
| 36m, refitted | [0.3819, 0.6841] | no | no | 0.3594 |
| 12m, pinned | [0.4371, 0.6195] | no | no | 0.4146 |
| 24m, pinned | [0.4348, 0.6284] | no | no | 0.4123 |
| 36m, pinned | [0.4166, 0.6286] | no | no | 0.3941 |

> ### ⚑ **P2 IS KEPT.** The *closer* of the two recorded engines sits **0.359 to 0.415 below** the lower edge of history's interval, on every one of six arms; week 2 sits further below still. The bar is not close to being uninformative.

**The same test on two other summaries of the same fit — and one of them does not agree.**
§1.6(a) explains why the strict share is not the only defensible summary, so the test was
run on two others as a check on itself. The result is split, and both halves are reported
because the disagreeing one is informative:

| summary | 24-month interval | median | engines inside? |
|---|---|---|---|
| **strict economic share (pre-declared)** | [0.3917, 0.6734] | 0.5595 | **no** |
| covariance-aware share | [0.4257, 1.3592] | 0.8145 | no |
| realised R² | **[−0.2203, 0.5616]** | 0.2774 | **yes** |

**The realised R² cannot be block-bootstrapped meaningfully on this equation, and that is
a finding rather than an excuse.** Its interval spans zero at every block length (12m
[−0.0954, 0.5231]; 36m [−0.2903, 0.6037]). The mechanism is mechanical: R² is
`1 − var(residual)/var(slope)` computed with *generalised* least-squares coefficients. GLS
does not minimise the plain sum of squares — it minimises the Prais-Winsten-transformed
one — so on a resample where `rho` moves, the plain residual variance can and does exceed
the response's. That is a statement about how an R² behaves under a GLS fit at `rho` = 0.98,
not a statement about the yield curve.

Two consequences, in order of importance. First, **it retro-justifies the design document's
own complaint** that week 3's `R² = 0.2223` "has no sampling interval": the interval, now
measured, is `[−0.22, 0.56]` and is useless as a bar. Second, **it means the P2 verdict is
robust to one alternative summary and not to the other**, and the artifact records
`verdict_robust_to_the_summary = false` rather than hiding it. The pre-declared statistic is
the strict share — it is the function the engine is scored by, which is P2's fourth
anti-test obligation and the reason it is primary — and on it, on every one of six arms, the
bar survives with room. But an owner reading "P2 is KEPT" is entitled to know that a
differently-chosen summary of the identical fit would have dropped it, and that the reason
the differently-chosen summary is rejected is an estimator pathology and not a preference.
This is stop-question 6.

### 1.6 Four things about this number that would be dishonest to leave out

**(a) 55.9% is not "56% of the curve's movement is explained".** The strict share sums
*squared component standard deviations*, which treats the components as uncorrelated. On
the generated side they are, by construction: `û`, the season term and the residual are
separate draws. On history they are **not** — the rule-implied rate and the inflation gap
share the inflation trend by definition, and their correlation on the fitted sample is
**0.705**. The consequence is measurable and is measured: history's total sum of squares is
**1.78×** the slope's own variance. The number that answers "how much of the curve's
movement does this equation explain" is the **realised R², 0.2464**. Both are in the
artifact. The strict share is the primary *because it is the function the engine is scored
by* — that identity is P2's fourth anti-test obligation and it outranks elegance — but
anyone quoting 55.9% as an explained-variance figure is quoting it wrong.

**(b) The substitution raises the measured share, and that direction deserves stating.**
The identical equation with the observed deviation in column 1 instead of the rule-implied
rate — and counting that deviation *generously*, as if it were economic — scores **0.1654**
against M4's 0.5587. The mechanism is not subtle and is not a modelling choice: `u_hat` is
standardised to unit variance and loads at 0.179 pp, while the rule-implied rate has a
standard deviation of about 3.48 pp (it is dominated by the inflation trend, which ran from
about 1% to about 9% across this panel) and loads at −0.240 pp per pp. The rule-implied rate
simply carries far more variation. **Choosing the regressor that gives the bigger number
would be indefensible if the choice had been made after seeing it; it was not** — the
substitution is named as decisive in the design document's §3.3, written and committed
before this measurement existed, and the reason given there is a definition-mismatch
argument that does not mention the direction of the effect. It is recorded here because a
reader is entitled to check that.

**(c) The season term is the smallest of the three economic components by a factor of
fifteen** (0.0538 pp against the policy term's 0.8362 pp). That is why M5 — the
decomposition's stability under the classifier's two threshold dials — is *less* load-bearing
for M4 than it was for week 3's fit, where the season block was the deliverable. It is not
a reason to skip M5: the season block is a function of the labels, week 3 found one such
coefficient pinned only to a factor of 2.5, and M5 remains on §3.3's list.

**(d) An AR(1) residual with `rho` = 0.981 is doing a great deal of work.** Part of it is
genuine term-premium movement that no macro state should be asked to explain — the design
document's fourth reason for making P2 two-sided, and it stands. The share is not a claim
that 44% of the curve is meaningless noise; it is a claim about what three macro states can
and cannot reach.

---

## 2. The windowing-symmetric phase anchor — P1's re-derivation

### 2.1 What the review demanded, and why

The verdict-integrity review's finding **C1** is on the record at
`2026-08-17-spine-v2-results.md` §8.1. In one sentence: the sealed `O1` judge censors the
first twelve months of every generated decade — their trailing-inflation warm-up, **12 of
every 120, about 10%** — while the historical side loses one warm-up in 813 months, about
**1.5%**. Every phase anchor the campaign has ever quoted (0.6176 on growth flips, 0.6111
on inflation crossings, 0.5972 overall) was measured on the **uncensored** panel. The
review's ruling:

> any stage-2 seal must **re-derive the phase anchor under windowing-symmetric constructs —
> both sides losing the same fraction of their months — before P1's threshold is cut**, and
> before O1's shortfall is cited as the size of the problem P1 exists to fix.

**The sealed O1 verdict is not reopened by anything below**, and this document does not
attempt to. `O1` FAILED at 0.511765 against 0.5180669104991394 under the sealed construct,
and that stands. What follows is what a *stage-2* anchor would be.

### 2.2 The two symmetric constructs

"Symmetric" can mean two things and both are computed.

**(a) Censored on both sides — history put through the engine's own windowing machine.**
Cut the panel into 120-month windows, drop each window's first 12 months, count the
transitions that survive, pool. That is exactly what the sealed judge does to a generated
batch, so on this construct **the generated side does not move at all** — only the anchor
does. Two window rules are reported, following `spine_v2_anchors.section_k`'s precedent
exactly:

- **overlapping** — one window per start row (694 of them), so every month the panel has is
  used. **This is section K's primary.**
- **disjoint** — non-overlapping decades from row 0 (6 of them), so every month is used at
  most once. The sensitivity check on the overlapping version's uneven month weighting; it
  rests on a handful of decades and is a check, not an anchor.

**(b) Uncensored on both sides.** History read as one 813-month run — the construct every
anchor on the record was measured on — beside the simulator's **internal** season index,
the object week 3's `o1_decomposition` scored and the one that reads 0.5241 overall.

**One implementation note, because the shortcut is load-bearing.** The pooled
overlapping-window fraction is computed as a *weighted* fraction over the panel's own
transitions — the transition between rows `t` and `t+1` is counted once per window that
contains both of them outside the warm-up — rather than by looping over 694 windows. That
is exact, and the script proves it by running the literal loop once and comparing:
**6639 transitions, 4030 clockwise, matched exactly.** The shortcut is what makes the
scramble null and the bootstrap affordable at full resolution.

### 2.3 The measurement

Clockwise fractions, by move type. A **growth flip** changes the growth answer only; an
**inflation crossing** changes the inflation answer only; a **diagonal** changes both, and
no diagonal pair is in the clock, so diagonals are counter-clockwise by construction and
are reported separately rather than folded into either type.

| construct | growth flips | inflation crossings | overall | weighted transitions |
|---|---|---|---|---|
| **uncensored both sides** | **0.617647** (21/34) | **0.611111** (22/36) | 0.597222 (43/72) | 72 |
| **windowed, overlapping** | **0.626416** (1935/3089) | **0.615814** (2095/3402) | 0.607019 (4030/6639) | 6639 |
| windowed, disjoint | 0.666667 (18/27) | 0.617647 (21/34) | 0.619048 (39/63) | 63 |

The uncensored row reproduces the sealed `grader_v2` ordering anchor **exactly** — 43
clockwise of 72 transitions — and the script refuses to continue if it does not.

> ### The finding the review did not anticipate
>
> **Symmetrising the windowing moves history's clockwise fraction UP, not down.**
> Overlapping windows: +0.0088 on growth flips, +0.0047 on inflation crossings, **+0.0098
> overall**. Disjoint windows: +0.0490, +0.0065, **+0.0218 overall**.
>
> §8.1 established that the censoring costs the *generated* side about **+0.0124** on the
> judged cell, and inferred that the asymmetry was penalising the engine. It is now
> measured that the same treatment *helps* history by a comparable amount. So on the point
> estimates, **a windowing-symmetric comparison makes the engine's shortfall larger, not
> smaller**: history 0.6070 against the engine's 0.5118, a gap of 0.0952, where the sealed
> mixed construct showed 0.5972 against 0.5118, a gap of 0.0854.
>
> Why it happens is mechanical rather than mysterious. A 120-month window drops the
> transitions that touch its warm-up edge, and the same edge effect that shortens
> decade-measured dwell medians (section K's `why_the_same_window_on_both_sides`) reweights
> which transitions are counted. History and the engine respond to it in the same
> direction; they do not respond by the same amount.

### 2.4 The independence null, measured rather than assumed

`P1` is not written on the clockwise fraction. It is written on the fraction's **departure
from what independent dials would give on the same batch** — which the design document
claims is ≈ 0.500 and requires to be measured.

**The construction**, from §3.1: circularly shift the inflation dial against the growth
axis, which preserves each dial's own dynamics — its run lengths, its hot share, its
persistence — and destroys only their alignment; rescore; average.

**Two deliberate departures from "many times", both toward exactness.**

1. **Every admissible shift is enumerated, not sampled.** With 813 months there are 812
   non-trivial shifts; all of them are scored. The null therefore needs **no seed** and has
   **no Monte Carlo error at all**.
2. **Shifts smaller than a guard band are excluded.** A one-month shift destroys almost
   none of the alignment, so including tiny shifts drags the null toward the measured value
   and flatters the departure the bar is cut from. The primary guard is **60 months** — five
   years, an order of magnitude beyond the several-quarter lag the growth → inflation
   channel is supposed to operate at. **Why that size and not another:** it is large enough
   that no plausible lag survives it and small enough to keep 694 of the 812 shifts, and
   the choice is shown not to matter — 0 months (all 812 shifts) and 120 months are both
   reported, and the three agree to about **0.001** on every construct.

The measured nulls, at the primary 60-month guard:

| construct | growth flips | inflation crossings | overall |
|---|---|---|---|
| uncensored both sides | 0.500283 | 0.500132 | **0.488440** |
| windowed, overlapping | 0.500084 | 0.499981 | **0.488401** |
| windowed, disjoint | 0.502961 | 0.501358 | **0.490623** |

**Two results, one confirming and one corrective.**

- **Per move type, the design document's ≈ 0.500 is right** — every value sits within 0.003
  of a coin flip, and the two primary constructs within 0.0003. The structural argument
  (down-flips and up-flips are equally helped and hurt by an unaligned inflation dial, so
  they cancel) is now a measurement.
- **The OVERALL null is not 0.500. It is 0.4884.** The diagonal moves are the reason: they
  are never clockwise, they are about 2–3% of transitions, and they pull the pooled fraction
  below a coin flip. **This matters for reading `O1`, which is the overall statistic**: its
  sealed floor of 0.5181 sits **0.0297 above its own independence null**, not 0.0181 above
  it. Nobody has been quoting it wrongly — the floor was always cut from history's own
  interval, not from 0.500 — but any sentence of the form "O1 asks for 0.018 better than a
  coin flip" understates what it asks by about 40%.

### 2.5 Which construct the stage-2 seal should adopt

**Adopt (a), censored on both sides, with overlapping windows.** The reason is one
sentence long and the rest is its consequences: *the censoring is a property of what the
engine emits, not of how it is judged.* A generated decade genuinely has no trailing
12-month inflation for its first twelve months — that is arithmetic, not a judging choice —
so the object the sealed pipeline produces, and the only object a player would ever see, is
a censored decade. The alternative symmetric construct removes the censoring from both
sides, which on the generated side means scoring the simulator's **internal** season index:
an array the dataclass itself documents as "always defined internally", that the sealed
judge never touches, that the product never shows, and that exists only because the
simulator happens to keep it. Judging that array is judging a thing the engine does not
ship. Putting history through the same windowing machine instead is the identical remedy
**PRE-SEAL RULING 1** applied to D1–D4 and **section K** applied to the dwell anchors — the
campaign has already ruled twice that the fix for a windowing mismatch is to window both
sides, not to un-window one — and it is the only one of the two symmetric constructs that
leaves the judged object unchanged. Overlapping rather than disjoint windows because
overlapping uses every month the panel has, which is section K's own primary choice for the
same statistic class; disjoint rests on six decades, its growth-flip fraction jumps to
0.6667 on 27 transitions, and it is reported as the sensitivity it is. The uneven month
weighting overlapping windows impose is real and is disclosed in the artifact in section
K's own words.

### 2.6 O1 under each construct — the reconciliation completed

This is the part the record was missing. §8.1 measured the generated side's construct gap
and left "whether a windowing-symmetric O1 would be cleared by this engine" explicitly
**unmeasured**. Here it is, with each engine's reading placed beside the floor its own
construct implies. All floors are 24-month block, 2.5th percentile, 2000 draws, cut on this
module's tape.

| history construct | O1 floor | week 3 `feedback` reading | clears? |
|---|---|---|---|
| **windowed, overlapping (recommended)** | **0.515672** | 0.511765 (the sealed, censored value — unchanged) | **NO**, short by 0.003907 |
| uncensored both sides | 0.519987 | 0.524138 (the internal, uncensored path) | **YES**, over by 0.004151 |
| windowed, disjoint (sensitivity) | 0.510627 | 0.511765 | YES, over by 0.001138 |
| *sealed construct, for reference* | *0.518067* | *0.511765* | *NO, short by 0.006302* |

**And it is not one engine's story.** All four engines the campaign fitted, on both arms —
eight cells — were checked the same way. **Under the recommended symmetric construct, none
of the eight clears**, the closest being `ml_link` unconditional at 0.514563 against 0.515672
(short by 0.0011). Under the uncensored construct, **four of the eight clear**. So the
construct choice does not merely move one verdict at the margin; it moves half of them.

**Read the table carefully, because three things in it are easy to get wrong.**

1. **The two symmetric constructs disagree.** Under the one this document recommends, O1
   still fails; under the other, it clears. Neither is a verdict — the sealed verdict is the
   verdict — but it means "a symmetric O1 would have been passed" is **not** a safe
   inference from §8.1, and neither is its opposite.
2. **The margins are the same size as the bootstrap's own tape noise, and that is measured
   rather than guessed.** Re-running the *uncensored* construct on the **sealed ordering
   seed** reproduces O1's sealed floor of `0.5180669104991394` **exactly** — which proves
   the machinery here is the machinery there, and isolates construct from draw. The same
   statistic on this module's own seed gives 0.519987. **So two honest bootstraps of the
   identical quantity at 2000 draws differ by 0.0019**, and every margin in the table above
   is between 0.0011 and 0.0063. A floor quoted to four decimals is quoting its tape as much
   as its data.
3. **Symmetrising raises history's point estimate but *lowers* its floor** (0.6070 vs
   0.5972 on the point; 0.515672 vs 0.519987 on the 24-month lower edge, paired on one
   tape). There is no contradiction: the windowed statistic is a weighted fraction over
   re-used months, and its bootstrap distribution is wider. The bar is cut from the lower
   edge, so the wider interval wins.

**The consequence for stage 2, stated plainly.** If the seal adopts the recommended
construct, O1's floor moves from 0.518067 to about 0.5157 and week 3's engine still fails —
by about 62% of the recorded margin. That is a real narrowing of the gap stage 2 has to
close, and it is **not** the "O1 was unfairly censored" story: on the point estimates the
symmetric comparison is *worse* for the engine, and only the interval's width moves the
floor down. Both halves of that need saying together or the number gets misread.

### 2.7 P1's candidate thresholds

`P1`'s tolerance is the design document's, unchanged: **half of history's own measured
departure from the batch's phase-scrambled null**, for both move types. The fraction ½ is
declared in code as a constant, so changing it would be a visible edit.

| construct | move type | history | null | **departure** | **candidate P1 threshold** |
|---|---|---|---|---|---|
| **windowed, overlapping** | growth flips | 0.626416 | 0.500084 | 0.126332 | **0.063166** ‡ |
| **(recommended)** | inflation crossings | 0.615814 | 0.499981 | 0.115833 | **0.057917** ‡ |
| uncensored both sides | growth flips | 0.617647 | 0.500283 | 0.117364 | 0.058682 |
| | inflation crossings | 0.611111 | 0.500132 | 0.110979 | 0.055489 |
| windowed, disjoint | growth flips | 0.666667 | 0.502961 | 0.163706 | 0.081853 |
| | inflation crossings | 0.617647 | 0.501358 | 0.116289 | 0.058145 |

The uncensored row reproduces the design document's stated candidates (0.059 growth, 0.056
inflation) to three decimals, which is the expected result and a check that nothing drifted.
**The recommended construct raises both thresholds by about 8% and 4% respectively** — a
slightly harder bar, in the same direction as §2.3's finding.

> ‡ **These two numbers are superseded.** The second pass found that the null they are cut
> from is not the null a *batch* admits: shifting one 813-month panel is not the operation
> a set of independent decades can perform on itself. Cut from the null P1 actually admits,
> the candidates are **0.069084** and **0.062547**. §2.10 has the correction and §5 has the
> measurement that forced it. The rest of this section — the fractions, the intervals, the
> construct recommendation — is unaffected.

**Why half, restated because it is the whole justification.** Each move type rests on about
35 transitions in the uncensored count. Demanding history's *point* value would fail a
correct engine roughly half the time — the exact defect O1's own §2(c) was rewritten to
avoid. Half of history's departure is the widest tolerance that keeps three properties, and
two of the three are checkable now: an engine with independent dials fails **by
construction** (its departure is zero); and both engines on the record fail it (§2.8). The
third — that an engine reproducing history's phase relation passes with room — is what M3's
power calculation is for and it is **not yet measured**.

### 2.8 The anti-test that can be run now

P1's third anti-test obligation is the retro-anti-test: *"Judge week 2's and week 3's
committed engines with the new judge. Both must fail. A new bar that passes an engine on the
record as uncoupled is void."* Their by-move-type clockwise fractions are committed in week
3's artifact, so this can be checked before any stage-2 code exists.

| engine / arm | growth flips | departure | inflation crossings | departure | passes? |
|---|---|---|---|---|---|
| `week2`, unconditional | 0.542222 | 0.042138 | 0.541538 | 0.041558 | **no** |
| `ml_link`, unconditional | 0.541667 | 0.041582 | 0.546012 | 0.046031 | **no** |
| `ols_feedback`, unconditional | 0.526531 | 0.026446 | 0.537037 | 0.037056 | **no** |
| `feedback` (week 3), unconditional | 0.536170 | 0.036086 | 0.547692 | 0.047711 | **no** |

against thresholds of 0.063166 and 0.057917. **Every engine on the record fails on both
move types, under every construct.** The obligation holds.

**Two honest qualifications.** First, each engine's departure is taken against **history's**
null, not its own — measuring the generated side's own scramble needs the batches
re-simulated, which this module does not do, and it is a prerequisite for *sealing* P1
rather than for anchoring it. On this panel every per-move null is within 0.001 of 0.500 and
the argument for 0.500 is structural, so the substitution is small; it is still a
substitution. Second, the closest engine is `feedback` on inflation crossings, failing by
**0.0102**. That is not a comfortable margin, and it is smaller than the margin the
uncensored construct would give.

### 2.9 How thin this evidence is

The design document said the sampling error on 35 transitions is "larger than the entire
departure being measured". That is now measured rather than estimated, and it is worse than
it sounds for one of the two move types.

Departure intervals, 24-month block, 2000 draws (the fraction's bootstrap interval, shifted
by the null):

| construct | move type | departure | 95% interval |
|---|---|---|---|
| uncensored | growth flips | 0.117364 | **[−0.000283, 0.233050]** |
| uncensored | inflation crossings | 0.110979 | [0.031118, 0.205750] |
| **windowed, overlapping** | growth flips | 0.126332 | **[0.006581, 0.238559]** |
| **windowed, overlapping** | inflation crossings | 0.115833 | [0.026294, 0.205675] |

**On the uncensored construct, history's own growth-flip phase relation is not
distinguishable from zero at 95%.** On the recommended construct it just is — the lower edge
clears zero by 0.0066 — and at 12-month blocks it does not (lower edge 0.4725 against a null
of 0.5001, i.e. −0.0276). This is the single most important caveat on P1 and it belongs in
the seal, not in a footnote: **P1 asks a generated engine to reproduce half of a departure
that history itself can only just distinguish from zero.** That is not a reason to abandon
the bar — the alternative is no phase bar at all, and an uncoupled engine still fails by
construction — but it is a reason the owner should see the interval before the threshold is
sealed, and a reason M3's power calculation is load-bearing rather than procedural.

### 2.10 The null P1 actually admits — a correction to §2.4 and §2.7

**What went wrong, in one sentence.** `P1`'s null is defined as *the batch's own* phase
scramble; §2.4 computed it by shifting one 813-month panel; **a generated batch is fifty
independent decades and cannot perform that operation on itself.** The only scramble a
batch admits is a shift *inside* each decade, and the two do not give the same number.

**The like-for-like construction.** Cut history into the same 694 overlapping 120-month
windows the recommended construct already uses, shift the hot/cool dial circularly **within
each window** (the same shift in every window), drop each window's first twelve months as
the judge does, pool, and average over every admissible shift. The guard band cannot stay at
60 months — inside a 120-month decade `min(k, 120−k) ≥ 60` admits exactly one shift — so it
comes down to **24 months**, which is more than twice the ten-month lag §3 measures for this
channel and still leaves 73 of the 119 shifts. Exhaustive, so still seedless.

| construct | move type | history | panel-wide null (§2.4) | **within-window null** | departure | **corrected threshold** |
|---|---|---|---|---|---|---|
| **windowed, overlapping** | growth flips | 0.626416 | 0.500084 | **0.488248** | 0.138168 | **0.069084** |
| **(recommended)** | inflation crossings | 0.615814 | 0.499981 | **0.490721** | 0.125093 | **0.062547** |
| windowed, disjoint | growth flips | 0.666667 | 0.502961 | 0.500500 | 0.166167 | 0.083083 |
| | inflation crossings | 0.617647 | 0.501358 | 0.488643 | 0.129004 | 0.064502 |

**Three things follow and all three matter.**

1. **The thresholds rise by about 9% and 8%.** A bar cut from the panel-wide null would have
   been about a tenth easier than the bar `P1` says it is.
2. **The overall null moves much further — from 0.4884 to 0.477281.** Diagonal moves are
   never clockwise (§2.4) and a short window catches proportionally more of them, so any
   sentence about how far `O1`'s floor sits above "the independence number" depends on which
   of the two constructions is meant. This document does **not** re-cut `O1` on it; that is
   stop-question 1 and it remains the owner's.
3. **The guard band matters more here than it did on the panel.** At 12 and 36 months the
   within-window nulls read 0.4834/0.4901 (growth) and 0.4859/0.4923 (inflation) — a spread
   of about 0.007, where the panel-wide null moved by 0.001 across its three guards. A
   120-month window has less room to be shifted in, so the guard is a real choice; 24 months
   is the declared primary and both sensitivities are in the artifact.

**Why this is a correction and not a preference.** The test is not which null is prettier;
it is which operation both sides can perform on the object each of them has. §5 measures the
generated side's own null by doing exactly this to five re-simulated batches, and confirms
the construction works there — which is what makes it like-for-like.

---

## 3. M3 — the growth → inflation coupling, and whether P1 is askable

### 3.1 Why this is a gate, and what was declared before the number was read

`P1` asks a generated engine to reproduce **half of history's growth/inflation phase
relation**. §2.9 showed how thin that anchor is. Stop-question 3 asked whether the bar is
worth sealing at all and said M3's power calculation should be treated as a gate rather than
a formality. This section takes that instruction literally, and puts a cheaper and more
decisive question in front of it:

> before asking whether an engine can reproduce the channel, ask whether **history
> establishes that the channel exists.**

If it does not, `P1` demands of the engine a fact the panel does not contain, and the
precedent is the one the design document names for `P2` — **A2's low-inflation ceiling,
dropped pre-seal rather than narrowed** once its cost was visible.

**The pre-declared rule, written into `scripts/stage2_anchors.py` before any number was
read, and applied mechanically:**

> `P1` is **DROPPED** unless all three hold —
> **(i)** the likelihood ratio against no coupling rejects at 95% under a **selection-aware**
> null that prices the 25-lag search;
> **(ii)** the block-bootstrap 95% interval for `lam_x` excludes zero at **every** one of the
> three block lengths, on **both** the held-lag and the re-selected-lag arm;
> **(iii)** `lam_x` has the sign the mechanism requires — **positive**, inflation rising after
> expansions.

Three conditions because each covers a different way of being wrong: the search, the
residual's dependence, the direction. Any one failing drops the bar.

### 3.2 The equation, and every convention in it

The design document's own inflation line, §2.2, with `dt` one month:

```
x_{t+1} = a·x_t + lam_x·( c_{t-m} - cbar ) + e_t
```

- `x` is the **inflation gap** — trailing 12-month CPI inflation minus L1's slow trend `pi*`
  — the same array M4 uses as its second regressor, built once.
- `c` is the **cycle input**, +1 expanding and −1 contracting, from `fred.USREC`. That is the
  WP2.6 contract L1 already consumes; it is **not** the classifier's growth axis, and §3.5
  reports what happens if it is.
- `a = 1 − k_x` is the gap's own persistence. Least squares **is** the Gaussian maximum
  likelihood for this equation, so the restriction `lam_x = 0` is nested exactly and the test
  is a likelihood ratio rather than an argument.

Two sample conventions, both stated so they can be disagreed with. **The warm-up is
dropped:** `build_panel` fills the first twelve months' inflation with the trend, which sets
the gap to exactly zero, and twelve manufactured zeros at the head of a persistence
regression would read as persistence. **Every lag is fitted on the same months** — the
sample opens at the longest lag in the grid — because selecting a lag by likelihood across
samples of different lengths is not a comparison. Of 813 panel months, 801 have trailing
inflation and **788 rows** survive both rules.

**And one limitation that is not a convention but a fact about the inputs.** The inflation
gap subtracts L1's *estimated* trend, so `x` is a generated regressor and the uncertainty in
`pi*` is not propagated into the interval below. That understates the standard error by an
unmeasured amount. It does not touch the gate: the selection-aware null shifts the same
constructed `x` against the same `c` and therefore inherits exactly the same construction, so
whatever `pi*`'s estimation does to the statistic it does to the null as well.

### 3.3 The lag profile, published whole

The grid is 0–24 months, declared in code, nothing searched outside it, every lag costing
the same one parameter.

| lag (months) | 0 | 5 | 7 | **9** | **10** | 12 | 15 | 19 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| `lam_x` | +0.00366 | +0.00538 | +0.00577 | +0.00632 | **+0.00633** | +0.00433 | +0.00186 | +0.00381 | +0.00019 |
| t-ratio | +3.25 | +4.97 | +5.40 | +5.92 | **+5.95** | +4.08 | +1.76 | +3.69 | +0.18 |
| LR vs no coupling | 10.51 | 24.37 | 28.70 | 34.44 | **34.80** | 16.50 | 3.09 | 13.51 | 0.03 |

The profile has one broad hump centred on nine to ten months and falls away sharply past a
year. **The likelihood selects ten months.** Nine is all but tied (34.44 against 34.80), and
the profile does **not** pin the lag tightly — §3.4's bootstrap says so in numbers.

**One coincidence worth naming so it is not over-read.** The curve's own lead, selected by
likelihood in week 2, is nine months. This lag is ten. They are two different channels
measured on two different equations and their near-agreement is not evidence for either.

### 3.4 What it says

| quantity | value |
|---|---|
| `lam_x` (pp of inflation gap per month, per unit of cycle) | **+0.006326** |
| standard error | 0.001063 |
| t-ratio | **+5.95** |
| persistence `a` | 0.994814 |
| **long-run gap at a fully expanded economy, relative to the average one** | **+0.313 pp** |
| likelihood ratio against no coupling | **34.80** |
| nominal chi-square(1) p-value | 3.6 × 10⁻⁹ |
| residual lag-1 autocorrelation | 0.198 |

**The nominal p-value is not the test, and the reason is structural.** The inflation gap is
built from a *trailing* 12-month rate, so consecutive months share eleven of their twelve
price changes and the residual carries a moving-average structure by construction — the
measured lag-1 residual autocorrelation is 0.198. A chi-square read off a likelihood ratio
assumes independent innovations and will overstate the evidence. So the gate rests on two
devices that carry the dependence, and the nominal number is reported only for scale.

**Device one — the selection-aware null.** Circularly shift the cycle input against the
inflation gap, which preserves each series' own dynamics and destroys only their alignment;
refit the whole 25-lag grid on the shifted pair; keep its **best** likelihood ratio. That
maximum's distribution is what a 25-lag search finds on two unrelated series. Every
admissible shift beyond a 60-month guard is enumerated — 694 of them, so no seed.

| the max-LR null over 694 shifts | median | 95th | 99th / largest | observed |
|---|---|---|---|---|
| | 6.07 | 13.03 | 20.59 | **34.80** |

**No shift, out of 694, reaches the observed statistic.** The plug-in p-value that counts the
observation as one of its own draws is therefore **0.00144** — the smallest this
construction can produce — and the same value holds when the null is taken at the selected
lag alone rather than over the grid, so the search is not what is carrying the result.

**Device two — the block bootstrap.** Rows are resampled in runs, which is what carries the
moving-average structure into the interval.

| block | `lam_x`, lag held at 10 | `lam_x`, lag re-selected each draw |
|---|---|---|
| 12 months | [+0.002205, +0.011273] | [+0.003601, +0.011947] |
| **24 months (primary)** | **[+0.001667, +0.011721]** | [+0.003090, +0.012665] |
| 36 months | [+0.001145, +0.012060] | [+0.002849, +0.012842] |

**Every interval excludes zero, on both arms, at all three block lengths.** The re-selected
arm is the honest one for a coefficient whose lag was chosen by likelihood, and it is the
*stronger* of the two — re-selecting per draw finds a coupling somewhere on the grid more
reliably than lag ten holds up.

**And the one thing that is NOT well determined, said plainly.** The bootstrap's median
selected lag is eight to nine months, and only **57%** of draws select within three months
of ten. **The coefficient is solid; the lag is not.** Anything downstream that depends on the
lag being ten rather than seven or twelve is resting on the wrong half of this measurement.

### 3.5 The sensitivity that could have broken it

The cycle input is a contract, so the obvious question is whether the channel is a property
of the economy or of the array chosen to represent it. Refitting the identical equation with
the **classifier's own growth axis** (`grader_v2`'s contracting labels) in place of
`fred.USREC`:

| arm | selected lag | `lam_x` | t-ratio |
|---|---|---|---|
| **primary — `fred.USREC`** | **10 months** | **+0.006326** | **+5.95** |
| classifier's growth axis | 2 months | +0.005021 | +6.10 |

Same sign, same order of size, comparable significance — **and a completely different lag.**
That is one more reason to treat the ten months as unpinned, and no reason at all to doubt
the channel.

### ⚑ 3.6 THE GATE VERDICT: **P1 IS KEPT**

| condition | required | measured | holds |
|---|---|---|---|
| (i) selection-aware rejection at 95% | p ≤ 0.05 | **0.00144** | **yes** |
| (ii) bootstrap excludes zero, all blocks, both arms | 6 of 6 | 6 of 6 | **yes** |
| (iii) sign positive | `lam_x` > 0 | +0.006326 | **yes** |

**History establishes the channel `P1` exists to test.** What that does and does not mean:
it means the bar is *askable* — the panel contains the fact the bar demands the engine
reproduce. It is **not** a statement that any engine can reach it, and it is **not** a
verdict on the recorded engines. The design document's **cheap exit A** — *"if `lam_x` is
not significant on the panel, stop"* — **does not fire.**

### 3.7 The power calculation — can a correct engine clear these bars?

The exam's standing rule is that **a bar a correct engine cannot clear is a bar-design
defect**, and two bars were caught that way pre-seal. The design document says this needs "a
true engine emitting real 120-month stretches". There is no stage-2 engine, so the true
engine used here is **history itself**: each replicate draws 50 real 120-month stretches with
replacement and puts them through the judge exactly as a generated batch goes through it —
first twelve months of each stretch censored, the rest pooled, the batch's **own**
within-window null computed from its own decades (§2.10's construction). 2000 replicates,
one literal seed, 50 decades because that is the sealed batch size.

| bar | statistic on the true engine | threshold / band | **power** |
|---|---|---|---|
| **P1**, growth flips | departure 0.1388, 95% [0.1053, 0.1752] | ≥ 0.069084 | **1.000** |
| **P1**, inflation crossings | departure 0.1251, 95% [0.1042, 0.1474] | ≥ 0.062547 | **1.000** |
| **P1**, both move types | — | both | **1.000** |
| **P2** | share 0.5534, 95% [0.4858, 0.6073] | inside [0.3917, 0.6734] | **1.000** |

**Neither bar is a design defect.** All 2000 replicates clear both `P1` thresholds — the
95% interval of the departure sits entirely above each of them — and `P2`'s share never
leaves history's interval at fifty decades. The `P2` arm uses the M4 point estimate's own loadings and holds
the residual at the fitted stationary standard deviation — which is exactly how the generated
side is scored, where the residual sd *is* a model parameter and only the economic components
are measured on the batch.

**Three limits, and the first is the one that matters.**

1. **This cannot see the anchor's own estimation error.** The stretches come from the same
   813 months the threshold is cut from, so a replicate can be unlucky in its *sampling* of
   history but never in its *estimate* of history. §2.9 is where that risk lives and it is
   unchanged: `P1` still asks for half of a departure history can only just distinguish from
   zero. A power of 1.000 does not touch that, and reading it as though it did would be the
   error this paragraph exists to prevent.
2. **History is the most favourable engine there is**, so these are **upper bounds** on any
   real engine's power. They say the bar is reachable, not that it will be reached.
3. **`P2`'s power is sampling adequacy only.** The components are history's own. Whether a
   coupled engine produces components of that size is week 1's question.

---

## 4. M5 — both anchors under the classifier's two threshold dials

**The grid is the sealed obligation's, imported unchanged** (`spine_v2_anchors.STABILITY_ARMS`):
the baseline, each dial moved **50 basis points** each way on its own, and the four joint
corners. A positive inflation delta raises the hot line (fewer hot months); a positive growth
delta raises the contraction line (more contracting months). The perturbation size is the
platform's own `BACKDROP_MARGIN_PP` and is not re-argued here.

**The verdict rule is the campaign's, unchanged:** a statistic that moves by more than **one
of its own standard errors** across the arms is UNSTABLE and escalates. The yardstick for
each statistic is its own block-bootstrap standard deviation at the primary block length,
measured in §1.4 and §2.9.

**Scope note, and it is a deliberate widening.** §3.3 of the design document names M5 as *the
decomposition's* stability — M4's. That is measured below and it is uneventful. The phase
anchor is a function of the same labels and nobody had asked the question of it; it is
measured too, and **that is where the instability is**.

### 4.1 A structural fact, turned into a test

M4's regressors are the rule-implied policy rate and the inflation gap. The cycle input
inside the rule is `1 − 2·USREC`, the WP2.6 contract — **not** the classifier's growth axis —
and the era line appears nowhere in the equation. So **only the growth dial can reach M4**,
and only through the season block, which §1.6(c) already measured as the smallest of the
three economic components by a factor of fifteen.

That is a claim, so the script tests it: the four inflation-dial-only arms must return M4's
economic share **bit for bit**, and the run aborts if they do not. Measured difference:
**exactly 0.0**.

### 4.2 M4's share barely notices

| arm | economic share | move, in its own bootstrap sd |
|---|---|---|
| baseline | 0.558667 | — |
| growth line −50 bp | 0.559535 | +0.012 |
| growth line +50 bp | 0.555968 | **−0.038** (worst) |
| all four inflation-only arms | 0.558667 | 0.000 |

Range across all nine arms: **[0.555968, 0.559535]** — a width of 0.0036 against a bootstrap
standard deviation of **0.0716**. **`M4` is STABLE**, by a factor of twenty, and §1.6(c)'s
argument that M5 would be less load-bearing for M4 than it was for week 3's fit is now a
measurement rather than an argument.

### 4.3 P1's anchor is a different story

Departure from the within-window null (§2.10's construction), by arm:

| arm | growth-flip departure | (sd) | inflation-crossing departure | (sd) |
|---|---|---|---|---|
| **baseline** | **0.138168** | — | **0.125093** | — |
| inflation line −50 bp | 0.080660 | **−0.960** | 0.062891 | **−1.347** |
| inflation line +50 bp | 0.101866 | −0.606 | 0.128416 | +0.072 |
| growth line −50 bp | 0.165643 | +0.459 | 0.105843 | −0.417 |
| growth line +50 bp | 0.143091 | +0.082 | 0.157201 | +0.696 |
| inflation − / growth − | 0.114339 | −0.398 | 0.063334 | −1.338 |
| inflation − / growth + | 0.100108 | −0.636 | 0.092934 | −0.697 |
| inflation + / growth − | 0.144228 | +0.101 | 0.127260 | +0.047 |
| inflation + / growth + | 0.097725 | −0.675 | 0.147272 | +0.480 |

> ### ⚑ The inflation-crossing departure **ESCALATES**: 1.35 of its own standard error, on a 50 bp move of the inflation dial. The growth-flip departure does not, at 0.96 — and "does not" there means "by four hundredths of a standard error".

**What this does to the candidate thresholds, which is the part that matters for a seal:**

| candidate threshold | baseline | range across the nine arms | ratio |
|---|---|---|---|
| growth flips | 0.069084 | [0.040330, 0.082822] | **2.05×** |
| inflation crossings | 0.062547 | [0.031446, 0.078601] | **2.50×** |

**`P1`'s thresholds are pinned only to a factor of two to two and a half by a
conventional-sized move of a classifier dial.** That is the same class of finding week 3
recorded for `expansion_age` (pinned to a factor of 2.5) and it is worse here, because a
threshold is a number that goes into a seal rather than a coefficient that goes into a
report. It does not make `P1` unaskable — every arm still leaves history's departure far
above zero, and the direction of the escalation is *downward*, i.e. toward an easier bar, so
adopting the baseline is not the flattering choice — but **the owner should see this range
before a threshold is sealed to six decimals**, and it belongs in the seal text rather than
in a sensitivity appendix.

**And the escalation path is undefined.** The sealed rule says an escalated statistic is
refit with soft labels and both are reported. A clockwise fraction is a **count**, not a fit;
there is no agreed meaning for a soft-label weighted transition count, and inventing one here
— weighting each transition by the confidence of the two months that make it, say — would be
a new judging convention introduced after seeing which way it moved. It is left undone and
named as stop-question 7.

---

## 5. The generated side's own scrambled null — stop-question 5, closed

**What was open.** `P1`'s null is *the batch's own* phase scramble. §2.8 substituted
history's, on the argument that every per-move null sits within 0.001 of 0.500. That argument
had never been checked on a generated batch, and §2.10 has just shown that the *construction*
matters more than anyone had assumed.

**What was done.** Week 3's recorded batches were **re-simulated from the committed engine**
— all four engines on the unconditional arm plus the primary engine's premise-accepted arm —
and each one's inflation dial was circularly shifted against its growth axis **inside each
decade**, exhaustively, at the same 24-month guard §2.10 uses.

**The reproduction is proved, not assumed.** Each batch's transition counts are compared with
week 3's committed `o1_decomposition` and each censored batch's pooled fraction with the
sealed `O1` value; the run aborts on any mismatch. `feedback`/unconditional reproduces
**304 clockwise of 580** transitions and a sealed `O1` of **0.511765**, exactly.

### 5.1 Engine-null against history-null

| batch (judged construct — the sealed judge's censored decades) | own overall null | history, panel-wide |
|---|---|---|
| `feedback`, unconditional (week 3's primary) | **0.487890** | 0.488401 |
| `feedback`, premise-accepted | 0.483061 | 0.488401 |
| `ml_link`, unconditional | 0.489389 | 0.488401 |
| `ols_feedback`, unconditional | 0.485435 | 0.488401 |
| `week2`, unconditional | 0.486133 | 0.488401 |

**The five engines' overall nulls land in [0.4831, 0.4894] and straddle history's panel-wide
0.4884.** The primary engine's is 0.487890 — 0.0005 away. So the *overall* substitution, the
one that matters for reading `O1`, is sound at the half-thousandth.

**But history's own within-window overall null is 0.477281, not 0.4884** (§2.10), and the
engines sit **above** it by 0.006–0.012. Both facts are true and they are about different
constructions: history's decades are cut from one continuous run and carry more diagonal
moves per window than a generated decade does. The consequence for a seal is narrow and
should be stated as such: **there is no single "independence number" to quote for the overall
statistic** — it is 0.500 by the structural argument, 0.4884 by a panel-wide shift, 0.4773 by
a within-window shift on history, and 0.483–0.489 on the engines. Any sentence of the form
"O1 asks for X better than a coin flip" has to say which.

### 5.2 The substitution, per move type — the question actually asked

| | own null, judged construct | history's stand-in | error |
|---|---|---|---|
| worst cell of ten (`ml_link`, growth flips) | 0.512722 | 0.500084 | **+0.012638** |
| `feedback` unconditional, growth flips | 0.507815 | 0.500084 | +0.007731 |
| `feedback` unconditional, inflation crossings | 0.500616 | 0.499981 | +0.000635 |
| median absolute error across the ten judged-construct cells | | | 0.00160 |

**Verdict on the substitution: sound, but not to 0.001.** §2.8's disclosure said "every
per-move null sits within 0.001 of 0.500"; that is true of *history's* nulls and **not** of
the engines' — the worst is 0.0126 out, which is a fifth of a candidate threshold. So the
substitution does not change any verdict, and it is not accurate enough to be left as a
permanent convention. **The P1 judge must compute the batch's own null**, as §3.1 of the
design document says it must; this section is the evidence that doing so is cheap and that
the answer is close but not identical.

### 5.3 The retro anti-test, re-run against each engine's own null

`P1`'s third anti-test obligation is that every engine on the record must fail. Judged
against **its own** null instead of history's:

| engine / arm (judged construct) | growth-flip departure | inflation-crossing departure | passes? |
|---|---|---|---|
| `feedback`, unconditional | 0.008931 | 0.036226 | **no** |
| `ml_link`, unconditional | 0.010642 | 0.034002 | **no** |
| `ols_feedback`, unconditional | 0.008890 | 0.030661 | **no** |
| `week2`, unconditional | 0.022516 | 0.036151 | **no** |
| `feedback`, premise-accepted | 0.003562 | 0.008818 | **no** |

against thresholds of **0.069084** and **0.062547**. **The obligation holds, and by much
wider margins than §2.8 reported** — the closest cell is now short by 0.026 rather than by
0.010. Two reasons, both worth understanding: the judged (censored) construct is what the
engines actually ship, and §2.8 compared the *internal uncensored* fractions against it; and
each engine's own null is slightly *above* 0.500, which shrinks its departure. Both
corrections push the same way, and neither was chosen after seeing which way it went — they
are the constructions §2.10 and §5 argued for on like-for-like grounds.

---

## 6. How many draws should a sealed floor be cut from? — stop-question 2, answered

### 6.1 The margins, and the rule

Stop-question 2 recorded that two honest bootstraps of the identical statistic differ by
0.0019 at 2000 draws while O1's margins are 0.0011–0.0063. This section takes every margin in
this run's **own** reconciliation table — each engine reading beside the floor its construct
implies, plus each sealed reading beside its sealed threshold — and finds the smallest.

| smallest margins the floor has to resolve | |
|---|---|
| `week2` unconditional vs the windowed-overlapping floor | **0.000761** |
| `ml_link` unconditional vs the windowed-overlapping floor | 0.001109 |
| `feedback` unconditional vs the windowed-disjoint floor | 0.001137 |
| `ols_feedback` premise-accepted vs the uncensored floor | 0.001225 |

The smallest is **0.000761**, smaller than the 0.0011 the first pass quoted — §2.6 discussed
the cells it was reconciling and did not sweep all thirty-two of them (eight engine-arms ×
three history constructs, plus each arm's own sealed reading against its sealed threshold). The
sweep is now done in code, from this run's own table, so the number cannot drift from the
thing it is derived from.

> **PRE-DECLARED RULE.** The **tape noise** — the standard deviation of the floor across
> independent bootstrap tapes — must be at most **one fifth** of the smallest margin the
> floor has to resolve. At one fifth, a two-standard-deviation tape excursion is still under
> half the margin, so no recorded verdict can flip on the draw; at one half a routine
> excursion could flip one, and at one tenth the cost quadruples for a resolution nothing
> uses.

**Required tape noise: 0.000152.**

### 6.2 Why the count is measured rather than extrapolated

The textbook answer is one measurement and one multiplication: a bootstrap percentile's Monte
Carlo standard deviation falls as one over the square root of the draw count. That was tried
first and it is not safe here, for a reason worth recording.

**The two floors behave differently and only one of them obeys a power law.**

- The **unweighted** floor — the sealed `O1` statistic — is a count over about seventy
  transitions, so it lives on a **lattice** of ratios of small integers. Twelve independent
  tapes return twelve distinct floors at 2000 draws, nine at 8000, and **six at 32000**, with
  the modal value already taking 42% of them. Past that its noise falls faster than any power
  law, because one lattice point takes the whole tail.
- The **windowed** floor is a weighted fraction over re-used months, is effectively
  continuous (twelve distinct values at every rung), and does follow a power law — with a
  fitted exponent of **−0.559**, not the textbook −0.500.

Neither behaviour is safe to extrapolate two orders of magnitude. So the draw count is
**climbed as a ladder** — quadruple until the measured noise meets the rule, then one
refinement rung at the count the fitted law implies, floored at 1.25× the last rung and
rounded up to a quotable number — and the answer is the smallest rung that **measurably**
meets it.

### 6.3 The ladder

| draws | uncensored floor: sd | distinct / 12 | windowed floor: sd | distinct / 12 |
|---|---|---|---|---|
| 2,000 | 0.002743 | 12 | **0.002931** | 12 |
| 8,000 | 0.001495 | 9 | 0.001990 | 12 |
| 32,000 | 0.000641 | 6 | 0.000721 | 12 |
| 128,000 | — | — | 0.000305 | 12 |
| 512,000 | — | — | 0.000155 | 12 |
| 640,000 (refinement) | — | — | **0.000148** | 12 |

**The windowed floor is the binding one** — it is noisier at every shared rung — and that is
not an accident: it is the construct §2.5 recommends, and its weighting over re-used months
is exactly what makes it continuous rather than lattice-valued.

### 6.4 The answer

The ladder quadrupled to 512,000 draws and **missed by 2%** — tape noise 0.000155 against a
target of 0.000152 — so one refinement rung was taken at the count the fitted law implied,
floored at 1.25× and rounded up.

| rung | tape noise (12 tapes) | vs required 0.000152 |
|---|---|---|
| 512,000 | 0.000155 | **misses**, by 2% |
| **640,000** | **0.000148** | **meets**, by 3% |

> ### ⚑ **640,000 draws.** Measured, not extrapolated, on the binding (windowed-overlapping) floor at the primary 24-month block. That is **320× the 2000 draws every floor in this document and in the sealed v2 anchors was cut from.**

**Runtime, which is the whole practical point:** the complete module — M3, M3's power
calculation, M4, M5, both phase constructs, the generated-side nulls and this entire ladder —
runs in **about 17 minutes** on this machine. Roughly 14 of those minutes are the ladder,
because the ladder measures **twelve** tapes at every rung in order to estimate a standard
deviation. **Cutting one floor at 640,000 draws costs about 30 seconds.** That is the
finding: the campaign has been cutting floors at 2000 draws not because more was expensive
but because nobody had asked.

**Three honest qualifications, in decreasing order of importance.**

1. **The answer is a band, not a point, and the band is roughly 500,000–650,000.** A standard
   deviation from twelve tapes is itself known only to about [0.66×, 1.52×], so 512,000's
   "miss" and 640,000's "meet" are separated by less than the resolution of the check that
   separates them. Quote **640,000** because it is the smallest count *measured* to meet the
   rule; treat anything below 500,000 as insufficient; do not read the last digit.
2. **The interval's upper edge does not meet the rule at 640,000** — it is 0.000225 against
   0.000152. Requiring the *upper edge* to meet it would push the count to about 1.4 million and
   would be requiring the check to be more certain than twelve tapes can make it. The rule as
   declared is on the point estimate and is applied as declared.
3. **The two extrapolations, published as the thing that does not settle it**: the fitted
   power law says 554,000 and the textbook square-root law says 606,000 for the binding
   construct. Both are in the measured band, which is reassuring — and neither could have
   been trusted in advance, because the *other* floor's noise falls off a lattice and obeys
   no such law at all.

### 6.5 What it costs, and where the rule does not reach

A clockwise-fraction floor is cheap: the draws are index arithmetic and nothing is refitted.
**A floor cut from a fitted statistic is not.** M4's share refits an AR(1) profile on every
draw — about two hundred times the work per draw — so applying the same rule to M4's interval
would be hours rather than minutes. **The rule as stated is for `O1`-class floors**, and
extending it to a fitted interval should be priced before it is promised.

**And the honest reading of the whole section.** This is a *resolution* requirement, not a
claim that a floor cut from 2000 draws is wrong. It says what draw count makes a floor
reproducible to better than a fifth of the smallest distance it has to measure, so that a
re-derivation on another tape cannot move a verdict. Every floor quoted in §2 of this
document was cut from 2000 draws and each one carries about 0.003 of tape noise — which is
why §2.6 said a floor quoted to four decimals is quoting its tape as much as its data, and
why this section exists.

---

## 7. Determinism and reproduction

- **One command:** `uv run python scripts/stage2_anchors.py`. No network; every input is
  read from the pinned campaign vintage through the same accessors `spine_v2_fit` uses.
- **Five literal seeds**, each used nowhere else: `M4_BOOTSTRAP_SEED = 20260821`,
  `PHASE_BOOTSTRAP_SEED = 20260822`, `M3_BOOTSTRAP_SEED = 20260823`,
  `M3_POWER_SEED = 20260824`, and `NOISE_TAPE_SEED_BASE = 20260825`. They continue the run
  20260816–20260820 that `spine_v2_anchors` occupies. The provenance check in §2.6 re-uses
  the sealed `e_ordering` seed, read from the anchors file rather than restated, and §5
  re-uses week 3's `VERIFY_SEED` deliberately — a different seed would be a different batch
  and would not be the recorded engine's null.
- **The noise study's tape stride is 10007, not the platform's 7919.** 7919 is spoken for on
  the ensemble axis, and re-using a stride on a new axis is how twenty spines once collapsed
  to two. The tapes are checked for distinctness at the cheapest rung rather than assumed to
  be distinct.
- **Three of the estimators use no seed at all** — the panel-wide scramble null, the
  within-window scramble null and M3's selection-aware null all enumerate every admissible
  shift, so they have no Monte Carlo error whatsoever.
- **Two byte-identical re-runs verified**, SHA-256
  `58a1f7b23d5b675bc3fad6673c220985daee00c48451f72c22f20a622c8759a8` on both; the committed
  artifact carries that hash. (A third pair was run before a one-line correction to a
  justification string; it was byte-identical to itself and differs from the committed pair in
  exactly that string and in **no number**, verified by diff.) Each run is about 17 minutes.
  All floats are rounded to 12 places before the
  JSON is written, on `spine_v2_fit._round`'s reasoning: BLAS is free to reassociate, and
  rounding the output at a resolution far below any reported precision is what makes
  `json.dumps` reproducible without pretending the twelfth decimal is meaningful.
- **Nothing sealed was touched.** `spine-v2-prereg.json` and `spine-v2-anchors.json` are
  opened read-only and their SHA-256s are recorded in the artifact. `src/` and `schemas/`
  are untouched. Ruff and pyright are clean full-tree.
- **Nine internal checks are assertions, not decorations**, and each fails the run rather
  than warning: the rebuilt Taylor anchor reproduces `build_panel`'s `u_hat` to 0.0; the
  block-aware AR(1) profile reduces to week 3's single-block profile to 0.0; the
  overlapping-window weights reproduce a literal 694-window count exactly; the uncensored
  construct reproduces the sealed 43-of-72 ordering anchor; the window-by-window pooling and
  the weighted shortcut agree to 1e-12 on every move type; the chi-square(1) tail hits its
  two textbook percentiles; M5's baseline arm reproduces the phase section's own fractions
  exactly (the two reach the panel by different routes); the four inflation-only arms move
  M4's share by exactly 0.0; and every re-simulated batch reproduces week 3's committed
  transition counts **and** its sealed `O1` value.

---

## 8. Stop-questions for the owner

**Four of the first pass's six are now closed by measurement.** They are kept below with
their answers so the record reads in order, and three new ones are added at the end.

| # | first-pass question | state after the second pass |
|---|---|---|
| 1 | does the seal re-cut `O1` on the symmetric construct? | **STILL OPEN** — and §2.10 widens it: there are now *three* candidate history constructs, not two |
| 2 | how many draws should a sealed floor be cut from? | **ANSWERED**, §6 |
| 3 | is `P1` worth sealing given how thin its anchor is? | **ANSWERED**, §3 — the channel is established at 95% and the bar is reachable; the anchor is still thin |
| 4 | M3 and M5 are owed | **DONE**, §3 and §4 |
| 5 | the generated side's own null is unmeasured | **DONE**, §5 |
| 6 | `P2`'s verdict is not robust to the choice of summary | **STILL OPEN** — untouched by the second pass |

### Still open

1. **Does the seal adopt the windowed-overlapping construct for O1 as well as for P1?**
   §2.5 recommends it, and §2.6 shows the consequence: O1's floor moves from 0.518067 to
   about 0.5157 and week 3's engine still fails, by 62% of the recorded margin. Re-cutting
   O1's floor means **amending a sealed threshold**, which is a different act from anchoring
   a new bar and should be ruled explicitly rather than inherited. The alternative — carry
   O1 byte-frozen on its mixed construct, and use the symmetric construct only for P1 — is
   defensible and has the merit that "all ten sealed v2 bars carry over byte-frozen" stays
   literally true. **This document does not choose.**

2. ~~**How many bootstrap draws should a sealed floor be cut from?**~~ **ANSWERED in §6**,
   with a pre-declared rule (tape noise ≤ one fifth of the smallest margin the floor must
   resolve) and a measured draw count. What remains for the owner is not the number but the
   **decision to adopt the rule**: it is a resolution requirement nobody has previously
   imposed, and it makes every floor in §2 of this document — all cut from 2000 draws —
   under-resolved by roughly a factor of twenty in variance.

3. ~~**Is P1 worth sealing given §2.9?**~~ **ANSWERED in §3, and the answer is yes on both
   halves of the question.** History establishes the channel (`lam_x` = +0.00633, no shift in
   694 matches it) and a correct engine clears the bar in 2000 of 2000 replicates at the
   sealed batch size. **§2.9's caveat is untouched by either**: the power calculation resamples
   the same 813 months the threshold is cut from, so it can see sampling noise and not
   estimation error. The bar is askable and reachable; its anchor is still thin.

4. ~~**M3 and M5 are still owed.**~~ **DONE**, §3 and §4. M5's result is not the quiet one it
   was expected to be — see new stop-question 7.

5. ~~**The generated side's own phase-scrambled null is unmeasured.**~~ **DONE**, §5. The
   substitution was sound to about 0.0016 in the median and 0.0126 at worst, no verdict moves,
   and the correct construction is cheap — so the P1 judge should compute the batch's own null
   rather than inherit history's.

6. **P2 is kept on the pre-declared statistic and would be dropped on one alternative
   summary of the same fit.** §1.5's second table: the strict share says keep with a margin
   of 0.37, the covariance-aware share agrees, and the realised R² — whose bootstrap
   interval is `[−0.22, 0.56]` — says drop. The strict share is primary because it is the
   function the engine is scored by, and the R²'s interval is wide because an R² is
   ill-behaved under a GLS fit at `rho` = 0.98, not because the curve is less economic than
   it looks. **That reasoning is the author's and it should be checked rather than
   accepted**, because it is the one place in this document where a defensible alternative
   choice flips a verdict.

### Raised by the second pass

7. **`P1`'s candidate thresholds are pinned only to a factor of two, and the escalation path
   for a counting statistic does not exist.** §4.3: a 50 bp move of the inflation dial moves
   the inflation-crossing departure by **1.35 of its own standard error** — an escalation
   under the sealed rule — and the candidate thresholds range over [0.0403, 0.0828] and
   [0.0314, 0.0786] across the nine arms. The sealed escalation path says "refit with soft
   labels and report both", which is written for *fitted coefficients*; a clockwise fraction
   is a count and there is no agreed soft-label version of one. **Inventing a weighting after
   seeing which way it moves would be a goalpost move**, so nothing was invented. The owner
   must rule on (a) whether a threshold can be sealed to six decimals when a conventional
   dial move doubles it, and (b) what escalation means for a count.

8. **Which null is `P1`'s null — and the same question for `O1`.** §2.10 shows the panel-wide
   scramble and the within-window scramble are different operations giving different numbers
   (thresholds +9%; the overall null 0.4884 versus 0.4773). This document recommends the
   within-window construction on a like-for-like argument and §5 confirms a batch can perform
   it. That recommendation should be **ruled, not inherited**, because it changes a threshold
   that goes into a seal. It also interacts with stop-question 1: re-cutting `O1` now has
   three candidate history constructs rather than two.

9. **The ten-month lag is not pinned, and something downstream may want it to be.** §3.4:
   only 57% of bootstrap draws select within three months of ten, and the classifier-cycle
   arm selects **two**. The coefficient is solid at every lag in the hump and the gate does
   not depend on the lag — but stage 2's coupled system has to *choose* an `m`, and this
   measurement says the panel does not choose it for you. Whatever the fit picks should be
   reported with this profile beside it rather than as a determined quantity.

---

## 9. What is NOT sealed by this document

Everything in it. No threshold is binding, no bar exists, and no sealed value has changed.
P1 and P2 must still be sealed **before the coupled fit is run**, through the seal's
machine-checked amendment log with their judge code hashed in — because a bar written after
a coupling is fitted is a description, not a test. The two open constructs the design
document names as prerequisites (does `AM-SPV2-2026-08-17-001` stand; hard labels or soft)
are untouched here and remain the owner's to rule first.

The standing caveat is unchanged and applies to every number above: nothing built on this
generator line is a convincing model of history, the holdout is spent, and no appeal to
held-out data is available to any result stage 2 produces.
