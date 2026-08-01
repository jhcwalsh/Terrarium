# KICKOFF-STEP3.md — Translation Layer Kickoff

*Wrapper for `STEP3-TRANSLATION-PLAN.md` (v1.0) + `STEP3-amendment-A1.md`, in the
manner of `KICKOFF-STEP0.md`. Drafted 2026-08-01 at Step 2R close for owner
approval; the plan and amendment stay authoritative — this document sequences
them, records what changed between their authorship and kickoff, and resolves
the ambiguities that must not reach a gate evidence pack.*

---

## 1. Prerequisites — status at kickoff

| Prerequisite | Status |
|---|---|
| `v0.3.0-contracts` (Step 2R exit) | Tagged at 2R close; `CONSOLIDATION-EVIDENCE.md` is the record |
| `sleeve-vehicle-state-spec.md` | Vendored (owner-supplied, 2026-07-31). **Reconstruction caveat**: its own header marks §3 as recovered text; WP2R.3 froze the schema against it, stated |
| `model-parameter-register.md` | Vendored (owner-supplied, 2026-07-31); G3 DoD item 5 is judgeable |
| `albourne-derived-measures-spec.md` | Vendored since Step 1 |
| Phase-A documents (liquidity spine v0.2, linkage estimation) | Vendored 2026-07-31 |
| HF strategy returns, de-smoothed | **Better than planned**: 21 sub-strategy series delivered (vintage `2026-08-01.2`), de-smoothed with diagnostics (`DESMOOTHING.md`) — owner decision, option (b) |
| ALB-A/B (cashflow profiles, market linkage) | **Not delivered.** Non-blocking by Amendment A1 Delta 1: tier 1 calibrates `linkage_version: public-0.1` (Robinson–Sensoy per linkage-estimation §5, provisional values P-A/P-B closed); the Albourne panel becomes the institutional recalibration (`panel-1.0`), off the public critical path |
| ALB-C (age×calendar) | Not delivered → WP3.12 records the deferral, per the plan's own instruction |
| ALB-F (gating base rates) | Not delivered → WP3.6 calibrates queues/gates against the 2022–23 open-ended RE reference episode (spec §6's stated fallback) |
| 2022 episode pack | Builds (`ah data episode 2022`, re-verified at 2R.9) |
| Generator | `hier-flow-v1` promoted (G2), authorable in WorldSpec v1.2, emits the generator-output contract (regime path + slow states on every ensemble) |

**Standing caveat carried into every Step 3 decision:** the promoted generator
beats the benchmark on the sealed criterion and is *not* a convincing model of
history (regime persistence undercalled, drawdowns understated ~2×, decade tier
73% unavailable — `G2-EVIDENCE.md` §7–8). Step 3 builds the translation layer on
it regardless — the layer is generator-agnostic by construction — and nothing
built here is represented as decision-ready; that is Step 5's question, after
the next generator campaign.

## 2. Gate spine

`G3-pre` (seal, before any estimation) → `G1-completion` (2022 end-to-end
reproduction, WP3.11) → `G3` (engine definition-of-done).

### G3-pre — the seal comes first (Amendment A1 Delta 6)

Sealed **before WP3.2 estimation begins**, on G2 terms, in a **new lock**
(`pre-registration-g3.lock`) covering:

1. **The sleeve-level tail battery** (DN-5 §7, option 1): thresholds authored
   from train+validation only, on the de-smoothed sub-strategy panel, plus the
   code that judges them — hashed together.
2. **The 2022 episode-reproduction criteria** (drawdown magnitudes, mark-lag
   length, weight-breach timing/size, distribution shortfall, secondary
   pricing): frozen here so no cashflow parameter is ever tuned against the
   episode that judges it (the plan's own pitfall, closed structurally).
3. **The tier-0-beats rule** for WP3.5/3.4, with `linkage_version` named in
   every comparison (Delta 4).

The seal guards (`tests/test_seal_guards.py`) extend to the new lock in the
same commit that creates it — the first seal born with its guards. **W11
attends the pre-seal review** (MPP-A1); scheduling is the owner's action.

### AM-4 numbering collision — resolved for gate purposes

Gate evidence cites the Phase-A documents **by title** — *liquidity-spine
v0.2*, *linkage-estimation* — never as "WP3.9"/"WP3.10". Plan-numbered WP3.9
(proxy models) and WP3.10 (hero funds) keep the plan's meaning. No evidence
pack may cite a bare "WP3.9/WP3.10" without qualification.

## 3. Build order (one WP per branch)

| # | Branch | Scope | Binding constraints |
|---|---|---|---|
| 0 | `wp3-00-g3pre-seal` | G3-pre as above | Precedes all estimation and all cashflow code |
| 1 | `wp3-01-state-objects` | Runtime state per the frozen v1.0 schemas: cohort, open-ended, evergreen, liquid, portfolio, institution; pure transitions + property tests; hero mode (`n_funds=1`, `dispersion_draw`) | Fresh implementation against liquidity-spine v0.2 (owner-accepted recommendation); no I/O |
| 2 | `wp3-02-mappings` | Per-sleeve loadings on **de-smoothed** series; residual vol + cross-sleeve residual correlation; stability/regime diagnostics; the D1 exhibit (smoothed-vs-de-smoothed betas) | Train+validation only — the holdout guard extends to mapping estimation; regime treatment decision closes register row D4; ensembles' emitted regime labels are the conditioning surface |
| 3 | `wp3-03-smoothing` | Forward smoothing per vehicle type; `desmooth(smooth(x)) ≈ x` tolerance test; reported serial correlation matches history | θ weights from Step 1/2R |
| 4 | `wp3-05-tier0` | Historical-simulation + constant-G TA benchmarks, **frozen before tier 1 exists** | Spec frozen at G3-pre |
| 5 | `wp3-04-tier1` | Market-sensitive TA at `public-0.1`; fees/carry/waterfall, recycling, sub-line deferral, extensions | Delta 3 binds: **no crisis-regime term** (with its acceptance test); f_call near-flat for buyout in stress; age-dominates-macro stated in the model card |
| 6 | `wp3-06-vehicles` | Notice/lockup/gates/side pockets; evergreen queues that lengthen under stress | 2022–23 RE reference episode standing in for ALB-F |
| 7 | `wp3-07-portfolio` | Cash, pacing, rebalancing + transaction costs, shortfall hierarchy, **forced-sale flag as headline output**, breach detection, fee drag | Fields per the frozen institution contract |
| 8 | `wp3-08-twin` | DB pension: liabilities, discounting, funding ratio, contribution policy, hedges + collateral pool, leverage | Twin's counterfactual = the stated t₀ pacing plan (Delta 5 / D9-ledger sense) |
| 9 | `wp3-09-proxies` | LSMC proxies; error bounds **in the capital region** pre-stated | |
| 10 | `wp3-10-hero-funds` | 3–5 named synthetic funds; aggregate reconciles to cohorts (test) | Step 4's prerequisite |
| 11 | `wp3-11-2022-reproduction` | The G1-completion run, scored against the G3-pre-sealed criteria; `G1-EVIDENCE.md` | Delta 4: framed so it does not re-certify what Phase A demonstrated |
| 12 | (single commit) | WP3.12 deferral record (ALB-C absent) | |

**Parallel obligations, slotted after `wp3-02`:** the Step 5 metric freeze
(WP5.1–5.2 definitions **plus** the holdout-evaluation specification demanded
by `AM-2026-07-31-002`) — frozen during Step 3, before any result they will
ever judge exists. The next generator campaign (FX block per
`S2R-FX-NEXT-CAMPAIGN` + `WP1.13` CAPE + the regime-persistence fix; one
retrain buys all three) runs whenever GPU time suits — independent of Step 3's
critical path, but it must land before Step 5's evaluation runs.

## 4. Open decision for the owner at kickoff

**G3-pre threshold granularity.** Author sleeve-tail thresholds per **modeled
sleeve** (7 HF + 9 PM, pooling member sub-strategy series under a pooling rule
stated in the seal) or per **delivered series** (21 + 9)?
**Recommendation: per modeled sleeve.** It matches the build list and DN-5's
intent, keeps the threshold count reviewable, and the pooling rule — sealed —
preserves auditability. Per-series remains available as a later additive
amendment if a sleeve's members prove heterogeneous.

## 5. Halt conditions

- Any Step 3 WP finding the sleeve-vehicle-state spec's reconstructed text
  materially ambiguous **halts and asks** rather than interpreting — the spec's
  own header requires verification before reliance.
- WP3.2 halts if any mapping would require holdout-span data — the guard is
  absolute and extends to estimation.
- The institutional recalibration (`panel-1.0`) halts until ALB-A/B deliver;
  it never blocks the public tier.
- RFR-88's PM half **must be fixed before the first PM cashflow intake is
  applied** (the code/id mismatch would land data under wrong ids silently).

## 6. Housekeeping

- CI coverage gate extends to `ah/port/` and `ah/twin/` at ≥85% when those
  trees first appear (G3 DoD item 7).
- `tier1-synthesis-and-decisions.md` remains missing; nothing in Step 3 names
  it (re-checked at kickoff).
- The decision register's open rows D4 (correlation regime) and D5 (structural
  vintage default) are owned by WP3.2 and world authoring respectively; close
  them when their WPs decide, with evidence.

---

*Not investment advice.*
