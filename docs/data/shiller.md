# Robert Shiller — ie_data

- **URL:** `https://img1.wsimg.com/blobby/go/ie_data.xls` (Shiller's online data).
- **License:** FREE (academic).
- **Methodology:** CAPE = real price / 10-year trailing average real earnings.
- **Quirks:** the workbook has **merged headers and footnote rows**. The parser locates the header row by content (a row containing `Date` and `P`) rather than by position, and asserts the target column (`P`/`D`/`E`/`CAPE`) is present (guards column drift). The `Date` column is a **fractional year** (1871.01 = Jan 1871; .10 = Oct). Real file is `.xls`; the parser reads via pandas (`.xls` needs `xlrd` at fetch time, `.xlsx` uses openpyxl).


> **Live status (verified):** fetched from the shillerdata.com wsimg blob with a browser User-Agent; needs `xlrd` for the `.xls`; the parser locates the `Data` sheet and the `Date/P/D/E/CPI/CAPE` header by content. NOTE: the current blob serves a 2024-09 snapshot, so QC flags staleness — replace the URL with the latest download link for current data.