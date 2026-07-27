# Regime skeleton fit report (WP2.6, Layer 2)

- config_hash: `cfg:1758709d4009c6ff`
- git_sha: `9f3c29b`
- seed: 20260727
- vintage_id: `2026-07-26.1`
- artifact content sha256: `e83b9e86f73a679e61d5f5929ee2f552f9eac3c190ecc2a62e6947ef329ef47d`
- climate (L1) artifact sha256: `98bdb68f3fd9753d5e10776772849bfa6bbe87f9a0fbd83952a7cad42000c487`
- ruleset: `regime_ruleset_v1`
- label span: 1926-07-01 .. 2020-12-01 (1134 months, 130 spells; first spell left-truncated and dropped, last right-censored)
- NUTS: 4 chain(s) x 1000 samples (1000 warmup), target_accept 0.9

## Empirical transition counts (sparsity, visible)

| from \ to | EXP | SLOW | REC | CRI | STAG | REF | total |
|---|---|---|---|---|---|---|---|
| EXP | 0 | 13 | 7 | 0 | 0 | 12 | 32 |
| SLOW | 17 | 0 | 10 | 0 | 3 | 4 | 34 |
| REC | 8 | 11 | 0 | 6 | 4 | 0 | 29 |
| CRI | 0 | 0 | 7 | 0 | 1 | 0 | 8 |
| STAG | 0 | 7 | 1 | 0 | 0 | 1 | 9 |
| REF | 6 | 3 | 5 | 2 | 1 | 0 | 17 |

Rare cells are regularized by the weakly informative Normal priors (priors.yaml): an unobserved transition's posterior stays near its prior rather than diverging; nothing is forced to zero.

## Convergence (R-hat, ESS, divergences)

- Divergences: 0
- max R-hat: 1.0008
- min ESS: 3748

