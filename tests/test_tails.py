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

import ast
import math
from collections.abc import Mapping
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest
from numpy.random import PCG64, Generator

from ah.eval.metrics import tails
from ah.eval.metrics.tails import (
    _chi2_sf,
    _historical_strategy_returns,
    build_tails_suite,
    christoffersen_conditional_coverage,
    christoffersen_independence,
    d4_tail_table,
    derived_series_values,
    elicitability_score,
    exceedance_indicator,
    kupiec_pof,
    strategy_returns,
    tail_dependence_lower,
    tail_dependence_upper,
    var_es,
)
from ah.eval.reference import (
    CROSS_BLOCK_STATS,
    STRATEGY_STATS,
    ReferenceStats,
)
from ah.eval.reference import (
    tail_dependence_lower as reference_tail_dependence_lower,
)
from ah.eval.reference import (
    tail_dependence_upper as reference_tail_dependence_upper,
)
from ah.factors import load_manifest
from ah.gen.base import Ensemble, EnsembleMeta, UnknownFactorError
from ah.strategies import (
    DerivedSeries,
    Strategy,
    StrategyError,
    load_d4_strategies,
    load_derived_series,
)

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
# Fix pass 2, MINOR 6 -- strategies and derived series must come from the same source
# --------------------------------------------------------------------------- #


def test_d4_tail_table_requires_derived_when_strategies_given_explicitly() -> None:
    """Passing `strategies` from a non-default file without pairing `derived` would
    silently evaluate it against the DEFAULT file's transforms -- reject it instead."""
    strategies = load_d4_strategies()
    with pytest.raises(StrategyError, match="derived"):
        d4_tail_table(_plausible_ensemble(n_paths=2, months=15), strategies=strategies)


def test_d4_tail_table_requires_strategies_when_derived_given_explicitly() -> None:
    """Gap 2 fix: symmetric guard. Passing `derived` from a non-default file without
    pairing `strategies` would silently pair it with the DEFAULT file's strategies --
    reject it instead."""
    derived = load_derived_series()
    with pytest.raises(StrategyError, match="strategies"):
        d4_tail_table(_plausible_ensemble(n_paths=2, months=15), derived=derived)


def test_d4_tail_table_pairs_explicit_strategies_with_matching_derived(tmp_path: Path) -> None:
    """A strategy and derived-series pair loaded from the SAME non-default file must
    be usable together, and must produce different numbers than pairing the same
    strategy with the DEFAULT file's derived series -- proving the pairing matters
    rather than being accepted vacuously."""
    custom = tmp_path / "pre-registration.yaml"
    custom.write_text(
        "derived_series:\n"
        "  govt_tr_10y:\n"
        "    from: ust_10y\n"
        "    transform: bond_total_return\n"
        "    params: {duration_years: 3.0}\n"
        '    formula: "r_t = 0.01 * ( y_{t-1}/12 - D*(y_t - y_{t-1}) )"\n'
        "    notes: fixture, deliberately a different duration than the default file\n"
        "d4_strategies:\n"
        "  only:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 0.6, govt_tr_10y: 0.4}\n"
        "    params: {}\n"
        "    notes: fixture\n",
        encoding="utf-8",
    )
    strategies = load_d4_strategies(custom)
    derived = load_derived_series(custom)
    ensemble = _plausible_ensemble(n_paths=5, months=24)

    table = d4_tail_table(ensemble, strategies=strategies, derived=derived)

    expected_returns = strategy_returns(ensemble, strategies[0], derived)
    expected_var95, expected_es95 = var_es(expected_returns, 0.95)
    assert table["only"]["var_95"] == pytest.approx(expected_var95)
    assert table["only"]["es_95"] == pytest.approx(expected_es95)

    # Same strategy, but paired (wrongly) with the DEFAULT file's derived series
    # (duration_years=8.5, not this fixture's 3.0) -- must disagree, or this test
    # would not be able to catch the mismatched-source defect at all.
    mismatched_returns = strategy_returns(ensemble, strategies[0], load_derived_series())
    mismatched_var95, _ = var_es(mismatched_returns, 0.95)
    assert mismatched_var95 != pytest.approx(expected_var95)


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


# --------------------------------------------------------------------------- #
# Fix pass 2, MINOR 8 -- _lagged_carry_minus_duration dtype/shape robustness
# --------------------------------------------------------------------------- #


def test_lagged_carry_minus_duration_rejects_non_2d_input() -> None:
    """Previously an IndexError from `level.shape[1]`; now a named StrategyError."""
    with pytest.raises(StrategyError, match="2-D"):
        tails._lagged_carry_minus_duration(np.array([4.0, 4.5, 4.2]), 8.5)


def test_lagged_carry_minus_duration_output_is_always_float64() -> None:
    level_int = np.array([[4, 5, 6]], dtype=np.int64)
    result = tails._lagged_carry_minus_duration(level_int, 8.5)
    assert result.dtype == np.float64


