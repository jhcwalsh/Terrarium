"""WP2.5 Layer 1 climate model: config, discretization, Kalman filter, FFBS.

Ground-truth strategy: the model is linear-Gaussian throughout, so the Kalman
filter's marginal log-likelihood and the FFBS smoother's conditional moments are
checked against a brute-force joint-multivariate-normal computation on tiny
problems (exact, no simulation tolerance games).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ah.experiment import config_hash
from ah.gen.climate import model as cm

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _theta_example() -> dict[str, float]:
    """A fixed, hand-checkable parameter point (units: %/yr, years, log units)."""
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
        "delta_L": 1.0,
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


# --------------------------------------------------------------------------- #
# cycle 1 -- config
# --------------------------------------------------------------------------- #


class TestConfig:
    def test_default_config_loads_and_has_every_prior(self):
        cfg = cm.load_config()
        assert set(cfg.priors) == set(cm.PARAM_NAMES)

    def test_dn11_priors_table_defaults(self):
        """The DN-1.1 priors table, verbatim, in the packaged defaults."""
        cfg = cm.load_config()
        assert cfg.priors["hl_pi"].dist == "lognormal_ci90"
        assert cfg.priors["hl_pi"].ci_lo == 8.0
        assert cfg.priors["hl_pi"].ci_hi == 20.0
        assert cfg.priors["mu_r"].dist == "normal"
        assert cfg.priors["mu_r"].loc == 0.75
        assert cfg.priors["mu_r"].scale == 0.75
        assert cfg.priors["phi_pi"].dist == "truncnormal"
        assert cfg.priors["phi_pi"].loc == 0.5
        assert cfg.priors["phi_pi"].scale == 0.25
        assert cfg.priors["phi_pi"].low == 0.0
        # every state/observation sigma is half-Cauchy ("let the century speak")
        for name, prior in cfg.priors.items():
            if name.startswith(("sigma_", "s_")):
                assert prior.dist == "halfcauchy", name

    def test_fit_defaults_tuned_for_real_panel(self):
        """The packaged NUTS settings: dense mass (35 correlated params), capped
        tree depth (a depth-10 tree costs ~2 min/iter on the real panel), 4
        parallel chains."""
        cfg = cm.load_config()
        assert cfg.fit.dense_mass is True
        assert cfg.fit.max_tree_depth == 8
        assert cfg.fit.chains == 4
        assert cfg.fit.chain_method == "parallel"

    def test_config_dict_hash_is_deterministic(self):
        a = cm.load_config()
        b = cm.load_config()
        assert config_hash(cm.config_dict(a)) == config_hash(cm.config_dict(b))

    def test_config_hash_changes_when_a_prior_moves(self):
        a = cm.load_config()
        b = cm.load_config()
        b.priors["mu_r"].loc = 1.5
        assert config_hash(cm.config_dict(a)) != config_hash(cm.config_dict(b))

    def test_lognormal_ci90_maps_quantiles_back(self):
        mu, sigma = cm.lognormal_ci90_params(8.0, 20.0)
        z95 = 1.6448536269514722
        assert math.exp(mu - z95 * sigma) == pytest.approx(8.0, rel=1e-9)
        assert math.exp(mu + z95 * sigma) == pytest.approx(20.0, rel=1e-9)

    def test_half_life_to_kappa(self):
        assert cm.half_life_to_kappa(10.0) == pytest.approx(math.log(2.0) / 10.0)

    def test_unknown_prior_dist_rejected(self):
        bad: dict = {"dist": "student_t", "loc": 0.0, "scale": 1.0}
        with pytest.raises(ValueError):
            cm.Prior(**bad)

    def test_state_contract(self):
        """The DN-1.1 SS II.2 five-state contract order, plus internal KF extras."""
        assert cm.STATE_NAMES == ("pi_star", "r_star", "g", "v", "credit_gap")
        assert cm.N_STATES == 5
        assert cm.KF_STATE_NAMES[: cm.N_STATES] == cm.STATE_NAMES
        assert len(cm.KF_STATE_NAMES) == cm.N_KF_STATES


# --------------------------------------------------------------------------- #
# cycle 2 -- Euler discretization matrices
# --------------------------------------------------------------------------- #


class TestDiscretization:
    def test_transition_matrix_hand_values(self):
        theta = _theta_example()
        A = np.asarray(cm.transition_matrix(theta))
        dt = cm.DT
        k_pi = math.log(2.0) / theta["hl_pi"]
        k_r = math.log(2.0) / theta["hl_r"]
        k_g = math.log(2.0) / theta["hl_g"]
        k_v = math.log(2.0) / theta["hl_v"]
        k_l = math.log(2.0) / theta["hl_L"]
        k_u = math.log(2.0) / theta["hl_u"]
        i = {name: j for j, name in enumerate(cm.KF_STATE_NAMES)}
        assert A[i["pi_star"], i["pi_star"]] == pytest.approx(1 - k_pi * dt)
        assert A[i["r_star"], i["r_star"]] == pytest.approx(1 - k_r * dt)
        # dr* = ... + beta_g dg: the g-column of the r* row carries -beta_g*k_g*dt
        assert A[i["r_star"], i["g"]] == pytest.approx(-theta["beta_g"] * k_g * dt)
        assert A[i["g"], i["g"]] == pytest.approx(1 - k_g * dt)
        assert A[i["v"], i["v"]] == pytest.approx(1 - k_v * dt)
        assert A[i["credit_gap"], i["credit_gap"]] == pytest.approx(1 - k_l * dt)
        assert A[i["credit_trend"], i["credit_trend"]] == pytest.approx(1.0)
        assert A[i["policy_dev"], i["policy_dev"]] == pytest.approx(1 - k_u * dt)
        # no other couplings
        expected_nonzero = {
            (i["pi_star"], i["pi_star"]),
            (i["r_star"], i["r_star"]),
            (i["r_star"], i["g"]),
            (i["g"], i["g"]),
            (i["v"], i["v"]),
            (i["credit_gap"], i["credit_gap"]),
            (i["credit_trend"], i["credit_trend"]),
            (i["policy_dev"], i["policy_dev"]),
        }
        nonzero = set(zip(*np.nonzero(A), strict=True))
        assert nonzero == expected_nonzero

    def test_transition_offset_carries_cycle_into_credit_norm(self):
        theta = _theta_example()
        cycle = np.array([0.0, 1.0, -1.0])
        b = np.asarray(cm.transition_offsets(theta, cycle))
        dt = cm.DT
        i = {name: j for j, name in enumerate(cm.KF_STATE_NAMES)}
        k_pi = math.log(2.0) / theta["hl_pi"]
        k_g = math.log(2.0) / theta["hl_g"]
        k_r = math.log(2.0) / theta["hl_r"]
        k_l = math.log(2.0) / theta["hl_L"]
        assert b.shape == (3, cm.N_KF_STATES)
        assert b[0, i["pi_star"]] == pytest.approx(k_pi * theta["mu_pi"] * dt)
        assert b[0, i["r_star"]] == pytest.approx(
            k_r * theta["mu_r"] * dt + theta["beta_g"] * k_g * theta["mu_g"] * dt
        )
        assert b[0, i["g"]] == pytest.approx(k_g * theta["mu_g"] * dt)
        assert b[0, i["v"]] == 0.0
        # credit-gap norm L_bar = delta_L * c_t: offset k_l * delta_L * c * dt
        assert b[0, i["credit_gap"]] == pytest.approx(0.0)
        assert b[1, i["credit_gap"]] == pytest.approx(k_l * theta["delta_L"] * 1.0 * dt)
        assert b[2, i["credit_gap"]] == pytest.approx(-k_l * theta["delta_L"] * 1.0 * dt)
        assert b[0, i["credit_trend"]] == pytest.approx(theta["mu_cr"] * dt)
        assert b[0, i["policy_dev"]] == 0.0

    def test_process_noise_couples_r_star_and_g(self):
        theta = _theta_example()
        Q = np.asarray(cm.process_noise(theta))
        dt = cm.DT
        i = {name: j for j, name in enumerate(cm.KF_STATE_NAMES)}
        assert Q.shape == (cm.N_KF_STATES, cm.N_KF_STATES)
        assert Q[i["pi_star"], i["pi_star"]] == pytest.approx(theta["sigma_pi"] ** 2 * dt)
        # r* variance includes its own noise plus beta_g^2 times g's noise
        assert Q[i["r_star"], i["r_star"]] == pytest.approx(
            (theta["sigma_r"] ** 2 + theta["beta_g"] ** 2 * theta["sigma_g"] ** 2) * dt
        )
        assert Q[i["r_star"], i["g"]] == pytest.approx(theta["beta_g"] * theta["sigma_g"] ** 2 * dt)
        assert Q[i["g"], i["r_star"]] == Q[i["r_star"], i["g"]]
        # symmetric positive definite
        np.testing.assert_allclose(Q, Q.T)
        assert np.all(np.linalg.eigvalsh(Q) > 0)

    def test_observation_matrix_hand_values(self):
        theta = _theta_example()
        H = np.asarray(cm.observation_matrix(theta))
        i = {name: j for j, name in enumerate(cm.KF_STATE_NAMES)}
        c = {name: j for j, name in enumerate(cm.CHANNELS)}
        assert H.shape == (cm.N_CHANNELS, cm.N_KF_STATES)
        # monthly inflation observes pi_star
        assert H[c["m_infl"], i["pi_star"]] == 1.0
        # the Taylor anchor: i = r* + pi* + phi_pi(pi_obs - pi*) + phi_c c + u + eps
        assert H[c["m_policy"], i["pi_star"]] == pytest.approx(1 - theta["phi_pi"])
        assert H[c["m_policy"], i["r_star"]] == 1.0
        assert H[c["m_policy"], i["policy_dev"]] == 1.0
        assert H[c["m_cape"], i["v"]] == 1.0
        assert H[c["q_bis"], i["credit_gap"]] == 1.0
        assert H[c["a_stir"], i["pi_star"]] == pytest.approx(1 - theta["phi_pi"])
        assert H[c["a_stir"], i["policy_dev"]] == 1.0
        assert H[c["a_ltrate"], i["pi_star"]] == 1.0
        assert H[c["a_ltrate"], i["r_star"]] == 1.0
        assert H[c["a_growth"], i["g"]] == 1.0
        # JST credit ratio observes trend + lam_cr * gap
        assert H[c["a_credit"], i["credit_trend"]] == 1.0
        assert H[c["a_credit"], i["credit_gap"]] == pytest.approx(theta["lam_cr"])
        # ten-year forward real equity return: a - b*v
        assert H[c["a_r10"], i["v"]] == pytest.approx(-theta["b_val"])

    def test_observation_offsets(self):
        theta = _theta_example()
        T = 2
        aux_pi = np.zeros((T, cm.N_CHANNELS))
        aux_c = np.zeros((T, cm.N_CHANNELS))
        c = {name: j for j, name in enumerate(cm.CHANNELS)}
        aux_pi[0, c["m_policy"]] = 4.0
        aux_c[0, c["m_policy"]] = 1.0
        aux_pi[1, c["a_stir"]] = 2.0
        aux_c[1, c["a_stir"]] = -1.0
        d = np.asarray(cm.observation_offsets(theta, aux_pi, aux_c))
        assert d.shape == (T, cm.N_CHANNELS)
        assert d[0, c["m_policy"]] == pytest.approx(theta["phi_pi"] * 4.0 + theta["phi_c"] * 1.0)
        assert d[1, c["a_stir"]] == pytest.approx(theta["phi_pi"] * 2.0 - theta["phi_c"])
        assert d[0, c["a_ltrate"]] == pytest.approx(theta["psi"])
        assert d[0, c["a_r10"]] == pytest.approx(theta["a_val"])
        assert d[0, c["m_infl"]] == 0.0
        assert d[0, c["a_credit"]] == 0.0

    def test_observation_noise_vector(self):
        theta = _theta_example()
        r = np.asarray(cm.observation_noise_sd(theta))
        c = {name: j for j, name in enumerate(cm.CHANNELS)}
        assert r.shape == (cm.N_CHANNELS,)
        assert r[c["m_infl"]] == theta["s_m_pi"]
        assert r[c["m_policy"]] == theta["sigma_i"]
        assert r[c["a_r10"]] == theta["s_r10"]


# --------------------------------------------------------------------------- #
# brute-force linear-Gaussian ground truth (numpy, exact)
# --------------------------------------------------------------------------- #


def _brute_force_moments(
    theta: dict[str, float],
    m0: np.ndarray,
    p0: np.ndarray,
    cycle: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    aux_pi: np.ndarray,
    aux_c: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Exact marginal loglik + posterior state means via one big joint Gaussian.

    States s_0..s_{T-1} stacked into one vector; observations are a linear map of
    it. Exact for a linear-Gaussian model -- the reference the KF must match.
    """
    T = y.shape[0]
    n = cm.N_KF_STATES
    A = np.asarray(cm.transition_matrix(theta))
    b = np.asarray(cm.transition_offsets(theta, cycle))
    Q = np.asarray(cm.process_noise(theta))
    H = np.asarray(cm.observation_matrix(theta))
    d = np.asarray(cm.observation_offsets(theta, aux_pi, aux_c))
    rsd = np.asarray(cm.observation_noise_sd(theta))

    # joint mean/cov of the stacked state vector (T*n,)
    mean = np.zeros(T * n)
    cov = np.zeros((T * n, T * n))
    mean[:n] = m0
    cov[:n, :n] = p0
    for t in range(1, T):
        prev = slice((t - 1) * n, t * n)
        cur = slice(t * n, (t + 1) * n)
        mean[cur] = A @ mean[prev] + b[t - 1]
        # cov rows: cov(s_t, s_k) = A cov(s_{t-1}, s_k) for k < t
        for k in range(t):
            ks = slice(k * n, (k + 1) * n)
            cov[cur, ks] = A @ cov[prev, ks]
            cov[ks, cur] = cov[cur, ks].T
        cov[cur, cur] = A @ cov[prev, prev] @ A.T + Q

    # observation selection
    rows = []
    obs_vals = []
    obs_mean_offset = []
    noise_vars = []
    for t in range(T):
        for j in range(cm.N_CHANNELS):
            if mask[t, j]:
                row = np.zeros(T * n)
                row[t * n : (t + 1) * n] = H[j]
                rows.append(row)
                obs_vals.append(y[t, j])
                obs_mean_offset.append(d[t, j])
                noise_vars.append(rsd[j] ** 2)
    Hbig = np.array(rows)
    yv = np.array(obs_vals)
    dv = np.array(obs_mean_offset)
    R = np.diag(noise_vars)

    mu_y = Hbig @ mean + dv
    S = Hbig @ cov @ Hbig.T + R
    resid = yv - mu_y
    sign, logdet = np.linalg.slogdet(S)
    assert sign > 0
    k = len(yv)
    ll = -0.5 * (k * math.log(2 * math.pi) + logdet + resid @ np.linalg.solve(S, resid))

    # posterior mean of the stacked states
    gain = cov @ Hbig.T @ np.linalg.inv(S)
    post_mean = mean + gain @ resid
    return float(ll), post_mean.reshape(T, n)


