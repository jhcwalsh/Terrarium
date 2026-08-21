"""The playable institution on the Step-3 twin (register ER-3).

What these protect is the thing that was missing: consequence. A capital call
must be funded from somewhere, cash cannot go negative, and when the liquid
leg is exhausted the institution sells private interests at a discount whether
it wants to or not. If any of that stops being true, a secondary sale goes
back to being a slider.
"""

from __future__ import annotations

import itertools
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
from ah.port.cohort import ClosedEndCohort
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


class TestSeedLadder:
    """ladder-01: the opening private book is a staggered ladder of vintages.

    Found by the audit-F2 expiry column, the first surface on which it was
    visible: the book used to open as three clones of the fixture cohort at
    age 5.25, so the ENTIRE private programme reached the end of its life in
    one quarter — 9.02 of undrawn commitment expiring at once, 17% of the
    decade's calls, and every seed cohort winding up together.
    """

    def test_the_ladder_is_staggered_one_rung_per_year_of_fund_life(self):
        """ER-14 close-out (Task S5): each sleeve's own life, not a single
        fixture-wide constant -- infra's pacing row declares 15 years
        (mappings/pacing-parameters-v1.0.yaml's pm_infra), the other three
        sleeves fall back to the shared fixture's 10 (pc/re have no row of
        their own yet; pe's pm_buyout row already agrees at 10)."""
        from ah.play import LIQUID_ASSETS, START_TARGETS, _build_portfolio, _doc, _ladder_life

        fixture_life = int(
            _doc("closed-end-cohort.example.json")["lifecycle"]["contractual_life_years"]
        )
        _, cohorts = _build_portfolio(Policy(), START_TARGETS, LIQUID_ASSETS)
        for asset in PRIVATE_ASSETS:
            life = _ladder_life(asset, fixture_life)
            ages = [c.age_years for c in cohorts[asset]]
            assert len(ages) == life
            assert ages == sorted(ages)  # a staircase
            assert len(set(ages)) == life  # no two rungs share an age
            assert max(ages) < life  # nothing opens already lapsed

    def test_the_ladder_opens_at_exactly_the_same_allocation_as_before(self):
        """The shape of the opening book changed; the institution's allocation
        did not. Each sleeve still opens at its target weight."""
        from ah.play import LIQUID_ASSETS, START_TARGETS, _build_portfolio

        _, cohorts = _build_portfolio(Policy(), START_TARGETS, LIQUID_ASSETS)
        for asset in PRIVATE_ASSETS:
            opening = sum(c.nav_true for c in cohorts[asset])
            assert opening == pytest.approx(START_TARGETS[asset], rel=1e-12)

    def test_the_warmup_rate_reproduces_the_fixtures_own_tvpi(self):
        """The rate the ladder is warmed at is ANCHORED, not chosen: it is the
        one that reproduces the committed fixture's TVPI at the fixture's own
        age, through the same cohort model the game runs. If the cohort model
        changes, this fails and the constant is re-solved — it never silently
        drifts into meaning something else."""
        from ah.play import _WARMUP_QUARTERLY_RETURN, _doc

        base = _doc("closed-end-cohort.example.json")
        cohort = ClosedEndCohort.new_commitment(
            base, committed=100.0, vintage_year=2019, cohort_id="warmup-check"
        )
        for _ in range(round(base["lifecycle"]["age_years"] * 4)):
            cohort.step(_WARMUP_QUARTERLY_RETURN)
        tvpi = (cohort.nav_true + cohort.cumulative_distributions) / cohort.paid_in
        assert tvpi == pytest.approx(base["performance"]["tvpi"], abs=5e-4)

    def test_commitment_retires_a_rung_a_year_instead_of_all_at_once(self, held):
        """The behaviour the change exists for. Under the cloned book every
        expiry landed in a single quarter; a staggered ladder retires one rung
        per year, which is what a steady-state programme does."""
        fired = [q.quarter for q in held.quarters if q.expired_undrawn > 0.0]
        assert len(fired) >= 8  # a decade of annual lapses, not one event
        gaps = {b - a for a, b in itertools.pairwise(fired)}
        assert gaps == {4}  # exactly one a year, evenly spaced


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
        """Not in a benign world; in one stressed enough to exhaust liquidity.
        This is the behaviour that makes a VOLUNTARY secondary a real decision
        — sell early at the haircut, or be sold later at it.

        History: through toy-v0.3 the deflation_bust preset triggered this at
        its base seed. toy-v0.5's variance-normalized Student-t innovations
        make typical months milder (the declared vol concentrates into rare
        tail months), and NO shipped preset now exhausts the liquid sleeves at
        any of 20 seeds — recorded in docs/engine-realism-register.md ER-8.
        The mechanic itself is covered here with a deliberately maximal world
        (schema-bound vol 45, drift -15, a 12-quarter severity-1.0 crisis),
        which forces secondaries on 10 of the first 11 seeds under toy-v0.5;
        seed 0 is pinned. If THIS world stops exhausting liquidity, that is a
        real engine event, not a golden to bump."""
        calm = simulate_play(_paths("goldilocks"), None)
        assert calm.forced_secondaries == 0

        doc: dict[str, Any] = json.loads(
            (PRESETS / "deflation_bust.json").read_text(encoding="utf-8")
        )
        fc = doc["factor_conditions"]
        fc["equity"]["vol_annual_pct"] = 45
        fc["equity"]["drift_annual_pct"] = -15
        fc["crisis_windows"] = [{"start_quarter": 2, "length_quarters": 12, "severity": 1.0}]
        nw = project_numeric(WorldSpec.model_validate(doc))
        stressed = simulate_play(run_path(nw, 0), None)
        assert stressed.forced_secondaries >= 1
        assert stressed.forced_secondary_nav > 0.0

    def test_expired_commitment_is_ledgered_where_the_unfunded_balance_drops(self, held):
        """ER-6's close-out said the residual "expires visibly instead of
        haunting the books"; the audit (F2, 2026-08-14) found the number was
        computed and then dropped by this loop, so nothing downstream could
        see it. The play surface now carries it.

        The seed cohorts open at age 5.25 against a 10-year contractual life,
        so all three lapse in the same quarter of a decade — the one place a
        player sees undrawn commitment cancelled rather than called.
        """
        expired = [q.expired_undrawn for q in held.quarters]
        assert all(e >= 0.0 for e in expired)
        fired = [q for q, e in enumerate(expired) if e > 0.0]
        assert fired, "no commitment ever expires — the ER-6 lapse never fires"

        # It is a REAL release, not a label: unfunded falls by at least the
        # expired amount across the lapse quarter, net of that quarter's own
        # calls (which also draw the balance down) and any new commitment.
        for q in fired:
            before = held.quarters[q - 1].unfunded_total if q else None
            if before is None:
                continue
            drop = before - held.quarters[q].unfunded_total
            assert drop >= expired[q] - held.quarters[q].new_commitments - 1e-9

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
        from ah.play import LIQUID_ASSETS, START_TARGETS, _build_portfolio, _secondary_sale

        policy = Policy()
        portfolio, cohorts = _build_portfolio(policy, START_TARGETS, LIQUID_ASSETS)
        # the opening book is a STAGGERED ladder (one vintage per year of a
        # fund's life), so the sale is exercised across every rung — which is
        # what a real secondary is sold out of
        ladder = cohorts["pe"]
        assert len(ladder) > 1
        before_nav = sum(c.nav_true for c in ladder)
        before_cash = portfolio.cash
        proceeds = _secondary_sale(portfolio, {"pe_ladder": ladder}, policy)

        nav_given_up = before_nav - sum(c.nav_true for c in ladder)
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

    def test_both_play_alpha_stamps_moved_and_they_are_distinct(self):
        """Survey S3: a shared bump is never right - the two planes score
        different tapes.
        Re-pinned under the chosen-PE adoption (D-ER16-1/AM-2026-08-19-001,
        2026-08-19): the GENERATED stamp alone moved to v6 (the v1.3 mapping
        artifact changed only the generated plane's pm_buyout translation);
        the toy stamp stayed at its v5.
        Re-pinned under the quarterly clock (D-QC-1/AM-2026-08-20-001,
        2026-08-20): BOTH stamps move to v7 in one release because the
        decision-skill definition changed on both planes (39 stances, the
        revisable vintage-year figure) - still two distinct STRINGS, never a
        shared value; the lineages merely align at the same number. The
        frozen legacy fallbacks for pre-release rows live in ah.serve
        (Task S5), not here."""
        from ah.port.adapter import GEN_PLAY_ALPHA_VERSION

        assert PLAY_ALPHA_VERSION == "port-v7-quarterly"
        assert GEN_PLAY_ALPHA_VERSION == "port-v7-quarterly-gen"
        assert PLAY_ALPHA_VERSION != GEN_PLAY_ALPHA_VERSION

    def test_the_research_alpha_definition_is_untouched(self):
        """decision_alpha_version names Step 5's RESEARCH definition and
        lives inside the G5 seal; bumping it would mean something different
        (ER-14's own consequences paragraph, verbatim)."""
        import yaml

        ROOT = Path(__file__).resolve().parents[1]
        doc = yaml.safe_load((ROOT / "step5-evaluation-protocol.yaml").read_text())
        assert doc["decision_alpha_version"] == "1.0"

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


