"""WP1.7 acceptance: de-smoothing (Geltner + GLM MA(k)) + diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from ah.data.desmooth import (
    desmooth_series,
    diagnostics,
    geltner_ar1,
    generate_desmoothing_md,
    glm_ma,
    ljung_box,
    regime_glm,
)


def _smooth(truth: np.ndarray, theta: list[float]) -> np.ndarray:
    """obs_t = sum_j theta_j truth_{t-j}."""
    obs = np.zeros_like(truth)
    for t in range(len(truth)):
        obs[t] = sum(theta[j] * truth[t - j] for j in range(len(theta)) if t - j >= 0)
    return obs


# --------------------------------------------------------------------------- #
# Geltner
# --------------------------------------------------------------------------- #


def test_geltner_recovers_higher_vol() -> None:
    rng = np.random.Generator(np.random.PCG64(0))
    truth = rng.normal(0, 0.05, 400)
    obs = _smooth(truth, [0.5, 0.5])  # AR(1)-style smoothing
    result = geltner_ar1(obs)
    assert np.std(result.truth) > np.std(obs)  # de-smoothed vol is higher


def test_geltner_mean_preserved() -> None:
    rng = np.random.Generator(np.random.PCG64(1))
    truth = rng.normal(0.01, 0.05, 400)
    obs = _smooth(truth, [0.6, 0.4])
    result = geltner_ar1(obs)
    assert abs(result.truth.mean() - obs.mean()) < 0.01  # ~ preserved


# --------------------------------------------------------------------------- #
# GLM MA(k)
# --------------------------------------------------------------------------- #


def test_glm_ma_selects_k_and_theta_sums_to_one() -> None:
    rng = np.random.Generator(np.random.PCG64(2))
    truth = rng.normal(0, 0.05, 300)
    obs = _smooth(truth, [0.5, 0.3, 0.2])
    result = glm_ma(obs, kmax=3)
    assert result.k in (1, 2, 3)
    assert abs(sum(result.theta) - 1.0) < 1e-9
    assert result.theta[0] >= max(result.theta[1:])  # dominant current-quarter weight


def test_glm_ma_boundary_falls_back_to_geltner() -> None:
    rng = np.random.Generator(np.random.PCG64(3))
    obs = rng.normal(0, 0.05, 300)  # iid, unsmoothed -> theta_0 ~ 1
    result = glm_ma(obs, kmax=2)
    assert result.fell_back
    assert result.method == "geltner_ar1"
    assert any("boundary" in w for w in result.warnings)


def test_regime_glm_is_experimental() -> None:
    rng = np.random.Generator(np.random.PCG64(4))
    truth = rng.normal(0, 0.05, 200)
    obs = _smooth(truth, [0.5, 0.3, 0.2])
    mask = np.zeros(len(obs))
    mask[50:80] = 1
    result = regime_glm(obs, mask)
    assert result.method == "regime_glm"
    assert any("experimental" in w for w in result.warnings)


# --------------------------------------------------------------------------- #
# Ljung-Box + diagnostics
# --------------------------------------------------------------------------- #


def test_ljung_box_iid_vs_autocorrelated() -> None:
    rng = np.random.Generator(np.random.PCG64(5))
    iid = rng.normal(0, 1, 500)
    _, _, ok = ljung_box(iid)
    assert ok
    # a strongly autocorrelated series fails
    ar = np.zeros(500)
    for t in range(1, 500):
        ar[t] = 0.8 * ar[t - 1] + rng.normal(0, 1)
    _, _, ok_ar = ljung_box(ar)
    assert not ok_ar


def test_diagnostics_sigma_ratio_and_beta() -> None:
    rng = np.random.Generator(np.random.PCG64(6))
    equity = rng.normal(0, 0.04, 300)
    truth = 0.8 * equity + rng.normal(0, 0.02, 300)
    obs = _smooth(truth, [0.4, 0.35, 0.25])
    d = diagnostics(obs, truth, equity)
    assert d.sigma_ratio > 1.0  # de-smoothed vol higher than reported
    assert d.beta_after > d.beta_before  # beta-to-equity rises after de-smoothing
    assert abs(d.mean_diff) < 0.01


def test_desmooth_series_and_md() -> None:
    rng = np.random.Generator(np.random.PCG64(7))
    truth = rng.normal(0, 0.05, 200)
    obs = _smooth(truth, [0.5, 0.3, 0.2])
    frame = pd.DataFrame(
        {"date": pd.date_range("2000-01-01", periods=200, freq="QS"), "value": obs}
    )
    r = desmooth_series("albourne.pm_buyout_ret_q", frame, method="glm_ma")
    assert r.series_id == "albourne.pm_buyout_ret_q"
    assert r.diagnostics is not None
    md = generate_desmoothing_md([r])
    assert "DESMOOTHING.md" in md
    assert "albourne.pm_buyout_ret_q" in md


# --------------------------------------------------------------------------- #
# property: smooth then de-smooth recovers volatility within tolerance
# --------------------------------------------------------------------------- #


@settings(max_examples=15, deadline=None)
@given(sigma=st.floats(0.02, 0.1), seed=st.integers(0, 10_000))
def test_smooth_then_desmooth_recovers_vol(sigma: float, seed: int) -> None:
    rng = np.random.Generator(np.random.PCG64(seed))
    truth = rng.normal(0, sigma, 300)
    obs = _smooth(truth, [0.5, 0.3, 0.2])
    result = glm_ma(obs, kmax=2)
    recovered_vol = float(np.std(result.truth))
    true_vol = float(np.std(truth))
    # recovered volatility is within 35% of the truth (and above the smoothed vol)
    assert 0.65 * true_vol <= recovered_vol <= 1.5 * true_vol
    assert recovered_vol > np.std(obs) * 0.95
