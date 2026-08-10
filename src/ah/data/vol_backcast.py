"""Backcast ``equity_vol`` below 1986 from realized volatility (WP-DATA-VOLEXT stage 2).

Why this exists
---------------
Stage 1 (``ah.data.vol_extend``) extends ``equity_vol`` to 1986-01 on
*observation* (VXO). Below 1986 no implied-vol index exists anywhere; the only
honest instrument is a model mapping realized volatility -- computable from
daily index returns back to 1926-07 -- into implied-vol space. This module is
that model. Its specification, thresholds and out-of-scope list are the task
file ``Instructions/TASK-vol-backcast-claude-code.md``; the owner decisions
that bind it (daily source = the French daily market factor; ensemble storage
design A; registered thresholds) are
``docs/superpowers/specs/2026-08-09-volext-decisions.md``.

Discipline, following ``ah.data.splice`` and ``ah.data.vol_extend``
-------------------------------------------------------------------
Every backcast row carries ``is_proxy=True`` and ``rule_id``; a backcast NEVER
overwrites an observed month; features are month-end samples of trailing
windows only (no look-ahead, tested by truncation); the acceptance thresholds
are REGISTERED in ``governance/amendment-log.yaml`` before the registered fit
runs -- ``scripts/volext_backcast_fit.py`` refuses to run without the entry
(the RFR-77 discipline, enforced mechanically).

THE FAILURE MODE THIS MODULE IS BUILT TO AVOID
----------------------------------------------
A regression's fitted values are SMOOTHER THAN THE TRUTH by construction: the
conditional mean discards the residual variance. Splicing a point backcast
would give the pre-1986 era an artificially calm volatility-of-volatility,
suppressing exactly the tail behaviour the extension exists to recover.
:func:`backcast` therefore returns an ENSEMBLE: residuals resampled in
12-month blocks (preserving their persistence and their tendency to cluster
in stress), added back in log space. ``n_draws=0`` gives the bare conditional
mean, for diagnostics only -- never for a panel that feeds a tail metric.

Specification (the reference sketch's ``downside`` term is DROPPED: t = -1.28
on the real fit; an unsupported regressor does not enter a registered spec)::

    log VIX_t = a + b1 log RV_t(22) + b2 log RV_t(66) + b3 log RV_t(252)
              + g log(1 + maxdd_t) + e_t

OLS with Newey-West HAC standard errors (Bartlett kernel, 12 lags):
overlapping trailing windows induce strong residual autocorrelation, and
plain OLS standard errors are badly understated.

References: Corsi (2009) JFEc 7(2) [HAR]; Newey & West (1987) Econometrica
55(3); Parkinson (1980) / Garman & Klass (1980) J. Business 53(1) [range
estimators, refused on degenerate OHLC]; Christensen & Prabhala (1998) JFE
50(2); Carr & Wu (2009) RFS 22(3); Bekaert & Hoerova (2014) J. Econometrics
183(2).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "FEATURES",
    "PINNED_DRAW_PATH",
    "PINNED_DRAW_SEED",
    "PINNED_DRAW_SPAN",
    "PINNED_PROVENANCE_SHA256",
    "REGISTERED_OBJECT",
    "REGISTERED_THRESHOLDS",
    "RULE_ID",
    "TRADING_DAYS",
    "BackcastFit",
    "BackcastSpec",
    "HeldOutReport",
    "RVConfig",
    "ValidationReport",
    "backcast",
    "close_from_returns",
    "fit",
    "fit_from_provenance",
    "paths",
    "pinned_draw_series",
    "realized_features",
    "validate",
    "vxo_heldout",
    "write_provenance",
]

TRADING_DAYS = 252

RULE_ID = "PROXY-EQUITY-VOL-HAR-V1"

#: The registered object name the ratified amendment carries; the fit script
#: matches it in ``governance/amendment-log.yaml`` before running.
REGISTERED_OBJECT = "equity_vol_backcast"

#: The owner-ratified acceptance thresholds (decisions doc D4, drafted in
#: ``governance/proposed/PROPOSED-AM-volext-thresholds.md``). These are the
#: REGISTERED values -- not the reference sketch's exploratory defaults, which
#: were chosen after seeing results and are deliberately not carried over.
REGISTERED_THRESHOLDS: dict[str, float] = {
    "vxo_heldout_corr_log_min": 0.90,
    "oct1987_peak_ratio_min": 0.75,
    "oct1987_peak_ratio_max": 1.35,
    "stress_bias_log_abs_max": 0.20,
    "ensemble_vol_of_vol_ratio_min": 0.85,
    "coverage_80_tolerance": 0.10,
}

#: Feature columns, in the order they enter the design matrix. Frozen: the
#: coefficient vector in a stored fit is positional.
FEATURES: tuple[str, ...] = ("log_rv22", "log_rv66", "log_rv252", "log_maxdd")

# --------------------------------------------------------------------------- #
# the pinned panel draw (AM-2026-08-09-002)
# --------------------------------------------------------------------------- #

#: sha256 of ``artifacts/volext/equity-vol-backcast-provenance.json`` as pinned
#: in AM-2026-08-09-002's payload. The materialization script refuses to run
#: against any other provenance, and :func:`pinned_draw_series` refuses to
#: serve a draw whose recorded provenance sha differs.
PINNED_PROVENANCE_SHA256 = "f0535582c061cc60ea8605aa9085d457b27dbc12af5e4718aed557146284fc92"

#: The ONE ensemble draw the extended panel consumes (ratification design
#: ruling R1): a single seed, drawn once, materialized to
#: :data:`PINNED_DRAW_PATH` by ``scripts/volext_materialize_draw.py`` and never
#: regenerated at read time. Tail-bearing DIAGNOSTICS still regenerate the full
#: ensemble from the provenance fit (owner decision D2); the panel itself is
#: one path so that every consumer sees the same history.
PINNED_DRAW_SEED = 20260809

#: Month span of the pinned draw, inclusive, ``YYYY-MM``: from the ratified
#: extended-span start (AM-2026-08-09-002) to the last month below the stage-1
#: VXO extension.
PINNED_DRAW_SPAN: tuple[str, str] = ("1953-04", "1985-12")

#: The materialized draw, committed as package data so the read path needs no
#: repository-root discovery and the seal can hash it as a file.
PINNED_DRAW_PATH = Path(__file__).parent / "equity_vol_pinned_draw.json"


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RVConfig:
    """How realized volatility is measured from daily prices."""

    #: "close" (close-to-close), "parkinson", or "garman_klass". Range-based
    #: estimators are more efficient per observation but need trustworthy
    #: intraday high/low; the S&P composite carries high == low == close
    #: before 1962, and the French daily factor (owner decision D1) has no
    #: OHLC at all -- ``close`` is the only honest choice here, and
    #: :func:`_require_ohlc` REFUSES a range estimator on degenerate inputs
    #: rather than silently returning nonsense.
    estimator: str = "close"
    #: Trailing windows in trading days, matched to the RV features.
    windows: tuple[int, ...] = (22, 66, 252)
    #: Minimum non-null daily observations in a month for it to be usable.
    min_days_per_month: int = 15


@dataclass(frozen=True)
class BackcastSpec:
    """The rule, in the sense of ``ah.data.splice.ProxyRule``."""

    rule_id: str = RULE_ID
    target: str = "fred.VIX"
    donor: str = "french.mkt_rf_d + french.rf_d"
    overlap_start: str = "1990-01-01"
    overlap_end: str | None = None
    rv: RVConfig = RVConfig()
    #: Newey-West lag truncation, in months: the longest trailing window
    #: (252 trading days ~ 12 months) is the horizon over which overlapping
    #: windows mechanically induce residual correlation.
    hac_lags: int = 12
    #: Block length in months for residual resampling.
    residual_block_months: int = 12
    #: Minimum overlap months to fit at all.
    min_overlap_months: int = 60


# --------------------------------------------------------------------------- #
# feature construction
# --------------------------------------------------------------------------- #


def close_from_returns(returns: pd.Series) -> pd.DataFrame:
    """A synthetic close-level frame (base 1.0) from daily simple returns.

    The French daily factor is returns-only; cumulating them gives the price
    level path that ``maxdd`` needs. The base is arbitrary -- both RV and
    drawdown are scale-free.
    """
    r = returns.astype(float).dropna().sort_index()
    if not r.index.is_unique:
        raise ValueError("duplicate dates in returns")
    return pd.DataFrame({"close": (1.0 + r).cumprod()}, index=r.index)


def _require_ohlc(px: pd.DataFrame) -> None:
    missing = {"open", "high", "low"} - set(px.columns)
    if missing:
        raise ValueError(f"range estimator needs OHLC; missing {sorted(missing)}")
    degenerate = float((px["high"].astype(float) <= px["low"].astype(float)).mean())
    if degenerate > 0.02:
        raise ValueError(
            f"{degenerate:.1%} of rows have high <= low -- this OHLC is synthetic "
            "(common for pre-1962 index history). Use estimator='close'."
        )


def _rv(px: pd.DataFrame, ret: pd.Series, window: int, cfg: RVConfig) -> pd.Series:
    """Annualized realized vol over a trailing window, in points (x100)."""
    min_periods = max(5, window // 2)
    if cfg.estimator == "close":
        return ret.rolling(window, min_periods=min_periods).std() * np.sqrt(TRADING_DAYS) * 100.0
    if cfg.estimator == "parkinson":
        _require_ohlc(px)
        hl = np.log(px["high"].astype(float) / px["low"].astype(float)) ** 2
        var = hl.rolling(window, min_periods=min_periods).mean() / (4.0 * np.log(2.0))
        return np.sqrt(var * TRADING_DAYS) * 100.0
    if cfg.estimator == "garman_klass":
        _require_ohlc(px)
        hi, lo = np.log(px["high"].astype(float)), np.log(px["low"].astype(float))
        op, cl = np.log(px["open"].astype(float)), np.log(px["close"].astype(float))
        term = 0.5 * (hi - lo) ** 2 - (2.0 * np.log(2.0) - 1.0) * (cl - op) ** 2
        var = term.rolling(window, min_periods=min_periods).mean()
        return np.sqrt(var.clip(lower=1e-12) * TRADING_DAYS) * 100.0
    raise ValueError(f"unknown rv estimator: {cfg.estimator!r}")


def realized_features(px: pd.DataFrame, cfg: RVConfig | None = None) -> pd.DataFrame:
    """Monthly feature frame from daily prices.

    ``px`` needs a DatetimeIndex and a ``close`` column (``open``/``high``/
    ``low`` only for range estimators). Every feature is a trailing-window
    statistic sampled at month end, so a row uses only information available
    by that month's close -- truncating the daily input never changes an
    earlier monthly row, and a test pins that.
    """
    cfg = cfg or RVConfig()
    px = px.sort_index()
    close = px["close"].astype(float)
    ret = np.log(close).diff()

    daily = pd.DataFrame(index=px.index)
    for w in cfg.windows:
        daily[f"rv{w}"] = _rv(px, ret, w, cfg)

    # tail severity: worst peak-to-trough within the trailing quarter -- the
    # jump/leverage component a symmetric variance measure smooths over.
    roll_max = close.rolling(66, min_periods=33).max()
    daily["maxdd"] = (1.0 - close / roll_max).clip(lower=0.0)

    counts = ret.notna().resample("ME").sum()
    monthly = daily.resample("ME").last()
    monthly = monthly[counts.reindex(monthly.index).fillna(0) >= cfg.min_days_per_month]

    out = pd.DataFrame(index=monthly.index)
    for w in cfg.windows:
        out[f"log_rv{w}"] = np.log(monthly[f"rv{w}"].clip(lower=1e-6))
    out["log_maxdd"] = np.log1p(monthly["maxdd"])
    out.index.name = "date"
    return out.dropna()


# --------------------------------------------------------------------------- #
# estimation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BackcastFit:
    spec: BackcastSpec
    coef: tuple[float, ...]  # (intercept, *FEATURES)
    se_hac: tuple[float, ...]
    se_ols: tuple[float, ...]
    tstat_hac: tuple[float, ...]
    r2: float
    resid: pd.Series
    resid_sigma: float
    n_obs: int
    overlap: tuple[str, str]

    def predict(self, x: pd.DataFrame) -> pd.Series:
        design = _design(x)
        return pd.Series(design @ np.asarray(self.coef), index=x.index, name="log_vix_hat")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self.spec)
        names = ("const", *FEATURES)
        d.update(
            {
                "rule_id": self.spec.rule_id,
                "coef": dict(zip(names, self.coef, strict=True)),
                "se_hac": dict(zip(names, self.se_hac, strict=True)),
                "se_ols": dict(zip(names, self.se_ols, strict=True)),
                "tstat_hac": dict(zip(names, self.tstat_hac, strict=True)),
                "r2": self.r2,
                "resid_sigma": self.resid_sigma,
                "n_obs": self.n_obs,
                "overlap": list(self.overlap),
            }
        )
        return d


def _design(x: pd.DataFrame) -> np.ndarray:
    missing = [c for c in FEATURES if c not in x.columns]
    if missing:
        raise ValueError(f"feature frame missing columns: {missing}")
    return np.column_stack([np.ones(len(x)), *(x[c].to_numpy(float) for c in FEATURES)])


def _ols_se(design: np.ndarray, resid: np.ndarray) -> np.ndarray:
    n, k = design.shape
    sigma2 = float(resid @ resid) / max(n - k, 1)
    cov = np.linalg.pinv(design.T @ design) * sigma2
    return np.sqrt(np.clip(np.diag(cov), 0.0, None))


def _newey_west(design: np.ndarray, resid: np.ndarray, lags: int) -> np.ndarray:
    n, k = design.shape
    xtx_inv = np.linalg.pinv(design.T @ design)
    u = design * resid[:, None]
    s = u.T @ u
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)  # Bartlett kernel
        g = u[lag:].T @ u[:-lag]
        s += w * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv * n / max(n - k, 1)
    return np.sqrt(np.clip(np.diag(cov), 0.0, None))


def fit(features: pd.DataFrame, vix: pd.Series, spec: BackcastSpec | None = None) -> BackcastFit:
    """Estimate the mapping on the observed overlap.

    ``vix`` is a monthly implied-vol series in points indexed by month end.
    Only months in BOTH inputs and inside the spec's overlap window are used;
    fewer than ``spec.min_overlap_months`` of them is a refusal.
    """
    spec = spec or BackcastSpec()
    y_all = np.log(vix.astype(float).clip(lower=1e-6))
    idx = features.index.intersection(y_all.index)
    idx = idx[idx >= pd.Timestamp(spec.overlap_start)]
    if spec.overlap_end is not None:
        idx = idx[idx <= pd.Timestamp(spec.overlap_end)]
    if len(idx) < spec.min_overlap_months:
        raise ValueError(
            f"overlap too short to fit: {len(idx)} months (need >= {spec.min_overlap_months})"
        )

    x, y = features.loc[idx], y_all.loc[idx].to_numpy(float)
    design = _design(x)
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    se_hac = _newey_west(design, resid, spec.hac_lags)
    se_ols = _ols_se(design, resid)
    ss_res, ss_tot = float(resid @ resid), float(((y - y.mean()) ** 2).sum())

    return BackcastFit(
        spec=spec,
        coef=tuple(float(c) for c in coef),
        se_hac=tuple(float(s) for s in se_hac),
        se_ols=tuple(float(s) for s in se_ols),
        tstat_hac=tuple(
            float(c / s) if s > 0 else float("nan") for c, s in zip(coef, se_hac, strict=True)
        ),
        r2=1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        resid=pd.Series(resid, index=idx, name="resid"),
        resid_sigma=float(np.std(resid, ddof=len(coef))),
        n_obs=len(idx),
        overlap=(str(idx.min().date()), str(idx.max().date())),
    )


# --------------------------------------------------------------------------- #
# the ensemble -- the requirement that is easiest to get wrong
# --------------------------------------------------------------------------- #


def paths(f: BackcastFit, n_months: int, n_draws: int, seed: int) -> np.ndarray:
    """Block-resampled residual paths, shape ``(n_draws, n_months)``, LOG space.

    Deterministic in ``(fit, seed)`` -- this is the consumer API of owner
    decision D2: any tail-bearing reader regenerates the ensemble from the
    provenance artifact's fit and a seed, bit-identically. Blocks preserve the
    residuals' own persistence and their clustering in stress; an iid draw
    would flatten both.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
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
    """Extend ``observed`` backward over the months ``features`` cover.

    Returns ``(frame, ensemble)``: ``frame`` is splice-shaped (``date, value,
    is_proxy, rule_id``) with the ensemble MEDIAN on backcast months and the
    observed value on observed months -- an observed month is never
    overwritten; ``ensemble`` is ``(n_draws, n_backcast_months)`` in LEVEL
    space, ``None`` when ``n_draws == 0``. Downstream tail metrics must
    consume the ensemble, not the median column (owner decision D2).
    """
    obs = observed.astype(float).dropna()
    pre = features.index[features.index < obs.index.min()]
    if len(pre) == 0:
        raise ValueError("nothing to backcast: features start after the observed series")

    mu = f.predict(features.loc[pre]).to_numpy()
    ens_log: np.ndarray | None = None
    if n_draws > 0:
        ens_log = mu[None, :] + paths(f, len(pre), n_draws, seed)
        value = np.exp(np.median(ens_log, axis=0))
    else:
        value = np.exp(mu)

    proxy = pd.DataFrame({"date": pre, "value": value, "is_proxy": True})
    actual = pd.DataFrame({"date": obs.index, "value": obs.to_numpy(float), "is_proxy": False})
    frame = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    frame["rule_id"] = f.spec.rule_id
    ensemble = pd.DataFrame(np.exp(ens_log), columns=pre) if ens_log is not None else None
    return frame, ensemble


