# PROPOSED amendment — registered acceptance thresholds for the equity_vol backcast

**Status: DRAFT — awaiting owner ratification. Nothing in this file is in
force.** This file is a proposal in the sense of
`docs/superpowers/specs/2026-08-09-volext-decisions.md` D3: the authority is
`governance/amendment-log.yaml`, appended only by
`ah.eval.prereg.append_amendment`, and this draft never enters it until the
owner says so.

**Ratify before:** the Stage-2 registered fit of
`src/ah/data/vol_backcast.py` runs on real data. Registering the grading
rubric after seeing the fit is the RFR-77 defect class
(`governance/retrofit-register.md`); this draft exists so that cannot happen
here.

**What ratification triggers:** one appended entry (below). No sealed value
changes, no re-seal — this registers criteria for a NEW object.

## The entry, ready for `append_amendment`

```yaml
amendment_id: AM-<date>-<seq>          # assigned at ratification
type: protocol_change
date: <ratification date>
post_hoc: false
rationale: >-
  Registers the acceptance thresholds for the equity_vol model-based
  backcast (WP-DATA-VOLEXT stage 2, src/ah/data/vol_backcast.py) BEFORE its
  registered fit is run. Values were fixed 2026-08-09 in owner Q&A, derived
  from the task file's reproduce-or-beat targets (VXO 1986-89 correlation
  0.949; Oct-1987 58.4 predicted vs 51.6 VIX-equivalent), not from any fit
  run in this repository. The reference implementation's exploratory
  DEFAULT_THRESHOLDS are explicitly not carried over.
payload:
  registered_object: equity_vol_backcast
  spec_module: src/ah/data/vol_backcast.py
  thresholds:
    vxo_heldout_corr_log_min: 0.90        # 1986-89 true held-out era
    oct1987_peak_ratio_min: 0.75          # predicted/actual, VIX-equivalent
    oct1987_peak_ratio_max: 1.35
    stress_bias_log_abs_max: 0.20         # top RV decile, OOS 2008+
    ensemble_vol_of_vol_ratio_min: 0.85
    coverage_80_tolerance: 0.10
  consequence: >-
    A fit failing any threshold does not ship: no backcast rows enter any
    vintage, and the failure is recorded in the provenance artifact.
```

## Notes for the ratifier

- The 1986-89 held-out check is the strongest test available: VXO is
  observed there and the model never sees it (fitted 1990+ only).
- The Oct-1987 band is asymmetric-wide because the episode is a single
  month of extrapolated tail; the floor (0.75) is the load-bearing side.
- `type: protocol_change` because the entry registers protocol for a new
  object; it changes nothing sealed, so no re-seal follows. If at
  ratification a different amendment type is preferred, only the `type`
  field changes — the thresholds are the substance.
