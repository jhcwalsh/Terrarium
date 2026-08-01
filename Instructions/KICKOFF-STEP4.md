# KICKOFF-STEP4.md — Artifacts & Actors Kickoff

*Wrapper for `STEP4-ARTIFACTS-ACTORS-PLAN.md` + `STEP4-amendment-A1.md`, in the
manner of `KICKOFF-STEP0.md`/`KICKOFF-STEP3.md`. Drafted 2026-08-01 at Step 3
close for owner approval; the plan and amendment stay authoritative — this
document sequences them, records what changed between their authorship and
kickoff, and resolves the ambiguities that must not reach a gate evidence pack.
**No Step 4 code exists yet; nothing here starts a build.***

---

## 1. Prerequisites — status at kickoff

| Prerequisite | Status |
|---|---|
| Step 3 complete (twin, portfolio, hero funds) | ✅ Tagged `v0.3.0-g1` (2026-08-01); `G1-EVIDENCE.md` is the record |
| Hero funds for cast binding (WP4.3) | ✅ `ah/port/heroes.py` — named splits reconcile to their parent cohort as an exact identity; naming deliberately left to this step |
| `artifact-layer/world-bible-v1.0.schema.json` | ✅ Vendored at `Instructions/world-bible-v1.0.schema.json` (validates bible_version, world_id, safety, institution, cast, research_houses, media, creation_checks) |
| `artifact-layer/ARTIFACT-AUTHORING.md` | ✅ Vendored at `Instructions/ARTIFACT-AUTHORING.md` (owner-supplied 2026-08-01). **Reconstruction caveat**: rebuilt from the 28 July transcript (v1.0-r); §§1–6 recovered verbatim per its own header. Carries G1–G9, P-LETTER/P-NOTE payload contracts, T-LETTER/T-NOTE v1.0, the regression-set spec, and scheduling defaults |
| `artifact-layer/example-bible-credit-winter.json` | ✅ Vendored (owner-supplied 2026-08-01), same reconstruction provenance. **Verified at kickoff**: validates against the schema with zero errors; cast of 4 (schema minimum, below the stated 8–14 sweet spot — shape demonstration, not a density template) |
| `Instructions/RECONSTRUCTION-NOTES.md` | ✅ Vendored alongside — the provenance record. Known gaps: `creation_checks.warnings` possibly truncated (low consequence); cast size (above). **One real inconsistency carried forward deliberately**: three `relationships[].with` values point at `harborlight-implicit`, which is the institution, not a cast id — verified present at kickoff. The notes recommend closing it as a **B6 creation check** (every `relationships[].with` resolves to a known id, blocking); that lands in the WP4.3 backlog against the schema changelog, not as a silent patch |
| Real-entity name screen source (GLEIF/SEC snapshot) | ❌ Not sourced. Tests run offline, so the screen needs a **vendored snapshot with its version recorded** (the plan requires "version recorded" explicitly) |
| Chronicle + append-only stores | ✅ Step 0 rails; artifact chronicle entries extend the existing discipline |
| 2022 episode pack, revealed-path machinery | ✅ `ah data episode 2022`; reveal/live mode (WP4.6) builds on existing world/run stores |

**Standing caveats carried into every Step 4 decision:**

1. **The G1 honest FAIL travels with the tape.** The 2022 replay fails its
   sealed gate on `mark_lag` (HF −3.1 months, diagnosis on record in
   `G1-EVIDENCE.md`). Step 4 renders the tape; it does not repair it. No
   artifact, template, or actor briefing may smooth, re-lag, or re-time series
   to make the narrative read better — the narrator's discipline is *every
   number from the tape*, including the numbers the tape gets wrong.
2. **The generator caveat from G2 still stands** (regime persistence
   undercalled, drawdowns understated ~2×). Nothing Step 4 produces is
   represented as decision-ready; that remains Step 5's question, after the
   next generator campaign.

## 2. Gate spine and the new boundary

Gate **G4** = the plan's six DoD items: Tier-1 determinism at calendar slots;
Tier-2 ≥95% first-pass with the retry/fallback path exercised; no real
entity / future dateline / unsourced number in any regression run; a full
sealed-reveal decade with replay-identical artifact sequence; bounded,
briefed, filed, benchmarked AI-committee decisions; documented pathology
measurements; and the GenAI governance pack.

**Step 4 introduces the first LLM components in the repo.** The rails, from
the first commit:

- **No LLM output ever enters the numeric path.** The boundary statement
  (WP4.10) is written first, not last, and an import-graph test in the manner
  of the leakage guard proves `ah/port/`, `ah/core/`, `ah/gen/` never import
  the authoring modules.
- **No network in tests.** The WP4.5 regression set runs on recorded
  authoring fixtures; live authoring and live committee calls sit behind
  explicit `--live` flags, exactly like the Step 0 compiler harness and the
  Step 1 connectors.
