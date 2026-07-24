"""Pydantic v2 models mirroring ``schemas/worldspec-v1.0.schema.json``.

The JSON Schema is the normative contract (see ``schemas/WORLDSPEC.md``); these
models are the ergonomic mirror. A test asserts the two agree on fuzzed
near-valid documents (``tests/test_worldspec.py``).

Design rules that keep the mirror faithful to the schema:

* **Required ⇔ required.** Every schema-``required`` field is a required pydantic
  field with *no* default (even where the schema lists an advisory ``default``),
  so "key absent" is rejected by both engines identically. Non-required fields are
  ``X | None = None`` (or carry the schema default where the schema gives one for
  an optional field).
* **``extra="forbid"`` ⇔ ``additionalProperties: false``.** Every object in the
  schema sets ``additionalProperties: false``; every model forbids extras.
* **Format-annotated strings are plain ``str``.** ``format: uuid`` / ``date-time``
  are annotations that jsonschema does not enforce by default and that pydantic
  *would* enforce if modeled as ``UUID``/``datetime`` — modeling them as ``str``
  keeps the two validators in agreement and makes the canonical example round-trip
  without datetime-serialization drift (a determinism concern, STEP0-PLAN §6).
* **Bounds ⇔ ``Field(ge=…, le=…)``; patterns/lengths mirrored likewise.**

Cross-field *coherence* (the V-rules) is deliberately NOT here — the schema is
single-field truth, the validator (WP0.3) owns coherence.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------- #
# Shared enums / aliases
# --------------------------------------------------------------------------- #

RegimeName = Literal[
    "expansion",
    "slowdown",
    "recession",
    "crisis",
    "recovery",
    "stagflation",
    "reflation",
    "deflation_boom",
]

Status = Literal["draft", "validated", "approved", "archived"]
SourceKind = Literal["compiler", "preset", "manual", "derived"]
ParameterVintage = Literal["historical_average", "current", "custom"]
GeneratorId = Literal["toy-v0", "bootstrap-stratified", "signature-mmd", "conditional-diffusion"]
DesmoothingMethod = Literal["geltner_ar1", "glm_ma", "regime_glm"]
PathShape = Literal["linear", "front_loaded", "back_loaded", "spike_and_settle"]
EquityBondRegime = Literal["negative", "positive", "inflation_conditional"]
RegimeMode = Literal["sequence", "transition_matrix", "unconditional"]


class _Base(BaseModel):
    """All WorldSpec models forbid unknown keys (mirrors additionalProperties:false)."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #


class Clamp(_Base):
    path: str
    submitted: float
    applied: float


class ValidationWarning(_Base):
    rule: str = Field(pattern=r"^V[0-9]+$")
    message: str
    acknowledged_by_author: bool = False


class Validation(_Base):
    validator_version: str
    validated_at: str  # format: date-time (annotation only)
    clamps: list[Clamp]
    warnings: list[ValidationWarning]


class Source(_Base):
    kind: SourceKind
    user_scenario_text: str | None = Field(default=None, max_length=2000)
    compiler_model: str | None = None
    compiler_prompt_version: str | None = None
    parent_world_id: str | None = None  # format: uuid


class Provenance(_Base):
    created_at: str  # format: date-time
    author: str
    source: Source
    validation: Validation | None = None


# --------------------------------------------------------------------------- #
# narrative  (DISPLAY ONLY — no engine component may read this object)
# --------------------------------------------------------------------------- #


class Dispatch(_Base):
    date: str = Field(pattern=r"^[0-9]{4}(-Q[1-4])?$")
    headline: str = Field(max_length=120)
    detail: str | None = Field(default=None, max_length=300)


class Narrative(_Base):
    language: str  # required by schema (advisory default "en"); kept required here
    title: str = Field(max_length=80)
    tagline: str = Field(max_length=140)
    summary: str = Field(max_length=1200)
    lesson: str = Field(max_length=600)
    dispatches: list[Dispatch] = Field(min_length=3, max_length=10)


# --------------------------------------------------------------------------- #
# horizon / regimes
# --------------------------------------------------------------------------- #


class Horizon(_Base):
    start: str = Field(pattern=r"^[0-9]{4}-Q[1-4]$")
    quarters: int = Field(ge=8, le=120)


class SequenceSegment(_Base):
    regime: RegimeName
    from_quarter: int = Field(ge=0)
    to_quarter: int = Field(ge=0)


class TransitionMatrix(_Base):
    states: list[RegimeName] = Field(min_length=2, max_length=6)
    matrix: list[list[Annotated[float, Field(ge=0, le=1)]]]
    initial_state: RegimeName


class Regimes(_Base):
    mode: RegimeMode
    sequence: list[SequenceSegment] | None = None
    transition_matrix: TransitionMatrix | None = None


# --------------------------------------------------------------------------- #
# factor_conditions
# --------------------------------------------------------------------------- #


