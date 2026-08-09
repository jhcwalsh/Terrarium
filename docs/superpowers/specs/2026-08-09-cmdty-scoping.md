# WP-DATA-CMDTY — scoping: close the sealed `commodities` factor with AQR CFTLR

*Scoping draft, 2026-08-09, fifth of the extension family. Owner questions
C1-C3 at the end gate the build. Context: `commodities` is a sealed
`missing_factor` (factors.yaml `kind: unavailable`; RFR-8), and the
LICENSE-REGISTRY's gap section exists to explain why no free source closed
it: the registered free series (`fred.CMDTY_GLOBAL`, `fred.CMDTY_PPI`) are
PRICE indices, not total-return.*

## The dataset the owner supplied

`Commodities for the Long Run Index Level Data Monthly.xlsx` — the AQR data
library set behind Levine, Ooi, Richardson (©2018; the FAJ paper of the same
name). Monthly, **1877-02 → present** (~1,780 months). Columns: excess /
excess-spot / carry returns of an **equal-weight commodity futures
portfolio**; the same for a long/short backwardation-tilted portfolio; an
aggregate backwardation measure; two categorical state columns
(backwardation/contango, inflation up/down). Plus Definition / Data Sources /
Disclosures sheets.

**Why it closes the gap in kind:** it is the excess return of an INVESTABLE
futures portfolio — not a spot price index. Total return = excess + T-bill,
and the risk-free leg is already registered (`french.rf` 1926-07+,
`fred.TB3MS` 1934+). The sealed factor spec's `numeraire: total_return` is
one addition away.

## Custody (already done, 2026-08-09)

The workbook was dropped in `docs/` — one `git add -A` from being pushed to
a public repository against AQR's redistribution terms. It now lives at
`data/aqr/` (gitignored, verified) and is NEVER committed; the intake
connector reads it from there, the Albourne manual-intake pattern.

## The WP shape (family pattern; nothing sealed touched)

1. Manual-intake connector `aqr_cftlr` (`fetch()` refuses network; loader
   takes the workbook path), requirements entries for the consumed columns.
2. New unsealed module (e.g. `ah.data.cmdty_close`): parse + the
   total-return construction (excess + rf, aligned monthly) + overlap
   verification against the registered `fred.CMDTY_*` price indices
   (spot-return column vs price-index returns — the only free cross-check
   that exists).
3. Live/local verification report `docs/data/CMDTY-REPORT.md`: coverage,
   the cross-check correlation, episode readings (1917-20, 1930s deflation,
   1973-74, 2008, 2020-22).
4. LICENSE-REGISTRY: the gap section updated from "no source" to "closed
   for research use under AQR terms; commercial clearance OPEN", plus the
   snapshot-staleness posture (the set updates periodically, Shiller-style).
5. A proposed amendment draft: remove `commodities` from the sealed
   `missing_factors`, register the factor construction, activation as a
   future `block_addition` with its own thresholds. PROPOSE ONLY — the
   ratification is bigger than the extension family's (re-seal + a factor
   no checkpoint has ever seen; it enters FUTURE campaigns only).

## Owner questions (gate the build)

- **C1 — which column is the factor?** Recommended: the equal-weight
  portfolio's excess return + registered risk-free leg → `total_return`.
  The long/short portfolio is a strategy, not the asset class; the spot
  column is exactly what the registry refuses.
- **C2 — licence tier and posture?** Recommended: `REG` (attribution
  required, redistribution prohibited), manual intake, file gitignored,
  registry updated to "closed for research use; commercial clearance an
  open registry item" — the registry is a checklist, not a clearance, and
  the commercial call is the owner's or counsel's.
- **C3 — scope of closing?** Recommended: intake + verified series +
  proposed amendment only; `missing_factors` removal, re-seal, and factor
  activation all deferred to ratification, like the four extensions.
