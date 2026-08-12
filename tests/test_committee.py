"""WP4.8 — the committee: bounded, briefed behind the wall, filed, beatable.

Offline throughout: deciders are injected callables. The bounded-menu
tests are the teeth — a model proposing an off-menu or declared-but-
unimplemented action falls back to the heuristic WITH the failure on the
record, never silently coerced.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from ah.artifacts import committee as com
from ah.artifacts.live import RevealedTape

RNG = np.random.Generator(np.random.PCG64(11))
TAPE = RNG.normal(0.004, 0.03, size=(120, 3))
PERSONA = com.Persona("steady", "disciplined, contrarian only with evidence")
WEIGHTS = {"public_equity": 0.52, "pm_buyout": 0.38, "cash": 0.10}

GOOD_RESPONSE = json.dumps(
    {
        "actions": [
            {"verb": "rebalance_public", "payload": {"target_weights": {"public_equity": 0.60}}}
        ],
        "rationale": "Weights drifted below target during the drawdown; restoring the "
        "policy mix is the disciplined move and liquidity comfortably covers it.",
    }
)


def _briefing(months: int = 60) -> str:
    return com.build_briefing(
        revealed=RevealedTape.cut(TAPE, months),
        weights_reported=WEIGHTS,
        coverage_liquid=0.43,
        wire_items=["Spreads widen", "CPI in line", "Stonebeck gates redemptions"],
    )


def _decide(decider, **overrides):
    kwargs: dict = dict(
        persona=PERSONA,
        briefing=_briefing(),
        decider=decider,
        model_id="fake-committee",
        window_id=3,
        submitted_at="2026-08-02T12:00:00+00:00",
        weights_reported=WEIGHTS,
    )
    kwargs.update(overrides)
    return com.committee_decide(**kwargs)


class TestBriefing:
    def test_briefing_is_deterministic_over_the_revealed_slice(self):
        assert _briefing() == _briefing()
        assert "months revealed: 60" in _briefing()
        assert "coverage (unfunded / liquid): 0.43" in _briefing()

    def test_briefing_reads_equity_by_named_column(self):
        """su-gen-03: the public-return column is a PARAMETER, not position 0.

        The Task 0 survey found the briefing silently treating tape column 0
        as an equity return — on a factor-ordered tape that column is cape_v
        and the briefing renders nonsense without failing. A caller with a
        non-first equity column must be able to say so, and the two reads
        must agree."""
        import numpy as np

        # equity in column 2; junk (a level-like series) in column 0
        months = 24
        rng = np.random.default_rng(7)
        tape = np.column_stack(
            [
                100.0 + np.arange(months),  # a level, poison if read as returns
                rng.normal(0, 0.01, months),
                rng.normal(0.005, 0.04, months),  # the actual equity column
            ]
        )
        moved = com.build_briefing(
            revealed=RevealedTape.cut(tape, months),
            weights_reported=WEIGHTS,
            coverage_liquid=0.4,
            wire_items=[],
            equity_column=2,
        )
        reference = com.build_briefing(
            revealed=RevealedTape.cut(tape[:, [2, 1, 0]], months),
            weights_reported=WEIGHTS,
            coverage_liquid=0.4,
            wire_items=[],
        )
        assert moved == reference

    def test_briefing_inherits_the_wall(self):
        """More reveal, different briefing — and the input object simply has
        no months beyond the pointer to leak."""
        assert _briefing(60) != _briefing(61)
        with pytest.raises(com.CommitteeError, match="at least one"):
            com.build_briefing(
                revealed=RevealedTape.cut(TAPE, 0),
                weights_reported=WEIGHTS,
                coverage_liquid=0.4,
                wire_items=[],
            )

    def test_prompt_carries_persona_as_configuration(self):
        prompt = com.render_committee_prompt(PERSONA, _briefing())
        assert "disciplined, contrarian only with evidence" in prompt
        assert com.COMMITTEE_PROMPT_VERSION == "committee-prompt@1.1"


class TestBoundedDecisions:
    def test_valid_model_decision_flows_through_typed(self):
        decision = _decide(lambda p: GOOD_RESPONSE)
        assert decision.decided_by == "model"
        assert decision.window.actions[0].verb == "rebalance_public"
        assert decision.prompt_version == "committee-prompt@1.1"
        assert decision.persona_id == "steady"

    def test_off_menu_action_falls_back_with_the_failure_filed(self):
        off_menu = json.dumps(
            {"actions": [{"verb": "sell_secondary", "payload": {}}], "rationale": "sell it all"}
        )
        decision = _decide(lambda p: off_menu)
        assert decision.decided_by == "heuristic_fallback"
        assert "model output rejected" in decision.rationale
        assert "not yet implemented" in decision.rationale

    def test_garbage_and_missing_rationale_fall_back(self):
        assert _decide(lambda p: "I think we should buy!").decided_by == "heuristic_fallback"
        no_rationale = json.dumps({"actions": [], "rationale": ""})
        assert _decide(lambda p: no_rationale).decided_by == "heuristic_fallback"

    def test_empty_actions_with_rationale_is_a_valid_model_decision(self):
        hold = json.dumps({"actions": [], "rationale": "Nothing has changed; we hold."})
        decision = _decide(lambda p: hold)
        assert decision.decided_by == "model" and decision.window.actions == ()

    def test_rationale_files_to_the_wire(self):
        payload = _decide(lambda p: GOOD_RESPONSE).rationale_wire_payload(
            world_id="w1", dateline="2028-03-15"
        )
        assert payload["headline"].startswith("Committee minutes, window 3")
        assert "disciplined move" in payload["body"]


class TestAblations:
    def test_heuristic_rebalances_outside_band_holds_inside(self):
        actions, _ = com.heuristic_decision(weights_reported={"public_equity": 0.52})
        assert actions[0]["payload"]["target_weights"]["public_equity"] == 0.60
        actions, rationale = com.heuristic_decision(weights_reported={"public_equity": 0.58})
        assert actions == [] and "within band" in rationale

    def test_random_within_bounds_is_seeded_and_bounded(self):
        a, _ = com.random_within_bounds(base_seed=42, window_id=1)
        b, _ = com.random_within_bounds(base_seed=42, window_id=1)
        assert a == b
        target = a[0]["payload"]["target_weights"]["public_equity"]
        assert 0.40 <= target <= 0.75

    def test_hold_course_is_the_empty_decision_on_the_record(self):
        actions, rationale = com.hold_course()
        assert actions == [] and "by construction" in rationale
