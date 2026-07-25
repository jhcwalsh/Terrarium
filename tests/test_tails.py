"""WP2.1b Task 2 acceptance: D4 strategy return paths and historical VaR/ES.

Scope discipline (see ``ah/eval/metrics/tails.py`` module docstring): this covers
only strategy_returns/var_es/d4_tail_table and the derived-series transforms.
Elicitability, Kupiec/Christoffersen backtests, and tail-dependence coefficients are
WP2.2 scope and are not tested here.

Test-data note, deliberate and load-bearing: the rate/spread factors are fed
**plausible level magnitudes in percent** (a 10y yield near 4, a policy rate near 2.5,
a HY spread near 4.5), not zero-mean N(0, 0.02) noise. Zero-mean noise in a level
factor is exactly what let the earlier level-summed-as-return defect survive review:
with levels centred on zero, a sign inversion is invisible and a positive-constant
carry term does not exist. Any test here that touches ust_10y / hy_spread /
policy_rate must keep using level magnitudes.
"""

from __future__ import annotations

from collections.abc import Mapping
from statistics import NormalDist

import numpy as np
import pytest
from numpy.random import PCG64, Generator

from ah.eval.metrics import tails
from ah.eval.metrics.tails import d4_tail_table, derived_series_values, strategy_returns, var_es
from ah.gen.base import Ensemble, EnsembleMeta, UnknownFactorError
from ah.strategies import DerivedSeries, Strategy, StrategyError, load_d4_strategies

_FACTOR_NAMES = [
    "equity_mkt",
    "smb",
    "hml",
    "mom",
    "commodities",
    "ust_10y",
    "hy_spread",
    "policy_rate",
]

_RETURN_FACTORS = ("equity_mkt", "smb", "hml", "mom", "commodities")

_GOVT_TR = DerivedSeries(
    series_id="govt_tr_10y",
    source_factor="ust_10y",
    transform="bond_total_return",
    params={"duration_years": 8.5},
    formula="r_t = 0.01 * ( y_{t-1}/12 - D*(y_t - y_{t-1}) )",
    notes="",
)
_CREDIT_XS = DerivedSeries(
    series_id="credit_xs_hy",
    source_factor="hy_spread",
    transform="spread_excess_return",
    params={"spread_duration_years": 4.0},
    formula="r_t = 0.01 * ( s_{t-1}/12 - SD*(s_t - s_{t-1}) )",
    notes="",
)
_CASH = DerivedSeries(
    series_id="cash_tr_1m",
    source_factor="policy_rate",
    transform="bond_total_return",
    params={"duration_years": 0.0},
    formula="r_t = 0.01 * y_{t-1}/12",
    notes="",
)
_DERIVED: Mapping[str, DerivedSeries] = {
    "govt_tr_10y": _GOVT_TR,
    "credit_xs_hy": _CREDIT_XS,
    "cash_tr_1m": _CASH,
}


def _make_ensemble(paths: np.ndarray, factor_names: list[str] | None = None) -> Ensemble:
    names = factor_names if factor_names is not None else _FACTOR_NAMES
    n_paths, months, _ = paths.shape
    return Ensemble(paths, list(names), EnsembleMeta("fake-v0", "v1", 0, n_paths, months))


def _level_ensemble(values: dict[str, list[float]]) -> Ensemble:
    """A one-path ensemble with named factors set to the given per-month values."""
    months = len(next(iter(values.values())))
    paths = np.zeros((1, months, len(_FACTOR_NAMES)), dtype=np.float64)
    for name, series in values.items():
        paths[0, :, _FACTOR_NAMES.index(name)] = series
    return _make_ensemble(paths)


