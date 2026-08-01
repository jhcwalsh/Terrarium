# G1-EVIDENCE.md — the 2022 end-to-end reproduction (WP3.11)

Vintage `2026-08-01.2`; window 2021-12-01..2023-12-31; every criterion sealed at
G3-pre (`pre-registration-g3.yaml`) BEFORE any of the judged code existed.
Public trough: 2022-09-01. Deterministic, no RNG.

## Verdict

**Episode criterion set: FAIL** (tier 1, `linkage_version tier1-public-0.1`).

| criterion | value | sealed pass condition met | detail |
|---|---|---|---|
| public_equity_drawdown | -0.2484 | YES | replay -0.2484 vs sealed reference -0.2484 (+/- 0.05) |
| mark_lag | 0.9667 | NO | PM lag 1.0m (sealed [1,6]), HF lag -3.1m (sealed [0,3]) |
| distribution_shortfall | 0.5442 | YES | depth 0.544 of normal (sealed [0.45, 0.55], the P-A calibration) |
| secondary_pricing | 0.8100 | YES | price 0.810 of NAV (sealed [0.76, 0.86], anchor 0.81) |
| private_weight_breach | 0.0332 | NO | breach at trough-9m, size 0.033 (sealed: within 3m, >= 0.02) |
| coverage_warning | 1.0000 | YES | unfunded/NAV present: True; unfunded/liquid present: True |

### Named limitations (the gate rule's permitted failures, named as required)

- **private_weight_breach** failed: breach at trough-9m, size 0.033 (sealed: within 3m, >= 0.02)

## Tier 0 vs tier 1 (the sealed tier0_beats_rule)

Tier 1 episode score (criteria failed): **2**; tier 0: **3** (tier 0's constant G produces NO distribution drought — depth 1.0, sealed fail).
**Tier 1 BEATS tier 0** (strictly lower score; a tie is not a beat). Claim scored under `linkage_version tier1-public-0.1`; a later `panel-1.0` claim is separate.

## Chain notes

- The public path is OBSERVED history: its drawdown criterion validates the
  chain's wiring, not a model.
- Mark lags use the frozen kernel with its MEASURED stickiness of 0.0 — this
  replay is the genuine test that criterion was preserved for.
- The secondary price is the v1 POLICY constant at the public anchor (0.81);
  a state-dependent discount curve is a later refinement, named here.
- The reference institution: 62% public equity / 38% mid-life buyout cohort,
  private range upper 0.35 — over-allocated at the door, as the sealed
  formula delegates to this replay spec.

## Diagnosis of the mark_lag failure (the finding, not an excuse)

The HF half fails at -3.1 months: the mapped HF composite's cumulative
trough lands at 2022's FIRST leg (June), three months before the public
total-return trough (September) — so no smoothing kernel could produce a
positive lag; the composite's own trough timing dominates. Two candidate
accounts, both already on the record:

1. **The sealed HY omission.** `hy_spread` is a sealed missing factor, so
   the loadings carry no high-yield channel — precisely the exposure that
   deepened HF credit losses into the autumn re-trough. The next campaign's
   panel (which revives HY via its splice) re-tests this mechanically.
2. **Stickiness lives in 2021-23.** The kernel's stickiness was MEASURED at
   0.0 on pre-2021 stress and the 2021-23 span was off-limits (holdout +
   judging episode). This replay is the genuine test that discipline
   preserved — and its answer is that 2022's mark lag does NOT fully emerge
   from the MA structure alone. Re-estimating stickiness with post-2021
   data is a NEXT-CAMPAIGN decision, taken with results in view and said so.

Under the sealed gate rule the criterion set FAILS (mark_lag is must-pass),
tier 1 still BEATS tier 0, and per the plan's own DoD the result ships
reported honestly rather than tuned quiet.
