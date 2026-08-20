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
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 197400


def test_the_toy_presets_moved_to_the_52x_block():
    """The 52x sub-block is toy-v0.7 (gen_presets.py's documented convention:
    50x = toy-v0.5, 51x = toy-v0.6). The engine is not part of a WorldSpec, so
    world identity is the only place the difference between two engines can
    live, and the leaderboard is keyed (world_id, seed, decision_alpha_version)."""
    ids = {p.stem: json.loads(p.read_text())["world_id"][-3:] for p in PRESETS.glob("*.json")}
    assert ids["stagflation"] == "521" and ids["goldilocks"] == "522"
    assert ids["deflation_bust"] == "523" and ids["reflation_boom"] == "524"
    assert ids["prehistory"] == "525" and ids["stagflation_1974"] == "604"


from conftest import make_synthetic_source_16 as _synthetic_source_16  # noqa: E402


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
        """pe/pc/re/infra truths come from the sealed PM loadings applied at
        monthly frequency (alpha_quarterly/3), systematic only — the stated
        convention. ER-14 close-out (Task S4): infra maps to the ALREADY
        estimated pm_infra row (v1.1, 60 quarters) -- no new estimation."""
        assert PM_SLEEVE_FOR_ASSET == {
            "pe": "pm_buyout",
            "pc": "pm_direct_lending",
            "re": "pm_re_value_add",
            "infra": "pm_infra",
        }
        result = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        # not the equity series and not zeros: the loadings actually applied
        assert np.abs(result.returns["pe"]).sum() > 0.0
        assert not np.allclose(result.returns["pe"], result.returns["equity"])

    def test_infra_maps_to_the_already_estimated_pm_infra_row(self, synthetic_registry):
        """The pm_infra row already exists in the sealed v1.1 artifact -
        estimated, 60 quarters, sum-beta(2) - so the generated path needs NO
        new estimation for infrastructure (design 2.7.1). infra_core stays
        parked as Tier B evergreen."""
        import yaml

        assert PM_SLEEVE_FOR_ASSET["infra"] == "pm_infra"
        art = yaml.safe_load(
            (ROOT / "mappings" / "sleeve-mappings-v1.1.yaml").read_text(encoding="utf-8")
        )
        assert "pm_infra" in art["pm_sleeves"]

    def test_generated_assets_carry_infra_and_still_drop_reits(self):
        assert "infra" in GEN_ASSETS
        assert "reits" not in GEN_ASSETS  # OD-3 unchanged

    def test_the_pm_residual_matrix_widened_and_this_is_disclosed(self, synthetic_registry):
        """standard_normal fills row-major, so a fourth column re-rolls
        pe/pc/re. The generated plane's digests move in this release anyway
        (GEN_PLAY_ALPHA_VERSION bumps, the played world moves 603 -> 604).
        Recorded here so the next reader does not mistake it for corruption."""
        result = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        assert result.returns["infra"].shape == result.returns["pe"].shape
        assert np.abs(result.returns["infra"]).sum() > 0.0


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


