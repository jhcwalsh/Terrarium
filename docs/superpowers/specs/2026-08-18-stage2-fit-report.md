# Stage 2, week A: the coupled system, fitted — and the arrow that moved the bars was not the one we bought

**Date:** 2026-08-18 · **Branch:** `stage2-02-fit` · **Decision:** `D-SP-9` (stage 2 funded,
owner ruling 2026-08-17)
**Status: FRONTIER.** Seven of the eight pre-flesh bars pass, including `O1`, which had
failed everywhere across two campaigns. `P2` fails — **from above**. Nothing is adopted, no
coefficient is tuned, and the row on the frontier that passes all eight is named and left
where it is.

**What it is a fit of.** `docs/superpowers/specs/2026-08-17-stage2-coupled-system-design.md`
§2.2. **What it is judged by.** `docs/superpowers/specs/2026-08-18-stage2-exam-delta.md`,
sealed at `docs/superpowers/specs/stage2-prereg.json` before the fit was run, with the ten v2
bars carried byte-frozen. **Where the numbers live.**
`docs/superpowers/specs/stage2-fitted-params.json`, written by `scripts/stage2_fit.py`,
byte-identical on a re-run
(`sha256 0604e55502df530e5ca8861cf45424668d9b686b0125cfeb2043a617e52a9c54`).