def test_lagged_carry_minus_duration_computes_at_float64_precision_for_float32_input() -> None:
    """Under NumPy's NEP 50 promotion rules, `float32_array / python_float` stays
    float32 -- so computing `previous`/`change` from the raw (possibly float32) input,
    only casting the zeroed `out` array to float64, silently loses precision. The
    fixed function casts the whole input to float64 before any arithmetic."""
    raw = [4.123456789, 4.567891234, 4.234567891]
    level32 = np.array([raw], dtype=np.float32)

    # What the function must match: upcast to float64 first, then compute.
    upcast_first = tails._lagged_carry_minus_duration(level32.astype(np.float64), 8.5)

    # What the OLD implementation computed: `previous`/`change` sliced straight from
    # the float32 array, so under NEP 50 the division/multiplication stay float32.
    previous32 = level32[:, :-1]
    change32 = level32[:, 1:] - previous32
    old_out = np.zeros((1, len(raw)), dtype=np.float64)
    old_out[:, 1:] = 0.01 * (previous32 / 12.0 - 8.5 * change32)

    result = tails._lagged_carry_minus_duration(level32, 8.5)

    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, upcast_first)
    # Confirms this test is not vacuous: the old code path really did disagree.
    assert not np.array_equal(result, old_out)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: elicitability_score
# --------------------------------------------------------------------------- #


def test_elicitability_score_is_minimized_at_the_true_var_es_pair() -> None:
    """The property that makes this a strictly consistent scoring rule: on a fixed
    sample, the (VaR, ES) pair var_es() itself computes scores strictly better (lower)
    than every mis-specified pair tried -- both directions, both over- and
    under-stating each of VaR and ES independently and jointly. A test that only
    checked the score is finite would prove nothing about consistency."""
    rng = Generator(PCG64(2026))
    returns = rng.standard_t(5, size=20000) * 0.02  # fat-tailed, deterministic sample
    level = 0.95
    true_var, true_es = var_es(returns, level)
    true_score = elicitability_score(returns, true_var, true_es, level)
    assert np.isfinite(true_score)

    for dv, de in [
        (1.5, 1.0),
        (0.5, 1.0),
        (1.0, 1.5),
        (1.0, 0.5),
        (1.3, 1.3),
        (0.7, 0.7),
        (1.2, 0.8),
    ]:
        mis_score = elicitability_score(returns, true_var * dv, true_es * de, level)
        assert mis_score > true_score, (dv, de, mis_score, true_score)


def test_elicitability_score_orientation_is_lower_is_better_by_construction() -> None:
    """Restates the property above at a single mis-specified point, explicitly framed
    as an orientation check: a flipped sign would make this assertion fail."""
    rng = Generator(PCG64(7))
    returns = rng.normal(0.0, 0.03, size=5000)
    var, es = var_es(returns, 0.95)
    correct = elicitability_score(returns, var, es, 0.95)
    wrong = elicitability_score(returns, var * 3.0, es * 3.0, 0.95)
    assert correct < wrong


def test_elicitability_score_nan_when_es_not_positive() -> None:
    returns = np.array([0.01, -0.02, 0.03])
    assert math.isnan(elicitability_score(returns, 0.02, 0.0, 0.95))
    assert math.isnan(elicitability_score(returns, 0.02, -1.0, 0.95))


def test_elicitability_score_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="level"):
        elicitability_score(np.array([0.01]), 0.01, 0.02, 1.5)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: chi-square survival function (df 1, 2 only)
# --------------------------------------------------------------------------- #


def test_chi2_sf_matches_known_critical_values() -> None:
    """The standard chi-square 95th-percentile critical values: sf(3.841459, 1) and
    sf(5.991465, 2) are both ~0.05 (textbook values, e.g. any statistics reference
    table)."""
    assert _chi2_sf(3.841459, 1) == pytest.approx(0.05, abs=1e-4)
    assert _chi2_sf(5.991465, 2) == pytest.approx(0.05, abs=1e-4)


def test_chi2_sf_at_zero_is_one() -> None:
    assert _chi2_sf(0.0, 1) == pytest.approx(1.0)
    assert _chi2_sf(0.0, 2) == pytest.approx(1.0)


def test_chi2_sf_rejects_unsupported_df() -> None:
    with pytest.raises(ValueError, match="df"):
        _chi2_sf(1.0, 3)


def test_chi2_sf_rejects_negative_x() -> None:
    with pytest.raises(ValueError, match="x"):
        _chi2_sf(-1.0, 1)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: kupiec_pof
# --------------------------------------------------------------------------- #


def test_kupiec_pof_hand_computed_on_a_small_fixed_sequence() -> None:
    """T=10, x=2 exceedances (20%) at level=0.95 (alpha=0.05): LR = 2.7955733336530155,
    p-value = 0.09452495105441394 -- hand-computed via the closed form in
    pre-registration.yaml's kupiec_pof_estimator (independently, offline, not by
    calling this module)."""
    indicator = np.array([False] * 8 + [True] * 2)
    lr, pvalue = kupiec_pof(indicator, 0.95)
    assert lr == pytest.approx(2.7955733336530155, abs=1e-9)
    assert pvalue == pytest.approx(0.09452495105441394, abs=1e-9)


