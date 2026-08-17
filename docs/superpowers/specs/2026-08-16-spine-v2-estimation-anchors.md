# Spine v2, stage 1 — the historical anchors, in plain language

**What this is.** Before the decade generator's economic engine is rebuilt, this
document measures the historical facts the rebuilt engine will be graded against.
Numbers first, model later. Nothing here is a pass/fail bar yet — these are the
measurements from which bars will be cut, and the last section says what each one
can and cannot carry.

**Every number below comes from one script.** Run it from the worktree root; it
needs no network, draws its only randomness from one fixed seed, and two
consecutive runs produce a byte-identical output file:

```
uv run python scripts/spine_v2_anchors.py
```

It writes `docs/superpowers/specs/spine-v2-anchors.json`. Every figure quoted in
this document is a field in that file, and every figure in that file states its
own derivation. If a number here and a number there ever disagree, the JSON is
what was measured and this document is wrong.

---

## 0. The words used here, in plain English

The project's own vocabulary is unavoidable — the anchors have to line up with
the code that will grade against them — but no term is used below without being
defined first.

- **The panel.** The single table of monthly US history the platform measures
  against: 813 months, April 1953 through December 2020, one row per month,
  sixteen columns (equity returns, commodity returns, the consumer price index,
  Treasury yields, the policy rate, credit spreads and so on). It is loaded by
  `ah.gen.bootstrap.campaign_source`, from the local data catalog; it is the same
  table the spine pilot measured against in both of its sealed rounds. Vintage
  `2026-08-10.1`.
- **Regime label.** Every month in the panel carries one of six labels, assigned
  by a fixed published rule (`regime_ruleset_v1`, `ah.data.derive.label_regime`).
  Two of them matter here:
  - **REC** ("recession") — either the NBER says the US was in recession that
    month, or industrial production was shrinking year on year.
  - **CRI** ("crisis") — the NBER says recession **and** the stock market was in
    a deep drawdown at the same time. CRI is the small, severe subset; a month is
    either REC or CRI, never both.
- **Onset.** The first month of a run. A "CRI onset" is a month labelled CRI whose
  previous month was not.
- **Trailing inflation.** The consumer price index this month divided by the same
  index twelve months earlier, minus one, in percent. Computed by
  `ah.gen.spine.panel_yoy`. It is undefined for the panel's first twelve months
  (there is nothing twelve months earlier), which is why several counts below
  start at 789 or 801 rather than 813.
- **The investment clock / quadrant.** Each month is put in one of four boxes by
  two yes/no questions — is the economy expanding (not REC and not CRI), and is
  inflation hot (trailing inflation above the panel's own median plus half a
  point, which works out to 3.35%)? The four boxes are named **recession**
  (contracting, cold), **stagflation** (contracting, hot), **recovery**
  (expanding, cold) and **expansion** (expanding, hot). Computed by
  `ah.gen.spine.panel_quadrant`; the threshold comes from
  `ah.gen.spine.fit_hazard`.
- **Dwell / spell.** An unbroken run of months in the same quadrant. Its length
  is the dwell.
- **Lift.** How much more likely something becomes once you condition on
  something else. Here: the chance a downturn begins within the next twelve
  months, measured over tight-policy months only, divided by the same chance
  measured over all months. A lift of 1.0 means the condition tells you nothing.
- **Block bootstrap.** A way of putting error bars on a statistic when the
  underlying data are not independent month to month. Explained where it is used
  (section B).

---

## 1. What the panel does not contain

Two gaps matter, and neither is worked around silently.

**The 2021–22 inflation surge is not in the panel.** The panel stops at December
2020. This is not an oversight: January 2021 onward is the platform's sealed
**holdout** split (`ah.splits.HOLDOUT`), the slice of history deliberately kept
back from every fitting decision — and already spent once, at WP5.6. The script
declares the 2021–22 episode in its episode list anyway and emits it with
`available: false`, `months_in_panel: 0`, and the reason, so it is visible as a
hole rather than absent from the list. **No 2021–22 number appears anywhere in
this document or in the JSON.** Anyone who wants one has to make a deliberate,
recorded decision to open the holdout; this script does not.

