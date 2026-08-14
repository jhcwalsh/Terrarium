# Campaign-4 — design spec (CLOSED: NO-GO at the Phase-0 gate)

**Status: CLOSED 2026-08-14 — the owner accepted the Phase-0 NO-GO. The
campaign was never sealed and never ran; the apprentice is shelved with
the reopening conditions below.** Written 2026-08-13, the day both
preconditions returned: the seed-committee diagnostic
(`experiments/probe-seed-committee/REPORT.md`) and the JST scoping note
(`docs/superpowers/specs/2026-08-13-jst-scoping-note.md`). Amended
2026-08-14 to add the Phase-0 gate; gated out the same day.

## The Phase-0 outcome (2026-08-14) — why this closed

Full evidence: `experiments/probe-campaign4-phase0/PHASE0-REPORT.md`
(gitignored store; the durable summary is this section). Dev-grade
numbers, provisional scenario definitions, no seal touched.

- **P0.a, delivery:** the committee's regime conditioning is skin-deep —
  the pinned regime LABEL obeys, the trajectories underneath do not (a
  sampled decade ran declining CPI through a pinned STAG regime). Primary
  interpretation (regime-sequence conditioning only): committee behind
  the benchmark on all three scenarios (stagflation ratio 0.0,
  disinflation boom 0.37, crisis 0.0). Under the most favorable
  convention (factor_conditions bound): stagflation clears at 20.5x but
  disinflation stays even (0.95x) and crisis collapses (0.017x, with an
  open hy_spread waypoint-binding question). 2 of 3 scenarios fail the
  2x bar under every interpretation tested.
