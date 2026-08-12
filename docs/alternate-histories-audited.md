# Alternate Histories, Audited

*Where the work stands, what it has taught us about how to do this well, and the
choices in front of us — before any new worlds are generated.*

**11 August 2026 · Written after the close of the third generator campaign.**
Published copy (same content, formatted):
https://claude.ai/code/artifact/c51a265d-95dd-4407-b1e2-b5b2ea40ee44

---

## The idea, in one paragraph

The platform is a flight simulator for long-horizon investors. It invents
plausible decades — economic histories that never happened — and puts you in the
seat of an institution living through one. Markets move month by month, capital
calls arrive and must be paid, the news lands as a wire feed, and once a year a
decision window opens: hold course, de-risk, lean in, or sell something at a
discount to raise cash. At the end you are scored not on whether you got lucky,
but against a *twin* — an identical institution in the identical world that
followed the written policy and never flinched. The gap between you and the twin
is the value your decisions added or destroyed. As the Step 5 companion puts it:
it is the difference between judging a poker player by one hand's winnings and
judging them by how they played the cards they could see.

## What has been built

### A machine room you can trust

Everything downstream rests on one property: the same starting seed always
produces the same world, bit for bit, forever. Every run is recorded with a
cryptographic fingerprint, records can never be edited after the fact (the
database physically refuses), and a replay command re-derives any past run and
confirms it matches. When a world is packaged for the game, it carries a seal
the player's own browser re-checks — so "nobody rewrote history mid-game" is
something the software proves, not something we promise.

### A real data foundation

Underneath the invented decades sits roughly a century of real economic and
market history — inflation, interest rates, equity returns, credit spreads and
more — kept the way a lab keeps a notebook. Every version of every series is
preserved; updates never overwrite the past; anything reconstructed rather than
observed is flagged as such, row by row. That last habit turned out to matter
more than we expected (see the third campaign, below).

### Two ways of inventing a decade

The platform has two world-makers. The first is a **collagist**: it cuts real
history into strips averaging six months long and splices them into new
sequences, so everything it produces is rearranged truth. The second is an
**apprentice**: a neural model that studied history's patterns and paints new
decades from scratch. The collagist can never imagine anything that didn't
happen; the apprentice can — which is both its promise and its risk. Three
formal contests between them are the platform's research spine.

### From markets to an institution's books

A market simulation is not an investor's experience; nobody lives through "the
equity factor." The translation layer turns market paths into an institution's
actual books — and, exactly like reality, it keeps *two sets* of them: what the
portfolio is truly worth, and what this quarter's statement claims. The gap
between the two — stale private-market valuations in a crash — is where much of
a real crisis story lives, and the game lets the player flip between the two
views at any time. This layer also runs the private-markets machinery: you
commit money, the funds call it over years, and distributions eventually come
back — unless markets are bad, when the calls keep coming and the distributions
dry up. If cash runs short, the simulation sells liquid holdings first and then
forces a discounted sale of private assets. A forced sale is a consequence, not
a button.

This layer holds the project's most instructive result: a rehearsal of the real
2022 downturn against criteria we sealed before writing the code. It **failed**
— four of six checks passed, but the model could not reproduce how slowly hedge
funds marked down their losses, and we published the failure with its diagnosis
instead of tuning it quiet. Under the rules we set ourselves, that is the
intended outcome of an honest test that doesn't pass.

### The decade as news

The numbers are honest, but nobody experiences a decade as a spreadsheet.
People experience it as news: a wire story about spreads blowing out, a
quarterly letter explaining a bad quarter, a central bank statement. The
platform writes these two ways: a rules-based writer that is deterministic and
boring but incapable of error, and an AI writer kept on a leash — every claim it
makes is checked against the world's actual numbers, and anything unverifiable
is blocked. The governing rule: the narrator must never invent a number. Boring
but honest beats fluent but wrong, every time. And structurally, no AI-written
word can ever reach the arithmetic that computes results — the engine literally
cannot see the narrative.

### Judging decisions, not outcomes

The scoring layer asks: given what was knowable at the time, across everything
that could have happened next, was that a good call? Every run has its policy
twin, and the post-game review prices each decision individually — "Year 4,
de-risked: −2.1 points" — with the parts summing exactly to your final score,
like a chess engine annotating a game. The layer also spent the project's
**one-shot holdout**: a slice of recent real history (2021–23) deliberately
locked away from all model-building, to be looked at once, under rules sealed in
advance. The look was revealing in both directions: the model's worst-case
warning safely contained the real 2022 drawdown, but the real inflation surge
escaped the model's predicted range *every single month* — exactly where its
documentation predicted it was weakest. Both results were published as-is.
There is no spare untouched data left; a new reserve is accruing and won't be
read before 2029.

