"""Open-ended, evergreen, and liquid sleeve runtime objects (WP3.1).

Pure state + the transitions WP3.1 owns: apply a period's return, move cash in
and out, roll the evergreen queue. The FULL vehicle mechanics — notice-period
scheduling, gate base rates, side-pocket carving, queue-lengthening-under-
stress calibration — are WP3.6's; what lives here is the state those mechanics
will drive, with the simple honest transitions the portfolio engine needs
meanwhile. Reported marks are written by WP3.3's kernel via ``report()``.

Each object round-trips through the frozen sleeve-vehicle-state v1.0 contract,
re-validating on the way out.
"""

from __future__ import annotations

from typing import Any

from ah.core.sleevestate import (
    EvergreenVehicleState,
    LiquidSleeveState,
    OpenEndedSleeveState,
    load_sleeve_state,
)


class SleeveError(ValueError):
    """A construction or transition that would violate a sleeve invariant."""


class OpenEndedSleeve:
    """An open-ended (hedge-fund) sleeve: monthly dealing, notice/lockup/gate terms."""

    def __init__(self, state: OpenEndedSleeveState) -> None:
        self._contract = state
        self.nav_true = state.value.nav_true
        self.nav_reported = state.value.nav_reported
        self.gated_flag = state.liquidity.gated_flag
        self.gated_share = state.liquidity.gated_share
        self._flows = dict.fromkeys(
            (
                "subscriptions",
                "redemptions_requested",
                "redemptions_paid",
                "return_true",
                "return_reported",
                "fees",
                "performance_fee_crystallized",
            ),
            0.0,
        )

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> OpenEndedSleeve:
        state = load_sleeve_state(document)
        if not isinstance(state, OpenEndedSleeveState):
            raise SleeveError(f"expected open_ended, got '{document.get('vehicle_type')}'")
        return cls(state)

    def apply_return(self, r_true: float) -> None:
        self.nav_true = max(0.0, self.nav_true * (1.0 + r_true))
        self._flows["return_true"] = r_true

    def report(self, nav_reported: float, r_reported: float) -> None:
        if nav_reported < 0.0:
            raise SleeveError("reported NAV cannot be negative")
        self.nav_reported = nav_reported
        self._flows["return_reported"] = r_reported

    def subscribe(self, amount: float) -> None:
        if amount < 0.0:
            raise SleeveError("subscription must be non-negative")
        self.nav_true += amount
        self.nav_reported += amount
        self._flows["subscriptions"] += amount

    def redeem(self, requested: float) -> float:
        """Pay a redemption subject to the gate. WP3.6 owns notice scheduling;
        here a request pays immediately up to the ungated share of NAV."""
        if requested < 0.0:
            raise SleeveError("redemption must be non-negative")
        self._flows["redemptions_requested"] += requested
        payable_cap = self.nav_true * (
            (self._contract.terms.gate_pct or 1.0) if self.gated_flag else 1.0
        )
        paid = min(requested, payable_cap, self.nav_true)
        self.nav_true -= paid
        self.nav_reported = max(0.0, self.nav_reported - paid)
        self._flows["redemptions_paid"] += paid
        return paid

    def to_document(self) -> dict[str, Any]:
        document = self._contract.model_dump(mode="json")
        document["value"] = {"nav_true": self.nav_true, "nav_reported": self.nav_reported}
        document["liquidity"] = {
            **document["liquidity"],
            "gated_flag": self.gated_flag,
            "gated_share": self.gated_share,
        }
        document["flows"] = dict(self._flows)
        load_sleeve_state(document)
        return document


