"""WP2.9 bake-off harness tests — one entry point, honest reporting.

Smoke-sized and CPU-only: the harness is exercised on tiny untrained models over
the synthetic joinery fixtures, because what is under test is the harness (does
it reach both families, does it count NFE honestly, does it refuse to present a
cross-sampler S ranking), not either model's quality.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ah.gen.blocks import bakeoff as bo
from ah.gen.blocks import data as bd
from ah.gen.blocks import diffusion as df
from ah.gen.blocks import flow as fl
from ah.gen.blocks import train as tr
from ah.gen.joinery import bridge
from joinery_common import make_climate_artifact, make_source

DIFF = df.DiffusionConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=5, lambda_tail=0.0)
FLOW = fl.FlowConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=4, lambda_tail=0.0)
FLOW_CFG = fl.FlowConfig(
    d_model=32,
    n_layers=1,
    n_heads=2,
    eval_nfe=4,
    lambda_tail=0.0,
    cond_dropout=0.2,
    guidance_scale=2.0,
)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    source = make_source(n_rows=240)
    climate = make_climate_artifact(
        tmp_path_factory.mktemp("clim-bake"), t_months=480, state_noise=0.05
    )
    return bd.build_dataset(source, climate, validation_start_date="2005-01-01")


@pytest.fixture(scope="module")
def checkpoints(dataset, tmp_path_factory):
    """A real (tiny) checkpoint per family, written through the SHARED saver."""
    out = tmp_path_factory.mktemp("ckpts")
    paths = {}
    for arm, config in (("hier-diffusion-v1", DIFF), ("hier-flow-v1", FLOW_CFG)):
        result = tr.train_blocks(
            dataset,
            config,
            seed=5,
            max_steps=4,
            eval_every=4,
            patience=2,
            device="cpu",
            n_rep_eval=1,
        )
        path = out / f"{arm}.pt"
        tr.save_checkpoint(result, dataset, path)
        paths[arm] = path
    return paths


class TestOneEntryPoint:
    def test_build_sampler_reaches_both_families(self, checkpoints, dataset):
        for arm in bo.ARM_IDS:
            sampler, meta = bo.build_sampler(
                arm, checkpoints[arm], factor_names=dataset.factor_names
            )
            assert isinstance(sampler, df.TorchBlockSampler)
            assert isinstance(sampler, bridge.BatchedBlockSampler)
            assert meta["cb_fingerprint"] == bridge.contract_fingerprint()

    def test_unknown_arm_errors_clearly(self):
        with pytest.raises(ValueError, match="unknown bake-off arm"):
            bo.build_sampler("hier-vae-v9")

    def test_arm_ids_are_exactly_the_registered_system_d_arms(self):
        from ah.gen import registry

        assert set(bo.ARM_IDS) <= set(registry.registered())
        assert set(bo.ARM_IDS) == {df.GENERATOR_ID, fl.GENERATOR_ID}


class TestSamplingCost:
    def _sampler(self, dataset, config, **kw):
        torch.manual_seed(0)
        return (
            fl.FlowBlockSampler if isinstance(config, fl.FlowConfig) else df.DiffusionBlockSampler
        )(
            config.build_model(),
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            **kw,
        )

    def test_cost_records_the_declared_width_and_device(self, dataset):
        s = self._sampler(dataset, FLOW, block_batch=8)
        cost = bo.measure_sampling_cost(s, arm="hier-flow-v1", n_blocks=16, warmup_blocks=4)
        assert cost.block_batch == 8
        assert cost.device == "cpu"
        assert cost.n_blocks_measured == 16
        assert cost.wall_seconds > 0
        assert cost.seconds_per_10k_decades == pytest.approx(
            10_000 * bo.blocks_per_decade() / cost.blocks_per_second
        )

    def test_nfe_per_block_is_the_true_network_eval_count(self, dataset):
        plain = self._sampler(dataset, FLOW, block_batch=4)
        guided = self._sampler(dataset, FLOW_CFG, block_batch=4)
        a = bo.measure_sampling_cost(plain, arm="a", n_blocks=8, warmup_blocks=0)
        b = bo.measure_sampling_cost(guided, arm="b", n_blocks=8, warmup_blocks=0)
        assert a.nfe_per_block == FLOW.eval_nfe
        assert b.nfe_per_block == 2 * FLOW_CFG.eval_nfe  # guidance is two evals per step
        assert b.nfe_per_10k_decades == 2 * a.nfe_per_10k_decades

    def test_a_decade_is_forty_blocks_at_the_joinery_stride(self):
        assert bo.blocks_per_decade(120, 3) == 40
        assert bo.blocks_per_decade() == 40


class TestConditioningResponse:
    def test_measures_every_channel_against_its_historical_slope(self, dataset):
        torch.manual_seed(1)
        model = FLOW.build_model()
        with torch.no_grad():
            model.out.weight.normal_(0.0, 0.05)
        sampler = fl.FlowBlockSampler(
            model,
            dataset.standardization,
            dataset.factor_names,
            trained_fingerprint=bridge.contract_fingerprint(),
            block_batch=32,
        )
        table = bo.conditioning_response(sampler, dataset, n_probe=32, seed=11)
        labels = {c[0] for c in bo.RESPONSE_CHANNELS} | {"regime_onehot"}
        assert set(table["channels"]) == labels
        for name, row in table["channels"].items():
            assert np.isfinite(row["historical_ols"]), name
            assert np.isfinite(row["model_finite_difference"]), name
        assert set(table["regime_sweep_generated_spread"]) == set(table["regime_band_centre"])

    def test_a_conditioning_blind_sampler_measures_a_zero_response(self, dataset):
        """The measurement's own negative control: a sampler that ignores c
        must show ratio ~0, or the table would flatter every model."""

        class _Blind:
            factor_names = dataset.factor_names
            block_months = dataset.block_months

            def sample_batch(self, conds, noise):
                z = np.zeros((conds.shape[0], self.block_months, len(self.factor_names)))
                from ah.gen.blocks import constraints as ct

                return ct.panel_to_constrained(z + noise * 0.01, self.factor_names)

        table = bo.conditioning_response(_Blind(), dataset, n_probe=16, seed=3)
        for name, row in table["channels"].items():
            assert abs(row["model_finite_difference"]) < 1e-9, name


class TestReporting:
    def _rows(self):
        return [
            bo.BakeoffRow(
                arm="hier-diffusion-v1",
                generative_objective="fixed-sigma-grid EDM denoising objective",
                gen_term=0.9379,
                aux_term=-3.2642,
                cost=bo.SamplingCost("hier-diffusion-v1", "cpu", 1, 31, 100, 2.0),
            ),
            bo.BakeoffRow(
                arm="hier-flow-v1",
                generative_objective="fixed-time-grid rectified-flow velocity objective",
                gen_term=1.5,
                aux_term=-3.1,
                guidance_scale=2.0,
                cost=bo.SamplingCost("hier-flow-v1", "cpu", 1, 8, 100, 0.6),
            ),
        ]

    def test_s_is_the_sealed_closed_form_with_the_pinned_lambda(self):
        row = self._rows()[0]
        assert row.selection_lambda == 1.0 == tr.SELECTION_LAMBDA
        assert row.s_value == pytest.approx(0.9379 - 3.2642)

    def test_markdown_states_the_incomparability_and_shows_both_terms(self):
        md = bo.render_markdown(self._rows())
        assert "NOT on one scale" in md
        assert "0.937900" in md and "-3.264200" in md  # both terms, separately
        assert "1.500000" in md and "-3.100000" in md
        # every arm's own objective is named next to its number
        assert "EDM denoising" in md and "velocity objective" in md
        # no ranking language, and no single "winner" column
        assert "winner" not in md.lower()

    def test_markdown_reports_cost_at_a_declared_width_and_device(self):
        md = bo.render_markdown(self._rows())
        assert "hier-flow-v1=1@cpu" in md
        assert "40 blocks at stride 3" in md

    def test_markdown_survives_missing_cost_and_conditioning(self):
        md = bo.render_markdown([bo.BakeoffRow(arm="hier-flow-v1", gen_term=1.0, aux_term=-1.0)])
        assert "n/a" in md
