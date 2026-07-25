# STEP4-ARTIFACTS-ACTORS-PLAN.md — The Storytellers and the Actors
## Implementation plan for Claude Code · Step 4 (WS-E + WS-F) · runs to Gate G4

**Prerequisite:** Step 3 complete (twin, portfolio, hero funds). **Companion docs to vendor:** `artifact-layer/ARTIFACT-AUTHORING.md`, `artifact-layer/world-bible-v1.0.schema.json`, `artifact-layer/example-bible-credit-winter.json`.

**Mission.** Two different kinds of AI with two different disciplines. The **narrator** (compiler, wire, letters, notes, board packs) is gated on factual consistency — every number from the tape, every entity fictional, nothing ahead of its dateline. The **actors** (human committees, then constrained AI committees) are gated on bounded action sets and validation against human behavior. Neither ever enters the certified numeric path.

### Definition of done (Gate G4)
1. Tier-1 artifacts generate deterministically from the tape at their calendar slots; Tier-2 artifacts pass the consistency gate at **≥95% first-pass**, with the two-retry-then-fallback path exercised and logged.
2. No artifact in any regression run references a real firm or person, a future dateline, or a number absent from its payload's claims table.
3. Live mode runs a full decade with sealed reveal; the chronicle is append-only and replay reproduces the identical artifact sequence.
4. AI committee decisions are bounded, briefed only on revealed information, filed with rationales, and benchmarked against **both** human cohorts and heuristic ablations.
5. Documented pathology measurements exist (too-rational tendency, prompt sensitivity across personas, effect-size inflation) — published internally before any client-facing claim.
6. The GenAI governance pack is complete: prompt versioning, output-variance measurement, injection testing, EU AI Act obligation mapping.

---

## Work packages

**WP4.1 — Artifact service and calendar.** Subscribe to clock/chapter events; `artifact_calendar` in the WorldSpec `temporal_delivery` block declares which types this world emits and when; chronicle entries carry type, dateline, author tier, gate result, payload hash. Renderers per type (wire item, release page, statement, letterhead, board pack) with **watermarking applied in the renderer**, not the style guide, and re-applied on export.

**WP4.2 — Tier-1 templates.** Deterministic, rule-generated from the tape: alerts, morning digest, data-release pages (tables with prior and revision), central bank statements, quarterly statements with **ensemble-derived peer percentiles**, and the **board pack** auto-assembled two world-weeks before each decision window (performance, allocation vs ranges, liquidity position, wire digest, consultant recommendation). Volume lives here; cost is zero.

**WP4.3 — World Bible implementation.** Schema validator with creation checks B1–B5 including **B3 economic consistency** (arcs must be possible in this world's parameters) and the real-entity name screen (GLEIF/SEC, version recorded). Cast binding to Step 3's hero funds so a named GP has numbers behind it.

**WP4.4 — Tier-2 authoring pipeline.** Payload builders (deterministic code, never an LLM) producing P-LETTER and P-NOTE with pre-formatted `checkable_claims_table`; prompt templates T-LETTER and T-NOTE at versioned strings; the consistency gate G1–G9 in order, blocking rules enforced, two retries then Tier-1 fallback; chronicle record on publication.

**WP4.5 — Authoring regression set.** ~30 frozen payloads (bull/crash/gate/big-comp-gap/quiet quarters × entity and house types). Any prompt or model change re-runs the set; reviewed for gate pass-rate, voice drift, and **disagreement quality** (the research-house pair must not converge). Ship gate: ≥95% first-pass.

**WP4.6 — Live mode productionization.** Reveal pointer at wall-clock speed; the three selection rules for which path becomes the tape (random / pre-stated percentile / pinned id) with the choice recorded in provenance; precomputed-reveal as default with sealed hash; chaptered generation behind a flag with **waypoints sealed at t₀**; notification policy (push only regime events, everything else into the digest); information wall tests.

**WP4.7 — Human actors: windows and pre-commitment.** Calendar decision windows plus **event-triggered windows** (spread breach, gating, mark catch-up, collateral call) — because real decisions are not uniformly spaced. The **pre-commitment playbook**: committees write conditional rules at t₀, and adherence-versus-deviation is measured when the trigger fires. Multi-team wargame mode: same world, same seed, independent institutions, comparative scoring.

**WP4.8 — AI committee.** Constrained action set validated against the allowed list; briefing built strictly from revealed information (returns, drawdown, rates, spreads, weights on the marks in view, last N wire items); personas as configuration; rationales filed to the wire; **heuristic ablation always available** as the fallback and as the comparison baseline. Prompt versions and model ids recorded per decision.

**WP4.9 — Actor validation study.** AI committees vs human cohorts on identical worlds and seeds; ablations (heuristic rules, random-within-bounds, hold-course); measure and publish the documented pathologies — excessive rationality relative to human cohorts, persona/prompt sensitivity, effect-size inflation, action-level fidelity. Result written up whichever way it falls; **no client-facing actor claim precedes this evidence**.

**WP4.10 — GenAI governance pack.** Prompt registry with versions and regression sets; output-variance measurement across seeds; prompt-injection testing on all payload paths; fictional-entity enforcement evidence; EU AI Act obligation mapping and NIST AI RMF scaffold; the boundary statement showing generative components never touch certified numerics.

---

## Sequencing, non-goals, pitfalls
**Order:** 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7 → 4.8 → 4.9 → 4.10. Tier-1 first because it transforms the experience at zero marginal cost; the bible before Tier-2 because it is both the continuity database and the safety enforcement point. **Non-goals:** grounded member/consumer agents (research track, post-G4), market-impact channels from actor behavior, chapter-conditioned world adaptation beyond the flagged experiment. **Pitfalls:** authors computing rather than copying numbers (G1 blocks derived arithmetic for exactly this reason); a fictional front page that could screenshot as real (watermark in the renderer, tested on export); fog artifacts that never resolve (G7 blocks the next chapter); persona differences mistaken for insight rather than measured as prompt sensitivity; and the drift where an actor's convenience nudges the world — decisions reshape the institution, never the tape.
