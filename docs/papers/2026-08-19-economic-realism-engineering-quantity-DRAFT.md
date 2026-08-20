> **DRAFT — pending owner edits.** Not reviewed, not released, not citable outside this repository.
> **Date:** 2026-08-19.
> The academic write-up: economic realism stated as a sealed, falsifiable exam over generated macroeconomic decades, and the four campaigns judged against it. Plain-English companion: `docs/papers/2026-08-19-twenty-decades-plain-DRAFT.md`. Player-facing companion: `docs/papers/2026-08-19-decade-you-live-through-users-guide-DRAFT.md`. Successor in framing to `docs/P1-specified-world-models-preprint.md` (SUPERSEDED).

---

# Economic Realism as an Engineering Quantity: A Sealed Exam for Generated Macroeconomic Decades

**Working paper draft — Terrarium / Alternate Histories Platform.** Draft of 2026-08-19.
Not investment advice.

Every number in this paper is quoted from a committed record in the project repository and
is cited to it. Nothing is estimated for the paper; where a quantity has not been measured,
the paper says so rather than supplying a figure.

### Sources

| tag | document |
|---|---|
| **METHOD** | `docs/current/METHOD.md` |
| **THESIS** | `docs/state-of-the-thesis.md` |
| **COMPILER** | `docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md` |
| **EXAM** | `2026-08-17-spine-v2-exam.md` (sealed) |
| **ANTITEST-1/2** | `spine-v2-antitest-results.md`; `stage2-antitest-results.md` |
| **V2R** | `2026-08-17-spine-v2-results.md` (§8 = post-review corrections) |
| **DESIGN-2** | `2026-08-17-stage2-coupled-system-design.md` |
| **DELTA** | `2026-08-18-stage2-exam-delta.md` (sealed) |
| **FIT** | `2026-08-18-stage2-fit-report.md` |
| **S2R** | `2026-08-18-stage2-results.md` (§7 = post-review corrections) |
| **REACH** | `2026-08-18-stage2-reach-results.md` |
| **RULERS** | `2026-08-18-stage2-rulers-results.md` |
| **SP02** | `2026-08-16-spine02-results.md` |
| **ER14** | `2026-08-18-er14-close-out-design.md`; `2026-08-18-er14-battery-disclosure.md`; `docs/current/private-markets-and-inflation.md` |
| **REGISTER** | `governance/decision-register.md` (D-SP-6…11, D-ER14-1/2, SM-RULING-A) |
| **P1-PRE / METHODOLOGY** | the project's two superseded framing documents |

---

## Abstract

Allocators are trained by one draw of history. The sample of macroeconomic decades an
institution can learn from is not merely small; it is a single realised path, and the
decisions that matter most — how much illiquidity to hold, how much inflation defence to
carry, how large a commitment programme to run — are taken against that one path and then
lived with for ten years. This paper describes a system that manufactures alternative
decades for allocation stress-testing, and argues that the *measurement* apparatus around it
is at least as much of the contribution as the generator.

The system has three layers. A slow **climate** layer is a five-state linear-Gaussian macro
model — trend inflation, the neutral real rate, trend growth, an equity valuation state, a
credit gap — with the latent path integrated out exactly by a Kalman filter and ~35
structural parameters sampled by Hamiltonian Monte Carlo. A monthly **clock** layer carries a
two-state growth chain with a fitted transition hazard, an inflation gap, a policy deviation
and a yield-curve equation, coupled inside one likelihood, with a nine-month lead from the
curve into the growth hazard closing the loop with a genuine lag. A **flesh** layer never
synthesises a market month: it selects verbatim months of real history to match the state the
first two layers are in. The claim is deliberately narrow — **real months, invented sequence,
declared severity** — and it is a claim about *prescription*, not prediction, in the register
in which a supervisory severely-adverse scenario is not a forecast (METHOD §2).

The measurement apparatus is the second and more transferable claim. Twelve pass/fail bars —
causal transmission, seasonal ordering, four persistence bars, a phase bar, a
curve-endogeneity bar, two allocation bars and two no-regression bars — were written down
with their historical anchors, sampling intervals, power calculations and justifications
*before the engine they judge existed*, then hashed together with the code that judges them.
Each new judge had to survive an anti-test proving its own pass rate rises in the effect it
claims to measure — an obligation adopted because a prior round shipped a clean FAIL from a
judge whose pass rate *decreased* monotonically in the modelled effect, so a model with no
reaction function scored best and the bar was unreachable by any model including a perfect
one (SP02). Every verdict passed through independent verdict-integrity reproduction before
reaching the owner; those reviews reproduced the artifacts byte-identically and returned
interpretive findings that corrected readings without changing a single sealed value.

The engine passes nine of the twelve bars. It also produces negative results the discipline
made unavoidable: the coupling the campaign was funded to build is significant on the panel
(t = +5.95) and **inert inside a decade** — switching it off moves the headline ordering bar
by −0.0012 and flips no verdict; the bar written to test that coupling passes through the
**reverse** channel and no sealed bar can tell the difference; the yield curve fails from
*above*, too determined by the economy; the compiler's story conditioning originally reached
**8.2%** of a decade's months, so world narrative and world markets agreed 1.4 percentage
points better than chance; the inflation-hedge bar, re-measured on 25,700 decades instead of
50, proved to have been read **47 standard errors** wrong, the true margin *negative* and
attributable to flight-to-quality in the severity pool the compiler draws from; and the seams
between spliced blocks are findable by a trivial jump detector with **45–49 points** of
advantage over guessing.

The thesis is that economic realism in a generated decade is not a matter of taste but an
**engineering quantity**: definable as statistics with historical anchors, measurable under a
pre-registration seal, and improvable against measured frontiers. The discipline that
measures it is presented as a contribution of equal standing.

---

## 1. Motivation

### 1.1 One sample, ten-year decisions

An institutional allocator's education is a sample of size one. The usable monthly panel here
runs **1953-04 to 2020-12 — 813 months**, of which 789 carry the full conditioning a causal
test requires. Inside it there are **seventeen recession-or-crisis onsets** and **six crisis
events** (1970-01, 1970-04, 1974-03, 2001-06, 2008-09, 2020-03) (EXAM §2). Sixty-eight years
of the world's most heavily documented economy yields seventeen of the events that matter
most.

The project measured the consequences rather than asserting them. The 95% block-bootstrap
interval on the crisis-only transmission statistic is **[0.705, 5.045]** — six events cannot
rule out that an inverted yield curve tells you *nothing whatsoever* about crises, so a bar
built on it would be nearly unfailable and the exam declines to build one (EXAM §2). The same
holds for season durations. Bootstrapping over *spells* — the independent units — the
recession median of 3 months carries a 95% interval of **[1.0, 12.5] months**; stagflation's
4 months, **[1.0, 10.5]**; recovery's 9 months, **[5.0, 16.0]**; expansion's 6 months,
**[3.0, 12.0]** (EXAM §3, 10,000 draws). The medians a practitioner would quote without
hesitation are soft by a factor of two to three.

That is the counterfactual-decade problem in arithmetic: not "history might have gone
otherwise" as a remark, but *the estimates describing how a decade behaves are so wide that an
institution tuned to the point estimates is tuned to noise.*

### 1.2 Allocation, not timing

The purpose statement governing what is tested is in the sealed exam's first section: **the
system tests robust asset allocation, not lever timing** — a player should be rewarded for
holding a portfolio that survives a range of futures, not for guessing when a central bank
moves (EXAM §1). Two structural consequences follow.

Both allocation bars are measured on **asset returns**, never on a portfolio's outcome. An
asset-level bar cannot be tuned toward a portfolio result without the tuning being visible as
a change to a published historical anchor — the mechanical form of the project's Rule 1,
*severity is never tuned to portfolio outcomes* (EXAM §6.3). And the persistence bars carry a
**±1 quarter** tolerance justified as a product fact rather than a statistical one: a quarter
is the smallest play unit, so a season right to within one quarter is right to within the
finest distinction the product can express, and a tighter bar would grade a difference no
allocator can act on (EXAM §3).

### 1.3 Why coherence is the binding requirement

A block bootstrap of real months already gives realistic marginal behaviour. What it does not
give is a *story* — and for allocation training the story is the point. The conditioned
compiler's design names the failure it was built to kill: *"a decade that is real at month
scale and incoherent at story scale"* (COMPILER, quoted in S2R §2.1). Section 6.4 reports the
measurement showing that failure was not dead but quantified, and the two engine changes that
moved it.

Coherence has a price. Every month is a verbatim historical month, so a decade's severity
ceiling is history's own worst months, and the worst rolling twelve months in the panel is
**−42.6%**. Both that ceiling and the thin material at the extreme come from drawing on one
country's record; the remedy, the international record, is licence-blocked (METHOD §6).

### 1.4 What is not claimed

The project made a documented turn on 2026-08-14 and this paper adopts it: **the generator
stopped being asked to predict and started being asked to prescribe** (METHOD §2). A world is
a *declared* stress scenario built to answer *could this institution survive this?* rather
than *how likely is this?*

The turn was forced by arithmetic, and the arithmetic is the record's clearest case of a label
mistaken for a quantity. Of 813 panel months, **38 carry the "crisis" label, averaging −1.79%
on equities**. A world declaring four quarters of crisis drew roughly 12 × −1.79% ≈ **−19.5%**
— and a 20% drawdown exhausts nobody's liquidity, which is why forced secondary sales fired in
**0 of 20 seeds**. *"Crisis" is a classification containing both October 2008 and months that
merely satisfied the rule.* Ranking by severity instead reaches the required depth and draws
on **more** real material — 82 to 163 eligible months rather than 38 (METHOD §2).

Three further exclusions. **There is no reaction-function bar**: the exam does not test
whether policy responds to inflation at all, and the omission was put to the owner before the
seal and confirmed as intended (EXAM §12.2). **There is no 2021–22 anchor**: the episode a
present-day allocator most wants lies inside the platform's sealed holdout, and the anchors
script declares it and emits `available: false`, `months_in_panel: 0`; opening a spent holdout
to set a bar would be fitting to data that was held back (EXAM §7). And **the holdout is
gone** — declined at an earlier gate on purpose, then spent — which raises rather than lowers
the bar on not fitting retrospectively (METHOD §6).

The platform's standing caveat is carried into every section below: *nothing built on this
generator line is a convincing model of history, and nothing built on the platform is
decision-ready* (METHOD §6; DELTA §7).

---

## 2. The architecture, in three layers

Three strictly-ordered, independently testable layers (COMPILER §3), described in the order
state flows.

### 2.1 Layer S — the slow climate

A five-state continuous-time linear-Gaussian macro model, discretised monthly at `dt = 1/12`,
with state vector

> `s_t = (π*_t, r*_t, g_t, v_t, L_t)`

reading: **π\*** trend inflation, **r\*** the neutral real rate, **g** trend growth, **v** a
log equity valuation state (CAPE-like, demeaned on the training span), **L** a credit/leverage
gap. Two further states ride inside the filter without being exported: a slow stochastic
**credit trend**, so that a century and a half of secular credit deepening is not forced into
the gap; and a **policy deviation** `u`, an Ornstein–Uhlenbeck deviation from the policy rule,
present because actual policy deviates persistently — the zero-lower-bound decade being the
obvious case — and because without it the filter would push those deviations into `r*`.

Because the system is linear and Gaussian throughout, the latent path is marginalised
**exactly** by a Kalman filter and the sampler runs over the ~35 structural parameters only;
joint draws of parameters and states come from a forward-filtering backward-sampling pass per
retained parameter draw. The panel is mixed-frequency, fusing annual macro-history (1870–2020)
with the monthly panel through the project's single sanctioned reference surface.

Two features matter downstream. The policy rule

> `i_t = r*_t + π*_t + φ_π·(π_t − π*_t) + φ_c·c_t + u_t + ε`

is an **observation** equation and never a state — which is exactly what lets a later layer
substitute its own cycle input `c_t` at simulation time without refitting. And `c_t ∈ [−1, +1]`
is an exogenous contract, fitted on history as `c_t = 1 − 2×USREC`: the same discrete signal a
later layer's own growth axis replaces.

### 2.2 Layer H — the correction hazard

A monthly hazard `h_m = rate[quadrant_m]`: the historical frequency of correction onsets in
whichever of four macro quadrants the world occupies, calibrated on the panel and nothing else.
Over a single categorical covariate the saturated fit *is* the frequency table, so there is
nothing to tune. When the draw fires, the compiler enters a crisis segment whose depth
percentile and dwell come from a small **pre-registered state-severity table** rather than a
formula buried in code — the requirement that a supply shock against above-trend inflation be
worse than one against benign inflation, implemented as three rows and sealed with the code
that applies them (COMPILER §3.2, §3.4).

The epistemic position is stated plainly and is the honest answer to the objection that
corrections are unpredictable: *"the machine does not predict them. It reproduces the
statistics of their preconditions and rolls dice."* Two decades from the same premise differ in
when — and whether — a second correction lands, which stops a repeat player learning a schedule
(COMPILER §3.2).

### 2.3 Layer F — the flesh, selected and never synthesised

The top layer emits asset returns by **selection only**. Each block must come from source
months whose own macro quadrant matches the spine's current quadrant, crossed with the severity
stratum currently demanded; adjacent blocks must agree on inflation-era bucket; and the jump in
trailing 12-month CPI inflation across a join is bounded by a threshold sealed from the panel's
own adjacent-month distribution (COMPILER §3.3).

The governing rule, carried unchanged through every campaign: **state chooses *which* real
months are drawn and never edits, scales or synthesises a month** (DESIGN-2 §2.4). The
consequences are a hard severity ceiling and an inherited dependence structure — the tape runs
forward through real history unfiltered from wherever it starts, so month-to-month
autocorrelation is *inherited rather than modelled* (METHOD §3).

The design's promise for this layer is explicit, and §6.4 reports how much of it was kept:

> *"the owner's returns/volatility/correlation point lands for free: months cast from real
> stagflation carry stagflation's true joint behaviour — including the equity–bond correlation
> flip — because they ARE stagflation months."* (COMPILER §3.3)

### 2.4 The coupled system

The two campaigns rebuilt the storyline layer's monthly dynamics into one system fitted as a
single likelihood (FIT §1):

```
growth chain    season_{t+1} ~ Bernoulli( h(season_t, dwell_t, z_t) )
inflation gap   x_{t+1} = k0 + a·x_t + λ_x·(c_{t−m} − c̄) + σ_x·e_t
inflation       π_t     = π*_t + x_t
policy dev      u_{t+1} = u0 + φ_u·u_t + λ_u·x_t + λ_c·c_t + σ_u·e_t
policy rate     i_t     = r*_t + π*_t + φ_π·x_t + φ_c·c_t
curve slope     slope_t = c0 + c_i·(i_t − ī) + c_x·(x_t − x̄)
                          + season_term(g_t, age_t) + e_t,   e ~ AR(1)
```

`z_t` carries `slope_{t−9}` — the curve at a nine-month lead — so the loop closes with a
genuine lag and there is no simultaneity to solve.

