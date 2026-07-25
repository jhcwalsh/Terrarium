# Retrofit register

**What this is.** A dated, append-only log of ideas, gaps, and scope items that surface
*during* a work package but are not that work package's job to fix. WP2.1b's own scope
discipline states the rule plainly: "if an idea arrives during this work that is not one
of the [named] items, write it to the retrofit register and move on." This file is where
it lands.

**Rules.**
- **Append-only.** New rows go at the bottom of the table. Never edit, delete, or
  reorder an existing row -- if a deferred item is later resolved, add a new row (or a
  note in the decision register) that references this row's `id`, rather than rewriting
  history here.
- Every row must name where the item actually lands (a work package, a decision-register
  id, or "unscheduled" if genuinely not yet planned) so a reader can trace it forward.
- This file records *that* something was deferred and *why*; it does not carry the
  technical detail of the deferred item itself -- that lives wherever the item is
  properly documented (a plan section, `factors.yaml`, `pre-registration.yaml`, etc.).

| date | id | raised in | item | why deferred | where it lands |
| --- | --- | --- | --- | --- | --- |
| 2026-07-25 | RFR-1 | WP2.1b Task 2 (D4 strategy-set redefinition) | `commodities` has no Step-1 data source. It is declared in `factors.yaml`'s `global` block and carries weight in two D4 strategies (`eqw_factors` 0.20, `endowment_proxy` 0.10 -- see `pre-registration.yaml`'s `rationale.d4_commodities_consequence`), but no series in `requirements.yaml` sources it. | Registering a commodities series is a new connector, which falls under the `requirements.yaml` §WP1.9 emergent-requirements rule -- out of scope for a pre-seal patch that is meant to stay narrow (WP2.1b's own scope discipline). | WP2.2 (register the series; the two affected D4 strategies' reference statistics become computable once it lands) |
| 2026-07-25 | RFR-2 | WP2.1b Task 5 (governance) | FX block (decision R5) -- unhedged foreign-currency exposure is out of scope for v1. | Closed CLOSED-deferred rather than resolved open: adding an `fx` block after the generator is trained requires new cross-block correlation the trained weights don't have. | Re-entry path is a `block_addition` amendment (`governance/amendment-log.yaml`) plus a full generator retrain; see `governance/decision-register.md`'s Step 2 section, row `R5` |
| 2026-07-25 | RFR-3 | WP2.1b Task 5 (governance) | UK factor block (decision J3) -- `bank_rate`, `gilt_nominal_10y`, `gilt_real_10y`, `rpi`, `cpi_uk` (declared but inactive in `factors.yaml`'s `uk` block). | Closed CLOSED-deferred rather than activated: activating it before the seal would have required the Step-1 UK data connectors (BoE curves, ONS RPI/CPI) to exist first, and `Instructions/WP2.1b-PRE-SEAL-PATCH.md` explicitly says not to hold the seal for them. | Re-entry path is a `block_addition` amendment plus a full generator retrain, same as R5; see `governance/decision-register.md`'s Step 2 section, row `J3`. `Instructions/WP1.12-UK-CONNECTORS.md` scopes the connector work that would precede activation. |
| 2026-07-25 | RFR-4 | WP2.1b final branch review (pre-seal patch) | `ah.gen.base.EnsembleMeta.active_blocks` has no producer. The field exists with default `()` and the battery already records it, but no generator exists yet to populate it, and nothing validates a populated value against the manifest. | Building the generator that would set it is WP2.2/WP2.4 scope, not a pre-seal-patch fix; the field and its default are correct as of WP2.1b, only its producer is missing. | WP2.2/WP2.4 -- every generator must set `active_blocks`, and validation against `ah.factors.load_manifest().active_blocks` should reject a mismatch. |
| 2026-07-25 | RFR-5 | WP2.1b final branch review (pre-seal patch) | Threshold-vs-data-availability gap: `ah.eval.prereg.verify()` checks that a threshold key names a real factor in the right block and a registered stat, but not that the factor has data. A threshold such as `"commodities.skew"` at `enforce` severity would seal cleanly while `ah.eval.reference.compute_reference` records `commodities` in `missing_factors` and computes nothing for it (see RFR-1). | Closing this requires `reference.py`'s `missing_factors` output as an input to `verify()`, which is WP2.2/WP2.3 scope; this patch's Fix 3 only aligns `_check_conventions` with `ah.strategies`, a distinct hole. | WP2.3 -- before sealing, cross-check every threshold key against the reference run's `missing_factors` and reject any `enforce` (or any) threshold keyed to a factor with no computed reference statistic. |
| 2026-07-25 | RFR-6 | WP2.1b final branch review (pre-seal patch) | `ah/splits.py`'s docstring promises the train/validation/holdout dates "are sealed in pre-registration.yaml (WP2.3)", but `pre-registration.yaml` has no `splits:` section yet. `splits.py` is now itself a hashed judged source (this patch's Fix 1), so the code's dates and the not-yet-added sealed dates cannot silently diverge once WP2.3 seals -- but they are not yet reconciled either. | Adding the sealed splits section is WP2.3's own sealing act, not a pre-seal-patch documentation fix. | WP2.3 -- add a `splits:` section to `pre-registration.yaml` recording the TRAIN/VALIDATION/HOLDOUT boundaries, and a test asserting `ah.splits.SPLITS` matches it exactly before sealing. |