**There is no real-asset return series.** The catalog registers no monthly REIT
or real-asset total-return series. An intake schema exists
(`src/ah/data/schemas/nareit_returns.py`) but no such series has been ingested,
and the only real-asset history present (`jst.usa_housing_tr`, the
Jordà–Schularick–Taylor housing total return) is **annual**, not monthly. Every
real-asset field in the JSON is `null` with a stated reason, and the
"real assets minus bonds" spread the brief asks for is `null` throughout. Nothing
is substituted for it.

**A note on the bond series.** The panel has no bond total-return column — only
the 10-year Treasury **yield**. The platform's one sanctioned way to turn that
yield into a monthly return is the sealed `govt_tr_10y` derived series
(`pre-registration.yaml`): the previous month's yield earned for one month, minus
8.5 (the assumed duration) times this month's change in yield. The script imports
that transform rather than writing a new formula, so the bond numbers below are
the same bond numbers the rest of the platform uses. Its first month is a
placeholder zero by the sealed warm-up rule, and is excluded from every statistic
here.

---

## 2. Section A — the event chronology

The brief asks for two downturn definitions, both computed, because the spine-02
verdict-integrity review found the sealed round-two judge had compared one
definition on the model side with a different one on the history side.

### Definition 1 — crisis onsets only (the sealed round-one anchor)

A downturn event is a month whose label turns to **CRI**. This is exactly the
event `ah.gen.spine.fit_hazard` counts and exactly what
`scripts/spine_pilot_seal.py` sealed.

**Six events in 68 years**, covering **38 crisis months**:

| # | start | end | months |
|---|---|---|---|
| 1 | 1970-01 | 1970-01 | 1 |
| 2 | 1970-04 | 1970-10 | 7 |
| 3 | 1974-03 | 1975-03 | 13 |
| 4 | 2001-06 | 2001-11 | 6 |
| 5 | 2008-09 | 2009-06 | 10 |
| 6 | 2020-03 | 2020-03 | 1 |

Read against known history this is recognisable but lumpy. The 1970 downturn is
counted as **two** events because a single month (January 1970) qualified, the
next two did not, and the run resumed in April — one economic episode, two
"onsets". The 2020 entry is one month long not because the panel runs out — the
panel continues to December 2020 — but because only March 2020 met the
deep-drawdown test; April 2020 onward is labelled REC, the equity market having
recovered past the crisis threshold while the recession continued. 1980, 1981–82
and 1990–91 do not appear at all: they were recessions without a simultaneous
deep equity drawdown by this rule's threshold.

**Months at risk:** 762 (months with a defined quadrant that were not already in
a crisis, excluding the panel's final month, which has no following month to
observe). For the twelve-month-lookahead work in section B, the usable
population is **789 months** — those with a defined trailing inflation reading
and a full twelve months of future panel left to look into.

### Definition 2 — recession **or** crisis onsets (the union)

A downturn event is a month whose label turns to REC **or** CRI. This is what the
sealed round-two judge actually counted on the model side.

**Seventeen events**, covering **197 months**:

| # | start | end | months | | # | start | end | months |
|---|---|---|---|---|---|---|---|---|
| 1 | 1953-08 | 1954-11 | 16 | | 10 | 1990-08 | 1991-03 | 8 |
| 2 | 1956-07 | 1956-07 | 1 | | 11 | 1991-08 | 1991-10 | 3 |
| 3 | 1957-09 | 1958-10 | 14 | | 12 | 2001-02 | 2002-05 | 16 |
| 4 | 1960-05 | 1961-05 | 13 | | 13 | 2003-06 | 2003-06 | 1 |
| 5 | 1967-07 | 1967-07 | 1 | | 14 | 2008-01 | 2009-12 | 24 |
| 6 | 1970-01 | 1970-11 | 11 | | 15 | 2015-03 | 2017-02 | 24 |
| 7 | 1973-12 | 1975-03 | 16 | | 16 | 2019-04 | 2020-12 | 21 |
| 8 | 1980-02 | 1980-07 | 6 | | | | | |
| 9 | 1981-08 | 1983-04 | 21 | | | | | |

**Months at risk:** 612 on the same hazard-denominator rule; the same 789-month
population for section B.

