# The stage-2 campaign — the verdict. FRONTIER at nine of twelve, with the whole exam measured for the first time.

**Date:** 2026-08-18 · **Branch:** `stage2-02-fit` · **Status: FRONTIER. No owner ruling
taken.** Funding ruling: `governance/decision-register.md` **D-SP-9** (2026-08-17) — the
coupled monthly system over growth, inflation, policy stance and curve, fitted jointly, plus
"the full exam weeks the v2 campaign never ran".

**What this document is.** The campaign's verdict record: what was sealed, what the sealed
bars read at the end, what the attribution proved about which arrow did the work, what the
allocation bars found the first time anyone ran them, and what is left open for the owner. It
is a *verdict* document, not a new measurement — every number in it is quoted from a committed
record and carries its source. **Nothing here re-judges anything, and every PASS/FAIL word
below is the sealed judge's own.**

> **POST-REVIEW NOTE (2026-08-18) — read §7 before using any characterization below.** An
> independent verdict-integrity review re-ran both judging entry points, regenerated **both
> artifacts byte-identically**, recomputed **all eleven sealed hashes clean**, reproduced **all
> twelve bar readings to the digit**, re-derived the three interpretive claims from the
> committed artifacts, and found **every PASS/FAIL word in this document correct against the
> sealed bands — 12 of 12**. It also returned **eleven findings**, all interpretive or omissive.
>
> **No verdict value and no PASS/FAIL word changes.** What changes is the *reading* attached to
> several of them. **§7 supersedes the framing in §1, §2, §2.4, §2.5, §3.1 and §5.2 wherever the
> two conflict**, and three of its consequences should be known before the body is read at all:
> (i) the "**exactly 0.0** drift" on the eight re-read bars is a **twelve-decimal rounding
> artifact** — the measured worst drift is **2.862e−13** (§7.2, the conclusion is untouched);
> (ii) the coupling's own age signature separates the wrong way in the **1–12 month** bucket, not
> the 37+ one, and the 37+ bucket separates the **right** way (§7.1); and (iii) the stage-2
> engine's generation-time covariate **levels** were undisclosed, exactly as they were in v2, and
> `T1`'s conditioning population has moved from **over**- to **under**-inverted between campaigns
> (§7.3, §5.6).
>
> **The pattern, stated plainly and it is not v2's.** Six findings make the engine or the record
> look better than the artifacts support (§7.2, §7.3, §7.4, §7.6, §7.7, §7.11); **three make the
> funded coupling look *more* inert than the artifacts support** (§7.1, §7.8, §7.9) — i.e. they
> lean *against* this document's own headline. Two are neutral.

**The records it stands on** (all committed, all on this branch):

| record | commit | what it is |
|---|---|---|
| `docs/superpowers/specs/2026-08-18-stage2-exam-delta.md` | `d67a455` (sealed) | the stage-2 exam — two new bars, ten carried byte-frozen, six rulings, its own limitations register |
| `docs/superpowers/specs/stage2-prereg.json` | `d67a455` | the seal — thresholds plus the sha256 of the eleven files that judge them |
| `docs/superpowers/specs/stage2-anchors.json` + `2026-08-17-stage2-anchors.md` | `be13c2f`, `b730146` | what made `P1` and `P2` numbers: `M3`, `M4`, `M5`, the windowing-symmetric phase re-derivation, the generated side's own null |
| `docs/superpowers/specs/stage2-antitest-results.json` | `3b54a58` | four monotone sweeps, five controls, and `P1`'s measured size |
| `docs/superpowers/specs/2026-08-18-stage2-fit-report.md` | `f5b718b` | **week A**: the coupled system fitted jointly, the eight pre-flesh bars, the attribution |
| `docs/superpowers/specs/stage2-fitted-params.json` | `0a5884d`, `0c7aa7e` | week A's artifact, `sha256 0604e555…`, byte-identical on a re-run |
| `docs/superpowers/specs/2026-08-18-stage2-week-c-report.md` | `f37f9a3`, `dbd0954` | **week C**: the flesh, and the four bars nobody had ever run |
| `docs/superpowers/specs/stage2-weekc-results.json` | `f37f9a3` | week C's artifact, `sha256 565413ac…`, byte-identical on a re-run |

Prior campaigns, frozen and not reopened by anything here: the pilot
(`2026-08-15-spine-pilot-results.md`), spine-02 (`2026-08-16-spine02-results.md`) and the v2
campaign (`2026-08-17-spine-v2-results.md`, closed at its second frontier with its own §8
post-review corrections).

---

## The one-paragraph answer

Stage 2 was funded to build one coupled monthly system — growth driving inflation, policy
leaning on both, the curve reading the policy rule, the curve driving the growth hazard — and
to run it against the exam the v2 campaign sealed and only half-ran. It did both. **Nine of
the twelve bars pass and three fail**, and for the first time in four rounds **every bar in
the exam has an actual reading**: `A1`, `A2`, `R1` and `R2` had never been measured by any
prior round, because none of them had built the flesh. The three failures are `P2` (**above**
its band, on dispersion stage 2 inherited rather than introduced), `A2` (all three conditions)
and `R2` (one seam in six thousand months). **Two findings outrank the scoreboard.** The
first is that **the arrow stage 2 was funded to build is inert**: `lam_x`, growth → inflation,
is significant on the panel at t = +5.95 and switching it off changes `O1` by −0.0012 and
flips no verdict; what moved the bars is the *other* change, the curve reading the
rule-implied policy rate, and `P1` — the bar written to test the funded arrow — passes through
the **reverse** channel, inflation → curve → growth, which no bar in the sealed exam can
distinguish from the intended one. The second is `A2`'s, and it is the campaign's headline:
**the flesh carries history's stock–bond correlation flip in the months it selects** — judged
on the inflation those drawn months actually carried, `A2` passes all three conditions with
room (+0.176 against −0.172, gap +0.348, 92.8% of windows) — **but the spine's conditioning
reaches only 8.2% of a decade**, so the world's story and the world's markets agree on 60.6%
of judged months against 59.2% expected if they were independent. That is the pilot-era
"real at month scale and incoherent at story scale" failure, now **measured and priced** rather
than argued. Nothing was tuned, no threshold was touched, no bar was invented, no file inside
either seal was edited, and no line of `src/` was changed.

---

## 1. What was sealed, and when

