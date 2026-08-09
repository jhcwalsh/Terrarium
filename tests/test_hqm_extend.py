"""WP-DATA-HQMEXT: the Aaa extension of the 10y HQM corporate spot rate.

Synthetic world: a latent high-grade 10y yield 1919-2025; observed Aaa is a
level-shifted long-maturity version carrying a term-premium component, and
HQM observes the latent series from 1984. Fit-recovery assertions are exact
where the synthetic link is exact; the slope diagnostic's synthetic world
gives it a real premium to find.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data import hqm_extend as hx
from ah.data.manifest import load_requirements

A_TRUE, B_TRUE = -0.30, 1.05


def _world(term_premium: bool = False):
    dates = pd.date_range("1919-01-31", "2025-12-31", freq="ME")
    rng = np.random.Generator(np.random.PCG64(3))
    aaa = 5.0 + np.cumsum(0.03 * rng.standard_normal(len(dates)))
    slope = 0.5 * np.sin(np.arange(len(dates)) / 40.0)  # the Aaa - GS10 gap
    hqm_latent = A_TRUE + B_TRUE * aaa + (0.4 * slope if term_premium else 0.0)
    gs10_vals = aaa - slope

    def frame(vals: np.ndarray, lo: str) -> pd.DataFrame:
        s = pd.Series(vals, index=dates).loc[lo:]
        return pd.DataFrame({"date": s.index, "value": s.to_numpy()})

    return {
        "aaa": frame(aaa, "1919-01"),
        "hqm": frame(hqm_latent, "1984-01"),
        "gs10": frame(gs10_vals, "1953-04"),
        "hqm_latent": pd.Series(hqm_latent, index=dates),
    }


@pytest.fixture(scope="module")
def world():
    return _world()


def test_fit_recovers_the_level_link_exactly(world):
    fit = hx.fit_aaa(world["hqm"], world["aaa"])
    assert fit.a == pytest.approx(A_TRUE, abs=1e-9)
    assert fit.b == pytest.approx(B_TRUE, abs=1e-9)
    stats = hx.overlap_stats(world["hqm"], world["aaa"])
    assert stats["rmse"] == pytest.approx(0.0, abs=1e-9)
    assert stats["corr"] == pytest.approx(1.0, abs=1e-9)


def test_extension_fills_backward_only_and_never_overwrites(world):
    ext = hx.extend_hqm(world["hqm"], world["aaa"])
    assert ext.series_id == "treasury.hqm_curve__extended"
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    assert proxy["date"].min() == pd.Timestamp("1919-01-31")
    assert proxy["date"].max() == pd.Timestamp("1983-12-31")
    assert len(proxy) == 780  # 1919-01..1983-12
    assert (ext.frame["rule_id"] == "PROXY-HQM10-AAA-V1").all()
    hqm_vals = world["hqm"]["value"].to_numpy()
    actual = ext.frame.loc[~ext.frame["is_proxy"], "value"].to_numpy()
    np.testing.assert_array_equal(actual, hqm_vals)
    # exact recreation of the latent series on the filled span
    expected = world["hqm_latent"].loc[proxy["date"].to_numpy()].to_numpy()
    np.testing.assert_allclose(proxy["value"].to_numpy(), expected, atol=1e-9)


def test_short_overlap_is_refused(world):
    short = world["hqm"].iloc[: hx.MIN_OVERLAP_MONTHS - 1]
    with pytest.raises(ValueError, match="overlap too short"):
        hx.fit_aaa(short, world["aaa"])


def test_duplicate_dates_are_refused(world):
    dup = pd.concat([world["aaa"], world["aaa"].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        hx.fit_aaa(world["hqm"], dup)


def test_slope_diagnostic_finds_a_real_premium_and_stays_diagnostic():
    world = _world(term_premium=True)
    diag = hx.slope_diagnostic(world["hqm"], world["aaa"], world["gs10"])
    # the alternative fit recovers the premium the simple fit cannot express
    assert diag["slope_coef"] == pytest.approx(0.4, abs=0.05)
    assert diag["overlap_rmse_slope"] < diag["overlap_rmse_simple"]
    # and the two constructions genuinely diverge over the pre-HQM era
    assert diag["divergence_max"] > 0.05
    assert diag["n_pre_months_compared"] > 300
    # while the REGISTERED construction remains the simple fit regardless
    fit = hx.fit_aaa(world["hqm"], world["aaa"])
    ext = hx.extend_hqm(world["hqm"], world["aaa"])
    pre = ext.frame.loc[ext.frame["is_proxy"], "value"].to_numpy()
    aaa_pre = world["aaa"]["value"].to_numpy()[: len(pre)]
    np.testing.assert_allclose(pre, fit.predict(aaa_pre), atol=1e-9)


def test_donor_is_already_registered_and_live():
    r = load_requirements()["fred.AAA"]
    assert r.code == "AAA" and r.license_tier == "FREE" and r.enforce
    assert r.min_start == "1919-01"


def test_nothing_sealed_learned_the_new_rule():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for sealed in ("src/ah/data/splice.py", "src/ah/data/derive.py"):
        text = (root / sealed).read_text(encoding="utf-8")
        assert "PROXY-HQM10" not in text, f"{sealed} references the unratified rule"
        assert "hqm_extend" not in text, f"{sealed} imports the unratified module"
