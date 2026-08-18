# The spine v2 engine, week 2: what was fitted, and what it can and cannot do

**Date:** 2026-08-17 · **Branch:** `spine2-02-fit` · **Status: FRONTIER.**
**Script:** `scripts/spine_v2_fit.py` (new, unhashed). **Parameters:**
`docs/superpowers/specs/spine-v2-fitted-params.json` (new, unhashed).
**Exam:** `docs/superpowers/specs/2026-08-17-spine-v2-exam.md`, SEALED.
**Seal:** `docs/superpowers/specs/spine-v2-prereg.json`. **Nothing hashed by that seal was
touched**; the twelve hashed paths were read, and the grader and the judges were *imported*,
never re-implemented. Nothing in `src/` and nothing in `schemas/` was edited — `src/`
integration is week 3.

---

## The one-paragraph answer

An economic engine was fitted to history: a monthly hazard for season transitions, driven by
the curve, the credit gap, the inflation gap and a drawdown state, with duration dependence
fitted jointly with the covariate effects. It was then simulated standalone — climate plus
seasons, no flesh, no block sampler — and measured against the six sealed bars that can be
measured before the sampler exists. **The four persistence bars (D1–D4) pass comfortably, at
every point on the frontier, in both arms.** **The transmission bar (T1) and the ordering bar
(O1) do not pass together at any transmission strength.** They are in direct opposition: the
sweep below shows T1 rising and O1 falling as the transmission coefficient is scaled up, and
no multiplier puts both inside their bands. That is the campaign's two-week cheap-failure
exit, and the mechanism behind it is identified and measured rather than guessed: the fitted
engine has causation running curve → season but **no feedback running season → curve**, so
its inverted-curve months land inside downturns instead of ahead of them. Week 3 is **not**
unblocked. Nothing was tuned past the frontier.

---

## 1. What was fitted, in plain language

The four seasons of the investment clock are two yes/no questions: is the economy expanding,
and is inflation hot. The exam's own grader (`grader_v2`) answers the first from the month's
`regime_ruleset_v1` label and the second from trailing CPI against the era line of 3.351323828920571 pp.

The engine keeps that structure exactly, because that is what makes the generated side and
the history side the same measurement:

- **The inflation dial is read, not sampled.** In a generated decade it is read off the
  simulated inflation path, the same way history's is read off observed trailing CPI.
- **The growth dial is the chain.** Its monthly probability of flipping — expanding to
  contracting, or back — is what was fitted.

So a season ends in a generated world for exactly the two reasons it ends in a real one:
the growth axis turned, or inflation crossed the line.

### The hazard and its likelihood

For each at-risk month `t`, with `s` the season, `d` the months elapsed in the current
**season** spell (counting from 1), and `z` the four covariates:

```
logit h_t = a[s_t] + b[s_t] * log(d_t) + z_t' g[growth axis of s_t]
y_t       = 1 if the growth axis at t+1 differs from the growth axis at t
log L     = sum_t w_t * [ y_t log h_t + (1 - y_t) log(1 - h_t) ]
```

That is an ordinary weighted Bernoulli (logistic) log-likelihood over months, maximised by
iteratively reweighted least squares. It is deterministic — no random start, no tie-break —
and it returns the inverse Fisher information, which is where every standard error quoted
below comes from. Sixteen parameters: four season intercepts, four season log-dwell slopes,
and four covariate loadings for each of the two directions.

**Why the covariate loadings are direction-specific.** A flip out of an expanding season
*starts* a downturn; a flip out of a contracting season *ends* one. The exam's causal story
is directional — tight policy is supposed to bring downturns on, not to end them sooner — so
forcing one shared loading would have made T1 untestable by construction. The two blocks are
`cov_expanding[...]` and `cov_contracting[...]` below.

**Duration dependence, and why this form.** `b[s] * log(d)` is a discrete-time
log-logistic/Weibull-style aging term, one slope per season, in the same design matrix and
the same Fisher information as the covariate loadings — so the two are fitted *jointly* and
their trade-off is one object rather than two sequential fits. It was chosen as the simplest
form that can bend a season's dwell distribution without adding a state: one parameter per
season, monotone in the direction its sign says, and `b[s] = 0` is exactly the memoryless
geometric chain. That nesting is the justification: "no duration dependence" is not an
argument to be had, it is a t-ratio to be read. (It reads small — see §3.)

