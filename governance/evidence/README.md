# governance/evidence/ — the frozen G2 evidence record (WP2R.8)

These are **archival snapshots**, taken at Step 2R consolidation, of the
documents the G2 gate decision rests on. The living documents remain at the
repo root — a later campaign may regenerate those; **these copies do not
change**. Any divergence between a root document and its snapshot here means
the root document has moved on since the gate, not that either is wrong.

Snapshots are copies, not moves, deliberately: sealed files
(`pre-registration.yaml`, `src/ah/eval/g2.py`, `src/ah/eval/prereg.py`,
`src/ah/eval/negative_controls.py` among others) cite `G2-EVIDENCE.md` and
`ABLATION.md` by name, and moving the targets would strand citations inside
files that cannot be edited without amendments.

| Snapshot | sha256 | What it is |
| --- | --- | --- |
| `G2-EVIDENCE.md` | `83645ca04217d1c91e8ee6e2d02a445e03bffd6e8e83fd89283e966bc8d9d2b0` | The G2 gate evidence: disclosures, verdict (PROMOTE `hier-flow-v1`), clause arithmetic, severe test, limitations |
| `ABLATION.md` | `684871291cc25cfc3daf7a6c5644ea2e671b68b0695e1835022f1f227b05cf31` | The 18-cell multi-seed ablation tables (systems A–E) |
| `ablation.json` | `23257085eba7473f85593e460728bb693f88272caa540f28550054099cbdb0cc` | The machine-readable grid behind `ABLATION.md` |

Archived at Step 2R from the `v0.2.0-g2` state of the root documents
(merge `02ed4cc`); the archiving commit is this file's own first commit.

**The negative-control report named by STEP2R-CONSOLIDATION-PLAN §WP2R.8 does
not exist as a standalone document and never did** — the plan names an
artifact that was never emitted (the RFR-77/-78 defect class: a sealed or
planning document asserting something nothing produced). The negative-control
*results* live in `G2-EVIDENCE.md` §4 (snapshotted above) and are continuously
asserted by `tests/test_negative_controls.py`; the absence is recorded here
rather than a report being reconstructed after the fact.
