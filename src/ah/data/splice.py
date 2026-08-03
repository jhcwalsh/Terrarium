"""Splice & proxy framework — gap-filling that never lies (STEP1-DATA-PLAN §WP1.5).

A :class:`ProxyRule` extends a target series backward using a donor series through a
transform (level map, regression on the overlap, ratio link, or a documented fixed
scale). The result is a **new** series ``<target>__extended`` carrying a per-obs
``is_proxy`` flag and the rule id. Two invariants: on the overlap the transformed
donor tracks the actual target within fit tolerance, and **no proxy observation ever
overwrites an actual one** (proxies fill only pre-history the target does not cover).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

Transform = str  # "regression" | "level_map" | "ratio" | "scale"


@dataclass(frozen=True)
class ProxyRule:
    rule_id: str
    target: str
    donor: str
    transform: Transform
    overlap_start: str | None = None
    overlap_end: str | None = None
    factor: float | None = None  # for "scale"
    doc: str = ""


@dataclass
class SpliceFit:
    transform: Transform
    a: float = 0.0  # intercept / offset
    b: float = 1.0  # slope / ratio / scale


@dataclass
class SpliceResult:
    series_id: str
    frame: pd.DataFrame  # date, value, is_proxy, rule_id
    fit: SpliceFit


def _align(target: pd.DataFrame, donor: pd.DataFrame, lo: str | None, hi: str | None):
    t = target.assign(date=pd.to_datetime(target["date"])).set_index("date")["value"].astype(float)
    d = donor.assign(date=pd.to_datetime(donor["date"])).set_index("date")["value"].astype(float)
    common = t.index.intersection(d.index)
    if lo is not None:
        common = common[common >= pd.Timestamp(lo)]
    if hi is not None:
        common = common[common <= pd.Timestamp(hi)]
    return t, d, common


def fit_transform(rule: ProxyRule, target: pd.DataFrame, donor: pd.DataFrame) -> SpliceFit:
    if rule.transform == "scale":
        return SpliceFit("scale", a=0.0, b=float(rule.factor if rule.factor is not None else 1.0))

    t, d, common = _align(target, donor, rule.overlap_start, rule.overlap_end)
    if len(common) < 2:
        raise ValueError(f"rule {rule.rule_id}: <2 overlapping points to fit")
    y = t.loc[common].to_numpy()
    x = d.loc[common].to_numpy()

    if rule.transform == "regression":
        b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
        a = float(y.mean() - b * x.mean())
        return SpliceFit("regression", a=a, b=b)
    if rule.transform == "level_map":
        return SpliceFit("level_map", a=float((y - x).mean()), b=1.0)
    if rule.transform == "ratio":
        return SpliceFit("ratio", a=0.0, b=float((y / x).mean()))
    raise ValueError(f"unknown transform {rule.transform}")


def apply_fit(fit: SpliceFit, donor_values: np.ndarray) -> np.ndarray:
    if fit.transform in ("regression", "level_map"):
        return fit.a + fit.b * donor_values
    return fit.b * donor_values  # ratio / scale


def splice(rule: ProxyRule, target: pd.DataFrame, donor: pd.DataFrame) -> SpliceResult:
    """Extend ``target`` backward with transformed ``donor``; actuals are never touched."""
    fit = fit_transform(rule, target, donor)

    t = target.assign(date=pd.to_datetime(target["date"]))
    d = donor.assign(date=pd.to_datetime(donor["date"]))
    target_min = t["date"].min()

    actual = t[["date", "value"]].copy()
    actual["is_proxy"] = False

    pre = d[d["date"] < target_min].copy()
    pre["value"] = apply_fit(fit, pd.to_numeric(pre["value"]).to_numpy())
    proxy = pre[["date", "value"]].copy()
    proxy["is_proxy"] = True

    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return SpliceResult(f"{rule.target}__extended", out, fit)


def overlap_error(rule: ProxyRule, target: pd.DataFrame, donor: pd.DataFrame) -> float:
    """RMSE of the transformed donor vs the actual target on the overlap window."""
    fit = fit_transform(rule, target, donor)
    t, d, common = _align(target, donor, rule.overlap_start, rule.overlap_end)
    pred = apply_fit(fit, d.loc[common].to_numpy())
    resid = t.loc[common].to_numpy() - pred
    return float(np.sqrt(np.mean(resid**2)))


#: Campaign-2 PINNED fits (owner decision 2026-08-02, holdout-leakage containment).
#: The hy_oas_pre1996 rule's only licensed fitting window (2023-08..2026-07, 36 obs)
#: lies entirely inside the holdout span, so fitting it at read time would require a
#: full-span read path inside sealed code -- a structural exception to the leakage
#: guard ("DataAccess.train_val() is the only reference/normalization surface").
#: Instead the fit was performed ONCE, offline, and its two scalars are frozen here:
#: measured on vintage 2026-08-02.4 (overlap RMSE 0.2058317839495792). The residual
#: information flow from the post-2020 span into the training panel is exactly these
#: two published constants, disclosed in the campaign seal and the retrofit register.
#: A pinned fit is re-frozen only by the same owner-decision route that froze it.
PINNED_FITS: dict[str, SpliceFit] = {
    "hy_oas_pre1996": SpliceFit("regression", a=1.4068184862787785, b=2.53288508610114),
}


def splice_pinned(rule: ProxyRule, target: pd.DataFrame, donor: pd.DataFrame) -> SpliceResult:
    """:func:`splice` with the rule's PINNED fit -- no calibration at read time.

    Unlike :func:`splice`, the target may be EMPTY: on a train+validation read the
    pinned rules' targets have no observations at all (that is why they are pinned),
    and then every donor row becomes a proxy observation. Actuals, where present,
    are never touched, exactly as in :func:`splice`.
    """
    fit = PINNED_FITS.get(rule.rule_id)
    if fit is None:
        raise ValueError(f"rule {rule.rule_id} has no pinned fit; use splice() instead")

    t = target.assign(date=pd.to_datetime(target["date"]))
    d = donor.assign(date=pd.to_datetime(donor["date"]))

    actual = t[["date", "value"]].copy()
    actual["is_proxy"] = False

    pre = d if t.empty else d[d["date"] < t["date"].min()].copy()
    pre = pre.copy()
    pre["value"] = apply_fit(fit, pd.to_numeric(pre["value"]).to_numpy())
    proxy = pre[["date", "value"]].copy()
    proxy["is_proxy"] = True

    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return SpliceResult(f"{rule.target}__extended", out, fit)


# --------------------------------------------------------------------------- #
# register rules (STEP1-DATA-PLAN §WP1.5 / data-requirements-register)
# --------------------------------------------------------------------------- #

PROXY_RULES: dict[str, ProxyRule] = {
    "hy_oas_pre1996": ProxyRule(
        rule_id="hy_oas_pre1996",
        target="fred.HY_OAS",
        donor="derived.baa_aaa_spread",
        transform="regression",
        overlap_start="2023-08-01",
        overlap_end="2026-07-01",
        doc=(
            "HY OAS extended backward from the Baa-Aaa spread. CAMPAIGN-2 "
            "CORRECTION (RFR-92): the rule as first authored specified a "
            "1996-2005 overlap that FRED has NEVER served under the ICE "
            "licensing cap (~3 trailing years only; S2-CAMPAIGN-VINTAGE "
            "records 37 obs, all recent) -- the rule was unfittable from "
            "birth. The overlap is now the licensed window that actually "
            "exists (2023-08..2026-07, ~36 monthly obs): thin, but HY OAS "
            "and Baa-Aaa are tightly coupled and the fit quality is "
            "reported by the splice's own overlap-error check. Every "
            "extended observation is flagged is_proxy."
        ),
    ),
    "fedfunds_pre1954": ProxyRule(
        rule_id="fedfunds_pre1954",
        target="fred.FEDFUNDS",
        donor="fred.TB3MS",
        transform="regression",
        overlap_start="1954-07-01",
        overlap_end="1990-01-01",
        doc=(
            "Effective federal funds rate before 1954-07 (FRED's first observation) "
            "regressed on the 3-month Treasury bill rate over the 1954-1990 overlap. "
            "The funds rate is the administered policy rate the `policy_rate` factor "
            "is defined as; the bill is a market yield carrying term premium and "
            "policy expectations, so it is a documented PROXY for the pre-1954 "
            "pre-history only and every spliced observation is flagged is_proxy."
        ),
    ),
    "fx_usd_pre2006": ProxyRule(
        rule_id="fx_usd_pre2006",
        target="fred.DTWEXBGS",
        donor="fred.DTWEXM",
        transform="regression",
        overlap_start="2006-01-01",
        overlap_end="2019-12-01",
        doc=(
            "Trade-weighted broad dollar index before 2006-01 (DTWEXBGS's first "
            "observation) regressed on the discontinued major-currencies index "
            "DTWEXM over the 2006-2019 overlap (the donor's full remaining life). "
            "Campaign-2's fx block (S2R-FX-NEXT-CAMPAIGN; R5 re-entry): the broad "
            "index is the honest modern series, the major-currencies index the "
            "only long-history donor, and every pre-2006 observation is a "
            "documented PROXY flagged is_proxy."
        ),
    ),
    "long_tsy_tr_pre1973": ProxyRule(
        rule_id="long_tsy_tr_pre1973",
        target="derived.long_tsy_tr",
        donor="derived.long_tsy_tr_from_yield",
        transform="regression",
        overlap_start="1973-01-01",
        overlap_end="1990-01-01",
        doc="Long-Treasury total return before 1973 constructed from yields (duration approx).",
    ),
    "private_credit_pre2004": ProxyRule(
        rule_id="private_credit_pre2004",
        target="cliffwater.cdli_ret_q",
        donor="derived.bdc_hy_blend",
        transform="regression",
        overlap_start="2004-09-01",
        overlap_end="2010-12-01",
        doc="Private credit before 2004 from a BDC/HY blend (donor prepared in derive).",
    ),
    "nareit_delevered_re": ProxyRule(
        rule_id="nareit_delevered_re",
        target="derived.re_delevered",
        donor="nareit.all_equity_tr",
        transform="scale",
        factor=0.6,
        doc="Nareit-derived de-levered RE proxy (cross-check); documented leverage haircut.",
    ),
}
