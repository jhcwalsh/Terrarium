"""Extend ``hqm_curve`` (the 10y HQM corporate spot rate) below 1984 (WP-DATA-HQMEXT).

Why this module exists
----------------------
Despite its name, the ``hqm_curve`` factor consumes ONE series: the 10-year
HQM corporate spot rate (``treasury.hqm_curve`` = FRED ``HQMCB10YR``), which
begins 1984-01 and — after the VOLEXT and FSEXT extensions — is the binding
factor of ``bootstrap_v1.block_draw_span``'s reachable floor. Moody's Aaa
seasoned corporate bond yield (``fred.AAA``) is the same economic object —
the high-grade corporate borrowing rate — observed monthly since 1919-01,
live, and already a registered P0 series. Owner rulings H1-H3 (2026-08-09,
recorded in ``docs/superpowers/specs/2026-08-09-hqmext-decisions.md``):
the recreation is accepted with the maturity/composition mismatch disclosed;
the registered construction is the simple level regression, with a
term-slope variant computed as a DIAGNOSTIC only; the extension runs to the
donor's 1919-01 start, with pre-1934 months panel-irrelevant until other
factors reach there.

The mismatch, stated
--------------------
Aaa is a seasoned ~20y+ Aaa-only portfolio yield; HQM 10y is a spot,
exactly-ten-year, A/AA/AAA-blend rate. The level fit on their ~500-month
overlap absorbs the average difference; the TIME-VARYING part is the term
premium between 10y and long maturities, violently variable in 1979-82.
:func:`slope_diagnostic` measures exactly that: it fits the alternative
``HQM10 = a + b*Aaa + c*(Aaa - GS10)`` on the overlap, extrapolates both
constructions over 1953-1983 (GS10's pre-HQM life), and reports where and
by how much they diverge — the owner's revisit trigger, not a silent model
choice.

Discipline, following ``ah.data.vol_extend`` and ``ah.data.funding_extend``
---------------------------------------------------------------------------
``ah.data.splice`` and ``ah.data.derive`` are hashed by
``pre-registration.lock``; this module consumes the framework read-only and
nothing sealed learns the rule (a test pins it). Backward fill only — the
target is live, so there is no forward hole. An observed month is never
overwritten; every filled row carries ``is_proxy=True`` and the rule id;
nothing consumes the output until the owner ratifies the span amendment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.funding_extend import LevelFit
from ah.data.splice import ProxyRule

__all__ = [
    "HQM_RULE",
    "MIN_OVERLAP_MONTHS",
    "HqmExtension",
    "extend_hqm",
    "fit_aaa",
    "overlap_stats",
    "slope_diagnostic",
]

#: The rule, in the sealed registry's own shape so ratification can move it
#: verbatim. ``transform`` names the link this module implements; the sealed
#: ``splice.fit_transform`` would reject it, which is correct.
HQM_RULE = ProxyRule(
    rule_id="PROXY-HQM10-AAA-V1",
    target="treasury.hqm_curve",
    donor="fred.AAA",
    transform="level_regression",
    overlap_start="1984-01-01",
    doc=(
        "Moody's Aaa seasoned long corporate yield mapped to the 10y HQM spot "
        "rate by level regression on the 1984+ overlap. Seasoned ~20y+ "
        "Aaa-only vs spot 10y A/AA/AAA blend -- accepted as the recreation by "
        "owner ruling H1; the time-varying maturity premium is measured by "
        "slope_diagnostic, not assumed away."
    ),
)

#: Below this many overlapping months the fit is refused.
MIN_OVERLAP_MONTHS = 60


@dataclass(frozen=True)
class HqmExtension:
    """The extended series, splice-shaped: ``date, value, is_proxy, rule_id``."""

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


def _overlap(target: pd.Series, donor: pd.Series, rule: ProxyRule) -> pd.DatetimeIndex:
    common = target.index.intersection(donor.index)
    if rule.overlap_start is not None:
        common = common[common >= pd.Timestamp(rule.overlap_start)]
    if rule.overlap_end is not None:
        common = common[common <= pd.Timestamp(rule.overlap_end)]
    return common


def fit_aaa(hqm: pd.DataFrame, aaa: pd.DataFrame, rule: ProxyRule = HQM_RULE) -> LevelFit:
    """Fit ``HQM10 = a + b * Aaa`` on the overlap; refuse under 60 months."""
    t, d = _monthly(hqm), _monthly(aaa)
    common = _overlap(t, d, rule)
    if len(common) < MIN_OVERLAP_MONTHS:
        raise ValueError(
            f"rule {rule.rule_id}: overlap too short to fit "
            f"({len(common)} months, need >= {MIN_OVERLAP_MONTHS})"
        )
    y = t.loc[common].to_numpy()
    x = d.loc[common].to_numpy()
    b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
    a = float(y.mean() - b * x.mean())
    return LevelFit(
        a=a, b=b, n_obs=len(common), overlap=(str(common.min().date()), str(common.max().date()))
    )


def extend_hqm(hqm: pd.DataFrame, aaa: pd.DataFrame, rule: ProxyRule = HQM_RULE) -> HqmExtension:
    """Extend the observed HQM 10y backward with the fitted Aaa donor.

    Backward only (the target is live); an observed month is never
    overwritten; proxies fill exactly the donor months before the target's
    first observation.
    """
    fit = fit_aaa(hqm, aaa, rule)
    t, d = _monthly(hqm), _monthly(aaa)
    pre = d.loc[d.index < t.index.min()]
    proxy = pd.DataFrame(
        {"date": pre.index, "value": fit.predict(pre.to_numpy()), "is_proxy": True}
    )
    actual = pd.DataFrame({"date": t.index, "value": t.to_numpy(), "is_proxy": False})
    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return HqmExtension(f"{rule.target}__extended", out, fit)


def overlap_stats(
    hqm: pd.DataFrame, aaa: pd.DataFrame, rule: ProxyRule = HQM_RULE
) -> dict[str, float]:
    """RMSE and correlation of the fitted donor vs the target on the overlap."""
    fit = fit_aaa(hqm, aaa, rule)
    t, d = _monthly(hqm), _monthly(aaa)
    common = _overlap(t, d, rule)
    actual = t.loc[common].to_numpy()
    pred = fit.predict(d.loc[common].to_numpy())
    return {
        "n_obs": float(fit.n_obs),
        "a": fit.a,
        "b": fit.b,
        "rmse": float(np.sqrt(np.mean((actual - pred) ** 2))),
        "corr": float(np.corrcoef(actual, pred)[0, 1]),
    }


def slope_diagnostic(
    hqm: pd.DataFrame,
    aaa: pd.DataFrame,
    gs10: pd.DataFrame,
    rule: ProxyRule = HQM_RULE,
) -> dict[str, float]:
    """The H2 diagnostic: does the maturity premium matter where we cannot check?

    Fits the alternative ``HQM10 = a + b*Aaa + c*(Aaa - GS10)`` on the
    overlap, then extrapolates BOTH constructions over GS10's pre-HQM life
    (1953..the overlap start) and reports the divergence — its mean, max and
    the month it peaks. A large divergence concentrated in 1979-82 is the
    revisit trigger owner ruling H2 names; the registered construction stays
    the simple fit either way.
    """
    t, d, g = _monthly(hqm), _monthly(aaa), _monthly(gs10)
    common = _overlap(t, d, rule).intersection(g.index)
    if len(common) < MIN_OVERLAP_MONTHS:
        raise ValueError("slope diagnostic: overlap too short")
    y = t.loc[common].to_numpy()
    x1 = d.loc[common].to_numpy()
    x2 = (d.loc[common] - g.loc[common]).to_numpy()
    design = np.column_stack([np.ones(len(common)), x1, x2])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid_b = y - design @ coef
    simple = fit_aaa(hqm, aaa, rule)
    resid_a = y - simple.predict(x1)

    pre = d.index.intersection(g.index)
    pre = pre[pre < pd.Timestamp(str(rule.overlap_start))]
    pa = simple.predict(d.loc[pre].to_numpy())
    pb = coef[0] + coef[1] * d.loc[pre].to_numpy() + coef[2] * (d.loc[pre] - g.loc[pre]).to_numpy()
    diff = np.abs(pa - pb)
    worst = int(np.argmax(diff))
    return {
        "n_overlap": float(len(common)),
        "slope_coef": float(coef[2]),
        "overlap_rmse_simple": float(np.sqrt(np.mean(resid_a**2))),
        "overlap_rmse_slope": float(np.sqrt(np.mean(resid_b**2))),
        "n_pre_months_compared": float(len(pre)),
        "divergence_mean": float(diff.mean()),
        "divergence_max": float(diff.max()),
        "divergence_worst_month": float(pre[worst].year * 100 + pre[worst].month),
    }
