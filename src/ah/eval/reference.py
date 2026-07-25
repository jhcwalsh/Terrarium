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

Data alignment and the ``commodities`` gap
--------------------------------------------
:func:`compute_reference` reads every active factor via
``access.train_val(series_id_for(factor))`` and aligns all of them on their common
(inner-joined) date index before computing anything, so every statistic in the same
run sees the same time axis. A factor the reader has no data for (as of this task, no
Step-1 series sources ``commodities`` -- see ``factors.yaml``'s header note) is *not*
an error and does not silently produce ``NaN``: it is skipped and its name recorded in
``ReferenceStats.missing_factors``. Concretely, a factor is "missing" when
``access.train_val`` either raises ``KeyError`` (no such series) or returns an empty
frame (no rows in train+validation).

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

    ``stats`` is keyed ``"<factor>.<stat_name>"``, e.g. ``"equity_mkt.mean"``.
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
    ``"equity_mkt~ust_10y.correlation"``.
    """

    pair: tuple[str, str]
    stats: Mapping[str, StatBand]


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
        object keys); everything else maps through directly.
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


CROSS_BLOCK_STATS: dict[str, Callable[[np.ndarray, np.ndarray], float]] = {
    "correlation": _correlation,
    "crisis_corr_lift": _crisis_corr_lift,
}


# --------------------------------------------------------------------------- #
# moving-block bootstrap
# --------------------------------------------------------------------------- #


def block_bootstrap_band(
    sample_fn: Callable[[np.ndarray], float],
    panel: np.ndarray,
    *,
    seed: int,
    n_resamples: int,
    level: float,
    block_length: int,
    tier: str = "monthly",
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

    Determinism: all randomness flows from ``numpy.random.Generator(PCG64(seed))``
    constructed fresh here from the given ``seed`` -- no global RNG, no ``random``.
    The same ``seed`` (with the same ``panel``, ``n_resamples``, ``level`` and
    ``block_length``) gives a bit-identical :class:`StatBand`.
    """
    panel = np.asarray(panel, dtype=np.float64)
    if panel.ndim != 2:
        raise ValueError(
            f"block_bootstrap_band: expected a 2-D (T, k) panel, got shape {panel.shape}"
        )
    t = panel.shape[0]
    if t == 0:
        raise ValueError("block_bootstrap_band: panel has zero rows")
    if not 0.0 < level < 1.0:
        raise ValueError(f"block_bootstrap_band: level must be in (0, 1), got {level}")
    if n_resamples < 1:
        raise ValueError(f"block_bootstrap_band: n_resamples must be >= 1, got {n_resamples}")

    point = float(sample_fn(panel))

    eff_block_length = max(1, min(block_length, t))
    max_start = t - eff_block_length
    n_blocks_needed = -(-t // eff_block_length)  # ceil division

    rng = np.random.Generator(np.random.PCG64(seed))
    resample_stats = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        starts = rng.integers(0, max_start + 1, size=n_blocks_needed)
        idx = np.concatenate([np.arange(s, s + eff_block_length) for s in starts])[:t]
        resample_stats[i] = sample_fn(panel[idx])

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
) -> pd.DataFrame | None:
    """``access.train_val`` for one factor, or ``None`` if the series has no data.

    "No data" covers both an unknown series id (``KeyError`` from the underlying
    reader, propagated through :meth:`~ah.splits.DataAccess.train_val`) and a known
    series id with zero rows in train+validation -- both are the ``commodities``-style
    gap this module must not raise or NaN on.
    """
    series_id = series_id_for(factor)
    try:
        df = access.train_val(series_id)
    except KeyError:
        return None
    if df.empty:
        return None
    return df


def _aligned_panel(
    access: DataAccess, factors: tuple[str, ...], series_id_for: Callable[[str], str]
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Read every factor via train_val, inner-join on date, return (panel, missing).

    The returned panel's columns are exactly the factors that had data, in the same
    relative order as ``factors``; the second element lists the ones that did not.
    """
    per_factor: dict[str, pd.Series] = {}
    missing: list[str] = []
    for factor in factors:
        df = _read_train_val(access, factor, series_id_for)
        if df is None:
            missing.append(factor)
            continue
        per_factor[factor] = df.set_index("date")["value"]

    if not per_factor:
        return pd.DataFrame(), tuple(missing)

    panel = pd.concat(per_factor, axis=1, join="inner").sort_index()
    present = tuple(f for f in factors if f in panel.columns)
    return panel[list(present)], tuple(missing)


def _block_reference(
    block: str,
    block_factors: list[str],
    panel: pd.DataFrame,
    *,
    seed: int,
    n_resamples: int,
    level: float,
    block_length: int,
) -> BlockReference:
    if not block_factors:
        return BlockReference(block=block, stats=MappingProxyType({}))
    block_panel = panel[block_factors].to_numpy(dtype=np.float64)
    stats: dict[str, StatBand] = {}
    for stat_name, registered in SINGLE_FACTOR_STATS.items():
        for j, factor in enumerate(block_factors):

            def sample_fn(
                arr: np.ndarray, _j: int = j, _fn: Callable[[np.ndarray], float] = registered.fn
            ) -> float:
                return _fn(arr[:, _j])

            band = block_bootstrap_band(
                sample_fn,
                block_panel,
                seed=seed,
                n_resamples=n_resamples,
                level=level,
                block_length=block_length,
                tier=registered.tier,
            )
            stats[f"{factor}.{stat_name}"] = band
    return BlockReference(block=block, stats=MappingProxyType(stats))


def _cross_block_reference(
    pair: tuple[str, str],
    factors_a: list[str],
    factors_b: list[str],
    panel: pd.DataFrame,
    *,
    seed: int,
    n_resamples: int,
    level: float,
    block_length: int,
) -> CrossBlockReference:
    stats: dict[str, StatBand] = {}
    for fa in factors_a:
        for fb in factors_b:
            pair_panel = panel[[fa, fb]].to_numpy(dtype=np.float64)
            for stat_name, fn in CROSS_BLOCK_STATS.items():

                def sample_fn(
                    arr: np.ndarray, _fn: Callable[[np.ndarray, np.ndarray], float] = fn
                ) -> float:
                    return _fn(arr[:, 0], arr[:, 1])

                band = block_bootstrap_band(
                    sample_fn,
                    pair_panel,
                    seed=seed,
                    n_resamples=n_resamples,
                    level=level,
                    block_length=block_length,
                    tier="monthly",
                )
                stats[f"{fa}~{fb}.{stat_name}"] = band
    return CrossBlockReference(pair=pair, stats=MappingProxyType(stats))


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
    ``access.train_val`` (never ``access.frame(..., "holdout", ...)``, and this module
    holds no :class:`~ah.splits.FinalEvaluationToken` with which it even could), aligns
    them on their common date index, then computes:

    - Every :data:`SINGLE_FACTOR_STATS` entry for every present factor, per active
      block (:class:`BlockReference`, one per ``manifest.active_blocks`` entry -- every
      active block gets an entry even if every one of its factors turned out to be
      missing, so a caller can always find the block by key).
    - Every :data:`CROSS_BLOCK_STATS` entry for every present factor pair drawn from
      each ``manifest.cross_block_pairs()`` block pair (:class:`CrossBlockReference`,
      one per pair, with the pair recorded on the object).

    Factors belonging to an inactive block (declared in ``manifest.blocks`` but absent
    from ``manifest.active_blocks``) are never read: ``manifest.active_factors()``
    already excludes them, and this function does not fall back to
    ``manifest.blocks`` directly for iteration.

    A single ``seed`` drives every block-bootstrap draw in this call (via
    :func:`block_bootstrap_band`, constructed fresh from ``seed`` each time): the
    same ``seed`` against the same data gives bit-identical bands. Passing the same
    ``block_length`` and the shared per-block panel to every statistic in that block
    means the resampled row positions (not their content) are identical across a
    block's stats for a given ``seed`` -- the "blocks are drawn jointly across
    factors" property the moving-block bootstrap is required to have.
    """
    active_factors = manifest.active_factors()
    panel, missing = _aligned_panel(access, active_factors, series_id_for)

    blocks: dict[str, BlockReference] = {}
    for block in manifest.active_blocks:
        block_factors = [f for f in manifest.blocks[block] if f in panel.columns]
        blocks[block] = _block_reference(
            block,
            block_factors,
            panel,
            seed=seed,
            n_resamples=n_resamples,
            level=level,
            block_length=block_length,
        )

    cross_blocks: dict[tuple[str, str], CrossBlockReference] = {}
    for pair in manifest.cross_block_pairs():
        block_a, block_b = pair
        factors_a = [f for f in manifest.blocks[block_a] if f in panel.columns]
        factors_b = [f for f in manifest.blocks[block_b] if f in panel.columns]
        cross_blocks[pair] = _cross_block_reference(
            pair,
            factors_a,
            factors_b,
            panel,
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
