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

import dataclasses
import json
from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from ah.core.engine import ASSETS, run_ensemble
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.eval import battery
from ah.eval import prereg as prereg_mod
from ah.eval import reference as reference_mod
from ah.eval.battery import (
    BatteryError,
    BatteryReport,
    MetricResult,
    MetricSpec,
    mc_error,
    register_suite,
    run_battery,
)
from ah.eval.reference import BlockReference, FactorCoverage, ReferenceStats, StatBand
from ah.factors import FactorManifest, FactorSource, load_manifest
from ah.gen.base import Ensemble, EnsembleMeta
from ah.splits import DataAccess

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
    """The real ``pre-registration.yaml``'s thresholds, **as a draft** (``sealed=False``).

    Every caller below runs ``run_battery`` over a SYNTHETIC two-factor manifest
    (``global: [g1]``, ``us: [u1]``) while wanting the real document's realistic
    threshold values attached to the results. Those two things are incompatible with
    verification: ``verify()`` checks that ``conventions`` classifies exactly the
    manifest's active factor set and that every threshold key names a factor of the
    block it sits under, and the real document is authored against the real manifest --
    so verifying it against ``g1``/``u1`` is not a check that could ever pass, and
    passing it would mean the check had stopped working.

    WP2.3 sealed the real file, and ``run_battery`` verifies any pre-registration
    claiming ``sealed: true`` on every invocation. Handing these tests a draft copy is
    therefore not a weakening -- it restores exactly the behaviour they had while the
    real file was unsealed (verification skipped, ``prereg_verified: false`` recorded on
    the report), with the reason now explicit instead of incidental. The genuine
    sealed-document path is covered against the REAL manifest by
    ``tests/test_prereg.py`` (``test_the_committed_lock_verifies_against_the_committed_tree``,
    ``test_load_and_verify_real_file_passes``) and, end to end through ``run_battery``,
    by ``tests/test_negative_controls.py``, which uses the real manifest throughout.
    """
    return dataclasses.replace(prereg_mod.load(), sealed=False)


# --------------------------------------------------------------------------- #
# 1. register_suite: registration only, validated
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _restore_suites() -> Iterator[None]:
    """Snapshot and restore ``battery.SUITES`` around every test in this module.

    ``SUITES`` is process-global module state and ``register_suite`` refuses to
    re-register a name, so a test that registers a throwaway suite and does not undo it
    poisons every later test -- and, worse, leaks a metric into any *other* module's
    ``run_battery`` call. The previous ``monkeypatch.setitem`` then ``del`` dance
    registered the key only so monkeypatch would learn to delete it again, which is
    both obscure and wrong for any test that registers more than one suite. A snapshot
    of the whole dict is exact and needs no cooperation from the test body.
    """
    snapshot = dict(battery.SUITES)
    try:
        yield
    finally:
        battery.SUITES.clear()
        battery.SUITES.update(snapshot)


