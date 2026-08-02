# EU AI Act obligation mapping + NIST AI RMF scaffold (WP4.10)

*The generative components' regulatory posture, mapped to what is actually
built. Internal working document; counsel review precedes any client-facing
reliance on these classifications.*

## System classification (working view)

Terrarium's generative components produce **fictional in-world content and
bounded simulated decisions inside a training/research simulation**. No
generative output enters the certified numeric path (structural, tested);
no output constitutes investment advice (every artifact is watermarked
"not investment advice" in the renderer and re-marked on export); no
component interacts with natural persons as a deployed consumer system in
the current phase (owner-only testing, D-K4-5).

| Component | Working classification | Rationale |
|---|---|---|
| Scenario compiler | Minimal risk | Authoring aid; output fully validated by schema + validator before use |
| Narrator (Tier-2) | Limited risk — transparency duties | Generates text a user reads; simulated-world marking satisfies the disclosure impulse (Art. 50-style transparency): nothing can screenshot as real |
| AI committee | Limited risk (research phase) | Simulated decisions in a bounded sandbox; no real-world effect; study-gated claims |

## Obligation mapping (what the build already does)

| Obligation theme | Where it is discharged |
|---|---|
| Transparency / AI-content disclosure | Watermark applied IN the renderer, re-applied on export, G8 blocks stripped marking; tested including screenshot-resistance intent |
| Technical documentation | This pack: prompt registry (versions, hashes, regression links), sealed gate rules (G4-pre), evidence documents per component |
| Record-keeping / traceability | G9 chronicle record (payload hash, prompt version, model id, gate result, retry count) on every publication; decision records with persona + prompt version + model id |
| Accuracy and robustness testing | The frozen 30-payload regression set (five live runs, trajectory recorded); injection testing on every payload path (tests/test_injection.py); the consistency gate G1–G9 |
| Human oversight | Ship gates require human review items (voice drift, disagreement quality); the owner ratifies prompt versions; heuristic fallback guarantees a non-generative path always exists |
| Data governance | Payload builders are deterministic code over the tape; no personal data enters any prompt; entities are fictional by construction (B1 screen against SEC EDGAR + curated registry, version recorded) |
| Risk management (ongoing) | Pathology measurements published internally BEFORE claims (ACTOR-VALIDATION.md); the no-client-facing-claim rule stands until the human-cohort study completes |

## NIST AI RMF scaffold (Govern / Map / Measure / Manage)

- **Govern**: the seal mechanism (G4-pre freeze, amendment log with post-hoc
  flags), the prompt registry, owner decision records (D-K4-*), the
  retrofit register's append-only discipline.
- **Map**: `governance/genai-track.md` — every generative component, its
  role, and the one hard rule (never in the numeric path, structurally
  tested at `tests/test_artifacts_service.py::TestBoundary`).
- **Measure**: the regression trajectory (3.3% → 76.7% first-pass, gate
  lineage versioned), fallback rate 0.20, persona sensitivity 0.78, effect
  sizes that cannot travel without dispersion.
- **Manage**: the two-retries-then-fallback rule; ship gates that hold
  releases (Tier-2 disabled at 76.7% < 95%); the heuristic ablation as the
  always-available non-generative substitute.

## Open items

- **Research-use consent disclosure** (D-K5-4, owner-approved 2026-08-02):
  the public product's ranked runs will feed the RQ5 behavioural panel;
  the research-use disclosure is designed into the consent flow from the
  start (sharing-spec s12 framing) and joins this counsel review — added
  now, per STEP5-amendment-A1, rather than retrofitted after players
  exist.

- Counsel review of the classifications above before any client-facing use.
- Re-map when the human-cohort phase begins (natural-person interaction
  changes the transparency surface).
- GPAI-provider obligations sit with the model vendor (Anthropic); this
  mapping covers Terrarium as deployer/integrator.

---

*Not legal advice; not investment advice.*
