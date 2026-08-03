"""WP2.8 diffusion tests — EDM identities, determinism, BlockSampler protocol."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ah.gen.blocks import constraints as ct
from ah.gen.blocks import data as bd
from ah.gen.blocks import diffusion as df
from ah.gen.bootstrap import FACTOR_SET
from ah.gen.joinery import bridge
from ah.gen.joinery.waypoints import (
    RATE_FLOOR_FACTORS,
    RATE_FLOOR_PCT,
    SPREAD_FLOOR_FACTORS,
    SPREAD_FLOOR_PCT,
    JoineryError,
)
from joinery_common import make_climate_artifact, make_source

SMALL = df.DiffusionConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=5)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    source = make_source(n_rows=240)
    climate = make_climate_artifact(
        tmp_path_factory.mktemp("clim-diff"), t_months=480, state_noise=0.05
    )
    return bd.build_dataset(source, climate, validation_start_date="2005-01-01")


@pytest.fixture(scope="module")
def sampler(dataset):
    torch.manual_seed(0)
    model = df.ConditionalDenoiser(SMALL)
    return df.DiffusionBlockSampler(
        model,
        dataset.standardization,
        dataset.factor_names,
        trained_fingerprint=bridge.contract_fingerprint(),
    )


class TestModel:
    def test_parameter_count_is_small(self):
        model = df.ConditionalDenoiser(df.DiffusionConfig())
        n = sum(p.numel() for p in model.parameters())
        assert n < 2_000_000  # "low millions at most" — default is ~0.6M

    def test_zero_init_makes_denoiser_near_identity_at_low_sigma(self):
        model = df.ConditionalDenoiser(SMALL)
        x = torch.randn(4, SMALL.block_months, SMALL.n_factors)
        cond = torch.randn(4, SMALL.cond_dim)
        sigma = torch.full((4,), 1e-3)
        with torch.no_grad():
            d = model.denoise(x, sigma, cond)
        # c_skip -> 1, c_out -> 0 as sigma -> 0, and F_theta is zero-init.
        assert float((d - x).abs().max()) < 1e-4

    def test_conditioning_conditions(self):
        torch.manual_seed(1)
        model = df.ConditionalDenoiser(SMALL)
        # give the zero-init output head weights so cond can reach the output
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.1)
        x = torch.randn(2, SMALL.block_months, SMALL.n_factors)
        sigma = torch.ones(2)
        c1 = torch.zeros(2, SMALL.cond_dim)
        c2 = torch.ones(2, SMALL.cond_dim)
        with torch.no_grad():
            d1 = model.denoise(x, sigma, c1)
            d2 = model.denoise(x, sigma, c2)
        assert float((d1 - d2).abs().max()) > 1e-6


class TestSampler:
    def test_karras_schedule_shape_and_monotonicity(self):
        sig = df.karras_sigmas(31, SMALL)
        assert sig.shape[0] == 17  # 16 steps + terminal zero
        assert float(sig[0]) == pytest.approx(SMALL.sigma_max)
        assert float(sig[-1]) == 0.0
        assert bool((sig[:-1] > sig[1:]).all())

    def test_nfe_is_exactly_the_model_eval_count(self):
        model = df.ConditionalDenoiser(SMALL)
        calls = 0
        original = model.denoise

        def counting(x, sigma, cond):
            nonlocal calls
            calls += 1
            return original(x, sigma, cond)

        model.denoise = counting  # type: ignore[method-assign]
        noise = torch.randn(2, SMALL.block_months, SMALL.n_factors)
        cond = torch.zeros(2, SMALL.cond_dim)
        df.sample_heun(model, cond, noise, nfe=9)
        assert calls == 9

    def test_sampling_is_deterministic_given_the_numpy_rng(self, sampler, dataset):
        cond = bridge.BlockConditioning(
            regime_onehot=np.eye(6)[0],
            state_snapshot=np.zeros(5),
            history_summary=np.zeros(3),
            waypoint_increments=np.zeros(4),
            start_month=0,
        )
        a = sampler.sample_block(cond, np.random.Generator(np.random.PCG64(42)))
        b = sampler.sample_block(cond, np.random.Generator(np.random.PCG64(42)))
        np.testing.assert_array_equal(a, b)
        c = sampler.sample_block(cond, np.random.Generator(np.random.PCG64(43)))
        assert not np.array_equal(a, c)

    def test_untrained_extreme_output_still_respects_floors(self, sampler):
        """Constraint exactness through the FULL sampling path — an untrained
        model driven by extreme noise can never emit a floor violation."""
        rng = np.random.Generator(np.random.PCG64(7))
        conds = 50.0 * rng.standard_normal((16, bridge.C_B_DIM))
        noise = 20.0 * rng.standard_normal((16, SMALL.block_months, len(FACTOR_SET)))
        blocks = sampler.sample_batch(conds, noise)
        for j, name in enumerate(FACTOR_SET):
            if name in RATE_FLOOR_FACTORS:
                assert np.all(blocks[..., j] >= RATE_FLOOR_PCT)
            if name in SPREAD_FLOOR_FACTORS:
                assert np.all(blocks[..., j] >= SPREAD_FLOOR_PCT)
            if name in ct.LOG1P_FACTORS:
                assert np.all(blocks[..., j] >= -1.0)

    def test_implements_the_frozen_block_sampler_protocol(self, sampler):
        assert isinstance(sampler, bridge.BlockSampler)
        assert isinstance(sampler, bridge.BatchedBlockSampler)  # WP2.8b extension
        assert sampler.block_months == SMALL.block_months
        assert sampler.factor_names == FACTOR_SET

    def test_contract_fingerprint_mismatch_refuses_loudly(self, dataset):
        model = df.ConditionalDenoiser(SMALL)
        with pytest.raises(JoineryError, match="contract mismatch"):
            df.DiffusionBlockSampler(
                model,
                dataset.standardization,
                dataset.factor_names,
                trained_fingerprint="not-the-contract",
            )

    def test_drives_the_joinery_bridge_end_to_end(self, sampler, dataset):
        """assemble_decade_path accepts the sampler exactly as it accepts the
        bootstrap stand-in — the wiring WP2.10's system D relies on."""
        from ah.gen.joinery import waypoints as wp

        months = 24
        labels = np.zeros(months, dtype=np.int64)
        waypoints = wp.DecadeWaypoints(
            policy_pct=np.full(2, 3.0),
            inflation_pct=np.full(2, 2.5),
            equity_log_drift=np.full(2, 0.06),
            spread_center_pct=np.full(2, 1.0),
            spread_lo_pct=np.full(2, 0.8),
            spread_hi_pct=np.full(2, 1.2),
            labels=labels,
            cycle=np.ones(months),
        )
        raw, conds = bridge.assemble_decade_path(
            months=months,
            waypoints=waypoints,
            targets=None,
            states_row=np.zeros((months, 5)),
            sampler=sampler,
            stats=dataset.stats,
            rng=np.random.Generator(np.random.PCG64(5)),
        )
        assert raw.shape == (months, len(FACTOR_SET))
        assert len(conds) == 8
        assert np.all(np.isfinite(raw))


