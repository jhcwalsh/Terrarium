# Data review - outliers and gaps (mechanical sweep)

Vintage **2026-08-07.5**, as of 2026-08-08. 70 series with data, 9 registered-never-fetched. Soft outlier = robust |z| >= 6.0 on the units-appropriate basis; hard = impossible value.

## Hard flags (impossible values)
- none

## Gaps (missing periods inside span)
- none: every fetched series is gap-free inside its span

## Staleness vs SLA
- **jst.usa_cpi**: 2411d old vs SLA 400d (1870-01..2020-01)
- **jst.usa_crisis**: 2411d old vs SLA 400d (1870-01..2020-01)
- **jst.usa_eq_tr**: 2411d old vs SLA 400d (1872-01..2020-01)
- **jst.usa_gdp**: 2411d old vs SLA 400d (1870-01..2020-01)
- **jst.usa_housing_tr**: 2411d old vs SLA 400d (1891-01..2020-01)
- **jst.usa_ltrate**: 2411d old vs SLA 400d (1870-01..2020-01)
- **jst.usa_stir**: 2411d old vs SLA 400d (1870-01..2020-01)
- **jst.usa_tloans**: 2411d old vs SLA 400d (1880-01..2020-01)
- **shiller.dividend**: 798d old vs SLA 60d (1871-01..2024-06)
- **shiller.earnings**: 798d old vs SLA 60d (1871-01..2024-06)
- **shiller.cape**: 706d old vs SLA 60d (1881-01..2024-09)
- **shiller.price**: 706d old vs SLA 60d (1871-01..2024-09)
- **bis.credit_gap_us**: 311d old vs SLA 280d (1957-10..2025-10)
- **fred.DTWEXBGS**: 38d old vs SLA 7d (2006-01..2026-07)
- **fred.CPI**: 68d old vs SLA 40d (1913-01..2026-06)
- **fred.CPI_CORE**: 68d old vs SLA 40d (1957-01..2026-06)
- **fred.INDPRO**: 68d old vs SLA 40d (1919-01..2026-06)
- **albourne.hf_distressed_ret_m**: 99d old vs SLA 75d (2002-01..2026-05)
- **albourne.hf_em_fi_ret_m**: 99d old vs SLA 75d (2002-01..2026-05)
- **albourne.hf_japan_ls_ret_m**: 99d old vs SLA 75d (2002-01..2026-05)
- **albourne.hf_risk_arb_ret_m**: 99d old vs SLA 75d (2008-06..2026-05)
- **albourne.hf_stat_arb_ret_m**: 99d old vs SLA 75d (2005-06..2026-05)
- **albourne.hf_structured_credit_ret_m**: 99d old vs SLA 75d (2003-04..2026-05)
- **fred.AAA**: 38d old vs SLA 35d (1919-01..2026-07)
- **fred.BAA**: 38d old vs SLA 35d (1919-01..2026-07)
- **fred.GS10**: 38d old vs SLA 35d (1953-04..2026-07)
- **fred.TB3MS**: 38d old vs SLA 35d (1934-01..2026-07)

