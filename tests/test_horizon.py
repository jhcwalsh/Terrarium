"""WP2.2 Task 3 acceptance: the 1-5yr and 10yr horizon tiers.

Mirrors ``tests/test_monthly.py``'s conventions: every metric is tested against a
closed-form or simulated ground truth (never against its own regression baseline), and
every metric reusing an ``ah.eval.reference`` definition is asserted to *agree* with it
on the same input. Tolerances are commented with their justification at the point of
use.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.random import PCG64, Generator

from ah.eval.battery import MetricSpec
from ah.eval.metrics.horizon import build_horizon_suite
from ah.eval.reference import (
    ReferenceStats,
    drawdown_episodes,
    ergodicity_gap,
    long_inflation_era_frequency,
    lost_decade_frequency,
    mean_reversion_halflife,
    spearman_rank_correlation,
    valuation_regression,
    variance_ratio,
)
from ah.factors import FactorManifest, FactorSource
from ah.gen.base import Ensemble, EnsembleMeta

# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


def _meta(n_paths: int, months: int) -> EnsembleMeta:
    return EnsembleMeta(
        generator_id="test-gen", vintage_id="v", seed=0, n_paths=n_paths, months=months
    )


def _one_factor_ensemble(values: np.ndarray, factor: str = "equity_mkt") -> Ensemble:
    n_paths, months = values.shape
    paths = values[:, :, None]
    return Ensemble(paths=paths, factor_names=[factor], meta=_meta(n_paths, months))


def _manifest() -> FactorManifest:
    """One block, factors covering both return-bearing and level classifications."""
    blocks = {"global": ("equity_mkt", "equity_vol"), "us": ("cpi",)}
    sources = {
        "equity_mkt": FactorSource(
            kind="series", units="ret", series_id="s.eq", numeraire="total_return"
        ),
        "equity_vol": FactorSource(kind="series", units="idx", series_id="s.vol"),
        "cpi": FactorSource(kind="series", units="index", series_id="s.cpi"),
    }
    return FactorManifest(blocks=blocks, active_blocks=("global", "us"), sources=sources)


def _empty_reference() -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=("global", "us"),
        vintage_id="v",
        n_resamples=1,
        seed=1,
        missing_factors=(),
    )


def _find_spec(specs: tuple[MetricSpec, ...], name: str) -> MetricSpec:
    for spec in specs:
        if spec.name == name:
            return spec
    raise AssertionError(f"no spec named {name!r} in {[s.name for s in specs]}")


# --------------------------------------------------------------------------- #
# 1. variance ratio -- iid ~1.0, >1 positively autocorrelated, <1 mean-reverting
# --------------------------------------------------------------------------- #


def test_variance_ratio_near_one_for_iid_returns() -> None:
    rng = Generator(PCG64(1))
    x = rng.normal(0.0, 0.02, size=2000)
    # Large-sample iid: variance ratio -> 1.0 exactly in expectation. 0.1 is generous
    # (variance ratio's own sampling noise at n=2000/k=12 is a few percent) but still
    # discriminates against a systematically wrong estimator (e.g. an extra factor of k).
    assert variance_ratio(x, 12) == pytest.approx(1.0, abs=0.1)


def test_variance_ratio_greater_than_one_for_positive_autocorrelation() -> None:
    rng = Generator(PCG64(2))
    n = 3000
    eps = rng.normal(0.0, 1.0, size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = 0.6 * x[t - 1] + eps[t]  # phi=0.6: strong positive persistence
    assert variance_ratio(x, 12) > 1.0


def test_variance_ratio_less_than_one_for_mean_reversion() -> None:
    rng = Generator(PCG64(3))
    n = 3000
    eps = rng.normal(0.0, 1.0, size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = -0.6 * x[t - 1] + eps[t]  # phi=-0.6: strong mean reversion
    assert variance_ratio(x, 12) < 1.0


def test_variance_ratio_metric_agrees_with_reference_and_pools_across_paths() -> None:
    """The wired ensemble metric pools non-overlapping sums ACROSS paths before
    taking the ratio -- not a per-path-ratio average. Two paths concatenated must give
    the identical ratio as one path formed by literally concatenating both arrays."""
    rng = Generator(PCG64(4))
    a = rng.normal(0.0, 0.02, size=120)
    b = rng.normal(0.0, 0.02, size=120)
    ensemble = _one_factor_ensemble(np.stack([a, b]))
    spec = _find_spec(
        build_horizon_suite(_manifest(), _empty_reference()), "equity_mkt.variance_ratio_12m"
    )
    pooled_direct = variance_ratio(
        np.concatenate([a[: (120 // 12) * 12], b[: (120 // 12) * 12]]), 12
    )
    # variance_ratio() itself windows non-overlapping sums from ONE flat array; the
    # metric must equal pooling the two paths' OWN non-overlapping sums, which -- since
    # 120 is an exact multiple of 12 -- is the same set of sums as windowing the
    # concatenation of the two (already-multiple-of-12) arrays.
    assert spec.fn(ensemble) == pytest.approx(pooled_direct, rel=1e-10)


def test_variance_ratio_rejects_bad_k() -> None:
    with pytest.raises(ValueError, match="k must be"):
        variance_ratio(np.arange(10.0), 0)


# --------------------------------------------------------------------------- #
# 2. mean-reversion half-life
# --------------------------------------------------------------------------- #


def test_halflife_recovers_known_phi_on_seeded_ar1() -> None:
    rng = Generator(PCG64(5))
    n = 5000
    phi = 0.9
    eps = rng.normal(0.0, 1.0, size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + eps[t]
    expected = np.log(0.5) / np.log(phi)
    value = mean_reversion_halflife(x)
    # Lag-1 sample ACF at n=5000 has small sampling error; half-life is a nonlinear
    # (and steep, near phi close to 1) transform of it, so a looser relative tolerance
    # is warranted -- 15% still discriminates a materially wrong estimator.
    assert value == pytest.approx(expected, rel=0.15)


def test_halflife_is_inf_when_phi_at_least_one() -> None:
    """The n-denominator ``_acf_at_lag`` estimator is bounded near +/-1 by
    Cauchy-Schwarz for any real finite series, so ``phi >= 1.0`` exactly is not a case
    genuine data can construct -- exercised directly, exactly as the phi==0 branch is,
    per the module's own precedent for testing a decided boundary behaviour."""
    import ah.eval.reference as ref

    original = ref._acf_at_lag
    try:
        ref._acf_at_lag = lambda x, lag: 1.0  # type: ignore[assignment]
        assert mean_reversion_halflife(np.arange(10.0)) == float("inf")
        ref._acf_at_lag = lambda x, lag: -1.5  # type: ignore[assignment]
        assert mean_reversion_halflife(np.arange(10.0)) == float("inf")
    finally:
        ref._acf_at_lag = original


