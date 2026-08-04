# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The **Alternate Histories Platform** — a scenario-simulation system for counterfactual
macro/market worlds. It is built in numbered steps, each with its own authoritative plan
and a gate that must be evidenced before the next step starts.

| Step | Scope | State |
|---|---|---|
| 0 | Rails: WorldSpec contract, validator, deterministic toy engine, append-only stores, offline compiler harness, battery skeleton, CLI | ✅ G0, tagged `v0.1.0-g0` · `G0-EVIDENCE.md` |
| 1 | Data layer: manifest/catalog/vintages, connectors, intake+schemas, QC, splice, derive, de-smoothing, episodes, reports, refresh | ✅ tagged `v0.2.0` |
| 2 | Generator layer: bootstrap benchmark, 4-layer hierarchical generator, validated battery, sealed pre-registration, G2 decision | ✅ **G2: PROMOTE `hier-flow-v1`**, tagged `v0.2.0-g2` · `G2-EVIDENCE.md` |
| 2R | Consolidation: contracts frozen, vintage handoff | ✅ tagged `v0.3.0-contracts` · `CONSOLIDATION-EVIDENCE.md` |
| 3 | Translation layer: sleeve/vehicle state, factor→sleeve mappings, cashflow tiers, the institutional twin | ⚠️ **WP3.1–3.11 shipped; G1-completion is an honest FAIL** (`G1-EVIDENCE.md`), tagged `v0.3.0-g1`. WP3.12 correctly deferred (ALB-C never arrived). **G3 itself was never taken.** |
| 4 | Artifacts, actors, live mode, GenAI governance | ✅ **G4 CLOSED**, tagged `v0.4.0-g4` · `governance/evidence/G4-EVIDENCE.md` |
| 5 | Decision evaluation: scorecard, re-coning, tournament, density pilot, walk-forward | ✅ complete. **The one-shot holdout was SPENT at WP5.6** · `RESEARCH-EVIDENCE.md` |
| SU | Product surface: world bundle, session service, the playable app | 🔄 **the live track.** `su-eng-01/02` + `su-app-01…05` merged; `Instructions/KICKOFF-PRODUCT-SU.md` |

**Read the state column before planning.** Two facts are easy to get wrong and both matter:
Step 3 reached its G1-completion gate with a **FAIL** (named limitations, tier 1 beating
tier 0) and G3 was never closed, yet Steps 4 and 5 proceeded — so "Step 3 is done" is not
true, and the translation layer ships with a recorded failure against the 2022 episode.
And the **holdout is gone**: declined at G2 on purpose (`S2-HOLDOUT-NOT-SPENT`), then spent
at WP5.6. There is no held-out data left to appeal to.

**Standing caveat, carried into every decision:** `hier-flow-v1` beats the benchmark on the
sealed criterion and is **not a convincing model of history** — regime persistence
undercalled, drawdowns understated ~2×, the decade tier 73% structurally unavailable
(`G2-EVIDENCE.md` §7–8). Nothing built on it is decision-ready.

**Plans are authoritative.** `STEP0-PLAN.md` and `STEP1-DATA-PLAN.md` sit at the repo root;
every other plan, amendment and KICKOFF wrapper lives in `Instructions/` (Steps 2, 2R, 3, 4,
5 plus `KICKOFF-PRODUCT-SU.md` and the `plain-english-step*.md` companions). Read the
relevant plan fully before writing code for that step. `schemas/` is the contract:
**read-only vendored truth** — never edit it. If a plan and `schemas/` disagree, `schemas/`
wins for field definitions and the plan wins for process; flag the conflict rather than
resolving it silently.

Plans have **halt conditions** (missing companion documents). Honor them — halt and request
the document rather than reconstructing a normative spec from memory. Step 2's `DN-1.1` halt
condition is discharged (vendored at `Instructions/DN1.1-multiyear-generator-design-note.md`).
`docs/tier1-synthesis-and-decisions.md`, named by Step 2's vendoring list, **is still missing**
— not itself a halt condition, but re-check before relying on it.

## Commands

```bash
uv sync --dev                      # env from the lockfile (Python 3.12 pinned)

uv run pytest                      # full suite (no network; pytest-socket enforces)
uv run pytest tests/test_engine.py::test_golden_snapshot   # a single test
uv run pytest -k desmooth -q                                # by keyword

uv run ruff check . --fix          # lint
uv run ruff format .               # format
uv run pyright                     # types (basic mode)

# the CI gate, verbatim (~26 minutes — run it in the background, read the log):
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90
uv run python -m ah.battery.report # validation battery on the stagflation preset
```

**CLI** (`ah`):

