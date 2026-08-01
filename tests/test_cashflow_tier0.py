"""WP3.5 — the tier-0 benchmark, frozen before tier 1 exists.

The classic constant-G TA behaves like the classic: a J-curve (early calls,
late distributions), full deployment, terminal liquidation to zero NAV, and a
TVPI a 12%-growth fund should have. Deterministic to the bit.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ah.port import cashflow_tier0 as t0

ROOT = Path(__file__).resolve().parents[1]


def _base() -> dict:
    return json.loads(
        (ROOT / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )


class TestSpec:
    def test_spec_is_frozen_with_measured_g_and_named_unavailability(self):
        spec = t0.load_spec()
        assert spec["tier0_version"] == "tier0-2026.08"
        assert 0.08 < spec["g_annual"] < 0.16  # measured public TR mean, sane band
        assert "UNPARAMETERIZABLE" in spec["historical_simulation_leg"]  # named, not dropped


class TestClassicShape:
    def _flows(self, quarters: int = 56) -> list:
        return t0.run_tier0(_base(), committed=100.0, vintage_year=2026, quarters=quarters)

    def test_j_curve_calls_front_distributions_back(self):
        flows = self._flows()
        calls = np.array([f.call for f in flows])
        dists = np.array([f.distribution_total for f in flows])
        assert calls[:8].sum() > calls[8:16].sum() > calls[16:24].sum()  # RC declines
        assert dists[:12].sum() < dists[28:40].sum()  # the bow builds late
        assert np.all(calls >= 0) and np.all(dists >= 0)

    def test_terminal_liquidation_forces_nav_to_zero(self):
        base = _base()
        flows = t0.run_tier0(base, committed=100.0, vintage_year=2026, quarters=48)
        # L = 10y = 40q; by 48q the fund has wound up: no NAV left to distribute
        tail_dists = [f.distribution_total for f in flows[44:]]
        assert sum(tail_dists) == pytest.approx(0.0, abs=1e-9)

    def test_moneyness_is_that_of_a_12pct_fund(self):
        flows = self._flows(quarters=60)
        paid_in = sum(f.call for f in flows)
        distributed = sum(f.distribution_total for f in flows)
        tvpi = distributed / paid_in
        assert 1.3 < tvpi < 3.5  # a decade-ish at ~12%/yr, J-curve drag included

    def test_bit_deterministic(self):
        a = self._flows()
        b = self._flows()
        assert a == b

    def test_refusals(self):
        with pytest.raises(t0.Tier0Error, match="quarters"):
            t0.run_tier0(_base(), committed=100.0, vintage_year=2026, quarters=0)
