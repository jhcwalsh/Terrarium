# D-SP-10 — the conditioning-reach fix, and the sealed 12-bar exam re-run on it

**Date:** 2026-08-18 · **Branch:** `stage2-03-reach` · **Status: measured, no owner
ruling taken.** Charter: `governance/decision-register.md` **D-SP-10** (2026-08-18) —
*"extend conditioning to reach every month … then re-run the FULL sealed 12-bar exam
unchanged — the exam does not move, the engine does."*

**What this document is.** The record of one engine change and the whole exam read on it.
Every number below is produced by `scripts/stage2_reach.py` and lives in
`docs/superpowers/specs/stage2-reach-results.json` (byte-identical on a re-run,
`sha256 bb78ff37…`). Every PASS/FAIL word is the sealed judge's own. Nothing was
tuned to a bar, no threshold was touched, no file inside either pre-registration was
edited, and no line of `src/` or `schemas/` was changed.

---

## The one-paragraph answer

The compiler used to consult the world's story only where a block opened — 494 of 6,000
months, 8.2% — and every other month was the panel's next row, taken for no reason but
contiguity. The fix makes it consult the story at **every** month: an entry is now chosen
for how far real history's own quadrant path tracks the spine's coming months, a block is
**ended** the moment its next month would land in the wrong quadrant, and when the era
filter leaves that break unjoinable the compiler moves to a month from which history
*walks into* the right quadrant instead. **Conditioning reach goes from 47.9% to 77.6% of
months, and the world's story and the world's markets now agree on 77.8% of judged months
against 60.5% expected of two independent dials — an excess over chance of 17.3 points
where it used to be 1.4.** The residual 22.4% is not slack: **every** unreached month is a
divergence the join filters refused, and 81% of those are refused by the era filter alone,
which is the constraint the ruling preserved — the era bucket and the quadrant's hot bit
are literally the same predicate, so an era-safe join *cannot* cross the inflation line.
On the scoreboard **eight of twelve pass after the fix (nine passed before) and the
failures are not the same failures** [CORRECTED — the integrity review caught the
original "nine still pass" here contradicting this document's own §4 table: `A1`
flips PASS→FAIL and nothing flips up to compensate]: the eight spine bars are bit-unchanged (a compiler change cannot
move them, and that is checked to 1e-12, not assumed); `A2` goes from failing all three
conditions to failing **one** (the window share), with its correlation now positive on
6 seeds of 6 where it was −0.018 before; `R2`'s join half is **cured** — the single
unfiltered forced re-entry that was the entire failure is gone, max jump 4.13 pp → 2.4997
pp inside the 2.5 bound, forced re-entries 1 → 0 — and its **p95 half now fails instead**,
because reach is bought with joins and a join may legally move inflation by 2.5 pp;
`A1` flips PASS → FAIL, and the six-seed disclosure says that flip is inside its own noise
(before: 2 of 6 seeds positive, mean −2.27; after: 4 of 6 positive, mean −0.97 — the
sealed seed is the fix's worst draw and was the pre-fix engine's best). `R1` passes both
sealed conditions with harder worlds (breach 4/20 → 8/20), and its *disclosed* third check
now fails. **The fix does what it was funded to do; two bars move against each other and
the frontier is mapped rather than tuned past.**

---

## 1. The defect, and the structural fact that decides the fix

### 1.1 What was broken

`ah.gen.spine.SpineBootstrap._draw` asks the spine which quadrant the world is in, and
then uses the answer **only to open a block**: the decade's first month, a join, a forced
re-entry. Every other month is `previous + 1`. Week C measured the cost — 8.2% of months
selected for their quadrant, and a story/market agreement of 60.6% against 59.2% expected
if the two were independent.

### 1.2 The fact that was not in the week-C record

**The panel's "hot" bit and the era-safe join's era bucket are the same predicate.**
`panel_quadrant` sets hot = `panel YoY > era_threshold_pp`; `sample_months` sets
`era_bucket` = `panel YoY > era_threshold_pp`. The same number, 3.3513 pp, on the same
series.

