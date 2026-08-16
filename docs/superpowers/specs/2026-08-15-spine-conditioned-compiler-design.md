# Spine-conditioned stress compiler — design

**Date:** 2026-08-15 · **Status:** DRAFT for owner review · **Working name:** `spine-bootstrap`
**Parents:** `docs/state-of-the-thesis.md` (the Path-B spending rule this pilot satisfies),
`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md` v0.3 (the flesh),
`G2-EVIDENCE.md` §7–8 (why L3 is out and L1/L2 are in),
the CPI join finding (2026-08-15, recorded in the stress spec's §10.2 inputs).

---

## 1. What this is

The synthesis of the two tracks: **spine from the model, flesh from history.**

- The hierarchical generator's L1/L2 layers — trend inflation, neutral rate, growth,
  vulnerability, credit gap, plus regime persistence — generate a coherent macro
  **spine** for the decade. These layers encode exactly the couplings the stitched
  worlds lack: CPI → policy → growth. The layer that failed its evidence (L3, the
  neural monthly texture that understates drawdowns ~2×) is not used.
- The stress compiler's stitcher supplies the **flesh**: verbatim 6-month chunks of
  real joint history, now selected *conditional on the spine's state* instead of on
  severity alone.

The failure this kills: world 703's inflation-era teleports (+1.1% → +5.6% YoY across
a join) and policy "reversals" that are splice artifacts — a decade that is real at
month scale and incoherent at story scale.

## 2. Owner rulings (2026-08-15, binding on this design)

- **R1 — Selection only.** State never edits a drawn month. A vulnerable state shifts
  *which* real months are drawn (stratum, depth percentile, crisis dwell) — never
  multiplies or perturbs their values. Every month remains verbatim history; the
  world's severity ceiling is history's worst months. Amplification is out of scope
  and returns only as a future amendment if measurement shows selection cannot reach
  declared severity bands.
- **R2 — State-dependent hazard for corrections.** Correction *timing* is not
  predicted and not scripted: each month carries a hazard driven by the spine, and a
  random draw fires it. Correction *preconditions* are modeled: hazard rises with
  credit gap, vulnerability, policy tightness versus neutral, and inflation above
  trend. Calibration target is historical correction frequency conditional on state —
  **never portfolio outcomes** (rule 1 of the stress methodology, carried forward).
- **Carried forward from the stress spec:** commit-order-as-pre-registration; reserved
  decisions proposed-never-taken; `schemas/` untouched (no new `generator_id` — see
  §7); depth never consulted when choosing block length.

## 3. Architecture

Three layers, strictly ordered. Each is independently testable.

### 3.1 Layer S — the spine sampler

**Input:** a declared **premise** and a seed.
**Output:** a 120-month path of slow states
`(pi_star, r_star, g, v, credit_gap, policy_stance)` plus a regime skeleton.

- Draws come from the **existing L1 posterior checkpoint** (campaign artifacts; no new
  training) pushed through the L2 regime skeleton — the same sampling path
  `hier-flow-v1` uses, truncated before L3.
- The **premise constrains the spine**: a premise is a small typed object —
  `{shock: supply, arrives: year 2, backdrop: inflation above trend, recovery: slow}` —
  compiled to acceptance conditions on spine draws (rejection sampling with a stated
  attempt cap; an unfillable premise is a **refusal with a named reason**, the
  "history never did this" feature, mirrored from the stress compiler's uncovered-
  quarter refusal).
- This is the first concrete step of the reserved premise-compiler decision (D-SC-2):
  the premise vocabulary here is deliberately minimal (shock type, timing, backdrop,
  recovery shape). Extending it to free text stays reserved.

**Why the spine can be trusted where L3 could not:** the recorded G2 failures are
drawdown depth (an L3 property — unused here) and regime persistence (partly L2).
Persistence is therefore a **sealed pilot bar** (§5, B4), not an assumption: if the
spine undercalls persistence, the pilot fails and says so.

### 3.2 Layer H — the correction hazard

Monthly hazard `h_m = logistic(a + b · x_m)` where `x_m` is the spine's state vector:
`(credit_gap_m, v_m, policy_stance_m − r_star_m, pi_m − pi_star_m)`, each standardized
against the L1 posterior's own scale.

