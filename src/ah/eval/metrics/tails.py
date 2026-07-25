"""D4 tail-fidelity metrics: strategy returns and historical VaR/ES (WP2.1b Item 1).

Computes every D4 benchmark strategy's realized return path, and historical VaR /
Expected Shortfall on it, from an :class:`~ah.gen.base.Ensemble` alone -- no
dependency on portfolio or sleeve machinery (``tests/test_tails_import_graph.py``
proves this by walking this module's imports). See
``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 1 and :mod:`ah.strategies` for the
five D4 strategy definitions this module evaluates.

Factor-slab convention: for D4 purposes, each active factor's generated monthly path
(an ``Ensemble.factor(name)`` slab) is used directly as its monthly return-equivalent
contribution -- static-weight strategies are a weighted sum of factor slabs; rule
strategies combine slabs per their stated rule (below). This is a convention scoped
to the D4 metric definition, not a claim about the generator's native units
elsewhere in the system; formalizing the full state-space unit contract
(softplus-space rates/spreads vs. return-space market factors, log-space prices) is
WP2.8's ``constraints.py``.

Rule dispatch: a rule strategy's target factor(s) are fixed by its rule id -- there
is no per-strategy target-factor field on :class:`ah.strategies.Strategy` for
``kind == "rule"``. ``momentum_12_1`` always reads ``equity_mkt``;
``term_structure_carry`` always reads ``ust_10y`` (long leg) and ``policy_rate``
(funding leg). Everything else about a rule's numeric behaviour (lookback/skip
months, long/funding weights) is parametrized from the strategy's
``lookback``/``params`` fields, so ``pre-registration.yaml`` pins the rule's
behaviour even though the target factor names are fixed in this module.

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

import numpy as np

from ah.gen.base import Ensemble
from ah.strategies import KNOWN_RULES, Strategy, StrategyError, load_d4_strategies


def strategy_returns(ensemble: Ensemble, strategy: Strategy) -> np.ndarray:
    """Realized return path for one D4 strategy, shape ``(n_paths, months)``.

    ``kind == "static_weights"``: a weighted sum of the ensemble's factor slabs.
    ``kind == "rule"``: dispatch to the rule named in ``strategy.rule`` (see the
    module docstring for the fixed target-factor-per-rule mapping and each rule's
    stated warm-up behaviour).
    """
    if strategy.kind == "static_weights":
        return _static_weighted_returns(ensemble, strategy)
    if strategy.kind == "rule":
        return _rule_returns(ensemble, strategy)
    raise StrategyError(f"strategy '{strategy.strategy_id}': unknown kind '{strategy.kind}'")


def _static_weighted_returns(ensemble: Ensemble, strategy: Strategy) -> np.ndarray:
    total = np.zeros((ensemble.n_paths, ensemble.months), dtype=np.float64)
    for factor_name, weight in strategy.weights.items():
        total += weight * ensemble.factor(factor_name)
    return total


def _rule_returns(ensemble: Ensemble, strategy: Strategy) -> np.ndarray:
    if strategy.rule not in KNOWN_RULES:
        raise StrategyError(
            f"strategy '{strategy.strategy_id}': rule '{strategy.rule}' is not implemented"
        )
    if strategy.rule == "momentum_12_1":
        return _momentum_12_1(ensemble, strategy)
    if strategy.rule == "term_structure_carry":
        return _term_structure_carry(ensemble, strategy)
    # Unreachable: KNOWN_RULES and the dispatch above are kept in sync by construction.
    raise StrategyError(  # pragma: no cover
        f"strategy '{strategy.strategy_id}': rule '{strategy.rule}' has no dispatch"
    )


def _momentum_12_1(ensemble: Ensemble, strategy: Strategy) -> np.ndarray:
    """12-1 momentum on ``equity_mkt``: fully invested if the 11-month signal (months
    t-lookback..t-skip, exclusive of the most recent ``skip`` months) is positive,
    flat otherwise. The first ``lookback_months`` months of a path are flat
    (no complete signal window is available yet) -- the stated warm-up behaviour.
    """
    equity = ensemble.factor("equity_mkt")
    lookback = int(strategy.params.get("lookback_months", 12))
    skip = int(strategy.params.get("skip_months", 1))
    n_paths, months = equity.shape
    position = np.zeros((n_paths, months), dtype=np.float64)
    for t in range(lookback, months):
        window = equity[:, t - lookback : t - skip]
        signal = window.sum(axis=1)
        position[:, t] = np.where(signal > 0.0, 1.0, 0.0)
    return position * equity


def _term_structure_carry(ensemble: Ensemble, strategy: Strategy) -> np.ndarray:
    """Static long ust_10y / short policy_rate, every month -- no lookback, no signal.

    Realized return = long_weight * ust_10y + funding_weight * policy_rate.
    """
    long_leg = ensemble.factor("ust_10y")
    funding_leg = ensemble.factor("policy_rate")
    long_weight = float(strategy.params.get("long_weight", 1.0))
    funding_weight = float(strategy.params.get("funding_weight", -1.0))
    return long_weight * long_leg + funding_weight * funding_leg


def var_es(returns: np.ndarray, level: float) -> tuple[float, float]:
    """Historical VaR and Expected Shortfall at ``level`` (e.g. 0.95, 0.99).

    ``returns`` is pooled across all dimensions (paths x months) before computing
    quantiles -- see the module docstring for the loss-magnitude convention.
    """
    if not 0.0 < level < 1.0:
        raise ValueError(f"level must be in (0, 1), got {level}")
    losses = -np.asarray(returns, dtype=np.float64).reshape(-1)
    var = float(np.quantile(losses, level))
    tail = losses[losses >= var]
    es = float(tail.mean()) if tail.size > 0 else var
    return var, es


def d4_tail_table(
    ensemble: Ensemble, strategies: tuple[Strategy, ...] | None = None
) -> dict[str, dict[str, float]]:
    """VaR/ES at 95% and 99% for every D4 strategy.

    ``strategies`` defaults to :func:`ah.strategies.load_d4_strategies`, the same
    object the WP2.8 tail auxiliary loss loads.
    """
    if strategies is None:
        strategies = load_d4_strategies()
    table: dict[str, dict[str, float]] = {}
    for strategy in strategies:
        returns = strategy_returns(ensemble, strategy)
        var_95, es_95 = var_es(returns, 0.95)
        var_99, es_99 = var_es(returns, 0.99)
        table[strategy.strategy_id] = {
            "var_95": var_95,
            "es_95": es_95,
            "var_99": var_99,
            "es_99": es_99,
        }
    return table