**House rules this document is written under** (D-SP-6's standing communication rule): plain
language; every number states what it is a measurement of; no term used without being defined
once.

---

## 0. The one-paragraph answer

The coupled system was fitted jointly on the campaign panel and simulated for fifty
unconditional decades at week 3's own verification seed. **`T1` passes at 2.2392, `O1` passes
at 0.5608 against its sealed floor of 0.5181, `D1`–`D4` all sit inside their bands, and `P1`
clears both move types with room — +0.1018 on growth flips against a threshold of 0.0403 and
+0.0735 on inflation crossings against 0.0314.** `P2` fails at a strict economic share of
0.7707 against a band of [0.3917, 0.6734], and the side it fails on is the **upper** one: the
generated yield curve is *too* determined by the economy, not too little. And then the part
that matters more than any of those readings: **switching the growth → inflation coupling off
entirely changes `O1` by −0.0012 and leaves every verdict exactly where it was.** The
coefficient `lam_x` is significant on the panel (t = +5.95, so the design document's Cheap
Exit A does not fire) and it is **inert inside a decade**, because its half-life is 133 months
and the growth spells it is supposed to bend last two to four years. The arrow that moved
`O1` is the other one — the curve reading the rule-implied policy rate instead of the rule's
leftovers, worth +0.0235 — and even that is bought with a generated curve running at 1.74× the
dispersion of history's. `O1` is reachable. It is not reachable by the mechanism stage 2 was
funded to build, and this report's job is to say so before anyone reads the seven passes as a
vindication of the coupling.

---

## 1. What was fitted, and the exact form

Four blocks, one likelihood, maximised as one object:

```
growth chain   season_{t+1} ~ Bernoulli( h(season_t, dwell_t, z_t) )      [week 2/3, UNCHANGED]
inflation gap  x_{t+1} = k0 + a·x_t + lam_x·(c_{t−m} − c̄) + σ_x·e_t                    [NEW]
inflation      pi_t   = pi*_t + x_t
policy dev     u_{t+1} = u0 + φ_u·u_t + lam_u·x_t + lam_c·c_t + σ_u·e_t        [NEW loadings]
policy rate    i_t    = r*_t + pi*_t + φ_pi·x_t + φ_c·c_t                     [L1's own rule]
curve slope    slope_t = c0 + c_i·(i_t − ī) + c_x·(x_t − x̄)
                        + season_term(g_t, age_t) + e_t,   e AR(1)                     [NEW]
```

`z_t` carries `slope_{t−9}` at week 2's likelihood-selected lead, so the loop closes with a
genuine lag and there is no simultaneity to solve anywhere in it.

### 1.1 The three primary constructs, declared in code before any bar was read

The design document's risk table names "the 93.9% trap repeating" — week 3 measured an
estimator that fits better and generates worse — and prescribes one mitigation: pre-commit the
primary **in code**, before any bar is read. Three of §2.2's lines are genuinely ambiguous, so
three constants were written into `scripts/stage2_fit.py` at module level
(`PRIMARY_CURVE_ARM`, `PRIMARY_CYCLE_INPUT`, `PRIMARY_HAZARD_ARM`, and the `DEVIATIONS`
table), and each ambiguity's other reading was fitted as a **disclosure** so the cost of the
choice is a number rather than an argument.

| ambiguity | what §2.2 says | what was taken, and why |
|---|---|---|
| **which policy rate the curve reads** | `c_i·(i_t − ī)` where `i_t = i_rule + u` | **`i_rule` alone.** The sealed `P2` anchor (exam delta §4.3) decomposes history on the rule-implied rate and classifies `u_hat` as **exogenous**, so keeping `u` out of the curve makes the generated and historical decompositions the same object with an empty exogenous block on both sides. That identity is `P2`'s fourth anti-test obligation, discharged structurally. |
| **the hazard's third covariate** | the line writes `x_t`; week 2's covariate is `pi* − pi_target` | **`pi* − pi_target`, unchanged.** The same paragraph calls the growth chain "unchanged in form", and week 3's discipline is that the transmission channel is never re-tuned to reach a bar. |
| **the generated cycle input** | "`c_t` = +1 expanding, −1 contracting" *and* "the WP2.6 contract, fitted on history as `1 − 2×USREC`" | **the axis-calibrated WP2.6 contract**: the panel mean of `1 − 2×USREC` inside each of the classifier's two growth axes, **+1.0000 expanding and +0.0088 contracting**. |

That third one deserves its paragraph, because it is the one a reviewer should push on.
`lam_x` is fitted against `1 − 2×USREC`, whose panel mean is **+0.7220** and which fires on
NBER recessions — 13.5% of months. The engine's contracting axis is `grader_v2`'s
`{REC, CRI, STAG}` and fires on **27.5%**. Feeding a literal `−1` into a coefficient fitted on
that regressor both doubles its range and moves its mean, which would shift the generated
inflation **level** by about a quarter of a percentage point as a side effect of a change
that is supposed to be about phase. The calibrated map has the law of total expectation on its
side: averaged over the panel's own axis shares it reproduces `c̄` exactly. And the
four-season map week 2 already uses to force L1 was **rejected** for this job, because it is
indexed by season and would therefore make the cycle input a function of the hot/cool dial —
injecting an inflation-to-inflation channel, of the wrong sign, into the very statistic `P1`
measures.

### 1.2 "Jointly", and what that does and does not mean — again

The joint log-likelihood is `L_hazard + L_inflation + L_policy + L_curve` and it
**block-diagonalises**, exactly as week 3's did and for exactly the same reason: on the
historical panel every path is *observed*. The season path comes from `grader_v2`'s labels,
the slope from the panel's own 10y−2y, the inflation gap from CPI minus L1's trend, and the
policy deviation from the observed rate minus L1's own Taylor anchor. So the cross-block
information is exactly zero and the joint maximum is attained blockwise. **That is a property
of the data and not an achievement of the design**, and it is stated here rather than left for
a reader to work out. What the joint fit buys is that every "no coupling" restriction nests
exactly and is therefore a likelihood-ratio test (§3.4), and that both halves of the loop come
from one likelihood on one panel. The coupling is a **generation-time** property.

Joint log-likelihood: **+2225.5160** = hazard −118.8401 + inflation +1972.8687 + policy
−39.4344 + curve +410.9218.

### 1.3 Nothing sealed was touched, and the fit reproduces the anchors

Every file in `stage2-prereg.json` and `spine-v2-prereg.json` is opened read-only; `src/` and
`schemas/` are untouched by this campaign. The inflation block **is** `M3`'s equation and the
curve block **is** `M4`'s — imported from `scripts/stage2_anchors.py`, not re-implemented — so
the engine's own fit and the sealed anchors must be the same numbers, and that is checked in
code rather than claimed in prose:

| identity | measured drift |
|---|---|
| `M3`'s selected lag | matches (10 months) |
| `M3`'s `lam_x` | 1.209e−14 |
| `M4`'s six curve coefficients | 4.841e−13 |
| `M4`'s `rho` | 1.277e−14 |
| `M4`'s history strict share (0.558667) | 2.811e−13 |
| week 3's committed hazard coefficients | 4.385e−13 |

The tolerance is 1e−11, and that is not slack: both artifacts round to twelve decimals, so an
exact refit of the identical equation agrees to a few units in the thirteenth by construction.
A tolerance of zero would be asserting that the committed JSON carries more digits than it
does. If any of these ever drifts, every verdict in this report is void.

---

## 2. The lag, chosen by the sealed rule

Ruling `SQ9` seals the **rule and the grid**, never a value: maximum likelihood on the
declared 25-lag grid (0 to 24 months), one parameter at every lag, the same months at every
lag so the likelihoods are comparable, the highest likelihood wins, and the whole profile is
published beside whatever it picks.

**Selected: `m` = 10 months.** The profile's top of the ridge, with the whole 25-point profile
in the artifact (`fit.inflation.lag_profile`):

| lag `m` | log-likelihood | `lam_x` | s.e. | t |
|---|---|---|---|---|
| **10** | **1972.8687** | **+0.006326** | 0.001063 | **+5.95** |
| 9 | 1972.6876 | +0.006315 | 0.001066 | +5.92 |
| 7 | 1969.8163 | +0.005767 | 0.001069 | +5.40 |
| 6 | 1969.1374 | +0.005658 | 0.001075 | +5.26 |
| 8 | 1968.9680 | +0.005599 | 0.001070 | +5.23 |
| 5 | 1967.6518 | +0.005375 | 0.001082 | +4.97 |
| … | | | | |
| 24 | 1955.4833 | (the floor of the profile) | | |

The likelihood ratio against no coupling at the selected lag is **34.80 on 1 df**.

**And the profile is a ridge, not a peak** — which is `L8` of the sealed limitations register,
confirmed rather than discovered. Ten and nine are separated by 0.18 of log-likelihood, and
the anchors already recorded that only 57% of bootstrap draws select within three months of
ten and that the classifier-cycle arm selects **two**. Whatever this fit picked had to be
published with the profile beside it and never as a determined quantity; it is, and it is not.

---

## 3. The fitted coefficients, their standard errors, and what is not identified

**Identifiability with roughly twelve recessions was named as THE risk and it bit two of the
five new coefficients.** A coefficient is called **unidentified** here when its 95% interval
spans both signs — applied uniformly, reported for every coefficient, and not softened for the
ones that fail it.

| block | coefficient | estimate | s.e. | t | 95% spans both signs? |
|---|---|---|---|---|---|
| inflation | **`lam_x`** (growth → inflation) | **+0.006326** | 0.001063 | **+5.95** | no |
| policy | `lam_u` (policy leans on inflation) | +0.09215 | 0.06052 | +1.52 | **YES** |
| policy | `lam_c` (policy leans on the cycle) | +0.03469 | 0.01359 | +2.55 | no |
| curve | **`c_i`** (curve ← rule-implied rate) | **−0.24032** | 0.01101 | **−21.83** | no |
| curve | `c_x` (curve ← inflation gap) | +0.49203 | 0.26150 | +1.88 | **YES** |
| curve | `C` (contracting level shift) | −0.07926 | 0.04322 | −1.83 | yes |
| curve | `E` (expansion age) | −0.03845 | 0.01555 | −2.47 | no |
| curve | `K` (contraction age) | +0.02681 | 0.01986 | +1.35 | yes |
| hazard | `cov_expanding[curve_slope]` | −1.48880 | 0.50412 | −2.95 | no |

Curve residual: `rho` = **0.98095** (s.e. 0.00682), innovation sd 0.14531 pp, stationary sd
**0.74799** pp. R² = 0.2464 on 809 months. Inflation block: persistence `a` = **0.994814**,
innovation sd 0.019790 pp, stationary sd 0.19457 pp. Policy block: `φ_u` = 0.96141, innovation
sd 0.25401.

**Said plainly, because the task asks for it plainly.** Two load-bearing couplings are **not
identified on this panel**:

- **`c_x` — inflation's channel into the yield curve — is not established.** t = 1.88, and the
  likelihood-ratio test for dropping it is 3.53 on 1 df, p = 0.060. The design document's
  §1.2 finding was that "inflation reaches the generated curve through no channel whatsoever";
  stage 2 builds the channel, and 68 years of one country's history cannot say how big it is.
  The sign is right and the size is a coin-toss away from zero.
- **`lam_u` — policy leaning harder on inflation than the rule says — is not established.**
  t = 1.52. Its companion `lam_c` (leaning on the cycle) *is* identified at t = 2.55, and the
  two together reject "policy is noise" at a likelihood ratio of 7.10 on 2 df. So the *block*
  earns its place and the *inflation* half of it does not.

**Neither stops the campaign, and which one would was pre-declared.** The design document's
**Cheap Exit A** names `lam_x` and nothing else: "If `lam_x` — inflation's response to growth
— is not significant on the panel, stop." It is not: t = +5.95. Deciding after the estimates
were visible that some other coefficient was the real stop condition would be a goalpost move
in the direction this campaign has twice refused to move in, so nothing was reclassified.

### 3.1 The correlation structure, which is as much of the answer as the standard errors

Cross-block correlations are **exactly zero** — not small, zero — because the blocks share no
parameters and every path they read is observed. That is the block-diagonality of §1.2 seen
from the other side, and it means the honest correlation report is *within* the curve block:

| | intercept | `c_i` | `c_x` | `C` | `E` | `K` |
|---|---|---|---|---|---|---|
| intercept | +1.000 | +0.031 | +0.015 | −0.000 | +0.007 | −0.004 |
| `c_i` | +0.031 | +1.000 | −0.199 | −0.064 | −0.081 | +0.110 |
| `c_x` | +0.015 | −0.199 | +1.000 | −0.010 | +0.036 | −0.037 |
| `C` | −0.000 | −0.064 | −0.010 | +1.000 | **+0.741** | **−0.688** |
| `E` | +0.007 | −0.081 | +0.036 | +0.741 | +1.000 | −0.512 |
| `K` | −0.004 | +0.110 | −0.037 | −0.688 | −0.512 | +1.000 |

The largest off-diagonal is **0.741**, and it is inside the *season block* — the three columns
that describe the same object (a growth spell and its age) from three directions. That is
week 3's own structure, inherited, and it is why the design document warned that `expansion_age`
was pinned only to a factor of 2.5. The design document's other identifiability worry — that
`c_i` and `c_x` "both read policy" and would fight — **did not materialise**: they correlate
at −0.199, and `c_x`'s wide interval is thinness of signal, not collinearity with `c_i`.

### 3.2 The likelihood-ratio tests, every restriction nested exactly

| restriction | df | LR | p |
|---|---|---|---|
| `c_i = 0` (curve does not read the policy rule) | 1 | **377.41** | 0.000 |
| `c_C = c_E = c_K = 0` (no season block) | 3 | 6.11 | 0.107 |
| `c_x = 0` (curve does not read the inflation gap) | 1 | 3.53 | 0.060 |
| `lam_x = 0` (inflation does not follow growth) | 1 | **34.80** | ≈ 0 |
| `lam_u = lam_c = 0` (policy is noise) | 2 | 7.10 | — |
| everything economic zeroed | 5 | 396.30 | — |

One reading dominates the table: **the rule-implied policy rate is the curve's real content,
by two orders of magnitude over everything else that was added.** And week 3's season block,
which was significant at p = 0.0066 against `u_hat`, is **no longer significant** (p = 0.107)
once the curve can read the actual rule — the growth information the season term was carrying
was largely the policy rate's, seen through a proxy.

---

## 4. The eight bars, on fifty unconditional decades

Seed **20260821** — week 3's own verification seed, re-used deliberately so the batch is the
same batch identity and a change of verdict is attributable to the engine and not to a
different tape. Fifty decades, fifty attempts (the unconditional arm rejects nothing).
Stream hygiene: 904 whole tapes drawn and compared; one new per-decade offset this campaign
(`policydev` = 1674811), proved disjoint from `spine_v2_fit`'s four, week 3's `openage`, every
value in `ah.gen.spine.LAYER_OFFSETS`, and the platform's `base + 7919·k` ladder.

| bar | what it asks | sealed band / floor | **measured** | verdict |
|---|---|---|---|---|
| **T1** | does tightening cause downturns? | [1.775283, 3.347362] | **2.23925** | **PASS** |
| **O1** | do the seasons turn the right way round? | ≥ 0.5180669 | **0.560825** | **PASS** |
| **D1** | recession spell length | [0.0, 5.0] months | **2.0** | **PASS** |
| **D2** | stagflation spell length | [1.0, 7.0] months | **4.0** | **PASS** |
| **D3** | recovery spell length | [2.0, 8.0] months | **4.0** | **PASS** |
| **D4** | expansion spell length | [1.0, 7.0] months | **3.0** | **PASS** |
| **P1** | do the two dials keep time with each other? | both move types (below) | **binding margin +0.042074** | **PASS** |
| **P2** | is the curve made of economics? | [0.391707, 0.673371] | **0.770683** | **FAIL — above** |
| A1, A2, R1, R2 | | | **not measured** | **week C** |

**A1 and A2 need the flesh** — verbatim real months of asset returns compiled onto the spine,
which this loop does not run — **`R1` needs the institutional twin's over-commitment grid and
`R2` needs an ensemble and the panel source.** None of the four is measured here, none is
estimated, and "seven of eight" is a statement about eight bars and not about the exam. Four
of the twelve have still never been run.

### 4.1 `P1`, per move type

| move type | clockwise fraction | the batch's own null | **departure** | sealed threshold | verdict |
|---|---|---|---|---|---|
| growth flips | 0.590244 (205 transitions) | 0.488492 | **+0.101752** | 0.040330 | PASS |
| inflation crossings | 0.563433 (268 transitions) | 0.489913 | **+0.073520** | 0.031446 | PASS |

Both clear, which is what the bar requires. The departures are about **74% and 59% of
history's own** (0.138168 and 0.125093) — so this engine has most of history's phase relation
rather than the third week 3 had. The null is the batch's own within-decade scramble,
exhaustively enumerated, seedless.

### 4.2 `O1`'s disclosure under the stage-2 primary construct

Ruling `SQ1` keeps `O1` byte-frozen and publishes the windowing-symmetric floor beside it as a
disclosure. The generated statistic is bit-identical under both constructs, so this is the
same number read against a different floor: **0.560825 against a symmetric floor of 0.515672,
clearing it by +0.045153.** The two constructs agree, so the disagreement stop-question §8.5
of the exam delta reserved does not arise.

### 4.3 `P2`, and why the failure is on the upper side

| component | generated sd (pp) | history's (pp) |
|---|---|---|
| policy rule (`c_i`·`i_rule`) | **1.365831** | 0.836190 |
| inflation gap (`c_x`·`x`) | 0.106533 | 0.078326 |
| season term | 0.059041 | 0.053794 |
| AR(1) residual, stationary (a model parameter) | 0.747993 | 0.747993 |
| **strict economic share** | **0.770683** | 0.558667 |

The exogenous block is empty on both sides, which is the like-for-like the primary curve arm
was chosen to get. So the share's overshoot is not a classification argument — it is
**dispersion**:

| quantity | generated ÷ history |
|---|---|
| rule-implied policy rate | **1.635×** |
| yield-curve slope | **1.735×** |
| inflation gap | 1.356× |

The generated rule-implied rate has a standard deviation of 5.683 pp against history's
3.476 pp. The coefficients are history's — nothing was scaled — so the numerator of a *share*
rises without any coupling changing, and the curve inherits it: generated slope sd **1.4623 pp
against history's 0.8427 pp**. That dispersion is **L1's**, not stage 2's: fifty decades each
re-draw their initial states from the posterior, and the spread of L1's `r*` and `pi*` across
those draws is wider than the single 68-year path history realised. `P2` is doing exactly the
job its upper edge was written for — "above it, the curve is a deterministic readout of the
state and a player can learn a rule that no real market would ever reward" — and it is
catching a defect that stage 2 inherited rather than one it introduced.

---

## 5. The attribution: which arrow moved which bar

**This is the section to read if you read one.** Stage 2 turns on two mechanisms at once, and
a campaign that has twice stopped at a frontier has no business shipping an unattributed pass.
Both were switched independently, from the same seed, and judged by the same sealed judges:

| curve | `lam_x` | `O1` | `T1` | `P2` share | `P1` growth / inflation | generated slope sd | bars passing |
|---|---|---|---|---|---|---|---|
| week 3's equation | ×0 | 0.5385 | 1.765 | 0.0247 | +0.0614 / +0.0569 | 0.745 | 6 |
| week 3's equation | ×1 | 0.5362 | 1.765 | 0.0242 | +0.0584 / +0.0563 | 0.748 | 6 |
| **stage 2** | **×0** | **0.5620** | 2.361 | 0.7717 | +0.1027 / +0.0720 | 1.454 | 7 |
| **stage 2 (the fit)** | **×1** | **0.5608** | 2.239 | 0.7707 | +0.1018 / +0.0735 | 1.462 | 7 |

> **`O1` moved by the coupling: −0.0012. `O1` moved by the curve: +0.0235.**

Read down the `lam_x` axis and nothing happens — twice. Read across the curve axis and
everything happens. **The growth → inflation arrow, which is the thing stage 2 was funded to
build and the thing `P1` was written to test, contributes nothing measurable at fifty
decades.**

**Why, in one line of arithmetic.** The fitted persistence is `a` = 0.994814, a **half-life of
133 months**. The long-run inflation gap per unit of cycle input is `lam_x/(1−a)` = **1.2199
pp**, which is a large number — and the calibrated axis swing is 0.991, so a permanent
expansion would eventually run about 1.21 pp hotter than a permanent contraction. But growth
spells in this engine last two to four years, over which only `1 − a^L` of that adjustment
happens: **11.7% at 24 months, 21% at 48.** The channel is real, it is significant, and it
operates on a timescale an order of magnitude longer than the cycle it is supposed to be
coupled to. Its own signature confirms it — the mean inflation gap by growth-spell age barely
separates the two axes (expanding +0.124 pp against contracting +0.056 pp in the 13–36 month
bucket, and the 37+ bucket separates the wrong way).

**So what did move `P1`?** Not the arrow `P1` was written against. The curve now reads
`i_rule = r* + pi* + φ_pi·x + φ_c·c`, which contains **inflation**; the curve drives the growth
hazard at a nine-month lead; so the engine gained an **inflation → curve → growth** channel,
which is the *reverse* of the arrow the design document diagnosed as missing. A phase relation
between two dials does not care which way the arrow points, and `P1` is a phase statistic. It
is passing honestly and for the wrong reason, and the exam has no bar that can tell those
apart — which is a fact about the exam and is now on the record.

**A caution attached to the whole table.** The `week3`-curve rows are week 3's *equation*
inside the stage-2 loop, not week 3's engine reproduced bit for bit: they run on the stage-2
policy deviation (which has loadings `lam_u`, `lam_c`) rather than week 2's input-free OU, and
their tape differs. That is why they read `O1` = 0.5385 where week 3's committed engine read
0.5241. The arm isolates an arrow; it does not re-measure an engine, and week 3's engine
remains on the record as the anchors retro-judged it.

---

## 6. The frontier, mapped — and the row that is not being taken

Scaling only, never tuning; every row re-simulated from the same seed and re-judged.

**The coupling axis (`lam_x` × 0, 0.5, 1, 2, 4):** seven bars pass at every point. `O1` reads
0.5620, 0.5565, 0.5608, 0.5489, 0.5556 — a range of 0.013 with no monotone trend, which is
noise at fifty decades. `P2` reads 0.7717 → 0.7692, moving by 0.0025 across a sixteen-fold
change in the coupling. **There is no frontier on this axis.** It is flat, and that flatness
is the campaign's central finding, not a null result to be buried.

**The curve-loading axis (`c_i`, `c_x` and the season block scaled together):**

| multiplier | `O1` | `T1` | `P2` share | `P1` growth / inflation | bars passing |
|---|---|---|---|---|---|
| ×0 | 0.5124 | 1.484 | 0.0000 | +0.0294 / +0.0393 | 4 (`D1`–`D4`) |
| **×0.5** | 0.5655 | 1.984 | **0.4570** | +0.1085 / +0.0817 | **8 — all of them** |
| ×1 (the fit) | 0.5608 | 2.239 | 0.7707 | +0.1018 / +0.0735 | 7 |
| ×2 | 0.5473 | 2.594 | 0.9307 | +0.0968 / +0.0548 | 7 |

This axis has a real frontier and it is monotone in the direction `P2`'s first anti-test
obligation requires: the economic share rises 0.000 → 0.457 → 0.771 → 0.931 as the loadings
scale. `P2` is inside the band only at ×0.5.

> **The ×0.5 row passes all eight bars and it is NOT being adopted.** It is not a fit; it is
> the fitted curve with its coefficients halved by hand, and halving a coefficient because a
> bar is on the other side of it is the definition of tuning past a conflict. Two campaigns
> have ended at a frontier and the discipline held both times; it holds here. The verdict is
> the fitted point, the fitted point is **FRONTIER**, and the ×0.5 row is published so the
> owner can see exactly what was left on the table and rule on it if they wish.

What the row does say, legitimately, is a **diagnosis of size**: the economic block's variance
is 1.8803 against the 1.1535 that the band's upper edge allows at this residual — an overshoot
of about **63%**, not an order of magnitude. And the dispersion ratios in §4.3 say where that
63% lives: in L1's own state dispersion across decades, not in the curve's coefficients. The
right fix is therefore not on this axis at all.

---

## 7. The label-stability obligation, and the coupling coefficient's stability

The sealed rule: a statistic that moves by more than **its own standard error** across the
nine dial arms escalates to soft labels, and both are reported. It was applied to every new
coefficient separately, because they do not all depend on the classifier in the same way — and
the way they differ is itself the finding.

| coefficient | worst arm | moves by (s.e.) | escalated? |
|---|---|---|---|
| **`lam_x` (primary, USREC)** | — | **0.000** | no — **invariant by construction** |
| `lam_x` (grader-axis refit) | growth line −50 bp | +0.659 | no |
| `c_i` | growth line +50 bp | +0.181 | no |
| `c_x` | growth line +50 bp | −0.090 | no |
| `cov_expanding[curve_slope]` (the v2 hazard) | inflation +, growth − | **−1.044** | **YES** |

**The coupling coefficient's stability verdict, stated the way the obligation asks.** The
primary `lam_x` is fitted against `1 − 2×USREC`, which is **not a function of the classifier's
dials at all** — so it is invariant across the whole grid by construction. That is a real
stability property and it is *not* a measurement: it says the coefficient cannot move, not
that it has been shown not to. The dial sensitivity that genuinely exists is carried by the
grader-axis refit, the same equation on the classifier's own growth axis, and **it moves by
0.66 of its own standard error at worst — inside the rule, no escalation.** Its selected lag,
however, moves between **1 and 2 months** across the arms (against the USREC arm's 10), which
is `L8` again: the lag is the unstable part, not the size.

The one escalation is the **v2 hazard's transmission coefficient**, at −1.04 s.e. That is week
3's own recorded escalation, inherited unchanged — stage 2 did not touch the hazard and did
not make it worse.

---

## 8. The disclosure arms — every construct the primary did not take

None of these can supply a verdict. They exist so the cost of each primary choice is a number.

**The inflation block on the classifier's own growth axis** (M3's own cycle-input sensitivity
arm; the object the *engine* generates): selected lag **2 months**, `lam_x` = +0.005021
(s.e. 0.000823, t = **+6.10**), persistence 0.998611, LR 36.49, long-run gap per unit cycle
**3.614 pp**. So the channel is *more* significant on the engine's own axis and *even slower*
(`a` = 0.998611 is a half-life of 499 months). Taking this arm would have made the coupling
more inert, not less. It changes no conclusion in §5.

**The hazard with the inflation gap substituted for the trend gap** (the design document's
literal `x_t`): log-likelihood **−119.7234 against the baseline's −118.8401**, so the
substitution fits **worse** by 0.88 at the same parameter count, and the transmission
coefficient moves from −1.4888 to −1.4139. The primary choice costs nothing and the design
document's notation would have cost a little.

**The curve with `u_hat` restored beside the rule-implied rate**: `c_u` = −0.0748,
LR = 10.62 on 1 df, so `u` does carry information the rule misses on history — and history's
strict share falls from 0.5587 to **0.5501** once `u` sits in the denominator as exogenous.
`c_i` is essentially unchanged (−0.2329 against −0.2403). Restoring `u` would have lowered the
generated share too, and would therefore have moved `P2` in the direction of its band — which
is precisely why it was **not** taken after the bars were read. The primary was fixed in code
first; this arm is reported, not adopted.

---

## 9. What the v2 fitted forms did, under the coupling

The task asked whether the hazard and the duration dependence keep their v2 fitted forms, and
whether the coupling changes them materially. **Both keep them, and the coupling changes
neither.**

- **The hazard is byte-for-byte week 3's** — max absolute coefficient drift **4.385e−13**
  against the committed artifact, which is the twelve-digit rounding and nothing else. Its
  duration term `b_s·log(dwell)` is unchanged, its nine-month curve lead is unchanged (the
  lead was re-selected by the same likelihood and picked 9 again), and its transmission
  coefficient is unchanged. It was not re-tuned to reach a bar, and the check is in code.
- **The curve's duration dependence — week 3's `C`, `E`, `K` season block — keeps its fitted
  form and loses its significance.** The three coefficients barely move in sign or rough size,
  but the likelihood ratio for dropping them falls from week 3's **12.23 (p = 0.0066)** to
  **6.11 (p = 0.107)**. That is material and it is a *result*, not a defect: once the curve can
  read the actual rule-implied policy rate, most of what the season term was doing turns out
  to have been the policy rate seen through a proxy. The block is kept — dropping a
  pre-existing fitted form because a new regressor stole its significance would be a modelling
  choice made after the fact — and its demotion is reported.

---

## 10. Limitations, measured

**M1 — the coupling is significant and inert.** §5. `lam_x` clears Cheap Exit A on the panel
and changes no verdict in a decade. Every sentence anyone writes about stage 2 "coupling
growth to inflation" has to carry this.

**M2 — `P1` passes through the reverse arrow.** The phase relation the bar measures is
delivered by inflation → curve → growth, not growth → inflation. `P1` is a phase statistic and
cannot distinguish the two. The sealed anti-test sweep that qualified `P1` swept a *synthetic*
coupling in which inflation is a lagged copy of growth; it was monotone, correctly, and it
could not have caught this.

**M3 — two load-bearing coefficients are unidentified** (`c_x` at t = 1.88, `lam_u` at
t = 1.52). §3.

**M4 — the generated world is over-dispersed** and `P2` catches it: the rule-implied rate at
1.63× history and the slope at 1.74×. This is inherited from L1's across-decade state spread
and no stage-2 coefficient touches it.

**M5 — the inflation innovation is drawn i.i.d.**, which is the equation as fitted. Its
residual carries a lag-1 autocorrelation of 0.198 from the trailing-12-month construction.
Simulating that structure would be simulating a model that was not estimated; it is declared
rather than added.

**M6 — the generated inflation level is half history's**: mean trailing CPI **1.81 pp against
history's 3.49 pp**, with the hot share nevertheless close (0.372 against 0.392) because the
across-decade spread is wide. This is L1's, is not new to stage 2, and is not something any
bar in this exam looks at.

**M7 — every sealed limitation of the exam is inherited whole**, including `L1` (`P1`'s size
is 9.0% against an uncoupled engine, so a single `P1` pass is evidence at about the strength of
one significance test), `L2` (`P1`'s thresholds are pinned only to a factor of 2 to 2.5),
`L9` (`P2`'s tape noise is unmeasured) and `L11` (both power figures are upper bounds).
**`L1` deserves emphasis here more than anywhere:** this engine's `P1` departures are 2.5× and
2.3× the sealed thresholds, well clear of a 9% false-positive band — but the reason they are
clear is `M2`, not the coupling.

**M8 — the standing caveat is unchanged.** Nothing built on this generator line is a
convincing model of history, the holdout is spent, and no appeal to held-out data is available
to any result stage 2 produces.

---

## 11. Status

**FRONTIER.** Seven of eight pre-flesh bars pass at the fitted point; `P2` fails from above at
0.7707 against [0.3917, 0.6734]. The eight-of-eight row on the frontier is a hand-scaled
coefficient and is not taken.

Whether this frontier unblocks week C is **not this report's call**. What it can say is what
week C would inherit: an engine whose `O1` clears both the sealed and the symmetric floor, whose
phase relation is real and arrives through the reverse arrow, whose curve is 74% too volatile,
and whose funded mechanism is measurably inert.

---

## 12. Stop-questions for the owner

1. **The coupling does not work and the campaign passed seven bars anyway. Which of those is
   the result?** Stage 2 was funded on §1.1's diagnosis — that `O1` needs a growth → inflation
   phase channel. The channel was built, it is significant on the panel, and switching it off
   changes `O1` by −0.0012. What moved the bars is §1.2's arrow. The honest options are (a)
   report stage 2 as having found `O1` reachable by a *different* mechanism than the one it
   bought, which is what this report does, or (b) treat a pass that the funded mechanism did
   not produce as not a pass at all. This is a ruling, not a measurement, and it is the whole
   decision.

2. **`P1` passes through the reverse arrow, and no bar in the sealed exam can see the
   difference.** Is that acceptable as-is, or does `P1` need a directional companion? A
   companion would be a **new bar written after a coupling was fitted**, which the exam delta's
   own opening sentence calls a description rather than a test — so the answer may have to be
   "acceptable, disclosed" rather than "fix it". Ruling this now, before week C, is cheaper
   than ruling it after A1/A2 land.

3. **`P2` fails on inherited dispersion. Is that stage 2's failure to own?** The generated
   rule-implied rate is 1.63× history's because L1 re-draws initial states per decade; no
   stage-2 coefficient is involved. Three readings are available and they lead different
   places: it is a genuine `P2` FAIL and stage 2 owns it; it is an L1 defect that stage 2 made
   *visible* (the ER-14 pattern — coupling the spine makes an existing blindness more visible,
   not worse); or the batch construction should be reconsidered before `P2` is read at all.

4. **`c_x` is not identified, and it is the coefficient the §1.2 fix rests on.** t = 1.88,
   p = 0.060 for dropping it. "Inflation now reaches the curve" is true as a structural
   statement and unpinned as a quantity. Is a directionally-correct, statistically-marginal
   channel enough to call §1.2 addressed?

5. **The season block lost its significance** (LR 12.23 → 6.11, p 0.0066 → 0.107) once the
   curve reads the rule. It was kept, because dropping a pre-existing fitted form after a new
   regressor steals its significance is a post-hoc modelling choice. Confirm the keep, or rule
   that the parsimonious curve is the one to carry into week C.

6. **The ×0.5-loading row passes all eight bars and was deliberately left on the table.** It
   is named here so the refusal is visible rather than silent. If the owner wants it explored,
   that is a ruling to take in the open — and it would need a re-derivation, not an adoption,
   because a halved coefficient is not a fit.