class PolicyRate(_Base):
    start_pct: float | None = Field(default=None, ge=0, le=15)
    end_pct: float | None = Field(default=None, ge=0, le=20)
    path_shape: PathShape = "linear"


class Inflation(_Base):
    average_pct: float | None = Field(default=None, ge=-5, le=20)
    peak_pct: float | None = Field(default=None, ge=-5, le=30)
    peak_quarter: int | None = Field(default=None, ge=0)


class Equity(_Base):
    drift_annual_pct: float | None = Field(default=None, ge=-15, le=20)
    vol_annual_pct: float | None = Field(default=None, ge=8, le=45)


class Credit(_Base):
    hy_spread_start_bps: float | None = Field(default=None, ge=200, le=800)
    hy_spread_peak_bps: float | None = Field(default=None, ge=250, le=2200)
    peak_quarter: int | None = Field(default=None, ge=0)


class Commodities(_Base):
    drift_annual_pct: float | None = Field(default=None, ge=-15, le=25)


class Correlation(_Base):
    equity_bond_regime: EquityBondRegime = "inflation_conditional"
    crisis_correlation_boost: float | None = Field(default=None, ge=0, le=0.6)


class CrisisWindow(_Base):
    start_quarter: int = Field(ge=0)
    length_quarters: int = Field(ge=1, le=12)
    severity: float = Field(ge=0, le=1)


class FactorConditions(_Base):
    policy_rate: PolicyRate | None = None
    inflation: Inflation | None = None
    equity: Equity | None = None
    credit: Credit | None = None
    commodities: Commodities | None = None
    correlation: Correlation | None = None
    crisis_windows: list[CrisisWindow] | None = Field(default=None, max_length=4)


# --------------------------------------------------------------------------- #
# structural
# --------------------------------------------------------------------------- #


class PrivateEquity(_Base):
    entry_multiple_drift_annual_pct: float | None = Field(default=None, ge=-6, le=4)
    leverage_turns: float | None = Field(default=None, ge=2, le=8)
    illiquidity_premium_annual_pct: float | None = Field(default=None, ge=0, le=5)


class PrivateCredit(_Base):
    annual_loss_rate_pct: float | None = Field(default=None, ge=0.2, le=10)
    recovery_rate_pct: float | None = Field(default=None, ge=20, le=80)
    spread_over_base_bps: float | None = Field(default=None, ge=250, le=900)


class RealEstate(_Base):
    cap_rate_shift_bps: float | None = Field(default=None, ge=-300, le=500)
    income_yield_pct: float | None = Field(default=None, ge=2, le=8)


class Infrastructure(_Base):
    discount_rate_shift_bps: float | None = Field(default=None, ge=-300, le=500)
    inflation_linkage: float | None = Field(default=None, ge=0, le=1)


class WeightsOnTruth(_Base):
    private_equity: float | None = Field(default=None, ge=0.1, le=1)
    private_credit: float | None = Field(default=None, ge=0.1, le=1)
    real_estate: float | None = Field(default=None, ge=0.1, le=1)
    infrastructure: float | None = Field(default=None, ge=0.1, le=1)


class Smoothing(_Base):
    emit_reported_marks: bool = True
    weights_on_truth: WeightsOnTruth | None = None


class Structural(_Base):
    parameter_vintage: ParameterVintage
    private_equity: PrivateEquity | None = None
    private_credit: PrivateCredit | None = None
    real_estate: RealEstate | None = None
    infrastructure: Infrastructure | None = None
    smoothing: Smoothing | None = None


# --------------------------------------------------------------------------- #
# engine_defaults / extensions
# --------------------------------------------------------------------------- #


class EngineDefaults(_Base):
    generator_id: GeneratorId
    min_generator_version: str | None = None
    mapping_version: str | None = None
    desmoothing_method: DesmoothingMethod = "glm_ma"
    n_paths: int = Field(ge=100, le=100000)  # required (no default; schema requires it)
    base_seed: int | None = None


# --------------------------------------------------------------------------- #
# top-level WorldSpec
# --------------------------------------------------------------------------- #


class WorldSpec(_Base):
    spec_version: str = Field(pattern=r"^1\.0\.[0-9]+$")
    world_id: str  # format: uuid
    status: Status
    provenance: Provenance
    narrative: Narrative
    horizon: Horizon
    regimes: Regimes
    factor_conditions: FactorConditions
    structural: Structural
    engine_defaults: EngineDefaults
    extensions: dict[str, Any] | None = None

    @field_validator("extensions")
    @classmethod
    def _extension_keys_namespaced(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        # Mirrors propertyNames: {pattern: "^x_"} on the extensions object.
        if v is not None:
            bad = [k for k in v if not k.startswith("x_")]
            if bad:
                raise ValueError(f"extension keys must start with 'x_': {bad}")
        return v