**The seal.** `docs/superpowers/specs/stage2-prereg.json`, schema `stage2-prereg-1`,
`sealed_at_utc` **2026-08-18T01:39:46-07:00**, recorded as of HEAD commit
`3b54a5814be3d5f3515cdfa4fc7e4d478b45134d` and committed at `d67a455` ("SEAL — the stage-2
exam pre-registered before the coupled fit"). **The seal was taken before the coupled fit was
run** — before `scripts/stage2_fit.py` existed as a fitting run and before any stage-2 bar had
a value. The exam delta's own opening sentence states the reason: *"a bar written after a
coupling is fitted is a description, not a test."*

**`amendments` is empty.** Nothing was amended in stage 2 — no threshold moved, no hashed file
was edited, no arm was re-chosen after a reading. (The v2 campaign's single construct amendment
`AM-SPV2-2026-08-17-001`, and its documentation follow-up `-002`, are carried inside the
byte-frozen v2 seal and continue to govern which arm `T1` and `O1` are judged on.)

**What the seal hashes.** Eleven paths — thresholds and judging code together: the exam delta
itself, `stage2-anchors.json`, `stage2-antitest-results.json`, the **v2 seal and v2 anchors
loaded whole**, and ~~five~~ **six** scripts [C5] (`stage2_anchors.py`, `stage2_antitest.py`,
`stage2_report.py`, `stage2_seal.py`, plus `spine_v2_report.py` and `spine_v2_grader.py`) — the
eleven are **5 documents/JSON + 6 scripts**, all recomputed clean by the review. The two pilot scripts
that carry `R1` and `R2` (`spine_pilot_b3.py`, `spine_pilot_report.py`) are reached through the
v2 seal, which is itself hashed, and recomputed by `tests/test_spine_v2_seal.py` on every run —
so the chain is closed by a machine check rather than by a convention.

**The twelve bars, as sealed.** Ten carried byte-frozen from the v2 exam — not re-derived, not
re-anchored, not re-implemented; `stage2_report.judge_carried_v2` imports `spine_v2_report`'s
own judges and hands them the v2 seal loaded whole. Two new, `P1` and `P2`.

| tier | code | the bar | sealed threshold |
|---|---|---|---|
| causal | **T1** | does tightening cause downturns? | lift inside **[1.7752827491108736, 3.3473622102535145]** |
| causal | **O1** | do the seasons turn the right way round? | clockwise fraction **≥ 0.5180669104991394** |
| persistence | **D1** | recession spell length | pooled median inside **[0.0, 5.0]** months |
| persistence | **D2** | stagflation spell length | pooled median inside **[1.0, 7.0]** months |
| persistence | **D3** | recovery spell length | pooled median inside **[2.0, 8.0]** months |
| persistence | **D4** | expansion spell length | pooled median inside **[1.0, 7.0]** months |
| phase | **P1** | do the two dials keep time with each other? | departure from the batch's own null ≥ **0.040330202948** (growth flips) **and** ≥ **0.031445706759** (inflation crossings) |
| curve | **P2** | is the curve made of economics? | strict economic share inside **[0.391706974667, 0.673370849738]** |
| allocation | **A1** | does the inflation hedge pay in high inflation? | directional, and the high spread inside **[−5.053054679081145, +32.31605649965673]** pp |
| allocation | **A2** | do stocks and bonds fall together in high inflation? | correlation > 0, **and** gap ≥ **0.13609378139729844**, **and** ≥ **80%** of 3-year windows positive |
| no-regression | **R1** | severity still bites the book | monotone coverage across `[15, 35, 40, 55]` private points, ≥ **1/20** breach at 55 |
| no-regression | **R2** | eras don't teleport at the seams | join jump ≤ **2.5** pp, p95 adjacent change ≤ **0.9292389954** pp |

Batch size `n_seeds = 50`, carried unchanged from the v2 seal. `R1`'s b3 grid keeps its own
byte-frozen `n_seeds = 20`.

**The two new bars came with obligations and they were discharged before the seal** (exam delta
§5, artifact `stage2-antitest-results.json`): four anti-test sweeps, **all monotone
non-decreasing**, and five controls, **all holding** — including the two the design document
named as the gaming routes (an uncoupled engine, and an engine that shrinks its noise to buy an
economic share; the latter fails **on the upper side** in 12 of 12 batches, which is the
mechanism by which `P2` catches this campaign's own engine).

---

## 2. The final bar readings, under the sealed constructs

All readings by the sealed judges themselves. The eight pre-flesh bars are quoted from
`stage2-fitted-params.json` (week A); the four flesh bars from `stage2-weekc-results.json`
(week C). **Every PASS/FAIL word in this table is the judge's.**

| bar | arm | sealed band / floor | measured | verdict | week |
|---|---|---|---|---|---|
| **T1** | unconditional | [1.775283, 3.347362] | **2.239246798804** | **PASS** | A |
| **O1** | unconditional | ≥ 0.5180669104991394 | **0.560824742268** | **PASS** | A |
| **D1** | unconditional | [0.0, 5.0] months | **2.0** | **PASS** | A |
| **D2** | unconditional | [1.0, 7.0] months | **4.0** | **PASS** | A |
| **D3** | unconditional | [2.0, 8.0] months | **4.0** | **PASS** | A |
| **D4** | unconditional | [1.0, 7.0] months | **3.0** | **PASS** | A |
| **P1** | unconditional | 0.040330 / 0.031446 | **+0.101752 / +0.073520** (binding margin **+0.042073930959**) | **PASS** | A |
| **P2** | unconditional | [0.391707, 0.673371] | **0.770682653481** | **FAIL — above the band** | A |
| **A1** | unconditional | direction, high spread inside [−5.053, +32.316] pp | **+0.378055215669 pp**; high **+2.142367937923 pp** | **PASS** | **C** |
| **A2** | unconditional | corr > 0; gap ≥ 0.136094; ≥ 80% of windows | **−0.017742671153; +0.060911208541; 0.4760** | **FAIL — all three** | **C** |
| **R1** | **declared premise**, b3 ladder, n = 20 [C4] | monotone coverage; ≥ 1/20 breach at 55 | medians **[0.098065, 0.291855, 0.361632, 0.667991]**; breach **4/20** | **PASS** | **C** |
| **R2** | unconditional | join ≤ 2.5 pp; p95 ≤ 0.9292 pp | **4.132499999786 pp**; **0.883035257076 pp** | **FAIL — join half only** | **C** |

> **Nine of twelve pass. Three fail.** And **all twelve have readings** — the first time in
> four rounds of this campaign line. The v2 campaign closed with `A1`, `A2`, `R1` and `R2`
> **NOT MEASURED**, and its own §2.4 said why: they need the flesh, and no round had built it.

**Two facts about the batch, so the scoreboard is not read as more than it is.** `A1`, `A2`,
`R2` and the eight pre-flesh bars are all read on the **same unconditional 50-decade batch at
seed 20260821** — week A's own verification seed — so a week-C verdict is attributable to the
flesh alone. **`R1` is the exception and it matters** [C4]: `stage2-weekc-results.json` records
`batches.R1.arm = "declared premise"` against `batches.A1_A2_R2.arm = "unconditional"`, so the
one flesh bar that passes cleanly is read on **the arm on which `A1`'s sign reverses** (§2.3).
That is the carried bar's own byte-frozen construction and changing it is the thing a carried
bar exists to prevent — but the two are not like-for-like and the original table did not say so. That claim is not prose: the eight pre-flesh bars were **re-judged on week C's own
fleshed batch** and checked against week A's artifact — ~~at **exactly 0.0 drift on all
eight**~~ **at a worst absolute drift of 2.862e−13** [C2 — the `0.0` in
`spine_identity.max_abs_drift` is the artifact's twelve-decimal rounding, not a measurement; the
unrounded figure is what `scripts/stage2_weekc.py` prints, and `spine_identity` **raises** above
1e−12, so the conclusion is untouched and the phrasing was wrong]. And week A's engine is
**frozen input** to week C: 42 coefficients re-checked, worst absolute drift **4.841e−13**
against a 1e−11 tolerance, a drift raises.

### 2.1 THE headline — `A2`, the flesh, and 8.2%

**The sealed reading is a FAIL and it stands: `A2` fails all three of its conditions.**

| condition | generated | required | verdict |
|---|---|---|---|
| correlation, high inflation | **−0.017742671153** | > 0 | **FAIL** |
| difference, high − low | **+0.060911208541** | ≥ 0.136093781397 | **FAIL** |
| share of 3-year windows positive, high | **0.4760** (1,500 windows) | ≥ 0.80 | **FAIL** |

History, for reference: **+0.30125 / −0.01823**, difference **0.31949**, **94.7%** of
high-inflation windows positive.

**And now the finding.** On the *same* batch, the *same* real months, the *same* sealed judge
— with the decade's inflation read off **the months actually drawn** instead of off the spine
that chose them (`disclosures.A1_A2_on_the_flesh_realised_inflation`):

| condition | judged on the spine's inflation *(the reading)* | judged on the drawn months' inflation *(disclosure)* | required |
|---|---|---|---|
| correlation, high | −0.017742671153 | **+0.176478725447** | > 0 |
| correlation, low | −0.078653879694 | **−0.171844713810** | — |
| difference | +0.060911208541 | **+0.348323439257** | ≥ 0.136093781397 |
| share positive, high | 0.4760 | **0.928499496475** | ≥ 0.80 |
| **would the bar pass?** | **no, on all three** | **yes, on all three** | |

`A1` under the same substitution: difference **+5.329708735843 pp** (high +6.065, low +0.735),
against the spine-inflation reading's +0.378 and history's +3.493.

**Said plainly: the months this compiler selects carry history's stock–bond correlation flip,
at very nearly history's own size. What fails is the link between the world's inflation dial
and the months it selects.**

**This is a disclosure and it is not a verdict.** It is reported, never judged; §4's first
stop-question is exactly which series a fleshed decade should report, and the primary taken is
the spine's, for the three reasons in week C §8.1 (the exam's own words are "compiled **onto
the spine**"; every other bar in the exam reads that series — `P1`'s hot dial *is* it; and it
is the only series the sealed 12-month warm-up rule fits).

**The alignment was measured rather than assumed** (`a_bar_diagnostics`):

| quantity | value |
|---|---|
| months judged (after the sealed 12-month warm-up) | 5,400 |
| share the spine's dial calls high (≥ 4%) | 0.338148148148 |
| share the drawn months' own inflation calls high | 0.217037037037 |
| **the two dials agree on** | **0.605925925926** |
| **agreement expected if they were statistically independent** | **0.591596159122** |
| mean inflation of a drawn month when the spine says "high" | **3.224842333401 pp** |
| mean inflation of a drawn month when the spine says "low" | **3.025038592897 pp** |

> **Agreement beats chance by 1.4 percentage points.** A "high" month's own inflation averages
> 0.20 pp above a "low" month's, and **both sit below the 3.3513 pp era line the pools are
> conditioned on**. The world's story and the world's markets are, to a first approximation,
> independent.

**And the structural cause, measured, and NOT stage 2's.** The compiler's quadrant conditioning
selects a month only when a block *starts* — the decade's first month, a join, or a forced
re-entry. Every other month is the panel's own next row, drawn for no reason but contiguity.

| quantity | value |
|---|---|
| months in the batch | 6,000 |
| months selected for their quadrant | **494** |
| **share of a decade the conditioning reaches** | **0.082333333333 — 8.2%** |

The declared mean block is 6 months, which would put the figure near 17%; the realised figure
is half that, because a join happens only when the block-break draw fires **and** the era-safe
join filter leaves a candidate — otherwise the block simply continues. **The spine chooses
about one month in twelve and inherits the other eleven.** A dial that sets 8% of a decade
cannot make the other 92% agree with it, and `A1`/`A2` are bars about all of it.

**Why this is the campaign's headline rather than a week-C footnote.** The conditioned
compiler's own design document (`2026-08-15-spine-conditioned-compiler-design.md` §3.3) states
the promise in as many words:

> *"the owner's returns/volatility/correlation point lands for free: months cast from real
> stagflation carry stagflation's true joint behaviour — including the equity–bond correlation
> flip — because they ARE stagflation months."*

That promise is **half kept, and the halves are now separately measured.** The flesh delivers
it: months drawn from genuinely high-inflation history do carry the flip, at +0.176 against
−0.172. The conditioning does not: only 8.2% of a decade's months are cast for their quadrant
at all, so "months cast from real stagflation" describes one month in twelve. The same design
document names the failure it was built to kill — *"a decade that is real at month scale and
incoherent at story scale"* — and that failure is **not dead; it is quantified.** It was
invisible until the allocation bars were run, because `A1` and `A2` are the only two bars in the
exam that condition asset behaviour on the spine's dial, and no round before this one had ever
run them.

**It belongs in the engine-realism register, and it is inherited whole.** Selection-only,
6-month mean blocks and era-safe joins are the sealed compiler design (owner ruling R1,
2026-08-15). Stage 2 changed none of them. §4's second stop-question asks the owner to classify
it: ER-class register entry, funded fix, or declared property — and notes that a fix means
changing block length or the join rule, which moves `R2` and `D1`–`D4` as a side effect.

### 2.2 `P2` — a FAIL from **above**, on dispersion stage 2 inherited

`P2` reads **0.770682653481** against a sealed band of **[0.391707, 0.673371]** and fails on
the **upper** side: the generated yield curve is *too* determined by the economy, not too
little. The components (week A §4.3):

| component | generated sd (pp) | history's (pp) |
|---|---|---|
| policy rule (`c_i`·`i_rule`) | **1.365831** | 0.836190 |
| inflation gap (`c_x`·`x`) | 0.106533 | 0.078326 |
| season term | 0.059041 | 0.053794 |
| AR(1) residual, stationary (a model parameter) | 0.747993 | 0.747993 |
| **strict economic share** | **0.770683** | 0.558667 |

**The exogenous block is empty on both sides** — that is the like-for-like the primary curve arm
(`PRIMARY_CURVE_ARM = "m4_rule_implied"`, fixed in code before any bar was read) was chosen to
get, and it is `P2`'s fourth anti-test obligation discharged structurally rather than argued.
So the overshoot is not a classification argument. It is **dispersion**:

| quantity | generated ÷ history |
|---|---|
| rule-implied policy rate | **1.635×** |
| yield-curve slope | **1.735×** |
| inflation gap | 1.356× |

Generated rule-implied rate sd **5.683 pp** against history's **3.476 pp**; generated slope sd
**1.4623 pp** against history's **0.8427 pp**. **The coefficients are history's — nothing was
scaled** — so the numerator of a *share* rises with no coupling changing, and the curve inherits
it. That dispersion is **L1's**: fifty decades each re-draw their initial states from the
posterior, and the spread of L1's `r*` and `pi*` across those draws is wider than the single
68-year path history realised. No stage-2 coefficient touches it.

**`P2` is doing exactly the job its upper edge was written for.** The exam delta §4.6: *"Above
it, the curve is a deterministic readout of the state and a player can learn a rule that no real
market would ever reward."* The anti-test control `P2_noise_shrink` fails an
economic-share-gaming engine **on the upper side in 12 of 12 batches**; the same edge caught this
engine. Whether stage 2 *owns* a failure it inherited is §4's third stop-question, and three
defensible readings are named there rather than resolved here.

**A size diagnosis, not a fix.** The economic block's variance is 1.8803 against the 1.1535 the
band's upper edge allows at this residual — an overshoot of about **63%**, not an order of
magnitude. And the dispersion ratios say where the 63% lives: in L1's across-decade state
spread, not in the curve's coefficients. **The right fix is not on the loading axis at all** —
see §3.3 on the ×0.5 row that was left where it was.

### 2.3 `A1` — a PASS at 11% of history's margin, and the sign reverses under the premise

| quantity | generated | history |
|---|---|---|
| spread, high inflation (≥ 4%) | **+2.142367937923 pp/yr** | +4.8720 pp/yr |
| spread, low inflation (< 4%) | **+1.764312722254 pp/yr** | +1.3787 pp/yr |
| **difference** | **+0.378055215669 pp** | **+3.4933 pp** |
| months, high / low | 1,826 / 3,574 | 225 / 576 |

> **`A1` PASSES**: directional PASS (+0.3781 > 0), containment PASS (+2.1424 inside
> [−5.053, +32.316]).

**Read the size before reading the verdict.** The direction is right and the effect is **11% of
history's**. The exam is explicit that the containment half is *"closer to a plumbing assertion
than to evidence about the engine"* under selection-only compilation, so the whole content of
this PASS is a difference of **+0.38 pp against an anchor of +3.49 pp**. It clears a bar that
asks for a sign.

**The sensitivity the exam requires published, and what it shows.** The exam prints the 3% line
precisely because history's own ordering **reverses** there:

| line | generated difference | history's difference |
|---|---|---|
| 3% | **+0.209894395995** | **−0.58 pp — history flips** |
| **4% (the bar)** | **+0.378055215669** | +3.49 pp |
| 5% | **+0.163198544281** | +7.73 pp |

**The engine does not flip at 3%, and that is not a strength.** History's spread swings over an
8.3-point range across the three lines; the generated spread moves over **0.16 to 0.38** — a
fifth of a point. The inflation line carries almost no information about the assets in these
worlds, at any line. That is `A2`'s failure seen through a different statistic, and §2.1 is its
diagnosis.

**The 802-premise sign reversal, disclosed.** On the premise-accepted batch (world `…802`'s
Hard Landing clause on, 832 attempts for 50 acceptances, same seed):

| bar | unconditional *(the reading)* | premise-accepted *(disclosure)* |
|---|---|---|
| `A1` | **PASS**, difference **+0.378055215669 pp** | **FAIL**, difference **−2.946513489416 pp** (high −0.183, low +2.763) |
| `A2` | FAIL (corr high −0.017743) | FAIL (corr high +0.043965, gap +0.117979 against 0.136094) |
| `R2` | FAIL, max jump 4.1325 pp | FAIL, max jump **11.23853069831 pp** |

**On a world built to be a supply-shock hard landing, commodities-minus-bonds is *worse* in the
months the spine calls high-inflation.** The exam judges the unconditional arm and that is what
is reported; this is a disclosure on an arm the exam does not judge the pre-flesh bars on
either. But it says the `A1` PASS is **not robust to the premise**, and §4's fourth
stop-question asks whether a bar that flips sign between the two arms is carrying the meaning it
was written for.

### 2.4 `R2` — a FAIL on ONE forced re-entry in 6,000 months, with the p95 half now passing on a pooled batch

| half | generated | bound | verdict |
|---|---|---|---|
| largest jump at a seam | **4.132499999786 pp** | ≤ 2.5 pp | **FAIL** |
| p95 adjacent-month change | **0.883035257076 pp** | ≤ 0.929238995443 pp | **PASS** |

**Round two failed BOTH halves** on both its seeds (max jumps 5.3195 and 2.4935 pp; p95 0.9678
and 0.9658). **The p95 half has flipped from FAIL to PASS** and the join half has not.
~~— the first time in this campaign line —~~ **[C7: FALSE and withdrawn.** Round one's b2
recorded p95 **0.9128** (seed 199002) and **0.9200** (seed 2199008), both inside the 0.9292
bound, and seed 199002 passed b2 **outright**. What is new here is that the p95 half passes on a
**pooled 50-decade batch** and that round two failed both halves on both its seeds — which is
all the week-C report itself claimed. The "first time" was added by this verdict.**]**

**The failure decomposes to a single event** (`r2_diagnostics`):

| quantity | value |
|---|---|
| seams in the batch (50 decades, 6,000 months) | **444** |
| seams that are forced re-entries (the panel-edge rule) | **1** |
| largest jump at an ordinary join | **2.480125016536 pp — inside the bound** |
| largest jump at the forced re-entry | **4.132499999786 pp — the failure** |

An ordinary join is filtered on the inflation era bucket **and** on `|ΔYoY| ≤ 2.5 pp`, so it
**cannot** exceed the bound; all 443 obey it, the largest landing 0.02 pp under. A **forced
re-entry** happens when a block reaches the panel's last row: the owner's ruling of 2026-08-16
ends the block and draws a fresh entry rather than wrapping to row 0 — and when no candidate in
that month's pool matches the era filter, it draws **unfiltered**. That happened **once in six
thousand months**, and that single unfiltered draw is the entire `R2` failure.

**So `R2` fails at the only place in the design that can exceed the bound**, and it is not
stage 2's line. Fixing it is a decision about the fallback (refuse the decade? widen the pool at
the edge? relax the era match before the level bound?) — §4's third stop-question. Every option
changes a sealed compiler behaviour; join-constraint tightening is inside D-SP-6's funded scope
and stage 2 did not spend a day on it.

