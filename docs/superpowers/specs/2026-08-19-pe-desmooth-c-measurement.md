# Route-C measurement: a state-dependent de-smoother for buyout

**Date:** 2026-08-19 - **Branch:** `pe-desmooth-01` (from `main` `c54c373`) -
**Script:** `scripts/pe_desmooth_c_estimation.py` (read-only against the shared
store; every number below is in the JSON sidecar
`2026-08-19-pe-desmooth-c-measurement.json`) - **Status:** MEASUREMENT ONLY.
Nothing sealed was changed.

---

## Verdict — the mechanism is real; the amendment is not supportable from inside this repo

**Route C was measured end to end and it does not produce the fix it was
hoped to produce.** The state-dependent smoothing mechanism is confirmed —
in calm quarters the buyout index shows *no detectable smoothing at all*,
while in recession quarters only 55% of a quarter's economic reality reaches
that quarter's mark — and buyout's own measured stickiness (0.45) lands
almost exactly on the 0.4508 the sealed kernel measured for real estate and
infrastructure. But pushing that de-smoother through the whole pipeline
moves almost nothing that matters:

- the reconstructed GFC drawdown deepens by only **3.3 points** (-26.05% -> -29.30%),
  still roughly **26 points short** of what the repo's one external anchor implies;
- the refit equity beta **does not rise** (0.8362 -> 0.8144 fitted / 0.8483 transferred);
- the unconditional intercept — the serenity finding's single most decisive
  number — **goes up, not down** (8.06%/yr -> 8.65% / 8.52%);
- on The Gulf Decade the refit rows leave PE **as serene or more serene** than
  the sealed row (median decade +257.66% -> +271.59% under Variant 1; paths
  where PE beats equity 169/200 -> 175/200);
- the D-preview finds **no downside kink on any reconstruction** (|t| < 0.8),
  so running Route D after C would find nothing either.

The reason is plain once seen: **the index never recorded the crash.** Its
worst GFC quarter is -15.01% and its whole GFC peak-to-trough is -25.61%.
A de-smoother can only redistribute and amplify what the marks contain; it
cannot recover information that was never written down. The answer moves to
**option F — external, crisis-visible data** — exactly as the serenity
finding anticipated it might.

---

## 1. Calibration (Step 0) — the pipeline reproduces the sealed row exactly

Before measuring anything new, the script rebuilds the sealed `pm_buyout` row
from scratch: raw composite (single member, `albourne.pm_buyout_ret_q`,
125 quarters 1989Q4-2020Q4), the current unconditional de-smoother
(`glm_ma` full sample — reproduces `k=1, theta=[0.85, 0.15]` exactly), then
the same fit function the sealed row came from
(`scripts/estimate_sleeve_mappings_v1_2.py`, loaded via `importlib` so no
code was copied). Every target matched to the seal's own rounding:

| quantity | sealed | reproduced |
|---|---:|---:|
| alpha_quarterly | 0.019441 | 0.019441 |
| equity_mkt (Dimson sum) | 0.8362 | 0.8362 |
| d_ig | -0.0279 | -0.0279 |
| residual_sigma_annual | 0.1225 | 0.1225 |
| r2_train_val | 0.269 | 0.269 |

One note: the catalog's current vintage is now `2026-08-10.1` (the sealed
artifact stamps `2026-08-07.5`); the buyout and factor series are unchanged
between the two, and the reproduction is exact anyway. The Step-6 machinery
was separately validated by rebuilding the sealed PE tape term-by-term and
asserting it bit-identical (1e-12) to `ah.port.adapter.run_gen_path` on
three of the 200 paths — and by recovering the serenity finding's own
numbers (+532.15% live decade, -30.09% crash year, 169/200) independently.

## 2. The three equations, side by side

