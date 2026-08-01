# Step 3 in plain English

*A companion to `STEP3-TRANSLATION-PLAN.md` and `KICKOFF-STEP3.md`. Those two
documents govern; this one just explains. If they ever disagree, they win.*

---

## What Step 3 is for

Steps 0–2 built a machine that generates believable *economic weather*:
thousands of alternate decades of interest rates, inflation, stock returns,
credit spreads. But no investor experiences "the equity factor". They
experience a **portfolio**: a hedge fund statement that arrives a month late,
a private equity fund that suddenly calls $5m of committed capital in a bad
quarter, a property fund that won't give the money back when asked, a pension
scheme whose deficit balloons because rates moved.

Step 3 builds the translation layer between the weather and that lived
experience. In: generated market conditions. Out: what a real institution's
statements, cashflows, and balance sheet would have looked like, month by
month, in each alternate world.

## The pieces, in the order they get built

**0. Rules before play (the "G3-pre" seal).** Before writing the models, we
write down — and cryptographically freeze — how we will judge them: what
counts as realistic tail behaviour for each type of investment, and what
counts as successfully reproducing the year 2022. This is the same discipline
Step 2 used: decide the exam before anyone sees the questions, so nobody can
quietly move the goalposts after seeing results. We learned in Step 2 that
even the freezing process needs guards; this time the guards are on from day
one.

**1. The objects (state).** Software versions of the things an institution
holds: a private-markets fund that calls and returns capital over a decade; a
hedge fund you can (usually) exit monthly; a semi-liquid fund with a
redemption queue; plain stocks and bonds. Each knows its own bookkeeping —
what's committed, what's been paid in, what it says it's worth versus what
it's really worth. These follow contracts we froze in Step 2R, so their shape
can't drift.

**2. From market factors to strategy returns (mappings).** How much does a
merger-arbitrage fund actually move when stock markets move? We estimate this
from twenty-one real hedge-fund strategy histories — using the *de-smoothed*
versions, because reported hedge-fund numbers are artificially calm (managers'
marks lag reality; we measured this: credit and distressed strategies
understate their own volatility by up to 40%). Estimating on the calm version
would build a world where private assets look magically safe. That is the
single most important trick in this step and the reason Step 1 built the
de-smoothing machinery.

**3. Putting the smoothing back (reporting).** Having estimated on honest
numbers, we then *deliberately re-apply* the smoothing when producing what the
investor **sees**. The simulation keeps two sets of books, exactly like
reality: what the portfolio is truly worth, and what this quarter's statement
claims. The gap between them — the stale marks in a crash — is where much of
2022's story lives.

**4. Cashflows (the J-curve).** Private funds don't behave like bank accounts.
You commit money; they call it over several years; eventually distributions
come back — unless markets are bad, when the calls keep coming but the
distributions dry up. We model this with an industry-standard cashflow model
made *market-sensitive*: exits speed up in booms and stall in busts. A key
honest finding from the research behind it: **a fund's age matters about ten
times more than the economy** for its cashflows — the economy is a tilt, not
the engine. And there is deliberately no special "crisis switch": ordinary
market variables explain crisis behaviour on their own, and we test that
claim rather than assume it. First we build a deliberately dumb baseline
version; the clever version must then *beat* the dumb one on reproducing real
episodes, or we say so and ship the dumb one.

**5. The fine print (vehicle mechanics).** Notice periods, lock-ups, gates,
side pockets, redemption queues that quietly lengthen in stress — the plumbing
that converts "I'd like my money back" into "you'll get 60% of it, in eight
months." The semi-liquid property fund gets first-class treatment because its
failure mode — a queue, with no formal gate ever declared — is the modern one.

**6. The portfolio engine.** One institution's whole book, run forward: cash
comes in from distributions and income, goes out to capital calls and
spending. When cash runs short, the engine sells liquid assets by policy; if
still short, it sells private stakes at a stress discount and raises a
**forced-sale flag** — deliberately a headline number, because "did we become
a forced seller?" is the question this platform exists to answer.

**7. The pension twin.** A defined-benefit pension scheme bolted onto the
portfolio: what it owes members for decades, how those obligations swing with
rates and inflation, its hedges, and the collateral behind those hedges —
including the *headroom* that ran out for UK schemes in 2022. Paired with a
"hold-course twin": an identical institution that mechanically sticks to its
original plan, so every decision's value can later be measured against the
road not taken.

**8. Speed tricks (proxies).** Liability calculations are slow; interactive
use needs answers in seconds. We train fast approximations and test them
hardest exactly where it matters most — the worst 1% of outcomes — because an
approximation that's accurate on average but wrong in disasters is worse than
useless here.

**9. Hero funds.** Three to five named, individual synthetic funds per world
(not just "the buyout sleeve") whose numbers reconcile to the aggregates.
They exist so Step 4's manager letters and news items have real arithmetic
behind them.

**10. The final exam (reproducing 2022).** Feed in 2022's actual market
moves; the whole chain must reproduce the year an allocator lived through:
public markets fall fast, private marks stay stale, the private share of the
portfolio breaches its range *because the denominator fell*, distributions
dry up while calls continue, and — for the over-committed — forced sales at a
discount. Scored against criteria frozen back at step 0 of this list, so the
result means something.

## What Step 3 deliberately does NOT do

No narrative artifacts, no AI actors, no live mode (Step 4). No judging of
decisions (Step 5). No claim that the generated worlds are a convincing model
of history — Step 2's verdict was "better than the benchmark, honestly still
not convincing", and everything built here inherits that caveat until the
next generator campaign (which will also add currency risk and revive the
decade-scale checks). The translation layer is built to be
generator-agnostic: when the better generator lands, this layer doesn't
change.

## What exists when Step 3 is done

Type one command and a complete institution comes back per alternate world:
true and reported returns, every fund's calls and distributions, the cash
account, breaches, forced sales, and the pension balance sheet — all
reproducible to the bit from a stored record, all validated against a frozen
contract, and the 2022 test passed or honestly failed in writing.

---

*Not investment advice.*
