# STEP0-PLAN.md — Lay the Rails
## Implementation plan for Claude Code · Alternate Histories Platform · Step 0 / Gate G0

**How to use this file:** place it at the repo root of a fresh repository together with the `schemas/` directory (four files listed in §8). Work through the work packages in order (WP0.1 → WP0.9), one PR per work package, keeping tests green at every merge. Everything needed is in this file; no external context is assumed.

---

## 0. Mission

Build the *rails* of a scenario-simulation platform: a versioned world contract (WorldSpec), its validator, a deterministic toy engine, append-only run/chronicle records, a compiler interface with a regression harness, a validation-battery skeleton wired into CI, and a CLI that proves the whole loop. **No real market data, no ML training, no UI, and no LLM anywhere in the numeric path** — those are later steps. Step 0 is done when a toy world round-trips `compile → validate → run → record → replay` and every number produced is traceable to a RunRecord.

### Definition of done (Gate G0 — these become CI checks)
1. `ah world build --preset stagflation && ah world validate && ah run && ah replay` completes; replay output is **bit-identical** to the original run (same digest).
2. WorldSpec JSON Schema validation + V-rule validator run on every world; clamps and warnings are recorded in provenance.
3. RunRecords store resolved engine version, seed, and SHA-256 output digest; a tamper test (mutate stored paths → digest mismatch detected) passes.
4. Chronicle is append-only (update/delete attempts raise; covered by tests).
5. Compiler regression harness runs 50 fixture scenarios **offline** (recorded fixtures, no network in CI) with 100% schema-valid, bounds-clamped output.
6. Validation-battery skeleton computes the stylized-fact panel on toy-engine output and evaluates against a thresholds config (thresholds may be `TODO`/non-blocking, but the plumbing must run in CI).
7. Lint, type-check, tests ≥90% coverage on `core/`, and the G0 end-to-end test all green in CI.

---

## 1. Tech decisions (fixed — do not relitigate in Step 0)

- **Python 3.12**, `uv` for env + lockfile, `pyproject.toml` single-package layout.
- **pydantic v2** for runtime models; **jsonschema** (Draft 2020-12) for contract validation — both run (schema = interchange truth, pydantic = ergonomic mirror; a test asserts they agree).
- **SQLite** via stdlib `sqlite3` for RunRecords + chronicle (single file `data/ah.db`); repository pattern so Postgres can replace it later without touching callers.
- **numpy** only for the engine; no pandas in `core/` (allowed in `battery/`).
- **typer** for the CLI, **pytest** + **hypothesis** (property tests for the engine), **ruff** (lint+format), **pyright** (basic mode).
- **GitHub Actions**: `ci.yml` = lint → typecheck → tests → G0 end-to-end; no network access in CI (enforce by pytest-socket).
- **Anthropic SDK** behind an interface; live calls only via explicit CLI flag, never in tests/CI.
- Determinism rule: **all randomness flows from one integer seed** through `numpy.random.Generator(PCG64(seed))`; no global RNG, no `random`, no time-based defaults.

## 2. Repository layout (create in WP0.1)

```
alternate-histories/
├── STEP0-PLAN.md                  # this file
├── pyproject.toml  uv.lock  README.md  CHANGELOG.md
├── .github/workflows/ci.yml
├── schemas/                       # vendored contracts (§8) — read-only truth
├── src/ah/
│   ├── core/
│   │   ├── worldspec.py           # pydantic models mirroring the schema
│   │   ├── validator.py           # V1–V12 + bounds clamps
│   │   ├── engine.py              # deterministic toy engine (§WP0.4 spec)
│   │   ├── institution.py         # sleeves, decisions, hold-course twin
│   │   └── digest.py              # canonical serialization + SHA-256
│   ├── store/
│   │   ├── db.py  runrecords.py  chronicle.py  worlds.py
│   ├── compiler/
│   │   ├── interface.py           # Protocol: compile(text) -> dict
│   │   ├── anthropic_adapter.py   # live impl (never imported by tests)
│   │   ├── fixture_adapter.py     # replays recorded fixtures
│   │   └── postprocess.py         # fence-strip, JSON extract, clamp handoff
│   ├── battery/
│   │   ├── stylized.py            # fact panel functions
│   │   ├── thresholds.yaml        # numeric gates (TODO markers allowed)
│   │   └── report.py
│   ├── cli.py
│   └── presets/                   # 4 preset worlds as WorldSpec JSON
├── tests/                         # mirrors src; + test_g0_end_to_end.py
├── fixtures/compiler/             # 50 scenario→world recorded pairs
├── governance/
│   ├── model-inventory.yaml  decision-register.md  genai-track.md
└── data/                          # gitignored; ah.db lives here
```

