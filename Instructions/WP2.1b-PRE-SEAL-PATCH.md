# WP2.1b — PRE-SEAL PATCH
## Work package for Claude Code · Alternate Histories Platform · runs before WP2.3 (pre-registration seal)

**Context.** The pre-registration seal at WP2.3 is a one-way door: after it, every change is a dated, post-hoc-flagged amendment visible in every evaluation report thereafter. Three items are known now and must be inside the seal. This patch is deliberately narrow — it does not add capability, only structure that the seal will freeze.

**Prerequisite:** WP2.1 merged (splits, registry, experiment scaffolding). May run in parallel with WP2.2 (battery), but **must merge before WP2.3**.
**Scope discipline:** if an idea arrives during this work that is not one of the three items below, write it to the retrofit register and move on.

---

## Item 1 — Redefine the D4 benchmark-strategy set over generator outputs only

**Problem.** The D4 set (whose VaR/ES define tail fidelity, and which the tail auxiliary loss optimizes) currently includes an "endowment mix" defined over portfolio sleeves. The generator produces factors, not sleeve returns, so the battery cannot compute this without importing Step-3 machinery — and the sleeve taxonomy is not frozen until Step 2R.

**Fix.** Define every D4 strategy purely as weights over **generated factors and their derived series**:

| Strategy id | Definition |
|---|---|
| `eqw_factors` | Equal weight across the generated factor set's return-bearing series |
| `sixty_forty` | 60% equity total return, 40% long-government total return |
| `endowment_proxy` | Factor-level stand-in for the endowment mix: equity / govt / credit / commodities / REITs at stated weights, **with private sleeves represented by their nearest factor proxy** — the weights and the proxy mapping are stated explicitly in the pre-registration |
| `momentum` | 12-1 momentum on the equity factor, monthly rebalanced, rules stated in full |
| `carry` | Term-structure carry rule, stated in full |

Each definition specifies: constituent series, weights, rebalancing frequency, and any lookback — completely, so the set is reconstructible from the pre-registration alone with no reference to code outside the sealed hash.

**Rationale text to include in `pre-registration.yaml`** (so the reviewer sees this was considered, not accidental): *the generator's outputs are factors; tail fidelity is therefore assessed on factor-level portfolios. The endowment proxy stands in for the institutional mix at the factor level. Sleeve-level tail behaviour is a Step-3 property, evaluated separately once mappings exist, and is not a G2 criterion.*

**Acceptance:** `tails.py` computes every D4 strategy from an `Ensemble` alone, with no import from portfolio or sleeve modules (import-graph test). Strategy definitions round-trip from the YAML. A test asserts the set used by the tail auxiliary loss and the set used by the battery are the same object, loaded from the same config.

## Item 2 — Restructure the factor manifest into blocks, with per-block pre-registration

**Problem.** A monolithic factor set means adding a jurisdiction later invalidates the sealed thresholds wholesale.

**Fix.** Introduce a block layer in the factor manifest:

```yaml
factor_blocks:
  global:  [equity_mkt, smb, hml, mom, equity_vol, commodities, ig_spread, hy_spread]
  us:      [policy_rate, ust_2y, ust_10y, cpi, hqm_curve, funding_spread]
  uk:      [bank_rate, gilt_nominal_10y, gilt_real_10y, rpi, cpi_uk]   # in or out per Item 3
active_blocks: [global, us]        # or [global, us, uk]
```

Requirements:
- `reference.py` computes reference statistics and bootstrap bands **per block**, and separately for **cross-block joint metrics** (correlation structure, crisis co-movement) with the block pair recorded.
- `pre-registration.yaml` nests thresholds under block ids and under cross-block pair ids.
- `prereg.verify()` checks that every active block has thresholds and that no threshold references an inactive block.
- The amendment log gains an explicit entry type: **`block_addition`** — additive by construction, requiring new per-block thresholds plus new cross-block joint thresholds, and *not* invalidating existing single-block thresholds. Document this property in the amendment log's header so a later reviewer understands why a block addition is not a re-seal.
- Every ensemble and battery report records `active_blocks`.

**Acceptance:** a synthetic two-block configuration passes the battery; adding a third block in a test fixture produces a valid `block_addition` amendment and leaves the original blocks' thresholds byte-identical; a threshold referencing an inactive block fails verification.

## Item 3 — Resolve FX (R5) and the UK block (J3) explicitly

**Problem.** Both are open, both are inside the seal's blast radius, and "we'll decide later" is itself an undocumented decision.

**Fix.** Take both decisions and record them, whichever way they go.

**FX (R5).** Either (a) add an `fx` block (base-currency-relative rates for the active jurisdictions) with its thresholds, or (b) record the deferral. If deferring, the pre-registration must state the consequence in one sentence: *institutions with material unhedged foreign-currency exposure are out of scope for v1; adding FX later is a `block_addition` amendment.*

**UK block (J3).** Either activate it — which requires the Step-1 data layer to supply BoE nominal/real/inflation curves and ONS RPI/CPI before the seal, so the reference statistics exist — or record the deferral with the same one-sentence consequence: *UK-domiciled institution twins are blocked until a `block_addition` amendment; the plugin interface accommodates them without rework.*

**Note on ordering.** If the UK block is wanted but the data connectors are not ready, do **not** hold the seal for them. Seal with `[global, us]`, and add UK as a clean `block_addition` when the data lands — that path now exists precisely so this choice is cheap. The wrong move is sealing a monolithic set and discovering the coupling later.

**Acceptance:** `governance/decision-register.md` shows R5 and J3 as CLOSED with the chosen option and its recorded consequence; `pre-registration.yaml` contains the rationale text; no open item in the register is marked as blocking WP2.3.

---

## Deliverables
- Updated `pre-registration.yaml` (unsealed) containing: block-nested thresholds, complete D4 strategy definitions, and the two rationale statements.
- `eval/reference.py` and `eval/tails.py` refactored per Items 1–2.
- `prereg.py` extended with block verification and the `block_addition` amendment type.
- `governance/decision-register.md` updated (D4 amended, R5 and J3 closed).
- PR description listing the three items, the decisions taken on Item 3, and any deviations.

## Definition of done
1. Full suite green; import-graph test proves `tails.py` has no portfolio/sleeve dependency.
2. Block round-trip and `block_addition` fixture tests pass.
3. Decision register shows zero open items blocking WP2.3.
4. A dry-run `prereg.seal()` succeeds and `prereg.verify()` passes against it.

**Then, and only then, proceed to WP2.3 and seal.**
