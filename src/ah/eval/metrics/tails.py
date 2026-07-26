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

Scope discipline (WP2.1b Item 1): WP2.1b built only D4 strategy evaluation and
VaR/ES, above. WP2.2 Task 4 completes the module: :func:`elicitability_score`, the
Kupiec/Christoffersen backtests, and the two tail-dependence coefficients, below --
see "WP2.2 Task 4" for where each is defined and how it is wired into the battery.

Determinism: no randomness is used anywhere in this module (elicitability, Kupiec,
Christoffersen and tail dependence are all closed-form/deterministic given data). A
future addition that needs randomness (e.g. an MC-error bootstrap over ensemble
subsamples) must use ``numpy.random.Generator(PCG64(seed))`` from an explicit seed --
no global RNG, no ``random``.

WP2.2 Task 4 -- elicitability, Kupiec/Christoffersen, tail dependence, and wiring
--------------------------------------------------------------------------------
Every backtest below is computed on the **frozen D4 strategy set**
(:func:`load_d4_strategies`), reusing :func:`strategy_returns`/:func:`var_es` -- never
a second route to the same arithmetic. Two return series feed them, and they are
never confused:

- the **generated** ensemble's own pooled strategy return path (what the metric under
  test is being evaluated on); and
- the **historical** (train+validation) strategy return path
  (:func:`_historical_strategy_returns`), built by inner-joining exactly one
  strategy's own legs from :attr:`~ah.eval.reference.ReferenceStats.historical_series`
  -- never a fresh catalog read, and never the full active-factor panel (which would
  poison the result with leading NaN from factors the strategy never holds).

