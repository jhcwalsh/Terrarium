"""WP1.1 acceptance: the requirements manifest loads and is queryable."""

from __future__ import annotations

from ah.data.manifest import Requirement, load_requirements, requirements


def test_manifest_loads_and_is_nonempty() -> None:
    reqs = requirements()
    assert len(reqs) > 30
    assert "fred.DGS10" in reqs
    assert "albourne.pm_buyout_ret_q" in reqs


def test_known_entry_fields() -> None:
    r = requirements()["fred.DGS10"]
    assert isinstance(r, Requirement)
    assert r.source == "fred"
    assert r.code == "DGS10"
    assert r.frequency == "D->M"
    assert r.units == "pct"
    assert r.min_start == "1962-01"
    assert r.sla_days == 7
    assert r.license_tier == "FREE"
    assert r.redistributable is True


def test_licensed_series_not_redistributable() -> None:
    r = requirements()["albourne.pm_buyout_ret_q"]
    assert r.license_tier == "COMM"
    assert r.intake == "manual"
    assert r.redistributable is False


def test_retired_series_present() -> None:
    r = requirements()["fred.TEDRATE"]
    assert "RETIRED" in (r.notes or "")
    assert r.enforce is False  # retired series should not enforce staleness


def test_queries_by_source_and_intake() -> None:
    reqs = load_requirements()
    assert {"fred", "french", "shiller", "jst", "bis", "albourne"} <= reqs.sources()
    assert all(r.source == "fred" for r in reqs.by_source("fred"))
    manual = reqs.by_intake("manual")
    assert all(r.intake == "manual" for r in manual)
    assert any(r.source == "albourne" for r in manual)


def test_jst_usa_series_expanded() -> None:
    reqs = requirements()
    for var in ("ltrate", "stir", "cpi", "gdp", "tloans", "eq_tr", "housing_tr", "crisis"):
        assert f"jst.usa_{var}" in reqs
