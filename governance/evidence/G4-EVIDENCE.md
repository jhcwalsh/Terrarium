# G4-EVIDENCE.md — Gate G4, scored criterion by criterion (WP4.10)

*Assembled at the close of the Step 4 build queue (wp4-01..wp4-10 plus the
retrofit and the wp5-00 metric freeze), and CLOSED at the ship-gate chase.
Every claim below cites a test, an evidence document, or a sealed artifact.
**Verdict: ALL SIX CRITERIA MET — Gate G4 CLOSES 2026-08-02.** Criterion 1
was open at assembly (76.7%) and closed by the chase: fifteen live runs,
pipeline v2 ratified pre-hoc (AM-2026-08-02-004), and the binding pair rule
met at **96.7% / 100.0%** (runs 14/15, identical configuration). An earlier
lucky single pass was refused; the pair rule exists because of it.*

## The six criteria (plan DoD, verbatim in substance)

**1. Tier-1 deterministic at calendar slots; Tier-2 ≥95% first-pass with
retry/fallback exercised.** — **MET** (closed by the chase; assembly-time
state preserved below for the record). Tier-1: deterministic by test
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

## The closing line

The measurement exists. Runs 14 and 15 (`letter@1.4`/`note@1.5`,
`gate-impl/1.0.6`, `author-pipeline/2.0` + `self-check@1.1`) measured
**96.7% and 100.0% first-pass** — two consecutive runs over the frozen
bar at identical configuration, per the binding pair rule
(AM-2026-08-02-004). The full fifteen-run trajectory, every instrument
failure, and the refused lucky pass are in
`fixtures/authoring_regression/manifest.yaml` and the archived evidence
files. **Gate G4 is CLOSED.** Step 4 ends with all four project gates
resolved: G0 closed, G1 evidenced with its named mark_lag limitation, G2
closed with its generator caveat, G4 closed clean.

---

*Not investment advice.*
