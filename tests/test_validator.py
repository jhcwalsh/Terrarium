"""WP0.3 acceptance: the V-rules (V1-V12).

The canonical stagflation example is the "clean" baseline (no clamps, no warnings,
no blocking). Each rule then gets a focused case, and a table-driven sweep asserts
each mutation raises exactly the expected rule.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ah.core.validator import (
    VALIDATOR_VERSION,
    ValidationResult,
    stamp_validation,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "schemas" / "example-long-stagflation.worldspec.json"
_EXAMPLE: dict[str, Any] = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def base() -> dict[str, Any]:
    """A fresh draft copy of the canonical example (validation stripped)."""
    w = copy.deepcopy(_EXAMPLE)
    w["status"] = "draft"
    w["provenance"].pop("validation", None)
    return w


def warn_rules(result: ValidationResult) -> list[str]:
    return [f.rule for f in result.warnings]


def block_rules(result: ValidationResult) -> list[str]:
    return [f.rule for f in result.blocking]


# --------------------------------------------------------------------------- #
# baseline + purity
# --------------------------------------------------------------------------- #


def test_canonical_example_is_clean() -> None:
    r = validate(base())
    assert r.clamps == []
    assert r.warnings == []
    assert r.blocking == []
    assert r.ok


def test_validate_does_not_mutate_input() -> None:
    w = base()
    snapshot = copy.deepcopy(w)
    w["factor_conditions"]["credit"]["hy_spread_peak_bps"] = 9999  # will be clamped
    before = copy.deepcopy(w)
    validate(w)
    assert w == before  # input untouched
    assert snapshot != before  # sanity: we did change something from the pristine


# --------------------------------------------------------------------------- #
# V9 — bounds clamps
# --------------------------------------------------------------------------- #


def test_v9_clamps_out_of_bounds_and_records_path() -> None:
    w = base()
    w["factor_conditions"]["credit"]["hy_spread_peak_bps"] = 2400  # max 2200
    r = validate(w)
    assert len(r.clamps) == 1
    c = r.clamps[0]
    assert c.path == "/factor_conditions/credit/hy_spread_peak_bps"
    assert c.submitted == 2400
    assert c.applied == 2200
    assert r.clamped_world["factor_conditions"]["credit"]["hy_spread_peak_bps"] == 2200


def test_v9_heavy_clamping_warns() -> None:
    w = base()
    fc = w["factor_conditions"]
    fc["policy_rate"]["start_pct"] = 99  # >15
    fc["policy_rate"]["end_pct"] = 99  # >20
    fc["equity"]["vol_annual_pct"] = 99  # >45
    fc["equity"]["drift_annual_pct"] = 99  # >20
    fc["commodities"]["drift_annual_pct"] = 99  # >25
    r = validate(w)
    assert len(r.clamps) == 5
    assert "V9" in warn_rules(r)


# --------------------------------------------------------------------------- #
# V2 — windows / peaks inside horizon
# --------------------------------------------------------------------------- #


def test_v2_clamps_peak_quarter_to_horizon_end() -> None:
    w = base()  # quarters = 40 -> last index 39
    w["factor_conditions"]["inflation"]["peak_quarter"] = 100
    r = validate(w)
    paths = {c.path for c in r.clamps}
    assert "/factor_conditions/inflation/peak_quarter" in paths
    assert r.clamped_world["factor_conditions"]["inflation"]["peak_quarter"] == 39


def test_v2_clamps_crisis_window_start_to_fit() -> None:
    w = base()
    w["factor_conditions"]["crisis_windows"] = [
        {"start_quarter": 38, "length_quarters": 6, "severity": 0.3}
    ]
    r = validate(w)
    win = r.clamped_world["factor_conditions"]["crisis_windows"][0]
    assert win["start_quarter"] + win["length_quarters"] <= 40
    assert win["start_quarter"] == 34


# --------------------------------------------------------------------------- #
# V3 / V1 / V4 / V5 / V6 — warnings
# --------------------------------------------------------------------------- #


def test_v3_swaps_inverted_spread_and_warns() -> None:
    w = base()
    w["factor_conditions"]["credit"]["hy_spread_start_bps"] = 700
    w["factor_conditions"]["credit"]["hy_spread_peak_bps"] = 300
    r = validate(w)
    assert "V3" in warn_rules(r)
    credit = r.clamped_world["factor_conditions"]["credit"]
    assert credit["hy_spread_start_bps"] == 300
    assert credit["hy_spread_peak_bps"] == 700


def test_v1_financial_repression_warns() -> None:
    w = base()
    w["factor_conditions"]["inflation"]["average_pct"] = 6.5  # >=5
    w["factor_conditions"]["policy_rate"]["end_pct"] = 1.5  # <=2
    assert "V1" in warn_rules(validate(w))


def test_v4_regime_condition_mismatch_warns() -> None:
    w = base()  # regimes include stagflation
    w["factor_conditions"]["inflation"]["average_pct"] = 3.0  # <4 with stagflation
    assert "V4" in warn_rules(validate(w))


def test_v5_extreme_divergence_warns() -> None:
    w = base()
    w["factor_conditions"]["equity"]["drift_annual_pct"] = 10  # >=8
    w["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] = -4  # <=-3
    assert "V5" in warn_rules(validate(w))


def test_v6_crisis_without_stress_warns() -> None:
    w = base()
    w["factor_conditions"]["credit"]["hy_spread_start_bps"] = 400
    w["factor_conditions"]["credit"]["hy_spread_peak_bps"] = 500  # <400+150
    w["factor_conditions"]["crisis_windows"] = [
        {"start_quarter": 4, "length_quarters": 4, "severity": 0.6}
    ]
    assert "V6" in warn_rules(validate(w))


# --------------------------------------------------------------------------- #
# V7 / V8 — narrative coherence
# --------------------------------------------------------------------------- #


def test_v7_dispatch_outside_horizon_warns() -> None:
    w = base()
    w["narrative"]["dispatches"].append({"date": "2040", "headline": "way later"})
    assert "V7" in warn_rules(validate(w))


def test_v8_too_few_dispatches_warns() -> None:
    w = base()
    w["narrative"]["dispatches"] = w["narrative"]["dispatches"][:2]
    assert "V8" in warn_rules(validate(w))


def test_v8_non_decreasing_dates_warn() -> None:
    w = base()
    w["narrative"]["dispatches"] = [
        {"date": "2031", "headline": "a"},
        {"date": "2028", "headline": "b"},  # goes backwards
        {"date": "2033", "headline": "c"},
    ]
    assert "V8" in warn_rules(validate(w))


# --------------------------------------------------------------------------- #
# V10 / V11 / V12 — blocking
# --------------------------------------------------------------------------- #


def test_v10_sequence_gap_blocks() -> None:
    w = base()
    w["regimes"]["sequence"][0]["to_quarter"] = 6  # leaves a gap at 7
    r = validate(w)
    assert "V10" in block_rules(r)
    assert not r.ok


def test_v10_sequence_undertiles_blocks() -> None:
    w = base()
    w["regimes"]["sequence"][-1]["to_quarter"] = 38  # ends at 38, not 39
    assert "V10" in block_rules(validate(w))


def test_v11_transition_matrix_bad_row_blocks() -> None:
    w = base()
    w["regimes"] = {
        "mode": "transition_matrix",
        "transition_matrix": {
            "states": ["expansion", "recession"],
            "matrix": [[0.5, 0.5], [0.3, 0.3]],  # row 1 sums to 0.6
            "initial_state": "expansion",
        },
    }
    assert "V11" in block_rules(validate(w))


def test_v11_transition_matrix_valid_ok() -> None:
    w = base()
    w["regimes"] = {
        "mode": "transition_matrix",
        "transition_matrix": {
            "states": ["expansion", "recession"],
            "matrix": [[0.9, 0.1], [0.2, 0.8]],
            "initial_state": "expansion",
        },
    }
    assert block_rules(validate(w)) == []


def test_v12_custom_without_sleeves_blocks() -> None:
    w = base()
    w["structural"] = {"parameter_vintage": "custom"}
    assert "V12" in block_rules(validate(w))


def test_v12_vintage_ignores_sleeves_warns() -> None:
    w = base()  # has sleeves
    w["structural"]["parameter_vintage"] = "historical_average"
    assert "V12" in warn_rules(validate(w))


# --------------------------------------------------------------------------- #
# stamping
# --------------------------------------------------------------------------- #


def test_stamp_flips_draft_to_validated_when_clean() -> None:
    r = validate(base())
    stamped = stamp_validation(r, validated_at="2026-07-24T00:00:00Z")
    assert stamped["status"] == "validated"
    v = stamped["provenance"]["validation"]
    assert v["validator_version"] == VALIDATOR_VERSION
    assert v["validated_at"] == "2026-07-24T00:00:00Z"
    assert v["clamps"] == []
    assert v["warnings"] == []


def test_stamp_leaves_status_when_blocking() -> None:
    w = base()
    w["structural"] = {"parameter_vintage": "custom"}  # V12 block
    r = validate(w)
    stamped = stamp_validation(r, validated_at="2026-07-24T00:00:00Z")
    assert stamped["status"] == "draft"  # never reaches validated


def test_stamp_records_clamps_and_warnings() -> None:
    w = base()
    w["factor_conditions"]["credit"]["hy_spread_peak_bps"] = 2400  # clamp
    w["factor_conditions"]["inflation"]["average_pct"] = 6.5
    w["factor_conditions"]["policy_rate"]["end_pct"] = 1.5  # V1 warn
    r = validate(w)
    stamped = stamp_validation(r, validated_at="2026-07-24T00:00:00Z")
    v = stamped["provenance"]["validation"]
    assert v["clamps"][0]["path"] == "/factor_conditions/credit/hy_spread_peak_bps"
    assert "V1" in [x["rule"] for x in v["warnings"]]


# --------------------------------------------------------------------------- #
# table-driven sweep
# --------------------------------------------------------------------------- #


def _mut_v1(w: dict[str, Any]) -> None:
    w["factor_conditions"]["inflation"]["average_pct"] = 6.5
    w["factor_conditions"]["policy_rate"]["end_pct"] = 1.0


def _mut_v4(w: dict[str, Any]) -> None:
    w["factor_conditions"]["inflation"]["average_pct"] = 3.0


def _mut_v5(w: dict[str, Any]) -> None:
    w["factor_conditions"]["equity"]["drift_annual_pct"] = 12
    w["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] = -5


def _mut_v7(w: dict[str, Any]) -> None:
    w["narrative"]["dispatches"].append({"date": "2099", "headline": "far future"})


_WARN_CASES: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("V1", _mut_v1),
    ("V4", _mut_v4),
    ("V5", _mut_v5),
    ("V7", _mut_v7),
]


@pytest.mark.parametrize(("rule", "mutate"), _WARN_CASES, ids=[c[0] for c in _WARN_CASES])
def test_warn_rule_table(rule: str, mutate: Callable[[dict[str, Any]], None]) -> None:
    w = base()
    mutate(w)
    assert rule in warn_rules(validate(w))


# --------------------------------------------------------------------------- #
# defensive branches / edge cases
# --------------------------------------------------------------------------- #


def test_v2_clamps_overlong_crisis_window_length() -> None:
    w = base()
    w["horizon"]["quarters"] = 8
    w["regimes"] = {"mode": "unconditional"}  # avoid V10 noise
    w["factor_conditions"]["crisis_windows"] = [
        {"start_quarter": 0, "length_quarters": 12, "severity": 0.3}
    ]
    r = validate(w)
    win = r.clamped_world["factor_conditions"]["crisis_windows"][0]
    assert win["length_quarters"] == 8
    assert any(c.path.endswith("/length_quarters") for c in r.clamps)


def test_v4_deflation_boom_via_transition_matrix() -> None:
    w = base()
    w["regimes"] = {
        "mode": "transition_matrix",
        "transition_matrix": {
            "states": ["deflation_boom", "expansion"],
            "matrix": [[0.9, 0.1], [0.1, 0.9]],
            "initial_state": "deflation_boom",
        },
    }
    w["factor_conditions"]["inflation"]["average_pct"] = 3.0  # >2 with deflation_boom
    r = validate(w)
    assert "V4" in warn_rules(r)
    assert r.blocking == []


def test_v11_non_square_matrix_blocks() -> None:
    w = base()
    w["regimes"] = {
        "mode": "transition_matrix",
        "transition_matrix": {
            "states": ["expansion", "recession", "crisis"],
            "matrix": [[0.5, 0.5], [0.5, 0.5]],  # 2x2 on 3 states
            "initial_state": "expansion",
        },
    }
    assert "V11" in block_rules(validate(w))


def test_v10_missing_sequence_blocks() -> None:
    w = base()
    w["regimes"] = {"mode": "sequence", "sequence": []}
    assert "V10" in block_rules(validate(w))


def test_v10_malformed_segment_blocks() -> None:
    w = base()
    w["regimes"]["sequence"][0]["to_quarter"] = -1  # to < from
    assert "V10" in block_rules(validate(w))


def test_unconditional_mode_has_no_regime_blocking() -> None:
    w = base()
    w["regimes"] = {"mode": "unconditional"}
    assert block_rules(validate(w)) == []


def test_v6_skipped_when_credit_absent() -> None:
    w = base()
    del w["factor_conditions"]["credit"]
    w["factor_conditions"]["crisis_windows"] = [
        {"start_quarter": 4, "length_quarters": 4, "severity": 0.9}
    ]
    r = validate(w)
    assert "V6" not in warn_rules(r)  # cannot judge stress without credit


def test_rules_skip_gracefully_when_conditions_absent() -> None:
    w = base()
    del w["factor_conditions"]["inflation"]
    del w["factor_conditions"]["policy_rate"]
    del w["factor_conditions"]["equity"]
    r = validate(w)  # must not raise
    assert "V1" not in warn_rules(r)
    assert "V5" not in warn_rules(r)


def test_stamp_creates_provenance_when_absent() -> None:
    r = validate({"status": "draft", "regimes": {"mode": "unconditional"}})
    stamped = stamp_validation(r, validated_at="2026-07-24T00:00:00Z")
    assert stamped["status"] == "validated"
    assert stamped["provenance"]["validation"]["validator_version"] == VALIDATOR_VERSION
