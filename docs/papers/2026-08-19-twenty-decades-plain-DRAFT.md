> **DRAFT — pending owner edits.** Not reviewed, not released, not citable outside this repository.
> **Date:** 2026-08-19.
> The plain-English account of what was built, how it was tested and — mostly — what it got wrong. Companion to the working paper `docs/papers/2026-08-19-economic-realism-engineering-quantity-DRAFT.md`; the player-facing guide is `docs/papers/2026-08-19-decade-you-live-through-users-guide-DRAFT.md`.

---

# Twenty Decades That Never Happened

*A plain-English companion to the working paper. What we built, how we tested it, and — mostly —
what it got wrong. Not investment advice.*

---

## 1. One history is not enough practice

An investment committee learns its trade from the decades its members have lived through. That is
a very small classroom. Our usable monthly record of the American economy runs from April 1953 to
December 2020 — **813 months**. Inside that stretch there are **seventeen** starts of a recession
or a crisis, and only **six** genuine crisis events. Sixty-eight years of the most heavily
documented economy on earth gives you seventeen of the events that actually matter.

That is not just an uncomfortable fact; it has arithmetic consequences we measured rather than
asserted. Take a simple question: how long does a recession last? The record says the middle answer
is three months. But when you take that same record and resample it — repeatedly rebuilding fake
histories out of its own real stretches, to see how much the answer wobbles — the honest range is
**one to twelve and a half months**. Recoveries look like nine months, honest range five to sixteen.
The numbers a practitioner would quote without hesitation are soft by a factor of two or three.

So the problem isn't the philosophical remark that history might have gone otherwise. It is this:
*the estimates that describe how a decade behaves are so wide that an institution tuned to the
point estimates is tuned to noise.* And the decisions being tuned — how much illiquidity to hold,
how much inflation defence to carry, how big a commitment programme to run — are made once, against
one path, and then lived inside for ten years.

What we built is a machine that manufactures other decades to practise on: twenty of them, fifty of
them, all coherent, none of them real. The rest of this piece is mostly about how we tried to prove
ourselves wrong.

---

## 2. How the machine works

Three layers, stacked. Think of climate, seasons, and weather.

**The climate.** Underneath everything sits a slow-moving backdrop with five dials: the long-run
drift of inflation, the neutral interest rate (the one that neither stimulates nor restrains), the
trend rate of growth, how expensive shares are, and how stretched credit is. These move over years,
not months. They are estimated from a long historical panel using about thirty-five underlying
parameters, and each generated decade starts by drawing a plausible set of them. This is where a
world gets its personality — high-inflation and low-growth, or calm and cheap.

**The seasons.** On top of the climate runs a monthly clock with four seasons, defined by two
yes/no questions: *is the economy expanding?* and *is inflation hot?*

|  | inflation cool | inflation hot |
|---|---|---|
| **expanding** | recovery | expansion |
| **contracting** | recession | stagflation |

"Hot" means trailing inflation above **3.35%** — a line we did not choose but measured: it is the
historical panel's own dividing line, so the same rule sorts real months and generated months
identically. The natural clockwise order is recovery → expansion → stagflation → recession → and
round again. Notice that each step changes exactly one of the two answers — which is why one of the
tests below is really about whether the two dials keep time with each other, rather than about
either dial alone.

The seasons don't take turns on a timer. They are wired together, and the wiring came out of the
data rather than out of anyone's hand. Growth feeds inflation with a lag. Policy leans against both
inflation and the cycle. Interest rates set the yield curve — the gap between long-term and
short-term borrowing rates. And the curve feeds back into whether growth turns, at a lead of **nine
months**, a delay the statistics chose rather than us. The one equation worth writing down is the
policy rule, in words:

> **interest rate = neutral rate + trend inflation + a reaction to how far inflation has strayed +
> a reaction to where we are in the cycle**

The loop closes: growth → inflation → interest rates → the yield curve → nine months later →
growth. Because the last arrow has a genuine lag, there is no circularity to unravel; each month is
computed from months already settled.

Downturns arrive by dice roll, not by schedule. The machine takes the historical frequency of
corrections starting from the conditions the world is currently in, and rolls. In the project's own
words: *"the machine does not predict them. It reproduces the statistics of their preconditions and
rolls dice."* Two decades built from the same premise differ in when — and whether — a second shock
lands, so a repeat player cannot learn a timetable.

