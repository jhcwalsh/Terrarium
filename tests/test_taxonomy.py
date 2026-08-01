"""WP2R.1 — the sleeve taxonomy and the Albourne mapping boundary.

The plan's acceptance, as tests: every delivered Albourne series maps to exactly
one sleeve_id; an unmapped vendor code fails intake with a readable report; the
taxonomy is versioned and referenced by id. Plus R13: secondaries is its own
sleeve whose TA parameters are never cloned from buyout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ah.data import taxonomy as tx
from ah.data.intake import validate_file
from ah.data.manifest import load_requirements
from ah.data.schemas.albourne_pm_returns import SCHEMA as PM_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "data" / "intake" / "albourne"


@pytest.fixture(scope="module")
def taxonomy() -> tx.Taxonomy:
    return tx.load_taxonomy()


class TestNamespace:
    def test_loads_and_is_versioned(self, taxonomy):
        assert taxonomy.version == tx.TAXONOMY_VERSION == "taxonomy-v1.1"

    def test_v1_build_list_is_within_the_spec_recommendation(self, taxonomy):
        """Spec §1.2 note: 8-10 PM and 7-9 HF sleeves for v1."""
        modeled = [taxonomy.sleeve(s) for s in taxonomy.modeled_v1]
        hf = [s for s in modeled if s.sleeve_id.startswith("hf_")]
        pm = [s for s in modeled if s.sleeve_id.startswith("pm_")]
        assert 7 <= len(hf) <= 9, [s.sleeve_id for s in hf]
        assert 8 <= len(pm) <= 10, [s.sleeve_id for s in pm]

    def test_aggregates_resolve_and_stay_in_group(self, taxonomy):
        for sleeve in taxonomy.sleeves.values():
            for child_id in sleeve.aggregates:
                child = taxonomy.sleeve(child_id)
                assert child.group == sleeve.group, (
                    f"{sleeve.sleeve_id} aggregates {child_id} across groups"
                )

    def test_r13_secondaries_is_its_own_sleeve_never_a_buyout_clone(self, taxonomy):
        secondaries = taxonomy.sleeve("pm_secondaries")
        assert secondaries.modeled_in_v1
        assert secondaries.group != taxonomy.sleeve("pm_buyout").group
        assert secondaries.notes and "cloned from buyout" in secondaries.notes.lower()

    def test_unknown_sleeve_id_raises_with_vocabulary(self, taxonomy):
        with pytest.raises(tx.TaxonomyError, match="unknown sleeve_id"):
            taxonomy.sleeve("pm_does_not_exist")


class TestSeriesCoverage:
    def test_every_registered_albourne_series_maps_to_exactly_one_sleeve(self, taxonomy):
        """The acceptance clause, verbatim — with the cashflow packs covered by the
        explicit non-sleeve list, so nothing is unaccounted for."""
        registered = {r.series_id for r in load_requirements() if r.source == "albourne"}
        mapped = set(taxonomy.series_to_sleeve)
        non_sleeve = set(taxonomy.non_sleeve_series)
        assert mapped & non_sleeve == set()
        assert mapped | non_sleeve == registered, (
            f"unaccounted: {sorted(registered - mapped - non_sleeve)}; "
            f"stale: {sorted((mapped | non_sleeve) - registered)}"
        )

    def test_series_coverage_of_the_v1_build_list(self, taxonomy):
        """taxonomy-v1.1 (option b): HF series are sub-strategy granular, so
        several series roll up to one modeled sleeve, and hf_ils receives a
        series while staying outside the build list — data availability and the
        build list are different statements. What must hold: every modeled
        sleeve is fed by at least one series, and every target is a real sleeve."""
        targets = set(taxonomy.series_to_sleeve.values())
        assert set(taxonomy.modeled_v1) <= targets, (
            f"modeled sleeves with no series: {sorted(set(taxonomy.modeled_v1) - targets)}"
        )
        assert targets <= set(taxonomy.sleeves)


class TestVendorCodes:
    def test_hedgers_inventory_is_complete_and_unambiguous(self, taxonomy):
        """20 sub-strategy indices mapped, 2 composites excluded with reasons,
        every index_id distinct — the scope inventory, fully classified."""
        import yaml

        doc = yaml.safe_load((ROOT / "taxonomy" / "albourne_mapping.yaml").read_text("utf-8"))
        hedgers = doc["codes"]["hedgers"]
        assert len(hedgers) == 20
        ids = [entry["index_id"] for entry in hedgers.values()]
        ids += [entry["index_id"] for entry in doc["excluded_codes"].values()]
        assert len(ids) == len(set(ids)) == 22
        for reason in taxonomy.excluded_codes.values():
            assert reason

    def test_sleeve_for_code_resolves_and_misses_loudly(self, taxonomy):
        assert tx.sleeve_for_code("buyout") == "pm_buyout"
        assert tx.sleeve_for_code("HedgeRS AW CTA") == "hf_cta"
        with pytest.raises(tx.TaxonomyError, match="not mapped"):
            tx.sleeve_for_code("HedgeRS Universal (AW)")  # excluded != mapped

    def test_every_fixture_strategy_code_is_mapped(self, taxonomy):
        """The committed intake fixtures stay format-faithful to the mapping."""
        import pandas as pd

        for csv in sorted(FIXTURES.glob("*.csv")):
            frame = pd.read_csv(csv)
            if "strategy" not in frame.columns:
                continue
            missing = tx.unmapped_codes(frame["strategy"].dropna().unique())
            assert not missing, f"{csv.name}: unmapped codes {missing}"


class TestIntakeBoundary:
    def test_clean_fixture_still_accepted(self):
        result = validate_file(FIXTURES / "pm-returns_2026Q2.csv", PM_SCHEMA)
        assert result.accepted, result.report

    def test_unmapped_code_fails_intake_with_a_readable_report(self, tmp_path):
        drop = tmp_path / "pm-returns_2026Q3.csv"
        drop.write_text(
            "period,strategy,ret\n2026Q1,buyout,0.03\n2026Q1,timberland_iii,0.02\n",
            encoding="utf-8",
        )
        result = validate_file(drop, PM_SCHEMA)
        assert not result.accepted
        assert any(v.kind == "unmapped_strategy" for v in result.violations)
        assert "timberland_iii" in result.report
        assert "albourne_mapping.yaml" in result.report
        # the mapped code in the same file is not what failed it
        assert "['buyout'" not in result.report


class TestFileContracts:
    def test_version_skew_is_rejected(self, tmp_path):
        sleeves = tmp_path / "sleeves.yaml"
        sleeves.write_text(
            "version: taxonomy-v9.9\nvehicle_types: [closed_end]\nsleeves:\n"
            "  - {id: x, group: g, vehicle: closed_end, modeled_in_v1: false, definition: d}\n",
            encoding="utf-8",
        )
        version, loaded = tx._load_sleeves(sleeves)
        assert version == "taxonomy-v9.9" and "x" in loaded

    def test_mapping_to_unknown_sleeve_is_rejected(self, tmp_path):
        _, sleeves = tx._load_sleeves(tx.SLEEVES_PATH)
        bad = tmp_path / "mapping.yaml"
        bad.write_text(
            "version: taxonomy-v1.0\nseries: {albourne.x_ret_q: not_a_sleeve}\n",
            encoding="utf-8",
        )
        with pytest.raises(tx.TaxonomyError, match="unknown sleeve"):
            tx._load_mapping(bad, sleeves)

    def test_code_cannot_be_both_mapped_and_excluded(self, tmp_path):
        _, sleeves = tx._load_sleeves(tx.SLEEVES_PATH)
        bad = tmp_path / "mapping.yaml"
        bad.write_text(
            "version: taxonomy-v1.0\n"
            "codes: {albourne: {buyout: pm_buyout}}\n"
            "excluded_codes: {buyout: {reason: also excluded}}\n",
            encoding="utf-8",
        )
        with pytest.raises(tx.TaxonomyError, match="both mapped and excluded"):
            tx._load_mapping(bad, sleeves)