def _plausible_ensemble(seed: int = 20260723, n_paths: int = 300, months: int = 60) -> Ensemble:
    """Return factors as monthly returns; rate/spread factors as PERCENT LEVELS.

    Levels are random walks from plausible starting points -- a 10y yield near 4%, a
    policy rate near 2.5%, a HY OAS near 4.5% -- because a level factor centred on
    zero cannot expose a sign inversion or a mis-scaled carry term.
    """
    rng = Generator(PCG64(seed))
    paths = np.zeros((n_paths, months, len(_FACTOR_NAMES)), dtype=np.float64)
    for name in _RETURN_FACTORS:
        paths[:, :, _FACTOR_NAMES.index(name)] = rng.normal(0.005, 0.04, size=(n_paths, months))

    def walk(start: float, step_sd: float, floor: float) -> np.ndarray:
        steps = rng.normal(0.0, step_sd, size=(n_paths, months))
        return np.maximum(start + np.cumsum(steps, axis=1), floor)

    paths[:, :, _FACTOR_NAMES.index("ust_10y")] = walk(4.0, 0.20, 0.05)
    paths[:, :, _FACTOR_NAMES.index("policy_rate")] = walk(2.5, 0.15, 0.0)
    paths[:, :, _FACTOR_NAMES.index("hy_spread")] = walk(4.5, 0.30, 1.0)
    return _make_ensemble(paths)


# --------------------------------------------------------------------------- #
# derived-series transforms: closed form and sign
# --------------------------------------------------------------------------- #


def test_bond_total_return_closed_form() -> None:
    """r_t = 0.01 * ( y_{t-1}/12 - D*(y_t - y_{t-1}) ), r_0 = 0, hand-computed."""
    ensemble = _level_ensemble({"ust_10y": [4.0, 4.5, 4.2]})
    values = derived_series_values(ensemble, _GOVT_TR)
    expected = [
        0.0,
        0.01 * (4.0 / 12.0 - 8.5 * 0.5),
        0.01 * (4.5 / 12.0 - 8.5 * -0.3),
    ]
    np.testing.assert_allclose(values[0], expected, rtol=0, atol=1e-15)
    # spelled out numerically, so the percent-to-decimal convention is pinned:
    assert values[0, 1] == pytest.approx(-0.0391666666666667, abs=1e-15)
    assert values[0, 2] == pytest.approx(0.02925, abs=1e-15)


def test_spread_excess_return_closed_form() -> None:
    """r_t = 0.01 * ( s_{t-1}/12 - SD*(s_t - s_{t-1}) ), r_0 = 0, hand-computed."""
    ensemble = _level_ensemble({"hy_spread": [4.0, 5.0, 4.5]})
    values = derived_series_values(ensemble, _CREDIT_XS)
    expected = [
        0.0,
        0.01 * (4.0 / 12.0 - 4.0 * 1.0),
        0.01 * (5.0 / 12.0 - 4.0 * -0.5),
    ]
    np.testing.assert_allclose(values[0], expected, rtol=0, atol=1e-15)
    assert values[0, 1] == pytest.approx(-0.0366666666666667, abs=1e-15)
    assert values[0, 2] == pytest.approx(0.0241666666666667, abs=1e-15)


def test_cash_return_is_pure_lagged_carry() -> None:
    """Zero duration collapses the bond formula to carry alone: r_t = 0.01*y_{t-1}/12."""
    ensemble = _level_ensemble({"policy_rate": [2.4, 2.4, 6.0]})
    values = derived_series_values(ensemble, _CASH)
    np.testing.assert_allclose(values[0], [0.0, 0.002, 0.002], rtol=0, atol=1e-15)


def test_govt_tr_10y_is_negative_when_yields_rise() -> None:
    """THE sign inversion this layer exists to fix: a rising yield must LOSE money."""
    ensemble = _level_ensemble({"ust_10y": [3.0, 3.5, 4.0, 4.5]})
    values = derived_series_values(ensemble, _GOVT_TR)
    assert np.all(values[0, 1:] < 0.0), values[0]


def test_govt_tr_10y_is_positive_when_yields_fall() -> None:
    ensemble = _level_ensemble({"ust_10y": [4.5, 4.0, 3.5, 3.0]})
    values = derived_series_values(ensemble, _GOVT_TR)
    assert np.all(values[0, 1:] > 0.0), values[0]


