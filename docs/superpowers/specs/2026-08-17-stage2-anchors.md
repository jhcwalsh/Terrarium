# Stage 2 pre-seal measurements — M4, and the windowing-symmetric phase anchor

**Date:** 2026-08-17 · **Branch:** `stage2-01-anchors` · **Decision:** `D-SP-9` (stage 2
funded, owner ruling 2026-08-17)
**Status: MEASURED, NOT SEALED.** Nothing here is a bar. Every threshold below is a
*candidate*, and it becomes binding only when it is entered through the seal's
machine-checked amendment log with its judge code hashed in — which is a separate step,
after the owner has read the `P2` verdict.

**What produced it.** `scripts/stage2_anchors.py`, one command, no network, three
byte-identical re-runs verified. Its output artifact is
`docs/superpowers/specs/stage2-anchors.json`; every number quoted below is in that file
and this document adds only the derivation and the reasoning.

**House rules this document is written under** (D-SP-6's standing communication rule):
plain language; every proposed pass/fail bar states the real quantity that anchors it and
why its tolerance is the size it is; no term used without being defined once.

---

## The one-paragraph answer

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
| **M2** | history's own **phase-scrambled null** for both move types | listed | **done**, §2.4 (all three constructs, three guard bands) |
| — | the **windowing-symmetric** re-derivation the verdict's §8.1 requires | required by C1, before P1's threshold is cut | **done**, §2 |

### What was NOT measured, and must be before either bar is sealed

- **M3, the power calculation** at 50 decades for P1 and P2. Not attempted here: it needs
  §8.1's machinery (a true engine emitting real 120-month stretches), which is a separate
  build. **The exam's standing rule is that a bar a correct engine cannot clear is a
  bar-design defect, and two were caught that way pre-seal** — so M3 is not optional.
- **M5, the decomposition's stability under the classifier's two threshold dials.** Not
  attempted. §1.6 notes why it matters less for M4 than it did for week 3's fit (the season
  block is the smallest of M4's three economic terms by a factor of fifteen), but "matters
  less" is not "measured".
- **The generated side's own phase-scrambled null.** P1's null is defined as *the batch's
  own* scramble. This document measures history's, and uses it as a stand-in when it checks
  the recorded engines against the candidate thresholds (§2.8). That substitution is small
  on this panel — every per-move null sits within 0.001 of 0.500 — but it is a substitution
  and it is disclosed at the place it is made, in the artifact as well as here.

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
| **windowed, overlapping** | growth flips | 0.626416 | 0.500084 | 0.126332 | **0.063166** |
| **(recommended)** | inflation crossings | 0.615814 | 0.499981 | 0.115833 | **0.057917** |
| uncensored both sides | growth flips | 0.617647 | 0.500283 | 0.117364 | 0.058682 |
| | inflation crossings | 0.611111 | 0.500132 | 0.110979 | 0.055489 |
| windowed, disjoint | growth flips | 0.666667 | 0.502961 | 0.163706 | 0.081853 |
| | inflation crossings | 0.617647 | 0.501358 | 0.116289 | 0.058145 |

The uncensored row reproduces the design document's stated candidates (0.059 growth, 0.056
inflation) to three decimals, which is the expected result and a check that nothing drifted.
**The recommended construct raises both thresholds by about 8% and 4% respectively** — a
slightly harder bar, in the same direction as §2.3's finding.

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

---

## 3. Determinism and reproduction

- **One command:** `uv run python scripts/stage2_anchors.py`. No network; every input is
  read from the pinned campaign vintage through the same accessors `spine_v2_fit` uses.
- **Two literal seeds**, both used nowhere else: `M4_BOOTSTRAP_SEED = 20260821` and
  `PHASE_BOOTSTRAP_SEED = 20260822`. They continue the run 20260816–20260820 that
  `spine_v2_anchors` occupies. The provenance check in §2.6 additionally re-uses the sealed
  `e_ordering` seed, read from the anchors file rather than restated.
- **The scramble null uses no seed at all** — it enumerates every admissible shift.
- **Three byte-identical re-runs verified**, SHA-256
  `eeedc4207067b6a8fc7647a98dc3e14b2b7c3b558e92603998a2c4e6de4a1441` on all three. All
  floats are rounded to 12 places before the
  JSON is written, on `spine_v2_fit._round`'s reasoning: BLAS is free to reassociate, and
  rounding the output at a resolution far below any reported precision is what makes
  `json.dumps` reproducible without pretending the twelfth decimal is meaningful.
