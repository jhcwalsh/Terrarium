# Spine-conditioned compiler pilot -- measurement results (Task 7)

Sealed thresholds: `docs/superpowers/specs/spine-pilot-prereg.json` (commit `c9bd036`). World: `src/ah/presets/spine_pilot.json` (`00000000-0000-4000-9000-000000000802`, "The Hard Landing"). Sensitivity seeds: [199002, 1199005, 2199008, 3199011, 4199014]. `n_paths=20` per seed.

## Verdict summary

| seed | B1 | B2 | B4 | B5 | B6 |
|---|---|---|---|---|---|
| 199002 | FAIL | PASS | FAIL | FAIL | INCONCLUSIVE (construct mismatch) |
| 1199005 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE (construct mismatch) |
| 2199008 | FAIL | FAIL | FAIL | PASS | INCONCLUSIVE (construct mismatch) |
| 3199011 | FAIL | FAIL | FAIL | PASS | INCONCLUSIVE (construct mismatch) |
| 4199014 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE (construct mismatch) |
| **ALL** | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE (construct mismatch) |

ALL-seed conjunction rule: B1/B2/B4/B5 are AND across seeds. B6's three-way conjunction: any seed FAIL dominates (a real construct-matched failure); else any seed INCONCLUSIVE dominates; else PASS.

## B1 -- reaction function

| seed | fraction of decades passing | threshold | verdict |
|---|---|---|---|
| 199002 | 0.1500 | >= 0.90 | FAIL |
| 1199005 | 0.1000 | >= 0.90 | FAIL |
| 2199008 | 0.1000 | >= 0.90 | FAIL |
| 3199011 | 0.1500 | >= 0.90 | FAIL |
| 4199014 | 0.1500 | >= 0.90 | FAIL |

## B2 -- era coherence

| seed | n_joins | max join YoY jump (pp) | bound (pp) | p95 adjacent YoY (pp) | bound (pp) | verdict |
|---|---|---|---|---|---|---|
| 199002 | 118 | 2.3453 | 2.5000 | 0.9128 | 0.9292 | PASS |
| 1199005 | 144 | 5.7020 | 2.5000 | 0.9717 | 0.9292 | FAIL |
| 2199008 | 132 | 9.5904 | 2.5000 | 0.9200 | 0.9292 | FAIL |
| 3199011 | 153 | 2.5000 | 2.5000 | 0.9782 | 0.9292 | FAIL |
| 4199014 | 187 | 2.8719 | 2.5000 | 1.0822 | 0.9292 | FAIL |

## B4 -- persistence and the clock's order

