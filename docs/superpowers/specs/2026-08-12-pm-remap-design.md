# PM Sleeve Re-Mapping (v1.1: Lagged Sum-Beta) — Design Note

Pre-declaration for amendment `AM-2026-08-12-001`. This note is committed
**before** the v1.1 estimator runs — the parameters below are fixed here,
not tuned after seeing the numbers.

## Finding A (noted and deferred, not fixed by this amendment)

`ah/core/engine.py::_reported_marks` samples only the quarter-end month's
single true return through the smoothing filter, discarding the other two
months of each quarter. Over the 1974 stress decade this makes reported PE
cumulate roughly 27% against a true return of roughly 125% — an order-of-
magnitude display defect, not a beta-mismeasurement one. It is deliberately
out of scope here: fixing it changes the *toy engine's* output and requires
a `TOY_ENGINE_VERSION` bump plus a new preset `world_id` block of its own.
It is deferred to a later, separately-scoped WP.

## Finding B (fixed by this amendment)

The v1.0 PM sleeve loadings under-state market beta, and MAPPINGS.md
already recorded the warning at estimation time, under "Reading these
numbers: the de-smoother is under-correcting":

> EVERY estimated equity beta lands below its DN-5 prior, and the shortfall
> sorts by how equity-like the sleeve is. The credit and real-asset sleeves
> come out near their priors (distressed 1.09x, infra 0.83x, mezzanine
> 0.75x); the equity-like ones come out far below (growth 0.57x, VC 0.36x,
> buyout 0.29x, secondaries 0.23x, RE value-add 0.17x).

and on the smoothing kernel itself:

> the Geltner phi for the appraisal sleeves is only 0.18 over the full
> sample, while the stress-state refit puts it at 0.47 — the full-sample
> operator is weak precisely because the smoothing is state-dependent and
> the calm majority dominates the fit.

and its explicit instruction on `pm_direct_lending`:

> `pm_direct_lending` is the weakest cell in the table and should not be
> used: 39 quarters after the constituent trim, an all-zero loading vector,
> R^2 of -0.00, and a de-smoother that fell back to a literal no-op.

v1.0 adoption carried these loadings into the twin without an owner ruling
on the under-correction warning or the "should not be used" instruction.
The trigger for re-opening this now is a product-surface credibility
finding on the generated 1974 world: PE decade Sharpe 1.30, with pe/pc/re
visibly decoupled from public factors — the realized form of exactly what
MAPPINGS.md warned about.

## Declared parameters

| Parameter | Value | Why |
|---|---|---|
| Lagged regressor | `equity_mkt` only, quarterly lags | dof discipline on 60–146-quarter panels; equity carries the appraisal-lag signal |
| Lag rule | n ≥ 80 quarters → 4 lags; 40 ≤ n < 80 → 2 lags; n < 40 → estimation refused, DN-5 prior adopted verbatim | pre-declared so lag count can't be tuned to taste |
| Reported loading | Dimson sum: contemporaneous + all lag betas, one number | runtime applies loadings to TRUE factors where no lag belongs; the lag lives only in the observation process |
| Bounds/priors on lags | each lag bounded `[0, inf)`, ridge prior 0; contemporaneous keeps its DN-5 prior | shrinkage target stays the recorded prior |
| `pm_direct_lending` | betas + residual sigma estimated on `cliffwater.bdc_ret_m` (monthly, market-priced), then multiplied by `bdc_delever_factor = 0.5`; alpha from the albourne DL composite mean net of those betas | v1.0's own report: the asset-level fit "should not be used"; BDCs are ~1x levered listed vehicles, hence the declared 0.5 |
| HF sleeves | copied verbatim from v1.0 | out of scope; unchanged inputs to the G1 record |
| De-smoothing | unchanged from v1.0 (family-routed Geltner/GLM) | the lag terms mop up what the operator misses; changing both at once would be unattributable |
| `residual_correlation`, `cta_rule` | copied verbatim from v1.0 | HF-only structures |
| Artifact/version | `mappings/sleeve-mappings-v1.1.yaml`, `mapping_version: map-2026.08.2` | append-only; v1.0 stays sealed as the G1-era record |
| World fence | `stagflation_1974` world_id `…601` → `…602` | scores under different formulas never share a leaderboard row |

## Non-goals

- **No re-score of the G1-completion gate.** Its FAIL (`G1-EVIDENCE.md`)
  stands, recorded under v1.0. This amendment does not revisit that verdict.
- **No engine change.** `ah/core/engine.py` is untouched by this amendment;
  Finding A is deferred separately.
- **No change to `GEN_PLAY_ALPHA_VERSION`.** The alpha *definition* is
  unchanged — only the PM sleeve loadings feeding it move, and the world
  fence (not the alpha version) is what keeps v1.0- and v1.1-scored runs
  from sharing a leaderboard row.
