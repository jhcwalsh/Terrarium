"""Stylized-fact panel functions over a returns matrix (STEP0-PLAN §WP0.8).

Pure numpy (pandas is permitted in this package but unnecessary here). These are the
descriptive statistics the validation battery evaluates against ``thresholds.yaml``.
Step 0 ships the plumbing; the numeric gates are pre-registered later (D6 workshop).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def excess_kurtosis(returns: np.ndarray) -> float:
    """Excess kurtosis (0 for a normal distribution)."""
    r = np.asarray(returns, dtype=np.float64).ravel()
    mu = r.mean()
    var = r.var()
    if var == 0:
        return 0.0
    return float(((r - mu) ** 4).mean() / var**2 - 3.0)


def skewness(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype=np.float64).ravel()
    mu = r.mean()
    std = r.std()
    if std == 0:
        return 0.0
    return float(((r - mu) ** 3).mean() / std**3)


def hill_tail_index(returns: np.ndarray, tail: float = 0.05) -> float:
    """Hill estimator of the tail index alpha on the upper tail of |returns|.

    Higher alpha = thinner tail. Returns ``nan`` if the tail is degenerate.
    """
    x = np.sort(np.abs(np.asarray(returns, dtype=np.float64).ravel()))[::-1]
    n = x.size
    k = max(1, int(np.ceil(tail * n)))
    if k + 1 > n:
        return float("nan")
    threshold = x[k]
    if threshold <= 0:
        return float("nan")
    top = x[:k]
    hill = np.mean(np.log(top) - np.log(threshold))
    if hill <= 0:
        return float("nan")
    return float(1.0 / hill)


def acf(returns: np.ndarray, lags: Sequence[int]) -> list[float]:
    """Autocorrelation of a 1-D return series at the given lags (biased estimator)."""
    r = np.asarray(returns, dtype=np.float64).ravel()
    n = r.size
    mu = r.mean()
    denom = np.sum((r - mu) ** 2)
    out: list[float] = []
    for k in lags:
        if k <= 0 or k >= n or denom == 0:
            out.append(0.0)
            continue
        num = np.sum((r[k:] - mu) * (r[:-k] - mu))
        out.append(float(num / denom))
    return out


def acf_abs(returns: np.ndarray, lags: Sequence[int]) -> list[float]:
    """Autocorrelation of |returns| (a vol-clustering signature)."""
    return acf(np.abs(np.asarray(returns, dtype=np.float64).ravel()), lags)


def max_drawdown(returns: np.ndarray) -> float:
    """Max drawdown of one return series (percent returns), as a negative fraction."""
    r = np.asarray(returns, dtype=np.float64).ravel()
    growth = np.maximum(0.0, 1.0 + r / 100.0)
    value = np.cumprod(growth)
    running_max = np.maximum.accumulate(value)
    drawdowns = value / running_max - 1.0
    return float(drawdowns.min()) if drawdowns.size else 0.0


def max_drawdown_distribution(matrix: np.ndarray) -> np.ndarray:
    """Per-path max drawdown for a (n_paths, months) matrix."""
    m = np.asarray(matrix, dtype=np.float64)
    return np.array([max_drawdown(m[i]) for i in range(m.shape[0])])


def cross_correlation_matrix(matrix: np.ndarray) -> np.ndarray:
    """Correlation matrix over columns of a (T, k) matrix."""
    m = np.asarray(matrix, dtype=np.float64)
    return np.asarray(np.corrcoef(m, rowvar=False))


def corr_matrix_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Frobenius distance between two correlation matrices."""
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))
