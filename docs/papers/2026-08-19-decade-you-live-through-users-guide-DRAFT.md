> **DRAFT — pending owner edits.** Not reviewed, not released, not citable outside this repository.
> **Date:** 2026-08-19.
> The user's guide to the world generator: what a generated decade is, what the player controls, and what the engine refuses to do. Companions: `docs/papers/2026-08-19-economic-realism-engineering-quantity-DRAFT.md` (the working paper) and `docs/papers/2026-08-19-twenty-decades-plain-DRAFT.md` (the plain-English account).

---

# The Decade You're About to Live Through

*A user's guide to the world generator: what it makes, what you control, and what it refuses to
do. Not investment advice.*

---

## 1. What a generated decade is

You are about to take the seat of an institution and live through ten years that never happened.

A generated decade is 120 months long. It has **one economic story** — inflation runs somewhere,
growth turns somewhere, policy responds, the yield curve does what the policy rate makes it do.
Underneath that story sit **real market months**: every equity return, bond return, commodity return
and credit spread you will see is a verbatim month of actual history, played back exactly as it
happened. Nothing is synthesised, scaled or smoothed. The slogan to carry is **real months, invented
sequence, declared severity.**

That combination is what the decade is *for*. Two jobs, and they are different.

**Training allocation judgment.** A committee learns its trade from the decades its members have lived
through, and that is a classroom of one. The usable monthly record of the American economy runs April
1953 to December 2020 — **813 months** — containing **seventeen** starts of a recession or crisis and
only **six** genuine crisis events. Sixty-eight years of the most heavily documented economy on earth
yields seventeen of the events that matter. It also makes the numbers you would quote without
hesitation softer than they look: resample that record and the honest range around "a recession lasts
about three months" is **one to twelve and a half months**. So: rehearse the same institution through
twenty coherent decades instead of one, and see which choices survive all of them.

**Stress-testing a real book.** You can also enter an institution's actual opening portfolio and
commitment plan and run *that* through the same worlds. The question then is the supervisory one:
*could this book survive this?* Commitments land as capital calls that must be paid in cash, and if
liquidity runs out you sell something at a discount in a month you did not choose.

### The boundary, stated once

**A generated decade is never a forecast, and nothing in it licenses a statement about what will
happen.** These worlds are *prescribed*, not predicted — declared stress scenarios in exactly the
sense a supervisor's severely-adverse scenario is one: severe, internally coherent, precedented, and
nobody's view of the future. Every world ships with the tagline *"a declared stress scenario, not a
forecast."* So the right question of your decisions is never "was I right about this world"; it is
**"is this allocation robust across the decades this machine can build?"** Judge yourself on the
spread across a batch, not on one outcome. And carry the project's standing caveat: nothing built on
this generator line is a convincing model of history, and nothing here is decision-ready.

---

## 2. The framework: three layers, and the dials you hold

The mental model is **climate, seasons, weather** — three stacked layers, each choosing the
conditions the next one runs in. Everything you see on screen is one of these three things.

### Layer one: the slow climate

Underneath a decade sits a slow-moving backdrop with five dials: the long-run drift of **inflation**;
the **neutral real interest rate** (the one that neither stimulates nor restrains); the **trend rate of
growth**; how **expensive equities** are; and how **stretched credit** is. These move over years, not
months, and each decade begins by drawing one plausible set of them. This is where a world gets its
personality — expensive and levered with inflation already drifting up, or cheap and calm with room to
run. Two decades from the same instruction can start in genuinely different climates, which is why a
batch is more informative than any one run.

### Layer two: the four seasons, and why they turn

On top of the climate runs a monthly clock. Every month sits in one of four boxes, decided by two
yes/no questions: *is the economy expanding?* and *is inflation hot?*

|  | inflation cool | inflation hot |
|---|---|---|
| **expanding** | recovery | expansion |
| **contracting** | recession | stagflation |

"Hot" means trailing inflation above **3.35%** — not chosen for taste, but the historical panel's own
dividing line, so the identical rule sorts real months and generated months alike.

