"""Derived metrics, regime labels, and the factor panel (STEP1-DATA-PLAN §WP1.6).

All derived series are catalogued with lineage (inputs + ruleset version). Functions
take canonical ``(date, value)`` frames and return the same shape. The regime labeller
is a single pure function plus a YAML of thresholds, version-stamped
``regime_ruleset_v1``. Panel assembly asserts no monthly gaps after each column's start
and carries a units registry; ``PANEL.md`` is generated, not hand-written.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

_THRESHOLDS_PATH = Path(__file__).parent / "regime_thresholds.yaml"
REGIME_LABELS = ["EXP", "SLOW", "REC", "CRI", "STAG", "REF"]


def _s(frame: pd.DataFrame) -> pd.Series:
    return frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")["value"].astype(float)


def _frame(series: pd.Series, name: str = "value") -> pd.DataFrame:
    return pd.DataFrame({"date": series.index, "value": series.to_numpy()}).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# (a) panel primitives
# --------------------------------------------------------------------------- #


def add(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """a + b on the common dates (excess return + risk-free = total return).

    The exact inverse of :func:`difference`, and used for the same reason: a series
    quoted net of another (Fama-French ``Mkt-RF`` is an excess return over the one-month
    bill) is put back onto a total-return numeraire by adding the series it was quoted
    net of, rather than by leaving the mismatch for a downstream portfolio to inherit.
    Both inputs must already be in the same units.
    """
    sa, sb = _s(a), _s(b)
    common = sa.index.intersection(sb.index)
    return _frame((sa.loc[common] + sb.loc[common]).sort_index())


def difference(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """a - b on the common dates (term/credit spreads, excess returns, real rates)."""
    sa, sb = _s(a), _s(b)
    common = sa.index.intersection(sb.index)
    return _frame((sa.loc[common] - sb.loc[common]).sort_index())


def hy_oas_spliced(hy: pd.DataFrame, baa: pd.DataFrame, aaa: pd.DataFrame) -> pd.DataFrame:
    """HY OAS extended backward with the Baa-Aaa donor (campaign-2 seal).

    Applies ``ah.data.splice.PROXY_RULES['hy_oas_pre1996']`` (RFR-92-corrected
    overlap) at the factor read surface via its PINNED fit
    (``splice.PINNED_FITS`` -- owner decision 2026-08-02: the rule's only
    licensed fitting window lies inside the holdout span, so the fit is frozen
    offline and no calibration happens at read time). On a train+validation
    read ``hy`` is empty and every row is proxy; actuals, where present, are
    never touched. The panel keeps its canonical ``(date, value)`` shape; proxy
    provenance is documented in ``factors.yaml`` and the retrofit register.
    """
    from ah.data import splice as sp

    result = sp.splice_pinned(sp.PROXY_RULES["hy_oas_pre1996"], hy, difference(baa, aaa))
    return result.frame[["date", "value"]].copy()


def fx_usd_spliced(broad: pd.DataFrame, major: pd.DataFrame) -> pd.DataFrame:
    """Broad trade-weighted dollar extended backward with the DTWEXM donor.

    Applies ``ah.data.splice.PROXY_RULES['fx_usd_pre2006']`` at the factor read
    surface (campaign-2 fx block, S2R-FX-NEXT-CAMPAIGN / R5 re-entry). Same
    contract as :func:`hy_oas_spliced`.
    """
    from ah.data import splice as sp

    result = sp.splice(sp.PROXY_RULES["fx_usd_pre2006"], broad, major)
    return result.frame[["date", "value"]].copy()


# --------------------------------------------------------------------------- #
# (a2) the extended factor reads (campaign-3 wiring; AM-2026-08-09-002)
#
# Each helper applies one of the seven ratified extension families AT THE READ
# SURFACE, exactly as hy_oas_spliced/fx_usd_spliced apply ah.data.splice. Two
# shared conventions, both chosen so a fixture vintage that predates the
# extended donors keeps its campaign-2 behaviour bit-for-bit:
#
# - A DONOR read that is EMPTY (the series is absent from the vintage, or the
#   panel's optional-input machinery substituted an empty frame) means the
#   extension does not engage and the unextended campaign-2 read is returned.
# - A fit refusal (the module's own ValueError: overlap shorter than the
#   family's MIN_OVERLAP_MONTHS) likewise falls back to the unextended read --
#   a short fixture overlap is a fact about the fixture, not an error. On the
#   live campaign-3 vintage every family's overlap is hundreds of months
#   (docs/data/*-REPORT.md) and the fallbacks are dead code there.
#
# Proxy provenance: every extension module flags its filled months is_proxy
# with a rule_id at source; this surface returns the canonical (date, value)
# shape and the per-factor proxy share is disclosed by the reporting layer
# (AM-2026-08-09-002's disclosure clause), not carried in the panel.
# --------------------------------------------------------------------------- #


def equity_vol_extended(vix: pd.DataFrame, vxo: pd.DataFrame) -> pd.DataFrame:
    """VIX extended to 1986-01 on observed VXO, then to 1953-04 on the pinned HAR draw.

    Applies ``PROXY-EQUITY-VOL-VXO-V1`` (``ah.data.vol_extend``, stage 1: a
    log-log fit of observed VXO onto VIX over the 1990+ overlap) and then
    prepends ``PROXY-EQUITY-VOL-HAR-V1``'s ONE pinned ensemble draw
    (``ah.data.vol_backcast.pinned_draw_series``; seed 20260809, materialized
    once, sha pinned by the campaign-3 pre-registration). The draw is model
    output and is prepended only when it lands flush against the extension
    (first observed/VXO month == 1986-01); on any other vintage shape it is
    withheld rather than leaving a panel gap that assemble_panel would refuse.
    """
    if vxo.empty:
        return vix[["date", "value"]].copy()
    from ah.data import vol_backcast as vb
    from ah.data import vol_extend as vx

    try:
        ext = vx.extend_equity_vol(vix, vxo)
    except ValueError:
        return vix[["date", "value"]].copy()
    frame = ext.frame[["date", "value"]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    first = frame["date"].min()
    junction = pd.Timestamp(f"{vb.PINNED_DRAW_SPAN[1]}-01") + pd.offsets.MonthBegin(1)
    if first != junction:
        return frame
    draw = vb.pinned_draw_series()
    pre = pd.DataFrame({"date": draw.index, "value": draw.to_numpy()})
    return pd.concat([pre, frame], ignore_index=True).sort_values(by="date", ignore_index=True)


def funding_spread_extended(
    ted: pd.DataFrame,
    cpf3m: pd.DataFrame,
    cp3m: pd.DataFrame,
    nber: pd.DataFrame,
    tb3m_sec: pd.DataFrame,
    tb3ms: pd.DataFrame,
) -> pd.DataFrame:
    """TED extended on BOTH ends with the fitted CP-bill spread (PROXY-FUNDING-CPBILL-V1).

    ``ah.data.funding_extend``: the commercial-paper leg chains
    CPF3M <- CP3M <- NBER by mean offset, the bill leg TB3M_SEC <- TB3MS, and
    ``TED = a + b * (CP - bill)`` is fitted on the observed overlap. Fills every
    month TED does not cover on either side (owner ruling F2 -- the post-2022
    hole is half the point), floored at 1934-01 (ruling F3). Any empty donor
    frame, or an overlap the module refuses, degrades to the campaign-2 read
    ``funding_stress(ted)`` unchanged.
    """
    donors = (cpf3m, cp3m, nber, tb3m_sec, tb3ms)
    if any(d.empty for d in donors):
        return funding_stress(ted)
    from ah.data import funding_extend as fe

    try:
        ext = fe.extend_funding_spread(ted, *donors)
    except ValueError:
        return funding_stress(ted)
    return ext.frame[["date", "value"]].copy()


def hqm_curve_extended(hqm: pd.DataFrame, aaa: pd.DataFrame) -> pd.DataFrame:
    """HQM 10y spot extended backward on the fitted Aaa donor (PROXY-HQM10-AAA-V1).

    ``ah.data.hqm_extend``: ``HQM10 = a + b * Aaa`` on the 1984+ overlap,
    backward fill only, observed months never overwritten. An empty or
    overlap-short donor degrades to the unextended read.
    """
    if aaa.empty:
        return hqm[["date", "value"]].copy()
    from ah.data import hqm_extend as he

    try:
        ext = he.extend_hqm(hqm, aaa)
    except ValueError:
        return hqm[["date", "value"]].copy()
    return ext.frame[["date", "value"]].copy()


def ust_2y_extended(dgs2: pd.DataFrame, gs1: pd.DataFrame, gs3: pd.DataFrame) -> pd.DataFrame:
    """DGS2 extended to 1953-04 by GS1/GS3 curve interpolation (PROXY-UST2Y-GS1GS3-V1).

    ``ah.data.ust2y_extend``: a two-donor regression on the curve neighbours
    over the observed overlap -- the binding factor of the ratified span
    (AM-2026-08-09-002 moved it here from equity_vol). Empty or overlap-short
    donors degrade to the unextended read.
    """
    if gs1.empty or gs3.empty:
        return dgs2[["date", "value"]].copy()
    from ah.data import ust2y_extend as u2

    try:
        ext = u2.extend_ust2y(dgs2, gs1, gs3)
    except ValueError:
        return dgs2[["date", "value"]].copy()
    return ext.frame[["date", "value"]].copy()


def ust_10y_extended(dgs10: pd.DataFrame, gs10: pd.DataFrame) -> pd.DataFrame:
    """DGS10 extended to 1953-04 on the GS10 identity splice (PROXY-UST10Y-GS10-V1).

    ``ah.data.ust10y_extend``: the same instrument published at monthly
    frequency (overlap corr 1.000), backward fill only. Empty or overlap-short
    donor degrades to the unextended read.
    """
    if gs10.empty:
        return dgs10[["date", "value"]].copy()
    from ah.data import ust10y_extend as u10

    try:
        ext = u10.extend_ust10y(dgs10, gs10)
    except ValueError:
        return dgs10[["date", "value"]].copy()
    return ext.frame[["date", "value"]].copy()


def fx_usd_extended(broad: pd.DataFrame, major: pd.DataFrame) -> pd.DataFrame:
    """fx_usd_spliced with the pegged-era parity index prepended (PROXY-FX-PARITY-V1).

    The DTWEXM donor is first extended to 1953-04 with the vendored
    Bretton-Woods parity index (``ah.data.fx_parity``; single-point junction
    pin, no fit) and the whole donor -- parity months included -- then goes
    through the same ``fx_usd_pre2006`` splice as :func:`fx_usd_spliced`, so
    pegged-era months arrive in DTWEXBGS units via one transform, not two
    conventions. The parity index is prepended only when the donor starts flush
    at the floating-era boundary (1973-01); otherwise -- a truncated fixture
    donor -- the read degrades to :func:`fx_usd_spliced` unchanged.

    Pegged-era months are near-constant BY CONSTRUCTION (the era's true value);
    correlation/ACF consumers over them need the degenerate-variance guard
    (``ah.eval.reference``), which is part of the same wiring.
    """
    from ah.data import fx_parity
    from ah.data import splice as sp

    d = major.assign(date=pd.to_datetime(major["date"]))
    first = d["date"].min() if not d.empty else None
    boundary = pd.Timestamp(fx_parity.END) + pd.offsets.MonthBegin(1)
    if first is None or first != boundary:
        return fx_usd_spliced(broad, major)
    ext = fx_parity.extend_fx(major)
    result = sp.splice(sp.PROXY_RULES["fx_usd_pre2006"], broad, ext.frame[["date", "value"]])
    return result.frame[["date", "value"]].copy()


def policy_rate_extended(fedfunds: pd.DataFrame, tb3ms: pd.DataFrame) -> pd.DataFrame:
    """FEDFUNDS extended to 1934-01 on the TB3MS donor (PROXY_RULES['fedfunds_pre1954']).

    The one extension whose rule predates this wiring: registered in
    ``ah.data.splice`` since Step 1 and APPLIED here for the first time
    (factors.yaml's entry has said "REGISTERED BUT NOT YET APPLIED" since the
    first seal). Regression transform on the 1954-1990 overlap; actuals never
    touched. An empty donor degrades to the unextended read.
    """
    if tb3ms.empty:
        return fedfunds[["date", "value"]].copy()
    from ah.data import splice as sp

    try:
        result = sp.splice(sp.PROXY_RULES["fedfunds_pre1954"], fedfunds, tb3ms)
    except ValueError:
        # the rule's own refusal (<2 overlap points inside its 1954-1990 fit
        # window): a fixture-shaped vintage, handled as every other family's
        # overlap refusal is -- the unextended campaign-2 read.
        return fedfunds[["date", "value"]].copy()
    return result.frame[["date", "value"]].copy()


def yoy(index_frame: pd.DataFrame, periods: int = 12) -> pd.DataFrame:
    """Year-on-year percent change of an index series."""
    s = _s(index_frame).sort_index()
    return _frame((s.pct_change(periods) * 100.0).dropna())


def realized_vol(returns_frame: pd.DataFrame, window: int = 12) -> pd.DataFrame:
    """Annualized realized volatility from monthly returns (rolling std * sqrt(12))."""
    s = _s(returns_frame).sort_index()
    vol = s.rolling(window, min_periods=max(3, window // 2)).std() * np.sqrt(12.0)
    return _frame(vol.dropna())


def drawdown_state(returns_frame: pd.DataFrame) -> pd.DataFrame:
    """Running drawdown (<=0) from compounded monthly returns."""
    s = _s(returns_frame).sort_index()
    wealth = (1.0 + s).cumprod()
    dd = wealth / wealth.cummax() - 1.0
    return _frame(dd)


def demeaned_log_cape(cape_frame: pd.DataFrame) -> pd.DataFrame:
    """DN-1's v_t: log(CAPE) demeaned by its full-sample mean."""
    s = _s(cape_frame).sort_index()
    logc = np.log(s.where(s > 0))
    return _frame((logc - logc.mean()).dropna())


def credit_to_gdp_gap(
    bis: pd.DataFrame, jst_tloans: pd.DataFrame | None = None, jst_gdp: pd.DataFrame | None = None
) -> pd.DataFrame:
    """DN-1's L_t: BIS credit-gap primary; JST tloans/gdp ratio extends pre-1961."""
    primary = _s(bis).sort_index()
    if jst_tloans is not None and jst_gdp is not None:
        tl, gdp = _s(jst_tloans), _s(jst_gdp)
        common = tl.index.intersection(gdp.index)
        jst_ratio = (tl.loc[common] / gdp.loc[common] * 100.0).sort_index()
        pre = jst_ratio[jst_ratio.index < primary.index.min()]
        combined = pd.concat([pre, primary]).sort_index()
        return _frame(combined)
    return _frame(primary)


def funding_stress(
    ted: pd.DataFrame, sofr_basis: pd.DataFrame | None = None, cutover: str = "2021-12-01"
) -> pd.DataFrame:
    """TED to 2021-12, then a documented SOFR-basis replacement (not a fake continuation)."""
    t = _s(ted).sort_index()
    t = t[t.index <= pd.Timestamp(cutover)]
    if sofr_basis is not None:
        sb = _s(sofr_basis).sort_index()
        sb = sb[sb.index > pd.Timestamp(cutover)]
        return _frame(pd.concat([t, sb]).sort_index())
    return _frame(t)


# --------------------------------------------------------------------------- #
# (b) regime labels v1 (rule-based)
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def regime_thresholds() -> dict[str, Any]:
    return yaml.safe_load(_THRESHOLDS_PATH.read_text(encoding="utf-8"))


def label_regime(
    *,
    usrec: float,
    cpi_yoy: float,
    growth_yoy: float,
    drawdown: float,
    hy_oas: float,
    thr: dict[str, Any] | None = None,
) -> str:
    """Pure rule-based monthly regime label (regime_ruleset_v1)."""
    t = thr or regime_thresholds()
    if usrec >= 0.5 and (drawdown <= t["drawdown_crisis"] or hy_oas >= t["hy_crisis"]):
        return "CRI"
    if usrec >= 0.5:
        return "REC"
    if cpi_yoy >= t["cpi_high"] and growth_yoy <= t["growth_weak"]:
        return "STAG"
    if cpi_yoy >= t["cpi_high"] and growth_yoy > t["growth_slow"]:
        return "REF"
    if growth_yoy <= t["growth_weak"]:
        return "REC"
    if growth_yoy < t["growth_slow"]:
        return "SLOW"
    return "EXP"


def label_series(features: pd.DataFrame, thr: dict[str, Any] | None = None) -> pd.DataFrame:
    """Label a features frame (columns: usrec, cpi_yoy, growth_yoy, drawdown, hy_oas)."""
    t = thr or regime_thresholds()
    labels = [
        label_regime(
            usrec=row.usrec,
            cpi_yoy=row.cpi_yoy,
            growth_yoy=row.growth_yoy,
            drawdown=row.drawdown,
            hy_oas=row.hy_oas,
            thr=t,
        )
        for row in features.itertuples()
    ]
    out = (
        features[["date"]].copy() if "date" in features else pd.DataFrame({"date": features.index})
    )
    out["label"] = labels
    out["ruleset"] = t["version"]
    return out.reset_index(drop=True)


def nber_confusion(labels: pd.DataFrame, usrec: pd.DataFrame) -> pd.DataFrame:
    """Confusion of (label in REC/CRI) vs NBER USREC — a report, not a test."""
    lab = labels.assign(date=pd.to_datetime(labels["date"])).set_index("date")["label"]
    rec = _s(usrec)
    common = lab.index.intersection(rec.index)
    pred = lab.loc[common].isin(["REC", "CRI"])
    actual = rec.loc[common] >= 0.5
    return pd.crosstab(actual.rename("nber_recession"), pred.rename("labelled_recession"))


# --------------------------------------------------------------------------- #
# (c) the factor panel
# --------------------------------------------------------------------------- #

UNITS_REGISTRY: dict[str, str] = {
    "term_spread": "pct",
    "credit_spread": "pct",
    "real_3m": "pct",
    "cpi_yoy": "pct",
    "core_cpi_yoy": "pct",
    "equity_vol": "pct_annual",
    "equity_drawdown": "fraction",
    "cape_v": "log_demeaned",
    "credit_gap": "pct",
    "hy_oas": "pct",
}


def assemble_panel(columns: dict[str, pd.DataFrame], *, freq: str = "MS") -> pd.DataFrame:
    """Outer-join derived series into a wide monthly panel; assert no gaps after start.

    The shared date index spans ``min(first observation)`` to ``max(last observation)``
    across every column. A column may start *late* (leading NaNs are allowed and are
    the normal case -- a spread index starting decades after the equity series beside
    it), but once a column has started it must have an observation in every month of
    the index, **including the final one**. So a column that stops early -- a retired
    series, or a test fixture whose frames have mismatched end dates -- raises
    ``ValueError`` naming that column and its gap count, exactly like an interior gap.
    That trailing-gap constraint is the one that surprises callers: real Step-1 series
    all extend to "now", so it only bites synthetic panels, and it bites them loudly.
    """
    if not columns:
        raise ValueError("no columns to assemble")
    series = {name: _s(f).sort_index() for name, f in columns.items()}
    start = min(s.index.min() for s in series.values())
    end = max(s.index.max() for s in series.values())
    index = pd.date_range(start, end, freq=freq)

    panel = pd.DataFrame(index=index)
    for name, s in series.items():
        col = s.reindex(index)
        first = col.first_valid_index()
        if first is not None:
            gap = int(col.loc[first:].isna().sum())
            if gap:
                raise ValueError(
                    f"panel column '{name}' has {gap} gap(s) after its start {first.date()}"
                )
        panel[name] = col
    panel.index.name = "date"
    return panel.reset_index()


def generate_panel_md(panel: pd.DataFrame, units: dict[str, str] | None = None) -> str:
    """Generate the PANEL.md data dictionary (never hand-written)."""
    units = units or UNITS_REGISTRY
    lines = [
        "# PANEL.md — factor panel data dictionary",
        "",
        f"- rows: {len(panel)}",
        f"- span: {panel['date'].min().date()} -> {panel['date'].max().date()}",
        "",
        "| column | units | first obs | n non-null |",
        "| --- | --- | --- | --- |",
    ]
    for col in panel.columns:
        if col == "date":
            continue
        s = panel[col]
        first = s.first_valid_index()
        first_date = panel["date"].iloc[first].date() if first is not None else "-"
        lines.append(f"| {col} | {units.get(col, '?')} | {first_date} | {int(s.notna().sum())} |")
    return "\n".join(lines) + "\n"
