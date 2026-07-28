"""WP2.8 data — overlapping L-month training blocks with frozen cb-v1 conditioning.

The training set (DN-1.1 §II.4): all overlapping L-month blocks of the campaign
factor panel, each with the conditioning vector the joinery will hand the
sampler at generation time. The c_b construction is NOT re-implemented: the
regime one-hot / s_t snapshot / h_t trailing summary / Δw increments are built
by :mod:`ah.gen.joinery.bridge`'s own helpers on a
:class:`~ah.gen.joinery.bridge.BlockConditioning`, so training and generation
see one code path behind the frozen ``cb-v1`` contract
(:func:`ah.gen.joinery.bridge.contract_fingerprint`).

Span honesty (recorded deviation from DN-1.1's "all overlapping L-blocks
1926-"): the maximal span on which every sealed ``bootstrap_v1.factor_set``
factor is simultaneously observed on the campaign vintage is the sealed
``block_draw_span`` 1990-01..2020-12 (binding factor ``equity_vol``) — the same
wall the sealed benchmark records. The training panel is therefore the
:class:`~ah.gen.bootstrap.BootstrapSource` panel, read through the sanctioned
surface when the source was built.

Δw for a historical block is read off monthly target curves built from the
historical year's ACTUAL annual aggregates (policy annual means, year-end log
CPI, cumulative annual log equity, year-end spread), interpolated exactly as
:func:`ah.gen.joinery.waypoints.monthly_targets` interpolates generated
waypoints — so the conditioning the model trains on has the same smooth-curve
shape it will be handed at generation time. h_t before month 12 of the panel
uses the ``SourceStats.h0_*`` fallback — part of the cb-v1 contract, and exactly
what the sampler sees for the first blocks of every generated decade.

Split hygiene (recorded decisions, both in the strict direction):

- Target curves are built PER SPLIT SEGMENT (train span; validation span), not
  over the whole panel: the policy curve's year-CENTER anchors would otherwise
  interpolate the first validation year's annual mean into the Δw conditioning
  of late-train blocks. Within a segment ``np.interp`` clamps beyond the last
  anchor, exactly as a decade's own curve clamps at the decade edge.
- The h_t fallback statistics for TRAINING conditioning are computed on the
  train segment only (the frozen contract's generation-time ``h0_*`` are
  train+validation — the sanctioned reference surface — but a training input
  must not embed validation data; the difference is three unconditional scalars
  and is measured small). Validation-fold blocks all start past month 12, so
  the fallback never fires for them.

Targets are the panel blocks in UNCONSTRAINED coordinates
(:mod:`ah.gen.blocks.constraints`); the cpi column is REBASED to the block start
(log level relative to month 0 of the block) because the bridge chains cpi at
block joins (``bridge.CHAINED_FACTORS``): a block contributes its within-block
inflation, never its absolute 1990s-vs-2010s price level, so the absolute level
must not be a learnable feature.

Standardization is TRAIN-ONLY (constants from blocks fully inside the sealed
``train`` split, recorded on the dataset; leakage test in the WP2.5 style).
Validation folds are BLOCK-AWARE: a block belongs to the fold containing its
start, and a block straddling any boundary (train/validation or fold/fold) is
dropped from both sides. Epochs are SUBSAMPLED for effective-sample honesty:
overlapping blocks are not independent, so an epoch draws ~n_months/L blocks
with no two starts closer than L; raw and effective counts are both recorded
and raw counts are never quoted as sample sizes.

Simulated-conditioning augmentation (considered, DECIDED AGAINST, recorded):
WP2.7 measured extrapolation share ~0.88 at generation time, so historical-only
conditioning trains for a regime the sampler rarely sees. Augmenting with
L1/L2-SIMULATED conditioning vectors would require pairing each simulated c
with a historical target block by nearest conditioning — constructing (c, x)
pairs from a joint distribution the data does not contain, and (with ~41
effective training blocks per epoch) mostly recycling the same few blocks under
far-off-support c, teaching the model that off-support conditioning maps to
in-support blocks — precisely the quiet failure the support monitor exists to
flag. Instead the training loop offers conditioning-noise augmentation
(Gaussian jitter on the standardized continuous c components, train-time only;
``cond_noise_std`` searched within the sealed 40-trial budget), and the
off-support behaviour is MEASURED in this WP's acceptance rather than papered
over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ah.gen.blocks import constraints as ct
from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.simulate import ClimateArtifact
from ah.gen.joinery import bridge
from ah.gen.joinery import waypoints as wp
from ah.gen.joinery.waypoints import JoineryError, MonthlyTargets, SourceStats
from ah.gen.regimes.semimarkov import REGIME_LABELS
from ah.splits import VALIDATION

__all__ = [
    "BlockDataset",
    "Standardization",
    "build_dataset",
    "epoch_starts",
    "historical_monthly_targets",
]

_LABEL_INDEX = {label: i for i, label in enumerate(REGIME_LABELS)}
_STD_FLOOR = 1e-8  # a degenerate coordinate stays ~0 rather than exploding


def historical_monthly_targets(
    source: BootstrapSource, lo: int = 0, hi: int | None = None
) -> MonthlyTargets:
    """Monthly target curves from the panel's ACTUAL annual aggregates.

    Anchor conventions mirror :func:`ah.gen.joinery.waypoints.monthly_targets`
    exactly: policy interpolated through year-center anchors of the annual MEAN;
    log CPI through year-end anchors relative to month 0; cumulative log equity
    through year-end anchors with a (-1, 0) start anchor; spread through
    year-end anchors of the year-end level. ``[lo, hi)`` restricts the curves to
    one split segment (month coordinates local to the segment) — see the module
    docstring's split-hygiene note.
    """
    hi = source.n_rows if hi is None else int(hi)
    if not 0 <= lo < hi <= source.n_rows:
        raise JoineryError(f"bad segment [{lo}, {hi}) for a {source.n_rows}-month panel")
    months = hi - lo
    spans = wp.year_spans(months)
    names = list(source.factor_names)

    def col(name: str) -> np.ndarray:
        return source.values[lo:hi, names.index(name)]

    policy = col("policy_rate")
    cpi = col("cpi")
    equity = col("equity_mkt")
    spread = col("ig_spread")
    if np.any(cpi <= 0.0):
        raise JoineryError("cpi levels must be positive to build historical targets")
    log_cpi = np.log(cpi)
    cum_eq = np.concatenate(([0.0], np.cumsum(np.log1p(equity))))  # cum_eq[t] = first t months

    m = np.arange(months, dtype=np.float64)
    centers = np.array([(s.start + s.stop - 1) / 2.0 for s in spans])
    ends = np.array([float(s.stop - 1) for s in spans])
    end_idx = np.array([s.stop - 1 for s in spans], dtype=np.int64)

    policy_curve = np.interp(m, centers, np.array([float(policy[s].mean()) for s in spans]))
    log_cpi_curve = np.interp(
        m,
        np.concatenate(([0.0], ends)),
        np.concatenate(([0.0], log_cpi[end_idx] - log_cpi[0])),
    )
    equity_curve = np.interp(
        m, np.concatenate(([-1.0], ends)), np.concatenate(([0.0], cum_eq[end_idx + 1]))
    )
    spread_curve = np.interp(m, ends, spread[end_idx])
    return MonthlyTargets(
        policy_pct=policy_curve,
        log_cpi=log_cpi_curve,
        equity_cum_log=equity_curve,
        spread_center_pct=spread_curve,
    )


@dataclass(frozen=True)
class Standardization:
    """Train-only standardization constants, recorded with every checkpoint.

    ``x_*`` are per-factor over training-block cells in unconstrained
    coordinates (cpi rebased); ``c_*`` are over the 12 CONTINUOUS c_b components
    of training blocks (the one-hot part is never standardized).
    """

    x_mean: np.ndarray  # (n_factors,)
    x_std: np.ndarray  # (n_factors,)
    c_mean: np.ndarray  # (12,)
    c_std: np.ndarray  # (12,)

    def standardize_x(self, x: np.ndarray) -> np.ndarray:
        return (x - self.x_mean) / self.x_std

    def destandardize_x(self, x: np.ndarray) -> np.ndarray:
        return x * self.x_std + self.x_mean

    def standardize_cond(self, c: np.ndarray) -> np.ndarray:
        """Standardize the continuous tail of ``(…, 18)`` c_b vectors; one-hot kept."""
        c = np.asarray(c, dtype=np.float64)
        out = c.copy()
        out[..., 6:] = (c[..., 6:] - self.c_mean) / self.c_std
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_mean": self.x_mean.tolist(),
            "x_std": self.x_std.tolist(),
            "c_mean": self.c_mean.tolist(),
            "c_std": self.c_std.tolist(),
        }

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> Standardization:
        return cls(
            x_mean=np.asarray(doc["x_mean"], dtype=np.float64),
            x_std=np.asarray(doc["x_std"], dtype=np.float64),
            c_mean=np.asarray(doc["c_mean"], dtype=np.float64),
            c_std=np.asarray(doc["c_std"], dtype=np.float64),
        )


@dataclass(frozen=True)
class BlockDataset:
    """The assembled block training set (see the module docstring).

    ``x`` is ``(n_blocks, L, F)`` in unconstrained coordinates (cpi rebased,
    NOT standardized — standardization constants live in ``standardization`` so
    a consumer can never mix constants from another dataset); ``cond`` is
    ``(n_blocks, 18)`` raw cb-v1 vectors; ``starts`` the panel month of each
    block. ``train_index`` and ``fold_indices`` partition rows; blocks
    straddling a boundary appear in neither (``n_dropped_straddling``).
    """

    factor_names: tuple[str, ...]
    block_months: int
    x: np.ndarray
    cond: np.ndarray
    starts: np.ndarray
    train_index: np.ndarray
    fold_indices: tuple[np.ndarray, ...]
    standardization: Standardization
    stats: SourceStats
    n_dropped_straddling: int
    validation_start_month: int

    @property
    def n_train_raw(self) -> int:
        """RAW overlapping training-block count — never a sample size."""
        return int(self.train_index.size)

    @property
    def n_train_effective(self) -> int:
        """Effective per-epoch sample size after overlap correction (~n_months/L)."""
        return int(self.validation_start_month // self.block_months)

    def train_x_standardized(self) -> np.ndarray:
        return self.standardization.standardize_x(self.x[self.train_index])

    def train_cond_standardized(self) -> np.ndarray:
        return self.standardization.standardize_cond(self.cond[self.train_index])

    def fold_x_standardized(self, k: int) -> np.ndarray:
        return self.standardization.standardize_x(self.x[self.fold_indices[k]])

    def fold_cond_standardized(self, k: int) -> np.ndarray:
        return self.standardization.standardize_cond(self.cond[self.fold_indices[k]])

    def fold_x_units(self, k: int) -> np.ndarray:
        """Fold blocks in FACTOR UNITS (cpi as within-block relative level)."""
        z = self.x[self.fold_indices[k]]
        return ct.panel_to_constrained(z, self.factor_names)


def _conditioning_rows(
    source: BootstrapSource,
    climate: ClimateArtifact,
    stats: SourceStats,
    segments: list[tuple[int, int, MonthlyTargets]],
    starts: np.ndarray,
    block_months: int,
) -> np.ndarray:
    """cb-v1 vectors for historical block starts, via the bridge's own machinery.

    ``segments`` is ``[(lo, hi, targets_for_segment), ...]`` covering the panel;
    a block's Δw is read off the curve of the segment CONTAINING ITS START, in
    segment-local coordinates (split hygiene, module docstring).
    """
    idx = climate.dates.get_indexer(source.dates)
    if np.any(idx < 0):
        first = source.dates[int(np.flatnonzero(idx < 0)[0])]
        raise JoineryError(
            f"climate artifact grid ({climate.dates[0].date()}..{climate.dates[-1].date()}) "
            f"does not cover source month {first.date()}"
        )
    states = climate.states.mean(axis=0)[idx, :]  # posterior-mean s_t at panel dates
    names = list(source.factor_names)
    eq_col = names.index("equity_mkt")
    spread_col = names.index("ig_spread")
    codes = np.array([_LABEL_INDEX[label] for label in source.labels], dtype=np.int64)
    eye = np.eye(len(REGIME_LABELS))

    def segment_of(start: int) -> tuple[int, int, MonthlyTargets]:
        for lo, hi, targets in segments:
            if lo <= start < hi:
                return lo, hi, targets
        raise JoineryError(f"block start {start} falls in no split segment")

    rows = np.empty((starts.size, bridge.C_B_DIM), dtype=np.float64)
    for i, start in enumerate(int(s) for s in starts):
        lo, hi, targets = segment_of(start)
        cond = bridge.BlockConditioning(
            regime_onehot=eye[codes[start]],
            state_snapshot=states[start],
            history_summary=bridge._history_summary(
                source.values, start, eq_col, spread_col, stats
            ),
            waypoint_increments=bridge._waypoint_increments(
                targets, start - lo, block_months, hi - lo
            ),
            start_month=start,
        )
        rows[i] = cond.to_vector()
    return rows


def _fold_boundaries(validation_start: int, months: int, n_folds: int) -> list[int]:
    """Boundary month indices: [0, validation_start, fold edges…, months]."""
    if not 0 < validation_start < months:
        raise JoineryError(
            f"validation must start strictly inside the panel (start {validation_start}, "
            f"months {months})"
        )
    val_months = months - validation_start
    if n_folds < 1 or val_months < n_folds:
        raise JoineryError(f"cannot cut {val_months} validation months into {n_folds} folds")
    edges = [0, validation_start]
    for k in range(1, n_folds):
        edges.append(validation_start + round(k * val_months / n_folds))
    edges.append(months)
    return edges


def build_dataset(
    source: BootstrapSource,
    climate: ClimateArtifact,
    *,
    block_months: int = bridge.BLOCK_MONTHS,
    n_folds: int = 3,
    validation_start_date: str = VALIDATION.start,
) -> BlockDataset:
    """Assemble the block training set from the campaign panel + L1 posterior.

    ``validation_start_date`` defaults to the SEALED split boundary
    (:data:`ah.splits.VALIDATION`); the parameter exists for synthetic tests
    only. Deterministic: no RNG anywhere in this function.
    """
    import dataclasses

    months = source.n_rows
    if months < 2 * block_months:
        raise JoineryError(f"panel of {months} months is too short for {block_months}-blocks")

    validation_start = int((source.dates < pd.Timestamp(validation_start_date)).sum())
    if not 0 < validation_start < months:
        raise JoineryError(
            f"validation boundary {validation_start_date} must fall strictly inside the "
            f"panel {source.dates[0].date()}..{source.dates[-1].date()}"
        )

    # Train-segment stats for the h_t fallback of training conditioning (split
    # hygiene, module docstring): the generation-time contract uses train+val
    # h0_*, but a TRAINING input must not embed validation-span data.
    train_view = dataclasses.replace(
        source,
        values=source.values[:validation_start],
        dates=source.dates[:validation_start],
        labels=source.labels[:validation_start],
    )
    stats = wp.source_stats(train_view, climate)

    segments = [
        (0, validation_start, historical_monthly_targets(source, 0, validation_start)),
        (validation_start, months, historical_monthly_targets(source, validation_start, months)),
    ]
    starts = np.arange(0, months - block_months + 1, dtype=np.int64)  # ALL overlapping blocks
    cond = _conditioning_rows(source, climate, stats, segments, starts, block_months)

    # Targets in unconstrained coordinates, cpi rebased to the block start.
    z_panel = ct.panel_to_unconstrained(source.values, source.factor_names)
    x = np.stack([z_panel[s : s + block_months] for s in starts])
    names = list(source.factor_names)
    for chained in bridge.CHAINED_FACTORS:
        if chained in names:
            col = names.index(chained)
            x[:, :, col] -= x[:, :1, col]  # log level relative to block month 0

    edges = _fold_boundaries(validation_start, months, n_folds)

    def inside(lo: int, hi: int) -> np.ndarray:
        return np.flatnonzero((starts >= lo) & (starts + block_months <= hi))

    train_index = inside(edges[0], edges[1])
    fold_indices = tuple(inside(edges[k], edges[k + 1]) for k in range(1, len(edges) - 1))
    kept = train_index.size + sum(f.size for f in fold_indices)
    n_dropped = int(starts.size - kept)

    train_x = x[train_index]
    x_mean = train_x.mean(axis=(0, 1))
    x_std = np.maximum(train_x.std(axis=(0, 1), ddof=0), _STD_FLOOR)
    train_c = cond[train_index][:, 6:]
    c_mean = train_c.mean(axis=0)
    c_std = np.maximum(train_c.std(axis=0, ddof=0), _STD_FLOOR)

    return BlockDataset(
        factor_names=tuple(source.factor_names),
        block_months=int(block_months),
        x=x,
        cond=cond,
        starts=starts,
        train_index=train_index,
        fold_indices=fold_indices,
        standardization=Standardization(x_mean=x_mean, x_std=x_std, c_mean=c_mean, c_std=c_std),
        stats=stats,
        n_dropped_straddling=n_dropped,
        validation_start_month=validation_start,
    )


def epoch_starts(dataset: BlockDataset, rng: np.random.Generator) -> np.ndarray:
    """One epoch's training-block row indices, overlap-corrected.

    A random phase in [0, L) picks a grid of starts spaced exactly L apart, so
    no two blocks in an epoch share a month (adjacent overlap zero); the grid is
    then shuffled. ~n_train_months/L blocks per epoch — the effective-sample
    correction DN-1.1 §II.4 requires (raw overlapping counts are never sample
    sizes).
    """
    ell = dataset.block_months
    phase = int(rng.integers(ell))
    train_starts = dataset.starts[dataset.train_index]
    grid = np.flatnonzero((train_starts - phase) % ell == 0)
    rows = dataset.train_index[grid]
    rng.shuffle(rows)
    return rows