The natural clockwise order is **recovery → expansion → stagflation → recession → recovery**. Each
step changes exactly one of the two answers: the growth dial and the inflation dial take turns. That
is why "do the seasons turn in the right order" is really a question about whether the two dials *keep
time with each other*.

**The seasons do not run on a timer.** They are wired together, and the wiring was estimated from
data rather than set by hand:

> growth feeds inflation with a lag → policy leans against both the inflation gap and the cycle →
> the policy rate sets the yield curve → and the curve feeds back into whether growth turns, **nine
> months later**.

The nine-month lead is a finding, not a setting: it was selected by maximum likelihood on a pre-declared
grid of every lag from zero to twenty-four months, beating its nearest rival by 2.8 log-likelihood
points. On this panel the curve leads the turn by about three quarters — and because that arrow has a
genuine lag, each month is computed from months already settled, with no circularity to unravel.

**Downturns arrive by dice roll, not by schedule.** The machine takes the historical frequency with
which corrections started from the conditions the world is currently in, and rolls: *"the machine does
not predict them. It reproduces the statistics of their preconditions and rolls dice."* So **two
decades from the same instruction differ in when — and whether — a second shock lands.** A repeat
player cannot learn a timetable.

*Two kinds of world.* In a **generated** world, layers one and two produce the storyline; in a
**declared** world it is written out quarter by quarter as an authored premise plus a severity rule,
cited to precedent. Layer three is identical either way, which is why one framework describes both.
Your library today holds the declared ones — the Gulf Decade, the Long Squeeze, the Lost Decade, the
Hard Landing. And "season" is the framework's vocabulary, not a label on screen: the app shows you
*conditions* — "the macro state the world is generating".

### Layer three: real months as the market texture

The top layer never invents a market month. It **selects** them, verbatim: when the storyline says
"this is a hot-inflation contraction, and a severe one," the machine finds real months that were
exactly that and plays their actual returns. The rule, carried unchanged through every round of
work:

> **the story chooses which real months are drawn, and never edits, scales or invents one.**

The most useful consequence for an allocator: **within any stretch of a decade, cross-asset behavior
is genuinely historical.** A stagflation run really behaves like stagflation — the equity–bond
correlation flip, the commodity lead, the credit spread widening in the same weeks the equity
drawdown deepens — because those months *are* stagflation months and they arrive whole rows at a
time. You are not looking at a correlation matrix someone specified; you are looking at what actually
co-moved.

Two prices. A **hard severity ceiling**: the worst rolling twelve months a generated decade can produce
is history's own worst twelve, **−42.6%**; the machine cannot show you what the record never showed,
and the remedy — other countries' records — is licence-blocked. And the decade has **joins**, the one
place the texture is not history's own (§4).

### The dials you control

**Premise — what shock, and when.** A premise is a typed object with four fields, not free text:
**shock** (`supply` or `financial` — no demand shock; the vocabulary is deliberately minimal),
**arrival quarter**, **backdrop** (`inflation above trend` or `benign`), and **recovery shape** (`slow`
or `normal`). Each field is an *acceptance condition* on the climates the machine draws, not an
instruction it obeys: "inflation above trend" means drawn trend inflation must sit at least half a
point above its own mean; "slow recovery" means at least 24 contraction months. *It changes* the shape
of the story; *it cannot change* the market months — a premise selects, it never authors returns. And a
premise you can state is not automatically one you can get: an unfillable one comes back as **a refusal
naming the clause that failed**, because history never did that. A refusal is information.

**Backdrop — what world the shock lands in.** The same shock is a different decade depending on what it
hits. This is a pre-registered three-row table, and the *only* place the world's state touches
severity:

| the world's state when the shock fires | how much deeper | how much longer |
|---|---|---|
| inflation at or below trend, credit gap low | the declared baseline | baseline |
| inflation above trend **or** credit gap high | one stratum deeper | one quarter longer |
| inflation above trend **and** credit gap high | two strata deeper | two quarters longer |

Three rows, auditable in one glance — a rule you can read, not a formula buried in code. One stratum
halves the entry percentile, floored at 5%.

