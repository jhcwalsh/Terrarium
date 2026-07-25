"""WP2.1b Task 2 acceptance: D4 strategy return paths and historical VaR/ES.

Scope discipline (see ``ah/eval/metrics/tails.py`` module docstring): this covers
only strategy_returns/var_es/d4_tail_table. Elicitability, Kupiec/Christoffersen
backtests, and tail-dependence coefficients are WP2.2 scope and are not tested here.
"""

from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pytest
from numpy.random import PCG64, Generator

from ah.eval.metrics.tails import d4_tail_table, strategy_returns, var_es
from ah.gen.base import Ensemble, EnsembleMeta
from ah.strategies import Strategy

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


def _make_ensemble(paths: np.ndarray, factor_names: list[str] | None = None) -> Ensemble:
    names = factor_names if factor_names is not None else _FACTOR_NAMES
    n_paths, months, _ = paths.shape
    return Ensemble(paths, list(names), EnsembleMeta("fake-v0", "v1", 0, n_paths, months))


# --------------------------------------------------------------------------- #
# strategy_returns: static_weights
# --------------------------------------------------------------------------- #


def test_strategy_returns_static_weights_closed_form() -> None:
    n_paths, months = 3, 5
    paths = np.zeros((n_paths, months, len(_FACTOR_NAMES)), dtype=np.float64)
    # equity_mkt constant 0.02, ust_10y constant 0.01, everything else 0
    paths[:, :, _FACTOR_NAMES.index("equity_mkt")] = 0.02
    paths[:, :, _FACTOR_NAMES.index("ust_10y")] = 0.01
    ensemble = _make_ensemble(paths)

    strategy = Strategy(
        strategy_id="test_sixty_forty",
        kind="static_weights",
        weights={"equity_mkt": 0.6, "ust_10y": 0.4},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy)
    expected = 0.6 * 0.02 + 0.4 * 0.01
    assert returns.shape == (n_paths, months)
    np.testing.assert_allclose(returns, expected)


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
    returns = strategy_returns(ensemble, strategy)
    expected = 0.5 * values[0] + 0.5 * values[1]
    np.testing.assert_allclose(returns, expected)


# --------------------------------------------------------------------------- #
# var_es
# --------------------------------------------------------------------------- #


def test_var_es_matches_analytic_normal_within_tolerance() -> None:
    mu, sigma = 0.005, 0.04
    n = 2_000_000
    rng = Generator(PCG64(12345))
    returns = rng.normal(loc=mu, scale=sigma, size=(1, n))

    tol = 0.002  # absolute, in return units; large-sample historical quantile convergence
    for level in (0.95, 0.99):
        var, es = var_es(returns, level)
        z = NormalDist().inv_cdf(level)
        analytic_var = -mu + sigma * z
        # ES for a normal loss distribution: E[loss | loss >= VaR] = -mu + sigma*phi(z)/(1-level)
        phi_z = NormalDist().pdf(z)
        analytic_es = -mu + sigma * phi_z / (1 - level)
        assert var == pytest.approx(analytic_var, abs=tol)
        assert es == pytest.approx(analytic_es, abs=tol)


def test_var_es_is_monotone() -> None:
    rng = Generator(PCG64(7))
    returns = rng.normal(loc=0.0, scale=0.03, size=(50, 24))
    var95, _es95 = var_es(returns, 0.95)
    var99, es99 = var_es(returns, 0.99)
    assert es99 >= var99 >= var95


def test_var_es_rejects_invalid_level() -> None:
    returns = np.zeros((2, 3))
    with pytest.raises(ValueError):
        var_es(returns, 1.5)


# --------------------------------------------------------------------------- #
# d4_tail_table
# --------------------------------------------------------------------------- #


def test_d4_tail_table_returns_finite_numbers_for_every_strategy() -> None:
    n_paths, months = 20, 36
    rng = Generator(PCG64(99))
    paths = rng.normal(loc=0.0, scale=0.02, size=(n_paths, months, len(_FACTOR_NAMES)))
    ensemble = _make_ensemble(paths)

    table = d4_tail_table(ensemble)
    assert set(table) == {"eqw_factors", "sixty_forty", "endowment_proxy", "momentum", "carry"}
    for strategy_id, metrics in table.items():
        assert set(metrics) == {"var_95", "es_95", "var_99", "es_99"}
        for value in metrics.values():
            assert np.isfinite(value), f"{strategy_id} produced a non-finite metric"


# --------------------------------------------------------------------------- #
# momentum rule
# --------------------------------------------------------------------------- #


def test_momentum_fully_invested_on_monotonic_rise() -> None:
    n_paths, months = 2, 20
    paths = np.zeros((n_paths, months, len(_FACTOR_NAMES)), dtype=np.float64)
    paths[:, :, _FACTOR_NAMES.index("equity_mkt")] = 0.01  # constant positive monthly return
    ensemble = _make_ensemble(paths)

    strategy = Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=12,
        rule="momentum_12_1",
        params={"lookback_months": 12, "skip_months": 1},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy)
    equity = ensemble.factor("equity_mkt")
    # after the 12-month warm-up, fully invested -> realized return equals the factor's own path
    np.testing.assert_allclose(returns[:, 12:], equity[:, 12:])


def test_momentum_flat_on_monotonic_fall() -> None:
    n_paths, months = 2, 20
    paths = np.zeros((n_paths, months, len(_FACTOR_NAMES)), dtype=np.float64)
    paths[:, :, _FACTOR_NAMES.index("equity_mkt")] = -0.01  # constant negative monthly return
    ensemble = _make_ensemble(paths)

    strategy = Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=12,
        rule="momentum_12_1",
        params={"lookback_months": 12, "skip_months": 1},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy)
    np.testing.assert_allclose(returns[:, 12:], 0.0)


def test_momentum_warmup_is_flat() -> None:
    n_paths, months = 2, 20
    paths = np.ones((n_paths, months, len(_FACTOR_NAMES)), dtype=np.float64) * 0.01
    ensemble = _make_ensemble(paths)
    strategy = Strategy(
        strategy_id="test_momentum",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=12,
        rule="momentum_12_1",
        params={"lookback_months": 12, "skip_months": 1},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy)
    np.testing.assert_allclose(returns[:, :12], 0.0)


# --------------------------------------------------------------------------- #
# carry rule
# --------------------------------------------------------------------------- #


def test_carry_is_the_stated_spread_every_month() -> None:
    n_paths, months = 3, 6
    paths = np.zeros((n_paths, months, len(_FACTOR_NAMES)), dtype=np.float64)
    paths[:, :, _FACTOR_NAMES.index("ust_10y")] = 0.03
    paths[:, :, _FACTOR_NAMES.index("policy_rate")] = 0.01
    ensemble = _make_ensemble(paths)

    strategy = Strategy(
        strategy_id="test_carry",
        kind="rule",
        weights={},
        rebalance="monthly",
        lookback=None,
        rule="term_structure_carry",
        params={"long_weight": 1.0, "funding_weight": -1.0},
        notes="",
    )
    returns = strategy_returns(ensemble, strategy)
    np.testing.assert_allclose(returns, 0.02)
