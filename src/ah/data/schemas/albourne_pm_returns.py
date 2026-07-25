"""Albourne private-markets strategy-level quarterly returns."""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

SCHEMA = IntakeSchema(
    name="albourne_pm_returns",
    source="albourne",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("ret", dtype="float", min=-0.9, max=3.0),
    ],
    period_col="period",
    frequency="Q",
    group_col="strategy",
    notes="net-of-fees quarterly returns per PM strategy; de-smoothing-ready.",
)
