"""Extend ``ust_10y`` below 1962 with its own monthly ancestor (WP-DATA-SPAN53).

``ust_10y`` (``fred.DGS10``, daily, 1962-01) and ``fred.GS10`` (monthly,
1953-04) are the SAME quantity — the 10-year constant-maturity Treasury
yield — published daily versus as a monthly average. The connector's D->M
rule already takes the monthly mean of DGS10, so the overlap fit compares
like with like and should be nearly an identity; the fit measures the
residual rather than assuming it. Owner ruling 2026-08-09 ("go with
1953-04"): this is one of the two donors for the span-53 ratification.

Same discipline as the whole extension family: sealed surfaces untouched
(tested), backward fill only, observed months never overwritten, every
filled row flagged under the rule id, nothing consumed until ratification.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.funding_extend import LevelFit
from ah.data.splice import ProxyRule

__all__ = [
    "MIN_OVERLAP_MONTHS",
    "UST10Y_RULE",
    "Ust10yExtension",
    "extend_ust10y",
    "fit_gs10",
    "overlap_stats",
]

UST10Y_RULE = ProxyRule(
    rule_id="PROXY-UST10Y-GS10-V1",
    target="fred.DGS10",
    donor="fred.GS10",
    transform="level_regression",
    overlap_start="1962-01-01",
    doc=(
        "The 10y CMT yield's monthly-average ancestor (GS10, 1953-04) mapped "
        "onto monthly-mean DGS10 by level regression on the 1962+ overlap -- "
        "near-identity by construction; the fit measures the residual."
    ),
)

MIN_OVERLAP_MONTHS = 60


@dataclass(frozen=True)
class Ust10yExtension:
    series_id: str
    frame: pd.DataFrame
    fit: LevelFit


def _monthly(frame: pd.DataFrame) -> pd.Series:
    s = (
        frame.assign(date=pd.to_datetime(frame["date"]))
        .set_index("date")["value"]
        .astype(float)
        .dropna()
        .sort_index()
    )
    if not s.index.is_unique:
        raise ValueError("duplicate dates in input frame")
    return s


def fit_gs10(dgs10: pd.DataFrame, gs10: pd.DataFrame, rule: ProxyRule = UST10Y_RULE) -> LevelFit:
    t, d = _monthly(dgs10), _monthly(gs10)
    common = t.index.intersection(d.index)
    common = common[common >= pd.Timestamp(str(rule.overlap_start))]
    if len(common) < MIN_OVERLAP_MONTHS:
        raise ValueError(
            f"rule {rule.rule_id}: overlap too short to fit "
            f"({len(common)} months, need >= {MIN_OVERLAP_MONTHS})"
        )
    y, x = t.loc[common].to_numpy(), d.loc[common].to_numpy()
    b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
    a = float(y.mean() - b * x.mean())
    return LevelFit(
        a=a, b=b, n_obs=len(common), overlap=(str(common.min().date()), str(common.max().date()))
    )


def extend_ust10y(
    dgs10: pd.DataFrame, gs10: pd.DataFrame, rule: ProxyRule = UST10Y_RULE
) -> Ust10yExtension:
    """Backward fill only; an observed month is never overwritten."""
    fit = fit_gs10(dgs10, gs10, rule)
    t, d = _monthly(dgs10), _monthly(gs10)
    pre = d.loc[d.index < t.index.min()]
    proxy = pd.DataFrame(
        {"date": pre.index, "value": fit.predict(pre.to_numpy()), "is_proxy": True}
    )
    actual = pd.DataFrame({"date": t.index, "value": t.to_numpy(), "is_proxy": False})
    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return Ust10yExtension(f"{rule.target}__extended", out, fit)


def overlap_stats(
    dgs10: pd.DataFrame, gs10: pd.DataFrame, rule: ProxyRule = UST10Y_RULE
) -> dict[str, float]:
    fit = fit_gs10(dgs10, gs10, rule)
    t, d = _monthly(dgs10), _monthly(gs10)
    common = t.index.intersection(d.index)
    common = common[common >= pd.Timestamp(str(rule.overlap_start))]
    actual = t.loc[common].to_numpy()
    pred = fit.predict(d.loc[common].to_numpy())
    return {
        "n_obs": float(fit.n_obs),
        "a": fit.a,
        "b": fit.b,
        "rmse": float(np.sqrt(np.mean((actual - pred) ** 2))),
        "corr": float(np.corrcoef(actual, pred)[0, 1]),
    }
