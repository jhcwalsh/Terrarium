"""WP5.5 acceptance: the chain-link window attribution.

DN-5 SS5's decomposition, pinned: the telescoping identity holds exactly,
hold-course decomposes to all zeros, and a single deviating window carries
exactly the sequence's whole alpha.
"""

from __future__ import annotations

import pytest

from ah.core.engine import run_path
from ah.core.institution import decision_months, simulate_institution
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.density import window_contributions

PRESETS = __import__("pathlib").Path(__file__).resolve().parents[1] / "src" / "ah" / "presets"


@pytest.fixture(scope="module")
def paths():
    import json

    world = json.loads((PRESETS / "stagflation.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(world))
    return run_path(nw, 20260803)


class TestChainLink:
    def test_telescopes_exactly_to_the_terminal_difference(self, paths):
        months = decision_months(paths.months)
        decisions = {m: a for m, a in zip(months, (["derisk", "hold", "leanin"] * 4)[: len(months)], strict=True)}
        attr = window_contributions(paths, decisions)
        twin = simulate_institution(paths, None)
        full = simulate_institution(paths, decisions)
        assert attr.twin_final == pytest.approx(float(twin.final_value), abs=1e-12)
        assert attr.final_value == pytest.approx(float(full.final_value), abs=1e-12)
        assert sum(attr.contributions) == pytest.approx(attr.total_alpha, abs=1e-9)

    def test_hold_course_decomposes_to_zeros(self, paths):
        attr = window_contributions(paths, {})
        assert all(c == pytest.approx(0.0, abs=1e-12) for c in attr.contributions)
        assert attr.total_alpha == pytest.approx(0.0, abs=1e-12)
        assert all(a == "hold" for a in attr.actions)

    def test_single_deviation_carries_the_whole_alpha(self, paths):
        months = decision_months(paths.months)
        lone = {months[3]: "derisk"}
        attr = window_contributions(paths, lone)
        full = simulate_institution(paths, lone)
        twin = simulate_institution(paths, None)
        expected = float(full.final_value - twin.final_value)
        assert attr.contributions[3] == pytest.approx(expected, abs=1e-9)
        others = [c for j, c in enumerate(attr.contributions) if j != 3]
        assert all(c == pytest.approx(0.0, abs=1e-12) for c in others)

    def test_sequential_convention_prefix_context(self, paths):
        """c_j is conditioned on the PRIOR decisions: the same window's action
        can carry a different contribution under a different prefix."""
        months = decision_months(paths.months)
        a = window_contributions(paths, {months[0]: "hold", months[4]: "derisk"})
        b = window_contributions(paths, {months[0]: "secondary", months[4]: "derisk"})
        assert a.contributions[4] != b.contributions[4]

    def test_reported_basis_is_a_different_decomposition(self, paths):
        months = decision_months(paths.months)
        decisions = {months[2]: "derisk"}
        true_attr = window_contributions(paths, decisions, use_reported=False)
        rep_attr = window_contributions(paths, decisions, use_reported=True)
        assert true_attr.twin_final != rep_attr.twin_final
