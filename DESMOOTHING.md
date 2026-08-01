# DESMOOTHING.md — de-smoothing diagnostics

| series | method | k | theta | sigma ratio | beta before | beta after | mean diff | Ljung-Box |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| albourne.hf_activist_ret_m | geltner_ar1 | 1 | 0.95, 0.05 | 1.05 | nan | nan | +0.0000 | ok |
|   -> albourne.hf_activist_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_asia_ls_ret_m | glm_ma | 2 | 0.75, 0.15, 0.10 | 1.30 | nan | nan | +0.0000 | ok |
| albourne.hf_cb_arb_ret_m | glm_ma | 1 | 0.70, 0.30 | 1.31 | nan | nan | +0.0000 | ok |
| albourne.hf_cta_ret_m | geltner_ar1 | 1 | 0.93, 0.07 | 1.07 | nan | nan | +0.0000 | ok |
|   -> albourne.hf_cta_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_distressed_ret_m | glm_ma | 2 | 0.65, 0.25, 0.10 | 1.43 | 0.25 | 0.38 | +0.0000 | ok |
| albourne.hf_em_fi_ret_m | glm_ma | 1 | 0.75, 0.25 | 1.27 | 0.29 | 0.38 | +0.0000 | ok |
| albourne.hf_em_ls_ret_m | glm_ma | 1 | 0.80, 0.20 | 1.21 | nan | nan | +0.0000 | ok |
| albourne.hf_europe_ls_ret_m | geltner_ar1 | 1 | 0.88, 0.12 | 1.13 | nan | nan | +0.0000 | ok |
|   -> albourne.hf_europe_ls_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_fi_arb_ret_m | geltner_ar1 | 1 | 0.91, 0.09 | 1.10 | nan | nan | +0.0000 | ok |
|   -> albourne.hf_fi_arb_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_fund_emn_ret_m | geltner_ar1 | 1 | 0.88, 0.12 | 1.12 | nan | nan | +0.0000 | ok |
|   -> albourne.hf_fund_emn_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_gaa_ret_m | geltner_ar1 | 1 | 0.93, 0.07 | 1.07 | nan | nan | -0.0000 | Q=17.6>15.5 |
|   -> albourne.hf_gaa_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_global_macro_ret_m | geltner_ar1 | 1 | 0.97, 0.03 | 1.03 | nan | nan | -0.0000 | Q=19.1>15.5 |
|   -> albourne.hf_global_macro_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_insurance_ret_m | glm_ma | 1 | 0.80, 0.20 | 1.21 | nan | nan | +0.0000 | ok |
| albourne.hf_japan_ls_ret_m | geltner_ar1 | 1 | 0.89, 0.11 | 1.11 | 0.17 | 0.19 | +0.0000 | ok |
|   -> albourne.hf_japan_ls_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_ms_diversified_ret_m | glm_ma | 1 | 0.75, 0.25 | 1.25 | nan | nan | +0.0000 | Q=17.8>15.5 |
| albourne.hf_quant_emn_ret_m | glm_ma | 2 | 0.85, 0.10, 0.05 | 1.16 | nan | nan | +0.0000 | Q=16.7>15.5 |
| albourne.hf_risk_arb_ret_m | geltner_ar1 | 1 | 0.95, 0.05 | 1.05 | 0.12 | 0.12 | +0.0000 | ok |
|   -> albourne.hf_risk_arb_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_rv_credit_ret_m | glm_ma | 2 | 0.55, 0.30, 0.15 | 1.53 | nan | nan | -0.0000 | ok |
| albourne.hf_stat_arb_ret_m | geltner_ar1 | 1 | 0.89, 0.11 | 1.11 | 0.06 | 0.07 | -0.0000 | ok |
|   -> albourne.hf_stat_arb_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |
| albourne.hf_structured_credit_ret_m | glm_ma | 1 | 0.85, 0.15 | 1.15 | 0.15 | 0.18 | +0.0000 | ok |
| albourne.hf_us_ls_ret_m | geltner_ar1 | 1 | 0.91, 0.09 | 1.10 | nan | nan | +0.0000 | ok |
|   -> albourne.hf_us_ls_ret_m warnings | boundary solution (theta_0 ~ 1); falling back to Geltner AR(1) | | | | | | | |

## HF sections (WP2R.2)

Vintage: `2026-08-01.2`; equity reference: `french.mkt_rf`; primary method GLM MA(k),
Geltner AR(1) run as secondary (table below). Parameters and diagnostics only —
no observation values; the COMM-licensed inputs stay in gitignored `data/`.

