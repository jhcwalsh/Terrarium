# Stress scenarios: the method, in brief

*2026-08-14 · matches spec v0.2. The short version of
`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md`, for a
reader who wants to know what we do and why before reading how. The attribution
evidence behind §"Why we had to" is
`docs/superpowers/specs/2026-08-14-stress-phase0-attribution.md`.*

---

## What changed

We stopped asking the generator to predict and started asking it to **prescribe**.

A stress world is no longer an attempt at a plausible future. It is a declared,
severe, coherent decade — **real months, invented sequence, precedented severity
rule** — used to answer one question: *could this institution survive this?* Not
*how likely is this?*

That claim is worded carefully. Every month is a real historical month,
bit-exact. But the sequence is assembled, and precedent for the parts is not
precedent for the whole. What carries the whole is the declared rule with its
cited precedent, plus a measured plausibility statistic (a Mahalanobis distance
of the assembled decade against the historical record) reported with every
world — reported, never gated on. Plausibility is a property of the joint
configuration, not of literal precedent: an assembled decade that never
happened can measure as more plausible than one that did.

That puts us in the company of supervisory stress testing rather than
forecasting. A CCAR severely-adverse scenario is not a prediction and nobody
pretends otherwise; its authority comes from being severe, coherent, precedented
and published.

## Why we had to

The old worlds were too mild to test anything, and the reason was arithmetic
rather than taste.

Our historical panel runs 1953–2020. Of its 813 months, 38 carry the "crisis"
label, and those crisis months average **−1.79%** on equities. A world that
declares four quarters of crisis draws twelve months from that pool at its
historical average:

> 12 × −1.79% ≈ **−19.5%**

A 20% drawdown does not exhaust anyone's liquidity. That is why forced
secondaries — the event the whole institutional model exists to teach — fired in
**0 of 20 seeds**.

**And it really is the markets, not the machinery.** Three portfolio-side
defects were live in the same period, each capable of producing 0/20 on its
own. The attribution test ran all three down: the distribution linkage was live
in every measurement; the secondary haircut is priced only *after* a forced
sale triggers, so it cannot create one (proven bit-identical at the crisis-level
haircut across 100 world-seeds); and the old cloned opening book overstated
stress rather than hiding it. Under the fully corrected institution, every
shipped world reads 0/20 — the corrected book is *harder* to break, so the
severity gap is wider than we first stated.

The flaw was using a *label* as if it were a *severity*. "Crisis" is a
classification: the stratum contains October 2008 and also months that merely
satisfied the rule. Ranking by severity instead reaches the depth we need and
draws on **more** real material, not less — 82 to 163 eligible months rather
than 38.

## The rules

**1. Declare the rule, not the outcome.**
A scenario declares *how to sample* — "crisis quarters draw from the worst decile
of months" — and never *what should result*. Drawdown depth is an emergent
consequence, measured and reported after the fact. The alternative is circular:
tune a world until the book breaks, then discover that the book breaks. Any
finding would be guaranteed by construction.

*One operation looks like that circularity and is not:* **reverse stress
testing** — searching a rule space that was declared and committed *before* the
search for the least-implausible world that breaks a given book, then reporting
that world's plausibility and labelling it search-derived in its provenance.
The rule space is fixed first; only where the breakage lives is discovered.
Whether that ships, and when, is an open owner decision.

**2. Severity chooses the entry, history writes the rest.**
The severity rule restricts only which month a block may *start* on. From there
the tape runs forward through real history unfiltered — the aftershocks, the
policy response, the partial recovery that actually followed. History is
autocorrelated, and we don't model that autocorrelation: we inherit it. A
month-by-month severity filter would produce a bag of bad months in a shuffled
order, which is noise with a severe average, not a crisis.

Two consequences follow. Blocks in stress segments run long, because every join
is a discontinuity. And joins are restricted to months whose *levels* are close
to where we are — nine of our fourteen factors are levels rather than returns, so
a careless splice teleports the credit spread from 300bp to 1400bp in a single
month.

**3. Commit the rule before you measure the consequence.**
The scenario — severity rule plus the historical precedent cited for it — is
committed first. The institutional run happens in a later commit. Git history is
the pre-registration, and it costs nothing. If a scenario disappoints, the only
permitted response is to re-examine the rule against precedent; moving a
percentile because a forced-secondary count was disappointing is precisely the
circularity rule 1 exists to prevent.

**4. Persistence is declared too** *(new at v0.2; form still an owner
decision)*. Entry severity plus long blocks produces **episodes**; the
institutional tail is a sustained **decade**. Twelve severe months inside an
otherwise-normal 120 is a bad year inside an acceptable decade, and it will not
exhaust a liquidity programme. So alongside the entry rule, a scenario declares
how long the stressed state persists — as a declared shape (Japan 1990–2003 and
the real-terms US 1966–82 are precedents for stress *being* the decade), never
as a target depth. Rule 1 applies to this knob like every other.

## What a scenario claims

**Claims:** severe · coherent · real months, invented sequence, precedented
severity rule · disclosed.

**Does not claim:** probable · typical · representative · a forecast.

Two tiers govern what a stress world is judged by. **Coherence always gates**:
real rows bit-exact, whole-row co-movement, level continuity at joins,
non-negative prices, determinism — a world violating these is not severe, it is
broken. **Fidelity is exempt by design**: the realism battery's typicality
tests (named by id in the spec) answer the wrong question of a deliberately
atypical scenario, and no G-gate is taken.

## How to argue with one

Every scenario carries its precedent inline — *"crisis entry at the worst decile:
2007-09 ran −50% over 17 months; 1973-74 ran −48% over 21"* — and reports what
its rule actually produced, plus its measured plausibility. So the argument is
conducted on history, in the open, by comparing the emergent depth against the
episodes cited. You never have to read the sampler to dispute the severity.

## Limits, stated

- **No mechanism — and therefore no causal narration.** The compiler has no
  reaction function and no causal structure. Terrarium properly has **two
  compilers**: this one (severity rule, no mechanism, institutional tier) and a
  premise compiler (named shock plus attribution, full causal narration) that
  is **not built**. Hard rule: **nothing built on the stress compiler may
  narrate causality it does not contain** — a wire over a stress world reports
  what happened, never why.
- **A ceiling set by the pool.** The worst rolling twelve months in the panel
  is −42.6%, and both this ceiling and the thin material at the extreme come
  from drawing on one country's record. The first-choice remedy is the
  international record (Japan post-1990, UK 1973–75 in real terms, the
  advanced-economy panel) — it widens the pool instead of slicing the same one
  thinner; extending into 1929–32 is second choice. Both are licence-blocked
  pending Counsel; the JST non-commercial correction sits upstream.
- **Thin material at the extreme.** A tight percentile draws repeatedly from a
  small pool of real months, so severe seeds resemble one another more than mild
  ones do. That is disclosed in the depth report rather than hidden.
- **Severity is estimated; incidence is curated — never confuse them.** How
  deep a scenario runs is fitted, with bands. How often the library *serves* a
  stressed world is a curation choice with no probabilistic content, disclosed
  on the world card. Serving stress often while implying it is rare would
  attach a probability by accident — the register (`docs/tail-register.md`,
  TR-7) carries the check.
- **Lessons about institutional mechanics transfer; lessons about market
  judgement do not.** These worlds are built to exercise liquidity, pacing and
  the appraisal lag. They are not evidence about anyone's ability to time a
  market.
