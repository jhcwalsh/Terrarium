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
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from ah.core.loader import load_worldspec
from ah.core.numericworld import NumericWorld
from ah.eval.metrics.conditional import (
    CONDITION_TYPES,
    CONDITIONAL_MIN_OBS,
    CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT,
    FIXTURES_DIR,
    OFF_SUPPORT_LEVELS,
    ConditionalFixtureError,
    build_conditional_suite,
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


def _historical_reference(manifest: FactorManifest) -> ReferenceStats:
    """A reference carrying real ``historical_series`` for cpi/policy_rate, so Part B's
    off-support sweep has a real support distribution to sweep against."""
    dates = pd.date_range("1990-01-01", periods=420, freq="MS")
    months = np.arange(420, dtype=np.float64)
    cpi = pd.Series(100.0 * 1.025 ** (months / 12.0), index=dates)
    rng = np.random.Generator(np.random.PCG64(7))
    policy_rate = pd.Series(3.0 + rng.normal(0.0, 1.0, size=420), index=dates)
    empty = _empty_reference(manifest)
    return ReferenceStats(
        blocks=empty.blocks,
        cross_blocks=empty.cross_blocks,
        active_blocks=empty.active_blocks,
        vintage_id=empty.vintage_id,
        n_resamples=empty.n_resamples,
        seed=empty.seed,
        missing_factors=empty.missing_factors,
        historical_series={"cpi": cpi, "policy_rate": policy_rate},
    )


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

    assert perfect_value == pytest.approx(0.0, abs=1e-6), (condition_type, perfect_value)
    assert math.isfinite(ignoring_value), (condition_type, ignoring_value)
    assert ignoring_value > perfect_value + 1.0, (condition_type, perfect_value, ignoring_value)


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


def test_off_support_adherence_degrades_monotonically_with_distance() -> None:
    gen_registry.register(_DistanceFidelityGenerator.generator_id, _DistanceFidelityGenerator)
    manifest = _manifest()
    specs = {s.name: s for s in build_conditional_suite(manifest, _historical_reference(manifest))}
    ensemble = _dummy_ensemble(_DistanceFidelityGenerator.generator_id)

    values = [
        specs[f"off_support_adherence_at_{level}"].fn(ensemble) for level, _ in OFF_SUPPORT_LEVELS
    ]
    assert all(math.isfinite(v) for v in values), values
    # Strictly increasing: SHRINK<1 means the generator's own tracking error grows
    # monotonically with |target - baseline|, and the swept target's distance from the
    # baseline grows monotonically with z (OFF_SUPPORT_LEVELS is sorted by z already).
    for earlier, later in itertools.pairwise(values):
        assert later >= earlier - 1e-9, values


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


def test_below_conditional_min_obs_nans_rather_than_reporting_a_lucky_small_sample() -> None:
    """Structural: CONDITIONAL_RESAMPLE_N_PATHS * (>=2 worlds per type) is always well
    above CONDITIONAL_MIN_OBS in production, but the floor itself is exercised directly
    here by calling the suite's own error-array machinery at a tiny path count."""
    from ah.eval.metrics.conditional import _make_condition_pool

    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    pool = _make_condition_pool("inflation")
    ensemble = _dummy_ensemble(_PerfectGenerator.generator_id)
    errors = pool(ensemble)
    assert errors.size >= CONDITIONAL_MIN_OBS, errors.size


# --------------------------------------------------------------------------- #
# 6. Monte-Carlo error: an honest, structural consequence stated in the module
# docstring, not left to be discovered.
# --------------------------------------------------------------------------- #


def test_mc_error_is_well_defined_and_finite_for_a_conditional_metric() -> None:
    """A conditional metric's fn() ignores the passed ensemble's OWN paths (it
    regenerates fresh ones from generator_id/seed) -- ah.eval.battery.mc_error's
    subsampling therefore recomputes the IDENTICAL value on every subsample (only
    generator_id/seed carry over, not paths), so mc_error is well-defined, finite, and
    (by construction) exactly 0.0 rather than NaN or a crash."""
    from ah.eval.battery import mc_error

    gen_registry.register(_PerfectGenerator.generator_id, _PerfectGenerator)
    specs = {s.name: s for s in build_conditional_suite(_manifest(), _empty_reference(_manifest()))}
    fn = specs["condition_adherence_error_inflation"].fn
    ensemble = EnsembleMeta(
        generator_id=_PerfectGenerator.generator_id, vintage_id="v", seed=0, n_paths=10, months=6
    )
    full_ensemble = Ensemble(paths=np.zeros((10, 6, 1)), factor_names=["x"], meta=ensemble)
    error = mc_error(fn, full_ensemble, seed=1, n_subsamples=5)
    assert error == pytest.approx(0.0, abs=1e-9), error


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