def test_credit_xs_hy_is_negative_when_spreads_widen() -> None:
    """Widening spreads must be booked as a LOSS, not a gain."""
    ensemble = _level_ensemble({"hy_spread": [4.0, 5.0, 6.5, 9.0]})
    values = derived_series_values(ensemble, _CREDIT_XS)
    assert np.all(values[0, 1:] < 0.0), values[0]


def test_credit_xs_hy_is_positive_when_spreads_tighten() -> None:
    ensemble = _level_ensemble({"hy_spread": [9.0, 6.5, 5.0, 4.0]})
    values = derived_series_values(ensemble, _CREDIT_XS)
    assert np.all(values[0, 1:] > 0.0), values[0]


def test_derived_series_warm_up_month_is_zero() -> None:
    ensemble = _level_ensemble({"ust_10y": [4.0, 4.5], "hy_spread": [4.0, 5.0]})
    assert derived_series_values(ensemble, _GOVT_TR)[0, 0] == 0.0
    assert derived_series_values(ensemble, _CREDIT_XS)[0, 0] == 0.0


def test_derived_series_of_a_single_month_path_is_all_zero() -> None:
    ensemble = _level_ensemble({"ust_10y": [4.0]})
    np.testing.assert_array_equal(derived_series_values(ensemble, _GOVT_TR), np.zeros((1, 1)))


def test_unknown_transform_raises_at_metric_time() -> None:
    ensemble = _level_ensemble({"ust_10y": [4.0, 4.5]})
    bogus = DerivedSeries("x", "ust_10y", "not_a_transform", {}, "f", "")
    with pytest.raises(StrategyError, match="no dispatch"):
        derived_series_values(ensemble, bogus)


def test_transform_missing_sealed_parameter_raises() -> None:
    ensemble = _level_ensemble({"ust_10y": [4.0, 4.5]})
    bogus = DerivedSeries("x", "ust_10y", "bond_total_return", {}, "f", "")
    with pytest.raises(StrategyError, match="duration_years"):
        derived_series_values(ensemble, bogus)


# --------------------------------------------------------------------------- #
# strategy_returns: static_weights
# --------------------------------------------------------------------------- #


def test_strategy_returns_static_weights_closed_form() -> None:
    """60/40 over equity and the DERIVED government total return."""
    ensemble = _level_ensemble({"equity_mkt": [0.02, 0.02, 0.02], "ust_10y": [4.0, 4.5, 4.2]})
    strategy = Strategy(
        strategy_id="test_sixty_forty",
        kind="static_weights",
        weights={"equity_mkt": 0.6, "govt_tr_10y": 0.4},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy, _DERIVED)
    govt = [0.0, 0.01 * (4.0 / 12.0 - 8.5 * 0.5), 0.01 * (4.5 / 12.0 - 8.5 * -0.3)]
    expected = [0.6 * 0.02 + 0.4 * g for g in govt]
    assert returns.shape == (1, 3)
    np.testing.assert_allclose(returns[0], expected, rtol=0, atol=1e-15)


def test_sixty_forty_loses_when_yields_rise_and_equity_is_flat() -> None:
    """The consequence of CRITICAL 1 at strategy level, asserted on sign."""
    ensemble = _level_ensemble({"equity_mkt": [0.0, 0.0, 0.0], "ust_10y": [4.0, 4.4, 4.8]})
    strategy = Strategy(
        strategy_id="test_sixty_forty",
        kind="static_weights",
        weights={"equity_mkt": 0.6, "govt_tr_10y": 0.4},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy, _DERIVED)
    assert np.all(returns[0, 1:] < 0.0), returns[0]


