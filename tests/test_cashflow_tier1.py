"""WP3.4 — tier 1, the market-sensitive engine.

The one-model identity is the anchor test: tier 1 with linkage and fees off IS
tier 0's recursion, flow for flow. Then: the frozen linkage hits P-A's target
at the measured 2022 state, stays bounded and monotone, carries no regime
argument structurally; stress starves distributions; the structural mechanics
(fees' basis change, recycling bounds, deferral, extension) behave.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ah.port import cashflow_tier0 as t0
from ah.port import cashflow_tier1 as t1

ROOT = Path(__file__).resolve().parents[1]


def _base() -> dict:
    return json.loads(
        (ROOT / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )


class TestLinkage:
    def test_f_dist_hits_the_pa_target_at_the_measured_2022_state(self):
        cal = t1.load_linkage()["f_dist"]["calibration"]
        got = t1.f_dist(cal["dd_2022_measured"], cal["spread_ratio_2022_measured"])
        # artifact rounding (6/4 dp) leaves ~5e-5 of slack; centered is the claim
        assert got == pytest.approx(0.50, abs=1e-3)  # P-A's drought-depth center
        assert 0.45 <= got <= 0.55  # inside the sealed criterion's window

    def test_f_dist_bounded_and_monotone(self):
        assert t1.f_dist(0.0, 1.0) == pytest.approx(1.0)
        assert t1.f_dist(0.6, 2.0) == pytest.approx(0.30)  # floor binds in disaster
        assert t1.f_dist(0.0, 0.7) == pytest.approx(1.5)  # boom: ceiling binds
        for dd_lo, dd_hi in [(0.0, 0.1), (0.1, 0.3)]:
            assert t1.f_dist(dd_hi, 1.2) < t1.f_dist(dd_lo, 1.2)

    def test_f_call_is_near_flat(self):
        """Delta 3's binding finding: a severe drawdown moves calls only a little."""
        assert t1.f_call(0.0) == 1.0
        assert t1.f_call(0.30) == pytest.approx(0.97)
        assert t1.f_call(0.30) > 0.9

    def test_no_regime_argument_reaches_the_linkage(self):
        """Delta 3, structural: continuous states only — by signature."""
        for fn in (t1.f_dist, t1.f_call):
            params = set(inspect.signature(fn).parameters)
            assert not params & {"regime", "crisis", "recession", "usrec", "label"}

    def test_refusals(self):
        with pytest.raises(t1.Tier1Error):
            t1.f_dist(-0.1, 1.0)
        with pytest.raises(t1.Tier1Error):
            t1.f_dist(0.1, 0.0)


class TestOneModel:
    def test_linkage_off_fees_off_is_exactly_tier0(self):
        """THE identity: one model with the linkage on or off — never two."""
        spec = t0.load_spec()
        g_q = (1.0 + float(spec["g_annual"])) ** 0.25 - 1.0
        quarters = 48
        tier0_flows = t0.run_tier0(_base(), committed=100.0, vintage_year=2026, quarters=quarters)
        result = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=np.full(quarters, g_q),
            drawdown_depth=np.zeros(quarters),
            spread_ratio=np.ones(quarters),
            terms=t1.StructuralTerms(
                recycling_fraction=0.0,
                extension_nav_threshold=float("inf"),  # structural mechanics off
            ),
            fees_on=False,
            linkage_on=False,
        )
        for a, b in zip(tier0_flows, result.flows, strict=True):
            assert a.call == pytest.approx(b.call)
            assert a.distribution_total == pytest.approx(b.distribution_total)
        assert result.carry_crystallized == 0.0

    def test_stress_starves_distributions(self):
        """The engine's central claim: same returns, stressed states -> fewer
        distributions, barely fewer calls."""
        quarters = 40
        returns = np.full(quarters, 0.02)
        calm = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=returns,
            drawdown_depth=np.zeros(quarters),
            spread_ratio=np.ones(quarters),
            fees_on=False,
        )
        stressed = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=returns,
            drawdown_depth=np.full(quarters, 0.25),
            spread_ratio=np.full(quarters, 1.25),
            fees_on=False,
        )
        dist_calm = sum(f.distribution_total for f in calm.flows)
        dist_stress = sum(f.distribution_total for f in stressed.flows)
        calls_calm = sum(f.call for f in calm.flows)
        calls_stress = sum(f.call for f in stressed.flows)
        assert dist_stress < 0.75 * dist_calm  # distributions starve
        assert calls_stress > 0.90 * calls_calm  # calls barely move


class TestStructuralMechanics:
    def _states(self, quarters: int) -> dict[str, Any]:
        return dict(
            drawdown_depth=np.zeros(quarters),
            spread_ratio=np.ones(quarters),
        )

    def test_fee_basis_changes_at_the_investment_period(self):
        quarters = 48
        result = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=np.full(quarters, 0.02),
            **self._states(quarters),
        )
        # first 5y: 2%/yr on committed = 0.5/quarter, constant
        assert result.fees_paid[0] == pytest.approx(0.5)
        assert result.fees_paid[18] == pytest.approx(0.5)
        # after: on NAV, which differs from committed
        assert result.fees_paid[30] != pytest.approx(0.5)

    def test_carry_crystallizes_only_above_hurdle(self):
        quarters = 44
        rich = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=np.full(quarters, 0.05),
            **self._states(quarters),
        )
        poor = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=np.full(quarters, -0.01),
            **self._states(quarters),
        )
        assert rich.carry_crystallized > 0.0
        assert poor.carry_crystallized == 0.0

    def test_subscription_line_defers_lp_calls(self):
        quarters = 12
        deferred = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=np.full(quarters, 0.02),
            **self._states(quarters),
            terms=t1.StructuralTerms(sub_line_deferral_quarters=4),
            fees_on=False,
        )
        assert all(f.call == 0.0 for f in deferred.flows[:4])  # LP sees nothing yet
        assert deferred.flows[4].call > 0.0  # then the line unwinds

    def test_extension_defers_terminal_liquidation(self):
        quarters = 52  # 13y on a 10y life
        strong = t1.run_tier1(
            _base(),
            committed=100.0,
            vintage_year=2026,
            sleeve_returns=np.full(quarters, 0.03),
            **self._states(quarters),
            fees_on=False,
        )
        assert strong.extended  # healthy NAV at L -> extension taken
        # distributions continue past year 10 (no cliff liquidation at q40)
        assert sum(f.distribution_total for f in strong.flows[41:48]) > 0.0
