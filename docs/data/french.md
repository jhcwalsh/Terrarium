# Ken French Data Library

- **URL:** `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip` (momentum: `F-F_Momentum_Factor_CSV.zip`).
- **License:** FREE (academic; attribution expected).
- **Methodology:** Fama-French factor construction; see the library documentation page.
- **Quirks:** the CSV has a text preamble, then a **monthly** block of `YYYYMM` rows, then a **trailing annual block** with the *same* header. The parser matches the 6-digit monthly key and stops at the first non-monthly row after the monthly block — it never indexes by position. Values are in **percent**.


> **Live status (verified):** downloads and parses; values converted percent->decimal on parse.