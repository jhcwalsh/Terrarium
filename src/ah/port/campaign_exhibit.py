"""Campaign R1 Track A — the twin over observed factor history (exhibit).

Outside both pre-registration locks by design: this module audits how the
translation layer behaves under the AM-2026-08-08-002 artifacts; nothing here
is judged, and nothing judged imports it. See
docs/superpowers/specs/2026-08-08-campaign-r1-design.md.

The prior/measured asymmetry is deliberate and IS the experiment:
``source="prior"`` reproduces the frozen pm_growth_loadings convention
(beta * factor, no alpha — the G1-replay convention), ``source="measured"``
uses the fitted row with its alpha. Their difference is exactly the change
adopting the measured loadings would make.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

CAMPAIGN_VINTAGE = "2026-08-07.5"

#: window -> (start, end). y2022 matches run_2022_replay.py's WINDOW.
WINDOWS: dict[str, tuple[str, str]] = {
    "full_span": ("1990-01-01", "2026-06-30"),
    "gfc": ("2007-07-01", "2009-12-31"),
    "covid": ("2020-01-01", "2020-12-31"),
    "y2022": ("2021-12-01", "2023-12-31"),
}

#: mapping regressor -> the observed series that realize it (I4/I6 wiring).
#: french.mkt_rf stays first: the missing-series error names its regressor.
_REGRESSOR_SOURCES: dict[str, tuple[str, ...]] = {
    "equity_mkt": ("french.mkt_rf", "french.rf"),
    "smb": ("french.smb",),
    "hml": ("french.hml",),
    "mom": ("french.mom",),
    "d_level": ("fred.DGS10",),
    "d_slope": ("fred.DGS10", "fred.DGS2"),
    "d_ig": ("fred.BAA", "fred.AAA"),
}


def _series(catalog: Any, vintage: str, sid: str) -> pd.Series:
    try:
        frame = catalog.read_observations(vintage, sid)
    except Exception as exc:  # an exhibit hard-fails; it never backfills silence
        needed_for = [k for k, v in _REGRESSOR_SOURCES.items() if sid in v]
        raise SystemExit(
            f"campaign R1: series '{sid}' unreadable on vintage {vintage} "
            f"(needed for regressor(s) {needed_for}): {exc}"
        ) from exc
    return pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
    )


def load_regressors(catalog: Any, vintage: str) -> pd.DataFrame:
    """Monthly regressor frame on the campaign vintage, common span, no NaNs."""
    s: dict[str, pd.Series] = {}
    for sources in _REGRESSOR_SOURCES.values():
        for sid in sources:
            if sid not in s:
                s[sid] = _series(catalog, vintage, sid)
    cols = {
        "equity_mkt": s["french.mkt_rf"] + s["french.rf"],
        "smb": s["french.smb"],
        "hml": s["french.hml"],
        "mom": s["french.mom"],
        "d_level": s["fred.DGS10"].diff(),
        "d_slope": (s["fred.DGS10"] - s["fred.DGS2"]).diff(),
        "d_ig": (s["fred.BAA"] - s["fred.AAA"]).diff(),
        # STATE column, not a mapping regressor: f_dist needs the spread LEVEL,
        # which cannot be reconstructed from d_ig changes within a window.
        "ig_level": s["fred.BAA"] - s["fred.AAA"],
    }
    frame = pd.DataFrame(cols).dropna()
    if frame.empty:
        raise SystemExit(f"campaign R1: empty regressor frame on vintage {vintage}")
    return frame


def hf_sleeve_returns(reg: pd.DataFrame, mapping: dict) -> dict[str, pd.Series]:
    """Monthly HF sleeve returns from the mapping's ``sleeves:`` block."""
    out: dict[str, pd.Series] = {}
    for sleeve, spec in mapping["sleeves"].items():
        r = pd.Series(float(spec["alpha_monthly"]), index=reg.index)
        for name, beta in spec["loadings"].items():
            if float(beta) != 0.0:
                r = r + float(beta) * reg[name]
        out[sleeve] = r
    return out


