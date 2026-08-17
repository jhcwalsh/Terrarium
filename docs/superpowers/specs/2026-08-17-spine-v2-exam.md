# The spine v2, stage 1 exam — what the rebuilt engine has to prove

**Date:** 2026-08-17 · **Status:** DRAFT for owner review · **Branch:** `spine2-01-exam`
**Authority:** `governance/decision-register.md` D-SP-6 (2026-08-16, "go on the engine work,
include the allocation tests") plus the owner rulings of 2026-08-17 recorded in §9.
**Measurements this document cuts bars from:** `docs/superpowers/specs/spine-v2-anchors.json`
and its plain-language companion `docs/superpowers/specs/2026-08-16-spine-v2-estimation-anchors.md`.
**Prior rounds carried forward:** `docs/superpowers/specs/spine02-prereg.json` (byte-frozen
thresholds) and `docs/superpowers/specs/2026-08-16-spine02-results.md` (the verdicts).

Nothing in this document has been fitted to. No engine work has started. That is the point:
these bars are written down, with their justifications, **before** any result exists.

---

## Before sealing — the OPEN items

Four things this exam needs that the anchors file does not yet carry. Each is a
measurement to add to `scripts/spine_v2_anchors.py` (or, for OPEN-4, a power calculation
to run) **before** the seal. Nothing below has been computed here; where a bar depends on
one, the bar says so in its own subsection.

| # | What is missing | What must be added | Which bar depends on it |
|---|---|---|---|
| **OPEN-1** | `spine-v2-anchors.json` contains no clockwise-fraction measurement. The 0.6029411764705882 anchor and its "68 transitions, standard error ≈ 0.059" disclosure come from round one's seal (`spine-pilot-prereg.json`), measured on an earlier run of the pipeline. | Recompute the clockwise fraction and its transition count on the same panel vintage (`2026-08-10.1`) as every other number in this exam, and confirm it reproduces the sealed value exactly. | **O1** (the seasons turn the right way round) |
| **OPEN-2** | No sampling interval on the stock–bond correlation gap. The anchors give the correlation levels and the share-of-windows figures at the 3%, 4% and 5% inflation lines, but no error bar on the *difference* between the high- and low-inflation figures. | A block bootstrap (the same Politis–Romano machinery and seed discipline already used for the transmission interval) for (i) the high-minus-low correlation difference and (ii) the difference in share-of-windows-positive, both at the 4% line. | **A2** (stocks and bonds fall together when inflation is high) — its 0.15 margin currently rests on published threshold sensitivity plus a halving rule, not on a measured interval |
| **OPEN-3** | No sampling interval on the per-season dwell medians. The anchors give every season's full sorted spell list and its interquartile range, but no bootstrap interval for the median itself. | A bootstrap over spells (resample the completed spells of each season) giving a 95% interval for each season's median. | **D1–D4** (how long each season lasts) — needed to confirm the ±1 quarter tolerance is *at least* as wide as the anchors' own wobble, which is currently argued from the interquartile ranges rather than measured |
| **OPEN-4** | No power calculation for the generated side. We know the panel's transmission lift rests on 789 eligible months; we have not established how many generated decades are needed for the generated-side lift's own sampling error to be small relative to the [1.78, 3.35] pass band. | A short calculation (or simulation) fixing `n_seeds` and `n_paths` so that the generated side's own error bar is a small fraction of each bar's band width, for **T1** and for **A1/A2** (which need enough high-inflation months per world). | **T1**, **A1**, **A2** — this determines the ensemble size the exam is run at |

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

> **≥ 0.6029411764705882** (0.6029) — one-sided.

**(b) The historical anchor.** 0.6029411764705882 is history's own clockwise fraction, sealed
in round one as `b4.panel_clockwise_fraction` in
`docs/superpowers/specs/spine-pilot-prereg.json`. It rests on **68 season transitions**, and
the sealed power disclosure that travels with it states a standard error of **≈ 0.059**.
See **OPEN-1**: this figure is not yet reproduced in the v2 anchors file.

**(c) Why the tolerance is what it is — and it is the strictest choice on the page.** Round
one's bar was two-sided, ±0.15 around the anchor, which put its lower edge at 0.4529. Round
two's engine measured clockwise fractions of 0.4574, 0.4820, 0.4831, 0.4886 and 0.5176 — a
clock barely better than a coin flip — and **passed on all five seeds**. A bar that a coin
flip passes is not measuring the thing it claims to measure. The owner's ruling makes it
one-sided at the anchor itself: the engine must be *at least as* clockwise as history, with
no allowance below. The honest consequence, stated now rather than after results: the anchor
is itself an estimate with a standard error of about 0.059, so an engine whose true ordering
exactly matched history's true ordering could still land a little below 0.6029 and fail. That
strictness is deliberate — it is the price of not repeating round two's false pass — but if
the owner wants the bar to absorb the anchor's own sampling error (e.g. ≥ 0.6029 − 0.059 =
0.5439), **now, before any result exists, is the only time that can be decided without it
being goalpost-moving.**

