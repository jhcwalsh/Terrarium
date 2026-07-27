"""The two ensemble pooling conventions, defined once for every metric suite.

An :class:`~ah.gen.base.Ensemble` carries ``n_paths`` independent simulated histories,
while :mod:`ah.eval.reference` defines every statistic over one flat series. Turning the
former into the latter is a *decision*, taken per statistic, and there are exactly two
sanctioned answers:

- :func:`pooled` -- every ``(path, month)`` observation of one factor, flattened, order
  irrelevant. Legitimate only for statistics of the *marginal* distribution, which never
  reference a previous observation.
- :func:`mean_over_paths` -- the statistic computed within each path's own month-series
  (never crossing a path boundary), then averaged. Mandatory for every time-ordered
  statistic: concatenating paths end to end before computing a lag-dependent statistic
  manufactures a spurious relationship at every path seam.

They live here rather than being copied into each suite (WP2.2 Task 3 fix pass 1, Minor
1). ``ah.eval.metrics.monthly`` and ``ah.eval.metrics.horizon`` previously carried
character-identical private copies of ``_mean_over_paths``, and the two must never
diverge: they are the same convention, sealed once in ``pre-registration.yaml``, and a
silent divergence between them would mean two suites pooling differently under one
sealed statement. Each suite still states *which* convention each of its metrics uses
and why -- that argument is per statistic and belongs in the suite; only the mechanism
is shared.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ah.gen.base import Ensemble

__all__ = ["mean_over_paths", "pooled"]


def pooled(ensemble: Ensemble, factor: str) -> np.ndarray:
    """Every ``(path, month)`` observation of ``factor``, flattened to float64 1-D."""
    return ensemble.factor(factor).reshape(-1).astype(np.float64)


def mean_over_paths(fn: Callable[[np.ndarray], float], ensemble: Ensemble, factor: str) -> float:
    """Apply a 1-D time-series statistic to each path's own month-series, then average.

    NaN per-path results are dropped, not treated as 0 (a degenerate constant path
    genuinely has no ACF to report, and averaging it in as 0 would understate the
    dispersion of paths that *do* have one). If every path is degenerate the mean of an
    empty array is NaN -- the correct "uncomputable" signal.
    """
    slab = ensemble.factor(factor).astype(np.float64)
    per_path = np.array([fn(slab[i]) for i in range(slab.shape[0])], dtype=np.float64)
    per_path = per_path[~np.isnan(per_path)]
    if per_path.size == 0:
        return float("nan")
    return float(np.mean(per_path))
