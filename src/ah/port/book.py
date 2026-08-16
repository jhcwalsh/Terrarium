"""The opening book and the kickoff commitment plan (su-app-06).

An ENTERED book replaces the ladder ``play._seed_ladder`` derives. Its private
rungs are serialized ``ClosedEndCohort`` documents, so entering a book reuses
the Step-3 state contract rather than inventing a second cohort model —
serialization IS the contract, exactly as it already is for ``_scaled_cohort``.

The pydantic models check types and signs. Everything semantic lives in
``validate_book`` / ``validate_plan`` as free functions, because the legal
sleeve set depends on the world being played and a model validator cannot see
it — and because a rule that raises inside pydantic comes back wrapped in a
``ValidationError``, which makes for a useless 422.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from ah.core.digest import canonical_json
from ah.port.cohort import ClosedEndCohort

BOOK_STATE_VERSION = "opening-book-0.1"
PLAN_STATE_VERSION = "commitment-plan-0.1"

#: Liquid points + private NAV + cash. The default books are 98 + 2 cash.
BOOK_TOTAL = 100.0
#: Scaling a ten-rung ladder to a target NAV leaves float dust.
BOOK_TOLERANCE = 1e-6
#: paid_in + unfunded == committed + cumulative_recycled. Verified to 4e-16
#: across the thirty seeded rungs; it is NOT the simpler
#: paid_in + unfunded == committed, which recycling can legitimately break.
RUNG_TOLERANCE = 1e-9

PRIVATE_SLEEVES: tuple[str, ...] = ("pe", "pc", "re")


class BookError(ValueError):
    """A book or plan that cannot be played, with the failing rule named."""


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class CommitmentPlan(BaseModel):
    """The kickoff pacing plan: planned commitment points per sleeve per year."""

    model_config = ConfigDict(extra="forbid")

    state_version: Literal["commitment-plan-0.1"] = PLAN_STATE_VERSION
    points: dict[str, list[float]]

    @field_validator("points")
    @classmethod
    def _shape(cls, value: dict[str, list[float]]) -> dict[str, list[float]]:
        if set(value) != set(PRIVATE_SLEEVES):
            raise ValueError(f"plan must name exactly {sorted(PRIVATE_SLEEVES)}")
        lengths = {len(v) for v in value.values()}
        if len(lengths) != 1:
            raise ValueError(f"plan sleeves have different lengths: {sorted(lengths)}")
        for sleeve, years in value.items():
            for k, points in enumerate(years):
                if points < 0.0:
                    raise ValueError(f"plan {sleeve} year {k} is negative: {points}")
        return value

    def digest(self) -> str:
        return _digest(self.model_dump())


class OpeningBook(BaseModel):
    """The institution's state at t0, as an analyst entered it."""

    model_config = ConfigDict(extra="forbid")

    state_version: Literal["opening-book-0.1"] = BOOK_STATE_VERSION
    liquid: dict[str, float]
    private: dict[str, list[dict[str, Any]]]
    cash: float

    @field_validator("liquid")
    @classmethod
    def _no_negative_weights(cls, value: dict[str, float]) -> dict[str, float]:
        for sleeve, points in value.items():
            if points < 0.0:
                raise ValueError(f"liquid sleeve '{sleeve}' is negative: {points}")
        return value

    @field_validator("cash")
    @classmethod
    def _no_negative_cash(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError(f"cash is negative: {value}")
        return value

    def digest(self) -> str:
        return _digest(self.model_dump())

    def cohorts(self, sleeve: str) -> list[ClosedEndCohort]:
        """The sleeve's rungs as runtime cohorts, re-validated on the way in."""
        return [ClosedEndCohort.from_document(doc) for doc in self.private[sleeve]]

    def target_nav(self) -> dict[str, float]:
        """Per-sleeve opening private NAV.

        This is the basis a commitment cap is measured against once an
        analyst has entered a book (su-app-06 I1): the book IS the
        institution, so ``2 x target x _ANNUAL_COMMITMENT_RATE`` has to be
        measured against the sleeve the analyst actually holds, not against
        ``START_TARGETS``. All three enforcement points — ``validate_plan``
        at kickoff, the decision door in ``ah.serve``, and
        ``simulate_play``'s own check — read the cap from here, so a plan
        legal at kickoff cannot be refused at the window it is committed in.
        """
        return {
            sleeve: sum(float(rung["value"]["nav_true"]) for rung in rungs)
            for sleeve, rungs in self.private.items()
        }

    def private_nav(self) -> float:
        return sum(
            float(rung["value"]["nav_true"]) for rungs in self.private.values() for rung in rungs
        )


def validate_book(book: OpeningBook, liquid_sleeves: tuple[str, ...]) -> None:
    """Refuse a book that cannot be played, naming the rule that failed.

    ``liquid_sleeves`` is the world's own set — in ``simulate_play`` it is
    ``tuple(a for a in paths.asset_order if a not in PRIVATE_ASSETS)``. A
    generated world has no ``reits``; entering one would create a sleeve the
    tape has no returns for.
    """
    if set(book.liquid) != set(liquid_sleeves):
        extra = sorted(set(book.liquid) - set(liquid_sleeves))
        missing = sorted(set(liquid_sleeves) - set(book.liquid))
        raise BookError(
            f"book's liquid sleeves do not match this world: unexpected {extra}, missing {missing}"
        )
    if set(book.private) != set(PRIVATE_SLEEVES):
        raise BookError(f"book must name exactly {sorted(PRIVATE_SLEEVES)} private sleeves")

    for sleeve, rungs in book.private.items():
        if not rungs:
            raise BookError(f"private sleeve '{sleeve}' has no rungs")
        for index, doc in enumerate(rungs):
            try:
                ClosedEndCohort.from_document(doc)  # the state contract validates the rung
            except ValueError as exc:
                raise BookError(
                    f"{sleeve} rung {index} is not a valid closed-end cohort document: {exc}"
                ) from exc
            commitment = doc["commitment"]
            lhs = float(commitment["paid_in"]) + float(commitment["unfunded"])
            rhs = float(commitment["committed"]) + float(commitment["cumulative_recycled"])
            if abs(lhs - rhs) > RUNG_TOLERANCE:
                raise BookError(
                    f"{sleeve} rung {index} breaks the recycling identity: "
                    f"paid_in + unfunded = {lhs}, committed + recycled = {rhs}"
                )

    total = sum(book.liquid.values()) + book.cash + book.private_nav()
    if abs(total - BOOK_TOTAL) > BOOK_TOLERANCE:
        raise BookError(f"book totals {total:g}, must total {BOOK_TOTAL:g}")


def validate_plan(plan: CommitmentPlan, targets: dict[str, float]) -> None:
    """Refuse a plan year outside the lever's already-declared bound."""
    from ah.play import _ANNUAL_COMMITMENT_RATE, COMMIT_CAP_MULTIPLE

    for sleeve, years in plan.points.items():
        cap = COMMIT_CAP_MULTIPLE * float(targets[sleeve]) * _ANNUAL_COMMITMENT_RATE
        for k, points in enumerate(years):
            if points > cap:
                raise BookError(
                    f"plan {sleeve} year {k} = {points} exceeds the declared bound "
                    f"[0, {cap:.4f}] (0..2x the sleeve's plan pace)"
                )