def test_strategy_returns_equal_weight_closed_form() -> None:
    n_paths, months = 2, 4
    rng = Generator(PCG64(42))
    values = rng.normal(size=(2,))
    paths = np.zeros((n_paths, months, 2), dtype=np.float64)
    paths[:, :, 0] = values[0]
    paths[:, :, 1] = values[1]
    ensemble = _make_ensemble(paths, factor_names=["equity_mkt", "smb"])

    strategy = Strategy(
        strategy_id="test_eqw",
        kind="static_weights",
        weights={"equity_mkt": 0.5, "smb": 0.5},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy, {})
    np.testing.assert_allclose(returns, 0.5 * values[0] + 0.5 * values[1])


def test_missing_factor_raises_a_named_error() -> None:
    """MINOR 15: `commodities` is the likely first real-world miss."""
    paths = np.zeros((2, 3, 1), dtype=np.float64)
    ensemble = _make_ensemble(paths, factor_names=["equity_mkt"])
    strategy = Strategy(
        strategy_id="test",
        kind="static_weights",
        weights={"commodities": 1.0},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )
    with pytest.raises(UnknownFactorError) as excinfo:
        strategy_returns(ensemble, strategy, {})
    assert "commodities" in str(excinfo.value)
    assert "equity_mkt" in str(excinfo.value)
    assert excinfo.value.name == "commodities"
    assert excinfo.value.available == ("equity_mkt",)


# --------------------------------------------------------------------------- #
# var_es
# --------------------------------------------------------------------------- #


def test_var_es_matches_analytic_normal_within_tolerance() -> None:
    """Tolerance is ~8x the MC standard error of the 95% quantile at this n.

    At n = 2e6 the MC s.e. of the 95% loss quantile is about 6e-5; the previous
    tolerance of 2e-3 admitted a ~3% systematic bias, so it could not discriminate a
    correct implementation from a mis-specified one.
    """
    mu, sigma = 0.005, 0.04
    n = 2_000_000
    rng = Generator(PCG64(12345))
    returns = rng.normal(loc=mu, scale=sigma, size=(1, n))

    tol = 5e-4
    for level in (0.95, 0.99):
        var, es = var_es(returns, level)
        z = NormalDist().inv_cdf(level)
        analytic_var = -mu + sigma * z
        # ES for a normal loss distribution: E[loss | loss >= VaR] = -mu + sigma*phi(z)/(1-level)
        analytic_es = -mu + sigma * NormalDist().pdf(z) / (1 - level)
        assert var == pytest.approx(analytic_var, abs=tol)
        assert es == pytest.approx(analytic_es, abs=tol)


def test_var_es_on_a_hand_computed_asymmetric_sample() -> None:
    """Exact values on an asymmetric sample -- a sign-flipped implementation cannot pass.

    Replaces a bare monotonicity assertion, which held for a sign-flipped
    implementation too and therefore protected nothing.
    """
    returns = np.array([[0.10, 0.05, 0.0, -0.02, -0.30]])
    # losses sorted: [-0.10, -0.05, 0.0, 0.02, 0.30]; linear-interp 95% quantile sits
    # at index 3.8 -> 0.02 + 0.8*(0.30-0.02) = 0.244; ES is the mean of losses >= it.
    var95, es95 = var_es(returns, 0.95)
    assert var95 == pytest.approx(0.244, abs=1e-12)
    assert es95 == pytest.approx(0.30, abs=1e-12)
    # A sign-flipped implementation would report the 95% quantile of *returns* (0.09).
    assert var95 != pytest.approx(0.09, abs=1e-3)
    var99, es99 = var_es(returns, 0.99)
    assert es99 >= var99 >= var95


def test_var_es_rejects_invalid_level() -> None:
    returns = np.zeros((2, 3))
    for level in (1.5, 0.0, 1.0, -0.1):
        with pytest.raises(ValueError, match="level must be in"):
            var_es(returns, level)


# --------------------------------------------------------------------------- #
# d4_tail_table
# --------------------------------------------------------------------------- #


