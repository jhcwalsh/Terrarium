"""Declared interior-gap interpolation (the 2025-10 shutdown hole)."""

from __future__ import annotations

import pandas as pd
import pytest

from ah.data.gapfill import GAP_FILL_RULES, fill_declared_gaps


def _frame(months: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime([m + "-01" for m in months]),
            "value": values,
            "series_id": "fred.CPI",
            "vintage": "v",
        }
    )


def test_declared_gap_is_filled_at_the_midpoint_and_flagged():
    frame = _frame(["2025-08", "2025-09", "2025-11", "2025-12"], [320.0, 322.0, 326.0, 327.0])
    out, notes = fill_declared_gaps("fred.CPI", frame)
    assert len(out) == 5
    row = out[out["date"] == pd.Timestamp("2025-10-01")].iloc[0]
    assert row["value"] == pytest.approx((322.0 + 326.0) / 2.0)
    assert bool(row["is_proxy"]) is True
    assert out["is_proxy"].sum() == 1  # every real observation stays unflagged
    assert notes and "midpoint" in notes[0] and "shutdown" in notes[0]


def test_gap_already_published_means_no_fill():
    frame = _frame(["2025-09", "2025-10", "2025-11"], [322.0, 324.0, 326.0])
    out, notes = fill_declared_gaps("fred.CPI", frame)
    assert len(out) == 3
    assert "is_proxy" not in out.columns  # untouched frames pass through as-is
    assert notes == []


def test_missing_neighbor_leaves_the_gap():
    frame = _frame(["2025-11", "2025-12"], [326.0, 327.0])  # no 2025-09
    out, notes = fill_declared_gaps("fred.CPI", frame)
    assert len(out) == 2
    assert notes and "NOT filled" in notes[0]


def test_undeclared_series_is_never_touched():
    frame = _frame(["2025-09", "2025-12"], [322.0, 327.0])  # a real 2-month gap
    out, notes = fill_declared_gaps("fred.VIX", frame)
    assert out is frame and notes == []


def test_rules_cover_exactly_the_shutdown_family():
    assert set(GAP_FILL_RULES) == {
        "fred.CPI",
        "fred.CPI_CORE",
        "fred.UNRATE",
        "fred.SAHMREALTIME",
    }
    assert all(list(months) == ["2025-10"] for months in GAP_FILL_RULES.values())