**The weather is real.** Here is the design decision that shapes everything else. The top layer
never invents a market month; it **selects** them, verbatim, from real history. When the storyline
says "this is a hot-inflation contraction, and a severe one," the machine finds real months that
were exactly that, and plays their actual returns — equities, bonds, commodities together, with
their true relationships intact. The rule, carried unchanged through every round of work: **the
story chooses which real months are drawn, and never edits, scales or invents one.**

The slogan is **real months, invented sequence, declared severity**.

You get realism for free — a stagflation stretch really behaves like stagflation, because it *is*
stagflation. You pay for it with a hard ceiling on severity: the worst twelve-month stretch any
generated decade can produce is history's own worst twelve months, **−42.6%**, and the machine
cannot show you something the record has never shown. (The obvious remedy, other countries'
records, is blocked by data licensing.)

---

## 3. How we know whether it's any good

This is the part we think is the real contribution, and the metaphor that runs through it is an
exam.

**The questions were written before the student existed.** Twelve pass/fail tests, each anchored to
a measured historical quantity, each with its tolerance justified in writing. They were finalised
and cryptographically sealed — thresholds *and* the code that grades them, hashed together — on 17
August 2026, *before any engine work and before a single generated decade existed*. The governing
sentence is blunt: **"a threshold chosen after seeing results is not a test, it is a
description."**

Every tolerance carries a stated reason. Season lengths are graded to within **one quarter**,
because a quarter is the smallest unit the product lets a player act in — grading finer would score
a distinction nobody can trade on. The inflation-hedge test uses a **4%** line, because 4% is
roughly double a modern central-bank target (so it is genuinely "high") and because it is the round
number a practitioner would name rather than the one that maximises the effect. We also published,
before grading, what happens at 3% and 5%. At 3% the answer *reverses sign*, because that line drags
most of the 1983–99 disinflation into the "high" bucket — the best stretch on record for long bonds.
Publishing that in advance is the difference between a threshold and an excuse.

**The graders were themselves tested for honesty.** Before a test is sealed, we sweep the thing it
claims to measure and confirm its pass rate goes *up* as that thing gets stronger. This obligation
exists because of an embarrassment. An earlier round sealed a test of whether policy responds to
inflation, ran it, and got a clean failure on every seed. On review, the test carried **no
information about the model at all**: it compared one quantity in changes against another in levels,
which mathematically produces a *negative* reading in the very effect being measured. The stronger
the policy response, the worse the score. A model with no policy response whatsoever scored the best
result the test could produce — about 0.47, still short of the 0.90 needed to pass. **The exam was
unpassable by any model, including a perfect one.** Rebuilt correctly, the policy response was
there, correctly signed, on all twenty decades.

Alongside the sweeps sit deliberate attacks: an engine trying to cheat a test by shrinking its own
randomness must fail, and does, twelve times out of twelve; and a passing batch, scrambled to
destroy the pattern being measured, must collapse — it does, from 0.29 to roughly zero, with the
pass rate falling from 100% to 12%.

**Every grade was independently re-checked.** No verdict reaches the owner until someone else
re-derives each grader's formula from scratch, re-runs the scripts, and characterises every failure.
Those reviews reproduced the results **byte for byte** and found **no number, verdict or arithmetic
wrong**. What they did find were interpretive errors — twelve in one review, of which the reviewer
noted that **eleven leaned the same way: they made our own work look better than the evidence
supported.** One forced a published claim to be withdrawn. Another pointed out that the feedback
mechanism an entire week of work had produced could be switched off entirely and the test it was
built for still passed.

**Two tests were thrown out for being unfair, before results existed.** We calculated in advance
whether a *correct* engine could pass each bar. One couldn't: the recovery-length test measured its
historical target across the whole record while grading the engine on ten-year windows, and those
aren't the same number. The tell was a calculation that got *worse* as we generated more decades —
0.36 at twenty, 0.14 at three hundred — because it was converging on a value the test excluded.
Measuring both sides the same way fixed it. A second test needed roughly four hundred decades to be
decisive; rather than raise the bar to make it cheaper, we **dropped it**, because a bar moved after
seeing what it costs is a bar chosen for convenience.

**And we refused the tempting row.** When the engine failed one test, a sweep found a setting — the
fitted coefficients halved by hand — at which everything passed. It was published and refused:
*"halving a coefficient because a bar is on the other side of it is the definition of tuning past a
conflict."*

---

## 4. The scoreboard, and the interesting half

