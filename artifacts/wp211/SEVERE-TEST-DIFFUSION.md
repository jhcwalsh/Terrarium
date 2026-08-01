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
- **Direction vs the excluded era is MIXED and near-identical between arms.** Severe understates 19 / overstates 16; primary understates 20 / overstates 15. Neither arm is systematically shy of the era, and neither is systematically hot.
- **The exclusion produces no systematic degradation.** The severe arm is CLOSER to 1966-1984 history than the primary on **17 of 35** metrics and further on 18 -- a coin flip.
- **The exclusion's effect is an order of magnitude smaller than the pre-existing gap.** Median |severe - primary| / |primary - history| = **0.078**: removing the 1970s moves a typical horizon metric by ~8% of the distance the full-sample system was ALREADY away from the era.
- 12 of 80 metrics move by more than 3x the primary arm's cross-seed sd, so the exclusion IS detectable; it is simply small against the common shortfall.

## THE TWO STATISTICS THE 1970s ACTUALLY TEST

The rest of the horizon tier is reported in full below, but these are the families the excluded decade genuinely bears on, so the reading of the test rests here. `d` is severe minus primary in units of the cross-seed sd of the PRIMARY arm (`-` when only one seed, or when the primary sd is zero); `vs hist` is severe minus history's own 1966-84 value.

### Inflation persistence

