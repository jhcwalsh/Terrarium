"""The two invariants every stage-2 week-C reading rests on.

Self-contained -- no catalog, no network, no ensemble, no fitted engine. These
guard ``scripts/stage2_worlds.py``'s composition, whose whole claim is that the
platform's flesh machinery runs byte-verbatim underneath a runtime substitution:

1. ``test_the_projection_reproduces_the_stage2_season_exactly`` -- the flesh is
   only conditioned on the classification the exam judges because the projection
   into the ``SpinePaths`` contract makes ``ah.gen.spine.spine_quadrant`` return
   the coupled chain's own season. If that identity ever breaks, every A1/A2/R2
   number is silently mis-conditioned rather than wrong in a visible way.
2. ``test_a_broken_projection_is_a_stop`` -- the same check, from the other side:
   a projection that does NOT reproduce the season must raise. A guard that
   cannot fail is not a guard, so it is broken on purpose here and the failure is
   demanded. (Written against the defect, per the platform's own rule on tests
   that merely restate the implementation.)
3. ``test_the_substitution_is_removed_on_the_way_out`` -- the substitution is a
   global mutation of ``ah.gen.spine.sample_spine`` and of the registered spine
   factory. If either survived the ``with`` block, an unrelated later run in the
   same process would silently get the stage-2 engine. Both the normal exit and
   the exception path are checked, because the exception path is the one that
   gets forgotten.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

import ah.gen.spine as spine_module
from ah.gen import stress as stress_module
from ah.gen.spine import spine_quadrant

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load(name: str) -> Any:
    """Load a ``scripts/`` module by path -- the platform's own test pattern.

    Registered in ``sys.modules`` under its own name so the module's own
    ``import stage2_fit`` resolves to the SAME object this file reaches through
    ``worlds.weeka``. Loading it twice would give two ``FitError`` classes and a
    ``pytest.raises`` that silently never matches.
    """
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


worlds = _load("stage2_worlds")
FitError = worlds.weeka.FitError

ERA_PP = 3.351323828920571
MONTHS = 24


@dataclass(frozen=True)
class _Decade:
    """The three fields the projection reads off a ``Stage2Decade``."""

    season: np.ndarray
    yoy: np.ndarray
    expanding: np.ndarray
    states: np.ndarray


def _decade(seed: int) -> _Decade:
    """A decade whose season spans all four quadrants, built from a fixed tape."""
    rng = np.random.Generator(np.random.PCG64(seed))
    yoy = ERA_PP + rng.normal(0.0, 2.0, size=MONTHS)
    expanding = rng.random(MONTHS) < 0.6
    season = (expanding.astype(np.int64) << 1) | (yoy > ERA_PP).astype(np.int64)
    states = rng.normal(0.0, 1.0, size=(MONTHS, 5))
    return _Decade(season=season, yoy=yoy, expanding=expanding, states=states)


def test_the_projection_reproduces_the_stage2_season_exactly() -> None:
    decades = [_decade(11), _decade(12)]
    assert len(set(np.unique(np.concatenate([d.season for d in decades])))) == 4, (
        "the fixture must span all four quadrants or it cannot test the mapping"
    )
    paths = worlds.spine_paths_from_decades(
        cast(Any, decades), ERA_PP, seed=1, attempts=len(decades)
    )
    for p, decade in enumerate(decades):
        for m in range(MONTHS):
            assert spine_quadrant(paths.states[p, m], int(paths.labels[p, m]), mu_pi=0.0) == int(
                decade.season[m]
            )
    # the projection touches column 0 and nothing else: the credit gap the
    # severity table reads must survive verbatim
    for p, decade in enumerate(decades):
        assert np.array_equal(paths.states[p, :, 1:], decade.states[:, 1:])


def test_a_broken_projection_is_a_stop() -> None:
    """Break the identity the guard exists for, and demand the raise."""
    decade = _decade(13)
    broken = _Decade(
        season=1 - decade.season,  # any season that is not the chain's own
        yoy=decade.yoy,
        expanding=decade.expanding,
        states=decade.states,
    )
    with pytest.raises(FitError, match="projection is not exact"):
        worlds.spine_paths_from_decades(cast(Any, [broken]), ERA_PP, seed=1, attempts=1)


@dataclass(frozen=True)
class _StubFrozen:
    """The only field ``stage2_flesh`` reads before a batch is compiled."""

    era_threshold_pp: float = ERA_PP


def test_the_substitution_is_removed_on_the_way_out() -> None:
    frozen = cast(Any, _StubFrozen())  # no batch is compiled inside the block
    before_sampler = spine_module.sample_spine
    before_factory = stress_module._SPINE_FACTORY

    with worlds.stage2_flesh(frozen, premise_mode=worlds.PREMISE_UNCONDITIONAL):
        assert spine_module.sample_spine is not before_sampler
        assert stress_module._SPINE_FACTORY is worlds._Stage2SpineFactory
    assert spine_module.sample_spine is before_sampler
    assert stress_module._SPINE_FACTORY is before_factory

    with (
        pytest.raises(RuntimeError, match="deliberate"),
        worlds.stage2_flesh(frozen, premise_mode=worlds.PREMISE_DECLARED),
    ):
        raise RuntimeError("deliberate")
    assert spine_module.sample_spine is before_sampler
    assert stress_module._SPINE_FACTORY is before_factory


def test_an_unknown_premise_mode_is_refused() -> None:
    with (
        pytest.raises(ValueError, match="premise_mode"),
        worlds.stage2_flesh(cast(Any, object()), premise_mode="whatever"),
    ):
        pass  # pragma: no cover - the context manager never opens