- **Calibration:** coefficients are fit so that correction frequency *per coarse state
  bucket* matches the campaign panel's historical frequency of correction onsets in
  those buckets (correction onset = the panel's existing CRI regime entries). Fitting
  data is the panel only. Portfolio outcomes never enter the objective (rule 1).
- **Firing:** when the monthly draw (from the path's own PCG64 stream, platform seed
  discipline) fires, the compiler enters a **crisis segment**: stratum shifts to the
  crisis pool, with depth percentile and dwell drawn from the **state-severity table**
  (§3.4). When the segment's dwell expires, control returns to the premise's baseline
  strata.
- **This is the answer to "corrections are notoriously hard to predict":** the machine
  does not predict them. It reproduces the *statistics of their preconditions* and
  rolls dice. Two decades from the same premise differ in when — and whether — the
  second correction lands. Repeat players cannot learn a schedule (the recorded
  weakness of authored-only corrections).

### 3.3 Layer F — the flesh (the existing stitcher, conditioned)

The `StressBootstrap` machinery is reused with two changes:

1. **Chunk selection conditions on the spine.** Each 6-month chunk must come from
   source months whose macro state matches the spine's current bucket. Buckets are
   deliberately coarse to protect pool depth (§6): inflation era
   {high-or-rising, low-or-stable}, growth {expansion, contraction}, policy
   {tightening, easing-or-floor}. Eight cells, crossed with the severity stratum the
   hazard/premise currently demands.
2. **The join discipline gains the inflation era.** Adjacent chunks must agree on
   inflation-era bucket, and the source-space CPI YoY jump across a join is bounded
   (threshold sealed at pre-registration from the panel's own adjacent-month
   distribution). This closes the CPI finding: era teleports become structurally
   impossible, not merely rare.

Verbatim months only (R1). `row_indices` provenance, per-path RNG streams, and the
`.source` exposure are unchanged from the stress compiler.

### 3.4 The state-severity table (the scaling requirement)

The owner's key requirement — *a supply shock against above-trend inflation is worse
than against benign inflation* — is implemented as a small pre-registered table, not a
formula buried in code:

| Spine state at firing | Depth stratum shift | Dwell shift |
|---|---|---|
| inflation ≤ trend, credit gap low | baseline (the premise's declared stratum) | baseline |
| inflation > trend **or** credit gap high | one stratum deeper | +1 quarter |
| inflation > trend **and** credit gap high | two strata deeper | +2 quarters |

Exact stratum definitions and shift sizes are **pre-registration candidates**: proposed
values are sealed (with the code that applies them) before any pilot ensemble is
drawn, per the existing commit-order discipline. The table is the single place state
touches severity — auditable in one glance, and selection-only by construction (it
shifts *which* pool is drawn from, never what a drawn month contains).

## 4. What "coherent" now means — the claim, stated plainly

A spine-conditioned decade tells one story because: the storyline is generated by a
model whose inflation, policy, and growth move for reasons (L1 dynamics); the months
are chosen to agree with that storyline; and the seams cannot jump eras. The world's
central bank "responds" to inflation because the spine's policy state genuinely
responds to the spine's inflation state, and the flesh is selected to match both.
What remains authored: the premise (by design — this is still a stress instrument,
and severity remains declared at the premise level). What remains impossible: months
history never produced (R1's ceiling, accepted).

## 5. The pilot and its sealed bars

Per the memo's spending rule: cheap, pre-registered, pass/fail before any larger
spend. **No new training; no L3; no new dependencies.** Reuses: the L1/L2 checkpoint,
`stress.py`, the stress-report harness, the E1 over-commitment grid, the block-length
study machinery.

Bars are sealed (thresholds + judging code hashed together) before the first pilot
ensemble is drawn. Numeric values marked *(cand.)* are candidates to be finalized at
sealing from panel measurements — the formulas are fixed now:

- **B1 — Reaction function (the test stitched worlds could never pass).** Across
  ≥100 spine draws: the spine's policy-stance change regressed on lagged inflation
  gap has the correct sign at a 1–4 quarter peak lag in ≥90% *(cand.)* of draws.
  Judged on the spine directly.
- **B2 — Era coherence.** Zero joins with source-space CPI YoY jump above the sealed
  bound; the 95th percentile of adjacent-month YoY changes within 1.25× *(cand.)* of
  the panel's own 95th percentile.
- **B3 — It can still hurt a book.** The E1 grid re-run under spine-conditioned
  worlds: coverage remains monotone in private allocation; the 55% arm breaches at
  least as often as under the stress compiler (≥1/20); hold-course depth lands inside
  each premise's declared band.
- **B4 — Persistence.** Spine regime sojourn distributions inside the battery's
  sealed bands (existing where defined; otherwise sealed from panel at
  pre-registration). **This is the bar the G2 record says to fear** — if the spine
  inherits hier-flow's undercalling, the pilot fails here, and the result is recorded,
  not massaged.
- **B5 — Hazard realism.** Per-bucket correction onset frequency within ±50%
  *(cand.)* relative of the panel's; median corrections per decade within the
  panel's decade range.

**Verdict rule:** all five PASS → the architecture earns a campaign-4-scale decision
(owner's call, with this spec as its basis). Any FAIL → the failing layer is named,
the result is committed, and the approach is parked with its evidence — same
discipline as every gate before it.

## 6. Risks, named

- **Spine gentleness (B4's target).** Partly mitigated by premises constraining the
  spine; if constrained spines *still* undercall persistence, that is a finding about
  L2 worth having at pilot price.
- **Pool sparsity.** Eight state cells × severity strata over an 813-row panel will
  leave thin cells (the stress compiler's strata already thin it — the block-length
  study's 35th-percentile pool was 284 rows). Mitigations: coarse buckets (already chosen), measured cell
  occupancy published in the pilot report, and refusal (not silent substitution) when
  a premise demands an empty cell. A refusal is information: history never did this.
- **L1 state identifiability.** `v` and `credit_gap` are posterior estimates, not
  observables; the hazard inherits their noise. The pilot report must show hazard
  sensitivity to posterior draw (fire the hazard under 5 posterior samples; the
  B5 statistics should be stable across them).
- **Two RNG consumers** (hazard draws + chunk draws) on one path stream — a seeding
  bug here silently changes worlds. The stream-splitting rule (separate `jumped`
  substreams per consumer) is a stated acceptance test, not a convention.

## 7. Contract and plumbing constraints

- `generator_id` **cannot gain values** (schema enum, pinned). Spine worlds ride the
  existing `bootstrap-stratified` id through the established dispatcher: a world
  carrying the new `extensions.x_spine` block routes to the spine-conditioned
  compiler; `x_stress` alone routes to the current stress compiler; neither routes
  sealed 1.0.x worlds anywhere new. Bit-identity of all existing worlds is an
  acceptance test.
- `x_spine` (premise, hazard config reference, state-severity table reference) is an
  **extension**, exactly as `x_stress` was — `schemas/` is not touched.
- Seal boundaries: the compiler remains "judged, not judge" (the `EXCLUDED_FROM_SEAL`
  classification argument from stress-01 applies unchanged). Pilot bars live with the
  eval/prereg machinery like every sealed criterion before them. **All three lock
  scopes get grepped before any edit** (standing rule).
- Narration: spine worlds carry the slow states natively (`SlowStateRecord`), so the
  narration workbench's anchor decomposition works without adaptation — and the
  join-awareness caveat shrinks to the (now bounded) within-era seams.

## 8. Decisions reserved for the owner (proposed, not taken)

- ⚑ **D-SP-1:** the state-severity table's sealed values (§3.4).
- ⚑ **D-SP-2:** the hazard's state vector — the four components proposed, any
  addition/removal is an owner call.
- ⚑ **D-SP-3:** the premise vocabulary's first release (shock type × timing ×
  backdrop × recovery shape proposed; anything richer waits on D-SC-2 proper).
- ⚑ **D-SP-4:** what a PASS buys — pilot success does not itself authorize a
  campaign; it authorizes the owner's decision about one.

## 9. Non-goals

No L3 or any neural texture. No editing, scaling, or synthesis of monthly values
(R1). No new dependencies. No schema changes. No free-text premises. No live-mode or
app surface work — the pilot's consumer is the measurement harness, and the app
integration is its own later spec if the pilot passes.
