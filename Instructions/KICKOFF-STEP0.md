# KICKOFF-STEP0.md — Handing Step 0 to the Code Agent

*The execution wrapper for `STEP0-PLAN.md`. Three parts: (1) what you do before the first session, (2) the `CLAUDE.md` to place in the repo — the agent's standing instructions, (3) the prompts that run the sessions.*

---

## Part 1 — Repo setup checklist (you, ~10 minutes, once)

1. Create a fresh repository `alternate-histories/` (private), default branch `main`, branch protection: PRs required, CI must pass.
2. Copy in, at these exact paths:
   - `STEP0-PLAN.md` (repo root)
   - `schemas/worldspec-v1.0.schema.json` ← from `worldspec/worldspec-v1.0.schema.json`
   - `schemas/example-long-stagflation.worldspec.json` ← from `worldspec/`
   - `schemas/WORLDSPEC.md` ← from `worldspec/`
   - `schemas/world-bible-v1.0.schema.json` ← from `artifact-layer/` (reference-only in Step 0, vendored now so the contract set is complete)
   - `CLAUDE.md` (repo root) ← Part 2 below, verbatim
3. Ensure the agent's environment has Python 3.12 and `uv` available, and **no** `FRED_API_KEY` or other secrets — Step 0 needs none; their absence is a useful guard.
4. Do **not** pre-create any source files, configs, or CI — the plan's WP0.1 owns the scaffold, and an empty start keeps ownership clean.

## Part 2 — `CLAUDE.md` (place at repo root, verbatim)

```markdown
# CLAUDE.md — Operating instructions for this repository

## What this repo is
Step 0 ("lay the rails") of the Alternate Histories Platform: WorldSpec contract,
validator, deterministic toy engine, append-only stores, offline compiler harness,
validation-battery skeleton, CLI. The authoritative task list is STEP0-PLAN.md.
Read it fully before writing any code. The schemas/ directory is the contract:
read-only, vendored truth. If STEP0-PLAN.md and schemas/ ever disagree, schemas/
wins for field definitions and STEP0-PLAN.md wins for process; flag the conflict
in the PR description rather than resolving it silently.

## How to work
- One work package (WP0.x) per branch/PR, in the order given in STEP0-PLAN.md §4.
  Branch naming: wp0x-short-name. Do not start a WP before the previous one is merged,
  except where §4 explicitly allows parallelism.
- Definition of done for every PR: acceptance tests from the WP pass, full suite
  green, ruff and pyright clean, CHANGELOG.md updated, PR description contains
  (a) what was built, (b) deviations from the plan with reasons, (c) anything
  discovered that affects later WPs.
- Tests first where the plan specifies acceptance tests; never weaken a test to
  make it pass; never mark tests skip/xfail without a linked TODO in the PR.
- Determinism is a hard invariant: single-seed PCG64 discipline per STEP0-PLAN.md §1.
  If you find yourself reaching for random, time.time(), or a global RNG — stop.
- The engine must be structurally narrative-blind (NumericWorld projection).
  This is a design guarantee, not a convention; it has its own test.
- No network calls anywhere in tests or CI (pytest-socket enforces). The Anthropic
  adapter exists but is exercised only via the CLI --live flag, never in tests.
- Dependencies: only those named in STEP0-PLAN.md §1. Adding any other dependency
  requires a stated justification in the PR description.

## When the plan is ambiguous
Choose the interpretation that (1) preserves determinism and auditability,
(2) keeps the contract (schemas/) authoritative, (3) is simplest to delete later.
Record the choice in the PR description under "Decisions taken". If the ambiguity
is material (would change an interface another WP depends on), stop and ask
instead of proceeding.

## What not to do
No real market data. No ML training. No UI. No LLM output in any numeric path.
No editing files under schemas/. No silent scope growth — if a nice-to-have
appears, note it in the PR description for the Step-1+ backlog and move on.

## Reporting
End every session with: WP status (done/in-progress/blocked), test count and
coverage on core/, any open questions for the human reviewer, and the exact
command(s) to verify the session's work.
```

## Part 3 — Session prompts

**Session 1 (paste as the opening message):**

> Read `STEP0-PLAN.md` and `CLAUDE.md` in full, then confirm your understanding in five bullets or fewer: the mission, the G0 definition of done, the WP order, the determinism rule, and the narrative-blindness guarantee. Verify the four files exist under `schemas/` — if any are missing, stop and tell me. Then execute **WP0.1** (scaffold, tooling, CI) per the plan, and open the PR.

**Sessions 2–N (template):**

> Continue per `STEP0-PLAN.md`. Previous state: WP0.[x] merged. Execute **WP0.[x+1]**. Before coding, restate the WP's acceptance tests in one line each; after coding, show they pass. Open the PR with the description format from `CLAUDE.md`.

**If a session ends mid-WP:**

> Resume WP0.[x] on branch `wp0[x]-...`. First run the test suite and summarize current state vs the WP's acceptance list, then continue.

**Final session (after WP0.9 merges):**

> Run the full Gate G0 checklist from `STEP0-PLAN.md` §0 end-to-end and produce `G0-EVIDENCE.md`: for each of the seven criteria, the command executed, the observed result, and pass/fail. If all pass, tag `v0.1.0-g0`. If any fail, stop and report — do not patch around a failing gate criterion.

## Part 4 — Your review checklist at each PR (2 minutes each)

- Do the acceptance tests named in the WP actually exist and run in CI (not just locally)?
- Any "Decisions taken" or deviations noted? Do you agree with them?
- Anything flagged for later WPs? Copy it into your notes.
- For WP0.4/0.5 specifically: open the golden-snapshot test and confirm it asserts hashes, not shapes.
- For WP0.6: confirm the chronicle's UPDATE/DELETE tests exercise the trigger *and* the repository layer.
- For WP0.9: read `G0-EVIDENCE.md` yourself before accepting the tag — this document is the first entry in the platform's validation record, and the habit of reading gate evidence starts here.

---

*When G0 is tagged: hand the agent `STEP1-DATA-PLAN.md` (already written) the same way — it assumes this repo's conventions and extends them.*
