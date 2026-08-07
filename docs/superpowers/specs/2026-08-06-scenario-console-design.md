# Scenario build console — design

**Date:** 2026-08-06
**Status:** approved by owner (this conversation); implementation not started
**Decisions taken with the owner:** internal QA audience; two WPs — console
first, then prompt fix; dry-run compile with explicit keep.

## What this is

A surface where the owner types a free-text scenario and watches it compile
into a world, stage by stage. It is an **internal QA tool**, a sibling of the
read-only inspection console (`ah/console.py`, port 8799) — not a product
surface, not part of the SU track.

## Why two WPs

The live compile path is currently broken: `prompt_v1.py` describes a
superseded schema generation, so live model output arrives with 38 extra keys
and 6 required fields missing, and every live compile ends in a validator
rejection (diagnosed 2026-08-06 with a throwaway scenario). A watch-it-compile
console over a compiler that can only fail is not worth shipping alone, so the
prompt fix is WP-A and the console WP-B, sequenced.

## WP-A — compiler prompt v2 (`compiler-prompt-v2` branch)

- The v2 prompt **derives its field specification from the vendored schema at
  import time** — required fields, enums, bounds — so prompt and `schemas/`
  cannot drift apart again. The v1 failure mode was a hand-written field list.
- **Envelope fields leave the prompt entirely.** Fields the model was never
  entitled to invent (`spec_version`, `created_at`, provenance stamps,
  `world_id`) are stamped in `postprocess.py` after extraction. This is the
  stashed envelope work (stash: "compiler envelope stamp (postprocess) - not
  part of ER-7"), unstashed and finished.
- Stray keys in model output are **stripped and reported**, never silently
  passed through; missing required fields still reject at the validator as
  they do today.
- `schemas/` stays read-only vendored truth; nothing in it changes.

**Acceptance:** all 50 offline compiler fixtures still pass; one throwaway
live compile ends with zero blocking findings and a constructed WorldSpec;
full gate green.

## WP-B — the build console (`build-console-01` branch)

**Module and port.** `ah/buildconsole.py`, FastAPI (existing dependency),
served on **port 8798**. Deliberately not part of `ah/console.py`: the QA
console's read-only guarantee is enforced by a guard test and stays untouched.
Same server-rendered HTML idiom; its own watermark: "BUILD SURFACE — WRITES
ONLY ON KEEP".

**One page, three states.**

1. **Compose** — textarea for the scenario, compile button, recent attempts
   listed below (read from the console's own jsonl attempt log — its
   permitted cache).
2. **Watching** — the compile runs in a background thread; the page polls via
   plain meta-refresh (~1.5 s, no JS framework) and renders the stage ledger
   as it grows:
   prompt built (size, schema hash) → request sent (model name) → raw text
   received (elapsed, chars) → JSON extracted → envelope stamped → validator
   verdict (per-rule table, clamps highlighted) → WorldSpec constructed
   (digest). A failed stage shows the full raw payload and error inline — a
   rejection is a first-class result, not an error page.
3. **Done** — dry-run result with two actions. **Keep** runs the same
   stamp+store path the CLI uses (optionally triggering an `ah run` with
   seed/n_paths so the world lands fully inspectable) and redirects to the
   world's row on the QA shelf at 8799. **Discard** persists nothing.

**Persistence rule.** Compiling is a dry-run: nothing is written to
`data/ah.db` except through the Keep handler. The attempt log (jsonl under the
console's cache dir) records every attempt, including failures, with raw
payloads — that is the debugging record.

**Error handling.** Network/API failure, malformed JSON, and validator
rejection each terminate the ledger at their stage with evidence preserved in
the attempt log.

**Testing.** Stage-ledger logic is pure functions tested directly; the compile
flow is tested end-to-end against the existing fixture adapter (no network in
tests, per repo rule); a guard test asserts the module's only store-writing
call site is the keep handler.

**Acceptance:** fixture-driven compile shows all stages green and Keep lands
the world on the QA shelf; a deliberately malformed fixture shows a red stage
with the raw payload; full gate green.

## Sequencing and constraints

1. ER-7 merge (`engine-er7-fat-tails`, gate9 in flight) lands first.
2. WP-A, full gate, `--no-ff` merge, push.
3. WP-B, full gate, `--no-ff` merge, push.

No new dependencies. Live compiles need network + API key at runtime only —
never in tests. CLI-echoed strings stay ASCII. The pre-registration lock does
not cover any file this project touches (`prompt_v1.py`, `postprocess.py`,
`buildconsole.py` are not in `hashed_files`) — verified against
`pre-registration.lock` as of 2026-08-06.

## Out of scope (deliberate)

- Player-facing scenario authoring (SU track; needs governance and polish).
- Editing or re-prompting a kept world (the store is append-only).
- Any write path from the QA inspection console.
- SSE/WebSocket streaming — meta-refresh polling is enough for a one-user
  internal tool and keeps the page JS-free.
