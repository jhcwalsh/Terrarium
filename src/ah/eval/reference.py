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
- :data:`STRATEGY_STATS` (WP2.2 Task 4) -- one sealed D4 benchmark strategy
  (``ah.strategies.load_d4_strategies``), keyed ``"<strategy_id>.<stat>"`` in
  ``ah.eval.prereg``'s ``thresholds.strategies`` section. A fourth scope, not a
  variant of the other three: its axis is sealed *data* in ``pre-registration.yaml``,
  not a factor or factor pair in ``ah.factors.FactorManifest``. See its own section
  below for why every entry carries no ``fn``.

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
conditional,calibration}.py``). Only ``monthly``, ``horizon``, ``tails`` and
``utility`` exist yet (WP2.2 Task 4 added the latter two); the rest are intentionally
not stubbed here.

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

from ah.data import derive
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

    ``n_valid_resamples`` is how many of the ``n_resamples`` replicates produced a
    non-NaN value. It exists because :func:`block_bootstrap_band` takes ordinary
    ``np.percentile``, which is **not** NaN-robust: a single undefined replicate (a
    resample too short on drawdown episodes, say) propagates NaN into *both* bounds even
    though ``point`` is perfectly well defined. That behaviour is deliberate and
    deferred (``governance/retrofit-register.md`` RFR-19), but without this field the
    resulting NaN band is indistinguishable, in the G2 evidence artifact, from a
    statistic that is not computable at all -- and a band resting on 3 valid replicates
    out of 1000 is indistinguishable from one resting on all 1000. ``None`` only on a
    band constructed by hand rather than by :func:`block_bootstrap_band`.
    """

    point: float
    lo: float
    hi: float
    n_resamples: int
    level: float
    tier: str
    resample_length: int | None = None
    n_valid_resamples: int | None = None


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
    # WP2.2 Task 4. Per-factor, date-indexed train+validation series (the SAME objects
    # `compute_reference` already builds internally as `series_by_factor`, before any
    # per-statistic alignment happens -- see the module docstring's "Data alignment").
    # Exposed here because the D4 tail-fidelity backtests (`ah.eval.metrics.tails`) and
    # the utility-tier suite (`ah.eval.metrics.utility`) both need genuinely joint,
    # multi-factor historical data (a strategy's weighted sum across several legs; a
    # real-vs-generated comparison) that no existing single-factor/cross-block-pair
    # registry can serve, and BOTH must read it through this one surface -- never a
    # fresh `DataAccess`/catalog read -- so the holdout-leakage guard and the "train+val
    # only" invariant cover them exactly as they cover every other reference statistic.
    # Keyed by factor id (not series id); values are UNALIGNED (each factor keeps its
    # own date index and length, exactly as `_series_by_factor` produced them) -- a
    # consumer that needs several factors aligned together (a D4 strategy's own legs, in
    # `ah.eval.metrics.tails`) is responsible for its own inner join over exactly the
    # factors it needs, the same pattern `_aligned_pair` already uses for a cross-block
    # pair, generalized to more than two series. This module deliberately does not
    # pre-join every active factor onto one shared axis (see "Data alignment" above): a
    # single short-history factor must not truncate a computation that never needed it.
    historical_series: Mapping[str, pd.Series] = MappingProxyType({})

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
                    "n_valid_resamples": band.n_valid_resamples,
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
    """A single-factor statistic function paired with its DN-1.1 Sec.II.6 horizon tier.

    Two further flags, both defaulting to the ordinary case, both added by WP2.2 Task
    3's fix pass because a statistic that needed either was being given a band that
    could not do its job:

    - ``length_matched`` (default ``True``): whether this statistic's bootstrap
      replicates are drawn at the judged ensemble's own path length (see
      :func:`block_bootstrap_band`'s "Length matching"). ``False`` means the replicates
      are drawn at the FULL train+validation sample length instead. That is right for a
      statistic whose own definition already fixes the length scale it operates on --
      ``lost_decade_frequency`` and ``long_inflation_era_frequency`` are the fraction of
      the input's own 120-month windows satisfying a property, so both sides evaluate
      the identical 120-month indicator whatever the outer series length, and the only
      thing the outer length changes is how many windows the frequency averages over,
      i.e. the frequency's own sampling error -- which is exactly what the band is
      measuring. Length-matching those two to a 120-month replicate would leave each
      replicate holding exactly ONE window, making every replicate value 0.0 or 1.0 and
      the percentile band either ``[0, 1]`` (vacuous) or ``[0, 0]``/``[1, 1]``
      (knife-edge). Contrast the ACF family, where the ESTIMATOR ITSELF is biased by
      series length and matching is mandatory.
    - ``has_historical_analog`` (default ``True``): ``False`` means the statistic cannot
      be posed on a historical series at all, so no resampling is performed and the band
      is NaN by construction (see :func:`_ergodicity_gap_reference_stub`). Registering
      the name is still what makes it sealable; running 1000 resamples of a function
      that returns a constant NaN is not.
    """

    fn: Callable[[np.ndarray], float]
    tier: str
    length_matched: bool = True
    has_historical_analog: bool = True


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

    **Censored at the search bounds** (Minor 8, WP2.2 Task 2 fix pass 2). A curve
    decaying genuinely faster than ``exp(-_DECAY_RATE_MAX * lag)`` cannot be
    represented within the sealed ``[-1.0, 5.0]`` search domain: the profiled SSE keeps
    improving all the way to the boundary, and :func:`fit_exp_decay_rate` returns
    approximately the bound itself (``~5.0``), **not NaN**. This is not a correctness
    bug -- the generated ensemble's rate and the reference's are censored by the exact
    same estimator, so a comparison between the two is still apples to apples -- but it
    is a fact about the estimator that belongs in its definition, not something a
    reader should have to discover by noticing a suspicious cluster of values at 5.0.
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


# --------------------------------------------------------------------------- #
# WP2.2 Task 3: the 1_5yr and 10yr horizon statistics (DN-1.1 Sec.II.6 rows 2-3)
#
# Live here for the identical structural reason WP2.2 Task 2's monthly statistics do
# (see this module's docstring, "WP2.2 Task 2: the monthly stylized-fact statistics"):
# a statistic defined only in ``ah.eval.metrics.horizon`` could never carry a sealed
# threshold, because ``ah.eval.prereg`` validates a threshold key's ``<stat>`` against
# these very registries. ``ah.eval.metrics.horizon`` imports these definitions; it
# supplies only the ensemble-level pooling convention on top (per-path average, or a
# true pool across paths -- stated per metric in that module's docstring, since
# ``governance/retrofit-register.md`` RFR-15 makes the distinction load-bearing for
# length matching).
# --------------------------------------------------------------------------- #

# ---- variance ratio (registered tier "1_5yr") ---------------------------------
#
# Lo-MacKinlay-style: Var(non-overlapping k-month sums) / (k * Var(the raw monthly
# values)), exactly 1.0 in expectation for iid returns (Var(sum of k iid) = k*Var(one)),
# > 1 under positive serial correlation (autocovariances add constructively to the
# k-sum's variance), < 1 under mean reversion (they subtract). NON-OVERLAPPING sums are
# used (via :func:`nonoverlapping_sums`, already registered for ``agg_gaussianity`` --
# not a second windowing scheme): overlapping k-month sums are the classical
# Lo-MacKinlay estimator and have smaller sampling variance, but induce (k-1)/k of the
# observations to share up to k-1 months of overlap, which is itself a manufactured
# serial dependence -- exactly the artifact this statistic exists to detect, not to
# manufacture. NO small-sample / heteroskedasticity-robust correction (the classical
# test statistic's variance formula under a maintained iid null) is applied: this
# module reports the ratio itself, a description, not a signed test statistic, so no
# asymptotic-variance correction is needed to interpret it, consistent with every other
# estimator in this file reporting a plain point value for banding rather than a
# corrected test statistic.
VARIANCE_RATIO_HORIZONS: tuple[tuple[int, str], ...] = (
    (12, "12m"),
    (36, "36m"),
    (60, "60m"),
    (120, "120m"),
)

# Variance's relative standard error is ~sqrt(2/n) for a roughly-Gaussian quantity: at
# n=10 that is ~45%, noisy but not meaningless -- unlike a fourth-moment statistic
# (AGG_GAUSSIANITY_MIN_SUMS's much higher floor of 30, below which excess kurtosis
# carries no information about the effect it targets at all). 10 rules out a variance
# computed from a literal handful of non-overlapping k-month sums while staying low
# enough that a k=120 ratio -- which yields exactly ONE non-overlapping sum per
# 120-month path -- remains computable once pooled across a production ensemble's many
# paths (see ``ah.eval.metrics.horizon``'s pooling wrapper).
VARIANCE_RATIO_MIN_SUMS = 10


def variance_ratio_from_arrays(sums: np.ndarray, raw_values: np.ndarray, k: int) -> float:
    """The variance-ratio computation, taking already-assembled arrays.

    Split from :func:`variance_ratio` so ``ah.eval.metrics.horizon`` can POOL
    non-overlapping sums (and raw values) ACROSS an ensemble's paths -- computed
    independently within each path via :func:`nonoverlapping_sums`, then concatenated,
    exactly as :func:`agg_gaussianity`'s own ensemble-level wrapper already does for a
    marginal-distribution statistic -- before taking the ratio once over the pooled
    arrays, rather than computing a ratio per path and averaging ratios (which is a
    different, more per-path-noisy estimator DN-1.1's "naturally pooled" framing does
    not ask for; see ``ah.eval.metrics.horizon``'s module docstring).
    """
    sums = np.asarray(sums, dtype=np.float64).reshape(-1)
    raw_values = np.asarray(raw_values, dtype=np.float64).reshape(-1)
    if k < 1:
        raise ValueError(f"variance_ratio_from_arrays: k must be >= 1, got {k}")
    if sums.size < VARIANCE_RATIO_MIN_SUMS or raw_values.size < 2:
        return float("nan")
    var_k = float(np.var(sums, ddof=1))
    var_1 = float(np.var(raw_values, ddof=1))
    if var_1 == 0.0:
        return float("nan")
    return var_k / (k * var_1)


def variance_ratio(x: np.ndarray, k: int) -> float:
    """Single-array convenience form of :func:`variance_ratio_from_arrays`.

    Used directly for the train+validation reference (one flat historical series --
    no ensemble/path structure to pool over) and, per-path, as the historical-analog
    convention the ensemble wrapper composes on top of.
    """
    if k < 1:
        raise ValueError(f"variance_ratio: k must be >= 1, got {k}")
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    return variance_ratio_from_arrays(nonoverlapping_sums(x, k), x, k)


def _variance_ratio_stat(k: int) -> Callable[[np.ndarray], float]:
    def stat(x: np.ndarray) -> float:
        return variance_ratio(x, k)

    return stat


# ---- mean-reversion half-life (registered tier "1_5yr") -----------------------


def mean_reversion_halflife(x: np.ndarray) -> float:
    """Half-life (in months) of an AR(1) fit's mean reversion: ``ln(0.5) / ln(phi)``.

    ``phi`` is the lag-1 sample autocorrelation, :func:`_acf_at_lag`\\ (x, 1) -- the
    same n-denominator Box-Jenkins estimator every other lag-dependent statistic in
    this file uses (not a second, independently fitted OLS AR(1) coefficient): for an
    AR(1) process the population lag-1 autocorrelation IS phi, so reusing the already-
    registered estimator is a correct fit, not an approximation.

    **Decided and tested behaviour at phi's extremes** (the brief's explicit
    requirement): the *magnitude* ``abs(phi)`` drives the decay, not signed ``phi``
    directly, so that a genuinely oscillating-but-decaying process (``-1 < phi < 0``)
    still gets a finite, meaningful half-life rather than an undefined ``ln`` of a
    negative number:

    - ``abs(phi) >= 1.0`` (no mean reversion, or an explosive/unit-root process):
      returns ``+inf``, not ``NaN`` -- "never reverts" is meaningfully different from
      "uncomputable", and a reader scanning a report table for a persistence problem
      should see an explicit infinity, not a blank uncomputable cell.
    - ``phi == 0.0`` (no lag-1 dependence at all): returns ``0.0`` -- the limit of
      ``ln(0.5)/ln(m)`` as ``m -> 0`` is exactly the "reverts within the same step"
      answer, not a special case bolted on.
    - ``phi`` is ``NaN`` (degenerate/too-short series, see :func:`_acf_at_lag`):
      returns ``NaN``, unchanged.
    """
    phi = _acf_at_lag(x, 1)
    if np.isnan(phi):
        return float("nan")
    magnitude = abs(phi)
    if magnitude >= 1.0:
        return float("inf")
    if magnitude == 0.0:
        return 0.0
    return float(np.log(0.5) / np.log(magnitude))


# ---- drawdown depth/duration joint distribution (registered tier "1_5yr") -----
#
# DN-1.1 asks for "drawdown depth/duration joint dist"; reported as three separately
# registered scalar summaries (median depth, median duration, their rank correlation)
# rather than an unusable distribution object -- WP2.3 can then band each individually.


def _drawdown_series(returns: np.ndarray) -> np.ndarray:
    """The running drawdown of ``returns`` via :func:`ah.data.derive.drawdown_state`.

    Reused, not reimplemented: ``drawdown_state`` takes a ``(date, value)`` frame, and
    its calculation (``(1+r).cumprod()`` then running max) does not read the dates
    arithmetically, only the row order -- so ``returns`` is wrapped in a synthetic
    monthly-dated frame purely to satisfy that signature.

    :data:`SINGLE_FACTOR_STATS` entries are evaluated uniformly over EVERY registered
    factor by :func:`compute_reference` (the same "computed regardless of relevance"
    precedent ``hill_tail_index`` already sets for a level factor), so this may be
    called on data with no economically real bound on magnitude -- and a battery run
    over an adversarial/broken generator (the WP2.2b negative-control suite's entire
    purpose) is exactly the case where it must not crash. ``np.errstate`` makes an
    overflowing cumulative product settle at ``+/-inf`` (a valid IEEE754 outcome, not
    an error) instead of raising under this repo's ``filterwarnings = ["error"]``
    pytest config.

    **What happens to those non-finite values is not a free pass** (WP2.2 Task 3 fix
    pass 1, Important 3). An earlier version of this docstring called ``inf``/``NaN``
    drawdowns "an honest 'cannot really say' outcome" because ``inf < 0.0`` and
    ``NaN < 0.0`` are both ``False``. They are not: under :func:`drawdown_episodes`'
    episode rule ``False`` means *at a new high*, so an overflowed path was silently
    recorded as having NO DRAWDOWNS AT ALL -- the favourable answer -- and then dropped
    from the pooled episode concatenation entirely, which is a "gamed by generating
    less" vector inside an aggregating metric. :func:`drawdown_episodes` now detects a
    non-finite drawdown series explicitly and poisons its own output with NaN instead.
    """
    returns = np.asarray(returns, dtype=np.float64).reshape(-1)
    if returns.shape[0] == 0:
        return returns
    dates = pd.date_range("2000-01-01", periods=returns.shape[0], freq="MS")
    with np.errstate(over="ignore", invalid="ignore"):
        dd_frame = derive.drawdown_state(pd.DataFrame({"date": dates, "value": returns}))
    return dd_frame["value"].to_numpy(dtype=np.float64)


# The minimum number of pooled drawdown episodes any of the three drawdown summaries
# is willing to be computed from -- the same shape of floor VARIANCE_RATIO_MIN_SUMS and
# AGG_GAUSSIANITY_MIN_SUMS impose on their own estimators, and absent here until WP2.2
# Task 3's fix pass (Important 3). Without it a generator whose paths mostly never draw
# down contributes zero episodes from those paths and is scored on the minority that
# did: a median from a single pooled episode was legal, and "generate fewer drawdowns"
# was a way to make the median shallower rather than to fail the metric.
# 10, matching VARIANCE_RATIO_MIN_SUMS rather than AGG_GAUSSIANITY_MIN_SUMS's 30: the
# sample median of n draws has an asymptotic standard error of ~1.25 * sigma / sqrt(n)
# (~40% of a standard deviation at n=10) -- noisy but informative, the same trade-off
# the variance floor already accepts, and far better behaved than the fourth-moment
# statistic that needs 30.
DRAWDOWN_MIN_EPISODES = 10


def drawdown_episodes(returns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Depth (positive magnitude) and duration (months) of every drawdown episode.

    An episode is a maximal run of consecutive months with running drawdown ``< 0``
    (``== 0.0`` exactly at a new high ends it). ``depth`` is the magnitude of the
    episode's trough (its most negative point); ``duration`` is the episode's length
    in months. An episode still open at the series' final observation is counted as
    ending there -- its trough may not be the eventual trough a longer series would
    reveal, a real, stated property of a finite window rather than a bug.

    Returns two equal-length 1-D arrays, empty (not raising) if ``returns`` produced
    no drawdown at all (e.g. an all-non-negative return series).

    **A non-finite running drawdown poisons the result rather than vanishing from it**
    (WP2.2 Task 3 fix pass 1, Important 3). If compounding overflowed
    (:func:`_drawdown_series`), ``wealth / cummax`` is ``inf/inf = NaN``; since
    ``NaN < 0.0`` is ``False`` the loop below would classify every such month as "at a
    new high" and return two EMPTY arrays -- reporting "this path had no drawdowns",
    the favourable answer, and removing the path from the pooled concatenation. Instead
    a single NaN episode is returned, which propagates NaN through every summary that
    reads it (:func:`_drawdown_summary_depth` and friends check for finiteness before
    taking a median) and so through the pooled ensemble metric as well. One
    uncomputable path NaNs the metric, exactly as one absent factor NaNs
    ``cross_block_corr_matrix_distance``.
    """
    dd = _drawdown_series(returns)
    if dd.size > 0 and not bool(np.all(np.isfinite(dd))):
        return np.array([float("nan")]), np.array([float("nan")])
    depths: list[float] = []
    durations: list[int] = []
    in_episode = False
    trough = 0.0
    length = 0
    for v in dd:
        if v < 0.0:
            if not in_episode:
                in_episode = True
                trough = float(v)
                length = 1
            else:
                trough = min(trough, float(v))
                length += 1
        else:
            if in_episode:
                depths.append(-trough)
                durations.append(length)
                in_episode = False
    if in_episode:
        depths.append(-trough)
        durations.append(length)
    return np.array(depths, dtype=np.float64), np.array(durations, dtype=np.float64)


