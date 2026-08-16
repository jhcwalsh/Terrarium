# Opening Book Entry (su-app-06) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an analyst enter a real institution's opening book — liquid weights, cash, and the private vintage ladder rung by rung — plus an editable ten-year commitment plan, and play the decade from it.

**Architecture:** One optional parameter (`opening_book`) threaded through `_build_portfolio` and `simulate_play`; `None` is today's derived path, byte for byte. A new `ah/port/book.py` holds the `OpeningBook` / `CommitmentPlan` contracts, whose private rungs are serialized `ClosedEndCohort` documents so the existing Step-3 state contract does the validating. The session row carries the book and plan as canonical JSON, which makes replay deterministic and demotes the session to practice.

**Tech Stack:** Python 3.12, pydantic v2, FastAPI, SQLite, pytest; React 18 + TypeScript + Vite + vitest for `app/`.

**Spec:** `docs/superpowers/specs/2026-08-15-opening-book-entry-design.md` — read it before Task 1; this plan argues from it throughout.

## Global Constraints

- **Determinism.** No global RNG, no `random`, no time-based defaults. Nothing in this WP draws randomness at all.
- **The server is the authority for value and scoring** (DN-3 W5, hard invariant). `app/` validates shape only — totals, signs, sleeve names. It computes no NAV, no coverage, no alpha.
- **`schemas/` is read-only vendored truth.** This WP adds no file to `schemas/`; the book contract is pydantic under `src/ah/`.
- **No network in tests** (`pytest-socket`, `--disable-socket` in `addopts`).
- **CLI-echoed strings stay ASCII.** Markdown may use Unicode freely.
- **Seal:** `ah/play.py`, `ah/port/`, `ah/serve.py`, `ah/store/` are outside the main/G3/G5 pre-registration locks. Verified 2026-08-15. Do not add any of them to `hashed_files`.
- **Sleeve sets are engine-dependent.** `START_TARGETS` (toy-v0) carries `reits`; `GEN_START_TARGETS` (generated worlds) does not. In `simulate_play` the truth is `liquid = tuple(a for a in paths.asset_order if a not in PRIVATE_ASSETS)` (`play.py:550`). Never hardcode a liquid sleeve list.
- **The books total 98, not 100.** `START_TARGETS` and `GEN_START_TARGETS` both sum to 98.0; `START_CASH = 2.0` is the balance. The enforced identity is `sum(liquid) + sum(rung nav_true) + cash = 100`.
- **Every task ends green:** `uv run pytest -q`, `uv run ruff check . --fix`, `uv run ruff format .`, `uv run pyright`. Lint before the long gate, not after.
- **Commit after every task.** One WP per branch; this whole plan is branch `su-app-06-allocation-entry`.

---

### Task 1: The book and plan contracts

**Files:**
- Create: `src/ah/port/book.py`
- Test: `tests/test_book.py`

**Interfaces:**
- Consumes: `ah.core.digest.canonical_json`, `ah.port.cohort.ClosedEndCohort`.
- Produces: `OpeningBook` (fields `state_version`, `liquid: dict[str, float]`, `private: dict[str, list[dict]]`, `cash: float`; methods `digest() -> str`, `cohorts(sleeve: str) -> list[ClosedEndCohort]`); `CommitmentPlan` (fields `state_version`, `points: dict[str, list[float]]`; method `digest() -> str`); `validate_book(book, liquid_sleeves) -> None`; `validate_plan(plan, targets) -> None`; `BookError`; constants `BOOK_STATE_VERSION`, `PLAN_STATE_VERSION`, `BOOK_TOTAL`, `BOOK_TOLERANCE`, `RUNG_TOLERANCE`.

**Design note the implementer must not "improve":** the pydantic models check *types and signs only*. Every semantic rule lives in the module-level `validate_book` / `validate_plan` functions, because the legal sleeve set depends on the world being played and a model validator cannot see it. Raising inside a pydantic validator would also bury `BookError` inside a `ValidationError`, which makes the 422 messages in Task 5 useless.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_book.py
"""The opening book contract (su-app-06).

A book is the institution's starting state as an analyst typed it: liquid
weights, cash, and a ladder of private vintages. The rungs are serialized
ClosedEndCohort documents, so the Step-3 state contract does the validating
and this module only adds the rules that are about the BOOK rather than
about one cohort.
"""

from __future__ import annotations

import copy

import pytest

from ah.port.book import (
    BOOK_TOTAL,
    CommitmentPlan,
    OpeningBook,
    BookError,
    validate_book,
    validate_plan,
)

TOY_LIQUID = ("equity", "bonds", "hy", "commodities", "reits")


def _rung(committed: float, paid_in: float, nav: float) -> dict:
    """A minimal closed_end document that the state contract accepts."""
    from ah.play import _doc  # the committed fixture is the shape of truth

    doc = copy.deepcopy(_doc("closed-end-cohort.example.json"))
    doc["commitment"] = {
        "committed": committed,
        "paid_in": paid_in,
        "unfunded": committed - paid_in,
        "recallable_balance": 0.0,
        "cumulative_recycled": 0.0,
    }
    doc["value"] = {
        "nav_true": nav,
        "nav_reported": nav,
        "cumulative_distributions": 0.0,
    }
    return doc


def _book(**overrides) -> OpeningBook:
    """A valid toy-shaped book: liquid 63 + private 35 + cash 2 = 100."""
    fields = {
        "liquid": {"equity": 33.0, "bonds": 12.0, "hy": 5.0, "commodities": 5.0, "reits": 8.0},
        "private": {
            "pe": [_rung(40.0, 20.0, 20.0)],
            "pc": [_rung(16.0, 8.0, 8.0)],
            "re": [_rung(14.0, 7.0, 7.0)],
        },
        "cash": 2.0,
    }
    fields.update(overrides)
    return OpeningBook(**fields)