| metric | severe | primary | d (primary sd) | hist 66-84 | vs hist |
|---|---|---|---|---|---|
| `cpi.long_inflation_era_frequency` | 0.4134 | 0.3802 | +8.81 | 1.0000 | -0.5866 |
| `cpi.mean_reversion_halflife` | 27.7042 | 26.7929 | +1.29 | 61.1849 | -33.4807 |
| `cpi.variance_ratio_120m` | 64.2242 | 64.6133 | -5.21 | - | - |
| `cpi.variance_ratio_12m` | 11.9209 | 11.9207 | +0.20 | 12.5691 | -0.6482 |
| `cpi.variance_ratio_36m` | 23.9447 | 24.1193 | -14.13 | - | - |
| `cpi.variance_ratio_60m` | 51.6250 | 51.7444 | -9.78 | - | - |
| `commodities.mean_reversion_halflife` | - | - | - | - | - |
| `commodities.variance_ratio_120m` | - | - | - | - | - |
| `commodities.variance_ratio_12m` | - | - | - | - | - |
| `commodities.variance_ratio_36m` | - | - | - | - | - |
| `commodities.variance_ratio_60m` | - | - | - | - | - |
| `equity_mkt.mean_reversion_halflife` | 0.2844 | 0.2797 | +28.46 | 0.2364 | +0.0480 |
| `equity_mkt.variance_ratio_120m` | 3.1154 | 2.1721 | +6.74 | - | - |
| `equity_mkt.variance_ratio_12m` | 1.0385 | 0.8161 | +4.25 | 1.2251 | -0.1867 |
| `equity_mkt.variance_ratio_36m` | 1.8577 | 1.4085 | +4.99 | - | - |
| `equity_mkt.variance_ratio_60m` | 2.4449 | 1.8044 | +5.52 | - | - |
| `equity_vol.mean_reversion_halflife` | 1.4809 | 1.6437 | -1.01 | - | - |
| `equity_vol.variance_ratio_120m` | 47.3521 | 47.8851 | -0.08 | - | - |
| `equity_vol.variance_ratio_12m` | 8.6627 | 8.6495 | +0.02 | - | - |
| `equity_vol.variance_ratio_36m` | 20.6879 | 20.7108 | -0.01 | - | - |
| `equity_vol.variance_ratio_60m` | 31.0740 | 30.9679 | +0.03 | - | - |
| `funding_spread.mean_reversion_halflife` | 1.3974 | 1.5737 | -1.17 | - | - |
| `funding_spread.variance_ratio_120m` | 46.6300 | 48.4371 | -0.38 | - | - |
| `funding_spread.variance_ratio_12m` | 8.1487 | 8.6018 | -1.23 | - | - |
| `funding_spread.variance_ratio_36m` | 18.9311 | 19.9802 | -0.90 | - | - |
| `funding_spread.variance_ratio_60m` | 29.4536 | 30.4427 | -0.35 | - | - |
| `hml.mean_reversion_halflife` | 0.5106 | 0.5980 | -1.68 | 0.3930 | +0.1176 |
| `hml.variance_ratio_120m` | 22.1577 | 29.8255 | -0.95 | - | - |
| `hml.variance_ratio_12m` | 4.6448 | 5.6144 | -1.24 | 1.6501 | +2.9948 |
| `hml.variance_ratio_36m` | 10.1492 | 12.9856 | -1.10 | - | - |
| `hml.variance_ratio_60m` | 14.2959 | 18.7171 | -1.07 | - | - |
| `hqm_curve.mean_reversion_halflife` | 4.0800 | 4.3132 | -0.71 | 1.2295 | +2.8505 |
| `hqm_curve.variance_ratio_120m` | 86.3212 | 86.4613 | -0.05 | - | - |
| `hqm_curve.variance_ratio_12m` | 10.9336 | 10.9456 | -0.08 | - | - |
| `hqm_curve.variance_ratio_36m` | 30.1176 | 30.2880 | -0.22 | - | - |
| `hqm_curve.variance_ratio_60m` | 47.9261 | 47.9161 | +0.01 | - | - |
| `hy_spread.mean_reversion_halflife` | - | - | - | - | - |
| `hy_spread.variance_ratio_120m` | - | - | - | - | - |
| `hy_spread.variance_ratio_12m` | - | - | - | - | - |
| `hy_spread.variance_ratio_36m` | - | - | - | - | - |
| `hy_spread.variance_ratio_60m` | - | - | - | - | - |
| `ig_spread.mean_reversion_halflife` | 1.6700 | 1.7884 | -1.03 | 14.9418 | -13.2718 |
| `ig_spread.variance_ratio_120m` | 33.0051 | 30.3870 | +0.47 | - | - |
| `ig_spread.variance_ratio_12m` | 7.7056 | 7.6273 | +0.23 | 10.6060 | -2.9004 |
| `ig_spread.variance_ratio_36m` | 15.4968 | 15.1301 | +0.21 | - | - |
| `ig_spread.variance_ratio_60m` | 22.2562 | 20.3772 | +0.65 | - | - |
| `mom.mean_reversion_halflife` | 0.4396 | 0.5167 | -0.68 | 0.1890 | +0.2506 |
| `mom.variance_ratio_120m` | 29.1845 | 30.3765 | -0.08 | - | - |
| `mom.variance_ratio_12m` | 4.9564 | 5.3844 | -0.26 | 1.1157 | +3.8407 |
| `mom.variance_ratio_36m` | 11.6442 | 12.4807 | -0.17 | - | - |
| `mom.variance_ratio_60m` | 17.9120 | 19.0735 | -0.14 | - | - |
| `policy_rate.mean_reversion_halflife` | 15.7318 | 15.4704 | +0.42 | 22.0937 | -6.3619 |
| `policy_rate.variance_ratio_120m` | 72.3550 | 71.9895 | +2.32 | - | - |
| `policy_rate.variance_ratio_12m` | 11.5276 | 11.5072 | +0.65 | 10.8265 | +0.7011 |
| `policy_rate.variance_ratio_36m` | 28.6002 | 28.5400 | +0.82 | - | - |
| `policy_rate.variance_ratio_60m` | 46.0515 | 45.8694 | +1.56 | - | - |
| `smb.mean_reversion_halflife` | 0.3525 | 0.3899 | -1.56 | 0.3977 | -0.0452 |
| `smb.variance_ratio_120m` | 12.0244 | 32.1098 | -1.74 | - | - |
| `smb.variance_ratio_12m` | 3.1586 | 5.0333 | -1.82 | 1.8746 | +1.2840 |
| `smb.variance_ratio_36m` | 6.2445 | 12.4388 | -1.77 | - | - |
| `smb.variance_ratio_60m` | 8.6362 | 18.7929 | -1.77 | - | - |
| `ust_10y.mean_reversion_halflife` | 5.2248 | 5.9392 | -2.29 | 42.9306 | -37.7057 |
| `ust_10y.variance_ratio_120m` | 92.1942 | 91.7162 | +0.15 | - | - |
| `ust_10y.variance_ratio_12m` | 11.3121 | 11.3343 | -0.80 | 12.0481 | -0.7360 |
| `ust_10y.variance_ratio_36m` | 31.4921 | 31.5431 | -0.13 | - | - |
| `ust_10y.variance_ratio_60m` | 50.7550 | 50.5661 | +0.19 | - | - |
| `ust_2y.mean_reversion_halflife` | 6.6723 | 7.3210 | -1.04 | 15.5876 | -8.9154 |
| `ust_2y.variance_ratio_120m` | 79.9585 | 78.9000 | +0.58 | - | - |
| `ust_2y.variance_ratio_12m` | 11.0122 | 11.0278 | -0.13 | - | - |
| `ust_2y.variance_ratio_36m` | 29.2062 | 29.1828 | +0.04 | - | - |
| `ust_2y.variance_ratio_60m` | 46.4564 | 46.1557 | +0.40 | - | - |

