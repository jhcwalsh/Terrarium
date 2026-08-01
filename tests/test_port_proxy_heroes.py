"""WP3.9 + WP3.10 — the liability proxy and the hero funds.

The proxy's acceptance is the pre-stated capital-region bound, checked by the
fit itself (a proxy that ships has already refused to be wrong in disasters);
the heroes' acceptance is exact reconciliation to the cohort — an identity,
not an approximation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ah.port.heroes import HeroError, reconcile, split_cohort
from ah.port.proxy import (
    MAX_REL_ERR_CAPITAL,
    MAX_REL_ERR_VALIDATION,
    LiabilityProfile,
    ProxyError,
    fit_liability_proxy,
)
from ah.port.twin import LiabilityState

ROOT = Path(__file__).resolve().parents[1]


def _cohort_doc() -> dict:
    return json.loads(
        (ROOT / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )


class TestProxy:
    def test_fit_meets_its_prestated_bounds_and_reports_them(self):
        proxy = fit_liability_proxy(LiabilityProfile())
        assert proxy.max_rel_err_validation <= MAX_REL_ERR_VALIDATION
        assert proxy.max_rel_err_capital <= MAX_REL_ERR_CAPITAL

    def test_proxy_matches_exact_pv_in_the_capital_corner(self):
        """The worst funding corner (low rates, high inflation) specifically."""
        profile = LiabilityProfile()
        proxy = fit_liability_proxy(profile)
        exact = LiabilityState(profile, discount_rate=0.005, realized_inflation_factor=1.55).pv()
        approx = proxy.pv(0.005, 1.55)
        assert abs(approx - exact) / exact < MAX_REL_ERR_CAPITAL

    def test_deterministic(self):
        a = fit_liability_proxy(LiabilityProfile())
        b = fit_liability_proxy(LiabilityProfile())
        np.testing.assert_array_equal(a.coefficients, b.coefficients)

    def test_refuses_to_extrapolate(self):
        proxy = fit_liability_proxy(LiabilityProfile())
        with pytest.raises(ProxyError, match="extrapolate"):
            proxy.pv(0.20, 1.0)

    def test_an_underpowered_basis_refuses_to_ship(self):
        with pytest.raises(ProxyError, match="pre-stated"):
            fit_liability_proxy(LiabilityProfile(), degree=1)


class TestHeroes:
    NAMES = ("Meridian Capital IV", "Blackthorn Partners II", "Halcyon Growth I")

    def test_heroes_reconcile_exactly_to_the_cohort(self):
        doc = _cohort_doc()
        heroes = split_cohort(doc, names=self.NAMES, seed=20260802)
        reconcile(doc, heroes)  # raises on any mismatch
        assert len(heroes) == 3
        for hero in heroes:
            assert hero["identity"]["n_funds"] == 1
            assert hero["identity"]["fund_name"] in self.NAMES
            assert 0.0 <= hero["parameters"]["dispersion_draw"] <= 1.0

    def test_deterministic_and_seed_sensitive(self):
        doc = _cohort_doc()
        a = split_cohort(doc, names=self.NAMES, seed=1)
        b = split_cohort(doc, names=self.NAMES, seed=1)
        c = split_cohort(doc, names=self.NAMES, seed=2)
        assert a == b
        assert a != c

    def test_reconcile_catches_a_cooked_book(self):
        doc = _cohort_doc()
        heroes = split_cohort(doc, names=self.NAMES, seed=3)
        heroes[0]["value"]["nav_true"] += 1.0  # someone flatters a letter
        with pytest.raises(HeroError, match="nav_true"):
            reconcile(doc, heroes)

    def test_refusals(self):
        doc = _cohort_doc()
        with pytest.raises(HeroError, match="3-5"):
            split_cohort(doc, names=("A", "B"), seed=1)
        with pytest.raises(HeroError, match="distinct"):
            split_cohort(doc, names=("A", "A", "B"), seed=1)
