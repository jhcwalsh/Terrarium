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

> **POST-REVIEW NOTE (2026-08-17) — read §8 before using any characterization below.** An
> independent verdict-integrity review re-ran both scripts, reproduced both artifacts
> byte-identically, recomputed all twelve sealed hashes as clean, and found **every bar
> reading and every PASS/FAIL word in this document correct against the seal**. It also
> returned **twelve findings**, all interpretive or omissive — and, in the reviewer's words,
> *"eleven of the twelve lean the same way: they make the week-3 mechanism look better, or the
> remaining gap look smaller, than the committed artifacts support."*
>
> **No verdict value and no PASS/FAIL word below changes.** What changes is the *reading*
> attached to several of them. **§8 supersedes the framing in §2.1, §2.2, §2.3, §3, §5.1,
> §5.2, §5.3 and §6 wherever the two conflict**, and three of its consequences should be known
> before the body is read at all: (i) the claim that **O1 is unreachable by this engine is NOT
> established** — the O1 FAIL stands under the sealed construct, but that construct carries a
> known censoring asymmetry worth **twice** the shortfall (§8.1); (ii) on the arm T1 is judged
> on, the fitted feedback's own contribution to T1 is **≈0 and slightly negative**, and **T1
> passes with the feedback switched off** (§8.2); (iii) the generation-time covariate *level*
> mismatches were undisclosed and are now in the register (§8.3, §6.5).

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
rounds' preregs (`spine-pilot-prereg.json`, `spine02-prereg.json`), and ~~six~~ **seven** scripts
[C10]
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

**(a) Most of the movement was the estimator, not the mechanism.**

> **SUPERSEDED IN FRAMING by §8.2 — read that first.** On the arm T1 is actually judged on,
> the correct lead is the script's own clean counterfactual: **×0.0 → ×1.0 moves T1 by
> −0.00036**, i.e. the fitted feedback's contribution to T1 is *approximately zero and
> slightly negative*, and **T1 passes at ×0.0 with the whole week-3 deliverable switched off**
> (1.91344 vs 1.91308). The estimator did the work; the mechanism did none of it on this arm.
> The +0.0748 row below is the **OLS-arm** reading of the feedback's worth — a labelled
> alternative, and the largest of the three available answers, not the headline.

The attribution as originally published, each row a real re-run rather than a decomposition on
paper:

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
short by 0.0025, and it ~~falls monotonically~~ **falls, though not monotonically** [C9 —
0.50870 at ×2.0 rises to 0.50933 at ×3.0 before falling to 0.48644 at ×4.0], to 0.4778 at ×6
(feedback report §8, which carries the same error).

> **SUPERSEDED IN FRAMING by §8.1 — the material review finding.** The decomposition table
> below is measured on a **different construct from the bar**: the sealed judge censors each
> decade's first twelve months (the trailing-inflation warm-up), the decomposition does not.
> Its generated overall of **0.5241 clears O1's sealed floor**, and the construct gap
> (**+0.0124**) is about **twice** the 0.0063 shortfall this section exists to diagnose. The
> sealed FAIL stands; the *diagnosis* below does not carry the weight originally put on it,
> and "O1 is unreachable" is not established. Two figures in the paragraphs below are also
> corrected there: "about 0.06 each" (actually 0.0814 and 0.0634) and history's "about 0.09
> on each move type" (unsupported).

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