Monthly true PE return on the generated plane, in decimal (the serenity
finding's form). The inflation term's 0.35 is CHOSEN (ratified lambda_PE)
and is identical in all three; a refit of the measured row does not move it.

**Sealed (all coefficients MEASURED on the unconditional reconstruction):**

```
r_pe(t) = 0.019441/3 + 0.8362*equity_mkt(t) - 0.0279*d_ig(t)
          - 0.35*(cpi_trail_excess(t)/12)/100 + eps(t)*0.1225/sqrt(12)
```

**Variant 1 — MEASURED state-dependent de-smoother (calm: no smoothing;
stress: theta=[0.55, 0.45] on 12 recession quarters):**

```
r_pe(t) = 0.020805/3 + 0.8144*equity_mkt(t) + 0.0182*smb(t) - 0.0435*d_ig(t)
          - 0.35*(cpi_trail_excess(t)/12)/100 + eps(t)*0.1157/sqrt(12)
```

**Variant 2 — ASSUMED transfer of the geltner-pool stickiness 0.4508
(theta_stress=[0.4668, 0.5332]; buyout is NOT in that pool):**

```
r_pe(t) = 0.020518/3 + 0.8483*equity_mkt(t) + 0.1350*smb(t) - 0.0312*d_ig(t)
          - 0.35*(cpi_trail_excess(t)/12)/100 + eps(t)*0.1576/sqrt(12)
```

Annualised intercepts, as the adapter compounds them: sealed **8.06%/yr**,
V1 **8.65%/yr**, V2 **8.52%/yr**. Read that again: the alpha the serenity
finding flagged as "paid at full rate through a collapse" gets slightly
*larger* under both variants, because amplifying crash quarters that later
mean-revert nudges the reconstruction's average return up (4.32% ->
4.40%/4.50% per quarter), and the intercept absorbs the difference.

## 3. What the state-dependent fit actually found (Steps 1-2)

Plain-language key: `theta[0]` is the share of a quarter's true economic
return that shows up in that quarter's reported mark; the rest leaks into
later quarters. `theta=[1, 0]` means marks are honest; `theta=[0.55, 0.45]`
means nearly half of a bad quarter is deferred into the next print.

- **Stress indicator:** `fred.USREC` (NBER recessions), reindexed to the
  composite's quarterly dates with forward-fill — the house `_stress_split`
  method, unchanged. This yields **12 stress quarters** (the brief guessed
  ~14; the exact-date reindex sees quarter-start dates, so 1990Q3 and 2020Q1
  fall out): 1990Q4, 1991Q1; 2001Q2-Q4; 2008Q1-2009Q2 (six); 2020Q2. Calm: 113.
