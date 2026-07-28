# WP2.9 sampler bake-off (hier-diffusion-v1 vs hier-flow-v1)

> The two `gen` columns are NOT on one scale and must not be ranked against each other: 3a's is a sigma-weighted denoising MSE on a fixed sigma grid, 3b's is an unweighted velocity MSE on a fixed time grid. The sealed tuning_protocol records exactly this and requires both terms of S to be reported separately, per sampler, with their scales -- so `S` is shown per arm as the quantity each arm was SELECTED by, never as a cross-arm ranking. Directly comparable: the `aux` column (the same D4 elicitability estimator, same folds, same noise seeds), sampling cost, conditioning response, and battery outcomes.

| arm | generative objective | gen (own scale) | aux (D4 FZ, shared) | S = gen + 1.0*aux | guidance | NFE/block | blocks/s | s/decade | s/10k decades |
|---|---|---|---|---|---|---|---|---|---|
| hier-diffusion-v1 | fixed-sigma-grid EDM denoising objective | 0.937858 | -3.264191 | -2.326333 | 1 | 31 | 537.7 | 0.0744 | 744 |
| hier-flow-v1 | fixed-time-grid rectified-flow velocity objective | 1.644183 | -3.409308 | -1.765125 | 1 | 4 | 4346.2 | 0.0092 | 92 |
| hier-flow-v1 (ablation: guidance 1.5) | fixed-time-grid rectified-flow velocity objective | 1.644183 | -3.301597 | -1.657414 | 1.5 | 8 | 2038.3 | 0.0196 | 196 |
| hier-flow-v1 (ablation: guidance 2.5) | fixed-time-grid rectified-flow velocity objective | 1.644183 | -3.117773 | -1.473590 | 2.5 | 8 | 1381.6 | 0.0290 | 290 |

Cost measured at block width hier-diffusion-v1=128@cuda, hier-flow-v1=128@cuda, hier-flow-v1 (ablation: guidance 1.5)=128@cuda, hier-flow-v1 (ablation: guidance 2.5)=128@cuda; a decade is 40 blocks at stride 3.

## Conditioning response (finite difference vs historical OLS)

| channel | historical | hier-diffusion-v1 model / ratio | hier-flow-v1 model / ratio | hier-flow-v1 (ablation: guidance 1.5) model / ratio | hier-flow-v1 (ablation: guidance 2.5) model / ratio |
|---|---|---|---|---|---|
| dw_equity_cum_log | +1.0086 | +0.7893 / 78% | +0.6970 / 69% | +0.9683 / 96% | +1.4567 / 144% |
| state_pi_star | +1.0622 | +0.4881 / 46% | +0.3196 / 30% | +0.3394 / 32% | +0.3708 / 35% |
| dw_log_cpi | +0.8035 | +0.3099 / 39% | +0.2284 / 28% | +0.2898 / 36% | +0.4055 / 50% |
| h_spread_level_pct | +0.7632 | +0.1419 / 19% | +0.1167 / 15% | +0.1564 / 20% | +0.2270 / 30% |
| dw_spread_center_pct | +0.8500 | +0.1158 / 14% | +0.1646 / 19% | +0.2108 / 25% | +0.2723 / 32% |
| dw_policy_rate_pct | -0.4361 | +0.1513 / -35% | +0.1127 / -26% | +0.1187 / -27% | +0.0963 / -22% |
| regime_onehot | +1.2074 | +0.0228 / 2% | +0.0401 / 3% | +0.0580 / 5% | +0.0913 / 8% |

## Notes

- **hier-diffusion-v1**: selected under its own sealed 40-trial budget; generative objective = fixed-sigma-grid EDM denoising objective
- **hier-flow-v1**: selected under its own sealed 40-trial budget; generative objective = fixed-time-grid rectified-flow velocity objective
- **hier-flow-v1 (ablation: guidance 1.5)**: selected under its own sealed 40-trial budget; generative objective = fixed-time-grid rectified-flow velocity objective
- **hier-flow-v1 (ablation: guidance 1.5)**: ABLATION ARM, not a selected configuration: the SAME checkpoint sampled at guidance 1.5 instead of the sealed selection's 1. Classifier-free guidance is learned aim (it amplifies conditioning the model already reads), not post-hoc repair; it is reported here alongside the unguided row so the effect is visible, and it costs 2x the network evaluations.
- **hier-flow-v1 (ablation: guidance 2.5)**: selected under its own sealed 40-trial budget; generative objective = fixed-time-grid rectified-flow velocity objective
- **hier-flow-v1 (ablation: guidance 2.5)**: ABLATION ARM, not a selected configuration: the SAME checkpoint sampled at guidance 2.5 instead of the sealed selection's 1. Classifier-free guidance is learned aim (it amplifies conditioning the model already reads), not post-hoc repair; it is reported here alongside the unguided row so the effect is visible, and it costs 2x the network evaluations.

## Not yet measured

Battery outcome, reconciliation-adjustment distribution and waypoint-band diagnostics are NOT in this table. They run through the joinery, whose ig_spread waypoint band is being corrected (WP2.7b); measuring the two arms across two different bands would not be a bake-off. Those rows are filled by the end-to-end sealed battery run once the band correction has landed.
