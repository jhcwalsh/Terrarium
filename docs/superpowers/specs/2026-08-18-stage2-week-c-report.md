# Stage 2, week C: the four bars nobody had ever run — and the one that says the flesh works and the dial does not

**Date:** 2026-08-18 · **Branch:** `stage2-02-fit` · **Decision:** `D-SP-9` (stage 2 funded,
owner ruling 2026-08-17)
**Status: FRONTIER, unchanged in kind.** `A1` and `R1` pass. `A2` and `R2` fail. Combined
with week A's eight, **nine of the exam's twelve bars pass and three fail** — and for the
first time in three campaigns every bar in the exam has actually been measured.

**What was measured.** `A1`, `A2`, `R1`, `R2` — the four bars the spine-v2 exam sealed and
no round has ever run, because each needs something a bare spine does not produce. **What
judged them.** The sealed judges, imported and never re-implemented: `A1`/`A2` through
`scripts/spine_v2_report.judge_all`, `R1` through `scripts/stage2_report.judge_r1`
(delegating to `spine_pilot_b3._judge` on the byte-frozen b3 block), `R2` through
`scripts/stage2_report.judge_r2` (delegating to `spine_pilot_report.judge_b2`). **What
produced the worlds.** `scripts/stage2_worlds.py` + `scripts/stage2_weekc.py`, on week A's
engine as frozen input (`docs/superpowers/specs/stage2-fitted-params.json`). **Where the
numbers live.** `docs/superpowers/specs/stage2-weekc-results.json`, byte-identical on a
re-run (`sha256 565413ac70cbd8a8e7763ffa541790fd770860879fea47035ea010ebf9cc6f19`).

