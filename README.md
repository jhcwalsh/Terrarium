# Alternate Histories Platform

A scenario-simulation platform for counterfactual macro/market worlds. This
repository contains **Step 0 — "lay the rails"**: the WorldSpec contract, its
validator, a deterministic toy engine, append-only run/chronicle stores, an
offline compiler regression harness, a validation-battery skeleton, and a CLI
that proves the loop `compile → validate → run → record → replay`.

> No real market data, no ML training, no UI, and no LLM in the numeric path.
> Those are later steps. See `STEP0-PLAN.md` for the authoritative task list and
> `schemas/WORLDSPEC.md` for the contract semantics.

## Quickstart

```bash
uv sync                 # create the environment from the lockfile
uv run pytest           # run the test suite (no network; pytest-socket enforces)
uv run ah version       # smoke-test the CLI entry point
```

## Architecture (Step 0)

```
schemas/            vendored, read-only contract (WorldSpec + world-bible + docs)
src/ah/
  core/             worldspec models · validator · toy engine · institution · digest
  store/            SQLite: worlds · run_records · append-only chronicle
  compiler/         compile(text)->dict interface · fixture + anthropic adapters
  battery/          stylized-fact panel · thresholds · report  (pandas allowed here)
  cli.py            the `ah` command
  presets/          preset worlds as WorldSpec JSON
tests/              mirrors src/ + test_g0_end_to_end.py
fixtures/compiler/  50 scenario→world recorded pairs
governance/         model inventory · decision register · genai track
data/               gitignored; ah.db lives here
```

## Gate G0 checklist

The definition of done lives in `STEP0-PLAN.md §0`. Each criterion becomes a CI
check; `tests/test_g0_end_to_end.py` executes the full list programmatically, and
`G0-EVIDENCE.md` (produced at gate time) records the command, result, and pass/fail
for each of the seven criteria.

## Determinism

All randomness flows from a single integer seed through
`numpy.random.Generator(PCG64(seed))`. No global RNG, no `random`, no time-based
defaults. Digests are canonical-JSON SHA-256 over the output path arrays.
