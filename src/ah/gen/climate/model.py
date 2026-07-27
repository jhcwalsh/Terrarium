"""WP2.5 Layer 1 -- the climate model (DN-1.1 SS II.2), numpyro/JAX side.

The five-state slow vector s_t = (pi*, r*, g, v, L): trend inflation, neutral real
rate, trend growth, log equity valuation (CAPE-like, demeaned on the TRAIN span),
credit/leverage gap. Euler-discretized monthly (dt = 1/12), estimated by NUTS on a
mixed-frequency panel fusing the annual JST macrohistory (1870-2020) with the
monthly Step-1 panel (via the sanctioned ``DataAccess.train_val`` surface).

Model structure (linear-Gaussian throughout, so the latent states are marginalized
exactly by a Kalman filter and NUTS runs over the ~35 structural parameters only;
joint (theta, s) posterior draws come from an FFBS pass per retained theta draw):

- Dynamics per DN-1.1 SS II.2, with two recorded gap-fills:
  (1) g_t has no dynamics equation in the design note; an OU reversion to mu_g is
      chosen (productivity eras persist decades -- see priors.yaml).
  (2) L_bar(R_t), the regime-dependent credit norm, is expressed through the cycle
      term: L_bar_t = delta_L * c_t. The regime skeleton R_t does not exist until
      WP2.6; c_t is the same exogenous cycle input the policy anchor consumes, so
      WP2.6's regime output flows into BOTH consumers through ONE contract.
- Two internal (non-contract) states ride along in the Kalman filter:
  ``credit_trend`` (tau): a slow stochastic trend in 100*log(tloans/gdp), so the
      150-year secular credit deepening is not forced into the gap L (LW-style
      trend/gap decomposition; identified by smoothness priors + the BIS gap).
  ``policy_dev`` (u): an OU deviation from the Taylor anchor, because actual policy
      deviates persistently (the ZLB decade); without it the filter would push
      those deviations into r*. The exported state contract stays the five of
      DN-1.1; tau and u are observation-model auxiliaries.
- The Taylor anchor i_t = r* + pi* + phi_pi(pi_t - pi*) + phi_c c_t + u_t + eps is
  an OBSERVATION equation (with pi_t = observed actual inflation and c_t exogenous
  data), never a state -- which is what lets WP2.6 swap its own c_t in at
  simulation time without refitting L1.

The cycle term c_t (the WP2.6 contract): an exogenous array, values in [-1, +1].
For FITTING on history the proxy is c_t = 1 - 2*USREC (NBER: +1 expansion, -1
recession) -- full-span coverage 1854-, the canonical cycle dating, and exactly the
discrete signal WP2.6's regime skeleton replaces. See ``ah.gen.climate.fit``.

Numerical precision: this module enables ``jax_enable_x64`` at import. The Kalman
recursion propagates 7x7 covariances over ~1800 steps; float32 accumulates enough
error there to corrupt gradients and NUTS adaptation, and every other numeric
surface in this repo is float64 (CLAUDE.md digests are over float64 tensors).
Import-time is deliberate: every entry point into climate math (fit, tests) must
see the same precision, and this package is the repo's only JAX consumer.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import jax
import numpy as np
import yaml
from pydantic import BaseModel, model_validator

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402  (after x64 switch, deliberately)
import numpyro  # noqa: E402
import numpyro.distributions as dist  # noqa: E402

# --------------------------------------------------------------------------- #
# the state contract (DN-1.1 SS II.2) and the internal KF state
# --------------------------------------------------------------------------- #

#: The five-state Layer-1 contract, in DN-1.1 order. Everything downstream
#: (simulate, WP2.6 hazards, WP2.7 waypoints) consumes exactly these five.
STATE_NAMES: tuple[str, ...] = ("pi_star", "r_star", "g", "v", "credit_gap")
N_STATES = 5

#: The Kalman-filter state: the contract plus two observation-model auxiliaries
#: (see the module docstring). Order matters; the first N_STATES are the contract.
KF_STATE_NAMES: tuple[str, ...] = (*STATE_NAMES, "credit_trend", "policy_dev")
N_KF_STATES = len(KF_STATE_NAMES)

#: Monthly Euler step, in years.
DT = 1.0 / 12.0

#: Observation channels, fixed order. m_* monthly, q_* quarterly, a_* annual.
CHANNELS: tuple[str, ...] = (
    "m_infl",  # monthly CPI YoY (log-diff, annualized %) ~ pi* + noise
    "m_policy",  # monthly policy rate ~ Taylor anchor
    "m_cape",  # monthly log CAPE, TRAIN-demeaned ~ v + noise
    "q_bis",  # quarterly BIS credit-to-GDP gap ~ L + noise
    "a_infl",  # JST annual inflation ~ pi* + noise (mid-year)
    "a_stir",  # JST annual short rate ~ Taylor anchor (mid-year)
    "a_ltrate",  # JST annual long rate ~ pi* + r* + psi + noise
    "a_growth",  # JST annual real GDP growth ~ g + noise
    "a_credit",  # JST 100*log(tloans/gdp) ~ tau + lam_cr*L + noise
    "a_r10",  # 10y forward real equity return ~ a - b*v + noise
)
N_CHANNELS = len(CHANNELS)

#: Channel -> the theta entry holding its observation noise sd.
CHANNEL_NOISE_PARAM: Mapping[str, str] = {
    "m_infl": "s_m_pi",
    "m_policy": "sigma_i",
    "m_cape": "s_m_cape",
    "q_bis": "s_q_bis",
    "a_infl": "s_a_infl",
    "a_stir": "s_a_stir",
    "a_ltrate": "s_a_lt",
    "a_growth": "s_a_g",
    "a_credit": "s_a_cr",
    "a_r10": "s_r10",
}

#: Every structural parameter, in sampling order. priors.yaml must cover exactly
#: this set (asserted by ClimateConfig and by tests).
PARAM_NAMES: tuple[str, ...] = (
    "hl_pi",
    "mu_pi",
    "sigma_pi",
    "hl_r",
    "mu_r",
    "beta_g",
    "sigma_r",
    "hl_g",
    "mu_g",
    "sigma_g",
    "hl_v",
    "sigma_v",
    "a_val",
    "b_val",
    "hl_L",
    "delta_L",
    "sigma_L",
    "mu_cr",
    "sigma_tau",
    "lam_cr",
    "hl_u",
    "sigma_u",
    "phi_pi",
    "phi_c",
    "psi",
    "sigma_i",
    "s_m_pi",
    "s_m_cape",
    "s_q_bis",
    "s_a_infl",
    "s_a_stir",
    "s_a_lt",
    "s_a_g",
    "s_a_cr",
    "s_r10",
)


# --------------------------------------------------------------------------- #
# config (YAML -> pydantic, hashed into the experiment record)
# --------------------------------------------------------------------------- #


class Prior(BaseModel):
    """One prior spec. ``dist`` selects the family; the fields it needs must be set.

    - ``normal``: loc, scale
    - ``truncnormal``: loc, scale, low
    - ``lognormal_ci90``: ci_lo, ci_hi -- the 90% CI of the quantity itself (e.g.
      a half-life in years); mapped to LogNormal(mu, sigma) via its quantiles.
    - ``halfcauchy``: scale
    """

    dist: Literal["normal", "truncnormal", "lognormal_ci90", "halfcauchy"]
    loc: float | None = None
    scale: float | None = None
    low: float | None = None
    ci_lo: float | None = None
    ci_hi: float | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> Prior:
        need: dict[str, tuple[str, ...]] = {
            "normal": ("loc", "scale"),
            "truncnormal": ("loc", "scale", "low"),
            "lognormal_ci90": ("ci_lo", "ci_hi"),
            "halfcauchy": ("scale",),
        }
        for field in need[self.dist]:
            if getattr(self, field) is None:
                raise ValueError(f"prior dist '{self.dist}' requires field '{field}'")
        return self


class InitStatePrior(BaseModel):
    loc: float
    scale: float


class SpanSettings(BaseModel):
    start: str
    end: str  # exclusive


class SeriesIds(BaseModel):
    cpi_monthly: str
    policy_rate_monthly: str
    cape_monthly: str
    usrec_monthly: str
    bis_gap_quarterly: str
    jst_cpi: str
    jst_stir: str
    jst_ltrate: str
    jst_gdp: str
    jst_tloans: str
    jst_eq_tr: str


class FitSettings(BaseModel):
    chains: int = 4
    warmup: int = 1000
    samples: int = 1000
    target_accept: float = 0.9
    max_tree_depth: int = 10
    dense_mass: bool = False
    chain_method: str = "sequential"
    artifact_draws: int = 1000
    ppc_draws: int = 200


class ClimateConfig(BaseModel):
    priors: dict[str, Prior]
    init_state: dict[str, InitStatePrior]
    span: SpanSettings
    series: SeriesIds
    fit: FitSettings

    @model_validator(mode="after")
    def _check_complete(self) -> ClimateConfig:
        missing = set(PARAM_NAMES) - set(self.priors)
        extra = set(self.priors) - set(PARAM_NAMES)
        if missing or extra:
            raise ValueError(
                f"priors must cover PARAM_NAMES exactly; missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
        missing_init = set(KF_STATE_NAMES) - set(self.init_state)
        if missing_init:
            raise ValueError(f"init_state missing entries for {sorted(missing_init)}")
        return self


_DEFAULT_CONFIG_PATH = Path(__file__).with_name("priors.yaml")


def load_config(path: str | Path | None = None) -> ClimateConfig:
    """Load the climate config (default: the packaged ``priors.yaml``)."""
    p = _DEFAULT_CONFIG_PATH if path is None else Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return ClimateConfig.model_validate(raw)


def config_dict(config: ClimateConfig) -> dict[str, Any]:
    """A canonical plain-dict rendering for ``ah.experiment.config_hash``."""
    return config.model_dump(mode="json", exclude_none=True)


# --------------------------------------------------------------------------- #
# prior/parameter transforms
# --------------------------------------------------------------------------- #

_Z95 = 1.6448536269514722  # Phi^{-1}(0.95)


def lognormal_ci90_params(ci_lo: float, ci_hi: float) -> tuple[float, float]:
    """(mu, sigma) of a LogNormal whose 5%/95% quantiles are ``ci_lo``/``ci_hi``."""
    if not (0 < ci_lo < ci_hi):
        raise ValueError(f"need 0 < ci_lo < ci_hi; got {ci_lo}, {ci_hi}")
    log_lo, log_hi = math.log(ci_lo), math.log(ci_hi)
    mu = 0.5 * (log_lo + log_hi)
    sigma = (log_hi - log_lo) / (2.0 * _Z95)
    return mu, sigma


def half_life_to_kappa(half_life_years: Any) -> Any:
    """OU mean-reversion rate (per year) from a half-life in years."""
    return jnp.log(2.0) / half_life_years


def prior_distribution(spec: Prior) -> dist.Distribution:
    """The numpyro distribution for one ``Prior`` spec."""
    if spec.dist == "normal":
        return dist.Normal(spec.loc, spec.scale)
    if spec.dist == "truncnormal":
        return dist.TruncatedNormal(loc=spec.loc, scale=spec.scale, low=spec.low)
    if spec.dist == "lognormal_ci90":
        assert spec.ci_lo is not None and spec.ci_hi is not None
        mu, sigma = lognormal_ci90_params(spec.ci_lo, spec.ci_hi)
        return dist.LogNormal(mu, sigma)
    if spec.dist == "halfcauchy":
        return dist.HalfCauchy(spec.scale)
    raise ValueError(f"unknown prior dist '{spec.dist}'")  # pragma: no cover


# --------------------------------------------------------------------------- #
# Euler discretization (DN-1.1 SS II.2 dynamics, monthly)
# --------------------------------------------------------------------------- #

_IDX = {name: i for i, name in enumerate(KF_STATE_NAMES)}
_CH = {name: i for i, name in enumerate(CHANNELS)}


def transition_matrix(theta: Mapping[str, Any]) -> jnp.ndarray:
    """A in s_{t+1} = A s_t + b_t + w_t, w_t ~ N(0, Q). Shape (7, 7)."""
    k_pi = half_life_to_kappa(theta["hl_pi"])
    k_r = half_life_to_kappa(theta["hl_r"])
    k_g = half_life_to_kappa(theta["hl_g"])
    k_v = half_life_to_kappa(theta["hl_v"])
    k_l = half_life_to_kappa(theta["hl_L"])
    k_u = half_life_to_kappa(theta["hl_u"])
    beta_g = theta["beta_g"]

    a = jnp.zeros((N_KF_STATES, N_KF_STATES))
    a = a.at[_IDX["pi_star"], _IDX["pi_star"]].set(1.0 - k_pi * DT)
    a = a.at[_IDX["r_star"], _IDX["r_star"]].set(1.0 - k_r * DT)
    # dr* = kappa_r(mu_r - r*)dt + beta_g dg + sigma_r dW: substituting dg's own
    # drift gives the g-column coupling; dg's diffusion lands in Q (see below).
    a = a.at[_IDX["r_star"], _IDX["g"]].set(-beta_g * k_g * DT)
    a = a.at[_IDX["g"], _IDX["g"]].set(1.0 - k_g * DT)
    a = a.at[_IDX["v"], _IDX["v"]].set(1.0 - k_v * DT)
    a = a.at[_IDX["credit_gap"], _IDX["credit_gap"]].set(1.0 - k_l * DT)
    a = a.at[_IDX["credit_trend"], _IDX["credit_trend"]].set(1.0)
    a = a.at[_IDX["policy_dev"], _IDX["policy_dev"]].set(1.0 - k_u * DT)
    return a


def transition_offsets(theta: Mapping[str, Any], cycle: Any) -> jnp.ndarray:
    """b_t for every step, shape (T, 7). ``cycle`` is the exogenous c_t array."""
    cycle = jnp.asarray(cycle)
    t_len = cycle.shape[0]
    k_pi = half_life_to_kappa(theta["hl_pi"])
    k_r = half_life_to_kappa(theta["hl_r"])
    k_g = half_life_to_kappa(theta["hl_g"])
    k_l = half_life_to_kappa(theta["hl_L"])

    b = jnp.zeros((t_len, N_KF_STATES))
    b = b.at[:, _IDX["pi_star"]].set(k_pi * theta["mu_pi"] * DT)
    b = b.at[:, _IDX["r_star"]].set(
        k_r * theta["mu_r"] * DT + theta["beta_g"] * k_g * theta["mu_g"] * DT
    )
    b = b.at[:, _IDX["g"]].set(k_g * theta["mu_g"] * DT)
    # credit-gap norm: L_bar_t = delta_L * c_t (the WP2.6 cycle contract's second
    # consumer; see the module docstring)
    b = b.at[:, _IDX["credit_gap"]].set(k_l * theta["delta_L"] * cycle * DT)
    b = b.at[:, _IDX["credit_trend"]].set(theta["mu_cr"] * DT)
    return b


def process_noise(theta: Mapping[str, Any]) -> jnp.ndarray:
    """Q, shape (7, 7). r* carries beta_g times g's Brownian in addition to its own."""
    beta_g = theta["beta_g"]
    q = jnp.zeros((N_KF_STATES, N_KF_STATES))
    q = q.at[_IDX["pi_star"], _IDX["pi_star"]].set(theta["sigma_pi"] ** 2 * DT)
    q = q.at[_IDX["r_star"], _IDX["r_star"]].set(
        (theta["sigma_r"] ** 2 + beta_g**2 * theta["sigma_g"] ** 2) * DT
    )
    q = q.at[_IDX["r_star"], _IDX["g"]].set(beta_g * theta["sigma_g"] ** 2 * DT)
    q = q.at[_IDX["g"], _IDX["r_star"]].set(beta_g * theta["sigma_g"] ** 2 * DT)
    q = q.at[_IDX["g"], _IDX["g"]].set(theta["sigma_g"] ** 2 * DT)
    q = q.at[_IDX["v"], _IDX["v"]].set(theta["sigma_v"] ** 2 * DT)
    q = q.at[_IDX["credit_gap"], _IDX["credit_gap"]].set(theta["sigma_L"] ** 2 * DT)
    q = q.at[_IDX["credit_trend"], _IDX["credit_trend"]].set(theta["sigma_tau"] ** 2 * DT)
    q = q.at[_IDX["policy_dev"], _IDX["policy_dev"]].set(theta["sigma_u"] ** 2 * DT)
    return q


