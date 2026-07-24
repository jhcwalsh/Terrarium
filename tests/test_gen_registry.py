"""WP2.1 acceptance: generator registry + Ensemble container."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.gen import registry
from ah.gen.base import Ensemble, EnsembleMeta, Generator

ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE: dict[str, Any] = json.loads(
    (ROOT / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
)


class _FakeGen:
    generator_id = "fake-v0"

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: Any, n_paths: int, seed: int) -> Ensemble:
        return Ensemble(
            np.zeros((n_paths, 12, 2)),
            ["equity", "bonds"],
            EnsembleMeta("fake-v0", "v1", seed, n_paths, 12),
        )


def test_ensemble_shape_validation_and_access() -> None:
    e = _FakeGen().sample(None, 5, 0)
    assert e.n_paths == 5 and e.months == 12
    assert e.factor("bonds").shape == (5, 12)
    with pytest.raises(ValueError):
        Ensemble(np.zeros((5, 12)), ["a"], EnsembleMeta("x", "v", 0, 5, 12))  # 2D
    with pytest.raises(ValueError):
        Ensemble(np.zeros((5, 12, 3)), ["a", "b"], EnsembleMeta("x", "v", 0, 5, 12))  # mismatch


def test_register_and_resolve() -> None:
    registry.register("fake-v0", _FakeGen)
    g = registry.resolve("fake-v0")
    assert isinstance(g, Generator)
    assert g.generator_id == "fake-v0"
    assert "fake-v0" in registry.registered()


def test_unknown_generator_errors() -> None:
    with pytest.raises(registry.UnknownGeneratorError):
        registry.resolve("does-not-exist-v9")


def test_resolve_for_world_uses_generator_id() -> None:
    registry.register("bootstrap-stratified", _FakeGen)
    doc = copy.deepcopy(_EXAMPLE)
    doc["engine_defaults"]["generator_id"] = "bootstrap-stratified"
    world = project_numeric(WorldSpec.model_validate(doc))
    g = registry.resolve_for_world(world)
    assert g.generator_id == "fake-v0"  # the registered factory
