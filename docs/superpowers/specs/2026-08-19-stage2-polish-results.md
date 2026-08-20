# D-SP-12 — the polish round: three changes, and the whole exam read on them

**Date:** 2026-08-19 · **Branch:** `stage2-05-polish` · **Status: measured, no owner
ruling taken.** Charter: `governance/decision-register.md` **D-SP-12** (2026-08-19, *"let us
do 1–3"*) — join selection by inflation distance, the conditional era-crossing rule adopted,
and the slow climate's dispersion recalibrated.

**What this document is.** The record of three engine changes and the sealed exam re-read on
them. Every number below is produced by `scripts/stage2_polish_run.py` and lives in
`docs/superpowers/specs/stage2-polish-results.json` (`sha256 e20a621c…`, byte-identical across
two clean runs, LF endings so the file on disk is the blob git stores); the calibration's
derivation lives in `docs/superpowers/specs/stage2-fitted-params-2.json` (`sha256 44244e7b…`,
also byte-identical across two clean runs).
Every PASS/FAIL word is the sealed judge's own.

**No file inside any of the three seals was edited, no threshold was moved, no amendment was
added, and no line of `src/` or `schemas/` was changed.** The engine changes are installed as
*substitutions around* the sealed code rather than as edits into it — `scripts/stage2_worlds.py`
is hashed by `stage2-prereg-2.json` as the era rule's implementation, so editing it would have
required an amendment, and an amendment is an edit to a sealed file. The consequence worth
stating: **the era rule that ran is still the sealed one**, `stage2_worlds._era_crossing_licence`,
not a copy of it that could drift.

---

## The one-paragraph answer

**The join fix works, the recalibration works, and the round costs one bar's failure mode.**
Choosing the smallest-inflation-gap candidate among the ones the compiler already admits moves
the seam median from **0.687 to 0.239 — inside its band** — and drops the seam detectability
statistic from **0.486 to 0.227, below its own null of 0.264**: a jump-threshold detector can no
longer find the splices. Recalibrating the slow climate's two level-carrying volatilities against
the panel's own decade-scale spread flips **`P2` FAIL → PASS** (0.7707 → 0.5453, inside
[0.3917, 0.6734]) and, unexpectedly, *raises* conditioning reach **80.7% → 83.7%** and raw dial
agreement **78.6% → 80.9%**, because a spine that demands less extreme inflation is a spine real
history can actually track (the excess *over chance* falls, and §6 says why).
**`A1R` improves by a factor of three** (−3.144 → −0.912 pp) and
**`A1` by three points** (−9.68 → −6.66). The scoreboard goes **8 of 12 to 9 of 12**: `P2` flips
up and nothing flips down. But **`S1` still FAILS**, on one of its four conditions — the seam
*p95* — and the reason is change 2: **59% of the seams above that cut are licensed era
crossings**, which are large-inflation-jump seams by construction. And **`R2`'s failure changes
character**: its p95 half is cured (1.210 → 0.846, inside the 0.929 bound) and its join half
breaks on **a single unfiltered forced re-entry at the panel's edge** (11.77 pp in 6,000 months;
the largest *ordinary* join is 2.480, inside the bound). Two changes pull against each other and
the frontier is mapped, not tuned past. Separately and not this round's doing: **`R1` could not
be measured at all**, because a platform change merged into `main` this morning broke a sealed
harness.

---

## 1. The three changes, and where they live

| # | change | mechanism | where |
|---|---|---|---|
| **1** | **join selection by inflation distance** | among the era-safe candidates that tie at the longest matching forward path, take the one whose `\|ΔYoY\|` at the seam is smallest; ties to the **earliest panel row** | `stage2_polish.SELECTION_MIN_GAP` |
| **2** | **the conditional era-crossing rule ADOPTED** | D-SP-11's sealed design, promoted from "an arm the run script names" to the default the run entry point carries | `stage2_polish.POLISH_REACH` |
| **3** | **the slow climate's dispersion recalibrated** | L1's `sigma_pi` × **0.653298** and `sigma_r` × **0.412113**, derived against the panel's own decade-scale spread | `stage2-fitted-params-2.json` |

**No declared tolerance moved.** The pool, both join filters, the severity stratum, the factor
tolerance, the declared 2.5 pp level bound, the block length, the premise rule and the
forced-re-entry rule are all exactly what they were. Change 1 decides *which* of the admitted
candidates is taken and nothing about *who* is admitted.

**The random tape did not move under change 1.** The platform draws one uniform among the
candidates tied at the longest forward path; the polish rule computes the same tie set, draws the
same uniform from the same range, discards it, and takes the minimum-gap member. So the block
stream is consumed at the same rate at the same points, and the join-selection arm differs from
D-SP-11's **only** in which tied candidate is taken. (Change 3 does move the spine — that is what
it is for.)

