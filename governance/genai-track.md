# Generative-AI track (STEP0-PLAN §WP0.9)

This page tracks every generative component of the platform, its guardrails, and the
external frameworks we align to. It is the standing answer to "where does an LLM
touch this system, and how is that bounded?".

## Components

| Component | Status | Role | Reads narrative? | In numeric path? |
| --- | --- | --- | --- | --- |
| Scenario compiler | live (Step 0 offline) | scenario text → WorldSpec JSON | n/a (writes it) | **No** |
| Narrator (Tier-2, WP4.4) | **SHIPPING** (pair rule met 2026-08-02: 96.7%/100.0% at pipeline v2; fifteen-run trajectory in the manifest) | letters/notes from deterministic payloads, judged by gate G1–G9 | yes (bible cast, arcs) | **No** (boundary test since wp4-01) |
| AI committee (WP4.8) | built; **study-grade only** (WP4.9 incomplete until the human-cohort arm runs, D-K4-5) | bounded in-world decisions, briefed behind the wall, rationales filed | yes (wire, briefing) | **No** (decisions reshape the institution, never the tape) |

Registry of every prompt, version, hash pin, and ship status:
`governance/prompt-registry.yaml` (WP4.10). Gate evidence:
`governance/evidence/G4-EVIDENCE.md`. Regulatory posture:
`governance/eu-ai-act-mapping.md`.

## The one hard rule

**No generative output ever enters the numeric path.** The engine consumes a
`NumericWorld` projection that structurally omits `narrative`; a test scans the
engine/institution source for any narrative access. The compiler produces
parameters and prose *together* so they agree, but the simulation is fully
determined by the structured parameters (WORLDSPEC.md §1).

## Prompt versioning policy

- Every prompt lives in a versioned library entry (e.g. `compile-world-v1.0`) and
  its version is recorded into `provenance.source.compiler_prompt_version`.
- Any prompt change bumps the version and must pass the ~50-scenario regression set
  (`tests/test_compiler.py`) before deployment, with compiled-parameter diffs
  reviewed by a human.
- The model id is pinned per prompt version and bumped deliberately (D9).

## External frameworks tracked

- **EU AI Act** — the platform is a decision-support tool; generative components are
  clearly delineated and excluded from the numeric/decision path.
- **NIST AI RMF** — map/measure/manage: this register + the model inventory are the
  "map"; the fixture regression and battery are "measure"; the no-numeric-path rule
  and human approval (D10) are "manage".
