# Inflation Pass-Through (Real-Asset Sleeves) + Credit Loss Term — Design Note

Pre-declaration for amendment `AM-2026-08-15-001`, entered in
`governance/amendment-log.yaml` in the same commit as this note. The functional
forms, lag structures, anchors and adoption rules below are fixed here, not
tuned after seeing numbers: no sleeve coefficient has been estimated against
them.

**One exception, stated rather than buried.** The CPI rent-vs-less-shelter
cross-check quoted in §3.2 (`artifacts/c1/passthrough-rent-crosscheck.json`)
was run *before* this note landed in history, so "committed before any
estimation runs" is true of the estimator and of every adopted coefficient, but
not of that one fit. It is evidence for the **lag shape only**: it fits a public
CPI-on-CPI relation, touches no sleeve, no composite and no catalog series, and
is never a source for any `b_infl` level. Disclosed here rather than left to a
reader to notice from the artifact's date.

Two changes, one principle: **measured components stay linear; nonlinearity
and slow dynamics enter as authored structural terms with disclosed
provenance.** Both terms are labelled `chosen` (or `measured-external` where
NPI supplies a fit), never `measured` against the Albourne composites — §2
states why the composites cannot identify either.

---

## 1. Scope

| Change | Sleeves touched | Layer |
|---|---|---|
| C1 — inflation pass-through | `pm_infra`, `pm_re_value_add`; form pre-declared for `re_core` / `infra_core` (unparameterized Tier B, evergreen) | sleeve mapping artifact |
| C2 — credit loss term | `pm_direct_lending`, `pm_mezzanine`, `pm_distressed` | sleeve mapping artifact (promoted from toy-engine ER-3/ER-4 mechanism) |

Out of scope, explicitly: HF sleeves (verbatim); the smoothing kernel; any
change to `decision_alpha_version`; hy_spread (sealed missing-factor on this
vintage — C2 is keyed to `ig_spread` for exactly that reason); caps/floors on
escalators (documented asymmetry, deferred); Finding A of the 2026-08-12 note
(reported-marks sampling defect, still deferred).

## 2. Why neither term can be measured on the composites

**C1.** Train+validation seals at 2021-01-01. The only inflation episode in
the composites' lifetimes that would identify a pass-through coefficient
(2021–23) is in the holdout. Over 1990–2020 trailing inflation is nearly
constant; `pm_infra` has 60 quarters. A coefficient fitted there is noise
carrying a `measured` label — worse than an honest `chosen`.

**C2.** Loss asymmetry is a tail property; the composites contain two spread
episodes inside train+val. No power. The term is structural or it is nothing.

## 3. C1 — inflation pass-through

### 3.1 Form (declared)

A new derived regressor and one loading per sleeve:

```
cpi_trail_t  =  annualised realised CPI inflation over the trailing K quarters
r_sleeve    +=  b_infl · ( cpi_trail_t − c_anchor )
```

- **K = 8** (two years). Rationale: escalator and lease-reset cycles pass CPI
  through over 1–3 years; 8 is the midpoint and is fixed here. K = 4 and
  K = 12 will be **recorded as sensitivities in the report, never adopted**.
- **c_anchor = mean of `cpi_trail` over train+validation**, computed once and
  written into the artifact. Demeaning at the anchor means adopting C1 leaves
  each sleeve's unconditional mean unchanged — the amendment adds
  state-dependence, not return. Any drift of the mean would be tuning.
- Runtime applies `b_infl` to the **true generated CPI path** (already a
  sealed factor), same convention as every other loading. The appraisal lag
  stays in the reporting kernel where it belongs; K is an economic
  pass-through lag, not a smoothing artefact, and the two must not be
  conflated in the write-up.

### 3.2 Coefficient provenance (declared triangulation, in priority order)

