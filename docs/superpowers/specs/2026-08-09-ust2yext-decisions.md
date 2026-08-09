# WP-DATA-UST2YEXT — the three owner rulings (2026-08-09)

*Fourth of the extension family (VOLEXT, FSEXT, HQMEXT, this); same
read → plan → owner Q&A → build pattern. Owner: "go with your
recommendations on all three and start the work."*

## U1 — Identity ruling: ACCEPTED

`ust_2y` (`fred.DGS2`, 1976-06+) is recreated below its start from its
observed curve neighbours `fred.GS1` and `fred.GS3` (both 1953-04+, live).
Interpolation between observed points either side of the target maturity on
the same curve — the mildest recreation in the family; the D6 doctrine
applies a fortiori.

## U2 — Fit form: two-donor regression

`ust2y = a + b1*GS1 + b2*GS3` on the ~600-month overlap — fitted
interpolation weights, nesting the plain average. MEASURED OUTCOME
(2026-08-09, `docs/data/UST2YEXT-REPORT.md`): corr 0.9999, RMSE 0.055 pct,
weights 0.367/0.646.

## U3 — Depth: the donors' 1953-04 start

278 proxy months, 1953-04..1976-05. Past the fx wall (1973-01) and past
ust_10y's 1962-01, so this factor never binds the panel again under any
ratification target now in view.

## Sealed-surface posture (unchanged from the family)

Nothing sealed learns rule `PROXY-UST2Y-GS1GS3-V1` (tested); nothing
consumes the output until the owner ratifies the span amendment. With all
four extensions verified, the binding factor is **`fx_usd` (1973-01)** — the
Bretton Woods wall, which is a design question (a par-rate index is nearly
constant with step revaluations), not a data fetch.