- **Determinism where the plan demands it.** Tier-1 artifacts and payload
  builders are pure functions of the tape and the calendar (seeded, no clock
  reads); only the Tier-2 *prose* is stochastic, and its gate result, prompt
  version, and payload hash are chronicled so replay reproduces the identical
  artifact sequence (DoD 3).

**Proposed (owner decision D-K4-3): a G4-pre freeze.** Before any prompt
iteration begins, freeze in the amendment-log discipline: the WP4.5
regression-set membership rule, the ≥95% first-pass threshold, and the G1–G9
blocking rules as vendored. Rationale: the consistency gate judges the
narrator the way the battery judges the generator; the project's rule is that
thresholds and the code that judges them are hashed before the judged thing
is tuned. Lighter than a full lock — one amendment entry, one hash — but the
same discipline.

## 3. Build order (one WP per branch)

| # | Branch | Scope | Binding constraints |
|---|---|---|---|
| 1 | `wp4-01-artifact-service` | Calendar/clock subscription; `artifact_calendar` in `temporal_delivery`; chronicle entries (type, dateline, author tier, gate result, payload hash); renderers with **watermark in the renderer**, re-applied on export | Chronicle append-only at both layers, as Step 0; export screenshot test for the watermark |
| 2 | `wp4-02-tier1-templates` | Alerts, morning digest, release pages (prior + revision), CB statements, quarterly statements with ensemble-derived peer percentiles, board pack (T−2 world-weeks) | **Amendment Delta 2 lands here**: capital-call, distribution, coverage-band, forced-sale (with cause and sleeves sold), secondary-discount templates; cashflow events report the **cash account**; forced-sale reads like the distress it is |
| 3 | `wp4-03-world-bible` | Schema validator; creation checks B1–B5 incl. B3 economic consistency; **B6 referential-integrity check** (reconstruction-notes recommendation, recorded against the schema changelog); real-entity screen (vendored snapshot, version recorded); cast binding to hero funds | Entity-screen snapshot still unsourced (D-K4-4); golden test against `example-bible-credit-winter.json` |
| 4 | `wp4-04-tier2-pipeline` | Deterministic payload builders (never an LLM) with `checkable_claims_table`; T-LETTER/T-NOTE versioned prompt strings (`author-prompt/letter@1.0`, `author-prompt/note@1.0`); gate G1–G9 in order, G1–G5+G8 blocking, G6 advisory in v1, two retries then Tier-1 fallback; chronicle record per G9 | Authoring spec is reconstructed text — any blocking-rule ambiguity **halts and asks** (§5) |
| 5 | `wp4-05-regression-set` | ~30 frozen payloads across bull/crash/gate/comp-gap/quiet × entity/house types; re-run on any prompt or model change; review pass-rate, voice drift, disagreement quality | Ship gate ≥95% first-pass; research-house pair must not converge; membership frozen per D-K4-3 if ratified |
| 6 | `wp4-06-live-mode` | Reveal pointer at wall-clock speed; three tape-selection rules recorded in provenance; precomputed-reveal default with sealed hash; chaptered generation behind a flag, waypoints sealed at t₀; notification policy; information-wall tests | Sealed-reveal hash joins the provenance record; wall tests are blocking |
| 7 | `wp4-07-human-actors` | Calendar + event-triggered decision windows (spread breach, gating, mark catch-up, collateral call); pre-commitment playbook with adherence measurement; multi-team wargame | Windows consume Step 3 outputs unchanged; decisions reshape the institution, never the tape |
| 8 | `wp4-08-ai-committee` | Bounded action set validated against the allowed list; briefing strictly from revealed information; personas as configuration; rationales filed to the wire; heuristic ablation as fallback and baseline | Prompt versions + model ids recorded per decision; briefing builder is deterministic code |
| 9 | `wp4-09-actor-validation` | AI vs human cohorts, identical worlds/seeds; ablations (heuristic, random-within-bounds, hold-course); publish the pathologies (too-rational, persona sensitivity, effect-size inflation, action fidelity) | Written up whichever way it falls; **no client-facing actor claim precedes this evidence** |
| 10 | `wp4-10-governance-pack` | Prompt registry + regression sets; output-variance across seeds; injection testing on all payload paths; fictional-entity enforcement evidence; EU AI Act mapping + NIST AI RMF scaffold; the boundary statement | The boundary *test* exists from WP4.1; this WP assembles the evidence |

**Slotted before `wp4-01`:** inspection points **I4** (reported-vs-true toggle
across a drawdown episode, WP3.3 outputs) and **I6** (liquidity inspection,
liquidity-spine §12) — Amendment Delta 6 places them here so the experience
slice never consumes an uninspected output. Diagnostic with teeth: work items
recorded against the relevant register rows before G4 closes. **I5**
(first-run observation) gates M4 and belongs to the experience track.

