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
# deliberately only when an intended engine change alters output. Last
# regeneration: the unit-coherence fix (percent-space constants restored from
# the plan's decimal-convention literals; owner-approved deviation).
GOLDEN_SEED = 42
# toy-v0.4 (register ER-7: standardized Student-t market innovations).
# Regenerated because the engine's numbers changed by design, which is what a
# golden snapshot exists to force someone to notice. Prior value, toy-v0.3:
# d6da53bc277c9b95922f2e5f2912b94843892383b5198e9bb3624d3800de9180
# Re-pinned under toy-v0.6 (ER-10). Prior value, toy-v0.5:
# 6c3f7c896a552b49eccbdb07aff4aed175ef9eebf6df9d98919a5e136a9a1f83
GOLDEN_DIGEST = "61e78e609d2a360b573a641abe0c8a1eea693f8cb527ac3148419280a218d6f5"


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


_PRESET_DIR = ROOT / "src" / "ah" / "presets"


def _preset_world(name: str) -> tuple[NumericWorld, int]:
    doc = json.loads((_PRESET_DIR / f"{name}.json").read_text(encoding="utf-8"))
    world = project_numeric(WorldSpec.model_validate(doc))
    seed = world.engine_defaults.base_seed
    return world, (seed if seed is not None else 0)


def test_reported_marks_catch_up_to_truth_er10() -> None:
    """ER-10 (found 2026-08-12): the old _reported_marks filtered only the
    quarter-end MONTH's return, silently discarding the other two months —
    reported PM cumulated ~1/3 of truth (stagflation pc: 23% reported vs
    77% true over the decade). Appraisal smoothing must DELAY returns, not
    destroy them: over a long horizon, cumulative reported must land near
    cumulative true. The old code fails this at ratio ~0.30.

    Summed over a small deterministic ensemble (not one path): a single
    40-quarter draw is a right-censored EWMA — whichever quarter lands last
    is only partially caught up (nothing follows it to finish the catch-up),
    so one path's ratio swings with that quarter's own size (observed 0.77-
    1.39 across seeds on stagflation/re alone). Summing several paths keeps
    the same invariant on the SAME fixture/weights but is no longer a bet on
    one draw's final quarter.
    """
    for preset in ("stagflation", "goldilocks"):
        world, seed = _preset_world(preset)
        res = run_ensemble(world, n_paths=16, base_seed=seed)
        for sleeve in REPORTED_SLEEVES:
            true_sum = float(res.returns[sleeve].sum())
            rep_sum = float(res.reported[sleeve].sum())
            assert true_sum > 20.0, f"{preset}/{sleeve}: fixture drifted"
            ratio = rep_sum / true_sum
            assert 0.80 < ratio < 1.20, (
                f"{preset}/{sleeve}: cumulative reported/true = {ratio:.2f} "
                "- smoothing is destroying or inventing return (ER-10)"
            )


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
