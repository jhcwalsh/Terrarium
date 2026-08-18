# D-SP-11 — the three rulers: designed, anchored, sealed, and then measured

**Date:** 2026-08-18 · **Branch:** `stage2-04-rulers` · **Status: measured, no owner
ruling taken.** Charter: `governance/decision-register.md` **D-SP-11** (2026-08-18, *"all
three"*) — a new seam/texture bar anchored and anti-tested; the conditional era-crossing
rule sealed before use; and the inflation-hedge measurement `A1` re-founded on a batch size
computed from the engine's own margin.

**What this document is.** The record of three new rulers and one engine rule, and of the
whole exam read through them. Every number below is produced by
`scripts/stage2_rulers_run.py` and lives in `docs/superpowers/specs/stage2-rulers-results.json`
(`sha256 045e66e5…`, byte-identical across two clean runs, LF endings so the file on disk is
the blob git stores).
The pre-registration is `docs/superpowers/specs/stage2-prereg-2.json`, written and committed
**before** the era-rule engine was run and before `A1R`'s ladder was compiled. No file inside
any of the three seals was edited, no threshold was moved, nothing was refitted, and no line
of `src/` or `schemas/` was changed.

**The charter's own condition, honoured literally.** The rulers change only forward. The
twelve sealed bars keep their thresholds, keep their judges and keep their words; `A1`'s
sealed single-batch verdict and `R2`'s two halves are reported here beside the new rulers
rather than replaced by them. `tests/test_stage2_rulers_seal.py::
test_both_prior_preregs_are_carried_byte_identical` fails if either prior seal moves.

---

## The one-paragraph answer

**The era-crossing rule works and it costs.** Conditioning reach goes **77.6% → 80.7%** and
story/market agreement **77.8% → 78.6%**; 104 seams cross the inflation line and **all 104
sit at a month where the spine's own inflation path crosses it, in the spine's own
direction** — re-derived from the compiled row tape, not read off the engine's counters. The
rule captures about three fifths of the reach that D-SP-10's disclosure arm priced the whole
era filter at, without ever crossing at a month the world's story does not. What it costs is
on the flesh bars: `A1` −7.51 → −9.68, `A2`'s high-inflation correlation +0.077 → +0.026,
`R2`'s p95 1.102 → 1.210. **The scoreboard count does not move: eight of twelve pass on both
sides.** The new seam bar `S1` returns its first verdict and it is a **FAIL on all three
engines in the lineage** — and that is the finding: the texture *inside* a block is
history's own on every arm and passes at both judged quantiles, while the **seams have
always been findable**, at week C's 444 seams as much as at D-SP-10's 1,162. A jump-threshold
detector separates seams from ordinary historical months with **45–49 points of advantage**
against a null that allows 21–30. D-SP-10's first stop-question asked whether `R2` measures
seam frequency or seam size; `S1` answers it: the size was out of band before the reach fix
existed, and the p95 flip `R2` recorded was frequency. And `A1`, re-founded on **514
sub-batches of fifty decades — 25,700 decades, a batch size computed for 90% power at the
engine's own measured margin** — stops being a coin flip and returns a verdict: the inflation
hedge **does not pay**, the pooled margin is **−1.54 pp** on the D-SP-10 engine and **−3.14 pp**
under the era rule, and the interval excludes zero by 12 and 24 standard errors and history's
+3.49 by 39 and 51. **The sealed single-batch reading was −7.51 where the truth is −1.54 — off
by 47 standard errors, four times the whole effect.** Every `A1` verdict this campaign has
recorded, in either direction, was a reading of a statistic whose sampling error dwarfed the
thing it measured. Nothing is re-graded; that is now simply known.

---

## 1. Ruler 1 — the seam/texture bar `S1`

### 1.1 The question, and why `R2` cannot answer it

`R2` has two halves. The first bounds the largest inflation jump at a seam; the second bounds
the 95th percentile of *all* adjacent-month inflation changes, pooled. That second half moves
when seams get **bigger** and it moves when seams get **more frequent**, and it cannot tell
you which. D-SP-10's record is the demonstration: the p95 half flipped to FAIL while the
contiguous months it is pooled over got *calmer* (0.742 → 0.696) and the number of seams
almost tripled. The bar was reading a frequency change as a texture failure.

**`S1` judges shape and is blind to frequency.** How many seams a world has is `R2`'s
business and `R2` keeps answering it. What `S1` asks is: *given that this world spliced here,
can you tell?*

### 1.2 The anchor — history's own month-to-month distribution, and it stands

The anchor is the panel's own adjacent-month `|ΔYoY|`: 800 defined transitions over the
campaign panel. **It is not a new anchor.** Its 95th percentile is `0.7433911963542538`,
which is `spine_pilot_report.judge_b2`'s sealed `panel_p95_adjacent_yoy_pp` to every digit —
the number `R2`'s own bound is cut from. `S1` stands on the exam's existing anchor rather
than opening a second one, and the seal records the anchor's sha256 so a moved panel is a
loud failure rather than a quiet re-anchoring.

| quantile | history's own |
|---|---|
| median | 0.23302 |
| p95 | **0.74339** (= `R2`'s sealed anchor) |

### 1.3 The seam criterion — anchored, not invented

The principle, and it is the charter's recommended one:

> **A seam should be statistically indistinguishable from an ordinary historical
> month-transition.**

Made concrete: the seam-pair jump distribution must sit inside history's own adjacent-jump
distribution, at declared quantiles, allowing for the sampling uncertainty of a sample that
size. **Nothing about the generated world enters the derivation of the band** — the band is a
function of the panel and of a sample size, and that is the entire content of the word
"anchored" here.

**Why this is the right operationalisation of "can you find them".** A detector that flags a
transition as a seam whenever its inflation jump exceeds a threshold `t` has an advantage
over guessing of exactly `|F_seam(t) − F_history(t)|`. If the two distributions agree where a
detector would cut, no such detector works. So the bar counts the seams a detector *could*
find, and not the seams the compiler cut.

### 1.4 The statistic and the band, exactly

**Statistic.** Over the compiled batch's *distinct* ordered adjacent row-pairs `(a, b)`, split
into **seam** pairs (`b ≠ a+1`) and **contiguous** pairs (`b = a+1`), take `|ΔYoY|` and read
its median and its 95th percentile.

**Band.** The null-predictive distribution of that quantile when `n` transitions are drawn
from the anchor: resample `n` values by **moving blocks of 24 months**, take the quantile,
repeat **2,000** times, keep the central **95%**. Deterministic in a sealed seed.

**Verdict.** Four two-sided conditions — contiguous at q50 and q95, seam at q50 and q95 —
and `S1` passes when every *judged* one holds.

### 1.5 Every tolerance, and the reason for it (the house rules)

| choice | value | why |
|---|---|---|
| **quantiles** | 0.50, 0.95 | the median is the ordinary-month anchor a detector tunes against; the p95 is the tail anchor **and is not a new number** — it is the quantile `R2`'s own sealed bound is cut at, so the two bars are read on the same summary and can be held side by side. The p99 is excluded: 800 anchor pairs means it rests on eight order statistics and its band is wider than any effect worth barring. The mean is excluded: `\|ΔYoY\|` is strongly right-skewed, so its mean re-states the tail and would double-count the p95 |
| **band level / draws** | 95% / 2,000 | `P2`'s own sealed convention, reused rather than a third one invented |
| **resampling** | moving blocks, 24 months | trailing 12-month YoY is a 12-month moving construct, so `\|ΔYoY\|` is strongly serially dependent and an iid bootstrap would report a band far narrower than history's own resolution — the bar would then reject worlds indistinguishable from history. 24 months is the campaign's `PRIMARY_BLOCK_MONTHS`, imported not retyped. **This is the conservative direction, which is the right direction for a band that decides a FAIL** |
| **de-duplication** | distinct ordered row-pairs | a fifty-decade batch has 5,950 adjacent pairs drawn from 800 distinct historical transitions and ~620 distinct rows, so the same transition is re-used dozens of times. Counting re-uses as independent evidence would cut the band far below the panel's own resolution and turn the bar into a test of how often the compiler repeats itself — which is `R2`'s question. The raw reading is published beside every judged one |
| **minimum tail count** | 5 beyond the quantile | the standard expected-count rule: 100 transitions at the p95, 10 at the median. Below it a PASS would mean "too few seams to tell" rather than "the seams look like history". A world with **no** seams passes the seam half **vacuously** — correct, there is nothing to find |
| **two-sided** | all four conditions | seams that are too big are findable; seams that are unnaturally *smooth* are findable too, and a compiler that only joins near-identical rows has stopped conditioning. The anti-test shows both edges bite |
| **a rule, not a number** | sealed as a rule | the band depends on the sample size the world presents, so a fixed threshold would be a band cut at one arbitrary `n`. Ruling **SQ9**'s precedent — seal the selection rule when the value is not pinned. Everything determining the band *is* pinned and hashed, and the seal carries a reference table of bands over `n = 100 … 6000` so any arm can be checked by hand |

### 1.6 The anti-tests — both directions, and the bar is reachable

`scripts/stage2_rulers_antitest.py`, run **before** the seal, on row tapes built over the
**real** panel so the judge's band is cut from the anchor the measurement uses. The seal
script refuses to write if any sweep is non-monotone or any control breaks.

| sweep | grid | `S1` pass rate | mean margin | monotone |
|---|---|---|---|---|
| **seam inflation** — seam jumps shrinking from 3× history's scale to history's own | 3.0 → 1.0 | 0.00, 0.00, 0.00, 0.00, **1.00** | −8.61 → −4.10 → −1.78 → −0.39 → **+0.34** | yes |
| **seam over-smoothing** — seam jumps growing from a fifth of history's scale to it | 0.2 → 1.0 | 0.00, 0.00, 0.00, 0.00, **1.00** | −3.03 → −2.18 → −1.26 → −0.37 → **+0.30** | yes |
| **texture roughening** — entries widening from the panel's most violent decile to the whole panel | 0.90 → 0.0 | 0.00, 0.00, 0.42, **1.00, 1.00** | −0.40 → −0.22 → −0.01 → +0.09 → **+0.30** | yes |

The margins move as a gradient, not as a step the grid happened to straddle.

**Why the sweeps run *toward* fidelity.** `S1`'s pass region is an interval, so a raw "more
of the effect" sweep would be non-monotone by construction. Each sweep therefore approaches
fidelity from one side and the pass rate is required not to fall — exam §6.1's rule stated on
the effect the bar actually measures. `P2`'s own loading sweep set the precedent.

**The bar is reachable.** At the fidelity point of both seam sweeps — where seam jumps *are*
draws from history's own distribution, by construction — `S1` passes 12 of 12. A bar no
design can clear is not a bar, and this is the evidence `S1` is not one.

| control | requirement | result |
|---|---|---|
| **noise-inflation attack** | must FAIL, and fail on the **upper** side of the texture half | `S1` pass rate **0.00 at every rung**; texture fails above **1.00** at the strongest camouflage; the self-referential bar `S1` refuses to be is fooled **0.50** of the time there |
| **history identity** | a world that IS history must PASS | **1.00**, seam half vacuous **1.00** |

**On the attack, and on the strawman that was rejected.** The obvious attack — seams at 2.5×
history's scale, camouflaged by roughening — was tried first and **discarded as a strawman**:
no real months are violent enough to hide a 2.5× seam, so even a self-anchored bar catches
it, and barring it proves nothing. The sealed attack is calibrated to the regime where the
camouflage genuinely works: **seams only 1.3× history's scale**, with every block entry drawn
from progressively more violent stretches of the panel. At the 80th-percentile roughness the
self-referential bar is fooled half the time — and `S1` fails 100% of the time, with its
**texture** half failing on the **upper** side 100% of the time. *The roughening that hides
the seams is exactly what `S1` catches.* That is the whole justification for anchoring the
band on history rather than on the world's own months, and it is a measurement rather than an
argument.

### 1.7 `S1`'s first reading — three engines, one answer

| arm | texture q50 | texture q95 | **seam q50** | **seam q95** | verdict | margin |
|---|---|---|---|---|---|---|
| **week-C baseline** (pre-D-SP-10) | 0.2245 in [0.1918, 0.2726] ✓ | 0.7282 in [0.6436, 0.8426] ✓ | **0.6010** vs [0.1799, 0.2849] ✗ | **1.8289** vs [0.6087, 0.8830] ✗ | **FAIL** | −3.447 |
| **D-SP-10 adopted** | 0.2111 in [0.1894, 0.2740] ✓ | 0.7435 in [0.6410, 0.8459] ✓ | **0.6143** vs [0.1945, 0.2723] ✗ | **2.0418** vs [0.6444, 0.8426] ✗ | **FAIL** | −6.050 |
| **D-SP-11 + era rule** | 0.2150 in [0.1894, 0.2740] ✓ | 0.7597 in [0.6410, 0.8459] ✓ | **0.6868** vs [0.1967, 0.2724] ✗ | **2.1836** vs [0.6451, 0.8395] ✗ | **FAIL** | −6.917 |

**The texture half passes on every arm, at both quantiles.** The months inside a block are
history's own months and they look like it. That is the half the identity control validates
and it is a clean result: whatever is wrong with these worlds, it is not their within-block
texture.

**The seam half fails on every arm, by a factor of two to three.** Seam medians sit at 0.60 –
0.69 against a band whose upper edge is 0.27; seam p95s sit at 1.83 – 2.18 against an upper
edge of 0.84.

**Detectability, the disclosure that makes it concrete:**

| arm | KS(seam, history) | null p95 at that `n` | KS(contiguous, history) |
|---|---|---|---|
| week-C baseline | **0.4556** | 0.3045 | 0.0297 |
| D-SP-10 adopted | **0.4530** | 0.2251 | 0.0555 |
| D-SP-11 + era rule | **0.4860** | 0.2142 | 0.0507 |

A jump-threshold detector finds seams with 45–49 points of advantage over guessing; sampling
noise alone allows 21–30. The contiguous months, by contrast, are indistinguishable from
history at 3–6 points.

### 1.8 What `S1` says that `R2` could not

1. **The seam problem pre-dates the reach fix.** Week C's engine — 444 seams, `R2`'s p95
   comfortably inside its bound at 0.883 — already had seam jumps 2.5× outside their band and
   a detectability of 0.456. **`R2` passing its p95 half was never evidence that the seams
   were invisible; it was evidence that there were few of them.** This is D-SP-10's first
   stop-question, answered with a number.
2. **The era rule makes seams slightly bigger, by construction.** Crossing the inflation line
   means a larger inflation jump almost by definition, so seam p95 goes 2.04 → 2.18 and
   detectability 0.453 → 0.486. That is a real cost of ruler 2 and it is the kind of cost a
   frequency-blind bar exists to surface.
3. **The lever is join *selection*, not the join *bound*.** Every seam here already respects
   the declared 2.5 pp bound — `R2`'s join half passes on both engines at 2.4997. What fails
   is that among the era-safe candidates the compiler picks without regard to how far the
   inflation moves. A compiler that preferred small-Δ joins would move toward the band without
   touching a single declared tolerance. **`S1` names a lever the exam did not previously
   have.** It is not exercised here: that is an engine change and this campaign's engine
   change was ruler 2.

---

## 2. Ruler 2 — the conditional era-crossing rule

### 2.1 The rule, stated exactly

> A seam may land on a row whose era bucket differs from the row the block is standing on
> **only if** the spine's own inflation path crosses the era line between those same two
> months, **and only into the bucket the spine crosses into**.

### 2.2 The month-window semantics, and why the window is zero months wide

The licence is read **at the month being drawn, against the month the block is standing on** —
the same two months the join itself connects. No tolerance, no lag, no look-ahead.

Three reasons, and the third is the one that decides it:

1. It is the literal reading of the charter — *"in a month where the spine itself crosses
   it"*.
2. It is the tightest reading available, which is what makes this a faithfulness test rather
   than a relaxation with a better name.
3. **A ±k window would need a tolerance nobody has anchored.** A seam that crosses the line
   one month before the story does is a seam that crosses at a month the story does not, and
   the whole point of the era filter is that such months exist. A window was available and is
   **not taken**; taking one would be a separate ruling with its own anchor.

**The direction clause is not decoration.** Without it, "the spine crossed this month" would
license a crossing in *either* direction, and a compiler could answer the story going hot by
taking the flesh cool. The clause demands that the row left carries the spine's **old** bucket
and the row entered carries its **new** one.

**Two properties make it a faithfulness test.** The licence only **adds** candidates and never
removes one, and it never widens the declared `join_yoy_max_pp` level bound — a licensed
crossing still has to move trailing inflation by no more than 2.5 pp. So the rule cannot lower
reach, cannot empty a pool, and cannot turn a joinable month into a refusal.

### 2.3 The reach gained

| quantity | week-C baseline | D-SP-10 | **D-SP-11 + era rule** |
|---|---|---|---|
| **conditioning reach** | 0.4785 | 0.7763 | **0.8068** |
| months selected at a block start | 0.0823 | 0.2020 | **0.2072** |
| **dial agreement** | 0.6059 | 0.7783 | **0.7856** |
| agreement expected if the dials were independent | 0.5916 | 0.6051 | 0.6072 |
| **excess over chance** | +1.43 pp | +17.32 pp | **+18.02 pp** |
| seams | 444 | 1,162 | 1,193 |
| mid-block divergence breaks | — | 1,658 | 1,581 |
| unresolved divergences | — | 1,342 | **1,159** |
| … of which blocked by the era filter | — | 1,083 | **913** |
| anticipating moves | — | 314 | **210** |
| forced re-entries | 1 (1 unfiltered) | 0 | **0** |
| distinct panel rows visited | 721 | 639 | 639 |

**Reach 77.6% → 80.7%, a gain of 3.05 points.** D-SP-10's disclosure arm (e) priced the whole
era filter at 4.84 points of reach (0.8247). **The conditional rule captures 63% of that,
without ever crossing at a month the world's story does not** — and the remaining 37% is the
era filter refusing to cross at months the story is not crossing either, which is the rule
working rather than the rule failing.

**The anticipating move fires less, and that is the mechanism improving rather than the number
moving.** It fires only on a divergence the join filters left unresolvable, and 183 fewer
divergences are unresolvable under the rule (1,342 → 1,159) because the licence lets an honest
join take them instead. The move itself drops 314 → 210 — so 104 months that used to be
"parked on a wrong-quadrant row from which history walks into the right one" are now months
the compiler simply reaches. D-SP-10's fifth stop-question — the anticipating move deliberately
selects months the story contradicts — is a third smaller under this rule.

### 2.4 The assertion, tested and audited

| arm | seams | bucket-changing seams | at a story crossing, in the story's direction | forced-re-entry exemptions | **unlicensed** |
|---|---|---|---|---|---|
| week-C baseline | 444 | 1 | 0 | **1** | **0** |
| D-SP-10 adopted | 1,162 | 0 | 0 | 0 | **0** |
| **D-SP-11 + era rule** | 1,193 | **104** | **104** | 0 | **0** |

`scripts/stage2_rulers.era_crossing_audit` re-derives every bucket-changing seam **from the
compiled row tape and the decade's own season path**, not from the engine's counters, and the
measurement script **raises** rather than reporting a number if any unlicensed crossing
exists. 323 of the batch's 5,950 month-transitions are story crossings; at **252** of them the block
was standing in the bucket the story was leaving, so the licence was live; **104** of those
found a candidate that also satisfied the 2.5 pp level bound, pool membership, the severity
stratum and the factor tolerance. The licence is a permission and not an obligation: the
ordinary same-bucket candidates stay in the pool and the path-matching pick chooses among all
of them.

The one licensed exemption is **counted, never waived**: the panel-edge forced re-entry (owner
ruling 2026-08-16) draws unfiltered when nothing matches, and can therefore change bucket with
no licence. Week C's single unfiltered re-entry is exactly that case, and it is classified as
such rather than reported as a violation. Under both post-fix engines there are no forced
re-entries at all.

`tests/test_stage2_rulers.py` pins the rule four ways: the licence predicate both ways
(crossing months license, non-crossing months do not, month 0 never does); the filter admits a
bucket change only in the licensed direction and never widens the level bound; the licence is
a superset of the platform's own filter on random inputs; and a compiled world under the rule
has zero unlicensed crossings while the D-SP-10 engine has zero crossings at all.

### 2.5 What the rule costs

| bar | D-SP-10 | D-SP-11 + era rule |
|---|---|---|
| `A1` difference | −7.5103 | **−9.6809** |
| `A2` correlation (high) | +0.0775 | **+0.0257** |
| `A2` gap | +0.2286 | **+0.1804** |
| `A2` window share | 0.6567 | **0.5960** |
| `R2` p95 | 1.1023 | **1.2102** |
| `S1` seam p95 | 2.0418 | **2.1836** |

**Every flesh bar moves against the rule, and the scoreboard count does not change.** More
reach is bought with more seams and bigger ones; the months the compiler reaches into are
increasingly the pool's own severe months, which is D-SP-10's third stop-question operating
harder. This is a frontier, mapped, not a defect.

---

## 3. Ruler 3 — `A1` re-founded

### 3.1 Why re-founding was needed

The sealed `A1` is read on one batch of fifty decades and asks only for a sign. D-SP-10's
six-seed disclosure measured what that reading is worth: across adjacent seeds the difference
swings by ±5 pp, mean **−0.9748**, sd **3.8663**, with the sealed seed landing on the fixed
engine's *worst* draw of six and the pre-fix engine's *best*. A verdict smaller than its own
seed-to-seed swing is a coin flip wearing a PASS.

### 3.2 The power calculation, at the engine's own margin

`A1`'s difference read on one fifty-decade sub-batch has a standard deviation across seeds;
read on `B` independent sub-batches and pooled, its standard error is that over `√B`. The
sub-batches are independent by construction — disjoint seeds, disjoint streams — so this
assumes nothing about months inside a decade, which are not independent.

For a two-sided test at α = 0.05 with power 0.90:

```
B  ≥  (z_0.975 + z_0.90)² · sd² / δ²  =  3.24152² · sd² / δ²
```

| against | δ (pp) | at the pilot's sd = 3.8663 | at its upper 90% bound = 6.8129 |
|---|---|---|---|
| **zero** (does the hedge pay at all?) | 0.9748 | 166 sub-batches | **514** |
| **history's +3.4933** (is it history's hedge?) | 4.4681 | 8 sub-batches | 25 |

**The adopted size is 514 sub-batches — 25,700 decades — and it is the *upper-bound* figure,
deliberately.** `B` scales with `sd²`, and the sampling distribution of `sd²` at six draws is
wide: its upper 90% chi-square bound is about three times the point estimate. Adopting the
point estimate alone would be doing a power calculation at the most flattering reading of its
own input. Achieved power at the adopted size: **0.9004**. The declared cap is 600
sub-batches and it does **not** bind.

**Runtime, stated because the charter asked.** 0.71 s to compile one fifty-decade batch with
no institutional twin attached, measured before the plan was written; the adopted ladder is
about six minutes of generation per engine.

**A cheap and useful asymmetry falls straight out of the table.** Telling this engine's hedge
from **history's** costs 25 sub-batches. Telling it from **zero** costs 514. The expensive
question is the interesting one, and nobody had bought it before.

### 3.3 The construct, sealed

* **Statistic:** `A1`'s own — commodities minus bonds, annualised, over the pooled
  high-inflation months and the pooled low-inflation months — pooled across all 25,700
  decades. Pooling uses the count-weighted identity over the **sealed judge's own**
  per-sub-batch verdicts, which is algebra rather than a re-implementation, and is
  **tested** against `judge_a1` run on the genuinely concatenated batch.
* **Seeds:** `20260821 + 15485863·k`, `k = 0 … 513`. The stride is prime, coprime with the
  platform's 7919 and with `SPINE2_ATTEMPT_STRIDE`, and larger than every layer offset — so
  `seed_i + offset_a = seed_j + offset_b` is impossible for `i ≠ j`. All 1,028 rung tapes are
  verified pairwise distinct. **Sub-batch 0 is the sealed verification seed**, so the old
  single-batch `A1` is literally the first rung of the new ladder.
* **Decision rule, declared before the measurement:** `A1R` PASSES when the two-sided 95%
  interval around the pooled difference lies **entirely above zero** *and* the pooled
  high-inflation spread sits inside `A1`'s carried containment band. Also reported and never
  the verdict: whether the interval excludes zero **in either direction**, and whether it
  excludes history's +3.4933.

### 3.4 The reading — a coin flip replaced by a verdict

| quantity | **before** (D-SP-10 engine) | **after** (D-SP-11 engine) |
|---|---|---|
| pooled difference | **−1.5448 pp** | **−3.1440 pp** |
| pooled spread, high inflation | −0.1044 pp/yr | −1.7755 pp/yr |
| pooled spread, low inflation | +1.4403 pp/yr | +1.3685 pp/yr |
| standard error | 0.1278 | 0.1311 |
| **95% interval** | **[−1.7952, −1.2943]** | **[−3.4008, −2.8871]** |
| distance from **zero** | −12.1 SE | **−24.0 SE** |
| distance from **history's +3.4933** | −39.4 SE | **−50.6 SE** |
| sub-batches with a positive difference | 156 of 514 (30.4%) | 69 of 514 (13.4%) |
| directional condition | **FAIL** | **FAIL** |
| containment condition | PASS | PASS |
| **`A1R`** | **FAIL** | **FAIL** |

**The verdict is precise and it is negative.** On both engines the inflation hedge pays
*less* in high-inflation months than in low ones, the interval excludes zero by twelve and
twenty-four standard errors, and it excludes history's +3.49 by thirty-nine and fifty-one.
There is no
seed-luck reading of that. The charter asked for a precise verdict either way; this is one.

**And the sealed seed was badly wrong about it.** Sub-batch 0 *is* the sealed verification
seed, so the old single-batch `A1` is the first rung of the ladder, and the two numbers can be
put side by side:

| | sealed single batch (50 decades) | pooled (25,700 decades) | error |
|---|---|---|---|
| D-SP-10 engine | **−7.5103** | **−1.5448** | **−5.97 pp = 47 standard errors** |
| D-SP-11 engine | **−9.6809** | **−3.1440** | **−6.54 pp = 50 standard errors** |

The sealed reading was not merely noisy: it was off by **four times the whole effect** on the
D-SP-10 engine and by **twice** it on the era-rule engine, and in both cases in the same
direction, which is what makes it a trap rather than a wobble. Every `A1` verdict in this campaign's record — the PASS at week C, the FAIL
after D-SP-10, and the six-seed disclosure that argued the flip was inside its own noise — was
a reading of a statistic whose sampling error dwarfed the thing it was measuring. **That is
the finding ruler 3 was funded to produce, and it is more important than either verdict.**

**The plan was conservative and the measurement says so.** The pilot's six-seed sd was
**3.8663**; the realised sub-batch sd over 514 draws is **2.897** (D-SP-10) and **2.971**
(D-SP-11) — the six-draw pilot overstated it by about a third, which is exactly the
uncertainty the upper-bound rule was adopted against. At the realised sd, 90% power against
the pilot's own margin would have needed **93** sub-batches, and against the *actual* margin
of −1.545 it needed **37**. The adopted 514 bought more power than it was asked for, and
declaring that is cheaper than the alternative of having bought too little.

**`A1`'s containment condition passes on both engines** (pooled high-inflation spread −0.104
and −1.776 against a band of [−5.053, +32.316]), so `A1R` fails on the directional condition
alone — which is the condition the re-founding exists to make answerable.

