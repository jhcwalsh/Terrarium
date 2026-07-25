"""Reference statistics and block-bootstrap bands, per block and cross-block (WP2.1b Item 2).

WP2.3's sealed acceptance bands are *derived from this module's output*: it computes
every reference statistic on train+validation only, per :class:`~ah.factors.FactorManifest`
block, and separately for cross-block joint metrics (correlation structure, crisis
co-movement) with the block pair recorded on the result. Getting this shape right now
means WP2.2's eight metric suites register into it rather than restructuring it after
the seal.

The hard invariant this module carries
---------------------------------------
**Reference statistics are computed on train + validation only, forever.** The holdout
is never an input; :func:`ah.splits.DataAccess.train_val` is the only sanctioned
surface this module touches. This module must never import ``ah.eval.g2`` and must
never accept a :class:`~ah.splits.FinalEvaluationToken` -- there is no code path here
by which one could reach the holdout even if a caller tried to hand one in.

Three registries, three statistic scopes
-----------------------------------------
WP2.1b Task 3 laid down the block-aware skeleton -- ``mean``, ``std``, ``skew``,
``excess_kurtosis`` and the lag-1 ACFs, plus the cross-block ``correlation`` and
``crisis_corr_lift`` -- in module-level tables, so later work adds statistics by
registering rather than by editing :func:`compute_reference`. WP2.2 Task 2 is the first
work to use that: it registered the full DN-1.1 Sec.II.6 monthly stylized-fact panel
here (the Hill tail indices, ACF of returns to lag 5 and of ``|deviation|`` to lag 24,
the fitted ACF decay, aggregational Gaussianity, leverage correlation) and added a third
registry for whole-panel statistics.

- :data:`SINGLE_FACTOR_STATS` -- one factor's own series, keyed ``"<factor>.<stat>"``.
- :data:`CROSS_BLOCK_STATS` -- one factor pair's aligned overlap, keyed
  ``"<factorA>~<factorB>.<stat>"``.
- :data:`PANEL_STATS` -- the whole factor panel, keyed by a bare ``"<stat>"``.

**These registries are the platform's statistic vocabulary, not merely this module's.**
:mod:`ah.eval.prereg` validates every ``pre-registration.yaml`` threshold key against
them, and once ``sealed: true`` lands :func:`ah.eval.battery.run_battery` verifies on
every invocation -- so a statistic a metric suite computes but does not register here
can never carry a sealed threshold, and an entry authored under its name would break
every battery run. That is why the estimators for the monthly panel live in this module
and :mod:`ah.eval.metrics.monthly` imports them, rather than the other way round.

STEP2-GENERATOR-PLAN Sec.WP2.2 owns the eight metric suites these registries serve:
``monthly``, ``horizon``, ``tails``, ``utility``, ``memorization``, ``economics``,
``conditional``, ``calibration``
(``src/ah/eval/metrics/{monthly,horizon,tails,utility,memorization,economics,
conditional,calibration}.py``). Only ``monthly`` and ``tails`` exist yet; the rest are
intentionally not stubbed here.

Horizon tiers (DN-1.1 Sec.II.6)
--------------------------------
Every registered statistic carries a horizon tier -- ``monthly``, ``1_5yr``, ``10yr``,
``economic``, or ``severe`` -- because the tier dimension is orthogonal to the block
dimension: WP2.3 seals per-metric severity *and* horizon tier, and WP2.2 adds the
``1_5yr`` / ``10yr`` / ``economic`` / ``severe`` statistics onto the same registries.
Every statistic registered by this task is ``monthly`` tier (the DN-1.1 stylized-fact
panel: tail behavior, ACF, skew, corr matrix, crisis-conditional correlation lift).
DN-1.1 Sec.II.6 states the 1-5yr tier's acceptance criterion as "within block-bootstrap
90% bands of history" -- which is why ``level`` defaults to 0.9 below; the monthly tier
inherits the same band mechanics here, ahead of WP2.2 stating its own criterion.
``SINGLE_FACTOR_STATS`` and ``CROSS_BLOCK_STATS`` both carry ``tier`` on a registration
record (:class:`RegisteredStat` / :class:`RegisteredCrossStat`) -- symmetric, so neither
table hardcodes tier as an inline literal at the call site.

Data alignment is scoped to what each statistic actually needs
-----------------------------------------------------------------
:func:`compute_reference` reads every active factor once, independently, via
``access.train_val(series_id_for(factor))``. It does **not** inner-join every active
factor onto one shared date axis before computing anything -- with real Step-1 series
that is not a hypothetical problem: spread and volatility indices start decades after
the equity series they share a block with, and rates/inflation series in one block
commonly cover a different span than another block's series entirely. A single
short-history factor must not silently truncate the reference window used for a
*different* factor's own statistics.

Alignment is therefore scoped per statistic:

- A **single-factor** statistic (every entry in :data:`SINGLE_FACTOR_STATS`) is
  computed over that one factor's own train+validation observations only -- no join
  with any other factor, in its own block or any other. ``equity_mkt``'s mean is not
  truncated by ``hy_spread`` starting fifty years later, even though both are in the
  ``global`` block.
- A **cross-block** statistic (every entry in :data:`CROSS_BLOCK_STATS`) is computed
  over exactly its own factor pair's aligned (inner-joined) overlap -- not the two
  blocks' full factor sets, and not every other active block. If a pair's date ranges
  do not overlap at all, that is not an error: the pair is recorded in
  ``CrossBlockReference.zero_overlap_pairs`` and contributes no stat entries, rather
  than raising an unhandled ``ValueError`` out of :func:`block_bootstrap_band`.

Nothing registered by this task is a genuinely joint (multi-factor) *within-block*
statistic, so no such alignment is implemented here; if WP2.2 registers one, it should
align only that statistic's own block-scoped factors, not reintroduce a single
all-active-factors join.

Where the data comes from
---------------------------
The factor-id -> catalog-series-id mapping is ``factors.yaml``'s ``factor_sources``
section (WP2.2 Task 1), read through :func:`ah.eval.panel.read_factor_frames` -- the
single resolution surface this module and :func:`ah.eval.panel.build_panel` share, so
the statistics WP2.3 seals bands over and the panel a generator is fitted against can
never resolve a factor differently. ``compute_reference`` therefore takes the manifest
itself (it always did) and a ``split_reader`` hook defaulting to
:meth:`ah.splits.DataAccess.train_val`; it no longer takes a bare ``series_id_for``
callable. That callable defaulted to *identity*, and nothing in production ever passed
it anything else, so every factor id was handed to the catalog verbatim, every factor
landed in ``missing_factors``, and the reference came back empty with no error --
closed here, with ``tests/test_reference.py``'s
``test_compute_reference_resolves_real_manifest_series_ids`` as the guard.

Missing factors: two kinds, never conflated
---------------------------------------------
A factor with no data is *not* an error and does not silently produce ``NaN``: it is
skipped and recorded. ``missing_declared`` names factors the manifest itself declares
``kind: unavailable`` (``commodities`` -- expected, governed by a retrofit-register
row); ``missing_no_data`` names factors that declare a real source but whose series
had no train+validation rows (unknown series id, or a known one with zero rows). The
second is the dangerous one and is reported separately -- see
:mod:`ah.eval.panel`'s module docstring. ``missing_factors`` is their union, kept for
callers that only need "which factors are absent".

A frame that *is* returned but is malformed (missing the ``date``/``value`` columns
this module assumes) is a different failure mode -- a bug, not a data gap -- and raises
a named :class:`ReferenceComputationError` identifying the offending factor and its
source rather than propagating an anonymous ``KeyError`` from deep inside pandas.

Per-factor coverage is recorded, not assumed
----------------------------------------------
``min_start`` across the mapped series runs from 1913 (CPI) to 1996 (HY OAS): a sealed
``equity_vol`` band rests on ~30 years of history and a sealed ``equity_mkt`` band on
~95. :class:`ReferenceStats` therefore records, per factor, the first and last
train+validation observation date and the observation count
(:class:`FactorCoverage`), and the battery report prints it. "What is the band a band
*of*" is the whole point of the mapping this module now reads.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd

from ah.eval.panel import FactorFrames, PanelError, SplitReader, default_split_reader
from ah.eval.panel import read_factor_frames as _read_factor_frames
from ah.factors import FactorManifest
from ah.splits import DataAccess

# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #


class ReferenceComputationError(RuntimeError):
    """Reference-statistic computation failed in a way that must name its cause.

    Raised (never a bare ``KeyError``/``ValueError``) whenever a reader failure can't
    be attributed to a legitimate data gap (see the module docstring's ``commodities``
    note) -- the message always names the offending factor, series id, and/or
    block/pair so the failure is diagnosable without a debugger.
    """


# --------------------------------------------------------------------------- #
# public result types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StatBand:
    """A point estimate plus its block-bootstrap confidence band.

    ``point`` is the statistic evaluated on the full (un-resampled) sample.
    ``lo``/``hi`` is the ``level``-central percentile interval over ``n_resamples``
    moving-block bootstrap resamples (see :func:`block_bootstrap_band`). ``tier`` is
    the DN-1.1 Sec.II.6 horizon tier this statistic belongs to (``monthly``, ``1_5yr``,
    ``10yr``, ``economic``, ``severe``).

    ``resample_length`` is how many rows each bootstrap replicate carried. ``None``
    means "the full sample length" (the historical default). When it is set -- which
    is how :func:`ah.eval.battery.run_full_battery` computes every reference, at the
    judged ensemble's own path length -- **``point`` is not expected to lie inside
    ``[lo, hi]``**, and that is not a defect: they answer different questions. ``point``
    is the statistic on all of history; ``lo``/``hi`` is the interval a *replicate of
    the generated path's length* produces. Every per-path statistic registered here
    uses the n-denominator Box-Jenkins ACF estimator, whose finite-sample bias is a
    function of series length, so a generated 120-month path and a 1100-month history
    are simply not measuring the same thing under one estimator. Length-matching the
    replicates is what makes the band a fair criterion; see :func:`block_bootstrap_band`
    and ``pre-registration.yaml``'s ``conventions.estimator_length_matching``.
    """

    point: float
    lo: float
    hi: float
    n_resamples: int
    level: float
    tier: str
    resample_length: int | None = None


@dataclass(frozen=True)
class BlockReference:
    """Reference statistics for one factor block.

    ``stats`` is keyed ``"<factor>.<stat_name>"``, e.g. ``"equity_mkt.mean"``. Each
    factor's stats are computed over that factor's own observations only -- see the
    module docstring's "Data alignment" section.
    """

    block: str
    stats: Mapping[str, StatBand]


@dataclass(frozen=True)
class CrossBlockReference:
    """Reference statistics for one active cross-block pair.

    ``pair`` (sorted, e.g. ``("global", "us")``) is recorded on the object itself --
    an explicit requirement of the WP2.1b patch, so a threshold consumer never has to
    reconstruct which pair a stat belongs to from context. ``stats`` is keyed
    ``"<factorA>~<factorB>.<stat_name>"`` for every factor pair drawn from the two
    blocks (Cartesian product of each block's present factors), e.g.
    ``"equity_mkt~ust_10y.correlation"``, computed over exactly that pair's aligned
    overlap (never a wider join). ``zero_overlap_pairs`` names every ``"<factorA>~
    <factorB>"`` pair whose train+validation date ranges do not overlap at all -- a
    named outcome, not the ``ValueError`` that would otherwise come out of
    :func:`block_bootstrap_band` for an empty panel.
    """

    pair: tuple[str, str]
    stats: Mapping[str, StatBand]
    zero_overlap_pairs: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactorCoverage:
    """What one factor's train+validation sample actually was.

    ``first_date``/``last_date`` are ISO ``YYYY-MM-DD`` strings (JSON-friendly and
    stable across pandas versions); ``n_obs`` is the observation count the statistics
    for that factor were computed over. Recorded because per-factor effective sample
    varies roughly fourfold across the mapped series and a sealed band that does not
    say how much history it rests on is not auditable.
    """

    first_date: str
    last_date: str
    n_obs: int


@dataclass(frozen=True)
class ReferenceStats:
    """The complete train+validation reference: every block, plus every cross-block pair.

    ``missing_factors`` lists every active factor for which no data was available; they
    contribute no entries to ``blocks`` or ``cross_blocks``. ``missing_declared`` and
    ``missing_no_data`` split that list into its two very different halves -- see the
    module docstring's "Missing factors: two kinds". ``coverage`` records, per factor
    that *did* produce statistics, the span and observation count those statistics rest
    on.
    """

    blocks: Mapping[str, BlockReference]
    cross_blocks: Mapping[tuple[str, str], CrossBlockReference]
    active_blocks: tuple[str, ...]
    vintage_id: str
    n_resamples: int
    seed: int
    missing_factors: tuple[str, ...]
    missing_declared: tuple[str, ...] = ()
    missing_no_data: tuple[str, ...] = ()
    coverage: Mapping[str, FactorCoverage] = MappingProxyType({})

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable rendering (for the battery report and Task 4's threshold authoring).

        Cross-block pair keys render as ``"block_a|block_b"`` (tuples cannot be JSON
        object keys); everything else maps through directly. ``zero_overlap_pairs`` is
        included only for pairs that actually have one (keeping the common-case JSON
        uncluttered).
        """

        def _stats_dict(
            stats: Mapping[str, StatBand],
        ) -> dict[str, dict[str, float | int | str | None]]:
            return {
                name: {
                    "point": band.point,
                    "lo": band.lo,
                    "hi": band.hi,
                    "n_resamples": band.n_resamples,
                    "level": band.level,
                    "tier": band.tier,
                    "resample_length": band.resample_length,
                }
                for name, band in stats.items()
            }

        zero_overlap = {
            "|".join(pair): list(ref.zero_overlap_pairs)
            for pair, ref in self.cross_blocks.items()
            if ref.zero_overlap_pairs
        }

        return {
            "vintage_id": self.vintage_id,
            "seed": self.seed,
            "n_resamples": self.n_resamples,
            "active_blocks": list(self.active_blocks),
            "missing_factors": list(self.missing_factors),
            "missing_declared": list(self.missing_declared),
            "missing_no_data": list(self.missing_no_data),
            "coverage": {
                factor: {
                    "first_date": cov.first_date,
                    "last_date": cov.last_date,
                    "n_obs": cov.n_obs,
                }
                for factor, cov in self.coverage.items()
            },
            "blocks": {block: _stats_dict(ref.stats) for block, ref in self.blocks.items()},
            "cross_blocks": {
                "|".join(pair): _stats_dict(ref.stats) for pair, ref in self.cross_blocks.items()
            },
            "zero_overlap_pairs": zero_overlap,
        }


# --------------------------------------------------------------------------- #
# single-factor statistics (registered; WP2.2 extends by registering, not editing
# compute_reference)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegisteredStat:
    """A single-factor statistic function paired with its DN-1.1 Sec.II.6 horizon tier."""

    fn: Callable[[np.ndarray], float]
    tier: str


def _mean(x: np.ndarray) -> float:
    return float(np.mean(x))


def _std(x: np.ndarray) -> float:
    """Sample standard deviation (``ddof=1``, the unbiased estimator)."""
    x = np.asarray(x, dtype=np.float64)
    if x.shape[0] < 2:
        return float("nan")
    return float(np.std(x, ddof=1))


def _central_moment(x: np.ndarray, order: int) -> float:
    xbar = np.mean(x)
    return float(np.mean((x - xbar) ** order))


def _skew(x: np.ndarray) -> float:
    """Fisher-Pearson moment coefficient of skewness: ``m3 / m2**1.5`` (population moments)."""
    x = np.asarray(x, dtype=np.float64)
    m2 = _central_moment(x, 2)
    m3 = _central_moment(x, 3)
    if m2 == 0.0:
        return float("nan")
    return m3 / m2**1.5


def _excess_kurtosis(x: np.ndarray) -> float:
    """Excess kurtosis: ``m4 / m2**2 - 3`` (population moments; 0 for a normal distribution)."""
    x = np.asarray(x, dtype=np.float64)
    m2 = _central_moment(x, 2)
    m4 = _central_moment(x, 4)
    if m2 == 0.0:
        return float("nan")
    return m4 / m2**2 - 3.0


def _acf1(x: np.ndarray) -> float:
    """Lag-1 sample autocorrelation ``gamma_1 / gamma_0``.

    Both ``gamma_0`` (variance) and ``gamma_1`` (lag-1 autocovariance) use the
    overall sample mean and an ``n``-denominator (the standard Box-Jenkins sample-ACF
    estimator), not ``numpy.corrcoef``'s pairwise-mean, ``n-1``-denominator estimator
    -- the two agree asymptotically but not at finite ``n``, and this module fixes one
    convention so the same series always gives the same number.
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    if n < 2:
        return float("nan")
    dev = x - np.mean(x)
    gamma0 = float(np.sum(dev**2) / n)
    gamma1 = float(np.sum(dev[:-1] * dev[1:]) / n)
    if gamma0 == 0.0:
        return float("nan")
    return gamma1 / gamma0


def _acf_at_lag(x: np.ndarray, lag: int) -> float:
    """``gamma_lag / gamma_0`` at an arbitrary positive lag -- :func:`_acf1` generalized.

    Identical convention (overall mean, n-denominator), so ``_acf_at_lag(x, 1)`` is
    ``_acf1(x)`` bit for bit. NaN for ``lag < 1``, for a series no longer than ``lag``,
    and for a degenerate (zero-variance) series.
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


def _abs_deviation(x: np.ndarray) -> np.ndarray:
    """``|x - mean(x)|`` -- the one volatility proxy this module uses, defined once."""
    x = np.asarray(x, dtype=np.float64)
    return np.abs(x - np.mean(x))


def _acf_r_at_lag(x: np.ndarray, lag: int) -> float:
    """ACF of the raw series at ``lag`` (registered as ``acf_r_lag{lag}``)."""
    return _acf_at_lag(x, lag)


def _acf_abs_at_lag(x: np.ndarray, lag: int) -> float:
    """ACF of ``|x - mean(x)|`` at ``lag`` (registered as ``acf_abs_lag{lag}``)."""
    return _acf_at_lag(_abs_deviation(x), lag)


def _acf_1(x: np.ndarray) -> float:
    return _acf1(x)


def _acf_abs_1(x: np.ndarray) -> float:
    """Lag-1 autocorrelation of ``|x - mean(x)|`` -- the volatility-clustering statistic."""
    return _acf_abs_at_lag(x, 1)


# --------------------------------------------------------------------------- #
# WP2.2 Task 2: the monthly stylized-fact statistics
#
# These live here, not in ``ah.eval.metrics.monthly``, for one structural reason:
# :mod:`ah.eval.prereg` validates a threshold key's ``<stat>`` against
# :data:`SINGLE_FACTOR_STATS` / :data:`CROSS_BLOCK_STATS` / :data:`PANEL_STATS`, and
# once ``sealed: true`` lands :func:`ah.eval.battery.run_battery` calls
# :func:`ah.eval.prereg.verify` unconditionally. A statistic defined only in a metric
# suite therefore cannot carry a sealed threshold at all, and an entry authored under
# its name would break every battery run rather than only the seal. Defining them here
# also gives each one a computed train+validation band for free. The metric suite
# imports these definitions; it never restates one (``metrics/monthly.py`` supplies
# only the ensemble-level pooling conventions on top).
# --------------------------------------------------------------------------- #


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
    loss -- an all-positive-return sample has no left tail at all), or the fitted mean
    log-ratio is ``<= 0``. **A level factor (a rate, a spread, an index) is normally
    all-positive and so reports NaN here by construction**: the Hill tail index of a
    level is not a meaningful quantity, and NaN is the honest answer rather than a
    number computed from the wrong side of a series that has no losses.
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


