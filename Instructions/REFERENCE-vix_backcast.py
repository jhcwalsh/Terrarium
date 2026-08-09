"""Backcast ``equity_vol`` (implied volatility) before its observed start.

Why this exists
---------------
``bootstrap_v1.block_draw_span`` is pinned to 1990-01..2020-12 because
``equity_vol`` (fred.VIXCLS) begins 1990-01. The benchmark therefore cannot
reach ANY pre-1990 episode -- not 1973-74, not 1987, not 1929-33 -- while the
challenger, fitted on the full span, has seen all of them. That asymmetry is
disclosed in the G2 evidence pack and is the reason the promotion had to be
re-run on a restricted window.

This module extends ``equity_vol`` backward from realized volatility, which is
computable from daily index prices as far back as those prices exist (1927-12
for the S&P composite).

Discipline, following ``ah.data.splice``
----------------------------------------
A synthetic observation is never silent. Every backcast row carries
``is_proxy=True`` and a ``rule_id``; a backcast NEVER overwrites an observed
month; and the fitted relationship must clear the acceptance checks in
:func:`validate` before any output is written to a vintage.

THE FAILURE MODE THIS MODULE IS BUILT TO AVOID
-----------------------------------------------
A regression's FITTED VALUES ARE SMOOTHER THAN THE TRUTH by construction: the
conditional mean discards the residual variance. Splicing a point-estimate
backcast into the panel would give the pre-1990 era an artificially calm
volatility-of-volatility -- suppressing exactly the tail behaviour the
extension exists to recover, and biasing any tail metric computed over the
extended span toward complacency.

:func:`backcast` therefore returns an ENSEMBLE by default. Residuals are
resampled in blocks (preserving their own autocorrelation and heteroskedastic
clustering) and added back in log space. Use ``n_draws=0`` to obtain the bare
conditional mean, and only for diagnostics -- never for a panel that feeds a
tail metric.

Specification
-------------
Target is monthly log implied vol. Features are a HAR cascade (Corsi 2009) of
trailing realized vol at daily/weekly/monthly/annual horizons, plus two terms
that carry the parts of the variance risk premium a symmetric RV measure
cannot: downside participation (the leverage effect, Black 1976; Christie 1982)
and within-window tail severity (jumps, Barndorff-Nielsen & Shephard 2004).

    log VIX_t = a
              + b1 log RV_t(22)  + b2 log RV_t(66) + b3 log RV_t(252)
              + g1 downside_t    + g2 log(1 + maxdd_t)
              + e_t

Estimated by OLS with Newey-West (1987) HAC standard errors, because
overlapping trailing windows induce strong residual autocorrelation and
plain OLS standard errors would be badly understated.

References
----------
Corsi, F. (2009). A simple approximate long-memory model of realized
    volatility. Journal of Financial Econometrics 7(2).
Newey, W. & West, K. (1987). A simple, positive semi-definite,
    heteroskedasticity and autocorrelation consistent covariance matrix.
    Econometrica 55(3).
Parkinson, M. (1980). The extreme value method for estimating the variance of
    the rate of return. Journal of Business 53(1).
Garman, M. & Klass, M. (1980). On the estimation of security price volatilities
    from historical data. Journal of Business 53(1).
Christensen, B. & Prabhala, N. (1998). The relation between implied and
    realized volatility. Journal of Financial Economics 50(2).
Carr, P. & Wu, L. (2009). Variance risk premiums. Review of Financial
    Studies 22(3).
Bekaert, G. & Hoerova, M. (2014). The VIX, the variance premium and stock
    market volatility. Journal of Econometrics 183(2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

__all__ = [
    "RVConfig",
    "BackcastSpec",
    "BackcastFit",
    "ValidationReport",
    "realized_features",
    "fit",
    "validate",
    "backcast",
    "TRADING_DAYS",
]

TRADING_DAYS = 252

#: Feature columns, in the order they enter the design matrix. Frozen: the
#: coefficient vector in a stored fit is positional.
FEATURES: tuple[str, ...] = (
    "log_rv22",
    "log_rv66",
    "log_rv252",
    "downside",
    "log_maxdd",
)


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RVConfig:
    """How realized volatility is measured from daily prices."""

    #: "close" (close-to-close), "parkinson", or "garman_klass".
    #: Range-based estimators are 5-8x more efficient per observation but need
    #: trustworthy intraday high/low. Yahoo's S&P composite carries H=L=C
    #: before 1962, so ``close`` is the only honest choice across the full span
    #: unless the caller supplies a better OHLC source.
    estimator: str = "close"
    #: Trailing windows in trading days, matched to FEATURES.
    windows: tuple[int, ...] = (22, 66, 252)
    #: Minimum non-null daily observations in a month for it to be usable.
    min_days_per_month: int = 15


@dataclass(frozen=True)
class BackcastSpec:
    """The rule, in the sense of ``ah.data.splice.ProxyRule``."""

    rule_id: str = "PROXY-EQUITY-VOL-HAR-V1"
    target: str = "fred.VIXCLS"
    donor: str = "daily_index_prices"
    overlap_start: str = "1990-01-01"
    overlap_end: str | None = None
    rv: RVConfig = field(default_factory=RVConfig)
    #: Newey-West lag truncation. Default follows the longest trailing window
    #: in months (252 trading days ~ 12 months), the horizon over which
    #: overlapping windows mechanically induce correlation.
    hac_lags: int = 12
    #: Block length in months for residual resampling.
    residual_block_months: int = 12
    doc: str = (
        "Monthly log implied vol regressed on a HAR cascade of trailing "
        "realized vol plus downside participation and within-window tail "
        "severity; residuals resampled in blocks so the backcast retains "
        "vol-of-vol."
    )


# --------------------------------------------------------------------------
# feature construction
# --------------------------------------------------------------------------


def _daily_returns(px: pd.DataFrame) -> pd.Series:
    close = px["close"].astype(float)
    return np.log(close).diff()


def _rv_close(ret: pd.Series, window: int) -> pd.Series:
    """Annualized close-to-close realized vol, in percentage points."""
    return ret.rolling(window, min_periods=max(5, window // 2)).std() * np.sqrt(
        TRADING_DAYS
    ) * 100.0


def _rv_parkinson(px: pd.DataFrame, window: int) -> pd.Series:
    hl = np.log(px["high"].astype(float) / px["low"].astype(float)) ** 2
    var = hl.rolling(window, min_periods=max(5, window // 2)).mean() / (4.0 * np.log(2.0))
    return np.sqrt(var * TRADING_DAYS) * 100.0


def _rv_garman_klass(px: pd.DataFrame, window: int) -> pd.Series:
    hi, lo = np.log(px["high"].astype(float)), np.log(px["low"].astype(float))
    op, cl = np.log(px["open"].astype(float)), np.log(px["close"].astype(float))
    term = 0.5 * (hi - lo) ** 2 - (2.0 * np.log(2.0) - 1.0) * (cl - op) ** 2
    var = term.rolling(window, min_periods=max(5, window // 2)).mean()
    return np.sqrt(var.clip(lower=1e-12) * TRADING_DAYS) * 100.0


def _rv(px: pd.DataFrame, ret: pd.Series, window: int, cfg: RVConfig) -> pd.Series:
    if cfg.estimator == "close":
        return _rv_close(ret, window)
    if cfg.estimator == "parkinson":
        _require_ohlc(px)
        return _rv_parkinson(px, window)
    if cfg.estimator == "garman_klass":
        _require_ohlc(px)
        return _rv_garman_klass(px, window)
    raise ValueError(f"unknown rv estimator: {cfg.estimator!r}")


def _require_ohlc(px: pd.DataFrame) -> None:
    missing = {"open", "high", "low"} - set(px.columns)
    if missing:
        raise ValueError(f"range estimator needs OHLC; missing {sorted(missing)}")
    degenerate = float((px["high"] <= px["low"]).mean())
    if degenerate > 0.02:
        raise ValueError(
            f"{degenerate:.1%} of rows have high <= low -- this OHLC is "
            "synthetic (common for pre-1962 index history). Use "
            "estimator='close'."
        )


def realized_features(px: pd.DataFrame, cfg: RVConfig | None = None) -> pd.DataFrame:
    """Monthly feature frame from daily prices.

    ``px`` needs a DatetimeIndex and a ``close`` column; ``open``/``high``/
    ``low`` are required only for range-based estimators. Features are sampled
    at month end, so each row uses only information available within that
    month -- no look-ahead.
    """
    cfg = cfg or RVConfig()
    px = px.sort_index()
    ret = _daily_returns(px)

    daily = pd.DataFrame(index=px.index)
    for w in cfg.windows:
        daily[f"rv{w}"] = _rv(px, ret, w, cfg)

    # leverage / asymmetry: share of the trailing quarter's realized variance
    # contributed by down days. ~0.5 in a symmetric market, higher in selloffs.
    neg = (ret.where(ret < 0, 0.0) ** 2).rolling(66, min_periods=33).sum()
    tot = (ret**2).rolling(66, min_periods=33).sum()
    daily["downside"] = (neg / tot.replace(0.0, np.nan)).clip(0.0, 1.0)

    # tail severity: worst peak-to-trough within the trailing quarter. Captures
    # the jump component that a variance measure smooths over.
    roll_max = px["close"].astype(float).rolling(66, min_periods=33).max()
    daily["maxdd"] = (1.0 - px["close"].astype(float) / roll_max).clip(lower=0.0)

    counts = ret.notna().resample("ME").sum()
    monthly = daily.resample("ME").last()
    monthly = monthly[counts.reindex(monthly.index).fillna(0) >= cfg.min_days_per_month]

    out = pd.DataFrame(index=monthly.index)
    for w in cfg.windows:
        out[f"log_rv{w}"] = np.log(monthly[f"rv{w}"].clip(lower=1e-6))
    out["downside"] = monthly["downside"]
    out["log_maxdd"] = np.log1p(monthly["maxdd"])
    out.index.name = "date"
    return out.dropna()


# --------------------------------------------------------------------------
# estimation
# --------------------------------------------------------------------------


@dataclass
class BackcastFit:
    spec: BackcastSpec
    coef: np.ndarray  # [intercept, *FEATURES]
    se_hac: np.ndarray
    tstat_hac: np.ndarray
    r2: float
    resid: pd.Series
    resid_sigma: float
    n_obs: int
    overlap: tuple[str, str]
    fitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def predict(self, X: pd.DataFrame) -> pd.Series:
        design = _design(X)
        return pd.Series(design @ self.coef, index=X.index, name="log_vix_hat")

    def to_dict(self) -> dict:
        d = asdict(self.spec)
        d.update(
            {
                "coef": {k: float(v) for k, v in zip(("const",) + FEATURES, self.coef)},
                "se_hac": {k: float(v) for k, v in zip(("const",) + FEATURES, self.se_hac)},
                "tstat_hac": {
                    k: float(v) for k, v in zip(("const",) + FEATURES, self.tstat_hac)
                },
                "r2": float(self.r2),
                "resid_sigma": float(self.resid_sigma),
                "n_obs": int(self.n_obs),
                "overlap": list(self.overlap),
                "fitted_at": self.fitted_at,
            }
        )
        return d


def _design(X: pd.DataFrame) -> np.ndarray:
    missing = [c for c in FEATURES if c not in X.columns]
    if missing:
        raise ValueError(f"feature frame missing columns: {missing}")
    return np.column_stack([np.ones(len(X)), *(X[c].to_numpy(float) for c in FEATURES)])


def _newey_west(design: np.ndarray, resid: np.ndarray, lags: int) -> np.ndarray:
    n, k = design.shape
    xtx_inv = np.linalg.pinv(design.T @ design)
    u = design * resid[:, None]
    S = u.T @ u
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)  # Bartlett kernel
        G = u[lag:].T @ u[:-lag]
        S += w * (G + G.T)
    cov = xtx_inv @ S @ xtx_inv * n / max(n - k, 1)
    return np.sqrt(np.clip(np.diag(cov), 0.0, None))


def fit(
    features: pd.DataFrame,
    vix: pd.Series,
    spec: BackcastSpec | None = None,
) -> BackcastFit:
    """Estimate the mapping on the observed overlap.

    ``vix`` is a monthly series of the implied-vol index in points, indexed by
    month end. Only months present in BOTH inputs and inside the spec's
    overlap window are used.
    """
    spec = spec or BackcastSpec()
    y_all = np.log(vix.astype(float).clip(lower=1e-6))
    idx = features.index.intersection(y_all.index)
    if spec.overlap_start:
        idx = idx[idx >= pd.Timestamp(spec.overlap_start)]
    if spec.overlap_end:
        idx = idx[idx <= pd.Timestamp(spec.overlap_end)]
    if len(idx) < 60:
        raise ValueError(f"overlap too short to fit: {len(idx)} months (need >= 60)")

    X, y = features.loc[idx], y_all.loc[idx].to_numpy(float)
    design = _design(X)
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    se = _newey_west(design, resid, spec.hac_lags)
    ss_res, ss_tot = float(resid @ resid), float(((y - y.mean()) ** 2).sum())

    return BackcastFit(
        spec=spec,
        coef=coef,
        se_hac=se,
        tstat_hac=np.divide(coef, np.where(se > 0, se, np.nan)),
        r2=1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        resid=pd.Series(resid, index=idx, name="resid"),
        resid_sigma=float(np.std(resid, ddof=len(coef))),
        n_obs=len(idx),
        overlap=(str(idx.min().date()), str(idx.max().date())),
    )


# --------------------------------------------------------------------------
# validation -- the part that decides whether this is usable
# --------------------------------------------------------------------------


@dataclass
class ValidationReport:
    oos_split: str
    oos_rmse_log: float
    oos_bias_log: float
    calm_bias_log: float
    stress_bias_log: float
    stress_ratio: float
    peak_errors: dict[str, dict[str, float]]
    vol_of_vol_ratio_mean: float
    vol_of_vol_ratio_ensemble: float
    coverage_80: float
    walkforward_rmse_log: float
    passes: dict[str, bool]

    @property
    def ok(self) -> bool:
        return all(self.passes.values())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


#: Acceptance thresholds. These are DEFAULTS for exploratory work. If this
#: backcast is to enter a sealed panel, the thresholds must be registered in
#: ``pre-registration.yaml`` BEFORE the fit is run, not chosen after seeing
#: these numbers.
DEFAULT_THRESHOLDS = {
    "oos_rmse_log": 0.30,       # ~30% proportional error on the level
    "abs_stress_bias_log": 0.20,  # systematic miss in the top RV decile
    "min_stress_ratio": 0.70,   # predicted vs actual mean level in stress
    "min_vol_of_vol_ratio": 0.80,  # ensemble must retain vol-of-vol
    "coverage_80_tol": 0.10,
}


def validate(
    features: pd.DataFrame,
    vix: pd.Series,
    spec: BackcastSpec | None = None,
    split: str = "2007-12-31",
    thresholds: dict | None = None,
    seed: int = 0,
) -> ValidationReport:
    """Out-of-sample and stress-conditional checks.

    The split defaults to end-2007 so the test period contains both the GFC and
    the COVID shock -- the two episodes most like the pre-1990 tail this
    backcast exists to reach. A model that fits calm markets and misses those
    is worse than no extension, because it would furnish the bootstrap with a
    placid 1930s.
    """
    spec = spec or BackcastSpec()
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    rng = np.random.default_rng(seed)

    train_spec = BackcastSpec(**{**asdict(spec), "overlap_end": split, "rv": spec.rv})
    f_tr = fit(features, vix, train_spec)

    idx_te = features.index[features.index > pd.Timestamp(split)]
    idx_te = idx_te.intersection(vix.index)
    if len(idx_te) < 24:
        raise ValueError("out-of-sample window shorter than 24 months")

    y_te = np.log(vix.loc[idx_te].astype(float).clip(lower=1e-6)).to_numpy()
    yhat = f_tr.predict(features.loc[idx_te]).to_numpy()
    err = y_te - yhat

    rv = features.loc[idx_te, "log_rv22"]
    stress = rv >= rv.quantile(0.90)
    calm = rv <= rv.quantile(0.50)

    peaks: dict[str, dict[str, float]] = {}
    for label, window in (
        ("gfc_2008_09_to_2009_03", ("2008-09-01", "2009-03-31")),
        ("covid_2020", ("2020-02-01", "2020-05-31")),
    ):
        m = (idx_te >= pd.Timestamp(window[0])) & (idx_te <= pd.Timestamp(window[1]))
        if m.any():
            peaks[label] = {
                "actual_peak": float(np.exp(y_te[m].max())),
                "predicted_peak": float(np.exp(yhat[m].max())),
                "ratio": float(np.exp(yhat[m].max() - y_te[m].max())),
            }

    # vol-of-vol: the conditional mean is smooth by construction; the ensemble
    # must put the dispersion back.
    actual_vov = float(np.std(np.diff(y_te)))
    mean_vov = float(np.std(np.diff(yhat)))
    ens = _residual_ensemble(f_tr, len(idx_te), n_draws=200, rng=rng)
    ens_vov = float(np.mean([np.std(np.diff(yhat + e)) for e in ens]))

    lo, hi = np.quantile(ens, [0.10, 0.90], axis=0)
    coverage = float(np.mean((err >= lo) & (err <= hi)))

    wf_errs: list[float] = []
    for cut in pd.date_range(split, features.index.max(), freq="24ME")[:-1]:
        try:
            fw = fit(features, vix, BackcastSpec(**{**asdict(spec), "overlap_end": str(cut.date()), "rv": spec.rv}))
        except ValueError:
            continue
        nxt = features.index[
            (features.index > cut) & (features.index <= cut + pd.DateOffset(months=24))
        ].intersection(vix.index)
        if len(nxt) == 0:
            continue
        e = np.log(vix.loc[nxt].astype(float)).to_numpy() - fw.predict(features.loc[nxt]).to_numpy()
        wf_errs.extend(e.tolist())

    rmse = float(np.sqrt(np.mean(err**2)))
    stress_bias = float(err[stress.to_numpy()].mean()) if stress.any() else float("nan")
    stress_ratio = (
        float(np.exp(yhat[stress.to_numpy()].mean() - y_te[stress.to_numpy()].mean()))
        if stress.any()
        else float("nan")
    )
    vov_mean_ratio = mean_vov / actual_vov if actual_vov > 0 else float("nan")
    vov_ens_ratio = ens_vov / actual_vov if actual_vov > 0 else float("nan")

    return ValidationReport(
        oos_split=split,
        oos_rmse_log=rmse,
        oos_bias_log=float(err.mean()),
        calm_bias_log=float(err[calm.to_numpy()].mean()) if calm.any() else float("nan"),
        stress_bias_log=stress_bias,
        stress_ratio=stress_ratio,
        peak_errors=peaks,
        vol_of_vol_ratio_mean=vov_mean_ratio,
        vol_of_vol_ratio_ensemble=vov_ens_ratio,
        coverage_80=coverage,
        walkforward_rmse_log=float(np.sqrt(np.mean(np.square(wf_errs)))) if wf_errs else float("nan"),
        passes={
            "oos_rmse": rmse <= thr["oos_rmse_log"],
            "stress_bias": abs(stress_bias) <= thr["abs_stress_bias_log"],
            "stress_level": stress_ratio >= thr["min_stress_ratio"],
            "ensemble_vol_of_vol": vov_ens_ratio >= thr["min_vol_of_vol_ratio"],
            "interval_coverage": abs(coverage - 0.80) <= thr["coverage_80_tol"],
        },
    )


# --------------------------------------------------------------------------
# backcast
# --------------------------------------------------------------------------


def _residual_ensemble(
    f: BackcastFit, n_months: int, n_draws: int, rng: np.random.Generator
) -> np.ndarray:
    """Block-resampled residual paths, shape ``(n_draws, n_months)``.

    Blocks preserve the residuals' own persistence and their tendency to
    cluster in stressed periods -- an iid draw would flatten both.
    """
    r = f.resid.to_numpy(float)
    block = max(1, min(f.spec.residual_block_months, len(r)))
    n_blocks = int(np.ceil(n_months / block))
    starts = rng.integers(0, max(1, len(r) - block + 1), size=(n_draws, n_blocks))
    out = np.empty((n_draws, n_blocks * block))
    for i in range(n_draws):
        out[i] = np.concatenate([r[s : s + block] for s in starts[i]])
    return out[:, :n_months]


def backcast(
    f: BackcastFit,
    features: pd.DataFrame,
    observed: pd.Series,
    n_draws: int = 200,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Extend ``observed`` backward over the months features cover.

    Returns ``(frame, ensemble)``:

    * ``frame`` is splice-compatible -- ``date, value, is_proxy, rule_id`` --
      where ``value`` is the ensemble MEDIAN on backcast months and the
      observed value on observed months. An observed month is never
      overwritten.
    * ``ensemble`` is ``(n_draws, n_backcast_months)`` in LEVEL space, or
      ``None`` when ``n_draws == 0``. Downstream tail metrics should consume
      the ensemble, not the median column.
    """
    rng = np.random.default_rng(seed)
    obs = observed.astype(float).dropna()
    pre = features.index[features.index < obs.index.min()]
    if len(pre) == 0:
        raise ValueError("nothing to backcast: features start after the observed series")

    mu = f.predict(features.loc[pre])
    ens_log = None
    if n_draws > 0:
        ens_log = mu.to_numpy()[None, :] + _residual_ensemble(f, len(pre), n_draws, rng)
        value = np.exp(np.median(ens_log, axis=0))
    else:
        value = np.exp(mu.to_numpy())

    proxy = pd.DataFrame(
        {"date": pre, "value": value, "is_proxy": True, "rule_id": f.spec.rule_id}
    )
    actual = pd.DataFrame(
        {
            "date": obs.index,
            "value": obs.to_numpy(float),
            "is_proxy": False,
            "rule_id": None,
        }
    )
    frame = pd.concat([proxy, actual], ignore_index=True).sort_values("date")
    frame = frame.reset_index(drop=True)

    ensemble = None
    if ens_log is not None:
        ensemble = pd.DataFrame(np.exp(ens_log), columns=pre)
    return frame, ensemble


def write_provenance(f: BackcastFit, report: ValidationReport, path: str) -> None:
    """Emit the fit and its validation as one auditable artifact."""
    payload = {
        "artifact": "equity_vol_backcast",
        "fit": f.to_dict(),
        "validation": report.to_dict(),
        "caveat": (
            "Backcast months are MODEL OUTPUT, not observation. The mapping is "
            "estimated on 1990+ and its behaviour in pre-1990 tail episodes is "
            "extrapolation, not evidence. Any metric computed over the extended "
            "span must consume the ensemble, and any battery result over that "
            "span must disclose the proxy share."
        ),
    }
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
