# MAPPINGS.md — factor -> sleeve mapping diagnostics (WP3.2)

Vintage `2026-08-07.5`; composites de-smoothed (GLM MA(k)), train+validation only;
final loadings on train+val, OOS diagnostic fit on train / scored on validation.
Artifact: `mappings/sleeve-mappings-v1.0.yaml` (`map-2026.08`).
`hf_cta` is a rule, not a regression (DN-5 §3.4) — see `ah/port/mapping.py`.

Superseded for PM sleeves by `mappings/sleeve-mappings-v1.1.yaml` (`map-2026.08.2`)
— PM rows re-estimated (Dimson sum-beta / BDC anchor / prior-adopted, per-row
`route`), HF rows/`residual_correlation`/`cta_rule` carried over verbatim from
v1.0. This is the artifact the runtime (`ah.port.mapping.ARTIFACT_PATH`) now
loads (AM-2026-08-12-001). The HF table and diagnosis below still describe
v1.0/v1.1's shared HF estimates; the PM table below is v1.0-only and is kept
for the smoothing diagnosis it documents — see `mappings/sleeve-mappings-v1.1.yaml`
for the numbers actually in force.

| sleeve | equity_mkt | smb | hml | mom | d_level | d_slope | d_ig | resid sigma (ann) | R² | OOS R² | β_mkt smooth | β_mkt desm | β_mkt exp | β_mkt rec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hf_credit | +0.218 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.052 | 5.2% | 0.43 | 0.32 | +0.134 | +0.218 | +0.135 | +nan |
| hf_equity_ls | +0.265 | +0.036 | -0.047 | +0.066 | +0.000 | +0.000 | +0.000 | 3.8% | 0.49 | 0.48 | +0.211 | +0.265 | +0.246 | +nan |
| hf_event | +0.423 | +0.082 | +0.085 | +0.000 | +0.000 | +0.000 | -0.030 | 5.1% | 0.68 | 0.59 | +0.324 | +0.423 | +0.381 | +nan |
| hf_macro | +0.079 | +0.000 | +0.000 | +0.000 | -0.007 | +0.002 | +0.000 | 5.0% | 0.05 | -0.15 | +0.075 | +0.079 | +0.101 | +nan |
| hf_multi | +0.217 | +0.000 | +0.000 | +0.000 | +0.001 | +0.000 | -0.042 | 7.1% | 0.26 | 0.15 | +0.119 | +0.217 | +0.204 | +nan |
| hf_rv | +0.000 | +0.000 | +0.000 | +0.000 | +0.008 | -0.007 | -0.043 | 5.2% | 0.15 | -0.01 | +0.000 | +0.000 | +0.000 | +nan |

## PM sleeves (quarterly)

Estimated on the first PriMaRS delivery. Composites de-smoothed with the
sleeve's OWN family (SM-10): Geltner for the appraisal-calendar sleeves,
GLM elsewhere. Priors are `cashflow-tier1-v1.0.yaml`'s `pm_growth_loadings`
— frozen as *chosen* because no PM data existed; these are the estimates
that supersede them.

| sleeve | family | n (quarters) | equity_mkt | smb | hml | mom | d_level | d_slope | d_ig | prior β_mkt | resid sigma (ann) | R² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pm_buyout | glm | 125 | +0.348 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.029 | +1.20 | 12.8% | 0.20 |
| pm_direct_lending | glm | 39 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.000 | +0.00 | 8.3% | -0.00 |
| pm_distressed | glm | 87 | +0.383 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.104 | +0.35 | 7.5% | 0.68 |
| pm_growth | glm | 94 | +0.744 | +0.000 | -0.546 | +0.000 | +0.000 | +0.000 | +0.000 | +1.30 | 18.1% | 0.43 |
| pm_infra | geltner | 60 | +0.249 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.30 | 5.8% | 0.36 |
| pm_mezzanine | glm | 102 | +0.226 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.069 | +0.30 | 5.8% | 0.55 |
| pm_re_value_add | geltner | 85 | +0.087 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.50 | 12.9% | 0.01 |
| pm_secondaries | glm | 89 | +0.251 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.056 | +1.10 | 10.8% | 0.27 |
| pm_vc | glm | 120 | +0.433 | +0.000 | -0.349 | +0.000 | +0.000 | +0.000 | +0.000 | +1.20 | 24.6% | 0.11 |

### Reading these numbers: the de-smoother is under-correcting

EVERY estimated equity beta lands below its DN-5 prior, and the shortfall
sorts by how equity-like the sleeve is. The credit and real-asset sleeves
come out near their priors (distressed 1.09x, infra 0.83x, mezzanine
0.75x); the equity-like ones come out far below (growth 0.57x, VC 0.36x,
buyout 0.29x, secondaries 0.23x, RE value-add 0.17x). Venture — the most
equity-like private asset there is — explains 11% of its own variance
against a 120-quarter panel, and RE value-add explains 1%.

That ordering is the signature of RESIDUAL SMOOTHING surviving the
de-smoothing operator, not of private equity genuinely having a third of
the market beta its economics imply. It is corroborated by the smoothing
kernel fitted alongside: the Geltner phi for the appraisal sleeves is only
0.18 over the full sample, while the stress-state refit puts it at 0.47 —
the full-sample operator is weak precisely because the smoothing is
state-dependent and the calm majority dominates the fit.

CONSEQUENCE, stated rather than buried: these loadings are ESTIMATES and
they supersede the priors as a record of what the delivered data says —
but 'measured' is not automatically 'better'. Adopting beta_mkt 0.087 for
RE value-add in place of the 0.50 prior would encode the smoothing defect
into the twin. Whether the twin consumes these loadings or keeps the
priors is an owner decision, not a consequence of running this script.
The Cliffwater BDC series (market-priced, same asset class as direct
lending, annualized vol 21.6% against this panel's 8.3% residual sigma)
is the natural instrument for calibrating how much correction is missing.

`pm_direct_lending` is the weakest cell in the table and should not be used:
39 quarters after the constituent trim, an all-zero loading vector, R^2 of
-0.00, and a de-smoother that fell back to a literal no-op.

Residual correlations on 225 common months; the D1 exhibit is the β_mkt smooth-vs-desmoothed pair (smoothed marks understate market exposure).