---

## 4. The scoreboard — old rulers and new, side by side

Read by the sealed judges, imported by name and never re-implemented. The eight pre-flesh
bars come through `stage2_weekc.spine_identity`, which **raises** unless each reproduces week
A's committed value to 1e-12; worst drift over the eight is **2.862e−13**.

| tier | bar | sealed band / floor | before (D-SP-10) | after (D-SP-11 + era rule) | verdict |
|---|---|---|---|---|---|
| causal | **T1** | [1.775283, 3.347362] | 2.239246798804 | **2.239246798804** | PASS → **PASS** |
| causal | **O1** | ≥ 0.5180669105 | 0.560824742268 | **0.560824742268** | PASS → **PASS** |
| persistence | **D1** | [0, 5] months | 2.0 | **2.0** | PASS → **PASS** |
| persistence | **D2** | [1, 7] months | 4.0 | **4.0** | PASS → **PASS** |
| persistence | **D3** | [2, 8] months | 4.0 | **4.0** | PASS → **PASS** |
| persistence | **D4** | [1, 7] months | 3.0 | **3.0** | PASS → **PASS** |
| phase | **P1** | departures ≥ 0.040330 / 0.031446 | +0.042073930959 | **+0.042073930959** | PASS → **PASS** |
| curve | **P2** | [0.391707, 0.673371] | 0.770682653481 | **0.770682653481** | FAIL → **FAIL** (above) |
| allocation | **A1** | direction; high spread in [−5.053, +32.316] | −7.510267 (dir FAIL, cont PASS) | **−9.680867** (dir FAIL, cont PASS) | FAIL → **FAIL** |
| allocation | **A2** | corr > 0; gap ≥ 0.136094; ≥ 80% of windows | +0.077493 / +0.228567 / 0.6567 | **+0.025716 / +0.180438 / 0.5960** | FAIL (1 of 3) → **FAIL (1 of 3)** |
| no-regression | **R1** | monotone coverage; ≥ 1/20 breach at 55 | medians [0.1219, 0.3785, 0.4730, 0.9225]; breach 8/20 | **[0.1211, 0.3880, 0.4888, 0.9909]; breach 10/20** | PASS → **PASS** |
| no-regression | **R2** | join ≤ 2.5 pp; p95 ≤ 0.929239 pp | 2.499733 / 1.102315 | **2.499733 / 1.210230** | FAIL (p95) → **FAIL (p95)** |
| **NEW** | **S1** | four two-sided conditions vs the panel's own bands | FAIL (texture PASS, seams FAIL, margin −6.050) | **FAIL** (texture PASS, seams FAIL, margin −6.917) | **FAIL → FAIL** |
| **NEW** | **A1R** | interval above zero; `A1`'s containment | −1.5448, CI [−1.7952, −1.2943] | **−3.1440, CI [−3.4008, −2.8871]** | **FAIL → FAIL** |