class TestSourceSpaceDerivations:
    """The 1974 console preview caught seam artifacts: differencing resampled
    LEVEL factors across block seams fabricated an -88.8% bond month and a
    21,755% mean inflation. The fix: every derived series is computed on the
    SOURCE panel and indexed by the drawn rows, so a generated month's yield
    change / trailing inflation is that real month's own value."""

    @staticmethod
    def _col(source, name):
        return source.values[:, list(source.factor_names).index(name)]

    def _expected_bond_pct(self, source):
        y = self._col(source, "ust_10y") / 100.0
        out = np.empty_like(y)
        out[0] = y[0] / 12.0
        out[1:] = y[:-1] / 12.0 + 8.5 * (y[:-1] - y[1:])
        return out * 100.0

    def _expected_infl_pct(self, source):
        cpi = self._col(source, "cpi")
        out = np.zeros_like(cpi)
        for r in range(1, len(cpi)):
            back = min(r, 12)
            out[r] = ((cpi[r] / cpi[r - back]) ** (12.0 / back) - 1.0) * 100.0
        return out

    def test_the_ensemble_carries_the_drawn_row_indices(self, synthetic_registry):
        world = _gen_world()
        gen = registry.resolve_for_world(world)
        ref = gen.sample(world, 2, SEED)
        assert ref.row_indices is not None
        assert ref.row_indices.shape == (2, ref.months)
        n_rows = synthetic_registry.values.shape[0]
        assert ref.row_indices.min() >= 0 and ref.row_indices.max() < n_rows
        eq = self._col(synthetic_registry, "equity_mkt")
        np.testing.assert_allclose(ref.factor("equity_mkt"), eq[ref.row_indices])

    def test_bond_months_are_real_source_months(self, synthetic_registry):
        """bonds[t] must equal the source-space bond return of the drawn row —
        no yield change is ever computed across a block seam."""
        world = _gen_world()
        gen = registry.resolve_for_world(world)
        ref = gen.sample(world, 1, SEED)
        assert ref.row_indices is not None
        p = run_gen_path(world, SEED)
        expected = self._expected_bond_pct(synthetic_registry)[ref.row_indices[0]]
        np.testing.assert_allclose(p.returns["bonds"], expected)

    def test_inflation_is_the_source_months_own_trailing_yoy(self, synthetic_registry):
        world = _gen_world()
        gen = registry.resolve_for_world(world)
        ref = gen.sample(world, 1, SEED)
        assert ref.row_indices is not None
        p = run_gen_path(world, SEED)
        expected = self._expected_infl_pct(synthetic_registry)[ref.row_indices[0]]
        np.testing.assert_allclose(p.inflation, expected)

    def test_hy_carries_an_equity_sensitivity(self, synthetic_registry):
        """Carry + spread duration alone gave HY a decade Sharpe of 2.18 in
        the 1974 preview — real high yield moves with equities. The stated
        convention adds beta 0.4 on the equity factor."""
        world = _gen_world()
        gen = registry.resolve_for_world(world)
        ref = gen.sample(world, 1, SEED)
        assert ref.row_indices is not None
        p = run_gen_path(world, SEED)
        y10 = self._col(synthetic_registry, "ust_10y")
        hs = self._col(synthetic_registry, "hy_spread")
        all_in = y10 + 0.55 * hs
        wide = y10 + hs
        base = np.empty_like(y10)
        base[0] = all_in[0] / 12.0
        base[1:] = all_in[:-1] / 12.0 + 4.0 * (wide[:-1] - wide[1:])
        rows = ref.row_indices[0]
        expected = base[rows] + 0.4 * ref.factor("equity_mkt")[0] * 100.0
        np.testing.assert_allclose(p.returns["hy"], expected)

    def test_pm_sleeves_carry_their_sealed_residual_variance(self, synthetic_registry):
        """pc collapsed to 0.0 vol (its sealed loadings are structural zeros);
        the artifact's residual_sigma_annual must be drawn, reproducibly."""
        r1 = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        r2 = run_gen_ensemble(_gen_world(), 2, base_seed=SEED)
        pc = r1.returns["pc"]
        assert float(np.std(pc)) > 0.05  # not a constant
        np.testing.assert_array_equal(pc, r2.returns["pc"])  # deterministic
        assert not np.allclose(pc[0], pc[1])  # paths differ


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


class TestPlayAndFeed:
    """su-gen-02: the play walk and the tier-1 feed over generated tapes."""

    def test_simulate_play_runs_a_generated_tape(self, synthetic_registry):
        """The twin ledger's engine accepts the generated sleeve set: liquid
        sleeves come from the tape's own asset_order (no reits), opening
        targets from GEN_START_TARGETS (reits' 8 points to equity, then ER-14
        close-out's A15 carve: 3 more points from equity and 2 from re to
        infra, 41 -> 38)."""
        from ah.play import simulate_play
        from ah.port.adapter import GEN_START_TARGETS

        assert "reits" not in GEN_START_TARGETS
        assert GEN_START_TARGETS["equity"] == pytest.approx(38.0)
        assert sum(GEN_START_TARGETS.values()) == pytest.approx(98.0)  # +2 cash
        p = run_gen_path(_gen_world(), SEED)
        result = simulate_play(p, None, start_targets=GEN_START_TARGETS)
        assert len(result.quarters) == p.months // 3
        assert np.isfinite(result.quarters[-1].nav_true)

    def test_feed_builds_on_a_generated_tape(self, synthetic_registry):
        """The wire renders over a generated path: peers regenerate through
        the supplied path function and the generated start mix."""
        from ah.feed import build_tier1_feed
        from ah.port.adapter import GEN_START_MIX

        world = _gen_world()
        p = run_gen_path(world, SEED)
        items = build_tier1_feed(
            world,
            p,
            base_seed=SEED,
            n_peer_paths=3,
            run_path_fn=run_gen_path,
            start_mix=GEN_START_MIX,
        )
        assert items
        types = {i["type"] for i in items}
        assert "cb_statement" in types
        assert all(0 <= i["month"] < p.months for i in items)


PRESET_1974 = ROOT / "src" / "ah" / "presets" / "stagflation_1974.json"