:func:`elicitability_score` and the Kupiec/Christoffersen backtests all score the
**generated** ensemble's realized losses against the **historical** VaR/ES -- an
out-of-sample-style comparison ("does the generator's own tail risk look like the
forecast history itself would have made"), not a self-referential score of the
generated sample against its own sample statistics (which would trivially optimize by
construction and prove nothing about tail fidelity). :func:`tail_dependence_lower` /
:func:`tail_dependence_upper` are re-exported, not restated, from
:mod:`ah.eval.reference` -- see :func:`build_tails_suite` for why they live there.

Registration is deferred, exactly as ``ah.eval.metrics.monthly``/``horizon``: this
suite needs a computed :class:`~ah.eval.reference.ReferenceStats` (for
``historical_series`` and the cross-block tail-dependence bands) and a
:class:`~ah.factors.FactorManifest` (for the tail-dependence factor-pair axis), so it
registers through :func:`build_tails_suite` / :func:`register_tails_suite` rather than
as an import-time side effect. ``ah.eval.battery.run_full_battery`` is the production
caller, via ``battery._REFERENCE_DEPENDENT_SUITE_BUILDERS``'s ``"tails"`` row.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from statistics import NormalDist

import numpy as np
import pandas as pd

from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.reference import ReferenceStats
from ah.eval.reference import tail_dependence_lower as _reference_tail_dependence_lower
from ah.eval.reference import tail_dependence_upper as _reference_tail_dependence_upper
from ah.factors import FactorManifest
from ah.gen.base import Ensemble, EnsembleMeta, UnknownFactorError
from ah.strategies import (
    KNOWN_RULES,
    KNOWN_TRANSFORMS,
    DerivedSeries,
    Strategy,
    StrategyError,
    load_conventions,
    load_d4_strategies,
    load_derived_series,
    strategy_legs,
)

# The percent-to-decimal conversion and the annual-to-monthly divisor, driven
# directly from `conventions.percent_to_decimal` / `conventions.months_per_year` in
# the sealed `pre-registration.yaml` -- not independent constants in this module. A
# level quoted in percent (4.25 meaning 4.25%) times `_PCT_TO_DECIMAL` is the decimal
# equivalent, applied once to the whole transform expression; an annual percent rate
# divided by `_MONTHS_PER_YEAR` is the simple (not compounded) monthly carry. Amending
# either sealed value changes every transform below, by construction: an amendment to
# `conventions.percent_to_decimal` or `conventions.months_per_year` is not a silent
# no-op (see `test_tails_pct_to_decimal_and_months_per_year_match_sealed_conventions`
# in tests/test_strategies.py).
_CONVENTIONS = load_conventions()
_PCT_TO_DECIMAL = _CONVENTIONS.percent_to_decimal
_MONTHS_PER_YEAR = _CONVENTIONS.months_per_year

# Re-exported under this module's own names, per pre-registration.yaml's
# `tail_dependence_estimator` -- the SAME function objects
# `ah.eval.reference.CROSS_BLOCK_STATS` calls to compute the real historical
# point+band, not wrappers, so a caller of `ah.eval.metrics.tails.tail_dependence_lower`
# gets the identical estimator the reference side used. Mirrors
# `ah.eval.metrics.monthly`'s `hill_tail_index = reference_hill_tail_index` precedent.
tail_dependence_lower = _reference_tail_dependence_lower
tail_dependence_upper = _reference_tail_dependence_upper

# The single VaR/ES level the Kupiec/Christoffersen backtests and elicitability_score
# run at, per pre-registration.yaml's kupiec_pof_estimator/elicitability_score_estimator
# blocks. NOT also 0.99: the expected exceedance count at alpha=0.01 over a 120-month
# generated path is ~1.2, far too few for a binomial/Markov-chain backtest to have any
# power -- a deliberate, stated scope decision, not an oversight. `var_95`/`es_95`/
# `var_99`/`es_99` (d4_var_es_estimator) remain descriptive at both levels.
BACKTEST_LEVEL = 0.95


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

    ``level`` is cast to float64 *before* any arithmetic, not only for the zeroed
    ``out`` array -- an integer or float32 input must not compute ``previous``/
    ``change`` at reduced precision and only widen at the final assignment. Shape is
    required to be exactly ``(n_paths, months)``; a caller passing anything else (a
    1-D series, e.g.) gets a named :class:`~ah.strategies.StrategyError` instead of an
    ``IndexError`` from ``level.shape[1]``.
    """
    level = np.asarray(level, dtype=np.float64)
    if level.ndim != 2:
        raise StrategyError(
            f"expected a 2-D (n_paths, months) level array, got shape {level.shape}"
        )
    out = np.zeros_like(level)
    if level.shape[1] < 2:
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
    ensemble: Ensemble,
    strategies: tuple[Strategy, ...] | None = None,
    derived: Mapping[str, DerivedSeries] | None = None,
) -> dict[str, dict[str, float]]:
    """VaR/ES at 95% and 99% for every D4 strategy.

    ``strategies`` and ``derived`` default *together* to
    :func:`ah.strategies.load_d4_strategies` and :func:`ah.strategies.load_derived_series`
    -- the same objects the WP2.8 tail auxiliary loss loads, both from the repo-root
    ``pre-registration.yaml``. They must come from the *same* source file: a strategy's
    weights/params name derived-series ids that only ``derived`` can resolve, so pairing
    a strategy set loaded from one file with derived-series transforms from another
    would silently evaluate the strategy against the wrong transform. If you pass an
    explicit ``strategies`` (e.g. loaded from a non-default path via
    ``load_d4_strategies(other_path)``), you must also pass the matching ``derived``
    (``load_derived_series(other_path)``) -- this function will not guess which file
    ``strategies`` came from. The same symmetry holds in the other direction: if you
    pass an explicit ``derived``, you must also pass the matching ``strategies``.
    """
    strategies_provided = strategies is not None
    derived_provided = derived is not None
    if strategies_provided != derived_provided:
        raise StrategyError(
            "d4_tail_table: 'strategies' and 'derived' must be supplied together, so the "
            "strategy set and its derived-series transforms are guaranteed to come from "
            "the same source file"
        )
    if strategies is None:
        strategies = load_d4_strategies()
    if derived is None:
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


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: elicitability score (Fissler-Ziegel)
# --------------------------------------------------------------------------- #


def elicitability_score(
    returns: np.ndarray, var: float, es: float, level: float = BACKTEST_LEVEL
) -> float:
    """The Fissler-Ziegel (2016) strictly consistent joint (VaR, ES) scoring function.

    **Orientation, stated once and applied consistently: LOWER IS BETTER.** This is a
    score to be minimized, and ``var``/``es`` minimize its expectation exactly at the
    TRUE VaR/ES of the distribution ``returns`` is drawn from (derivation below) -- that
    is what makes it a *consistent scoring rule* for the pair, not merely a plausible
    formula. A flipped sign here would silently invert the G2 tail criterion.

    Exact functional form, in this platform's positive-loss-magnitude convention (see
    the module docstring's "VaR/ES loss convention"; ``pre-registration.yaml``'s
    ``elicitability_score_estimator``). ``alpha = 1 - level`` is the tail probability;
    ``losses = -returns`` (pooled, if ``returns`` has more than one dimension);
    ``var`` and ``es > 0`` are a forecast (VaR, ES) pair, positive loss magnitudes:

        s_t = 1{loss_t >= var} * (loss_t - var) / (alpha * es) + var/es + ln(es) - 1

    and the returned value is ``mean(s_t)`` over every pooled observation.

    **Why this minimizes at the true (VaR, ES) pair** (so the elicitability property is
    reconstructible from this docstring, not merely asserted). Write ``E[S]`` for the
    population expectation of ``s_t`` as a function of ``(var, es)``, holding the loss
    distribution fixed, with ``F`` its CDF:

        E[S] = (1/(alpha*es)) * E[1{loss>=var}(loss-var)] + var/es + ln(es) - 1

    Differentiating under the integral (Leibniz), ``d/d(var) E[1{loss>=var}(loss-var)]
    = -(1 - F(var))`` (the boundary term at ``loss = var`` vanishes, since the
    integrand there is zero), so::

        dE[S]/d(var) = (1/es) * (1 - (1-F(var))/alpha)

    which is zero exactly when ``1 - F(var) = alpha``, i.e. ``var`` is the ``alpha``-tail
    VaR. At that stationary point, ``E[1{loss>=var*}(loss-var*)] = alpha*(ES* - var*)``
    (from the definition ``ES* = E[loss | loss>=var*]``), and::

        dE[S]/d(es) = -(ES* - var*)/es^2 - var*/es^2 + 1/es = -ES*/es^2 + 1/es

    which is zero exactly when ``es = ES*``. So the joint stationary point of
    ``E[S]`` over ``(var, es)`` is exactly ``(VaR_alpha, ES_alpha)`` of the loss
    distribution -- the property ``tests/test_tails.py`` checks empirically (on a fixed
    finite sample, where the identical algebra holds with the population expectation
    replaced by the sample mean and ``F`` by the empirical CDF, i.e. ``var``/``es`` as
    :func:`var_es` already computes them) by asserting a mis-specified pair scores
    strictly worse than the sample's own ``var_es`` pair -- not merely that the score is
    finite, which would prove nothing about consistency.

    Chosen family member: the Fissler-Ziegel ``G1 = 0`` (no auxiliary VaR term) with the
    log-barrier ``G2(es) = 1/es`` (antiderivative ``ln(es)``) -- the simplest member of
    the family for which strict consistency already holds, needing no second,
    arbitrarily-chosen family parameter.

    ``NaN`` if ``es <= 0`` (no positive ES magnitude to score against) or ``level`` is
    not in ``(0, 1)``.
    """
    if not 0.0 < level < 1.0:
        raise ValueError(f"elicitability_score: level must be in (0, 1), got {level}")
    if not es > 0.0:
        return float("nan")
    alpha = 1.0 - level
    losses = -np.asarray(returns, dtype=np.float64).reshape(-1)
    if losses.size == 0:
        return float("nan")
    indicator = losses >= var
    tail_term = float(np.mean(indicator * (losses - var))) / (alpha * es)
    return tail_term + var / es + math.log(es) - 1.0


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: chi-square survival function (df 1 and 2 only -- no scipy)
# --------------------------------------------------------------------------- #

_NORMAL = NormalDist()


def _chi2_sf(x: float, df: int) -> float:
    """``P(chi-square(df) > x)``, exact closed form, ``df in (1, 2)`` only.

    ``df=1``: a chi-square(1) variable is the square of a standard normal ``Z``, so
    ``P(Z**2 > x) = P(|Z| > sqrt(x)) = 2 * (1 - Phi(sqrt(x)))``, ``Phi`` the standard
    normal CDF (:class:`statistics.NormalDist`). Verified against the standard
    chi-square(1) 95th-percentile critical value 3.841459 in
    ``tests/test_tails.py``.

    ``df=2``: a chi-square(2) variable is exponential with mean 2, so its survival
    function has the closed form ``exp(-x/2)`` directly -- no normal-CDF detour needed.
    Verified against the standard chi-square(2) 95th-percentile critical value 5.991465.

    No other degrees of freedom are supported (raises :class:`ValueError`): Kupiec's
    test is always 1 d.o.f. and Christoffersen's conditional-coverage test is always 2
    (Kupiec + independence, each contributing one), so no other value is ever needed by
    this module, and a general chi-square CDF would need either scipy or an incomplete-
    gamma series this platform has no other use for.
    """
    if x < 0.0:
        raise ValueError(f"_chi2_sf: x must be >= 0, got {x}")
    if df == 1:
        return 2.0 * (1.0 - _NORMAL.cdf(math.sqrt(x)))
    if df == 2:
        return math.exp(-x / 2.0)
    raise ValueError(f"_chi2_sf: only df in (1, 2) is supported, got {df}")


def _bernoulli_loglik(n1: int, n0: int, p: float) -> float:
    """Log-likelihood of ``n1`` successes / ``n0`` failures under Bernoulli(p), with the
    ``0 * ln(0) := 0`` convention: a zero count never needs its own probability to be
    defined (handles ``p`` exactly 0 or 1 with a count of 0 in the corresponding cell,
    which is exactly the case a maximum-likelihood ``p`` estimated from the same counts
    produces at either boundary)."""
    ll = 0.0
    if n1 > 0:
        if not p > 0.0:
            return float("-inf")
        ll += n1 * math.log(p)
    if n0 > 0:
        if not p < 1.0:
            return float("-inf")
        ll += n0 * math.log(1.0 - p)
    return ll


def _pof_lr_from_counts(n1: int, t: int, level: float) -> float:
    """Kupiec proportion-of-failures LR statistic from exceedance count ``n1`` of ``t``."""
    alpha = 1.0 - level
    p_hat = n1 / t
    ll_null = _bernoulli_loglik(n1, t - n1, alpha)
    ll_alt = _bernoulli_loglik(n1, t - n1, p_hat)
    return max(-2.0 * (ll_null - ll_alt), 0.0)


def kupiec_pof(indicator: np.ndarray, level: float = BACKTEST_LEVEL) -> tuple[float, float]:
    """Kupiec (1995) proportion-of-failures unconditional-coverage LR test.

    ``indicator`` is a 1-D boolean (or 0/1) exceedance sequence (see
    :func:`exceedance_indicator`). Returns ``(LR statistic, p-value)``; the p-value is
    ``_chi2_sf(LR, df=1)``. Full closed form, and why it is the right null, in
    ``pre-registration.yaml``'s ``kupiec_pof_estimator``. ``(NaN, NaN)`` for an empty
    sequence.
    """
    x = np.asarray(indicator, dtype=bool).reshape(-1)
    t = x.shape[0]
    if t == 0:
        return float("nan"), float("nan")
    n1 = int(np.sum(x))
    lr = _pof_lr_from_counts(n1, t, level)
    return float(lr), _chi2_sf(lr, df=1)


def _transition_counts(indicator: np.ndarray) -> tuple[int, int, int, int]:
    """One-step transition counts ``(n00, n01, n10, n11)`` of a 1-D exceedance sequence."""
    x = np.asarray(indicator, dtype=bool).reshape(-1)
    prev, nxt = x[:-1], x[1:]
    n00 = int(np.sum(~prev & ~nxt))
    n01 = int(np.sum(~prev & nxt))
    n10 = int(np.sum(prev & ~nxt))
    n11 = int(np.sum(prev & nxt))
    return n00, n01, n10, n11


def _independence_lr_from_counts(n00: int, n01: int, n10: int, n11: int) -> float:
    """Christoffersen independence LR statistic from pooled one-step transition counts."""
    total = n00 + n01 + n10 + n11
    if total == 0:
        return float("nan")
    pi01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
    pi11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
    pi = (n01 + n11) / total
    ll_alt = _bernoulli_loglik(n01, n00, pi01) + _bernoulli_loglik(n11, n10, pi11)
    ll_null = _bernoulli_loglik(n01 + n11, n00 + n10, pi)
    return max(-2.0 * (ll_null - ll_alt), 0.0)


def christoffersen_independence(indicator: np.ndarray) -> tuple[float, float]:
    """Christoffersen (1998) independence LR test on an exceedance indicator sequence.

    Tests whether exceedances cluster in time (a Markov-chain LR test against the null
    that the one-step transition probabilities into "exceedance" do not depend on the
    previous state). Returns ``(LR statistic, p-value)``, ``p-value = _chi2_sf(LR,
    df=1)``. Full closed form in ``pre-registration.yaml``'s
    ``christoffersen_independence_estimator``. ``(NaN, NaN)`` for a sequence shorter
    than 2 (no transitions to count).
    """
    x = np.asarray(indicator, dtype=bool).reshape(-1)
    if x.shape[0] < 2:
        return float("nan"), float("nan")
    n00, n01, n10, n11 = _transition_counts(x)
    lr = _independence_lr_from_counts(n00, n01, n10, n11)
    if np.isnan(lr):
        return float("nan"), float("nan")
    return float(lr), _chi2_sf(lr, df=1)


def christoffersen_conditional_coverage(
    indicator: np.ndarray, level: float = BACKTEST_LEVEL
) -> tuple[float, float]:
    """The joint Kupiec + independence test: ``LR_cc = LR_pof + LR_ind ~ chi-square(2)``.

    Returns ``(LR statistic, p-value)``, ``p-value = _chi2_sf(LR_cc, df=2)``. ``(NaN,
    NaN)`` if either component test is undefined (e.g. fewer than 2 observations).
    """
    lr_pof, pof_pvalue = kupiec_pof(indicator, level)
    lr_ind, ind_pvalue = christoffersen_independence(indicator)
    if math.isnan(lr_pof) or math.isnan(lr_ind):
        return float("nan"), float("nan")
    lr_cc = lr_pof + lr_ind
    del pof_pvalue, ind_pvalue  # component p-values are not the joint one
    return float(lr_cc), _chi2_sf(lr_cc, df=2)


def exceedance_indicator(returns: np.ndarray, var: float) -> np.ndarray:
    """``loss >= var``, per observation of ``returns`` (any shape, preserved)."""
    losses = -np.asarray(returns, dtype=np.float64)
    return losses >= var


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: historical D4 strategy returns, from ReferenceStats.historical_series
# --------------------------------------------------------------------------- #


def _historical_strategy_returns(
    reference: ReferenceStats, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray | None:
    """The historical (train+validation) realized return path for one D4 strategy.

    Inner-joins exactly ``strategy``'s own legs (:func:`ah.strategies.strategy_legs`,
    resolved through ``derived`` to the underlying SOURCE FACTOR for a derived-series
    leg) onto their shared date overlap from
    :attr:`~ah.eval.reference.ReferenceStats.historical_series` -- never the full
    active-factor panel, which would poison the result with leading NaN from factors
    the strategy never holds (a strategy using only post-1996 ``hy_spread`` must not be
    truncated to CPI's 1913 start merely because both are active factors). The aligned
    overlap is wrapped as a single-path :class:`~ah.gen.base.Ensemble` and handed to
    :func:`strategy_returns` -- the SAME function that evaluates the generated
    ensemble, so historical and generated values can never diverge in how a strategy is
    computed from resolved series.

    Returns ``None`` (the metric reports NaN) if any leg's underlying factor has no
    historical series at all (``commodities``, today -- see
    ``pre-registration.yaml``'s ``rationale.d4_commodities_consequence``) or if the
    aligned overlap is empty, mirroring
    :attr:`~ah.eval.reference.CrossBlockReference.zero_overlap_pairs`'s treatment of
    the identical situation for a cross-block pair.
    """
    legs = strategy_legs(strategy)
    needed_factors = sorted({derived[leg].source_factor if leg in derived else leg for leg in legs})
    if any(f not in reference.historical_series for f in needed_factors):
        return None
    joined = pd.concat(
        {f: reference.historical_series[f] for f in needed_factors}, axis=1, join="inner"
    ).sort_index()
    if joined.empty:
        return None
    values = joined.to_numpy(dtype=np.float64)
    hist_ensemble = Ensemble(
        paths=values[np.newaxis, :, :],
        factor_names=list(needed_factors),
        meta=EnsembleMeta(
            generator_id="historical-train-val",
            vintage_id=reference.vintage_id,
            seed=reference.seed,
            n_paths=1,
            months=values.shape[0],
        ),
    )
    return strategy_returns(hist_ensemble, strategy, derived)


def _historical_var_es(
    reference: ReferenceStats,
    strategy: Strategy,
    derived: Mapping[str, DerivedSeries],
    level: float,
) -> tuple[float, float]:
    """The historical VaR/ES forecast :func:`elicitability_score`/Kupiec/Christoffersen
    score the generated ensemble against. ``(NaN, NaN)`` if the historical strategy
    return path cannot be built (see :func:`_historical_strategy_returns`)."""
    hist_returns = _historical_strategy_returns(reference, strategy, derived)
    if hist_returns is None:
        return float("nan"), float("nan")
    return var_es(hist_returns, level)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: build_tails_suite / register_tails_suite
# --------------------------------------------------------------------------- #


def _strategy_spec(
    name: str, fn: Callable[[Ensemble], float], *, metadata: tuple[tuple[str, str], ...] = ()
) -> MetricSpec:
    return MetricSpec(name=name, tier="monthly", fn=fn, suite="tails", metadata=metadata)


def _generated_pooled_returns(
    ensemble: Ensemble, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray | None:
    """The generated ensemble's pooled strategy return path, or ``None`` if a leg is
    absent from this ensemble (``UnknownFactorError`` -- e.g. ``commodities``)."""
    try:
        return strategy_returns(ensemble, strategy, derived).reshape(-1)
    except UnknownFactorError:
        return None


def _var_es_metric(
    strategy: Strategy, derived: Mapping[str, DerivedSeries], level: float, which: str
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        pooled = _generated_pooled_returns(ensemble, strategy, derived)
        if pooled is None or pooled.size == 0:
            return float("nan")
        var, es = var_es(pooled, level)
        return var if which == "var" else es

    return fn


def _elicitability_metric(
    strategy: Strategy, derived: Mapping[str, DerivedSeries], reference: ReferenceStats
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        pooled = _generated_pooled_returns(ensemble, strategy, derived)
        if pooled is None or pooled.size == 0:
            return float("nan")
        hist_var, hist_es = _historical_var_es(reference, strategy, derived, BACKTEST_LEVEL)
        if np.isnan(hist_var) or np.isnan(hist_es):
            return float("nan")
        return elicitability_score(pooled, hist_var, hist_es, BACKTEST_LEVEL)

    return fn


def _backtest_metric(
    strategy: Strategy,
    derived: Mapping[str, DerivedSeries],
    reference: ReferenceStats,
    test: str,
    which: str,
) -> MetricFn:
    """``test`` in {"kupiec", "christoffersen_independence", "christoffersen_cc"};
    ``which`` in {"stat", "pvalue"} -- shared plumbing for the six Kupiec/Christoffersen
    metric specs (both levels of both outputs of both tests)."""

    def fn(ensemble: Ensemble) -> float:
        pooled_2d = _generated_returns_2d(ensemble, strategy, derived)
        if pooled_2d is None:
            return float("nan")
        hist_var, hist_es = _historical_var_es(reference, strategy, derived, BACKTEST_LEVEL)
        del hist_es  # only the VaR forecast is needed for a backtest's indicator
        if np.isnan(hist_var):
            return float("nan")
        if test == "kupiec":
            n1_total = 0
            t_total = 0
            for i in range(pooled_2d.shape[0]):
                indicator = exceedance_indicator(pooled_2d[i], hist_var)
                n1_total += int(np.sum(indicator))
                t_total += indicator.size
            if t_total == 0:
                return float("nan")
            lr = _pof_lr_from_counts(n1_total, t_total, BACKTEST_LEVEL)
            return lr if which == "stat" else _chi2_sf(lr, df=1)

        n00 = n01 = n10 = n11 = 0
        n1_total = 0
        t_total = 0
        for i in range(pooled_2d.shape[0]):
            indicator = exceedance_indicator(pooled_2d[i], hist_var)
            n1_total += int(np.sum(indicator))
            t_total += indicator.size
            if indicator.size >= 2:
                c00, c01, c10, c11 = _transition_counts(indicator)
                n00 += c00
                n01 += c01
                n10 += c10
                n11 += c11
        if t_total == 0:
            return float("nan")
        lr_ind = _independence_lr_from_counts(n00, n01, n10, n11)
        if test == "christoffersen_independence":
            if np.isnan(lr_ind):
                return float("nan")
            return lr_ind if which == "stat" else _chi2_sf(lr_ind, df=1)

        # christoffersen_cc
        if np.isnan(lr_ind):
            return float("nan")
        lr_pof = _pof_lr_from_counts(n1_total, t_total, BACKTEST_LEVEL)
        lr_cc = lr_pof + lr_ind
        return lr_cc if which == "stat" else _chi2_sf(lr_cc, df=2)

    return fn


def _generated_returns_2d(
    ensemble: Ensemble, strategy: Strategy, derived: Mapping[str, DerivedSeries]
) -> np.ndarray | None:
    """The generated ensemble's per-path (``n_paths, months``) strategy return slab, or
    ``None`` if a leg is absent from this ensemble -- the 2-D counterpart of
    :func:`_generated_pooled_returns`, kept because Christoffersen's transition counts
    must never cross a path boundary (see :func:`_backtest_metric`)."""
    try:
        return strategy_returns(ensemble, strategy, derived)
    except UnknownFactorError:
        return None


def _strategy_specs(
    strategy: Strategy, derived: Mapping[str, DerivedSeries], reference: ReferenceStats
) -> list[MetricSpec]:
    sid = strategy.strategy_id
    specs = [
        _strategy_spec(f"{sid}.var_95", _var_es_metric(strategy, derived, 0.95, "var")),
        _strategy_spec(f"{sid}.es_95", _var_es_metric(strategy, derived, 0.95, "es")),
        _strategy_spec(f"{sid}.var_99", _var_es_metric(strategy, derived, 0.99, "var")),
        _strategy_spec(f"{sid}.es_99", _var_es_metric(strategy, derived, 0.99, "es")),
        _strategy_spec(
            f"{sid}.elicitability_score", _elicitability_metric(strategy, derived, reference)
        ),
    ]
    for test, prefix in (
        ("kupiec", "kupiec_pof"),
        ("christoffersen_independence", "christoffersen_independence"),
        ("christoffersen_cc", "christoffersen_conditional_coverage"),
    ):
        specs.append(
            _strategy_spec(
                f"{sid}.{prefix}_stat", _backtest_metric(strategy, derived, reference, test, "stat")
            )
        )
        specs.append(
            _strategy_spec(
                f"{sid}.{prefix}_pvalue",
                _backtest_metric(strategy, derived, reference, test, "pvalue"),
            )
        )
    return specs


def _tail_dependence_metric(fa: str, fb: str, upper: bool) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if fa not in ensemble.factor_names or fb not in ensemble.factor_names:
            return float("nan")
        a = ensemble.factor(fa).reshape(-1).astype(np.float64)
        b = ensemble.factor(fb).reshape(-1).astype(np.float64)
        return tail_dependence_upper(a, b) if upper else tail_dependence_lower(a, b)

    return fn


def build_tails_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every ``tails``-tier :class:`~ah.eval.battery.MetricSpec`.

    Two axes, built independently (see the module docstring): every sealed D4 strategy
    (:func:`load_d4_strategies`) gets its eleven ``STRATEGY_STATS`` metrics
    (``"<strategy_id>.<stat>"``), and every active cross-block factor pair
    (``manifest.cross_block_pairs()``, the identical loop
    ``ah.eval.metrics.monthly.build_monthly_suite`` uses for ``crisis_corr_lift``) gets
    its two tail-dependence metrics (``"<factorA>~<factorB>.<stat>"``).
    """
    specs: list[MetricSpec] = []
    strategies = load_d4_strategies()
    derived = load_derived_series()
    for strategy in strategies:
        specs.extend(_strategy_specs(strategy, derived, reference))

    active_set = set(manifest.active_factors())
    seen_pairs: set[tuple[str, str]] = set()
    for block_a, block_b in manifest.cross_block_pairs():
        for fa in manifest.blocks[block_a]:
            if fa not in active_set:
                continue
            for fb in manifest.blocks[block_b]:
                if fb not in active_set or (fa, fb) in seen_pairs:
                    continue
                seen_pairs.add((fa, fb))
                specs.append(
                    _strategy_spec(
                        f"{fa}~{fb}.tail_dependence_lower", _tail_dependence_metric(fa, fb, False)
                    )
                )
                specs.append(
                    _strategy_spec(
                        f"{fa}~{fb}.tail_dependence_upper", _tail_dependence_metric(fa, fb, True)
                    )
                )

    return tuple(specs)


def register_tails_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("tails", build_tails_suite(manifest, reference))``."""
    register_suite("tails", build_tails_suite(manifest, reference))
