"""The section renders, is self-contained, and states its frozen parameters."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.programme import _model_curves, model_block

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


def test_model_block_prints_the_frozen_linkage_parameters():
    html = model_block()
    # the values a reader must be able to check against mappings/
    assert "1.540688" in html  # f_dist a_drawdown
    assert "1.376940" in html  # f_dist b_log_spread
    assert "0.1" in html  # f_call c
    assert "2.5" in html  # bow B
    assert "0.55" in html  # yield_rate Y


def test_model_block_states_the_asymmetry_it_exists_to_show():
    html = model_block().lower()
    assert "f_call" in html and "f_dist" in html
    assert "continuous" in html, "the no-regime-label claim must be on the page"


def test_model_block_is_self_contained():
    html = model_block()
    for forbidden in ("http://", "https://", "<script", "src="):
        assert forbidden not in html, f"the page must not reference {forbidden}"


def test_model_block_is_deterministic():
    assert model_block() == model_block()


# ---------------------------------------------------------------------------
# The curve VALUES, pinned directly -- substring assertions on the rendered
# HTML (above) cannot catch a swapped parameter, a flipped sign, a mis-indexed
# rc_curve, or a dropped age/life clamp on the bow. These can.


def test_model_curves_call_rate_matches_frozen_rc_curve():
    # rc_curve straight from fixtures/state/closed-end-cohort.example.json:
    # [0.25, 0.3, 0.2, 0.12, 0.08, 0.05]
    curves = _model_curves()
    assert curves["call_rate"][0] == 0.25
    assert curves["call_rate"][5] == 0.05


def test_model_curves_bow_reaches_yield_rate_at_terminal_age():
    # Y(age/L)^B at age == L: min(1.0, L/L) ** B == 1, so the curve's
    # terminal value is exactly Y (yield_rate = 0.55) -- the plateau
    # src/ah/port/cohort.py's step docstring claims.
    curves = _model_curves()
    assert curves["bow"][-1] == 0.55


def test_model_curves_f_dist_matches_frozen_linkage():
    # dd == 0.0 -> exp(0) == 1.0, inside [floor, ceiling], unclipped.
    # dd == 0.5 (index 20 of 41, since _DD_DOMAIN steps by 1/40) ->
    # exp(-1.540688 * 0.5) = exp(-0.770344) ~= 0.462869..., inside
    # [0.3, 1.5] so unclipped -- computed directly from the frozen a_drawdown.
    curves = _model_curves()
    assert curves["f_dist"][0] == 1.0
    expected_at_half_drawdown = math.exp(-1.540688 * 0.5)
    assert curves["f_dist"][20] == pytest.approx(expected_at_half_drawdown)


def test_model_curves_f_call_matches_frozen_linkage_and_respects_clip_bounds():
    # dd == 1.0 -> 1.0 - 0.1 * 1.0 == 0.9, inside [0.5, 1.2], unclipped.
    curves = _model_curves()
    assert curves["f_call"][-1] == pytest.approx(0.9)
    # the clip floor (0.5) and ceiling (1.2) are never breached over the domain
    assert all(0.5 <= v <= 1.2 for v in curves["f_call"])


def test_model_curves_f_call_span_is_narrower_than_f_dist_span():
    # The asymmetry the section exists to show, as a number rather than prose:
    # f_call moves ~10% over the plotted domain (1.0 -> 0.9), f_dist moves
    # ~70% (1.0 -> its 0.3 floor). f_call's span must stay materially
    # narrower -- this is what "f_call is clipped near-flat while f_dist can
    # fall to its floor" means, made falsifiable.
    curves = _model_curves()
    fc_span = max(curves["f_call"]) - min(curves["f_call"])
    fd_span = max(curves["f_dist"]) - min(curves["f_dist"])
    assert fc_span < fd_span * 0.5
