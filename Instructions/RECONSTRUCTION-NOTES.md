# artifact-layer — Reconstruction Notes

*1 August 2026 · Covers `ARTIFACT-AUTHORING.md`, `world-bible-v1.0.schema.json`, `example-bible-credit-winter.json`.*

All three files were authored in the 28 July session and vendored to Claude Code as Step 4 companions, but were never persisted to the project repository. They have been rebuilt from the session transcript. Read this note before freezing anything against them.

---

## 1. Provenance by file

| File | Recovery | Notes |
|---|---|---|
| `ARTIFACT-AUTHORING.md` | §§1–6 recovered verbatim | Complete document as originally written. Only addition is the reconstruction-status block at the top |
| `world-bible-v1.0.schema.json` | Recovered verbatim, all blocks | Header, `safety`, `institution`, `cast`, `research_houses`, `media`, `creation_checks`. Validates as Draft 2020-12 |
| `example-bible-credit-winter.json` | Recovered verbatim | Validates against the schema with zero errors |

Nothing was invented, extended, or silently corrected. Where the transcript was truncated, the gap is recorded below rather than filled.

## 2. Known gaps

**2.1 — `creation_checks.warnings` may be incomplete.** The transcript truncates inside the first B3 warning in the example bible. One warning is reproduced; if the original carried a second, it is lost. Low consequence — the warnings array is illustrative, not load-bearing.

**2.2 — Cast size.** The example bible contains four cast entities (Meridian, Stonebeck, Kestrel, Vessey). This satisfies `minItems: 4` but sits below the schema's own stated sweet spot of 8–14. It is possible the original example carried more entities and the transcript captured only four; equally possible it was deliberately minimal. Treat the example as a shape demonstration, not a template for cast density.

## 3. One real inconsistency, carried forward unfixed

Three `relationships[].with` values in the example bible point at `harborlight-implicit`, which is **not a cast id** — Harborlight is the `institution`, which lives outside the `cast` array. The schema describes `with` as "cast id" but does not enforce referential integrity, so the instance validates anyway.

Two ways to close it, neither applied here because both are contract changes rather than reconstruction:

- Widen the `with` description to "cast id or the literal `institution`", and have the bible validator resolve against `cast ∪ {institution}`; or
- Add a B6 creation check: every `relationships[].with` resolves to a known id, blocking on failure.

The second is the better fit with the B-check discipline and is the recommendation. It belongs in the WP4.3 backlog, recorded against the schema changelog rather than patched in place.

## 4. Where these bind

| File | Binds to |
|---|---|
| `world-bible-v1.0.schema.json` | WP4.3 (bible implementation, checks B1–B5, cast binding to Step 3 hero funds) |
| `ARTIFACT-AUTHORING.md` | WP4.4 (Tier-2 authoring pipeline); gate G4 definition-of-done items 1 and 2 |
| Both | STEP4 plan "companion docs to vendor" list |

Neither is on the M4 critical path — Phase A ships Tier-1 artifacts only (WP4.1/4.2), and Tier-2 is an M7/G4 object. The reason to hold them now is that the Step 4 plan names them as prerequisites and the G4 acceptance criteria are stated against them.

## 5. Still stranded

For the register, the artifact-layer trio is now recovered. Outstanding from the same problem set:

- WorldSpec schema and specification
- Albourne derived-measures specification (highest priority — both previously reconstructed documents cite ALB-A through ALB-F as though it exists in the repo)
- Data requirements register v1.1
- Generator output variable enumeration
- Step plans 0–5 and Step 2R, WP2.1b, WP1.12
- Design notes DN-1.1, DN-2, DN-3, DN-4, DN-5 (DN-1 exists in the project as a PDF only)
- MPP Amendment A1 and the Step 3/4/5 amendments

---

*Reconstructed content. Verify against the original session transcript before treating any of it as a frozen contract.*
