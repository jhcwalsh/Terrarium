"""The sleeve/vehicle state contract — pydantic mirror + dual-validating loader (WP2R.3).

``schemas/sleeve-vehicle-state-v1.0.schema.json`` is the normative contract
(spec §3, three vehicle types first-class per R3, recycling/recallable explicit
per R14, granularity carried by ``n_funds`` + ``dispersion_draw``). This module
mirrors it in pydantic and loads documents **JSON Schema first**, exactly as
``ah.core.loader`` does for WorldSpec.

Where the two validators deliberately differ: JSON Schema cannot express the
two cross-field invariants — ``paid_in <= committed`` and
``recallable_balance <= cumulative_distributions`` — so the pydantic mirror is
*strictly stricter*, on exactly those two rules and nothing else. The agreement
test asserts both halves: agreement everywhere else, and the divergence set
being exactly these two.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

_SCHEMA_FILENAME = "sleeve-vehicle-state-v1.0.schema.json"


def _repo_root() -> Path:
    # src/ah/core/sleevestate.py -> parents[3] == repo root (editable/dev layout).
    return Path(__file__).resolve().parents[3]


def schema_path() -> Path:
    """Absolute path to the vendored, normative state JSON Schema."""
    return _repo_root() / "schemas" / _SCHEMA_FILENAME


@lru_cache(maxsize=1)
def state_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = state_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class SleeveStateSchemaError(ValueError):
    """A document that fails JSON Schema validation (checked before pydantic)."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(
            "sleeve/vehicle state failed JSON Schema validation:\n" + "\n".join(errors)
        )


def is_schema_valid(document: dict[str, Any]) -> bool:
    return _validator().is_valid(document)


def validate_against_schema(document: dict[str, Any]) -> None:
    errors = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(_validator().iter_errors(document), key=lambda e: list(e.absolute_path))
    ]
    if errors:
        raise SleeveStateSchemaError(errors)


# --------------------------------------------------------------------------- #
# the pydantic mirror
# --------------------------------------------------------------------------- #

