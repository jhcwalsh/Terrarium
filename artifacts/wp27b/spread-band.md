# WP2.7b — the `ig_spread` band is now regime-conditional

Correction to WP2.7's waypoint construction, prompted by
`artifacts/wp28/ig-spread-diagnosis.md`. Nothing sealed was touched: the whole
joinery lives under `src/ah/gen/`, which `prereg._REQUIRED_JUDGED_SOURCES` does
not cover (re-verified). No retraining, no sampler change, `beta_L` untouched,
`cb-v1` untouched.

**The rule this work was done under:** the band is a property of the REFERENCE.
Every choice below was made from the train+validation history and fixed *before*
either sampler was run against it. No estimator, shrinkage strength or floor was
selected because of what it did to a generator's number.

## 1. What the reference says about the old pooled width

Campaign vintage `2026-07-26.1`, train+validation 1990-01..2020-12 (372 months),
band residual `e_t = ig_spread_t - mu_spread(R_t) - beta_L * credit_gap_t`
(`beta_L = 0.0011521`, unchanged).

| regime | n months | episodes | rho (lag-1, within-episode) | n_eff (mean) | n_eff (variance) | raw resid sd | centre mu_spread |
|---|---|---|---|---|---|---|---|
| EXP  | 231 | 11 | 0.922 |  9.37 | 18.71 | 0.2117 | 0.831 |
| SLOW |  30 | 14 | 0.503 |  9.93 | 17.89 | 0.1675 | 0.932 |
| REC  |  80 | 10 | 0.742 | 11.83 | 23.16 | 0.2329 | 1.121 |
| CRI  |  17 |  3 | 0.825 |  1.63 |  3.24 | 1.0041 | 1.957 |
| STAG |   5 |  2 | 0.204 |  3.30 |  4.60 | 0.0708 | 0.974 |
| REF  |   9 |  4 | 0.174 |  6.33 |  8.47 | 0.0960 | 0.943 |

Three facts, all about the data and none about any generator:

1. **The variances are not equal.** Max/min variance ratio **201x**. A Bartlett-style
   pooled log-variance statistic is 210.5 against a null built by permuting whole
   contiguous regime EPISODES (so the null keeps the serial structure): p50 75.1,
   p95 144.0, **p = 0.0034** over 5,000 permutations. A single pooled width is a
   homoskedasticity assumption the reference rejects.
2. **The pooled width is a crisis statistic in disguise.** CRI is 4.6% of the months
   and **51%** of the pooled residual variance. Shrinking the quiet regimes toward
   the arithmetic pool re-imports exactly that contamination.
3. **The reference cannot sit inside its own pooled band.** Real 1990-2020 spreads
   fall outside `mu_spread(CRI) +/- 0.292` in **16 of 17 CRI months (94.1%)**, and
   outside the STAG and REF bands in **0** months. The generator-side evidence
   (the bootstrap, drawing real CRI blocks, exits 86.7% of the time) was a symptom
   of this, not the cause.

Every regime is also far less informative than its month count suggests: the
lag-1 autocorrelation of the residual gives **1.6 to 12 effective observations**
per regime — EXP's 231 months included — and the independent count of contiguous
episodes (2 to 14) agrees within a factor of two.

## 2. The estimator

For each regime R, with `s_R^2` the residual variance about that regime's own mean,
`rho_R` the lag-1 autocorrelation over contiguous month pairs inside the regime
(clipped to `[0, 0.95]`), `n_eff_R = n(1-rho)/(1+rho)` and `nu_R = n(1-rho^2)/(1+rho^2) - 1`:

```
sigma_R^2   = (nu_R * s_R^2 + nu0 * s0^2) / (nu_R + nu0)          nu0 = BAND_PRIOR_DF = 1
s0^2        = exp( sum_R nu_R * ln s_R^2 / sum_R nu_R )           (information-weighted
                                                                   GEOMETRIC mean)
half-width  = sigma_R * sqrt(1 + 1 / n_eff_R)                     (predictive sd)
```

Justifications, each from the data:

- **Conditioning at all** — section 1, fact 1 (p = 0.0034).
- **AR(1) effective sizes** rather than month counts — the residual is strongly
  serially correlated (rho up to 0.92); using n would claim 231 observations for
  EXP where the data support ~9-19.
- **Shrinkage** — STAG's raw sd of 0.071 rests on 5 months from 2 episodes and REF's
  0.096 on 9 months from 4. Without shrinkage the joinery would assert a +/-7bp
  stagflation band on that evidence.
