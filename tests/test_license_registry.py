"""The licence registry and the free funding-stress leg it made possible."""

from __future__ import annotations

import sys
from pathlib import Path

from ah.data.manifest import load_requirements

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
REGISTRY = ROOT / "docs" / "data" / "LICENSE-REGISTRY.md"


def test_every_series_declares_a_tier_and_only_free_is_redistributable():
    for r in load_requirements():
        assert r.license_tier in {"FREE", "REG", "COMM"}, r.series_id
        assert r.redistributable == (r.license_tier == "FREE"), r.series_id


def test_the_funding_stress_legs_are_registered_free_and_distinct():
    """TED retired in 2022-01. Its replacement legs must be free, and the
    daily secondary-market bill series must NOT be confused with the monthly
    average used as the pre-1954 policy-rate splice donor."""
    reqs = load_requirements()
    cp, bill, old = reqs["fred.CPF3M"], reqs["fred.TB3M_SEC"], reqs["fred.TB3MS"]
    assert cp.license_tier == bill.license_tier == "FREE"
    assert cp.code == "DCPF3M" and bill.code == "DTB3"
    assert bill.code != old.code, "TB3M_SEC and TB3MS must be different upstream series"
    assert reqs["fred.SOFR"].license_tier == "FREE"
    # SOFR is registered but must not be silently treated as the TED successor
    assert "NOT as the funding-stress leg" in (reqs["fred.SOFR"].notes or "")


def test_registry_is_present_and_names_every_commercial_gap():
    assert REGISTRY.exists(), "run scripts/build_license_registry.py"
    text = REGISTRY.read_text(encoding="utf-8")
    for need in ("Commodities total return", "High-yield OAS", "TERM SOFR", "ALB-A"):
        assert need in text, f"gap '{need}' missing from the registry"
    # the registry must not read as clearance
    assert "checklist, not a clearance" in text
    # and it must say that buying data is not the whole job
    assert "amendment plus a re-seal" in text


def test_registry_lists_every_commercial_series_it_claims_to():
    text = REGISTRY.read_text(encoding="utf-8")
    comm = [r.series_id for r in load_requirements() if r.license_tier == "COMM"]
    assert comm, "expected commercial-tier series in the manifest"
    missing = [s for s in comm if f"`{s}`" not in text]
    assert not missing, f"COMM series absent from the registry: {missing[:5]}"


def test_commodities_gap_refuses_the_price_index_substitution():
    """The registry must say WHY the free commodity series do not close the
    gap -- a spot price index is not a total-return index, and quietly
    registering one would be the substitution this platform refuses."""
    text = REGISTRY.read_text(encoding="utf-8")
    section = text.split("### Commodities total return")[1].split("###")[0]
    assert "total_return" in section and "PPIACO" in section
    reqs = load_requirements()
    assert not [r for r in reqs if "commod" in r.series_id.lower()], (
        "a commodities series was registered without closing the sealed missing_factor"
    )