def test_kupiec_pof_is_near_zero_at_exactly_the_expected_rate() -> None:
    """T=20, x=1: p_hat = 1/20 = 0.05 = alpha EXACTLY, so LR is EXACTLY 0 (both terms
    of the log-likelihood ratio are identical), not merely small."""
    indicator = np.array([False] * 19 + [True])
    lr, pvalue = kupiec_pof(indicator, 0.95)
    assert lr == pytest.approx(0.0, abs=1e-9)
    assert pvalue == pytest.approx(1.0, abs=1e-9)


def test_kupiec_pof_rejects_at_double_the_rate_on_a_large_sample() -> None:
    """T=1000, x=100 (10%, double the nominal 5%): large LR, tiny p-value -- rejects
    H0 at any conventional significance level."""
    rng = Generator(PCG64(11))
    n1_positions = rng.choice(1000, size=100, replace=False)
    indicator = np.zeros(1000, dtype=bool)
    indicator[n1_positions] = True
    lr, pvalue = kupiec_pof(indicator, 0.95)
    assert lr > 3.841459  # exceeds the chi-square(1) 95% critical value
    assert pvalue < 0.001


def test_kupiec_pof_empty_sequence_is_nan() -> None:
    lr, pvalue = kupiec_pof(np.array([], dtype=bool), 0.95)
    assert math.isnan(lr)
    assert math.isnan(pvalue)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: christoffersen_independence / christoffersen_conditional_coverage
# --------------------------------------------------------------------------- #


def test_christoffersen_independence_near_zero_on_an_iid_sequence() -> None:
    rng = Generator(PCG64(3))
    indicator = rng.random(4000) < 0.05
    lr, pvalue = christoffersen_independence(indicator)
    # An iid Bernoulli sequence has no genuine transition-probability dependence on
    # the previous state; at n=4000 the LR statistic should sit comfortably below its
    # own chi-square(1) 95% critical value (3.841459) essentially always.
    assert lr < 3.841459
    assert pvalue > 0.05


def test_christoffersen_independence_large_on_a_clustered_sequence() -> None:
    """All exceedances consecutive -- the textbook clustering failure mode."""
    n = 2000
    indicator = np.zeros(n, dtype=bool)
    indicator[900:1000] = True  # one contiguous 100-month block of exceedances
    lr, pvalue = christoffersen_independence(indicator)
    assert lr > 3.841459
    assert pvalue < 0.01


def test_christoffersen_independence_short_sequence_is_nan() -> None:
    lr, pvalue = christoffersen_independence(np.array([True]))
    assert math.isnan(lr)
    assert math.isnan(pvalue)


def test_christoffersen_conditional_coverage_is_kupiec_plus_independence() -> None:
    rng = Generator(PCG64(5))
    indicator = rng.random(3000) < 0.05
    lr_pof, _ = kupiec_pof(indicator, 0.95)
    lr_ind, _ = christoffersen_independence(indicator)
    lr_cc, pvalue_cc = christoffersen_conditional_coverage(indicator, 0.95)
    assert lr_cc == pytest.approx(lr_pof + lr_ind, abs=1e-9)
    assert pvalue_cc == pytest.approx(_chi2_sf(lr_cc, df=2), abs=1e-12)


def test_christoffersen_conditional_coverage_nan_when_a_component_is_nan() -> None:
    lr, pvalue = christoffersen_conditional_coverage(np.array([], dtype=bool), 0.95)
    assert math.isnan(lr)
    assert math.isnan(pvalue)


def test_exceedance_indicator_orientation() -> None:
    returns = np.array([0.10, -0.05, -0.30, 0.02])
    indicator = exceedance_indicator(returns, var=0.04)
    np.testing.assert_array_equal(indicator, [False, True, True, False])


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: tail_dependence_lower / tail_dependence_upper (re-exported from
# ah.eval.reference -- same function objects, tested for numeric ground truth there;
# this only confirms the re-export)
# --------------------------------------------------------------------------- #


def test_tail_dependence_functions_are_the_reference_module_objects() -> None:
    assert tail_dependence_lower is reference_tail_dependence_lower
    assert tail_dependence_upper is reference_tail_dependence_upper


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: _historical_strategy_returns
# --------------------------------------------------------------------------- #


def _reference_with_historical_series(series: Mapping[str, pd.Series]) -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=(),
        vintage_id="v",
        n_resamples=1,
        seed=0,
        missing_factors=(),
        historical_series=series,
    )


