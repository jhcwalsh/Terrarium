# BUILD-SUMMARY.md — what actually exists

*Assembled 2026-08-05 from the repository at `main` @ `545a2ac`, by reading the
code and running it. Where a design document and the code disagree, **the code
is reported and the disagreement is recorded in §5**. Nothing planned is
described as existing.*

**How to read this.** §1 is the map. §2 is the inventory with evidence and
invocation. §3 is the configuration, verbatim from the files that hold it.
§4 is the test estate. §5 is the gap list, and §5 is the part worth your
time — an orientation document whose gap section is short is a document that
did not look.

---

## 1. System map

Dependency direction is downward only. `port` / `gen` / `eval` / `artifacts`
depend on `data`, which depends on `core`; nothing points back up. The product
surface (`bundle`, `feed`, `serve`, `play`, `credibility`, `programme`) sits on
top of `core` + `port` and is the only layer the browser sees.

```
Terrarium/
├── src/ah/
│   ├── core/                  the numeric core — no pandas, no network, no clock
│   │   ├── worldspec.py       pydantic mirror of schemas/worldspec-v1.2.schema.json
│   │   ├── loader.py          jsonschema-first then pydantic (a property test pins agreement)
│   │   ├── validator.py       V1–V12 coherence rules; V10/V11/V12 block   → validate()
│   │   ├── numericworld.py    the narrative-free projection the engine consumes
│   │   ├── engine.py          the deterministic toy engine `toy-v0.3`     → run_path/run_ensemble
│   │   ├── institution.py     Step-0 toy institution (8 weights, no cash) → simulate_institution
│   │   ├── sleevestate.py     Step-3 sleeve/vehicle state contract
│   │   ├── institutionstate.py institution state for the twin
│   │   └── digest.py          canonical JSON + SHA-256 over float64 tensors
│   ├── store/                 SQLite; append-only where it matters
│   │   ├── db.py              schema + triggers (chronicle UPDATE/DELETE refused)
│   │   ├── worlds.py          save_world refuses edits to engine-consumed fields
│   │   ├── runrecords.py      RunRecords + verify_run (the anchor behind `ah replay`)
│   │   ├── chronicle.py       append-only event log per world
│   │   ├── sessions.py        play sessions: monotone pointer, final decisions
│   │   └── leaderboard.py     submit_score/scores over db.py:92's
│   │                          UNIQUE(world_id, seed, decision_alpha_version, participant)
│   ├── compiler/              scenario text → raw world document
│   │   ├── pipeline.py        validate → clamp → construct WorldSpec       → process()
│   │   ├── fixture_adapter.py the offline compiler (50 committed fixtures)
│   │   └── anthropic_adapter.py the live compiler, imported only under --live
│   ├── data/                  Step 1 — immutable Parquet vintages over DuckDB
│   │   ├── catalog.py         the vintage store; `current` advances only if QC passes
│   │   ├── connectors/        fred, bis, french, jst, shiller, treasury_hqm
│   │   ├── qc.py splice.py derive.py desmooth.py episode.py reports.py refresh.py
│   │   └── cli.py             → `ah data …`
│   ├── gen/                   Step 2 — the generator layer (research, NOT on the play path)
│   │   ├── registry.py        generator_id → factory                       → resolve()
│   │   ├── bootstrap.py       `bootstrap-v1`, the sealed benchmark
│   │   ├── climate/ regimes/  L1 (numpyro) and L2 (semi-Markov)
│   │   ├── blocks/            L3 — diffusion + flow (`hier-flow-v1`, torch)
│   │   ├── joinery/           L4 — waypoints, bridge, Denton reconciliation
│   │   └── systems.py         the five ablation systems A–E
│   ├── eval/                  the sealed judging code (hashed in pre-registration.lock)
│   │   ├── prereg.py g2.py g3seal.py g5seal.py     seals, locks, amendment log
│   │   ├── battery.py metrics/                     the Step-2 validation battery
│   │   ├── decision_metrics.py                     Step-5 sealed metric set
│   │   └── walkforward.py counterfactual.py episode2022.py negative_controls.py
│   ├── port/                  Step 3 — the translation layer and the real institution
│   │   ├── sleeves.py vehicles.py cohort.py        state objects
│   │   ├── cashflow_tier0.py cashflow_tier1.py     the commitment/call/distribution model
│   │   ├── portfolio.py                            cash account + coverage on both bases
│   │   ├── engine.py                               the quarterly waterfall  → PortfolioEngine
│   │   ├── twin.py                                 the DB-pension institutional twin
│   │   └── mapping.py smoothing.py heroes.py proxy.py
│   ├── artifacts/             Step 4 — the wire, the letters, the committee
│   │   ├── templates.py render.py                  Tier-1, pure functions of the tape
│   │   ├── author.py prompts.py gate.py            Tier-2 authoring + the G1–G9 gate
│   │   ├── bible.py validation.py committee.py     continuity, actor study, AI committee
│   │   ├── chronicle.py payloads.py                the G9 publication record (unused — §5.13)
│   │   └── live.py calendar.py windows.py decisions.py
│   ├── battery/               Step-0 stylized battery (thresholds still `todo` — §5)
│   ├── presets/               the four preset worlds
│   ├── splits.py              train/val/holdout + the FinalEvaluationToken guard (sealed)
│   ├── factors.py strategies.py  the factor manifest and the D4 strategy set (both sealed)
│   ├── experiment.py          local-first experiment tracking under experiments/
│   ├── play.py                the playable institution on the Step-3 twin → simulate_play
│   ├── bundle.py              the world bundle, contract `world-bundle-0.4` → build_bundle
│   ├── feed.py                the in-timeline tier-1 wire                  → build_tier1_feed
│   ├── serve.py               FastAPI session service — the scoring authority
│   ├── credibility.py         admin console: does this world's arithmetic look sane
│   ├── programme.py           the private-programme section of that console
│   ├── inspect.py             static figure page from a RunRecord alone
│   ├── tournament.py density.py                    Step-5 harnesses
│   └── cli.py exp_cli.py      → `ah`, `ah exp`
├── app/                       the React/TS player (vite 5173, proxies /sessions → 8787)
├── schemas/                   READ-ONLY vendored contract truth
├── mappings/                  frozen parameter artifacts (pacing, tier-0 spec, tier-1
│                              linkage, smoothing kernel, sleeve mappings)
├── fixtures/                  compiler, state, worlds, entity_screen, actor_validation,
│                              authoring_regression
├── tests/                     121 test modules + one shared helper
├── scripts/                   53 deterministic build/measure/train scripts
├── Instructions/              the authoritative plans, design notes and kickoffs
├── governance/                seals, amendment log, decision register, GenAI pack, evidence
├── docs/                      the realism register, data specs, and the superpowers plans
├── artifacts/                 committed research outputs (wp24…wp57, campaign2)
├── configs/ taxonomy/         search configs and the sleeve taxonomy
├── experiments/  (gitignored)  trained checkpoints and experiment records
└── data/         (gitignored)  the Parquet vintage store and data/ah.db
```

