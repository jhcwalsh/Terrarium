# The spine v2, stage 1 exam — what the rebuilt engine has to prove

**Date:** 2026-08-17 · **Status:** DRAFT for owner review, **OPEN items closed 2026-08-17**
· **Branch:** `spine2-01-exam`
**Authority:** `governance/decision-register.md` D-SP-6 (2026-08-16, "go on the engine work,
include the allocation tests") plus the owner rulings of 2026-08-17 recorded in §9.
**Measurements this document cuts bars from:** `docs/superpowers/specs/spine-v2-anchors.json`
and its plain-language companion `docs/superpowers/specs/2026-08-16-spine-v2-estimation-anchors.md`.
**Prior rounds carried forward:** `docs/superpowers/specs/spine02-prereg.json` (byte-frozen
thresholds) and `docs/superpowers/specs/2026-08-16-spine02-results.md` (the verdicts).
**Added the same day, before the seal:** **§11**, the two owner-agreed
regime-identification obligations — the classifier's thresholds perturbed each way, and a
richer identification of the same four seasons compared under a decision rule declared in
advance. Its result is that **the simple two-dial classifier stays as the grader and no bar
is re-anchored**, with two disclosures the owner should read beside D1–D3 (§11.3, §11.6).

Nothing in this document has been fitted to. No engine work has started. That is the point:
these bars are written down, with their justifications, **before** any result exists.

---

## Closed before sealing — the OPEN items

This document was drafted with four measurements missing, each blocking named bars.
**All four have been made** (2026-08-17), by extending `scripts/spine_v2_anchors.py` —
same determinism rules, one literal seed per new section, byte-identical re-runs — and
they are recorded in the anchors JSON as sections `e_ordering`,
`f_correlation_intervals`, `g_dwell_intervals` and `h_generated_side_power`, with the
plain-language write-up in §9 of
`docs/superpowers/specs/2026-08-16-spine-v2-estimation-anchors.md`. This table is now the
record of what was added and what it changed. The bars themselves are stated, as always,
in their own subsections below.

| # | What was missing | What was measured | Effect on the bars |
|---|---|---|---|
| **OPEN-1** | No clockwise-fraction measurement on this vintage; the 0.6029411764705882 anchor came from round one's seal, measured by an earlier run of the pipeline. | Recomputed on vintage `2026-08-10.1`, reusing the pilot's own definitions by import (`ah.gen.spine.panel_quadrant`, `ah.gen.spine.CLOCKWISE`; the transition rule of `scripts/spine_pilot_seal._b4_clockwise_fraction`). **0.6029411764705882 on 68 transitions, 41 of them clockwise — bit-identical to the sealed value.** Block-bootstrap 95% interval **[0.5185185185185185, 0.6842285508291275]**. | **O1 changed.** Its bar moves from the point anchor to the interval's **lower edge, 0.5185** — see §2, O1(a) and O1(c). |
| **OPEN-2** | No sampling interval on the stock–bond correlation gap; A2's 0.15 margin rested on threshold sensitivity plus a halving rule. | Block bootstrap, same machinery and block lengths as the transmission interval. High-minus-low **correlation difference 0.3194875488039316, 95% interval [0.13609378139729844, 0.556828299873221]**. High-minus-low **share-of-windows-positive difference 0.40507701786814543, 95% interval [0.17717364337543898, 0.6231004989665900]**. | **A2(i) changed.** Its margin moves from 0.15 to the measured **lower edge, 0.1361** — see §4, A2(a) and A2(c). **A2(ii) unchanged**; the measurement supports its edges rather than moving them. |
| **OPEN-3** | No sampling interval on the per-season dwell medians. | Bootstrap over **spells** (the independent units), 10,000 draws: recession 3 months **[1.0, 12.5]**, stagflation 4 **[1.0, 10.5]**, recovery 9 **[5.0, 16.0]**, expansion 6 **[3.0, 12.0]**. | **D1–D4 unchanged** — the ±1 quarter tolerance stands on its play-unit justification. But the check it was asked to pass **failed in all four seasons**: the tolerance is *narrower* than the median's own sampling wobble everywhere. Recorded in §3 and it changes how a D verdict must be read. |
| **OPEN-4** | No power calculation for the generated side. | Simulation, 2,000 ensembles per grid point, a true engine modelled as one emitting uniformly-drawn contiguous 120-month stretches of the panel. Decades needed for a 90% pass: **T1 5, O1 5, D1 15, D4 10, A1 40, D2 50, A2 400, D3 never.** | **Ensemble size fixed at 50 decades per premise** (§8.1). Two bars came back as bar-design problems rather than sizing problems — **D3 is unpassable by a true engine as written, and A2 is dominated by its low-inflation ceiling** — both flagged for the owner in §8.1. |

An amendment after the seal goes through the machine-checked log, never by editing this file.

---

## 1. Purpose

The decade generator's economic engine is being rebuilt so that the storyline — inflation,
policy, growth, the seasons of the economic cycle — is *generated* rather than pasted
together, and this exam is the fixed set of pass/fail tests it has to clear afterwards. The
owner's purpose statement governs what is tested: **the product tests robust asset
allocation, not lever timing** — a player should be rewarded for holding a portfolio that
survives a range of futures, not for guessing when a central bank moves. That is why two of
the ten bars below are allocation bars measured on **asset returns** (what commodities,
bonds and equities did), never on portfolio outcomes. Every bar is written down here, with
its exact number, the historical fact it comes from, and why its tolerance is the size it
is, **before any fitting has been done** — because a threshold chosen after seeing results
is not a test, it is a description. When this document is approved, the thresholds and the
code that judges them are hashed together into a seal, and after that they can only change
through the amendment log.

---

## 2. The causal tier — does the engine have cause and effect?

Two bars. Together they ask whether the generated worlds have an economy in them or just a
sequence of moods.

### T1 — "does tightening cause downturns?" (the transmission bar)

**The plain question.** In real history, when monetary policy is tight, a downturn is more
likely to begin over the following year. Does the same hold in the generated worlds, and by
about the same amount?

**What the words mean.**
- **Tight policy** here means an **inverted yield curve**: the interest rate on 10-year
  government debt sits *below* the rate on 2-year debt. That is unusual — normally you are
  paid more for lending longer — and historically it is the single most reliable warning
  sign of a coming downturn. Owner ruling, 2026-08-17: this is the definition, applied
  **identically on both sides** — the same 10-year-below-2-year test on real history and on
  the generated worlds.
- **A downturn** means a month whose regime label turns to **recession or crisis**
  (`REC` or `CRI` under the platform's published labelling rule `regime_ruleset_v1`).
  Both sides use this same union. This is not a free choice: the spine-02 verdict-integrity
  review found the previous round's judge compared *recession-or-crisis* events on the model
  side against *crisis-only* events on the history side, and the resulting FAIL was an
  artefact of that mismatch, not a finding about the model.
- **Lift** means: the chance a downturn starts within the next 12 months measured over tight
  months only, divided by the same chance measured over all eligible months. A lift of 1.0
  means tightness tells you nothing.

**(a) The bar.** The generated worlds' lift, computed exactly as above, must land inside

> **[1.7752827491108736, 3.3473622102535145]** — read as **[1.78, 3.35]**.

Eligibility is matched on both sides: a month counts only if it has a defined trailing
12-month inflation reading and a full 12 months of future path left to look into. On a
120-month generated decade that leaves 96 eligible months per decade.

**(b) The historical anchor.** History's own lift on this definition is
**2.3718540268456376** (2.37×) — 86 of 149 inverted-curve months were followed by a downturn
onset within 12 months (a 57.72% chance), against 192 of 789 months overall (24.33%).
Inverted-curve months are 149 of 789, or 18.88% of the panel
(`b_transmission_lift.point_estimates.rec_plus_cri`, `primary_tight_base_rate`).

**(c) Why the band is that wide.** The band is the 95% interval from a **block bootstrap** —
a way of putting error bars on a statistic when the observations are not independent.
Downturns arrive in clumps and so do inverted-curve months, so consecutive months carry much
of the same information; the bootstrap rebuilds fake 789-month histories out of randomly
chosen *runs* of consecutive real months (average run length 24 months, 2,000 repetitions,
one fixed seed `20260816`) so the clumping survives into the error bar. The width is not a
modelling choice that better estimation could tighten: it is what **seventeen downturn events
in 68 years** support. Two facts make it defensible rather than arbitrary. It barely moves
when the bootstrap's run length changes — [1.7690954133122256, 3.344157353806588] at 12
months and [1.855774205869812, 3.3351204643619226] at 36 months — so it is not an artefact of
that choice. And it excludes 1.0 comfortably, so an engine with no policy-to-downturn channel
at all fails it.

**Crisis-only is deliberately NOT a bar.** The same statistic measured on the severe
subset — crisis onsets only — gives a lift of **2.8646715810320167** with a 95% interval of
**[0.7051593174267592, 5.045392747118623]**. That interval **contains 1.0**. There are only
**six crisis events** in the whole panel (1970-01, 1970-04, 1974-03, 2001-06, 2008-09,
2020-03), and six events cannot rule out that an inverted curve tells you nothing at all
about crises. A bar built on it would be nearly unfailable and therefore worthless. The
crisis-only figure is **reported as a disclosure beside every T1 verdict**, never judged.

**(d) What a FAIL means in product terms.** A fail here means tightening still does not cause
downturns in the generated worlds — so a player who correctly reads a tightening cycle and
shifts toward defence is not rewarded for being right, and the game teaches nothing about
policy risk.

**What this bar does and does not test — a caveat that rides with it.** Under the
selection-only rule (R1: the compiler chooses real months, never edits them), the yield curve
in a generated world is carried in by the *selected historical months*, while the downturn
labels are driven by the *spine*. So T1 tests two things at once: that the engine has a
transmission channel, and that the flesh selected around the spine stays aligned with it. A
FAIL does not by itself say which of the two broke, and the judge must report both the
generated side's tight-month base rate and its conditional/unconditional rates so the two can
be separated by eye. The alternative — conditioning the model side on its own internal policy
gap — is what round two did, and the review found it was comparing a market price against a
policy setting. The owner's identical-conditioning ruling removes that ambiguity at the cost
of the one named above.

### O1 — "the seasons turn the right way round" (the ordering bar)

**The plain question.** The economy moves through four seasons in a broadly repeating order.
Do the generated worlds turn the same way, or do their seasons arrive shuffled?

**What the words mean.** Every month is placed in one of four boxes — the **investment
clock** — by two yes/no questions: is the economy expanding, and is inflation hot (above the
panel's own line, 3.351323828920571 percentage points)?

| | inflation cool | inflation hot |
|---|---|---|
| **expanding** | recovery | expansion |
| **contracting** | recession | stagflation |

The **clockwise** order is recovery → expansion → stagflation → recession → recovery. The
**clockwise fraction** is the share of all month-to-month season changes that follow that
order.

**(a) The bar.** The generated worlds' clockwise fraction must be

> **≥ 0.5185185185185185** (0.5185) — one-sided.

That number is the **lower edge of the historical anchor's own 95% interval**, not a
tolerance chosen around it.

**(b) The historical anchor.** History's clockwise fraction is **0.6029411764705882**, on
**68 season transitions**, 41 of them clockwise. Sealed in round one as
`b4.panel_clockwise_fraction` in `docs/superpowers/specs/spine-pilot-prereg.json`, and
**re-measured on this exam's own panel vintage (`2026-08-10.1`) where it reproduces
bit-identically** (`e_ordering.clockwise_fraction`, OPEN-1 closed). Its block-bootstrap 95%
interval is **[0.5185185185185185, 0.6842285508291275]** at the primary 24-month run length,
moving to [0.5098, 0.6957] at 12 months and [0.5273, 0.6818] at 36 — so, as with T1, the run
length is not driving it. The binomial standard error is **0.05933493096110905**, the "≈
0.059" the round-one seal disclosed.

**(c) Why the bar sits at the interval's lower edge.** The draft of this document set the bar
at the point anchor itself and flagged the problem in the same breath: *the anchor is an
estimate*, so an engine whose true ordering exactly matched history's could still land below
0.6029 and fail. A bar that a correct engine fails one time in two is not a test of the
engine. The bar therefore demands what a bar can honestly demand — **consistency with
history** — and 0.5185 is the point below which the generated fraction is no longer
consistent with the historical one.

**This does not reopen round two's false pass, and the margin is thin enough to state
exactly.** Round two's five seeds measured 0.4574, 0.4820, 0.4831, 0.4886 and **0.5176**.
All five are still below 0.5185 — the best of them by **0.0009**. The bar that a coin flip
passed (round one's two-sided ±0.15, lower edge 0.4529) is not what this is; but the owner
should see that this bar's discriminating power against round two's engine now rests on the
last decimal place of one seed rather than on a comfortable gap.

**Two alternatives, both stated before any v2 result exists.** The drafter's own suggestion
was to absorb *one* standard error rather than the full interval: **≥ 0.6029 − 0.0593 =
0.5436** (`e_ordering.one_se_below_point`), which is stricter and would fail all five
round-two seeds with room to spare. And an i.i.d.-over-transitions bootstrap would put the
edge at **0.4853**, which is looser and *would* let round two's best seed through. The block
interval was chosen because it is the same kind of object as every other interval in this
exam; the fact that it comes back **narrower** than the i.i.d. one is not a mistake but a
measured property — the clockwise indicator's lag-1 autocorrelation across consecutive
transitions is **−0.342**, i.e. the clock backtracks and then returns, so consecutive
transitions carry more information kept together than scrambled. If the owner prefers the
one-SE bar, **now, before any result exists, is the only time that can be decided without it
being goalpost-moving.**

**(d) What a FAIL means in product terms.** A fail means the seasons arrive in a shuffled
order, so nothing a player learns in one world about what usually follows what transfers to
the next — the game becomes a slot machine with economic vocabulary.

**Threshold-sensitivity disclosure, added 2026-08-17 (§11.2–11.3).** O1 is the most robust
of the six classifier-dependent bars. Perturbing either dial by 50 basis points moves the
historical clockwise fraction only within **0.5556 – 0.6250**, well inside its own 95%
interval and **above this bar under every one of the eight perturbed arms** (worst arm clears
by 0.0370). The richer five-input classifier of §11.4 moves it by 0.0064. O1 can therefore
be quoted without a threshold caveat — which is not true of D1, D2 or D3.

---

## 3. The persistence tier — do the seasons last as long as they should?

Four bars, one per season. **A "spell" is an unbroken run of months in one season**, and its
length is what these bars test.

**Two rules that apply to all four, stated once.**

*Completed spells only, censored ones disclosed.* A spell that was already running when the
usable record starts, or is still running when it ends, has an unknown true length — we only
see part of it. Including such a spell drags the median down. Owner ruling: the headline
anchors use **completed spells only**. The panel contains exactly two censored spells, both
in the recession season, and both are disclosed beside the D1 headline with their observed
minimum lengths.

*Tolerance ± 1 quarter on every season's median.* Owner ruling, with its justification: **a
quarter is the game's smallest play unit.** The player makes decisions on a quarterly cycle,
so a season whose length is right to within one quarter is right to within the finest
distinction the product can express; a tighter bar would be grading a difference no player
can act on, and a looser one would let a season be off by a decision cycle. **The tolerance
is unchanged by OPEN-3** — its justification is a product fact, and a product fact is not
overturned by a sampling interval.

**But the check OPEN-3 was asked to perform came back negative in all four seasons, and that
changes how a D verdict must be read.** The medians were bootstrapped by resampling
**spells** — a spell's months are one observation of one dwell, not many independent
observations of it, so the spells are the independent units and resampling months would have
returned an interval far too narrow (`g_dwell_intervals`, 10,000 draws, seed `20260819`):

| season | completed spells | median | **95% interval** | half-width | ±1 quarter is wider? |
|---|---|---|---|---|---|
| recession (D1) | 12 | 3 months | **[1.0, 12.5] months** | 9.5 months (3.17 q) | **no** |
| stagflation (D2) | 12 | 4 months | **[1.0, 10.5] months** | 6.5 months (2.17 q) | **no** |
| recovery (D3) | 22 | 9 months | **[5.0, 16.0] months** | 7.0 months (2.33 q) | **no** |
| expansion (D4) | 21 | 6 months | **[3.0, 12.0] months** | 6.0 months (2.00 q) | **no** |

The anchors' interquartile ranges suggested the medians were soft; this measures it, and they
are softer than the argument suggested — by about a factor of two for expansion and
stagflation, and more than three for recession. The consequence, which the judge must print
beside every D verdict: **a D-bar FAIL that misses by one quarter is inside the anchor's own
sampling noise and is not evidence about the engine**; a FAIL that misses by two quarters or
more is outside it for stagflation, recovery and expansion. Nothing about the pass/fail
arithmetic changes; what changes is that a marginal FAIL may not be reported as a finding.

*A floor note that applies to D1 and D2.* No spell can be shorter than one month (0.33
quarters), so where the ±1 quarter band's lower edge falls at or below that floor, the bar
binds only from above. This is stated per bar rather than hidden.

**A second disclosure that applies to all four, added 2026-08-17 (§11.3).** These four
anchors are computed from a classifier with two threshold dials, and §11 perturbs each by
50 basis points. The four medians survive that perturbation *relative to their own sampling
intervals* (all four verdicts are STABLE), but **relative to the ±1 quarter bands above they
do not**: history's recession median leaves D1's band under 3 of the 8 perturbed arms, its
stagflation median leaves D2's under 6 of 8, and its recovery median leaves D3's under 3 of
8. **D4 is the only one of the four that stays inside its band under every arm.** No band is
changed because of this — that would be the goalpost move pre-registration exists to prevent
— but a D verdict should be read with it in view, alongside the OPEN-3 caution above.

### D1 — "how long a recession lasts" (contracting, inflation cool)

**(a) The bar.** Median completed recession spell in **[0.00, 2.00] quarters** = **[0, 6]
months**. Because a spell is at least one month, the achievable band is [0.33, 2.00]
quarters and **the bar binds only from above**: a recession season whose median exceeds 6
months fails.

**(b) The historical anchor.** **1.00 quarter (3 months)**, from **12 completed spells**
(`c_regime_durations.per_quadrant.recession.median_quarters` = 1.0,
`median_months` = 3.0, `n_completed_spells` = 12). Interquartile range 0.33–4.08 quarters
(1–12.25 months).

**Censored disclosure (owner ruling).** Two recession spells are censored and are excluded
from the anchor above:
- **1954-04 → 1954-11**, left-censored, **observed minimum 8 months** (it was already running
  when the usable record begins, twelve months in, because trailing inflation is undefined
  before then);
- **2019-04 → 2020-12**, right-censored, **observed minimum 21 months** (still running when
  the panel ends in December 2020).

Including both, the recession median rises from 3 months to **5 months** — which is exactly
the pilot's sealed anchor `panel_dwell_medians = [5, 4, 9, 6]` **months** (not quarters; the
unit slip is corrected in the anchors document §4). Recession is the *only* season where the
choice matters; stagflation, recovery and expansion read identically either way.

**(c) Why ±1 quarter.** The quarter is the smallest play unit (see above). Note also that
recession's median rests on twelve spells whose middle half runs from 1 to 12.25 months — a
distribution that wide, observed twelve times, cannot support a tighter bar than this.

**Disclosure the owner should carry: this bar is looser on recession than round one's was.**
Round one judged the recession median as a ratio against the all-spells anchor of 5 months
inside a [0.6, 1.4] band, i.e. 3.0–7.0 months; three of five seeds failed it at medians of 2
months. The completed-spell switch moves the anchor to 3 months and the band to 0–6 months,
under which those same seeds would pass. This is a consequence of the correctness ruling
(completed spells only), not a weakening chosen to make a result look better — and it is
stated here, before results, for exactly that reason.

**(d) What a FAIL means in product terms.** A fail means recessions in the game run longer
than history's, so the player spends implausible stretches of every world in a downturn and
learns to hold permanently defensive allocations — which is not robust allocation, it is
pessimism rewarded by a bug.

### D2 — "how long stagflation lasts" (contracting, inflation hot) — first-class, per the owner

**(a) The bar.** Median completed stagflation spell in **[0.33, 2.33] quarters** = **[1, 7]
months** (the arithmetic band is 1.33 ± 1.00 quarters; its lower edge coincides with the
one-month floor, so it binds mainly from above).

**(b) The historical anchor.** **1.3333333333333333 quarters (4 months)**, from **12
completed spells**, none censored
(`c_regime_durations.per_quadrant.stagflation`). Interquartile range 0.33–3.42 quarters
(1–10.25 months). The full sorted list is short enough to print: 1, 1, 1, 1, 2, 2, 6, 8, 10,
11, 16, 21 months.

**(c) Why ±1 quarter.** Smallest play unit, as above. Twelve spells with a median of 4 months
means moving a single spell by one month can move the median by half a month; a bar tighter
than a quarter would be testing that wobble rather than the engine.

**Why this bar is first-class (owner's emphasis, 2026-08-17).** Stagflation — the economy
contracting *while* inflation runs hot — is **as bad or worse for a portfolio than an
ordinary recession**, because it is the one season where the usual defence fails: bonds do
not rescue equities (see **A2**), and the assets that do help are the ones most allocators
hold least. A generated world that skips lightly through stagflation is not a mildly wrong
world; it is a world missing the hardest allocation problem the product exists to teach. That
is why stagflation gets its own bar rather than being averaged into a "downturn" cell.

**(d) What a FAIL means in product terms.** Too short, and the season that most punishes a
conventional 60/40 book is a blip the player can wait out, so nothing rewards holding real
inflation defence; too long, and stagflation dominates every world and the player learns a
single trade rather than robust allocation.

### D3 — "how long a recovery lasts" (expanding, inflation cool)

**(a) The bar.** Median completed recovery spell in **[2.00, 4.00] quarters** = **[6, 12]
months**. Both edges bind.

**(b) The historical anchor.** **3.00 quarters (9 months)**, from **22 completed spells**,
none censored. Interquartile range 1.42–5.83 quarters (4.25–17.5 months).

**(c) Why ±1 quarter.** Smallest play unit. Twenty-two spells is the best-supported of the
four cells, so this bar could in principle be tighter than the thin ones — but the owner's
ruling sets one tolerance across all four seasons for comparability, and a quarter is the
finest distinction the product can express regardless of how well-measured the anchor is. The
distribution is extremely skewed (2, 2, 3, 3, 3, 4, 5, 5, 5, 6, 6, 12, 13, 14, 16, 16, 18,
19, 25, 39, 62, **100** months), so the median is the right summary and the tail is not
tested by this bar.

**This is the bar that caught the real defect.** Round two's engine produced recovery medians
of 2 to 3 months against history's 9, failing on **all five seeds** — the clearest
apples-to-apples signal in the whole prior record, judged by frozen code both rounds. It is
also squarely inside D-SP-6's funded scope ("recovery-duration refit to the historical event
chronology"), so this is a bar the rebuild is expected to flip.

**⚠ OPEN-4 found that this bar, as written, cannot be passed by a correct engine — owner
decision needed before the seal.** The power calculation measures a *true* engine — one
emitting real contiguous 120-month stretches of US history — producing a pooled recovery
median of **5 months**, outside the [6, 12] band, with power *falling* as the ensemble grows
(0.36 at 20 decades, 0.14 at 300) because it is converging on a value the band excludes. No
other bar behaves this way, and the cause is not the engine, the tolerance, or the ensemble
size: **the anchor was measured panel-wide and the bar is judged per decade.** Cutting 68
years into decades censors long spells at the decade edges, and recovery's distribution has a
hole exactly where its median sits — sorted, it runs 2, 2, 3, 3, 3, 4, 5, 5, 5, 6, 6, **12**,
13, 14, … so the panel-wide median of 9 is the midpoint of a jump from 6 to 12 and nothing
observed lies there. A slight re-weighting toward shorter spells moves it discontinuously to
5. OPEN-3's interval says the same thing from the other side: recovery's median has a 95%
interval of **[5, 16] months**, so 9 was never a firm number.
**This is a bar-design question and it is deliberately not resolved here** — the options
(re-anchor D3 on decade-measured spells, widen its band to the sampling interval, or accept
that D3 is a bar the engine is expected to fail for a reason that is not the engine's) each
change what the exam tests, and that is the owner's call, taken before results exist rather
than after.

**(d) What a FAIL means in product terms.** Too short, and the good stretches never last, so
patience is never rewarded and the player learns to stay defensive forever — the exact
opposite of the robust-allocation lesson.

### D4 — "how long an expansion lasts" (expanding, inflation hot)

**(a) The bar.** Median completed expansion spell in **[1.00, 3.00] quarters** = **[3, 9]
months**.

**(b) The historical anchor.** **2.00 quarters (6 months)**, from **21 completed spells**,
none censored. Interquartile range 1.00–4.33 quarters (3–13 months).

**(c) Why ±1 quarter.** Smallest play unit; 21 spells, skewed (1, 1, 1, 1, 1, 3, 3, 3, 4, 4,
6, 7, 8, 11, 12, 13, 14, 19, 24, 40, 58 months), same reasoning as D3.

**(d) What a FAIL means in product terms.** A fail means the hot-and-growing season — the one
where an allocator is most tempted to add risk and most needs to judge how long the party
lasts — is either over before it can be traded or never ends, so the timing-versus-robustness
lesson the product is built around cannot be taught.

---

## 4. The allocation tier — do the right assets get rewarded?

Two bars, both added by D-SP-6, both measured on **asset returns** and never on portfolio
outcomes. The reason for that restriction is rule 1 of the stress methodology — *severity is
never tuned to portfolio results* — restated in §6.

**The high-inflation line: 4% trailing CPI, and why (owner ruling, 2026-08-17).** Both bars
split months into "high inflation" and "low inflation" by **trailing 12-month CPI inflation
at or above 4%**. The reasons, all stated before any result is graded:
1. **It is a genuinely-high-inflation test.** 4% is roughly double a modern central bank's
   target. A lower line lets ordinary years count as inflationary and the test stops being
   about inflation.
2. **It is conventional, not estimated.** The line was not chosen by looking for the value
   that produces the largest effect; it is the round number a practitioner would name.
3. **The sensitivity is published in the same document** (below), including the one place the
   answer reverses — so nobody has to take the choice on trust, and the choice cannot be
   re-made after seeing results.

At the 4% line the panel has **225 high-inflation months and 576 low-inflation months**.

**What is NOT here: real assets.** The owner's original framing of this bar was "real assets
versus nominal bonds". **The catalog registers no monthly real-asset total-return series** —
an intake schema exists (`src/ah/data/schemas/nareit_returns.py`) but no series has been
ingested, and the only real-asset history present (`jst.usa_housing_tr`) is annual. Every
`real_assets` field in the anchors file is `null` by construction. The bar is therefore
**commodities minus bonds only**, and *real assets minus bonds is explicitly null and
disclosed, never substituted*. If a monthly real-asset series is ingested later, adding that
leg is an amendment, not a silent extension.

### A1 — "does the inflation hedge pay when inflation is high?" (the spread bar)

**The plain question.** Commodities are the thing an allocator holds *because* it is supposed
to do well when inflation is high; long government bonds are the thing that suffers. Does the
gap between them widen when inflation is high, as it did in history?

**What the words mean.** The **spread** is commodities' annualised average return minus
bonds', in percentage points. Returns are annualised **arithmetically** (twelve times the
mean monthly return) because only the arithmetic version is additive across assets — a
difference of two arithmetic annualised means is itself a valid annualised difference. Bonds
are the platform's sealed `govt_tr_10y` transform applied to the 10-year Treasury yield (the
panel carries no bond total-return column); commodities are the panel's AQR equal-weight
commodity total return.

**(a) The bar.** At the 4% line, in the generated worlds:
> **spread(high inflation) > spread(low inflation)** — a strictly positive difference.

with a plausibility containment condition: the high-inflation spread must land inside
**[−5.053054679081145, +32.31605649965673] pp**, the full range spanned by the five named
historical episodes.

**(b) The historical anchors.** At the 4% line, from
`d_allocation_episode_facts.inflation_states.cpi_yoy_ge_4pct`:

| | high inflation (≥4%) | low inflation (<4%) |
|---|---|---|
| commodities | +12.071515017325682 %/yr | +6.800995026567669 %/yr |
| bonds | +7.199556518375341 %/yr | +5.422319207648189 %/yr |
| **commodities − bonds** | **+4.871958498950341 pp** | **+1.37867581891948 pp** |

History's margin is **+3.49 pp** (4.87 minus 1.38). The per-episode spreads, which set the
containment range, are:

| episode | months used | commodities − bonds |
|---|---|---|
| post-war calm 1953-04…1965-12 | 141 | **+2.651683219332134 pp** |
| first oil shock 1973-01…1975-12 | 36 | **+32.31605649965673 pp** |
| great inflation 1977-01…1982-12 | 72 | **+4.679409544353171 pp** |
| great disinflation 1983-01…1999-12 | 204 | **−2.8161608171996004 pp** |
| post-GFC calm 2010-01…2019-12 | 120 | **−5.053054679081145 pp** |

**(c) Why the bar is directional and the band that wide.** Across five real decades of US
history the same statistic ran from **−5.05 pp to +32.32 pp** — a 37-point range, both ends
of which actually happened. Even restricting to the two in-panel high-inflation episodes, it
is **+4.68 pp** in one and **+32.32 pp** in the other: the 1973–75 oil shock alone was a
three-year, 30%-volatility commodity event that would breach almost any narrow band from
above. A band tighter than the episode range would be rejecting behaviour that is on the
record. So the testable content is the **direction**, and the magnitude condition is a
plausibility check. Be honest about how much the containment half is worth: because the
compiler is **selection-only** (verbatim historical months, never edited), the generated
worlds' spread is structurally bounded by history's own months, so the containment condition
is closer to a plumbing assertion than to evidence about the engine — in the same sense
round one's B5 recovery cell was tautological. **The directional half is the real test.**

**The 3% sensitivity, published here, including the sign flip.**

| inflation line | high-inflation months | spread, high | spread, low | high − low |
|---|---|---|---|---|
| **3%** | 368 | **+2.047212191625329 pp** | **+2.6257132735411672 pp** | **−0.58 pp — SIGN FLIPS** |
| **4% (the bar)** | 225 | +4.871958498950341 pp | +1.37867581891948 pp | +3.49 pp |
| 5% | 153 | +8.617096086048779 pp | +0.8825497419691102 pp | +7.73 pp |

At a 3% line the ordering **reverses**: the commodities-over-bonds spread is *smaller* in the
high bucket than the low one. The cause is mechanical and worth stating plainly: a 3% line
drags most of the 1983–1999 disinflation into the "high" bucket, and that was the single best
stretch in the record for long bonds (+10.05%/yr). **This fact is not robust to the
threshold; it is conditional on it.** That is why the threshold is part of the bar's
statement, why it is fixed at 4% before results, and why the 3% number is printed here rather
than discovered later. The 3% and 5% columns are **disclosure, never judged**.

**(d) What a FAIL means in product terms.** A fail here means holding the inflation hedge is
not rewarded when inflation is high — so the single clearest allocation lesson the product
exists to teach is absent from its worlds, and a player who diversifies into real-asset-like
exposure is punished for doing the historically right thing.

### A2 — "do stocks and bonds fall together when inflation is high?" (the correlation flip bar)

**The plain question.** A conventional portfolio leans on bonds rising when equities fall.
Historically that protection **disappears when inflation is high** — the two fall together.
Does the generated engine reproduce the flip?

**What the words mean.** The **stock–bond correlation** is the correlation between the
monthly equity return and the monthly bond return. Positive means they move together, which
is what removes the diversification an allocator is counting on. A **rolling 36-month window**
is that correlation computed inside every three-year window, each window assigned to the
inflation state of its **final month** — the month the correlation is "as of".

**(a) The bar.** Both conditions must hold, at the 4% line:
- **A2(i) — level and margin.** The correlation over high-inflation months must be
  **positive**, and must exceed the correlation over low-inflation months by at least
  **0.13609378139729844** (0.1361) — the **lower edge of the historical difference's own 95%
  interval**, not a tolerance chosen around it.
- **A2(ii) — how common the flip is.** At least **80%** of 36-month windows ending in a
  high-inflation month must show a positive stock–bond correlation, and **no more than 65%**
  of windows ending in a low-inflation month.

**(b) The historical anchors.** From
`d_allocation_episode_facts.inflation_states.cpi_yoy_ge_4pct.stock_bond_correlation` and
`…rolling_stock_bond_correlation.by_threshold.cpi_yoy_ge_4pct`:

| | high inflation (≥4%) | low inflation (<4%) |
|---|---|---|
| correlation over all months in state | **+0.30125403304704923** | **−0.01823351575688256** |
| share of 36-month windows positive | **94.7%** (0.9466666666666667, 225 windows) | **54.2%** (0.5415896487985212, 541 windows) |
| mean rolling correlation | +0.30479407214313187 | +0.03224573547036783 |

History's level gap is **0.3195** (+0.30125 minus −0.01823). The rolling-window fact is the
sharpest in the whole measurement: **95% of three-year windows ending in high inflation show
a positive stock–bond correlation, against 54% — a coin flip — in low inflation.**

**(c) Where the 0.1361 margin and the 80%/65% edges come from.** The margin is now a
**measured sampling interval** (OPEN-2 closed); the two share edges remain cut from the
published threshold sensitivity, which the measurement supports rather than moves.

**The margin.** History's high-minus-low correlation difference is
**0.3194875488039316**, and its block-bootstrap 95% interval — the same Politis–Romano
machinery, the same 12/24/36-month block lengths and the same seed discipline as the
transmission interval — is **[0.13609378139729844, 0.556828299873221]** at the primary
24-month run length, moving only to [0.1195, 0.5429] at 12 months and [0.1204, 0.5509] at 36.
The bar is the **lower edge**, by the same logic as O1: what a bar can honestly demand is
that the generated difference be *consistent with* history, not that it exceed a point
estimate that is itself noisy. This is slightly **looser** than the draft's provisional 0.15,
which came from halving the historical gap — a reasonable guess at the sampling noise that
the measurement shows was a little optimistic. The correction goes the honest way and is made
here, before any result exists, exactly as the draft undertook to do.

**The two share edges are unchanged, and the same measurement supports them.** The
high-minus-low difference in share-of-windows-positive is **0.40507701786814543** with a 95%
interval of **[0.17717364337543898, 0.6231004989665900]**. The 80% floor and 65% ceiling
together demand a difference of at least **15 percentage points** — *below* that interval's
lower edge of 17.7 — so the pair of absolute edges asks for less than the measured interval
would, and neither needs to move.

**⚠ But OPEN-4 found the 65% ceiling is the binding condition and has little headroom —
owner decision needed before the seal.** Split into its four conditions, A2 needs 5 generated
decades for "correlation positive", 10 for the margin and 10 for the ≥ 80% high-inflation
share; the **≤ 65% low-inflation share needs 400**, and drags the whole bar there. The reason
is that a true engine's low-inflation share **measured on decades** is **0.6216** — 2.8 points
under the ceiling — against the **0.5416** panel-wide figure the ceiling was cut from. Part of
that shift is a property of the power model rather than of any engine (drawing decade starts
uniformly down-weights the panel's first and last few years, which are exactly its two most
negatively-correlated low-inflation stretches, the 1950s–60s and the 2010s), so the 400 is
soft. What is not soft: **the ceiling has far less room against a decade-measured statistic
than against the panel-wide one it was derived from.** Raising it is a live option and is the
owner's call, taken now.

**The threshold sensitivity the two share edges rest on:**

| inflation line | correlation, high | correlation, low | gap | windows positive, high | windows positive, low |
|---|---|---|---|---|---|
| 3% | +0.26776000715530485 | −0.09682697926086808 | 0.3646 | 85.8% | 47.9% |
| **4% (the bar)** | +0.30125403304704923 | −0.01823351575688256 | **0.3195** | **94.7%** | **54.2%** |
| 5% | +0.3390382145390731 | +0.010927392717242666 | 0.3281 | 98.0% | 58.1% |

- **The 0.1361 margin** is a little over **twice** the threshold sensitivity of the
  high-inflation level itself, which moves only 0.07 across the whole 3%→5% range, so the bar
  cannot be passed or failed by the choice of line. It still fails an engine that gets the
  sign right but the magnitude weakly — the failure mode the spine-02 review found for
  transmission ("present but weak", 1.14× against history's 2.37×) — because 0.1361 is a
  little under half history's own 0.3195 gap.
- **The 80% floor** sits 5.8 points below the *lowest* share history shows at any line
  (85.8%, at 3%); **the 65% ceiling** sits 6.9 points above the *highest* low-inflation share
  (58.1%, at 5%). Both edges therefore clear the entire published threshold range by 6–7
  points, so neither is an artefact of the 4% choice. Read the ⚠ above for what happens to
  the ceiling's headroom once the statistic is measured on decades rather than panel-wide.

**(d) What a FAIL means in product terms.** A fail means bonds keep diversifying equities
even when inflation is high — so the generated worlds never take away the protection a
conventional book depends on, players are never taught the failure mode that removes
diversification exactly when it is needed most, and the game systematically rewards the
allocation that history punished hardest.

---

## 5. The no-regression tier — what already works must keep working

Two bars carried forward **byte-frozen** from `docs/superpowers/specs/spine02-prereg.json` —
same thresholds, same judging code, so a change in verdict is attributable to the engine and
nothing else. Round-one and round-two verdicts stay frozen and are not reopened.

### R1 — "severity still bites the book" (the b3 over-commitment grid)

**The plain question.** If the worlds stop being able to hurt a portfolio, every score in the
product becomes meaningless. Does the rebuilt engine still produce worlds that strain a book
as its allocation to illiquid private assets rises?

**(a) The bar** — `b3` in `spine02-prereg.json`, quoted exactly:
- allocation grid `grid_private_pct` = **[15, 35, 40, 55]** percent in private assets;
- `coverage_must_be_monotone` = **true** — the median worst liquidity-coverage statistic must
  be **non-decreasing** across those four arms;
- `min_breach_seeds_at_55` = **1** — at the 55% arm, at least **1 of 20** seeds must actually
  breach (coverage reaching 1.0, i.e. unfunded commitments matching liquid assets);
- `n_seeds` = **20**.

**(b) The anchor.** These are not measured historical quantities but the sealed bars of the
prior round, carried unchanged. Round two measured coverage medians of **[0.0901, 0.2821,
0.3514, 0.6643]** (monotone) and **2 of 20** breach seeds at the 55% arm — **PASS**, and a
clean one: it was recorded after the seed-stride fix, so it rests on 20 genuinely distinct
storylines rather than round one's 2-of-20 collision.

**(c) Why no tolerance is attached.** There is nothing to widen: a monotonicity check and a
count of at least one breach are the loosest form each condition can take. This is a
regression guard, not an estimate.

**(d) What a FAIL means in product terms.** A fail means the worlds can no longer hurt a
book — allocation choices carry no consequence, over-commitment is free, and the scores the
product hands a player stop meaning anything.

### R2 — "eras don't teleport at the seams" (the b2 era-coherence bar)

**The plain question.** The worlds are built by stitching together six-month chunks of real
history. If the inflation environment jumps at a seam — a decade running at 1% inflation
suddenly running at 6% — the world is real month by month and incoherent as a story.

**(a) The bar** — `b2` in `spine02-prereg.json`, quoted exactly:
- `join_yoy_max_pp` = **2.5** — no seam may carry a jump in trailing 12-month CPI inflation
  larger than 2.5 percentage points;
- `p95_ratio_max` = **1.25** against `panel_p95_adjacent_yoy_pp` =
  **0.7433911963542538** — the 95th percentile of month-to-month changes in trailing inflation
  across a generated decade must be no more than 1.25 × history's own, i.e. **≤ 0.9292 pp**.

**(b) The anchor.** 0.7433911963542538 pp is history's own 95th-percentile adjacent-month
change in trailing inflation — the bar says generated worlds may be up to a quarter jumpier
than history and no more.

**(c) Why 1.25× and 2.5 pp.** Both were sealed in round one from the panel's own
adjacent-month distribution and are carried **unchanged and byte-frozen**; re-deriving them
now, with a rebuilt engine in hand, is exactly the move pre-registration exists to prevent.

**(d) What a FAIL means in product terms.** A fail means the decade teleports between
inflation eras mid-story, so a player who forms a view about the world's regime has it
invalidated by an artefact of construction rather than by an event.

**R2 is expected to flip, and that is the point.** Round two **FAILED** R2 on four of five
seeds and on the ALL row (one seed carried a 5.3195 pp join jump against the 2.5 pp bound,
and every seed's p95 sat at 0.9658–0.9678 against the 0.9292 pp bound). **Join-constraint
tightening is inside D-SP-6's funded scope.** So R2 is the one carried bar the rebuild is
expected to turn from FAIL to PASS — and because the judging code is byte-identical across
rounds, a flip is attributable to the fix rather than to a redefinition.

---

## 6. Judge-integrity obligations

Three obligations, all of them consequences of things that actually went wrong in the prior
rounds. They bind the campaign, not the engine.

**6.1 Every NEW judge ships with an anti-test sweep run on the judge itself.** Before a judge
is sealed, sweep the model parameter the judge claims to measure and confirm the judge's pass
rate **increases in the effect being measured**. The reason is on the record: round two's B1
v2 reaction-function judge produced a clean FAIL on all five seeds that carried **zero
information about the model** — the verdict-integrity review found its pass fraction
*decreased monotonically* in the reaction strength `phi`, so a model with no reaction function
at all scored best (~0.47) and the 0.90 bar was unreachable by any model, including a perfect
one. New judges in this exam — **T1, D1–D4, A1, A2** — each need this sweep; **R1 and R2**
are byte-frozen and are not re-swept, because changing them is the thing being prevented.

**6.2 The verdict-integrity review happens before verdicts reach the owner.** Round two's
numbers were computationally exact and two of its five characterizations were nonetheless
misleading (B1 v2 and B6 v2), which is a defect no amount of arithmetic checking catches. The
review re-derives each judge's formula, characterizes every FAIL, and checks that both sides
of every comparison use the same definitions — the B6 mismatch (recession-or-crisis on one
side, crisis-only on the other) is the concrete precedent, and T1 above is written to make
that particular error impossible. **No verdict is reported to the owner before this review
runs**, and its findings correct the *reading*, never the sealed values.

**6.3 Rule 1 restated: severity is never tuned to portfolio outcomes.** No threshold anywhere
in this exam may be adjusted because of what it does to a portfolio's returns, drawdowns or
score. That is precisely why the two allocation bars are defined on **asset returns** —
commodities, bonds and equities — and not on any book's outcome: an asset-level bar cannot be
tuned toward a portfolio result without the tuning being visible as a change to a published
historical anchor.

---

## 7. What is NOT in this exam

Stated plainly so the exam's scope cannot be over-read from its passing.

- **No stagflation-entry transmission bar.** The natural companion to T1 — "does tight policy
  make *stagflation* more likely?" — is not here because the counts do not support it.
  History gives **12 completed stagflation spells**, i.e. twelve entries in 68 years, against
  the seventeen recession-or-crisis onsets T1 rests on; and the anchors file measures no
  tight-conditioned stagflation onset rate at all, so building the bar would mean adding the
  measurement first. The demonstration of what small counts buy is already in hand: the
  crisis-only lift, on six events, has a 95% interval of **[0.71, 5.05]** — an interval that
  contains "tightness tells you nothing". A twelve-event stagflation bar would be no better.
- **No real-asset spread bar.** There is no monthly real-asset total-return series in the
  catalog (§4). `real_assets_minus_bonds` is `null` throughout the anchors file and stays
  null; nothing is substituted for it. A1 is commodities-minus-bonds and is labelled as such
  everywhere.
- **No 2021–22 anchor anywhere.** The 2021–22 inflation surge is the episode a present-day
  allocator most wants and it lies entirely inside the platform's sealed holdout (2021-01
  onward), which was already spent at WP5.6. The anchors script declares the episode and
  emits it as `available: false`, `months_in_panel: 0`, with the reason. **Every episode band
  in this exam rests on in-panel episodes** — the 1973–75 oil shock and the 1977–82 great
  inflation on the high-inflation side, the post-war calm, the great disinflation and the
  post-GFC calm as contrast eras. Opening the holdout to set a bar would be fitting to data
  that was held back, and would need its own recorded owner decision.
- **Stage 2 is not funded.** D-SP-6 funds the generation-time hazard link, the
  recovery-duration refit and join-constraint tightening. **Model-implied conditional means
  ("stage 2") and any L3 generator are explicitly out.** The flesh stays selection-only (R1
  of the compiler design: state chooses *which* real months are drawn, never edits them), so
  every world's severity ceiling remains history's worst months.
- **ER-14 is the second leg, and this exam does not cover it.** The owner's allocation thesis
  has two halves: that inflation moves asset returns (this exam), and that it reaches an
  institution's **private** book. ER-14 records that it does not — private equity is
  bit-identical from 1% to 12% inflation, real estate moves the wrong way, and the apparent
  response of the private book is a second-order effect of the commodity sleeve beside it
  (`docs/current/private-markets-and-inflation.md`). **A clean pass on A1 and A2 would say
  nothing about that.** ER-14 is acknowledged in D-SP-6 and is not scheduled.
- **No reaction-function bar and no hazard-frequency bar are carried.** B1's v2 construct was
  found uninformative and no v3 judge is specified; B5 v2's weak cross-seed over-firing signal
  (pooled +16.9%, z = 2.41) was recorded but its construct changes once the hazard becomes
  generation-time rather than a post-hoc overlay. Both are **omissions the owner should
  confirm are intended**, not oversights — if either belongs in stage 1, it must be added
  before the seal.

---

## 8. Process — what happens after the owner approves

1. **Approval.** The owner approves this document, or amends it. Amendments made now cost
   nothing; amendments made after the seal go through the machine-checked log. **Three
   decisions are waiting on this step and all three are cheap now and expensive later:** O1's
   bar (interval edge, as written, or the stricter one-SE variant — §2), D3's band (which a
   correct engine cannot clear as written — §3), and A2's 65% ceiling (2.8 points of headroom
   against a decade-measured statistic — §4). **§11's threshold-sensitivity result belongs
   with them**: it changes no bar, but it shows that D1, D2 and D3 each sit outside their own
   band when the inflation line moves half a percentage point, which bears on what the owner
   decides about D3 in particular.
2. ~~The OPEN items are closed~~ — **done, 2026-08-17.** See the table at the top for what was
   measured and what moved: O1's bar and A2's margin now sit at the lower edge of their
   anchors' own 95% intervals, the dwell tolerance stands but its reading changed, and the
   ensemble size is fixed below.
3. **The judges are coded from this document**, one per bar, each printing its own inputs
   (both sides' base rates, counts and eligible-month totals) so a verdict can be read rather
   than trusted.
4. **An anti-test sweep is run on every new judge** (§6.1) and its result is recorded beside
   the judge. A judge whose pass rate does not increase in the effect it claims to measure
   does not get sealed.
5. **The seal.** Thresholds **and the code that judges them** are hashed together into
   `docs/superpowers/specs/spine-v2-prereg.json` before any fitting run, following the
   platform's standing pre-registration discipline. Prior rounds' seals stay untouched; b2 and
   b3 are carried in byte-frozen.
6. **Then, and only then, the engine work starts.** Verdicts pass through the
   verdict-integrity review (§6.2) before they reach the owner.

### 8.1 The ensemble size — 50 decades per premise (OPEN-4 closed)

**How it was established.** A true engine — one actually sitting at the historical point
estimates — is modelled as one that emits, for each decade, a uniformly-drawn contiguous
**120-month stretch of the panel**: history's point estimates by construction, and history's
own month-to-month dependence, which an i.i.d. binomial calculation would discard. Each bar
is judged on the pooled statistic over *n* such decades exactly as the judge will judge it on
*n* generated ones, 2,000 times per grid point, from the anchor script's own seeded generator
(`h_generated_side_power`, seed `20260820`). Eligibility is matched to the judge throughout:
the decade's own 12-month inflation warm-up, T1's further 12-month lookahead (the 96 eligible
months of §2), A2's rolling windows computed **inside** the decade (84 of them), and D1–D4's
completed-spell rule applied to the decade's own edges.

| bar | power at the pilot's 20 seeds | decades needed for 90% |
|---|---|---|
| **T1** | 0.999 | **5** |
| **O1** | 1.000 | **5** |
| **D4** | 0.994 | **10** |
| **D1** | 0.967 | **15** |
| **A1** | 0.830 | **40** |
| **D2** | 0.807 | **50** |
| **A2** | 0.608 | **400** — see §4's ⚠ |
| **D3** | 0.359 | **never** — see §3's ⚠ |

**The ruling.** The exam runs at **`n_seeds` = 50 decades per premise**, which clears every
bar that a correct engine can clear — T1, O1, D1, D2, D4 and A1 — at 90% or better. **The
pilot's 20 is not enough**: it leaves A1 at 0.83 and D2 at 0.81, so either could record a
FAIL from ensemble size alone. A2's 400 and D3's impossibility are **not sizing problems and
are not bought with compute**; they are the two bar-design questions §8 step 1 puts to the
owner, and 50 is the right size whichever way those go.

**The compute implication, in one sentence.** Fifty decades per premise is 2.5× the pilot's
ensemble and the compiler is selection-only, so the decade generation itself is cheap — but
R1's b3 arm multiplies by its four allocation grid points and stays byte-frozen at its own
`n_seeds` = 20, so the incremental cost lands on the eight new judges rather than on the
carried ones, and the one number that would have made the exam expensive (A2's 400) is a bar
to fix rather than compute to buy.

---

## 9. The bars at a glance

| tier | code | plain name | the bar | historical anchor |
|---|---|---|---|---|
| causal | **T1** | does tightening cause downturns | lift inside **[1.78, 3.35]** | 2.37× (86/149 vs 192/789) |
| causal | **O1** | the seasons turn the right way round | clockwise fraction **≥ 0.5185** (the anchor's 95% interval's lower edge) | 0.6029 (68 transitions, 95% CI [0.5185, 0.6842]) |
| persistence | **D1** | how long a recession lasts | median **[0, 6] months** (binds from above) | 1.00 q / 3 months, 12 completed spells |
| persistence | **D2** | how long stagflation lasts | median **[1, 7] months** | 1.33 q / 4 months, 12 completed spells |
| persistence | **D3** | how long a recovery lasts | median **[6, 12] months** | 3.00 q / 9 months, 22 completed spells |
| persistence | **D4** | how long an expansion lasts | median **[3, 9] months** | 2.00 q / 6 months, 21 completed spells |
| allocation | **A1** | does the inflation hedge pay | spread(high) > spread(low) at 4%; inside [−5.05, +32.32] pp | +4.87 pp vs +1.38 pp |
| allocation | **A2** | stocks and bonds fall together | corr(high) > 0 and exceeds corr(low) by ≥ **0.1361** (the difference's 95% interval's lower edge); ≥ 80% / ≤ 65% of 3-year windows positive | +0.30 vs −0.02, difference 0.3195 (95% CI [0.1361, 0.5568]); 94.7% vs 54.2% |
| no-regression | **R1** | severity still bites the book | b3 byte-frozen: monotone coverage, ≥ 1/20 breach at 55% | prior seal (round two: PASS) |
| no-regression | **R2** | eras don't teleport at the seams | b2 byte-frozen: join jump ≤ 2.5 pp, p95 ≤ 0.9292 pp | panel p95 0.7434 pp (round two: FAIL) |

**Ten bars: 2 causal, 4 persistence, 2 allocation, 2 no-regression.** Run at **50 decades per
premise** (§8.1); R1's b3 grid keeps its own byte-frozen `n_seeds` = 20. Every threshold in
this table is a field in `docs/superpowers/specs/spine-v2-anchors.json` under `exam_bars`,
derived there from the measurement it is cut from rather than restated — so this table, that
file and the judges cannot disagree about a number.

**Two bars carry a ⚠ into the approval step**, both found by the OPEN-4 power calculation and
neither resolved here: **D3** cannot be passed by a correct engine as written (§3), and
**A2**'s 65% low-inflation ceiling has 2.8 points of headroom against a decade-measured
statistic and needs 400 decades to clear at 90% (§4).

---

## 10. Owner rulings incorporated (2026-08-17)

Recorded verbatim in substance so the provenance of each choice is auditable:

1. **Tight policy means an inverted yield curve**, applied identically on both sides; the
   pass band is the block-bootstrap 95% interval for the recession-or-crisis definition
   (~[1.78, 3.35]); **crisis-only must not be a bar** because its interval contains 1.0 on six
   events. → §2, T1.
2. **Duration anchors from completed spells only**, with the two censored recession spells
   disclosed beside the headline with their observed minimum lengths; **four season bars, one
   per quadrant**; stagflation is first-class because it is as bad or worse for a portfolio
   than recession; tolerance **±1 quarter**, justified as the game's smallest play unit. →
   §3, D1–D4.
3. **The high-inflation line is 4% trailing CPI**, with the **3% sensitivity published in the
   same document** including the sign flip of the commodities-minus-bonds spread, and the
   plain statement of why 4% was chosen — before results are graded, so it cannot be called
   goalpost-placing. → §4.
4. **2021–22 is excluded from anchor-setting** (it lies in the spent holdout); episode bands
   rest on in-panel episodes. → §7.
5. **No real-asset monthly series exists**, so the inflation-hedge spread bar is
   commodities-minus-bonds only; real-assets-minus-bonds is null and disclosed, never
   substituted. → §4, §7.
6. **Plain language, and every bar carries its justification** — what real quantity anchors
   it and why the tolerance is the size it is — written before results exist (D-SP-6's
   standing communication rule). → the whole document.
7. **Regime identification must be shown to be robust before the seal** — the classifier's
   thresholds perturbed each way, and a richer identification of the same four seasons
   built and compared under a decision rule declared in advance. → §11, added the same day.

---

## 11. Regime identification robustness (pre-seal, owner-agreed 2026-08-17)

Six of this exam's ten bars — **O1** and **D1–D4**, and through its downturn labels **T1**
— are measured on months that a classifier sorted into four boxes. If the boxes move when
the classifier's questions are nudged, those bars are partly measuring the questions rather
than the economy. Two obligations were agreed with the owner on 2026-08-17 and both were
run before the seal. Their full output is in `docs/superpowers/specs/spine-v2-anchors.json`
under `i_label_stability` and `j_richer_identification`; the plain-language derivation of
every number below is in §10 of the estimation-anchors companion. **Neither obligation
draws a random number** — both are deterministic recomputations of the same anchors under a
different labelling of the same months, so there is no new seed and no new tape.

### 11.0 Where this sits: hard labels now, soft labels if fitting proves unstable

Every season in this exam is a **hard label** — a month sits in exactly one of four boxes,
and a month a hair either side of a line is treated as fully in one box and not at all in
the other. That is the right place to start: it is the vocabulary the judges, the bars and
the product itself are written in, and a hard label can be audited in a way a probability
cannot. It is also a choice with a known failure mode, and the owner and the drafter agreed
on 2026-08-17 how it will be watched, in two halves. **This section is the first half**: a
pre-seal check that the labels do not move under a defensible nudge of the lines. **The
second half falls in week 2, when the engine is actually fitted** — the fit is repeated
under the same threshold perturbations used here, and if the *fitted parameters*, not
merely the historical anchors, move materially when the lines move, then the labelling
**escalates from hard labels to soft ones**: each month carries a membership weight across
the four seasons instead of a single box, and the dwell, ordering and transition statistics
become the weighted versions of the same quantities. Agreeing that escalation now, before
any fitting result exists, is what makes taking it later the execution of a plan rather
than a reaction to a number. Nothing measured below triggers it; §11.4 records the reason
it may nonetheless be needed.

### 11.1 Obligation A — what was perturbed, and why by that much

**The classifier has exactly two dials, and they are not the same kind of object.**

- The **inflation dial** is a threshold inside the classifier itself: `ah.gen.spine.
  panel_quadrant` calls a month hot when its trailing 12-month CPI inflation exceeds the
  panel's era threshold, **3.351323828920571 pp**. It is perturbed directly.
- The **growth dial** is not a threshold at all at the classifier level: `panel_quadrant`
  reads a published month label and asks only whether it is `REC` or `CRI`. Its boundary
  therefore lives one layer down, in `regime_ruleset_v1`'s **`growth_weak`** line on
  trailing industrial-production growth (**0.0 %/yr**). It is perturbed *there* and the
  months are re-labelled through `ah.data.derive.label_regime`.

**The perturbation is ±0.50 pp on each dial, in that dial's own units.** Fifty basis points
is not a round number picked for looking tidy: on the inflation side it is the platform's
own `ah.gen.spine.BACKDROP_MARGIN_PP`, the displacement the spine already treats as the
smallest meaningful move in an inflation state — it sits inside the era threshold itself
(`median(YoY) + 0.5`) and inside `spine_quadrant`'s hot test — and it is one conventional
central-bank move. The growth dial takes the same 50 basis points so that neither dial is
nudged harder than the other *in the units the dials are stated in*.

**The honest asymmetry, stated rather than hidden.** Equal in stated units is not equal in
each dial's own spread. Trailing CPI inflation has a panel standard deviation of **2.81 pp**
and **157** of the panel's months sit within 50 bp of the inflation line; trailing
industrial-production growth has a standard deviation of **5.37 pp** and only **38** months
sit within 50 bp of the growth line. So the same 50 bp is a bigger move relative to the
inflation dial, and the arms below duly relabel far more months on that dial (70–86 months)
than on the growth dial (8 months). Equalising the two in standard deviations instead would
mean nudging the inflation line by an amount no practitioner would call a threshold choice.

**The re-labelling is verified, not assumed.** The features `label_regime` classifies are
rebuilt with `ah.gen.bootstrap`'s own helpers on the same frames `build_source` uses, and
the script **asserts that the unperturbed rebuild reproduces the panel's own labels exactly**
before any threshold moves. Without that assertion every difference below could be a second
implementation drifting rather than a dial turning.

**One quirk the perturbation exposes, worth carrying.** `growth_weak` also gates the
ruleset's `STAG` branch, and `panel_quadrant` treats `STAG` as **expanding** — its
contracting test is `REC`-or-`CRI` membership and nothing else. So the six-label ruleset's
"stagflation" and the investment clock's "stagflation" are not the same object, and a hot
weak-growth month can move between *recession* and an *expanding* quadrant rather than into
the stagflation cell. §11.5 finds this biting on real months (1975).

**The nine arms** — the baseline, each dial moved each way alone, and the four joint
corners. A positive inflation delta raises the hot line (fewer hot months); a positive
growth delta raises the contraction line (more contracting months).

| arm | Δinfl | Δgrowth | months relabelled | contracting months | clockwise fraction | transitions | recession | stagflation | recovery | expansion | T1 lift |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0 | 0 | 0 (0.0%) | 197 | 0.6029 | 68 | **3** | **4** | **9** | **6** | 2.372 |
| growth −50bp | 0 | −0.5 | 8 (1.0%) | 189 | 0.5970 | 67 | 3 | 6 | 8.5 | 6 | 2.430 |
| growth +50bp | 0 | +0.5 | 8 (1.0%) | 205 | 0.6250 | 72 | 2 | 4 | 6 | 6.5 | 2.243 |
| inflation −50bp | −0.5 | 0 | 86 (10.7%) | 197 | 0.5811 | 74 | 8 | 8.5 | 8 | 7 | 2.372 |
| inflation +50bp | +0.5 | 0 | 70 (8.7%) | 197 | 0.5556 | 54 | 4 | 9 | 15 | 4 | 2.372 |
| infl − / growth − | −0.5 | −0.5 | 94 (11.7%) | 189 | 0.5833 | 72 | 7.5 | 9 | 9 | 7 | 2.430 |
| infl − / growth + | −0.5 | +0.5 | 92 (11.5%) | 205 | 0.5921 | 76 | 4 | 8.5 | 6.5 | 7 | 2.243 |
| infl + / growth − | +0.5 | −0.5 | 77 (9.6%) | 189 | 0.5577 | 52 | 8.5 | 9 | 15 | 4 | 2.430 |
| infl + / growth + | +0.5 | +0.5 | 76 (9.5%) | 205 | 0.5763 | 59 | 3.5 | 9 | 12.5 | 4 | 2.243 |

The four season columns are **completed-spell median dwells in months**, on exactly §3's
completed-spell rule (a spell touching either end of the usable record is dropped), and the
script asserts its own spell decomposition reproduces §3's lists on the baseline arm.

### 11.2 Obligation A — the verdicts against sampling noise

The rule, stated before the numbers: **STABLE** means every arm's value lies inside the
anchor's own 95% sampling interval — the interval OPEN-1 measured for the ordering fraction
and OPEN-3 measured for the dwell medians — so a 50 bp move of the line does not move the
anchor further than resampling the same history already moves it. **FRAGILE** means at
least one arm lands outside.

| anchor | baseline | arm range across the nine arms | perturbation spread | its own 95% interval | spread ÷ interval width | verdict |
|---|---|---|---|---|---|---|
| clockwise fraction (O1) | 0.6029 | 0.5556 – 0.6250 | 0.0694 | [0.5185, 0.6842] | 0.42 | **STABLE** |
| recession dwell (D1) | 3 m | 2.0 – 8.5 m | 6.5 m | [1.0, 12.5] m | 0.57 | **STABLE** |
| stagflation dwell (D2) | 4 m | 4.0 – 9.0 m | 5.0 m | [1.0, 10.5] m | 0.53 | **STABLE** |
| recovery dwell (D3) | 9 m | 6.0 – 15.0 m | 9.0 m | [5.0, 16.0] m | 0.82 | **STABLE** |
| expansion dwell (D4) | 6 m | 4.0 – 7.0 m | 3.0 m | [3.0, 12.0] m | 0.33 | **STABLE** |

**All five anchors are STABLE. Read that carefully — it is a weaker statement than it
sounds.** Every anchor passes because the sampling intervals it is measured against are
very wide, which is OPEN-3's own finding, not a new one. The recovery median moves through
a **nine-month** range under a half-point nudge of a line and still counts as stable, because
its sampling interval is eleven months wide. What §11.2 establishes is that threshold
choice adds no *more* uncertainty than the panel's own smallness already does. It does not
establish that the seasons are firmly identified, and it should not be quoted as if it did.

**Transition counts carry no verdict**, and the reason is stated rather than glossed: no
sampling interval for a *count* exists anywhere in this exam on the same footing (the
ordering bootstrap deliberately drops about one pair in `mean_block` at its block joins, so
its per-draw transition count is below the panel's by construction and is not an error bar
on it). The counts are reported as context and they move a lot — 52 to 76 against the
baseline's 68 — which is itself the point: the *number of season changes* in US history is
a function of where the inflation line sits. The O1 bar is cut from the **fraction**, which
does carry a verdict above.

**T1 is untouched in the ways that matter, and this was checked rather than assumed.** The
growth-dial perturbation moves `REC` labels, and T1's downturn definition is the
`REC`-or-`CRI` union, so T1's lift moves with it: across the nine arms the historical lift
runs **2.243 to 2.430** (panel onset counts 16 to 19 against the baseline's 17), against
T1's band of **[1.78, 3.35]**. Every arm is comfortably inside. The tight-policy side of
T1 — the 10-year-below-2-year curve test — is untouched by either dial. **A1 and A2 are
untouched entirely**: they split months at the fixed 4% CPI line, not at the era threshold,
so neither dial reaches them.

### 11.3 Obligation A — the second reading, and why it matters more

The verdict rule above answers the question the owner asked: *is the perturbation spread
inside the anchor's own sampling noise?* There is a different question the exam actually
judges with: *does the anchor stay inside its own **bar** when the line moves 50 bp?* The
two can disagree, and here they do, because the ±1 quarter bands of §3 are much narrower
than the sampling intervals of OPEN-3. Each arm was therefore also checked against the bar
cut from it (`i_label_stability.bar_band_check`):

| bar | its band | arm range | arms whose value falls **outside the bar** |
|---|---|---|---|
| **O1** ≥ 0.5185 | one-sided | 0.5556 – 0.6250 | **none** (worst arm clears by 0.0370) |
| **D1** recession | [0, 6] m | 2.0 – 8.5 m | **3 of 8** — inflation −50bp alone (8.0 m), and the two corners pairing growth −50bp with either inflation move (7.5 m and 8.5 m) |
| **D2** stagflation | [1, 7] m | 4.0 – 9.0 m | **6 of 8** — every arm that moves the inflation line at all |
| **D3** recovery | [6, 12] m | 6.0 – 15.0 m | **3 of 8** — inflation +50bp and both corners containing it |
| **D4** expansion | [3, 9] m | 4.0 – 7.0 m | **none** |

**What this says in one sentence: for D1, D2 and D3, history itself — re-measured with the
inflation line moved half a percentage point — would fail the bar that was cut from
history.** D2 is the sharpest case: *every* arm that touches the inflation line puts the
historical stagflation median at 8.5 or 9 months against a band of [1, 7]. D4 and O1 are
the two robust ones and can be quoted without this caveat.

This does not change any bar and no bar is re-cut here — re-cutting a bar because of a
sensitivity result would be exactly the goalpost-move pre-registration exists to prevent.
It is recorded for three purposes: it is the strongest argument in this document for the
week-2 soft-label escalation described in §11.0; it is a second, independent reason to read
a marginal D verdict as uninformative (§3 already gives the first); and it means **D2's
bar, like D3's, rests on a number that a defensible alternative threshold would move
outside its own band** — a fact the owner should have alongside the two ⚠ items §8 already
puts to them.

### 11.4 Obligation B — a richer identification of the same four seasons

**The taxonomy does not change.** Recession, recovery, expansion and stagflation, read off
the same two axes and the same `ah.gen.spine.QUADRANTS` encoding (the script asserts that
feeding it the incumbent growth dial reproduces `panel_quadrant`'s cells bit-identically).
What changes is *how the growth axis is decided*: four voters vote, and a stated tie-break
settles a tie.

**The rule, in full, as it would be printed in a judge:**

```
GROWTH AXIS — four voters, each firing on the months its own indicator calls most
contraction-like:
  V1  LABEL   the month's regime_ruleset_v1 label is REC or CRI      (the incumbent dial)
  V2  LABOR   the 12-month change in the unemployment rate
  V3  CREDIT  the Baa-minus-Aaa investment-grade spread
  V4  STRESS  the equity drawdown from its running peak

V2, V3 and V4 fire above a threshold set at the (1 − b) quantile of their own panel
values, where b = 0.23595505617977527 is the share of the panel's classifiable months
the incumbent dial itself calls contracting — so no voter is louder than another merely
by calling more months bad.

Let c = V1 + V2 + V3 + V4.
    c >= 3   ->  contracting
    c <= 1   ->  expanding
    c == 2   ->  V1 decides                                    (the stated tie-break)

INFLATION AXIS — unchanged: hot = trailing 12-month CPI inflation above the panel's era
threshold, 3.351323828920571 pp.

SEASON = (expanding << 1) | hot, read through ah.gen.spine.QUADRANTS.
```

**Why the thresholds are base-rate matched rather than named round numbers.** The move has
direct precedent in this exam's own measurements: `b_transmission_lift` already evaluates
every alternative tight-policy definition at the primary definition's base rate, for the
same reason — an indicator that calls more months bad scores differently for reasons that
have nothing to do with the indicator. No threshold here was chosen by looking at what it
does to an anchor, and each one's realised value is published:

| voter | indicator | threshold it lands on | months it fires on | agreement with the incumbent dial |
|---|---|---|---|---|
| V1 LABEL | `REC`/`CRI` | — | 23.60% | 100% |
| V2 LABOR | 12-month change in unemployment, pp | **> +0.4236 pp** | 23.60% | 85.0% |
| V3 CREDIT | Baa − Aaa, pp | **> 1.19 pp** | 23.22% | 73.7% |
| V4 STRESS | equity drawdown | **deeper than −10.28%** | 23.60% | 73.8% |

Vote counts across the 801 classifiable months: **398** months with no contracting vote,
**211** with one, **78** at the 2–2 tie the incumbent settles, **70** with three, **44**
with all four.

**Exactly which series each voter reads, and over what span.**

- **LABOR — `fred.UNRATE`**, monthly, registered in `requirements.yaml` and present in the
  campaign vintage from **1948-01**. That is more than five years before the panel starts,
  so the 12-month lookback exists for every panel month and no month is dropped.
- **CREDIT — the panel's own `ig_spread` factor**, Baa minus Aaa in percentage points,
  monthly across the whole panel.
- **STRESS — the equity drawdown** from the running peak of the `equity_mkt` cumulative
  index, computed by `ah.gen.bootstrap._drawdown_fraction`: the platform's *own* drawdown
  feature, the same one `regime_ruleset_v1`'s crisis branch reads.

**What was considered and NOT used, stated rather than substituted silently.**

- **`bis.credit_gap_us`** — the climate model's credit gap — is **not** the credit input,
  and the reason is availability, not preference: it is **quarterly** and begins
  **1957-10**, fifty-four months after the panel starts. Using it would mean forward-filling
  a quarterly series into a monthly classifier *and* leaving a four-and-a-half-year hole at
  the panel's head. The monthly `ig_spread` carries the same dimension over the whole span
  and is used instead.
- **`hy_spread`** is not used because on this panel it carries no information `ig_spread`
  does not: `fred.HY_OAS`'s licensed history begins 2023-08 and lies entirely inside the
  holdout, so every panel month of `hy_spread` is the spliced Baa−Aaa proxy.
- **A second inflation input does not exist over the whole panel.** The only other monthly
  inflation series in the campaign vintage is `fred.CPI_CORE`, which begins **1957-01** —
  forty-five months after the panel starts. A classifier whose rule changes part-way through
  the panel is worse than one with a single input, so the inflation axis keeps its single
  input. **This is the dimension this comparison does not enrich, and nothing is substituted
  for it.** The three extra inputs the owner named — credit, labor, market stress — are all
  cyclical or financial-conditions indicators and none is an inflation indicator, so all
  three enter the growth axis; the disagreement map below is entirely a map of
  growth-direction disagreement.

### 11.5 Obligation B — the disagreement map

**The two classifications disagree on 52 of the 801 classifiable months — 6.49%.**

Where, by decade:

| decade | classifiable months | disagreeing | share |
|---|---|---|---|
| 1950s (from 1954-04) | 69 | 1 | 1.4% |
| 1960s | 120 | 8 | 6.7% |
| 1970s | 120 | 10 | 8.3% |
| 1980s | 120 | 1 | 0.8% |
| 1990s | 120 | 0 | **0.0%** |
| 2000s | 120 | 4 | 3.3% |
| 2010s | 120 | 26 | **21.7%** |
| 2020 | 12 | 2 | 16.7% |

Where, by the season the simple classifier assigned (rows), and what the richer one made of
those months (columns):

| simple ↓ / richer → | recession | stagflation | recovery | expansion | months | reassigned |
|---|---|---|---|---|---|---|
| **recession** | 72 | 0 | **37** | 0 | 109 | **33.9%** |
| **stagflation** | 0 | 79 | 0 | 1 | 80 | 1.3% |
| **recovery** | **4** | 0 | 374 | 0 | 378 | 1.1% |
| **expansion** | 0 | **10** | 0 | 224 | 234 | 4.3% |

**The disagreement is not spread thinly — it is one concentrated defect plus three
episodes.** A third of every month the simple classifier calls a recession is reassigned,
almost all of it to recovery, and almost all of it in the 2010s. **Six runs of three or more
consecutive disagreeing months** account for 48 of the 52:

| run | months | simple | richer | what is happening in the data |
|---|---|---|---|---|
| **1960-05 → 1960-11** | 7 | recession | recovery | NBER *was* in recession (`usrec` = 1) and all three corroborating voters were quiet: unemployment up at most 0.40 pp, spread 0.76–0.82, drawdown never worse than −8%. **The richer classifier overrules a real recession here** — the 1960–61 downturn was mild on every corroborating measure. |
| **1975-04 → 1975-12** | 9 | expansion | stagflation | Industrial production −11% year on year, unemployment +3.7 pp, spread 1.6–1.8, drawdown −15% to −25%, inflation ~10%. All three voters fire. The simple classifier called these months *expanding* only because the ruleset labelled them `STAG`, which `panel_quadrant` treats as expanding — the §11.1 quirk biting on the tail of the 1973–75 bust. **The richer classifier is plainly right here.** |
| **2002-06 → 2002-09** | 4 | recovery | recession | The post-dot-com equity bear: drawdown −34% to −45%, unemployment +0.7 to +1.3 pp, spread 1.21–1.37. No NBER recession, so the simple dial says recovery. |
| **2015-03 → 2015-08** | 6 | recession | recovery | `usrec` = 0; the label is `REC` on industrial-production growth alone (−0.0% to −2.1%). Unemployment **falling** 0.7–1.3 pp, spread 0.90–1.15, drawdown ≤ 6%. |
| **2016-04 → 2017-02** | 11 | recession | recovery | Same shape: the industrial/energy slump, `usrec` = 0, unemployment falling, spreads normal, essentially no drawdown. |
| **2019-04 → 2020-02** | 11 | recession | recovery | Same shape again: the 2019 manufacturing slowdown. **This is exactly the right-censored recession spell §3 discloses beside the D1 headline** — the "observed minimum 21 months" that runs 2019-04 → 2020-12. The richer classifier keeps only its COVID tail. |

**The plain reading.** Four of the six runs are one recurring defect: `regime_ruleset_v1`
calls a month `REC` whenever trailing industrial-production growth is at or below zero, even
with no NBER recession, no rise in unemployment, no credit stress and no equity drawdown.
Those are **industrial-production-only recessions**, and they are why the simple
classifier's recession season is a third larger than the richer one's (109 months against
76). One run (1975) is the opposite error and the simple classifier is clearly wrong. One
run (1960) is a case where the **richer** classifier is wrong, because a genuine but mild
recession registers on none of its corroborating measures — a real cost of the extra
inputs, and the reason the richer classifier is not obviously the better instrument.

### 11.6 Obligation B — the decision rule and its verdicts

**The rule, quoted verbatim as declared before the comparison was run:**

> the richer classifier replaces the simple one ONLY IF the disagreement changes an anchor
> by more than that anchor's own sampling noise. Otherwise simplicity wins.

**How "sampling noise" is read**, stated because the phrase admits two readings and the
answer here is the same under both. The primary reading is the one this exam already
publishes per anchor: the absolute change between the two classifiers' values must exceed
the anchor's **95% interval half-width** — the `ci95_half_width_months` OPEN-3 already
computes, and the equivalent for the ordering fraction. The stricter alternative reading —
*the richer value leaves the interval altogether* — is reported beside every verdict.

| anchor | simple | richer | change | its 95% half-width | change exceeds it? | richer value still inside the interval? | verdict |
|---|---|---|---|---|---|---|---|
| clockwise fraction | 0.6029 | 0.6094 | 0.0064 | 0.0844 | no | yes | **SIMPLICITY WINS** |
| recession dwell | 3 m | 5 m | 2.0 m | 9.5 m | no | yes | **SIMPLICITY WINS** |
| stagflation dwell | 4 m | 3.5 m | 0.5 m | 6.5 m | no | yes | **SIMPLICITY WINS** |
| recovery dwell | 9 m | 12 m | 3.0 m | 7.0 m | no | yes | **SIMPLICITY WINS** |
| expansion dwell | 6 m | 6 m | 0.0 m | 6.0 m | no | yes | **SIMPLICITY WINS** |

**The decision rule does not trigger on any anchor, under either reading. The simple
two-dial classifier becomes the sealed grader, and no bar in this document is re-anchored.**

Two things the owner should carry out of that result rather than take it as a clean bill of
health.

1. **The rule was met comfortably in ratio terms and not in absolute ones.** The richer
   classifier moves the recession median from 3 to 5 months and the recovery median from 9
   to 12 — a third and a half of a play-quarter tolerance's worth in one case and a full
   quarter in the other — and both survive the rule only because the sampling half-widths
   they are compared against are 9.5 and 7.0 months. Recovery is also the anchor D3's ⚠
   already concerns; if the owner reopens D3, **12 months is the number the richer
   classifier would have put there**, which sits exactly on that band's upper edge.
2. **"Simplicity wins" is a verdict about the anchors, not about the labels.** The two
   classifications disagree about a third of all recession months, and §11.5 shows the
   simple one is the wrong side of that disagreement in the 2010s. The anchors survive
   because a median over ten-to-twelve spells is a blunt instrument, not because the
   seasons agree. Anything that reads *individual months* rather than a pooled median —
   the generation-time hazard link, for instance — has no protection from this result.

### 11.7 What §11 licenses and what it does not

It licenses sealing the simple two-dial classifier as the grader, with O1 and D4 quotable
without a threshold caveat, and T1 shown to be insensitive to both dials.

It does **not** license the claim that the four seasons are firmly identified. The five
anchors are STABLE only against sampling intervals that OPEN-3 already showed are very
wide; measured against the exam's own ±1 quarter bands, three of the four D anchors leave
their band under a half-point move of the inflation line; and the richer classifier
disagrees about a third of recession months on a defect (industrial-production-only
recessions) that is real. **The week-2 fitting-stability check of §11.0 is the obligation
that carries this forward, and the soft-label escalation is the agreed response if the fit
proves threshold-unstable.**