```bash
uv run ah world build --preset stagflation   # compile/preset -> validate -> stamp -> store
uv run ah run --paths 1000 && uv run ah replay   # replay must print MATCH (bit-identical)
uv run ah verify | ah battery | ah chronicle
uv run ah inspect [RUN_ID] --out page.html   # static figure page, regenerates + verifies
uv run ah bundle [RUN_ID] --out world.bundle.gz   # the app's world bundle (su-eng-01)
uv run ah credibility --preset stagflation --preset goldilocks --out credibility.html

uv run ah data refresh --live                # REAL fetch via connectors (needs network + FRED_API_KEY)
uv run ah data refresh --fixtures <dir> --asof YYYY-MM-DD   # offline/deterministic
uv run ah data status | ah data asof DATE | ah data episode 2022
uv run ah data intake validate <file> --schema albourne_pm_returns

uv run ah exp list | ah exp show <id> | ah exp diff <a> <b>
```

**The playable app** (`app/`, per PD-1 it lives in this repo):

```bash
uv run uvicorn ah.serve:app --port 8787   # the session service — NOTE THE PORT
cd app && npm run dev                      # vite on 5173, proxies /sessions -> 8787
cd app && npm run typecheck && npm run test && npm run build
```

**Regenerating committed fixtures/artifacts** (all under `scripts/`, all deterministic):
`gen_fixtures.py` (50 compiler fixtures), `gen_presets.py` (4 preset worlds),
`gen_data_fixtures.py` + `gen_intake_fixtures.py` (connector/intake fixtures),
`download_data.py` (live download + validate + summary), `build_artifact.py` (data visual).
`app/fixtures/toy.bundle.gz` is a committed bundle both suites verify — rebuild it with
`ah bundle` whenever the engine or the bundle contract changes.

## Architecture

Dependencies point **downward only**: `port`/`gen`/`eval`/`artifacts` → `data` → `core`.

**`ah/core/` — the numeric core (Step 0).** `worldspec.py` mirrors the JSON Schema in
pydantic; `loader.py` validates jsonschema-first then pydantic (a property test asserts the
two agree). `validator.py` implements V1–V12 (bounds clamps driven from the schema itself;
V10/V11/V12 block). `engine.py` is the deterministic `toy-v0` engine; `institution.py` runs
sleeves/decisions over its paths; `sleevestate.py` carries the Step-3 state contract;
`digest.py` gives canonical JSON + SHA-256 over float64 tensors. **No pandas in `core/`.**

**`ah/store/` (Step 0)** — SQLite for worlds / RunRecords / chronicle / sessions /
leaderboard. `worlds.save` refuses edits to engine-consumed fields under an existing
`world_id`; the chronicle is append-only at *both* the trigger and repository layers.
`verify_run` recomputes a run's digest from stored inputs — the anchor behind `ah replay`.

**`ah/data/` (Step 1)** — `requirements.yaml` is the single source of truth for required
series. `catalog.py` is a DuckDB catalog over an **immutable Parquet vintage store**
(`(date, value, series_id, vintage)`); re-writing a (vintage, series) raises, the `current`
pointer is append-only and **advances only if QC passes**, and `as_of` reads resolve through
pointer history. Connectors split `fetch()` (network, untested) from `parse()` (pure, golden-
tested). `qc.py` quarantines a vintage on any enforce-level failure. `splice.py` extends series
backward with `is_proxy` flags and never overwrites actuals.

**`ah/gen/` + `ah/eval/` (Step 2)** — `gen/registry.py` resolves a WorldSpec
`engine_defaults.generator_id` to a generator; `gen/base.py` defines the `Generator` protocol
and the `Ensemble` container. `splits.py` + `eval/g2.py` implement the leakage guard.
`eval/` also carries the sealed judging code: `prereg.py`, `battery.py`, `ablation.py`,
`negative_controls.py`, `decision_metrics.py`, `walkforward.py`, `g3seal.py`, `g5seal.py`.

**`ah/port/` (Step 3) — the translation layer, and the real institutional twin.**
`sleeves.py`/`vehicles.py` carry sleeve and vehicle state; `mapping.py` is factor→sleeve;
`cashflow_tier0.py`/`cashflow_tier1.py` are the commitment/call/distribution models;
`portfolio.py` and `twin.py` are the institution with an actual cash account; `smoothing.py`,
`cohort.py`, `heroes.py`, `proxy.py`, `engine.py` support them. **This is what the play
surface should consume** — `ah/pacing.py` is a display-only toy ledger, not a substitute.

**`ah/artifacts/` (Step 4)** — tier-1 deterministic templates (`templates.py`, `render.py`),
tier-2 authoring (`author.py`, `prompts.py`, `gate.py`, `validation.py`), the world bible,
calendars, committee, live mode. No LLM output ever enters the numeric path.

**The product surface (SU track)** — `ah/bundle.py` builds the world bundle (contract
`world-bundle-0.3`, <1MB gz, mtime=0); `ah/feed.py` generates the in-timeline wire;
`ah/serve.py` is the FastAPI session service and the **authority for anything that scores**;
`ah/credibility.py` is the admin console; `app/` is the React/TS player.

## Hard invariants (each has a test; do not weaken)

- **Determinism.** All randomness flows from one integer seed through
  `numpy.random.Generator(PCG64(seed))`. No global RNG, no `random`, no time-based defaults.
  Ensemble seeds are `base_seed + 7919*k`.
