# METHOD.md — what has been built, and by what method

*The current account, as of 2026-08-15. Descriptive: it records what exists and
how it came to exist. It is not a plan, a proposal, or a specification — the
authoritative plans live in `Instructions/` and the contracts live in
`schemas/`, and where this document and an evidence document disagree, **the
evidence document wins**.*

*Every number and every verdict below is quoted from a committed record in this
repository. Where something has not been measured, this document says so rather
than estimating it.*

---

## 1. What the platform is

A flight simulator for long-horizon investors. It builds counterfactual economic
decades and puts the reader in the seat of an institution living through one:
markets move month by month, capital calls arrive and must be paid, news lands
as a wire feed, and once a quarter a decision window opens; commitments form
annually and lock at year-close (D-QC-1, 2026-08-20). At the end the player
is scored against a **twin** — an identical institution in the identical world
that followed written policy and never flinched. The gap between player and twin
is the value the decisions added or destroyed.

The design property everything else rests on: **the same seed always produces
the same world, bit for bit.** Runs are recorded with a cryptographic digest,
records cannot be edited after the fact, and `ah replay` re-derives any past run
and confirms it matches.

## 2. The turn that defines the current method

Until 2026-08-14 the platform's worlds were attempts at *plausible futures*. They
are now **declared stress scenarios**, and the difference is the single most
important thing to understand about the current method:

> We stopped asking the generator to predict and started asking it to
> **prescribe**.

A stress world is a declared, severe, coherent decade — **real months, invented
sequence, precedented severity rule** — built to answer *could this institution
survive this?* rather than *how likely is this?* That places the work alongside
supervisory stress testing (a CCAR severely-adverse scenario is not a forecast
and nobody pretends otherwise) rather than alongside forecasting.

The claim is worded narrowly on purpose. Every month is a real historical month,
bit-exact; the *sequence* is assembled; and precedent for the parts is not
precedent for the whole. What carries the whole is the declared rule with its
cited precedent, plus a measured plausibility statistic (a Mahalanobis distance
of the assembled decade against the historical record) **reported with every
world and never gated on**.

**Why the turn was forced, in arithmetic rather than taste.** The historical
panel runs 1953–2020. Of its 813 months, 38 carry the "crisis" label, averaging
−1.79% on equities. A world declaring four quarters of crisis therefore drew
roughly 12 × −1.79% ≈ **−19.5%** — and a 20% drawdown exhausts nobody's
liquidity, which is why forced secondaries fired in **0 of 20 seeds**. The flaw
was using a *label* as if it were a *severity*: "crisis" is a classification
containing both October 2008 and months that merely satisfied the rule. Ranking
by severity instead reaches the depth required and draws on **more** real
material, not less — 82 to 163 eligible months rather than 38.

An attribution study ran down the three portfolio-side defects live in the same
period and cleared all three, so the gap is genuinely in the markets and not in
the machinery.

The full statement of the rules, the limits and the measurements is
`docs/current/stress-scenario-methodology.md`; the design is
`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md`.

## 3. What has been built

Dependencies point downward only: `port` / `gen` / `eval` / `artifacts` →
`data` → `core`.

**The numeric core and the rails** (Step 0, gate G0 passed, `v0.1.0-g0`). The
WorldSpec contract and its validator (V1–V12), a deterministic engine, append-only
stores for worlds, run records and the chronicle, an offline compiler harness and
a CLI proving `compile → validate → run → record → replay`. `ah/core/engine.py`
runs `toy-v0` worlds only and refuses any other `generator_id` by design.

**The data layer** (Step 1, `v0.2.0`). Roughly a century of real economic and
market history kept as an **immutable Parquet vintage store** over a DuckDB
catalog: re-writing a (vintage, series) raises, the `current` pointer is
append-only and advances only if QC passes, and `as_of` reads resolve through
pointer history. Connectors split `fetch()` (network) from `parse()` (pure,
golden-tested). Series extended backward carry `is_proxy` flags row by row, and
actuals are never overwritten. De-smoothing corrects the appraisal lag in
private-market series before anything is calibrated on them.

**The generator layer** (Step 2, gate G2 taken, `v0.2.0-g2`). Two world-makers:

- the **collagist** (`bootstrap-v1`) — a block bootstrap that cuts real history
  into strips and splices them into new sequences, so everything it produces is
  rearranged truth;
- the **apprentice** (`hier-flow-v1`) — a four-layer hierarchical generator that
  learned history's patterns and can paint decades from scratch.

Three sealed contests decided between them. G2 promoted the apprentice; the
second campaign promoted it again on richer data; the **third campaign
(2026-08-11), on the full 1953–2020 span, reversed the verdict** — the
apprentice's edge was smaller than its own run-to-run noise, which under the
sealed rule is not a win. A fourth contest was designed and then deliberately
**not run**: a pre-seal gate of cheap diagnostics (~85 minutes of compute) found
that the model's scenario obedience was skin-deep and that its edge and its
tail-exaggeration were the same knob, and returned NO-GO on 2026-08-14. The
apprentice is shelved with three named numbers that must move before it reopens.

