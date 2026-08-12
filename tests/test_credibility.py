"""The credibility console: does it actually catch an incredible world?

This is admin tooling, so the bar is different from the engine's — nothing
here is sealed and no flag can fail a build. What the tests protect is the
property that makes it worth having: a statistic that a human would object to
must show up as a flag, and the page must be deterministic so two people
reading it are reading the same thing.

The headline case is the one that motivated the tool: high yield on the
stagflation preset earns gross spread with no default losses, and comes out
at a decade Sharpe above 1.0. If a future change makes that credible, this
test will say so by failing — which is the correct way to find out.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ah.core.engine import ASSETS, REPORTED_SLEEVES, run_ensemble
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.credibility import (
    MAX_PLAUSIBLE_SHARPE,
    PLAUSIBLE,
    asset_stats,
    build_report,
    factor_stats,
    render_credibility_page,
    smoothing_stats,
)

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "src" / "ah" / "presets" / "stagflation.json"
SEED = 771204


def _world(quarters: int | None = None):
    doc: dict[str, Any] = json.loads(PRESET.read_text(encoding="utf-8"))
    if quarters is not None:
        doc = copy.deepcopy(doc)
        doc["horizon"]["quarters"] = quarters
    return project_numeric(WorldSpec.model_validate(doc))


@pytest.fixture(scope="module")
def ensemble():
    return run_ensemble(_world(), 60, base_seed=SEED)


class TestAssetStats:
    def test_every_asset_is_reported_in_contract_order(self, ensemble):
        assert [s.asset for s in asset_stats(ensemble)] == list(ASSETS)

    def test_percentiles_are_ordered(self, ensemble):
        for s in asset_stats(ensemble):
            assert s.ann_p5 <= s.ann_median <= s.ann_p95
            assert s.vol >= 0.0
            assert 0.0 <= s.worst_drawdown <= 100.0

    def test_high_yield_is_paid_net_of_defaults(self, ensemble):
        """Register ER-1, now CLOSED — and this test is what closed it.

        It was written the other way up: when high yield booked the full
        current spread as carry with no loss offset, it printed 18.7%/yr on
        12.1% vol, a decade Sharpe of 1.54, and this asserted the flag fired.
        toy-v0.3 charges the defaults the spread is pricing, so the assertion
        inverts. If a future change reintroduces free carry, this fails.

        ER-9's tail flags are excluded from the no-flags assertion: the t(6)
        tails print a -26% HY month on this ensemble, which is ER-9's open
        finding, not ER-1's closed one. When ER-9 closes in the engine, the
        exclusion becomes vacuous rather than wrong."""
        hy = next(s for s in asset_stats(ensemble) if s.asset == "hy")
        assert hy.ann_median / hy.vol <= MAX_PLAUSIBLE_SHARPE, hy
        non_tail = [f for f in hy.flags if "worst month" not in f and "drawdown" not in f]
        assert not non_tail, non_tail

    def test_a_flag_names_the_number_and_the_declared_edge(self):
        """Flag TEXT must carry the number and the edge it crossed. Checked
        against a deliberately impossible band rather than a real world, so
        the test survives the engine being fixed."""
        import ah.credibility as cred

        ens = run_ensemble(_world(8), 8, base_seed=SEED)
        original = dict(cred.PLAUSIBLE)
        try:
            cred.PLAUSIBLE["bonds"] = cred.Band(90.0, 99.0, 90.0, 99.0, "impossible")
            flagged = [s for s in asset_stats(ens) if s.flags]
        finally:
            cred.PLAUSIBLE.clear()
            cred.PLAUSIBLE.update(original)
        assert flagged
        for s in flagged:
            for f in s.flags:
                assert "%" in f or "return/vol" in f

    def test_bands_cover_every_asset(self):
        assert set(PLAUSIBLE) == set(ASSETS)
        for band in PLAUSIBLE.values():
            assert band.ret_lo < band.ret_hi
            assert 0.0 <= band.vol_lo < band.vol_hi


class TestTailBands:
    """Register ER-9: tail statistics need declared edges too.

    Motivated by the 2026-08-11 stagflation review: the console showed a 96%
    worst-path equity drawdown driven by a single -86% month (the whole of
    1929-32 compressed into one month) and a 100% worst PE drawdown (the -99
    limited-liability floor binding), and no band existed to flag either -
    the owner had to squint at a cell. These bands make that a flag.
    """

    def test_bands_declare_tail_edges_for_every_asset(self):
        for band in PLAUSIBLE.values():
            assert -100.0 < band.month_lo < 0.0
            assert 0.0 < band.dd_hi < 100.0

    def test_a_catastrophic_month_and_its_drawdown_are_flagged(self):
        """A -95% equity month breaches any defensible monthly floor, and the
        drawdown it leaves breaches the path-drawdown ceiling; both must flag,
        and quiet assets must stay quiet on both tail checks."""
        from ah.core.engine import EnsembleResult

        months = 24
        flat = np.full((2, months), 0.5)
        eq = flat.copy()
        eq[0, 12] = -95.0
        returns = {a: flat for a in ASSETS}
        returns["equity"] = eq
        ens = EnsembleResult(
            months=months,
            n_paths=2,
            seeds=[SEED, SEED + 7919],
            returns=returns,
            reported={},
        )
        stats = {s.asset: s for s in asset_stats(ens)}
        eq_flags = stats["equity"].flags
        assert any("worst month" in f for f in eq_flags), eq_flags
        assert any("drawdown" in f for f in eq_flags), eq_flags
        for f in eq_flags:
            assert "%" in f or "return/vol" in f
        for asset, s in stats.items():
            if asset == "equity":
                continue
            tail = [f for f in s.flags if "worst month" in f or "drawdown" in f]
            assert not tail, (asset, tail)

    def test_page_shows_the_tail_columns(self):
        rep = build_report(_world(8), base_seed=SEED, n_paths=12)
        page = render_credibility_page([rep])
        assert "worst month %" in page
        assert "declared tail" in page


class TestFactorStats:
    def test_the_credit_cycle_clears_instead_of_plateauing(self):
        """Register ER-1's second half, now CLOSED.

        The old triangular path started at 401bp, ended at 358bp and AVERAGED
        1279bp — years spent at levels that clear in months. This test used to
        assert that gap, because the console has to show where a path spends
        its time rather than just the endpoints an eyeball would check. The
        pulse still reaches the declared peak at the declared quarter, but the
        decade now averages near its long-run level."""
        from ah.core.engine import run_path

        paths = [run_path(_world(), SEED + 7919 * k) for k in range(8)]
        spread = next(f for f in factor_stats(paths) if f.name.startswith("HY spread"))
        assert spread.mean < 2.0 * max(abs(spread.start), abs(spread.end))
        assert not spread.flags, spread.flags
        # the declared peak is still reached — the spec field kept its meaning
        assert spread.hi > 1800.0

    def test_crisis_share_is_a_fraction(self):
        from ah.core.engine import run_path

        paths = [run_path(_world(), SEED + 7919 * k) for k in range(4)]
        crisis = next(f for f in factor_stats(paths) if f.name.startswith("crisis"))
        assert 0.0 <= crisis.mean <= 1.0


class TestSmoothing:
    def test_reported_marks_are_smoother_and_trend(self, ensemble):
        rows = smoothing_stats(ensemble)
        assert [r.sleeve for r in rows] == list(REPORTED_SLEEVES)
        for r in rows:
            # this is the product's central claim about the reported plane;
            # if it ever stops holding, the console says so out loud
            assert r.vol_ratio < 1.0
            assert not r.flags, r.flags


class TestReportAndPage:
    def test_report_is_deterministic(self):
        a = build_report(_world(8), base_seed=SEED, n_paths=12, title="t")
        b = build_report(_world(8), base_seed=SEED, n_paths=12, title="t")
        assert a == b

    def test_page_is_self_contained_and_byte_stable(self):
        rep = build_report(_world(8), base_seed=SEED, n_paths=12, title="A World")
        page = render_credibility_page([rep])
        assert render_credibility_page([rep]) == page
        assert page.startswith("<!doctype html>")
        assert "<script" not in page and "http://" not in page and "https://" not in page
        assert "A World" in page
        for asset in ASSETS:
            assert f">{asset}<" in page

    def test_page_counts_the_flags_it_shows(self):
        rep = build_report(_world(8), base_seed=SEED, n_paths=12)
        page = render_credibility_page([rep])
        if rep.flag_count:
            assert f"{rep.flag_count} flags" in page
        else:
            assert "nothing flagged" in page

    def test_a_clean_world_reports_clean(self):
        """A hand-made report with no flags must not claim there are some."""
        rep = build_report(_world(8), base_seed=SEED, n_paths=12)
        clean = type(rep)(
            world_id=rep.world_id,
            title="Spotless",
            months=rep.months,
            n_paths=rep.n_paths,
            base_seed=rep.base_seed,
            assets=[
                type(a)(a.asset, a.ann_p5, a.ann_median, a.ann_p95, a.vol, 0.0, 0.0, ())
                for a in rep.assets
            ],
            factors=[type(f)(f.name, f.start, f.end, f.mean, f.lo, f.hi, ()) for f in rep.factors],
            smoothing=[
                type(s)(s.sleeve, s.true_vol, s.reported_vol, s.vol_ratio, s.reported_autocorr, ())
                for s in rep.smoothing
            ],
            correlations=rep.correlations,
        )
        assert clean.flag_count == 0
        assert "nothing flagged" in render_credibility_page([clean])


def test_console_cannot_reach_the_store_at_all():
    """It is an admin READ surface: looking at a world cannot change it.

    Enforced structurally rather than by grepping for verbs — the module
    imports no store and no sqlite3, so there is nothing for it to write
    through. (An earlier version of this test scanned for the string
    "append(" and tripped over ``flags.append``, which is the kind of test
    that teaches you to ignore it.)
    """
    import ast

    import ah.credibility as cred

    tree = ast.parse(Path(cred.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(m.startswith("ah.store") for m in imported), imported
    assert "sqlite3" not in imported


def test_smoothing_is_measured_where_the_marks_actually_land():
    """Private assets report at quarter ends, so the monthly reported series
    is two zeros and a number. Measuring lag-1 autocorrelation on THAT reads
    the reporting calendar, not the smoothing — the console did exactly this
    on its first run and reported a fault that was its own."""
    from ah.credibility import _quarterly_reported, _quarterly_true

    ens = run_ensemble(_world(8), 6, base_seed=SEED)
    rep_m = ens.reported["pe"]
    off_quarter = np.delete(rep_m, np.arange(2, rep_m.shape[1], 3), axis=1)
    assert np.all(off_quarter == 0.0), "marks outside quarter ends should be zero"

    rep_q = _quarterly_reported(rep_m)
    true_q = _quarterly_true(ens.returns["pe"])
    assert rep_q.shape == true_q.shape
    assert np.all(rep_q != 0.0)


def test_correlations_are_symmetric_with_unit_diagonal(ensemble):
    rep = build_report(_world(8), base_seed=SEED, n_paths=12)
    for a in ASSETS:
        assert rep.correlations[a][a] == pytest.approx(1.0)
        for b in ASSETS:
            assert rep.correlations[a][b] == pytest.approx(rep.correlations[b][a])
    assert np.isfinite(list(rep.correlations["equity"].values())).all()


def test_credibility_page_carries_the_programme_section():
    # NOTE: the plan's snippet called render_credibility_page([rep]) with no
    # programme list and still expected the section to appear. That cannot
    # pass: render_programme_section([]) renders nothing when nothing is
    # passed in, and WorldReport itself carries no NumericWorld for the page
    # to build one from. Building and passing a ProgrammeReport, as
    # credibility_cmd now does, is the only way this assertion can be true.
    from ah.credibility import build_report, render_credibility_page
    from ah.programme import build_programme_report

    world = _world()
    rep = build_report(world, base_seed=771204, n_paths=8)
    prog = build_programme_report(world, base_seed=771204, n_paths=2)
    page = render_credibility_page([rep], [prog])
    assert "the private programme" in page.lower()
    assert "linkage off" in page.lower()
