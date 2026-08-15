"""Closed-end cohort runtime object (WP3.1).

Liquidity-spine v0.2 §3 state + §4 recursions, as a pure object: no I/O, no
RNG, no clock. Linkage responses ``f_call``/``f_dist`` arrive as plain floats
per step — WP3.4 supplies the calibrated functions; the Phase-A subset runs
them at 1.0 (AM-2: "the same state object, the same recursions, coefficients
off"). Fees and carry accrue in WP3.4's engine; this object books zero for
them, stated rather than implied.

Serialization round-trips through the frozen sleeve-vehicle-state v1.0
contract (``ah.core.sleevestate``): ``from_document`` validates jsonschema-
first, ``to_document`` re-validates on the way out — a cohort that cannot
serialize to the contract is a bug at the moment it happens, not at save time.

Invariants (the plan's property tests, enforced on every transition):
``unfunded >= 0``, ``paid_in <= committed``,
``recallable_balance <= cumulative_distributions``, NAVs ``>= 0``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ah.core.sleevestate import ClosedEndCohortState, load_sleeve_state


class CohortError(ValueError):
    """A construction or transition that would violate a cohort invariant."""


@dataclass(frozen=True)
class CohortStep:
    """One period's flows, as returned by :meth:`ClosedEndCohort.step`.

    ``expired_undrawn`` (ER-6 close-out, owner D1 option C): the residual
    commitment cancelled at terminal lapse — a real LP event, ledgered
    visibly instead of haunting the unfunded totals forever. Zero on every
    non-terminal step.
    """

    call: float
    distribution_income: float
    distribution_capital: float
    nav_growth: float
    fees_paid: float
    carry_crystallized: float
    expired_undrawn: float = 0.0
    #: True on the step where the fund reaches the end of its contractual life
    #: and liquidates. The whole remaining NAV leaves as one distribution on
    #: the FUND's clock, saying nothing about the market — so any statistic
    #: about distribution RATES has to know which part of the quarter's
    #: distributions was this, and recording it beats inferring it from a NAV
    #: that fell to zero (a forced secondary does that too, without paying a
    #: distribution). ``expired_undrawn`` cannot stand in: it is zero on the
    #: lapse of a fund that was fully drawn.
    is_terminal: bool = False

    @property
    def distribution_total(self) -> float:
        return self.distribution_income + self.distribution_capital


class ClosedEndCohort:
    """Mutable runtime state for one (sleeve, vintage) cohort or synthetic fund."""

    def __init__(self, state: ClosedEndCohortState) -> None:
        self._contract = state  # identity/parameters/fees stay contract-typed
        # mutable numerics, plain floats
        self.paid_in = state.commitment.paid_in
        self.unfunded = state.commitment.unfunded
        self.recallable_balance = state.commitment.recallable_balance
        self.cumulative_recycled = state.commitment.cumulative_recycled
        self.nav_true = state.value.nav_true
        self.nav_reported = state.value.nav_reported
        self.cumulative_distributions = state.value.cumulative_distributions
        self.age_years = state.lifecycle.age_years
        self.extension_status = state.lifecycle.extension_status
        self._last = CohortStep(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._check()

    # ------------------------------------------------------------------ #
    # contract round-trip
    # ------------------------------------------------------------------ #
    @property
    def contract(self) -> ClosedEndCohortState:
        """The contract snapshot this cohort was constructed from (identity,
        parameters, fees, committed capital — the immutable side)."""
        return self._contract

    @property
    def committed(self) -> float:
        return self._contract.commitment.committed

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> ClosedEndCohort:
        state = load_sleeve_state(document)
        if not isinstance(state, ClosedEndCohortState):
            raise CohortError(
                f"expected a closed_end document, got '{document.get('vehicle_type')}'"
            )
        return cls(state)

    @classmethod
    def new_commitment(
        cls, base_document: dict[str, Any], *, committed: float, vintage_year: int, cohort_id: str
    ) -> ClosedEndCohort:
        """§5's commitment decision: a fresh cohort — PIC = 0, NAV = 0, age = 0."""
        if committed <= 0:
            raise CohortError("a new commitment must be positive")
        doc = dict(base_document)
        doc["identity"] = {
            **base_document["identity"],
            "vintage_year": vintage_year,
            "cohort_id": cohort_id,
        }
        doc["commitment"] = {
            "committed": committed,
            "paid_in": 0.0,
            "unfunded": committed,
            "recallable_balance": 0.0,
            "cumulative_recycled": 0.0,
        }
        doc["value"] = {"nav_true": 0.0, "nav_reported": 0.0, "cumulative_distributions": 0.0}
        doc["lifecycle"] = {**base_document["lifecycle"], "age_years": 0.0}
        doc["flows"] = dict.fromkeys(base_document["flows"], 0.0)
        return cls.from_document(doc)

    def to_document(self) -> dict[str, Any]:
        s = self._contract
        document = s.model_dump(mode="json")
        document["commitment"] = {
            "committed": s.commitment.committed,
            "paid_in": self.paid_in,
            "unfunded": self.unfunded,
            "recallable_balance": self.recallable_balance,
            "cumulative_recycled": self.cumulative_recycled,
        }
        document["value"] = {
            "nav_true": self.nav_true,
            "nav_reported": self.nav_reported,
            "cumulative_distributions": self.cumulative_distributions,
        }
        document["lifecycle"] = {
            "age_years": self.age_years,
            "contractual_life_years": s.lifecycle.contractual_life_years,
            "extension_status": self.extension_status,
        }
        document["flows"] = {
            "calls": self._last.call,
            "distributions_income": self._last.distribution_income,
            "distributions_capital": self._last.distribution_capital,
            "nav_growth": self._last.nav_growth,
            "fees_paid": self._last.fees_paid,
            "carry_crystallized": self._last.carry_crystallized,
        }
        load_sleeve_state(document)  # re-validate: serialization IS the contract
        return document

    # ------------------------------------------------------------------ #
    # §4 recursions — one period
    # ------------------------------------------------------------------ #
    def step(
        self,
        r_true: float,
        *,
        f_call: float = 1.0,
        f_dist: float = 1.0,
        years_per_period: float = 0.25,
    ) -> CohortStep:
        """Advance one period under true return ``r_true``.

        ``call_rate_t = RC(age) * f_call``           (RC annual; scaled by period)
        ``call_t      = call_rate_t * unfunded``     (capped at unfunded)
        ``dist_rate_t = Y * (age/L)^B * f_dist``     (the register's classic RD(t); bounded [0, 1])
        ``NAV_t       = NAV*(1+r) + call_t - dist_t`` (floored at 0)

        The distribution rate is the model-parameter-register §1 form exactly
        (``RD(t) = Y * (t/L)^B``, annual, scaled to the period). ``Y`` here is
        the register's yield/terminal rate — the LEVEL of the bow at maturity —
        so at ``age = L`` the annual distribution rate is ``Y``. TERMINAL
        LIQUIDATION (the register's flagged convention, resolved): from
        ``age >= L`` (extensions excluded — WP3.4's behavior), the remaining
        NAV distributes in full, forcing NAV to zero rather than letting the
        bow taper forever. Income books ``min(dist, yield_rate/periods_py *
        grown NAV)``, capital the remainder.
        """
        if f_call < 0.0 or f_dist < 0.0:
            raise CohortError("linkage multipliers must be non-negative")
        if years_per_period <= 0.0:
            raise CohortError("years_per_period must be positive")
        p = self._contract.parameters
        life = self._contract.lifecycle.contractual_life_years

        terminal = self.age_years >= life and self.extension_status != "extended"
        expired = 0.0
        if terminal:
            call = 0.0  # past end of life the commitment lapses: no further calls
            # ER-6 (owner D1, option C): the residual commitment EXPIRES at
            # lapse — cancelled and ledgered, exactly as an LP's undrawn
            # commitment is released at fund term, never silently retained.
            expired = self.unfunded
            self.unfunded = 0.0
        else:
            rc_index = min(int(self.age_years), len(p.rc_curve) - 1)
            call_rate = min(1.0, p.rc_curve[rc_index] * f_call * years_per_period)
            call = min(self.unfunded, call_rate * self.unfunded)

        grown = max(0.0, self.nav_true * (1.0 + r_true))
        life_frac = min(1.0, self.age_years / life)
        if terminal:
            dist_rate = 1.0  # terminal liquidation: the fund winds up, NAV -> 0
        else:
            dist_rate = min(1.0, p.yield_rate * (life_frac**p.bow) * f_dist * years_per_period)
        dist = dist_rate * grown
        income = min(dist, p.yield_rate * years_per_period * grown)
        capital = dist - income

        nav_growth = grown - self.nav_true
        self.nav_true = grown + call - dist
        self.paid_in += call
        self.unfunded -= call
        self.cumulative_distributions += dist
        self.age_years += years_per_period
        self._last = CohortStep(call, income, capital, nav_growth, 0.0, 0.0, expired, terminal)
        self._check()
        return self._last

    def report(self, nav_reported: float) -> None:
        """WP3.3's kernel writes the reported mark; the cohort only checks it."""
        if nav_reported < 0.0:
            raise CohortError("reported NAV cannot be negative")
        self.nav_reported = nav_reported

    def recall(self, amount: float) -> float:
        """R14: recall previously distributed capital, bounded by the balance.

        Accounting convention (stated): a recallable distribution, when
        recalled, UNWINDS paid-in capital — ``paid_in`` falls and ``unfunded``
        rises by the same amount, so a later call re-contributes it and
        ``paid_in <= committed`` holds for the cohort's whole life. This is the
        LP convention that keeps the frozen contract's invariant true without a
        side ledger.
        """
        if amount < 0.0:
            raise CohortError("recall amount must be non-negative")
        if amount > self.recallable_balance + 1e-12:
            raise CohortError(
                f"recall {amount} exceeds recallable balance {self.recallable_balance}"
            )
        if amount > self.paid_in + 1e-12:
            raise CohortError("cannot recall more than has ever been paid in")
        self.recallable_balance -= amount
        self.paid_in -= amount
        self.unfunded += amount
        self._check()
        return amount

    def mark_recallable(self, amount: float) -> None:
        """Flag part of a distribution as subject to recall (bounded by history)."""
        if amount < 0.0:
            raise CohortError("recallable amount must be non-negative")
        if self.recallable_balance + amount > self.cumulative_distributions + 1e-12:
            raise CohortError("recallable balance may never exceed cumulative distributions")
        self.recallable_balance += amount

    # ------------------------------------------------------------------ #
    def _check(self) -> None:
        c = self._contract.commitment
        if self.unfunded < -1e-9:
            raise CohortError(f"unfunded went negative: {self.unfunded}")
        if self.paid_in > c.committed + 1e-9:
            raise CohortError(f"paid_in {self.paid_in} exceeds committed {c.committed}")
        if self.recallable_balance > self.cumulative_distributions + 1e-9:
            raise CohortError("recallable balance exceeds cumulative distributions")
        if self.nav_true < 0.0 or self.nav_reported < 0.0:
            raise CohortError("NAV went negative")
