"""The stress-scenario compiler (bootstrap-stratified).

Severity ranking of historical months for stress-scenario selection.
Three functionals: equity (rank by equity alone), joint_risk (equity + credit),
all_down (equity + credit + yields, the default — closes the flight-to-quality escape valve).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ah.core.numericworld import NumericWorld
from ah.core.worldspec import StressSegment, StressSpec
from ah.gen import registry
from ah.gen.base import AbsentLayer, Ensemble, EnsembleMeta, Generator, RegimeRecord
from ah.gen.bootstrap import REGIME_LABELS, BootstrapSource


class StressError(ValueError):
    """Raised for any bootstrap-stratified stress-sampler misuse: an unfitted
    generator, a world with no declared x_stress, a quarter no segment covers,
    or a spec/args combination the sampler cannot honour."""


def _z(column: np.ndarray) -> np.ndarray:
    sd = float(column.std())
    if sd == 0.0:
        return np.zeros_like(column)
    return (column - float(column.mean())) / sd


def severity_score(values: np.ndarray, factor_names: Sequence[str], functional: str) -> np.ndarray:
    """One severity score per row; LOWER IS MORE SEVERE.

    Components are z-scored so a spread in percentage points cannot dominate a
    return in decimals. Credit and yields enter NEGATED: a wide spread and a
    rising yield are both adverse, so negating them puts "bad" at the bottom
    alongside a negative equity return.
    """
    names = list(factor_names)
    x = np.asarray(values, dtype=np.float64)

    def col(name: str) -> np.ndarray:
        if name not in names:
            raise ValueError(f"panel has no factor '{name}'; available: {names}")
        return x[:, names.index(name)]

    equity = _z(col("equity_mkt"))
    if functional == "equity":
        return equity
    credit = -_z(col("hy_spread"))
    if functional == "joint_risk":
        return equity + credit
    if functional == "all_down":
        # a RISING long yield is adverse (no flight-to-quality bid), so the
        # bond leg enters negated exactly as credit does
        return equity + credit + -_z(col("ust_10y"))
    raise ValueError(
        f"unknown severity functional '{functional}'; known: equity, joint_risk, all_down"
    )


def eligible_rows(scores: np.ndarray, percentile: float) -> np.ndarray:
    """Row indices whose severity is at or below ``percentile`` (100 = all).

    Never empty: a percentile tight enough to select nothing would make its
    segment unsamplable, so the single worst row is the floor.
    """
    s = np.asarray(scores, dtype=np.float64)
    if percentile >= 100.0:
        return np.arange(s.size, dtype=np.int64)
    keep = max(1, int(np.floor(s.size * percentile / 100.0)))
    return np.sort(np.argsort(s, kind="stable")[:keep]).astype(np.int64)


#: Of the sealed 14-factor panel, these nine are LEVELS rather than increments.
#: Splicing a level at a block join teleports it; splicing a return does not.
LEVEL_FACTORS: tuple[str, ...] = (
    "equity_vol",
    "ig_spread",
    "hy_spread",
    "policy_rate",
    "ust_2y",
    "ust_10y",
    "cpi",
    "hqm_curve",
    "funding_spread",
)


def join_candidates(
    values: np.ndarray,
    factor_names: Sequence[str],
    current_row: int,
    tolerance: Mapping[str, float],
    pool: np.ndarray,
) -> np.ndarray:
    """Rows in ``pool`` reachable from ``current_row`` without a level teleport.

    A factor with no declared tolerance does not constrain. May return an empty
    array; the caller decides what to do (the sampler continues the block).
    """
    names = list(factor_names)
    x = np.asarray(values, dtype=np.float64)
    keep = np.ones(pool.size, dtype=bool)
    for factor, tol in tolerance.items():
        if factor not in names:
            raise ValueError(f"join tolerance names unknown factor '{factor}'")
        column = x[:, names.index(factor)]
        keep &= np.abs(column[pool] - column[int(current_row)]) <= float(tol)
    return pool[keep]


def _segment_for(stress: StressSpec, quarter: int) -> StressSegment:
    """The segment covering ``quarter``.

    Raises :class:`StressError` naming the quarter when no segment covers it.
    ``StressSpec`` only checks that its segments tile with no gap or overlap;
    it never checks against a world's horizon, so a scenario that ends short
    of the sampled horizon must fail loudly here rather than silently running
    past the declared stress window.
    """
    for seg in stress.segments:
        if seg.from_quarter <= quarter <= seg.to_quarter:
            return seg
    last = max(seg.to_quarter for seg in stress.segments)
    raise StressError(
        f"quarter {quarter} is covered by no stress segment; segments end at quarter {last}"
    )


class StressBootstrap:
    """The stress-scenario compiler. Implements ah.gen.base.Generator."""

    generator_id = "bootstrap-stratified"

    def __init__(self, source: BootstrapSource | None = None) -> None:
        self._source = source

    @property
    def source(self) -> BootstrapSource:
        if self._source is None:
            raise StressError("bootstrap-stratified is not fitted; call fit(campaign_source())")
        return self._source

    def fit(self, data: Any) -> None:
        if not isinstance(data, BootstrapSource):
            raise StressError(
                f"fit expects a BootstrapSource (see ah.gen.bootstrap.campaign_source); "
                f"got {type(data).__name__}"
            )
        self._source = data

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        if world.stress is None:
            raise StressError(
                f"world '{world.world_id}' selects bootstrap-stratified but declares no "
                "extensions.x_stress; a stress world must declare its severity rule"
            )
        months = int(world.horizon.quarters) * 3
        return self.sample_months(months, n_paths, seed, world=world, stress=world.stress)

    def sample_months(
        self,
        months: int,
        n_paths: int,
        seed: int,
        *,
        world: NumericWorld | None = None,
        stress: StressSpec | None = None,
    ) -> Ensemble:
        source = self.source
        if stress is None:
            raise StressError("bootstrap-stratified requires a StressSpec")
        months, n_paths = int(months), int(n_paths)
        if months < 1 or n_paths < 1:
            raise StressError(f"months and n_paths must be >= 1; got {months}, {n_paths}")

        scores = severity_score(source.values, source.factor_names, stress.functional)
        # Every DECLARED segment's pool is built up front -- pool_sizes below
        # stamps the whole spec, not just whatever the sampled months happen
        # to touch, so a segment past the sampled horizon still gets a size.
        per_segment_pool: dict[int, np.ndarray] = {
            seg.from_quarter: eligible_rows(scores, seg.entry_percentile) for seg in stress.segments
        }
        # month -> (pool, restart probability) from the segment covering it
        pools: list[np.ndarray] = []
        probs: list[float] = []
        for m in range(months):
            quarter = m // 3
            seg = _segment_for(stress, quarter)
            pools.append(per_segment_pool[seg.from_quarter])
            probs.append(1.0 / float(seg.mean_block_months))

        index = self._draw(source, months, n_paths, seed, pools, probs, stress.join_tolerance)
        paths = source.values[index]

        label_codes = {label: i for i, label in enumerate(REGIME_LABELS)}
        source_codes = np.array([label_codes[label] for label in source.labels], dtype=np.int64)

        conditioning = {
            "mode": "declared-stress-scenario",
            "functional": stress.functional,
            "segments": [
                {
                    "from_quarter": s.from_quarter,
                    "to_quarter": s.to_quarter,
                    "entry_percentile": s.entry_percentile,
                    "mean_block_months": s.mean_block_months,
                }
                for s in stress.segments
            ],
            "pool_sizes": [int(per_segment_pool[s.from_quarter].size) for s in stress.segments],
            "join_tolerance": dict(stress.join_tolerance),
            "precedent": list(stress.precedent),
            "ruleset_version": source.ruleset_version,
            "block_draw_span": {
                "start": str(source.dates[0].date()),
                "end": str(source.dates[-1].date()),
                "months": source.n_rows,
            },
            # This generator honours no factor_conditions either: severity is
            # declared through x_stress, not through an inflation average.
            "factor_conditions_honoured": False,
            # Spec v0.2 (S5): a hand-declared scenario. A reverse-search world
            # (D-SC-3, not built) would stamp "search-derived" here instead.
            "provenance": "declared",
        }
        if world is not None:
            conditioning["world_id"] = world.world_id
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id=source.vintage_id,
            seed=int(seed),
            n_paths=n_paths,
            months=months,
            conditioning=conditioning,
            active_blocks=tuple(source.active_blocks),
        )
        return Ensemble(
            paths=paths,
            factor_names=list(source.factor_names),
            meta=meta,
            row_indices=index,
            regimes=RegimeRecord(
                labels=source_codes[index],
                legend=REGIME_LABELS,
                mode="realized-declared-stress",
                ruleset_version=source.ruleset_version,
            ),
            slow_states=AbsentLayer(reason="a resampler has no slow-state layer"),
        )

    def _draw(
        self,
        source: BootstrapSource,
        months: int,
        n_paths: int,
        seed: int,
        pools: list[np.ndarray],
        probs: list[float],
        tolerance: Mapping[str, float],
    ) -> np.ndarray:
        n = source.n_rows
        index = np.empty((n_paths, months), dtype=np.int64)

        for p in range(n_paths):
            # Each path draws from its own independent stream (a PCG64 jump of
            # p * 2**128 steps): path p's tape then depends only on (seed, p),
            # never on how many OTHER paths are being drawn alongside it. A
            # single shared stream consumed path-major (draw all path-0
            # values, then path-1, ...) would make an earlier path's outcome
            # depend on n_paths, because the entry draw at m=0 and every
            # restart's destination draw consume a variable, path-count-
            # dependent number of stream words before the next path starts.
            rng = np.random.Generator(np.random.PCG64(int(seed)).jumped(p))
            first = pools[0]
            index[p, 0] = int(first[rng.integers(0, first.size)])
            for m in range(1, months):
                pool = pools[m]
                previous = int(index[p, m - 1])
                advanced = (previous + 1) % n
                trigger = rng.random()
                if trigger >= probs[m]:
                    index[p, m] = advanced
                    continue
                # Exclude the current row itself: with an exact-match tolerance
                # (e.g. 0.0) a row trivially matches itself, which would count
                # as a "reachable join" that goes nowhere. A join must land
                # somewhere other than where the block already is.
                candidates = join_candidates(
                    source.values,
                    source.factor_names,
                    previous,
                    tolerance,
                    pool[pool != previous],
                )
                # Severity is a preference over entries, never a licence to
                # teleport: with nothing reachable the block simply continues.
                index[p, m] = (
                    advanced
                    if candidates.size == 0
                    else int(candidates[rng.integers(0, candidates.size)])
                )
        return index


def stress_or_legacy_factory() -> Generator:
    """The `bootstrap-stratified` id serves two masters (spec v0.2 erratum).

    Sealed 1.0.x worlds carry the id as a deprecated alias for bootstrap-v1 and
    declare no x_stress; they must keep resolving to the legacy factory
    bit-identically. A stress world declares extensions.x_stress and routes to
    the compiler. Dispatch happens at sample() time on the world itself.
    """
    return _StressOrLegacyDispatch()


class _StressOrLegacyDispatch:
    generator_id = "bootstrap-stratified"

    def __init__(self) -> None:
        self._source: BootstrapSource | None = None

    @property
    def source(self) -> BootstrapSource:
        """The campaign panel - identical for both dispatch routes (the legacy
        generator and the compiler are both fitted from campaign_source()), so
        the adapter's source-space derivations (_source_of) are route-blind."""
        if self._source is None:
            from ah.gen.bootstrap import campaign_source

            self._source = campaign_source()
        return self._source

    def fit(self, data: Any) -> None:  # parity with the Generator protocol
        raise StressError("the dispatcher is not fitted; it resolves per world")

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        from ah.gen.bootstrap import bootstrap_v1_factory

        if world.stress is None:
            return bootstrap_v1_factory().sample(world, n_paths, seed)
        gen = StressBootstrap()
        gen.fit(self.source)
        return gen.sample(world, n_paths, seed)


registry.register("bootstrap-stratified", stress_or_legacy_factory)
