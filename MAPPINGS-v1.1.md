# MAPPINGS-v1.1.md — PM sum-beta re-estimation (AM-2026-08-12-001)

Vintage `2026-08-10.1`; train+validation only; lag rule and BDC anchor
declared in docs/superpowers/specs/2026-08-12-pm-remap-design.md
BEFORE this ran. HF sleeves verbatim from v1.0.

| sleeve | route | n | lags | b_mkt v1.0 | b_mkt v1.1 | per-lag | alpha_q v1.0 | alpha_q v1.1 | sigma_ann |
|---|---|---|---|---|---|---|---|---|---|
| pm_buyout | sum-beta(4) | 125 | 4 | +0.348 | +0.836 | [0.144 0.103 0.089 0.125] | +0.0332 | +0.0194 | 12.3% |
| pm_direct_lending | bdc-anchor*0.5 | 195 | 0 | +0.000 | +0.469 | [] | +0.0157 | +0.0016 | 5.6% |
| pm_distressed | sum-beta(4) | 87 | 4 | +0.383 | +0.483 | [0.    0.034 0.    0.081] | +0.0165 | +0.0143 | 7.3% |
| pm_growth | sum-beta(4) | 94 | 4 | +0.744 | +1.274 | [0.058 0.    0.302 0.139] | +0.0238 | +0.0109 | 17.1% |
| pm_infra | sum-beta(2) | 60 | 2 | +0.249 | +0.334 | [0.03  0.052] | +0.0111 | +0.0089 | 5.7% |
| pm_mezzanine | sum-beta(4) | 102 | 4 | +0.226 | +0.280 | [0.    0.061 0.005 0.   ] | +0.0208 | +0.0193 | 5.7% |
| pm_re_value_add | sum-beta(4) | 85 | 4 | +0.087 | +0.368 | [0.    0.077 0.044 0.146] | +0.0154 | +0.0093 | 12.6% |
| pm_secondaries | sum-beta(4) | 89 | 4 | +0.252 | +0.730 | [0.24  0.069 0.094 0.022] | +0.0297 | +0.0190 | 9.7% |
| pm_vc | sum-beta(4) | 120 | 4 | +0.433 | +1.261 | [0.252 0.154 0.123 0.27 ] | +0.0289 | +0.0057 | 23.6% |