> **Eight of twelve pass before and eight of twelve pass after.** No sealed verdict flips
> under the era rule. Both new rulers return **FAIL** on both engines, so **eight of fourteen**
> pass if the new rulers are counted — and they should not be counted yet, because whether
> `S1` and `A1R` become bars is the owner's ruling, not this campaign's.

**The old rulers keep their words.** `A1`'s sealed single-batch verdict is in the table above
exactly as `judge_a1` returns it, on both engines, beside `A1R`. `R2`'s two halves are there
beside `S1`. Nothing was re-graded, and `test_both_prior_preregs_are_carried_byte_identical`
fails if either prior seal's thresholds move.

**Also reported and never a verdict.** `R1`'s disclosed hold-course depth check — D-SP-10's
fourth stop-question — is still outside its self-constructed band on both engines
(−0.5477 before, **−0.4867** after, against a shallow edge of −0.3750), so the judge's own
`overall` field remains **false** while both sealed conditions pass. The era rule made the
worlds harder again on three of the four arms: the coverage medians go 0.1219 → 0.1211
(the only one that falls, by 0.0008), 0.3785 → 0.3880, 0.4730 → 0.4888 and 0.9225 → 0.9909,
and the breach count at the 55-point arm rises **8/20 → 10/20** (it was 2/20 in round two and
4/20 at week C). That is the direction a no-regression bar exists to protect.