# --------------------------------------------------------------------------- #
# observation model
# --------------------------------------------------------------------------- #


def observation_matrix(theta: Mapping[str, Any]) -> jnp.ndarray:
    """H, shape (n_channels, 7): y_t = H s_t + d_t + eps."""
    phi_pi = theta["phi_pi"]
    h = jnp.zeros((N_CHANNELS, N_KF_STATES))
    h = h.at[_CH["m_infl"], _IDX["pi_star"]].set(1.0)
    # anchor: i = r* + pi* + phi_pi*(pi_obs - pi*) + phi_c*c + u + eps
    #        = (1 - phi_pi)*pi* + r* + u + [phi_pi*pi_obs + phi_c*c] + eps
    h = h.at[_CH["m_policy"], _IDX["pi_star"]].set(1.0 - phi_pi)
    h = h.at[_CH["m_policy"], _IDX["r_star"]].set(1.0)
    h = h.at[_CH["m_policy"], _IDX["policy_dev"]].set(1.0)
    h = h.at[_CH["m_cape"], _IDX["v"]].set(1.0)
    h = h.at[_CH["q_bis"], _IDX["credit_gap"]].set(1.0)
    h = h.at[_CH["a_infl"], _IDX["pi_star"]].set(1.0)
    h = h.at[_CH["a_stir"], _IDX["pi_star"]].set(1.0 - phi_pi)
    h = h.at[_CH["a_stir"], _IDX["r_star"]].set(1.0)
    h = h.at[_CH["a_stir"], _IDX["policy_dev"]].set(1.0)
    h = h.at[_CH["a_ltrate"], _IDX["pi_star"]].set(1.0)
    h = h.at[_CH["a_ltrate"], _IDX["r_star"]].set(1.0)
    h = h.at[_CH["a_growth"], _IDX["g"]].set(1.0)
    h = h.at[_CH["a_credit"], _IDX["credit_trend"]].set(1.0)
    h = h.at[_CH["a_credit"], _IDX["credit_gap"]].set(theta["lam_cr"])
    # E[r_equity(10y)] = a - b*v (valuation mean reversion => predictability)
    h = h.at[_CH["a_r10"], _IDX["v"]].set(-theta["b_val"])
    return h


