# WP-DATA-HQMEXT — the three owner rulings (2026-08-09)

*Companion to `docs/superpowers/specs/2026-08-09-fsext-scoping.md` and the
VOLEXT decisions doc; same read → plan → owner Q&A → build pattern. Owner:
"go with your recommendations on all three and start the work."*

## H1 — Identity ruling: ACCEPTED

Moody's Aaa (seasoned, ~20y+ maturity, Aaa-only, observed monthly from
1919-01) is accepted as the recreation donor for the 10y HQM corporate spot
rate (spot, exactly-ten-year, A/AA/AAA blend, 1984-01+), under the D6/F1
recreation-vs-modelling doctrine. The mismatch is disclosed and measured on
the ~500-month overlap, not assumed away. Note the factor's name oversells
it: `hqm_curve` consumes ONE series (`HQMCB10YR`), so this is a single-yield
extension, not a term-structure reconstruction.

## H2 — Fit form: simple level regression, slope variant as DIAGNOSTIC

The registered construction is `HQM10 = a + b*Aaa` on the 1984+ overlap. The
alternative with a term-slope regressor (`+ c*(Aaa - GS10)`) is computed and
reported by `slope_diagnostic` — extrapolating both constructions over the
pre-HQM era and reporting where they diverge — as the owner's revisit
trigger, never a silent model choice. MEASURED OUTCOME (2026-08-09,
`docs/data/HQMEXT-REPORT.md`): slope coefficient +0.05, overlap RMSE
improvement 0.0005 pct, max pre-1984 divergence 0.081 pct at 1959-09 — the
Volcker-era worry did not materialize; the trigger is quiet.

## H3 — Depth: the donor's 1919-01 start

The extension runs to Aaa's first observation. Pre-1934 months are
panel-irrelevant until other factors reach there (funding_spread's F3 floor
is 1934-01) and are built anyway because they cost nothing and the climate
layer may want them.

## Sealed-surface posture (unchanged from VOLEXT/FSEXT)

`factors.yaml`, `splice.py` and `derive.py` are lock-hashed; the module
`ah.data.hqm_extend` consumes the splice framework read-only, nothing sealed
learns rule `PROXY-HQM10-AAA-V1` (tested), and nothing consumes the output
until the owner ratifies the span amendment. With VOLEXT + FSEXT + HQMEXT
verified, the span chain's next binding factor is `ust_2y` (GS2, 1976-06),
then `fx_usd` (1973-01).
