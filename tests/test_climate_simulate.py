"""WP2.5 simulate.py: deterministic artifact load, parameter uncertainty inside
the ensemble (the plan's explicit assertion), the c_t cycle contract for WP2.6,
and dynamics consistency with the fitted model's discretization."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.gen.climate import fit as cf
from ah.gen.climate import model as cm
from ah.gen.climate import simulate as cs

# --------------------------------------------------------------------------- #
# synthetic artifact
# --------------------------------------------------------------------------- #

T_MONTHS = 36
N_DRAWS = 8


def _theta_base() -> dict[str, float]:
    return {
        "hl_pi": 12.0,
        "mu_pi": 3.0,
        "sigma_pi": 0.4,
        "hl_r": 15.0,
        "mu_r": 0.75,
        "beta_g": 1.0,
        "sigma_r": 0.3,
        "hl_g": 20.0,
        "mu_g": 2.0,
        "sigma_g": 0.25,
        "hl_v": 10.0,
        "sigma_v": 0.5,
        "a_val": 6.0,
        "b_val": 6.0,
        "hl_L": 8.0,
        "delta_L": 2.0,
        "sigma_L": 2.0,
        "mu_cr": 1.0,
        "sigma_tau": 0.5,
        "lam_cr": 0.7,
        "hl_u": 2.0,
        "sigma_u": 0.8,
        "phi_pi": 0.5,
        "phi_c": 0.5,
        "psi": 1.5,
        "sigma_i": 0.5,
        "s_m_pi": 1.5,
        "s_m_cape": 0.1,
        "s_q_bis": 2.0,
        "s_a_infl": 1.0,
        "s_a_stir": 1.0,
        "s_a_lt": 1.0,
        "s_a_g": 1.5,
        "s_a_cr": 3.0,
        "s_r10": 3.0,
    }


def _make_artifact(tmp_path, *, spread_mu_pi: bool = True) -> cs.ClimateArtifact:
    """An artifact whose posterior draws genuinely disagree about mu_pi."""
    rng = np.random.Generator(np.random.PCG64(99))
    base = _theta_base()
    params = {name: np.full(N_DRAWS, value) for name, value in base.items()}
    if spread_mu_pi:
        # draws disagree about the long-run inflation anchor: 1% .. 8%
        params["mu_pi"] = np.linspace(1.0, 8.0, N_DRAWS)
    states = rng.standard_normal((N_DRAWS, T_MONTHS, cm.N_STATES)) * 0.1
    states[:, :, 0] += 3.0  # pi* around 3
    states[:, :, 1] += 1.0  # r* around 1
    dates = pd.date_range("2018-01-01", periods=T_MONTHS, freq="MS")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "artifact.npz"
    cf.save_artifact(
        path,
        params=params,
        states=states,
        dates=dates,
        meta={"schema_version": "climate-artifact-v1", "seed": 0},
    )
    return cs.load_artifact(path)


# --------------------------------------------------------------------------- #
# deterministic load + simulation
# --------------------------------------------------------------------------- #


class TestDeterminism:
    def test_same_file_same_seed_bit_identical(self, tmp_path):
        art_a = _make_artifact(tmp_path / "a")
        art_b = cs.load_artifact(art_a.path)
        sim_a = cs.simulate_decades(art_a, 6, seed=42)
        sim_b = cs.simulate_decades(art_b, 6, seed=42)
        np.testing.assert_array_equal(sim_a.states, sim_b.states)
        np.testing.assert_array_equal(sim_a.theta_index, sim_b.theta_index)

    def test_different_seed_differs(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim_a = cs.simulate_decades(art, 6, seed=42)
        sim_b = cs.simulate_decades(art, 6, seed=43)
        assert not np.array_equal(sim_a.states, sim_b.states)

    def test_resave_same_content_same_hash(self, tmp_path):
        art_a = _make_artifact(tmp_path / "a")
        art_b = _make_artifact(tmp_path / "b")
        assert art_a.meta["content_sha256"] == art_b.meta["content_sha256"]

    def test_decades_are_seed_stride_independent(self, tmp_path):
        """Decade k depends only on base_seed + 7919*k, not on n_decades."""
        art = _make_artifact(tmp_path)
        sim_small = cs.simulate_decades(art, 2, seed=7)
        sim_large = cs.simulate_decades(art, 5, seed=7)
        np.testing.assert_array_equal(sim_small.states, sim_large.states[:2])


# --------------------------------------------------------------------------- #
# parameter uncertainty inside the ensemble (DN-1.1: asserted, not assumed)
# --------------------------------------------------------------------------- #


class TestParameterUncertainty:
    def test_distinct_decades_draw_distinct_theta(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim = cs.simulate_decades(art, 24, seed=5)
        assert len(np.unique(sim.theta_index)) > 1
        assert len(np.unique(sim.params["mu_pi"])) > 1

    def test_posterior_sampling_widens_across_decade_dispersion(self, tmp_path):
        """The plan's real assertion: across-decade dispersion of decade-mean pi*
        exceeds the fixed-theta counterfactual, because theta varies per decade."""
        art = _make_artifact(tmp_path)
        n = 48
        months = 600  # long enough for mu_pi differences to dominate
        sim_mixed = cs.simulate_decades(art, n, seed=11, months=months)
        decade_means_mixed = sim_mixed.state("pi_star")[:, months // 2 :].mean(axis=1)
        spreads_fixed = []
        for k in range(art.n_draws):
            sim_fixed = cs.simulate_decades(art, n, seed=11, months=months, theta_index=k)
            spreads_fixed.append(sim_fixed.state("pi_star")[:, months // 2 :].mean(axis=1).std())
        assert decade_means_mixed.std() > 2.0 * max(spreads_fixed)

    def test_theta_index_pins_every_decade(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim = cs.simulate_decades(art, 5, seed=3, theta_index=2)
        assert set(sim.theta_index.tolist()) == {2}
        assert set(sim.params["mu_pi"].tolist()) == {float(art.params["mu_pi"][2])}


# --------------------------------------------------------------------------- #
# the c_t cycle contract (what WP2.6 fills in)
# --------------------------------------------------------------------------- #


class TestCycleContract:
    def test_default_is_neutral_zero(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim_none = cs.simulate_decades(art, 3, seed=1)
        sim_zero = cs.simulate_decades(art, 3, seed=1, cycle=np.zeros(120))
        np.testing.assert_array_equal(sim_none.states, sim_zero.states)

    def test_cycle_moves_the_credit_gap_norm(self, tmp_path):
        """delta_L * c_t is the credit norm: a persistent +1 cycle must pull the
        credit gap up relative to a persistent -1 cycle (same noise seed)."""
        art = _make_artifact(tmp_path)
        up = cs.simulate_decades(art, 4, seed=2, cycle=np.ones(120))
        down = cs.simulate_decades(art, 4, seed=2, cycle=-np.ones(120))
        gap_up = up.state("credit_gap")[:, -60:].mean()
        gap_down = down.state("credit_gap")[:, -60:].mean()
        assert gap_up > gap_down
        # ... and only the credit gap: pi*, r*, g, v are cycle-independent in L1
        for name in ("pi_star", "r_star", "g", "v"):
            np.testing.assert_array_equal(up.state(name), down.state(name))

    def test_per_decade_cycle_shape_accepted(self, tmp_path):
        art = _make_artifact(tmp_path)
        cyc = np.zeros((3, 120))
        cyc[1, :] = 0.5
        sim = cs.simulate_decades(art, 3, seed=1, cycle=cyc)
        assert sim.states.shape == (3, 120, cm.N_STATES)

    def test_bad_cycle_shapes_and_values_refused(self, tmp_path):
        art = _make_artifact(tmp_path)
        with pytest.raises(ValueError, match="shape"):
            cs.simulate_decades(art, 3, seed=1, cycle=np.zeros(60))
        with pytest.raises(ValueError, match=r"\[-1, \+1\]"):
            cs.simulate_decades(art, 3, seed=1, cycle=np.full(120, 2.0))
        with pytest.raises(ValueError, match="finite"):
            cs.simulate_decades(art, 3, seed=1, cycle=np.full(120, np.nan))


# --------------------------------------------------------------------------- #
# s0 selection (incl. the WP2.11 severe-test path: start from a chosen date)
# --------------------------------------------------------------------------- #


class TestStartState:
    def test_default_s0_is_last_grid_month(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim = cs.simulate_decades(art, 3, seed=9)
        assert sim.s0_date == art.dates[-1]
        for k in range(3):
            np.testing.assert_array_equal(sim.states[k, 0], art.states[sim.theta_index[k], -1])

    def test_explicit_s0_date_selects_that_month(self, tmp_path):
        art = _make_artifact(tmp_path)
        target: pd.Timestamp = art.dates[10]  # type: ignore[assignment]
        sim = cs.simulate_decades(art, 3, seed=9, s0_date=target)
        for k in range(3):
            np.testing.assert_array_equal(sim.states[k, 0], art.states[sim.theta_index[k], 10])

    def test_off_grid_s0_date_refused(self, tmp_path):
        art = _make_artifact(tmp_path)
        with pytest.raises(ValueError, match="monthly grid"):
            cs.simulate_decades(art, 3, seed=9, s0_date="1965-01-15")


# --------------------------------------------------------------------------- #
# dynamics consistency with the fitted model + the anchor helper
# --------------------------------------------------------------------------- #


class TestDynamics:
    def test_noiseless_path_matches_model_transition_matrices(self, tmp_path):
        """With all state sigmas zero the simulated path must equal the
        deterministic recursion of model.transition_matrix/transition_offsets."""
        rng = np.random.Generator(np.random.PCG64(4))
        base = _theta_base()
        for name in ("sigma_pi", "sigma_r", "sigma_g", "sigma_v", "sigma_L"):
            base[name] = 0.0
        params = {name: np.full(2, val) for name, val in base.items()}
        states = rng.standard_normal((2, 12, cm.N_STATES))
        dates = pd.date_range("2020-01-01", periods=12, freq="MS")
        path = tmp_path / "det.npz"
        cf.save_artifact(path, params=params, states=states, dates=dates, meta={})
        art = cs.load_artifact(path)

        months = 24
        cyc = np.sin(np.arange(months) / 3.0)  # within [-1, 1]
        sim = cs.simulate_decades(art, 1, seed=0, months=months, cycle=cyc, theta_index=0)

        a = np.asarray(cm.transition_matrix(base))
        b = np.asarray(cm.transition_offsets(base, cyc))
        s = np.zeros(cm.N_KF_STATES)
        s[: cm.N_STATES] = art.states[0, -1]
        expected = [s[: cm.N_STATES].copy()]
        for t in range(months - 1):
            s = a @ s + b[t]
            expected.append(s[: cm.N_STATES].copy())
        np.testing.assert_allclose(sim.states[0], np.array(expected), atol=1e-12)

    def test_policy_anchor_closed_form(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim = cs.simulate_decades(art, 3, seed=8, months=24)
        cyc = np.full(24, 0.25)
        anchor = cs.policy_anchor(sim, cycle=cyc)
        k = 1
        expected = sim.state("r_star")[k] + sim.state("pi_star")[k] + sim.params["phi_c"][k] * 0.25
        np.testing.assert_allclose(anchor[k], expected, atol=1e-12)

    def test_policy_anchor_with_actual_inflation(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim = cs.simulate_decades(art, 2, seed=8, months=12)
        pi_act = sim.state("pi_star") + 1.0
        anchor = cs.policy_anchor(sim, pi_actual=pi_act)
        base = cs.policy_anchor(sim)
        np.testing.assert_allclose(
            anchor - base, sim.params["phi_pi"][:, None] * np.ones((2, 12)), atol=1e-12
        )

    def test_anchor_rejects_wrong_pi_shape(self, tmp_path):
        art = _make_artifact(tmp_path)
        sim = cs.simulate_decades(art, 2, seed=8, months=12)
        with pytest.raises(ValueError, match="pi_actual"):
            cs.policy_anchor(sim, pi_actual=np.zeros((3, 12)))

    def test_input_validation(self, tmp_path):
        art = _make_artifact(tmp_path)
        with pytest.raises(ValueError, match="n_decades"):
            cs.simulate_decades(art, 0, seed=1)
        with pytest.raises(ValueError, match="months"):
            cs.simulate_decades(art, 1, seed=1, months=0)
        with pytest.raises(ValueError, match="theta_index"):
            cs.simulate_decades(art, 1, seed=1, theta_index=N_DRAWS)
