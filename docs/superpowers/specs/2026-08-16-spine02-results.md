# Spine-02 -- measurement re-run (Task 13)

Sealed thresholds: `docs/superpowers/specs/spine02-prereg.json` (commit `d8d506c`). World: `src/ah/presets/spine_pilot.json` (`00000000-0000-4000-9000-000000000802`, "The Hard Landing"). Sensitivity seeds: [199002, 1199005, 2199008, 3199011, 4199014]. `n_paths=20` per seed. B1/B5/B6 are the v2 (Task-11-respecified) bars; B2/B4 are round one's bars, judged by the SAME frozen code (`test_v1_judges_are_frozen`).

## Verdict summary (round two)

| seed | B1 v2 | B2 | B4 | B5 v2 | B6 v2 |
|---|---|---|---|---|---|
| 199002 | FAIL | FAIL | FAIL | PASS | FAIL |
| 1199005 | FAIL | PASS | FAIL | PASS | FAIL |
| 2199008 | FAIL | FAIL | FAIL | FAIL | FAIL |
| 3199011 | FAIL | FAIL | FAIL | PASS | FAIL |
| 4199014 | FAIL | FAIL | FAIL | PASS | FAIL |
| **ALL** | FAIL | FAIL | FAIL | FAIL | FAIL |

ALL-seed conjunction rule (unchanged from round one): B1/B2/B4/B5 are AND across seeds. B6's three-way conjunction: any seed FAIL dominates (a real construct-matched failure); else any seed INCONCLUSIVE dominates; else PASS.

## Round one vs round two, side by side

| bar | round one ALL | round two ALL | same bar? |
|---|---|---|---|
| B1 | FAIL | FAIL | no -- v2 respecified |
| B2 | FAIL | FAIL | yes -- frozen v1 code |
| B4 | FAIL | FAIL | yes -- frozen v1 code |
| B5 | FAIL | FAIL | no -- v2 respecified |
| B6 | INCONCLUSIVE (construct mismatch) | FAIL | no -- v2 respecified |

Round-one verdicts cited verbatim from `docs/superpowers/specs/2026-08-15-spine-pilot-results.md`'s own summary table (the **ALL** row). B1/B5/B6 test a DIFFERENT construct in round two (see judge docstrings in `scripts/spine_pilot_report.py`), so a verdict flip there is not necessarily 'the same defect, fixed' -- B2/B4 are the one apples-to-apples comparison in this table, run through byte-identical judging code both rounds.

## Distinct-spine counts (stride-fix verification)

**Within-call** (per sensitivity seed, across its own 20 decades -- each decade within one `sample_spine` call already advances on its own attempt index, so this checks nothing was aliasing WITHIN a call):

| seed | distinct spines | n decades | spine attempts used |
|---|---|---|---|
| 199002 | 20 | 20 | 287 |
| 1199005 | 20 | 20 | 358 |
| 2199008 | 20 | 20 | 320 |
| 3199011 | 20 | 20 | 233 |
| 4199014 | 20 | 20 | 250 |