# Search domain for the exponential-decay rate (see fit_exp_decay_rate). Sealed values:
# the estimator is not reconstructible from the pre-registration without them.
_DECAY_RATE_MIN = -1.0
_DECAY_RATE_MAX = 5.0
_DECAY_GRID_POINTS = 241
_DECAY_GOLDEN_TOL = 1e-10
_DECAY_MAX_ITERATIONS = 200
_GOLDEN_RATIO = 0.6180339887498949  # (sqrt(5) - 1) / 2


def fit_exp_decay_rate(lags: np.ndarray, values: np.ndarray) -> float:
    """Least-squares exponential-decay rate for ``(lag, value)`` pairs, fitted in LEVELS.

    Fitted form, stated fully because WP2.3 seals a band on it: ``value ~= A *
    exp(-rate * lag)``, fitted by ordinary least squares **on the values themselves**,
    minimizing ``sum_k ( value_k - A * exp(-rate * lag_k) )**2``. For any fixed
    ``rate`` the optimal amplitude has the closed form ``A*(rate) = sum_k value_k *
    e_k / sum_k e_k**2`` with ``e_k = exp(-rate * lag_k)``, so the problem reduces to a
    one-dimensional minimization over ``rate``. That minimization is deterministic and
    dependency-free: evaluate the profiled sum of squares on
    ``_DECAY_GRID_POINTS`` (241) equally spaced points across
    ``[_DECAY_RATE_MIN, _DECAY_RATE_MAX]`` (-1.0 to 5.0), then golden-section search
    within the bracketing interval either side of the grid minimum until the interval
    is narrower than ``_DECAY_GOLDEN_TOL`` (1e-10) or ``_DECAY_MAX_ITERATIONS`` (200)
    iterations have run. No RNG, no optimizer dependency, no scipy.

    **Why levels rather than log space** (WP2.2 Task 2 fix pass, Important 1). The
    previous version regressed ``ln(value)`` on ``lag`` over the pairs with
    ``value > 0``, dropping the rest. Dropping only the non-positive values is a
    one-sided selection: at lags where the true autocorrelation is ~0, only upward
    noise survives the filter, which lifts the fitted tail and biases ``rate``
    downward -- and the bias is worst exactly where a volatility-clustering curve is
    most informative (the long lags). Clamping instead of dropping trades one bias for
    another. Fitting in levels consumes **every** lag, whatever its sign, so no
    selection happens at all and the estimator is defined for every input.

    **Residual bias, stated rather than left to be discovered.** A levels fit weights
    absolute residuals equally, so the large low-lag values dominate: ``rate`` is a
    summary of the curve's early decay more than of its tail. That is a property of
    the *exponential form*, not of the loss function -- see this module's note on why
    the exponential form is used at all, and note that every individual
    ``acf_abs_lag{k}`` is separately registered, so the long-memory information the
    exponential summary compresses away is still judged lag by lag.

    Sign convention: a genuinely *decaying* curve gives ``rate > 0``; a curve that
    grows with lag gives ``rate < 0`` rather than being silently floored at zero.

    NaN if fewer than 2 pairs are given, if any value is non-finite (an uncomputable
    ACF must not be silently fitted around), or if every value is exactly zero (the
    residual is then flat in ``rate`` and no minimum is identified).
    """
    lags = np.asarray(lags, dtype=np.float64).reshape(-1)
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if lags.shape != values.shape:
        raise ValueError(
            f"fit_exp_decay_rate: lags {lags.shape} and values {values.shape} must match"
        )
    if (
        lags.size < 2
        or not bool(np.all(np.isfinite(values)))
        or not bool(np.all(np.isfinite(lags)))
    ):
        return float("nan")
    if not bool(np.any(values != 0.0)):
        return float("nan")

    def sse(rate: float) -> float:
        e = np.exp(-rate * lags)
        denom = float(np.sum(e * e))
        if denom == 0.0 or not np.isfinite(denom):
            return float("inf")
        amplitude = float(np.sum(values * e) / denom)
        return float(np.sum((values - amplitude * e) ** 2))

    grid = np.linspace(_DECAY_RATE_MIN, _DECAY_RATE_MAX, _DECAY_GRID_POINTS)
    grid_sse = np.array([sse(float(r)) for r in grid], dtype=np.float64)
    best = int(np.argmin(grid_sse))
    lo = float(grid[max(best - 1, 0)])
    hi = float(grid[min(best + 1, _DECAY_GRID_POINTS - 1)])

    c = hi - _GOLDEN_RATIO * (hi - lo)
    d = lo + _GOLDEN_RATIO * (hi - lo)
    f_c, f_d = sse(c), sse(d)
    for _ in range(_DECAY_MAX_ITERATIONS):
        if hi - lo < _DECAY_GOLDEN_TOL:
            break
        if f_c < f_d:
            hi, d, f_d = d, c, f_c
            c = hi - _GOLDEN_RATIO * (hi - lo)
            f_c = sse(c)
        else:
            lo, c, f_c = c, d, f_d
            d = lo + _GOLDEN_RATIO * (hi - lo)
            f_d = sse(d)
    return (lo + hi) / 2.0


