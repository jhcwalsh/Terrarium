"""Datalab — the interrogation console over the vintage store (spec 2026-08-09).

Presentation only: every number on screen comes from ``ah.datalab`` (the
pure, read-only, guard-tested data layer). Run with::

    uv run --group console streamlit run apps/datalab/app.py --server.port 8795

Owner rulings 2026-08-09: port 8795 / name datalab; CSV downloads carry the
licence header and REG attribution in their bytes; the Campaign lens is a
first-class page.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from ah import datalab as dl  # noqa: E402
from ah.data.manifest import load_requirements  # noqa: E402
from ah.factors import load_manifest  # noqa: E402

st.set_page_config(page_title="datalab", layout="wide")

_PROXY_COLORS = alt.Scale(scheme="tableau10")


@st.cache_data(show_spinner=False)
def _inventory(data_root: str, asof: str) -> pd.DataFrame:
    with dl.open_catalog(data_root) as cat:
        return dl.series_inventory(cat, asof=asof)


@st.cache_data(show_spinner=False)
def _series(data_root: str, series_id: str, vintage: str | None, asof: str | None):
    with dl.open_catalog(data_root) as cat:
        return dl.series_frame(cat, series_id, vintage=vintage, asof=asof)


@st.cache_data(show_spinner=False)
def _factor(data_root: str, factor: str, vintage: str | None) -> dl.FactorRead:
    with dl.open_catalog(data_root) as cat:
        return dl.factor_read(cat, factor, vintage=vintage)


@st.cache_data(show_spinner=False)
def _diff(data_root: str, a: str, b: str) -> dl.VintageDiff:
    with dl.open_catalog(data_root) as cat:
        return dl.vintage_diff(cat, a, b)


@st.cache_data(show_spinner=False)
def _current_vintage(data_root: str) -> str | None:
    with dl.open_catalog(data_root) as cat:
        return cat.current_vintage()


@st.cache_data(show_spinner=False)
def _fan(n_draws: int, seed: int) -> pd.DataFrame:
    return dl.har_fan(n_draws=n_draws, seed=seed)


def _split_layers() -> list[alt.Chart]:
    """Train/validation shading and the SPENT holdout, on every time chart."""
    spans = dl.span_annotations()
    rows = [
        {"start": spans.train[0], "end": spans.train[1], "label": "train"},
        {"start": spans.validation[0], "end": spans.validation[1], "label": "validation"},
        {"start": spans.holdout[0], "end": spans.holdout[1], "label": "holdout (SPENT, WP5.6)"},
    ]
    frame = pd.DataFrame(rows)
    frame["start"] = pd.to_datetime(frame["start"])
    frame["end"] = pd.to_datetime(frame["end"])
    band = (
        alt.Chart(frame)
        .mark_rect(opacity=0.07)
        .encode(
            x="start:T", x2="end:T", color=alt.Color("label:N", legend=alt.Legend(title="split"))
        )
    )
    return [band]


def _line_chart(frame: pd.DataFrame, *, title: str, proxy: bool = False) -> alt.Chart:
    base = alt.Chart(frame).encode(x=alt.X("date:T", title=None))
    line = base.mark_line(strokeWidth=1.4).encode(
        y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False))
    )
    layers = [*_split_layers(), line]
    if proxy and "is_proxy" in frame.columns and frame["is_proxy"].any():
        pts = (
            base.transform_filter(alt.datum.is_proxy)
            .mark_point(size=8, filled=True, opacity=0.6)
            .encode(
                y="value:Q",
                color=alt.Color(
                    "rule_id:N", scale=_PROXY_COLORS, legend=alt.Legend(title="proxy rule")
                ),
            )
        )
        layers.append(pts)
    return alt.layer(*layers).properties(title=title, height=320).interactive()


def _share_table(share: dict) -> None:
    if not share:
        return
    cols = st.columns(3)
    cols[0].metric("months", share["n_months"])
    cols[1].metric("proxy months", share["n_proxy"])
    pct = share["share"]
    cols[2].metric("proxy share", f"{pct:.1%}" if pct == pct else "n/a")
    if share["by_rule"]:
        st.dataframe(
            pd.DataFrame([{"rule": k, "share": f"{v:.1%}"} for k, v in share["by_rule"].items()]),
            hide_index=True,
        )


def _download(frame: pd.DataFrame, series_ids: list[str], label: str, key: str) -> None:
    reqs = load_requirements()
    contributing = [reqs[sid] for sid in series_ids if sid in {r.series_id for r in reqs}]
    st.download_button(
        f"download CSV ({label})",
        data=dl.csv_bytes(frame, contributing),
        file_name=f"datalab-{label}.csv",
        mime="text/csv",
        key=key,
    )


# --------------------------------------------------------------------------- #
# shell
# --------------------------------------------------------------------------- #

st.sidebar.title("datalab")
st.sidebar.caption(dl.WATERMARK)
data_root = st.sidebar.text_input("data root", value=str(dl.DEFAULT_DATA_ROOT))
current = _current_vintage(data_root)
if current is None:
    st.error(f"no current vintage under {data_root} -- run a refresh first")
    st.stop()
st.sidebar.caption(f"current vintage: {current}")
page = st.sidebar.radio(
    "page", ["Series", "Factors", "Extensions", "Campaign lens", "Vintages", "Spans"]
)
today = _dt.date.today().isoformat()

manifest = load_manifest()
factors = list(manifest.active_factors())

if page == "Series":
    st.header("Registered series")
    inv = _inventory(data_root, today)
    st.dataframe(
        inv.style.apply(
            lambda row: (
                ["background-color: #fee; color: #7a1f1f" if row["stale"] else ""] * len(row)
            ),
            axis=1,
        ),
        hide_index=True,
        height=420,
    )
    sid = st.selectbox("series", inv["series_id"].tolist())
    vintage = st.text_input("vintage (blank = current)", value="") or None
    frame = _series(data_root, sid, vintage, None)
    if frame is None:
        st.warning(f"{sid}: no observations on this vintage")
    else:
        st.altair_chart(_line_chart(frame, title=sid), width="stretch")
        gaps = frame["date"].diff().dt.days.gt(45).sum()
        st.caption(f"{len(frame)} obs; {gaps} gap(s) over 45 days")
        _download(frame, [sid], sid.replace(".", "-"), key=f"dl-{sid}")

elif page == "Factors":
    st.header("The factor read surface")
    factor = st.selectbox("factor", factors)
    vintage = st.text_input("vintage (blank = current)", value="") or None
    fr = _factor(data_root, factor, vintage)
    if fr.frame is None:
        st.warning(f"{factor}: {fr.note}")
    else:
        st.altair_chart(
            _line_chart(fr.frame, title=f"{factor} (as read)", proxy=True),
            width="stretch",
        )
        if fr.unextended is not None and len(fr.unextended) != len(fr.frame):
            merged = pd.concat(
                [
                    fr.frame.assign(read="extended"),
                    fr.unextended.assign(read="unextended"),
                ]
            )
            overlay = (
                alt.Chart(merged)
                .mark_line(strokeWidth=1.2)
                .encode(
                    x="date:T",
                    y=alt.Y("value:Q", scale=alt.Scale(zero=False)),
                    color=alt.Color("read:N", legend=alt.Legend(title="read")),
                )
                .properties(title="extended vs unextended (campaign-2) read", height=280)
                .interactive()
            )
            st.altair_chart(overlay, width="stretch")
        _share_table(fr.share)
        if factor == "equity_vol" and fr.frame["is_proxy"].any():
            st.caption(
                "Pre-1986 months are MODEL OUTPUT: the pinned HAR draw "
                "(PROXY-EQUITY-VOL-HAR-V1, seed 20260809, sha 53a378a4...)."
            )
        fs = manifest.sources[factor]
        contributing = list(fs.inputs) if fs.kind == "derived" else [str(fs.series_id)]
        _download(fr.frame, contributing, factor, key=f"dl-{factor}")

elif page == "Extensions":
    st.header("The extension families")
    st.caption(
        "Donor-vs-target views of the seven ratified families; fit numbers come "
        "from each module's own overlap_stats. Full reports: docs/data/*-REPORT.md"
    )
    fam = st.selectbox(
        "family",
        [
            "equity_vol (VXO + pinned HAR draw)",
            "funding_spread (CP-bill)",
            "hqm_curve (Aaa)",
            "ust_2y (GS1/GS3)",
            "ust_10y (GS10)",
            "fx_usd (parity + DTWEXM)",
            "policy_rate (TB3MS)",
        ],
    )
    factor = fam.split(" ")[0]
    fr = _factor(data_root, factor, None)
    if fr.frame is None:
        st.warning(f"{factor}: {fr.note}")
    else:
        st.altair_chart(
            _line_chart(fr.frame, title=f"{factor} (as read)", proxy=True),
            width="stretch",
        )
        _share_table(fr.share)
    if factor == "equity_vol":
        st.subheader("The HAR ensemble fan (regenerated) vs the pinned draw")
        n_draws = st.slider("draws", 16, 400, 200, step=16)
        seed = st.number_input("seed", value=0, step=1)
        fan = _fan(int(n_draws), int(seed))
        base = alt.Chart(fan).encode(x="date:T")
        band90 = base.mark_area(opacity=0.18).encode(y="q05:Q", y2="q95:Q")
        band50 = base.mark_area(opacity=0.30).encode(y="q25:Q", y2="q75:Q")
        med = base.mark_line(strokeDash=[4, 3], strokeWidth=1).encode(y="q50:Q")
        pinned = base.mark_line(strokeWidth=1.6, color="#b40000").encode(y="pinned:Q")
        st.altair_chart(
            alt.layer(band90, band50, med, pinned)
            .properties(title="MODEL OUTPUT -- not observation", height=340)
            .interactive(),
            width="stretch",
        )
        st.caption(
            "Owner decision D2: tail readers regenerate the ensemble from the "
            "provenance artifact; the panel serves ONLY the pinned red path."
        )

elif page == "Campaign lens":
    st.header("Campaign lens -- one factor, two vintages")
    col_a, col_b = st.columns(2)
    vintage_a = col_a.text_input("vintage A", value="2026-08-02.4")
    vintage_b = col_b.text_input("vintage B", value=current)
    chosen = st.multiselect("factors", factors, default=["equity_vol", "ust_2y"])
    for factor in chosen:
        ca, cb = st.columns(2)
        for col, vintage in ((ca, vintage_a), (cb, vintage_b)):
            with col:
                fr = _factor(data_root, factor, vintage)
                if fr.frame is None:
                    st.warning(f"{factor} @ {vintage}: {fr.note}")
                else:
                    st.altair_chart(
                        _line_chart(fr.frame, title=f"{factor} @ {vintage}", proxy=True),
                        width="stretch",
                    )
                    _share_table(fr.share)

elif page == "Vintages":
    st.header("Vintage diff")
    col_a, col_b = st.columns(2)
    a = col_a.text_input("vintage A", value="2026-08-02.4")
    b = col_b.text_input("vintage B", value=current)
    diff = _diff(data_root, a, b)
    st.caption(f"status: {a} = {diff.status_a} · {b} = {diff.status_b}")
    changed = diff.table[diff.table["change"] != "same"]
    st.subheader(f"{len(changed)} series changed")
    st.dataframe(changed, hide_index=True)
    with st.expander("all series"):
        st.dataframe(diff.table, hide_index=True)

else:  # Spans
    st.header("Splits and spans")
    spans = dl.span_annotations()
    rows = [
        ("train", *spans.train, ""),
        ("validation", *spans.validation, ""),
        ("holdout", *spans.holdout, "SPENT at WP5.6 -- one read, taken"),
        ("campaign-2 draw span", *spans.campaign2_span, "bootstrap-v1 as sealed at G2"),
        ("live sealed draw span", *spans.live_span, "AM-2026-08-09-002 (1953-04 ratification)"),
        ("severe-test exclusion", *spans.severe_exclusion, "the decade the severe leg removes"),
    ]
    frame = pd.DataFrame(rows, columns=["span", "start", "end", "note"])
    st.dataframe(frame, hide_index=True)
    tl = frame.assign(start=pd.to_datetime(frame["start"]), end=pd.to_datetime(frame["end"]))
    chart = (
        alt.Chart(tl)
        .mark_bar(height=14)
        .encode(
            x=alt.X("start:T", title=None),
            x2="end:T",
            y=alt.Y("span:N", sort=None, title=None),
            color=alt.Color("span:N", legend=None),
            tooltip=["span", "start", "end", "note"],
        )
        .properties(height=240)
    )
    st.altair_chart(chart, width="stretch")

st.sidebar.divider()
st.sidebar.caption("read-only: this app has no store-write call sites (guard-tested)")