- **Nothing sealed was touched.** `spine-v2-prereg.json` and `spine-v2-anchors.json` are
  opened read-only and their SHA-256s are recorded in the artifact. `src/` and `schemas/`
  are untouched. Ruff and pyright are clean on the new module.
- **Four internal checks are assertions, not decorations**, and each fails the run rather
  than warning: the rebuilt Taylor anchor reproduces `build_panel`'s `u_hat` to 0.0; the
  block-aware AR(1) profile reduces to week 3's single-block profile to 0.0; the
  overlapping-window weights reproduce a literal 694-window count exactly; and the
  uncensored construct reproduces the sealed 43-of-72 ordering anchor.

---

## 4. Stop-questions for the owner

1. **Does the seal adopt the windowed-overlapping construct for O1 as well as for P1?**
   §2.5 recommends it, and §2.6 shows the consequence: O1's floor moves from 0.518067 to
   about 0.5157 and week 3's engine still fails, by 62% of the recorded margin. Re-cutting
   O1's floor means **amending a sealed threshold**, which is a different act from anchoring
   a new bar and should be ruled explicitly rather than inherited. The alternative — carry
   O1 byte-frozen on its mixed construct, and use the symmetric construct only for P1 — is
   defensible and has the merit that "all ten sealed v2 bars carry over byte-frozen" stays
   literally true. **This document does not choose.**

2. **How many bootstrap draws should a sealed floor be cut from?** §2.6 measures two honest
   bootstraps of the identical quantity differing by **0.0019** at 2000 draws, against O1
   margins of 0.0011 to 0.0063. Either the draw count rises until the tape noise is well
   below the margins the bar will be decided by, or the seal states which tape its floor was
   cut from and accepts that a re-derivation on another tape will disagree in the third
   decimal. The campaign has so far done neither explicitly.

3. **Is P1 worth sealing given §2.9?** History's growth-flip departure is not distinguishable
   from zero at 95% on the uncensored construct and only just is on the recommended one.
   P1 remains meaningful — an uncoupled engine fails by construction and all four recorded
   engines fail — but the owner should see that interval before a threshold is sealed on
   half of it, and **M3's power calculation should be treated as a gate rather than a
   formality.**

4. **M3 and M5 are still owed and neither was in this scope.** M3 (power at 50 decades, on a
   true-engine emitter) and M5 (the decomposition's stability under the classifier's two
   dials) are both on §3.3's list. §1.6(c) argues M5 is less load-bearing for M4 than it was
   for week 3's fit; that argument is not a substitute for running it.

5. **The generated side's own phase-scrambled null is unmeasured.** P1's null is defined as
   *the batch's own* scramble; §2.8 substitutes history's. Closing that needs the batches
   re-simulated and belongs to whoever writes the P1 judge.

6. **P2 is kept on the pre-declared statistic and would be dropped on one alternative
   summary of the same fit.** §1.5's second table: the strict share says keep with a margin
   of 0.37, the covariance-aware share agrees, and the realised R² — whose bootstrap
   interval is `[−0.22, 0.56]` — says drop. The strict share is primary because it is the
   function the engine is scored by, and the R²'s interval is wide because an R² is
   ill-behaved under a GLS fit at `rho` = 0.98, not because the curve is less economic than
   it looks. **That reasoning is the author's and it should be checked rather than
   accepted**, because it is the one place in this document where a defensible alternative
   choice flips a verdict.

---

## 5. What is NOT sealed by this document

Everything in it. No threshold is binding, no bar exists, and no sealed value has changed.
P1 and P2 must still be sealed **before the coupled fit is run**, through the seal's
machine-checked amendment log with their judge code hashed in — because a bar written after
a coupling is fitted is a description, not a test. The two open constructs the design
document names as prerequisites (does `AM-SPV2-2026-08-17-001` stand; hard labels or soft)
are untouched here and remain the owner's to rule first.

The standing caveat is unchanged and applies to every number above: nothing built on this
generator line is a convincing model of history, the holdout is spent, and no appeal to
held-out data is available to any result stage 2 produces.
