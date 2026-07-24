"""WP0.8 acceptance: stylized-fact functions + battery plumbing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

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


def test_thresholds_yaml_loads_all_todo() -> None:
    thresholds = load_thresholds()
    assert thresholds  # non-empty
    assert all(spec.get("status") == "todo" for spec in thresholds.values())


def test_run_battery_on_stagflation_passes() -> None:
    report = run_battery(_ensemble())
    assert report.version == BATTERY_VERSION
    assert report.checks  # metrics were evaluated
    assert report.passed  # all thresholds are todo -> non-blocking
    assert report.enforce_failures == []


def test_enforce_failure_is_detected() -> None:
    scalars = {"excess_kurtosis": 5.0}
    thresholds = {"excess_kurtosis": {"max": 0.0, "status": "enforce"}}
    checks = evaluate(scalars, thresholds)
    assert checks[0].ok is False
    # and it surfaces through a report
    report = run_battery(_ensemble(), {"excess_kurtosis": {"max": -100.0, "status": "enforce"}})
    assert not report.passed
    assert report.enforce_failures


def test_todo_failure_is_non_blocking() -> None:
    report = run_battery(_ensemble(), {"excess_kurtosis": {"max": -100.0, "status": "todo"}})
    # the check fails but status is todo -> still passes
    assert report.passed


def test_render_markdown_and_json() -> None:
    report = run_battery(_ensemble())
    md = render_markdown(report)
    assert BATTERY_VERSION in md
    assert "enforce failures: 0" in md
    payload = json.loads(render_json(report))
    assert payload["passed"] is True
    assert "excess_kurtosis" in payload["scalars"]


def test_main_returns_zero() -> None:
    assert main([]) == 0
