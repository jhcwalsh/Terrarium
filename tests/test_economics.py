"""WP2.2 Task 5 acceptance: the economic tier (implied Sharpe, term premium, ERP,
no-money-pump audit, policy-anchor sanity).

Mirrors ``tests/test_tails.py``/``tests/test_utility.py``'s conventions: every
computable metric is tested on a hand-built ensemble where the quantity is known by
construction, and -- Task 5's brief is explicit about this -- for the two
zero-violation metrics a DELIBERATELY VIOLATING ensemble must produce a non-zero count,
because a check that always reports 0 without ever being exercised the other way is
decorative, not a check.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pytest
from numpy.random import PCG64, Generator

from ah.data.derive import REGIME_LABELS
from ah.eval.battery import STRUCTURALLY_UNAVAILABLE, _passed
from ah.eval.metrics.economics import (
    ECONOMICS_MIN_OBS,
    RATE_FLOOR_FACTORS,
    RATE_FLOOR_PCT,
    SPREAD_FLOOR_FACTORS,
    SPREAD_FLOOR_PCT,
    TAYLOR_PHI_PI,
    TAYLOR_PI_TARGET,
    TAYLOR_R_STAR,
    build_economics_suite,
)
from ah.eval.reference import PANEL_STATS, ReferenceStats
from ah.factors import FactorManifest
from ah.gen.base import Ensemble, EnsembleMeta

ROOT = Path(__file__).resolve().parents[1]

_ACTIVE = (
    "equity_mkt",
    "smb",
    "hml",
    "mom",
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


def _real_manifest() -> FactorManifest:
    """The real active-factor namespace (global + us blocks), so ensemble factor names
    match ``factors.yaml`` -- required for term_premium/equity_risk_premium/
    money_pump_violations/floor_violations/policy_anchor_deviation, each of which reads
    the ensemble's OWN factor names, not a synthetic manifest."""
    from ah.factors import load_manifest

    return load_manifest()


def _empty_reference() -> ReferenceStats:
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=("global", "us"),
        vintage_id="v",
        n_resamples=1,
        seed=0,
        missing_factors=(),
    )


def _ensemble(values: dict[str, np.ndarray], n_paths: int, months: int) -> Ensemble:
    names = list(values)
    paths = np.stack([values[n] for n in names], axis=-1)
    meta = EnsembleMeta(
        generator_id="test-gen", vintage_id="v", seed=0, n_paths=n_paths, months=months
    )
    return Ensemble(paths=paths, factor_names=names, meta=meta)


def _constant_slab(value: float, n_paths: int, months: int) -> np.ndarray:
    return np.full((n_paths, months), value, dtype=np.float64)


# --------------------------------------------------------------------------- #
# 1. term_premium
# --------------------------------------------------------------------------- #


def test_term_premium_matches_a_known_constant_spread() -> None:
    n_paths, months = 4, 120
    ust_10y = _constant_slab(4.5, n_paths, months)
    policy_rate = _constant_slab(3.0, n_paths, months)
    ensemble = _ensemble({"ust_10y": ust_10y, "policy_rate": policy_rate}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert specs["term_premium"].fn(ensemble) == pytest.approx(1.5)


def test_term_premium_nan_when_a_leg_is_absent() -> None:
    ensemble = _ensemble({"ust_10y": _constant_slab(4.5, 4, 120)}, 4, 120)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["term_premium"].fn(ensemble))


def test_term_premium_nan_below_the_min_obs_floor() -> None:
    ust_10y = _constant_slab(4.5, 1, 10)
    policy_rate = _constant_slab(3.0, 1, 10)
    ensemble = _ensemble({"ust_10y": ust_10y, "policy_rate": policy_rate}, 1, 10)
    assert ust_10y.size < ECONOMICS_MIN_OBS
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["term_premium"].fn(ensemble))


# --------------------------------------------------------------------------- #
# 2. equity_risk_premium -- the sealed cash_tr_1m leg, not an independently invented one
# --------------------------------------------------------------------------- #