class TestOpeningBook:
    def test_a_valid_book_passes_and_totals_one_hundred(self):
        book = _book()
        validate_book(book, liquid_sleeves=TOY_LIQUID)
        total = sum(book.liquid.values()) + book.cash
        total += sum(r["value"]["nav_true"] for rungs in book.private.values() for r in rungs)
        assert total == pytest.approx(BOOK_TOTAL)

    def test_a_book_that_does_not_total_one_hundred_is_refused(self):
        book = _book(cash=5.0)  # 63 + 35 + 5 = 103
        with pytest.raises(BookError, match="totals 103"):
            validate_book(book, liquid_sleeves=TOY_LIQUID)

    def test_a_sleeve_the_world_does_not_carry_is_refused(self):
        # reits exists in the toy book and NOT in generated worlds: entering it
        # against a generated world would create a sleeve the tape has no
        # returns for, which is the whole point of section 3.1.
        book = _book()
        gen_liquid = ("equity", "bonds", "hy", "commodities")
        with pytest.raises(BookError, match="reits"):
            validate_book(book, liquid_sleeves=gen_liquid)

    def test_a_rung_breaking_the_recycling_identity_is_refused(self):
        bad = _rung(40.0, 20.0, 20.0)
        bad["commitment"]["unfunded"] = 25.0  # 20 + 25 != 40 + 0
        with pytest.raises(BookError, match="recycling identity"):
            validate_book(_book(private={"pe": [bad], "pc": [_rung(16.0, 8.0, 8.0)],
                                         "re": [_rung(14.0, 7.0, 7.0)]}),
                          liquid_sleeves=TOY_LIQUID)

    def test_an_empty_sleeve_ladder_is_refused(self):
        with pytest.raises(BookError, match="no rungs"):
            validate_book(_book(private={"pe": [], "pc": [_rung(16.0, 8.0, 8.0)],
                                         "re": [_rung(14.0, 7.0, 7.0)]}),
                          liquid_sleeves=TOY_LIQUID)

    def test_negative_cash_is_refused_by_the_model_itself(self):
        with pytest.raises(ValueError):
            _book(cash=-1.0)

    def test_cohorts_round_trip_through_the_state_contract(self):
        book = _book()
        cohorts = book.cohorts("pe")
        assert len(cohorts) == 1
        assert cohorts[0].nav_true == pytest.approx(20.0)

    def test_digest_is_stable_and_order_independent(self):
        a = _book()
        b = _book(liquid={"reits": 8.0, "commodities": 5.0, "hy": 5.0,
                          "bonds": 12.0, "equity": 33.0})
        assert a.digest() == b.digest()

    def test_digest_changes_when_one_rung_changes(self):
        a = _book()
        b = _book(private={"pe": [_rung(40.0, 20.5, 20.0)], "pc": [_rung(16.0, 8.0, 8.0)],
                           "re": [_rung(14.0, 7.0, 7.0)]})
        assert a.digest() != b.digest()


class TestCommitmentPlan:
    def test_a_valid_plan_passes(self):
        plan = CommitmentPlan(points={"pe": [3.6] * 10, "pc": [1.44] * 10, "re": [1.26] * 10})
        validate_plan(plan, targets={"pe": 20.0, "pc": 8.0, "re": 7.0})

    def test_a_year_over_the_declared_cap_is_refused(self):
        # the bound is 0..COMMIT_CAP_MULTIPLE (2.0) x target x 0.18
        # pe: 2.0 * 20.0 * 0.18 = 7.2
        plan = CommitmentPlan(points={"pe": [7.3] + [3.6] * 9, "pc": [1.44] * 10,
                                      "re": [1.26] * 10})
        with pytest.raises(BookError, match="year 0"):
            validate_plan(plan, targets={"pe": 20.0, "pc": 8.0, "re": 7.0})

    def test_a_negative_year_is_refused(self):
        with pytest.raises(ValueError):
            CommitmentPlan(points={"pe": [-1.0] * 10, "pc": [1.44] * 10, "re": [1.26] * 10})

    def test_sleeves_of_different_lengths_are_refused(self):
        with pytest.raises(ValueError):
            CommitmentPlan(points={"pe": [3.6] * 10, "pc": [1.44] * 9, "re": [1.26] * 10})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_book.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ah.port.book'`

- [ ] **Step 3: Write the implementation**

```python
# src/ah/port/book.py
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

    def private_nav(self) -> float:
        return sum(
            float(rung["value"]["nav_true"])
            for rungs in self.private.values()
            for rung in rungs
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
            f"book's liquid sleeves do not match this world: "
            f"unexpected {extra}, missing {missing}"
        )
    if set(book.private) != set(PRIVATE_SLEEVES):
        raise BookError(f"book must name exactly {sorted(PRIVATE_SLEEVES)} private sleeves")

    for sleeve, rungs in book.private.items():
        if not rungs:
            raise BookError(f"private sleeve '{sleeve}' has no rungs")
        for index, doc in enumerate(rungs):
            ClosedEndCohort.from_document(doc)  # the state contract validates the rung
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
    from ah.play import COMMIT_CAP_MULTIPLE, _ANNUAL_COMMITMENT_RATE

    for sleeve, years in plan.points.items():
        cap = COMMIT_CAP_MULTIPLE * float(targets[sleeve]) * _ANNUAL_COMMITMENT_RATE
        for k, points in enumerate(years):
            if points > cap:
                raise BookError(
                    f"plan {sleeve} year {k} = {points} exceeds the declared bound "
                    f"[0, {cap:.4f}] (0..2x the sleeve's plan pace)"
                )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_book.py -q`
Expected: PASS, 13 tests.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/port/book.py tests/test_book.py
git commit -m "feat(su-app-06): the opening book and commitment plan contracts

