"""WP2.9 flow tests — rectified-flow identities, CFG, determinism, the protocol.

The 3b variant must be behind the IDENTICAL interface as 3a, so most of these
tests are the WP2.8 diffusion tests re-pointed at the flow sampler: if a
property held for one sampler and not the other, "one entry point" would be a
claim rather than a fact.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ah.gen.blocks import constraints as ct
from ah.gen.blocks import data as bd
from ah.gen.blocks import diffusion as df
from ah.gen.blocks import flow as fl
from ah.gen.blocks import losses as ls
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

SMALL = fl.FlowConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=4)
SMALL_CFG = fl.FlowConfig(
    d_model=32, n_layers=1, n_heads=2, eval_nfe=4, cond_dropout=0.2, guidance_scale=2.0
)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    source = make_source(n_rows=240)
    climate = make_climate_artifact(
        tmp_path_factory.mktemp("clim-flow"), t_months=480, state_noise=0.05
    )
    return bd.build_dataset(source, climate, validation_start_date="2005-01-01")


@pytest.fixture(scope="module")
def sampler(dataset):
    torch.manual_seed(0)
    model = SMALL.build_model()
    return fl.FlowBlockSampler(
        model,
        dataset.standardization,
        dataset.factor_names,
        trained_fingerprint=bridge.contract_fingerprint(),
    )


class TestConfig:
    def test_guidance_without_dropout_is_normalized_away(self):
        """A null branch that was never trained must not be sampled from: with
        cond_dropout 0 the guidance scale collapses to 1.0 BEFORE hashing, so
        the sealed budget is not spent twice on the same model."""
        c = fl.FlowConfig(cond_dropout=0.0, guidance_scale=2.5)
        assert c.guidance_scale == 1.0
        assert c.as_dict()["guidance_scale"] == 1.0

    def test_guidance_with_dropout_survives(self):
        assert fl.FlowConfig(cond_dropout=0.1, guidance_scale=2.5).guidance_scale == 2.5

    def test_sampling_nfe_counts_the_guidance_branch(self):
        """The sealed tie-break reads sampling cost. CFG is two network
        evaluations per step and must be reported as such."""
        assert fl.FlowConfig(eval_nfe=8).sampling_nfe == 8
        assert fl.FlowConfig(eval_nfe=8, cond_dropout=0.1, guidance_scale=2.0).sampling_nfe == 16

    def test_heun_requires_an_even_nfe(self):
        with pytest.raises(JoineryError, match="even"):
            fl.FlowConfig(solver="heun", eval_nfe=5)

    def test_unknown_solver_and_time_distribution_refuse(self):
        with pytest.raises(JoineryError, match="solver"):
            fl.FlowConfig(solver="rk4")
        with pytest.raises(JoineryError, match="time_dist"):
            fl.FlowConfig(time_dist="beta")


class TestIntegrator:
    def test_constant_velocity_is_integrated_exactly_by_both_solvers(self):
        """The rectified-flow straight-line property: a constant field moves the
        sample by exactly v over t in [0, 1], for any step count and either
        solver. This is the identity the whole design rests on."""
        noise = torch.zeros(3, 6, 12)
        cond = torch.zeros(3, bridge.C_B_DIM)

        def velocity(x, t, c):
            return torch.full_like(x, 0.25)

        for solver, nfe in (("euler", 1), ("euler", 7), ("heun", 2), ("heun", 8)):
            cfg = fl.FlowConfig(solver=solver, eval_nfe=nfe)
            out = fl.flow_integrate(velocity, cfg, cond, noise, nfe)
            assert torch.allclose(out, torch.full_like(noise, 0.25), atol=1e-6)

    def test_linear_in_t_velocity_needs_the_second_order_solver(self):
        """Heun is exact for a field linear in t where Euler is not — evidence
        the 'heun' option is a real second-order corrector, not a relabel."""
        noise = torch.zeros(2, 6, 12)
        cond = torch.zeros(2, bridge.C_B_DIM)

        def velocity(x, t, c):
            return t[:, None, None].expand_as(x)  # integral over [0,1] is 0.5

        euler = fl.flow_integrate(
            velocity, fl.FlowConfig(solver="euler", eval_nfe=4), cond, noise, 4
        )
        heun = fl.flow_integrate(velocity, fl.FlowConfig(solver="heun", eval_nfe=4), cond, noise, 4)
        assert abs(float(heun.mean()) - 0.5) < 1e-6
        assert abs(float(euler.mean()) - 0.5) > 1e-3

    def test_nfe_is_exactly_the_network_eval_count(self):
        torch.manual_seed(1)
        model = SMALL.build_model()
        calls = 0
        original = model.net_call

        def counting(x, t, cond):
            nonlocal calls
            calls += 1
            return original(x, t, cond)

        model.net_call = counting  # type: ignore[method-assign]
        noise = torch.randn(2, SMALL.block_months, SMALL.n_factors)
        cond = torch.zeros(2, SMALL.cond_dim)
        model.sample(cond, noise, nfe=6)
        assert calls == 6

    def test_guidance_doubles_the_network_eval_count(self):
        torch.manual_seed(1)
        model = SMALL_CFG.build_model()
        calls = 0
        original = model.net_call

        def counting(x, t, cond):
            nonlocal calls
            calls += 1
            return original(x, t, cond)

        model.net_call = counting  # type: ignore[method-assign]
        noise = torch.randn(2, SMALL_CFG.block_months, SMALL_CFG.n_factors)
        cond = torch.zeros(2, SMALL_CFG.cond_dim)
        model.sample(cond, noise, nfe=6)
        assert calls == 12


class TestModel:
    def test_parameter_count_is_small(self):
        model = fl.FlowConfig().build_model()
        assert sum(p.numel() for p in model.parameters()) < 2_000_000

    def test_zero_init_head_makes_the_sample_the_noise(self):
        """F_theta is zero-initialized, so the learned velocity is identically
        zero at init and the ODE is the identity map."""
        model = SMALL.build_model()
        noise = torch.randn(4, SMALL.block_months, SMALL.n_factors)
        cond = torch.randn(4, SMALL.cond_dim)
        with torch.no_grad():
            out = model.sample(cond, noise, nfe=4)
        assert float((out - noise).abs().max()) == 0.0

    def test_conditioning_conditions(self):
        torch.manual_seed(1)
        model = SMALL.build_model()
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.1)
        x = torch.randn(2, SMALL.block_months, SMALL.n_factors)
        t = torch.full((2,), 0.5)
        with torch.no_grad():
            v1 = model.net_call(x, t, torch.zeros(2, SMALL.cond_dim))
            v2 = model.net_call(x, t, torch.ones(2, SMALL.cond_dim))
        assert float((v1 - v2).abs().max()) > 1e-6

    def test_guidance_extrapolates_away_from_the_unconditional_branch(self):
        """CFG's defining identity: v_g = v_uncond + s*(v_cond - v_uncond), so
        at s=2 the guided step is exactly twice the conditional step's
        displacement from the unconditional one."""
        torch.manual_seed(2)
        model = SMALL_CFG.build_model()
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.1)
            model.null_cond.normal_(0.0, 0.5)
        x = torch.randn(3, SMALL_CFG.block_months, SMALL_CFG.n_factors)
        t = torch.full((3,), 0.3)
        cond = torch.randn(3, SMALL_CFG.cond_dim)
        with torch.no_grad():
            v_c = model.net_call(x, t, cond)
            v_u = model.net_call(x, t, model.null_cond.expand(3, -1))
            v_g = model.guided_velocity(x, t, cond, 2.0)
        assert torch.allclose(v_g, v_u + 2.0 * (v_c - v_u), atol=1e-6)


class TestObjective:
    def test_validation_objective_is_deterministic_and_grid_fixed(self, dataset):
        torch.manual_seed(3)
        model = SMALL.build_model()
        objective = model.make_objective()
        x = torch.as_tensor(dataset.fold_x_standardized(0), dtype=torch.float32)
        cond = torch.as_tensor(dataset.fold_cond_standardized(0), dtype=torch.float32)
        a = objective.validation_objective(x, cond)
        b = objective.validation_objective(x, cond)
        assert a == b
        assert np.isfinite(a)
        assert len(ls.VAL_TIME_GRID) == 8
        assert all(0.0 < t < 1.0 for t in ls.VAL_TIME_GRID)

    def test_zero_init_objective_is_the_target_norm(self, dataset):
        """At init the predicted velocity is 0, so the objective is E||x1-x0||^2
        exactly — a closed form to check the loss against."""
        model = SMALL.build_model()
        objective = model.make_objective()
        x = torch.as_tensor(dataset.fold_x_standardized(0), dtype=torch.float32)
        cond = torch.as_tensor(dataset.fold_cond_standardized(0), dtype=torch.float32)
        gen = torch.Generator().manual_seed(objective.VAL_NOISE_SEED)
        expected = []
        for _t in ls.VAL_TIME_GRID:
            noise = torch.randn(x.shape, generator=gen)
            expected.append(float(((x - noise) ** 2).mean()))
        assert objective.validation_objective(x, cond) == pytest.approx(
            float(np.mean(expected)), rel=1e-6
        )

    def test_training_loss_is_differentiable_and_finite(self, dataset):
        torch.manual_seed(4)
        model = SMALL.build_model()
        objective = model.make_objective()
        x = torch.as_tensor(dataset.train_x_standardized()[:8], dtype=torch.float32)
        cond = torch.as_tensor(dataset.train_cond_standardized()[:8], dtype=torch.float32)
        loss = objective.training_loss(x, cond, torch.Generator().manual_seed(5))
        loss.backward()
        assert torch.isfinite(loss)
        assert any(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())

    def test_conditioning_dropout_trains_the_null_branch(self, dataset):
        """Without dropout the null embedding receives no gradient — which is
        exactly why FlowConfig refuses to guide when cond_dropout is 0."""
        x = torch.as_tensor(dataset.train_x_standardized()[:16], dtype=torch.float32)
        cond = torch.as_tensor(dataset.train_cond_standardized()[:16], dtype=torch.float32)
        for config, expect_grad in ((SMALL_CFG, True), (SMALL, False)):
            torch.manual_seed(6)
            model = config.build_model()
            with torch.no_grad():
                model.out.weight.normal_(0.0, 0.1)
            loss = model.make_objective().training_loss(x, cond, torch.Generator().manual_seed(7))
            loss.backward()
            grad = model.null_cond.grad
            has = grad is not None and float(grad.abs().sum()) > 0.0
            assert has is expect_grad

    def test_logit_normal_time_sampling_stays_inside_the_open_interval(self):
        torch.manual_seed(8)
        config = fl.FlowConfig(d_model=32, n_layers=1, n_heads=2, time_dist="logit_normal")
        model = config.build_model()
        objective = model.make_objective()
        t = objective.draw_time(4096, torch.Generator().manual_seed(9), torch.device("cpu"))
        assert float(t.min()) > 0.0 and float(t.max()) < 1.0
        assert 0.4 < float(t.mean()) < 0.6  # symmetric at logit mean 0


class TestSampler:
    def test_sampling_is_deterministic_given_the_numpy_rng(self, sampler):
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
        assert isinstance(sampler, bridge.BatchedBlockSampler)
        assert isinstance(sampler, df.TorchBlockSampler)  # shared machinery, not a fork
        assert sampler.block_months == SMALL.block_months
        assert sampler.factor_names == FACTOR_SET

    def test_contract_fingerprint_mismatch_refuses_loudly(self, dataset):
        with pytest.raises(JoineryError, match="contract mismatch"):
            fl.FlowBlockSampler(
                SMALL.build_model(),
                dataset.standardization,
                dataset.factor_names,
                trained_fingerprint="not-the-contract",
            )

    def test_guidance_scale_is_overridable_for_the_ablation(self, dataset):
        """The bake-off must report WITH and WITHOUT guidance from one
        checkpoint, so the scale is a sampler-construction knob."""
        torch.manual_seed(0)
        model = SMALL_CFG.build_model()
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.1)
            model.null_cond.normal_(0.0, 0.5)
        kw = dict(
            standardization=dataset.standardization,
            factor_names=dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
        )
        guided = fl.FlowBlockSampler(model, **kw)  # type: ignore[arg-type]
        plain = fl.FlowBlockSampler(model, guidance_scale=1.0, **kw)  # type: ignore[arg-type]
        assert guided.guidance_scale == 2.0
        assert guided.nfe_per_block == 2 * plain.nfe_per_block
        rng = np.random.Generator(np.random.PCG64(1))
        conds = rng.standard_normal((4, bridge.C_B_DIM))
        noise = rng.standard_normal((4, SMALL_CFG.block_months, len(FACTOR_SET)))
        assert not np.array_equal(
            guided.sample_batch(conds, noise), plain.sample_batch(conds, noise)
        )

    def test_drives_the_joinery_bridge_end_to_end(self, sampler, dataset):
        from ah.gen.joinery import waypoints as wp

        months = 24
        waypoints = wp.DecadeWaypoints(
            policy_pct=np.full(2, 3.0),
            inflation_pct=np.full(2, 2.5),
            equity_log_drift=np.full(2, 0.06),
            spread_center_pct=np.full(2, 1.0),
            spread_lo_pct=np.full(2, 0.8),
            spread_hi_pct=np.full(2, 1.2),
            labels=np.zeros(months, dtype=np.int64),
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


class TestBatchedSampling:
    """The seven WP2.8b requirements, re-proved for the flow sampler."""

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

    def _sampler(self, dataset, width, config=SMALL):
        torch.manual_seed(0)
        model = config.build_model()
        with torch.no_grad():  # give the zero-init head something to say
            model.out.weight.normal_(0.0, 0.1)
        return fl.FlowBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            block_batch=width,
        )

    def test_width_1_sample_blocks_equals_the_per_block_path_bit_for_bit(self, dataset):
        s = self._sampler(dataset, 1)
        conds = self._conds(4)
        seeds = [11, 12, 13, 14]
        batched = s.sample_blocks(conds, [np.random.Generator(np.random.PCG64(k)) for k in seeds])
        one_by_one = np.stack(
            [
                s.sample_block(c, np.random.Generator(np.random.PCG64(k)))
                for c, k in zip(conds, seeds, strict=True)
            ]
        )
        np.testing.assert_array_equal(batched, one_by_one)

    def test_each_decade_draws_from_its_own_stream_in_its_own_order(self, dataset):
        s = self._sampler(dataset, 1)
        conds = self._conds(2)
        rng_a = np.random.Generator(np.random.PCG64(99))
        first = s.sample_blocks([conds[0]], [rng_a])[0]
        second = s.sample_blocks([conds[1]], [rng_a])[0]
        rng_b = np.random.Generator(np.random.PCG64(99))
        np.testing.assert_array_equal(first, s.sample_block(conds[0], rng_b))
        np.testing.assert_array_equal(second, s.sample_block(conds[1], rng_b))

    def test_a_fixed_width_is_invariant_to_batch_composition(self, dataset):
        """Row independence VERIFIED, not assumed (WP2.8b requirement (iii)),
        and verified on a network with weights rather than a zero map.

        What holds EXACTLY: at a fixed width, a row kept at its own row index is
        untouched by its neighbours or by zero padding. What does NOT hold, and
        is asserted as round-off rather than equality: moving a row to a
        different index. Chunking maps decade m to index m % width in every run,
        so the exact property is the one the design uses. Same measured
        behaviour as the 3a sampler — this is a property of the shared backbone
        and the float32 GEMM under it, not of either objective.
        """
        wide = self._sampler(dataset, 8)
        conds = self._conds(8, seed=17)
        seeds = list(range(50, 58))

        def draw(subset):
            return wide.sample_blocks(
                [conds[i] for i in subset],
                [np.random.Generator(np.random.PCG64(seeds[i])) for i in subset],
            )

        full = draw(range(8))
        np.testing.assert_array_equal(draw([0, 1, 2]), full[[0, 1, 2]])
        np.testing.assert_array_equal(draw([0]), full[[0]])
        moved = draw([7, 0, 3])
        assert not np.array_equal(moved, full[[7, 0, 3]])
        assert float(np.abs(moved - full[[7, 0, 3]]).max()) < 1e-4

    def test_a_row_at_its_own_index_is_untouched_by_every_other_row(self, dataset):
        """The exact form of the property, isolated: zero out every other row of
        the batch and the surviving row reproduces the full batch bit for bit."""
        wide = self._sampler(dataset, 4)
        conds = self._conds(4, seed=29)
        seeds = [80, 81, 82, 83]

        def rngs(subset):
            return [np.random.Generator(np.random.PCG64(seeds[i])) for i in subset]

        full = wide.sample_blocks(conds, rngs(range(4)))
        for i in range(4):
            # index-preserving isolation: prefix of length i+1, tail zero-padded,
            # so row i keeps index i while rows i+1.. are replaced by zeros
            got = wide.sample_blocks(conds[: i + 1], rngs(range(i + 1)))
            np.testing.assert_array_equal(got[i], full[i])

    def test_composition_invariance_holds_under_guidance_too(self, dataset):
        wide = self._sampler(dataset, 8, config=SMALL_CFG)
        conds = self._conds(8, seed=19)
        seeds = list(range(60, 68))

        def draw(subset):
            return wide.sample_blocks(
                [conds[i] for i in subset],
                [np.random.Generator(np.random.PCG64(seeds[i])) for i in subset],
            )

        full = draw(range(8))
        np.testing.assert_array_equal(draw([2]), full[[2]])

    def test_end_to_end_width_1_reproduces_the_unbatched_driver(self, dataset, tmp_path_factory):
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        batched = self._sampler(dataset, 1)

        class _Unbatched:
            factor_names = batched.factor_names
            block_months = batched.block_months

            def sample_block(self, cond, rng):
                return batched.sample_block(cond, rng)

        legacy = _Unbatched()
        assert not isinstance(legacy, bridge.BatchedBlockSampler)

        base = tmp_path_factory.mktemp("flow-width1")
        kw = dict(
            climate=make_climate_artifact(base / "clim", t_months=480, state_noise=0.05),
            regimes_artifact=make_regimes_artifact(base / "reg"),
            source=make_source(n_rows=240),
            n_decades=3,
            seed=4242,
            months=24,
            config=JoineryConfig(acceptance_filter=False),
        )
        a = assemble_decades(sampler=batched, **kw)  # type: ignore[arg-type]
        b = assemble_decades(sampler=legacy, **kw)  # type: ignore[arg-type]
        np.testing.assert_array_equal(a.paths, b.paths)

    def test_cross_width_divergence_is_float32_round_off_not_identity(self, dataset):
        conds = self._conds(8, seed=23)
        seeds = list(range(70, 78))

        def draw(width):
            s = self._sampler(dataset, width)
            return s.sample_blocks(conds, [np.random.Generator(np.random.PCG64(k)) for k in seeds])

        narrow, wide = draw(1), draw(8)
        scale = np.maximum(np.abs(narrow), 1e-6)
        assert float(np.max(np.abs(narrow - wide) / scale)) < 1e-3

    def test_a_decades_path_is_independent_of_how_many_decades_share_the_run(
        self, dataset, tmp_path_factory
    ):
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        s = self._sampler(dataset, 4)
        base = tmp_path_factory.mktemp("flow-nindep")
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

    def test_the_batch_width_and_device_are_recorded_in_the_lineage(
        self, dataset, tmp_path_factory
    ):
        from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        s = self._sampler(dataset, 4)
        base = tmp_path_factory.mktemp("flow-lineage")
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
        assert ens.meta.conditioning["block_sampler"] == "FlowBlockSampler"


class TestSharedStack:
    """§WP2.9's 'sharing data/constraints/losses/training/tuning' — as tests."""

    def test_the_trainer_is_the_same_function(self, dataset):
        from ah.gen.blocks import train as tr

        tiny = fl.FlowConfig(
            d_model=32,
            n_layers=1,
            n_heads=2,
            batch_size=16,
            eval_nfe=4,
            aux_nfe=2,
            lambda_tail=0.1,
            aux_every=2,
            lr=1e-3,
        )
        result = tr.train_blocks(
            dataset,
            tiny,
            seed=11,
            max_steps=20,
            eval_every=10,
            patience=5,
            device="cpu",
            n_rep_eval=1,
        )
        assert result.steps_run == 20
        assert np.isfinite(result.best_s)
        assert result.config_hash.startswith("cfg:")
        expected = float(np.mean(result.per_fold_gen)) + tr.SELECTION_LAMBDA * float(
            np.mean(result.per_fold_aux)
        )
        assert result.best_s == pytest.approx(expected, rel=1e-12)
        again = tr.train_blocks(
            dataset,
            tiny,
            seed=11,
            max_steps=20,
            eval_every=10,
            patience=5,
            device="cpu",
            n_rep_eval=1,
        )
        assert again.checkpoint_hash == result.checkpoint_hash

    def test_the_checkpoint_records_which_generative_objective_was_used(self, dataset, tmp_path):
        from ah.gen.blocks import train as tr

        tiny = fl.FlowConfig(
            d_model=32, n_layers=1, n_heads=2, batch_size=16, eval_nfe=4, lambda_tail=0.0
        )
        result = tr.train_blocks(
            dataset, tiny, seed=1, max_steps=4, eval_every=4, patience=2, device="cpu", n_rep_eval=1
        )
        meta = tr.save_checkpoint(result, dataset, tmp_path / "flow.pt")
        assert "velocity" in meta["generative_objective"]
        assert meta["cb_fingerprint"] == bridge.contract_fingerprint()
        model, std, meta2 = fl.load_checkpoint(tmp_path / "flow.pt")
        assert meta2["checkpoint_hash"] == result.checkpoint_hash
        assert isinstance(model.config, fl.FlowConfig)
        np.testing.assert_array_equal(std.x_mean, dataset.standardization.x_mean)

    def test_the_tuning_protocol_is_the_same_module(self, tmp_path, dataset):
        from ah.gen.blocks import tuning as tu

        configs = [
            fl.FlowConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=4, lambda_tail=0.0),
            fl.FlowConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=4, lambda_tail=0.1),
        ]
        entries = tu.run_search(
            dataset,
            configs,
            exp_dir=tmp_path,
            seed=3,
            trial_max_steps=4,
            trial_eval_every=4,
            trial_patience=5,
            device="cpu",
            n_rep_eval=1,
            space_sha256="deadbeef",
        )
        assert [e["event"] for e in entries].count("trial_completed") == 2
        sel = tu.select_config(entries, n_folds=3)
        assert sel["selection_lambda"] == 1.0
        assert "gen_term" in sel and "aux_term" in sel

    def test_the_committed_flow_search_space_loads_against_flow_config(self):
        from pathlib import Path

        from ah.gen.blocks import tuning as tu

        root = Path(__file__).resolve().parents[1]
        space, budget, sha = tu.load_search_space(
            root / "configs" / "wp29-flow-search-v1.yaml", fl.FlowConfig
        )
        assert len(sha) == 64
        assert budget["n_trials"] <= tu.TRIAL_BUDGET
        for key in ("cond_noise_std", "cond_dropout", "guidance_scale", "d_model", "eval_nfe"):
            assert key in space, key
        # the attenuation finding: an unjittered, undropped arm must be reachable
        assert 0.0 in space["cond_noise_std"] and 0.0 in space["cond_dropout"]
        from ah.experiment import config_hash

        configs = tu.sample_trial_configs(space, 12, seed=5, config_cls=fl.FlowConfig)
        assert len({config_hash(c.as_dict()) for c in configs}) == 12


