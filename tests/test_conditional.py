"""WP2.2 Task 6 acceptance: condition adherence + off-support degradation.

Mirrors ``tests/test_economics.py``/``tests/test_calibration.py``'s conventions.
This suite's defining property is different from every other WP2.2 suite: its metrics
REGENERATE ensembles from checked-in/swept WorldSpec worlds via the generator the
ensemble under test was itself produced by (see
``ah.eval.metrics.conditional``'s module docstring), so most tests here register a
small, deterministic, hand-built :class:`~ah.gen.base.Generator` test double via
``ah.gen.registry.register`` (mirroring ``tests/test_gen_registry.py``'s ``_FakeGen``)
rather than constructing an ensemble directly.
"""

from __future__ import annotations

import ast
import itertools
import json
import math
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

import ah.eval.metrics.conditional as conditional_mod
from ah.core.loader import load_worldspec, worldspec_schema
from ah.core.numericworld import NumericWorld
from ah.eval.metrics.conditional import (
    CONDITION_TYPES,
    CONDITIONAL_MC_ERROR_REPLICATES,
    CONDITIONAL_MIN_OBS,
    CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT,
    FIXTURES_DIR,
    OFF_SUPPORT_LEVELS,
    OFF_SUPPORT_TYPES,
    ConditionalFixtureError,
    build_conditional_suite,
    conditional_mc_error,
    load_conditional_test_worlds,
)
from ah.eval.reference import PANEL_STATS, ReferenceStats
from ah.factors import FactorManifest, load_manifest
from ah.gen import registry as gen_registry
from ah.gen.base import Ensemble, EnsembleMeta

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _isolate_generator_registry() -> Iterator[None]:
    """Restore ``ah.gen.registry``'s global table (and this suite's regeneration memo).

    Every test here registers test-double generators into a PROCESS-GLOBAL dict; without
    a teardown they leak into every later test module in the session, and a memoized
    regeneration could outlive the registry entry that produced it. Both are restored.
    """
    saved = dict(gen_registry._REGISTRY)
    conditional_mod.clear_regeneration_cache()
    try:
        yield
    finally:
        gen_registry._REGISTRY.clear()
        gen_registry._REGISTRY.update(saved)
        conditional_mod.clear_regeneration_cache()


def _manifest() -> FactorManifest:
    return load_manifest()


def _empty_reference(manifest: FactorManifest) -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=manifest.active_blocks,
        vintage_id="v",
        n_resamples=1,
        seed=0,
        missing_factors=(),
    )


_N_HISTORY_MONTHS = 420


def _historical_series(seed: int = 7) -> dict[str, pd.Series]:
    """Synthetic cpi/policy_rate history with REAL dispersion in BOTH swept quantities.

    The cpi level is a random walk in log space, NOT deterministic geometric growth. That
    distinction is the whole point: under ``100 * 1.025**(m/12)`` the trailing-12m YoY
    inflation is a CONSTANT 2.5 and its ``std(ddof=1)`` is ~1e-14 (nonzero only by float
    error), so every swept inflation target collapses onto the historical mean and the
    inflation arm of Part B contributes ~zero error at every distance level -- the sweep
    would pass identically with that arm deleted. A real log random walk gives YoY a real
    mean and standard deviation, so ``mean(X) + z*std(X)`` actually moves with ``z``.
    """
    dates = pd.date_range("1990-01-01", periods=_N_HISTORY_MONTHS, freq="MS")
    rng = np.random.Generator(np.random.PCG64(seed))
    # ~3%/yr mean inflation with genuine month-to-month variation -> YoY mean ~3pp,
    # YoY std ~1.4pp.
    monthly_log_inflation = rng.normal(0.03 / 12.0, 0.004, size=_N_HISTORY_MONTHS)
    cpi = pd.Series(100.0 * np.exp(np.cumsum(monthly_log_inflation)), index=dates)
    policy_rate = pd.Series(3.0 + rng.normal(0.0, 1.0, size=_N_HISTORY_MONTHS), index=dates)
    return {"cpi": cpi, "policy_rate": policy_rate}


def _reference_with_series(
    manifest: FactorManifest, series: dict[str, pd.Series]
) -> ReferenceStats:
    empty = _empty_reference(manifest)
    return ReferenceStats(
        blocks=empty.blocks,
        cross_blocks=empty.cross_blocks,
        active_blocks=empty.active_blocks,
        vintage_id=empty.vintage_id,
        n_resamples=empty.n_resamples,
        seed=empty.seed,
        missing_factors=empty.missing_factors,
        historical_series=series,
    )


def _historical_reference(manifest: FactorManifest) -> ReferenceStats:
    """A reference carrying real ``historical_series`` for cpi/policy_rate, so Part B's
    off-support sweep has a real support distribution to sweep against."""
    return _reference_with_series(manifest, _historical_series())


def _dummy_ensemble(generator_id: str, seed: int = 0) -> Ensemble:
    """A tiny placeholder ensemble whose OWN paths are irrelevant -- every metric in
    this suite regenerates fresh ensembles from ``generator_id``, never reading
    ``ensemble.paths`` (see the module docstring)."""
    meta = EnsembleMeta(generator_id=generator_id, vintage_id="v", seed=seed, n_paths=2, months=6)
    return Ensemble(paths=np.zeros((2, 6, 1)), factor_names=["x"], meta=meta)


def _months(world: NumericWorld) -> int:
    return world.horizon.quarters * 3