## 3. Work packages

### WP0.1 — Scaffold, tooling, CI
Create the layout above; configure uv/ruff/pyright/pytest/pytest-socket; CI green on an empty test. Pre-commit hooks (ruff, pyright). Acceptance: CI passes on main; `uv run pytest` works locally.

### WP0.2 — WorldSpec models + loader
Implement pydantic models mirroring `schemas/worldspec-v1.0.schema.json` exactly (field names, bounds, enums). Loader: `load_worldspec(path|dict) -> WorldSpec` runs **jsonschema first**, then pydantic. Round-trip test: `schemas/example-long-stagflation.worldspec.json` loads, dumps, reloads identically. Property test: pydantic accepts ⇔ jsonschema accepts on fuzzed near-valid documents (hypothesis). Key structures (see schema for full detail): `spec_version, world_id, status, provenance{source, validation{clamps, warnings}}, narrative{...display-only...}, horizon{start, quarters}, regimes{mode: sequence|transition_matrix|unconditional}, factor_conditions{policy_rate, inflation, equity, credit, commodities, correlation, crisis_windows}, structural{parameter_vintage, private_equity, private_credit, real_estate, smoothing}, engine_defaults{generator_id, n_paths, base_seed, ...}, extensions{x_*}`.
**Hard rule to enforce in code:** nothing under `ah/core/engine.py` or `ah/core/institution.py` may read `narrative` — add an import-time assertion/test that the engine module never accesses that attribute (e.g., engine receives a `NumericWorld` dataclass projected from WorldSpec that structurally omits narrative).

### WP0.3 — Validator (V-rules)
`validate(world: dict) -> ValidationResult{clamped_world, clamps[], warnings[], blocking[]}` implementing:
- Bounds clamps to schema min/max, each recorded `{path, submitted, applied}` (V9; >3 clamps adds a warning).
- **V1** inflation ≥5 & rate_end ≤2 → warn (financial repression). **V2** windows/peaks inside horizon → clamp. **V3** spread peak ≥ start → swap+warn. **V4** regime/condition mismatch (stagflation & inflation<4; deflation_boom & inflation>2) → warn. **V5** equity drift ≥8 & PE multiple drift ≤−3 (or reverse) → warn. **V6** crisis severity ≥0.5 with spread peak < start+150 → warn. **V7** narrative dates inside horizon → warn. **V8** dispatches 3–10, non-empty, non-decreasing → warn. **V10** sequence must tile [0, quarters−1] gap/overlap-free → **reject**. **V11** transition matrix row-stochastic ±1e-6, square → **reject**. **V12** vintage consistency (custom requires ≥1 sleeve; non-custom with sleeves → warn).
Validator writes `provenance.validation` and flips status draft→validated. One test per rule, plus a table-driven suite.