class TestRegistry:
    def test_generator_id_registered_and_factory_guards(self):
        from ah.gen import registry

        assert fl.GENERATOR_ID in registry.registered()
        if fl.PINNED_CHECKPOINT_SHA256 is None:
            with pytest.raises(JoineryError, match="no pinned checkpoint"):
                registry.resolve(fl.GENERATOR_ID)

    def test_both_samplers_are_reachable_through_the_one_entry_point(self):
        """§WP2.9 acceptance, as a test: the registry resolves both arms of
        ablation system D by id, and both are the same system class."""
        from ah.gen import registry

        assert {df.GENERATOR_ID, fl.GENERATOR_ID} <= set(registry.registered())
        assert issubclass(fl.HierFlowV1, df.HierBlockSystem)
        assert issubclass(df.HierDiffusionV1, df.HierBlockSystem)

    def test_primary_checkpoint_matches_its_pin(self):
        if fl.PINNED_CHECKPOINT_SHA256 is None or not fl.DEFAULT_CHECKPOINT.exists():
            pytest.skip("no primary flow checkpoint present (pre-training checkout)")
        from ah.gen.blocks.train import state_dict_sha256
        from ah.gen.joinery.assemble import PINNED_CLIMATE_SHA256, PINNED_REGIMES_SHA256

        model, std, meta = fl.load_checkpoint(fl.DEFAULT_CHECKPOINT)
        assert meta["checkpoint_hash"] == fl.PINNED_CHECKPOINT_SHA256
        assert state_dict_sha256(model.state_dict()) == fl.PINNED_CHECKPOINT_SHA256
        assert meta["cb_fingerprint"] == bridge.contract_fingerprint()
        assert meta["climate_sha256"] == PINNED_CLIMATE_SHA256
        assert meta["regimes_sha256"] == PINNED_REGIMES_SHA256
        assert meta["selection_lambda"] == 1.0
        # CAMPAIGN-2 PROMOTION: the primary pin is now the campaign-2 seed-0
        # artifact, trained on the sealed FIFTEEN-factor set. The geometry
        # asserted is the checkpoint's OWN recorded factor list, which for this
        # pin equals the sealed bootstrap_v1.factor_set.
        assert std.x_mean.shape == (len(meta["factor_names"]),)
        assert tuple(meta["factor_names"]) == FACTOR_SET


