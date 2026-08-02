# KICKOFF-STEP5.md — Decision Evaluation Kickoff

*Wrapper for `STEP5-DECISION-EVALUATION-PLAN.md` + `STEP5-amendment-A1.md`,
in the manner of the Step 0/3/4 kickoffs. Drafted 2026-08-02 at the Step 4
close; the plan and amendment stay authoritative — this document sequences
them, records what changed between their authorship and kickoff, and fixes
the owner's kickoff decisions. **All five kickoff decisions were resolved
by the owner on 2026-08-02, same day as drafting.***

---

## 1. Prerequisites — status at kickoff

| Prerequisite | Status |
|---|---|
| Steps 3+4 sufficiently complete | ✅ Step 3 tagged `v0.3.0-g1`; Step 4 complete with **Gate G4 CLOSED** (pair rule met 96.7%/100.0%; `G4-EVIDENCE.md`) |
| WP5.1–5.2 protocol + metrics frozen before results | ✅ **Discharged early as wp5-00** (`pre-registration-g5.lock`, `AM-2026-08-02-003` recording the lateness vs the plan's Step-3 schedule — but still before anything it judges existed) |
| One-shot holdout machinery | ✅ Step 2's `FinalEvaluationToken` path, guarded and untouched |
| Decision/wargame substrate | ✅ wp4-07 windows + playbook + wargame; wp4-08 committee; the retrofit's typed contract; leaderboard triple key |
| **Generator campaign** (FX + CAPE + regime persistence + mark-lag diagnosis) | ❌ **Owner decision D-K5-1: SCHEDULED NOW.** Must land before any FINAL evaluation run enters the research record; interim runs on `hier-flow-v1` carry the caveat verbatim |
| **`--inspect` renderer** (MPP-A1 build item, labeled WP2R.4 there) | ❌ Never built (this repo's WP2R.4 label went to the generator-output schema). Both amendment RQs and the methodology-note figures consume it → built here as wp5-02 |
| RQ5 consent line on the counsel list | ✅ Owner-approved (D-K5-4); recorded in `governance/eu-ai-act-mapping.md` open items |

**Standing caveats carried into every Step 5 result:** the G2 generator
caveat (drawdowns understated, regime persistence undercalled) until the
campaign lands; the G1 mark_lag limitation; and the plan's deepest pitfall,
quoted at every write-up: *a policy that wins in the ensemble has been
tested against the policy AND the generator together — say so plainly.*

## 2. The owner's kickoff decisions (all resolved 2026-08-02)

| Id | Decision | Resolution |
|---|---|---|
| D-K5-1 | Generator campaign timing | **Schedule NOW**, in parallel with wp5-01/02. One retrain buys: the FX block (RFR-2 re-entry), CAPE (WP1.13), the regime-persistence fix, and the 2022 mark-lag diagnosis (HY channel / post-2021 stickiness). The GPU host is ALREADY SATISFIED: the owner's local RTX 3080 (10GB) trained the Step 2 campaign (torch + native Windows CUDA); no cloud spend needed. The cost is wall-clock, dominated by the battery/ablation tier (the WP2.10 batching lesson applies). Final Step 5 evaluations wait for it; nothing else does |
| D-K5-2 | RQ4 practitioner panel | **PARKED until the product is polished** — and wanted then ("will be great to do"). Re-raised at the beta/M4 boundary; recruitment is not the constraint |
| D-K5-3 | Decision-density compute | **Pilot first: hundreds of worlds**, cheap deciders (ablations + committee sparingly), with **time and cost measured and reported** so the full thousands-of-worlds version can be budgeted from data rather than guesses. The pilot's evidence pack includes a cost-per-world table |
| D-K5-4 | RQ5 research-use consent | **Approved**: the disclosure joins the counsel-review list now, designed-in before any player exists |
| D-K5-5 | First-tournament format | **Recruitment is not the issue; format is.** Owner's sequence: **solo first**, then the synchronized real-time cohort (one world-quarter per day scale over ~a month), then simultaneous multiplayer — mirroring `product-sequencing-note.md`. The wp5-04 harness therefore supports all three temporal formats from birth (same engine; the format is a reveal-cadence and session-grouping choice, not an engine fork) |

## 3. Build order (one WP per branch)

| # | Branch | Scope | Binding constraints |
|---|---|---|---|
| 1 | `wp5-01-walkforward` | The sealed protocol, executable: expanding-window folds per D9, quarterly rebalancing, the six benchmark policies, Wilcoxon + rank-biserial effect sizes; results reproduce from RunRecords | Implements `step5-evaluation-protocol.yaml`; NEVER redefines it (the lock is the contract); runnable on `hier-flow-v1` with the caveat recorded |
| 2 | `wp5-02-inspect` | The `--inspect` renderer debt: one code path, any RunRecord → static figure page (factor panel, sleeve panel, reported-vs-true toggle, episode annotations, correlogram) | Reads RunRecords only, no separate state; becomes the figure pipeline for RQ1–RQ5 and the methodology note |
| — | (parallel) | **The generator campaign** per D-K5-1: spec → data (HY splice revival, FX, CAPE) → retrain → battery + I2-class inspection → promotion by the Step 2 rules | Blocks FINAL evaluations only; a new `block_addition` amendment + full battery per the sealed re-entry paths (RFR-2/RFR-3) |
| 3 | `wp5-03-counterfactual` | Hold-course twins at scale; **re-coning** (conditional ensemble regenerated from any mid-path state); the was-it-a-good-call metric as an explicit computation | Verify `hier-flow-v1` mid-path conditioning cleanly supports re-coning before building on it; if not, flag — do not approximate silently |
| 4 | `wp5-04-tournament` | N decision-makers, identical worlds/seeds; leaderboards (triple key); dispersion stats; the cohort-exercise export consumed from wp4-07 | Supports the three temporal formats (solo / cohort-cadence / simultaneous) as configuration per D-K5-5 |
| 5 | `wp5-05-density-pilot` | The decision-density study at PILOT scale: hundreds of worlds × {ablations, committee (sampled), hold-course}, alpha attributed by window; **cost-per-world and wall-clock measured and tabled** | The WP2.10 lesson stands (batch the sampler); the pilot's report ends with the budget table for the full run (D-K5-3) |
| 6 | `wp5-06-holdout` | The one shot, through the token path, once, logged | LAST; only after the campaign has landed, every metric run is final, and the owner says go — this one is not covered by any standing authorization |
| 7 | `wp5-07-research-evidence` | `RESEARCH-EVIDENCE.md`: RQ1 (fidelity), RQ2 (held-out regimes), RQ3 (decision value), RQ5 (commitment behaviour — harness only until players exist), RQ4 (parked, D-K5-2); negatives included; every figure regenerable from a RunRecord id | The generator-and-policy-together caveat verbatim in the write-up |

## 4. Halt conditions

- **wp5-06 halts on owner sign-off**, explicitly and always: spending the
  holdout is a one-way act and no goal, chain, or standing authorization
  covers it.
- wp5-03 halts if re-coning would require approximating the generator's
  conditional structure — flag, never fudge.
- Any final-record evaluation halts until the campaign-promoted generator
  exists (interim runs proceed, labeled interim).
- The sealed protocol/metrics are immutable inputs: any WP finding them
  ambiguous halts and asks; amendments go through the log.

## 5. Housekeeping

- CI coverage discipline extends to `ah/eval/` additions as they appear.
- RQ5's flinch construct cites Robinson–Sensoy finding 4.1 (the
  distribution-side mechanism), per the amendment's housekeeping.
- The decision-density paper's twin-policy definition (mechanical t₀
  pacing) carries its D9 changelog reference in the methods section.
- Parked-but-alive registers: RQ4 panel (D-K5-2, re-raise at polish);
  GLEIF integration; French SLA (RFR-86); counsel review of the AI Act
  mapping + the new consent line.

---

*Not investment advice.*
