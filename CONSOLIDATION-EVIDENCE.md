# CONSOLIDATION-EVIDENCE.md — Step 2R: the contracts frozen, everything re-run

Date: 2026-08-01. Exit: tag `v0.3.0-contracts`. Prerequisite discharged:
`v0.2.0-g2` tagged with `G2-EVIDENCE.md` accepted (2026-07-31).

## 1. Every contract version

| Contract | File | Version | Frozen by |
|---|---|---|---|
| WorldSpec | `schemas/worldspec-v1.2.schema.json` | **1.2.0** (active; v1.0 stays vendored) | WP2R.7 |
| Sleeve/vehicle state | `schemas/sleeve-vehicle-state-v1.0.schema.json` | 1.0.0 | WP2R.3 |
| Portfolio/institution state | `schemas/portfolio-institution-state-v1.0.schema.json` | 1.0.0 | WP2R.6 |
| Generator output | `schemas/generator-output-v1.0.schema.json` | 1.0.0 | WP2R.4 |
| Sleeve taxonomy + vendor mapping | `taxonomy/sleeves.yaml`, `taxonomy/albourne_mapping.yaml` | **taxonomy-v1.1** | WP2R.1, bumped WP2R.2 |
| Pre-registration seal | `pre-registration.lock` | `sha256:99ab3f772be6…`, 33 files | unchanged all of 2R — no judged source was touched |

Every contract has a pydantic mirror with jsonschema-first dual validation and an
agreement test; the three seal guards (`tests/test_seal_guards.py`) run on every
suite invocation.

## 2. The full-stack regression, in plan order

- **Step 0 (G0):** `ah world build --preset stagflation` (a migrated **v1.2**
  preset) → `ah run --paths 1000` → **`ah replay` prints MATCH**
  (`sha256:d18a36fba9f4…`) → `ah verify` True → `ah battery` 0 enforce failures
  → chronicle intact (birth + run entries) → `python -m ah.battery.report`
  0 enforce failures.
- **Step 1:** full data-layer test suites green in the gate run;
  `ah data status` current at **`2026-08-01.2`** (the first real manual delivery,
  WP2R.2); `ah data episode 2022` builds. The de-smoothing layer now covers all
  21 delivered HF series (`DESMOOTHING.md`, acceptance asserted by its
  generating script).
- **Step 2:** the battery on the promoted and benchmark systems was re-run
  end-to-end by WP2R.5's frozen-vintage reproduction — **bit-identical to the
  campaign across all six cells including retrained neural checkpoints**
  (`governance/evidence/WP2R5-VINTAGE-HANDOFF.md`). Not repeated here; that
  document is the evidence.
- **WP2R.4's deferred clause, discharged:** `hier-flow-v1` resolved from the
  registry (pinned checkpoint `b1fe26e100678a26…`, hash-verified at load),
  sampled, and its generator-output document **validates against the contract
  with every tensor digest re-derived** (`build_document` + `verify_arrays`).
  Regime layer `semimarkov`, slow-state layer `simulated`, joinery diagnostics
  present — nothing absent, nothing silent.

## 3. Re-baselined digests

**None.** No engine-consumed numeric path changed in Step 2R: the golden
snapshot, replay digests, sealed fixtures, and the seal itself are byte-stable
(the suite's digest tests passed unmodified in every WP gate, and §2's replay
MATCH is the live confirmation). The WorldSpec migration was deliberately
zero-mutation: the widened contract accepts sealed 1.0.x bytes rather than
rewriting them.

## 4. Retrofit absorption — zero open items assigned to 2R

R1 (taxonomy) → WP2R.1. R2 (HF de-smoothing) → WP2R.2. R3 (vehicle types) +
R14 (recycling/recallable) → WP2R.3. R4 (generator-output schema) → WP2R.4.
R5 (FX) → closed CLOSED-deferred at WP2.1b, folded into the next campaign's
retrain by `S2R-FX-NEXT-CAMPAIGN`. R6/R7 (portfolio/institution variables) →
WP2R.6. R13 (secondaries as own sleeve) → WP2R.1.

Register rows opened during 2R and deliberately **not** owned by it:
RFR-86 (French SLA cadence — owner decision), RFR-87 (`temporal_delivery` —
Step 4 authors it against its own plan), RFR-88's PM half (intake code/id
mismatch — bites at first PM delivery, fix then or at 3R). None is 2R work;
each has a named owner or trigger.

## 5. Deviations from the 2R plan, already recorded where they happened

- WP2R.8 added the three seal guards (justified: closes the RFR-76..84 class
  before G3-pre is minted).
- WP2R.5's "monthly cron re-enable" was vacuous (it never stopped); the local
  refresh quarantined correctly on RFR-86's cadence collision.
- WP2R.2's "re-file existing intakes" was vacuous (no intake ever existed);
  the plan's group-level HF series were replaced by sub-strategy granularity on
  the owner's decision (option b).
- WP2R.7's `temporal_delivery` block was never defined anywhere → RFR-87.
- The plan's §WP2R.8 D-ids mismatch the decision register's → closed by
  content per the owner (see the register's WP2R.8 note).

## 6. Exit

Full suite green at every merge (final gate exit 0 unpiped, coverage ≥97%
against the 90% gate throughout); ruff + pyright clean; seal verifies at
`sha256:99ab3f772be6…` with 33 files, untouched by 2R. **No Step 3 work is
blocked by an unfrozen interface.** Tag: `v0.3.0-contracts`.