def _rank(x: np.ndarray) -> np.ndarray:
    """Average ("fractional") 1-based ranks of ``x``, ties averaged."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


def spearman_rank_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman's rank correlation: Pearson correlation of average ranks (ties
    averaged) -- the standard equivalent formulation, chosen to avoid a scipy
    dependency (``CLAUDE.md``: no new dependencies; numpy plus ``statistics`` covers
    this file). ``NaN`` if fewer than 2 paired observations.
    """
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    if a.shape[0] != b.shape[0]:
        raise ValueError(f"spearman_rank_correlation: shape mismatch {a.shape} vs {b.shape}")
    if a.shape[0] < 2:
        return float("nan")
    return _correlation(_rank(a), _rank(b))


def drawdown_median(episode_values: np.ndarray) -> float:
    """Median of a pooled drawdown-episode array, under the shared floor and NaN rule.

    One function so the reference side (one historical series) and the ensemble side
    (``ah.eval.metrics.horizon``'s pooled concatenation across paths) can never drift
    apart on either the :data:`DRAWDOWN_MIN_EPISODES` floor or the treatment of a
    non-finite episode -- the same reason ``agg_gaussianity`` shares
    :data:`AGG_GAUSSIANITY_MIN_SUMS` across both sides.
    """
    episode_values = np.asarray(episode_values, dtype=np.float64).reshape(-1)
    if episode_values.size < DRAWDOWN_MIN_EPISODES:
        return float("nan")
    if not bool(np.all(np.isfinite(episode_values))):
        return float("nan")
    return float(np.median(episode_values))


