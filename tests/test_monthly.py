"""WP2.2 Task 2 acceptance: the monthly-tier stylized-fact panel.

Every metric is tested against a closed-form or simulated ground truth (never against
its own regression baseline), and every metric reusing an ``ah.eval.reference``
definition is asserted to *agree* with it on the same input -- not merely to look
similar. Tolerances are commented with their justification at the point of use.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest
from numpy.random import PCG64, Generator

from ah.eval import battery
from ah.eval.battery import MetricSpec, run_battery
from ah.eval.metrics.monthly import (
    _acf_at_lag,
    _fit_exp_decay_rate,
    _leverage_one_path,
    _paired_corr_matrices,
    acf_abs_decay,
    agg_gaussianity,
    build_monthly_suite,
    corr_matrix_distance,
    hill_tail_index,
    register_monthly_suite,
)
from ah.eval.reference import (
    CrossBlockReference,
    ReferenceStats,
    StatBand,
    _acf1,
    _crisis_corr_lift,
    _excess_kurtosis,
    _skew,
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


def _one_factor_ensemble(values: np.ndarray, factor: str = "g1") -> Ensemble:
    """``values`` shape ``(n_paths, months)`` -> a one-factor Ensemble."""
    n_paths, months = values.shape
    paths = values[:, :, None]
    return Ensemble(paths=paths, factor_names=[factor], meta=_meta(n_paths, months))


def _two_factor_ensemble(
    a: np.ndarray, b: np.ndarray, names: tuple[str, str] = ("a", "b")
) -> Ensemble:
    n_paths, months = a.shape
    paths = np.stack([a, b], axis=-1)
    return Ensemble(paths=paths, factor_names=list(names), meta=_meta(n_paths, months))


def _simple_manifest(active_blocks: tuple[str, ...] = ("global", "us")) -> FactorManifest:
    blocks = {"global": ("g1",), "us": ("u1",)}
    sources = {
        "g1": FactorSource(kind="series", units="ret", series_id="s.g1", numeraire="total_return"),
        "u1": FactorSource(kind="series", units="ret", series_id="s.u1", numeraire="total_return"),
    }
    return FactorManifest(blocks=blocks, active_blocks=active_blocks, sources=sources)


def _empty_reference(active_blocks: tuple[str, ...] = ("global", "us")) -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=active_blocks,
        vintage_id="v",
        n_resamples=1,
        seed=1,
        missing_factors=(),
    )


# --------------------------------------------------------------------------- #
# 1. excess_kurtosis / skew: reuse of reference._excess_kurtosis / reference._skew
# --------------------------------------------------------------------------- #


def test_excess_kurtosis_near_zero_on_large_normal_sample() -> None:
    rng = Generator(PCG64(1))
    x = rng.normal(0.0, 1.0, size=(50, 400))
    ensemble = _one_factor_ensemble(x)
    spec = _find_spec(
        build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.excess_kurtosis"
    )
    value = spec.fn(ensemble)
    # A 20000-point normal sample's sample excess kurtosis has standard error
    # ~sqrt(24/n) ~ 0.011; 0.15 is a >10-sigma band, generous but still discriminating
    # against a systematically biased estimator (e.g. off by a factor or a stray +3).
    assert value == pytest.approx(0.0, abs=0.15)


def test_excess_kurtosis_clearly_positive_on_student_t() -> None:
    rng = Generator(PCG64(2))
    x = rng.standard_t(
        df=3, size=(50, 400)
    )  # df=3: population excess kurtosis is infinite/large; sample is clearly > 0
    ensemble = _one_factor_ensemble(x)
    spec = _find_spec(
        build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.excess_kurtosis"
    )
    value = spec.fn(ensemble)
    assert value > 1.0


def test_excess_kurtosis_metric_agrees_with_reference_definition() -> None:
    x = np.array([1.0, -2.0, 3.0, 0.5, -1.5, 2.5, -0.5, 1.0])
    spec = _find_spec(
        build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.excess_kurtosis"
    )
    ensemble = _one_factor_ensemble(x.reshape(1, -1))
    assert spec.fn(ensemble) == pytest.approx(_excess_kurtosis(x), rel=0, abs=1e-12)


def test_skew_hand_computed_and_agrees_with_reference() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 10.0])  # right-skewed by construction
    xbar = np.mean(x)
    m2 = np.mean((x - xbar) ** 2)
    m3 = np.mean((x - xbar) ** 3)
    expected = m3 / m2**1.5
    assert expected > 0  # sanity: this hand array is right-skewed

    spec = _find_spec(build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.skew")
    ensemble = _one_factor_ensemble(x.reshape(1, -1))
    value = spec.fn(ensemble)
    assert value == pytest.approx(expected, rel=0, abs=1e-12)
    assert value == pytest.approx(_skew(x), rel=0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 2. Hill tail index
# --------------------------------------------------------------------------- #


def test_hill_tail_index_recovers_known_pareto_alpha() -> None:
    """numpy's Generator.pareto(a) draws from the Lomax (Pareto II) distribution;
    1 + Lomax(a) is the classical Type-I Pareto with scale 1 and shape a. Losses are
    set equal to this positive, Pareto-tailed variable (returns = -losses), so the
    Hill estimator's target alpha is known exactly: `a` below.
    """
    rng = Generator(PCG64(3))
    alpha = 2.5
    n = 20000
    losses = 1.0 + rng.pareto(alpha, size=n)
    returns = -losses

    estimated = hill_tail_index(returns, 0.05)

    # Hill estimator asymptotic std error ~ alpha / sqrt(k); k = 0.05*20000 = 1000,
    # se ~ 2.5/31.6 ~ 0.079. A relative tolerance of 15% (~0.375 in alpha) is about a
    # 4-5 sigma band: wide enough to absorb finite-sample bias, tight enough that a
    # systematically wrong estimator (wrong side, off-by-one order statistic, wrong
    # ratio direction) would fail it.
    assert estimated == pytest.approx(alpha, rel=0.15)


def test_hill_tail_index_sign_is_positive_for_a_heavy_tail() -> None:
    rng = Generator(PCG64(4))
    losses = 1.0 + rng.pareto(3.0, size=5000)
    returns = -losses
    assert hill_tail_index(returns, 0.05) > 0.0


def test_hill_tail_index_returns_nan_when_there_is_no_left_tail() -> None:
    """An all-positive-return sample has no losses at all: the top-k 'losses' are all
    <= 0, so the estimator must not silently compute a number from non-loss values."""
    rng = Generator(PCG64(5))
    returns = rng.uniform(0.01, 1.0, size=1000)  # strictly positive: no losses
    assert np.isnan(hill_tail_index(returns, 0.05))


def test_hill_tail_index_returns_nan_with_too_few_observations() -> None:
    # n=1: k = max(1, round(0.05*1)) = 1, so k+1=2 order statistics are required and
    # only 1 observation exists -- NaN, not a value computed from an under-supported k.
    assert np.isnan(hill_tail_index(np.array([-1.0]), 0.05))


def test_hill_metrics_registered_at_5pct_and_1pct() -> None:
    rng = Generator(PCG64(6))
    losses = 1.0 + rng.pareto(2.0, size=(20, 2000))
    returns = -losses
    ensemble = _one_factor_ensemble(returns)
    specs = build_monthly_suite(_simple_manifest(), _empty_reference())
    v5 = _find_spec(specs, "g1.hill_tail_index_5pct").fn(ensemble)
    v1 = _find_spec(specs, "g1.hill_tail_index_1pct").fn(ensemble)
    assert v5 > 0.0
    assert v1 > 0.0


# --------------------------------------------------------------------------- #
# 3. ACF of returns, lags 1-5; agreement with reference._acf1 at lag 1
# --------------------------------------------------------------------------- #


def test_acf_at_lag_one_matches_reference_acf1_bit_for_bit() -> None:
    rng = Generator(PCG64(7))
    x = rng.normal(size=500)
    assert _acf_at_lag(x, 1) == _acf1(x)


def test_acf_r_lag1_recovers_known_ar1_phi() -> None:
    rng = Generator(PCG64(8))
    phi = 0.6
    n = 20000
    z = rng.normal(0.0, 1.0, size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + z[t]
    ensemble = _one_factor_ensemble(x.reshape(1, -1))

    spec = _find_spec(build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.acf_r_lag1")
    value = spec.fn(ensemble)

    # AR(1) sample-ACF-at-lag-1 standard error ~ sqrt((1-phi^2))/sqrt(n) ~ 0.0057 at
    # n=20000; abs=0.03 is a >5-sigma band -- wide enough for finite-sample bias, still
    # tight enough to catch a badly wrong (e.g. lag-2, or un-normalized) estimator.
    assert value == pytest.approx(phi, abs=0.03)


def test_acf_r_lag1_metric_agrees_with_reference_acf1_on_same_input() -> None:
    rng = Generator(PCG64(9))
    x = rng.normal(size=(1, 300))
    ensemble = _one_factor_ensemble(x)
    spec = _find_spec(build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.acf_r_lag1")
    assert spec.fn(ensemble) == pytest.approx(_acf1(x[0]), rel=0, abs=1e-12)


def test_acf_r_lags_do_not_leak_across_path_boundaries() -> None:
    """Two paths, each a short constant-then-jump series that would show spurious
    lag-1 correlation if concatenated end to end; per-path-then-averaged must not."""
    path_a = np.array([1.0, 1.0, 1.0, 1.0])
    path_b = np.array([-1.0, -1.0, -1.0, -1.0])
    # both paths are constant -> NaN per-path (zero variance) -> whole metric is NaN,
    # not some spurious value from the artificial a->b seam a flatten-then-ACF would see
    ensemble = _one_factor_ensemble(np.stack([path_a, path_b]))
    spec = _find_spec(build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.acf_r_lag1")
    assert np.isnan(spec.fn(ensemble))


# --------------------------------------------------------------------------- #
# 4. ACF of |deviation|, lags 1-24, and the fitted decay
# --------------------------------------------------------------------------- #


def test_fit_exp_decay_rate_recovers_exact_noiseless_rate() -> None:
    lags = np.arange(1, 25, dtype=np.float64)
    true_rate = 0.12
    values = 0.5 * np.exp(-true_rate * lags)  # exact, no noise
    recovered = _fit_exp_decay_rate(lags, values)
    # Noiseless log-linear data recovered by OLS is exact up to floating-point error.
    assert recovered == pytest.approx(true_rate, abs=1e-9)


def test_fit_exp_decay_rate_is_negative_for_a_growing_curve() -> None:
    lags = np.arange(1, 10, dtype=np.float64)
    values = np.exp(0.2 * lags)  # growing, not decaying
    assert _fit_exp_decay_rate(lags, values) < 0.0


def test_fit_exp_decay_rate_fits_a_curve_with_only_one_positive_point() -> None:
    """BEHAVIOUR CHANGE, fix pass Important 1. The log-space fit needed at least two
    strictly positive values and returned NaN otherwise; the levels fit has no such
    requirement, because it does not select on sign at all. What used to be the
    "fewer than two positive points" NaN case is now an ordinary fit -- and must be,
    since dropping the non-positive points was itself the bias under repair.
    """
    lags = np.array([1.0, 2.0, 3.0])
    values = np.array([0.5, -0.1, -0.2])
    rate = _fit_exp_decay_rate(lags, values)
    assert not np.isnan(rate)
    assert rate > 0.0  # the curve does decay, steeply


def test_fit_exp_decay_rate_nan_with_fewer_than_two_points() -> None:
    assert np.isnan(_fit_exp_decay_rate(np.array([1.0]), np.array([0.5])))


def test_fit_exp_decay_rate_nan_with_a_non_finite_value() -> None:
    """An uncomputable ACF (a degenerate path) must not be silently fitted around."""
    lags = np.arange(1.0, 5.0)
    assert np.isnan(_fit_exp_decay_rate(lags, np.array([0.5, np.nan, 0.2, 0.1])))


def _garch11_path(n: int, beta: float, seed: int) -> np.ndarray:
    """A GARCH(1,1)-style volatility-clustering path with persistence `beta` (higher
    beta -> slower ACF(|r|) decay). omega/alpha kept modest so the process stays
    stationary (alpha+beta < 1) across every beta this module's tests use."""
    rng = Generator(PCG64(seed))
    omega, alpha = 0.02, 0.08
    sigma2 = np.empty(n)
    r = np.empty(n)
    sigma2[0] = omega / (1 - alpha - beta)
    r[0] = np.sqrt(sigma2[0]) * rng.normal()
    for t in range(1, n):
        sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
        r[t] = np.sqrt(sigma2[t]) * rng.normal()
    return r