class TestGuidanceHookPlumbing:
    """§WP2.9's optional joinery guidance hook: PLUMBED, DEFAULTED OFF, RECORDED.

    The decision not to activate it is in flow.py's module docstring and in
    progress.md; what is tested here is that the plumbing exists and that a run
    always says which hook (if any) produced it, so a guided run can never be
    mistaken for an unguided one.
    """

    def _system(self, dataset, tmp_path_factory, guidance):
        from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

        torch.manual_seed(0)
        model = SMALL.build_model()
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.1)
        sampler = fl.FlowBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
        )
        base = tmp_path_factory.mktemp("guide")
        from ah.gen.joinery.assemble import JoineryConfig

        system = fl.HierFlowV1(
            make_climate_artifact(base / "clim", t_months=480, state_noise=0.05),
            make_regimes_artifact(base / "reg"),
            make_source(n_rows=240),
            sampler,
            JoineryConfig(acceptance_filter=False),
            guidance=guidance,
        )
        return system

    def test_default_is_no_hook_and_the_lineage_says_so(self, dataset, tmp_path_factory):
        system = self._system(dataset, tmp_path_factory, None)
        ens = system.sample_months(24, 2, 7)
        assert ens.meta.conditioning["joinery_guidance_hook"] is None
        assert ens.meta.generator_id == fl.GENERATOR_ID

    def test_a_hook_is_applied_and_named_in_the_lineage(self, dataset, tmp_path_factory):
        class _Nudge:
            """A trivial hook: proof the wiring reaches every sampled block."""

            def adjust(self, block, cond):
                out = np.array(block, dtype=np.float64, copy=True)
                out[:, 0] *= 1.01
                return out

        plain = self._system(dataset, tmp_path_factory, None).sample_months(24, 2, 7)
        guided = self._system(dataset, tmp_path_factory, _Nudge()).sample_months(24, 2, 7)
        assert guided.meta.conditioning["joinery_guidance_hook"] == "_Nudge"
        assert not np.array_equal(plain.paths, guided.paths)

    def test_the_frozen_hook_signature_cannot_see_a_waypoint_LEVEL(self):
        """The recorded finding behind the deferral: `GuidanceHook.adjust` is
        given the block and c_b only, and every c_b waypoint component is an
        INCREMENT (the ig-spread diagnosis' H6). So the hook can express a
        chaining-style correction from `h_spread_level_pct`, but it cannot aim
        at a band CENTRE — no level target is reachable through the contract."""
        increments = [n for n in bridge.C_B_COMPONENTS if n.startswith("dw_")]
        assert increments == [
            "dw_policy_rate_pct",
            "dw_log_cpi",
            "dw_equity_cum_log",
            "dw_spread_center_pct",
        ]
        levels = [n for n in bridge.C_B_COMPONENTS if n.startswith("w_")]
        assert levels == []