**One coincidence, checked rather than left.** The unconditional and premise-accepted batches
report *exactly* the same p95, 0.883035257076, to twelve decimals — on two demonstrably
different batches (444 seams against 370; maximum jumps of 4.13 pp against 11.24 pp). It is not
a caching bug: the p95 is taken over 5,950 adjacent-month pairs that are almost all **contiguous
panel rows**, so its order statistics come from the panel's own adjacent-inflation distribution,
which has a plateau exactly there — the 5,651st and 5,652nd sorted values are the same number on
both batches, so the interpolated percentile is too.

### 2.5 `T1`, `O1`, `D1`–`D4`, `P1`, `R1` — the nine passes, and what each is worth

**`O1` is the one that had never passed.** It reads **0.560824742268** against a floor of
0.5180669104991394, clearing by **+0.0428**. It had failed **everywhere it had ever been
measured** — ~~across two prior campaigns~~ **the v2 campaign's eight engine × arm cells
(0.4913 to 0.5149) and every point of both its frontier sweeps** [C6: `O1` is a v2-exam bar and
appears in neither the pilot's nor spine-02's records, so "two prior campaigns" overstated its
history; it is **one** campaign, four engines, two arms, two sweeps]. It also clears the
**windowing-symmetric** floor the stage-2 exam calls its primary construct (**0.515672**, by
+0.045153), so ruling `SQ1`'s reserved disagreement — the two constructs returning different
verdicts on the same engine — **does not arise**. The v2 verdict's §8.1 correction, which
withdrew the claim that "O1 is unreachable by this engine" and demanded a stage-2 seal re-derive
the phase anchor under symmetric constructs before citing O1's shortfall, is thereby settled in
the direction the review left open: **O1 is reachable.** §3 says by what, and it is not the
mechanism stage 2 was funded to build.

