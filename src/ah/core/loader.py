"""Load and validate WorldSpec documents.

``load_worldspec`` runs the **JSON Schema (Draft 2020-12) first** — the schema is
the normative contract — and only then constructs the pydantic model. Both must
agree (asserted by a property test); running both on load is the belt-and-suspenders
the WorldSpec doc calls for ("schema = interchange truth, pydantic = ergonomic
mirror; a test asserts they agree").
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ah.core.worldspec import WorldSpec

# WP2R.7: v1.2 is the active contract; it accepts 1.0.x documents unchanged (the
# sealed fixtures and vendored example stay untouched). worldspec-v1.0.schema.json
# remains in schemas/ as the vendored record of the original contract.
_SCHEMA_FILENAME = "worldspec-v1.2.schema.json"


def _repo_root() -> Path:
    # src/ah/core/loader.py -> parents[3] == repo root (editable/dev layout).
    return Path(__file__).resolve().parents[3]


def schema_path() -> Path:
    """Absolute path to the vendored, normative WorldSpec JSON Schema."""
    return _repo_root() / "schemas" / _SCHEMA_FILENAME


@lru_cache(maxsize=1)
def worldspec_schema() -> dict[str, Any]:
    """The parsed WorldSpec JSON Schema (cached)."""
    return json.loads(schema_path().read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = worldspec_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class WorldSpecSchemaError(ValueError):
    """Raised when a document fails JSON Schema validation (before pydantic)."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("WorldSpec failed JSON Schema validation:\n" + "\n".join(errors))


def is_schema_valid(document: dict[str, Any]) -> bool:
    """True iff the document satisfies the WorldSpec JSON Schema (no format checks)."""
    return _validator().is_valid(document)


def validate_against_schema(document: dict[str, Any]) -> None:
    """Raise ``WorldSpecSchemaError`` with all findings if the document is invalid."""
    errors = sorted(_validator().iter_errors(document), key=lambda e: list(e.path))
    if errors:
        msgs = [f"  at /{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors]
        raise WorldSpecSchemaError(msgs)


def _read_source(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def load_worldspec(source: str | Path | dict[str, Any]) -> WorldSpec:
    """Load a WorldSpec from a path or dict: JSON Schema first, then pydantic."""
    data = _read_source(source)
    validate_against_schema(data)
    return WorldSpec.model_validate(data)
