# PROPOSED amendment — close the sealed `commodities` missing factor

**Status: DRAFT — awaiting owner ratification. Nothing in this file is in
force.** The authority is `governance/amendment-log.yaml`; the sealed
`missing_factors` list still contains `commodities`, `factors.yaml` still
carries `kind: unavailable`, and a test pins both until ratification.

**Basis (WP-DATA-CMDTY, owner rulings C1-C3,
`docs/superpowers/specs/2026-08-09-cmdty-scoping.md`):** the owner-supplied
AQR Commodities-for-the-Long-Run set provides the monthly excess return of
an investable equal-weight commodity futures portfolio, 1877-02 → present.
`aqr.cmdty_ew_tr = aqr.cmdty_ew_excess + french.rf` (1,187 months,
1926-07+) satisfies the sealed `numeraire: total_return` — the exact
property every free source lacked. Verification:
`docs/data/CMDTY-REPORT.md` (parse cross-checks vs the registered free
price indices; episode readings correct unprompted: 1930-32 −73%, 1973-74
+156%, 2008 −34%).

**What ratification triggers (all of it, and it is BIGGER than the
extension family's):**

1. The entry below appended to `governance/amendment-log.yaml`.
2. `pre-registration.yaml`: `commodities` removed from `missing_factors`.
3. `factors.yaml`: the `commodities` block changes from `kind: unavailable`
   to the derived total-return construction. Both files are lock-hashed →
   **re-seal**.
4. Factor ACTIVATION is a further, separate `block_addition` amendment with
   its own pre-registered thresholds — and the factor has never been seen
   by any checkpoint, campaign, or sealed verdict: it enters FUTURE
   campaigns only, which say so in their own pre-registrations.
5. The licence caveat travels: REG tier, attribution required, raw data
   never redistributed, commercial clearance an OPEN registry item until
   the owner or counsel closes it.

## The entry, ready for `append_amendment`

```yaml
amendment_id: AM-<date>-<seq>          # assigned at ratification
type: protocol_change
date: <ratification date>
post_hoc: false
rationale: >-
  Closes the sealed missing_factor `commodities` on the owner-supplied AQR
  Commodities-for-the-Long-Run set (rule CMDTY-CFTLR-EW-TR-V1): monthly
  excess return of an investable equal-weight futures portfolio from
  1877-02, plus the registered risk-free leg (french.rf), satisfying the
  factor's sealed total_return numeraire. Verification in
  docs/data/CMDTY-REPORT.md predates this ratification. REG licence:
  attribution required, raw data gitignored and never redistributed,
  commercial clearance an open registry item. Activation is NOT effected
  here: it requires its own block_addition amendment with pre-registered
  thresholds, and the factor enters future campaigns only.
payload:
  sealed_field: missing_factors
  removed: commodities
  factor_construction: "aqr.cmdty_ew_tr = aqr.cmdty_ew_excess + french.rf"
  coverage: "1926-07 .. present (excess-only 1877-02..1926-06, excluded)"
  licence: "REG (AQR terms); commercial clearance OPEN"
  activation: deferred to a separate block_addition amendment
```
