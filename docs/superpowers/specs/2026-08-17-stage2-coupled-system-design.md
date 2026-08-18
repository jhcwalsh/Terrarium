# Stage 2 — the coupled economic system: a costed proposal

**Date:** 2026-08-17 · **Branch:** `spine2-02-fit`
**Status: PROPOSED, NOT FUNDED.** Decision **D-SP-9** is written down in §6 and is
**not taken**. Nothing in this document authorises work; it exists so the owner can
price the thing before deciding whether it is worth buying.

**What it is built from — measurements, not aspiration:**
`docs/superpowers/specs/2026-08-17-spine-v2-fit-report.md` (week 2, FRONTIER),
`docs/superpowers/specs/2026-08-17-spine-v2-feedback-report.md` (week 3, FRONTIER),
the sealed exam `docs/superpowers/specs/2026-08-17-spine-v2-exam.md` and its seal
`docs/superpowers/specs/spine-v2-prereg.json` (amended once, `AM-SPV2-2026-08-17-001`),
the original architecture `docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md`,
the fitted L1 system `src/ah/gen/climate/model.py`, and `docs/state-of-the-thesis.md` (Path B).

**House rules this document is written under** (D-SP-6's standing communication rule):
plain language; every proposed pass/fail bar states the real quantity that anchors it
and why its tolerance is the size it is; no term used without being defined once.

---

## The one-paragraph answer

Two campaigns have now ended at a **frontier** rather than a verdict, and both stopped
at the same kind of wall: the generated economy's parts do not talk to each other.
Week 2 found the yield curve had no way of knowing a downturn had begun; week 3 built
that one channel, and found that (a) it closed only a quarter of the gap, and (b) the
remaining failure — O1, the seasons turning the right way round — is a different missing
channel entirely, between **growth and inflation**. Both missing channels have the same
root: the engine is a set of **independent dials** with a hazard bolted on, not a system.
Stage 2 is one change — make the four quantities the product actually shows a player
(growth, inflation, policy, the curve) into **one coupled monthly system, fitted jointly
on the same panel** — and it is the smallest change that could move the two bars that
are stuck. It is estimated at **2–3 weeks of modelling plus the 2 weeks of full exam the
v2 campaign never ran**, on CPU. It buys nothing for the private book (ER-14 stands
untouched), nothing for ranked play (parked, D-SP-7), and the product ships on the
stress compiler either way. The honest base rate is that a third campaign also ends at
a measured frontier — that is a reason to price it carefully, not a reason to pretend
otherwise.

---

## 1. WHY — the two mechanisms the campaign measured as missing

Neither of these is a hypothesis. Both were measured, by sealed judges or by
decompositions published beside them, and both have a recorded location.

### 1.1 Growth and inflation do not know about each other (the O1 diagnosis)

**Where it was recorded.** Week 3's report, §7 ("O1: measured, and it is not the curve's
fault"), decomposing the ordering bar by the kind of move being counted.

**What the ordering bar actually asks.** Every month sits in one of four boxes by two
yes/no questions — is the economy expanding, and is inflation hot. The clock's forward
direction is recovery → expansion → stagflation → recession → recovery. Look at that
sequence and notice its structure: **it alternates.** One step changes the growth answer,
the next changes the inflation answer. So a growth flip is "clockwise" **only if it
happens while inflation is hot** (or cool, on the way back up), and an inflation crossing
is clockwise **only if it happens on the matching growth axis**. O1 is therefore not a
test of the growth dial or of the inflation dial. **It is a test of the phase between
them** — whether the two dials move in a fixed relationship to one another, or wander
independently.

**The measurement:**

| clockwise fraction, by move type | history | week-3 engine | what independence would give |
|---|---|---|---|
| growth flips (expanding ↔ contracting) | **0.6176** (47.2% of 72 transitions) | **0.5362** (40.5%) | ≈ 0.500 |
| inflation crossings (hot ↔ cool) | **0.6111** (50.0%) | **0.5477** (56.0%) | ≈ 0.500 |
| overall (the sealed O1 statistic) | 0.5972 | 0.5241 | ≈ 0.500 |

**Why 0.500 is the independence number, in plain words.** A growth axis that flips must
flip *down* then *up* then *down* — the directions strictly alternate. A downward flip is
clockwise when inflation is hot; an upward flip is clockwise when inflation is cool. If
the inflation dial has no relationship to the growth dial, then whatever share of months
are hot, it applies equally to the downward flips (helping) and the upward flips
(hurting), and the two cancel: the clockwise fraction lands on a coin flip. The same
argument, with the axes swapped, gives 0.500 for inflation crossings. *(In a finite
sample the two flip directions are not exactly balanced, so the exact null is a shade off
0.500 and must be computed rather than assumed — §3.1 makes that part of the bar.)*

**So the finding, stated as a size:** history sits about **0.11 above a coin flip on both
move types**; the engine sits about **0.04 above it**. It has roughly a third of the
phase relation history has, and the shortfall is spread evenly across both move types
(about 0.06 each) — which is the signature of a missing *link*, not of one broken dial.

**Why the engine has no phase relation — the mechanism, from the code.** In the shipped
engine the growth axis is the fitted hazard chain (weeks 2–3) and the inflation axis is
read straight off L1's trend-inflation state. In `src/ah/gen/climate/model.py`,
`transition_matrix` writes exactly one off-diagonal entry — `r_star ← g` — and the
inflation row `pi_star ← pi_star` is a plain mean-reverting process with no other input.
**There is no equation anywhere in the system in which inflation responds to growth.**
The two dials are independent because they were built independent.

**What history says the missing link is.** Downturns tend to begin while inflation is
still hot, and disinflation tends to arrive *during* them — inflation follows growth,
with a lag of several quarters. That is the single most standard fact in cyclical
macroeconomics and the engine does not contain it in any form.

### 1.2 The curve is not made of economics (the 93.9% finding)

**Where it was recorded.** Week 3's report, §6 ("Why the fitted feedback closes only a
quarter of the gap"), variance-decomposition table; week 2's report, §2, recorded the
same statistic at 59.6% and called it a limitation.

**The measurement.** The generated 10-year-minus-2-year slope is built as
`c0 + c_u·û + season term + AR(1) residual`. Splitting its variance:

| engine | policy-state contribution | season-term contribution | **residual (drawn noise) share** |
|---|---|---|---|
| week 2 (OLS link, no feedback) | 0.5358 pp sd | none | **59.6%** |
| **week 3 primary (exact ML, with feedback)** | 0.1486 pp sd | 0.1132 pp sd | **93.9%** |

**And the uncomfortable part, which the week-3 report states in its own words:** T1 —
the bar that asks whether tight policy brings downturns on — **passes on the arm where
the curve is least economically determined.** The estimator that raised the noise share
from 59.6% to 93.9% is worth about twice as much T1 movement as the economic feedback is.

**Two facts that make this worse than a "share" number suggests.**

1. **The one economic-looking term is not economic either.** `û` is L1's *policy
   deviation* — the part of the policy rate the Taylor rule did **not** explain — and in
   L1 it is a stand-alone mean-reverting process with no inputs at all
   (`transition_matrix` sets only its own diagonal). So the generated curve responds to
   the *residual* of the policy rule rather than to the rule.
2. **Inflation reaches the generated curve through no channel whatsoever.** The season
   term is a function of the growth axis only (a contracting flag and the age of the
   current growth spell). `û` has no inflation input. So a generated decade running at
   1% inflation and one running at 8% have **the same law for the yield curve**. That is
   the same class of defect as ER-14 (inflation does not reach private markets at all),
   in a different part of the system.

**What that costs the product, in the owner's terms.** The yield curve is the thing the
exam uses as the definition of "tight policy", and it is one of the numbers a player
looks at. If it is 94% drawn noise with no inflation input, then a player reading the
curve is reading a random number generator with a plausible autocorrelation, and the
lesson "tight policy precedes trouble" is being taught by a coincidence.

### 1.3 What the two have in common

Both are the same shape: **a quantity the product displays is produced by its own
private process instead of by the economy around it.** That is what "coupled system"
means here, and it is why the two are proposed as one piece of work rather than two.

---

## 2. WHAT — one coupled monthly system

### 2.1 The model class, named

**A monthly linear-Gaussian state-space system with a non-diagonal transition matrix,
carrying a two-state growth chain on top of it** — in plainer words: a small structural
macro model in which growth, inflation, policy and the curve each read the others, run
one month at a time, and fitted as one object on one panel.

Two things follow from naming it that way, and both are the reason this is a *2–3 week*
proposal rather than a campaign:

- **It is the machinery already in the repo.** `src/ah/gen/climate/model.py` is exactly
  this class already: states evolve linearly with Gaussian shocks, the latent path is
  integrated out exactly by a Kalman filter, and NUTS (numpyro/JAX) samples the ~35
  structural parameters. Stage 2 **turns on couplings that are currently zero** and adds
  four or five parameters. It does not introduce a new estimator, a new dependency, or a
  neural anything. **No L3.**
- **The growth chain is weeks 2–3's fitted hazard, unchanged in form.** The season
  transition hazard, its nine-month curve lead, its duration term and its season → curve
  feedback are all carried; stage 2 adds the arrows they are missing.

### 2.2 The system, in one equation block

Notation, defined once: `c_t` is the **cycle input**, +1 when the economy is expanding
and −1 when contracting — an array L1 *already consumes* (its docstring calls it "the
WP2.6 contract", fitted on history as `1 − 2×USREC`). `x_t` is the **inflation gap**, how
far actual inflation sits above or below its slow trend `π*`. `u_t` is the **policy
deviation**, how far the policy rate sits from what the rule says. `dt` is one month.

```
growth chain   season_{t+1} ~ Bernoulli( h(season_t, dwell_t, [slope_{t-9}, credit_gap_t, x_t, drawdown_t]) )
cycle input    c_t        = +1 expanding, -1 contracting            <- now produced INSIDE the system
inflation gap  x_{t+1}    = (1 - k_x dt) x_t + lam_x * (c_{t-m} - cbar) dt + sig_x e_t     [NEW]
inflation      pi_t       = pi*_t + x_t
policy dev     u_{t+1}    = (1 - k_u dt) u_t + lam_u * x_t dt + lam_c * c_t dt + sig_u e_t [NEW loadings]
policy rate    i_t        = r*_t + pi*_t + phi_pi (pi_t - pi*_t) + phi_c c_t + u_t   [L1's rule, unchanged]
curve slope    slope_t    = c0 + c_i*(i_t - ibar) + c_x*x_t + season_term(g_t, age_t) + e_t   [reads the RULE]
e_t            = rho e_{t-1} + eta_t
```

**Read as five plain sentences:**

1. **Inflation follows growth with a lag** (`lam_x`, lag `m`): after the economy has been
   expanding for a while, inflation drifts up; after it has been contracting, inflation
   drifts down. This is the arrow §1.1 measured as missing, and it is the one that can
   move O1.
2. **Policy stops being noise** (`lam_u`, `lam_c`): the deviation from the rule leans with
   the inflation gap and the cycle instead of wandering on its own — the plain fact that
   central banks tighten *harder* than the rule says when inflation runs hot, and cut
   *harder* than it says in a downturn.
3. **The curve reads the policy rate the model implies, not the rule's leftovers**
   (`c_i`, `c_x` replacing today's `c_u`). This is the arrow §1.2 measured as missing.
4. **The growth chain reads the curve, as it already does**, at the nine-month lead
   weeks 2–3 selected by likelihood — so the loop closes with a genuine lag and there is
   no simultaneity to solve.
5. **The season → curve feedback of week 3 is kept**, unchanged in form and re-fitted
   inside the bigger likelihood.

**The loop, drawn:** growth axis → cycle input → inflation gap → policy rate → curve →
(nine months later) growth hazard → growth axis. Every arrow is either an equation L1
already has or one new fitted coefficient. Nothing is hand-set.

### 2.3 How it is fitted, and one honest limit stated up front

The likelihood is three blocks added together and maximised (or sampled) as one object:
the Kalman marginal likelihood for the state-space part (existing L1 machinery, NUTS),
the discrete-time hazard likelihood for the growth chain (week 2's, IRLS), and the exact
AR(1) likelihood for the curve equation (week 3's).

**The honest limit, carried forward from week 3's §2 because it applies again.** On the
historical panel almost everything is *observed* — the season path from the grader's
labels, the slope from the panel's own 10y−2y, actual inflation from CPI, the policy rate
from FRED. So most of the cross-block information is zero and the joint fit largely
**block-diagonalises**: it is a property of the data, not an achievement of the design.
**The coupling is a generation-time property.** What the joint fit buys is that both
halves of the loop come from one likelihood on one panel, and that every "no coupling"
restriction (`lam_x = 0`, `lam_u = lam_c = 0`, `c_x = 0`) is nested exactly, so each is a
likelihood-ratio test rather than an argument. The one genuinely new cross-block piece is
the lag `m`, chosen by likelihood over a stated grid at constant parameter count — the
same discipline that chose the curve's nine-month lead, with the whole profile published.

### 2.4 Where it slots into the architecture — and what does NOT change

The compiler design's three layers are unchanged in structure:

| layer | today | under stage 2 |
|---|---|---|
| **S — the spine** | L1 states + a hazard chain, independent dials | **replaced** by the coupled system above |
| **H — the correction hazard** | per-quadrant hazard, fires crisis segments | **unchanged** |
| **F — the flesh** | verbatim 6-month chunks of real history, selected on the spine's state | **unchanged** |

**R1 — selection only — STANDS.** State chooses *which* real months are drawn; it never
edits, scales or synthesises a month. Every generated month remains verbatim history and
every world's severity ceiling remains history's worst months.

**Severity discipline unchanged.** Severity stays declared at the premise level; the
state-severity table is untouched; rule 1 (severity is never tuned to portfolio outcomes)
is reaffirmed, and it is why both new bars in §3 are measured on the macro path and on
asset returns, never on a book.

**No schema change, no new `generator_id`, no new dependency, no L3.** The coupled fit
produces a new posterior checkpoint and a new fitted-parameter artifact; the routing
through `extensions.x_spine` is unchanged.

### 2.5 The renumbering, stated honestly

**The label "stage 2" has been used for two different things and they must be separated
before a decision is taken on either.**

- D-SP-6 excluded "model-implied conditional means (stage 2) and any L3 generator".
- Week 2's report §8 then used "stage 2 of D-SP-6" to name the *missing curve response to
  the cycle* — and week 3 went on to build a version of exactly that, under D-SP-8,
  without anyone treating it as having crossed the funded boundary.

That is a genuine conflation and this document resolves it by splitting the label:

| | scope | R1 | status |
|---|---|---|---|
| **Stage 2** (this document) | model-implied conditional means **for the MACRO system only** — growth, inflation, policy, curve. The spine's own states become functions of each other. | **selection-only stands**; assets are still verbatim real months | **PROPOSED — D-SP-9, not taken** |
| **Stage 3** (named here, *not* proposed) | model-implied conditional means **for ASSET returns** — the engine would state what equities/bonds/commodities are expected to do given the state, instead of drawing real months | **would require amending R1** — a different and much larger decision | **not funded, not proposed, no cost estimated** |

**Stage 2 couples the macro system and nothing else.** A month's asset returns still come
from a real month of history, chosen (never edited) to match the spine. Anyone reading
this proposal as "the engine starts making up returns" is reading it wrong, and anyone
who wants that should be told it is stage 3 and has not been costed.

---

## 3. THE EXAM DELTA

**All ten sealed v2 bars carry over byte-frozen** — same thresholds, same judging code,
imported and never re-implemented — so that any change of verdict is attributable to the
engine and to nothing else:

| tier | bars | v2 status |
|---|---|---|
| causal | **T1**, **O1** | measured: T1 PASS (on the amended arm), O1 FAIL everywhere |
| persistence | **D1–D4** | measured: PASS, in all 32 frontier rows across two campaigns |
| allocation | **A1**, **A2** | **never measured** — they need the flesh, which week 4 never ran |
| no-regression | **R1**, **R2** | **never measured** in v2 — round two's verdicts were PASS / FAIL |

Two consequences to carry: the persistence tier has never been the binding constraint and
probably will not become one; and **four of the ten bars have never been run at all**, so
"five of six passed" is a statement about six bars, not about the exam.

**Two things must be settled before stage 2 starts, not after** (they are week 3's
stop-questions and they change what the bars mean):
1. **Does `AM-SPV2-2026-08-17-001` stand?** Under it, T1 and O1 are judged unconditionally
   and T1 passes; without it, on the premise-accepted arm, T1 reads 1.2231 and fails.
2. **Hard labels or soft?** Week 3's stability grid escalated on two coefficients. The
   soft-label refit reads *better*, which is exactly why adopting it after seeing bars
   would be a goalpost move. Decide now or not at all.

### The two new bars the coupling itself must pass

Both are **proposals**. Neither can be sealed as written: each names measurements that do
not yet exist, and §3.3 says what must be measured first. Their codes (**P1**, **P2**) are
placeholders to be fixed at sealing. Both must be **sealed before the coupled fit is run**
— through the seal's machine-checked amendment log with their judge code hashed in, never
by editing the exam document — because a bar written after a coupling is fitted is a
description, not a test.

### 3.1 P1 — the phase-coupling bar ("do the two dials keep time with each other?")

**The plain question.** In history, downturns tend to begin while inflation is still hot,
and inflation cools during them. Does the generated world do the same, or do its growth
and inflation dials wander independently?

**The statistic.** The clockwise fraction, computed **separately for growth flips and for
inflation crossings**, exactly as week 3's §7 computed it — and each one reported as its
**departure from that batch's own independence null**.

**How the null is computed (this is part of the bar, not a footnote).** The judge takes
the batch's own months, **scrambles the phase** of the inflation dial relative to the
growth axis — shifting the inflation series by a random whole number of months, many
times, which preserves each dial's own dynamics and destroys only their alignment — and
recomputes the two fractions. That is the exact value an engine with independent dials
would produce **on that batch**, so the bar cannot be passed or failed by a base-rate
accident, and it is the same construction on both sides.

**(a) The proposed bar.** For **both** move types, on the unconditional batch:

> departure from the batch's own phase-scrambled null **≥ half of history's own measured
> departure** — a candidate **0.056** (inflation crossings) and **0.059** (growth flips),
> to be replaced at sealing by half of the panel's measured departure under the same
> scramble.

**(b) The anchor.** History's clockwise fractions by move type — **0.6176** on growth
flips and **0.6111** on inflation crossings (week-3 report §7, on the sealed `grader_v2`
labels, 72 transitions on the campaign vintage) — against a null of ≈ 0.500. So history's
departure is ≈ **0.117** and ≈ **0.111**.

**(c) Why the tolerance is half, and not history's own value.** Each move type rests on
about 35 transitions. The sampling error on a fraction measured over 35 transitions is
about **0.083** — *larger than the entire departure being measured*. Demanding history's
point value would therefore fail a correct engine roughly half the time, which is the
exact defect O1's own §2(c) was rewritten to avoid. Half of history's departure is the
largest tolerance with three properties, all checkable before results:
- an engine with independent dials **fails by construction** (its departure is zero);
- **both engines already on the record fail it** — week 3 departs by ≈ 0.036 (growth) and
  ≈ 0.048 (inflation), week 2 by less;
- an engine that reproduces history's phase relation passes with room (0.11 against 0.056).

A bar that a known-uncoupled engine passes is worthless; a bar that a correct engine fails
half the time is worse. This is the widest tolerance that keeps both properties, and that
is the whole justification — it is not a number chosen because it looked reachable.

**(d) What a FAIL means in product terms.** The seasons keep arriving in an order the
player cannot learn from, because knowing the economy has turned tells them nothing about
what inflation will do next — the "slot machine with economic vocabulary" failure O1 was
written against, localised to its cause.

**Anti-test obligations** (§6.1 of the exam applies to every new judge):
1. **Sweep the coupling.** Refit nothing; scale `lam_x` through ×0, ×0.5, ×1, ×2, ×4,
   re-simulate from the same seeds, re-judge. The **measured departure must increase
   monotonically** across the swept range and the judge's pass rate must be non-decreasing.
   Where it saturates must be reported — both prior campaigns found bars that rise and
   then fall in their own mechanism's strength, so saturation is expected and must be
   visible rather than discovered.
2. **The null engine must fail.** At `lam_x = 0` the dials are independent by construction
   and P1 must return a FAIL. If it does not, the judge is broken.
3. **The retro-anti-test.** Judge week 2's and week 3's committed engines with the new
   judge. **Both must fail.** A new bar that passes an engine on the record as uncoupled
   is void, and this check costs minutes because both engines reproduce bit for bit.
4. **The scramble control.** Phase-scramble a *generated* batch that passes and confirm
   the statistic falls back to the null — proof the statistic measures alignment and not
   some other property of the batch.

### 3.2 P2 — the curve-endogeneity bar ("is the curve made of economics?")

**The plain question.** How much of the generated yield curve's movement comes from the
economy the engine is simulating, and how much is drawn noise?

**The statistic.** The share of the generated 10y−2y slope's variance attributable to the
model's own economic states — the policy rate implied by the rule, the inflation gap, and
the growth-season term — with **exogenous shocks excluded from the numerator**. The
exclusion is the whole point: today's engine would score 40.4% (week 2) or 6.1% (week 3)
on a naive accounting, but week 2's entire "explained" share is a stand-alone
mean-reverting process with no economic inputs, so under an honest accounting week 2
scores **0.0%** and week 3 scores **2.2%** (the season term alone).

**(a) The proposed bar.** Two-sided:

> the generated economic share must land **inside the historical interval** for the same
> decomposition measured the same way on the panel.

**(b) The anchor — and this is the bar that cannot be sealed today.** The nearest thing
on the record is week 3's curve regression on history: **R² = 0.2223** over 809 months
(0.1981 without the season block, so the season block is worth ≈ 2.4 points of it). That
number is **not bar-grade**, for four reasons that must be stated rather than smoothed:
1. it is an **in-sample** fit statistic, computed on the same months that chose the
   coefficients, so it is biased upward;
2. it has **no sampling interval** — nothing in the anchors file measures one;
3. its main regressor is the **observed policy deviation**, which on history contains real
   economic content (the zero-bound decade, credit conditions, everything the rule missed)
   but in simulation is a synthetic process — so the two sides are **not the same object**,
   which is exactly the mismatch the exam's own §6.2 review exists to catch;
4. the residual it leaves is a highly persistent process (`ρ` ≈ 0.97), and part of that is
   genuine term-premium movement that no macro state should be asked to explain. A curve
   that was 100% determined by three macro states would be *wrong in the other direction*
   — which is why the bar is two-sided.

**(c) Why two-sided, and why the width is history's own interval.** The upper edge is not
decoration: a share statistic can be moved to 100% by shrinking the noise, so a one-sided
"more economics is better" bar is gameable by an engine that simply removes the surprise
the product needs. The width is the sampling interval of a statistic measured on 68 years
of one country's history — the same construction and the same justification as T1's band
([1.78, 3.35]), which is wide for the same reason: it is what the data supports, and
narrowing it would be a modelling preference dressed as a measurement.

**(d) What a FAIL means in product terms.** Below the band, the curve a player is reading
is noise wearing an economic label, and the exam's own definition of "tight policy" is a
coin toss. Above it, the curve is a deterministic readout of the state and a player can
learn a rule that no real market would ever reward.

**Anti-test obligations:**
1. **Sweep the endogenous loadings** (`c_i`, `c_x`, `lam_u` together): the measured
   economic share must rise monotonically and the pass rate must be non-decreasing over
   the range where the share is inside the band.
2. **The noise-shrink control must FAIL from above.** Hold the loadings and scale the
   residual innovation down until the share exceeds the band's upper edge; the judge must
   return FAIL. This is the specific gaming route and it must be demonstrated closed.
3. **The retro-anti-test.** Week 2 (0.0%) and week 3 (2.2%) must both be judged and both
   must fail below the band. If either passes, the bar is not measuring what §1.2 found.
4. **Same-definition proof.** The decomposition function must be a single piece of code
   called on both sides — panel and generated batch — with the sides differing only in
   their input array. The exam's precedent for why (B6's recession-or-crisis mismatch) is
   on the record.

### 3.3 What must be measured before either bar can be sealed

Neither bar exists as a number today. In the order they would be taken, all through
`scripts/spine_v2_anchors.py`'s determinism rules (one literal seed per new section,
byte-identical re-runs):

| # | measurement | why it is needed |
|---|---|---|
| M1 | history's clockwise fraction **by move type**, with its block-bootstrap interval (the anchors file has only the pooled interval) | P1's anchor and its honesty about how thin 35 transitions are |
| M2 | history's own **phase-scrambled null** for both move types | P1's null is claimed to be ≈ 0.500; that must be measured, not assumed |
| M3 | the **power calculation** for P1 and P2 at 50 decades, on §8.1's machinery (a true engine emitting real 120-month stretches) | the exam's standing rule: a bar a correct engine cannot clear is a bar-design defect, and two were caught that way pre-seal |
| M4 | history's **curve decomposition**, defined on the *rule-implied* policy rate rather than its residual, with a block-bootstrap interval | P2's anchor. **Without M4 there is no P2** — this is the "cannot be measured cleanly yet" item, and it is a measurement, not a modelling choice |
| M5 | the decomposition's **stability under the classifier's two threshold dials** (the §11 grid) | the season block is a function of the labels; week 3 found one such coefficient pinned only to a factor of 2.5 |

M1–M3 are hours. M4 is the one with design content in it, and if it comes back with an
interval so wide that the engines on record sit inside it, **P2 should be dropped rather
than narrowed** — the precedent is A2's low-inflation ceiling, dropped pre-seal rather
than moved once its cost was visible.

---

## 4. COST, honestly

### Week by week, with a named cheap exit at the end of each

**Week 1 — joint-fit design and estimation.**
Write the coupling set down (which arrows, which lags, what each restriction nests);
extend the transition and observation matrices in the L1 model; refit by NUTS on the
campaign vintage; refit the hazard and curve blocks inside the same likelihood; publish
the lag profile and every likelihood-ratio test. Also: seal P1 and P2 (M1–M5 first).
> **Cheap exit A.** If `lam_x` — inflation's response to growth — is not significant on
> the panel, stop. The mechanism O1 needs is then not identifiable at this resolution on
> 68 years, which is a finding worth having for one week's spend, and it is reported as
> one. *(This is a real possibility, not a formality: week 2's fit produced several
> coefficients with t-ratios under 1 on 35 events.)*

**Week 2 — the verification loop.**
Simulate 50-decade batches; measure the six pre-flesh bars with the sealed judges,
imported and unmodified; measure P1 and P2; re-run the label-stability grid over every
new coefficient; map the frontier by scaling the new couplings — **never by tuning them**.
> **Cheap exit B.** If O1 stays below its floor at every point on the coupling frontier —
> as it did at every point on week 3's — stop and report FRONTIER. Two campaigns have
> ended here already and the discipline held both times; it must hold a third.

**Weeks 3–4 — the full exam, which the v2 campaign never ran.**
Integrate the coupled spine into `src/` (the first time this campaign touches `src/` at
all); run the flesh; measure **A1, A2, R1, R2** — the four bars nobody has ever run
against a v2 engine — plus the verdict-integrity review before anything reaches the owner.
> **Cheap exit C.** If R2 (the era-coherence bar the join tightening was supposed to flip)
> still fails, the flesh work is the finding and the allocation bars can wait. And if
> integration would require touching `schemas/` or any sealed file, stop and ask: that is
> a contract question, not an engineering one.

**Total: 2–3 weeks of modelling, plus 2 weeks of exam.** The honest reading of that range:
week 1 is the only week whose length is genuinely uncertain (the identification work), and
weeks 3–4 are a cost the campaign already owes regardless of stage 2 — they are the
exam's own remaining half.

### Compute

- **The L1-class refit is CPU work and the repo has measured it.** The campaign-3 runbook
  records a severe-leg L1 fit at **126 minutes, 0 divergences, R-hat 1.0030**, on this
  machine, and its L2 companion at **0.3 minutes**. CLAUDE.md's standing note is the same:
  numpyro+JAX ship native Windows CPU wheels and L1/L2 are verified on them; only L3
  training would need a different host, **and stage 2 does not train L3.** Budget a
  handful of two-hour fits, not a GPU campaign.
- **The hazard and curve blocks are seconds** — iteratively reweighted least squares and a
  199-point scan with a golden-section refinement, both deterministic.
- **Decade generation is cheap because the compiler is selection-only.** The sealed batch
  is 50 decades per premise; week 3's premise-accepted batch took 708 attempts for 50
  decades and ran inside a script.
- **The expensive item is the full exam's no-regression arm**, not the fitting: R1's
  over-commitment grid is 4 allocation points × 20 seeds through the institutional twin,
  and A1/A2 need the flesh compiled. This is hours, not days — **and it is explicitly not
  the sealed validation battery**, whose conditional tier is the historically expensive
  thing in this repo (measured: ~20 min over the bootstrap versus 7–9 hours over a neural
  generator, and ~23–25 min per criterion-size cell even batched). If anyone proposes
  running the battery over stage-2 worlds, that is a separate spend and it should be
  priced separately.
- **Per-branch overhead:** the CI gate is ~38 minutes and must be run to a bound log
  before any merge. Three or four branches is two to three hours of gate time.

### Risks, named

| risk | why it is real here | what it costs if it bites |
|---|---|---|
| **Identifiability on a thin panel** | 12 completed stagflation spells, 17 downturn onsets, 35 growth-axis flips, 19 completed spells per growth axis — and stage 2 adds 4–5 parameters to a system already fitted on those events. `lam_x` and the policy rule's existing `phi_c` both read the cycle; `c_i` and `c_x` both read policy | wide standard errors and a coefficient pinned only to a factor of two — the outcome week 3 already recorded for `expansion_age`. Mitigation: every coupling nests zero exactly, so each is a likelihood-ratio test; publish every profile |
| **The 93.9% trap repeating** | week 3 measured an estimator that fits better and generates worse. Nothing prevents that recurring | a pass that is not progress. Mitigation: pre-commit the primary estimator **in code, before any bar is read** (week 3's precedent), and P2 exists specifically to catch it |
| **Label instability compounding** | two of four fitted coefficients already escalate under a 50 bp move in the classifier's dials, and every escalated arm makes the effect *stronger* — the convenient direction | claims about coupling *size* become unquotable. Mitigation: settle hard-vs-soft labels **before** week 1, per §3 |
| **The construct question is still open** | T1 passes on the amended arm and fails on the other. Stage 2 would inherit that ambiguity into two more bars | two campaigns' verdicts resting on an unconfirmed reading. Mitigation: confirm or reject the amendment before any fitting |
| **Frontier discipline under a third campaign** | after two FRONTIERs there is real pressure to take a pass | the one thing this record has that is worth protecting. Mitigation: the cheap exits above are named per week, in advance, with what triggers each |

---

## 5. WHAT IT DOES NOT BUY

Stated flatly, so a pass cannot be over-read.

- **ER-14 is untouched.** Inflation does not reach the private book *at all* — private
  equity is bit-identical from 1% to 12% inflation, real estate moves the wrong way, and
  the apparent response of the private book is a second-order effect of the commodity
  sleeve beside it (`docs/current/private-markets-and-inflation.md`). Stage 2 couples the
  **macro spine**; it does not touch the translation layer's factor→sleeve linkage. If
  anything, a spine whose inflation actually moves makes the private book's blindness
  *more* visible. **This is the second leg of the owner's allocation thesis and it is a
  separate release event** — an `ah/port/mapping.py` artifact bump plus a `world_id` block
  move for touched presets, which is the owner's call and not a side effect of any report.
- **No ranked-play implications.** D-SP-7 parks ranked sessions; the play surface is
  practice-only. Stage 2 changes nothing about scoring, leaderboards, or eligibility, and
  it does not un-park anything.
- **The product ships on the stress compiler regardless.** D-SP-4's ruling stands: the
  product line proceeds on the plain stress compiler, and the live work is disclosure —
  moving what a world is made of out of the evidence files and into the player's face.
  Stage 2 is **not on the product's critical path**, and if it is funded it must not be
  allowed to become the reason disclosure slips.
- **It does not make anything decision-ready.** The standing caveat is unchanged: nothing
  built on this generator line is a convincing model of history, the holdout is spent, and
  no appeal to held-out data is available to any result stage 2 produces.
- **It does not buy a passing exam.** Two campaigns, two frontiers. Four of the ten bars
  have never been run. The honest prior is that stage 2 also ends with a measured wall —
  and the value on offer is *which* wall, measured, not a verdict.

---

## 6. Decision block

### ⚑ D-SP-9 — the coupled economic system (stage 2, macro only) — **PROPOSED, NOT TAKEN**

**What is being proposed:** §2 — one coupled monthly system over growth, inflation,
policy and the curve, fitted jointly on the campaign panel by the machinery already in
the repo; the flesh, R1 selection-only and the severity discipline unchanged; two new
bars (§3) sealed before the fit, and the ten existing bars carried byte-frozen.

**Cost:** 2–3 weeks of modelling plus the 2 weeks of full exam the v2 campaign never ran;
CPU throughout; cheap exits named per week.

**The three options, and what each means:**

| ruling | what happens next |
|---|---|
| **FUND** | M1–M5 are measured, P1/P2 are sealed by amendment with their judge code hashed, week 1 begins. The two open constructs (the amendment; hard vs soft labels) are ruled **first**, in writing, before any fitting. |
| **DECLINE** | The spine v2 campaign closes at its second frontier with both reports as its record. O1 is stated as **not reachable by this architecture**, the finding is filed, and the product line continues on the stress compiler with disclosure as the live work. Nothing is lost that is not already written down. |
| **DEFER** | The campaign is parked exactly as week 3 left it. Re-opening starts from §3.3's measurement list, which is the cheap half and can be done at any time to sharpen the decision without committing to the modelling. |

**This decision is not taken here.** The document exists to be priced and ruled on. Per
the standing convention, reserved decisions are **proposed-never-taken**: nothing in this
repository changes on the strength of this file existing.

**What the owner is actually being asked.** Week 3's stop-question 2 put it in one line
and it is the whole decision: *O1 needs a growth ↔ inflation phase channel, and building
one means the inflation axis stops being read straight off L1.* This document is the
costed version of that question. If the answer is no, O1 is not reachable and the
campaign should stop where it stands — **as it was designed to.**