This list is much closer to what an economist would call the US recession
chronology — 1953–54, 1957–58, 1960–61, 1970, 1973–75, 1980, 1981–83, 1990–91,
2001, 2008–09 are all there and dated correctly. But it also picks up things
nobody calls a recession, because the rule fires on shrinking industrial
production even without an NBER recession: **1985-07**, **2003-06**, **1967-07**
are one-month industrial blips, and **2015-03 to 2017-02** is the two-year
manufacturing/energy slowdown. The final entry, **2019-04 to 2020-12**, merges
the 2019 industrial slowdown straight into the pandemic and runs to the panel's
edge, so its length is a censoring artefact, not a fact.

**Which definition to use.** Neither is "right". The CRI-only definition names
severe events an allocator would actually feel, but there are only six of them in
seven decades, which is not enough to estimate anything precisely (section B
shows exactly how imprecise). The REC+CRI definition has seventeen events and
supports a usable estimate, at the cost of counting some months no allocator
would call a downturn. The recommendation in section 6 is to set bars on REC+CRI
and to report CRI-only as a disclosure.

---

## 3. Section B — the transmission lift

**The question.** If policy is tight this month, how much more likely is it that a
downturn begins within the next twelve months, compared with an average month?

**What "tight policy" means here.** A month where the 10-year Treasury yield sits
**below** the 2-year yield — an inverted yield curve. This is not a fresh choice:
it is exactly the panel-side conditioning the spine pilot sealed in round one
(`scripts/spine_pilot_seal._b6_onset_rates`) and the one the round-two matched
comparison used. **149 of the 789 usable months (18.9%) are tight by this
definition.** Section 3.3 measures how much the answer moves if a different
indicator of tightness is used instead — and it moves a lot.

**How each rate is computed.** For each of the 789 usable months, ask "did a
downturn begin in any of the next twelve months?" — a yes/no. The
*unconditional* rate is the share of all 789 months answering yes. The
*conditional* rate is the share of the 149 tight months answering yes. The lift
is the second divided by the first.

### 3.1 The point estimates

| downturn definition | tight months answering yes | conditional rate | all months answering yes | unconditional rate | **lift** |
|---|---|---|---|---|---|
| crisis only (CRI) | 33 / 149 | 0.2215 | 61 / 789 | 0.0773 | **2.86×** |
| recession or crisis (REC+CRI) | 86 / 149 | 0.5772 | 192 / 789 | 0.2433 | **2.37×** |

Both conditional/unconditional pairs reproduce the sealed anchors exactly
(`spine02-prereg.json` carries 0.2214765100671141 and 0.07731305449936629), which
is the cross-check that the definitions used here are the definitions the pilot
used. The **2.37×** figure is the same number the spine-02 review quoted as
history's transmission strength when it re-matched the outcome definitions; the
model's own matched figure was **1.14×**.

### 3.2 The error bars, and why they are computed this way

A naive error bar would treat the 789 months as 789 independent observations.
They are not: downturns arrive in clumps, and so do inverted-curve months, so
consecutive rows carry much of the same information. Treating them as independent
would make the interval far too narrow and would produce a pass band the rebuilt
engine could fail for no good reason.

The interval below is a **stationary block bootstrap** (Politis–Romano). In
plain terms: build a fake 789-month history by pasting together randomly chosen
runs of *consecutive* real months — run lengths drawn at random with a stated
average, wrapping around the end of the panel — recompute the lift on the fake
history, and repeat 2,000 times. Because whole runs travel together, the clumping
survives into the fake histories and the resulting spread is honest. The
reported interval is the 2.5th to 97.5th percentile of those 2,000 values. The
average run length is the one thing that must be chosen; **24 months is the
primary choice** (a downturn plus its lead-in is roughly this long), with 12 and
36 months reported as sensitivity. All randomness comes from a single
`numpy.random.Generator(PCG64(20260816))` used in a fixed order.

| downturn definition | avg. run length | lift | **95% interval** |
|---|---|---|---|
| crisis only | 12 months | 2.86× | **[1.04, 5.23]** |
| crisis only | **24 months (primary)** | 2.86× | **[0.71, 5.05]** |
| crisis only | 36 months | 2.86× | **[0.59, 5.13]** |
| recession or crisis | 12 months | 2.37× | **[1.77, 3.34]** |
| recession or crisis | **24 months (primary)** | 2.37× | **[1.78, 3.35]** |
| recession or crisis | 36 months | 2.37× | **[1.86, 3.34]** |

