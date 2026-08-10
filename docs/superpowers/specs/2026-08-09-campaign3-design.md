# Campaign-3 — design spec (the first campaign on the extended panel)

*Builds on `2026-08-09-campaign3-scoping.md` (owner rulings K1-K4) and
`AM-2026-08-09-002` (the span-53 ratification, which declares this campaign
the training basis for the extended panel). Status: spec for owner review;
the campaign's own pre-registration is drafted FROM this document and sealed
before any training run.*

## Objective

Retrain the generator family on the 813-month panel (1953-04..2020-12) and
race it against the extended `bootstrap-v1` under a fresh seal. A promotion
here means what G2's could not: the benchmark is no longer handicapped by
its data window, and the severe test runs on both sides.

## 1. The read-path flip (the wiring the ratification deferred)

Campaign-3's seal is where sealed code first serves the extended series.
Work items, all inside the new seal:

- `ah.data.derive` (sealed) gains extended factor reads for equity_vol,
  funding_spread, hqm_curve, ust_2y, ust_10y and fx_usd, calling the seven
  extension modules — which are ADDED TO `hashed_files` along with the
  backcast provenance artifact (the seal must cover everything that
  determines judged numbers; leaving them unhashed would be RFR-82 again).
- equity_vol pre-1986 = the ONE pinned HAR draw (seed 20260809, artifact
  sha in AM-2026-08-09-002). The draw is materialized once and its own
  sha pinned in the campaign-3 prereg.
- policy_rate applies the registered `fedfunds_pre1954` splice at read.
- Degenerate-variance guards wherever correlations/ACFs are computed over
  pegged-era fx months (near-zero variance is the era's true value; a
  correlation against a constant is undefined, and the guard must return
  a stated sentinel, never NaN propagation).
- A clean vintage carrying the new donors (VXO, CP3M, CP3M_NBER, GS1, GS3)
  — the campaign vintage is sealed as always. Weekday refresh; the Sunday
  DTWEXBGS staleness quarantine was correct behaviour, not an obstacle.
- The "nothing sealed learned the rule" tests across the extension family
  INVERT at this seal (their third state: rules ratified and wired).

## 2. Reference and thresholds (RFR-77 discipline, unchanged)

Every reference band re-derived on extended train+validation via the same
`ah.eval.reference` machinery; thresholds sealed BEFORE training, with the
judging code, in one lock. The campaign-2 bands are dead letters here —
nothing may be carried over by habit; every number is recomputed and every
carry-over is an explicit, argued choice in the prereg.

Split design: train/validation boundaries restated on the extended span
(same fractions as campaign-2 unless the prereg argues otherwise). The
holdout question is K1's, below — there is NO holdout from the past.

## 3. The K-rulings, operationalized

- **K1 (holdout):** the prereg seals a future-accruing holdout rule — data
  first published after 2026-08 is untouchable until 2029-01 at the
  earliest, one read, WP5.6's protocol shape (spec sealed before reading;
  publish both ways; nothing re-runs).
- **K2 (commodities):** `aqr.cmdty_ew_tr` activates via its own
  block_addition with thresholds derived on the extended reference. First
  campaign to see the factor; REG licence caveats ride every artifact; the
  commodities-close amendment (drafted in governance/proposed/) is ratified
  as part of the campaign-3 seal event.
- **K3 (HAR ablation):** the cell grid includes a MASKED variant
  (equity_vol treated as missing pre-1986) so the
  learning-from-our-own-reconstruction effect is a measured number. The
  comparison is reported in the campaign evidence; the prereg states in
  advance what difference magnitude would demote the included variant.
- **K4 (hardware):** training does not start until the owner picks the
  host. CPU feasibility: ~2.2h per flow cell (measured); the campaign-2
  grid shape (5 systems x 3 seeds) puts a CPU campaign at multiple days
  of wall-clock. WSL2/GPU host halves nothing on paper until benchmarked —
  the decision is cost/patience, not correctness.

## 4. The race

- Systems: bootstrap-v1 (extended span, now with 1973-74 and stagflation
  in its draw universe) vs hier-flow-v2 (retrained) — plus the ablation
  family incl. the K3 masked cell. hier-diffusion retrain is optional and
  the prereg must say whether it races.
- Decision rule: the G2 four-clause shape restated on the new reference;
  the draw-span bias clause DIES (the handicap it disclosed is gone) and
  is replaced by a proxy-share disclosure clause: every verdict table
  reports the per-factor proxy share of the months that produced it.
- Severe test: exclude the 1970s, regenerate from the 1965 state, compare
  1966-84 — POSABLE FOR BOTH SIDES for the first time. The prereg pins
  the protocol AND a decision criterion this time (RFR-77's lesson: a
  procedure without a criterion judges nothing).

## 5. Order of work

1. Clean weekday refresh -> sealed campaign-3 vintage.
2. Wiring WP (sec.1) behind campaign-3 branch; extension-family test
   inversions; full gate.
3. Reference + threshold derivation on the extended panel; prereg drafted
   (this spec -> YAML); owner reviews.
4. SEAL (hashes: prereg, factors.yaml, judged sources + the seven
   extension modules + pinned artifacts). Owner ratifies commodities-close
   in the same event.
5. K4 hardware call -> train -> battery -> race -> verdict, the G2
   machinery end to end.

## Honesty clauses carried forward

Proxy months are flagged at source and disclosed in every table; the HAR
months are model output and say so; the campaign-2 record is untouched and
its reproducibility ends only at the moment the campaign-3 seal changes the
read path — recorded then, in the amendment that does it, not discovered
later.