Every symbol, once. **`season`** is which of four macro seasons the month is in; **`dwell`**
how many months it has already run. **`x`** is the *inflation gap*: how far actual inflation
sits above or below its slow trend. **`c`** is the *cycle input*, near +1 expanding and near 0
or −1 contracting. **`u`** is the *policy deviation*: how far the policy rate sits from what the
rule says. **`slope`** is the yield curve, ten-year minus two-year. **`a`** is the inflation
gap's persistence; **`λ_x`** its loading on the lagged cycle — the growth → inflation arrow;
**`λ_u`**, **`λ_c`** the policy deviation's loadings on inflation and cycle; **`c_i`**, **`c_x`**
the curve's loadings on the model-implied policy rate and the inflation gap; **`ρ`** the curve
residual's autocorrelation.

The loop in one sentence: *growth axis → cycle input → inflation gap → policy rate → curve →
(nine months later) growth hazard → growth axis* (DESIGN-2 §2.2). As plain statements, the four
new arrows are: inflation follows growth with a lag; policy stops being noise and leans on both
the inflation gap and the cycle; the curve reads the policy rate the *model* implies rather than
the rule's leftovers; and the growth chain reads the curve at a lead a likelihood chose. Nothing
is hand-set.

**The seasons.** Every month is placed in one of four boxes by two yes/no questions — is the
economy expanding, and is inflation hot (above the panel's own line, **3.351323828920571 pp**)?

| | inflation cool | inflation hot |
|---|---|---|
| **expanding** | recovery | expansion |
| **contracting** | recession | stagflation |

The **clockwise** order is recovery → expansion → stagflation → recession → recovery, and it
*alternates axes*: two of its four steps change the growth answer and two change the inflation
answer. This is not decoration — it is why the ordering statistic turns out to be a test of the
**phase** between two dials rather than of either dial alone, the finding that structured the
whole second half of the campaign (EXAM §2; V2R §2.2).

### 2.5 What the estimation buys, and one honest limit

The joint log-likelihood is `L_hazard + L_inflation + L_policy + L_curve`, maximised as one
object; the fitted value is **+2225.5160** (FIT §1.2).

The limit is stated up front rather than left for a reader to derive. On the historical panel
almost everything is *observed* — the season path from the classifier's labels, the slope from
the panel's own 10y−2y, actual inflation from CPI, the policy rate from the published series —
so the cross-block information is **exactly zero, not merely small**, and the joint maximum is
attained blockwise. *"That is a property of the data and not an achievement of the design"*
(FIT §1.2).

What the joint fit does buy is narrower and real: every "no coupling" restriction nests exactly,
so each is a likelihood-ratio test rather than an argument; both halves of the loop come from
one likelihood on one panel; and the coupling is a **generation-time** property, active where
the season is *not* observed.

The lag `m` was chosen by a sealed rule — maximum likelihood on a declared 25-lag grid (0 to 24
months), one parameter at every lag, the same months at every lag, the whole profile published
beside whatever it picks (DELTA SQ9). It selected **10 months**, likelihood ratio against no
coupling **34.80 on 1 df**. And the profile is a **ridge, not a peak**: lag 10 beats lag 9 by
**0.18 of log-likelihood**, only 57% of bootstrap draws select within three months of ten, and a
sensitivity arm selects **2** (FIT §2; DELTA L8). The rule was sealed precisely because the
value could not be.

---

## 3. The measurement discipline as a first-class contribution

Generative modelling papers routinely report a battery of statistics and declare the agreement
satisfactory. The claim here is that the *procedure* turning a battery into evidence is the harder
problem, and that this project's answer is transferable independently of the engine it was built
for. Six components; each adopted because something went wrong without it, each mechanically
enforced rather than conventional.

### 3.1 Seal the rules before running the race

Thresholds *and the code that judges them* are hashed together before any fitting run. The
twelve-bar seal is `stage2-prereg.json`, `sealed_at_utc` **2026-08-18T01:39:46-07:00**, against a
named HEAD commit, hashing **eleven paths**: the exam document, the anchors artifact, the anti-test
results, the prior seal and anchors loaded whole, and six scripts (S2R §1). Its predecessor was
sealed **2026-08-17T14:42:40-07:00**, *before any engine work and before any generated ensemble
existed* (V2R §1). The exam states the property — *"a threshold chosen after seeing results is not
a test, it is a description"* (EXAM §1) — and the stage-2 delta states it in the negative: *"a bar
written after a coupling is fitted is a description, not a test."*

**A carried bar is byte-frozen.** The ten bars carried forward were *not re-derived, not
re-anchored, not re-implemented*: the new judge imports the old judges by name and hands them the
old seal loaded whole. *"A change in one of these ten verdicts is therefore attributable to the
engine and to nothing else, which is the only reason a carried bar is worth having"* (DELTA §1).

**Amendments go through a machine-checked log, never by editing the file.** The v2 campaign took
exactly one construct amendment; it changed **no threshold** and edited **no hashed file**, and
resolved a real ambiguity — the power calculation modelled a true engine as drawing
*unconditionally* while the same section fixed the batch size at "50 decades **per premise**", and
the two arms disagreed by 0.53 of transmission lift.

What makes the machinery credible is what the entry recorded about itself. The amended arm already
read **more favourably on both bars at the moment of amending** — 1.763633 vs 1.230161, and
0.514911 vs 0.500707 — and the entry records those four numbers in its own
`readings_known_at_amendment_time` payload with `amended_arm_reads_more_favourably: true`. Both
arms failed both bars at that moment, so nothing flipped FAIL→PASS at the act of amending; the
readings moved toward their bands, and that is on the record rather than in a footnote. The
alternative reading is published in full: reject the amendment and the campaign closes at FRONTIER
on both causal bars, the final engine reading 1.2231 FAIL and 0.4913 FAIL (V2R §1, §4.2).

The log is append-only in a way that costs something. When a review found a factual error *inside*
a sealed amendment's rationale — it cited the superseded pre-fix anchor (68 transitions, 41
clockwise) as provenance for a floor actually cut from 72 and 43 — the entry was **not edited**; a
follow-up entry records the correction through the same machinery. *"The log is the record, and
editing an entry would erase the thing the log exists to keep"* (V2R §8.6). The stage-2 amendment
block is **empty** (S2R §1).

**Where a value cannot be pinned, the seal governs the rule.** The coupling lag is sealed as a
selection rule because the panel does not pin the value (§2.5). The seam ruler's band is sealed as
a *construction* — resample *n* values from history's own adjacent-jump distribution in moving
blocks of 24 months, take the quantile, repeat 2,000 times, keep the central 95% — because the band
depends on the sample size the world presents, *"so a fixed threshold would be a band cut at one
arbitrary n"* (RULERS §1.5).

### 3.2 Judges that must pass anti-tests of their own

**The episode.** A prior round sealed a reaction-function judge and got a clean FAIL on all five
seeds. The verdict-integrity review found the judge *carried zero information about the model*: it
correlated **differenced** policy against the **undifferenced** surprise level, so the covariance
it measured was `cov = −φ·σ²` — *negative* in the response strength φ. A parameter sweep confirmed
the pass fraction **decreased monotonically in φ**: a model with no reaction function at all scored
the best achievable value, **~0.47**, itself short of the 0.90 bar. *The bar was unreachable by any
model, including a perfect one.* An independent test of the construct the review considered correct
— the residualised policy *level* against the surprise — found the reaction function live and
correctly signed, recovering φ_π in **[0.417, 0.852]**, positive on all 20 decades. The reading
issued was the opposite of the one the raw table supported: *"do not read its FAIL as a defect
finding"* (SP02).

The standing obligation: **before a judge is sealed, sweep the model property it claims to measure
and confirm its pass rate increases in it. A judge whose pass rate does not increase in the effect
it claims to measure does not get sealed** (EXAM §6.1). Byte-frozen carried bars are deliberately
*not* re-swept, because changing them is what a carried bar exists to prevent.

Two subtleties, because a naive implementation produces false negatives. **Two-sided bars are swept
on closeness, not on the raw effect** — a raw sweep of a two-sided band would correctly fall at the
top and prove nothing, so the persistence bars generate half the batches a fixed distance above the
anchor and half below at each grid point, and the transmission bar re-orders a two-sided grid by
how far the *realised* lift sits from history's, normalised by the band's own half-width on that
side (ANTITEST-1). And **saturation must be reported**, *"because both prior campaigns found bars
that rise and then fall in their own mechanism's strength"*: the phase sweep saturates at coupling
0.5, but the mean departure keeps rising past it (0.006 → 0.043 → 0.086 → 0.132 → 0.204 → 0.254 →
0.291), so the bar is not on a plateau it could slide off (ANTITEST-2).

All nine sweeps of the first exam were monotone non-decreasing, at 24 batches per grid point and 50
decades per batch, byte-reproducible: the transmission sweep runs 0.00 → 0.12 → 0.46 → 0.75 → 0.96
→ 1.00 as the modelled causal probability goes 0 → 1; the correlation sweep runs 0.00 → 0.00 →
0.00 → 0.21 → 0.96 → 1.00 → 1.00 as the imposed high-inflation correlation rises from −0.1 to +0.6
(ANTITEST-1).

**Controls are distinct from sweeps.** A control is required to behave in one specified way rather
than to be monotone, and the seal script refuses to write if any control is false (ANTITEST-2):

| control | what it demands | result |
|---|---|---|
| `P1_null_engine` | at zero coupling the judge is centred on the null | mean departure **−0.00008 / −0.00011** against thresholds 0.0403 / 0.0314 — 0.2% and 0.3% of threshold |
| `P1_scramble` | phase-scramble a passing batch; the statistic must collapse | departure **0.2904 → −0.0010**, **0.2849 → −0.0007**; pass rate **1.000 → 0.123** over 300 batches |
| `P1_retro` | every engine already on the record must fail | all five engine-arms fail on both move types |
| `P2_noise_shrink` | an engine shrinking its noise to buy an economic share must FAIL, **from above** | at residual sd 0.500 the share is 0.7227; **12 of 12** fail above the band |
| `P2_retro` | the two recorded engines (0.0%, 2.2%) must fail **below** | all four arms fail below, each reproducing the anchors' share to 1e−9 |

Two construction defects were found *by* these controls and recorded rather than quietly fixed,
because each moved the answer by more than the residual being measured. The scramble control was
first written with **one shift for the whole batch** — a synthetic growth axis is quasi-periodic,
so one shift moves every decade to the same new phase and a shift near a whole number of cycles
re-aligns them — leaving a fully coupled batch at 0.054 departure and 58% pass. Rewritten with an
independent shift per decade but restricted to the sealed guard, it still left +0.019 / +0.023 and
23%, because the guard belongs to the *null* and restricting a control that must destroy alignment
to that set samples phases non-uniformly. *"Both artifacts are properties of the shift set, not of
the judge"*, and the docstring keeps the history.

The regime also establishes a bar's honest weakness. The phase bar's **size** — its false-positive
rate against an engine whose dials are independent by construction — is **9.0% over 300 batches of
fifty decades** at the sealed thresholds, against **1.3%** at the recommended construct's candidate
and **0.3%** at the strictest; the size at all eleven published candidates is in the artifact
(0.003 … 0.090). It is in the limitations register, not a footnote: *"a 9% size means a single PASS
on P1 is evidence of some phase coupling at about the conventional strength of one significance
test, not proof of it"* (DELTA L1).

And an anti-test can be right and still blind. The sweep qualifying the phase bar swept a
*synthetic* coupling in which inflation is a lagged copy of growth. It was monotone, correctly. It
**could not have caught** a pass arriving through the opposite arrow — which is what happened
(§6.2), and the campaign states this rather than discovering it later.

### 3.3 Independent verdict-integrity reproduction

**No verdict reaches the owner before an independent review re-derives each judge's formula,
characterises every FAIL, and checks that both sides of every comparison use the same definitions**
(EXAM §6.2). The precedent is a prior-round defect that counted recession-or-crisis on the model
side against crisis-only on the history side, making the FAIL an artefact of the mismatch.

The reviews certify the arithmetic and correct the prose. The v2 review re-ran both fitting scripts
read-only: both artifacts regenerated **byte-identically**; all twelve sealed hashes recomputed
**clean**; every bar reading, all 32 frontier rows, both attribution tables, the 16 hazard
coefficients, the curve block, the label-stability arms and every historical anchor matched **to the
digit** — *"No discrepancy at any digit."* Every PASS/FAIL word was **ALL CORRECT**. It returned
**twelve findings** — one material, three substantive, eight minor, all interpretive or omissive —
and named the pattern:

> *"eleven of the twelve lean the same way: they make the week-3 mechanism look better, or the
> remaining gap look smaller, than the committed artifacts support."* (V2R §8)

The rule the corrections follow is that **no verdict value and no PASS/FAIL word changes** — none
was found wrong; what is corrected is the characterisation, and where corrections and body conflict
the corrections govern. The stage-2 review reproduced all twelve bars to the digit and returned
twelve findings of the same kind; the final review reproduced every number from scratch and found
**zero numeric, verdict or arithmetic errors**.

Three corrections show the mechanism working against its own authors.

**The material one.** The ordering FAIL was diagnosed in a section whose decomposition was measured
on a *different construct from the bar*: the sealed judge censors each decade's first twelve months
(the trailing-inflation warm-up) while the decomposition scored the simulator's always-defined
internal path. The decomposition's **0.5241 clears the sealed floor of 0.5180669**, and the
construct gap of **+0.0124** is about **twice** the 0.0063 shortfall the section existed to
diagnose. The reviewer is precise about scope: *"the sealed judge is the authority, O1 FAILS at
0.511765, and I am not claiming the bar was mis-scored… What I am claiming is that the verdict's
diagnostic section is built on a different object than the bar, in the favourable direction, by more
than the margin at issue — and says nothing about it."* The asymmetry is the campaign's own named
defect applied everywhere but here: history's side loses one warm-up in 813 months (**1.5%**), the
generated side 12 in every 120 (**10%**). Consequence: the claim *"O1 is unreachable by this
engine"* was **withdrawn**, and any future seal was required to re-derive the phase anchor under
windowing-symmetric constructs before citing that shortfall (V2R §8.1).

**The substantive one.** The verdict headlined the largest of three available answers to "what is
the fitted feedback worth". The artifact's own clean counterfactual — the frontier row with the
loadings zeroed — moves the transmission bar by **−0.00036**, and **the bar passes with the entire
deliverable switched off** (1.91344 vs 1.91308). The review's judgement was *understated* rather
than overstated: *"on the arm the verdict is judged on, it is not 'most' — it is all of it, and the
artifact records the number that says so"* (V2R §8.2).

**The one catching a self-flattering correction.** A stage-2 correction found a claim about the
coupling's age signature had named the wrong bucket — and the correction *favoured the coupling*.
It is recorded anyway, noting that what survives is the weaker and still-true claim, and that the
inertness finding *does not rest on that diagnostic* (S2R §3.1).