def _gen_world_1974():
    doc = json.loads(PRESET_1974.read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


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
        adapter, replay bit-identical, and stamp the honest lineage.

        re-pinned under map-2026.08.2 (AM-2026-08-12-001): world fence 601->602.
        re-pinned again for ER-10 (toy-v0.6): world fence 602->603.
        re-pinned again for ER-14 close-out (toy-v0.7, D-ER14-2, 2026-08-18):
        world fence 603->604.
        """
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
        assert "00000000-0000-4000-9000-000000000604" in build.output
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

    def test_gen_reported_marks_catch_up_to_truth_er10(self):
        """ER-10 on the generated path: the adapter shares _reported_marks, so
        the 1974 world inherited the same 1/3-of-truth defect (pe: 27% reported
        vs 125% true)."""
        world = _gen_world_1974()
        seed = world.engine_defaults.base_seed
        p = run_gen_path(world, seed if seed is not None else SEED)
        for sleeve in ("pe", "pc", "re"):
            true_sum = float(p.returns[sleeve].sum())
            rep_sum = float(p.reported[sleeve].sum())
            ratio = rep_sum / true_sum
            assert 0.80 < ratio < 1.20, f"{sleeve}: reported/true {ratio:.2f}"


# --------------------------------------------------------------------------- #
# pe-drift-01: structural.private_equity.entry_multiple_drift_annual_pct is a
# TOY-PLANE-ONLY field. Read the finding note before changing anything here:
# docs/superpowers/specs/2026-08-19-pe-drift-finding.md
# --------------------------------------------------------------------------- #


class TestEntryMultipleDriftIsToyPlaneOnly:
    """The suspected ER-14 double charge (the authored -2.0 drift *plus* the
    endogenous mu_PE compression that was anchored ON that -2.0) is REAL on the
    toy plane and INERT on the generated plane.

    The reason is structural, not incidental: ``engine.run_path`` reads the
    field at ``_f(st.private_equity, "entry_multiple_drift_annual_pct", ...)``
    and adds it into ``pe``; the generated plane's PE comes from
    ``adapter._pm_true_monthly_path``, which builds pm_buyout out of the sealed
    v1.2 artifact's alpha/loadings/passthrough/residual and never touches
    ``world.structural`` at all. These tests pin BOTH halves, because a future
    change that starts reading the field on the generated plane would silently
    re-create the double charge that D-ER14-2/A5 zeroed the live presets to
    avoid.
    """

    def test_the_field_does_not_reach_the_generated_plane(self, synthetic_registry):
        """Bit-identical PE, true and reported, at the schema's two extremes
        (-6 and +4). A generated world's private equity cannot see this field."""
        doc = copy.deepcopy(json.loads(PRESET.read_text(encoding="utf-8")))
        doc["engine_defaults"]["generator_id"] = "bootstrap-v1"

        def paths(drift: float) -> EnginePaths:
            d = copy.deepcopy(doc)
            d["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] = drift
            return run_gen_path(project_numeric(WorldSpec.model_validate(d)), SEED)

        low, high = paths(-6.0), paths(4.0)  # the schema's declared min and max
        np.testing.assert_array_equal(low.returns["pe"], high.returns["pe"])
        np.testing.assert_array_equal(low.reported["pe"], high.reported["pe"])
        # ...and nothing else on the tape moves either.
        for a in GEN_ASSETS:
            np.testing.assert_array_equal(low.returns[a], high.returns[a])

    def test_the_field_DOES_reach_the_toy_plane(self):
        """The control. Without this the test above proves nothing — a probe
        that cannot detect the field on the plane that certainly consumes it is
        measuring its own plumbing. The toy charge is exactly drift/12 per
        month, which is the half D-ER14-2/A5 removed from the live presets."""
        from ah.core.engine import run_path

        doc = copy.deepcopy(json.loads(PRESET.read_text(encoding="utf-8")))

        def pe(drift: float) -> np.ndarray:
            d = copy.deepcopy(doc)
            d["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] = drift
            return run_path(project_numeric(WorldSpec.model_validate(d)), SEED).returns["pe"]

        diff = pe(-2.0) - pe(0.0)
        assert not np.array_equal(pe(-2.0), pe(0.0))
        np.testing.assert_allclose(diff, np.full_like(diff, -2.0 / 12.0), atol=1e-12)

    def test_the_live_successor_presets_do_not_hand_author_the_drift(self):
        """er14-06 created 711/712/713 by copying the shape of the RETIRED
        701/703 records, which carry -2.0 by design (they are frozen records of
        a pre-mu_PE engine). That copy carried the -2.0 across the D-ER14-2/A5
        zeroing line. Inert on this plane today — pinned so it stays a
        deliberate choice rather than an inherited accident."""
        for stem in ("gulf_decade", "stress_1974_successor", "stress_1990_successor"):
            doc = json.loads((PRESETS / f"{stem}.json").read_text(encoding="utf-8"))
            assert doc["engine_defaults"]["generator_id"] == "bootstrap-stratified", stem
            assert doc["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] == 0.0, (
                stem
            )
