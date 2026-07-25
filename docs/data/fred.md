# FRED (Federal Reserve Economic Data)

- **URL:** `https://api.stlouisfed.org/fred/series/observations?series_id=<CODE>&api_key=$FRED_API_KEY&file_type=json`
- **License:** FREE. Most FRED series are public; some are subject to the source provider's terms (e.g. ICE BofA OAS). Redistribution of copyrighted source series is restricted — catalogue with `license_tier: FREE`, but do not re-host raw third-party series.
- **Auth:** `FRED_API_KEY` from env (never in code/fixtures).
- **Methodology:** per-series on the FRED page; recorded in the catalog `methodology` link at intake.
- **Quirks:** missing observations are the string `"."` (parsed to NaN). Daily series aggregate to monthly by **mean** (rates/spreads) except **VIX** which uses the **month-end** value. Series are period-labelled at month start.
- **Retired:** `fred.TEDRATE` discontinued 2022-01 — retained deliberately (enforce=false); funding-stress after 2021-12 uses a documented SOFR-based replacement in `derive.py`, not a fake continuation.
- **URL verification:** endpoints are verified at build time when network is available; this offline build uses recorded/synthetic fixtures.