- **Narrative-blindness.** The engine consumes a `NumericWorld` projection that structurally
  omits `narrative`. A test scans `engine.py`/`institution.py` for narrative *field access*.
  The validator may read narrative (V7/V8); display surfaces may too.
- **No network in tests or CI** (`pytest-socket`, `--disable-socket` in `addopts`).
- **Leakage guard.** The holdout is reachable only with a `FinalEvaluationToken` minted
  *solely* in `ah/eval/g2.py`; an import-graph test proves no `ah/gen/` module imports it.
  `DataAccess.train_val()` is the only reference/normalization surface. **The holdout has now
  been spent** (WP5.6) — there is nothing left to hold back, which raises rather than lowers
  the bar on not fitting to it retrospectively.
- **Pre-registration seal.** Thresholds *and the code that judges them* are hashed together
  before any training run; amendments go through the machine-checked log. `hashed_files`
  covers `battery/report.py`, `battery/stylized.py`, `battery/thresholds.yaml`,
  `data/derive.py`, `data/splice.py`, `eval/*`, `factors.py`, `splits.py`, `strategies.py`.
  **Check the lock before editing any of those.** `ah/core/engine.py` is NOT in it.
- **Store immutability.** Vintages, RunRecords, and the chronicle are append-only.
- **The server is the authority for value and scoring** (DN-3 W5). The app may mirror target
  *weights* (simple bookkeeping); it must never compute value or alpha client-side.

## Working conventions

- **One work package per branch**, in plan order; branch `wpN-MM-short-name`; merge `--no-ff`
  into `main` only when the full gate is green, then plain-push to `origin`. History was
  rewritten once to scrub a secret — **check with the user before any force-push.**
- **Definition of done for every WP:** the plan's acceptance tests pass, full suite green,
  ruff + pyright clean, `CHANGELOG.md` updated, and the commit body states (a) what was built,
  (b) deviations with reasons, (c) anything discovered that affects later WPs.
- **Read the gate log as data.** Run it in the background to a file, then read the `EXIT:`
  line and the pass count before claiming anything. Never chain a merge onto a `tail`.
- Never weaken a test to make it pass; never skip/xfail without a linked TODO. If a test you
  wrote to catch a defect starts failing because the defect is fixed, **invert it** and keep
  the history in the docstring — do not delete it.
- Dependencies: only those named in the step's plan §1. Adding one needs a stated justification.
- When a plan is ambiguous, choose the interpretation that preserves determinism and
  auditability, keeps `schemas/` authoritative, and is simplest to delete later — then record
  the choice. If the ambiguity would change an interface another WP depends on, stop and ask.
- **`docs/engine-realism-register.md`** records places where the toy engine is faithful to its
  plan but not to an allocator's expectations. ER-1 and ER-4 are closed; ER-2 (no meeting
  calendar / 25bp quantisation), ER-3 (the play surface does not use `ah/port/`), and ER-5
  (crisis is a rectangular block; equity ACF 0.364) are open. Each entry says what a fix
  invalidates. **These are release events and the owner's call, not incidental cleanups.**

## Environment gotchas (learned the hard way)

- **The session service listens on 8787**, not 8000 — `app/vite.config.ts` proxies `/sessions`
  there. Checking 8000 will tell you it is down when it is not. After changing `ah/serve.py`,
  kill the listener and restart, or live checks silently exercise stale code (`pkill` does not
  work on Windows; use `Get-NetTCPConnection -LocalPort 8787` → `Stop-Process`).
- **`generator_id` is pinned by an enum in `schemas/`** and cannot gain new values. When the
  toy engine's numbers change, bump `TOY_ENGINE_VERSION` (stamped on every RunRecord as
  `resolved_engine.generator_version`) and move the presets to a new `world_id` block, so
  scores from two engines cannot share a leaderboard row. `decision_alpha_version` names the
  alpha *definition* and lives inside the seal — do not bump it for an engine change.
- `src/ah/cli.py` and `src/ah/data/cli.py` **must not** use `from __future__ import annotations`
  — Typer resolves parameter hints at runtime and it breaks them.
- CLI-echoed strings stay **ASCII** (Windows console is cp1252; `→` crashes it). Markdown files
  may use Unicode freely.
- pandas/numpy/torch stub noise is silenced per-package via pyright `executionEnvironments`
  for `src/ah/{data,gen,eval}` only — the rest of the tree keeps full basic-mode strictness.
- `data/` and `experiments/` are gitignored; `.env` is gitignored and must stay untracked.
- **Fixtures are synthetic but format-faithful** (no network at build time). Real-world quirks
  they can't capture: FRED serves only ~3 years of `BAMLH0A0HYM2` (ICE licensing — the Baa−Aaa
  splice proxy covers it), and Shiller's free endpoint is a periodic snapshot (staleness warns).
- L1/L2 run on numpyro+JAX, which ships native Windows **CPU** wheels and is verified working
  here. WSL2 (not installed) or another Linux/GPU host is only relevant for L3 training.