def test_d4_tail_table_returns_finite_numbers_for_every_strategy() -> None:
    table = d4_tail_table(_plausible_ensemble())
    assert set(table) == {"eqw_factors", "sixty_forty", "endowment_proxy", "momentum", "carry"}
    for strategy_id, metrics in table.items():
        assert set(metrics) == {"var_95", "es_95", "var_99", "es_99"}
        for value in metrics.values():
            assert np.isfinite(value), f"{strategy_id} produced a non-finite metric"


def test_every_d4_strategy_has_a_positive_loss_magnitude() -> None:
    """The module's own stated convention, on an ensemble with realistic LEVELS.

    A negative VaR here means a strategy's pooled loss distribution is dominated by a
    positive constant -- the signature of a rate/spread level being summed as if it
    were a return. This is the assertion the old zero-mean N(0, 0.02) fixture could
    not make.
    """
    table = d4_tail_table(_plausible_ensemble())
    for strategy_id, metrics in table.items():
        for key, value in metrics.items():
            assert value > 0.0, f"{strategy_id}.{key} = {value} is not a positive loss magnitude"


def test_d4_tail_table_default_strategies_is_the_loaded_object(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """M5: the default set is the *same object* the tail auxiliary loss will load."""
    captured: list[tuple[Strategy, ...]] = []
    real = tails.load_d4_strategies

    def spy() -> tuple[Strategy, ...]:
        result = real()
        captured.append(result)
        return result

    monkeypatch.setattr(tails, "load_d4_strategies", spy)
    d4_tail_table(_plausible_ensemble(n_paths=4, months=18))
    assert captured, "d4_tail_table did not resolve its default strategy set"
    assert captured[0] is load_d4_strategies()


# --------------------------------------------------------------------------- #
# momentum rule
# --------------------------------------------------------------------------- #


def _momentum(lookback: int = 12, skip: int = 1) -> Strategy:
    return Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=lookback,
        rule="momentum_12_1",
        params={"target_series": "equity_mkt", "skip_months": skip},
        notes="",
    )


def test_momentum_fully_invested_on_monotonic_rise() -> None:
    paths = np.zeros((2, 20, len(_FACTOR_NAMES)), dtype=np.float64)
    paths[:, :, _FACTOR_NAMES.index("equity_mkt")] = 0.01
    ensemble = _make_ensemble(paths)
    returns = strategy_returns(ensemble, _momentum(), _DERIVED)
    equity = ensemble.factor("equity_mkt")
    np.testing.assert_allclose(returns[:, 12:], equity[:, 12:])


def test_momentum_flat_on_monotonic_fall() -> None:
    paths = np.zeros((2, 20, len(_FACTOR_NAMES)), dtype=np.float64)
    paths[:, :, _FACTOR_NAMES.index("equity_mkt")] = -0.01
    ensemble = _make_ensemble(paths)
    returns = strategy_returns(ensemble, _momentum(), _DERIVED)
    np.testing.assert_allclose(returns[:, 12:], 0.0)


def test_momentum_warmup_is_flat() -> None:
    paths = np.ones((2, 20, len(_FACTOR_NAMES)), dtype=np.float64) * 0.01
    ensemble = _make_ensemble(paths)
    returns = strategy_returns(ensemble, _momentum(), _DERIVED)
    np.testing.assert_allclose(returns[:, :12], 0.0)


def test_momentum_warmup_length_follows_the_lookback_field() -> None:
    """FINDING 4: the rule is driven by Strategy.lookback, the single declaration."""
    paths = np.ones((2, 20, len(_FACTOR_NAMES)), dtype=np.float64) * 0.01
    ensemble = _make_ensemble(paths)
    returns = strategy_returns(ensemble, _momentum(lookback=6), _DERIVED)
    np.testing.assert_allclose(returns[:, :6], 0.0)
    np.testing.assert_allclose(returns[:, 6:], ensemble.factor("equity_mkt")[:, 6:])


