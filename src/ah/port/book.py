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
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from ah.core.digest import canonical_json
from ah.port.cohort import ClosedEndCohort

BOOK_STATE_VERSION = "opening-book-0.2"
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

#: Cohort ids the ENGINE mints for itself during play. ``ah.play`` commits one
#: new vintage per private sleeve per year as ``f"{asset}-v{year}"``, and
#: ``Portfolio.add`` raises on a duplicate key — so an entered rung carrying
#: one of these ids validates at the door, plays for as many years as it takes
#: the pacing plan to reach that vintage, and then 500s mid-decade. The
#: namespace is refused wholesale rather than horizon by horizon: the check
#: has no business knowing how long the world runs, and the derived book's own
#: rungs are ``f"{asset}-s{k}"``, which never collides.
_RESERVED_COHORT_ID = re.compile(r"^(?:" + "|".join(PRIVATE_SLEEVES) + r")-v\d+$")


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

    state_version: Literal["opening-book-0.1", "opening-book-0.2"] = BOOK_STATE_VERSION
    liquid: dict[str, float]
    private: dict[str, list[dict[str, Any]]]
    cash: float
    #: The institution's POLICY targets (su-app-07), distinct from the VALUES
    #: above. ``None`` (the 0.1 shape) means "no targets entered" — a book
    #: paces against its own opening weights; see ``effective_targets()``.
    targets: dict[str, float] | None = None
    #: Reporting bands per sleeve, ``{sleeve: (lo, hi)}``. ``None`` means "no
    #: bands entered". A target outside its own band is legal (accepted, not
    #: refused) — ``validate_book`` returns it as a warning string instead.
    ranges: dict[str, tuple[float, float]] | None = None

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
        """Per-sleeve opening private NAV — what the analyst actually HOLDS.

        su-app-06 (I1) measured the commitment cap against this, because the
        book IS the institution and ``START_TARGETS`` is not. su-app-07 moved
        the cap one step further on, to ``effective_targets()``: an
        institution paces against the allocation it is aiming at, and a book
        that holds 20 points of pe against a 30-point policy target must be
        allowed to commit toward the 30. This method is still the fallback
        that ``effective_targets()`` builds its private half from when no
        targets were entered, and is still the opening NAV every value
        surface reads — it is no longer the cap basis.
        """
        return {
            sleeve: sum(float(rung["value"]["nav_true"]) for rung in rungs)
            for sleeve, rungs in self.private.items()
        }

    def private_nav(self) -> float:
        return sum(
            float(rung["value"]["nav_true"]) for rungs in self.private.values() for rung in rungs
        )

    def effective_targets(self) -> dict[str, float]:
        """The policy targets this book paces against: the entered `targets`
        when present, else the book's own opening values.

        Always a FRESH dict. ``simulate_play`` binds its local ``targets`` to
        this return value (su-app-07 task 2), so handing back ``self.targets``
        by reference would let a later in-place edit anywhere downstream
        silently rewrite the stored book's own policy.
        """
        if self.targets is not None:
            return dict(self.targets)
        return {**self.liquid, **self.target_nav()}


def validate_book(book: OpeningBook, liquid_sleeves: tuple[str, ...]) -> list[str]:
    """Refuse a book that cannot be played, naming the rule that failed.

    ``liquid_sleeves`` is the world's own set — in ``simulate_play`` it is
    ``tuple(a for a in paths.asset_order if a not in PRIVATE_ASSETS)``. A
    generated world has no ``reits``; entering one would create a sleeve the
    tape has no returns for.

    Returns a list of warning strings (empty when clean) rather than raising
    for a target outside its own reporting range — that combination is
    accepted (su-app-07's deliberate choice) and ``pyproject.toml`` sets
    ``filterwarnings = ["error"]``, so ``warnings.warn`` would invert the
    very requirement this implements by raising inside the suite that tests
    the leniency.
    """
    if set(book.liquid) != set(liquid_sleeves):
        extra = sorted(set(book.liquid) - set(liquid_sleeves))
        missing = sorted(set(liquid_sleeves) - set(book.liquid))
        raise BookError(
            f"book's liquid sleeves do not match this world: unexpected {extra}, missing {missing}"
        )
    if set(book.private) != set(PRIVATE_SLEEVES):
        raise BookError(f"book must name exactly {sorted(PRIVATE_SLEEVES)} private sleeves")

    # cohort ids are the PORTFOLIO's keys, and the portfolio is flat: a book
    # is checked across all three sleeves at once, not sleeve by sleeve.
    seen: dict[str, str] = {}
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
            # `Portfolio.add` raises PortfolioError on a repeated key, which
            # is a 500 on every read of a session the door already accepted.
            # Both of these are the boundary's job (su-app-06 I4).
            cohort_id = str(doc["identity"]["cohort_id"])
            if cohort_id in seen:
                raise BookError(
                    f"{sleeve} rung {index} repeats cohort_id '{cohort_id}', already used by "
                    f"{seen[cohort_id]}: every rung in the book needs its own id"
                )
            seen[cohort_id] = f"{sleeve} rung {index}"
            if _RESERVED_COHORT_ID.match(cohort_id):
                raise BookError(
                    f"{sleeve} rung {index} uses the reserved cohort_id '{cohort_id}': "
                    "'<sleeve>-v<year>' names the vintages the pacing plan commits "
                    "during play, and would collide with one of them mid-decade"
                )
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

    full_sleeves = set(liquid_sleeves) | set(PRIVATE_SLEEVES)

    if book.targets is not None:
        if set(book.targets) != full_sleeves:
            extra = sorted(set(book.targets) - full_sleeves)
            missing = sorted(full_sleeves - set(book.targets))
            raise BookError(
                f"book's targets do not match this world: unexpected {extra}, missing {missing}"
            )
        for sleeve, value in book.targets.items():
            if value < 0.0:
                raise BookError(f"target '{sleeve}' is negative: {value}")
        target_total = sum(book.targets.values()) + book.cash
        if abs(target_total - BOOK_TOTAL) > BOOK_TOLERANCE:
            raise BookError(f"book's targets total {target_total:g}, must total {BOOK_TOTAL:g}")

    warnings: list[str] = []
    if book.ranges is not None:
        unknown = sorted(set(book.ranges) - full_sleeves)
        if unknown:
            raise BookError(f"book's ranges name sleeves this world does not have: {unknown}")
        for sleeve, band in book.ranges.items():
            lo, hi = band
            if not (0.0 <= lo < hi <= 100.0):
                raise BookError(
                    f"range for '{sleeve}' is not a valid band: [{lo:g}, {hi:g}] "
                    "(need 0 <= lo < hi <= 100)"
                )
        # a target outside its own range is ACCEPTED — surfaced as a warning
        # rather than refused. Checked against `effective_targets()`, not
        # `book.targets` directly, so a book with no entered targets (paced
        # against its own opening weights) is held to the same declared
        # bands: effective_targets() is the single place this resolves, so
        # every consumer — including this one — reads through it rather than
        # re-deriving the fallback.
        effective = book.effective_targets()
        for sleeve, band in book.ranges.items():
            lo, hi = band
            value = effective.get(sleeve)
            if value is not None and not (lo <= value <= hi):
                warnings.append(
                    f"target '{sleeve}' = {value:g} is outside its declared range [{lo:g}, {hi:g}]"
                )

    return warnings


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
