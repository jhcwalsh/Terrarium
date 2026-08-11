"""WP2.10: the grid driver's two load-bearing claims.

1. Computing the reference ONCE and calling ``run_battery`` per cell is exactly
   what ``run_full_battery`` does per cell. The grid rests on this — it is the
   difference between a ~10-hour batch and a ~12-hour one — so it is pinned rather
   than assumed.
2. The plan covers every DN-1.1 letter at every seed index, is uniquely keyed, and
   is ordered cheapest-first so a mistake surfaces in minutes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from ah.eval import battery
from ah.eval.reference import compute_reference
from ah.gen import systems

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_driver():
    """Import ``scripts/run_ablation_grid.py`` as a module (it is not a package)."""
    path = _REPO_ROOT / "scripts" / "run_ablation_grid.py"
    spec = importlib.util.spec_from_file_location("run_ablation_grid", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_ablation_grid"] = module
    spec.loader.exec_module(module)
    return module


grid = _load_driver()


@pytest.fixture(autouse=True)
def restore_suites():
    """Snapshot and restore ``battery.SUITES`` around EVERY test in this module.

    ``SUITES`` is process-global and ``register_suite`` refuses to re-register a
    name, so a module that registers the eight reference-dependent suites and does
    not undo it poisons every later test file -- exactly the failure
    ``tests/test_monthly.py``'s own ``restore_suites`` fixture documents. This
    module registers them twice by design (that IS the thing under test), so the
    fixture is autouse rather than opt-in.
    """
    snapshot = dict(battery.SUITES)
    try:
        yield
    finally:
        battery.SUITES.clear()
        battery.SUITES.update(snapshot)


# --------------------------------------------------------------------------- #
# claim 1: the reference-reuse shortcut is not a shortcut
# --------------------------------------------------------------------------- #


def test_reusing_one_reference_reproduces_run_full_battery_exactly() -> None:
    """``run_full_battery``'s three documented steps, performed explicitly, must give
    a byte-identical report. If this ever diverges the grid is judging differently
    from every other battery script in the repo and must stop."""
    from test_eval_battery import (  # type: ignore[import-not-found]
        _orchestration_access,
        _orchestration_ensemble,
        _orchestration_manifest,
        _real_prereg,
    )

    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()
    access = _orchestration_access()
    prereg = _real_prereg()
    via_full = battery.run_full_battery(
        ensemble,
        access=access,
        manifest=manifest,
        prereg=prereg,
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    reference = compute_reference(
        access,
        manifest,
        vintage_id=ensemble.meta.vintage_id,
        seed=11,
        n_resamples=8,
        level=0.9,
        block_length=24,
        resample_length=ensemble.months,
    )
    battery.register_reference_dependent_suites(manifest, reference)
    via_reuse = battery.run_battery(
        ensemble, reference=reference, prereg=prereg, manifest=manifest, seed=0
    )

    assert via_reuse.to_json() == via_full.to_json()


def test_one_reference_serves_two_cells_identically() -> None:
    """The reuse is only sound because the reference does not depend on the ensemble
    beyond its ``months`` — two different ensembles of the same length must get the
    same bands from the same reference object."""
    from test_eval_battery import (  # type: ignore[import-not-found]
        _orchestration_access,
        _orchestration_ensemble,
        _orchestration_manifest,
        _real_prereg,
    )

    manifest = _orchestration_manifest()
    prereg = _real_prereg()
    reference = compute_reference(
        _orchestration_access(),
        manifest,
        vintage_id="v-orchestration",
        seed=11,
        n_resamples=8,
        level=0.9,
        block_length=24,
        resample_length=120,
    )
    battery.register_reference_dependent_suites(manifest, reference)

    a = _orchestration_ensemble()
    b = _orchestration_ensemble()
    b.paths = b.paths * 1.05
    ra = battery.run_battery(a, reference=reference, prereg=prereg, manifest=manifest, seed=0)
    rb = battery.run_battery(b, reference=reference, prereg=prereg, manifest=manifest, seed=0)

    bands_a = {r.name: r.band for r in ra.results if r.band is not None}
    bands_b = {r.name: r.band for r in rb.results if r.band is not None}
    assert bands_a.keys() == bands_b.keys()
    assert all(bands_a[k] == bands_b[k] for k in bands_a)
    # ...and the two ensembles genuinely produced different values, so the test is
    # not vacuously comparing a report to itself.
    va = {r.name: r.value for r in ra.results}
    vb = {r.name: r.value for r in rb.results}
    assert any(not (np.isnan(va[k]) and np.isnan(vb[k])) and va[k] != vb[k] for k in va)


# --------------------------------------------------------------------------- #
# claim 2: the plan
# --------------------------------------------------------------------------- #


def test_the_plan_covers_every_system_at_every_seed_index() -> None:
    cells = grid.plan_cells()
    assert len(cells) == len(systems.SYSTEMS) * len(systems.SEED_PLAN)
    for row in systems.SYSTEMS:
        indices = sorted(c.seed_index for c in cells if c.system_id == row.system_id)
        assert indices == [s.index for s in systems.SEED_PLAN]
    # Campaign-3 (AM-2026-08-10-001): the sealed six-letter grid, F included.
    assert {c.letter for c in cells} == {"A", "B", "C", "D", "E", "F"}


def test_every_cell_id_and_slug_is_unique() -> None:
    cells = grid.plan_cells()
    assert len({c.cell_id for c in cells}) == len(cells)
    assert len({c.slug for c in cells}) == len(cells)
    assert all(":" not in c.slug for c in cells)  # slugs become directory names


def test_neural_cells_carry_a_training_seed_and_deterministic_cells_do_not() -> None:
    for cell in grid.plan_cells():
        if cell.neural:
            assert cell.train_seed == systems.train_seed_for(cell.family, cell.seed_index)
        else:
            assert cell.train_seed is None


def test_every_cell_at_one_seed_index_shares_the_sampling_seed() -> None:
    """A cross-system difference must never be a seed difference."""
    cells = grid.plan_cells()
    for seed in systems.SEED_PLAN:
        at_index = {c.sample_seed for c in cells if c.seed_index == seed.index}
        assert at_index == {seed.sample_seed}


def test_the_plan_is_ordered_cheapest_first() -> None:
    """Campaign-3: hier-diffusion left the grid (does not race), so the cost
    ordering the campaign-2 assertion pinned -- diffusion strictly last, 4.6x
    the flow arm -- no longer has a subject. What remains checkable is that
    the deterministic systems run before every trained flow cell."""
    cells = grid.plan_cells()
    order = [c.system_id for c in cells]
    for cheap in ("bootstrap-v1", systems.SYSTEM_A_ID):
        for trained in (systems.SYSTEM_D_V2_ID, systems.SYSTEM_F_ID):
            assert order.index(cheap) < order.index(trained)


def test_the_driver_defaults_to_the_sealed_criterion_size() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--n-paths", type=int, default=grid.CRITERION_N_PATHS)
    parser.add_argument("--months", type=int, default=grid.CRITERION_MONTHS)
    args = parser.parse_args([])
    assert (args.n_paths, args.months) == (1024, 120)
    assert grid.REFERENCE_SEED == 20260726
    assert grid.N_RESAMPLES == 1000
    assert grid.BLOCK_LENGTH == 120
    assert pytest.approx(0.9) == grid.LEVEL