def test_halflife_zero_phi_branch_directly() -> None:
    import ah.eval.reference as ref

    original = ref._acf_at_lag
    try:
        ref._acf_at_lag = lambda x, lag: 0.0  # type: ignore[assignment]
        assert mean_reversion_halflife(np.arange(10.0)) == 0.0
    finally:
        ref._acf_at_lag = original


def test_halflife_nan_when_acf_is_nan() -> None:
    assert np.isnan(mean_reversion_halflife(np.array([1.0])))


# --------------------------------------------------------------------------- #
# 3. drawdown episodes -- hand-built path with one known drawdown
# --------------------------------------------------------------------------- #


def test_drawdown_episode_depth_and_duration_are_exact_on_hand_built_path() -> None:
    # Wealth path: 1 -> 1.1 -> 0.99 -> 0.88 -> 0.968 -> 1.1616 (recovers past the
    # prior high of 1.1, ending the episode). Returns are the period-over-period pct
    # changes implied by that wealth path.
    wealth = np.array([1.0, 1.1, 0.99, 0.88, 0.968, 1.1616])
    returns = wealth[1:] / wealth[:-1] - 1.0
    depths, durations = drawdown_episodes(returns)
    # Drawdown series (running max of wealth-after-return-0 is 1.1 from month 0):
    # month0: dd=0 (wealth=1.1, new high); month1: dd = 0.99/1.1-1 = -0.10 (in episode);
    # month2: dd = 0.88/1.1-1 = -0.20 (trough); month3: dd = 0.968/1.1-1=-0.12;
    # month4: dd = 1.1616/1.1-1 = +0.056 -> clamped by cummax, dd=0 (new high, episode
    # ends). One episode: depth=0.20, duration=3 (months 1,2,3).
    assert depths.shape == (1,)
    assert durations.shape == (1,)
    assert depths[0] == pytest.approx(0.20, abs=1e-9)
    assert durations[0] == 3


