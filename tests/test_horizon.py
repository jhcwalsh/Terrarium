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
from ah.eval.metrics.horizon import REGIME_RULESET_VERSION, build_horizon_suite
from ah.eval.reference import (
    DRAWDOWN_MIN_EPISODES,
    LONG_INFLATION_ERA_WINDOW_MONTHS,
    LOST_DECADE_WINDOW_MONTHS,
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


def test_halflife_is_inf_when_phi_at_least_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The n-denominator ``_acf_at_lag`` estimator is bounded near +/-1 by
    Cauchy-Schwarz for any real finite series, so ``phi >= 1.0`` exactly is not a case
    genuine data can construct -- exercised directly, exactly as the phi==0 branch is,
    per the module's own precedent for testing a decided boundary behaviour."""
    import ah.eval.reference as ref

    monkeypatch.setattr(ref, "_acf_at_lag", lambda x, lag: 1.0)
    assert mean_reversion_halflife(np.arange(10.0)) == float("inf")
    monkeypatch.setattr(ref, "_acf_at_lag", lambda x, lag: -1.5)
    assert mean_reversion_halflife(np.arange(10.0)) == float("inf")


def test_halflife_zero_phi_branch_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    import ah.eval.reference as ref

    monkeypatch.setattr(ref, "_acf_at_lag", lambda x, lag: 0.0)
    assert mean_reversion_halflife(np.arange(10.0)) == 0.0


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


def _shallow_episode_returns() -> np.ndarray:
    """One drawdown episode: depth 0.10, duration 1 month."""
    wealth = np.array([1.0, 1.0, 0.9, 1.0])  # leading flat month establishes the peak
    return wealth[1:] / wealth[:-1] - 1.0


def _deep_episode_returns() -> np.ndarray:
    """One drawdown episode: depth 0.30, duration 3 months."""
    wealth = np.array([1.0, 1.0, 0.9, 0.8, 0.7, 1.0])
    return wealth[1:] / wealth[:-1] - 1.0


def _drawdown_ensemble(n_shallow: int, n_deep: int) -> Ensemble:
    """``n_shallow`` one-episode shallow paths plus ``n_deep`` one-episode deep ones."""
    shallow, deep = _shallow_episode_returns(), _deep_episode_returns()
    n = max(shallow.shape[0], deep.shape[0])
    rows = [np.pad(shallow, (0, n - shallow.shape[0]))] * n_shallow
    rows += [np.pad(deep, (0, n - deep.shape[0]))] * n_deep
    return _one_factor_ensemble(np.stack(rows))


def test_drawdown_metrics_pool_episodes_across_paths_not_average_per_path() -> None:
    """Paths each carrying one drawdown episode of a different depth/duration: the
    pooled median over ALL episodes must differ from either path's own value alone,
    proving pooling by concatenation (not a per-path mean of per-path medians)."""
    ensemble = _drawdown_ensemble(n_shallow=5, n_deep=5)
    specs = build_horizon_suite(_manifest(), _empty_reference())
    depth_spec = _find_spec(specs, "equity_mkt.drawdown_median_depth")
    duration_spec = _find_spec(specs, "equity_mkt.drawdown_median_duration")
    rank_spec = _find_spec(specs, "equity_mkt.drawdown_depth_duration_rank_corr")
    # Pooled episodes: five of (0.10, 1) and five of (0.30, 3). Median depth is the
    # mean of the 5th and 6th order statistics = (0.10 + 0.30)/2 = 0.20; median
    # duration = (1 + 3)/2 = 2.0; depth and duration are perfectly co-monotonic so the
    # rank correlation is exactly +1.
    assert depth_spec.fn(ensemble) == pytest.approx(0.20, abs=1e-9)
    assert duration_spec.fn(ensemble) == pytest.approx(2.0, abs=1e-9)
    assert rank_spec.fn(ensemble) == pytest.approx(1.0, abs=1e-9)


def test_drawdown_metrics_nan_below_the_pooled_episode_floor() -> None:
    """IMPORTANT 3. A generator whose paths mostly never draw down contributes no
    episodes from those paths and would otherwise be scored on the handful that did --
    a median from one or two pooled episodes was legal. Below
    ``DRAWDOWN_MIN_EPISODES`` pooled episodes the metric is NaN, so generating less
    cannot buy a favourable number."""
    specs = build_horizon_suite(_manifest(), _empty_reference())
    below = _drawdown_ensemble(n_shallow=DRAWDOWN_MIN_EPISODES - 1, n_deep=0)
    at_floor = _drawdown_ensemble(n_shallow=DRAWDOWN_MIN_EPISODES, n_deep=0)
    for name in (
        "equity_mkt.drawdown_median_depth",
        "equity_mkt.drawdown_median_duration",
        "equity_mkt.drawdown_depth_duration_rank_corr",
    ):
        spec = _find_spec(specs, name)
        assert np.isnan(spec.fn(below)), name
    # At the floor the depth/duration medians are computable again (the rank
    # correlation is legitimately NaN here: every episode is identical, so both rank
    # vectors are constant and the correlation is undefined).
    assert _find_spec(specs, "equity_mkt.drawdown_median_depth").fn(at_floor) == pytest.approx(0.10)
    assert _find_spec(specs, "equity_mkt.drawdown_median_duration").fn(at_floor) == pytest.approx(
        1.0
    )


def test_drawdown_episodes_are_nan_not_absent_when_compounding_overflows() -> None:
    """IMPORTANT 3, the worse half. ``wealth/cummax`` overflows to ``inf/inf = nan``
    and ``nan < 0.0`` is ``False``, so an overflowed path used to be silently recorded
    as having NO drawdowns -- the FAVOURABLE answer -- and dropped from the pooled
    concatenation entirely. It must NaN the metric instead."""
    returns = np.full(24, 1e300)
    depths, durations = drawdown_episodes(returns)
    assert depths.size == durations.size
    assert depths.size > 0, "an overflowed path must not report 'no drawdowns'"
    assert np.isnan(depths).all()
    assert np.isnan(durations).all()


def test_one_overflowed_path_nans_the_pooled_drawdown_metrics() -> None:
    """The pooled metric must not quietly average over the paths that stayed finite."""
    good = _drawdown_ensemble(n_shallow=DRAWDOWN_MIN_EPISODES + 5, n_deep=0)
    slab = good.paths[:, :, 0].copy()
    slab[0, :] = 1e300  # one adversarial path overflows the compounding
    poisoned = _one_factor_ensemble(slab)
    specs = build_horizon_suite(_manifest(), _empty_reference())
    for name in ("equity_mkt.drawdown_median_depth", "equity_mkt.drawdown_median_duration"):
        spec = _find_spec(specs, name)
        assert not np.isnan(spec.fn(good)), name
        assert np.isnan(spec.fn(poisoned)), name


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


def test_lost_decade_frequency_is_all_or_nothing_on_uniform_decades() -> None:
    """The two saturating cases, on inputs exactly one decade long (one window)."""
    # Exactly one 120-month window, compounding to exactly 0.0 total return.
    gain_then_loss = np.zeros(LOST_DECADE_WINDOW_MONTHS)
    gain_then_loss[0] = 0.1
    gain_then_loss[1] = -1.0 / 1.1  # (1.1)*(1 - 1/1.1) = 1.0 -> total return 0.0
    assert lost_decade_frequency(gain_then_loss) == pytest.approx(1.0)
    assert lost_decade_frequency(np.full(LOST_DECADE_WINDOW_MONTHS, 0.01)) == 0.0


def test_lost_decade_frequency_counts_a_fraction_of_decade_windows() -> None:
    """A FREQUENCY, not a 0/1 indicator: the fraction of the input's own overlapping
    120-month windows whose compounded total return is non-positive.

    Ground truth is closed form, not a re-implementation. The series is 120 months of
    exactly +1% followed by 120 months of exactly -1%, so window ``s`` (s = 0..120,
    121 windows in a 240-month series) carries ``120 - s`` gains and ``s`` losses and
    compounds to ``1.01**(120-s) * 0.99**s``. That is <= 1 exactly when
    ``(120 - s)*ln(1.01) + s*ln(0.99) <= 0``, i.e. ``s >= 120*ln(1.01)/(ln(1.01) -
    ln(0.99)) = 59.75``, so windows s = 60..120 are lost decades: 61 of 121.
    """
    returns = np.concatenate([np.full(120, 0.01), np.full(120, -0.01)])
    assert lost_decade_frequency(returns) == pytest.approx(61.0 / 121.0, rel=1e-12)


def test_lost_decade_frequency_nan_below_one_full_decade() -> None:
    """A decade is the unit of the statistic: fewer than 120 months carries no window
    at all, and NaN (not a value computed from a shorter, easier window) is the honest
    answer."""
    assert np.isnan(lost_decade_frequency(np.array([])))
    assert np.isnan(lost_decade_frequency(np.full(LOST_DECADE_WINDOW_MONTHS - 1, 0.01)))


def test_lost_decade_frequency_nan_when_compounding_overflows() -> None:
    """An overflowing compounded return must NaN the statistic, never report the
    FAVOURABLE 'not a lost decade' answer (``inf <= 0`` is ``False``)."""
    returns = np.full(LOST_DECADE_WINDOW_MONTHS, 1e300)
    assert np.isnan(lost_decade_frequency(returns))


def test_lost_decade_frequency_pooled_across_paths_exact_ratio() -> None:
    """Constructed ensemble: exactly 2 of 5 production-length (120-month) paths are
    'lost decades'; each path carries exactly one decade window, so the pooled
    frequency must be exactly 2/5."""
    lost = np.full(LOST_DECADE_WINDOW_MONTHS, -0.01)  # compounds negative
    won = np.full(LOST_DECADE_WINDOW_MONTHS, 0.05)  # compounds positive
    paths = np.stack([lost, lost, won, won, won])
    ensemble = _one_factor_ensemble(paths)
    spec = _find_spec(
        build_horizon_suite(_manifest(), _empty_reference()), "equity_mkt.lost_decade_frequency"
    )
    assert spec.fn(ensemble) == pytest.approx(2.0 / 5.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 5. long-inflation-era frequency
# --------------------------------------------------------------------------- #


def _cpi_level(rates: np.ndarray) -> np.ndarray:
    """A CPI index level built by compounding ``rates`` month by month from 100.0."""
    level = np.empty(rates.shape[0] + 1)
    level[0] = 100.0
    for i, rate in enumerate(rates):
        level[i + 1] = level[i] * (1.0 + rate)
    return level


def test_long_inflation_era_frequency_detects_sustained_run() -> None:
    # Exactly one decade window (120 level months). 0.6%/month compounds to ~7.4%/yr,
    # comfortably above the 4.0 cpi_high threshold, sustained across the whole
    # post-warmup part of the window, so that one window scores 1.0.
    level = _cpi_level(np.full(LONG_INFLATION_ERA_WINDOW_MONTHS - 1, 0.006))
    assert long_inflation_era_frequency(level) == 1.0


def test_long_inflation_era_frequency_zero_for_low_stable_inflation() -> None:
    level = _cpi_level(np.full(LONG_INFLATION_ERA_WINDOW_MONTHS - 1, 0.002))  # ~2.4%/yr
    assert long_inflation_era_frequency(level) == 0.0


def test_long_inflation_era_frequency_nan_below_one_full_decade() -> None:
    assert np.isnan(long_inflation_era_frequency(np.array([100.0, 101.0])))
    assert np.isnan(
        long_inflation_era_frequency(
            _cpi_level(np.full(LONG_INFLATION_ERA_WINDOW_MONTHS - 2, 0.006))
        )
    )


def test_long_inflation_era_frequency_counts_a_fraction_of_decade_windows() -> None:
    """A FREQUENCY, not a 0/1 indicator: with a high-inflation era confined to the
    first half of a 240-month series, some decade windows contain it and some do not,
    so the answer must be strictly between 0 and 1 -- a value a single whole-series
    indicator could never produce."""
    rates = np.where(np.arange(239) < 120, 0.006, 0.0016)
    value = long_inflation_era_frequency(_cpi_level(rates))
    assert 0.0 < value < 1.0


def test_long_inflation_era_frequency_rejects_a_brief_spike() -> None:
    """A single hot print (well above threshold for a handful of months, not the
    sealed 24-month minimum run) must NOT count -- the min-duration floor is the
    point of the sealed definition, not merely the threshold level."""
    # One decade window; a brief 10-month spike to ~7.4%/yr in its middle, ~2%/yr
    # otherwise. The spike clears cpi_high but never the 24-month run floor.
    idx = np.arange(LONG_INFLATION_ERA_WINDOW_MONTHS - 1)
    rates = np.where((idx >= 40) & (idx < 50), 0.006, 0.0016)
    assert long_inflation_era_frequency(_cpi_level(rates)) == 0.0


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


def _ar1(rng: Generator, n: int, phi: float, sigma: float = 1.0) -> np.ndarray:
    """One stationary AR(1) path, started from its own stationary distribution."""
    x = np.empty(n)
    x[0] = rng.normal(0.0, sigma / np.sqrt(1.0 - phi**2))
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal(0.0, sigma)
    return x


def test_ergodicity_gap_near_zero_when_a_long_path_matches_the_ensemble() -> None:
    """DN-1.1 Sec.II.6's definition: LONG-PATH time average vs ENSEMBLE cross-sectional
    average. Both are drawn from the same stationary process, so the two agree and the
    gap is ~0."""
    rng = Generator(PCG64(7))
    long_path = rng.normal(0.0, 1.0, size=6000)
    ensemble_paths = rng.normal(0.0, 1.0, size=(500, 120))
    assert ergodicity_gap(long_path, ensemble_paths) == pytest.approx(0.0, abs=0.1)


def test_ergodicity_gap_near_zero_for_a_persistent_but_ergodic_process() -> None:
    """The null this metric is judged against must NOT be iid-within-path. A stationary
    AR(1) with phi=0.9 is strongly persistent and perfectly ergodic; the previous
    Var(pooled)/months null made it read ~18 (catastrophically non-ergodic) for a
    CORRECT generator. Under the long-path-vs-ensemble definition it reads ~0."""
    rng = Generator(PCG64(70))
    long_path = _ar1(rng, 40000, phi=0.9)
    ensemble_paths = np.stack([_ar1(rng, 120, phi=0.9) for _ in range(400)])
    # Both averages estimate the same population mean 0 in units of the process's own
    # pooled dispersion; the residual is pure sampling noise from the ensemble's own
    # 400 x 120 draw and the long path's finite length.
    assert ergodicity_gap(long_path, ensemble_paths) < 0.2


def test_ergodicity_gap_clearly_nonzero_when_the_long_path_is_stuck_in_one_regime() -> None:
    """Genuine non-ergodicity: the ensemble mixes two long-run regimes, while a single
    long realization stays in one of them forever, so its time average never converges
    to the ensemble average. That is exactly the failure DN-1.1's row names."""
    rng = Generator(PCG64(8))
    long_path = rng.normal(5.0, 0.5, size=6000)  # stuck in the high regime
    regimes = np.where(rng.integers(0, 2, size=(400, 1)) == 0, -5.0, 5.0)
    ensemble_paths = regimes + rng.normal(0.0, 0.5, size=(400, 120))
    assert ergodicity_gap(long_path, ensemble_paths) > 0.5


def test_ergodicity_gap_rejects_wrong_ndim() -> None:
    with pytest.raises(ValueError, match="2-D"):
        ergodicity_gap(np.arange(10.0), np.arange(10.0))
    with pytest.raises(ValueError, match="1-D"):
        ergodicity_gap(np.ones((2, 3)), np.ones((2, 3)))


def test_ergodicity_gap_nan_for_degenerate_ensemble() -> None:
    assert np.isnan(ergodicity_gap(np.ones(50), np.ones((5, 10))))


def test_ergodicity_gap_reference_side_is_always_nan() -> None:
    """No historical analog: history is ONE realization and there is no historical
    ensemble to compare it against, so the registered reference-side ``fn`` for this
    stat must be NaN, not a fabricated point."""
    from ah.eval.reference import SINGLE_FACTOR_STATS

    assert np.isnan(SINGLE_FACTOR_STATS["ergodicity_gap"].fn(np.arange(100.0)))


def test_ergodicity_gap_metric_is_structurally_unavailable_not_a_second_variance_ratio() -> None:
    """CRITICAL 2. The previous ensemble-side ``ergodicity_gap`` was algebraically
    ``|variance_ratio_120m - 1|`` at production path length -- two sealed names for one
    number, the exact duplication this suite already refused for ``agg_gaussianity``
    horizon 1. It is now DN-1.1's long-path-vs-ensemble comparison, which the battery
    cannot evaluate because it is handed one ``Ensemble`` of production-length paths
    and no long path: the metric is NaN and MARKED as structurally unavailable, so a
    WP2.3 reader cannot mistake it for a generator failure."""
    rng = Generator(PCG64(9))
    paths = rng.normal(0.0, 0.04, size=(40, 120))
    ensemble = _one_factor_ensemble(paths)
    specs = build_horizon_suite(_manifest(), _empty_reference())
    gap_spec = _find_spec(specs, "equity_mkt.ergodicity_gap")
    vr_spec = _find_spec(specs, "equity_mkt.variance_ratio_120m")

    value = gap_spec.fn(ensemble)
    assert np.isnan(value)
    assert gap_spec.status == "structurally_unavailable"
    # And the number it used to be is genuinely computable here -- proving the old
    # metric had a real value to duplicate, so this is a removed duplicate rather than
    # a metric that never worked.
    assert not np.isnan(vr_spec.fn(ensemble))


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


def test_valuation_metrics_activate_with_cape_v_active() -> None:
    """Campaign-2: with cape_v + equity_mkt active, the RFR-18 gap CLOSES -- the
    two valuation metrics compute (verified against an exact linear ground truth)
    instead of marking structurally-unavailable NaN."""
    blocks = {"global": ("equity_mkt",), "valuation": ("cape_v",)}
    sources = {
        "equity_mkt": FactorSource(
            kind="series", units="ret", series_id="s.eq", numeraire="total_return"
        ),
        "cape_v": FactorSource(
            kind="derived", units="log", expr="demeaned_log_cape", inputs=("s.cape",)
        ),
    }
    manifest = FactorManifest(blocks=blocks, active_blocks=("global", "valuation"), sources=sources)
    specs = build_horizon_suite(manifest, _empty_reference())
    slope = _find_spec(specs, "ten_year_return_vs_valuation_slope")
    r2 = _find_spec(specs, "ten_year_return_vs_valuation_r2")
    assert slope.status == "ok" and r2.status == "ok"

    rng = np.random.Generator(np.random.PCG64(7))
    n = 128
    cape0 = rng.normal(0.0, 0.5, n)
    decade_return = 0.5 - 0.8 * cape0  # exact linear law: slope -0.8, R^2 1.0
    monthly = (1.0 + decade_return) ** (1.0 / 120.0) - 1.0
    paths = np.zeros((n, 120, 2))
    paths[:, :, 0] = monthly[:, None]  # equity_mkt: constant monthly compounding
    paths[:, :, 1] = cape0[:, None]  # cape_v: starting valuation, held flat
    ensemble = Ensemble(paths=paths, factor_names=["equity_mkt", "cape_v"], meta=_meta(n, 120))
    np.testing.assert_allclose(slope.fn(ensemble), -0.8, atol=1e-9)
    np.testing.assert_allclose(r2.fn(ensemble), 1.0, atol=1e-9)

    short = Ensemble(
        paths=paths[:, :60, :], factor_names=["equity_mkt", "cape_v"], meta=_meta(n, 60)
    )
    assert np.isnan(slope.fn(short))  # no full decade window -> NaN, not a guess


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


# --------------------------------------------------------------------------- #
# 10. structural gaps are MACHINE-VISIBLE, not just NaN
# --------------------------------------------------------------------------- #


def test_every_structural_gap_metric_is_marked_and_no_other_metric_is() -> None:
    """A bare NaN is byte-identical in the report to a genuine generator failure, and
    under THE ONE NaN RULE an ``enforce`` threshold on a structurally unavailable
    metric would fail every run forever. The marker is what lets a WP2.3 reader tell
    the two apart."""
    specs = build_horizon_suite(_manifest(), _empty_reference())
    marked = {s.name for s in specs if s.status == "structurally_unavailable"}
    assert marked == {
        "regime_duration_mean",
        "regime_duration_p50",
        "regime_duration_p90",
        "ten_year_return_vs_valuation_slope",
        "ten_year_return_vs_valuation_r2",
        "equity_mkt.ergodicity_gap",
        "equity_vol.ergodicity_gap",
        "cpi.ergodicity_gap",
    }
    assert all(s.status == "ok" for s in specs if s.name not in marked)


def test_regime_ruleset_version_reaches_the_metric_metadata() -> None:
    """WP2.6 refits on these labels and the plan requires the ruleset version be
    traceable: a module-level constant nothing reads is not traceability. It must be
    on the spec (and so in the report), not only in ``horizon.py``."""
    specs = build_horizon_suite(_manifest(), _empty_reference())
    for name in ("regime_duration_mean", "regime_duration_p50", "regime_duration_p90"):
        spec = _find_spec(specs, name)
        assert dict(spec.metadata)["regime_ruleset_version"] == REGIME_RULESET_VERSION