- **Calm fit: no smoothing detected.** The MA fit hit the estimator's own
  boundary (theta_0 ~ 1; the house rule treats theta_0 >= 0.9 as "no
  smoothing" and refuses to fabricate precision) and fell back to Geltner
  with a lag weight of 0.007 — i.e. calm-quarter marks are essentially
  honest. Reconstruction uses identity [1, 0] for calm quarters; treating
  the near-identity Geltner pair as MA weights instead changes the
  reconstruction by at most 0.24pp in any quarter and nothing in the GFC
  drawdown, so nothing hangs on that choice.
- **Stress fit: theta=[0.55, 0.45]** (`glm_ma`, k=1 by AIC, no boundary, no
  fallback). Implied buyout-own stickiness: **1 - 0.55/1.00 = 0.45** —
  within rounding of the 0.4508 the sealed kernel measured for
  infra + RE. The repo's belief that "marks get roughly twice as sticky when
  markets fall" now has a buyout-native measurement behind it, not just a
  transferred one.

**Identification honesty — read before believing the 0.45:**

- 12 observations, on a 0.05-step grid (the estimator's resolution: theta is
  only ever a multiple of 0.05).
- The concatenated stress sample contains **3 splices** (non-adjacent
  quarters glued together; the ACF objective treats each seam as a real
  adjacency). Calm side: 4 splices among 113, negligible there.
- **Leave-one-episode-out, stress theta_0:** drop 1990-91 -> 0.50 (k moves
  to 2); drop 2001 -> 0.55; drop **2008-09 -> 0.80**; drop 2020 -> 0.60.
  Range **0.50-0.80** — wide, but it never crosses the calm value (1.0), so
  the *direction* (stress marks are stickier) survives every drop. The
  *magnitude* does not: without the GFC the implied stickiness collapses
  from 0.45 to **0.20**. This estimate is, to first order, a statement about
  six quarters of 2008-09.
- Variant 2's alternative calm anchor: using the calm-split value (~0.99)
  instead of the full-sample 0.85 gives theta0_stress = 0.545 — i.e. the
  transfer then lands on Variant 1's own fitted 0.55. The two variants are
  the same claim seen from two directions; V2 as specified (0.85-based,
  theta0_stress 0.4668) is the more aggressive of the two.

## 4. The crisis drawdown table — the headline

Peak-to-trough of the compounded quarterly series inside each episode
window (windows span peak-before to recovery-after; all numbers MEASURED
except the V2 column, which inherits ASSUMED from the transfer):

| series | sigma/quarter | ACF1 | worst quarter | 1990-91 | 2001 | **2008-09** | 2020 |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw reported index | 6.17% | +0.18 | -15.01% (2008Q4) | -5.52% | -18.91% | **-25.61%** | -7.27% |
| current "truth" (unconditional) | 7.16% | -0.01 | -16.22% (2008Q4) | -10.48% | -19.57% | **-26.05%** | -9.55% |
| Variant 1 (measured) | 6.95% | -0.08 | -18.88% (1990Q4) | -18.88% | -16.75% | **-29.30%** | -7.27% |
| Variant 2 (ASSUMED) | 9.03% | **-0.34** | -32.85% (1990Q4) | -32.85% | -20.18% | **-29.59%** | -9.55% |

Against the one external anchor the repo holds: secondaries cleared at
**0.60 of NAV in 2009-H1** (`docs/data/secondaries.md`, itself flagged
"illustrative"). If reported NAV sat 25.61% below peak at the trough and the
market cleared claims at 0.60 of that, the market-implied true peak-to-trough
is **about -55%** (DERIVED from an assumed anchor; clearing prices include a
liquidity discount, so treat -55% as the aggressive end). The reconstructions
reach **-29.3% / -29.6%**. The state-dependent de-smoother closes about an
eighth of the gap between the current truth series and the anchor.

Two honesty flags on the table itself:

- **Variant 2's worst episode is 1990-91, not the GFC** (-32.85%), because
  the uniform transfer amplifies the index's known outlier quarters there
  (the data review's only |z| >= 6 observations are two *positive* 1990-91
  prints beside it). That is an artifact of over-amplification, not a
  discovery about the Gulf War recession.
- **Variant 2's reconstruction has ACF1 = -0.34**: strong *negative*
  autocorrelation, meaning the inversion overshoots and fabricates
  quarter-on-quarter reversals that were never there. A correct de-smoother
  should leave roughly zero (Variant 1: -0.08; current: -0.01). By the
  de-smoothing module's own whiteness standard, the 0.4508 transfer is too
  strong for this index — a second, independent reason to distrust V2.
- Variant 1 leaves 2020 untouched (-7.27%, the raw value): the single 2020
  stress quarter (Q2) was a rebound quarter, and the crash mark (Q1) is
  calm-labelled under NBER quarter-start dating. State-dependent
  de-smoothing keyed to NBER dates misses fast crashes entirely.

## 5. The refit rows (Step 4) — what changes and what refuses to

Same fit function, same 125 quarters, same priors and ridge; the only input
that changes is the truth series.

| | sealed | Variant 1 (measured) | Variant 2 (ASSUMED) |
|---|---:|---:|---:|
| alpha_quarterly | 0.019441 | 0.020805 | 0.020518 |
| alpha, %/yr as applied | **8.06** | **8.65** | **8.52** |
| equity_mkt (Dimson sum, 4 lags) | **0.8362** | **0.8144** | **0.8483** |
| smb | 0.0 | 0.0182 | 0.1350 |
| hml / mom / d_level / d_slope | 0.0 | 0.0 | 0.0 |
| d_ig | -0.0279 | **-0.0435** | -0.0312 |
| residual_sigma_annual | 0.1225 | 0.1157 | 0.1576 |
| r2_train_val | 0.269 | 0.307 | 0.238 |

(The v1.2 fit function returns only the summed equity beta; it does not
expose the per-lag Dimson decomposition, so none is reported.)

Reading it honestly:

- **The beta does not rise.** `MAPPINGS.md`'s circularity hypothesis — "the
  beta is low because the de-smoother is weak" — is *not confirmed by
  measurement*: fixing the de-smoother's state-dependence leaves the equity
  loading within +/-0.02 of the sealed value in both directions. Twelve
  amplified quarters out of 125 cannot move a ridge-shrunk Dimson sum.
- **The one genuine improvement is the credit channel.** Variant 1 deepens
  `d_ig` from -0.0279 to -0.0435 (+56%) and raises R^2 to 0.307 with a
  *smaller* residual — the amplified crash quarters are better explained,
  and specifically by credit-spread moves. The serenity finding measured the
  sealed credit term as worth ~0.04 of extra downside beta in a crisis;
  V1 would make that ~0.06. Real, but roughly a quarter-point of extra PE
  loss in a -20% equity month — not a crash channel.
- **The intercept problem is untouched, slightly worsened.** 8.06 -> 8.65%/yr.

## 6. The D-preview (Step 5) — D after C finds nothing

The serenity probe's asymmetry regression, quarterly, per reconstruction
(`r_pe = a + b*r_eq + c*r_eq*1{r_eq<0} + d*1{r_eq<0}`; contemporaneous only,
so `b` is not comparable to the Dimson 0.8362 — this is a kink detector,
not a beta estimate):

| reconstruction | kink c | t(c) |
|---|---:|---:|
| current unconditional | +0.069 | 0.32 |
| Variant 1 | +0.052 | 0.25 |
| Variant 2 (ASSUMED) | -0.201 | -0.73 |

No reconstruction shows an identifiable downside kink; 125 quarters of this
index cannot distinguish any of these from zero. **Running Route D (an
asymmetric-beta refit) after C would return "no asymmetry."** The one
mildly interesting sign: V2's kink is *negative* — another symptom of its
over-inverted reversals, not of PE resilience.

## 7. The Gulf Decade what-if (Step 6)

World `...712`, seed 202608, 200 paths at the platform stride; the sealed
case is asserted bit-identical to `run_gen_path`. Equity reference: live
tape +107.51%, median +149.91%.

| | sealed | Variant 1 | Variant 2 (ASSUMED) |
|---|---:|---:|---:|
| live-tape decade PE | +532.15% | +563.55% | +695.85% |
| median decade PE (200 paths) | +257.66% | **+271.59%** | +257.81% |
| median PE max drawdown | -31.52% | -29.82% | -36.76% |
| paths PE beats equity | 169/200 | **175/200** | 158/200 |
| crash-year PE, live tape (months 48-59) | -30.09% | -29.45% | -30.01% |
| median crash-year PE | +16.55% | +17.72% | +15.86% |
| alpha term, %/yr | 8.06 | 8.65 | 8.52 |

**Variant 1 makes the serenity marginally worse on every axis that
mattered:** higher median decade, shallower median drawdown, more
equity-beating paths, milder crash year, bigger always-on intercept.
Variant 2 deepens the median max drawdown to -36.76% — but through a 29%
larger *idiosyncratic* residual (0.1576 vs 0.1225), i.e. random-time
drawdowns, precisely the "wrong shape" the serenity finding already
diagnosed; its crash-year response is unchanged (-30.01% vs -30.09%) and
its live tape *gains* 164 points of decade return from the same lucky
residual draws, now amplified.

## 8. Recommendation, with reasons

1. **Do not amend the sealed mapping on this evidence.** The brief's own
   support test fails: the reconstruction says buyout's GFC drawdown was
   about -29%, the refit moves the row by amounts that leave every
   player-facing symptom the same or worse, and the only external anchor
   (illustrative) sits ~26 points deeper. Amending a seal to ship V1 would
   change digests, worlds and leaderboards to make PE *more* serene.
2. **Keep the measurement — it is the repo's first crisis-conditional
   buyout smoothing estimate, and it is directionally solid.** Calm marks
   honest, stress marks ~2x sticky (0.45, matching the pool's 0.4508),
   GFC-dominated identification (0.20 without 2008-09). Worth citing in the
   ER-16 discussion and in any future kernel work; not worth a seal event.
3. **The answer is option F — external data.** The binding constraint is not
   the de-smoother, it is that the Albourne index never recorded the crash
   (worst GFC quarter -15%). No operator fitted on this index can restore
   what the anchor implies. A crisis-visible series (Burgiss/Cambridge/State
   Street composites, listed-PE, or real secondaries pricing) is the only
   route to a supportable amendment; the serenity finding's options
   A + B + E remain the right interim posture.
4. **If anything from this run is ever adopted piecemeal, it is Variant 1's
   credit loading** (d_ig -0.0435, R^2 0.307, smaller residual) — the one
   coefficient that moved for the right reason. But it cannot be adopted
   alone honestly: it comes from the same refit whose beta fell and whose
   alpha rose, and cherry-picking one coefficient from a rejected fit is
   exactly the tuning the seal exists to prevent.

## 9. Deviations from the brief, recorded

- The brief expected ~14 stress quarters; the house reindex method yields
  **12** (exact-date matching at quarter starts drops 1990Q3 and 2020Q1).
  Counts and the full quarter list are in the JSON.
- The brief suggested passing a modified row through
  `_pm_true_monthly_path`'s `rows` argument; that argument is the ensemble's
  source-row indices, not the mapping row (the function reads the artifact
  internally). The what-if instead rebuilds the PE tape term-by-term and
  asserts the sealed case bit-identical (1e-12) to `run_gen_path` — the
  same validation the serenity probe used.
- The calm-side fit fell back to Geltner at the boundary ("no smoothing
  detected"), so Variant 1's calm state uses identity weights, with the
  sensitivity reconstruction reported (max difference 0.24pp/quarter, GFC
  drawdown identical).

## 10. What this run touched

New files only: the script, this document, the JSON sidecar. `data/` was
read through the same `Catalog`/`DataAccess` path every sealed estimator
uses; `data/ah.db` was opened `mode=ro`; all series access went through
`DataAccess.train_val` (holdout untouched). No sealed file, mapping, schema
or register entry was edited. Deterministic end to end: the only RNG is the
adapter's own residual stream at the platform stride.