Two things to read off this table.

1. **The crisis-only interval contains 1.0.** At the primary run length the
   interval runs from 0.71 to 5.05 — that is, this panel cannot rule out that an
   inverted curve tells you nothing at all about crises, and cannot rule out that
   it quintuples the odds. That is what six events buys. A pass/fail bar built on
   the crisis-only lift would be nearly unfailable and therefore nearly
   worthless.
2. **The recession-or-crisis interval is stable and excludes 1.0.** [1.78, 3.35]
   at 24 months, and barely moving at 12 or 36 — the choice of run length is not
   driving it. This is the number that can carry a bar.

### 3.3 How much does "tight policy" being defined differently change the answer?

Three indicators of tight policy, each evaluated twice: at its own natural
cut-off, and at a cut-off tuned so it calls the **same share of months tight**
(18.9%) as the primary definition does. The second comparison is the fair one: a
lift is mechanically diluted by labelling more months tight, so an indicator that
fires 70% of the time will always look weaker regardless of its merit.

| indicator of "tight" | cut-off | months called tight | lift, crisis only | lift, recession or crisis |
|---|---|---|---|---|
| inverted yield curve (10y below 2y) — **primary** | natural | 149 / 789 (18.9%) | 2.86× | **2.37×** |
| inverted yield curve | matched share | 149 / 789 (18.9%) | 2.86× | 2.37× |
| policy rate above its own 36-month average | natural | 402 / 765 (52.6%) | 1.44× | 1.38× |
| policy rate above its own 36-month average | matched share | 145 / 765 (19.0%) | 2.25× | **1.82×** |
| policy rate above trailing inflation (positive real rate) | natural | 548 / 789 (69.5%) | 1.18× | 1.10× |
| policy rate above trailing inflation (positive real rate) | matched share | 149 / 789 (18.9%) | 1.13× | **1.24×** |

(The inverted-curve row is identical under both cut-offs — the natural cut and the
matched-share cut select the same 149 months. That coincidence is a useful check
that the matching machinery is doing what it claims.)

**This is the largest single open question in the whole measurement.** At a
matched share, the recession-or-crisis lift is **2.37×** if tightness means an
inverted curve, **1.82×** if it means the policy rate above its recent norm, and
**1.24×** if it means a positive real policy rate. The gap between 2.37 and 1.24
is far wider than the [1.78, 3.35] sampling interval — so the choice of indicator
matters more than the sampling noise the interval describes. It is raised as an
open question in section 7 rather than settled here.

---

## 4. Section C — how long regimes last

Every month is in one of the four investment-clock boxes; a **spell** is an
unbroken run in one box; the numbers below are the lengths of those runs.