1. **NPI, 1978– (NCREIF query tool; membership per data register P1).**
   Distributed lag on trailing CPI, fitted to **two exports**: *NOI growth*
   (primary — escalation lives in income growth, and NOI is not appraised)
   and *income return* (continuity target; **disclosed caveat**: income
   return is a yield, so its denominator carries the cap-rate channel and can
   contaminate the fit — the NOI-growth fit governs if the two disagree).
   This refinement was made at implementation, before any NCREIF data was
   seen, and is disclosed here rather than silently applied. Label:
   `measured-external`, source and window recorded.
   *Lag-shape evidence already in hand (public, reproducible):* the CPI
   rent-vs-less-shelter pass-through, 1955–2020 quarterly, fitted with the
   committed script — contemporaneous coefficient indistinguishable from
   zero (t=0.5), long-run pass-through **0.64**, cumulative share of long-run
   **47% at K=4, 72% at K=8, 88% at K=12**, diagnostic R² 0.62. This
   corroborates both the K=8 declaration and the §2 claim that a `d_cpi`
   regressor would find nothing; it is evidence for the **lag shape only**,
   never a source for any sleeve's `b_infl` level. Provenance:
   `passthrough-rent-crosscheck.json` (input hash embedded).
2. **Contract share** — pass-through ≈ revenue share with contractual CPI
   linkage. Core infra: documentable from concession/regulatory structure
   (declared prior **0.6**, range 0.4–0.8). Value-add RE: lease-reset
   structure, declared prior **0.3**, range 0.15–0.45. Label: `chosen`,
   document-anchored.
3. **De-levered listed proxies** (utilities, listed infra, REITs) — bound the
   long-run level only. Listed marks price *expected* inflation instantly,
   which is precisely the dynamic private marks lack; the lag shape from
   listed data would be wrong by construction. Cross-check, never source.

**Adoption rule (declared):** `b_infl(pm_infra)` and `b_infl(re_core form)`
are set from (2) unless the NPI fit's implied infra analogue contradicts the
0.4–0.8 range, in which case the disagreement is written up and the owner
rules; `b_infl(pm_re_value_add)` is set from (1) scaled by the value-add
lease-share ratio from (2). No value is adopted that was not producible from
this paragraph.

### 3.3 Acceptance

- **Episode reproduction, 1978–82** (inside train+val): the fitted NPI lag
  shape reproduces the observed income-return climb with the observed delay.
- **Episode check, 2021–24:** **RULED — owner, 2026-08-15 (Ruling A).**
  An external-series comparison of a pre-committed authored coefficient
  against published NPI prints is validation evidence, not holdout access:
  NPI is not a catalog factor under the sealed splits, and the coefficient is
  frozen before the check runs. Rationale recorded: the inflation channel is
  too material to the product to ship unchecked. **Scope of the ruling,
  narrowly:** (i) external series only — never a catalog factor read;
  (ii) the compared value must be committed and hashed before the check;
  (iii) one execution, result recorded verbatim in the report; (iv) the
  result is **never** a calibration input — if the check fails, the failure
  is disclosed and the coefficient is revisited only through a further dated
  amendment whose trigger is the disclosed failure. This ruling is precedent
  for future authored parameters under the same four conditions and no wider.

## 4. C2 — credit loss term

### 4.1 Form (declared)

Promoted from the toy engine's ER-3/ER-4 mechanism, restated for the
production quarterly artifact and keyed to the available factor:

```
loss_q  =  θ_sleeve · max( ig_spread_{t−4} − s̄ , 0 )
r_sleeve  =  alpha_adj + Σ beta_f·F_f − loss_q + ε
```

- **Lag 4 quarters** (the toy engine's 12 months — spreads price the risk
  about a year before losses land). Fixed here.
- **s̄ = median ig_spread over train+validation**, written to the artifact.
- **No crisis dummy.** The WP3.10 §4.2 finding governs: smooth functions of
  fundamentals, no regime override. Clustering severity lives in θ and in the
  spread path's own dynamics, which L3 already makes fat-tailed.