**Severity — how hard.** Severity declares **how to sample**, never what should result. Two parts, both
declared per segment. The **entry percentile** says how deep the pool is — a three-rung ladder: **10**
(the worst decile, "the severe rung"), **35** (the worst third, "the squeeze"), **100** (unrestricted).
The **functional** says what "worst" means:

| functional | ranks months by | the scenario it expresses |
|---|---|---|
| `equity` | equity return alone | a pure market crash; bonds may rally |
| `joint_risk` | equity down *and* credit widening | a credit-led break |
| **`all_down`** | the worst simultaneous move across equity, credit *and* bonds | **no hiding place** |

Every shipped stress world uses `all_down`, on the stated reasoning that *"flight-to-quality is the
escape valve a stress test must be able to close."* Beside these sits **block length** — how long a
drawn stretch of real history runs before the next join, six months in the shipped worlds — and the
measured finding is that it, not the percentile and not the functional, is *"the coherence dial."*

"Crisis quarters draw from the worst decile" is a severity rule; "equities should fall 40%" is not, and
the system cannot express it. Depth is an **emergent consequence, measured after the fact**. That
carries the product's most important guarantee:

> **Severity never reads portfolio outcomes.** No threshold in the world generator or its acceptance
> tests may be adjusted because of what it does to a book's returns, drawdowns or score.

This is a construction, not a promise. The two acceptance tests that touch allocation are defined on
**asset returns** and never on a book's outcome, because an asset-level test cannot be tuned toward a
portfolio result without the tuning showing up as a change to a published historical number. An earlier
draft proposed calibrating severity until the institution broke in a declared fraction of runs, and it
was refused as circular: *"a world tuned until the book breaks, followed by the discovery that the book
breaks. Any conclusion would have been guaranteed by construction."* If a scenario disappoints, the
permitted response is to re-examine the rule against precedent — never to dial until it passes.

Severity also cannot reach past the entry: it restricts only which month a block may *start* on, and
from there the tape runs forward through real history unfiltered — the aftershocks, the policy response,
the partial recovery that actually followed. A month-by-month filter would give you a bag of bad months
in shuffled order: noise with a severe average, not a crisis.

---

## 3. How a decade evolves: the Gulf Decade

Take the shipped canonical example. **The Gulf Decade** is a declared stress scenario: escalating
military action in the Middle East disrupts oil supply into an economy *already running hot*. Its
lesson line states the point:

> *"An oil shock does not need a cold economy to be dangerous — arriving on top of inflation that is
> already running hot removes the policymaker's usual room to look through it."*

Its declared backdrop is 8% average inflation peaking at 12.5% in quarter 9, the policy rate running
6.5% to 9.5%. Its precedent is cited inline, so you argue with it on history rather than on the
sampler: 1973–74's embargo, which ran **−48% over 21 months** with inflation above 10%; 1990's Gulf
spike; and 1979's second oil shock, the stated reason the *grind* is dialled to the severe rung rather
than only the shock quarter.

**Years 1–2: it opens hot.** The world starts in **stagflation**, drawing from the worst third of
history. There is no calm opening act. The clock reads YEAR 1 OF 10 and advances a quarter at a time,
and each release brings the *prints* — a **monthly economic release** carrying CPI inflation and the
high-yield spread, each with its prior and its revisions, plus a quarterly **statement on monetary
policy** — arriving on a **wire** tagged DATA RELEASE, CENTRAL BANK, THE MARKET RECORD, FORCED SALE.
What is happening to you quietly is pacing: commitments made now decide whether you have cash in year
five.

**Year 3: the crisis quarters.** The declared rule shifts entry to the **worst decile**. Note the
functional this world declares: **`all_down`** — the 2022 precedent, equities and bonds down together,
*with no flight-to-quality bid*. This is where the conventional defence is explicitly removed. The
months arrive as whole rows, so the drawdown, the spread blowout and the policy response come in their
true relative sizes. The private book now moves in four directions at once:

- **Infrastructure** carries contractual escalators — the strongest hedge in the book by design, and
  its pass-through is not a guess: it is read live from the world's own declared share of
  inflation-linked revenues. A world writing 85% gets 85%.