**(d) What a FAIL means in product terms.** A fail means the seasons arrive in a shuffled
order, so nothing a player learns in one world about what usually follows what transfers to
the next — the game becomes a slot machine with economic vocabulary.

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
can act on, and a looser one would let a season be off by a decision cycle. See **OPEN-3**:
this tolerance should also be confirmed to be at least as wide as the medians' own sampling
wobble, which the anchors' interquartile ranges strongly suggest but do not yet measure.

*A floor note that applies to D1 and D2.* No spell can be shorter than one month (0.33
quarters), so where the ±1 quarter band's lower edge falls at or below that floor, the bar
binds only from above. This is stated per bar rather than hidden.

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
  **0.15**.
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

**(c) Where the 0.15 margin and the 80%/65% edges come from.** Both are derived from the
published threshold sensitivity, which is the one uncertainty the anchors do quantify for
this statistic:

| inflation line | correlation, high | correlation, low | gap | windows positive, high | windows positive, low |
|---|---|---|---|---|---|
| 3% | +0.26776000715530485 | −0.09682697926086808 | 0.3646 | 85.8% | 47.9% |
| **4% (the bar)** | +0.30125403304704923 | −0.01823351575688256 | **0.3195** | **94.7%** | **54.2%** |
| 5% | +0.3390382145390731 | +0.010927392717242666 | 0.3281 | 98.0% | 58.1% |

- **The 0.15 margin** is a little under **half** the smallest gap history shows at any
  published line (0.3195, at the 4% line itself). Halving leaves room for the generated
  side's own sampling noise while still failing an engine that gets the sign right but the
  magnitude weakly — which is precisely the failure mode the spine-02 review found for
  transmission ("present but weak", 1.14× against history's 2.37×). It is also a bit over
  **twice** the threshold sensitivity of the high-inflation level itself, which moves only
  0.07 across the whole 3%→5% range, so the bar cannot be passed or failed by the choice of
  line.
- **The 80% floor** sits 5.8 points below the *lowest* share history shows at any line
  (85.8%, at 3%); **the 65% ceiling** sits 6.9 points above the *highest* low-inflation share
  (58.1%, at 5%). Both edges therefore clear the entire published threshold range by 6–7
  points, so neither is an artefact of the 4% choice.

**See OPEN-2.** These margins rest on threshold sensitivity plus a halving rule, not on a
measured sampling interval. A block bootstrap of the high-minus-low difference should be
added before the seal; if it comes back wider than expected, the honest response is to widen
the margin **now**, before results, and record why.

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
   nothing; amendments made after the seal go through the machine-checked log.
2. **The OPEN items are closed** (the table at the top): the clockwise anchor is recomputed on
   the current vintage, bootstrap intervals are added for the correlation gap and the dwell
   medians, and the ensemble size is fixed by the power calculation. If any measurement comes
   back wider than assumed, the affected tolerance is widened **here, before results**, with
   the reason recorded.
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

---

## 9. The bars at a glance

| tier | code | plain name | the bar | historical anchor |
|---|---|---|---|---|
| causal | **T1** | does tightening cause downturns | lift inside **[1.78, 3.35]** | 2.37× (86/149 vs 192/789) |
| causal | **O1** | the seasons turn the right way round | clockwise fraction **≥ 0.6029** | 0.6029 (68 transitions, SE ≈ 0.059) |
| persistence | **D1** | how long a recession lasts | median **[0, 6] months** (binds from above) | 1.00 q / 3 months, 12 completed spells |
| persistence | **D2** | how long stagflation lasts | median **[1, 7] months** | 1.33 q / 4 months, 12 completed spells |
| persistence | **D3** | how long a recovery lasts | median **[6, 12] months** | 3.00 q / 9 months, 22 completed spells |
| persistence | **D4** | how long an expansion lasts | median **[3, 9] months** | 2.00 q / 6 months, 21 completed spells |
| allocation | **A1** | does the inflation hedge pay | spread(high) > spread(low) at 4%; inside [−5.05, +32.32] pp | +4.87 pp vs +1.38 pp |
| allocation | **A2** | stocks and bonds fall together | corr(high) > 0 and exceeds corr(low) by ≥ 0.15; ≥ 80% / ≤ 65% of 3-year windows positive | +0.30 vs −0.02; 94.7% vs 54.2% |
| no-regression | **R1** | severity still bites the book | b3 byte-frozen: monotone coverage, ≥ 1/20 breach at 55% | prior seal (round two: PASS) |
| no-regression | **R2** | eras don't teleport at the seams | b2 byte-frozen: join jump ≤ 2.5 pp, p95 ≤ 0.9292 pp | panel p95 0.7434 pp (round two: FAIL) |

**Ten bars: 2 causal, 4 persistence, 2 allocation, 2 no-regression.**

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