**The collagist is the generator of record.** The standing sentence: *rearranged
truth now; invented worlds only when earned.*

**The stress compiler** (`src/ah/gen/stress.py`, 2026-08-14). Severity ranking of
historical months under three functionals — `equity`, `joint_risk`, and
`all_down` (the default, which closes the flight-to-quality escape valve). A
world declares an `x_stress` spec — functional, segments, join tolerance, and
the **precedent cited inline** — and the compiler assembles real months to match
the declared rule. Severity restricts only which month a block may *start* on;
from there the tape runs forward through real history unfiltered, so
autocorrelation is inherited rather than modelled.

**The translation layer** (Step 3 — see §6, its gate is an honest FAIL). Turns
market paths into an institution's actual books, and keeps *two sets* of them:
what the portfolio is truly worth, and what this quarter's statement claims. It
runs the private-markets machinery — commitments, calls over years,
distributions, and the liquidity cascade that sells liquid holdings first and
then forces a discounted sale of private assets. A forced sale is a consequence,
not a button.

**Artifacts and actors** (Step 4, gate G4 closed, `v0.4.0-g4`). The decade as
news: a deterministic rules-based writer, and an AI writer on a leash where every
claim is checked against the world's actual numbers and anything unverifiable is
blocked. **No LLM output ever enters the numeric path** — the engine consumes a
projection that structurally omits `narrative`, and a test enforces it.

**Decision evaluation** (Step 5). The policy twin, the drift twin, per-decision
attribution that sums exactly to the final score, re-coning, tournament and
walk-forward. This layer spent the project's one-shot holdout (§6).

**The product surface** (the live track). The world bundle
(`world-bundle-0.3`, <1MB gz), the in-timeline wire, the FastAPI session
service — **the authority for anything that scores** — the credibility console,
and the React player. Since 2026-08-14 the **CIO dashboard is the play surface**;
`Book` and `PrivateMarkets` have retired into it.

## 4. The method — the disciplines that govern

These are not aspirations; each has a mechanical enforcement, and most were
learned by something going wrong.

**Seal the rules before running the race.** Thresholds *and the code that judges
them* are hashed together before any training run; amendments go through a
machine-checked log. This is what made the 2022 failure meaningful, what forced
an invalid scoring run into the open, and what let the third campaign's upset
verdict be accepted without argument.

**Declare the rule, not the outcome.** A scenario declares *how to sample* and
never *what should result*. Depth is an emergent consequence, measured and
reported after the fact. The alternative is circular: tune a world until the book
breaks, then discover that the book breaks.

**Commit the rule before you measure the consequence.** The scenario is committed
first; the institutional run happens in a later commit. Git history is the
pre-registration, and it costs nothing. If a scenario disappoints, the only
permitted response is to re-examine the rule against precedent.

**Reconstructed data may be used to judge, never to teach.** Two
otherwise-identical apprentices were trained, one fed statistically reconstructed
pre-1986 volatility and one denied it. The one trained on **57% less data** did
better. Feeding a model your own model's output teaches it your reconstruction,
not reality. This is the single clearest methodological lesson the project has
produced.

**Measure before you commit.** When a commitment is expensive and a measurement
is cheap, the measurement goes first, and the commitment's budget is pre-declared
so sunk costs never renegotiate it. This converted a two-week sealed contest into
a same-day NO-GO with better evidence.

**A gate that cannot fail protects nothing.** Several engine defects sat
unnoticed for weeks because the checks that would have caught them had
thresholds still marked "to-do". An unenforced check is worse than no check,
because it reads as a green light.

**A test that pins numbers can entomb a bug.** Golden tests assert that numbers
*don't change* — determinism, not sense. A deterministic bug passes them forever.
The appraisal-smoothing defect survived four review gates behind green suites
because every test asserted stability and none asserted the economic invariant
that mattered. The costliest bugs are missing-invariant bugs.

**A written warning nobody must answer is a warning nobody answers.** An
estimation report flagged its own weakness and deferred adoption to an owner
decision; the artifact was consumed anyway and the warning sat unread for weeks.
Warnings must be routed to a decision point that blocks.

**Publish the failures.** The 2022 rehearsal failed, the holdout exposed an
inflation blind spot, and the in-house model lost to the simple one. Each is on
the record, and together they are the reason the passes are believable.

**Mechanically enforced, not remembered.** Determinism flows from one integer
seed through `numpy.random.Generator(PCG64(seed))` — no global RNG, no
time-based defaults. The holdout was reachable only through a token minted in one
module, proven by an import-graph test. A citation checker verifies that every
file a living document names exists. Merging into `main` physically requires a
machine-validated green test log for the exact commit being merged — a hook, not
a habit, because a discipline that lives in memory fails under pressure.

## 5. Where it stands today (2026-08-15)

