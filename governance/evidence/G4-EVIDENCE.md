# G4-EVIDENCE.md — Gate G4, scored criterion by criterion (WP4.10)

*Assembled at the close of the Step 4 build queue (wp4-01..wp4-10 plus the
retrofit and the wp5-00 metric freeze). Every claim below cites a test, an
evidence document, or a sealed artifact. **Verdict up front: G4 does NOT
close today — criterion 1's Tier-2 half is honestly unmet.** Five of six
criteria are evidenced; the gap is named, measured, and has stated next
levers.*

## The six criteria (plan DoD, verbatim in substance)

**1. Tier-1 deterministic at calendar slots; Tier-2 ≥95% first-pass with
retry/fallback exercised.** — **HALF MET.** Tier-1: deterministic by test
(same tape, same words; schedule deterministic under declaration
reordering). Tier-2: the retry/fallback path is exercised and logged
(five live runs, zero fallbacks in the last three, every retry recorded)
— but the first-pass rate is **76.7% against the frozen 95% bar**
(`AUTHORING-REGRESSION.md`; trajectory 3.3% → 76.7% across five runs, gate
lineage `gate-impl/1.0.0→1.0.2`, prompts `letter@1.1`/`note@1.2`).
**Consequence, enforced: live-world Tier-2 authoring is disabled.** Next
levers, recorded in the manifest: few-shot exemplars; a pre-gate
self-check pass. Iterated by version bump with full re-runs, as always.

**2. No artifact in any regression run references a real firm or person, a
future dateline, or a number absent from its payload's claims table.** —
**MET.** Enforced by G1/G3/G4 (blocking); all 30 run-5 recorded artifacts
re-gate clean offline in CI forever
(`tests/test_authoring_regression.py::TestRecordedReplay`); injection
attempts that would breach it are caught (`tests/test_injection.py`).

**3. Live mode runs with sealed reveal; chronicle append-only; replay
reproduces the identical artifact sequence.** — **MET.** t₀ seal with
tamper detection to one mark in one millionth
(`tests/test_live_mode.py::TestSeal`); the information wall is structural
(unrevealed months never enter the object); the chronicle is append-only
at trigger and repository layers (Step 0, retested); replay reproduces
the sequence from the chronicle, never by re-prompting (G9 records:
payload hash, prompt version, model id, gate result, retry count).

**4. AI committee decisions bounded, briefed only on revealed information,
filed with rationales, benchmarked against heuristic ablations.** —
**MET, with the human half deferred.** Bounded (typed contract; off-menu
rejects with the rejection filed), briefed behind the structural wall,
filed (no rationale, no decision; minutes to the wire), benchmarked
against heuristic / random-within-bounds / hold-course on identical
worlds and seeds (`ACTOR-VALIDATION.md`). The **human-cohort benchmark is
deferred by owner decision D-K4-5** — a scope decision on the record, not
a silent gap.

**5. Documented pathology measurements exist, published internally before
any client-facing claim.** — **MET within scope.** Measured and
published: fallback rate 0.20 (action-level fidelity), persona/prompt
sensitivity 0.78, effect sizes structurally chained to their dispersion.
The **too-rational pathology is not measurable without human cohorts**
and is recorded as such — no proxy number. The no-client-facing-claim
rule stands in the evidence verbatim.

**6. The GenAI governance pack is complete.** — **MET.**
`governance/prompt-registry.yaml` (four prompt families, versions, hash
pins, regression links, ship status); injection testing on all payload
paths (authoring + committee; template engine proven single-pass);
output-variance policy (Tier-1 zero by test; Tier-2 measured, never
pretended away); fictional-entity enforcement (B1 screen, version
recorded; G4 closed world); `governance/eu-ai-act-mapping.md` with the
NIST AI RMF scaffold; and the boundary statement below.

## The boundary statement

**No generative output enters the certified numeric path.** Structural,
twice over: the engine consumes a NumericWorld that omits narrative
(Step 0 guard), and `ah/core`, `ah/gen`, `ah/port` never import
`ah/artifacts` — asserted by
`tests/test_artifacts_service.py::TestBoundary` on every CI run since
wp4-01. Generative components read the tape; they cannot write it.

## What closing G4 requires

One thing: a Tier-2 prompt version measuring **≥95% first-pass** on the
frozen 30-payload set. Everything else is evidenced above. When that
measurement exists, this document gains its closing line and the gate
tags; until then Step 4's build is COMPLETE and its gate is OPEN — the
same honest posture as G1's mark_lag and G2's generator caveat.

---

*Not investment advice.*
