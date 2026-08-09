"""WP-DATA-FSEXT: the CP-bill extension of ``funding_spread``, both ends.

Synthetic world: one latent CP path and one latent bill path 1930-2025; the
observed segments are windows of them with known level offsets, and TED is an
exact level map of the true spread on its 1986-2022 life. Every recovery
assertion is therefore exact, and the segment-chaining diagnostics have known
right answers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data import funding_extend as fx
from ah.data.manifest import load_requirements

A_TRUE, B_TRUE = 0.1, 0.9
CP3M_OFFSET, NBER_OFFSET, TB3MS_OFFSET = -0.15, -0.40, +0.05


def _world():
    dates = pd.date_range("1930-01-31", "2025-12-31", freq="ME")
    t = np.arange(len(dates))
    rng = np.random.Generator(np.random.PCG64(5))
    latent_cp = 4.0 + np.cumsum(0.02 * rng.standard_normal(len(dates)))
    spread_true = 0.45 + 0.25 * np.sin(t / 7.0) + 0.05 * rng.standard_normal(len(dates))
    latent_bill = latent_cp - spread_true
    cp = pd.Series(latent_cp, index=dates)
    bill = pd.Series(latent_bill, index=dates)

    def frame(s: pd.Series, lo: str, hi: str, offset: float = 0.0) -> pd.DataFrame:
        w = s.loc[lo:hi] + offset
        return pd.DataFrame({"date": w.index, "value": w.to_numpy()})

    ted_true = pd.Series(A_TRUE + B_TRUE * spread_true, index=dates)
    return {
        "cpf3m": frame(cp, "1997-01", "2025-12"),
        "cp3m": frame(cp, "1971-04", "1997-08", CP3M_OFFSET),
        "nber": frame(cp, "1930-01", "1971-12", NBER_OFFSET),
        "tb3m_sec": frame(bill, "1954-01", "2025-12"),
        "tb3ms": frame(bill, "1934-01", "1960-12", TB3MS_OFFSET),
        "ted": frame(ted_true, "1986-01", "2022-01"),
        "latent_cp": cp,
        "spread_true": pd.Series(spread_true, index=dates),
    }


@pytest.fixture(scope="module")
def world():
    return _world()


def test_cp_chain_recovers_the_latent_path_and_reports_offsets(world):
    diag: dict[str, dict[str, float]] = {}
    cp = fx.cp_series(world["cpf3m"], world["cp3m"], world["nber"], diag)
    np.testing.assert_allclose(
        cp.to_numpy(), world["latent_cp"].loc[cp.index].to_numpy(), atol=1e-9
    )
    assert diag["cp3m_onto_cpf3m"]["offset"] == pytest.approx(-CP3M_OFFSET, abs=1e-9)
    assert diag["nber_onto_cp3m"]["offset"] == pytest.approx(-NBER_OFFSET, abs=1e-9)
    assert diag["cp3m_onto_cpf3m"]["overlap_rmse"] == pytest.approx(0.0, abs=1e-9)


def test_fit_recovers_the_level_link_exactly(world):
    diag: dict[str, dict[str, float]] = {}
    cp = fx.cp_series(world["cpf3m"], world["cp3m"], world["nber"], diag)
    bill = fx.bill_series(world["tb3m_sec"], world["tb3ms"], diag)
    spread = (cp - bill.reindex(cp.index)).dropna()
    fit = fx.fit_level(world["ted"], spread)
    assert fit.a == pytest.approx(A_TRUE, abs=1e-9)
    assert fit.b == pytest.approx(B_TRUE, abs=1e-9)
    assert fit.n_obs == 433  # 1986-01..2022-01 inclusive
    stats = fx.overlap_stats(world["ted"], spread)
    assert stats["rmse"] == pytest.approx(0.0, abs=1e-9)
    assert stats["corr"] == pytest.approx(1.0, abs=1e-9)


def test_extension_fills_both_ends_floored_and_never_overwrites(world):
    ext = fx.extend_funding_spread(
        world["ted"],
        world["cpf3m"],
        world["cp3m"],
        world["nber"],
        world["tb3m_sec"],
        world["tb3ms"],
    )
    assert ext.series_id == "fred.TEDRATE__extended"
    proxy = ext.frame.loc[ext.frame["is_proxy"]]
    # backward fill starts at the F3 floor, NOT at the NBER segment's 1930 start
    assert proxy["date"].min() == pd.Timestamp("1934-01-31")
    # forward fill covers the post-TED hole
    assert proxy["date"].max() == pd.Timestamp("2025-12-31")
    back = proxy.loc[proxy["date"] < pd.Timestamp("1986-01-01")]
    fwd = proxy.loc[proxy["date"] > pd.Timestamp("2022-01-31")]
    assert len(back) == 624 and len(fwd) == 47
    assert (ext.frame["rule_id"] == "PROXY-FUNDING-CPBILL-V1").all()
    # observed TED months are byte-for-byte untouched
    ted_vals = world["ted"]["value"].to_numpy()
    actual = ext.frame.loc[~ext.frame["is_proxy"], "value"].to_numpy()
    np.testing.assert_array_equal(actual, ted_vals)
    # and the filled values are the exact level map of the true spread
    expected_back = (A_TRUE + B_TRUE * world["spread_true"].loc[back["date"].to_numpy()]).to_numpy()
    np.testing.assert_allclose(back["value"].to_numpy(), expected_back, atol=1e-9)


def test_short_ted_overlap_is_refused(world):
    diag: dict[str, dict[str, float]] = {}
    cp = fx.cp_series(world["cpf3m"], world["cp3m"], world["nber"], diag)
    bill = fx.bill_series(world["tb3m_sec"], world["tb3ms"], diag)
    spread = (cp - bill.reindex(cp.index)).dropna()
    short_ted = world["ted"].iloc[: fx.MIN_OVERLAP_MONTHS - 1]
    with pytest.raises(ValueError, match="overlap too short"):
        fx.fit_level(short_ted, spread)


def test_short_segment_join_is_refused(world):
    truncated = world["cp3m"].loc[
        world["cp3m"]["date"] <= pd.Timestamp("1997-02-28")
    ]  # 2-month overlap with cpf3m
    with pytest.raises(ValueError, match="segment join cp3m_onto_cpf3m"):
        fx.cp_series(world["cpf3m"], truncated, world["nber"])


def test_duplicate_dates_are_refused(world):
    dup = pd.concat([world["cpf3m"], world["cpf3m"].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        fx.cp_series(dup, world["cp3m"], world["nber"])


def test_donors_are_registered_warn_only():
    reqs = load_requirements()
    for sid, code in (("fred.CP3M", "CP3M"), ("fred.CP3M_NBER", "M13002US35620M156NNBR")):
        r = reqs[sid]
        assert r.code == code and r.license_tier == "FREE"
        assert not r.enforce and r.sla_days == 99999
        assert "funding_extend" in (r.notes or "") or "funding_spread" in (r.notes or "")


def test_nothing_sealed_learned_the_new_rule():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for sealed in ("src/ah/data/splice.py", "src/ah/data/derive.py"):
        text = (root / sealed).read_text(encoding="utf-8")
        assert "PROXY-FUNDING-CPBILL" not in text, f"{sealed} references the unratified rule"
        assert "funding_extend" not in text, f"{sealed} imports the unratified module"
