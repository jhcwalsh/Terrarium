"""The institutional twin — DB pension first (WP3.8).

Liabilities, discounting, funding ratio, hedges and the collateral pool —
consuming the frozen WP2R.6 institution contract — plus the hold-course twin's
commitment policy (liquidity-spine §5.1: **the twin follows the pacing plan
set at t = 0, mechanically, regardless of conditions** — decision alpha on
commitments is the cost of flinching, and it needs this counterfactual to be
defined at all).

The liability model is deliberately v1-simple and stated: a parameterized
annual benefit-cashflow profile discounted at a flat rate, with an
inflation-linked share. What the plan's acceptance demands is DIRECTIONS and
MAGNITUDES an actuary would recognize (a rate shock moves liabilities by
roughly duration x shock; the hedge loses when rates rise and collateral
posts; an under-hedged plan's funding volatility is liability-dominated) —
all pinned by test. Full member-level projection is a later refinement, named.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ah.core.institutionstate import PortfolioInstitutionState


class TwinError(ValueError):
    """A liability spec, shock, or plan the twin refuses."""


@dataclass(frozen=True)
class LiabilityProfile:
    """A DB scheme's projected benefit outflows (annual, from valuation date).

    ``peak_year``/``horizon`` shape a smooth hump (young schemes peak later);
    ``inflation_linked_share`` of every cashflow indexes to realized inflation.
    Register kind C throughout — chosen, stated, sensitivity-flagged.
    """

    annual_benefit_base: float = 5.0
    horizon_years: int = 60
    peak_year: int = 20
    inflation_linked_share: float = 0.7

    def cashflows(self) -> np.ndarray:
        t = np.arange(1, self.horizon_years + 1, dtype=float)
        hump = (t / self.peak_year) * np.exp(1.0 - t / self.peak_year)
        return self.annual_benefit_base * hump


@dataclass
class LiabilityState:
    profile: LiabilityProfile
    discount_rate: float
    realized_inflation_factor: float = 1.0

    def __post_init__(self) -> None:
        if self.discount_rate <= -0.5 or self.discount_rate > 0.5:
            raise TwinError("discount rate out of range")

    def pv(self) -> float:
        cf = self.profile.cashflows()
        linked = self.profile.inflation_linked_share
        cf = cf * (linked * self.realized_inflation_factor + (1.0 - linked))
        t = np.arange(1, cf.size + 1, dtype=float)
        return float(np.sum(cf / (1.0 + self.discount_rate) ** t))

    def duration(self) -> float:
        """Macaulay-style PV-weighted mean time — the actuary's sanity number."""
        cf = self.profile.cashflows()
        t = np.arange(1, cf.size + 1, dtype=float)
        disc = cf / (1.0 + self.discount_rate) ** t
        return float(np.sum(t * disc) / np.sum(disc))


@dataclass
class CollateralAccount:
    """The pool behind the rate hedge — the 2022 gilt mechanic's home.

    A rate RISE devalues the receive-fixed hedge; variation margin posts OUT of
    headroom. When headroom runs dry the hedge force-unwinds — logged, never
    silent.
    """

    posted: float
    headroom: float
    unwinds: list[dict[str, float]] = field(default_factory=list)

    def post_margin(self, amount: float) -> float:
        """Post (or receive, if negative) variation margin; returns the hedge
        notional fraction force-unwound (0 = none)."""
        if amount <= 0.0:  # rates fell: margin comes back, headroom rebuilds
            self.posted = max(0.0, self.posted + amount)
            self.headroom -= amount
            return 0.0
        if amount <= self.headroom:
            self.posted += amount
            self.headroom -= amount
            return 0.0
        covered = self.headroom
        shortfall = amount - covered
        self.posted += covered
        self.headroom = 0.0
        fraction_unwound = shortfall / amount
        self.unwinds.append(
            {"margin_call": amount, "covered": covered, "fraction_unwound": fraction_unwound}
        )
        return fraction_unwound


@dataclass
class PensionTwin:
    """Assets + liabilities + hedges, stepped by rate/inflation shocks."""

    contract: PortfolioInstitutionState
    liabilities: LiabilityState
    assets: float
    collateral: CollateralAccount = field(init=False)
    hedge_ratio_effective: float = field(init=False)

    def __post_init__(self) -> None:
        pool = self.contract.institution.collateral_pool
        self.collateral = CollateralAccount(posted=pool.posted, headroom=pool.headroom)
        self.hedge_ratio_effective = self.contract.institution.hedging.rates_hedge_ratio

    def funding_ratio(self) -> float:
        pv = self.liabilities.pv()
        return self.assets / pv if pv > 0 else float("inf")

    def rate_shock(self, dy: float) -> dict[str, float]:
        """Apply a parallel discount-rate shock. Directions, per the actuary:
        rates up -> liabilities DOWN, hedge LOSES, margin POSTS, headroom FALLS
        (and the under-hedged share of the liability move hits funding)."""
        pv_before = self.liabilities.pv()
        duration = self.liabilities.duration()
        self.liabilities.discount_rate += dy
        pv_after = self.liabilities.pv()

        # the hedge replicates the hedged share of the liability move
        hedge_pnl = self.hedge_ratio_effective * (pv_after - pv_before)
        self.assets += hedge_pnl
        # variation margin ~ the hedge's mark-to-market loss when rates rise
        margin_call = -hedge_pnl
        unwound = self.collateral.post_margin(margin_call)
        if unwound > 0.0:
            self.hedge_ratio_effective *= 1.0 - unwound

        return {
            "dy": dy,
            "duration": duration,
            "liability_pv_change": pv_after - pv_before,
            "hedge_pnl": hedge_pnl,
            "margin_call": margin_call,
            "fraction_unwound": unwound,
            "funding_ratio": self.funding_ratio(),
        }

    def inflation_shock(self, factor: float) -> None:
        if factor <= 0.0:
            raise TwinError("inflation factor must be positive")
        hedged = self.contract.institution.hedging.inflation_hedge_ratio
        pv_before = self.liabilities.pv()
        self.liabilities.realized_inflation_factor *= factor
        pv_after = self.liabilities.pv()
        self.assets += hedged * (pv_after - pv_before)


@dataclass(frozen=True)
class HoldCourseTwin:
    """§5.1: the t=0 pacing plan, followed mechanically, whatever happens.

    ``commitment_for_year`` takes the crisis state ONLY to ignore it — the
    signature makes the counterfactual explicit: same year, same plan, same
    number, regardless. The cost of flinching is measured against this."""

    pacing_plan: tuple[float, ...]

    def commitment_for_year(self, year_index: int, *, crisis_state: object = None) -> float:
        if year_index < 0:
            raise TwinError("year index must be >= 0")
        if year_index >= len(self.pacing_plan):
            return self.pacing_plan[-1]  # the plan's terminal pace continues
        del crisis_state  # deliberately unread — that is the whole point
        return self.pacing_plan[year_index]
