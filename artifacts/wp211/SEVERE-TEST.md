# WP2.11 severe test (part 1) -- the 1970s-excluded refit

- protocol: `severe_test_protocol (pre-registration.yaml)`
- fitting-sample exclusion: **1970-01-01..1979-12-31**
- regeneration start state: **1965-01-01**
- compared window: **1966-01-01..1984-12-01** (deliberately CONTAINS the exclusion)
- arms: primary, severe; seed indices: [0, 1, 2]

## What "the horizon tier" was taken to mean

`ah.eval.battery.TIERS` has no tier named `horizon`. Two readings are available and THEY DIFFER; both are reported, and every row below carries its suite and its tier so either can be applied.

- reading A (by suite): `suite == "horizon"`
- reading B (by tier): `tier in ("1_5yr", "10yr")`

Reading A selects 110 metrics; reading B selects 113.
In B but not A (3): `interval_coverage_50_5y`, `interval_coverage_90_5y`, `pit_ks_stat_5y`.

## Sealed `structurally_unavailable` names in this set

Named, not silently absent. These carry no computable value by construction; they are excluded from every comparison below and no threshold may gate on them.

- `commodities.ergodicity_gap`
- `cpi.ergodicity_gap`
- `equity_mkt.ergodicity_gap`
- `equity_vol.ergodicity_gap`
- `funding_spread.ergodicity_gap`
- `hml.ergodicity_gap`
- `hqm_curve.ergodicity_gap`
- `hy_spread.ergodicity_gap`
- `ig_spread.ergodicity_gap`
- `mom.ergodicity_gap`
- `policy_rate.ergodicity_gap`
- `regime_duration_mean`
- `regime_duration_p50`
- `regime_duration_p90`
- `smb.ergodicity_gap`
- `ten_year_return_vs_valuation_r2`
- `ten_year_return_vs_valuation_slope`
- `ust_10y.ergodicity_gap`
- `ust_2y.ergodicity_gap`

## ASSESSMENT

- horizon metrics valued in BOTH arms: **80**; of those, a 1966-1984 historical value exists for **35** (the rest are bounded by the window, not by the arms -- see the undefined-reason counts below).
- **Direction vs the excluded era is MIXED and near-identical between arms.** Severe understates 22 / overstates 13; primary understates 21 / overstates 14. Neither arm is systematically shy of the era, and neither is systematically hot.
- **The exclusion produces no systematic degradation.** The severe arm is CLOSER to 1966-1984 history than the primary on **18 of 35** metrics and further on 17 -- a coin flip.
- **The exclusion's effect is an order of magnitude smaller than the pre-existing gap.** Median |severe - primary| / |primary - history| = **0.064**: removing the 1970s moves a typical horizon metric by ~6% of the distance the full-sample system was ALREADY away from the era.
- 14 of 80 metrics move by more than 3x the primary arm's cross-seed sd, so the exclusion IS detectable; it is simply small against the common shortfall.

## THE TWO STATISTICS THE 1970s ACTUALLY TEST

The rest of the horizon tier is reported in full below, but these are the families the excluded decade genuinely bears on, so the reading of the test rests here. `d` is severe minus primary in units of the cross-seed sd of the PRIMARY arm (`-` when only one seed, or when the primary sd is zero); `vs hist` is severe minus history's own 1966-84 value.

### Inflation persistence