**House rules this document is written under** (D-SP-6's standing communication rule): plain
language; every number states what it is a measurement of; no term used without being defined
once.

---

## 0. The one-paragraph answer

The coupled engine of week A was given its flesh — verbatim real months of asset returns,
compiled onto the spine by the platform's own quadrant-conditioned block sampler, which runs
byte-verbatim underneath a composition that lives entirely in `scripts/`. **`A1` passes:
commodities beat bonds by more when the world says inflation is high than when it says
inflation is low, by +0.378 pp a year, inside the sealed containment range. `R1` passes and
cleanly: coverage is monotone across the allocation ladder (0.098 → 0.292 → 0.362 → 0.668)
and 4 of 20 rungs breach at the 55-point arm against a floor of 1. `A2` fails all three of
its conditions: the stock–bond correlation in high inflation is −0.018, which is not positive,
and it exceeds the low-inflation correlation by 0.061 against a sealed margin of 0.136.
`R2` fails on one seam in six thousand months.** And the finding that matters more than any
of the four verdicts: **on the very same batch, judged on the inflation the drawn months
actually carried rather than on the inflation the spine simulated, `A2` passes all three
conditions with room — correlation +0.176 in high inflation against −0.172 in low, a gap of
0.348, and 93% of three-year windows positive.** The flesh reproduces history's correlation
flip in the months it selects. The coupled spine's inflation dial then fails to point at
those months: dial and drawn months agree on 60.6% of judged months against 59.2% expected if
they were independent. The reason is structural and is not stage 2's: the compiler's quadrant
conditioning only chooses a month when a block *starts*, and **8.2% of months in a decade
start a block.** The other 92% are the panel's own next row.

---

## 1. What week C built, and what it deliberately did not

### 1.1 The composition, and the one line that is substituted

Week A fitted the coupled system and read the eight bars a bare spine admits. The other four
need a **compiled world**: `A1` and `A2` need real months of asset returns, `R2` needs the
compiled ensemble and the panel source, and `R1` needs the institutional twin run over a
compiled path. So week C builds the compiled world — and builds it by **composition**, not by
promotion:

- **Nothing in `src/` is edited.** Not one line. The flesh machinery — `SpineBootstrap`'s
  quadrant-conditioned pools, its percentile strata, its hazard corrections, its era-safe
  joins, its forced-re-entry rule — runs exactly as the platform ships it.
- **Exactly one function is substituted, at runtime, from `scripts/`**:
  `ah.gen.spine.sample_spine`, the sampler that decides which climate and which growth path
  the flesh is conditioned on. `stage2_worlds.stage2_flesh` installs the coupled system's own
  batch generator in its place and restores the platform's on exit, including on an
  exception.
- **Promoting the stage-2 sampler into `src/` is a separate owner release event, after a
  pass, and it is not done here.** Everything below is measured against a platform that is
  bit-for-bit the one on `main`.

### 1.2 The one place the old machinery's interface forces a choice

`SpineBootstrap._draw` computes each month's quadrant *itself*, through
`ah.gen.spine.spine_quadrant`: hot is `pi_star − mu_pi > 0.5` and expanding is "the six-label
regime code is outside `{REC, CRI}`". Stage 2's own season — the one `grader_v2` judges and
every week-A bar was read on — is `(expanding << 1) | (yoy > 3.3513)` where `yoy = pi* + x` is
the coupled system's inflation and the contracting axis is grader_v2's `{REC, CRI, STAG}`.
**Those are different classifications.** Handing the stage-2 decade to `_draw` raw would
condition the flesh on a classification the exam does not judge.

Three options existed and the minimal-change one was taken:

| option | what it costs |
|---|---|
| re-implement `_draw`'s loop in `scripts/` with the stage-2 quadrant inlined | a copy of sealed-adjacent machinery, which drifts under an editor — the exact failure mode the campaign's "import, never copy" rule exists against |
| edit `src/ah/gen/spine.py` | out of the campaign's scope, and a release event |
| **project the stage-2 decade into the `SpinePaths` contract so the machinery's own formulas evaluate to the stage-2 season** | **taken** — not one line of the flesh changes |

The projection: `states[:, :, 0]` carries `yoy − 3.3513 + 0.5` with `mu_pi = 0`, so
`spine_quadrant`'s hot test is `yoy > 3.3513` **exactly** — the same strict inequality, no
epsilon; `labels` carry `EXP` where the coupled chain's growth axis is expanding and `REC`
where it is contracting, so `label not in {REC, CRI}` *is* that axis; every other state column
is the decade's real L1 state, so the severity table's credit condition still reads the true
credit gap. The projection is used **only** for the quadrant — a compiled ensemble's own regime
record is the panel's labels at the selected rows, never these.

**And the projection is verified in code rather than argued.** Before the flesh is allowed to
see a batch, `spine_paths_from_decades` asserts month by month that
`spine_quadrant(projected) == the stage-2 season`, for every month of every decade. If it ever
stopped being exact the run stops. It was exact on all 6,000 months of every batch below.

### 1.3 The engine is frozen input, and that is checked, not promised

`stage2-fitted-params.json` is week A's artifact and week C may not refit anything.
`stage2_worlds.build_frozen_system` re-runs week A's own deterministic estimator and then
checks **every fitted number** against the committed artifact: 42 coefficients and constants,
worst absolute drift **4.841e−13** against a tolerance of 1e−11 (the artifact's own
twelve-decimal rounding). A rebuild that does not reproduce the frozen numbers raises.

### 1.4 The spine week C fleshes IS the spine week A judged

`A1`, `A2` and `R2` are read on the **unconditional 50-decade batch at seed 20260821** — week
A's own verification seed, so the macro path is bit-identical to the one the eight pre-flesh
bars were read on and a week-C verdict is attributable to the flesh alone. That claim is not
prose: the eight pre-flesh bars are **re-judged on this batch** and checked against the
artifact's own values before any week-C bar is reported.

> **Worst absolute drift across all eight: 0.0. Exactly zero, not "small".**

| bar | week A | week C's re-read | drift |
|---|---|---|---|
| T1 | 2.239246798804 | 2.239246798804 | 0 |
| O1 | 0.560824742268 | 0.560824742268 | 0 |
| D1 / D2 / D3 / D4 | 2.0 / 4.0 / 4.0 / 3.0 | 2.0 / 4.0 / 4.0 / 3.0 | 0 |
| P1 (binding margin) | 0.042073930959 | 0.042073930959 | 0 |
| P2 | 0.770682653481 | 0.770682653481 | 0 |

### 1.5 Stream hygiene

Week A proved its five per-decade streams disjoint from each other and from
`ah.gen.spine.LAYER_OFFSETS`. Week C turns on two more consumers at the same base seeds — the
block stream and the hazard stream inside `_draw` — opened a **different way**
(`PCG64(seed + offset).jumped(p)`, one fixed jump per path, against week A's
`PCG64(seed + offset + 32452843·attempt)`). Two differently-constructed streams cannot be
compared by looking at integers, so whole tapes were drawn and compared: **2,688 flesh streams
against 25,200 stage-2 attempt streams across all 21 base seeds, no collision**, plus
disjointness from the bare ladder and coprimality of the two strides.

---

## 2. The batches, and which construct each bar's seal demands

| bars | batch | why that one |
|---|---|---|
| `A1`, `A2`, `R2` | **unconditional, 50 decades, seed 20260821**, fleshed on world `…802`'s flesh spec | 50 decades is the exam's sealed ensemble size; the seed and the unconditional arm are week A's, so the spine is identical (§1.4) |
| `R1` | **the b3 ladder, byte-frozen**: world `…802`'s own premise, 20 rungs at `199002 + 7919·k`, arms `[15, 35, 40, 55]` private points, same book construction, same hold-course institution run | R1 is a carried no-regression bar; changing any of that is the thing a carried bar exists to prevent |

**World `…802` ("The Hard Landing") is the only world in the tree that declares both
`x_stress` and `x_spine`**, so it supplies the flesh *spec* — segments, entry percentiles,
6-month mean blocks, join tolerances, severity table — for both batches. On the unconditional
batch its **premise clause** is switched off and every attempt is accepted; nothing else about
the world changes. That is week A's own unconditional arm, not a new construct. What it does
mean, and it is a disclosure not a defect, is that even the unconditional batch draws from
world 802's declared severity shape (entry at the worst 35% of months, and the worst 10% over
quarters 8–14). §9 carries it.