### 3.4 Power calculations, and bars fixed as bars

Before sealing, every bar's power was computed against a modelled "true engine" emitting
uniformly-drawn contiguous 120-month stretches of the panel — history's point estimates by
construction, and history's own month-to-month dependence, which an i.i.d. binomial calculation
would discard — judged on the pooled statistic over *n* such decades exactly as the judge would
judge *n* generated ones, 2,000 times per grid point (EXAM §8.1).

Two bars **could not be bought with compute**, and both were fixed as bars. *The recovery-duration
bar could not be passed by a correct engine at all*: a true engine produces a pooled recovery
median of 5 months against a band of [6, 12], with power *falling* as the ensemble grew — **0.36 at
20 decades, 0.14 at 300** — because it was converging on a value the band excluded. The cause was
neither engine, tolerance nor size: **the anchor was measured panel-wide and the statistic on
120-month decades**. Measuring both sides on the decade window put the anchor at 5 months and the
true engine mid-band, and power at 50 decades became **0.987**. And *one condition of the
correlation bar demanded ~400 decades* — the only condition in the exam to do so — on 2.8 points of
headroom; it was **dropped rather than raised**, *"on the grounds that a ceiling moved after seeing
what it costs is a bar chosen for its power rather than for its meaning."* The statistic is still
computed and printed beside every verdict against the value it would have been judged at. That
bar's power went 0.689 → 1.000 (EXAM §3, §4).

At **50 decades per premise** every retained bar clears 90% power: T1, O1, D4 and A2 at 1.000; D1
0.993; D3 0.987; A1 0.936; D2 **0.921**, the weakest.

What the figures cannot establish is also stated. Both power calculations use *history itself* as
the true engine, resampling the same 813 months the thresholds are cut from, so they see sampling
noise and **not** estimation error: they are **upper bounds**, and *"a power of 1.000 says the bar
is reachable, not that it will be reached"* (DELTA L11). For the persistence bars, *"a D bar's
power calculation is now close to tautological by construction"* — the anchor is cut from the same
object the true engine emits — so a high number says the statistic is *stable*, not that the bar
discriminates.

### 3.5 Frontier discipline: the rows that were not taken

The final component is a refusal. When the fitted engine failed the curve bar, a frontier sweep
found a row — the fitted curve coefficients halved by hand — at which **all eight pre-flesh bars
pass**. It was not adopted:

> *"It is not a fit; it is the fitted curve with its coefficients halved by hand, and halving a
> coefficient because a bar is on the other side of it is the definition of tuning past a conflict.
> Three campaigns have ended at a frontier and the discipline held every time. The verdict is the
> fitted point."* (S2R §3.3; FIT §6)

The same discipline governed arms that read *better*. The declared escalation fired when a
coefficient proved threshold-unstable; the soft-label refit was run, reported, and **not adopted**
— *"every escalated arm makes the feedback stronger, not weaker… Choosing the arm that reads
better, after seeing which one reads better, is the thing frontier discipline exists to stop"*
(V2R §4.1). Restoring a curve term that would have *lowered* the generated economic share, moving
the failing bar toward its band, *"is precisely why it was not taken after the bars were read"*
(FIT §8). And when a later campaign chose a conditioning design, the selection rule was stated so
it could be checked — chosen on reach, agreement and preserved constraints, *not on any bar* — and
demonstrated non-bar-maximising by naming two rejected arms that scored better on individual bars
(REACH §2).

### 3.6 The determinism substrate

All randomness flows from one integer seed through a single counter-based generator; no global
state, no time-based defaults; every artifact regenerates byte-identically, verified rather than
asserted. Two incidents set the standard. A prior round suffered a **seed-stride collision** that
left a 20-rung ladder measuring **two** storylines; the fix is a prime stride coprime to the
platform's own, disjoint per-layer offsets, and a test drawing the first eight float64s of hundreds
of streams to confirm no two coincide (V2R §5.3). And a determinism claim *cost a defect to make
honestly*: two runs of the final measurement script differed by **exactly two keys, both elapsed
wall-clock seconds, and nothing else** — every measured number and verdict bit-identical. The clock
was removed and printed instead. *"A results file that carries a wall clock cannot make a
determinism claim; the intention was there from the start and the property was not, and only
running the check twice found that out"* (RULERS §5). A related rule governs engine changes made in
analysis scripts: the reach fix lives in a *copy* of the platform's sampler, admissible only
because it is **pinned** — one test runs both on the same synthetic inputs and demands
**bit-identical row indices** at the baseline, and its partner demands a non-baseline design does
*not* match, *"so the pin is a comparison rather than a tautology"* (REACH §1.4).

---

## 4. The twelve bars

Each bar states the real quantity anchoring it and why its tolerance is that size — the house rule
the exam was written under (EXAM §1, §10).

| tier | bar | plain question | historical anchor | the bar |
|---|---|---|---|---|
| causal | **T1** | does tightening cause downturns? | lift **2.3718540268456376** (86/149 tight-month onsets vs 192/789) | inside **[1.7752827491108736, 3.3473622102535145]** — the anchor's own 95% block-bootstrap interval |
| causal | **O1** | do the seasons turn the right way round? | clockwise fraction **0.5972222222222222** over 72 transitions, 43 clockwise; 95% CI [0.5181, 0.6765] | **≥ 0.5180669104991394** — the interval's lower edge |
| persistence | **D1** | how long a recession lasts | **2 months**, 893 decade-pooled completed spells | pooled median in **[0, 5]** months |
| persistence | **D2** | how long stagflation lasts | **4 months**, 1,268 spells | pooled median in **[1, 7]** months |
| persistence | **D3** | how long a recovery lasts | **5 months**, 1,661 spells | pooled median in **[2, 8]** months |
| persistence | **D4** | how long an expansion lasts | **4 months**, 2,123 spells | pooled median in **[1, 7]** months |
| phase | **P1** | do the two dials keep time with each other? | departures **0.138168** (growth flips) and **0.125093** (inflation crossings) from history's own within-window null | departure ≥ **0.040330202948** *and* ≥ **0.031445706759** from the batch's own null |
| curve | **P2** | is the curve made of economics? | history's strict economic share **0.558667** on 809 months | inside **[0.391706974667, 0.673370849738]** |
| allocation | **A1** | does the inflation hedge pay when inflation is high? | commodities − bonds **+4.87 pp** high vs **+1.38 pp** low, margin **+3.49 pp** | directional (high > low), high spread inside **[−5.05, +32.32] pp** |
| allocation | **A2** | do stocks and bonds fall together when inflation is high? | corr **+0.30125** high vs **−0.01823** low, difference **0.3195** (95% CI [0.1361, 0.5568]); 94.7% vs 54.2% of windows positive | corr(high) > 0; gap ≥ **0.13609378139729844**; ≥ **80%** of 3-year windows positive |
| no-regression | **R1** | severity still bites the book | prior seal (round two: PASS at medians [0.0901, 0.2821, 0.3514, 0.6643], 2/20 breaches) | monotone coverage across [15, 35, 40, 55]% private; ≥ **1/20** breach at 55% |
| no-regression | **R2** | eras don't teleport at the seams | panel p95 adjacent trailing-inflation change **0.7433911963542538 pp** | join jump ≤ **2.5 pp**; decade p95 ≤ **1.25×** panel = **0.9292 pp** |

**Definitions used above, once.** *Tight policy* is an **inverted yield curve** (10-year below
2-year), applied identically on both sides; a *downturn* is a month labelled recession or crisis, a
union used on both sides because a prior review found a judge comparing recession-or-crisis on the
model side against crisis-only on the history side; *lift* is the chance a downturn starts within
12 months over tight months divided by the same chance over all eligible months, so 1.0 means
tightness tells you nothing. The *clockwise* order is recovery → expansion → stagflation →
recession → recovery. A *spell* is an unbroken run of months in one season. The *spread* is
commodities' annualised average return minus bonds', annualised arithmetically because only the
arithmetic version is additive across assets. The *strict economic share* is the summed squares of
the curve's economic components over the summed squares of everything, with exogenous shocks in the
denominator and excluded from the numerator.

Six of the tolerances carry justifications that are the substance of the exam rather than
housekeeping.

**Why the transmission band is that wide.** The bootstrap rebuilds fake 789-month histories out of
randomly chosen *runs* of consecutive real months (mean run 24 months, 2,000 repetitions, one fixed
seed) so the clumping of downturns and of inverted months survives into the error bar. *"The width
is not a modelling choice that better estimation could tighten: it is what seventeen downturn events
in 68 years support."* It barely moves with block length ([1.769, 3.344] at 12 months; [1.856,
3.335] at 36) and excludes 1.0 comfortably, so an engine with no channel fails it. A caveat rides
with every reading: under selection-only compilation the curve is carried in by the *selected
months* while labels come from the *spine*, so the bar tests transmission and flesh-alignment
together, and the judge must print both sides' base rates (EXAM §2, §12.3).

**Why the ordering bar sits at an interval edge rather than at the anchor.** *The anchor is an
estimate*, so an engine whose true ordering exactly matched history's could land below the point
anchor and fail. *"A bar that a correct engine fails one time in two is not a test of the engine."*
What a bar can honestly demand is **consistency with history**. A stricter one-standard-error
variant (0.5394) and a looser i.i.d.-bootstrap variant (0.4861) were both published before any
result, with the note that *"now, before any result exists, is the only time that can be decided
without it being goalpost-moving."* Neither was taken. Two properties are measurements rather than
assumptions: the block interval is **narrower** than the i.i.d. one because the clockwise
indicator's lag-1 autocorrelation across transitions is **−0.377** — the clock backtracks and
returns — and it barely moves with block length (EXAM §2).

**A pre-seal correction to the classifier.** The season classifier answered "is the economy
expanding?" by asking whether the month's label was recession or crisis — and the ruleset's *own*
stagflation label is neither, **so a stagflation month had been counting as expanding**. The
robustness study caught it biting: the whole of **1975-04 → 1975-12** — industrial production down
11% year on year, unemployment up 3.7 points, a 15–25% equity drawdown, inflation near 10% — was
classified as *expansion*. The fix is one line, `contracting = REC or CRI or STAG`, and it moves
**31 months, every one from expansion to stagflation**; affected anchors were re-anchored pre-seal
with old published beside new. The clockwise fraction moves by **0.0057** and the bar by
**0.00045**, and the smallness is informative — the months that move make a clockwise step in the
same place the clock was already turning. **The two intervals are drawn from the same resampling
tape**, so the difference is the labelling, not two different sets of random numbers. The fix also
repaired a power problem: the stagflation bar reads **0.921** power under the corrected grader
against **0.692** under the incumbent (EXAM §2, §3, §11.5).

**Why the persistence tolerance is ±1 quarter, and why the anchors are decade-pooled.** The
tolerance is a *product fact*: a quarter is the smallest play unit, so a season right to within one
quarter is right to within the finest distinction the product can express — and it is explicitly
**unchanged** by the measurement of the anchors' sampling intervals, because *"a product fact is
not overturned by a sampling interval or a windowing rule."* The anchors are pooled across the
batch and measured on the decade window on **both** sides, for two separate reasons: history's own
decades average 1.3 completed recession spells, 1.6 stagflation, 2.4 recovery and 2.7 expansion, so
a per-decade median measures luck; and judging a decade-windowed statistic against a panel-wide
anchor is the same error a prior review had already found. Recovery's median falls from **9 months
panel-wide to 5 on decades**, because a 120-month window drops the spell it opens with and the one
it closes with and a long spell is likelier to touch an edge — its spell list runs 2, 2, 3, 3, 3, 4,
5, 5, 5, 6, 6, **12**, 13, 14, … so the panel-wide median of 9 is *"the midpoint of a jump nothing
observed sits in."* Completed spells only, with the panel's two censored recession spells disclosed
by name and observed minimum length (**1954-04 → 1954-11**, 8 months; **2019-04 → 2020-12**, 21
months). The pooled anchor uses overlapping windows, weighting interior months more heavily; the
disjoint-decade sensitivity gives 3 / 2 / 5 / 5 months on ten to eighteen spells — recovery and
recession agree within tolerance, **stagflation does not, and it rests on ten spells**. Both are
published (EXAM §3).

Stagflation is first-class by owner ruling, on an allocation argument: it is *"the one season where
the usual defence fails: bonds do not rescue equities, and the assets that do help are the ones
most allocators hold least. A generated world that skips lightly through stagflation is not a mildly
wrong world; it is a world missing the hardest allocation problem the product exists to teach."*

**Why the allocation line is 4%, with its sign flip published.** Three grounds stated before
grading: 4% is roughly double a modern target, so it is a genuinely-high-inflation test; it is
*conventional, not estimated* — the round number a practitioner would name, not the value maximising
the effect; and the sensitivities are published in the same document, including the one place the
answer reverses. At the 4% line the panel has **225 high-inflation and 576 low-inflation months**.

| line | high-inflation months | spread, high | spread, low | high − low |
|---|---|---|---|---|
| 3% | 368 | +2.047212191625329 pp | +2.6257132735411672 pp | **−0.58 pp — SIGN FLIPS** |
| **4% (the bar)** | 225 | +4.871958498950341 pp | +1.37867581891948 pp | **+3.49 pp** |
| 5% | 153 | +8.617096086048779 pp | +0.8825497419691102 pp | +7.73 pp |

At 3% the ordering reverses, because that line drags most of the 1983–1999 disinflation into the
"high" bucket and that was the best stretch in the record for long bonds (+10.05%/yr). *"This fact
is not robust to the threshold; it is conditional on it. That is why the threshold is part of the
bar's statement, why it is fixed at 4% before results, and why the 3% number is printed here rather
than discovered later"* (EXAM §4).

The hedge bar is directional because across five in-panel decades the statistic ran over a
**37-point range, both ends of which actually happened** (post-war calm +2.65; first oil shock
**+32.32**; great inflation +4.68; great disinflation −2.82; post-GFC calm **−5.05**); a band
tighter than the episode range would reject behaviour on the record. And the exam is candid that
containment is nearly worthless as evidence: under selection-only compilation the generated spread
is structurally bounded by history's own months, so containment is *"closer to a plumbing assertion
than to evidence about the engine."* **The directional half is the real test.** One honest exclusion
rides with it: the owner's original framing was "real assets versus nominal bonds", but **no monthly
real-asset total-return series exists in the catalog**; every such field is `null` by construction
and *never substituted*.

The correlation bar's margin was *loosened* by measurement, from a provisional 0.15 obtained by
halving history's gap: *"a reasonable guess at the sampling noise that the measurement shows was a
little optimistic. The correction goes the honest way and is made here, before any result exists."*
It is a little over **twice** the threshold sensitivity of the high-inflation level itself, which
moves only 0.07 across the whole 3%→5% range, so the bar cannot be passed or failed by the choice
of line; and the 80% floor sits **5.8 points below the lowest share history shows at any published
line** (85.8%, at 3%). The dropped low-inflation ceiling costs the bar its *"and the flip is
specific to high inflation"* half: *"an engine whose windows are positive nearly all the time, in
every inflation state, would now pass A2 on the margin alone if its levels differed by 0.1361. The
low-inflation share is the number to read when checking for that"* — and it is printed beside every
verdict (EXAM §4).