def test_drawdown_episodes_empty_for_all_positive_returns() -> None:
    depths, durations = drawdown_episodes(np.array([0.01, 0.02, 0.03, 0.01]))
    assert depths.size == 0
    assert durations.size == 0


def test_drawdown_episode_still_open_at_series_end_is_counted() -> None:
    # A leading flat month establishes the initial peak (drawdown_state's running-max
    # convention treats month 0 of the RETURNS array as automatically "at its own
    # peak" -- a decline occurring in that very first return would otherwise be
    # invisible, since there is no prior point in the returns-only array to compare
    # it against). wealth: 1.0 -> 1.0 -> 0.9 -> 0.8, still underwater at the end.
    wealth = np.array([1.0, 1.0, 0.9, 0.8])
    returns = wealth[1:] / wealth[:-1] - 1.0
    depths, durations = drawdown_episodes(returns)
    assert depths.shape == (1,)
    assert durations[0] == 2
    assert depths[0] == pytest.approx(0.20, abs=1e-9)


def test_spearman_rank_correlation_hand_computed() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([10.0, 20.0, 30.0, 40.0])  # perfectly monotonic
    assert spearman_rank_correlation(a, b) == pytest.approx(1.0, abs=1e-12)
    assert spearman_rank_correlation(a, b[::-1]) == pytest.approx(-1.0, abs=1e-12)


def test_spearman_rank_correlation_nan_below_two_points() -> None:
    assert np.isnan(spearman_rank_correlation(np.array([1.0]), np.array([2.0])))


def test_drawdown_metrics_pool_episodes_across_paths_not_average_per_path() -> None:
    """Two paths, each with one drawdown episode of a different depth/duration: the
    pooled median over both episodes must differ from either path's own value alone,
    proving pooling by concatenation (not per-path mean of per-path medians, which
    here would give the same numeric answer by coincidence for 2 paths -- so this test
    also checks episode COUNT via the rank-correlation NaN floor)."""
    # Each starts with a leading flat month, for the same reason given in
    # test_drawdown_episode_still_open_at_series_end_is_counted above.
    wealth_a = np.array([1.0, 1.0, 0.9, 1.0])  # depth 0.10, duration 1
    wealth_b = np.array([1.0, 1.0, 0.9, 0.8, 0.7, 1.0])  # depth 0.30, duration 3
    returns_a = wealth_a[1:] / wealth_a[:-1] - 1.0
    returns_b = wealth_b[1:] / wealth_b[:-1] - 1.0
    n = max(returns_a.shape[0], returns_b.shape[0])
    padded_a = np.pad(returns_a, (0, n - returns_a.shape[0]))
    padded_b = np.pad(returns_b, (0, n - returns_b.shape[0]))
    ensemble = _one_factor_ensemble(np.stack([padded_a, padded_b]))
    specs = build_horizon_suite(_manifest(), _empty_reference())
    depth_spec = _find_spec(specs, "equity_mkt.drawdown_median_depth")
    duration_spec = _find_spec(specs, "equity_mkt.drawdown_median_duration")
    rank_spec = _find_spec(specs, "equity_mkt.drawdown_depth_duration_rank_corr")
    # Median of {0.10, 0.30} = 0.20; median of {1, 3} = 2.0; with exactly 2 pooled
    # points the rank correlation is always +/-1 (never NaN), confirming 2 episodes
    # were pooled, not 1.
    assert depth_spec.fn(ensemble) == pytest.approx(0.20, abs=1e-9)
    assert duration_spec.fn(ensemble) == pytest.approx(2.0, abs=1e-9)
    assert rank_spec.fn(ensemble) == pytest.approx(1.0, abs=1e-9)


