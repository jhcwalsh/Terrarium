"""FTSE Nareit All Equity REIT total return (monthly)."""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

SCHEMA = IntakeSchema(
    name="nareit_returns",
    source="nareit",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("ret", dtype="float", min=-0.8, max=2.0),
    ],
    period_col="period",
    frequency="M",
    notes="REG tier; manual drop or fetch-if-permitted.",
)
