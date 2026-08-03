"""WP2.8 constraints tests — floors impossible BY CONSTRUCTION, round trips exact."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ah.gen.blocks import constraints as ct
from ah.gen.bootstrap import FACTOR_SET
from ah.gen.joinery.waypoints import (
    RATE_FLOOR_FACTORS,
    RATE_FLOOR_PCT,
    SPREAD_FLOOR_FACTORS,
    SPREAD_FLOOR_PCT,
    JoineryError,
)


class TestCoverage:
    def test_every_sealed_factor_has_a_transform(self):
        for name in FACTOR_SET:
            assert ct.transform_for(name) is not None

    def test_unmapped_factor_is_a_hard_error_not_a_passthrough(self):
        with pytest.raises(JoineryError, match="no declared coordinate transform"):
            ct.transform_for("mystery_factor")

    def test_floors_are_the_sealed_conventions_floors(self):
        for name in RATE_FLOOR_FACTORS:
            tr = ct.transform_for(name)
            assert tr.kind == "softplus_floor"
            assert tr.floor == RATE_FLOOR_PCT == -1.0
        for name in SPREAD_FLOOR_FACTORS:
            tr = ct.transform_for(name)
            assert tr.kind == "softplus_floor"
            # DN-1.1's illustrative 100bp is superseded by the sealed 0.0.
            assert tr.floor == SPREAD_FLOOR_PCT == 0.0


class TestRoundTrip:
    @pytest.mark.parametrize("name", sorted(ct.TRANSFORMS))
    def test_round_trip_bit_tight_float64(self, name):
        tr = ct.transform_for(name)
        rng = np.random.Generator(np.random.PCG64(7))
        if tr.kind == "softplus_floor":
            y = tr.floor + 10.0 ** rng.uniform(-6, 1.6, size=4096)  # floor+1e-6 .. floor+~40
        elif tr.kind == "log":
            y = 10.0 ** rng.uniform(-3, 3, size=4096)
        else:  # log1p
            y = np.expm1(rng.uniform(-3.0, 1.5, size=4096))
        back = tr.to_constrained(tr.to_unconstrained(y))
        np.testing.assert_allclose(back, y, rtol=1e-12, atol=1e-14)

    def test_round_trip_across_softplus_saturation_boundary(self):
        tr = ct.transform_for("policy_rate")
        y = tr.floor + np.array([1e-8, 1e-3, 1.0, 29.999, 30.001, 45.0, 60.0])
        np.testing.assert_allclose(tr.to_constrained(tr.to_unconstrained(y)), y, rtol=1e-12)

    def test_panel_round_trip(self):
        rng = np.random.Generator(np.random.PCG64(11))
        y = np.empty((5, 6, len(FACTOR_SET)))
        for j, name in enumerate(FACTOR_SET):
            tr = ct.transform_for(name)
            if tr.kind == "softplus_floor":
                y[..., j] = tr.floor + rng.uniform(0.05, 8.0, size=(5, 6))
            elif tr.kind == "log":
                y[..., j] = rng.uniform(0.5, 300.0, size=(5, 6))
            else:
                y[..., j] = rng.uniform(-0.4, 0.4, size=(5, 6))
        z = ct.panel_to_unconstrained(y, FACTOR_SET)
        np.testing.assert_allclose(ct.panel_to_constrained(z, FACTOR_SET), y, rtol=1e-12)


class TestFloorsByConstruction:
    """A sampled batch can NEVER violate a floor — arbitrary z, not sampling luck."""

    @pytest.mark.parametrize("name", sorted(ct.TRANSFORMS))
    def test_any_unconstrained_value_maps_inside_the_constraint(self, name):
        tr = ct.transform_for(name)
        z = np.array([-1e6, -1e3, -50.0, -1.0, 0.0, 1.0, 50.0, 700.0])
        y = tr.to_constrained(z)
        assert np.all(np.isfinite(y[z < 690]))  # exp overflow only at absurd z, and only log-kind
        if tr.kind == "softplus_floor":
            # The sealed floor_violations estimator counts value < floor strictly;
            # softplus >= 0 makes that impossible for every real z.
            assert np.all(y >= tr.floor)
            assert np.all(y[z > -700] >= tr.floor)
        elif tr.kind == "log":
            assert np.all(y >= 0.0)
        elif tr.kind == "identity":
            # campaign-2: cape_v is a signed demeaned log -- unbounded BY DESIGN,
            # the identity map is the honest coordinate (no floor to enforce).
            np.testing.assert_array_equal(y, z)
        else:
            assert np.all(y >= -1.0)

    def test_rate_and_spread_floors_hold_under_extreme_noise_panel(self):
        rng = np.random.Generator(np.random.PCG64(3))
        z = 100.0 * rng.standard_normal((64, 6, len(FACTOR_SET)))
        y = ct.panel_to_constrained(z, FACTOR_SET)
        for j, name in enumerate(FACTOR_SET):
            if name in RATE_FLOOR_FACTORS:
                assert np.all(y[..., j] >= RATE_FLOOR_PCT)
            if name in SPREAD_FLOOR_FACTORS:
                assert np.all(y[..., j] >= SPREAD_FLOOR_PCT)


class TestTorchAgreement:
    def test_torch_inverse_matches_numpy_and_is_differentiable(self):
        rng = np.random.Generator(np.random.PCG64(5))
        z_np = rng.standard_normal((8, 6, len(FACTOR_SET)))
        z = torch.tensor(z_np, dtype=torch.float64, requires_grad=True)
        y_t = ct.panel_to_constrained_torch(z, FACTOR_SET)
        np.testing.assert_allclose(
            y_t.detach().numpy(), ct.panel_to_constrained(z_np, FACTOR_SET), rtol=1e-12
        )
        y_t.sum().backward()
        grad = z.grad
        assert grad is not None and bool(torch.all(torch.isfinite(grad)))
        assert bool((grad != 0).any())