def test_equity_risk_premium_matches_hand_computed_cash_tr_1m() -> None:
    """cash_tr_1m = bond_total_return(policy_rate, duration_years=0.0) =
    0.01 * policy_rate_{t-1} / 12 (pure carry; r_0 = 0.0 by the sealed warm-up rule).
    At a CONSTANT policy_rate of 3.0 that is 0.01 * 3.0 / 12 = 0.0025 every month after
    month 0."""
    n_paths, months = 4, 24
    equity_mkt = _constant_slab(0.01, n_paths, months)
    policy_rate = _constant_slab(3.0, n_paths, months)
    ensemble = _ensemble({"equity_mkt": equity_mkt, "policy_rate": policy_rate}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    value = specs["equity_risk_premium"].fn(ensemble)
    cash = np.zeros(months)
    cash[1:] = 0.01 * 3.0 / 12.0
    expected = float(np.mean(equity_mkt[0] - cash))
    assert value == pytest.approx(expected)


def test_equity_risk_premium_nan_when_equity_mkt_absent() -> None:
    ensemble = _ensemble({"policy_rate": _constant_slab(3.0, 2, 24)}, 2, 24)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["equity_risk_premium"].fn(ensemble))


# --------------------------------------------------------------------------- #
# 3. money_pump_violations -- the deliberately-violating test IS the deliverable
# --------------------------------------------------------------------------- #


