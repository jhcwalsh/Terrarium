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

    def test_high_yield_is_flagged_on_the_stagflation_preset(self, ensemble):
        """The finding that motivated the console (register ER-1). If a fix
        lands, this test fails and the register entry should close."""
        hy = next(s for s in asset_stats(ensemble) if s.asset == "hy")
        assert hy.flags, "HY earning gross spread with no defaults should flag"
        assert hy.ann_median / hy.vol > MAX_PLAUSIBLE_SHARPE

    def test_a_flag_names_the_number_and_the_declared_edge(self, ensemble):
        flagged = [s for s in asset_stats(ensemble) if s.flags]
        assert flagged, "a stressed toy world should trip at least one prior"
        for s in flagged:
            for f in s.flags:
                assert "%" in f or "return/vol" in f

    def test_bands_cover_every_asset(self):
        assert set(PLAUSIBLE) == set(ASSETS)
        for band in PLAUSIBLE.values():
            assert band.ret_lo < band.ret_hi
            assert 0.0 <= band.vol_lo < band.vol_hi


class TestFactorStats:
    def test_spread_hump_is_visible_as_a_mean_far_from_its_ends(self):
        """ER-1's second half: the spread starts and ends near 400bp but
        averages far above it. The console must show that, not just the
        endpoints an eyeball would check."""
        from ah.core.engine import run_path

        paths = [run_path(_world(), SEED + 7919 * k) for k in range(8)]
        spread = next(f for f in factor_stats(paths) if f.name.startswith("HY spread"))
        assert spread.mean > 2.0 * max(abs(spread.start), abs(spread.end))
        assert spread.flags

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
                type(a)(a.asset, a.ann_p5, a.ann_median, a.ann_p95, a.vol, 0.0, ())
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
