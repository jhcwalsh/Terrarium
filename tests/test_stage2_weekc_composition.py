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

D-SP-10 adds a fourth, and it is the one that makes the composed block sampler
admissible at all: ``scripts/stage2_worlds._reach_draw`` is a copy of the
platform's ``SpineBootstrap._draw`` with two gated additions, and a copy of
sealed-adjacent machinery drifts unless something pins it.
``test_the_baseline_reach_draw_is_the_platforms_own`` runs BOTH on the same
inputs and demands bit-identical row indices at ``REACH_BASELINE``; its partner
demands that a non-baseline design does NOT match, so the pin is a real
comparison rather than a tautology. Both run on a synthetic panel -- no catalog,
no network, no fitted engine -- because ``_draw`` reads nothing but arrays.
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


# --------------------------------------------------------------------------- #
# D-SP-10 -- the composed block sampler, pinned against the platform's own
# --------------------------------------------------------------------------- #

_PANEL_ROWS = 600
_DRAW_MONTHS = 60
_DRAW_PATHS = 4


class _FakeSource:
    """The three attributes ``_draw`` reads off a ``BootstrapSource``."""

    def __init__(self, values: np.ndarray, names: list[str]) -> None:
        self.values = values
        self.factor_names = names
        self.n_rows = int(values.shape[0])


def _draw_inputs(seed: int = 7) -> Any:
    """A synthetic ``_DrawInputs``: every array the sampler reads, and nothing else.

    Built so the sampler is genuinely exercised rather than short-circuited --
    all four quadrants are present in every severity stratum the world's
    percentiles and the severity table's shifts can open (35, 17.5, 8.75 and the
    5.0 floor), the hazard fires often enough to shift strata, and the join
    tolerances are satisfiable so joins actually happen.
    """
    from ah.gen.spine import HazardTable, _DrawInputs

    rng = np.random.Generator(np.random.PCG64(seed))
    names = ["equity_mkt", "hy_spread", "policy_rate", "cpi"]
    values = rng.normal(0.0, 0.2, size=(_PANEL_ROWS, len(names)))
    cells = np.arange(_PANEL_ROWS, dtype=np.int8) % 4  # every stratum holds all four
    scores = np.arange(_PANEL_ROWS, dtype=np.float64)  # eligible_rows takes a prefix
    yoy = 3.0 + (cells & 1) * 2.0 + rng.normal(0.0, 0.1, size=_PANEL_ROWS)
    era_bucket = (cells & 1).astype(np.int64)

    states = rng.normal(0.0, 1.0, size=(_DRAW_PATHS, _DRAW_MONTHS, 5))
    hot = rng.random((_DRAW_PATHS, _DRAW_MONTHS)) < 0.4
    states[:, :, 0] = np.where(hot, 1.0, 0.0)  # spine_quadrant: col0 - 0 > 0.5
    labels = np.where(
        rng.random((_DRAW_PATHS, _DRAW_MONTHS)) < 0.6, _EXP_CODE_T, _REC_CODE_T
    ).astype(np.int64)
    sp = worlds.SpinePaths(
        states=states,
        labels=labels,
        cycle=np.zeros((_DRAW_PATHS, _DRAW_MONTHS)),
        policy=np.zeros((_DRAW_PATHS, _DRAW_MONTHS)),
        mu_pi=np.zeros(_DRAW_PATHS),
        pi_actual=np.zeros((_DRAW_PATHS, _DRAW_MONTHS)),
        attempts=_DRAW_PATHS,
        seed=seed,
    )
    world = worlds.load_world()  # a JSON read: no catalog, no network
    return _DrawInputs(
        source=cast(Any, _FakeSource(values, names)),
        sp=sp,
        hazard=HazardTable(
            rates=np.full(4, 0.05),
            era_threshold_pp=4.0,
            cell_months=np.full(4, 100),
            fallback_rate=0.05,
        ),
        scores=scores,
        cells=cells,
        yoy=yoy,
        era_bucket=era_bucket,
        months=_DRAW_MONTHS,
        n_paths=_DRAW_PATHS,
        seed=seed,
        stress=cast(Any, world.stress),
        spine=cast(Any, world.spine),
        pools={},
    )


_EXP_CODE_T = worlds._EXP_CODE
_REC_CODE_T = worlds._REC_CODE