class _PerfectGenerator:
    """Honours every WorldSpec condition EXACTLY, by construction."""

    generator_id = "conditional-test-perfect"

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = _months(world)
        fc = world.factor_conditions
        cpi = np.full((n_paths, months), 100.0, dtype=np.float64)
        if fc.inflation is not None and fc.inflation.average_pct is not None:
            target = fc.inflation.average_pct
            growth = (1.0 + target / 100.0) ** (1.0 / 12.0)
            levels = 100.0 * growth ** np.arange(months, dtype=np.float64)
            cpi = np.tile(levels, (n_paths, 1))
        policy_rate = np.full((n_paths, months), 3.0, dtype=np.float64)
        if fc.policy_rate is not None:
            start = fc.policy_rate.start_pct if fc.policy_rate.start_pct is not None else 3.0
            end = fc.policy_rate.end_pct if fc.policy_rate.end_pct is not None else start
            policy_rate = np.tile(np.linspace(start, end, months), (n_paths, 1))
        equity_mkt = np.zeros((n_paths, months), dtype=np.float64)
        if fc.crisis_windows:
            window = fc.crisis_windows[0]
            mid_month = round((window.start_quarter + window.length_quarters / 2.0) * 3)
            mid_month = min(max(mid_month, 0), months - 1)
            equity_mkt[:, mid_month] = -(
                window.severity * CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT / 100.0
            )
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id="v",
            seed=seed,
            n_paths=n_paths,
            months=months,
        )
        paths = np.stack([cpi, policy_rate, equity_mkt], axis=-1)
        return Ensemble(paths=paths, factor_names=["cpi", "policy_rate", "equity_mkt"], meta=meta)


class _IgnoringGenerator:
    """Mirrors WP2.2b's NC5: ignores ``world.factor_conditions`` entirely, always
    sampling the same unconditioned, mildly-inflationary, flat-rate, noisy-equity
    paths whatever the WorldSpec asks for."""

    generator_id = "conditional-test-ignorer"

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = _months(world)
        rng = np.random.Generator(np.random.PCG64(seed))
        levels = 100.0 * (1.0 + 0.02 / 12.0) ** np.arange(months, dtype=np.float64)
        cpi = np.tile(levels, (n_paths, 1))
        policy_rate = np.full((n_paths, months), 3.0, dtype=np.float64)
        equity_mkt = rng.normal(0.0, 0.02, size=(n_paths, months))
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id="v",
            seed=seed,
            n_paths=n_paths,
            months=months,
        )
        paths = np.stack([cpi, policy_rate, equity_mkt], axis=-1)
        return Ensemble(paths=paths, factor_names=["cpi", "policy_rate", "equity_mkt"], meta=meta)


class _MissingCpiGenerator:
    """Emits every factor EXCEPT cpi -- "the generator produces less"."""

    generator_id = "conditional-test-missing-cpi"

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = _months(world)
        policy_rate = np.full((n_paths, months), 3.0, dtype=np.float64)
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id="v",
            seed=seed,
            n_paths=n_paths,
            months=months,
        )
        return Ensemble(paths=policy_rate[:, :, None], factor_names=["policy_rate"], meta=meta)


class _RaisesOnSevereGenerator:
    """Honours the MILD inflation world exactly but CRASHES sampling the SEVERE one --
    proves a single world's failure poisons the WHOLE pooled metric, not a partial
    (smaller, more favourable) result from the surviving world alone."""

    generator_id = "conditional-test-raises-on-severe"

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        fc = world.factor_conditions
        if (
            fc.inflation is not None
            and fc.inflation.average_pct is not None
            and fc.inflation.average_pct > 10.0
        ):
            raise RuntimeError("deliberate crash on the severe inflation world")
        return _PerfectGenerator().sample(world, n_paths, seed)


class _TailBadInflationGenerator:
    """Honours inflation exactly on ~88% of paths and is wildly wrong on ~12% -- the
    "usually right, occasionally wildly wrong" case the p90 metric must catch."""

    generator_id = "conditional-test-tailbad"
    WILD_FRACTION = 0.12
    WILD_OFFSET_PCT = 50.0

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = _months(world)
        fc = world.factor_conditions
        target = (
            fc.inflation.average_pct
            if (fc.inflation and fc.inflation.average_pct is not None)
            else 0.0
        )
        n_wild = max(1, round(self.WILD_FRACTION * n_paths))

        def _levels(avg_pct: float) -> np.ndarray:
            growth = (1.0 + avg_pct / 100.0) ** (1.0 / 12.0)
            return 100.0 * growth ** np.arange(months, dtype=np.float64)

        cpi = np.tile(_levels(target), (n_paths, 1))
        cpi[:n_wild] = _levels(target + self.WILD_OFFSET_PCT)
        policy_rate = np.full((n_paths, months), 3.0, dtype=np.float64)
        equity_mkt = np.zeros((n_paths, months), dtype=np.float64)
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id="v",
            seed=seed,
            n_paths=n_paths,
            months=months,
        )
        paths = np.stack([cpi, policy_rate, equity_mkt], axis=-1)
        return Ensemble(paths=paths, factor_names=["cpi", "policy_rate", "equity_mkt"], meta=meta)


class _DistanceFidelityGenerator:
    """Off-support test double: realized inflation/rate = baseline +
    SHRINK*(target-baseline) -- a KNOWN, deliberately imperfect function of how far the
    requested target sits from a fixed baseline, so adherence error is a known,
    monotonically increasing function of the sweep distance."""

    generator_id = "conditional-test-distance-fidelity"
    SHRINK = 0.4
    BASELINE_INFLATION_PCT = 2.5
    BASELINE_RATE_END_PCT = 3.0

    def fit(self, data: Any) -> None:
        pass

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = _months(world)
        fc = world.factor_conditions
        target_inflation = self.BASELINE_INFLATION_PCT
        if fc.inflation is not None and fc.inflation.average_pct is not None:
            target_inflation = self.BASELINE_INFLATION_PCT + self.SHRINK * (
                fc.inflation.average_pct - self.BASELINE_INFLATION_PCT
            )
        growth = (1.0 + target_inflation / 100.0) ** (1.0 / 12.0)
        cpi = np.tile(100.0 * growth ** np.arange(months, dtype=np.float64), (n_paths, 1))

        end = self.BASELINE_RATE_END_PCT
        if fc.policy_rate is not None and fc.policy_rate.end_pct is not None:
            end = self.BASELINE_RATE_END_PCT + self.SHRINK * (
                fc.policy_rate.end_pct - self.BASELINE_RATE_END_PCT
            )
        policy_rate = np.tile(np.linspace(self.BASELINE_RATE_END_PCT, end, months), (n_paths, 1))
        equity_mkt = np.zeros((n_paths, months), dtype=np.float64)
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id="v",
            seed=seed,
            n_paths=n_paths,
            months=months,
        )
        paths = np.stack([cpi, policy_rate, equity_mkt], axis=-1)
        return Ensemble(paths=paths, factor_names=["cpi", "policy_rate", "equity_mkt"], meta=meta)