### The playable game

A working single-player app exists end to end: pick a world, watch the decade
unfold, decide at each annual window, read the wire, flip between reported and
true books, and finish on an outcome card against your twin, with the
per-decision review and a leaderboard. The server owns every number that
matters; the browser renders and asks, but never computes a score it could be
trusted to fake. Today it plays on four hand-authored scenario worlds
(stagflation, goldilocks, reflation boom, deflation bust) produced by a
deliberately simple toy engine — which is precisely what the next piece of work
would change.

## Three contests

### 1 · The first race (late July 2026) — apprentice promoted

Five generator systems raced the collagist under rules sealed before training
began. One — the flow-based apprentice — beat it on the agreed test and was
promoted. The evidence document leads with its own disclosure list: the
deciding rule had to be corrected after results existed, the reviewer was not
independent, and the head-to-head was tilted *toward* promotion by a data-span
quirk. It also stated plainly that neither contestant was a convincing model of
history: both understated crash depths roughly two-fold, and the tier of tests
that would catch decade-scale error was three-quarters unbuildable.

### 2 · Richer data, same verdict (early August 2026) — apprentice promoted again

The factor set grew from twelve to fifteen real-world series, everything
retrained, and the apprentice won again — this time on every seed, cleanly. The
campaign's own footnote is telling: the first scoring run was declared invalid
and redone because the measuring stick had been built subtly wrong, and the tell
was the collagist "failing" a test it should pass by construction. A result
that looks wrong in your favour is a bug until proven otherwise.

### 3 · The full span — and an upset (10–11 August 2026) — keep the collagist

This week's campaign extended the training record back to 1953 — 68 years,
stagflation included — and retrained the whole family. On the fuller record
**the collagist won**. The apprentice's average edge was smaller than its own
run-to-run noise, which under the sealed rule is not a win. The verdict: the
collagist, resampling real 1953–2020 history, is the generator of record.

The campaign also ran the platform's harshest exam for the first time: delete
the entire 1970s from a generator's memory and ask it to imagine 1966–84 from
the 1965 starting point. Both contestants passed every check. And it surfaced
the campaign's real discovery — the finding about our own reconstructed data,
below.

## What this has taught us about method

**Seal the rules before running the race.** Every contest's pass/fail criteria
— and the very code that judges them — are cryptographically frozen before any
training run, so nobody can tune the test after seeing answers. This sounds
like ceremony; it repeatedly proved to be the load-bearing wall. It's what made
the 2022 failure meaningful, what forced the invalid scoring run into the open,
and what let this week's upset verdict be accepted without argument: the rule
fired, the answer stood.

**Never train a model on your own reconstructions.** Pre-1986 equity volatility
doesn't exist as observed data, so we had reconstructed it with a statistical
model — dutifully flagged, row by row. This campaign trained two
otherwise-identical apprentices: one fed those reconstructed months, one denied
them. The one trained on *57% less data* did better. Feeding a model your own
model's output taught it your reconstruction, not reality. This is now a
standing rule — reconstructed data may be used to judge, never to teach — and it
stands as the single clearest methodological lesson the project has produced.

> A published failure has been worth more to this project than any pass. The
> 2022 rehearsal failed, the holdout exposed the inflation blind spot, and this
> week the in-house model lost to the simple one — each is on the record, and
> together they are the reason the passes are believable.

**A gate that cannot fail protects nothing.** Several engine defects sat
unnoticed for weeks for one reason: the statistical checks that would have
caught them were wired up but their thresholds were all marked "to-do" —
nothing was actually looking. The lesson is now institutional: an unenforced
check is worse than no check, because it reads as a green light.

**Simple beat clever — so aim the test at what you actually value.** After
three campaigns, cutting-and-splicing real history beats the neural models on
the agreed measure. In hindsight that measure — statistical resemblance to
history — is one a resampler of history is nearly unbeatable on *by
construction*. The apprentice's genuine promise is what the collagist
structurally cannot do: answer "what if" questions about conditions history
never produced. Any future contest should judge exactly that, or it isn't worth
running.

**The remaining weak point: claims nothing checks.** The first campaign's
review found the same class of defect seven times in three days — a sealed
document asserting something no code mechanically verifies. The cheap fixes
(automated citation checks, sealing-coverage tests) are named in the evidence,
and none has yet been built or assigned. This is the project's known governance
debt.

## Known weaknesses, on the record

The platform keeps a standing register of places where the simulation is
faithful to its plans but not to what a practitioner would believe. Each is a
deliberate, owner-level decision to fix, because fixing any of them changes
every world's numbers. Open items:

