"""WP1.6 acceptance: derived primitives, regime labels, panel assembly."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data.derive import (
    REGIME_LABELS,
    UNITS_REGISTRY,
    assemble_panel,
    credit_to_gdp_gap,
    demeaned_log_cape,
    difference,
    drawdown_state,
    generate_panel_md,
    label_regime,
    label_series,
    nber_confusion,
    realized_vol,
    regime_thresholds,
    yoy,
)


def _m(values: list[float], start: str = "2000-01-01") -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def _annual(values: list[float], start: str = "1870-01-01") -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="YS")]
    return pd.DataFrame({"date": dates, "value": values})


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #


def test_difference_term_spread() -> None:
    gs10 = _m([3.0, 3.5, 4.0])
    tb3 = _m([1.0, 1.5, 2.0])
    out = difference(gs10, tb3)
    assert out["value"].tolist() == [2.0, 2.0, 2.0]


def test_yoy() -> None:
    idx = _m([100.0] * 12 + [110.0])
    out = yoy(idx)
    assert abs(out["value"].iloc[-1] - 10.0) < 1e-9  # +10% yoy


def test_realized_vol_positive() -> None:
    rng = np.random.Generator(np.random.PCG64(0))
    rets = _m(list(rng.normal(0, 0.04, 60)))
    out = realized_vol(rets)
    assert (out["value"] > 0).all()


def test_drawdown_state_nonpositive() -> None:
    rets = _m([0.05, -0.10, -0.05, 0.20])
    dd = drawdown_state(rets)
    assert (dd["value"] <= 1e-12).all()
    assert dd["value"].min() < 0


def test_demeaned_log_cape_zero_mean() -> None:
    out = demeaned_log_cape(_m([10.0, 20.0, 30.0, 25.0]))
    assert abs(out["value"].mean()) < 1e-9


def test_credit_to_gdp_gap_extends_with_jst() -> None:
    bis = _m([2.0, 2.5], start="1961-03-01")
    tloans = _annual([50.0, 55.0], start="1955-01-01")
    gdp = _annual([100.0, 100.0], start="1955-01-01")
    out = credit_to_gdp_gap(bis, tloans, gdp)
    # pre-1961 JST ratio (50, 55) then BIS (2.0, 2.5)
    assert out["value"].to_numpy() == pytest.approx([50.0, 55.0, 2.0, 2.5])


# --------------------------------------------------------------------------- #
# regime labels
# --------------------------------------------------------------------------- #


def test_regime_ruleset_version() -> None:
    assert regime_thresholds()["version"] == "regime_ruleset_v1"


@pytest.mark.parametrize(
    ("usrec", "cpi", "growth", "dd", "hy", "expected"),
    [
        (1, 2, -3, -0.30, 9, "CRI"),
        (1, 2, -1, -0.05, 4, "REC"),
        (0, 6, -1, -0.05, 4, "STAG"),
        (0, 6, 3, 0.0, 3, "REF"),
        (0, 2, -1, 0.0, 3, "REC"),
        (0, 2, 1.0, 0.0, 3, "SLOW"),
        (0, 2, 4.0, 0.0, 3, "EXP"),
    ],
)
def test_label_regime_cases(
    usrec: float, cpi: float, growth: float, dd: float, hy: float, expected: str
) -> None:
    label = label_regime(usrec=usrec, cpi_yoy=cpi, growth_yoy=growth, drawdown=dd, hy_oas=hy)
    assert label == expected
    assert expected in REGIME_LABELS


def test_label_series_stamps_version() -> None:
    features = pd.DataFrame(
        {
            "date": ["2000-01-01", "2000-02-01"],
            "usrec": [0, 1],
            "cpi_yoy": [2.0, 2.0],
            "growth_yoy": [3.0, -1.0],
            "drawdown": [0.0, -0.05],
            "hy_oas": [3.0, 4.0],
        }
    )
    out = label_series(features)
    assert out["label"].tolist() == ["EXP", "REC"]
    assert (out["ruleset"] == "regime_ruleset_v1").all()


def test_nber_confusion_shape() -> None:
    labels = pd.DataFrame({"date": ["2000-01-01", "2000-02-01"], "label": ["EXP", "REC"]})
    usrec = pd.DataFrame({"date": ["2000-01-01", "2000-02-01"], "value": [0.0, 1.0]})
    table = nber_confusion(labels, usrec)
    assert table.to_numpy().sum() == 2


# --------------------------------------------------------------------------- #
# panel assembly
# --------------------------------------------------------------------------- #


def test_assemble_panel_no_gaps_and_units() -> None:
    panel = assemble_panel(
        {
            "term_spread": _m([2.0, 2.1, 2.0], start="2000-01-01"),
            "cpi_yoy": _m([3.0, 3.2], start="2000-02-01"),  # starts later; NaN before is ok
        }
    )
    assert list(panel.columns) == ["date", "term_spread", "cpi_yoy"]
    assert len(panel) == 3
    assert bool(panel["term_spread"].notna().all())  # no gaps after its start
    assert "term_spread" in UNITS_REGISTRY


def test_assemble_panel_rejects_interior_gap() -> None:
    gapped = pd.DataFrame(
        {"date": ["2000-01-01", "2000-03-01"], "value": [1.0, 2.0]}  # Feb missing
    )
    with pytest.raises(ValueError, match="gap"):
        assemble_panel({"x": gapped})


def test_generate_panel_md() -> None:
    panel = assemble_panel({"term_spread": _m([2.0, 2.1, 2.0])})
    md = generate_panel_md(panel)
    assert "PANEL.md" in md
    assert "term_spread" in md
    assert "pct" in md