# --------------------------------------------------------------------------- #
# 1. checked-in authored worlds
# --------------------------------------------------------------------------- #


def test_every_fixture_world_file_validates_against_the_schema() -> None:
    files = sorted(FIXTURES_DIR.glob("*.json"))
    assert files, "expected checked-in fixtures/worlds/conditional/*.json worlds"
    for path in files:
        load_worldspec(path)  # must not raise


def test_every_condition_type_has_at_least_one_authored_world() -> None:
    worlds = load_conditional_test_worlds()
    covered = {ctype for ctype, _ in worlds}
    assert covered == set(CONDITION_TYPES)


def test_load_conditional_test_worlds_is_cached_and_deterministic() -> None:
    a = load_conditional_test_worlds()
    b = load_conditional_test_worlds()
    assert a == b or [d for _, d in a] == [d for _, d in b]


# --------------------------------------------------------------------------- #
# 2. condition adherence -- THE deliverable: perfect vs ignoring, both directions,
# for every condition type.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("condition_type", CONDITION_TYPES)
def test_perfect_generator_scores_near_zero_adherence_error(condition_type: str) -> None:
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)
    value = specs[f"condition_adherence_error_{condition_type}"].fn(ensemble)
    assert value == pytest.approx(0.0, abs=1e-6), (condition_type, value)


# The minimum margin by which the condition-IGNORING generator must score worse than the
# perfect one, PER CONDITION TYPE, in that type's own units. A single flat margin (this
# test used to assert `+1.0` for all four) is satisfied vacuously by a type whose fixtures
# happen to sit close to the ignoring generator's own unconditional output -- exactly the
# case `rate` was in before `rate_endpoints_mild`'s endpoints were widened. Each entry
# below is roughly 60-70% of the value the checked-in fixtures actually produce, so a real
# regression in discrimination trips it while path-to-path noise does not; NC5's future
# failure (WP2.2b) must not be marginal.
_MIN_DISCRIMINATION_MARGIN: dict[str, float] = {
    "inflation": 3.0,  # actual ~5.5 pp
    "rate": 2.0,  # actual ~2.75 pp
    "crisis_timing": 8.0,  # actual ~15.8 quarters
    "crisis_severity": 4.0,  # actual ~7.7 pp
}


def test_every_condition_type_has_a_stated_discrimination_margin() -> None:
    assert set(_MIN_DISCRIMINATION_MARGIN) == set(CONDITION_TYPES)


