"""Emergent-depth, coherence, and plausibility reports for a stress ensemble.

Task 6 of the stress-scenario compiler build. Three functions, each a pure
measurement -- no thresholds, no pass/fail. `depth_report` and
`coherence_report` are the reader's sanity checks that the compiler is doing
what it claims (a real drawdown got assembled; the block structure did not
collapse into an i.i.d. shuffle). `plausibility_report` is the disclosure
required by spec v0.2 A2: every emitted month is a real historical row, so a
month-level novelty statistic is trivially zero -- the only place invention
can show up is in the *sequence* the compiler assembles. All three are
printed for the reader's own judgment, never used to gate a run.

Run as a script, it builds the stress_1974 world and prints all three:

    uv run python scripts/stress_report.py

Importing this module (as the tests do) never touches the catalog -- the
catalog read only happens under ``if __name__ == "__main__":``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ah.gen.base import Ensemble
from ah.gen.bootstrap import BootstrapSource

_PRESETS = Path(__file__).resolve().parents[1] / "src" / "ah" / "presets"
_ROLLING_WINDOW = 12
_RIDGE = 1e-9


# --------------------------------------------------------------------------- #
# depth_report
# --------------------------------------------------------------------------- #


def _drawdown(equity_returns: np.ndarray) -> tuple[float, int]:
    """(depth, duration_months) of one path's deepest equity drawdown.

    ``depth`` is the most negative point of wealth/running-max - 1 (<= 0 by
    construction, since wealth starts equal to its own running max).
    ``duration_months`` is the month count from the peak that set the running
    max at the trough to the trough itself.
    """
    wealth = np.cumprod(1.0 + equity_returns)
    running_max = np.maximum.accumulate(wealth)
    drawdown = wealth / running_max - 1.0
    trough = int(np.argmin(drawdown))
    # last index at or before the trough where wealth matched its running max
    at_peak = np.flatnonzero(wealth[: trough + 1] == running_max[trough])
    peak = int(at_peak[-1]) if at_peak.size else 0
    return float(drawdown[trough]), trough - peak


def depth_report(ensemble: Ensemble) -> dict[str, float]:
    """Per-path equity drawdown depth/duration and the hy_spread peak level.

    ``median_peak_to_trough``: median across paths of each path's deepest
    cumulative-return drawdown (equity_mkt is a monthly return in decimals).
    ``median_drawdown_months``: median across paths of that drawdown's
    peak-to-trough duration. ``hy_spread_peak``: median across paths of each
    path's own maximum hy_spread level.
    """
    equity = ensemble.factor("equity_mkt")
    hy_spread = ensemble.factor("hy_spread")

    depths = np.empty(ensemble.n_paths)
    durations = np.empty(ensemble.n_paths)
    for p in range(ensemble.n_paths):
        depths[p], durations[p] = _drawdown(equity[p])
    spread_peaks = hy_spread.max(axis=1)

    return {
        "median_peak_to_trough": float(np.median(depths)),
        "median_drawdown_months": float(np.median(durations)),
        "hy_spread_peak": float(np.median(spread_peaks)),
    }


# --------------------------------------------------------------------------- #
# coherence_report
# --------------------------------------------------------------------------- #


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation between two equal-length 1-D arrays.

    A zero-variance side (constant input) would make ``np.corrcoef`` divide
    by a zero std; reported as 0.0 -- "no measurable persistence" is the
    honest report for a series with no variance, not a crash.
    """
    if a.size < 2 or float(a.std()) == 0.0 or float(b.std()) == 0.0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _lag1_autocorr(x: np.ndarray) -> float:
    """Pearson correlation between x[:-1] and x[1:]."""
    if x.size < 2:
        return 0.0
    return _corr(x[:-1], x[1:])


def coherence_report(ensemble: Ensemble, source: BootstrapSource) -> dict[str, float | int]:
    """Autocorrelation and join-seam diagnostics against the source panel.

    ``ac1_generated``: lag-1 autocorrelation of equity_mkt, POOLED across
    paths -- every path's (x[:-1], x[1:]) pairs are concatenated into one
    array before a single correlation is taken, rather than averaging one
    coefficient per path, so a handful of very short paths cannot outweigh
    the same number of pairs drawn from a long one.
    ``ac1_panel``: the same statistic computed once on ``source.values``'
    equity_mkt column.
    ``join_count``: total row_indices steps that are not +1 (mod n) across
    every path, excluding month 0 (there is no step INTO month 0 to judge).
    ``max_level_jump``: the largest absolute hy_spread change observed at any
    such join.
    """
    names = list(ensemble.factor_names)
    equity_idx = names.index("equity_mkt")
    hy_idx = names.index("hy_spread")

    gen_a = ensemble.paths[:, :-1, equity_idx].reshape(-1)
    gen_b = ensemble.paths[:, 1:, equity_idx].reshape(-1)
    ac1_generated = _corr(gen_a, gen_b)

    panel_equity = source.values[:, list(source.factor_names).index("equity_mkt")]
    ac1_panel = _lag1_autocorr(panel_equity)

    if ensemble.row_indices is None:
        raise ValueError("coherence_report needs an ensemble with row_indices (a resampler)")
    idx = ensemble.row_indices
    n = source.n_rows
    steps = (idx[:, 1:] - idx[:, :-1]) % n
    joined = steps != 1

    join_count = int(joined.sum())
    if join_count == 0:
        max_level_jump = 0.0
    else:
        hy = ensemble.paths[:, :, hy_idx]
        jumps = np.abs(hy[:, 1:] - hy[:, :-1])[joined]
        max_level_jump = float(jumps.max())

    return {
        "ac1_generated": ac1_generated,
        "ac1_panel": ac1_panel,
        "join_count": join_count,
        "max_level_jump": max_level_jump,
    }