# --------------------------------------------------------------------------- #
# validation -- the part that decides whether this is usable
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def validate(
    features: pd.DataFrame,
    vix: pd.Series,
    spec: BackcastSpec | None = None,
    split: str = "2007-12-31",
    thresholds: dict[str, float] | None = None,
    seed: int = 0,
) -> ValidationReport:
    """Out-of-sample and stress-conditional checks against the REGISTERED thresholds.

    The split defaults to end-2007 so the test period contains the GFC and the
    COVID shock -- the episodes most like the pre-1990 tail this backcast
    exists to reach. A model that fits calm markets and misses those is worse
    than no extension, because it would furnish the bootstrap with a placid
    1930s. Top-RV-decile bias is therefore reported separately and gates.
    """
    spec = spec or BackcastSpec()
    thr = {**REGISTERED_THRESHOLDS, **(thresholds or {})}

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
    stress = (rv >= rv.quantile(0.90)).to_numpy()
    calm = (rv <= rv.quantile(0.50)).to_numpy()

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
    ens = paths(f_tr, len(idx_te), n_draws=200, seed=seed)
    ens_vov = float(np.mean([np.std(np.diff(yhat + e)) for e in ens]))

    lo, hi = np.quantile(ens, [0.10, 0.90], axis=0)
    coverage = float(np.mean((err >= lo) & (err <= hi)))

    wf_errs: list[float] = []
    for cut in pd.date_range(split, features.index.max(), freq="24ME")[:-1]:
        try:
            fw = fit(
                features,
                vix,
                BackcastSpec(**{**asdict(spec), "overlap_end": str(cut.date()), "rv": spec.rv}),
            )
        except ValueError:
            continue
        nxt = features.index[
            (features.index > cut) & (features.index <= cut + pd.DateOffset(months=24))
        ].intersection(vix.index)
        if len(nxt) == 0:
            continue
        e = np.log(vix.loc[nxt].astype(float)).to_numpy() - fw.predict(features.loc[nxt]).to_numpy()
        wf_errs.extend(e.tolist())

    stress_bias = float(err[stress].mean()) if stress.any() else float("nan")
    vov_mean_ratio = mean_vov / actual_vov if actual_vov > 0 else float("nan")
    vov_ens_ratio = ens_vov / actual_vov if actual_vov > 0 else float("nan")

    return ValidationReport(
        oos_split=split,
        oos_rmse_log=float(np.sqrt(np.mean(err**2))),
        oos_bias_log=float(err.mean()),
        calm_bias_log=float(err[calm].mean()) if calm.any() else float("nan"),
        stress_bias_log=stress_bias,
        stress_ratio=(
            float(np.exp(yhat[stress].mean() - y_te[stress].mean()))
            if stress.any()
            else float("nan")
        ),
        peak_errors=peaks,
        vol_of_vol_ratio_mean=vov_mean_ratio,
        vol_of_vol_ratio_ensemble=vov_ens_ratio,
        coverage_80=coverage,
        walkforward_rmse_log=(
            float(np.sqrt(np.mean(np.square(wf_errs)))) if wf_errs else float("nan")
        ),
        passes={
            "stress_bias": abs(stress_bias) <= thr["stress_bias_log_abs_max"],
            "ensemble_vol_of_vol": vov_ens_ratio >= thr["ensemble_vol_of_vol_ratio_min"],
            "interval_coverage": abs(coverage - 0.80) <= thr["coverage_80_tolerance"],
        },
    )


