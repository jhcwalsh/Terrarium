"""Step 5 decision metrics — frozen at wp5-00, before any outcome they judge.

SEALED JUDGED CODE (pre-registration-g5.lock). The plan's own constraint:
these definitions freeze before the first evaluation run, and freezing
them after outcomes were visible would invalidate the exercise. Every
metric is a pure formula with a worked example in its docstring and a
unit test asserting that example; nothing here reads a store, an engine,
or a clock. `decision_alpha_version = "1.0"` on every RunRecord (retrofit
R-1) refers to THIS sealed definition set.

The PRIMARY metric is drawdown surprise. Everything else is secondary,
pre-stated as such — the p-value-hunting defense in the plan's pitfall
list, made structural.
"""

from __future__ import annotations

import numpy as np

PRIMARY_METRIC = "drawdown_surprise"
DECISION_ALPHA_VERSION = "1.0"  # what the RunRecord stamp refers to


class MetricError(ValueError):
    """An input the metric refuses to score."""


def max_drawdown(returns: np.ndarray) -> float:
    """Peak-to-trough loss of the cumulative product, as a POSITIVE depth.

    Worked example: returns [0.10, -0.20, 0.05] -> wealth [1.10, 0.88,
    0.924]; peak 1.10, trough 0.88 -> 0.2 exactly.
    """
    wealth = np.concatenate([[1.0], np.cumprod(1.0 + np.asarray(returns, dtype=float))])
    peaks = np.maximum.accumulate(wealth)
    return float(np.max(1.0 - wealth / peaks))


def drawdown_surprise(realized_returns: np.ndarray, ensemble_returns: np.ndarray) -> float:
    """PRIMARY. Realized max drawdown minus the ensemble-predicted p95 depth.

    Positive = the world hurt more than the generator warned at the 95th
    percentile; zero or negative = reality stayed inside the warning.
    Worked example: realized dd 0.30 against an ensemble whose p95 dd is
    0.25 -> surprise +0.05.
    """
    ens = np.asarray(ensemble_returns, dtype=float)
    if ens.ndim != 2:
        raise MetricError("ensemble_returns is paths x periods")
    predicted_p95 = float(np.percentile([max_drawdown(path) for path in ens], 95.0))
    return max_drawdown(realized_returns) - predicted_p95


def decision_alpha(player_wealth: float, twin_wealth: float) -> float:
    """Terminal wealth vs the hold-course twin, in log points.

    Worked example: player 1.50 vs twin 1.35 -> ln(1.50/1.35) = +0.10536.
    """
    if player_wealth <= 0 or twin_wealth <= 0:
        raise MetricError("wealth must be positive")
    return float(np.log(player_wealth / twin_wealth))


def decision_alpha_by_window(
    player_wealth_at: np.ndarray, twin_wealth_at: np.ndarray
) -> np.ndarray:
    """R12: the alpha attributed per decision window (v1.0 definition).

    Inputs are wealth levels at each window boundary, index 0 = t0, so
    window k spans boundaries [k, k+1]. The attribution is the change in
    log relative wealth across the window; the attributions SUM EXACTLY
    to total decision alpha (telescoping), which the unit test asserts —
    no residual bucket, no leakage between windows.

    Worked example: player [1.0, 1.1, 1.5], twin [1.0, 1.1, 1.35] ->
    window 1: ln(1.1/1.1) - ln(1.0/1.0) = 0.0; window 2:
    ln(1.5/1.35) - ln(1.1/1.1) = +0.10536. Sum = total alpha.
    """
    p = np.asarray(player_wealth_at, dtype=float)
    t = np.asarray(twin_wealth_at, dtype=float)
    if p.shape != t.shape or p.ndim != 1 or len(p) < 2:
        raise MetricError("wealth series must be equal-length 1-D with >= 2 boundaries")
    if np.any(p <= 0) or np.any(t <= 0):
        raise MetricError("wealth must be positive")
    rel = np.log(p / t)
    return np.diff(rel)


def forced_sale_cost(forced_sales: list[dict], nav_reference: float) -> tuple[int, float]:
    """(incidence, total haircut cost as a fraction of reference NAV).

    Only forced secondaries carry a haircut cost; liquid pro-rata sales
    are counted in incidence but cost zero by definition. Worked example:
    two events, one secondary selling 10.0 NAV at 0.19 haircut, reference
    NAV 100 -> (2, 0.019).
    """
    if nav_reference <= 0:
        raise MetricError("nav_reference must be positive")
    cost = sum(
        e["nav_sold"] * e["haircut"] for e in forced_sales if e.get("kind") == "forced_secondary"
    )
    return len(forced_sales), float(cost / nav_reference)


def liquidity_shortfall_probability(
    coverage_liquid_paths: np.ndarray, threshold: float = 1.0
) -> float:
    """Fraction of paths whose liquid coverage EVER breaches the threshold.

    Coverage here is unfunded/liquid (P-B's binding ratio): breaching 1.0
    means unfunded commitments exceed everything sellable. Worked example:
    3 paths, maxima [0.4, 1.2, 0.9] -> 1/3.
    """
    paths = np.asarray(coverage_liquid_paths, dtype=float)
    if paths.ndim != 2:
        raise MetricError("coverage paths are paths x periods")
    return float(np.mean(np.max(paths, axis=1) >= threshold))


def funding_ratio_tail(funding_ratios_terminal: np.ndarray, quantile: float = 0.01) -> float:
    """The worst-1% terminal funding ratio (lower = worse).

    Worked example: 100 paths uniform 0.51..1.50 -> the 1st percentile
    sits near 0.52 (the exact value is the interpolated percentile,
    asserted in the unit test).
    """
    x = np.asarray(funding_ratios_terminal, dtype=float)
    if x.ndim != 1 or len(x) == 0:
        raise MetricError("terminal funding ratios are a non-empty vector")
    return float(np.percentile(x, quantile * 100.0))


def breach_duration_quarters(private_weights: np.ndarray, upper: float) -> int:
    """How many quarters the private weight sits above the policy upper.

    Worked example: weights [0.30, 0.36, 0.37, 0.33], upper 0.35 -> 2.
    """
    w = np.asarray(private_weights, dtype=float)
    return int(np.sum(w > upper))


def precommitment_adherence(planned: list[dict], executed: list[dict]) -> float:
    """Fraction of triggered playbook rules the committee actually followed.

    A rule is a dict with 'rule_id' and 'triggered' (bool); an execution
    carries 'rule_id' and 'followed' (bool). Untriggered rules are out of
    the denominator — adherence is measured when the moment came, not on
    paper. Worked example: 3 rules, 2 triggered, 1 followed -> 0.5.
    """
    triggered = {r["rule_id"] for r in planned if r.get("triggered")}
    if not triggered:
        raise MetricError("no triggered rules: adherence undefined, not 100%")
    followed = {e["rule_id"] for e in executed if e.get("followed")}
    return len(triggered & followed) / len(triggered)