def _tiny_problem(seed: int = 0):
    """A tiny mixed-frequency problem with irregular missingness."""
    rng = np.random.default_rng(seed)
    theta = _theta_example()
    T = 10
    m0 = np.array([3.0, 2.0, 2.0, 0.0, 0.0, -160.0, 0.0])
    p0 = np.diag([4.0, 2.0, 1.0, 0.25, 9.0, 100.0, 1.0])
    cycle = np.sign(rng.standard_normal(T))
    y = np.full((T, cm.N_CHANNELS), np.nan)
    mask = np.zeros((T, cm.N_CHANNELS), dtype=bool)
    aux_pi = np.zeros((T, cm.N_CHANNELS))
    aux_c = np.zeros((T, cm.N_CHANNELS))
    c = {name: j for j, name in enumerate(cm.CHANNELS)}
    for t in range(T):
        # monthly channels most months, annual channels sparsely
        for name in ("m_infl", "m_cape"):
            if rng.random() < 0.8:
                mask[t, c[name]] = True
        if rng.random() < 0.6:
            mask[t, c["m_policy"]] = True
            aux_pi[t, c["m_policy"]] = 3.0 + rng.standard_normal()
            aux_c[t, c["m_policy"]] = cycle[t]
        if t in (3, 7):
            for name in ("a_infl", "a_stir", "a_ltrate", "a_growth", "a_credit", "a_r10"):
                mask[t, c[name]] = True
            aux_pi[t, c["a_stir"]] = 3.0
            aux_c[t, c["a_stir"]] = cycle[t]
        if t == 5:
            mask[t, c["q_bis"]] = True
    y[mask] = rng.standard_normal(int(mask.sum())) * 2.0
    y[:, c["a_credit"]] = np.where(mask[:, c["a_credit"]], -158.0 + rng.standard_normal(T), np.nan)
    return theta, m0, p0, cycle, y, mask, aux_pi, aux_c


