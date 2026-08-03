"""A' residual parameterization (campaign-2) — the train/sample symmetry contract.

The network models deviations around the conditioning-implied drift means
(``bridge.conditioning_drift_means``); the dataset subtracts them, the sampler
adds them back from the same raw c_b vector, and every unit conversion restores
them so the sealed tail auxiliary keeps scoring actual factor units.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ah.gen.blocks import constraints as ct
from ah.gen.blocks import data as bd
from ah.gen.blocks import diffusion as bdiff
from ah.gen.blocks import flow as bflow
from ah.gen.blocks import train as tr
from ah.gen.joinery import bridge
from joinery_common import make_climate_artifact, make_source

VAL_DATE = "2005-01-01"


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(
        tmp_path_factory.mktemp("clim"), start="1988-01-01", t_months=480, state_noise=0.05
    )


@pytest.fixture(scope="module")
def source():
    return make_source(n_rows=240)


@pytest.fixture(scope="module")
def plain(source, climate):
    return bd.build_dataset(source, climate, validation_start_date=VAL_DATE)


@pytest.fixture(scope="module")
def resid(source, climate):
    return bd.build_dataset(source, climate, validation_start_date=VAL_DATE, residual_drift=True)


class TestDriftMeans:
    def test_cpi_ramp_and_equity_constant(self):
        cond = np.zeros((2, bridge.C_B_DIM))
        i_cpi = bridge.C_B_COMPONENTS.index("dw_log_cpi")
        i_eq = bridge.C_B_COMPONENTS.index("dw_equity_cum_log")
        cond[0, i_cpi] = 0.06
        cond[0, i_eq] = 0.12
        names = ("cpi", "equity_mkt", "ust_10y")
        m = bridge.conditioning_drift_means(cond, names, 6)
        assert m.shape == (2, 6, 3)
        np.testing.assert_allclose(m[0, :, 0], 0.06 * np.arange(6) / 6.0)
        np.testing.assert_allclose(m[0, :, 1], np.full(6, 0.12 / 6.0))
        assert np.all(m[0, :, 2] == 0.0)  # non-drift factor untouched
        assert np.all(m[1] == 0.0)  # zero dw -> zero mean (bind_waypoints-off path)

    def test_level_factors_never_get_a_mean(self):
        cond = np.ones((1, bridge.C_B_DIM))  # every component nonzero
        m = bridge.conditioning_drift_means(cond, ("policy_rate", "ig_spread"), 6)
        assert np.all(m == 0.0)

    def test_bad_shape_refused(self):
        with pytest.raises(Exception, match="cond_vectors"):
            bridge.conditioning_drift_means(np.zeros((3, 5)), ("cpi",), 6)


class TestDatasetResidual:
    def test_x_plus_mean_reconstructs_direct_targets(self, plain, resid):
        assert resid.residual_drift and resid.drift_mean is not None
        np.testing.assert_allclose(resid.x + resid.drift_mean, plain.x, atol=1e-12)

    def test_drift_mean_matches_cond_rows(self, resid):
        expected = bridge.conditioning_drift_means(
            resid.cond, resid.factor_names, resid.block_months
        )
        np.testing.assert_allclose(resid.drift_mean, expected)

    def test_standardization_describes_residuals(self, plain, resid):
        cpi = list(resid.factor_names).index("cpi")
        train_resid = resid.x[resid.train_index]
        np.testing.assert_allclose(
            resid.standardization.x_mean, train_resid.mean(axis=(0, 1)), atol=1e-12
        )
        # and it genuinely moved for the drift factors (the panel trends)
        assert resid.standardization.x_mean[cpi] != plain.standardization.x_mean[cpi]

    def test_fold_units_identical_to_direct_parameterization(self, plain, resid):
        """The sealed auxiliary's real side must not move with the parameterization."""
        for k in range(len(plain.fold_indices)):
            np.testing.assert_allclose(resid.fold_x_units(k), plain.fold_x_units(k), atol=1e-12)

    def test_off_by_default(self, plain):
        assert plain.residual_drift is False and plain.drift_mean is None


class _ZeroIntegrateSampler(bdiff.TorchBlockSampler):
    def _integrate(self, cond: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
        return torch.zeros_like(noise)


def _sampler_for(config, resid):
    model = config.build_model()
    return _ZeroIntegrateSampler(
        model,
        resid.standardization,
        resid.factor_names,
        trained_fingerprint=bridge.contract_fingerprint(),
    )


class TestSamplerAddBack:
    def test_sample_batch_restores_drift(self, resid):
        config = bflow.FlowConfig(
            d_model=16, n_layers=1, n_heads=2, residual_drift=True, n_factors=15
        )
        sampler = _sampler_for(config, resid)
        cond = resid.cond[:3]
        noise = np.zeros((3, resid.block_months, 15))
        out = sampler.sample_batch(cond, noise)
        m = bridge.conditioning_drift_means(cond, resid.factor_names, resid.block_months)
        base = resid.standardization.destandardize_x(np.zeros_like(noise))
        expected = ct.panel_to_constrained(base + m, resid.factor_names)
        np.testing.assert_allclose(out, expected, atol=1e-12)

    def test_flag_off_means_no_add_back(self, resid):
        config = bflow.FlowConfig(d_model=16, n_layers=1, n_heads=2, n_factors=15)
        sampler = _sampler_for(config, resid)
        cond = resid.cond[:3]
        noise = np.zeros((3, resid.block_months, 15))
        out = sampler.sample_batch(cond, noise)
        base = resid.standardization.destandardize_x(np.zeros_like(noise))
        np.testing.assert_allclose(
            out, ct.panel_to_constrained(base, resid.factor_names), atol=1e-12
        )


class TestConfigHashStability:
    def test_default_as_dict_omits_the_field(self):
        assert "residual_drift" not in bflow.FlowConfig().as_dict()
        assert "residual_drift" not in bdiff.DiffusionConfig().as_dict()

    def test_enabled_as_dict_carries_the_field(self):
        assert bflow.FlowConfig(residual_drift=True).as_dict()["residual_drift"] is True
        assert bdiff.DiffusionConfig(residual_drift=True).as_dict()["residual_drift"] is True

    def test_checkpoint_config_round_trips(self):
        config = bflow.FlowConfig(residual_drift=True)
        assert bflow.FlowConfig(**config.as_dict()) == config


class TestTrainGuard:
    def test_mismatched_flags_refused(self, resid):
        config = bflow.FlowConfig(d_model=16, n_layers=1, n_heads=2, n_factors=15)
        with pytest.raises(Exception, match="residual_drift"):
            tr.train_blocks(resid, config, seed=1, max_steps=1, eval_every=1, patience=1)
