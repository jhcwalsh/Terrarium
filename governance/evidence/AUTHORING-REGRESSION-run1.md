# AUTHORING-REGRESSION.md — the WP4.5 set, measured

Set `authoring-regression-1.0` (30 payloads); model `claude-sonnet-5`;
prompts `author-prompt/letter@1.0` / `note@1.0`; run asof 2026-08-02 (LIVE).
Ship gate (FROZEN, AM-2026-08-02-002): first-pass gate rate >= 95%.

| first-pass | pass after retry | fallback | first-pass rate | ships |
|---|---|---|---|---|
| 1/30 | 9 | 20 | 3.3% | NO - prompt version may not ship |

## Per-payload results

| payload | result | retries | violations at final gate |
|---|---|---|---|
| letter-bull-meridian | pass | 0 | - |
| letter-bull-stonebeck | pass | 1 | - |
| letter-comp_gap-meridian | fallback | 2 | G2 |
| letter-comp_gap-stonebeck | fallback | 2 | G4 |
| letter-crash-meridian | pass | 1 | - |
| letter-crash-stonebeck | pass | 1 | - |
| letter-gate_event-meridian | pass | 1 | - |
| letter-gate_event-stonebeck | fallback | 2 | G2, G4 |
| letter-quiet-meridian | pass | 2 | - |
| letter-quiet-stonebeck | fallback | 2 | G4, G5 |
| note-bull-calder-private_credit | pass | 1 | - |
| note-bull-calder-stonebeck | pass | 1 | - |
| note-bull-grimshaw-private_credit | fallback | 2 | G4 |
| note-bull-grimshaw-stonebeck | fallback | 2 | G4 |
| note-comp_gap-calder-private_credit | fallback | 2 | G4 |
| note-comp_gap-calder-stonebeck | fallback | 2 | G4 |
| note-comp_gap-grimshaw-private_credit | fallback | 2 | G4 |
| note-comp_gap-grimshaw-stonebeck | pass | 1 | - |
| note-crash-calder-private_credit | pass | 1 | - |
| note-crash-calder-stonebeck | fallback | 2 | G4 |
| note-crash-grimshaw-private_credit | fallback | 2 | G4 |
| note-crash-grimshaw-stonebeck | fallback | 2 | G4, G5 |
| note-gate_event-calder-private_credit | fallback | 2 | G2, G4 |
| note-gate_event-calder-stonebeck | fallback | 2 | G4 |
| note-gate_event-grimshaw-private_credit | fallback | 2 | G4 |
| note-gate_event-grimshaw-stonebeck | fallback | 2 | G2 |
| note-quiet-calder-private_credit | fallback | 2 | G2, G4 |
| note-quiet-calder-stonebeck | fallback | 2 | G4 |
| note-quiet-grimshaw-private_credit | fallback | 2 | G4 |
| note-quiet-grimshaw-stonebeck | fallback | 2 | G2, G4 |

## Human review items (spec s5: reviewed, not automated)

- **Voice drift**: read a bull and a crash letter per entity against the
  bible's voice register and tics; drift is a prompt-version question.
- **Disagreement quality**: the calder/grimshaw pair on the same subject
  must read the same numbers through different priors and NOT converge.

---

*Not investment advice.*
