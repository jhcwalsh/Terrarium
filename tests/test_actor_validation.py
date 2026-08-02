"""WP4.9 — the study machinery: identical worlds, honest measures.

Offline throughout (deciders injected). The dispersion rule is the
teeth: effect sizes refuse to exist without their across-world spread
and world count attached.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from ah.artifacts import committee as com
from ah.artifacts import validation as val

RNG = np.random.Generator(np.random.PCG64(5))
TAPES = {seed: RNG.normal(0.004, 0.03, size=(36, 3)) for seed in (101, 202, 303)}

GOOD = json.dumps(
    {
        "actions": [
            {"verb": "rebalance_public", "payload": {"target_weights": {"public_equity": 0.6}}}
        ],
        "rationale": "Restore the mix; risk is manageable and we expect drift to persist.",
    }
)
HOLD = json.dumps({"actions": [], "rationale": "We hold; nothing in the tape demands action."})


def _all_records(decider_map):
    records = []
    for seed, tape in TAPES.items():
        records.extend(val.run_ablation_arms(tape, world_seed=seed))
        records.extend(
            val.run_model_arm(
                tape,
                world_seed=seed,
                personas=[com.Persona(pid, desc) for pid, desc in decider_map],
                decider=lambda p: GOOD,
                model_id="fake",
            )
        )
    return records


class TestAblationArms:
    def test_arms_are_deterministic_on_identical_worlds(self):
        a = val.run_ablation_arms(TAPES[101], world_seed=101)
        b = val.run_ablation_arms(TAPES[101], world_seed=101)
        assert a == b
        assert {r.arm for r in a} == set(val.DECIDER_ARMS)

    def test_hold_course_never_acts_random_always_acts(self):
        records = val.run_ablation_arms(TAPES[101], world_seed=101)
        rates = val.action_rates(records)
        assert rates["hold_course"] == 0.0
        assert rates["random_within_bounds"] == 1.0


class TestPathologies:
    def test_persona_agreement_and_disagreement_measured(self):
        same = _all_records([("a", "desc a"), ("b", "desc b")])
        assert val.persona_sensitivity(same) == 0.0  # identical decider -> no disagreement
        records = []
        for seed, tape in TAPES.items():
            records.extend(
                val.run_model_arm(
                    tape,
                    world_seed=seed,
                    personas=[com.Persona("act", "acts"), com.Persona("hold", "holds")],
                    decider=lambda p: GOOD if "acts" in p else HOLD,
                    model_id="fake",
                )
            )
        assert val.persona_sensitivity(records) == 1.0  # deciders differ everywhere

    def test_fallback_rate_counts_rejections(self):
        records = []
        for seed, tape in TAPES.items():
            records.extend(
                val.run_model_arm(
                    tape,
                    world_seed=seed,
                    personas=[com.Persona("garbled", "returns prose")],
                    decider=lambda p: "buy the dip!!",
                    model_id="fake",
                )
            )
        assert val.fallback_rate(records) == 1.0

    def test_effect_sizes_refuse_to_travel_alone(self):
        records = []
        for seed, tape in TAPES.items():
            records.extend(val.run_ablation_arms(tape, world_seed=seed))
        result = val.effect_size_with_dispersion(records, "random_within_bounds", "hold_course")
        assert result["mean_diff"] == pytest.approx(1.0)
        assert result["n_worlds"] == 3.0
        assert "sd_across_worlds" in result  # the mean never ships without it
        with pytest.raises(val.ValidationError, match="no worlds"):
            val.effect_size_with_dispersion(records, "model:x", "hold_course")