ACF_ABS_DECAY_MAX_LAG = 24


def acf_abs_decay(x: np.ndarray, max_lag: int = ACF_ABS_DECAY_MAX_LAG) -> float:
    """Fitted exponential-decay rate of ``x``'s ACF(|deviation|) over lags 1..``max_lag``.

    Computes :func:`_acf_abs_at_lag` for every lag in ``1..max_lag`` -- exactly the
    ``acf_abs_lag{k}`` statistics, so the curve fitted here is the curve reported
    lag by lag -- and fits :func:`fit_exp_decay_rate` to it.

    **Why an exponential form for a canonically hyperbolic stylized fact** (WP2.2
    Task 2 fix pass, Important 2). The volatility-clustering fact this summarizes is
    conventionally described as a slow, power-law decay of ACF(|r|) (Cont 2001), not
    an exponential one, and an exponential fitted to a hyperbolic curve gives a rate
    dominated by the low lags. The exponential is used anyway, deliberately, on three
    grounds, all of which depend on it being read as a *comparative summary* and not
    as a claim about the true functional form:

    1. The quantity is only ever compared against itself: the generated ensemble's
       rate against the same estimator applied to reference replicates of the same
       length over the same fixed lag window ``1..max_lag``. Under a fixed window and
       a fixed estimator the rate is a monotone summary of how fast the curve falls,
       which is what the criterion needs.
    2. A log-log (power-law) fit is not a neutral alternative: it is equally
       misspecified if the truth is closer to exponential, and its log-spaced abscissa
       weights the first four lags *more* heavily still.
    3. The long-memory information an exponential summary compresses away is not lost:
       every ``acf_abs_lag{k}`` for ``k`` in ``1..24`` is separately registered and
       separately banded, so "slow decay" versus "fast decay with high short-memory
       persistence" is discriminated by the lag-24 band, not by this number.

    A rate is comparable only against another rate fitted over the same lag window
    with the same estimator; it is not comparable across different ``max_lag`` values.
    """
    lags = np.arange(1, max_lag + 1, dtype=np.float64)
    dev = _abs_deviation(x)
    values = np.array([_acf_at_lag(dev, int(lag)) for lag in lags], dtype=np.float64)
    return fit_exp_decay_rate(lags, values)


