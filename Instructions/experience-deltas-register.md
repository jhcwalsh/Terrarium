# Experience-Deltas Register

*Created 2026-08-01 under kickoff decision D-K4-2. The owner scoped Step 4 in
this repo to the engine side and conditioned it: the experience-layer deltas
from `STEP4-amendment-A1.md` **must not be lost**. This register is the durable
record. Any project that builds the DN-3 web experience must consume this file;
any Step 4 WP that builds an engine-side counterpart must tick its row. Rows
are never deleted — they are closed with a pointer to the implementing work.*

| # | Delta (STEP4-amendment-A1) | Engine-side counterpart (this repo) | Experience-side obligation (DN-3 project) | Status |
|---|---|---|---|---|
| E1 | **Delta 1 — Commitment window** | Decision windows incl. event-triggered (WP4.7); per-sleeve annual commitment as a decision type with WP3.9 §5 constraints; "hold = stay on pacing plan" distinguishable from an unvisited screen in the RunRecord | UI surface showing, at the moment of decision: coverage on both bases, vintage stack by age, trailing distributions, the t₀ pacing plan; explicit "holding to plan" affordance; tutorial extension with one unmissable commitment consequence | OPEN |
| E2 | **Delta 2 — Cashflow wire events** | Tier-1 templates for capital call, distribution, coverage-band crossing, forced sale (cause + sleeves sold), secondary discount; cash-account voice; forced-sale reads like distress (WP4.2) | Renders in the wire feed; no additional obligation | OPEN — lands in `wp4-02` |
| E3 | **Delta 3 — Outcome card** | Forced-sale count live from the engine (Step 3 done); coverage on both bases exposed in QuarterReport (done) | Interpretation guide gains coverage-on-both-bases as the toggle's second act; coverage-at-worst as a card metric is **consider-not-commit**, decision deferred to after I5 | OPEN (engine side done) |
| E4 | **Delta 4 — Post-game annotations** | Both annotations computable from the RunRecord alone, no new state: the **flinch cost** (commitment cut → later distribution shortfall vs plan) and the **arithmetic warning** (denominator-driven coverage reaction cost) | Chess-style review screen renders them; tone owned by the style guide, "without smugness" | OPEN |
| E5 | **Delta 5 — Help agent scope (M5)** | Grounded-corpus content: commitment mechanics, coverage, forced sales — answerable from glossary + interpretation guide + revealed state | The agent itself; the never-advice rule: explains why, never suggests what | OPEN |
| E6 | **Delta 6 — Inspection points I4–I6** | I4 (reported-vs-true toggle) and I6 (liquidity) run on WP3.3/WP3.9 outputs **before** `wp4-01` branches; work items recorded before G4 closes | I5 (first-run observation, ~20 real users) gates M4 — deferred with D-K4-5 (owner is the only cohort for now); must run before any external release | OPEN |

**Standing rule:** closing a row requires a pointer (commit, WP, or DN-3
ticket), not a deletion. If the DN-3 project starts in another repository,
this file is copied there and the copy noted here.

---

*Not investment advice.*
