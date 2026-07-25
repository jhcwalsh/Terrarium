"""The monthly-tier stylized-fact panel (WP2.2 Task 2).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``monthly.py`` bullet, and DN-1.1 Sec.II.6's monthly
row ("Stylized-fact panel: tail index, ACF |r|, skew, corr matrix; ... Pre-registered
bands (D6); beats bootstrap (G2) -- reference data 1926- panel"). Every metric here is
registered at tier ``"monthly"``.

Reuse, not reinvention
-----------------------
This project has already produced one sign-inverted, independently-restated metric
defect (see ``ah.eval.metrics.tails`` and its WP2.1b history). :mod:`ah.eval.reference`
already implements ``_skew`` (population moments, ``m3/m2**1.5``), ``_excess_kurtosis``
(population moments, ``m4/m2**2 - 3``), ``_acf1`` (Box-Jenkins, n-denominator, overall
mean), ``_correlation`` (Pearson on two aligned 1-D arrays) and ``_crisis_corr_lift``
(worst-decile-of-A conditional-correlation lift) -- every one of those definitions is
imported and reused verbatim below, never restated. New statistics this module
introduces for the first time (Hill tail index, ACF at lags beyond 1, aggregational
Gaussianity, leverage correlation, the ACF-decay fit, correlation-matrix distance) are
each defined exactly once, here.

Two population conventions, stated once
-----------------------------------------
An :class:`~ah.gen.base.Ensemble` carries ``n_paths`` independent simulated histories,
not one long historical series the way :mod:`ah.eval.reference` operates on. Every
metric below uses one of two explicit pooling conventions, chosen per statistic and
never mixed:

- **Pooled** (:func:`_pooled`): every ``(path, month)`` observation of one factor,
  flattened to 1-D, order irrelevant. Used only for statistics of the *marginal*
  distribution that do not depend on time order -- ``excess_kurtosis``, ``skew``, the
  Hill tail index, the aggregational-Gaussianity sums (after non-overlapping
  aggregation *within* each path), ``corr_matrix_distance``, and
  ``crisis_corr_lift`` (a joint-marginal, not a serial, statistic). Pooling paths
  together here is legitimate and enlarges the effective sample beyond one path's
  months, because none of these statistics reference a *previous* observation.
- **Per-path, then averaged** (:func:`_mean_over_paths`): every statistic that
  depends on time order -- ``acf_r_lag{1..5}``, ``acf_abs_lag{1..24}``,
  ``acf_abs_decay``, ``leverage_correlation``. Each is computed within one path's own
  month-series (never crossing a path boundary) and the per-path values are averaged.
  Concatenating paths end-to-end before computing a lag-dependent statistic would
  manufacture a spurious relationship at every path seam; this convention exists
  specifically to prevent that.

This mirrors :mod:`ah.eval.reference`'s own single-factor convention exactly: every
:data:`~ah.eval.reference.SINGLE_FACTOR_STATS` entry is computed over one factor's own
observations, on its own (train+validation) axis. The generated-side metrics below
apply the *same* underlying formula to the *generated* population, using whichever of
the two pooling conventions the statistic's own definition requires.

A metric whose factor is absent from a given ensemble (declared active in
``factors.yaml`` but ``kind: unavailable``, e.g. ``commodities`` -- see
:class:`ah.gen.base.UnknownFactorError`'s docstring) returns NaN rather than raising:
per THE ONE NaN RULE (``ah.eval.battery._passed``), an inapplicable metric must not
crash the whole battery run, and NaN already fails an enforce threshold on its own.

Naming, and where it does (and does not) reuse ``reference.py``'s keys
--------------------------------------------------------------------------
:class:`~ah.eval.battery.MetricSpec.name` follows ``"<factor>.<stat>"`` /
``"<factorA>~<factorB>.<stat>"`` so a metric's value can be matched, by name alone,
against a train+validation :class:`~ah.eval.reference.StatBand` computed over the same
quantity (:func:`ah.eval.battery._lookup_band`). Three deliberate naming choices, each
stated so the choice is visible rather than an accident of typing:

- ``skew`` and ``excess_kurtosis`` use exactly those words -- the same key
  :data:`~ah.eval.reference.SINGLE_FACTOR_STATS` already registers for the identical
  formula -- so a generated ensemble's skew/kurtosis is shown next to its historical
  band automatically, in every battery report, with no extra wiring.
- ``crisis_corr_lift`` is likewise named to match :data:`~ah.eval.reference.
  CROSS_BLOCK_STATS`'s existing key exactly -- **not** ``crisis_conditional_corr_lift``
  as STEP2-GENERATOR-PLAN's prose reads and as this task's brief headed it. The brief
  itself requires reusing ``reference._crisis_corr_lift``'s definition "rather than
  introducing a second one"; naming the *metric* differently from the *reference band*
  computing the identical quantity would silently orphan that reuse from the one place
  (``_lookup_band``) it would otherwise show up unprompted. This is a stated deviation
  from the brief's own suggested identifier, not an oversight.
- ``acf_r_lag{1..5}`` and ``acf_abs_lag{1..24}`` (plus ``acf_abs_decay``) are **not**
  aliased to ``reference.py``'s ``acf_1`` / ``acf_abs_1`` at lag 1, even though lag 1 is
  numerically the identical quantity. Aliasing only lag 1 while lags 2+ use the new
  naming scheme would make the suite's own naming inconsistent with itself for a
  marginal diagnostic benefit (the historical band showing up automatically at lag 1
  only). Every test below that touches lag 1 still asserts numeric agreement with
  ``reference._acf1`` directly, so the *reuse* obligation is met; only the *report
  display convenience* is left for a future task/WP2.3 amendment to pick up if wanted.
  Recorded as an open naming question for WP2.3, not resolved unilaterally here.
- ``corr_matrix_distance`` has no factor prefix at all: it is a single whole-panel
  aggregate, not a per-factor or per-pair statistic (see below).

Deferred registration: ``build_monthly_suite``, not import-time ``register_suite``
--------------------------------------------------------------------------------------
``ah.eval.battery``'s module docstring describes the common pattern as "calling
``register_suite()`` at import time" -- true for every metric here except
``corr_matrix_distance``, which structurally needs the train+validation
:class:`~ah.eval.reference.ReferenceStats` (the historical correlation matrix it is a
*distance to*) and a :class:`~ah.factors.FactorManifest` (which factors are active) to
even construct its specs. Neither is available at plain module import (computing
``ReferenceStats`` needs a live :class:`~ah.splits.DataAccess` over the real Step-1
catalog). Rather than splitting the suite across two registration paths (eight metric
groups registered at import, one deferred), this module registers the whole "monthly"
suite through one function, :func:`build_monthly_suite`, called once a manifest and a
computed reference are available (an orchestration wiring step for a later task, e.g.
the G2 harness or a battery-running CLI command -- not built here). Callers needing the
suite in ``battery.SUITES`` call ``register_suite("monthly", build_monthly_suite(
manifest, reference))`` themselves; this module does not do so as an import side
effect, and calling ``build_monthly_suite`` never edits ``ah.eval.battery.run_battery``.

``corr_matrix_distance``'s scope: cross-block pairs only
-----------------------------------------------------------
:data:`~ah.eval.reference.CROSS_BLOCK_STATS` registers ``correlation`` only for
cross-block factor pairs (every factor of block A against every factor of block B, for
each active block pair) -- there is currently no registered *within-block* pairwise
correlation statistic in ``reference.py`` at all. ``corr_matrix_distance`` can only be
a distance to a reference matrix that reference.py actually computes, so it is built
over exactly the factors that appear in at least one cross-block correlation entry,
with within-block pairs (and any factor with no cross-block partner) simply absent
from the matrix -- not zero-filled, which would falsely assert "reference says these
are uncorrelated" for a pair nothing has measured. Extending ``reference.py`` with a
within-block pairwise-correlation statistic (so this metric could cover the full
active factor set) is future work, recorded here rather than silently worked around.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.reference import (
    CrossBlockReference,
    ReferenceStats,
)
from ah.eval.reference import (
    _correlation as reference_correlation,
)
from ah.eval.reference import (
    _crisis_corr_lift as reference_crisis_corr_lift,
)
from ah.eval.reference import (
    _excess_kurtosis as reference_excess_kurtosis,
)
from ah.eval.reference import (
    _skew as reference_skew,
)
from ah.factors import FactorManifest
from ah.gen.base import Ensemble

SUITE = "monthly"
TIER = "monthly"

__all__ = [
    "SUITE",
    "TIER",
    "acf_abs_decay",
    "agg_gaussianity",
    "build_monthly_suite",
    "corr_matrix_distance",
    "hill_tail_index",
    "register_monthly_suite",
]


# --------------------------------------------------------------------------- #
# pooling helpers -- see the module docstring's "Two population conventions"
# --------------------------------------------------------------------------- #


def _pooled(ensemble: Ensemble, factor: str) -> np.ndarray:
    """Every ``(path, month)`` observation of ``factor``, flattened to float64 1-D."""
    return ensemble.factor(factor).reshape(-1).astype(np.float64)


def _mean_over_paths(fn: Callable[[np.ndarray], float], ensemble: Ensemble, factor: str) -> float:
    """Apply a 1-D time-series statistic to each path's own month-series, then average.

    NaN per-path results are dropped, not treated as 0 (a degenerate constant path
    genuinely has no ACF to report, and averaging it in as 0 would understate the
    dispersion of paths that *do* have one). If every path is degenerate the mean of
    an empty array is NaN -- the correct "uncomputable" signal.
    """
    slab = ensemble.factor(factor).astype(np.float64)
    per_path = np.array([fn(slab[i]) for i in range(slab.shape[0])], dtype=np.float64)
    per_path = per_path[~np.isnan(per_path)]
    if per_path.size == 0:
        return float("nan")
    return float(np.mean(per_path))


# --------------------------------------------------------------------------- #
# 1-3: excess kurtosis, skew, Hill tail index
# --------------------------------------------------------------------------- #

# excess_kurtosis and skew are reference._excess_kurtosis / reference._skew, applied to
# the pooled population -- no local reimplementation (see module docstring).


def hill_tail_index(x: np.ndarray, tail_fraction: float) -> float:
    """Hill estimator of the tail index of the LEFT tail (losses) of ``x``.

    Orientation, stated explicitly because a side error here is silent: ``x`` is a
    return series (positive = gain); losses are ``-x``. The Hill estimator is the
    classical estimator for the *right* tail of a positive random variable, so it is
    applied to ``losses = -x``, sorted **descending**: ``L_(1) >= L_(2) >= ... >=
    L_(n)``. With ``k = max(1, round(tail_fraction * n))`` (``tail_fraction=0.05`` is
    the "5%" threshold, i.e. the top ~5% largest losses), the estimator is the ratio
    form (Hill, 1975), using the ``(k+1)``-th order statistic as the threshold:

        alpha_hat = ( (1/k) * sum_{i=1..k} ln( L_(i) / L_(k+1) ) )^{-1}

    A **smaller** ``alpha_hat`` means a **fatter** (heavier) left tail. ``alpha_hat``
    is reported positive for a genuine Pareto-style heavy tail.

    Returns NaN -- never raises, and never silently returns a number computed from the
    wrong side -- whenever there is no left tail to estimate: fewer than ``k + 1``
    observations, any of the top ``k + 1`` "losses" is ``<= 0`` (i.e. not an actual
    loss -- an all-positive-return sample has no left tail at all, and a sample with
    fewer than ``k`` real losses cannot support this threshold), or the fitted mean
    log-ratio is ``<= 0`` (would invert to a non-positive/undefined tail index).
    """
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = x.shape[0]
    if not 0.0 < tail_fraction < 1.0:
        raise ValueError(f"hill_tail_index: tail_fraction must be in (0, 1), got {tail_fraction}")
    losses_sorted = np.sort(-x)[::-1]  # descending losses
    k = max(1, round(tail_fraction * n))
    if n < k + 1:
        return float("nan")
    top = losses_sorted[: k + 1]  # the k+1 largest losses, including L_(k+1)
    if np.any(top <= 0.0):
        return float("nan")
    threshold = top[-1]
    mean_log_ratio = float(np.mean(np.log(top[:-1] / threshold)))
    if not mean_log_ratio > 0.0:
        return float("nan")
    return 1.0 / mean_log_ratio


# --------------------------------------------------------------------------- #
# 4-5: ACF of returns (lags 1-5), ACF of |deviation| (lags 1-24) + fitted decay
# --------------------------------------------------------------------------- #


def _acf_at_lag(x: np.ndarray, lag: int) -> float:
    """``gamma_lag / gamma_0``, the Box-Jenkins convention: overall mean, n-denominator.

    Generalizes ``reference._acf1`` (which is exactly this function at ``lag=1``) to
    an arbitrary positive lag -- the identical convention, so this module's lag-1
    result agrees with ``reference._acf1`` bit-for-bit on the same input (asserted by
    test, not merely claimed).
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    if lag < 1 or n <= lag:
        return float("nan")
    dev = x - np.mean(x)
    gamma0 = float(np.sum(dev**2) / n)
    if gamma0 == 0.0:
        return float("nan")
    gamma_lag = float(np.sum(dev[:-lag] * dev[lag:]) / n)
    return gamma_lag / gamma0