# --------------------------------------------------------------------------- #
# cycle 3 -- Kalman filter marginal likelihood
# --------------------------------------------------------------------------- #


class TestKalmanFilter:
    def test_loglik_matches_brute_force_joint_gaussian(self):
        theta, m0, p0, cycle, y, mask, aux_pi, aux_c = _tiny_problem()
        ll_exact, _ = _brute_force_moments(theta, m0, p0, cycle, y, mask, aux_pi, aux_c)
        data = cm.KFData(
            y=np.nan_to_num(y),
            mask=mask.astype(np.float64),
            aux_pi=aux_pi,
            aux_c=aux_c,
            cycle=cycle,
            m0=m0,
            p0=p0,
        )
        ll_kf = float(cm.kalman_loglik(theta, data))
        assert ll_kf == pytest.approx(ll_exact, rel=1e-8)

    def test_loglik_is_finite_and_masking_matters(self):
        theta, m0, p0, cycle, y, mask, aux_pi, aux_c = _tiny_problem(seed=1)
        data = cm.KFData(
            y=np.nan_to_num(y),
            mask=mask.astype(np.float64),
            aux_pi=aux_pi,
            aux_c=aux_c,
            cycle=cycle,
            m0=m0,
            p0=p0,
        )
        ll_full = float(cm.kalman_loglik(theta, data))
        assert np.isfinite(ll_full)
        # dropping an observed channel changes the likelihood
        mask2 = mask.copy()
        mask2[:, 0] = False
        data2 = cm.KFData(
            y=np.nan_to_num(y),
            mask=mask2.astype(np.float64),
            aux_pi=aux_pi,
            aux_c=aux_c,
            cycle=cycle,
            m0=m0,
            p0=p0,
        )
        assert float(cm.kalman_loglik(theta, data2)) != pytest.approx(ll_full)


