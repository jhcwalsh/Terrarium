"""WP-DATA-CMDTY: the AQR CFTLR intake and the commodities total-return construction.

The workbook fixture is built in-test with the real sheet's layout (preamble
rows, blank-first-cell header row, monthly data) so the content-locating
parser is exercised against the structure it will actually meet. The real
workbook is licensed (REG) and gitignored — no test touches it.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from ah.data import cmdty_close as cc
from ah.data.connectors.aqr_cftlr import COLUMN_PREFIXES, parse_workbook
from ah.data.manifest import load_requirements

HEADERS = [
    "",
    "Excess return of equal-weight commodity portfolio",
    "Excess spot return of equal-weight commodity portfolio",
    "Interest rate adjusted carry of equal-weight commodity portfolio",
    "Spot return of equal-weight commodity portfolio",
    "Carry of equal-weight commodity portfolio",
    "Excess return of long/short commodity portfolio",
]

ROWS = [
    ("1877-02-28", 0.011, 0.013, -0.002, 0.010, 0.001, 0.005),
    ("1877-03-31", -0.020, -0.018, -0.002, -0.021, 0.001, 0.004),
    ("1877-04-30", 0.007, 0.009, -0.002, 0.008, -0.001, -0.003),
]


def _workbook_bytes(headers: list[str] = HEADERS) -> bytes:
    blank: list[object] = [None] * len(headers)
    first: list[object] = ["AQR Capital Management, LLC", *([None] * (len(headers) - 1))]
    rows: list[list[object]] = [first]
    rows += [list(blank) for _ in range(9)]  # preamble filler
    rows.append(list(headers))
    for date, *vals in ROWS:
        rows.append([date, *vals][: len(headers)])
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, header=False)
    return buf.getvalue()


def test_parser_locates_columns_by_content():
    out = parse_workbook(_workbook_bytes())
    assert set(out) == set(COLUMN_PREFIXES)
    ex = out["ew_excess"]
    assert ex["date"].dt.strftime("%Y-%m").tolist() == ["1877-02", "1877-03", "1877-04"]
    assert ex["value"].tolist() == pytest.approx([0.011, -0.020, 0.007])
    # the spot column is column 4, NOT the 'excess spot' column 2
    assert out["ew_spot"]["value"].tolist() == pytest.approx([0.010, -0.021, 0.008])


def test_parser_refuses_ambiguous_or_missing_headers():
    from ah.data.connectors.base import ConnectorError

    dup = [*HEADERS, "Spot return of equal-weight commodity portfolio (dup)"]
    with pytest.raises(ConnectorError, match="matched 2 headers"):
        parse_workbook(_workbook_bytes(dup))
    junk = [h.replace("Excess return of equal-weight", "Something else") for h in HEADERS]
    with pytest.raises(ConnectorError, match="header row"):
        parse_workbook(_workbook_bytes(junk))


def test_total_return_is_excess_plus_rf_and_excludes_prehistory():
    dates = pd.date_range("1920-01-01", periods=120, freq="MS")
    rng = np.random.Generator(np.random.PCG64(2))
    excess = pd.DataFrame({"date": dates, "value": 0.005 * rng.standard_normal(120)})
    rf = pd.DataFrame({"date": dates[78:], "value": np.full(42, 0.003)})  # rf starts later
    out = cc.total_return(excess, rf)
    assert out.series_id == "aqr.cmdty_ew_tr" and out.rule_id == cc.RULE_ID
    assert len(out.frame) == 42
    np.testing.assert_allclose(
        out.frame["value"].to_numpy(), excess["value"].to_numpy()[78:] + 0.003
    )
    assert out.excess_only == ("1920-01-01", "1926-06-01")
    assert "AQR" in out.attribution and "not redistributed" in out.attribution


def test_total_return_refuses_thin_overlap():
    dates = pd.date_range("2000-01-01", periods=20, freq="MS")
    excess = pd.DataFrame({"date": dates, "value": np.zeros(20)})
    rf = pd.DataFrame({"date": dates[-5:], "value": np.zeros(5)})
    with pytest.raises(ValueError, match="share only"):
        cc.total_return(excess, rf)


def test_cross_check_recovers_a_perfect_comovement():
    dates = pd.date_range("1992-01-01", periods=100, freq="MS")
    rng = np.random.Generator(np.random.PCG64(9))
    spot_ret = 0.02 * rng.standard_normal(100)
    level = 100.0 * np.exp(np.cumsum(spot_ret))
    spot = pd.DataFrame({"date": dates, "value": spot_ret})
    index = pd.DataFrame({"date": dates, "value": level})
    out = cc.cross_check(spot, index)
    assert out["corr"] == pytest.approx(1.0, abs=1e-9)
    assert out["n_obs"] == 99.0


def test_series_registered_reg_manual_never_redistributable():
    reqs = load_requirements()
    for sid in ("aqr.cmdty_ew_excess", "aqr.cmdty_ew_spot"):
        r = reqs[sid]
        assert r.license_tier == "REG" and r.intake == "manual"
        assert not r.enforce and not r.redistributable
        assert r.min_start == "1877-02"
    assert "NOT the factor" in (reqs["aqr.cmdty_ew_spot"].notes or "")


def test_the_sealed_missing_factor_was_not_silently_closed():
    from pathlib import Path

    from ah.factors import load_manifest

    assert load_manifest().sources["commodities"].kind == "unavailable"
    # and the licensed workbook is never in a committable location
    root = Path(__file__).resolve().parents[1]
    strays = list(root.glob("docs/**/*Commodities for the Long Run*"))
    assert not strays, f"licensed workbook in a committable path: {strays}"
