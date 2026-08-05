"""The section renders, is self-contained, and states its frozen parameters."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.programme import (
    _model_curves,
    build_programme_report,
    model_block,
    render_programme_section,
)

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


# ---------------------------------------------------------------------------
# Task 5: the per-world blocks -- ladder, linkage, liquidity, flags, and the
# report builder that runs the ensemble.
#
# _world and PRESETS are already defined at the top of this file (Task 4).


@pytest.fixture(scope="module")
def report():
    return build_programme_report(_world("stagflation"), base_seed=771204, n_paths=4)


def test_report_covers_the_decade(report):
    assert len(report.quarters) == 40
    assert len(report.ladder) == 10


def test_section_shows_the_linkage_counterfactual(report):
    html = render_programme_section([report])
    assert "linkage off" in html.lower()
    assert "drawdown" in html.lower()
    assert "spread ratio" in html.lower()


def test_section_lists_forced_sales_with_their_cause(report):
    html = render_programme_section([report])
    # every logged sale's cause string must reach the page verbatim
    for sale in report.forced_sales:
        assert str(sale["cause"]) in html


def test_section_is_deterministic_for_a_fixed_world_and_seed():
    a = build_programme_report(_world("goldilocks"), base_seed=771204, n_paths=4)
    b = build_programme_report(_world("goldilocks"), base_seed=771204, n_paths=4)
    assert render_programme_section([a]) == render_programme_section([b])


@pytest.mark.parametrize("name", ["stagflation", "goldilocks", "deflation_bust", "reflation_boom"])
def test_every_preset_renders(name):
    rep = build_programme_report(_world(name), base_seed=771204, n_paths=2)
    assert render_programme_section([rep])


# ---------------------------------------------------------------------------
# Carry-forward #1: infinite coverage (NAV <= 0) must render as a clear
# marker, never the literal string "inf" -- and max() over quarters must not
# choke when several of them are infinite.


def test_liquidity_block_renders_wiped_coverage_not_the_string_inf():
    from ah.programme import ProgrammeQuarter, ProgrammeReport, _liquidity_block

    wiped = ProgrammeQuarter(
        quarter=0,
        month=2,
        drawdown_depth=0.5,
        spread_ratio=1.0,
        f_dist=0.5,
        f_call=1.0,
        calls=1.0,
        distributions=0.0,
        distributions_unlinked=0.0,
        cash=0.0,
        nav_true=0.0,
        nav_reported=0.0,
        private_nav=0.0,
        unfunded=5.0,
        private_weight_true=0.0,
        coverage_true=float("inf"),
        coverage_reported=float("inf"),
        forced_sale_total=0.0,
    )
    rep = ProgrammeReport(
        world_id="test",
        title="test",
        quarters=[wiped],
        ladder=[],
        stats=[],
        vintage_stack=[],
        forced_sales=[],
    )
    html = _liquidity_block(rep)
    assert "inf" not in html.lower()
    assert "wiped" in html.lower()


def test_liquidity_block_worst_quarter_selection_survives_multiple_infinities():
    from ah.programme import ProgrammeQuarter, ProgrammeReport, _liquidity_block

    def q(n: int, cov: float) -> ProgrammeQuarter:
        return ProgrammeQuarter(
            quarter=n,
            month=n * 3 + 2,
            drawdown_depth=0.0,
            spread_ratio=1.0,
            f_dist=1.0,
            f_call=1.0,
            calls=0.0,
            distributions=0.0,
            distributions_unlinked=0.0,
            cash=1.0,
            nav_true=1.0,
            nav_reported=1.0,
            private_nav=0.0,
            unfunded=0.0,
            private_weight_true=0.0,
            coverage_true=cov,
            coverage_reported=cov,
            forced_sale_total=0.0,
        )

    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[q(0, 0.2), q(1, float("inf")), q(2, float("inf")), q(3, 0.5)],
        ladder=[],
        stats=[],
        vintage_stack=[],
        forced_sales=[],
    )
    # must not raise (a naive .format() on inf is fine, but a comparison bug
    # would be), and must land on one of the infinite quarters -- Python's
    # max() returns the FIRST value achieving the maximum on ties, so this
    # pins the result to quarter 1 rather than leaving it unspecified.
    html = _liquidity_block(rep)
    assert "quarter 1)" in html


# ---------------------------------------------------------------------------
# Carry-forward #2: a statistic present on only some paths must say so, not
# silently report a median over a possibly-unrepresentative subset.


def test_programme_stats_reports_how_many_paths_a_statistic_came_from():
    from ah.programme import PROGRAMME_PLAUSIBLE, programme_stats

    name = next(iter(PROGRAMME_PLAUSIBLE))
    # present on 2 of 4 paths -- the other two couldn't compute it at all
    per_path = [{name: 0.5}, {name: 0.7}, {}, {}]
    stats = programme_stats(per_path, {name: 0.5})
    stat = next(s for s in stats if s.name == name)
    assert stat.n_present == 2
    assert stat.n_total == 4


def test_stats_table_shows_the_present_count(report):
    html = render_programme_section([report])
    assert " of 4" in html


# ---------------------------------------------------------------------------
# Review round 1, C1: the linkage table's directional column must agree in
# SIGN with path_stats.linkage_shortfall ((unlinked - linked) / unlinked),
# and its CSS class must follow the value's sign, not a hardcoded 'neg'.
# f_dist's ceiling (1.5, mappings/cashflow-tier1-v1.0.yaml) means the
# linkage routinely RAISES distributions -- the old
# "distributions - distributions_unlinked" rendered unconditionally red
# under a "shortfall" header painted that benefit as harm.


def _q(**overrides):
    from ah.programme import ProgrammeQuarter

    fields = {
        "quarter": 0,
        "month": 2,
        "drawdown_depth": 0.0,
        "spread_ratio": 1.0,
        "f_dist": 1.0,
        "f_call": 1.0,
        "calls": 0.0,
        "distributions": 0.0,
        "distributions_unlinked": 0.0,
        "cash": 0.0,
        "nav_true": 0.0,
        "nav_reported": 0.0,
        "private_nav": 0.0,
        "unfunded": 0.0,
        "private_weight_true": 0.0,
        "coverage_true": 0.0,
        "coverage_reported": 0.0,
        "forced_sale_total": 0.0,
    }
    fields.update(overrides)
    return ProgrammeQuarter(**fields)


def test_linkage_effect_sign_matches_linkage_shortfall_convention():
    from ah.programme import _linkage_effect

    # the linkage HELPED this quarter (f_dist's ceiling let it raise
    # distributions above the unlinked counterfactual) -- must be NEGATIVE,
    # matching linkage_shortfall's (unlinked - linked) / unlinked sign.
    helped = _q(distributions=12.0, distributions_unlinked=8.0)
    assert _linkage_effect(helped) == -4.0

    # the linkage HURT this quarter -- must be POSITIVE.
    hurt = _q(distributions=3.0, distributions_unlinked=10.0)
    assert _linkage_effect(hurt) == 7.0


def test_linkage_table_css_class_follows_the_effect_sign_not_a_constant():
    from ah.programme import ProgrammeReport, _linkage_table

    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[
            _q(quarter=0, distributions=12.0, distributions_unlinked=8.0),  # helped
            _q(quarter=1, month=5, distributions=3.0, distributions_unlinked=10.0),  # hurt
        ],
        ladder=[],
        stats=[],
        vintage_stack=[],
        forced_sales=[],
    )
    html = _linkage_table(rep)
    assert "class='pos'>-4.00</td>" in html
    assert "class='neg'>7.00</td>" in html
    assert "shortfall" not in html.split("<p class='note'>")[0].lower()  # not the header
    assert "unlinked minus linked" in html.lower()


# ---------------------------------------------------------------------------
# Review round 1, C2: the "alive" count must be cohorts with a positive
# final NAV, not every cohort id that ever appeared -- play.py logs a
# vintage_nav entry every quarter a cohort's ladder exists in, including
# quarters after it has been fully liquidated.


def test_stack_block_counts_only_cohorts_with_positive_final_nav():
    from ah.programme import ProgrammeReport, _stack_block

    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[],
        ladder=[],
        stats=[],
        vintage_stack=[
            ("opener-a", [10.0, 5.0, 0.0, 0.0]),  # liquidated before the end
            ("opener-b", [8.0, 6.0, 3.0, 4.0]),  # still alive
        ],
        forced_sales=[],
    )
    html = _stack_block(rep)
    assert "1 of 2" in html


# ---------------------------------------------------------------------------
# Review round 1, I1: the sale log's period (PortfolioEngine._period,
# src/ah/port/engine.py:75,90 -- 1-based, incremented at the top of
# run_quarter) must be converted to the page's 0-based quarter convention
# (PlayQuarter.quarter/ProgrammeQuarter.quarter) before display.


def test_sale_row_converts_the_1based_period_to_the_pages_0based_quarter():
    from ah.programme import _sale_row

    # PortfolioEngine logs period=1 for its FIRST quarter, which is quarter
    # 0 everywhere else on the page.
    sale = {
        "period": 1,
        "amount": 5.0,
        "cause": "x",
        "kind": "liquid_pro_rata",
        "sleeves_sold": [],
    }
    html = _sale_row(sale)
    assert "<td>Q0</td>" in html
    assert "<td>Q1</td>" not in html


# ---------------------------------------------------------------------------
# Review round 1, I2: no test constrained any COLUMN mapping -- the reviewer
# proved this by mutation (swapping f_dist/f_call in the linkage table, and
# called_to_date/unfunded_end in the ladder table, left every existing test
# green). These pin cell ORDER with all-distinguishable values, so a swap
# breaks them -- verified locally by making both swaps and confirming these
# two fail, then reverting (see the task report).


def test_ladder_table_columns_are_not_swapped():
    from ah.programme import LadderYear, ProgrammeReport, _ladder_table

    year = LadderYear(
        year=3,
        committed=10.0,
        called=20.0,
        distributed=30.0,
        net=99.0,
        called_to_date=40.0,
        unfunded_end=50.0,
        private_nav_end=60.0,
    )
    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[],
        ladder=[year],
        stats=[],
        vintage_stack=[],
        forced_sales=[],
    )
    html = _ladder_table(rep)
    body = html[html.index("<tbody>") : html.index("</tbody>")]
    order = ["10.00", "20.00", "30.00", "99.00", "40.00", "50.00", "60.00"]
    positions = [body.index(v) for v in order]
    assert positions == sorted(positions)


def test_linkage_table_columns_are_not_swapped():
    from ah.programme import ProgrammeReport, _linkage_table

    q = _q(
        quarter=7,
        month=23,
        drawdown_depth=0.11,
        spread_ratio=0.22,
        f_dist=0.33,
        f_call=0.44,
        distributions=55.0,
        distributions_unlinked=66.0,
    )
    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[q],
        ladder=[],
        stats=[],
        vintage_stack=[],
        forced_sales=[],
    )
    html = _linkage_table(rep)
    body = html[html.index("<tbody>") : html.index("</tbody>")]
    order = ["0.110", "0.220", "0.330", "0.440", "55.00", "66.00", "11.00"]
    positions = [body.index(v) for v in order]
    assert positions == sorted(positions)


def test_stats_table_columns_are_not_swapped():
    from ah.programme import Band, ProgrammeReport, ProgrammeStat, _stats_table

    stat = ProgrammeStat(
        name="z",
        median=1.0,
        p10=2.0,
        p90=3.0,
        path0=4.0,
        band=Band(5.0, 6.0, "q"),
        flagged=False,
        n_present=7,
        n_total=8,
    )
    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[],
        ladder=[],
        stats=[stat],
        vintage_stack=[],
        forced_sales=[],
    )
    html = _stats_table(rep)
    body = html[html.index("<tbody>") : html.index("</tbody>")]
    order = ["1.000", "2.000", "3.000", "4.000", "7 of 8", "5.00", "6.00"]
    positions = [body.index(v) for v in order]
    assert positions == sorted(positions)


# ---------------------------------------------------------------------------
# Review round 1, I3: path 0's own value must not silently fall back to the
# median when path 0 never computed the statistic -- especially now that the
# adjacent "paths" column can read "1 of 20".


def test_programme_stat_path0_is_none_when_absent_from_path0():
    from ah.programme import PROGRAMME_PLAUSIBLE, programme_stats

    name = next(iter(PROGRAMME_PLAUSIBLE))
    per_path = [{name: 0.5}, {name: 0.6}]
    stats = programme_stats(per_path, {})  # path 0 never has the key
    stat = next(s for s in stats if s.name == name)
    assert stat.path0 is None


def test_stats_table_renders_a_dash_when_path0_is_missing():
    from ah.programme import Band, ProgrammeReport, ProgrammeStat, _stats_table

    stat = ProgrammeStat(
        name="crossover_years",
        median=5.0,
        p10=4.0,
        p90=6.0,
        path0=None,
        band=Band(4.0, 8.0, "q"),
        flagged=False,
        n_present=2,
        n_total=4,
    )
    rep = ProgrammeReport(
        world_id="t",
        title="t",
        quarters=[],
        ladder=[],
        stats=[stat],
        vintage_stack=[],
        forced_sales=[],
    )
    html = _stats_table(rep)
    assert "<td>-</td>" in html