| metric | severe | primary | d (primary sd) | hist 66-84 | vs hist |
|---|---|---|---|---|---|
| `cpi.long_inflation_era_frequency` | 0.4414 | 0.4238 | +3.18 | 1.0000 | -0.5586 |
| `cpi.mean_reversion_halflife` | 29.9610 | 29.7333 | +0.78 | 61.1849 | -31.2239 |
| `cpi.variance_ratio_120m` | 64.1710 | 64.5030 | -3.10 | - | - |
| `cpi.variance_ratio_12m` | 11.9232 | 11.9243 | -8.21 | 12.5691 | -0.6459 |
| `cpi.variance_ratio_36m` | 23.9381 | 24.1017 | -10.93 | - | - |
| `cpi.variance_ratio_60m` | 51.6233 | 51.7412 | -10.32 | - | - |
| `commodities.mean_reversion_halflife` | - | - | - | - | - |
| `commodities.variance_ratio_120m` | - | - | - | - | - |
| `commodities.variance_ratio_12m` | - | - | - | - | - |
| `commodities.variance_ratio_36m` | - | - | - | - | - |
| `commodities.variance_ratio_60m` | - | - | - | - | - |
| `equity_mkt.mean_reversion_halflife` | 0.3003 | 0.2982 | +0.23 | 0.2364 | +0.0639 |
| `equity_mkt.variance_ratio_120m` | 3.5119 | 2.7163 | +4.91 | - | - |
| `equity_mkt.variance_ratio_12m` | 1.1717 | 1.0215 | +2.44 | 1.2251 | -0.0534 |
| `equity_mkt.variance_ratio_36m` | 2.0938 | 1.7612 | +3.15 | - | - |
| `equity_mkt.variance_ratio_60m` | 2.7561 | 2.2568 | +3.68 | - | - |
| `equity_vol.mean_reversion_halflife` | 1.5907 | 1.6651 | -0.51 | - | - |
| `equity_vol.variance_ratio_120m` | 44.6257 | 44.6767 | -0.01 | - | - |
| `equity_vol.variance_ratio_12m` | 8.6382 | 8.6387 | -0.00 | - | - |
| `equity_vol.variance_ratio_36m` | 20.2832 | 20.4317 | -0.10 | - | - |
| `equity_vol.variance_ratio_60m` | 29.6969 | 29.3981 | +0.11 | - | - |
| `funding_spread.mean_reversion_halflife` | 1.6535 | 1.7545 | -0.36 | - | - |
| `funding_spread.variance_ratio_120m` | 34.3348 | 36.3089 | -0.51 | - | - |
| `funding_spread.variance_ratio_12m` | 7.7222 | 7.9028 | -0.40 | - | - |
| `funding_spread.variance_ratio_36m` | 16.5409 | 17.3478 | -0.62 | - | - |
| `funding_spread.variance_ratio_60m` | 23.5594 | 24.4386 | -0.38 | - | - |
| `hml.mean_reversion_halflife` | 0.5425 | 0.5528 | -0.27 | 0.3930 | +0.1495 |
| `hml.variance_ratio_120m` | 15.8938 | 17.8615 | -0.85 | - | - |
| `hml.variance_ratio_12m` | 4.2923 | 4.5042 | -0.88 | 1.6501 | +2.6422 |
| `hml.variance_ratio_36m` | 8.6343 | 9.2044 | -0.92 | - | - |
| `hml.variance_ratio_60m` | 11.5805 | 12.5916 | -0.95 | - | - |
| `hqm_curve.mean_reversion_halflife` | 5.2995 | 5.4315 | -0.30 | 1.2295 | +4.0700 |
| `hqm_curve.variance_ratio_120m` | 81.5118 | 82.4658 | -0.45 | - | - |
| `hqm_curve.variance_ratio_12m` | 10.9461 | 10.9641 | -0.36 | - | - |
| `hqm_curve.variance_ratio_36m` | 29.5189 | 29.6548 | -0.52 | - | - |
| `hqm_curve.variance_ratio_60m` | 46.5098 | 46.8010 | -0.47 | - | - |
| `hy_spread.mean_reversion_halflife` | - | - | - | - | - |
| `hy_spread.variance_ratio_120m` | - | - | - | - | - |
| `hy_spread.variance_ratio_12m` | - | - | - | - | - |
| `hy_spread.variance_ratio_36m` | - | - | - | - | - |
| `hy_spread.variance_ratio_60m` | - | - | - | - | - |
| `ig_spread.mean_reversion_halflife` | 2.6088 | 2.5502 | +0.61 | 14.9418 | -12.3330 |
| `ig_spread.variance_ratio_120m` | 42.5478 | 43.3880 | -0.32 | - | - |
| `ig_spread.variance_ratio_12m` | 8.9377 | 8.7146 | +1.71 | 10.6060 | -1.6683 |
| `ig_spread.variance_ratio_36m` | 18.8936 | 19.2039 | -0.50 | - | - |
| `ig_spread.variance_ratio_60m` | 27.6852 | 27.4650 | +0.17 | - | - |
| `mom.mean_reversion_halflife` | 0.4476 | 0.4898 | -1.19 | 0.1890 | +0.2586 |
| `mom.variance_ratio_120m` | 16.6277 | 20.6417 | -0.60 | - | - |
| `mom.variance_ratio_12m` | 3.8555 | 4.3490 | -0.75 | 1.1157 | +2.7398 |
| `mom.variance_ratio_36m` | 7.8359 | 9.2002 | -0.64 | - | - |
| `mom.variance_ratio_60m` | 11.3124 | 13.4683 | -0.56 | - | - |
| `policy_rate.mean_reversion_halflife` | 18.9766 | 18.7463 | +0.24 | 22.0937 | -3.1171 |
| `policy_rate.variance_ratio_120m` | 72.8758 | 72.5687 | +2.44 | - | - |
| `policy_rate.variance_ratio_12m` | 11.6189 | 11.6127 | +0.29 | 10.8265 | +0.7924 |
| `policy_rate.variance_ratio_36m` | 28.8199 | 28.7915 | +0.53 | - | - |
| `policy_rate.variance_ratio_60m` | 46.3983 | 46.2596 | +1.67 | - | - |
| `smb.mean_reversion_halflife` | 0.3698 | 0.4069 | -4.00 | 0.3977 | -0.0279 |
| `smb.variance_ratio_120m` | 7.5078 | 14.9860 | -2.18 | - | - |
| `smb.variance_ratio_12m` | 2.7370 | 3.6088 | -3.35 | 1.8746 | +0.8624 |
| `smb.variance_ratio_36m` | 4.6671 | 7.3063 | -2.63 | - | - |
| `smb.variance_ratio_60m` | 5.9087 | 10.1580 | -2.30 | - | - |
| `ust_10y.mean_reversion_halflife` | 6.0655 | 6.2198 | -0.43 | 42.9306 | -36.8651 |
| `ust_10y.variance_ratio_120m` | 89.7699 | 91.0800 | -4.25 | - | - |
| `ust_10y.variance_ratio_12m` | 11.2826 | 11.3155 | -1.25 | 12.0481 | -0.7655 |
| `ust_10y.variance_ratio_36m` | 31.1030 | 31.3204 | -5.80 | - | - |
| `ust_10y.variance_ratio_60m` | 49.8865 | 50.2393 | -3.36 | - | - |
| `ust_2y.mean_reversion_halflife` | 6.8406 | 6.6102 | +0.27 | 15.5876 | -8.7470 |
| `ust_2y.variance_ratio_120m` | 80.6944 | 80.5897 | +0.04 | - | - |
| `ust_2y.variance_ratio_12m` | 11.0464 | 10.9927 | +0.26 | - | - |
| `ust_2y.variance_ratio_36m` | 29.3762 | 29.2848 | +0.12 | - | - |
| `ust_2y.variance_ratio_60m` | 46.6464 | 46.3479 | +0.25 | - | - |

