"""WP-DATA-SPAN53: the two donors that carry the span to 1953-04.

ust_10y: an identity-class splice (GS10 is DGS10's monthly-average
ancestor). fx_usd: the pegged-era parity step index — its synthetic tests
are exact because the construction is a table of published facts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data import fx_parity as fp
from ah.data import ust10y_extend as tx


def _yield_world():
    dates = pd.date_range("1953-04-01", "2025-12-01", freq="MS")
    rng = np.random.Generator(np.random.PCG64(23))
    latent = 4.0 + np.cumsum(0.04 * rng.standard_normal(len(dates)))
    gs10 = pd.DataFrame({"date": dates, "value": latent})
    obs = pd.Series(latent, index=dates).loc["1962-01":]
    dgs10 = pd.DataFrame({"date": obs.index, "value": 0.01 + 0.999 * obs.to_numpy()})
    return dgs10, gs10, latent


def test_ust10y_fit_and_backfill_are_exact():
    dgs10, gs10, _latent = _yield_world()
    fit = tx.fit_gs10(dgs10, gs10)
    assert fit.a == pytest.approx(0.01, abs=1e-9)
    assert fit.b == pytest.approx(0.999, abs=1e-9)
    ext = tx.extend_ust10y(dgs10, gs10)
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    assert proxy["date"].min() == pd.Timestamp("1953-04-01")
    assert proxy["date"].max() == pd.Timestamp("1961-12-01")
    assert len(proxy) == 105
    assert (ext.frame["rule_id"] == "PROXY-UST10Y-GS10-V1").all()
    np.testing.assert_array_equal(
        ext.frame.loc[~ext.frame["is_proxy"], "value"].to_numpy(),
        dgs10["value"].to_numpy(),
    )
    stats = tx.overlap_stats(dgs10, gs10)
    assert stats["rmse"] == pytest.approx(0.0, abs=1e-9)


def test_ust10y_short_overlap_refused():
    dgs10, gs10, _ = _yield_world()
    with pytest.raises(ValueError, match="overlap too short"):
        tx.fit_gs10(dgs10.iloc[: tx.MIN_OVERLAP_MONTHS - 1], gs10)


def test_parity_index_is_flat_between_documented_steps():
    idx = fp.parity_index()
    assert idx.index.min() == pd.Timestamp("1953-04-01")
    assert idx.index.max() == pd.Timestamp("1972-12-01")
    assert idx.iloc[0] == pytest.approx(100.0)
    # flat through 1956 (no realignment in the table before 1957-08)
    early = idx.loc["1953-04":"1957-07"]
    assert float(early.std()) == pytest.approx(0.0, abs=1e-12)
    # GBP devaluation 1967-11: sterling per USD RISES -> dollar index steps UP
    step = float(idx.loc["1967-11-01"] / idx.loc["1967-10-01"])
    assert step == pytest.approx((2.80 / 2.40) ** (1.0 / 6.0), rel=1e-9)
    # Smithsonian 1971-12: the dollar devalues against every basket member
    assert float(idx.loc["1971-12-01"]) < float(idx.loc["1971-11-01"])
    # and every month is a step or flat -- no noise by construction. The
    # largest single step is the Smithsonian realignment itself (1971-12,
    # historically a ~10.7% dollar devaluation), which the basket reproduces.
    rets = idx.pct_change().dropna()
    assert (rets.abs() < 0.12).all()
    assert rets.abs().idxmax() == pd.Timestamp("1971-12-01")


def test_extend_fx_pins_the_junction_and_never_overwrites():
    months = pd.date_range("1973-01-01", periods=24, freq="MS")
    rng = np.random.Generator(np.random.PCG64(4))
    dtwexm = pd.DataFrame(
        {"date": months, "value": 95.0 * np.exp(np.cumsum(0.01 * rng.standard_normal(24)))}
    )
    ext = fp.extend_fx(dtwexm)
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    assert proxy["date"].min() == pd.Timestamp("1953-04-01")
    assert proxy["date"].max() == pd.Timestamp("1972-12-01")
    assert len(proxy) == 237
    # junction: last parity month equals the first observed value / step ratio
    last_proxy = float(proxy["value"].iloc[-1])
    first_obs = float(dtwexm["value"].iloc[0])
    assert last_proxy == pytest.approx(first_obs)
    np.testing.assert_array_equal(
        ext.frame.loc[~ext.frame["is_proxy"], "value"].to_numpy(),
        dtwexm["value"].to_numpy(),
    )
    assert (ext.frame["rule_id"] == "PROXY-FX-PARITY-V1").all()


def test_fx_refuses_when_nothing_to_prepend():
    months = pd.date_range("1950-01-01", periods=12, freq="MS")
    early = pd.DataFrame({"date": months, "value": np.full(12, 100.0)})
    with pytest.raises(ValueError, match="nothing to prepend"):
        fp.extend_fx(early)


def test_nothing_sealed_learned_the_new_rules():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for sealed in ("src/ah/data/splice.py", "src/ah/data/derive.py"):
        text = (root / sealed).read_text(encoding="utf-8")
        for needle in ("PROXY-UST10Y", "PROXY-FX-PARITY", "ust10y_extend", "fx_parity"):
            assert needle not in text, f"{sealed} references unratified {needle}"