- **nu0 = 1**, the weakest proper shrinkage, stated rather than fitted. The
  empirical-Bayes marginal MLE (scaled-inverse-chi2 prior, `s_R^2/s0^2 ~ F(nu_R, nu0)`)
  brackets it — `nu0 = 1.25` with the prior centred on the pooled variance, `1.78`
  with `(nu0, s0)` fitted jointly — but that hyperparameter is **not robustly
  identified from six groups**: leave-one-regime-out moves it from 1.4 to 17.8 when
  CRI is the group dropped. The fit is reported as corroboration, not adopted.
- **Geometric rather than arithmetic prior centre** — section 1, fact 2. The joint
  EB fit independently prefers a centre of 0.155 against the arithmetic pool's
  0.294; the information-weighted geometric mean is 0.188 and needs no fitting.
- **Predictive inflation** — the centre `mu_spread(R)` is itself estimated on
  `n_eff_R` observations, so a year-end level deviates from the *estimated* centre
  by `sigma_R * sqrt(1 + 1/n_eff_R)`. This is how the CRI centre's noise is carried.

**Resulting half-widths** (campaign vintage; pooled width was 0.2920 everywhere):

| regime | n | n_eff (mean) | raw sd | shrunk sigma_R | **half-width** | vs pooled |
|---|---|---|---|---|---|---|
| EXP  | 231 |  9.37 | 0.2117 | 0.2105 | **0.2214** | 0.76x |
| SLOW |  30 |  9.93 | 0.1675 | 0.1687 | **0.1770** | 0.61x |
| REC  |  80 | 11.83 | 0.2329 | 0.2311 | **0.2407** | 0.82x |
| CRI  |  17 |  1.63 | 1.0041 | 0.8414 | **1.0682** | 3.66x |
| STAG |   5 |  3.30 | 0.0708 | 0.1079 | **0.1231** | 0.42x |
| REF  |   9 |  6.33 | 0.0960 | 0.1110 | **0.1194** | 0.41x |

Typical width `s0` = 0.1883; pooled (kept as the absent-regime fallback) = 0.2920.
Averaged over generated year-ends the mean half-width barely moves (0.2920 ->
0.2858, -2%): the change is almost purely a **reallocation** of width across
regimes, not a loosening or a tightening.

### What was deliberately NOT done

- **The centre is unchanged.** `mu_spread(CRI) = 1.957` rests on 17 months
  (`n_eff` 1.63) and is genuinely noisy — its standard error is ~0.79, so the
  claim "crises have wider spreads" is only ~1.3 standard errors from the
  unconditional mean, while the claim "crises have wider DISPERSION" is
  significant at p = 0.003. Shrinking the centre toward the unconditional mean
  would bias the crisis target toward normal-times levels, which is the failure
  DN-1.1's regime conditioning exists to prevent, and it would also flatter a
  regime-blind sampler. Centre uncertainty is carried in the width instead.
- **No Student-t correction** for the variance's own uncertainty. A t-scaled
  68.27% band would widen CRI a further ~17% and STAG ~12%. Omitted to keep one
  convention (`+/- 1 predictive sd`), and recorded here so the omission is visible.
- **No coverage target.** The `+/- 1 sd` convention is WP2.7's and is preserved
  verbatim; only the estimate of that sd changed. Re-scaling the band to preserve
  the OLD band's incidental 84.9% in-sample coverage was considered and rejected:
  that coverage is an artifact of the mis-specified pooled estimate, not a design
  target, and enshrining it would be fitting to the thing just refuted.
- **`beta_L` is untouched** (0.0011521, i.e. ~0 — a separate, already-recorded finding).

## 3. Re-measurement — both samplers, same seeds, same waypoints

`scripts/measure_spread_band.py`, seed 20260727, 256 decades x 120 months,
diffusion at **block width 128 on CUDA**. The comparison is exact, not approximate:
the band enters the assembled path only through the reconciliation TARGET, while
the raw block stream is conditioned on the band's CENTRE, which did not change.
One assembly per sampler therefore serves both band definitions, and the raw
year-end deviations are identical between the two columns by construction.

Control: the old-band diffusion numbers reproduce the committed WP2.8 diagnosis
to five decimals (p50 0.20411 / p90 0.51396 / exit 0.614 against 0.2041 / 0.5140 /
61.4%).

### Band-exit rate