# A fourth-standardized-moment statistic on a handful of points is noise, not a
# measurement: the sample excess kurtosis of n iid normal draws has standard error
# ~sqrt(24/n), which is 0.9 at n = 30 and 2.4 at n = 4. 30 is the floor below which
# the number carries no information about the effect it exists to detect (the decay of
# excess kurtosis toward 0 with aggregation horizon), so below it the statistic is NaN
# rather than a number that would be sealed as if it meant something.
AGG_GAUSSIANITY_MIN_SUMS = 30


def nonoverlapping_sums(x: np.ndarray, horizon_months: int) -> np.ndarray:
    """Non-overlapping ``horizon_months``-month sums of a 1-D series (partial tail dropped)."""
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = x.shape[0]
    usable = (n // horizon_months) * horizon_months
    if usable == 0:
        return np.empty(0, dtype=np.float64)
    return x[:usable].reshape(-1, horizon_months).sum(axis=1)


def agg_gaussianity(x: np.ndarray, horizon_months: int) -> float:
    """Excess kurtosis of non-overlapping ``horizon_months``-month sums of ``x``.

    The stylized fact: excess kurtosis decays toward 0 as ``horizon_months`` grows
    (aggregational Gaussianity -- a slow approach to the CLT limit for a fat-tailed
    monthly return). Reuses :func:`_excess_kurtosis`, not a second definition. NaN if
    fewer than :data:`AGG_GAUSSIANITY_MIN_SUMS` sums are available.

    ``horizon_months=1`` is the identity aggregation and is *exactly*
    ``excess_kurtosis``; it is therefore deliberately **not** registered under a second
    name (WP2.2 Task 2 fix pass, Important 4 -- two registered names for one number is
    two sealed bands on one quantity).
    """
    if horizon_months < 1:
        raise ValueError(f"agg_gaussianity: horizon_months must be >= 1, got {horizon_months}")
    sums = nonoverlapping_sums(x, horizon_months)
    if sums.size < AGG_GAUSSIANITY_MIN_SUMS:
        return float("nan")
    return _excess_kurtosis(sums)


def leverage_correlation(x: np.ndarray) -> float:
    """``corr(r_t, |r_{t+1} - mean(r)|)`` -- the leverage effect, at lag 1 month.

    This month's return against next month's realized-volatility proxy. The proxy is
    ``|r_{t+1} - mean(r)|``, the absolute deviation from the series' own mean -- the
    same ``|x - mean(x)|`` convention :func:`_acf_abs_1` already uses for volatility
    clustering, so the proxy is not a third, independently invented one. A negative
    result is the classical leverage effect (a down month is followed by higher
    realized volatility). NaN if the series has fewer than 3 observations (fewer than
    2 paired ``(r_t, vol_{t+1})`` observations to correlate).
    """
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    if x.shape[0] < 3:
        return float("nan")
    mean_x = float(np.mean(x))
    return _correlation(x[:-1], np.abs(x[1:] - mean_x))


def corr_matrix_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distance between two same-shaped correlation matrices: the **Frobenius norm** of
    their difference, ``sqrt(sum((a - b)**2))``.

    Chosen over the (also standard) Herdin et al. correlation-matrix-distance
    similarity measure (``1 - trace(a @ b) / (norm(a, 'fro') * norm(b, 'fro'))``,
    scale/rotation-normalized) because the raw Frobenius difference is the simpler,
    more literal reading of "how far apart are these two matrices" for two correlation
    matrices already on the same bounded ``[-1, 1]`` scale by construction -- no
    normalization is needed to make them comparable. ``0`` for two identical matrices;
    strictly positive and monotonically larger the more their entries differ.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"corr_matrix_distance: shape mismatch {a.shape} vs {b.shape}")
    return float(np.linalg.norm(a - b, ord="fro"))


