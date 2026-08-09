# TASK — Backcast `equity_vol` before 1990 (WP-DATA-VOLEXT)

Paste this whole file to Claude Code from the repository root.

---

## Context you need before writing anything

`bootstrap_v1.block_draw_span` is pinned to **1990-01..2020-12** because `equity_vol`
(`fred.VIX`, see `factors.yaml:158`) starts 1990-01. `pre-registration.yaml:4124` states this
explicitly: *"equity_vol (fred.VIX) begins 1990-01, funding_spread (TED) 1986-01 and hqm_curve
… equity_vol binds the span."* The consequence, disclosed in `governance/evidence/G2-EVIDENCE.md`
§3.3, is that `bootstrap-v1` **cannot reach any pre-1990 episode** while the challenger, fitted on
the full span, has seen 1929-33, 1937, 1973-74 and 1987. The G2 promotion had to be re-run on a
restricted window because of it.

**Two facts established before this task, which set its shape:**

1. **`funding_spread` (TEDRATE) also starts 1986-01-02.** Extending `equity_vol` alone moves the
   binding constraint to 1986 and no further. Do not size this work as if it unlocks the 1970s —
   it does not, on its own.
2. **`VXOCLS` on FRED starts 1986-01-02 and is observed, free and licence-clean.** The original
   S&P 100 volatility index. It reaches 1986 with a real implied-vol print, which is exactly where
   TED binds anyway. **Prefer observation to modelling wherever it is available.**

So this task has two stages, and stage 1 must ship before stage 2 is worth doing.

---

## Stage 1 — the observed extension (do this first)

Add `fred.VXOCLS` to the FRED connector and catalog. Splice it onto `fred.VIX` using the existing
`ah.data.splice` framework: `VXOCLS` is the donor, `VIX` the target, `transform="regression"` on
the 1990+ overlap. VXO is ATM S&P 100 implied vol and runs systematically above VIX, so the log-log
regression link is the right transform; verify the overlap fit before accepting it.

Then propose (do not apply) the `block_draw_span` change to 1986-01, and state in the PR
description that `funding_spread` becomes the binding series at that point.

**Stage 1 is a data-layer change with no modelling and should be reviewable in isolation.**

---

## Stage 2 — the model-based backcast below 1986

Build `src/ah/data/vol_backcast.py`. A reference implementation exists and is attached at
`REFERENCE-vix_backcast.py` — **treat it as a specification sketch, not code to vendor**. Rewrite
it to repo conventions: module docstring stating the discipline in the style of
`src/ah/data/splice.py` and `gapfill.py`, `from __future__ import annotations`, frozen dataclasses,
no network at import.

### Specification

Monthly log implied vol on a HAR cascade (Corsi 2009) of trailing realized volatility, plus a
tail-severity term:

```
log VIX_t = a + b1 log RV_t(22) + b2 log RV_t(66) + b3 log RV_t(252) + g log(1 + maxdd_t) + e_t
```

- Realized vol from daily index log returns, close-to-close, annualized, in points. Range-based
  estimators (Parkinson, Garman–Klass) are more efficient but the S&P composite carries
  `high == low == close` before 1962 — the module must **refuse** a range estimator when more than
  2% of rows are degenerate rather than silently returning nonsense.
- `maxdd` is the worst peak-to-trough over the trailing 66 trading days. It carries the jump
  component and the leverage effect.
- **Drop the `downside` semivariance term** that appears in the reference implementation. On the
  real fit it came in at t = −1.28; it is not supported by the data and should not enter a
  registered specification.
- OLS with **Newey–West HAC** standard errors, Bartlett kernel, 12 lags. Overlapping trailing
  windows induce strong residual autocorrelation; plain OLS standard errors are badly understated
  and must not be reported.
- Features sampled at month end from daily data only — **no look-ahead**. There must be a test that
  truncating the daily input does not change any earlier monthly feature value.

### The requirement that is easiest to get wrong

**Return an ensemble, not a point estimate.** A regression's fitted values are smoother than the
truth by construction — the conditional mean discards the residual variance. Splicing a point
backcast would give the pre-1990 era an artificially calm volatility-of-volatility, suppressing
exactly the tail behaviour the extension exists to recover, and biasing every tail metric computed
over the extended span toward complacency.

Resample residuals in **12-month blocks** (preserving their persistence and their tendency to
cluster in stress) and add them in log space. Measured on the reference implementation: the
conditional mean retains 0.874 of true vol-of-vol; the ensemble, 1.034. Provide `n_draws=0` for the
bare mean and document it as diagnostic-only.