**Why the phase thresholds are where they are.** Three things stack (DELTA §3.4). The tolerance is
*half* history's departure, and the halving is the anchor's own uncertainty made into a rule — each
move type rests on about 35 uncensored transitions, and the sampling error on a fraction over 35
transitions is about **0.083, larger than the entire departure being measured**. That half is
eleven numbers, not one, because a 50 bp move of the classifier's dials shifts the departure by
1.35 of its own standard error on inflation crossings, with candidates ranging over
[0.040330, 0.082822] and [0.031446, 0.078601] — **factors of 2.05× and 2.50×**. And the ruling
takes the **minimum**, because the economic question is *"is there ANY unambiguous phase coupling in
this engine?"* and at the minimum every engine on the record still fails. The null is part of the
bar: the judge shifts each decade's inflation dial circularly against its growth axis, **every
admissible shift enumerated** at a 24-month guard, preserving each dial's own dynamics and
destroying only their alignment — so it **needs no seed and has no Monte Carlo error**, and it is
computed on *the batch being judged* rather than substituted from history, a substitution the
anchors measured wrong by up to **0.0126**, a fifth of a threshold.

**Why the curve bar is two-sided.** A share can be driven to 1.0 by shrinking the noise, so a
one-sided bar is gameable by an engine that removes the surprise the product needs; and a curve 100%
determined by three macro states would be wrong in the other direction, since part of an AR(1)
residual at ρ = 0.981 is genuine term-premium movement no macro state should explain. The anti-test
demonstrates the gaming route closed (§3.2). The strict-share accounting is itself the finding: on a
naive accounting two prior engines score 40.4% and 6.1%, but one engine's entire "explained" share
is a stand-alone mean-reverting process with no economic inputs, so under this accounting they score
**0.0%** and **2.2%** — *"and the gap between the two numbers is the finding the bar exists to
prevent recurring."* A pre-declared drop rule was applied mechanically — if history's interval came
back so wide that the recorded engines sat inside it, the bar was to be **dropped rather than
narrowed** — and the closer engine sits 0.359 to 0.415 below the lower edge, so it was kept
(DELTA §4).

**Why the no-regression bars have no tolerance.** *"A monotonicity check and a count of at least one
breach are the loosest form each condition can take. This is a regression guard, not an estimate."*
Both seam thresholds were sealed in an earlier round from the panel's own adjacent-month
distribution and carried unchanged, because *"re-deriving them now, with a rebuilt engine in hand,
is exactly the move pre-registration exists to prevent."* The seam bar was *expected* to flip
FAIL→PASS and the exam says so in advance — and because the judging code is byte-identical, a flip
is attributable to the fix rather than to a redefinition (EXAM §5).

### 4.1 Two rulers added later, deliberately not counted as bars

After the exam was run, two further instruments were designed, anchored, anti-tested and sealed —
and kept as *rulers* rather than promoted, because promotion is an owner ruling (RULERS).

**S1, the seam/texture ruler.** The carried seam bar's second half moves when seams get *bigger* and
when they get *more frequent*, and cannot tell you which. S1 judges shape and is blind to frequency:
*"given that this world spliced here, can you tell?"* Its criterion is that **a seam should be
statistically indistinguishable from an ordinary historical month-transition**, made concrete as the
seam-pair jump distribution sitting inside history's own adjacent-jump distribution at declared
quantiles. **Nothing about the generated world enters the derivation of the band.** Its anchor is not
new: history's adjacent-month `|ΔYoY|` over 800 transitions, 95th percentile
**0.7433911963542538** — the number the carried bar is cut from, to every digit. Every tolerance is
justified: quantiles 0.50 and 0.95 (p99 excluded because 800 anchor pairs leave it resting on eight
order statistics; the mean excluded because the distribution is strongly right-skewed and its mean
would double-count the tail), and 24-month resampling blocks imported from the campaign's primary
length rather than retyped.