def test_the_baseline_reach_draw_is_the_platforms_own() -> None:
    """The copy is admissible only while it reproduces the original exactly."""
    platform, _ = spine_module.SpineBootstrap._draw(cast(Any, None), _draw_inputs())
    composed, _ = worlds._reach_draw(_draw_inputs(), worlds.reach_design(worlds.REACH_BASELINE))
    assert np.array_equal(platform, composed), (
        "the composed block sampler no longer reproduces ah.gen.spine.SpineBootstrap._draw "
        "at REACH_BASELINE; the platform's rule and this campaign's copy of it have drifted"
    )


def test_a_design_that_does_nothing_would_fail_that_pin() -> None:
    """The pin bites: a design that changes the rule must change the tape.

    Without this, a ``_reach_draw`` that silently ignored its ``design`` would
    pass the test above and the whole fix would be inert while reporting
    success -- which is exactly the failure mode the platform's rule on tests
    that restate the implementation is written against.
    """
    baseline, _ = worlds._reach_draw(_draw_inputs(), worlds.reach_design(worlds.REACH_BASELINE))
    adopted, stamp = worlds._reach_draw(_draw_inputs(), worlds.ADOPTED_REACH)
    assert not np.array_equal(baseline, adopted)
    assert stamp["divergence_breaks"] > 0


def test_the_composed_draw_is_deterministic_and_seed_separated() -> None:
    """Same seed, same tape; a different seed, a different tape."""
    a, _ = worlds._reach_draw(_draw_inputs(seed=7), worlds.ADOPTED_REACH)
    b, _ = worlds._reach_draw(_draw_inputs(seed=7), worlds.ADOPTED_REACH)
    c, _ = worlds._reach_draw(_draw_inputs(seed=11), worlds.ADOPTED_REACH)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_the_fix_raises_reach_on_the_synthetic_panel() -> None:
    """The property the ruling funded, asserted on a panel with no fitted engine.

    Reach is the share of months whose drawn row carries the spine's own
    quadrant. It is what D-SP-10 is about, so it is checked here rather than
    only in the campaign's artifact.
    """
    args = _draw_inputs()
    spine_q = np.array(
        [
            [
                spine_quadrant(args.sp.states[p, m], int(args.sp.labels[p, m]), mu_pi=0.0)
                for m in range(args.months)
            ]
            for p in range(args.n_paths)
        ]
    )
    base_rows, _ = worlds._reach_draw(args, worlds.reach_design(worlds.REACH_BASELINE))
    fix_rows, _ = worlds._reach_draw(_draw_inputs(), worlds.ADOPTED_REACH)
    base = worlds.reach_metrics(base_rows, spine_q, np.asarray(args.cells))
    fixed = worlds.reach_metrics(fix_rows, spine_q, np.asarray(args.cells))
    assert fixed["conditioning_reach"] > base["conditioning_reach"]


def test_reach_metrics_counts_starts_and_matches_separately() -> None:
    """The two numbers are different quantities and must not collapse.

    Hand-built: one path of four months. Rows 0 -> 1 -> 1 -> 2. The second step
    repeats a row and the third advances by one, so exactly two months open a
    block (month 0 and the repeat). Quadrants are set so three of the four
    months carry the spine's own -- a case where "selected" and "matched"
    genuinely disagree, which is the whole point of reporting both.
    """
    rows = np.array([[0, 1, 1, 2]], dtype=np.int64)
    cells = np.array([1, 2, 3], dtype=np.int8)  # row 0 -> q1, row 1 -> q2, row 2 -> q3
    seasons = np.array([[1, 2, 0, 3]], dtype=np.int64)
    out = worlds.reach_metrics(rows, seasons, cells)
    assert out["months_selected_for_their_quadrant"] == 2
    assert out["share_of_months_selected_for_their_quadrant"] == 0.5
    assert out["months_whose_drawn_row_carries_the_spine_s_quadrant"] == 3
    assert out["conditioning_reach"] == 0.75
    assert out["distinct_panel_rows_visited"] == 3


def test_an_unknown_reach_design_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown reach design"):
        worlds.reach_design("whatever-the-owner-did-not-fund")


def test_an_unknown_premise_mode_is_refused() -> None:
    with (
        pytest.raises(ValueError, match="premise_mode"),
        worlds.stage2_flesh(cast(Any, object()), premise_mode="whatever"),
    ):
        pass  # pragma: no cover - the context manager never opens