### At-risk months: the completed-transition rule

A month enters the likelihood only if its season is defined (trailing inflation exists), the
next month's season is defined, every covariate is readable, and it is not inside the panel's
**first** season spell — whose start is unobserved, so its dwell is unknown (left truncation).
The panel's last month has no `t+1` and drops out, which is the right-censoring half of the
same rule. On the campaign vintage (`2026-08-10.1`, 813 months, 1953-04 to 2020-12) that
leaves **792 at-risk months carrying 35 growth-axis flips**.

Thirty-five events is thin for sixteen parameters and it is stated here rather than buried:
it is the reason several coefficients below carry t-ratios under 1, and it is a fact about
sixty-eight years of American economic history, not about the estimator.

---

## 2. The attenuation this fit exists to remove

**The pilot's own words.** `src/ah/gen/regimes/semimarkov.py`'s module docstring records the
defect: the historical L2 fit used the observed `GS10 − TB3MS` slope, while at simulation time
the same covariate becomes `psi0 − phi_c0 * c(R_t)` — "The proxy carries the level of the
historical slope but compresses its variance (no simulated inversions), so the inversion
channel of the fitted hazards is attenuated at generation time — recorded as a v1 limitation
in regime-fit-report.md."

**How bad it is, measured on the pinned artifact.** `psi0 = 0.6937814976865678`,
`phi_c0 = 0.0930147890808868`, and `cycle_by_regime` takes the values `{-1, 0.04, 1}`. So the
pilot's generation-time curve slope takes **three values, spanning 0.60 to 0.79 pp, and never
once goes below zero**. A hazard fitted on a covariate that is inverted in **18.3%** of
history's months is asked to generate worlds in which it is inverted **0%** of the time. Every
transmission verdict the pilot could have produced was decided by that before any coefficient
was estimated.

**What replaces it.** Each covariate is supplied at generation time by a quantity on the same
scale as the one it was fitted on, and the module *measures* the match rather than asserting
it. The measured ratios of simulated to historical standard deviation, over the 50-decade
premise-accepted batch:

| covariate | historical sd | simulated sd | ratio | note |
|---|---|---|---|---|
| `curve_slope` | 0.8427 pp | 0.7292 pp | **0.865** | inverted share 0.1833 historical vs **0.2752** simulated (pilot proxy: 0.0000) |
| `credit_gap` | 6.1939 | 3.6489 | **0.589** | L1's own simulated dispersion over ten years; not rescaled |
| `pi_gap` | 2.6551 pp | 4.2583 pp | **1.604** | L1's own; over-dispersed, see §6 |
| `drawdown_state` | 0.3212 | 0.4326 | **1.347** | a 0/1 dummy; the sd ratio is a firing-rate ratio (11.7% vs 24.9%) |

The curve is the one this campaign was funded for, and it is fixed: **0.865 of history's
dispersion and inversions in 27.5% of months, against a proxy that had none.**

### How the generated curve is built, and what it costs

The curve's variance in L1 lives in the **policy-deviation state `u`** — the OU deviation from
the Taylor anchor — and `u` is not one of the five contract states `simulate_decades` emits.
It is, however, exactly the anchor's residual, so it is recoverable on history:

```
u_t = policy_rate_t  -  [ r*_t + pi*_t + phi_pi (pi_obs_t - pi*_t) + phi_c c_t ]
```

with `r*`, `pi*` the L1 posterior-mean smoothed states, `phi_pi = 0.6246097900151228`,
`phi_c = 0.0930147890808868` the posterior means, and `c_t = 1 - 2*USREC` the same cycle proxy
L1 was fitted against. That gives `mean(u) = -0.2139`, `sd(u) = 0.2727`.

Standardise it (`u_hat`, mean 0 sd 1) and regress the panel's own `ust_10y - ust_2y` on it:

```
slope = 0.7086089371069557  -  0.5358012856236766 * u_hat  +  e
R^2 = 0.4042666701854173,  sd(e) = 0.6504227629213196
e is AR(1): rho = 0.947188362871781, innovation sd = 0.2085654060915283
```

