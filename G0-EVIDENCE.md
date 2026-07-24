# G0-EVIDENCE.md — Gate G0 evidence

Step 0 ("lay the rails") of the Alternate Histories Platform. This document records,
for each of the seven Gate G0 criteria (STEP0-PLAN.md §0), the command executed, the
observed result, and pass/fail. It is the platform's first entry in its validation
record. Environment: Python 3.12.10, uv 0.11.x, Windows (CI: Ubuntu). All tests run
with no network (pytest-socket `--disable-socket`).

**Summary: 7 / 7 criteria PASS.**

---

### G0.1 — The loop completes; replay is bit-identical

**Command**
```
ah world build --preset stagflation
ah world validate
ah run --paths 100
ah replay
```
**Observed**
- `build` → world `00000000-0000-4000-9000-000000000001`
- `validate` → `clamps=0 warnings=[] blocking=[]`
- `run` → a run_id; `replay` prints identical `stored` and `replay` digests → `MATCH`
- Determinism: two runs at the same seed/paths yield the same `outputs_digest`
  (`tests/test_g0_end_to_end.py::test_g0_1_...`, `tests/test_cli.py::test_run_two_runs_same_digest`).

**Result: PASS**

---

### G0.2 — Schema + V-rule validation on every world; clamps/warnings in provenance

**Command**
```
uv run pytest tests/test_g0_end_to_end.py -k g0_2 -v
uv run pytest tests/test_validator.py tests/test_worldspec.py
```
**Observed** — `world build` stamps `provenance.validation` (validator_version `1.0.0`,
`clamps`, `warnings`) and flips status to `validated`; a clamp fixture records clamps
via the validator (V9). Loader runs JSON Schema (Draft 2020-12) first, then pydantic;
the two agree on 400 fuzzed documents.

**Result: PASS**

---

### G0.3 — RunRecords store resolved engine, seed, SHA-256 digest; tamper detected

**Command**
```
uv run pytest tests/test_g0_end_to_end.py -k g0_3 -v
uv run pytest tests/test_stores.py -k tamper
```
**Observed** — RunRecord carries `resolved_engine` (generator_version, validator_version
`1.0.0`, battery_version `battery-0.1`), `seed`, and `outputs_digest` (`sha256:…`).
`verify_run` returns `True` for an intact record and `False` after the stored digest
(or the stored world) is mutated.

**Result: PASS**

---

### G0.4 — Chronicle is append-only (update/delete raise)

**Command**
```
uv run pytest tests/test_g0_end_to_end.py -k g0_4 -v
uv run pytest tests/test_stores.py -k chronicle
```
**Observed** — a raw `UPDATE`/`DELETE` on `chronicle` raises `sqlite3.Error` (trigger),
and the repository module exposes no mutator functions. Both layers covered.

**Result: PASS**

---

### G0.5 — Offline compiler harness: 50 fixtures, schema-valid, bounds-clamped

**Command**
```
uv run pytest tests/test_compiler.py
uv run pytest tests/test_g0_end_to_end.py -k g0_5 -v
```
**Observed** — 50 fixtures (40 valid, 5 clamp, 5 reject). Valid + clamp worlds compile,
validate, build, and run ≥ 12 months with finite output; clamp worlds record clamps;
reject worlds are rejected. No network (FixtureCompiler only; the live adapter is not
imported).

**Result: PASS**

---

### G0.6 — Validation-battery skeleton computes the panel and evaluates thresholds

**Command**
```
uv run python -m ah.battery.report      # CI job, stagflation preset
ah battery                              # on a stored run
```
**Observed** — battery `battery-0.1` prints the stylized-fact panel
(excess kurtosis, skew, Hill tail index, ACF r / |r|, max-drawdown median, corr
distance) with `enforce failures: 0` and exit code 0. Thresholds are all `todo`
(non-blocking) per the plan; the enforce path is exercised in tests.

**Result: PASS**

---

### G0.7 — Lint, type-check, tests ≥ 90% coverage on core/, and the G0 e2e test — all green

**Command**
```
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --cov=ah.core --cov-fail-under=90
uv run pytest tests/test_g0_end_to_end.py
```
**Observed**
- ruff: `All checks passed!`
- ruff format: `50 files already formatted`
- pyright: `0 errors, 0 warnings, 0 informations`
- pytest: `186 passed`; coverage on `ah.core` = **96.54%** (gate ≥ 90)
- G0 end-to-end: `7 passed`

**Result: PASS**

---

*All seven criteria pass. Tagging `v0.1.0-g0`.*