def drawdown_rank_corr(depths: np.ndarray, durations: np.ndarray) -> float:
    """Spearman rank correlation of pooled depths against durations, same floor/NaN rule."""
    depths = np.asarray(depths, dtype=np.float64).reshape(-1)
    durations = np.asarray(durations, dtype=np.float64).reshape(-1)
    if depths.size < DRAWDOWN_MIN_EPISODES:
        return float("nan")
    if not (bool(np.all(np.isfinite(depths))) and bool(np.all(np.isfinite(durations)))):
        return float("nan")
    return spearman_rank_correlation(depths, durations)


def _drawdown_summary_depth(x: np.ndarray) -> float:
    depths, _ = drawdown_episodes(x)
    return drawdown_median(depths)


def _drawdown_summary_duration(x: np.ndarray) -> float:
    _, durations = drawdown_episodes(x)
    return drawdown_median(durations)


def _drawdown_summary_rank_corr(x: np.ndarray) -> float:
    depths, durations = drawdown_episodes(x)
    return drawdown_rank_corr(depths, durations)


# ---- lost-decade frequency (registered tier "10yr") ----------------------------
#
# NOMINAL, not real (CPI-deflated) total return -- a deliberate, stated scope
# limitation, not an oversight. "Lost decade" is classically a REAL-return concept,
# but this statistic is registered in SINGLE_FACTOR_STATS, whose reference-side
# ``fn: Callable[[np.ndarray], float]`` is applied by ``_block_reference`` to exactly
# ONE factor's own column (see this module's "Data alignment" section) -- there is no
# second (CPI) series available to a SINGLE_FACTOR_STATS function at all. A real
# (deflated) version needs a genuinely joint equity+CPI reference computation, which
# this module's own docstring flags as future work needing its own alignment ("if
# WP2.2 registers [a joint within-block statistic], it should align only that
# statistic's own block-scoped factors, not reintroduce a single all-active-factors
# join") -- out of this task's registered-not-edited scope. Recorded as
# ``governance/retrofit-register.md`` RFR-21 for WP2.3 to decide: seal the nominal
# version as-is, or build the joint deflated one first.
#
# INTERNAL WINDOWING, AND WHY (WP2.2 Task 3 fix pass 1, Critical 1). This function is a
# FREQUENCY: the fraction of the input's own overlapping LOST_DECADE_WINDOW_MONTHS-month
# windows that compounded to a non-positive total return. The first version was instead
# a single 0.0/1.0 indicator over the whole input, with the "frequency" supposedly
# emerging from calling it once per bootstrap replicate. That does not work, and the
# claim was wrong on its own terms: :func:`block_bootstrap_band` takes PERCENTILES of
# the replicate values, never their mean, so the historical frequency -- the mean of
# that Bernoulli resample distribution -- was never formed anywhere, and the band was
# the 5th/95th percentile of a 0/1 variable: `[0, 1]` (vacuous, admits every possible
# ensemble value) or `[0, 0]`/`[1, 1]` (knife-edge, fails any generator with a non-zero
# rate). A sealable band that cannot do its job.
#
# OVERLAPPING windows (stride 1 month), unlike ``variance_ratio``'s deliberately
# NON-overlapping k-month sums. The two choices are consistent, not contradictory,
# because the failure modes differ: overlapping SUMS manufacture serial dependence in
# the very variance a variance ratio exists to measure, whereas this statistic is a MEAN
# OF INDICATORS, for which overlap introduces no bias in the estimated marginal
# probability at all -- it only reduces the effective sample size, which is precisely
# what the bootstrap band (not the point estimate) is responsible for reporting. The
# alternative, calendar-aligned non-overlapping decades, would rest the whole statistic
# on ~9 windows AND on an arbitrary phase choice (starting the tiling in 1926 rather
# than 1927 gives a materially different answer), which is a worse estimator of the same
# quantity.
#
# LENGTH-MATCHING CONSEQUENCE, stated because it is the price of this fix. A
# length-matched replicate (``resample_length=ensemble.months`` = 120) holds exactly ONE
# window, which would reproduce the degenerate Bernoulli band this fix removes. This
# statistic is therefore registered ``length_matched=False`` (see :class:`RegisteredStat`)
# and its replicates are drawn at the full train+validation length. That is not a
# violation of ``conventions.estimator_length_matching`` but the correct reading of it:
# matching exists because the ACF family's ESTIMATOR is biased by series length, while
# here the 120-month window fixes the length scale internally and identically on both
# sides -- the ensemble side evaluates the same 120-month indicator, once per path. The
# outer length changes only how many windows are averaged, i.e. the frequency's own
# sampling error, which is the thing the band is measuring. The band is consequently
# wide, reflecting history's ~9-14 effectively independent decades: DN-1.1 Sec.II.6's
# "wide-band consistency, honestly reported (n ~ 14)" for this exact tier.
LOST_DECADE_WINDOW_MONTHS = 120