### WP0.4 — Deterministic toy engine
Port the prototype engine as pure functions. Monthly, `NM = quarters*3`. All series seeded from `base_seed` via PCG64. Spec (implement exactly; symbols from `factor_conditions` fc and `structural` st):
- Paths: policy rate — AR toward linear start→end target, `r ← max(0.1, r + 0.15(target−r) + 0.06·z)`; HY spread — linear rise to `peak` at `spreadPeakQuarter*3` then linear decay toward `0.9·start`, plus `14·z` noise, floor 150; inflation — AR(0.12) toward `average_pct` (×1.15 in crisis) with `0.28·z`, floor −2.
- Crisis months: `[crisisStartQuarter*3, +crisisLengthQuarters*3)`. Common factor: `z_i = ρ·z_M + √(1−ρ²)·ε`, ρ=0.85 in crisis else 0.45. Equity–bond correlation +0.35 if inflation avg>3.5 else −0.30.
- Monthly returns (drifts %/yr ÷12; vols %/yr ÷√12): equity `drift/12 + vol·z_i − 0.022·crisis`; bonds `rate/1200 − 6·Δrate + 0.007·z_B`; HY `rate/1200 + spread/120000 − 3.5·Δspread + 0.5·vol_eq·z_i − 0.006·crisis`; commodities `drift/12 + max(0, inflAvg−2.5)/1200 + 0.052·z_i`; REITs `0.65·eq − 2.5·Δrate + 0.026·ε`; PE `1.4·eq + (illiq+multDrift)/1200 + 0.02·ε`; PC `(rate+4.5)/1200 − lossM·(3.2 crisis|0.6) + 0.18·eq + 0.007·ε` with `lossM = annualLoss/1200`; RE `0.045/12 − capShift/(10000·NM)·2.2 + 0.35·eq + 0.011·ε`.
- Reported marks (pe/pc/re): quarterly only — at month `(m+1)%3==0`, `rep = w·q_true + (1−w)·rep_prev`, w from `structural.smoothing.weights_on_truth` (defaults .35/.30/.35); other months 0.
- Ensemble: `run_ensemble(world, n_paths)` uses seeds `base_seed + 7919·k`.
Tests: golden snapshot (seed 42 stagflation preset → frozen array hashes); hypothesis properties (no NaN/inf; rate ≥0.1; spread ≥150; reported series flat off quarter-ends); determinism (two runs identical); narrative-blindness test from WP0.2.

### WP0.5 — Institution simulator + decisions
Port sleeves/targets logic: start mix {equity .30, bonds .10, hy .05, commod .05, reits .05, pe .25, pc .10, re .10}; decision months = each 12th month−1 for years 1–9; actions `hold | derisk | leanin | secondary` (shift 10pts growth {equity,pe} ↔ defensives {bonds,pc} preserving proportions; secondary: sell min(8pts, w_pe) of PE at 0.82 → one-off haircut `total ×= 1 − sold·0.18`, targets pe−.08 → bonds+.08, renormalize); annual rebalance to targets at decision months; `useReported` selects reported vs true series for private sleeves. Provide `hold_course_twin(world, seed)` and `decision_alpha`. Golden + property tests (weights sum to 1; no negative sleeves).

### WP0.6 — Stores: worlds, RunRecords, chronicle
SQLite, WAL mode, migrations in `store/db.py`. Tables: `worlds(world_id PK, spec_version, status, json, created_at)` (immutability: engine-consumed field edits require new world_id + `parent_world_id` — enforced in `worlds.save`); `run_records(run_id PK, world_id FK, resolved_engine json, seed, n_paths, overrides json, outputs_digest, summary_stats json, created_at)`; `chronicle(id PK, world_id, run_id, seq, month, type, payload json, created_at)` with **no UPDATE/DELETE** (repository exposes only append/read; a trigger raises on update/delete; test both).
`digest.py`: canonical JSON (sorted keys, fixed float formatting `repr` of float64) → SHA-256 over the concatenated path arrays; `verify(run_id)` recomputes and compares. Tamper test required.

### WP0.7 — Compiler interface + offline regression harness
`CompilerProtocol.compile(scenario_text: str) -> dict` with two impls: `AnthropicCompiler` (model `claude-sonnet-4-6`, prompt in `compiler/prompt_v1.py` with version string `compile-world-v1.0`, JSON-only instruction, fictional-entities rule) and `FixtureCompiler` (looks up `fixtures/compiler/{slug}.json`). Postprocess: strip fences, extract outermost `{}`, parse, hand to validator. Build the **50-fixture regression set**: 50 scenario strings covering inflation/deflation/crisis/no-crisis/rates-up/down/sideways/credit-stress/boom variants, each with a checked-in compiled-world JSON (author them directly — hand-written fixtures are fine and better-controlled than recorded API output for step 0; mark 10 as *adversarial*: out-of-bounds numbers to exercise clamps, missing fields to exercise rejection). Harness test: all 50 load → validate → run 12 months without error; adversarial ones produce expected clamps/rejections. A `--live` CLI path may call the real API; tests never do (pytest-socket enforces).

