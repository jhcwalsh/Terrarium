"""The generator→engine adapter (su-gen-01, Task 1 of the generated-worlds plan).

The adapter is the seam the Task 0 survey named: a generator-backed
``run_gen_ensemble``/``run_gen_path`` pair that maps a 16-factor bootstrap
``Ensemble`` into the toy engine's ``EnsembleResult``/``EnginePaths`` contracts
so digest, replay, twin, play, and bundle stay untouched.

Owner decisions applied here: OD-3 — reits is DROPPED in generated worlds
(no factor exists; no invented proxy); the reits start weight moves to equity
(its 0.84-correlated public neighbour), stated in the adapter.

Tests run against a synthetic 16-factor ``BootstrapSource`` (the
test_bootstrap.py pattern) — no vintage store, no network. The one test that
needs the real catalog is guarded on ``data/`` presence.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import ah.gen.bootstrap as bs
from ah.core.digest import digest_ensemble, digest_paths
from ah.core.engine import ASSETS, REPORTED_SLEEVES, EnginePaths, EnsembleResult
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.gen import registry
from ah.port.adapter import (
    GEN_ASSETS,
    PM_SLEEVE_FOR_ASSET,
    run_gen_ensemble,
    run_gen_path,
)

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "src" / "ah" / "presets" / "stagflation.json"
SEED = 197400


def _synthetic_source_16(n_rows: int = 72) -> bs.BootstrapSource:
    """A 16-factor source with per-factor realistic scales, deterministic in
    the row index, so adapter conversions are checkable without the catalog."""
    i = np.arange(n_rows, dtype=np.float64)
    cols = {
        "cape_v": 0.2 + 0.01 * np.sin(i / 5.0),
        "commodities": 0.02 * np.sin(i / 3.0),
        "cpi": 100.0 * (1.003**i),
        "equity_mkt": 0.015 * np.sin(i / 4.0) + 0.005,
        "equity_vol": 18.0 + 3.0 * np.sin(i / 6.0),
        "funding_spread": 0.7 + 0.1 * np.sin(i / 7.0),
        "fx_usd": 120.0 + 5.0 * np.sin(i / 9.0),
        "hml": 0.004 * np.sin(i / 5.5),
        "hqm_curve": 6.5 + 0.5 * np.sin(i / 8.0),
        "hy_spread": 4.0 + 1.0 * np.sin(i / 6.5),
        "ig_spread": 1.0 + 0.3 * np.sin(i / 6.0),
        "mom": 0.006 * np.sin(i / 4.5),
        "policy_rate": 5.0 + 1.0 * np.sin(i / 10.0),
        "smb": 0.003 * np.sin(i / 3.5),
        "ust_10y": 6.0 + 0.8 * np.sin(i / 11.0),
        "ust_2y": 5.5 + 0.9 * np.sin(i / 10.5),
    }
    names = tuple(sorted(cols))  # bootstrap panels are alphabetical
    values = np.column_stack([cols[n] for n in names])
    cycle = ("EXP", "EXP", "STAG", "STAG", "REC", "CRI", "REF", "SLOW")
    labels = tuple(cycle[k % len(cycle)] for k in range(n_rows))
    dates = pd.DatetimeIndex(pd.date_range("1970-01-01", periods=n_rows, freq="MS"))
    return bs.BootstrapSource(
        factor_names=names,
        dates=dates,
        values=values,
        labels=labels,
        ruleset_version="regime_ruleset_v1",
        vintage_id="test-vintage",
        active_blocks=("global", "us"),
    )


def _gen_world():
    doc = copy.deepcopy(json.loads(PRESET.read_text(encoding="utf-8")))
    doc["engine_defaults"]["generator_id"] = "bootstrap-v1"
    return project_numeric(WorldSpec.model_validate(doc))


@pytest.fixture()
def synthetic_registry():
    saved = registry.snapshot()
    source = _synthetic_source_16()
    registry.register("bootstrap-v1", lambda: bs.BootstrapV1(source))
    try:
        yield source
    finally:
        registry.restore(saved)


class TestEnsembleContract:
    def test_result_is_an_engine_ensemble_over_gen_assets(self, synthetic_registry):
        """The adapter returns the toy dataclass with reits dropped (OD-3)."""
        result = run_gen_ensemble(_gen_world(), 4, base_seed=SEED)
        assert isinstance(result, EnsembleResult)
        assert result.asset_order == GEN_ASSETS
        assert "reits" not in GEN_ASSETS
        assert tuple(a for a in ASSETS if a != "reits") == GEN_ASSETS
        assert set(result.returns) == set(GEN_ASSETS)
        assert set(result.reported) == set(REPORTED_SLEEVES)
        for a in GEN_ASSETS:
            assert result.returns[a].shape == (4, result.months)

    def test_equity_and_commodities_are_the_factors_in_percent(self, synthetic_registry):
        """Return-bearing factors are DECIMAL; the engine contract is PERCENT."""
        world = _gen_world()
        result = run_gen_ensemble(world, 3, base_seed=SEED)
        gen = registry.resolve_for_world(world)
        for k in range(3):
            ref = gen.sample(world, 1, SEED + 7919 * k)
            np.testing.assert_allclose(
                result.returns["equity"][k], ref.factor("equity_mkt")[0] * 100.0
            )
            np.testing.assert_allclose(
                result.returns["commodities"][k], ref.factor("commodities")[0] * 100.0
            )

    def test_path_k_of_the_ensemble_is_run_gen_path_at_the_strided_seed(self, synthetic_registry):
        """The toy invariant run_path(base+7919k) == ensemble path k carries over."""
        world = _gen_world()
        result = run_gen_ensemble(world, 3, base_seed=SEED)
        for k in range(3):
            p = run_gen_path(world, SEED + 7919 * k)
            assert isinstance(p, EnginePaths)
            for a in GEN_ASSETS:
                np.testing.assert_array_equal(p.returns[a], result.returns[a][k])

    def test_crisis_mask_comes_from_the_regime_record(self, synthetic_registry):
        """Bootstrap ignores crisis_windows; CRI months in the realized regime
        path are the crisis mask."""
        world = _gen_world()
        p = run_gen_path(world, SEED)
        gen = registry.resolve_for_world(world)
        ref = gen.sample(world, 1, SEED)
        from ah.gen.base import RegimeRecord

        assert isinstance(ref.regimes, RegimeRecord)
        codes = np.asarray(ref.regimes.labels)[0]
        legend = tuple(ref.regimes.legend)
        expected = (codes == legend.index("CRI")).astype(float)
        np.testing.assert_array_equal(p.crisis, expected)

    def test_spread_channel_is_hy_spread_in_bps(self, synthetic_registry):
        """The toy spread channel is the HY spread in bps (play's 400bp
        reference, the feed's 800bp threshold); hy_spread is percent."""
        world = _gen_world()
        p = run_gen_path(world, SEED)
        gen = registry.resolve_for_world(world)
        ref = gen.sample(world, 1, SEED)
        np.testing.assert_allclose(p.spread, ref.factor("hy_spread")[0] * 100.0)

    def test_reported_marks_are_quarter_end_only(self, synthetic_registry):
        """The reported plane keeps the toy shape: zeros except quarter-ends."""
        result = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        for s in REPORTED_SLEEVES:
            rep = result.reported[s]
            months = rep.shape[1]
            for m in range(months):
                if (m + 1) % 3 != 0:
                    np.testing.assert_array_equal(rep[:, m], 0.0)
            assert np.abs(rep[:, 2::3]).sum() > 0.0

    def test_private_assets_use_the_pm_sleeve_mappings(self, synthetic_registry):
        """pe/pc/re truths come from the sealed PM loadings applied at monthly
        frequency (alpha_quarterly/3), systematic only — the stated convention."""
        assert PM_SLEEVE_FOR_ASSET == {
            "pe": "pm_buyout",
            "pc": "pm_direct_lending",
            "re": "pm_re_value_add",
        }
        result = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        # not the equity series and not zeros: the loadings actually applied
        assert np.abs(result.returns["pe"]).sum() > 0.0
        assert not np.allclose(result.returns["pe"], result.returns["equity"])


class TestDigestThreading:
    def test_gen_results_digest_without_reits(self, synthetic_registry):
        result = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        d1 = digest_ensemble(result)
        d2 = digest_ensemble(run_gen_ensemble(_gen_world(), 2, base_seed=SEED))
        assert d1 == d2 and d1.startswith("sha256:")

    def test_gen_path_digest_is_stable(self, synthetic_registry):
        p1 = run_gen_path(_gen_world(), SEED)
        p2 = run_gen_path(_gen_world(), SEED)
        assert digest_paths(p1) == digest_paths(p2)

    def test_toy_digests_are_byte_identical_to_before_the_threading(self):
        """The asset_order default must preserve every existing toy digest:
        recompute one the old way (fixed ASSETS iteration) and compare."""
        from ah.core.digest import sha256_of_arrays
        from ah.core.engine import run_ensemble

        doc = json.loads(PRESET.read_text(encoding="utf-8"))
        nw = project_numeric(WorldSpec.model_validate(doc))
        ens = run_ensemble(nw, 8, base_seed=771204)
        old_way = sha256_of_arrays(
            [ens.returns[a] for a in ASSETS] + [ens.reported[s] for s in REPORTED_SLEEVES]
        )
        assert digest_ensemble(ens) == old_way


class TestTwinAndDispatch:
    def test_gen_start_mix_moves_reits_weight_to_equity(self):
        """OD-3: reits' 5 points go to equity (its 0.84-correlated public
        neighbour); the mix still sums to 1 over GEN_ASSETS."""
        from ah.core.institution import START_MIX
        from ah.port.adapter import GEN_START_MIX

        assert set(GEN_START_MIX) == set(GEN_ASSETS)
        assert GEN_START_MIX["equity"] == pytest.approx(START_MIX["equity"] + START_MIX["reits"])
        assert sum(GEN_START_MIX.values()) == pytest.approx(1.0)
        for a in GEN_ASSETS:
            if a != "equity":
                assert GEN_START_MIX[a] == pytest.approx(START_MIX[a])

    def test_hold_course_twin_runs_on_generated_paths(self, synthetic_registry):
        """The institution accepts the generated sleeve set; the twin produces
        a finite final value and a weights panel over 7 sleeves."""
        from ah.port.adapter import gen_hold_course_twin

        twin = gen_hold_course_twin(_gen_world(), SEED)
        assert np.isfinite(twin.final_value)
        assert twin.weights.shape[1] == len(GEN_ASSETS)

    def test_compute_outputs_digest_dispatches_for_generated_worlds(self, synthetic_registry):
        """Replay's anchor must recompute a generated run's digest through the
        adapter, so verify_run stays MATCH for generated worlds."""
        from ah.store.runrecords import compute_outputs_digest

        doc = copy.deepcopy(json.loads(PRESET.read_text(encoding="utf-8")))
        doc["engine_defaults"]["generator_id"] = "bootstrap-v1"
        expected = digest_ensemble(run_gen_ensemble(_gen_world(), 3, base_seed=SEED))
        assert compute_outputs_digest(doc, SEED, 3) == expected

    def test_gen_lineage_pins_generator_and_vintage(self, synthetic_registry):
        """The resolved_engine stamp must say what actually produced the
        numbers: the generator id/version and the campaign vintage (OD-4)."""
        from ah.port.adapter import gen_lineage

        lineage = gen_lineage(_gen_world())
        assert lineage["generator_id"] == "bootstrap-v1"
        assert lineage["generator_version"] == "bootstrap-v1"
        assert lineage["campaign_vintage_id"] == "test-vintage"


@pytest.mark.skipif(
    not (ROOT / "data" / "catalog.duckdb").exists(),
    reason="vintage store is local-only by design (OD-4); the synthetic-source "
    "tests above cover the adapter logic on every checkout",
)
class TestAgainstTheRealPanel:
    def test_er9_bound_holds_on_a_real_sample(self):
        """No generated equity month can be worse than the panel's worst real
        month (survey S4: -22.59%, Oct 1987)."""
        world = _gen_world()
        result = run_gen_ensemble(world, 16, base_seed=SEED)
        assert result.returns["equity"].min() >= -22.60
        assert result.returns["equity"].min() <= -1.0  # a real sample moves

    def test_the_1974_preset_builds_runs_and_replays_match(self, tmp_path):
        """Task 1 acceptance end to end: build the OD-1 world, run through the
        adapter, replay bit-identical, and stamp the honest lineage."""
        from typer.testing import CliRunner

        from ah.cli import app
        from ah.store import runrecords as run_store

        runner = CliRunner()
        db = tmp_path / "gen.db"

        def invoke(*args: str):
            r = runner.invoke(app, ["--db", str(db), *args])
            assert r.exit_code == 0, r.output
            return r

        build = invoke("world", "build", "--preset", "stagflation_1974")
        assert "00000000-0000-4000-9000-000000000601" in build.output
        rid = invoke("run", "--paths", "12").output.strip().splitlines()[-1]
        replay = invoke("replay", rid)
        assert "MATCH" in replay.output

        import sqlite3

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rec = run_store.get_run_record(conn, rid)
        assert rec is not None
        assert rec["resolved_engine"]["generator_id"] == "bootstrap-v1"
        assert rec["resolved_engine"]["generator_version"] == "bootstrap-v1"
        assert rec["resolved_engine"]["campaign_vintage_id"] == "2026-08-10.1"