def _decade_window_count(n: int, window: int) -> int:
    """How many overlapping ``window``-length windows an ``n``-observation series holds."""
    return 0 if n < window else n - window + 1


def lost_decade_frequency(returns: np.ndarray) -> float:
    """Fraction of ``returns``' overlapping 120-month windows whose compounded total
    return (product of ``1+r``, minus 1) is ``<= 0.0``.

    ``NaN`` if ``returns`` is shorter than :data:`LOST_DECADE_WINDOW_MONTHS` (a decade
    is the unit of this statistic; a shorter series carries no window at all, and a
    value computed from a shorter, easier window would not be the same quantity), or if
    any window's compounded value is non-finite.

    ``np.errstate`` (see :func:`_drawdown_series` for the full argument): evaluated
    uniformly over every registered factor, this must not RAISE on an extreme-magnitude
    input under this repo's ``filterwarnings = ["error"]`` config. An overflowed product
    is then ``NaN``, never the favourable "clearly not a lost decade" answer that
    ``inf <= 0.0 -> False`` used to produce -- the same gaming vector Important 3 found
    in the drawdown path.
    """
    returns = np.asarray(returns, dtype=np.float64).reshape(-1)
    n_windows = _decade_window_count(returns.shape[0], LOST_DECADE_WINDOW_MONTHS)
    if n_windows == 0:
        return float("nan")
    gross = 1.0 + returns
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        windows = np.lib.stride_tricks.sliding_window_view(gross, LOST_DECADE_WINDOW_MONTHS)
        compounded = np.prod(windows, axis=1)
    if not bool(np.all(np.isfinite(compounded))):
        return float("nan")
    return float(np.mean(compounded <= 1.0))


# ---- long-inflation-era frequency (registered tier "10yr") ---------------------
#
# Sealed definition: a "sustained high-inflation era" is a run of >= LONG_INFLATION_
# MIN_RUN_MONTHS (24, two years -- long enough to distinguish a genuine multi-year
# inflationary era from a single hot-CPI-print blip, short enough to still be found
# inside a single ~120-month generated decade) CONSECUTIVE months with year-on-year
# CPI inflation (:func:`ah.data.derive.yoy` on the level series) at or above
# ``ah.data.derive.regime_thresholds()['cpi_high']`` -- the Step-1 regime ruleset's
# OWN inflation threshold (regime_ruleset_v1: 4.0), reused rather than a second,
# independently chosen number, and traceable to that ruleset's version (see
# ``ah.eval.metrics.horizon``'s module docstring for where the version is recorded).
#
# Like ``lost_decade_frequency`` (see the argument there in full, which applies
# verbatim), this is a FREQUENCY over overlapping 120-month windows of the LEVEL series
# -- not a single 0.0/1.0 indicator over the whole input -- and is registered
# ``length_matched=False`` so its replicates are drawn at the full train+validation
# length rather than at one decade.
#
# WINDOWED ON THE LEVEL, NOT ON cpi_yoy, and that distinction is load-bearing.
# ``derive.yoy`` consumes the first 12 months of whatever it is given, so a window of
# 120 LEVEL months yields 108 cpi_yoy months inside it, comfortably enough to hold the
# 24-month minimum run -- whereas windowing the already-derived cpi_yoy series at 120
# would need 132 level months and would make the statistic uncomputable on exactly the
# 120-month paths a generator produces. Because cpi_yoy at level index t reads only
# level indices t and t-12, restricting a globally computed cpi_yoy to level-window
# ``[s, s + 120)`` gives EXACTLY the within-window year-on-year series, so the whole
# frequency is computed from one global ``derive.yoy`` call rather than one per window.
LONG_INFLATION_MIN_RUN_MONTHS = 24
LONG_INFLATION_ERA_WINDOW_MONTHS = 120
YOY_WARMUP_MONTHS = 12


