# Compiler Prompt v2 + Envelope Stamping (WP-A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live scenario compiles succeed: the model supplies the six substantive WorldSpec blocks, the system stamps the envelope, and the prompt derives its field contract from the vendored schema so it cannot drift again.

**Architecture:** Three moves. (1) `stamp_envelope` in `postprocess.py` (from the 2026-08-06 stash, rebased onto WP-B's `fetch_raw_text` refactor) supplies the five system-owned envelope keys and drops model-invented ones. (2) A new `prompt_v2.py` builds its system prompt from `schemas/worldspec-v1.2.schema.json` at import time — required fields, enums, bounds — plus the vendored example's six blocks as a canonical few-shot. (3) The build console's ledger gains an `envelope` stage between `extract` and `validate`, so live iterations are watched in the browser.

**Tech Stack:** stdlib json only; no new dependencies. Live calls stay lazy and test-free.

## Global Constraints

- Branch `compiler-prompt-v2` cut from `main` **after WP-B merges** (it consumes `fetch_raw_text` and edits `buildconsole.run_stages`).
- Diagnosis this plan answers (2026-08-06, live `claude-sonnet-4-6`): output carried `meta` + `schema_version`, omitted all of `world_id`/`provenance`/`status`/`spec_version`/`extensions` → every live build failed at pydantic construction; all 50 offline fixtures pass because they predate the envelope change.
- Schema contract (verified): v1.2 top level requires `spec_version, world_id, status, provenance, narrative, horizon, regimes, factor_conditions, structural, engine_defaults`; `additionalProperties: false`. Model owns the last six; system owns the rest plus optional `extensions`.
- `schemas/` is read-only vendored truth — the prompt READS it, never edits it. `ah/core/loader.py:24` pins `worldspec-v1.2.schema.json`.
- No file in `pre-registration.lock` is touched. No network in tests; the live acceptance run is a manual step via the console.
- `prompt_v1.py` stays untouched (it is named in RunRecord provenance history); v2 is a new module and the adapter switches to it.
- Keep the stash's no-clock-reads discipline: `created_at` is always a caller argument.
- Done = tests+gate green, ruff/pyright clean, CHANGELOG updated, commit bodies per convention. Restore the stash with `git stash pop` only on the WP-A branch; if it conflicts with WP-B's adapter, take the plan's Task 1 code below as the resolution (it IS the merged result).

---

### Task 1: `stamp_envelope` in postprocess (rebased stash) + adapter/CLI wiring

**Files:**
- Modify: `src/ah/compiler/postprocess.py`, `src/ah/compiler/anthropic_adapter.py`, `src/ah/cli.py:116-121`
- Test: `tests/test_compiler.py` (append)

**Interfaces:**
- Produces: `stamp_envelope(obj, *, scenario_text, created_at, compiler_model, prompt_version, world_id=None) -> dict` (pure, non-mutating); `SPEC_VERSION = "1.2.0"`; `_SYSTEM_OWNED`; `_MODEL_INVENTED`; `AnthropicCompiler.compile(scenario_text, *, created_at="1970-01-01T00:00:00Z")`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_compiler.py`)

```python
def test_stamp_envelope_supplies_system_owned_keys():
    from ah.compiler.postprocess import SPEC_VERSION, stamp_envelope

    body = {"narrative": {}, "horizon": {}, "meta": {"x": 1}, "schema_version": "9.9"}
    out = stamp_envelope(
        body,
        scenario_text="a scenario",
        created_at="2026-08-06T00:00:00+00:00",
        compiler_model="claude-sonnet-4-6",
        prompt_version="compile-world-v2.0",
    )
    assert out["spec_version"] == SPEC_VERSION
    assert out["status"] == "draft"
    assert out["extensions"] == {}
    assert out["provenance"]["source"]["compiler_prompt_version"] == "compile-world-v2.0"
    assert out["provenance"]["created_at"] == "2026-08-06T00:00:00+00:00"
    assert "meta" not in out and "schema_version" not in out  # model-invented dropped
    assert "world_id" in out
    assert "meta" in body  # input not mutated


def test_stamp_envelope_world_id_override_is_deterministic():
    from ah.compiler.postprocess import stamp_envelope

    out = stamp_envelope(
        {},
        scenario_text="s",
        created_at="t",
        compiler_model="m",
        prompt_version="p",
        world_id="00000000-0000-4000-8000-00000000abcd",
    )
    assert out["world_id"] == "00000000-0000-4000-8000-00000000abcd"
```

- [ ] **Step 2: Run to verify fail** — `uv run pytest tests/test_compiler.py -q` → ImportError on `stamp_envelope`.

- [ ] **Step 3: Implement.** In `postprocess.py`, add exactly the stash's content (constants + `stamp_envelope`; the stash diff is reproduced in the repo stash `compiler envelope stamp (postprocess) - not part of ER-7` and in this plan's authoring conversation). In `anthropic_adapter.py`, `compile` becomes:

```python
    def compile(
        self, scenario_text: str, *, created_at: str = "1970-01-01T00:00:00Z"
    ) -> dict[str, Any]:  # pragma: no cover - live only
        """Compile a scenario, then stamp the envelope the system owns.

        ``created_at`` is a caller argument, never a clock read. The CLI passes
        the same timestamp it stamps validation with.
        """
        return stamp_envelope(
            extract_json(fetch_raw_text(self.model, scenario_text)),
            scenario_text=scenario_text,
            created_at=created_at,
            compiler_model=self.model,
            prompt_version=self.prompt_version,
        )
```

In `cli.py` `world_build`, hoist `now = _now()` above the compile branch and pass `created_at=now` to `AnthropicCompiler().compile(...)`; reuse the same `now` for `stamp_validation`/`save_world` below (do not call `_now()` twice).

- [ ] **Step 4: Run tests, verify pass; lint** — `uv run pytest tests/test_compiler.py tests/test_cli.py -q && uv run ruff check . && uv run ruff format --check . && uv run pyright src/ah/compiler`
- [ ] **Step 5: Commit** — `git commit -am "feat(compiler): system-owned envelope stamping (WP-A task 1)"`

---

### Task 2: `prompt_v2.py` — schema-derived field contract

**Files:**
- Create: `src/ah/compiler/prompt_v2.py`
- Test: `tests/test_compiler.py` (append)

**Interfaces:**
- Produces: `PROMPT_VERSION = "compile-world-v2.0"`; `MODEL_OWNED = ("narrative", "horizon", "regimes", "factor_conditions", "structural", "engine_defaults")`; `schema_digest() -> str` (pure); `SYSTEM_PROMPT: str`; `build_messages(scenario_text) -> list[dict[str, str]]` (same shape as v1's).

- [ ] **Step 1: Write the failing tests**

```python
def test_prompt_v2_names_every_model_owned_required_field():
    import json
    from pathlib import Path

    from ah.compiler.prompt_v2 import MODEL_OWNED, SYSTEM_PROMPT

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "worldspec-v1.2.schema.json")
        .read_text(encoding="utf-8")
    )
    for block in MODEL_OWNED:
        assert block in SYSTEM_PROMPT
        sub = schema["properties"][block]
        for req in sub.get("required", []):
            assert req in SYSTEM_PROMPT, f"{block}.{req} missing from prompt"