**`T1` reads 2.239246798804** inside [1.775283, 3.347362]. The v2 campaign's `T1` was a
**QUALIFIED PASS** at 1.913081 whose qualification (v2 §8.2) was that the fitted feedback's own
contribution was ≈0 and slightly negative and that T1 passed with the whole week-3 deliverable
switched off. Stage 2's `T1` moves further into the band, and §3's attribution table says which
change did it.

**`D1`–`D4` pass, and the v2 record's caution carries.** 2.0 / 4.0 / 4.0 / 3.0 against
[0,5] / [1,7] / [2,8] / [1,7]. Across four rounds and thirty-two-plus frontier rows the dwell
medians have never been the binding constraint. Two cautions travel with them unchanged: the D
bars' power calculation is close to tautological (the anchor is cut from the same object the
power model's true engine emits, exam §12.3), and v2's §8.5 correction stands — the *margin* was
overstated in that campaign, and D3/D4 sat exactly on their bands' lower edges at sweep extremes.
Also carried: v2 §6.2's grader defect reaches a **D anchor**, because the 2019-04 → 2020-02
cluster a richer five-input classifier reassigns *is* the right-censored recession spell `D1`
discloses.

**`P1` passes both move types with room:**

| move type | clockwise fraction | the batch's own null | **departure** | sealed threshold | verdict |
|---|---|---|---|---|---|
| growth flips | 0.590244 (205 transitions) | 0.488492 | **+0.101752** | 0.040330202948 | PASS |
| inflation crossings | 0.563433 (268 transitions) | 0.489913 | **+0.073520** | 0.031445706759 | PASS |

The departures are **74% and 59% of history's own** (0.138168 and 0.125093) — so this engine has
most of history's phase relation rather than the third week 3 had. The null is the batch's own
within-decade scramble, **exhaustively enumerated, seedless, no Monte Carlo error**. The
departures sit at **2.5× and 2.3×** the sealed thresholds, well clear of the 9.0% false-positive
band `L1` records — **but the reason they are clear is `M2`, the reverse arrow, not the coupling**
(§3.2).

**`R1` passes cleanly, and the worlds got harder rather than softer.** Coverage is monotone
across the ladder — 0.098065 → 0.291855 → 0.361632 → 0.667991 — and **4 of 20** rungs breach at
the 55-point arm against a floor of 1. Every coverage median is **above** round two's
([0.0901, 0.2821, 0.3514, 0.6643]) and the breach count **doubled** (2/20 → 4/20). That is the
direction a no-regression bar exists to protect. The 20 rungs are verified pairwise distinct on
**both** their spines and their compiled month tapes — not a formality, because round one recorded
a seed-stride collision that left a 20-rung ladder measuring two storylines.

**`R1`'s third check is a disclosure, and its margin should be read before it is quoted.**
Hold-course depth **−0.376590584108** clears the shallow edge of a **self-constructed** band
[−0.4260, −0.3750] by **0.0009** — a tenth of round two's already-thin 0.0059. `spine_pilot_b3`'s
own docstring and the round-two record both put it outside the sealed b3 bars ("constructed
post-seal, disclosed, not judged"). The judge's own `overall` field, which ANDs it in, is also
PASS, so nothing hangs on the distinction *here* — it is drawn because it will matter the moment
the number moves. §4's fifth stop-question.

---

## 3. The attribution — which arrow moved which bar

**This is the section to read if you read one.** Stage 2 turned on two mechanisms at once, and a
campaign line that has stopped at a frontier three times has no business shipping an
unattributed pass. Both were switched independently, from the same seed, and judged by the same
sealed judges (week A §5; every row is a real re-run, not a decomposition on paper):

| curve | `lam_x` | `O1` | `T1` | `P2` share | `P1` growth / inflation | slope sd | bars passing |
|---|---|---|---|---|---|---|---|
| week 3's equation | ×0 | 0.5385 | 1.765 | 0.0247 | +0.0614 / +0.0569 | 0.745 | 6 |
| week 3's equation | ×1 | 0.5362 | 1.765 | 0.0242 | +0.0584 / +0.0563 | 0.748 | 6 |
| **stage 2** | **×0** | **0.5620** | 2.361 | 0.7717 | +0.1027 / +0.0720 | 1.454 | 7 |
| **stage 2 (the fit)** | **×1** | **0.5608** | 2.239 | 0.7707 | +0.1018 / +0.0735 | 1.462 | 7 |

> **`O1` moved by the coupling: −0.0012. `O1` moved by the curve: +0.0235.**

Read down the `lam_x` axis and nothing happens — twice. Read across the curve axis and
everything happens.

**A caution attached to the whole table, from week A and repeated here rather than dropped:** the
`week3`-curve rows are week 3's *equation* inside the stage-2 loop, not week 3's engine
reproduced bit for bit. They run on the stage-2 policy deviation (with loadings `lam_u`, `lam_c`)
rather than week 2's input-free OU, and their tape differs — which is why they read `O1` = 0.5385
where week 3's committed engine read 0.5241. **The arm isolates an arrow; it does not re-measure
an engine.**

### 3.1 Finding one — the funded arrow is INERT

**`M1`.** The growth → inflation coupling `lam_x` is the thing D-SP-9 funded and the thing `P1`
was written to test. It is **significant on the panel** — `lam_x` = **+0.006326**, s.e. 0.001063,
**t = +5.95**, likelihood ratio against no coupling **34.80 on 1 df** — so the design document's
**Cheap Exit A**, which names `lam_x` and nothing else, **did not fire**. And it is **inert inside
a decade**: switching it off entirely changes `O1` by **−0.0012** and flips **no verdict**.

**Why, in one line of arithmetic.** Fitted persistence `a` = **0.994814** — a **half-life of 133
months**. The long-run inflation gap per unit of cycle input is `lam_x/(1−a)` = **1.2199 pp**,
which is large; but growth spells in this engine last two to four years, over which only
`1 − a^L` of that adjustment happens: **11.7% at 24 months, ~~21%~~ 22.1% at 48** [C9 — the exact
figure is `1 − a^48` = 0.220866; the 24-month figure is exact]. The channel is real, it is
significant, and it operates on a timescale an order of magnitude longer than the cycle it is
supposed to be coupled to.

**Its own age signature, corrected [C1] — and the correction leans against this section.** The
diagnostic is the mean inflation gap by growth-spell age: if inflation follows growth, the gap
should climb the longer an expansion runs and fall the longer a contraction runs.

| growth-spell age | expanding | contracting | separation | direction |
|---|---|---|---|---|
| 1–12 months | +0.122619 | +0.125498 | **−0.002879** | **the wrong way** |
| 13–36 months | +0.123613 | +0.056135 | **+0.067478** | the right way |
| 37+ months | +0.215498 | +0.183389 | **+0.032109** | the right way |

> ~~"the 37+ bucket separates the wrong way"~~ **FALSE.** The bucket that separates the wrong way
> is **1–12 months**; the 37+ bucket separates the **right** way, by less than the 13–36 bucket
> does. What survives is the weaker and still-true claim the sentence was for: **the signature
> barely separates the two axes at all**, the largest separation anywhere being 0.067 pp against
> an inflation-gap standard deviation of 0.217 pp. **The inertness finding does not rest on this
> diagnostic** — it rests on the ×0 vs ×1 re-runs (−0.0012), and the diagnostic is never a bar.

**The coupling frontier is flat, and that flatness is a finding rather than a null result.**
Scaling `lam_x` × 0, 0.5, 1, 2, 4: seven bars pass at every point; `O1` reads 0.5620, 0.5565,
0.5608, 0.5489, 0.5556 — a range of 0.013 with no monotone trend, which is noise at fifty
decades; `P2` moves 0.7717 → 0.7692 across ~~a **sixteen-fold** change in the coupling~~ **the
whole sweep — the coupling switched off entirely at one end, and an eight-fold range (×0.5 to
×4) between the non-zero points** [C8: the grid is ×0, 0.5, 1, 2, 4; there is no sixteen-fold
change in it, and the quoted endpoints are ×0 and ×4, between which no ratio exists]. **There is
no frontier on this axis.**

**The disclosure arm makes it worse, not better.** Fitting the same inflation block on the
classifier's own growth axis — the object the *engine* generates — gives `lam_x` = +0.005021,
**t = +6.10**, LR 36.49, and persistence 0.998611, a half-life of **499 months**. *More*
significant and *more* inert. Taking that arm would have changed no conclusion in this section.

### 3.2 Finding two — `P1` passes through the REVERSE arrow, and no sealed bar can see the difference

**`M2`.** What moved `P1` is not the arrow `P1` was written against. The curve now reads
`i_rule = r* + pi* + φ_pi·x + φ_c·c`, which **contains inflation**; the curve drives the growth
hazard at a **nine-month lead**; so the engine gained an **inflation → curve → growth** channel —
the *reverse* of the arrow the design document diagnosed as missing.

**A phase relation between two dials does not care which way the arrow points, and `P1` is a
phase statistic.** It is passing honestly and for the wrong reason, and **the exam has no bar
that can tell those apart** — a fact about the exam, now on the record.

**The anti-test could not have caught it, and that is stated rather than discovered later.** The
sealed sweep that qualified `P1` swept a *synthetic* coupling in which inflation is a lagged copy
of growth. It was monotone, correctly — 0.17 → 0.54 → 0.96 → 1.00 → 1.00 → 1.00 → 1.00, saturating
at 0.5 coupling, with the mean departure still rising past saturation (0.006 → 0.043 → 0.086 →
0.132 → 0.204 → 0.254 → 0.291) so the bar is not sitting on a plateau it could slide off. A sweep
of the intended direction cannot detect a pass arriving from the opposite one.

**A directional companion bar would be a new bar written after a coupling was fitted** — which
the exam delta's own opening sentence calls a description, not a test. §4's second stop-question
asks the owner to rule, and notes the answer may have to be "acceptable, disclosed" rather than
"fix it".

### 3.3 Finding three — `P2`'s fail-from-above is **L1 dispersion**, measured

**`M4`.** Covered in §2.2 and restated here as an attribution, because it belongs beside the other
two: **no stage-2 coefficient is involved in `P2`'s failure.** The coefficients are history's, the
exogenous block is empty on both sides, and the entire overshoot is carried by generated
components running 1.635× / 1.735× / 1.356× history's dispersion — inherited from L1's
across-decade state spread, which is a property of the pinned artifact rather than of anything
stage 2 fitted. **This is the ER-14 pattern**: coupling the spine did not make an existing defect
worse; it made it *visible*, by putting a bar in front of it that had never existed before.

**The row that was left on the table, named so the refusal is visible rather than silent.** On the
curve-loading axis (`c_i`, `c_x` and the season block scaled together):

| multiplier | `O1` | `T1` | `P2` share | `P1` growth / inflation | bars passing |
|---|---|---|---|---|---|
| ×0 | 0.5124 | 1.484 | 0.0000 | +0.0294 / +0.0393 | 4 (`D1`–`D4`) |
| **×0.5** | 0.5655 | 1.984 | **0.4570** | +0.1085 / +0.0817 | **8 — all eight pre-flesh bars** |
| ×1 (the fit) | 0.5608 | 2.239 | 0.7707 | +0.1018 / +0.0735 | 7 |
| ×2 | 0.5473 | 2.594 | 0.9307 | +0.0968 / +0.0548 | 7 |

> **The ×0.5 row passes all eight pre-flesh bars and it was NOT adopted.** It is not a fit; it is
> the fitted curve with its coefficients halved by hand, and halving a coefficient because a bar
> is on the other side of it is the definition of tuning past a conflict. Three campaigns have
> ended at a frontier and the discipline held every time. The verdict is the fitted point.

This axis is monotone in the direction `P2`'s first anti-test obligation requires (0.000 → 0.457
→ 0.771 → 0.931), which is the evidence that the bar is measuring what it claims. **And the ×0.5
row is not the fix even if it were adopted**: the dispersion ratios in §2.2 put the 63% overshoot
in L1's state spread, not in the curve's coefficients, so the right repair is not on this axis at
all.