def _cpi_yoy_from_level(cpi_level: np.ndarray) -> np.ndarray:
    """Year-on-year CPI inflation from a raw index-level array, via :func:`ah.data.derive.yoy`.

    Reused, not reimplemented: ``yoy`` is wrapped the same way :func:`_drawdown_series`
    wraps ``drawdown_state`` -- a synthetic monthly-dated frame, since ``yoy``'s
    ``pct_change`` does not read the dates arithmetically, only row order.
    """
    cpi_level = np.asarray(cpi_level, dtype=np.float64).reshape(-1)
    if cpi_level.shape[0] == 0:
        return cpi_level
    dates = pd.date_range("2000-01-01", periods=cpi_level.shape[0], freq="MS")
    yoy_frame = derive.yoy(pd.DataFrame({"date": dates, "value": cpi_level}))
    return yoy_frame["value"].to_numpy(dtype=np.float64)


def long_inflation_era_frequency(cpi_level: np.ndarray) -> float:
    """Fraction of ``cpi_level``'s overlapping 120-month windows that contain a
    sustained high-inflation era (see the section header above for the full sealed
    definition). ``NaN`` if ``cpi_level`` is shorter than
    :data:`LONG_INFLATION_ERA_WINDOW_MONTHS`.
    """
    cpi_level = np.asarray(cpi_level, dtype=np.float64).reshape(-1)
    n = cpi_level.shape[0]
    n_windows = _decade_window_count(n, LONG_INFLATION_ERA_WINDOW_MONTHS)
    if n_windows == 0:
        return float("nan")
    # cpi_yoy[j] corresponds to level index j + YOY_WARMUP_MONTHS (derive.yoy drops the
    # warm-up), so level window [s, s + W) covers cpi_yoy indices
    # [s, s + W - YOY_WARMUP_MONTHS).
    cpi_yoy = _cpi_yoy_from_level(cpi_level)
    threshold = float(derive.regime_thresholds()["cpi_high"])
    above = (cpi_yoy >= threshold).astype(np.int64)
    # run_start[j] is 1 when a full LONG_INFLATION_MIN_RUN_MONTHS run of above-threshold
    # months STARTS at cpi_yoy index j -- so a window contains an era exactly when at
    # least one such start falls early enough for the whole run to fit inside it.
    cum_above = np.concatenate([[0], np.cumsum(above)])
    min_run = LONG_INFLATION_MIN_RUN_MONTHS
    n_yoy = above.shape[0]
    n_starts = max(0, n_yoy - min_run + 1)
    if n_starts == 0:
        return 0.0
    run_start = (cum_above[min_run : min_run + n_starts] - cum_above[:n_starts]) == min_run
    cum_start = np.concatenate([[0], np.cumsum(run_start.astype(np.int64))])
    per_window_yoy = LONG_INFLATION_ERA_WINDOW_MONTHS - YOY_WARMUP_MONTHS
    starts_per_window = max(0, per_window_yoy - min_run + 1)
    if starts_per_window == 0:
        return 0.0
    lo = np.arange(n_windows)
    hi = np.minimum(lo + starts_per_window, n_starts)
    lo = np.minimum(lo, hi)
    return float(np.mean((cum_start[hi] - cum_start[lo]) > 0))


# ---- 10y return vs starting valuation: slope & R^2 (registered tier "10yr") ----
#
# Structural gap, stated rather than hidden (see ``ah.eval.metrics.horizon``'s module
# docstring): there is no valuation/CAPE factor anywhere in ``factors.yaml`` today --
# DN-1.1's Layer-1 "climate" state ``v_t`` (demeaned log CAPE) is not yet a Step-2
# generator-visible factor, though the raw ``shiller.cape`` series IS registered in
# ``requirements.yaml``. Consequently this pure regression estimator is exercised only
# against synthetic ground truth in tests today; the wired ensemble-side metric (see
# ``ah.eval.metrics.horizon``) returns NaN unconditionally, honestly, until a
# valuation factor exists. It is registered in :data:`PANEL_STATS` (bare name, no
# historical band -- the same shape as ``cross_block_corr_matrix_distance``) rather
# than :data:`SINGLE_FACTOR_STATS`, because it is not "one factor's own series": it is
# a comparison between an equity return series and a valuation series that today has
# no factor identity to be keyed under at all.


def valuation_regression(cape_v: np.ndarray, forward_return: np.ndarray) -> tuple[float, float]:
    """OLS slope and R^2 of ``forward_return ~ a + b * cape_v`` (``b`` is the slope).

    Ordinary least squares in closed form (no scipy): ``slope = Sxy / Sxx``,
    ``intercept = ybar - slope * xbar``, ``R^2 = 1 - SS_res / SS_tot``. ``(NaN, NaN)``
    if fewer than 3 paired points, if ``cape_v`` is exactly constant (``Sxx == 0``, no
    variance to regress against), or (for R^2 alone) if ``forward_return`` is exactly
    constant (``SS_tot == 0``, R^2 undefined -- the slope is still well-defined and
    returned in that case).
    """
    cape_v = np.asarray(cape_v, dtype=np.float64).reshape(-1)
    forward_return = np.asarray(forward_return, dtype=np.float64).reshape(-1)
    if cape_v.shape[0] != forward_return.shape[0]:
        raise ValueError(
            f"valuation_regression: shape mismatch {cape_v.shape} vs {forward_return.shape}"
        )
    n = cape_v.shape[0]
    if n < 3:
        return float("nan"), float("nan")
    xbar, ybar = float(np.mean(cape_v)), float(np.mean(forward_return))
    sxx = float(np.sum((cape_v - xbar) ** 2))
    if sxx == 0.0:
        return float("nan"), float("nan")
    sxy = float(np.sum((cape_v - xbar) * (forward_return - ybar)))
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    fitted = intercept + slope * cape_v
    ss_res = float(np.sum((forward_return - fitted) ** 2))
    ss_tot = float(np.sum((forward_return - ybar) ** 2))
    if ss_tot == 0.0:
        return slope, float("nan")
    r2 = 1.0 - ss_res / ss_tot
    return slope, r2