- **Real estate has two sides that fight.** Income escalates; cap rates reprice against the higher
  discount rate. Escalation wins on net, but only just, and the repricing lands first.
- **Private credit floats.** Coupons reset up with the policy rate — then a loss-rate uplift and spread
  convexity claw it back, so on net high inflation is *negative* for the sleeve.
- **Private equity gets squeezed.** Nominal revenue growth helps; multiple compression hurts more.

None of it is fast: the channel runs off a **24-month trailing average** of inflation against a 2%
anchor, because that is how long these things actually take.

**Years 4–8: the grind.** The world returns to **stagflation and stays there for five years**, still
entering at the worst decile. This is the persistence decision made visible: twelve severe months inside
an otherwise-normal 120 is a bad year inside an acceptable decade and will not exhaust a liquidity
programme; a sustained decade will. Watch the policy chase in the prints — the rate climbing toward
9.5%, the curve flattening and inverting. An inverted curve here is a real signal about the *next three
quarters*, at about history's own strength: a one-standard-deviation flatter curve nine months earlier
multiplies the odds of an expansion turning by roughly four and a half, and the mirror holds. It is not
a signal about next month, and the system is built so that guessing next month cannot be rewarded.

Play is quarterly; decisions are annual. Once a year the tape stops — *"the window is open. Time is
stopped. Nothing moves until you commit."* — and you have **four levers**: **hold course** (rebalance
to target: *"a commitment, not a shrug"*), **de-risk** (10 points out of equities and private equity
into bonds and private credit), **lean in** (10 points the other way), or a **secondary sale** (up to
8 points of private equity at an 18% discount). You also set next year's commitments per sleeve,
warned plainly: *"cuts starve distributions years out, raises call capital you must fund."* And:
*"Decisions are final. The server will hold you to this."*

Beside the levers sit your **policy bands** — each sleeve's weight against target and range, badged
**ok / watch / breach** by the server, reporting only: nothing rebalances to a band on its own. Two
switches matter. One flips your book between **as reported** (appraised, smoothed private marks) and
**as true**; that gap is the appraisal lag, and it is what the grind punishes. The other opens the
**CIO dashboard**, whose Liquidity tab carries the number that decides this decade: **coverage —
unfunded commitments over liquid assets**. Three things now bite together: the denominator falls so
your private weight drifts up on its own; calls keep arriving on year-one commitments; and
distributions dry up exactly when you wanted them. The forced sale, if it comes, is not a choice you
make — it is a consequence you already made, in a calmer year.

**Years 9–10: the uneasy unwind.** The world moves to **recovery**, entry easing back to the worst
third. Recovery does not arrive on a timer, and it lasts about as long as recoveries actually last
inside a ten-year window — a property that sank three previous versions of this machine, and is now its
most reliably passed test (§4).

Then the world reports what its rule actually produced — emergent depth, coherence, a plausibility
statistic — and you reach **the reckoning**. Throughout, one panel has shown your world against **the
middle half of its 1,000 siblings**: same rule, different seeds. That fan is the honest picture of what
your decade was — one draw, not the answer.

---

## 4. The world's credentials: what "this world passed its exam" means

Every world carries a **report card**, unusual in one respect: **the questions were written before the
machine that answers them existed.** Twelve pass/fail tests, each anchored to a measured historical
quantity with its tolerance justified in writing, were sealed — thresholds *and* the code that grades
them, hashed together — before any engine work started. The governing sentence: *"a threshold chosen
after seeing results is not a test, it is a description."*

**The engine passes nine of the twelve.** The headline four, in your terms:

**Seasons turn in order.** The clockwise fraction reads **0.5608** against a floor of **0.5181** — the
lower edge of history's own 95% interval, not history's point value, because an engine whose ordering
exactly matched history's would fail a point-value bar about half the time, and *"a bar that a correct
engine fails one time in two is not a test of the engine."* This bar had never passed anywhere it had
ever been measured.