def test_historical_strategy_returns_reuses_strategy_returns_on_the_aligned_legs() -> None:
    dates = pd.date_range("2000-01-01", periods=5, freq="MS")
    equity = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00], index=dates)
    ust = pd.Series([4.0, 4.5, 4.2, 4.0, 4.1], index=dates)
    reference = _reference_with_historical_series({"equity_mkt": equity, "ust_10y": ust})
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
    result = _historical_strategy_returns(reference, strategy, _DERIVED)
    assert result is not None
    assert result.shape == (1, 5)

    # Must equal strategy_returns() applied directly to the same aligned data -- the
    # "no second route" requirement, checked by construction rather than assumed.
    expected_ensemble = Ensemble(
        paths=np.stack([equity.to_numpy(), ust.to_numpy()], axis=-1)[np.newaxis, :, :],
        factor_names=["equity_mkt", "ust_10y"],
        meta=EnsembleMeta("x", "v", 0, 1, 5),
    )
    expected = strategy_returns(expected_ensemble, strategy, _DERIVED)
    np.testing.assert_allclose(result, expected)


def test_historical_strategy_returns_none_when_a_leg_factor_is_absent() -> None:
    """The commodities case: a strategy needing a factor with no historical series at
    all reports None (the metric layer then reports NaN), never raises."""
    reference = _reference_with_historical_series({})
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
    assert _historical_strategy_returns(reference, strategy, {}) is None


def test_historical_strategy_returns_none_on_empty_overlap() -> None:
    dates_a = pd.date_range("1990-01-01", periods=3, freq="MS")
    dates_b = pd.date_range("2010-01-01", periods=3, freq="MS")
    reference = _reference_with_historical_series(
        {
            "equity_mkt": pd.Series([0.01, 0.02, 0.03], index=dates_a),
            "ust_10y": pd.Series([4.0, 4.1, 4.2], index=dates_b),
        }
    )
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
    assert _historical_strategy_returns(reference, strategy, _DERIVED) is None


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: build_tails_suite / register_tails_suite -- wiring
# --------------------------------------------------------------------------- #


def test_every_tails_metric_name_can_carry_a_sealed_threshold() -> None:
    """Mirrors ``test_every_monthly_metric_name_is_a_registered_reference_statistic``
    (test_monthly.py) and ``test_every_metric_is_registered_at_its_dn1_1_tier``
    (test_horizon.py): every metric this suite emits must be keyed under a name
    ``ah.eval.prereg`` can validate, or an entry authored under it would break every
    battery run once sealed."""
    manifest = load_manifest()
    reference = _reference_with_historical_series({})
    specs = build_tails_suite(manifest, reference)
    assert specs
    for spec in specs:
        assert spec.tier == "monthly"
        assert spec.suite == "tails"
        if "~" in spec.name:
            stat = spec.name.split(".", 1)[1]
            assert stat in CROSS_BLOCK_STATS, spec.name
        else:
            strategy_id, stat = spec.name.split(".", 1)
            assert strategy_id in {s.strategy_id for s in load_d4_strategies()}, spec.name
            assert stat in STRATEGY_STATS, spec.name


def test_build_tails_suite_covers_every_d4_strategy_and_stat() -> None:
    manifest = load_manifest()
    reference = _reference_with_historical_series({})
    specs = build_tails_suite(manifest, reference)
    names = {s.name for s in specs}
    for strategy in load_d4_strategies():
        for stat in STRATEGY_STATS:
            assert f"{strategy.strategy_id}.{stat}" in names


def test_build_tails_suite_never_crashes_when_a_strategy_leg_is_absent_everywhere() -> None:
    """Every metric must NaN, not raise, when the ensemble and the reference both
    lack a strategy's legs (e.g. commodities) -- THE ONE NaN RULE, and the same
    absent-factor convention every other metric suite in this platform follows."""
    manifest = load_manifest()
    reference = _reference_with_historical_series({})
    specs = build_tails_suite(manifest, reference)
    ensemble = Ensemble(
        paths=np.zeros((2, 6, 1), dtype=np.float64),
        factor_names=["equity_mkt"],
        meta=EnsembleMeta("x", "v", 0, 2, 6),
    )
    for spec in specs:
        value = spec.fn(ensemble)  # must not raise
        assert isinstance(value, float)