The consequence is not small. A join must land in the spine's quadrant (pool membership
*is* that) **and** match the previous row's era bucket. If the spine has just crossed the
inflation line and the row the block is standing on has not, those two demands contradict:
every candidate is filtered out and the block simply continues. **An era-safe join can
never follow the story across the inflation line.** Adding joins — shorter blocks, or
breaking on divergence — cannot repair that, because the repair is forbidden at exactly
the months that matter.

What *can* cross the line is real history's own contiguity: a stretch of months that
crosses it by itself, on the panel, in the same month the spine does. That is not a
teleport, and the era filter never sees it. **So the fix has to be about which stretch is
chosen, not only about how often a choice is made.** The measurement bears this out: after
the fix, **1,083 of the 1,342 remaining unreached months (80.7%) are divergences the era
filter refused.**

### 1.3 The fix, in three parts

| part | what it does | what it preserves |
|---|---|---|
| **(b) path-matched entry** | an entry is chosen for the length of the leading run over which the panel's own forward quadrants equal the spine's coming months, uniform among the ties | pool membership, severity stratum, both join filters. It **cannot** empty a pool: every candidate already matches at the entry month, so the maximum prefix is always attained |
| **(c) mid-block divergence break** | a block whose next month would land in the wrong quadrant is ended, and the ordinary era-safe join is attempted | with no candidate reachable the block continues, exactly as the platform does, and the month is **counted** as an unresolved divergence rather than papered over |
| **(d) anticipating re-entry** | when that break is unjoinable, move instead to a month — drawn from the pool of the quadrant the block is standing in, through the same two join filters — from which history walks into the spine's quadrant within the look-ahead | the month itself stays mis-conditioned and is still counted as unreached. The move fires **only when it pays**: if no candidate reaches the spine's quadrant anywhere in the look-ahead, nothing moves |

The look-ahead is **6 months** — the world's own declared `mean_block_months`, the horizon
over which an entry is expected to be used. It is not a new number, and §2 shows the
choice is not on a knife edge for reach.

**Nothing else changed.** Era-safe joins stand. The forced-re-entry rule (owner ruling
2026-08-16), including its unfiltered fallback, is byte-unchanged. Block length is
untouched — it is an owner declaration (2026-08-15, on the generator-only coherence study)
and re-declaring it was not this campaign's to do. Severity remains selection-only: the
sampler reads the panel's quadrant and nothing else — no return, no drawdown, no portfolio
outcome. Premise refusal is untouched. **No new random stream was opened**: every draw the
fix makes comes from the block stream the platform already opens per path, so there is no
new axis and no new stride — the "coprime strides + distinct-tape test" obligation does not
arise, and the tests instead pin determinism and seed separation directly.

### 1.4 How the copy is kept honest

The fix lives in `scripts/stage2_worlds.py::_reach_draw`, a copy of the platform's `_draw`
with the two gated additions. Week C refused exactly such a copy because copies drift. It
is admissible here only because it is **pinned**:
`tests/test_stage2_weekc_composition.py::test_the_baseline_reach_draw_is_the_platforms_own`
runs both on the same synthetic inputs and demands **bit-identical row indices** at
`REACH_BASELINE`, and its partner test demands that a non-baseline design does *not* match,
so the pin is a comparison rather than a tautology. `scripts/stage2_weekc.py` names the
baseline design at every call site and still regenerates `stage2-weekc-results.json`
**byte-identically** (`sha256 565413ac…`, unchanged).

---

## 2. The frontier — every candidate design, one batch, the sealed judges

All twelve arms on the unconditional 50-decade batch at week A's verification seed
20260821. **Reach** is the share of months whose drawn panel row carries the spine's own
quadrant; **selected** is week C's own formula (months that open a block), recomputed
unchanged so the 8.2% is comparable; **agreement** is the A1/A2 dial agreement.