**The 20 rungs of R1's ladder are verified pairwise distinct** — both their spines and their
compiled month tapes, 20 of 20 on each. That check is not a formality: round one recorded a
seed-stride collision that left a 20-rung ladder measuring two storylines.

---

## 3. `A1` — does the inflation hedge pay when inflation is high? **PASS**

**The bar.** At the 4% line: the commodities-minus-bonds spread over high-inflation months
must exceed the spread over low-inflation months (a strictly positive difference), and the
high-inflation spread must land inside **[−5.053, +32.316] pp**, the full range spanned by the
five named historical episodes.

| quantity | generated | history |
|---|---|---|
| spread, high inflation (≥ 4%) | **+2.1424 pp/yr** | +4.8720 pp/yr |
| spread, low inflation (< 4%) | **+1.7643 pp/yr** | +1.3787 pp/yr |
| **difference** | **+0.3781 pp** | **+3.4933 pp** |
| months, high / low | 1,826 / 3,574 | 225 / 576 |

> **`A1` PASSES: directional PASS (+0.3781 > 0), containment PASS (+2.1424 inside
> [−5.053, +32.316]).**

**Read the size before reading the verdict.** The bar is directional and the direction is
right, but the effect is **11% of history's**. The exam is explicit that the containment half
is "closer to a plumbing assertion than to evidence about the engine" under selection-only
compilation, so the whole content of this PASS is a difference of +0.38 pp against an anchor
of +3.49 pp. It clears a bar that asks for a sign.

**The sensitivity the exam requires published, and what it shows.** The exam prints the 3%
line precisely because **history's own ordering reverses there** (−0.58 pp), and prints 5% for
symmetry. Both are disclosures and neither is judged:

| line | generated: spread high | spread low | difference | history's difference |
|---|---|---|---|---|
| 3% | +2.0126 pp | +1.8027 pp | **+0.2099** | **−0.58 pp — history flips** |
| **4% (the bar)** | **+2.1424 pp** | **+1.7643 pp** | **+0.3781** | +3.49 pp |
| 5% | +2.0126 pp | +1.8494 pp | +0.1632 | +7.73 pp |

**The engine does not flip at 3%, and that is not a strength.** History's spread swings from
−0.58 to +3.49 to +7.73 across the three lines — an 8.3-point range. The generated spread moves
over **0.21 to 0.38 to 0.16** — a fifth of a point. The inflation line carries almost no
information about the assets in these worlds, at any line. That is the same fact `A2` fails
on, seen through a different statistic, and §4.2 is its diagnosis.

---

## 4. `A2` — do stocks and bonds fall together when inflation is high? **FAIL**