| population | old band | new band |
|---|---|---|
| **historical, all months (the honest reference)** | **15.1%** | **27.4%** |
| historical, Decembers only | 16.1% | 35.5% |
| bootstrap year-ends (`joinery-bootstrap-v0`) | 20.7% | 25.9% |
| diffusion year-ends (`hier-diffusion-v1`) | 61.4% | 69.1% |

The historical rate rises because the old pooled band was, for the four common
regimes, a ~1.4-sigma band wearing a 1-sigma label; the new one is an honest
1-sigma band (a normal would exit 31.7%). The bootstrap now lands within 1.5
points of the reference (25.9% vs 27.4%) — the benchmark is calibrated against
history rather than against a width its own crisis blocks could not reach. The
diffusion sampler is **2.5x the reference rate**, which is the finding.

### Mean excursion (how far outside, not just how often)

| | old | new |
|---|---|---|
| historical | 0.0445 | **0.0295** |
| bootstrap | 0.0595 | **0.0380** (-36%) |
| diffusion | 0.2615 | **0.2608** (-0.3%) |

**The fix helps the reference and the benchmark and does essentially nothing for
the trained sampler.** That is the headline result and it is not a happy one for
WP2.8: with a band the bootstrap can hit in every regime, the diffusion sampler's
excursion is unchanged, so the 8x reconciliation gap was never mostly a band
artifact. The ratio of mean excursions moves from 4.4x to **6.9x**.

### Per-regime band-exit rate

| regime | share of year-ends | hist old | hist new | boot old | boot new | diff old | diff new |
|---|---|---|---|---|---|---|---|
| EXP  | 37.1% | 11.3% | 22.9% | 11.7% | 18.6% | 54.3% | 64.9% |
| REC  | 30.2% | 16.3% | 33.8% | 20.3% | 31.3% | 63.6% | 70.4% |
| REF  | 10.6% |  0.0% | 22.2% |  9.2% | 43.2% | 61.6% | 87.1% |
| SLOW |  9.2% |  3.3% | 36.7% | 11.0% | 28.8% | 55.5% | 75.0% |
| CRI  |  9.1% | **94.1%** | **52.9%** | **86.7%** | **8.6%** | **90.6%** | **51.5%** |
| STAG |  3.7% |  0.0% |  0.0% | 10.5% | 41.1% | 57.9% | 78.9% |

CRI is repaired: the benchmark now sits inside its crisis band 91% of the time
instead of 13%. CRI's contribution to the bootstrap's total excursion falls from
**24.0% to 1.9%**.

**CRI still exits 52.9% historically, and that is a real limitation, not a
residual defect of the estimator.** The 17 CRI months are three episodes with
completely different credit behaviour — 2001-06..11 at 0.79-0.88 (an equity
crisis in which IG spreads never moved), 2008-09..2009-06 at 1.66-3.38, and
2020-03 at 1.27. No unimodal band centred on their mean can contain all three.
The `regime_ruleset_v1` CRI label is not a credit-spread state, and any tighter
CRI target would need a conditioning variable the label does not carry.

### Denton reconciliation adjustment (`mean |x-z|` per decade, 256 decades)

| sampler | factor | old p50 / p90 | new p50 / p90 |
|---|---|---|---|
| bootstrap | ig_spread | 0.02634 / 0.15091 | **0.02601 / 0.07924** |
| diffusion | ig_spread | 0.20411 / 0.51396 | **0.18198 / 0.52168** |

`cpi`, `equity_mkt` and `policy_rate` are bit-identical between the two columns —
the band touches only the `ig_spread` target, as designed.

## 4. Sealed battery, re-run under the new band

See `artifacts/wp27b/battery-joinery/` and `artifacts/wp27b/battery-diffusion/`.
Both at the sealed `n_paths = 1024`, seed 20260727, filtered and unfiltered.
**Declared:** the diffusion run used **block width 128 on CUDA** (WP2.8b), while
the committed WP2.8 verdict was produced at width 1 on CPU. Cross-width results
differ at float32 round-off — WP2.8b measured the worst per-factor gap at 1.8e-5
of that factor's own cross-ensemble sd — which is immaterial to a verdict but is
stated rather than hidden, and is recorded in each ensemble's lineage as
`conditioning.block_sampler_batch` / `block_sampler_device`.

WP2.7's and WP2.8's published reconciliation numbers are **superseded** by this
change; their battery verdicts are re-run here rather than assumed.
