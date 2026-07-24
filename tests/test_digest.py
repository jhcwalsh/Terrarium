"""WP0.6 acceptance (core side): canonical serialization + digests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ah.core.digest import (
    canonical_json,
    digest_ensemble,
    digest_paths,
    sha256_of_arrays,
)
from ah.core.engine import run_ensemble, run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE: dict[str, Any] = json.loads(
    (ROOT / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
)


def toy_world() -> Any:
    doc = copy.deepcopy(_EXAMPLE)
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    return project_numeric(WorldSpec.model_validate(doc))


def test_digest_paths_is_deterministic() -> None:
    w = toy_world()
    assert digest_paths(run_path(w, 42)) == digest_paths(run_path(w, 42))


def test_digest_paths_changes_with_seed() -> None:
    w = toy_world()
    assert digest_paths(run_path(w, 1)) != digest_paths(run_path(w, 2))


def test_digest_has_prefix() -> None:
    assert digest_paths(run_path(toy_world(), 3)).startswith("sha256:")


def test_digest_ensemble_deterministic() -> None:
    w = toy_world()
    a = digest_ensemble(run_ensemble(w, 3, base_seed=100))
    b = digest_ensemble(run_ensemble(w, 3, base_seed=100))
    assert a == b


def test_sha256_of_arrays_rounds_below_tolerance() -> None:
    a = [1.0, 2.0, 3.0]
    b = [1.0, 2.0, 3.0 + 1e-15]  # below the 12-decimal rounding threshold
    assert sha256_of_arrays([a]) == sha256_of_arrays([b])


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    # nested + stable
    assert canonical_json({"x": {"z": 1, "y": 2}}) == '{"x":{"y":2,"z":1}}'