def pm_sleeve_returns(reg_q: pd.DataFrame, mapping: dict, *, source: str) -> dict[str, pd.Series]:
    """Quarterly PM sleeve returns under the prior or the measured loadings.

    ``source="prior"`` reproduces the frozen pm_growth_loadings convention
    (beta * factor, no alpha); ``"measured"`` uses the fitted row with its
    alpha. The asymmetry is the experiment — see the module docstring.
    """
    if source not in ("prior", "measured"):
        raise ValueError(f"source must be 'prior' or 'measured', got {source!r}")
    out: dict[str, pd.Series] = {}
    for sleeve, spec in mapping["pm_sleeves"].items():
        if source == "prior":
            r = pd.Series(0.0, index=reg_q.index)
            for name, beta in spec["prior_superseded"].items():
                if name != "source" and float(beta) != 0.0:
                    r = r + float(beta) * reg_q[name]
        else:
            r = pd.Series(float(spec["alpha_quarterly"]), index=reg_q.index)
            for name, beta in spec["loadings"].items():
                if float(beta) != 0.0:
                    r = r + float(beta) * reg_q[name]
        out[sleeve] = r
    return out


def geltner_report(true: np.ndarray, *, a: float, phi: float) -> np.ndarray:
    """Forward AR(1) partial adjustment: reported[t] = phi*reported[t-1] + a*true[t]."""
    x = np.asarray(true, dtype=float)
    rep = np.empty_like(x)
    prev = 0.0
    for t, value in enumerate(x):
        prev = phi * prev + a * float(value)
        rep[t] = prev
    return rep


def reported_plane(sleeve_id: str, true: pd.Series) -> pd.Series:
    """The sleeve's reported returns under its OWN smoothing family.

    Family resolution is read-only through the sealed taxonomy
    (``ah.eval.sleevetails.smoothing_family``) so the exhibit cannot drift
    from the judged classification; HF sleeves are always GLM.
    """
    from ah.eval.sleevetails import smoothing_family
    from ah.port import smoothing as sk

    family = "glm" if sleeve_id.startswith("hf_") else smoothing_family(sleeve_id)
    values = true.to_numpy(dtype=float)
    if family == "geltner":
        a, phi = sk.geltner_for(sleeve_id)
        reported = geltner_report(values, a=a, phi=phi)
    else:
        reported = sk.smooth(values, sk.theta_for(sleeve_id))
    return pd.Series(reported, index=true.index)


def load_real_mapping() -> dict:
    """The committed sleeve-mappings artifact, read-only."""
    from ah.port.mapping import load_artifact

    return load_artifact()


# The exhibit's institution — chosen, stated, and NOT a sealed reference book:
# 30% private (one mid-life buyout cohort, the committed fixture document),
# the liquid 70% split 60/40 public equity / equal-weight HF composite,
# cash 4% of book on top. Policy() defaults throughout.
_PRIVATE_WEIGHT = 0.30
_PUBLIC_SHARE_OF_LIQUID = 0.60
_CASH_FRACTION = 0.04
_TWIN_PM_SLEEVE = "pm_buyout"  # the fixture cohort's shape


@dataclass(frozen=True)
class WindowResult:
    window: str
    source: str
    quarters: int
    end_nav: float
    max_dd_true: float
    max_dd_reported: float
    calls_paid: float
    distributions: float
    forced_sale_quarters: int
    forced_sale_total: float
    min_coverage: float
    peak_private_weight_reported: float
    breach_quarters: int


def _quarterly(reg: pd.DataFrame) -> pd.DataFrame:
    """Quarter sums for returns/changes; quarter-end LAST for the state level."""
    out = reg.drop(columns=["ig_level"], errors="ignore").resample("QE").sum()
    if "ig_level" in reg.columns:
        out["ig_level"] = reg["ig_level"].resample("QE").last()
    return out