## Statistical outliers (soft, top 3 per series)
- **fred.TB3MS** (pct, 60 obs at |z|>=6.0): 1980-05-01 diff-z=-44.5 (value 8.5800); 1981-11-01 diff-z=-25.8 (value 10.8600); 1982-08-01 diff-z=-25.7 (value 8.6800)
- **fred.INDPRO** (idx, 40 obs at |z|>=6.0): 1933-05-01 log-diff-z=+17.5 (value 4.7392); 2020-04-01 log-diff-z=-16.7 (value 84.5619); 1933-06-01 log-diff-z=+16.2 (value 5.4663)
- **fred.FEDFUNDS** (pct, 35 obs at |z|>=6.0): 1980-05-01 diff-z=-44.7 (value 10.9800); 1981-02-01 diff-z=-21.2 (value 15.9300); 1980-03-01 diff-z=+20.6 (value 17.1900)
- **shiller.dividend** (index, 31 obs at |z|>=6.0): 1938-12-01 log-diff-z=-16.1 (value 0.5100); 1938-11-01 log-diff-z=-14.8 (value 0.5600); 1938-10-01 log-diff-z=-13.7 (value 0.6100)
- **fred.AAA** (pct, 28 obs at |z|>=6.0): 1980-02-01 diff-z=+14.5 (value 12.3800); 1981-11-01 diff-z=-13.3 (value 14.2200); 2008-12-01 diff-z=-12.0 (value 5.0500)
- **shiller.earnings** (index, 17 obs at |z|>=6.0): 2009-10-01 log-diff-z=+37.8 (value 25.3500); 2008-12-01 log-diff-z=-28.8 (value 14.8800); 2009-11-01 log-diff-z=+21.8 (value 38.1600)
- **fred.BAA** (pct, 16 obs at |z|>=6.0): 1932-08-01 diff-z=-21.6 (value 8.2200); 1932-04-01 diff-z=+13.8 (value 10.4600); 2008-10-01 diff-z=+13.3 (value 8.8800)
- **fred.CPI** (index, 15 obs at |z|>=6.0): 1946-07-01 log-diff-z=+15.3 (value 19.8000); 1917-04-01 log-diff-z=+13.0 (value 12.6000); 1921-02-01 log-diff-z=-9.6 (value 18.4000)
- **fred.TEDRATE** (pct, 12 obs at |z|>=6.0): 2008-10-01 diff-z=+16.6 (value 3.3527); 2008-11-01 diff-z=-15.3 (value 2.0989); 1987-10-01 diff-z=+12.6 (value 2.2619)
- **fred.DGS2** (pct, 10 obs at |z|>=6.0): 1980-05-01 diff-z=-13.5 (value 9.4500); 1981-11-01 diff-z=-11.8 (value 12.8817); 1980-04-01 diff-z=-10.6 (value 12.5019)
- **fred.SAHMREALTIME** (pct, 10 obs at |z|>=6.0): 264 negative value(s), first 1961-12-01 = -0.070 (review: plausible for breakevens/gaps, not for yields); 2020-04-01 diff-z=+35.7 (value 4.0000); 2020-05-01 diff-z=+31.5 (value 7.2700); 2021-04-01 diff-z=-23.1 (value -0.0700)
- **fred.UNRATE** (pct, 10 obs at |z|>=6.0): 2020-04-01 diff-z=+70.1 (value 14.8000); 2020-06-01 diff-z=-14.8 (value 11.0000); 2020-08-01 diff-z=-12.1 (value 8.4000)
- **french.mom** (ret, 8 obs at |z|>=6.0): 1932-08-01 value-z=-18.3 (value -0.5261); 1932-07-01 value-z=-15.9 (value -0.4563); 2009-04-01 value-z=-12.1 (value -0.3436)
- **albourne.hf_rv_credit_ret_m** (ret, 7 obs at |z|>=6.0): 2008-10-01 value-z=-19.7 (value -0.1299); 2008-09-01 value-z=-11.6 (value -0.0746); 2020-03-01 value-z=-9.3 (value -0.0588)
- **shiller.cape** (idx, 7 obs at |z|>=6.0): 1932-08-01 log-diff-z=+13.0 (value 8.8347); 1929-11-01 log-diff-z=-10.1 (value 21.1710); 1932-04-01 log-diff-z=-8.7 (value 7.1922)
- **shiller.price** (index, 7 obs at |z|>=6.0): 1932-08-01 log-diff-z=+12.7 (value 7.5300); 1929-11-01 log-diff-z=-10.0 (value 20.5800); 1932-04-01 log-diff-z=-8.9 (value 6.2800)
- **albourne.hf_insurance_ret_m** (ret, 6 obs at |z|>=6.0): 2017-09-01 value-z=-20.2 (value -0.1032); 2022-09-01 value-z=-18.2 (value -0.0928); 2011-03-01 value-z=-13.1 (value -0.0649)
- **french.hml** (ret, 6 obs at |z|>=6.0): 1932-07-01 value-z=+14.9 (value 0.3552); 1932-08-01 value-z=+14.3 (value 0.3420); 1939-09-01 value-z=+9.1 (value 0.2176)
- **fred.GS10** (pct, 5 obs at |z|>=6.0): 1981-11-01 diff-z=-9.1 (value 13.3900); 1980-02-01 diff-z=+8.4 (value 12.4100); 1982-10-01 diff-z=-7.4 (value 10.9100)
- **fred.T5YIE** (pct, 4 obs at |z|>=6.0): 3 negative value(s), first 2008-10-01 = -0.028 (review: plausible for breakevens/gaps, not for yields); 2008-11-01 diff-z=-10.5 (value -1.3989); 2008-10-01 diff-z=-10.4 (value -0.0277); 2008-12-01 diff-z=+8.6 (value -0.2400)
- **french.mkt_rf** (ret, 4 obs at |z|>=6.0): 1933-04-01 value-z=+9.0 (value 0.3881); 1932-08-01 value-z=+8.6 (value 0.3712); 1932-07-01 value-z=+7.7 (value 0.3361)
- **french.smb** (ret, 4 obs at |z|>=6.0): 1933-05-01 value-z=+14.4 (value 0.3596); 2000-02-01 value-z=+8.5 (value 0.2125); 1939-09-01 value-z=+8.2 (value 0.2057)
- **albourne.hf_cb_arb_ret_m** (ret, 3 obs at |z|>=6.0): 2008-10-01 value-z=-12.8 (value -0.1223); 2008-09-01 value-z=-12.2 (value -0.1164); 2020-03-01 value-z=-10.7 (value -0.1012)
- **albourne.hf_em_fi_ret_m** (ret, 3 obs at |z|>=6.0): 2008-10-01 value-z=-11.2 (value -0.1609); 2020-03-01 value-z=-11.1 (value -0.1598); 2019-08-01 value-z=-6.8 (value -0.0940)
- **albourne.hf_fi_arb_ret_m** (ret, 3 obs at |z|>=6.0): 2008-03-01 value-z=-19.2 (value -0.0942); 2008-10-01 value-z=-8.2 (value -0.0374); 2008-09-01 value-z=-6.2 (value -0.0267)
- **albourne.pm_re_va_ret_q** (ret, 3 obs at |z|>=6.0): 2000-01-01 value-z=-16.4 (value -0.3223); 2006-10-01 value-z=+8.5 (value 0.1980); 2008-10-01 value-z=-6.7 (value -0.1188)
- **fred.DGS10** (pct, 3 obs at |z|>=6.0): 1981-11-01 diff-z=-8.1 (value 13.3928); 1980-02-01 diff-z=+7.5 (value 12.4147); 1982-10-01 diff-z=-6.6 (value 10.9065)
- **jst.usa_ltrate** (pct, 3 obs at |z|>=6.0): 1986-01-01 diff-z=-9.2 (value 7.6825); 1981-01-01 diff-z=+7.8 (value 13.9108); 1980-01-01 diff-z=+6.5 (value 11.4600)
- **albourne.hf_distressed_ret_m** (ret, 2 obs at |z|>=6.0): 2020-03-01 value-z=-12.7 (value -0.1341); 2008-10-01 value-z=-7.3 (value -0.0730)
- **albourne.hf_ms_diversified_ret_m** (ret, 2 obs at |z|>=6.0): 2008-10-01 value-z=-11.6 (value -0.0905); 2008-09-01 value-z=-10.5 (value -0.0813)
- **albourne.hf_stat_arb_ret_m** (ret, 2 obs at |z|>=6.0): 2007-08-01 value-z=-9.6 (value -0.0866); 2008-09-01 value-z=-8.0 (value -0.0716)
- **albourne.pm_buyout_ret_q** (ret, 2 obs at |z|>=6.0): 1990-07-01 value-z=+7.6 (value 0.3193); 1991-10-01 value-z=+7.0 (value 0.2957)
- **albourne.pm_growth_ret_q** (ret, 2 obs at |z|>=6.0): 1999-10-01 value-z=+17.7 (value 0.5381); 2000-01-01 value-z=+7.4 (value 0.2438)
- **albourne.pm_vc_ret_q** (ret, 2 obs at |z|>=6.0): 1999-10-01 value-z=+10.3 (value 0.5121); 1997-10-01 value-z=+7.6 (value 0.3874)
- **fred.GDPC1** (lvl, 2 obs at |z|>=6.0): 2020-04-01 log-diff-z=-13.3 (value 19077.9920); 2020-07-01 log-diff-z=+10.0 (value 20558.8790)
- **fred.T10YIE** (pct, 2 obs at |z|>=6.0): 2008-10-01 diff-z=-7.9 (value 1.0618); 2020-03-01 diff-z=-6.4 (value 0.9868)
- **jst.usa_tloans** (lvl, 2 obs at |z|>=6.0): 1932-01-01 log-diff-z=-6.4 (value 34.4780); 1933-01-01 log-diff-z=-6.4 (value 27.8960)
- **albourne.hf_asia_ls_ret_m** (ret, 1 obs at |z|>=6.0): 2026-04-01 value-z=+6.6 (value 0.1511)
- **albourne.hf_em_ls_ret_m** (ret, 1 obs at |z|>=6.0): 2020-03-01 value-z=-6.5 (value -0.0895)
- **albourne.hf_quant_emn_ret_m** (ret, 1 obs at |z|>=6.0): 2008-09-01 value-z=-6.2 (value -0.0623)
- **albourne.hf_risk_arb_ret_m** (ret, 1 obs at |z|>=6.0): 2020-03-01 value-z=-9.2 (value -0.0632)
- **albourne.hf_structured_credit_ret_m** (ret, 1 obs at |z|>=6.0): 2020-03-01 value-z=-24.5 (value -0.2144)
- **albourne.hf_us_ls_ret_m** (ret, 1 obs at |z|>=6.0): 2008-09-01 value-z=-6.5 (value -0.1094)
- **albourne.pm_distressed_ret_q** (ret, 1 obs at |z|>=6.0): 2008-10-01 value-z=-7.1 (value -0.1728)
- **albourne.pm_dl_ret_q** (ret, 1 obs at |z|>=6.0): 2012-10-01 value-z=-11.1 (value -0.1921)
- **albourne.pm_mezz_ret_q** (ret, 1 obs at |z|>=6.0): 2008-10-01 value-z=-7.9 (value -0.1377)
- **bis.credit_gap_us** (gap, 1 obs at |z|>=6.0): 2020-04-01 diff-z=+7.1 (value 2.8827)
- **jst.usa_gdp** (lvl, 1 obs at |z|>=6.0): 1932-01-01 log-diff-z=-7.8 (value 59.5220)
- **jst.usa_housing_tr** (ret, 1 obs at |z|>=6.0): 1908-01-01 value-z=+7.1 (value 0.4719)
- **jst.usa_stir** (pct, 1 obs at |z|>=6.0): 1874-01-01 diff-z=-8.4 (value 3.4300)
- **treasury.hqm_curve** (pct, 1 obs at |z|>=6.0): 2008-10-01 diff-z=+7.9 (value 8.8500)