# ---- ergodicity gap (registered tier "10yr") -----------------------------------
#
# DN-1.1 Sec.II.6's 10yr row names this metric "ergodicity (LONG-PATH VS ENSEMBLE
# stats)", and that is what it now is: the discrepancy between the TIME average of one
# long single realization and the CROSS-SECTIONAL average of an ensemble of short paths,
# expressed in units of the process's own pooled dispersion.
#
#     ergodicity_gap = |mean(long_path) - mean(ensemble)| / std(ensemble, pooled)
#
# Under ergodicity the two averages converge to the same population mean, so the gap
# goes to 0 as the long path lengthens, whatever the process's persistence. Under
# genuine non-ergodicity -- the ensemble mixing several long-run regimes while any one
# realization stays inside one of them forever -- the time average never reaches the
# ensemble average and the gap stays bounded away from 0. Scope, stated: this compares
# FIRST moments only; a second-moment (time-average vs ensemble variance) version would
# be a second registered name and is deliberately not registered.
#
# WHAT THIS REPLACES, AND WHY (WP2.2 Task 3 fix pass 1, Critical 2). The first version
# compared the cross-sectional dispersion of per-path time-averages against
# Var(pooled)/months, "what an iid-within-path null predicts". Two independent defects,
# either alone disqualifying:
#   (a) IT WAS ALREADY REGISTERED UNDER ANOTHER NAME. At the production path length,
#       ah.eval.metrics.horizon's pooled variance_ratio at k = months yields exactly one
#       non-overlapping sum per path, so VR_120 = Var(path_means)/(Var(pooled)/months)
#       -- and the old gap was |VR_120 - 1|. Two registered names, two sealed bands, one
#       quantity. This file already refused exactly that when it dropped
#       ``agg_gaussianity`` horizon 1 for being bit-identical to ``excess_kurtosis``.
#   (b) THE NULL WAS INDEFENSIBLE FOR THE FACTORS IT WAS REGISTERED ON. Var(pooled)/
#       months is the variance of a mean of INDEPENDENT observations; for a stationary
#       AR(1) with phi = 0.9 the true variance of a 120-month mean is ~19x larger, so a
#       perfectly correct, perfectly ergodic generator of a persistent factor
#       (``ust_10y``, ``cpi``, ``hy_spread``) read as gap ~ 18: catastrophically
#       non-ergodic. The definition above has no iid null in it at all, so persistence
#       is simply not an input to the answer.
#
# NO HISTORICAL ANALOG EITHER WAY: history is one realization and there is no historical
# ENSEMBLE to compare it against, so the reference-side registration is
# :func:`_ergodicity_gap_reference_stub` (always NaN, and registered
# ``has_historical_analog=False`` so no resampling is performed at all). The metric is
# also STRUCTURALLY UNAVAILABLE on the ensemble side today -- see
# ``ah.eval.metrics.horizon`` and ``governance/retrofit-register.md`` RFR-20:
# ``ah.eval.battery.run_battery`` is handed exactly one ``Ensemble`` of
# production-length paths and no long path, so there is nothing to put in the first
# argument. The estimator is built and tested here so it is ready the moment a
# generator emits one.
def ergodicity_gap(long_path: np.ndarray, ensemble_paths: np.ndarray) -> float:
    """``long_path``: one 1-D realization, ideally many times ``months`` long.
    ``ensemble_paths``: a ``(n_paths, months)`` slab of independent short paths.

    ``NaN`` if either side is too small to average (fewer than 2 long-path
    observations, fewer than 2 ensemble paths, fewer than 2 months) or if the
    ensemble's pooled standard deviation is exactly zero (a degenerate constant
    ensemble supplies no scale to express the discrepancy in).
    """
    long_path = np.asarray(long_path, dtype=np.float64)
    ensemble_paths = np.asarray(ensemble_paths, dtype=np.float64)
    if long_path.ndim != 1:
        raise ValueError(f"ergodicity_gap: long_path must be 1-D, got {long_path.shape}")
    if ensemble_paths.ndim != 2:
        raise ValueError(
            f"ergodicity_gap: expected a 2-D (n_paths, months) ensemble, got {ensemble_paths.shape}"
        )
    n_paths, months = ensemble_paths.shape
    if long_path.shape[0] < 2 or n_paths < 2 or months < 2:
        return float("nan")
    pooled = ensemble_paths.reshape(-1)
    scale = float(np.std(pooled, ddof=1))
    if scale == 0.0:
        return float("nan")
    return abs(float(np.mean(long_path)) - float(np.mean(pooled))) / scale


def _ergodicity_gap_reference_stub(x: np.ndarray) -> float:
    """Registered reference-side ``fn`` for ``ergodicity_gap`` -- always ``NaN``.

    A flat historical series has exactly one "path": ergodicity (long-path time-
    average vs ensemble cross-sectional average) is a property only assessable on a
    GENERATED ensemble of multiple paths, never on the single observed historical
    realization. Registering a stub here (rather than leaving the name unregistered)
    is what makes ``"<factor>.ergodicity_gap"`` sealable at all -- see this section's
    header note.
    """
    return float("nan")


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
#
# SCOPE OF THIS ARGUMENT (Minor 8, WP2.2 Task 2 fix pass 2). The seam-shrinkage
# argument above governs the number of BLOCKS a resample is built from, which only
# matters when a replicate is stitched together from more than one block. At
# production defaults (block_length=120, resample_length=ensemble.months <= 120 --
# see run_full_battery), ceil(resample_length / block_length) == 1: every replicate IS
# a single contiguous block, so there is no seam at all and the resample distribution
# is an ordinary subsampling distribution, not a moving-block one. That is statistically
# fine (a percentile band over single-block draws is still a valid band), but it means
# the (b-k)/b seam-shrinkage rule this constant is chosen to satisfy does not bind on
# the length-matched production path at all -- it governs only the UNMATCHED path
# (resample_length=None, replicates built from the full ~1100-month history, where
# multiple blocks per replicate is the normal case). A rule stated in this sealed file
# that the production path never exercises would otherwise look stronger than it is.
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
    # WP2.2 Task 3: the 1_5yr and 10yr horizon statistics (see the definitions above,
    # under "WP2.2 Task 3: the 1_5yr and 10yr horizon statistics").
    **{
        f"variance_ratio_{suffix}": RegisteredStat(fn=_variance_ratio_stat(k), tier="1_5yr")
        for k, suffix in VARIANCE_RATIO_HORIZONS
    },
    "mean_reversion_halflife": RegisteredStat(fn=mean_reversion_halflife, tier="1_5yr"),
    "drawdown_median_depth": RegisteredStat(fn=_drawdown_summary_depth, tier="1_5yr"),
    "drawdown_median_duration": RegisteredStat(fn=_drawdown_summary_duration, tier="1_5yr"),
    "drawdown_depth_duration_rank_corr": RegisteredStat(
        fn=_drawdown_summary_rank_corr, tier="1_5yr"
    ),
    # length_matched=False on both: a 120-month replicate holds exactly ONE decade
    # window, which is the degenerate Bernoulli band Critical 1 removed. See
    # RegisteredStat and lost_decade_frequency's section header.
    "lost_decade_frequency": RegisteredStat(
        fn=lost_decade_frequency, tier="10yr", length_matched=False
    ),
    "long_inflation_era_frequency": RegisteredStat(
        fn=long_inflation_era_frequency, tier="10yr", length_matched=False
    ),
    # No historical analog -- see _ergodicity_gap_reference_stub's docstring.
    "ergodicity_gap": RegisteredStat(
        fn=_ergodicity_gap_reference_stub, tier="10yr", has_historical_analog=False
    ),
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


