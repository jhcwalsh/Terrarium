# Jordà-Schularick-Taylor Macrohistory Database

- **URL:** `https://www.macrohistory.net/app/download/<id>/JSTdatasetR<n>.dta` (current release).
- **License:** FREE (cite the JST papers).
- **Coverage:** annual macro-financial panel, 1870-. **All countries are kept in the raw artifact**; `parse` filters to **USA** (start country) and extracts one variable (ltrate, stir, cpi, gdp, tloans, eq_tr, housing_tr, crisis). Year is labelled at Jan 1.
- **Quirks:** Stata `.dta`; country column is `iso` (fallback `country`). Variable availability differs by release — the parser asserts the requested variable exists.


> **Live status (verified):** downloads and parses via `https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.dta` (R6, 18 economies 1870-); parser filters USA. 151 USA rows.