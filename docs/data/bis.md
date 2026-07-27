# BIS — Credit-to-GDP gap

- **URL:** `https://www.bis.org/statistics/full_webstats_credit_gap_dataflow_csv_row.zip`.
- **License:** FREE (BIS terms; attribution).
- **Coverage:** quarterly credit-to-GDP gap; US series selected. History from 1961Q1.
- **Quirks:** the bulk file is **wide** (a column per economy); the pipeline selects the US series and persists the reduced long `(date, value)` shape the connector parses. Pre-1961 credit-gap history is extended from JST `tloans/gdp` in `derive.py` (documented proxy).


> **Live status (verified):** downloads from the BIS Data Portal `https://data.bis.org/static/bulk/WS_CREDIT_GAP_csv_flat.zip`; parser selects US, CG_DTYPE=C (Credit-to-GDP gaps), quarterly.