**Cross-call, the round-one collision itself** (the B3 ladder, `199002 + 7919*k`, k=0..19 -- one INDEPENDENT `sample_spine(n_decades=1, ...)` call per seed): **20/20** distinct spines. Round one measured **2/20** on this exact ladder (`k=0..18` collapsed onto one shared attempt tape; only `k=19` differed -- see round one's 'Spine multiplicity disclosure', final-review finding F3). The Task-10 fix (`ATTEMPT_STRIDE` decoupled from `SEED_STRIDE`) is what this number verifies.

## B1 v2 -- reaction function (contemporaneous lag, 0..2 months)

| seed | fraction of decades passing | threshold | verdict |
|---|---|---|---|
| 199002 | 0.4500 | >= 0.90 | FAIL |
| 1199005 | 0.3500 | >= 0.90 | FAIL |
| 2199008 | 0.4500 | >= 0.90 | FAIL |
| 3199011 | 0.5500 | >= 0.90 | FAIL |
| 4199014 | 0.5000 | >= 0.90 | FAIL |

## B2 -- era coherence (round-one bar and judge, unchanged)

| seed | n_joins | max join YoY jump (pp) | bound (pp) | p95 adjacent YoY (pp) | bound (pp) | verdict |
|---|---|---|---|---|---|---|
| 199002 | 131 | 5.3195 | 2.5000 | 0.9678 | 0.9292 | FAIL |
| 1199005 | 153 | 2.5000 | 2.5000 | 0.8938 | 0.9292 | PASS |
| 2199008 | 137 | 2.4935 | 2.5000 | 0.9658 | 0.9292 | FAIL |
| 3199011 | 154 | 2.4801 | 2.5000 | 0.9676 | 0.9292 | FAIL |
| 4199014 | 176 | 2.4871 | 2.5000 | 0.9676 | 0.9292 | FAIL |

## B4 -- persistence and the clock's order (round-one bar and judge, unchanged)

### seed 199002

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 52 | 3.0 | 5.0 | 0.600 | [0.6, 1.4] | PASS |
| stagflation | 96 | 4.0 | 4.0 | 1.000 | [0.6, 1.4] | PASS |
| recovery | 65 | 2.0 | 9.0 | 0.222 | [0.6, 1.4] | FAIL |
| expansion | 114 | 4.5 | 6.0 | 0.750 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4886 (150/307 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 1199005

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 69 | 4.0 | 5.0 | 0.800 | [0.6, 1.4] | PASS |
| stagflation | 80 | 5.0 | 4.0 | 1.250 | [0.6, 1.4] | PASS |
| recovery | 78 | 3.0 | 9.0 | 0.333 | [0.6, 1.4] | FAIL |
| expansion | 89 | 4.0 | 6.0 | 0.667 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4831 (143/296 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 2199008

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 52 | 2.0 | 5.0 | 0.400 | [0.6, 1.4] | FAIL |
| stagflation | 105 | 5.0 | 4.0 | 1.250 | [0.6, 1.4] | PASS |
| recovery | 58 | 3.0 | 9.0 | 0.333 | [0.6, 1.4] | FAIL |
| expansion | 110 | 4.0 | 6.0 | 0.667 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4820 (147/305 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 3199011

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 89 | 2.0 | 5.0 | 0.400 | [0.6, 1.4] | FAIL |
| stagflation | 103 | 3.0 | 4.0 | 0.750 | [0.6, 1.4] | PASS |
| recovery | 96 | 3.0 | 9.0 | 0.333 | [0.6, 1.4] | FAIL |
| expansion | 101 | 3.0 | 6.0 | 0.500 | [0.6, 1.4] | FAIL |

Clockwise fraction: 0.5176 (191/369 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

### seed 4199014

| quadrant | visits (spells) | median (months) | panel median | ratio | band | pass |
|---|---|---|---|---|---|---|
| recession | 57 | 2.0 | 5.0 | 0.400 | [0.6, 1.4] | FAIL |
| stagflation | 99 | 4.0 | 4.0 | 1.000 | [0.6, 1.4] | PASS |
| recovery | 68 | 2.0 | 9.0 | 0.222 | [0.6, 1.4] | FAIL |
| expansion | 113 | 4.0 | 6.0 | 0.667 | [0.6, 1.4] | PASS |

Clockwise fraction: 0.4574 (145/317 transitions) vs panel 0.6029 +/- 0.15 -> PASS
B4 overall: FAIL

## B5 v2 -- hazard realism (aggregate, normal approximation)

| seed | observed | expected | sd | margin | diff | zero_rate_ok | verdict |
|---|---|---|---|---|---|---|---|
| 199002 | 42 | 37.2706 | 5.9221 | 12.1072 | 4.7294 | True | PASS |
| 1199005 | 35 | 34.5760 | 5.7117 | 11.6948 | 0.4240 | True | PASS |
| 2199008 | 50 | 35.6056 | 5.7874 | 11.8432 | 14.3944 | True | FAIL |
| 3199011 | 40 | 38.3912 | 6.0117 | 12.2827 | 1.6088 | True | PASS |
| 4199014 | 55 | 43.9963 | 6.4285 | 13.0997 | 11.0037 | True | PASS |

## B6 v2 -- transmission (quantile-matched, three-way outcome)

| seed | value (spine conditional) | panel conditional | panel unconditional | rel error | sign ok | spine base rate | panel base rate | base rate ratio | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 199002 | 0.4775 | 0.2215 | 0.0773 | 1.1560 | PASS | 0.1852 (400/2160) | 0.1833 | 1.010 | FAIL |
| 1199005 | 0.5225 | 0.2215 | 0.0773 | 1.3592 | PASS | 0.1852 (400/2160) | 0.1833 | 1.010 | FAIL |
| 2199008 | 0.4875 | 0.2215 | 0.0773 | 1.2011 | PASS | 0.1852 (400/2160) | 0.1833 | 1.010 | FAIL |
| 3199011 | 0.5800 | 0.2215 | 0.0773 | 1.6188 | PASS | 0.1852 (400/2160) | 0.1833 | 1.010 | FAIL |
| 4199014 | 0.5850 | 0.2215 | 0.0773 | 1.6414 | PASS | 0.1852 (400/2160) | 0.1833 | 1.010 | FAIL |

## Occupancy and corrections (no silent caps)

### seed 199002

- spine attempts: 287
- distinct spines (within-call): 20/20
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@17.5': 10, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@17.5': 46, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@17.5': 68, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[3, 1, 3, 5, 1, 2, 2, 1, 3, 1, 1, 4, 1, 1, 1, 2, 4, 3, 2, 1]`
- per_quadrant_onsets: `[2, 34, 0, 6]`
- per_quadrant_months: `[268, 437, 413, 871]`
- forced_reentries: 2
- unfiltered_reentries: 2

### seed 1199005

- spine attempts: 358
- distinct spines (within-call): 20/20
- pool_occupancy: `{'0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[1, 3, 0, 2, 2, 1, 2, 4, 0, 1, 2, 0, 1, 1, 4, 2, 4, 2, 2, 1]`
- per_quadrant_onsets: `[2, 28, 0, 5]`
- per_quadrant_months: `[409, 384, 498, 756]`
- forced_reentries: 0
- unfiltered_reentries: 0

### seed 2199008

- spine attempts: 320
- distinct spines (within-call): 20/20
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[3, 2, 4, 1, 3, 2, 4, 4, 2, 4, 1, 4, 1, 2, 2, 4, 3, 1, 1, 2]`
- per_quadrant_onsets: `[2, 48, 0, 0]`
- per_quadrant_months: `[240, 420, 403, 831]`
- forced_reentries: 1
- unfiltered_reentries: 0

### seed 3199011

- spine attempts: 233
- distinct spines (within-call): 20/20
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@35': 139}`
- per_path_onsets: `[3, 3, 2, 4, 1, 3, 0, 1, 2, 3, 2, 3, 1, 3, 4, 1, 1, 1, 1, 1]`
- per_quadrant_onsets: `[4, 35, 0, 1]`
- per_quadrant_months: `[413, 445, 517, 637]`
- forced_reentries: 1
- unfiltered_reentries: 0

### seed 4199014

- spine attempts: 250
- distinct spines (within-call): 20/20
- pool_occupancy: `{'0/recession@8.75': 4, '0/recession@35': 25, '0/stagflation@8.75': 32, '0/stagflation@35': 62, '0/recovery@8.75': 5, '0/recovery@35': 58, '0/expansion@8.75': 30, '0/expansion@35': 139, '8/recession@5': 4, '8/recession@10': 4, '8/stagflation@5': 18, '8/stagflation@10': 34, '8/recovery@5': 1, '8/recovery@10': 8, '8/expansion@5': 17, '8/expansion@10': 35, '15/recession@8.75': 4, '15/recession@17.5': 10, '15/recession@35': 25, '15/stagflation@8.75': 32, '15/stagflation@17.5': 46, '15/stagflation@35': 62, '15/recovery@8.75': 5, '15/recovery@17.5': 18, '15/recovery@35': 58, '15/expansion@8.75': 30, '15/expansion@17.5': 68, '15/expansion@35': 139}`
- per_path_onsets: `[4, 0, 1, 3, 4, 4, 1, 2, 2, 6, 1, 3, 3, 2, 5, 4, 3, 3, 1, 3]`
- per_quadrant_onsets: `[3, 47, 0, 5]`
- per_quadrant_months: `[318, 532, 257, 759]`
- forced_reentries: 2
- unfiltered_reentries: 1

## Sealed disclosures (quoted verbatim)

- B4 power disclosure: stagflation's dwell median rests on 12 spells and the clockwise anchor on 68 transitions (SE ~0.059); tolerances are near the anchors' own sampling noise - a marginal B4 result must be read accordingly; tolerances must NOT be widened after measurement
- B5 v2 zero-rate convention: a panel rate of exactly 0 passes iff the realized rate is exactly 0; note the recovery cell is tautological (the sampler cannot fire at rate 0), so a PASS there is a plumbing assertion, not evidence about the model

## What changed and why

Two wiring fixes separate this round's numbers from round one's, both landed under spine-02's own authority before this seal (Task 10, commit `75e8b07`), and both verified directly above rather than merely asserted:

1. **The attempt stride was decoupled from the platform's per-path stride.** Round one's `sample_spine` advanced its climate/regimes/inflnoise attempt streams by `SEED_STRIDE` (7919) -- the SAME constant the platform uses for its own per-path ensemble seeding (`base_seed + 7919*k`, CLAUDE.md). Whenever one call's accepted attempt index landed exactly `7919*k` away from another call's base seed, the two calls' climate/regimes/inflnoise draws collided and produced BIT-IDENTICAL spines from that attempt onward (final-review finding F3). This silently collapsed the macro-storyline diversity behind an entire seed ladder to a handful of distinct spines -- round one's own B3 section measured 2/20 on the `199002 + 7919*k` ladder. `ATTEMPT_STRIDE` (a large prime, coprime to 7919) replaces `SEED_STRIDE` for the attempt loop, so no attempt index in the budget can realign two calls' streams. Re-measured above: the same ladder now reads **20/20**.
2. **`pi_actual` (fitted CPI observation noise) now feeds the policy anchor.** Round one's Taylor anchor responded only to `pi_star`, the slow-moving trend component -- the transitory inflation surprise a real policy reaction function actually chases structurally never reached it. B1 v1 therefore tested the anchor's response to `pi_star - mu_pi` at a 3..12-month lag and failed on every seed (0.10-0.15 of decades passing against a 0.90 bar). spine-02 wires `pi_actual = pi_star + eps` into `policy_anchor`, so the anchor CAN respond same-month; B1 v2 tests the response to `pi_actual - pi_star` at the model's own 0..2-month contemporaneous lag -- the window the round-one construct structurally excluded. B6 v2's quantile-matched tightness threshold (Task 11) is a separate, independently-motivated respec (matching the panel's own curve-inversion base rate per decade rather than a fixed `policy_gap > 0` cut) and does not depend on either wiring fix above.


## B3 -- the over-commitment grid under spine worlds, re-run (Task 13)

`scripts/spine_pilot_b3.py` re-run UNCHANGED against this round's (stride-fixed) tree -- the script itself is sealed and untouched; its tapes differ from round one's legitimately, because the upstream stride fix changes what `sample_spine` returns for the same seeds. Section below is copied VERBATIM from what the script itself appended to `docs/superpowers/specs/2026-08-15-spine-pilot-results.md` (its own hardcoded output path) in this run.

Distinct-spine count across this same 20-seed ladder (`199002 + 7919*k`, k=0..19), computed independently above via `sample_spine` directly: **20/20**.


## B3 -- the over-commitment grid under spine worlds (Task 8)

Method citation: `docs/superpowers/specs/2026-08-15-e1-overcommitment-measurement.md` (the E1 declaration, world `...703`), ported VERBATIM onto world `...802` -- same four allocation arms, same 20-seed ladder harness (`199002 + 7919*k`, world 802's own base seed and the platform's own per-path stride), same book construction (cash fixed at 2; private sleeves scaled from 20/8/7; liquid sleeves scaled from 41/12/5/5), same coverage statistic (worst unfunded/liquid, breach line 1.0 -- `ah.eval.decision_metrics.liquidity_shortfall_probability`), same hold-course (no-decisions) institution run. Sealed b3 bar: `docs/superpowers/specs/spine-pilot-prereg.json` (commit `c9bd036`) -- grid `[15, 35, 40, 55]`, `min_breach_seeds_at_55=1`, `n_seeds=20`, `coverage_must_be_monotone=True`. **b3 harness postdates the seal; its method is the committed E1 declaration (2026-08-15), cited verbatim; sealed b3 thresholds unchanged.**

Seeds attempted: 20. Refusals: 0 (none).

### B3 grid table

| arm (private pts) | coverage breach (>=1.0 ever) | forced secondaries | worst coverage med . max | final min . med | seeds below 100/75/50 |
|---|---|---|---|---|---|
| 15 | 0/20 | 0/20 | 0.090 . 0.149 | 73.6 . 161.3 | 3/1/0 |
| 35 | 0/20 | 0/20 | 0.282 . 0.479 | 79.7 . 188.1 | 2/0/0 |
| 40 | 0/20 | 0/20 | 0.351 . 0.611 | 81.3 . 194.6 | 1/0/0 |
| 55 | 2/20 | 0/20 | 0.664 . 1.326 | 86.1 . 213.9 | 1/0/0 |

### Hold-course depth (arm-invariant market fact, per seed)

Median peak-to-trough equity drawdown across 20 successful seeds: **-0.3809** (-38.1%). Declared band: `[-0.4260, -0.3750]` (`[-42.6%, -37.5%]`) -- see `DEPTH_BAND` in `scripts/spine_pilot_b3.py` for the construction and citations (a documented deviation: neither the E1 doc nor the stress-03 method states a literal two-sided band).

### B3 verdict (three-part)

| check | value | threshold | verdict |
|---|---|---|---|
| (a) coverage monotone in allocation | [0.0901, 0.2821, 0.3514, 0.6643] | non-decreasing medians across the grid | PASS |
| (b) breach seeds at 55 | 2/20 | >= 1 | PASS |
| (c) hold-course depth inside declared band | -0.3809 | [-0.4260, -0.3750] | PASS |
| **OVERALL** |  |  | PASS |

### Comparison against the E1 family (world 703, stress compiler, no spine)

| arm (private pts) | 703 worst coverage med . max (E1, cited) | 802 worst coverage med . max (this run) |
|---|---|---|
| 15 | 0.103 . 0.164 | 0.090 . 0.149 |
| 35 | 0.309 . 0.540 | 0.282 . 0.479 |
| 40 | 0.382 . 0.694 | 0.351 . 0.611 |
| 55 | 0.719 . 1.571 | 0.664 . 1.326 |

The E1 family's own headline reading: coverage moves 0.10 -> 1.57 across this same grid on world 703 (stress compiler, no spine). The row above lets the owner read world 802's spine-conditioned numbers against that side by side, arm for arm.

