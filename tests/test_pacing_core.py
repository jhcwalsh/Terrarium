"""sp-01: the pacing core — DN-5 v0.2's twins and the player's commitment lever.

The ratified spec (`Instructions/DN-5-decision-alpha-and-twin.md`):

* The POLICY twin flexes annual commitments toward the policy private
  weight — ``target = base_pace * g(w_policy - w_reported)`` with ``g``
  clipped to a band; never zero, never doubled.
* The DRIFT twin keeps the fixed nominal schedule — in the play layer (which
  never rebalances on its own) the pacing rule IS the whole distinction.
* The player's per-sleeve annual commitment is a decision type beside the
  four public actions; committing the plan is "hold to plan", recorded but
  numerically identical to silence.

Declared parameters (DN-5 leaves the form open; recorded here and in
play.py): band (0.5, 1.5); linear g with sensitivity 4.0 — ten points
overweight throttles commitments by 40%, ten under raises them 40%.

DN-5 §7 rows covered here: drift reduction, pacing floor, telescoping,
null player, determinism. Bands-and-costs rows (symmetry, secondary
ordering) concern DN-5 machinery the play layer never shipped — out of
sp-01's scope, recorded in the plan.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    _ANNUAL_COMMITMENT_RATE,
    PACING_BAND,
    PACING_SENSITIVITY,
    PRIVATE_ASSETS,
    START_TARGETS,
    simulate_play,
    window_contributions_play,
)

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(name: str = "stagflation", seed: int = 771204):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return run_path(project_numeric(WorldSpec.model_validate(doc)), seed)


def _plan_points() -> float:
    return sum(START_TARGETS[a] * _ANNUAL_COMMITMENT_RATE for a in PRIVATE_ASSETS)


class TestPolicyTwinPacing:
    def test_policy_twin_throttles_commitments_in_a_crash(self):
        """Overweight privates on reported marks => the flexing twin commits
        LESS than the fixed schedule; the whole vintage-timing lesson."""
        p = _paths("deflation_bust", 1848)
        policy = simulate_play(p, None)  # the ratified default IS the flex
        fixed = simulate_play(p, None, pacing_rule="fixed")
        committed_policy = sum(q.new_commitments for q in policy.quarters)
        committed_fixed = sum(q.new_commitments for q in fixed.quarters)
        assert committed_policy < committed_fixed

    def test_pacing_floor_holds_in_the_deepest_drawdown(self):
        """DN-5 §7 'Pacing floor': the multiplier never leaves the band —
        a twin that cuts to zero reproduces 2009's most-criticised
        behaviour and makes the benchmark easy for the wrong reason."""
        p = _paths("deflation_bust", 1848)
        result = simulate_play(p, None)
        lo, hi = PACING_BAND
        plan = _plan_points()
        for q in result.quarters:
            if q.new_commitments > 0.0:
                assert q.new_commitments >= lo * plan - 1e-9
                assert q.new_commitments <= hi * plan + 1e-9

    def test_drift_reduction(self):
        """DN-5 §7 'Drift reduction': band clamped to (1, 1) makes the
        policy twin reproduce the drift twin bit-for-bit."""
        p = _paths()
        clamped = simulate_play(p, None, pacing_band=(1.0, 1.0))
        drift = simulate_play(p, None, pacing_rule="fixed")
        assert clamped.final_value == drift.final_value
        for a, b in zip(clamped.quarters, drift.quarters, strict=True):
            assert a.new_commitments == b.new_commitments

    def test_declared_parameters_are_the_recorded_ones(self):
        assert PACING_BAND == (0.5, 1.5)
        assert PACING_SENSITIVITY == 4.0


class TestCommitmentLever:
    def _commit(self, points: dict[str, float]) -> dict:
        return {"action": "commit", "commitments": points}

    def test_player_can_cut_the_next_years_commitments_to_zero(self):
        """The lever: a commit decision at a window overrides the NEXT
        commitment event's per-sleeve points."""
        p = _paths()
        cut = simulate_play(p, {11: self._commit({a: 0.0 for a in PRIVATE_ASSETS})})
        q4 = next(q for q in cut.quarters if q.quarter == 4)
        assert q4.new_commitments == 0.0
        default = simulate_play(p, None)
        assert cut.final_value != default.final_value

    def test_committing_the_plan_is_numerically_holding_to_plan(self):
        """'Hold to plan' must be a recordable choice that changes nothing:
        committing exactly the plan's own points reproduces the no-decision
        run to the penny. Pinned under the fixed rule, where the plan is
        exactly the declared pace (no multiplier float-dust)."""
        p = _paths()
        default = simulate_play(p, None, pacing_rule="fixed")
        plan_pts = {a: START_TARGETS[a] * _ANNUAL_COMMITMENT_RATE for a in PRIVATE_ASSETS}
        held = simulate_play(p, {11: self._commit(plan_pts)}, pacing_rule="fixed")
        assert held.final_value == default.final_value

    def test_commitment_bounds_are_enforced(self):
        """Declared constraint (recorded): 0 <= points <= 2x the sleeve's
        plan pace. Outside it the decision is refused loudly."""
        p = _paths()
        with pytest.raises(ValueError, match="commit"):
            simulate_play(p, {11: self._commit({"pe": -1.0})})
        with pytest.raises(ValueError, match="commit"):
            simulate_play(p, {11: self._commit({"pe": 99.0})})

    def test_telescoping_with_a_commit_decision(self):
        """DN-5 §7 'Telescoping': per-window contributions still sum to the
        final-value gap when the decision map contains the new type."""
        p = _paths()
        decisions = {11: self._commit({a: 0.0 for a in PRIVATE_ASSETS}), 23: "derisk"}
        active = simulate_play(p, decisions)
        twin = simulate_play(p, None)
        attribution = window_contributions_play(p, decisions)
        assert np.isclose(
            sum(attribution.contributions),
            active.final_value - twin.final_value,
            atol=1e-9,
        )

    def test_null_player_scores_exactly_zero(self):
        """DN-5 §7 'Null player': no action in any window => alpha 0.0 and
        every contribution exactly 0.0 — against the FLEXING twin."""
        p = _paths()
        attribution = window_contributions_play(p, {})
        assert all(c == 0.0 for c in attribution.contributions)

    def test_a_public_action_and_commitments_ride_together(self):
        """sp-02: the kickoff says the four public actions PLUS the lever —
        one window's decision can carry both, and both apply."""
        p = _paths()
        combined = simulate_play(
            p,
            {11: {"action": "derisk", "commitments": {a: 0.0 for a in PRIVATE_ASSETS}}},
        )
        q4 = next(q for q in combined.quarters if q.quarter == 4)
        assert q4.new_commitments == 0.0  # the lever applied
        commit_only = simulate_play(
            p, {11: {"action": "commit", "commitments": {a: 0.0 for a in PRIVATE_ASSETS}}}
        )
        assert combined.final_value != commit_only.final_value  # the derisk applied too

    def test_unknown_action_name_in_a_structured_decision_is_refused(self):
        p = _paths()
        with pytest.raises(ValueError, match="unknown"):
            simulate_play(p, {11: {"action": "yolo", "commitments": {"pe": 1.0}}})

    def test_determinism(self):
        p = _paths()
        d = {11: self._commit({"pe": 1.0, "pc": 0.5, "re": 0.5}), 35: "leanin"}
        a = simulate_play(p, d)
        b = simulate_play(p, d)
        assert a.final_value == b.final_value