class EvergreenVehicle:
    """A semi-liquid vehicle whose failure mode is the queue (spec §2)."""

    def __init__(self, state: EvergreenVehicleState) -> None:
        self._contract = state
        self.nav_true = state.value.nav_true
        self.nav_reported = state.value.nav_reported
        self.pending_redemption = state.queue.pending_redemption_amount
        self.queue_age_periods = state.queue.queue_age_periods
        self.fulfilled_pct_history = list(state.queue.fulfilled_pct_history)
        self._flows = dict.fromkeys(
            (
                "subscriptions",
                "redemptions_requested",
                "redemptions_fulfilled",
                "return_true",
                "return_reported",
                "income_distributed",
            ),
            0.0,
        )

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> EvergreenVehicle:
        state = load_sleeve_state(document)
        if not isinstance(state, EvergreenVehicleState):
            raise SleeveError(f"expected evergreen, got '{document.get('vehicle_type')}'")
        return cls(state)

    def apply_return(self, r_true: float) -> None:
        self.nav_true = max(0.0, self.nav_true * (1.0 + r_true))
        self._flows["return_true"] = r_true

    def report(self, nav_reported: float, r_reported: float) -> None:
        if nav_reported < 0.0:
            raise SleeveError("reported NAV cannot be negative")
        self.nav_reported = nav_reported
        self._flows["return_reported"] = r_reported

    def request_redemption(self, amount: float) -> None:
        if amount < 0.0:
            raise SleeveError("redemption request must be non-negative")
        self.pending_redemption += amount
        self._flows["redemptions_requested"] += amount

    def roll_queue(self) -> float:
        """One period of the queue: fulfil up to the cap, pro-rata by policy.

        THE mechanic (spec §2): fulfilment is capped at
        ``redemption_cap_pct_per_period * NAV``, unfulfilled requests roll
        forward and the queue ages — a 'liquid' allocation converts into a
        locked one with no formal gate ever declared.
        """
        cap = self._contract.terms.redemption_cap_pct_per_period * self.nav_true
        fulfilled = min(self.pending_redemption, cap)
        self.nav_true -= fulfilled
        self.nav_reported = max(0.0, self.nav_reported - fulfilled)
        self.pending_redemption -= fulfilled
        requested = self.pending_redemption + fulfilled
        self.fulfilled_pct_history.append(fulfilled / requested if requested > 0 else 1.0)
        self.queue_age_periods = (
            0.0 if self.pending_redemption <= 1e-12 else (self.queue_age_periods + 1.0)
        )
        self._flows["redemptions_fulfilled"] += fulfilled
        return fulfilled

    def to_document(self) -> dict[str, Any]:
        document = self._contract.model_dump(mode="json")
        document["value"] = {"nav_true": self.nav_true, "nav_reported": self.nav_reported}
        document["queue"] = {
            "pending_redemption_amount": self.pending_redemption,
            "queue_age_periods": self.queue_age_periods,
            "fulfilled_pct_history": list(self.fulfilled_pct_history),
        }
        document["flows"] = dict(self._flows)
        load_sleeve_state(document)
        return document


class LiquidSleeve:
    """Stocks/bonds/credit — the funding source for everything else."""

    def __init__(self, state: LiquidSleeveState) -> None:
        self._contract = state
        self.value = state.value
        self.weight = state.weight
        self.return_period = state.return_period

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> LiquidSleeve:
        state = load_sleeve_state(document)
        if not isinstance(state, LiquidSleeveState):
            raise SleeveError(f"expected liquid, got '{document.get('vehicle_type')}'")
        return cls(state)

    def apply_return(self, r: float) -> None:
        self.value = max(0.0, self.value * (1.0 + r))
        self.return_period = r

    def sell(self, amount: float) -> float:
        """Sell down (shortfall resolution); returns proceeds, bounded by value."""
        if amount < 0.0:
            raise SleeveError("sale must be non-negative")
        proceeds = min(amount, self.value)
        self.value -= proceeds
        return proceeds

    def buy(self, amount: float) -> None:
        if amount < 0.0:
            raise SleeveError("purchase must be non-negative")
        self.value += amount

    def to_document(self) -> dict[str, Any]:
        document = self._contract.model_dump(mode="json")
        document["value"] = self.value
        document["weight"] = self.weight
        document["return_period"] = self.return_period
        load_sleeve_state(document)
        return document