@pytest.mark.parametrize("condition_type", CONDITION_TYPES)
def test_ignoring_generator_scores_clearly_worse_than_perfect(condition_type: str) -> None:
    """THE DELIVERABLE (brief: "Assert both"). A generator that structurally ignores
    conditioning (mirrors WP2.2b's NC5) must score CLEARLY worse than one that honours
    conditions exactly -- this suite's entire value is discriminating between them."""
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    gen_registry.register(_IgnoringGenerator.generator_id, _IgnoringGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    name = f"condition_adherence_error_{condition_type}"

    perfect_value = specs[name].fn(_dummy_ensemble(_PerfectGenerator.generator_id))
    ignoring_value = specs[name].fn(_dummy_ensemble(_IgnoringGenerator.generator_id))

    margin = _MIN_DISCRIMINATION_MARGIN[condition_type]
    assert perfect_value == pytest.approx(0.0, abs=1e-6), (condition_type, perfect_value)
    assert math.isfinite(ignoring_value), (condition_type, ignoring_value)
    assert ignoring_value > perfect_value + margin, (
        condition_type,
        perfect_value,
        ignoring_value,
        margin,
    )


# --------------------------------------------------------------------------- #
# 3. p90 catches a tail-bad generator the mean hides
# --------------------------------------------------------------------------- #


def test_p90_catches_a_generator_right_on_average_wrong_in_the_tail() -> None:
    gen_registry.register(_TailBadInflationGenerator.generator_id, _TailBadInflationGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    ensemble = _dummy_ensemble(_TailBadInflationGenerator.generator_id)

    mean_value = specs["condition_adherence_error_inflation"].fn(ensemble)
    p90_value = specs["condition_adherence_error_p90_inflation"].fn(ensemble)

    # ~88% of pooled paths are exact (error ~0), ~12% are wildly off (error ~50pp) --
    # the mean is dragged down by the large well-behaved majority while the 90th
    # percentile sits inside the wild minority (12% > 10%).
    assert mean_value < 15.0, mean_value
    assert p90_value > 35.0, p90_value
    assert p90_value > mean_value + 20.0, (mean_value, p90_value)


# --------------------------------------------------------------------------- #
# 4. off-support degradation
# --------------------------------------------------------------------------- #


def test_the_swept_support_distributions_have_real_dispersion() -> None:
    """Guards the test fixture itself, because a degenerate one silences an entire arm.

    If either swept quantity's support distribution is (near-)constant, ``mean(X) +
    z*std(X)`` does not move with ``z``, that arm contributes the same error at every
    level, and every off-support test below would pass with the arm deleted. Asserted
    here, once, rather than being an unstated property of ``_historical_series``.
    """
    series = _historical_series()
    yoy = conditional_mod._yoy_1d(series["cpi"].to_numpy(dtype=np.float64))
    yoy = yoy[np.isfinite(yoy)]
    assert float(np.std(yoy, ddof=1)) > 0.5, "cpi YoY must vary by more than 0.5pp"
    rate = series["policy_rate"].to_numpy(dtype=np.float64)
    assert float(np.std(rate, ddof=1)) > 0.5, "policy_rate must vary by more than 0.5pp"


def _per_arm_mean_errors(reference: ReferenceStats, generator_id: str) -> dict[str, list[float]]:
    """Mean adherence error at each swept level, reported SEPARATELY per swept arm.

    Part B's reported metrics pool the two arms, and a pooled assertion is exactly what
    let a dead arm hide: `_DistanceFidelityGenerator`'s rate arm alone produced the whole
    monotone trend while the inflation arm sat at ~1e-13 across every level. Reading the
    level's own ``(world_items, error_fns)`` is the only way to assert per arm.
    """
    per_arm: dict[str, list[float]] = {}
    for level in conditional_mod._build_off_support_levels(reference):
        assert len(level.world_items) == len(OFF_SUPPORT_TYPES), level
        for (k, doc), error_fn in zip(level.world_items, level.error_fns, strict=True):
            arm = doc["extensions"]["x_condition_type"]
            regen = conditional_mod._regenerate(doc, generator_id, 64, 1_000 + k)
            assert regen is not None, (arm, level.level)
            per_arm.setdefault(arm, []).append(float(np.mean(error_fn(*regen))))
    return per_arm


def test_off_support_adherence_degrades_strictly_in_every_swept_arm() -> None:
    """CRITICAL: per arm, not pooled. A pooled-only assertion cannot tell a suite in
    which both arms degrade from one in which a single arm carries the entire trend."""
    gen_registry.register(_DistanceFidelityGenerator.generator_id, _DistanceFidelityGenerator)
    manifest = _manifest()
    per_arm = _per_arm_mean_errors(
        _historical_reference(manifest), _DistanceFidelityGenerator.generator_id
    )

    assert set(per_arm) == set(OFF_SUPPORT_TYPES), per_arm
    for arm, values in sorted(per_arm.items()):
        assert len(values) == len(OFF_SUPPORT_LEVELS), (arm, values)
        assert all(math.isfinite(v) for v in values), (arm, values)
        # STRICTLY increasing, with a margin far above float noise: SHRINK<1 means the
        # generator's own tracking error grows with |target - baseline|, and the swept
        # target's distance from the baseline grows with z (OFF_SUPPORT_LEVELS is sorted
        # by z already). An arm that is inert shows up here as a flat (or ~1e-13) list.
        for earlier, later in itertools.pairwise(values):
            assert later > earlier + 0.1, (arm, values)


def test_off_support_adherence_degrades_monotonically_with_distance() -> None:
    gen_registry.register(_DistanceFidelityGenerator.generator_id, _DistanceFidelityGenerator)
    manifest = _manifest()
    specs = {s.name: s for s in build_conditional_suite(manifest, _historical_reference(manifest))}
    ensemble = _dummy_ensemble(_DistanceFidelityGenerator.generator_id)

    values = [
        specs[f"off_support_adherence_at_{level}"].fn(ensemble) for level, _ in OFF_SUPPORT_LEVELS
    ]
    assert all(math.isfinite(v) for v in values), values
    # STRICTLY increasing (the comment here used to claim "strictly" while the assertion
    # was `later >= earlier - 1e-9`, which admits a decrease): the pooled mean of two
    # per-arm errors that each strictly increase must itself strictly increase.
    for earlier, later in itertools.pairwise(values):
        assert later > earlier, values


def test_off_support_pass_rate_is_high_at_typical_and_lower_at_beyond() -> None:
    gen_registry.register(_DistanceFidelityGenerator.generator_id, _DistanceFidelityGenerator)
    manifest = _manifest()
    specs = {s.name: s for s in build_conditional_suite(manifest, _historical_reference(manifest))}
    ensemble = _dummy_ensemble(_DistanceFidelityGenerator.generator_id)

    typical = specs["off_support_pass_rate_at_typical"].fn(ensemble)
    beyond = specs["off_support_pass_rate_at_beyond"].fn(ensemble)
    assert math.isfinite(typical) and math.isfinite(beyond)
    assert typical > beyond, (typical, beyond)
    assert typical >= 0.9, typical  # near the historical mean, SHRINK*0 error ~= 0


def test_off_support_metrics_nan_without_a_historical_series() -> None:
    """No historical_series -> no support mean/std -> Part B cannot construct a swept
    target at all -- NaN, not a silently-omitted (and so smaller-looking) metric."""
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    manifest = _manifest()
    specs = {s.name: s for s in build_conditional_suite(manifest, _empty_reference(manifest))}
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)
    for level, _ in OFF_SUPPORT_LEVELS:
        assert math.isnan(specs[f"off_support_adherence_at_{level}"].fn(ensemble))
        assert math.isnan(specs[f"off_support_pass_rate_at_{level}"].fn(ensemble))


@pytest.mark.parametrize("present", ["cpi", "policy_rate"])
def test_off_support_metrics_nan_when_only_one_swept_type_has_history(present: str) -> None:
    """CRITICAL: PARTIAL support must poison the level, not shrink it silently.

    ``off_support_adherence_at_{level}``'s sealed definition
    (``pre-registration.yaml``'s ``off_support_estimator``) is "across BOTH swept types".
    A vintage with ``policy_rate`` history but no ``cpi`` history therefore must NOT
    report the rate arm alone under that name -- a different, possibly smaller number
    published under a sealed name that says it means something else. The both-absent
    case (tested above) holds fixed the very axis this defect lives on.
    """
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    manifest = _manifest()
    series = {k: v for k, v in _historical_series().items() if k == present}
    assert len(series) == 1
    specs = {
        s.name: s
        for s in build_conditional_suite(manifest, _reference_with_series(manifest, series))
    }
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)
    for level, _ in OFF_SUPPORT_LEVELS:
        assert math.isnan(specs[f"off_support_adherence_at_{level}"].fn(ensemble)), (present, level)
        assert math.isnan(specs[f"off_support_pass_rate_at_{level}"].fn(ensemble)), (present, level)


