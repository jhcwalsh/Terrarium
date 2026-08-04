"""The pacing ledger: does the money add up, and does it stay display-only?

Two families of test. The first is bookkeeping — a commitment is drawn down
by its calls and nothing else, NAV is what has been called plus growth minus
what has come back, and DPI/TVPI mean what those letters mean. The second is
the boundary: this ledger must not be able to touch scoring, because the
engine has no cash account and pretending otherwise would mislead a player
(register ER-3).
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest

from ah.core.engine import REPORTED_SLEEVES, run_path
from ah.core.institution import START_MIX
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.pacing import (
    CALL_RATE_EARLY,
    COMMITMENT_MULTIPLE,
    DISTRIBUTION_RATE,
    J_CURVE_QUARTERS,
    build_ledgers,
)

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "src" / "ah" / "presets" / "stagflation.json"
SEED = 771204


def _paths(quarters: int | None = None):
    doc: dict[str, Any] = json.loads(PRESET.read_text(encoding="utf-8"))
    if quarters is not None:
        doc = copy.deepcopy(doc)
        doc["horizon"]["quarters"] = quarters
    return run_path(project_numeric(WorldSpec.model_validate(doc)), SEED)


@pytest.fixture(scope="module")
def ledgers():
    return build_ledgers(_paths())


class TestShape:
    def test_one_ledger_per_private_asset(self, ledgers):
        assert set(ledgers) == set(REPORTED_SLEEVES)

    def test_rows_line_up_with_quarter_ends(self, ledgers):
        p = _paths()
        expected = [m for m in range(p.months) if (m + 1) % 3 == 0]
        for led in ledgers.values():
            assert led.quarter_months == expected
            for series in (led.called, led.distributed, led.unfunded, led.nav, led.dpi, led.tvpi):
                assert len(series) == len(expected)

    def test_commitment_is_the_over_committed_target(self, ledgers):
        for asset, led in ledgers.items():
            assert led.commitment == pytest.approx(START_MIX[asset] * 100.0 * COMMITMENT_MULTIPLE)


class TestBookkeeping:
    def test_unfunded_only_falls_and_calls_account_for_it(self, ledgers):
        for led in ledgers.values():
            prev = led.commitment
            for q, u in enumerate(led.unfunded):
                assert u <= prev + 1e-9, "unfunded cannot grow — nothing re-commits"
                assert prev - u == pytest.approx(led.called[q], abs=1e-6)
                prev = u
            assert prev > 0.0, "a fixed fraction of the remainder never fully draws"

    def test_first_call_is_the_declared_fraction_of_the_commitment(self, ledgers):
        for led in ledgers.values():
            assert led.called[0] == pytest.approx(led.commitment * CALL_RATE_EARLY, abs=1e-6)

    def test_nothing_comes_back_before_the_j_curve_turns(self, ledgers):
        for led in ledgers.values():
            assert all(d == 0.0 for d in led.distributed[:J_CURVE_QUARTERS])
            assert any(d > 0.0 for d in led.distributed[J_CURVE_QUARTERS:])

    def test_distribution_is_the_declared_fraction_of_nav(self, ledgers):
        for led in ledgers.values():
            q = J_CURVE_QUARTERS
            # NAV is reported net of the distribution, so gross it back up
            gross = led.nav[q] / (1.0 - DISTRIBUTION_RATE)
            assert led.distributed[q] == pytest.approx(gross * DISTRIBUTION_RATE, rel=1e-6)

    def test_dpi_and_tvpi_mean_what_they_say(self, ledgers):
        for led in ledgers.values():
            cum_called = 0.0
            cum_dist = 0.0
            for q in range(len(led.called)):
                cum_called += led.called[q]
                cum_dist += led.distributed[q]
                assert led.dpi[q] == pytest.approx(cum_dist / cum_called, abs=1e-5)
                assert led.tvpi[q] == pytest.approx((led.nav[q] + cum_dist) / cum_called, abs=1e-5)

    def test_dpi_starts_at_zero_and_never_falls(self, ledgers):
        for led in ledgers.values():
            assert led.dpi[0] == 0.0
            assert all(b >= a - 1e-9 for a, b in zip(led.dpi, led.dpi[1:], strict=False))

    def test_every_number_is_finite(self, ledgers):
        for led in ledgers.values():
            for series in (led.called, led.distributed, led.unfunded, led.nav, led.dpi, led.tvpi):
                assert all(math.isfinite(v) for v in series)


class TestDeterminismAndBoundary:
    def test_same_tape_same_ledger(self):
        a = build_ledgers(_paths(8))
        b = build_ledgers(_paths(8))
        assert a == b

    def test_ledger_cannot_reach_the_institution_or_the_store(self):
        """Display-only, enforced structurally: the module may read START_MIX
        and the engine's types, but it must not import the simulator or any
        store, so there is no path by which a call could move a portfolio."""
        import ast

        import ah.pacing as pacing

        tree = ast.parse(Path(pacing.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(m.startswith("ah.store") for m in imported), imported
        assert "ah.serve" not in imported

    def test_scoring_is_untouched_by_the_ledger(self):
        """The institution simulation must produce the same value whether or
        not anyone has built a ledger — the ledger is read, never applied."""
        from ah.core.institution import hold_course_twin

        doc: dict[str, Any] = json.loads(PRESET.read_text(encoding="utf-8"))
        world = project_numeric(WorldSpec.model_validate(doc))
        before = hold_course_twin(world, SEED).final_value
        build_ledgers(run_path(world, SEED))
        after = hold_course_twin(world, SEED).final_value
        assert before == after