def _garch11_ensemble(n_paths: int, months: int, beta: float, base_seed: int) -> Ensemble:
    """Many independent GARCH(1,1) paths sharing one persistence `beta`, as one
    Ensemble -- a single path's per-lag ACF is too noisy at higher lags to fit a
    reliable decay rate (a single 6000-month path was tried and gave a NON-
    discriminating, noise-dominated fit); `acf_abs_decay`'s own per-path-then-averaged
    convention (:func:`ah.eval.metrics.monthly._mean_over_paths`) is what tames that
    noise, so the test must exercise it with a real multi-path ensemble, not fake it
    with one long path.
    """
    paths = np.stack([_garch11_path(months, beta, base_seed * 10_000 + i) for i in range(n_paths)])
    return _one_factor_ensemble(paths)


def test_acf_abs_decay_rate_orders_persistence_correctly() -> None:
    """Simulated ground truth: a slower-decaying (higher-persistence GARCH beta)
    process must recover a SMALLER fitted decay rate than a faster-decaying one, and
    both rates must be positive (genuine decay, not growth) -- the qualitative
    property this metric exists to check, per the module's own docstring."""
    slow = _garch11_ensemble(200, 400, beta=0.85, base_seed=10)
    fast = _garch11_ensemble(200, 400, beta=0.30, base_seed=11)

    rate_slow = acf_abs_decay(slow, "g1")
    rate_fast = acf_abs_decay(fast, "g1")

    assert rate_slow > 0.0
    assert rate_fast > 0.0
    assert rate_slow < rate_fast


