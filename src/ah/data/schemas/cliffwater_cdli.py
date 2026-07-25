"""Cliffwater Direct Lending Index (CDLI) quarterly returns."""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

SCHEMA = IntakeSchema(
    name="cliffwater_cdli",
    source="cliffwater",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("ret", dtype="float", min=-0.8, max=1.0),
    ],
    period_col="period",
    frequency="Q",
    notes="market-level private credit index; cross-check for Albourne PC.",
)
