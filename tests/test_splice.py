"""WP1.5 acceptance: splice/proxy transforms + invariants."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ah.data.splice import (
    PROXY_RULES,
    ProxyRule,
    fit_transform,
    overlap_error,
    splice,
)


def _series(values: list[float], start: str = "1990-01-01", freq: str = "MS") -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq=freq)]
    return pd.DataFrame({"date": dates, "value": values})


def test_register_rules_present() -> None:
    assert set(PROXY_RULES) == {
        "hy_oas_pre1996",
        "long_tsy_tr_pre1973",
        "private_credit_pre2004",
        "nareit_delevered_re",
        "fedfunds_pre1954",
        "fx_usd_pre2006",
    }


def test_fx_usd_pre2006_rule_extends_the_broad_dollar_from_major() -> None:
    """Campaign-2 (S2R-FX-NEXT-CAMPAIGN; R5 re-entry): the fx block's series
    is the trade-weighted BROAD dollar index (fred.DTWEXBGS, 2006-01 on),
    spliced backward from the DISCONTINUED major-currencies index
    (fred.DTWEXM, 1973-2019) over their 2006-2019 overlap -- the donor's
    full remaining life. Proxy-flagged, never overwriting an actual."""
    rule = PROXY_RULES["fx_usd_pre2006"]
    assert rule.target == "fred.DTWEXBGS"
    assert rule.donor == "fred.DTWEXM"
    assert rule.transform == "regression"
    assert rule.overlap_start == "2006-01-01"
    assert rule.overlap_end == "2019-12-01"
    assert "is_proxy" in rule.doc


def test_fedfunds_pre1954_rule_extends_the_policy_rate_from_bills() -> None:
    """WP2.2 Task 1 fix pass, Critical 2: `policy_rate` maps to the effective federal
    funds rate (fred.FEDFUNDS), which FRED serves only from 1954-07. The pre-1954
    campaign window is covered by splicing the 3-month bill (fred.TB3MS, from 1934)
    backward through this rule -- flagged `is_proxy`, never overwriting an actual.
    """
    rule = PROXY_RULES["fedfunds_pre1954"]
    assert rule.target == "fred.FEDFUNDS"
    assert rule.donor == "fred.TB3MS"
    assert rule.transform == "regression"
    assert rule.overlap_start is not None and rule.overlap_end is not None
    assert rule.doc


def test_fedfunds_pre1954_backfill_flags_proxy_and_preserves_actuals() -> None:
    # donor (bills) runs 1950-1959; target (funds rate) starts 1954-07, as FRED serves it.
    donor = _series([1.0 + 0.01 * i for i in range(120)], start="1950-01-01")
    target = _series([1.4 + 0.012 * i for i in range(66)], start="1954-07-01")
    rule = PROXY_RULES["fedfunds_pre1954"]
    result = splice(
        ProxyRule(
            rule.rule_id,
            rule.target,
            rule.donor,
            rule.transform,
            overlap_start="1954-07-01",
            overlap_end="1959-12-01",
            doc=rule.doc,
        ),
        target,
        donor,
    )

    proxies = result.frame[result.frame["is_proxy"]]
    actuals = result.frame[~result.frame["is_proxy"]]
    assert proxies["date"].max() < pd.Timestamp("1954-07-01")
    assert actuals["date"].min() == pd.Timestamp("1954-07-01")
    assert len(actuals) == 66
    assert (result.frame["rule_id"] == "fedfunds_pre1954").all()


def test_regression_recovers_linear_relationship() -> None:
    donor = _series([float(i) for i in range(24)])
    target = _series([3.0 + 2.0 * i for i in range(24)])  # target = 3 + 2*donor
    rule = ProxyRule(
        "r", "t", "d", "regression", overlap_start="1990-01-01", overlap_end="1991-12-01"
    )
    fit = fit_transform(rule, target, donor)
    assert abs(fit.a - 3.0) < 1e-6
    assert abs(fit.b - 2.0) < 1e-6


def test_level_map_and_ratio() -> None:
    donor = _series([10.0, 20.0, 30.0])
    target = _series([12.0, 22.0, 32.0])  # +2 offset
    lm = fit_transform(ProxyRule("r", "t", "d", "level_map"), target, donor)
    assert abs(lm.a - 2.0) < 1e-9
    tr = _series([20.0, 40.0, 60.0])  # 2x
    ra = fit_transform(ProxyRule("r", "t", "d", "ratio"), tr, donor)
    assert abs(ra.b - 2.0) < 1e-9


def test_splice_extends_backward_and_flags_proxy() -> None:
    donor = _series([float(i) for i in range(36)], start="1990-01-01")  # 1990-1992
    target = _series([3.0 + 2.0 * (i + 24) for i in range(12)], start="1992-01-01")  # 1992
    rule = ProxyRule(
        "r", "t", "d", "regression", overlap_start="1992-01-01", overlap_end="1992-12-01"
    )
    result = splice(rule, target, donor)
    assert result.series_id == "t__extended"
    # pre-1992 are proxies, 1992 rows are actuals
    proxies = result.frame[result.frame["is_proxy"]]
    actuals = result.frame[~result.frame["is_proxy"]]
    assert proxies["date"].max() < pd.Timestamp("1992-01-01")
    assert actuals["date"].min() == pd.Timestamp("1992-01-01")
    assert len(actuals) == 12
    assert (result.frame["rule_id"] == "r").all()


def test_no_proxy_overwrites_actual() -> None:
    donor = _series([float(i) for i in range(36)], start="1990-01-01")
    target = _series([100.0 + i for i in range(12)], start="1992-01-01")
    rule = ProxyRule(
        "r", "t", "d", "regression", overlap_start="1992-01-01", overlap_end="1992-12-01"
    )
    result = splice(rule, target, donor)
    merged = result.frame.set_index("date")
    for _, row in target.assign(date=pd.to_datetime(target["date"])).iterrows():
        v = merged.loc[row["date"]]
        assert v["is_proxy"] == False  # noqa: E712
        assert v["value"] == row["value"]  # actual preserved exactly


def test_splice_pinned_uses_frozen_fit_and_handles_empty_target() -> None:
    """Campaign-2: the hy_oas_pre1996 fit is PINNED (owner decision 2026-08-02 --
    its only licensed fitting window lies inside the holdout span). splice_pinned
    must (a) never fit, (b) proxy every row when the target is empty (the
    train+validation case), (c) leave actuals untouched when present."""
    from ah.data.splice import PINNED_FITS, PROXY_RULES, splice_pinned

    rule = PROXY_RULES["hy_oas_pre1996"]
    fit = PINNED_FITS["hy_oas_pre1996"]
    donor = _series([1.0, 2.0, 3.0], start="1990-01-01")

    empty = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})
    result = splice_pinned(rule, empty, donor)
    assert len(result.frame) == 3
    assert result.frame["is_proxy"].all()
    expected = fit.a + fit.b * pd.Series([1.0, 2.0, 3.0])
    assert (result.frame["value"].to_numpy() == expected.to_numpy()).all()
    assert result.fit is fit  # the frozen object, not a re-fit

    target = _series([9.9], start="1990-03-01")
    with_actual = splice_pinned(rule, target, donor)
    actuals = with_actual.frame[~with_actual.frame["is_proxy"]]
    assert len(actuals) == 1 and actuals["value"].iloc[0] == 9.9
    assert len(with_actual.frame[with_actual.frame["is_proxy"]]) == 2  # pre-target only


def test_splice_pinned_refuses_a_rule_with_no_pinned_fit() -> None:
    from ah.data.splice import PROXY_RULES, splice_pinned

    donor = _series([1.0], start="1990-01-01")
    empty = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})
    with pytest.raises(ValueError, match="no pinned fit"):
        splice_pinned(PROXY_RULES["fx_usd_pre2006"], empty, donor)


def test_scale_transform_no_fit_needed() -> None:
    donor = _series([10.0, 20.0], start="1990-01-01")
    target = _series([5.0], start="1992-01-01")
    rule = ProxyRule("r", "t", "d", "scale", factor=0.6)
    result = splice(rule, target, donor)
    proxies = result.frame[result.frame["is_proxy"]]
    assert np.allclose(np.asarray(proxies["value"]), [6.0, 12.0])  # donor * 0.6


# --------------------------------------------------------------------------- #
# property: on the overlap, transformed donor tracks the target within tolerance
# --------------------------------------------------------------------------- #


@settings(max_examples=40, deadline=None)
@given(
    a=st.floats(-5, 5),
    b=st.floats(0.5, 3.0),
    noise=st.floats(0.0, 0.2),
    seed=st.integers(0, 10_000),
)
def test_overlap_error_within_tolerance(a: float, b: float, noise: float, seed: int) -> None:
    rng = np.random.Generator(np.random.PCG64(seed))
    n = 60
    donor_vals = np.linspace(1.0, 10.0, n)
    target_vals = a + b * donor_vals + rng.normal(0, noise, n)
    donor = _series(list(donor_vals), start="1990-01-01")
    target = _series(list(target_vals), start="1990-01-01")
    rule = ProxyRule(
        "r", "t", "d", "regression", overlap_start="1990-01-01", overlap_end="1999-12-01"
    )
    # RMSE on the overlap is bounded by a few sigma of the injected noise
    assert overlap_error(rule, target, donor) <= 3.0 * noise + 1e-6
