"""NCREIF NPI / ODCE quarterly returns (schema now, data later)."""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

SCHEMA = IntakeSchema(
    name="ncreif_returns",
    source="ncreif",
    columns=[
        ColumnSpec("period", dtype="period"),
        ColumnSpec("index", dtype="str"),  # npi | odce
        ColumnSpec("ret", dtype="float", min=-0.8, max=1.0),
    ],
    period_col="period",
    frequency="Q",
    group_col="index",
    notes="status: pending-license; schema validated ahead of data.",
)