def test_momentum_without_lookback_raises() -> None:
    paths = np.ones((2, 20, len(_FACTOR_NAMES)), dtype=np.float64) * 0.01
    ensemble = _make_ensemble(paths)
    strategy = Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=None,
        rule="momentum_12_1",
        params={"target_series": "equity_mkt", "skip_months": 1},
        notes="",
    )
    with pytest.raises(StrategyError, match="lookback"):
        strategy_returns(ensemble, strategy, _DERIVED)


def test_momentum_without_target_series_raises() -> None:
    """FINDING 5/7: no code-side default target factor."""
    paths = np.ones((2, 20, len(_FACTOR_NAMES)), dtype=np.float64) * 0.01
    ensemble = _make_ensemble(paths)
    strategy = Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=12,
        rule="momentum_12_1",
        params={"skip_months": 1},
        notes="",
    )
    with pytest.raises(StrategyError, match="target_series"):
        strategy_returns(ensemble, strategy, _DERIVED)


def test_momentum_without_skip_months_raises() -> None:
    paths = np.ones((2, 20, len(_FACTOR_NAMES)), dtype=np.float64) * 0.01
    ensemble = _make_ensemble(paths)
    strategy = Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=12,
        rule="momentum_12_1",
        params={"target_series": "equity_mkt"},
        notes="",
    )
    with pytest.raises(StrategyError, match="skip_months"):
        strategy_returns(ensemble, strategy, _DERIVED)


# --------------------------------------------------------------------------- #
# carry rule
# --------------------------------------------------------------------------- #


def _carry() -> Strategy:
    return Strategy(
        strategy_id="test_carry",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=None,
        rule="term_structure_carry",
        params={
            "long_series": "govt_tr_10y",
            "funding_series": "cash_tr_1m",
            "long_weight": 1.0,
            "funding_weight": -1.0,
        },
        notes="",
    )


def test_carry_is_the_stated_spread_when_rates_are_flat() -> None:
    """Flat 3% long yield funded at flat 1%: 0.01*(3-1)/12 per month after warm-up."""
    ensemble = _level_ensemble(
        {"ust_10y": [3.0] * 6, "policy_rate": [1.0] * 6},
    )
    returns = strategy_returns(ensemble, _carry(), _DERIVED)
    assert returns[0, 0] == 0.0  # warm-up month
    np.testing.assert_allclose(returns[0, 1:], 0.01 * 2.0 / 12.0, rtol=0, atol=1e-15)


def test_carry_loses_when_the_long_leg_sells_off() -> None:
    ensemble = _level_ensemble(
        {"ust_10y": [3.0, 3.6, 4.2], "policy_rate": [1.0, 1.0, 1.0]},
    )
    returns = strategy_returns(ensemble, _carry(), _DERIVED)
    assert np.all(returns[0, 1:] < 0.0), returns[0]


def test_carry_without_a_sealed_leg_raises() -> None:
    ensemble = _level_ensemble({"ust_10y": [3.0, 3.0], "policy_rate": [1.0, 1.0]})
    strategy = Strategy(
        strategy_id="test_carry",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=None,
        rule="term_structure_carry",
        params={"long_series": "govt_tr_10y", "long_weight": 1.0, "funding_weight": -1.0},
        notes="",
    )
    with pytest.raises(StrategyError, match="funding_series"):
        strategy_returns(ensemble, strategy, _DERIVED)


def test_unknown_rule_raises_at_metric_time() -> None:
    ensemble = _level_ensemble({"equity_mkt": [0.01, 0.01]})
    strategy = Strategy(
        strategy_id="test",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=None,
        rule="not_a_rule",
        params={},
        notes="",
    )
    with pytest.raises(StrategyError, match="not implemented"):
        strategy_returns(ensemble, strategy, _DERIVED)


def test_unknown_kind_raises() -> None:
    ensemble = _level_ensemble({"equity_mkt": [0.01, 0.01]})
    strategy = Strategy(
        strategy_id="test",
        kind="not_a_kind",
        weights={},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )
    with pytest.raises(StrategyError, match="unknown kind"):
        strategy_returns(ensemble, strategy, _DERIVED)