@dataclass(frozen=True)
class HeldOutReport:
    """The 1986-89 VXO check: a TRUE held-out era.

    VXO is observed 1986-89 and the model is fitted on 1990+ only. VXO months
    are mapped to VIX-equivalents through the STAGE-1 log-log fit (the repo's
    own mapping -- the reference sketch's 51.6 for Oct-1987 came from its
    exploratory mapping; ours puts the month at its own value and the ratio
    thresholds are mapping-relative).
    """

    corr_log: float
    rmse_log: float
    n_months: int
    oct1987_actual_vix_equiv: float
    oct1987_predicted: float
    oct1987_ratio: float
    passes: dict[str, bool]

    @property
    def ok(self) -> bool:
        return all(self.passes.values())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def vxo_heldout(
    f: BackcastFit,
    features: pd.DataFrame,
    vxo_vix_equiv: pd.Series,
    thresholds: dict[str, float] | None = None,
) -> HeldOutReport:
    """Score the backcast on 1986-89 against VXO-derived VIX-equivalents.

    ``vxo_vix_equiv`` is the observed VXO series already mapped through the
    stage-1 ``vol_extend`` fit, restricted by this function to months strictly
    before the model's overlap start (so the check cannot leak fitted months).
    """
    thr = {**REGISTERED_THRESHOLDS, **(thresholds or {})}
    equiv = vxo_vix_equiv.astype(float).dropna()
    idx = features.index.intersection(equiv.index)
    idx = idx[idx < pd.Timestamp(f.spec.overlap_start)]
    if len(idx) < 24:
        raise ValueError(f"held-out era too short: {len(idx)} months (need >= 24)")

    y = np.log(equiv.loc[idx].to_numpy(float))
    yhat = f.predict(features.loc[idx]).to_numpy()
    corr = float(np.corrcoef(y, yhat)[0, 1])
    rmse = float(np.sqrt(np.mean((y - yhat) ** 2)))

    oct87 = idx[idx.strftime("%Y-%m") == "1987-10"]
    if len(oct87) == 0:
        raise ValueError("held-out era does not contain 1987-10")
    actual = float(equiv.loc[oct87[0]])
    predicted = float(np.exp(f.predict(features.loc[oct87]).iloc[0]))
    ratio = predicted / actual

    return HeldOutReport(
        corr_log=corr,
        rmse_log=rmse,
        n_months=len(idx),
        oct1987_actual_vix_equiv=actual,
        oct1987_predicted=predicted,
        oct1987_ratio=ratio,
        passes={
            "vxo_heldout_corr": corr >= thr["vxo_heldout_corr_log_min"],
            "oct1987_peak": thr["oct1987_peak_ratio_min"] <= ratio <= thr["oct1987_peak_ratio_max"],
        },
    )


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #


def write_provenance(
    f: BackcastFit,
    validation: ValidationReport,
    heldout: HeldOutReport,
    path: Path,
    *,
    fitted_at: str,
    amendment_id: str,
) -> None:
    """Emit the fit and its full validation as one auditable artifact.

    ``fitted_at`` and ``amendment_id`` are supplied by the caller -- this
    module never reads a clock (the repo's no-time-based-defaults invariant)
    and never asserts its own ratification.
    """
    payload = {
        "artifact": REGISTERED_OBJECT,
        "rule_id": f.spec.rule_id,
        "amendment_id": amendment_id,
        "fitted_at": fitted_at,
        "registered_thresholds": REGISTERED_THRESHOLDS,
        "fit": f.to_dict(),
        "residuals": {str(k.date()): float(v) for k, v in f.resid.items()},
        "validation": validation.to_dict(),
        "vxo_heldout": heldout.to_dict(),
        "caveat": (
            "Backcast months are MODEL OUTPUT, not observation. The mapping is "
            "estimated on 1990+ and its behaviour in pre-1986 tail episodes is "
            "extrapolation, not evidence. Any metric computed over the extended "
            "span must consume the ensemble (regenerate via ah.data.vol_backcast"
            ".paths from this artifact's fit and residuals -- owner decision D2), "
            "and any battery result over that span must disclose the proxy share. "
            "The stored median column is diagnostic/display only."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def fit_from_provenance(payload: dict[str, Any]) -> BackcastFit:
    """Rebuild the registered :class:`BackcastFit` from a provenance payload.

    The inverse of :func:`write_provenance` for the fields that determine
    numbers: spec, coefficients and the residual pool (:func:`paths` consumes
    only ``resid`` and ``spec.residual_block_months``;
    :meth:`BackcastFit.predict` only ``coef``). Standard errors and fit
    statistics are carried through for display faithfulness, not because any
    consumer re-judges them.
    """
    d = payload["fit"]
    spec = BackcastSpec(
        rule_id=d["rule_id"],
        target=d["target"],
        donor=d["donor"],
        overlap_start=d["overlap_start"],
        overlap_end=d["overlap_end"],
        rv=RVConfig(
            estimator=d["rv"]["estimator"],
            windows=tuple(d["rv"]["windows"]),
            min_days_per_month=d["rv"]["min_days_per_month"],
        ),
        hac_lags=d["hac_lags"],
        residual_block_months=d["residual_block_months"],
        min_overlap_months=d["min_overlap_months"],
    )
    names = ("const", *FEATURES)
    resid = pd.Series(
        {pd.Timestamp(k): float(v) for k, v in payload["residuals"].items()}, name="resid"
    ).sort_index()
    return BackcastFit(
        spec=spec,
        coef=tuple(float(d["coef"][n]) for n in names),
        se_hac=tuple(float(d["se_hac"][n]) for n in names),
        se_ols=tuple(float(d["se_ols"][n]) for n in names),
        tstat_hac=tuple(float(d["tstat_hac"][n]) for n in names),
        r2=float(d["r2"]),
        resid=resid,
        resid_sigma=float(d["resid_sigma"]),
        n_obs=int(d["n_obs"]),
        overlap=(d["overlap"][0], d["overlap"][1]),
    )


def pinned_draw_series(path: Path | None = None) -> pd.Series:
    """The materialized pinned draw as a month-START indexed level series.

    Loads :data:`PINNED_DRAW_PATH` (written once by
    ``scripts/volext_materialize_draw.py``), refuses a file whose recorded
    seed, span or provenance sha differs from the module's pinned constants,
    and refuses a gap in the monthly index. Month-start timestamps match the
    connector/vintage date convention the factor read surface joins against.
    """
    p = path or PINNED_DRAW_PATH
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("provenance_sha256") != PINNED_PROVENANCE_SHA256:
        raise ValueError(
            f"pinned draw at {p} records provenance sha {doc.get('provenance_sha256')!r}, "
            f"not the AM-2026-08-09-002 pin {PINNED_PROVENANCE_SHA256!r}"
        )
    if int(doc.get("seed", -1)) != PINNED_DRAW_SEED or doc.get("draw_index", -1) != 0:
        raise ValueError(f"pinned draw at {p} is not the seed-{PINNED_DRAW_SEED} draw 0")
    if tuple(doc.get("span", ())) != PINNED_DRAW_SPAN:
        raise ValueError(f"pinned draw at {p} spans {doc.get('span')}, not {PINNED_DRAW_SPAN}")
    s = pd.Series(
        {pd.Timestamp(f"{k}-01"): float(v) for k, v in doc["values"].items()},
        name="equity_vol_pinned",
    ).sort_index()
    expected = pd.date_range(f"{PINNED_DRAW_SPAN[0]}-01", f"{PINNED_DRAW_SPAN[1]}-01", freq="MS")
    if not s.index.equals(expected):
        raise ValueError(f"pinned draw at {p} has {len(s)} months; expected {len(expected)}")
    return s