The loading is negative, which is the economics: `u` above zero means policy is tighter than
its own anchor, and a tighter policy rate flattens the curve. At generation time `u` is
simulated as the OU its own fitted `hl_u`/`sigma_u` describe, standardised **by its own
stationary moments** rather than by the historical sample's — because the L1 posterior's
implied dispersion (0.561) and the smoothed path's realised dispersion (0.273) disagree by a
factor of two, and standardising both sides by each side's own stationary law is what stops
that mismatch leaking into the link. The residual is redrawn as its fitted AR(1).

**What that costs, stated plainly: 59.6% of the generated curve's variance is a fitted AR(1)
residual, not an L1 state.** The curve is L1-*linked*, not L1-*determined*. It is a very large
improvement on a three-valued constant, and it is not the same thing as a model-implied term
structure. Stage 2 of D-SP-6 — model-implied conditional means — is explicitly **not funded**,
and this is one of the places that shows.

### The drawdown state

The ruleset's own drawdown dummy is `1[equity drawdown <= -0.20]`, and a no-flesh spine has no
equity path — fitting on it would have re-created exactly the attenuation being removed. So
the covariate is a **36-month trailing drawdown of L1's valuation state `v`**, computed by the
identical formula on both sides, with its single threshold calibrated so its firing rate on
history *equals* the equity dummy's:

- equity dummy fires in **11.685%** of months (95 of 813);
- the `v`-drawdown threshold that matches that rate is **−0.3233655255884241**;
- the two dummies **agree on 94.10% of months**.

One calibrated constant, calibrated to history, not to a bar.

---

## 3. The fitted parameters