def run_window(name: str, reg: pd.DataFrame, mapping: dict, *, source: str) -> WindowResult:
    """One deterministic pass of the twin over an observed window.

    ``breach_quarters`` counts REPORTED-plane breaches — the plane policy
    actually acts on.
    """
    import json
    from pathlib import Path

    from ah.port.cashflow_tier1 import f_call, f_dist
    from ah.port.cohort import ClosedEndCohort
    from ah.port.engine import Policy, PortfolioEngine
    from ah.port.portfolio import Portfolio
    from ah.port.sleeves import LiquidSleeve

    repo_root = Path(__file__).resolve().parents[3]
    reg_q = _quarterly(reg)
    quarters = len(reg_q)
    if quarters < 1:
        raise SystemExit(f"campaign R1: window '{name}' has no complete quarter")

    # sleeve returns on both planes
    hf = hf_sleeve_returns(reg, mapping)
    hf_true_m = sum(hf.values()) / len(hf)
    hf_true_q = hf_true_m.resample("QE").sum().reindex(reg_q.index).fillna(0.0)
    pm_true_q = pm_sleeve_returns(reg_q, mapping, source=source)[_TWIN_PM_SLEEVE]
    pm_rep_q = reported_plane(_TWIN_PM_SLEEVE, pm_true_q)
    public_q = ((1.0 + reg["equity_mkt"]).resample("QE").prod() - 1.0).reindex(reg_q.index)

    # cashflow states: equity drawdown depth, spread ratio vs the window's
    # first-year mean, floored at 0.5 (the run_2022_replay construction)
    cum = (1.0 + reg["equity_mkt"]).cumprod()
    depth_q = (1.0 - cum / cum.cummax()).clip(lower=0.0).resample("QE").last()
    anchor = float(reg["ig_level"].iloc[:12].mean())
    ratio_q = (reg["ig_level"] / anchor).clip(lower=0.5).resample("QE").last()

    # the book at the door
    base = json.loads(
        (repo_root / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )
    cohort = ClosedEndCohort.from_document(base)
    cohort.report(cohort.nav_true)  # reported meets true at the window door
    private_start = cohort.nav_true
    liquid_total = private_start * (1.0 - _PRIVATE_WEIGHT) / _PRIVATE_WEIGHT
    liquid_doc = json.loads(
        (repo_root / "fixtures" / "state" / "liquid-sleeve.example.json").read_text("utf-8")
    )
    sleeves: dict[str, LiquidSleeve] = {}
    for key, share in (
        ("public_equity", _PUBLIC_SHARE_OF_LIQUID),
        ("hf_composite", 1.0 - _PUBLIC_SHARE_OF_LIQUID),
    ):
        doc = json.loads(json.dumps(liquid_doc))
        doc["identity"] = {**doc["identity"], "sleeve_id": key}
        doc["value"] = liquid_total * share
        doc["weight"] = share * (1.0 - _PRIVATE_WEIGHT)
        sleeves[key] = LiquidSleeve.from_document(doc)

    portfolio = Portfolio(cash=_CASH_FRACTION * (private_start + liquid_total))
    portfolio.add(_TWIN_PM_SLEEVE, cohort)
    for key, sleeve in sleeves.items():
        portfolio.add(key, sleeve)
    engine = PortfolioEngine(portfolio, Policy())

    nav_true_path = [portfolio.nav_true()]
    nav_rep_path = [portfolio.nav_reported()]
    calls_total = dist_total = forced_total = 0.0
    forced_quarters = breach_quarters = 0
    min_coverage = float("inf")
    peak_w_rep = portfolio.private_weight_reported()

    for t in range(quarters):
        sleeves["public_equity"].apply_return(float(public_q.iloc[t]))
        sleeves["hf_composite"].apply_return(float(hf_true_q.iloc[t]))
        fc = f_call(float(depth_q.iloc[t]))
        fd = f_dist(float(depth_q.iloc[t]), float(ratio_q.iloc[t]))
        step = cohort.step(float(pm_true_q.iloc[t]), f_call=fc, f_dist=fd)
        cohort.report(cohort.nav_reported * (1.0 + float(pm_rep_q.iloc[t])))
        report = engine.run_quarter(distributions=step.distribution_total, calls=step.call)
        calls_total += report.calls_paid
        dist_total += report.distributions_received
        forced_total += report.forced_sale_total
        forced_quarters += int(report.forced_sale_total > 0.0)
        breach_quarters += int(report.breach_reported)
        min_coverage = min(min_coverage, report.coverage_true)
        peak_w_rep = max(peak_w_rep, report.private_weight_reported)
        nav_true_path.append(portfolio.nav_true())
        nav_rep_path.append(portfolio.nav_reported())

    def _max_dd(path: list[float]) -> float:
        arr = np.asarray(path, dtype=float)
        return float((arr / np.maximum.accumulate(arr) - 1.0).min())

    return WindowResult(
        window=name,
        source=source,
        quarters=quarters,
        end_nav=float(nav_true_path[-1]),
        max_dd_true=_max_dd(nav_true_path),
        max_dd_reported=_max_dd(nav_rep_path),
        calls_paid=calls_total,
        distributions=dist_total,
        forced_sale_quarters=forced_quarters,
        forced_sale_total=forced_total,
        min_coverage=min_coverage,
        peak_private_weight_reported=peak_w_rep,
        breach_quarters=breach_quarters,
    )
