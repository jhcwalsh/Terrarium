# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The **Alternate Histories Platform** — a scenario-simulation system for counterfactual
macro/market worlds. It is built in numbered steps, each with its own authoritative plan
and a gate that must be evidenced before the next step starts.

| Step | Scope | State |
|---|---|---|
| 0 | Rails: WorldSpec contract, validator, deterministic toy engine, append-only stores, offline compiler harness, battery skeleton, CLI | ✅ Gate G0 tagged `v0.1.0-g0` |
| 1 | Data layer: manifest/catalog/vintages, connectors, intake+schemas, QC, splice, derive, de-smoothing, episodes, reports, refresh | ✅ tagged `v0.2.0` |
| 2 | Generator layer: bootstrap benchmark, 4-layer hierarchical generator, validated battery, sealed pre-registration, G2 decision | 🔄 WP2.1 merged |

**Plans are authoritative.** `STEP0-PLAN.md` and `STEP1-DATA-PLAN.md` sit at the repo root;
all plans (plus `STEP2-GENERATOR-PLAN.md` and the KICKOFF wrapper) live in `Instructions/`.
Read the relevant plan fully before writing code for that step. `schemas/` is the contract:
**read-only vendored truth** — never edit it. If a plan and `schemas/` disagree, `schemas/`
wins for field definitions and the plan wins for process; flag the conflict rather than
resolving it silently.

Plans have **halt conditions** (missing companion documents). Honor them — halt and request
the document rather than reconstructing a normative spec from memory. Step 2's WP2.5+ halt
condition on `DN-1.1` is discharged: it is vendored (owner-approved) at
`Instructions/DN1.1-multiyear-generator-design-note.md`, and `ah/eval/reference.py` already
cites it as normative. `tier1-synthesis-and-decisions.md`, named by the plan's vendoring
list, is still missing from `docs/` — it is not itself a halt condition, but its absence
should be re-checked before it is next needed.

## Commands

```bash
uv sync --dev                      # env from the lockfile (Python 3.12 pinned)

uv run pytest                      # full suite (no network; pytest-socket enforces)
uv run pytest tests/test_engine.py::test_golden_snapshot   # a single test
uv run pytest -k desmooth -q                                # by keyword

uv run ruff check . --fix          # lint
uv run ruff format .               # format
uv run pyright                     # types (basic mode)

# the CI gate, verbatim:
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90
uv run python -m ah.battery.report # validation battery on the stagflation preset
```

**CLI** (`ah`, three sub-apps):

```bash
uv run ah world build --preset stagflation   # compile/preset -> validate -> stamp -> store
uv run ah run --paths 1000 && uv run ah replay   # replay must print MATCH (bit-identical)
uv run ah verify | ah battery | ah chronicle

uv run ah data refresh --live                # REAL fetch via connectors (needs network + FRED_API_KEY)
uv run ah data refresh --fixtures <dir> --asof YYYY-MM-DD   # offline/deterministic
uv run ah data status | ah data asof DATE | ah data episode 2022
uv run ah data intake validate <file> --schema albourne_pm_returns

uv run ah exp list | ah exp show <id> | ah exp diff <a> <b>
```

**Regenerating committed fixtures/artifacts** (all under `scripts/`, all deterministic):
`gen_fixtures.py` (50 compiler fixtures), `gen_presets.py` (4 preset worlds),
`gen_data_fixtures.py` + `gen_intake_fixtures.py` (connector/intake fixtures),
`download_data.py` (live download + validate + summary), `build_artifact.py` (data visual).

## Architecture

Three layers, added one step at a time. Dependencies point **downward only**:
`gen`/`eval` → `data` → `core`.

**`ah/core/` — the numeric core (Step 0).** `worldspec.py` mirrors the JSON Schema in
pydantic; `loader.py` validates jsonschema-first then pydantic (a property test asserts the
two agree). `validator.py` implements V1–V12 (bounds clamps driven from the schema itself;
V10/V11/V12 block). `engine.py` is the deterministic `toy-v0` engine; `institution.py` runs
sleeves/decisions over its paths; `digest.py` gives canonical JSON + SHA-256 over float64
tensors. **No pandas in `core/`.**

