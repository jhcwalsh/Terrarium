"""Manual-intake schema registry (STEP1-DATA-PLAN §WP1.3)."""

from __future__ import annotations

from ah.data.schemas import (
    albourne_derived_cf,
    albourne_hf_returns,
    albourne_pm_returns,
    cliffwater_bdc,
    cliffwater_cdli,
    nareit_returns,
    ncreif_returns,
)
from ah.data.schemas.base import IntakeSchema

SCHEMAS: dict[str, IntakeSchema] = {
    s.name: s
    for s in [
        albourne_pm_returns.SCHEMA,
        albourne_hf_returns.SCHEMA,
        *albourne_derived_cf.ALL,
        cliffwater_bdc.SCHEMA,
        cliffwater_cdli.SCHEMA,
        nareit_returns.SCHEMA,
        ncreif_returns.SCHEMA,
    ]
}


def get_schema(name: str) -> IntakeSchema | None:
    return SCHEMAS.get(name)
