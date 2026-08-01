"""WP2R.6 — the portfolio/institution state extensions (R6, R7).

The plan's acceptance, as tests: the fields exist with units and defaults; a
stub institution instance validates; and the names are the ones Step 3's plan
uses (rates/inflation hedge ratios, collateral pool with haircuts/posted/
headroom, explicit and pass-through leverage, fee drag, FX hedge ratio).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ah.core import institutionstate as inst

ROOT = Path(__file__).resolve().parents[1]
# Named .json, not .example.json: test_sleevestate.py's glob over *.example.json
# asserts exactly the four VEHICLE examples, and this stub is not a vehicle.
STUB = ROOT / "fixtures" / "state" / "institution-stub.json"


def _stub() -> dict:
    return json.loads(STUB.read_text(encoding="utf-8"))


class TestAcceptance:
    def test_stub_institution_validates_and_round_trips(self):
        document = _stub()
        assert inst.is_schema_valid(document) and inst.is_pydantic_valid(document)
        state = inst.load_institution_state(document)  # jsonschema first
        assert state.model_dump(mode="json") == document

    def test_step3_plan_names_are_the_field_names(self):
        """WP3.8's vocabulary, verbatim: hedge ratios for rates and inflation,
        collateral pool with haircuts/posting/headroom, leverage."""
        state = inst.load_institution_state(_stub())
        assert state.institution.hedging.rates_hedge_ratio == 0.7
        assert state.institution.hedging.inflation_hedge_ratio == 0.55
        assert state.institution.collateral_pool.posted == 18.0
        assert state.institution.collateral_pool.headroom == 26.5
        assert state.institution.collateral_pool.eligible_assets[0].haircut == 0.02
        assert state.institution.leverage.explicit_ratio == 1.35
        assert state.institution.leverage.pass_through_ratio == 1.08
        assert state.portfolio.fee_drag_bps_annual == 68.0

    def test_defaults_exist_so_a_minimal_document_is_expressible(self):
        minimal = {
            "state_version": "1.0.0",
            "portfolio": {
                "cash": 0.0,
                "sleeve_ids": [],
                "fee_drag_bps_annual": 0,
                "transaction_cost_defaults_bps": {},
            },
            "institution": {
                "hedging": {
                    "rates_hedge_ratio": 0,
                    "inflation_hedge_ratio": 0,
                    "fx_hedge_ratio": 0,
                },
                "collateral_pool": {"eligible_assets": [], "posted": 0, "headroom": 0},
                "leverage": {"explicit_ratio": 1, "pass_through_ratio": 1},
            },
        }
        state = inst.load_institution_state(minimal)
        assert state.institution.leverage.explicit_ratio == 1.0  # unlevered

    def test_fx_hedge_ratio_exists_and_is_inert_at_zero_per_r5(self):
        """The field is present (so the contract survives the next campaign's FX
        block) and the v1 stub carries 0, consistent with the sealed R5 decision."""
        assert _stub()["institution"]["hedging"]["fx_hedge_ratio"] == 0.0


class TestBounds:
    @pytest.mark.parametrize(
        "path,value",
        [
            (("institution", "hedging", "rates_hedge_ratio"), 2.0),  # > 1.5
            (("institution", "collateral_pool", "posted"), -1.0),
            (("institution", "leverage", "explicit_ratio"), 0.5),  # < 1 = data error
            (("portfolio", "cash"), -0.01),
        ],
    )
    def test_out_of_bounds_rejected_by_both_validators(self, path, value):
        document = copy.deepcopy(_stub())
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert not inst.is_schema_valid(document)
        assert not inst.is_pydantic_valid(document)

    def test_haircut_is_a_fraction(self):
        document = copy.deepcopy(_stub())
        document["institution"]["collateral_pool"]["eligible_assets"][0]["haircut"] = 1.2
        assert not inst.is_schema_valid(document)
        assert not inst.is_pydantic_valid(document)

    def test_extra_keys_rejected(self):
        document = copy.deepcopy(_stub())
        document["institution"]["funding_ratio"] = 1.1  # WP3.8's output, not stored state
        assert not inst.is_schema_valid(document)
        assert not inst.is_pydantic_valid(document)

    def test_loader_is_jsonschema_first(self):
        document = copy.deepcopy(_stub())
        document["institution"]["leverage"]["explicit_ratio"] = 0.2
        with pytest.raises(inst.InstitutionStateSchemaError, match="explicit_ratio"):
            inst.load_institution_state(document)