def test_generating_less_never_improves_a_backtest_metric() -> None:
    """A generator that simply omits a D4 strategy's leg must not score BETTER than
    one that supplies plausible data for it -- the "gamed by generating less"
    failure mode this platform's other suites already guard against
    (cross_block_corr_matrix_distance, drawdown episode floors, decade-frequency
    windowing). Omitting a leg must NaN the metric (which THE ONE NaN RULE already
    fails against any enforce bound), never report a friendlier number."""
    manifest = load_manifest()
    ensemble_full = _plausible_ensemble(seed=999, n_paths=50, months=60)
    dates = pd.date_range("2000-01-01", periods=60, freq="MS")
    reference = _reference_with_historical_series(
        {
            "equity_mkt": pd.Series(ensemble_full.factor("equity_mkt")[0], index=dates),
            "ust_10y": pd.Series(ensemble_full.factor("ust_10y")[0], index=dates),
            "hy_spread": pd.Series(ensemble_full.factor("hy_spread")[0], index=dates),
            "policy_rate": pd.Series(ensemble_full.factor("policy_rate")[0], index=dates),
            "smb": pd.Series(ensemble_full.factor("smb")[0], index=dates),
            "hml": pd.Series(ensemble_full.factor("hml")[0], index=dates),
            "mom": pd.Series(ensemble_full.factor("mom")[0], index=dates),
        }
    )
    full_specs = {s.name: s for s in build_tails_suite(manifest, reference)}

    # A generator that omits ust_10y entirely (so sixty_forty/carry cannot be evaluated).
    reduced_factor_names = [f for f in _FACTOR_NAMES if f != "ust_10y"]
    reduced_paths = np.delete(ensemble_full.paths, _FACTOR_NAMES.index("ust_10y"), axis=2)
    ensemble_reduced = Ensemble(
        reduced_paths, reduced_factor_names, EnsembleMeta("x", "v", 0, *reduced_paths.shape[:2])
    )

    for name in ("sixty_forty.var_95", "sixty_forty.elicitability_score", "carry.var_95"):
        omitted_value = full_specs[name].fn(ensemble_reduced)
        assert math.isnan(omitted_value), f"{name} did not NaN when its leg was omitted"

    # ------------------------------------------------------------------ #
    # Vector 2 (Critical 1): a generator emitting LESS TAIL must not score better on
    # `elicitability_score`. The historical (VaR, ES) pair is the target; a generated
    # ensemble whose own (VaR, ES) is a fraction of history's must score STRICTLY
    # WORSE than one that reproduces it, and a generator emitting (near-)nothing must
    # not be the global optimum. See
    # `test_elicitability_metric_is_minimized_by_matching_history` for the full
    # four-way ordering; this is the "generating less" face of the same property.
    # ------------------------------------------------------------------ #
    elicitability = full_specs["sixty_forty.elicitability_score"]
    matching = elicitability.fn(ensemble_full)
    shrunk = elicitability.fn(_volatility_scaled(ensemble_full, 0.25))
    assert np.isfinite(matching)
    assert shrunk > matching, (shrunk, matching)

    # ------------------------------------------------------------------ #
    # Vector 3 (Important 4): halving the ENSEMBLE SIZE must not move a backtest
    # statistic or its p-value. Pooling n_paths x months observations made
    # `LR = 2*T*KL(p_hat || alpha)` scale linearly with n_paths, so running 100 paths
    # instead of 1000 divided the statistic by 10 and let a `min:` p-value floor pass
    # that the full ensemble would have failed. The reference-sample-size
    # normalization makes both invariant: the SAME paths repeated 4x are the same
    # p_hat and must give the bit-identical value.
    # ------------------------------------------------------------------ #
    tiled = Ensemble(
        np.tile(ensemble_full.paths, (4, 1, 1)),
        list(ensemble_full.factor_names),
        EnsembleMeta("x", "v", 0, ensemble_full.n_paths * 4, ensemble_full.months),
    )
    for name in (
        "sixty_forty.kupiec_pof_lr_1path",
        "sixty_forty.kupiec_pof_chi2_tail_1path",
        "sixty_forty.christoffersen_independence_lr_1path",
        "sixty_forty.christoffersen_independence_chi2_tail_1path",
        "sixty_forty.christoffersen_conditional_coverage_lr_1path",
        "sixty_forty.christoffersen_conditional_coverage_chi2_tail_1path",
    ):
        small = full_specs[name].fn(ensemble_full)
        large = full_specs[name].fn(tiled)
        assert np.isfinite(small), name
        assert large == pytest.approx(small, rel=1e-9), (name, small, large)

    # ------------------------------------------------------------------ #
    # Vector 4 (Important 6): a generator whose losses NEVER reach history's VaR gets
    # zero exceedances, and with n01 = n10 = n11 = 0 every Christoffersen
    # log-likelihood term vanishes under the 0*ln0 convention -- LR_ind = 0, p = 1.0,
    # a maximally favourable independence score for emitting nothing. Below the
    # minimum-exceedance floor the statistic must be NaN instead.
    # ------------------------------------------------------------------ #
    flat = _volatility_scaled(ensemble_full, 0.0)
    for name in (
        "sixty_forty.christoffersen_independence_lr_1path",
        "sixty_forty.christoffersen_independence_chi2_tail_1path",
        "sixty_forty.christoffersen_conditional_coverage_lr_1path",
        "sixty_forty.christoffersen_conditional_coverage_chi2_tail_1path",
    ):
        assert math.isnan(full_specs[name].fn(flat)), f"{name} rewarded a zero-tail generator"
    # Kupiec is already coercive on the same ensemble (0% observed vs 5% nominal) and
    # must keep rejecting it -- the floor above must not silently disarm it too.
    assert full_specs["sixty_forty.kupiec_pof_chi2_tail_1path"].fn(flat) < 0.05