def test_acf_abs_lag1_metric_matches_reference_convention_on_abs_deviation() -> None:
    rng = Generator(PCG64(12))
    x = rng.normal(size=(1, 300))
    ensemble = _one_factor_ensemble(x)
    expected = _acf1(np.abs(x[0] - np.mean(x[0])))  # reference._acf_abs_1's own formula
    spec = _find_spec(
        build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.acf_abs_lag1"
    )
    assert spec.fn(ensemble) == pytest.approx(expected, rel=0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 5. aggregational Gaussianity
# --------------------------------------------------------------------------- #


def test_agg_gaussianity_12m_nearer_zero_than_1m_on_fat_tailed_iid_returns() -> None:
    rng = Generator(PCG64(13))
    x = rng.standard_t(
        df=4, size=(40, 2400)
    )  # fat-tailed iid base, CLT should kick in on aggregation
    ensemble = _one_factor_ensemble(x)

    k1 = agg_gaussianity(ensemble, "g1", 1)
    k12 = agg_gaussianity(ensemble, "g1", 12)

    assert k1 > 0.0  # sanity: the base series is indeed fat-tailed at h=1
    assert abs(k12) < abs(k1)


def test_agg_gaussianity_reuses_reference_excess_kurtosis() -> None:
    """Also documents why `agg_gaussianity_1m` is not a registered metric: at h=1 the
    aggregation is the identity, so this IS `excess_kurtosis` (fix pass, Important 4).

    The sample is 40 points rather than the 8 it used to be: a fourth-moment statistic
    below `reference.AGG_GAUSSIANITY_MIN_SUMS` now returns NaN instead of a number that
    is pure noise (fix pass, Minor). The assertion is unchanged.
    """
    rng = Generator(PCG64(313))
    x = rng.standard_t(df=5, size=(1, 40))
    ensemble = _one_factor_ensemble(x)
    value = agg_gaussianity(ensemble, "g1", 1)
    assert value == pytest.approx(_excess_kurtosis(x[0]), rel=0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 6. leverage correlation
# --------------------------------------------------------------------------- #


def test_leverage_correlation_negative_on_constructed_leverage_effect() -> None:
    """Deterministic construction with a known negative return -> future-vol relation:
    r_t = A_t * (+1 if t even else -1); A_{t+1} = clip(1.0 - 1.5*r_t, 0.1, 4.0) -- the
    next amplitude (and so |r_{t+1} - mean|, since sign alternation keeps the mean
    small relative to amplitude) is a decreasing function of r_t by construction, the
    classical leverage-effect shape.
    """
    n = 100
    r = np.zeros(n)
    amplitude = 1.0
    for t in range(n - 1):
        sign = 1.0 if t % 2 == 0 else -1.0
        r[t] = amplitude * sign
        amplitude = float(np.clip(1.0 - 1.5 * r[t], 0.1, 4.0))
    r[n - 1] = amplitude * (1.0 if (n - 1) % 2 == 0 else -1.0)
    ensemble = _one_factor_ensemble(r.reshape(1, -1))

    spec = _find_spec(
        build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.leverage_correlation"
    )
    value = spec.fn(ensemble)

    assert value < -0.3  # strongly, not just barely, negative -- discriminates a broken sign


def test_leverage_correlation_near_zero_on_symmetric_independent_data() -> None:
    rng = Generator(PCG64(14))
    x = rng.normal(size=500)
    value = _leverage_one_path(x)
    # corr of two independent length-~500 series has SE ~ 1/sqrt(500) ~ 0.045; 0.2 is
    # a >4-sigma band.
    assert value == pytest.approx(0.0, abs=0.2)


# --------------------------------------------------------------------------- #
# 7. correlation-matrix distance
# --------------------------------------------------------------------------- #


def test_corr_matrix_distance_zero_against_itself() -> None:
    m = np.array([[1.0, 0.3, -0.2], [0.3, 1.0, 0.5], [-0.2, 0.5, 1.0]])
    assert corr_matrix_distance(m, m) == pytest.approx(0.0, abs=0.0)


def test_corr_matrix_distance_orders_by_how_different() -> None:
    base = np.array([[1.0, 0.3, -0.2], [0.3, 1.0, 0.5], [-0.2, 0.5, 1.0]])
    close = np.array([[1.0, 0.32, -0.18], [0.32, 1.0, 0.52], [-0.18, 0.52, 1.0]])
    far = np.array([[1.0, -0.8, 0.1], [-0.8, 1.0, -0.6], [0.1, -0.6, 1.0]])

    d_close = corr_matrix_distance(base, close)
    d_far = corr_matrix_distance(base, far)

    assert d_close > 0.0
    assert d_close < d_far


def test_corr_matrix_distance_metric_uses_cross_block_reference_correlations() -> None:
    manifest = _simple_manifest()
    ref_corr = 0.4
    band = StatBand(point=ref_corr, lo=0.2, hi=0.6, n_resamples=5, level=0.9, tier="monthly")
    reference = ReferenceStats(
        blocks={},
        cross_blocks={
            ("global", "us"): CrossBlockReference(
                pair=("global", "us"), stats={"g1~u1.correlation": band}
            )
        },
        active_blocks=("global", "us"),
        vintage_id="v",
        n_resamples=5,
        seed=1,
        missing_factors=(),
    )

    rng = Generator(PCG64(15))
    n_paths, months = 200, 24
    a = rng.normal(size=(n_paths, months))
    b = ref_corr * a + np.sqrt(1 - ref_corr**2) * rng.normal(size=(n_paths, months))
    ensemble = _two_factor_ensemble(a, b, names=("g1", "u1"))

    specs = build_monthly_suite(manifest, reference)
    value = _find_spec(specs, "cross_block_corr_matrix_distance").fn(ensemble)

    # ensemble's g1~u1 correlation should be close to ref_corr=0.4 by construction, so
    # the 2x2 off-diagonal distance should be small (well under a mismatched-band scale).
    assert value < 0.3


def test_corr_matrix_distance_metric_nan_when_no_reference_pairs_exist() -> None:
    manifest = _simple_manifest()
    reference = _empty_reference()
    ensemble = _two_factor_ensemble(np.zeros((5, 10)), np.zeros((5, 10)), names=("g1", "u1"))
    specs = build_monthly_suite(manifest, reference)
    value = _find_spec(specs, "cross_block_corr_matrix_distance").fn(ensemble)
    assert np.isnan(value)


# --------------------------------------------------------------------------- #
# 8. crisis-conditional correlation lift: reuse of reference._crisis_corr_lift
# --------------------------------------------------------------------------- #


def test_crisis_corr_lift_positive_when_crisis_correlation_is_constructed_higher() -> None:
    rng = Generator(PCG64(16))
    n_paths, months = 50, 200
    a = rng.normal(0.0, 1.0, size=(n_paths, months))
    b = 0.05 * rng.normal(size=(n_paths, months))  # weak unconditional link
    # in A's worst decile, make B track A strongly (crisis co-movement)
    threshold = np.percentile(a, 10)
    crisis_mask = a <= threshold
    b = np.where(crisis_mask, 0.9 * a + 0.1 * rng.normal(size=a.shape), b)
    ensemble = _two_factor_ensemble(a, b, names=("g1", "u1"))

    manifest = _simple_manifest()
    specs = build_monthly_suite(manifest, _empty_reference())
    value = _find_spec(specs, "g1~u1.crisis_corr_lift").fn(ensemble)

    assert value > 0.1


def test_crisis_corr_lift_metric_equals_reference_definition_on_same_input() -> None:
    rng = Generator(PCG64(17))
    a = rng.normal(size=(1, 400))
    b = rng.normal(size=(1, 400))
    ensemble = _two_factor_ensemble(a, b, names=("g1", "u1"))
    manifest = _simple_manifest()
    specs = build_monthly_suite(manifest, _empty_reference())
    value = _find_spec(specs, "g1~u1.crisis_corr_lift").fn(ensemble)
    expected = _crisis_corr_lift(a[0], b[0])
    assert value == pytest.approx(expected, rel=0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 9. suite shape, absent-factor NaN guard, and battery registration
# --------------------------------------------------------------------------- #


def _find_spec(specs: tuple[MetricSpec, ...], name: str) -> MetricSpec:
    for s in specs:
        if s.name == name:
            return s
    raise AssertionError(
        f"no metric named {name!r} in suite; have: {sorted(s.name for s in specs)}"
    )


def test_build_monthly_suite_names_and_tiers() -> None:
    specs = build_monthly_suite(_simple_manifest(), _empty_reference())
    names = {s.name for s in specs}
    assert "g1.excess_kurtosis" in names
    assert "g1.skew" in names
    assert "g1.hill_tail_index_5pct" in names
    assert "g1.hill_tail_index_1pct" in names
    for lag in range(1, 6):
        assert f"g1.acf_r_lag{lag}" in names
    for lag in range(1, 25):
        assert f"g1.acf_abs_lag{lag}" in names
    assert "g1.acf_abs_decay" in names
    # h=1 is the identity aggregation and is exactly `excess_kurtosis`; only h>1
    # points of the aggregation curve get their own name (fix pass, Important 4).
    assert "g1.agg_gaussianity_3m" in names
    assert "g1.agg_gaussianity_12m" in names
    assert "g1.leverage_correlation" in names
    assert "g1~u1.crisis_corr_lift" in names
    assert "cross_block_corr_matrix_distance" in names
    assert all(s.tier == "monthly" for s in specs)
    assert all(s.suite == "monthly" for s in specs)
    # no accidental duplicate names (register_suite would reject this anyway)
    assert len(names) == len(specs)


def test_metric_returns_nan_when_factor_absent_from_ensemble() -> None:
    """`u1` is active in the manifest but this ensemble (like a real generator missing
    a declared-unavailable factor) does not carry it at all."""
    manifest = _simple_manifest()
    specs = build_monthly_suite(manifest, _empty_reference())
    ensemble = _one_factor_ensemble(np.zeros((3, 10)), factor="g1")  # no "u1"
    value = _find_spec(specs, "u1.skew").fn(ensemble)
    assert np.isnan(value)
    lift = _find_spec(specs, "g1~u1.crisis_corr_lift").fn(ensemble)
    assert np.isnan(lift)


@pytest.fixture
def restore_suites() -> Iterator[None]:
    """Snapshot and restore ``battery.SUITES`` around a test that registers into it.

    ``SUITES`` is process-global module state and ``register_suite`` refuses to
    re-register a name, so a test that registers a suite and does not undo it poisons
    every later test -- and leaks a metric into any other module's ``run_battery``
    call. The same fixture ``tests/test_eval_battery.py`` uses; a ``try/finally`` pop
    was the ad-hoc version, and it only removes the one key the test remembers to name.
    """
    snapshot = dict(battery.SUITES)
    try:
        yield
    finally:
        battery.SUITES.clear()
        battery.SUITES.update(snapshot)


def test_register_monthly_suite_appears_in_run_battery_without_editing_it(
    restore_suites: None,
) -> None:
    """Integration proof: monthly registers via the ordinary register_suite() path and
    run_battery picks it up with no change to run_battery's own source (Task 1's own
    acceptance bar, applied to this suite)."""
    assert "monthly" not in battery.SUITES
    manifest = _simple_manifest()
    reference = _empty_reference()
    register_monthly_suite(manifest, reference)

    rng = Generator(PCG64(18))
    n_paths, months = 40, 30
    g1 = rng.normal(0.0, 0.03, size=(n_paths, months))
    u1 = rng.normal(0.0, 0.03, size=(n_paths, months))
    ensemble = _two_factor_ensemble(g1, u1, names=("g1", "u1"))

    from ah.eval import prereg as prereg_mod

    report = run_battery(
        ensemble, reference=reference, prereg=prereg_mod.load(), manifest=manifest, seed=0
    )
    names = {r.name for r in report.results if r.suite == "monthly"}
    assert "g1.skew" in names
    assert "cross_block_corr_matrix_distance" in names


def test_monthly_is_registered_in_prereg_metric_suite_names() -> None:
    """The seal join is a fixed name list (ah.eval.prereg._METRIC_SUITE_NAMES), not a
    directory scan -- adding this module without adding its name there would leave it
    silently outside the pre-registration seal (see ah.eval.prereg's module docstring
    and CLAUDE.md's hard invariant)."""
    from ah.eval import prereg as prereg_mod

    assert "monthly" in prereg_mod._METRIC_SUITE_NAMES


# --------------------------------------------------------------------------- #
# WP2.2 Task 2 fix pass
# --------------------------------------------------------------------------- #


def test_every_monthly_metric_name_is_a_registered_reference_statistic() -> None:
    """Critical 2. ``ah.eval.prereg`` validates a threshold key's ``<stat>`` against
    these registries, so a metric whose statistic is unregistered cannot carry a sealed
    threshold at all -- and, once ``sealed: true`` lands, an entry authored under such
    a name breaks every battery run rather than only the seal."""
    from ah.eval.reference import CROSS_BLOCK_STATS, PANEL_STATS, SINGLE_FACTOR_STATS

    specs = build_monthly_suite(_simple_manifest(), _empty_reference())
    for spec in specs:
        if "." not in spec.name:
            assert spec.name in PANEL_STATS, spec.name
        elif "~" in spec.name:
            assert spec.name.split(".", 1)[1] in CROSS_BLOCK_STATS, spec.name
        else:
            assert spec.name.split(".", 1)[1] in SINGLE_FACTOR_STATS, spec.name


def test_agg_gaussianity_1m_is_not_registered_as_a_second_metric() -> None:
    """Important 4. The h=1 aggregation is the identity, so ``agg_gaussianity_1m`` was
    bit-identical to ``excess_kurtosis``: two sealed names, one number. Only the h>1
    points of the aggregation curve are registered; the h=1 point IS
    ``excess_kurtosis`` (numeric identity asserted by
    ``test_agg_gaussianity_reuses_reference_excess_kurtosis`` above)."""
    names = {s.name for s in build_monthly_suite(_simple_manifest(), _empty_reference())}
    assert "g1.agg_gaussianity_1m" not in names
    assert "g1.agg_gaussianity_3m" in names
    assert "g1.agg_gaussianity_12m" in names
    assert "g1.excess_kurtosis" in names


def test_corr_matrix_distance_metric_is_named_for_the_pairs_it_actually_covers() -> None:
    """Minor. The metric covers cross-block pairs only (``reference.py`` registers no
    within-block pairwise correlation), so the unqualified name overstated coverage in
    every report table and threshold key."""
    names = {s.name for s in build_monthly_suite(_simple_manifest(), _empty_reference())}
    assert "cross_block_corr_matrix_distance" in names
    assert "corr_matrix_distance" not in names


def test_paired_corr_matrices_flag_the_pairs_the_reference_actually_covers() -> None:
    """Minor. Both returned matrices carry 0.0 off-diagonal wherever the reference has
    no entry for that pair -- harmless for the difference, but it means the returned
    ensemble matrix is NOT the ensemble's correlation matrix. The mask says which
    entries are real."""
    manifest = FactorManifest(
        blocks={"global": ("g1", "g2"), "us": ("u1",)},
        active_blocks=("global", "us"),
        sources={
            name: FactorSource(
                kind="series", units="ret", series_id=f"s.{name}", numeraire="total_return"
            )
            for name in ("g1", "g2", "u1")
        },
    )
    band = StatBand(point=0.4, lo=0.2, hi=0.6, n_resamples=5, level=0.9, tier="monthly")
    reference = ReferenceStats(
        blocks={},
        cross_blocks={
            ("global", "us"): CrossBlockReference(
                pair=("global", "us"),
                stats={"g1~u1.correlation": band, "g2~u1.correlation": band},
            )
        },
        active_blocks=("global", "us"),
        vintage_id="v",
        n_resamples=5,
        seed=1,
        missing_factors=(),
    )
    rng = Generator(PCG64(210))
    paths = rng.normal(size=(20, 40, 3))
    ensemble = Ensemble(paths=paths, factor_names=["g1", "g2", "u1"], meta=_meta(20, 40))

    paired = _paired_corr_matrices(ensemble, reference, manifest.active_factors())
    assert paired is not None
    # g1~g2 is a within-block pair: no reference entry, so it is masked out and both
    # matrices carry 0.0 there -- NOT the ensemble's real g1~g2 correlation.
    i, j = paired.factors.index("g1"), paired.factors.index("g2")
    assert not paired.mask[i, j]
    assert paired.ensemble[i, j] == 0.0
    k = paired.factors.index("u1")
    assert paired.mask[i, k] and paired.mask[j, k]
    assert paired.ensemble[i, k] != 0.0


def test_acf_abs_lag1_metric_agrees_with_the_reference_function_itself() -> None:
    """Important 5. The previous version retyped ``_acf1(np.abs(x - mean))`` by hand,
    so a divergence in ``reference._acf_abs_1`` would have left the test green."""
    from ah.eval.reference import _acf_abs_1

    rng = Generator(PCG64(112))
    x = rng.normal(size=(1, 300))
    ensemble = _one_factor_ensemble(x)
    spec = _find_spec(
        build_monthly_suite(_simple_manifest(), _empty_reference()), "g1.acf_abs_lag1"
    )
    assert spec.fn(ensemble) == pytest.approx(_acf_abs_1(x[0]), rel=0, abs=1e-12)


def test_hill_metric_recovers_the_known_alpha_of_its_own_fixture() -> None:
    """Minor: the registration test asserted only ``> 0`` on data with a known alpha."""
    rng = Generator(PCG64(6))
    alpha = 2.0
    losses = 1.0 + rng.pareto(alpha, size=(20, 2000))
    ensemble = _one_factor_ensemble(-losses)
    specs = build_monthly_suite(_simple_manifest(), _empty_reference())
    # k = 5% of 40000 pooled observations = 2000; Hill's asymptotic SE is
    # alpha / sqrt(k) ~ 0.045, so rel=0.15 (~0.3 in alpha) is a >6-sigma band.
    assert _find_spec(specs, "g1.hill_tail_index_5pct").fn(ensemble) == pytest.approx(
        alpha, rel=0.15
    )
    assert _find_spec(specs, "g1.hill_tail_index_1pct").fn(ensemble) == pytest.approx(
        alpha, rel=0.15
    )


def test_agg_gaussianity_needs_more_than_a_handful_of_sums() -> None:
    """Minor: ``sums.size < 4`` was a very weak guard for a fourth-moment statistic.
    Excess kurtosis on 4-10 points is noise, not a measurement."""
    x = np.arange(40.0).reshape(2, 20)
    ensemble = _one_factor_ensemble(x)
    # h=12 over two 20-month paths yields one sum per path: 2 pooled sums.
    assert np.isnan(agg_gaussianity(ensemble, "g1", 12))
    # h=1 over the same paths yields 40 pooled sums, comfortably above the floor.
    assert not np.isnan(agg_gaussianity(ensemble, "g1", 1))


# --- Important 1: the decay estimator must not select on the sign of its inputs ---


def test_fit_exp_decay_rate_uses_every_lag_including_non_positive_ones() -> None:
    """Dropping non-positive ACF values is a one-sided selection: at lags where the
    true ACF is ~0 only upward noise survives, lifting the fitted tail and biasing the
    rate downward. The levels fit consumes the whole curve, sign and all, so a curve
    and its sign-symmetric perturbations do not systematically differ."""
    lags = np.arange(1, 25, dtype=np.float64)
    clean = 0.5 * np.exp(-0.3 * lags)
    up = clean.copy()
    down = clean.copy()
    # a symmetric perturbation over the noise-dominated tail, where the ACF is ~0
    up[16:] += 0.01
    down[16:] -= 0.01
    r_clean = _fit_exp_decay_rate(lags, clean)
    r_up = _fit_exp_decay_rate(lags, up)
    r_down = _fit_exp_decay_rate(lags, down)
    assert not np.isnan(r_down), "a curve with negative tail values must still fit"
    # the two perturbations pull the rate in opposite directions by similar amounts;
    # the log-space fit could not see `down` at all.
    assert (r_up - r_clean) * (r_down - r_clean) < 0.0
    assert abs((r_up - r_clean) + (r_down - r_clean)) < 0.5 * abs(r_up - r_clean)


def test_fit_exp_decay_rate_is_defined_for_a_curve_that_crosses_zero() -> None:
    lags = np.arange(1, 13, dtype=np.float64)
    values = 0.4 * np.exp(-0.25 * lags) - 0.02
    assert float(values[-1]) < 0.0
    assert not np.isnan(_fit_exp_decay_rate(lags, values))


def test_fit_exp_decay_rate_is_nan_for_an_all_zero_curve() -> None:
    lags = np.arange(1, 6, dtype=np.float64)
    assert np.isnan(_fit_exp_decay_rate(lags, np.zeros(5)))


def _ar1_vol_path(
    n: int, phi: float, seed: int, mu: float = 12.0, sigma: float = 0.5
) -> np.ndarray:
    """A path whose ACF(|x - mean|) is exactly geometric with ratio ``phi``.

    ``v`` is an AR(1) with mean ``mu`` far enough above zero that it never changes
    sign, so ``acf(v, k) = phi**k`` exactly in population. The sign of ``x`` alternates,
    so ``mean(x) ~ 0`` and ``|x - mean(x)| = v``: the volatility-clustering curve this
    metric fits is a known exponential of rate ``-ln(phi)``.
    """
    rng = Generator(PCG64(seed))
    v = np.empty(n)
    v[0] = mu
    for t in range(1, n):
        v[t] = mu + phi * (v[t - 1] - mu) + sigma * rng.normal()
    assert v.min() > 0.0
    return v * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)


def test_acf_abs_decay_recovers_a_known_exponential_rate() -> None:
    """MISSING (from the brief): the composite metric was only ordering-tested.
    ``_ar1_vol_path``'s ACF(|deviation|) is exactly ``phi**k``, so the metric's target
    is ``-ln(phi)``, known independently of this implementation."""
    phi = 0.9
    paths = np.stack([_ar1_vol_path(2000, phi, 4000 + i) for i in range(30)])
    ensemble = _one_factor_ensemble(paths)

    rate = acf_abs_decay(ensemble, "g1")

    # Per-path rates have sd ~0.025 across these 30 paths, so their mean has SE ~0.005;
    # abs=0.02 is a ~4-sigma band around -ln(0.9) = 0.1054 that still excludes
    # -ln(0.85) = 0.1625 and -ln(0.95) = 0.0513 by a wide margin. The small residual
    # upward bias (measured ~+0.005) is the finite-sample ACF bias described in the
    # module docstring, not slack in the estimator.
    assert rate == pytest.approx(-np.log(phi), abs=0.02)


def test_acf_abs_decay_is_computed_per_path_then_averaged() -> None:
    """The module's stated convention for every time-order-dependent statistic, and
    the convention the length-matched reference band assumes: a reference replicate is
    one series of the ensemble's path length, so the ensemble side must average that
    same single-series estimator rather than fit a path-averaged curve (a materially
    less biased -- and therefore NON-comparable -- functional)."""
    from ah.eval.reference import acf_abs_decay as reference_acf_abs_decay

    paths = np.stack([_ar1_vol_path(400, 0.9, 5100 + i) for i in range(6)])
    ensemble = _one_factor_ensemble(paths)
    expected = float(np.mean([reference_acf_abs_decay(p) for p in paths]))
    assert acf_abs_decay(ensemble, "g1") == pytest.approx(expected, rel=0, abs=1e-12)


# --- Important 3: a generator reproducing history lands inside its own band ---


def _seasonal_vol_series(n: int, seed: int, offset: int = 0) -> np.ndarray:
    """A path whose |deviation| carries a near-deterministic 24-month volatility cycle.

    Chosen deliberately: with an almost deterministic period-24 signal the sample ACF
    at lag 24 is dominated by the estimator's own length dependence -- the
    n-denominator shrinkage factor ``(n - k) / n`` -- and by nothing else, so a test
    built on it measures the artifact under repair rather than a process's sampling
    noise.
    """
    rng = Generator(PCG64(seed))
    t = np.arange(offset, offset + n)
    v = 5.0 + 2.0 * np.cos(2.0 * np.pi * t / 24.0) + 0.2 * rng.normal(size=n)
    return v * np.where(t % 2 == 0, 1.0, -1.0)


def test_length_matched_band_contains_a_generator_reproducing_the_same_process() -> None:
    """Important 3. The n-denominator ACF estimator shrinks by ``(n - k) / n``: ~20% at
    lag 24 on a 120-month path and ~2% on the ~1100-month history the reference is
    computed over. A generator reproducing history EXACTLY would therefore sit outside
    a band drawn at history's length, purely as an estimator artifact. Reference
    replicates are drawn at the ensemble's own path length so both sides carry the
    same bias.
    """
    import pandas as pd

    from ah.eval.reference import compute_reference
    from ah.splits import DataAccess

    months = 120
    history = _seasonal_vol_series(1200, 42)
    dates = pd.date_range("1900-01-01", periods=history.size, freq="MS")
    frames = {"s.g1": pd.DataFrame({"date": dates, "value": history})}

    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in frames:
            raise KeyError(series_id)
        return frames[series_id]

    manifest = FactorManifest(
        blocks={"global": ("g1",)},
        active_blocks=("global",),
        sources={
            "g1": FactorSource(
                kind="series", series_id="s.g1", units="ret", numeraire="total_return"
            )
        },
    )
    access = DataAccess(reader)
    ensemble = _one_factor_ensemble(
        np.stack([_seasonal_vol_series(months, 6000 + i, offset=i) for i in range(40)])
    )
    specs = build_monthly_suite(manifest, _empty_reference(("global",)))

    matched = compute_reference(
        access,
        manifest,
        vintage_id="v",
        seed=5,
        n_resamples=200,
        block_length=months,
        resample_length=months,
    )
    unmatched = compute_reference(
        access, manifest, vintage_id="v", seed=5, n_resamples=200, block_length=months
    )

    for lag in (12, 24):
        name = f"g1.acf_abs_lag{lag}"
        value = _find_spec(specs, name).fn(ensemble)
        band = matched.blocks["global"].stats[name]
        assert band.lo <= value <= band.hi, f"{name}: {value} outside {band}"
        # ... while the same statistic on the FULL history -- what an un-length-matched
        # band is centred on -- is a materially different number. That gap IS the
        # artifact: history reproduced exactly would fail its own band.
        full_sample = unmatched.blocks["global"].stats[name].point
        # The gap is the (n - k) / n shrinkage the estimator applies at path length:
        # |full_sample| * lag / months, and at least half of it must actually show up,
        # or the fixture is not length-sensitive and the test would prove nothing.
        predicted_shrinkage = abs(full_sample) * lag / months
        assert abs(full_sample - value) > 0.5 * predicted_shrinkage, (
            f"{name}: expected a length artifact of ~{predicted_shrinkage:.3f}, saw "
            f"{abs(full_sample - value):.3f}"
        )
        assert not (band.lo <= full_sample <= band.hi)