# --------------------------------------------------------------------------- #
# plausibility_report
# --------------------------------------------------------------------------- #


def _rolling_mean_windows(values: np.ndarray, window: int) -> np.ndarray:
    """(T, F) -> (T - window + 1, F) rolling mean vectors, via a cumsum trick."""
    t = values.shape[0]
    if t < window:
        return np.empty((0, values.shape[1]), dtype=np.float64)
    cumsum = np.concatenate(
        [np.zeros((1, values.shape[1]), dtype=np.float64), np.cumsum(values, axis=0)], axis=0
    )
    return (cumsum[window:] - cumsum[:-window]) / float(window)


def _mahalanobis(vectors: np.ndarray, mean: np.ndarray, inv_cov: np.ndarray) -> np.ndarray:
    diff = vectors - mean
    quad = np.einsum("ij,jk,ik->i", diff, inv_cov, diff)
    return np.sqrt(np.clip(quad, 0.0, None))


def plausibility_report(ensemble: Ensemble, source: BootstrapSource) -> dict[str, float]:
    """Mahalanobis novelty of the generated sequence, in rolling-12m space.

    Spec v0.2 A2: every emitted month is a real panel row, so a month-level
    novelty statistic is trivially zero. The invention (if any) lives in the
    SEQUENCE the compiler assembles, which rolling 12-month mean vectors make
    visible. The panel's own rolling vectors are the reference distribution
    (mean + covariance, ridged by 1e-9 on the diagonal for invertibility);
    each generated path's rolling vectors are scored against that reference.
    Reported alongside the panel's own 95th-percentile distance against
    itself, as a yardstick -- a large distance is disclosure, not failure.
    """
    panel_names = list(source.factor_names)
    gen_names = list(ensemble.factor_names)
    if panel_names != gen_names:
        # align the generated columns onto the panel's column order so the
        # covariance/mean reference and the scored vectors describe the same
        # feature space
        order = [gen_names.index(name) for name in panel_names]
    else:
        order = list(range(len(panel_names)))

    panel_windows = _rolling_mean_windows(source.values, _ROLLING_WINDOW)
    mean = panel_windows.mean(axis=0)
    cov = np.cov(panel_windows, rowvar=False) + _RIDGE * np.eye(panel_windows.shape[1])
    inv_cov = np.linalg.inv(cov)

    panel_dists = _mahalanobis(panel_windows, mean, inv_cov)

    gen_vectors = []
    for p in range(ensemble.n_paths):
        path_values = ensemble.paths[p][:, order]
        gen_vectors.append(_rolling_mean_windows(path_values, _ROLLING_WINDOW))
    gen_windows = np.concatenate(gen_vectors, axis=0)
    gen_dists = _mahalanobis(gen_windows, mean, inv_cov)

    return {
        "mahalanobis_median": float(np.median(gen_dists)),
        "mahalanobis_max": float(np.max(gen_dists)),
        "panel_mahalanobis_p95": float(np.percentile(panel_dists, 95)),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print_report(title: str, report: dict[str, Any]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for key, value in report.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.6f}")
        else:
            print(f"  {key}: {value}")


def main() -> None:
    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec
    from ah.gen.bootstrap import campaign_source
    from ah.gen.stress import StressBootstrap

    doc = json.loads((_PRESETS / "stress_1974.json").read_text(encoding="utf-8"))
    world = project_numeric(WorldSpec.model_validate(doc))
    if world.stress is None:
        raise SystemExit("stress_1974 preset declares no extensions.x_stress")

    seed = world.engine_defaults.base_seed
    if seed is None:
        raise SystemExit("stress_1974 preset declares no engine_defaults.base_seed")

    source = campaign_source()
    gen = StressBootstrap(source)
    ensemble = gen.sample(world, n_paths=world.engine_defaults.n_paths, seed=seed)

    print(f"stress_1974: {ensemble.n_paths} paths x {ensemble.months} months")
    _print_report("depth", depth_report(ensemble))
    _print_report("coherence", coherence_report(ensemble, source))
    _print_report("plausibility", plausibility_report(ensemble, source))
    print()


if __name__ == "__main__":
    main()