- **θ (chosen), anchored to public loss histories — match rule declared:**
  θ_DL is set so that **mean(loss_q) over train+validation equals the CDLI
  mean annualised net realised-loss rate ÷ 4** (CDLI registration-tier, in
  the data register; input CSV hashed into provenance by
  `fit_credit_loss_theta.py`). Acceptance, not calibration: cumulative
  modelled DL loss over 2008Q1–2010Q4 must land within **±30%** of the CDLI
  cumulative for the same window, or the functional form is written up as
  wrong. Then mezzanine θ = 1.5× DL, distressed θ = 0.5× DL (distressed
  *buys* impaired credit; its downside is mark risk already in beta, not
  origination loss — this asymmetry of treatment is deliberate and stated).
- **Alpha re-basing (declared):** `alpha_adj = alpha_v1.1 + mean(loss_q over
  train+val)`. Unconditional means are preserved; the term redistributes
  return across states. Without this rule, adoption silently cuts PC returns
  and the change is indistinguishable from tuning toward the Sharpe ceiling.

### 4.2 Acceptance

- GFC-shaped spread path produces cumulative DL losses of CDLI 2008–09 order
  (match to the published series, tolerance stated in the report).
- Benign presets: PC decade Sharpe moves **toward** ≤1.0 without the
  credibility-console threshold being touched (the ER-4 discipline — flags
  are never silenced by moving the flag).
- Removing the term and re-adding a crisis dummy adds no significant
  explanatory power on any composite (the §4.2 test, run as a check).

## 5. Governance

- Artifact: `sleeve-mappings-v1.2.yaml`, `mapping_version: map-2026.08.3`.
  v1.1 is never edited; the new estimator script is self-contained (sealed
  judges read alone). HF rows, residual_correlation, cta_rule verbatim.
- New schema fields: `b_infl`, `cpi_trail_k`, `c_anchor`, `theta_loss`,
  `loss_lag_q`, `s_bar`, per-row `provenance` — and, closing the standing gap,
  **`r2_train_val` restored to every PM row** (the estimator holds the
  residuals; the field costs one line).
- `post_hoc: true` — the trigger is a design review finding (missing slow
  inflation channel; linear credit payoff), disclosed as such. The
  pre-declared procedure here is what keeps it from being tuning.
- Any preset whose institution holds the touched sleeves moves to a new
  `world_id` block on adoption (the ER-3 precedent: scores under two return
  models never share a board).
- DN-5 §4.1's "loadings are claims about the mean" note gains a sentence:
  two authored structural terms now make the conditional mean nonlinear in
  `ig_spread` and slow in `cpi`; both are disclosed, neither is estimated
  from the panel.
- Register entries: **§3.3 Ruling A — ratified, owner, 2026-08-15** (enter as
  a dated SM/D-series item; it is precedent-setting and must not live only in
  this note). Still ⚑: C1 adoption; C2 adoption; the re_core/infra_core forms
  parked until those sleeves are parameterized (links to the Albourne
  coefficient request §2a).

## 6. Order of work

1. Enter Ruling A in the decision register (dated, owner-attributed).
2. NPI income-return fetch + distributed-lag fit (external, no catalog touch).
3. Adopt coefficients per §3.2's rule; **commit and hash the adopted values
   and the exact 2021–24 comparison spec (series, window, tolerance) before
   the check runs** — Ruling A condition (ii).
4. Estimator `v1_2` written test-first against this note; C1 + C2 + R² field.
5. Run the 2021–24 check once; record the result verbatim in the report.
6. Report: adopted values with provenance labels, sensitivities (K=4/12,
   θ×[0.5,2]) recorded-not-adopted, acceptance results including 1978–82
   and the 2021–24 check.
7. Adoption is a named owner release event, not a side effect of the report
   existing — the Campaign R1 rule.

---

*Not investment advice. Simulation calibration; parameters generic.*
