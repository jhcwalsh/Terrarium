"""LSMC-style liability proxy (WP3.9) — fast PV for interactivity.

Classic least-squares Monte Carlo discipline (the Krah et al. shape) without a
neural network: a polynomial basis regression of liability PV on the
(discount rate, inflation factor) state, because v1's liability model is
smooth in two dimensions and a proxy that a reader can differentiate by hand
beats an opaque one it would take a GPU to audit. The discipline is what
matters and is kept exactly:

* **separate fitting and validation scenario sets** (disjoint seeds, the 7919
  rule);
* **dedicated test points in the capital region** — the worst 1% of funding
  outcomes, which for a fixed asset base is the HIGHEST-liability corner (low
  rates x high inflation);
* **pre-stated error bounds**, declared as module constants BEFORE any fit
  runs and asserted by the fit itself: a proxy accurate on average but wrong
  in disasters is worse than useless here.

Portfolio metrics run direct (the plan's boundary) — only liability PV is
proxied.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ah.port.twin import LiabilityProfile, LiabilityState

SEED_STRIDE = 7919
#: Pre-stated acceptance bounds (relative error), declared before any fit.
MAX_REL_ERR_VALIDATION = 0.005
MAX_REL_ERR_CAPITAL = 0.010
#: The capital region: the worst tail of funding outcomes = the top PV
#: percentile of the validation set.
CAPITAL_REGION_PERCENTILE = 99.0


class ProxyError(ValueError):
    """A fit that violates its pre-stated bounds, or bad inputs."""


def _design(rates: np.ndarray, inflations: np.ndarray, degree: int) -> np.ndarray:
    cols = [(rates**i) * (inflations**j) for i in range(degree + 1) for j in range(degree + 1 - i)]
    return np.stack(cols, axis=1)


@dataclass(frozen=True)
class LiabilityProxy:
    profile: LiabilityProfile
    coefficients: np.ndarray
    degree: int
    max_rel_err_validation: float
    max_rel_err_capital: float
    rate_range: tuple[float, float]
    inflation_range: tuple[float, float]

    def pv(self, rate: float, inflation_factor: float) -> float:
        lo_r, hi_r = self.rate_range
        lo_i, hi_i = self.inflation_range
        if not (lo_r <= rate <= hi_r and lo_i <= inflation_factor <= hi_i):
            raise ProxyError(
                f"state ({rate:.4f}, {inflation_factor:.4f}) outside the fitted "
                f"region — the proxy refuses to extrapolate silently"
            )
        x = _design(np.array([rate]), np.array([inflation_factor]), self.degree)
        return float((x @ self.coefficients)[0])


def _exact_pv(profile: LiabilityProfile, rate: float, inflation: float) -> float:
    return LiabilityState(profile, discount_rate=rate, realized_inflation_factor=inflation).pv()


def fit_liability_proxy(
    profile: LiabilityProfile,
    *,
    rate_range: tuple[float, float] = (0.0, 0.10),
    inflation_range: tuple[float, float] = (0.8, 1.6),
    degree: int = 6,
    n_fit: int = 400,
    n_validation: int = 400,
    seed: int = 20260802,
) -> LiabilityProxy:
    """Fit, validate on a disjoint set, and REFUSE if the pre-stated bounds fail.

    The capital-region check is not an average: every test point in the worst
    tail must individually sit inside ``MAX_REL_ERR_CAPITAL``.
    """
    rng_fit = np.random.Generator(np.random.PCG64(seed))
    rng_val = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE))

    def scenarios(rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
        rates = rng.uniform(*rate_range, size=n)
        infl = rng.uniform(*inflation_range, size=n)
        return rates, infl

    fit_r, fit_i = scenarios(rng_fit, n_fit)
    y_fit = np.array([_exact_pv(profile, r, i) for r, i in zip(fit_r, fit_i, strict=True)])
    x_fit = _design(fit_r, fit_i, degree)
    coefficients, *_ = np.linalg.lstsq(x_fit, y_fit, rcond=None)

    val_r, val_i = scenarios(rng_val, n_validation)
    y_val = np.array([_exact_pv(profile, r, i) for r, i in zip(val_r, val_i, strict=True)])
    y_hat = _design(val_r, val_i, degree) @ coefficients
    rel_err = np.abs(y_hat - y_val) / y_val

    capital_cut = np.percentile(y_val, CAPITAL_REGION_PERCENTILE)
    capital_mask = y_val >= capital_cut
    max_val = float(rel_err.max())
    max_cap = float(rel_err[capital_mask].max()) if capital_mask.any() else float("nan")

    if max_val > MAX_REL_ERR_VALIDATION:
        raise ProxyError(
            f"validation error {max_val:.4%} exceeds the pre-stated "
            f"{MAX_REL_ERR_VALIDATION:.2%} bound — the proxy does not ship"
        )
    if not np.isfinite(max_cap) or max_cap > MAX_REL_ERR_CAPITAL:
        raise ProxyError(
            f"capital-region error {max_cap:.4%} exceeds the pre-stated "
            f"{MAX_REL_ERR_CAPITAL:.2%} bound — accurate on average is not enough"
        )

    return LiabilityProxy(
        profile=profile,
        coefficients=coefficients,
        degree=degree,
        max_rel_err_validation=max_val,
        max_rel_err_capital=max_cap,
        rate_range=rate_range,
        inflation_range=inflation_range,
    )
