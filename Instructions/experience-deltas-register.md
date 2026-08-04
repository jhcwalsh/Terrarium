# Experience-Deltas Register

*Created 2026-08-01 under kickoff decision D-K4-2. The owner scoped Step 4 in
this repo to the engine side and conditioned it: the experience-layer deltas
from `STEP4-amendment-A1.md` **must not be lost**. This register is the durable
record. Any project that builds the DN-3 web experience must consume this file;
any Step 4 WP that builds an engine-side counterpart must tick its row. Rows
are never deleted — they are closed with a pointer to the implementing work.*

| # | Delta (STEP4-amendment-A1) | Engine-side counterpart (this repo) | Experience-side obligation (DN-3 project) | Status |
|---|---|---|---|---|
| E1 | **Delta 1 — Commitment window** | Decision windows incl. event-triggered (WP4.7); per-sleeve annual commitment as a decision type with WP3.9 §5 constraints; "hold = stay on pacing plan" distinguishable from an unvisited screen in the RunRecord | UI surface showing, at the moment of decision: coverage on both bases, vintage stack by age, trailing distributions, the t₀ pacing plan; explicit "holding to plan" affordance; tutorial extension with one unmissable commitment consequence | **PARTIAL** — see §E1 |
| E2 | **Delta 2 — Cashflow wire events** | Tier-1 templates for capital call, distribution, coverage-band crossing, forced sale (cause + sleeves sold), secondary discount; cash-account voice; forced-sale reads like distress (WP4.2) | Renders in the wire feed; no additional obligation | **PARTIAL** — see §E2 |
| E3 | **Delta 3 — Outcome card** | Forced-sale count live from the engine (Step 3 done); coverage on both bases exposed in QuarterReport (done) | Interpretation guide gains coverage-on-both-bases as the toggle's second act; coverage-at-worst as a card metric is **consider-not-commit**, decision deferred to after I5 | OPEN (engine side done) — see §E3 |
| E4 | **Delta 4 — Post-game annotations** | Both annotations computable from the RunRecord alone, no new state: the **flinch cost** (commitment cut → later distribution shortfall vs plan) and the **arithmetic warning** (denominator-driven coverage reaction cost) | Chess-style review screen renders them; tone owned by the style guide, "without smugness" | **PARTIAL** — see §E4 |
| E5 | **Delta 5 — Help agent scope (M5)** | Grounded-corpus content: commitment mechanics, coverage, forced sales — answerable from glossary + interpretation guide + revealed state | The agent itself; the never-advice rule: explains why, never suggests what | OPEN |
| E6 | **Delta 6 — Inspection points I4–I6** | I4 (reported-vs-true toggle) and I6 (liquidity) run on WP3.3/WP3.9 outputs **before** `wp4-01` branches; work items recorded before G4 closes | I5 (first-run observation, ~20 real users) gates M4 — deferred with D-K4-5 (owner is the only cohort for now); must run before any external release | OPEN |
| E7 | **Retrofit R-1 (DN-5) — three analysis series** | RunRecord stamps (`twin_definition`) land at the retrofit; the drift twin's engine work is scheduled later | The analysis screen must accommodate **three** series — player, policy twin, drift twin — not two: layout, legend, and colour set widen now so the third series is a data arrival, not a redesign; renders correctly when given two | **CLOSED** — see §E7 |
| E8 | **Retrofit R-1 (DN-5) — per-window annotation slot** | Decision-window contract (`ah/artifacts/decisions.py`) defines window identity | The post-game view carries one short annotation line per decision window (e.g. `Year 4, de-risked: -2.1 points`); placeholder or hidden when absent, but the slot exists in the layout before the scoring that fills it | **CLOSED** — see §E8 |

**Standing rule:** closing a row requires a pointer (commit, WP, or DN-3
ticket), not a deletion. If the DN-3 project starts in another repository,
this file is copied there and the copy noted here.

---

## Pointers — audited 2026-08-04, after the SU single-user slice

*The five `su-app-*` work packages and the `wire-play-surface` merge landed
substantial parts of six rows. This audit was done by reading the shipped
surface, not the changelog prose: a row is marked CLOSED only where the whole
obligation is on screen. Where the headline piece landed and the rest did not,
the row stays open with its progress recorded — the register exists to keep
what is missing visible, and a half-ticked row would hide it.*

### §E1 — PARTIAL

**Landed.** The explicit "holding to plan" affordance, which is the row's
core: `app/src/components/DecisionWindow.tsx` (`f04de07`, su-app-02, merge
`5c9932c`) makes hold course a radio selection with the same weight as the
other three actions, and the commit button is dead until something is chosen —
there is no click-through default, pinned by test. Coverage **on both bases**
is on screen at the moment of decision: `app/src/components/Book.tsx`
(`8141ab2`) renders true coverage in the rail and states reported against true
in the note. The Book, the ledger and the decision window co-render on one
screen (`app/src/Play.tsx`), so "at the moment of decision" is satisfied for
what is shown.