---

## 5. What was checked rather than asserted

- **The spine did not move.** The eight pre-flesh bars are re-judged on the era-rule batch and
  every value reproduces week A's committed artifact; `stage2_weekc.spine_identity` **raises**
  above 1e-12 and the worst drift is **2.862e−13**.
- **The engine was not refitted.** All 42 coefficients are asserted against
  `stage2-fitted-params.json` at 1e-11 before any batch is compiled; a drift is a stop.
- **Both prior records still regenerate byte-identically.** `stage2-weekc-results.json`
  (`sha256 565413ac…`) and `stage2-reach-results.json` (`sha256 bb78ff37…`) are unchanged
  after the engine edit — ruler 2's counters are stamped only on the arm that carries the
  rule, precisely so that a record does not move because a later campaign added a key.
- **This artifact regenerates byte-identically** (`sha256 045e66e5…`, two clean runs
  compared), and that claim cost a defect to make
  honestly. The first two runs of `scripts/stage2_rulers_run.py` produced files that differed,
  and the diff was **exactly two keys, both of them elapsed wall-clock seconds, and nothing
  else** — every measured number, every verdict and every band was bit-identical across the
  pair. The clock was removed from the artifact and is printed instead, and two further runs
  were compared byte for byte. A results file that carries a wall clock cannot make a
  determinism claim; the intention was there from the start and the property was not, and only
  running the check twice found that out.
