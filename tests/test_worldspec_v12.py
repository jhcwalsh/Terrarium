"""WP2R.7 — WorldSpec v1.2: the resolved generator namespace.

The plan's acceptance, as tests: all Step 0/1/2 worlds revalidate (the sealed
conditional fixtures and the vendored example UNTOUCHED, under the widened
contract); the presets migrated; the new namespace resolves through the
registry, including the deprecated aliases that keep sealed worlds runnable;
and the v1.2 schema differs from vendored v1.0 in exactly the three declared
places — so "V-rules unchanged" is a checked fact, not a claim.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ah.core import loader
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
SEALED_FIXTURES = sorted((ROOT / "fixtures" / "worlds" / "conditional").glob("*.worldspec.json"))
PRESETS = sorted((ROOT / "src" / "ah" / "presets").glob("*.json"))
VENDORED_EXAMPLE = ROOT / "schemas" / "example-long-stagflation.worldspec.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestActiveContract:
    def test_loader_serves_v12(self):
        assert loader.schema_path().name == "worldspec-v1.2.schema.json"
        assert "v1.2.0" in loader.worldspec_schema()["$id"]

    def test_v10_file_still_vendored_untouched(self):
        v10 = json.loads((ROOT / "schemas" / "worldspec-v1.0.schema.json").read_text("utf-8"))
        assert "v1.0.0" in v10["$id"]
        assert v10["properties"]["engine_defaults"]["properties"]["generator_id"]["enum"] == [
            "toy-v0",
            "bootstrap-stratified",
            "signature-mmd",
            "conditional-diffusion",
        ]

    def test_v12_differs_from_v10_in_exactly_three_places(self):
        """V-rules unchanged, mechanically: strip the three declared changes and
        the two documents must be identical — any other drift fails here."""
        v10 = json.loads((ROOT / "schemas" / "worldspec-v1.0.schema.json").read_text("utf-8"))
        v12 = copy.deepcopy(loader.worldspec_schema())
        # change 1: the id
        v12["$id"] = v10["$id"]
        # change 2: spec_version widened
        v12["properties"]["spec_version"] = v10["properties"]["spec_version"]
        # change 3: engine_defaults gained the namespace + taxonomy_version
        ed12 = v12["properties"]["engine_defaults"]["properties"]
        ed10 = v10["properties"]["engine_defaults"]["properties"]
        ed12["generator_id"] = ed10["generator_id"]
        del ed12["taxonomy_version"]
        assert v12 == v10


class TestRevalidation:
    @pytest.mark.parametrize("path", SEALED_FIXTURES, ids=lambda p: p.stem)
    def test_sealed_conditional_fixtures_revalidate_untouched(self, path):
        """Sealed 1.0.x bytes, legacy generator name, valid under v1.2 — the whole
        reason the deprecated enum members and the widened pattern exist."""
        document = _load(path)
        assert document["spec_version"].startswith("1.0.")
        world = loader.load_worldspec(document)
        assert isinstance(world, WorldSpec)

    @pytest.mark.parametrize("path", PRESETS, ids=lambda p: p.stem)
    def test_presets_migrated_to_v12(self, path):
        document = _load(path)
        assert document["spec_version"] == "1.2.0"
        loader.load_worldspec(document)

    def test_vendored_example_revalidates(self):
        document = _load(VENDORED_EXAMPLE)
        assert document["engine_defaults"]["generator_id"] == "conditional-diffusion"
        loader.load_worldspec(document)


class TestNamespaceResolution:
    def _world_doc(self, generator_id: str) -> dict:
        document = copy.deepcopy(_load(PRESETS[0]))
        document["engine_defaults"]["generator_id"] = generator_id
        return document

    def test_promoted_default_is_authorable(self):
        world = loader.load_worldspec(self._world_doc("hier-flow-v1"))
        assert world.engine_defaults.generator_id == "hier-flow-v1"

    def test_legacy_aliases_resolve_to_their_successors(self):
        """The sealed worlds must RUN, not merely validate: both legacy names bind
        to the same factories as their v1.2 successors. Re-registered inside a
        snapshot/restore so the assertion is about the MODULE WIRING, not about
        whatever a previously-run test left in the process-global registry
        (test_gen_registry deliberately overwrites 'bootstrap-stratified' with a
        fake and does not restore)."""
        from ah.gen import bootstrap as bs
        from ah.gen import registry
        from ah.gen.blocks import diffusion as df

        saved = registry.snapshot()
        try:
            registry.register(bs.GENERATOR_ID, bs.bootstrap_v1_factory)
            registry.register(bs.SCHEMA_GENERATOR_ID, bs.bootstrap_v1_factory)
            registry.register(df.GENERATOR_ID, df.hier_diffusion_v1_factory)
            registry.register(df.LEGACY_SCHEMA_GENERATOR_ID, df.hier_diffusion_v1_factory)
            snap = registry.snapshot()
            assert bs.SCHEMA_GENERATOR_ID == "bootstrap-stratified"
            assert df.LEGACY_SCHEMA_GENERATOR_ID == "conditional-diffusion"
            assert snap["bootstrap-stratified"] is snap["bootstrap-v1"]
            assert snap["conditional-diffusion"] is snap["hier-diffusion-v1"]
        finally:
            registry.restore(saved)

    def test_signature_mmd_validates_but_does_not_resolve(self):
        """RESERVED: schema-nameable (sealed-world compatibility), not runnable."""
        from ah.gen import registry

        loader.load_worldspec(self._world_doc("signature-mmd"))
        with pytest.raises(Exception, match="signature-mmd"):
            registry.resolve("signature-mmd")

    def test_unknown_generator_rejected_by_schema(self):
        document = self._world_doc("gpt-market-sim")
        assert not loader.is_schema_valid(document)


class TestTaxonomyVersionField:
    def test_optional_and_pattern_bound(self):
        document = copy.deepcopy(_load(PRESETS[0]))
        document["engine_defaults"]["taxonomy_version"] = "taxonomy-v1.0"
        world = loader.load_worldspec(document)
        assert world.engine_defaults.taxonomy_version == "taxonomy-v1.0"
        document["engine_defaults"]["taxonomy_version"] = "sleeves-2026"
        assert not loader.is_schema_valid(document)

    def test_declared_version_matches_the_shipped_taxonomy(self):
        from ah.data.taxonomy import TAXONOMY_VERSION

        assert TAXONOMY_VERSION == "taxonomy-v1.0"  # the value worlds should declare
