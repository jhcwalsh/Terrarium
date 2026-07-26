"""The monthly-tier stylized-fact panel (WP2.2 Task 2).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``monthly.py`` bullet, and DN-1.1 Sec.II.6's monthly
row ("Stylized-fact panel: tail index, ACF |r|, skew, corr matrix; ... Pre-registered
bands (D6); beats bootstrap (G2) -- reference data 1926- panel"). Every metric here is
registered at tier ``"monthly"``.

Where the definitions live, and why not here
----------------------------------------------
**Every statistic this suite reports is defined in :mod:`ah.eval.reference`, not in this
module.** That is a structural requirement, not a style preference:
:mod:`ah.eval.prereg` validates a threshold key's ``<stat>`` against
:data:`~ah.eval.reference.SINGLE_FACTOR_STATS` /
:data:`~ah.eval.reference.CROSS_BLOCK_STATS` / :data:`~ah.eval.reference.PANEL_STATS`,
and once ``sealed: true`` lands :func:`ah.eval.battery.run_battery` calls
:func:`ah.eval.prereg.verify` on **every** invocation. A statistic defined only in a
metric suite therefore could not carry a sealed threshold at all, and an entry authored
under its name would break every battery run rather than only the seal. Defining them in
``reference.py`` also earns each one a computed train+validation band for free.

What this module contributes is the layer above the estimators: the two
:class:`~ah.gen.base.Ensemble` pooling conventions, the absent-factor NaN guard, and the
:class:`~ah.eval.battery.MetricSpec` wiring. It restates no formula.

Two population conventions, stated once
-----------------------------------------
An :class:`~ah.gen.base.Ensemble` carries ``n_paths`` independent simulated histories,
not one long historical series the way :mod:`ah.eval.reference` operates on. Every
metric below uses one of two explicit pooling conventions, chosen per statistic and
never mixed:

- **Pooled** (:func:`_pooled`): every ``(path, month)`` observation of one factor,
  flattened to 1-D, order irrelevant. Used only for statistics of the *marginal*
  distribution that do not depend on time order -- ``excess_kurtosis``, ``skew``, the
  Hill tail indices, the aggregational-Gaussianity sums (after non-overlapping
  aggregation *within* each path), ``cross_block_corr_matrix_distance``, and
  ``crisis_corr_lift`` (a joint-marginal, not a serial, statistic). Pooling paths
  together here is legitimate and enlarges the effective sample beyond one path's
  months, because none of these statistics references a *previous* observation.
- **Per-path, then averaged** (:func:`_mean_over_paths`): every statistic that depends
  on time order -- ``acf_r_lag{1..5}``, ``acf_abs_lag{1..24}``, ``acf_abs_decay``,
  ``leverage_correlation``. Each is computed within one path's own month-series (never
  crossing a path boundary) and the per-path values are averaged. Concatenating paths
  end-to-end before computing a lag-dependent statistic would manufacture a spurious
  relationship at every path seam; this convention exists specifically to prevent that.

``acf_abs_decay`` follows the per-path convention like every other time-ordered
statistic -- fit one path's own 24-lag curve, then average the rates. An earlier version
averaged the *curve* across paths and fitted once, which is a materially **less biased**
estimator of the true decay rate and, for exactly that reason, is **not** the one to
use: the reference band is the distribution of the same statistic over a single series
of the ensemble's path length, so the ensemble side must apply the same single-series
functional or the two are not comparable (see "Length matching" below). The metric's job
is comparison against history, not estimation of a physical constant.

Length matching, and the residual it does not cover
------------------------------------------------------
:func:`ah.eval.reference.compute_reference` draws its bootstrap replicates at the judged
ensemble's own path length (``resample_length``; :func:`ah.eval.battery.run_full_battery`
passes it). Every per-path statistic here uses the n-denominator Box-Jenkins ACF
estimator, whose finite-sample bias is a function of series length -- the ``(n - k) / n``
shrinkage alone is ~20% at lag 24 on a 120-month path against ~2% on the ~1100-month
history -- so without length matching a generator reproducing history *exactly* would
report materially smaller ``acf_abs_lag{12..24}`` and a materially larger
``acf_abs_decay`` than its own reference band, purely as an artifact. Length matching
puts the identical bias on both sides. (The alternative, an ``(n - k)`` denominator, was
rejected: it would have to change :func:`ah.eval.reference._acf1` too -- the two must
never diverge -- and it corrects only the shrinkage term, leaving the mean-subtraction
bias intact and still length-dependent.)

**Residual, stated rather than left to be discovered.** Length matching is applied
uniformly, at the path length. That is exactly right for the per-path statistics. For the
*pooled* statistics it is not: this suite computes ``skew``, ``excess_kurtosis``, the
Hill indices, the aggregational-Gaussianity kurtoses and ``crisis_corr_lift`` over
``n_paths * months`` pooled observations, while a reference replicate carries only
``months``. Sample skewness, kurtosis and the Hill index are all biased at small samples,
so for those statistics the two sides are matched in neither sample size nor bias; their
bands are conservatively wide, and a fat-tailed generator will read as further from
history than it is. Closing that means a per-statistic resample length (pooled statistics
matched to ``n_paths * months``, per-path statistics to ``months``), which is a change to
``reference.py``'s draw structure -- ``governance/retrofit-register.md`` RFR-15, owned by
WP2.3, which must decide before it seals a band over any pooled statistic.

A metric whose factor is absent from a given ensemble (declared active in
``factors.yaml`` but ``kind: unavailable``, e.g. ``commodities`` -- see
:class:`ah.gen.base.UnknownFactorError`'s docstring) returns NaN rather than raising:
per THE ONE NaN RULE (``ah.eval.battery._passed``), an inapplicable metric must not
crash the whole battery run, and NaN already fails an enforce threshold on its own.

Naming
--------
:class:`~ah.eval.battery.MetricSpec.name` is ``"<factor>.<stat>"`` /
``"<factorA>~<factorB>.<stat>"`` / (for a whole-panel statistic) a bare ``"<stat>"``, and
in every case ``<stat>`` is **exactly** a key of the corresponding ``reference.py``
registry. That is what lets a metric's value be matched, by name alone, against its
train+validation :class:`~ah.eval.reference.StatBand`
(:func:`ah.eval.battery._lookup_band`) and against its sealed
:class:`~ah.eval.prereg.Threshold` (:func:`ah.eval.battery._lookup_threshold`). There is
no metric-only naming scheme; the registries are the vocabulary.

Two naming decisions were reversed in this task's fix pass, both because they would have
put two sealed names on one number:

- ``acf_1`` / ``acf_abs_1`` became ``acf_r_lag1`` / ``acf_abs_lag1``, so lag 1 is not
  registered twice under two schemes.
- ``agg_gaussianity_1m`` is gone entirely: the h=1 aggregation is the identity, so it was
  bit-identical to ``excess_kurtosis``. The aggregational-Gaussianity *ordering*
  (kurtosis decaying toward 0 with horizon) is read against ``excess_kurtosis`` as its
  h=1 anchor; only h>1 points carry their own name.

``cross_block_corr_matrix_distance``: scope is in the name
-------------------------------------------------------------
:data:`~ah.eval.reference.CROSS_BLOCK_STATS` registers ``correlation`` only for
cross-block factor pairs (every factor of block A against every factor of block B, per
active block pair) -- there is no registered *within-block* pairwise correlation
statistic in ``reference.py`` at all (``governance/retrofit-register.md`` RFR-14). The
metric can only be a distance to a matrix the reference actually computes, so it is built
over exactly the factors that appear in at least one cross-block ``correlation`` entry,
with within-block pairs (and any factor with no cross-block partner) masked out rather
than zero-filled-as-if-measured. The unqualified name ``corr_matrix_distance`` overstated
that coverage in every report table and threshold key, so the metric carries the
qualified one; the pure matrix-distance function it calls keeps the general name because
it genuinely is general.

Two consequences of it being a single whole-panel aggregate, both deliberate:

- It is registered in :data:`~ah.eval.reference.PANEL_STATS` and sealed under
  ``pre-registration.yaml``'s ``thresholds.panel`` section, keyed by its bare name -- it
  belongs to no factor and no pair, so neither of the other two key shapes fits it.
- **One degenerate factor NaNs the whole metric.** A factor with zero pooled variance
  makes its own :func:`ah.eval.reference._correlation` entries NaN, and the Frobenius
  norm of a matrix containing NaN is NaN, so a single bad factor takes down the only
  panel-level statistic. That is the correct behaviour under THE ONE NaN RULE (an
  uncomputable metric has not demonstrated compliance) and it is deliberately not
  softened by dropping the offending row: silently shrinking the matrix would change
  *which* pairs the sealed distance is a distance over, run to run.
- **One ABSENT factor NaNs the whole metric too** (WP2.2 Task 2 fix pass 2, Important
  1). The matrix axis is fixed by the reference's covered factor set, never
  re-intersected with whatever the ensemble happens to emit: a generator that simply
  omits a covered factor does not get a smaller, easier-to-satisfy matrix -- it gets
  NaN, the same outcome as a degenerate factor. Without this, the metric could be
  gamed by generating less: a smaller matrix over fewer pairs produces a smaller
  Frobenius distance, so omitting a factor made an absolute-bound threshold easier to
  pass, not harder. See :func:`_paired_corr_matrices`.

Registration is deferred, and now has a caller
-------------------------------------------------
This suite needs a computed :class:`~ah.eval.reference.ReferenceStats` and a
:class:`~ah.factors.FactorManifest` to construct its specs at all
(``cross_block_corr_matrix_distance`` is a distance *to* the historical correlation
matrix), neither of which exists at plain module import. It therefore registers through
:func:`build_monthly_suite` / :func:`register_monthly_suite` rather than as an import side
effect. :func:`ah.eval.battery.run_full_battery` is the production caller that computes
the reference and performs that registration; before this task's fix pass there was none,
so ``battery.SUITES`` was empty in every non-test code path and every battery run
returned a vacuously passing, metric-free report.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.metrics._pooling import mean_over_paths, pooled
from ah.eval.reference import (
    ACF_ABS_MAX_LAG,
    ACF_R_MAX_LAG,
    AGG_GAUSSIANITY_HORIZONS,
    AGG_GAUSSIANITY_MIN_SUMS,
    CrossBlockReference,
    ReferenceStats,
)
from ah.eval.reference import (
    _acf_abs_at_lag as reference_acf_abs_at_lag,
)
from ah.eval.reference import (
    _acf_at_lag as reference_acf_at_lag,
)
from ah.eval.reference import (
    _acf_r_at_lag as reference_acf_r_at_lag,
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
from ah.eval.reference import (
    acf_abs_decay as reference_acf_abs_decay,
)
from ah.eval.reference import (
    corr_matrix_distance as reference_corr_matrix_distance,
)
from ah.eval.reference import (
    fit_exp_decay_rate as reference_fit_exp_decay_rate,
)
from ah.eval.reference import (
    hill_tail_index as reference_hill_tail_index,
)
from ah.eval.reference import (
    leverage_correlation as reference_leverage_correlation,
)
from ah.eval.reference import (
    nonoverlapping_sums as reference_nonoverlapping_sums,
)
from ah.factors import FactorManifest
from ah.gen.base import Ensemble

SUITE = "monthly"
TIER = "monthly"

HILL_TAIL_FRACTIONS: tuple[tuple[float, str], ...] = ((0.05, "5pct"), (0.01, "1pct"))
CORR_MATRIX_DISTANCE_METRIC = "cross_block_corr_matrix_distance"

# Re-exported under this module's own names so a reader of a metric definition below can
# see, without leaving the file, that the estimator is ``reference.py``'s and not a
# second one. These are the SAME function objects, not wrappers.
_acf_at_lag = reference_acf_at_lag
_fit_exp_decay_rate = reference_fit_exp_decay_rate
_leverage_one_path = reference_leverage_correlation
hill_tail_index = reference_hill_tail_index
corr_matrix_distance = reference_corr_matrix_distance

__all__ = [
    "CORR_MATRIX_DISTANCE_METRIC",
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


# Both conventions are defined once, in ``ah.eval.metrics._pooling``, and aliased here
# under this module's historical private names. They used to be a verbatim copy in each
# suite; two suites pooling under one sealed convention must not be able to diverge
# silently (WP2.2 Task 3 fix pass 1, Minor 1).
_pooled = pooled
_mean_over_paths = mean_over_paths


# --------------------------------------------------------------------------- #
# ensemble-level forms of the reference statistics that need a pooling decision
# --------------------------------------------------------------------------- #


def acf_abs_decay(ensemble: Ensemble, factor: str) -> float:
    """``reference.acf_abs_decay`` per path, averaged -- see the module docstring."""
    return _mean_over_paths(reference_acf_abs_decay, ensemble, factor)


def agg_gaussianity(ensemble: Ensemble, factor: str, horizon_months: int) -> float:
    """Excess kurtosis of non-overlapping ``horizon_months``-month sums of ``factor``.

    Sums are computed independently within each path (never spanning a path boundary),
    then **pooled** across paths before the kurtosis is taken -- this is a
    marginal-distribution statistic, like ``excess_kurtosis`` itself, so pooling is the
    same legitimate convention :func:`_pooled` uses elsewhere (and the same convention
    whose length-matching residual the module docstring records).

    Reuses :func:`ah.eval.reference.nonoverlapping_sums` and
    :func:`ah.eval.reference._excess_kurtosis`, and the same
    :data:`~ah.eval.reference.AGG_GAUSSIANITY_MIN_SUMS` floor the reference statistic
    applies, so the ensemble and reference sides cannot drift apart on the minimum
    sample a fourth-moment statistic is allowed to be computed from.
    """
    slab = ensemble.factor(factor).astype(np.float64)
    sums = np.concatenate(
        [reference_nonoverlapping_sums(slab[i], horizon_months) for i in range(slab.shape[0])]
    )
    if sums.size < AGG_GAUSSIANITY_MIN_SUMS:
        return float("nan")
    return reference_excess_kurtosis(sums)


# --------------------------------------------------------------------------- #
# cross-block correlation-matrix distance
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PairedCorrMatrices:
    """Two matrices over one factor axis, plus the mask saying which entries are real.

    ``ensemble`` and ``reference`` are **not** correlation matrices: both carry ``0.0``
    at every off-diagonal entry where ``mask`` is ``False`` (a factor pair the reference
    has no ``correlation`` entry for -- every within-block pair, today). They are built
    to be *differenced*, where a matched pair of zeros is harmless; read either one on
    its own and the masked entries are silently wrong. ``mask`` exists so that reading
    them on their own is not a mistake anybody can make quietly, and ``factors`` gives
    the axis order both matrices and the mask share.
    """

    factors: tuple[str, ...]
    ensemble: np.ndarray
    reference: np.ndarray
    mask: np.ndarray


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


def _paired_corr_matrices(
    ensemble: Ensemble, reference: ReferenceStats, active_factors: tuple[str, ...]
) -> PairedCorrMatrices | None:
    """The ensemble's and the reference's correlations over one shared factor axis.

    The axis is exactly the factors that (a) are declared active and (b) have at least
    one cross-block reference correlation entry -- see the module docstring's
    "cross_block_corr_matrix_distance". Returns ``None`` (metric reports NaN) if fewer
    than 2 such factors exist, **or if any of them is absent from this ensemble**
    (WP2.2 Task 2 fix pass 2, Important 1).

    That last clause is deliberate, not an oversight: the metric's axis is fixed by the
    reference (which factors it has a covered pair for), not by whatever the ensemble
    happens to emit. The previous version intersected the covered axis with
    ``ensemble.factor_names``, so a generator that simply omitted a covered factor got
    a *smaller* matrix and therefore a *smaller* (easier-to-pass) Frobenius distance --
    it is easier to pass an absolute bound by generating less. A degenerate
    (zero-variance) factor already NaNs the whole metric under THE ONE NaN RULE; an
    *absent* factor is a strictly worse case (no data at all, not merely bad data) and
    must NaN it identically, never shrink it.
    """
    ref_pairs = _reference_pairwise_correlations(dict(reference.cross_blocks))
    covered_all = sorted({f for pair in ref_pairs for f in pair} & set(active_factors))
    if any(f not in ensemble.factor_names for f in covered_all):
        return None
    covered = tuple(covered_all)
    m = len(covered)
    if m < 2:
        return None
    ens_matrix = np.eye(m, dtype=np.float64)
    ref_matrix = np.eye(m, dtype=np.float64)
    mask = np.eye(m, dtype=bool)
    pooled = {f: _pooled(ensemble, f) for f in covered}
    for i in range(m):
        for j in range(i + 1, m):
            key = frozenset((covered[i], covered[j]))
            if key not in ref_pairs:
                continue
            mask[i, j] = mask[j, i] = True
            ref_matrix[i, j] = ref_matrix[j, i] = ref_pairs[key]
            ens_matrix[i, j] = ens_matrix[j, i] = reference_correlation(
                pooled[covered[i]], pooled[covered[j]]
            )
    return PairedCorrMatrices(factors=covered, ensemble=ens_matrix, reference=ref_matrix, mask=mask)


def _make_corr_matrix_distance_metric(
    reference: ReferenceStats, active_factors: tuple[str, ...]
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        paired = _paired_corr_matrices(ensemble, reference, active_factors)
        if paired is None:
            return float("nan")
        return corr_matrix_distance(paired.ensemble, paired.reference)

    return fn


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


def _single_factor_specs(factor: str) -> list[MetricSpec]:
    """Every per-factor spec, each named for its ``SINGLE_FACTOR_STATS`` key."""
    specs = [
        _spec(f"{factor}.excess_kurtosis", _pooled_metric(factor, reference_excess_kurtosis)),
        _spec(f"{factor}.skew", _pooled_metric(factor, reference_skew)),
    ]
    for fraction, suffix in HILL_TAIL_FRACTIONS:
        specs.append(
            _spec(
                f"{factor}.hill_tail_index_{suffix}",
                _pooled_metric(factor, lambda x, frac=fraction: reference_hill_tail_index(x, frac)),
            )
        )
    for lag in range(1, ACF_R_MAX_LAG + 1):
        specs.append(
            _spec(
                f"{factor}.acf_r_lag{lag}",
                _per_path_metric(factor, lambda s, k=lag: reference_acf_r_at_lag(s, k)),
            )
        )
    for lag in range(1, ACF_ABS_MAX_LAG + 1):
        specs.append(
            _spec(
                f"{factor}.acf_abs_lag{lag}",
                _per_path_metric(factor, lambda s, k=lag: reference_acf_abs_at_lag(s, k)),
            )
        )
    specs.append(_spec(f"{factor}.acf_abs_decay", _acf_abs_decay_metric(factor)))
    for horizon, suffix in AGG_GAUSSIANITY_HORIZONS:
        specs.append(
            _spec(f"{factor}.agg_gaussianity_{suffix}", _agg_gaussianity_metric(factor, horizon))
        )
    specs.append(
        _spec(f"{factor}.leverage_correlation", _per_path_metric(factor, _leverage_one_path))
    )
    return specs


def build_monthly_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every monthly-tier :class:`~ah.eval.battery.MetricSpec`, for ``manifest``'s
    active factors and cross-block pairs. See the module docstring for naming, pooling
    convention, and why this is a builder rather than an import-time registration."""
    specs: list[MetricSpec] = []
    active = manifest.active_factors()

    for factor in active:
        specs.extend(_single_factor_specs(factor))

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
        _spec(CORR_MATRIX_DISTANCE_METRIC, _make_corr_matrix_distance_metric(reference, active))
    )

    return tuple(specs)


def register_monthly_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("monthly", build_monthly_suite(manifest, reference))``."""
    register_suite(SUITE, build_monthly_suite(manifest, reference))