**Censoring is separated out.** A spell that is still running when the panel ends,
or that was already running when the panel's usable record begins, has an
unknown true length — we only see part of it. Including such a spell in a median
biases the median down. All the headline figures below use **completed** spells
only, and the censored ones are listed separately. In this panel there are
exactly two censored spells, both in the recession box: 1954-04 to 1954-11 (the
first quadrant spell after the twelve months where trailing inflation is not yet
defined) and 2019-04 to 2020-12 (still running at the panel's end).

Lengths are given in **quarters**, as the brief asks, and in **months**, because
months are the unit the platform's own sealed anchor is stated in. Quarters =
months ÷ 3.

| quadrant | completed spells | median | interquartile range | censored spells |
|---|---|---|---|---|
| recession (contracting, cold) | **12** | **1.00 q** (3 months) | 0.33 – 4.08 q (1 – 12.25 months) | 2 |
| stagflation (contracting, hot) | **12** | **1.33 q** (4 months) | 0.33 – 3.42 q (1 – 10.25 months) | 0 |
| recovery (expanding, cold) | **22** | **3.00 q** (9 months) | 1.42 – 5.83 q (4.25 – 17.5 months) | 0 |
| expansion (expanding, hot) | **21** | **2.00 q** (6 months) | 1.00 – 4.33 q (3 – 13 months) | 0 |

The full sorted spell lists are in the JSON
(`c_regime_durations.per_quadrant.<quadrant>.sorted_spells_months` and
`…_quarters`). They are worth a glance because the distributions are extremely
skewed: recovery's twenty-two spells run 2, 2, 3, 3, 3, 4, 5, 5, 5, 6, 6, 12, 13,
14, 16, 16, 18, 19, 25, 39, 62, **100** months. A single hundred-month recovery
sits next to a cluster of two- and three-month ones. The median is a fair summary
of the middle; it says nothing about that tail.

### A correction the brief needs

The spine pilot's sealed anchor `panel_dwell_medians = [5, 4, 9, 6]` is in
**months, not quarters** — the stage-1 brief describes it as quarters. In
quarters those same figures are [1.67, 1.33, 3.00, 2.00]. The script reproduces
the sealed `[5, 4, 9, 6]` exactly (it is in the JSON as
`pilot_b4_panel_dwell_medians_months`, and each quadrant's
`all_spells_including_censored.median_months` matches it), so the unit is not in
doubt.

The pilot's anchor also **includes censored spells**. That is the whole
difference between its [5, 4, 9, 6] and the completed-only [3, 4, 9, 6] above:
recession is the only quadrant with censored spells, and including its truncated
21-month tail-end run pulls its median from 3 up to 5. Stagflation, recovery and
expansion are unchanged either way.

### Sparsity — quantified, because the brief asks

The pilot's own sealed power disclosure warned that its stagflation median rested
on 12 spells. That is confirmed and it is not the only thin cell:

- **recession: 12 completed spells. stagflation: 12 completed spells.** With
  twelve observations, the median is essentially the average of the sixth and
  seventh values in a sorted list of twelve — moving one spell by a month can
  move the median by a month. Both these quadrants' medians are 3 and 4 months
  respectively, so a one-month wobble is a 25–33% swing in the ratio a bar would
  test.
- **recovery: 22 spells. expansion: 21 spells.** Better, but still small, and
  both distributions have long tails that make the mean useless and the median
  only moderately stable.
- The interquartile ranges show the same thing from the other side: recession's
  middle half of spells runs from 1 month to 12.25 months. A distribution that
  wide, observed twelve times, does not support a tight bar.

---

## 5. Section D — what happened to portfolios, by inflation state and by episode

### 5.1 The split

Months are split into **high inflation** and **low inflation** by trailing
12-month CPI inflation. **4% is the primary line** — a conventional threshold,
not one estimated from anything here — with **3%** and **5%** reported as
sensitivity so the reader can see how much rests on the conventional choice. Only
months with a defined trailing inflation reading are used (801 of 813; the first
twelve months have no reading).

Returns are annualised two ways, and both are in the JSON: **arithmetic** (twelve
times the average monthly return) and **geometric** (compounding that average
monthly return for twelve months). Spreads below use the arithmetic figure,
because only the arithmetic one is additive across assets — a difference of two
arithmetic annualised means is itself a valid annualised difference, which is not
true of geometric means.

**At the primary 4% line** — 225 high-inflation months, 576 low-inflation months:

| | high inflation (≥4%) | low inflation (<4%) | difference |
|---|---|---|---|
| equities (Fama-French market total return) | **+5.53%/yr** | **+14.17%/yr** | −8.64 pp |
| government bonds (sealed `govt_tr_10y`) | **+7.20%/yr** | **+5.42%/yr** | +1.78 pp |
| commodities (AQR equal-weight, total return) | **+12.07%/yr** | **+6.80%/yr** | +5.27 pp |
| real assets | *not available* | *not available* | — |
| **commodities minus bonds** | **+4.87 pp** | **+1.38 pp** | +3.49 pp |
| **real assets minus bonds** | *not available* | *not available* | — |

The headline shape is the familiar one: in high-inflation months equities earn
about a third of what they earn otherwise, and commodities earn nearly double.
Bonds' behaviour is the surprise — they did *better* in high-inflation months
than low ones, at 7.20% versus 5.42%. That is not an error and not a
counterexample to duration risk: the ≥4% bucket is dominated by 1977–1982 and by
the descent out of it, when yields were extremely high, so the carry term
(earning a 12% yield for a month) frequently outran the price term. The
period-average masks enormous month-to-month variation: bond volatility in the
high-inflation bucket is 11.2% a year versus 6.2% in the low bucket.

**Sensitivity — and one sign flip that matters:**

| threshold | high months | commodities−bonds, high | commodities−bonds, low |
|---|---|---|---|
| 3% | 368 | **+2.05 pp** | **+2.63 pp** |
| **4% (primary)** | 225 | **+4.87 pp** | **+1.38 pp** |
| 5% | 153 | **+8.62 pp** | **+0.88 pp** |

At 4% and 5% the commodities-over-bonds spread is much larger in high inflation
than low, and grows as the line is raised. **At 3% the ordering reverses** — the
spread is *smaller* in the high bucket than the low one. The reason is that a 3%
line drags most of the 1983–1999 disinflation into the "high" bucket, and that
was the single best stretch in the record for long bonds (+10.05%/yr). Anyone
setting a bar on this spread must state the threshold as part of the bar; the
fact is not robust to the threshold, it is conditional on it.

### 5.2 The named episodes

Each episode is a fixed calendar window; the figures are that window's own
annualised arithmetic means, computed exactly as above.

| episode | months used | avg. trailing inflation | equities | bonds | commodities | **commodities − bonds** | stock/bond correlation |
|---|---|---|---|---|---|---|---|
| post-war calm 1953-04…1965-12 | 141 | 1.38% | +14.49% | +2.06% | +4.71% | **+2.65 pp** | −0.10 |
| **first oil shock 1973-01…1975-12** | 36 | 8.80% | **−5.03%** | +2.77% | **+35.09%** | **+32.32 pp** | +0.24 |
| **great inflation 1977-01…1982-12** | 72 | 9.24% | +13.13% | +5.36% | +10.04% | **+4.68 pp** | +0.34 |
| great disinflation 1983-01…1999-12 | 204 | 3.27% | +17.50% | +10.05% | +7.23% | **−2.82 pp** | +0.24 |
| post-GFC calm 2010-01…2019-12 | 120 | 1.77% | +13.65% | +3.89% | −1.16% | **−5.05 pp** | −0.35 |
| **2021-22 inflation surge** | **0 of 24** | — | — | — | — | — | — |

**The 2021–22 row is empty on purpose** — see section 1. It is the one episode a
present-day allocator would most want, and this panel cannot supply it.

The range across episodes is the important output of this table. The
commodities-over-bonds spread runs from **−5.05 pp** (post-GFC calm) to **+32.32
pp** (the 1973–75 oil shock) — a spread of 37 percentage points between two real
decades of US history, both of which actually happened. Even restricting to the
two high-inflation episodes that *are* in the panel, the same statistic is +32.32
pp in one and +4.68 pp in the other. That is the honest width any sealed band on
this quantity has to respect, and section 6 says why.

Two individual figures worth flagging so they are not mis-read:

- **Equities earned +13.13%/yr through 1977–1982.** This looks wrong against the
  reputation of the period, and it is not: it is a *nominal* arithmetic
  annualised mean over 72 months that includes the 1980 and 1982 rallies, against
  average inflation of 9.24% — a real return near zero. Every return in this
  document is nominal.
- **Commodities earned +35.09%/yr through 1973–1975** on an arithmetic basis and
  +41.32% geometric, against 30.4% annualised volatility over just 36 months.
  One episode, three years, one commodity shock. It is a real historical fact and
  a terrible basis for a narrow bar.

### 5.3 Stock–bond correlation

The correlation between the equity monthly return and the bond monthly return —
positive means they fall together, which is what removes the diversification an
allocator is counting on.

**Computed over all months in each state** (same 4% primary line and 3%/5%
sensitivity):

| threshold | high-inflation months | correlation, high | low-inflation months | correlation, low |
|---|---|---|---|---|
| 3% | 368 | **+0.27** | 433 | **−0.10** |
| **4% (primary)** | 225 | **+0.30** | 576 | **−0.02** |
| 5% | 153 | **+0.34** | 648 | **+0.01** |

The sign difference is robust to all three thresholds: high-inflation months carry
a clearly positive stock–bond correlation, low-inflation months carry one at or
just below zero. The magnitude of the high-inflation figure creeps up as the line
is raised (+0.27 → +0.34), so the threshold changes the level by roughly 0.07 but
not the conclusion.

**Rolling 36-month correlation.** The same correlation computed inside every
36-month window, then each window assigned to the inflation state of its **final
month** — the month the correlation is "as of". 766 windows are defined, the first
ending 1957-03.

| threshold | windows in high inflation | share positive | mean | windows in low inflation | share positive | mean |
|---|---|---|---|---|---|---|
| 3% | 367 | **85.8%** | +0.27 | 399 | **47.9%** | −0.03 |
| **4% (primary)** | 225 | **94.7%** | +0.30 | 541 | **54.2%** | +0.03 |
| 5% | 153 | **98.0%** | +0.32 | 613 | **58.1%** | +0.06 |

At the primary line, **95% of three-year windows ending in a high-inflation month
show a positive stock–bond correlation**, against **54%** of windows ending in a
low-inflation month — a coin flip. This is the single sharpest fact in the whole
measurement: it is nearly categorical, it holds at every threshold tested, and it
is exactly the behaviour a diversified portfolio is most exposed to.

---

## 6. What each anchor can carry as a pass/fail bar, and why the tolerance is that wide

The brief asks that anywhere a number will become a bar, the size of the
tolerance be explained. This section does that. **None of these are bars yet** —
they are recommendations to whoever seals them.

**B — transmission lift. Recommended bar: the recession-or-crisis lift must land
inside [1.78, 3.35]. Do not set a bar on the crisis-only lift.**
The width is the 95% block-bootstrap interval at the primary 24-month run length,
and it is that wide for one reason: seventeen events in 68 years. The interval is
not a modelling choice that could be tightened by better estimation — it is what
seventeen clustered events support. Two supporting facts make it defensible as a
band rather than arbitrary: it barely moves when the bootstrap's run length is
changed to 12 or 36 months ([1.77, 3.34] and [1.86, 3.34]), so it is not an
artefact of that choice; and it excludes 1.0 comfortably, so a model with no
transmission at all fails it. **The crisis-only interval [0.71, 5.05] must not
become a bar**: it contains 1.0, so a model with no policy-to-downturn channel
whatsoever would pass it, which is the definition of a worthless test. Report the
crisis-only figure as a disclosure and bar on the union.
*Caveat that must ride with this bar:* it is measured with tightness meaning an
inverted yield curve. Section 3.3 shows the same statistic reads 1.82× or 1.24×
under other reasonable meanings of tight — see section 7.

**C — regime durations. Recommended bar: a ratio band on the median dwell, and it
must be at least as wide as the pilot's existing [0.6, 1.4], not narrower.**
The pilot's own sealed disclosure already warned that its tolerances sat near the
anchors' sampling noise. This measurement quantifies why: recession and
stagflation medians each rest on **twelve** completed spells, with interquartile
ranges (1 to 12.25 months, and 1 to 10.25 months) wider than the medians
themselves (3 and 4 months). With twelve observations of a distribution that
skewed, the median's own sampling wobble is on the order of one month — which on
a 3-month median is a third of the value, i.e. comparable to the entire [0.6,
1.4] band. Any bar narrower than the existing one is measuring noise.
Two further conditions on this bar: (i) it must state whether it uses
**completed** or **all** spells, because for recession those give 3 and 5 months
and the ratio moves 40% depending on the answer; (ii) recovery and expansion
(22 and 21 spells) can carry a somewhat tighter bar than recession and
stagflation (12 each), and treating all four cells identically over-weights the
two thin ones.

**D(i) — the commodities-over-bonds spread. Recommended bar: a wide band, stated
together with its inflation threshold, and no tighter than the episode range.**
At the primary 4% line the historical figure is +4.87 pp in high inflation versus
+1.38 pp in low. But across real episodes the same statistic ran from −5.05 pp to
+32.32 pp, and *within* the high-inflation episodes alone from +4.68 pp to +32.32
pp. A band narrower than roughly [0, +15] pp would be rejecting behaviour that
actually happened in US history — the 1973–75 window alone would breach almost
any tight band, from above. The threshold must be part of the bar's statement,
because at a 3% line the sign of the high-versus-low difference reverses (section
5.1). The defensible bar is directional and loose: *the spread must be larger in
high inflation than in low inflation at the 4% line*, with the magnitude reported
rather than bounded tightly.

**D(ii) — the stock–bond correlation. Recommended bar: the tightest of the four,
because the fact is the sharpest.**
Two anchors, both robust across the 3/4/5% thresholds: (a) the correlation over
high-inflation months is positive and roughly **+0.30**, against roughly **0.00**
over low-inflation months, with the sign difference holding at every threshold;
(b) **94.7%** of 36-month windows ending in a high-inflation month show a positive
correlation, against **54.2%** of low-inflation windows. Anchor (b) is close to
categorical and moves only from 85.8% to 98.0% across the whole threshold range,
so a bar such as *"at least 80% of three-year windows in high inflation must show
positive stock–bond correlation, and no more than 65% in low inflation"* is
defensible on this evidence. The level anchor (a) should carry a tolerance of
around ±0.10 on the high-inflation figure — the threshold sensitivity alone moves
it 0.07, so anything tighter would be testing the threshold choice rather than
the model.

**A — the chronology itself is not a bar.** Six crisis events and seventeen
recession-or-crisis events are the raw material behind everything above; the
chronology's job is to let a reader check the definitions against known history,
which section 2 does.

---

## 7. Open questions for the owner

**Q1 — which meaning of "tight policy" should the rebuilt engine be graded on?**
This is a real fork, not a detail. At a matched base rate the recession-or-crisis
lift is **2.37×** if tight means an inverted yield curve, **1.82×** if it means
the policy rate above its own 36-month average, and **1.24×** if it means a
positive real policy rate. Those differences are wider than the [1.78, 3.35]
sampling interval, so whichever is chosen effectively sets the bar. The case for
each: the **inverted curve** is what the pilot sealed and what the 2.37×-versus-
1.14× finding in the spine-02 review was computed on, so it preserves continuity
with the existing record — but a yield curve is a market price, not a policy
setting, and the rebuilt engine will have an explicit policy rate and an explicit
neutral rate to compare it against. The model side of the sealed round-two
comparison already conditioned on a **policy gap** (the policy rate minus the
model's own neutral rate), which is conceptually much closer to the second and
third rows of that table than to the first. There is therefore a live risk that
the celebrated 2.37×-vs-1.14× gap is partly a comparison of a yield curve against
a policy gap. **This measurement does not resolve it**; the primary number is
reported on the sealed precedent (inverted curve) and every alternative is in the
JSON. An owner ruling is needed before any bar is sealed on B.

**Q2 — should the 2021–22 episode be measured at all?** It is the episode the
brief names first among high-inflation episodes and the one a present-day
allocator cares most about, and it is entirely inside the spent holdout. Opening
it to set a bar means fitting a bar to data that was supposed to be held back —
precisely the hazard CLAUDE.md flags now that the holdout is spent. This script
did not open it. If the owner wants those numbers, that should be a recorded,
deliberate decision with its consequence stated, not a side effect of an
anchor-measuring script.

**Q3 — completed spells or all spells for the dwell bar?** The pilot's sealed
anchor uses all spells including censored ones and reads [5, 4, 9, 6] months;
completed-only reads [3, 4, 9, 6]. Only the recession cell differs, and it differs
by 40%. Continuity with the pilot argues for keeping all spells; correctness
argues for completed only. Both are in the JSON; the bar must name which.

**Q4 — the brief's unit slip.** The stage-1 brief describes the pilot's dwell
medians `[5, 4, 9, 6]` as quarters. They are **months** (`[1.67, 1.33, 3.00,
2.00]` quarters). Flagged so no bar is written in the wrong unit.

---

## 8. Provenance

- **Script:** `scripts/spine_v2_anchors.py` — deterministic, offline, one seed
  (`20260816`), verified byte-identical across consecutive runs.
- **Output:** `docs/superpowers/specs/spine-v2-anchors.json`.
- **Panel:** vintage `2026-08-10.1`, ruleset `regime_ruleset_v1`, 813 months
  1953-04 … 2020-12, campaign train+validation only.
- **Definitions imported, not reimplemented:** `ah.gen.spine.panel_yoy`,
  `ah.gen.spine.panel_quadrant`, `ah.gen.spine.fit_hazard`,
  `ah.gen.regimes.semimarkov.spells_from_labels`,
  `ah.strategies.load_derived_series` + `ah.eval.metrics.tails.
  derived_series_values` (the sealed `govt_tr_10y` transform).
- **Nothing under `schemas/`, `src/ah/eval/`, `src/ah/gen/`, `src/ah/battery/`,
  or any `*.lock` file was modified.** This work package is measurement only.
