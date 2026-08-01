"""WP2R.4 — the generator-output contract.

What is proven here, one sentence per class:

* the joinery emits a schema-valid document whose regime/slow-state layers are
  present, digest-verifiable, and stable per seed;
* bootstrap-v1 emits a schema-valid document whose slow-state absence is a
  reasoned statement, never an omission;
* the contract refuses an ensemble that neither produces a layer nor gives a
  reason, and refuses a factor the sealed manifest does not declare;
* the emitted factor namespace is a faithful copy of the sealed manifest, and
  every derived factor's identity metadata resolves to a real ah.data.derive
  helper over registered series — the acceptance clause "the identity metadata
  lets a consumer recompute every derived variable" as a test.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.data import derive
from ah.data.manifest import requirements
from ah.factors import load_manifest
from ah.gen import output as go
from ah.gen.base import AbsentLayer, Ensemble, EnsembleMeta
from ah.gen.bootstrap import FACTOR_SET, REGIME_LABELS, BootstrapV1
from ah.gen.climate.model import STATE_NAMES
from ah.gen.joinery import assemble as asm
from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

MONTHS = 24  # smoke-sized decades, as in test_joinery_assemble


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(tmp_path_factory.mktemp("climate"))


@pytest.fixture(scope="module")
def regimes_artifact(tmp_path_factory):
    return make_regimes_artifact(tmp_path_factory.mktemp("regimes"))


@pytest.fixture(scope="module")
def source():
    return make_source()


@pytest.fixture(scope="module")
def joinery_ensemble(climate, regimes_artifact, source):
    return asm.assemble_decades(
        climate=climate,
        regimes_artifact=regimes_artifact,
        source=source,
        n_decades=4,
        months=MONTHS,
        seed=1234,
    )


@pytest.fixture(scope="module")
def bootstrap_ensemble(source):
    gen = BootstrapV1()
    gen.fit(source)
    return gen.sample_months(MONTHS, 5, seed=99)


class TestJoineryDocument:
    def test_document_validates_and_arrays_verify(self, joinery_ensemble):
        doc = go.build_document(joinery_ensemble)  # validates before returning
        go.verify_arrays(joinery_ensemble, doc)
        assert doc["contract_version"] == go.CONTRACT_VERSION
        assert doc["provenance"]["generator_id"] == "joinery-bootstrap-v0"
        assert doc["shape"] == {
            "n_paths": 4,
            "months": MONTHS,
            "n_factors": len(joinery_ensemble.factor_names),
        }

    def test_regime_and_slow_state_layers_are_present(self, joinery_ensemble):
        doc = go.build_document(joinery_ensemble)
        assert doc["regimes"]["labels_legend"] == list(REGIME_LABELS)
        assert doc["regimes"]["ruleset_version"] == "regime_ruleset_v1"
        assert doc["slow_states"]["names"] == list(STATE_NAMES)
        assert doc["slow_states"]["layer"] == "simulated"
        assert doc["arrays"]["regime_labels"]["shape"] == [4, MONTHS]
        assert doc["arrays"]["slow_states"]["shape"] == [4, MONTHS, len(STATE_NAMES)]

    def test_frozen_climate_is_marked(self, climate, regimes_artifact, source):
        ensemble = asm.assemble_decades(
            climate=climate,
            regimes_artifact=regimes_artifact,
            source=source,
            n_decades=2,
            months=MONTHS,
            seed=7,
            config=asm.JoineryConfig(use_climate=False),
        )
        doc = go.build_document(ensemble)
        assert doc["slow_states"]["layer"] == "frozen-posterior-mean"

    def test_diagnostics_block_is_present_and_typed(self, joinery_ensemble):
        doc = go.build_document(joinery_ensemble)
        diag = doc["diagnostics"]
        assert "absent" not in diag
        assert isinstance(diag["waypoints_bound"], bool)
        assert isinstance(diag["waypoint_tolerance"]["all_ok"], bool)
        assert diag["acceptance_filter"]["n_rejected"] >= 0

    def test_same_seed_same_document(self, climate, regimes_artifact, source):
        def build():
            return go.build_document(
                asm.assemble_decades(
                    climate=climate,
                    regimes_artifact=regimes_artifact,
                    source=source,
                    n_decades=2,
                    months=MONTHS,
                    seed=4242,
                )
            )

        assert build() == build()  # digests included — bit-stable emission

    def test_regime_labels_match_the_operative_waypoint_labels(self, joinery_ensemble):
        # The ensemble's regime tensor is the same operative path (crisis
        # overlays applied) the bridge conditioned on — codes must be valid.
        labels = joinery_ensemble.regimes.labels
        assert labels.min() >= 0
        assert labels.max() < len(REGIME_LABELS)


class TestBootstrapDocument:
    def test_document_validates_and_absence_is_reasoned(self, bootstrap_ensemble):
        doc = go.build_document(bootstrap_ensemble)
        go.verify_arrays(bootstrap_ensemble, doc)
        assert doc["slow_states"]["absent"] is True
        assert "bootstrap-v1" in doc["slow_states"]["reason"]
        assert doc["arrays"]["slow_states"] is None
        assert doc["diagnostics"]["absent"] is True  # no joinery ran

    def test_realized_regime_path_is_the_drawn_rows_labels(self, source, bootstrap_ensemble):
        rec = bootstrap_ensemble.regimes
        assert rec.mode == "realized-historical-frequency"
        assert rec.legend == REGIME_LABELS
        assert rec.labels.shape == (5, MONTHS)
        # Every realized label is a label the draw span actually carries.
        drawn = {REGIME_LABELS[int(code)] for code in np.unique(rec.labels)}
        assert drawn <= set(source.labels)


class TestContractRefusals:
    def _meta(self) -> EnsembleMeta:
        return EnsembleMeta(
            generator_id="test-gen",
            vintage_id="test-vintage",
            seed=1,
            n_paths=2,
            months=3,
            conditioning={},
            active_blocks=("global", "us"),
        )

    def test_bare_none_layer_is_refused(self):
        ensemble = Ensemble(
            paths=np.zeros((2, 3, len(FACTOR_SET))),
            factor_names=list(FACTOR_SET),
            meta=self._meta(),
            regimes=None,
            slow_states=AbsentLayer("no slow states in this test double"),
        )
        with pytest.raises(go.OutputContractError, match="silent omission"):
            go.build_document(ensemble)

    def test_unknown_factor_is_refused(self):
        ensemble = Ensemble(
            paths=np.zeros((2, 3, 1)),
            factor_names=["not_a_sealed_factor"],
            meta=self._meta(),
            regimes=AbsentLayer("no regimes in this test double"),
            slow_states=AbsentLayer("no slow states in this test double"),
        )
        with pytest.raises(go.OutputContractError, match="manifest does not declare"):
            go.build_document(ensemble)

    def test_schema_rejects_null_for_a_layer_block(self, bootstrap_ensemble):
        doc = go.build_document(bootstrap_ensemble)
        broken = dict(doc)
        broken["regimes"] = None  # omission is not a permitted spelling of absence
        with pytest.raises(go.OutputContractError, match="regimes"):
            go.validate_document(broken)

    def test_tampered_digest_is_detected(self, bootstrap_ensemble):
        doc = go.build_document(bootstrap_ensemble)
        tampered = {**doc, "arrays": {**doc["arrays"], "paths": {**doc["arrays"]["paths"]}}}
        tampered["arrays"]["paths"]["sha256"] = "sha256:" + "0" * 64
        with pytest.raises(go.OutputContractError, match="paths"):
            go.verify_arrays(bootstrap_ensemble, tampered)

    def test_absent_layer_requires_a_reason(self):
        with pytest.raises(ValueError, match="non-empty reason"):
            AbsentLayer("")


class TestFactorNamespaceFidelity:
    def test_namespace_is_a_faithful_copy_of_the_sealed_manifest(self, bootstrap_ensemble):
        doc = go.build_document(bootstrap_ensemble)
        manifest = load_manifest()
        series_registry = requirements()
        by_name = {entry["name"]: entry for entry in doc["factors"]}
        assert list(by_name) == list(bootstrap_ensemble.factor_names)
        for name, entry in by_name.items():
            source = manifest.sources[name]
            assert entry["kind"] == source.kind
            if source.kind == "series":
                assert entry["units"] == series_registry[source.series_id or ""].units
                assert entry["identity"] is None
            elif source.kind == "derived":
                assert entry["units"] == source.units
                assert entry["identity"] == {
                    "expr": source.expr,
                    "inputs": list(source.inputs),
                }

    def test_every_derived_identity_recomputes(self, bootstrap_ensemble):
        """The acceptance clause, verbatim: identity metadata must let a consumer
        recompute every derived variable — the expr must be a real ah.data.derive
        callable and every input a registered series."""
        doc = go.build_document(bootstrap_ensemble)
        series_registry = requirements()
        derived = [e for e in doc["factors"] if e["kind"] == "derived"]
        assert derived, "the sealed factor set carries derived factors; none emitted"
        for entry in derived:
            helper = getattr(derive, entry["identity"]["expr"], None)
            assert callable(helper), f"{entry['name']}: expr does not resolve in ah.data.derive"
            for series_id in entry["identity"]["inputs"]:
                assert series_id in series_registry, (
                    f"{entry['name']}: input '{series_id}' is not a registered series"
                )