## Cross-series sanity
- Baa-Aaa spread negative in 0/1291 months - OK
- DGS10 vs GS10 max abs divergence 0.005pp at 1978-11-01 - OK (<0.25pp)
- CPI monthly drops >2%: 7 (worst -3.16% at 1921-02-01)

## Registered, never fetched
- albourne.cf_A_lifecycle
- albourne.cf_B_calendar_rates
- albourne.cf_C_age_calendar
- albourne.cf_D_vintage
- albourne.cf_E_episodes
- cliffwater.cdli_ret_q
- nareit.all_equity_tr
- ncreif.npi_ret_q
- ncreif.odce_ret_q

## Per-series inventory

| series | units | n | span | gaps | stale/SLA | outliers |
|---|---|---|---|---|---|---|
| albourne.hf_activist_ret_m | ret | 267 | 2004-04..2026-06 | 0 | 68/75 | 0 |
| albourne.hf_asia_ls_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 1 |
| albourne.hf_cb_arb_ret_m | ret | 292 | 2002-03..2026-06 | 0 | 68/75 | 3 |
| albourne.hf_cta_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 0 |
| albourne.hf_distressed_ret_m | ret | 293 | 2002-01..2026-05 | 0 | 99/75 | 2 |
| albourne.hf_em_fi_ret_m | ret | 293 | 2002-01..2026-05 | 0 | 99/75 | 3 |
| albourne.hf_em_ls_ret_m | ret | 284 | 2002-11..2026-06 | 0 | 68/75 | 1 |
| albourne.hf_europe_ls_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 0 |
| albourne.hf_fi_arb_ret_m | ret | 273 | 2003-10..2026-06 | 0 | 68/75 | 3 |
| albourne.hf_fund_emn_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 0 |
| albourne.hf_gaa_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 0 |
| albourne.hf_global_macro_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 0 |
| albourne.hf_insurance_ret_m | ret | 239 | 2006-08..2026-06 | 0 | 68/75 | 6 |
| albourne.hf_japan_ls_ret_m | ret | 293 | 2002-01..2026-05 | 0 | 99/75 | 0 |
| albourne.hf_ms_diversified_ret_m | ret | 293 | 2002-02..2026-06 | 0 | 68/75 | 2 |
| albourne.hf_quant_emn_ret_m | ret | 292 | 2002-03..2026-06 | 0 | 68/75 | 1 |
| albourne.hf_risk_arb_ret_m | ret | 216 | 2008-06..2026-05 | 0 | 99/75 | 1 |
| albourne.hf_rv_credit_ret_m | ret | 291 | 2002-04..2026-06 | 0 | 68/75 | 7 |
| albourne.hf_stat_arb_ret_m | ret | 252 | 2005-06..2026-05 | 0 | 99/75 | 2 |
| albourne.hf_structured_credit_ret_m | ret | 278 | 2003-04..2026-05 | 0 | 99/75 | 1 |
| albourne.hf_us_ls_ret_m | ret | 294 | 2002-01..2026-06 | 0 | 68/75 | 1 |
| albourne.pm_buyout_ret_q | ret | 146 | 1989-10..2026-01 | 0 | 219/240 | 2 |
| albourne.pm_distressed_ret_q | ret | 108 | 1999-04..2026-01 | 0 | 219/240 | 1 |
| albourne.pm_dl_ret_q | ret | 60 | 2011-04..2026-01 | 0 | 219/240 | 1 |
| albourne.pm_growth_ret_q | ret | 115 | 1997-07..2026-01 | 0 | 219/240 | 2 |
| albourne.pm_infra_ret_q | ret | 81 | 2006-01..2026-01 | 0 | 219/240 | 0 |
| albourne.pm_mezz_ret_q | ret | 123 | 1995-07..2026-01 | 0 | 219/240 | 1 |
| albourne.pm_re_va_ret_q | ret | 106 | 1999-10..2026-01 | 0 | 219/240 | 3 |
| albourne.pm_secondaries_ret_q | ret | 110 | 1998-10..2026-01 | 0 | 219/240 | 0 |
| albourne.pm_vc_ret_q | ret | 141 | 1991-01..2026-01 | 0 | 219/240 | 2 |
| bis.credit_gap_us | gap | 273 | 1957-10..2025-10 | 0 | 311/280 | 1 |
| fred.AAA | pct | 1291 | 1919-01..2026-07 | 0 | 38/35 | 28 |
| fred.BAA | pct | 1291 | 1919-01..2026-07 | 0 | 38/35 | 16 |
| fred.CPI | index | 1362 | 1913-01..2026-06 | 0 | 68/40 | 15 |
| fred.CPI_CORE | index | 834 | 1957-01..2026-06 | 0 | 68/40 | 0 |
| fred.DGS10 | pct | 776 | 1962-01..2026-08 | 0 | 7/7 | 3 |
| fred.DGS2 | pct | 603 | 1976-06..2026-08 | 0 | 7/7 | 10 |
| fred.DTWEXBGS | index | 247 | 2006-01..2026-07 | 0 | 38/7 | 0 |
| fred.DTWEXM | index | 564 | 1973-01..2019-12 | 0 | 2442/99999 | 0 |
| fred.FEDFUNDS | pct | 865 | 1954-07..2026-07 | 0 | 38/40 | 35 |
| fred.GDPC1 | lvl | 318 | 1947-01..2026-04 | 0 | 129/130 | 2 |
| fred.GS10 | pct | 880 | 1953-04..2026-07 | 0 | 38/35 | 5 |
| fred.HY_OAS | pct | 37 | 2023-08..2026-08 | 0 | 7/7 | 0 |
| fred.INDPRO | idx | 1290 | 1919-01..2026-06 | 0 | 68/40 | 40 |
| fred.SAHMREALTIME | pct | 800 | 1959-12..2026-07 | 0 | 38/40 | 10 |
| fred.T10YIE | pct | 284 | 2003-01..2026-08 | 0 | 7/7 | 2 |
| fred.T5YIE | pct | 284 | 2003-01..2026-08 | 0 | 7/7 | 4 |
| fred.TB3MS | pct | 1111 | 1934-01..2026-07 | 0 | 38/35 | 60 |
| fred.TEDRATE | pct | 433 | 1986-01..2022-01 | 0 | 1680/9999 | 12 |
| fred.UNRATE | pct | 943 | 1948-01..2026-07 | 0 | 38/40 | 10 |
| fred.USREC | 0/1 | 2060 | 1854-12..2026-07 | 0 | 38/40 | 0 |
| fred.VIX | idx | 440 | 1990-01..2026-08 | 0 | 7/7 | 0 |
| french.hml | ret | 1200 | 1926-07..2026-06 | 0 | 68/90 | 6 |
| french.mkt_rf | ret | 1200 | 1926-07..2026-06 | 0 | 68/90 | 4 |
| french.mom | ret | 1194 | 1927-01..2026-06 | 0 | 68/90 | 8 |
| french.rf | ret | 1200 | 1926-07..2026-06 | 0 | 68/90 | 0 |
| french.smb | ret | 1200 | 1926-07..2026-06 | 0 | 68/90 | 4 |
| jst.usa_cpi | index | 151 | 1870-01..2020-01 | 0 | 2411/400 | 0 |
| jst.usa_crisis | 0/1 | 151 | 1870-01..2020-01 | 0 | 2411/400 | 0 |
| jst.usa_eq_tr | ret | 149 | 1872-01..2020-01 | 0 | 2411/400 | 0 |
| jst.usa_gdp | lvl | 151 | 1870-01..2020-01 | 0 | 2411/400 | 1 |
| jst.usa_housing_tr | ret | 130 | 1891-01..2020-01 | 0 | 2411/400 | 1 |
| jst.usa_ltrate | pct | 151 | 1870-01..2020-01 | 0 | 2411/400 | 3 |
| jst.usa_stir | pct | 151 | 1870-01..2020-01 | 0 | 2411/400 | 1 |
| jst.usa_tloans | lvl | 141 | 1880-01..2020-01 | 0 | 2411/400 | 2 |
| shiller.cape | idx | 1725 | 1881-01..2024-09 | 0 | 706/60 | 7 |
| shiller.dividend | index | 1842 | 1871-01..2024-06 | 0 | 798/60 | 31 |
| shiller.earnings | index | 1842 | 1871-01..2024-06 | 0 | 798/60 | 17 |
| shiller.price | index | 1845 | 1871-01..2024-09 | 0 | 706/60 | 7 |
| treasury.hqm_curve | pct | 511 | 1984-01..2026-07 | 0 | 38/45 | 1 |