### Validation, which decides whether this is usable at all

- Out-of-sample: fit ≤ 2007, test 2008+ (contains the GFC and COVID — the episodes most like the
  pre-1990 tail this exists to reach). Report RMSE in logs, overall bias, and bias in the **top RV
  decile** separately. A model that fits calm markets and misses stress is worse than no extension,
  because it furnishes the bootstrap with a placid 1930s.
- Peak reproduction on both crisis windows, reported as predicted/actual ratio.
- Vol-of-vol ratio for both the conditional mean and the ensemble.
- Interval coverage of the ensemble against realized error.
- Expanding-window walk-forward.
- **The strongest available test, which must be included:** VXO is observed 1986-89 and the model
  is fitted on 1990+ only. Map VXO→VIX-equivalent on the overlap, then score the backcast on
  1986-89 as a true held-out era. The reference implementation achieves correlation 0.949 on log
  levels and predicts October 1987 at 58.4 against a VIX-equivalent of 51.6. Treat those as the
  numbers to reproduce or beat; a material regression against them means the rewrite broke
  something.

---

## Hard constraints

**Governance.** `equity_vol`'s start date, `block_draw_span`, and `level_factors` are sealed in
`pre-registration.yaml`. Any change to them is a dated entry in `governance/amendment-log.yaml`,
written **before** the campaign it affects. Acceptance thresholds for the backcast must be
registered there before the registered fit is run — do **not** carry over the exploratory defaults
in the reference implementation, which were chosen after seeing results. That pattern is the
RFR-77 defect class (`governance/retrofit-register.md`); do not reproduce it in a new place.

**Provenance.** Every backcast row carries `is_proxy=True` and a `rule_id`, and a backcast never
overwrites an observed month — same discipline as `ah.data.splice` and `ah.data.gapfill`. Emit a
JSON provenance artifact under `artifacts/` containing the fit, the HAC standard errors, the full
validation report, and an explicit caveat that backcast months are model output rather than
observation.

**Tests run offline.** `pyproject.toml` configures pytest with `--disable-socket`. All tests use
synthetic fixtures — generate daily prices with clustered volatility and a **persistent (AR(1))**
pricing error, so the HAC test actually exercises the property it claims. No network fetch in any
test.

**Licensed data.** `/data/` is gitignored and holds the vintage store. Fitted artifacts go there;
code and provenance JSON are committed.

**Dependencies.** Do not add `yfinance` to `pyproject.toml` for a data-acquisition path. Follow the
existing connector pattern in `src/ah/data/connectors/` — the loader takes a frame, and acquisition
is a connector's job with its own licence entry in `docs/data/LICENSE-REGISTRY.md`. Flag the daily
index price source as a decision for the owner rather than choosing one silently; it needs a
licence review, unlike the keyless FRED endpoints.

---

## Acceptance criteria

1. Stage 1 shipped and reviewable independently of stage 2.
2. `pytest tests/test_vol_backcast.py` passes, offline, including: no-look-ahead, HAC exceeds naive
   OLS, backcast never overwrites observed, ensemble restores vol-of-vol while the mean does not,
   seed determinism, refusal on short overlap, refusal on degenerate OHLC, and a deliberately
   broken mapping that `validate()` must reject.
3. The 1986-89 VXO held-out check runs from a committed script and reports correlation and the
   October 1987 comparison.
4. Provenance JSON written; no sealed value silently changed; amendment drafted for owner
   ratification rather than applied.
5. `ruff` and `mypy` clean to repo settings.

## Explicitly out of scope

- Applying any amendment or changing `block_draw_span` in `pre-registration.yaml`. **Propose only.**
- Retraining L3, regenerating any campaign, or re-running any battery.
- Extending `funding_spread` or `hqm_curve`. Separate work packages; note in the PR that
  `funding_spread` becomes binding at 1986 and that reaching the 1970s needs both.
- Any claim that the extended span makes `bootstrap-v1` a fair comparator over pre-1990 episodes.
  It resamples model output there, which is a **weaker** benchmark position than the current
  restricted-window disclosure, not a stronger one. Say so in the PR.

## Start by

Reading `src/ah/data/splice.py`, `src/ah/data/gapfill.py`, `src/ah/data/connectors/fred.py`,
`factors.yaml` (the `equity_vol` block at line 158), and `pre-registration.yaml` around lines 4120-4135
and 4438-4451. Then propose the file layout and the amendment text before writing the estimator.
