# The spine v2 campaign — the verdict. CLOSED at the second frontier.

**Date:** 2026-08-17 · **Branch:** `spine2-02-fit` · **Status: CLOSED, owner-ruled
2026-08-17.** Funding ruling: `governance/decision-register.md` D-SP-6 (2026-08-16 evening),
stage 1 only. Continuation ruling: D-SP-8 (2026-08-17), which ordered the season-to-curve
feedback built and re-measured.

**What this document is.** The campaign's close-out record: what was sealed, what the sealed
bars read at the end, what the two escalations proved, what the owner ruled on the three open
housekeeping questions, and what a future stage-2 campaign inherits. It is a *verdict*
document, not a new measurement — every number in it is quoted from a committed record and
carries its source. Nothing here re-judges anything.

**The records it stands on** (all committed, all on this branch):

| record | commit | what it is |
|---|---|---|
| `docs/superpowers/specs/2026-08-17-spine-v2-exam.md` | `5d1a282` (sealed) | the exam — ten bars, their anchors, their justifications, its own declared limitations |
| `docs/superpowers/specs/spine-v2-prereg.json` | `5d1a282` | the seal — thresholds plus the sha256 of the twelve files that judge them |
| amendment `AM-SPV2-2026-08-17-001` | `181c208` | which batch T1 and O1 are judged on |
| `docs/superpowers/specs/2026-08-17-spine-v2-fit-report.md` | `78e71bd` | week 2: the fitted hazard, and the **first** frontier |
| `docs/superpowers/specs/2026-08-17-spine-v2-feedback-report.md` | `45dc10e` | week 3: the fitted season-to-curve feedback, and the **second** frontier |

Prior rounds, frozen and not reopened by anything here: the pilot
(`2026-08-15-spine-pilot-results.md`) and spine-02 (`2026-08-16-spine02-results.md`).

---

## The one-paragraph answer

The spine v2 campaign was funded to find out whether a generation-time economic engine —
seasons driven by a hazard that reads the curve, the credit gap, inflation and drawdown —
could satisfy a pre-registered exam written before any of it existed. It got two escalations
and produced two frontiers, both measured rather than argued. **The four persistence bars
(D1–D4) pass everywhere** — both arms, all four engines, all thirty-two frontier rows. **The
transmission bar T1 ends at a QUALIFIED PASS**: it reads 1.9131 inside a band of
[1.7753, 3.3474], but the decomposition shows most of that movement came from changing the
*estimator*, not from the mechanism the week was funded to build, and the estimator that
clears the bar is the one in which the generated curve is **93.9% exogenous noise**. **The
ordering bar O1 FAILS**, at 0.5118 against a floor of 0.5181, and it fails at *every*
feedback strength on the whole frontier, because O1 measures the phase between the growth and
inflation dials and the curve is not that channel. **A1, A2, R1 and R2 were never measured** —
they need the flesh, and the sampler integration was never reached. The campaign is closed at
this frontier by design: the two things standing between the engine and a clean pass are both
named, both measured, and both lie outside stage 1's funded scope.

---

## 1. What was sealed, and when

