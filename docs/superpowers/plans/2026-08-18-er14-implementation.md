# ER-14 close-out release — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking. One reviewed commit per task; a
> review after each task and a whole-WP review before each WP merge.

**Goal:** make private markets feel inflation — four economic channels written into the
return process on both the toy and the generated plane, a fourth private class
(infrastructure) in the played book, and the release mechanics (engine/alpha version
bumps, world fences, retirement, reseal batching F5) that a return-process change
obliges — inverting ER-14 against acceptance tests AT-1..AT-14.

**Architecture:** one derived state variable (`inflation_excess`, a 24-month trailing
mean of the engine's already-simulated inflation path, demeaned at 2.0%) feeds four
return equations in `src/ah/core/engine.py`; a fifth asset (`infra`) joins `ASSETS`,
`PRIVATE_ASSETS` and the played book with its Student-t draw **appended last** to the
existing draw block; the generated plane gets the same channel through a new sealed
mapping artifact `mappings/sleeve-mappings-v1.2.yaml` (C1 + the `pm_buyout` extension +
F5a/F5b/F5c), adopted through the amendment log with a single G3 reseal. No sealed
file's *contents* are edited; `schemas/` is untouched.

**Tech stack:** Python 3.12 (uv), numpy, pydantic + jsonschema, FastAPI, SQLite,
pytest (`--disable-socket`), ruff, pyright; React/TypeScript + Vite + vitest in `app/`.

**Authority documents — read all four before Task 1:**

| Document | What it binds |
|---|---|
| `docs/superpowers/specs/2026-08-18-er14-close-out-design.md` | the ratified design; both revisions; §2 mechanisms, §6 acceptance tests, §7 release checklist |
| `governance/decision-register.md` → `D-ER14-1` | the charter: the close-out is funded, batched with F5; ratification precedes sealing |
| `governance/decision-register.md` → `D-ER14-2` (commit `4c00877` on `main`) | the ratification: all fifteen coefficients, the sleeve GO, CDLI decoupled, 7xx/8xx retired, **AT-14 mandated verbatim** |
| `docs/engine-realism-register.md` → ER-14, ER-15, ER-11, ER-12 | the defect being closed, the side effects accepted, the constraints carried |

**Ratified coefficients (D-ER14-2, A1 — do not re-derive, do not adjust):**

| Symbol | Value | Where it lands |
|---|---|---|
| `C_ANCHOR` | 2.0 % | `INFLATION_ANCHOR_PCT` |
| `K` | 24 months | `INFLATION_TRAIL_MONTHS` |
| `λ_RE` | 0.30 | `_LAMBDA_RE` |
| `γ_RE` | 0.50 | `_GAMMA_RE` |
| `λ_PE` | 0.35 | `_LAMBDA_PE` |
| `μ_PE` | 0.45 | `_MU_PE` |
| `φ_PC` | 1.0 | `_PHI_PC` |
| `ω_PC` | 0.03 | `_OMEGA_PC` |
| `θ_toy` | 0.10 | `_THETA_TOY` |
| `λ_INFRA` | 0.60 **default only** — read live from `structural.infrastructure.inflation_linkage` | `_DEF["infra_linkage"]` |
| `γ_INFRA` | 0.30 | `_GAMMA_INFRA` |
| `β_INFRA` | 0.33 | `_BETA_INFRA` |
| `σ_INFRA` | 1.65 | `_SIGMA_INFRA` |
| `infra_yield` | 5.0 %/yr | `_DEF["infra_yield"]` |
| infra crisis term | −0.5 | `_INFRA_CRISIS` |
| (constraint) | `abs(λ_PE − μ_PE) >= 0.06` | asserted by a test, A3 |

Reused, **not** new: `D_RE = D_INFRA = 4.0` (the engine's existing `-4.0*d_rate`
property duration) and `s̄ = _SPREAD_REFERENCE_BPS = 400.0`.

---

## Global constraints

Every task's requirements implicitly include this section.

- **The three seal locks.** Grep and verify all three **before the first edit and
  again before the merge** — never only G3 (memory rule: three locks share
  `factors.yaml`, `src/ah/eval/prereg.py`, `src/ah/splits.py`):

  ```bash
  uv run python -c "from ah.eval.g3seal import verify_g3; print(verify_g3())"
  uv run python -c "from ah.eval.g5seal import verify_g5; print(verify_g5())"
  uv run python -c "
  from pathlib import Path; from ah.eval.prereg import load, verify; from ah.factors import load_manifest
  p = load(Path('pre-registration.yaml')); verify(p, load_manifest(), lock_path=Path('pre-registration.lock')); print('main lock OK')"
  ```

  - `pre-registration.lock` (main, 44 files, digest `sha256:7421dd3e…`, sealed 2026-08-10)
    hashes `factors.yaml`, `pre-registration.yaml`, 8 conditional worldspec fixtures,
    `src/ah/battery/{report.py,stylized.py,thresholds.yaml}`, nine `src/ah/data/*.py`
    extenders + 2 JSONs, `src/ah/eval/{ablation,battery,g2,negative_controls,panel,prereg,reference}.py`,
    all ten `src/ah/eval/metrics/*`, `src/ah/{factors,splits,strategies}.py`.
    **UNTOUCHED — required.** The battery *runs*; nothing hashed is *edited*.
    `src/ah/core/engine.py` is in **no** lock, and neither is any `src/ah/port/` module.
  - `pre-registration-g3.lock` (26 files, digest `sha256:45c80506…`, sealed 2026-08-12)
    hashes `factors.yaml`, `mappings/{cashflow-tier0-v1.0,cashflow-tier1-v1.0,sleeve-mappings-v1.0,sleeve-mappings-v1.1,smoothing-kernel-v1.0}.yaml`,
    `pre-registration-g3.yaml`, six `scripts/*.py`, `src/ah/data/{derive,desmooth,taxonomy}.py`,
    `src/ah/eval/{episode2022,g3seal,prereg,reference,sleevetails}.py` + 2 metrics,
    `src/ah/splits.py`, `taxonomy/{albourne_mapping,sleeves}.yaml`.
    **RESEALED exactly once**, in WP `er14-05`, when `mappings/sleeve-mappings-v1.2.yaml`
    and `scripts/estimate_sleeve_mappings_v1_2.py` join `seal_scope.hashed_files`
    **together** (the AM-2026-08-15-001 planned-arrival pattern). **No existing hashed
    file's contents are edited** — v1.0 and v1.1 are never touched.
  - `pre-registration-g5.lock` (7 files, digest `sha256:0596b861…`, sealed 2026-08-10)
    hashes `Instructions/holdout-evaluation-spec.md`, `factors.yaml`,
    `src/ah/eval/{decision_metrics,g5seal,prereg}.py`, `src/ah/splits.py`,
    `step5-evaluation-protocol.yaml`. **UNTOUCHED — required.**
    `decision_alpha_version` is **not** bumped (a test asserts it).
  - **The mapping amendment path.** `mappings/cashflow-tier1-v1.0.yaml` is inside the G3
    lock and is **NOT edited** — D-ER14-2 ratified the §3 recommendation (cashflow timing
    stays inflation-blind; returns respond and cashflows follow derivatively). If anyone
    proposes editing it, or `mappings/sleeve-mappings-v1.0/v1.1.yaml`, that is a **STOP**:
    it needs its own owner decision, a new amendment-log entry, and a re-check of all
    three lock scopes (main / G3 / G5) — not a task in this plan. The only artifact this
    release adds is `mappings/sleeve-mappings-v1.2.yaml`, through
    `governance/amendment-log.yaml` (a new dated entry **extending** AM-2026-08-15-001,
    `post_hoc: true`, trigger named as ER-14, ratified coefficients written into the entry
    **before** the estimator runs), plus a `pm_infra` row in
    `mappings/pacing-parameters-v1.0.yaml` — which is in **no** lock but is owner-approved
    (WI-I6-1, 2026-08-02) and drift-guarded by `tests/test_pacing_artifact.py`, so it is
    an owner event, not a free edit.
- **Version stamps and world fences move exactly once, in `er14-05`:**
  `TOY_ENGINE_VERSION` `toy-v0.6` → `toy-v0.7` (`src/ah/core/engine.py:56`);
  `PLAY_ALPHA_VERSION` `port-v4-ladder` → `port-v5-inflation` (`src/ah/play.py:92`);
  `GEN_PLAY_ALPHA_VERSION` `port-v4-ladder-gen` → `port-v5-inflation-gen`
  (`src/ah/port/adapter.py:108`) — **distinct values, never a shared bump**;
  `decision_alpha_version` **untouched**. Toy preset world ids move `…511-515` →
  `…521-525` (the `52x` sub-block = toy-v0.7, per `scripts/gen_presets.py`'s documented
  convention); the played generated preset moves `…603` → `…604`; the campaign/spine
  worlds `…701`, `…703`, `…801`, `…802` are **RETIRED, not renumbered** (D-ER14-2).
- **ER-15 session demotion is an accepted side effect.** The default opening book gains
  a fourth private sleeve, so its digest moves and every in-flight session is
  invalidated — old three-sleeve posts demote to practice. Correct behaviour; it must be
  **announced** in `CHANGELOG.md` and the ER-14 close-out entry, never discovered.
- **ASCII only in anything CLI-echoed** (Windows console is cp1252; `→` crashes it).
  Markdown, docstrings and the app may use Unicode freely.
- **Determinism.** All randomness flows from one integer seed through
  `numpy.random.Generator(PCG64(seed))`. **No new unseeded randomness.** The one new
  stream (`e_infra`) is **appended at the end** of `run_path`'s up-front draw block —
  see AT-14, quoted verbatim in its task — and a distinct-tape test proves it is a
  different tape from every existing stream.
- **Never weaken a test.** No threshold is moved to accommodate a result (AT-9). If a
  test written to catch a defect starts failing because the defect is fixed, **invert
  it** and keep the history in the docstring. No `skip`/`xfail` without a linked TODO.
- **`schemas/` is read-only vendored truth** and is not edited. It does not block this
  release: no schema enumerates the asset or sleeve set; `worldspec-v1.3.schema.json`
  already carries `structural.infrastructure.{discount_rate_shift_bps,inflation_linkage}`
  and `structural.smoothing.weights_on_truth.infrastructure`, and
  `src/ah/core/worldspec.py` already mirrors them (`class Infrastructure`, line 331).
  The one genuine contract limitation — `structural.infrastructure` has **no**
  income-yield field, so `infra_yield` stays a hardcoded engine constant — is recorded in
  ER-14's unconsumed/unavailable-field map, not designed around.
- **Narrative-blindness holds.** Every new term reads continuous state
  (`inflation`, `spread_lagged`) or a declared structural parameter
  (`inflation_linkage`); none reads a regime label or a narrative field.
- **No network** in tests or CI (`pytest-socket`). Fixtures are committed and
  deterministic.
- **Lint before the long gate:** `uv run ruff check . --fix`, `uv run ruff format .`,
  `uv run pyright`, and (for app work) `cd app && npm run typecheck && npm run test &&
  npm run build` — all clean **before** starting a ~38-minute gate.
- **Dependencies:** no new ones. Anything else needs a stated justification and an owner
  decision.

---

## Branch strategy — chosen, with reasoning

**One release branch, `er14-release`, off `main`; each WP on its own sub-branch merged
`--no-ff` into it; exactly one `--no-ff` merge into `main`, behind one full green gate.**

```
main
 └── er14-release                      (integration; the only branch that merges to main)
      ├── er14-02-mechanisms   --no-ff→ er14-release
      ├── er14-03-credit       --no-ff→ er14-release
      ├── er14-04b-sleeve      --no-ff→ er14-release
      ├── er14-04c-app         --no-ff→ er14-release
      └── er14-05-release      --no-ff→ er14-release   → full gate → --no-ff → main
```

Why not five independent merges to `main`, which is the house default:

1. **The suite is legitimately red between the first mechanism commit and the re-pin
   sweep.** Changing three return equations invalidates every value golden, every run
   digest and both committed bundles. A WP that merged to `main` before the re-pin
   would land a red `main`; a WP that re-pinned early would re-pin the same goldens
   three times, tripling the exposure to the `artifact-repoint-consumer-sweep` failure
   (a missed consumer costing a red gate).
2. **The release is atomic by construction.** `TOY_ENGINE_VERSION`, the play-alpha
   stamps and the world fences move **once**. A half-merged release would ship an engine
   whose numbers had changed under world ids that had not moved — precisely the
   leaderboard collision the fences exist to prevent.
3. **The house rule is preserved where it does work.** One WP per branch, one reviewed
   commit per task, a whole-WP review before each sub-merge. `githooks/commit-msg` only
   requires a `.gate-ok` stamp when merging **into `main`** (verified: it tests
   `branch = main` and `MERGE_HEAD`), so sub-merges into `er14-release` are legal and
   the single stamped gate still guards `main`.

**The red ledger (how a red tree stays honest).** Because the suite is red mid-release,
each WP must account for every failure. Maintain `docs/superpowers/plans/er14-red-ledger.md`
on `er14-release`: one line per failing test id, its cause (`value-golden`,
`world-id-pin`, `bundle-fixture`), and the WP that will clear it. Rules:

- A failure **not** on the ledger is a **STOP** — diagnose before proceeding.
- Every WP close-out task appends its new expected-red entries and re-runs the suite to
  confirm the failing set equals the ledger exactly.
- `er14-05` Task R4 drives the ledger to empty and **deletes the file** in that commit.
  The ledger never reaches `main`.

**Definition of done — per task:** the task's tests pass, the task's own acceptance
criteria are met, `ruff` + `pyright` clean for touched files, one commit whose body
states (a) what was built, (b) deviations with reasons, (c) anything discovered that
affects later WPs.

**Definition of done — per WP (sub-merge into `er14-release`):** all tasks complete;
`uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright` clean tree-wide;
the targeted suites named in the WP's close-out task green; the full suite's failing set
equals the red ledger exactly; `CHANGELOG.md` updated with one entry per task;
whole-WP adversarial review done and findings fixed; merge `--no-ff` into `er14-release`.

**Definition of done — the release (merge into `main`):** the red ledger is empty and
deleted; all three lock digests verified; lint clean; app `typecheck`/`test`/`build`
clean; then the full gate in the background —
`uv run python scripts/run_gate.py gate-er14.log` — read the `EXIT:` line and the pass
count from the log (never chain a merge onto a `tail`); `uv run python scripts/check_gate.py gate-er14.log`;
re-verify `HEAD` equals the stamp (the owner commits onto branches mid-gate);
`git merge --no-ff` into `main`; plain push (standing authorization; **never** force-push).
Restart the 8787 session service from the merged tree.

---

## File structure

**Modified — engine and product (no new production modules):**

| File | Responsibility after this release |
|---|---|
| `src/ah/core/engine.py` | the four inflation channels, the shared `inflation_excess` helper, the `infra` return, `ASSETS`/`REPORTED_SLEEVES` gaining `infra`, `TOY_ENGINE_VERSION` |
| `src/ah/play.py` | `PRIVATE_ASSETS` 4-tuple, re-carved `START_TARGETS`, `PLAY_ALPHA_VERSION`, the explicit infra secondary-sale exclusion |
| `src/ah/core/institution.py` | `START_MIX` gains infra (no `GROWTH`/`DEFENSIVE` entry) |
| `src/ah/port/adapter.py` | generated-plane targets/mix/order, `PM_SLEEVE_FOR_ASSET["infra"] = "pm_infra"`, the v1.2 artifact's `b_infl` channel, Student-t + PM block residuals (F5c), `GEN_PLAY_ALPHA_VERSION` |
| `src/ah/port/mapping.py` | `_cta_rule` consumes the v1.2 EWMA vol + position cap (F5a) |
| `src/ah/serve.py` | four-sleeve opening book, moved book digest, the announced ER-15 demotion |
| `src/ah/cioview.py` | `GOAL_OF`/`CLASS_LABEL`/`BAND_PCT` gain infra |
| `src/ah/bundle.py` | `BUNDLE_VERSION` bump for the changed series set |
| `scripts/gen_presets.py`, `scripts/gen_prehistory_preset.py` | the `52x` world-id block; `entry_multiple_drift_annual_pct = 0.0` on the live presets |
| `scripts/estimate_sleeve_mappings_v1_2.py` | emits the v1.2 artifact with C1 (+`pm_buyout`), F5a, F5b, F5c, and **without** the CDLI-blocked C2 block |
| `mappings/pacing-parameters-v1.0.yaml` | gains the `pm_infra` row (`contractual_life_years: 15`) |
| `pre-registration-g3.yaml` | `seal_scope.hashed_files` gains the v1.2 pair |
| `governance/amendment-log.yaml` | one new appended entry extending AM-2026-08-15-001 |
| `app/src/…` | a fourth private asset class through `Play.tsx`, `BookEntry.tsx`, `CioDashboard.tsx`, `VintageChart.tsx`, `DecisionWindow.tsx` and the label maps |

**Created:**

| File | Responsibility |
|---|---|
| `tests/test_er14_inflation.py` | AT-1..AT-8, AT-11, AT-12 (the probe suite) |
| `tests/test_er14_streams.py` | AT-7, AT-14 and the stream-corruption guards |
| `scripts/gen_er14_baseline.py` | captures the two reference baselines (toy-v0.6 publics; the no-infra build) |
| `tests/fixtures/er14/public-baseline-toy-v0.6.npz` + `.json` | AT-6b's reference |
| `tests/fixtures/er14/no-infra-baseline.npz` + `.json` | AT-14's reference |
| `scripts/measure_er14_response.py` | the close-out measurement run (AT-2/3/4/5/8/11/12/13 numbers → `artifacts/er14/response.json`) |
| `mappings/sleeve-mappings-v1.2.yaml` | the generated plane's inflation channel + F5 (sealed on arrival) |
| `docs/superpowers/plans/er14-red-ledger.md` | transient; deleted in `er14-05` |

**Deliberately NOT touched:** `schemas/`, `mappings/cashflow-tier1-v1.0.yaml`,
`mappings/sleeve-mappings-v1.0.yaml`, `mappings/sleeve-mappings-v1.1.yaml`,
`src/ah/port/smoothing.py` (ER-11: the shipped reported plane is the engine's own
filter), `src/ah/eval/*` (all three locks), `scripts/gen_fixtures.py` (validator-level;
if its output changes — **STOP**).

---

## Plan-level risks

| # | Risk | Why it is first / how the plan handles it |
|---|---|---|
| **R-1** | **Silent corruption of every world by RNG draw order** (design §2.7.2). Adding `e_infra` anywhere except the end of `run_path`'s up-front draw block shifts every subsequent stream, changing `e_pe`/`e_pc`/`e_re` and — through the common-factor construction — the public assets too, in every world, invisibly, with no test naming the cause. | **The highest-risk line in the release and it is one line.** AT-14 is quoted verbatim in Task S1, the draw is appended last, `tests/test_er14_streams.py` compares against a committed pre-sleeve baseline, and Task S1's step 6 is a mandatory break-and-revert: insert the draw at the top, watch AT-14 go red, revert. |
| R-2 | The golden re-pin sweep overruns or misses a consumer (the ER-10 precedent: a strictly smaller change still produced a red gate from a missed consumer). | The sweep is its own task (R4) with a mechanical attribution rule — every failure is (a) a value golden, (b) a world-id pin, (c) **STOP** — driven by the red ledger, and it runs the FULL suite to a log, never a subset. |
| R-3 | A coefficient gets "improved" during implementation. | Every value is ratified in D-ER14-2 and tabled above; a task that wants a different number **stops and asks**. Tests assert the constants' values, including `abs(λ_PE − μ_PE) >= 0.06` (A3). |
| R-4 | The reseal touches more than intended (three locks share `factors.yaml`, `prereg.py`, `splits.py`). | All three digests are verified before the first edit and again before the merge; only `pre-registration-g3.yaml`'s `seal_scope` list changes, and `seal_g3` is minted once with the superseded digest recorded in the amendment entry. |
| R-5 | `stagflation_1974` (`…603`→`…604`) and `spine_pilot` (`…802`, retired) are consumed by the **active** spine/stage2 track on other branches. Retiring or renumbering mid-flight breaks work in progress. | Task R3 lists every consumer found (`tests/test_gen_adapter.py:392`, `scripts/spine_pilot_report.py:676`, `scripts/spine02_report.py:303` — the last two cite ids in prose only). **Before starting `er14-05`, confirm with the owner that no spine run is in flight**; the merge is a coordination event, not just a gate. |
| R-6 | D-ER14-2 says "the six presets' `entry_multiple_drift` zeroed" **and** says 7xx/8xx are retired records that must not be rewritten. Zeroing a retired world's authored field edits a record. | Resolved in Task M5: zero the **two live** presets (`stagflation`, `stagflation_1974`); leave the four retired JSONs byte-identical — a retired world never runs under `toy-v0.7`, so no double charge can occur. Flagged in the commit body and the close-out entry as a deviation from the literal wording, reversible in one line if the owner prefers all six. |
| R-7 | The battery moves outside its bands and the temptation is to re-band. | AT-9 is a **disclosure rule**: every moved stylized fact is disclosed in the close-out; `src/ah/battery/thresholds.yaml` is inside the main lock and is never edited. If a band edit is proposed — **STOP**. |
| R-8 | The `world-bundle` contract's series set changes and an app decoder pins it. | Task S6 greps every decoder for a pinned count/version before writing anything; the contract version is bumped and both committed bundles rebuilt; if a decoder pins a count that cannot be moved — **STOP and decide**. |
| R-9 | PE's net (−0.10) is a small difference of two larger ratified numbers; a sign flip would re-create ER-14 in weaker form. | AT-2 is a **materiality** test (≥ 0.65 pp/yr), and Task M5 asserts the ratified net-floor constraint directly on the constants. |
| R-10 | The generated plane cannot ship its C2 half (CDLI/Cliffwater export not in hand). | D-ER14-2 decoupled it: the v1.2 artifact ships **C1 only** (plus F5); the toy plane's convexity ships as the declared engine constant `θ_toy = 0.10`. Task G1 makes the estimator's `--theta` optional and records the omission in the artifact and the report. |

---

# WP `er14-02` — the mechanisms (branch `er14-02-mechanisms`)

**Scope:** the shared state variable, real estate, private equity, the infrastructure
return *mechanism* (as a pure function — the sleeve is wired in `er14-04b`), rider R1,
and the two reference baselines. **Discharges AT-1, AT-2, AT-3, AT-6a (pe/re),
AT-6b, AT-8.**

Branch from `er14-release` (which is branched from `main` at the ratification commit
`4c00877` or later).

---

### Task M1: capture the toy-v0.6 baselines and record the defect one last time

**Files:**
- Create: `scripts/gen_er14_baseline.py`
- Create: `tests/fixtures/er14/public-baseline-toy-v0.6.npz`
- Create: `tests/fixtures/er14/public-baseline-toy-v0.6.json`
- Create: `tests/test_er14_inflation.py` (AT-6b only in this task)
- Create: `docs/superpowers/plans/er14-red-ledger.md`

**Interfaces:**
- Produces: `scripts/gen_er14_baseline.py::build(out_stem: str, assets: tuple[str, ...]) -> None`
  writing `<out_stem>.npz` (per-preset float64 arrays, key `"<preset>/<asset>"`) and
  `<out_stem>.json` (`{"<fixture-stem>/<asset>": "sha256:…"}` for the 51 compiler
  fixtures, via `ah.core.digest.sha256_of_arrays`).
- Produces: `tests/test_er14_inflation.py::PUBLIC_ASSETS = ("equity", "bonds", "hy", "commodities", "reits")`.

**Why this task exists first.** AT-6b compares against `toy-v0.6`. The reference has to be
taken on a clean tree **before any mechanism edit**, or there is nothing to compare with.

- [ ] **Step 1: write the baseline generator**

```python
"""Capture engine return baselines for the ER-14 release (AT-6b, AT-14).

Two references are needed and neither can be reconstructed after the fact:
  * the toy-v0.6 PUBLIC-asset streams, proving the release moves nothing it
    should not (AT-6b);
  * the post-mechanism, PRE-SLEEVE streams for all eight assets, proving the
    appended e_infra draw shifts nothing (AT-14, design 2.7.2).

Presets are stored as raw float64 arrays (exact comparison); the 51 compiler
fixtures are stored as sha256_of_arrays digests (the repo's own 12-decimal
platform-determinism convention) to keep the fixture small.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ah.core.digest import sha256_of_arrays
from ah.core.engine import run_path
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
FIXTURES = ROOT / "fixtures" / "compiler"
SEED = 12345


def _paths(doc: dict) -> object:
    return run_path(project_numeric(load_worldspec(doc)), SEED)


def build(out_stem: str, assets: tuple[str, ...]) -> None:
    arrays: dict[str, np.ndarray] = {}
    for path in sorted(PRESETS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        paths = _paths(doc)
        for asset in assets:
            arrays[f"{path.stem}/{asset}"] = np.asarray(paths.returns[asset], dtype=np.float64)
    np.savez_compressed(ROOT / f"{out_stem}.npz", **arrays)

    digests: dict[str, str] = {}
    skipped: list[str] = []
    for path in sorted(FIXTURES.glob("*.json")):
        if path.name == "_manifest.json":
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        try:
            paths = _paths(doc)
        except Exception as exc:  # a fixture the validator/engine rejects by design
            skipped.append(f"{path.stem}: {type(exc).__name__}")
            continue
        for asset in assets:
            digests[f"{path.stem}/{asset}"] = sha256_of_arrays([paths.returns[asset]])
    (ROOT / f"{out_stem}.json").write_text(
        json.dumps({"digests": digests, "skipped": skipped, "seed": SEED}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"{out_stem}: {len(arrays)} arrays, {len(digests)} digests, {len(skipped)} skipped")


if __name__ == "__main__":
    build(
        "tests/fixtures/er14/public-baseline-toy-v0.6",
        ("equity", "bonds", "hy", "commodities", "reits"),
    )
```

- [ ] **Step 2: run it on the clean tree and commit the fixtures**

Run: `uv run python scripts/gen_er14_baseline.py`
Expected: `50 arrays` (10 presets × 5 public assets), a digest count of
5 × (the compiler fixtures that load), and the skip list. Record all three numbers in the
commit body. **If any preset fails to load — STOP**: that is a finding about the presets,
not this task.

- [ ] **Step 3: write the shared test helpers (used by every later AT task)**

```python
# tests/test_er14_inflation.py - the helper block. Defined ONCE here; Tasks M3,
# M5, C1-C4, S1 and G2 import these names and add no second implementation.
ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
FIXTURES = ROOT / "fixtures" / "compiler"
BASELINE_NPZ = ROOT / "tests" / "fixtures" / "er14" / "public-baseline-toy-v0.6.npz"
BASELINE_JSON = BASELINE_NPZ.with_suffix(".json")
ANCHOR_BASELINE_NPZ = ROOT / "tests" / "fixtures" / "er14" / "anchor-baseline-toy-v0.6.npz"
SEED = 12345
PUBLIC_ASSETS = ("equity", "bonds", "hy", "commodities", "reits")
STAGFLATION = PRESETS / "stagflation.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _set_dotted(doc: dict, dotted: str, value: float) -> None:
    """Set a dotted WorldSpec path, creating intermediate objects as needed."""
    node = doc
    *parents, leaf = dotted.split(".")
    for key in parents:
        node = node.setdefault(key, {})
    node[leaf] = value


def _world(infl_pct: float, preset: Path = STAGFLATION, **field_overrides):
    doc = copy.deepcopy(_load(preset))
    _set_dotted(doc, "factor_conditions.inflation.average_pct", infl_pct)
    for dotted, value in field_overrides.items():
        _set_dotted(doc, dotted, value)
    return project_numeric(load_worldspec(doc))


def probe(infl_pct: float, preset: Path = STAGFLATION, **field_overrides) -> EnsembleResult:
    """ER-14's own experiment, unchanged: one field varied, everything else held.
    200 paths, base_seed=12345 (design 6: reusing the exact experiment that found
    the defect is what makes 'inverted' mean something)."""
    return run_ensemble(_world(infl_pct, preset, **field_overrides), 200, base_seed=SEED)


def ensemble_of(preset_stem: str) -> EnsembleResult:
    """The preset AS AUTHORED - no field varied. Used by the world-basis tests."""
    doc = _load(PRESETS / f"{preset_stem}.json")
    return run_ensemble(project_numeric(load_worldspec(doc)), 200, base_seed=SEED)


def annualised(ens: EnsembleResult, asset: str) -> float:
    r = ens.returns[asset] / 100.0
    return float((np.prod(1 + r, axis=1).mean() ** (12 / r.shape[1]) - 1) * 100)


def sharpe(ens: EnsembleResult, asset: str) -> float:
    r = ens.returns[asset] / 100.0
    return float(r.mean() * 12 / (r.std(ddof=1) * math.sqrt(12)))
```

- [ ] **Step 4: write AT-6b as a test**

```python
def test_at6b_public_assets_are_bit_identical_to_toy_v06():
    """AT-6b. equity/bonds/hy/commodities/reits are bit-identical to toy-v0.6 on
    every preset and every compiler fixture, unconditionally.

    Only three (later four) return equations move and no RNG draw is added or
    REORDERED. If a public asset moves, something was touched that should not
    have been - this is the STOP condition of the whole implementation."""
    ref = np.load(BASELINE_NPZ)
    for path in sorted(PRESETS.glob("*.json")):
        paths = run_path(project_numeric(load_worldspec(_load(path))), SEED)
        for asset in PUBLIC_ASSETS:
            np.testing.assert_array_equal(
                paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
            )

def test_at6b_public_assets_hold_on_every_compiler_fixture():
    """AT-6b, the fixture half: same claim, checked by digest over the 51
    committed compiler fixtures."""
    doc = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    for key, expected in doc["digests"].items():
        stem, asset = key.rsplit("/", 1)
        paths = run_path(project_numeric(load_worldspec(_load(FIXTURES / f"{stem}.json"))), SEED)
        assert sha256_of_arrays([paths.returns[asset]]) == expected, key
```

- [ ] **Step 5: run the AT-6b tests**

Run: `uv run pytest tests/test_er14_inflation.py -q`
Expected: PASS (nothing has changed yet — this is a guard being armed, not a red test).

- [ ] **Step 6: reproduce ER-14's own measurement, one last time**

Run the register's §7 probe verbatim (`docs/current/private-markets-and-inflation.md` §7,
the `§4.3` block) and confirm today's numbers: `pe` delta 1% → 12% is **0.000**, `re` is
**−0.117**, `pc` is **+0.022**. Paste the table into the commit body. This is the
anti-test guard's "before" half — the design requires AT-2/3/4 to be demonstrated failing
on `toy-v0.6` before the mechanism lands.

