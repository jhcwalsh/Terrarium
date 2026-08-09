"""WP1.2 acceptance: golden parse tests for each public connector (offline)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ah.data.connectors.base import (
    Connector,
    RawArtifact,
    aggregate_daily_to_monthly,
    to_monthly_last,
    to_monthly_mean,
)
from ah.data.connectors.bis import BisConnector
from ah.data.connectors.fred import FredConnector
from ah.data.connectors.french import FrenchConnector
from ah.data.connectors.jst import JstConnector
from ah.data.connectors.shiller import ShillerConnector
from ah.data.connectors.treasury_hqm import TreasuryHqmConnector
from ah.data.manifest import requirements

FX = Path(__file__).resolve().parent / "fixtures" / "data"
REQ = requirements()


def _raw(source: str, name: str, series_id: str) -> RawArtifact:
    return RawArtifact(source, series_id, (FX / source / name).read_bytes())


# --------------------------------------------------------------------------- #
# aggregation rule
# --------------------------------------------------------------------------- #


def test_monthly_mean_vs_last() -> None:
    df = pd.DataFrame(
        {"date": ["2020-01-02", "2020-01-20", "2020-02-05"], "value": [2.0, 4.0, 8.0]}
    )
    mean = to_monthly_mean(df)
    assert mean["value"].tolist() == [3.0, 8.0]
    last = to_monthly_last(df)
    assert last["value"].tolist() == [4.0, 8.0]


def test_aggregate_uses_last_for_vix() -> None:
    df = pd.DataFrame({"date": ["2020-01-02", "2020-01-20"], "value": [2.0, 4.0]})
    assert aggregate_daily_to_monthly(df, "fred.VIX")["value"].tolist() == [4.0]
    assert aggregate_daily_to_monthly(df, "fred.DGS10")["value"].tolist() == [3.0]


# --------------------------------------------------------------------------- #
# FRED
# --------------------------------------------------------------------------- #


def test_fred_daily_monthly_mean() -> None:
    out = FredConnector().parse(_raw("fred", "dgs10.json", "fred.DGS10"), REQ["fred.DGS10"])
    assert out["date"].dt.strftime("%Y-%m").tolist() == ["2020-01", "2020-02"]
    assert out["value"].tolist() == [3.0, 4.0]  # Jan mean(2,4), Feb mean(3,5)


def test_fred_vix_month_end() -> None:
    out = FredConnector().parse(_raw("fred", "vix.json", "fred.VIX"), REQ["fred.VIX"])
    assert out["value"].tolist() == [4.0, 5.0]  # month-end values


def test_fred_vxo_month_end_with_missing_marker() -> None:
    # The VXO donor aggregates month-end like its splice target fred.VIX, and
    # FRED's "." missing marker never becomes a value.
    out = FredConnector().parse(_raw("fred", "vxo.json", "fred.VXO"), REQ["fred.VXO"])
    assert out["value"].tolist() == [4.8, 6.0]


def test_fred_monthly_passthrough() -> None:
    out = FredConnector().parse(_raw("fred", "tb3ms.json", "fred.TB3MS"), REQ["fred.TB3MS"])
    assert out["value"].tolist() == [1.5, 1.6]


def test_fred_fedfunds_monthly_passthrough() -> None:
    """WP2.2 Task 1 fix pass, Critical 2: `policy_rate` maps to fred.FEDFUNDS, so the
    series needs an offline fixture and a golden parse test like every other FRED
    series -- the suite stays network-free.
    """
    out = FredConnector().parse(
        _raw("fred", "fedfunds.json", "fred.FEDFUNDS"), REQ["fred.FEDFUNDS"]
    )
    assert out["date"].dt.strftime("%Y-%m").tolist() == ["1954-07", "1954-08", "1954-09"]
    assert out["value"].tolist() == [0.8, 1.22, 1.07]


def test_fred_satisfies_protocol() -> None:
    assert isinstance(FredConnector(), Connector)


# --------------------------------------------------------------------------- #
# Ken French
# --------------------------------------------------------------------------- #


def test_french_factor_monthly_block_ignores_annual() -> None:
    out = FrenchConnector().parse(
        _raw("french", "factors.csv", "french.mkt_rf"), REQ["french.mkt_rf"]
    )
    assert out["date"].dt.strftime("%Y-%m").tolist() == ["2020-01", "2020-02"]
    # percent -> decimal: 2.00% -> 0.02, -3.00% -> -0.03; annual 2020 row excluded
    assert out["value"].tolist() == pytest.approx([0.02, -0.03])


def test_french_selects_requested_column() -> None:
    out = FrenchConnector().parse(_raw("french", "factors.csv", "french.hml"), REQ["french.hml"])
    assert out["value"].tolist() == pytest.approx([0.005, -0.0025])


def test_french_momentum() -> None:
    out = FrenchConnector().parse(_raw("french", "momentum.csv", "french.mom"), REQ["french.mom"])
    assert out["value"].tolist() == pytest.approx([0.01, -0.02])


def test_french_daily_keeps_daily_rows() -> None:
    # frequency "D" selects the daily file's YYYYMMDD block; rows stay daily
    # (no monthly aggregation -- the vol backcast needs the returns themselves)
    out = FrenchConnector().parse(
        _raw("french", "factors_daily.csv", "french.mkt_rf_d"), REQ["french.mkt_rf_d"]
    )
    assert out["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2020-01-02",
        "2020-01-03",
        "2020-02-03",
    ]
    assert out["value"].tolist() == pytest.approx([0.005, -0.012, 0.008])
    rf = FrenchConnector().parse(
        _raw("french", "factors_daily.csv", "french.rf_d"), REQ["french.rf_d"]
    )
    assert rf["value"].tolist() == pytest.approx([0.00006, 0.00006, 0.00005])


# --------------------------------------------------------------------------- #
# Shiller / JST / BIS / Treasury HQM
# --------------------------------------------------------------------------- #


def test_shiller_price_fractional_dates() -> None:
    out = ShillerConnector().parse(
        _raw("shiller", "ie_data.xlsx", "shiller.price"), REQ["shiller.price"]
    )
    assert out["date"].dt.strftime("%Y-%m").tolist() == ["1871-01", "1871-02", "1871-03"]
    assert out["value"].tolist() == [4.44, 4.5, 4.61]


def test_jst_filters_usa() -> None:
    out = JstConnector().parse(_raw("jst", "jst.dta", "jst.usa_ltrate"), REQ["jst.usa_ltrate"])
    assert out["date"].dt.year.tolist() == [1870, 1871, 1872]
    assert out["value"].tolist() == [5.32, 5.11, 5.0]


def test_bis_credit_gap() -> None:
    out = BisConnector().parse(
        _raw("bis", "credit_gap.csv", "bis.credit_gap_us"), REQ["bis.credit_gap_us"]
    )
    assert len(out) == 3
    assert out["value"].tolist() == [2.5, 2.7, 2.6]


def test_bis_flat_format_selects_us_gap() -> None:
    # Real BIS Data Portal flat shape: only US + gap-type (CG_DTYPE 'C') rows are kept.
    csv = (
        "FREQ:Frequency,BORROWERS_CTY:Borrowers' country,CG_DTYPE:Credit gap data type,"
        "TIME_PERIOD:Time,OBS_VALUE:Val\n"
        "Q: Quarterly,US: United States,C: Credit-to-GDP gaps (actual-trend),1961-Q1,2.5\n"
        "Q: Quarterly,US: United States,A: Credit-to-GDP ratios (actual data),1961-Q1,99.0\n"
        "Q: Quarterly,GB: United Kingdom,C: Credit-to-GDP gaps (actual-trend),1961-Q1,-1.0\n"
    )
    out = BisConnector().parse(RawArtifact("bis", "x", csv.encode()), REQ["bis.credit_gap_us"])
    assert out["value"].tolist() == [2.5]  # US gap only; ratio + GB excluded
    assert out["date"].iloc[0] == pd.Timestamp("1961-01-01")


def test_treasury_hqm_10y() -> None:
    out = TreasuryHqmConnector().parse(
        _raw("treasury_hqm", "hqm.xlsx", "treasury.hqm_curve"), REQ["treasury.hqm_curve"]
    )
    assert out["value"].tolist() == [3.1, 3.2, 3.0]  # the 10.0 maturity column


def test_all_connectors_satisfy_protocol() -> None:
    for conn in (
        FredConnector(),
        FrenchConnector(),
        ShillerConnector(),
        JstConnector(),
        BisConnector(),
        TreasuryHqmConnector(),
    ):
        assert isinstance(conn, Connector)


def test_shiller_column_drift_raises() -> None:
    import io

    from ah.data.connectors.base import ConnectorError

    # a valid workbook whose 'P' column drifted to 'Price' -> header assertion fires
    buf = io.BytesIO()
    pd.DataFrame({"Date": [1871.01], "Price": [4.44]}).to_excel(buf, index=False)
    with pytest.raises(ConnectorError):
        ShillerConnector().parse(RawArtifact("shiller", "x", buf.getvalue()), REQ["shiller.price"])