def observation_offsets(theta: Mapping[str, Any], aux_pi: Any, aux_c: Any) -> jnp.ndarray:
    """d_t, shape (T, n_channels).

    ``aux_pi[t, ch]`` holds observed actual inflation for the anchor channels
    (zero elsewhere); ``aux_c[t, ch]`` the cycle term for those channels.
    """
    aux_pi = jnp.asarray(aux_pi)
    aux_c = jnp.asarray(aux_c)
    d = theta["phi_pi"] * aux_pi + theta["phi_c"] * aux_c
    d = d.at[:, _CH["a_ltrate"]].add(theta["psi"])
    d = d.at[:, _CH["a_r10"]].add(theta["a_val"])
    return d


def observation_noise_sd(theta: Mapping[str, Any]) -> jnp.ndarray:
    """Per-channel observation noise sd, shape (n_channels,)."""
    return jnp.stack([jnp.asarray(theta[CHANNEL_NOISE_PARAM[ch]]) for ch in CHANNELS])


# --------------------------------------------------------------------------- #
# masked mixed-frequency Kalman filter (marginal likelihood) + FFBS
# --------------------------------------------------------------------------- #


class KFData:
    """The filter's data bundle. Arrays are float64; ``mask`` is 0/1 float.

    ``y`` must be NaN-free (mask the gaps and zero-fill them); ``m0``/``p0`` are
    the initial-state prior moments at the first row's date.
    """

    def __init__(
        self,
        *,
        y: np.ndarray,
        mask: np.ndarray,
        aux_pi: np.ndarray,
        aux_c: np.ndarray,
        cycle: np.ndarray,
        m0: np.ndarray,
        p0: np.ndarray,
    ) -> None:
        self.y = np.asarray(y, dtype=np.float64)
        self.mask = np.asarray(mask, dtype=np.float64)
        self.aux_pi = np.asarray(aux_pi, dtype=np.float64)
        self.aux_c = np.asarray(aux_c, dtype=np.float64)
        self.cycle = np.asarray(cycle, dtype=np.float64)
        self.m0 = np.asarray(m0, dtype=np.float64)
        self.p0 = np.asarray(p0, dtype=np.float64)
        t_len = self.y.shape[0]
        for name, arr, shape in (
            ("y", self.y, (t_len, N_CHANNELS)),
            ("mask", self.mask, (t_len, N_CHANNELS)),
            ("aux_pi", self.aux_pi, (t_len, N_CHANNELS)),
            ("aux_c", self.aux_c, (t_len, N_CHANNELS)),
            ("cycle", self.cycle, (t_len,)),
            ("m0", self.m0, (N_KF_STATES,)),
            ("p0", self.p0, (N_KF_STATES, N_KF_STATES)),
        ):
            if arr.shape != shape:
                raise ValueError(f"KFData.{name}: expected shape {shape}, got {arr.shape}")
        if np.isnan(self.y).any():
            raise ValueError("KFData.y must be NaN-free (zero-fill masked gaps)")


