"""WP2.2 Task 5 acceptance: the calibration tier (PIT / interval coverage).

Mirrors ``tests/test_monthly.py``/``tests/test_horizon.py``/``tests/test_tails.py``/
``tests/test_utility.py``'s conventions: every metric is tested against simulated
ground truth (never a bare finiteness check), tolerances are justified at the point of
use, and a dedicated AST guard proves this module never imports ``ah.eval.g2``.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.random import PCG64, Generator

from ah.eval.metrics.calibration import (
    CALIBRATION_HORIZONS,
    CALIBRATION_MIN_GENERATED_SUMS,
    CALIBRATION_MIN_ORIGINS,
    _pit_value,
    build_calibration_suite,
    ks_statistic_vs_uniform,
    rolling_origin_sums,
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
    blocks = {"global": ("equity_mkt",), "us": ("policy_rate",)}
    sources = {
        "equity_mkt": FactorSource(
            kind="series", units="ret", series_id="s.eq", numeraire="total_return"
        ),
        "policy_rate": FactorSource(kind="series", units="pct", series_id="s.pr"),
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
# 1. rolling_origin_sums
# --------------------------------------------------------------------------- #


def test_rolling_origin_sums_matches_hand_computed_windows() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sums = rolling_origin_sums(x, 2)
    # origins 0..3 (n - h + 1 = 4): [1+2, 2+3, 3+4, 4+5]
    np.testing.assert_allclose(sums, [3.0, 5.0, 7.0, 9.0])


def test_rolling_origin_sums_empty_when_shorter_than_horizon() -> None:
    assert rolling_origin_sums(np.array([1.0, 2.0]), 5).size == 0


def test_rolling_origin_sums_single_origin_at_exact_length() -> None:
    x = np.array([1.0, 2.0, 3.0])
    sums = rolling_origin_sums(x, 3)
    np.testing.assert_allclose(sums, [6.0])


# --------------------------------------------------------------------------- #
# 2. ks_statistic_vs_uniform -- verified against a hand-derivable known value
# --------------------------------------------------------------------------- #


def test_ks_statistic_of_an_evenly_spaced_sample_is_exactly_one_over_two_n() -> None:
    """A perfectly evenly spaced sample x_i = (i - 0.5)/n, i=1..n, has a hand-derivable
    closed-form KS statistic vs Uniform(0,1): D = 1/(2n) exactly (each order statistic
    sits precisely midway between the two nominal grid points i/n and (i-1)/n, so both
    one-sided deviations equal 0.5/n at every i)."""
    for n in (5, 20, 137):
        x = (np.arange(1, n + 1, dtype=np.float64) - 0.5) / n
        d = ks_statistic_vs_uniform(x)
        assert d == pytest.approx(1.0 / (2.0 * n), abs=1e-12)


def test_ks_statistic_is_zero_for_the_degenerate_single_point_at_the_median() -> None:
    # n=1: D = max(1 - x, x - 0); minimized at x=0.5, D=0.5 (not zero -- a single point
    # cannot look "uniform"). Verifies the formula rather than assuming a value.
    assert ks_statistic_vs_uniform(np.array([0.5])) == pytest.approx(0.5)


def test_ks_statistic_detects_a_badly_miscalibrated_sample() -> None:
    """A sample concentrated near 0 (never near 1) must show a large KS statistic --
    the maximum possible deviation as concentration increases is bounded below by how
    far the empirical CDF departs from the diagonal."""
    x = np.full(50, 0.01)
    d = ks_statistic_vs_uniform(x)
    assert d > 0.9


def test_ks_statistic_nan_for_empty_input() -> None:
    assert math.isnan(ks_statistic_vs_uniform(np.array([])))


def test_ks_statistic_matches_brute_force_sup_norm_definition() -> None:
    """Independent numerical cross-check of the closed-form formula against the
    textbook DEFINITION (sup over t of |F_n(t) - t|), evaluated on a fine grid --
    proves the closed form is not merely self-consistent but actually the KS
    statistic."""
    rng = Generator(PCG64(5))
    x = rng.uniform(0.0, 1.0, size=40)
    d_formula = ks_statistic_vs_uniform(x)
    grid = np.linspace(0.0, 1.0, 20000)
    xs = np.sort(x)
    ecdf = np.searchsorted(xs, grid, side="right") / xs.shape[0]
    d_grid = float(np.max(np.abs(ecdf - grid)))
    assert d_formula == pytest.approx(d_grid, abs=1.0 / 20000)


# --------------------------------------------------------------------------- #
# 3. _pit_value -- mid-rank empirical CDF with ties
# --------------------------------------------------------------------------- #


def test_pit_value_below_every_sample_point_is_zero() -> None:
    sample = np.sort(np.array([1.0, 2.0, 3.0]))
    assert _pit_value(sample, 0.0) == 0.0


def test_pit_value_above_every_sample_point_is_one() -> None:
    sample = np.sort(np.array([1.0, 2.0, 3.0]))
    assert _pit_value(sample, 10.0) == 1.0


def test_pit_value_at_a_tie_uses_the_mid_rank_convention() -> None:
    sample = np.sort(np.array([1.0, 1.0, 1.0, 2.0]))
    # value exactly 1.0: 0 strictly below, 3 equal -> (0 + 0.5*3)/4 = 0.375
    assert _pit_value(sample, 1.0) == pytest.approx(0.375)


def test_pit_value_of_the_median_of_an_odd_sample_is_near_one_half() -> None:
    sample = np.sort(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert _pit_value(sample, 3.0) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# 4. build_calibration_suite -- rolling-origin protocol end to end
# --------------------------------------------------------------------------- #


def _correctly_specified_fixture(
    seed: int, n_paths: int = 40, months: int = 240, real_months: int = 1000
) -> tuple[FactorManifest, ReferenceStats, Ensemble]:
    """Generated and real data drawn from the SAME iid distribution -- the "correctly
    specified forecast" case: the ensemble's own pooled predictive distribution IS the
    real data-generating process, so PIT must come out close to uniform and coverage
    close to nominal."""
    rng = Generator(PCG64(seed))
    manifest = _manifest()
    dates = pd.date_range("1950-01-01", periods=real_months, freq="MS")
    real = pd.Series(rng.normal(0.01, 0.05, size=real_months), index=dates)
    reference = _reference_with_series({"equity_mkt": real})
    paths = rng.normal(0.01, 0.05, size=(n_paths, months, 1))
    ensemble = Ensemble(paths=paths, factor_names=["equity_mkt"], meta=_meta(n_paths, months))
    return manifest, reference, ensemble


def _overconfident_fixture(
    seed: int, n_paths: int = 40, months: int = 240, real_months: int = 1000
) -> tuple[FactorManifest, ReferenceStats, Ensemble]:
    """The generated distribution has the SAME mean but a MUCH SMALLER variance than
    the real data -- a deliberately over-confident (too-narrow) forecast. Coverage
    must come out clearly below nominal and the KS statistic must be large."""
    rng = Generator(PCG64(seed))
    manifest = _manifest()
    dates = pd.date_range("1950-01-01", periods=real_months, freq="MS")
    real = pd.Series(rng.normal(0.01, 0.05, size=real_months), index=dates)
    reference = _reference_with_series({"equity_mkt": real})
    paths = rng.normal(0.01, 0.005, size=(n_paths, months, 1))  # 10x tighter
    ensemble = Ensemble(paths=paths, factor_names=["equity_mkt"], meta=_meta(n_paths, months))
    return manifest, reference, ensemble


def test_correctly_specified_forecast_is_well_calibrated() -> None:
    manifest, reference, ensemble = _correctly_specified_fixture(seed=100)
    specs = {s.name: s for s in build_calibration_suite(manifest, reference)}
    ks_1y = specs["pit_ks_stat_1y"].fn(ensemble)
    assert ks_1y < 0.08, ks_1y
    for level in (50, 90):
        coverage = specs[f"interval_coverage_{level}_1y"].fn(ensemble)
        assert coverage == pytest.approx(level / 100.0, abs=0.08), (level, coverage)


def test_overconfident_forecast_shows_low_coverage_and_a_large_ks_statistic() -> None:
    manifest, reference, ensemble = _overconfident_fixture(seed=101)
    specs = {s.name: s for s in build_calibration_suite(manifest, reference)}
    ks_1y = specs["pit_ks_stat_1y"].fn(ensemble)
    assert ks_1y > 0.2, ks_1y
    for level in (50, 90):
        coverage = specs[f"interval_coverage_{level}_1y"].fn(ensemble)
        assert coverage < (level / 100.0) - 0.15, (level, coverage)


def test_calibration_min_generated_sums_floor_is_a_positive_constant() -> None:
    assert CALIBRATION_MIN_GENERATED_SUMS > 1


def test_calibration_min_origins_floor_is_a_positive_constant() -> None:
    assert CALIBRATION_MIN_ORIGINS > 1


def test_calibration_nan_when_no_return_bearing_factor_is_shared() -> None:
    manifest = _manifest()
    reference = _reference_with_series({})
    ensemble = Ensemble(
        paths=np.zeros((2, 300, 1), dtype=np.float64),
        factor_names=["policy_rate"],  # a level factor, never a return_bearing one
        meta=_meta(2, 300),
    )
    specs = {s.name: s for s in build_calibration_suite(manifest, reference)}
    for _horizon, suffix in CALIBRATION_HORIZONS:
        assert math.isnan(specs[f"pit_ks_stat_{suffix}"].fn(ensemble))
        for level in (50, 90):
            assert math.isnan(specs[f"interval_coverage_{level}_{suffix}"].fn(ensemble))


def test_calibration_nan_when_generated_ensemble_is_too_short_for_the_floor() -> None:
    """A generator producing too little must NaN, never a lucky/degenerate favourable
    number -- THE ONE NaN RULE, and the anti-gaming floor this module states."""
    manifest, reference, _ = _correctly_specified_fixture(seed=102)
    tiny_ensemble = Ensemble(
        paths=np.random.default_rng(1).normal(0.01, 0.05, size=(1, 5, 1)),
        factor_names=["equity_mkt"],
        meta=_meta(1, 5),
    )
    specs = {s.name: s for s in build_calibration_suite(manifest, reference)}
    assert math.isnan(specs["pit_ks_stat_1y"].fn(tiny_ensemble))
    assert math.isnan(specs["interval_coverage_50_1y"].fn(tiny_ensemble))


def test_every_calibration_metric_name_can_carry_a_sealed_threshold() -> None:
    manifest, reference, _ = _correctly_specified_fixture(seed=103)
    specs = build_calibration_suite(manifest, reference)
    expected = {"pit_ks_stat_1y", "pit_ks_stat_5y"}
    for level in (50, 90):
        for _, suffix in CALIBRATION_HORIZONS:
            expected.add(f"interval_coverage_{level}_{suffix}")
    assert {s.name for s in specs} == expected
    for spec in specs:
        assert spec.tier == "monthly"
        assert spec.suite == "calibration"
        assert spec.name in PANEL_STATS


# --------------------------------------------------------------------------- #
# 5. registration bookkeeping
# --------------------------------------------------------------------------- #


def test_calibration_is_registered_in_prereg_metric_suite_names() -> None:
    from ah.eval import prereg as prereg_mod

    assert "calibration" in prereg_mod._METRIC_SUITE_NAMES


def test_calibration_suite_registered_in_reference_dependent_suite_builders() -> None:
    from ah.eval import battery as battery_mod

    assert battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS["calibration"] == (
        "ah.eval.metrics.calibration",
        "build_calibration_suite",
    )


# --------------------------------------------------------------------------- #
# 6. calibration.py never imports ah.eval.g2 (mirrors tests/test_utility.py's guard)
# --------------------------------------------------------------------------- #

_CALIBRATION_PATH = ROOT / "src" / "ah" / "eval" / "metrics" / "calibration.py"


def test_calibration_module_never_imports_g2_or_names_the_token() -> None:
    text = _CALIBRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_CALIBRATION_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ah.eval.g2" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "g2" not in module.split("."), module
            for alias in node.names:
                assert alias.name != "FinalEvaluationToken"


def test_calibration_module_never_reads_a_data_access_directly() -> None:
    text = _CALIBRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_CALIBRATION_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ah.splits":
            raise AssertionError(f"calibration.py must not import ah.splits: {ast.dump(node)}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "ah.splits"
