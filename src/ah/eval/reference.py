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

Scope of this task (WP2.1b Task 3)
-----------------------------------
This is the block-aware **skeleton**: a small, honest single-factor statistic set
(``mean``, ``std``, ``skew``, ``excess_kurtosis``, ``acf_1``, ``acf_abs_1``) plus two
cross-block joint statistics (``correlation``, ``crisis_corr_lift``), each registered
in a module-level table so later work adds statistics by registering, not by editing
:func:`compute_reference`. STEP2-GENERATOR-PLAN Sec.WP2.2 owns the eight full metric
suites this registry will grow into: ``monthly``, ``horizon``, ``tails``, ``utility``,
``memorization``, ``economics``, ``conditional``, ``calibration``
(``src/ah/eval/metrics/{monthly,horizon,tails,utility,memorization,economics,
conditional,calibration}.py``). Those suites are intentionally not stubbed here.

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

The ``commodities`` gap
-------------------------
No Step-1 series sources ``commodities`` yet (see ``factors.yaml``'s header note). A
factor the reader has no data for is *not* an error and does not silently produce
``NaN``: it is skipped and its name recorded in ``ReferenceStats.missing_factors``.
Concretely, a factor is "missing" when ``access.train_val`` either raises ``KeyError``
(no such series) or returns an empty frame (no rows in train+validation). A frame that
*is* returned but is malformed (missing the ``date``/``value`` columns the rest of this
module assumes) is a different failure mode -- a bug, not a data gap -- and raises a
named :class:`ReferenceComputationError` identifying the offending factor and series id
rather than propagating an anonymous ``KeyError`` from deep inside pandas.

The factor-id -> catalog-series-id mapping does not exist anywhere in the repo yet
(that mapping is WP2.2/Step-2R scope). ``compute_reference`` therefore takes a
``series_id_for`` callable, defaulting to identity, so tests can inject a mapping and
WP2.2 can supply the real one later without changing this module's signature.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd

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
    """

    point: float
    lo: float
    hi: float
    n_resamples: int
    level: float
    tier: str


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
class ReferenceStats:
    """The complete train+validation reference: every block, plus every cross-block pair.

    ``missing_factors`` lists active factors for which no data was available (see the
    module docstring's ``commodities`` note); they contribute no entries to ``blocks``
    or ``cross_blocks``.
    """

    blocks: Mapping[str, BlockReference]
    cross_blocks: Mapping[tuple[str, str], CrossBlockReference]
    active_blocks: tuple[str, ...]
    vintage_id: str
    n_resamples: int
    seed: int
    missing_factors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable rendering (for the battery report and Task 4's threshold authoring).

        Cross-block pair keys render as ``"block_a|block_b"`` (tuples cannot be JSON
        object keys); everything else maps through directly. ``zero_overlap_pairs`` is
        included only for pairs that actually have one (keeping the common-case JSON
        uncluttered).
        """

        def _stats_dict(stats: Mapping[str, StatBand]) -> dict[str, dict[str, float | int | str]]:
            return {
                name: {
                    "point": band.point,
                    "lo": band.lo,
                    "hi": band.hi,
                    "n_resamples": band.n_resamples,
                    "level": band.level,
                    "tier": band.tier,
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


def _acf_1(x: np.ndarray) -> float:
    return _acf1(x)


def _acf_abs_1(x: np.ndarray) -> float:
    """Lag-1 autocorrelation of ``|x - mean(x)|`` -- the volatility-clustering statistic."""
    x = np.asarray(x, dtype=np.float64)
    return _acf1(np.abs(x - np.mean(x)))


SINGLE_FACTOR_STATS: dict[str, RegisteredStat] = {
    "mean": RegisteredStat(fn=_mean, tier="monthly"),
    "std": RegisteredStat(fn=_std, tier="monthly"),
    "skew": RegisteredStat(fn=_skew, tier="monthly"),
    "excess_kurtosis": RegisteredStat(fn=_excess_kurtosis, tier="monthly"),
    "acf_1": RegisteredStat(fn=_acf_1, tier="monthly"),
    "acf_abs_1": RegisteredStat(fn=_acf_abs_1, tier="monthly"),
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
# moving-block bootstrap
# --------------------------------------------------------------------------- #


def _ctx(context: str) -> str:
    return f" [{context}]" if context else ""


def _draw_moving_block_indices(
    t: int, *, seed: int, n_resamples: int, block_length: int, context: str = ""
) -> np.ndarray:
    """Precompute ``n_resamples`` moving-block row-index draws for a ``t``-row panel.

    Returns an ``(n_resamples, t)`` int array; row ``i`` is the row-index sequence for
    resample ``i``. Extracted from :func:`block_bootstrap_band` so a caller that needs
    to evaluate several statistics over the *same* panel can draw once and reuse the
    same indices explicitly (see :func:`block_bootstrap_band`'s ``resample_indices``
    parameter) instead of relying on separate calls with matching ``(seed, t,
    block_length, n_resamples)`` happening to produce the same draws as an emergent
    side effect of content-independent RNG parameters.

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

    eff_block_length = min(block_length, t)
    max_start = t - eff_block_length
    n_blocks_needed = -(-t // eff_block_length)  # ceil division

    rng = np.random.Generator(np.random.PCG64(seed))
    indices = np.empty((n_resamples, t), dtype=np.int64)
    for i in range(n_resamples):
        starts = rng.integers(0, max_start + 1, size=n_blocks_needed)
        row_idx = np.concatenate([np.arange(s, s + eff_block_length) for s in starts])[:t]
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

    ``resample_indices``, if given, must be the ``(n_resamples, T)`` output of
    :func:`_draw_moving_block_indices` for this exact ``T`` -- pass the *same* array to
    every statistic sharing a panel to make the "these stats saw the same resample"
    property explicit rather than an accident of matching parameters. If omitted, the
    indices are drawn fresh from ``seed`` (still fully deterministic on its own).

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

    point = float(sample_fn(panel))

    if resample_indices is None:
        resample_indices = _draw_moving_block_indices(
            t, seed=seed, n_resamples=n_resamples, block_length=block_length, context=context
        )
    elif resample_indices.shape != (n_resamples, t):
        raise ValueError(
            f"block_bootstrap_band{_ctx(context)}: resample_indices shape "
            f"{resample_indices.shape} does not match (n_resamples={n_resamples}, t={t})"
        )

    resample_stats = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        resample_stats[i] = sample_fn(panel[resample_indices[i]])

    alpha = (1.0 - level) / 2.0
    lo = float(np.percentile(resample_stats, 100.0 * alpha))
    hi = float(np.percentile(resample_stats, 100.0 * (1.0 - alpha)))
    return StatBand(point=point, lo=lo, hi=hi, n_resamples=n_resamples, level=level, tier=tier)


# --------------------------------------------------------------------------- #
# compute_reference
# --------------------------------------------------------------------------- #


def _identity(factor_id: str) -> str:
    return factor_id


def _read_train_val(
    access: DataAccess, factor: str, series_id_for: Callable[[str], str]
) -> pd.Series | None:
    """``access.train_val`` for one factor, as a date-indexed value series, or ``None``.

    ``None`` covers both an unknown series id (``KeyError`` from the underlying
    reader, propagated through :meth:`~ah.splits.DataAccess.train_val`) and a known
    series id with zero rows in train+validation -- both are the ``commodities``-style
    gap this module must not raise or NaN on. A frame that *is* non-empty but is
    missing the ``date``/``value`` columns is a different failure mode entirely (a bug,
    not a gap) and raises :class:`ReferenceComputationError` naming the factor and
    series id, rather than letting a bare ``KeyError`` propagate anonymously from
    ``df.set_index("date")["value"]``.
    """
    series_id = series_id_for(factor)
    try:
        df = access.train_val(series_id)
    except KeyError:
        return None
    if df.empty:
        return None
    missing_cols = {"date", "value"} - set(df.columns)
    if missing_cols:
        raise ReferenceComputationError(
            f"factor '{factor}' (series_id '{series_id}'): train_val frame is missing "
            f"required column(s) {sorted(missing_cols)}"
        )
    return df.set_index("date")["value"].sort_index()


def _read_all_factors(
    access: DataAccess, factors: tuple[str, ...], series_id_for: Callable[[str], str]
) -> tuple[dict[str, pd.Series], tuple[str, ...]]:
    """Read every factor's own train+validation series independently.

    No cross-factor alignment happens here -- each statistic aligns only what it
    needs (see the module docstring's "Data alignment" section). Returns
    ``(factor -> date-indexed value series, missing factor names)``, missing names in
    ``factors`` order.
    """
    series_by_factor: dict[str, pd.Series] = {}
    missing: list[str] = []
    for factor in factors:
        series = _read_train_val(access, factor, series_id_for)
        if series is None:
            missing.append(factor)
        else:
            series_by_factor[factor] = series
    return series_by_factor, tuple(missing)


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
    block_length: int = 24,
    series_id_for: Callable[[str], str] = _identity,
) -> ReferenceStats:
    """Compute train+validation reference statistics and bootstrap bands, per block.

    Reads every :meth:`FactorManifest.active_factors` factor through
    ``access.train_val(series_id_for(factor))`` (never ``access.frame(..., "holdout",
    ...)``, and this module holds no :class:`~ah.splits.FinalEvaluationToken` with
    which it even could), each independently -- see the module docstring's "Data
    alignment" section for why this function does not inner-join every active factor
    onto one shared date axis before computing anything. Then computes:

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
    """
    active_factors = manifest.active_factors()
    series_by_factor, missing = _read_all_factors(access, active_factors, series_id_for)

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
        )

    return ReferenceStats(
        blocks=MappingProxyType(blocks),
        cross_blocks=MappingProxyType(cross_blocks),
        active_blocks=manifest.active_blocks,
        vintage_id=vintage_id,
        n_resamples=n_resamples,
        seed=seed,
        missing_factors=missing,
    )
