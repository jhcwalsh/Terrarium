"""Vehicle mechanics (WP3.6): notice, lockups, gates, side pockets, queues.

The engine layer over WP3.1's sleeve state objects — what converts "I'd like
my money back" into what actually happens. Deterministic throughout: the
mechanics are rules over state, never draws.

* **Open-ended**: redemption requests mature after the notice period; at each
  dealing date the gate caps payouts at ``gate_pct * NAV`` (excess prorated and
  rolled, ``gated_flag`` raised); the side-pocket share of any payout is
  withheld until side-pocket resolution. ``realizable_by_horizon`` computes the
  30/90/180-day realizable amounts from the terms alone — realizable-vs-stated
  liquidity, the sleeve's key modeled risk.
* **Evergreen**: WP3.1's capped queue roll, plus the stress response — in
  stress, redemption demand surges while the cap holds, so the queue LENGTHENS
  (the 2022-23 open-ended real-estate reference episode's mechanic). ALB-F
  gate base rates were never delivered; the stress-response bands here are
  AUTHORED (register kind C) against the public record of that episode and say
  so — the G1 evidence pack carries the citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ah.port.sleeves import EvergreenVehicle, OpenEndedSleeve, SleeveError

DAYS_PER_QUARTER = 91


@dataclass
class PendingRedemption:
    amount: float
    quarters_until_payable: int


@dataclass
class OpenEndedMechanics:
    """Notice + gate + side-pocket scheduling over an open-ended sleeve."""

    sleeve: OpenEndedSleeve
    pending: list[PendingRedemption] = field(default_factory=list)
    side_pocketed: float = 0.0

    def request(self, amount: float) -> None:
        """File a redemption; it matures after the notice period."""
        if amount < 0.0:
            raise SleeveError("redemption request must be non-negative")
        notice_quarters = -(-self.sleeve._contract.terms.notice_days // DAYS_PER_QUARTER)
        self.pending.append(PendingRedemption(amount, notice_quarters))

    def dealing_date(self) -> float:
        """One quarter passes: mature the notice queue, pay through the gate.

        Returns cash actually paid. The side-pocket share of any payout is
        withheld (it pays only at side-pocket resolution); if matured requests
        exceed the gate, the gate raises and the excess rolls forward.
        """
        for p in self.pending:
            p.quarters_until_payable -= 1
        due = sum(p.amount for p in self.pending if p.quarters_until_payable <= 0)
        if due <= 0.0:
            self.sleeve.gated_flag = False
            return 0.0

        terms = self.sleeve._contract.terms
        gate_cap = (terms.gate_pct if terms.gate_pct is not None else 1.0) * self.sleeve.nav_true
        payable = min(due, gate_cap)
        self.sleeve.gated_flag = payable < due
        self.sleeve.gated_share = 0.0 if due <= 0 else max(0.0, 1.0 - payable / due)

        liquid_share = 1.0 - terms.side_pocket_share
        cash_out = payable * liquid_share
        self.side_pocketed += payable * terms.side_pocket_share

        paid = self.sleeve.redeem(payable)  # NAV falls by the full redeemed amount
        assert abs(paid - payable) < 1e-9 or paid < payable  # sleeve floor may bind
        # unpaid excess rolls: rebuild the queue pro-rata
        scale = 0.0 if due <= 0 else max(0.0, 1.0 - payable / due)
        survivors = []
        for p in self.pending:
            if p.quarters_until_payable <= 0:
                if scale > 0:
                    survivors.append(PendingRedemption(p.amount * scale, 1))
            else:
                survivors.append(p)
        self.pending = survivors
        return cash_out

    def resolve_side_pocket(self, recovery_rate: float = 1.0) -> float:
        """Side pockets pay at exit, at a recovery rate; returns the payout."""
        if not 0.0 <= recovery_rate <= 1.5:
            raise SleeveError("recovery_rate out of range")
        payout = self.side_pocketed * recovery_rate
        self.side_pocketed = 0.0
        return payout

    def realizable_by_horizon(self) -> dict[str, float]:
        """What is genuinely realizable in 30/90/180 days, from the terms alone.

        Notice must have elapsed AND a dealing date passed AND the gate honored:
        within `notice_days` nothing is realizable; at the first dealing date
        after notice the gate cap applies; a second dealing date within the
        horizon allows a second gated tranche. Deterministic in the terms.
        """
        terms = self.sleeve._contract.terms
        nav = self.sleeve.nav_true
        gate = terms.gate_pct if terms.gate_pct is not None else 1.0
        freq_days = {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "quarterly": 91,
            "semiannual": 182,
            "annual": 365,
        }[terms.redemption_frequency]
        out: dict[str, float] = {}
        for label, horizon in (("30d", 30), ("90d", 90), ("180d", 180)):
            if self.sleeve._contract.terms.lockup_remaining_months * 30 > horizon:
                out[label] = 0.0
                continue
            usable = horizon - terms.notice_days
            if usable < 0:
                out[label] = 0.0
                continue
            dealing_dates = 1 + usable // freq_days
            # each dealing date releases at most the gate share of remaining NAV
            remaining = nav * (1.0 - terms.side_pocket_share)
            realizable = 0.0
            for _ in range(int(dealing_dates)):
                tranche = gate * remaining
                realizable += tranche
                remaining -= tranche
            out[label] = min(realizable, nav)
        return out


#: The evergreen stress-response bands — AUTHORED (kind C) against the public
#: record of the 2022-23 open-ended RE episode; ALB-F never delivered. The G1
#: evidence pack carries the citations; these constants say what they are.
STRESS_REDEMPTION_SURGE = 3.0  # stress demand vs calm demand
STRESS_SUBSCRIPTION_HAIRCUT = 0.8  # inflows dry up in stress


def evergreen_stress_quarter(
    vehicle: EvergreenVehicle,
    *,
    calm_redemption_demand: float,
    stress: bool,
) -> float:
    """One quarter of an evergreen under calm or stress demand.

    In stress: demand surges (x3), subscriptions dry up (x0.2), the cap holds —
    so the queue lengthens and fulfilment collapses without any gate being
    declared. The 2022-23 RE mechanic as a rule.
    """
    if calm_redemption_demand < 0.0:
        raise SleeveError("demand must be non-negative")
    demand = calm_redemption_demand * (STRESS_REDEMPTION_SURGE if stress else 1.0)
    vehicle.request_redemption(demand)
    # calm-period inflows are the portfolio engine's business (WP3.7), not this rule's
    return vehicle.roll_queue()
