"""WP0.8 acceptance: stylized-fact functions + battery plumbing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ah.battery.report import (
    BATTERY_VERSION,
    evaluate,
    load_thresholds,
    main,
    render_json,
    render_markdown,
    run_battery,
)
from ah.battery.stylized import (
    acf,
    acf_abs,
    corr_matrix_distance,
    excess_kurtosis,
    hill_tail_index,
    max_drawdown,
    max_drawdown_distribution,
    skewness,
)
from ah.core.engine import run_ensemble
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.eval import prereg
from ah.factors import load_manifest

ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE: dict[str, Any] = json.loads(
    (ROOT / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
)


def _ensemble(n_paths: int = 32) -> Any:
    doc = dict(_EXAMPLE)
    doc = json.loads(json.dumps(doc))
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_ensemble(nw, n_paths, base_seed=42)


# --------------------------------------------------------------------------- #
# stylized functions
# --------------------------------------------------------------------------- #


def test_excess_kurtosis_known_value() -> None:
    # [-1,1,-1,1]: mean 0, var 1, mean(x^4)=1 -> excess = 1 - 3 = -2
    assert excess_kurtosis(np.array([-1.0, 1.0, -1.0, 1.0])) == -2.0


def test_excess_kurtosis_constant_is_zero() -> None:
    assert excess_kurtosis(np.array([5.0, 5.0, 5.0])) == 0.0


def test_skewness_symmetric_is_zero() -> None:
    assert abs(skewness(np.array([-2.0, -1.0, 1.0, 2.0]))) < 1e-12


def test_acf_lag0_absent_and_white_noise_near_zero() -> None:
    rng = np.random.Generator(np.random.PCG64(0))
    x = rng.standard_normal(5000)
    a = acf(x, [1, 2, 3])
    assert len(a) == 3
    assert all(abs(v) < 0.1 for v in a)


def test_acf_out_of_range_lag_is_zero() -> None:
    assert acf(np.array([1.0, 2.0, 3.0]), [10]) == [0.0]


def test_acf_abs_shape() -> None:
    assert len(acf_abs(np.arange(20.0), list(range(1, 13)))) == 12


def test_max_drawdown_simple() -> None:
    # +10% then -50%: value 1.1 -> 0.55, drawdown -0.5
    assert abs(max_drawdown(np.array([10.0, -50.0])) - (-0.5)) < 1e-12


def test_max_drawdown_distribution_shape() -> None:
    m = np.array([[1.0, -2.0, 3.0], [0.0, 0.0, 0.0]])
    dd = max_drawdown_distribution(m)
    assert dd.shape == (2,)
    assert dd[1] == 0.0  # flat path has no drawdown


def test_hill_tail_index_positive_on_sample() -> None:
    rng = np.random.Generator(np.random.PCG64(1))
    x = rng.standard_normal(1000)
    alpha = hill_tail_index(x)
    assert alpha > 0


def test_corr_matrix_distance_zero_for_identical() -> None:
    a = np.eye(3)
    assert corr_matrix_distance(a, a) == 0.0


# --------------------------------------------------------------------------- #
# battery plumbing
# --------------------------------------------------------------------------- #


def test_thresholds_yaml_ratification_state() -> None:
    """Which gates are live, asserted exactly.

    HISTORY: this was ``test_thresholds_yaml_loads_all_todo`` and asserted that
    EVERY gate was ``todo``. That was true from WP0.8 until the owner ratified
    five of the seven on 2026-08-06 (AM-2026-08-06-001), so the old assertion
    encoded a temporary state as an invariant. Inverted rather than deleted, per
    the repo convention, and tightened: it now pins exactly which gates are live,
    so a future ratification or relaxation has to be deliberate.
    """
    thresholds = load_thresholds()
    assert thresholds  # non-empty
    live = {k for k, v in thresholds.items() if v.get("status") == "enforce"}
    todo = {k for k, v in thresholds.items() if v.get("status") == "todo"}
    assert live == {"excess_kurtosis", "skewness", "hill_tail_index", "max_drawdown_median"}
    # acf_r_lag1 was observed (ER-5) before any ratification, so it can never be
    # pre-registered on this generator; corr_distance has no named reference.
    # acf_abs_lag1 was ratified and withdrawn the same day (AM-2026-08-06-002):
    # the statistic moves monotonically with ensemble size, so no band bounds it.
    assert todo == {"acf_r_lag1", "acf_abs_lag1", "corr_distance"}


def test_run_battery_on_stagflation_passes_every_ratified_gate() -> None:
    """The engine meets its own ratified battery — since toy-v0.5, and not before.

    HISTORY, in three acts. (1) This was ``test_run_battery_on_stagflation_passes``
    and asserted ``report.passed``, which held only because every gate was
    ``todo``. (2) Ratification on 2026-08-06 made the gates real and the first
    ratified run failed one: pooled equity ``excess_kurtosis`` was 0.085 against
    a floor of 0.5 — near-Gaussian months. The test was INVERTED to assert that
    failure, with instructions to whoever fixed the engine to update it
    deliberately. (3) toy-v0.5 (register ER-7 closed: standardized Student-t
    innovations, df=6, plus the -99% limited-liability floor) is that fix:
    measured 2026-08-08, excess_kurtosis 2.0919 in [0.5, 8.0], skewness 0.0221,
    hill 4.3839, max_drawdown_median -0.5976 — zero enforce failures. df was
    chosen from the literature before this run and NOT tuned to the band
    (engine.py `_INNOVATION_DF` comment); the value is reported wherever it
    falls. If this goes red again, the engine changed — judge the change, do
    not touch the bands.
    """
    report = run_battery(_ensemble())
    assert report.version == BATTERY_VERSION
    assert report.checks  # metrics were evaluated
    assert [c.metric for c in report.enforce_failures] == []
    assert report.passed


def test_enforce_failure_is_detected() -> None:
    scalars = {"excess_kurtosis": 5.0}
    thresholds = {"excess_kurtosis": {"max": 0.0, "status": "enforce"}}
    checks = evaluate(scalars, thresholds)
    assert checks[0].ok is False
    # and it surfaces through a report
    report = run_battery(_ensemble(), {"excess_kurtosis": {"max": -100.0, "status": "enforce"}})
    assert not report.passed
    assert report.enforce_failures


def test_nan_metric_fails_rather_than_passing() -> None:
    """WP2.2 Task 1 fix pass, I2: ONE NaN rule across both batteries.

    This module used to skip the bound comparison entirely for a NaN value and mark the
    check ``ok``; ``ah.eval.battery._passed`` treated NaN as a failure. Both modules are
    inside the pre-registration seal, so the same generator could have been judged
    differently depending on which battery ran. The rule is now: an uncomputable metric
    has not demonstrated compliance, so it FAILS -- and it fails even against a
    threshold that declares no bounds at all, which is the case a comparison-based
    implementation gets wrong.
    """
    checks = evaluate(
        {"excess_kurtosis": float("nan")},
        {"excess_kurtosis": {"min": -100.0, "max": 100.0, "status": "enforce"}},
    )
    assert checks[0].ok is False

    unbounded = evaluate({"excess_kurtosis": float("nan")}, {"excess_kurtosis": {"status": "todo"}})
    assert unbounded[0].ok is False

    report = run_battery(
        _ensemble(), {"excess_kurtosis": {"min": -100.0, "max": 100.0, "status": "enforce"}}
    )
    assert report.passed  # sanity: a real (non-NaN) value inside the band still passes


def test_todo_failure_is_non_blocking() -> None:
    report = run_battery(_ensemble(), {"excess_kurtosis": {"max": -100.0, "status": "todo"}})
    # the check fails but status is todo -> still passes
    assert report.passed


def test_render_markdown_and_json() -> None:
    report = run_battery(_ensemble())
    md = render_markdown(report)
    assert BATTERY_VERSION in md
    assert "enforce failures: 0" in md  # zero since toy-v0.5; see the gate test above
    payload = json.loads(render_json(report))
    assert payload["passed"] is True
    assert "excess_kurtosis" in payload["scalars"]


def test_report_records_active_blocks_from_factor_manifest() -> None:
    # WP2.1b Item 2: every battery report records active_blocks, read from factors.yaml.
    report = run_battery(_ensemble())
    assert report.active_blocks == ("global", "us", "fx", "valuation")
    assert "active_blocks: global, us, fx, valuation" in render_markdown(report)
    payload = json.loads(render_json(report))
    assert payload["active_blocks"] == ["global", "us", "fx", "valuation"]


def test_main_returns_zero_when_every_ratified_gate_passes() -> None:
    """HISTORY: was ``test_main_returns_zero`` (true while every gate was
    ``todo``), then ``test_main_returns_one_while_a_ratified_gate_fails``
    (ratification made excess_kurtosis fail its floor and CI ran red on
    purpose). toy-v0.5 gave the engine its fat tails honestly — see
    test_run_battery_on_stagflation_passes_every_ratified_gate — so the entry
    point returns 0 again, and this time the zero is EARNED: four enforce
    gates are live and all pass.
    """
    assert main([]) == 0


# --------------------------------------------------------------------------- #
# WP2.1b Item 2 acceptance: "a synthetic two-block configuration passes the battery"
# --------------------------------------------------------------------------- #


def test_run_battery_accepts_injected_synthetic_manifest(tmp_path: Path) -> None:
    # A synthetic two-block manifest, disjoint from the real repo's global/us.
    factors_path = tmp_path / "factors.yaml"
    factors_path.write_text(
        "factor_blocks:\n"
        "  alpha: [alpha_factor]\n"
        "  beta: [beta_factor]\n"
        "active_blocks: [alpha, beta]\n"
        "factor_sources:\n"
        "  alpha_factor: {kind: unavailable, reason: fixture}\n"
        "  beta_factor: {kind: unavailable, reason: fixture}\n",
        encoding="utf-8",
    )
    synthetic_manifest = load_manifest(factors_path)
    assert synthetic_manifest.active_blocks == ("alpha", "beta")

    report = run_battery(_ensemble(), manifest=synthetic_manifest)
    # This test is about MANIFEST INJECTION, not about threshold outcomes. It
    # asserted `report.passed` when every gate was `todo`; under ratified gates
    # the enforce-failure set is whatever the engine earns (empty since
    # toy-v0.5), which says nothing about whether an injected manifest is
    # accepted. Assert the thing under test instead.
    assert [c.metric for c in report.enforce_failures] == []
    assert report.active_blocks == ("alpha", "beta")
    assert "active_blocks: alpha, beta" in render_markdown(report)
    payload = json.loads(render_json(report))
    assert payload["active_blocks"] == ["alpha", "beta"]

    # A matching prereg -- block/cross-block thresholds for exactly this manifest,
    # verified against it (proves the "matching" claim, not just that the battery
    # accepted the manifest injection).
    prereg_doc = {
        "schema_version": "1.0",
        "sealed": False,
        "campaign_vintage_id": "test",
        "factor_manifest": "factors.yaml",
        "active_blocks": ["alpha", "beta"],
        "conventions": {
            "percent_to_decimal": 0.01,
            "months_per_year": 12.0,
            "return_bearing_factors": ["alpha_factor"],
            "level_factors": ["beta_factor"],
            "rebalance_cadences": ["monthly"],
            "static_weights_composition": "test fixture",
            # Required by verify() since the WP2.2 Task 1 fix pass (Critical 3).
            "numeraire": "total_return",
            "numeraire_zero_cost_legs": [],
        },
        "thresholds": {
            "blocks": {
                "alpha": {"alpha_factor.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
                "beta": {"beta_factor.std": {"min": 0.0, "max": 5.0, "severity": "report"}},
            },
            "cross_blocks": {
                "alpha|beta": {
                    "alpha_factor~beta_factor.correlation": {
                        "min": -1.0,
                        "max": 1.0,
                        "severity": "report",
                    }
                }
            },
        },
        "decisions": {},
    }
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(yaml.safe_dump(prereg_doc, sort_keys=False), encoding="utf-8")

    loaded = prereg.load(prereg_path)
    prereg.verify(loaded, synthetic_manifest)  # must not raise
