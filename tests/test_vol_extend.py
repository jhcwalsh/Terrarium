"""Stage 1 of WP-DATA-VOLEXT: the observed VXO extension of ``equity_vol``.

The sealed-surface posture under test: ``ah.data.vol_extend`` consumes the
splice framework read-only (``splice.py`` and ``derive.py`` are hashed by
``pre-registration.lock``), so these tests also pin that nothing sealed
learned the new rule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data import vol_extend as vx
from ah.data.manifest import load_requirements


def _frame(start: str, months: int, values: np.ndarray) -> pd.DataFrame:
    dates = pd.date_range(start, periods=months, freq="ME")
    return pd.DataFrame({"date": dates, "value": values})


def _pair(a: float = 0.05, b: float = 0.97, seed: int = 7):
    """A VXO-like donor (1986-01..2000-12) and VIX-like target (1990-01..2000-12)
    linked by log VIX = a + b log VXO exactly on the overlap."""
    rng = np.random.default_rng(seed)
    donor_vals = np.exp(np.log(20.0) + 0.25 * rng.standard_normal(180))
    donor = _frame("1986-01-31", 180, donor_vals)
    target_vals = np.exp(a + b * np.log(donor_vals[48:]))
    target = _frame("1990-01-31", 132, target_vals)
    return target, donor


def test_fit_recovers_the_loglog_link_exactly():
    target, donor = _pair(a=0.05, b=0.97)
    fit = vx.fit_loglog(target, donor)
    assert fit.a == pytest.approx(0.05, abs=1e-9)
    assert fit.b == pytest.approx(0.97, abs=1e-9)
    assert fit.n_obs == 132
    assert fit.overlap == ("1990-01-31", "2000-12-31")


def test_extension_fills_only_prehistory_and_flags_it():
    target, donor = _pair()
    ext = vx.extend_equity_vol(target, donor)
    assert ext.series_id == "fred.VIX__extended"
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    actual_values = ext.frame.loc[~ext.frame["is_proxy"], "value"]
    assert len(proxy) == 48 and proxy["date"].max() < pd.Timestamp("1990-01-31")
    assert (ext.frame["rule_id"] == "PROXY-EQUITY-VOL-VXO-V1").all()
    # observed months are byte-for-byte the target's values -- never overwritten
    np.testing.assert_array_equal(actual_values.to_numpy(), target["value"].to_numpy())


def test_vxo_above_vix_means_proxies_sit_below_the_donor():
    # a < 0, b = 1: the donor runs systematically above the target, as VXO
    # does above VIX; the transformed proxies must come out BELOW the donor.
    target, donor = _pair(a=-0.12, b=1.0)
    ext = vx.extend_equity_vol(target, donor)
    proxy = ext.frame.loc[ext.frame["is_proxy"], "value"].to_numpy()
    donor_pre = donor["value"].to_numpy()[:48]
    assert (proxy < donor_pre).all()


def test_short_overlap_is_refused():
    target, donor = _pair()
    short_target = target.iloc[: vx.MIN_OVERLAP_MONTHS - 1]
    with pytest.raises(ValueError, match="overlap too short"):
        vx.fit_loglog(short_target, donor)


def test_duplicate_dates_are_refused():
    target, donor = _pair()
    dup = pd.concat([donor, donor.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        vx.fit_loglog(target, dup)


def test_overlap_stats_are_exact_on_a_noiseless_link():
    target, donor = _pair()
    stats = vx.overlap_stats(target, donor)
    assert stats["rmse_log"] == pytest.approx(0.0, abs=1e-9)
    assert stats["corr_log"] == pytest.approx(1.0, abs=1e-9)
    assert stats["n_obs"] == 132.0


def test_vxo_is_registered_as_a_warn_only_donor():
    req = load_requirements()["fred.VXO"]
    assert req.code == "VXOCLS" and req.license_tier == "FREE"
    assert not req.enforce, "a discontinued donor must never gate a refresh"
    assert req.sla_days == 99999, "permanent, documented staleness"
    assert req.min_start == "1986-01"
    assert "DISCONTINUED" in (req.notes or "")


def test_vxo_aggregates_month_end_like_vix():
    from ah.data.connectors.base import aggregate_daily_to_monthly

    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-31", "2020-02-03"]),
            "value": [10.0, 12.0, 11.0],
        }
    )
    out = aggregate_daily_to_monthly(daily, "fred.VXO")
    assert out["value"].tolist() == [12.0, 11.0], "month-end last, not monthly mean"


def test_nothing_sealed_learned_the_new_rule():
    """The sealed registry and the sealed factor read path must not reference
    the stage-1 rule until the owner ratifies the amendment that moves it."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for sealed in ("src/ah/data/splice.py", "src/ah/data/derive.py"):
        text = (root / sealed).read_text(encoding="utf-8")
        assert "VXO" not in text, f"{sealed} references the unratified VXO rule"
        assert "vol_extend" not in text, f"{sealed} imports the unratified module"
