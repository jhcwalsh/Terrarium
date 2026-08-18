# D-SP-11 - anti-test results for `S1` (run BEFORE the seal)

Produced by `scripts/stage2_rulers_antitest.py`, which imports the real judge from `scripts/stage2_rulers.py` and the real threshold block through `sealed_from_sources` - the same single assembly path the seal writes. Machine-readable values: `docs/superpowers/specs/stage2-rulers-antitest-results.json`.

**The obligation.** exam section 6.1, carried into D-SP-11: before a judge is sealed, sweep the property the judge claims to measure and confirm the pass rate increases in it. D-SP-11's charter adds two: a seam-worsening sweep must fail the bar monotonically, and a seam-hiding-by-noise-inflation attack must also fail

**The rule.** S1 asks whether a seam is DISTINGUISHABLE from an ordinary historical month-transition, which is a two-sided property, so its pass region is an interval and a single sweep of 'more of the effect' would be non-monotone by construction. Each sweep therefore runs TOWARD fidelity from one side and the pass rate must not fall. The noise-inflation attack is a CONTROL: its pass rate is required to be zero and its failure required to be on the upper side of the texture half, so it is excluded from the monotonicity gate and carries its own boolean

**Size.** 12 worlds per grid point, 50 decades of 120 months each - the campaign's own batch shape. Every world is a row tape over the REAL panel, so the judge's band is cut from the same anchor the measurement will use. One literal seed per construct, all distinct.

**Verdict: every sweep is monotone non-decreasing and both controls hold.**

## Sweeps

### `S1_seam_inflation`

seam jumps shrinking from 3x history's own scale down to history's own scale (the charter's seam-worsening sweep, read from its good end).

| grid point | S1 pass rate | seam half | texture half | mean margin |
|---|---|---|---|---|
| 3 | **0.00** | 0.00 | 1.00 | -8.607 |
| 2 | **0.00** | 0.00 | 1.00 | -4.103 |
| 1.5 | **0.00** | 0.00 | 1.00 | -1.775 |
| 1.2 | **0.00** | 0.00 | 1.00 | -0.386 |
| 1 | **1.00** | 1.00 | 1.00 | +0.336 |

Monotone non-decreasing: **yes**

### `S1_seam_oversmoothing`

seam jumps growing from a fifth of history's own scale up to it -- the other way a seam becomes findable, by being unnaturally smooth.

| grid point | S1 pass rate | seam half | texture half | mean margin |
|---|---|---|---|---|
| 0.2 | **0.00** | 0.00 | 1.00 | -3.025 |
| 0.4 | **0.00** | 0.00 | 1.00 | -2.179 |
| 0.6 | **0.00** | 0.00 | 1.00 | -1.256 |
| 0.8 | **0.00** | 0.00 | 1.00 | -0.374 |
| 1 | **1.00** | 1.00 | 1.00 | +0.304 |

Monotone non-decreasing: **yes**

### `S1_texture_roughening`

block entries widening from the panel's most violent decile back to the whole panel, with the seams held at history's own scale throughout.

| grid point | S1 pass rate | seam half | texture half | mean margin |
|---|---|---|---|---|
| 0.9 | **0.00** | 0.00 | 0.00 | -0.399 |
| 0.75 | **0.00** | 0.83 | 0.00 | -0.221 |
| 0.5 | **0.42** | 1.00 | 0.42 | -0.013 |
| 0.25 | **1.00** | 1.00 | 1.00 | +0.088 |
| 0 | **1.00** | 1.00 | 1.00 | +0.295 |

Monotone non-decreasing: **yes**

## Controls

### `S1_noise_inflation_attack`

seams at 1.3x history's own scale, camouflaged by drawing every block entry from progressively more violent stretches of the panel so the world's own months move as much as its splices do

*Requirement.* three things, and all three are needed for the control to say anything. (1) S1's pass rate must be ZERO at every rung -- the attack never works. (2) The camouflage must actually fool the self-referential bar S1 refuses to be, at a strictly positive rate, or the attack is a strawman and barring it proves nothing. (3) At the rung where the camouflage works best, S1's TEXTURE half must fail on the UPPER side in every replicate: the roughening that hides the seams is exactly what S1 catches.

- S1 pass rate: **0.00**
- texture fails above rate: **1.00**
- self referential bar pass rate: **0.50**
- Holds: **yes**

### `S1_history_identity`

fifty contiguous 120-month stretches of the real panel.

*Requirement.* must PASS every replicate, with the seam half vacuous. A bar that fails a world which IS history is measuring itself and no other reading of it is honest.

- S1 pass rate: **1.00**
- seam half vacuous rate: **1.00**
- Holds: **yes**

## What is NOT swept, and why

A1R is not swept and cannot be: it is A1's own statistic and A1's own carried containment band read on a larger batch, so there is no new judging rule to anti-test -- what changed is the batch size, and its adequacy is a power calculation rather than a sweep. The twelve sealed bars are byte-frozen and are deliberately not re-swept, the reason a carried bar exists
