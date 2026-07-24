"""WP0.5 acceptance: institution simulator + decisions.

Golden hold-course value, plus property tests: weights sum to 1 and no sleeve ever
goes negative, across seeds and action mixes; decision mechanics (derisk/leanin/
secondary) behave as specified; decision_alpha is active - twin.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from ah.core.engine import run_path
from ah.core.institution import (
    DEFENSIVE,
    GROWTH,
    START_MIX,
    decision_alpha,
    decision_months,
    hold_course_twin,
    simulate_institution,
)
from ah.core.numericworld import NumericWorld, project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "schemas" / "example-long-stagflation.worldspec.json"
_EXAMPLE: dict[str, Any] = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

GOLDEN_SEED = 42
GOLDEN_HOLD_FINAL = 65.226660  # growth of 100, stagflation hold-course twin


def make_world(quarters: int | None = None) -> NumericWorld:
    doc = copy.deepcopy(_EXAMPLE)
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    if quarters is not None:
        doc["horizon"]["quarters"] = quarters
    return project_numeric(WorldSpec.model_validate(doc))


# --------------------------------------------------------------------------- #
# baseline / golden
# --------------------------------------------------------------------------- #


def test_start_mix_sums_to_one() -> None:
    assert math.isclose(sum(START_MIX.values()), 1.0)


def test_decision_months_are_annual_years_1_to_9() -> None:
    assert decision_months(120) == [11, 23, 35, 47, 59, 71, 83, 95, 107]
    assert decision_months(36) == [11, 23, 35]  # short horizon -> fewer decisions


def test_golden_hold_course_final_value() -> None:
    r = hold_course_twin(make_world(), GOLDEN_SEED)
    assert math.isclose(r.final_value, GOLDEN_HOLD_FINAL, rel_tol=0, abs_tol=1e-4)
    assert all(a == "hold" for _, a in r.decisions)
    assert len(r.decisions) == 9


# --------------------------------------------------------------------------- #
# invariants
# --------------------------------------------------------------------------- #

_ACTIONS = st.sampled_from(["hold", "derisk", "leanin", "secondary"])


@settings(max_examples=60, deadline=None)
@given(
    seed=st.integers(0, 2**31 - 1),
    quarters=st.integers(8, 40),
    data=st.data(),
)
def test_weights_sum_to_one_and_never_negative(
    seed: int, quarters: int, data: st.DataObject
) -> None:
    world = make_world(quarters)
    dmonths = decision_months(quarters * 3)
    decisions = {m: data.draw(_ACTIONS) for m in dmonths}
    r = simulate_institution(run_path(world, seed), decisions)

    assert r.weights.shape == (quarters * 3, 8)
    assert np.all(r.weights >= -1e-12)  # no negative sleeves
    assert np.allclose(r.weights.sum(axis=1), 1.0, atol=1e-9)
    assert np.all(r.total >= 0.0)
    assert np.all(np.isfinite(r.total))


def test_use_reported_changes_result() -> None:
    world = make_world()
    true_run = hold_course_twin(world, GOLDEN_SEED, use_reported=False)
    rep_run = hold_course_twin(world, GOLDEN_SEED, use_reported=True)
    assert not math.isclose(true_run.final_value, rep_run.final_value)


# --------------------------------------------------------------------------- #
# decision mechanics
# --------------------------------------------------------------------------- #


def _weights_at(r: Any, month: int) -> dict[str, float]:
    from ah.core.institution import SLEEVES

    return {s: r.weights[month, i] for i, s in enumerate(SLEEVES)}


def test_derisk_moves_weight_growth_to_defensive() -> None:
    world = make_world()
    dm = decision_months(120)
    hold = hold_course_twin(world, GOLDEN_SEED)
    derisk = simulate_institution(run_path(world, GOLDEN_SEED), {dm[0]: "derisk"})
    # right after the first decision month, defensive share should be higher
    m = dm[0]
    hold_def = sum(_weights_at(hold, m)[k] for k in DEFENSIVE)
    derisk_def = sum(_weights_at(derisk, m)[k] for k in DEFENSIVE)
    assert derisk_def > hold_def
    hold_grw = sum(_weights_at(hold, m)[k] for k in GROWTH)
    derisk_grw = sum(_weights_at(derisk, m)[k] for k in GROWTH)
    assert derisk_grw < hold_grw


def test_leanin_moves_weight_defensive_to_growth() -> None:
    world = make_world()
    dm = decision_months(120)
    hold = hold_course_twin(world, GOLDEN_SEED)
    leanin = simulate_institution(run_path(world, GOLDEN_SEED), {dm[0]: "leanin"})
    m = dm[0]
    assert sum(_weights_at(leanin, m)[k] for k in GROWTH) > sum(
        _weights_at(hold, m)[k] for k in GROWTH
    )


def test_secondary_reduces_pe_target_weight() -> None:
    world = make_world()
    dm = decision_months(120)
    m = dm[0]
    sec = simulate_institution(run_path(world, GOLDEN_SEED), {m: "secondary"})
    # PE weight right after a secondary should be below the start-mix PE weight
    assert _weights_at(sec, m)["pe"] < START_MIX["pe"]


def test_decision_alpha_is_active_minus_twin() -> None:
    world = make_world()
    dm = decision_months(120)
    decisions = {dm[0]: "derisk", dm[3]: "secondary", dm[5]: "leanin"}
    paths = run_path(world, GOLDEN_SEED)
    active = simulate_institution(paths, decisions)
    twin = simulate_institution(paths, None)
    assert math.isclose(
        decision_alpha(world, GOLDEN_SEED, decisions),
        active.final_value - twin.final_value,
        rel_tol=0,
        abs_tol=1e-9,
    )


def test_unknown_action_treated_as_hold() -> None:
    world = make_world()
    dm = decision_months(120)
    weird = simulate_institution(run_path(world, GOLDEN_SEED), {dm[0]: "nonsense"})
    hold = hold_course_twin(world, GOLDEN_SEED)
    assert math.isclose(weird.final_value, hold.final_value)