### The drawdown / duration joint

| metric | severe | primary | d (primary sd) | hist 66-84 | vs hist |
|---|---|---|---|---|---|
| `commodities.drawdown_depth_duration_rank_corr` | - | - | - | - | - |
| `commodities.drawdown_median_depth` | - | - | - | - | - |
| `commodities.drawdown_median_duration` | - | - | - | - | - |
| `commodities.lost_decade_frequency` | - | - | - | - | - |
| `equity_mkt.drawdown_depth_duration_rank_corr` | 0.8685 | 0.8723 | -1.10 | 0.9479 | -0.0794 |
| `equity_mkt.drawdown_median_depth` | 0.0335 | 0.0343 | -0.39 | 0.0686 | -0.0350 |
| `equity_mkt.drawdown_median_duration` | 3.0000 | 3.0000 | +0.0000 (abs) | 2.0000 | +1.0000 |
| `equity_mkt.lost_decade_frequency` | 0.2923 | 0.2428 | +107.48 | 0.0000 | +0.2923 |
| `hml.drawdown_depth_duration_rank_corr` | 0.8812 | 0.8987 | -0.96 | 0.9193 | -0.0381 |
| `hml.drawdown_median_depth` | 0.0174 | 0.0198 | -0.97 | 0.0404 | -0.0230 |
| `hml.drawdown_median_duration` | 2.6667 | 3.0000 | -0.41 | 4.0000 | -1.3333 |
| `hml.lost_decade_frequency` | 0.7454 | 0.7826 | -0.81 | 0.0000 | +0.7454 |
| `mom.drawdown_depth_duration_rank_corr` | 0.8078 | 0.8187 | -0.76 | 0.9118 | -0.1040 |
| `mom.drawdown_median_depth` | 0.0187 | 0.0185 | +0.06 | 0.0600 | -0.0413 |
| `mom.drawdown_median_duration` | 2.0000 | 2.0000 | +0.0000 (abs) | 4.0000 | -2.0000 |
| `mom.lost_decade_frequency` | 0.3079 | 0.3564 | -0.51 | 0.0000 | +0.3079 |
| `smb.drawdown_depth_duration_rank_corr` | 0.8688 | 0.8850 | -1.55 | 0.8944 | -0.0256 |
| `smb.drawdown_median_depth` | 0.0190 | 0.0187 | +0.34 | 0.0618 | -0.0428 |
| `smb.drawdown_median_duration` | 2.0000 | 2.3333 | -0.71 | 5.0000 | -3.0000 |
| `smb.lost_decade_frequency` | 0.4502 | 0.5947 | -2.06 | 0.0459 | +0.4043 |

