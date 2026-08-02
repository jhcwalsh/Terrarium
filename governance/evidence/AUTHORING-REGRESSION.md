# AUTHORING-REGRESSION.md — the WP4.5 set, measured

Set `authoring-regression-1.0` (30 payloads); model `claude-sonnet-5`;
prompts author-prompt/letter@1.1 / author-prompt/note@1.2; gate-impl/1.0.2; run asof 2026-08-02 (LIVE).
Ship gate (FROZEN, AM-2026-08-02-002): first-pass gate rate >= 95%.

| first-pass | pass after retry | fallback | first-pass rate | ships |
|---|---|---|---|---|
| 23/30 | 7 | 0 | 76.7% | NO - prompt version may not ship |

## Per-payload results

| payload | result | retries | violations at final gate |
|---|---|---|---|
| letter-bull-meridian | pass | 0 | - |
| letter-bull-stonebeck | pass | 1 | - |
| letter-comp_gap-meridian | pass | 0 | - |
| letter-comp_gap-stonebeck | pass | 1 | - |
| letter-crash-meridian | pass | 0 | - |
| letter-crash-stonebeck | pass | 0 | - |
| letter-gate_event-meridian | pass | 0 | - |
| letter-gate_event-stonebeck | pass | 0 | - |
| letter-quiet-meridian | pass | 0 | - |
| letter-quiet-stonebeck | pass | 1 | - |
| note-bull-calder-private_credit | pass | 0 | - |
| note-bull-calder-stonebeck | pass | 0 | - |
| note-bull-grimshaw-private_credit | pass | 1 | - |
| note-bull-grimshaw-stonebeck | pass | 0 | - |
| note-comp_gap-calder-private_credit | pass | 1 | - |
| note-comp_gap-calder-stonebeck | pass | 0 | - |
| note-comp_gap-grimshaw-private_credit | pass | 0 | - |
| note-comp_gap-grimshaw-stonebeck | pass | 0 | - |
| note-crash-calder-private_credit | pass | 0 | - |
| note-crash-calder-stonebeck | pass | 0 | - |
| note-crash-grimshaw-private_credit | pass | 2 | - |
| note-crash-grimshaw-stonebeck | pass | 0 | - |
| note-gate_event-calder-private_credit | pass | 1 | - |
| note-gate_event-calder-stonebeck | pass | 0 | - |
| note-gate_event-grimshaw-private_credit | pass | 0 | - |
| note-gate_event-grimshaw-stonebeck | pass | 0 | - |
| note-quiet-calder-private_credit | pass | 0 | - |
| note-quiet-calder-stonebeck | pass | 0 | - |
| note-quiet-grimshaw-private_credit | pass | 0 | - |
| note-quiet-grimshaw-stonebeck | pass | 0 | - |

## Human review items (spec s5: reviewed, not automated)

- **Voice drift**: read a bull and a crash letter per entity against the
  bible's voice register and tics; drift is a prompt-version question.
- **Disagreement quality**: the calder/grimshaw pair on the same subject
  must read the same numbers through different priors and NOT converge.

---

*Not investment advice.*