| | |
|---|---|
| Engine | `toy-v0.6` |
| Generator of record | the collagist, `bootstrap-v1`, over the sealed 1953–2020 panel |
| Shipped playable world | `stagflation_1974`, world `…603`; toy presets `511–514` |
| Declared stress worlds | `stress_1974` `…701`, `stress_1990` `…702`, and `…703` at 6-month blocks |
| Sleeve mappings | `v1.1` (`map-2026.08.2`) |
| Play alphas | `port-v4-ladder` / `port-v4-ladder-gen` |

**Three declared stress scenarios have been measured, each once, each after its
rule was committed.** `stress_1974` produced a median peak-to-trough of −29.9%;
`stress_1990` — the Lost Decade, implementing the owner's persistence ruling —
produced −30.1%, statistically indistinguishable, and recorded the finding that
**persistence-by-shape saturates**. The binding dial turned out to be block
length, not the percentile and not the shape. A generator-only coherence study
set 6-month blocks (the sealed benchmark's own setting), and at that length the
decade finally moved: median peak-to-trough **−37.5%** over 18 months, median
final value 154 on 100, two seeds in twenty ending below their start — with
coherence holding exactly as the study predicted.

**And the adequacy ladder still reads 0/20 coverage breaches and 0/20 forced
secondaries.** After three scenarios, each pushing the market side further on
precedent, the honest reading is that **the hold-course institution is genuinely
robust**: roughly seventy percent of the default book is liquid, and a −37%
decade leaves years of sellable assets between the institution and its private
commitments.

**The over-commitment measurement (E1) closed the argument.** Worst coverage is
monotone in allocation (0.10 → 1.57); a 55-point breach book produces the
programme's first coverage breach (1/20); forced secondaries remain 0/20
everywhere. The forced secondary is not the default book's event — it is the
*over-committed* book's event. The reference ladder shape that once described
4–8/20 forced sales is recorded as a **drafting artifact**, unreachable in
precedented markets at declared allocations, rather than quietly adjusted.

## 6. What is not true of it

**The standing caveat, carried into every decision.** `hier-flow-v1` beat the
benchmark on the sealed criterion and is **not a convincing model of history** —
regime persistence undercalled, drawdowns understated roughly two-fold, the
decade tier 73% structurally unavailable. **Nothing built on this platform is
decision-ready**, and every evidence document says so.

**Step 3's gate is an honest FAIL.** G1-completion recorded named limitations
with tier 1 beating tier 0; the 2022 rehearsal failed four-of-six with the model
unable to reproduce how slowly hedge funds marked down losses. **G3 itself was
never taken**, yet Steps 4 and 5 proceeded. "Step 3 is done" is not true.

**The holdout is gone.** Declined at G2 on purpose, then spent at WP5.6. The look
was revealing in both directions — the worst-case warning safely contained the
real 2022 drawdown, but the real inflation surge escaped the predicted range
*every single month*. There is no held-out data left to appeal to, which raises
rather than lowers the bar on not fitting to it retrospectively. A new reserve is
accruing and will not be read before 2029.

**No mechanism, and therefore no causal narration.** The stress compiler has no
reaction function and no causal structure. Terrarium properly has two compilers:
this one, and a premise compiler with full causal narration that is **not
built**. Hard rule: nothing built on the stress compiler may narrate causality it
does not contain.

**A ceiling set by the pool.** The worst rolling twelve months in the panel is
−42.6%, and both that ceiling and the thin material at the extreme come from
drawing on one country's record. The remedy — the international record — is
licence-blocked pending Counsel, with the JST non-commercial correction upstream
of it.

**Open realism items** (`docs/engine-realism-register.md`): ER-2 (no meeting
calendar, 25bp quantisation), ER-5 (crisis is a rectangular block), ER-8 (typical
months milder), ER-9 (single months larger than whole historical bear markets —
moot for collagist worlds, which are bounded by real months) and ER-13 (the CIO
dashboard's inherited decade is a simulated past scaled to the opening book's
NAV, not a reconstruction of the history that produced it). ER-1, ER-3, ER-4,
ER-6, ER-7, ER-10, ER-11 and ER-12 are closed. Each entry states what a fix
invalidates; every one of them is a release event and an owner decision.

**Also open:** the F5 calibration drift from the translation-layer audit (CTA
vol, PM betas short of prior, Gaussian PM residuals against the sealed SM-8),
recorded rather than fixed; and `linkage_shortfall` at 0.027, below its floor,
recorded rather than tuned.

## 7. Where to read next

| To learn | Read |
|---|---|
| the stress method in full, with its limits | `docs/current/stress-scenario-methodology.md` |
| every severity-producing mechanism and its falsifier | `docs/current/tail-register.md` |
| the narrative account of how the work got here | `docs/current/alternate-histories-audited.md` |
| what the game shows a player, and how to read it | `docs/interpretation-guide.md` |
| where the engine is faithful to plan but not to belief | `docs/engine-realism-register.md` |
| the detailed code inventory (as of 2026-08-05) | `docs/BUILD-SUMMARY.md` |
| how to drive the CLI (as of 2026-08-05) | `docs/USER-MANUAL.md` |
| what governs, what is record, and why | `docs/current/README.md` |

*Not investment advice — as every evidence document in this project concludes.*