def _kf_matrices(theta: Mapping[str, Any], data: KFData):
    a = transition_matrix(theta)
    b = transition_offsets(theta, data.cycle)
    q = process_noise(theta)
    h = observation_matrix(theta)
    d = observation_offsets(theta, data.aux_pi, data.aux_c)
    r_var = observation_noise_sd(theta) ** 2
    return a, b, q, h, d, r_var


def _filter_step(a, q, h, r_var, carry, inputs):
    """One month: sequential scalar updates over the channels, unrolled.

    Unrolled Python loop rather than an inner ``lax.scan``: the channel count is
    small and static, and a flat per-step graph keeps the reverse-mode gradient
    ~4x cheaper than a nested scan (measured on the real panel), which is what
    NUTS wall-clock is made of. The math is identical either way.
    """
    m_pred, p_pred, ll = carry
    y_t, mask_t, d_t = inputs

    m, p = m_pred, p_pred
    for j in range(N_CHANNELS):
        h_row = h[j]
        msk = mask_t[j]
        s_var = h_row @ p @ h_row + r_var[j]
        resid = y_t[j] - (h_row @ m + d_t[j])
        gain = (p @ h_row) / s_var
        ll_i = -0.5 * (jnp.log(2.0 * jnp.pi * s_var) + resid**2 / s_var)
        m = m + msk * gain * resid
        p_new = p - msk * s_var * jnp.outer(gain, gain)
        p = 0.5 * (p_new + p_new.T)
        ll = ll + msk * ll_i
    return m, p, ll


