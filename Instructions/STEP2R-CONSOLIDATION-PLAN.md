# STEP2R-CONSOLIDATION-PLAN.md — Freeze the Contracts, Absorb the Retrofits
## Implementation plan for Claude Code · runs after Gate G2, before Step 3 · ~1 week

**Purpose.** Not new capability. This step freezes every interface Step 3 will build against, absorbs the retrofit register items R1–R7 and R13–R14 from `MASTER-ROADMAP.md`, bumps contract versions, and re-runs everything under the new contracts. Consolidation is what keeps the thin-slice build from accumulating drift.

**Prerequisite:** `v0.2.0-g2` tagged, `G2-EVIDENCE.md` accepted. **Exit:** `v0.3.0-contracts` tagged; no Step 3 work blocked by an unfrozen interface.

---

## WP2R.1 — Taxonomy freeze and the Albourne mapping (R1, R13)
Create `taxonomy/sleeves.yaml`: the platform's own `sleeve_id` namespace covering the full HF and PM breadth from `sleeve-vehicle-state-spec.md` §1, each with group, default vehicle type, modeled-in-v1 flag, and a one-line definition. Create `taxonomy/albourne_mapping.yaml` mapping vendor codes → `sleeve_id` (populated from the scope inventory; unmapped vendor codes are an intake error, not a silent drop). Re-validate Step 1's intake schemas against the namespace and re-file existing intakes. **Secondaries enters as its own sleeve** (R13) with the note that its TA parameters are estimated separately, never cloned from buyout.
*Acceptance:* every delivered Albourne series maps to exactly one `sleeve_id`; an unmapped code fails intake with a readable report; `taxonomy` is versioned and referenced by id everywhere downstream.

## WP2R.2 — Hedge fund de-smoothing (R2)
Extend Step 1's `desmooth.py` coverage to every `albourne.hf_*` series (GLM MA(k) primary, Geltner secondary), regenerate `DESMOOTHING.md` with HF sections, and add HF diagnostics to the D1 exhibit set. Note in the report which HF strategies show material smoothing (expect: credit, structured credit, ILS, distressed) versus negligible (liquid macro, CTA) — this is itself a finding worth recording.
*Acceptance:* every modeled HF sleeve has de-smoothed series and diagnostics; volatility-ratio and beta-shift tests pass; means unchanged within tolerance.

## WP2R.3 — Sleeve/vehicle state schema freeze (R3, R14)
Author `schemas/sleeve-vehicle-state-v1.0.schema.json` + pydantic mirror, implementing `sleeve-vehicle-state-spec.md` §3 with the **three vehicle types** (closed-end drawdown, open-ended NAV, evergreen/semi-liquid) as first-class (R3), and explicit fields for **recycling/recallable balance** (R14), fee/carry state, and the granularity discriminator (`n_funds`, `dispersion_draw`). Dual validation (jsonschema + pydantic) with the agreement test, exactly as WorldSpec.
*Acceptance:* round-trip test on a hand-authored example of each vehicle type; schema/pydantic agreement property test green.

## WP2R.4 — Generator output schema + the factor-set decision (R4, R5)
Author `schemas/generator-output-v1.0.schema.json`: the factor namespace with units, the **primitive vs derived** split declared explicitly (derived variables carry their defining identity as metadata), slow states, regime path, waypoint/diagnostic block, and the provenance quartet. Refactor Step 2's `Ensemble` to emit and validate against it. **Resolve R5 (FX / non-US factors) here**: either add them to the factor set — which requires re-running the reference statistics and re-sealing the battery, with the amendment logged — or record the decision to defer with its rationale and its consequence for institutions with unhedged exposure. Do not leave it open.
*Acceptance:* all registered systems emit schema-valid ensembles; the identity metadata lets a consumer recompute every derived variable; the FX decision is written into the decision register with a status.

## WP2R.5 — Data layer additions and vintage handoff
Absorb whatever `GAPS.md` accumulated during Step 2 (new series discovered as needed, retired sources, SLA changes). Transition the campaign from Step 2's **frozen vintage** back to rolling refresh: document the last campaign vintage in the model inventory, verify that re-running the G2 battery on the frozen vintage still reproduces `G2-EVIDENCE.md`, then re-enable the monthly cron.
*Acceptance:* `ah data refresh` green; frozen-vintage reproduction verified and recorded; gap register current.

## WP2R.6 — Portfolio variable extensions (R6, R7)
Schema-level only — implementation is Step 3. Add to the portfolio/institution state: **interest-rate and inflation hedge ratios**, **collateral pool** (eligible assets, haircut schedule, posted, headroom), **leverage** (explicit and pass-through), **transaction cost** parameters per liquid sleeve, **portfolio-level fee drag** aggregation, and **FX hedge ratio** (consistent with the R5 decision). These are the variables that make a DB pension twin behave like a pension rather than an endowment with liabilities attached.
*Acceptance:* schema fields exist with units and defaults; a stub institution instance validates; Step 3's plan references them by name.

## WP2R.7 — WorldSpec v1.2
Bump for: the resolved `generator_id` namespace (including whichever system G2 promoted — or `bootstrap-v1` if the benchmark shipped), the sleeve-namespace reference, the finalized `temporal_delivery` block, and any factor-set change from R5. Update the validator (V-rules unchanged unless the factor set moved), migrate stored example worlds and presets, changelog entry.
*Acceptance:* all Step 0/1/2 worlds migrate and revalidate; replay of a pre-migration RunRecord still reproduces its digest (migration is metadata-only for existing runs).

## WP2R.8 — Governance and decision-register consolidation
Refresh `model-inventory.yaml` with every Step-2 model card. Update `governance/decision-register.md`: mark D1 (de-smoothing), D2 (factor set + regime ruleset), D3 (generator + sampler), D4 (tail objective + strategy set), D5 (state space), D6 (thresholds) as **CLOSED** with links to the evidence that closed them; leave D7–D10 open with their Step-3 owners named. Archive `G2-EVIDENCE.md`, the ablation tables, and the negative-control report into `governance/evidence/`.
*Acceptance:* the register's status column is accurate; a reader can trace every closed decision to its artifact.

## WP2R.9 — Full-stack regression under the new contracts
Re-run: Step 0's G0 checklist, Step 1's refresh + de-smoothing + episode packs, Step 2's battery on the promoted/benchmark system, and the CLI end-to-end. Everything must pass under the frozen contracts, and any digest that legitimately changed (because a schema changed) must be re-baselined with an explanatory changelog entry — never silently.
*Acceptance:* CI green; `CONSOLIDATION-EVIDENCE.md` lists every contract version, every re-baselined digest with its reason, and confirms zero open retrofit items assigned to 2R. Tag `v0.3.0-contracts`.

---

## Notes
- **Duration:** roughly a week of focused sessions. Resist scope growth — every "while we're in here" idea goes to the retrofit register for 3R.
- **The one judgment call:** R5 (FX). Adding factors after the battery seal costs a re-seal and re-run; deferring costs modeling fidelity for non-US-exposed institutions. Make it explicitly, record it, move on.
- **If G2 shipped the benchmark:** nothing in this plan changes except that `generator_id` defaults to `bootstrap-v1` and the model inventory records the honest negative result alongside the ablation evidence. Step 3 proceeds identically.