- **The era rule is audited from the tape, not from the counters**, and an unlicensed crossing
  is a stop.
- **The A1R ladder's rungs have pairwise distinct tapes** — all 514, both layers.
- **The anti-tests ran before the seal** and the seal script refuses to write on a non-monotone
  sweep or a broken control.
- **Nothing inside any seal was edited.** `stage2-prereg.json` and `spine-v2-prereg.json` are
  carried whole into `stage2-prereg-2.json` and their hashes are checked by three separate
  test suites.

---

## 6. Stop-questions — OPEN owner decisions

1. **The era rule buys reach and every flesh bar pays for it.** Reach +3.05 points, agreement
   +0.72 points, 104 faithful crossings, zero unlicensed ones — and `A1` −7.51 → −9.68, `A2`'s
   correlation +0.077 → +0.026, `R2`'s p95 1.102 → 1.210, `S1`'s seam p95 2.04 → 2.18. The
   scoreboard count is unchanged, so nothing forces a choice; the choice is whether the
   ruling's own objective (conditioning that reaches the story) outranks the direction the
   bars moved. **Adopt the rule, or keep it as a measured disclosure like arm (e)?**
2. **`S1` fails on every engine in the lineage and it names a lever nobody has pulled.** Every
   seam already respects the declared 2.5 pp join bound — `R2`'s join half passes at 2.4997 on
   both engines. What fails is that among the era-safe candidates the compiler chooses without
   regard to how far inflation moves. A compiler that *preferred small-Δ joins* would move
   toward `S1`'s band without touching one declared tolerance. That is an engine change and
   this campaign's engine change was ruler 2. **Is join-selection-by-inflation-distance
   funded?**