**The seal.** `docs/superpowers/specs/spine-v2-prereg.json`, schema `spine-v2-prereg-1`,
`sealed_at_utc` **2026-08-17T14:42:40-07:00**, recorded as of HEAD commit
`1ca6ed5bd11b8a5901c8e3786a668643e6dedc7d` and committed at `5d1a282`
("PRE-REGISTRATION — the spine v2 exam is SEALED; ten bars, their judges, and the code hashed
together"). The seal was taken **before any engine work and before any generated ensemble
existed**.

**What the seal hashes.** Twelve paths, thresholds and judging code together — the exam
document itself, `spine-v2-anchors.json`, `spine-v2-antitest-results.json`, the two prior
rounds' preregs (`spine-pilot-prereg.json`, `spine02-prereg.json`), and six scripts
(`spine_v2_anchors.py`, `spine_v2_antitest.py`, `spine_v2_grader.py`, `spine_v2_report.py`,
`spine_v2_seal.py`, plus the byte-frozen `spine_pilot_b3.py` and `spine_pilot_report.py` that
carry R1 and R2). The exam document's sha256 is
`4fdf7c0ae6afb97764a6633f09f186ddfcc9b740509e64342eba94a38ab6f568`; it is byte-identical
today, re-verified while writing this document and asserted in code by
`tests/test_spine_v2_seal.py`, which recomputes every hash against the working tree and fails
unless each mismatch is named by an amendment entry.

**The ten bars, as sealed** (exam §9; thresholds live in `spine-v2-anchors.json` under
`exam_bars` so the table, the file and the judges cannot disagree about a number):

| tier | code | the bar | historical anchor |
|---|---|---|---|
| causal | **T1** | transmission lift inside **[1.7752827491108736, 3.3473622102535145]** | 2.37× (86/149 tight-month onsets vs 192/789) |
| causal | **O1** | clockwise fraction **≥ 0.5180669104991394** | 0.5972 over 72 transitions, 95% CI [0.5181, 0.6765] |
| persistence | **D1** | recession pooled median **[0, 5] months** | 2 months, 893 decade-pooled spells |
| persistence | **D2** | stagflation pooled median **[1, 7] months** | 4 months, 1268 spells |
| persistence | **D3** | recovery pooled median **[2, 8] months** | 5 months, 1661 spells |
| persistence | **D4** | expansion pooled median **[1, 7] months** | 4 months, 2123 spells |
| allocation | **A1** | spread(high) > spread(low) at the 4% line, inside [−5.05, +32.32] pp | +4.87 pp vs +1.38 pp |
| allocation | **A2** | corr(high) > 0, exceeding corr(low) by ≥ 0.1361; ≥ 80% of 3-year windows positive in high inflation | +0.30 vs −0.02, difference 0.3195, CI [0.1361, 0.5568] |
| no-regression | **R1** | b3 byte-frozen: monotone coverage, ≥ 1/20 breach at the 55% arm | round two: PASS |
| no-regression | **R2** | b2 byte-frozen: join jump ≤ 2.5 pp, p95 ≤ 0.9292 pp | round two: FAIL |

Batch size `n_seeds = 50`, owner-ruled 2026-08-17 (exam §8.1) — at 50 every retained bar
clears 90% power for a true engine, the weakest being D2 at 0.921. R1's b3 grid keeps its own
byte-frozen `n_seeds = 20`.

**The one amendment.** `AM-SPV2-2026-08-17-001`, dated 2026-08-17, `post_hoc: true`, logged
in the seal's own `amendments` block and committed at `181c208` — **before any week-3 model
work began**, on the authority of owner ruling D-SP-8. It changed **no threshold**
(`thresholds_changed: []`) and edited **no hashed file** (`hashed_files_edited: []`; the exam
document is byte-identical and the entry says so). What it resolved was an ambiguity the
sealed record genuinely contained: exam §8.1's power calculation models a true engine as one
emitting **unconditionally** drawn 120-month stretches of the panel, while the same section's
ruling sentence fixes `n_seeds` at "50 decades **per premise**". Week 2 measured both arms and
they disagreed by 0.53 of T1 lift, so the reading had to be settled before a verdict rather
than after one.

**The ruling:** T1 and O1 are judged on an **unconditional** 50-decade batch — same engine,
same base seed, `ah.gen.spine._reject_reason`'s premise acceptance not applied. D1–D4 keep the
premise-accepted batch, as would A1/A2/R1/R2. The reasoning is like-for-like conditioning
applied a third time (after PRE-SEAL RULING 1's D3 windowing and round two's B6 base rates):
both T1's band and O1's floor are measured over the *whole* panel, so a premise-selected batch
distorts exactly the composition T1 measures.

**What the amendment disclosed about itself, at the time it was written:** the unconditional
arm already read **more favourably** on both bars — T1 1.763633 vs 1.230161, O1 0.514911 vs
0.500707 — and the entry records those four numbers in its own
`readings_known_at_amendment_time` payload, together with
`amended_arm_reads_more_favourably: true`. **Both arms failed both bars at that moment**, so
nothing flipped FAIL→PASS at the act of amending; but both readings moved toward their bands
and that is on the record rather than in a footnote. §4 below is the owner's ruling on whether
it stands.

---

## 2. The final bar readings, under the sealed constructs

The primary engine is the exact-ML joint fit (`feedback`), declared as primary in the module
docstring **before any bar was read** (feedback report §5). All readings are by the sealed
judges themselves, imported unmodified from `scripts/spine_v2_report.py`.

| bar | arm (per the amendment) | sealed threshold | measured | verdict |
|---|---|---|---|---|
| **T1** | unconditional | [1.7752827491108736, 3.3473622102535145] | **1.913081** | **QUALIFIED PASS** — read §2.1 before using it |
| **O1** | unconditional | ≥ 0.5180669104991394 | **0.511765** | **FAIL** — short by 0.00630 |
| **D1** | premise-accepted | [0, 5] months | 2 | **PASS** |
| **D2** | premise-accepted | [1, 7] months | 3 | **PASS** |
| **D3** | premise-accepted | [2, 8] months | 4 | **PASS** |
| **D4** | premise-accepted | [1, 7] months | 3 | **PASS** |
| **A1** | premise-accepted | [−5.05, +32.32] pp, directional | — | **NOT MEASURED** |
| **A2** | premise-accepted | gap ≥ 0.1361, 80% share floor | — | **NOT MEASURED** |
| **R1** | b3 grid, n=20 | monotone + ≥1/20 breach at 55% | — | **NOT MEASURED** |
| **R2** | b2 frozen | join ≤ 2.5 pp, p95 ≤ 0.9292 pp | — | **NOT MEASURED** |

Source: feedback report §4 (`45dc10e`). Premise-accepted batch: 708 attempts for 50 decades
(496 backdrop, 145 arrival, 17 slow-recovery rejections). Unconditional batch: 50 attempts.

### 2.1 T1 — a QUALIFIED PASS, and why the qualification is first-class

T1 is inside its band. It is **not** a clean win, and this document will not present it as
one. Three measured facts sit beside the number, all from feedback report §5–6:

**(a) Most of the movement was the estimator, not the mechanism.** The attribution, each row
a real re-run rather than a decomposition on paper:

| change | T1, unconditional | movement |
|---|---|---|
| week 2 baseline | 1.7636 (FAIL, short by 0.0117) | — |
| + the fitted feedback alone, under week 2's own OLS estimator | 1.8384 | **+0.0748** |
| + the exact-ML estimator alone, **no feedback** | 1.9057 | **+0.1421** |
| both — the primary engine | 1.9131 | +0.1495 |

The estimator change is worth about **twice** what the feedback is worth, and **either alone
clears the bar**, because week 2 was already only 0.0117 below it. "The season-to-curve
feedback fixed T1" is a misreading of this table.

**(b) The bar was cleared by the arm in which the curve is least economically determined.**
The variance decomposition of the generated curve (feedback report §6):

| engine | `û` (L1 state) contribution sd | season term sd | residual stationary sd | **residual share of variance** |
|---|---|---|---|---|
| `week2` | 0.5358 | 0 | 0.6504 | **59.6%** |
| `ml_link` | 0.1531 | 0 | 0.7426 | 95.9% |
| `ols_feedback` | 0.5419 | 0.2787 | 0.6028 | 49.4% |
| **`feedback` (primary)** | **0.1486** | **0.1132** | **0.7314** | **93.9%** |

Week 2 flagged 59.6% exogenous residual as a limitation. The exact-ML estimator — the one the
joint likelihood names, and the one on which T1 passes — raises it to **93.9%**. Either T1 is
insensitive to how economically determined the curve is, which is a finding about T1, or the
exact-ML link is the right estimator for an inference and the wrong one for a generator. The
campaign did not resolve that, and the owner should not read T1's PASS without it.

**(c) It does not pass on the other arm.** On the premise-accepted batch the same engine
reads **1.2231** and fails. T1 fails on the premise arm at *every* point of the frontier
(1.1875 to 1.7047). A reader who rejects the amendment should read this campaign as FRONTIER
on both causal bars, not one.

**Why the qualification is not a hedge.** The two estimators disagree about the L1 link by a
factor of 3.6 (`c_u` = −0.1486 exact-ML vs −0.5419 OLS) — a real property of the data, since
with ρ ≈ 0.97 the Prais–Winsten transform is near-differencing and a levels relation between
two persistent series largely vanishes in differences. Both estimators were run, each with and
without the feedback, and the verdict was **pre-committed in code to the exact-ML arm before
any bar was read**. That is what makes the attribution table above possible and what stops the
exercise from being "run two and report whichever passes".

### 2.2 O1 — a FAIL, and the phase-channel diagnosis

O1 reads **0.511765** against a floor of 0.5180669104991394 — short by 0.0063. It does not
clear anywhere: its best value on the entire feedback frontier is **0.5156 at ×0.5**, still
short by 0.0025, and it falls monotonically beyond that to 0.4778 at ×6 (feedback report §8).

**Why, measured rather than argued** (feedback report §7). O1's clockwise clock is
`recovery → expansion → stagflation → recession → recovery`, and it **alternates axes**: two
of its four steps are inflation crossings and two are growth flips. So a growth flip is
clockwise if and only if it happens while inflation is hot, and an inflation crossing is
clockwise if and only if it happens on the matching growth axis. **O1 is a test of the phase
between the two dials, not of either dial alone.** Decomposed:

| | overall | growth flips | inflation crossings | diagonal |
|---|---|---|---|---|
| **history** | 0.5972 | **0.6176** (47.2% of transitions) | **0.6111** (50.0%) | 0.0000 (2.8%) |
| **generated** (`feedback`, unconditional) | 0.5241 | **0.5362** (40.5%) | **0.5477** (56.0%) | 0.0000 (3.4%) |

The shortfall is spread evenly across both move types — about 0.06 each — and both sit near
0.53, which is a coin flip. The engine's two dials are close to independent: the growth chain
is the fitted hazard, the inflation axis is read straight off L1, and **nothing couples their
phase**. History has a mild phase relation — downturns tend to begin hot, disinflation tends to
arrive during them — worth about 0.09 on each move type. A season → curve channel cannot
supply that, because the curve is not the link between growth and inflation. The frontier
sweep confirms the diagnosis behaves as stated: O1 is flat-to-declining in feedback strength.

A secondary contributor, carried from week 2 unchanged: the generated batch runs **56.0%
inflation crossings against history's 50.0%**, consistent with L1's `pi_gap` being
over-dispersed at **1.604×** history's standard deviation (fit report §2). L1 was reused as-is,
per the brief.

### 2.3 D1–D4 — PASS, everywhere, and that is a real result

D1–D4 pass on **both arms, for all four engines** (`week2`, `ml_link`, `ols_feedback`,
`feedback`; feedback report §4's attribution table), and in **all sixteen rows of each
frontier sweep** — week 2's transmission sweep and week 3's feedback sweep, thirty-two rows
between them, across a twelve-fold change in transmission strength and a six-fold change in
feedback strength. The dwell medians move by at most one month anywhere in that space.

**Across two campaigns and thirty-two frontier rows the dwell medians have never been the
binding constraint.** That matters because recovery persistence is precisely what sank the
pilot and spine-02 (B4 FAIL, recoveries at ~half history's length, twice-confirmed under
byte-frozen judges) and it is the same persistence flaw that sank `hier-flow` at G2. The
generation-time hazard with fitted duration dependence fixed it.

The exam's own reading note applies and is repeated: a D verdict that missed by one quarter
would be inside the anchor's own sampling noise. **These do not miss.** Also carried: the D
bars' power calculation is close to tautological, because the anchor is cut from the same
object the power model's true engine emits (exam §12.3).

### 2.4 A1, A2, R1, R2 — NOT MEASURED, and exactly why

These four bars were never run. Not estimated, not guessed at, not partially reported. The
judge-facing records carry `NaN` in all three return series and only the six pre-sampler
judges were ever called.

**The reason is structural, not a matter of time running out.** A1 and A2 are defined on
**asset returns** — commodities, bonds, equities — and R1/R2 need a **compiled ensemble** and
the panel source: R1 is spine-02's b3 over-commitment grid run through the institution, R2 is
spine-02's b2 era-coherence bar on stitched decades. All four therefore require the **flesh**:
the block sampler integrated into `src/`, emitting asset returns and compiled worlds. Weeks 2
and 3 were both **standalone** — climate plus seasons, no flesh, no block sampler, no asset
returns, nothing in `src/` or `schemas/` touched.

The campaign's design said to stop at a frontier rather than build past one. It hit the first
frontier in week 2 and the second in week 3, so **sampler integration was never started** and
the flesh never existed to measure these four against. That is the intended cheap-failure
exit working, not an omission: the two weeks cost two weeks and bought two named mechanisms,
instead of buying an integration whose bars were already known not to clear.

**Consequence to carry:** the campaign never tested the owner's allocation thesis at all. A1
and A2 — "does the inflation hedge pay" and "do stocks and bonds fall together" — are the two
bars D-SP-6 added because the product tests robust asset *allocation*. They remain untested by
this campaign, on top of ER-14 (inflation does not reach the private book), which a clean pass
on them would not have touched anyway.

---

## 3. The two frontiers — what each escalation proved and what it revealed

The campaign was funded as a staged bet with a cheap-failure exit at each stage. It took two
stages and produced two frontiers. Both are worth reading as *results*, because in each case
the reason for the stop was measured and named rather than inferred.

### Frontier 1 (week 2, `78e71bd`) — transmission against ordering

**What was built.** A monthly hazard for season transitions — sixteen parameters: four season
intercepts, four log-dwell slopes, four covariate loadings for each of the two growth
directions — fitted by IRLS on **792 at-risk months carrying 35 growth-axis flips** (campaign
vintage `2026-08-10.1`, 813 months, 1953-04 to 2020-12). Covariates: curve slope, credit gap,
inflation gap, drawdown state.

**What it proved.**

1. **The pilot's attenuation is gone, and it was the whole story before.** The pilot's
   generation-time curve slope took **three values spanning 0.60 to 0.79 pp and was never once
   inverted**, while the hazard behind it was fitted on a covariate inverted in 18.3% of
   history's months. Every transmission verdict the pilot could have produced was decided by
   that before a coefficient was estimated. Week 2's generated curve carries **0.865 of
   history's dispersion** and inverts in **27.5%** of months.
2. **The transmission channel is real, significant, and correctly signed in both directions.**
   `cov_expanding[curve_slope]` = **−1.4888** (s.e. 0.5041, t = −2.95): a one-sd flatter curve
   nine months earlier multiplies the odds of an expansion turning by **exp(1.4888) = 4.43**.
   `cov_contracting[curve_slope]` = **+1.1904** (t = +3.04): a steeper curve raises the hazard
   of a contraction ending. Curves invert before downturns and steepen out of them; the fit
   found both halves independently.
3. **The lead time is an economic finding, chosen by likelihood on a pre-stated grid.** Nine
   months wins by 2.8 log-likelihood points over its nearest rival and 9.7 over the
   contemporaneous specification at identical degrees of freedom. **On this panel the yield
   curve leads the turn by about three quarters.**
4. **Duration dependence is present but weak** — every `log_dwell` t-ratio under 1.3, so the
   memoryless nesting cannot be rejected on 35 events. No D verdict rests on it.

**What it revealed — the frontier itself.** T1 and O1 are in direct opposition along
transmission strength. Scaling *only* `cov_expanding[curve_slope]` and re-judging: O1 falls
monotonically (0.5204 → 0.4821 unconditional) and passes only where transmission is switched
off or halved, which is where T1 fails hardest; T1 passes only at ×1.5 to ×3.0, where O1 has
already fallen below its bar. **There is no multiplier at which both pass.** T1 also
*saturates and reverses* — peaking at 1.878 near ×2 and falling to 1.526 by ×6 — because a
stronger coefficient raises the unconditional onset rate, which is the ratio's denominator.

**The diagnosis, measured not guessed.** The engine had causation running **curve → season**
and **no feedback running season → curve**:

| | share of inverted months that are expanding | base rate |
|---|---|---|
| **history** | **0.7651** | 0.7364 |
| week 2, unconditional | **0.4048** | 0.6896 |

In history the inverted curve sits where the turn **has not happened yet**. In week 2's engine
it sat **inside** the downturn — anti-concentrated exactly where T1 needs it concentrated.
Worse, the correctly-fitted `cov_contracting[curve_slope] = +1.1904` means a generated
contraction persists until the curve happens to steepen on its own, piling inverted months up
inside contractions. Two secondary contributors, both measured and both smaller: the engine
churns (439 growth-axis flips in 6,000 months, 7.3% monthly, against history's 35 in 792,
4.4%, which raises the unconditional onset rate to 0.32 against history's 0.24), and L1's
inflation is over-dispersed at 1.604×.

### Frontier 2 (week 3, `d5207f9` + `45dc10e`) — feedback strength against a phase channel

**What was built,** on D-SP-8's ruling. A season-state term in the curve equation — three new
coefficients, all estimated, no sign imposed:
`slope_t = c0 + c_u·û_t + c_C·(C_t − C̄) + c_E·(E_t − Ē) + c_K·(K_t − K̄) + e_t`, with `C` a
contracting indicator, `E` = log(spell age) when expanding, `K` = log(spell age) when
contracting, and `e` an AR(1) fitted by exact Gaussian ML. Fitted **jointly** with the hazard
in one likelihood, on 809 months.

**What it proved.**

1. **The feedback is real.** Likelihood ratio against no season feedback: **12.2272 on 3 df,
   p = 0.00664**. `c_C` = −0.1377 (t = −2.56), `c_E` = −0.0623 (t = −3.23), `c_K` = +0.0673
   (t = +2.73). Every coefficient carries the sign the economics predicts.
2. **The economics came out of the likelihood, not out of a hand.** Read as the centred season
   term the simulator actually adds: a **young expansion has the steepest curve** (+0.132 pp)
   and it flattens monotonically as the expansion matures (−0.167 pp by month 120) — policy
   tightening into strength; a **contraction opens at the unconditional mean** (−0.006 pp,
   because the curve inverted *before* the downturn and does not un-invert when it begins) and
   then steepens strongly as the downturn runs (+0.270 pp by month 60) — policy cutting.
3. **The hazard was not re-tuned to reach a bar.** The joint likelihood block-diagonalises on
   the historical panel (both processes are observed, so the cross-block information is exactly
   zero), and the hazard coefficients are **numerically unchanged from week 2 — max |difference|
   0.000e+00**, checked in code against the committed week-2 artifact. The coupling is at
   *generation* time, where the season is not observed.
4. **The diagnostic it was built to move, moved** — 0.4048 → **0.4893**, which is **23.5% of
   the 0.3603 gap to history**, and monotonically to **0.8376** past history's own 0.7651 when
   the fitted strength is scaled. The mechanism identified in week 2 is genuinely the
   mechanism.

**What it revealed — the new frontier.** Three things, all measured:

- **The fitted feedback is under-powered, and the reason is not the one that looked obvious.**
  The "the engine churns too fast for an age term to develop" hypothesis was **tested and
  rejected**: `mean log age` is literally what the loading multiplies, and it matches history
  to 0.04 on the expanding side (2.8638 generated vs 2.9017 historical). The actual reason is
  that the season term is worth **0.155 of a residual standard deviation** under the primary
  fit — 0.30 pp of total travel against a 0.73 pp residual sd. A term worth a sixth of the
  noise cannot reorganise a curve however right its sign is.
- **Pushing the mechanism harder does not buy the bar.** The diagnostic is monotone in feedback
  strength; T1 is not. T1 peaks near ×0.5 and *falls to a FAIL at ×4* before recovering at ×6 —
  the same saturation week 2 found along its own axis, and for the same reason.
- **O1 is unreachable along this axis at all,** and §2.2 says why. That is the second
  frontier: not "the feedback was too weak" but "the bar that remains is measuring something
  the built channel structurally cannot supply".

**Read together, the two frontiers are one story.** Week 2 said the missing thing is a curve
that responds to the cycle. Week 3 built exactly that, proved it real and correctly signed,
and found that (a) it is an order of magnitude too small against the residual it competes with
under the estimator the joint likelihood names, and (b) the bar still outstanding was never a
curve bar. Both remaining obstacles are stage-2 objects — model-implied conditional means —
which D-SP-6 explicitly does not fund. **The campaign hit the boundary of its funded scope,
twice, and stopped there both times without tuning past it.**

---

## 4. The three housekeeping rulings (owner, 2026-08-17, at close)

Each of these was an open stop-question in the week-3 report. Each is ruled here.

### 4.1 The soft-label refit remains SENSITIVITY-ONLY — it is not adopted

The exam's declared escalation (§11.0) fired: the label-stability obligation found the
transmission coefficient unstable across the classifier's perturbation arms, so the soft-label
refit was run and reported. **It is not adopted as the primary.** The baseline hard-label fit
remains the campaign's primary, as the exam's declared limitation specifies, and every number
in this verdict is a hard-label number.

This ruling costs something and the cost is stated: **every escalated arm makes the feedback
stronger, not weaker.** The soft-label refit gives `expansion_age` = −0.1039 against a
baseline of −0.0623 (a 2.155-SE move), and under it the season-to-residual ratio would be 0.26
rather than 0.155 — i.e. the arm that was *not* taken is the arm that would have read better
on the diagnostic. That is precisely why it is not taken. Choosing the arm that reads better,
after seeing which one reads better, is the thing frontier discipline exists to stop.

### 4.2 The amendment STANDS, with its disclosure attached

`AM-SPV2-2026-08-17-001` stands. It was taken before the measurement it governs, it changed no
threshold, it edited no hashed file, its argument (like-for-like conditioning) is the same one
that already fixed D3's windowing and round two's B6 base rates, and it reaches only the two
bars whose anchors are unconditional — so it cannot be reached for again.

**The disclosure travels with it permanently, in every reading of T1 and O1 from here on:** the
amended arm read more favourably on both bars at the moment of amending (T1 1.7636 vs 1.2302;
O1 0.5149 vs 0.5007), the amendment entry says so in its own payload, and every reading taken
under it is post-hoc-flagged per the seal's own convention. A reader who does not accept the
amendment gets a coherent alternative reading and it is published in full: on the premise arm
the final engine reads **T1 1.2231 FAIL and O1 0.4913 FAIL** — week 2's verdict unchanged, and
the campaign closes at FRONTIER on both causal bars instead of one. Nothing in this record
hides that reading or requires the amendment to be believed in order to follow it.

### 4.3 The post-hoc specification choices STAND, as disclosures

Three specification choices were made after a result was already visible. All three stand, and
all three are carried as disclosures rather than presented as if they had been there from the
start:

| choice | when it was made | why it is not goalpost-moving |
|---|---|---|
| the curve enters the hazard at a **9-month lag** rather than contemporaneously | after a first run showed a T1 miss | chosen by **likelihood** on a pre-stated grid, whole profile published, at constant parameter count on a common at-risk set; and **T1 barely moved** (1.2243 → 1.2302), which is itself evidence it was not chosen to move T1 |
| a contracting spell's label splits **`REC`/`STAG` at history's own rate** (0.7778, 7 of 9 spells), drawn once per spell | after the same first run | the rate was **read off history's labels**, not chosen: only 31 of the 95 contracting months at or above the 4.0 pp line are `STAG`, so the naive whole-season map would have put 111 of history's contracting months outside T1's numerator where history puts 31. Per-spell rather than per-month because a per-month coin would chop `REC` runs into spurious onsets — manufacturing T1 structure out of labelling noise |
| the **primary estimator** (exact ML) among two that disagree by 3.6× on the L1 link | pre-committed in the module docstring **before any bar was read** | it is the estimator the joint likelihood names; both estimators were run with and without the feedback, and the OLS arm supplies a disclosure and no verdict. This is the choice that makes §2.1's attribution table possible |

Neither of the first two rescued T1 in week 2 — which is itself the evidence that neither was
chosen to. They stand because their selection criteria are auditable and published, not
because their outcomes were convenient.

---

## 5. What this record buys a stage-2 campaign

The campaign did not produce a passing engine. It produced something a stage-2 proposal can be
costed against: **two named missing mechanisms, each with a measured size**, plus one working
subsystem that no longer needs to be re-argued.

### 5.1 Mechanism one — a model-implied curve, not a fitted residual

**What is missing.** The generated curve is L1-*linked*, not L1-*determined*. There is no
model-implied conditional mean: in a real economy the curve steepens *because* the downturn
arrives and policy is cut, and that is stage 2 of D-SP-6, explicitly not funded.

**Its measured size.**

- Under the primary exact-ML fit, **93.9% of the generated curve's variance is an exogenous
  AR(1) residual** (week 2's OLS arm: 59.6%). The `û` contribution is 0.1486 pp sd and the
  season term 0.1132 pp, against a 0.7314 pp residual.
- The fitted season term is worth **0.155 of a residual sd** (0.462 under OLS), and closes
  **23.5%** of the inverted-and-expanding gap at its fitted strength (0.4048 → 0.4893 against
  history's 0.7651).
- Where it does and does not bite, against history: the inverted share of **contracting**
  months goes 0.400 → 0.284 against history's 0.154 — about 40% of that error closed; the
  **expanding** side barely moves, 0.126 → 0.132 against history's 0.195. Sign right in both
  places, size short in both.
- **Scaling it is not the fix.** At ×4–×6 the diagnostic reaches and passes history's
  composition (0.7419, 0.8376) and T1 *fails at ×4* — the saturation is real and it is the
  same one week 2 found.

**What that costs a stage-2 proposal:** the target is not "a bigger loading". It is a curve
whose conditional mean is produced by the model, so that the season term is not competing
against a 0.73 pp exogenous residual for control of the same series.

### 5.2 Mechanism two — a growth ↔ inflation phase channel

**What is missing.** Nothing couples the *phase* of the two dials. The growth chain is the
fitted hazard; the inflation axis is read straight off L1; they are close to independent.

**Its measured size.**

- O1 shortfall is **≈0.06 on each move type**, evenly split: growth flips 0.5362 generated vs
  0.6176 historical; inflation crossings 0.5477 vs 0.6111. Both generated values sit near a
  coin flip.
- History's own phase relation — downturns tend to begin hot, disinflation tends to arrive
  during them — is worth about **0.09 on each move type**.
- O1's best value anywhere on the feedback frontier is **0.5156** (at ×0.5) against a floor of
  0.5181: **short by 0.0025 at the very best**, monotone-declining thereafter.
- A contributing, separable defect: the generated batch runs **56.0% inflation crossings vs
  history's 50.0%**, consistent with L1's `pi_gap` at **1.604×** history's dispersion.

**What that costs a stage-2 proposal:** the inflation axis must stop being read straight off
L1. That is a larger change than week 3's, and it is stage-2 territory. Also note the cheaper
partial: L1's `pi_gap` over-dispersion is a fact about the *pinned artifact*, not about
anything this campaign fitted, so it can be attacked independently of the phase channel.

### 5.3 What no longer needs re-arguing

- **Persistence is solved.** D1–D4 pass in all thirty-two frontier rows, both arms, four
  engines. The pilot's and spine-02's B4 recovery-persistence residue — the same flaw that
  sank `hier-flow` at G2 — does not survive a generation-time hazard with fitted duration
  dependence. A stage-2 campaign inherits this rather than re-litigating it.
- **The transmission channel is estimated, significant, and directionally correct in both
  directions,** with a likelihood-selected 9-month lead time. `spine-v2-fitted-params.json`
  and `spine-v2-feedback-params.json` carry maximum-likelihood estimates and nothing else; both
  regenerate byte-for-byte (`uv run python scripts/spine_v2_fit.py`,
  `uv run python scripts/spine_v2_feedback.py`; the latter verified across three runs).
- **The stream discipline is proved, not asserted.** `SPINE2_ATTEMPT_STRIDE = 32452843`, prime
  and coprime to the platform's 7919 and distinct from `ah.gen.spine.ATTEMPT_STRIDE`; five
  per-decade byte offsets disjoint from the platform's five; `assert_distinct_tapes` draws the
  first eight float64s of 520 streams and checks no two coincide and that no attempt-strided
  stream lands on the platform's `base_seed + 7919*k` ladder. This is the seed-stride collision
  that cost round one 18 of its 20 spines, and it does not recur here.
- **Two judge defects and a bar defect are logged from the prior rounds and still stand:** B1
  v3 (construct), B6 v3 (outcome-event match), B5 clustering-aware variance. The v2 exam
  confirmed two omissions as intended rather than fixing them — **no reaction-function bar** and
  **no hazard-frequency bar** — so a stage-2 exam starts from a known gap list rather than a
  blank sheet.

---

## 6. The campaign's own limitations register

Written here because a limitation that only appears in a working report is a limitation that
gets lost. These are the campaign's, not the exam's; the exam's own declared list (§12) stands
unchanged and is not restated.

### 6.1 Label instability — the sizes, not just the verdict

The sealed label-stability obligation was discharged in full at both stages (fit report §5,
feedback report §9). Every arm re-fits; the two down-weighting arms weight the curve block too,
so they cannot report a spurious zero. Movements are in units of each statistic's own baseline
standard error:

| statistic | baseline | s.e. | worst threshold arm | movement | soft-label refit | verdict |
|---|---|---|---|---|---|---|
| `cov_expanding[curve_slope]` (transmission) | −1.4888 | 0.5041 | infl +50 / growth −50 | **−1.044 SE** | −1.0785 (+0.814 SE) | **UNSTABLE — escalated** |
| `contracting` (`c_C`) | −0.1377 | 0.0539 | growth +50 | +0.626 SE | −0.2102 (−1.347 SE) | STABLE (threshold arms) |
| `expansion_age` (`c_E`) | −0.0623 | 0.0193 | growth −50 | **+1.074 SE** | −0.1039 (**−2.155 SE**) | **UNSTABLE — escalated** |
| `contraction_age` (`c_K`) | +0.0673 | 0.0246 | growth +50 | +0.905 SE | +0.1076 (+1.637 SE) | STABLE (threshold arms) |

**The magnitudes to carry:**

- **The transmission coefficient is pinned only to about a factor of two.** Range across all
  eleven arms: **−2.0152 to −0.9876**. Every arm keeps the right sign and significance; its
  *size* is not pinned better than 2× by a classifier whose two dials can each move half a
  point. Every transmission number in this campaign should be read with that beside it.
- **`expansion_age` — the coefficient the whole week-3 mechanism rests on — is pinned only to
  about a factor of 2.5.** Range −0.1039 to −0.0416. The soft-label refit moves it 2.155 SE,
  to two-thirds larger in magnitude than the baseline.
- **The reassuring arm:** down-weighting the months nearest the classification lines moves
  transmission by only 0.32 SE, so the estimate does not rest on borderline cases. It is the
  *joint* perturbation of both dials in opposite directions that bites — which is what the
  exam's own §3 had already found for D2.
- **The direction of the instability is inconvenient:** every escalated arm makes the mechanism
  *stronger*. §4.1 rules on that and does not take it.

### 6.2 The industrial-production-only recession dial

Inherited from the sealed grader, declared pre-seal (exam §12.1), and it bites this campaign
specifically. `regime_ruleset_v1` calls a month `REC` whenever trailing industrial-production
growth is at or below zero — **no NBER recession, no rise in unemployment, no credit stress and
no equity drawdown required.** A richer five-input classifier, built and compared under a
decision rule declared in advance, reassigns **37 of the 109 months the sealed classifier calls
recession** — a third of them, almost all to recovery — clustered at **2015-03→2015-08**,
**2016-04→2017-02** and **2019-04→2020-02** (the industrial/energy slump and the 2019
manufacturing slowdown: `usrec` = 0 throughout, unemployment falling, spreads normal, essentially
no drawdown).

**Why it matters more here than at the seal.** The exam's own §12.1 says the "simplicity wins"
verdict protects only **pooled medians**, not individual months, and that *anything reading
individual months — the generation-time hazard link above all — has no protection from this
result.* This campaign's central object is exactly that: a monthly hazard whose 35 events and
792 at-risk months are defined by this dial, and a curve block whose season regressors are
these labels. It cannot be fixed inside the campaign: `regime_ruleset_v1` is sealed
platform-wide (`src/ah/data/regime_thresholds.yaml`), and changing it would move the panel's
own labels, every anchor in this exam, and every prior round's sealed record.

### 6.3 The 93.9%-noise curve

The single most consequential limitation, and it is on the pass side of the ledger rather than
the fail side, which is why it is stated as its own entry. **T1 clears on the arm in which the
generated curve is 93.9% exogenous AR(1) residual.** Week 2 flagged 59.6% as a limitation; the
exact-ML estimator raises it to 93.9% *and* clears the bar. Either T1 is not sensitive to how
economically determined the curve is — a finding about T1 — or exact ML is the right estimator
for an inference and the wrong one for a generator. **The campaign did not resolve this and no
script can.** Any future use of T1 as evidence should carry the question with it.

### 6.4 The rest, in one place

- **Thirty-five events for sixteen parameters.** The hazard's at-risk set is 792 months
  carrying 35 growth-axis flips. That is thin, it is why several coefficients carry t-ratios
  under 1, and it is a fact about sixty-eight years of American economic history rather than
  about the estimator. Duration dependence in particular cannot be distinguished from
  memoryless on this sample.
- **The engine churns.** 439 growth-axis flips in 6,000 generated months (7.3% monthly) against
  history's 35 in 792 (4.4%), lifting the unconditional 12-month onset rate to 0.32 against
  history's 0.24 — and a high baseline compresses any lift T1 can show.
- **L1's `pi_gap` is over-dispersed at 1.604×** history's sd, and its `credit_gap` under-dispersed
  at 0.589. L1 was reused as-is per the brief; these are facts about the pinned artifact.
- **`CRI` is never emitted** by a no-flesh spine (no equity path to fire the crisis disjunct),
  so T1's crisis-only disclosure is **empty** in both loops — reported empty rather than faked.
- **Two counters, one mild inconsistency, disclosed:** the opening growth-spell age is drawn
  from history's empirical age-at-a-random-month distribution (from its own fifth stream, so
  week 2's tape is reproduced bit for bit), while the season dwell that drives the hazard still
  starts at 1 as in week 2. The two are different objects and the inconsistency at `t = 0` is
  stated rather than hidden.
- **The premise-accepted batch is compositionally hot** and that is why the arm question was
  decision-bearing: season occupancy 20.5 / 23.2 / 28.0 / 28.3 (recession / stagflation /
  recovery / expansion) against history's 13.6 / 13.9 / 47.2 / 25.3.
- **Nothing was integrated.** No file in `src/` or `schemas/` was edited by either week; both
  scripts and both parameter artifacts are new and unhashed by the seal. There is no engine in
  the platform to un-ship, and no world, preset or `TOY_ENGINE_VERSION` moved.

---

## 7. Status and disposition

**CLOSED**, owner-ruled 2026-08-17, at the second frontier.

- The seal stands with its single amendment; every prior round's verdicts stay frozen.
- Five of the ten bars have readings: **D1–D4 PASS**, **T1 QUALIFIED PASS**, **O1 FAIL**. Four
  bars — **A1, A2, R1, R2** — were never measured, because the flesh was never built.
- No parameter was tuned to move a bar in either week. Every scaled coefficient exists only
  inside a frontier sweep and is reported as a counterfactual. The soft-label refit fired, is
  reported, and was **not adopted** although it reads better.
- A **stage-2 campaign is not proposed here.** §5 states what one would inherit and what its
  two named targets would be; whether to fund it is the owner's decision and is open.
