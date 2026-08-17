# Spine v2 - anti-test sweep results (run BEFORE the seal)

Produced by `scripts/spine_v2_antitest.py`, which imports the real judges from `scripts/spine_v2_report.py` and the real thresholds through `sealed_from_anchors` - the same assembly the seal writes. Machine-readable values: `docs/superpowers/specs/spine-v2-antitest-results.json`.

**The obligation.** exam section 6.1: before a judge is sealed, sweep the model property the judge claims to measure and confirm the judge's pass rate increases in it.

**The rule.** one-sided bars (O1, A1, A2) are swept on the effect itself, from absent to history's own level, and the pass rate must not fall along it. Two-sided bars (T1, D1-D4) are swept on CLOSENESS to the historical anchor, because a raw sweep of a two-sided bar would correctly fall at the top and prove nothing: D1-D4 do it by generating half the batches a fixed distance above the anchor and half the same distance below it at each grid point, and T1 does it by running a raw parameter grid that spans both sides and then re-ordering the points by how far the REALIZED lift sits from history's, normalised by the band's own half-width on that side (its band is not symmetric around the anchor). T1 additionally gets the one-sided sweep, because that is the literal B1 v2 comparison.

**Size.** 24 batches per grid point, 50 decades per batch (the campaign's own sealed batch size), 120 months per decade. One literal seed per sweep, all distinct; re-running reproduces the JSON byte for byte.

**Verdict: every sweep is monotone non-decreasing.**

## T1_directional - the probability that a tight-policy episode causes a downturn within a year

| effect | pass rate | mean pooled transmission lift |
|---|---|---|
| 0 | **0.00** | 1.0025 |
| 0.2 | **0.12** | 1.4581 |
| 0.4 | **0.46** | 1.7640 |
| 0.6 | **0.75** | 1.9123 |
| 0.8 | **0.96** | 2.1719 |
| 1 | **1.00** | 2.2570 |

Monotone non-decreasing: **yes**.

The literal B1 v2 comparison: a judge whose pass rate falls as the modelled effect grows toward history's is measuring something other than the effect.

## T1_closeness - closeness of the realized transmission lift to history's 2.3719x, spanning both sides of the band

| effect | pass rate | mean pooled transmission lift |
|---|---|---|
| p_cause=0.0, background=0.012 | **0.00** | 1.0250 |
| p_cause=0.3, background=0.012 | **0.17** | 1.5884 |
| p_cause=0.6, background=0.012 | **0.88** | 1.9870 |
| p_cause=1.0, background=0.012 | **1.00** | 2.2222 |
| p_cause=1.0, background=0.006 | **1.00** | 2.5952 |
| p_cause=1.0, background=0.0018 | **0.96** | 2.9590 |
| p_cause=1.0, background=0.0, gap=(60, 110) | **0.00** | 7.0546 |

Pass rate re-ordered from the farthest realized lift to the closest: **[0.00, 0.00, 0.17, 0.88, 0.96, 1.00, 1.00]**.

Monotone non-decreasing: **yes**.

The raw grid is re-ordered by the realized lift's distance from history's, so the monotonicity claim is about closeness and not about the synthetic parameter; the raw pass_rate row is published beside it and does fall at the top, which is the two-sided band working as intended.

## O1 - the probability that a season change follows the clock's order

| effect | pass rate | mean pooled clockwise fraction |
|---|---|---|
| 0 | **0.00** | 0.0000 |
| 0.15 | **0.00** | 0.1498 |
| 0.3 | **0.00** | 0.3019 |
| 0.45 | **0.00** | 0.4498 |
| 0.6 | **1.00** | 0.6075 |
| 0.75 | **1.00** | 0.7508 |
| 0.9 | **1.00** | 0.9012 |

Monotone non-decreasing: **yes**.

## D1 - closeness of the generated recession spell median to history's decade-pooled 2 months, both directions

| miss from anchor | pass rate | mean pooled completed-spell median, months |
|---|---|---|
| 8 | **0.50** | 5.5000 |
| 6 | **0.50** | 4.5000 |
| 4 | **0.50** | 3.5000 |
| 3 | **1.00** | 3.0000 |
| 2 | **1.00** | 2.5000 |
| 1 | **1.00** | 2.0000 |
| 0 | **1.00** | 2.0000 |

Monotone non-decreasing: **yes**.

## D2 - closeness of the generated stagflation spell median to history's decade-pooled 4 months, both directions

| miss from anchor | pass rate | mean pooled completed-spell median, months |
|---|---|---|
| 8 | **0.50** | 6.5000 |
| 6 | **0.50** | 5.5000 |
| 4 | **0.50** | 4.5000 |
| 3 | **1.00** | 4.0000 |
| 2 | **1.00** | 4.0000 |
| 1 | **1.00** | 4.0000 |
| 0 | **1.00** | 4.0000 |

Monotone non-decreasing: **yes**.

## D3 - closeness of the generated recovery spell median to history's decade-pooled 5 months, both directions

| miss from anchor | pass rate | mean pooled completed-spell median, months |
|---|---|---|
| 8 | **0.00** | 7.0000 |
| 6 | **0.00** | 6.0000 |
| 4 | **0.00** | 5.0000 |
| 3 | **1.00** | 5.0000 |
| 2 | **1.00** | 5.0000 |
| 1 | **1.00** | 5.0000 |
| 0 | **1.00** | 5.0000 |

Monotone non-decreasing: **yes**.

## D4 - closeness of the generated expansion spell median to history's decade-pooled 4 months, both directions

| miss from anchor | pass rate | mean pooled completed-spell median, months |
|---|---|---|
| 8 | **0.50** | 6.5000 |
| 6 | **0.50** | 5.5000 |
| 4 | **0.50** | 4.5000 |
| 3 | **1.00** | 4.0000 |
| 2 | **1.00** | 4.0000 |
| 1 | **1.00** | 4.0000 |
| 0 | **1.00** | 4.0000 |

Monotone non-decreasing: **yes**.

## A1 - the commodities-minus-bonds excess, in pp/yr, added when inflation is high

| effect | pass rate | mean pooled spread(high) minus spread(low), pp/yr |
|---|---|---|
| -4 | **0.00** | -4.4182 |
| -2 | **0.08** | -2.0763 |
| 0 | **0.46** | -0.0139 |
| 1 | **0.79** | 1.2928 |
| 2 | **0.96** | 3.0629 |
| 3.5 | **1.00** | 3.8957 |
| 5 | **1.00** | 5.5232 |

Monotone non-decreasing: **yes**.

## A2 - the stock-bond correlation imposed on high-inflation months

| effect | pass rate | mean pooled high-minus-low stock-bond correlation difference |
|---|---|---|
| -0.1 | **0.00** | -0.0927 |
| 0 | **0.00** | -0.0016 |
| 0.1 | **0.00** | 0.1039 |
| 0.2 | **0.21** | 0.2003 |
| 0.3 | **0.96** | 0.3008 |
| 0.45 | **1.00** | 0.4538 |
| 0.6 | **1.00** | 0.6025 |

Monotone non-decreasing: **yes**.