def kalman_loglik(theta: Mapping[str, Any], data: KFData) -> jnp.ndarray:
    """Exact marginal log-likelihood of the masked mixed-frequency panel."""
    a, b, q, h, d, r_var = _kf_matrices(theta, data)
    y = jnp.asarray(data.y)
    mask = jnp.asarray(data.mask)

    def step(carry, inputs):
        m_f, p_f, ll = carry
        y_t, mask_t, d_t, b_prev, first = inputs
        # predict from the previous filtered state (skip at t=0: prior IS predictive)
        m_pred = jnp.where(first, m_f, a @ m_f + b_prev)
        p_pred = jnp.where(first, p_f, a @ p_f @ a.T + q)
        m_new, p_new, ll_new = _filter_step(
            a, q, h, r_var, (m_pred, p_pred, ll), (y_t, mask_t, d_t)
        )
        return (m_new, p_new, ll_new), None

    t_len = y.shape[0]
    first_flags = jnp.zeros(t_len, dtype=bool).at[0].set(True)
    b_prev = jnp.concatenate([jnp.zeros((1, N_KF_STATES)), b[:-1]], axis=0)
    init = (jnp.asarray(data.m0), jnp.asarray(data.p0), jnp.asarray(0.0))
    (_, _, ll), _ = jax.lax.scan(step, init, (y, mask, d, b_prev, first_flags))
    return ll