### The drawdown / duration joint

| metric | severe | primary | d (primary sd) | hist 66-84 | vs hist |
|---|---|---|---|---|---|
| `commodities.drawdown_depth_duration_rank_corr` | - | - | - | - | - |
| `commodities.drawdown_median_depth` | - | - | - | - | - |
| `commodities.drawdown_median_duration` | - | - | - | - | - |
| `commodities.lost_decade_frequency` | - | - | - | - | - |
| `equity_mkt.drawdown_depth_duration_rank_corr` | 0.8838 | 0.8850 | -0.43 | 0.9479 | -0.0641 |
| `equity_mkt.drawdown_median_depth` | 0.0422 | 0.0444 | -0.73 | 0.0686 | -0.0264 |
| `equity_mkt.drawdown_median_duration` | 3.0000 | 3.0000 | +0.0000 (abs) | 2.0000 | +1.0000 |
| `equity_mkt.lost_decade_frequency` | 0.2923 | 0.2428 | +107.48 | 0.0000 | +0.2923 |
| `hml.drawdown_depth_duration_rank_corr` | 0.9289 | 0.9100 | +0.80 | 0.9193 | +0.0095 |
| `hml.drawdown_median_depth` | 0.0452 | 0.3315 | -0.93 | 0.0404 | +0.0048 |
| `hml.drawdown_median_duration` | 6.3333 | 49.0000 | -0.94 | 4.0000 | +2.3333 |
| `hml.lost_decade_frequency` | 0.8880 | 0.9307 | -0.97 | 0.0000 | +0.8880 |
| `mom.drawdown_depth_duration_rank_corr` | 0.8344 | 0.8514 | -0.57 | 0.9118 | -0.0774 |
| `mom.drawdown_median_depth` | 0.0279 | 0.0297 | -0.90 | 0.0600 | -0.0321 |
| `mom.drawdown_median_duration` | 2.0000 | 2.0000 | +0.0000 (abs) | 4.0000 | -2.0000 |
| `mom.lost_decade_frequency` | 0.3499 | 0.4561 | -0.65 | 0.0000 | +0.3499 |
| `smb.drawdown_depth_duration_rank_corr` | 0.8255 | 0.8608 | -4.69 | 0.8944 | -0.0689 |
| `smb.drawdown_median_depth` | 0.0220 | 0.0224 | -0.16 | 0.0618 | -0.0398 |
| `smb.drawdown_median_duration` | 2.0000 | 2.0000 | +0.0000 (abs) | 5.0000 | -3.0000 |
| `smb.lost_decade_frequency` | 0.2744 | 0.6003 | -3.91 | 0.0459 | +0.2285 |

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
| `cpi.long_inflation_era_frequency` | horizon | 10yr | 0.4134 | 0.3802 | 0.0332 | 1.0000 | [0.2260, 0.6688] |
| `cpi.mean_reversion_halflife` | horizon | 1_5yr | 27.7042 | 26.7929 | 0.9113 | 61.1849 | [13.3564, 47.1680] |
| `cpi.variance_ratio_120m` | horizon | 1_5yr | 64.2242 | 64.6133 | -0.3891 | - | [nan, nan] |
| `cpi.variance_ratio_12m` | horizon | 1_5yr | 11.9209 | 11.9207 | 0.0002 | 12.5691 | [11.3485, 13.0992] |
| `cpi.variance_ratio_36m` | horizon | 1_5yr | 23.9447 | 24.1193 | -0.1746 | - | [nan, nan] |
| `cpi.variance_ratio_60m` | horizon | 1_5yr | 51.6250 | 51.7444 | -0.1194 | - | [nan, nan] |
| `equity_mkt.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8838 | 0.8850 | -0.0012 | 0.9479 | [nan, nan] |
| `equity_mkt.drawdown_median_depth` | horizon | 1_5yr | 0.0422 | 0.0444 | -0.0023 | 0.0686 | [nan, nan] |
| `equity_mkt.drawdown_median_duration` | horizon | 1_5yr | 3.0000 | 3.0000 | 0.0000 | 2.0000 | [nan, nan] |
| `equity_mkt.lost_decade_frequency` | horizon | 10yr | 0.2923 | 0.2428 | 0.0495 | 0.0000 | [0.0000, 0.1320] |
| `equity_mkt.mean_reversion_halflife` | horizon | 1_5yr | 0.2844 | 0.2797 | 0.0047 | 0.2364 | [0.1589, 0.4222] |
| `equity_mkt.variance_ratio_120m` | horizon | 1_5yr | 3.1154 | 2.1721 | 0.9433 | - | [nan, nan] |
| `equity_mkt.variance_ratio_12m` | horizon | 1_5yr | 1.0385 | 0.8161 | 0.2223 | 1.2251 | [0.3983, 2.0883] |
| `equity_mkt.variance_ratio_36m` | horizon | 1_5yr | 1.8577 | 1.4085 | 0.4491 | - | [nan, nan] |
| `equity_mkt.variance_ratio_60m` | horizon | 1_5yr | 2.4449 | 1.8044 | 0.6405 | - | [nan, nan] |
| `equity_vol.mean_reversion_halflife` | horizon | 1_5yr | 1.4809 | 1.6437 | -0.1628 | - | [1.9936, 5.2685] |
| `equity_vol.variance_ratio_120m` | horizon | 1_5yr | 47.3521 | 47.8851 | -0.5331 | - | [nan, nan] |
| `equity_vol.variance_ratio_12m` | horizon | 1_5yr | 8.6627 | 8.6495 | 0.0132 | - | [6.2371, 9.4084] |
| `equity_vol.variance_ratio_36m` | horizon | 1_5yr | 20.6879 | 20.7108 | -0.0229 | - | [nan, nan] |
| `equity_vol.variance_ratio_60m` | horizon | 1_5yr | 31.0740 | 30.9679 | 0.1061 | - | [nan, nan] |
| `funding_spread.mean_reversion_halflife` | horizon | 1_5yr | 1.3974 | 1.5737 | -0.1762 | - | [2.5453, 6.9164] |
| `funding_spread.variance_ratio_120m` | horizon | 1_5yr | 46.6300 | 48.4371 | -1.8070 | - | [nan, nan] |
| `funding_spread.variance_ratio_12m` | horizon | 1_5yr | 8.1487 | 8.6018 | -0.4531 | - | [5.2105, 10.6764] |
| `funding_spread.variance_ratio_36m` | horizon | 1_5yr | 18.9311 | 19.9802 | -1.0490 | - | [nan, nan] |
| `funding_spread.variance_ratio_60m` | horizon | 1_5yr | 29.4536 | 30.4427 | -0.9891 | - | [nan, nan] |
| `hml.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.9289 | 0.9100 | 0.0189 | 0.9193 | [nan, nan] |
| `hml.drawdown_median_depth` | horizon | 1_5yr | 0.0452 | 0.3315 | -0.2863 | 0.0404 | [nan, nan] |
| `hml.drawdown_median_duration` | horizon | 1_5yr | 6.3333 | 49.0000 | -42.6667 | 4.0000 | [nan, nan] |
| `hml.lost_decade_frequency` | horizon | 10yr | 0.8880 | 0.9307 | -0.0426 | 0.0000 | [0.0030, 0.2512] |
| `hml.mean_reversion_halflife` | horizon | 1_5yr | 0.5106 | 0.5980 | -0.0874 | 0.3930 | [0.1849, 0.5567] |
| `hml.variance_ratio_120m` | horizon | 1_5yr | 22.1577 | 29.8255 | -7.6678 | - | [nan, nan] |
| `hml.variance_ratio_12m` | horizon | 1_5yr | 4.6448 | 5.6144 | -0.9696 | 1.6501 | [0.6915, 2.3081] |
| `hml.variance_ratio_36m` | horizon | 1_5yr | 10.1492 | 12.9856 | -2.8364 | - | [nan, nan] |
| `hml.variance_ratio_60m` | horizon | 1_5yr | 14.2959 | 18.7171 | -4.4212 | - | [nan, nan] |
| `hqm_curve.mean_reversion_halflife` | horizon | 1_5yr | 4.0800 | 4.3132 | -0.2332 | 1.2295 | [8.2312, 27.4521] |
| `hqm_curve.variance_ratio_120m` | horizon | 1_5yr | 86.3212 | 86.4613 | -0.1401 | - | [nan, nan] |
| `hqm_curve.variance_ratio_12m` | horizon | 1_5yr | 10.9336 | 10.9456 | -0.0120 | - | [8.9064, 12.2628] |
| `hqm_curve.variance_ratio_36m` | horizon | 1_5yr | 30.1176 | 30.2880 | -0.1704 | - | [nan, nan] |
| `hqm_curve.variance_ratio_60m` | horizon | 1_5yr | 47.9261 | 47.9161 | 0.0100 | - | [nan, nan] |
| `hy_spread.mean_reversion_halflife` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_120m` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_12m` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_36m` | horizon | 1_5yr | - | - | - | - | - |
| `hy_spread.variance_ratio_60m` | horizon | 1_5yr | - | - | - | - | - |
| `ig_spread.mean_reversion_halflife` | horizon | 1_5yr | 1.6700 | 1.7884 | -0.1184 | 14.9418 | [6.0799, 27.7542] |
| `ig_spread.variance_ratio_120m` | horizon | 1_5yr | 33.0051 | 30.3870 | 2.6181 | - | [nan, nan] |
| `ig_spread.variance_ratio_12m` | horizon | 1_5yr | 7.7056 | 7.6273 | 0.0783 | 10.6060 | [7.8017, 12.5491] |
| `ig_spread.variance_ratio_36m` | horizon | 1_5yr | 15.4968 | 15.1301 | 0.3667 | - | [nan, nan] |
| `ig_spread.variance_ratio_60m` | horizon | 1_5yr | 22.2562 | 20.3772 | 1.8790 | - | [nan, nan] |
| `interval_coverage_50_5y` | calibration | 1_5yr | 0.3720 | 0.4422 | -0.0702 | - | - |
| `interval_coverage_90_5y` | calibration | 1_5yr | 0.8105 | 0.7503 | 0.0602 | - | - |
| `mom.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8344 | 0.8514 | -0.0170 | 0.9118 | [nan, nan] |
| `mom.drawdown_median_depth` | horizon | 1_5yr | 0.0279 | 0.0297 | -0.0018 | 0.0600 | [nan, nan] |
| `mom.drawdown_median_duration` | horizon | 1_5yr | 2.0000 | 2.0000 | 0.0000 | 4.0000 | [nan, nan] |
| `mom.lost_decade_frequency` | horizon | 10yr | 0.3499 | 0.4561 | -0.1061 | 0.0000 | [0.0000, 0.3499] |
| `mom.mean_reversion_halflife` | horizon | 1_5yr | 0.4396 | 0.5167 | -0.0771 | 0.1890 | [0.1706, 0.5252] |
| `mom.variance_ratio_120m` | horizon | 1_5yr | 29.1845 | 30.3765 | -1.1920 | - | [nan, nan] |
| `mom.variance_ratio_12m` | horizon | 1_5yr | 4.9564 | 5.3844 | -0.4281 | 1.1157 | [0.2687, 1.9267] |
| `mom.variance_ratio_36m` | horizon | 1_5yr | 11.6442 | 12.4807 | -0.8365 | - | [nan, nan] |
| `mom.variance_ratio_60m` | horizon | 1_5yr | 17.9120 | 19.0735 | -1.1615 | - | [nan, nan] |
| `pit_ks_stat_5y` | calibration | 1_5yr | 0.2574 | 0.3896 | -0.1322 | - | - |
| `policy_rate.mean_reversion_halflife` | horizon | 1_5yr | 15.7318 | 15.4704 | 0.2614 | 22.0937 | [8.1933, 90.9740] |
| `policy_rate.variance_ratio_120m` | horizon | 1_5yr | 72.3550 | 71.9895 | 0.3655 | - | [nan, nan] |
| `policy_rate.variance_ratio_12m` | horizon | 1_5yr | 11.5276 | 11.5072 | 0.0205 | 10.8265 | [9.5313, 12.6171] |
| `policy_rate.variance_ratio_36m` | horizon | 1_5yr | 28.6002 | 28.5400 | 0.0602 | - | [nan, nan] |
| `policy_rate.variance_ratio_60m` | horizon | 1_5yr | 46.0515 | 45.8694 | 0.1821 | - | [nan, nan] |
| `smb.drawdown_depth_duration_rank_corr` | horizon | 1_5yr | 0.8255 | 0.8608 | -0.0352 | 0.8944 | [nan, nan] |
| `smb.drawdown_median_depth` | horizon | 1_5yr | 0.0220 | 0.0224 | -0.0003 | 0.0618 | [nan, nan] |
| `smb.drawdown_median_duration` | horizon | 1_5yr | 2.0000 | 2.0000 | 0.0000 | 5.0000 | [nan, nan] |
| `smb.lost_decade_frequency` | horizon | 10yr | 0.2744 | 0.6003 | -0.3258 | 0.0459 | [0.1182, 0.5439] |
| `smb.mean_reversion_halflife` | horizon | 1_5yr | 0.3525 | 0.3899 | -0.0374 | 0.3977 | [0.1635, 0.5082] |
| `smb.variance_ratio_120m` | horizon | 1_5yr | 12.0244 | 32.1098 | -20.0854 | - | [nan, nan] |
| `smb.variance_ratio_12m` | horizon | 1_5yr | 3.1586 | 5.0333 | -1.8747 | 1.8746 | [0.3997, 2.3984] |
| `smb.variance_ratio_36m` | horizon | 1_5yr | 6.2445 | 12.4388 | -6.1942 | - | [nan, nan] |
| `smb.variance_ratio_60m` | horizon | 1_5yr | 8.6362 | 18.7929 | -10.1567 | - | [nan, nan] |
| `ust_10y.mean_reversion_halflife` | horizon | 1_5yr | 5.2248 | 5.9392 | -0.7144 | 42.9306 | [8.4362, 27.7645] |
| `ust_10y.variance_ratio_120m` | horizon | 1_5yr | 92.1942 | 91.7162 | 0.4781 | - | [nan, nan] |
| `ust_10y.variance_ratio_12m` | horizon | 1_5yr | 11.3121 | 11.3343 | -0.0222 | 12.0481 | [9.4122, 12.3796] |
| `ust_10y.variance_ratio_36m` | horizon | 1_5yr | 31.4921 | 31.5431 | -0.0510 | - | [nan, nan] |
| `ust_10y.variance_ratio_60m` | horizon | 1_5yr | 50.7550 | 50.5661 | 0.1889 | - | [nan, nan] |
| `ust_2y.mean_reversion_halflife` | horizon | 1_5yr | 6.6723 | 7.3210 | -0.6487 | 15.5876 | [10.4115, 58.5356] |
| `ust_2y.variance_ratio_120m` | horizon | 1_5yr | 79.9585 | 78.9000 | 1.0586 | - | [nan, nan] |
| `ust_2y.variance_ratio_12m` | horizon | 1_5yr | 11.0122 | 11.0278 | -0.0155 | - | [9.9799, 12.6519] |
| `ust_2y.variance_ratio_36m` | horizon | 1_5yr | 29.2062 | 29.1828 | 0.0234 | - | [nan, nan] |
| `ust_2y.variance_ratio_60m` | horizon | 1_5yr | 46.4564 | 46.1557 | 0.3007 | - | [nan, nan] |

## Support diagnostic (1965-launched decades)

| cell | extrapolation share (mean) | (max) | flagged off-support | regime TV (mean) |
|---|---|---|---|---|
| primary:s0 | 0.8606 | 1.0000 | 999 | 0.3267 |
| primary:s1 | 0.8652 | 1.0000 | 1001 | 0.3266 |
| primary:s2 | 0.8600 | 1.0000 | 1000 | 0.3265 |
| severe:s0 | 0.8663 | 1.0000 | 1011 | 0.3407 |
| severe:s1 | 0.8555 | 1.0000 | 1008 | 0.3405 |
| severe:s2 | 0.8627 | 1.0000 | 1006 | 0.3401 |

## Cells

| cell | criterion bearing | prereg verified | enforce pass | checkpoint |
|---|---|---|---|---|
| primary:s0 | True | True | True | `f0c79f000be659c8...` |
| primary:s1 | True | True | True | `6e06252943e45d51...` |
| primary:s2 | True | True | True | `38f385c6e87d12d2...` |
| severe:s0 | True | True | True | `dd589ac80071fbf1...` |
| severe:s1 | True | True | False | `a64463efa5fa9253...` |
| severe:s2 | True | True | True | `375b486be15a4f0a...` |

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