The shortfall is spread across both move types — ~~about 0.06 each~~ **0.0814 on growth flips
and 0.0634 on inflation crossings** [C1b] — and both sit near
0.53, which is a coin flip. The engine's two dials are close to independent: the growth chain
is the fitted hazard, the inflation axis is read straight off L1, and **nothing couples their
phase**. History has a mild phase relation — downturns tend to begin hot, disinflation tends to
arrive during them — ~~worth about 0.09 on each move type~~ **[C1c: unsupported; history's own
per-move excess over a coin flip is 0.1176 and 0.1111, and 0.09 is closest to its *overall*
excess of 0.0972, which is not a per-move quantity]**. A season → curve channel cannot
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
feedback strength. ~~The dwell medians move by at most one month anywhere in that space.~~
**FALSE — corrected in §8.5 (C5).** Week-2 unconditional D4 runs 3, 4, 3, 2, 2, 2, 2, 1 and
premise D4 runs 3, 4, 4, 3, 2, 2, 2, 1 — a range of **three** months; and D3/D4 sit **exactly
on their bands' lower edges** at the sweeps' extremes (D4 = 1 against [1, 7] at ×6 on both arms
and at ×4 premise; D3 = 2 against [2, 8] at ×4/×6). The PASSes stand. The margin does not.

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
  fit — ~~0.30 pp~~ **0.4657 pp** [C7: the artifact's `season_term_range_on_generated_pp` is
  [−0.166497, +0.299185]; 0.2992 is the term's maximum, not its range] of total travel against
  a 0.73 pp residual sd. A term worth a sixth of the
  noise cannot reorganise a curve however right its sign is.
- **Pushing the mechanism harder does not buy the bar.** The diagnostic is monotone in feedback
  strength; T1 is not. T1 peaks near ×0.5 and *falls to a FAIL at ×4* before recovering at ×6 —
  the same saturation week 2 found along its own axis, and for the same reason.
- **O1 does not clear anywhere along this axis under the sealed judge,** and §2.2 says why.
  That is the second frontier: not "the feedback was too weak" but "the bar that remains is
  measuring something the built channel structurally cannot supply". **Narrowed by §8.1:** the
  original wording here was "**O1 is unreachable along this axis at all**", and the review
  established that this is **not** supported — the sealed construct's decade warm-up censoring
  costs ~0.0124, twice the shortfall, so what is established is that *O1 fails under the
  sealed construct*, not that the engine cannot reach the ordering the bar is about.

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
  months goes 0.400 → 0.284 against history's 0.154 — ~~about 40%~~ **47.3%** [C8] of that
  error closed; the
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

- O1 shortfall is ~~≈0.06 on each move type, evenly split~~ **0.0814 on growth flips and
  0.0634 on inflation crossings** [C1b — "about 0.06 each" understates the growth-flip gap by
  36%]: growth flips 0.5362 generated vs 0.6176 historical; inflation crossings 0.5477 vs
  0.6111. Both generated values sit near a coin flip. **And the generated side of this
  comparison is the un-censored internal path, not the sealed judge's — see §8.1.**
- ~~History's own phase relation … is worth about 0.09 on each move type.~~ **UNSUPPORTED
  [C1c].** History's per-move excess over a coin flip is **0.1176** and **0.1111**; the
  per-move history-minus-generated gaps are 0.0814 and 0.0634. The 0.09 figure matches
  neither — it is closest to history's *overall* excess (0.5972 − 0.5 = 0.0972), which is not
  a per-move-type quantity.
- O1's best value anywhere on the feedback frontier is **0.5156** (at ×0.5) against a floor of
  0.5181: **short by 0.0025 at the very best**, ~~monotone-declining~~ **declining but not
  monotonically** [C9] thereafter — and measured under the sealed judge's decade-warm-up
  censoring, which §8.1 shows is worth about twice the shortfall.
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
  first eight float64s of ~~520~~ **320** streams [C11: `n_streams_checked` = 520 is week 2's
  *four*-offset check; the five-offset check is `n_streams_checked_with_openage` = 320, and
  `openage_disjoint_from_every_other_layer` is true] and checks no two coincide and that no attempt-strided
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

**Added post-review [C6] — it reaches the campaign's only clean pass, not just the hazard.**
This entry originally applied the defect to the monthly hazard alone. The exam's own §12.1
carries a sharper consequence that was dropped: the **2019-04 → 2020-02** cluster "is *exactly
the right-censored recession spell D1 discloses* (2019-04 → 2020-12, observed minimum 21
months); the richer classifier keeps only its COVID tail." That links the grader defect
directly to a **D anchor** — i.e. to D1–D4, the campaign's only unqualified pass and the one
thing §5.3 hands to stage 2 as settled. The pooled medians are blunt instruments and survive
(§11.6's "simplicity wins" verdict protects exactly that and nothing finer), but the anchor
D1 is judged against rests partly on months a second reasonable classifier calls recoveries.

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

### 6.5 The O1 diagnostic is measured on a different construct from the O1 bar (added post-review)

The bar reads **0.511765** under the sealed judge; the decomposition that carries §2.2, §5.2
and stage-2 "mechanism two" reads **0.524138** on the simulator's internal season path — and
**0.5241 clears the sealed floor of 0.5180669**. The difference is the sealed judge's
per-decade trailing-inflation warm-up (`yoy[:12] = nan`, so the first 12 of every 120 months
lose their transitions) against a decomposition that scores a path "always defined
internally". **The gap, +0.0124 on the judged cell, is about twice the 0.0063 shortfall.**
Full reconciliation and the eight-cell table: §8.1.

### 6.6 Generation-time covariate LEVEL mismatches (added post-review)

Week 2 disclosed the covariates' **dispersion** ratios and this document repeated them. Their
**levels** were disclosed nowhere, and two of the three bear directly on a bar. From
`spine-v2-fitted-params.json`, `verification/covariate_dispersion`:

| covariate | simulated mean | historical mean | shift | why it matters |
|---|---|---|---|---|
| `curve_slope` | **0.4668 pp** | **0.7086 pp** | −0.242 pp = −0.29 of history's sd | T1's tight set is `slope < 0`, so the shift moves the conditioning population itself: generated tight share **0.274** vs history's **0.189** |
| `credit_gap` | **+3.188** | **−1.066** | +4.25 = +0.69 of history's sd | feeds `cov_contracting[credit_gap]` = +0.6689 (t = 2.01) |
| `drawdown_state` | fires **24.9%** of months | fires **11.7%** | 2.13× | feeds `cov_expanding[drawdown_state]` = +1.995, the largest coefficient in the expanding block; absent from §6.4 entirely |

**And the headline correction inside this entry:** §3 presents the generated curve inverting in
**27.5%** of months as the fix for the pilot's 0%. History's own inverted share is **18.3%**.
That is a **1.5× over-inversion, not a match** — the pilot's attenuation was replaced by a
mismatch in the other direction, and the verdict presented only the half that reads as a fix.

### 6.7 The drawdown covariate is a calibrated proxy, not the ruleset's dummy (added post-review)

`drawdown_state` is **not** the ruleset's equity-drawdown dummy. A no-flesh spine has no equity
path, so it is a **36-month trailing drawdown of L1's valuation state `v`**, with one constant
(**−0.3234**) calibrated so its firing rate on history equals the equity dummy's 11.685%; the
two dummies agree on **94.10%** of months. Disclosed in fit report §2, absent from this
register until the review. It is one calibrated constant, calibrated to history rather than to
a bar — and it is still a substitution inside the covariate that carries the largest expanding
coefficient (see §6.6's firing-rate row).

---

## 7. Status and disposition

**CLOSED**, owner-ruled 2026-08-17, at the second frontier. *(Read with §8: the review changed
no verdict value and no PASS/FAIL word, and it narrowed what the O1 FAIL and the T1 PASS can
be said to establish.)*

- The seal stands with its single construct amendment, plus one documentation follow-up
  (`AM-SPV2-2026-08-17-002`, §8.6) correcting a superseded anchor citation inside the first
  entry's rationale. Every prior round's verdicts stay frozen.
- Five of the ten bars have readings: **D1–D4 PASS**, **T1 QUALIFIED PASS**, **O1 FAIL under
  the sealed construct** (§8.1: the construct carries a censoring asymmetry worth twice the
  shortfall, so "unreachable" is not established). Four
  bars — **A1, A2, R1, R2** — were never measured, because the flesh was never built.
- No parameter was tuned to move a bar in either week. Every scaled coefficient exists only
  inside a frontier sweep and is reported as a counterfactual. The soft-label refit fired, is
  reported, and was **not adopted** although it reads better.
- A **stage-2 campaign is not proposed here.** §5 states what one would inherit and what its
  two named targets would be; whether to fund it is the owner's decision and is open.

---

## 8. Post-review corrections (verdict-integrity review, 2026-08-17)

An independent verdict-integrity review re-ran `scripts/spine_v2_fit.py` and
`scripts/spine_v2_feedback.py` read-only, and reported in three parts.

**What it certified.** Both artifacts regenerated **byte-identically**
(`spine-v2-fitted-params.json`, `spine-v2-feedback-params.json`). All twelve sealed hashes
recomputed **clean** against the working tree, exam document included. Every bar reading, all
32 frontier rows, both attribution tables, the 16 hazard coefficients, the curve block, the
label-stability arms, the premise tallies and every historical anchor re-derived from
`spine-v2-anchors.json` matched **to the digit**: *"No discrepancy at any digit."* Every
PASS/FAIL word was checked against the sealed bands and found **ALL CORRECT**, including the
NOT MEASURED status of A1/A2/R1/R2, verified against `bars_measured` and
`bars_deferred_to_week_4` in the artifact itself.

**What it found.** Twelve findings — one material, three substantive, eight minor — all
interpretive or omissive, and one pattern the review named explicitly:

> "**eleven of the twelve lean the same way: they make the week-3 mechanism look better, or
> the remaining gap look smaller, than the committed artifacts support.**"

**The rule this section follows** (round two's precedent, `2026-08-16-spine02-results.md`):
**no verdict value and no PASS/FAIL word changes** — none was found wrong. What is corrected is
the *characterization* attached to them. Where this section and the body conflict, **this
section governs**. Each correction quotes the reviewer's own finding.

### 8.1 C1 (MATERIAL) — the O1 diagnostic is measured on a different construct from the O1 bar

**The sealed verdict is unchanged: O1 FAILS at 0.511765 against the floor 0.5180669104991394.**
The review is explicit that it is not claiming a mis-scored bar:

> "To be clear about what this does and does not mean: **the sealed judge is the authority, O1
> FAILS at 0.511765, and I am not claiming the bar was mis-scored.** The seal defines the
> construct and the construct includes the warm-up. What I am claiming is that the verdict's
> diagnostic section is built on a different object than the bar, in the favourable direction,
> by more than the margin at issue — and says nothing about it."

**The two objects, named.** `judge_o1` (sealed) scores `clockwise_counts(_cells(decade,
sealed))` — the sealed grader's re-derivation from emitted labels plus simulated year-on-year
inflation — and `to_decade()` sets `yoy[:12] = np.nan` (*"the decade's own trailing-inflation
warm-up"*), so **the first 12 months of every decade are cell −1 and their transitions are
dropped**. The `o1_decomposition` used in §2.2 scores `d.season`, the simulator's internal
season index, documented in its own dataclass as *"always defined internally"*. The
transition/clockwise logic is otherwise byte-for-byte the same, so the entire gap is the
per-decade warm-up censoring.

**The measurement, all eight engine x arm cells — the decomposition reads higher every time:**

| engine | arm | sealed judge | decomposition | gap | decomposition vs floor 0.51807 |
|---|---|---|---|---|---|
| `week2` | unconditional | 0.514911 (259/503) | 0.522807 (298/570) | +0.0079 | PASS |
| `ml_link` | unconditional | 0.514563 (265/515) | 0.526496 (308/585) | +0.0119 | PASS |
| `ols_feedback` | unconditional | 0.504798 (263/521) | 0.513559 (303/590) | +0.0088 | FAIL |
| **`feedback` (the judged cell)** | **unconditional** | **0.511765 (261/510)** | **0.524138 (304/580)** | **+0.0124** | **PASS** |
| `week2` | premise | 0.500707 | 0.517576 | +0.0169 | FAIL |
| `ml_link` | premise | 0.496571 | 0.514758 | +0.0182 | FAIL |
| `ols_feedback` | premise | 0.507102 | 0.521212 | +0.0141 | PASS |
| `feedback` | premise | 0.491345 | 0.506373 | +0.0150 | FAIL |

**The three facts that follow, stated plainly:**

1. **The construct gap is twice the shortfall.** +0.0124 against a 0.0063 miss.
2. **The internal-path measurement clears the floor.** 0.5241 > 0.5180669. §2.2 printed
   "short by 0.0063" and then, four lines later, a table whose generated overall is 0.5241,
   *"with no reconciliation, no note that the two are different constructs, and no note that
   one of them is above the bar. A reader is left to assume the table explains the FAIL. It
   does not: on the table's own construct there is no FAIL to explain."*
3. **The asymmetry is this campaign's own named defect, not applied here.** The
   decomposition's *history* side is on the sealed construct (72 transitions / 43 clockwise,
   matching `l_grader_v2.full_ordering_v2` exactly) and loses one 12-month warm-up in 813
   months — **1.5%**. The bar's *generated* side loses 12 in every 120 — **10%**. As the review
   puts it: *"That is precisely the censoring mismatch **PRE-SEAL RULING 1 fixed for D1-D4**
   ... and that **AM-SPV2-2026-08-17-001 invoked for the arm choice**. The like-for-like
   principle was applied twice and not applied here."*

**What is therefore established, and what is not.**

- **Established:** *O1 fails under the sealed construct, and the sealed construct carries a
  known censoring asymmetry* — one that costs the generated side about twice the margin the
  bar was missed by.
- **NOT established:** *"O1 is unreachable by this engine."* That claim appeared in §3
  ("unreachable along this axis at all"), was echoed in §2.2, §5.2 and in the campaign's
  framing of its second frontier, and it is **withdrawn**. The frontier finding that survives
  is narrower and still real: **under the sealed judge, no feedback strength clears O1** (best
  0.5156 at x0.5), and O1's construct is a phase test the curve channel does not address.
  Whether a windowing-symmetric O1 would be cleared by this engine is **unmeasured** — the
  internal-path reading of the judged cell is above the floor, which is suggestive and is not
  a verdict, because it is not the sealed construct.
- **Consequence for stage 2:** any stage-2 seal must **re-derive the phase anchor under
  windowing-symmetric constructs before using O1's shortfall as a justification.** That caveat
  is carried into `2026-08-17-stage2-coupled-system-design.md` §WHY.

**Two sub-findings inside the same claim** (both corrected inline in §2.2 and §5.2):

- **C1b — "the shortfall is spread evenly ... about 0.06 each" is wrong.** The actual gaps are
  **0.0814** (growth flips) and **0.0634** (inflation crossings): *"'About 0.06 each'
  understates the growth-flip gap by 36%."* Self-correcting, since both numbers are printed
  beside the claim, but the characterization was wrong.
- **C1c — history's "about 0.09 on each move type" is UNSUPPORTED.** History's per-move excess
  over a coin flip is **0.1176** and **0.1111**; the per-move history-minus-generated gaps are
  0.0814 and 0.0634. *"`0.09` matches neither; it is closest to history's overall excess
  (0.5972 − 0.5 = 0.0972), which is not a per-move-type quantity."* The figure appeared in
  §2.2 and §5.2 here and in feedback report §7, stated each time as measured.

The qualitative diagnosis itself survives, and the review says so: it recomputed the mix effect
— holding the generated per-move rates at history's move mix changes the overall by only
**0.0028** — so the shortfall really is a per-move-type rate effect and not composition.

### 8.2 C2 (SUBSTANTIVE) — the feedback's own effect on the causal bars is ~0, and T1 passes with it OFF

**This is the reading §2.1(a) should have led with.** The artifact defines the x0.0 row of the
frontier as *"the primary engine with the three loadings zeroed, **keeping the unrestricted
fit's** intercept, u_hat loading and residual AR(1) ... the gap between them is the nuisance
parameters, **not a feedback effect**"* — i.e. **the artifact itself designates x0.0 as the
clean isolation of the feedback**. Measured on the arm the bars are judged on:

```
x0.0   T1 1.91343964  PASS      O1 0.51456311
x1.0   T1 1.91308121  PASS      O1 0.51176471
       dT1 = -0.00035842        dO1 = -0.00279840
```

**So the fitted season-to-curve feedback moves T1 by essentially zero, slightly negative, and
moves O1 AWAY from its floor — and T1 passes at x0.0, with the entire week-3 deliverable
switched off.**

T1's response is strongly non-additive (+0.0748 + 0.1421 = 0.2169 against a joint +0.1495, an
interaction of −0.0674), so "what the feedback is worth" has **three** answers, and the verdict
headlined the largest:

| reading of the feedback's T1 effect | value | status |
|---|---|---|
| **frontier x0.0 vs x1.0 — the script's own clean counterfactual** | **−0.00036** | **the primary reading** |
| exact-ML `feedback` vs `ml_link` (nuisance parameters refit under the restriction) | +0.0074 | secondary |
| under week 2's OLS estimator — the row §2.1(a) quoted | +0.0748 | labelled alternative only |

The review's judgement was UNDERSTATED rather than OVERSTATED, and it says why: *"The verdict
says 'most of that movement came from changing the estimator, not from the mechanism the week
was funded to build.' That is directionally honest and it is the reason I do not call this
OVERSTATED. But on the arm the verdict is judged on, it is not 'most' — it is all of it, and
the artifact records the number that says so. Neither −0.00036, −0.00280, nor 'T1 passes at
x0.0' appears anywhere in the verdict."* All three now appear, here and in §2.1(a).

**What this does not change.** T1's QUALIFIED PASS stands, and the qualification gets stronger,
not weaker: on the judged arm the pass is attributable to the estimator alone. §5.1's statement
of what stage 2 inherits is unaffected in substance — the mechanism is real, correctly signed,
significant (LR 12.23, p = 0.0066) and monotone in its own diagnostic — but "it moved T1 across
its lower edge" (feedback report §10, quoted approvingly in §3 here) must be read as **the
estimator moved T1 across its lower edge**.

### 8.3 C3 (SUBSTANTIVE) — the covariate LEVEL mismatches were undisclosed

> "**Generation-time covariate *level* mismatches are undisclosed — only dispersion ratios
> are.**"

Now in the register as **§6.6**, with the three shifts (curve mean −0.242 pp; `credit_gap`
+4.25; drawdown firing 2.13x) and, most consequentially, the correction that the generated
curve's **27.5% inverted share against history's 18.3% is a 1.5x over-inversion rather than a
match** — §3 presented it as the fix for the pilot's 0% without the comparison. The tight-set
consequence is direct: T1 conditions on `slope < 0`, so the generated tight share is 0.274
against history's 0.189, and the conditioning population itself differs.

### 8.4 C4 (MINOR) — the drawdown covariate is a proxy substitution

> "It is a 36-month trailing drawdown of L1's valuation state `v`, standing in for the
> ruleset's equity-drawdown dummy, with one constant (−0.3234) calibrated so the historical
> firing rates match; the two agree on 94.1% of months. Disclosed in fit report §2; absent
> from the verdict's register."

Now in the register as **§6.7**.

### 8.5 C5–C11 — the overstated dwell margin and the six numeric slips

| # | claim as published | correction | where |
|---|---|---|---|
| **C5** (substantive) | "The dwell medians move by **at most one month** anywhere in that space" | **FALSE.** Week-2 unconditional D4 runs 3, 4, 3, 2, 2, 2, 2, 1; premise D4 runs 3, 4, 4, 3, 2, 2, 2, 1 — **a range of three**. D3/D4 also sit **exactly on their bands' lower edges** at the sweep extremes (D4 = 1 vs [1, 7] at x6 both arms and x4 premise; D3 = 2 vs [2, 8] at x4/x6). "PASS everywhere" and "these do not miss" both stand; the *margin* was overstated — and, as the review notes, *"since 'persistence is solved' is the one clean thing §5.3 hands to stage 2, the margin is overstated."* | §2.3, corrected inline |
| **C6** (minor) | §6.2 applied the grader defect to the hazard only | The exam §12.1 consequence that was dropped: the 2019-04 -> 2020-02 cluster **is exactly the right-censored recession spell D1 discloses**, so the defect reaches a **D anchor** — the campaign's only clean pass | §6.2, added inline |
| **C7** (minor) | "**0.30 pp** of total travel" | **0.4657 pp.** The artifact records `season_term_range_on_generated_pp` = [−0.166497, +0.299185]; **0.2992 is the maximum, not the range**. From the published coefficients the theoretical flattest-to-steepest is 0.436 pp. Understated the mechanism by ~35%. The load-bearing 0.155 sd ratio is separately correct (`season_term_sd_over_residual_sd` = 0.154721), so the conclusion is unaffected | §5.1, corrected inline |
| **C8** (minor) | "about **40%** of that error closed" | **47.3%** — (0.4002 − 0.2835)/(0.4002 − 0.1535). Understated | §5.1, corrected inline |
| **C9** (minor) | O1 "**falls monotonically** ... to 0.4778 at x6" | **Not monotone:** 0.50870 at x2.0 -> **0.50933** at x3.0 -> 0.48644 at x4.0. Same error in feedback report §8. The "no feedback strength clears O1" finding survives | §2.2 and §5.2, corrected inline |
| **C10** (minor) | "**six** scripts", seven then listed | **Seven.** The twelve hashed paths are 5 documents + 7 scripts; the total was right, the interior count was not | §1, corrected inline |
| **C11** (minor) | "`assert_distinct_tapes` draws the first eight float64s of **520** streams", attached to the five-offset claim | `n_streams_checked` = 520 is week 2's **four**-offset check; the five-offset check is `n_streams_checked_with_openage` = **320**. The substantive claim stands: five offsets, disjoint from the platform's five, `openage_disjoint_from_every_other_layer` = true | §5.3, corrected inline |

### 8.6 C12 — the amendment's superseded anchor citation, corrected by follow-up amendment

The one finding that is **not** in this document: it is inside the sealed log.

> "the rationale states O1's floor is 'the lower edge of the clockwise-fraction interval
> measured over the WHOLE panel (**68 transitions, 41 clockwise**)'. Per
> `spine-v2-anchors.json`, 68/41 is the **superseded pre-mapping-fix** anchor ... The sealed
> floor `0.5180669104991394` is cut from grader_v2's **72 transitions / 43 clockwise**. The
> floor *value* quoted is correct; the provenance sentence names the wrong anchor. Immaterial
> to the ruling, but it is a factual error inside a sealed amendment. The verdict's §1 table
> gets it right (`0.5972 over 72 transitions`)."

**How it was handled.** `AM-SPV2-2026-08-17-001` was **not edited** — the log is the record, and
editing an entry would erase the thing the log exists to keep. A follow-up entry,
**`AM-SPV2-2026-08-17-002`** (type `documentation`, post-hoc, appended through the same log
machinery and machine-checked by `tests/test_spine_v2_seal.py`), records the correction: the
sealed floor is cut from `l_grader_v2.full_ordering_v2` — **72 transitions, 43 clockwise,
clockwise fraction 0.5972, block-24m bootstrap CI lower edge 0.5180669104991394** — while **68
transitions / 41 clockwise** (fraction 0.6029, floor 0.5185185185185185) is the pre-mapping-fix
`e_ordering` anchor, superseded by PRE-SEAL RULING 2 and retained in the anchors file only
under `exam_bars_superseded`. **No threshold moves, no hashed file is edited, and the ruling of
AM-SPV2-2026-08-17-001 is unchanged in every respect** — only its provenance sentence is
corrected, in the log, where a reader of the first entry will find it.

### 8.7 Two review observations that are not corrections, recorded anyway

- **On the 93.9% noise share (judged FAIR).** The review endorsed §2.1(b)/§6.3 — *"That is the
  right call and it is not hedged"* — with two caveats. First, the share is a **sum of squares
  of three component sds**, not a covariance-aware decomposition of the realised generated
  slope, and the components are not independent by construction; the artifact's own reading
  text is more careful, calling the season/residual ratio *"a ceiling"*. Second, the verdict
  left both horns open, but **its own four-engine set leans to the first**: `ols_feedback`
  **passes** T1 at 49.4% noise while `week2` **fails** at 59.6%, so **T1's verdict is not
  ordered by noise share** — evidence for "T1 is insensitive to how economically determined the
  curve is", which went unremarked. It is remarked now.
- **On §1's bar table (presentational, not an error).** "round two: PASS" and "round two: FAIL"
  for R1/R2 sit in a column headed *historical anchor*; those are prior-round verdicts, not
  anchors. §2 and §7 are unambiguous, so no reader is actually misled — noted for a future
  table.
