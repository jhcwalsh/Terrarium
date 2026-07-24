"""WP1.5 acceptance: splice/proxy transforms + invariants."""

from __future__ import annotations

import numpy as np
import pandas as pd
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
    }


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