def _clean_suite_name(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Assert ``name`` is not already registered; teardown is ``_restore_suites``'."""
    assert name not in battery.SUITES


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


def test_a_spec_may_override_the_mc_error_estimator(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP2.2 Task 6 fix pass 1 (Important 7). `MetricSpec.mc_error_fn` exists because
    `ah.eval.metrics.conditional`'s metrics ignore the passed ensemble's paths entirely,
    so path subsampling reports a confident 0.0 beside a value with real Monte-Carlo
    uncertainty -- and that 0.0 is exactly the number a WP2.3 threshold author reads to
    size a band. Overriding must reach the REPORT, not just the spec."""
    name = "_test_suite_mc_override"
    _clean_suite_name(monkeypatch, name)
    seen: list[tuple[int, int]] = []

    def _fixed_error(fn: object, ensemble: Ensemble, *, seed: int, n_subsamples: int) -> float:
        seen.append((seed, n_subsamples))
        return 0.125

    register_suite(
        name,
        [
            MetricSpec(
                name="overridden",
                tier="monthly",
                fn=lambda e: 1.0,
                suite=name,
                mc_error_fn=_fixed_error,
            ),
            MetricSpec(name="default", tier="monthly", fn=lambda e: 1.0, suite=name),
        ],
    )
    report = battery.run_battery(
        _toy_ensemble(),
        reference=_empty_reference(),
        prereg=_real_prereg(),
        manifest=load_manifest(),
        seed=3,
        filtered=None,
    )
    by_name = {r.name: r for r in report.results if r.suite == name}
    assert by_name["overridden"].mc_error == pytest.approx(0.125)
    # The default estimator is untouched for every other spec: a constant metric has
    # zero spread across subsamples, so 0.0 here is the DEFAULT path having run.
    assert by_name["default"].mc_error == pytest.approx(0.0)
    assert seen and all(s == 3 for s, _ in seen), seen


# --------------------------------------------------------------------------- #
# 2b. WP2.2 Task 3: "bands or it didn't happen" made structural for the 10yr tier
# --------------------------------------------------------------------------- #


def test_require_mc_error_reported_rejects_a_10yr_metric_with_no_error_at_all() -> None:
    """The battery must reject a 10yr-tier metric registered without a Monte-Carlo
    error estimate, rather than relying on anyone remembering (STEP2-GENERATOR-PLAN
    Sec.6: "small-n decade metrics -- bands or it didn't happen"). ``_run_suites``
    already computes ``mc_error`` unconditionally for every spec today, so this is a
    structural, tested guarantee rather than an accident of the current code shape."""
    from ah.eval.battery import _require_mc_error_reported

    with pytest.raises(BatteryError, match="10yr"):
        _require_mc_error_reported("10yr", "some.metric", None)


def test_require_mc_error_reported_allows_a_honestly_nan_10yr_error() -> None:
    """NaN is not rejected: a 10yr metric whose value (and therefore Monte-Carlo
    error) is honestly uncomputable today -- e.g. ah.eval.metrics.horizon's
    structural-gap metrics -- has reported its error faithfully. Rejecting NaN here
    would make the battery raise on every real run touching those metrics, which is
    the opposite of "honestly reported"."""
    from ah.eval.battery import _require_mc_error_reported

    _require_mc_error_reported("10yr", "some.metric", float("nan"))  # must not raise


def test_require_mc_error_reported_does_not_apply_outside_10yr() -> None:
    from ah.eval.battery import _require_mc_error_reported

    _require_mc_error_reported("1_5yr", "some.metric", None)  # must not raise
    _require_mc_error_reported("monthly", "some.metric", None)  # must not raise


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


def _a_band(point: float = 0.0) -> StatBand:
    return StatBand(
        point=point, lo=point - 1.0, hi=point + 1.0, n_resamples=5, level=0.9, tier="monthly"
    )


def _band_reference(point: float) -> ReferenceStats:
    band = _a_band(point)
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


def test_battery_report_json_and_markdown_carry_resample_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Important 2 (WP2.2 Task 2 fix pass 2). `StatBand.resample_length` says whether a
    band was drawn length-matched to the judged ensemble's own path length or at the
    full historical sample -- load-bearing per `pre-registration.yaml`'s
    `conventions.estimator_length_matching` (a length-matched band's `point` is NOT
    expected to lie inside `[lo, hi]`, which reads as an unexplained failure without
    this field). `_result_dict` and `to_markdown` used to drop it on the floor, so the
    battery JSON -- the G2 evidence artifact -- could not distinguish a length-matched
    band from an unmatched one.
    """
    name = "_test_resample_length_visible"
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
    band = StatBand(
        point=0.0, lo=-1.0, hi=1.0, n_resamples=5, level=0.9, tier="monthly", resample_length=48
    )
    reference = ReferenceStats(
        blocks={"global": BlockReference(block="global", stats={"g1.mean": band})},
        cross_blocks={},
        active_blocks=("global",),
        vintage_id="v",
        n_resamples=5,
        seed=1,
        missing_factors=(),
    )
    ensemble = _constant_ensemble(0.5)

    report = run_battery(
        ensemble, reference=reference, prereg=_real_prereg(), manifest=load_manifest(), seed=0
    )

    payload = json.loads(report.to_json())
    result = next(r for r in payload["unfiltered"]["tiers"]["monthly"] if r["name"] == "g1.mean")
    assert result["band"]["resample_length"] == 48

    md = report.to_markdown()
    assert "resample_length" in md, "the markdown table must name the column"
    assert "48" in md, "the markdown table must show the actual value"


def test_battery_report_markdown_shows_unmatched_resample_length_plainly() -> None:
    """The other half of the same property: a band with no `resample_length` (drawn at
    the full historical sample, never length-matched) must render as an explicit
    absence, not merely an empty cell indistinguishable from a missing band."""
    band_no_length = StatBand(point=0.0, lo=-1.0, hi=1.0, n_resamples=5, level=0.9, tier="monthly")
    assert band_no_length.resample_length is None
    from ah.eval.battery import MetricResult, _result_dict

    result = MetricResult(
        name="g1.mean",
        suite="s",
        tier="monthly",
        value=0.5,
        mc_error=None,
        band=band_no_length,
        severity="report",
        passed=None,
    )
    encoded = _result_dict(result)
    assert encoded["band"]["resample_length"] is None


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
    with pytest.raises(FrozenInstanceError):
        r.value = 2.0  # type: ignore[misc]


def test_metric_spec_is_frozen() -> None:
    spec = MetricSpec(name="x.mean", tier="monthly", fn=lambda e: 0.0, suite="s")
    with pytest.raises(FrozenInstanceError):
        spec.name = "y.mean"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# 6. WP2.2 Task 1 fix pass: MC-error meta, the one NaN rule, report accounting,
#    the aggregate verdict, and verify()-at-invocation.
# --------------------------------------------------------------------------- #


def test_mc_error_sub_ensemble_meta_n_paths_matches_its_paths() -> None:
    """I1: `mc_error` sliced `paths[idx]` but passed `meta=ensemble.meta` unchanged.

    `Ensemble.n_paths` reads `paths.shape[0]`; `EnsembleMeta.n_paths` is an independent
    field. Passing the parent's meta onto a subsample deliberately manufactures
    instances where the two disagree -- and a Tasks 2-6 metric reading `e.meta.n_paths`
    (entirely natural: it is the documented lineage record) would get a silently wrong
    MC error on every subsample.
    """
    rng = np.random.Generator(np.random.PCG64(11))
    n_paths = 100
    values = rng.normal(0.0, 1.0, size=(n_paths, 3))
    ensemble = Ensemble(paths=values[:, :, None], factor_names=["g1"], meta=_uniform_meta(n_paths))

    seen: list[tuple[int, int]] = []

    def metric(e: Ensemble) -> float:
        seen.append((e.n_paths, e.meta.n_paths))
        return float(np.mean(e.factor("g1")))

    mc_error(metric, ensemble, seed=5, n_subsamples=10)

    assert seen, "expected mc_error to evaluate the metric on sub-ensembles"
    for actual, declared in seen:
        assert actual == declared, (
            f"sub-ensemble carries {actual} paths but its meta declares {declared}"
        )
    assert sum(actual for actual, _ in seen) == n_paths  # disjoint and exhaustive


def test_nan_metric_fails_a_threshold_rather_than_passing_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I2: an uncomputable metric has not demonstrated compliance.

    `ah/battery/report.py::evaluate` treated NaN as PASS while
    `ah/eval/battery.py::_passed` treated it as FAIL -- two divergent rules, both
    inside the seal. One rule now: NaN = FAIL, on both sides.
    """
    name = "_test_nan_fails"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [MetricSpec(name="g1.mean", tier="monthly", fn=lambda e: float("nan"), suite=name)],
    )
    prereg_obj, manifest = _write_synthetic_prereg(
        tmp_path, min_v=-1.0, max_v=1.0, severity="enforce"
    )

    report = run_battery(
        _constant_ensemble(0.5),
        reference=_band_reference(point=0.0),
        prereg=prereg_obj,
        manifest=manifest,
        seed=0,
    )

    result = next(r for r in report.results if r.name == "g1.mean")
    assert np.isnan(result.value)
    assert result.passed is False


def test_battery_report_carries_missing_factor_accounting_and_a_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I5 (+ I3, I4): the report must say what was missing, why, and whether it passed."""
    name = "_test_report_accounting"
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
    reference = ReferenceStats(
        blocks={"global": BlockReference(block="global", stats={"g1.mean": _a_band()})},
        cross_blocks={},
        active_blocks=("global",),
        vintage_id="v",
        n_resamples=5,
        seed=1,
        missing_factors=("commodities", "hy_spread"),
        missing_declared=("commodities",),
        missing_no_data=("hy_spread",),
        coverage={
            "g1": FactorCoverage(first_date="1926-07-01", last_date="2020-12-01", n_obs=1134)
        },
    )

    report = run_battery(
        _constant_ensemble(0.5),
        reference=reference,
        prereg=prereg_obj,
        manifest=manifest,
        seed=0,
    )

    assert report.missing_declared == ("commodities",)
    assert report.missing_no_data == ("hy_spread",)
    assert report.passed is True  # the only enforce metric is inside its band

    payload = json.loads(report.to_json())
    assert payload["missing_factors"]["no_data"] == ["hy_spread"]
    assert payload["missing_factors"]["declared_unavailable"] == ["commodities"]
    assert payload["passed"] is True
    assert payload["coverage"]["g1"]["n_obs"] == 1134

    md = report.to_markdown()
    assert "hy_spread" in md
    assert "1926-07-01" in md  # I4: per-factor coverage is visible, not just recorded


def test_battery_report_aggregate_verdict_is_false_on_an_enforce_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = "_test_report_verdict_fail"
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

    report = run_battery(
        _constant_ensemble(5.0),  # outside [-1, 1]
        reference=_band_reference(point=0.0),
        prereg=prereg_obj,
        manifest=manifest,
        seed=0,
    )

    assert report.passed is False
    assert [r.name for r in report.enforce_failures] == ["g1.mean"]


def test_report_severity_metric_failure_does_not_fail_the_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = "_test_report_verdict_report_tier"
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
        tmp_path, min_v=-1.0, max_v=1.0, severity="report"
    )

    report = run_battery(
        _constant_ensemble(5.0),
        reference=_band_reference(point=0.0),
        prereg=prereg_obj,
        manifest=manifest,
        seed=0,
    )

    assert report.results[0].passed is False
    assert report.enforce_failures == ()
    assert report.passed is True


def test_run_battery_verifies_a_sealed_preregistration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I6: plan Sec.WP2.3 requires verify() at every battery/G2 invocation.

    It cannot run unconditionally while the pre-registration is unsealed (the
    provisional document does not satisfy every check yet), so the call is guarded on
    `prereg.sealed` -- present, not silently absent. Proved by loading a *sealed*
    synthetic pre-registration that verify() must reject and asserting run_battery
    refuses to produce a report from it.
    """
    name = "_test_verify_called"
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
    factors_path = tmp_path / "factors.yaml"
    factors_path.write_text(
        "factor_blocks:\n  global: [g1]\nactive_blocks: [global]\n"
        "factor_sources:\n  g1: {kind: series, series_id: s.g1, units: ret}\n",
        encoding="utf-8",
    )
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(
        'schema_version: "1.0"\n'
        "sealed: true\n"  # sealed, so verify() must run
        "factor_manifest: factors.yaml\n"
        "active_blocks: [global]\n"
        "thresholds:\n"
        "  blocks:\n"
        "    global:\n"
        "      g1.mean: {min: -1.0, max: 1.0, severity: enforce}\n"
        "  cross_blocks: {}\n",  # no conventions block at all -> verify() fails
        encoding="utf-8",
    )
    sealed_prereg = prereg_mod.load(prereg_path)
    manifest = load_manifest(factors_path)

    with pytest.raises(prereg_mod.PreRegError):
        run_battery(
            _constant_ensemble(0.5),
            reference=_band_reference(point=0.0),
            prereg=sealed_prereg,
            manifest=manifest,
            seed=0,
        )


def test_every_registered_reference_stat_tier_is_a_battery_tier() -> None:
    """Minor: `battery.TIERS` and `reference.py`'s per-stat tiers were two independent
    statements of one vocabulary. A stat registered with a tier the battery does not
    know would be reported under a tier heading that never renders.
    """
    from ah.eval.reference import CROSS_BLOCK_STATS, SINGLE_FACTOR_STATS

    for stat_name, registered in SINGLE_FACTOR_STATS.items():
        assert registered.tier in battery.TIERS, stat_name
    for stat_name, cross in CROSS_BLOCK_STATS.items():
        assert cross.tier in battery.TIERS, stat_name


def test_dry_run_seal_needs_no_out_path() -> None:
    """Minor: `run_battery` passed `out_path=Path("unused-dry-run.lock")`, a dead
    required argument for a call that writes nothing.
    """
    digest = prereg_mod.seal(prereg_mod.load().source_path, sealed_at="n/a", dry_run=True)
    assert digest.startswith("sha256:")


# --------------------------------------------------------------------------- #
# WP2.3 final pass -- criterion_bearing checks the VINTAGE, not only the size
# --------------------------------------------------------------------------- #


def _sized_ensemble(*, n_paths: int, months: int, vintage_id: str) -> Ensemble:
    """A minimal one-factor ensemble with the given size and vintage identity."""
    return Ensemble(
        paths=np.zeros((n_paths, months, 1)),
        factor_names=["g1"],
        meta=EnsembleMeta(
            generator_id="test",
            vintage_id=vintage_id,
            seed=0,
            n_paths=n_paths,
            months=months,
        ),
    )


def test_criterion_bearing_requires_the_sealed_vintage_not_only_the_sealed_size() -> None:
    """``multi_seed_decision_rule.criterion_bearing_runs_only`` names three conditions;
    ``criterion_bearing`` used to record ONE.

    The size was compared and the vintage was not -- ``ensemble.meta.vintage_id`` was
    carried onto the report and never checked -- so a full-size run against a superseded
    vintage was stamped ``criterion_bearing: true``. That hazard was live: superseded
    vintages stay on disk and stay reachable through the catalog's append-only pointer
    history, and a predecessor of the campaign vintage can be an incomplete snapshot
    (``governance/retrofit-register.md`` RFR-62). This pins the fix against the REAL
    sealed document, so the sealed sentence and the code cannot drift apart.
    """
    sealed = prereg_mod.load()
    assert sealed.sealed is True
    size = sealed.raw["ensemble_size"]
    vintage = sealed.raw["campaign_vintage_id"]

    at_criterion = _sized_ensemble(
        n_paths=size["n_paths"], months=size["months"], vintage_id=vintage
    )
    assert battery.criterion_bearing_for(at_criterion, sealed) is True

    # The exact hazard: sealed size, WRONG vintage. `2026-07-24` is a real superseded
    # vintage in this repo's catalog and is missing `fred.FEDFUNDS` entirely.
    wrong_vintage = _sized_ensemble(
        n_paths=size["n_paths"], months=size["months"], vintage_id="2026-07-24"
    )
    assert wrong_vintage.meta.vintage_id != vintage
    assert battery.criterion_bearing_for(wrong_vintage, sealed) is False

    # The size half still holds, both axes.
    assert (
        battery.criterion_bearing_for(
            _sized_ensemble(n_paths=16, months=size["months"], vintage_id=vintage), sealed
        )
        is False
    )
    assert (
        battery.criterion_bearing_for(
            _sized_ensemble(n_paths=size["n_paths"], months=60, vintage_id=vintage), sealed
        )
        is False
    )


def test_criterion_bearing_is_none_while_unsealed_and_false_without_a_sealed_vintage() -> None:
    """``None`` is "no criterion exists to compare against", which is not the same claim
    as ``False`` ("this run is not citable"). A sealed document that names no campaign
    vintage is the second case, not the first: the campaign cannot be identified, so
    nothing can be shown to have run against it."""
    draft = _real_prereg()  # the real document, sealed=False
    ensemble = _sized_ensemble(n_paths=1024, months=120, vintage_id="anything")
    assert battery.criterion_bearing_for(ensemble, draft) is None

    sealed = prereg_mod.load()
    raw = dict(sealed.raw)
    del raw["campaign_vintage_id"]
    no_vintage = dataclasses.replace(sealed, raw=raw)
    assert battery.criterion_bearing_for(ensemble, no_vintage) is False

    raw_no_size = dict(sealed.raw)
    del raw_no_size["ensemble_size"]
    assert battery.criterion_bearing_for(
        ensemble, dataclasses.replace(sealed, raw=raw_no_size)
    ) is (None)


# --------------------------------------------------------------------------- #
# WP2.2 Task 2 fix pass -- Critical 1: an orchestration step that actually runs
#
# Before this, no production code path called any `register_*_suite()`, so
# `battery.SUITES` was empty in every non-test run: `run_battery` computed zero
# metrics and returned a report whose `passed` was vacuously True. These tests
# assert a real run returns a NON-EMPTY metric set, computed against a reference
# this call itself computed from the catalog.
# --------------------------------------------------------------------------- #


def _orchestration_manifest() -> FactorManifest:
    return FactorManifest(
        blocks={"global": ("g1",), "us": ("u1",)},
        active_blocks=("global", "us"),
        sources={
            "g1": FactorSource(
                kind="series", series_id="s.g1", units="ret", numeraire="total_return"
            ),
            "u1": FactorSource(
                kind="series", series_id="s.u1", units="ret", numeraire="total_return"
            ),
        },
    )


def _orchestration_access(months: int = 900, seed: int = 77) -> DataAccess:
    dates = pd.date_range("1940-01-01", periods=months, freq="MS")
    rng = np.random.Generator(np.random.PCG64(seed))
    frames = {
        "s.g1": pd.DataFrame({"date": dates, "value": rng.normal(0.0, 0.04, size=months)}),
        "s.u1": pd.DataFrame({"date": dates, "value": rng.normal(0.0, 0.02, size=months)}),
    }

    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in frames:
            raise KeyError(series_id)
        return frames[series_id]

    return DataAccess(reader)


def _orchestration_ensemble(n_paths: int = 24, months: int = 120) -> Ensemble:
    rng = np.random.Generator(np.random.PCG64(78))
    paths = np.stack(
        [
            rng.normal(0.0, 0.04, size=(n_paths, months)),
            rng.normal(0.0, 0.02, size=(n_paths, months)),
        ],
        axis=-1,
    )
    meta = EnsembleMeta(
        generator_id="orchestration-test",
        vintage_id="v-orchestration",
        seed=0,
        n_paths=n_paths,
        months=months,
        active_blocks=("global", "us"),
    )
    return Ensemble(paths=paths, factor_names=["g1", "u1"], meta=meta)


def test_run_full_battery_returns_a_non_empty_metric_set() -> None:
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    assert report.results, "a real battery run must compute at least one metric"
    monthly = {r.name for r in report.results if r.suite == "monthly"}
    assert "g1.skew" in monthly
    assert "g1.acf_abs_lag24" in monthly
    assert "cross_block_corr_matrix_distance" in monthly

    # WP2.2 Task 3: the horizon suite must be wired into run_full_battery too --
    # mirrors the lesson RFR-13 records for a suite that is written and tested but
    # never registered in _REFERENCE_DEPENDENT_SUITE_BUILDERS.
    horizon = {r.name for r in report.results if r.suite == "horizon"}
    assert horizon, "run_full_battery must register and run the horizon suite"
    assert "g1.variance_ratio_12m" in horizon
    assert "g1.mean_reversion_halflife" in horizon
    assert "g1.ergodicity_gap" in horizon
    assert "regime_duration_mean" in horizon
    assert "ten_year_return_vs_valuation_slope" in horizon
    horizon_results = {r.name: r for r in report.results if r.suite == "horizon"}
    assert horizon_results["g1.variance_ratio_12m"].tier == "1_5yr"
    assert horizon_results["g1.ergodicity_gap"].tier == "10yr"
    # Structural-gap metrics are honestly NaN, and every 10yr one still carries a
    # (NaN) Monte-Carlo error rather than none at all.
    assert np.isnan(horizon_results["regime_duration_mean"].value)
    assert horizon_results["ten_year_return_vs_valuation_slope"].mc_error is not None


def test_run_full_battery_returns_tails_and_utility_metrics_by_name() -> None:
    """WP2.2 Task 4: `tails` and `utility` must be wired the identical way `horizon`
    was wired in Task 3 (`_REFERENCE_DEPENDENT_SUITE_BUILDERS`, not a hand-edit of
    `run_full_battery` itself) -- this test is the direct analogue of the horizon
    assertions in `test_run_full_battery_returns_a_non_empty_metric_set` above, and
    fails identically to how that one would fail if a later task's suite were written,
    tested, and never registered (RFR-13)."""
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    tails_results = {r.name: r for r in report.results if r.suite == "tails"}
    assert tails_results, "run_full_battery must register and run the tails suite"
    # The D4 strategy names' own metrics are present (though NaN here: the
    # orchestration fixture's factors are g1/u1, not the real D4 strategies' equity_mkt
    # etc, so every strategy leg is absent from this ensemble -- see
    # ah.eval.metrics.tails.build_tails_suite's absent-leg NaN guard).
    assert "sixty_forty.var_95" in tails_results
    assert tails_results["sixty_forty.var_95"].tier == "monthly"
    assert np.isnan(tails_results["sixty_forty.var_95"].value)
    # The cross-block tail-dependence metrics ARE computable on this fixture (g1/u1
    # are a real active cross-block pair), and must produce a REAL, finite number --
    # not NaN -- proving the suite is not universally NaN by construction.
    assert "g1~u1.tail_dependence_lower" in tails_results
    assert np.isfinite(tails_results["g1~u1.tail_dependence_lower"].value)

    utility_results = {r.name: r for r in report.results if r.suite == "utility"}
    assert utility_results, "run_full_battery must register and run the utility suite"
    assert {"discriminative_score", "predictive_score", "tstr_degradation"} == set(utility_results)
    for r in utility_results.values():
        assert r.tier == "monthly"
        # g1/u1 ARE shared between the real historical series and this ensemble, so
        # the utility tier is genuinely computable here too.
        assert np.isfinite(r.value)


def test_run_full_battery_returns_memorization_economics_calibration_metrics_by_name() -> None:
    """WP2.2 Task 5: `memorization`, `economics` and `calibration` must be wired the
    identical way Task 3/4 wired `horizon`/`tails`/`utility` -- the direct analogue of
    the assertions above, and it fails identically to how it would fail if Task 5's
    suites were written, tested, and never registered (RFR-13).

    `economics`/`calibration` are largely NaN on THIS fixture's synthetic g1/u1 factor
    names (economics needs the real factor names -- equity_mkt, policy_rate, cpi, etc
    -- and calibration is scoped to conventions.return_bearing_factors, which does not
    include g1/u1 either) -- exactly the same "sixty_forty.var_95 is NaN here" shape
    `test_run_full_battery_returns_tails_and_utility_metrics_by_name` already accepts
    for `tails`; both suites are proven to compute REAL, finite values on realistic
    fixtures in `tests/test_economics.py`/`tests/test_calibration.py`. `memorization`
    IS genuinely computable on g1/u1 (they are shared, real-valued factors with enough
    train+validation history in this fixture), so it is asserted finite here.
    """
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    memorization_results = {r.name: r for r in report.results if r.suite == "memorization"}
    assert memorization_results, "run_full_battery must register and run the memorization suite"
    assert {
        "nn_distance_p05",
        "nn_distance_p50",
        "membership_inference_auc",
        "near_duplicate_fraction",
    } == set(memorization_results)
    for r in memorization_results.values():
        assert r.tier == "monthly"
        assert np.isfinite(r.value), (r.name, r.value)

    economics_results = {r.name: r for r in report.results if r.suite == "economics"}
    assert economics_results, "run_full_battery must register and run the economics suite"
    assert "term_premium" in economics_results
    assert economics_results["term_premium"].tier == "economic"
    assert np.isnan(economics_results["term_premium"].value)
    from ah.data.derive import REGIME_LABELS

    assert economics_results["implied_sharpe_EXP"].status == "structurally_unavailable"
    assert all(f"implied_sharpe_{r}" in economics_results for r in REGIME_LABELS)

    calibration_results = {r.name: r for r in report.results if r.suite == "calibration"}
    assert calibration_results, "run_full_battery must register and run the calibration suite"
    assert "pit_ks_stat_1y" in calibration_results
    assert calibration_results["pit_ks_stat_1y"].tier == "monthly"


def test_run_full_battery_returns_conditional_metrics_by_name() -> None:
    """WP2.2 Task 6: `conditional` must be wired the identical way Tasks 3-5 wired
    `horizon`/`tails`/`utility`/`memorization`/`economics`/`calibration` -- the direct
    analogue of the assertions above, and fails identically to how it would fail if
    Task 6's suite were written, tested, and never registered (RFR-13).

    This assertion FAILED before `conditional` was added to
    `ah.eval.battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` (`report.results` carried no
    `suite == "conditional"` rows at all -- `KeyError`/empty-set, not a passing
    assertion).

    Every value is honestly NaN here: `_orchestration_ensemble()`'s
    `generator_id="orchestration-test"` has no registered factory in `ah.gen.registry`
    (no generator is registered in production until WP2.4), so
    `ah.eval.metrics.conditional._regenerate` cannot resolve it and every metric NaNs
    by design -- see that module's docstring's "Platform-gap consequence, stated
    plainly". `tests/test_conditional.py` proves the suite computes real, finite,
    discriminating values once a generator IS registered.
    """
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    conditional_results = {r.name: r for r in report.results if r.suite == "conditional"}
    assert conditional_results, "run_full_battery must register and run the conditional suite"
    assert {
        "condition_adherence_error_inflation",
        "condition_adherence_error_p90_inflation",
        "condition_adherence_error_rate",
        "condition_adherence_error_p90_rate",
        "condition_adherence_error_crisis_timing",
        "condition_adherence_error_p90_crisis_timing",
        "condition_adherence_error_crisis_severity",
        "condition_adherence_error_p90_crisis_severity",
        "off_support_adherence_at_typical",
        "off_support_adherence_at_p95",
        "off_support_adherence_at_p99",
        "off_support_adherence_at_beyond",
        "off_support_pass_rate_at_typical",
        "off_support_pass_rate_at_p95",
        "off_support_pass_rate_at_p99",
        "off_support_pass_rate_at_beyond",
    } == set(conditional_results)
    for r in conditional_results.values():
        assert r.tier == "monthly"
        assert r.suite == "conditional"
        # "orchestration-test" has no registered generator -- a platform gap, not a
        # generator-quality signal (see the module docstring).
        assert np.isnan(r.value), (r.name, r.value)
        assert r.severity == "report", (r.name, r.severity)


def test_run_full_battery_orchestration_fixture_fails_on_the_money_pump_and_floor_gates() -> None:
    """Important 7 (WP2.2 Task 5 fix pass): the orchestration fixture's factors are
    synthetic g1/u1, not the real D4 legs -- it emits NONE of
    conventions.numeraire_zero_cost_legs (smb/hml/mom/credit_xs_hy) and none of
    RATE_FLOOR_FACTORS/SPREAD_FLOOR_FACTORS, so money_pump_violations and
    floor_violations are both NaN on this fixture (see
    ah.eval.metrics.economics.build_economics_suite's absent-input NaN guard). Both are
    sealed enforce/max:0 in pre-registration.yaml, and THE ONE NaN RULE means a NaN
    enforce metric FAILS -- so this real orchestration path produces two enforce
    failures and BatteryReport.passed is False. No test previously asserted a verdict
    on this fixture at all, so this behaviour (a deliberate, documented consequence --
    see economics.py's module docstring and governance/retrofit-register.md RFR-30, not
    a bug) was unpinned and could regress silently in either direction. This test pins
    it: any ensemble not emitting the audited factors hard-fails G2 on an audit it
    structurally cannot be checked against, and WP2.4's generator must emit at least
    one factor from each audited set for a real battery run to reach a genuine
    (non-NaN-forced) verdict on these two gates.
    """
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    economics_results = {r.name: r for r in report.results if r.suite == "economics"}
    assert np.isnan(economics_results["money_pump_violations"].value)
    assert np.isnan(economics_results["floor_violations"].value)
    assert economics_results["money_pump_violations"].severity == "enforce"
    assert economics_results["floor_violations"].severity == "enforce"
    assert economics_results["money_pump_violations"].passed is False
    assert economics_results["floor_violations"].passed is False

    enforce_failure_names = {r.name for r in report.enforce_failures}
    assert {"money_pump_violations", "floor_violations"} <= enforce_failure_names
    assert report.passed is False


def test_run_full_battery_attaches_real_reference_bands_and_coverage() -> None:
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    assert set(report.coverage) == {"g1", "u1"}, "the reference was actually computed"
    banded = [r for r in report.results if r.band is not None]
    assert banded, "no metric matched a computed reference band by name"
    # Important 3: the reference replicates are drawn at the ENSEMBLE's path length, so
    # both sides of every per-path statistic carry the same estimator bias -- EXCEPT for
    # the statistics whose registry entry declares `length_matched=False`, which are
    # drawn at the full train+validation length instead and record `None` (WP2.2 Task 3's
    # decade frequencies; WP2.2 Task 4's tail-dependence coefficients). The assertion is
    # over the split, not a blanket value, so a future statistic silently opting out of
    # length matching still fails here.
    unmatched_stats = {
        name for name, reg in reference_mod.SINGLE_FACTOR_STATS.items() if not reg.length_matched
    } | {name for name, reg in reference_mod.CROSS_BLOCK_STATS.items() if not reg.length_matched}
    assert unmatched_stats, "the split this assertion is over must be non-empty"
    for r in banded:
        assert r.band is not None
        stat = r.name.split(".", 1)[1] if "." in r.name else r.name
        expected = None if stat in unmatched_stats else ensemble.months
        assert r.band.resample_length == expected, (r.name, r.band.resample_length)


def test_run_full_battery_is_repeatable_without_a_duplicate_registration_error() -> None:
    """`register_suite` refuses to re-register a name, so an orchestration step that
    registered naively would work exactly once per process."""
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()
    kwargs: dict[str, Any] = dict(
        access=_orchestration_access(),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )
    first = battery.run_full_battery(ensemble, **kwargs)
    second = battery.run_full_battery(ensemble, **kwargs)
    assert [r.name for r in first.results] == [r.name for r in second.results]
    # WP2.2 Task 3: some horizon metrics are honestly, deterministically NaN (the
    # structural-gap metrics -- see ah.eval.metrics.horizon's module docstring), and
    # `nan != nan`, so a plain list `==` would fail even on a bit-identical rerun.
    # np.testing.assert_equal treats matching NaNs as equal, which is what
    # "repeatable" actually means here.
    np.testing.assert_equal([r.value for r in first.results], [r.value for r in second.results])


def test_run_full_battery_judges_against_the_reference_the_second_call_actually_built() -> None:
    """Minor 4 (WP2.2 Task 2 fix pass 2). The existing repeatability test above runs the
    SAME reference twice, so it only proves no `BatteryError` is raised on a second
    call -- it would pass just as well under a regression to `SUITES.setdefault` (i.e.
    "register once, keep serving the first run's specs forever"). The property that
    actually matters is that a second call against a DIFFERENT reference is judged
    against THAT reference: `cross_block_corr_matrix_distance` closes over the
    reference's own correlation points, so two calls fed different underlying data must
    produce two different values. A `setdefault`-style regression would make both calls
    return the FIRST call's value, unchanged.
    """
    manifest = _orchestration_manifest()
    ensemble = _orchestration_ensemble()

    report_a = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(seed=77),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )
    report_b = battery.run_full_battery(
        ensemble,
        access=_orchestration_access(seed=4242),
        manifest=manifest,
        prereg=_real_prereg(),
        seed=0,
        reference_seed=11,
        n_resamples=8,
        block_length=24,
    )

    value_a = next(
        r.value for r in report_a.results if r.name == "cross_block_corr_matrix_distance"
    )
    value_b = next(
        r.value for r in report_b.results if r.name == "cross_block_corr_matrix_distance"
    )
    assert value_a != value_b, (
        "two different references must judge cross_block_corr_matrix_distance "
        "differently -- identical values here would mean the second call is still "
        "judged against the first call's reference"
    )


def test_panel_threshold_is_found_by_the_metric_name_lookup() -> None:
    """A panel statistic carries no factor prefix, so it is looked up in its own
    `thresholds.panel` section rather than under a block or a pair."""
    loaded = prereg_mod.load()
    assert loaded.panel_thresholds, "the real pre-registration declares a panel threshold"
    name = next(iter(loaded.panel_thresholds))
    assert battery._lookup_threshold(name, loaded) is loaded.panel_thresholds[name]


# --------------------------------------------------------------------------- #
# 11. WP2.2 Task 3 fix pass 1: the guards that only count if a real run trips them
# --------------------------------------------------------------------------- #


def test_missing_mc_error_is_rejected_through_run_battery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """IMPORTANT 1. The three tests above call ``_require_mc_error_reported`` directly
    with hand-passed arguments, so the ONE failure the guard exists for -- a refactor
    that drops the call site -- was caught by nothing. This drives a real
    ``run_battery`` with ``mc_error`` returning ``None`` and asserts the rejection."""
    name = "_test_mc_error_guard"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="g1.mean", tier="10yr", fn=lambda e: float(np.mean(e.factor("g1"))), suite=name
            )
        ],
    )
    monkeypatch.setattr(battery, "mc_error", lambda *args, **kwargs: None)
    prereg, manifest = _write_synthetic_prereg(tmp_path, min_v=-1.0, max_v=1.0, severity="report")
    with pytest.raises(BatteryError, match="10yr"):
        run_battery(
            _constant_ensemble(0.0),
            reference=_band_reference(0.0),
            prereg=prereg,
            manifest=manifest,
            seed=3,
        )


def test_structurally_unavailable_status_is_visible_in_json_and_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A structural gap and a genuine generator failure are both bare NaN in the
    report today, and under THE ONE NaN RULE an ``enforce`` threshold on the former
    fails every run forever. The status marker (and any metric metadata) must reach the
    G2 evidence artifact, not stay in a module constant."""
    name = "_test_status_marker"
    _clean_suite_name(monkeypatch, name)
    register_suite(
        name,
        [
            MetricSpec(
                name="g1.mean",
                tier="10yr",
                fn=lambda e: float("nan"),
                suite=name,
                status="structurally_unavailable",
                metadata=(("regime_ruleset_version", "regime_ruleset_v1"),),
            )
        ],
    )
    prereg, manifest = _write_synthetic_prereg(tmp_path, min_v=-1.0, max_v=1.0, severity="report")
    report = run_battery(
        _constant_ensemble(0.0),
        reference=_band_reference(0.0),
        prereg=prereg,
        manifest=manifest,
        seed=3,
    )
    entry = report.to_dict()["unfiltered"]["tiers"]["10yr"][0]
    assert entry["status"] == "structurally_unavailable"
    assert entry["metadata"] == {"regime_ruleset_version": "regime_ruleset_v1"}
    markdown = report.to_markdown()
    assert "structurally_unavailable" in markdown
    assert "regime_ruleset_version=regime_ruleset_v1" in markdown


def test_register_suite_rejects_an_unknown_status(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "_test_bad_status"
    _clean_suite_name(monkeypatch, name)
    with pytest.raises(BatteryError, match="status"):
        register_suite(
            name,
            [
                MetricSpec(
                    name="g1.mean",
                    tier="monthly",
                    fn=lambda e: 0.0,
                    suite=name,
                    status="probably_fine",
                )
            ],
        )