- **P0.b, tails:** the sampling-time knob (guidance_scale 0.25) met the
  literal <= 10-exceedance dev bar (8/8/10 of 139 usable bands — the
  seed-committee report's "63" was a counting error, corrected) but
  still exceeded the benchmark's own counts (7/5/6) in every seed, and
  it collapsed the clause-(i) objective edge ~14x (mean_d -0.171 ->
  -0.012). Tail conformance and the objective edge trade off roughly
  linearly in the knob — evidence the edge partly RIDES on the excess
  co-movement. The retrain attempts (A/C) were not run: the stop-rule's
  letter was met, and the independent delivery wall made them moot.
- **Verdict:** two independent walls (shallow conditioning; tail/edge
  coupling), both architecture-level. The gate's purpose was to avoid
  buying a sealed FAIL that was already measurable — it did, for ~85
  minutes of GPU.

**Reopening conditions (verbatim substance from the report):**
1. Committee delivery must reach >= 2x the benchmark's own rate on
   stagflation AND crisis under regime-sequence conditioning alone — or a
   future campaign formally rules that D3 requests may bind
   factor_conditions, and the diagnostic is re-run under that ruling.
2. The crisis scenario additionally needs the hy_spread waypoint-binding
   question resolved (if the conditioning channel never reaches the
   factor's reconciliation target, no ruling fixes delivery).
3. Any tail fix must beat the benchmark's OWN exceedance count in every
   seed while keeping |mean_d| a meaningful multiple of sd_d — attempt A
   (a training-time penalty) is the named next idea, since sampling-time
   knobs demonstrably cannot reach both targets at once.
These are architecture/training-recipe work, not more seeds of the same
recipe. Until someone brings a design that plausibly moves them,
`SHIP-BENCHMARK` stands and the collagist is the product engine.

---

*The design below is preserved as written, for whoever reopens this.*

## Objective

Judge, under a sealed rule, whether the neural generator family
(`hier-flow-v2`, reconstituted as a committee with a tail-calibration fix)
can earn its way into the product — where "earn" now means TWO things at
once:

1. **Clear the full four-clause promotion rule** with the variance lesson
   applied (the committee is the system, so training-seed dispersion stops
   masking a real effect), and
2. **Deliver conditional capability** — decades that *satisfy a requested
   macro condition*, the one thing the resampler structurally cannot do.
   The product form of this gap is on the record: the 1974 world asked for
   stagflation and got a decade whose equity median ran +11.5%/yr, because
   regime conditioning pins block starts only — a tilt, not a guarantee.

The standing rule is unchanged and this campaign is its test: *rearranged
truth now; invented worlds only when earned.*

## What campaign-3 plus the probe established (the evidence this rests on)

- **The objective edge is real and was hidden by training variance.**
  Original three seeds: pooled `mean_d = -0.1367`, cross-seed
  `sd = 0.1612` (seed 0 flipped sign, `d = +0.048`). The three-checkpoint
  committee at the same sampling seeds: `mean_d = -0.1710`,
  `sd = 0.0020` — dispersion down 80x, the numeric inequality cleared 84x
  over. Clause (i)'s failure was variance; committee pooling fixes it.
- **The tail failure is not variance and pooling does not touch it.** The
  flow model generates MORE cross-factor tail co-movement than the
  historical reference bands tolerate: 19–20 exceedances (of 63 usable
  cross-block bands) for the committee vs bootstrap-v1's 5–7, essentially
  identical to every individual seed (18–22). Every training run agrees;
  a mixture reproduces it exactly. This is a property of the architecture
  or training recipe — the one named problem this campaign attacks.
- **The probe is diagnostic-grade only.** Clauses (2)–(4) were never
  evaluated on the committee; a mixture with no sealed identity is not a
  shippable system; SHIP-BENCHMARK stands. Campaign-4 exists to turn the
  diagnostic into (or fail to turn it into) campaign-grade evidence.
- **No data cavalry is coming.** The JST note's verdict: cross-country
  data is annual, monthly disaggregation is reconstruction, and
  reconstruction in training is banned (K3). Training data stays the real
  monthly panel. Better training and a better-aimed test are the only
  levers — which is exactly what this campaign is.

## D1. The system under test: committee-as-the-system

The registered challenger is a **committee of K independently trained
checkpoints** (default K = 3; owner may set 5 at approval — cost is ~one
extra training day for a further variance floor). Ensemble path `i` is
answered by checkpoint `i mod K` — the probe's `CommitteeBlockSampler`
construction, proven deterministic and seedable (bit-identical reruns;
per-row provenance verified). No weight averaging.

The "no single model backs it" objection is answered by making the
committee construction itself the versioned system: at freeze, the K
checkpoint hashes enter the sealed campaign document, and the committee
wrapper code joins the lock. Multi-SAMPLING-seed dispersion replaces
cross-TRAINING-seed dispersion in clause (i)'s pooled route — the honest
translation of the sealed rule's intent now that training seeds are inside
the system rather than replicates of it.

**Product-adoption note (out of campaign scope):** `generator_id` is pinned
by an enum in `schemas/` and cannot gain values. If the committee ever
promotes, how it is named for the product surface is a separate owner
decision; the campaign judges the system under a campaign-local id, exactly
as campaign-3 judged its systems.

## Phase 0 — the development gate (unsealed, BEFORE anything is sealed)

*(Added 2026-08-14 at owner direction: don't pay seal-grade prices for
information dev-grade experiments can deliver first.)*

Two measurements, both on the EXISTING checkpoints, both dev-side
(train+val only, dev metrics, no seal touched, no campaign implied —
the seed-committee probe's discipline exactly):

- **P0.a — conditional-delivery diagnostic.** Measure, for the first time
  on any system, the delivery rate: committee vs benchmark, conditioned on
  the three D3 scenarios under PROVISIONAL dev definitions (marked as
  such; the sealed thresholds are set later at the seal event, from
  reference machinery, never from these results). Answers: is the untested
  clause already passable?
- **P0.b — the tail-calibration attempts** (moved here from the sealed
  phase, same budget: the three attempts of D2, ≤ 4 working days,
  cheapest first — attempt B is hours and no retrain). Dev bar unchanged:
  cross-block exceedance ≤ 10 of 63 on the development battery.

**The gate:** the campaign is sealed and bought ONLY if Phase 0 shows a
live path on BOTH fronts — some attempt meets the tail dev bar, AND the
delivery diagnostic shows the committee ahead of the benchmark by enough
that 2x at seal-grade is plausible. Otherwise the outcome is a shelf note
with precise numbers (what must move, by how much) for ~3 unsealed days,
instead of a two-week sealed FAIL. Honesty line: Phase 0 results are
dev-grade and are NOT campaign evidence; sealed thresholds are derived
from the reference machinery per RFR-77, never tuned to what Phase 0
achieved; the campaign trains FRESH seeds under the sealed recipe.

## D2. The tail-calibration phase — capped (runs inside Phase 0)

The named problem: **excess cross-factor tail co-movement** (too much
joint-crash, not too little). Pre-declared attempt budget, recorded here
so sunk costs cannot renegotiate it:

- **Attempt A — tail-co-movement penalty:** add an explicit penalty on
  cross-block lower/upper tail dependence of generated paths against the
  training panel's own coefficients, weighted into the existing objective.
- **Attempt B — coupling recalibration:** temperature/shrinkage on the
  cross-block coupling layers at sampling time (a calibration knob fitted
  on train+val, not a retrain) — cheapest if it works.
- **Attempt C — per-block tail-scale head:** let each block carry its own
  tail-scale parameter conditioned on regime, so co-movement in crisis
  months is learned per-pair rather than shared.

**Budget: these three attempts or 4 working days, whichever ends first.**
Phase success bar (dev-side, train+val only, never the sealed bands
themselves): cross-block exceedance ≤ 10 of 63 on the development battery.
This phase now runs UNSEALED inside Phase 0, and its result feeds the
gate: meet the bar and the campaign seals the winning recipe; miss it and
the shelf note records the attempts — no sealed FAIL is bought for a
failure already measured. Every attempt (incl. failures) goes in the
evidence pack either way.

## D3. The re-aimed criterion: conditional delivery

The new sealed metric family, and the heart of the re-aim. For each of
three pre-declared scenario requests, both systems generate conditioned
ensembles, and we measure the **delivery rate** — the fraction of decades
that actually satisfy the request:

1. **Stagflation decade** — e.g. trailing-YoY CPI ≥ 5% in at least 60 of
   120 months AND real equity total return ≤ 0 over the decade.
2. **Disinflation boom** — CPI YoY declining decade-on-average with
   equity real return above a set floor.
3. **Crisis decade** — at least one drawdown episode deeper than a set
   depth with spread widening beyond a set level, co-timed.

Exact thresholds are the owner's to set at approval (proposed values to be
tabled in the seal event, computed ONLY from train+val history, e.g. "the
1973–82 realized values"), then sealed. The clause:

> **Conditional-delivery clause:** for every scenario, the challenger's
> delivery rate must be at least **2x** the benchmark's under the same
> conditioning request, AND the challenger's conditioned ensembles must
> pass the same credibility battery (bands judged on the conditioned
> output) with no enforce-tier regression vs the benchmark's conditioned
> output. Delivering the condition by breaking the world does not count.

This is the test bootstrap-v1 is NOT nearly unbeatable on by construction
— it is the test the product actually needs, per the 1974 finding.

## D4. The decision rule (sketch — final text is written at the seal)

Four-clause structure retained, applied to the committee:

- **Clause (1)**: objective beats via the pooled route on sampling seeds;
  tail-band no-regression must hold in every sampling seed — **unchanged
  and unrelaxed**; the tail phase must earn it. The campaign-3 verdict
  script's pooled-route gap (it omits the AND with clause (ii) that the
  sealed prose requires — found by the probe, inert in campaign-3's data)
  is **fixed before the seal and the fixed script joins the lock.**
- **Clauses (2)–(4)**: memorization, constraint violations, enforce-tier
  regression — carried as sealed in campaign-3, evaluated on the
  committee, severe leg on both sides.
- **Clause (5), new**: conditional delivery per D3.
- **Verdicts**: `PROMOTE-CONDITIONAL` (all five) → invented worlds may
  enter the product behind a disclosure line, as a *second* world class
  beside the collagist's, never replacing it. Anything less →
  `SHIP-BENCHMARK`, with the clause-by-clause record published.

## D5. Data and training rules

- Training data: the extended real-months panel, current clean vintage
  (2026-08-10.1 or a newer clean weekday vintage taken at seal time).
  **Real months only** — the K3 rule is carried forward as a standing
  sealed constraint, not re-derived. No JST rows (annual; see the scoping
  note). No reconstructed rows, period.
- The K1 future-accruing holdout is untouched (first read 2029; one read
  ever). Judging uses the sealed reference machinery on train+val, as in
  campaign-3.
- Hardware: the local RTX 3080, strictly sequential cells (the K4
  precedent host; same-device bit-determinism verified in campaign-2).

## Order of work

1. Owner approves this note. **[APPROVED with the Phase-0 amendment,
   2026-08-14.]**
2. **Phase 0** (unsealed, ~3–5 days): P0.a delivery diagnostic + P0.b
   tail attempts. Ends with a go/no-go on the owner's desk, with numbers.
3. **Owner go/no-go.** On go, the owner also sets: K (3 or 5) and the D3
   scenario thresholds (or delegates their tabling to the seal event).
4. Pre-seal repairs, committed before the campaign block is written: the
   promotion-script AND fix (+ its test); the conditional-delivery metric
   implementation (+ tests) — the judge must exist to be hashed.
5. **The seal event**: campaign-4 block in `pre-registration.yaml` — rule
   text, thresholds, the frozen recipe from Phase 0, committee
   construction, checkpoint-hash placeholders declared as planned
   arrivals — all three locks re-sealed in one commit with superseded
   digests recorded.
6. Train K fresh seeds under the sealed recipe; freeze; hashes join the
   seal by dated amendment (planned arrival, post_hoc false).
7. Batteries + severe legs + conditional-delivery grids, both systems.
8. Verdict via the fixed script; evidence doc; owner receives the result.

**Timeline: Phase 0 ~3–5 days → go/no-go → campaign ~5–7 days on a go.**
Owner touchpoints: steps 1 (done), 3 (go/no-go, the substantive one),
5 (ratify), 8 (receive). Collagist product work continues in the main
tree throughout; the GPU belongs to the campaign.

## Honesty clauses

- The probe's numbers are diagnostic-grade and are NOT evidence in this
  campaign; everything is recomputed under the seal.
- SHIP-BENCHMARK stands unless and until all five clauses clear.
- A tail phase that fails its dev bar does not stop the campaign; it
  produces a sealed honest FAIL with the attempts on record.
- No relaxation of any carried threshold without a logged amendment; the
  three-lock discipline applies to every file this campaign touches.
- If the verdict is FAIL, the shelf note names the reopening condition
  (what number must move, by how much) — no ambiguous abandonment.
