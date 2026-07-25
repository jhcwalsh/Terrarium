"""D4 tail-fidelity metrics: strategy returns and historical VaR/ES (WP2.1b Item 1).

Computes every D4 benchmark strategy's realized return path, and historical VaR /
Expected Shortfall on it, from an :class:`~ah.gen.base.Ensemble` alone -- no
dependency on portfolio or sleeve machinery (``tests/test_tails_import_graph.py``
proves this by walking this module's imports). See
``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 1 and :mod:`ah.strategies` for the
five D4 strategy definitions this module evaluates.

Units: returns are used directly, levels only through a declared derived series.
------------------------------------------------------------------------------
There is no "treat every factor slab as a return" convention here, and there must not
be: the generator emits some factors as period returns and others as levels quoted in
percent, and summing the two inverts the sign of a bond or credit leg. Return-bearing
factors (``equity_mkt``, ``smb``, ``hml``, ``mom``, ``commodities``) are read from the
ensemble and used directly. Level/rate/spread factors (``ust_10y``, ``hy_spread``,
``policy_rate``, ...) enter a D4 portfolio **only** through a derived series declared
in ``pre-registration.yaml``'s ``derived_series`` block -- a named transform, with all
of its parameters, its percent-to-decimal conversion, its lag and its warm-up stated
in the sealed file. This module implements those transforms; the sealed file defines
them, and if the two disagree the sealed file wins. Formalizing the full state-space
unit contract for the generator itself (softplus-space rates/spreads vs. return-space
market factors, log-space prices) remains WP2.8's ``constraints.py``.

Everything a strategy needs is sealed data, not a constant here: a rule's target
series arrive as ``params`` keys ending in ``_series``, its lookback as
``Strategy.lookback``, and its remaining knobs as the rest of ``params``. Nothing in
this module supplies a default for a sealed parameter -- a missing one raises
:class:`~ah.strategies.StrategyError` naming it, so a typo in the file that is about
to be hashed cannot silently become a differently-parametrized strategy.

VaR/ES loss convention: both are reported as **positive magnitudes of loss**.
Losses are the negative of returns; VaR at level p is the p-quantile of the pooled
loss distribution (the loss threshold exceeded (1-p) of the time); ES at level p is
the mean loss in the tail at or beyond VaR_p.

Scope discipline (WP2.1b Item 1): this module builds only D4 strategy evaluation and
VaR/ES. The rest of STEP2-GENERATOR-PLAN's tails.py -- the elicitability score,
Kupiec/Christoffersen backtests, and tail-dependence coefficients -- is WP2.2 scope
and is intentionally not implemented here.

Determinism: no randomness is used in this module. Any future addition that needs
randomness (e.g. an MC-error bootstrap over ensemble subsamples) must use
``numpy.random.Generator(PCG64(seed))`` from an explicit seed -- no global RNG, no
``random``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from ah.gen.base import Ensemble
from ah.strategies import (
    KNOWN_RULES,
    KNOWN_TRANSFORMS,
    DerivedSeries,
    Strategy,
    StrategyError,
    load_d4_strategies,
    load_derived_series,
)

# The single percent-to-decimal conversion, matching
# `conventions.percent_to_decimal` in pre-registration.yaml: a level quoted in
# percent (4.25 meaning 4.25%) times 0.01 is the decimal equivalent. Applied once, to
# the whole transform expression -- every transform below is linear in the percent
# level, so one leading factor converts the entire result.
_PCT_TO_DECIMAL = 0.01

# Months per year, for converting an annual percent rate to a monthly carry: y/12,
# simple, not compounded. Also from the sealed conventions block.
_MONTHS_PER_YEAR = 12.0


# --------------------------------------------------------------------------- #
# derived-series transforms
# --------------------------------------------------------------------------- #


def _transform_param(series: DerivedSeries, name: str) -> float:
    try:
        return float(series.params[name])
    except KeyError as exc:
        raise StrategyError(
            f"derived series '{series.series_id}' (transform '{series.transform}') is "
            f"missing sealed parameter '{name}'"
        ) from exc


def _lagged_carry_minus_duration(level: np.ndarray, duration: float) -> np.ndarray:
    """``r_t = 0.01 * ( x_{t-1}/12 - D*(x_t - x_{t-1}) )``, with ``r_0 = 0.0``.

    The shared closed form behind both declared transforms: a carry term (last
    month-end level earned over one month) and a price term (minus duration times the
    level change). ``level`` is in percent; the result is a monthly decimal return.
    Month 0 has no ``t-1`` predecessor and is 0.0 -- the single warm-up rule stated in
    ``pre-registration.yaml``'s ``conventions.warm_up``.
    """
    out = np.zeros_like(np.asarray(level, dtype=np.float64))
    if out.shape[1] < 2:
        return out
    previous = level[:, :-1]
    change = level[:, 1:] - previous
    out[:, 1:] = _PCT_TO_DECIMAL * (previous / _MONTHS_PER_YEAR - duration * change)
    return out


def _bond_total_return(level: np.ndarray, series: DerivedSeries) -> np.ndarray:
    """Bond total return from a yield level: carry minus duration times yield change."""
    return _lagged_carry_minus_duration(level, _transform_param(series, "duration_years"))


def _spread_excess_return(level: np.ndarray, series: DerivedSeries) -> np.ndarray:
    """Credit excess return from a spread level: carry minus spread duration times change."""
    return _lagged_carry_minus_duration(level, _transform_param(series, "spread_duration_years"))


_TRANSFORM_DISPATCH: Mapping[str, Callable[[np.ndarray, DerivedSeries], np.ndarray]] = {
    "bond_total_return": _bond_total_return,
    "spread_excess_return": _spread_excess_return,
}


def derived_series_values(ensemble: Ensemble, series: DerivedSeries) -> np.ndarray:
    """The ``(n_paths, months)`` monthly-decimal-return slab for one derived series."""
    transform = _TRANSFORM_DISPATCH.get(series.transform)
    if transform is None:
        raise StrategyError(
            f"derived series '{series.series_id}': transform '{series.transform}' has "
            f"no dispatch; known transforms: {sorted(KNOWN_TRANSFORMS)}"
        )
    return transform(ensemble.factor(series.source_factor), series)


def _resolve_series(
    ensemble: Ensemble, name: str, derived: Mapping[str, DerivedSeries]
) -> np.ndarray:
    """One weight/param key -> a ``(n_paths, months)`` return slab.

    An active factor reads straight from the ensemble; a declared derived series is
    computed from its source factor's slab via its sealed transform.
    """
    series = derived.get(name)
    if series is not None:
        return derived_series_values(ensemble, series)
    return ensemble.factor(name)


# --------------------------------------------------------------------------- #
# sealed-parameter access (no code-side defaults)
# --------------------------------------------------------------------------- #


def _number_param(strategy: Strategy, name: str) -> float:
    value = strategy.params.get(name)
    if value is None:
        raise StrategyError(
            f"strategy '{strategy.strategy_id}' (rule '{strategy.rule}') is missing "
            f"sealed parameter '{name}'; sealed parameters have no code-side default"
        )
    if isinstance(value, str):
        raise StrategyError(
            f"strategy '{strategy.strategy_id}': parameter '{name}' must be numeric, got {value!r}"
        )
    return float(value)


def _series_param(strategy: Strategy, name: str) -> str:
    value = strategy.params.get(name)
    if not isinstance(value, str) or not value:
        raise StrategyError(
            f"strategy '{strategy.strategy_id}' (rule '{strategy.rule}') is missing "
            f"sealed series parameter '{name}'; a rule's target series is sealed data, "
            f"not a constant in this module"
        )
    return value


def _required_lookback(strategy: Strategy) -> int:
    if strategy.lookback is None:
        raise StrategyError(
            f"strategy '{strategy.strategy_id}' (rule '{strategy.rule}') requires a "
            f"non-null 'lookback'"
        )
    return int(strategy.lookback)


# --------------------------------------------------------------------------- #
# rules
# --------------------------------------------------------------------------- #


def _momentum_12_1(
    ensemble: Ensemble, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray:
    """12-1 momentum on the sealed ``target_series``.

    Fully invested if the signal -- the sum over months ``[t - lookback, t - skip)``,
    excluding the most recent ``skip_months`` -- is strictly positive; flat otherwise.
    ``lookback`` comes from :attr:`Strategy.lookback`, its single declaration. The
    first ``lookback`` months of a path have no complete signal window and are flat,
    per the single warm-up rule in the sealed conventions block.
    """
    target = _resolve_series(ensemble, _series_param(strategy, "target_series"), derived)
    lookback = _required_lookback(strategy)
    skip = int(_number_param(strategy, "skip_months"))
    n_paths, months = target.shape
    position = np.zeros((n_paths, months), dtype=np.float64)
    for t in range(lookback, months):
        signal = target[:, t - lookback : t - skip].sum(axis=1)
        position[:, t] = np.where(signal > 0.0, 1.0, 0.0)
    return position * target


def _term_structure_carry(
    ensemble: Ensemble, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray:
    """Static long ``long_series`` / short ``funding_series``, every month -- no signal.

    Realized return = ``long_weight * long_series + funding_weight * funding_series``.
    Both legs are declared derived series in the sealed file, so both are already
    monthly decimal returns and no unit arithmetic happens here.
    """
    long_leg = _resolve_series(ensemble, _series_param(strategy, "long_series"), derived)
    funding_leg = _resolve_series(ensemble, _series_param(strategy, "funding_series"), derived)
    long_weight = _number_param(strategy, "long_weight")
    funding_weight = _number_param(strategy, "funding_weight")
    return long_weight * long_leg + funding_weight * funding_leg


_DISPATCH: Mapping[str, Callable[[Ensemble, Strategy, Mapping[str, DerivedSeries]], np.ndarray]] = {
    "momentum_12_1": _momentum_12_1,
    "term_structure_carry": _term_structure_carry,
}


# --------------------------------------------------------------------------- #
# strategy evaluation
# --------------------------------------------------------------------------- #


def strategy_returns(
    ensemble: Ensemble,
    strategy: Strategy,
    derived: Mapping[str, DerivedSeries] | None = None,
) -> np.ndarray:
    """Realized return path for one D4 strategy, shape ``(n_paths, months)``.

    ``kind == "static_weights"``: a weighted sum of resolved series -- return-bearing
    factors directly, level factors via their declared derived series.
    ``kind == "rule"``: dispatch to the rule named in ``strategy.rule``, which reads
    its target series and knobs from the strategy's sealed ``params``.
    ``derived`` defaults to :func:`ah.strategies.load_derived_series`.
    """
    if derived is None:
        derived = load_derived_series()
    if strategy.kind == "static_weights":
        return _static_weighted_returns(ensemble, strategy, derived)
    if strategy.kind == "rule":
        return _rule_returns(ensemble, strategy, derived)
    raise StrategyError(f"strategy '{strategy.strategy_id}': unknown kind '{strategy.kind}'")


def _static_weighted_returns(
    ensemble: Ensemble, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray:
    total = np.zeros((ensemble.n_paths, ensemble.months), dtype=np.float64)
    for series_name, weight in strategy.weights.items():
        total += weight * _resolve_series(ensemble, series_name, derived)
    return total


def _rule_returns(
    ensemble: Ensemble, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray:
    rule = _DISPATCH.get(strategy.rule or "")
    if rule is None:
        raise StrategyError(
            f"strategy '{strategy.strategy_id}': rule '{strategy.rule}' is not "
            f"implemented; known rules: {sorted(KNOWN_RULES)}"
        )
    return rule(ensemble, strategy, derived)


def var_es(returns: np.ndarray, level: float) -> tuple[float, float]:
    """Historical VaR and Expected Shortfall at ``level`` (e.g. 0.95, 0.99).

    ``returns`` is pooled across all dimensions (paths x months) before computing
    quantiles -- see the module docstring for the loss-magnitude convention.
    """
    if not 0.0 < level < 1.0:
        raise ValueError(f"level must be in (0, 1), got {level}")
    losses = -np.asarray(returns, dtype=np.float64).reshape(-1)
    var = float(np.quantile(losses, level))
    # np.quantile(losses, level) <= losses.max() for any non-empty input, so the tail
    # always holds at least one observation; empty input raises inside np.quantile.
    tail = losses[losses >= var]
    return var, float(tail.mean())


def d4_tail_table(
    ensemble: Ensemble, strategies: tuple[Strategy, ...] | None = None
) -> dict[str, dict[str, float]]:
    """VaR/ES at 95% and 99% for every D4 strategy.

    ``strategies`` defaults to :func:`ah.strategies.load_d4_strategies`, the same
    object the WP2.8 tail auxiliary loss loads.
    """
    if strategies is None:
        strategies = load_d4_strategies()
    derived = load_derived_series()
    table: dict[str, dict[str, float]] = {}
    for strategy in strategies:
        returns = strategy_returns(ensemble, strategy, derived)
        var_95, es_95 = var_es(returns, 0.95)
        var_99, es_99 = var_es(returns, 0.99)
        table[strategy.strategy_id] = {
            "var_95": var_95,
            "es_95": es_95,
            "var_99": var_99,
            "es_99": es_99,
        }
    return table