**Entry points, exhaustively.** The console script `ah` (`pyproject.toml:35` →
`ah.cli:app`); the ASGI app `ah.serve:app` (`src/ah/serve.py:318`); the module
entry `python -m ah.battery.report`; the vite app in `app/`; and the 53
scripts in `scripts/`, each run with `uv run python scripts/<name>.py`.

---

## 2. Capability inventory

Status vocabulary: **working** — runs end to end and I ran it; **partial** —
runs, but a named part of what the design asks for is absent; **stub** —
present as an interface or placeholder without the substance behind it;
**absent** — named somewhere but not built; **unverified** — I could not run it.
Qualifiers after a status ("working, sealed"; "working locally, not reproducible
from a clean clone") are free text, not vocabulary.

**Flags are not exhaustive.** The "how to invoke" column shows the shortest
command that does the thing, not every option. Notably absent from it:
`ah data refresh --dry-run/--source/--vintage`, the `--data-root`/`--root`
overrides on the data and experiment commands, and `ah credibility --seed`.
Run `--help` on any subcommand for the full set.

**Coverage of this inventory, stated:** `core/`, `port/` and `store/` are
covered module by module. `eval/`, `gen/`, `compiler/` and `data/` are covered by
capability, not by module — 28 of the 157 modules under `src/ah/` have no row of
their own, including sealed judged code (`factors.py`, `strategies.py`,
`eval/reference.py`, `eval/panel.py`, `eval/ablation.py`, `eval/sleevetails.py`)
and `gen/base.py`. See §5.15.

### World generation

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Preset worlds (4) | working | `src/ah/presets/*.json`; ran all four through build/validate | `ah world build --preset stagflation` |
| Scenario → world, offline | working | `src/ah/compiler/fixture_adapter.py`; 50 fixtures in `fixtures/compiler/`; I built `00000000-0000-4000-8000-000000000000` from a fixture scenario | `ah world build --scenario "<text from fixtures/compiler/_manifest.json>"` |
| Scenario → world, live LLM | **unverified** | `src/ah/compiler/anthropic_adapter.py`, imported lazily at `src/ah/cli.py:117` | `ah world build --scenario "…" --live` (needs network + key; not run) |
| Toy engine `toy-v0.3` | working | `src/ah/core/engine.py:42`, `run_path` at `:261`, `run_ensemble` at `:415` | `ah run [WORLD_ID] --paths N --seed S` |
| L1 climate layer | working locally, **not reproducible from a clean clone** | `src/ah/gen/climate/`; the fitted posterior is `experiments/climate-l1-f7d4119c7101-s20260726/climate-posterior.npz`, SHA-pinned at `joinery/assemble.py:140,146`. the L1 *fit report* is `experiments/climate-l1-…/climate-fit-report.md`, gitignored alongside the posterior; `artifacts/wp27/` carries the downstream joinery/battery report | `uv run python scripts/fit_climate.py` |
| L2 regime layer | working locally, **not reproducible from a clean clone** | `src/ah/gen/regimes/`; posterior at `experiments/regimes-l2-1758709d4009-s20260727/`, SHA-pinned at `joinery/assemble.py:143,147` | `uv run python scripts/fit_regimes.py` |
| L3 block generators | working locally, **not reproducible from a clean clone** | `src/ah/gen/blocks/flow.py:583` registers `hier-flow-v1`; the factory hard-requires `experiments/campaign2-flow-s0/checkpoint.pt` against pinned SHA `c6addb54…` (`flow.py:503,514,551`). `experiments/` is gitignored | `registry.resolve("hier-flow-v1")` — I confirmed it resolves here and the checkpoint hash matches |
| L4 joinery | working (research) | `src/ah/gen/joinery/{waypoints,bridge,reconcile,assemble}.py` | via the systems in `src/ah/gen/systems.py` |
| Ablation systems A–E | partial | `src/ah/gen/systems.py:503,610`; registry lists `abl-a/b/c` variants. `abl-b-neural-rollout-diffusion` and `abl-c-neural-only-diffusion` are **constructible but untested by design** (`systems.py` §"B and C run the FLOW arm only") | `uv run python scripts/run_ablation_grid.py` |
| **Neural generators on the play path** | **absent** | `ah run` calls `run_ensemble` (`cli.py:195`), which calls `_require_toy` (`engine.py:151`) and raises `UnsupportedGeneratorError` for anything but `toy-v0` | — see §5.1 |

### Compiler and coherence checks

| capability | status | evidence | how to invoke |
|---|---|---|---|
| JSON-Schema validation | working | `src/ah/core/loader.py`; schema is `schemas/worldspec-v1.2.schema.json` | inside `process()` |
| Pydantic mirror agreement | working | `src/ah/core/worldspec.py`; property test `tests/test_worldspec.py` | `pytest tests/test_worldspec.py` |
| V1–V12 coherence rules | working | `src/ah/core/validator.py:70`; bounds clamps `:128`, blocking V10/V11 `:428`, V12 `:493` | `ah world validate [WORLD_ID]` — output: `clamps=0 warnings=[] blocking=[]` |
| Clamp-then-construct pipeline | working | `src/ah/compiler/pipeline.py:28`; rejection path `cli.py:124` | `ah world build` |
| Validation stamping | working | `stamp_validation` at `cli.py:129`; flips `status` to `validated` | automatic on build |

### Ensemble generation, replay, verification

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Ensemble with seed lineage | working | `engine.py:427` — seeds are `base_seed + 7919*k` | `ah run --paths 1000` |
| Output digest | working | `src/ah/core/digest.py`; `compute_outputs_digest` at `store/runrecords.py:31` | recorded on every RunRecord |
| Replay (bit-identical) | working | `cli.py:239`; I ran it and got `MATCH` on `sha256:73326f13…` | `ah replay [RUN_ID]` |
| Verify from lineage | working | `store/runrecords.py:83` | `ah verify [RUN_ID]` → `True` |
| Append-only chronicle | working | trigger-level refusal, `store/db.py:48`; I read a 2-entry chronicle back | `ah chronicle [WORLD_ID]` |
| World immutability | working | `store/worlds.py:58` raises `ImmutableWorldError` on engine-consumed edits | — |

### Cashflow engine and the portfolio engine

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Tier-0 cashflow (constant-G TA) | working | `src/ah/port/cashflow_tier0.py`; frozen spec `mappings/cashflow-tier0-v1.0.yaml` | `run_tier0(...)` |
| Tier-1 cashflow (market-linked) | working | `src/ah/port/cashflow_tier1.py:90`; linkage frozen in `mappings/cashflow-tier1-v1.0.yaml`; `f_dist` (`:48`) / `f_call` (`:61`) consume **continuous states only** | `run_tier1(...)` |
| "Tier 1 with linkage+fees off IS tier 0" | working | asserted by test, `tests/test_cashflow_tier1.py` | `pytest tests/test_cashflow_tier1.py` |
| Cohort recursion | working | `src/ah/port/cohort.py`; parameters in `mappings/pacing-parameters-v1.0.yaml`, drift-guarded by `tests/test_pacing_artifact.py` | — |
| Call curve `rc_curve` | **partial — placeholder** | `[0.25,0.30,0.20,0.12,0.08,0.05]` in `fixtures/state/closed-end-cohort.example.json`; **~29% of every commitment is never called** (`docs/engine-realism-register.md` §ER-6, status **open**) | — see §5.3 |
| Quarterly waterfall | working | `src/ah/port/engine.py:77` — receive, pay calls, spend off the trailing **reported** average, then forced sale | `PortfolioEngine.run_quarter(...)` |
| Forced sale, liquid pro-rata | working | `port/engine.py:107-126`, every event logged with cause and sleeves | — |
| Forced secondary at haircut | working | `port/engine.py:128-153` at `secondary_haircut = 0.19` | — |
| Private-weight breach detection | working | `port/engine.py:155-170`, both bases | `QuarterReport.breach_true/breach_reported` |
| Vehicle mechanics (notice, gates, side pockets) | working | `src/ah/port/vehicles.py`; `tests/test_port_vehicles.py` | — |
| Hero funds (reconciliation invariant) | working | `src/ah/port/heroes.py`; `tests/test_port_proxy_heroes.py` | — |

### Decisions, twins, decision alpha

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Decision windows | working | `core/institution.py:71` — month `12y-1`, years 1–9. For a 40-quarter world: `[11,23,35,47,59,71,83,95,107]` (I read this back off a live session) | `GET /sessions/{sid}` → `decision_windows` |
| Four actions | working | `hold / derisk / leanin / secondary` (`core/institution.py:52`) | `POST /sessions/{sid}/decisions` |
| **Play institution (the scored one)** | working | `src/ah/play.py:310` `simulate_play` — real cash account, a commitment ladder, calls that must be funded, forced sales | via the session service |
| **Toy institution (Step 0)** | working, but **still on live surfaces** | `core/institution.py:98`; used by `bundle.summary`, `inspect.py`, `feed.py:175`, `tournament.py`, `density.py` | — see §5.2 |
| Hold-course twin (product) | working | `play.py:451` — the twin takes no action at any window | `simulate_play(paths, None)` |
| Hold-course twin (toy) | working | `core/institution.py:162` | `hold_course_twin(...)` |
| Institutional twin (DB pension) | working, v1-simple | `src/ah/port/twin.py` — parameterized benefit profile, flat discount, hedges, collateral. Full member-level projection explicitly deferred | `tests/test_port_twin.py` |
| **Drift twin** | **stub — slot only** | `serve.py:300` returns `"drift_twin": None`; the contract carries three series so its arrival is a data change (E7, `Instructions/experience-deltas-register.md`) | — |
| Decision alpha, product | working | `serve.py:256` `alpha = active.final_value - twin.final_value`, stamped `PLAY_ALPHA_VERSION = "port-v1-cashflow"` (`play.py:80`). I measured `+3.3735` on a played decade | `GET /sessions/{sid}/outcome` |
| Decision alpha, research | working, sealed | `eval/decision_metrics.py:55` (log points), `DECISION_ALPHA_VERSION = "1.0"` inside the G5 lock | `pytest tests/test_decision_metrics.py` |
| Chain-link window attribution | working | `play.py:476`, K+1 exact runs, no sampling. I verified the telescoping identity live: contributions summed to `3.3735227993676062`, exactly the reported alpha | `GET /sessions/{sid}/outcome` → `window_contributions` |
| Counterfactual "was it a good call" | working | `src/ah/eval/counterfactual.py`; `tests/test_recone.py` | research only |
| Tournament (3 formats) | working | `src/ah/tournament.py` — solo / cohort-cadence / simultaneous; score invariance across formats is a pinned test | `pytest tests/test_tournament.py` |
| Decision-density study | working | `src/ah/density.py` — but on the **toy** institution | `pytest tests/test_density.py` |
| Leaderboard | working (server), **broken in the dev app** | `serve.py:212` returns rows keyed on the required triple; `curl` against a live service returned `{"world_id":"x","seed":1,"decision_alpha_version":"1.0","rows":[]}` | — see §5.4 |

### The battery

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Step-0 stylized battery | **partial — no ratified thresholds** | `src/ah/battery/thresholds.yaml`: every metric is `status: todo`, and the file says so ("Step 0 ships plumbing only… placeholders documenting intent, not ratified thresholds"). `passed` is `not enforce_failures` (`battery/report.py:62`), so with zero `enforce` entries it cannot fail | `ah battery [RUN_ID]` / `python -m ah.battery.report` — **not run here, per instruction** |
| Step-2 validation battery | working, sealed | `src/ah/eval/battery.py` with suites in `src/ah/eval/metrics/`; MC error bars, reference bands, prereg thresholds. Hashed into `pre-registration.lock` | `run_full_battery(...)`; results committed under `artifacts/wp27*/`, `artifacts/wp29/` |
| Negative controls | working | `src/ah/eval/negative_controls.py`; `tests/test_negative_controls.py` | — |
| Leakage guard | working | `src/ah/splits.py`; `FinalEvaluationToken` mintable only in `eval/g2.py`; import-graph test `tests/test_leakage_guard.py`. **The holdout has been spent** (WP5.6) | `pytest tests/test_leakage_guard.py` |
| Pre-registration seal | working | `pre-registration.lock` (34 hashed files), `pre-registration-g3.lock`, `pre-registration-g5.lock`; `tests/test_seal_guards.py` | `pytest tests/test_seal_guards.py` |

### Artifact generation

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Tier-1 templates | working | `src/ah/artifacts/templates.py` — pure functions of the tape, no LLM/RNG/clock | via `build_tier1_feed` |
| Tier-1 wire in the bundle | working | `src/ah/feed.py:159`. My stagflation bundle carried **222 items** across `cb_statement`, `newspaper`, `quarterly_statement`, `release_page`, `wire_digest` | `ah bundle [RUN_ID]` |
| Watermarking | working | applied in the renderer, `src/ah/artifacts/render.py` | — |
| Tier-2 authoring pipeline | working, **not shipped in bundles** | `src/ah/artifacts/author.py` (two retries then Tier-1 fallback, `MAX_RETRIES = 2`); the ≥95% first-pass bar is **met** — `governance/evidence/AUTHORING-REGRESSION.md` records 30/30, 100.0%, "ships: YES". No bundle contains a tier-2 letter | `uv run python scripts/run_authoring_regression.py` (**live model; not run here**) |
| G1–G9 consistency gate | working | `src/ah/artifacts/gate.py`, `GATE_IMPL_VERSION = "gate-impl/1.0.6"`; blocking split frozen under AM-2026-08-02-002. G3's leak-checker prompt is **v1.1, not built** (stated in the module docstring); G6 is advisory | `pytest tests/test_authoring_regression.py` |
| World bible | working | `src/ah/artifacts/bible.py`, checks B1–B6 | `pytest tests/test_bible.py` |
| AI committee | working | `src/ah/artifacts/committee.py`; benchmarked in `governance/evidence/ACTOR-VALIDATION.md` | `pytest tests/test_committee.py` |
| Live mode (sealed reveal) | working | `src/ah/artifacts/live.py`; tape seal reused by the bundle (`bundle.py:151`) | `pytest tests/test_live_mode.py` |

### The product surface

| capability | status | evidence | how to invoke |
|---|---|---|---|
| World bundle | working | `src/ah/bundle.py:56` `BUNDLE_VERSION = "world-bundle-0.4"`; 1 MB budget enforced at `:190`. I built one: **31,263 bytes**, `digest_verified: true` | `ah bundle [RUN_ID] --out world.bundle.gz` |
| Session service | working | `src/ah/serve.py`; 7 routes. I created a session, advanced, decided at all 9 windows, completed, and read the outcome | `uv run uvicorn ah.serve:app --port 8787` |
| Mark-to-market at the pointer | working | `serve.py:119` — server-side, never client-side (W5). At month 12 I read `value=98.0151`, `cash=0.3183`, `coverage_true=0.1782`, `private_weight_true=0.3436` | `GET /sessions/{sid}` |
| Auth | **absent by design (v0.1)** | `serve.py:8-10` — "no auth — single-user, local"; joins at the M4 boundary | — |
| React player | working | `app/`; 8 test files / 32 tests pass, `tsc -b --noEmit` clean | `cd app && npm run dev` |
| Client-side seal re-verification | working | `app/src/lib/bundle.ts`, pinned against the committed `app/fixtures/toy.bundle.gz` by the **TypeScript suite only** — the Python suite builds its own bundles and never opens that file (§5.8) | `cd app && npm run test` |
| Offline replay cache | working | `app/src/lib/idb.ts` (IndexedDB, W8) | — |
| Static figure page | working | `src/ah/inspect.py`; regenerates and re-verifies the digest on every render. I produced a 125,911-byte self-contained page | `ah inspect [RUN_ID] --out page.html` |
| Credibility console (admin) | working | `src/ah/credibility.py:294`; read-only. I ran it over two presets: "2 worlds, 2 flags" | `ah credibility --preset stagflation --preset goldilocks --out credibility.html` |
| Private-programme console section | working | `src/ah/programme.py:751`; read-only enforced by import-graph test `tests/test_programme_guard.py` | included in `ah credibility` |
| **`ah audit` (world register + wire audit)** | **absent — plan only** | `docs/superpowers/plans/2026-08-05-world-and-wire-audit.md` (2,027 lines, 7 tasks) and its design note; `ah --help` lists no `audit` command | — |
| Scenario build console (WP-B, added 2026-08-06 — postdates this document's survey) | working | `src/ah/buildconsole.py`; dry-run five-stage compile ledger, keep-only writes (guard test `test_only_keep_handler_writes_to_store`); live path known to end in validator rejection until the compiler prompt rewrite (WP-A) | `uv run uvicorn ah.buildconsole:app --port 8798` |

### The data layer

| capability | status | evidence | how to invoke |
|---|---|---|---|
| Requirements register | working | `requirements.yaml` — the single source of truth for required series | — |
| Immutable vintage store | working | `src/ah/data/catalog.py`; re-writing a (vintage, series) raises; `current` advances only on QC pass | — |
| Connectors | working (`parse` tested, `fetch` untested by design) | `src/ah/data/connectors/` — fred, bis, french, jst, shiller, treasury_hqm | `ah data refresh --live` (network; not run here) |
| Offline refresh | working | `src/ah/data/refresh.py` | `ah data refresh --fixtures <dir> --asof YYYY-MM-DD` |
| Status report | working | I ran it: current vintage `2026-08-02.4`, six sources, QC 138 enforce-passed | `ah data status` |
| As-of resolution | working | `src/ah/data/catalog.py` pointer history | `ah data asof YYYY-MM-DD` |
| Episode packs | working | I ran the 2022 pack: 42 series, window 2022-01-01→2023-12-31 | `ah data episode 2022` |
| Manual intake validation | working | `src/ah/data/intake.py` + `src/ah/data/schemas/` | `ah data intake validate <file> --schema albourne_pm_returns` |
| Manual intake **apply** (state-mutating) | working | `src/ah/data/cli.py` — "Validate a drop AND apply it: write the vintage, run QC, advance on pass"; on QC failure the vintage is quarantined and the pointer stays put | `ah data intake apply <file> --vintage 2026-08-01.1` (`--vintage` required; `--schema` optional, inferred) |
| Experiment tracking | working | `src/ah/experiment.py`; I listed 8 experiments with config hash, seed, git SHA, vintage | `ah exp list` / `show` / `diff` |

---

## 3. The numbers as configured

Every value below is read from the file cited. **UNSET** means the code has no
default and nothing in the repo supplies one.

### Run shape

| quantity | value | source |
|---|---|---|
| Horizon (all 4 presets) | 40 quarters = 120 months, starting `2027-Q1` | `src/ah/presets/*.json` |
| Decision windows per run | **9** — months 11, 23, 35, 47, 59, 71, 83, 95, 107 | `core/institution.py:71` (`12y-1`, years 1–9) |
| Ensemble size, presets | **1000** paths | `src/ah/presets/*.json` `engine_defaults.n_paths` |
| Ensemble size, schema default | 10000 (min 100, max 100000) | `schemas/worldspec-v1.2.schema.json` |
| Ensemble size, credibility console | 400 paths (`--paths`) | `cli.py:300` |
| Seed lineage | `base_seed + 7919*k` | `engine.py:44,427` |
| Preset base seeds | stagflation 771204 · goldilocks 42 · deflation_bust 1848 · reflation_boom 2021 | `src/ah/presets/*.json` |
| Engine version stamp | `toy-v0.3` | `engine.py:42` |
| Validator version | `1.0.0` | `validator.py:27` |
| Battery version | `battery-0.1` | `battery/report.py:34` |
| Bundle contract | `world-bundle-0.4`, ≤1,000,000 bytes gz | `bundle.py:56,57` |
| Product alpha version | `port-v1-cashflow` | `play.py:80` |
| Research alpha version | `1.0` (sealed) | `eval/decision_metrics.py:21` |

### Sleeves

| set | members | source |
|---|---|---|
| Engine assets (order is contract) | equity, bonds, hy, commodities, reits, pe, pc, re | `engine.py:74` |
| Appraisal-smoothed ("reported") | pe, pc, re | `engine.py:84` |
| Liquid (play) | equity, bonds, hy, commodities, reits | `play.py:82` |
| Private (play) | pe, pc, re | `play.py:83` |
| Growth / defensive pairs | (equity, pe) / (bonds, pc) | `play.py:125-126` |

### Opening book — the scored institution

| item | value | source |
|---|---|---|
| Targets, in points of 100 | equity 33 · bonds 12 · hy 5 · commodities 5 · reits 8 · pe 20 · pc 8 · re 7 | `play.py:96-105` |
| Opening cash | 2.0 | `play.py:106` |
| Opening private weight | 35 points — deliberately inside the policy band | `play.py` §START_TARGETS note |

The Step-0 toy institution uses a **different** opening mix — 45 points private
(`core/institution.py:39`), outside the play policy band. Both are live; see §5.2.

### Costs, bands, policy

| item | value | source |
|---|---|---|
| Spending rate | 4.5%/yr, taken quarterly | `port/engine.py:37` |
| Spending basis | trailing **12 quarters of REPORTED** value | `port/engine.py:38,98` |
| Secondary haircut (play/port) | **0.19** (sells at 0.81 of NAV — the 2022-H2 public anchor) | `port/engine.py:39` |
| Secondary discount (toy institution) | **0.18** | `core/institution.py:56` |
| Private-weight policy band | **(0.15, 0.40)** | `port/engine.py:40` |
| Derisk/lean-in shift | 10 points, liquid leg only | `play.py:122` |
| Voluntary secondary size | 8 points of the largest live PE cohort | `play.py:123` |
| Transaction costs | **UNSET** — there is no cost term anywhere; `LiquidSleeve.sell`/`buy` move value at par | `port/sleeves.py:203,211` |
| Management fee / carry on the play path | **supplied but never applied** — every scored cohort is built from a document carrying `mgmt_fee_rate 0.02`, `carry_rate 0.20`, `hurdle 0.08`, European waterfall. They are never charged: `cohort.step` books `CohortStep(..., 0.0, 0.0)` for fees and carry, and the fee machinery lives in `run_tier1`, which the play path never calls | fixture `fixtures/state/closed-end-cohort.example.json`; loaded at `play.py:205-227,230-257`; zeroed at `port/cohort.py:203` |

### Pacing

| item | value | source |
|---|---|---|
| New vintage cadence | every 4th quarter (annual) | `play.py:119` |
| Annual commitment rate | **18%** of each private sleeve's target NAV (≈6.3 points/yr against ≈35 private) | `play.py:118` |
| Contractual life | 10 years | `mappings/pacing-parameters-v1.0.yaml` |
| Distribution bow | 2.5 | `mappings/pacing-parameters-v1.0.yaml` |
| Terminal yield rate | 0.55 | `mappings/pacing-parameters-v1.0.yaml` |
| Call curve `rc_curve` | `[0.25, 0.30, 0.20, 0.12, 0.08, 0.05]` of remaining unfunded, per year, last value repeated | `mappings/pacing-parameters-v1.0.yaml`; **class "chosen", pending ALB-A** |
| Tier-1 `f_call` | `clip(1 - c·drawdown, 0.5, 1.2)` — near-flat by design | `cashflow_tier1.py:61-66` |
| Tier-1 `f_dist` | `clip(exp(-a·dd - b·ln(spread_ratio)), floor, ceiling)` | `cashflow_tier1.py:48-58`; coefficients in `mappings/cashflow-tier1-v1.0.yaml` |
| Spread reference | 400 bps | `play.py:109`, `engine.py:60` |

### Declared plausibility bands (admin console — priors, not truth)

Asset bands, annualized % over ten years (`credibility.py:66`): equity −8…14 ret /
12…28 vol · bonds −2…9 / 3…12 · hy 0…11 / 6…18 · commodities −6…16 / 12…28 ·
reits −8…12 / 12…26 (and pe/pc/re below those lines in the same table).

Programme bands (`programme.py:209`), all seven: `peak_unfunded_ratio` 0.25–0.75 ·
`call_rate_y1_3` 0.15–0.45 · `crossover_years` 4–8 · `dpi_age9` 0.7–2.0 ·
`linkage_bite` 0.50–1.20 · `linkage_shortfall` 0.05–0.35 ·
`forced_secondaries` 0.0–1.0.

### Battery thresholds

**All `status: todo`** — `excess_kurtosis`, `skewness`, `hill_tail_index`,
`acf_r_lag1`, `acf_abs_lag1`, `max_drawdown_median`, `corr_distance`
(`src/ah/battery/thresholds.yaml`). No metric is `enforce`; the Step-0 battery
therefore cannot fail. The Step-2 battery's thresholds are real and live in
`pre-registration.yaml` under the seal.

---

## 4. Test estate

### Suites

| suite | what it is | how to run |
|---|---|---|
| Python, `tests/` | 121 `test_*.py` modules, **2,226 tests** (plus `joinery_common.py`, a shared helper) covering core, store, data, gen, eval, port, artifacts, product surface | `uv run pytest` |
| TypeScript, `app/src/**` | 8 test files, 32 tests (bundle loader + seal, session client, decision window, ranked setup, reckoning, fan chart, book, private markets) | `cd app && npm run test` |
| Type checking | pyright basic mode over `src` + `tests` | `uv run pyright` |
| Lint + format | ruff 0.16.0 (pinned in `uv.lock`) | `uv run ruff check .` / `ruff format --check .` |

Structural invariants are tests, not conventions: narrative-blindness
(`tests/test_narrative_blindness.py` scans the engine for narrative field
access), no-network (`pytest-socket`, `--disable-socket` in `addopts`),
leakage guard (`tests/test_leakage_guard.py` is an import-graph assertion),
seal integrity (`tests/test_seal_guards.py`), the artifacts boundary
(`tests/test_artifacts_service.py::TestBoundary` — `core`/`gen`/`port` never
import `artifacts`), and the programme console's read-only guarantee
(`tests/test_programme_guard.py`).

### What CI runs

`.github/workflows/ci.yml`, on push to `main` and on every PR, in order:

1. `uv sync --frozen --dev`
2. `uv run ruff check .` **and** `uv run ruff format --check .`
3. `uv run pyright`
4. `uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90`
5. `uv run python -m ah.battery.report`
6. `uv run pytest tests/test_g0_end_to_end.py -v`

Note the coverage gate covers **`ah.core` only** (`pyproject.toml:69`), not the
rest of the tree. Two further workflows are scheduled, not gating:
`data-monthly.yml` (a monthly public-source refresh that opens an issue on QC
failure) and `data-reminders.yml` (quarterly manual-intake reminders).

### Last-known status, measured here on 2026-08-05

| check | result |
|---|---|
| `uv run pyright` | **0 errors, 0 warnings, 0 informations** — clean |
| `uv run ruff check .` | **All checks passed** |
| `uv run ruff format --check .` | **FAILS — 2 files would be reformatted** (both markdown plan docs; see §5.5) |
| `cd app && npm run typecheck` | clean |
| `cd app && npm run test` | **8 files, 32 tests, all pass** |
| `uv run pytest` | **2,226 tests across 121 modules — all passed** (exit 0, ~20 minutes wall clock) |
| `uv run pytest` on the core rails only (engine, validator, worldspec, stores, digest, G0 end-to-end) | **80 passed in 3.29s** |
| `python -m ah.battery.report` | **not run** — battery execution is gated pending threshold ratification (§3) |

---

## 5. Known gaps and discrepancies

Ordered by how much they would surprise someone who read the design documents
and then read the code. Everything here was found in this pass; nothing is
copied forward from a status table without re-checking.

### 5.1 The promoted generator cannot reach a player

Step 2's gate promoted `hier-flow-v1` (`G2-EVIDENCE.md`; `S2-DEFAULT-GENERATOR`),
and the WorldSpec enum carries it (`core/worldspec.py:62`). But every playable
path runs the **toy engine**: `ah run` calls `run_ensemble` (`cli.py:195`),
which calls `_require_toy` (`engine.py:151`) and raises
`UnsupportedGeneratorError` for any other id. `ah/gen/registry.py` is never
imported by `ah/cli.py`, `ah/bundle.py`, `ah/serve.py`, or `ah/play.py`. The
generator layer is a research artifact; the product runs on `toy-v0.3`.

Two consequences worth stating separately:

- **A fresh clone cannot instantiate the generator stack at all.**
  `hier_flow_v1_factory` requires `experiments/campaign2-flow-s0/checkpoint.pt`
  and refuses anything whose SHA-256 is not `c6addb54…` (`flow.py:551-557`); it
  then loads the L1 and L2 posteriors from `experiments/climate-l1-…` and
  `experiments/regimes-l2-…`, each SHA-pinned (`joinery/assemble.py:140-147`).
  `experiments/` is gitignored. It resolves on this machine; it would not on a
  clean checkout. Refitting/retraining is the documented alternative
  (`scripts/fit_climate.py`, `scripts/fit_regimes.py`,
  `scripts/train_flow_final.py`) and is GPU-hours of work.
- **`signature-mmd` is a name with nothing behind it.** It is in the schema enum
  and the pydantic mirror, and the registry has no factory for it — by design
  (`worldspec.py:56`: "raises `UnknownGeneratorError` until something registers
  under it"), but a world declaring it is constructible and unrunnable.

### 5.2 Two institutions are live at once, and both reach the player

`ah/play.py` (cash account, calls, forced sales) is what scores. `ah/core/institution.py`
(eight weights, no cash, nothing can be owed) is Step 0's toy. The toy is still
wired into surfaces the player sees:

- `bundle.py:98` computes the **toy** twin (`hold_course_twin`) and `:160` writes
  its final value into `summary.twin_final_value` (and `run` puts the same number
  into `summary_stats.final_of_100`, `cli.py:224`);
- `bundle.py:158` puts the **port** twin's ledger into `twin_ledger`;
- `feed.py:175,180` builds the quarterly institution statement and its peer bands
  from `simulate_institution` — the toy;
- `inspect.py`, `tournament.py` and `density.py` all run the toy.

This is not theoretical. In the single bundle I built from the stagflation
preset (run `03a76c08…`, seed 771204, 200 paths):

```
summary.twin_final_value          = 166.502   (toy institution)
twin_ledger.nav_reported[-1]      =  76.712   (port institution — the one that scores)
```

The same file states the same institution's terminal value twice, 2.2× apart,
and the wire the player reads is narrated off the higher one. The bundle
docstring's own framing ("the HOLD-COURSE TWIN's cashflows") is accurate for
`twin_ledger`; `summary.twin_final_value` is the leftover.

### 5.3 ER-6: about 29% of every commitment is never called

`docs/engine-realism-register.md` §ER-6, status **open**, dated 2026-08-05. The
call curve is an ALB-A placeholder that was never fitted; measured at
`committed = 1.0`, paid-in reaches 0.7075 over the contractual life against an
allocator's 85–95% expectation. Downstream, `peak_unfunded_ratio` flags on all
four presets (3.018 / 2.445 / 3.308 / 2.453 against a declared 0.25–0.75) and
the J-curve crossover lands at ~8.5 years against a declared 4–8. On
`deflation_bust` no year-1 vintage crosses over within the decade at all. The
register is explicit that this is a prerequisite for the commitment lever (E1),
not a parallel cleanup.

Two further register entries are open: **ER-2** (the policy rate is a continuous
drift with no meeting calendar and no 25bp quantisation) and **ER-5** (the crisis
is a rectangular block, giving equity an ACF of 0.364). ER-1 and ER-4 are closed
in `toy-v0.3`; **ER-3 is closed in the play surface** (`wire-play-surface`) — a
different layer, since ER-3 was the no-cashflow gap and was fixed in `ah/port/`,
not in the return process.

### 5.4 The leaderboard is unreachable from the dev app

`app/src/lib/session.ts:176` fetches `/leaderboard/{worldId}`. `app/vite.config.ts:8`
proxies **only** `/sessions`. Verified against the running dev stack:

```
GET http://127.0.0.1:8787/leaderboard/x?seed=1&alpha_version=1.0  → 200 application/json
GET http://localhost:5173/leaderboard/x?seed=1&alpha_version=1.0  → 200 text/html      (vite's SPA fallback)
GET http://localhost:5173/sessions/nope                            → 404 application/json (proxied correctly)
```

The client parses the SPA's HTML as JSON and throws; `Leaderboard.tsx:31` catches
it and renders the error string in place of the board. The server side is fine —
the same request direct to 8787 returns a well-formed empty board. It is a
one-line proxy entry.

### 5.5 `ruff format --check .` fails on `main` today

ruff 0.16 formats Python code blocks inside Markdown, and two committed plan
documents contain unformatted blocks:

- `docs/superpowers/plans/2026-08-04-private-programme-console-section.md`
- `docs/superpowers/plans/2026-08-05-world-and-wire-audit.md`

`uv.lock` pins ruff 0.16.0 and CI runs `uv sync --frozen`, so CI's lint step
would take the same view. `ruff check .` and `pyright` are both clean; this is
the formatter alone, and `ruff format` on those two files fixes it.

### 5.6 The battery CI step cannot fail

`.github/workflows/ci.yml` runs `python -m ah.battery.report` as a gate, but
every threshold in `src/ah/battery/thresholds.yaml` is `status: todo`, and
`BatteryReport.passed` is `not enforce_failures` (`battery/report.py:58-64`).
With no `enforce` metric the step is green by construction. The file is candid
about this ("placeholders documenting intent, not ratified thresholds") — the
gap is that CI presents it as a gate.

The CI step is also mislabelled. It is titled "Validation battery (stagflation
preset)", but `main()` runs `_stagflation_ensemble()` (`battery/report.py:189-196`),
which loads `schemas/example-long-stagflation.worldspec.json` — a schema example,
not `src/ah/presets/stagflation.json` — forces `generator_id = "toy-v0"`, and runs
**64 paths at `base_seed=42`**, not the preset's 1000 at 771204.

Note the Step-2 battery (`ah/eval/battery.py`) *does* have real, sealed
thresholds and all eight suites registered
(`_REFERENCE_DEPENDENT_SUITE_BUILDERS`, `battery.py:955`); the two are different
objects with similar names.

### 5.7 Tier-2 authoring passes its bar and still ships nothing

`governance/evidence/AUTHORING-REGRESSION.md` records the current run as **30/30,
100.0% first-pass, "ships: YES"** against the frozen ≥95% bar, and
`governance/evidence/G4-EVIDENCE.md` closes criterion 1 at 96.7%/100.0%. But
every bundle still stamps:

```
meta.artifact_tier = "tier-1 templated wire (build-time, deterministic);
                      tier-2 letters await the frozen >=95% first-pass bar"
```

(`bundle.py:139-142`, and I read it back out of a freshly built bundle).

The string is stale, but the deeper point is that it describes the wrong rule.
The ratified decision, PD-4 (`Instructions/KICKOFF-PRODUCT-SU.md:78`), is
**key-conditional, not bar-conditional**: "tier-1 deterministic always; tier-2
letters *when a key is present at build*, recorded in the bundle either way."
`bundle.py` has no such branch — it never imports `ah.artifacts.author`, so a key
present at build time would change nothing. The stale string is the symptom; the
missing PD-4 branch is the gap.

Also unbuilt: G3's leak-checker prompt over the draft, recorded as v1.1 in
`artifacts/gate.py`'s docstring, and G6 which warns "not evaluated" unless past
artifacts are supplied.

### 5.8 Documentation that no longer matches the code

| claim | where | what the code says |
|---|---|---|
| bundle contract is `world-bundle-0.3` | `CLAUDE.md` §Architecture | `bundle.py:56` — `world-bundle-0.4` |
| "`ah/pacing.py` is a display-only toy ledger" | `CLAUDE.md` §Architecture | the module was **deleted** in `168cd22` ("retire ah/pacing.py"); only a stale `.pyc` remains. The pacing table lives in `mappings/pacing-parameters-v1.0.yaml` |
| `docs/tier1-synthesis-and-decisions.md`, named by Step 2's vendoring list | `CLAUDE.md` | still missing — confirmed absent |
| "CLI-echoed strings stay ASCII" | `CLAUDE.md` §Environment gotchas | `data/episode.py:107` emits an em-dash, echoed via `typer.echo(pack.brief)` at `data/cli.py:154`. It does not crash — exit 0 under PowerShell with the dash rendering correctly — but it renders as `?` in Git Bash. (`data/reports.py`'s em-dashes are **not** a deviation: they are in the module docstring and in the generated `GAPS.md`, which CLAUDE.md explicitly permits Unicode in) |
| "`app/fixtures/toy.bundle.gz` is a committed bundle **both suites** verify" | `CLAUDE.md` §Regenerating fixtures, repeated in `CHANGELOG.md` | only the TypeScript suite reads it (`app/src/lib/bundle.test.ts:22`). No file under `tests/` mentions it; `tests/test_bundle.py` builds its own bundle. The two seal implementations are **not** pinned against a shared fixture — which is the property the sentence is claiming |

### 5.9 Gate state, carried forward and re-checked

These are the project's own recorded positions, verified against the evidence
files rather than restated from the status table:

- **Step 3's G1-completion is an honest FAIL** — `G1-EVIDENCE.md`: `mark_lag`
  (must-pass) failed at 0.9667 and `private_weight_breach` failed at 0.0332.
  Tier 1 beat tier 0 (2 criteria failed vs 3). **G3 itself was never taken.**
- **The holdout is spent** — declined at G2 on purpose, spent at WP5.6.
  `RESEARCH-EVIDENCE.md`: primary drawdown surprise −0.3952, realized terminal
  wealth at the 99.6th percentile of the ensemble, `cpi` band coverage 0.000,
  and `fx_usd` went unread because of a reader fallback bug that, per the sealed
  spec, publishes as a gap rather than re-running.
- **The severe test is inconclusive** and the L3 leg structurally vacuous
  (0 blocks dropped) — `artifacts/wp211/SEVERE-TEST.md` via `RESEARCH-EVIDENCE.md`.
- **The standing caveat** — `hier-flow-v1` beats the benchmark on the sealed
  criterion and is not a convincing model of history: regime persistence
  undercalled, drawdowns understated ~2×, the decade tier 73% structurally
  unavailable (`G2-EVIDENCE.md` §7–8). Nothing built on it is decision-ready.

### 5.10 Named-but-absent, and deferred-by-decision

- **`ah audit`** — 2,287 lines of design and implementation plan merged at
  `545a2ac`; no code, no CLI command.
- **Drift twin** — the third analysis series is a `None` in the API contract
  (`serve.py:300`), by design, so its arrival is a data change.
- **E1 commitment lever** — `Instructions/experience-deltas-register.md` marks
  E1, E2 and E4 **PARTIAL**, E3 and E5 **OPEN**, E6 **OPEN** (I5's ~20-user
  first-run observation deferred under D-K4-5), E7 and E8 **CLOSED**.
- **Auth** — deliberately absent at v0.1 (`serve.py:8-10`); required before any
  external user.
- **Human-cohort benchmark and the too-rational pathology** — deferred by owner
  decision D-K4-5, recorded in `G4-EVIDENCE.md` criterion 4/5 rather than
  proxied with a number.
- **Fee/carry on the play path** — `simulate_play` steps cohorts directly
  (`play.py:385`) and never calls `run_tier1`, so the management fee, the
  European carry, recycling, subscription-line deferral and extension behaviour
  that `cashflow_tier1.py` implements are **not applied to the scored
  institution**. Whether that is intended is not stated anywhere I found.
- **Preset structural coverage** — three of four presets carry only
  `parameter_vintage` under `structural`; the toy engine falls back to `_DEF`
  (`engine.py:89-106`) for private-market parameters in those worlds.

### 5.11 A secondary sale relieves nothing — the obligation survives it

This is on the scored path, and it inverts the sign of the only liquidity lever
the player has.

Both the voluntary sale (`play.py:298-307`) and the forced secondary
(`port/engine.py:136-140`) reduce `cohort.nav_true` and `cohort.nav_reported` and
credit cash. **Neither touches `unfunded` or `committed`.** Nothing else does:
in `port/cohort.py`, `unfunded` moves only in `step()` (`:200`) and `recall()`
(`:233`); `report()` (`:207-211`) writes the mark and returns. And calls are
sized `call = min(self.unfunded, call_rate * self.unfunded)` (`cohort.py:185`) —
a function of the unfunded balance, independent of NAV.

So you sell an LP interest at a 19% haircut, keep 100% of the future call
obligation, and — since coverage is unfunded ÷ what you own — **coverage gets
strictly worse after the one action that exists to relieve liquidity stress**. A
cohort driven toward `nav_true ≈ 0` by repeated forced secondaries keeps calling
at full size. Not in `docs/engine-realism-register.md` (ER-1…ER-6 do not reach
it).

### 5.12 Two writers to the leaderboard, and a version-label collision

The `decision_alpha_version` column is the mechanism that is supposed to keep
incompatible scores off one board (`db.py:92`, `UNIQUE(world_id, seed,
decision_alpha_version, participant)`). Three numeric definitions exist and two
of them share a label:

| writer | label | institution | metric |
|---|---|---|---|
| `serve.py:257` | `port-v1-cashflow` | port (cash account) | terminal value difference |
| `tournament.py:268` | **`1.0`** (from `store/runrecords.py:27`) | **toy** (§5.2) | terminal value difference |
| `eval/decision_metrics.py:21` | **`1.0`** (sealed under G5) | — | log points, `ln(player/twin)` |

`tests/test_play.py:167` asserts only that `PLAY_ALPHA_VERSION` differs from the
sealed constant; nothing pins `runrecords.py`'s constant against it. The comment
at `runrecords.py:22-24` ("inert… Nothing reads them yet") is stale —
`tournament.py` reads it and writes it to the board. Every bundle also stamps
`meta.decision_stamps.decision_alpha_version = "1.0"`.

### 5.13 Named-but-unwired, beyond §5.10

- **`src/ah/artifacts/chronicle.py`** — 88 lines implementing artifact
  publication as `type='artifact'` chronicle entries, described as the G9 record.
  Its only importer anywhere is `tests/test_artifacts_service.py`. §5.7 lists G3
  and G6 as the unbuilt gate pieces; G9's record is unwired too.
- **`scripts/build_artifact.py`** executes
  `Path("scratch_data.json").read_text(...)` **at module import** (`:9`). That
  file is not in the tree and never was (`git log --all` finds nothing). The
  script cannot be imported, let alone run — yet `CLAUDE.md` still lists it under
  "Regenerating committed fixtures/artifacts (all deterministic)".
- **`ah data intake apply`** — "Validate a drop AND apply it: write the vintage,
  run QC, advance on pass." A state-mutating command with no row in §2, which
  documents `intake validate` only.

### 5.14 Pacing is open-loop, and one fixture governs all three private sleeves

Three separate simplifications, none of them registered:

- **The commitment size never responds to anything.**
  `amount = START_TARGETS[asset] * _ANNUAL_COMMITMENT_RATE` (`play.py:213`) is a
  constant. Not a function of current NAV, the world, the coverage ratio, or any
  decision. A portfolio halved by a crash keeps committing ~6.3 points a year,
  driving private weight up mechanically at the worst moment.
- **PC and RE run buyout's cashflow profile.** `play.py:334` loads one base
  document and stamps `sleeve_id` onto copies (`play.py:217`);
  `mappings/pacing-parameters-v1.0.yaml` carries exactly one sleeve row,
  `pm_buyout`. Private credit and real estate therefore inherit buyout's
  `rc_curve`, bow 2.5, terminal yield 0.55 and 10-year life. There is no distinct
  PC or RE cashflow shape in the model at all.
- **Equity drawdown drives every sleeve's linkage.** `play.py:337-339` computes
  `drawdown_depth` from `q_returns["equity"]` alone and feeds the resulting
  `f_call`/`f_dist` to pe, pc *and* re.

ER-6 covers the *shape* of `rc_curve`. None of these three is in the register.

### 5.15 Smaller things that still change what a reader concludes

- **The decision actions are absolute point amounts that can silently truncate.**
  `_SHIFT_POINTS = 10.0` and `_SECONDARY_POINTS = 8.0` are value units on a book
  that starts at 100 and ends anywhere; at the ninth window on a book worth 76,
  "10 points" is 13% of it. Worse, `_rebalance` returns silently when the source
  leg is empty (`play.py:272-277`) and the secondary caps at available NAV
  (`:301`) — so a chosen action can execute partially or not at all and surface
  as a `0.0` window contribution **indistinguishable from `hold`**.
- **CI never runs the app, and never runs on Windows.** `ci.yml` has no Node
  step: the React suite (32 tests), its typecheck, its build, and the client-side
  seal implementation are all ungated. And `runs-on: ubuntu-latest` only — so the
  ASCII-CLI rule in §5.8 could not be enforced by CI even in principle.
- **CI never validates the promoted checkpoint.** Six tests skip when
  `experiments/` is absent — `tests/test_blocks_flow.py:689` ("no primary flow
  checkpoint present (pre-training checkout)"), `:806`, `:832`, `:855`,
  `test_blocks_diffusion.py:481`, `test_blocks_tuning.py:204`. On a clean CI
  clone all six skip. The "2,226 passed" figure in §4 is this machine's; CI sees
  fewer, and none of them exercise `hier-flow-v1`'s checkpoint.
- **28 of 157 modules under `src/ah/` have no inventory row**, including sealed
  judged code: `factors.py` and `strategies.py` (both in
  `pre-registration.lock`), `eval/reference.py` (2,540 lines, sealed in *both*
  `pre-registration.lock` and `pre-registration-g3.lock`), `eval/panel.py`,
  `eval/ablation.py`, `eval/sleevetails.py`, and `gen/base.py`. Worth noting
  against §5.9's "G3 itself was never taken": G3-pre's judged code exists and is
  sealed.
- **`README.md` still describes the repository as Step 0.** "This repository
  contains **Step 0** — 'lay the rails'… *No real market data, no ML training, no
  UI, and no LLM in the numeric path.*" Three of those four negations are now
  false (there is a real vintage store, there are trained models, there is an
  app); only "no LLM in the numeric path" still holds, and it is a standing
  invariant. Its architecture tree lists six components and omits `data/`,
  `gen/`, `eval/`, `port/`, `artifacts/` and `app/`. It is the repository's front
  door.
- **`app/README.md` is stale** — it describes `App.tsx` as "the v0.1 shell
  (browse mode; session binding is su-app-02)" and lists four files, written
  before `su-app-01…05` merged.
- **The governance registers are not read by this document.**
  `governance/retrofit-register.md` is an append-only log of **96 dated
  deferrals**, and neither this summary nor the manual cites it, the decision
  register, the amendment log, the model inventory, the prompt registry, or the
  EU AI Act mapping. One row bears directly on §5.9's standing caveat: **RFR-66**
  records that the G2 head-to-head is biased *toward* promotion by the
  benchmark's data window — `bootstrap-v1` can only resample 1990–2020 while the
  challenger saw 1929–33, 1937, 1973–74 and 1987, and both are scored against
  realizations that include all of it. It was sealed into the pre-registration
  rather than deferred. Anyone auditing §5 for completeness should read that file
  next; it is the project's own gap register and it is longer than this section.

---

*Evidence for every "working" claim in §2 is either a file:line in this
repository or a command I ran on 2026-08-05; the commands and their real output
are in `docs/USER-MANUAL.md`. Anything I could not verify is marked, and the
full list of what I could not verify is in the closing note of that document.*