| arm | reach | selected | agreement | seams | forced re-entry | rows visited | A1 diff pp | A2 corr / gap / window | R2 max jump / p95 |
|---|---|---|---|---|---|---|---|---|---|
| baseline (pre-fix) | 0.4785 | 0.0823 | 0.6059 | 444 | 1 (1 unfiltered) | 721 | +0.378 **P** | −0.018 / 0.061 / 0.476 | 4.133 / 0.883 |
| (a) short blocks, 3m | 0.5178 | 0.1585 | 0.6044 | 901 | 0 | 638 | −1.328 | −0.047 / 0.095 / 0.432 | 2.480 / 0.976 |
| (a) short blocks, 2m | 0.5612 | 0.2433 | 0.6254 | 1410 | 3 (3) | 709 | +3.931 **P** | +0.034 / 0.099 / 0.505 | 9.442 / 1.207 |
| (b) path match, h=6 | 0.5495 | 0.0908 | 0.6417 | 495 | 5 (2) | 687 | −1.924 | +0.059 / 0.108 / 0.640 | 9.400 / 0.900 |
| (b) path match, h=12 | 0.5873 | 0.0937 | 0.6513 | 512 | 3 (2) | 694 | +2.969 **P** | +0.035 / 0.006 / 0.603 | 9.400 / 0.858 |
| (c) divergence break | 0.6957 | 0.1738 | 0.6948 | 993 | 0 | 645 | −2.969 | +0.066 / 0.184 / 0.555 | 2.480 / 1.143 |
| (b)+(c), h=6 | 0.6882 | 0.1385 | 0.7083 | 781 | 3 (2) | 640 | −6.013 | +0.031 / 0.163 / 0.611 | 8.780 / 0.968 |
| (b)+(c), h=12 | 0.7142 | 0.1322 | 0.7102 | 743 | 1 (1) | 656 | −1.403 | +0.037 / 0.037 / 0.639 | 8.780 / 0.968 |
| **(d) +anticipate, h=6 — ADOPTED** | **0.7763** | **0.2020** | **0.7783** | 1162 | **0** | 639 | −7.510 | +0.077 / 0.229 / 0.657 | **2.4997** / 1.102 |
| (d) +anticipate, h=12 | 0.7657 | 0.2397 | 0.7631 | 1388 | 1 (1) | 553 | −5.700 | −0.006 / 0.067 / 0.591 | 5.320 / 1.178 |
| (d) +anticipate, h=24 | 0.7092 | 0.2733 | 0.7274 | 1590 | 0 | 546 | −0.797 | −0.058 / −0.085 / 0.554 | 2.490 / 1.338 |
| (e) era-relaxed — **DISCLOSURE, not adopted** | 0.8247 | 0.2120 | 0.7843 | 1222 | 0 | 590 | −15.379 | −0.125 / 0.056 / 0.505 | 2.495 / 1.309 |

**How the arms read.**

- **(a) shorter blocks is the weakest lever and the most expensive.** Halving the declared
  block length to 3 months triples the conditioning points (8.2% → 15.9%) and buys 4 points
  of reach; going to 2 months buys 8 points and 1,410 seams. Neither touches the era-line
  problem at all — agreement stays at chance. And block length is an owner declaration, so
  this arm is not the campaign's to adopt even if it had worked.
- **(b) path matching is cheap and partial.** It buys 7 points of reach for **51 extra
  seams** — it changes *which* stretch is entered, not how often. It is the only part of
  the fix that can cross the era line, and it is why (d) works.
- **(c) divergence break is the big single lever and it is half-blocked.** Reach 0.696, but
  **1,619 of its 1,826 breaks (89%) find no candidate** and continue anyway. That number is
  the era filter, measured.
- **(d) is the adopted point.** Highest reach and highest agreement of any arm that keeps
  every constraint; the only arm that resolves era-blocked divergences at all; and the only
  one that drives forced re-entries to zero — which, per §5.3, is what cures `R2`'s join
  half.
- **(e) prices the constraint and is never adopted.** Dropping the era bucket from the join
  filter (keeping the declared 2.5 pp level bound) buys another 5 points of reach. It is
  reported so the cost of the preserved rule is a number rather than an argument.
  **Relaxing an era-safe join is an owner ruling, not a campaign's choice** — §7's second
  stop-question.