**`ah/store/` (Step 0)** — SQLite for worlds / RunRecords / chronicle. `worlds.save` refuses
edits to engine-consumed fields under an existing `world_id`; the chronicle is append-only at
*both* the trigger and repository layers. `verify_run` recomputes a run's digest from stored
inputs — that is the reproducibility anchor behind `ah replay`.

**`ah/data/` (Step 1)** — `requirements.yaml` is the single source of truth for required
series. `catalog.py` is a DuckDB catalog over an **immutable Parquet vintage store**
(`(date, value, series_id, vintage)`); re-writing a (vintage, series) raises, the `current`
pointer is append-only and **advances only if QC passes**, and `as_of` reads resolve through
pointer history. Connectors split `fetch()` (network, untested) from `parse()` (pure, golden-
tested). `qc.py` quarantines a vintage on any enforce-level failure. `splice.py` extends series
backward with `is_proxy` flags and never overwrites actuals. `derive.py`, `desmooth.py`,
`episode.py`, `reports.py`, `refresh.py` build on top; `cli.py` exposes `ah data`.

**`ah/gen/` + `ah/eval/` (Step 2)** — `gen/registry.py` resolves a WorldSpec
`engine_defaults.generator_id` to a generator; `gen/base.py` defines the `Generator` protocol
and the `Ensemble` container (whose metadata pins generator/checkpoint/config/vintage/seed).
`splits.py` + `eval/g2.py` implement the leakage guard (below).

## Hard invariants (each has a test; do not weaken)

- **Determinism.** All randomness flows from one integer seed through
  `numpy.random.Generator(PCG64(seed))`. No global RNG, no `random`, no time-based defaults.
  If you reach for one of those — stop. Ensemble seeds are `base_seed + 7919*k`.
- **Narrative-blindness.** The engine consumes a `NumericWorld` projection that structurally
  omits `narrative`. A test scans `engine.py`/`institution.py` for narrative *field access*
  (mentioning the word in a docstring is fine). The validator may read narrative (V7/V8).
- **No network in tests or CI** (`pytest-socket`, `--disable-socket` in `addopts`). The
  Anthropic compiler and live connectors are exercised only via explicit flags (`--live`).
- **Leakage guard (Step 2).** The holdout is reachable only with a `FinalEvaluationToken`
  minted *solely* in `ah/eval/g2.py`; an import-graph test proves no `ah/gen/` module imports
  it. `DataAccess.train_val()` is the only reference/normalization surface. Reference stats
  and normalization are train+validation only, forever.
- **Pre-registration seal (Step 2).** Thresholds *and the code that judges them* are hashed
  together before any training run; amendments go through the machine-checked log.
- **Store immutability.** Vintages, RunRecords, and the chronicle are append-only.

## Working conventions

- **One work package per branch**, in plan order; branch `wpN-MM-short-name`; merge `--no-ff`
  into `main` only when the full gate is green. There is a remote (`origin`), but history was
  rewritten once to scrub a secret — check with the user before any force-push.
- **Definition of done for every WP:** the plan's acceptance tests pass, full suite green,
  ruff + pyright clean, `CHANGELOG.md` updated, and the commit body states (a) what was built,
  (b) deviations with reasons, (c) anything discovered that affects later WPs.
- Never weaken a test to make it pass; never skip/xfail without a linked TODO.
- Dependencies: only those named in the step's plan §1. Adding one needs a stated justification.
- When a plan is ambiguous, choose the interpretation that preserves determinism and
  auditability, keeps `schemas/` authoritative, and is simplest to delete later — then record
  the choice. If the ambiguity would change an interface another WP depends on, stop and ask.
- Not in scope until their step: factor→strategy mappings, cashflow/TA calibration, the
  institutional twin (Step 3); artifacts/world-bible/LLM content (Step 4). No LLM output ever
  enters the numeric path.

## Environment gotchas (learned the hard way)

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
- L1/L2 (Step 2) run on numpyro+JAX. JAX ships native Windows **CPU** wheels (verified:
  jax 0.11 + numpyro 0.21 install, import, and NUTS-sample correctly on this machine), and
  L1/L2 are CPU workloads by plan — no WSL2 needed for them. WSL2 (not currently installed)
  or another Linux/GPU host only becomes relevant for L3 training (WP2.8+), where GPU is
  assumed.