- [ ] **Step 7: open the red ledger**

Create `docs/superpowers/plans/er14-red-ledger.md` with the header, the rules from this
plan's branch-strategy section, and an empty table (`| test id | cause | cleared by |`).

- [ ] **Step 8: commit**

```bash
git add scripts/gen_er14_baseline.py tests/fixtures/er14 tests/test_er14_inflation.py docs/superpowers/plans/er14-red-ledger.md
git commit -m "test(er14-02): the toy-v0.6 baselines and AT-6b, armed before any mechanism"
```

---

### Task M2: the shared state variable

**Files:**
- Modify: `src/ah/core/engine.py` (constants block near line 87; a new helper beside `_t_draws`)
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces: `ah.core.engine.INFLATION_TRAIL_MONTHS: int = 24`,
  `ah.core.engine.INFLATION_ANCHOR_PCT: float = 2.0`,
  `ah.core.engine.inflation_excess(inflation: np.ndarray, *, k: int = INFLATION_TRAIL_MONTHS, anchor: float = INFLATION_ANCHOR_PCT) -> np.ndarray`
  returning annual percentage points, same length as `inflation`.
- Consumed by: every mechanism task in `er14-02`/`er14-03`, `_infra_return` in Task M6,
  and `src/ah/port/adapter.py` in `er14-05` (the `port → core` direction is allowed).

- [ ] **Step 1: write the failing tests**

```python
def test_inflation_excess_is_a_trailing_mean_demeaned_at_the_anchor():
    x = inflation_excess(np.full(36, 6.5))
    assert np.allclose(x, 4.5)

def test_inflation_excess_warms_up_over_available_months_not_from_zero():
    """K=24 with a 120-month world would leave a fifth of the game dead and put a
    visible step at month 24. The mean is taken over the months available, so a
    world that opens hot is hot from month 0 (design 2.0)."""
    infl = np.array([10.0, 0.0, 0.0, 0.0])
    x = inflation_excess(infl, k=24)
    assert x[0] == pytest.approx(10.0 - 2.0)
    assert x[1] == pytest.approx(5.0 - 2.0)
    assert x[3] == pytest.approx(2.5 - 2.0)

def test_inflation_excess_window_is_exactly_k_months():
    infl = np.concatenate([np.zeros(24), np.full(24, 12.0)])
    x = inflation_excess(infl, k=24)
    assert x[47] == pytest.approx(12.0 - 2.0)
    assert x[35] == pytest.approx(6.0 - 2.0)

def test_inflation_excess_consumes_no_rng():
    """The channel is derived state, not a new stream (AT-7's precondition)."""
    rng = np.random.Generator(np.random.PCG64(7))
    before = rng.standard_normal(3).tolist()
    inflation_excess(np.full(24, 3.0))
    rng2 = np.random.Generator(np.random.PCG64(7))
    assert rng2.standard_normal(3).tolist() == before

def test_the_anchor_is_the_engines_own_anchor():
    """C_ANCHOR is not a new number: it is _RATE_SHOCK_INFLATION_ANCHOR and
    _DEF['infl_avg'] (D-ER14-2 A1 row 1)."""
    assert INFLATION_ANCHOR_PCT == _RATE_SHOCK_INFLATION_ANCHOR == _DEF["infl_avg"] == 2.0
```

- [ ] **Step 2: run them and watch them fail**

Run: `uv run pytest tests/test_er14_inflation.py -k excess -q`
Expected: FAIL — `ImportError: cannot import name 'inflation_excess'`.

- [ ] **Step 3: implement**

```python
# ER-14 close-out (D-ER14-2, 2026-08-18). The inflation channel's shared state.
# K = 24 months is C1's declared cpi_trail_k (8 quarters) at the engine's monthly
# resolution - inherited from AM-2026-08-15-001, not chosen here. The anchor is
# the engine's own: _RATE_SHOCK_INFLATION_ANCHOR and _DEF["infl_avg"], so a 2%
# world gets essentially no new drift and adoption adds STATE-DEPENDENCE, not
# return.
INFLATION_TRAIL_MONTHS = 24
INFLATION_ANCHOR_PCT = 2.0


def inflation_excess(
    inflation: np.ndarray,
    *,
    k: int = INFLATION_TRAIL_MONTHS,
    anchor: float = INFLATION_ANCHOR_PCT,
) -> np.ndarray:
    """Trailing-mean inflation less the anchor, in ANNUAL percentage points.

    Warm-up: for m < k-1 the mean is over the months available, not held at
    zero - a decade world is 120 months and two years of dead channel would be
    a fifth of the game. Consumes no RNG.
    """
    infl = np.asarray(inflation, dtype=np.float64)
    csum = np.concatenate([[0.0], np.cumsum(infl)])
    idx = np.arange(infl.size)
    lo = np.maximum(0, idx - k + 1)
    trail = (csum[idx + 1] - csum[lo]) / (idx - lo + 1)
    return trail - anchor
```

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q`
Expected: PASS, and AT-6b still PASS (no return equation has changed).

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-02): inflation_excess - the shared state variable (K=24, anchor 2.0)"
```

---

### Task M3: real estate — income escalation against cap-rate repricing

