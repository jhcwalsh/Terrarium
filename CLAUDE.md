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
