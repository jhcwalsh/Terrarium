"""The portfolio/institution state extensions — pydantic mirror + loader (WP2R.6).

``schemas/portfolio-institution-state-v1.0.schema.json`` is the normative
contract (R6/R7: hedge ratios, collateral pool, leverage, fee drag, transaction
costs, FX hedge ratio consistent with sealed R5). Schema-level only — the
runtime engine that moves these fields is Step 3 (WP3.7/WP3.8). Same
dual-validation pattern as WorldSpec and the sleeve/vehicle contract.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

_SCHEMA_FILENAME = "portfolio-institution-state-v1.0.schema.json"


def _repo_root() -> Path:
    # src/ah/core/institutionstate.py -> parents[3] == repo root.
    return Path(__file__).resolve().parents[3]


def schema_path() -> Path:
    return _repo_root() / "schemas" / _SCHEMA_FILENAME


@lru_cache(maxsize=1)
def institution_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = institution_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class InstitutionStateSchemaError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(
            "portfolio/institution state failed JSON Schema validation:\n" + "\n".join(errors)
        )


def is_schema_valid(document: dict[str, Any]) -> bool:
    return _validator().is_valid(document)


def validate_against_schema(document: dict[str, Any]) -> None:
    errors = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(_validator().iter_errors(document), key=lambda e: list(e.absolute_path))
    ]
    if errors:
        raise InstitutionStateSchemaError(errors)


_HedgeRatio = Annotated[float, Field(ge=0, le=1.5)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PortfolioState(_Model):
    cash: float = Field(ge=0)
    sleeve_ids: tuple[str, ...]
    fee_drag_bps_annual: float = Field(ge=0, default=0)
    transaction_cost_defaults_bps: dict[str, float] = Field(default_factory=dict)


class Hedging(_Model):
    rates_hedge_ratio: _HedgeRatio = 0.0
    inflation_hedge_ratio: _HedgeRatio = 0.0
    #: Inert at 0 for the v1 campaign per sealed R5 (no FX factor); becomes live
    #: with the next campaign's FX block (S2R-FX-NEXT-CAMPAIGN).
    fx_hedge_ratio: _HedgeRatio = 0.0


class EligibleAsset(_Model):
    sleeve_id: str = Field(min_length=1)
    haircut: float = Field(ge=0, le=1)


class CollateralPool(_Model):
    eligible_assets: tuple[EligibleAsset, ...]
    posted: float = Field(ge=0, default=0)
    headroom: float = Field(ge=0, default=0)


class Leverage(_Model):
    explicit_ratio: float = Field(ge=1, default=1)
    pass_through_ratio: float = Field(ge=1, default=1)


class InstitutionBlock(_Model):
    hedging: Hedging
    collateral_pool: CollateralPool
    leverage: Leverage


class PortfolioInstitutionState(_Model):
    state_version: str = Field(pattern=r"^1\.0\.[0-9]+$")
    portfolio: PortfolioState
    institution: InstitutionBlock


def is_pydantic_valid(document: dict[str, Any]) -> bool:
    try:
        PortfolioInstitutionState.model_validate(document)
    except Exception:
        return False
    return True


def load_institution_state(document: dict[str, Any]) -> PortfolioInstitutionState:
    """JSON Schema first (the normative contract), then the pydantic mirror."""
    validate_against_schema(document)
    return PortfolioInstitutionState.model_validate(document)