class TestRealFlowTuningLog:
    """The sealed 'tuning log complete and within budget' acceptance, MACHINE-
    CHECKED against the actual WP2.9 campaign search record — the same check
    ``tests/test_blocks_tuning.py`` applies to WP2.8's, over the 3b log.

    The experiment store is local-first (gitignored), so the log is validated
    from whichever copy is present; skip only when neither exists."""

    def _log_path(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for p in (
            root / "experiments" / "l3b-flow-tuning-v1" / "tuning-log.jsonl",
            root / "artifacts" / "wp29" / "tuning-log.jsonl",
        ):
            if p.exists():
                return p
        return None

    def test_flow_tuning_log_is_complete_and_within_its_own_budget(self):
        from ah.gen.blocks import train as tr
        from ah.gen.blocks import tuning as tu

        path = self._log_path()
        if path is None:
            pytest.skip("no WP2.9 tuning log present (pre-search checkout)")
        entries = tu.read_log(path)
        header = entries[0]
        assert header["event"] == "search_header"
        assert header["selection_lambda"] == tr.SELECTION_LAMBDA == 1.0
        assert len(header["search_space_sha256"]) == 64
        n_folds = int(header["n_folds"])
        tu.validate_log(entries, n_folds=n_folds)
        # PER SAMPLER: this log spends its own budget, not WP2.8's leftovers.
        assert len(tu.distinct_started_hashes(entries)) <= tu.TRIAL_BUDGET
        recorded = [e for e in entries if e.get("event") == "selected"]
        if recorded:
            sel = tu.select_config(entries, n_folds=n_folds)
            assert recorded[-1]["config_hash"] == sel["config_hash"]
            assert recorded[-1]["s_value"] == pytest.approx(sel["s_value"])
            assert recorded[-1]["gen_term"] == pytest.approx(sel["gen_term"])
            assert recorded[-1]["aux_term"] == pytest.approx(sel["aux_term"])

    def test_every_trial_logged_the_true_nfe_not_the_requested_one(self):
        """The sealed tie-break reads sampling cost. A guided trial costs two
        network evaluations per step, and the log must say so."""
        from ah.gen.blocks import tuning as tu
        from ah.gen.blocks.flow import FlowConfig

        path = self._log_path()
        if path is None:
            pytest.skip("no WP2.9 tuning log present (pre-search checkout)")
        entries = tu.read_log(path)
        started = {
            e["config_hash"]: e["config"] for e in entries if e.get("event") == "trial_started"
        }
        checked = 0
        for e in entries:
            if e.get("event") != "trial_completed":
                continue
            config = FlowConfig(**started[e["config_hash"]])
            assert e["eval_nfe"] == config.sampling_nfe
            assert e["requested_nfe"] == config.eval_nfe
            checked += 1
        assert checked > 0

    def test_the_search_space_file_is_the_one_the_log_records(self):
        import hashlib
        from pathlib import Path

        from ah.gen.blocks import tuning as tu

        path = self._log_path()
        if path is None:
            pytest.skip("no WP2.9 tuning log present (pre-search checkout)")
        root = Path(__file__).resolve().parents[1]
        space = root / "configs" / "wp29-flow-search-v1.yaml"
        recorded = tu.read_log(path)[0]["search_space_sha256"]
        assert hashlib.sha256(space.read_bytes()).hexdigest() == recorded
