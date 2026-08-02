"""WP2.7 bridge — block assembly and the frozen c_b conditioning contract.

DN-1.1 §II.4/§II.5 step 4: a decade's monthly path is assembled from overlapping
L-month blocks (L=6 default, stride L/2=3) sampled from a block generator
``G(x | c_b)``, blended with a linear cross-fade in state space on the overlaps.

THE FROZEN CONDITIONING CONTRACT (what WP2.8/2.9 train against)
---------------------------------------------------------------
``c_b`` is :class:`BlockConditioning` — four typed parts, serialized in the fixed
:data:`C_B_COMPONENTS` order (:data:`C_B_DIM` = 18):

- ``regime_onehot`` (6): one-hot of the regime R at the block's START month, in
  :data:`ah.gen.regimes.semimarkov.REGIME_LABELS` order (EXP..REF).
- ``state_snapshot`` (5): the L1 slow-state vector s_t at the block's start month,
  in :data:`ah.gen.climate.model.STATE_NAMES` order.
- ``history_summary`` (3): h_t, the trailing-12-month summary of the ASSEMBLED
  path: (sum of monthly log equity returns; sd (ddof=1) of those monthly log
  returns, monthly not annualized; ig_spread level at the last assembled month).
  A block starting before month 12 has no assembled trailing year, and uses the
  train+validation unconditional values (``SourceStats.h0_*``) — part of the
  contract, not an implementation detail.
- ``waypoint_increments`` (4): Δw, the waypoint-target increments the block must
  be consistent with, read off the :class:`~ah.gen.joinery.waypoints.MonthlyTargets`
  curves over the block's window [s, s+L): ``curve[min(s+L, months)-1] -
  curve[max(s-1, 0)]`` for (policy_pct, log_cpi, equity_cum_log,
  spread_center_pct).

Serialization: :meth:`BlockConditioning.to_vector` (float64, component order
above), :meth:`to_json`/:meth:`from_json` (schema-versioned, sorted keys), and
:func:`contract_fingerprint` — a SHA-256 over the schema version + component
names that WP2.8/2.9 pin so an incompatible contract fails loudly, not silently.

The guidance hook (DN-1.1 §II.5 design note (a)) is PRESENT and STUBBED:
``assemble_decade_path(guidance=...)`` calls ``guidance.adjust(block, cond)`` per
sampled block; the default ``None`` does nothing. Training-free
posterior-sampling guidance is a WP2.9 evaluation item, not a WP2.7 behavior.

Determinism: the sampler is driven by the caller's ``numpy.random.Generator``;
this module opens no stream of its own.

Batching across decades (WP2.8b)
--------------------------------
Blocks WITHIN a decade are irreducibly sequential: block b's ``h_t`` summarizes
months earlier blocks produced. Blocks ACROSS decades at the same index are
independent given their conditioning, and every decade's block b starts at the
same month — so that is the axis a neural sampler can batch.
:func:`assemble_decade_paths` drives N decades in lockstep, block-major: at each
block index it builds all N conditioning vectors, hands them to the sampler in
ONE call, and scatters the results back. Each decade keeps its own
``numpy.random.Generator`` and the sampler draws from it at exactly the point the
per-decade driver would have, so batching changes what work is grouped, never
what any stream produces or when.

A sampler opts in by implementing :class:`BatchedBlockSampler`'s
``sample_blocks``; anything that does not (``BootstrapBlockSampler``) falls back
to running :func:`assemble_decade_path` per decade, unchanged.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.model import STATE_NAMES
from ah.gen.joinery.waypoints import (
    DecadeWaypoints,
    JoineryError,
    MonthlyTargets,
    SourceStats,
)
from ah.gen.regimes.semimarkov import REGIME_LABELS

__all__ = [
    "BLOCK_MONTHS",
    "BLOCK_STRIDE",
    "C_B_COMPONENTS",
    "C_B_DIM",
    "C_B_SCHEMA_VERSION",
    "BatchedBlockSampler",
    "BlockConditioning",
    "BlockSampler",
    "BootstrapBlockSampler",
    "DecadeAssembly",
    "GuidanceHook",
    "assemble_decade_path",
    "assemble_decade_paths",
    "contract_fingerprint",
]

#: DN-1.1 §II.4 defaults: L=6-month blocks, stride L/2=3 (overlap 3).
BLOCK_MONTHS = 6
BLOCK_STRIDE = 3

#: Trending price-index factors are CHAINED at block joins: an incoming block's
#: level column is rebased multiplicatively so its first overlap month continues
#: the assembled path, i.e. the block contributes its within-block INFLATION, not
#: its absolute 1990s-vs-2010s price level. Recorded WP2.7 decision: raw level
#: resampling (what bootstrap-v1 emits, judged and passing as such) makes the
#: assembled cpi path a jump process whose Denton adjustment would measure the
#: draw-span's price trend rather than generator-vs-structure disagreement —
#: exactly the diagnostic §WP2.7 says must stay meaningful. Rates and spreads are
#: mean-reverting levels and are NOT chained.
CHAINED_FACTORS: tuple[str, ...] = ("cpi",)

C_B_SCHEMA_VERSION = "cb-v1"

_HISTORY_COMPONENTS: tuple[str, ...] = (
    "h_equity_ret_12m_log",
    "h_equity_vol_12m",
    "h_spread_level_pct",
)
_INCREMENT_COMPONENTS: tuple[str, ...] = (
    "dw_policy_rate_pct",
    "dw_log_cpi",
    "dw_equity_cum_log",
    "dw_spread_center_pct",
)

#: The frozen component order of the serialized c_b vector.
C_B_COMPONENTS: tuple[str, ...] = (
    *(f"regime_{label}" for label in REGIME_LABELS),
    *(f"state_{name}" for name in STATE_NAMES),
    *_HISTORY_COMPONENTS,
    *_INCREMENT_COMPONENTS,
)
C_B_DIM = len(C_B_COMPONENTS)


def contract_fingerprint() -> str:
    """SHA-256 over the schema version + ordered component names.

    WP2.8/2.9 record this next to their checkpoints: a trained sampler whose
    fingerprint differs from the runtime's is conditioned on a different contract
    and must refuse to sample.
    """
    doc = json.dumps({"schema": C_B_SCHEMA_VERSION, "components": list(C_B_COMPONENTS)})
    return hashlib.sha256(doc.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BlockConditioning:
    """One block's conditioning vector c_b (see the module docstring's contract)."""

    regime_onehot: np.ndarray  # (6,)
    state_snapshot: np.ndarray  # (5,)
    history_summary: np.ndarray  # (3,)
    waypoint_increments: np.ndarray  # (4,)
    start_month: int

    def __post_init__(self) -> None:
        for name, arr, size in (
            ("regime_onehot", self.regime_onehot, len(REGIME_LABELS)),
            ("state_snapshot", self.state_snapshot, len(STATE_NAMES)),
            ("history_summary", self.history_summary, len(_HISTORY_COMPONENTS)),
            ("waypoint_increments", self.waypoint_increments, len(_INCREMENT_COMPONENTS)),
        ):
            a = np.asarray(arr, dtype=np.float64)
            if a.shape != (size,):
                raise JoineryError(f"c_b {name} must have shape ({size},); got {a.shape}")
            object.__setattr__(self, name, a)

    def to_vector(self) -> np.ndarray:
        """The (18,) float64 vector in :data:`C_B_COMPONENTS` order."""
        return np.concatenate(
            [
                self.regime_onehot,
                self.state_snapshot,
                self.history_summary,
                self.waypoint_increments,
            ]
        )

    def continuous_vector(self) -> np.ndarray:
        """The 12 continuous components (one-hot excluded) — support.py's input.

        The one-hot part would make any covariance singular; the regime dimension
        is monitored separately by the support monitor's regime-frequency check.
        """
        return np.concatenate([self.state_snapshot, self.history_summary, self.waypoint_increments])

    def to_json(self) -> str:
        vec = self.to_vector()
        doc = {
            "schema": C_B_SCHEMA_VERSION,
            "start_month": int(self.start_month),
            "components": {name: float(vec[i]) for i, name in enumerate(C_B_COMPONENTS)},
        }
        return json.dumps(doc, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> BlockConditioning:
        doc = json.loads(text)
        if doc.get("schema") != C_B_SCHEMA_VERSION:
            raise JoineryError(
                f"c_b schema mismatch: got {doc.get('schema')!r}, this runtime speaks "
                f"{C_B_SCHEMA_VERSION!r}"
            )
        values = doc["components"]
        vec = np.array([float(values[name]) for name in C_B_COMPONENTS])
        return cls(
            regime_onehot=vec[0:6],
            state_snapshot=vec[6:11],
            history_summary=vec[11:14],
            waypoint_increments=vec[14:18],
            start_month=int(doc["start_month"]),
        )


# --------------------------------------------------------------------------- #
# the block-sampler protocol (bootstrap stand-in now; WP2.8/2.9 behind it later)
# --------------------------------------------------------------------------- #


@runtime_checkable
class BlockSampler(Protocol):
    """What L4 requires of a block generator — the L3 interface (DN-1.1 §II.4).

    ``sample_block(cond, rng)`` returns a ``(block_months, len(factor_names))``
    float array. Implementations must draw all randomness from ``rng`` (a
    ``numpy.random.Generator`` the assembler owns) so decade assembly stays
    deterministic per seed.
    """

    factor_names: tuple[str, ...]
    block_months: int

    def sample_block(self, cond: BlockConditioning, rng: np.random.Generator) -> np.ndarray: ...


@runtime_checkable
class BatchedBlockSampler(Protocol):
    """OPTIONAL throughput extension (WP2.8b): one call, many decades.

    ``sample_blocks(conds, rngs)`` returns ``(len(conds), block_months,
    len(factor_names))``. The i-th block must be exactly what
    ``sample_block(conds[i], rngs[i])`` would have produced at that point in
    ``rngs[i]``'s stream — same draws, same order, one per decade. What a batched
    implementation may change is how the *network* evaluation is grouped; what it
    may not change is the RNG.

    Samplers that do not implement it keep working: :func:`assemble_decade_paths`
    checks ``isinstance(sampler, BatchedBlockSampler)`` and otherwise runs the
    per-decade :func:`assemble_decade_path` loop unchanged.
    """

    factor_names: tuple[str, ...]
    block_months: int

    def sample_block(self, cond: BlockConditioning, rng: np.random.Generator) -> np.ndarray: ...

    def sample_blocks(
        self,
        conds: Sequence[BlockConditioning],
        rngs: Sequence[np.random.Generator],
    ) -> np.ndarray: ...


@runtime_checkable
class GuidanceHook(Protocol):
    """The stubbed inference-time guidance hook (DN-1.1 §II.5 design note (a))."""

    def adjust(self, block: np.ndarray, cond: BlockConditioning) -> np.ndarray: ...


class BootstrapBlockSampler:
    """The stand-in block generator: regime-stratified historical L-month blocks.

    §WP2.7's instruction verbatim — test all of L4 with bootstrap blocks (ablation
    system C's machinery, free). A block is ``block_months`` CONTIGUOUS rows of
    the source panel (multivariate: one shared row index across all factors),
    whose start month carries the conditioned regime label, wrapping circularly
    like the sealed benchmark. Only the regime component of c_b conditions the
    draw — a bootstrap cannot aim at s_t, h_t or Δw, which is exactly the
    structural gap the conditional generators exist to close (and the Denton
    reconciliation guarantees despite).

    ``fallback_counts`` records every conditioned label with no stratum in the
    draw span (STAG on the real 1990-2020 span): the draw falls back to an
    unconditional uniform start, visibly rather than silently.
    """

    def __init__(self, source: BootstrapSource, *, block_months: int = BLOCK_MONTHS) -> None:
        if block_months < 1:
            raise JoineryError("block_months must be >= 1")
        self._source = source
        self.block_months = int(block_months)
        self.factor_names = tuple(source.factor_names)
        self.fallback_counts: dict[str, int] = {}

    def sample_block(self, cond: BlockConditioning, rng: np.random.Generator) -> np.ndarray:
        source = self._source
        label = REGIME_LABELS[int(np.argmax(cond.regime_onehot))]
        stratum = source.strata.get(label)
        if stratum is None:
            self.fallback_counts[label] = self.fallback_counts.get(label, 0) + 1
            start = int(rng.integers(source.n_rows))
        else:
            start = int(stratum[rng.integers(stratum.size)])
        rows = (start + np.arange(self.block_months)) % source.n_rows
        return source.values[rows]


# --------------------------------------------------------------------------- #
# decade assembly (DN-1.1 §II.5 step 4)
# --------------------------------------------------------------------------- #


def _history_summary(
    assembled: np.ndarray,
    start: int,
    eq_col: int,
    spread_col: int,
    stats: SourceStats,
) -> np.ndarray:
    if start < 12:
        return np.array([stats.h0_equity_ret_12m, stats.h0_equity_vol_12m, stats.h0_spread_level])
    eq = np.log1p(assembled[start - 12 : start, eq_col])
    return np.array(
        [
            float(eq.sum()),
            float(np.std(eq, ddof=1)),
            float(assembled[start - 1, spread_col]),
        ]
    )


def _waypoint_increments(
    targets: MonthlyTargets | None, start: int, block_months: int, months: int
) -> np.ndarray:
    if targets is None:
        return np.zeros(4)
    hi = min(start + block_months, months) - 1
    lo = max(start - 1, 0)
    return np.array(
        [
            targets.policy_pct[hi] - targets.policy_pct[lo],
            targets.log_cpi[hi] - targets.log_cpi[lo],
            targets.equity_cum_log[hi] - targets.equity_cum_log[lo],
            targets.spread_center_pct[hi] - targets.spread_center_pct[lo],
        ]
    )


#: A' residual parameterization covers exactly the INTEGRATED-DRIFT factors,
#: whose Δw component determines a per-month mean with no absolute level needed.
#: policy_rate and ig_spread are mean-reverting LEVELS whose Δw is a level
#: change — a level anchor is not recoverable from c_b (the Taylor anchor needs
#: per-decade posterior draws that c_b does not carry), so they stay direct.
DRIFT_MEAN_FACTORS: tuple[str, ...] = ("cpi", "equity_mkt")

_DW_LOG_CPI = C_B_COMPONENTS.index("dw_log_cpi")
_DW_EQUITY_CUM_LOG = C_B_COMPONENTS.index("dw_equity_cum_log")


def conditioning_drift_means(
    cond_vectors: np.ndarray, factor_names: Sequence[str], block_months: int
) -> np.ndarray:
    """Per-month conditioning-implied drift means in UNCONSTRAINED coordinates.

    The A' residual contract: the network models deviations around these means
    — subtracted from targets at dataset build, added back after de-standardize
    at sample time — so era-scale trend tracking is structural rather than
    learned. Derived from the RAW (unstandardized) c_b vectors alone, which is
    what makes train/sample symmetry exact and leaves the cb-v1 contract and
    its fingerprint untouched.

    Given Δw spanning ``block_months`` monthly increments of the target curve:

    - ``cpi``: the block's x is log level rebased to block month 0, so the
      implied mean is the linear ramp ``m[j] = Δw_log_cpi * j / L``.
    - ``equity_mkt``: x is log1p(monthly return), so the implied mean is the
      constant per-month drift ``m[j] = Δw_equity_cum_log / L``.

    Zero Δw (bind_waypoints off, or a targets-free segment) gives a zero mean,
    collapsing the residual path to the direct one.
    """
    cond = np.asarray(cond_vectors, dtype=np.float64)
    if cond.ndim != 2 or cond.shape[1] != C_B_DIM:
        raise JoineryError(f"cond_vectors must be (n, {C_B_DIM}); got {cond.shape}")
    names = list(factor_names)
    m = np.zeros((cond.shape[0], block_months, len(names)), dtype=np.float64)
    ramp = np.arange(block_months, dtype=np.float64) / float(block_months)
    if "cpi" in names:
        m[:, :, names.index("cpi")] = cond[:, _DW_LOG_CPI, None] * ramp
    if "equity_mkt" in names:
        m[:, :, names.index("equity_mkt")] = cond[:, _DW_EQUITY_CUM_LOG, None] / float(block_months)
    return m


@dataclass(frozen=True)
class DecadeAssembly:
    """One decade's inputs to :func:`assemble_decade_paths`.

    ``rng`` is that decade's own stream (``PCG64(base + 7919*k)`` upstream); the
    driver never shares a generator between decades, batched or not.
    """

    waypoints: DecadeWaypoints
    targets: MonthlyTargets | None
    states_row: np.ndarray
    rng: np.random.Generator


class _PathBuilder:
    """One decade's in-progress path: conditioning out, sampled blocks in.

    Both drivers go through this, so the arithmetic of c_b construction, cpi
    chaining and the cross-fade is written once and is identical whether the
    network evaluation was batched or not.
    """

    def __init__(
        self,
        *,
        months: int,
        spec: DecadeAssembly,
        names: list[str],
        eq_col: int,
        spread_col: int,
        block_months: int,
        stats: SourceStats,
    ) -> None:
        if months < 1:
            raise JoineryError("months must be >= 1")
        if spec.waypoints.months != months:
            raise JoineryError(
                f"waypoints cover {spec.waypoints.months} months; asked to assemble {months}"
            )
        states_row = np.asarray(spec.states_row, dtype=np.float64)
        if states_row.shape != (months, 5):
            raise JoineryError(f"states_row must be (months, 5); got {states_row.shape}")

        self.months = months
        self.spec = spec
        self.states_row = states_row
        self.names = names
        self.eq_col = eq_col
        self.spread_col = spread_col
        self.block_months = block_months
        self.stats = stats
        self.assembled = np.zeros((months, len(names)), dtype=np.float64)
        self.written = 0  # months [0, written) hold assembled values
        self.conds: list[BlockConditioning] = []

    def conditioning(self, start: int) -> BlockConditioning:
        cond = BlockConditioning(
            regime_onehot=np.eye(len(REGIME_LABELS))[int(self.spec.waypoints.labels[start])],
            state_snapshot=self.states_row[start],
            history_summary=_history_summary(
                self.assembled, start, self.eq_col, self.spread_col, self.stats
            ),
            waypoint_increments=_waypoint_increments(
                self.spec.targets, start, self.block_months, self.months
            ),
            start_month=start,
        )
        self.conds.append(cond)
        return cond

    def integrate(self, start: int, block: np.ndarray) -> None:
        names, assembled = self.names, self.assembled
        end = min(start + self.block_months, self.months)
        overlap = max(0, self.written - start)

        # Chain price-index levels at the join (see CHAINED_FACTORS).
        if start > 0:
            for name in CHAINED_FACTORS:
                if name not in names:
                    continue
                col = names.index(name)
                anchor = assembled[start if overlap > 0 else start - 1, col]
                if block[0, col] <= 0 or anchor <= 0:
                    raise JoineryError(
                        f"chained factor '{name}' needs positive levels to rebase "
                        f"(block starts at {block[0, col]}, path at {anchor})"
                    )
                block = block.copy()
                block[:, col] *= anchor / block[0, col]
        for i in range(end - start):
            t = start + i
            if i < overlap:
                w = (i + 1) / (overlap + 1)
                assembled[t] = (1.0 - w) * assembled[t] + w * block[i]
            else:
                assembled[t] = block[i]
        self.written = max(self.written, end)


def _factor_columns(sampler: BlockSampler) -> tuple[list[str], int, int]:
    names = list(sampler.factor_names)
    try:
        return names, names.index("equity_mkt"), names.index("ig_spread")
    except ValueError as exc:
        raise JoineryError(
            f"sampler must emit equity_mkt and ig_spread (h_t needs them); got {names}"
        ) from exc


def assemble_decade_path(
    *,
    months: int,
    waypoints: DecadeWaypoints,
    targets: MonthlyTargets | None,
    states_row: np.ndarray,
    sampler: BlockSampler,
    stats: SourceStats,
    rng: np.random.Generator,
    stride: int = BLOCK_STRIDE,
    guidance: GuidanceHook | None = None,
) -> tuple[np.ndarray, list[BlockConditioning]]:
    """One decade's raw (pre-reconciliation) monthly path from overlapping blocks.

    Blocks start at months 0, stride, 2*stride, ...; each is sampled from
    ``sampler`` conditioned on c_b, optionally adjusted by the (stubbed) guidance
    hook, and blended into the assembled path with a linear cross-fade over the
    overlap: an overlap of ``o`` months uses incoming weights (1/(o+1), ...,
    o/(o+1)). ``targets=None`` sets Δw to zeros (unconditioned-bridge mode, used
    by tests); production always passes the waypoint target curves.

    Returns the ``(months, n_factors)`` path and the per-block conditioning
    vectors in block order (support.py consumes them; WP2.8 trains against them).
    """
    names, eq_col, spread_col = _factor_columns(sampler)
    n_factors = len(names)
    block_months = int(sampler.block_months)
    builder = _PathBuilder(
        months=months,
        spec=DecadeAssembly(waypoints=waypoints, targets=targets, states_row=states_row, rng=rng),
        names=names,
        eq_col=eq_col,
        spread_col=spread_col,
        block_months=block_months,
        stats=stats,
    )

    for start in range(0, months, stride):
        cond = builder.conditioning(start)
        block = np.asarray(sampler.sample_block(cond, rng), dtype=np.float64)
        if block.shape != (block_months, n_factors):
            raise JoineryError(
                f"sampler returned shape {block.shape}, expected {(block_months, n_factors)}"
            )
        if guidance is not None:
            block = np.asarray(guidance.adjust(block, cond), dtype=np.float64)
        builder.integrate(start, block)

    return builder.assembled, builder.conds


def assemble_decade_paths(
    *,
    months: int,
    decades: Sequence[DecadeAssembly],
    sampler: BlockSampler,
    stats: SourceStats,
    stride: int = BLOCK_STRIDE,
    guidance: GuidanceHook | None = None,
) -> list[tuple[np.ndarray, list[BlockConditioning]]]:
    """Assemble many decades, batching the sampler ACROSS them where it can.

    Returns one ``(path, conds)`` pair per entry of ``decades``, in order — the
    same pairs :func:`assemble_decade_path` returns decade by decade.

    Control flow: block-major. For each block index in turn (blocks stay strictly
    sequential — ``h_t`` demands it) every decade's c_b is built from ITS OWN
    partially assembled path, the whole slate goes to ``sampler.sample_blocks``
    in one call with each decade's own generator, and the returned blocks are
    cross-faded back into their own decades. A sampler without the batched entry
    point takes the unchanged per-decade path instead.
    """
    if not decades:
        return []
    if not isinstance(sampler, BatchedBlockSampler):
        return [
            assemble_decade_path(
                months=months,
                waypoints=spec.waypoints,
                targets=spec.targets,
                states_row=spec.states_row,
                sampler=sampler,
                stats=stats,
                rng=spec.rng,
                stride=stride,
                guidance=guidance,
            )
            for spec in decades
        ]

    names, eq_col, spread_col = _factor_columns(sampler)
    n_factors = len(names)
    block_months = int(sampler.block_months)
    builders = [
        _PathBuilder(
            months=months,
            spec=spec,
            names=names,
            eq_col=eq_col,
            spread_col=spread_col,
            block_months=block_months,
            stats=stats,
        )
        for spec in decades
    ]
    rngs = [spec.rng for spec in decades]
    expected = (len(decades), block_months, n_factors)
    for start in range(0, months, stride):
        conds = [builder.conditioning(start) for builder in builders]
        blocks = np.asarray(sampler.sample_blocks(conds, rngs), dtype=np.float64)
        if blocks.shape != expected:
            raise JoineryError(
                f"batched sampler returned shape {blocks.shape}, expected {expected}"
            )
        for builder, cond, block in zip(builders, conds, blocks, strict=True):
            if guidance is not None:
                block = np.asarray(guidance.adjust(block, cond), dtype=np.float64)
            builder.integrate(start, block)

    return [(builder.assembled, builder.conds) for builder in builders]
