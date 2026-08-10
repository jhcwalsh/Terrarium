"""WP-DATA-UST2YEXT: the curve-interpolation extension of ust_2y.

Synthetic world: a latent yield-curve level 1953-2025; GS1 and GS3 are the
level plus maturity-specific spreads, and the 2y yield is an exact linear
combination of them plus a constant — so fit recovery and the filled values
are exact.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data import ust2y_extend as ux
from ah.data.manifest import load_requirements

A_TRUE, B1_TRUE, B2_TRUE = 0.05, 0.45, 0.55


def _world():
    dates = pd.date_range("1953-04-30", "2025-12-31", freq="ME")
    rng = np.random.Generator(np.random.PCG64(17))
    level = 4.0 + np.cumsum(0.05 * rng.standard_normal(len(dates)))
    slope = 0.3 * np.sin(np.arange(len(dates)) / 30.0)
    gs1 = level - slope
    gs3 = level + 0.4 * slope
    dgs2 = A_TRUE + B1_TRUE * gs1 + B2_TRUE * gs3

    def frame(vals: np.ndarray, lo: str) -> pd.DataFrame:
        s = pd.Series(vals, index=dates).loc[lo:]
        return pd.DataFrame({"date": s.index, "value": s.to_numpy()})

    return {
        "gs1": frame(gs1, "1953-04"),
        "gs3": frame(gs3, "1953-04"),
        "dgs2": frame(dgs2, "1976-06"),
        "dgs2_latent": pd.Series(dgs2, index=dates),
    }


@pytest.fixture(scope="module")
def world():
    return _world()


def test_fit_recovers_the_interpolation_weights_exactly(world):
    fit = ux.fit_curve(world["dgs2"], world["gs1"], world["gs3"])
    assert fit.a == pytest.approx(A_TRUE, abs=1e-8)
    assert fit.b1 == pytest.approx(B1_TRUE, abs=1e-8)
    assert fit.b2 == pytest.approx(B2_TRUE, abs=1e-8)
    stats = ux.overlap_stats(world["dgs2"], world["gs1"], world["gs3"])
    assert stats["rmse"] == pytest.approx(0.0, abs=1e-8)
    assert stats["corr"] == pytest.approx(1.0, abs=1e-8)


def test_extension_fills_backward_only_and_never_overwrites(world):
    ext = ux.extend_ust2y(world["dgs2"], world["gs1"], world["gs3"])
    assert ext.series_id == "fred.DGS2__extended"
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    assert proxy["date"].min() == pd.Timestamp("1953-04-30")
    assert proxy["date"].max() == pd.Timestamp("1976-05-31")
    assert len(proxy) == 278  # 1953-04..1976-05
    assert (ext.frame["rule_id"] == "PROXY-UST2Y-GS1GS3-V1").all()
    dgs2_vals = world["dgs2"]["value"].to_numpy()
    actual = ext.frame.loc[~ext.frame["is_proxy"], "value"].to_numpy()
    np.testing.assert_array_equal(actual, dgs2_vals)
    expected = world["dgs2_latent"].loc[proxy["date"].to_numpy()].to_numpy()
    np.testing.assert_allclose(proxy["value"].to_numpy(), expected, atol=1e-8)


def test_fill_requires_both_donors(world):
    # truncate GS1 to start 1960: filled months must start there too, because
    # the interpolation needs both curve neighbours
    gs1_late = world["gs1"].loc[world["gs1"]["date"] >= pd.Timestamp("1960-01-01")]
    ext = ux.extend_ust2y(world["dgs2"], gs1_late, world["gs3"])
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    assert proxy["date"].min() == pd.Timestamp("1960-01-31")


def test_short_overlap_is_refused(world):
    short = world["dgs2"].iloc[: ux.MIN_OVERLAP_MONTHS - 1]
    with pytest.raises(ValueError, match="overlap too short"):
        ux.fit_curve(short, world["gs1"], world["gs3"])


def test_duplicate_dates_are_refused(world):
    dup = pd.concat([world["gs1"], world["gs1"].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        ux.fit_curve(world["dgs2"], dup, world["gs3"])


def test_donors_are_registered_warn_only():
    reqs = load_requirements()
    for sid, code in (("fred.GS1", "GS1"), ("fred.GS3", "GS3")):
        r = reqs[sid]
        assert r.code == code and r.license_tier == "FREE"
        assert not r.enforce and r.min_start == "1953-04"


def test_the_sealed_read_path_learned_the_rule():
    """INVERTED 2026-08-09 (campaign-3 wiring; AM-2026-08-09-002).

    HISTORY, first state: pinned that neither sealed file referenced
    PROXY-UST2Y or imported ``ust2y_extend`` while the rule was verified but
    unratified. The campaign-3 wiring put it on the read path
    (``derive.ust_2y_extended`` -- the BINDING factor of the ratified
    1953-04 span); the pin inverts, and ``splice.py`` stays clean.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    derive_text = (root / "src/ah/data/derive.py").read_text(encoding="utf-8")
    assert "ust2y_extend" in derive_text and "PROXY-UST2Y" in derive_text
    splice_text = (root / "src/ah/data/splice.py").read_text(encoding="utf-8")
    assert "ust2y_extend" not in splice_text
    lock = json.loads((root / "pre-registration.lock").read_text(encoding="utf-8"))
    assert "src/ah/data/ust2y_extend.py" in lock["hashed_files"]