| parameter | mean | sd | 5% | 95% | ESS | R-hat |
|---|---|---|---|---|---|---|
| alpha[EXP] | -2.7830 | 0.3639 | -3.3940 | -2.1993 | 5054 | 1.0002 |
| alpha[SLOW] | -0.0202 | 0.5526 | -0.9180 | 0.8861 | 4300 | 1.0000 |
| alpha[REC] | -2.2313 | 0.4096 | -2.8567 | -1.5382 | 4499 | 1.0008 |
| alpha[CRI] | -0.9594 | 0.9786 | -2.6198 | 0.5479 | 5209 | 0.9993 |
| alpha[STAG] | 0.3487 | 0.9358 | -1.0885 | 2.0296 | 5139 | 0.9998 |
| alpha[REF] | -1.6049 | 0.5160 | -2.4443 | -0.7756 | 4581 | 1.0000 |
| gamma[EXP,curve_slope] | -0.2347 | 0.2001 | -0.5590 | 0.0946 | 5907 | 0.9996 |
| gamma[EXP,credit_gap] | 0.1725 | 0.2282 | -0.1915 | 0.5484 | 6412 | 0.9996 |
| gamma[EXP,pi_gap] | 0.2695 | 0.3900 | -0.3552 | 0.9080 | 6186 | 0.9993 |
| gamma[EXP,drawdown_state] | -0.0283 | 0.4777 | -0.8145 | 0.7363 | 7444 | 0.9997 |
| gamma[SLOW,curve_slope] | -0.1771 | 0.2723 | -0.5954 | 0.2798 | 6316 | 0.9997 |
| gamma[SLOW,credit_gap] | -0.4076 | 0.2242 | -0.7872 | -0.0505 | 7014 | 0.9995 |
| gamma[SLOW,pi_gap] | -0.4300 | 0.3561 | -1.0033 | 0.1680 | 6239 | 0.9997 |
| gamma[SLOW,drawdown_state] | 0.6359 | 0.6603 | -0.4542 | 1.7219 | 8140 | 0.9997 |
| gamma[REC,curve_slope] | 0.1255 | 0.2822 | -0.3138 | 0.5999 | 5388 | 1.0000 |
| gamma[REC,credit_gap] | 0.2343 | 0.2364 | -0.1461 | 0.6342 | 6174 | 0.9994 |
| gamma[REC,pi_gap] | 0.0666 | 0.2544 | -0.3269 | 0.5084 | 7572 | 1.0001 |
| gamma[REC,drawdown_state] | 0.4902 | 0.6126 | -0.5106 | 1.4837 | 4806 | 1.0001 |
| gamma[CRI,curve_slope] | 0.4436 | 0.2278 | 0.0943 | 0.8262 | 4221 | 0.9997 |
| gamma[CRI,credit_gap] | -0.5626 | 0.4863 | -1.3724 | 0.2223 | 6570 | 0.9994 |
| gamma[CRI,pi_gap] | -0.2677 | 0.5380 | -1.1475 | 0.5933 | 5357 | 1.0008 |
| gamma[CRI,drawdown_state] | -0.4404 | 0.8426 | -1.8676 | 0.9495 | 6195 | 0.9994 |
| gamma[STAG,curve_slope] | -1.0685 | 0.4577 | -1.7803 | -0.3233 | 6206 | 0.9996 |
| gamma[STAG,credit_gap] | -0.0599 | 0.5616 | -0.9819 | 0.8556 | 7458 | 0.9995 |
| gamma[STAG,pi_gap] | -0.1393 | 0.4111 | -0.7694 | 0.5573 | 7252 | 0.9994 |
| gamma[STAG,drawdown_state] | 0.0018 | 0.7131 | -1.2146 | 1.1376 | 8833 | 0.9993 |
| gamma[REF,curve_slope] | -0.5122 | 0.2633 | -0.9539 | -0.0922 | 7585 | 0.9992 |
| gamma[REF,credit_gap] | 0.6355 | 0.2368 | 0.2576 | 1.0251 | 6976 | 0.9998 |
| gamma[REF,pi_gap] | -0.3840 | 0.3901 | -1.0015 | 0.2759 | 5561 | 0.9996 |
| gamma[REF,drawdown_state] | -0.3445 | 0.4831 | -1.1483 | 0.4309 | 7251 | 0.9995 |
| log_r[EXP] | -0.1813 | 0.2609 | -0.6286 | 0.2364 | 5724 | 0.9993 |
| log_r[SLOW] | 0.1081 | 0.4791 | -0.6569 | 0.9027 | 3748 | 1.0004 |
| log_r[REC] | -0.2655 | 0.3117 | -0.7919 | 0.2350 | 4771 | 1.0001 |
| log_r[CRI] | 0.1555 | 0.5839 | -0.7809 | 1.1373 | 4410 | 0.9999 |
| log_r[STAG] | 0.9957 | 0.7465 | -0.1542 | 2.2991 | 4241 | 1.0003 |
| log_r[REF] | 0.3521 | 0.3911 | -0.2932 | 0.9677 | 4556 | 0.9997 |
| trans_a[EXP->REC] | -0.6925 | 0.5254 | -1.5351 | 0.1866 | 7025 | 0.9995 |
| trans_a[EXP->CRI] | -3.5265 | 1.1551 | -5.3434 | -1.6344 | 5992 | 0.9994 |
| trans_a[EXP->STAG] | -3.2630 | 1.1569 | -5.1230 | -1.3644 | 6280 | 0.9994 |
| trans_a[EXP->REF] | -0.1177 | 0.4798 | -0.8960 | 0.6551 | 6623 | 1.0000 |
| trans_a[SLOW->REC] | -0.3296 | 0.4409 | -1.0447 | 0.3768 | 6934 | 0.9998 |
| trans_a[SLOW->CRI] | -3.6781 | 1.0860 | -5.3384 | -1.8624 | 5080 | 0.9994 |
| trans_a[SLOW->STAG] | -1.9377 | 0.7072 | -3.0921 | -0.7996 | 5190 | 0.9997 |
| trans_a[SLOW->REF] | -1.6998 | 0.6486 | -2.7767 | -0.6239 | 5979 | 1.0000 |
| trans_a[REC->SLOW] | 0.7535 | 0.5484 | -0.1362 | 1.6311 | 5244 | 0.9994 |
| trans_a[REC->CRI] | -0.8322 | 0.7289 | -1.9377 | 0.4197 | 4886 | 0.9998 |
| trans_a[REC->STAG] | -0.5473 | 0.7383 | -1.6817 | 0.7012 | 5537 | 0.9992 |
| trans_a[REC->REF] | -3.0266 | 1.2133 | -4.8993 | -0.9611 | 5772 | 0.9992 |
| trans_a[CRI->SLOW] | -0.9531 | 1.6536 | -3.6029 | 1.8405 | 6845 | 0.9995 |
| trans_a[CRI->REC] | 3.6223 | 1.1235 | 1.7125 | 5.4158 | 5112 | 0.9999 |
| trans_a[CRI->STAG] | 0.6704 | 1.3836 | -1.4125 | 3.1379 | 5431 | 1.0001 |
| trans_a[CRI->REF] | -1.3548 | 1.5963 | -3.8874 | 1.2711 | 5421 | 0.9999 |
| trans_a[STAG->SLOW] | 3.2491 | 1.1243 | 1.4291 | 5.0967 | 5339 | 0.9993 |
| trans_a[STAG->REC] | 0.7224 | 1.3343 | -1.5974 | 2.8030 | 5115 | 0.9995 |
| trans_a[STAG->CRI] | -1.6520 | 1.5358 | -4.0854 | 0.8646 | 5957 | 0.9997 |
| trans_a[STAG->REF] | -1.1492 | 1.3309 | -3.3598 | 0.9981 | 6280 | 0.9993 |
| trans_a[REF->SLOW] | -0.4778 | 0.7655 | -1.7101 | 0.7536 | 5638 | 0.9996 |
| trans_a[REF->REC] | -0.1459 | 0.7010 | -1.3156 | 0.9854 | 5337 | 0.9993 |
| trans_a[REF->CRI] | -2.0270 | 0.8921 | -3.3810 | -0.4851 | 5682 | 0.9995 |
| trans_a[REF->STAG] | -2.8305 | 1.0052 | -4.4923 | -1.2400 | 4517 | 0.9993 |
| trans_b[SLOW,curve_slope] | 0.2107 | 0.3202 | -0.3306 | 0.7037 | 5937 | 0.9999 |
| trans_b[SLOW,credit_gap] | -0.2552 | 0.3083 | -0.7771 | 0.2355 | 5328 | 1.0001 |
| trans_b[SLOW,pi_gap] | 0.4586 | 0.4099 | -0.2061 | 1.1503 | 5307 | 0.9997 |
| trans_b[SLOW,drawdown_state] | -0.4054 | 0.5832 | -1.2875 | 0.6292 | 7051 | 0.9996 |
| trans_b[REC,curve_slope] | -0.7110 | 0.3056 | -1.2016 | -0.2046 | 5679 | 0.9994 |
| trans_b[REC,credit_gap] | -0.1041 | 0.2575 | -0.5261 | 0.3166 | 5179 | 0.9999 |
| trans_b[REC,pi_gap] | 0.1222 | 0.4317 | -0.6476 | 0.7571 | 4608 | 0.9993 |
| trans_b[REC,drawdown_state] | 0.1299 | 0.6091 | -0.9032 | 1.1154 | 6851 | 0.9994 |
| trans_b[CRI,curve_slope] | -0.5898 | 0.3472 | -1.1495 | -0.0191 | 6066 | 0.9996 |
| trans_b[CRI,credit_gap] | -0.1449 | 0.4331 | -0.8333 | 0.6019 | 6475 | 0.9994 |
| trans_b[CRI,pi_gap] | 0.9028 | 0.4557 | 0.1570 | 1.6431 | 4905 | 0.9997 |
| trans_b[CRI,drawdown_state] | 1.6731 | 0.6379 | 0.6159 | 2.7159 | 5894 | 0.9993 |
| trans_b[STAG,curve_slope] | -0.1692 | 0.3770 | -0.7835 | 0.4501 | 5688 | 0.9994 |
| trans_b[STAG,credit_gap] | 0.0854 | 0.4118 | -0.6249 | 0.7278 | 6578 | 0.9999 |
| trans_b[STAG,pi_gap] | 1.9945 | 0.4700 | 1.2252 | 2.7736 | 4836 | 1.0001 |
| trans_b[STAG,drawdown_state] | -0.8333 | 0.7463 | -2.0890 | 0.3393 | 8137 | 0.9993 |
| trans_b[REF,curve_slope] | -0.1514 | 0.3499 | -0.7393 | 0.4007 | 5517 | 0.9998 |
| trans_b[REF,credit_gap] | 0.0945 | 0.3370 | -0.4470 | 0.6697 | 5130 | 0.9996 |
| trans_b[REF,pi_gap] | 1.9653 | 0.4806 | 1.1329 | 2.7052 | 4909 | 0.9999 |
| trans_b[REF,drawdown_state] | 0.2318 | 0.6496 | -0.8647 | 1.2526 | 6400 | 0.9995 |

