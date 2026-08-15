# Stress scenarios: the method, in brief

*2026-08-14. The short version of
`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md`, for a
reader who wants to know what we do and why before reading how.*

---

## What changed

We stopped asking the generator to predict and started asking it to **prescribe**.

A stress world is no longer an attempt at a plausible future. It is a declared,
severe, coherent decade — assembled entirely from real historical months — used
to answer one question: *could this institution survive this?* Not *how likely is
this?*

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

The flaw was using a *label* as if it were a *severity*. "Crisis" is a
classification: the stratum contains October 2008 and also months that merely
satisfied the rule. Ranking by severity instead reaches the depth we need and
draws on **more** real material, not less — 82 to 163 eligible months rather
than 38.

## The three rules

**1. Declare the rule, not the outcome.**
A scenario declares *how to sample* — "crisis quarters draw from the worst decile
of months" — and never *what should result*. Drawdown depth is an emergent
consequence, measured and reported after the fact. The alternative is circular:
tune a world until the book breaks, then discover that the book breaks. Any
finding would be guaranteed by construction.

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

## What a scenario claims

**Claims:** severe · coherent · composed entirely of real, precedented months ·
disclosed.

**Does not claim:** probable · typical · representative · a forecast.

Because it is atypical by construction, a stress world is not judged against the
realism battery. Asking "is this the typical distribution of futures" of a
deliberately severe scenario answers the wrong question.

## How to argue with one

Every scenario carries its precedent inline — *"crisis entry at the worst decile:
2007-09 ran −50% over 17 months; 1973-74 ran −48% over 21"* — and reports what
its rule actually produced. So the argument is conducted on history, in the open,
by comparing the emergent depth against the episodes cited. You never have to
read the sampler to dispute the severity.

## Limits, stated

- **No mechanism.** The compiler has no reaction function and no causal
  structure. It cannot explain *why* anything happened, and nothing built on it
  may narrate causality it does not contain.
- **A ceiling set by the span.** The worst rolling twelve months in the panel is
  −42.6%; 1929–32 lies outside the sealed draw span. Depression-class severity
  would need the span extended, which is a data-layer project with its own
  proxy and licensing consequences.
- **Thin material at the extreme.** A tight percentile draws repeatedly from a
  small pool of real months, so severe seeds resemble one another more than mild
  ones do. That is disclosed in the depth report rather than hidden.
- **Lessons about institutional mechanics transfer; lessons about market
  judgement do not.** These worlds are built to exercise liquidity, pacing and
  the appraisal lag. They are not evidence about anyone's ability to time a
  market.