**Not landed.**
- **The vintage stack by age.** `PrivateMarkets.tsx` shows the last revealed
  quarter's calls and distributions only. There is no by-age stack.
- **Trailing distributions.** Same surface, same limit: one quarter, not a
  trailing series.
- **The t₀ pacing plan.** Not rendered anywhere; the player cannot see the
  plan they are holding to or departing from.
- **The tutorial extension** with one unmissable commitment consequence.
- **The per-sleeve annual commitment decision type.** The shipped action set
  is four (`hold | derisk | leanin | secondary`, `app/src/lib/session.ts`).
  `KICKOFF-PRODUCT-SU.md` §2 scoped "the four public actions **plus the
  commitment lever** (E1)"; the lever is not in the set. Without it the row's
  own subject — the commitment decision — cannot be taken by a player, which
  is why this row cannot close on the hold-course affordance alone.

### §E2 — PARTIAL

**Landed.** The engine-side counterpart is complete: all five Delta-2 event
classes exist as tier-1 templates in `src/ah/artifacts/templates.py`
(WP4.2) — capital call, distribution, coverage-band crossing, forced sale,
secondary discount. The wire itself ships and reveals in-timeline:
`src/ah/feed.py` + `app/src/components/Feed.tsx` (`b14e93b`, su-app-03, merge
`b0bb1c3`). **Forced sales reach the wire** and read as distress —
`app/src/Play.tsx` merges the session's `forced_sales` into the feed and
`Feed.tsx` labels them `FORCED SALE` (`1bca4bc`, merge `1194e2e`).

**Not landed.** Three of the five classes are written but nothing renders
them. Capital calls and distributions appear as ledger rows in
`PrivateMarkets.tsx`/`Book.tsx`, not as wire events in the cash-account voice
the row specifies; coverage-band crossing and secondary discount have
templates and no call site. `build_tier1_feed` emits crisis digests, release
pages, newspapers, central-bank statements and quarterly statements only —
the cashflow classes are session-dependent and were never wired the way the
forced sale was.

### §E3 — OPEN (engine side done)

**Landed.** Engine side was already done at Step 3 and is now genuinely
plumbed through: the play surface scores on the real institutional twin
(`src/ah/play.py` → `ah/port/`, `d45ef06`/`6ef5d06`, merge `1194e2e`, closing
ER-3), so forced-sale counts and coverage on both bases are live session
fields, not aspirations. The outcome card renders and states its own scope
(`app/src/Reckoning.tsx`, `74bd3fc`).

**Not landed.** The row's experience obligation is that the **interpretation
guide** gains coverage-on-both-bases as the toggle's second act. There is no
interpretation guide in this repo — the phrase appears only in a source
comment. The document has to exist before the row can close. The card metric
(coverage-at-worst) remains consider-not-commit behind I5, as ratified.

**Stale copy to fix when this row is worked.** `Reckoning.tsx` says
forced-sale and coverage metrics "join with the institutional plane" — written
before ER-3 closed. The institutional plane has arrived; the card should now
show those numbers rather than promise them.

### §E4 — PARTIAL

**Landed.** The chess-style review screen exists and steps the decade window
by window (`app/src/Reckoning.tsx`, `74bd3fc`, su-app-04, merge `5dfcd88`).
The counterfactual the flinch cost needs is defined and implemented engine-side
(`src/ah/port/twin.py`, `src/ah/play.py:413` — the hold-to-plan twin).

**Not landed.** Neither named annotation exists. There is no flinch cost
(commitment cut → later distribution shortfall vs plan) and no arithmetic
warning (coverage reaction that was denominator-driven) anywhere in the app or
the service — a repo-wide search finds the concepts only in plan documents and
twin docstrings. What the review renders today is E8's chain-link line, which
is a different annotation answering a different question. Note the dependency:
the flinch cost is only meaningful once E1's commitment lever exists, since
today a player cannot cut a commitment.

### §E7 — CLOSED

`app/src/components/AnalysisChart.tsx` + `Reckoning.tsx` (`74bd3fc`,
su-app-04, merge `5dfcd88`; quarterly/monthly axis corrected in `bb5ac59`).
`threeSeries()` carries player / policy twin / drift twin with a colour each,
the drift twin's `values` typed `number[] | null` as a reserved slot, and the
legend marks the missing series rather than dropping it. Renders correctly
when given two, which is the row's stated test. The drift twin's arrival is
now a data change, exactly as required.

### §E8 — CLOSED

`annotationLine()` in `app/src/Reckoning.tsx` (`74bd3fc`, su-app-04, merge
`5dfcd88`) produces the register's exact shape — `Year 4, de-risked: -2.1
points` — one line per decision window, sourced from the chain-link
decomposition ported onto the real twin (`ef4e4bd`, `6ef5d06`) so the lines
sum to the player's alpha, and the review copy says so.

---

*Not investment advice.*