**Nine of twelve.**

| what it asks | result |
|---|---|
| Does tighter policy actually cause downturns? | **pass** |
| Do the four seasons turn in the right order? | **pass** (first time ever) |
| How long recessions last | **pass** |
| How long stagflations last | **pass** |
| How long recoveries last | **pass** |
| How long expansions last | **pass** |
| Do the growth and inflation dials keep time with each other? | **pass** (but see below) |
| Is the yield curve made of economics? | **fail — too much so** |
| Does the inflation hedge pay when inflation is high? | **pass** — and the pass was luck (see below) |
| Do shares and bonds fall together when inflation is high? | **fail** |
| Does severity still hurt a portfolio? | **pass** |
| Do historical eras teleport at the joins? | **fail**, on one of two halves |

The season-length tests deserve a note: getting a generated recovery to last as long as a real one
had sunk three previous attempts, and they now pass in every engine setting ever measured.

But the failures taught us more, so here they are at length.

### The mechanism we funded, which did nothing

A whole round of work was funded on one diagnosis: the seasons turn wrongly because nothing connects
the *phase* of the growth dial to the phase of the inflation dial. So build that connection — make
inflation follow growth.

We built it. On the historical panel it is unambiguously real: the coefficient sits more than five
standard errors from zero. Inside a ten-year world it is **completely inert**. Switching the whole
thing off moves the headline test by **−0.0012** and flips no verdict. The yield-curve change made
in the same round moved it by +0.0235 — twenty times as much.

The reason fits in one line of arithmetic. The inflation gap the connection feeds is extremely
persistent: its half-life is **133 months**. Growth phases in this engine last two to four years,
over which only **11.7%** of the adjustment happens. *The channel is real, it is significant, and it
works on a timescale ten times longer than the cycle it was supposed to be coupled to.* Scaling it
up fourfold or down to zero produces no trend at all. That flatness is the round's central finding,
and it is a negative one.

### The test that passed for the wrong reason

The phase test — whether the two dials keep time — passed comfortably, at two and a half times its
threshold. It passed through a channel running the **opposite way** from the one we built. The new
yield-curve equation reads a policy rate that *contains* inflation, and the curve drives growth nine
months later, so inflation now reaches growth by a back route. A phase relationship doesn't care
which way the arrow points.

**Our exam has no test that can tell the two apart.** We could write one, and deliberately didn't:
a test written *after* seeing which mechanism fired is a description of the result, not a test of
it. So the finding is recorded as passing honestly, for the wrong reason, with the exam unable to
distinguish. That is a fact about the exam, and it is on the record.

### The headline number that turned out to be luck

The inflation-hedge test — do commodities beat bonds when inflation is high? — was read on a single
batch of fifty decades and asked only for a sign. Run the same reading on six adjacent random seeds
and it swings by about ±5 points, flipping sign repeatedly. So we re-measured it properly, with a
batch size computed from the engine's own variability, on **25,700 decades**.

| engine version | the single sealed reading | the proper measurement | error |
|---|---|---|---|
| one | **−7.51** | **−1.54** | **47 standard errors** |
| the next | **−9.68** | **−3.14** | **50 standard errors** |

The sealed seed happened to be one engine's best draw of six and another's worst — which is why the
same test read as a pass on one version and a clear fail on the next. Every published verdict on it,
including a disclosure arguing the difference sat inside its own noise, was a reading of a statistic
whose measurement error dwarfed the thing it was measuring.

### What the inflation-hedge truth actually is

Once measured properly, the answer is negative: in these worlds, commodities do *not* out-earn
bonds when inflation is high. That looks like a defect. It is a finding about crises.

The machine draws its months from the worst third of history by severity — that's what makes a
generated decade a stress test rather than an average one. Split that severe pool by inflation and
here is what you find, using nothing but real historical months:

| where the months come from | high-inflation months | commodities minus bonds |
|---|---|---|
| the whole record | 225 | **+4.87 %/yr** |
| the worst 10% by severity | 59 | **−8.52 %/yr** |

> **The severe months of history are flight-to-quality months: bonds win and commodities lose,
> whatever inflation is doing.**

So the harder the machine conditions on severity, the more this test measures the severity filter
rather than the inflation dial. It is not a statement about commodities as an asset class; it is a
statement about the specific months when everything is going badly. A test written on the whole
record's inflation split is being read on a population that disagrees with it *in sign*. That is a
limitation of the test — and arguably the most useful single thing the exercise produced.