## Fitted sojourns at z = 0 (posterior E[D], months)

| regime | mean E[D] | 5% | 95% |
|---|---|---|---|
| EXP | 14.7 | 9.7 | 20.9 |
| SLOW | 2.2 | 1.7 | 2.8 |
| REC | 8.5 | 5.6 | 12.7 |
| CRI | 5.5 | 1.7 | 14.1 |
| STAG | 3.4 | 1.7 | 6.6 |
| REF | 8.6 | 5.0 | 13.9 |

## Posterior-mean transition probabilities at z = 0

| from \ to | EXP | SLOW | REC | CRI | STAG | REF |
|---|---|---|---|---|---|---|
| EXP | 0.000 | 0.398 | 0.207 | 0.019 | 0.025 | 0.351 |
| SLOW | 0.466 | 0.000 | 0.339 | 0.018 | 0.080 | 0.096 |
| REC | 0.238 | 0.483 | 0.000 | 0.115 | 0.145 | 0.019 |
| CRI | 0.036 | 0.028 | 0.840 | 0.000 | 0.080 | 0.017 |
| STAG | 0.048 | 0.808 | 0.107 | 0.016 | 0.000 | 0.020 |
| REF | 0.357 | 0.238 | 0.316 | 0.060 | 0.029 | 0.000 |