class TestFullJoinery:
    def test_assemble_decades_end_to_end_with_the_diffusion_sampler(
        self, sampler, tmp_path_factory
    ):
        """The complete 7-step assembly (waypoints -> blocks -> Denton -> filter
        -> Ensemble) driven by the diffusion sampler on synthetic artifacts —
        the exact wiring the battery and WP2.10's system D use."""
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        base = tmp_path_factory.mktemp("full-joinery")
        climate = make_climate_artifact(base / "clim", t_months=480, state_noise=0.05)
        regimes = make_regimes_artifact(base / "reg")
        source = make_source(n_rows=240)
        ensemble = assemble_decades(
            climate=climate,
            regimes_artifact=regimes,
            source=source,
            n_decades=2,
            seed=99,
            months=24,
            sampler=sampler,
            config=JoineryConfig(acceptance_filter=False),
        )
        assert ensemble.paths.shape == (2, 24, len(FACTOR_SET))
        assert np.all(np.isfinite(ensemble.paths))
        assert ensemble.meta.conditioning["block_sampler"] == "DiffusionBlockSampler"
        # floors survive reconciliation + the sampler jointly
        for j, name in enumerate(FACTOR_SET):
            if name in RATE_FLOOR_FACTORS:
                assert np.all(ensemble.paths[..., j] >= RATE_FLOOR_PCT)
            if name in SPREAD_FLOOR_FACTORS:
                assert np.all(ensemble.paths[..., j] >= SPREAD_FLOOR_PCT)
        # bit-determinism through the whole joinery
        again = assemble_decades(
            climate=climate,
            regimes_artifact=regimes,
            source=source,
            n_decades=2,
            seed=99,
            months=24,
            sampler=sampler,
            config=JoineryConfig(acceptance_filter=False),
        )
        np.testing.assert_array_equal(ensemble.paths, again.paths)