def test_prompt_v2_never_asks_for_system_owned_keys():
    from ah.compiler.postprocess import _SYSTEM_OWNED
    from ah.compiler.prompt_v2 import SYSTEM_PROMPT

    ask = SYSTEM_PROMPT[SYSTEM_PROMPT.index("Output a JSON object") :]
    for key in _SYSTEM_OWNED:
        assert key not in ask, f"prompt asks the model for system-owned {key}"


def test_prompt_v2_embeds_the_vendored_example_blocks():
    from ah.compiler.prompt_v2 import SYSTEM_PROMPT

    # the canonical example's title proves the few-shot rode along
    assert "stagflation" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement**

```python
"""Compiler prompt library v2: the field contract is DERIVED from the vendored
schema at import time, so prompt and ``schemas/`` cannot drift apart (v1 drifted:
it was a hand-written field list against a superseded schema generation).

Pure strings + builders — no network, safe to import in tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPT_VERSION = "compile-world-v2.0"

MODEL_OWNED = ("narrative", "horizon", "regimes", "factor_conditions", "structural", "engine_defaults")

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "worldspec-v1.2.schema.json"
_EXAMPLE_PATH = _SCHEMA_PATH.parent / "example-long-stagflation.worldspec.json"


def _field_line(name: str, spec: dict[str, Any], required: bool) -> str:
    bits = [spec.get("type", "object")]
    if "enum" in spec:
        bits.append("one of " + ", ".join(map(str, spec["enum"])))
    if "minimum" in spec or "maximum" in spec:
        bits.append(f"range [{spec.get('minimum', '-inf')}, {spec.get('maximum', 'inf')}]")
    if "minItems" in spec or "maxItems" in spec:
        bits.append(f"items {spec.get('minItems', 0)}..{spec.get('maxItems', 'n')}")
    flag = "REQUIRED" if required else "optional"
    return f"  - {name} ({flag}: {'; '.join(bits)})"


def schema_digest() -> str:
    """A compact, deterministic text rendering of the six model-owned blocks."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    lines: list[str] = []
    for block in MODEL_OWNED:
        spec = schema["properties"][block]
        req = set(spec.get("required", []))
        lines.append(f"{block}:")
        for fname, fspec in sorted(spec.get("properties", {}).items()):
            lines.append(_field_line(fname, fspec, fname in req))
    return "\n".join(lines)


def _example_blocks() -> str:
    doc = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    return json.dumps({k: doc[k] for k in MODEL_OWNED if k in doc}, indent=1)


SYSTEM_PROMPT = f"""\
You compile a user's counterfactual macro/market scenario into WorldSpec JSON
(schema {json.loads(_SCHEMA_PATH.read_text(encoding='utf-8')).get('$id', 'worldspec-v1.2')}).

Output a JSON object with EXACTLY these six top-level keys and no others:
{", ".join(MODEL_OWNED)}. The platform stamps identity and provenance itself;
do not output any other top-level key.

Rules:
- Output JSON ONLY. No prose, no Markdown, no code fences.
- The engine reads only the structured parameters; narrative must agree with them.
- Set only the factor_conditions the scenario implies; omit the rest.
- FICTIONAL ENTITIES ONLY: never name a real firm, fund, or person.
- Keep every value inside the bounds below; do not rely on downstream clamping.

Field contract (derived from the vendored schema):
{schema_digest()}

Canonical example (the six blocks of the vendored long-stagflation world):
{_example_blocks()}
"""


def build_messages(scenario_text: str) -> list[dict[str, str]]:
    """Return the messages payload for the Messages API (user turn only)."""
    return [
        {
            "role": "user",
            "content": f"Compile this scenario into the six-block JSON document:\n\n{scenario_text}",
        }
    ]
```

