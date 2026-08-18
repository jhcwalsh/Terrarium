# Stage 2 - anti-test sweep results (run BEFORE the seal)

Produced by `scripts/stage2_antitest.py`, which imports the real judges from `scripts/stage2_report.py` and the real thresholds through `sealed_from_anchors` - the same single assembly path the seal writes. Machine-readable values: `docs/superpowers/specs/stage2-antitest-results.json`.

**The obligation.** exam section 6.1, carried into the stage-2 delta: before a judge is sealed, sweep the model property the judge claims to measure and confirm the judge's pass rate increases in it; plus the four per-bar obligations the stage-2 design document adds for P1 and for P2.

**The rule.** P1's bar is one-sided from below, so its sweep runs the coupling from absent to total and the pass rate must not fall. P2's bar is TWO-SIDED, so its loading sweep is evaluated over the sub-range where the share is still inside the band -- the design document's own wording -- and a separate closeness sweep, half the batches above the anchor and half below, carries the two-sided claim. The noise-shrink attack is a CONTROL and not a sweep: its pass rate is required to FALL, and to fall on the upper side, so it is excluded from the monotonicity gate and carries its own required boolean.

**Size.** 24 batches per grid point, 50 decades per batch (the campaign's own sealed batch size), 120 months per decade. One literal seed per sweep, all distinct; re-running reproduces the JSON byte for byte.

**Verdict: every sweep is monotone non-decreasing and every control holds.**

## Sweeps

### P1_coupling - the fraction of a decade over which the inflation dial is a lagged copy of the growth axis rather than an independent process (10-month lag)

| effect | pass rate | mean binding margin |
|---|---|---|
| 0 | **0.17** | -0.0351 |
| 0.15 | **0.54** | 0.0015 |
| 0.3 | **0.96** | 0.0398 |
| 0.5 | **1.00** | 0.0799 |
| 0.7 | **1.00** | 0.1496 |
| 0.85 | **1.00** | 0.2024 |
| 1 | **1.00** | 0.2498 |

Monotone non-decreasing: **yes**; saturates at **0.5**.

The design document requires the SATURATION point reported, because both prior campaigns found bars that rise and then fall in their own mechanism's strength. Here the departure keeps rising past the point the pass rate saturates, so the bar is not on a plateau it could slide off.

### P1_coupling_lag_sensitivity - the same coupling sweep at seven and thirteen months instead of ten -- M3 measures ten and says the panel does not pin it, so the judge's response must not depend on which lag inside the hump the engine happens to use

| effect | pass rate | mean binding margin at full coupling |
|---|---|---|
| lag_7m | **1.00** | 0.3650 |
| lag_13m | **1.00** | 0.0600 |

Monotone non-decreasing: **yes**.

### P2_loadings - the scale on the three economic curve loadings, from none to history's own level -- the endogenous loadings c_i, c_x and lam_u swept together

| effect | pass rate | mean strict economic share of the generated slope's variance |
|---|---|---|
| 0 | **0.00** | 0.0000 |
| 0.25 | **0.00** | 0.0707 |
| 0.5 | **0.00** | 0.2321 |
| 0.75 | **0.62** | 0.4009 |
| 0.9 | **1.00** | 0.4846 |
| 1 | **1.00** | 0.5477 |

Mean economic share along the grid: [0.0000, 0.0707, 0.2321, 0.4009, 0.4846, 0.5477].

Monotone non-decreasing: **yes**; saturates at **0.9**.

The obligation is stated as 'the measured economic share must rise monotonically and the pass rate must be non-decreasing OVER THE RANGE WHERE THE SHARE IS INSIDE THE BAND', because the bar is two-sided and a raw sweep would correctly fall once the share leaves the band from above. Both halves are checked separately and both are recorded.

### P2_closeness - closeness of the generated economic share to history's 0.5587, half the batches that far above it and half that far below

| effect | pass rate | mean strict economic share of the generated slope's variance |
|---|---|---|
| 0.35 | **0.00** | 0.5559 |
| 0.25 | **0.00** | 0.5568 |
| 0.15 | **0.46** | 0.5589 |
| 0.08 | **1.00** | 0.5532 |
| 0.03 | **1.00** | 0.5651 |
| 0 | **1.00** | 0.5539 |

Monotone non-decreasing: **yes**.

The v2 D-bar pattern, applied to a two-sided share: a judge that is not maximised at the anchor fails this, which is the B1 v2 defect translated to a two-sided bar. The grid is ordered largest-miss-first, so a correct judge's rates are non-decreasing.

## Controls

A control is not a sweep: its pass rate is *required* to behave in a particular way rather than to be monotone, so each carries its own requirement and its own boolean. The seal refuses to write if any of them is false.

### P1_null_engine - HOLDS

**Obligation.** at zero coupling the dials are independent by construction and P1 must return a FAIL; if it does not, the judge is broken.

**Requirement.** reading (a): the measured departure at zero coupling is within its own Monte Carlo standard error of zero, on both move types. Reading (b) -- that the null engine never passes -- is arithmetically unreachable for a counting statistic at a finite batch size (it is the bar's SIZE, and no bar in this exam was ever asked for zero size), so it is measured and disclosed rather than required.

**Reading (a) -- is the judge centred on the null?**

| move type | mean departure | standard error | as a fraction of the threshold |
|---|---|---|---|
| growth_flip | -0.00008 | 0.00178 | -0.002 |
| inflation_crossing | -0.00011 | 0.00182 | -0.003 |

**Reading (b) -- the size of the bar.** False-positive rate against an engine whose dials are independent by construction, over 300 batches of 50 decades: **0.090** at the sealed thresholds.

| candidate threshold | size |
|---|---|
| `construct__windowed_disjoint` | 0.003 |
| `construct__windowed_overlapping` | 0.013 |
| `label_dial_arm__baseline` | 0.013 |
| `label_dial_arm__growth_line_minus_50bp` | 0.003 |
| `label_dial_arm__growth_line_plus_50bp` | 0.007 |
| `label_dial_arm__inflation_line_minus_50bp` | 0.090 |
| `label_dial_arm__inflation_line_plus_50bp` | 0.027 |
| `label_dial_arm__inflation_minus_growth_minus` | 0.047 |
| `label_dial_arm__inflation_minus_growth_plus` | 0.060 |
| `label_dial_arm__inflation_plus_growth_minus` | 0.010 |
| `label_dial_arm__inflation_plus_growth_plus` | 0.013 |

The false-positive rate against an engine whose dials are independent by construction, at the sealed batch size of 50 decades. Sealing at the SOFTEST candidate (ruling SQ7) buys reach against a correct engine and pays for it here; the number at the recommended construct's own candidate is published beside it so the trade is visible.

### P1_scramble - HOLDS

**Obligation.** phase-scramble a generated batch that PASSES and confirm the statistic falls back to the null -- proof the bar measures alignment and not some other property of the batch.

**Requirement.** the coupled batch passes; after the scramble the mean departure is below the sealed threshold on both move types and is at most one tenth of its pre-scramble value; and the pass rate falls. NOT 'to exactly zero': a scrambled batch is an uncoupled batch, so what its pass rate must fall to is the bar's own size, and demanding third-decimal agreement would be demanding the control prove something the obligation never claimed.

Pass rate before the scramble **1.00**, after **0.123** over 300 batches.

| move type | mean departure before | after | its standard error |
|---|---|---|---|
| growth_flip | 0.2904 | **-0.0010** | 0.0021 |
| inflation_crossing | 0.2849 | **-0.0007** | 0.0021 |

Both construction choices in this control were got wrong first and each moved the answer by more than the residual it was measuring -- one shift for the whole batch left a mean departure of 0.054 and a 58% pass rate, and a guarded per-decade shift left +0.019 / +0.023 and 23%. Both artifacts are the shift SET, not the judge; the docstring on _scramble records why.

### P1_retro - HOLDS

**Obligation.** judge every engine on the record with the new judge; all must fail. A new bar that passes an engine already established as uncoupled is void.

**Requirement.** no recorded engine passes.

| engine / arm | growth flips | inflation crossings | passes? |
|---|---|---|---|
| `feedback__premise_accepted` | 0.003562 | 0.008818 | **no** |
| `feedback__unconditional` | 0.008931 | 0.036226 | **no** |
| `ml_link__unconditional` | 0.010642 | 0.034002 | **no** |
| `ols_feedback__unconditional` | 0.008890 | 0.030661 | **no** |
| `week2__unconditional` | 0.022516 | 0.036151 | **no** |

Judged against each engine's OWN within-decade null on the censored construct it actually ships -- the anchors' section 5.3 measurement, not the earlier section 2.8 one that substituted history's null and read 0.010 margins.

### P2_noise_shrink - HOLDS

**Obligation.** hold the loadings and scale the residual innovation down until the share exceeds the band's upper edge; the judge must return FAIL, and it must fail on the UPPER side. This is the specific gaming route a one-sided share bar would leave open and the design document requires it demonstrated closed.

**Requirement.** pass rate 0.0 at the smallest residual, and every failure there is from ABOVE.

| residual sd (pp) | pass rate | mean economic share | fails from above |
|---|---|---|---|
| 0.747993 | **1.00** | 0.5403 | 0.00 |
| 0.6 | **0.88** | 0.6493 | 0.12 |
| 0.5 | **0.00** | 0.7227 | 1.00 |
| 0.35 | **0.00** | 0.8321 | 1.00 |
| 0.2 | **0.00** | 0.9164 | 1.00 |
| 0.1 | **0.00** | 0.9579 | 1.00 |

An engine that removes the surprise the product needs scores a HIGHER economic share, which is why the bar is two-sided and why this control, not the loading sweep, is the one that proves the upper edge is load-bearing.

### P2_retro - HOLDS

**Obligation.** week 2 (0.0%) and week 3 (2.2%) must both be judged and both must fail BELOW the band. If either passes, the bar is not measuring what the finding found.

**Requirement.** no recorded engine passes, and every failure is from below.

| engine / arm | share through the sealed judge | passes? | side |
|---|---|---|---|
| `feedback__premise_accepted` | 0.016064 | **no** | below |
| `feedback__unconditional` | 0.022473 | **no** | below |
| `week2__premise_accepted` | 0.000000 | **no** | below |
| `week2__unconditional` | 0.000000 | **no** | below |

Each engine's share is recomputed by the sealed judge from its committed component standard deviations and must reproduce the share the anchors recorded for it -- which is what makes 'one decomposition function, called on both sides' a check rather than a claim.

## Not swept

The ten carried v2 bars are byte-frozen and are deliberately NOT re-swept: changing them is the thing a carried bar exists to prevent, and each was anti-tested before the v2 seal.

