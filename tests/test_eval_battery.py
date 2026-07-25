"""WP2.2 Task 1 acceptance: the validation battery orchestrator.

``ah.eval.battery`` is the spine Tasks 2-6 register their metric suites into
(``monthly``, ``horizon``, ``tails``, ``utility``, ``memorization``, ``economics``,
``conditional``, ``calibration``). This task builds the orchestrator itself, the
registration mechanism, the Monte-Carlo error helper, and proves the plan's WP2.2
acceptance criterion ("battery runs on the Step-0 toy engine's output end to end in
CI") with a throwaway test suite -- the real suites are Tasks 2-6's scope, not this
one's.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ah.core.engine import ASSETS, run_ensemble
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.eval import battery
from ah.eval import prereg as prereg_mod
from ah.eval.battery import (
    BatteryError,
    BatteryReport,
    MetricResult,
    MetricSpec,
    mc_error,
    register_suite,
    run_battery,
)
from ah.eval.reference import BlockReference, ReferenceStats, StatBand
from ah.factors import load_manifest
from ah.gen.base import Ensemble, EnsembleMeta

ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE: dict[str, Any] = json.loads(
    (ROOT / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
)


def _toy_ensemble(n_paths: int = 32, base_seed: int = 42) -> Ensemble:
    """The Step-0 toy engine's output, wrapped as an ``ah.gen.base.Ensemble``."""
    doc = json.loads(json.dumps(_EXAMPLE))
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    nw = project_numeric(WorldSpec.model_validate(doc))
    result = run_ensemble(nw, n_paths, base_seed=base_seed)
    paths = np.stack([result.returns[a] for a in ASSETS], axis=-1)
    meta = EnsembleMeta(
        generator_id="toy-v0",
        vintage_id="toy-vintage-test",
        seed=base_seed,
        n_paths=n_paths,
        months=result.months,
    )
    return Ensemble(paths=paths, factor_names=list(ASSETS), meta=meta)


def _empty_reference() -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=(),
        vintage_id="v-empty",
        n_resamples=1,
        seed=1,
        missing_factors=(),
    )


def _real_prereg() -> prereg_mod.PreRegistration:
    return prereg_mod.load()


# --------------------------------------------------------------------------- #
# 1. register_suite: registration only, validated
# --------------------------------------------------------------------------- #