### WP0.8 — Validation battery skeleton
`battery/stylized.py`: functions over a returns matrix — excess kurtosis, skew, Hill tail index (5% tail), ACF of returns lags 1–5, ACF of |r| lags 1–12, max drawdown distribution, cross-correlation matrix distance vs a reference. `thresholds.yaml`: per-metric `{min?, max?, status: enforce|todo}` — ship with sensible `todo` placeholders (pre-registration happens at the D6 workshop; the *plumbing* is step 0). `report.py`: run battery on a toy ensemble → markdown + JSON report, exit non-zero only on `enforce` failures. CI job runs it on the stagflation preset. Battery version string recorded into RunRecords.

### WP0.9 — CLI, governance scaffolding, docs
CLI (`ah`): `world build --preset X | --scenario "..." [--live]`, `world validate <id>`, `world show <id>`, `run <world_id> [--seed N --paths N]`, `replay <run_id>` (recompute, compare digest), `verify <run_id>`, `battery <run_id>`, `chronicle <world_id>`. Governance files: `model-inventory.yaml` (entries: toy-engine v0, validator v1, battery v0.1, compiler prompt v1.0 — fields: owner, version, tier[numeric|genai], validation_evidence, last_review); `decision-register.md` (D1–D10 as a table: decision, options, recommended default, status=OPEN, owner, blocks); `genai-track.md` (one page: compiler + future narrator/actor components, prompt versioning policy, no-generative-content-in-numeric-path rule, EU-AI-Act/NIST tracking note). README: quickstart + architecture sketch + the G0 checklist. `CHANGELOG.md` seeded with `worldspec 1.0.0`.
Final deliverable: `tests/test_g0_end_to_end.py` executing the full Definition-of-done list programmatically.

## 4. PR sequence & conventions
One PR per WP, in order (WP0.4 and WP0.5 may be one PR; WP0.6 can start after WP0.2). Conventional commits; every PR updates CHANGELOG; no PR merges red. Type hints everywhere in `core/` and `store/`; docstrings state units (%/yr vs monthly decimal) on every engine function — unit confusion is the #1 foreseeable bug.

## 5. Explicit non-goals for Step 0
Real market data ingestion; de-smoothing; any trained model; the diffusion/bootstrap generators (engine_defaults may name them, engine only implements `toy-v0` and must **error clearly** on others); Tier-2 artifacts/world bible; live-mode UI; auth; Postgres; performance tuning beyond "tests run < 60s".

## 6. Foreseeable pitfalls (read before coding)
Float determinism across platforms — pin numpy, use float64 throughout, digest via `repr`; if CI-vs-local drift appears, digest on rounded 12-decimal values and document it. Seed hygiene — one `Generator` per simulation, threaded explicitly. JSON float canonicalization — one serializer in `digest.py`, used everywhere. The narrative-blindness guarantee — do it structurally (projected `NumericWorld` without the field), not by convention. SQLite append-only — trigger + repository, test both layers.

## 7. Estimated shape
~2,500–3,500 LOC src, similar in tests. WP0.1–0.3 ≈ day 1–2; WP0.4–0.5 ≈ day 2–4; WP0.6–0.7 ≈ day 4–6; WP0.8–0.9 ≈ day 6–8 of focused Claude Code sessions.

## 8. Provided files to vendor into `schemas/` (do not edit; copy verbatim)
- `worldspec-v1.0.schema.json` — the contract (normative).
- `example-long-stagflation.worldspec.json` — canonical example; used in WP0.2 round-trip test and as the `stagflation` preset seed.
- `world-bible-v1.0.schema.json` — **reference only in Step 0** (Step 4 consumes it); vendor now so the contract set is complete.
- `WORLDSPEC.md` — semantics, V-rule text, RunRecord description; treat as documentation-of-record.
If any of these files are missing at kickoff, halt and request them rather than reconstructing from this plan.