def test_drawdown_metrics_not_registered_for_level_factors() -> None:
    """A level factor (equity_vol) must not carry drawdown/lost-decade specs -- see
    reference.py's drawdown_episodes docstring: compounding a level is not merely
    uninformative, it is numerically wrong."""
    specs = build_horizon_suite(_manifest(), _empty_reference())
    names = {s.name for s in specs}
    assert "equity_vol.drawdown_median_depth" not in names
    assert "equity_vol.lost_decade_frequency" not in names
    assert "equity_mkt.drawdown_median_depth" in names
    assert "equity_mkt.lost_decade_frequency" in names


# --------------------------------------------------------------------------- #
# 4. lost-decade frequency -- exact ratio on a constructed series
# --------------------------------------------------------------------------- #


def test_lost_decade_frequency_single_series_indicator() -> None:
    # A series whose whole compounded return is exactly 0: two +10%/-10%-ish months.
    gain_then_loss = np.array([0.1, -1.0 / 1.1])  # (1.1)*(1-1/1.1) = 0.0
    assert lost_decade_frequency(gain_then_loss) == pytest.approx(1.0)
    all_gains = np.array([0.01, 0.02, 0.03])
    assert lost_decade_frequency(all_gains) == 0.0


def test_lost_decade_frequency_nan_on_empty_series() -> None:
    assert np.isnan(lost_decade_frequency(np.array([])))


