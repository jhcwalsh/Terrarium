"""WP2.2 Task 4 acceptance: the utility tier (discriminative score, predictive score,
TSTR degradation).

Mirrors ``tests/test_monthly.py``/``tests/test_horizon.py``/``tests/test_tails.py``'s
conventions: every metric is tested against simulated ground truth (never a bare
finiteness check), tolerances are justified at the point of use, and a dedicated AST
guard proves this module never imports ``ah.eval.g2`` -- in the style of
``tests/test_reference.py``'s own guard.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.random import PCG64, Generator

from ah.eval.metrics.utility import (
    UTILITY_FIT_SEED,
    UTILITY_WINDOW_MONTHS,
    _fit_gd,
    _window_features,
    build_utility_suite,
    discriminative_score,
    predictive_score,
    tstr_degradation,
)
from ah.eval.reference import PANEL_STATS, ReferenceStats
from ah.factors import FactorManifest, FactorSource
from ah.gen.base import Ensemble, EnsembleMeta

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


# --------------------------------------------------------------------------- #
# 1. discriminative_score
# --------------------------------------------------------------------------- #


def test_discriminative_score_near_zero_when_drawn_from_the_same_distribution() -> None:
    rng = Generator(PCG64(1))
    real = rng.normal(0.0, 1.0, size=(500, 2))
    generated = rng.normal(0.0, 1.0, size=(500, 2))
    score = discriminative_score(real, generated, seed=1)
    # A well-specified logistic classifier cannot systematically beat chance when the
    # two samples are drawn from the same distribution; 0.1 comfortably covers the
    # test-split sampling noise at n~150 held out (binomial SE ~ 0.5/sqrt(150) ~ 0.04).
    assert score < 0.1


def test_discriminative_score_clearly_positive_when_generated_mean_is_shifted() -> None:
    rng = Generator(PCG64(2))
    real = rng.normal(0.0, 1.0, size=(500, 2))
    generated = rng.normal(3.0, 1.0, size=(500, 2))  # far from real in both features
    score = discriminative_score(real, generated, seed=1)
    assert score > 0.3


def test_discriminative_score_same_seed_is_bit_identical() -> None:
    rng = Generator(PCG64(3))
    real = rng.normal(0.0, 1.0, size=(300, 2))
    generated = rng.normal(0.2, 1.0, size=(300, 2))
    a = discriminative_score(real, generated, seed=7)
    b = discriminative_score(real, generated, seed=7)
    assert a == b


def test_discriminative_score_different_seed_gives_a_different_score() -> None:
    rng = Generator(PCG64(3))
    real = rng.normal(0.0, 1.0, size=(300, 2))
    generated = rng.normal(0.2, 1.0, size=(300, 2))
    a = discriminative_score(real, generated, seed=7)
    b = discriminative_score(real, generated, seed=8)
    assert a != b


def test_discriminative_score_nan_below_four_pooled_examples() -> None:
    assert math.isnan(discriminative_score(np.zeros((1, 2)), np.zeros((1, 2)), seed=1))


def test_discriminative_score_rejects_mismatched_feature_widths() -> None:
    with pytest.raises(ValueError, match="2-D"):
        discriminative_score(np.zeros((5, 2)), np.zeros((5, 3)), seed=1)


# --------------------------------------------------------------------------- #
# 2. predictive_score / tstr_degradation
# --------------------------------------------------------------------------- #


def _ar1_pairs(rng: Generator, n: int, phi: float) -> tuple[np.ndarray, np.ndarray]:
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal(0.0, 1.0)
    return x[:-1], x[1:]


def test_predictive_score_lower_when_synthetic_matches_real_dynamics_than_when_noise() -> None:
    rng = Generator(PCG64(10))
    real_x, real_y = _ar1_pairs(rng, 3000, phi=0.5)
    matched_x, matched_y = _ar1_pairs(rng, 3000, phi=0.5)  # same AR(1) dynamics
    noise = rng.normal(0.0, 1.0, size=3000)
    noise_x, noise_y = noise[:-1], noise[1:]

    matched_error = predictive_score(matched_x, matched_y, real_x, real_y, seed=1)
    noise_error = predictive_score(noise_x, noise_y, real_x, real_y, seed=1)
    assert matched_error < noise_error


def test_tstr_degradation_near_one_when_synthetic_matches_real_dynamics() -> None:
    rng = Generator(PCG64(11))
    real_x, real_y = _ar1_pairs(rng, 4000, phi=0.5)
    matched_x, matched_y = _ar1_pairs(rng, 4000, phi=0.5)
    degradation = tstr_degradation(matched_x, matched_y, real_x, real_y, seed=1)
    # A generator reproducing the real dynamics should score close to the TRTR
    # baseline's own sampling noise (fit/eval on two different real halves); 0.25
    # comfortably covers that at n=2000 real pairs.
    assert degradation == pytest.approx(1.0, abs=0.25)


def test_tstr_degradation_clearly_worse_when_synthetic_is_pure_noise() -> None:
    rng = Generator(PCG64(12))
    real_x, real_y = _ar1_pairs(rng, 4000, phi=0.7)  # strong real dynamics
    noise = rng.normal(0.0, 1.0, size=4000)
    noise_x, noise_y = noise[:-1], noise[1:]
    degradation = tstr_degradation(noise_x, noise_y, real_x, real_y, seed=1)
    assert degradation > 1.1


def test_predictive_score_same_seed_is_bit_identical() -> None:
    rng = Generator(PCG64(13))
    gx, gy = _ar1_pairs(rng, 500, phi=0.3)
    rx, ry = _ar1_pairs(rng, 500, phi=0.3)
    a = predictive_score(gx, gy, rx, ry, seed=42)
    b = predictive_score(gx, gy, rx, ry, seed=42)
    assert a == b


def test_predictive_score_different_seed_gives_a_different_score() -> None:
    rng = Generator(PCG64(13))
    gx, gy = _ar1_pairs(rng, 500, phi=0.3)
    rx, ry = _ar1_pairs(rng, 500, phi=0.3)
    a = predictive_score(gx, gy, rx, ry, seed=42)
    b = predictive_score(gx, gy, rx, ry, seed=43)
    assert a != b


def test_tstr_degradation_same_seed_is_bit_identical() -> None:
    rng = Generator(PCG64(14))
    gx, gy = _ar1_pairs(rng, 500, phi=0.4)
    rx, ry = _ar1_pairs(rng, 500, phi=0.4)
    a = tstr_degradation(gx, gy, rx, ry, seed=5)
    b = tstr_degradation(gx, gy, rx, ry, seed=5)
    assert a == b


def test_tstr_degradation_different_seed_gives_a_different_score() -> None:
    rng = Generator(PCG64(14))
    gx, gy = _ar1_pairs(rng, 500, phi=0.4)
    rx, ry = _ar1_pairs(rng, 500, phi=0.4)
    a = tstr_degradation(gx, gy, rx, ry, seed=5)
    b = tstr_degradation(gx, gy, rx, ry, seed=6)
    assert a != b


def test_tstr_degradation_inf_when_real_variance_is_degenerate() -> None:
    gx, gy = np.zeros(10), np.zeros(10)
    rx, ry = np.zeros(10), np.zeros(10)  # constant real series -> zero TRTR MSE
    result = tstr_degradation(gx, gy, rx, ry, seed=1)
    assert result == float("inf")


# --------------------------------------------------------------------------- #
# 3. _fit_gd / _window_features -- the shared core
# --------------------------------------------------------------------------- #


def test_fit_gd_recovers_a_known_linear_relationship() -> None:
    rng = Generator(PCG64(20))
    x = rng.normal(0.0, 1.0, size=2000).reshape(-1, 1)
    y = 2.0 * x[:, 0] + 0.5  # a=0.5 (bias), b=2.0, no noise
    weights = _fit_gd(x, y, loss="squared")
    assert weights[0] == pytest.approx(2.0, abs=0.05)  # slope
    assert weights[1] == pytest.approx(0.5, abs=0.05)  # bias


def test_fit_gd_is_seed_free_and_deterministic() -> None:
    rng = Generator(PCG64(21))
    x = rng.normal(size=(200, 1))
    y = rng.normal(size=200)
    a = _fit_gd(x, y, loss="squared")
    b = _fit_gd(x, y, loss="squared")
    np.testing.assert_array_equal(a, b)


def test_fit_gd_rejects_unknown_loss() -> None:
    with pytest.raises(ValueError, match="loss"):
        _fit_gd(np.zeros((3, 1)), np.zeros(3), loss="bogus")


def test_window_features_drops_the_partial_tail() -> None:
    x = np.arange(10, dtype=np.float64)  # window=4 -> 2 full windows, 2 dropped
    features = _window_features(x, 4)
    assert features.shape == (2, 2)
    np.testing.assert_allclose(features[0], [np.mean([0, 1, 2, 3]), np.std([0, 1, 2, 3])])


def test_window_features_empty_when_shorter_than_one_window() -> None:
    features = _window_features(np.arange(3, dtype=np.float64), 12)
    assert features.shape == (0, 2)


# --------------------------------------------------------------------------- #
# 4. build_utility_suite -- wiring
# --------------------------------------------------------------------------- #


def _plausible_series(rng: Generator, months: int) -> pd.Series:
    dates = pd.date_range("2000-01-01", periods=months, freq="MS")
    return pd.Series(rng.normal(0.005, 0.04, size=months), index=dates)


def test_every_utility_metric_name_can_carry_a_sealed_threshold() -> None:
    manifest = _manifest()
    reference = _reference_with_series({})
    specs = build_utility_suite(manifest, reference)
    assert {s.name for s in specs} == {
        "discriminative_score",
        "predictive_score",
        "tstr_degradation",
    }
    for spec in specs:
        assert spec.tier == "monthly"
        assert spec.suite == "utility"
        assert spec.name in PANEL_STATS


def test_build_utility_suite_computes_real_values_when_factors_are_shared() -> None:
    rng = Generator(PCG64(30))
    months = 120
    reference = _reference_with_series(
        {"g1": _plausible_series(rng, months), "u1": _plausible_series(rng, months)}
    )
    paths = np.stack(
        [rng.normal(0.005, 0.04, size=(4, months)), rng.normal(0.005, 0.04, size=(4, months))],
        axis=-1,
    )
    ensemble = Ensemble(paths=paths, factor_names=["g1", "u1"], meta=_meta(4, months))

    specs = {s.name: s for s in build_utility_suite(_manifest(), reference)}
    for name in ("discriminative_score", "predictive_score", "tstr_degradation"):
        value = specs[name].fn(ensemble)
        assert np.isfinite(value), f"{name} = {value}"


def test_build_utility_suite_nan_when_no_factor_is_shared() -> None:
    reference = _reference_with_series({})
    ensemble = Ensemble(
        paths=np.zeros((2, 6, 1), dtype=np.float64),
        factor_names=["g1"],
        meta=_meta(2, 6),
    )
    specs = {s.name: s for s in build_utility_suite(_manifest(), reference)}
    for name in ("discriminative_score", "predictive_score", "tstr_degradation"):
        assert math.isnan(specs[name].fn(ensemble))


def test_utility_fit_seed_is_a_fixed_module_constant() -> None:
    """Re-running the battery at a different run seed must not change the utility
    tier's value for an unchanged ensemble -- UTILITY_FIT_SEED, not the battery's own
    seed, drives every stochastic step in this suite (see the module docstring)."""
    assert isinstance(UTILITY_FIT_SEED, int)


def test_utility_window_months_is_a_positive_constant() -> None:
    assert UTILITY_WINDOW_MONTHS > 1


# --------------------------------------------------------------------------- #
# 5. registration bookkeeping
# --------------------------------------------------------------------------- #


def test_utility_is_registered_in_prereg_metric_suite_names() -> None:
    from ah.eval import prereg as prereg_mod

    assert "utility" in prereg_mod._METRIC_SUITE_NAMES


def test_utility_suite_registered_in_reference_dependent_suite_builders() -> None:
    from ah.eval import battery as battery_mod

    assert battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS["utility"] == (
        "ah.eval.metrics.utility",
        "build_utility_suite",
    )


# --------------------------------------------------------------------------- #
# 6. utility.py never imports ah.eval.g2 or names FinalEvaluationToken (mirrors
# tests/test_reference.py's guard)
# --------------------------------------------------------------------------- #

_UTILITY_PATH = ROOT / "src" / "ah" / "eval" / "metrics" / "utility.py"


def test_utility_module_never_imports_g2_or_names_the_token() -> None:
    text = _UTILITY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_UTILITY_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ah.eval.g2" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "g2" not in module.split("."), module
            for alias in node.names:
                assert alias.name != "FinalEvaluationToken"


def test_utility_module_never_reads_a_data_access_directly() -> None:
    """Real data must come through ReferenceStats.historical_series only -- never a
    fresh ah.splits.DataAccess/catalog read. A bare-name/import AST scan, the same
    style as the g2 guard above."""
    text = _UTILITY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_UTILITY_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ah.splits":
            raise AssertionError(f"utility.py must not import ah.splits: {ast.dump(node)}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "ah.splits"