def test_off_support_sweep_bounds_are_read_from_the_worldspec_schema() -> None:
    """The clip bounds must BE the schema's, not a hand-copied restatement of them.

    Two independent definitions of one quantity is the defect class; the concrete failure
    mode is that tightening the schema makes every swept target build a document
    ``load_worldspec`` rejects. Asserting the derived values against the schema node read
    independently here proves the derivation reads the right node, and the literals name
    today's values so a schema change is visible in the diff.
    """
    props = worldspec_schema()["properties"]["factor_conditions"]["properties"]
    bounds = conditional_mod._off_support_bounds()
    assert set(bounds) == set(OFF_SUPPORT_TYPES)
    assert bounds["inflation"] == (
        float(props["inflation"]["properties"]["average_pct"]["minimum"]),
        float(props["inflation"]["properties"]["average_pct"]["maximum"]),
    )
    assert bounds["rate"] == (
        float(props["policy_rate"]["properties"]["end_pct"]["minimum"]),
        float(props["policy_rate"]["properties"]["end_pct"]["maximum"]),
    )
    assert bounds == {"inflation": (-5.0, 20.0), "rate": (0.0, 20.0)}


def test_every_programmatically_swept_world_validates_against_the_schema() -> None:
    """The existing fixture-validation test globs FIXTURES_DIR only, so no test covered
    the worlds Part B BUILDS -- the ones whose targets come from a z-score and a clip."""
    manifest = _manifest()
    checked = 0
    for level in conditional_mod._build_off_support_levels(_historical_reference(manifest)):
        for _k, doc in level.world_items:
            load_worldspec(doc)  # must not raise
            checked += 1
    assert checked == len(OFF_SUPPORT_LEVELS) * len(OFF_SUPPORT_TYPES), checked


# --------------------------------------------------------------------------- #
# 5. anti-gaming: no metric may improve when the generator produces less
# --------------------------------------------------------------------------- #


def test_unresolvable_generator_id_nans_every_metric_rather_than_crashing() -> None:
    manifest = _manifest()
    specs = build_conditional_suite(manifest, _empty_reference(manifest))
    ensemble = _dummy_ensemble("no-such-generator-anywhere-v99")
    for spec in specs:
        value = spec.fn(ensemble)  # must not raise
        assert math.isnan(value), (spec.name, value)


def test_omitting_the_conditioned_factor_nans_rather_than_a_small_error() -> None:
    """THE ANTI-GAMING DELIVERABLE for this suite: a generator that emits NONE of the
    conditioned factor (cpi) has produced LESS than one that emits it and adheres
    poorly -- and must NaN, never read as a smaller (better) error than the
    ignoring generator's real, finite, large error."""
    gen_registry.register(_MissingCpiGenerator.generator_id, _MissingCpiGenerator)
    gen_registry.register(_IgnoringGenerator.generator_id, _IgnoringGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}

    missing_value = specs["condition_adherence_error_inflation"].fn(
        _dummy_ensemble(_MissingCpiGenerator.generator_id)
    )
    ignoring_value = specs["condition_adherence_error_inflation"].fn(
        _dummy_ensemble(_IgnoringGenerator.generator_id)
    )
    assert math.isnan(missing_value)
    assert math.isfinite(ignoring_value)


def test_a_generator_crashing_on_one_world_poisons_the_whole_pooled_metric() -> None:
    """A generator that samples the mild inflation world perfectly but RAISES on the
    severe one must NaN the WHOLE condition_adherence_error_inflation metric -- never
    silently report the mild world's own (0.0, best-possible) error as if the severe
    world had never been asked."""
    gen_registry.register(_RaisesOnSevereGenerator.generator_id, _RaisesOnSevereGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    ensemble = _dummy_ensemble(_RaisesOnSevereGenerator.generator_id)
    value = specs["condition_adherence_error_inflation"].fn(ensemble)  # must not raise
    assert math.isnan(value), value


def test_production_pool_size_is_always_above_conditional_min_obs() -> None:
    """Structural: CONDITIONAL_RESAMPLE_N_PATHS * (>=2 worlds per type) is always well
    above CONDITIONAL_MIN_OBS, so the floor never fires on a checked-in configuration.

    (Renamed: this asserts the OPPOSITE of the insufficient-sample branch -- the branch
    itself is exercised by the test below, which previously had this test's name.)
    """
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    pool = conditional_mod._make_condition_pool("inflation")
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)
    errors = pool(ensemble)
    assert errors.size >= CONDITIONAL_MIN_OBS, errors.size


@pytest.mark.parametrize(
    "metric_factory",
    [conditional_mod._mean_metric, conditional_mod._p90_metric],
    ids=["mean", "p90"],
)
def test_below_conditional_min_obs_nans_rather_than_reporting_a_lucky_small_sample(
    metric_factory: Any,
) -> None:
    """THE INSUFFICIENT branch, exercised directly.

    A pool one observation short of the floor must NaN -- never report the (perfectly
    finite, possibly flattering) statistic of a small sample. One observation over the
    floor must report it, so the test pins the boundary rather than just the reject side.
    """
    ensemble = _dummy_ensemble("irrelevant-here")

    too_few = metric_factory(lambda _e: np.zeros(CONDITIONAL_MIN_OBS - 1, dtype=np.float64))
    assert math.isnan(too_few(ensemble))

    just_enough = metric_factory(lambda _e: np.zeros(CONDITIONAL_MIN_OBS, dtype=np.float64))
    assert just_enough(ensemble) == pytest.approx(0.0)