class TestBatchedSampling:
    """WP2.8b — batching the network evaluation ACROSS decades.

    What is proved exactly here: the width-1 path reproduces the per-block path
    bit for bit, the noise still comes off each decade's own stream in its own
    order, and a fixed width is invariant to batch COMPOSITION (position,
    neighbours, zero padding). What is NOT claimed anywhere — because the
    float32 GEMM underneath is not batch-size invariant — is equality ACROSS
    widths; the last test states the measured bound instead.
    """

    def _conds(self, n, seed=3):
        rng = np.random.Generator(np.random.PCG64(seed))
        return [
            bridge.BlockConditioning(
                regime_onehot=np.eye(6)[i % 6],
                state_snapshot=rng.standard_normal(5),
                history_summary=rng.standard_normal(3),
                waypoint_increments=rng.standard_normal(4),
                start_month=3 * i,
            )
            for i in range(n)
        ]

    def test_block_batch_must_be_positive(self, dataset):
        torch.manual_seed(0)
        model = df.ConditionalDenoiser(SMALL)
        with pytest.raises(JoineryError, match="block_batch"):
            df.DiffusionBlockSampler(
                model,
                dataset.standardization,
                dataset.factor_names,
                trained_fingerprint=bridge.contract_fingerprint(),
                block_batch=0,
            )

    def test_width_1_sample_blocks_equals_the_per_block_path_bit_for_bit(self, sampler):
        conds = self._conds(4)
        seeds = [11, 12, 13, 14]
        batched = sampler.sample_blocks(
            conds, [np.random.Generator(np.random.PCG64(s)) for s in seeds]
        )
        one_by_one = np.stack(
            [
                sampler.sample_block(c, np.random.Generator(np.random.PCG64(s)))
                for c, s in zip(conds, seeds, strict=True)
            ]
        )
        np.testing.assert_array_equal(batched, one_by_one)

    def test_each_decade_draws_from_its_own_stream_in_its_own_order(self, sampler):
        """Batching must not change what any RNG produces, or when. Two blocks
        drawn from ONE stream in sequence must match the same stream driven
        through two successive sample_blocks calls."""
        conds = self._conds(2)
        rng_a = np.random.Generator(np.random.PCG64(99))
        first = sampler.sample_blocks([conds[0]], [rng_a])[0]
        second = sampler.sample_blocks([conds[1]], [rng_a])[0]
        rng_b = np.random.Generator(np.random.PCG64(99))
        np.testing.assert_array_equal(first, sampler.sample_block(conds[0], rng_b))
        np.testing.assert_array_equal(second, sampler.sample_block(conds[1], rng_b))

    def test_a_fixed_width_is_invariant_to_batch_composition(self, dataset):
        """The property the whole design rests on (measured, then pinned): at a
        FIXED batch width a row's output depends only on that row and its ROW
        INDEX — not on its neighbours and not on how much of the batch is zero
        padding.

        STRENGTHENED BY WP2.9. This test used to run on the module fixture,
        whose output head is zero-initialized — a network emitting identically
        zero, for which every composition claim is vacuously true. It now runs on
        a network with weights, which is what turned up the correction recorded
        in :class:`df.TorchBlockSampler`'s docstring: index-preserving
        composition is EXACT, but moving a row to a different index is not (it
        moves by float32 GEMM round-off). The index-preserving property is the
        one ``sample_blocks``' chunking delivers and the one the acceptance
        filter needs; see
        ``test_a_decades_path_is_independent_of_how_many_decades_share_the_run``.
        """
        torch.manual_seed(0)
        model = df.ConditionalDenoiser(SMALL)
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.1)  # a network that actually speaks
        wide = df.DiffusionBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            block_batch=8,
        )
        conds = self._conds(8, seed=17)
        seeds = list(range(50, 58))

        def draw(subset):
            return wide.sample_blocks(
                [conds[i] for i in subset],
                [np.random.Generator(np.random.PCG64(seeds[i])) for i in subset],
            )

        full = draw(range(8))
        # a short batch is zero-padded up to the width: the real rows, at the
        # row indices they already occupied, are bit-for-bit unchanged
        np.testing.assert_array_equal(draw([0, 1, 2]), full[[0, 1, 2]])
        np.testing.assert_array_equal(draw([0]), full[[0]])
        # reordering DOES move the answer, and only by float32 round-off
        moved = draw([7, 0, 3])
        reference = full[[7, 0, 3]]
        assert not np.array_equal(moved, reference)
        assert float(np.abs(moved - reference).max()) < 1e-4

    def test_end_to_end_width_1_reproduces_the_unbatched_driver(self, dataset, tmp_path_factory):
        """The legacy-equivalence anchor: an ensemble assembled through the
        batched driver at width 1 is bit-identical to one assembled by a sampler
        that does not advertise sample_blocks at all (so the bridge falls back to
        the committed per-decade, per-block loop)."""
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        torch.manual_seed(0)
        model = df.ConditionalDenoiser(SMALL)
        batched = df.DiffusionBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            block_batch=1,
        )

        class _Unbatched:  # the WP2.8 interface, exactly: no sample_blocks
            factor_names = batched.factor_names
            block_months = batched.block_months

            def sample_block(self, cond, rng):
                return batched.sample_block(cond, rng)

        legacy = _Unbatched()
        assert not isinstance(legacy, bridge.BatchedBlockSampler)

        base = tmp_path_factory.mktemp("width1")
        climate = make_climate_artifact(base / "clim", t_months=480, state_noise=0.05)
        regimes = make_regimes_artifact(base / "reg")
        source = make_source(n_rows=240)
        kw = dict(
            climate=climate,
            regimes_artifact=regimes,
            source=source,
            n_decades=3,
            seed=4242,
            months=24,
            config=JoineryConfig(acceptance_filter=False),
        )
        a = assemble_decades(sampler=batched, **kw)  # type: ignore[arg-type]
        b = assemble_decades(sampler=legacy, **kw)  # type: ignore[arg-type]
        np.testing.assert_array_equal(a.paths, b.paths)

    def test_cross_width_divergence_is_float32_round_off_not_identity(self, dataset):
        """DELIBERATELY NOT an identity assertion. The float32 GEMM the denoiser
        is built from is not batch-size invariant on any backend measured (CPU
        and CUDA both change a row's output at batch 2 already), so widths cannot
        agree bit for bit. This pins the SIZE of the disagreement — round-off,
        not behaviour — so a regression that actually changes the model shows up.
        """
        torch.manual_seed(0)
        model = df.ConditionalDenoiser(SMALL)
        conds = self._conds(8, seed=23)
        seeds = list(range(70, 78))

        def draw(width):
            s = df.DiffusionBlockSampler(
                model,
                dataset.standardization,
                dataset.factor_names,
                trained_fingerprint=bridge.contract_fingerprint(),
                block_batch=width,
            )
            return s.sample_blocks(conds, [np.random.Generator(np.random.PCG64(k)) for k in seeds])

        narrow, wide = draw(1), draw(8)
        scale = np.maximum(np.abs(narrow), 1e-6)
        assert float(np.max(np.abs(narrow - wide) / scale)) < 1e-3

    def test_the_batch_width_is_recorded_in_the_ensemble_lineage(self, dataset, tmp_path_factory):
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        torch.manual_seed(0)
        model = df.ConditionalDenoiser(SMALL)
        s = df.DiffusionBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            block_batch=4,
        )
        base = tmp_path_factory.mktemp("lineage")
        ens = assemble_decades(
            climate=make_climate_artifact(base / "clim", t_months=480, state_noise=0.05),
            regimes_artifact=make_regimes_artifact(base / "reg"),
            source=make_source(n_rows=240),
            n_decades=2,
            seed=7,
            months=24,
            sampler=s,
            config=JoineryConfig(acceptance_filter=False),
        )
        assert ens.meta.conditioning["block_sampler_batch"] == 4
        assert ens.meta.conditioning["block_sampler_device"] == "cpu"

    def test_a_decades_path_is_independent_of_how_many_decades_share_the_run(
        self, dataset, tmp_path_factory
    ):
        """What the acceptance filter needs: a replacement decade regenerated on
        its own must be the decade the full ensemble would have produced. Padding
        to a fixed width is what preserves that under batching."""
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        torch.manual_seed(0)
        model = df.ConditionalDenoiser(SMALL)
        s = df.DiffusionBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            block_batch=4,
        )
        base = tmp_path_factory.mktemp("nindep")
        kw = dict(
            climate=make_climate_artifact(base / "clim", t_months=480, state_noise=0.05),
            regimes_artifact=make_regimes_artifact(base / "reg"),
            source=make_source(n_rows=240),
            seed=31337,
            months=24,
            sampler=s,
            config=JoineryConfig(acceptance_filter=False),
        )
        few = assemble_decades(n_decades=2, **kw)  # type: ignore[arg-type]
        many = assemble_decades(n_decades=5, **kw)  # type: ignore[arg-type]
        np.testing.assert_array_equal(few.paths, many.paths[:2])


