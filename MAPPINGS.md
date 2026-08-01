# MAPPINGS.md — factor -> sleeve mapping diagnostics (WP3.2)

Vintage `2026-08-01.2`; composites de-smoothed (GLM MA(k)), train+validation only;
final loadings on train+val, OOS diagnostic fit on train / scored on validation.
Artifact: `mappings/sleeve-mappings-v1.0.yaml` (`map-2026.08`).
`hf_cta` is a rule, not a regression (DN-5 §3.4) — see `ah/port/mapping.py`.

| sleeve | equity_mkt | smb | hml | mom | d_level | d_slope | d_ig | resid σ (ann) | R² | OOS R² | β_mkt smooth | β_mkt desm | β_mkt exp | β_mkt rec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hf_credit | +0.218 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | -0.052 | 5.2% | 0.43 | 0.32 | +0.134 | +0.218 | +0.135 | +nan |
| hf_equity_ls | +0.265 | +0.036 | -0.047 | +0.066 | +0.000 | +0.000 | +0.000 | 3.8% | 0.49 | 0.48 | +0.211 | +0.265 | +0.246 | +nan |
| hf_event | +0.423 | +0.082 | +0.085 | +0.000 | +0.000 | +0.000 | -0.030 | 5.1% | 0.68 | 0.59 | +0.324 | +0.423 | +0.381 | +nan |
| hf_macro | +0.079 | +0.000 | +0.000 | +0.000 | -0.007 | +0.002 | +0.000 | 5.0% | 0.05 | -0.15 | +0.075 | +0.079 | +0.101 | +nan |
| hf_multi | +0.217 | +0.000 | +0.000 | +0.000 | +0.001 | +0.000 | -0.042 | 7.1% | 0.26 | 0.15 | +0.119 | +0.217 | +0.204 | +nan |
| hf_rv | +0.000 | +0.000 | +0.000 | +0.000 | +0.008 | -0.007 | -0.043 | 5.2% | 0.15 | -0.01 | +0.000 | +0.000 | +0.000 | +nan |

Residual correlations on 225 common months; the D1 exhibit is the β_mkt smooth-vs-desmoothed pair (smoothed marks understate market exposure).