**The bar.** Three conditions at the 4% line, all required: the high-inflation stock–bond
correlation is **positive**; it exceeds the low-inflation correlation by at least **0.13609**
(the lower edge of history's own 95% interval); and at least **80%** of 36-month windows
ending in a high-inflation month are positive.

| condition | generated | required | verdict |
|---|---|---|---|
| correlation, high inflation | **−0.017743** | > 0 | **FAIL** |
| correlation, low inflation | −0.078654 | (reference) | — |
| difference, high − low | **+0.060911** | ≥ 0.136094 | **FAIL** |
| share of 3-year windows positive, high inflation | **0.4760** (1,500 windows) | ≥ 0.80 | **FAIL** |
| share positive, low inflation (dropped ceiling, disclosure) | 0.4681 (2,700 windows) | — | reported |

> **`A2` FAILS all three conditions.** History's numbers are +0.30125 / −0.01823, a difference
> of 0.31949, and 94.7% of high-inflation windows positive.

### 4.1 The disclosure that changes what this FAIL means

The same batch, the same real months, the same sealed judge — with the decade's inflation read
off **the months actually drawn** instead of off the spine that chose them:

| condition | judged on the spine's inflation | judged on the drawn months' inflation | required |
|---|---|---|---|
| correlation, high | −0.017743 | **+0.176479** | > 0 |
| correlation, low | −0.078654 | **−0.171845** | — |
| difference | +0.060911 | **+0.348323** | ≥ 0.136094 |
| share of windows positive, high | 0.4760 | **0.9285** | ≥ 0.80 |
| share positive, low (disclosure) | 0.4681 | 0.3293 | — |
| **would the bar pass?** | **no, on all three** | **yes, on all three** | |

And `A1` under the same substitution: difference **+5.3297 pp** (high +6.0651, low +0.7354)
against the spine-inflation reading's +0.3781 and history's +3.4933.

**This is a disclosure and it is not a verdict.** It is reported here, never judged, and §8.1
states exactly why the spine's inflation is the primary. But it says something the bare FAIL
cannot: **the months this compiler selects do carry history's correlation flip, at very nearly
history's own size.** What fails is the link between the world's inflation dial and the months
it selects.

### 4.2 The diagnosis, measured

If a bar conditions asset returns on a simulated dial, it can only see history's behaviour to
the extent the compiler puts genuinely high-inflation months where the dial says inflation is
high. That alignment is a quantity, so it was measured rather than assumed:

| quantity | value |
|---|---|
| months judged (after the sealed 12-month warm-up) | 5,400 |
| share the spine's dial calls high (≥ 4%) | 0.3381 |
| share the drawn months' own inflation calls high | 0.2170 |
| **the two dials agree on** | **0.6059** |
| **agreement expected if they were statistically independent** | **0.5916** |
| mean inflation of the months drawn when the spine says high | **3.2248 pp** |
| mean inflation of the months drawn when the spine says low | **3.0250 pp** |

> **The dial and the months it selects are, to a first approximation, independent.** Agreement
> beats chance by 1.4 percentage points; the mean inflation of a "high" month is 0.20 pp above
> that of a "low" one, and both sit *below* the 3.3513 pp era line the pools are conditioned on.

**And the structural reason, which is not stage 2's.** The compiler's quadrant conditioning
chooses a month only when a block **starts** — the decade's first month, a join, or a forced
re-entry. Every other month is the panel's own next row, drawn for no reason but contiguity.

| quantity | value |
|---|---|
| months in the batch | 6,000 |
| months selected for their quadrant | **494** |
| **share of a decade the conditioning reaches** | **8.2%** |

The declared mean block is 6 months, which would put the figure near 17%; the realised figure
is half that, because a join only happens when the block-break draw fires *and* the era-safe
join filter leaves a candidate — otherwise the block simply continues. So **the spine chooses
roughly one month in twelve and inherits the other eleven.** A dial that sets 8% of a decade
cannot make the other 92% agree with it, and `A1`/`A2` are bars about all of it.

This is a property of the sealed compiler design — selection-only, 6-month mean blocks,
era-safe joins — inherited whole by stage 2 and made visible by the first campaign that ever
ran the two allocation bars. It belongs in the engine-realism register, and §11 asks for that.

---

## 5. `R1` — severity still bites the book **PASS**

**The bar** (`b3`, byte-frozen): the median worst liquidity-coverage statistic must be
**non-decreasing** across the allocation grid `[15, 35, 40, 55]` private points, and at least
**1 of 20** rungs must breach (coverage reaching 1.0) at the 55-point arm.

| arm (private points) | median worst coverage | round two's |
|---|---|---|
| 15 | **0.098065** | 0.0901 |
| 35 | **0.291855** | 0.2821 |
| 40 | **0.361632** | 0.3514 |
| 55 | **0.667991** | 0.6643 |

| check | value | threshold | verdict |
|---|---|---|---|
| (a) coverage monotone in allocation | the four medians above | non-decreasing | **PASS** |
| (b) breach rungs at 55 | **4 / 20** | ≥ 1 | **PASS** |
| (c) hold-course depth inside the declared band *(disclosure)* | **−0.376591** | [−0.4260, −0.3750] | pass, by 0.0009 |

> **`R1` PASSES on the sealed bar** — (a) and (b), which are the two conditions the exam
> quotes. The judge's own `overall` field, which ANDs in check (c), is also PASS, so nothing
> hangs on the distinction here. It is drawn anyway because it will matter the moment (c)
> moves: `spine_pilot_b3`'s own docstring and the round-two record both put (c) outside the
> sealed b3 bars ("constructed post-seal, disclosed, not judged").

**Read (c)'s margin before quoting it.** −0.376591 clears the shallow edge of a
**self-constructed** band by **0.0009** — a tenth of round two's already-thin 0.0059. The band
is a documented deviation, not a sealed bar, and a disclosure sitting nine ten-thousandths
inside a band it built for itself is not evidence of anything. It is reported so nobody
discovers it later.

**The worlds got slightly harder, not softer.** Every coverage median is above round two's and
the breach count doubled, 2 of 20 → 4 of 20. That is the direction a no-regression bar exists
to protect, and the ladder's 20 rungs are verified distinct so it rests on 20 storylines.

---

## 6. `R2` — eras don't teleport at the seams **FAIL**

**The bar** (`b2`, byte-frozen): no seam may carry a jump in trailing 12-month CPI inflation
larger than **2.5 pp**, and the 95th percentile of month-to-month changes in trailing inflation
must be at most **0.9292 pp** (1.25× history's own 0.7434).

| half | generated | bound | verdict |
|---|---|---|---|
| largest jump at a seam | **4.1325 pp** | ≤ 2.5 pp | **FAIL** |
| p95 adjacent-month change | **0.8830 pp** | ≤ 0.9292 pp | **PASS** |

> **`R2` FAILS**, on the join half only. Round two failed **both** halves (5.3195 pp and p95
> 0.9658–0.9678). **The p95 half has flipped from FAIL to PASS** and the join half has not.

### 6.1 Where the 4.13 pp comes from — the whole failure is one seam

Obligation 6.2 requires every FAIL characterised, and this one has an exact cause:

| quantity | value |
|---|---|
| seams in the batch (50 decades, 6,000 months) | **444** |
| seams that are forced re-entries (the panel-edge rule) | **1** |
| largest jump at an ordinary join | **2.4801 pp — inside the bound** |
| largest jump at the forced re-entry | **4.1325 pp — the failure** |

An ordinary join is filtered on the inflation era bucket **and** on `|ΔYoY| ≤ 2.5 pp`, so it
cannot exceed the bound; all 443 of them obey it, with the largest landing 0.02 pp under.
A **forced re-entry** happens when a block reaches the panel's last row: the owner's ruling of
2026-08-16 ends the block and draws a fresh entry rather than wrapping to row 0 — and when no
candidate in that month's pool matches the era filter, it draws **unfiltered**. That happened
**once in six thousand months**, and that single unfiltered draw is the entire `R2` failure.

**So `R2` is one line of code away from passing, and it is not stage 2's line.** The
unfiltered fallback is a declared, owner-ruled escape hatch in the platform's compiler; the
exam expected `R2` to flip on join-constraint tightening, which is inside D-SP-6's funded scope
and which stage 2 did not spend a day on. Fixing it is a decision about the fallback (refuse?
widen the pool? relax the era match before relaxing the level bound?), and it is the owner's,
because every option changes a sealed compiler behaviour.

---

## 7. The full exam — all twelve bars, for the first time

Week A's eight are quoted **unchanged**, from `stage2-fitted-params.json`, and were re-read on
week C's own batch at exactly zero drift (§1.4).

| bar | what it asks | sealed band / floor | measured | verdict | week |
|---|---|---|---|---|---|
| **T1** | does tightening cause downturns? | [1.775283, 3.347362] | **2.239247** | **PASS** | A |
| **O1** | do the seasons turn the right way round? | ≥ 0.5180669 | **0.560825** | **PASS** | A |
| **D1** | recession spell length | [0, 5] months | **2.0** | **PASS** | A |
| **D2** | stagflation spell length | [1, 7] months | **4.0** | **PASS** | A |
| **D3** | recovery spell length | [2, 8] months | **4.0** | **PASS** | A |
| **D4** | expansion spell length | [1, 7] months | **3.0** | **PASS** | A |
| **P1** | do the two dials keep time with each other? | both move types | **binding margin +0.042074** | **PASS** | A |
| **P2** | is the curve made of economics? | [0.391707, 0.673371] | **0.770683** | **FAIL — above** | A |
| **A1** | does the inflation hedge pay in high inflation? | direction, and high spread inside [−5.053, +32.316] pp | **+0.3781 pp; high +2.1424 pp** | **PASS** | **C** |
| **A2** | do stocks and bonds fall together in high inflation? | corr > 0, gap ≥ 0.136094, ≥ 80% of windows | **−0.017743; +0.060911; 47.6%** | **FAIL — all three** | **C** |
| **R1** | severity still bites the book | monotone coverage, ≥ 1/20 breach at 55 | **monotone; 4/20** | **PASS** | **C** |
| **R2** | eras don't teleport at the seams | jump ≤ 2.5 pp, p95 ≤ 0.9292 pp | **4.1325 pp; 0.8830 pp** | **FAIL — join half** | **C** |

> **Nine of twelve pass. Three fail: `P2` from above on inherited dispersion, `A2` on all
> three of its conditions, `R2` on a single seam.** Four bars that had never been run in any
> round of this campaign now have readings.

---

## 8. The disclosures, in full

None of these can supply a verdict. They exist so that a choice costs a number rather than an
argument.

### 8.1 Which inflation a fleshed decade reports — the primary, and why

A fleshed decade carries **two** inflation series and the exam's `Decade` contract has one
slot. The primary taken is the **spine's own** `pi* + x`:

- The exam's own sentence is that `A1` and `A2` need "verbatim real months of asset returns
  **compiled onto the spine**". The spine is the world; the flesh supplies the returns.
- Every other bar in the exam reads the spine's series. `O1` and `D1`–`D4` are cut from the
  seasons, which are cut from it; `P1`'s hot dial **is** it. Judging `A1`/`A2` on a different
  inflation would mean one batch judged under two inflation series.
- It is the only series the sealed 12-month warm-up rule fits: a decade's drawn panel months
  carry a defined trailing inflation from their first month.

The alternative reading is in §4.1 and it flips `A2`. It has a real argument behind it —
`ah.port.adapter.run_gen_path` reports a compiled world's inflation as the panel's at the drawn
rows, so it is what a *player* sees — and §11's first stop-question is exactly this.

### 8.2 The premise-accepted batch

The same three bars on 50 **premise-accepted** decades (world 802's Hard Landing clause on,
832 attempts for 50 acceptances), same seed:

| bar | unconditional (the reading) | premise-accepted (disclosure) |
|---|---|---|
| `A1` | **PASS**, difference +0.3781 pp | **FAIL**, difference **−2.9465 pp** (high −0.1833, low +2.7632) |
| `A2` | FAIL (corr high −0.0177) | FAIL, corr high +0.0440, gap +0.1180 against 0.1361 |
| `R2` | FAIL, max jump 4.1325 pp | FAIL, max jump **11.2385 pp** |

**`A1`'s sign reverses under the premise.** That is worth the owner's attention: on a world
built to be a supply-shock hard landing, commodities-minus-bonds is *worse* in the months the
spine calls high-inflation. It is a disclosure, on an arm the exam does not judge the pre-flesh
bars on either, and it is not being read as a verdict — but it says the `A1` PASS above is not
robust to the premise.

### 8.3 The compiler's own stamp on the judged batch

50 decades, 6,000 months: 28 pools built, smallest pool **1 row**, 721 distinct panel rows
visited of 813, 1 forced re-entry, 1 unfiltered re-entry, 50 spine attempts for 50 decades
(the unconditional arm rejects nothing).

---

## 9. Limitations, measured

**W1 — the conditioning reaches 8.2% of a decade.** §4.2. The single most important number in
this report. It bounds what any bar conditioned on the spine's dial can see in the flesh, it
belongs to the sealed compiler design rather than to stage 2, and it was invisible until the
allocation bars were run.

**W2 — `A1` passes on a sign, at 11% of history's size, and reverses under the premise.**
§3 and §8.2. A bar that asks for a direction got one. Nothing more should be read into it.

**W3 — the unconditional batch still carries world 802's severity shape.** World `…802` is the
only world in the tree that declares both `x_stress` and `x_spine`, so it supplies the flesh
spec for both batches: entries are drawn from the worst 35% of months by the `all_down`
severity functional, and from the worst 10% over quarters 8–14. Switching the premise clause
off makes the batch unconditional in its **spine**; it does not make the flesh neutral. A
neutral flesh spec does not exist in the tree and inventing one would be improvising a
construct.

**W4 — `R2`'s failure is a single event, and single events are not estimates.** One forced
re-entry in 6,000 months decided the verdict. The bar is a hard maximum, so that is exactly
what it is written to catch — but nobody should read "4.13 pp" as a property of the engine's
typical seam. The typical seam is 443 joins with a maximum of 2.48 pp.

**W5 — `R1`'s depth disclosure clears a self-constructed band by 0.0009.** §5.

**W6 — the composition is a runtime substitution, not a promoted engine.** Every number here
was produced by a `scripts/`-level composition over an unmodified platform. Whether the
substituted sampler behaves identically once promoted into `src/` is a claim this report does
not make and cannot: promotion is a release event with its own gate.

**W7 — every limitation of week A and of the sealed exam is inherited whole.** `M1` (the
coupling is significant and inert), `M2` (`P1` passes through the reverse arrow), `M4` (the
generated world is over-dispersed and `P2` catches it), `L1` (`P1`'s size is 9.0%), `L12` (the
v2 exam's own limitations), and `L13` — **nothing here reaches the private book. ER-14 stands
exactly where it was**, and a passing `A1` says nothing about it.

**W8 — the standing caveat is unchanged.** Nothing built on this generator line is a
convincing model of history, the holdout is spent, and no appeal to held-out data is available
to any result week C produces.

---

## 10. Status

**FRONTIER.** Nine of twelve bars pass. `A1` and `R1` pass; `A2` fails on all three of its
conditions and `R2` fails on one seam; `P2` still fails from above on inherited dispersion.
Nothing was tuned, no threshold was touched, no bar was invented, and no file inside either
seal was edited. `uv run python scripts/stage2_weekc.py` is byte-identical on a re-run.

---

## 11. Stop-questions for the owner

1. **Which inflation series does a *fleshed* decade report — and `A2`'s verdict is the price.**
   On the spine's own inflation, `A2` fails all three conditions. On the inflation the drawn
   months actually carried, it passes all three with room (§4.1). The exam's `Decade` contract
   has one slot and does not say. The primary taken is the spine's, for the three reasons in
   §8.1, and the alternative has a real argument — the platform's own adapter reports a
   compiled world's inflation as the panel's. **This is a ruling, not a measurement, and it
   decides a bar.**

2. **The compiler's conditioning reaches 8.2% of a decade. Is that an ER-class register entry,
   a funded fix, or a declared property?** It is the mechanism behind both allocation readings
   and it is inherited from the sealed compiler design. A fix would be a change to block
   length or to the join rule, which changes `R2` and `D1`–`D4` as a side effect — so it is a
   release decision, not a cleanup.

3. **`R2` fails on one unfiltered forced re-entry in 6,000 months.** The panel-edge rule is an
   owner ruling (2026-08-16) and its unfiltered fallback is the only seam in the design that
   can exceed the bound. Refuse the decade? Widen the pool at the edge? Relax the era match
   before the level bound? Each changes a sealed compiler behaviour, and join-constraint
   tightening is inside D-SP-6's funded scope but was not spent.

4. **`A1` passes unconditionally and reverses sign under the premise** (+0.3781 pp against
   −2.9465 pp, §8.2). The exam judges the unconditional arm and that is what is reported. Is a
   bar that flips sign between the two arms carrying the meaning it was written for?

5. **`R1`'s third check is a disclosure that now clears its own constructed band by 0.0009.**
   The sealed bar is (a) and (b) and both pass comfortably. Confirm that (c) stays a
   disclosure, or rule that it becomes a bar — in which case it needs a band cut from
   something other than itself.

6. **Promotion.** The stage-2 world assembly is composed in `scripts/` and substitutes exactly
   one platform function at runtime. **Promoting it into `src/` is a separate owner release
   event and has not been taken.** Nine of twelve is a frontier, not a pass, and this report
   does not ask for the promotion.