def _volatility_scaled(ensemble: Ensemble, factor: float) -> Ensemble:
    """``ensemble`` with every factor's per-path variation about its own path mean
    scaled by ``factor`` (levels keep their mean, so a rate factor stays a plausible
    rate rather than collapsing to zero and inverting a bond leg's carry)."""
    paths = np.asarray(ensemble.paths, dtype=np.float64)
    means = paths.mean(axis=1, keepdims=True)
    scaled = means + factor * (paths - means)
    return Ensemble(
        scaled,
        list(ensemble.factor_names),
        EnsembleMeta("x", "v", 0, ensemble.n_paths, ensemble.months),
    )


# --------------------------------------------------------------------------- #
# WP2.2 Task 4 fix pass 2: the backtest reference sample size is a SEALED CONSTANT,
# never the judged ensemble's own path length (BLOCKING 2 / NEW-1)
# --------------------------------------------------------------------------- #


def test_backtest_reference_sample_size_is_pinned_not_ensemble_derived() -> None:
    """NEW-1 (WP2.2 Task 4 fix pass 2). ``_backtest_metric`` used to read
    ``reference_n`` off the GENERATED ensemble's own ``months``
    (``pooled_2d.shape[1]``), so ``LR ~ months``: a 60-month ensemble reported HALF the
    statistic (and a materially larger tail -- LR 3.84 -> 1.92 moves the tail from 0.05
    to 0.17) that a 120-month ensemble with the IDENTICAL exceedance rate reported. The
    dominant failure mode this work package exists to close -- a metric that improves
    when the generator produces less -- had not closed; it had moved from the
    ``n_paths`` axis (closed by ``_reference_scaled_lr``'s own reference-sample-size fix)
    to the ``months`` axis. ``BACKTEST_REFERENCE_MONTHS`` pins the reference length to a
    sealed constant, so two ensembles with the same per-month exceedance rate and
    transition ratios but DIFFERENT path lengths must report the bit-identical
    statistic.

    A period-5 pattern (1 exceedance every 5 months) tiled to two different total
    lengths makes ``p_hat`` EXACTLY invariant (Kupiec's statistic depends on nothing
    else, so its check below is bit-exact to ``rel=1e-9``). The transition RATIOS
    Christoffersen depends on are only ASYMPTOTICALLY invariant under this
    construction: a linear (non-circular) tiling of ``N`` period-repeats has exactly
    ``N - 1`` period-boundary transitions, not ``N`` (the final repeat's trailing
    element has no successor to transition into), so ``n01`` is short by exactly one
    count regardless of ``N`` -- a real, understood O(1/N) discretization artifact of
    this test's construction, not a defect in the code under test. At the repeat counts
    below (200 and 400) that artifact is a fraction of a percent in the LR statistic --
    comfortably inside the tolerances used here -- and utterly unlike the ~2x (100%)
    discrepancy the pre-fix ``months``-derived ``reference_n`` produced between a
    1000- and a 2000-month ensemble at the identical exceedance rate.
    """
    rng = Generator(PCG64(909))
    historical = rng.standard_t(5, size=600) * 0.02
    dates = pd.date_range("1960-01-01", periods=600, freq="MS")
    reference = _reference_with_historical_series(
        {"equity_mkt": pd.Series(historical, index=dates)}
    )
    strategy = _pure_equity_strategy()
    cache = tails._HistoricalCache(reference, {})

    period = np.array([-1.0, 0.01, 0.01, 0.01, 0.01], dtype=np.float64)  # 1-in-5 exceedance
    short = np.tile(period, 200).reshape(1, -1)  # 1000 months, 200 exceedances, p_hat = 0.2
    long = np.tile(period, 400).reshape(1, -1)  # 2000 months, 400 exceedances, p_hat = 0.2
    assert short.shape[1] != long.shape[1]

    # Kupiec depends only on the pooled exceedance count -- reps / (5*reps) = 0.2
    # exactly, at every length -- so its invariance is checked bit-exactly.
    for which in ("stat", "pvalue"):
        metric = tails._backtest_metric(strategy, cache, "kupiec", which)
        value_short = metric(_equity_ensemble(short))
        value_long = metric(_equity_ensemble(long))
        assert np.isfinite(value_short), which
        assert value_long == pytest.approx(value_short, rel=1e-9), (
            which,
            value_short,
            value_long,
        )

    # Christoffersen's transition ratios carry the O(1/N) tiling artifact described
    # above. The "stat" (LR) tolerance is loose-but-discriminating (the pre-fix bug's
    # own gap was ~100%, so 5% still cleanly separates "fixed" from "still reads
    # reference_n off the ensemble"); "pvalue" is chi2_sf of the stat and therefore
    # amplifies a small stat discrepancy exponentially, so it gets a wider -- but still
    # utterly unlike the pre-fix order-of-magnitude gap -- tolerance.
    for test in ("christoffersen_independence", "christoffersen_cc"):
        stat_metric = tails._backtest_metric(strategy, cache, test, "stat")
        stat_short = stat_metric(_equity_ensemble(short))
        stat_long = stat_metric(_equity_ensemble(long))
        assert np.isfinite(stat_short), test
        assert stat_long == pytest.approx(stat_short, rel=0.05), (test, stat_short, stat_long)

        pvalue_metric = tails._backtest_metric(strategy, cache, test, "pvalue")
        pvalue_short = pvalue_metric(_equity_ensemble(short))
        pvalue_long = pvalue_metric(_equity_ensemble(long))
        assert np.isfinite(pvalue_short), test
        assert pvalue_long == pytest.approx(pvalue_short, rel=0.5), (
            test,
            pvalue_short,
            pvalue_long,
        )