**Seasons last true lengths.** Recession, stagflation, recovery and expansion medians all land inside
bands set at **±1 quarter** around history's decade-window medians — recovery, for instance, at four
months against history's five, inside a band of two to eight. The quarter is not a statistical choice:
it is the smallest unit the product lets you act in, so grading finer would score a distinction you
cannot trade on.

**Tightening bites, at 2.2×.** In real history, when the curve is inverted, a downturn is about **2.37
times** more likely to begin over the following year. In the generated worlds it is **2.24 times**,
against a permitted band of **[1.78, 3.35]**. The band is wide, and honestly so — it is what seventeen
downturn events in sixty-eight years support, and no better estimation could tighten it. What it does
exclude comfortably is 1.0, so an engine in which tightening told you nothing would fail.

**Declared severity provably binds.** Run the same worlds against books holding 15%, 35%, 40% and 55%
in private assets and liquidity strain must rise monotonically, with at least one seed in twenty
breaching at the most over-committed arm. It does: coverage medians **[0.10, 0.29, 0.36, 0.67]**, with
**4 of 20** breaching at 55%. If this test failed, every score would stop meaning anything and
over-commitment would be free.

### The failures, which you should read as properties

**In stress-heavy decades, the classic commodity hedge can fail.** On the whole historical record,
commodities out-earn bonds when inflation is high by **+4.87 percentage points a year**. In these
worlds, measured across **25,700 decades**, they do not — the margin is negative and precisely so. Not
a defect: the most useful thing the exercise produced. The cause is severity conditioning. Split the
pool these worlds draw from by inflation, using nothing but real months:

| where the months come from | high-inflation months | commodities minus bonds |
|---|---|---|
| the whole record | 225 | **+4.87 %/yr** |
| the worst 10% by severity | 59 | **−8.52 %/yr** |

> **The severe months of history are flight-to-quality months: bonds win and commodities lose,
> whatever inflation is doing.**

That is a statement about the months when everything goes badly at once, not about commodities as an
asset class — and it is what a stress instrument should be teaching. If your inflation defence is sized
on the whole-record relationship, these worlds show you the population where that relationship reverses.
(A world declaring `all_down`, like the Gulf Decade, removes the bond leg of the defence too.)

**The yield curve is too determined by the economy.** It fails from *above*: **77%** economic content
against a permitted band of **39% to 67%**. A real curve carries genuine surprise no macro state should
explain; this one carries too little. So do not treat the curve here as independent information beyond
the macro state you can already see.

**The seams are findable; the texture is not.** Decades are assembled from blocks averaging six months,
so they have joins, and a trivial detector — look for a big jump in trailing inflation — spots those
joins with **45 to 49 percentage points of advantage** over guessing. The months *inside* a block pass
their test at both measured quantiles: *"whatever is wrong with these worlds, it is not their
within-block texture."* So what is exam-certified is precise: **the texture inside a stretch is
certified; the transitions between stretches are not.** Joins are constrained — in the Gulf Decade the
high-yield spread may not jump more than 1.5 points and the policy rate more than 1.0 point at any seam
— but constrained is not invisible. The fix is known and deliberately unmade: it would invalidate the
sealed comparison the record rests on.

### One caveat riding on every report card

**A marginal pass is not a finding.** Six tests are measured on months a classifier sorted into four
boxes. Nudge the two classifying lines by half a percentage point and re-measure *history itself*: for
the recession, stagflation and recovery length tests, **the real record would fail the bar cut from the
real record.** No band was changed as a result — re-cutting a bar from a sensitivity result is what
sealing exists to prevent — but a test passing by a hair should be read as a hair. And "nine of twelve"
is a statement about these twelve tests only: four had never been run before.

---

## 5. What the scores mean, and what the simulator refuses to do

### The score is a comparison against a twin

The reckoning shows three figures: **you**, the **policy twin**, and your **decision alpha**. The twin
is an identical institution, in the identical world, that followed the written policy and never
flinched — *"same world, same shocks, only the decisions differ. The twin paces its commitments to
policy and never sells by choice."*