_Money = Annotated[float, Field(ge=0)]
_Fraction = Annotated[float, Field(ge=0, le=1)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClosedEndIdentity(_Model):
    sleeve_id: str = Field(min_length=1)
    vintage_year: int = Field(ge=1980, le=2100)
    cohort_id: str = Field(min_length=1)
    n_funds: int = Field(ge=1)
    fund_name: str | None


class Commitment(_Model):
    committed: _Money
    paid_in: _Money
    unfunded: _Money
    recallable_balance: _Money
    cumulative_recycled: _Money


class ClosedEndValue(_Model):
    nav_true: _Money
    nav_reported: _Money
    cumulative_distributions: _Money


class Lifecycle(_Model):
    age_years: float = Field(ge=0)
    contractual_life_years: float = Field(gt=0)
    extension_status: Literal["none", "extended", "expired"]


class Performance(_Model):
    tvpi: float | None = Field(ge=0)
    dpi: float | None = Field(ge=0)
    rvpi: float | None = Field(ge=0)
    irr_to_date: float | None
    pme: float | None = Field(ge=0)


class TAParameters(_Model):
    rc_curve: tuple[_Fraction, ...] = Field(min_length=1)
    bow: float = Field(gt=0)
    yield_rate: _Fraction
    beta_g: float
    alpha_g: float
    lambda_g: float = Field(ge=0)
    k_d: float = Field(ge=0)
    k_c: float = Field(ge=0)
    sigma_eps: float = Field(ge=0)
    dispersion_draw: _Fraction | None


class Fees(_Model):
    mgmt_fee_rate: _Fraction
    fee_basis_state: Literal["committed", "invested", "nav"]
    carry_rate: _Fraction
    hurdle: _Fraction
    catch_up: _Fraction
    waterfall_type: Literal["european", "american"]
    accrued_carry: _Money


class ClosedEndFlows(_Model):
    calls: _Money
    distributions_income: _Money
    distributions_capital: _Money
    nav_growth: float
    fees_paid: _Money
    carry_crystallized: _Money


class ClosedEndCohortState(_Model):
    state_version: str = Field(pattern=r"^1\.0\.[0-9]+$")
    vehicle_type: Literal["closed_end"]
    identity: ClosedEndIdentity
    commitment: Commitment
    value: ClosedEndValue
    lifecycle: Lifecycle
    performance: Performance
    parameters: TAParameters
    fees: Fees
    flows: ClosedEndFlows

    @model_validator(mode="after")
    def _cross_field_invariants(self) -> ClosedEndCohortState:
        # The two rules JSON Schema cannot express; the agreement test pins that
        # these are the ONLY divergences between the two validators.
        if self.commitment.paid_in > self.commitment.committed:
            raise ValueError(
                f"paid_in {self.commitment.paid_in} exceeds committed {self.commitment.committed}"
            )
        if self.commitment.recallable_balance > self.value.cumulative_distributions:
            raise ValueError(
                f"recallable_balance {self.commitment.recallable_balance} exceeds "
                f"cumulative_distributions {self.value.cumulative_distributions} — "
                "nothing can be recallable that was never distributed"
            )
        return self


class SleeveIdentity(_Model):
    sleeve_id: str = Field(min_length=1)
    n_funds: int = Field(ge=1)
    fund_name: str | None


class NavValue(_Model):
    nav_true: _Money
    nav_reported: _Money


class OpenEndedTerms(_Model):
    notice_days: int = Field(ge=0)
    lockup_remaining_months: float = Field(ge=0)
    gate_pct: _Fraction | None
    redemption_frequency: Literal["daily", "weekly", "monthly", "quarterly", "semiannual", "annual"]
    side_pocket_share: _Fraction


class OpenEndedLiquidity(_Model):
    realizable_30d: _Money
    realizable_90d: _Money
    realizable_180d: _Money
    gated_flag: bool
    gated_share: _Fraction
    queue_position: float | None = Field(ge=0)


class OpenEndedFlows(_Model):
    subscriptions: _Money
    redemptions_requested: _Money
    redemptions_paid: _Money
    return_true: float
    return_reported: float
    fees: _Money
    performance_fee_crystallized: _Money


class OpenEndedSleeveState(_Model):
    state_version: str = Field(pattern=r"^1\.0\.[0-9]+$")
    vehicle_type: Literal["open_ended"]
    identity: SleeveIdentity
    value: NavValue
    terms: OpenEndedTerms
    liquidity: OpenEndedLiquidity
    flows: OpenEndedFlows


class EvergreenTerms(_Model):
    redemption_cap_pct_per_period: _Fraction
    notice_days: int = Field(ge=0)
    queue_policy: Literal["pro_rata", "fifo"]


class EvergreenQueue(_Model):
    pending_redemption_amount: _Money
    queue_age_periods: float = Field(ge=0)
    fulfilled_pct_history: tuple[_Fraction, ...]


class EvergreenLiquidity(_Model):
    realizable_this_period: _Money
    expected_time_to_full_exit_periods: float = Field(ge=0)


class EvergreenFlows(_Model):
    subscriptions: _Money
    redemptions_requested: _Money
    redemptions_fulfilled: _Money
    return_true: float
    return_reported: float
    income_distributed: _Money


class EvergreenVehicleState(_Model):
    state_version: str = Field(pattern=r"^1\.0\.[0-9]+$")
    vehicle_type: Literal["evergreen"]
    identity: SleeveIdentity
    value: NavValue
    terms: EvergreenTerms
    queue: EvergreenQueue
    liquidity: EvergreenLiquidity
    flows: EvergreenFlows


class LiquidIdentity(_Model):
    sleeve_id: str = Field(min_length=1)


class LiquidSleeveState(_Model):
    state_version: str = Field(pattern=r"^1\.0\.[0-9]+$")
    vehicle_type: Literal["liquid"]
    identity: LiquidIdentity
    value: _Money
    weight: float = Field(ge=0)
    target_weight: _Fraction
    return_period: float
    transaction_cost_bps: float = Field(ge=0)


SleeveState = Annotated[
    ClosedEndCohortState | OpenEndedSleeveState | EvergreenVehicleState | LiquidSleeveState,
    Field(discriminator="vehicle_type"),
]

_ADAPTER: TypeAdapter[Any] = TypeAdapter(SleeveState)


def is_pydantic_valid(document: dict[str, Any]) -> bool:
    try:
        _ADAPTER.validate_python(document)
    except Exception:
        return False
    return True


def load_sleeve_state(
    document: dict[str, Any],
) -> ClosedEndCohortState | OpenEndedSleeveState | EvergreenVehicleState | LiquidSleeveState:
    """JSON Schema first (the normative contract), then the pydantic mirror."""
    validate_against_schema(document)
    return _ADAPTER.validate_python(document)