3. **`R2`'s p95 half and `S1`'s seam half now measure overlapping things, badly.** `R2`'s p95
   pools seams and contiguous months and moves with either; `S1` separates them and says the
   seams were out of band before D-SP-10 existed. **Should `R2`'s p95 be retired in favour of
   `S1`'s seam half plus an explicit seam-frequency statement — or kept, on the grounds that a
   carried bar's whole value is that it does not move?** This is D-SP-10's first stop-question,
   now with the measurement it was missing.
4. **Do `S1` and `A1R` become bars?** They are sealed constructs with anti-tests and a power
   calculation, and both return FAIL. Promoting them makes the exam fourteen bars; leaving
   them as rulers makes them diagnostics that inform without judging. The charter funded the
   rulers and did not say which.
5. **`S1` was not cut blind, and the fix is cheap if the owner wants it.** D-SP-10 had already
   published this engine's seam and contiguous p95 before the bar was designed. The band is a
   pure function of the panel and a sample size, so the exposure is to the *choice of
   statistic*, not to the threshold. **Re-derive the statistic independently, or accept the
   disclosure?**
6. **`A1`'s sealed reading was off by 47 standard errors and every prior `A1` verdict rests on
   it.** Week C's PASS, D-SP-10's FAIL and the six-seed disclosure are all readings of a
   single fifty-decade draw whose error is two to four times the effect. Nothing is
   re-graded — the charter forbids it — but **the record should probably carry a pointer from
   each of those verdicts to this measurement.**
