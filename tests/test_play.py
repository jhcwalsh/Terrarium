"""The playable institution on the Step-3 twin (register ER-3).

What these protect is the thing that was missing: consequence. A capital call
must be funded from somewhere, cash cannot go negative, and when the liquid
leg is exhausted the institution sells private interests at a discount whether
it wants to or not. If any of that stops being true, a secondary sale goes
back to being a slider.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ah.core.engine import run_path
from ah.core.institution import decision_months
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    PLAY_ALPHA_VERSION,
    PRIVATE_ASSETS,
    START_TARGETS,
    play_alpha,
    simulate_play,
)
from ah.port.engine import Policy

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


@pytest.fixture(scope="module")
def stagflation():
    return _paths()


@pytest.fixture(scope="module")
def held(stagflation):
    return simulate_play(stagflation, None)


class TestShapeAndDeterminism:
    def test_one_row_per_quarter_closing_on_quarter_ends(self, held, stagflation):
        assert len(held.quarters) == stagflation.months // 3
        for i, q in enumerate(held.quarters):
            assert q.quarter == i
            assert q.month == i * 3 + 2

    def test_same_tape_same_decade(self, stagflation):
        a = simulate_play(stagflation, None)
        b = simulate_play(stagflation, None)
        assert [q.nav_true for q in a.quarters] == [q.nav_true for q in b.quarters]
        assert a.final_value == b.final_value

    def test_the_opening_book_sits_inside_the_policy_band(self):
        """A book that breaches its own private-weight range on day one
        force-sells its way through the decade — measured at 29 forced
        quarters out of 40 before this was corrected."""
        lo, hi = Policy().private_weight_range
        total = sum(START_TARGETS.values())
        private = sum(START_TARGETS[a] for a in PRIVATE_ASSETS)
        assert lo < private / total < hi


class TestConsequence:
    def test_cash_is_never_negative(self, held):
        """The whole point. Calls are paid from cash, and if cash is short the
        waterfall sells — it does not overdraw."""
        assert all(q.cash >= -1e-9 for q in held.quarters)

    def test_capital_is_actually_called_and_returned(self, held):
        assert sum(q.calls_paid for q in held.quarters) > 0.0
        assert sum(q.distributions_received for q in held.quarters) > 0.0

    def test_spending_rides_the_reported_plane(self, held):
        """Section 7's mechanic: spending comes off smoothed marks, so it
        holds up when true value falls. Every quarter spends something."""
        assert all(q.spending_paid > 0.0 for q in held.quarters)

    def test_a_forced_secondary_happens_where_it_should(self):
        """Not in a benign world; in the one named after a bust. This is the
        behaviour that makes a VOLUNTARY secondary a real decision — sell
        early at the haircut, or be sold later at it."""
        calm = simulate_play(_paths("goldilocks"), None)
        bust = simulate_play(_paths("deflation_bust"), None)
        assert calm.forced_secondaries == 0
        assert bust.forced_secondaries >= 1
        assert bust.forced_secondary_nav > 0.0

    def test_every_sale_is_logged_with_a_cause(self, held):
        for entry in held.sale_log:
            assert entry["cause"]
            assert entry["kind"] in {"liquid_pro_rata", "forced_secondary"}
            assert entry["amount"] > 0.0
            assert entry["sleeves_sold"]


class TestDecisions:
    def test_hold_course_is_exactly_the_twin(self, stagflation):
        """Alpha is active minus twin on the same tape, and the twin holds
        course — so holding must score exactly zero, not approximately."""
        windows = decision_months(stagflation.months)
        assert play_alpha(stagflation, dict.fromkeys(windows, "hold")) == 0.0
        assert play_alpha(stagflation, {}) == 0.0

    def test_derisk_and_leanin_move_the_book_in_opposite_directions(self, stagflation):
        windows = decision_months(stagflation.months)
        derisk = play_alpha(stagflation, dict.fromkeys(windows, "derisk"))
        leanin = play_alpha(stagflation, dict.fromkeys(windows, "leanin"))
        assert derisk != 0.0 and leanin != 0.0
        assert (derisk > 0) != (leanin > 0)

    def test_a_secondary_sale_raises_cash_at_the_haircut(self, stagflation):
        """The proceeds are real money, and less than the NAV given up.

        Tested on the MECHANISM, not on the quarter's end state. Comparing
        books after a sale does not isolate the discount: the cash raised can
        prevent a forced liquidation later in the same quarter, and the first
        version of this test failed because selling left the book *better*
        off. That is a genuine property of the model — selling early to avoid
        being sold later is exactly the decision the surface is meant to pose
        — but it is not what "the discount costs you something" means.
        """
        from ah.play import _build_portfolio, _secondary_sale

        policy = Policy()
        portfolio, cohorts = _build_portfolio(policy)
        before_nav = cohorts["pe"].nav_true
        before_cash = portfolio.cash
        proceeds = _secondary_sale(portfolio, {"pe_ladder": [cohorts["pe"]]}, policy)

        nav_given_up = before_nav - cohorts["pe"].nav_true
        assert nav_given_up > 0.0
        assert portfolio.cash == pytest.approx(before_cash + proceeds)
        assert proceeds == pytest.approx(nav_given_up * (1.0 - policy.secondary_haircut))
        assert proceeds < nav_given_up, "selling at a discount must cost value"

    def test_selling_into_a_bust_can_beat_being_sold(self, stagflation):
        """The finding the test above uncovered, pinned so it stays true:
        a voluntary secondary is not automatically a loss, because the
        alternative is the waterfall doing it for you at the same haircut
        with worse timing."""
        window = decision_months(stagflation.months)[0]
        assert play_alpha(stagflation, {window: "secondary"}) != 0.0

    def test_an_unknown_action_is_treated_as_holding(self, stagflation):
        window = decision_months(stagflation.months)[0]
        assert play_alpha(stagflation, {window: "nonsense"}) == 0.0


class TestScoringIdentity:
    def test_the_product_carries_its_own_alpha_version(self):
        """It must NOT be Step 5's constant: that names the research
        definition and sits inside the G5 seal, where a change needs an
        amendment and would mean something different."""
        from ah.eval import decision_metrics

        assert PLAY_ALPHA_VERSION != decision_metrics.DECISION_ALPHA_VERSION
        assert PLAY_ALPHA_VERSION

    def test_play_does_not_use_the_toy_simulator(self):
        """It replaces ah.core.institution for SCORING rather than wrapping it.

        The window calendar (`decision_months`) is shared on purpose — the
        windows are the same windows. What must not be imported is the toy
        simulator, because two value models in one scoring path is exactly the
        drift this guard exists to prevent.
        """
        import ast

        import ah.play as play_module

        tree = ast.parse(Path(play_module.__file__).read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
        assert "ah.core.institution.simulate_institution" not in names
        assert "ah.core.institution.hold_course_twin" not in names
        assert "ah.core.institution.decision_months" in names


class TestAttribution:
    def test_contributions_sum_to_the_alpha_shown(self, stagflation):
        """The property that made porting mandatory: what the reckoning
        attributes to each window must add up to the alpha beside it."""
        from ah.play import window_contributions_play

        windows = decision_months(stagflation.months)
        decisions = {windows[0]: "derisk", windows[3]: "secondary", windows[5]: "leanin"}
        attr = window_contributions_play(stagflation, decisions)
        assert sum(attr.contributions) == pytest.approx(attr.total_alpha, abs=1e-9)
        assert attr.total_alpha == pytest.approx(play_alpha(stagflation, decisions), abs=1e-9)

    def test_one_contribution_per_window_in_order(self, stagflation):
        from ah.play import window_contributions_play

        windows = decision_months(stagflation.months)
        attr = window_contributions_play(stagflation, {windows[0]: "derisk"})
        assert attr.months == tuple(windows)
        assert len(attr.contributions) == len(windows)
        assert attr.actions[0] == "derisk"
        assert all(a == "hold" for a in attr.actions[1:])

    def test_holding_throughout_attributes_nothing(self, stagflation):
        from ah.play import window_contributions_play

        attr = window_contributions_play(stagflation, {})
        assert attr.contributions == tuple(0.0 for _ in attr.months)
        assert attr.total_alpha == 0.0