**On the look-ahead.** Reach across h = 6 / 12 / 24 is 0.776 / 0.766 / 0.709 and agreement
0.778 / 0.763 / 0.727, so the declared-block-length choice is also the best of the three on
the funded objective; nothing was traded to pick it. Longer look-aheads make the
anticipating move fire more often (314 → 670 → 1,053) and buy less, because a candidate
that matches a 24-month path does not exist in an 813-row panel.

**The selection rule, stated so it can be checked.** The arm was chosen on **reach,
agreement and the preserved constraints** — the ruling's own objective — and *not* on any
bar. Reading down the bar columns confirms the choice is not a bar-maximising one: (c) has
a better `A1` and (b) h=12 has a better `p95`.

---

## 3. Reach and agreement — before and after

| quantity | before | after |
|---|---|---|
| months in the batch | 6,000 | 6,000 |
| months that open a block (**week C's 8.2% figure**) | 494 — **0.0823** | 1,212 — **0.2020** |
| months whose drawn row carries the spine's quadrant (**reach**) | 2,871 — **0.4785** | 4,658 — **0.7763** |
| **dial agreement** (the 60.6% figure) | **0.605926** | **0.778333** |
| agreement expected if the two dials were independent | 0.591596 | 0.605084 |
| **excess over chance** | **+1.43 pp** | **+17.32 pp** |
| mean inflation of a drawn month when the spine says "high" | 3.2248 pp | **3.8460 pp** |
| mean inflation of a drawn month when the spine says "low" | 3.0250 pp | **2.2490 pp** |
| distinct panel rows visited | 721 | 639 |

**The two reach numbers are different quantities and both are reported.** "Selected"
counts months chosen at a block start; "reach" counts months that actually carry the
story's quadrant, however they got there — a month that continues a block *into* the right
quadrant is conditioned in every sense `A1` and `A2` can see. The first is a lower bound on
the second, and reporting only the first (as week C did) understates the pre-fix engine as
much as it would understate this one.

**The week-C record's sharpest sentence is now false in the right direction.** It read:
*"a 'high' month's own inflation averages 0.20 pp above a 'low' month's, and both sit below
the 3.3513 pp era line the pools are conditioned on."* After the fix the gap is **1.60 pp**
and the high mean sits **above** the era line while the low mean sits well below it.

**Where the residual 22.4% goes, exactly.** Reach = 1 − 1,342/6,000 = 0.77633, and 1,342 is
precisely the count of unresolved divergences. There is no other source of mis-conditioning
left: every month is either selected in the spine's quadrant, continues into it, or is a
divergence the join filters refused. **1,083 of the 1,342 (80.7%) are refused by the era
filter alone.**

---

## 4. The scoreboard — all twelve bars, before and after

Read by the sealed judges, imported by name and never re-implemented. The eight pre-flesh
bars come through `stage2_weekc.spine_identity`, which **raises** unless each reproduces
week A's committed value to 1e-12.

| tier | bar | sealed band / floor | before | after | verdict |
|---|---|---|---|---|---|
| causal | **T1** | [1.775283, 3.347362] | 2.239246798804 | **2.239246798804** | PASS → **PASS** (drift 0.0) |
| causal | **O1** | ≥ 0.5180669105 | 0.560824742268 | **0.560824742268** | PASS → **PASS** (drift 0.0) |
| persistence | **D1** | [0, 5] months | 2.0 | **2.0** | PASS → **PASS** |
| persistence | **D2** | [1, 7] months | 4.0 | **4.0** | PASS → **PASS** |
| persistence | **D3** | [2, 8] months | 4.0 | **4.0** | PASS → **PASS** |
| persistence | **D4** | [1, 7] months | 3.0 | **3.0** | PASS → **PASS** |
| phase | **P1** | departures ≥ 0.040330 / 0.031446 | binding margin +0.042073930959 | **+0.042073930959** | PASS → **PASS** |
| curve | **P2** | [0.391707, 0.673371] | 0.770682653481 | **0.770682653481** | FAIL → **FAIL** (above) |
| allocation | **A1** | direction; high spread in [−5.053, +32.316] pp | **+0.378055215669** | **−7.510267165828** | **PASS → FAIL** |
| allocation | **A2** | corr > 0; gap ≥ 0.136094; ≥ 80% of windows | −0.017743 / +0.060911 / 0.4760 | **+0.077493 / +0.228567 / 0.6567** | FAIL(3 of 3) → **FAIL (1 of 3)** |
| no-regression | **R1** | monotone coverage; ≥ 1/20 breach at 55 | medians [0.0981, 0.2919, 0.3616, 0.6680]; breach 4/20 | **[0.1219, 0.3785, 0.4730, 0.9225]; breach 8/20** | PASS → **PASS** |
| no-regression | **R2** | join ≤ 2.5 pp; p95 ≤ 0.929239 pp | 4.132500 / 0.883035 | **2.499733 / 1.102315** | FAIL (join) → **FAIL (p95)** |

> **Nine of twelve passed before; eight of twelve pass after — `A1`'s flip is the
> difference.** [CORRECTED per the integrity review; the original boxed claim of
> "nine, before and after" contradicted the table above it.] The eight spine bars are bit-identical —
> a compiler change cannot move a bar cut from the spine, and the worst drift over the
> eight is **2.862e−13**, week C's own figure, which is twelve-digit rounding. **The three
> flesh bars that can move, moved: one improved without flipping (`A2`), one flipped in
> each direction (`R2`'s two halves), one flipped down (`A1`).**

---

## 5. Bar by bar

### 5.1 `A2` — from failing three conditions to failing one

| condition | required | before | after | history |
|---|---|---|---|---|
| correlation, high inflation | > 0 | −0.017743 **FAIL** | **+0.077493 PASS** | +0.30125 |
| difference, high − low | ≥ 0.136094 | +0.060911 **FAIL** | **+0.228567 PASS** | 0.31949 |
| share of 3-year windows positive | ≥ 0.80 | 0.4760 **FAIL** | 0.6567 **FAIL** | 0.947 |

**Two of three conditions flip to PASS and the third moves 18 points toward its floor.**
The correlation is positive on **6 seeds of 6** after the fix (+0.077 … +0.143) where before
it straddled zero on 6 seeds (−0.018 … +0.079, 4 positive). This is the bar D-SP-10 was
funded for, and it responded.

**The disclosure arm got stronger too, which is the check that the flesh was never the
problem.** Judged on the inflation the drawn months actually carried rather than the
spine's: correlation **+0.3327** (was +0.1765), gap **+0.5088** (was +0.3483), window share
**0.9367** (was 0.9285) — all three pass, with room, and closer to history than before.
The months this compiler selects carry history's stock–bond flip; what the fix improved is
the link between the story's dial and the months it selects, and there is still 22.4% of
that link missing.

### 5.2 `A1` — a flip that is inside its own noise, and a mechanism worth more than the flip

| quantity | before | after | history |
|---|---|---|---|
| spread, high inflation | +2.1424 pp/yr | **−1.8962 pp/yr** | +4.8720 |
| spread, low inflation | +1.7643 pp/yr | +5.6141 pp/yr | +1.3787 |
| **difference** | **+0.3781 PASS** | **−7.5103 FAIL** | +3.4933 |

**First, the dispersion, because it changes what the flip means.** Six seeds per arm, fixed
before any was read, judging nothing:

| arm | `A1` difference across seeds 20260821–26 | mean | sd | positive |
|---|---|---|---|---|
| before | +0.378, −4.904, −4.604, +1.464, −5.568, −0.367 | **−2.267** | 3.093 | **2 of 6** |
| after | −7.510, +0.637, +1.993, +0.028, +2.597, −3.594 | **−0.975** | 3.866 | **4 of 6** |

**The sealed seed is the pre-fix engine's best draw of six and the fixed engine's worst.**
On the mean, the fix *improves* `A1`; on the sealed seed it flips it. `A1` at n = 50 swings
by ±5 pp between adjacent seeds under both engines, against a bar that asks only for a
sign. Neither the old PASS nor the new FAIL is carrying much.

**Second, the mechanism, which is a real finding and does not depend on the flip.** The
entry pool is the worst 35% (and, in the crisis segment, the worst 10%) of panel months by
the `all_down` severity functional. Split that pool by inflation and the whole story is
visible — these are panel facts, no generation involved:

| population | months ≥ 4% YoY | commodities − bonds | months < 4% | commodities − bonds |
|---|---|---|---|---|
| whole panel (history's own `A1` anchor) | 225 | **+4.872 pp/yr** | 576 | +1.379 |
| worst-35% `all_down` pool | 162 | +6.092 | 122 | **−11.487** |
| worst-10% `all_down` pool | 59 | **−8.519** | 22 | **−20.851** |

**The severe months of history are flight-to-quality months: bonds win and commodities
lose, whatever inflation is doing.** So the harder the compiler conditions — and the more
months it therefore draws *from the pool* rather than inheriting by contiguity — the more
`A1` reads the severity functional rather than the inflation dial. The anticipating move
sharpens this because it parks, by construction, on a wrong-quadrant month **from the
pool**: at the sealed seed the most-drawn such months are 2008-12, 2009-02, 2010-05/06,
1998-08 — the exact months where bonds rallied hardest.

**This is not an argument for changing anything.** It is the reason `A1`'s content is thin
in both engines, and it is §7's third stop-question: a bar written on the whole panel's
inflation split is being read on a world whose months are drawn from the worst third of the
same panel, and those two populations disagree in sign.

### 5.3 `R2` — the join half is cured, the p95 half now fails, and both are arithmetic

| half | bound | before | after |
|---|---|---|---|
| largest jump at a seam | ≤ 2.5 pp | **4.132500 FAIL** | **2.499733 PASS** |
| p95 adjacent-month change | ≤ 0.929239 pp | 0.883035 PASS | **1.102315 FAIL** |
| seams | — | 444 | 1,162 |
| forced re-entries / of which unfiltered | — | 1 / 1 | **0 / 0** |

**The join half was cured exactly as the charter guessed it might be, and not by
special-casing it.** Week C's entire `R2` failure was one unfiltered forced re-entry in
6,000 months: a block reached the panel's last row and no candidate matched the era filter,
so it drew unfiltered. The fix never touches that rule. What it does is make blocks whose
forward path cannot track the spine unattractive to enter — and a block entered within a
few rows of the panel's end cannot track anything. **Forced re-entries fall to zero, and
with them the only seam in the design that can exceed the bound.** The largest remaining
jump, 2.499733 pp, is an ordinary join landing 0.00027 pp under its own bound.

**Across seeds the cure is real but not universal**: max jump before was
[4.13, 10.98, 12.55, 7.03, 9.59, 6.05] — **0 of 6 inside the bound**, and the sealed seed
was the mildest of the six. After: [2.50, 13.04, 9.34, 2.49, 4.55, 2.48] — **3 of 6
inside** [CORRECTED per the integrity review: 2.499733, 2.494033 and 2.475963 are ≤ 2.5;
the original said 4 of 6]. Forced re-entry is a rare event and the fix makes it rarer, not impossible.

**The p95 half fails for a compositional reason, and here is the arithmetic.** The p95 is
taken over all 5,950 adjacent-month pairs. Split them:

| | before | after |
|---|---|---|
| seam pairs | 444 (7.46%) | 1,162 (19.53%) |
| p95 over **contiguous** pairs only | 0.7422 pp | **0.6956 pp** |
| p95 over **seam** pairs only | 1.8148 pp | 1.9143 pp |
| pairs above the 0.929239 bound | 259 (**4.35%**) | 409 (**6.87%**) |
| … of which seams / contiguous | 131 / 128 | **303 / 106** |

**The contiguous months got *calmer* (0.742 → 0.696) and the contiguous pairs above the
bound *fell* (128 → 106).** What rose is the seam count. Before, 4.35% of pairs exceeded
the bound so the 95th percentile sat below it; after, 6.87% do, so it sits above. **A join
is permitted to move trailing inflation by up to the declared 2.5 pp, conditioning that
reaches every month is bought with joins, and the p95 bar was calibrated on a world with
7% seams.** The two halves of `R2` therefore pull against each other by construction — the
join half wants fewer forced re-entries, which the fix delivers by making blocks
path-appropriate; the p95 half wants fewer joins, which is the opposite of reach. **This is
the trade the frontier discipline says to map, not tune**, and §7's first stop-question
asks the owner to rule on it.

### 5.4 `R1` — passes, on harder worlds, with its disclosed third check now failing

| check | before | after |
|---|---|---|
| coverage medians across [15, 35, 40, 55] | [0.0981, 0.2919, 0.3616, 0.6680] | **[0.1219, 0.3785, 0.4730, 0.9225]** |
| monotone (sealed) | PASS | **PASS** |
| breach at the 55-point arm (sealed, ≥ 1/20) | 4/20 | **8/20** |
| hold-course depth (**disclosure**, self-constructed band [−0.4260, −0.3750]) | −0.376591 inside by 0.0009 | **−0.547720 — outside** |
| the judge's own `overall` (which ANDs the disclosure in) | true | **false** |

**`R1` passes both sealed conditions and the worlds got harder in every column** — every
coverage median rises and the breach count doubles again (2/20 in round two, 4/20 in week C,
8/20 now). That is the direction a no-regression bar exists to protect.

**But the distinction week C drew as a formality is now load-bearing.** `spine_pilot_b3`'s
third check — hold-course drawdown depth inside a band the script constructs for itself —
is documented in its own docstring and in the round-two record as "constructed post-seal,
disclosed, not judged", and the exam's `R1` statement quotes two conditions. Week C cleared
that band by 0.0009 and noted the distinction "will matter the moment the number moves".
**It has moved**: depth is −0.5477 against a shallow edge of −0.3750. The reported `R1`
PASS is the two sealed conditions; the judge's own `overall` field is now **false**. Both
are in the artifact and neither is hidden. §7's fourth stop-question.

### 5.5 The premise-accepted arm — a disclosure, and it moved the other way

The exam judges the unconditional arm. On the declared-premise batch (world …802's Hard
Landing clause on): `A1` **+1.7714 (PASS)** where week C's premise arm read **−2.9465
(FAIL)**; `A2` still fails (correlation +0.0067, window 0.5022); `R2` max jump 10.7095 pp.
Week C's tenth stop-question — *"is a bar that flips sign between the two arms carrying the
meaning it was written for?"* — is now sharper, not softer: `A1` flips sign between the two
arms under both engines, in **opposite directions**.

---

## 6. What was checked rather than asserted

- **The spine did not move.** The eight pre-flesh bars are re-judged on the fixed batch and
  every value reproduces week A's committed artifact; the check **raises** above 1e-12 and
  the worst drift printed by the run is **2.862e−13**. A compiler change cannot move a spine
  bar, and now that is evidence. (The artifact's `max_abs_drift` field reads `0.0` because
  it is rounded to twelve decimals — the same rounding the stage-2 verdict's §7.2 correction
  was about. The unrounded figure is the one quoted here.)
- **The engine was not refitted.** `build_frozen_system` re-runs week A's estimator and
  asserts all **42** coefficients against `stage2-fitted-params.json` at 1e-11 before any
  batch is compiled; the worst drift is below the artifact's own twelve-decimal rounding,
  and a drift above tolerance is a stop rather than a warning.
- **The pre-fix arm still reproduces the committed week-C reading.** `A1`, `A2` and `R2` are
  recompiled here under `REACH_BASELINE` and checked field by field against
  `stage2-weekc-results.json` at 1e-12; a drift is a stop, because the before/after
  comparison would otherwise be meaningless.
- **`stage2-weekc-results.json` is byte-identical** to its committed version
  (`sha256 565413ac…`) after the change.
- **`stage2-reach-results.json` is byte-identical on a re-run** (`sha256 bb78ff37…`), and
  is written with LF endings so the file on disk IS the blob git stores -- a quoted sha256
  that only holds on one platform is not a determinism claim (commit `0c7aa7e`'s point).
- **The composed sampler is pinned to the platform's** at `REACH_BASELINE`, bit-for-bit,
  by a test that a non-baseline design is required to fail.
- **The b3 ladder's 20 rungs are pairwise distinct** on both their spines and their compiled
  month tapes, checked under the new design (the round-one seed-stride defect).
- **No new RNG axis exists**, so no new stride was needed; determinism and seed separation
  are tested directly on the composed draw.
- **Nothing inside either seal was edited.** `stage2-prereg.json` hashes six scripts and
  five documents; none of them is touched. `scripts/stage2_worlds.py`,
  `scripts/stage2_weekc.py` and the new `scripts/stage2_reach.py` are in neither seal.

---

## 7. Stop-questions — OPEN owner decisions

1. **`R2`'s two halves now pull in opposite directions and no design can satisfy both.**
   Reach is bought with joins; a join may legally move trailing inflation by the declared
   2.5 pp; the p95 bound was calibrated against a world with 7% seams and the fixed world
   has 19.5%. The honest options are to accept `R2` as a bar that measures seam *frequency*
   as much as seam *size*, to rule that the p95 half needs re-deriving against a conditioned
   compiler (which is an exam change and cannot be done inside this campaign), or to accept
   less reach. **A frontier, not a defect.**
2. **The era filter costs 5 points of reach and the disclosure arm prices it.** The era
   bucket and the quadrant's hot bit are the same predicate, so an era-safe join can never
   follow the story across the inflation line. Dropping the bucket while keeping the
   declared 2.5 pp level bound reaches 0.8247 — and a 2.5 pp-bounded step across a
   median-derived line is arguably not the "era teleport" the rule was written against.
   **Relaxing it is an owner ruling and was not taken.**
3. **`A1` reads the severity functional more than the inflation dial, and better
   conditioning makes that worse.** History's high-inflation months pay +4.87 pp/yr on
   commodities-minus-bonds; the worst-10% `all_down` pool's high-inflation months pay
   **−8.52**. Is `A1` carrying the meaning it was written for when the world it judges is
   drawn from the worst third of the panel?
4. **`R1`'s disclosed depth check has left its self-constructed band** (−0.5477 against a
   shallow edge of −0.3750), so the judge's own `overall` is now false while both sealed
   conditions pass. Confirm it stays a disclosure — in which case `R1` is a PASS — or rule
   it a bar, in which case it needs a band cut from something other than itself.
5. **The anticipating move deliberately selects 314 months the world's story contradicts**,
   to align the months after them. That is a new *kind* of incoherence: before the fix every
   mis-conditioned month was an inherited continuation. It is counted, it is disclosed, and
   the nearest alternative that never does it — (b)+(c) at h=12 — is one full row of the
   frontier table, at 0.714 reach, 1 forced re-entry and a worse `A2`.
6. **Promotion is still not asked for.** The fix is composed in `scripts/`. Promoting
   `_reach_draw` into `ah/gen/spine.py` is a separate owner release event, and this campaign
   does not ask for it.

---

## 8. Limitations

- **Reach is 77.6%, not 100%.** The ruling asked for conditioning that reaches every month.
  Under the preserved era-safe join rule that is **not attainable** — 80.7% of the remaining
  gap is the era filter refusing to cross the inflation line, and the only mechanism that
  can cross it is real history's own contiguity, which the panel supplies in finite
  quantity. The honest statement is: the fix reaches every month it is *allowed* to reach,
  and the residue is the constraint, measured.
- **One panel, 813 rows, one country, 68 years.** Path matching over a 6-month look-ahead
  is choosing among a few dozen candidates; over 24 months there is essentially nothing to
  choose from, which is why the longest look-ahead is the worst.
- **Texture was traded.** Distinct panel rows visited falls 721 → 639 and the mean block
  shortens; "history writes the rest" dilutes as blocks shorten (the 2026-08-15 coherence
  study's own unmeasured cost), and this fix shortens them by breaking rather than by
  re-declaring the length.
- **The six-seed dispersion is a disclosure and judges nothing.** It is reported because
  `A1`'s verdict change is smaller than its own seed-to-seed swing, and a reader who saw
  only the sealed seed would draw a conclusion the batch cannot support.
- **The standing caveat carries.** Nothing built on this generator line is a convincing
  model of history, the holdout is spent, and no appeal to held-out data is available.