Check token size: print `len(SYSTEM_PROMPT)` once; if the example pushes it past ~20k chars, trim `narrative.dispatches` in `_example_blocks` to the first 3 entries (deterministically) and say so in the prompt.

- [ ] **Step 4: Run tests, verify pass; lint.**
- [ ] **Step 5: Switch the adapter**: in `anthropic_adapter.py` replace the `prompt_v1` import with `from ah.compiler.prompt_v2 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages`. Run the FULL offline fixture regression: `uv run pytest tests/test_compiler.py tests/test_cli.py -q` (fixtures don't touch the live prompt, so all 50 must still pass).
- [ ] **Step 6: Commit** — `git commit -am "feat(compiler): schema-derived prompt v2 (WP-A task 2)"`

---

### Task 3: The console's `envelope` stage

**Files:**
- Modify: `src/ah/buildconsole.py` (`run_stages`, the live fetch already exists)
- Test: `tests/test_buildconsole.py` (append)

**Interfaces:**
- Consumes: `stamp_envelope` (Task 1). `run_stages` gains keyword `stamp_live_envelope: bool` derived from `att.live` at the call site — no signature change elsewhere.

- [ ] **Step 1: Write the failing tests**

```python
def test_live_attempt_gets_envelope_stage(tmp_path):
    """Simulated live: fetch returns a six-block body with model-invented keys;
    the envelope stage must stamp identity before validation."""
    body = {k: v for k, v in _good_doc().items()
            if k in ("narrative", "horizon", "regimes", "factor_conditions",
                     "structural", "engine_defaults")}
    body["meta"] = {"model": "invented"}
    att = Attempt(attempt_id="a9", scenario_text="x", live=True,
                  created_at="2026-08-06T00:00:00+00:00", stages=[])
    run_stages(att, fetch_text=lambda s: json.dumps(body))
    names = [s.name for s in att.stages]
    assert names == ["prompt", "model", "extract", "envelope", "validate", "stamp"]
    assert att.stamped is not None
    assert att.stamped["provenance"]["source"]["kind"] == "compiler"


def test_fixture_attempt_envelope_stage_is_carried(tmp_path):
    att = Attempt(attempt_id="a10", scenario_text="x", live=False,
                  created_at="2026-08-06T00:00:00+00:00", stages=[])
    run_stages(att, fetch_text=lambda s: json.dumps(_good_doc()))
    env = next(s for s in att.stages if s.name == "envelope")
    assert env.status == "ok" and "fixture" in env.detail
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.** In `run_stages`, after the `extract` stage and before `validate`:

```python
        s = _stage(att, "envelope", "")
        if att.live:
            raw = stamp_envelope(
                raw,
                scenario_text=att.scenario_text,
                created_at=att.created_at,
                compiler_model=COMPILER_MODEL,
                prompt_version=PROMPT_VERSION,
            )
            s.detail = f"stamped world_id {raw['world_id']} (system-owned envelope)"
        else:
            s.detail = "fixture carries its own envelope — carried through"
        s.status = "ok"
```

Import `stamp_envelope` from `ah.compiler.postprocess` at module top (pure, test-safe) and `COMPILER_MODEL` likewise; switch the buildconsole `PROMPT_VERSION`/`SYSTEM_PROMPT`/`build_messages` imports from `prompt_v1` to `prompt_v2` so the prompt stage reports v2 truthfully.
- [ ] **Step 4: Run `uv run pytest tests/test_buildconsole.py -q`, verify pass; lint.**
- [ ] **Step 5: Commit** — `git commit -am "feat(buildconsole): envelope stage between extract and validate (WP-A task 3)"`

---

### Task 4: Live acceptance through the console, docs, gate, merge

- [ ] **Step 1: Live iteration loop (manual, needs `ANTHROPIC_API_KEY`).** `uv run uvicorn ah.buildconsole:app --port 8798`; compile a throwaway scenario with the live checkbox. Iterate on prompt_v2 wording ONLY if a stage goes red — each round is visible in the ledger. Acceptance: all six stages green, `validate` shows `0 blocking`, `stamp` shows a constructed world_id. Do NOT press Keep for throwaway scenarios. Save the attempt-log line as evidence (quote it in the commit body).
- [ ] **Step 2: CLI parity check** — `uv run ah world build --scenario "<same throwaway>" --live` prints a world id (this DOES store; use `--db` pointed at a scratch file: `uv run ah --db scratch.db world build ...`, then delete `scratch.db`).
- [ ] **Step 3: CHANGELOG** — WP-A entry: envelope stamping, schema-derived prompt v2, the console's envelope stage, and the measured before/after (38 extra keys + 6 missing → clean compile). Update `docs/USER-MANUAL.md`'s build-console subsection: delete the "known state: live path still ends in a validator rejection" sentence (it stops being true), replace with the live-green state.
- [ ] **Step 4: Full gate in the branch's tree, background, to a file; read the `EXIT:` line and pass count.** Also ruff + format + pyright.
- [ ] **Step 5: Merge `--no-ff` into main when green, plain push. Drop the stash afterwards** (`git stash drop` — its content now lives in Task 1's commit; say so in the merge body).

---

## Self-review notes

- Coverage: diagnosis→fix mapping is total: missing envelope (Task 1), wrong field list (Task 2), watchability (Task 3), proof (Task 4).
- Type consistency: `stamp_envelope` signature identical across Tasks 1 and 3; `build_messages` shape matches v1 so `fetch_raw_text` needs no change.
- Judgment call recorded: `prompt_v1.py` is kept for provenance history; v2 is a parallel module. Fixture envelopes are carried, never re-stamped — re-stamping would break the 50-fixture regression and fixture determinism.
- Risk named: the few-shot example may exceed sensible prompt size — bounded mitigation written into Task 2 Step 3.