class TestRegistry:
    def test_generator_id_registered_and_factory_guards(self):
        from ah.gen import registry

        assert df.GENERATOR_ID in registry.registered()
        if df.PINNED_CHECKPOINT_SHA256 is None:
            with pytest.raises(JoineryError, match="no pinned checkpoint"):
                registry.resolve(df.GENERATOR_ID)

    def test_primary_checkpoint_matches_its_pin(self):
        """The committed pin must name the checkpoint on disk (when present:
        experiments/ is the gitignored local-first store, so a fresh checkout
        skips). Guards the lineage claim every ensemble makes."""
        if df.PINNED_CHECKPOINT_SHA256 is None or not df.DEFAULT_CHECKPOINT.exists():
            pytest.skip("no primary checkpoint present (pre-training checkout)")
        from ah.gen.blocks.train import state_dict_sha256

        model, std, meta = df.load_checkpoint(df.DEFAULT_CHECKPOINT)
        assert meta["checkpoint_hash"] == df.PINNED_CHECKPOINT_SHA256
        assert state_dict_sha256(model.state_dict()) == df.PINNED_CHECKPOINT_SHA256
        # the trained contract must be the runtime's frozen cb-v1 contract
        assert meta["cb_fingerprint"] == bridge.contract_fingerprint()
        # ...and the L1/L2 lineage the WP2.7 joinery pins
        from ah.gen.joinery.assemble import PINNED_CLIMATE_SHA256, PINNED_REGIMES_SHA256

        assert meta["climate_sha256"] == PINNED_CLIMATE_SHA256
        assert meta["regimes_sha256"] == PINNED_REGIMES_SHA256
        assert meta["selection_lambda"] == 1.0
        # The G2-promoted checkpoint is a TWELVE-factor artifact and remains the
        # generator of record for G2's claims (AM-2026-08-02-009); campaign-2's
        # fifteen-factor set applies to campaign-2 checkpoints, not this pin. The
        # geometry asserted is the checkpoint's OWN recorded factor list.
        assert std.x_mean.shape == (len(meta["factor_names"]),)
        assert list(meta["factor_names"]) == [
            "cpi", "equity_mkt", "equity_vol", "funding_spread", "hml", "hqm_curve",
            "ig_spread", "mom", "policy_rate", "smb", "ust_10y", "ust_2y",
        ]
