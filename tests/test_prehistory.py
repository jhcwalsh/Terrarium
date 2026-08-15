"""cio-04: the inherited decade that renders before a world's month 0.

Display-only by ruling (see the plan and DN-8's O-1 resolution): the opening
book is unchanged, and the pre-history is pinned to terminate at it.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

import pytest

from ah.cioview import _quarterly_returns as cioview_quarterly_returns
from ah.cioview import build_cio_view, validate_cio_view
from ah.core.engine import run_path
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.validator import validate
from ah.play import simulate_play
from ah.prehistory import PREHISTORY_QUARTERS, _prehistory_paths, build_prehistory

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


def test_prehistory_exported_months_reproduce_the_replay_nav():
    """Pins an identity that is currently true only by accident of
    ``play.py``'s implementation: ``PlayQuarter.nav_true_months[2]`` and
    ``PlayQuarter.nav_true`` are the same ``portfolio.nav_true()`` call
    (src/ah/play.py:699 and :711) -- same for the reported pair. Nothing in
    ``simulate_play``'s contract guarantees that stays true. If a future
    change sampled the month-2 mark before the quarter's waterfall ran,
    Task 3's chart (built from ``nav_*_months``) and the return convention's
    own inputs (``q.nav_true``/``q.nav_reported``, read directly off the
    replay by ``build_prehistory``) would silently disagree.

    Recomputes the replay directly (white-box: ``_prehistory_paths`` is
    private) rather than inverting the exported, ALREADY-SCALED month array
    back into a per-quarter ratio the way this test used to: C1 folded each
    quarter's payout into the return numerator, which is additive and does
    not survive a level-only rescale the way a bare ratio does, so a scaled
    boundary value can no longer stand in for the unscaled one. The return
    convention itself is pinned separately, below.
    """
    seed = 771204
    p = build_prehistory(seed, 100.0, 98.0)
    paths = _prehistory_paths(seed)
    result = simulate_play(paths, None)
    scale_true = p.nav_true_months[-1] / result.quarters[-1].nav_true
    scale_reported = p.nav_reported_months[-1] / result.quarters[-1].nav_reported
    for q_idx, q in enumerate(result.quarters):
        month_idx = q_idx * 3 + 2
        assert abs(p.nav_true_months[month_idx] - q.nav_true * scale_true) < 1e-6
        assert abs(p.nav_reported_months[month_idx] - q.nav_reported * scale_reported) < 1e-6


def test_prehistory_returns_use_the_payout_added_back_convention():
    """C1 (Critical, whole-branch review): the two halves of every long
    return window must use the SAME return convention.
    ``ah.cioview._quarterly_returns`` adds a quarter's ``spending_paid`` back
    to its closing level before taking the ratio (``performance.footnote``:
    "Payout added back; time-weighted") -- the inherited decade is replayed
    hold-course under the same default policy spend as any other quarter, so
    leaving the add-back out of ``prehistory._quarterly_returns`` silently
    switched conventions mid-window the instant an inherited quarter sat
    beside a world quarter in one annualised figure. Reviewer-measured
    impact before this fix: the fixture's 10Y Total plan read a sign-flipped
    -0.9729% (reported plane) instead of the correct +1.2267%, at stagflation
    seed 771204 -- this test's own case.

    Computed a known case BOTH ways: once via ``build_prehistory`` (the
    shipped path) and once via ``ah.cioview._quarterly_returns`` fed the
    identical, unscaled replay directly -- the two must agree exactly, since
    they are meant to be the same formula, not merely close.
    """
    seed = 771204
    p = build_prehistory(seed, 100.0, 98.0)
    paths = _prehistory_paths(seed)
    result = simulate_play(paths, None)
    n = PREHISTORY_QUARTERS
    assert list(p.quarterly_returns_true) == cioview_quarterly_returns(result, "true", n)
    assert list(p.quarterly_returns_reported) == cioview_quarterly_returns(result, "reported", n)
    # Every quarter pays a spend under the default policy, so the add-back
    # is not a no-op here -- if it ever became one, the assertions above
    # would stop proving the convention actually matters.
    assert all(q.spending_paid > 0 for q in result.quarters)


def test_prehistory_rejects_degenerate_terminal_values():
    with pytest.raises(ValueError):
        build_prehistory(771204, 0.0, 98.0)
    with pytest.raises(ValueError):
        build_prehistory(771204, 100.0, float("nan"))
    with pytest.raises(ValueError):
        build_prehistory(771204, float("inf"), 98.0)


# --- Task 3: the inherited decade landing on build_cio_view's payload -----


def _paths(preset: str = "stagflation"):
    doc = _doc(preset)
    spec = load_worldspec(doc)
    nw = project_numeric(spec)
    return run_path(nw, doc["engine_defaults"]["base_seed"])


def _view(
    *,
    prehistory: bool,
    revealed: int,
    plane: str = "reported",
    fq: int = 4,
    preset: str = "stagflation",
) -> dict[str, Any]:
    return build_cio_view(
        _paths(preset),
        {},
        run_id="r-test",
        seed=42,
        world_title="Stagflation",
        world_version="toy-v0.6",
        alpha_version="port-v4-ladder",
        start_targets=None,
        plane=plane,
        revealed_months=revealed,
        forecast_quarters=fq,
        prehistory=prehistory,
    )


def test_view_with_prehistory_validates_and_fills_the_long_columns():
    v = _view(prehistory=True, revealed=12)  # one year into the world
    assert validate_cio_view(v) == []
    h = v["plan"]["history"]
    assert h["worldStartIndex"] == PREHISTORY_QUARTERS * 3
    assert len(h["values"]) == h["worldStartIndex"] + 12
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    for period in ("3Y", "5Y", "10Y"):
        assert v["performance"]["total"][idx[period]] is not None, period


def test_prehistory_is_continuous_at_the_world_boundary():
    """No step at month 0: the inherited path terminates on the opening book."""
    v = _view(prehistory=True, revealed=12)
    values = v["plan"]["history"]["values"]
    i = v["plan"]["history"]["worldStartIndex"]
    joint = abs(values[i] / values[i - 1] - 1.0)
    typical = median(abs(values[k] / values[k - 1] - 1.0) for k in range(1, i))
    assert joint < 5 * typical, "visible discontinuity at the world boundary"


def test_market_paths_stay_coupled_to_plan_history():
    v = _view(prehistory=True, revealed=12)
    n = len(v["plan"]["history"]["values"])
    for s in v["markets"]["returns"]:
        assert len(s["path"]) == n


def test_prehistory_off_reproduces_the_old_shape():
    v = _view(prehistory=False, revealed=60)
    assert v["plan"]["history"]["worldStartIndex"] == 0
    assert len(v["plan"]["history"]["values"]) == 60
    # Minor 1 (whole-branch review): no test called validate_cio_view with
    # prehistory=False, so the off-path lost its validator coverage.
    assert validate_cio_view(v) == []
