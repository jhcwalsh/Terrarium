"""WP2.7 assemble — DN-1.1 §II.5's 7-step decade-generation algorithm, end to end.

| Step | Operation (and where it lives)                                          |
|------|-------------------------------------------------------------------------|
| 1    | Draw (θ, s₀) from the L1 posterior; simulate s_t monthly (L1 simulate)  |
| 2    | Sample R_t from L2 given s — or accept a WorldSpec regime mode (L2)     |
| 3    | Waypoints w(s, R); WorldSpec factor_conditions bind here (waypoints.py) |
| 4    | Overlapping L-blocks from the pluggable BlockSampler; cross-fade (bridge)|
| 5    | Denton-reconcile to annual waypoints; re-apply floors (reconcile.py)    |
| 6    | Acceptance filter: ≤10%, named non-enforce metric subset, fully logged  |
| 7    | Emit the Ensemble with full lineage metadata                            |

Step 7's DN-1.1 text also names "map factors → strategy returns (WS-C mappings)".
That mapping is **Step 3 scope** (STEP2 §5 explicit non-goals) and is deferred;
the D4 strategies in ``ah.strategies`` are evaluation-side and are not what that
step means. Recorded here and in progress.md.

One-pass vs two-pass (carried-forward decision)
-----------------------------------------------
DEFAULT: ONE-PASS — L1 simulated under a neutral cycle, L2 sampled on those
states, L2's c_t then fed to the policy anchor at waypoint time. This is exactly
the ordering WP2.6's acceptance evidence certifies (18/18 duration/frequency
bands, one-pass). ``JoineryConfig.two_pass`` (off by default) re-runs L1 with
L2's emitted c_t: the same seed reopens the same PCG64 stream, so θ, s₀ and every
innovation are identical and the ONLY change is the credit-gap forcing
``L_bar_t = delta_L · c_t`` inside the state dynamics (the anchor already used
L2's c_t in both modes) — which shifts the credit-gap path and therefore the
spread waypoint centers. L2's labels are NOT re-drawn from the re-run states
(that would need a fixed-point iteration nothing in DN-1.1 asks for).

The acceptance filter (step 6, plan-critical)
---------------------------------------------
Metrics: :data:`FILTER_METRICS` = (skew, excess_kurtosis, hill_tail_index_5pct)
over the return factors (equity_mkt, smb, hml, mom) — DN-1.1's "fast subset
(tail panel...)". The subset is DISJOINT from every ``severity: enforce`` name in
the sealed manifest (tested against ``pre-registration.yaml``), and — stricter
than the letter of the plan — from every statistic FEEDING an enforce-tier band
gate: DN-1.1's parenthetical also names the ACF panel, but the sealed
``dependence_band_exceedance_fraction`` (enforce) aggregates exactly the ACF
statistics, so scoring on them would shape the enforce gate's input; the ACF
panel is therefore deliberately excluded (recorded deviation). The
implementations here are simple local numpy estimators, NOT imports of the
sealed ``ah.eval`` estimators (ah.gen never imports ah.eval) and NOT claimed to
be them.

Scoring: per decade, per (factor, metric), the absolute gap between the decade's
statistic and the train+validation historical value, scaled by the cross-decade
MAD of that statistic; a decade's score is the mean over components. A statistic
that is NaN for a decade while finite historically contributes a large penalty
(the WP2.2 anti-gaming rule: absence must never score better than presence).
Rejection: the worst ``floor(max_reject_fraction · n)`` decades (≤10%) are
rejected and resampled ONCE from fresh decade indices (n, n+1, ...) on the same
layer streams; replacements are accepted unconditionally (a second pass would
compound selection); every rejection is logged with seeds and scores.
``acceptance_filter=False`` disables the whole thing so the battery can see
filtered AND unfiltered ensembles.

Determinism: every stream is ``PCG64(seed + LAYER_OFFSET + 7919*k)``. Layer
offsets are chosen so no two layers' streams can coincide for ANY pair of decade
indices (no offset difference is a multiple of 7919 — tested). Bit-identical
ensembles per seed (tested).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ah.core.numericworld import NumericWorld
from ah.gen import registry
from ah.gen.base import Ensemble, EnsembleMeta
from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.simulate import (
    ClimateArtifact,
    SimulatedClimate,
    simulate_decades,
)
from ah.gen.climate.simulate import (
    load_artifact as load_climate_artifact,
)
from ah.gen.joinery import bridge
from ah.gen.joinery import reconcile as rc
from ah.gen.joinery import support as sp
from ah.gen.joinery import waypoints as wp
from ah.gen.regimes.semimarkov import (
    RegimePaths,
    RegimesArtifact,
    regime_path_for_world,
    simulate_regimes,
)
from ah.gen.regimes.semimarkov import (
    load_artifact as load_regimes_artifact,
)

__all__ = [
    "FILTER_FACTORS",
    "FILTER_METRICS",
    "GENERATOR_ID",
    "LAYER_SEED_OFFSETS",
    "SEED_STRIDE",
    "JoineryBootstrapV0",
    "JoineryConfig",
    "assemble_decades",
    "frozen_climate",
]

GENERATOR_ID = "joinery-bootstrap-v0"

SEED_STRIDE = 7919  # CLAUDE.md's platform-wide decade stride

#: Distinct base seeds per layer (carried-forward decision: identical seeds open
#: identical PCG64 streams in L1 and L2). Offsets are pairwise non-congruent
#: mod 7919, so no decade index of one layer can reopen another layer's stream.
LAYER_SEED_OFFSETS: dict[str, int] = {
    "climate": 0,
    "regimes": 1_000_003,
    "blocks": 2_000_003,
}

#: The named acceptance-filter subset (see the module docstring).
FILTER_METRICS: tuple[str, ...] = ("skew", "excess_kurtosis", "hill_tail_index_5pct")
FILTER_FACTORS: tuple[str, ...] = ("equity_mkt", "smb", "hml", "mom")

#: Anti-gaming penalty for a decade whose statistic is NaN while history's is
#: finite (a decade with no negative equity months has no tail — that is a
#: reason to reject it, never a free pass).
_NAN_PENALTY = 1e6

# The default real artifacts (the fitted L1/L2 posteriors), pinned by content
# SHA-256 exactly as the fit reports record them. Used only by the registered
# factory / the battery script — unit tests build synthetic artifacts.
_REPO_ROOT = Path(__file__).resolve().parents[4]  # src/ah/gen/joinery -> repo root
DEFAULT_CLIMATE_ARTIFACT = (
    _REPO_ROOT / "experiments" / "climate-l1-f7d4119c7101-s20260726" / "climate-posterior.npz"
)
DEFAULT_REGIMES_ARTIFACT = (
    _REPO_ROOT / "experiments" / "regimes-l2-1758709d4009-s20260727" / "regimes-posterior.npz"
)
PINNED_CLIMATE_SHA256 = "98bdb68f3fd9753d5e10776772849bfa6bbe87f9a0fbd83952a7cad42000c487"
PINNED_REGIMES_SHA256 = "e83b9e86f73a679e61d5f5929ee2f552f9eac3c190ecc2a62e6947ef329ef47d"


@dataclass(frozen=True)
class JoineryConfig:
    """Everything tunable about the assembly, hashed into the ensemble lineage."""

    block_months: int = bridge.BLOCK_MONTHS
    block_stride: int = bridge.BLOCK_STRIDE
    acceptance_filter: bool = True
    max_reject_fraction: float = 0.10  # DN-1.1 §II.5: deliberately mild, <=10%
    two_pass: bool = False  # see the module docstring; one-pass is the certified default
    support_quantile: float = sp.EXTRAPOLATION_QUANTILE
    s0_date: str | None = None  # None -> the artifact's last fitted month
    reconcile: rc.ReconcileConfig = field(default_factory=rc.ReconcileConfig)

    #: WP2.10 ablation lever — DN-1.1 §II.7 system **B** (neural rollout).
    #: ``False`` drops step 3's *binding* and step 5 entirely: the bridge is handed
    #: ``targets=None`` (so every Δw component of ``c_b`` is zero) and no Denton
    #: reconciliation runs, which also means **the post-Denton floor re-application
    #: does not run** — the only remaining floor guarantee is whatever the block
    #: sampler provides structurally (``ah.gen.blocks.constraints`` does; the
    #: bootstrap stand-in does by construction; a Gaussian sampler does NOT, which
    #: is why system A keeps binding on). Waypoints are still *built* — the regime
    #: labels feed ``c_b``'s one-hot and the support diagnostic — they are simply
    #: not aimed at. Reconciliation diagnostics come back empty, and the ensemble
    #: lineage records ``reconciliation_applied: false``.
    bind_waypoints: bool = True

    #: WP2.10 ablation lever — DN-1.1 §II.7 system **C** (neural only, "no L1").
    #: ``False`` replaces the simulated climate path with the posterior-MEAN state
    #: at ``s0_date``, held constant for every month of every decade (and the
    #: posterior-mean θ for the waypoint parameters). L1 therefore contributes no
    #: variation to anything: ``c_b``'s state snapshot is a constant vector, L2's
    #: slow-state covariates are constant so the semi-Markov chain runs at its
    #: baseline hazards, and the structural waypoints stop moving. It is the
    #: cheapest faithful reading of "no L1" that keeps every downstream interface
    #: intact — L2 is logit-linked to L1's slow states, so the layer cannot simply
    #: be deleted without also deleting L2.
    use_climate: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "block_months": self.block_months,
            "block_stride": self.block_stride,
            "acceptance_filter": self.acceptance_filter,
            "max_reject_fraction": self.max_reject_fraction,
            "two_pass": self.two_pass,
            "support_quantile": self.support_quantile,
            "s0_date": self.s0_date,
            "bind_waypoints": self.bind_waypoints,
            "use_climate": self.use_climate,
            "reconcile": {k: float(v) for k, v in self.reconcile.__dict__.items()},
        }


# --------------------------------------------------------------------------- #
# local filter statistics (simple numpy; deliberately NOT the sealed estimators)
# --------------------------------------------------------------------------- #


def _skew(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if x.size < 12:
        return float("nan")
    sd = float(np.std(x, ddof=0))
    if sd == 0.0:
        return float("nan")
    return float(np.mean(((x - x.mean()) / sd) ** 3))


def _excess_kurtosis(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if x.size < 12:
        return float("nan")
    sd = float(np.std(x, ddof=0))
    if sd == 0.0:
        return float("nan")
    return float(np.mean(((x - x.mean()) / sd) ** 4) - 3.0)


def _hill_tail_index_5pct(x: np.ndarray) -> float:
    """Hill estimator on the lower (loss) tail at the 5% cut. Local, unsealed."""
    x = x[np.isfinite(x)]
    losses = np.sort(-x[x < 0.0])[::-1]  # positive losses, descending
    k = int(np.floor(0.05 * x.size))
    if k < 3 or losses.size <= k or losses[k] <= 0.0:
        return float("nan")
    return float(1.0 / np.mean(np.log(losses[:k] / losses[k])))


_FILTER_FUNCS = {
    "skew": _skew,
    "excess_kurtosis": _excess_kurtosis,
    "hill_tail_index_5pct": _hill_tail_index_5pct,
}


def _filter_stat_matrix(paths: np.ndarray, columns: dict[str, int]) -> np.ndarray:
    """(n_decades, n_factors*n_metrics) filter statistics per decade."""
    n = paths.shape[0]
    out = np.empty((n, len(columns) * len(FILTER_METRICS)))
    for d in range(n):
        j = 0
        for name in FILTER_FACTORS:
            if name not in columns:
                continue
            series = paths[d, :, columns[name]]
            for metric in FILTER_METRICS:
                out[d, j] = _FILTER_FUNCS[metric](series)
                j += 1
    return out


class _FilterScorer:
    """The acceptance-filter scoring rule, FROZEN on the initial ensemble.

    The historical reference values and the cross-decade MAD scale are computed
    ONCE, from the source and the initial n-decade ensemble, and reused for every
    score afterwards — including replacement decades. (First-run lesson, caught
    at 1024 decades: scoring a single replacement decade with a scale re-derived
    from its own 1-row stat matrix degenerates the MAD to ~0 and logs a
    meaningless ~1e12 score; the filter's decisions were unaffected — replacements
    are accepted unconditionally — but a log entry nobody can read is not a log.)
    """

    def __init__(self, paths: np.ndarray, source: BootstrapSource) -> None:
        names = list(source.factor_names)
        self.columns = {name: names.index(name) for name in FILTER_FACTORS if name in names}
        stats = _filter_stat_matrix(paths, self.columns)

        reference = np.empty(stats.shape[1])
        j = 0
        for name in FILTER_FACTORS:
            if name not in self.columns:
                continue
            series = source.values[:, self.columns[name]]
            for metric in FILTER_METRICS:
                reference[j] = _FILTER_FUNCS[metric](series)
                j += 1
        self.reference = reference
        self.ref_ok = np.isfinite(reference)

        scale = np.ones(stats.shape[1])
        for j in range(stats.shape[1]):
            col = stats[:, j]
            finite = col[np.isfinite(col)]
            if finite.size:
                scale[j] = float(np.median(np.abs(finite - np.median(finite)))) * 1.4826 + 1e-12
        self.scale = scale

    def scores(self, paths: np.ndarray) -> np.ndarray:
        """Per-decade scores: scaled distance to the historical statistics."""
        stats = _filter_stat_matrix(paths, self.columns)
        if not np.any(self.ref_ok):
            return np.zeros(stats.shape[0])  # nothing to score against; filter no-op
        gaps = np.abs(stats - self.reference)
        # NaN handling (anti-gaming): decade-NaN against a finite reference is a
        # penalty; a reference-NaN component is uninformative and is dropped.
        gaps[:, ~self.ref_ok] = np.nan
        penalty = np.isnan(gaps) & self.ref_ok[None, :]
        scored = gaps / self.scale
        scored[penalty] = _NAN_PENALTY
        # every row has at least one non-NaN entry: penalty cells were filled
        # above and ref-NaN columns are excluded from the mean by nanmean.
        return np.nanmean(scored, axis=1)


# --------------------------------------------------------------------------- #
# "no L1": the climate layer replaced by its posterior mean (WP2.10 system C)
# --------------------------------------------------------------------------- #


def frozen_climate(
    climate: ClimateArtifact,
    *,
    months: int,
    s0_date: str | None = None,
    seed: int = 0,
) -> SimulatedClimate:
    """A one-decade :class:`SimulatedClimate` with NO climate dynamics at all.

    Every month carries the same state vector — the posterior MEAN of the smoothed
    state at ``s0_date`` (the artifact's last fitted month by default) — and every
    waypoint parameter is the posterior mean of its draws. Deterministic: no RNG is
    consumed, and ``seed`` is recorded only so the returned object says which decade
    stream it stands in for.

    This is what :attr:`JoineryConfig.use_climate` ``= False`` substitutes for
    :func:`~ah.gen.climate.simulate.simulate_decades`. It removes the climate layer's
    two contributions at once — the *path* (slow states stop moving) and the
    *parameter uncertainty* (every decade gets the same θ) — which is exactly the
    pair DN-1.1 §II.7 asks system C to do without. ``theta_index`` is ``-1``: no
    posterior draw was selected, and a reader of the lineage must not be able to
    mistake the mean for a draw.
    """
    from ah.gen.climate.simulate import N_STATES, PARAM_NAMES

    ts = climate.dates[-1] if s0_date is None else pd.Timestamp(s0_date)
    locs = climate.dates.get_indexer([ts])
    if locs[0] < 0:
        raise wp.JoineryError(
            f"s0_date {ts.date()} is not on the climate artifact's monthly grid "
            f"({climate.dates[0].date()} .. {climate.dates[-1].date()})"
        )
    t0 = int(locs[0])
    mean_state = np.asarray(climate.states[:, t0, :], dtype=np.float64).mean(axis=0)
    states = np.broadcast_to(mean_state, (1, months, N_STATES)).copy()
    params = {
        name: np.array([float(np.mean(climate.params[name]))], dtype=np.float64)
        for name in PARAM_NAMES
    }
    return SimulatedClimate(
        states=states,
        theta_index=np.array([-1], dtype=np.int64),
        params=params,
        s0_date=ts,
        seed=int(seed),
    )


# --------------------------------------------------------------------------- #
# per-decade generation (steps 1-5 for one decade index)
# --------------------------------------------------------------------------- #


@dataclass
class _DecadeResult:
    path: np.ndarray  # (months, n_factors), reconciled
    waypoints: wp.DecadeWaypoints
    reconciliation: rc.DecadeReconciliation
    support: dict[str, Any]
    decade_index: int


@dataclass
class _DecadePrep:
    """Steps 1-3 for one decade: the skeleton a block sampler then fills in.

    Split out from :class:`_DecadeResult` so many decades can be prepared before
    any of them is bridged — that is what lets the bridge batch the block
    sampler across decades (WP2.8b). Nothing here consumes the block stream:
    ``rng`` is decade ``m``'s untouched ``PCG64(seed + blocks_offset + 7919*m)``.
    """

    decade_index: int
    sim: SimulatedClimate
    waypoints: wp.DecadeWaypoints
    targets: wp.MonthlyTargets
    rng: np.random.Generator


class _DecadeFactory:
    """Generates decade ``m`` reproducibly from the layer base seeds.

    A single-decade ``simulate_*`` call with base seed ``seed + 7919*m`` opens
    exactly the stream a batched call would give decade ``m`` — the platform
    seed rule makes per-decade generation and batched generation bit-identical,
    which is what lets the acceptance filter resample decade ``n+j`` without
    re-running the whole ensemble. The block sampler preserves the same property
    across its own batching (a fixed batch width, padded — see
    :class:`ah.gen.blocks.diffusion.DiffusionBlockSampler`).
    """

    def __init__(
        self,
        *,
        climate: ClimateArtifact,
        regimes_artifact: RegimesArtifact,
        source: BootstrapSource,
        stats: wp.SourceStats,
        support_ref: sp.SupportReference,
        sampler: bridge.BlockSampler,
        config: JoineryConfig,
        months: int,
        seed: int,
        world: NumericWorld | None,
        guidance: bridge.GuidanceHook | None,
    ) -> None:
        self.climate = climate
        self.regimes_artifact = regimes_artifact
        self.source = source
        self.stats = stats
        self.support_ref = support_ref
        self.sampler = sampler
        self.config = config
        self.months = months
        self.seed = seed
        self.world = world
        self.guidance = guidance

    def _simulate_layers(self, m: int) -> tuple[SimulatedClimate, RegimePaths]:
        l1_seed = self.seed + LAYER_SEED_OFFSETS["climate"] + SEED_STRIDE * m
        l2_seed = self.seed + LAYER_SEED_OFFSETS["regimes"] + SEED_STRIDE * m
        if self.config.use_climate:
            sim = simulate_decades(
                self.climate, 1, seed=l1_seed, months=self.months, s0_date=self.config.s0_date
            )
        else:
            # System C: L1 replaced by its posterior mean, frozen. No RNG is drawn
            # here, so l1_seed is deliberately unused -- the decade's remaining
            # randomness (L2's chain, L3's blocks) still runs on its own streams.
            sim = frozen_climate(
                self.climate, months=self.months, s0_date=self.config.s0_date, seed=l1_seed
            )
        if self.world is None:
            regimes = simulate_regimes(self.regimes_artifact, sim.states, seed=l2_seed)
        else:
            regimes = regime_path_for_world(
                self.regimes_artifact,
                self.world.regimes,
                self.world.horizon,
                n_paths=1,
                seed=l2_seed,
            )
        if self.config.two_pass:
            # Same seed -> same theta/s0/innovations; only the credit-gap forcing
            # L_bar = delta_L * c_t changes (see the module docstring).
            sim = simulate_decades(
                self.climate,
                1,
                seed=l1_seed,
                months=self.months,
                s0_date=self.config.s0_date,
                cycle=regimes.cycle,
            )
        return sim, regimes

    def prepare(self, m: int) -> _DecadePrep:
        """Steps 1-3 for decade ``m`` (L1, L2, waypoints) — no block sampling yet."""
        sim, regimes = self._simulate_layers(m)
        conditions = None if self.world is None else self.world.factor_conditions
        waypoints = wp.build_waypoints(sim, regimes, self.stats, conditions=conditions)[0]
        return _DecadePrep(
            decade_index=m,
            sim=sim,
            waypoints=waypoints,
            # System B: `targets=None` is the bridge's documented unbound mode --
            # every waypoint increment in c_b becomes zero.
            targets=(
                wp.monthly_targets(waypoints, self.months) if self.config.bind_waypoints else None
            ),
            rng=np.random.Generator(
                np.random.PCG64(self.seed + LAYER_SEED_OFFSETS["blocks"] + SEED_STRIDE * m)
            ),
        )

    def assemble(self, preps: Sequence[_DecadePrep]) -> list[_DecadeResult]:
        """Steps 4-5 for prepared decades: bridge them together, then reconcile.

        The bridge sees every decade at once, so a batched sampler evaluates its
        network once per block index instead of once per (decade, block). Steps
        5 and 6 are untouched by that: reconciliation is per decade and per year
        and still runs on a complete decade path, and the acceptance filter still
        scores fully assembled, fully reconciled decades.
        """
        outputs = bridge.assemble_decade_paths(
            months=self.months,
            decades=[
                bridge.DecadeAssembly(
                    waypoints=p.waypoints,
                    targets=p.targets,
                    states_row=p.sim.states[0],
                    rng=p.rng,
                )
                for p in preps
            ],
            sampler=self.sampler,
            stats=self.stats,
            stride=self.config.block_stride,
            guidance=self.guidance,
        )
        names = tuple(self.sampler.factor_names)
        results: list[_DecadeResult] = []
        for prep, (raw, conds) in zip(preps, outputs, strict=True):
            if self.config.bind_waypoints:
                reconciled, diagnostics = rc.reconcile_decade(
                    raw, names, prep.waypoints, self.config.reconcile
                )
            else:
                # System B/C: step 5 does not run. An empty DecadeReconciliation is
                # the honest record (no factor was adjusted); note that the floor
                # RE-application inside reconcile_decade does not run either -- see
                # JoineryConfig.bind_waypoints.
                reconciled, diagnostics = raw, rc.DecadeReconciliation()
            results.append(
                _DecadeResult(
                    path=reconciled,
                    waypoints=prep.waypoints,
                    reconciliation=diagnostics,
                    support=sp.decade_support(conds, prep.waypoints.labels, self.support_ref),
                    decade_index=prep.decade_index,
                )
            )
        return results

    def generate(self, m: int) -> _DecadeResult:
        """One decade end to end (steps 1-5). Kept for single-decade callers."""
        return self.assemble([self.prepare(m)])[0]

    def decade_seed(self, m: int, layer: str = "climate") -> int:
        return self.seed + LAYER_SEED_OFFSETS[layer] + SEED_STRIDE * m


# --------------------------------------------------------------------------- #
# the 7-step assembly
# --------------------------------------------------------------------------- #


def assemble_decades(
    *,
    climate: ClimateArtifact,
    regimes_artifact: RegimesArtifact,
    source: BootstrapSource,
    n_decades: int,
    seed: int,
    months: int = 120,
    world: NumericWorld | None = None,
    sampler: bridge.BlockSampler | None = None,
    config: JoineryConfig | None = None,
    guidance: bridge.GuidanceHook | None = None,
) -> Ensemble:
    """DN-1.1 §II.5 steps 1-7 over ``n_decades`` decades. See the module docstring.

    ``world`` switches step 2 to the WorldSpec regime modes and binds its
    ``factor_conditions`` at step 3; ``None`` uses the fitted semi-Markov
    skeleton and no conditions. ``sampler`` defaults to the bootstrap stand-in
    (:class:`~ah.gen.joinery.bridge.BootstrapBlockSampler`); WP2.8/2.9 pass
    their trained samplers through the same protocol.
    """
    if n_decades < 1:
        raise wp.JoineryError("n_decades must be >= 1")
    config = JoineryConfig() if config is None else config
    if world is not None and int(world.horizon.quarters) * 3 != months:
        raise wp.JoineryError(
            f"world horizon covers {int(world.horizon.quarters) * 3} months but the "
            f"assembly asked for {months} — the horizon binds"
        )
    if sampler is None:
        sampler = bridge.BootstrapBlockSampler(source, block_months=config.block_months)

    stats = wp.source_stats(source, climate)
    support_ref = sp.build_support_reference(source, climate, quantile=config.support_quantile)
    factory = _DecadeFactory(
        climate=climate,
        regimes_artifact=regimes_artifact,
        source=source,
        stats=stats,
        support_ref=support_ref,
        sampler=sampler,
        config=config,
        months=months,
        seed=seed,
        world=world,
        guidance=guidance,
    )

    # Steps 1-5 for every decade. Prepared first, bridged together: a batched
    # block sampler evaluates its network once per block index across all
    # decades instead of once per (decade, block) — WP2.8b, throughput only.
    results = factory.assemble([factory.prepare(m) for m in range(n_decades)])

    # -- step 6: the acceptance filter -------------------------------------- #
    paths = np.stack([r.path for r in results])
    rejections: list[dict[str, Any]] = []
    n_reject = int(np.floor(config.max_reject_fraction * n_decades))
    if config.acceptance_filter and n_reject > 0:
        scorer = _FilterScorer(paths, source)  # reference + scale frozen on this ensemble
        scores = scorer.scores(paths)
        # worst-decile indices, deterministic tie-break by decade index
        order = np.lexsort((np.arange(n_decades), -scores))
        rejected = [int(i) for i in order[:n_reject]]
        # Replacements are drawn from fresh decade indices n, n+1, ... on the
        # same layer streams; they are independent of each other, so they are
        # prepared and bridged as one batch too. Each still reopens exactly the
        # stream its index names, and each is still accepted unconditionally.
        replacements = factory.assemble([factory.prepare(n_decades + j) for j in range(n_reject)])
        for j, idx in enumerate(rejected):
            replacement_index = n_decades + j
            replacement = replacements[j]
            replacement_score = float(scorer.scores(replacement.path[None, ...])[0])
            rejections.append(
                {
                    "decade": idx,
                    "score": float(scores[idx]),
                    "decade_seed": factory.decade_seed(idx),
                    "replacement_index": replacement_index,
                    "replacement_seed": factory.decade_seed(replacement_index),
                    "replacement_score": replacement_score,
                    "scores_by_component": None,  # component detail lives in the score matrix
                }
            )
            results[idx] = replacement
        paths = np.stack([r.path for r in results])

    # -- step 7: emit the ensemble with full lineage ------------------------- #
    recon_summary = _aggregate_reconciliation(results)
    support_summary = _aggregate_support(results, config)
    tolerance = {
        "n_decades_ok": int(sum(1 for r in results if r.reconciliation.tolerance_ok)),
        "all_ok": bool(all(r.reconciliation.tolerance_ok for r in results)),
        "floor_clamped_cells": int(sum(r.reconciliation.floor_clamped_cells for r in results)),
        # years whose annual target was infeasible under the hard floor (the floor
        # wins by design); exempted from the tolerance check, counted here.
        "n_floor_bound_years": int(
            sum(f.n_floor_bound_years for r in results for f in r.reconciliation.factors.values())
        ),
    }

    fallback = getattr(sampler, "fallback_counts", None)
    conditioning: dict[str, Any] = {
        "system": "L1+L2+L4 (bootstrap stand-in blocks)",
        "one_pass": not config.two_pass,
        # WP2.10: which of DN-1.1 §II.5's steps actually ran. A reader of an
        # ablation ensemble must not have to infer this from an empty diagnostic.
        "waypoints_bound": bool(config.bind_waypoints),
        "reconciliation_applied": bool(config.bind_waypoints),
        "floors_reapplied_post_denton": bool(config.bind_waypoints),
        "climate_layer": "simulated" if config.use_climate else "frozen-posterior-mean",
        "layer_seeds": {layer: seed + offset for layer, offset in LAYER_SEED_OFFSETS.items()},
        "seed_stride": SEED_STRIDE,
        "layer_artifacts": {
            "climate_sha256": str(climate.meta.get("content_sha256")),
            "regimes_sha256": str(regimes_artifact.meta.get("content_sha256")),
            "regimes_pins_climate_sha256": str(
                regimes_artifact.meta.get("climate_artifact_sha256")
            ),
        },
        "ruleset_version": str(regimes_artifact.meta.get("ruleset_version", "unknown")),
        "regime_mode": "semimarkov" if world is None else str(world.regimes.mode),
        "factor_conditions": results[0].waypoints.record,
        # WP2.7b: the ig_spread band is regime-conditional; its width, the effective
        # sample size behind each width and the estimator's constants travel with
        # every ensemble, because the reconciliation diagnostic cannot be read
        # without them.
        "spread_band": stats.spread_band_diagnostics,
        "cb_contract": {
            "schema": bridge.C_B_SCHEMA_VERSION,
            "components": list(bridge.C_B_COMPONENTS),
            "fingerprint": bridge.contract_fingerprint(),
        },
        "config": config.as_dict(),
        "acceptance_filter": {
            "enabled": bool(config.acceptance_filter),
            "metrics": list(FILTER_METRICS),
            "factors": list(FILTER_FACTORS),
            "max_reject_fraction": float(config.max_reject_fraction),
            "n_rejected": len(rejections),
            "rejections": rejections,
        },
        "support": support_summary,
        "reconciliation": recon_summary,
        "waypoint_tolerance": tolerance,
        "block_sampler": type(sampler).__name__,
        # WP2.8b: how many decades one network evaluation carried, and where it
        # ran. Part of the lineage because a batched float32 GEMM is not
        # batch-size invariant — two ensembles at the same seed and different
        # widths agree to round-off, not bit for bit, and a reader must be able
        # to see which width produced the numbers in front of them.
        "block_sampler_batch": int(getattr(sampler, "block_batch", 1)),
        "block_sampler_device": str(getattr(sampler, "device", "cpu")),
        "sampler_fallbacks": dict(fallback) if fallback else {},
        "factor_conditions_honoured": world is not None,
        "strategy_mapping": "deferred to Step 3 (WS-C mappings; DN-1.1 II.5 step 7 note)",
    }

    meta = EnsembleMeta(
        generator_id=GENERATOR_ID,
        vintage_id=source.vintage_id,
        seed=int(seed),
        n_paths=int(n_decades),
        months=int(months),
        checkpoint_hash=None,
        config_hash=None,
        conditioning=conditioning,
        active_blocks=tuple(source.active_blocks),
    )
    return Ensemble(paths=paths, factor_names=list(sampler.factor_names), meta=meta)


def _aggregate_reconciliation(results: list[_DecadeResult]) -> dict[str, Any]:
    """The reconciliation-diagnostic distribution across decades, per factor."""
    per_factor: dict[str, Any] = {}
    for name in rc.VARIANT_BY_FACTOR:
        means = np.array(
            [
                float(r.reconciliation.factors[name].adjustment_by_year.mean())
                for r in results
                if name in r.reconciliation.factors
            ]
        )
        if means.size == 0:
            continue
        flagged = sum(
            1
            for r in results
            if name in r.reconciliation.factors and r.reconciliation.factors[name].flagged
        )
        per_factor[name] = {
            "variant": rc.VARIANT_BY_FACTOR[name],
            "mean_abs_adjustment_p50": float(np.quantile(means, 0.50)),
            "mean_abs_adjustment_p90": float(np.quantile(means, 0.90)),
            "mean_abs_adjustment_max": float(means.max()),
            "n_flagged_decades": int(flagged),
        }
    return {"per_factor": per_factor, "n_decades": len(results)}


def _aggregate_support(results: list[_DecadeResult], config: JoineryConfig) -> dict[str, Any]:
    shares = [float(r.support["extrapolation_share"]) for r in results]
    tvs = [float(r.support["regime_freq_tv"]) for r in results]
    pooled: dict[str, float] = {}
    for label in wp.REGIME_LABELS:
        pooled[label] = float(np.mean([r.support["regime_frequencies"][label] for r in results]))
    return {
        "quantile": float(config.support_quantile),
        "extrapolation_share_by_decade": shares,
        "extrapolation_share_mean": float(np.mean(shares)),
        "extrapolation_share_max": float(np.max(shares)),
        "n_flagged_off_support": int(sum(1 for r in results if r.support["flag_off_support"])),
        "regime_freq_tv_by_decade": tvs,
        "regime_freq_tv_mean": float(np.mean(tvs)),
        "regime_frequencies_pooled": pooled,
    }


# --------------------------------------------------------------------------- #
# the Generator wrapper + registration
# --------------------------------------------------------------------------- #


class JoineryBootstrapV0:
    """The assembled L1+L2+L4 system with bootstrap stand-in blocks.

    Implements :class:`ah.gen.base.Generator`. The id is NOT in the schema's
    ``generator_id`` enum (the same wall ``bootstrap-v1`` hit; STEP2R §WP2R.6
    bumps the enum) — authored worlds reach this system in WP2.10 when
    ``systems.py`` names the ablation compositions; until then research callers
    resolve it by id or call :func:`assemble_decades` directly.
    """

    generator_id = GENERATOR_ID

    def __init__(
        self,
        climate: ClimateArtifact,
        regimes_artifact: RegimesArtifact,
        source: BootstrapSource,
        config: JoineryConfig | None = None,
    ) -> None:
        self._climate = climate
        self._regimes = regimes_artifact
        self._source = source
        self._config = JoineryConfig() if config is None else config

    def fit(self, data: Any) -> None:
        """Adopt a prepared :class:`BootstrapSource` (nothing to estimate here)."""
        if not isinstance(data, BootstrapSource):
            raise wp.JoineryError(
                f"{GENERATOR_ID}.fit expects a BootstrapSource; got {type(data).__name__}"
            )
        self._source = data

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = int(world.horizon.quarters) * 3
        return assemble_decades(
            climate=self._climate,
            regimes_artifact=self._regimes,
            source=self._source,
            n_decades=n_paths,
            seed=seed,
            months=months,
            world=world,
            config=self._config,
        )

    def sample_months(
        self, months: int, n_paths: int, seed: int, *, unfiltered: bool = False
    ) -> Ensemble:
        """Research entry point: no WorldSpec, fitted regimes, optional filter-off."""
        config = replace(self._config, acceptance_filter=False) if unfiltered else self._config
        return assemble_decades(
            climate=self._climate,
            regimes_artifact=self._regimes,
            source=self._source,
            n_decades=n_paths,
            seed=seed,
            months=months,
            config=config,
        )


def joinery_bootstrap_v0_factory() -> JoineryBootstrapV0:
    """Construct the assembled system from the pinned artifacts + campaign source.

    Raises if the artifacts are absent or their content hashes do not match the
    pinned fit-report values — a joinery running on unpinned layers would break
    the lineage claim every ensemble makes.
    """
    from ah.gen.bootstrap import campaign_source

    climate = load_climate_artifact(DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = load_regimes_artifact(DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise wp.JoineryError(
            f"climate artifact sha {climate.meta['content_sha256'][:16]}... != pinned "
            f"{PINNED_CLIMATE_SHA256[:16]}..."
        )
    if regimes_artifact.meta["content_sha256"] != PINNED_REGIMES_SHA256:
        raise wp.JoineryError(
            f"regimes artifact sha {regimes_artifact.meta['content_sha256'][:16]}... != "
            f"pinned {PINNED_REGIMES_SHA256[:16]}..."
        )
    return JoineryBootstrapV0(climate, regimes_artifact, campaign_source())


registry.register(GENERATOR_ID, joinery_bootstrap_v0_factory)
