# WP-DATA-VOLEXT — the five owner decisions (2026-08-09)

*Companion to `Instructions/TASK-vol-backcast-claude-code.md`, which is the
authoritative specification. This file records the decisions taken in owner
Q&A before Stage 1 started, so Stage 2 inherits them without re-litigating.*

## D1 — Daily price source: French daily Mkt-RF

Realized-vol features are computed from the **Ken French daily market factor**
(F-F Research Data Factors, daily, from 1926-07-01), through the existing
`french` connector family. Grounds: the generator's `equity_mkt` factor *is*
`french.mkt_rf`, so the backcast vol is the implied-vol counterpart of the
same return series the bootstrap resamples — the 1931 vol spike lands in the
same months as the 1931 return crash; zero new licence exposure (FREE tier,
already-registered source); the VIX-vs-whole-market identity mismatch is
absorbed by the 1990+ overlap fit and disclosed in the provenance artifact.
Consequences accepted: returns-only, so the range-estimator branch is
permanently dormant (close-to-close is what the spec mandates pre-1962
anyway), and `maxdd` is computed from cumulated returns.

Rejected: Stooq (licence ambiguous), Yahoo (ToS-hostile), FRED SP500 (10y
only), licensed feeds (unjustified cost for this stage), Schwert vendoring
(only needed for pre-1926 reach, which nothing here targets).

## D2 — Ensemble storage: design A (point series + generative artifact)

The vintage store gets ONE extended series in three segments — observed VIX
(1990+), VXO splice (1986–90, `is_proxy`, rule `PROXY-EQUITY-VOL-VXO-V1`),
backcast median (pre-1986, `is_proxy`, rule `PROXY-EQUITY-VOL-HAR-V1`). The
committed provenance JSON carries the fit, HAC covariance, residual pool and
seed protocol; ensemble paths are regenerated bit-identically from
`(fit, seed)` via a `paths()` API. The stored median is diagnostic/display
only — every tail-bearing consumer must draw from the ensemble; the series
notes and the provenance caveat both say so. Rejected: materialized ensemble
members (store-semantics violation, vintage blowup), ensemble-only (splits
the series across storage systems at 1986), store schema extension (2R froze
the contract).

## D3 — Amendments: two separate instruments, drafted in `governance/proposed/`

1. **Backcast acceptance thresholds** — additive registration for a new
   object; queued for ratification at the START of Stage 2, before the
   registered fit runs (the RFR-77 discipline).
2. **`block_draw_span` → 1986-01** — a sealed-value change with a re-seal
   behind it; on no critical path; ratified whenever the owner's evidence
   standard is met, possibly never. Stage 1 and 2 both complete without it.

Drafts live as `governance/proposed/PROPOSED-AM-*.md` files carrying the
exact entry text for `ah.eval.prereg.append_amendment`. Nothing provisional
ever enters `amendment-log.yaml` itself.

## D4 — Registered thresholds (owner-ratified values, fixed before any fit)

| check | threshold |
|---|---|
| 1986–89 VXO held-out, log-level correlation | ≥ 0.90 |
| Oct-1987 predicted/actual peak ratio | in [0.75, 1.35] |
| top-RV-decile OOS bias, log | abs ≤ 0.20 |
| ensemble vol-of-vol ratio | ≥ 0.85 |
| 80% interval coverage | within ±0.10 |

Derived from the task file's reproduce-or-beat targets (corr 0.949; 58.4 vs
51.6), not from any fit run in this repo. The reference implementation's
`DEFAULT_THRESHOLDS` are explicitly NOT carried over.

## D5 — Type checker

Acceptance criterion 5's "mypy" is read as **pyright** (the repo's checker,
basic mode with the `src/ah/data` stub-noise carve-out). mypy is not added.

## D6 — Admission ruling (owner, 2026-08-09, after the stage-2 PASS)

**The backcast equity_vol IS admissible as span-bearing data.** The owner's
distinction: *recreating* a series from observed contemporaneous inputs
(realized vol computed from the era's own daily returns, mapped through a
fitted, held-out-audited link, with a disclosed residual ensemble) is not
*modelling* in the sense the benchmark must exclude — the platform's own
generator never touches it. This supersedes the argued-against posture the
span draft originally carried; the counterargument (a benchmark partly built
on our fitted mapping is a weaker null in pre-1986 episodes) stays recorded
here and in the draft's history rather than being erased. Conditions carried
forward unchanged: every model month stays `is_proxy` under
`PROXY-EQUITY-VOL-HAR-V1`, any statistic over the extended span discloses the
proxy share, tail-bearing consumers draw from the ensemble (never the stored
median), and admission takes effect only through a ratified amendment.
Practical consequence unchanged: `funding_spread` (1986-01) still binds the
joint panel; admission moves nothing until it and its successors extend.

## Sealed-surface posture (established during planning, binds both stages)

`src/ah/data/splice.py` (including the `PROXY_RULES` registry) and
`src/ah/data/derive.py` are hashed by `pre-registration.lock`. Stage 1
therefore lives in a NEW module `src/ah/data/vol_extend.py` that consumes the
splice framework read-only and implements the log-log link itself (the sealed
`"regression"` transform is level-space). Nothing sealed is edited in either
stage; moving the rule into the canonical registry and wiring `derive.py`
happens once, under the span amendment, if ratified.
