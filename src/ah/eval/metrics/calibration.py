"""The calibration tier: rolling-origin PIT and interval coverage (WP2.2 Task 5).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``calibration.py`` bullet: "Rolling-origin
probabilistic calibration on train+validation: PIT histograms and interval coverage at
1y and 5y horizons for factor aggregates. Cheap here; gives Step 5 a baseline." All six
metrics are tier ``"monthly"`` (the DN-1.1 tier a battery run reports them under is
orthogonal to the 1y/5y horizon baked into each metric's own name).

Where the definitions live, and why not here
----------------------------------------------
Exactly as ``ah.eval.metrics.monthly``/``horizon``/``tails``/``utility``: this suite
compares the GENERATED ensemble's own predictive distribution against REAL
train+validation realizations, so -- like ``discriminative_score`` -- there is no
single-argument historical point estimate to bootstrap a band around. The six names
are registered in :data:`~ah.eval.reference.PANEL_STATS` (bare names, no ``fn``,
whole-panel scope -- every metric pools across every shared return-bearing active
factor), which is what lets each one carry a sealed threshold at all: a statistic
defined only here could never satisfy :mod:`ah.eval.prereg`'s threshold-key checker,
and once ``sealed: true`` lands an unregistered name would break every battery run.

The rolling-origin protocol, stated in full (WP2.3 seals a band over this)
-------------------------------------------------------------------------------
For each horizon ``h`` in :data:`CALIBRATION_HORIZONS` (12 months = "1y", 60 months =
"5y") and each **active, return-bearing** factor present in both
:attr:`~ah.eval.reference.ReferenceStats.historical_series` and the judged ensemble
(``conventions.return_bearing_factors`` intersected with ``manifest.active_factors()``
-- levels are excluded because summing a rate or spread over ``h`` months is not a
meaningful aggregate, the identical restriction ``ah.eval.metrics.horizon`` applies to
drawdown/lost-decade):

1. **The predictive distribution** is the GENERATED ensemble's own pooled population of
   non-overlapping ``h``-month sums: :func:`ah.eval.reference.nonoverlapping_sums`
   applied independently WITHIN each path (never spanning a path boundary, exactly
   ``ah.eval.metrics.monthly.agg_gaussianity``'s convention), then concatenated across
   paths. This is deliberately **unconditional** -- the same pooled distribution is used
   at every rolling origin below, not a distribution conditioned on that origin's own
   history -- because nothing in the platform today produces a genuinely
   history-conditioned forecast (that is Step 3's L1 climate-conditioning job); this
   suite is explicitly the CHEAP baseline the plan bullet calls for, not the sealed
   final protocol.
2. **The rolling origins** are every ``h``-month window of the REAL train+validation
   series with **origin spacing of 1 month** (fully overlapping: origin ``t`` covers
   months ``[t, t+h)``, for every ``t`` such that the window fits -- see
   :func:`rolling_origin_sums`). The number of origins for one factor at horizon ``h``
   is therefore ``len(historical_series[factor]) - h + 1``; this is NOT chosen by the
   generator (the real side is fixed by history alone), so it cannot be gamed by
   producing a shorter or longer ensemble.
3. **PIT** for one realized origin sum ``s`` is :func:`_pit_value` of ``s`` against the
   generated pooled distribution's own empirical CDF (mid-rank, ties averaged -- see
   that function). Every origin of every qualifying factor at a given horizon
   contributes one PIT value to one pooled sample (PIT values are already unitless, in
   ``[0, 1]``, so pooling across factors of different raw scales is safe here in a way
   pooling raw sums across factors would not be); ``pit_ks_stat_{1y,5y}`` is
   :func:`ks_statistic_vs_uniform` of that pooled sample. Perfect calibration -> the
   pooled PIT sample is uniform on ``[0, 1]`` -> KS statistic 0; **lower is better**.
4. **Interval coverage** for nominal level ``q`` in ``{50, 90}`` is, per factor, the
   ``[q/2, 100 - q/2]`` percentile interval of that SAME factor's generated pooled
   distribution (``alpha = (1 - q/100) / 2``; ``lo = quantile(alpha)``,
   ``hi = quantile(1 - alpha)``); the pooled coverage indicator (real origin sum inside
   ``[lo, hi]``) is pooled across every qualifying factor and origin, and
   ``interval_coverage_{q}_{1y,5y}`` is the mean of that pooled 0/1 indicator. Perfect
   calibration -> the reported coverage equals the nominal rate ``q/100`` -- **neither
   higher nor lower is "better"**: an over-wide generated distribution reads as
   OVER-coverage, which is exactly as much a calibration failure as under-coverage, so
   a sealed band brackets the nominal rate on both sides rather than treating one
   direction as free.

Two floors, and why (THE ONE NaN RULE / anti-gaming)
---------------------------------------------------------
:data:`CALIBRATION_MIN_GENERATED_SUMS` (30): below this many pooled generated sums for
a factor at a horizon, that factor contributes NOTHING to either metric at that
horizon -- a 5th/95th-percentile cut estimated from a handful of points is not a
measurement. If NO factor clears the floor at a horizon, both metrics at that horizon
are NaN. :data:`CALIBRATION_MIN_ORIGINS` (30): the pooled REAL-side sample (PIT values,
or coverage indicators) must also clear a floor before either metric reports a number,
for the identical reason on the fixed-by-history side. Both floors NaN rather than
report a favourable-looking degenerate number computed from too little -- a generator
that shrinks its own ensemble below :data:`CALIBRATION_MIN_GENERATED_SUMS` fails
outright (NaN fails an enforce threshold under THE ONE NaN RULE) rather than being
rewarded with a lucky small-sample pass.

No scipy, no sklearn: the Kolmogorov-Smirnov statistic and the mid-rank empirical CDF
are both implemented here in closed form, unit-tested in ``tests/test_calibration.py``
against hand-derivable known values (an evenly spaced sample's KS statistic against
Uniform(0,1) has the closed form ``1/(2n)``) and cross-checked against the textbook
sup-norm definition on a fine grid.

Registration is deferred, exactly as every other reference-dependent suite
-------------------------------------------------------------------------------
This suite needs a computed :class:`~ah.eval.reference.ReferenceStats` (for
``historical_series``) and a :class:`~ah.factors.FactorManifest` (for the shared
active-factor axis), so it registers through :func:`build_calibration_suite` /
:func:`register_calibration_suite` rather than as an import-time side effect.
``ah.eval.battery.run_full_battery`` is the production caller, via
``battery._REFERENCE_DEPENDENT_SUITE_BUILDERS``'s ``"calibration"`` row.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.reference import ReferenceStats
from ah.eval.reference import nonoverlapping_sums as reference_nonoverlapping_sums
from ah.factors import FactorManifest
from ah.gen.base import Ensemble
from ah.strategies import load_conventions

SUITE = "calibration"
TIER = "monthly"

# 12 months = "1y", 60 months = "5y" -- the two horizons STEP2-GENERATOR-PLAN Sec.WP2.2
# names explicitly for this suite.
CALIBRATION_HORIZONS: tuple[tuple[int, str], ...] = ((12, "1y"), (60, "5y"))

CALIBRATION_LEVELS: tuple[int, ...] = (50, 90)

# See the module docstring's "Two floors". 30 matches
# ah.eval.reference.AGG_GAUSSIANITY_MIN_SUMS's floor for a distributional-tail-sensitive
# statistic estimated from pooled sums -- a 5th/95th percentile cut computed from fewer
# than ~30 points carries essentially no information about the true tail.
CALIBRATION_MIN_GENERATED_SUMS = 30
CALIBRATION_MIN_ORIGINS = 30

__all__ = [
    "CALIBRATION_HORIZONS",
    "CALIBRATION_LEVELS",
    "CALIBRATION_MIN_GENERATED_SUMS",
    "CALIBRATION_MIN_ORIGINS",
    "SUITE",
    "TIER",
    "build_calibration_suite",
    "ks_statistic_vs_uniform",
    "register_calibration_suite",
    "rolling_origin_sums",
]


# --------------------------------------------------------------------------- #
# closed-form primitives (no scipy) -- see the module docstring
# --------------------------------------------------------------------------- #


def rolling_origin_sums(x: np.ndarray, horizon: int) -> np.ndarray:
    """Every OVERLAPPING ``horizon``-length window sum of ``x``, origin spacing 1.

    Window ``i`` covers ``x[i : i + horizon)``; there are ``len(x) - horizon + 1``
    windows (empty if ``x`` is shorter than ``horizon``). This is the REAL-side
    rolling-origin convention -- deliberately overlapping, unlike
    :func:`ah.eval.reference.nonoverlapping_sums`'s generated-side convention: the two
    sides of this suite are not required to use the same windowing scheme (see the
    module docstring), and overlap here does not manufacture the artifact it would in a
    variance-ratio-style statistic, because a rolling-origin PIT/coverage check treats
    each origin as its own independent forecast evaluation, not as an input to a
    variance estimate.
    """
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = x.shape[0]
    if n < horizon:
        return np.empty(0, dtype=np.float64)
    cumsum = np.concatenate([[0.0], np.cumsum(x)])
    return cumsum[horizon:] - cumsum[:-horizon]


def _pit_value(sorted_sample: np.ndarray, value: float) -> float:
    """Mid-rank empirical CDF of ``value`` against ``sorted_sample`` (already sorted).

    ``(count strictly less than value) + 0.5 * (count exactly equal to value)``, all
    divided by ``n`` -- the standard tie-averaged convention (the same "average ties"
    principle :func:`ah.eval.reference._rank` uses for Spearman correlation), so a
    generated distribution with repeated values (e.g. a near-degenerate generator) does
    not silently bias every tied PIT toward 0 or toward 1.
    """
    n = sorted_sample.shape[0]
    lo = int(np.searchsorted(sorted_sample, value, side="left"))
    hi = int(np.searchsorted(sorted_sample, value, side="right"))
    return (lo + 0.5 * (hi - lo)) / n


def ks_statistic_vs_uniform(x: np.ndarray) -> float:
    """One-sample Kolmogorov-Smirnov statistic of ``x`` against Uniform(0, 1).

    Closed form on the sorted sample ``x_(1) <= ... <= x_(n)``:

        D = max_i max( i/n - x_(i), x_(i) - (i-1)/n )

    the standard textbook two-sided KS statistic specialized to a Uniform(0,1) null
    (``F_0(t) = t``). 0 for a perfectly uniform sample; NaN for an empty input. Verified
    in ``tests/test_calibration.py`` against a hand-derivable closed-form value (an
    evenly spaced sample has ``D = 1/(2n)`` exactly) and cross-checked against the raw
    sup-norm definition on a fine grid.
    """
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = x.shape[0]
    if n == 0:
        return float("nan")
    xs = np.sort(x)
    i = np.arange(1, n + 1, dtype=np.float64)
    d_plus = i / n - xs
    d_minus = xs - (i - 1.0) / n
    return float(np.max(np.maximum(d_plus, d_minus)))


# --------------------------------------------------------------------------- #
# ensemble-level wiring
# --------------------------------------------------------------------------- #


def _shared_return_bearing_factors(
    manifest: FactorManifest,
    reference: ReferenceStats,
    ensemble: Ensemble,
    return_bearing: frozenset[str],
) -> list[str]:
    """Active, return-bearing factors present in both the real historical series and
    this ensemble -- the identical restriction ``ah.eval.metrics.horizon`` applies to
    drawdown/lost-decade (summing a level over a horizon is not a meaningful
    aggregate), applied here to whichever ``manifest`` and ``reference`` are given
    (never re-reading the sealed ``pre-registration.yaml``'s own active factor set)."""
    return [
        f
        for f in manifest.active_factors()
        if f in return_bearing and f in reference.historical_series and f in ensemble.factor_names
    ]


def _generated_pooled_sums(ensemble: Ensemble, factor: str, horizon: int) -> np.ndarray:
    """The generated ensemble's own pooled predictive-distribution sample at ``horizon``
    -- non-overlapping sums computed independently WITHIN each path, then concatenated
    (the identical convention ``ah.eval.metrics.monthly.agg_gaussianity`` uses)."""
    slab = ensemble.factor(factor).astype(np.float64)
    parts = [reference_nonoverlapping_sums(slab[i], horizon) for i in range(slab.shape[0])]
    non_empty = [p for p in parts if p.size > 0]
    return np.concatenate(non_empty) if non_empty else np.empty(0, dtype=np.float64)


def _real_rolling_origin_sums(series: pd.Series, horizon: int) -> np.ndarray:
    return rolling_origin_sums(series.to_numpy(dtype=np.float64), horizon)


def _interval_bounds(sorted_gen: np.ndarray, level: int) -> tuple[float, float]:
    alpha = (1.0 - level / 100.0) / 2.0
    lo = float(np.quantile(sorted_gen, alpha))
    hi = float(np.quantile(sorted_gen, 1.0 - alpha))
    return lo, hi


def _pooled_pit_and_coverage(
    manifest: FactorManifest,
    reference: ReferenceStats,
    ensemble: Ensemble,
    horizon: int,
    return_bearing: frozenset[str],
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Pooled PIT values and pooled per-level coverage indicators, over every
    qualifying factor's rolling origins, at one horizon -- see the module docstring's
    "The rolling-origin protocol"."""
    pit_values: list[float] = []
    coverage_hits: dict[int, list[bool]] = {level: [] for level in CALIBRATION_LEVELS}

    for factor in _shared_return_bearing_factors(manifest, reference, ensemble, return_bearing):
        generated = _generated_pooled_sums(ensemble, factor, horizon)
        if generated.size < CALIBRATION_MIN_GENERATED_SUMS:
            continue
        real = _real_rolling_origin_sums(reference.historical_series[factor], horizon)
        if real.size == 0:
            continue
        sorted_gen = np.sort(generated)
        for value in real:
            pit_values.append(_pit_value(sorted_gen, float(value)))
        for level in CALIBRATION_LEVELS:
            lo, hi = _interval_bounds(sorted_gen, level)
            coverage_hits[level].extend(((real >= lo) & (real <= hi)).tolist())

    return (
        np.array(pit_values, dtype=np.float64),
        {level: np.array(hits, dtype=np.float64) for level, hits in coverage_hits.items()},
    )


def _pit_ks_metric(
    manifest: FactorManifest,
    reference: ReferenceStats,
    horizon: int,
    return_bearing: frozenset[str],
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        pit_values, _ = _pooled_pit_and_coverage(
            manifest, reference, ensemble, horizon, return_bearing
        )
        if pit_values.size < CALIBRATION_MIN_ORIGINS:
            return float("nan")
        return ks_statistic_vs_uniform(pit_values)

    return fn


def _coverage_metric(
    manifest: FactorManifest,
    reference: ReferenceStats,
    horizon: int,
    level: int,
    return_bearing: frozenset[str],
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        _, coverage = _pooled_pit_and_coverage(
            manifest, reference, ensemble, horizon, return_bearing
        )
        hits = coverage[level]
        if hits.size < CALIBRATION_MIN_ORIGINS:
            return float("nan")
        return float(np.mean(hits))

    return fn


def _spec(name: str, fn: MetricFn) -> MetricSpec:
    return MetricSpec(name=name, tier=TIER, fn=fn, suite=SUITE)


def build_calibration_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every ``calibration``-tier :class:`~ah.eval.battery.MetricSpec` -- six names,
    two per horizon (``pit_ks_stat``) plus four (``interval_coverage_{50,90}``). See
    the module docstring for the full rolling-origin protocol."""
    return_bearing = load_conventions().return_bearing_factors
    specs: list[MetricSpec] = []
    for horizon, suffix in CALIBRATION_HORIZONS:
        specs.append(
            _spec(
                f"pit_ks_stat_{suffix}",
                _pit_ks_metric(manifest, reference, horizon, return_bearing),
            )
        )
        for level in CALIBRATION_LEVELS:
            specs.append(
                _spec(
                    f"interval_coverage_{level}_{suffix}",
                    _coverage_metric(manifest, reference, horizon, level, return_bearing),
                )
            )
    return tuple(specs)


def register_calibration_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("calibration", build_calibration_suite(manifest, reference))``."""
    register_suite(SUITE, build_calibration_suite(manifest, reference))