def test_off_support_metrics_also_nan_below_conditional_min_obs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Part B carries the identical floor and must apply it identically."""
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    manifest = _manifest()
    specs = {s.name: s for s in build_conditional_suite(manifest, _historical_reference(manifest))}
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)

    monkeypatch.setattr(
        conditional_mod,
        "_off_support_pooled_errors",
        lambda _level, _ensemble: np.zeros(CONDITIONAL_MIN_OBS - 1, dtype=np.float64),
    )
    for level, _ in OFF_SUPPORT_LEVELS:
        assert math.isnan(specs[f"off_support_adherence_at_{level}"].fn(ensemble)), level
        assert math.isnan(specs[f"off_support_pass_rate_at_{level}"].fn(ensemble)), level


def test_a_generator_factory_that_raises_nans_rather_than_aborting_the_battery() -> None:
    """`ah.gen.registry.resolve` invokes the registered FACTORY. WP2.4's bootstrap will
    load and fit inside its factory, so a factory that raises while constructing is a
    real path -- and it is not an `UnknownGeneratorError`, so before this it escaped
    `spec.fn` and took every other suite's results with it."""

    def _exploding_factory() -> Any:
        raise RuntimeError("deliberate failure while CONSTRUCTING the generator")

    gen_registry.register("conditional-test-exploding-factory", _exploding_factory)
    manifest = _manifest()
    specs = build_conditional_suite(manifest, _historical_reference(manifest))
    ensemble = _dummy_ensemble("conditional-test-exploding-factory")
    for spec in specs:
        value = spec.fn(ensemble)  # must not raise
        assert math.isnan(value), (spec.name, value)


def test_a_swept_world_failing_schema_validation_nans_rather_than_aborting_the_battery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`load_worldspec(doc)` used to sit OUTSIDE the guarded region, so a swept world
    that failed schema/pydantic validation crashed the whole battery rather than
    NaN-ing one metric. Simulated by a sweep builder that emits an invalid document."""
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)

    real_sweep_world = conditional_mod._sweep_world

    def _invalid_sweep_world(condition_type: str, level: str, target: float) -> dict[str, Any]:
        doc = real_sweep_world(condition_type, level, target)
        doc["horizon"] = {"start": "not-a-quarter", "quarters": -3}
        return doc

    monkeypatch.setattr(conditional_mod, "_sweep_world", _invalid_sweep_world)
    manifest = _manifest()
    specs = {s.name: s for s in build_conditional_suite(manifest, _historical_reference(manifest))}
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)
    for level, _ in OFF_SUPPORT_LEVELS:
        assert math.isnan(specs[f"off_support_adherence_at_{level}"].fn(ensemble)), level


def test_a_fixture_world_whose_tag_disagrees_with_its_conditions_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A world tagged `inflation` whose factor_conditions has no inflation block used to
    raise a raw KeyError at metric-evaluation time -> battery abort, not NaN. The tag and
    the fields are two statements of one fact and must be reconciled at LOAD time."""
    good = json.loads((FIXTURES_DIR / "inflation_mild.worldspec.json").read_text(encoding="utf-8"))
    good["factor_conditions"] = {"policy_rate": {"start_pct": 2.0, "end_pct": 3.0}}
    (tmp_path / "mistagged.json").write_text(json.dumps(good), encoding="utf-8")

    monkeypatch.setattr(conditional_mod, "FIXTURES_DIR", tmp_path)
    conditional_mod.load_conditional_test_worlds.cache_clear()
    try:
        with pytest.raises(ConditionalFixtureError, match="x_condition_type"):
            conditional_mod.load_conditional_test_worlds()
    finally:
        conditional_mod.load_conditional_test_worlds.cache_clear()


# --------------------------------------------------------------------------- #
# 5b. determinism: same seed -> bit-identical, different seed -> different
# --------------------------------------------------------------------------- #