## Covariates z(s) and standardization

DN-1.1 SS II.3: z(s) = (curve_slope, credit_gap, pi_gap, drawdown_state).
Standardization constants (train+val fit span; the 0/1 drawdown dummy is
left unstandardized) -- applied identically at simulation time:

| covariate | mean | sd |
|---|---|---|
| curve_slope | 1.2114 | 1.2805 |
| credit_gap | -0.9521 | 5.4009 |
| pi_gap | 0.8322 | 3.8800 |
| drawdown_state | 0.0000 | 1.0000 |

- pi_target: 2.0 (configured constant; see priors.yaml)
- curve slope: fred.GS10 - fred.TB3MS from 1953-04; JST annual long-short
  spread (usa_ltrate - usa_stir) held within-year before that (splice).
- historical credit_gap / pi_gap: WP2.5 posterior-mean smoothed path.
- SIMULATION-side proxies (recorded limitation): curve_slope becomes
  psi0 - phi_c0*c(R_t) (the L1 posterior-mean model-implied slope, which
  compresses slope variance -- no simulated inversions, so the fitted
  inversion channel is attenuated at generation time); drawdown_state
  becomes 1[R_t == CRI] (historically drawdowns also breach the threshold
  outside CRI months).

## The cycle term c_t (the WP2.5 contract)

c_t = cycle_by_regime[R_t], the train+val mean of L1's own fitting proxy
(1 - 2*USREC) within each label -- proxy-consistent by construction, so the
fitted phi_c/delta_L keep their meaning. Unsmoothed: the proxy the anchor
was fitted against is itself a +/-1 step function.

| regime | c |
|---|---|
| EXP | +1.000 |
| SLOW | +1.000 |
| REC | +0.040 |
| CRI | -1.000 |
| STAG | +1.000 |
| REF | +1.000 |

## Acceptance: simulated durations/frequencies vs train+val bootstrap bands

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
| freq | EXP | 0.459 | 0.339 | 0.574 | 0.375 | YES |
| freq | SLOW | 0.071 | 0.038 | 0.111 | 0.084 | YES |
| freq | REC | 0.198 | 0.132 | 0.271 | 0.267 | YES |
| freq | CRI | 0.082 | 0.026 | 0.156 | 0.071 | YES |
| freq | STAG | 0.030 | 0.005 | 0.063 | 0.041 | YES |
| freq | REF | 0.160 | 0.073 | 0.250 | 0.163 | YES |
| median_dur | EXP | 12.000 | 6.000 | 14.000 | 7.000 | YES |
| median_dur | SLOW | 2.000 | 1.000 | 2.000 | 2.000 | YES |
| median_dur | REC | 4.000 | 3.000 | 8.500 | 4.000 | YES |
| median_dur | CRI | 8.500 | 4.000 | 13.000 | 4.000 | YES |
| median_dur | STAG | 4.000 | 1.463 | 5.000 | 2.000 | YES |
| median_dur | REF | 6.000 | 2.500 | 10.000 | 5.000 | YES |
| p90_dur | EXP | 31.000 | 18.400 | 52.537 | 28.200 | YES |
| p90_dur | SLOW | 4.700 | 4.000 | 7.000 | 5.000 | YES |
| p90_dur | REC | 18.200 | 10.298 | 21.000 | 18.000 | YES |
| p90_dur | CRI | 21.700 | 9.400 | 42.000 | 16.300 | YES |
| p90_dur | STAG | 8.000 | 2.000 | 8.000 | 5.000 | YES |
| p90_dur | REF | 27.800 | 10.000 | 35.800 | 20.000 | YES |

Inside: 18 / 18 judged bands.
