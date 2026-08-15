"""The stress-scenario compiler (bootstrap-stratified).

Severity ranking of historical months for stress-scenario selection.
Three functionals: equity (rank by equity alone), joint_risk (equity + credit),
all_down (equity + credit + yields, the default — closes the flight-to-quality escape valve).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def _z(column: np.ndarray) -> np.ndarray:
    sd = float(column.std())
    if sd == 0.0:
        return np.zeros_like(column)
    return (column - float(column.mean())) / sd


def severity_score(
    values: np.ndarray, factor_names: Sequence[str], functional: str
) -> np.ndarray:
    """One severity score per row; LOWER IS MORE SEVERE.

    Components are z-scored so a spread in percentage points cannot dominate a
    return in decimals. Credit and yields enter NEGATED: a wide spread and a
    rising yield are both adverse, so negating them puts "bad" at the bottom
    alongside a negative equity return.
    """
    names = list(factor_names)
    x = np.asarray(values, dtype=np.float64)

    def col(name: str) -> np.ndarray:
        if name not in names:
            raise ValueError(f"panel has no factor '{name}'; available: {names}")
        return x[:, names.index(name)]

    equity = _z(col("equity_mkt"))
    if functional == "equity":
        return equity
    credit = -_z(col("hy_spread"))
    if functional == "joint_risk":
        return equity + credit
    if functional == "all_down":
        # a RISING long yield is adverse (no flight-to-quality bid), so the
        # bond leg enters negated exactly as credit does
        return equity + credit + -_z(col("ust_10y"))
    raise ValueError(
        f"unknown severity functional '{functional}'; known: equity, joint_risk, all_down"
    )


def eligible_rows(scores: np.ndarray, percentile: float) -> np.ndarray:
    """Row indices whose severity is at or below ``percentile`` (100 = all).

    Never empty: a percentile tight enough to select nothing would make its
    segment unsamplable, so the single worst row is the floor.
    """
    s = np.asarray(scores, dtype=np.float64)
    if percentile >= 100.0:
        return np.arange(s.size, dtype=np.int64)
    keep = max(1, int(np.floor(s.size * percentile / 100.0)))
    return np.sort(np.argsort(s, kind="stable")[:keep]).astype(np.int64)


#: Of the sealed 14-factor panel, these nine are LEVELS rather than increments.
#: Splicing a level at a block join teleports it; splicing a return does not.
LEVEL_FACTORS: tuple[str, ...] = (
    "equity_vol", "ig_spread", "hy_spread", "policy_rate",
    "ust_2y", "ust_10y", "cpi", "hqm_curve", "funding_spread",
)


def join_candidates(
    values: np.ndarray,
    factor_names: Sequence[str],
    current_row: int,
    tolerance: Mapping[str, float],
    pool: np.ndarray,
) -> np.ndarray:
    """Rows in ``pool`` reachable from ``current_row`` without a level teleport.

    A factor with no declared tolerance does not constrain. May return an empty
    array; the caller decides what to do (the sampler continues the block).
    """
    names = list(factor_names)
    x = np.asarray(values, dtype=np.float64)
    keep = np.ones(pool.size, dtype=bool)
    for factor, tol in tolerance.items():
        if factor not in names:
            raise ValueError(f"join tolerance names unknown factor '{factor}'")
        column = x[:, names.index(factor)]
        keep &= np.abs(column[pool] - column[int(current_row)]) <= float(tol)
    return pool[keep]