Its anti-tests run *toward* fidelity, because an interval-shaped pass region makes a raw sweep
non-monotone by construction; at the fidelity point — where seam jumps *are* draws from history's
own distribution — **S1 passes 12 of 12**, the evidence that it is not a bar no design can clear.
Its control is the sharpest in the record: the obvious attack, seams at 2.5× history's scale
camouflaged by roughening, was **tried first and discarded as a strawman**, because no real months
are violent enough to hide a 2.5× seam. The sealed attack is calibrated to where camouflage
genuinely works — **seams only 1.3× history's scale** — and at 80th-percentile roughness a
*self-referential* bar (anchored on the world's own months) is fooled **half the time** while S1
fails 100% of the time with its texture half failing on the upper side 100% of the time. *"The
roughening that hides the seams is exactly what S1 catches"* — the entire justification for
anchoring on history rather than on the world's own months, stated as a measurement rather than an
argument (RULERS §1.6).

**A1R, the inflation-hedge measurement re-founded.** The sealed hedge bar is read on one batch of
fifty decades and asks only for a sign, and a six-seed disclosure showed that reading swings by
±5 pp. A1R computes the batch size from a power calculation at *the engine's own measured margin*:
for a two-sided test at α = 0.05 with power 0.90, `B ≥ 3.24152²·sd²/δ²`. Against zero, at the
pilot's sd of 3.8663 that is 166 sub-batches; at its **upper 90% chi-square bound** of 6.8129 it is
**514**. The upper bound was adopted deliberately — *"B scales with sd², and the sampling
distribution of sd² at six draws is wide… Adopting the point estimate alone would be doing a power
calculation at the most flattering reading of its own input"* (RULERS §3.2). Achieved power
**0.9004**. A cheap asymmetry falls out of the same table: telling this engine's hedge from
*history's* costs 25 sub-batches; telling it from *zero* costs 514. **The expensive question is the
interesting one, and nobody had bought it before.** Seeds are `20260821 + 15485863·k` for
`k = 0…513`, the stride prime and coprime with the platform's own, all 1,028 rung tapes verified
pairwise distinct — and **sub-batch 0 is the sealed verification seed**, so the old reading is
literally the first rung of the new ladder.

---

## 5. Results

### 5.1 The campaign arc

The engine was built and judged in five recorded stages, each with a named cheap exit. The shape of
the sequence matters: two of the five stopped at a *measured* frontier rather than tuning past it,
and the two that changed the engine were funded against a measurement rather than a hunch.

| stage | built | outcome |
|---|---|---|
| **v2 week 2** | a monthly season-transition hazard, 16 parameters, fitted by IRLS on **792 at-risk months carrying 35 growth-axis flips** | **FRONTIER 1**: transmission and ordering in direct opposition along transmission strength; *"there is no multiplier at which both pass"* |
| **v2 week 3** | a season-state term in the curve equation, three coefficients, no sign imposed | **FRONTIER 2**: the feedback is real (LR **12.2272 on 3 df, p = 0.00664**) and an order of magnitude too small against the residual it competes with |
| **stage 2 week A** | the full coupled system, eight pre-flesh bars | **FRONTIER**: 7 of 8 pass; the curve bar fails *from above* |
| **stage 2 week C** | the flesh; the whole twelve-bar exam, measured for the first time | **9 of 12 pass**; the conditioning-reach finding |
| **the reach fix, then three rulers** | conditioning extended to every month; a conditional era-crossing rule | reach 47.9% → 77.6% → 80.7%; both new rulers FAIL |

The week-2 frontier deserves its diagnosis quoted, as a clean case of a measurement telling a
modeller what to build next. The engine had causation running curve → season and **no feedback
running season → curve**:

| | share of inverted months that are expanding | base rate |
|---|---|---|
| **history** | **0.7651** | 0.7364 |
| week 2's engine | **0.4048** | 0.6896 |

*"In history the inverted curve sits where the turn has not happened yet. In week 2's engine it sat
inside the downturn — anti-concentrated exactly where T1 needs it concentrated"* (V2R §3).

Week 3 built precisely that channel and proved it real and correctly signed: a **young expansion has
the steepest curve** (+0.132 pp), flattening monotonically as the expansion matures (−0.167 pp by
month 120) — policy tightening into strength; a contraction opens at the unconditional mean
(−0.006 pp, because the curve inverted *before* the downturn and does not un-invert when it begins)
then steepens strongly as it runs (+0.270 pp by month 60) — policy cutting. *"The economics came out
of the likelihood, not out of a hand."* The diagnostic it was built to move moved from 0.4048 to
**0.4893**, **23.5%** of the gap to history, and monotonically past history's 0.7651 when scaled. It
still was not enough, and the campaign said so in a measurable quantity rather than a judgement: the
season term is worth **0.155 of a residual standard deviation**. *"A term worth a sixth of the noise
cannot reorganise a curve however right its sign is."*

### 5.2 The twelve bars, as read

The first campaign in four rounds in which **every bar has an actual reading** (S2R §2). Readings
are by the sealed judges, imported by name and never re-implemented; the eight pre-flesh bars and
three of the four flesh bars are read on the same unconditional 50-decade batch, so a flesh verdict
is attributable to the flesh alone.

| tier | bar | sealed band / floor | measured | verdict |
|---|---|---|---|---|
| causal | **T1** | [1.775283, 3.347362] | **2.239246798804** | **PASS** |
| causal | **O1** | ≥ 0.5180669104991394 | **0.560824742268** | **PASS** |
| persistence | **D1** | [0, 5] months | **2.0** | **PASS** |
| persistence | **D2** | [1, 7] months | **4.0** | **PASS** |
| persistence | **D3** | [2, 8] months | **4.0** | **PASS** |
| persistence | **D4** | [1, 7] months | **3.0** | **PASS** |
| phase | **P1** | ≥ 0.040330 / ≥ 0.031446 | **+0.101752 / +0.073520** | **PASS** |
| curve | **P2** | [0.391707, 0.673371] | **0.770682653481** | **FAIL — above** |
| allocation | **A1** | directional; containment | **+0.378055 pp**; high **+2.142368 pp** | **PASS** |
| allocation | **A2** | corr > 0; gap ≥ 0.136094; ≥ 80% | **−0.017743; +0.060911; 0.4760** | **FAIL — all three** |
| no-regression | **R1** | monotone; ≥ 1/20 breach at 55 | medians **[0.098065, 0.291855, 0.361632, 0.667991]**; breach **4/20** | **PASS** |
| no-regression | **R2** | join ≤ 2.5 pp; p95 ≤ 0.9292 pp | **4.132500 pp**; **0.883035 pp** | **FAIL — join half only** |

**Nine of twelve pass.** Three readings carry more than their verdict.

**The ordering bar had never passed anywhere it had ever been measured.** It clears its floor by
**+0.0428**; in the prior campaign it failed in all eight engine × arm cells (0.4913 to 0.5149) and
at every point of both frontier sweeps. It also clears the **windowing-symmetric** floor the stage-2
exam calls its primary construct — **0.515672**, by +0.045153 — so the reserved stop-question about
the two constructs disagreeing does not arise, and the review's demand that a stage-2 seal re-derive
the phase anchor under symmetric constructs is settled in the direction the review left open: **the
ordering is reachable** (S2R §2.5).

**The transmission bar moved further into its band**, 1.913081 → **2.239246798804** against an
anchor of 2.3718540268456376. It inherits a disclosure the verdict did not draw: the v2 engine ran
the generated curve at **27.5% inverted against history's 18.3%**, a 1.5× *over*-inversion, while
the stage-2 engine runs at **16.0% against 18.3%**, *under*-inverted. Since the bar conditions on
`slope < 0`, its conditioning population **moved from over- to under-inverted between the two
campaigns** while the reading moved 1.913 → 2.239, and any comparison must carry that (S2R §5.6).

**The persistence bars have never once been the binding constraint** — not here, and not across the
prior campaign's thirty-two frontier rows spanning a twelve-fold change in transmission strength and
a six-fold change in feedback strength. That is a real result: recovery persistence is exactly what
sank the pilot, the prior round and the neural generator at an earlier gate, and a generation-time
hazard with fitted duration dependence fixed it. Two cautions travel with it (§6.8, §6.9).

### 5.3 The channels, as estimated

**Transmission.** `cov_expanding[curve_slope]` = **−1.4888** (s.e. 0.5041, t = −2.95): a
one-standard-deviation flatter curve nine months earlier multiplies the odds of an expansion turning
by **exp(1.4888) = 4.43**. Its mirror `cov_contracting[curve_slope]` = **+1.1904** (t = +3.04): a
steeper curve raises the hazard of a contraction ending. *"Curves invert before downturns and
steepen out of them; the fit found both halves independently."* The lead time is an economic finding
chosen by likelihood on a pre-stated grid: **nine months wins by 2.8 log-likelihood points over its
nearest rival and 9.7 over the contemporaneous specification at identical degrees of freedom. On
this panel the yield curve leads the turn by about three quarters.** Stage 2 re-selected it by the
same likelihood and picked nine again.

**Coupling.** `λ_x` = **+0.006326** (s.e. 0.001063, **t = +5.95**), LR against no coupling **34.80
on 1 df**. The nested restriction tests, every one exact (FIT §3.2):

| restriction | df | LR | p |
|---|---|---|---|
| `c_i = 0` (curve does not read the policy rule) | 1 | **377.41** | 0.000 |
| `λ_x = 0` (inflation does not follow growth) | 1 | **34.80** | ≈ 0 |
| `λ_u = λ_c = 0` (policy is noise) | 2 | 7.10 | — |
| `c_x = 0` (curve does not read the inflation gap) | 1 | 3.53 | 0.060 |
| `c_C = c_E = c_K = 0` (no season block) | 3 | 6.11 | 0.107 |
| everything economic zeroed | 5 | 396.30 | — |

*"One reading dominates the table: the rule-implied policy rate is the curve's real content, by two
orders of magnitude over everything else that was added."* And week 3's season block, significant at
p = 0.0066 against a proxy, is **no longer significant** (p = 0.107) once the curve can read the
actual rule — most of what it was carrying turns out to have been the policy rate seen through a
proxy. It was **kept** anyway, because dropping a pre-existing fitted form after a new regressor
steals its significance is a post-hoc modelling choice; the demotion is reported (FIT §9).

**The phase reading:**

| move type | clockwise fraction | batch's own null | departure | threshold | % of history's |
|---|---|---|---|---|---|
| growth flips | 0.590244 (205 transitions) | 0.488492 | **+0.101752** | 0.040330 | **74%** |
| inflation crossings | 0.563433 (268 transitions) | 0.489913 | **+0.073520** | 0.031446 | **59%** |

The departures sit at **2.5× and 2.3× the sealed thresholds**, well clear of the 9.0% false-positive
band. Why that is nonetheless not the vindication it looks like is §6.2.

**One anchor's disclosure, because it shows what small counts buy.** The crisis-only version of the
transmission statistic, on six events, is a lift of 2.8646715810320167 with a 95% interval of
**[0.7051593174267592, 5.045392747118623]** that contains 1.0. It is reported beside every
transmission verdict and never judged — and in generated worlds it is reported **empty** rather than
faked, because a no-flesh spine has no equity path to fire the crisis label (EXAM §2; V2R §6.4).

### 5.4 The conditioning-reach fix

The campaign's headline finding — reported as a negative result in §6.4 — was funded as a fix, and
the fix's measurements are among the cleanest in the record. The defect: the compiler consulted the
world's story only where a block *opened*, and every other month was the panel's next row, taken for
no reason but contiguity.

| quantity | week C | after reach fix | + era rule |
|---|---|---|---|
| months that open a block | 494 — **8.2%** | 1,212 — **20.2%** | **20.7%** |
| **conditioning reach** (months whose drawn row carries the spine's quadrant) | 2,871 — **47.9%** | 4,658 — **77.6%** | **80.7%** |
| **story/market dial agreement** | **60.6%** | **77.8%** | **78.6%** |
| agreement expected if the dials were independent | 59.2% | 60.5% | 60.7% |
| **excess over chance** | **+1.43 pp** | **+17.32 pp** | **+18.02 pp** |
| mean inflation of a drawn month when the spine says "high" | 3.2248 pp | **3.8460 pp** | — |
| mean inflation of a drawn month when the spine says "low" | 3.0250 pp | **2.2490 pp** | — |
| seams | 444 | 1,162 | 1,193 |
| forced re-entries (of which unfiltered) | 1 (1) | **0 (0)** | **0 (0)** |

The fix has three parts, each preserving a named constraint: a **path-matched entry**, choosing an
entry for the length of the leading run over which the panel's own forward quadrants equal the
spine's coming months; a **mid-block divergence break**, ending a block whose next month would land
in the wrong quadrant; and an **anticipating re-entry**, which — when that break is unjoinable —
moves to a month from which history *walks into* the right quadrant. The look-ahead is **6 months**,
the world's own declared mean block length; reach across 6 / 12 / 24 is 0.776 / 0.766 / 0.709, so
*"the declared-block-length choice is also the best of the three on the funded objective; nothing was
traded to pick it"* (REACH §1.3, §2).

The pre-fix record's sharpest sentence became **false in the right direction**. It had read: *"a
'high' month's own inflation averages 0.20 pp above a 'low' month's, and both sit below the 3.3513
pp era line the pools are conditioned on."* After the fix the gap is **1.60 pp** and the high mean
sits **above** the era line while the low mean sits well below it.

The conditional era-crossing rule added afterwards is a **faithfulness test rather than a
relaxation**: *a seam may land on a row whose era bucket differs from the row the block is standing
on **only if** the spine's own inflation path crosses the era line between those same two months,
and only into the bucket the spine crosses into*. The window is **zero months wide** — no tolerance,
no lag, no look-ahead — because *"a ±k window would need a tolerance nobody has anchored"*, and a
window was available and **not taken**. The audit re-derives every bucket-changing seam **from the
compiled row tape and the decade's own season path, not from the engine's counters**, and the script
**raises** rather than reporting a number if any unlicensed crossing exists:

| arm | seams | bucket-changing | at a story crossing, in the story's direction | **unlicensed** |
|---|---|---|---|---|
| week-C baseline | 444 | 1 | 0 | **0** (the one is a counted forced-re-entry exemption) |
| reach fix | 1,162 | 0 | 0 | **0** |
| **+ era rule** | 1,193 | **104** | **104** | **0** |

Of 5,950 month-transitions, **323 are story crossings**; at **252** the block was standing in the
bucket the story was leaving, so the licence was live; **104** of those found a candidate also
satisfying the 2.5 pp level bound, pool membership, the severity stratum and the factor tolerance.
The rule captures **63%** of the reach a disclosure arm priced the whole era filter at, *"without
ever crossing at a month the world's story does not"* — the remaining 37% being the era filter
refusing to cross at months the story is not crossing either, *"which is the rule working rather
than the rule failing"* (RULERS §2).

### 5.5 What the fix bought, bar by bar

| bar | week C | after reach fix | + era rule |
|---|---|---|---|
| the eight spine bars | as §5.2 | **bit-identical** (worst drift 2.862e−13) | **bit-identical** |
| **A2** correlation (high) | −0.017743 **FAIL** | **+0.077493 PASS** | +0.025716 PASS |
| **A2** gap | +0.060911 **FAIL** | **+0.228567 PASS** | +0.180438 PASS |
| **A2** window share | 0.4760 **FAIL** | 0.6567 **FAIL** | 0.5960 **FAIL** |
| **A1** difference | +0.378055 **PASS** | −7.510267 **FAIL** | −9.680867 **FAIL** |
| **R2** join half | 4.1325 pp **FAIL** | **2.4997 pp PASS** | 2.4997 pp **PASS** |
| **R2** p95 half | 0.8830 pp **PASS** | 1.1023 pp **FAIL** | 1.2102 pp **FAIL** |
| **R1** breach at 55% | 4/20 | **8/20** | **10/20** |
| scoreboard | **9 of 12** | **8 of 12** | **8 of 12** |

**The correlation bar responded exactly as the funding ruling predicted.** Two of three conditions
flipped to PASS and the third moved 18 points toward its floor; the high-inflation correlation is
positive on **6 seeds of 6** after the fix (+0.077 … +0.143) where before it straddled zero. The
disclosure arm strengthened too, which is the check that the flesh was never the problem: judged on
the inflation the drawn months actually carried, correlation **+0.3327**, gap **+0.5088**, window
share **0.9367** — all three passing with room, and closer to history than before (REACH §5.1).

**The seam bar's join half was cured without being special-cased.** The entire pre-fix failure was
one unfiltered forced re-entry in 6,000 months. The fix never touches that rule; it makes blocks
whose forward path cannot track the spine unattractive to enter, and a block entered within a few
rows of the panel's end cannot track anything. Forced re-entries fall to zero, *"and with them the
only seam in the design that can exceed the bound"*; the largest remaining jump, **2.499733 pp**, is
an ordinary join landing 0.00027 pp under its own bound.

**The worlds got harder, not softer.** Every coverage median rises and the breach count at the most
over-committed arm doubles twice: 2/20 in the prior round, 4/20 at week C, 8/20 after the fix, 10/20
under the era rule. *"That is the direction a no-regression bar exists to protect."*

**Every flesh bar pays for the era rule.** It buys 3.05 points of reach and 0.72 points of
agreement, and costs the hedge difference (−7.51 → −9.68), the correlation (+0.077 → +0.026), the
seam p95 (1.102 → 1.210) and the seam-shape p95 (2.04 → 2.18). The scoreboard count does not move,
so nothing forces a choice; whether the ruling's own objective outranks the direction the bars moved
is left explicitly open. *"This is a frontier, mapped, not a defect"* (RULERS §2.5, §6).

---

## 6. Negative results and limitations

This section is not an appendix. Several of these results are more informative than the passes,
and two of them invalidate readings the project itself had published.

### 6.1 The funded arrow is inert

Stage 2 was funded on a specific diagnosis: the ordering bar fails because nothing couples the
*phase* of the growth and inflation dials, so build the growth → inflation arrow. It was built.
It is **significant on the panel** — `λ_x` = +0.006326, t = **+5.95**, LR 34.80 on 1 df, clearing
the pre-declared cheap-exit condition that named `λ_x` and nothing else. And it is **inert inside
a decade**.

Every row below is a real re-run from the same seed judged by the same sealed judges (FIT §5;
S2R §3):

| curve equation | `λ_x` | O1 | T1 | P2 share | P1 growth / inflation | bars passing |
|---|---|---|---|---|---|---|
| week 3's | ×0 | 0.5385 | 1.765 | 0.0247 | +0.0614 / +0.0569 | 6 |
| week 3's | ×1 | 0.5362 | 1.765 | 0.0242 | +0.0584 / +0.0563 | 6 |
| **stage 2** | **×0** | **0.5620** | 2.361 | 0.7717 | +0.1027 / +0.0720 | 7 |
| **stage 2 (the fit)** | **×1** | **0.5608** | 2.239 | 0.7707 | +0.1018 / +0.0735 | 7 |

> **The ordering bar moved by the coupling: −0.0012. The ordering bar moved by the curve:
> +0.0235.**

*"Read down the `λ_x` axis and nothing happens — twice. Read across the curve axis and everything
happens"* (FIT §5).

**Why, in one line of arithmetic.** Fitted persistence `a` = **0.994814**, a **half-life of 133
months**. The long-run inflation gap per unit of cycle input is `λ_x/(1−a)` = **1.2199 pp** — a
large number; a permanent expansion would eventually run about 1.21 pp hotter than a permanent
contraction. But growth spells in this engine last two to four years, over which only `1 − a^L`
of that adjustment happens: **11.7% at 24 months, 22.1% at 48**. *"The channel is real, it is
significant, and it operates on a timescale an order of magnitude longer than the cycle it is
supposed to be coupled to"* (S2R §3.1).

The coupling frontier is **flat**: scaling `λ_x` across ×0, 0.5, 1, 2, 4 gives ordering readings
of 0.5620, 0.5565, 0.5608, 0.5489, 0.5556 — a range of 0.013 with no monotone trend, which is
noise at fifty decades. *"There is no frontier on this axis. It is flat, and that flatness is the
campaign's central finding, not a null result to be buried"* (FIT §6). The disclosure arm makes
it worse: fitting the same inflation block on the classifier's own growth axis — the object the
*engine* generates — gives `λ_x` = +0.005021, **t = +6.10**, LR 36.49, persistence 0.998611, a
half-life of **499 months**. *More* significant and *more* inert.

The same finding has a harsher precedent. The week-3 season-to-curve feedback — the entire
deliverable of that week — moves the transmission bar by **−0.00036** on the arm it is judged on,
and **the bar passes with the feedback switched off** (V2R §8.2).

### 6.2 The phase bar passes through the reverse arrow

The bar written to test the funded coupling passes — through a channel running the *other way*.
The curve now reads `i_rule = r* + π* + φ_π·x + φ_c·c`, which **contains inflation**; the curve
drives the growth hazard at a nine-month lead; so the engine gained an **inflation → curve →
growth** channel, the reverse of the arrow the design diagnosed as missing.

> *"A phase relation between two dials does not care which way the arrow points, and P1 is a
> phase statistic. It is passing honestly and for the wrong reason, and the exam has no bar that
> can tell those apart — which is a fact about the exam and is now on the record."* (S2R §3.2)

The anti-test could not have caught it, and the campaign says so rather than discovering it
later: the sealed sweep that qualified the bar swept a *synthetic* coupling in which inflation is
a lagged copy of growth, and *"a sweep of the intended direction cannot detect a pass arriving
from the opposite one."* Writing a directional companion bar now *"would be a new bar written
after a coupling was fitted — which the exam delta's own opening sentence calls a description,
not a test"*, so none was written and the ruling is left open, with the note that the answer may
have to be *"acceptable, disclosed"* rather than *"fix it"*.

The consequence for reading the pass: the departures sit well clear of the 9.0% false-positive
band — *"but the reason they are clear is the reverse arrow, not the coupling"* (S2R §5.2). The
stop-question put to the owner is the honest form of the dilemma: *"the honest options are (a)
report stage 2 as having found O1 reachable by a different mechanism than the one it bought,
which is what this report does, or (b) treat a pass that the funded mechanism did not produce as
not a pass at all. This is a ruling, not a measurement, and it is the whole decision"* (FIT §12).

### 6.3 The inflation-hedge measurement was 47 standard errors wrong

The clearest single argument in the record for measuring how well you are measuring.

The hedge bar is read on one batch of fifty decades and asks only for a sign. Across six adjacent
seeds that reading swings by ±5 pp:

| engine arm | difference across seeds 20260821–26 | mean | sd | positive |
|---|---|---|---|---|
| before the reach fix | +0.378, −4.904, −4.604, +1.464, −5.568, −0.367 | **−2.267** | 3.093 | 2 of 6 |
| after the reach fix | −7.510, +0.637, +1.993, +0.028, +2.597, −3.594 | **−0.975** | 3.866 | 4 of 6 |

**The sealed seed is the pre-fix engine's best draw of six and the fixed engine's worst.** On the
mean the fix *improves* the statistic; on the sealed seed it flips it from PASS to FAIL
(REACH §5.2).

Pooled over **514 sub-batches of fifty decades — 25,700 decades**:

| quantity | pre-era-rule engine | era-rule engine |
|---|---|---|
| pooled difference | **−1.5448 pp** | **−3.1440 pp** |
| standard error | 0.1278 | 0.1311 |
| **95% interval** | **[−1.7952, −1.2943]** | **[−3.4008, −2.8871]** |
| distance from zero | **−12.1 SE** | **−24.0 SE** |
| distance from history's +3.4933 | **−39.4 SE** | **−50.6 SE** |
| sub-batches with a positive difference | 156 of 514 (30.4%) | 69 of 514 (13.4%) |
| verdict | **FAIL** (directional) | **FAIL** (directional) |

Because sub-batch 0 *is* the sealed verification seed, the old reading is the ladder's first
rung, so the two sit side by side:

| | sealed single batch (50 decades) | pooled (25,700 decades) | error |
|---|---|---|---|
| pre-era-rule engine | **−7.5103** | **−1.5448** | **−5.97 pp = 47 standard errors** |
| era-rule engine | **−9.6809** | **−3.1440** | **−6.54 pp = 50 standard errors** |

*"The sealed reading was not merely noisy: it was off by four times the whole effect on one
engine and by twice it on the other, and in both cases in the same direction, which is what makes
it a trap rather than a wobble. Every A1 verdict in this campaign's record — the PASS at week C,
the FAIL after the reach fix, and the six-seed disclosure that argued the flip was inside its own
noise — was a reading of a statistic whose sampling error dwarfed the thing it was measuring"*
(RULERS §3.4). The plan was also conservative twice over, and says so: the realised sub-batch sd
is **2.897** against the pilot's 3.8663, so the six-draw pilot overstated it by about a third,
and at the realised sd and the actual margin only **37** sub-batches were needed.

**The mechanism behind the negative sign is a real finding, independent of the flip.** The
compiler draws entry months from the worst 35% of panel months — and, in the crisis segment, the
worst 10% — by a joint-severity functional. Split that pool by inflation; these are panel facts,
no generation involved (REACH §5.2):

| population | months ≥ 4% YoY | commodities − bonds | months < 4% | commodities − bonds |
|---|---|---|---|---|
| whole panel (history's own anchor) | 225 | **+4.872 pp/yr** | 576 | +1.379 |
| worst-35% severity pool | 162 | +6.092 | 122 | **−11.487** |
| worst-10% severity pool | 59 | **−8.519** | 22 | **−20.851** |

> **The severe months of history are flight-to-quality months: bonds win and commodities lose,
> whatever inflation is doing.**

So the harder the compiler conditions — and the more months it therefore draws *from the pool*
rather than inheriting by contiguity — the more the hedge statistic reads the severity functional
rather than the inflation dial. The anticipating move sharpens this by construction, because it
parks on a wrong-quadrant month *from the pool*: at the sealed seed the most-drawn such months
are 2008-12, 2009-02, 2010-05/06, 1998-08 — *"the exact months where bonds rallied hardest."*

The campaign is careful about scope: *"A1R is a verdict about this engine on this panel, and it is
not a statement about inflation hedging… 25,700 decades measure that selection effect very
precisely and do not make it a fact about commodities"* (RULERS §7). A bar written on the whole
panel's inflation split is being read on a world whose months are drawn from the worst third of
the same panel, **and those two populations disagree in sign**. That is a limitation of the bar
rather than of the engine.

### 6.4 The seams have always been findable

The seam bar's first reading is a **FAIL on all three engines in the lineage**, and the finding is
not the fail but its date.

| arm | texture q50 | texture q95 | **seam q50** | **seam q95** | verdict | margin |
|---|---|---|---|---|---|---|
| week-C baseline | 0.2245 ✓ | 0.7282 ✓ | **0.6010** vs [0.1799, 0.2849] ✗ | **1.8289** vs [0.6087, 0.8830] ✗ | **FAIL** | −3.447 |
| reach fix | 0.2111 ✓ | 0.7435 ✓ | **0.6143** vs [0.1945, 0.2723] ✗ | **2.0418** vs [0.6444, 0.8426] ✗ | **FAIL** | −6.050 |
| + era rule | 0.2150 ✓ | 0.7597 ✓ | **0.6868** ✗ | **2.1836** ✗ | **FAIL** | −6.917 |

**The texture half passes on every arm, at both quantiles**: the months inside a block are
history's own months and they look like it. *"Whatever is wrong with these worlds, it is not
their within-block texture."* The seam half fails on every arm by a factor of two to three.

| arm | KS(seam, history) | null p95 at that n | KS(contiguous, history) |
|---|---|---|---|
| week-C baseline | **0.4556** | 0.3045 | 0.0297 |
| reach fix | **0.4530** | 0.2251 | 0.0555 |
| + era rule | **0.4860** | 0.2142 | 0.0507 |

A jump-threshold detector separates seams from ordinary historical months with **45–49 points of
advantage** over guessing, against a null allowing 21–30; the contiguous months are
indistinguishable from history at 3–6 points.

Three consequences (RULERS §1.8). **The seam problem pre-dates the reach fix**: the week-C engine,
with 444 seams and its pooled p95 comfortably inside the carried bar at 0.883, already had seam
jumps 2.5× outside their band and a detectability of 0.456 — so *"R2 passing its p95 half was
never evidence that the seams were invisible; it was evidence that there were few of them."*
**The era rule makes seams slightly bigger by construction**, since crossing the inflation line
means a larger inflation jump almost by definition. And **the lever is join *selection*, not the
join *bound***: every seam already respects the declared 2.5 pp bound, and what fails is that
among era-safe candidates the compiler picks without regard to how far inflation moves. A compiler
preferring small-Δ joins would move toward the band without touching a single declared tolerance.
That lever is named and **not exercised**, because it is an engine change and the campaign's
engine change was the era rule.

The bar also carries an unusual self-disclosure: **it was not cut blind.** The prior campaign had
already published this engine's seam and contiguous p95 (1.9143 and 0.6956 against a panel p95 of
0.7434) before the bar was designed. The band is nonetheless a pure function of the panel and a
sample size, and both sweep endpoints are fixed by construction — *"but a reader should know the
designer knew the answer"* (RULERS §7). The independent review's assessment: an honest
foreknowledge disclosure rather than a rigged statistic, with every discretionary choice traceable
to a pre-existing sealed convention and a FAIL margin far too large for any disclosed alternative
to flip.

### 6.5 The curve is 93.9% noise in one campaign and too determined in the next

The most consequential limitation of the v2 campaign sits **on the pass side of the ledger**: the
transmission bar cleared on the arm in which the generated curve is **93.9% exogenous AR(1)
residual**.

| engine | `û` contribution sd | season term sd | residual sd | residual share of variance |
|---|---|---|---|---|
| week 2 | 0.5358 | 0 | 0.6504 | 59.6% |
| ml_link | 0.1531 | 0 | 0.7426 | 95.9% |
| ols_feedback | 0.5419 | 0.2787 | 0.6028 | 49.4% |
| **the primary fit** | **0.1486** | **0.1132** | **0.7314** | **93.9%** |

Week 2 flagged 59.6% as a limitation; the estimator the joint likelihood names raises it to 93.9%
**and** clears the bar. *"Either the transmission bar is insensitive to how economically
determined the curve is — which is a finding about the bar — or exact ML is the right estimator
for an inference and the wrong one for a generator. The campaign did not resolve this and no
script can"* (V2R §6.3). The review added a fact leaning toward the first horn: within the
campaign's own four-engine set one engine **passes** at 49.4% noise while another **fails** at
59.6%, so **the verdict is not ordered by noise share** (V2R §8.7).

Stage 2 built the curve bar to make that quantity judgeable — and failed it **from above**:

| component | generated sd (pp) | history's (pp) |
|---|---|---|
| policy rule | **1.365831** | 0.836190 |
| inflation gap | 0.106533 | 0.078326 |
| season term | 0.059041 | 0.053794 |
| AR(1) residual, stationary (a model parameter) | 0.747993 | 0.747993 |
| **strict economic share** | **0.770683** | **0.558667** |

The exogenous block is empty on both sides, so the overshoot is not a classification argument — it
is **dispersion**: the generated rule-implied rate runs at **1.635×** history's, the slope at
**1.735×**, the inflation gap at **1.356×** (generated slope sd 1.4623 pp against 0.8427 pp).
**The coefficients are history's — nothing was scaled** — so a *share*'s numerator rises with no
coupling changing. The dispersion is inherited from the climate layer's across-decade state
spread: fifty decades each re-draw initial states from the posterior, and the spread of `r*` and
`π*` across those draws is wider than the single 68-year path history realised. No stage-2
coefficient touches it (S2R §2.2). The campaign's own reading generalises: *"This is the ER-14
pattern: coupling the spine did not make an existing defect worse; it made it visible, by putting
a bar in front of it that had never existed before"* (S2R §3.3).

### 6.6 Two coefficients are not identified, and twelve recessions is why

A coefficient is called unidentified when its 95% interval spans both signs — applied uniformly,
reported for every coefficient, not softened for those that fail it (FIT §3):

| block | coefficient | estimate | s.e. | t | 95% spans both signs? |
|---|---|---|---|---|---|
| inflation | `λ_x` (growth → inflation) | +0.006326 | 0.001063 | **+5.95** | no |
| policy | **`λ_u`** (policy leans on inflation) | +0.09215 | 0.06052 | **+1.52** | **YES** |
| policy | `λ_c` (policy leans on the cycle) | +0.03469 | 0.01359 | +2.55 | no |
| curve | `c_i` (curve ← rule-implied rate) | −0.24032 | 0.01101 | **−21.83** | no |
| curve | **`c_x`** (curve ← inflation gap) | +0.49203 | 0.26150 | **+1.88** | **YES** |
| curve | `C` (contracting level shift) | −0.07926 | 0.04322 | −1.83 | yes |
| curve | `E` (expansion age) | −0.03845 | 0.01555 | −2.47 | no |
| curve | `K` (contraction age) | +0.02681 | 0.01986 | +1.35 | yes |
| hazard | `cov_expanding[curve_slope]` | −1.48880 | 0.50412 | −2.95 | no |

**`c_x` — inflation's channel into the yield curve — is not established.** t = 1.88, LR 3.53 on
1 df, p = 0.060. The prior diagnosis was that *"inflation reaches the generated curve through no
channel whatsoever"*; stage 2 builds the channel, *"and 68 years of one country's history cannot
say how big it is. The sign is right and the size is a coin-toss away from zero"* — and it is the
coefficient the whole "inflation now reaches the curve" claim rests on. **`λ_u` is not
established** at t = 1.52; its companion `λ_c` is at 2.55, and the two together reject "policy is
noise" at LR 7.10 on 2 df. *"The block earns its place; the inflation half of it does not"*
(S2R §5.1).

Neither stops the campaign, and **which one would was pre-declared**: the cheap-exit condition
names `λ_x` and nothing else. *"Deciding after the estimates were visible that some other
coefficient was the real stop condition would be a goalpost move in the direction this campaign
has twice refused to move in, so nothing was reclassified."*

The correlation structure is *"as much of the answer as the standard errors"*. Cross-block
correlations are **exactly zero, not small**; the largest off-diagonal anywhere is **+0.741**,
inside the season block — three columns describing the same object from three directions. The
feared collinearity — the two curve loadings "both read policy" — **did not materialise**: they
correlate at **−0.199**, so the wide interval is thinness of signal (FIT §3.1).

The underlying constraint applies throughout: the hazard's at-risk set is **792 months carrying
35 growth-axis flips**. *"That is thin, it is why several coefficients carry t-ratios under 1, and
it is a fact about sixty-eight years of American economic history rather than about the estimator.
Duration dependence in particular cannot be distinguished from memoryless on this sample"*
(V2R §6.4).

### 6.7 The era-predicate ceiling

The conditioning fix cannot be pushed much further, for a structural reason rather than an
engineering one. **The panel's "hot" bit and the era-safe join's era bucket are the same
predicate** — both `panel YoY > era_threshold_pp`, the same 3.3513 pp on the same series. A join
must land in the spine's quadrant *and* match the previous row's era bucket; if the spine has just
crossed the inflation line while the row the block stands on has not, those demands contradict,
every candidate is filtered out, and the block continues. **An era-safe join can never follow the
story across the inflation line** (REACH §1.2).

Measured rather than argued: after the fix, **1,083 of the 1,342 remaining unreached months —
80.7% — are divergences the era filter refused**, and reach decomposes exactly, `1 − 1342/6000 =
0.77633`, with no other source of mis-conditioning left. A frontier arm dropping the era bucket
from the join filter buys another **5 points of reach** — and is **never adopted**, because
*"relaxing an era-safe join is an owner ruling, not a campaign's choice"*; it is reported *"so the
cost of the preserved rule is a number rather than an argument"* (REACH §2). The conditional
crossing rule recovers 63% of that priced cost, leaving the residual a genuine ceiling: *"the era
licence fires only where the spine crosses, and the spine crosses rarely"* (RULERS §7).

There is also a designed trade the fix cannot escape. Conditioning that reaches every month is
**bought with joins**, and a join may legally move trailing inflation by up to 2.5 pp — so the two
halves of the carried seam bar *pull against each other by construction*. The arithmetic
exonerates the contiguous months: after the fix the p95 over **contiguous** pairs *falls* from
0.7422 to **0.6956** and contiguous pairs above the bound *fall* from 128 to 106; what rose is the
seam count, 444 (7.46% of pairs) to 1,162 (19.53%), taking pairs above the bound from 4.35% to
6.87% and pushing the 95th percentile over the line. *"The contiguous months got calmer"*
(REACH §5.3).

### 6.8 Label instability, with magnitudes

Six of the exam's bars are measured on months a classifier sorted into four boxes, so the project
measured what happens when its two dials are nudged by **±0.50 pp** — chosen because on the
inflation side it *is* the platform's own smallest meaningful move in an inflation state and one
conventional central-bank move, with the growth dial taking the same amount so neither is nudged
harder in its own stated units. The re-labelling is *verified, not assumed*: the script asserts
the unperturbed rebuild reproduces the panel's own labels exactly before any threshold moves
(EXAM §11.1). The honest asymmetry is stated: trailing CPI has a panel sd of 2.81 pp with 157
months within 50 bp of its line, while trailing industrial-production growth has an sd of 5.37 pp
with only 38 — so the same 50 bp relabels 70–86 months on one dial against 8 on the other.

**Two questions, and they disagree.** Against each anchor's own *sampling interval*, all five
anchors are STABLE — and the exam immediately warns this *"is a weaker statement than it sounds"*:
*"The recovery median moves through a nine-month range under a half-point nudge of a line and
still counts as stable, because its sampling interval is eleven months wide"* (EXAM §11.2).
Against each anchor's own *bar*:

| bar | its band | arm range | arms falling **outside the bar** |
|---|---|---|---|
| **O1** ordering | ≥ 0.5181 | 0.5763 – 0.6154 | **none** (worst clears by 0.0582) |
| **D1** recession | [0, 5] m | 2 – 13 m | **3 of 8** |
| **D2** stagflation | [1, 7] m | 2 – 14 m | **7 of 8** |
| **D3** recovery | [2, 8] m | 4 – 14 m | **2 of 8** |
| **D4** expansion | [1, 7] m | 2 – 6 m | **none** |

> **For the recession, stagflation and recovery bars, history itself — re-measured with the
> inflation line moved half a percentage point — would fail the bar that was cut from history.**

Stagflation is the sharpest case and the pre-seal grader fix made it *worse*: seven of eight
perturbed arms put history's own pooled stagflation median outside the band, because the fix
routes stagflation months onto the growth axis and the growth dial's line is one of the two being
perturbed. **No band was changed** — *"re-cutting a bar from a sensitivity result is the goalpost
move pre-registration exists to prevent"* — and the reading is carried on every persistence
verdict: **a marginal verdict is not a finding** (EXAM §3, §11.3).

Applied to *fitted coefficients*, the same obligation produced two escalations, in units of each
statistic's own standard error (V2R §6.1):

| statistic | baseline | s.e. | worst threshold arm | movement | soft-label refit | verdict |
|---|---|---|---|---|---|---|
| transmission | −1.4888 | 0.5041 | infl +50 / growth −50 | **−1.044 SE** | −1.0785 (+0.814 SE) | **UNSTABLE — escalated** |
| `c_C` contracting | −0.1377 | 0.0539 | growth +50 | +0.626 SE | −0.2102 (−1.347 SE) | stable |
| `c_E` expansion age | −0.0623 | 0.0193 | growth −50 | **+1.074 SE** | −0.1039 (**−2.155 SE**) | **UNSTABLE — escalated** |
| `c_K` contraction age | +0.0673 | 0.0246 | growth +50 | +0.905 SE | +0.1076 (+1.637 SE) | stable |

Magnitudes to carry: **the transmission coefficient is pinned only to about a factor of two** —
range across all eleven arms **−2.0152 to −0.9876**, every arm keeping sign and significance; and
**the coefficient the whole week-3 mechanism rests on is pinned only to about a factor of 2.5**,
range −0.1039 to −0.0416. The reassuring arm: down-weighting months nearest the classification
lines moves transmission by only 0.32 SE, so the estimate does not rest on borderline cases —
*"it is the joint perturbation of both dials in opposite directions that bites."* And **the
direction of the instability is inconvenient: every escalated arm makes the mechanism stronger**,
which is exactly why the escalated arm was not adopted (§3.5).

Stage 2's own coefficients were re-checked, and one result is a *property rather than a
measurement*: the primary coupling coefficient is fitted against a regressor that is **not a
function of the classifier's dials at all**, so it is invariant across the grid by construction.
*"That is a real stability property and it is not a measurement: it says the coefficient cannot
move, not that it has been shown not to."* The dial sensitivity that genuinely exists is carried
by a refit on the classifier's own axis and moves 0.66 SE at worst — inside the rule. **Its
selected lag, however, moves between 1 and 2 months across the arms against the primary arm's
10.** *"The lag is the unstable part, not the size"* (S2R §5.3).

Finally, the escalation path has a hole the project declines to paper over. The sealed rule for an
escalated statistic is "refit with soft labels and report both", written for *fitted
coefficients*. A clockwise fraction is a **count**, and there is no agreed soft-label version of
one. *"Inventing a weighting after seeing which way it moved would be a goalpost move, so nothing
was invented"* (DELTA L3).

### 6.9 The grader's own known defect

The sealed grader reads a labelling ruleset that calls a month a recession whenever trailing
industrial-production growth is at or below zero — **with no official recession dating, no rise in
unemployment, no credit stress and no equity drawdown required**. A richer five-input classifier,
built and compared under a decision rule declared in advance, disagrees on **52 of 801
classifiable months**, concentrated rather than thin: **37 of the 109 months the sealed classifier
calls recession — a third — are reassigned, almost all to recovery**, clustered at **2015-03 →
2015-08**, **2016-04 → 2017-02** and **2019-04 → 2020-02** (EXAM §12.1).

It is declared rather than fixed for a governance reason: the ruleset is sealed platform-wide, and
changing it would move the panel's own labels, every anchor in the exam, and every prior round's
sealed record. *"That is a platform decision, not a pre-seal cleanup."*

The decision rule that kept the simple classifier — *"the richer classifier replaces the simple
one ONLY IF the disagreement changes an anchor by more than that anchor's own sampling noise"* —
did not trigger on any anchor under either reading of "sampling noise" (EXAM §11.6). But the exam
states what that protects: *"'Simplicity wins' is a verdict about the anchors, not about the
labels… The anchors survive because a median over ten-to-twelve spells is a blunt instrument, not
because the seasons agree. Anything that reads individual months — the generation-time hazard
link, for instance — has no protection from this result."* The campaign's central object is
exactly that. And a post-review correction drew the sharper consequence: the **2019-04 → 2020-02**
cluster *is exactly the right-censored recession spell the recession bar discloses*, so the defect
reaches a **persistence anchor** — the campaign's cleanest pass and the one thing handed forward
as settled (V2R §6.2).

Two notes keep the richer classifier from being simply better. It *overrules a real recession* in
1960-05 → 1960-11 — officially dated, but mild on every corroborating measure — *"a real cost of
the extra inputs, and the reason the richer classifier is not obviously the better instrument."*
And it enriches only the growth axis: **a second inflation series does not exist over the whole
panel**, so *"this is the dimension this comparison does not enrich, and nothing is substituted
for it"* (EXAM §11.4–11.5).

### 6.10 The rest of the standing list

- **A single event decided a verdict.** The seam bar's join-half failure was one forced re-entry
  in 6,000 months. *"Nobody should read 4.13 pp as a property of the engine's typical seam. The
  typical seam is 443 joins with a maximum of 2.48 pp"* (S2R §5.5).
- **The generated inflation *level* is half history's**: mean trailing CPI **1.81 pp against
  3.49 pp**, with the hot share nevertheless close (0.372 against 0.392) because the across-decade
  spread is wide. Inherited from the climate layer, and **no bar in the exam looks at it**.
- **The engine churns.** 439 growth-axis flips in 6,000 generated months (7.3% monthly) against
  history's 35 in 792 (4.4%), lifting the unconditional 12-month onset rate to 0.32 against 0.24 —
  *"and a high baseline compresses any lift the transmission bar can show"* (V2R §6.4).
- **The pinned climate artifact is mis-dispersed in two places**: the inflation gap over-dispersed
  at **1.604×** history's sd, the credit gap under-dispersed at **0.589**.
- **One covariate is a calibrated proxy.** A no-flesh spine has no equity path, so the drawdown
  covariate is a 36-month trailing drawdown of the climate layer's valuation state with one
  constant (−0.3234) calibrated so its firing rate on history equals the equity dummy's 11.685%;
  the two agree on **94.10%** of months. Calibrated to history rather than to a bar — *"and it is
  still a substitution inside the covariate that carries the largest expanding coefficient"*
  (V2R §6.7).
- **The inflation innovation is drawn i.i.d.**, as fitted; its residual carries a lag-1
  autocorrelation of 0.198 from the trailing-12-month construction. *"Simulating that structure
  would be simulating a model that was not estimated; it is declared rather than added."*
- **The curve bar's tape noise is unmeasured** (band cut from 2,000 draws; the adopted
  640,000-draw rule met by arithmetic rather than measurement), and **its verdict is not robust to
  the choice of summary**: the realised R², whose bootstrap interval `[−0.2203, 0.5616]` spans
  zero at every block length, would have dropped the bar. *"The reasoning that rejects it is the
  author's and should be checked rather than accepted"* — the one place a defensible alternative
  flips a verdict (DELTA L6, L9).
- **The strict share is not an explained-variance figure.** It treats components as uncorrelated;
  on history they are not — the rule-implied rate and the inflation gap correlate at **0.705** and
  history's total sum of squares is **1.78× the slope's own variance**. Reading 55.9% as "56% of
  the curve's movement is explained" is reading it wrong; that question's answer is the realised
  R², **0.2464** (DELTA L7).
- **The engine is a runtime substitution, not a promoted engine.** One function is composed at
  runtime inside a context manager that restores the platform on exit, with the projection asserted
  month-by-month on all 6,000 months. *"Whether the substituted sampler behaves identically once
  promoted is a claim this campaign does not make and cannot."*
- **A disclosed check inside a carried bar is now failing.** The severity bar passes both *sealed*
  conditions, but the script's third check — a self-constructed band documented as "constructed
  post-seal, disclosed, not judged" — cleared by 0.0009 at week C and is **outside on both later
  engines** (−0.5477, then −0.4867, against a shallow edge of −0.3750), so the judge's aggregate
  field is **false** while both sealed conditions pass. Both are in the artifact; neither is hidden.
- **Four of the twelve bars had never been run before this campaign**, so *"any sentence of the
  form 'five of six passed' is a statement about six bars, not about the exam"* (DELTA §1).
- **The standing caveat.** *"Nothing built on this generator line is a convincing model of history,
  the holdout is spent, and no appeal to held-out data is available to any result this campaign
  produces."*

---

## 7. The translation layer: how inflation reaches private assets

The exam measures a macro path and a set of asset returns. It says nothing about whether inflation
reaches an institution's **private** book, and the exam says so in its own scope section: a clean
pass on both allocation bars *"would say nothing about that"* (EXAM §7). This section reports the
second leg of the allocation thesis, because it is where the paper's argument generalises most
sharply: the defect was invisible for weeks, was found by a probe rather than a test, and was
closed by a mechanism whose every coefficient is *declared* rather than estimated — with the
declaration made a formal governance act.

### 7.1 The defect, measured

Filed after a single-field probe: the stagflation preset, 200 paths, one fixed seed, one field
varied — declared average inflation — everything else held. Annualised percentage returns (ER14):

| declared inflation | equity | bonds | commodities | **private equity** | **private credit** | **real estate** |
|---|---|---|---|---|---|---|
| 1.0% | −0.997 | 5.314 | 11.322 | **−1.772** | **7.369** | **1.839** |
| 2.0% | −0.997 | 5.314 | 11.322 | **−1.772** | **7.369** | **1.839** |
| 6.5% | −0.997 | 5.236 | 15.817 | **−1.772** | **7.378** | **1.798** |
| 12.0% | −0.997 | 5.059 | 22.271 | **−1.772** | **7.391** | **1.722** |

> *"**Private equity is bit-identical across a twelvefold change in inflation.** `pe = 1.4*eq +
> const`, and equity itself carries no inflation term, so the pass-through is not small — it is
> zero by construction."*

Private credit moves **+0.02 pp** over the whole range — *"noise"*. Real estate moves **−0.12 pp**
— *"the wrong sign for the asset class most often held as an inflation hedge"*. Commodities, at
+11 pp, are the only asset with material pass-through. The negative signs are volatility drag
rather than repricing: the realised mean policy rate moves only 6.342 → 6.358 from 1% to 12%.

The sharpest evidence is an attribution experiment — replace the commodity sleeve with equity and
re-run:

| declared inflation | private NAV (with commodities) | private NAV (commodities → equity) |
|---|---|---|
| 1.0% | 34.982 | 31.066 |
| 6.5% | 36.016 | 30.953 |
| 12.0% | 37.917 | **30.702** |

> *"**Without the commodity sleeve, the private book gets smaller as inflation rises.** The entire
> positive inflation response of the private programme is an indirect effect of a liquid sleeve
> sitting next to it in the same portfolio"* — transmitted through total NAV → reported private
> weight → the pacing multiplier → commitments → calls.

The defect had a contract-level signature worth recording as a general lesson. A map of
**declared-but-unconsumed fields** found the world specification could say "property income yield
is 8%", "private credit spreads are 600 bp", "infrastructure revenue is 85% inflation-linked" —
and the engine read none of them. *"The one place the contract knows how to say 'this asset class
passes inflation through' is attached to the one private class that is not simulated"* (ER14).

### 7.2 The mechanisms and the ratified-coefficient approach

The close-out routes inflation through one shared state variable and four asset-level channels.
The state variable is deliberately slow and deliberately shared:

```
K              = 24 months
C_ANCHOR       = 2.0 %/yr
infl_trail[m]  = mean of the trailing K months of annualised inflation
x[m]           = infl_trail[m] − C_ANCHOR          # "inflation excess", annual pp
```

Warm-up uses the months available rather than zero, because *"a decade world is 120 months and two
years of dead channel would be a fifth of the game"*; and the 2.0 anchor is not a fresh judgement
but a number the repository already declares in three places, pinned by a test asserting all three
equal.

Each channel splits a **level** effect (income or coupon escalation, which accrues) from a
**change** effect (discount- or cap-rate repricing, charged once):

| class | level channel | change channel | net |
|---|---|---|---|
| **real estate** | income escalation, **λ_RE = 0.30** | cap-rate repricing, **γ_RE = 0.50** on the existing duration 4.0 | **+0.30 pp/yr per pp of excess** |
| **private equity** | nominal revenue growth, **λ_PE = 0.35** | multiple compression, **μ_PE = 0.45** | **−0.10 pp/yr per pp** |
| **private credit** | floating coupon, **φ_PC = 1.0**, measured against the world's *own declared average* | loss-rate uplift **ω_PC = 0.03** (one-sided) plus spread convexity **θ = 0.10** | negative on net at high inflation |
| **infrastructure** (a new sleeve) | contractual escalators, **λ_INFRA = 0.60, read live from the world's declared `inflation_linkage`** | discount-rate repricing, **γ_INFRA = 0.30** | **+0.60 pp/yr per pp** — the strongest hedge in the book, by design |

**Every one of these coefficients is `chosen`, and none is `measured`** (ER14 §9). That is the
approach, defended as a discipline rather than a compromise:

> *"Each channel needs a coefficient, and a coefficient is a claim about the world, so the owner
> ratifies it rather than an implementer choosing it inside a commit."*

The house rule making "declared" different from "invented": *"every number below is traced to
something already declared in this repository — a sealed artifact, an amendment-logged
declaration, an existing engine constant, or an authored preset — or else it is derived in the
open from those. Where a number is genuinely a judgment with no repo-internal anchor, it says
so."* Four illustrations of that rule doing work:

- **γ_RE = 0.50** derives from a *committed measurement*: a rent-versus-less-shelter cross-check
  gives long-run pass-through **0.64**, of which **72%** is realised by eight quarters; 0.64 ×
  0.72 = **0.46**, rounded to 0.50.
- **μ_PE = 0.45** is read off the repository's own authored presets: all six worlds declaring 6.5%
  inflation also declare an entry-multiple drift of **−2.0%/yr**, and 6.5% is 4.5 pp above the
  anchor, so **2.0 ÷ 4.5 = 0.444**. Consistently, those hand-authored drifts were then **zeroed**
  in the live presets so the effect is not charged twice.
- **ω_PC = 0.03** comes from a *bounding rule rather than a pick*: inflation stress must never
  exceed the engine's own declared crisis stress, and since the crisis amplifier is a +0.6 uplift
  while the schema caps declared inflation at 20%, ω_PC ≤ 0.6/18 = **0.033**.
- **λ_INFRA is not a constant at all.** It is read live from the world's declared
  `inflation_linkage` field — the share of revenues contractually inflation-linked — because *the
  schema field is the pass-through coefficient definitionally*. A world writing 0.85 gets 0.85.

Two coefficients transplanted from a measured artifact — an infrastructure equity beta of
**0.3337** and a residual volatility of **0.0569** annual, from a sealed sleeve-mapping row
estimated on 60 quarters — are labelled ***`chosen` (transplanted from a measured row)*** rather
than `measured`, *"because calling them `measured` would overclaim"*. And where a number has no
anchor at all, the design says so: an infrastructure crisis term of −0.5, half of real estate's,
is *"the weakest-anchored number in the package — a judgment scaled off a neighbouring judgment,
with no external reference — and it is flagged as such rather than dressed up."* No acceptance
test depends on it.

**What makes the approach upgradeable** is that each coefficient ships with a **declared range**
and a **named measured-external upgrade path** — a property-index net-operating-income fit for the
real-estate pair, a private-credit loss-index match rule for the convexity term, a buyout revenue
panel for the private-equity pair. Adoption of a measured value is a **named owner release
event**, not a side effect of a report existing (REGISTER).

The project also built a precedent for validating a declared coefficient without spending data,
and its four conditions transfer wholesale. External-series comparison of a pre-committed authored
coefficient against published prints is *"validation evidence, not holdout access"*, under four
conditions and no wider: external series only, never a catalog read; **the compared value is
committed and hashed before the check runs** — *"a coefficient that could still move is not being
validated, it is being fitted"*; one execution, recorded verbatim including a result that
embarrasses the coefficient; and **never a calibration input** — *"re-running until it passes is
the failure mode this condition exists to forbid"* (REGISTER, SM-RULING-A).

Finally, acceptance bars were derived to survive their own coefficients' uncertainty: *"A
threshold is derived from the lower bound of the ratified coefficient's declared range, never from
its central value. A test that only passes when a coefficient happens to sit mid-range is testing
luck."* And where a net response is a small difference between two larger declared numbers —
private equity's −0.10 is λ_PE − μ_PE, and *"if the owner ratifies λ_PE at its top and μ_PE at its
bottom, the net is +0.19 and the sign flips"* — the acceptance bar is a **materiality** test with a
ratified floor on the absolute net, not a sign test (ER14 §2.2, §6).

### 7.3 What the close-out achieved, and what it did not

Measured on the same probe:

| asset | before | after | acceptance bar |
|---|---|---|---|
| real estate | **−0.117 pp/yr** (wrong sign) | **+3.35 pp/yr** | ≥ +1.5 |
| private equity | **0.000** (bit-identical) | **−1.12 pp/yr** | \|Δ\| ≥ 0.65 |
| private credit | **+0.022 pp/yr** | **−0.8990 pp/yr** | ≤ −0.30 |
| infrastructure | *the asset did not exist* | passing, and required to exceed real estate's | ≥ +4.0 |

Two properties bear on the paper's thesis rather than on the engine. **The determinism constraint
was proved rather than assumed**: the new infrastructure shock must be drawn **strictly last**,
because inserting it elsewhere silently re-rolls every other private residual and, through the
common-factor construction, the public assets, in every world. The break-and-revert proof was
executed — moving the draw to the top turned the guard test red with **100% of elements
mismatched** on a named world and asset, and reverting restored it.

**The battery re-run is a disclosure, not a gate**, and its clause is the general lesson: *"No band
was moved, is proposed to move, or should move as a result of this run. If a future reader is
tempted to widen a band to make a red battery run green, that is the mistake this document exists
to name in advance: **a flag is a finding, never something to be edited away**"* (ER14, battery
disclosure). Every public-asset stylised fact came back **bit-identical**; exactly one number
moved — a correlation-distance metric, 4.133 → 4.955 — and it carries no declared band, so it is
disclosed because it is the one number that moved at all. A separate metric already outside its
declared window before the work began is disclosed as *"a pre-existing, already-disclosed
condition this release neither creates nor worsens."*

**What closing the defect does not buy**, in the design's own six items:

1. **It is a response, not a hedge.** At 6.5% inflation, +1.35 pp/yr of property escalation and
   +2.7 pp/yr of infrastructure escalation are still large *real* losses. *"Private markets become
   inflation-aware, not inflation-proof."*
2. **The infrastructure escalator is symmetric and real ones usually are not** — caps and floors
   are deferred, so the design **overstates the class's deflation downside**, possibly by the whole
   −1.8 pp/yr the deflation mirror shows.
3. **The evergreen infrastructure vehicle a real allocator most often holds remains
   unparameterised**, because the cohort machinery is closed-end by construction.
4. **The propensity to distribute stays inflation-blind.** Inflation changes the *level* of
   distributions through net asset value but never the *propensity*: *"two worlds with identical
   equity drawdown and identical spreads — one at 12% inflation, one at 1% — will have the same
   distribution factor."*
5. **A policy reaction function was deliberately not built**, for a measurement-design reason:
   routing the fix through a public state variable *"reintroduces exactly the confound this is
   about"* — private markets would again respond only by transmission — and *"it moves every asset
   at once"*, destroying attribution.
6. **The standing caveat is unchanged.** *"Closing ER-14 removes one specific missing channel. It
   does not make anything built on the generator decision-ready."*

Three status disclosures the paper records rather than smooths. The design document is labelled a
**proposal awaiting ratification**; the coefficients were subsequently ratified unchanged and the
mechanisms shipped, so the numbers agree but the epistemic status of the two records differs. The
project's governing prose account of the defect and its engine-realism register entry are **both
still in their pre-fix state**, with the rewrite scheduled and unrun — so **the register entry is
not yet formally closed** even though the mechanism ships. And two coefficients on the *generated*
plane are explicitly **sign-only placeholders** pending the measured upgrade.

---

## 8. Related approaches

Brief and deliberately fair; the purpose is to locate the design point, not to claim priority.

**A citation caveat, carried from the project's own records.** The superseded preprint containing
this project's literature discussion states in its own related-work section that *"citations are
to be verified at page level before submission; several are currently sourced from working
summaries rather than from the originals"* (P1-PRE). This paper repeats the warning rather than
removing it: the neighbours below are named as the project named them, and none has been
page-verified for this draft.

**Regime-switching and semi-Markov models.** The natural comparison for a four-season clock with
fitted dwell times is the Markov-switching literature and its semi-Markov extensions; the project
places its own season layer there — sojourn times drawn from a duration distribution rather than
implied by a constant transition probability — with an epistemic caveat that distinguishes it from
the standard use: **the regime labels are a declared human taxonomy, varied in robustness grids,
not presented as discovered truth** (METHODOLOGY). That distinction is load-bearing. In a
Markov-switching model the states are latent and identified by the fit; here the four seasons are
*defined* by two published thresholds — which is why an entire section of the exam is devoted to
what happens when those thresholds move (§6.8) and why a defect in the labelling ruleset is a
first-class declared limitation (§6.9) rather than an estimation nuisance. The trade is
transparency for identification: nothing here discovers a regime, and everything here can be
audited.

**Block bootstrap and resampling.** The flesh layer *is* a conditioned block bootstrap — the most
direct neighbour, the more so because the project's history made it the incumbent. A block
bootstrap of real months was originally the *deliberately dumb alternative*, the kill criterion a
learned generator had to beat; three sealed contests later it is the generator of record, on the
finding that the learned model's edge was smaller than its own run-to-run noise (METHOD §3). The
standing sentence is *"rearranged truth now; invented worlds only when earned."* What this system
adds is conditioning: blocks selected to match a generated macro state, joins filtered on
inflation era and a bounded inflation jump, severity drawn from a declared stratum. What it
inherits is the severity ceiling and, as §6.4 shows, **seams a trivial detector can find**. The
honest summary is that this is a block bootstrap whose incoherence has been *measured* rather than
assumed away: 8.2% conditioning reach and 1.4 points of story/market agreement over chance before;
80.7% and 18.0 points after.

**DSGE and structural macro.** The coupled system is a small structural macro model in the sense
that growth, inflation, policy and the curve each read the others through estimated loadings — but
it is not a DSGE and claims none of one's properties. No optimising agents, no explicit
expectations operator, no cross-equation restrictions from an equilibrium; coefficients estimated
freely, "no coupling" restrictions tested as nested likelihood ratios rather than imposed as
priors. Two of five new coefficients are **not identified on 68 years of data** (§6.6), which is
precisely the constraint that motivates a DSGE's cross-equation discipline — and this paper's
response is to *report the non-identification* rather than to import restrictions that would hide
it. The contrast is therefore not "which model is better" but "what is the response to thin
data": a structural model buys identification with theory; this one declines the purchase and
publishes the interval.

**Economic scenario generators.** The cascade architecture — a slow inflation process driving
faster asset processes — is the direct structural ancestor of the three-layer design, and the
project names it as such (METHODOLOGY). Modern generative scenario work has moved to neural
architectures with substantially better high-frequency realism; the project's own list names
generative-adversarial, signature-based, diffusion-based, tail-elicitable and arbitrage-constrained
approaches, plus a regulatory-scope neural generator and its companion validation methodology
(P1-PRE §2.2). The gap claimed against that literature was that it *"does not generally produce
coherent decade-length paths carrying an explicit, auditable regime narrative and a modelled
distinction between reported and true values — because it is mostly aimed at short-horizon risk
measurement, where neither is required."*

That claim survives the turn but its emphasis moves. What this paper adds is not a better
generator; it is a **sealed acceptance apparatus with anti-tested judges**, and a set of
*measured* answers to questions usually argued: how much of a generated curve is economics (55.9%
in history, 77.1% in the engine, against a band of [39.2%, 67.3%]); how far a generated decade's
story reaches into its own months (8.2%, then 77.6%, then 80.7%); and whether a seam is findable
(yes, at 45–49 points of detector advantage). The literature's standard evaluation vocabulary —
discriminative and predictive scores, train-on-synthetic-test-on-real — measures whether synthetic
data *looks like* real data. It does not measure whether a decade *coheres as a story*, and the
bars of §4 are an attempt to make that measurable.

**Supervisory stress testing.** The neighbour the project moved *toward*, and the one the
superseded framing never engaged. A severely-adverse supervisory scenario is a declared,
internally coherent path used to ask whether an institution survives; it is not a forecast and
nobody pretends otherwise (METHOD §2). That is exactly this system's claim after the turn. The
differences: a supervisory scenario is authored by hand at low frequency and applied to many
institutions, whereas these decades are generated at monthly frequency with an ensemble of fifty
per premise and a per-decision attribution against a policy twin. The similarity is the one that
matters for interpretation: **severity is declared, and depth is an emergent consequence measured
after the fact, never tuned to a portfolio result** (METHOD §4; EXAM §6.3).

**What this paper supersedes.** The project's earlier working paper argued a "specified world
model" design point — authored latent dynamics, an authored observation operator, learning
confined to a bounded layer — with a four-layer hierarchical neural generator as its instantiation,
and made an identification argument for why the observation operator in this domain must be
specified rather than learned (P1-PRE). **That framing is superseded in two specific respects and
no more.** The *instantiation* was reversed: the learned generator lost three sealed contests and
the block bootstrap is the generator of record. And the *kind* of world that ships changed, from
plausible-future draws to declared stress scenarios. What is **not** retracted: the earlier
paper's sealed empirical results, which stand; its identification argument, which this paper
neither uses nor disputes; and its anti-prediction disclaimer, which was present from the start —
*"no predictive claim… nothing in this framework licenses a statement about what will happen"* —
and which the turn made **constitutive rather than caveat-shaped**.

---

## 9. Conclusion

### 9.1 What is established

**That economic realism in a generated decade can be made an engineering quantity.** Twelve
statistics, each with a historical anchor, a stated sampling interval, a justified tolerance and a
power calculation, were written down before the engine existed and hashed with the code that
judges them. All twelve were then read. The evidence for the claim is that the exam produced
results its authors did not want and could not argue away: a funded mechanism measured as inert, a
bar passing through the wrong channel, a curve failing from above, a headline statistic measured
47 standard errors wrong.

**That the engine has cause and effect at the macro level.** The transmission channel is estimated,
significant and correctly signed in both directions, at a likelihood-selected nine-month lead; the
seasons turn the right way round for the first time in the campaign line, clearing both the sealed
and the symmetric floor; and the four persistence bars pass in every arm, engine and frontier row
ever measured — a real result, because recovery persistence is exactly what sank three
predecessors.

**That the discipline catches what arithmetic cannot.** Three independent reproductions certified
every number to the digit and returned twenty-four interpretive findings between them, eleven of
the first twelve leaning the same way. A judge that measured nothing was caught by an anti-test,
not by intuition. A construct mismatch worth twice a bar's margin was caught by a reviewer, not by
the arithmetic. A determinism claim was falsified by running the check twice.

**That the failures are reportable.** Every negative result in §6 is in a committed record, most in
the same document as the passes, several correcting the project's own prior published readings.
That is the property the whole apparatus exists to produce.

### 9.2 What is not established

**Not that the engine is a convincing model of history.** The standing caveat is carried into every
campaign document and repeated here without softening. The holdout is spent; no appeal to held-out
data is available to any result in this paper; nothing built on this line is decision-ready.

**Not that the coupling works.** It is significant on the panel and inert inside a decade. The
paper reports the passes and the inertness with equal weight and does not resolve the ruling the
campaign left open: whether a pass the funded mechanism did not produce is a pass.

**Not that the phase relation is the one intended.** It arrives through the reverse channel, and
**the exam has no bar that can distinguish the two**. A directional companion bar would be a bar
written after the coupling was fitted, which is the thing the apparatus forbids.

**Not that the worlds are coherent at story scale.** They are far more coherent than they were —
80.7% conditioning reach against 47.9%, 18.0 points of story/market agreement over chance against
1.4 — and their seams remain findable by a trivial detector at 45–49 points of advantage. The
lever that would fix that is named and unexercised.

**Not that the allocation lesson survives the selection.** The inflation-hedge margin in these
worlds is precisely measured and **negative**, because the compiler draws months from the worst
third of the panel by a joint-severity functional, and the severe months of history are
flight-to-quality months where bonds win regardless of inflation. That is a fact about the bar and
the pool, not about commodities — and it means an allocation bar written on the whole panel's
inflation split is being read on a population that disagrees with it in sign.

**Not that the private book is inflation-proof.** The translation layer now responds in all four
private classes where before private equity was bit-identical across a twelvefold change. It is
*"a response, not a hedge"*: at 6.5% inflation the escalation channels are still large real
losses, the propensity to distribute remains inflation-blind, and the formal register entry is not
yet closed.

### 9.3 What would falsify it

The claim under test is that these statistics measure economic realism and that the engine has
improved against them. Five things would falsify it; four are cheap.

1. **A bar a correct engine cannot pass.** The power apparatus is the defence and has already
   caught two — one unpassable by construction, one demanding 400 decades on 2.8 points of
   headroom. A third would indict the apparatus rather than the engine. The tell is a power curve
   that *falls* as the ensemble grows.
2. **A judge whose pass rate does not rise in the effect it claims to measure.** This has happened
   once, publicly, and the sweep now runs before every seal. A carried bar failing a retrospective
   sweep would falsify the whole carried-bar argument.
3. **A verdict a defensible alternative construct reverses.** One is already on the record and
   disclosed: the curve bar's verdict is not robust to the choice of summary, and the reasoning
   rejecting the alternative is *"the author's and should be checked rather than accepted."* If it
   fails on inspection, the bar drops.
4. **A statistic whose sampling error dwarfs its effect.** This has also happened, and the fix — a
   power calculation at the engine's own margin, then a ladder of 514 sub-batches — is general. Any
   bar read on a single fifty-decade batch and asking only for a sign is a candidate; one such
   reading was re-founded and the rest have not been swept.
5. **The expensive one: an out-of-sample decade.** The system cannot be validated the way a
   robotics simulator can, because the real system is the future and no transfer experiment is
   possible at decade scale. The holdout that could have partially served is spent; a new reserve
   is accruing and will not be read before 2029. Until then the only honest position is that these
   worlds are prescribed rather than predicted, and that the case for them rests on the coherence
   statistics being measured under seal rather than on any claim about what will happen.

### 9.4 The transferable claim

Strip out the engine and a procedure remains. Write the statistics down before the thing they
judge exists. Anchor each to a measured historical quantity with its own sampling interval, and
justify the tolerance in the units of the decision it serves. Hash the thresholds together with
the code that judges them, and route every change through a log recording what was known at the
moment of the change. Prove each judge rises in the effect it claims to measure, and build
specific controls for the specific ways the bar could be gamed. Have someone else reproduce the
artifacts and characterise every failure before anyone reads a verdict. Compute the power, and
when a bar fails its own power calculation, fix the bar rather than buying compute. And when a
frontier sweep offers a hand-scaled row that passes everything, publish it and refuse it.

None of that is specific to economic decades. What is specific is the finding that when you do it,
the interesting results are the ones arriving in the wrong direction — the arrow that proved
inert, the bar that passed through the wrong channel, the hedge that was measured backwards.
Those are the results this paper considers its contribution, and the apparatus is what made them
sayable.

---

*Not investment advice — as every evidence document in this project concludes.*