def _filter_pass(theta: Mapping[str, Any], data: KFData):
    """Filtered moments per month (for FFBS). Returns (means (T,7), covs (T,7,7))."""
    a, b, q, h, d, r_var = _kf_matrices(theta, data)
    y = jnp.asarray(data.y)
    mask = jnp.asarray(data.mask)
    t_len = y.shape[0]
    first_flags = jnp.zeros(t_len, dtype=bool).at[0].set(True)
    b_prev = jnp.concatenate([jnp.zeros((1, N_KF_STATES)), b[:-1]], axis=0)

    def step(carry, inputs):
        m_f, p_f = carry
        y_t, mask_t, d_t, b_p, first = inputs
        m_pred = jnp.where(first, m_f, a @ m_f + b_p)
        p_pred = jnp.where(first, p_f, a @ p_f @ a.T + q)
        m_new, p_new, _ = _filter_step(a, q, h, r_var, (m_pred, p_pred, 0.0), (y_t, mask_t, d_t))
        return (m_new, p_new), (m_new, p_new)

    init = (jnp.asarray(data.m0), jnp.asarray(data.p0))
    _, (means, covs) = jax.lax.scan(step, init, (y, mask, d, b_prev, first_flags))
    return means, covs


_JITTER = 1e-9


def _ffbs_single(key, theta: Mapping[str, Any], data: KFData) -> jnp.ndarray:
    """One backward-sampling draw of the full state path, shape (T, 7)."""
    a = transition_matrix(theta)
    b = transition_offsets(theta, data.cycle)
    q = process_noise(theta)
    means, covs = _filter_pass(theta, data)
    t_len = means.shape[0]

    def draw(k, mean, cov):
        cov = 0.5 * (cov + cov.T) + _JITTER * jnp.eye(N_KF_STATES)
        chol = jnp.linalg.cholesky(cov)
        return mean + chol @ jax.random.normal(k, (N_KF_STATES,))

    keys = jax.random.split(key, t_len)
    s_last = draw(keys[-1], means[-1], covs[-1])

    def back_step(carry, inputs):
        s_next = carry
        m_f, p_f, b_t, k = inputs
        m_pred = a @ m_f + b_t
        p_pred = a @ p_f @ a.T + q
        p_pred = 0.5 * (p_pred + p_pred.T) + _JITTER * jnp.eye(N_KF_STATES)
        j = jnp.linalg.solve(p_pred.T, (a @ p_f)).T  # J = P_f A' P_pred^{-1}
        mean = m_f + j @ (s_next - m_pred)
        cov = p_f - j @ p_pred @ j.T
        s_t = draw(k, mean, cov)
        return s_t, s_t

    # iterate t = T-2 .. 0; b_t is the offset used in the t -> t+1 transition
    inputs = (means[:-1][::-1], covs[:-1][::-1], b[:-1][::-1], keys[:-1][::-1])
    _, draws_rev = jax.lax.scan(back_step, s_last, inputs)
    path = jnp.concatenate([draws_rev[::-1], s_last[None, :]], axis=0)
    return path


def ffbs_draws(keys, theta: Mapping[str, Any], data: KFData) -> jnp.ndarray:
    """Vectorized FFBS: one smoothed state-path draw per key, (n_keys, T, 7)."""
    return jax.vmap(lambda k: _ffbs_single(k, theta, data))(keys)


# --------------------------------------------------------------------------- #
# the numpyro model
# --------------------------------------------------------------------------- #


def init_state_moments(config: ClimateConfig) -> tuple[np.ndarray, np.ndarray]:
    """(m0, P0) of the initial-state prior, in KF_STATE_NAMES order."""
    m0 = np.array([config.init_state[n].loc for n in KF_STATE_NAMES], dtype=np.float64)
    p0 = np.diag([config.init_state[n].scale ** 2 for n in KF_STATE_NAMES]).astype(np.float64)
    return m0, p0


def numpyro_model(data: KFData, config: ClimateConfig) -> None:
    """Priors from config; the marginalized KF likelihood as a factor."""
    theta = {
        name: numpyro.sample(name, prior_distribution(config.priors[name])) for name in PARAM_NAMES
    }
    numpyro.factor("kf_loglik", kalman_loglik(theta, data))
