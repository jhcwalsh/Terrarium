"""The walk-forward harness (WP5.1) — the sealed protocol, executable.

IMPLEMENTS, never redefines: the scheme comes from the SEALED
``step5-evaluation-protocol.yaml`` (verified intact via the G5 lock before
any run), and the fold structure is the AM-2026-08-02-005 pin — ten
expanding folds, test years 2011..2020, training from 1871-01, quarterly
rebalancing. The holdout (2021-01+) is structurally out of reach: fold
construction refuses test years beyond 2020.

The six benchmark policies are pure functions of TRAILING history only
(the fold hands each policy exactly the data a decision-maker could have
seen). Stochastic policies (gaussian MC, bootstrap) draw from
PCG64(seed) derived from the fold — deterministic, reproducible, and the
seed is recorded in the result. Statistics: Wilcoxon signed-rank across
folds WITH the rank-biserial effect size — per the sealed rule, a p-value
alone is not a result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from ah.eval import decision_metrics as dm
from ah.eval.g5seal import G5_PROTOCOL_PATH, verify_g5

FOLD_TEST_YEARS = tuple(range(2011, 2021))  # AM-2026-08-02-005, verbatim
TRAIN_START = "1871-01"
QUARTER_MONTHS = 3

BENCHMARK_POLICIES = (
    "history_only_optimization",
    "gaussian_monte_carlo",
    "bootstrap_ensemble",
    "static_60_40",
    "static_endowment_mix",
    "fixed_heuristic_rules",
)


class WalkForwardError(ValueError):
    """A harness input or configuration the sealed protocol refuses."""


def load_protocol(*, verify: bool = True) -> dict[str, Any]:
    """The sealed protocol, verified intact against the G5 lock first."""
    if verify:
        verify_g5()
    doc = yaml.safe_load(G5_PROTOCOL_PATH.read_text(encoding="utf-8"))
    if doc["evaluation"]["scheme"] != "expanding_window_walk_forward":
        raise WalkForwardError("protocol scheme mismatch — refusing to run")
    return doc


@dataclass(frozen=True)
class Fold:
    fold_id: int
    test_year: int
    train_start: str
    train_end: str  # exclusive: the test year's first month
    test_start: str
    test_end: str  # exclusive


def folds() -> list[Fold]:
    """The AM-2026-08-02-005 pin, verbatim; the holdout is unreachable."""
    out = []
    for i, year in enumerate(FOLD_TEST_YEARS, start=1):
        out.append(
            Fold(
                fold_id=i,
                test_year=year,
                train_start=TRAIN_START,
                train_end=f"{year}-01",
                test_start=f"{year}-01",
                test_end=f"{year + 1}-01",
            )
        )
    return out


# -- the six benchmark policies --------------------------------------------- #


def _mean_variance_weights(mu: np.ndarray, cov: np.ndarray, ridge: float = 1e-4) -> np.ndarray:
    """Long-only, fully-invested max-Sharpe-style weights: inv(cov+ridge) @ mu,
    clipped at zero and renormalized; uniform if everything clips out."""
    n = len(mu)
    w = np.linalg.solve(cov + ridge * np.eye(n), mu)
    w = np.clip(w, 0.0, None)
    total = w.sum()
    return w / total if total > 1e-12 else np.full(n, 1.0 / n)


def history_only_optimization(history: pd.DataFrame, *, rng: np.random.Generator) -> np.ndarray:
    return _mean_variance_weights(
        history.mean().to_numpy(), np.cov(history.to_numpy(), rowvar=False)
    )


def gaussian_monte_carlo(
    history: pd.DataFrame, *, rng: np.random.Generator, n_sims: int = 2000
) -> np.ndarray:
    mu, cov = history.mean().to_numpy(), np.cov(history.to_numpy(), rowvar=False)
    sims = rng.multivariate_normal(mu, cov, size=n_sims)
    return _mean_variance_weights(sims.mean(axis=0), np.cov(sims, rowvar=False))


def bootstrap_ensemble(
    history: pd.DataFrame, *, rng: np.random.Generator, n_boot: int = 200, block: int = 24
) -> np.ndarray:
    x = history.to_numpy()
    n = len(x)
    samples = []
    for _ in range(n_boot):
        idx: list[int] = []
        while len(idx) < n:
            start = int(rng.integers(0, max(1, n - block)))
            idx.extend(range(start, min(start + block, n)))
        samples.append(x[idx[:n]])
    stacked = np.concatenate(samples, axis=0)
    return _mean_variance_weights(stacked.mean(axis=0), np.cov(stacked, rowvar=False))


def static_60_40(history: pd.DataFrame, *, rng: np.random.Generator) -> np.ndarray:
    return _named_weights(history, {"equity": 0.60, "bonds": 0.40})


def static_endowment_mix(history: pd.DataFrame, *, rng: np.random.Generator) -> np.ndarray:
    return _named_weights(
        history, {"equity": 0.65, "bonds": 0.10, "commodities": 0.10, "credit": 0.15}
    )


def fixed_heuristic_rules(history: pd.DataFrame, *, rng: np.random.Generator) -> np.ndarray:
    """The banded rule: 60/40 target, rebalance only when trailing-year drift
    exceeds 5 points (mirrors the committee heuristic's discipline)."""
    target = _named_weights(history, {"equity": 0.60, "bonds": 0.40})
    tail = history.tail(12)
    if len(tail) < 2:
        return target
    growth = (1.0 + tail).prod().to_numpy()
    drifted = target * growth
    drifted = drifted / drifted.sum()
    return target if np.max(np.abs(drifted - target)) > 0.05 else drifted


def _named_weights(history: pd.DataFrame, mapping: dict[str, float]) -> np.ndarray:
    cols = list(history.columns)
    missing = [k for k in mapping if k not in cols]
    if missing:
        raise WalkForwardError(f"policy needs asset columns {missing}; universe has {cols}")
    w = np.array([mapping.get(c, 0.0) for c in cols], dtype=float)
    return w / w.sum()


POLICY_FNS: dict[str, Callable[..., np.ndarray]] = {
    "history_only_optimization": history_only_optimization,
    "gaussian_monte_carlo": gaussian_monte_carlo,
    "bootstrap_ensemble": bootstrap_ensemble,
    "static_60_40": static_60_40,
    "static_endowment_mix": static_endowment_mix,
    "fixed_heuristic_rules": fixed_heuristic_rules,
}


# -- the harness ------------------------------------------------------------ #


@dataclass
class FoldResult:
    fold_id: int
    policy: str
    terminal_log_wealth: float
    max_drawdown: float
    seed: int


@dataclass
class WalkForwardResult:
    protocol_version: str
    fold_results: list[FoldResult] = field(default_factory=list)

    def per_policy(self, metric: str) -> dict[str, np.ndarray]:
        out: dict[str, list[float]] = {}
        for r in sorted(self.fold_results, key=lambda x: x.fold_id):
            out.setdefault(r.policy, []).append(getattr(r, metric))
        return {k: np.array(v) for k, v in out.items()}


def run_walkforward(
    returns: pd.DataFrame,
    *,
    policies: tuple[str, ...] = BENCHMARK_POLICIES,
    base_seed: int = 0,
) -> WalkForwardResult:
    """Every policy through every fold: quarterly rebalancing to the policy's
    weights, computed from TRAILING data only at each rebalance date.

    ``returns``: monthly asset returns, DatetimeIndex, named asset columns.
    """
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise WalkForwardError("returns needs a DatetimeIndex")
    protocol = load_protocol()
    result = WalkForwardResult(protocol_version=protocol["protocol_version"])

    for fold in folds():
        test = (
            returns.loc[fold.test_start : fold.test_end].iloc[:-1]
            if fold.test_end in returns.index
            else returns.loc[fold.test_start : fold.test_end]
        )
        test = returns[(returns.index >= fold.test_start) & (returns.index < fold.test_end)]
        if test.empty:
            continue
        for policy in policies:
            seed = base_seed + 7919 * fold.fold_id
            rng = np.random.Generator(np.random.PCG64(seed))
            fn = POLICY_FNS[policy]
            path: list[float] = []
            for q_start in range(0, len(test), QUARTER_MONTHS):
                asof = test.index[q_start]
                trailing = returns[(returns.index >= fold.train_start) & (returns.index < asof)]
                weights = fn(trailing, rng=rng)
                block = test.iloc[q_start : q_start + QUARTER_MONTHS]
                path.extend((block.to_numpy() @ weights).tolist())
            arr = np.asarray(path)
            result.fold_results.append(
                FoldResult(
                    fold_id=fold.fold_id,
                    policy=policy,
                    terminal_log_wealth=float(np.log(np.prod(1.0 + arr))),
                    max_drawdown=dm.max_drawdown(arr),
                    seed=seed,
                )
            )
    return result


def wilcoxon_with_effect(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """Wilcoxon signed-rank ACROSS FOLDS with the rank-biserial effect size —
    per the sealed rule, the effect size always rides with the p-value."""
    if len(a) != len(b) or len(a) < 3:
        raise WalkForwardError("paired fold vectors of length >= 3 required")
    diff = a - b
    if np.allclose(diff, 0.0):
        return {"statistic": 0.0, "p_value": 1.0, "effect_size_rank_biserial": 0.0}
    res = stats.wilcoxon(a, b)
    ranks = stats.rankdata(np.abs(diff[diff != 0.0]))
    signs = np.sign(diff[diff != 0.0])
    r_rb = float(np.sum(ranks * signs) / np.sum(ranks))
    return {
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "effect_size_rank_biserial": r_rb,
    }
