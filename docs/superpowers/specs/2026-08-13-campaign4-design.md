# Campaign-4 — design spec (DRAFT for owner approval)

**Status: DRAFT — nothing here is sealed, no work begins until the owner
approves this note.** Written 2026-08-13, the day both preconditions
returned: the seed-committee diagnostic
(`experiments/probe-seed-committee/REPORT.md`) and the JST scoping note
(`docs/superpowers/specs/2026-08-13-jst-scoping-note.md`).

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

## D2. The tail-calibration phase — capped, in the sealed document

The named problem: **excess cross-factor tail co-movement** (too much
joint-crash, not too little). Pre-declared attempt budget, sealed so sunk
costs cannot renegotiate it:

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
Whatever exists when the budget ends is what the campaign freezes and
judges — **the campaign runs either way**; a tail phase that fails its dev
bar produces an honest sealed FAIL, not an extension. Every attempt (incl.
failures) goes in the evidence pack.

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

1. Owner approves this note (and sets: K, the D2 budget if different, the
   D3 scenario thresholds or delegates their tabling to the seal event).
2. Pre-seal repairs, committed before the campaign block is written: the
   promotion-script AND fix (+ its test); the conditional-delivery metric
   implementation (+ tests) — the judge must exist to be hashed.
3. **The seal event**: campaign-4 block in `pre-registration.yaml` — rule
   text, thresholds, D2 budget, committee construction, checkpoint-hash
   placeholders declared as planned arrivals — all three locks re-sealed
   in one commit with superseded digests recorded.
4. Tail-calibration phase (≤ 4 working days, D2).
5. Train K fresh seeds under the final recipe; freeze; hashes join the
   seal by dated amendment (planned arrival, post_hoc false).
6. Batteries + severe legs + conditional-delivery grids, both systems.
7. Verdict via the fixed script; evidence doc; owner receives the result.

**Timeline: best case ~7 working days, capped case ~12.** Owner
touchpoints: steps 1, 3 (ratify), 7 (receive) — roughly an hour each.
Collagist product work continues in the main tree throughout; the GPU
belongs to the campaign.

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
