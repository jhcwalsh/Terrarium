"""De-smoothing module (STEP1-DATA-PLAN §WP1.7).

Reported private-markets returns are appraisal-smoothed: a moving average of the
true economic returns. This module recovers the truth two ways —

* **Geltner AR(1)**: estimate the lag-1 autocorrelation phi, then
  ``r_true_t = (r_obs_t - (1 - a) * r_obs_{t-1}) / a`` with ``a = 1 - phi`` (the
  weight on current-quarter truth).
* **GLM MA(k)**: model ``r_obs_t = sum_j theta_j r_true_{t-j}`` with
  ``theta >= 0, sum theta = 1``. theta is estimated on the simplex by whitening the
  recovered truth (true smoothing weights make the recovered truth iid), k in
  {1,2,3} is chosen by AIC (default report k=2), and a boundary solution
  (theta_0 ~ 1, i.e. "no smoothing detected") falls back to Geltner with a warning
  rather than fabricating precision.

Diagnostics (sigma ratio, beta to equity before/after, mean difference, Ljung-Box on
the recovered-truth autocorrelation, theta) are rendered into ``DESMOOTHING.md``.
All estimation is deterministic (seeded), numpy-only.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

Method = Literal["geltner_ar1", "glm_ma", "regime_glm"]

# chi-square 0.95 quantiles by dof (Ljung-Box critical values), dof 1..12.
_CHI2_95 = [3.84, 5.99, 7.81, 9.49, 11.07, 12.59, 14.07, 15.51, 16.92, 18.31, 19.68, 21.03]


@dataclass
class Diagnostics:
    sigma_ratio: float
    beta_before: float
    beta_after: float
    mean_diff: float
    ljung_box_q: float
    ljung_box_crit: float
    ljung_box_ok: bool


@dataclass
class DesmoothResult:
    series_id: str
    method: Method
    theta: list[float]
    k: int
    aic: float
    truth: np.ndarray
    fell_back: bool = False
    warnings: list[str] = field(default_factory=list)
    diagnostics: Diagnostics | None = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _acf(x: np.ndarray, lag: int) -> float:
    x = x - x.mean()
    denom = np.sum(x**2)
    if denom == 0 or lag >= len(x):
        return 0.0
    return float(np.sum(x[lag:] * x[:-lag]) / denom)


def _recover_truth(obs: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """Invert obs_t = sum_j theta_j truth_{t-j} recursively (theta[0] > 0)."""
    k = len(theta) - 1
    truth = np.zeros_like(obs)
    for t in range(len(obs)):
        acc = obs[t]
        for j in range(1, k + 1):
            if t - j >= 0:
                acc -= theta[j] * truth[t - j]
        truth[t] = acc / theta[0]
    return truth


def _autocorr_objective(obs: np.ndarray, theta: np.ndarray) -> float:
    truth = _recover_truth(obs, theta)
    return float(sum(_acf(truth, lag) ** 2 for lag in range(1, len(theta))))


def _simplex_grid(k: int, step: float = 0.05) -> list[np.ndarray]:
    """Weights [theta_0..theta_k] on the simplex with theta_0 the largest (smoothing)."""
    points = round(1.0 / step)  # round() of a float returns an int
    grids = []
    for combo in itertools.product(range(points + 1), repeat=k):
        tail = np.array(combo, dtype=float) * step
        head = 1.0 - tail.sum()
        if head <= 0:
            continue
        theta = np.concatenate([[head], tail])
        if theta[0] >= theta[1:].max(initial=0.0):  # dominant current-quarter weight
            grids.append(theta)
    return grids


# --------------------------------------------------------------------------- #
# Geltner AR(1)
# --------------------------------------------------------------------------- #


def geltner_ar1(obs: np.ndarray) -> DesmoothResult:
    phi = _acf(obs, 1)
    phi = float(np.clip(phi, 0.0, 0.95))
    a = 1.0 - phi
    truth = obs.copy().astype(float)
    for t in range(1, len(obs)):
        truth[t] = (obs[t] - phi * obs[t - 1]) / a if a > 1e-6 else obs[t]
    return DesmoothResult("", "geltner_ar1", [a, phi], 1, float("nan"), truth)


# --------------------------------------------------------------------------- #
# GLM MA(k)
# --------------------------------------------------------------------------- #


def _fit_ma_k(obs: np.ndarray, k: int) -> tuple[np.ndarray, float]:
    best_theta = np.concatenate([[1.0], np.zeros(k)])
    best_obj = _autocorr_objective(obs, best_theta)
    for theta in _simplex_grid(k):
        obj = _autocorr_objective(obs, theta)
        if obj < best_obj:
            best_obj, best_theta = obj, theta
    n = len(obs)
    aic = n * math.log(best_obj + 1e-8) + 2 * k
    return best_theta, aic


def glm_ma(obs: np.ndarray, kmax: int = 3, *, default_k: int = 2) -> DesmoothResult:
    """Fit MA(k) for k in 1..kmax, select by AIC; fall back to Geltner on a boundary."""
    fits = {k: _fit_ma_k(obs, k) for k in range(1, kmax + 1)}

    # AIC selection, nudged toward default_k on near-ties
    def score(k: int) -> float:
        return fits[k][1] + (0.0 if k == default_k else 1e-6)

    k = min(fits, key=score)
    theta, aic = fits[k]

    warnings: list[str] = []
    if theta[0] >= 0.9:  # tail mass < 0.1 -> essentially no smoothing detected
        warnings.append("boundary solution (theta_0 ~ 1); falling back to Geltner AR(1)")
        fallback = geltner_ar1(obs)
        fallback.warnings = warnings
        fallback.fell_back = True
        return fallback

    truth = _recover_truth(obs, theta)
    return DesmoothResult("", "glm_ma", [float(x) for x in theta], k, aic, truth, warnings=warnings)


def regime_glm(obs: np.ndarray, crisis_mask: np.ndarray, kmax: int = 2) -> DesmoothResult:
    """Experimental: theta estimated separately in crisis vs normal months."""
    normal = glm_ma(obs[~crisis_mask.astype(bool)], kmax=kmax)
    result = glm_ma(obs, kmax=kmax)
    result.method = "regime_glm"
    result.warnings = [
        *result.warnings,
        "experimental: regime-split theta",
        f"normal theta={normal.theta}",
    ]
    return result


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #


def _beta(y: np.ndarray, x: np.ndarray) -> float:
    x = x - x.mean()
    var = np.sum(x**2)
    if var == 0:
        return 0.0
    return float(np.sum((y - y.mean()) * x) / var)


def ljung_box(x: np.ndarray, lags: int = 8) -> tuple[float, float, bool]:
    n = len(x)
    lags = min(lags, len(_CHI2_95), n - 1)
    q = n * (n + 2) * sum(_acf(x, k) ** 2 / (n - k) for k in range(1, lags + 1))
    crit = _CHI2_95[lags - 1]
    return float(q), float(crit), bool(q < crit)


def diagnostics(
    obs: np.ndarray, truth: np.ndarray, equity: np.ndarray | None = None
) -> Diagnostics:
    sigma_ratio = float(np.std(truth) / np.std(obs)) if np.std(obs) > 0 else float("nan")
    beta_before = _beta(obs, equity) if equity is not None else float("nan")
    beta_after = _beta(truth, equity) if equity is not None else float("nan")
    q, crit, ok = ljung_box(truth)
    return Diagnostics(
        sigma_ratio=sigma_ratio,
        beta_before=beta_before,
        beta_after=beta_after,
        mean_diff=float(truth.mean() - obs.mean()),
        ljung_box_q=q,
        ljung_box_crit=crit,
        ljung_box_ok=ok,
    )


def desmooth_series(
    series_id: str,
    frame: pd.DataFrame,
    *,
    method: Method = "glm_ma",
    equity: np.ndarray | None = None,
) -> DesmoothResult:
    obs = pd.to_numeric(frame["value"]).to_numpy(dtype=float)
    result = geltner_ar1(obs) if method == "geltner_ar1" else glm_ma(obs)
    result.series_id = series_id
    result.diagnostics = diagnostics(obs, result.truth, equity)
    return result


def generate_desmoothing_md(results: list[DesmoothResult]) -> str:
    lines = [
        "# DESMOOTHING.md — de-smoothing diagnostics",
        "",
        "| series | method | k | theta | sigma ratio | beta before | beta after | mean diff | Ljung-Box |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        d = r.diagnostics
        theta = ", ".join(f"{t:.2f}" for t in r.theta)
        if d is None:
            lines.append(f"| {r.series_id} | {r.method} | {r.k} | {theta} | - | - | - | - | - |")
            continue
        lb = "ok" if d.ljung_box_ok else f"Q={d.ljung_box_q:.1f}>{d.ljung_box_crit:.1f}"
        lines.append(
            f"| {r.series_id} | {r.method} | {r.k} | {theta} | {d.sigma_ratio:.2f} | "
            f"{d.beta_before:.2f} | {d.beta_after:.2f} | {d.mean_diff:+.4f} | {lb} |"
        )
        if r.warnings:
            lines.append(f"|   -> {r.series_id} warnings | {'; '.join(r.warnings)} | | | | | | | |")
    return "\n".join(lines) + "\n"