class TestInfrastructureCarve:
    """ER-14 close-out (Task S2, A15/A16, D-ER14-2): infrastructure joins the
    played book at 5 points, carved 3 from REITs and 2 from real estate --
    private lands at 38, not 40, so the opening book stays clear of
    Policy.private_weight_range's 0.40 upper bound (an opening breach
    previously produced 29 forced quarters out of 40)."""

    def test_the_opening_book_still_sits_inside_the_policy_band(self):
        from ah.play import PRIVATE_ASSETS, _policy_private_weight

        assert 0.15 < _policy_private_weight(START_TARGETS) < 0.40
        assert sum(START_TARGETS[a] for a in PRIVATE_ASSETS) == pytest.approx(38.0)

    def test_the_real_goal_bucket_is_unchanged_by_the_carve(self):
        """A15: 3 points from REITs and 2 from real estate, so commodities 5 +
        reits 5 + re 5 + infra 5 = 20 points, exactly as before the carve.
        Commodities is DELIBERATELY untouched: ER-14's own attribution
        experiment moves those five points, and touching the sleeve would
        confound the measurement the close-out is judged against."""
        assert START_TARGETS["commodities"] == 5.0
        assert sum(START_TARGETS[a] for a in ("commodities", "reits", "re", "infra")) == 20.0

    def test_infrastructure_is_excluded_from_the_secondary_lever_by_decision(self):
        """A16, ratified: infra is excluded from the secondary-sale lever for
        now (infrastructure secondaries are genuinely thin). _secondary_sale
        is scoped to the pe ladder by an EXPLICIT constant, not by an
        accident of a hardcoded key."""
        from ah.play import SECONDARY_SLEEVE

        assert SECONDARY_SLEEVE == "pe"