### Three more, briefly

**The seams are visible.** Because decades are assembled from blocks of real months, they have
joins. A trivial detector — look for a big jump in trailing inflation — spots them with **45 to 49
percentage points of advantage** over guessing. The months *inside* blocks are indistinguishable
from history; the joins are not, and always were not: an earlier engine looked cleaner only because
it had fewer joins, not better ones. We know the fix — choose joins that move inflation least — and
deliberately haven't made it yet.

**The yield curve fails from above.** It is *too* determined by the economy — 77% economic content
against a permitted band of 39% to 67% — because the climate layer spreads its starting conditions
wider across fifty decades than the single path history happened to walk. A real curve contains
genuine surprise; ours contains too little.

**History would fail its own exam.** Nudge the two classifying lines by half a percentage point and
re-measure history itself: for three of the four season-length tests, **the real record would fail
the bar that was cut from the real record.** No band was changed as a result — re-cutting a bar from
a sensitivity result is exactly what sealing exists to prevent — but the reading rides on every
season verdict: a marginal pass is not a finding.

### And one found by accident

Separately from the exam, a probe asked what happens to a portfolio's private assets as declared
inflation rises from 1% to 12%. Answer: **private equity returns were bit-identical** — not slightly
insensitive, literally the same number, because private equity was defined as a multiple of public
equity and public equity carried no inflation term. Real estate moved 0.12 points *in the wrong
direction*. The whole apparent inflation response of the private book was a side effect of the
commodities sitting beside it. Real estate now moves from −0.12 to **+3.35** points a year and three
other private classes respond too, but the honest description is *"private markets become
inflation-aware, not inflation-proof."*

---

## 5. What this is for, and what it is not for

**It is for practice and for stress-testing.** An allocator can run the same institution through
twenty coherent decades and see which choices survive all of them.

**It is not a prediction, and the reason is worth stating plainly.** In 2026 we made a deliberate
turn: the machine stopped being asked *what will happen* and started being asked *could this
institution survive this?* A generated world is a **declared** stress scenario, in the same sense
that a bank supervisor's "severely adverse scenario" is not a forecast and nobody pretends it is.

That turn was forced by arithmetic, not philosophy. We had been declaring worlds by *labelling*
months as crises. But of 813 historical months, 38 carry the crisis label, and they average −1.79%
on equities. A world declaring four quarters of crisis therefore drew about −19.5% — and a 20%
drawdown exhausts nobody's liquidity, which is why forced asset sales fired in **zero of twenty**
test worlds. "Crisis" is a classification containing both October 2008 and months that merely
satisfied a rule. Ranking by *severity* instead reaches real depth, and draws on **more** genuine
material: 82 to 163 eligible months rather than 38.

**It is not decision-ready, and we say so in every document.** Nothing built on this line is a
convincing model of history. The dataset we had held back for a final honest test has been spent, so
no appeal to held-out data is available to anything here, and a new reserve cannot be read before
2029. Until then the only honest position is that these worlds are *prescribed*, not predicted.

---

## 6. Why the discipline is the real invention

Strip out the economics and a procedure remains. It goes like this.

Write the tests down before the thing they judge exists. Anchor each to a measured historical
quantity, and state how uncertain that quantity is. Justify every tolerance in the units of the
decision it serves, not the units that happen to be convenient. Seal the thresholds *together with
the code that grades them*, so neither can drift. Route every change through a log recording what was
already known at the moment of the change. Prove each grader's score rises as the thing it measures
gets stronger, and build specific attacks for the specific ways it could be gamed. Have someone else
reproduce every artifact and characterise every failure before anyone reads a verdict. Compute in
advance whether a correct answer could even pass; when it couldn't, fix the test rather than buying
more computing. And when a sweep offers a hand-tuned setting that passes everything, publish it and
refuse it.

None of that is specific to economic decades. It would work on a climate model, a drug trial
pipeline, or any simulator whose realism is currently a matter of taste.

What *is* specific is the finding that when you actually do this, the interesting results come back
in the wrong direction. The mechanism we funded and built proved inert. The test we were proudest of
passed through a channel we hadn't built. The headline hedge number was measured backwards by
forty-seven standard errors. History itself would fail three of the bars cut from history.

Those are the results we consider the contribution. The apparatus is what made them sayable —
and, more to the point, what made them unavoidable.

---

*Not investment advice.*