def test_same_seed_is_bit_identical_and_a_different_seed_gives_a_different_value() -> None:
    """The regeneration seed is `ensemble.meta.seed + 7919*k`, so `meta.seed` is the one
    knob threading randomness into this suite. `_PerfectGenerator` ignores `seed`
    entirely, so it can prove neither half; `_IgnoringGenerator` consumes it (its
    equity_mkt is drawn from PCG64(seed)), which is what makes the second assertion
    meaningful."""
    gen_registry.register(_IgnoringGenerator.generator_id, _IgnoringGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    fn = specs["condition_adherence_error_crisis_timing"].fn

    a = fn(_dummy_ensemble(_IgnoringGenerator.generator_id, seed=11))
    b = fn(_dummy_ensemble(_IgnoringGenerator.generator_id, seed=11))
    c = fn(_dummy_ensemble(_IgnoringGenerator.generator_id, seed=12))

    assert a == b, (a, b)  # bit-identical, not approx
    assert math.isfinite(a) and math.isfinite(c)
    assert a != c, (a, c)


# --------------------------------------------------------------------------- #
# 6. Monte-Carlo error: an honest, structural consequence stated in the module
# docstring, not left to be discovered.
# --------------------------------------------------------------------------- #


def _full_ensemble(generator_id: str, seed: int = 0) -> Ensemble:
    meta = EnsembleMeta(generator_id=generator_id, vintage_id="v", seed=seed, n_paths=10, months=6)
    return Ensemble(paths=np.zeros((10, 6, 1)), factor_names=["x"], meta=meta)


def test_the_default_path_subsampling_mc_error_is_a_misleading_zero_here() -> None:
    """WHY this suite overrides mc_error, pinned as a fact rather than left as prose.

    `ah.eval.battery.mc_error` subsamples the PASSED ensemble's paths. No metric here
    reads them, so it returns exactly 0.0 -- for a metric whose value carries real
    Monte-Carlo uncertainty (`conditional_mc_error` measures it as clearly non-zero
    below). 0.0 is the number a WP2.3 threshold author reads to size a band, so
    reporting it here would be worse than reporting nothing."""
    from ah.eval.battery import mc_error

    gen_registry.register(_IgnoringGenerator.generator_id, _IgnoringGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    fn = specs["condition_adherence_error_crisis_timing"].fn
    ensemble = _full_ensemble(_IgnoringGenerator.generator_id)

    assert mc_error(fn, ensemble, seed=1, n_subsamples=5) == pytest.approx(0.0, abs=1e-12)
    assert conditional_mc_error(fn, ensemble, seed=1, n_subsamples=5) > 0.1


def test_conditional_mc_error_measures_spread_across_regeneration_seeds() -> None:
    """The replacement estimator, against a hand-computed ground truth.

    `std(replicates, ddof=1)` over CONDITIONAL_MC_ERROR_REPLICATES regenerations at
    stated seeds -- NOT divided by sqrt(k), because each replicate is an independent
    re-draw of the whole statistic and the reported value is one such draw."""
    gen_registry.register(_IgnoringGenerator.generator_id, _IgnoringGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    fn = specs["condition_adherence_error_crisis_timing"].fn
    ensemble = _full_ensemble(_IgnoringGenerator.generator_id, seed=5)

    stride = conditional_mod._MC_REPLICATE_STRIDE
    expected_replicates = [
        fn(_dummy_ensemble(_IgnoringGenerator.generator_id, seed=5 + stride * (r + 1)))
        for r in range(CONDITIONAL_MC_ERROR_REPLICATES)
    ]
    expected = float(np.std(np.array(expected_replicates), ddof=1))

    assert conditional_mc_error(fn, ensemble, seed=1, n_subsamples=5) == pytest.approx(expected)
    assert expected > 0.0


def test_conditional_mc_error_is_zero_for_a_genuinely_seed_independent_generator() -> None:
    """0.0 is still the right answer when it is a MEASURED fact about the generator
    rather than an artifact of the estimator: `_PerfectGenerator` ignores `seed`."""
    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    fn = specs["condition_adherence_error_inflation"].fn
    error = conditional_mc_error(
        fn, _full_ensemble(_PerfectGenerator.generator_id), seed=1, n_subsamples=5
    )
    assert error == pytest.approx(0.0, abs=1e-9), error


def test_conditional_mc_error_is_nan_for_an_uncomputable_metric() -> None:
    manifest = _manifest()
    specs = build_conditional_suite(manifest, _historical_reference(manifest))
    ensemble = _full_ensemble("no-such-generator-anywhere-v99")
    for spec in specs:
        assert math.isnan(conditional_mc_error(spec.fn, ensemble, seed=1, n_subsamples=5)), (
            spec.name
        )


def test_every_conditional_spec_carries_the_regeneration_mc_error_estimator() -> None:
    manifest = _manifest()
    for spec in build_conditional_suite(manifest, _historical_reference(manifest)):
        assert spec.mc_error_fn is conditional_mc_error, spec.name


def test_regeneration_is_memoized_so_the_suite_does_not_resample_the_same_world() -> None:
    """The value and its CONDITIONAL_MC_ERROR_REPLICATES replicates are a pure function
    of (world document, generator_id, n_paths, seed), and the mean and p90 metrics of a
    condition type share every one of them. Without the memo a full evaluation made ~670
    `.sample()` calls, almost all recomputing bit-identical values."""
    calls: list[int] = []

    class _CountingGenerator(_PerfectGenerator):
        generator_id = "conditional-test-counting"

        def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
            calls.append(seed)
            return super().sample(world, n_paths, seed)

    gen_registry.register(_CountingGenerator.generator_id, _CountingGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    ensemble = _dummy_ensemble(_CountingGenerator.generator_id)

    mean_fn = specs["condition_adherence_error_inflation"].fn
    p90_fn = specs["condition_adherence_error_p90_inflation"].fn
    assert math.isfinite(mean_fn(ensemble))
    after_first = len(calls)
    assert after_first == 2, calls  # exactly the two checked-in inflation worlds

    assert math.isfinite(p90_fn(ensemble))
    assert len(calls) == after_first, "the p90 metric must reuse the mean metric's regenerations"

    assert math.isfinite(mean_fn(ensemble))
    assert len(calls) == after_first, "a repeat evaluation must reuse them too"


def test_a_differently_targeted_world_under_the_same_world_id_is_not_served_stale() -> None:
    """The memo is keyed on the world DOCUMENT, not its `world_id`. Part B's sweep worlds
    reuse one id per (type, level) while their target is a function of the reference, so
    an id-keyed memo would hand a second battery run (new vintage, new support mean/std)
    the first run's ensemble."""
    gen_registry.register(_DistanceFidelityGenerator.generator_id, _DistanceFidelityGenerator)
    a = conditional_mod._sweep_world("inflation", "typical", 3.0)
    b = conditional_mod._sweep_world("inflation", "typical", 12.0)
    assert a["world_id"] == b["world_id"]

    regen_a = conditional_mod._regenerate(a, _DistanceFidelityGenerator.generator_id, 8, 1)
    regen_b = conditional_mod._regenerate(b, _DistanceFidelityGenerator.generator_id, 8, 1)
    assert regen_a is not None and regen_b is not None
    assert regen_a[1].factor_conditions.inflation is not None
    assert regen_b[1].factor_conditions.inflation is not None
    assert regen_a[1].factor_conditions.inflation.average_pct == 3.0
    assert regen_b[1].factor_conditions.inflation.average_pct == 12.0
    assert not np.array_equal(regen_a[0].factor("cpi"), regen_b[0].factor("cpi"))


# --------------------------------------------------------------------------- #
# 7. registration bookkeeping (structural requirements 1, 2, 5)
# --------------------------------------------------------------------------- #


def test_every_conditional_metric_name_can_carry_a_sealed_threshold() -> None:
    manifest = _manifest()
    specs = build_conditional_suite(manifest, _empty_reference(manifest))
    expected = set()
    for ctype in CONDITION_TYPES:
        expected.add(f"condition_adherence_error_{ctype}")
        expected.add(f"condition_adherence_error_p90_{ctype}")
    for level, _ in OFF_SUPPORT_LEVELS:
        expected.add(f"off_support_adherence_at_{level}")
        expected.add(f"off_support_pass_rate_at_{level}")
    assert {s.name for s in specs} == expected
    for spec in specs:
        assert spec.tier == "monthly"
        assert spec.suite == "conditional"
        assert spec.name in PANEL_STATS


def test_conditional_is_registered_in_prereg_metric_suite_names() -> None:
    from ah.eval import prereg as prereg_mod

    assert "conditional" in prereg_mod._METRIC_SUITE_NAMES


def test_conditional_suite_registered_in_reference_dependent_suite_builders() -> None:
    from ah.eval import battery as battery_mod

    assert battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS["conditional"] == (
        "ah.eval.metrics.conditional",
        "build_conditional_suite",
    )


def test_conditional_py_is_pinned_in_the_judged_source_set() -> None:
    from ah.eval import prereg as prereg_mod

    resolved = {p.resolve() for p in prereg_mod._default_judged_sources()}
    assert (ROOT / "src" / "ah" / "eval" / "metrics" / "conditional.py").resolve() in resolved


def test_every_authored_conditional_world_is_pinned_in_the_judged_source_set() -> None:
    """The authored worlds are SEALED INPUT DATA, not disposable fixtures.

    `pre-registration.yaml`'s condition_adherence_*_estimator blocks define each statistic
    as "pooled across every checked-in fixtures/worlds/conditional/*.json world tagged X".
    Before this, editing `inflation_severe.worldspec.json`'s average_pct from 12.0 to 3.0
    changed every inflation metric's value with NO lock violation and no amendment, and
    the estimator was not reconstructible from the sealed set alone.
    """
    from ah.eval import prereg as prereg_mod

    resolved = {p.resolve() for p in prereg_mod._default_judged_sources()}
    on_disk = {p.resolve() for p in FIXTURES_DIR.glob("*.json")}
    assert on_disk, "expected checked-in authored worlds"
    missing = sorted(str(p) for p in on_disk - resolved)
    assert not missing, (
        f"authored conditional world(s) {missing} are outside the sealed judged-source "
        f"set -- add them via ah.eval.prereg._REQUIRED_JUDGED_FIXTURE_GLOBS"
    )


def test_the_seal_digest_changes_when_an_authored_conditional_world_changes(
    tmp_path: Path,
) -> None:
    """The mechanical proof that the seal actually covers those documents."""
    from ah.eval import prereg as prereg_mod

    sources = list(prereg_mod._default_judged_sources())
    before = prereg_mod.seal(
        ROOT / "pre-registration.yaml", judged_sources=sources, sealed_at="x", dry_run=True
    )

    world = FIXTURES_DIR / "inflation_severe.worldspec.json"
    original = world.read_text(encoding="utf-8")
    edited = json.loads(original)
    edited["factor_conditions"]["inflation"]["average_pct"] = 3.0
    try:
        world.write_text(json.dumps(edited, indent=2), encoding="utf-8")
        after = prereg_mod.seal(
            ROOT / "pre-registration.yaml", judged_sources=sources, sealed_at="x", dry_run=True
        )
    finally:
        world.write_text(original, encoding="utf-8", newline="")
    assert after != before, "editing an authored conditional world must break the seal"

    restored = prereg_mod.seal(
        ROOT / "pre-registration.yaml", judged_sources=sources, sealed_at="x", dry_run=True
    )
    assert restored == before, "the fixture must be restored byte-identically"


def test_a_fixture_world_missing_its_condition_type_tag_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An authored world checked in without (or with an unknown) extensions.
    x_condition_type is a silent hole in the suite -- must raise, not be skipped."""
    import ah.eval.metrics.conditional as conditional_mod

    good = json.loads((FIXTURES_DIR / "inflation_mild.worldspec.json").read_text(encoding="utf-8"))
    del good["extensions"]["x_condition_type"]
    (tmp_path / "untagged.json").write_text(json.dumps(good), encoding="utf-8")

    monkeypatch.setattr(conditional_mod, "FIXTURES_DIR", tmp_path)
    conditional_mod.load_conditional_test_worlds.cache_clear()
    try:
        with pytest.raises(ConditionalFixtureError):
            conditional_mod.load_conditional_test_worlds()
    finally:
        conditional_mod.load_conditional_test_worlds.cache_clear()


# --------------------------------------------------------------------------- #
# 8. narrative-blindness + no g2 import (repo-wide conventions every
# reference-dependent suite in eval/metrics/ carries)
# --------------------------------------------------------------------------- #

_CONDITIONAL_PATH = ROOT / "src" / "ah" / "eval" / "metrics" / "conditional.py"

_NARRATIVE_ACCESS = re.compile(
    r"""\.narrative\b|\[\s*['"]narrative['"]\s*\]|\.get\(\s*['"]narrative['"]"""
)


def test_conditional_module_never_accesses_a_narrative_field() -> None:
    """Conditions flow through ah.core.numericworld.project_numeric (which structurally
    omits narrative), never from WorldSpec.narrative directly -- mirrors
    tests/test_narrative_blindness.py's scan, applied to this module specifically."""
    source = _CONDITIONAL_PATH.read_text(encoding="utf-8")
    assert not _NARRATIVE_ACCESS.search(source), (
        "ah.eval.metrics.conditional accesses a 'narrative' field -- conditions must "
        "come from the WorldSpec's numeric projection only."
    )


def test_conditional_module_never_imports_g2_or_names_the_token() -> None:
    text = _CONDITIONAL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_CONDITIONAL_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ah.eval.g2" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "g2" not in module.split("."), module
            for alias in node.names:
                assert alias.name != "FinalEvaluationToken"


# --------------------------------------------------------------------------- #
# 9. every conditional threshold in the real pre-registration.yaml is 'report', never
# 'enforce' -- nothing in this suite may gate G2.
# --------------------------------------------------------------------------- #


def test_every_real_conditional_threshold_is_report_severity_never_enforce() -> None:
    from ah.eval import prereg as prereg_mod

    real = prereg_mod.load()
    conditional_names = {
        s.name for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))
    }
    checked = 0
    for name, threshold in real.panel_thresholds.items():
        if name in conditional_names:
            checked += 1
            assert threshold.severity == "report", (name, threshold.severity)
    assert checked == len(conditional_names), (checked, len(conditional_names))