### seed 199002

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 54 | 3.0 | 5.0 | 0.600 | [0.6, 1.4] | PASS |
| stagflation | 83 | 6.0 | 4.0 | 1.500 | [0.6, 1.4] | FAIL |
| recovery | 65 | 4.0 | 9.0 | 0.444 | [0.6, 1.4] | FAIL |
| expansion | 90 | 5.0 | 6.0 | 0.833 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4706 (128/272 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 1199005

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 73 | 3.0 | 5.0 | 0.600 | [0.6, 1.4] | PASS |
| stagflation | 105 | 4.0 | 4.0 | 1.000 | [0.6, 1.4] | PASS |
| recovery | 86 | 2.5 | 9.0 | 0.278 | [0.6, 1.4] | FAIL |
| expansion | 108 | 5.0 | 6.0 | 0.833 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4915 (173/352 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 2199008

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 61 | 3.0 | 5.0 | 0.600 | [0.6, 1.4] | PASS |
| stagflation | 109 | 3.0 | 4.0 | 0.750 | [0.6, 1.4] | PASS |
| recovery | 76 | 3.0 | 9.0 | 0.333 | [0.6, 1.4] | FAIL |
| expansion | 115 | 4.0 | 6.0 | 0.667 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.5044 (172/341 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 3199011

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 63 | 4.0 | 5.0 | 0.800 | [0.6, 1.4] | PASS |
| stagflation | 93 | 4.0 | 4.0 | 1.000 | [0.6, 1.4] | PASS |
| recovery | 54 | 2.5 | 9.0 | 0.278 | [0.6, 1.4] | FAIL |
| expansion | 91 | 6.0 | 6.0 | 1.000 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4840 (136/281 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 4199014

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 56 | 2.5 | 5.0 | 0.500 | [0.6, 1.4] | FAIL |
| stagflation | 96 | 5.0 | 4.0 | 1.250 | [0.6, 1.4] | PASS |
| recovery | 54 | 4.0 | 9.0 | 0.444 | [0.6, 1.4] | FAIL |
| expansion | 93 | 5.0 | 6.0 | 0.833 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4946 (138/279 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

## B5 -- hazard realism

### seed 199002

| quadrant | onsets | months | realized rate | panel rate | panel cell months | eligible | rel error | pass |
|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 258 | 0.0039 | 0.0108 | 93 | True | 0.640 | FAIL |
| 1 | 44 | 480 | 0.0917 | 0.0702 | 57 | True | 0.306 | PASS |
| 2 | 0 | 518 | 0.0000 | 0.0000 | 378 | True | n/a | PASS |
| 3 | 6 | 642 | 0.0093 | 0.0043 | 234 | True | 1.187 | FAIL |

B5 overall: FAIL

### seed 1199005

| quadrant | onsets | months | realized rate | panel rate | panel cell months | eligible | rel error | pass |
|---|---|---|---|---|---|---|---|---|
| 0 | 6 | 291 | 0.0206 | 0.0108 | 93 | True | 0.918 | FAIL |
| 1 | 40 | 566 | 0.0707 | 0.0702 | 57 | True | 0.007 | PASS |
| 2 | 0 | 391 | 0.0000 | 0.0000 | 378 | True | n/a | PASS |
| 3 | 3 | 655 | 0.0046 | 0.0043 | 234 | True | 0.072 | PASS |

B5 overall: FAIL

### seed 2199008

| quadrant | onsets | months | realized rate | panel rate | panel cell months | eligible | rel error | pass |
|---|---|---|---|---|---|---|---|---|
| 0 | 2 | 248 | 0.0081 | 0.0108 | 93 | True | 0.250 | PASS |
| 1 | 41 | 516 | 0.0795 | 0.0702 | 57 | True | 0.132 | PASS |
| 2 | 0 | 429 | 0.0000 | 0.0000 | 378 | True | n/a | PASS |
| 3 | 2 | 750 | 0.0027 | 0.0043 | 234 | True | 0.376 | PASS |

B5 overall: PASS

### seed 3199011

| quadrant | onsets | months | realized rate | panel rate | panel cell months | eligible | rel error | pass |
|---|---|---|---|---|---|---|---|---|
| 0 | 2 | 357 | 0.0056 | 0.0108 | 93 | True | 0.479 | PASS |
| 1 | 40 | 462 | 0.0866 | 0.0702 | 57 | True | 0.234 | PASS |
| 2 | 0 | 269 | 0.0000 | 0.0000 | 378 | True | n/a | PASS |
| 3 | 4 | 867 | 0.0046 | 0.0043 | 234 | True | 0.080 | PASS |

B5 overall: PASS

### seed 4199014

| quadrant | onsets | months | realized rate | panel rate | panel cell months | eligible | rel error | pass |
|---|---|---|---|---|---|---|---|---|
| 0 | 2 | 258 | 0.0078 | 0.0108 | 93 | True | 0.279 | PASS |
| 1 | 35 | 515 | 0.0680 | 0.0702 | 57 | True | 0.032 | PASS |
| 2 | 0 | 382 | 0.0000 | 0.0000 | 378 | True | n/a | PASS |
| 3 | 7 | 802 | 0.0087 | 0.0043 | 234 | True | 1.042 | FAIL |

B5 overall: FAIL

## B6 -- transmission (three-way outcome)

| seed | value (spine conditional) | panel conditional | panel unconditional | rel error | sign ok | spine base rate | panel base rate | base rate ratio | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 199002 | 0.4913 | 0.2215 | 0.0773 | 1.2183 | PASS | 0.7981 (1724/2160) | 0.1833 (149/813) | 4.355 | INCONCLUSIVE (construct mismatch) |
| 1199005 | 0.4794 | 0.2215 | 0.0773 | 1.1645 | PASS | 0.8083 (1746/2160) | 0.1833 (149/813) | 4.411 | INCONCLUSIVE (construct mismatch) |
| 2199008 | 0.5100 | 0.2215 | 0.0773 | 1.3028 | PASS | 0.9250 (1998/2160) | 0.1833 (149/813) | 5.047 | INCONCLUSIVE (construct mismatch) |
| 3199011 | 0.4388 | 0.2215 | 0.0773 | 0.9814 | PASS | 0.8514 (1839/2160) | 0.1833 (149/813) | 4.645 | INCONCLUSIVE (construct mismatch) |
| 4199014 | 0.4500 | 0.2215 | 0.0773 | 1.0318 | PASS | 0.6574 (1420/2160) | 0.1833 (149/813) | 3.587 | INCONCLUSIVE (construct mismatch) |

Sealed disclosure: panel conditioning (curve inversion) covers 149/813 months; the spine-side conditioning fraction is unpinned; the Task-7 report MUST print both base rates, and a B6 FAIL with base rates differing by more than 2x is recorded as INCONCLUSIVE (construct mismatch), not a compiler defect

## Occupancy and corrections (no silent caps)

### seed 199002

- spine attempts: 245
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[2, 4, 4, 3, 2, 2, 1, 4, 3, 2, 4, 3, 3, 2, 5, 0, 2, 3, 1, 1]`
- per_quadrant_onsets: `[1, 44, 0, 6]`
- per_quadrant_months: `[258, 480, 518, 642]`
- forced_reentries: 1
- unfiltered_reentries: 1

### seed 1199005

- spine attempts: 260
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@17.5': 10, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@17.5': 46, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@17.5': 18, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[1, 2, 2, 0, 2, 1, 3, 5, 0, 3, 1, 2, 3, 3, 5, 1, 4, 5, 3, 3]`
- per_quadrant_onsets: `[6, 40, 0, 3]`
- per_quadrant_months: `[291, 566, 391, 655]`
- forced_reentries: 2
- unfiltered_reentries: 1

### seed 2199008

- spine attempts: 265
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@17.5': 10, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@17.5': 18, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[2, 3, 5, 2, 3, 2, 0, 4, 0, 3, 0, 3, 2, 3, 2, 3, 1, 4, 2, 1]`
- per_quadrant_onsets: `[2, 41, 0, 2]`
- per_quadrant_months: `[248, 516, 429, 750]`
- forced_reentries: 2
- unfiltered_reentries: 2

### seed 3199011

- spine attempts: 239
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@17.5': 46, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@17.5': 68, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[2, 4, 1, 2, 4, 2, 0, 2, 3, 1, 3, 1, 3, 2, 6, 4, 2, 2, 1, 1]`
- per_quadrant_onsets: `[2, 40, 0, 4]`
- per_quadrant_months: `[357, 462, 269, 867]`
- forced_reentries: 2
- unfiltered_reentries: 0

### seed 4199014

- spine attempts: 269
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[4, 3, 3, 1, 4, 2, 0, 2, 0, 5, 1, 3, 1, 2, 1, 3, 3, 2, 0, 4]`
- per_quadrant_onsets: `[2, 35, 0, 7]`
- per_quadrant_months: `[258, 515, 382, 802]`
- forced_reentries: 1
- unfiltered_reentries: 1

## Sealed disclosures (quoted verbatim)

- B4 power disclosure: stagflation's dwell median rests on 12 spells and the clockwise anchor on 68 transitions (SE ~0.059); tolerances are near the anchors' own sampling noise - a marginal B4 result must be read accordingly; tolerances must NOT be widened after measurement
- B5 zero-rate convention: a panel rate of exactly 0 passes iff the realized rate is exactly 0; note the recovery cell is tautological (the sampler cannot fire at rate 0), so a PASS there is a plumbing assertion, not evidence about the model
- B5 numerator disclosure: the table rests on 6 panel CRI onsets (1970-01, 1970-04, 1974-03, 2001-06, 2008-09, 2020-03); 1970 is one episode counted as two onsets and expansion's rate rests on the 1970-01 orphan blip; B5 tests the wiring, not the hazard model
- B6 base-rate disclosure: panel conditioning (curve inversion) covers 149/813 months; the spine-side conditioning fraction is unpinned; the Task-7 report MUST print both base rates, and a B6 FAIL with base rates differing by more than 2x is recorded as INCONCLUSIVE (construct mismatch), not a compiler defect
- Severity table disclosure: the either/both inflation condition equals the quadrant hot bit; discrimination in practice is on credit_gap (owner ruling 2026-08-16: keep for pilot, revisit at D-SP-1)

## B3 -- the over-commitment grid under spine worlds (Task 8)

Method citation: `docs/superpowers/specs/2026-08-15-e1-overcommitment-measurement.md` (the E1 declaration, world `...703`), ported VERBATIM onto world `...802` -- same four allocation arms, same 20-seed ladder harness (`199002 + 7919*k`, world 802's own base seed and the platform's own per-path stride), same book construction (cash fixed at 2; private sleeves scaled from 20/8/7; liquid sleeves scaled from 41/12/5/5), same coverage statistic (worst unfunded/liquid, breach line 1.0 -- `ah.eval.decision_metrics.liquidity_shortfall_probability`), same hold-course (no-decisions) institution run. Sealed b3 bar: `docs/superpowers/specs/spine-pilot-prereg.json` (commit `c9bd036`) -- grid `[15, 35, 40, 55]`, `min_breach_seeds_at_55=1`, `n_seeds=20`, `coverage_must_be_monotone=True`. **b3 harness postdates the seal; its method is the committed E1 declaration (2026-08-15), cited verbatim; sealed b3 thresholds unchanged.**

Seeds attempted: 20. Refusals: 0 (none).

### B3 grid table

| arm (private pts) | coverage breach (>=1.0 ever) | forced secondaries | worst coverage med . max | final min . med | seeds below 100/75/50 |
|---|---|---|---|---|---|
| 15 | 0/20 | 0/20 | 0.081 . 0.118 | 96.9 . 193.1 | 1/0/0 |
| 35 | 0/20 | 0/20 | 0.242 . 0.365 | 99.6 . 195.1 | 1/0/0 |
| 40 | 0/20 | 0/20 | 0.301 . 0.456 | 100.2 . 194.5 | 0/0/0 |
| 55 | 0/20 | 0/20 | 0.578 . 0.877 | 101.6 . 201.3 | 0/0/0 |

### Hold-course depth (arm-invariant market fact, per seed)

Median peak-to-trough equity drawdown across 20 successful seeds: **-0.3497** (-35.0%). Declared band: `[-0.4260, -0.3750]` (`[-42.6%, -37.5%]`) -- see `DEPTH_BAND` in `scripts/spine_pilot_b3.py` for the construction and citations (a documented deviation: neither the E1 doc nor the stress-03 method states a literal two-sided band).

### B3 verdict (three-part)

| check | value | threshold | verdict |
|---|---|---|---|
| (a) coverage monotone in allocation | [0.0810, 0.2420, 0.3006, 0.5776] | non-decreasing medians across the grid | PASS |
| (b) breach seeds at 55 | 0/20 | >= 1 | FAIL |
| (c) hold-course depth inside declared band | -0.3497 | [-0.4260, -0.3750] | FAIL |
| **OVERALL** |  |  | FAIL |

### Comparison against the E1 family (world 703, stress compiler, no spine)

| arm (private pts) | 703 worst coverage med . max (E1, cited) | 802 worst coverage med . max (this run) |
|---|---|---|
| 15 | 0.103 . 0.164 | 0.081 . 0.118 |
| 35 | 0.309 . 0.540 | 0.242 . 0.365 |
| 40 | 0.382 . 0.694 | 0.301 . 0.456 |
| 55 | 0.719 . 1.571 | 0.578 . 0.877 |

The E1 family's own headline reading: coverage moves 0.10 -> 1.57 across this same grid on world 703 (stress compiler, no spine). The row above lets the owner read world 802's spine-conditioned numbers against that side by side, arm for arm.