**Material smoothing** (some lag weight > 0.10): albourne.hf_asia_ls_ret_m, albourne.hf_cb_arb_ret_m, albourne.hf_distressed_ret_m, albourne.hf_em_fi_ret_m, albourne.hf_em_ls_ret_m, albourne.hf_europe_ls_ret_m, albourne.hf_fund_emn_ret_m, albourne.hf_insurance_ret_m, albourne.hf_japan_ls_ret_m, albourne.hf_ms_diversified_ret_m, albourne.hf_rv_credit_ret_m, albourne.hf_stat_arb_ret_m, albourne.hf_structured_credit_ret_m.

**Negligible smoothing**: albourne.hf_activist_ret_m, albourne.hf_cta_ret_m, albourne.hf_fi_arb_ret_m, albourne.hf_gaa_ret_m, albourne.hf_global_macro_ret_m, albourne.hf_quant_emn_ret_m, albourne.hf_risk_arb_ret_m, albourne.hf_us_ls_ret_m.

### Geltner AR(1) secondary

| series | method | k | theta | sigma ratio | beta before | beta after | mean diff | Ljung-Box |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| albourne.hf_activist_ret_m | geltner_ar1 | 1 | 0.95, 0.05 | 1.05 | nan | nan | +0.0000 | ok |
| albourne.hf_asia_ls_ret_m | geltner_ar1 | 1 | 0.79, 0.21 | 1.23 | nan | nan | +0.0000 | ok |
| albourne.hf_cb_arb_ret_m | geltner_ar1 | 1 | 0.57, 0.43 | 1.58 | nan | nan | +0.0000 | ok |
| albourne.hf_cta_ret_m | geltner_ar1 | 1 | 0.93, 0.07 | 1.07 | nan | nan | +0.0000 | ok |
| albourne.hf_distressed_ret_m | geltner_ar1 | 1 | 0.61, 0.39 | 1.50 | 0.25 | 0.40 | -0.0000 | ok |
| albourne.hf_em_fi_ret_m | geltner_ar1 | 1 | 0.68, 0.32 | 1.39 | 0.29 | 0.42 | -0.0000 | ok |
| albourne.hf_em_ls_ret_m | geltner_ar1 | 1 | 0.74, 0.26 | 1.29 | nan | nan | -0.0001 | ok |
| albourne.hf_europe_ls_ret_m | geltner_ar1 | 1 | 0.88, 0.12 | 1.13 | nan | nan | +0.0000 | ok |
| albourne.hf_fi_arb_ret_m | geltner_ar1 | 1 | 0.91, 0.09 | 1.10 | nan | nan | +0.0000 | ok |
| albourne.hf_fund_emn_ret_m | geltner_ar1 | 1 | 0.88, 0.12 | 1.12 | nan | nan | +0.0000 | ok |
| albourne.hf_gaa_ret_m | geltner_ar1 | 1 | 0.93, 0.07 | 1.07 | nan | nan | -0.0000 | Q=17.6>15.5 |
| albourne.hf_global_macro_ret_m | geltner_ar1 | 1 | 0.97, 0.03 | 1.03 | nan | nan | -0.0000 | Q=19.1>15.5 |
| albourne.hf_insurance_ret_m | geltner_ar1 | 1 | 0.74, 0.26 | 1.31 | nan | nan | -0.0000 | ok |
| albourne.hf_japan_ls_ret_m | geltner_ar1 | 1 | 0.89, 0.11 | 1.11 | 0.17 | 0.19 | +0.0000 | ok |
| albourne.hf_ms_diversified_ret_m | geltner_ar1 | 1 | 0.60, 0.40 | 1.52 | nan | nan | +0.0000 | ok |
| albourne.hf_quant_emn_ret_m | geltner_ar1 | 1 | 0.85, 0.15 | 1.16 | nan | nan | +0.0000 | ok |
| albourne.hf_risk_arb_ret_m | geltner_ar1 | 1 | 0.95, 0.05 | 1.05 | 0.12 | 0.12 | +0.0000 | ok |
| albourne.hf_rv_credit_ret_m | geltner_ar1 | 1 | 0.44, 0.56 | 1.89 | nan | nan | -0.0000 | ok |
| albourne.hf_stat_arb_ret_m | geltner_ar1 | 1 | 0.89, 0.11 | 1.11 | 0.06 | 0.07 | -0.0000 | ok |
| albourne.hf_structured_credit_ret_m | geltner_ar1 | 1 | 0.81, 0.19 | 1.21 | 0.15 | 0.19 | +0.0000 | ok |
| albourne.hf_us_ls_ret_m | geltner_ar1 | 1 | 0.91, 0.09 | 1.10 | nan | nan | +0.0000 | ok |