# WP2.2 Task 4 -- empirical tail-dependence coefficients (ah.eval.metrics.tails' item
# 4). Live HERE, not in ah.eval.metrics.tails, for the identical structural reason
# every other CROSS_BLOCK_STATS estimator does (see the module docstring): a
# statistic defined only in a metric suite could never carry a sealed threshold, and
# registering it here gives it a real computed train+validation point + block-
# bootstrap band for free, via the existing `_cross_block_reference` machinery -- no
# new plumbing needed. `ah.eval.metrics.tails` imports and re-exports these two names
# under its own module (the SAME function objects, not wrappers), exactly as
# `ah.eval.metrics.monthly` already does for `hill_tail_index`/`corr_matrix_distance`;
# a direct import from `ah.eval.metrics.tails` into this module would cycle
# (tails -> battery -> reference), so the direction must run this way.
TAIL_DEPENDENCE_TAIL_FRACTION = 0.05
# Matches Hill's own 5% tail-fraction convention (HILL_TAIL_FRACTIONS in
# ah.eval.metrics.monthly) rather than an independently chosen number -- the same "top
# ~5%" reading of "the tail" applies to a bivariate joint-exceedance estimator as it
# does to a univariate one, and reusing the constant means one amendment moves both if
# it ever does.
TAIL_DEPENDENCE_MIN_TAIL_OBS = 10
# The same shape of floor VARIANCE_RATIO_MIN_SUMS/DRAWDOWN_MIN_EPISODES impose: below
# this many observations actually IN the tail (n * fraction), the joint-exceedance
# fraction is computed from a literal handful of points and reports NaN rather than a
# number with no information content.


def _pseudo_observations(x: np.ndarray) -> np.ndarray:
    """Rank-based pseudo-observations in ``(0, 1)``: ``rank(x) / (n + 1)``.

    The standard empirical-copula transform to uniform margins (Frahm, Junker & Schmidt
    2005); ``/(n+1)`` rather than ``/n`` keeps every value strictly inside ``(0, 1)`` (no
    boundary value at exactly 1.0), and ties are averaged via :func:`_rank` -- the same
    ranking convention :func:`spearman_rank_correlation` already uses, not a second one.
    """
    return _rank(x) / (x.shape[0] + 1.0)


def _tail_dependence(a: np.ndarray, b: np.ndarray, *, upper: bool) -> float:
    """Nonparametric tail-dependence coefficient estimator, upper or lower tail.

    With pseudo-observations ``U = rank(a)/(n+1)``, ``V = rank(b)/(n+1)`` and
    ``fraction = TAIL_DEPENDENCE_TAIL_FRACTION`` (0.05):

    - upper: ``u = 1 - fraction``; ``lambda_U = mean(1{U > u AND V > u}) / fraction``.
    - lower: ``u = fraction``; ``lambda_L = mean(1{U <= u AND V <= u}) / fraction``.

    Both estimate ``P(other in its tail | one in its tail)`` at threshold ``u``: under
    independence this converges to ``fraction`` -> 0 as ``fraction`` shrinks (so a small,
    stated, nonzero value at a finite ``fraction`` is the expected, honest outcome, not a
    defect); for a comonotone pair (``a == b`` exactly) it is exactly 1.0 at every
    ``fraction``, since both legs' rank exceedances coincide perfectly. ``NaN`` if ``a``
    and ``b`` are not the same length, or if the aligned sample has fewer than
    :data:`TAIL_DEPENDENCE_MIN_TAIL_OBS` observations actually inside the tail
    (``n * fraction``).
    """
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    if a.shape[0] != b.shape[0]:
        return float("nan")
    n = a.shape[0]
    fraction = TAIL_DEPENDENCE_TAIL_FRACTION
    if n * fraction < TAIL_DEPENDENCE_MIN_TAIL_OBS:
        return float("nan")
    u_a = _pseudo_observations(a)
    u_b = _pseudo_observations(b)
    if upper:
        threshold = 1.0 - fraction
        joint = np.mean((u_a > threshold) & (u_b > threshold))
    else:
        threshold = fraction
        joint = np.mean((u_a <= threshold) & (u_b <= threshold))
    return float(joint) / fraction


def tail_dependence_lower(a: np.ndarray, b: np.ndarray) -> float:
    """Empirical lower-tail dependence coefficient -- see :func:`_tail_dependence`."""
    return _tail_dependence(a, b, upper=False)


def tail_dependence_upper(a: np.ndarray, b: np.ndarray) -> float:
    """Empirical upper-tail dependence coefficient -- see :func:`_tail_dependence`."""
    return _tail_dependence(a, b, upper=True)