| Item | In plain terms |
|---|---|
| Committed capital under-called | About 29% of every private-markets commitment is never drawn, against a real-world 85–95%. The call-pace curve was a placeholder awaiting data that never arrived. This one gates the game's marquee lever — choosing how much to commit — so it comes first. |
| Crises are too rectangular | The toy engine's crisis is a uniform block of bad months, which leaves a statistical signature real markets don't have — the engine's largest remaining realism defect. |
| Forced sales currently unreachable | A recent fix made typical months milder, and now no shipped scenario can trigger a forced sale — so the mechanic that makes voluntary sales a real decision is dormant in every playable world. |
| Interest rates drift, committees decide | The simulated policy rate glides continuously rather than moving in quarter-point committee steps, so narrated "rate decisions" are numbers no committee could have taken. |

Two more caveats frame everything: the translation layer's 2022 failure stands
un-remedied (its formal gate was never re-taken), and the holdout showed the
generator's predicted ranges simply do not cover an inflation regime like
2021–23. Nothing built on this platform is decision-ready, and every evidence
document says so.

## Next steps we could contemplate

**1 · Put the campaign-tested worlds into the game.** The natural next move,
and a draft plan already exists awaiting review
(`docs/superpowers/plans/2026-08-11-su-generated-worlds.md`). Today the game
plays hand-authored toy scenarios; the proposal is to let it play worlds built
by the generator that just survived three campaigns — decades spliced from real
1953–2020 history, stagflation reachable, severe-tested. The story it enables
is the product's credibility story: *this decade is rearranged truth, and here
is the audit trail.* One distinction is worth stating plainly, because the
word "generated" invites confusion: these are the **collagist's** worlds —
every month in them is a real month that actually occurred; only the sequence
is new. The **apprentice's** truly-invented decades stay out of the product
until a re-aimed contest shows it can invent credibly — *rearranged truth
now; invented worlds only when earned* is both the engineering fact and the
honest marketing sentence. Two calls are the owner's before work starts: which
scenario ships first (a 1974-style stagflation start is the showcase; a 1965
start is the boldest), and whether commodities becomes a playable sleeve now or
stays display-only until the commitment-pacing fix lands.

**2 · Make the institution more lifelike.** Fix the under-called commitments
first — it is the named prerequisite for the commitment lever, the game's most
distinctive decision. The rectangular-crisis defect is the other big one. Both
change every number, so both are release events, sequenced deliberately rather
than slipped in.

**3 · Two cheap research probes, in the gaps.** First, a one-day diagnostic:
pool the apprentice's three trained copies into a committee and re-score — if
the committee clears the bar the individuals missed, this week's loss was
training noise, not lack of ability, and that reshapes any future campaign.
Second, a design note (no computation): a long cross-country historical dataset
— 18 countries, ~150 years — as *real* additional training data, which is the
honest version of the data multiplier the reconstruction shortcut failed to be.

**4 · A fourth campaign only if the probes justify it — and re-aimed.** Judge
"matches history as well as the collagist *and* answers what-if questions the
collagist structurally can't," with the reconstructed-data ban sealed into the
rules from the start.

**5 · Toward other players, in order.** The standing sequence: single player
first (the owner is the first cohort), then a synchronized cohort living
through one sealed world in real time, then facilitated wargames. Anything
involving outside participants waits on the consent framework — a legal-track
item, not an engineering one.

**6 · Pay down the governance debt.** Build the small mechanical checkers the
evidence already names, so "the seal asserts something nothing verifies" stops
being a recurring defect class. Unglamorous, cheap, and it compounds.

A reasonable path through: review the generated-worlds plan (item 1) as the
main line, run the two probes in its gaps, and schedule the commitment-pacing
fix as the first release event after the plan's survey stage says how the
pieces fit. Everything else keeps.

---

*Sources: the gate evidence documents (`G0-EVIDENCE.md`, `G2-EVIDENCE.md`,
`G1-EVIDENCE.md`, `governance/evidence/G4-EVIDENCE.md`), the consolidated
research record (`RESEARCH-EVIDENCE.md`), the three campaign promotion verdicts
(`G2-EVIDENCE.md`, `artifacts/campaign2/PROMOTION.md`,
`CAMPAIGN3-PROMOTION.md`), the engine realism register
(`docs/engine-realism-register.md`), the product kickoff
(`Instructions/KICKOFF-PRODUCT-SU.md`) and the plain-English companions — with
every number quoted from the sealed artifacts rather than from memory.*

*As every evidence document in the project concludes: not investment advice.*
