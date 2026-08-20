"""D-SP-12 (the polish round): the engine substitutions, pinned.

Charter: ``governance/decision-register.md`` **D-SP-12** (owner ruling
2026-08-19). The round's behavioural changes live in
``scripts/stage2_polish.py``, a module **outside every seal**. Change 1 is join
selection by inflation distance: among the era-safe candidates the compiler
already admits, the one whose trailing-inflation gap at the seam is smallest is
taken, with the earliest panel row as the deterministic tie-break.

**Why a substitution rather than an edit.** ``scripts/stage2_worlds.py`` is
hashed by ``docs/superpowers/specs/stage2-prereg-2.json`` -- the D-SP-11 seal
names it as the era rule's implementation. Editing it would need an amendment,
which would mean editing a sealed file, which D-SP-12's charter forbids. The
substitution keeps **the sealed era rule's own code as the code that runs** and
adds the polish behaviour around it. These tests are what makes that
admissible: each one pins the substitution to the platform's behaviour where it
is supposed to be inert, and demonstrates the change where it is not.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"


def _load(name: str) -> ModuleType:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def polish() -> ModuleType:
    return _load("stage2_polish")


@pytest.fixture(scope="module")
def worlds() -> ModuleType:
    return _load("stage2_worlds")


# --------------------------------------------------------------------------- #
# 1. join selection by inflation distance
# --------------------------------------------------------------------------- #


def test_the_minimal_gap_candidate_wins(polish: ModuleType) -> None:
    """Given a candidate set, the smallest |dYoY| at the seam is the one taken."""
    yoy = np.array([1.0, 5.0, 2.5, 9.0, 3.1, 3.0], dtype=np.float64)
    candidates = np.array([1, 2, 3, 4], dtype=np.int64)
    # standing on row 5 (yoy 3.0): gaps are 2.0, 0.5, 6.0, 0.1 -> row 4 wins
    assert polish.min_gap_pick(candidates, yoy, previous=5) == 4
    # standing on row 0 (yoy 1.0): gaps are 4.0, 1.5, 8.0, 2.1 -> row 2 wins
    assert polish.min_gap_pick(candidates, yoy, previous=0) == 2


def test_ties_break_to_the_earliest_panel_row(polish: ModuleType) -> None:
    """The declared tie-break: equal gaps go to the earlier panel date.

    Stated as a rule rather than left to argsort's stability, because a rule
    that depends on a library's internal choice is not a rule.
    """
    yoy = np.array([2.0, 4.0, 0.0, 4.0, 3.0], dtype=np.float64)
    candidates = np.array([1, 3], dtype=np.int64)  # both exactly 1.0 above row 4
    assert polish.min_gap_pick(candidates, yoy, previous=4) == 1
    # reversing the candidate order must not reverse the answer
    assert polish.min_gap_pick(candidates[::-1].copy(), yoy, previous=4) == 1


def test_min_gap_pick_is_deterministic_across_repeats(polish: ModuleType) -> None:
    """No RNG, no ordering luck: the same inputs give the same row, every time."""
    rng = np.random.Generator(np.random.PCG64(20260819))
    yoy = rng.normal(3.0, 2.0, size=200)
    for _ in range(25):
        candidates = np.sort(rng.choice(200, size=17, replace=False)).astype(np.int64)
        previous = int(rng.integers(0, 200))
        first = polish.min_gap_pick(candidates, yoy, previous=previous)
        assert all(
            polish.min_gap_pick(candidates, yoy, previous=previous) == first for _ in range(3)
        )
        gaps = np.abs(yoy[candidates] - yoy[previous])
        assert np.isclose(abs(yoy[first] - yoy[previous]), gaps.min())


def test_the_selection_is_off_by_default_and_restored_after(
    polish: ModuleType, worlds: ModuleType
) -> None:
    """Importing the module changes nothing; the context manager is the switch."""
    before = (worlds._join_filter, worlds._path_prefix_pick, worlds._path_agreement_pick)
    with polish.join_selection(polish.SELECTION_MIN_GAP):
        assert worlds._path_prefix_pick is not before[1]
    assert (worlds._join_filter, worlds._path_prefix_pick, worlds._path_agreement_pick) == before


def test_the_platform_rule_inside_the_context_is_bit_identical(
    polish: ModuleType, worlds: ModuleType
) -> None:
    """``SELECTION_PLATFORM`` inside the context must draw exactly as outside it.

    The anti-drift device for the whole substitution: if the wrapper changed the
    tape even when the rule is 'do what the platform does', nothing measured
    under it would be comparable to the D-SP-11 record. The candidates are
    routed through ``_join_filter`` so the wrapper is genuinely live on them.
    """
    cells = np.zeros(64, dtype=np.int64)
    spine_q = np.zeros(64, dtype=np.int64)
    pool = np.array([3, 9, 21, 40], dtype=np.int64)
    yoy = np.arange(64, dtype=np.float64)
    era = np.zeros(64, dtype=np.int64)

    def pick() -> int:
        filtered = worlds._join_filter(pool, era, yoy, 8, 100.0, era_relaxed=False)
        return worlds._path_prefix_pick(
            filtered, cells, spine_q, 0, 6, np.random.Generator(np.random.PCG64(7))
        )

    outside = pick()
    with polish.join_selection(polish.SELECTION_PLATFORM):
        inside = pick()
    assert inside == outside


def test_the_selection_only_fires_on_a_join_filtered_candidate_set(
    polish: ModuleType, worlds: ModuleType
) -> None:
    """Month 0 and the unfiltered panel-edge fallback are NOT joins.

    Those two call sites hand ``_path_prefix_pick`` the raw pool, not the output
    of ``_join_filter``, and neither creates a seam whose inflation gap is a
    meaningful quantity (month 0 has no previous row; the unfiltered fallback is
    the owner's 2026-08-16 panel-edge rule and is byte-unchanged). The
    substitution recognises the difference by identity, and this is the check.
    """
    cells = np.zeros(64, dtype=np.int64)
    spine_q = np.zeros(64, dtype=np.int64)
    pool = np.array([3, 9, 21, 40], dtype=np.int64)
    yoy = np.arange(64, dtype=np.float64)
    era = np.zeros(64, dtype=np.int64)

    expected = polish._ORIGINAL_PREFIX_PICK(
        pool, cells, spine_q, 0, 6, np.random.Generator(np.random.PCG64(11))
    )
    with polish.join_selection(polish.SELECTION_MIN_GAP):
        # a pool that never passed through _join_filter: the platform's uniform draw
        got = worlds._path_prefix_pick(
            pool, cells, spine_q, 0, 6, np.random.Generator(np.random.PCG64(11))
        )
        assert got == expected
        # the same rows, now arriving as a join_filter result: min-gap decides
        filtered = worlds._join_filter(pool, era, yoy, 8, 100.0, era_relaxed=False)
        picked = worlds._path_prefix_pick(
            filtered, cells, spine_q, 0, 6, np.random.Generator(np.random.PCG64(11))
        )
        assert picked == 9


# --------------------------------------------------------------------------- #
# 2. the era rule adopted -- the polish engine configuration
# --------------------------------------------------------------------------- #


def test_the_polish_engine_adopts_the_conditional_era_crossing_rule(
    polish: ModuleType, worlds: ModuleType
) -> None:
    """Change 2 as a check: the run entry point's default carries the rule.

    Every other field of the design is pinned too, because "adopt the era rule"
    means adopt D-SP-11's design and nothing else -- a block-length override or
    a relaxed join sneaking in beside it would be a second change wearing the
    first one's name.
    """
    assert polish.POLISH_REACH is worlds.ERA_CONDITIONAL_REACH
    assert polish.POLISH_REACH.era_conditional_crossing is True
    assert polish.POLISH_REACH.era_relaxed_joins is False
    assert polish.POLISH_REACH.anticipate is True
    assert polish.POLISH_REACH.break_on_divergence is True
    assert polish.POLISH_REACH.match_horizon == worlds.DEFAULT_MATCH_HORIZON
    assert polish.POLISH_REACH.block_months_override is None
    run = _load("stage2_polish_run")
    assert run.POLISH is polish.POLISH_REACH


def test_an_unlicensed_crossing_is_a_stop_and_not_a_number(polish: ModuleType) -> None:
    """The audit's verdict is raised, not reported. D-SP-11 wrote it that way."""
    assert polish.assert_licensed_crossings({"holds": True, "crossing_seams": 3}, arm="x")["holds"]
    with pytest.raises(RuntimeError, match="stop, not a diagnostic"):
        polish.assert_licensed_crossings({"holds": False, "unlicensed_crossing_seams": 2}, arm="x")


# --------------------------------------------------------------------------- #
# 3. the L1 across-decade dispersion recalibration
# --------------------------------------------------------------------------- #


def test_the_l1_substitution_is_bit_identical_at_unit_scale(polish: ModuleType) -> None:
    """Scale 1.0 must reproduce ``ah.gen.climate.simulate.simulate_decades`` exactly.

    The pin that makes the recalibrated arm attributable: at unit scale the
    substitution is the platform's own function, bit for bit, so every
    difference measured later is the calibration and not the copy.
    """
    from ah.gen.climate.simulate import simulate_decades
    from ah.gen.systems import _pinned_layers

    climate, _regimes = _pinned_layers()
    want = simulate_decades(climate, 6, seed=20260819, months=120)
    got = polish.scaled_simulate_decades(polish.L1_UNIT)(climate, 6, seed=20260819, months=120)
    assert np.array_equal(got.states, want.states)
    assert np.array_equal(got.theta_index, want.theta_index)


def test_a_smaller_scale_shrinks_the_across_decade_spread(polish: ModuleType) -> None:
    """The lever moves the quantity it is calibrated on, and in one direction."""
    from ah.gen.systems import _pinned_layers

    climate, _regimes = _pinned_layers()
    spreads = []
    for factor in (1.0, 0.6, 0.3):
        cal = polish.L1Calibration(sigma_pi=factor, sigma_r=factor)
        sim = polish.scaled_simulate_decades(cal)(climate, 40, seed=20260819, months=120)
        spreads.append(float(sim.states[:, :, 0].mean(axis=1).std(ddof=1)))
    assert spreads[0] > spreads[1] > spreads[2]


def test_only_the_two_declared_volatilities_move(polish: ModuleType) -> None:
    """Every other L1 parameter is the posterior's own, at every scale."""
    from ah.gen.climate.model import PARAM_NAMES
    from ah.gen.systems import _pinned_layers

    climate, _regimes = _pinned_layers()
    cal = polish.L1Calibration(sigma_pi=0.5, sigma_r=0.25)
    base = polish.scaled_simulate_decades(polish.L1_UNIT)(climate, 8, seed=20260819, months=24)
    got = polish.scaled_simulate_decades(cal)(climate, 8, seed=20260819, months=24)
    assert polish.CALIBRATED_PARAMS == ("sigma_pi", "sigma_r")
    for name in PARAM_NAMES:
        if name in polish.CALIBRATED_PARAMS:
            continue
        assert np.array_equal(got.params[name], base.params[name]), name
    assert np.allclose(got.params["sigma_pi"], base.params["sigma_pi"] * 0.5)
    assert np.allclose(got.params["sigma_r"], base.params["sigma_r"] * 0.25)


def test_the_l1_calibration_is_off_by_default_and_restored_after(polish: ModuleType) -> None:
    weeka = _load("stage2_fit")
    before = weeka.simulate_decades
    with polish.l1_calibration(polish.L1Calibration(sigma_pi=0.5, sigma_r=0.5)):
        assert weeka.simulate_decades is not before
    assert weeka.simulate_decades is before
    # the unit calibration installs nothing at all
    with polish.l1_calibration(polish.L1_UNIT):
        assert weeka.simulate_decades is before


def test_the_estimator_inverts_its_own_relation(polish: ModuleType) -> None:
    """``k`` solves ``S(k)^2 = F^2 + k^2 (S(1)^2 - F^2)`` at the target, exactly."""
    calibrate = _load("stage2_polish_calibrate")
    target, floor, at_unit = 2.0, 0.5, 4.0
    k = calibrate._solve(target, floor, at_unit)
    assert np.isclose(np.sqrt(floor**2 + k**2 * (at_unit**2 - floor**2)), target)


def test_the_recalibrated_parameters_go_to_a_new_versioned_artifact(
    polish: ModuleType,
) -> None:
    """The frozen week-A artifact is an INPUT to this round and is never written.

    D-SP-12's charter: "If the parameters are inside frozen fitted-params
    artifacts, produce a NEW versioned params artifact ... never edit the frozen
    one." So no module in this round may open the frozen path for writing.
    """
    import json

    assert polish.POLISH_PARAMS_PATH.name == "stage2-fitted-params-2.json"
    for name in ("stage2_polish", "stage2_polish_calibrate", "stage2_polish_run"):
        path = _SCRIPTS / f"{name}.py"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "write_text" in line:
                assert "POLISH_PARAMS_PATH" in line or "RESULTS" in line, line
    doc = json.loads(polish.POLISH_PARAMS_PATH.read_text(encoding="utf-8"))
    frozen = json.loads(
        (_REPO_ROOT / "docs/superpowers/specs/stage2-fitted-params.json").read_text(
            encoding="utf-8"
        )
    )
    assert doc["carried_from"]["fit"] == frozen["fit"], "the 42 week-A coefficients must be carried"