**Out-of-repo deltas (pending owner decision D-K4-2):** Amendment Deltas 1
(commitment-window UI), 3 (outcome card), 4 (post-game annotations), and 5
(help agent) describe DN-3 experience-layer surfaces. Recommended scoping:
this repo builds the *engine side* those surfaces consume (windows, events,
RunRecord-computable annotations, grounded-corpus content), and the SPA/UI
work tracks DN-3 separately. Delta 4's constraint binds here regardless: both
annotations computable from the RunRecord alone, no new state.

## 4. Kickoff decisions — resolved

All six resolved by the owner, 2026-08-01:

| Id | Decision | Resolution |
|---|---|---|
| D-K4-1 | Artifact-layer docs; B6; Albourne §5 claim | **RESOLVED.** Docs vendored; **B6 ratified** (lands in WP4.3, recorded against the schema changelog). Albourne question closed by inspection: `Instructions/albourne-derived-measures-spec.md` is the **original**, vendored at Step 1 (`a37b175`), sections A–G present — ALB-A–F are its section letters; `RECONSTRUCTION-NOTES.md` §5 is stale on this item and nothing needs recovering |
| D-K4-2 | Repo boundary for the experience deltas | **RESOLVED: engine-side only in this repo.** Owner condition: the UI deltas **must not be lost** — they are registered in `Instructions/experience-deltas-register.md` (created with this resolution), which DN-3 work must consume; the register is the durable record, not this kickoff's prose |
| D-K4-3 | G4-pre freeze | **RATIFIED.** Minted as one amendment-log entry at Step 4 build start, before any prompt tuning; covers regression-set membership rule, the ≥95% first-pass threshold, and the G1–G9 blocking split as vendored |
| D-K4-4 | Real-entity screen source | **RESOLVED (delegated to builder): GLEIF LEI Golden Copy + SEC EDGAR.** GLEIF Level-1 full file (CC0, monthly, versioned by publication date) filtered to a normalized financial-entity name list, plus SEC EDGAR `company_tickers.json`; vendored as a derived fixture with its generation script in `scripts/`, source names, publication dates, and SHA-256 recorded. Refresh: at each Step 4 minor release, cadence stated in the fixture header |
| D-K4-5 | Human cohorts for WP4.7/4.9 | **RESOLVED: no external cohorts yet.** The app is built first; the owner is the first and only test cohort for now, with external cohorts brought in later. Consequence, stated: the WP4.9 validation study **cannot complete** on a one-person cohort — it runs its ablation arms (heuristic, random-within-bounds, hold-course) and pathology measurements now, and the human-cohort arm is deferred with the deferral recorded in the study write-up. The plan's rule is unchanged and now bites harder: **no client-facing actor claim** until the full study exists |
| D-K4-6 | LLM provider | **RESOLVED: Claude** (Anthropic API), Step 0 compiler-harness pattern — recorded fixtures offline, `--live` for real calls, model id + prompt version chronicled per artifact and per decision |

## 5. Halt conditions

- The authoring spec and example bible are **reconstructed text** (v1.0-r).
  Any WP finding them materially ambiguous on a blocking rule — or finding
  content the reconstruction notes' gap register does not explain — **halts
  and asks** rather than interpreting; the notes' own footer requires
  verification before treating anything as a frozen contract. The owner's
  2026-08-01 resolutions (B6 ratified, G4-pre ratified) stand as confirmation
  that the reconstruction is workable; the ambiguity rule above survives that
  confirmation — recovered text still halts on any blocking-rule doubt.
- The **real-entity screen halts** WP4.3's B-check completion until a
  versioned offline snapshot is vendored (D-K4-4). No network at test time is
  non-negotiable.
- **No client-facing actor claim** of any kind before WP4.9's write-up exists
  (the plan's own rule, restated as a halt).
- Any WP finding the vendored authoring spec ambiguous on a blocking rule
  **halts and asks** rather than interpreting — gate rules are the one place
  interpretation is forbidden.

## 6. Housekeeping

- CI coverage gate: extend to the new artifact/actor trees at ≥85% when they
  first appear, in the manner of Step 3's extension.
- The G1 `mark_lag` diagnosis (HY omission; 2021–23-resident stickiness)
  remains queued for the **next generator campaign** alongside the FX block
  and CAPE/regime items; Step 4 has no license to touch it.
- `tier1-synthesis-and-decisions.md` remains missing; nothing in Step 4 names
  it (re-checked at kickoff).
- Step 5 metric freeze obligation (from Step 3's kickoff): if not yet
  discharged, it must not slip past Step 4 — the metrics must be frozen
  before any result they judge exists.

---

*Not investment advice.*