Selected lag for the curve first — because the exam's own causal story is a *lead*
relationship ("when monetary policy is tight, a downturn is more likely to begin over the
**following year**"), and a contemporaneous covariate cannot represent it. The lag is chosen
by **maximum likelihood over a stated grid at a constant parameter count and a common at-risk
set**, so it is a fit criterion and not a bar criterion. The whole profile is published:

| lag (months) | log-likelihood | transmission coefficient | standard error |
|---|---|---|---|
| 0 | −128.4951 | −0.4731 | 0.3755 |
| 3 | −125.4001 | −0.9523 | 0.4326 |
| 6 | −121.6556 | −0.9687 | 0.4234 |
| **9** | **−118.8247** | **−1.4865** | **0.5037** |
| 12 | −127.5794 | −0.5391 | 0.3754 |
| 15 | −127.9433 | −0.3615 | 0.3299 |
| 18 | −129.0797 | −0.1742 | 0.3079 |
| 24 | −129.5971 | −0.1279 | 0.2852 |

Nine months wins by 2.8 log-likelihood points over its nearest rival and 9.7 over the
contemporaneous specification, on identical degrees of freedom. Read as economics: **on this
panel the yield curve leads the turn by about three quarters.**

The fit at the selected lag — 35 flips, 792 at-risk months, log-likelihood **−118.8401**:

| parameter | estimate | s.e. | t |
|---|---|---|---|
| `intercept[recession]` | −0.8180 | 0.6908 | −1.18 |
| `intercept[stagflation]` | −2.1582 | 0.9658 | −2.23 |
| `intercept[recovery]` | −4.5023 | 1.0232 | −4.40 |
| `intercept[expansion]` | −3.4515 | 0.6790 | −5.08 |
| `log_dwell[recession]` | −0.4303 | 0.3523 | −1.22 |
| `log_dwell[stagflation]` | −0.0494 | 0.4348 | −0.11 |
| `log_dwell[recovery]` | +0.1008 | 0.3034 | +0.33 |
| `log_dwell[expansion]` | −0.1821 | 0.2899 | −0.63 |
| **`cov_expanding[curve_slope]`** | **−1.4888** | **0.5041** | **−2.95** |
| `cov_expanding[credit_gap]` | +0.2026 | 0.3249 | +0.62 |
| `cov_expanding[pi_gap]` | +0.3388 | 0.3636 | +0.93 |
| `cov_expanding[drawdown_state]` | +1.9949 | 1.2986 | +1.54 |
| `cov_contracting[curve_slope]` | +1.1904 | 0.3918 | +3.04 |
| `cov_contracting[credit_gap]` | +0.6689 | 0.3336 | +2.01 |
| `cov_contracting[pi_gap]` | +0.6307 | 0.3397 | +1.86 |
| `cov_contracting[drawdown_state]` | −1.7931 | 0.8392 | −2.14 |

**Three things worth reading off this table.**

1. **The transmission channel is real and it is significant.** A one-standard-deviation
   flatter curve nine months earlier multiplies the odds of an expanding season turning
   contracting by `exp(1.4888) = 4.43`, at t = −2.95. The pilot's version of this number
   could not have been anything but zero at generation time.
2. **The curve works in both directions, with the right signs.** `cov_contracting` is +1.1904
   (t = +3.04): a *steeper* curve raises the hazard of a contraction ending. Curves invert
   before downturns and steepen out of them; the fit finds both halves independently.
3. **Duration dependence is present but weak.** Every `log_dwell` t-ratio is under 1.3 in
   absolute value, so the memoryless nesting cannot be rejected on this sample. The three
   negative signs (recession, stagflation, expansion) say those seasons become *less* likely
   to turn the longer they run; recovery's small positive says the opposite. None of it is
   significant, and no D verdict below rests on it.

### The engine's other fitted numbers

| quantity | value | how it was derived |
|---|---|---|
| `season_cycle` (c_t per season) | recession 0.3761, stagflation −0.2793, recovery 1.0, expansion 1.0 | panel mean of `1 − 2*USREC` inside each `grader_v2` season — the construction `ah.gen.regimes.fit.build_fit_data` uses per regime, applied per season, so L1's `phi_c`/`delta_L` keep their fitted meaning |
| `initial_expanding_rate` | 0.7253 | the panel's own share of expanding months among defined seasons |
| inflation residual AR(1) | rho 0.99207, innovation sd 0.02008 | fitted on `observed CPI YoY − pi*`; L1's `pi*` tracks observed trailing CPI at correlation 0.99980 with residual sd 0.1597 pp, so this residual is small by construction |
| `stag_spell_rate` | 0.7778 (7 of 9 spells) | see §4 |

---

## 4. Labelling a generated month, and why it is not one label per season

The judge is handed `regime_ruleset_v1` labels and a trailing-inflation series, and does the
season classification itself through the sealed grader. So the simulator has to emit labels
whose contracting set inverts `grader_v2` exactly.

The naive mapping (season stagflation → `STAG`) is **wrong against history and it matters**,
because T1's downturn union is `REC`-or-`CRI` and is deliberately *not* re-anchored under the
mapping fix. On the panel, of the **95 contracting months at or above the ruleset's 4.0 pp CPI
line, 31 are labelled `STAG` and 64 are labelled `REC` or `CRI`** — so mapping the whole
stagflation season to `STAG` would place 111 of history's contracting months outside T1's
numerator when history places only 31 there, and mapping it all to `REC` would make every
generated contraction a T1 downturn when 14% of history's are not.

The rule adopted reproduces the split at its measured rate, drawn **once per contracting
spell** rather than per month:

- expanding season → `EXP`;
- a contracting spell containing any month at or above 4.0 pp draws once at
  **0.7778** (7 of the panel's 9 such spells actually carry a `STAG` label); if it draws
  `STAG`, its months at or above 4.0 pp are `STAG` and the rest `REC`, otherwise all `REC`.

Per-spell rather than per-month because `STAG` months clump in history, and a per-month coin
would chop `REC` runs into spurious extra onsets — manufacturing T1 structure out of labelling
noise.

**`CRI` is never emitted.** A no-flesh spine has no equity drawdown to fire the ruleset's
crisis disjunct on. So **T1's crisis-only disclosure is empty in this loop** (`lift` null,
both rates 0.0) and is reported empty rather than faked.

**Both of these — the curve lag and the label split — were specified after a first run had
already produced a T1 miss.** That is stated here rather than smoothed over. Neither was
chosen by looking at T1: the lag was chosen by likelihood on a pre-stated grid, and the label
split was chosen by counting history's own labels. The first run's numbers are on the record
in this report's own §7 so the movement is visible.

---

## 5. The label-stability obligation

The sealed section's obligation, discharged in full. The statistic tracked is
`cov_expanding[curve_slope]` — the fitted transmission strength — and the decision rule is the
one the campaign agreed: **if it moves by more than its own standard error across arms,
escalate to soft labels and report both.**

Baseline: **−1.4888**, standard error **0.5041**.

| arm | transmission | s.e. | movement, in baseline SEs |
|---|---|---|---|
| baseline | −1.4888 | 0.5041 | 0.000 |
| inflation line −50bp | −1.4824 | 0.5071 | +0.013 |
| inflation line +50bp | −1.4249 | 0.5167 | +0.127 |
| growth line −50bp | −1.5163 | 0.4916 | −0.055 |
| growth line +50bp | −0.9876 | 0.3943 | +0.994 |
| both −50bp | −1.5409 | 0.5099 | −0.103 |
| inflation −50 / growth +50 | −0.9995 | 0.4126 | +0.971 |
| **inflation +50 / growth −50** | **−2.0152** | **0.6169** | **−1.044** |
| both +50bp | −1.0392 | 0.4231 | +0.892 |
| borderline months down-weighted | −1.3293 | 0.5180 | +0.316 |
| **soft labels (the escalation)** | **−1.0785** | **0.6185** | **+0.814** |

**Verdict: UNSTABLE — escalated, both reported.** One arm (inflation line +50bp with growth
line −50bp) moves the transmission coefficient by **1.044** of its own standard errors, just
past the threshold, and three further arms sit between 0.89 and 0.99. So the obligation's
escalation fired and the soft-label refit was run: weighting every month by a logistic
confidence in each dial (never zero, so no month is dropped — that is what soft membership
means) gives **−1.0785**, 0.814 SEs from the baseline and still significantly negative.

**The honest reading.** The transmission channel survives every arm with the right sign and a
similar order of magnitude — the range across all eleven arms is −0.99 to −2.02 — but its
*size* is not pinned down to better than about a factor of two by a classifier whose dials
can each move half a point. Every transmission number quoted in this report should be read
with that beside it. The down-weighting arm is the reassuring one: dropping the months nearest
the lines moves the coefficient by only 0.32 SE, so the estimate does not rest on the
borderline cases. It is the *joint* perturbation of both dials in opposite directions that
bites, which is what §3 of the exam already found for D2.

---

## 6. The in-model verification loop, and its six readings

**What was simulated.** 50 decades of 120 months each (the seal's own `n_seeds = 50`), climate
plus seasons only — **no flesh, no block sampler, no asset returns**. The standard premise is
the one spine preset the platform carries (`src/ah/presets/spine_pilot.json`): supply shock,
arriving quarter 8, `inflation_above_trend` backdrop, slow recovery. Premise acceptance uses
`ah.gen.spine._reject_reason`'s clauses and its imported constants verbatim, with "in a
contraction" read off this layer's own contracting axis. **687 attempts produced 50 accepted
decades** (rejections: 481 backdrop, 143 arrival, 13 slow-recovery).

**Determinism and stream discipline.** Every draw comes from `numpy.random.Generator(PCG64)`.
Four per-decade byte offsets (`seasons` 601387, `slope` 715393, `inflnoise` 829417, `labels`
1063441), all distinct from `ah.gen.spine.LAYER_OFFSETS`' five; the premise-attempt loop
advances by a **new stride, `SPINE2_ATTEMPT_STRIDE = 32452843`** — prime, coprime to the
platform's 7919, and different from `ah.gen.spine.ATTEMPT_STRIDE` (104395301). The
distinctness is *proved numerically* by `assert_distinct_tapes`, which draws the first eight
float64s of **520 streams** and checks that no two coincide and that no attempt-strided season
stream lands on the platform's own `base_seed + 7919*k` ladder. L1's own offset is 0 — the
same as the pilot's — because that call *is* `simulate_decades`, which owns its per-decade
stream discipline; that reuse is intended and is excluded from the ladder check by name.

**The measurements were taken by the sealed judges themselves**, imported from
`scripts/spine_v2_report.py` and unmodified: `judge_t1`, `judge_o1`, `judge_d1`…`judge_d4`,
reading thresholds from `spine-v2-prereg.json`.

### The six readings, against their sealed bands

Headline arm — the 50 premise-accepted decades:

| bar | what it asks | sealed band | measured | verdict |
|---|---|---|---|---|
| **T1** | does tightening cause downturns? | **[1.7752827491108736, 3.3473622102535145]** | **1.230161** | **FAIL** |
| **O1** | do the seasons turn clockwise? | **≥ 0.5180669104991394** | **0.500707** | **FAIL** |
| **D1** | recession dwell, months | **[0, 5]** | **2** | PASS |
| **D2** | stagflation dwell, months | **[1, 7]** | **3** | PASS |
| **D3** | recovery dwell, months | **[2, 8]** | **3** | PASS |
| **D4** | expansion dwell, months | **[1, 7]** | **4** | PASS |

Disclosure arm — the **same engine, same seed, no premise acceptance** (this is the construct
the exam's own power calculation modelled, since its true engine emits uniformly-drawn
120-month stretches of the panel):

| bar | sealed band | measured | verdict |
|---|---|---|---|
| T1 | [1.7752827491108736, 3.3473622102535145] | **1.763633** | FAIL — **short of the lower edge by 0.0117** |
| O1 | ≥ 0.5180669104991394 | **0.514911** | FAIL — **short by 0.0032** |
| D1 | [0, 5] | 2 | PASS |
| D2 | [1, 7] | 3 | PASS |
| D3 | [2, 8] | 3 | PASS |
| D4 | [1, 7] | 3 | PASS |

Both bars miss by less than a percent of their own scale in the unconditional arm and by a
wide margin under the premise. **Neither reading is a pass, and neither is being reported as
one.** The premise costs roughly 0.53 of T1 lift and 0.014 of clockwise fraction, because it
selects for hot decades: season occupancy in the accepted batch is recession 20.5%,
stagflation 23.2%, recovery 28.0%, expansion 28.3%, against history's 13.6% / 13.9% / 47.2% /
25.3%.

### The four bars that are NOT measured here

**A1, A2, R1 and R2 need the flesh and are week 4.** A1 and A2 are measured on asset returns
(commodities, bonds, equities) and R1/R2 on a compiled ensemble and the panel source; a
no-flesh spine has none of those. They are not measured, not estimated, and not guessed at.
The judge-facing records carry `NaN` in all three return series and only the six pre-sampler
judges were called.

---

## 7. The frontier: transmission against ordering

The task's instruction was explicit — if the joint fit cannot reach the transmission band and
the dwell bands at once, do not tune past it; map the frontier. It was mapped by scaling
**only** `cov_expanding[curve_slope]`, re-simulating from the same seed, and re-judging.
Nothing else moves; nothing is re-fitted. `×0.0` is the null engine with no policy-to-downturn
channel at all, which the exam says must fail T1 — and does, at a lift below 1.0, which is
also an anti-test of this sweep.

**Unconditional arm** (the construct the power calculation modelled):

| multiplier | coefficient | T1 lift | O1 clockwise | D1 | D2 | D3 | D4 | all six |
|---|---|---|---|---|---|---|---|---|
| ×0.0 | 0.0000 | 0.9228 FAIL | **0.5204 PASS** | 2 | 3 | 3 | 3 | no |
| ×0.5 | −0.7444 | 1.3849 FAIL | **0.5187 PASS** | 2 | 3 | 3 | 4 | no |
| ×1.0 (the fit) | −1.4888 | 1.7636 FAIL | 0.5149 FAIL | 2 | 3 | 3 | 3 | no |
| ×1.5 | −2.2332 | **1.8588 PASS** | 0.5116 FAIL | 2 | 3 | 3 | 2 | no |
| ×2.0 | −2.9776 | **1.8780 PASS** | 0.4868 FAIL | 2 | 3 | 3 | 2 | no |
| ×3.0 | −4.4664 | **1.8244 PASS** | 0.4883 FAIL | 2 | 3 | 3 | 2 | no |
| ×4.0 | −5.9552 | 1.7273 FAIL | 0.4863 FAIL | 2 | 3 | 2 | 2 | no |
| ×6.0 | −8.9328 | 1.5256 FAIL | 0.4821 FAIL | 2 | 3 | 2 | 1 | no |

**Premise-accepted arm:**

| multiplier | T1 lift | O1 clockwise | D1 | D2 | D3 | D4 | all six |
|---|---|---|---|---|---|---|---|
| ×0.0 | 1.1239 FAIL | 0.5047 FAIL | 3 | 2 | 3 | 3 | no |
| ×0.5 | 1.1884 FAIL | 0.5084 FAIL | 3 | 2 | 4 | 4 | no |
| ×1.0 | 1.2302 FAIL | 0.5007 FAIL | 2 | 3 | 3 | 4 | no |
| ×1.5 | 1.2958 FAIL | 0.4973 FAIL | 3 | 3 | 3 | 3 | no |
| ×2.0 | 1.2743 FAIL | 0.4883 FAIL | 2 | 3 | 3 | 2 | no |
| ×3.0 | 1.2885 FAIL | 0.4906 FAIL | 2 | 3 | 3 | 2 | no |
| ×4.0 | 1.3060 FAIL | 0.4885 FAIL | 3 | 3 | 3 | 2 | no |
| ×6.0 | 1.1903 FAIL | 0.4851 FAIL | 2 | 3 | 2 | 1 | no |

**Three things this table settles.**

1. **The persistence bars are not the constraint.** D1–D4 pass in **all sixteen rows**, both
   arms, every multiplier. The dwell medians move by at most one month across a twelve-fold
   change in transmission strength. Whatever week 2 failed at, it was not the seasons' length.
   *(The exam's own reading note applies and is repeated here: a D verdict that misses by one
   quarter would be inside the anchor's sampling noise. These do not miss.)*
2. **The frontier is transmission against ORDERING, not transmission against persistence.**
   O1 falls monotonically as the transmission coefficient grows — 0.5204 → 0.4821 in the
   unconditional arm — and it passes only where transmission is switched off or halved, which
   is exactly where T1 fails hardest. T1 passes only at ×1.5 to ×3.0, where O1 has already
   fallen below its bar. **There is no multiplier at which both pass.**
3. **T1 saturates and then reverses.** It peaks at 1.878 around ×2 and falls back to 1.526 by
   ×6. Turning the channel up past a point stops helping, because a stronger coefficient
   raises the *unconditional* onset rate — the ratio's denominator — as fast as the
   conditional one.

---

## 8. Why: the missing feedback, measured

The decomposition below is the diagnosis, and it was measured, not inferred. It splits T1's
statistic by the growth axis of the conditioning month, on both sides.

| | months | tight months | tight share | P(onset within 12m \| tight) | P(onset within 12m) | lift |
|---|---|---|---|---|---|---|
| **history, all** | 789 | 149 | 0.189 | 0.5772 | 0.2433 | **2.3719** |
| history, expanding only | 581 | 114 | 0.196 | 0.6842 | 0.2874 | 2.3804 |
| history, contracting only | 208 | 35 | 0.168 | 0.2286 | 0.1202 | 1.9017 |
| **generated, all** | 4800 | 1315 | 0.274 | 0.3947 | 0.3208 | **1.2302** |
| generated, expanding only | 2560 | 536 | 0.209 | 0.5224 | 0.3605 | 1.4489 |
| generated, contracting only | 2240 | 779 | 0.348 | 0.3068 | 0.2754 | 1.1138 |

And the line that carries the finding:

| | share of tight months that are expanding | share of all months that are expanding |
|---|---|---|
| **history** | **0.7651** | 0.7364 |
| **generated** | **0.4015** | 0.5339 |

**In history the inverted curve sits where the turn has not happened yet** — 76.5% of inverted
months are expansions, slightly *more* than the 73.6% base rate. **In the generated worlds it
sits inside the downturn** — only 40.2% of inverted months are expanding, against a 53.4% base
rate. The curve is anti-concentrated exactly where T1 needs it concentrated.

The mechanism is visible in the fitted parameters themselves, and it is not a coding error:

- The engine has causation running **curve → season** (`cov_expanding[curve_slope] = −1.4888`)
  but **no feedback running season → curve.** The curve is L1's policy-deviation state plus a
  fitted AR(1) residual; nothing in a contraction makes it steepen.
- Worse, `cov_contracting[curve_slope] = +1.1904` — correctly fitted, since a steepening curve
  ends real recessions — means that in a generated world a contraction *persists until the
  curve happens to steepen on its own*. So inverted months pile up **inside** contractions,
  which is precisely the wrong place for T1's numerator.

In a real economy the curve steepens *because* the downturn arrives and policy is cut. That is
a **model-implied conditional mean** — stage 2 of D-SP-6, explicitly and deliberately **not
funded**. The frontier this campaign has hit is the boundary of stage 1's funded scope, not a
failure of estimation.

Two secondary contributors, both measured and both smaller:

- **The generated engine churns.** 439 growth-axis flips in 6,000 months (7.3% monthly) against
  history's 35 in 792 (4.4%), giving an unconditional 12-month onset rate of 0.32 against
  history's 0.24. A high baseline compresses any lift.
- **L1's inflation is over-dispersed for a decade.** `pi_gap`'s simulated standard deviation is
  **1.604×** history's, so the hot dial crosses its line more often than history's does and
  hot seasons are over-represented. L1 was reused as-is, per the brief, and this is a fact
  about the pinned artifact rather than about the week-2 fit.

---

## 9. Status, and what was and was not done

**Status: FRONTIER.** Week 3 (sampler integration) is **not** unblocked.

The four persistence bars land in band at every point on the frontier. The transmission bar
and the ordering bar cannot be satisfied together at any transmission strength, and the reason
is a named, measured structural gap — no season → curve feedback — that lies outside stage
1's funded scope.

**What was deliberately not done.** No parameter was tuned to move a bar. The one scaled
coefficient exists only inside the frontier sweep and is reported as a counterfactual, never
as a fitted value; `spine-v2-fitted-params.json` carries the maximum-likelihood estimates and
nothing else. No sealed file was edited. No file in `src/` or `schemas/` was edited. A1, A2,
R1 and R2 were not measured and were not estimated.

**What moved after a result was seen, and why.** Two specification choices were made after a
first run showed a T1 miss, and both are recorded here rather than presented as if they had
been there all along:

| change | first-run value | reason it was changed | reason it is not goalpost-moving |
|---|---|---|---|
| the curve enters at a **9-month lag** rather than contemporaneously | T1 1.2243 (premise) / — | the exam defines T1 as a 12-month-ahead relationship; a contemporaneous covariate cannot represent one | the lag was picked by **likelihood** on a pre-stated grid, and the profile is published; T1 barely moved (1.2243 → 1.2302) |
| a contracting spell's label splits `REC`/`STAG` at history's own rate | whole stagflation season → `STAG` | measured against the panel: only 31 of 95 contracting months at or above 4.0 pp are `STAG`, so the naive map put 111 of history's contracting months outside T1's numerator when history puts 31 there | the rate was read off history's labels, not chosen to move T1 |

Neither change rescued T1, which is itself evidence that neither was chosen to.

**Reproducibility.** `uv run python scripts/spine_v2_fit.py` regenerates
`spine-v2-fitted-params.json` byte for byte: the fit is deterministic (IRLS, no random start),
every simulation seed is a literal, and every reported float is rounded to twelve places on
output so BLAS reassociation cannot move a byte.

---

## 10. Stop-questions for the owner

1. **Which arm is the campaign's construct — premise-accepted or unconditional?** The exam's
   power calculation modelled a true engine emitting uniform 120-month panel stretches, i.e.
   the unconditional arm, but §8.1 fixes `n_seeds` at "50 decades **per premise**". The two
   arms disagree by 0.53 of T1 lift. This is a reading of the sealed document, not a change to
   it, and it should be settled before week 3 rather than after a verdict.
2. **Is stage-2 scope (a model-implied curve that responds to the cycle) worth opening?** §8
   identifies it as the specific missing piece and D-SP-6 explicitly excludes it. If the answer
   is no, T1 and O1 are not jointly reachable by this engine and the campaign should stop here
   as designed.
3. **The label-stability escalation fired.** The transmission coefficient ranges −0.99 to −2.02
   across the arms. The escalation was executed and both are reported, per the agreed path —
   but the owner may want to record whether a coefficient pinned only to a factor of two is
   acceptable to carry into week 3 at all, if week 3 happens.