def _lagged_stat(fn: Callable[[np.ndarray, int], float], lag: int) -> Callable[[np.ndarray], float]:
    """Bind ``lag`` into a two-argument estimator for registration."""

    def stat(x: np.ndarray) -> float:
        return fn(x, lag)

    return stat


def _tail_fraction_stat(fraction: float) -> Callable[[np.ndarray], float]:
    def stat(x: np.ndarray) -> float:
        return hill_tail_index(x, fraction)

    return stat


def _horizon_stat(horizon_months: int) -> Callable[[np.ndarray], float]:
    def stat(x: np.ndarray) -> float:
        return agg_gaussianity(x, horizon_months)

    return stat


ACF_R_MAX_LAG = 5
ACF_ABS_MAX_LAG = 24
AGG_GAUSSIANITY_HORIZONS: tuple[tuple[int, str], ...] = ((3, "3m"), (12, "12m"))

# The longest lag any registered statistic reads (acf_abs_lag24, and acf_abs_decay's
# own 24-lag fit window).
MAX_REGISTERED_LAG = ACF_ABS_MAX_LAG

# A moving-block bootstrap preserves a lag-k relationship only for the pairs that fall
# inside one block: with blocks of length b it keeps a fraction (b - k) / b of them, so
# a resampled lag-k autocorrelation is shrunk toward zero by roughly that factor. At the
# previous default (24) and a judged window running out to lag 24, the band for every
# long-lag ACF statistic was therefore an artifact of the block length rather than a
# statement about history -- exactly the class of error a sealed band must not encode.
# The default is now several multiples of MAX_REGISTERED_LAG (120 months = 10 years),
# which keeps the shrinkage at lag 24 to ~20% while still cutting a ~1100-month history
# into ~9 blocks, enough for a usable percentile band. Both constraints bind: raising it
# further (240+) leaves too few blocks and the band degenerates.
# `tests/test_reference.py::test_default_block_length_exceeds_the_longest_registered_lag`
# is the machine-checked half of this paragraph.
DEFAULT_BLOCK_LENGTH = 120

SINGLE_FACTOR_STATS: dict[str, RegisteredStat] = {
    "mean": RegisteredStat(fn=_mean, tier="monthly"),
    "std": RegisteredStat(fn=_std, tier="monthly"),
    "skew": RegisteredStat(fn=_skew, tier="monthly"),
    "excess_kurtosis": RegisteredStat(fn=_excess_kurtosis, tier="monthly"),
    # WP2.2 Task 2 fix pass: `acf_1` / `acf_abs_1` were renamed into the lag-indexed
    # scheme rather than kept alongside `acf_r_lag1` / `acf_abs_lag1`. Registering both
    # would have put two names -- and so two sealed bands and two thresholds -- on one
    # number. Renaming a registry key is free while `sealed: false`; after WP2.3 it is
    # a dated amendment, which is exactly why it happens now.
    **{
        f"acf_r_lag{lag}": RegisteredStat(fn=_lagged_stat(_acf_r_at_lag, lag), tier="monthly")
        for lag in range(1, ACF_R_MAX_LAG + 1)
    },
    **{
        f"acf_abs_lag{lag}": RegisteredStat(fn=_lagged_stat(_acf_abs_at_lag, lag), tier="monthly")
        for lag in range(1, ACF_ABS_MAX_LAG + 1)
    },
    "acf_abs_decay": RegisteredStat(fn=acf_abs_decay, tier="monthly"),
    "hill_tail_index_5pct": RegisteredStat(fn=_tail_fraction_stat(0.05), tier="monthly"),
    "hill_tail_index_1pct": RegisteredStat(fn=_tail_fraction_stat(0.01), tier="monthly"),
    **{
        f"agg_gaussianity_{suffix}": RegisteredStat(fn=_horizon_stat(h), tier="monthly")
        for h, suffix in AGG_GAUSSIANITY_HORIZONS
    },
    "leverage_correlation": RegisteredStat(fn=leverage_correlation, tier="monthly"),
}


# --------------------------------------------------------------------------- #
# cross-block joint statistics
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegisteredCrossStat:
    """A cross-block statistic function paired with its DN-1.1 Sec.II.6 horizon tier.

    Symmetric with :class:`RegisteredStat`: tier is carried on the registration record,
    not hardcoded inline where the stat is invoked.
    """

    fn: Callable[[np.ndarray, np.ndarray], float]
    tier: str