def test_money_pump_violations_is_zero_for_a_realistic_two_sided_zero_cost_leg() -> None:
    n_paths, months = 4, 120
    rng = Generator(PCG64(1))
    smb = rng.normal(0.0, 0.03, size=(n_paths, months))  # genuinely two-sided
    ensemble = _ensemble({"smb": smb}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert specs["money_pump_violations"].fn(ensemble) == 0.0


def test_money_pump_violations_flags_a_deliberately_never_negative_zero_cost_leg() -> None:
    """THE DELIVERABLE: a zero-cost leg (smb) that never loses money on any path is a
    costless, riskless-or-better combination -- exactly the free-lunch this audit
    exists to catch. Must produce a NON-ZERO count."""
    n_paths, months = 4, 120
    smb = np.full((n_paths, months), 0.001, dtype=np.float64)  # always strictly positive
    ensemble = _ensemble({"smb": smb}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    violations = specs["money_pump_violations"].fn(ensemble)
    assert violations == float(n_paths), violations


def test_money_pump_violations_counts_only_the_violating_paths() -> None:
    n_paths, months = 4, 120
    rng = Generator(PCG64(2))
    smb = rng.normal(0.0, 0.03, size=(n_paths, months))
    smb[0, :] = 0.001  # path 0 is the deliberate violator; the rest are two-sided
    ensemble = _ensemble({"smb": smb}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert specs["money_pump_violations"].fn(ensemble) == 1.0


def test_money_pump_violations_nan_when_no_zero_cost_leg_is_present() -> None:
    ensemble = _ensemble({"equity_mkt": _constant_slab(0.01, 2, 120)}, 2, 120)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["money_pump_violations"].fn(ensemble))


def test_money_pump_violations_is_enforce_severity_registration() -> None:
    """A structural constraint (the audit) needs to be enforce/max:0 in the sealed
    document to gate anything -- this test only checks the metric's own contract is
    the shape a max:0 threshold can judge (a non-negative count)."""
    n_paths, months = 2, 60
    smb = np.full((n_paths, months), 0.001, dtype=np.float64)
    ensemble = _ensemble({"smb": smb}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    value = specs["money_pump_violations"].fn(ensemble)
    assert value >= 0.0


# --------------------------------------------------------------------------- #
# 4. floor_violations -- deliberately-violating ensemble again the deliverable
# --------------------------------------------------------------------------- #


def test_floor_violations_is_zero_when_every_rate_and_spread_stays_above_floor() -> None:
    n_paths, months = 2, 120
    values = {f: _constant_slab(5.0, n_paths, months) for f in RATE_FLOOR_FACTORS}
    values.update({f: _constant_slab(2.0, n_paths, months) for f in SPREAD_FLOOR_FACTORS})
    ensemble = _ensemble(values, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert specs["floor_violations"].fn(ensemble) == 0.0


def test_floor_violations_flags_a_deliberately_sub_floor_rate() -> None:
    n_paths, months = 2, 120
    values = {f: _constant_slab(5.0, n_paths, months) for f in RATE_FLOOR_FACTORS}
    values["policy_rate"] = _constant_slab(RATE_FLOOR_PCT - 1.0, n_paths, months)  # deliberate
    ensemble = _ensemble(values, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    violations = specs["floor_violations"].fn(ensemble)
    assert violations == float(n_paths * months), violations


def test_floor_violations_flags_a_deliberately_sub_floor_spread() -> None:
    n_paths, months = 2, 120
    values = {f: _constant_slab(2.0, n_paths, months) for f in SPREAD_FLOOR_FACTORS}
    values["hy_spread"] = _constant_slab(SPREAD_FLOOR_PCT - 0.5, n_paths, months)  # deliberate
    ensemble = _ensemble(values, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    violations = specs["floor_violations"].fn(ensemble)
    assert violations == float(n_paths * months), violations


def test_floor_violations_nan_when_no_floor_bearing_factor_present() -> None:
    ensemble = _ensemble({"equity_mkt": _constant_slab(0.01, 2, 120)}, 2, 120)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["floor_violations"].fn(ensemble))


# --------------------------------------------------------------------------- #
# 5. policy_anchor_deviation
# --------------------------------------------------------------------------- #


def test_policy_anchor_deviation_is_zero_when_policy_rate_exactly_tracks_the_anchor() -> None:
    n_paths, months = 2, 50
    cpi = _constant_slab(100.0, n_paths, months)  # flat CPI -> cpi_yoy = 0 for every t>=12
    anchor = TAYLOR_R_STAR + TAYLOR_PI_TARGET + TAYLOR_PHI_PI * (0.0 - TAYLOR_PI_TARGET)
    policy_rate = _constant_slab(anchor, n_paths, months)
    ensemble = _ensemble({"policy_rate": policy_rate, "cpi": cpi}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    value = specs["policy_anchor_deviation"].fn(ensemble)
    assert value == pytest.approx(0.0, abs=1e-9)


def test_policy_anchor_deviation_matches_a_hand_computed_constant_gap() -> None:
    n_paths, months = 2, 50
    cpi = _constant_slab(100.0, n_paths, months)
    anchor = TAYLOR_R_STAR + TAYLOR_PI_TARGET + TAYLOR_PHI_PI * (0.0 - TAYLOR_PI_TARGET)
    policy_rate = _constant_slab(anchor + 1.0, n_paths, months)  # a stated, constant gap
    ensemble = _ensemble({"policy_rate": policy_rate, "cpi": cpi}, n_paths, months)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    value = specs["policy_anchor_deviation"].fn(ensemble)
    assert value == pytest.approx(1.0, abs=1e-9)


def test_policy_anchor_deviation_nan_when_cpi_absent() -> None:
    ensemble = _ensemble({"policy_rate": _constant_slab(3.0, 2, 36)}, 2, 36)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["policy_anchor_deviation"].fn(ensemble))


def test_policy_anchor_deviation_nan_when_too_short_for_any_yoy_value() -> None:
    ensemble = _ensemble(
        {"policy_rate": _constant_slab(3.0, 2, 6), "cpi": _constant_slab(100.0, 2, 6)}, 2, 6
    )
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    assert math.isnan(specs["policy_anchor_deviation"].fn(ensemble))


# --------------------------------------------------------------------------- #
# 5b. CRITICAL 1 -- policy_anchor_deviation must not reward a degenerate generator.
# THE DELIVERABLE: a test showing a zero-variance generator scores better than a
# realistic one under the raw metric, and a second test showing this is caught by the
# sealed two-sided band.
# --------------------------------------------------------------------------- #


def test_policy_anchor_deviation_near_zero_is_not_automatically_good() -> None:
    """A generator emitting a policy_rate that DETERMINISTICALLY equals the simplified
    anchor every month scores exactly 0.0 -- the numerically best possible value --
    under the raw metric alone, despite being LESS realistic than a generator with
    genuine idiosyncratic variation: real policy rates deviate from any Taylor-type
    anchor by roughly 1-2 percentage points RMS in practice. This is the gaming route
    Critical 1 names, demonstrated directly: the degenerate (zero-variance) generator
    scores STRICTLY BETTER than the more realistic (noisy) one."""
    n_paths, months = 2, 50
    cpi = _constant_slab(100.0, n_paths, months)
    anchor = TAYLOR_R_STAR + TAYLOR_PI_TARGET + TAYLOR_PHI_PI * (0.0 - TAYLOR_PI_TARGET)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}

    degenerate_ensemble = _ensemble(
        {"policy_rate": _constant_slab(anchor, n_paths, months), "cpi": cpi}, n_paths, months
    )
    degenerate_value = specs["policy_anchor_deviation"].fn(degenerate_ensemble)

    rng = Generator(PCG64(99))
    realistic_policy_rate = anchor + rng.normal(0.0, 1.5, size=(n_paths, months))
    realistic_ensemble = _ensemble(
        {"policy_rate": realistic_policy_rate, "cpi": cpi}, n_paths, months
    )
    realistic_value = specs["policy_anchor_deviation"].fn(realistic_ensemble)

    assert degenerate_value == pytest.approx(0.0, abs=1e-9)
    assert realistic_value > 1.0, realistic_value
    # THE GAMING: less realistic (deterministic) reads as strictly better than more
    # realistic (noisy).
    assert degenerate_value < realistic_value


def test_policy_anchor_deviation_degenerate_generator_fails_the_sealed_two_sided_band() -> None:
    """...and now it is caught: pre-registration.yaml's policy_anchor_deviation
    threshold is sealed TWO-SIDED (min bounded away from 0.0), following
    interval_coverage's precedent that both directions of a calibration-style
    statistic are failures. The degenerate exact-tracker fails the sealed band; a
    realistically noisy generator passes it."""
    from ah.eval import prereg as prereg_mod

    threshold = prereg_mod.load().panel_thresholds["policy_anchor_deviation"]
    assert threshold.min is not None and threshold.min > 0.0, threshold

    n_paths, months = 2, 50
    cpi = _constant_slab(100.0, n_paths, months)
    anchor = TAYLOR_R_STAR + TAYLOR_PI_TARGET + TAYLOR_PHI_PI * (0.0 - TAYLOR_PI_TARGET)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}

    degenerate_ensemble = _ensemble(
        {"policy_rate": _constant_slab(anchor, n_paths, months), "cpi": cpi}, n_paths, months
    )
    degenerate_value = specs["policy_anchor_deviation"].fn(degenerate_ensemble)
    assert not _passed(degenerate_value, threshold)

    rng = Generator(PCG64(98))
    realistic_policy_rate = anchor + rng.normal(0.0, 1.5, size=(n_paths, months))
    realistic_ensemble = _ensemble(
        {"policy_rate": realistic_policy_rate, "cpi": cpi}, n_paths, months
    )
    realistic_value = specs["policy_anchor_deviation"].fn(realistic_ensemble)
    assert _passed(realistic_value, threshold)


# --------------------------------------------------------------------------- #
# 6. implied_sharpe_{regime} -- structural gap, mirrors ah.eval.metrics.horizon
# --------------------------------------------------------------------------- #


def test_implied_sharpe_is_always_nan_and_marked_structurally_unavailable() -> None:
    ensemble = _ensemble({"equity_mkt": _constant_slab(0.01, 2, 120)}, 2, 120)
    specs = {s.name: s for s in build_economics_suite(_real_manifest(), _empty_reference())}
    for regime in REGIME_LABELS:
        spec = specs[f"implied_sharpe_{regime}"]
        assert spec.status == STRUCTURALLY_UNAVAILABLE
        assert math.isnan(spec.fn(ensemble))
        assert dict(spec.metadata)["gap"] == "RFR-27"


# --------------------------------------------------------------------------- #
# 7. registration bookkeeping
# --------------------------------------------------------------------------- #


def test_every_economics_metric_name_can_carry_a_sealed_threshold() -> None:
    specs = build_economics_suite(_real_manifest(), _empty_reference())
    expected = {f"implied_sharpe_{r}" for r in REGIME_LABELS} | {
        "term_premium",
        "equity_risk_premium",
        "money_pump_violations",
        "floor_violations",
        "policy_anchor_deviation",
    }
    assert {s.name for s in specs} == expected
    for spec in specs:
        assert spec.tier == "economic"
        assert spec.suite == "economics"
        assert spec.name in PANEL_STATS


def test_economics_is_registered_in_prereg_metric_suite_names() -> None:
    from ah.eval import prereg as prereg_mod

    assert "economics" in prereg_mod._METRIC_SUITE_NAMES


def test_economics_suite_registered_in_reference_dependent_suite_builders() -> None:
    from ah.eval import battery as battery_mod

    assert battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS["economics"] == (
        "ah.eval.metrics.economics",
        "build_economics_suite",
    )


# --------------------------------------------------------------------------- #
# 8. economics.py never imports ah.eval.g2 (Minor, WP2.2 Task 5 fix pass -- mirrors
# tests/test_calibration.py's / tests/test_memorization.py's identical guard; this
# suite has no leakage-relevant DataAccess/FinalEvaluationToken concern of its own
# (see the module docstring's "Registration is deferred"), but the g2-import guard is
# a repo-wide convention every reference-dependent suite in eval/metrics/ carries).
# --------------------------------------------------------------------------- #

_ECONOMICS_PATH = ROOT / "src" / "ah" / "eval" / "metrics" / "economics.py"


def test_economics_module_never_imports_g2_or_names_the_token() -> None:
    text = _ECONOMICS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(_ECONOMICS_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ah.eval.g2" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "g2" not in module.split("."), module
            for alias in node.names:
                assert alias.name != "FinalEvaluationToken"