def _fit_exp_decay_rate(lags: np.ndarray, values: np.ndarray) -> float:
    """Least-squares exponential-decay rate for ``(lag, value)`` pairs.

    Fitted form, stated fully because WP2.3 seals a band on it: ``value ~= A *
    exp(-rate * lag)``, fitted by ordinary least squares in log space -- ``ln(value) =
    ln(A) - rate * lag`` -- over every pair with ``value > 0`` (a non-positive ACF
    value has no logarithm and is dropped, never clamped to a small positive number,
    which would bias the fit). ``rate`` is returned **signed**: a genuinely *decaying*
    autocorrelation (the stylized fact this exists to check) gives ``rate > 0``; a
    curve that grows with lag gives ``rate < 0`` rather than being silently floored at
    zero, so a badly-behaved input is visible in the sign, not hidden.

    NaN if fewer than 2 usable (``lag``, ``value > 0``) pairs remain, or if every
    usable lag is identical (a zero-variance regressor -- no slope is fittable).
    """
    lags = np.asarray(lags, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    mask = values > 0.0
    if int(np.sum(mask)) < 2:
        return float("nan")
    lag_v = lags[mask]
    log_v = np.log(values[mask])
    lag_mean = np.mean(lag_v)
    log_mean = np.mean(log_v)
    denom = float(np.sum((lag_v - lag_mean) ** 2))
    if denom == 0.0:
        return float("nan")
    slope = float(np.sum((lag_v - lag_mean) * (log_v - log_mean)) / denom)
    return -slope


def acf_abs_decay(ensemble: Ensemble, factor: str, max_lag: int = 24) -> float:
    """Fitted exponential-decay rate of ``factor``'s ACF(|deviation|), lags 1..``max_lag``.

    Computes :func:`_acf_at_lag` on ``|x - mean(x)|`` for every lag in ``1..max_lag``
    (per-path, then averaged across paths -- see the module docstring's pooling
    convention; the same quantity as ``acf_abs_lag{k}`` at each ``k``), then fits
    :func:`_fit_exp_decay_rate` to the resulting 24-point curve.
    """
    lags = np.arange(1, max_lag + 1)
    values = np.array(
        [
            _mean_over_paths(
                lambda s, lag_=lag: _acf_at_lag(np.abs(s - np.mean(s)), lag_), ensemble, factor
            )
            for lag in lags
        ],
        dtype=np.float64,
    )
    return _fit_exp_decay_rate(lags.astype(np.float64), values)


# --------------------------------------------------------------------------- #
# 6: aggregational Gaussianity
# --------------------------------------------------------------------------- #


def _nonoverlapping_sums(x: np.ndarray, horizon_months: int) -> np.ndarray:
    """Non-overlapping ``horizon_months``-month sums of a 1-D series (partial tail dropped)."""
    n = x.shape[0]
    usable = (n // horizon_months) * horizon_months
    if usable == 0:
        return np.empty(0, dtype=np.float64)
    return x[:usable].reshape(-1, horizon_months).sum(axis=1)


def agg_gaussianity(ensemble: Ensemble, factor: str, horizon_months: int) -> float:
    """Excess kurtosis of non-overlapping ``horizon_months``-month sums of ``factor``.

    Sums are computed independently within each path (never spanning a path
    boundary), then **pooled** across paths before the kurtosis is taken -- this is a
    marginal-distribution statistic (like ``excess_kurtosis`` itself), not a
    time-ordering-dependent one, so pooling is the same legitimate convention
    :func:`_pooled` uses elsewhere. Reuses ``reference._excess_kurtosis`` (the sealed
    definition), not a second one.

    The stylized fact this metric exists to check: excess kurtosis decays toward 0 as
    ``horizon_months`` grows (aggregational Gaussianity -- a slow approach to the CLT
    limit for a fat-tailed monthly return). NaN if fewer than 4 pooled sums are
    available (a 4th-standardized-moment statistic needs more than a handful of
    points to mean anything).
    """
    slab = ensemble.factor(factor).astype(np.float64)
    sums = np.concatenate(
        [_nonoverlapping_sums(slab[i], horizon_months) for i in range(slab.shape[0])]
    )
    if sums.size < 4:
        return float("nan")
    return reference_excess_kurtosis(sums)


# --------------------------------------------------------------------------- #
# 7: leverage correlation
# --------------------------------------------------------------------------- #


def _leverage_one_path(x: np.ndarray) -> float:
    """``corr(r_t, |r_{t+1} - mean(r)|)`` within one path -- the leverage effect.

    Lag: **1 month** (this month's return vs. next month's realized volatility
    proxy). Volatility proxy: ``|r_{t+1} - mean(r)|``, the absolute deviation of next
    month's return from *this path's own* mean -- the same ``|x - mean(x)|``
    convention ``reference._acf_abs_1`` already uses for volatility clustering, so the
    proxy is not a third, independently-invented one. A negative result is the
    classical leverage effect (a down month is followed by higher realized
    volatility); NaN if the path has fewer than 3 months (need at least 2 paired
    ``(r_t, vol_{t+1})`` observations to correlate).
    """
    x = np.asarray(x, dtype=np.float64)
    if x.shape[0] < 3:
        return float("nan")
    mean_x = np.mean(x)
    r_t = x[:-1]
    vol_next = np.abs(x[1:] - mean_x)
    return reference_correlation(r_t, vol_next)


# --------------------------------------------------------------------------- #
# 8: correlation-matrix distance
# --------------------------------------------------------------------------- #


def corr_matrix_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distance between two same-shaped correlation matrices: the **Frobenius norm**
    of their difference, ``sqrt(sum((a - b)**2))``.

    Chosen over the (also standard) Herdin et al. correlation-matrix-distance
    similarity measure (``1 - trace(a @ b) / (norm(a, 'fro') * norm(b, 'fro'))``,
    scale/rotation-normalized, symmetric under global rescaling of either matrix)
    because the raw Frobenius difference is the simpler, more literal reading of "how
    far apart are these two matrices" for two correlation matrices that are already on
    the same (bounded, [-1, 1]-entried) scale by construction -- no normalization is
    needed to make the two comparable. ``0`` for two identical matrices; strictly
    positive and monotonically larger the more the two matrices' entries differ.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"corr_matrix_distance: shape mismatch {a.shape} vs {b.shape}")
    return float(np.linalg.norm(a - b, ord="fro"))


def _reference_pairwise_correlations(
    cross_blocks: dict[tuple[str, str], CrossBlockReference],
) -> dict[frozenset[str], float]:
    """Every cross-block factor-pair ``correlation`` point ``reference.py`` computed.

    Keyed by an unordered pair (``frozenset`` of the two factor names), so lookup does
    not depend on which block was iterated first when the pair was originally keyed
    ``"<factorA>~<factorB>"``. Carries no within-block pairs (see module docstring).
    """
    out: dict[frozenset[str], float] = {}
    for cross_ref in cross_blocks.values():
        for key, band in cross_ref.stats.items():
            if not key.endswith(".correlation"):
                continue
            fa, fb = key[: -len(".correlation")].split("~")
            out[frozenset((fa, fb))] = band.point
    return out


def _corr_matrices(
    ensemble: Ensemble, reference: ReferenceStats, active_factors: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray] | None:
    """The ensemble's and the reference's correlation matrices over the same factor axis.

    The factor axis is exactly the factors that (a) are declared active and (b) have
    at least one cross-block reference correlation entry -- see the module docstring's
    "corr_matrix_distance's scope". Returns ``None`` (metric reports NaN) if fewer
    than 2 such factors exist, or if none of them are present in this particular
    ``ensemble`` (e.g. every covered factor happens to be ``kind: unavailable``).
    """
    ref_pairs = _reference_pairwise_correlations(reference.cross_blocks)
    covered_all = sorted({f for pair in ref_pairs for f in pair} & set(active_factors))
    covered = [f for f in covered_all if f in ensemble.factor_names]
    m = len(covered)
    if m < 2:
        return None
    ens_matrix = np.eye(m, dtype=np.float64)
    ref_matrix = np.eye(m, dtype=np.float64)
    pooled = {f: _pooled(ensemble, f) for f in covered}
    for i in range(m):
        for j in range(i + 1, m):
            fa, fb = covered[i], covered[j]
            key = frozenset((fa, fb))
            if key not in ref_pairs:
                continue
            ref_matrix[i, j] = ref_matrix[j, i] = ref_pairs[key]
            ens_matrix[i, j] = ens_matrix[j, i] = reference_correlation(pooled[fa], pooled[fb])
    return ens_matrix, ref_matrix


def _make_corr_matrix_distance_metric(
    reference: ReferenceStats, active_factors: tuple[str, ...]
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        matrices = _corr_matrices(ensemble, reference, active_factors)
        if matrices is None:
            return float("nan")
        ens_matrix, ref_matrix = matrices
        return corr_matrix_distance(ens_matrix, ref_matrix)

    return fn


# --------------------------------------------------------------------------- #
# 9: crisis-conditional correlation lift -- reference._crisis_corr_lift, reused
# --------------------------------------------------------------------------- #

# No local definition: applied directly to pooled (path x month) observations of the
# two factors in build_monthly_suite() below. See module docstring's "Reuse, not
# reinvention" and "Naming" sections.


# --------------------------------------------------------------------------- #
# MetricSpec factories: guard against a factor absent from a given ensemble
# --------------------------------------------------------------------------- #


def _spec(name: str, fn: MetricFn) -> MetricSpec:
    return MetricSpec(name=name, tier=TIER, fn=fn, suite=SUITE)


def _pooled_metric(factor: str, stat: Callable[[np.ndarray], float]) -> MetricFn:
    """``stat`` applied to ``factor``'s pooled population; NaN if ``factor`` is absent
    from a given ensemble (see module docstring's NaN-on-absent-factor rule)."""

    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return stat(_pooled(ensemble, factor))

    return fn


def _per_path_metric(factor: str, stat: Callable[[np.ndarray], float]) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return _mean_over_paths(stat, ensemble, factor)

    return fn


def _cross_factor_metric(
    fa: str, fb: str, stat: Callable[[np.ndarray, np.ndarray], float]
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if fa not in ensemble.factor_names or fb not in ensemble.factor_names:
            return float("nan")
        return stat(_pooled(ensemble, fa), _pooled(ensemble, fb))

    return fn


def _agg_gaussianity_metric(factor: str, horizon_months: int) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return agg_gaussianity(ensemble, factor, horizon_months)

    return fn


def _acf_abs_decay_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return acf_abs_decay(ensemble, factor)

    return fn


# --------------------------------------------------------------------------- #
# build_monthly_suite / register_monthly_suite
# --------------------------------------------------------------------------- #


def build_monthly_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every monthly-tier :class:`~ah.eval.battery.MetricSpec`, for ``manifest``'s
    active factors and cross-block pairs. See the module docstring for naming, pooling
    convention, and why this is a builder rather than an import-time registration."""
    specs: list[MetricSpec] = []
    active = manifest.active_factors()

    for factor in active:
        specs.append(
            _spec(f"{factor}.excess_kurtosis", _pooled_metric(factor, reference_excess_kurtosis))
        )
        specs.append(_spec(f"{factor}.skew", _pooled_metric(factor, reference_skew)))
        specs.append(
            _spec(
                f"{factor}.hill_tail_index_5pct",
                _pooled_metric(factor, lambda x: hill_tail_index(x, 0.05)),
            )
        )
        specs.append(
            _spec(
                f"{factor}.hill_tail_index_1pct",
                _pooled_metric(factor, lambda x: hill_tail_index(x, 0.01)),
            )
        )
        for lag in range(1, 6):
            specs.append(
                _spec(
                    f"{factor}.acf_r_lag{lag}",
                    _per_path_metric(factor, lambda s, lag_=lag: _acf_at_lag(s, lag_)),
                )
            )
        for lag in range(1, 25):
            specs.append(
                _spec(
                    f"{factor}.acf_abs_lag{lag}",
                    _per_path_metric(
                        factor, lambda s, lag_=lag: _acf_at_lag(np.abs(s - np.mean(s)), lag_)
                    ),
                )
            )
        specs.append(_spec(f"{factor}.acf_abs_decay", _acf_abs_decay_metric(factor)))
        for horizon, suffix in ((1, "1m"), (3, "3m"), (12, "12m")):
            specs.append(
                _spec(
                    f"{factor}.agg_gaussianity_{suffix}", _agg_gaussianity_metric(factor, horizon)
                )
            )
        specs.append(
            _spec(f"{factor}.leverage_correlation", _per_path_metric(factor, _leverage_one_path))
        )

    active_set = set(active)
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
                    _spec(
                        f"{fa}~{fb}.crisis_corr_lift",
                        _cross_factor_metric(fa, fb, reference_crisis_corr_lift),
                    )
                )

    specs.append(
        _spec("corr_matrix_distance", _make_corr_matrix_distance_metric(reference, active))
    )

    return tuple(specs)


def register_monthly_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("monthly", build_monthly_suite(manifest, reference))``."""
    register_suite(SUITE, build_monthly_suite(manifest, reference))