def _correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation between two aligned 1-D arrays."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape[0] < 2 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _crisis_corr_lift(a: np.ndarray, b: np.ndarray) -> float:
    """Crisis co-movement: correlation on A's worst decile, minus the unconditional correlation.

    Precise definition (so this is reconstructible from the pre-registration alone):
    let ``threshold`` be the 10th percentile of ``a`` (the block-A factor) over the
    aligned sample, and the "crisis" subset be every co-dated observation with
    ``a <= threshold`` (``a``'s worst decile by value -- for a return-bearing factor
    this is its worst-loss months). ``crisis_corr_lift = corr(a[crisis], b[crisis]) -
    corr(a, b)``. A positive lift means A and B co-move more strongly in A's worst
    months than on average -- the crisis-co-movement failure mode this statistic is
    built to catch. ``NaN`` if the crisis subset has fewer than 2 observations or is
    degenerate (zero variance in either leg, so the conditional correlation is itself
    undefined).
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    unconditional = _correlation(a, b)
    threshold = np.percentile(a, 10)
    mask = a <= threshold
    if mask.sum() < 2:
        return float("nan")
    conditional = _correlation(a[mask], b[mask])
    if np.isnan(conditional) or np.isnan(unconditional):
        return float("nan")
    return conditional - unconditional


CROSS_BLOCK_STATS: dict[str, RegisteredCrossStat] = {
    "correlation": RegisteredCrossStat(fn=_correlation, tier="monthly"),
    "crisis_corr_lift": RegisteredCrossStat(fn=_crisis_corr_lift, tier="monthly"),
}


# --------------------------------------------------------------------------- #
# whole-panel statistics
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegisteredPanelStat:
    """A whole-panel statistic: a name and a DN-1.1 Sec.II.6 horizon tier, no function.

    Third registry, third scope. :data:`SINGLE_FACTOR_STATS` is keyed
    ``"<factor>.<stat>"`` and :data:`CROSS_BLOCK_STATS` ``"<factorA>~<factorB>.<stat>"``;
    a panel statistic is keyed by its **bare name**, because it is a property of the
    whole factor panel and belongs to no single factor or pair. ``pre-registration.yaml``
    carries it under ``thresholds.panel``, and :func:`ah.eval.prereg.verify` validates
    the key against this registry the same way it validates the other two.

    **Why no ``fn``.** The one entry today, ``cross_block_corr_matrix_distance``, is a
    *distance between a generated ensemble and the reference itself*, so its value on
    history is identically zero and there is no historical point estimate or bootstrap
    band to compute: the sealed threshold is an absolute bound on that distance,
    judged directly by :func:`ah.eval.battery._passed`. Registering it here is what
    makes it sealable at all -- a metric name no registry knows cannot carry a
    threshold, and once ``sealed: true`` lands an entry under such a name breaks every
    battery run. A future panel statistic that *is* computable on the historical panel
    would need an aligned multi-factor panel, which :func:`compute_reference`
    deliberately does not build (see the module docstring's "Data alignment"); that is
    a change to make explicitly, not by adding an ``fn`` field on a whim.
    """

    tier: str


PANEL_STATS: dict[str, RegisteredPanelStat] = {
    "cross_block_corr_matrix_distance": RegisteredPanelStat(tier="monthly"),
}


# --------------------------------------------------------------------------- #
# moving-block bootstrap
# --------------------------------------------------------------------------- #


def _ctx(context: str) -> str:
    return f" [{context}]" if context else ""


def _draw_moving_block_indices(
    t: int,
    *,
    seed: int,
    n_resamples: int,
    block_length: int,
    context: str = "",
    resample_length: int | None = None,
) -> np.ndarray:
    """Precompute ``n_resamples`` moving-block row-index draws for a ``t``-row panel.

    Returns an ``(n_resamples, L)`` int array where ``L`` is ``resample_length`` (or
    ``t`` when that is ``None``); row ``i`` is the row-index sequence for resample
    ``i``, every index drawn from ``[0, t)``. Extracted from
    :func:`block_bootstrap_band` so a caller that needs to evaluate several statistics
    over the *same* panel can draw once and reuse the same indices explicitly (see
    :func:`block_bootstrap_band`'s ``resample_indices`` parameter) instead of relying on
    separate calls with matching parameters happening to produce the same draws as an
    emergent side effect of content-independent RNG parameters.

    ``resample_length`` is the WP2.2-Task-2 length-matching hook: replicates shorter
    than the sample are drawn from the same ``t`` rows but carry ``L`` of them, so a
    length-sensitive estimator sees the same series length on both sides of the
    comparison (see :func:`block_bootstrap_band`).

    Determinism: all randomness flows from ``numpy.random.Generator(PCG64(seed))``
    constructed fresh here from the given ``seed`` -- no global RNG, no ``random``.
    """
    if t < 1:
        raise ValueError(f"_draw_moving_block_indices{_ctx(context)}: t must be >= 1, got {t}")
    if n_resamples < 1:
        raise ValueError(
            f"_draw_moving_block_indices{_ctx(context)}: n_resamples must be >= 1, "
            f"got {n_resamples}"
        )
    if block_length < 1:
        raise ValueError(
            f"_draw_moving_block_indices{_ctx(context)}: block_length must be >= 1, "
            f"got {block_length}"
        )
    length = t if resample_length is None else resample_length
    if length < 1:
        raise ValueError(
            f"_draw_moving_block_indices{_ctx(context)}: resample_length must be >= 1, "
            f"got {resample_length}"
        )

    eff_block_length = min(block_length, t)
    max_start = t - eff_block_length
    n_blocks_needed = -(-length // eff_block_length)  # ceil division

    rng = np.random.Generator(np.random.PCG64(seed))
    indices = np.empty((n_resamples, length), dtype=np.int64)
    for i in range(n_resamples):
        starts = rng.integers(0, max_start + 1, size=n_blocks_needed)
        row_idx = np.concatenate([np.arange(s, s + eff_block_length) for s in starts])[:length]
        indices[i] = row_idx
    return indices


def block_bootstrap_band(
    sample_fn: Callable[[np.ndarray], float],
    panel: np.ndarray,
    *,
    seed: int,
    n_resamples: int,
    level: float,
    block_length: int,
    tier: str = "monthly",
    context: str = "",
    resample_indices: np.ndarray | None = None,
    resample_length: int | None = None,
) -> StatBand:
    """Moving-block bootstrap confidence band for ``sample_fn`` evaluated over ``panel``.

    ``panel`` is a 2-D ``(T, k)`` array aligned on a shared time axis (``T`` rows =
    time, ``k`` columns = factors). Blocks of consecutive **rows** are resampled --
    never per-column/per-factor resampling -- and every column of a given resample is
    built from the *same* drawn row positions, so any cross-sectional dependence
    between ``panel``'s columns survives the resample. ``sample_fn`` receives the
    ``(T, k)`` panel (the original, or a resampled one of matching shape) and returns
    one scalar; it is responsible for selecting whichever column(s) it needs.

    Resampling: with ``eff_block_length = min(block_length, T)``, each of the
    ``n_resamples`` draws samples block-start row indices uniformly (with
    replacement) from ``[0, T - eff_block_length]`` until enough blocks are
    concatenated to cover at least ``T`` rows, then truncates to exactly ``T`` rows.
    The returned band's ``point`` is ``sample_fn`` on the full, un-resampled
    ``panel``; ``lo``/``hi`` is the ``level``-central percentile interval (e.g. the
    5th/95th percentile of the resample distribution for ``level=0.9``) over the
    ``n_resamples`` resampled values.

    **Length matching** (WP2.2 Task 2 fix pass, Important 3). ``resample_length``, if
    given, makes each replicate ``L`` rows long instead of ``T`` -- still drawn from
    the same ``T`` rows, still in blocks. Every per-path statistic registered in
    :data:`SINGLE_FACTOR_STATS` uses the n-denominator Box-Jenkins ACF estimator, whose
    finite-sample bias is a function of the series length: the ``(n - k) / n``
    shrinkage alone is ~20% at lag 24 on a 120-month path and ~2% on the ~1100-month
    historical series, and the mean-subtraction term is larger still for a persistent
    process. A band drawn at history's length is therefore not a criterion a
    120-month-path generator can satisfy even by reproducing history *exactly*; the
    gap is an artifact of the estimator, not evidence about the generator. Drawing the
    replicates at the ensemble's own path length puts the identical bias on both sides.
    The alternative -- switching every ACF to an ``(n - k)`` denominator -- was
    rejected because it would have to change :func:`_acf1` too (the two must never
    diverge) and it corrects only the shrinkage term, leaving the mean-subtraction bias
    intact and still length-dependent. Consequence, stated on :class:`StatBand`: when
    ``resample_length`` is set, ``point`` (the full-sample estimate) is not expected to
    lie inside ``[lo, hi]``.

    ``resample_indices``, if given, must be the ``(n_resamples, L)`` output of
    :func:`_draw_moving_block_indices` for this exact ``T``/``L`` -- pass the *same*
    array to every statistic sharing a panel to make the "these stats saw the same
    resample" property explicit rather than an accident of matching parameters. If
    omitted, the indices are drawn fresh from ``seed`` (still fully deterministic on
    its own).

    ``context``, if given, is appended to any raised ``ValueError`` so a caller
    computing many bands (one per factor, one per cross-block pair, ...) can identify
    which one failed without a debugger.

    Determinism: all randomness flows from ``numpy.random.Generator(PCG64(seed))``
    constructed fresh here from the given ``seed`` -- no global RNG, no ``random``.
    The same ``seed`` (with the same ``panel``, ``n_resamples``, ``level`` and
    ``block_length``) gives a bit-identical :class:`StatBand`.
    """
    panel = np.asarray(panel, dtype=np.float64)
    if panel.ndim != 2:
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: expected a 2-D (T, k) panel, "
            f"got shape {panel.shape}"
        )
    t = panel.shape[0]
    if t == 0:
        raise ValueError(f"block_bootstrap_band{_ctx(context)}: panel has zero rows")
    if not 0.0 < level < 1.0:
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: level must be in (0, 1), got {level}"
        )
    if n_resamples < 1:
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: n_resamples must be >= 1, got {n_resamples}"
        )
    if block_length < 1:
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: block_length must be >= 1, got {block_length}"
        )

    if resample_length is not None and resample_length < 1:
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: resample_length must be >= 1, "
            f"got {resample_length}"
        )
    length = t if resample_length is None else resample_length

    point = float(sample_fn(panel))

    if resample_indices is None:
        resample_indices = _draw_moving_block_indices(
            t,
            seed=seed,
            n_resamples=n_resamples,
            block_length=block_length,
            context=context,
            resample_length=resample_length,
        )
    elif resample_indices.shape != (n_resamples, length):
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: resample_indices shape "
            f"{resample_indices.shape} does not match (n_resamples={n_resamples}, "
            f"length={length})"
        )

    resample_stats = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        resample_stats[i] = sample_fn(panel[resample_indices[i]])

    alpha = (1.0 - level) / 2.0
    lo = float(np.percentile(resample_stats, 100.0 * alpha))
    hi = float(np.percentile(resample_stats, 100.0 * (1.0 - alpha)))
    return StatBand(
        point=point,
        lo=lo,
        hi=hi,
        n_resamples=n_resamples,
        level=level,
        tier=tier,
        resample_length=resample_length,
    )


# --------------------------------------------------------------------------- #
# compute_reference
# --------------------------------------------------------------------------- #


def _series_by_factor(read: FactorFrames) -> dict[str, pd.Series]:
    """Turn :attr:`FactorFrames.frames` into date-indexed value series, one per factor.

    No cross-factor alignment happens here -- each statistic aligns only what it needs
    (see the module docstring's "Data alignment" section). Resolution and the
    "missing, not an error" contract already happened in
    :func:`ah.eval.panel.read_factor_frames`; this is only the frame -> series shaping
    the statistics below want.
    """
    return {
        factor: frame.set_index("date")["value"].sort_index()
        for factor, frame in read.frames.items()
    }


def _coverage(series_by_factor: Mapping[str, pd.Series]) -> dict[str, FactorCoverage]:
    """Per-factor first/last observation date and count, in ``series_by_factor`` order."""
    coverage: dict[str, FactorCoverage] = {}
    for factor, series in series_by_factor.items():
        index = pd.to_datetime(pd.Index(series.index))
        coverage[factor] = FactorCoverage(
            first_date=str(index.min().date()),
            last_date=str(index.max().date()),
            n_obs=int(series.shape[0]),
        )
    return coverage


def _aligned_pair(series_by_factor: Mapping[str, pd.Series], fa: str, fb: str) -> np.ndarray | None:
    """Inner-join ``fa`` and ``fb``'s own series on date into a ``(T, 2)`` array.

    Returns ``None`` if the aligned overlap is empty (``T == 0``) -- the "zero-overlap
    pair" case that must be a named outcome (see ``CrossBlockReference.zero_overlap_pairs``)
    rather than an unhandled ``ValueError`` raised from deep inside
    :func:`block_bootstrap_band`.
    """
    joined = pd.concat(
        {fa: series_by_factor[fa], fb: series_by_factor[fb]}, axis=1, join="inner"
    ).sort_index()
    if joined.empty:
        return None
    return joined.to_numpy(dtype=np.float64)


def _block_reference(
    block: str,
    block_factors: list[str],
    series_by_factor: Mapping[str, pd.Series],
    *,
    seed: int,
    n_resamples: int,
    level: float,
    block_length: int,
    resample_length: int | None = None,
) -> BlockReference:
    """Every :data:`SINGLE_FACTOR_STATS` entry for every present factor of ``block``.

    Each factor gets its own panel (its own observations only -- see the module
    docstring) and its own moving-block resample draw, drawn once per factor and
    reused across every stat registered for that factor (:func:`_draw_moving_block_indices`),
    not redrawn per ``(factor, stat)``.
    """
    stats: dict[str, StatBand] = {}
    for factor in block_factors:
        panel = series_by_factor[factor].to_numpy(dtype=np.float64).reshape(-1, 1)
        t = panel.shape[0]
        resample_indices = _draw_moving_block_indices(
            t,
            seed=seed,
            n_resamples=n_resamples,
            block_length=block_length,
            context=f"block={block} factor={factor}",
            resample_length=resample_length,
        )
        for stat_name, registered in SINGLE_FACTOR_STATS.items():

            def sample_fn(
                arr: np.ndarray, _fn: Callable[[np.ndarray], float] = registered.fn
            ) -> float:
                return _fn(arr[:, 0])

            band = block_bootstrap_band(
                sample_fn,
                panel,
                seed=seed,
                n_resamples=n_resamples,
                level=level,
                block_length=block_length,
                tier=registered.tier,
                context=f"block={block} factor={factor} stat={stat_name}",
                resample_indices=resample_indices,
                resample_length=resample_length,
            )
            stats[f"{factor}.{stat_name}"] = band
    return BlockReference(block=block, stats=MappingProxyType(stats))


def _cross_block_reference(
    pair: tuple[str, str],
    factors_a: list[str],
    factors_b: list[str],
    series_by_factor: Mapping[str, pd.Series],
    *,
    seed: int,
    n_resamples: int,
    level: float,
    block_length: int,
    resample_length: int | None = None,
) -> CrossBlockReference:
    """Every :data:`CROSS_BLOCK_STATS` entry for every present factor pair drawn from ``pair``.

    Each ``(fa, fb)`` pair is aligned against *only itself* (:func:`_aligned_pair`), not
    the rest of either block, and gets its own moving-block resample draw reused across
    every stat registered for that pair. A pair with zero date overlap is recorded in
    the result's ``zero_overlap_pairs`` and contributes no stat entries.
    """
    stats: dict[str, StatBand] = {}
    zero_overlap: list[str] = []
    for fa in factors_a:
        for fb in factors_b:
            pair_panel = _aligned_pair(series_by_factor, fa, fb)
            if pair_panel is None:
                zero_overlap.append(f"{fa}~{fb}")
                continue
            t = pair_panel.shape[0]
            resample_indices = _draw_moving_block_indices(
                t,
                seed=seed,
                n_resamples=n_resamples,
                block_length=block_length,
                context=f"pair={pair[0]}|{pair[1]} factors={fa}~{fb}",
                resample_length=resample_length,
            )
            for stat_name, registered in CROSS_BLOCK_STATS.items():

                def sample_fn(
                    arr: np.ndarray,
                    _fn: Callable[[np.ndarray, np.ndarray], float] = registered.fn,
                ) -> float:
                    return _fn(arr[:, 0], arr[:, 1])

                band = block_bootstrap_band(
                    sample_fn,
                    pair_panel,
                    seed=seed,
                    n_resamples=n_resamples,
                    level=level,
                    block_length=block_length,
                    tier=registered.tier,
                    context=f"pair={pair[0]}|{pair[1]} factors={fa}~{fb} stat={stat_name}",
                    resample_indices=resample_indices,
                    resample_length=resample_length,
                )
                stats[f"{fa}~{fb}.{stat_name}"] = band
    return CrossBlockReference(
        pair=pair, stats=MappingProxyType(stats), zero_overlap_pairs=tuple(zero_overlap)
    )


def compute_reference(
    access: DataAccess,
    manifest: FactorManifest,
    *,
    vintage_id: str,
    seed: int,
    n_resamples: int = 1000,
    level: float = 0.9,
    block_length: int = DEFAULT_BLOCK_LENGTH,
    resample_length: int | None = None,
    split_reader: SplitReader = default_split_reader,
    factor_frames: FactorFrames | None = None,
) -> ReferenceStats:
    """Compute train+validation reference statistics and bootstrap bands, per block.

    Resolves every :meth:`FactorManifest.active_factors` factor through
    :func:`ah.eval.panel.read_factor_frames` -- the manifest's own ``factor_sources``
    mapping, so ``kind: series`` and ``kind: derived`` factors both resolve and no
    factor id is ever handed to the catalog verbatim. Reading goes through
    ``split_reader``, which defaults to :meth:`~ah.splits.DataAccess.train_val` (never
    ``access.frame(..., "holdout", ...)``, and this module holds no
    :class:`~ah.splits.FinalEvaluationToken` with which it even could). Each factor is
    read independently -- see the module docstring's "Data alignment" section for why
    this function does not inner-join every active factor onto one shared date axis
    before computing anything.

    ``factor_frames`` is the injection point: pass an already-resolved
    :class:`~ah.eval.panel.FactorFrames` to compute statistics over frames a caller
    built itself (a test fixture, or a caller that also wants
    :func:`ah.eval.panel.build_panel`'s assembled view of the *same* read, without
    paying for the read twice). When given, ``access``/``split_reader`` are not used.

    Then computes:

    - Every :data:`SINGLE_FACTOR_STATS` entry for every present factor, per active
      block (:class:`BlockReference`, one per ``manifest.active_blocks`` entry -- every
      active block gets an entry even if every one of its factors turned out to be
      missing, so a caller can always find the block by key), each over that factor's
      own observations only.
    - Every :data:`CROSS_BLOCK_STATS` entry for every present factor pair drawn from
      each ``manifest.cross_block_pairs()`` block pair (:class:`CrossBlockReference`,
      one per pair, with the pair recorded on the object), each over exactly that
      factor pair's aligned overlap. A pair with zero overlap is recorded in
      ``zero_overlap_pairs`` rather than raising.

    Factors belonging to an inactive block (declared in ``manifest.blocks`` but absent
    from ``manifest.active_blocks``) are never read: ``manifest.active_factors()``
    already excludes them, and this function does not fall back to
    ``manifest.blocks`` directly for iteration.

    A single ``seed`` drives every block-bootstrap draw in this call: the same ``seed``
    against the same data gives bit-identical bands. For a given factor (or cross-block
    pair), the moving-block resample row positions are drawn exactly once and reused
    across every stat computed for that factor/pair (:func:`_draw_moving_block_indices`),
    not redrawn per ``(factor, stat)`` -- so the "stats sharing a panel share a
    resample" property is explicit, not an emergent side effect of separate calls
    happening to share the same ``(seed, T, block_length, n_resamples)``.

    ``resample_length`` makes every bootstrap replicate that many rows long instead of
    the factor's own sample length -- **pass the judged ensemble's path length**, which
    is what :func:`ah.eval.battery.run_full_battery` does. Without it, the band for
    every length-sensitive statistic (every ACF, the fitted decay, the leverage
    correlation) is drawn at ~1100 months while the generator is measured over ~120,
    and the two are not comparable under the n-denominator estimator this module fixes
    as its convention. See :func:`block_bootstrap_band` for the full argument and for
    why the ``(n - k)``-denominator alternative was rejected.
    """
    if factor_frames is None:
        try:
            factor_frames = _read_factor_frames(access, manifest, split_reader=split_reader)
        except PanelError as exc:
            # A malformed frame (or a malformed factor_sources entry) is a bug, not a
            # data gap. Re-raised under this module's own named error so a caller of
            # compute_reference sees one error type -- the message already names the
            # offending factor and series id.
            raise ReferenceComputationError(str(exc)) from exc
    series_by_factor = _series_by_factor(factor_frames)
    missing = factor_frames.missing

    blocks: dict[str, BlockReference] = {}
    for block in manifest.active_blocks:
        block_factors = [f for f in manifest.blocks[block] if f in series_by_factor]
        blocks[block] = _block_reference(
            block,
            block_factors,
            series_by_factor,
            seed=seed,
            n_resamples=n_resamples,
            level=level,
            block_length=block_length,
            resample_length=resample_length,
        )

    cross_blocks: dict[tuple[str, str], CrossBlockReference] = {}
    for pair in manifest.cross_block_pairs():
        block_a, block_b = pair
        factors_a = [f for f in manifest.blocks[block_a] if f in series_by_factor]
        factors_b = [f for f in manifest.blocks[block_b] if f in series_by_factor]
        cross_blocks[pair] = _cross_block_reference(
            pair,
            factors_a,
            factors_b,
            series_by_factor,
            seed=seed,
            n_resamples=n_resamples,
            level=level,
            block_length=block_length,
            resample_length=resample_length,
        )

    return ReferenceStats(
        blocks=MappingProxyType(blocks),
        cross_blocks=MappingProxyType(cross_blocks),
        active_blocks=manifest.active_blocks,
        vintage_id=vintage_id,
        n_resamples=n_resamples,
        seed=seed,
        missing_factors=missing,
        missing_declared=factor_frames.missing_declared,
        missing_no_data=factor_frames.missing_no_data,
        coverage=MappingProxyType(_coverage(series_by_factor)),
    )