def test_lost_decade_frequency_pooled_across_paths_exact_ratio() -> None:
    """Constructed ensemble: exactly 2 of 5 paths are 'lost decades' (non-positive
    compounded return); the pooled frequency must be exactly 2/5."""
    lost = np.array([-0.01, -0.01, -0.01])  # compounds negative
    won = np.array([0.05, 0.05, 0.05])  # compounds positive
    paths = np.stack([lost, lost, won, won, won])
    ensemble = _one_factor_ensemble(paths)
    spec = _find_spec(
        build_horizon_suite(_manifest(), _empty_reference()), "equity_mkt.lost_decade_frequency"
    )
    assert spec.fn(ensemble) == pytest.approx(2.0 / 5.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 5. long-inflation-era frequency
# --------------------------------------------------------------------------- #


def test_long_inflation_era_frequency_detects_sustained_run() -> None:
    # ``derive.yoy`` consumes the first 12 months, so a run needs 12 + 24 = 36 months
    # of level data at minimum to clear the sealed 24-month floor; 40 gives headroom.
    # 0.6%/month compounds to ~7.2%/yr, comfortably above the 4.0 cpi_high threshold,
    # sustained for the entire post-warmup window.
    n = 12 + 40
    level = np.empty(n)
    level[0] = 100.0
    monthly_rate = 0.006
    for i in range(1, n):
        level[i] = level[i - 1] * (1.0 + monthly_rate)
    assert long_inflation_era_frequency(level) == 1.0


def test_long_inflation_era_frequency_zero_for_low_stable_inflation() -> None:
    n = 12 + 40
    level = np.empty(n)
    level[0] = 100.0
    for i in range(1, n):
        level[i] = level[i - 1] * (1.0 + 0.002)  # ~2.4%/yr, below cpi_high=4.0
    assert long_inflation_era_frequency(level) == 0.0


def test_long_inflation_era_frequency_nan_on_too_short_series() -> None:
    assert np.isnan(long_inflation_era_frequency(np.array([100.0, 101.0])))


def test_long_inflation_era_frequency_rejects_a_brief_spike() -> None:
    """A single hot print (well above threshold for a handful of months, not the
    sealed 24-month minimum run) must NOT count -- the min-duration floor is the
    point of the sealed definition, not merely the threshold level."""
    n = 12 + 40
    level = np.empty(n)
    level[0] = 100.0
    for i in range(1, n):
        # A brief 10-month spike to ~8%/yr around the midpoint, ~2%/yr otherwise.
        rate = 0.006 if 20 <= i < 30 else 0.0016
        level[i] = level[i - 1] * (1.0 + rate)
    assert long_inflation_era_frequency(level) == 0.0


def test_long_inflation_era_only_registered_for_cpi() -> None:
    specs = build_horizon_suite(_manifest(), _empty_reference())
    names = {s.name for s in specs}
    assert "cpi.long_inflation_era_frequency" in names
    assert "equity_mkt.long_inflation_era_frequency" not in names
    assert "equity_vol.long_inflation_era_frequency" not in names


# --------------------------------------------------------------------------- #
# 6. valuation regression -- recovers a known slope
# --------------------------------------------------------------------------- #


def test_valuation_regression_recovers_known_slope() -> None:
    rng = Generator(PCG64(6))
    n = 500
    cape_v = rng.normal(0.0, 1.0, size=n)
    true_slope = -0.05
    noise = rng.normal(0.0, 0.001, size=n)  # tiny noise -> near-perfect R^2
    forward_return = 0.08 + true_slope * cape_v + noise
    slope, r2 = valuation_regression(cape_v, forward_return)
    assert slope == pytest.approx(true_slope, rel=0.02)
    assert r2 == pytest.approx(1.0, abs=0.01)


def test_valuation_regression_nan_on_constant_cape() -> None:
    slope, r2 = valuation_regression(np.ones(10), np.arange(10.0))
    assert np.isnan(slope)
    assert np.isnan(r2)


def test_valuation_regression_nan_below_three_points() -> None:
    slope, r2 = valuation_regression(np.array([1.0, 2.0]), np.array([1.0, 2.0]))
    assert np.isnan(slope)
    assert np.isnan(r2)


# --------------------------------------------------------------------------- #
# 7. ergodicity gap -- ~0 for stationary iid, clearly non-zero for a trend
# --------------------------------------------------------------------------- #


def test_ergodicity_gap_near_zero_for_stationary_iid_paths() -> None:
    rng = Generator(PCG64(7))
    paths = rng.normal(0.0, 1.0, size=(500, 60))
    value = ergodicity_gap(paths)
    # Both sides of the ratio are themselves noisy sample-variance estimates at
    # n_paths=500/months=60; 0.5 (a 50% relative gap) is generous but still clearly
    # separates this from the trend case below (which is orders of magnitude larger).
    assert value == pytest.approx(0.0, abs=0.5)


def test_ergodicity_gap_clearly_nonzero_for_a_deliberate_trend() -> None:
    """A deliberate per-path persistent bias -- each path drawn once from a WIDE
    distribution and held fixed for its whole length, as if each path got "stuck" in
    a different long-run regime for its entire 60 months (DN-1.1's non-ergodicity
    concern in its starkest form). This inflates the cross-sectional dispersion of
    per-path time-averages (``dispersion``) far ABOVE what pooled variance / months
    predicts under an iid-within-path null (``expected_dispersion``), the opposite
    direction from the iid case, and unambiguously far from it."""
    rng = Generator(PCG64(8))
    n_paths, months = 200, 60
    per_path_bias = rng.normal(0.0, 5.0, size=(n_paths, 1))
    noise = rng.normal(0.0, 0.1, size=(n_paths, months))
    paths = per_path_bias + noise
    value = ergodicity_gap(paths)
    assert value > 2.0  # a large, unambiguous gap vs. the near-zero iid case


def test_ergodicity_gap_rejects_wrong_ndim() -> None:
    with pytest.raises(ValueError, match="2-D"):
        ergodicity_gap(np.arange(10.0))


def test_ergodicity_gap_nan_for_degenerate_ensemble() -> None:
    assert np.isnan(ergodicity_gap(np.ones((5, 10))))


def test_ergodicity_gap_reference_side_is_always_nan() -> None:
    """No historical analog: a flat historical series has one path, so the
    registered reference-side ``fn`` for this stat must be NaN, not a fabricated
    point (see reference.py's ``_ergodicity_gap_reference_stub``)."""
    from ah.eval.reference import SINGLE_FACTOR_STATS

    assert np.isnan(SINGLE_FACTOR_STATS["ergodicity_gap"].fn(np.arange(100.0)))


# --------------------------------------------------------------------------- #
# 8. structural gaps -- always NaN, never gamed
# --------------------------------------------------------------------------- #


def test_regime_duration_metrics_are_structurally_nan() -> None:
    specs = build_horizon_suite(_manifest(), _empty_reference())
    ensemble = _one_factor_ensemble(np.zeros((3, 24)))
    for name in ("regime_duration_mean", "regime_duration_p50", "regime_duration_p90"):
        spec = _find_spec(specs, name)
        assert np.isnan(spec.fn(ensemble))
        assert spec.tier == "1_5yr"


def test_valuation_slope_r2_metrics_are_structurally_nan() -> None:
    specs = build_horizon_suite(_manifest(), _empty_reference())
    ensemble = _one_factor_ensemble(np.zeros((3, 24)))
    for name in ("ten_year_return_vs_valuation_slope", "ten_year_return_vs_valuation_r2"):
        spec = _find_spec(specs, name)
        assert np.isnan(spec.fn(ensemble))
        assert spec.tier == "10yr"


def test_absent_factor_is_nan_not_a_smaller_number() -> None:
    """A factor omitted from an ensemble entirely must NaN every metric registered
    under it -- never a suspiciously smaller/better number (Task 2's gaming lesson)."""
    manifest = _manifest()
    specs = build_horizon_suite(manifest, _empty_reference())
    # An ensemble that carries only "cpi", omitting "equity_mkt" entirely.
    ensemble = Ensemble(paths=np.zeros((3, 24, 1)), factor_names=["cpi"], meta=_meta(3, 24))
    for spec in specs:
        if spec.name.startswith("equity_mkt."):
            assert np.isnan(spec.fn(ensemble)), spec.name


# --------------------------------------------------------------------------- #
# 9. tier assignment -- DN-1.1 Sec.II.6 is normative
# --------------------------------------------------------------------------- #


def test_every_metric_is_registered_at_its_dn1_1_tier() -> None:
    specs = build_horizon_suite(_manifest(), _empty_reference())
    by_stat: dict[str, set[str]] = {}
    for spec in specs:
        stat = spec.name.split(".", 1)[1] if "." in spec.name else spec.name
        by_stat.setdefault(stat, set()).add(spec.tier)
    tier_1_5yr = {
        "variance_ratio_12m",
        "variance_ratio_36m",
        "variance_ratio_60m",
        "variance_ratio_120m",
        "mean_reversion_halflife",
        "drawdown_median_depth",
        "drawdown_median_duration",
        "drawdown_depth_duration_rank_corr",
        "regime_duration_mean",
        "regime_duration_p50",
        "regime_duration_p90",
    }
    tier_10yr = {
        "lost_decade_frequency",
        "long_inflation_era_frequency",
        "ten_year_return_vs_valuation_slope",
        "ten_year_return_vs_valuation_r2",
        "ergodicity_gap",
    }
    for stat in tier_1_5yr:
        assert by_stat[stat] == {"1_5yr"}, stat
    for stat in tier_10yr:
        assert by_stat[stat] == {"10yr"}, stat
    assert not (tier_1_5yr & tier_10yr)


def test_no_metric_is_registered_at_monthly_tier() -> None:
    specs = build_horizon_suite(_manifest(), _empty_reference())
    assert all(s.tier in ("1_5yr", "10yr") for s in specs)
