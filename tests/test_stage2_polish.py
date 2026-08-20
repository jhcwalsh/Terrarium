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