---

## 2. Change 1 and `S1` — the round's headline

### 2.1 The reading

| condition | band | D-SP-11 | **+ join selection** | **POLISHED** |
|---|---|---|---|---|
| texture q50 | ≈[0.190, 0.274] | 0.2150 ✓ | 0.2142 ✓ | **0.2242 ✓** |
| texture q95 | ≈[0.638, 0.845] | 0.7597 ✓ | 0.7097 ✓ | **0.7679 ✓** |
| **seam q50** | ≈[0.189, 0.275] | **0.6868 ✗** | **0.2747 ✓** | **0.2390 ✓** |
| **seam q95** | ≈[0.622, 0.846] | **2.1836 ✗** | **2.0649 ✗** | **2.0972 ✗** |
| **`S1`** | all four | **FAIL** (−6.9168) | **FAIL** (−5.5699) | **FAIL** (−5.5864) |

(Bands are re-cut for each arm at that arm's own transition count, which is what the sealed rule
says to do; they move by a percent or two between arms for that reason alone.)

**Three of four conditions now hold where two did.** The seam median — the number a detector
tunes against — moves from **2.5× outside its band to inside it**, and the two texture
conditions never moved.

### 2.2 Does the join fix make the seams undetectable? On the disclosure that asks directly, yes

`S1` carries a detectability disclosure: the Kolmogorov–Smirnov distance between the seam-jump
distribution and history's own adjacent-jump distribution, which **is** the best possible
jump-threshold detector's advantage over guessing, with its own null band beside it.