# --------------------------------------------------------------------------- #
# cycle 4 -- FFBS smoother draws
# --------------------------------------------------------------------------- #


class TestPriorPredictive:
    """Prior predictive sanity: the packaged priors imply plausible slow states."""

    def test_half_life_prior_hits_dn11_interval(self):
        import jax

        cfg = cm.load_config()
        d = cm.prior_distribution(cfg.priors["hl_pi"])
        samples = np.asarray(d.sample(jax.random.PRNGKey(0), (20000,)))
        lo, hi = np.quantile(samples, [0.05, 0.95])
        assert lo == pytest.approx(8.0, rel=0.05)
        assert hi == pytest.approx(20.0, rel=0.05)

    def test_prior_draws_simulate_finite_stationary_decades(self):
        import jax

        from ah.gen.climate.model import DT

        cfg = cm.load_config()
        key = jax.random.PRNGKey(1)
        n = 50
        rng = np.random.default_rng(2)
        thetas = {}
        for name in cm.PARAM_NAMES:
            key, sub = jax.random.split(key)
            thetas[name] = np.asarray(cm.prior_distribution(cfg.priors[name]).sample(sub, (n,)))
        # Euler-step 120 months per prior draw from the init-state prior mean
        m0, _ = cm.init_state_moments(cfg)
        for i in range(n):
            theta = {name: float(thetas[name][i]) for name in cm.PARAM_NAMES}
            s = m0[: cm.N_STATES].copy()
            for _t in range(120):
                eps = rng.standard_normal(cm.N_STATES)
                k = {p: math.log(2.0) / theta[p] for p in ("hl_pi", "hl_r", "hl_g", "hl_v", "hl_L")}
                dg = (
                    k["hl_g"] * (theta["mu_g"] - s[2]) * DT
                    + theta["sigma_g"] * math.sqrt(DT) * eps[2]
                )
                s[0] += (
                    k["hl_pi"] * (theta["mu_pi"] - s[0]) * DT
                    + theta["sigma_pi"] * math.sqrt(DT) * eps[0]
                )
                s[1] += (
                    k["hl_r"] * (theta["mu_r"] - s[1]) * DT
                    + theta["beta_g"] * dg
                    + theta["sigma_r"] * math.sqrt(DT) * eps[1]
                )
                s[2] += dg
                s[3] += -k["hl_v"] * s[3] * DT + theta["sigma_v"] * math.sqrt(DT) * eps[3]
                s[4] += k["hl_L"] * (0.0 - s[4]) * DT + theta["sigma_L"] * math.sqrt(DT) * eps[4]
            assert np.all(np.isfinite(s))
            # half-lives well over a month keep the Euler step stable: 1-k*dt > 0
            for kappa in k.values():
                assert 1.0 - kappa * DT > 0.0


