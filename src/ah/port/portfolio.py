"""Portfolio and institution state containers (WP3.1).

The aggregation layer of liquidity-spine v0.2 §3: one cash account, the sleeve
registry, and coverage ON BOTH BASES — true and reported — because in a
drawdown reported coverage looks healthier than true coverage (the denominator
effect in the number allocators actually watch). The ENGINE that moves cash
through the waterfall is WP3.7's; the twin's mechanics are WP3.8's. What lives
here is state, aggregation, and the invariants.

The institution wraps the portfolio plus the frozen portfolio/institution
contract (hedging, collateral pool, leverage — WP2R.6), round-tripping through
``ah.core.institutionstate``.
"""

from __future__ import annotations

from typing import Any

from ah.core.institutionstate import PortfolioInstitutionState, load_institution_state
from ah.port.cohort import ClosedEndCohort
from ah.port.sleeves import EvergreenVehicle, LiquidSleeve, OpenEndedSleeve

AnySleeve = ClosedEndCohort | OpenEndedSleeve | EvergreenVehicle | LiquidSleeve


class PortfolioError(ValueError):
    """A construction or aggregation that violates a portfolio invariant."""


class Portfolio:
    """Cash + the sleeves, with both-bases aggregation."""

    def __init__(self, *, cash: float) -> None:
        if cash < 0.0:
            raise PortfolioError("cash cannot start negative")
        self.cash = cash
        self.cohorts: dict[str, ClosedEndCohort] = {}
        self.open_ended: dict[str, OpenEndedSleeve] = {}
        self.evergreen: dict[str, EvergreenVehicle] = {}
        self.liquid: dict[str, LiquidSleeve] = {}
        #: WP3.7's headline output — every forced sale is a logged event, never
        #: a silent number (spec §8: period, amount, cause, sleeves sold).
        self.forced_sales: list[dict[str, Any]] = []

    # -- registry ----------------------------------------------------------- #
    def add(self, key: str, sleeve: AnySleeve) -> None:
        registry = {
            ClosedEndCohort: self.cohorts,
            OpenEndedSleeve: self.open_ended,
            EvergreenVehicle: self.evergreen,
            LiquidSleeve: self.liquid,
        }[type(sleeve)]
        if key in registry:
            raise PortfolioError(f"duplicate sleeve key '{key}'")
        registry[key] = sleeve  # type: ignore[index]

    # -- aggregation, both bases -------------------------------------------- #
    def nav_true(self) -> float:
        return (
            self.cash
            + sum(c.nav_true for c in self.cohorts.values())
            + sum(s.nav_true for s in self.open_ended.values())
            + sum(e.nav_true for e in self.evergreen.values())
            + sum(liq.value for liq in self.liquid.values())
        )

    def nav_reported(self) -> float:
        return (
            self.cash
            + sum(c.nav_reported for c in self.cohorts.values())
            + sum(s.nav_reported for s in self.open_ended.values())
            + sum(e.nav_reported for e in self.evergreen.values())
            + sum(liq.value for liq in self.liquid.values())  # liquid marks are true
        )

    def total_unfunded(self) -> float:
        return sum(c.unfunded for c in self.cohorts.values())

    def coverage_true(self) -> float:
        nav = self.nav_true()
        return self.total_unfunded() / nav if nav > 0 else float("inf")

    def coverage_reported(self) -> float:
        nav = self.nav_reported()
        return self.total_unfunded() / nav if nav > 0 else float("inf")

    def coverage_liquid(self) -> float:
        """P-B's caveat, first-class: unfunded against LIQUID assets — the
        ratio that actually determines whether you become a forced seller."""
        liquid = self.cash + sum(liq.value for liq in self.liquid.values())
        return self.total_unfunded() / liquid if liquid > 0 else float("inf")

    def private_weight_true(self) -> float:
        nav = self.nav_true()
        if nav <= 0:
            return 0.0
        private = sum(c.nav_true for c in self.cohorts.values()) + sum(
            e.nav_true for e in self.evergreen.values()
        )
        return private / nav

    def private_weight_reported(self) -> float:
        nav = self.nav_reported()
        if nav <= 0:
            return 0.0
        private = sum(c.nav_reported for c in self.cohorts.values()) + sum(
            e.nav_reported for e in self.evergreen.values()
        )
        return private / nav

    def weights_true(self) -> dict[str, float]:
        """Per-sleeve weights on the true basis; sums to 1 for a solvent book."""
        nav = self.nav_true()
        if nav <= 0:
            raise PortfolioError("weights undefined for a valueless portfolio")
        weights = {"cash": self.cash / nav}
        for key, c in self.cohorts.items():
            weights[key] = c.nav_true / nav
        for key, s in self.open_ended.items():
            weights[key] = s.nav_true / nav
        for key, e in self.evergreen.items():
            weights[key] = e.nav_true / nav
        for key, liq in self.liquid.items():
            weights[key] = liq.value / nav
        return weights


class Institution:
    """A portfolio plus the frozen institution contract (WP2R.6 fields)."""

    def __init__(self, portfolio: Portfolio, contract: PortfolioInstitutionState) -> None:
        self.portfolio = portfolio
        self.contract = contract

    @classmethod
    def from_document(cls, portfolio: Portfolio, document: dict[str, Any]) -> Institution:
        return cls(portfolio, load_institution_state(document))

    def to_document(self) -> dict[str, Any]:
        document = self.contract.model_dump(mode="json")
        document["portfolio"] = {
            **document["portfolio"],
            "cash": self.portfolio.cash,
            "sleeve_ids": sorted(
                {
                    *document["portfolio"]["sleeve_ids"],
                }
            ),
        }
        load_institution_state(document)
        return document
