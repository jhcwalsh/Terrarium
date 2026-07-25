"""Albourne hedge-fund strategy-level monthly returns."""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

SCHEMA = IntakeSchema(
    name="albourne_hf_returns",
    source="albourne",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("strategy", dtype="str"),
        ColumnSpec("ret", dtype="float", min=-0.8, max=2.0),
    ],
    period_col="period",
    frequency="M",
    group_col="strategy",
    notes="net-of-fees monthly returns per HF strategy.",
)