def _clean_suite_name(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Ensure ``name`` is absent from SUITES before and after the test."""
    assert name not in battery.SUITES
    monkeypatch.setitem(battery.SUITES, name, ())
    del battery.SUITES[name]


def test_register_suite_adds_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_suite_adds_specs"
    _clean_suite_name(monkeypatch, name)
    spec = MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite=name)

    register_suite(name, [spec])

    assert battery.SUITES[name] == (spec,)


def test_register_suite_rejects_empty_name(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite="")
    with pytest.raises(BatteryError, match="non-empty"):
        register_suite("", [spec])


def test_register_suite_rejects_empty_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_suite_empty"
    _clean_suite_name(monkeypatch, name)
    with pytest.raises(BatteryError, match="no metrics"):
        register_suite(name, [])


def test_register_suite_rejects_suite_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_suite_mismatch"
    _clean_suite_name(monkeypatch, name)
    spec = MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite="other")
    with pytest.raises(BatteryError, match="suite"):
        register_suite(name, [spec])


def test_register_suite_rejects_unknown_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_suite_bad_tier"
    _clean_suite_name(monkeypatch, name)
    spec = MetricSpec(name="x.mean", tier="decadal", fn=lambda e: 0.0, suite=name)
    with pytest.raises(BatteryError, match="tier"):
        register_suite(name, [spec])


def test_register_suite_rejects_duplicate_metric_name(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_suite_dup"
    _clean_suite_name(monkeypatch, name)
    specs = [
        MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite=name),
        MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 1.0, suite=name),
    ]
    with pytest.raises(BatteryError, match="duplicate"):
        register_suite(name, specs)


def test_register_suite_rejects_reregistration(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_suite_rereg"
    _clean_suite_name(monkeypatch, name)
    spec = MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite=name)
    register_suite(name, [spec])
    with pytest.raises(BatteryError, match="already registered"):
        register_suite(name, [spec])


# --------------------------------------------------------------------------- #
# 2. mc_error: deterministic, recovers the right order of magnitude
# --------------------------------------------------------------------------- #


def _uniform_meta(n_paths: int) -> EnsembleMeta:
    return EnsembleMeta(generator_id="test-gen", vintage_id="v", seed=0, n_paths=n_paths, months=1)


def test_mc_error_recovers_standard_error_of_the_mean() -> None:
    rng = np.random.Generator(np.random.PCG64(0))
    n_paths, months, sigma = 4000, 3, 2.0
    values = rng.normal(0.0, sigma, size=(n_paths, months))
    ensemble = Ensemble(paths=values[:, :, None], factor_names=["g1"], meta=_uniform_meta(n_paths))

    def metric(e: Ensemble) -> float:
        return float(np.mean(e.factor("g1")))

    error = mc_error(metric, ensemble, seed=1, n_subsamples=40)

    expected_se = sigma / np.sqrt(n_paths * months)
    assert error == pytest.approx(expected_se, rel=0.35)


def test_mc_error_is_deterministic_for_fixed_seed() -> None:
    rng = np.random.Generator(np.random.PCG64(3))
    values = rng.normal(0.0, 1.0, size=(200, 2))
    ensemble = Ensemble(paths=values[:, :, None], factor_names=["g1"], meta=_uniform_meta(200))

    def metric(e: Ensemble) -> float:
        return float(np.mean(e.factor("g1")))

    e1 = mc_error(metric, ensemble, seed=7, n_subsamples=10)
    e2 = mc_error(metric, ensemble, seed=7, n_subsamples=10)
    assert e1 == e2


def test_mc_error_different_seed_gives_different_value() -> None:
    rng = np.random.Generator(np.random.PCG64(4))
    values = rng.normal(0.0, 1.0, size=(200, 2))
    ensemble = Ensemble(paths=values[:, :, None], factor_names=["g1"], meta=_uniform_meta(200))

    def metric(e: Ensemble) -> float:
        return float(np.mean(e.factor("g1")))

    e1 = mc_error(metric, ensemble, seed=7, n_subsamples=10)
    e2 = mc_error(metric, ensemble, seed=8, n_subsamples=10)
    assert e1 != e2


def test_mc_error_rejects_too_few_subsamples() -> None:
    ensemble = Ensemble(paths=np.zeros((10, 2, 1)), factor_names=["g1"], meta=_uniform_meta(10))
    with pytest.raises(BatteryError, match="n_subsamples"):
        mc_error(lambda e: 0.0, ensemble, seed=1, n_subsamples=1)


def test_mc_error_rejects_more_subsamples_than_paths() -> None:
    ensemble = Ensemble(paths=np.zeros((3, 2, 1)), factor_names=["g1"], meta=_uniform_meta(3))
    with pytest.raises(BatteryError, match="fewer"):
        mc_error(lambda e: 0.0, ensemble, seed=1, n_subsamples=10)


# --------------------------------------------------------------------------- #
# 3. band / threshold lookup drives severity + passed, over a fully synthetic fixture
# --------------------------------------------------------------------------- #


def _write_synthetic_prereg(tmp_path: Path, *, min_v: float, max_v: float, severity: str):
    factors_path = tmp_path / "factors.yaml"
    factors_path.write_text(
        "factor_blocks:\n  global: [g1]\nactive_blocks: [global]\n"
        "factor_sources:\n  g1: {kind: series, series_id: s.g1, units: ret}\n",
        encoding="utf-8",
    )
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(
        'schema_version: "1.0"\n'
        "sealed: false\n"
        "factor_manifest: factors.yaml\n"
        "active_blocks: [global]\n"
        "thresholds:\n"
        "  blocks:\n"
        "    global:\n"
        f"      g1.mean: {{min: {min_v}, max: {max_v}, severity: {severity}}}\n"
        "  cross_blocks: {}\n",
        encoding="utf-8",
    )
    return prereg_mod.load(prereg_path), load_manifest(factors_path)


def _band_reference(point: float) -> ReferenceStats:
    band = StatBand(
        point=point, lo=point - 1.0, hi=point + 1.0, n_resamples=5, level=0.9, tier="monthly"
    )
    return ReferenceStats(
        blocks={"global": BlockReference(block="global", stats={"g1.mean": band})},
        cross_blocks={},
        active_blocks=("global",),
        vintage_id="v",
        n_resamples=5,
        seed=1,
        missing_factors=(),
    )


def _constant_ensemble(value: float, n_paths: int = 8) -> Ensemble:
    paths = np.full((n_paths, 4, 1), value, dtype=np.float64)
    meta = EnsembleMeta(generator_id="const-gen", vintage_id="v", seed=1, n_paths=n_paths, months=4)
    return Ensemble(paths=paths, factor_names=["g1"], meta=meta)


def test_run_battery_marks_enforce_threshold_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = "_test_severity_pass"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="g1.mean",
                tier="monthly",
                fn=lambda e: float(np.mean(e.factor("g1"))),
                suite=name,
            )
        ],
    )
    prereg_obj, manifest = _write_synthetic_prereg(
        tmp_path, min_v=-1.0, max_v=1.0, severity="enforce"
    )
    reference = _band_reference(point=0.0)
    ensemble = _constant_ensemble(0.5)

    report = run_battery(
        ensemble, reference=reference, prereg=prereg_obj, manifest=manifest, seed=0
    )

    result = next(r for r in report.results if r.name == "g1.mean")
    assert result.severity == "enforce"
    assert result.passed is True
    assert result.value == pytest.approx(0.5)
    assert result.band is not None and result.band.point == 0.0


def test_run_battery_marks_enforce_threshold_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = "_test_severity_fail"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="g1.mean",
                tier="monthly",
                fn=lambda e: float(np.mean(e.factor("g1"))),
                suite=name,
            )
        ],
    )
    prereg_obj, manifest = _write_synthetic_prereg(
        tmp_path, min_v=-1.0, max_v=1.0, severity="enforce"
    )
    reference = _band_reference(point=0.0)
    ensemble = _constant_ensemble(5.0)  # well outside [-1, 1]

    report = run_battery(
        ensemble, reference=reference, prereg=prereg_obj, manifest=manifest, seed=0
    )

    result = next(r for r in report.results if r.name == "g1.mean")
    assert result.severity == "enforce"
    assert result.passed is False


def test_run_battery_unmatched_metric_is_report_and_unjudged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = "_test_severity_unmatched"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="g1.no_such_stat",
                tier="monthly",
                fn=lambda e: float(np.mean(e.factor("g1"))),
                suite=name,
            )
        ],
    )
    prereg_obj, manifest = _write_synthetic_prereg(
        tmp_path, min_v=-1.0, max_v=1.0, severity="enforce"
    )
    reference = _band_reference(point=0.0)
    ensemble = _constant_ensemble(5.0)

    report = run_battery(
        ensemble, reference=reference, prereg=prereg_obj, manifest=manifest, seed=0
    )

    result = next(r for r in report.results if r.name == "g1.no_such_stat")
    assert result.severity == "report"
    assert result.passed is None
    assert result.band is None


# --------------------------------------------------------------------------- #
# 4. run_battery on the Step-0 toy engine's output, end to end (plan's own
#    acceptance criterion for WP2.2), plus filtered/unfiltered and registration
# --------------------------------------------------------------------------- #


def test_run_battery_on_toy_engine_emits_both_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_toy_engine_suite"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="equity.dummy_mean",
                tier="monthly",
                fn=lambda e: float(np.mean(e.factor("equity"))),
                suite=name,
            )
        ],
    )
    ensemble = _toy_ensemble()

    report = run_battery(
        ensemble,
        reference=_empty_reference(),
        prereg=_real_prereg(),
        manifest=load_manifest(),
        seed=1,
    )

    assert isinstance(report, BatteryReport)
    assert report.system_id == "toy-v0"
    assert report.vintage_id == "toy-vintage-test"
    assert report.active_blocks == ("global", "us")
    assert report.prereg_digest.startswith("sha256:")

    result = next(r for r in report.results if r.name == "equity.dummy_mean")
    assert isinstance(result, MetricResult)
    assert result.mc_error is not None and result.mc_error >= 0.0

    as_json = report.to_json()
    payload = json.loads(as_json)
    assert payload["battery_version"] == report.battery_version
    assert "equity.dummy_mean" in as_json

    as_markdown = report.to_markdown()
    assert "equity.dummy_mean" in as_markdown
    assert "monthly" in as_markdown


def test_run_battery_reports_filtered_and_unfiltered_side_by_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "_test_filtered_suite"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="equity.dummy_mean",
                tier="monthly",
                fn=lambda e: float(np.mean(e.factor("equity"))),
                suite=name,
            )
        ],
    )
    unfiltered = _toy_ensemble(n_paths=32, base_seed=42)
    filtered = _toy_ensemble(n_paths=16, base_seed=99)

    report = run_battery(
        unfiltered,
        reference=_empty_reference(),
        prereg=_real_prereg(),
        manifest=load_manifest(),
        seed=1,
        filtered=filtered,
    )

    assert report.results_filtered is not None
    assert len(report.results) == len(report.results_filtered) == 1
    # different ensembles -> (almost certainly) different values
    assert report.results[0].value != report.results_filtered[0].value

    payload = json.loads(report.to_json())
    assert "filtered" in payload
    assert "unfiltered" in payload
    assert "Filtered" in report.to_markdown()
    assert "Unfiltered" in report.to_markdown()


def test_run_battery_without_filtered_omits_filtered_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "_test_no_filtered_suite"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="equity.dummy_mean",
                tier="monthly",
                fn=lambda e: float(np.mean(e.factor("equity"))),
                suite=name,
            )
        ],
    )
    report = run_battery(
        _toy_ensemble(),
        reference=_empty_reference(),
        prereg=_real_prereg(),
        manifest=load_manifest(),
        seed=1,
    )

    assert report.results_filtered is None
    assert "filtered" not in report.to_dict()
    assert "Filtered" not in report.to_markdown()


def test_registered_suite_appears_without_editing_run_battery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registration-only contract: adding a brand-new suite name and metric makes
    it appear in the next report with no change to run_battery's own source.
    """
    name = "_test_brand_new_suite_xyz"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="bonds.dummy_std",
                tier="1_5yr",
                fn=lambda e: float(np.std(e.factor("bonds"))),
                suite=name,
            )
        ],
    )

    report = run_battery(
        _toy_ensemble(),
        reference=_empty_reference(),
        prereg=_real_prereg(),
        manifest=load_manifest(),
        seed=1,
    )

    names = {r.name for r in report.results}
    assert "bonds.dummy_std" in names
    tier_result = next(r for r in report.results if r.name == "bonds.dummy_std")
    assert tier_result.tier == "1_5yr"
    assert tier_result.suite == name


# --------------------------------------------------------------------------- #
# 5. basic dataclass shape
# --------------------------------------------------------------------------- #


def test_metric_result_is_frozen() -> None:
    r = MetricResult(
        name="x.mean",
        suite="s",
        tier="monthly",
        value=1.0,
        mc_error=0.1,
        band=None,
        severity="report",
        passed=None,
    )
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        r.value = 2.0  # type: ignore[misc]


def test_metric_spec_is_frozen() -> None:
    spec = MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite="s")
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        spec.name = "y.mean"  # type: ignore[misc]
