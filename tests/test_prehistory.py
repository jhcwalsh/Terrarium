"""cio-04: the inherited decade that renders before a world's month 0.

Display-only by ruling (see the plan and DN-8's O-1 resolution): the opening
book is unchanged, and the pre-history is pinned to terminate at it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.validator import validate
from ah.prehistory import PREHISTORY_QUARTERS, build_prehistory

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _doc(name: str) -> dict[str, Any]:
    return json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))


def test_prehistory_preset_passes_the_v_rules():
    """DN-8 O-1's stated cost of option A: an unvalidated pre-history would be
    an unvalidated artefact sitting inside a validated product.

    The interface this WP promises (task-1-brief.md) is a document that
    "loads, validates (V1-V12), and projects" -- so all three are exercised
    here rather than just the V-rules: ``load_worldspec`` runs the JSON
    Schema and pydantic construction, ``validate`` runs V1-V12 against the
    raw document (its real signature takes ``dict``, not a ``WorldSpec``),
    and ``project_numeric`` proves the loaded spec turns into an engine-ready
    ``NumericWorld``.
    """
    doc = _doc("prehistory")
    spec = load_worldspec(doc)  # schema + pydantic: proves it *loads*
    report = validate(doc)  # V1-V12 against the raw document
    assert report.ok, [f.message for f in report.blocking]
    project_numeric(spec)  # proves it *projects*


def test_prehistory_preset_is_a_decade_and_is_calm():
    doc = _doc("prehistory")
    assert doc["horizon"]["quarters"] == 40
    # no crisis windows: the inherited past is unremarkable by construction,
    # so the decade the player actually plays is the one with the weather in
    # it. Crisis windows live at factor_conditions.crisis_windows in this
    # schema (there is no top-level "stress" field) -- checked there so the
    # assertion is actually load-bearing rather than vacuously true.
    assert not doc.get("factor_conditions", {}).get("crisis_windows"), (
        "the inherited decade carries no crisis"
    )


def test_prehistory_is_deterministic_and_terminates_at_the_opening_book():
    a = build_prehistory(771204, 100.0, 98.0)
    b = build_prehistory(771204, 100.0, 98.0)
    assert a == b
    assert a.months == PREHISTORY_QUARTERS * 3
    assert abs(a.nav_true_months[-1] - 100.0) < 1e-9
    assert abs(a.nav_reported_months[-1] - 98.0) < 1e-9
    assert len(a.quarterly_returns_true) == PREHISTORY_QUARTERS


def test_prehistory_differs_by_seed():
    a = build_prehistory(771204, 100.0, 98.0)
    b = build_prehistory(19740101, 100.0, 98.0)
    assert a.nav_true_months != b.nav_true_months


def test_prehistory_market_paths_are_monthly_and_complete():
    p = build_prehistory(771204, 100.0, 98.0)
    assert p.market_paths, "no market series"
    for series in p.market_paths.values():
        assert len(series) == p.months


def test_prehistory_returns_are_not_degenerate():
    """The validator flags an exact zero in a return column as a possible
    unreached period; a flat pre-history would manufacture those. Checked on
    BOTH planes: the CIO view defaults to REPORTED (cioview.py:203), which is
    what the validator's exact-zero check will actually see in practice, not
    just the true plane.

    Scope, stated: this guards the realistic failure mode -- a flat or
    degenerate pre-history manufacturing exact-zero quarters -- not the
    validator's literal condition. The validator's own check runs on
    ``performance.total``, an aggregated/annualised period return; this
    module computes and exports raw quarterly returns, a different
    (related but not identical) quantity.
    """
    p = build_prehistory(771204, 100.0, 98.0)
    assert len({round(r, 6) for r in p.quarterly_returns_true}) > 20
    assert all(r != 0.0 for r in p.quarterly_returns_true)
    assert len({round(r, 6) for r in p.quarterly_returns_reported}) > 20
    assert all(r != 0.0 for r in p.quarterly_returns_reported)


def test_prehistory_returns_are_scale_invariant():
    """Scaling is level-only: quarterly returns come off the UNSCALED replay,
    so they must be identical regardless of the terminal NAVs used to pin the
    endpoint (a hard constraint of this WP's safety argument)."""
    a = build_prehistory(771204, 100.0, 98.0)
    b = build_prehistory(771204, 250.0, 40.0)
    assert a.quarterly_returns_true == b.quarterly_returns_true
    assert a.quarterly_returns_reported == b.quarterly_returns_reported


def _boundary_returns(months: tuple[float, ...], n_quarters: int) -> tuple[float, ...]:
    """Ratios between successive quarter-boundary marks in an EXPORTED
    (already scaled) monthly NAV series.

    Scale-invariant by construction -- a constant multiplier applied to
    every level cancels in any ratio of two levels -- so this can compare
    directly against ``quarterly_returns_{true,reported}`` regardless of
    which terminal NAVs were used to build the ``PreHistory``.
    """
    closes = [months[q * 3 + 2] for q in range(n_quarters)]
    return tuple(closes[i + 1] / closes[i] - 1.0 for i in range(n_quarters - 1))


def test_prehistory_exported_months_reproduce_quarterly_returns():
    """Pins an identity that is currently true only by accident of
    ``play.py``'s implementation: ``PlayQuarter.nav_true_months[2]`` and
    ``PlayQuarter.nav_true`` are the same ``portfolio.nav_true()`` call
    (src/ah/play.py:699 and :711) -- same for the reported pair. Nothing in
    ``simulate_play``'s contract guarantees that stays true. If a future
    change sampled the month-2 mark before the quarter's waterfall ran,
    Task 3's chart (built from ``nav_*_months``) and its printed return
    columns (built from ``quarterly_returns_*``) would silently disagree,
    while ``test_prehistory_returns_are_scale_invariant`` -- which never
    reads ``nav_*_months`` at all -- would stay green.

    Quarter 0 is excluded: its return needs a pre-quarter-0 opening level,
    which is not part of the exported months array (by design -- the array
    starts at month 0 of the pre-history, not before it).
    """
    p = build_prehistory(771204, 100.0, 98.0)
    n = PREHISTORY_QUARTERS
    boundary_true = _boundary_returns(p.nav_true_months, n)
    boundary_reported = _boundary_returns(p.nav_reported_months, n)
    for got, want in zip(boundary_true, p.quarterly_returns_true[1:], strict=True):
        assert abs(got - want) < 1e-12
    for got, want in zip(boundary_reported, p.quarterly_returns_reported[1:], strict=True):
        assert abs(got - want) < 1e-12


def test_prehistory_rejects_degenerate_terminal_values():
    with pytest.raises(ValueError):
        build_prehistory(771204, 0.0, 98.0)
    with pytest.raises(ValueError):
        build_prehistory(771204, 100.0, float("nan"))
    with pytest.raises(ValueError):
        build_prehistory(771204, float("inf"), 98.0)
