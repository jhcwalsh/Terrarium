# US Treasury — HQM corporate spot-rate curve

- **URL:** `https://home.treasury.gov/system/files/226/hqm_84_present.xlsx`.
- **License:** FREE (US government work).
- **Coverage:** monthly high-quality market (HQM) corporate spot rates by maturity, 1984-.
- **Quirks:** a maturity x month grid. The **full curve is retained in the raw artifact**; the catalogued `treasury.hqm_curve` series returns the representative **10-year** HQM spot rate. Other maturities are reconstructed from raw by the derive layer (pension discount curves).


> **Live status (verified):** `treasury.hqm_curve` is now sourced from FRED `HQMCB10YR` (the 10y HQM corporate spot rate; full curve = `HQMCB<maturity>`), avoiding the Treasury `.xls`. This connector is retained for the full-curve xls if ever needed.