## Horizon-tier comparison: severe vs primary vs 1966-1984 history

`severe` and `primary` are cross-seed means of the metric on 1024x120 ensembles launched from the 1965 climate state; `hist 66-84` is history's own value of the same statistic on the compared window (a DIAGNOSTIC, not a sealed band); `band` is the sealed reference band where one is usable.

| metric | suite | tier | severe | primary | severe-primary | hist 66-84 | band |
|---|---|---|---|---|---|---|---|
| `commodities.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.drawdown_median_depth` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.drawdown_median_duration` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.lost_decade_frequency` | horizon | 10yr | - | - | - | - | - |
| `commodities.mean_reversion_halflife` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.variance_ratio_120m` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.variance_ratio_12m` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.variance_ratio_36m` | horizon | 1_5yr | - | - | - | - | - |
| `commodities.variance_ratio_60m` | horizon | 1_5yr | - | - | - | - | - |
| `cpi.long_inflation_era_frequency` | horizon | 10yr | 0.4414 | 0.4238 | 0.0176 | 1.0000 | [0.2260, 0.6688] |
| `cpi.mean_reversion_halflife` | horizon | 1_5yr | 29.9610 | 29.7333 | 0.2278 | 61.1849 | [13.3564, 47.1680] |
| `cpi.variance_ratio_120m` | horizon | 1_5yr | 64.1710 | 64.5030 | -0.3320 | - | [nan, nan] |
| `cpi.variance_ratio_12m` | horizon | 1_5yr | 11.9232 | 11.9243 | -0.0011 | 12.5691 | [11.3485, 13.0992] |
| `cpi.variance_ratio_36m` | horizon | 1_5yr | 23.9381 | 24.1017 | -0.1636 | - | [nan, nan] |
| `cpi.variance_ratio_60m` | horizon | 1_5yr | 51.6233 | 51.7412 | -0.1178 | - | [nan, nan] |
| `equity_mkt.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8685 | 0.8723 | -0.0038 | 0.9479 | [nan, nan] |
| `equity_mkt.drawdown_median_depth` | horizon | 1_5yr | 0.0335 | 0.0343 | -0.0008 | 0.0686 | [nan, nan] |
| `equity_mkt.drawdown_median_duration` | horizon | 1_5yr | 3.0000 | 3.0000 | 0.0000 | 2.0000 | [nan, nan] |
| `equity_mkt.lost_decade_frequency` | horizon | 10yr | 0.2923 | 0.2428 | 0.0495 | 0.0000 | [0.0000, 0.1320] |
| `equity_mkt.mean_reversion_halflife` | horizon | 1_5yr | 0.3003 | 0.2982 | 0.0021 | 0.2364 | [0.1589, 0.4222] |
| `equity_mkt.variance_ratio_120m` | horizon | 1_5yr | 3.5119 | 2.7163 | 0.7956 | - | [nan, nan] |
| `equity_mkt.variance_ratio_12m` | horizon | 1_5yr | 1.1717 | 1.0215 | 0.1502 | 1.2251 | [0.3983, 2.0883] |
| `equity_mkt.variance_ratio_36m` | horizon | 1_5yr | 2.0938 | 1.7612 | 0.3326 | - | [nan, nan] |
| `equity_mkt.variance_ratio_60m` | horizon | 1_5yr | 2.7561 | 2.2568 | 0.4993 | - | [nan, nan] |
| `equity_vol.mean_reversion_halflife` | horizon | 1_5yr | 1.5907 | 1.6651 | -0.0744 | - | [1.9936, 5.2685] |
| `equity_vol.variance_ratio_120m` | horizon | 1_5yr | 44.6257 | 44.6767 | -0.0510 | - | [nan, nan] |
| `equity_vol.variance_ratio_12m` | horizon | 1_5yr | 8.6382 | 8.6387 | -0.0005 | - | [6.2371, 9.4084] |
| `equity_vol.variance_ratio_36m` | horizon | 1_5yr | 20.2832 | 20.4317 | -0.1485 | - | [nan, nan] |
| `equity_vol.variance_ratio_60m` | horizon | 1_5yr | 29.6969 | 29.3981 | 0.2987 | - | [nan, nan] |
| `funding_spread.mean_reversion_halflife` | horizon | 1_5yr | 1.6535 | 1.7545 | -0.1011 | - | [2.5453, 6.9164] |
| `funding_spread.variance_ratio_120m` | horizon | 1_5yr | 34.3348 | 36.3089 | -1.9741 | - | [nan, nan] |
| `funding_spread.variance_ratio_12m` | horizon | 1_5yr | 7.7222 | 7.9028 | -0.1806 | - | [5.2105, 10.6764] |
| `funding_spread.variance_ratio_36m` | horizon | 1_5yr | 16.5409 | 17.3478 | -0.8070 | - | [nan, nan] |
| `funding_spread.variance_ratio_60m` | horizon | 1_5yr | 23.5594 | 24.4386 | -0.8792 | - | [nan, nan] |
| `hml.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8812 | 0.8987 | -0.0175 | 0.9193 | [nan, nan] |
| `hml.drawdown_median_depth` | horizon | 1_5yr | 0.0174 | 0.0198 | -0.0024 | 0.0404 | [nan, nan] |
| `hml.drawdown_median_duration` | horizon | 1_5yr | 2.6667 | 3.0000 | -0.3333 | 4.0000 | [nan, nan] |
| `hml.lost_decade_frequency` | horizon | 10yr | 0.7454 | 0.7826 | -0.0371 | 0.0000 | [0.0030, 0.2512] |
| `hml.mean_reversion_halflife` | horizon | 1_5yr | 0.5425 | 0.5528 | -0.0102 | 0.3930 | [0.1849, 0.5567] |
| `hml.variance_ratio_120m` | horizon | 1_5yr | 15.8938 | 17.8615 | -1.9677 | - | [nan, nan] |
| `hml.variance_ratio_12m` | horizon | 1_5yr | 4.2923 | 4.5042 | -0.2119 | 1.6501 | [0.6915, 2.3081] |
| `hml.variance_ratio_36m` | horizon | 1_5yr | 8.6343 | 9.2044 | -0.5701 | - | [nan, nan] |
| `hml.variance_ratio_60m` | horizon | 1_5yr | 11.5805 | 12.5916 | -1.0111 | - | [nan, nan] |
| `hqm_curve.mean_reversion_halflife` | horizon | 1_5yr | 5.2995 | 5.4315 | -0.1320 | 1.2295 | [8.2312, 27.4521] |
| `hqm_curve.variance_ratio_120m` | horizon | 1_5yr | 81.5118 | 82.4658 | -0.9540 | - | [nan, nan] |
| `hqm_curve.variance_ratio_12m` | horizon | 1_5yr | 10.9461 | 10.9641 | -0.0180 | - | [8.9064, 12.2628] |
| `hqm_curve.variance_ratio_36m` | horizon | 1_5yr | 29.5189 | 29.6548 | -0.1359 | - | [nan, nan] |
| `hqm_curve.variance_ratio_60m` | horizon | 1_5yr | 46.5098 | 46.8010 | -0.2913 | - | [nan, nan] |
| `hy_spread.mean_reversion_halflife` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_120m` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_12m` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_36m` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_60m` | horizon | 1_5yr | - | - | - | - | - |
| `ig_spread.mean_reversion_halflife` | horizon | 1_5yr | 2.6088 | 2.5502 | 0.0586 | 14.9418 | [6.0799, 27.7542] |
| `ig_spread.variance_ratio_120m` | horizon | 1_5yr | 42.5478 | 43.3880 | -0.8402 | - | [nan, nan] |
| `ig_spread.variance_ratio_12m` | horizon | 1_5yr | 8.9377 | 8.7146 | 0.2231 | 10.6060 | [7.8017, 12.5491] |
| `ig_spread.variance_ratio_36m` | horizon | 1_5yr | 18.8936 | 19.2039 | -0.3103 | - | [nan, nan] |
| `ig_spread.variance_ratio_60m` | horizon | 1_5yr | 27.6852 | 27.4650 | 0.2202 | - | [nan, nan] |
| `interval_coverage_50_5y` | calibration | 1_5yr | 0.4799 | 0.4724 | 0.0075 | - | - |
| `interval_coverage_90_5y` | calibration | 1_5yr | 0.8253 | 0.8134 | 0.0119 | - | - |
| `mom.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8078 | 0.8187 | -0.0109 | 0.9118 | [nan, nan] |
| `mom.drawdown_median_depth` | horizon | 1_5yr | 0.0187 | 0.0185 | 0.0002 | 0.0600 | [nan, nan] |
| `mom.drawdown_median_duration` | horizon | 1_5yr | 2.0000 | 2.0000 | 0.0000 | 4.0000 | [nan, nan] |
| `mom.lost_decade_frequency` | horizon | 10yr | 0.3079 | 0.3564 | -0.0485 | 0.0000 | [0.0000, 0.3499] |
| `mom.mean_reversion_halflife` | horizon | 1_5yr | 0.4476 | 0.4898 | -0.0422 | 0.1890 | [0.1706, 0.5252] |
| `mom.variance_ratio_120m` | horizon | 1_5yr | 16.6277 | 20.6417 | -4.0140 | - | [nan, nan] |
| `mom.variance_ratio_12m` | horizon | 1_5yr | 3.8555 | 4.3490 | -0.4935 | 1.1157 | [0.2687, 1.9267] |
| `mom.variance_ratio_36m` | horizon | 1_5yr | 7.8359 | 9.2002 | -1.3643 | - | [nan, nan] |
| `mom.variance_ratio_60m` | horizon | 1_5yr | 11.3124 | 13.4683 | -2.1559 | - | [nan, nan] |
| `pit_ks_stat_5y` | calibration | 1_5yr | 0.2388 | 0.3108 | -0.0720 | - | - |
| `policy_rate.mean_reversion_halflife` | horizon | 1_5yr | 18.9766 | 18.7463 | 0.2303 | 22.0937 | [8.1933, 90.9740] |
| `policy_rate.variance_ratio_120m` | horizon | 1_5yr | 72.8758 | 72.5687 | 0.3070 | - | [nan, nan] |
| `policy_rate.variance_ratio_12m` | horizon | 1_5yr | 11.6189 | 11.6127 | 0.0062 | 10.8265 | [9.5313, 12.6171] |
| `policy_rate.variance_ratio_36m` | horizon | 1_5yr | 28.8199 | 28.7915 | 0.0285 | - | [nan, nan] |
| `policy_rate.variance_ratio_60m` | horizon | 1_5yr | 46.3983 | 46.2596 | 0.1387 | - | [nan, nan] |
| `smb.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8688 | 0.8850 | -0.0162 | 0.8944 | [nan, nan] |
| `smb.drawdown_median_depth` | horizon | 1_5yr | 0.0190 | 0.0187 | 0.0003 | 0.0618 | [nan, nan] |
| `smb.drawdown_median_duration` | horizon | 1_5yr | 2.0000 | 2.3333 | -0.3333 | 5.0000 | [nan, nan] |
| `smb.lost_decade_frequency` | horizon | 10yr | 0.4502 | 0.5947 | -0.1445 | 0.0459 | [0.1182, 0.5439] |
| `smb.mean_reversion_halflife` | horizon | 1_5yr | 0.3698 | 0.4069 | -0.0371 | 0.3977 | [0.1635, 0.5082] |
| `smb.variance_ratio_120m` | horizon | 1_5yr | 7.5078 | 14.9860 | -7.4782 | - | [nan, nan] |
| `smb.variance_ratio_12m` | horizon | 1_5yr | 2.7370 | 3.6088 | -0.8718 | 1.8746 | [0.3997, 2.3984] |
| `smb.variance_ratio_36m` | horizon | 1_5yr | 4.6671 | 7.3063 | -2.6392 | - | [nan, nan] |
| `smb.variance_ratio_60m` | horizon | 1_5yr | 5.9087 | 10.1580 | -4.2493 | - | [nan, nan] |
| `ust_10y.mean_reversion_halflife` | horizon | 1_5yr | 6.0655 | 6.2198 | -0.1543 | 42.9306 | [8.4362, 27.7645] |
| `ust_10y.variance_ratio_120m` | horizon | 1_5yr | 89.7699 | 91.0800 | -1.3100 | - | [nan, nan] |
| `ust_10y.variance_ratio_12m` | horizon | 1_5yr | 11.2826 | 11.3155 | -0.0329 | 12.0481 | [9.4122, 12.3796] |
| `ust_10y.variance_ratio_36m` | horizon | 1_5yr | 31.1030 | 31.3204 | -0.2174 | - | [nan, nan] |
| `ust_10y.variance_ratio_60m` | horizon | 1_5yr | 49.8865 | 50.2393 | -0.3528 | - | [nan, nan] |
| `ust_2y.mean_reversion_halflife` | horizon | 1_5yr | 6.8406 | 6.6102 | 0.2305 | 15.5876 | [10.4115, 58.5356] |
| `ust_2y.variance_ratio_120m` | horizon | 1_5yr | 80.6944 | 80.5897 | 0.1046 | - | [nan, nan] |
| `ust_2y.variance_ratio_12m` | horizon | 1_5yr | 11.0464 | 10.9927 | 0.0537 | - | [9.9799, 12.6519] |
| `ust_2y.variance_ratio_36m` | horizon | 1_5yr | 29.3762 | 29.2848 | 0.0914 | - | [nan, nan] |
| `ust_2y.variance_ratio_60m` | horizon | 1_5yr | 46.6464 | 46.3479 | 0.2985 | - | [nan, nan] |

## Support diagnostic (1965-launched decades)

| cell | extrapolation share (mean) | (max) | flagged off-support | regime TV (mean) |
|---|---|---|---|---|
| primary:s0 | 0.8632 | 1.0000 | 1002 | 0.3267 |
| primary:s1 | 0.8683 | 1.0000 | 1005 | 0.3266 |
| primary:s2 | 0.8650 | 1.0000 | 1003 | 0.3265 |
| severe:s0 | 0.8640 | 1.0000 | 1009 | 0.3407 |
| severe:s1 | 0.8648 | 1.0000 | 1010 | 0.3405 |
| severe:s2 | 0.8670 | 1.0000 | 1009 | 0.3401 |

## Cells

| cell | criterion bearing | prereg verified | enforce pass | checkpoint |
|---|---|---|---|---|
| primary:s0 | True | True | True | `b1fe26e100678a26...` |
| primary:s1 | True | True | True | `5b359c8cf29d0de0...` |
| primary:s2 | True | True | True | `b661abc1cc4dffde...` |
| severe:s0 | True | True | True | `668784c2d953808e...` |
| severe:s1 | True | True | True | `b21d202cfde7cee9...` |
| severe:s2 | True | True | True | `1276baad677c93e3...` |

### 1966-1984 historical coverage (which factors history can even answer for)

| factor | n obs | span |
|---|---|---|
| cpi | 228 | 1966-01-01 .. 1984-12-01 |
| equity_mkt | 228 | 1966-01-01 .. 1984-12-01 |
| equity_vol | 0 | None .. None |
| funding_spread | 0 | None .. None |
| hml | 228 | 1966-01-01 .. 1984-12-01 |
| hqm_curve | 12 | 1984-01-01 .. 1984-12-01 |
| ig_spread | 228 | 1966-01-01 .. 1984-12-01 |
| mom | 228 | 1966-01-01 .. 1984-12-01 |
| policy_rate | 228 | 1966-01-01 .. 1984-12-01 |
| smb | 228 | 1966-01-01 .. 1984-12-01 |
| ust_10y | 228 | 1966-01-01 .. 1984-12-01 |
| ust_2y | 103 | 1976-06-01 .. 1984-12-01 |
