# WP2.9 monthly-tier neighborhood check (validation folds, hier-flow-v1)

EVIDENCE, NOT A SEALED GATE. Local numpy statistics of generated blocks
(n=1680, 16 per conditioning vector, solver euler, NFE 4) vs the actual validation blocks (n=105).

| factor | skew gen/real | exkurt gen/real | acf1 gen/real | acf2 gen/real |
|---|---|---|---|---|
| cpi | +0.390 / +0.453 | +0.682 / +0.962 | +0.734 / +0.890 | +0.680 / +0.679 |
| equity_mkt | -0.452 / -0.349 | -0.113 / +1.378 | +0.053 / -0.091 | +0.034 / -0.124 |
| equity_vol | +1.067 / +2.344 | +1.881 / +6.931 | +0.533 / +0.700 | +0.492 / +0.467 |
| funding_spread | +1.744 / +1.771 | +7.696 / +4.895 | +0.547 / +0.683 | +0.485 / +0.326 |
| hml | -0.051 / -0.586 | +0.730 / +5.290 | +0.180 / +0.136 | +0.131 / +0.202 |
| hqm_curve | +0.147 / -0.469 | +0.099 / +0.419 | +0.770 / +0.964 | +0.741 / +0.907 |
| ig_spread | +0.751 / +0.644 | +1.562 / -0.278 | +0.714 / +0.907 | +0.656 / +0.742 |
| mom | -0.311 / -0.035 | +0.667 / +0.811 | +0.032 / -0.141 | +0.018 / +0.040 |
| policy_rate | +0.488 / +1.130 | +0.029 / -0.326 | +0.886 / +0.987 | +0.876 / +0.963 |
| smb | -0.062 / +0.104 | -0.100 / -0.322 | -0.007 / -0.134 | -0.013 / +0.050 |
| ust_10y | +0.001 / -0.460 | -0.188 / +0.353 | +0.820 / +0.955 | +0.790 / +0.885 |
| ust_2y | +0.537 / +1.024 | +0.212 / -0.262 | +0.887 / +0.987 | +0.873 / +0.965 |

cross-factor corr gap (pooled cells): mean abs 0.1853, max abs 0.7649
