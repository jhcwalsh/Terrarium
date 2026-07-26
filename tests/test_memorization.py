"""WP2.2 Task 5 acceptance: the memorization tier (nn-distance, membership inference,
near-duplicate fraction).

This is the suite that makes "the generator didn't memorize its training data"
falsifiable, and WP2.2b's NC4 (a memorizer replaying training decades with noise) must
fail it -- so both directions are tested explicitly: a literal replayer scores
``nn_distance ~ 0``, ``membership_inference_auc ~ 1``, ``near_duplicate_fraction ~ 1``;
an independent seeded draw scores ``nn_distance`` clearly positive, AUC ~ 0.5, fraction
~ 0. Mirrors ``tests/test_utility.py``'s conventions (ground-truth simulation, an AST
guard proving no ``ah.eval.g2`` import).
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.random import PCG64, Generator

from ah.eval.metrics.memorization import (
    MEMORIZATION_BLOCK_MONTHS,
    MEMORIZATION_EPSILON_PERCENTILE,
    MEMORIZATION_MIN_TRAIN_BLOCKS,
    _block_distance,
    _leave_one_out_epsilon,
    _mann_whitney_auc,
    _nearest_neighbor_distance,
    _raw_blocks,
    _standardize,
    _train_validation_series,
    build_memorization_suite,
)
from ah.eval.reference import PANEL_STATS, ReferenceStats
from ah.factors import FactorManifest, FactorSource
from ah.gen.base import Ensemble, EnsembleMeta
from ah.splits import TRAIN, VALIDATION

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


def _meta(n_paths: int, months: int) -> EnsembleMeta:
    return EnsembleMeta(
        generator_id="test-gen", vintage_id="v", seed=0, n_paths=n_paths, months=months
    )


def _manifest() -> FactorManifest:
    blocks = {"global": ("g1",), "us": ("u1",)}
    sources = {
        "g1": FactorSource(kind="series", units="ret", series_id="s.g1", numeraire="total_return"),
        "u1": FactorSource(kind="series", units="ret", series_id="s.u1", numeraire="total_return"),
    }
    return FactorManifest(blocks=blocks, active_blocks=("global", "us"), sources=sources)


def _reference_with_series(series: dict[str, pd.Series]) -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=("global", "us"),
        vintage_id="v",
        n_resamples=1,
        seed=0,
        missing_factors=(),
        historical_series=series,
    )


def _combined_train_val_series(rng: Generator, train_months: int, val_months: int) -> pd.Series:
    """A single combined train+validation series spanning the sealed split boundary,
    exactly the shape ``ReferenceStats.historical_series`` carries in production."""
    train_dates = pd.date_range(TRAIN.start, periods=train_months, freq="MS")
    val_dates = pd.date_range(VALIDATION.start, periods=val_months, freq="MS")
    values = rng.normal(0.0, 0.04, size=train_months + val_months)
    return pd.Series(values, index=train_dates.append(val_dates))


# --------------------------------------------------------------------------- #
# 1. _train_validation_series -- the date-boundary split of an already-combined series
# --------------------------------------------------------------------------- #


def test_train_validation_series_splits_by_the_sealed_split_boundary() -> None:
    rng = Generator(PCG64(1))
    combined = _combined_train_val_series(rng, train_months=200, val_months=50)
    train, val = _train_validation_series(combined)
    assert len(train) == 200
    assert len(val) == 50
    # Sidesteps pandas-stubs' overly broad DatetimeIndex.max()/.min() return type: a
    # plain Python list of Timestamps, maxed/minned with the builtin, is unambiguously
    # typed (matches tests/test_reference.py's identical idiom).
    validation_start = pd.Timestamp(VALIDATION.start)
    validation_end = pd.Timestamp(VALIDATION.end)
    train_dates: list[pd.Timestamp] = list(train.index)
    val_dates: list[pd.Timestamp] = list(val.index)
    assert max(train_dates) < validation_start
    assert min(val_dates) >= validation_start
    assert max(val_dates) < validation_end


def test_train_validation_series_reconstructs_the_original_when_concatenated() -> None:
    """Splitting an already-fetched train+val series by the sealed boundary must
    recover exactly the rows a fresh ``access.frame(series_id, "train")`` /
    ``access.frame(series_id, "validation")`` read would have given -- the whole
    justification for not threading a live DataAccess through this suite."""
    rng = Generator(PCG64(2))
    combined = _combined_train_val_series(rng, train_months=100, val_months=40)
    train, val = _train_validation_series(combined)
    recombined = pd.concat([train, val]).sort_index()
    pd.testing.assert_series_equal(recombined, combined.sort_index())


# --------------------------------------------------------------------------- #
# 2. _standardize / _raw_blocks / _block_distance
# --------------------------------------------------------------------------- #


def test_standardize_gives_zero_mean_unit_std_by_the_reference_moments() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    standardized = _standardize(x, mean=3.0, std=2.0)
    np.testing.assert_allclose(standardized, [-1.0, -0.5, 0.0, 0.5, 1.0])


def test_raw_blocks_are_non_overlapping_and_drop_the_partial_tail() -> None:
    x = np.arange(10, dtype=np.float64)
    blocks = _raw_blocks(x, block_months=4, mean=0.0, std=1.0)
    assert blocks.shape == (2, 4)
    np.testing.assert_allclose(blocks[0], [0.0, 1.0, 2.0, 3.0])
    np.testing.assert_allclose(blocks[1], [4.0, 5.0, 6.0, 7.0])


def test_block_distance_of_a_block_against_itself_is_zero() -> None:
    b = np.array([1.0, -2.0, 3.0])
    assert _block_distance(b, b) == 0.0


def test_block_distance_is_euclidean() -> None:
    a = np.array([0.0, 0.0])
    b = np.array([3.0, 4.0])
    assert _block_distance(a, b) == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# 3. _nearest_neighbor_distance / _leave_one_out_epsilon
# --------------------------------------------------------------------------- #


def test_nearest_neighbor_distance_finds_the_closest_of_several_candidates() -> None:
    query = np.array([0.0, 0.0])
    candidates = np.array([[10.0, 10.0], [1.0, 0.0], [0.0, 5.0]])
    assert _nearest_neighbor_distance(query, candidates) == pytest.approx(1.0)


def test_leave_one_out_epsilon_is_small_for_genuinely_distinct_blocks() -> None:
    """Independent draws are, with overwhelming probability, all mutually far apart --
    epsilon (the 5th percentile of self nearest-neighbour distance) should sit well
    below the typical pairwise distance, not at it."""
    rng = Generator(PCG64(3))
    blocks = rng.normal(0.0, 1.0, size=(200, 12))
    epsilon = _leave_one_out_epsilon(blocks, MEMORIZATION_EPSILON_PERCENTILE)
    typical = np.median(
        [_nearest_neighbor_distance(blocks[i], np.delete(blocks, i, axis=0)) for i in range(50)]
    )
    assert epsilon < typical


# --------------------------------------------------------------------------- #
# 4. _mann_whitney_auc -- Mann-Whitney AUC via ranks (no sklearn)
# --------------------------------------------------------------------------- #


def test_mann_whitney_auc_is_one_half_when_scores_are_drawn_from_the_same_distribution() -> None:
    rng = Generator(PCG64(4))
    positive = rng.normal(0.0, 1.0, size=500)
    negative = rng.normal(0.0, 1.0, size=500)
    auc = _mann_whitney_auc(positive, negative)
    assert auc == pytest.approx(0.5, abs=0.05)


def test_mann_whitney_auc_is_one_when_positive_scores_always_exceed_negative() -> None:
    positive = np.array([5.0, 6.0, 7.0])
    negative = np.array([1.0, 2.0, 3.0])
    assert _mann_whitney_auc(positive, negative) == pytest.approx(1.0)


def test_mann_whitney_auc_is_zero_when_positive_scores_are_always_below_negative() -> None:
    positive = np.array([1.0, 2.0, 3.0])
    negative = np.array([5.0, 6.0, 7.0])
    assert _mann_whitney_auc(positive, negative) == pytest.approx(0.0)


def test_mann_whitney_auc_handles_ties_at_one_half_each() -> None:
    # every positive equals every negative -> each pairwise comparison is a tie (0.5)
    positive = np.array([1.0, 1.0])
    negative = np.array([1.0, 1.0])
    assert _mann_whitney_auc(positive, negative) == pytest.approx(0.5)


def test_mann_whitney_auc_nan_when_either_side_is_empty() -> None:
    assert math.isnan(_mann_whitney_auc(np.array([]), np.array([1.0])))
    assert math.isnan(_mann_whitney_auc(np.array([1.0]), np.array([])))


def test_mann_whitney_auc_matches_brute_force_pairwise_comparison() -> None:
    """Independent cross-check: AUC = P(positive > negative) + 0.5*P(tie), computed by
    literal pairwise enumeration."""
    rng = Generator(PCG64(6))
    positive = rng.normal(0.3, 1.0, size=30)
    negative = rng.normal(0.0, 1.0, size=25)
    fast = _mann_whitney_auc(positive, negative)
    wins = ties = 0
    for p in positive:
        for n in negative:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    brute = (wins + 0.5 * ties) / (positive.size * negative.size)
    assert fast == pytest.approx(brute)


# --------------------------------------------------------------------------- #
# 5. build_memorization_suite -- both directions on realistic ensembles
# --------------------------------------------------------------------------- #


def _panel(
    rng: Generator, train_months: int, val_months: int
) -> tuple[FactorManifest, ReferenceStats]:
    manifest = _manifest()
    reference = _reference_with_series(
        {
            "g1": _combined_train_val_series(rng, train_months, val_months),
            "u1": _combined_train_val_series(rng, train_months, val_months),
        }
    )
    return manifest, reference


def _literal_replayer_ensemble(
    reference: ReferenceStats, n_paths: int, months: int, seed: int, noise_scale: float = 1e-6
) -> Ensemble:
    """A generator that literally replays TRAIN blocks with tiny noise -- WP2.2b's NC4
    memorization failure mode. Every generated path is a noised concatenation of
    non-overlapping TRAIN blocks of ``g1``/``u1``."""
    rng = Generator(PCG64(seed))
    train_g1, _ = _train_validation_series(reference.historical_series["g1"])
    train_u1, _ = _train_validation_series(reference.historical_series["u1"])
    g1_vals = train_g1.to_numpy(dtype=np.float64)
    u1_vals = train_u1.to_numpy(dtype=np.float64)
    n_train = min(g1_vals.shape[0], u1_vals.shape[0])
    g1_vals, u1_vals = g1_vals[:n_train], u1_vals[:n_train]

    def one_path() -> tuple[np.ndarray, np.ndarray]:
        reps = -(-months // n_train)
        g1 = np.tile(g1_vals, reps)[:months] + rng.normal(0.0, noise_scale, size=months)
        u1 = np.tile(u1_vals, reps)[:months] + rng.normal(0.0, noise_scale, size=months)
        return g1, u1

    g1_paths, u1_paths = [], []
    for _ in range(n_paths):
        g1, u1 = one_path()
        g1_paths.append(g1)
        u1_paths.append(u1)
    paths = np.stack([np.stack(g1_paths), np.stack(u1_paths)], axis=-1)
    return Ensemble(paths=paths, factor_names=["g1", "u1"], meta=_meta(n_paths, months))


def _independent_ensemble(n_paths: int, months: int, seed: int) -> Ensemble:
    rng = Generator(PCG64(seed))
    paths = rng.normal(0.0, 0.04, size=(n_paths, months, 2))
    return Ensemble(paths=paths, factor_names=["g1", "u1"], meta=_meta(n_paths, months))


def test_literal_replayer_scores_as_memorized() -> None:
    """``months`` is set EQUAL to ``train_months`` so every generated path is a single,
    complete pass over the whole train series -- every train block gets replayed, not
    just a truncated prefix (a partial-coverage replayer would correctly score a
    membership-inference AUC between 0.5 and 1, not near 1, for the blocks it never
    touched -- that is the metric working as designed, not a bug in the fixture)."""
    rng = Generator(PCG64(10))
    manifest, reference = _panel(rng, train_months=240, val_months=200)
    ensemble = _literal_replayer_ensemble(reference, n_paths=6, months=240, seed=11)

    specs = {s.name: s for s in build_memorization_suite(manifest, reference)}
    nn_p05 = specs["nn_distance_p05"].fn(ensemble)
    nn_p50 = specs["nn_distance_p50"].fn(ensemble)
    auc = specs["membership_inference_auc"].fn(ensemble)
    dup_frac = specs["near_duplicate_fraction"].fn(ensemble)

    assert nn_p05 < 1e-3, nn_p05
    assert nn_p50 < 1e-3, nn_p50
    assert auc > 0.9, auc
    assert dup_frac > 0.9, dup_frac


def test_independent_draw_scores_as_not_memorized() -> None:
    rng = Generator(PCG64(20))
    manifest, reference = _panel(rng, train_months=600, val_months=200)
    ensemble = _independent_ensemble(n_paths=6, months=240, seed=21)

    specs = {s.name: s for s in build_memorization_suite(manifest, reference)}
    nn_p05 = specs["nn_distance_p05"].fn(ensemble)
    nn_p50 = specs["nn_distance_p50"].fn(ensemble)
    auc = specs["membership_inference_auc"].fn(ensemble)
    dup_frac = specs["near_duplicate_fraction"].fn(ensemble)

    assert nn_p05 > 0.5, nn_p05
    assert nn_p50 > 0.5, nn_p50
    assert auc == pytest.approx(0.5, abs=0.15), auc
    assert dup_frac < 0.05, dup_frac


def test_memorization_nan_when_no_factor_has_enough_train_blocks() -> None:
    manifest = _manifest()
    reference = _reference_with_series({})  # no historical data at all
    ensemble = _independent_ensemble(n_paths=2, months=24, seed=30)
    specs = {s.name: s for s in build_memorization_suite(manifest, reference)}
    for name in (
        "nn_distance_p05",
        "nn_distance_p50",
        "membership_inference_auc",
        "near_duplicate_fraction",
    ):
        assert math.isnan(specs[name].fn(ensemble))


def test_memorization_block_months_is_a_positive_constant() -> None:
    assert MEMORIZATION_BLOCK_MONTHS > 1


def test_memorization_min_train_blocks_floor_is_at_least_two() -> None:
    # leave-one-out epsilon needs >= 2 train blocks per factor to be defined at all.
    assert MEMORIZATION_MIN_TRAIN_BLOCKS >= 2


def test_every_memorization_metric_name_can_carry_a_sealed_threshold() -> None:
    rng = Generator(PCG64(40))
    manifest, reference = _panel(rng, train_months=300, val_months=100)
    specs = build_memorization_suite(manifest, reference)
    assert {s.name for s in specs} == {
        "nn_distance_p05",
        "nn_distance_p50",
        "membership_inference_auc",
        "near_duplicate_fraction",
    }
    for spec in specs:
        assert spec.tier == "monthly"
        assert spec.suite == "memorization"
        assert spec.name in PANEL_STATS


# --------------------------------------------------------------------------- #
# 6. registration bookkeeping
# --------------------------------------------------------------------------- #


def test_memorization_is_registered_in_prereg_metric_suite_names() -> None:
    from ah.eval import prereg as prereg_mod

    assert "memorization" in prereg_mod._METRIC_SUITE_NAMES


def test_memorization_suite_registered_in_reference_dependent_suite_builders() -> None:
    from ah.eval import battery as battery_mod

    assert battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS["memorization"] == (
        "ah.eval.metrics.memorization",
        "build_memorization_suite",
    )


# --------------------------------------------------------------------------- #
# 7. memorization.py never imports ah.eval.g2, never names FinalEvaluationToken, and
# never reads a live DataAccess (only the sealed TRAIN/VALIDATION split *boundaries*,
# which carry no read capability -- see the module docstring).
# --------------------------------------------------------------------------- #

_MEMORIZATION_PATH = ROOT / "src" / "ah" / "eval" / "metrics" / "memorization.py"


def test_memorization_module_never_imports_g2_or_names_the_token() -> None:
    text = _MEMORIZATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_MEMORIZATION_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ah.eval.g2" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "g2" not in module.split("."), module
            for alias in node.names:
                assert alias.name != "FinalEvaluationToken"


def test_memorization_module_never_imports_data_access() -> None:
    """TRAIN/VALIDATION (bare Split date boundaries) may be imported from ah.splits;
    DataAccess (a live read capability) must never be."""
    text = _MEMORIZATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_MEMORIZATION_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ah.splits":
            for alias in node.names:
                assert alias.name not in ("DataAccess", "FinalEvaluationToken")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "ah.splits"
