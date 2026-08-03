"""WP2.7 assemble: the 7-step algorithm, acceptance filter, lineage, disjointness."""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.worldspec import Horizon
from ah.gen.base import Ensemble
from ah.gen.joinery import assemble as asm
from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

ROOT = Path(__file__).resolve().parents[1]

MONTHS = 24  # smoke-sized decades (2 years); the real run uses 120 via the script


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(tmp_path_factory.mktemp("climate"))


@pytest.fixture(scope="module")
def regimes_artifact(tmp_path_factory):
    return make_regimes_artifact(tmp_path_factory.mktemp("regimes"))


@pytest.fixture(scope="module")
def source():
    return make_source()


def _assemble(climate, regimes_artifact, source, **kw):
    from typing import Any

    defaults: dict[str, Any] = dict(n_decades=8, months=MONTHS, seed=1234)
    defaults.update(kw)
    return asm.assemble_decades(
        climate=climate, regimes_artifact=regimes_artifact, source=source, **defaults
    )


# --------------------------------------------------------------------------- #
# the acceptance-filter/enforce disjointness proof (the plan's named test)
# --------------------------------------------------------------------------- #


class TestFilterDisjointness:
    def test_filter_metrics_disjoint_from_every_sealed_enforce_name(self):
        """Loads pre-registration.yaml, collects severity: enforce names, asserts
        disjointness — the filter may not teach to the exam."""
        doc = yaml.safe_load((ROOT / "pre-registration.yaml").read_text("utf-8"))
        enforce: set[str] = set()

        def walk(node, name=None):
            if isinstance(node, dict):
                if node.get("severity") == "enforce" and name is not None:
                    enforce.add(name)
                for key, value in node.items():
                    walk(value, key)
            elif isinstance(node, list):
                for item in node:
                    walk(item, name)

        walk(doc.get("thresholds", {}))
        assert enforce  # the sealed manifest does carry enforce names
        # strategy-level keys are dotted ("carry.var_95"); compare bare names too
        bare = {name.split(".")[-1] for name in enforce}
        assert set(asm.FILTER_METRICS).isdisjoint(enforce)
        assert set(asm.FILTER_METRICS).isdisjoint(bare)

    def test_filter_metrics_feed_no_enforce_band_family(self):
        """Substantive (not just nominal) disjointness: the two enforce-tier band
        gates aggregate named per-factor statistics; the filter subset must not
        contain any of them. (A test module may import ah.eval; joinery may not.)"""
        from ah.eval.metrics.monthly import BAND_EXCEEDANCE_FAMILIES

        doc = yaml.safe_load((ROOT / "pre-registration.yaml").read_text("utf-8"))
        panel = doc["thresholds"]["panel"]
        for family, members in BAND_EXCEEDANCE_FAMILIES.items():
            if panel.get(family, {}).get("severity") == "enforce":
                assert set(asm.FILTER_METRICS).isdisjoint(members), family

    def test_joinery_never_imports_ah_eval(self):
        """The filter statistics are local numpy implementations, structurally:
        no module under ah/gen/joinery imports anything from ah.eval."""
        joinery = ROOT / "src" / "ah" / "gen" / "joinery"
        offenders = []
        for path in sorted(joinery.glob("*.py")):
            tree = ast.parse(path.read_text("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                offenders += [
                    f"{path.name}: {name}" for name in names if name.startswith("ah.eval")
                ]
        assert offenders == []


# --------------------------------------------------------------------------- #
# layer seed hygiene
# --------------------------------------------------------------------------- #


class TestLayerSeeds:
    def test_offsets_never_collide_across_layers(self):
        # Streams are PCG64(base + offset + 7919*k). Two layers collide for SOME
        # pair of decade indices iff their offset difference is a multiple of
        # 7919 — so no offset, and no pairwise difference, may be one.
        offsets = list(asm.LAYER_SEED_OFFSETS.values())
        assert len(set(offsets)) == len(offsets)
        for i, a in enumerate(offsets):
            for b in offsets[i + 1 :]:
                assert (a - b) % asm.SEED_STRIDE != 0
            if a != 0:
                assert a % asm.SEED_STRIDE != 0


# --------------------------------------------------------------------------- #
# end-to-end assembly
# --------------------------------------------------------------------------- #


class TestAssembleDecades:
    def test_shapes_and_lineage_metadata(self, climate, regimes_artifact, source):
        ens = _assemble(climate, regimes_artifact, source)
        assert isinstance(ens, Ensemble)
        assert ens.paths.shape == (8, MONTHS, 15)  # campaign-2 factor set
        assert ens.factor_names == list(source.factor_names)
        assert ens.meta.generator_id == asm.GENERATOR_ID
        assert ens.meta.vintage_id == source.vintage_id
        assert ens.meta.active_blocks == ("global", "us", "fx", "valuation")

        cond = ens.meta.conditioning
        arts = cond["layer_artifacts"]
        assert arts["climate_sha256"] == climate.meta["content_sha256"]
        assert arts["regimes_sha256"] == regimes_artifact.meta["content_sha256"]
        assert cond["layer_seeds"] == {
            "climate": 1234,
            "regimes": 1234 + asm.LAYER_SEED_OFFSETS["regimes"],
            "blocks": 1234 + asm.LAYER_SEED_OFFSETS["blocks"],
        }
        assert cond["one_pass"] is True
        assert cond["ruleset_version"] == "regime_ruleset_v1"
        assert cond["cb_contract"]["schema"] == "cb-v1"
        assert len(cond["support"]["extrapolation_share_by_decade"]) == 8
        assert "reconciliation" in cond
        assert cond["reconciliation"]["per_factor"]["policy_rate"]["variant"] == "additive"
        assert cond["waypoint_tolerance"]["all_ok"] in (True, False)
        # the whole record must be JSON-serializable (it lands in RunRecords)
        json.dumps(cond)

    def test_bit_identical_per_seed(self, climate, regimes_artifact, source):
        a = _assemble(climate, regimes_artifact, source)
        b = _assemble(climate, regimes_artifact, source)
        np.testing.assert_array_equal(a.paths, b.paths)
        assert a.meta.conditioning == b.meta.conditioning
        c = _assemble(climate, regimes_artifact, source, seed=99)
        assert not np.array_equal(a.paths, c.paths)

    def test_waypoint_tolerance_met_on_the_assembled_ensemble(
        self, climate, regimes_artifact, source
    ):
        # The plan's first acceptance item, asserted on the emitted ensemble:
        # post-reconciliation annual aggregates hit the waypoints within config
        # tolerance for every decade (recorded per-decade during assembly).
        ens = _assemble(climate, regimes_artifact, source)
        tol = ens.meta.conditioning["waypoint_tolerance"]
        assert tol["all_ok"] is True
        assert tol["n_decades_ok"] == 8

    def test_filter_rejects_worst_decile_and_logs_everything(
        self, climate, regimes_artifact, source
    ):
        ens = _assemble(climate, regimes_artifact, source, n_decades=20)
        log = ens.meta.conditioning["acceptance_filter"]
        assert log["enabled"] is True
        assert log["metrics"] == list(asm.FILTER_METRICS)
        assert log["n_rejected"] == 2  # floor(0.10 * 20)
        assert log["n_rejected"] <= int(0.10 * 20)
        for entry in log["rejections"]:
            for key in (
                "decade",
                "score",
                "decade_seed",
                "replacement_index",
                "replacement_seed",
                "replacement_score",
            ):
                assert key in entry
            # Regression (first 1024-decade run): the replacement score must be on
            # the SAME frozen scale as the ensemble scores — a scale re-derived
            # from the replacement's own 1-row stat matrix degenerates the MAD to
            # ~0 and logs a meaningless ~1e12 number.
            assert np.isfinite(entry["replacement_score"])
            assert entry["replacement_score"] <= asm._NAN_PENALTY

    def test_filter_off_leaves_every_decade_in_place(self, climate, regimes_artifact, source):
        cfg = asm.JoineryConfig(acceptance_filter=False)
        ens = _assemble(climate, regimes_artifact, source, n_decades=20, config=cfg)
        log = ens.meta.conditioning["acceptance_filter"]
        assert log["enabled"] is False
        assert log["n_rejected"] == 0
        assert log["rejections"] == []

    def test_filtered_and_unfiltered_differ_only_at_rejected_decades(
        self, climate, regimes_artifact, source
    ):
        unfiltered = _assemble(
            climate,
            regimes_artifact,
            source,
            n_decades=20,
            config=asm.JoineryConfig(acceptance_filter=False),
        )
        filtered = _assemble(climate, regimes_artifact, source, n_decades=20)
        rejected = {
            e["decade"] for e in filtered.meta.conditioning["acceptance_filter"]["rejections"]
        }
        assert rejected
        for k in range(20):
            same = np.array_equal(filtered.paths[k], unfiltered.paths[k])
            assert same == (k not in rejected)

    def test_support_diagnostic_populates_per_decade(self, climate, regimes_artifact, source):
        ens = _assemble(climate, regimes_artifact, source)
        support = ens.meta.conditioning["support"]
        shares = support["extrapolation_share_by_decade"]
        assert len(shares) == 8
        assert all(0.0 <= s <= 1.0 for s in shares)
        assert support["quantile"] == 0.99
        assert "n_flagged_off_support" in support
        assert len(support["regime_freq_tv_by_decade"]) == 8


# --------------------------------------------------------------------------- #
# WorldSpec binding through the assembled system
# --------------------------------------------------------------------------- #


def _fixture_world(months: int):
    world = project_numeric(
        load_worldspec(ROOT / "fixtures/worlds/conditional/rate_endpoints_mild.worldspec.json")
    )
    return dataclasses.replace(world, horizon=Horizon(start="2027-Q1", quarters=months // 3))


class TestWorldBinding:
    def test_authored_policy_path_binds_the_emitted_ensemble(
        self, climate, regimes_artifact, source
    ):
        world = _fixture_world(MONTHS)  # policy 5.0 -> 2.0 linear
        ens = _assemble(climate, regimes_artifact, source, n_decades=4, world=world)
        policy = ens.factor("policy_rate")
        n_years = MONTHS // 12
        tau = (np.arange(n_years) + 0.5) / n_years
        want = 5.0 + (2.0 - 5.0) * tau
        for k in range(4):
            got = [float(policy[k, 12 * y : 12 * (y + 1)].mean()) for y in range(n_years)]
            np.testing.assert_allclose(got, want, atol=1e-6)
        assert ens.meta.conditioning["regime_mode"] == "unconditional"
        assert ens.meta.conditioning["factor_conditions"]["policy_override"]["bound"] is True

    def test_sequence_world_pins_the_regime_path(self, climate, regimes_artifact, source):
        from ah.core.worldspec import Regimes

        world = _fixture_world(MONTHS)
        seq_regimes = Regimes.model_validate(
            {
                "mode": "sequence",
                "sequence": [
                    {"regime": "stagflation", "from_quarter": 0, "to_quarter": MONTHS // 3 - 1}
                ],
            }
        )
        world = dataclasses.replace(world, regimes=seq_regimes)
        ens = _assemble(climate, regimes_artifact, source, n_decades=2, world=world)
        assert ens.meta.conditioning["regime_mode"] == "sequence"
        # STAG has no stratum in the synthetic source? it does (default labels
        # carry STAG), so blocks were drawn from the STAG stratum; the regime
        # record shows a pure STAG mix.
        support = ens.meta.conditioning["support"]
        assert support["regime_frequencies_pooled"]["STAG"] == pytest.approx(1.0)

    def test_horizon_mismatch_raises(self, climate, regimes_artifact, source):
        world = _fixture_world(120)
        with pytest.raises(asm.wp.JoineryError, match="horizon"):
            _assemble(climate, regimes_artifact, source, n_decades=2, months=MONTHS, world=world)


# --------------------------------------------------------------------------- #
# the Generator wrapper + registry
# --------------------------------------------------------------------------- #


class TestGeneratorWrapper:
    def test_registered_id_resolves_and_samples(self, climate, regimes_artifact, source):
        gen = asm.JoineryBootstrapV0(climate, regimes_artifact, source)
        world = _fixture_world(MONTHS)
        ens = gen.sample(world, n_paths=3, seed=7)
        assert ens.paths.shape == (3, MONTHS, 15)  # campaign-2 factor set
        assert ens.meta.generator_id == asm.GENERATOR_ID

    def test_generator_id_is_registered(self):
        from ah.gen import registry

        assert asm.GENERATOR_ID in registry.registered()

    def test_two_pass_flag_changes_credit_channel_only_by_default_off(
        self, regimes_artifact, tmp_path
    ):
        # The default is ONE-PASS (the WP2.6-certified ordering). two_pass re-runs
        # L1 with L2's c_t: same seed, same theta/innovations, only the credit-gap
        # forcing changes — so with a REAL spread-on-gap loading (planted beta) the
        # spread waypoints, and hence the reconciled paths, must move.
        from joinery_common import make_planted_beta_pair

        climate2, source2 = make_planted_beta_pair(tmp_path, beta=0.3)
        one_pass = _assemble(climate2, regimes_artifact, source2, n_decades=2)
        two_pass = _assemble(
            climate2,
            regimes_artifact,
            source2,
            n_decades=2,
            config=asm.JoineryConfig(two_pass=True),
        )
        assert one_pass.meta.conditioning["one_pass"] is True
        assert two_pass.meta.conditioning["one_pass"] is False
        assert not np.array_equal(one_pass.paths, two_pass.paths)
        # the change is confined to the credit channel: equity paths identical
        np.testing.assert_array_equal(one_pass.factor("equity_mkt"), two_pass.factor("equity_mkt"))