class TestFFBS:
    def test_ffbs_mean_matches_exact_posterior_mean(self):
        import jax

        theta, m0, p0, cycle, y, mask, aux_pi, aux_c = _tiny_problem(seed=2)
        _, post_mean = _brute_force_moments(theta, m0, p0, cycle, y, mask, aux_pi, aux_c)
        data = cm.KFData(
            y=np.nan_to_num(y),
            mask=mask.astype(np.float64),
            aux_pi=aux_pi,
            aux_c=aux_c,
            cycle=cycle,
            m0=m0,
            p0=p0,
        )
        n_draws = 4000
        keys = jax.random.split(jax.random.PRNGKey(0), n_draws)
        draws = np.asarray(cm.ffbs_draws(keys, theta, data))
        assert draws.shape == (n_draws, y.shape[0], cm.N_KF_STATES)
        assert np.all(np.isfinite(draws))
        emp_mean = draws.mean(axis=0)
        emp_sd = draws.std(axis=0)
        se = emp_sd / math.sqrt(n_draws)
        # every state, every time: empirical mean within 5 standard errors of exact
        np.testing.assert_array_less(np.abs(emp_mean - post_mean), 5.0 * se + 1e-9)

    def test_ffbs_is_deterministic_in_key(self):
        import jax

        theta, m0, p0, cycle, y, mask, aux_pi, aux_c = _tiny_problem(seed=3)
        data = cm.KFData(
            y=np.nan_to_num(y),
            mask=mask.astype(np.float64),
            aux_pi=aux_pi,
            aux_c=aux_c,
            cycle=cycle,
            m0=m0,
            p0=p0,
        )
        keys = jax.random.split(jax.random.PRNGKey(7), 3)
        a = np.asarray(cm.ffbs_draws(keys, theta, data))
        b = np.asarray(cm.ffbs_draws(keys, theta, data))
        np.testing.assert_array_equal(a, b)