# --------------------------------------------------------------------------- #
# WP2.2 Task 4 fix pass: the elicitability METRIC (not merely the scoring rule)
# --------------------------------------------------------------------------- #


def _pure_equity_strategy() -> Strategy:
    """A one-leg strategy whose realized return IS the ``equity_mkt`` slab.

    Deliberately not one of the five sealed D4 strategies: this test needs to control
    the strategy's realized return path EXACTLY (to scale its volatility by a known
    factor), which a multi-leg strategy mixing a return factor with a duration-scaled
    level factor does not allow. The metric wiring under test is identical either way.
    """
    return Strategy(
        strategy_id="test_pure_equity",
        kind="static_weights",
        weights={"equity_mkt": 1.0},
        rebalance="monthly",
        lookback=None,
        rule=None,
        params={},
        notes="",
    )


def _equity_ensemble(values: np.ndarray) -> Ensemble:
    paths = np.asarray(values, dtype=np.float64)[:, :, np.newaxis]
    return Ensemble(
        paths, ["equity_mkt"], EnsembleMeta("x", "v", 0, paths.shape[0], paths.shape[1])
    )


def test_elicitability_metric_is_minimized_by_matching_history() -> None:
    """THE metric-level property, distinct from the scoring rule's own consistency.

    ``test_elicitability_score_is_minimized_at_the_true_var_es_pair`` varies (V, E) on
    a FIXED sample: it validates the scoring RULE, and passes under either argument
    wiring. This test varies the GENERATED SAMPLE with history fixed -- which is what
    the battery metric actually does -- and is the only thing that can tell the two
    wirings apart.

    The pre-fix wiring froze (V, E) at history's values and varied the generated
    losses, collapsing the score to ``c1 * mean((L - V)^+) + c2`` with ``c1 > 0``: a
    monotone increasing function of generated tail heaviness, minimized by a generator
    emitting IDENTICALLY ZERO. Since DN-1.1 line 95 makes this the WP2.8 auxiliary
    loss, that would have trained the generator toward zero volatility.

    The correct (Tail-GAN) direction estimates (V, E) from the GENERATED sample and
    scores them against REAL realizations, which is coercive as E -> 0 and is minimized
    exactly when the generated (VaR, ES) equals history's.
    """
    rng = Generator(PCG64(4242))
    months = 600
    historical = rng.standard_t(5, size=months) * 0.02
    dates = pd.date_range("1960-01-01", periods=months, freq="MS")
    reference = _reference_with_historical_series(
        {"equity_mkt": pd.Series(historical, index=dates)}
    )
    strategy = _pure_equity_strategy()
    metric = tails._elicitability_metric(strategy, tails._HistoricalCache(reference, {}))

    matched = rng.standard_t(5, size=(40, 120)) * 0.02  # same law as history
    score_matched = metric(_equity_ensemble(matched))
    assert np.isfinite(score_matched)

    for label, scale in (("half", 0.5), ("double", 2.0), ("near-zero", 0.01)):
        score = metric(_equity_ensemble(matched * scale))
        assert score > score_matched, (label, score, score_matched)

    # An identically-zero generator has no positive ES magnitude at all: NaN, which
    # THE ONE NaN RULE already fails against any enforce bound. Under the pre-fix
    # wiring it was finite and the single BEST score in the whole comparison.
    assert math.isnan(metric(_equity_ensemble(np.zeros((40, 120)))))


# --------------------------------------------------------------------------- #
# WP2.2 Task 4 fix pass: minimum-exceedance floor (Important 6)
# --------------------------------------------------------------------------- #


def test_christoffersen_independence_is_nan_below_the_minimum_exceedance_floor() -> None:
    """Zero exceedances leaves n01 = n10 = n11 = 0, so every log-likelihood term
    vanishes under the 0*ln(0) := 0 convention and LR_ind is -0.0 with p = 1.0 at
    EVERY sequence length -- a perfect independence score for a generator whose losses
    never reach the threshold. Below BACKTEST_MIN_EXCEEDANCES the statistic is NaN."""
    assert tails.BACKTEST_MIN_EXCEEDANCES > 1
    for n1 in range(tails.BACKTEST_MIN_EXCEEDANCES):
        indicator = np.zeros(2000, dtype=bool)
        indicator[np.arange(n1) * 97] = True
        lr, pvalue = christoffersen_independence(indicator)
        assert math.isnan(lr), n1
        assert math.isnan(pvalue), n1

    # One exceedance above the floor: defined again, not NaN for all time.
    indicator = np.zeros(2000, dtype=bool)
    indicator[np.arange(tails.BACKTEST_MIN_EXCEEDANCES) * 97] = True
    lr, pvalue = christoffersen_independence(indicator)
    assert np.isfinite(lr)
    assert np.isfinite(pvalue)


