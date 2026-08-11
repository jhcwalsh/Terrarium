# Regime label sensitivity report (WP2.6: regime_ruleset_v1 vs v1b)

- config_hash: `cfg:1758709d4009c6ff`
- git_sha: `9f1d570`
- span: 1926-07-01 .. 2020-12-01 (1134 months)
- label agreement rate: 0.9083

The plan's honesty note: L2 is fitted on rule-based labels, so the fit
could in principle be an artifact of the ruleset's thresholds. This run
refits under a perturbed ruleset (`regime_ruleset_v1b`, below) and reports
what actually moves. `src/ah/data/regime_thresholds.yaml` is not modified;
the variant is passed through the labeler's `thr` parameter.

## Threshold perturbations (and why they are material)

| threshold | v1 | v1b |
|---|---|---|
| cpi_high | 4.0 | 3.5 |
| growth_weak | 0.0 | 0.25 |
| growth_slow | 1.5 | 1.75 |
| drawdown_crisis | -0.2 | -0.15 |
| hy_crisis | 8.0 | 8.0 |

Each perturbation moves a boundary through a dense part of the feature
distribution (see priors.yaml's sensitivity block for the per-threshold
rationale); hy_crisis is unchanged because the disjunct is dead on
train+validation data (hy_spread's licensed history is all holdout).

## Label composition under both rulesets

| regime | freq v1 | freq v1b | median dur v1 | v1b | p90 dur v1 | v1b | spells v1 | v1b |
|---|---|---|---|---|---|---|---|---|
| EXP | 0.459 | 0.399 | 12.0 | 5.0 | 31.0 | 19.0 | 31 | 41 |
| SLOW | 0.071 | 0.079 | 2.0 | 2.0 | 4.7 | 3.7 | 34 | 44 |
| REC | 0.198 | 0.181 | 4.0 | 4.0 | 18.2 | 15.4 | 29 | 34 |
| CRI | 0.082 | 0.096 | 8.5 | 5.0 | 21.7 | 15.7 | 8 | 12 |
| STAG | 0.030 | 0.041 | 4.0 | 2.0 | 8.0 | 7.2 | 9 | 15 |
| REF | 0.160 | 0.203 | 6.0 | 2.5 | 27.8 | 24.2 | 17 | 30 |

## Empirical transition counts

v1:

| from \ to | EXP | SLOW | REC | CRI | STAG | REF | total |
|---|---|---|---|---|---|---|---|
| EXP | 0 | 13 | 7 | 0 | 0 | 12 | 32 |
| SLOW | 17 | 0 | 10 | 0 | 3 | 4 | 34 |
| REC | 8 | 11 | 0 | 6 | 4 | 0 | 29 |
| CRI | 0 | 0 | 7 | 0 | 1 | 0 | 8 |
| STAG | 0 | 7 | 1 | 0 | 0 | 1 | 9 |
| REF | 6 | 3 | 5 | 2 | 1 | 0 | 17 |

v1b:

| from \ to | EXP | SLOW | REC | CRI | STAG | REF | total |
|---|---|---|---|---|---|---|---|
| EXP | 0 | 15 | 4 | 0 | 0 | 23 | 42 |
| SLOW | 20 | 0 | 13 | 0 | 7 | 4 | 44 |
| REC | 7 | 13 | 0 | 9 | 5 | 0 | 34 |
| CRI | 0 | 0 | 10 | 0 | 2 | 0 | 12 |
| STAG | 0 | 8 | 4 | 0 | 0 | 3 | 15 |
| REF | 14 | 8 | 4 | 3 | 1 | 0 | 30 |

## Fitted hazards under both rulesets

Convergence: v1 max R-hat 1.0008, min ESS 3748, 0 divergences; v1b max R-hat 1.0019, min ESS 3884, 0 divergences.

Posterior E[D] at z = 0 (months):

| regime | v1 mean | v1 5% | v1 95% | v1b mean | v1b 5% | v1b 95% |
|---|---|---|---|---|---|---|
| EXP | 14.7 | 9.7 | 20.9 | 8.7 | 6.1 | 12.1 |
| SLOW | 2.2 | 1.7 | 2.8 | 2.0 | 1.7 | 2.5 |
| REC | 8.5 | 5.6 | 12.7 | 6.2 | 4.2 | 8.6 |
| CRI | 5.5 | 1.7 | 14.1 | 4.1 | 1.5 | 10.0 |
| STAG | 3.4 | 1.7 | 6.6 | 2.1 | 1.4 | 3.1 |
| REF | 8.6 | 5.0 | 13.9 | 6.0 | 3.4 | 10.2 |

Posterior-mean transition probabilities at z = 0, v1 -> v1b (delta):

| from \ to | EXP | SLOW | REC | CRI | STAG | REF |
|---|---|---|---|---|---|---|
| EXP | 0.00 (+0.00) | 0.40 (-0.10) | 0.21 (-0.13) | 0.02 (-0.01) | 0.02 (-0.01) | 0.35 (+0.24) |
| SLOW | 0.47 (-0.04) | 0.00 (+0.00) | 0.34 (-0.01) | 0.02 (-0.01) | 0.08 (+0.07) | 0.10 (-0.02) |
| REC | 0.24 (-0.05) | 0.48 (-0.02) | 0.00 (+0.00) | 0.12 (+0.04) | 0.15 (+0.04) | 0.02 (-0.00) |
| CRI | 0.04 (-0.01) | 0.03 (-0.01) | 0.84 (+0.03) | 0.00 (+0.00) | 0.08 (-0.00) | 0.02 (-0.01) |
| STAG | 0.05 (+0.01) | 0.81 (-0.26) | 0.11 (+0.22) | 0.02 (-0.01) | 0.00 (+0.00) | 0.02 (+0.03) |
| REF | 0.36 (+0.14) | 0.24 (+0.04) | 0.32 (-0.15) | 0.06 (-0.02) | 0.03 (-0.01) | 0.00 (+0.00) |

Sojourn covariate loadings gamma (posterior mean), v1 vs v1b:

| regime | covariate | gamma v1 | gamma v1b |
|---|---|---|---|
| EXP | curve_slope | -0.224 | -0.393 |
| EXP | credit_gap | +0.164 | +0.258 |
| EXP | pi_gap | +0.273 | +0.815 |
| EXP | drawdown_state | -0.049 | +0.264 |
| SLOW | curve_slope | -0.158 | -0.361 |
| SLOW | credit_gap | -0.401 | -0.223 |
| SLOW | pi_gap | -0.417 | -0.270 |
| SLOW | drawdown_state | +0.579 | +0.718 |
| REC | curve_slope | +0.119 | +0.237 |
| REC | credit_gap | +0.239 | +0.492 |
| REC | pi_gap | +0.048 | +0.135 |
| REC | drawdown_state | +0.485 | +0.052 |
| CRI | curve_slope | +0.440 | +0.640 |
| CRI | credit_gap | -0.574 | -0.443 |
| CRI | pi_gap | -0.266 | -0.692 |
| CRI | drawdown_state | -0.445 | -0.372 |
| STAG | curve_slope | -1.074 | -0.647 |
| STAG | credit_gap | -0.052 | +0.147 |
| STAG | pi_gap | -0.123 | -0.643 |
| STAG | drawdown_state | -0.007 | +0.027 |
| REF | curve_slope | -0.502 | -0.529 |
| REF | credit_gap | +0.640 | +0.354 |
| REF | pi_gap | -0.379 | -0.760 |
| REF | drawdown_state | -0.338 | -0.144 |

## Acceptance bands under v1b

This is GENERATOR-SIDE acceptance evidence, not a sealed battery metric:
the battery's `regime_duration_*` statistics are sealed
`structurally_unavailable` and the judged sources are untouched. WP2.11
must cite this table as generator evidence, not as a battery result.

Simulated: 512 decades x 120 months, seed 20260727, L1 starting states spread over 10 historical dates (1926-07-01 .. 2016-07-01, neutral cycle, one-pass).
Durations use complete (interior) spells only, both historically and in
simulation; a 120-month decade right-censors spells longer than the decade,
so long-spell quantiles (EXP especially) are biased short on the simulated
side -- read `p90_dur[EXP]` with that in mind.

| statistic | regime | historical | band 2.5% | band 97.5% | simulated | inside |
|---|---|---|---|---|---|---|
| freq | EXP | 0.399 | 0.281 | 0.512 | 0.337 | YES |
| freq | SLOW | 0.079 | 0.044 | 0.122 | 0.087 | YES |
| freq | REC | 0.181 | 0.109 | 0.257 | 0.240 | YES |
| freq | CRI | 0.096 | 0.040 | 0.165 | 0.066 | YES |
| freq | STAG | 0.041 | 0.008 | 0.086 | 0.056 | YES |
| freq | REF | 0.203 | 0.108 | 0.301 | 0.214 | YES |
| median_dur | EXP | 5.000 | 3.000 | 9.012 | 4.000 | YES |
| median_dur | SLOW | 2.000 | 1.000 | 2.000 | 2.000 | YES |
| median_dur | REC | 4.000 | 1.000 | 6.000 | 3.000 | YES |
| median_dur | CRI | 5.000 | 2.000 | 11.000 | 4.000 | YES |
| median_dur | STAG | 2.000 | 1.000 | 3.500 | 2.000 | YES |
| median_dur | REF | 2.500 | 1.000 | 5.000 | 2.000 | YES |
| p90_dur | EXP | 19.000 | 14.000 | 38.000 | 19.000 | YES |
| p90_dur | SLOW | 3.700 | 3.000 | 5.000 | 4.000 | YES |
| p90_dur | REC | 15.400 | 6.397 | 19.000 | 16.000 | YES |
| p90_dur | CRI | 15.700 | 9.600 | 42.000 | 15.900 | YES |
| p90_dur | STAG | 7.200 | 2.000 | 8.700 | 6.000 | YES |
| p90_dur | REF | 24.200 | 6.498 | 30.000 | 15.000 | YES |

Inside: 18 / 18 judged bands.