7. **Promotion is still not asked for.** Both the reach fix and the era rule are composed in
   `scripts/`. Promoting `_reach_draw` or `_era_crossing_licence` into `ah/gen/spine.py` is a
   separate owner release event and this campaign does not ask for it.

---

## 7. Limitations

- **`S1` was not cut blind.** D-SP-10's results document had already published this engine's
  seam and contiguous p95 (1.9143 and 0.6956 against a panel p95 of 0.7434) before the bar was
  designed. The band is nonetheless a pure function of the panel and of a sample size, and
  both sweep endpoints are fixed by the construction rather than chosen — but a reader should
  know the designer knew the answer.
- **De-duplication is a judgement call.** It removes a repetition artefact that would shrink
  the band far below the panel's own resolution; it also makes `S1` blind to a world that uses
  one bad seam five hundred times. `R2` sees that world and `S1` does not, which is why both
  are reported.
- **The 24-month block is the campaign's primary length, not a length fitted to `|ΔYoY|`'s own
  dependence.** It is conservative — wider bands, more forgiving — and its adequacy is not
  measured.
- **The era licence fires only where the spine crosses, and the spine crosses rarely.** The
  rule can buy only a bounded amount of reach; the residual gap stays what D-SP-10 measured
  it to be.
- **`A1R`'s power calculation takes its variance at the upper bound but its effect at the
  point estimate.** If the engine's true margin had been nearer zero than −0.97, the adopted
  batch would have been under-powered and the honest reading would have been "cannot
  distinguish", not "no effect". In the event the margin came out *larger* than the pilot's
  and the variance *smaller*, so the plan was conservative twice over — but that is luck about
  which way the pilot erred, not a property of the method.
- **`A1R` is a verdict about this engine on this panel, and it is not a statement about
  inflation hedging.** The pooled difference is negative because the compiler draws its months
  from the worst third of the panel by the `all_down` severity functional, where bonds win;
  25,700 decades measure that selection effect very precisely and do not make it a fact about
  commodities.
- **`A1R` inherits every one of `A1`'s own problems.** D-SP-10's third stop-question stands
  untouched: history's high-inflation months pay +4.87 pp/yr on commodities-minus-bonds while
  the worst-10% `all_down` pool's high-inflation months pay −8.52. A precise verdict on a bar
  whose content is thin is still a verdict about a thin bar.
- **Nothing here reaches the private book.** ER-14 stands.
- **The standing caveat carries.** Nothing built on this generator line is a convincing model
  of history, the holdout is spent, and no appeal to held-out data is available.