**Files:**
- Modify: `src/ah/core/engine.py:424-431` (the `re` equation) and the constants block
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Consumes: `inflation_excess` (Task M2); `probe`, `annualised`, `ensemble_of`, `_world`
  (Task M1's helper block).
- Produces: `_LAMBDA_RE = 0.30`, `_GAMMA_RE = 0.50`, `_D_RE = 4.0` (module constants).

- [ ] **Step 1: capture the anchor baseline — before touching `re`**

AT-6a needs an "inflation pinned at the anchor" reference taken on `toy-v0.6`. Add to
`scripts/gen_er14_baseline.py`:

```python
def build_anchor_baseline() -> None:
    """The AT-6a reference: every preset with its declared inflation set to the
    anchor and its crisis windows cleared, so _inflation_path's mean-reverting
    path sits at C_ANCHOR and the new terms are inert by construction."""
    arrays: dict[str, np.ndarray] = {}
    for path in sorted(PRESETS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["factor_conditions"]["inflation"]["average_pct"] = 2.0
        doc["factor_conditions"]["crisis_windows"] = []
        paths = _paths(doc)
        for asset in ("pe", "pc", "re"):
            arrays[f"{path.stem}/{asset}"] = np.asarray(paths.returns[asset], dtype=np.float64)
    np.savez_compressed(ROOT / "tests/fixtures/er14/anchor-baseline-toy-v0.6.npz", **arrays)
```

Run it **now**, while `engine.py`'s `re` equation is still `toy-v0.6` — the reference
must be a `toy-v0.6` number. Record the git sha in the sidecar JSON and commit the
fixture in this task.

- [ ] **Step 2: write the failing tests (AT-1, AT-3, AT-8 + the shape claims)**

```python
def test_at1_private_returns_are_no_longer_bit_identical_across_inflation():
    """AT-1, the literal inversion. ER-14's headline is 'bit-identical across a
    twelvefold change'; this is that sentence negated. Break-proof: it cannot be
    satisfied by a test that restates the implementation."""
    lo = run_path(_world(1.0), 12345)
    hi = run_path(_world(12.0), 12345)
    for asset in ("pe", "re"):
        assert not np.array_equal(lo.returns[asset], hi.returns[asset]), asset


def test_at3_real_estate_moves_the_right_way_and_materially():
    """AT-3. Delta annualised re, 1% -> 12%, must be POSITIVE and >= +1.5 pp/yr
    (lambda_RE's declared range floor 0.15 x 11pp - rounding). Today's measured
    value is -0.117: this is a sign flip of ~1.6 pp/yr minimum."""
    delta = annualised(probe(12.0), "re") - annualised(probe(1.0), "re")
    assert delta >= 1.5, delta


def test_at8_the_deflation_mirror():
    """AT-8. deflation_bust (-1.0%) re sits at least 0.5 pp/yr BELOW goldilocks
    (2.0%) re. The mechanism must be symmetric - an inflation RESPONSE, not a
    one-sided bonus that only ever pays. lambda_RE's range floor 0.15 x 3.0pp =
    0.45, rounded to 0.5."""
    bust = annualised(ensemble_of("deflation_bust"), "re")
    gold = annualised(ensemble_of("goldilocks"), "re")
    assert gold - bust >= 0.5, (gold, bust)


def test_the_repricing_term_is_a_change_effect_not_a_level_effect():
    """Income escalation is proportional to x (permanent); cap-rate repricing is
    proportional to dx (transient). Modelling them with the same time signature
    is the single most common way to get this wrong (design 2.1). With inflation
    STEADY the repricing term contributes nothing."""
    steady = np.full(120, 6.5)
    x = inflation_excess(steady)
    d_x = np.diff(x, prepend=x[0])
    assert np.allclose(d_x[24:], 0.0, atol=1e-12)


@pytest.mark.parametrize("asset", ["pe", "re"])
def test_at6a_the_inflation_channel_is_inert_at_the_anchor(asset):
    """AT-6a (pe/re half; pc joins in Task C5). A world whose inflation sits at
    C_ANCHOR gets x == 0, so every new term vanishes and the asset is
    BIT-IDENTICAL to toy-v0.6: zero inflation delta => bit-unchanged where the
    mechanism should be inert."""
    ref = np.load(ANCHOR_BASELINE_NPZ)
    for path in sorted(PRESETS.glob("*.json")):
        doc = _load(path)
        _set_dotted(doc, "factor_conditions.inflation.average_pct", 2.0)
        doc["factor_conditions"]["crisis_windows"] = []
        paths = run_path(project_numeric(load_worldspec(doc)), SEED)
        np.testing.assert_array_equal(
            paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
        )
```

- [ ] **Step 3: run them and watch AT-3 and AT-8 fail**

Run: `uv run pytest tests/test_er14_inflation.py -k "at1 or at3 or at8" -q`
Expected: AT-3 FAILs with a delta near **−0.117**; AT-8 FAILs; AT-1 FAILs
(`arrays are equal`). Record the three failure values in the commit body — this is the
anti-test guard.

- [ ] **Step 4: implement the real estate mechanism**

```python
# ER-14 close-out coefficients (D-ER14-2 A1, ratified 2026-08-18). Every value is
# the owner's, with its anchor recorded in the design's 2.1/2.2/2.3/2.6.
_LAMBDA_RE = 0.30   # income escalation: C1's declared pm_re_value_add
_GAMMA_RE = 0.50    # cap-rate repricing: partial Fisher, 0.64 x 72% at K=8
_D_RE = 4.0         # NOT new: the property rate duration already in -4.0*d_rate
```

```python
    # computed once, immediately after d_rate / d_spread; every mechanism reads it
    x = inflation_excess(inflation)
    d_x = np.diff(x, prepend=x[0])          # same convention as d_rate: month 0 is zero
    # (the existing parameter-extraction block is unchanged)
    re = (
        re_income / 12.0
        - re_cap / (100.0 * nm) * 2.2
        - _D_RE * d_rate
        + 0.35 * eq
        + 1.5 * e_re
        - 1.0 * crisis
        # ER-14: leases escalate with the price level (a LEVEL effect on x), while
        # nominal discount rates lift cap rates and mark a long-duration asset down
        # (a CHANGE effect on dx). Same duration the rate term already uses.
        + _LAMBDA_RE * x / 12.0
        - _D_RE * _GAMMA_RE * d_x
    )
```

`re_income` arrives in Task M4; until then keep the literal `4.5 / 12.0` and the
`-4.0 * d_rate` replaced by `-_D_RE * d_rate` (numerically identical — AT-6b proves it).

- [ ] **Step 5: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q`
Expected: AT-1 (re), AT-3, AT-8, AT-6a PASS; AT-6b still PASS (publics untouched).
Expected delta on AT-3: about **+3.3 pp/yr** (0.30 × 11) — if it is materially different,
stop and reconcile against design §4 before proceeding.

- [ ] **Step 6: break-and-revert proof**

Set `_LAMBDA_RE = 0.0`, run AT-3, confirm **RED**; revert. Paste both outputs into the
commit body (the design's anti-test guard: "set λ_RE to 0 and AT-3 must go red").

- [ ] **Step 7: commit**

```bash
git commit -am "feat(er14-02): real estate feels inflation - escalation (level) vs cap-rate repricing (change); AT-1/3/8"
```

---

### Task M4: rider R1 — read `structural.real_estate.income_yield_pct`

**Files:**
- Modify: `src/ah/core/engine.py` (`_DEF`, the `re` equation)
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces: `_DEF["re_income_yield"] = 4.5`; the local `re_income` in `run_path`.

- [ ] **Step 1: write the failing tests**

```python
def test_r1_income_yield_is_read_from_the_world():
    """R1 (A11, recommended in). The 4.5% income yield was hardcoded while the
    schema field structural.real_estate.income_yield_pct sat declared and dead
    (ER-14's unconsumed-field map). Schema range 2-8."""
    lo = annualised(probe(6.5, **{"structural.real_estate.income_yield_pct": 3.0}), "re")
    hi = annualised(probe(6.5, **{"structural.real_estate.income_yield_pct": 7.0}), "re")
    assert hi - lo == pytest.approx(4.0, abs=0.15)

def test_r1_changes_no_shipped_preset():
    """NO shipped preset declares income_yield_pct, so every preset is
    numerically unchanged by R1 - the cheapest honest repair in the package."""
    for path in sorted(PRESETS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert "income_yield_pct" not in doc["structural"].get("real_estate", {}), path.stem
```

- [ ] **Step 2: run and watch the first fail**

Run: `uv run pytest tests/test_er14_inflation.py -k r1 -q`
Expected: the read test FAILs (`hi - lo == 0.0`); the no-preset-declares test PASSES.

- [ ] **Step 3: implement**

One new entry at the end of the existing `_DEF` dict:

```python
    "re_income_yield": 4.5,   # R1: the hardcoded income level, now a default
```
```python
    re_income = _f(st.real_estate, "income_yield_pct", _DEF["re_income_yield"])
```
and use `re_income / 12.0` in the `re` equation.

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q` — Expected: PASS, AT-6b green,
AT-3/AT-8 unchanged to 12 decimals (no preset declares the field).

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-02): R1 - real_estate.income_yield_pct is read; no preset number moves"
```

---

### Task M5: private equity — nominal earnings against multiple compression

**Files:**
- Modify: `src/ah/core/engine.py:417` (the `pe` equation), constants block
- Modify: `scripts/gen_presets.py` (`stagflation`'s `entry_multiple_drift_annual_pct` → 0.0)
- Modify: `src/ah/presets/stagflation.json`, `src/ah/presets/stagflation_1974.json` (regenerated / hand-edited)
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces: `_LAMBDA_PE = 0.35`, `_MU_PE = 0.45`.

- [ ] **Step 1: write the failing tests (AT-2 + the ratified net floor + the double-count)**

```python
def test_at2_private_equity_differs_materially_across_inflation():
    """AT-2. |Delta annualised pe|, 1% -> 12%, >= 0.65 pp/yr (the asked net floor
    0.06 x the 11pp probe range). Today's measured value is EXACTLY 0.000: pe =
    1.4*eq + const, and equity carries no inflation term either."""
    delta = abs(annualised(probe(12.0), "pe") - annualised(probe(1.0), "pe"))
    assert delta >= 0.65, delta


def test_the_pe_net_floor_is_respected():
    """A3, ratified: |lambda_PE - mu_PE| >= 0.06, so no in-range combination can
    produce a near-zero net and quietly re-create ER-14 in weaker form."""
    assert abs(_LAMBDA_PE - _MU_PE) >= 0.06


def test_pe_responds_negatively_to_inflation():
    """Net PE = lambda_PE - mu_PE = -0.10 pp/yr per pp: a 12% world's private
    equity runs about 1.1 pp/yr below a 1% world's (design 2.2)."""
    assert annualised(probe(12.0), "pe") < annualised(probe(1.0), "pe")


def test_the_live_presets_no_longer_hand_author_the_inflation_drift():
    """A5. mu_PE makes multiple compression endogenous; leaving the authored
    -2.0 in place would charge it twice. The field now means NON-inflation
    multiple drift (secular dry-powder, sector re-rating)."""
    for stem in ("stagflation", "stagflation_1974"):
        doc = json.loads((PRESETS / f"{stem}.json").read_text(encoding="utf-8"))
        assert doc["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] == 0.0
```

- [ ] **Step 2: run and record the reds**

Run: `uv run pytest tests/test_er14_inflation.py -k "at2 or pe" -q`
Expected: AT-2 FAILs with delta **0.000** (the register's own number); the preset test
FAILs with `-2.0`.

- [ ] **Step 3: implement the mechanism**

```python
_LAMBDA_PE = 0.35   # unlevered pass-through 0.25 x the engine's declared 1.4 leverage beta
_MU_PE = 0.45       # the shipped presets' own authored -2.0 drift at 4.5pp excess
```
```python
    # ER-14: portfolio companies bill in nominal currency (lambda_PE, folding in
    # the real erosion of fixed-rate acquisition debt - disclosed as a fold-in,
    # design 2.2), and exits price on multiples that compress as nominal discount
    # rates rise (mu_PE). Expressed inside the engine's OWN vocabulary: mu_PE makes
    # entry_multiple_drift respond to inflation instead of being hand-authored.
    pe = 1.4 * eq + (pe_illiq + pe_mult + (_LAMBDA_PE - _MU_PE) * x) / 12.0 + 2.0 * e_pe
```

- [ ] **Step 4: re-author the two LIVE presets**

In `scripts/gen_presets.py`, set the `stagflation` row's multiple drift to `0.0`
(the `preset(...)` builder's corresponding argument — check the signature; if the
builder has no such parameter, add one defaulting to the current value so no other
preset moves). Then:

Run: `uv run python scripts/gen_presets.py`
Hand-edit `src/ah/presets/stagflation_1974.json`'s
`structural.private_equity.entry_multiple_drift_annual_pct` to `0.0`.

**Do NOT touch `stress_1974.json`, `stress_1990.json`, `narration_1974.json`,
`spine_pilot.json`** — R-6 in the risk table: D-ER14-2 retires those worlds, and a
retired world is a record. State the deviation in the commit body.

- [ ] **Step 5: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q`
Expected: AT-1/2/3/8 PASS, AT-6a/6b PASS. AT-2's delta should be about **1.1 pp/yr**
(0.10 × 11). Then run the full suite to a log and append every new failure to the red
ledger with cause `value-golden` or `world-id-pin`:

```bash
uv run pytest -q > er14-m5.log 2>&1; echo "EXIT: $?" >> er14-m5.log
```
Read the log (never `tail` into a decision) and update `er14-red-ledger.md`.

- [ ] **Step 6: commit**

```bash
git commit -am "feat(er14-02): private equity feels inflation - nominal earnings vs multiple compression; AT-2; live presets de-double-counted"
```

---

### Task M6: the infrastructure return mechanism (pure function)

**Files:**
- Modify: `src/ah/core/engine.py` (constants + a new module-level function)
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces:

  ```python
  def infra_return(
      *,
      x: np.ndarray,            # inflation excess, annual pp
      d_x: np.ndarray,          # its first difference (prepend=first, so month 0 is 0)
      d_rate: np.ndarray,       # the authored rate path's first difference, pp
      eq: np.ndarray,           # the equity return stream, monthly percent
      e_infra: np.ndarray,      # unit-variance Student-t innovations
      crisis: np.ndarray,       # the binary crisis mask
      linkage: float,           # structural.infrastructure.inflation_linkage
      disc_shift_bps: float,    # structural.infrastructure.discount_rate_shift_bps
      yield_pct: float,         # infra_yield, annual percent
      nm: int,
  ) -> np.ndarray
  ```
  returning monthly percent, same length as `eq`.
- Consumed by: `run_path` in Task S1 (`er14-04b`) — **this task does not wire it in**;
  the asset does not exist until the sleeve WP, and wiring it early would shift the
  draw block (R-1).

- [ ] **Step 1: write the failing tests**

```python
def test_infra_escalator_is_the_declared_linkage_share():
    """lambda_INFRA is not a constant - it is
    structural.infrastructure.inflation_linkage, 'Share of revenues contractually
    inflation-linked', bounded 0-1. That IS the pass-through coefficient,
    definitionally (design 2.6)."""
    kw = _flat_infra_kwargs(x_level=4.5)
    hi = infra_return(**{**kw, "linkage": 0.9}).mean() * 12
    lo = infra_return(**{**kw, "linkage": 0.3}).mean() * 12
    assert (hi - lo) == pytest.approx((0.9 - 0.3) * 4.5, abs=0.05)


def test_infra_response_ratio_is_linear_in_the_linkage_share():
    """AT-12's property at the function level: the ratio of two worlds'
    inflation responses is the ratio of their declared linkages, 0.3/0.9 = 0.33."""
    base = _flat_infra_kwargs(x_level=0.0)
    hot = _flat_infra_kwargs(x_level=4.5)
    resp = lambda k: (infra_return(**{**hot, "linkage": k}).mean()
                      - infra_return(**{**base, "linkage": k}).mean())
    assert resp(0.3) / resp(0.9) == pytest.approx(0.333, abs=0.05)


def test_infra_reprices_less_than_property_for_the_same_acceleration():
    """gamma_INFRA 0.30 on a 4.0 duration charges -1.2 x dx against real estate's
    -2.0 x dx. Infrastructure both earns more from sustained inflation and is
    marked down less when inflation surges - the class's investment case, and the
    design reproduces both without either being asserted."""
    assert _D_INFRA * _GAMMA_INFRA < _D_RE * _GAMMA_RE


def test_infra_reads_the_discount_rate_shift_field():
    """structural.infrastructure.discount_rate_shift_bps was declared and dead
    (the second half of ER-14's most quotable line)."""
    kw = _flat_infra_kwargs(x_level=0.0)
    assert infra_return(**{**kw, "disc_shift_bps": 300.0}).sum() < infra_return(**kw).sum()


def test_infra_uses_the_transplanted_pm_infra_constants():
    """beta_INFRA and sigma_INFRA come straight out of the sealed pm_infra row in
    sleeve-mappings-v1.1.yaml: equity_mkt 0.3337 and residual_sigma_annual 0.0569,
    which at monthly resolution is 0.0569/sqrt(12) = 1.64%. Label: chosen
    (transplanted from a measured row)."""
    row = yaml.safe_load(Path("mappings/sleeve-mappings-v1.1.yaml").read_text())["pm_sleeves"]["pm_infra"]
    assert _BETA_INFRA == pytest.approx(row["loadings"]["equity_mkt"], abs=0.005)
    assert _SIGMA_INFRA == pytest.approx(row["residual_sigma_annual"] / math.sqrt(12) * 100, abs=0.02)
```

- [ ] **Step 2: run and watch them fail**

Run: `uv run pytest tests/test_er14_inflation.py -k infra -q`
Expected: FAIL — `cannot import name 'infra_return'`.

- [ ] **Step 3: implement**

```python
_LAMBDA_INFRA_DEFAULT = 0.60   # C1's declared pm_infra linkage; a DEFAULT, not a constant
_GAMMA_INFRA = 0.30            # gamma_RE 0.50 x ~1.6 duration premium x 0.4 unregulated share
_D_INFRA = 4.0                 # RE's duration reused, so ONE number carries the difference
_BETA_INFRA = 0.33             # pm_infra's estimated equity_mkt loading (v1.1, 60 quarters)
_SIGMA_INFRA = 1.65            # pm_infra's residual_sigma_annual 0.0569 / sqrt(12)
_INFRA_CRISIS = 0.5            # half of real estate's -1.0; the weakest-anchored number here


def infra_return(*, x, d_x, d_rate, eq, e_infra, crisis, linkage, disc_shift_bps, yield_pct, nm):
    """Core/core-plus infrastructure: contracted income, an escalator whose share
    the WORLD declares, and a damped discount-rate repricing.

    Same time signatures as real estate, deliberately, so the two are directly
    comparable: escalation is a LEVEL effect on x, repricing a CHANGE effect on
    dx. The escalator is SYMMETRIC - C1 defers caps and floors, so deflation
    charges infrastructure the full -0.6 x |x| and the overstatement is measured
    (AT-13), not argued about. Leverage is not modelled: pm_infra is estimated on
    a net levered composite, so it is already inside beta and sigma.
    """
    return (
        yield_pct / 12.0
        + linkage * x / 12.0
        - _D_INFRA * _GAMMA_INFRA * d_x
        - _D_INFRA * d_rate
        - disc_shift_bps / (100.0 * nm) * 2.2
        + _BETA_INFRA * eq
        + _SIGMA_INFRA * e_infra
        - _INFRA_CRISIS * crisis
    )
```

Add the two `_DEF` entries the wiring task will use:
`_DEF["infra_yield"] = 5.0`, `_DEF["infra_linkage"] = _LAMBDA_INFRA_DEFAULT`,
`_DEF["infra_disc"] = 0.0` (matching `re_cap_shift`'s default),
`_DEF["smooth_infra"] = 0.35` (**plan decision, not in the design**: the appraisal
weight for a real asset, matching `smooth_re`; the schema declares the field with range
0.1–1 and no preset sets it, so nothing shipped moves — recorded in the commit body).

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q`
Expected: PASS. AT-6b still PASS — nothing is wired into `run_path`, no draw added.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-02): the infrastructure return mechanism - linkage read live, repricing damped (pure function; wired in er14-04b)"
```

---

### Task M7: WP `er14-02` close-out

**Files:** `CHANGELOG.md`, `docs/superpowers/plans/er14-red-ledger.md`

- [ ] **Step 1: lint the whole tree**

Run: `uv run ruff check . --fix && uv run ruff format . && uv run pyright`
Expected: clean. (Lint before the long gate — two restarts have been paid for
stragglers found mid-run.)

- [ ] **Step 2: full suite to a log; reconcile the ledger**

```bash
uv run pytest -q > er14-02-full.log 2>&1; echo "EXIT: $?" >> er14-02-full.log
```
Read the log. Every failure must be on `er14-red-ledger.md` with a cause. **Any failure
that is not a value golden, a world-id pin or a bundle fixture is a STOP.**

- [ ] **Step 3: CHANGELOG**

One entry per task (M1–M6), naming the ratified coefficients and D-ER14-2.

- [ ] **Step 4: whole-WP adversarial review**

Review the branch diff against design §2.0–2.2, §2.6 and this plan; fix findings.
Specifically re-check: no RNG call added; no public asset touched; every coefficient
equals its ratified value; `schemas/` untouched; all three lock digests unchanged
(re-run the three verify commands).

- [ ] **Step 5: merge into the release branch**

```bash
git checkout er14-release && git merge --no-ff er14-02-mechanisms
```

---

# WP `er14-03` — the decoupled credit path (branch `er14-03-credit`)

**Scope:** private credit's floating coupon, the borrower-coverage squeeze, the C2
convexity **decoupled from CDLI** (D-ER14-2: "private-credit convexity ships declared at
0.10; C2's measured half awaits the export"), rider R2, and AT-6a extended to `pc`.
**Discharges AT-4, AT-5, AT-6a (full).**

---

### Task C1: the floating coupon (φ_PC)

**Files:**
- Modify: `src/ah/core/engine.py:421` (the `pc` equation), constants block
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Consumes: `inflation_excess`, `INFLATION_ANCHOR_PCT` (Task M2).
- Produces: `_PHI_PC = 1.0`.

- [ ] **Step 1: write the failing test (AT-5)**

```python
def test_at5_the_floating_benefit_is_visible_when_the_policy_rate_moves():
    """AT-5, as RESTATED and ratified (A10). D-ER14-1 asked that PC's floating
    benefit be visible; measuring that by varying INFLATION with rates pinned asks
    the coupon to respond to something it is not connected to, and would fail a
    correct model. So: +2 pp on policy_rate.end_pct, all else held, must lift
    annualised pc by >= +0.80 pp/yr (a glide ending 2pp higher raises the mean
    policy rate ~1pp, which is ~1 pp/yr of coupon; 0.80 leaves room for the loss
    side to offset)."""
    base = annualised(probe(6.5), "pc")
    up = annualised(probe(6.5, **{"factor_conditions.policy_rate.end_pct": 9.5}), "pc")
    assert up - base >= 0.80, up - base


def test_phi_pc_measures_excess_against_the_worlds_own_declared_average():
    """The asymmetry with RE and PE is the whole point (design 2.3). Property and
    buyout have NO authored inflation channel anywhere in the WorldSpec, so their
    excess is measured against the platform anchor. Private credit's level is
    already authored through factor_conditions.policy_rate; measuring its excess
    against C_ANCHOR would charge stagflation the benefit twice and print a
    ~12%/yr private credit book. Only the WITHIN-world dynamics change."""
    ens_lo, ens_hi = probe(1.0), probe(12.0)
    # a 12x change in the DECLARED average must not move the coupon term's mean
    # by anything like 11pp/12: the coupon tracks deviations from that average.
    assert abs(annualised(ens_hi, "pc") - annualised(ens_lo, "pc")) < 2.0
```

- [ ] **Step 2: run and record the red**

Run: `uv run pytest tests/test_er14_inflation.py -k at5 -q`
Expected: AT-5 currently PASSES or FAILS depending on the existing `rate/12` carry —
run it and **record the measured value** before implementing. (The coupon already
tracks the authored rate, so this test is a guard on not *losing* the benefit as much
as on gaining it. If it passes at baseline, say so in the commit body; a guard that was
already green is honest as long as it is not claimed as new evidence.)

- [ ] **Step 3: implement**

```python
_PHI_PC = 1.0   # Fisher one-for-one on a nominal reference rate
```
```python
    infl_trail = x + INFLATION_ANCHOR_PCT
    pc = (
        (rate + pc_spread_pct) / 12.0
        # ER-14: the loan's floating base tracks inflation WITHIN the world. A
        # shadow rate that can differ from the engine's own `rate` path is an
        # admitted approximation (ER-2 already records that rate is a continuous
        # drift with no meeting calendar); the clean alternative - a policy
        # reaction function in _rate_path - is DECLINED in design 2.4 because it
        # would route the fix through a PUBLIC channel, which is the very
        # second-order effect ER-14 exists to complain about.
        + _PHI_PC * (infl_trail - infl_avg) / 12.0
        - pc_loss_m
        - 0.8 * d_spread
        + 0.18 * eq
        + 1.45 * e_pc
    )
```
`pc_spread_pct` is `4.5` until Task C4 makes it a field read.

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q` — Expected: AT-5 PASS, AT-6b PASS.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-03): private credit's coupon tracks inflation within the world (phi_PC=1.0); AT-5"
```

---

### Task C2: the borrower-coverage squeeze (ω_PC)

**Files:**
- Modify: `src/ah/core/engine.py:403` (`pc_loss_m`), constants block
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces: `_OMEGA_PC = 0.03`.

- [ ] **Step 1: write the failing tests (AT-4)**

```python
def test_at4_the_loss_bite_is_negative_under_the_rates_held_probe():
    """AT-4. Delta annualised pc, 1% -> 12%, rates HELD, must be <= -0.30 pp/yr.
    Today's measured value is +0.022. A lender whose rate does not rise while its
    borrowers' costs do is in trouble - that is the whole content of the test."""
    delta = annualised(probe(12.0), "pc") - annualised(probe(1.0), "pc")
    assert delta <= -0.30, delta


def test_the_squeeze_is_one_sided_at_the_anchor(monkeypatch):
    """max(0, x): deflation does not squeeze borrower coverage through INPUT
    costs - it squeezes it through revenue, a different channel, deliberately not
    modelled (design 4, the mirror). So on deflation_bust the term is inert, and
    zeroing omega_PC changes nothing."""
    bust = annualised(ensemble_of("deflation_bust"), "pc")
    monkeypatch.setattr(engine, "_OMEGA_PC", 0.0)
    assert annualised(ensemble_of("deflation_bust"), "pc") == pytest.approx(bust, abs=1e-12)


def test_inflation_stress_never_exceeds_the_engines_own_crisis_stress():
    """omega_PC's value is derived from a BOUNDING rule, not picked: the schema
    caps inflation.average_pct at 20 (x_max = 18) and _CRISIS_LOSS_AMPLIFIER is
    1.6, so omega_PC <= 0.6/18 = 0.033."""
    assert _OMEGA_PC <= (_CRISIS_LOSS_AMPLIFIER - 1.0) / 18.0
```

- [ ] **Step 2: run and record the red**

Run: `uv run pytest tests/test_er14_inflation.py -k at4 -q`
Expected: FAIL with delta near **+0.02** — the register's own measured value.

- [ ] **Step 3: implement**

```python
_OMEGA_PC = 0.03   # fractional loss uplift per pp of excess; bounded under the crisis amplifier
```
```python
    pc_loss_m = (
        (pc_loss / 12.0)
        * (0.7 + 0.6 * spread_lagged / _SPREAD_REFERENCE_BPS)
        * loss_amp
        # ER-14: sustained inflation squeezes levered borrowers from both ends -
        # input and wage costs rise, and their own floating coupons rise with the
        # reference rate - so coverage deteriorates and defaults rise.
        * (1.0 + _OMEGA_PC * np.maximum(0.0, x))
    )
```

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q` — Expected: AT-4 PASS at about
**−0.8 pp/yr**; AT-5 still PASS; AT-6b PASS.

- [ ] **Step 5: break-and-revert proof**

Set `_OMEGA_PC = 0.0`; AT-4 must go RED; revert. Record both in the commit body.

- [ ] **Step 6: commit**

```bash
git commit -am "feat(er14-03): the borrower-coverage squeeze (omega_PC=0.03); AT-4 inverted"
```

---

### Task C3: the C2 convexity, decoupled from CDLI (θ_toy)

**Files:**
- Modify: `src/ah/core/engine.py` (`pc_loss_m`), constants block
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces: `_THETA_TOY = 0.10`.

- [ ] **Step 1: write the failing tests**

```python
def _pc_at(peak_bps: float, **extra) -> float:
    """Annualised pc on a calm-inflation world whose HY spread peak is set."""
    return annualised(
        probe(2.0, **{"factor_conditions.credit.hy_spread_peak_bps": peak_bps, **extra}), "pc"
    )


def test_theta_is_additive_never_a_replacement():
    """C2's bare form implies ZERO loss below the median spread. Substituting it
    for the toy engine's through-cycle loss would delete ER-1's close-out and hand
    private credit back the Sharpe near 2 that ER-1 and ER-4 were written to
    remove. The convex term is ADDED on top of the existing linear loss - so below
    s_bar the world's declared annual_loss_rate_pct still bites, hard."""
    lo = _pc_at(350.0, **{"structural.private_credit.annual_loss_rate_pct": 0.5})
    hi = _pc_at(350.0, **{"structural.private_credit.annual_loss_rate_pct": 5.0})
    assert lo - hi > 2.0


def test_theta_is_convex_above_the_engines_own_spread_reference():
    """s_bar = _SPREAD_REFERENCE_BPS = 400, documented in place as 'the spread a
    normal credit market prices' - no new constant, and it plays exactly the role
    C2's s_bar plays. Each extra 200bp of peak spread must cost MORE when spreads
    are already wide than when they are near the reference."""
    near = _pc_at(400.0) - _pc_at(600.0)
    wide = _pc_at(1600.0) - _pc_at(1800.0)
    assert wide > near


def test_theta_toy_is_the_ratified_declared_value_pending_cdli():
    """D-ER14-2: CDLI decoupled - the convexity ships DECLARED at 0.10 and C2's
    measured half awaits the Cliffwater export. Anchor: _HY_LOSS_SHARE 0.45 x the
    engine's own pc/hy spread-sensitivity ratio (0.8/3.5 = 0.229) = 0.103."""
    assert _THETA_TOY == 0.10
    assert _THETA_TOY == pytest.approx(_HY_LOSS_SHARE * (0.8 / 3.5), abs=0.005)


def test_private_credit_has_not_recovered_its_pre_er1_sharpe():
    """ER-1/ER-4 regression guard: the convex term must not be a net GIFT.
    Decade Sharpe of pc on the stagflation preset stays well under 2.0."""
    assert sharpe(probe(6.5), "pc") < 1.5
```

- [ ] **Step 2: run and watch them fail**

Run: `uv run pytest tests/test_er14_inflation.py -k theta -q`
Expected: the convexity test FAILs (today's loss is linear in `spread_lagged`).

- [ ] **Step 3: implement**

```python
_THETA_TOY = 0.10   # C2's convexity adapted to the toy plane; DECLARED, CDLI decoupled (D-ER14-2)
```
```python
    pc_loss_m = (
        ... the linear term from Task C2 ...
        # C2's contribution is CONVEXITY: losses accelerate once spreads exceed
        # their normal level. Additive, never a replacement (design 2.3).
        + _THETA_TOY * np.maximum(spread_lagged - _SPREAD_REFERENCE_BPS, 0.0) / 1200.0 * loss_amp
    )
```

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_er14_inflation.py -q` — Expected: PASS, AT-4 still ≤ −0.30,
AT-6b PASS.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-03): the convex spread loss (theta_toy=0.10, declared; CDLI decoupled per D-ER14-2)"
```

---

### Task C4: rider R2 — read `structural.private_credit.spread_over_base_bps`

**Files:**
- Modify: `src/ah/core/engine.py` (`_DEF`, the `pc` equation)
- Test: `tests/test_er14_inflation.py`

**Interfaces:**
- Produces: `_DEF["pc_spread_bps"] = 450.0`; the local `pc_spread_pct` in `run_path`.

- [ ] **Step 1: write the failing tests**

```python
def test_r2_the_spread_over_base_is_read_from_the_world():
    """R2 (A11, in). The +4.5% spread was hardcoded; the field is declared and
    dead. Its schema range (250-900bp) contains 450bp = exactly the hardcode."""
    lo = annualised(probe(6.5, **{"structural.private_credit.spread_over_base_bps": 300.0}), "pc")
    hi = annualised(probe(6.5, **{"structural.private_credit.spread_over_base_bps": 700.0}), "pc")
    assert hi - lo == pytest.approx(4.0, abs=0.20)


def test_r2_changes_no_shipped_preset():
    for path in sorted(PRESETS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert "spread_over_base_bps" not in doc["structural"].get("private_credit", {})
```

- [ ] **Step 2: run and watch the first fail**

Run: `uv run pytest tests/test_er14_inflation.py -k r2 -q` — Expected: FAIL (`hi - lo == 0.0`).

- [ ] **Step 3: implement**

```python
_DEF["pc_spread_bps"] = 450.0   # R2: the hardcoded +4.5%, now a default
```
```python
    pc_spread_pct = _f(st.private_credit, "spread_over_base_bps", _DEF["pc_spread_bps"]) / 100.0
```

- [ ] **Step 4: run the tests** — `uv run pytest tests/test_er14_inflation.py -q`; PASS,
and the AT deltas unchanged to 12 decimals (no preset declares the field).

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-03): R2 - private_credit.spread_over_base_bps is read; no preset number moves"
```

---

### Task C5: AT-6a in full, and the decoupling disclosure

**Files:**
- Modify: `tests/test_er14_inflation.py` (extend the AT-6a parametrization to `pc`)
- Modify: `docs/engine-realism-register.md` (ER-14: a working note, not the close-out —
  the close-out entry is written in `er14-05`)

**Interfaces:** none new.

- [ ] **Step 1: extend AT-6a to all three private assets**

```python
@pytest.mark.parametrize("asset", ["pe", "pc", "re"])
def test_at6a_the_inflation_channel_is_inert_at_the_anchor(asset, monkeypatch):
    """AT-6a. With the inflation path pinned at C_ANCHOR *and* theta_toy = 0,
    pe/pc/re are BIT-IDENTICAL to toy-v0.6 on every preset.

    theta_toy is excluded because the convex spread term is a SEPARATE declared
    change and is not inflation-keyed - saying so is more honest than a test that
    quietly covers two changes (design 6, AT-6a)."""
    monkeypatch.setattr(engine, "_THETA_TOY", 0.0)
    ref = np.load(ANCHOR_BASELINE_NPZ)
    for path in sorted(PRESETS.glob("*.json")):
        paths = run_path(project_numeric(load_worldspec(_anchored(path))), SEED)
        np.testing.assert_array_equal(paths.returns[asset], ref[f"{path.stem}/{asset}"])
```

Extending an existing parametrization is not weakening a test; the `pe`/`re` cases
written in `er14-02` stay exactly as they were.

- [ ] **Step 2: run it**

Run: `uv run pytest tests/test_er14_inflation.py -k at6a -q` — Expected: PASS for all
three assets. **If `pc` fails, STOP**: it means a term that should be inflation-keyed is
firing at the anchor, or `θ_toy` was folded into the wrong place.

- [ ] **Step 3: record the shadow-rate approximation in the register**

Append to ER-14's entry (still `open` at this point) a short working note: φ_PC makes the
loan's floating base a **shadow rate** that can differ from the engine's `rate` path;
this is an admitted approximation, defensible under ER-2 (the rate is a continuous drift
with no meeting calendar), with the clean alternative (a policy reaction function in
`_rate_path`) declined in design §2.4 and left as ask A8. **The close-out entry itself is
written in `er14-05` Task D2** — do not close ER-14 here.

- [ ] **Step 4: commit**

```bash
git commit -am "test(er14-03): AT-6a covers pc; the shadow-rate approximation recorded on ER-14"
```

---

### Task C6: WP `er14-03` close-out

Identical shape to Task M7:

- [ ] **Step 1:** `uv run ruff check . --fix && uv run ruff format . && uv run pyright` — clean.
- [ ] **Step 2:** full suite to `er14-03-full.log`; read the `EXIT:` line; reconcile
      `er14-red-ledger.md` exactly (a failure not on the ledger is a STOP).
- [ ] **Step 3:** `CHANGELOG.md`, one entry per task.
- [ ] **Step 4:** whole-WP adversarial review; re-verify all three lock digests unchanged.
- [ ] **Step 5:** `git checkout er14-release && git merge --no-ff er14-03-credit`.

---

# WP `er14-04b` — the infrastructure sleeve (branch `er14-04b-sleeve`)

**Scope:** put infrastructure in the book a player allocates — the engine's asset tuple,
the two independent private-set literals, the institution, the generated path, the
pacing row, the session contracts, the CIO view and the bundle contract.
**Discharges AT-11, AT-12, AT-14, AT-7.**

**The single highest-risk task in the release is S1.** Read R-1 in the risk table and
§2.7.2 of the design before touching `run_path`.

---

### Task S1: the engine gains `infra` — and the draw is appended LAST

**Files:**
- Modify: `src/ah/core/engine.py:107-117` (`ASSETS`, `REPORTED_SLEEVES`), `:122-139`
  (`_DEF`), `:329-340` (the draw block), `:433-448` (the returns dict), `:451-485`
  (`_reported_marks` weights)
- Create: `tests/test_er14_streams.py`
- Test: `tests/test_er14_inflation.py` (AT-11, AT-12)

**Interfaces:**
- Consumes: `infra_return(...)` (Task M6), `inflation_excess` (Task M2).
- Produces: `ASSETS` as a 9-tuple ending `"infra"`; `REPORTED_SLEEVES = ("pe","pc","re","infra")`;
  `EnginePaths.returns["infra"]`, `EnginePaths.reported["infra"]`;
  `_DEF["infra_yield"]=5.0`, `_DEF["infra_linkage"]=0.60`, `_DEF["infra_disc"]=0.0`,
  `_DEF["smooth_infra"]=0.35`. Every downstream task in this WP consumes `ASSETS`.

**AT-14 — quoted VERBATIM from the ratified design §6 (D-ER14-2 mandates it verbatim):**

> | **AT-14** | **Sleeve addition, if A14 is granted: the draw-order guard.** With `infra` added to `ASSETS`, the five public assets **and** `pe`/`pc`/`re` must remain bit-identical to the no-infra build on every preset | exact equality | §2.7.2: appending the new Student-t draw at the end of the block preserves every existing stream; inserting it anywhere else silently corrupts every world. This test is the only thing standing between a one-line mistake and an undetectable one |

And the hard constraint it enforces, also verbatim, from design §2.7.2:

> **Hard constraint for the implementation plan: the new draw is appended at the end
> of the existing draw block, never inserted.** Appended, every existing stream is
> bit-identical and AT-6b/AT-7 hold. This is the single highest-risk line in the
> whole sleeve addition and it is one line.

- [ ] **Step 1: capture the no-infra baseline (AT-14's reference)**

The reference is the tree **as it stands right now** — mechanisms complete, no sleeve.
Extend `scripts/gen_er14_baseline.py`'s `__main__` with a second call and run it:

```python
    build("tests/fixtures/er14/no-infra-baseline", ("equity", "bonds", "hy", "commodities",
                                                    "reits", "pe", "pc", "re"))
```

Run: `uv run python scripts/gen_er14_baseline.py`
Commit the fixture **before** editing `engine.py`. Record the git sha in the sidecar JSON.

- [ ] **Step 2: write the failing tests**

```python
# tests/test_er14_streams.py

def test_at14_the_draw_order_guard():
    """AT-14 (D-ER14-2, mandated verbatim). With infra added to ASSETS, the five
    public assets AND pe/pc/re must remain bit-identical to the no-infra build on
    every preset.

    Design 2.7.2: appending the new Student-t draw at the end of the block
    preserves every existing stream; inserting it anywhere else silently corrupts
    every world. This test is the only thing standing between a one-line mistake
    and an undetectable one."""
    ref = np.load(NO_INFRA_BASELINE_NPZ)
    for path in sorted(PRESETS.glob("*.json")):
        paths = run_path(project_numeric(load_worldspec(_load(path))), SEED)
        for asset in ("equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re"):
            np.testing.assert_array_equal(
                paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
            )


def test_at7_the_draw_block_order_is_the_declared_one():
    """AT-7. The draw order in run_path is unchanged and e_infra is LAST. Read as
    source, because the ordering - not any value - is the invariant."""
    src = inspect.getsource(engine.run_path)
    block = src.split("crisis = _crisis_mask")[0]
    drawn = re.findall(r"^\s*(\w+) = (?:rng\.standard_normal|_t_draws)\(", block, re.M)
    assert drawn == [
        "z_rate", "z_spread", "z_infl", "z_m",
        "e_eq", "e_hy", "e_com", "e_b", "e_reit",
        "e_pe", "e_pc", "e_re",
        "e_infra",          # appended, never inserted (design 2.7.2)
    ]


def _redraw_streams(seed: int, nm: int) -> dict[str, np.ndarray]:
    """Re-draw run_path's up-front block, in the DECLARED order, from a fresh
    generator - the only honest way to inspect the streams without exporting
    them from production code."""
    rng = np.random.Generator(np.random.PCG64(seed))
    out = {name: rng.standard_normal(nm) for name in ("z_rate", "z_spread", "z_infl")}
    for name in ("z_m", "e_eq", "e_hy", "e_com", "e_b", "e_reit",
                 "e_pe", "e_pc", "e_re", "e_infra"):
        out[name] = engine._t_draws(rng, nm)
    return out


def test_e_infra_is_its_own_tape_not_a_copy_of_another_stream():
    """Distinct-tape guard (the seed-stride lesson: reusing the platform stride on
    a new axis collapsed 20 spines to 2). e_infra must correlate with no existing
    innovation stream, and must not equal one."""
    streams = _redraw_streams(seed=12345, nm=120)
    for name, other in streams.items():
        if name == "e_infra":
            continue
        assert not np.array_equal(streams["e_infra"], other), name
        assert abs(np.corrcoef(streams["e_infra"], other)[0, 1]) < 0.25, name
```

```python
# tests/test_er14_inflation.py

def test_at11_infrastructure_is_the_strongest_responder_in_the_book():
    """AT-11. Delta annualised infra, 1% -> 12%, must be POSITIVE and >= +4.0
    pp/yr (lambda_INFRA's declared range floor 0.4 x 11pp - rounding). Also
    required: infra's response must EXCEED real estate's on the same probe - the
    RANKING is the substantive claim, and a mechanism that got the levels right
    but the order wrong would be worse than useless to an allocator."""
    d_infra = annualised(probe(12.0), "infra") - annualised(probe(1.0), "infra")
    d_re = annualised(probe(12.0), "re") - annualised(probe(1.0), "re")
    assert d_infra >= 4.0, d_infra
    assert d_infra > d_re, (d_infra, d_re)


def test_at12_the_dead_field_is_alive():
    """AT-12. Two worlds identical but for
    structural.infrastructure.inflation_linkage = 0.3 vs 0.9 must produce
    DIFFERENT infra returns, and the ratio of their inflation responses must be
    0.33 +/- 0.05.

    This is the second inverted defect: ER-14's most quotable line is that the
    contract's only inflation-linkage field belongs to a class the engine does not
    simulate."""
    key = "structural.infrastructure.inflation_linkage"
    lo_hot, lo_cold = probe(12.0, **{key: 0.3}), probe(1.0, **{key: 0.3})
    hi_hot, hi_cold = probe(12.0, **{key: 0.9}), probe(1.0, **{key: 0.9})
    assert not np.array_equal(lo_hot.returns["infra"], hi_hot.returns["infra"])
    resp_lo = annualised(lo_hot, "infra") - annualised(lo_cold, "infra")
    resp_hi = annualised(hi_hot, "infra") - annualised(hi_cold, "infra")
    assert resp_lo / resp_hi == pytest.approx(0.333, abs=0.05)
```

- [ ] **Step 3: run them and watch them fail**

Run: `uv run pytest tests/test_er14_streams.py tests/test_er14_inflation.py -k "at14 or at7 or at11 or at12 or e_infra" -q`
Expected: AT-11/AT-12 FAIL with `KeyError: 'infra'`; AT-7 FAILs on the missing entry;
AT-14 PASSES (nothing has changed yet — it is armed).

- [ ] **Step 4: implement — the one-line rule first**

```python
ASSETS: tuple[str, ...] = (
    "equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re",
    # ER-14 close-out (D-ER14-2): the fourth private class. APPENDED - the tuple's
    # order is the digest contract and infra must be last for the same reason its
    # draw is (design 2.7.2).
    "infra",
)
REPORTED_SLEEVES: tuple[str, ...] = ("pe", "pc", "re", "infra")
```

In `run_path`, **append after `e_re` and nowhere else**:

```python
    e_re = _t_draws(rng, nm)
    # ER-14 close-out. APPENDED AT THE END OF THE BLOCK, NEVER INSERTED: any other
    # position shifts every subsequent stream and silently changes e_pe/e_pc/e_re -
    # and, through the common-factor construction, the public assets too - in every
    # world, with no test naming the cause. AT-14 in tests/test_er14_streams.py is
    # the guard; design 2.7.2 is the argument.
    e_infra = _t_draws(rng, nm)
```

Then the return, the dict entry, and the reported weight:

```python
    infra = infra_return(
        x=x, d_x=d_x, d_rate=d_rate, eq=eq, e_infra=e_infra, crisis=crisis,
        linkage=_f(st.infrastructure, "inflation_linkage", _DEF["infra_linkage"]),
        disc_shift_bps=_f(st.infrastructure, "discount_rate_shift_bps", _DEF["infra_disc"]),
        yield_pct=_DEF["infra_yield"],   # no schema field exists for it (design 2.7.0)
        nm=nm,
    )
    returns = {..., "re": re, "infra": infra}
```
In `_reported_marks`, the weights dict maps the sleeve key to the schema's field name —
follow the existing three exactly and add the fourth:

```python
    weights = {
        "pe": _f(weights_model, "private_equity", _DEF["smooth_pe"]),
        "pc": _f(weights_model, "private_credit", _DEF["smooth_pc"]),
        "re": _f(weights_model, "real_estate", _DEF["smooth_re"]),
        "infra": _f(weights_model, "infrastructure", _DEF["smooth_infra"]),
    }
```

- [ ] **Step 5: run the tests**

Run: `uv run pytest tests/test_er14_streams.py tests/test_er14_inflation.py -q`
Expected: **all PASS, including AT-14 and AT-6b.** If AT-14 goes red here, the draw is
in the wrong place — fix the position, do not re-pin the baseline.

- [ ] **Step 6: the mandatory break-and-revert (design §6's second anti-test guard)**

Move `e_infra = _t_draws(rng, nm)` to the **top** of the draw block. Run
`uv run pytest tests/test_er14_streams.py -k at14 -q` and confirm it goes **RED** with
mismatches on `equity` (i.e. the corruption is real and detected). Revert the move,
re-run, confirm green. Paste both outputs into the commit body. **This step is not
optional**: it is the evidence that AT-14 bites.

- [ ] **Step 7: verify the WorldSpec mirror needs nothing**

`src/ah/core/worldspec.py` already carries `class Infrastructure` (line 331),
`Smoothing.infrastructure` (line 340) and `Structural.infrastructure` (line 353), and
`schemas/worldspec-v1.3.schema.json` already declares all three. Add a test asserting
that (so a future edit cannot quietly diverge):

```python
def test_the_contract_already_anticipated_this_class():
    """schemas/ is read-only vendored truth and does NOT block the sleeve
    (design 2.7.0): no schema enumerates the asset or sleeve set, and both
    infrastructure fields plus the smoothing weight are already declared."""
    schema = json.loads(Path("schemas/worldspec-v1.3.schema.json").read_text())
    infra = schema["properties"]["structural"]["properties"]["infrastructure"]["properties"]
    assert set(infra) == {"discount_rate_shift_bps", "inflation_linkage"}
    assert "infrastructure" in Smoothing.model_fields
    assert "infrastructure" in Structural.model_fields
```

- [ ] **Step 8: commit**

```bash
git commit -am "feat(er14-04b): infra joins ASSETS - the Student-t draw appended LAST; AT-14, AT-11, AT-12, AT-7"
```

---

### Task S2: the played book — BOTH private-set literals

**Files:**
- Modify: `src/ah/play.py:95` (`PRIVATE_ASSETS`), `:108-117` (`START_TARGETS`),
  `:333-334` (`_GROWTH`/`_DEFENSIVE`), `:618-640` and `:763` (`_secondary_sale`),
  `:482-520` (the seed-ladder docstring that says "all three sleeves")
- Modify: `src/ah/port/book.py:38` (`PRIVATE_SLEEVES`), `:103` (`_RESERVED_COHORT_ID`),
  `:122-134` (`CommitmentPlan._shape`), `:26` (`BOOK_STATE_VERSION`), `:145` (the
  `state_version` Literal)
- Test: `tests/test_play.py`, `tests/test_book.py`, `tests/test_book_defaults.py`

**Interfaces:**
- Produces: `play.PRIVATE_ASSETS = ("pe", "pc", "re", "infra")`;
  `book.PRIVATE_SLEEVES = ("pe", "pc", "re", "infra")`;
  `BOOK_STATE_VERSION = "opening-book-0.3"` with `state_version: Literal["opening-book-0.1", "opening-book-0.2", "opening-book-0.3"]`;
  `START_TARGETS` = equity 33, bonds 12, hy 5, commodities 5, **reits 5**, pe 20, pc 8,
  **re 5**, **infra 5** (98.0 + `START_CASH` 2.0).

**Finding this task exists for (not in the design):** the private set is declared
**twice** — `play.PRIVATE_ASSETS` and `port/book.py`'s `PRIVATE_SLEEVES` — and
`CommitmentPlan._shape` raises `plan must name exactly ['pc','pe','re']` unless a plan
names exactly that set. Change both together or every served plan 422s.

- [ ] **Step 1: write the failing tests**

```python
def test_the_private_set_is_declared_once_in_effect():
    """port/book.py carries an INDEPENDENT literal of the private set. It gates
    every CommitmentPlan by shape, so a divergence 422s every plan the server
    itself just served."""
    from ah.play import PRIVATE_ASSETS
    from ah.port.book import PRIVATE_SLEEVES
    assert tuple(sorted(PRIVATE_ASSETS)) == tuple(sorted(PRIVATE_SLEEVES))


def test_the_opening_book_still_sits_inside_the_policy_band():
    """The carve keeps private at 38 of 100, NOT 40: carving all five points from
    REITs would put private exactly on private_weight_range's upper bound and
    re-create the opening breach that produced 29 forced quarters out of 40
    (play.py:99-107)."""
    assert 0.15 < _policy_private_weight(START_TARGETS) < 0.40
    assert sum(START_TARGETS[a] for a in PRIVATE_ASSETS) == pytest.approx(38.0)


def test_the_real_goal_bucket_is_unchanged_by_the_carve():
    """A15: 3 points from REITs and 2 from real estate, so commodities 5 + reits 5
    + re 5 + infra 5 = 20 points, exactly as now, and the CIO dashboard's goal
    display does not shift for an unrelated reason. Commodities is DELIBERATELY
    untouched: ER-14's own attribution experiment moves those five points, and
    touching the sleeve would confound the measurement the close-out is judged
    against."""
    assert START_TARGETS["commodities"] == 5.0
    assert sum(START_TARGETS[a] for a in ("commodities", "reits", "re", "infra")) == 20.0


def test_infrastructure_is_excluded_from_the_secondary_lever_by_decision():
    """A16, ratified: infra is excluded from the secondary-sale lever for now
    (infrastructure secondaries are genuinely thin). _secondary_sale is scoped to
    the pe ladder by an EXPLICIT constant, not by an accident of a hardcoded key."""
    from ah.play import SECONDARY_SLEEVE
    assert SECONDARY_SLEEVE == "pe"


def test_every_private_sleeve_gets_a_seeded_ladder():
    book = default_opening_book(...)
    assert set(book.private) == set(PRIVATE_ASSETS)
```

- [ ] **Step 2: run and watch them fail**

Run: `uv run pytest tests/test_play.py tests/test_book.py -k "private or carve or secondary" -q`
Expected: FAIL on the set comparison and the targets.

- [ ] **Step 3: implement**

```python
PRIVATE_ASSETS: tuple[str, ...] = ("pe", "pc", "re", "infra")

# A15 (D-ER14-2): infrastructure enters at 5 points, carved 3 from REITs and 2
# from real estate. Private lands at 38, not 40 - the policy band's upper bound
# is 0.40 and an opening breach previously produced 29 forced quarters out of 40.
START_TARGETS: dict[str, float] = {
    "equity": 33.0, "bonds": 12.0, "hy": 5.0, "commodities": 5.0, "reits": 5.0,
    "pe": 20.0, "pc": 8.0, "re": 5.0, "infra": 5.0,
}

# A16 (D-ER14-2): the forced/voluntary secondary lever stays scoped to buyout.
# Infrastructure secondaries are thin; this is a DECISION, recorded here rather
# than left implicit in a hardcoded "pe_ladder" key (design 2.7.1).
SECONDARY_SLEEVE = "pe"
```
Rewrite `_secondary_sale`'s call site to use `f"{SECONDARY_SLEEVE}_ladder"` and
`ladders[SECONDARY_SLEEVE]` so the scope is stated once, in one place.

`_GROWTH`/`_DEFENSIVE`: **infra joins neither** — matching how `re`, `reits` and
`commodities` are already treated (design §2.7.1). `_rebalance` filters both tuples to
`LIQUID_ASSETS`, so an entry would be a no-op that misleads a reader. Record the
decision in a comment.

In `src/ah/port/book.py`:
```python
PRIVATE_SLEEVES: tuple[str, ...] = ("pe", "pc", "re", "infra")   # keep in step with play.PRIVATE_ASSETS
BOOK_STATE_VERSION = "opening-book-0.3"   # 0.3: the fourth private sleeve (ER-14)
```
and widen the `state_version` Literal to accept `0.1`/`0.2`/`0.3` (old documents stay
readable — the house rule is fence, never delete).

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_play.py tests/test_book.py tests/test_book_defaults.py -q`
Expected: the new tests PASS; value goldens FAIL and go on the red ledger
(`test_golden_hold_course_final_value`, `test_the_ladder_opens_at_exactly_the_same_allocation_as_before`,
`test_the_toy_book_carries_reits_and_the_generated_book_does_not`, etc.). **A failure
that is a *shape* error rather than a *value* change is a STOP.**

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-04b): infrastructure in the played book - both private-set literals, the A15 carve, the A16 secondary scope"
```

---

### Task S3: the institution

**Files:**
- Modify: `src/ah/core/institution.py:27-37` (`SLEEVES`), `:39-48` (`START_MIX`),
  `:50-51` (`GROWTH`/`DEFENSIVE`), `:144-151` (the `secondary` branch)
- Test: `tests/test_institution.py`

**Interfaces:**
- Produces: `SLEEVES` as a 9-tuple in `ASSETS` order; `START_MIX` summing to 1.0 with
  `"infra": 0.05` carved from `reits` 0.05 → 0.03 and `re` 0.10 → 0.08.

- [ ] **Step 1: write the failing tests**

```python
def test_start_mix_sums_to_one_with_the_fourth_private_sleeve():
    assert sum(START_MIX.values()) == pytest.approx(1.0)
    assert set(START_MIX) == set(SLEEVES)


def test_sleeve_order_matches_the_engines_asset_order():
    """feed.py:330 zips institution weights against asset names positionally - a
    divergence mislabels every board-pack allocation line SILENTLY."""
    assert SLEEVES == ASSETS


def test_infrastructure_joins_neither_tilt_bucket():
    """Matching how re, reits and commodities are already treated (design 2.7.1)."""
    assert "infra" not in GROWTH and "infra" not in DEFENSIVE
```

- [ ] **Step 2: run them** — Expected: FAIL on the set/order comparisons.

- [ ] **Step 3: implement** — append `"infra"` to `SLEEVES` (same order as `ASSETS`);
`START_MIX` gains `"infra": 0.05` with `reits` 0.05 → 0.03 and `re` 0.10 → 0.08 (the
same proportional carve as the play book, keeping the real-asset weight constant);
leave the `secondary` branch's pe→bonds hardcode **unchanged** (A16 scope) and add a
one-line comment saying so.

- [ ] **Step 4: run the tests** — the three new tests PASS;
`test_golden_hold_course_final_value` FAILs → red ledger (`value-golden`).

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-04b): the twin's sleeve set and start mix gain infrastructure"
```

---

### Task S4: the generated path

**Files:**
- Modify: `src/ah/port/adapter.py:72-77` (`PM_SLEEVE_FOR_ASSET`, `_PM_ASSET_ORDER`),
  `:95-118` (`GEN_START_TARGETS`, `GEN_START_MIX`), `:191-201` (the residual draw)
- Test: `tests/test_gen_adapter.py`

**Interfaces:**
- Produces: `PM_SLEEVE_FOR_ASSET["infra"] = "pm_infra"`;
  `_PM_ASSET_ORDER = ("pe", "pc", "re", "infra")`; `GEN_ASSETS` auto-inherits `infra`
  (it is `tuple(a for a in ASSETS if a != "reits")`).

**Finding this task exists for (not in the design):** `adapter.py:192` draws
`rng.standard_normal((months, len(_PM_ASSET_ORDER)))`. `standard_normal` fills
**row-major**, so widening the matrix from 3 to 4 columns **re-rolls pe/pc/re residuals**
even though `infra` is appended last. AT-14's bit-identity claim is therefore **scoped to
the toy plane**, exactly as AT-14 words it ("on every preset"). The generated plane's
digests move in this release regardless — `GEN_PLAY_ALPHA_VERSION` bumps and the played
generated world moves `…603` → `…604` — so nothing is lost, but it must be **stated**,
not discovered. Do **not** "fix" it by restructuring the draw into per-sleeve streams:
that would be a second, unattributed numeric change in the same release (the ER-12 lesson).

- [ ] **Step 1: write the failing tests**

```python
def test_infra_maps_to_the_already_estimated_pm_infra_row():
    """The pm_infra row already exists in the sealed v1.1 artifact - estimated,
    60 quarters, sum-beta(2) - so the generated path needs NO new estimation for
    infrastructure (design 2.7.1). infra_core stays parked as Tier B evergreen."""
    assert PM_SLEEVE_FOR_ASSET["infra"] == "pm_infra"
    art = yaml.safe_load(Path("mappings/sleeve-mappings-v1.1.yaml").read_text())
    assert "pm_infra" in art["pm_sleeves"]


def test_generated_assets_carry_infra_and_still_drop_reits():
    assert "infra" in GEN_ASSETS and "reits" not in GEN_ASSETS   # OD-3 unchanged


def test_the_pm_residual_matrix_widened_and_this_is_disclosed():
    """standard_normal fills row-major, so a fourth column re-rolls pe/pc/re. The
    generated plane's digests move in this release anyway (GEN_PLAY_ALPHA_VERSION
    bumps, the played world moves 603 -> 604). Recorded here so the next reader
    does not mistake it for corruption."""
    ens = run_gen_path(...)
    assert ens.returns["infra"].shape == ens.returns["pe"].shape
```

- [ ] **Step 2: run them** — Expected: FAIL with `KeyError: 'infra'`.

- [ ] **Step 3: implement** — add the mapping, append `"infra"` to `_PM_ASSET_ORDER`,
and re-carve `GEN_START_TARGETS` (equity 41, bonds 12, hy 5, commodities 5, pe 20, pc 8,
**re 5**, **infra 5** = 98.0 — the generated book has no REITs, so the two points come
from real estate and the remaining three from equity: state the carve in a comment and
keep the private total at 38) and `GEN_START_MIX` (add `"infra": 0.05`, `re` 0.10 → 0.08,
`equity` 0.35 → 0.32).

- [ ] **Step 4: run the tests** — new tests PASS; `test_gen_path_digest_is_stable`,
`test_gen_results_digest_without_reits`, `test_toy_digests_are_byte_identical_to_before_the_threading`
FAIL → red ledger (`value-golden`).

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-04b): the generated path carries infra on the sealed pm_infra row (residual matrix widening disclosed)"
```

---

### Task S5: the pacing artifact gains a `pm_infra` row

**Files:**
- Modify: `mappings/pacing-parameters-v1.0.yaml`
- Test: `tests/test_pacing_artifact.py`, `tests/test_play.py` (ladder length)

**Interfaces:**
- Produces: `sleeves.pm_infra = {contractual_life_years: 15.0, bow: 2.5, yield_rate: 0.55, rc_curve: [0.35, 0.40, 0.30, 0.25, 0.20, 0.15]}`.

**Governance:** the file is in **no lock** (verified across all three) but is
owner-approved under WI-I6-1 (2026-08-02) with `tests/test_pacing_artifact.py` as its
drift guard — an owner event, ratified in D-ER14-2 ("pacing gains one pm_infra row,
contractual_life_years 15, drift-guarded").

- [ ] **Step 1: read the artifact before and after**

Run: `uv run python scripts/inspect_pacing.py > pacing-before.txt`
Keep the file; it goes in the commit body.

- [ ] **Step 2: write the failing tests**

```python
def test_the_infra_row_makes_exactly_one_claim():
    """A16, ratified: contractual_life_years 15 against buyout's 10, anchored in
    taxonomy/sleeves.yaml's own pm_infra note ('Long lives; extension behavior
    matters'). bow and yield_rate carry over from pm_buyout UNCHANGED, so the new
    row makes exactly one claim."""
    table = yaml.safe_load(Path("mappings/pacing-parameters-v1.0.yaml").read_text())
    buyout, infra = table["sleeves"]["pm_buyout"], table["sleeves"]["pm_infra"]
    assert infra["contractual_life_years"] == 15.0
    assert infra["bow"] == buyout["bow"]
    assert infra["yield_rate"] == buyout["yield_rate"]
    assert infra["rc_curve"] == buyout["rc_curve"]


def test_the_infra_ladder_has_one_rung_per_year_of_contractual_life():
    """ER-12's close-out extends by construction: at a 15-year life the opening
    staggered book is 15 rungs, not 10."""
    book = default_opening_book(...)
    assert len(book.private["infra"]) == 15
    assert len(book.private["pe"]) == 10
```

- [ ] **Step 3: run them** — Expected: FAIL (`KeyError: 'pm_infra'`).

- [ ] **Step 4: implement** — add the row to the artifact, and make the ladder builder
resolve its rung count from the sleeve's own `contractual_life_years` (via
`PM_SLEEVE_FOR_ASSET`) rather than a literal 10, if it does not already. **If
`_seed_ladder` turns out to hardcode 10 rungs, that is a real change: state it in the
commit body and re-check `test_the_ladder_is_staggered_one_rung_per_year_of_fund_life`.**

- [ ] **Step 5: run the tests and diff the inspection**

Run: `uv run pytest tests/test_pacing_artifact.py tests/test_pacing_core.py -q`
Run: `uv run python scripts/inspect_pacing.py > pacing-after.txt && diff pacing-before.txt pacing-after.txt`
Expected: exactly one new sleeve block in the diff; `pm_buyout`'s lines unchanged.

- [ ] **Step 6: commit**

```bash
git commit -am "feat(er14-04b): pacing gains the pm_infra row (life 15y, one claim); ladder extends to 15 rungs"
```

---

### Task S6: the session service, the moved digest, and the announced demotion

**Files:**
- Modify: `src/ah/serve.py` (`/book/default`, `/book/ladder`'s 422 message, `POST /sessions`
  window-count check, `_band_report` ordering)
- Test: `tests/test_serve_book.py`, `tests/test_serve.py`

**Interfaces:**
- Consumes: `play.PRIVATE_ASSETS`, `book.PRIVATE_SLEEVES` (Task S2).
- Produces: no new endpoint; `/book/default` now returns four private sleeves and a
  **moved** `book_digest` / `plan_digest`.

- [ ] **Step 1: write the failing tests**

```python
def test_the_served_default_book_carries_four_private_sleeves():
    body = client.get(f"/book/default?run_id={run_id}").json()
    assert set(body["book"]["private"]) == {"pe", "pc", "re", "infra"}
    assert set(body["plan"]["points"]) == {"pe", "pc", "re", "infra"}


def test_the_default_book_submitted_back_still_keeps_ranked():
    """Ruling D's invariant: the served default and the pre-fill move together, so
    an untouched POST still digests as the default."""
    body = client.get(f"/book/default?run_id={run_id}").json()
    r = client.post("/sessions", json={..., "book": body["book"], "plan": body["plan"], "ranked": True})
    assert r.json()["ranked"] is True


def test_a_three_sleeve_book_is_demoted_to_practice_not_crashed():
    """ER-15, accepted side effect (D-ER14-2): the default book gains a fourth
    private sleeve, so its digest moves and every in-flight session is
    invalidated. Old three-sleeve posts demote to practice - correct behaviour,
    announced rather than discovered."""
    r = client.post("/sessions", json={..., "book": _legacy_three_sleeve_book(), "ranked": True})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["ranked"] is False


def test_the_unknown_sleeve_422_names_the_new_set():
    r = client.get(f"/book/ladder?run_id={run_id}&sleeve=nope&value=5")
    assert r.status_code == 422 and "infra" in r.json()["detail"]
```

**Decide and record in the commit body:** a legacy three-sleeve plan fails
`CommitmentPlan._shape` and therefore 422s rather than demoting. Both outcomes are
defensible; the test above accepts either but **pins whichever the code does**, and the
choice is announced. Recommended: let it 422 with a message naming the new sleeve set —
a plan that cannot name the world's sleeves is malformed, not merely edited.

- [ ] **Step 2: run them** — Expected: FAIL (three sleeves served).

- [ ] **Step 3: implement** — the endpoints are already comprehensions over
`PRIVATE_ASSETS`; the work is the 422 strings, the window-count loop (now four sleeves),
and a docstring on `POST /sessions` recording the ER-15 demotion with its date and
D-ER14-2 as authority.

- [ ] **Step 4: run the tests** and restart the live service before any manual check:
`Get-NetTCPConnection -LocalPort 8787` → `Stop-Process`, then
`uv run uvicorn ah.serve:app --port 8787` from the branch tree. (Checking port 8000 will
tell you it is down when it is not.)

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-04b): the session service serves a four-sleeve book; the ER-15 demotion announced"
```

---

### Task S7: the CIO view and the other display surfaces

**Files:**
- Modify: `src/ah/cioview.py:53-63` (`GOAL_OF`), `:64-74` (`CLASS_LABEL`), `:75-90` (`BAND_PCT`)
- Modify: `src/ah/console.py:854, 905` (per-sleeve table columns),
  `src/ah/credibility.py` (asset_order-driven; verify), `src/ah/inspect.py` (correlogram size)
- Test: `tests/test_cioview.py`, `tests/test_credibility.py`, `tests/test_inspect.py`

**Interfaces:**
- Produces: `GOAL_OF["infra"] = "real"`, `CLASS_LABEL["infra"] = "Infrastructure"`,
  `BAND_PCT["infra"] = 2.0`.

**Three unguarded lookups will `KeyError` without this task:** `CLASS_LABEL[...]`
(lines 490, 691, 747, 803, 821), `BAND_PCT[cid]` (line 477), `GOAL_OF[cid]` (lines 481,
491).

- [ ] **Step 1: write the failing tests**

```python
def test_every_asset_has_a_goal_a_label_and_a_fallback_band():
    """Three unguarded dict lookups in cioview KeyError on an unmapped asset."""
    for asset in (*ASSETS, "cash"):
        assert asset in GOAL_OF and asset in CLASS_LABEL and asset in BAND_PCT


def test_infrastructure_reads_as_a_real_asset_and_as_illiquid():
    """GOAL_OF real (design 2.7.1). Tier assignment is automatic - everything in
    PRIVATE_ASSETS is the illiquid remainder - so no tier edit is needed."""
    assert GOAL_OF["infra"] == "real"
    view = build_cio_view(...)
    assert _class(view, "infra")["liquid"] is False


def test_the_no_book_band_fallback_is_the_real_estate_value():
    """A15: BAND_PCT['infra'] = 2.0, matching re."""
    assert BAND_PCT["infra"] == BAND_PCT["re"] == 2.0
```

- [ ] **Step 2: run them** — Expected: FAIL with `KeyError: 'infra'`.

- [ ] **Step 3: implement** the three dict entries; then run the console/inspect/
credibility suites and fix any per-sleeve column count that is written as a literal
(`console.py:854, 905` build `<th>` cells from `PRIVATE_ASSETS`, so they follow — confirm
the rendered table's column count in the test).

- [ ] **Step 4: run the tests**

Run: `uv run pytest tests/test_cioview.py tests/test_credibility.py tests/test_inspect.py tests/test_console_guard.py -q`
Expected: the new tests PASS; fixture-byte-equality and value goldens FAIL → red ledger.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-04b): the CIO view and the consoles carry infrastructure (real-asset goal, illiquid tier)"
```

---

### Task S8: the bundle contract and the committed fixtures

**Files:**
- Modify: `src/ah/bundle.py:57` (`BUNDLE_VERSION`)
- Regenerate: `app/fixtures/toy.bundle.gz`, `app/fixtures/gen.bundle.gz` (via
  `scripts/gen_bundle_fixtures.py`), `app/fixtures/cio-sample.{reported,true,decided}.json`
  (via `scripts/gen_cio_fixture.py`)
- Test: `tests/test_bundle.py`, `tests/test_cioview.py` (the byte-equality regeneration test)

**Interfaces:**
- Produces: `BUNDLE_VERSION = "world-bundle-0.6"`.

- [ ] **Step 1: the STOP check — does any decoder pin a count?**

```bash
git grep -n "series_order\|bundle_version\|world-bundle" app/src src tests
```
Confirm (as inspected 2026-08-18) that `app/src/lib/bundle.ts` pins tape **rows** to
`meta.months` and does **not** pin a column count, and that `tests/test_bundle.py`
derives `series_order` from `ASSETS`/`REPORTED_SLEEVES` rather than a literal.
**If a decoder pins a count — STOP and decide** whether the contract version can carry
the change before writing anything (risk R-8).

- [ ] **Step 2: write the failing test**

```python
def test_the_bundle_carries_the_new_series_set_under_a_new_contract_version():
    """Toy: 8+3 = 11 columns becomes 9+4 = 13. Generated: 7+3 = 10 becomes 8+4 =
    12. The payload's asset set changed, so the version - the app's compatibility
    handle - moves with it."""
    doc = build_bundle(...)
    assert doc["bundle_version"] == "world-bundle-0.6"
    assert doc["revealed"]["series_order"] == [*ASSETS, *(f"{s}_reported" for s in REPORTED_SLEEVES)]
    assert len(doc["revealed"]["series_order"]) == 13
```

- [ ] **Step 3: run it** — Expected: FAIL on the version string.

- [ ] **Step 4: implement and regenerate**

```python
BUNDLE_VERSION = "world-bundle-0.6"  # 0.6: the fourth private sleeve (ER-14 close-out)
```
Run: `uv run python scripts/gen_bundle_fixtures.py` (the generated bundle needs the local
vintage store — OD-4; if it is unavailable, **stop and get it**, do not hand-edit a
fixture).
Run: `uv run python scripts/gen_cio_fixture.py`
Check the compressed size stays under `MAX_COMPRESSED_BYTES` (1 MB): two extra columns on
a ~31 KB bundle leave ample headroom, but assert it, do not assume it.

- [ ] **Step 5: run the tests**

Run: `uv run pytest tests/test_bundle.py tests/test_cioview.py -q`
Expected: PASS (the fixtures now match the code). `cd app && npm run test` will still be
red until WP `er14-04c` — record those in the red ledger with cause `bundle-fixture`.

- [ ] **Step 6: commit**

```bash
git commit -am "feat(er14-04b): world-bundle-0.6 - thirteen toy series, twelve generated; fixtures regenerated"
```

---

### Task S9: WP `er14-04b` close-out

- [ ] **Step 1:** `uv run ruff check . --fix && uv run ruff format . && uv run pyright` — clean.
- [ ] **Step 2:** full suite to `er14-04b-full.log`; read the `EXIT:` line and the pass
      count; reconcile `er14-red-ledger.md` exactly. **Every remaining failure must be a
      value golden, a world-id pin or an app fixture.**
- [ ] **Step 3:** `CHANGELOG.md`, one entry per task, naming A14/A15/A16 and D-ER14-2.
- [ ] **Step 4:** whole-WP adversarial review. Re-run the AT-14 break-and-revert once
      more at the WP tip (the draw block may have been touched by a later task), and
      re-verify all three lock digests.
- [ ] **Step 5:** `git checkout er14-release && git merge --no-ff er14-04b-sleeve`.

---

# WP `er14-04c` — the app (branch `er14-04c-app`)

**Scope:** a fourth private asset class through every label map, the book entry grid, the
decision window, the CIO dashboard and the vintage charts, plus every fixture and pinned
list. The design calls this "the bulk of the cost".

**No new server contract.** If a task here needs a server change, that is a finding:
stop, record it, and decide whether it belongs in `er14-04b`.

---

### Task A1: the label maps and the private set

**Files:**
- Modify: `app/src/lib/assetLabels.ts:13-22` (`ASSET_LABELS`),
  `app/src/lib/sleeveLabels.ts:18-28` (`SLEEVE_LABEL`),
  `app/src/Play.tsx:57` (`PRIVATE_ASSETS` Set) and its "eight charts" docstring at `:79`,
  `app/src/components/DecisionWindow.tsx:64-68` (`PRIVATE_SLEEVES`)
- Test: `app/src/lib/assetLabels.test.ts` (or nearest), `app/src/components/DecisionWindow.test.tsx`

**Interfaces:**
- Produces: `ASSET_LABELS` gains `["infra", "Infrastructure"]` in engine-contract order;
  `SLEEVE_LABEL.infra = "Infrastructure"`; `PRIVATE_ASSETS = new Set(["pe","pc","re","infra"])`;
  `DecisionWindow`'s `PRIVATE_SLEEVES` gains `["infra", "Infrastructure"]`.

- [ ] **Step 1: write the failing tests**

```ts
it("labels every asset the engine ships", () => {
  // player-facing copy is the full capitalized name (owner rule, app-open-01)
  expect(ASSET_LABELS.map(([k]) => k)).toEqual(
    ["equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re", "infra"],
  );
  expect(labelFor("infra")).toBe("Infrastructure");
});

it("offers a commit row for every private sleeve the server serves", () => {
  render(<DecisionWindow {...props} planCommitments={{ pe: 1.5, pc: 1.2, re: 0.9, infra: 0.4 }} />);
  expect(screen.getByLabelText("Infrastructure commitment")).toBeInTheDocument();
});
```

- [ ] **Step 2: run them** — `cd app && npx vitest run src/lib src/components/DecisionWindow.test.tsx`
      Expected: FAIL on the missing key/row.

- [ ] **Step 3: implement** the four literals. `DecisionWindow`'s secondary copy
      ("Sell up to 8pts of private equity at an 18% discount") stays **unchanged** — A16
      keeps the lever on buyout.

- [ ] **Step 4: run the tests** — PASS.

- [ ] **Step 5: commit**

```bash
git commit -m "feat(er14-04c): Infrastructure in the label maps, the private set and the decision window"
```

---

### Task A2: the opening book screen

**Files:**
- Modify: `app/src/components/BookEntry.tsx` (the targets table, the ranges row, the
  per-sleeve vintage ladder and its `VintageChart`)
- Test: `app/src/BookEntry.test.tsx` (fixtures at `:83`, `:97`, `:108-124`; the
  eight-target-row test at `:615`; the reits assertions at `:253`, `:612`)

**Interfaces:**
- Consumes: `/book/default`'s four-sleeve `book.private` and `plan.points` (Task S6).
- Produces: no new component; `BookEntry` renders `book.private`'s keys, so the work is
  fixtures, counts and copy.

- [ ] **Step 1: update the fixtures to the served shape**

The three fixtures (`targets` at `:83`, `plan.points` at `:97`, `WITH_REITS` at
`:108-124`) are hand-written server shapes. Regenerate them **from the served payload**
(`GET /book/default` against a local toy run and a generated run) rather than by editing
literals — a hand-edited fixture that disagrees with the server is how the app and the
server drift.

- [ ] **Step 2: write the failing tests**

```ts
it("renders nine target rows for a world that carries reits", () => {
  // was eight; the fourth private asset class is the ninth row
  render(<BookEntry world={WITH_REITS} />);
  expect(screen.getAllByRole("row", { name: /target/ })).toHaveLength(9);
  expect(screen.getByLabelText("infra target")).toBeInTheDocument();
});

it("renders a band row and a vintage ladder for infrastructure", () => {
  render(<BookEntry world={WITH_REITS} />);
  expect(screen.getByLabelText("infra band lo")).toBeInTheDocument();
  expect(screen.getAllByTestId("vintage-chart")).toHaveLength(4);
});

it("the infrastructure ladder carries fifteen rungs", () => {
  // one rung per year of contractual life (ER-12); pm_infra's life is 15 years
  render(<BookEntry world={WITH_REITS} />);
  expect(screen.getAllByTestId("rung-infra")).toHaveLength(15);
});
```

- [ ] **Step 3: run them** — Expected: FAIL on counts.

- [ ] **Step 4: implement** — the grid is data-driven; expect CSS column-count work in
      `app/src/styles.css` (`.policy-grid`) and the `:661` policy-grid assertion to move.

- [ ] **Step 5: run the tests** — `cd app && npx vitest run src/BookEntry.test.tsx` — PASS.

- [ ] **Step 6: commit**

```bash
git commit -m "feat(er14-04c): the opening book carries a fourth private asset class (15-rung ladder)"
```

---

### Task A3: the cockpit — fan charts, CIO dashboard, vintage charts

**Files:**
- Modify: `app/src/Play.tsx` (the peer-tab chart list),
  `app/src/components/CioDashboard.tsx`, `app/src/components/VintageChart.tsx`
- Test: `app/src/Play.cio.test.tsx:329-342` (the pinned eight-asset list),
  `app/src/components/CioDashboard.test.tsx:159`, `app/src/lib/cioView.test.ts:88-89`

**Interfaces:**
- Consumes: the server's `classIds` / `series` maps (already data-driven) and
  `world-bundle-0.6`'s `series_order`.

- [ ] **Step 1: re-pin the eight-asset list to nine**

```ts
it("renders all nine moved fan charts", () => {
  // was eight: ER-14's close-out adds infrastructure as the fourth private class
  // (D-ER14-2, 2026-08-18). The list is the ENGINE CONTRACT order.
  const expected = ["equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re", "infra"];
  const { container } = render(<Play {...playProps} />);
  for (const key of expected) {
    expect(container.querySelector(`figure.fan-chart[data-asset="${key}"]`)).not.toBeNull();
  }
  expect(container.querySelectorAll("figure.fan-chart")).toHaveLength(9);
});
```

This is a **re-pin, not a weakening**: the assertion still names every asset explicitly
and still fails if one goes missing. Record the reason and the date in the test body.

- [ ] **Step 2: run it** — Expected: FAIL (8 charts rendered) until the fixtures from
      Task S8 are picked up; if it still fails after that, the chart list is hardcoded —
      make it derive from `series_order`.

- [ ] **Step 3: implement** — private charts read `${key}_reported` (Play.tsx:97), which
      now includes `infra_reported`; the CIO private-cashflow selector reads the server's
      `classIds`, so infra appears without a client-side list.

- [ ] **Step 4: run the tests** — `cd app && npx vitest run` — PASS.

- [ ] **Step 5: commit**

```bash
git commit -m "feat(er14-04c): nine fan charts, infrastructure through the CIO dashboard and vintage charts"
```

---

### Task A4: WP `er14-04c` close-out

- [ ] **Step 1:** `cd app && npm run typecheck && npm run test && npm run build` — all clean.
- [ ] **Step 2:** live walk against the restarted 8787 service: pick a world, enter the
      book (four private rows, 15 infra rungs), play a window, open the CIO dashboard,
      confirm Infrastructure appears with a band and in the real-return goal bucket.
      Screenshot into the commit body.
- [ ] **Step 3:** `CHANGELOG.md`; reconcile the red ledger (the app entries clear here).
- [ ] **Step 4:** whole-WP adversarial review.
- [ ] **Step 5:** `git checkout er14-release && git merge --no-ff er14-04c-app`.

---

# WP `er14-05` — the release (branch `er14-05-release`)

**Scope:** the version stamps, the world fences, the retirement of the campaign worlds,
the mechanical golden re-pin sweep, the generated plane's v1.2 artifact with F5, the
single G3 reseal, the battery re-run and its disclosure, the console walk, and the
close-out documents. **Discharges AT-9, AT-10, AT-13.**

This is the WP that overruns. The ER-10 precedent — a strictly smaller change, one
function — still needed a dedicated re-pin task and still produced a red gate from a
missed consumer. Budget accordingly and do not skip Task R4's attribution rule.

---

### Task R1: the version stamps

**Files:**
- Modify: `src/ah/core/engine.py:56`, `src/ah/play.py:92`, `src/ah/port/adapter.py:108`
- Test: `tests/test_engine.py`, `tests/test_play.py`, `tests/test_gen_adapter.py`

**Interfaces:**
- Produces: `TOY_ENGINE_VERSION = "toy-v0.7"`, `PLAY_ALPHA_VERSION = "port-v5-inflation"`,
  `GEN_PLAY_ALPHA_VERSION = "port-v5-inflation-gen"`.

- [ ] **Step 1: write the failing tests**

```python
def test_the_engine_stamps_toy_v07():
    """A return-process change bumps the stamp: RunRecords carry it as
    resolved_engine.generator_version, so scores made under two engines can never
    share a leaderboard row (generator_id itself is a schemas/ enum and cannot
    gain values)."""
    assert TOY_ENGINE_VERSION == "toy-v0.7"


def test_both_play_alpha_stamps_moved_and_they_are_distinct():
    """Survey S3: a shared bump is never right - the two planes score different
    tapes."""
    assert PLAY_ALPHA_VERSION == "port-v5-inflation"
    assert GEN_PLAY_ALPHA_VERSION == "port-v5-inflation-gen"
    assert PLAY_ALPHA_VERSION != GEN_PLAY_ALPHA_VERSION


def test_the_research_alpha_definition_is_untouched():
    """decision_alpha_version names Step 5's RESEARCH definition and lives inside
    the G5 seal; bumping it would mean something different (ER-14's own
    consequences paragraph, verbatim)."""
    doc = yaml.safe_load(Path("step5-evaluation-protocol.yaml").read_text())
    assert doc["decision_alpha_version"] == "1.0"
```

- [ ] **Step 2: run them** — Expected: FAIL on the three literals (the fourth passes and
      stays as a guard).

- [ ] **Step 3: implement** the three constants, each with a one-line comment naming
      D-ER14-2 and the reason.

- [ ] **Step 4: run the tests** — PASS; the G5 lock digest is re-verified unchanged.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-05): toy-v0.7, port-v5-inflation, port-v5-inflation-gen; decision_alpha_version untouched"
```

---

### Task R2: the world fences

**Files:**
- Modify: `scripts/gen_presets.py:114-190` (the `51x` block comment and four ids),
  `scripts/gen_prehistory_preset.py` (`…515`), `src/ah/presets/*.json` (regenerated),
  `src/ah/presets/stagflation_1974.json` (`…603` → `…604`)
- Test: `tests/test_gen_adapter.py:392`, any test pinning a preset id

**Interfaces:**
- Produces: `…521` stagflation, `…522` goldilocks, `…523` deflation_bust,
  `…524` reflation_boom, `…525` prehistory, `…604` stagflation_1974.

- [ ] **Step 1: write the failing test**

```python
def test_the_toy_presets_moved_to_the_52x_block():
    """The 52x sub-block is toy-v0.7 (gen_presets.py's documented convention:
    50x = toy-v0.5, 51x = toy-v0.6). The engine is not part of a WorldSpec, so
    world identity is the only place the difference between two engines can live,
    and the leaderboard is keyed (world_id, seed, decision_alpha_version)."""
    ids = {p.stem: json.loads(p.read_text())["world_id"][-3:] for p in PRESETS.glob("*.json")}
    assert ids["stagflation"] == "521" and ids["goldilocks"] == "522"
    assert ids["deflation_bust"] == "523" and ids["reflation_boom"] == "524"
    assert ids["prehistory"] == "525" and ids["stagflation_1974"] == "604"
```

- [ ] **Step 2: run it** — Expected: FAIL.

- [ ] **Step 3: implement** — extend `gen_presets.py`'s block comment with the `52x`
      line (the file's own convention record), move the four ids, run
      `uv run python scripts/gen_presets.py` and `uv run python scripts/gen_prehistory_preset.py`,
      and hand-move `stagflation_1974`'s id.

- [ ] **Step 4: run the tests** — `uv run pytest tests/test_gen_adapter.py -q`; update
      the `:392` assertion to `…604` and its docstring history line (601→602→603→604).

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-05): world fences - the toy presets move to 52x, the played generated world to 604"
```

---

### Task R3: retiring the campaign and spine worlds

**Files:**
- Create/modify: `src/ah/cli.py` (a `RETIRED_WORLD_IDS` fence in `world_build`)
- Modify: `scripts/gen_presets.py` (the convention comment), `docs/engine-realism-register.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `ah.cli.RETIRED_WORLD_IDS: frozenset[str]` containing `…701` (`stress_1974`),
  `…703` (`stress_1990`), `…801` (`narration_1974`), `…802` (`spine_pilot`), and
  `ah world build --preset <retired>` exiting non-zero with an ASCII message.

**The mechanism is a plan decision — the design ratified the *outcome* (D-ER14-2:
"Campaign worlds 7xx/8xx RETIRED, not renumbered") but the repo has no retirement
machinery.** Chosen mechanism, with its reasoning:

- **Fence at world *build*, not in `ah/core/`.** Running a world requires building and
  storing it first, so the build boundary is sufficient, and `ah/core/engine.py` must not
  learn about product presets.
- **The JSONs stay in place, byte-unchanged.** They are records; `spine_pilot_report.py`
  and `spine02_report.py` cite their ids in prose, and those citations must keep
  resolving. Retirement means *never re-runnable under the new engine*, not *deleted*.
- **Before this task runs, confirm with the owner that no spine/stage2 run is in flight**
  (risk R-5). This is a coordination event.

- [ ] **Step 1: write the failing tests**

```python
def test_a_retired_world_cannot_be_built_under_the_new_engine():
    """D-ER14-2: the campaign and spine worlds are RETIRED, not renumbered. Their
    world_ids are records of what a campaign actually executed - gen_presets.py
    states the principle for the G0 world ('a record of what G0 actually ran, and
    must not be rewritten') - and adding infra changes the SHAPE of the tape, so a
    re-run would return nine return series where the recorded evidence describes
    eight. Retirement is the only option that keeps the record meaning what it
    says."""
    result = runner.invoke(app, ["world", "build", "--preset", "stress_1974"])
    assert result.exit_code != 0
    assert "retired" in result.output.lower()
    assert result.output.isascii()          # Windows console is cp1252


def test_the_retired_presets_are_still_readable_and_byte_unchanged():
    for stem in ("stress_1974", "stress_1990", "narration_1974", "spine_pilot"):
        doc = json.loads((PRESETS / f"{stem}.json").read_text(encoding="utf-8"))
        assert doc["world_id"] in RETIRED_WORLD_IDS
        # the record is untouched: the authored multiple drift is STILL -2.0 here
        assert doc["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] == -2.0
```

The second assertion is the machine-readable form of risk R-6's resolution: the live
presets are de-double-counted (Task M5), the retired records are not edited.

- [ ] **Step 2: run them** — Expected: FAIL (the build succeeds today).

- [ ] **Step 3: implement**

```python
# ER-14 close-out (D-ER14-2, 2026-08-18). These worlds' numbers - and, with the
# infrastructure sleeve, the SHAPE of their tapes - changed under toy-v0.7, but
# their ids are records of what a campaign actually executed. Renumbering would
# not reproduce those campaigns, only produce differently-shaped new ones under
# new ids; leaving them runnable would invite exactly the leaderboard collision
# the fences exist to prevent. So: readable forever, never re-runnable.
RETIRED_WORLD_IDS = frozenset({
    "00000000-0000-4000-9000-000000000701",   # stress_1974
    "00000000-0000-4000-9000-000000000703",   # stress_1990
    "00000000-0000-4000-9000-000000000801",   # narration_1974
    "00000000-0000-4000-9000-000000000802",   # spine_pilot
})
```
In `world_build`, after `raw` is loaded:
```python
    if raw.get("world_id") in RETIRED_WORLD_IDS:
        typer.echo(
            f"RETIRED: world {raw['world_id']} is a campaign record and cannot be "
            "rebuilt under toy-v0.7 (ER-14 close-out, D-ER14-2). Read it, do not run it.",
            err=True,
        )
        raise typer.Exit(1)
```
(ASCII only — no arrows, no em dashes in CLI output.)

- [ ] **Step 4: run the tests** — `uv run pytest tests/test_cli.py -q` — PASS.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-05): the 7xx/8xx campaign and spine worlds are retired - readable, never re-runnable"
```

---

### Task R4: the mechanical golden re-pin sweep

**Files:** every test named on the red ledger; `docs/superpowers/plans/er14-red-ledger.md`
(**deleted** in this commit)

**Interfaces:** none — this task changes expected values and pinned ids only.

**The attribution rule (design §7 item 10), applied to every single failure:**
(a) a **value golden** — re-pin, and record the old value in the test's docstring history
(the `test_engine.py:42-47` precedent, which already carries `toy-v0.3` → `v0.5` → `v0.6`);
(b) a **world-id pin** — update the id; (c) **anything else — STOP.**

- [ ] **Step 1: run the full suite to a log**

```bash
uv run python -m pytest -q > er14-repin-1.log 2>&1; echo "EXIT: $?" >> er14-repin-1.log
```
Read the log. Never pipe a checker through `tail` and never chain a decision onto it —
`echo EXIT` on a pipeline lies on short-circuit.

- [ ] **Step 2: attribute every failure**

Expected files, from the ER-10 precedent plus the inspected inventory:
`test_engine` (`GOLDEN_DIGEST` at `:48`), `test_digest`, `test_cli`, `test_bundle`,
`test_play`, `test_play_linkage`, `test_institution` (`GOLDEN_HOLD_FINAL` at `:48`),
`test_serve`, `test_serve_book`, `test_book`, `test_book_defaults`, `test_programme*`,
`test_credibility`, `test_cioview` (the `toy-v0.6` / `port-v4-ladder` literals at
`:102`, `:104`, `:260`, `:261`), `test_gen_adapter`, `test_inspect`, `test_feed`,
`test_annotations`, `test_sessions`, `test_tournament`, `test_buildconsole`,
`test_g0_end_to_end`, `test_narrative_blindness`, `test_live_mode`, `test_pacing_core`.

- [ ] **Step 3: re-pin, one test file per commit**

For each: update the expected value, and **extend the docstring history** with
`toy-v0.7 (ER-14 close-out, D-ER14-2, 2026-08-18): <old> -> <new>`. Never delete the
history; never relax an assertion to a tolerance to avoid re-pinning it.

- [ ] **Step 4: re-run until the failing set is empty**

```bash
uv run python -m pytest -q > er14-repin-N.log 2>&1; echo "EXIT: $?" >> er14-repin-N.log
```
Expected: `EXIT: 0`. Compare the pass count against the pre-release count and explain any
*decrease* (new tests should only add).

- [ ] **Step 5: delete the red ledger**

```bash
git rm docs/superpowers/plans/er14-red-ledger.md
```
Verify with `git status --short` in full (never `tail`): `git rm --cached` aborts
atomically on one bad pathspec, and a hidden stderr once shipped scratch logs to pushed
`main`.

- [ ] **Step 6: commit**

```bash
git commit -m "test(er14-05): the golden re-pin sweep - every value attributed, the red ledger closed"
```

---

### Task R5: rebuild the committed artifacts under the final engine

**Files:** `app/fixtures/toy.bundle.gz`, `app/fixtures/gen.bundle.gz`,
`app/fixtures/cio-sample.{reported,true,decided}.json`

- [ ] **Step 1:** `uv run python scripts/gen_bundle_fixtures.py` (the world ids moved in
      Task R2, so both bundles change again — this is the final rebuild).
- [ ] **Step 2:** `uv run python scripts/gen_cio_fixture.py`.
- [ ] **Step 3:** `uv run pytest tests/test_bundle.py tests/test_cioview.py -q` — PASS
      (including the byte-equality regeneration test).
- [ ] **Step 4:** `cd app && npm run test` — PASS.
- [ ] **Step 5:** verify the CLI round trip end to end:
      `uv run ah world build --preset stagflation && uv run ah run --paths 1000 && uv run ah replay`
      — `replay` must print **MATCH** (bit-identical).
- [ ] **Step 6: commit**

```bash
git commit -am "chore(er14-05): both bundles and the CIO fixtures rebuilt under toy-v0.7 / the 52x fence"
```

---

### Task G1: the v1.2 mapping artifact — C1 extended, F5 folded in, C2 decoupled

**Files:**
- Modify: `scripts/estimate_sleeve_mappings_v1_2.py`
- Create: `mappings/sleeve-mappings-v1.2.yaml`, `MAPPINGS-v1.2.md`
- Test: `tests/test_estimate_v12.py`

**Interfaces:**
- Consumes: `mappings/sleeve-mappings-v1.1.yaml` (read-only, never edited).
- Produces: `mappings/sleeve-mappings-v1.2.yaml` with `mapping_version: map-2026.08.3`,
  every PM row carrying `inflation_passthrough {b_infl, k_quarters, c_anchor, provenance}`
  and a restored `r2_train_val`; a `pm_residuals` block (`df: 5`, a PM block correlation);
  an updated `cta_rule` (EWMA half-life + position cap); **no `credit_loss` block**.
- Existing symbols to reuse, not re-implement: `lag_count`, `dimson_frame`,
  `fit_sum_beta`, `pm_constraints`, `cpi_trail`, `ig_spread_q`, `loss_series`,
  `reproduction_drift`, `check_reproduction`, `build_row`, `main`, and the constants
  `B_INFL`, `CPI_TRAIL_K`, `BETA_MATCH_TOL`, `LOSS_SLEEVES`.

- [ ] **Step 1: write the failing tests**

```python
def test_c1_now_covers_buyout():
    """A6, ratified: without the extension the generated path's private equity
    stays inflation-blind and ER-14 closes on one plane only. AM-2026-08-15-001
    scoped C1 to pm_infra and pm_re_value_add; PM_SLEEVE_FOR_ASSET maps the
    product's pe to pm_buyout."""
    assert set(B_INFL) == {"pm_infra", "pm_re_value_add", "pm_buyout"}
    assert B_INFL["pm_buyout"] == 0.35        # lambda_PE, the ratified toy value


def test_the_artifact_ships_without_the_cdli_blocked_credit_loss_block():
    """A7 / D-ER14-2: CDLI decoupled. C1 (+ the buyout extension and F5) adopts
    now; C2's measured half adopts when the Cliffwater export lands. The toy
    plane's convexity is a DECLARED engine constant (theta_toy = 0.10) and does
    not enter this sealed artifact."""
    doc = yaml.safe_load(OUT_PATH.read_text())
    assert all("credit_loss" not in row for row in doc["pm_sleeves"].values())
    assert doc["c2_status"] == "deferred: awaiting Cliffwater CDLI export (AM-... / D-ER14-2)"


def test_f5b_restores_r2_but_moves_no_coefficient():
    """F5b: record only. Adjusting a MEASURED beta toward a prior is precisely the
    tuning the seal exists to prevent. v1.1's loadings are carried verbatim; the
    estimator refuses (tol 1e-3) if the reproduced betas drift."""
    v11 = yaml.safe_load(Path("mappings/sleeve-mappings-v1.1.yaml").read_text())
    v12 = yaml.safe_load(OUT_PATH.read_text())
    for name, row in v11["pm_sleeves"].items():
        assert v12["pm_sleeves"][name]["loadings"] == row["loadings"]
    assert v12["pm_sleeves"]["pm_buyout"]["r2_train_val"] is not None


def test_f5c_declares_student_t_residuals_and_a_pm_block_correlation():
    """DN5 section 9 SM-8 seals 'Student-t, df ~ 5; block correlation within style
    family and within PM asset type'. adapter.py drew standard_normal, independent
    across sleeves - thin tails and no co-movement on the path players actually
    play. df = 5 per SM-8 (A9: a seal beats a convenience; the toy engine's 6.0
    is disclosed as a divergence)."""
    doc = yaml.safe_load(OUT_PATH.read_text())
    assert doc["pm_residuals"]["df"] == 5
    assert doc["pm_residuals"]["rescaled_to_unit_variance"] is True
    corr = doc["pm_residuals"]["block_correlation"]
    assert corr["pm_buyout"]["pm_buyout"] == 1.0


def test_f5a_declares_an_ewma_vol_and_a_position_cap():
    """The CTA rule realises 0.1595 annualised vol against a declared 0.10 target
    on the 1974 world: position size is per_inst_target / sigma with a trailing
    12-month sigma, so a vol jump leaves the denominator stale for up to a year."""
    rule = yaml.safe_load(OUT_PATH.read_text())["cta_rule"]
    assert rule["vol_estimator"] == "ewma" and rule["halflife_months"] > 0
    assert rule["position_cap"] > 0
```

- [ ] **Step 2: run them** — Expected: FAIL (`mappings/sleeve-mappings-v1.2.yaml` does
      not exist; `B_INFL` has two keys).

- [ ] **Step 3: implement the estimator changes**

- `B_INFL` gains `"pm_buyout": 0.35`, with `B_INFL_PROVENANCE` naming the new amendment.
- `--theta` becomes **optional**; when absent, the `credit_loss` block is omitted
  entirely and a top-level `c2_status` records why. **Do not** substitute the toy plane's
  `θ_toy = 0.10` into the sealed artifact: the toy value is declared for a different
  object (a monthly toy loss on the engine's own spread path).
- Add `pm_residuals` (df 5, `sqrt(df/(df-2))` rescaling so **no declared
  `residual_sigma_annual` changes** — the ER-7 precedent verbatim) and the PM block
  correlation, beside the existing HF-only `residual_correlation`.
- Author the `cta_rule` override (EWMA half-life + position cap) instead of copying
  v1.1's block verbatim.

- [ ] **Step 4: run the estimator**

Run: `uv run python scripts/estimate_sleeve_mappings_v1_2.py`
Expected: writes `mappings/sleeve-mappings-v1.2.yaml` and `MAPPINGS-v1.2.md`; the
reproduction check passes at `BETA_MATCH_TOL = 1e-3`. **If it refuses, STOP** — a
reproduction failure is a finding about v1.1, not an obstacle to route around.

- [ ] **Step 5: run the tests** — `uv run pytest tests/test_estimate_v12.py -q` — PASS.

- [ ] **Step 6: commit** (the artifact and the estimator in **one** commit — they join
      the seal scope together)

```bash
git add scripts/estimate_sleeve_mappings_v1_2.py mappings/sleeve-mappings-v1.2.yaml MAPPINGS-v1.2.md tests/test_estimate_v12.py
git commit -m "feat(er14-05): sleeve-mappings-v1.2 - C1 extended to pm_buyout, F5a/F5b/F5c, C2 deferred on CDLI"
```

---

### Task G2: the generated plane consumes the channel — AT-10

**Files:**
- Modify: `src/ah/port/adapter.py:121-215` (`_source_series`, the loading application,
  the residual draw), `src/ah/port/mapping.py::_cta_rule`
- Test: `tests/test_gen_adapter.py`, `tests/test_er14_inflation.py` (AT-10)

**Interfaces:**
- Consumes: `mappings/sleeve-mappings-v1.2.yaml` (Task G1),
  `ah.core.engine.inflation_excess` / `INFLATION_TRAIL_MONTHS` (Task M2 — `port → core`
  is the allowed direction).
- Produces: a `cpi_trail` regressor at K = 24 months derived **alongside** the existing
  12-month display series (`infl_pct` is left untouched so nothing display-facing moves
  for an unrelated reason).

- [ ] **Step 1: write the failing tests (AT-10)**

```python
GEN_WORLD = PRESETS / "stagflation_1974.json"


def gen_probe(infl_pct: float) -> EnsembleResult:
    """The same one-field probe, run through the generated path."""
    return run_gen_ensemble(_world(infl_pct, GEN_WORLD), 200, base_seed=SEED)


def _declared_b_infl(sleeve: str) -> float:
    art = yaml.safe_load(Path("mappings/sleeve-mappings-v1.2.yaml").read_text())
    return float(art["pm_sleeves"][sleeve]["inflation_passthrough"]["b_infl"])


def test_at10_the_generated_plane_is_no_longer_inflation_blind():
    """AT-10, the AT-1 half. Bit-identity across a twelvefold change must be dead
    on BOTH planes - otherwise ER-14 closes on one plane and stays open on the one
    that ships generated worlds."""
    lo, hi = gen_probe(1.0), gen_probe(12.0)
    for asset in ("pe", "pc", "re", "infra"):
        assert not np.array_equal(lo.returns[asset], hi.returns[asset]), asset


@pytest.mark.parametrize(
    "asset,sleeve,direction",
    [("pe", "pm_buyout", -1), ("re", "pm_re_value_add", +1), ("infra", "pm_infra", +1)],
)
def test_at10_generated_sign_and_materiality(asset, sleeve, direction):
    """AT-10, the AT-2/3 half. The SIGN rules transfer unchanged. The materiality
    floor is derived in-test from the artifact's OWN declared b_infl times the
    11pp probe range (x 0.5, the same 'range floor not central value' discipline
    the toy thresholds use), because the generated plane's units are the
    artifact's, not the toy engine's - a hardcoded toy threshold here would be
    testing a coincidence. If a derived floor cannot be met, STOP and report; do
    not lower it."""
    delta = annualised(gen_probe(12.0), asset) - annualised(gen_probe(1.0), asset)
    floor = 0.5 * _declared_b_infl(sleeve) * 11.0
    assert direction * delta >= floor, (asset, delta, floor)


def test_at10_generated_private_credit_still_takes_the_loss_bite():
    """AT-10, the AT-4 half: pc responds NEGATIVELY to inflation with rates held.
    On the generated plane the bite is the toy engine's omega_PC equivalent
    riding the shared tape, so this is a sign test only - C2's measured half is
    deferred on the CDLI export (D-ER14-2)."""
    delta = annualised(gen_probe(12.0), "pc") - annualised(gen_probe(1.0), "pc")
    assert delta < 0.0, delta
```

`run_gen_ensemble` is the generated-plane ensemble entry point in
`src/ah/port/adapter.py` — use whatever that module already exports (`run_gen_path` for a
single path); do not add a new entry point for the test.

- [ ] **Step 2: run them** — Expected: FAIL (`pe` bit-identical across inflation on the
      generated plane — ER-14 half-closed).

- [ ] **Step 3: implement**

- derive `cpi_trail` (K = 24 months) in `_source_series`, leaving `infl_pct` alone;
- apply each PM sleeve's `b_infl * (cpi_trail - c_anchor)` from the v1.2 artifact;
- replace `rng.standard_normal(...)` with standardized Student-t draws at the artifact's
  declared `df`, rescaled by `sqrt(df/(df-2))`, correlated by the declared PM block
  matrix (Cholesky), **keeping the column order `_PM_ASSET_ORDER`**;
- `mapping.py::_cta_rule` reads the EWMA half-life and the position cap from the artifact.

- [ ] **Step 4: run the tests and the F5a acceptance**

Run: `uv run pytest tests/test_gen_adapter.py tests/test_er14_inflation.py -q`
Then the F5a acceptance from design §5: realised annualised CTA vol within **±0.02 of the
0.10 target on all four presets**. Record the four numbers in the commit body.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-05): the generated plane feels inflation (C1 via v1.2), Student-t PM residuals, the CTA vol fix; AT-10"
```

---

### Task G3: the amendment entry and the single G3 reseal

**Files:**
- Modify: `governance/amendment-log.yaml` (append one entry), `pre-registration-g3.yaml`
  (`seal_scope.hashed_files`), `pre-registration-g3.lock` (minted)
- Test: `tests/test_g3seal.py`, `tests/test_prereg.py`, `tests/test_seal_guards.py`

**Interfaces:**
- Produces: amendment `AM-2026-08-18-001`, `type: protocol_change`, `post_hoc: true`,
  whose `payload` records: `extends: AM-2026-08-15-001`, the ratified coefficient table
  (all fifteen), `artifact: mappings/sleeve-mappings-v1.2.yaml`,
  `estimator: scripts/estimate_sleeve_mappings_v1_2.py`, `c2_deferred` with its reason,
  `f5: {a: cta EWMA + cap, b: r2 restored, no coefficient moved, c: Student-t df 5 + PM block}`,
  `superseded_lock_digest: sha256:45c80506…`, `seal_impact` naming G3 only.

- [ ] **Step 1: verify all three locks BEFORE the edit**

Run the three verify commands from Global Constraints. Record the three digests in the
commit body. (Memory rule: three locks share `factors.yaml`, `prereg.py`, `splits.py`;
unchecked edits have cost gates twice — AM-2026-08-08-001, AM-2026-08-09-004/-005.)

- [ ] **Step 2: append the amendment — BEFORE the seal, with the coefficients in it**

Use `ah.eval.prereg.append_amendment` (append-only; it validates the schema and rejects
duplicate ids). The rationale must state: the trigger (ER-14, filed 2026-08-16), the
ratification (D-ER14-2, 2026-08-18), why `post_hoc: true`, what keeps it honest (every
coefficient declared with its anchor and its `measured-external` upgrade path **before**
the estimator ran), and the C2 deferral with the CDLI dependency named.

- [ ] **Step 3: write the failing test**

```python
def test_the_er14_amendment_declares_every_ratified_coefficient():
    """Ratified coefficients are hashed into the entry BEFORE the estimator runs
    (design 7 item 14). An artifact whose numbers were not declared first is
    indistinguishable from a tuned one."""
    entry = {a.amendment_id: a for a in load_amendments(LOG)}["AM-2026-08-18-001"]
    declared = entry.payload["ratified_coefficients"]
    assert declared["lambda_RE"] == 0.30 and declared["lambda_INFRA_default"] == 0.60
    assert len(declared) == 15
    assert entry.payload["extends"] == "AM-2026-08-15-001"
```

- [ ] **Step 4: add the pair to the seal scope and mint**

Add to `pre-registration-g3.yaml`'s `seal_scope.hashed_files`, immediately after the v1.1
pair (lines 182-183), with a comment naming `AM-2026-08-18-001` and the planned-arrival
pattern:
```yaml
    - scripts/estimate_sleeve_mappings_v1_2.py
    - mappings/sleeve-mappings-v1.2.yaml
```
Then:
```bash
uv run python -c "from ah.eval.g3seal import seal_g3, verify_g3; print(seal_g3(sealed_at='2026-08-18')); print(verify_g3())"
```

- [ ] **Step 5: verify all three locks AFTER**

Re-run the three verify commands. **`pre-registration.lock` and `pre-registration-g5.lock`
digests must be UNCHANGED** — if either moved, something sealed was touched: **STOP**.
G3's digest moves by design; record old → new in the commit body and in the amendment's
`superseded_lock_digest`.

- [ ] **Step 6: run the seal suites**

Run: `uv run pytest tests/test_g3seal.py tests/test_prereg.py tests/test_seal_guards.py -q`
Expected: PASS, including `test_every_seal_scope_entry_exists` and the boundary guards.

- [ ] **Step 7: commit**

```bash
git commit -am "SEAL(er14-05): AM-2026-08-18-001 extends C1 to pm_buyout; the v1.2 pair joins the G3 lock (one reseal, F5 batched)"
```

---

### Task B1: the battery re-runs, and what moves is disclosed

**Files:** `docs/superpowers/specs/2026-08-18-er14-battery-disclosure.md` (new record),
`CHANGELOG.md`

**AT-9, verbatim from the design:** *"The validation battery re-runs on the stagflation
preset; every stylized fact that moves outside its band is **disclosed in the close-out**,
and **no threshold is moved to accommodate it**."* This is not pass/fail — it is the rule
that governs what happens when the battery moves, which it will.

- [ ] **Step 1: capture the before**

Check out `main` into a scratch worktree and run
`uv run python -m ah.battery.report > battery-before.txt` there. (`src/ah/battery/*` is
inside the **main** lock — it is *run*, never *edited*.)

- [ ] **Step 2: run the after**

Run: `uv run python -m ah.battery.report > battery-after.txt`

- [ ] **Step 3: write the disclosure**

A table: every stylized fact, before, after, its band, and whether it moved outside. For each
that did: what mechanism moved it and why that is expected (or not). **If the temptation
to edit `src/ah/battery/thresholds.yaml` arises — STOP.** The ER-4 discipline: flags are
never silenced by moving the flag.

- [ ] **Step 4: chase `band_outside=True` in the sealed JSON**, not evidence-doc prose
      (the sealed-bands memory rule) — read the battery's own output document.

- [ ] **Step 5: commit**

```bash
git commit -am "docs(er14-05): the battery re-run and its disclosure - what moved, and no band moved to meet it"
```

---

### Task B2: the close-out measurements and the console walk

**Files:**
- Create: `scripts/measure_er14_response.py`, `artifacts/er14/response.json`
- Test: `tests/test_er14_inflation.py` (AT-13 reads the measurement)

**Interfaces:**
- Produces: `measure_er14_response.py::main()` writing
  `{"probe": {...}, "by_asset": {asset: {"1pct":…, "12pct":…, "delta":…}}, "at13": {...}}`
  — deterministic, no network, ASCII stdout.

- [ ] **Step 1: implement the measurement script**

Re-use ER-14's own probe verbatim (`docs/current/private-markets-and-inflation.md` §7)
so the close-out's "after" table sits column-for-column against the register's "before"
table, and add the world-basis pair (`stagflation_1974` vs `goldilocks`) — the design's
§4 is honest only as a pair.

- [ ] **Step 2: AT-13 — the escalator asymmetry, measured not argued**

```python
def test_at13_the_symmetric_escalators_deflation_cost_is_recorded():
    """AT-13, a DISCLOSURE with no threshold. C1 explicitly defers escalator caps
    and floors ('documented asymmetry, deferred'), so this design inherits a
    SYMMETRIC escalator and overstates infrastructure's deflation downside -
    possibly by the whole -1.8 pp/yr. The size goes in the close-out entry as a
    number, so the deferred item carries its own cost estimate."""
    doc = json.loads(Path("artifacts/er14/response.json").read_text())
    assert "at13" in doc and "floored_variant_delta_pp" in doc["at13"]
```
The floored variant is computed **inside the script** by patching
`ah.core.engine.inflation_excess` with a clipped wrapper (`np.maximum(x, 0.0)` below the
anchor) — a measurement affordance, **not** a production flag. No shipped code gains a
switch for it.

- [ ] **Step 3: run it** — `uv run python scripts/measure_er14_response.py`; read the
      JSON; sanity-check the four private assets against design §4's predicted table
      (RE ≈ +3.3, PE ≈ −1.1, PC ≈ −0.8, infra ≈ +6.6 pp/yr on the probe basis).
      **A number materially off its prediction is a finding — reconcile before writing
      the close-out.**

- [ ] **Step 4: the credibility console walk**

```bash
uv run ah credibility --preset stagflation --preset goldilocks --preset deflation_bust --out credibility-er14.html
```
Walk it. The console has twice caught adapter defect classes the unit suite missed
(memory rule: console walk before merge). Record what you looked at and what you found.

- [ ] **Step 5: commit**

```bash
git commit -am "feat(er14-05): the close-out measurements (AT-13 included) and the credibility walk"
```

---

### Task D1: close the register entry and the documents

**Files:** `docs/engine-realism-register.md` (ER-14 → **CLOSED**), `CLAUDE.md` (the
register line), `CHANGELOG.md`, `docs/current/private-markets-and-inflation.md` (re-headed),
`governance/decision-register.md` (a close-out note under D-ER14-2)

- [ ] **Step 1: close ER-14** with, at minimum:
  - the post-fix measurement table from `artifacts/er14/response.json` beside the
    original one, so the inversion is visible;
  - **the named residuals**, each stated rather than implied:
    - *the propensity to distribute stays inflation-blind* — inflation changes the
      **level** of distributions through NAV, never the **propensity**; two worlds with
      identical drawdown and spreads have the same `f_dist` (§3, ratified);
    - *it is a response, not a hedge* — at 6.5% inflation, +1.35 pp/yr of escalated
      property income and +2.7 pp/yr on infrastructure are both still large **real**
      losses;
    - *the escalator is symmetric and real ones usually are not* — with AT-13's measured
      overstatement as a number; the fix belongs to C1's deferred item;
    - *the played infrastructure sleeve is closed-end* — `infra_core` stays Tier B and
      unparameterized because `ClosedEndCohort` is closed-end by construction; **no
      register row is reclassified**;
    - *the shadow-rate approximation* in φ_PC, with §2.4's declined alternative;
    - *`structural.infrastructure` has no income-yield field*, so `infra_yield` is a
      hardcoded constant — a **contract** limitation, recorded in the unconsumed/
      unavailable-field map;
    - *ER-11 still governs the reported plane* — the inflation response reaches players
      through the engine's own filter, whose inverse property does not hold;
    - *the standing caveat is unchanged* — `hier-flow-v1` is not a convincing model of
      history; closing ER-14 removes one missing channel and makes nothing decision-ready.
  - the retirement of the 7xx/8xx worlds and the ER-15 session demotion, both announced.
- [ ] **Step 2: update `CLAUDE.md`** — move ER-14 from the open list to the closed list
      with a one-line summary and the date, in the register paragraph's existing style.
- [ ] **Step 3: re-head `docs/current/private-markets-and-inflation.md`** with the
      post-fix measurements; keep the pre-fix numbers in place as the record (the
      document is the supporting detail for a now-closed finding — say so in the banner).
- [ ] **Step 4: `CHANGELOG.md`** — the release entry, one line per WP.
- [ ] **Step 5: `governance/decision-register.md`** — a short close-out note under
      D-ER14-2: what shipped, the two deviations (R-6's preset scope; AT-14 scoped to the
      toy plane per Task S4's finding), and the residuals list by reference.
- [ ] **Step 6: commit**

```bash
git commit -am "docs(er14-05): ER-14 CLOSED - the inverted defect, the named residuals, the retirements"
```

---

### Task D2: the gate and the merge

- [ ] **Step 1: lint everything first** (lint-before-the-long-gate):
      `uv run ruff check . --fix && uv run ruff format . && uv run pyright`, then
      `cd app && npm run typecheck && npm run test && npm run build`.
- [ ] **Step 2: verify all three lock digests** one final time; only G3's has moved.
- [ ] **Step 3: merge the WP branch into the integration branch**
      (`git checkout er14-release && git merge --no-ff er14-05-release`).
- [ ] **Step 4: run the gate in the background, on `er14-release`**

```bash
uv run python scripts/run_gate.py gate-er14.log
```
Never invoke bare pytest for a gate: `run_gate.py` binds the log to the sha it tested and
refuses to start on a dirty tree. Read the `EXIT:` line and the pass count **from the
log** — never chain a merge onto a `tail`.

- [ ] **Step 5: stamp and re-verify**

```bash
uv run python scripts/check_gate.py gate-er14.log
git rev-parse HEAD            # must equal the first line of .gate-ok
```
The owner commits onto branches mid-gate; the stamp binds exactly one commit.

- [ ] **Step 6: merge into `main` and push**

```bash
git checkout main && git merge --no-ff er14-release
git push                      # standing authorization; NEVER force-push
```
The commit body states: what shipped, the deviations (R-6, AT-14's plane scope, the
`smooth_infra` default), and what the next reader must know (ER-15 demotion, retired
worlds, the C2/CDLI residual).

- [ ] **Step 7: restart the session service from the merged tree**

`Get-NetTCPConnection -LocalPort 8787` → `Stop-Process`, then
`uv run uvicorn ah.serve:app --port 8787`. (`pkill` does not work on Windows, and a
stale listener silently serves the old contract — the exact trap `app-open-02` opened with.)

---

## Self-review record (writing-plans discipline)

**1. Spec coverage.** Walked design §0–§10 and D-ER14-2 clause by clause:

| Spec item | Task |
|---|---|
| §2.0 shared state, K, anchor, warm-up, units | M2 |
| §2.1 real estate (λ_RE, γ_RE, D_RE) | M3 |
| §2.1 rider R1 | M4 |
| §2.2 private equity (λ_PE, μ_PE), the double-count | M5 |
| §2.3 private credit (φ_PC, ω_PC, θ_toy), rider R2 | C1, C2, C3, C4 |
| §2.4 declined policy reaction function | recorded in C1's comment + D1's residuals |
| §2.5 generated plane (cpi_trail, C1→pm_buyout, K=24 series, C2 decoupled) | G1, G2 |
| §2.6 infrastructure mechanism (λ/γ/β/σ/yield/crisis) | M6 |
| §2.7.0 schemas check | S1 step 7 |
| §2.7.1 layer-by-layer sleeve scope | S1–S8 |
| §2.7.2 the corruption risk | R-1, S1 (AT-14 verbatim + break-and-revert) |
| §2.7.3 the starting weight and carve | S2, S4 |
| §2.7.4 pacing, the evergreen problem | S5 |
| §2.7.5 `pm_infra` not `infra_core` | S4, D1's residuals |
| §3 Delta 3 / no cashflow amendment | Global Constraints, D1 |
| §4 the 1970s table | B2 (measured against it) |
| §5 F5a/F5b/F5c | G1, G2 |
| §6 AT-1…AT-14 | M1(6b), M3(1,3,8,6a), M5(2), C1(5), C2(4), C5(6a), S1(7,11,12,14), G2(10), B1(9), B2(13) |
| §7 release checklist items 1–21 | R1–R5, G1–G3, B1–B2, D1–D2 |
| §8 sequencing | the five WPs |
| §9 asks A1–A16 | ratified values in the header table; each ask's outcome carried by the task that implements it |
| §10 what closing ER-14 does not buy | D1 step 1 |

No spec requirement is without a task.

**2. Placeholder scan.** No "TBD", "implement later", "add error handling", "similar to
Task N", or "write tests for the above". Every code step carries real code; every test
step carries real assertions. Two places deliberately carry a **STOP and decide** rather
than an answer, because the design itself makes them conditional on inspection: the
bundle decoder's count pin (S8 step 1) and a legacy three-sleeve plan's 422-vs-demote
behaviour (S6 step 1) — each states the recommended answer and what evidence settles it.

**3. Type consistency.** Cross-checked every symbol used across task boundaries:
`inflation_excess` (M2 → M3, M5, M6, C1, C2, G2), `infra_return`'s keyword-only signature
(M6 → S1), `ASSETS`/`REPORTED_SLEEVES` (S1 → S3, S4, S8), `PRIVATE_ASSETS` **and**
`PRIVATE_SLEEVES` (S2 → S6, S7), `SECONDARY_SLEEVE` (S2), `PM_SLEEVE_FOR_ASSET` (S4 → G2),
`BUNDLE_VERSION` (S8 → A3), the three version stamps (R1 → R4's re-pins), and the v1.2
artifact keys `inflation_passthrough` / `pm_residuals` / `cta_rule` / `c2_status`
(G1 → G2's consumers). Names are identical at every use site.