CROSS_BLOCK_STATS: dict[str, RegisteredCrossStat] = {
    "correlation": RegisteredCrossStat(fn=_correlation, tier="monthly"),
    "crisis_corr_lift": RegisteredCrossStat(fn=_crisis_corr_lift, tier="monthly"),
    "tail_dependence_lower": RegisteredCrossStat(fn=tail_dependence_lower, tier="monthly"),
    "tail_dependence_upper": RegisteredCrossStat(fn=tail_dependence_upper, tier="monthly"),
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

    WP2.2 Task 3 adds four more no-``fn`` entries for the same reason, but for two
    DIFFERENT underlying causes, both stated where each is registered below and in
    ``ah.eval.metrics.horizon``'s module docstring: ``regime_duration_{mean,p50,p90}``
    (the Step-1 regime ruleset needs ``usrec``/``growth_yoy``, neither of which has a
    factor mapping in ``factors.yaml`` at all -- not a per-ensemble absent-factor case,
    a structural one) and ``ten_year_return_vs_valuation_{slope,r2}`` (no valuation/
    CAPE factor exists in ``factors.yaml`` either). Both are honestly always NaN on any
    ensemble today; see ``governance/retrofit-register.md``.
    """

    tier: str


PANEL_STATS: dict[str, RegisteredPanelStat] = {
    "cross_block_corr_matrix_distance": RegisteredPanelStat(tier="monthly"),
    # WP2.2 Task 3 -- structural gaps, always NaN on any ensemble today (see this
    # class's docstring and ah.eval.metrics.horizon's module docstring).
    "regime_duration_mean": RegisteredPanelStat(tier="1_5yr"),
    "regime_duration_p50": RegisteredPanelStat(tier="1_5yr"),
    "regime_duration_p90": RegisteredPanelStat(tier="1_5yr"),
    "ten_year_return_vs_valuation_slope": RegisteredPanelStat(tier="10yr"),
    "ten_year_return_vs_valuation_r2": RegisteredPanelStat(tier="10yr"),
    # WP2.2 Task 4 -- ah.eval.metrics.utility's three whole-panel metrics (a
    # real-vs-generated comparison over the whole active factor panel, not a single
    # factor or pair -- see that module's docstring for why a per-factor scope was
    # rejected). No `fn`/band for the identical reason `cross_block_corr_matrix_distance`
    # has none: these compare a GENERATED ensemble against real data directly, so there
    # is no single-argument historical point estimate to bootstrap.
    "discriminative_score": RegisteredPanelStat(tier="monthly"),
    "predictive_score": RegisteredPanelStat(tier="monthly"),
    "tstr_degradation": RegisteredPanelStat(tier="monthly"),
}


# --------------------------------------------------------------------------- #
# WP2.2 Task 4 -- D4-strategy-level tail-fidelity statistics.
#
# A fourth, small registry, structurally distinct from the three above because its
# axis is neither a factor, a factor pair, nor the whole panel: it is one of the five
# SEALED D4 BENCHMARK STRATEGIES (`ah.strategies.load_d4_strategies`), which are named
# data in `pre-registration.yaml`, not entries of `ah.factors.FactorManifest`. This
# module does not import `ah.strategies` (unnecessary -- see below) and the strategy
# IDs are validated against the live D4 set only by `ah.eval.prereg` (which already
# imports `ah.strategies` to interpret the sealed D4 definitions -- see that module's
# docstring, "What the seal covers").
#
# Threshold keys are `"<strategy_id>.<stat>"` (`ah.eval.prereg`'s new
# `thresholds.strategies` section, a flat mapping mirroring `thresholds.panel`'s shape
# but with the dotted key `PANEL_STATS`'s own key-shape rule forbids -- see
# `ah.eval.prereg._check_strategy_threshold_key`).
#
# Like `PANEL_STATS`, every entry here carries no `fn`: `var_95`/`es_95`/`var_99`/
# `es_99` are the GENERATED ensemble's own realized historical VaR/ES (a descriptive
# report, not a value with a train+val band -- see `ah.eval.metrics.tails.var_es`, WP2.1b).
# `elicitability_score`/`kupiec_pof_*`/`christoffersen_*` are backtests of the GENERATED
# ensemble's exceedances against the HISTORICAL (train+validation) D4 strategy return
# series' own VaR/ES -- an out-of-sample-style comparison, not a value with a symmetric
# historical band of its own; a test statistic or a scoring-rule value is judged by an
# absolute bound (a critical value, a p-value floor), never by "does it look like
# history's own value of the same statistic" (there is no such thing: history has no
# ensemble of its own exceedance sequences to compare against). All computation lives in
# `ah.eval.metrics.tails.build_tails_suite`, which reads `ReferenceStats.historical_series`
# (never a fresh catalog read) to obtain the D4 strategies' historical return series.
@dataclass(frozen=True)
class RegisteredStrategyStat:
    """A D4-strategy-level statistic: a name and its DN-1.1 Sec.II.6 horizon tier, no
    function -- see the section header above for why every entry here has none."""

    tier: str


STRATEGY_STATS: dict[str, RegisteredStrategyStat] = {
    "var_95": RegisteredStrategyStat(tier="monthly"),
    "es_95": RegisteredStrategyStat(tier="monthly"),
    "var_99": RegisteredStrategyStat(tier="monthly"),
    "es_99": RegisteredStrategyStat(tier="monthly"),
    "elicitability_score": RegisteredStrategyStat(tier="monthly"),
    "kupiec_pof_stat": RegisteredStrategyStat(tier="monthly"),
    "kupiec_pof_pvalue": RegisteredStrategyStat(tier="monthly"),
    "christoffersen_independence_stat": RegisteredStrategyStat(tier="monthly"),
    "christoffersen_independence_pvalue": RegisteredStrategyStat(tier="monthly"),
    "christoffersen_conditional_coverage_stat": RegisteredStrategyStat(tier="monthly"),
    "christoffersen_conditional_coverage_pvalue": RegisteredStrategyStat(tier="monthly"),
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

    if block_length >= t:
        # Minor 5 (WP2.2 Task 2 fix pass 2). eff_block_length = min(block_length, t)
        # would be t, so max_start = t - t = 0: every block-start draw is FORCED to 0,
        # there is no randomness left, and every replicate is the identical
        # whole-sample block -- a zero-width band (lo == hi) that fails nearly any
        # threshold with no warning at all. Not reachable at today's 120-month paths
        # and 1996+ shortest series (t comfortably exceeds block_length everywhere in
        # production), but reachable the moment a judged path length exceeds a
        # short-history factor's own history. Raised here rather than silently sealing
        # a degenerate band.
        raise ValueError(
            f"_draw_moving_block_indices{_ctx(context)}: block_length ({block_length}) "
            f">= panel length ({t}) leaves no block-start freedom -- every replicate "
            f"would be the identical whole-sample block, producing a zero-width band "
            f"with no warning. Use a block_length < panel length, or treat this "
            f"factor's short history as a named limitation rather than silently "
            f"sealing a degenerate band."
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
        # Recorded, not acted on: `np.percentile` above is deliberately NOT NaN-robust
        # (RFR-19, a decision owned by WP2.3 because it changes every existing band's
        # semantics), so this is how a reader of the sealed artifact sees that a NaN
        # band came from a handful of undefined replicates rather than from an
        # uncomputable statistic. See StatBand.n_valid_resamples.
        n_valid_resamples=int(np.count_nonzero(~np.isnan(resample_stats))),
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
    docstring) and **at most two** moving-block resample draws, each drawn once per
    factor and reused across every stat that needs it
    (:func:`_draw_moving_block_indices`), never redrawn per ``(factor, stat)``:

    - the length-matched draw at ``resample_length`` (the ordinary case, every
      ``RegisteredStat`` with ``length_matched=True``); and
    - a full-sample-length draw, made only if some registered stat declares
      ``length_matched=False`` and a ``resample_length`` was actually requested -- see
      :class:`RegisteredStat` for why the decade-frequency statistics need it.

    A stat with ``has_historical_analog=False`` is not resampled at all; its band is
    constructed directly as NaN (running 1000 resamples of a function that returns a
    constant NaN produced the same band at 1000x the cost).
    """
    stats: dict[str, StatBand] = {}
    needs_unmatched = resample_length is not None and any(
        not registered.length_matched
        for registered in SINGLE_FACTOR_STATS.values()
        if registered.has_historical_analog
    )
    for factor in block_factors:
        panel = series_by_factor[factor].to_numpy(dtype=np.float64).reshape(-1, 1)
        t = panel.shape[0]
        indices_by_length: dict[int | None, np.ndarray] = {
            resample_length: _draw_moving_block_indices(
                t,
                seed=seed,
                n_resamples=n_resamples,
                block_length=block_length,
                context=f"block={block} factor={factor}",
                resample_length=resample_length,
            )
        }
        if needs_unmatched:
            indices_by_length[None] = _draw_moving_block_indices(
                t,
                seed=seed,
                n_resamples=n_resamples,
                block_length=block_length,
                context=f"block={block} factor={factor} (full-length replicates)",
                resample_length=None,
            )
        for stat_name, registered in SINGLE_FACTOR_STATS.items():
            if not registered.has_historical_analog:
                stats[f"{factor}.{stat_name}"] = StatBand(
                    point=float("nan"),
                    lo=float("nan"),
                    hi=float("nan"),
                    n_resamples=n_resamples,
                    level=level,
                    tier=registered.tier,
                    resample_length=resample_length,
                    n_valid_resamples=0,
                )
                continue

            def sample_fn(
                arr: np.ndarray, _fn: Callable[[np.ndarray], float] = registered.fn
            ) -> float:
                return _fn(arr[:, 0])

            stat_resample_length = resample_length if registered.length_matched else None
            band = block_bootstrap_band(
                sample_fn,
                panel,
                seed=seed,
                n_resamples=n_resamples,
                level=level,
                block_length=block_length,
                tier=registered.tier,
                context=f"block={block} factor={factor} stat={stat_name}",
                resample_indices=indices_by_length[stat_resample_length],
                resample_length=stat_resample_length,
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
        historical_series=MappingProxyType(dict(series_by_factor)),
    )