### 3.4 What did NOT change, checked in code

- **The hazard keeps its v2 fitted form byte-for-byte** — max absolute coefficient drift
  **4.385e−13** against the committed week-3 artifact, which is the twelve-digit rounding and
  nothing else. Its duration term is unchanged; its nine-month curve lead was **re-selected by the
  same likelihood and picked 9 again**; its transmission coefficient is unchanged. **It was not
  re-tuned to reach a bar, and the check is in code.**
- **The fit reproduces the sealed anchors in code**, not in prose: `M3`'s lag matches (10 months),
  `M3`'s `lam_x` to 1.209e−14, `M4`'s six curve coefficients to 4.841e−13, `M4`'s `rho` to
  1.277e−14, `M4`'s history strict share to 2.811e−13, week 3's hazard to 4.385e−13 — all against
  a 1e−11 tolerance that is the artifacts' own rounding, not slack. **If any of these ever drifts,
  every verdict in this document is void.**
- **The curve's season block keeps its fitted form and LOSES its significance.** The likelihood
  ratio for dropping week 3's `C`/`E`/`K` block falls from **12.23 (p = 0.0066)** to **6.11
  (p = 0.107)** once the curve can read the actual rule-implied rate — most of what the season term
  was carrying turns out to have been the policy rate seen through a proxy. **The block is kept**,
  because dropping a pre-existing fitted form after a new regressor steals its significance is a
  post-hoc modelling choice; the demotion is reported. §4's fifth week-A stop-question.
- **Nothing in `src/` or `schemas/` was edited by any week of this campaign.** Week C's flesh runs
  by **composition**: exactly one function (`ah.gen.spine.sample_spine`) is substituted at runtime
  from `scripts/`, inside a context manager that restores the platform on exit including on an
  exception, and the projection into the `SpinePaths` contract is asserted month-by-month —
  exact on all 6,000 months of every batch — before the flesh is allowed to see a batch.

---

## 4. The stop-questions — OPEN owner decisions

**No owner ruling has been taken on this campaign.** Twelve stop-questions are on the record —
six raised by week A and six by week C — and **all twelve are open**. They are reproduced here
rather than left in two working reports, because a stop-question that only appears in a working
report is a stop-question that gets lost. Week A's first is the campaign's central ruling.

### 4.1 From week A (`f5b718b` §12) — six, all open

1. **The coupling does not work and the campaign passed seven pre-flesh bars anyway. Which of
   those is the result?** Stage 2 was funded on the diagnosis that `O1` needs a growth → inflation
   phase channel. The channel was built, it is significant on the panel, and switching it off
   changes `O1` by −0.0012. What moved the bars is the other arrow. The honest options are **(a)**
   report stage 2 as having found `O1` reachable by a *different* mechanism than the one it bought
   — which is what this document does — or **(b)** treat a pass the funded mechanism did not
   produce as not a pass at all. **This is a ruling, not a measurement, and it is the whole
   decision.**
2. **`P1` passes through the reverse arrow and no bar in the sealed exam can see the difference.**
   Acceptable as-is, or does `P1` need a directional companion? A companion would be a new bar
   written after a coupling was fitted, which the exam delta's own opening sentence calls a
   description rather than a test — so the answer may have to be "acceptable, disclosed".
3. **`P2` fails on inherited dispersion. Is that stage 2's failure to own?** Three readings lead
   different places: a genuine `P2` FAIL stage 2 owns; an L1 defect stage 2 made *visible* (the
   ER-14 pattern); or a batch-construction question to settle before `P2` is read at all.
4. **`c_x` is not identified** (t = 1.88, LR 3.53 on 1 df, p = 0.060) **and it is the coefficient
   the curve-reads-inflation fix rests on.** "Inflation now reaches the curve" is true as a
   structural statement and unpinned as a quantity. Is a directionally-correct,
   statistically-marginal channel enough to call the diagnosis addressed?
5. **The season block lost its significance** (LR 12.23 → 6.11, p 0.0066 → 0.107). Confirm the
   keep, or rule that the parsimonious curve is the one to carry forward.
6. **The ×0.5-loading row passes all eight pre-flesh bars and was deliberately left on the
   table.** Named so the refusal is visible. Exploring it would need a re-derivation, not an
   adoption, because a halved coefficient is not a fit.

### 4.2 From week C (`f37f9a3` §11) — six, all open

7. **Which inflation series does a *fleshed* decade report — and `A2`'s verdict is the price.** On
   the spine's own inflation, `A2` fails all three conditions. On the inflation the drawn months
   actually carried, it passes all three with room (§2.1). The exam's `Decade` contract has one
   slot and does not say. The primary taken is the spine's; the alternative has a real argument
   (`ah.port.adapter.run_gen_path` reports a compiled world's inflation as the panel's at the drawn
   rows — i.e. it is what a *player* sees). **This is a ruling, not a measurement, and it decides
   a bar.**
8. **The compiler's conditioning reaches 8.2% of a decade. ER-class register entry, funded fix, or
   declared property?** It is the mechanism behind both allocation readings and it is inherited
   from the sealed compiler design. A fix means changing block length or the join rule, which moves
   `R2` and `D1`–`D4` as a side effect — a release decision, not a cleanup.
9. **`R2` fails on one unfiltered forced re-entry in 6,000 months.** The panel-edge rule is an
   owner ruling (2026-08-16) and its unfiltered fallback is the only seam in the design that can
   exceed the bound. Refuse the decade? Widen the pool at the edge? Relax the era match before the
   level bound? Join-constraint tightening is inside D-SP-6's funded scope and was not spent.
10. **`A1` passes unconditionally and reverses sign under the premise** (+0.3781 pp against
    −2.9465 pp). Is a bar that flips sign between the two arms carrying the meaning it was written
    for?
11. **`R1`'s third check is a disclosure that now clears its own constructed band by 0.0009.**
    Confirm it stays a disclosure, or rule it a bar — in which case it needs a band cut from
    something other than itself.