def test_christoffersen_conditional_coverage_inherits_the_exceedance_floor() -> None:
    lr, pvalue = christoffersen_conditional_coverage(np.zeros(2000, dtype=bool), 0.95)
    assert math.isnan(lr)
    assert math.isnan(pvalue)


def test_lr_statistics_are_never_negative_zero() -> None:
    """`max(x, 0.0)` returns -0.0 when x is -0.0 (Python returns the FIRST argument on
    a tie), and the battery markdown then prints `-0`. Both LR builders normalize."""
    # level=0.5 makes alpha EXACTLY 0.5 (1 - 0.95 is 0.05000000000000004, which is why
    # the "expected rate" Kupiec test above does not actually reach the tie); 10 of 20
    # is then p_hat == alpha bit-exactly, both log-likelihoods are identical, and the
    # raw statistic is -2.0 * 0.0 == -0.0.
    lr = tails._pof_lr_from_counts(10, 20, 0.5)
    assert lr == 0.0
    assert math.copysign(1.0, lr) > 0.0
    # pi01 == pi11 == pi == 0 exactly: every log-likelihood term is 0 under 0*ln0 := 0.
    lr_ind = tails._independence_lr_from_counts(100, 0, 10, 0)
    assert lr_ind == 0.0
    assert math.copysign(1.0, lr_ind) > 0.0
    scaled = tails._reference_scaled_lr(lr_ind, 110, 120)
    assert math.copysign(1.0, scaled) > 0.0


# --------------------------------------------------------------------------- #
# WP2.2 Task 4 fix pass: the historical join must be contiguous monthly (Minor)
# --------------------------------------------------------------------------- #


def test_historical_strategy_returns_raises_on_a_non_contiguous_monthly_join() -> None:
    """`_lagged_carry_minus_duration` treats adjacent rows as CONSECUTIVE months, so a
    single interior gap silently becomes a multi-month yield change scaled by duration
    8.5 -- a fabricated bond return an order of magnitude too large."""
    dates = pd.DatetimeIndex(["2000-01-01", "2000-02-01", "2000-05-01", "2000-06-01"])
    reference = _reference_with_historical_series(
        {
            "equity_mkt": pd.Series([0.01, 0.02, -0.01, 0.03], index=dates),
            "ust_10y": pd.Series([4.0, 4.5, 4.2, 4.0], index=dates),
        }
    )
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
    with pytest.raises(StrategyError, match="contiguous"):
        _historical_strategy_returns(reference, strategy, _DERIVED)


def test_build_tails_suite_raises_at_build_time_on_a_non_contiguous_historical_join() -> None:
    """MINOR 8 (WP2.2 Task 4 fix pass 2). ``_HistoricalCache`` is lazy by design (each
    strategy's historical join is built once, on first use, and memoized) and
    ``build_tails_suite`` never forced that first use -- so a real
    ``_require_contiguous_months`` gap surfaced only when SOME metric's ``.fn`` happened
    to be called mid-battery-run, aborting every OTHER suite's results for a data defect
    in one strategy's legs. ``build_tails_suite`` now warms the cache for every strategy
    eagerly, so the identical gap now raises at REGISTRATION time, before any metric is
    ever evaluated -- the same ``StrategyError`` ``_historical_strategy_returns`` always
    raised, just surfaced earlier."""
    manifest = load_manifest()
    dates = pd.DatetimeIndex(["2000-01-01", "2000-02-01", "2000-05-01", "2000-06-01"])
    reference = _reference_with_historical_series(
        {
            "equity_mkt": pd.Series([0.01, 0.02, -0.01, 0.03], index=dates),
            "ust_10y": pd.Series([4.0, 4.5, 4.2, 4.0], index=dates),
        }
    )
    with pytest.raises(StrategyError, match="contiguous"):
        build_tails_suite(manifest, reference)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: run_full_battery integration + registration bookkeeping
# --------------------------------------------------------------------------- #


def test_tails_is_registered_in_prereg_metric_suite_names() -> None:
    from ah.eval import prereg as prereg_mod

    assert "tails" in prereg_mod._METRIC_SUITE_NAMES


def test_tails_suite_registered_in_reference_dependent_suite_builders() -> None:
    from ah.eval import battery as battery_mod

    assert battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS["tails"] == (
        "ah.eval.metrics.tails",
        "build_tails_suite",
    )


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: tails.py never imports ah.eval.g2 (mirrors test_reference.py's guard)
# --------------------------------------------------------------------------- #

_TAILS_PATH = Path(__file__).resolve().parents[1] / "src" / "ah" / "eval" / "metrics" / "tails.py"


def test_tails_module_never_imports_g2_or_names_the_token() -> None:
    text = _TAILS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_TAILS_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ah.eval.g2" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "g2" not in module.split("."), module
            for alias in node.names:
                assert alias.name != "FinalEvaluationToken"