| arm | KS(seam, history) | its null p95 | verdict of the disclosure |
|---|---|---|---|
| week-C baseline (from D-SP-11's record) | 0.4556 | 0.3045 | findable |
| D-SP-10 adopted (from D-SP-11's record) | 0.4530 | 0.2251 | findable |
| **D-SP-11 + era rule** | **0.4860** | 0.2142 | findable |
| **+ join selection** | **0.2207** | 0.2671 | **not findable** |
| **POLISHED** | **0.2265** | 0.2640 | **not findable** |

**For the first time in the lineage the seam statistic sits inside its own sampling null.** A
jump-threshold detector run on a polished world has no advantage over guessing that the world's
own sample size does not explain.

**And `S1` still fails.** The bar is stated at declared quantiles, two-sided, all four judged —
and the seam p95 is 2.10 against an upper edge of 0.85. The disclosure and the bar disagree
because they read different things: the KS statistic is a whole-distribution comparison in which
a 5% tail is worth at most five points, and the bar asks the tail itself to sit inside history's.
**Both are reported and neither is adjusted.** The honest sentence is: *the seams are no longer
findable by the detector `S1`'s own disclosure describes, and the seam tail is still outside the
band `S1` judges.*

### 2.3 Where the surviving tail comes from — and it is change 2

Splitting the distinct seam pairs by whether the seam crossed the era line:

| arm | seams that crossed | their median | their p95 | same-bucket median | same-bucket p95 | share of the top 5% that crossed |
|---|---|---|---|---|---|---|
| D-SP-11 | 92 of 783 (11.7%) | 1.7502 | 2.4379 | 0.6182 | 1.9603 | **57.5%** |
| **POLISHED** | 78 of 517 (15.1%) | 1.1987 | 2.3358 | **0.1873** | 1.8407 | **59.3%** |

**Change 1 did what it was funded to do and change 2 supplies what is left.** The same-bucket
seams — the ones min-gap selection can actually choose — have a median of **0.187**, deep inside
history's own. The licensed era crossings cannot be made small: crossing the inflation line
means moving trailing inflation across a 3.35 pp threshold, so a licensed crossing is a
large-`|ΔYoY|` seam **by construction**, and 59% of the seams above the p95 cut are exactly
those. Adopting the era rule and passing `S1`'s seam tail are, on this panel, close to mutually
exclusive.

**This is a frontier and it is left where it is.** No construct was changed, the p95 quantile was
not moved, and the era rule was not weakened to reach a bar.

### 2.4 The gap-only disclosure arm — the two-sided bar biting from below

The arm that ignores the forward-path score and lets inflation distance decide among **all**
era-safe candidates is measured and **never adopted**:

| quantity | POLISHED | gap-only (disclosure) |
|---|---|---|
| seam q50 | 0.2390 ✓ | **0.1750 ✗ — below the band** |
| seam q95 | 2.0972 | 1.8831 |
| KS(seam, history) | 0.2265 | 0.1596 |
| seams | 1,139 | 1,630 |
| `A1` difference | −6.6598 | **−13.2370** |
| `A1` containment | PASS | **FAIL** (−10.16 outside [−5.053, +32.316]) |
| dial agreement | 0.8085 | 0.7937 |

**`S1`'s lower edge bites exactly where the design note said it would.** A compiler that only
ever joins near-identical rows has seams that are findable *by being unnaturally smooth*, and it
has stopped conditioning: the arm's seam median falls out of the band from below, its `A1`
containment half — which has passed on every engine in this campaign — breaks, and its dial
agreement falls. This is the measurement that says the adopted rule broke a **tie** rather than
replacing the forward-path score, and why.

---

## 3. Change 2 — the era rule adopted, and its audit retaken

The rule itself does not move. What this round adds is that the licence audit is **retaken on
every arm** rather than inherited: change 1 alters which candidate is taken at a crossing month,
so D-SP-11's 104-of-104 reading is not a property of the polished engine.

| arm | bucket-changing seams | at a story crossing, in the story's direction | **unlicensed** |
|---|---|---|---|
| D-SP-11 (recompiled here) | 104 | 104 | **0** |
| + join selection | 89 | 89 | **0** |
| + L1 recalibration | 84 | 84 | **0** |
| **POLISHED** | **92** | **92** | **0** |
| gap-only (disclosure) | 135 | 135 | **0** |

Every one re-derived from the compiled row tape by the sealed
`stage2_rulers.era_crossing_audit`, and an unlicensed crossing **raises** rather than being
reported. The counts differ between arms because the licence is a permission and not an
obligation — a different pick among the same admitted candidates takes a different number of the
crossings on offer.

---

## 4. Change 3 — the slow climate, diagnosed and recalibrated

### 4.1 The prior diagnosis does not hold

`2026-08-18-stage2-results.md` §2.2 attributed the 1.635× / 1.735× over-dispersion to L1's
per-decade posterior redraw: *"fifty decades each re-draw their initial states from the
posterior, and the spread of L1's `r*` and `pi*` across those draws is wider than the single
68-year path history realised."* Measured directly:

| arm | generated `i_rule` total sd |
|---|---|
| the engine as it stands | **5.6839** |
| the drawn initial state `s0` pinned to the posterior mean | **5.6903** |
| `s0` **and** `mu_pi`, `mu_r` pinned to the posterior mean | **5.5814** |

**Removing the posterior spread entirely leaves the over-dispersion essentially untouched.** The
smoother is sharp at the last month of the fit span, so there is almost no posterior spread in
the state there to remove.

**It is the diffusion.** `pi*` has a fitted half-life of 10.7 years at an innovation volatility of
2.68 pp and `r*` 7.8 years at 2.16 pp, so over a 120-month decade both states wander far further
than the panel's own two states did — and different decades wander to different places, which is
what an across-decade spread reads. The attribution arms, on the 200-decade calibration batch:

| arm | `pi*` across-decade sd | `r*` across-decade sd | `i_rule` total sd | `P2` share |
|---|---|---|---|---|
| unrecalibrated | 3.7417 | 2.9179 | 6.0536 | 0.7919 |
| `sigma_pi` = 0 | **0.5460** | 2.9179 | 3.7689 | 0.5981 |
| `sigma_r` = 0 | 3.7417 | **0.5538** | 4.8817 | 0.7129 |
| both = 0 | 0.5460 | 0.5538 | 1.0336 | 0.1156 |

### 4.2 The target — a measured historical quantity, not a bar

**Target:** the panel's own across-decade standard deviation of `pi*` and of `r*` — the standard
deviation of the six non-overlapping 120-month decade means, on the **same posterior-mean smoothed
path `M4` decomposes history's curve on**.

| state | history's across-decade sd | history's within-decade sd | history's total sd |
|---|---|---|---|
| `pi*` | **2.4726** | 1.5175 | 2.7182 |
| `r*` | **1.3339** | 1.8381 | 2.2000 |
| `i_rule` | 2.8976 | 2.1424 | 3.4006 — *reported, never targeted* |

**`P2`'s band appears nowhere in the estimator.** The target is a property of the panel, it was
measured before the bar was read, and it does not mention a bar.

### 4.3 The estimator, exactly

Write `S(k)` for the generated across-decade spread of a state when its innovation volatility is
scaled by `k`. Two components add in variance — a floor `F` that survives `k = 0` (decades still
differ in their drawn `mu` and `s0`) and a diffusion term proportional to `k`:

```
S(k)^2 = F^2 + k^2 (S(1)^2 − F^2)      →      k = sqrt(max(T^2 − F^2, 0)) / sqrt(S(1)^2 − F^2)
```

`F` and `S(1)` are measured on a **declared calibration batch** — seed **20260819** (the ruling's
own date), **200 decades**, deliberately *not* the exam's seed and batch, because reading the
target on the batch the bars are read on would be in-sample against its own verification. The
relation is exact only for an isolated state and these two are not isolated (`r*` carries
`beta_g` times growth's innovation), so the declared rule is: **apply, re-measure, at most two
closed-form steps, 2% relative tolerance, every step recorded.**

| step | `sigma_pi` | `sigma_r` | achieved `pi*` | achieved `r*` | relative error | inside tolerance |
|---|---|---|---|---|---|---|
| 1 | 0.651501 | 0.423571 | 2.4662 | 1.3646 | −0.26% / **+2.31%** | no |
| **2 (adopted)** | **0.653298** | **0.412113** | **2.4727** | **1.3353** | +0.002% / +0.11% | **yes** |

Both steps were taken and both are in the artifact. The `r*` factor is the one that needed the
second step, because `r*` is the state the relation is least exact for.

### 4.4 What it bought, and the response curve that shows it was not aimed at a bar

On the calibration batch, `i_rule`'s total sd goes **6.0536 → 3.6016** against history's
**3.4006** — 5.9% high, and *not targeted*. The economic share follows:

| uniform scale on both sigmas | `i_rule` total sd | `P2` economic share |
|---|---|---|
| 1.00 | 6.0536 | 0.7919 |
| 0.90 | 5.4678 | 0.7566 |
| 0.80 | 4.8838 | 0.7130 |
| **0.70** | 4.3051 | **0.6593** — *the band's upper edge is 0.6734* |
| 0.60 | 3.7295 | 0.5931 |
| 0.50 | 3.1642 | 0.5134 |
| 0.40 | 2.6111 | 0.4203 |
| 0.25 | 1.8266 | 0.2675 — *below the band* |

The band `[0.3917, 0.6734]` is cleared anywhere from about 0.42 to 0.72 on this axis. The adopted
point sits at (0.653, 0.412), which is where the **historical target** puts it — not at the
middle of the pass region and not at its widest point. A reader who wants to check that the
calibration was not aimed at the band can read this column.

---

## 5. The scoreboard — fourteen lines, before and after

**Before** is the D-SP-11 engine (the era rule with the platform's join selection), recompiled
here and checked field by field against `stage2-rulers-results.json` — **max drift 0.0 on every
one of `A1`, `A2`, `R2`**, so the comparison is between two engines and not between two
harnesses. **After** is the polished engine. Read by the sealed judges, imported by name.

| tier | bar | sealed band / floor | **before** (D-SP-11) | **after** (polished) | verdict |
|---|---|---|---|---|---|
| causal | **T1** | [1.775283, 3.347362] | 2.239246798804 | **2.677702044791** | PASS → **PASS** |
| causal | **O1** | ≥ 0.5180669105 | 0.560824742268 | **0.543529411765** | PASS → **PASS** |
| persistence | **D1** | [0, 5] months | 2.0 | **2.0** | PASS → **PASS** |
| persistence | **D2** | [1, 7] months | 4.0 | **4.0** | PASS → **PASS** |
| persistence | **D3** | [2, 8] months | 4.0 | **4.0** | PASS → **PASS** |
| persistence | **D4** | [1, 7] months | 3.0 | **3.0** | PASS → **PASS** |
| phase | **P1** | binding margin ≥ 0 | +0.042073930959 | **+0.028601177818** | PASS → **PASS** |
| curve | **P2** | [0.391707, 0.673371] | 0.770682653481 (above) | **0.545257832482** | **FAIL → PASS** |
| allocation | **A1** | direction; high spread in [−5.053, +32.316] | −9.680867 (dir FAIL, cont PASS) | **−6.659750** (dir FAIL, cont PASS) | FAIL → **FAIL** |
| allocation | **A2** | corr > 0; gap ≥ 0.136094; ≥ 80% of windows | +0.025716 / +0.180438 / 0.5960 | **+0.040926 / +0.155564 / 0.6099** | FAIL (1 of 3) → **FAIL (1 of 3)** |
| no-regression | **R1** | monotone coverage; ≥ 1/20 breach at 55 | medians [0.1211, 0.3880, 0.4888, 0.9909]; breach 10/20 → PASS | **NOT MEASURED** — see §5.2 | PASS → **carried** |
| no-regression | **R2** | join ≤ 2.5 pp; p95 ≤ 0.929239 pp | 2.499733 / **1.210230** | **11.770689** / 0.846247 | FAIL (p95) → **FAIL (join)** |
| ruler | **S1** | four two-sided conditions | FAIL, margin −6.9168 (seams 2 of 2 outside) | **FAIL, margin −5.5864** (seams 1 of 2 outside) | FAIL → **FAIL** |
| ruler | **A1R** | interval above zero; `A1`'s containment | −3.1440, CI [−3.4008, −2.8871] | **−0.9115, CI [−1.2349, −0.5882]** | FAIL → **FAIL** |

> **Eight of twelve passed before; nine of twelve pass after** (counting `R1`'s carried verdict).
> **`P2` flips up and nothing flips down.** Counting the two rulers as well: **8 of 14 → 9 of 14.**
> `R2` was already failing and still fails — but on the other half, which is a different fact
> and is characterised in §5.1 rather than netted out.

### 5.1 `R2` — the p95 half is cured and the join half breaks on one event

| half | bound | before | after |
|---|---|---|---|
| largest jump at a seam | ≤ 2.5 pp | 2.499733 **PASS** | **11.770689 FAIL** |
| p95 adjacent-month change | ≤ 0.929239 pp | **1.210230 FAIL** | **0.846247 PASS** |
| seams | — | 1,193 | 1,139 |
| forced re-entries / of which unfiltered | — | 0 / 0 | **1 / 1** |
| largest jump at an **ordinary** join | — | 2.499733 | **2.480125** |

**The whole join-half failure is one seam in 6,000 months.** `stage2_weekc.r2_diagnostics`
attributes it exactly: a forced re-entry at the panel's last row, where no candidate matched and
the owner's 2026-08-16 rule draws **unfiltered**. Every ordinary join is still inside the declared
bound with room. This is precisely the failure D-SP-10 cured by making panel-edge blocks
unattractive to enter, and **change 3 brings it back on its own arm** — a recalibrated spine
reaches further into the panel, so blocks run to its end more often: the L1-only arm has two
unfiltered re-entries and reads 2.8302, already outside the bound. The join-selection arm has two
forced re-entries and *no* unfiltered ones and `R2` **passes** on it (2.489681 / 0.857568). So
the join half is change 3's cost, and the combination changes the size of the single surviving
event rather than the number of them.

**And the p95 half is genuinely cured, not traded.** 1.210 → 0.846 against a 0.929 bound, with
*fewer* seams than before — the contiguous months were never the problem and the seams got
smaller.

### 5.2 `R1` — not measured, and the reason is not this round

`R1`'s byte-frozen b3 ladder **does not run on this repository state**. `ah.play.PRIVATE_ASSETS`
gained a fourth private sleeve, `infra` (`er14-04b`/`er14-05`, merged into `main` on 2026-08-19),
while `scripts/spine_pilot_b3.py` still declares its book over `pe`/`pc`/`re` only, so
`ah.play._build_portfolio` raises `KeyError: 'infra'` on the first rung.

Neither repair is available under this charter: `spine_pilot_b3.py` is **hashed by
`spine-v2-prereg.json`**, so editing it is a sealed-file change; adding `infra` to the declared
book is a **construct change**. The attempt is made by the run script, the exception is recorded
verbatim in the artifact, and `R1`'s D-SP-11 verdict is carried. **This also means
`stage2-rulers-results.json`'s own `R1` block no longer regenerates on today's `main`** — the
breakage is older than this round and reaches backwards. It is §9's first stop-question.

### 5.3 `A1` and `A1R` — the biggest move on the flesh, and still a FAIL

| quantity | before (D-SP-11) | after (polished) | history |
|---|---|---|---|
| `A1` spread, high inflation | −5.0444 pp/yr | **−3.9058** | +4.8720 |
| `A1` spread, low inflation | +4.6365 pp/yr | **+2.7540** | +1.3787 |
| **`A1` difference** | **−9.6809** | **−6.6598** | +3.4933 |
| **`A1R` pooled difference** (25,700 decades) | **−3.1440** | **−0.9115** | +3.4933 |
| `A1R` 95% interval | [−3.4008, −2.8871] | **[−1.2349, −0.5882]** | — |
| `A1R` distance from zero | −24.0 SE | **−5.53 SE** | — |
| sub-batches with a positive difference | 69 of 514 (13.4%) | **192 of 514 (37.4%)** | — |

**The pooled inflation-hedge margin moves two-thirds of the way to zero and still excludes it.**
`A1R`'s directional condition fails; its containment condition passes (pooled high spread −0.760
inside [−5.053, +32.316]). The `A1R` reading for the D-SP-11 engine is **carried from the
committed rulers artifact** rather than recomputed — that artifact is the record and re-running
25,700 decades to re-derive a committed number buys nothing.

### 5.4 `A2` — unchanged in verdict, better in two of three, worse in one

| condition | required | before | after | drawn-months disclosure (after) |
|---|---|---|---|---|
| correlation, high inflation | > 0 | +0.025716 PASS | **+0.040926 PASS** | +0.263909 |
| difference, high − low | ≥ 0.136094 | +0.180438 PASS | **+0.155564 PASS** | +0.438086 |
| share of 3-year windows positive | ≥ 0.80 | 0.5960 FAIL | **0.6099 FAIL** | **0.922438** |

The disclosure arm — `A2` judged on the inflation the drawn months actually carried rather than
on the spine's — **passes all three with room, and its window share rises 0.870 → 0.922.** The
months this compiler selects carry history's stock–bond flip; what is missing is still the link
between the story's dial and the months selected, and 16% of that link is still absent.

### 5.5 The eight spine bars moved, and that is change 3 working

`stage2_weekc.spine_identity` **raises** unless the eight pre-flesh bars reproduce week A to
1e-12. It is still asserted on every arm whose slow climate is unrecalibrated — the before arm
reproduces week A at **drift 0.0** — and it **cannot** be asserted on a recalibrated arm, because
change 3 moves the spine deliberately. On those arms the eight are re-judged and reported:

| bar | week A | polished | drift | verdict |
|---|---|---|---|---|
| T1 | 2.239247 | 2.677702 | 0.438455 | PASS → PASS (further into the band) |
| O1 | 0.560825 | 0.543529 | 0.017295 | PASS → PASS (floor 0.518067) |
| D1–D4 | 2 / 4 / 4 / 3 | 2 / 4 / 4 / 3 | 0.0 | PASS → PASS |
| P1 | +0.042074 | +0.028601 | 0.013473 | PASS → PASS (**a third of the margin gone**) |
| P2 | 0.770683 | 0.545258 | 0.225425 | **FAIL → PASS** |

**`P1`'s headroom is the price nobody asked about.** Its binding margin — the smaller of the two
move types' (departure − threshold) — falls by a third. It still passes, and it is now the bar
closest to flipping.

**The 42 stage-2 coefficients did not move.** `build_frozen_system` re-runs week A's estimator and
checks every one against the frozen artifact before any batch is compiled; **max drift 0.0 over
42 numbers**. Nothing in this round refits a stage-2 parameter.

---

## 6. Reach, agreement, and the surprise

| quantity | week-C | D-SP-10 | D-SP-11 | + join sel. | + L1 recal. | **POLISHED** |
|---|---|---|---|---|---|---|
| **conditioning reach** | 0.4785 | 0.7763 | 0.8068 | 0.7903 | 0.8405 | **0.8365** |
| **dial agreement** | 0.6059 | 0.7783 | 0.7856 | 0.7643 | 0.8213 | **0.8085** |
| agreement if the dials were independent | 0.5916 | 0.6051 | 0.6054 | 0.6078 | 0.6652 | **0.6674** |
| **excess over chance** | +1.43 pp | +17.32 | +18.02 | +15.64 | +15.61 | **+14.11** |
| seams | 444 | 1,162 | 1,193 | 1,122 | 1,160 | **1,139** |
| unresolved divergences | — | 1,342 | 1,159 | 1,258 | 957 | **981** |
| anticipating moves | — | 314 | 210 | 233 | 184 | **216** |
| forced re-entries / unfiltered | 1 / 1 | 0 / 0 | 0 / 0 | 2 / 0 | 2 / 2 | **1 / 1** |

**The recalibration buys reach, and nobody predicted that.** Change 3 was funded to fix `P2` and
it raised conditioning reach by 3.4 points and raw agreement by 3.6 — more than the whole era
rule bought. The mechanism is straightforward once seen: an over-dispersed slow climate demands
inflation quadrants the panel's 813 real rows cannot supply, and shrinking that demand to
history's own scale makes the story trackable. **Unresolved divergences fall 1,159 → 981.**

**And the excess over chance falls anyway, which is the honest reading of the same table.** A
recalibrated spine crosses the era line less often, so its inflation dial is more concentrated,
so two *independent* dials would agree 66.7% of the time instead of 60.5%. Raw agreement rises
2.3 points and the baseline rises 6.2, and the excess therefore goes **+18.02 → +14.11 pp**.
Reach — which counts months whose drawn row carries the spine's own quadrant, and has no such
baseline — is unambiguous at **+3.0 points**. **Both are reported and the excess is the more
conservative of the two.**

**Change 1 costs 1.6 points of reach and 2.1 of raw agreement**, because the minimum-gap
candidate is not always the one that tracks the story furthest — it is chosen among the ties, and
ties are common but not universal. That is the price of change 1, stated as a number.

---

## 7. The frontier — what each change helps and what it breaks

Every cell is a real arm on the same batch, not a decomposition on paper. "alone" means that
change applied to the D-SP-11 engine and nothing else.

| quantity | D-SP-11 | **change 1 alone** | **change 3 alone** | **POLISHED (1+2+3)** |
|---|---|---|---|---|
| `S1` seam q50 | 0.6868 ✗ | **0.2747 ✓** | 0.6411 ✗ | **0.2390 ✓** |
| `S1` seam q95 | 2.1836 ✗ | 2.0649 ✗ | 2.2087 ✗ | 2.0972 ✗ |
| `S1` binding margin | −6.9168 | **−5.5699** | **−7.9057** | −5.5864 |
| KS(seam, history) / its null | 0.4860 / 0.2142 | **0.2207 / 0.2671** | 0.4455 / 0.2245 | **0.2265 / 0.2640** |
| `R2` join half | 2.4997 ✓ | 2.4897 ✓ | **2.8302 ✗** | **11.7707 ✗** |
| `R2` p95 half | 1.2102 ✗ | **0.8576 ✓** | 1.2016 ✗ | **0.8462 ✓** |
| `P2` | 0.7707 ✗ | 0.7707 ✗ | **0.5453 ✓** | **0.5453 ✓** |
| `P1` binding margin | +0.0421 | +0.0421 | **+0.0286** | **+0.0286** |
| `A1` difference | −9.6809 | **−4.3075** | −6.7559 | −6.6598 |
| conditioning reach | 0.8068 | 0.7903 | **0.8405** | 0.8365 |
| raw dial agreement | 0.7856 | 0.7643 | **0.8213** | 0.8085 |

**The four things this table says, and none of them was tuned past.**

1. **Change 1 owns `S1`'s seam median and `R2`'s p95 half.** Both flip on its arm alone, and
   change 3 moves neither.
2. **Change 3 owns `P2`, reach and agreement — and it breaks `R2`'s join half by itself**
   (2.8302, from two unfiltered panel-edge re-entries where D-SP-11 had none). The combination
   makes that one event larger, not more frequent: 11.7707 at a single seam.
3. **Change 2 is why `S1` still fails.** 59% of the seams above the p95 cut are licensed era
   crossings, which cannot be small.
4. **The two improvements to `A1` do not add.** +5.37 pp from change 1 alone and +2.93 pp from
   change 3 alone give +3.02 pp together, because both work through the same mechanism — which
   months the compiler ends up drawing from the severity pool — and they overlap.

---

## 8. What was checked rather than asserted

- **No sealed file was edited and no amendment was added.** `tests/test_stage2_seal.py`,
  `tests/test_stage2_rulers_seal.py` and `tests/test_spine_v2_seal.py` all pass, which means every
  hashed file — including `scripts/stage2_worlds.py` — still matches its sealed hash byte for
  byte. The engine changes are substitutions installed around that code, not edits into it.
- **The before arm reproduces the committed D-SP-11 record**, field by field, at **drift 0.0** on
  `A1`, `A2` and `R2`. A drift is a stop.
- **The engine was not refitted.** All 42 week-A coefficients are checked against
  `stage2-fitted-params.json` at 1e-11 before any batch is compiled; **max drift 0.0**.
- **The frozen params artifact was never written.** The recalibration went into a new versioned
  file, `stage2-fitted-params-2.json`, which carries week A's 42 coefficients by value — and a
  test asserts they equal the frozen artifact's.
- **The join-selection substitution is inert where it should be**, and that is a comparison
  rather than a claim: `SELECTION_PLATFORM` inside the context draws exactly what the platform
  draws outside it, and the identity guard keeps the rule off the two call sites that are not
  joins (month 0 and the unfiltered panel-edge fallback).
- **The L1 substitution is bit-identical to the platform's at unit scale**, so every difference
  measured is the calibration and not the copy.
- **Only the two declared L1 volatilities move.** A test compares every other posterior parameter
  array element by element.
- **The era licence is audited from the tape on every arm**, and an unlicensed crossing raises.
  Retaken, not inherited.
- **Both artifacts regenerate byte-identically** across two clean runs
  (`stage2-polish-results.json` and `stage2-fitted-params-2.json`), written with LF endings so the
  file on disk is the blob git stores. Neither carries a wall clock — D-SP-11's own determinism
  incident, not repeated.
- **`R1`'s failure was reproduced and recorded verbatim**, not summarised.

---

## 9. Stop-questions — OPEN owner decisions

1. **A sealed harness no longer runs against `src/`.** `spine_pilot_b3.py` is hashed by
   `spine-v2-prereg.json` and declares a three-sleeve private book; `ah.play.PRIVATE_ASSETS` now
   has four. `R1` cannot be measured by anyone, this round or any other, and
   `stage2-rulers-results.json`'s `R1` block no longer regenerates. **The repair is either an
   amendment to `spine-v2-prereg.json` naming `spine_pilot_b3.py` (a protocol change), or a
   platform-side compatibility shim, or a ruling that `R1` is retired.** All three are the
   owner's, and until one is taken the exam has eleven measurable bars, not twelve.
2. **`S1` fails on one condition and the era rule is why.** Three of four conditions now hold and
   the detectability disclosure sits inside its own null; the seam p95 is out because 59% of that
   tail is licensed era crossings, which are large-jump seams by construction. **Is `S1`'s seam
   p95 the right statement of "you cannot find the seams" when the compiler is licensed to cross
   the inflation line — or does adopting change 2 mean accepting that `S1`'s tail condition is
   unreachable?** Nothing was changed to resolve this.
3. **`R2`'s join half now fails on one unfiltered panel-edge re-entry in 6,000 months**, and
   change 3 is what brought it back (2.8302 on the L1-only arm, 11.7707 combined). The ordinary
   joins max at 2.480. The owner's 2026-08-16 forced-re-entry rule is what draws unfiltered, and
   D-SP-10 cured this failure by accident — by making panel-edge blocks unattractive — rather
   than by rule, so any change that reaches further into the panel can undo the cure. **Is a bar
   that a single rare event flips carrying the meaning it was written for, or does the panel-edge
   rule need a bound of its own?**
4. **`P1`'s margin lost a third of itself to change 3** (+0.0421 → +0.0286) and is now the
   closest bar to flipping. It was not measured before because nothing had moved the spine. **Is
   that an acceptable price for `P2`, and should the next round measure `P1`'s sensitivity to the
   calibration before anything else moves the slow climate?**
5. **The recalibration is a scaling of an L1 posterior parameter, not a refit of L1.** It brings
   the generated decade-scale spread to the panel's own, and part of what it absorbs is the
   difference between a *smoothed posterior-mean estimate* and a *simulated forward path* — which
   is a real modelling gap, not a parameter error. **Should the L1 layer be refitted with this
   target in it, or does stage 2 keep applying a scaling on top of a frozen posterior and
   declaring it?**
6. **The recalibration bought more conditioning reach than the era rule did.** 80.7% → 84.1% on
   its own arm, raw agreement 78.6% → 82.1%, unresolved divergences 1,159 → 957. That was not the
   change's purpose. (Its excess-over-chance *falls*, because the recalibrated dial is more
   concentrated and the independence baseline rises with it — §6.) **Does the reach deficit get
   re-read as a slow-climate problem rather than a compiler problem?** D-SP-10's whole frontier
   was searched on the compiler.
7. **Promotion is still not asked for.** All three changes are composed in `scripts/`. Promoting
   any of them into `ah/gen/` is a separate owner release event and this round does not ask for
   it.

---

## 10. Limitations

- **The engine changes are substitutions over a sealed module.** They are pinned by tests that
  demand bit-identity where they are meant to be inert, and the sealed era rule's own code is what
  runs — but a substitution is a heavier device than an edit, and it exists because the D-SP-11
  seal hashed the engine file. A future round that wants to edit `stage2_worlds.py` needs an
  amendment and should take one deliberately rather than inherit this workaround.
- **The calibration target's own uncertainty is unquantified.** It rests on six non-overlapping
  decades of one 68-year panel, and no usable sampling band exists for it: the 24-month
  moving-block bootstrap the campaign uses elsewhere returns [0.43, 1.83] for `pi*` against the
  panel's own 2.47, because reassembling the path out of two-year blocks destroys exactly the long
  persistence (the 1970s-to-1990s level shift) the target is made of. That resampling is published
  as a **null**, not as a band, and the two factors are point estimates with no interval.
  The overlapping-window estimator reads 1.986 for `pi*` and 1.422 for `r*` — it is
  downward-biased by construction and is reported, not used.
- **The recalibration compares a smoothed estimate with a simulated path.** History's `pi*` and
  `r*` are posterior-mean smoothed paths; a generated decade is a forward simulation. It is
  nonetheless the comparison the exam itself makes — `M4` decomposes history on exactly this
  series and `p2_components` scores the engine by the same function on its own — which is why the
  target is stated in those terms and the caveat is stated here.
- **`R1` is not measured.** Eleven of twelve bars have readings this round.
- **`S1` was not cut blind** (D-SP-11's own disclosure, carried), and this round chose its
  join-selection rule knowing what `S1` measures. The rule itself is anchored on nothing about the
  bar — it minimises a distance the compiler could always have seen — but a reader should know the
  designer knew the answer.
- **One panel, 813 rows, one country, 68 years.** The min-gap rule chooses among a few dozen
  candidates; there is no more panel to choose from.
- **`A1R` inherits every one of `A1`'s own problems**, unchanged: the compiler draws its months
  from the worst third of the panel by the `all_down` severity functional, where bonds win, and
  25,700 decades measure that selection effect very precisely without making it a fact about
  commodities.
- **The standing caveat carries.** Nothing built on this generator line is a convincing model of
  history, the holdout is spent, and no appeal to held-out data is available.