Rungs are serialized ClosedEndCohort documents, so the Step-3 state contract
validates them. Semantic rules are free functions, not model validators: the
legal sleeve set depends on the world, and a rule raised inside pydantic
comes back wrapped in a ValidationError that makes a useless 422."
```

---

### Task 2: The default book and default plan

**Files:**
- Modify: `src/ah/play.py` (add two public functions after `plan_commitments`, ~line 184)
- Test: `tests/test_book_defaults.py`

**Interfaces:**
- Consumes: Task 1's `OpeningBook`, `CommitmentPlan`, `validate_book`, `validate_plan`.
- Produces: `ah.play.default_opening_book(targets: Mapping[str, float] | None = None) -> OpeningBook`; `ah.play.default_commitment_plan(targets: Mapping[str, float] | None = None, windows: int = 9) -> CommitmentPlan`.

**Why these live in `play.py` and not `book.py`:** `_seed_ladder` and `START_TARGETS` are in `play.py`, and `ah.play` already imports `ah.port`. Putting the builders in `book.py` would invert that and create a cycle.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_book_defaults.py
"""The default book is today's derived book (su-app-06).

The screen opens pre-filled and the pre-fill must BE the current product,
or the round-trip test in test_book_override.py is comparing two different
institutions and proving nothing.
"""

from __future__ import annotations

import pytest

from ah.play import (
    PRIVATE_ASSETS,
    START_CASH,
    START_TARGETS,
    default_commitment_plan,
    default_opening_book,
)
from ah.port.adapter import GEN_START_TARGETS
from ah.port.book import BOOK_TOTAL, validate_book, validate_plan


def _liquid_of(targets) -> tuple[str, ...]:
    return tuple(a for a in targets if a not in PRIVATE_ASSETS)


class TestDefaultBook:
    @pytest.mark.parametrize("targets", [START_TARGETS, GEN_START_TARGETS])
    def test_the_default_book_is_valid_and_totals_one_hundred(self, targets):
        book = default_opening_book(targets)
        validate_book(book, liquid_sleeves=_liquid_of(targets))
        total = sum(book.liquid.values()) + book.cash + book.private_nav()
        assert total == pytest.approx(BOOK_TOTAL, abs=1e-6)

    def test_the_toy_book_carries_reits_and_the_generated_book_does_not(self):
        assert "reits" in default_opening_book(START_TARGETS).liquid
        assert "reits" not in default_opening_book(GEN_START_TARGETS).liquid

    def test_each_private_sleeve_gets_a_ten_rung_ladder(self):
        book = default_opening_book(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            assert len(book.private[sleeve]) == 10

    def test_each_sleeve_opens_at_its_target_nav(self):
        book = default_opening_book(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            nav = sum(r["value"]["nav_true"] for r in book.private[sleeve])
            assert nav == pytest.approx(START_TARGETS[sleeve], abs=1e-9)

    def test_cash_is_the_balance(self):
        assert default_opening_book(START_TARGETS).cash == START_CASH

    def test_the_seeded_ladder_opens_converged(self):
        # ER-14: the derived book can never open with nav_reported != nav_true.
        # An ENTERED book can, and that is the state the calibration never saw.
        book = default_opening_book(START_TARGETS)
        for rungs in book.private.values():
            for rung in rungs:
                assert rung["value"]["nav_reported"] == pytest.approx(rung["value"]["nav_true"])

    def test_the_default_is_reproducible(self):
        assert default_opening_book(START_TARGETS).digest() == (
            default_opening_book(START_TARGETS).digest()
        )


class TestDefaultPlan:
    def test_the_default_plan_has_one_entry_per_decision_window(self):
        # NOT one per calendar year. decision_months(120) is nine windows, and
        # the engine fires nine commitments (q = 4, 8, ... 36; `q > 0 and
        # q % 4 == 0`). A tenth entry would be dead.
        from ah.core.institution import decision_months

        plan = default_commitment_plan(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            assert len(plan.points[sleeve]) == len(decision_months(120)) == 9

    def test_the_default_plan_is_flat_at_the_fixed_rule_pace(self):
        plan = default_commitment_plan(START_TARGETS)
        for sleeve in PRIVATE_ASSETS:
            pace = plan.points[sleeve]
            assert len(set(pace)) == 1  # flat: the kickoff default, section 10
            assert pace[0] == pytest.approx(START_TARGETS[sleeve] * 0.18)

    def test_the_default_plan_is_inside_the_declared_bound(self):
        validate_plan(default_commitment_plan(START_TARGETS), dict(START_TARGETS))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_book_defaults.py -q`
Expected: FAIL — `ImportError: cannot import name 'default_opening_book' from 'ah.play'`

- [ ] **Step 3: Write the implementation**

Add to `src/ah/play.py` immediately after `plan_commitments` (~line 184), and add `"default_opening_book"`, `"default_commitment_plan"` to `__all__`:

```python
def default_opening_book(targets: Mapping[str, float] | None = None) -> OpeningBook:
    """Today's DERIVED book, as an OpeningBook document (su-app-06).

    This is what the entry screen opens pre-filled with, and it is built by
    the same ``_seed_ladder`` the engine uses — never a second implementation,
    or the round-trip equivalence test would be comparing two copies of the
    same mistake.
    """
    t = dict(targets) if targets is not None else dict(START_TARGETS)
    base = _doc("closed-end-cohort.example.json")
    return OpeningBook(
        liquid={a: float(t[a]) for a in t if a not in PRIVATE_ASSETS},
        private={
            a: [c.to_document() for c in _seed_ladder(base, a, float(t[a]))]
            for a in PRIVATE_ASSETS
        },
        cash=START_CASH,
    )


def default_commitment_plan(
    targets: Mapping[str, float] | None = None, windows: int = 9
) -> CommitmentPlan:
    """The kickoff plan: the FIXED-rule pace, flat across the decade.

    ONE ENTRY PER DECISION WINDOW, not per calendar year. A 120-month decade
    has nine windows (months 11, 23, ... 107) and the engine fires exactly
    nine commitments (quarters 4, 8, ... 36 — ``q > 0 and q % 4 == 0``, so
    there is no commitment at q=0; the t0 book is the entered ladder, not a
    commitment). Plan index k is the k-th window, which drives the engine's
    vintage year k+1. Callers with a non-decade horizon pass
    ``windows=len(decision_months(months))``.

    Flat because the policy flex is a function of the realized reported
    private weight, which at kickoff cannot be known without simulating the
    tape — and simulating it here would leak it. ``serve.py`` already uses
    ``pacing_rule="fixed"`` for exactly this pre-quarter-0 case.

    A non-flat schedule derived from the current portfolio is wanted and is
    explicitly later work; ``CommitmentPlan``'s per-year shape already carries
    one without a contract change.
    """
    base = plan_commitments(0.0, targets, pacing_rule="fixed")
    return CommitmentPlan(points={a: [base[a]] * windows for a in PRIVATE_ASSETS})
```

Add the import near the other `ah.port` imports at the top of `play.py`:

```python
from ah.port.book import CommitmentPlan, OpeningBook
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_book_defaults.py -q`
Expected: PASS, 10 tests.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/play.py tests/test_book_defaults.py
git commit -m "feat(su-app-06): default_opening_book and default_commitment_plan

Built by the same _seed_ladder and plan_commitments the engine uses, so the
pre-fill IS the current product rather than a second implementation of it."
```

---

### Task 3: The numeric override

**Files:**
- Modify: `src/ah/play.py:441-468` (`_build_portfolio`), `src/ah/play.py:521-553` (`simulate_play` signature and the `_build_portfolio` call)
- Test: `tests/test_book_override.py`

**Interfaces:**
- Consumes: Task 2's `default_opening_book`.
- Produces: `_build_portfolio(policy, targets, liquid, book: OpeningBook | None = None)`; `simulate_play(..., opening_book: OpeningBook | None = None)`.

**This task contains the load-bearing test.** Test 3 in the spec — serve the default book, feed it back, get an identical decade — is the one that proves the entry path and the derived path agree. If it fails, do not weaken it; the serialization or the reconstruction is wrong.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_book_override.py
"""An entered book replaces the derived ladder (su-app-06).

Two properties matter and they pull in opposite directions:
DELETABILITY  - opening_book=None must reproduce today's institution exactly,
                so every session that exists keeps replaying as it did;
EQUIVALENCE   - the DEFAULT book fed back in as an entered book must produce
                an identical decade, so the entry path and the derived path
                are the same institution and not merely similar ones.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    PRIVATE_ASSETS,
    START_TARGETS,
    default_opening_book,
    simulate_play,
)
from ah.port.book import OpeningBook

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


@pytest.fixture(scope="module")
def stagflation():
    return _paths()


def _quarters_equal(a, b) -> bool:
    return [
        (q.quarter, q.nav_true, q.nav_reported, q.cash, q.calls_paid,
         q.distributions_received, q.unfunded_total, q.forced_sale_total)
        for q in a.quarters
    ] == [
        (q.quarter, q.nav_true, q.nav_reported, q.cash, q.calls_paid,
         q.distributions_received, q.unfunded_total, q.forced_sale_total)
        for q in b.quarters
    ]


class TestEquivalence:
    def test_the_default_book_reproduces_the_derived_decade_exactly(self, stagflation):
        """The load-bearing test. Serve the default, feed it back, compare."""
        derived = simulate_play(stagflation, None)
        entered = simulate_play(
            stagflation, None, opening_book=default_opening_book(START_TARGETS)
        )
        assert _quarters_equal(derived, entered)
        assert derived.final_value == pytest.approx(entered.final_value, rel=0, abs=0)

    def test_equivalence_holds_with_decisions_too(self, stagflation):
        decisions = {11: "derisk", 23: "leanin", 35: "secondary"}
        derived = simulate_play(stagflation, decisions)
        entered = simulate_play(
            stagflation, decisions, opening_book=default_opening_book(START_TARGETS)
        )
        assert _quarters_equal(derived, entered)

    def test_the_book_round_trips_through_json(self, stagflation):
        """What the session row stores is JSON, not a Python object."""
        book = default_opening_book(START_TARGETS)
        revived = OpeningBook.model_validate(json.loads(book.model_dump_json()))
        assert revived.digest() == book.digest()
        assert _quarters_equal(
            simulate_play(stagflation, None, opening_book=book),
            simulate_play(stagflation, None, opening_book=revived),
        )


class TestAnEnteredBookActuallyChangesThings:
    def test_a_different_allocation_gives_a_different_decade(self, stagflation):
        """Guards against the override being silently ignored — the failure
        mode that would make every test above pass for the wrong reason."""
        book = default_opening_book(START_TARGETS)
        moved = book.model_copy(deep=True)
        moved.liquid["equity"] -= 5.0
        moved.liquid["bonds"] += 5.0
        entered = simulate_play(stagflation, None, opening_book=moved)
        derived = simulate_play(stagflation, None)
        assert not _quarters_equal(derived, entered)

    def test_the_opening_cash_comes_from_the_book(self, stagflation):
        book = default_opening_book(START_TARGETS)
        moved = book.model_copy(deep=True)
        moved.cash += 1.0
        moved.liquid["equity"] -= 1.0
        result = simulate_play(stagflation, None, opening_book=moved)
        derived = simulate_play(stagflation, None)
        assert result.quarters[0].cash != derived.quarters[0].cash


class TestDeletability:
    def test_none_is_the_derived_path(self, stagflation):
        """opening_book=None must not merely resemble the old behaviour."""
        result = simulate_play(stagflation, None, opening_book=None)
        for sleeve in PRIVATE_ASSETS:
            assert result.quarters[0].private_true[sleeve] > 0.0
        assert result.quarters[0].nav_true > 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_book_override.py -q`
Expected: FAIL — `TypeError: simulate_play() got an unexpected keyword argument 'opening_book'`

- [ ] **Step 3: Write the implementation**

Replace `_build_portfolio` (`play.py:441-468`) with:

```python
def _build_portfolio(
    policy: Policy,
    targets: Mapping[str, float],
    liquid: tuple[str, ...],
    book: OpeningBook | None = None,
) -> tuple[Portfolio, dict[str, list[ClosedEndCohort]]]:
    """An ongoing institution at its target weights, with a cash buffer.

    "Ongoing" now means a staggered ladder per private sleeve (see
    :func:`_seed_ladder`), not one mid-life cohort: the institution opens at
    the same allocation it always did, but its vintages mature one a year
    instead of all at once.

    su-app-06: when ``book`` is given, the liquid values, the cash and every
    private rung come from it instead of being derived. ``book=None`` is the
    derived path, unchanged — that is the whole feature's off switch.
    """
    portfolio = Portfolio(cash=START_CASH if book is None else book.cash)
    base = _doc("closed-end-cohort.example.json")
    liquid_doc = _doc("liquid-sleeve.example.json")

    for asset in liquid:
        sleeve = LiquidSleeve.from_document(liquid_doc)
        sleeve.value = float(targets[asset]) if book is None else float(book.liquid[asset])
        portfolio.add(asset, sleeve)

    cohorts: dict[str, list[ClosedEndCohort]] = {}
    for asset in PRIVATE_ASSETS:
        if book is None:
            rungs = _seed_ladder(base, asset, float(targets[asset]))
        else:
            rungs = book.cohorts(asset)
        for cohort in rungs:
            portfolio.add(cohort.contract.identity.cohort_id, cohort)
        cohorts[asset] = rungs
    return portfolio, cohorts
```

In `simulate_play`, add the parameter to the signature (after `pacing_band`):

```python
    opening_book: OpeningBook | None = None,
```

and change the call at `play.py:553` to:

```python
    portfolio, cohorts = _build_portfolio(policy, targets, liquid, opening_book)
```

Add to `simulate_play`'s docstring:

```
    ``opening_book`` (su-app-06) replaces the DERIVED opening state with an
    entered one — liquid values, cash and every private rung. ``None`` is the
    derived path and is bit-identical to the behaviour before this parameter
    existed.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_book_override.py tests/test_play.py -q`
Expected: PASS. `test_play.py` must be green **unchanged** — it is the regression fence for the `None` path. If any test there fails, the `None` branch was altered; fix the branch, never the test.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/play.py tests/test_book_override.py
git commit -m "feat(su-app-06): opening_book overrides the derived ladder

One optional parameter through _build_portfolio and simulate_play; None is
the derived path unchanged. The load-bearing test feeds the DEFAULT book back
in as an entered book and asserts an identical decade, which is what proves
the entry path and the derived path are the same institution."
```

---

### Task 4: Store the book on the session

**Files:**
- Modify: `src/ah/store/db.py:111` (`_SESSION_STAMPS`)
- Modify: `src/ah/store/sessions.py:73-111` (`create_session`)
- Test: `tests/test_sessions.py` (append a class)

**Interfaces:**
- Consumes: nothing from earlier tasks (raw JSON strings only — the store does not import `ah.port`).
- Produces: `create_session(..., opening_book: str | None = None, commitment_plan: str | None = None)`; session documents gain `opening_book` and `commitment_plan` keys, `None` when absent.

**Deliberate:** the store holds **canonical JSON strings**, not parsed models. `ah/store/` sits below `ah/port/` in the dependency order (`port` → `data` → `core`), and having the store import a port contract would invert it.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_sessions.py
class TestOpeningBookColumns:
    """su-app-06: the entered book is the session's book of record."""

    def test_a_session_defaults_to_no_book(self, conn):
        rec = _a_session(conn)
        assert rec["opening_book"] is None
        assert rec["commitment_plan"] is None

    def test_a_book_and_plan_round_trip_as_stored_json(self, conn):
        book = '{"state_version":"opening-book-0.1","cash":2.0}'
        plan = '{"state_version":"commitment-plan-0.1"}'
        rec = _a_session(conn, opening_book=book, commitment_plan=plan)
        again = sessions.get_session(conn, rec["session_id"])
        assert again["opening_book"] == book
        assert again["commitment_plan"] == plan

    def test_the_columns_are_added_to_a_pre_existing_database(self, tmp_path):
        """The additive-column pattern: an old database upgrades in place and
        its rows read back NULL rather than failing."""
        path = tmp_path / "old.db"
        conn = db.connect(path)
        conn.execute("ALTER TABLE sessions DROP COLUMN opening_book")
        conn.execute("ALTER TABLE sessions DROP COLUMN commitment_plan")
        conn.commit()
        conn.close()
        conn = db.connect(path)  # migrate() must put them back
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
        assert {"opening_book", "commitment_plan"} <= columns
```

Add this helper near the top of the test module if one does not already exist (check first — reuse the module's existing session-creating helper if it has one):

```python
def _a_session(conn, **kwargs):
    run_id = _a_run_record(conn)  # reuse this module's existing helper
    return sessions.create_session(conn, run_id=run_id, months=120, **kwargs)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_sessions.py -k OpeningBookColumns -q`
Expected: FAIL — `KeyError: 'opening_book'`

- [ ] **Step 3: Write the implementation**

In `src/ah/store/db.py`, extend `_SESSION_STAMPS` (line 111):

```python
# narr-02 (DN-9 N-af): the rationale field's version stamp lives on the
# session row itself ... (existing comment unchanged)
#
# su-app-06: the entered opening book and kickoff commitment plan, stored as
# canonical JSON. NULL means the derived default, which is every session
# written before this change - so old rows replay exactly as they did.
_SESSION_STAMPS = (
    ("rationale_schema_version", "TEXT"),
    ("opening_book", "TEXT"),
    ("commitment_plan", "TEXT"),
)
```

In `src/ah/store/sessions.py`, extend `create_session`:

```python
def create_session(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    months: int,
    basis: str = "reported",
    ranked: bool = False,
    participant: str | None = None,
    opening_book: str | None = None,
    commitment_plan: str | None = None,
) -> dict[str, Any]:
```

and add the two columns and two placeholders to the INSERT, passing
`opening_book` and `commitment_plan` in the values tuple.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_sessions.py -q`
Expected: PASS, including every pre-existing test in the module.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/store/db.py src/ah/store/sessions.py tests/test_sessions.py
git commit -m "feat(su-app-06): sessions carry the opening book and commitment plan

Additive columns via the existing _SESSION_STAMPS pattern; NULL is the
derived default, so every session written before this replays unchanged.
Stored as JSON strings - the store must not import a port contract."
```

---

### Task 5: Serve the default, accept an entered book, demote to practice

**Files:**
- Modify: `src/ah/serve.py:96-101` (`CreateSession`), `src/ah/serve.py:223-242` (`create_session`), `src/ah/serve.py:286-298` (`_mark_to_market` book plumbing)
- Test: `tests/test_serve_book.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `GET /book/default?run_id=…` returning `{"book": {...}, "plan": {...}, "liquid_sleeves": [...], "book_digest": "...", "plan_digest": "..."}`; `POST /sessions` accepting optional `book` and `plan`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_serve_book.py
"""The book entry endpoints (su-app-06).

The server is the authority: it serves the default, validates what comes
back, and decides ranked eligibility. The app is not trusted to do any of it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# reuse this module's established app/client fixtures — see tests/test_serve.py
from tests.test_serve import _client, _seeded_run  # noqa: F401


class TestDefaultBookEndpoint:
    def test_it_serves_a_book_a_plan_and_the_worlds_sleeve_set(self, _client, _seeded_run):
        r = _client.get(f"/book/default?run_id={_seeded_run}")
        assert r.status_code == 200
        body = r.json()
        assert body["book"]["state_version"] == "opening-book-0.1"
        assert body["plan"]["state_version"] == "commitment-plan-0.1"
        assert set(body["book"]["liquid"]) == set(body["liquid_sleeves"])
        assert len(body["book_digest"]) == 64

    def test_an_unknown_run_is_404(self, _client):
        assert _client.get("/book/default?run_id=nope").status_code == 404


class TestCreateSessionWithABook:
    def test_the_default_book_submitted_back_keeps_ranked(self, _client, _seeded_run):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        r = _client.post("/sessions", json={
            "run_id": _seeded_run, "ranked": True, "participant": "alice",
            "book": default["book"], "plan": default["plan"],
        })
        assert r.status_code == 201
        assert r.json()["ranked"] is True

    def test_an_edited_book_is_demoted_to_practice(self, _client, _seeded_run):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        book = default["book"]
        book["liquid"]["equity"] -= 5.0
        book["liquid"]["bonds"] += 5.0
        r = _client.post("/sessions", json={
            "run_id": _seeded_run, "ranked": True, "participant": "alice",
            "book": book, "plan": default["plan"],
        })
        assert r.status_code == 201
        assert r.json()["ranked"] is False, "a custom book must never be ranked"

    def test_an_edited_plan_is_also_demoted(self, _client, _seeded_run):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        plan = default["plan"]
        plan["points"]["pe"][3] = 0.0  # a cut year
        r = _client.post("/sessions", json={
            "run_id": _seeded_run, "ranked": True, "participant": "alice",
            "book": default["book"], "plan": plan,
        })
        assert r.json()["ranked"] is False

    def test_a_book_that_does_not_total_one_hundred_is_422_naming_the_rule(
        self, _client, _seeded_run
    ):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        book = default["book"]
        book["cash"] += 3.0
        r = _client.post("/sessions", json={"run_id": _seeded_run, "book": book})
        assert r.status_code == 422
        assert "must total 100" in r.json()["detail"]

    def test_a_foreign_sleeve_is_422(self, _client, _seeded_run):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        book = default["book"]
        book["liquid"]["gold"] = 0.0
        r = _client.post("/sessions", json={"run_id": _seeded_run, "book": book})
        assert r.status_code == 422
        assert "gold" in r.json()["detail"]

    def test_a_plan_year_over_the_cap_is_422(self, _client, _seeded_run):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        plan = default["plan"]
        plan["points"]["pe"][0] = 999.0
        r = _client.post("/sessions", json={
            "run_id": _seeded_run, "book": default["book"], "plan": plan,
        })
        assert r.status_code == 422
        assert "declared bound" in r.json()["detail"]

    def test_a_session_with_a_stored_book_replays_it(self, _client, _seeded_run):
        """The book is the book of record: reading the session back and
        marking to market must use the stored book, not the default."""
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        book = default["book"]
        book["liquid"]["equity"] -= 5.0
        book["liquid"]["bonds"] += 5.0
        sid = _client.post("/sessions", json={
            "run_id": _seeded_run, "book": book, "plan": default["plan"],
        }).json()["session_id"]
        _client.post(f"/sessions/{sid}/advance", json={"to_month": 6})
        custom = _client.get(f"/sessions/{sid}").json()

        plain = _client.post("/sessions", json={"run_id": _seeded_run}).json()["session_id"]
        _client.post(f"/sessions/{plain}/advance", json={"to_month": 6})
        derived = _client.get(f"/sessions/{plain}").json()

        assert custom["value"] != derived["value"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_serve_book.py -q`
Expected: FAIL — 404 on `/book/default`.

If `tests/test_serve.py` does not export reusable `_client` / `_seeded_run` fixtures, move them into `tests/conftest.py` first (a mechanical extraction, no behaviour change) and import from there instead.

- [ ] **Step 3: Write the implementation**

In `src/ah/serve.py`, extend the request model:

```python
class CreateSession(BaseModel):
    run_id: str
    basis: str = "reported"
    ranked: bool = False
    participant: str | None = None
    # su-app-06: an entered book and kickoff plan. Absent = the derived
    # default, which is every session that existed before this.
    book: OpeningBook | None = None
    plan: CommitmentPlan | None = None
```

Add a helper next to `_mark_to_market`:

```python
def _world_book(conn: sqlite3.Connection, run_id: str) -> tuple[OpeningBook, CommitmentPlan, tuple[str, ...]]:
    """The derived default for the world behind ``run_id``, and its sleeve set."""
    rec = get_run_record(conn, run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no run_record {run_id}")
    world = get_world(conn, rec["world_id"])
    if world is None:  # pragma: no cover - FK'd at creation
        raise HTTPException(status_code=404, detail=f"missing world {rec['world_id']}")
    ws = WorldSpec.model_validate(world)
    targets = dict(START_TARGETS)
    if ws.engine_defaults.generator_id != "toy-v0":
        from ah.port.adapter import GEN_START_TARGETS

        targets = dict(GEN_START_TARGETS)
    liquid = tuple(a for a in targets if a not in PRIVATE_ASSETS)
    return default_opening_book(targets), default_commitment_plan(targets), liquid
```

Add the endpoint next to `GET /worlds`:

```python
    @app.get("/book/default")
    def default_book(run_id: str, conn: sqlite3.Connection = Depends(db)):
        """su-app-06: the pre-fill the entry screen opens with — today's
        derived book and the flat fixed-rule plan, for THIS world's sleeve
        set. Built by the engine's own code, never a second implementation."""
        book, plan, liquid = _world_book(conn, run_id)
        return {
            "book": book.model_dump(),
            "plan": plan.model_dump(),
            "liquid_sleeves": list(liquid),
            "book_digest": book.digest(),
            "plan_digest": plan.digest(),
        }
```

Extend `create_session`:

```python
    @app.post("/sessions", status_code=201)
    def create_session(body: CreateSession, conn: sqlite3.Connection = Depends(db)):
        rec = get_run_record(conn, body.run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"no run_record {body.run_id}")
        world = get_world(conn, rec["world_id"])
        if world is None:
            raise HTTPException(status_code=404, detail=f"missing world {rec['world_id']}")
        months = WorldSpec.model_validate(world).horizon.quarters * 3

        default_book_, default_plan_, liquid = _world_book(conn, body.run_id)
        ranked = body.ranked
        book_json = plan_json = None
        if body.book is not None or body.plan is not None:
            book = body.book or default_book_
            plan = body.plan or default_plan_
            try:
                validate_book(book, liquid_sleeves=liquid)
                validate_plan(plan, _plan_targets(book))
            except BookError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            # section 2: a custom book is PRACTICE ONLY. Enforced here, on the
            # authority, not in the app.
            if book.digest() != default_book_.digest() or plan.digest() != default_plan_.digest():
                ranked = False
            book_json = book.model_dump_json()
            plan_json = plan.model_dump_json()

        try:
            return session_store.create_session(
                conn,
                run_id=body.run_id,
                months=months,
                basis=body.basis,
                ranked=ranked,
                participant=body.participant,
                opening_book=book_json,
                commitment_plan=plan_json,
            )
        except session_store.SessionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
```

`_plan_targets` used above is a module-level helper added next to `_world_book`. The plan's cap is a function of the sleeve's target NAV, which for an entered book is that sleeve's own opening NAV, not `START_TARGETS`:

```python
def _plan_targets(book: OpeningBook) -> dict[str, float]:
    """The per-sleeve target NAV a plan's cap is measured against — for an
    entered book that is the sleeve's own opening NAV, not START_TARGETS."""
    return {
        sleeve: sum(float(r["value"]["nav_true"]) for r in rungs)
        for sleeve, rungs in book.private.items()
    }
```

In `_mark_to_market`, load the stored book once and pass it to both `simulate_play` calls:

```python
        stored = doc.get("opening_book")
        book = OpeningBook.model_validate_json(stored) if stored else None
        ...
        active = simulate_play(paths, decisions, use_reported=use_reported,
                               start_targets=targets, opening_book=book)
        twin = simulate_play(paths, None, use_reported=use_reported,
                             start_targets=targets, opening_book=book)
```

Add the imports at the top of `serve.py`:

```python
from ah.play import default_commitment_plan, default_opening_book
from ah.port.book import BookError, CommitmentPlan, OpeningBook, validate_book, validate_plan
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_serve_book.py tests/test_serve.py -q`
Expected: PASS, both modules. `test_serve.py` unchanged.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/serve.py tests/test_serve_book.py
git commit -m "feat(su-app-06): serve the default book, accept an entered one

GET /book/default returns the pre-fill for the world's own sleeve set;
POST /sessions validates a submitted book/plan and demotes to practice when
either digest differs from the default. Both simulate_play calls - active and
twin - get the same book, so alpha still isolates decisions."
```

---

### Task 6: The lever measures deviation from your plan

**Files:**
- Modify: `src/ah/serve.py:291-294` and `src/ah/serve.py:333-348` (the pre-fill blocks in `_mark_to_market`)
- Test: `tests/test_serve_book.py` (append a class)

**Interfaces:**
- Consumes: Task 5's stored `commitment_plan`.
- Produces: session documents gain `plan_pace` (the pacing rule's view) alongside `next_plan_commitments` (now the player's plan, when one is stored).

**The scope fence (spec §4.3), which is the whole point of this task:** a session **without** a stored plan keeps `plan_commitments` and the audit-F4 staleness caveat verbatim. Only a plan-carrying session gets the exact per-year number. Do not "simplify" by applying the new path to both.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_serve_book.py
class TestPlanDrivenLever:
    """su-app-06 section 4.3, and its fence."""

    def test_a_session_without_a_plan_keeps_todays_behaviour(self, _client, _seeded_run):
        sid = _client.post("/sessions", json={"run_id": _seeded_run}).json()["session_id"]
        _client.post(f"/sessions/{sid}/advance", json={"to_month": 11})
        doc = _client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]  # recomputed from the reported weight
        assert doc["next_plan_basis"] is not None  # the F4 caveat still declared

    def test_a_plan_carrying_session_pre_fills_the_players_own_number(
        self, _client, _seeded_run
    ):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        plan = default["plan"]
        plan["points"]["pe"] = [5.0] * 10  # a deliberate, flat, non-default plan
        sid = _client.post("/sessions", json={
            "run_id": _seeded_run, "book": default["book"], "plan": plan,
        }).json()["session_id"]
        _client.post(f"/sessions/{sid}/advance", json={"to_month": 11})
        doc = _client.get(f"/sessions/{sid}").json()
        assert doc["next_plan_commitments"]["pe"] == pytest.approx(5.0)

    def test_the_pacing_rules_view_is_shown_beside_it_not_applied(
        self, _client, _seeded_run
    ):
        default = _client.get(f"/book/default?run_id={_seeded_run}").json()
        plan = default["plan"]
        plan["points"]["pe"] = [5.0] * 10
        sid = _client.post("/sessions", json={
            "run_id": _seeded_run, "book": default["book"], "plan": plan,
        }).json()["session_id"]
        _client.post(f"/sessions/{sid}/advance", json={"to_month": 11})
        doc = _client.get(f"/sessions/{sid}").json()
        assert doc["plan_pace"] is not None
        assert doc["plan_pace"]["pe"] != pytest.approx(5.0), (
            "the flex must be a displayed comparison, not the applied number"
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_serve_book.py -k PlanDrivenLever -q`
Expected: FAIL — `KeyError: 'plan_pace'`

- [ ] **Step 3: Write the implementation**

In `_mark_to_market`, add `"plan_pace"` to the list of keys nulled at the top, then after the existing `next_plan_commitments` assignment (`serve.py:333-336`) insert:

```python
        # su-app-06 section 4.3: with a stored plan the pre-fill is the
        # player's OWN number for this year - exact, so the audit-F4
        # staleness caveat does not apply - and the pacing rule's view rides
        # alongside as a comparison rather than acting as a silent default.
        # A session with no plan keeps today's behaviour verbatim.
        stored_plan = doc.get("commitment_plan")
        if stored_plan:
            plan = CommitmentPlan.model_validate_json(stored_plan)
            # Plan index = the DECISION WINDOW ordinal, not a calendar year.
            # Windows sit at quarters 2, 6, 10, ... (months 11, 23, 35, ...),
            # each driving the commitment at the next multiple of 4. At those
            # quarters `(q + 1) // 4` IS the window ordinal — verified: q=2 -> 0,
            # q=6 -> 1, q=34 -> 8. The clamp guards a non-decade horizon.
            year = min((here.quarter + 1) // 4, len(next(iter(plan.points.values()))) - 1)
            doc["plan_pace"] = doc["next_plan_commitments"]
            doc["next_plan_commitments"] = {
                sleeve: round(points[year], 4) for sleeve, points in plan.points.items()
            }
            doc["next_plan_basis"] = None  # nothing is being approximated
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_serve_book.py -q`
Expected: PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/serve.py tests/test_serve_book.py
git commit -m "feat(su-app-06): the lever pre-fills from the player's own plan

On a plan-carrying session the pre-fill is the player's exact number for the
year, so the audit-F4 staleness caveat no longer applies, and the policy
pacing flex becomes a displayed comparison (plan_pace) instead of a silent
default. Fenced: a session with no plan is untouched."
```

---

### Task 7: The entry screen

**Files:**
- Create: `app/src/BookEntry.tsx`, `app/src/BookEntry.test.tsx`
- Modify: `app/src/App.tsx:24` (the `Mode` union) and the mode switch, `app/src/lib/session.ts:145-152` (`createSession`)
- Modify: `app/src/styles.css` (append a `.book-entry` block)

**Interfaces:**
- Consumes: Task 5's `GET /book/default` payload.
- Produces: `BookEntry` component with props `{ runId: string; onReady: (book: Book, plan: Plan, isDefault: boolean) => void; onCancel: () => void }`; types `Book`, `Plan`, `DefaultBookResponse` exported from `app/src/lib/session.ts`.

- [ ] **Step 1: Write the failing test**

```tsx
// app/src/BookEntry.test.tsx
/**
 * The book entry screen (su-app-06).
 *
 * The screen validates SHAPE only. Every value that matters comes from the
 * server (DN-3 W5), so these tests assert on totals, sleeve names and the
 * ranked-availability statement - never on NAV, coverage or alpha.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { BookEntry } from "./BookEntry";

const DEFAULT_RESPONSE = {
  book: {
    state_version: "opening-book-0.1",
    liquid: { equity: 41, bonds: 12, hy: 5, commodities: 5 },
    private: {
      pe: [{ commitment: { committed: 4, paid_in: 2, unfunded: 2, recallable_balance: 0, cumulative_recycled: 0 }, value: { nav_true: 20, nav_reported: 20, cumulative_distributions: 0 }, identity: { vintage_year: 2019 } }],
      pc: [{ commitment: { committed: 1.6, paid_in: 0.8, unfunded: 0.8, recallable_balance: 0, cumulative_recycled: 0 }, value: { nav_true: 8, nav_reported: 8, cumulative_distributions: 0 }, identity: { vintage_year: 2019 } }],
      re: [{ commitment: { committed: 1.4, paid_in: 0.7, unfunded: 0.7, recallable_balance: 0, cumulative_recycled: 0 }, value: { nav_true: 7, nav_reported: 7, cumulative_distributions: 0 }, identity: { vintage_year: 2019 } }],
    },
    cash: 2,
  },
  plan: { state_version: "commitment-plan-0.1", points: { pe: [3.6], pc: [1.44], re: [1.26] } },
  liquid_sleeves: ["equity", "bonds", "hy", "commodities"],
  book_digest: "a".repeat(64),
  plan_digest: "b".repeat(64),
};

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(DEFAULT_RESPONSE) }),
  ) as unknown as typeof fetch;
});

describe("BookEntry", () => {
  it("opens pre-filled with the served default, never blank", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const equity = await screen.findByLabelText<HTMLInputElement>("equity");
    expect(equity.value).toBe("41");
  });

  it("shows the running total and reports 100 for the default", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(await screen.findByTestId("book-total")).toHaveTextContent("100");
  });

  it("blocks the commit when the total is not 100", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const equity = await screen.findByLabelText<HTMLInputElement>("equity");
    fireEvent.change(equity, { target: { value: "50" } });
    expect(await screen.findByTestId("book-total")).toHaveTextContent("109");
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
  });

  it("renders only the sleeves the world carries", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    await screen.findByLabelText("equity");
    expect(screen.queryByLabelText("reits")).toBeNull();
  });

  it("says ranked is available while the book is untouched", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(await screen.findByTestId("ranked-note")).toHaveTextContent(/ranked is available/i);
  });

  it("says ranked is lost once anything is edited", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const bonds = await screen.findByLabelText<HTMLInputElement>("bonds");
    fireEvent.change(bonds, { target: { value: "12.5" } });
    expect(await screen.findByTestId("ranked-note")).toHaveTextContent(/practice only/i);
  });

  it("restores a sleeve's ladder with reset", async () => {
    render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const nav = await screen.findByLabelText<HTMLInputElement>("pe rung 0 nav_true");
    fireEvent.change(nav, { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: /reset pe/i }));
    await waitFor(() =>
      expect(screen.getByLabelText<HTMLInputElement>("pe rung 0 nav_true").value).toBe("20"),
    );
  });

  it("hands back isDefault=true for an untouched book", async () => {
    const onReady = vi.fn();
    render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /continue/i }));
    await waitFor(() => expect(onReady).toHaveBeenCalled());
    expect(onReady.mock.calls[0][2]).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd app && npm run test -- --run BookEntry`
Expected: FAIL — cannot resolve `./BookEntry`.

- [ ] **Step 3: Write the implementation**

Create `app/src/BookEntry.tsx`. Requirements it must satisfy, all covered by the tests above:

- On mount, `GET /book/default?run_id=${runId}`; render nothing but a loading line until it resolves.
- One labelled number input per served liquid sleeve (`aria-label` = the sleeve name), plus `cash`.
- One table per private sleeve, one row per rung, seven inputs per row with `aria-label` of the form `` `${sleeve} rung ${i} ${field}` `` over `vintage_year`, `committed`, `paid_in`, `unfunded`, `nav_true`, `nav_reported`, `cumulative_distributions`. `recallable_balance` and `cumulative_recycled` are carried through untouched.
- A *reset {sleeve}* button per table restoring that sleeve's rungs from the served default.
- A `data-testid="book-total"` element showing `sum(liquid) + sum(rung nav_true) + cash`, rounded to 2dp.
- A `data-testid="ranked-note"` element reading "Ranked is available — this is the default book" while the state deep-equals the served default, and "Practice only — you have edited the book" otherwise.
- The plan grid: one row per year, one column per private sleeve, plus reset-to-default.
- *Continue* is disabled unless the total is 100 ± 0.01 and every input parses; on click it calls `onReady(book, plan, isDefault)`.
- **No value arithmetic beyond those sums.** No NAV projection, no coverage, no alpha — those come from the server.

Then in `app/src/App.tsx`, widen the mode union at line 24 and route into it:

```tsx
type Mode = "browse" | "book" | "setup" | "play";
```

`browse` → *Play this world* now enters `book`; `BookEntry.onReady` stores the book/plan in state and advances to `setup`; `RankedSetup` receives `bookIsDefault` and disables the ranked radio with the reason when it is false; `onStart` passes `book` and `plan` through to `createSession`.

And extend the client in `app/src/lib/session.ts`:

```ts
export interface Rung {
  identity: { vintage_year: number; [k: string]: unknown };
  commitment: {
    committed: number; paid_in: number; unfunded: number;
    recallable_balance: number; cumulative_recycled: number;
  };
  value: { nav_true: number; nav_reported: number; cumulative_distributions: number };
  [k: string]: unknown;
}

export interface Book {
  state_version: string;
  liquid: Record<string, number>;
  private: Record<string, Rung[]>;
  cash: number;
}

export interface Plan {
  state_version: string;
  points: Record<string, number[]>;
}

export interface DefaultBookResponse {
  book: Book;
  plan: Plan;
  liquid_sleeves: string[];
  book_digest: string;
  plan_digest: string;
}

export function getDefaultBook(runId: string): Promise<DefaultBookResponse> {
  return request(`/book/default?run_id=${encodeURIComponent(runId)}`);
}

export function createSession(body: {
  run_id: string;
  basis?: "reported" | "actual";
  ranked?: boolean;
  participant?: string;
  book?: Book;
  plan?: Plan;
}): Promise<Session> {
  return request("/sessions", { method: "POST", body: JSON.stringify(body) });
}
```

Append a `.book-entry` block to `app/src/styles.css` following the existing `.setup` / `.commit-lever` conventions — a scrollable table per sleeve, numeric inputs right-aligned, the total and the ranked note visually prominent.

- [ ] **Step 4: Run the app suite to verify it passes**

```bash
cd app && npm run typecheck && npm run test -- --run && npm run build
```
Expected: typecheck clean, all tests pass (77 existing + the 8 new), build succeeds.

- [ ] **Step 5: Commit**

```bash
git add app/src/BookEntry.tsx app/src/BookEntry.test.tsx app/src/App.tsx app/src/lib/session.ts app/src/styles.css
git commit -m "feat(su-app-06): the book entry screen

Opens pre-filled with the server's derived book for the world's own sleeve
set, never blank; per-sleeve ladder tables with reset; the plan grid; and a
standing statement of whether ranked is still available. Shape validation
only - every number that matters still comes from the server."
```

---

### Task 8: ER-14, the changelog, and the gate

**Files:**
- Modify: `docs/engine-realism-register.md`, `CHANGELOG.md`, `CLAUDE.md` (the ER list in the working-conventions section)

- [ ] **Step 1: Add ER-14 to the register**

Append, following the existing entry format (each entry says what a fix invalidates):

```markdown
### ER-14 — an entered opening book can sit outside the fitted ladder shape

**Status: OPEN** (opened 2026-08-15, su-app-06)

`_seed_ladder` derives the opening private book as a staggered ten-rung
staircase warmed forward at a single rate, and that shape is what the pacing
model, the call/distribution linkage and the ER-6 close-out were checked
against. An ENTERED book can be arbitrarily far from it — one enormous
vintage, a five-year gap, a sleeve entirely in its harvest years.

It can also open in a state the derived book can never reach:
`nav_reported != nav_true` at t0, i.e. an appraisal filter that starts
un-converged. The seeded ladder converges by construction
(`cohort.report(cohort.nav_true)` at the end of warm-up), so no calibration
evidence covers the un-converged opening.

Nothing downstream is wrong — the waterfall, the filter and the linkage all
run as specified on whatever book they are given. What does not extend is the
*evidence*: the sealed pacing figures were fitted on the seeded shape.

**A fix invalidates:** re-fitting pacing and linkage across a family of ladder
shapes would move the sealed pacing figures in DN-5 §2.1, which is an
amendment-log event and an owner decision, not a cleanup.

**Mitigation in place:** a custom book is practice-only, so nothing scored on
the leaderboard is produced from an unfitted ladder.
```

- [ ] **Step 2: Update `CHANGELOG.md` and `CLAUDE.md`**

Add a `CHANGELOG.md` entry naming the contract, the endpoint, the practice-only rule and ER-14. Add ER-14 to the open list in `CLAUDE.md`'s engine-realism-register paragraph.

- [ ] **Step 3: Full-tree lint and types BEFORE the long gate**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
```
Both must be clean. Stragglers found mid-gate cost a restart of the whole ~38 minutes.

- [ ] **Step 4: Run the gate**

```bash
uv run python scripts/run_gate.py gate-su-app-06.log
```
Run it in the background and read the log as data. Check the `EXIT:` line and the pass count before claiming anything — never chain a merge onto a `tail`.

- [ ] **Step 5: Commit and stop**

```bash
git add docs/engine-realism-register.md CHANGELOG.md CLAUDE.md gate-su-app-06.log
git commit -m "docs(su-app-06): ER-14, changelog, gate log

ER-14: an entered ladder can sit arbitrarily far from the shape the pacing
model and the linkage were fitted on, and can open with an un-converged
appraisal filter. Mitigated by the practice-only rule, not fixed."
```

**Do not merge.** Re-verify HEAD, run `uv run python scripts/check_gate.py gate-su-app-06.log` on the branch, and hand back to the owner — the owner commits onto branches mid-gate, and `.gate-ok` binds exactly one commit.

---

## Self-Review

**Spec coverage:** §3 contract → Task 1; §3.1 sleeve set → Tasks 1, 2, 5, 7; §4.1 override → Task 3; §4.2 twin → Task 5; §4.3 plan/flex → Task 6; §5 server and storage → Tasks 4, 5; §6 screen → Task 7; §7 guardrails → Tasks 1, 5; §7 ER-14 → Task 8; §8 tests 1–8 → Tasks 1, 3, 5, 6, 7; §9 WPs → Tasks 1–8; §10 out of scope → untouched, and the flat-plan rationale is recorded in `default_commitment_plan`'s docstring.

**Known gap, deliberate:** spec §8 test 6 asks for a service-restart replay check. `test_a_session_with_a_stored_book_replays_it` (Task 5) covers the stored-book read path through a fresh request but not a genuine process restart; the store round-trip in Task 4 covers persistence. A true restart test would need a fixture the suite does not have. If the executor finds one, add it; do not fake it.

**Type consistency:** `OpeningBook.cohorts()` (Task 1) is called in Task 3's `_build_portfolio`. `default_opening_book` / `default_commitment_plan` (Task 2) are called in Task 5's `_world_book`. `validate_book(book, liquid_sleeves=...)` keyword matches across Tasks 1, 2, 5. `Book` / `Plan` TS types (Task 7) mirror the Python `model_dump()` shape from Task 1. `plan_pace` (Task 6) is a new session key, not a rename of `next_plan_commitments`.
