"""WP3.11 — the episode scorer: sealed formulas, executable.

One sealed sentence per test: window boundaries bind exactly, NaN is a fail
everywhere (never a pass, never an exclusion), the gate rule's two clauses
compose as sealed, and a missing criterion refuses rather than defaults.
"""

from __future__ import annotations

import pytest

from ah.eval import episode2022 as ep


def _all_passing() -> list[ep.CriterionResult]:
    return [
        ep.score_public_equity_drawdown(-0.2484),
        ep.score_mark_lag(2.0, 1.0),
        ep.score_distribution_shortfall(0.50, 1.0),
        ep.score_secondary_pricing(0.81),
        ep.score_private_weight_breach(1.0, 0.03),
        ep.score_coverage_warning(True, True),
    ]


class TestSealedFormulas:
    def test_drawdown_window_binds_exactly(self):
        assert ep.score_public_equity_drawdown(-0.2484).passed
        assert ep.score_public_equity_drawdown(-0.2984).passed  # edge of +/- 0.05
        assert not ep.score_public_equity_drawdown(-0.31).passed

    def test_mark_lag_needs_both_halves(self):
        assert ep.score_mark_lag(1.0, 0.0).passed
        assert not ep.score_mark_lag(0.5, 1.0).passed  # PM below 1
        assert not ep.score_mark_lag(2.0, -3.1).passed  # the replay's actual HF miss
        assert not ep.score_mark_lag(7.0, 1.0).passed  # PM above 6

    def test_drought_depth_window(self):
        assert ep.score_distribution_shortfall(0.45, 1.0).passed
        assert ep.score_distribution_shortfall(0.55, 1.0).passed
        assert not ep.score_distribution_shortfall(0.60, 1.0).passed  # too shallow
        assert not ep.score_distribution_shortfall(0.40, 1.0).passed  # too deep

    def test_nan_is_a_fail_never_a_pass(self):
        assert not ep.score_public_equity_drawdown(float("nan")).passed
        assert not ep.score_mark_lag(float("nan"), 1.0).passed
        assert not ep.score_distribution_shortfall(0.5, 0.0).passed  # degenerate normal
        assert not ep.score_private_weight_breach(float("nan"), 0.05).passed

    def test_secondary_and_breach_windows(self):
        assert ep.score_secondary_pricing(0.76).passed
        assert not ep.score_secondary_pricing(0.75).passed
        assert ep.score_private_weight_breach(-3.0, 0.02).passed  # sealed: within 3m
        assert not ep.score_private_weight_breach(4.0, 0.05).passed
        assert not ep.score_private_weight_breach(1.0, 0.01).passed  # rounding artifact


class TestGateRule:
    def test_all_pass_passes_with_no_named_failures(self):
        verdict = ep.apply_gate_rule(_all_passing())
        assert verdict.passed and verdict.named_failures == ()
        assert verdict.score() == 0

    def test_permitted_failures_pass_the_gate_but_are_named(self):
        results = _all_passing()
        results[4] = ep.score_private_weight_breach(9.0, 0.03)  # the replay's case
        verdict = ep.apply_gate_rule(results)
        assert verdict.passed  # may-fail-named does not sink the gate
        assert verdict.named_failures == ("private_weight_breach",)
        assert verdict.score() == 1

    def test_a_must_pass_failure_sinks_the_gate(self):
        results = _all_passing()
        results[1] = ep.score_mark_lag(2.0, -3.1)  # the replay's actual failure
        verdict = ep.apply_gate_rule(results)
        assert not verdict.passed
        assert verdict.score() == 1

    def test_missing_criterion_refuses(self):
        with pytest.raises(ep.EpisodeScoreError, match="missing"):
            ep.apply_gate_rule(_all_passing()[:-1])
