"""WP0.7 acceptance: compiler interface + offline regression harness.

All 50 fixtures compile -> validate; the 40 valid + 5 clamp worlds build and run
12+ months; the 5 reject worlds are rejected; clamp worlds record clamps. Plus unit
tests for postprocess and the fixture adapter. No network anywhere (pytest-socket).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.compiler.fixture_adapter import FixtureCompiler, slugify
from ah.compiler.interface import CompileError, CompilerProtocol
from ah.compiler.pipeline import process
from ah.compiler.postprocess import extract_json, strip_fences
from ah.compiler.prompt_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "compiler"
MANIFEST: list[dict[str, str]] = json.loads(
    (FIXTURES / "_manifest.json").read_text(encoding="utf-8")
)

COMPILER = FixtureCompiler(FIXTURES)


def test_manifest_has_50_entries_with_expected_kinds() -> None:
    assert len(MANIFEST) == 50
    kinds = [e["kind"] for e in MANIFEST]
    assert kinds.count("valid") == 40
    assert kinds.count("clamp") == 5
    assert kinds.count("reject") == 5


def test_fixture_compiler_satisfies_protocol() -> None:
    assert isinstance(COMPILER, CompilerProtocol)


@pytest.mark.parametrize("entry", MANIFEST, ids=[e["slug"] for e in MANIFEST])
def test_fixture_regression(entry: dict[str, str]) -> None:
    raw = COMPILER.compile(entry["scenario"])
    outcome = process(raw)
    kind = entry["kind"]

    if kind == "reject":
        assert outcome.rejected, f"{entry['slug']} should have been rejected"
        return

    assert not outcome.rejected, f"{entry['slug']} unexpectedly rejected: {outcome.reject_reason}"
    assert outcome.world is not None

    if kind == "clamp":
        assert outcome.result.clamps, "clamp fixture produced no clamps"

    # the compiled world actually runs (>= 12 months, all finite)
    nw = project_numeric(outcome.world)
    paths = run_path(nw, seed=7)
    assert paths.months >= 12
    for series in paths.returns.values():
        assert series.shape == (paths.months,)
        assert bool((series == series).all())  # no NaN


# --------------------------------------------------------------------------- #
# postprocess
# --------------------------------------------------------------------------- #


def test_extract_json_plain() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_fences() -> None:
    text = '```json\n{\n  "a": 1\n}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_surrounding_prose() -> None:
    text = 'Here is your world:\n{"world_id": "x"}\nHope that helps!'
    assert extract_json(text) == {"world_id": "x"}


def test_strip_fences_without_language_tag() -> None:
    assert strip_fences("```\n{}\n```") == "{}"


def test_extract_json_raises_on_no_object() -> None:
    with pytest.raises(CompileError):
        extract_json("no json here")


def test_extract_json_raises_on_bad_json() -> None:
    with pytest.raises(CompileError):
        extract_json("{not valid}")


def test_extract_json_raises_on_non_object() -> None:
    with pytest.raises(CompileError):
        extract_json("[1, 2, 3]")


# --------------------------------------------------------------------------- #
# fixture adapter + prompt
# --------------------------------------------------------------------------- #


def test_slugify_is_deterministic() -> None:
    assert slugify("Hello, World!") == "hello-world"


def test_fixture_compiler_missing_raises() -> None:
    with pytest.raises(CompileError):
        COMPILER.compile("a scenario that has no fixture at all")


def test_prompt_version_and_content() -> None:
    assert PROMPT_VERSION == "compile-world-v1.0"
    assert "JSON ONLY" in SYSTEM_PROMPT
    assert "FICTIONAL ENTITIES ONLY" in SYSTEM_PROMPT
    msgs = build_messages("a stagflation decade")
    assert msgs[0]["role"] == "user"
    assert "a stagflation decade" in msgs[0]["content"]


def test_anthropic_adapter_not_imported() -> None:
    """The live adapter must not be imported as a side effect of the compiler pkg."""
    import sys

    assert "ah.compiler.anthropic_adapter" not in sys.modules