12. **Promotion.** The stage-2 world assembly is composed in `scripts/` and substitutes exactly one
    platform function at runtime. **Promoting it into `src/` is a separate owner release event and
    has not been taken. Nine of twelve is a frontier, not a pass, and this campaign does not ask
    for the promotion.**

---

## 5. The campaign's own limitations register

Written here because a limitation that only appears in a working report is a limitation that gets
lost. These are the campaign's; the sealed exam's own declared list (`L1`–`L13`, exam delta §6)
stands unchanged, is inherited whole, and is not restated except where a stage-2 reading turns on
it.

### 5.1 The two unidentified coefficients

A coefficient is called **unidentified** here when its 95% interval spans both signs — applied
uniformly, reported for every coefficient, not softened for the ones that fail it.

| block | coefficient | estimate | s.e. | t | 95% spans both signs? |
|---|---|---|---|---|---|
| inflation | `lam_x` (growth → inflation) | +0.006326 | 0.001063 | **+5.95** | no |
| policy | **`lam_u`** (policy leans on inflation) | +0.09215 | 0.06052 | **+1.52** | **YES** |
| policy | `lam_c` (policy leans on the cycle) | +0.03469 | 0.01359 | +2.55 | no |
| curve | `c_i` (curve ← rule-implied rate) | −0.24032 | 0.01101 | **−21.83** | no |
| curve | **`c_x`** (curve ← inflation gap) | +0.49203 | 0.26150 | **+1.88** | **YES** |
| curve | `C` (contracting level shift) | −0.07926 | 0.04322 | −1.83 | yes |
| curve | `E` (expansion age) | −0.03845 | 0.01555 | −2.47 | no |
| curve | `K` (contraction age) | +0.02681 | 0.01986 | +1.35 | yes |
| hazard | `cov_expanding[curve_slope]` | −1.48880 | 0.50412 | −2.95 | no |

- **`c_x` — inflation's channel into the yield curve — is not established.** LR 3.53 on 1 df,
  p = 0.060. **The sign is right and the size is a coin-toss away from zero**, and it is the
  coefficient the whole "inflation now reaches the curve" claim rests on. Sixty-eight years of one
  country's history cannot say how big it is.
- **`lam_u` is not established** (t = 1.52). Its companion `lam_c` *is* (t = 2.55), and the two
  together reject "policy is noise" at LR 7.10 on 2 df. **The block earns its place; the inflation
  half of it does not.**

**Neither stops the campaign, and which one would was pre-declared.** Cheap Exit A names `lam_x`
and nothing else. Deciding after the estimates were visible that some other coefficient was the
real stop condition would be a goalpost move.

**The correlation structure is as much of the answer as the standard errors.** Cross-block
correlations are **exactly zero** — the blocks share no parameters and every path they read is
observed on the panel, so the joint likelihood block-diagonalises. **That is a property of the
data, not an achievement of the design**, and it is stated rather than left for a reader to work
out. The largest off-diagonal anywhere is **+0.741**, inside week 3's inherited season block. The
design document's feared collinearity — `c_i` and `c_x` "both read policy" — **did not
materialise**: they correlate at **−0.199**, so `c_x`'s wide interval is thinness of signal.

### 5.2 `P1`'s size is 9.0%, and this engine's pass has to be read against it

