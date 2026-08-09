"""Extend ``ust_2y`` below 1976 by curve interpolation (WP-DATA-UST2YEXT).

Why this module exists
----------------------
``ust_2y`` (``fred.DGS2``) begins 1976-06 and — after the VOLEXT, FSEXT and
HQMEXT extensions — is the binding factor of ``bootstrap_v1.block_draw_span``'s
reachable floor. Its curve neighbours ``fred.GS1`` and ``fred.GS3`` (1-year
and 3-year constant-maturity yields, monthly, live) are observed from
1953-04. Recreating the 2-year point from the observed points either side of
it on the same curve is interpolation, the mildest recreation in the whole
extension family. Owner rulings U1-U3 (2026-08-09, recorded in
``docs/superpowers/specs/2026-08-09-ust2yext-decisions.md``): the recreation
is accepted; the registered construction is the two-donor regression (fitted
interpolation weights, nesting the plain average); the extension runs to the
donors' 1953-04 start.

Discipline, following the VOLEXT/FSEXT/HQMEXT family
----------------------------------------------------
``ah.data.splice`` and ``ah.data.derive`` are hashed by
``pre-registration.lock``; this module consumes the framework read-only and
nothing sealed learns the rule (a test pins it). Backward fill only; an
observed month is never overwritten; every filled row carries
``is_proxy=True`` and the rule id; nothing consumes the output until the
owner ratifies the span amendment. Aggregation note: DGS2 arrives daily and
the connector's D->M rule takes the monthly MEAN, matching GS1/GS3, which
ARE monthly averages — like is fitted against like.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.splice import ProxyRule

__all__ = [
    "MIN_OVERLAP_MONTHS",
    "UST2Y_RULE",
    "TwoDonorFit",
    "Ust2yExtension",
    "extend_ust2y",
    "fit_curve",
    "overlap_stats",
]

#: The rule, in the sealed registry's own shape so ratification can move it
#: verbatim. ``transform`` names the link this module implements; the sealed
#: ``splice.fit_transform`` would reject it, which is correct.
UST2Y_RULE = ProxyRule(
    rule_id="PROXY-UST2Y-GS1GS3-V1",
    target="fred.DGS2",
    donor="fred.GS1 + fred.GS3",
    transform="two_donor_regression",
    overlap_start="1976-06-01",
    doc=(
        "2-year constant-maturity yield interpolated from its observed curve "
        "neighbours: ust_2y = a + b1*GS1 + b2*GS3, fitted on the 1976+ "
        "overlap. Accepted by owner ruling U1 as interpolation between "
        "observed points on the same curve."
    ),
)

#: Below this many overlapping months the fit is refused.
MIN_OVERLAP_MONTHS = 60


@dataclass(frozen=True)
class TwoDonorFit:
    """``target = a + b1 * donor1 + b2 * donor2``, OLS on the overlap."""

    a: float
    b1: float
    b2: float
    n_obs: int
    overlap: tuple[str, str]

    def predict(self, d1: np.ndarray, d2: np.ndarray) -> np.ndarray:
        return self.a + self.b1 * d1 + self.b2 * d2


@dataclass(frozen=True)
class Ust2yExtension:
    """The extended series, splice-shaped: ``date, value, is_proxy, rule_id``."""

    series_id: str
    frame: pd.DataFrame
    fit: TwoDonorFit


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


def fit_curve(
    dgs2: pd.DataFrame,
    gs1: pd.DataFrame,
    gs3: pd.DataFrame,
    rule: ProxyRule = UST2Y_RULE,
) -> TwoDonorFit:
    """Fit the interpolation weights on the overlap; refuse under 60 months."""
    t, d1, d3 = _monthly(dgs2), _monthly(gs1), _monthly(gs3)
    common = t.index.intersection(d1.index).intersection(d3.index)
    if rule.overlap_start is not None:
        common = common[common >= pd.Timestamp(rule.overlap_start)]
    if rule.overlap_end is not None:
        common = common[common <= pd.Timestamp(rule.overlap_end)]
    if len(common) < MIN_OVERLAP_MONTHS:
        raise ValueError(
            f"rule {rule.rule_id}: overlap too short to fit "
            f"({len(common)} months, need >= {MIN_OVERLAP_MONTHS})"
        )
    y = t.loc[common].to_numpy()
    design = np.column_stack(
        [np.ones(len(common)), d1.loc[common].to_numpy(), d3.loc[common].to_numpy()]
    )
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return TwoDonorFit(
        a=float(coef[0]),
        b1=float(coef[1]),
        b2=float(coef[2]),
        n_obs=len(common),
        overlap=(str(common.min().date()), str(common.max().date())),
    )


def extend_ust2y(
    dgs2: pd.DataFrame,
    gs1: pd.DataFrame,
    gs3: pd.DataFrame,
    rule: ProxyRule = UST2Y_RULE,
) -> Ust2yExtension:
    """Extend the observed 2y yield backward with the fitted interpolation.

    Backward only (the target is live); an observed month is never
    overwritten; proxies fill exactly the months BOTH donors cover before
    the target's first observation.
    """
    fit = fit_curve(dgs2, gs1, gs3, rule)
    t, d1, d3 = _monthly(dgs2), _monthly(gs1), _monthly(gs3)
    pre = d1.index.intersection(d3.index)
    pre = pre[pre < t.index.min()]
    proxy = pd.DataFrame(
        {
            "date": pre,
            "value": fit.predict(d1.loc[pre].to_numpy(), d3.loc[pre].to_numpy()),
            "is_proxy": True,
        }
    )
    actual = pd.DataFrame({"date": t.index, "value": t.to_numpy(), "is_proxy": False})
    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return Ust2yExtension(f"{rule.target}__extended", out, fit)


def overlap_stats(
    dgs2: pd.DataFrame,
    gs1: pd.DataFrame,
    gs3: pd.DataFrame,
    rule: ProxyRule = UST2Y_RULE,
) -> dict[str, float]:
    """RMSE and correlation of the fitted interpolation vs the target."""
    fit = fit_curve(dgs2, gs1, gs3, rule)
    t, d1, d3 = _monthly(dgs2), _monthly(gs1), _monthly(gs3)
    common = t.index.intersection(d1.index).intersection(d3.index)
    if rule.overlap_start is not None:
        common = common[common >= pd.Timestamp(rule.overlap_start)]
    if rule.overlap_end is not None:
        common = common[common <= pd.Timestamp(rule.overlap_end)]
    actual = t.loc[common].to_numpy()
    pred = fit.predict(d1.loc[common].to_numpy(), d3.loc[common].to_numpy())
    return {
        "n_obs": float(fit.n_obs),
        "a": fit.a,
        "b1": fit.b1,
        "b2": fit.b2,
        "rmse": float(np.sqrt(np.mean((actual - pred) ** 2))),
        "corr": float(np.corrcoef(actual, pred)[0, 1]),
    }
