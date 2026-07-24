"""WP0.4 acceptance: the deterministic toy engine.

* golden snapshot: seed 42 on the stagflation world hashes to a frozen digest;
* determinism: two runs of the same seed are bit-identical;
* properties (hypothesis): no NaN/inf, rate >= 0.1, spread >= 150, reported marks
  are flat (zero) off quarter-ends, across seeds and horizon lengths;
* ensemble seeding and the unsupported-generator guard.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ah.core.engine import (
    ASSETS,
    REPORTED_SLEEVES,
    UnsupportedGeneratorError,
    run_ensemble,
    run_path,
)
from ah.core.numericworld import NumericWorld, project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "schemas" / "example-long-stagflation.worldspec.json"
_EXAMPLE: dict[str, Any] = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

# Frozen golden digest for seed 42 on the stagflation world (toy-v0). Regenerate
# deliberately only when an intended engine change alters output.
GOLDEN_SEED = 42
GOLDEN_DIGEST = "aea5b731c90d379a5d219e5b08291425666c821cfd240e5adc568027bc575ae7"


def make_world(quarters: int | None = None) -> NumericWorld:
    """A stagflation NumericWorld with the toy generator (optionally re-horizoned)."""
    doc = copy.deepcopy(_EXAMPLE)
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    if quarters is not None:
        doc["horizon"]["quarters"] = quarters
    return project_numeric(WorldSpec.model_validate(doc))


def digest_of(paths: Any) -> str:
    h = hashlib.sha256()
    for arr in (paths.rate, paths.spread, paths.inflation, paths.crisis):
        h.update(np.round(arr, 12).tobytes())
    for a in ASSETS:
        h.update(np.round(paths.returns[a], 12).tobytes())
    for a in REPORTED_SLEEVES:
        h.update(np.round(paths.reported[a], 12).tobytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# golden + determinism
# --------------------------------------------------------------------------- #


def test_golden_snapshot() -> None:
    p = run_path(make_world(), GOLDEN_SEED)
    assert p.months == 120
    assert digest_of(p) == GOLDEN_DIGEST


def test_determinism_same_seed() -> None:
    a = run_path(make_world(), 123)
    b = run_path(make_world(), 123)
    for asset in ASSETS:
        assert np.array_equal(a.returns[asset], b.returns[asset])
    assert np.array_equal(a.rate, b.rate)
    assert np.array_equal(a.spread, b.spread)
    assert np.array_equal(a.inflation, b.inflation)


def test_different_seeds_differ() -> None:
    a = run_path(make_world(), 1)
    b = run_path(make_world(), 2)
    assert not np.array_equal(a.returns["equity"], b.returns["equity"])


# --------------------------------------------------------------------------- #
# properties
# --------------------------------------------------------------------------- #


@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 2**31 - 1), quarters=st.integers(8, 40))
def test_invariants_hold(seed: int, quarters: int) -> None:
    p = run_path(make_world(quarters), seed)
    nm = quarters * 3
    assert p.months == nm

    for asset in ASSETS:
        arr = p.returns[asset]
        assert arr.shape == (nm,)
        assert np.all(np.isfinite(arr))

    assert np.all(p.rate >= 0.1)
    assert np.all(p.spread >= 150.0)
    assert np.all(np.isfinite(p.inflation))

    # reported marks are zero off quarter-ends
    for sleeve in REPORTED_SLEEVES:
        rep = p.reported[sleeve]
        off_quarter = [m for m in range(nm) if (m + 1) % 3 != 0]
        assert np.all(rep[off_quarter] == 0.0)


def test_reported_marks_present_at_quarter_ends() -> None:
    p = run_path(make_world(), 7)
    for sleeve in REPORTED_SLEEVES:
        quarter_ends = [m for m in range(p.months) if (m + 1) % 3 == 0]
        # at least some quarter-end marks are nonzero (sanity, not guaranteed all)
        assert any(p.reported[sleeve][m] != 0.0 for m in quarter_ends)


# --------------------------------------------------------------------------- #
# ensemble + guards
# --------------------------------------------------------------------------- #


def test_ensemble_seeds_and_shapes() -> None:
    res = run_ensemble(make_world(), n_paths=5, base_seed=1000)
    assert res.n_paths == 5
    assert res.seeds == [1000, 8919, 16838, 24757, 32676]
    for asset in ASSETS:
        assert res.returns[asset].shape == (5, res.months)


def test_ensemble_path_matches_single_run() -> None:
    world = make_world()
    res = run_ensemble(world, n_paths=4, base_seed=555)
    single = run_path(world, res.seeds[2])
    assert np.array_equal(res.returns["equity"][2], single.returns["equity"])


def test_ensemble_default_base_seed_from_world() -> None:
    # example base_seed is 771204
    res = run_ensemble(make_world(), n_paths=2)
    assert res.seeds[0] == 771204


def test_unsupported_generator_raises() -> None:
    doc = copy.deepcopy(_EXAMPLE)  # generator_id = conditional-diffusion
    world = project_numeric(WorldSpec.model_validate(doc))
    with pytest.raises(UnsupportedGeneratorError):
        run_path(world, 1)
    with pytest.raises(UnsupportedGeneratorError):
        run_ensemble(world, 2)


def test_ensemble_rejects_nonpositive_paths() -> None:
    with pytest.raises(ValueError):
        run_ensemble(make_world(), 0)