That separates **structure from luck**: everything that happened *to* the world happened to both of
you, so what is left in the gap is what you did. It is the difference between judging a poker player by
one hand's winnings and judging them by how they played the cards they could see. The review then
decomposes the gap window by window — *"the value of the decision given everything decided before it
and mechanical policy after it"* — and the lines sum exactly to your alpha.

**Comparisons are within-world only.** A score from one world does not compare to one from another,
because worlds differ in how hard they are, deliberately. This is enforced structurally: a board is
keyed on the triple **(world, seed, scoring version)**, so scores from different histories or different
alpha definitions can never share a table. And that identity is checkable rather than promised — the
same seed produces the same world bit for bit, forever, and the packaged world carries a seal your own
browser re-checks. Because shock timing is a dice roll, one decade also carries a lot of noise: read a
policy across a batch, not across one seed.

**Everything runs as practice right now.** Ranked play is parked by owner ruling. Two reasons worth
knowing even after that changes: a ranked ladder only means something if every entry faced the same
starting position, so entering your own opening book or plan demotes the session to practice — enforced
by the server, not the app; and an entered book can sit far outside the staggered vintage shape the
pacing model was fitted on, so its cashflow behaviour is less trustworthy than the default book's.

### What it refuses to do

**Predict.** No world is a forecast and no batch is a distribution over the future. The one number
speaking to plausibility — a statistical distance of the assembled decade against the historical record
— is **reported with every world and never gated on**, precisely so it cannot be mistaken for a
probability.

**Rank across firms.** There is no cross-institution league table; two institutions with different
books, liabilities and worlds have scores that are not on the same scale.

**Produce a forecastable answer.** There is no schedule to learn, no lever whose timing is the trick,
no "correct" allocation being withheld. The stated purpose is explicit: *the product tests robust asset
allocation, not lever timing — a player should be rewarded for holding a portfolio that survives a
range of futures, not for guessing when a central bank moves.* If you find yourself trying to time the
shock, you are playing a game the instrument was designed not to have.

**Narrate causality it does not contain.** A world's copy may say what its rule declared and what its
months did, and no more. The related discipline: *severity is estimated; incidence is curated — and the
two never merge.* How bad a shock is, is measured from history; whether it happens is a human
declaration, and the product will not dress the second up as the first.

Which leads to the one boundary to carry out of the room:

> **Lessons about institutional mechanics transfer; lessons about market judgement do not.** These
> worlds are built to exercise liquidity, pacing and the appraisal lag. They are not evidence about
> anyone's ability to time a market.

---

## 6. How it was built, in brief

The full construction story is in the two companion papers — a working paper on the measurement
apparatus, and a plain-English companion. Only its shape belongs here. The three layers, made concrete:
a five-state linear-Gaussian macro model for the climate; a monthly coupled system for the seasons
whose growth chain, inflation gap, policy deviation and yield-curve equation were fitted inside **one
likelihood**, so every "no coupling" restriction is an exact statistical test rather than an argument;
and a selection layer drawing verbatim real months. In one honest sentence: a conditioned block
bootstrap whose incoherence has been *measured* rather than assumed away.

The part the project considers its real contribution is the exam, not the engine. Twelve bars were
written with their historical anchors, sampling intervals, power calculations and justifications
**before the engine existed**, then hashed together with the code that judges them. Every new judge had
to survive an **anti-test** proving its own pass rate rises as the thing it claims to measure gets
stronger — adopted after an earlier round shipped a clean failure from a test that was mathematically
unpassable by any model, including a perfect one. Every verdict then went through **independent
reproduction**; those reviews regenerated the artifacts byte-identically, found no number or verdict
wrong, and returned interpretive corrections of which the reviewer noted that eleven of twelve leaned
the same way — *they made the work look better than the evidence supported.* Two bars were thrown out
before results existed for being unfair to a correct engine, and one hand-tuned setting that would have
passed everything was found, published, and refused.

That discipline is why this guide can tell you the commodity hedge fails in stress-heavy decades, the
curve is too determined and the seams are findable — and why you should believe those statements about
as much as the four passes above them. The apparatus exists to make the inconvenient results
unavoidable, and its authors' own summary is that the interesting findings came back in the wrong
direction.

---

*Not investment advice.*