Inherited whole from the seal's `L1` and repeated here because it bears directly on the headline
`P1` PASS. Against a synthetic engine whose two dials are **independent by construction**, `P1`
returns a PASS in **9.0% of 300 batches of fifty decades** at the sealed thresholds — against
**1.3%** at the recommended construct's own candidate and **0.3%** at the strictest published one.
The judge is not broken — its mean departure at zero coupling is ~~+0.0006~~ **−7.99e−05 on
growth flips and −1.10e−04 on inflation crossings**, both inside their own Monte Carlo standard
errors (1.778e−03, 1.820e−03) [C10 — the `+0.0006` is quoted from the **sealed** exam delta's §6
`L1` prose, and it matches neither the artifact nor the exam's own §5 control table nor the seal
JSON's own `L1` string; see §7.10, and note that no sealed file was edited to say so]. This is
the bar's **size**, and it is what ruling `SQ7` cost.

**How this campaign's reading sits against it.** The measured departures are **2.5× and 2.3×** the
sealed thresholds, well clear of a 9% false-positive band. **But the reason they are clear is
`M2` — the reverse arrow — not the coupling.** A single `P1` PASS is evidence of *some* phase
coupling at about the strength of one conventional significance test, and this one is evidence of
a channel the campaign did not set out to build.

### 5.3 The dial sensitivities, and the one that is a property rather than a measurement

The sealed rule: a statistic that moves by more than its own standard error across the nine dial
arms escalates to soft labels, and both are reported.

| coefficient | worst arm | moves by (s.e.) | escalated? |
|---|---|---|---|
| **`lam_x` (primary, USREC)** | — | **0.000** | no — **invariant by construction** |
| `lam_x` (grader-axis refit) | growth line −50 bp | +0.659 | no |
| `c_i` | growth line +50 bp | +0.181 | no |
| `c_x` | growth line +50 bp | −0.090 | no |
| `cov_expanding[curve_slope]` (the v2 hazard) | inflation +, growth − | **−1.044** | **YES** (week 3's own, inherited) |

**The caveat that matters.** The primary `lam_x` is fitted against `1 − 2×USREC`, which is **not a
function of the classifier's dials at all** — so it is invariant across the whole grid *by
construction*. **That is a real stability property and it is not a measurement**: it says the
coefficient cannot move, not that it has been shown not to. The dial sensitivity that genuinely
exists is the grader-axis refit's, and it moves 0.66 s.e. at worst — inside the rule. Its
**selected lag**, however, moves between **1 and 2 months** across the arms against the USREC arm's
**10**. That is `L8` again: **the lag is the unstable part, not the size.**

**And `L8` was confirmed rather than discovered.** The selected lag `m` = 10 is the top of a
**ridge, not a peak** — lag 10 beats lag 9 by **0.18 of log-likelihood** — and the anchors already
recorded that only 57% of bootstrap draws select within three months of ten. Ruling `SQ9` sealed
the **rule and the grid**, never a value; the whole 25-point profile is published in the artifact,
and the selected lag must never be quoted as a determined quantity.

**`P1`'s thresholds themselves are pinned only to a factor of 2 to 2.5** (`L2`): a 50 bp move of
the classifier's inflation dial — the platform's own `BACKDROP_MARGIN_PP`, not an exotic
perturbation — moves the inflation-crossing departure by 1.35 of its own standard error, and the
candidate thresholds range over [0.0403, 0.0828] and [0.0314, 0.0786]. **A threshold sealed to six
decimals under that range is quoting its dial as much as its data**, and `L3` records that the
escalation path for a *counting* statistic does not exist — nothing was invented to fill it.

### 5.4 The inherited compiler's reach — the 8.2%, as a limitation rather than a finding

§2.1 states it as the campaign's headline. It is repeated here as a **register entry**, because it
bounds what any future bar conditioned on the spine's dial can see in the flesh:

- **The conditioning reaches 8.2% of a decade** (494 of 6,000 months). Selection-only, 6-month mean
  blocks, era-safe joins — the sealed compiler design, owner-ruled 2026-08-15, inherited whole.
- **It was invisible until the allocation bars were run**, because `A1` and `A2` are the only bars
  in the exam that condition asset behaviour on the spine's dial.
- **It bounds `A1` and `A2` and nothing else in the exam** — but it bounds them completely. Both
  are bars about a whole decade's months, and the dial sets one month in twelve.
- **A fix is a release decision.** Changing block length or the join rule moves `R2` and `D1`–`D4`
  as a side effect.

### 5.5 The rest, in one place

- **`R2`'s failure is a single event, and single events are not estimates.** One forced re-entry in
  6,000 months decided the verdict. The bar is a hard maximum, so that is exactly what it is
  written to catch — but **nobody should read "4.13 pp" as a property of the engine's typical
  seam.** The typical seam is 443 joins with a maximum of 2.48 pp.
- **The "unconditional" batch still carries world 802's severity shape.** World `…802` is the only
  world in the tree that declares both `x_stress` and `x_spine`, so it supplies the flesh *spec* for
  both batches: entries drawn from the worst 35% of months by the `all_down` severity functional,
  and the worst 10% over quarters 8–14. **Switching the premise clause off makes the batch
  unconditional in its *spine*; it does not make the flesh neutral.** A neutral flesh spec does not
  exist in the tree and inventing one would be improvising a construct.
- **`P2`'s tape noise has not been measured** (`L9`). Its band is cut from 2000 draws; the adopted
  640,000-draw rule is met **by arithmetic rather than by measurement** on the one sealed floor that
  has a tape. `P2`'s verdict is also **not robust to the choice of summary** (`L6`): the realised
  R², whose bootstrap interval `[−0.2203, 0.5616]` spans zero at every block length, would have
  dropped the bar, and **the reasoning that rejects it is the author's and should be checked rather
  than accepted.**
- **The generated inflation *level* is half history's** — mean trailing CPI **1.81 pp against
  history's 3.49 pp**, with the hot share nevertheless close (0.372 against 0.392) because the
  across-decade spread is wide. **This is L1's, is not new to stage 2, and no bar in this exam looks
  at it.** It sits directly beside §2.1's finding that a drawn "high" month averages 3.22 pp — both
  say the level plane and the dial plane are not the same object.
- **The inflation innovation is drawn i.i.d.**, which is the equation as fitted; its residual
  carries a lag-1 autocorrelation of 0.198 from the trailing-12-month construction. **Simulating that
  structure would be simulating a model that was not estimated**; it is declared rather than added.
- **The composition is a runtime substitution, not a promoted engine.** Whether the substituted
  sampler behaves identically once promoted into `src/` is a claim this campaign does not make and
  cannot: promotion is a release event with its own gate.
- **Nothing here reaches the private book.** `ER-14` stands exactly where it was — inflation does
  not reach private markets at all — and **a passing `A1` says nothing about it.** Stage 3's
  asset-return conditional means remain unfunded (D-SP-9).
- **The v2 exam's own limitations are inherited whole** (`L12`), including the
  industrial-production-only recession dial, `T1`'s un-re-anchored downturn union, and the absence
  of any 2021–22 anchor — that episode lies inside the spent holdout.
- **The standing caveat is unchanged and applies to every number above:** nothing built on this
  generator line is a convincing model of history, **the holdout is spent**, and no appeal to
  held-out data is available to any result this campaign produces.

### 5.6 Generation-time covariate LEVEL mismatches (added post-review) [C3]

The v2 review raised this class as its finding C3 and put it in the v2 register as §6.6, because
the campaign had disclosed the covariates' **dispersion** ratios and not their **levels**. Stage 2
repeated the omission. From `stage2-fitted-params.json`, `verification.diagnostics`:

| quantity | generated | history | why it matters |
|---|---|---|---|
| **inverted-curve share** | **0.160333** | **0.183272** | `T1` conditions on `slope < 0`, so this **is** its tight set — the conditioning population, not a side fact |
| expanding share | 0.776667 | 0.719557 | the growth axis the hazard runs on, and the axis `P1`'s growth flips are counted over |
| inflation-gap sd | 0.216515 | 0.159701 | the 1.356× ratio `P2` catches; disclosed in §2.2 as a ratio, not as a level |

**And the consequence the verdict did not draw.** The v2 campaign ran the generated curve at
**27.5% inverted against history's 18.3% — a 1.5× over-inversion**, and its own review had to
correct the verdict for presenting that as a fix. Stage 2's engine runs at **16.0% against
18.3% — 0.87×, under-inverted.** So `T1`'s conditioning population **moved from over- to
under-inverted between the two campaigns** while `T1` itself moved 1.913 → 2.239. Nothing in the
body says so, and any comparison of the two `T1` readings should carry it.

### 5.7 Four sealed limitations the body did not restate (added post-review) [C11]

`L12` is inherited whole and `L1`, `L2`, `L3`, `L6`, `L8`, `L9`, `L13` are carried above. Four
more are in the seal's own `declared_limitations` and two of them bear directly on readings this
document leads with:

- **`L4` — `P1` asks for a fraction of a departure history can only just establish.** On the
  uncensored construct history's **own** growth-flip departure has a 95% interval of
  **[−0.000283, +0.233050]** — *not distinguishable from zero*. On the sealed construct it just
  is, by 0.0066 at the lower edge, and at 12-month blocks it is not. `M3`'s gate closes whether
  the *channel* exists; it does not close how precisely its *size* is known.
- **`L7` — the strict share is NOT an explained-variance figure.** It sums squared component
  standard deviations, i.e. treats the components as uncorrelated. On the generated side they are,
  by construction. **On history they are not**: the rule-implied rate and the inflation gap
  correlate at **0.705**, and history's total sum of squares is **1.78× the slope's own
  variance**. Anyone reading §2.2's *"history's strict economic share = 0.558667"* as "56% of the
  curve's movement is explained" is reading it wrong; the number that answers *that* question is
  the realised R², **0.2464**.
- **`L10` — `P2`'s power is sampling adequacy only.** It places history's own components inside
  history's interval; it cannot say whether a coupled engine would produce components of that size.
- **`L11` — history is the most favourable engine there is.** Both power figures use history itself
  as the true engine while resampling the same 813 months the thresholds are cut from, so they see
  sampling noise and **not** estimation error. They are **upper bounds** on any real engine's power.

---

## 6. Status and disposition

**FRONTIER.** Nine of twelve bars pass; three fail. No owner ruling has been taken and twelve
stop-questions are open. *(Read with §7: the verdict-integrity review changed no verdict value
and no PASS/FAIL word — it reproduced all twelve to the digit and found all twelve PASS/FAIL
words correct — and it returned eleven findings, all interpretive or omissive, correcting the
characterization attached to several readings and adding two entries to the register.)*

- **The seal stands, unamended.** `amendments` is empty: no threshold moved, no hashed file was
  edited, no arm was re-chosen after a reading. Every prior round's verdicts stay frozen.
- **All twelve bars have readings for the first time.** `A1`, `A2`, `R1` and `R2` had never been
  measured by any round of this campaign line.
- **`O1` passes for the first time**, under both the sealed floor and the windowing-symmetric floor
  the stage-2 exam calls primary — settling the v2 review's §8.1 open question in the direction it
  left open. **It does not pass by the funded mechanism** (§3.1).
- **No parameter was tuned to move a bar.** Every scaled coefficient exists only inside a frontier
  sweep and is reported as a counterfactual. **The ×0.5 row that passes all eight pre-flesh bars was
  named and not taken.**
- **`src/` and `schemas/` are untouched by the whole campaign**, and **the `src/` promotion is not
  requested**. There is no engine in the platform to un-ship, and no world, preset or
  `TOY_ENGINE_VERSION` moved.
- **A stage-3 campaign is not proposed here.** Asset-return conditional means are unfunded, and
  §2.1's 8.2% is the number any such proposal would have to be costed against.

---

## 7. Post-review corrections (verdict-integrity review, 2026-08-18)

An independent verdict-integrity review re-ran `scripts/stage2_fit.py` and
`scripts/stage2_weekc.py` and re-derived every load-bearing claim from the committed artifacts
rather than re-reading the working reports.

**What it certified.**

- **Both artifacts regenerated byte-identically.** `stage2-fitted-params.json`
  `sha256 0604e55502df530e5ca8861cf45424668d9b686b0125cfeb2043a617e52a9c54`;
  `stage2-weekc-results.json`
  `sha256 565413ac70cbd8a8e7763ffa541790fd770860879fea47035ea010ebf9cc6f19`. Both match the
  values the working reports publish, and `git status` was **clean after both runs**.
- **All eleven sealed hashes recomputed clean** against the working tree, exam delta included, and
  the seal's `amendments` list is **empty** — nothing was amended in stage 2.
- **All twelve bar readings reproduced to the digit** by re-running the entry points. The fit
  script printed `T1 PASS 2.2392467988040385 · O1 PASS 0.5608247422680412 · D1 2.0 · D2 4.0 ·
  D3 4.0 · D4 3.0 · P1 PASS 0.042073930959286236 · P2 FAIL 0.7706826534809134`; the week-C script
  printed `A1 PASS 0.3780552156694983 · A2 FAIL −0.01774267115346028 · R1 PASS 4/20 ·
  R2 FAIL 4.132499999786177`. **No discrepancy at any digit.**
- **Every PASS/FAIL word re-checked against the sealed bands: 12 of 12 correct**, recomputed
  independently of the judges from `stage2-prereg.json`'s own thresholds — including `P2`'s
  `failure_side: above` and `R2`'s split verdict (join FAIL, p95 PASS).
- **The three interpretive claims re-derived exactly.** 494/6000 = 0.08233333 ✓;
  `p·q + (1−p)(1−q)` = 0.5915961591 against the artifact's 0.591596159122 (agreement to 1.8e−13) ✓;
  agreement 0.605925925926, excess over chance **+0.014330** ✓. `A2` both ways: the sealed judge's
  three conditions recomputed on both series, FAIL 0/3 on the spine's inflation and PASS 3/3 on
  the drawn months' ✓, with the reported gap equal to (high − low) to 0.0 in both. `R2`: 444 seams
  = 443 ordinary + 1 forced; `max(ordinary, forced) = 4.132499999786 = the bar's value` ✓; the
  ordinary maximum clears the bound by 0.019875 pp; the p95 bound is exactly 1.25 × the panel's
  0.7433911964 ✓; 5,950 adjacent pairs = 50 × 119 ✓.
- **The seal genuinely predates the fit.** `scripts/stage2_fit.py` does **not exist** at the seal
  commit `d67a455`; it first appears at `0a5884d`. The `sealed_at_utc` string's HEAD commit
  `3b54a58…` is the commit immediately preceding the seal.

**What it found.** Eleven findings — none touching a verdict value or a PASS/FAIL word, all
interpretive or omissive. **The rule this section follows** (the v2 campaign's precedent): where
this section and the body conflict, **this section governs**.

**And the pattern, which is not v2's.** The v2 review found eleven of twelve findings leaning the
same way. Here they split: **six make the engine or the record look better than the artifacts
support** (§7.2, §7.3, §7.4, §7.6, §7.7, §7.11) and **three make the funded coupling look *more*
inert than the artifacts support** (§7.1, §7.8, §7.9) — the latter leaning *against* this
document's own headline. Two (§7.5, §7.10) are neutral. That is worth stating because a
one-directional pattern is evidence of motivated reading and a split one is not; what this split
is evidence of is ordinary carelessness in both directions.

### 7.1 C1 (SUBSTANTIVE) — the coupling's age signature: the wrong bucket was named, and the correction favours the coupling

Corrected inline in §3.1 with the full three-bucket table. The claim as published — carried
verbatim from week-A fit report §5 — was *"the 37+ bucket separates the wrong way"*. From
`verification.diagnostics.inflation_gap_by_growth_spell_age`:

```
1-12 months   expanding +0.122619   contracting +0.125498   separation -0.002879   WRONG way
13-36 months  expanding +0.123613   contracting +0.056135   separation +0.067478   right way
37+  months   expanding +0.215498   contracting +0.183389   separation +0.032109   right way
```

**The bucket that separates the wrong way is 1–12 months, not 37+.** The 37+ bucket separates the
right way, by less than the 13–36 bucket does. The weaker claim the sentence was for survives —
the signature *barely* separates the axes, the largest separation anywhere being 0.067 pp against
an inflation-gap sd of 0.217 pp — and **the inertness finding does not rest on the signature at
all**: it rests on the ×0-vs-×1 re-runs (`O1` −0.001175257732), which the review reproduced.

### 7.2 C2 (SUBSTANTIVE) — "exactly 0.0 drift, not 'small'" is a rounding artifact

Corrected inline in §2. `stage2-weekc-results.json` carries
`spine_identity.max_abs_drift = 0.0` and `abs_drift = 0.0` on each of the eight bars, and the
week-C report §1.4 puts it emphatically: *"Worst absolute drift across all eight: 0.0. Exactly
zero, not 'small'."* **Every float in that artifact is written through `weeka._round(payload, 12)`.**
Re-running the script prints the unrounded value:

```
frozen-engine agreement: max drift 4.841e-13
spine identity vs week A:  max drift 2.862e-13
```

So the measured worst drift is **2.862e−13**, not zero. **The conclusion is untouched and is
arguably strengthened**: `spine_identity` *raises* above a 1e−12 tolerance, 2.862e−13 is well
inside it, and the eight verdicts are identical — the batch really is week A's. What is wrong is
the phrasing. Note the asymmetry that made this catchable: `frozen_engine_agreement.max_abs_drift`
is rounded to `0.0` in the same artifact, and there both working reports quote the **unrounded**
4.841e−13 correctly. The same field, treated two different ways, in one file.

### 7.3 C3 (SUBSTANTIVE, omission) — the generation-time covariate LEVELS were undisclosed, again

Now in the register as **§5.6**. This is the v2 review's own C3 recurring: dispersion ratios
disclosed, levels not. The consequential one is that `T1` conditions on `slope < 0`, so the
inverted share **is** its tight set — and it moved from v2's **1.5× over**-inversion (0.274 vs
0.189) to stage 2's **0.87× under**-inversion (0.160 vs 0.183) while `T1` moved 1.913 → 2.239.
A reader comparing the two campaigns' `T1` numbers is comparing readings taken over materially
different conditioning populations, and neither verdict said so.

### 7.4 C4 (SUBSTANTIVE, omission) — `R1` is judged on a different arm from every other flesh bar

Now corrected in §2's table and in the note beneath it. `stage2-weekc-results.json` records
`batches.R1.arm = "declared premise"` against `batches.A1_A2_R2.arm = "unconditional"`. The
original table's arm column read "b3 ladder, n = 20", which is true and does not say it. It
matters because §2.3 discloses that **`A1`'s sign reverses on the premise-accepted batch**
(+0.3781 → −2.9465 pp), so the flesh bar that passes most cleanly is read on the arm where the
other passing flesh bar fails. R1's construction is byte-frozen and changing it is exactly what a
carried bar exists to prevent — so this is a disclosure obligation, not a defect.

### 7.5 C5 (MINOR) — "five scripts", six then listed

Corrected inline in §1. The eleven hashed paths are **5 documents/JSON + 6 scripts**. The total was
right, the interior count was not. **This is finding C10 of the v2 review repeating verbatim**
("six scripts", seven then listed) — the same sentence shape, in the same position, one campaign
later.

### 7.6 C6 (MINOR) — `O1` "failed everywhere across two prior campaigns" overstates its history

Corrected inline in §2.5. `O1` is a **v2-exam** bar. It appears nowhere in
`2026-08-15-spine-pilot-results.md` or `2026-08-16-spine02-results.md`, whose sealed bars are
`b1`–`b6`. What is established, and it is still a strong statement, is that `O1` failed in **all
eight** of the v2 campaign's engine × arm cells (0.491345 to 0.514911 against a floor of
0.5180669) and at every point of both v2 frontier sweeps — **one** prior campaign, four engines,
two arms, two sweeps.

### 7.7 C7 (MINOR) — "the p95 half passing for the first time" is FALSE

Corrected inline in §2.4 and in its heading. Round one's `b2` recorded p95 **0.9128** on seed
199002 and **0.9200** on seed 2199008, both inside the 0.9292 bound; seed 199002 passed `b2`
**outright** (max jump 2.3453 pp). The week-C report's own claim is correctly scoped to round two
(*"Round two failed **both** halves … the p95 half has flipped"*) — **the "first time in this
campaign line" was added by this verdict** and is withdrawn. What is new is that the p95 half
passes on a **pooled 50-decade batch** rather than per-seed.

### 7.8 C8 (MINOR) — "a sixteen-fold change in the coupling"

Corrected inline in §3.1. The `lam_x` frontier grid is **×0, 0.5, 1, 2, 4**. The largest ratio
between non-zero points is **eight-fold**, and the quoted endpoints (0.7717 → 0.7692) are ×0 and
×4, between which no ratio exists at all. Carried from week-A fit report §6. **The finding is
unaffected** — `P2` moves 0.0025 across the whole sweep, the coupling switched off entirely at
one end — but the overstatement made the flatness look better-tested than it is, i.e. it leans
*toward* this document's own headline.

### 7.9 C9 (MINOR) — "21% at 48 months" is 22.1%

Corrected inline in §3.1. `1 − a^48` at `a` = 0.994814070132 is **0.220866**. The 24-month figure
(0.117314 → 11.7%) is exact, as are the half-life (133.312 months), the long-run gap
(`lam_x/(1−a)` = 1.219912 pp) and the calibrated axis swing (1.0 − 0.008772 = 0.991228).
Understates the coupling's reach by about a point — again leaning toward the inertness headline.

### 7.10 C10 — a factual error inside a SEALED document, recorded and NOT edited

Corrected inline in §5.2. The sealed exam delta's §6 `L1` states that `P1`'s *"mean departure at
zero coupling is +0.0006, inside one standard error of zero"*. From
`stage2-antitest-results.json`, `controls.P1_null_engine`:

| move type | mean departure at zero coupling | its Monte Carlo standard error | inside 1 s.e. of zero? |
|---|---|---|---|
| growth flips | **−7.990761e−05** | 1.778222e−03 | yes |
| inflation crossings | **−1.097286e−04** | 1.819705e−03 | yes |

**The `+0.0006` matches nothing.** It disagrees with the artifact, with the exam's **own §5
control table** (which quotes −0.00008 / −0.00011 correctly), and with the seal JSON's own `L1`
string (which says only "within one standard error of zero"). The claim `L1` is making — that the
judge is centred on the null — **is true**, and no threshold, judging rule or verdict is affected.

**How it is handled.** Following the v2 precedent (§8.6 / `AM-SPV2-2026-08-17-002`): **the sealed
file is not edited**, because the seal is the record and editing it would erase the thing the
record exists to keep. The correction is recorded here. Whether it is also appended to the seal's
`amendments` log as a `documentation` entry — which would be the first amendment of any kind in
stage 2 — **is the owner's call and was deliberately not taken by this review.**

### 7.11 C11 (MINOR, omission) — four sealed limitations were not restated

Now in the register as **§5.7**: `L4` (history's own uncensored growth-flip departure has a 95%
interval of [−0.000283, +0.233050] and does not exclude zero), `L7` (the strict share is **not**
an explained-variance figure — history's components correlate at 0.705 and its total sum of
squares is 1.78× the slope's variance; the explained-variance number is R² = 0.2464), `L10` and
`L11` (`P2`'s power is sampling adequacy only, and both power figures use history as the true
engine, so they are upper bounds). `L4` bears on the `P1` PASS this document leads with and `L7`
bears on how §2.2's share table may be quoted.

### 7.12 Two review observations that are not corrections, recorded anyway

- **One claim in the body is carried rather than re-derived, and it is labelled as such.** §2.4's
  explanation of the identical p95 across two different batches — *"the 5,651st and 5,652nd sorted
  values are the same number on both batches"* — is week C's, and re-deriving it needs both
  ensembles rather than either committed artifact. The **arithmetic around it checks out** (5,950
  adjacent pairs = 50 × 119, and a linear-interpolated p95 lands at index 0.95 × 5,949 = 5,651.55,
  i.e. between the 5,651st and 5,652nd order statistics), and both batches' p95 fields are
  byte-identical in the artifact. The plateau claim itself is **not independently verified here**.
- **The review checked whether §2.1's headline reads better than the artifact supports, and it
  does not.** The A2-on-drawn-months disclosure passes all three sealed conditions by the sealed
  judge's own arithmetic (corr +0.176479 > 0; gap +0.348323 ≥ 0.136094; share 0.928499 ≥ 0.80),
  the artifact flags it `"Reported, never judged"`, and §2.1 says so in bold. The 8.2% and the
  60.6%/59.2% pair reproduce exactly. **No finding.**
