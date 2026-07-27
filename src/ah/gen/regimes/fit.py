"""WP2.6 fitting: labels, spells, covariates, NUTS, acceptance bands, sensitivity.

Data discipline (STEP2 SS6: leakage is the whole game):

- Every series is read through :meth:`ah.splits.DataAccess.train_val` -- the one
  sanctioned reference/normalization surface; holdout rows cannot reach the fit.
- Covariate standardization constants are computed HERE, on the fit span
  (train+validation), recorded in the artifact, and applied identically at
  simulation time.
- The historical slow-state covariates (credit gap, pi* - target) come from the
  WP2.5 posterior-mean smoothed path; the consumed climate artifact's canonical
  content SHA-256 is recorded in this artifact's metadata, so the L2 posterior
  names the exact L1 posterior it was conditioned on.

Label assembly mirrors :func:`ah.gen.bootstrap.regime_labels_for` -- same four
observable features (cpi_yoy, INDPRO growth_yoy, equity drawdown, USREC), same
refusal on a missing feature month, and the same sealed ``hy_oas`` gap: the
factor's entire licensed history is holdout, so ``hy_oas`` is NaN always, the
CRI high-yield disjunct is dead, and CRI rests on the drawdown disjunct alone.
It is re-implemented here (rather than imported) for one reason only: the
sensitivity run needs the labeler's ``thr`` parameter, which the bootstrap's
assembly does not expose. A test pins the two paths to identical labels under
the default thresholds so they cannot drift.

The acceptance evidence (plan WP2.6: "simulated duration/frequency
distributions inside train+val bootstrap bands") is generated here, into
``regime-fit-report.md`` -- deliberately NOT via the sealed battery: the
battery's ``regime_duration_*`` statistics are sealed ``structurally_
unavailable`` and the judged sources may not be touched. This is generator-side
evidence, not a sealed battery metric; WP2.11 must cite it as such.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ah.experiment import ExperimentStore, config_hash, git_sha
from ah.gen.climate.simulate import ClimateArtifact, content_sha256, simulate_decades
from ah.gen.regimes import semimarkov as sm
from ah.splits import DataAccess

__all__ = [
    "ARTIFACT_FILENAME",
    "ARTIFACT_SCHEMA_VERSION",
    "REPORT_FILENAME",
    "SENSITIVITY_ARTIFACT_FILENAME",
    "SENSITIVITY_REPORT_FILENAME",
    "FitData",
    "FitResult",
    "SpellData",
    "acceptance_rows",
    "bootstrap_label_bands",
    "build_fit_data",
    "fit_regimes",
    "label_features",
    "label_run_stats",
    "label_sequence",
    "save_artifact",
    "semimarkov_loglik",
    "simulated_label_stats",
]

ARTIFACT_FILENAME = "regimes-posterior.npz"
SENSITIVITY_ARTIFACT_FILENAME = "regimes-posterior-v1b.npz"
REPORT_FILENAME = "regime-fit-report.md"
SENSITIVITY_REPORT_FILENAME = "regime-sensitivity-report.md"
ARTIFACT_SCHEMA_VERSION = "regimes-artifact-v1"

_N = sm.N_REGIMES
_NC = sm.N_COVARIATES
_LABELS = sm.REGIME_LABELS
_LABEL_INDEX = {label: i for i, label in enumerate(_LABELS)}

# --------------------------------------------------------------------------- #
# identification layout (see semimarkov.py's module docstring)
# --------------------------------------------------------------------------- #

#: Per-row reference destination: EXP for every row but EXP's own, SLOW there.
_ROW_REF: tuple[int, ...] = tuple(1 if k == 0 else 0 for k in range(_N))
#: Free transition intercepts (row, col): off-diagonal, non-reference. 24 entries.
_TRANS_A_ENTRIES: tuple[tuple[int, int], ...] = tuple(
    (k, j) for k in range(_N) for j in range(_N) if j != k and j != _ROW_REF[k]
)
#: Free destination loadings (dest, covariate): every destination but EXP. 20 entries.
_TRANS_B_ENTRIES: tuple[tuple[int, int], ...] = tuple(
    (j, c) for j in range(1, _N) for c in range(_NC)
)


def scatter_trans_a(free: np.ndarray) -> np.ndarray:
    """(24,) free intercepts -> the full (6, 6) matrix with identification zeros."""
    out = np.zeros((_N, _N), dtype=np.float64)
    rows, cols = zip(*_TRANS_A_ENTRIES, strict=True)
    out[list(rows), list(cols)] = np.asarray(free, dtype=np.float64)
    return out


def scatter_trans_b(free: np.ndarray) -> np.ndarray:
    """(20,) free loadings -> the full (6, 4) destination matrix (EXP row zero)."""
    out = np.zeros((_N, _NC), dtype=np.float64)
    rows, cols = zip(*_TRANS_B_ENTRIES, strict=True)
    out[list(rows), list(cols)] = np.asarray(free, dtype=np.float64)
    return out


# --------------------------------------------------------------------------- #
# label features + label sequence (the bootstrap mirror, with a thr parameter)
# --------------------------------------------------------------------------- #


def _tv_series(access: DataAccess, series_id: str) -> pd.Series | None:
    """train_val as a date-indexed float series; None for unknown/empty."""
    try:
        frame = access.train_val(series_id)
    except KeyError:
        return None
    if frame.empty:
        return None
    s = frame.set_index("date")["value"].astype(float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _require(access: DataAccess, series_id: str) -> pd.Series:
    series = _tv_series(access, series_id)
    if series is None:
        raise sm.RegimesError(
            f"series '{series_id}' produced no train+validation data; "
            f"the regime fit refuses a silently absent input"
        )
    return series


def _yoy_percent(level: pd.Series) -> pd.Series:
    """Trailing 12-month percent change of a level series (the bootstrap's rule)."""
    return (level / level.shift(12) - 1.0) * 100.0


def _drawdown_fraction(returns: pd.Series) -> pd.Series:
    """Peak-to-current drawdown over the series' own FULL train+val history
    (the bootstrap's rule: the running maximum must know every earlier peak)."""
    clean = returns.dropna()
    index = (1.0 + clean).cumprod()
    return index / index.cummax() - 1.0


def label_features(access: DataAccess, config: sm.RegimesConfig) -> pd.DataFrame:
    """The four observable label features on a monthly grid (NaN where absent).

    Columns: ``cpi_yoy``, ``growth_yoy``, ``drawdown``, ``usrec`` -- exactly the
    :func:`ah.gen.bootstrap.regime_labels_for` feature set (``hy_oas`` is NaN
    always and is supplied at labeling time, not here).
    """
    ids = config.series
    cpi = _require(access, ids.cpi_monthly)
    indpro = _require(access, ids.indpro_monthly)
    usrec = _require(access, ids.usrec_monthly)
    mkt_rf = _require(access, ids.equity_mkt_rf)
    rf = _require(access, ids.equity_rf)
    common = mkt_rf.index.intersection(rf.index)
    equity = (mkt_rf.loc[common] + rf.loc[common]).sort_index()

    start = min(s.index.min() for s in (cpi, indpro, usrec, equity))
    end = max(s.index.max() for s in (cpi, indpro, usrec, equity))
    dates = pd.date_range(start, end, freq="MS")

    features = pd.DataFrame(index=dates)
    features["cpi_yoy"] = _yoy_percent(cpi).reindex(dates)
    features["growth_yoy"] = _yoy_percent(indpro).reindex(dates)
    features["drawdown"] = _drawdown_fraction(equity).reindex(dates)
    features["usrec"] = usrec.reindex(dates)
    return features


def label_sequence(features: pd.DataFrame, thr: dict[str, Any]) -> np.ndarray:
    """Label codes for a COMPLETE features frame (any NaN row is refused).

    ``hy_oas`` is passed as NaN for every month -- the sealed gap documented in
    :func:`ah.gen.bootstrap.regime_labels_for`: no train+validation ``hy_spread``
    value exists, ``NaN >= hy_crisis`` is False, and CRI rests on the drawdown
    disjunct alone.
    """
    from ah.data.derive import label_regime

    if features[["cpi_yoy", "growth_yoy", "drawdown", "usrec"]].isna().any().any():
        first_bad = features.index[features.isna().any(axis=1)][0]
        raise sm.RegimesError(
            f"regime features are incomplete (first gap at {first_bad.date()}); "
            f"a defaulted feature would silently change the labels"
        )
    codes = [
        _LABEL_INDEX[
            label_regime(
                usrec=float(row.usrec),
                cpi_yoy=float(row.cpi_yoy),
                growth_yoy=float(row.growth_yoy),
                drawdown=float(row.drawdown),
                hy_oas=float("nan"),
                thr=thr,
            )
        ]
        for row in features.itertuples()
    ]
    return np.asarray(codes, dtype=np.int64)


# --------------------------------------------------------------------------- #
# covariates z(s) on the historical span
# --------------------------------------------------------------------------- #


def _slope_series(
    access: DataAccess, config: sm.RegimesConfig, dates: pd.DatetimeIndex
) -> np.ndarray:
    """Curve slope on ``dates``: monthly GS10-TB3MS, JST annual spread before.

    The monthly spread exists from 1953-04 (GS10's start). Earlier months use
    the annual JST long-short spread (usa_ltrate - usa_stir), held constant
    within each year -- a documented splice, preferred to dropping the
    1926-1953 spells (which contain the Great Depression, the single most
    informative crisis observation the century offers).
    """
    ids = config.series
    gs10 = _require(access, ids.gs10_monthly)
    tb3 = _require(access, ids.tb3ms_monthly)
    common = gs10.index.intersection(tb3.index)
    monthly = (gs10.loc[common] - tb3.loc[common]).sort_index()

    lt = _require(access, ids.jst_ltrate)
    st = _require(access, ids.jst_stir)
    a_common = lt.index.intersection(st.index)
    annual = (lt.loc[a_common] - st.loc[a_common]).sort_index()
    annual_monthly = annual.reindex(
        pd.date_range(annual.index.min(), dates.max(), freq="MS")
    ).ffill()

    combined = monthly.reindex(dates)
    fallback = annual_monthly.reindex(dates)
    return combined.where(combined.notna(), fallback).to_numpy(dtype=np.float64)


def _covariates_raw(
    access: DataAccess,
    config: sm.RegimesConfig,
    climate_artifact: ClimateArtifact,
    dates: pd.DatetimeIndex,
    drawdown: np.ndarray,
    thr: dict[str, Any],
) -> np.ndarray:
    """Unstandardized z(s) rows for ``dates``: slope, L, pi*-target, drawdown state."""
    locs = climate_artifact.dates.get_indexer(dates)
    if (locs < 0).any():
        first = dates[np.flatnonzero(locs < 0)[0]]
        raise sm.RegimesError(
            f"month {first.date()} is outside the climate artifact's grid "
            f"({climate_artifact.dates[0].date()} .. {climate_artifact.dates[-1].date()}); "
            f"the historical covariates need the smoothed slow-state path"
        )
    mean_states = climate_artifact.states.mean(axis=0)  # (T, 5) posterior mean
    z = np.empty((len(dates), _NC), dtype=np.float64)
    z[:, 0] = _slope_series(access, config, dates)
    z[:, 1] = mean_states[locs, 4]  # credit_gap
    z[:, 2] = mean_states[locs, 0] - config.pi_target  # pi* - target
    z[:, 3] = (drawdown <= float(thr["drawdown_crisis"])).astype(np.float64)
    return z


# --------------------------------------------------------------------------- #
# spells + fit data
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SpellData:
    """Sojourn/transition observations the numpyro model consumes.

    Censoring convention: the FIRST spell's duration is dropped (its start is
    unobserved -- left truncation), the LAST spell's duration is right-censored
    at the sample end (a survival term, not a pmf term). Every interior spell
    boundary contributes one transition observation with z at the boundary
    month (= the incoming spell's first month).
    """

    soj_state: np.ndarray  # (n_soj,) int
    soj_dur: np.ndarray  # (n_soj,) int, months >= 1
    soj_z: np.ndarray  # (n_soj, 4) standardized
    soj_censored: np.ndarray  # (n_soj,) bool; True only for the final spell
    trans_from: np.ndarray  # (n_tr,) int
    trans_to: np.ndarray  # (n_tr,) int
    trans_z: np.ndarray  # (n_tr, 4) standardized


@dataclass(frozen=True)
class FitData:
    """Everything one ruleset's fit needs, plus what the artifact must record."""

    dates: pd.DatetimeIndex
    labels: np.ndarray  # (T,) int codes
    ruleset_version: str
    thresholds: dict[str, Any]
    z: np.ndarray  # (T, 4) standardized
    cov_mean: np.ndarray  # (4,)
    cov_sd: np.ndarray  # (4,)
    spells: SpellData
    transition_counts: np.ndarray  # (6, 6) int
    cycle_by_regime: np.ndarray  # (6,)
    init_freqs: np.ndarray  # (6,)
    climate_artifact_sha256: str


def build_fit_data(
    access: DataAccess,
    config: sm.RegimesConfig,
    climate_artifact: ClimateArtifact,
    *,
    thr: dict[str, Any] | None = None,
) -> FitData:
    """Assemble labels, covariates and spell observations for one ruleset.

    ``thr=None`` uses the Step-1 ``regime_ruleset_v1`` thresholds; the
    sensitivity run passes ``config.sensitivity`` as a dict. The fit span is the
    maximal contiguous run of months where all four label features AND the
    climate grid are available (INDPRO bounds it on the left, the artifact/
    train_val end on the right).
    """
    from ah.data.derive import regime_thresholds

    thresholds = dict(regime_thresholds()) if thr is None else dict(thr)
    features = label_features(access, config)

    complete = features.notna().all(axis=1).to_numpy()
    on_grid = climate_artifact.dates.get_indexer(features.index) >= 0
    usable = complete & on_grid
    if not usable.any():
        raise sm.RegimesError("no month has all four label features and a climate grid entry")
    first, last = int(np.flatnonzero(usable)[0]), int(np.flatnonzero(usable)[-1])
    if not usable[first : last + 1].all():
        gap = features.index[first + int(np.flatnonzero(~usable[first : last + 1])[0])]
        raise sm.RegimesError(
            f"label features have an interior gap at {gap.date()}; "
            f"the spell sequence would silently skip months"
        )
    span = features.iloc[first : last + 1]
    dates = pd.DatetimeIndex(span.index)

    labels = label_sequence(span, thresholds)
    z_raw = _covariates_raw(
        access, config, climate_artifact, dates, span["drawdown"].to_numpy(), thresholds
    )

    cov_mean = z_raw.mean(axis=0)
    cov_sd = z_raw.std(axis=0)
    # the drawdown dummy stays 0/1 (a standardized dummy has no cleaner meaning)
    cov_mean[3] = 0.0
    cov_sd[3] = 1.0
    cov_sd[cov_sd == 0.0] = 1.0
    z = (z_raw - cov_mean) / cov_sd

    spells = sm.spells_from_labels(labels)
    if len(spells) < 3:
        raise sm.RegimesError(
            f"only {len(spells)} spell(s) in the label sequence; after dropping the "
            f"left-truncated first and right-censoring the last there is nothing to fit"
        )

    soj = spells[1:]  # first spell dropped: left-truncated
    soj_state = np.array([s for s, _, _ in soj], dtype=np.int64)
    soj_dur = np.array([d for _, _, d in soj], dtype=np.int64)
    soj_z = np.stack([z[t0] for _, t0, _ in soj])
    soj_censored = np.zeros(len(soj), dtype=bool)
    soj_censored[-1] = True  # last spell truncated by the sample end

    trans_from = np.array([s for s, _, _ in spells[:-1]], dtype=np.int64)
    trans_to = np.array([s for s, _, _ in spells[1:]], dtype=np.int64)
    trans_z = np.stack([z[t0] for _, t0, _ in spells[1:]])

    counts = np.zeros((_N, _N), dtype=np.int64)
    np.add.at(counts, (trans_from, trans_to), 1)

    usrec = span["usrec"].to_numpy(dtype=np.float64)
    proxy = 1.0 - 2.0 * usrec
    cycle = np.empty(_N, dtype=np.float64)
    for k in range(_N):
        mask = labels == k
        if mask.any():
            cycle[k] = float(np.clip(proxy[mask].mean(), -1.0, 1.0))
        else:
            # a label absent from history: fall back to its ruleset-side sign
            cycle[k] = -1.0 if _LABELS[k] in ("REC", "CRI") else 1.0

    init_freqs = np.bincount(labels, minlength=_N).astype(np.float64) / labels.size

    return FitData(
        dates=dates,
        labels=labels,
        ruleset_version=str(thresholds["version"]),
        thresholds=thresholds,
        z=z,
        cov_mean=cov_mean,
        cov_sd=cov_sd,
        spells=SpellData(
            soj_state=soj_state,
            soj_dur=soj_dur,
            soj_z=soj_z,
            soj_censored=soj_censored,
            trans_from=trans_from,
            trans_to=trans_to,
            trans_z=trans_z,
        ),
        transition_counts=counts,
        cycle_by_regime=cycle,
        init_freqs=init_freqs,
        climate_artifact_sha256=str(climate_artifact.meta["content_sha256"]),
    )


# --------------------------------------------------------------------------- #
# the numpyro model
# --------------------------------------------------------------------------- #


def _nb_logpmf(x: Any, r: Any, p: Any) -> Any:
    """NegBin log-pmf (failures-before-r-th-success), differentiable in r and p."""
    import jax.numpy as jnp
    from jax.scipy.special import gammaln

    return gammaln(x + r) - gammaln(r) - gammaln(x + 1.0) + r * jnp.log(p) + x * jnp.log1p(-p)


def semimarkov_loglik(params: dict[str, Any], spells: SpellData) -> Any:
    """The DN-1.1 SS II.3 log-likelihood (JAX scalar).

    Sojourns: ``D = 1 + X``, ``X ~ NegBin(r_k, p_k)``, ``logit p_k = alpha_k +
    gamma_k' z``; the censored final spell contributes ``log P(X >= d-1)``,
    computed as an exact finite pmf sum (``1 - CDF(d-2)``) rather than via
    ``betainc``, whose JAX gradient w.r.t. ``r`` is unimplemented -- durations
    are concrete data, so the sum has a static length. Tested against
    ``scipy.stats.nbinom``. Transitions: multinomial logit over destinations
    j != k with logits ``a_kj + b_j' z`` (self masked out).
    """
    import jax.numpy as jnp
    from jax.nn import log_softmax

    alpha, gamma = params["alpha"], params["gamma"]
    r, trans_a, b_dest = params["r"], params["trans_a"], params["b_dest"]

    s = jnp.asarray(spells.soj_state)
    x = jnp.asarray(spells.soj_dur, dtype=jnp.float64) - 1.0  # NegBin support
    z = jnp.asarray(spells.soj_z)

    logit_p = alpha[s] + jnp.sum(gamma[s] * z, axis=1)
    p = jnp.clip(jax_sigmoid(logit_p), 1e-12, 1.0 - 1e-12)
    rk = r[s]
    logpmf = _nb_logpmf(x, rk, p)

    cens_np = np.asarray(spells.soj_censored)
    unc = np.flatnonzero(~cens_np)
    ll_soj = jnp.sum(logpmf[unc])
    for i in np.flatnonzero(cens_np):
        x_i = int(spells.soj_dur[i]) - 1
        if x_i == 0:
            continue  # P(X >= 0) = 1
        grid = jnp.arange(x_i, dtype=jnp.float64)  # 0 .. x-1
        cdf = jnp.sum(jnp.exp(_nb_logpmf(grid, rk[i], p[i])))
        ll_soj = ll_soj + jnp.log(jnp.clip(1.0 - cdf, 1e-300, 1.0))

    tf = jnp.asarray(spells.trans_from)
    tt = jnp.asarray(spells.trans_to)
    tz = jnp.asarray(spells.trans_z)
    logits = trans_a[tf] + tz @ b_dest.T  # (n_tr, 6)
    self_mask = jnp.arange(_N)[None, :] == tf[:, None]
    logits = jnp.where(self_mask, -jnp.inf, logits)
    ll_tr = jnp.sum(jnp.take_along_axis(log_softmax(logits, axis=1), tt[:, None], axis=1))

    return ll_soj + ll_tr


def jax_sigmoid(x: Any) -> Any:
    import jax

    return jax.nn.sigmoid(x)


def numpyro_model(spells: SpellData, config: sm.RegimesConfig) -> None:
    """Priors from config; the semi-Markov likelihood as a factor."""
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist

    pri = config.priors

    def normal(spec: sm.PriorSpec, shape: tuple[int, ...]):
        return dist.Normal(spec.loc, spec.scale).expand(shape).to_event(len(shape))

    alpha = numpyro.sample("alpha", normal(pri.alpha, (_N,)))
    gamma = numpyro.sample("gamma", normal(pri.gamma, (_N, _NC)))
    log_r = numpyro.sample("log_r", normal(pri.log_r, (_N,)))
    a_free = numpyro.sample("trans_a_free", normal(pri.trans_a, (len(_TRANS_A_ENTRIES),)))
    b_free = numpyro.sample("trans_b_free", normal(pri.trans_b, (len(_TRANS_B_ENTRIES),)))

    a_rows, a_cols = zip(*_TRANS_A_ENTRIES, strict=True)
    b_rows, b_cols = zip(*_TRANS_B_ENTRIES, strict=True)
    params = {
        "alpha": alpha,
        "gamma": gamma,
        "r": jnp.exp(log_r),
        "trans_a": jnp.zeros((_N, _N)).at[list(a_rows), list(a_cols)].set(a_free),
        "b_dest": jnp.zeros((_N, _NC)).at[list(b_rows), list(b_cols)].set(b_free),
    }
    numpyro.factor("semimarkov_loglik", semimarkov_loglik(params, spells))


_SITE_NAMES = ("alpha", "gamma", "log_r", "trans_a_free", "trans_b_free")


def _flat_param_names() -> list[str]:
    names: list[str] = []
    names += [f"alpha[{lbl}]" for lbl in _LABELS]
    names += [f"gamma[{lbl},{cov}]" for lbl in _LABELS for cov in sm.COVARIATE_NAMES]
    names += [f"log_r[{lbl}]" for lbl in _LABELS]
    names += [f"trans_a[{_LABELS[k]}->{_LABELS[j]}]" for k, j in _TRANS_A_ENTRIES]
    names += [f"trans_b[{_LABELS[j]},{sm.COVARIATE_NAMES[c]}]" for j, c in _TRANS_B_ENTRIES]
    return names


def _run_nuts(spells: SpellData, config: sm.RegimesConfig, seed: int):
    import jax
    from numpyro.infer import MCMC, NUTS, init_to_median

    kernel = NUTS(
        numpyro_model,
        target_accept_prob=config.fit.target_accept,
        max_tree_depth=config.fit.max_tree_depth,
        dense_mass=config.fit.dense_mass,
        init_strategy=init_to_median,
    )
    mcmc = MCMC(
        kernel,
        num_warmup=config.fit.warmup,
        num_samples=config.fit.samples,
        num_chains=config.fit.chains,
        chain_method=config.fit.chain_method,
        progress_bar=False,
    )
    mcmc.run(jax.random.PRNGKey(seed), spells, config, extra_fields=("diverging",))
    return mcmc


def _diagnostics(mcmc, config: sm.RegimesConfig) -> dict[str, Any]:
    from numpyro.diagnostics import summary as numpyro_summary

    grouped = mcmc.get_samples(group_by_chain=True)
    stats = numpyro_summary(grouped)

    flat_names = _flat_param_names()
    per_param: dict[str, dict[str, float]] = {}
    cursor = 0
    for site in _SITE_NAMES:
        row = stats[site]
        n_flat = int(np.asarray(row["mean"]).size)
        for offset in range(n_flat):
            per_param[flat_names[cursor + offset]] = {
                "mean": float(np.asarray(row["mean"]).ravel()[offset]),
                "sd": float(np.asarray(row["std"]).ravel()[offset]),
                "q05": float(np.asarray(row["5.0%"]).ravel()[offset]),
                "q95": float(np.asarray(row["95.0%"]).ravel()[offset]),
                "n_eff": float(np.asarray(row["n_eff"]).ravel()[offset]),
                "r_hat": float(np.asarray(row["r_hat"]).ravel()[offset]),
            }
        cursor += n_flat

    diverging = np.asarray(mcmc.get_extra_fields()["diverging"])
    rhats = np.array([p["r_hat"] for p in per_param.values()])
    ess = np.array([p["n_eff"] for p in per_param.values()])
    finite = rhats[np.isfinite(rhats)]
    return {
        "per_param": per_param,
        "max_rhat": float(finite.max()) if finite.size else float("nan"),
        "min_ess": float(np.nanmin(ess)) if np.isfinite(ess).any() else float("nan"),
        "divergences": int(diverging.sum()),
        "n_chains": int(config.fit.chains),
        "n_samples": int(config.fit.samples),
        "n_warmup": int(config.fit.warmup),
    }


def _thin_indices(total: int, keep: int) -> np.ndarray:
    keep = min(keep, total)
    return np.unique(np.round(np.linspace(0, total - 1, keep)).astype(np.int64))


def _posterior_draws(mcmc, keep_idx: np.ndarray) -> dict[str, np.ndarray]:
    """Thinned flat draws -> the artifact's full-matrix draw arrays."""
    flat = mcmc.get_samples(group_by_chain=False)
    alpha = np.asarray(flat["alpha"], dtype=np.float64)[keep_idx]
    gamma = np.asarray(flat["gamma"], dtype=np.float64)[keep_idx]
    r = np.exp(np.asarray(flat["log_r"], dtype=np.float64)[keep_idx])
    a_free = np.asarray(flat["trans_a_free"], dtype=np.float64)[keep_idx]
    b_free = np.asarray(flat["trans_b_free"], dtype=np.float64)[keep_idx]
    trans_a = np.stack([scatter_trans_a(row) for row in a_free])
    b_dest = np.stack([scatter_trans_b(row) for row in b_free])
    return {"alpha": alpha, "gamma": gamma, "r": r, "trans_a": trans_a, "b_dest": b_dest}


# --------------------------------------------------------------------------- #
# artifact
# --------------------------------------------------------------------------- #


def save_artifact(
    path: Path,
    *,
    draws: dict[str, np.ndarray],
    cov_mean: np.ndarray,
    cov_sd: np.ndarray,
    cycle_by_regime: np.ndarray,
    init_freqs: np.ndarray,
    meta: dict[str, Any],
) -> str:
    """Write the L2 posterior artifact; returns the canonical content SHA-256.

    Same pattern as the climate artifact: the hash covers every array plus the
    meta JSON, is stored inside the file, and
    :func:`ah.gen.regimes.semimarkov.load_artifact` re-verifies it on load.
    """
    arrays: dict[str, np.ndarray] = {
        name: np.asarray(draws[name], dtype=np.float64) for name in sm._DRAW_SHAPES
    }
    arrays["cov_mean"] = np.asarray(cov_mean, dtype=np.float64)
    arrays["cov_sd"] = np.asarray(cov_sd, dtype=np.float64)
    arrays["cycle_by_regime"] = np.asarray(cycle_by_regime, dtype=np.float64)
    arrays["init_freqs"] = np.asarray(init_freqs, dtype=np.float64)
    meta = dict(meta)
    meta.pop("content_sha256", None)
    meta_json = json.dumps(meta, sort_keys=True)
    arrays["meta_json"] = np.array(meta_json)
    digest = content_sha256(arrays, meta_json)
    np.savez(path, content_sha256=np.array(digest), **arrays)
    return digest


# --------------------------------------------------------------------------- #
# acceptance evidence: bootstrap bands vs simulated durations/frequencies
# --------------------------------------------------------------------------- #


def _complete_run_durations(labels: np.ndarray) -> dict[int, list[int]]:
    """Durations of interior (complete) runs per state; first/last runs dropped."""
    out: dict[int, list[int]] = {k: [] for k in range(_N)}
    spells = sm.spells_from_labels(labels)
    for state, _, dur in spells[1:-1]:
        out[state].append(dur)
    return out


def label_run_stats(labels: np.ndarray | list[np.ndarray]) -> dict[str, np.ndarray]:
    """Frequencies and complete-spell duration quantiles for label sequence(s).

    ``labels`` may be one sequence or a list of independent sequences (simulated
    decades); frequencies pool all months, durations pool interior runs.
    """
    rows = (
        [np.asarray(labels)] if isinstance(labels, np.ndarray) else [np.asarray(x) for x in labels]
    )
    total = sum(row.size for row in rows)
    counts = np.zeros(_N, dtype=np.int64)
    durs: dict[int, list[int]] = {k: [] for k in range(_N)}
    for row in rows:
        counts += np.bincount(row, minlength=_N)
        for state, values in _complete_run_durations(row).items():
            durs[state].extend(values)

    freq = counts.astype(np.float64) / float(total)
    med = np.full(_N, np.nan)
    p90 = np.full(_N, np.nan)
    n_spells = np.zeros(_N, dtype=np.int64)
    for k in range(_N):
        if durs[k]:
            arr = np.asarray(durs[k], dtype=np.float64)
            med[k] = float(np.median(arr))
            p90[k] = float(np.percentile(arr, 90.0))
            n_spells[k] = arr.size
    return {"freq": freq, "median_dur": med, "p90_dur": p90, "n_spells": n_spells}


def bootstrap_label_bands(
    labels: np.ndarray,
    *,
    n_boot: int,
    mean_block_months: int,
    seed: int,
    band_lo: float,
    band_hi: float,
) -> dict[str, Any]:
    """Stationary-block-bootstrap bands on regime frequencies and durations.

    The resampling form mirrors the sealed benchmark's (Politis-Romano geometric
    blocks with circular wrap): restart with probability ``1/mean_block_months``,
    otherwise advance by one. Blocks must dominate the spell scale or the
    resample destroys the persistence being measured (WP2.2's b=24 lesson), so
    the default mean block is 120 months. Deterministic per seed.
    """
    arr = np.asarray(labels, dtype=np.int64)
    t_len = arr.size
    rng = np.random.Generator(np.random.PCG64(seed))
    p = 1.0 / float(mean_block_months)

    restart = rng.random((n_boot, t_len)) < p
    restart[:, 0] = True
    starts = rng.integers(0, t_len, size=(n_boot, t_len))
    index = np.empty((n_boot, t_len), dtype=np.int64)
    index[:, 0] = starts[:, 0]
    for t in range(1, t_len):
        advanced = (index[:, t - 1] + 1) % t_len
        index[:, t] = np.where(restart[:, t], starts[:, t], advanced)
    resamples = arr[index]

    stats = {"freq": [], "median_dur": [], "p90_dur": []}
    for b in range(n_boot):
        row_stats = label_run_stats(resamples[b])
        for name in stats:
            stats[name].append(row_stats[name])

    bands: dict[str, Any] = {"n_boot": n_boot, "mean_block_months": mean_block_months, "seed": seed}
    for name, values in stats.items():
        matrix = np.stack(values)  # (n_boot, 6)
        lo = np.full(_N, np.nan)
        hi = np.full(_N, np.nan)
        n_valid = np.zeros(_N, dtype=np.int64)
        for k in range(_N):
            valid = matrix[:, k][np.isfinite(matrix[:, k])]
            n_valid[k] = valid.size
            if valid.size:
                lo[k] = float(np.quantile(valid, band_lo))
                hi[k] = float(np.quantile(valid, band_hi))
        bands[name] = {"lo": lo, "hi": hi, "n_valid": n_valid}
    return bands


def simulated_label_stats(
    artifact: sm.RegimesArtifact,
    climate_artifact: ClimateArtifact,
    *,
    n_decades: int,
    months: int,
    seed: int,
    s0_dates: list[pd.Timestamp] | None = None,
) -> dict[str, Any]:
    """Pooled regime stats for the fitted L2 simulated over real L1 decades.

    L1 paths come from :func:`simulate_decades` with a NEUTRAL cycle (the
    acceptance run is one-pass; the L1<->L2 feedback loop is WP2.7 joinery).
    ``s0_dates`` spreads the starting climate state across history -- decades
    started only from the artifact's final month would inherit 2020's slow
    state everywhere and understate the frequency of high-inflation regimes;
    by default the label-era grid is sampled every ten years. Deterministic:
    batch i uses ``seed + 1_000_003 * i``.
    """
    if s0_dates is None:
        grid = climate_artifact.dates
        lo = grid.get_indexer([pd.Timestamp("1926-07-01")])
        start = int(lo[0]) if lo[0] >= 0 else 0
        s0_dates = [pd.Timestamp(grid[i]) for i in range(start, len(grid) - 1, 120)]
    n_batches = len(s0_dates)
    per_batch = int(np.ceil(n_decades / n_batches))

    rows: list[np.ndarray] = []
    used = 0
    for i, s0 in enumerate(s0_dates):
        take = min(per_batch, n_decades - used)
        if take <= 0:
            break
        batch_seed = seed + 1_000_003 * i
        climate = simulate_decades(
            climate_artifact, take, seed=batch_seed, months=months, s0_date=s0
        )
        sim = sm.simulate_regimes(artifact, climate.states, seed=batch_seed)
        rows.extend(sim.labels[k] for k in range(take))
        used += take

    stats = label_run_stats(rows)
    stats["n_decades"] = used
    stats["months"] = months
    stats["seed"] = seed
    stats["s0_dates"] = [str(ts.date()) for ts in s0_dates]
    return stats


def acceptance_rows(
    hist: dict[str, np.ndarray], bands: dict[str, Any], simulated: dict[str, Any]
) -> list[dict[str, Any]]:
    """The acceptance table: one row per (statistic, regime), inside/outside."""
    rows: list[dict[str, Any]] = []
    for name in ("freq", "median_dur", "p90_dur"):
        for k in range(_N):
            lo = float(bands[name]["lo"][k])
            hi = float(bands[name]["hi"][k])
            sim_val = float(simulated[name][k])
            inside: bool | None
            if np.isnan(sim_val) or np.isnan(lo) or np.isnan(hi):
                inside = None
            else:
                inside = bool(lo <= sim_val <= hi)
            rows.append(
                {
                    "stat": name,
                    "regime": _LABELS[k],
                    "historical": float(hist[name][k]),
                    "band_lo": lo,
                    "band_hi": hi,
                    "simulated": sim_val,
                    "inside": inside,
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# report generation (ASCII only)
# --------------------------------------------------------------------------- #


def _fmt(value: float, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.{digits}f}"


def _mean_sojourn_table(draws: dict[str, np.ndarray]) -> list[tuple[str, float, float, float]]:
    """Posterior mean/5%/95% of E[D] = 1 + r(1-p)/p at z = 0, per state."""
    p = 1.0 / (1.0 + np.exp(-draws["alpha"]))  # (n_draws, 6)
    mean_d = 1.0 + draws["r"] * (1.0 - p) / p
    out = []
    for k in range(_N):
        col = mean_d[:, k]
        out.append(
            (
                _LABELS[k],
                float(col.mean()),
                float(np.quantile(col, 0.05)),
                float(np.quantile(col, 0.95)),
            )
        )
    return out


def _mean_transition_matrix(draws: dict[str, np.ndarray]) -> np.ndarray:
    """Posterior-mean destination probabilities at z = 0, rows = origin."""
    trans_a = draws["trans_a"]  # (n, 6, 6)
    n = trans_a.shape[0]
    probs = np.zeros((_N, _N))
    for k in range(_N):
        logits = trans_a[:, k, :].copy()
        logits[:, k] = -np.inf
        shifted = logits - logits.max(axis=1, keepdims=True)
        e = np.exp(shifted)
        probs[k] = (e / e.sum(axis=1, keepdims=True)).sum(axis=0) / n
    return probs


def _count_table(counts: np.ndarray) -> list[str]:
    lines = ["| from \\ to | " + " | ".join(_LABELS) + " | total |", "|---" * (_N + 2) + "|"]
    for k in range(_N):
        row = " | ".join(str(int(counts[k, j])) for j in range(_N))
        lines.append(f"| {_LABELS[k]} | {row} | {int(counts[k].sum())} |")
    return lines


def _acceptance_section(rows: list[dict[str, Any]], simulated: dict[str, Any]) -> list[str]:
    lines = [
        "This is GENERATOR-SIDE acceptance evidence, not a sealed battery metric:",
        "the battery's `regime_duration_*` statistics are sealed",
        "`structurally_unavailable` and the judged sources are untouched. WP2.11",
        "must cite this table as generator evidence, not as a battery result.",
        "",
        f"Simulated: {simulated['n_decades']} decades x {simulated['months']} months, "
        f"seed {simulated['seed']}, L1 starting states spread over "
        f"{len(simulated['s0_dates'])} historical dates "
        f"({simulated['s0_dates'][0]} .. {simulated['s0_dates'][-1]}, neutral cycle, one-pass).",
        "Durations use complete (interior) spells only, both historically and in",
        "simulation; a 120-month decade right-censors spells longer than the decade,",
        "so long-spell quantiles (EXP especially) are biased short on the simulated",
        "side -- read `p90_dur[EXP]` with that in mind.",
        "",
        "| statistic | regime | historical | band 2.5% | band 97.5% | simulated | inside |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        inside = "n/a" if row["inside"] is None else ("YES" if row["inside"] else "NO")
        lines.append(
            f"| {row['stat']} | {row['regime']} | {_fmt(row['historical'])} | "
            f"{_fmt(row['band_lo'])} | {_fmt(row['band_hi'])} | {_fmt(row['simulated'])} | "
            f"{inside} |"
        )
    judged = [r for r in rows if r["inside"] is not None]
    n_in = sum(1 for r in judged if r["inside"])
    lines += ["", f"Inside: {n_in} / {len(judged)} judged bands."]
    return lines


def _report(
    fit_data: FitData,
    diagnostics: dict[str, Any],
    draws: dict[str, np.ndarray],
    *,
    config: sm.RegimesConfig,
    cfg_hash: str,
    sha: str,
    seed: int,
    vintage_id: str,
    artifact_digest: str,
    acceptance: list[dict[str, Any]] | None,
    simulated: dict[str, Any] | None,
) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Regime skeleton fit report (WP2.6, Layer 2)")
    add("")
    add(f"- config_hash: `{cfg_hash}`")
    add(f"- git_sha: `{sha}`")
    add(f"- seed: {seed}")
    add(f"- vintage_id: `{vintage_id}`")
    add(f"- artifact content sha256: `{artifact_digest}`")
    add(f"- climate (L1) artifact sha256: `{fit_data.climate_artifact_sha256}`")
    add(f"- ruleset: `{fit_data.ruleset_version}`")
    add(
        f"- label span: {fit_data.dates[0].date()} .. {fit_data.dates[-1].date()} "
        f"({len(fit_data.dates)} months, {len(fit_data.spells.soj_state) + 1} spells; "
        f"first spell left-truncated and dropped, last right-censored)"
    )
    add(
        f"- NUTS: {diagnostics['n_chains']} chain(s) x {diagnostics['n_samples']} samples "
        f"({diagnostics['n_warmup']} warmup), target_accept {config.fit.target_accept}"
    )
    add("")
    add("## Empirical transition counts (sparsity, visible)")
    add("")
    lines += _count_table(fit_data.transition_counts)
    add("")
    add(
        "Rare cells are regularized by the weakly informative Normal priors "
        "(priors.yaml): an unobserved transition's posterior stays near its prior "
        "rather than diverging; nothing is forced to zero."
    )
    add("")
    add("## Convergence (R-hat, ESS, divergences)")
    add("")
    add(f"- Divergences: {diagnostics['divergences']}")
    add(f"- max R-hat: {diagnostics['max_rhat']:.4f}")
    add(f"- min ESS: {diagnostics['min_ess']:.0f}")
    add("")
    add("| parameter | mean | sd | 5% | 95% | ESS | R-hat |")
    add("|---|---|---|---|---|---|---|")
    for name, p in diagnostics["per_param"].items():
        add(
            f"| {name} | {p['mean']:.4f} | {p['sd']:.4f} | {p['q05']:.4f} | "
            f"{p['q95']:.4f} | {p['n_eff']:.0f} | {p['r_hat']:.4f} |"
        )
    add("")
    add("## Fitted sojourns at z = 0 (posterior E[D], months)")
    add("")
    add("| regime | mean E[D] | 5% | 95% |")
    add("|---|---|---|---|")
    for label, mean, lo, hi in _mean_sojourn_table(draws):
        add(f"| {label} | {mean:.1f} | {lo:.1f} | {hi:.1f} |")
    add("")
    add("## Posterior-mean transition probabilities at z = 0")
    add("")
    probs = _mean_transition_matrix(draws)
    add("| from \\ to | " + " | ".join(_LABELS) + " |")
    add("|---" * (_N + 1) + "|")
    for k in range(_N):
        add(f"| {_LABELS[k]} | " + " | ".join(f"{probs[k, j]:.3f}" for j in range(_N)) + " |")
    add("")
    add("## Covariates z(s) and standardization")
    add("")
    add("DN-1.1 SS II.3: z(s) = (curve_slope, credit_gap, pi_gap, drawdown_state).")
    add("Standardization constants (train+val fit span; the 0/1 drawdown dummy is")
    add("left unstandardized) -- applied identically at simulation time:")
    add("")
    add("| covariate | mean | sd |")
    add("|---|---|---|")
    for i, name in enumerate(sm.COVARIATE_NAMES):
        add(f"| {name} | {fit_data.cov_mean[i]:.4f} | {fit_data.cov_sd[i]:.4f} |")
    add("")
    add(f"- pi_target: {config.pi_target} (configured constant; see priors.yaml)")
    add("- curve slope: fred.GS10 - fred.TB3MS from 1953-04; JST annual long-short")
    add("  spread (usa_ltrate - usa_stir) held within-year before that (splice).")
    add("- historical credit_gap / pi_gap: WP2.5 posterior-mean smoothed path.")
    add("- SIMULATION-side proxies (recorded limitation): curve_slope becomes")
    add("  psi0 - phi_c0*c(R_t) (the L1 posterior-mean model-implied slope, which")
    add("  compresses slope variance -- no simulated inversions, so the fitted")
    add("  inversion channel is attenuated at generation time); drawdown_state")
    add("  becomes 1[R_t == CRI] (historically drawdowns also breach the threshold")
    add("  outside CRI months).")
    add("")
    add("## The cycle term c_t (the WP2.5 contract)")
    add("")
    add("c_t = cycle_by_regime[R_t], the train+val mean of L1's own fitting proxy")
    add("(1 - 2*USREC) within each label -- proxy-consistent by construction, so the")
    add("fitted phi_c/delta_L keep their meaning. Unsmoothed: the proxy the anchor")
    add("was fitted against is itself a +/-1 step function.")
    add("")
    add("| regime | c |")
    add("|---|---|")
    for k in range(_N):
        add(f"| {_LABELS[k]} | {fit_data.cycle_by_regime[k]:+.3f} |")
    add("")
    add("## Acceptance: simulated durations/frequencies vs train+val bootstrap bands")
    add("")
    if acceptance is not None and simulated is not None:
        lines += _acceptance_section(acceptance, simulated)
    else:
        add("(acceptance run skipped in this invocation)")
    add("")
    return "\n".join(lines)


def _sensitivity_report(
    fd_v1: FitData,
    fd_v1b: FitData,
    draws_v1: dict[str, np.ndarray],
    draws_v1b: dict[str, np.ndarray],
    diag_v1: dict[str, Any],
    diag_v1b: dict[str, Any],
    *,
    config: sm.RegimesConfig,
    cfg_hash: str,
    sha: str,
    acceptance_v1b: list[dict[str, Any]] | None,
    simulated_v1b: dict[str, Any] | None,
) -> str:
    lines: list[str] = []
    add = lines.append
    agreement = float(np.mean(fd_v1.labels == fd_v1b.labels))
    add("# Regime label sensitivity report (WP2.6: regime_ruleset_v1 vs v1b)")
    add("")
    add(f"- config_hash: `{cfg_hash}`")
    add(f"- git_sha: `{sha}`")
    add(f"- span: {fd_v1.dates[0].date()} .. {fd_v1.dates[-1].date()} ({len(fd_v1.dates)} months)")
    add(f"- label agreement rate: {agreement:.4f}")
    add("")
    add("The plan's honesty note: L2 is fitted on rule-based labels, so the fit")
    add("could in principle be an artifact of the ruleset's thresholds. This run")
    add("refits under a perturbed ruleset (`regime_ruleset_v1b`, below) and reports")
    add("what actually moves. `src/ah/data/regime_thresholds.yaml` is not modified;")
    add("the variant is passed through the labeler's `thr` parameter.")
    add("")
    add("## Threshold perturbations (and why they are material)")
    add("")
    add("| threshold | v1 | v1b |")
    add("|---|---|---|")
    from ah.data.derive import regime_thresholds

    v1 = regime_thresholds()
    for key in ("cpi_high", "growth_weak", "growth_slow", "drawdown_crisis", "hy_crisis"):
        add(f"| {key} | {v1[key]} | {fd_v1b.thresholds[key]} |")
    add("")
    add("Each perturbation moves a boundary through a dense part of the feature")
    add("distribution (see priors.yaml's sensitivity block for the per-threshold")
    add("rationale); hy_crisis is unchanged because the disjunct is dead on")
    add("train+validation data (hy_spread's licensed history is all holdout).")
    add("")
    add("## Label composition under both rulesets")
    add("")
    stats_v1 = label_run_stats(fd_v1.labels)
    stats_v1b = label_run_stats(fd_v1b.labels)
    add(
        "| regime | freq v1 | freq v1b | median dur v1 | v1b | p90 dur v1 | v1b | spells v1 | v1b |"
    )
    add("|---|---|---|---|---|---|---|---|---|")
    for k in range(_N):
        add(
            f"| {_LABELS[k]} | {_fmt(float(stats_v1['freq'][k]))} | "
            f"{_fmt(float(stats_v1b['freq'][k]))} | {_fmt(float(stats_v1['median_dur'][k]), 1)} | "
            f"{_fmt(float(stats_v1b['median_dur'][k]), 1)} | "
            f"{_fmt(float(stats_v1['p90_dur'][k]), 1)} | {_fmt(float(stats_v1b['p90_dur'][k]), 1)} | "
            f"{int(stats_v1['n_spells'][k])} | {int(stats_v1b['n_spells'][k])} |"
        )
    add("")
    add("## Empirical transition counts")
    add("")
    add("v1:")
    add("")
    lines += _count_table(fd_v1.transition_counts)
    add("")
    add("v1b:")
    add("")
    lines += _count_table(fd_v1b.transition_counts)
    add("")
    add("## Fitted hazards under both rulesets")
    add("")
    add(
        f"Convergence: v1 max R-hat {diag_v1['max_rhat']:.4f}, min ESS "
        f"{diag_v1['min_ess']:.0f}, {diag_v1['divergences']} divergences; "
        f"v1b max R-hat {diag_v1b['max_rhat']:.4f}, min ESS {diag_v1b['min_ess']:.0f}, "
        f"{diag_v1b['divergences']} divergences."
    )
    add("")
    add("Posterior E[D] at z = 0 (months):")
    add("")
    add("| regime | v1 mean | v1 5% | v1 95% | v1b mean | v1b 5% | v1b 95% |")
    add("|---|---|---|---|---|---|---|")
    t1 = _mean_sojourn_table(draws_v1)
    t2 = _mean_sojourn_table(draws_v1b)
    for (label, m1, lo1, hi1), (_, m2, lo2, hi2) in zip(t1, t2, strict=True):
        add(f"| {label} | {m1:.1f} | {lo1:.1f} | {hi1:.1f} | {m2:.1f} | {lo2:.1f} | {hi2:.1f} |")
    add("")
    add("Posterior-mean transition probabilities at z = 0, v1 -> v1b (delta):")
    add("")
    p1 = _mean_transition_matrix(draws_v1)
    p2 = _mean_transition_matrix(draws_v1b)
    add("| from \\ to | " + " | ".join(_LABELS) + " |")
    add("|---" * (_N + 1) + "|")
    for k in range(_N):
        cells = [f"{p1[k, j]:.2f} ({p2[k, j] - p1[k, j]:+.2f})" for j in range(_N)]
        add(f"| {_LABELS[k]} | " + " | ".join(cells) + " |")
    add("")
    add("Sojourn covariate loadings gamma (posterior mean), v1 vs v1b:")
    add("")
    add("| regime | covariate | gamma v1 | gamma v1b |")
    add("|---|---|---|---|")
    g1 = draws_v1["gamma"].mean(axis=0)
    g2 = draws_v1b["gamma"].mean(axis=0)
    for k in range(_N):
        for c in range(_NC):
            add(f"| {_LABELS[k]} | {sm.COVARIATE_NAMES[c]} | {g1[k, c]:+.3f} | {g2[k, c]:+.3f} |")
    add("")
    add("## Acceptance bands under v1b")
    add("")
    if acceptance_v1b is not None and simulated_v1b is not None:
        lines += _acceptance_section(acceptance_v1b, simulated_v1b)
    else:
        add("(v1b acceptance run skipped in this invocation)")
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# the entry point
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FitResult:
    artifact_path: Path
    report_path: Path
    sensitivity_report_path: Path | None
    diagnostics: dict[str, Any]
    diagnostics_v1b: dict[str, Any] | None
    acceptance: list[dict[str, Any]] | None
    label_agreement_v1b: float | None
    config_hash: str


def _fit_one(
    fit_data: FitData, config: sm.RegimesConfig, seed: int
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    mcmc = _run_nuts(fit_data.spells, config, seed)
    diagnostics = _diagnostics(mcmc, config)
    flat = mcmc.get_samples(group_by_chain=False)
    total = int(np.asarray(flat["alpha"]).shape[0])
    keep_idx = _thin_indices(total, config.fit.artifact_draws)
    draws = _posterior_draws(mcmc, keep_idx)
    return diagnostics, draws


def _artifact_meta(
    fit_data: FitData,
    config: sm.RegimesConfig,
    diagnostics: dict[str, Any],
    *,
    cfg: dict[str, Any],
    cfg_hash: str,
    sha: str,
    seed: int,
    vintage_id: str,
    created_at: str,
    climate_artifact: ClimateArtifact,
    n_draws: int,
) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "config": cfg,
        "config_hash": cfg_hash,
        "git_sha": sha,
        "seed": seed,
        "vintage_id": vintage_id,
        "created_at": created_at,
        "ruleset_version": fit_data.ruleset_version,
        "thresholds": {k: v for k, v in fit_data.thresholds.items()},
        "label_span": [str(fit_data.dates[0].date()), str(fit_data.dates[-1].date())],
        "n_months": len(fit_data.dates),
        "n_sojourn_obs": int(fit_data.spells.soj_state.size),
        "n_transitions": int(fit_data.spells.trans_from.size),
        "transition_counts": fit_data.transition_counts.tolist(),
        "covariate_names": list(sm.COVARIATE_NAMES),
        "pi_target": float(config.pi_target),
        "slope_psi0": float(np.mean(climate_artifact.params["psi"])),
        "slope_phi_c0": float(np.mean(climate_artifact.params["phi_c"])),
        "climate_artifact_sha256": fit_data.climate_artifact_sha256,
        "climate_artifact_path": str(climate_artifact.path),
        "n_draws": int(n_draws),
        "negbin_convention": (
            "D = 1 + X, X ~ NegBin(r, p) failures-before-rth-success; "
            "logit p = alpha + gamma'z; higher p => shorter sojourn"
        ),
        "cycle_mapping": "per-regime train+val mean of 1 - 2*USREC (L1's fitting proxy)",
        "diagnostics": {
            "max_rhat": diagnostics["max_rhat"],
            "min_ess": diagnostics["min_ess"],
            "divergences": diagnostics["divergences"],
        },
    }


def fit_regimes(
    access: DataAccess,
    config: sm.RegimesConfig,
    *,
    climate_artifact: ClimateArtifact,
    seed: int,
    vintage_id: str,
    out_dir: str | Path,
    created_at: str,
    report_copy_path: str | Path | None = None,
    sensitivity_report_copy_path: str | Path | None = None,
    run_acceptance: bool = True,
    run_sensitivity: bool = True,
) -> FitResult:
    """Fit L2 on the labeled history; write artifact(s), reports, exp record.

    The v1 fit uses ``seed``; the v1b sensitivity refit uses ``seed + 1``. Both
    artifacts land in ``out_dir`` (the experiment directory); the reports are
    also copied to ``report_copy_path``/``sensitivity_report_copy_path`` when
    given (repo-root copies, like WP2.5). ``created_at`` is recorded, not read
    from any clock.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cfg = sm.config_dict(config)
    cfg_hash = config_hash(cfg)
    sha = git_sha()
    acc = config.acceptance

    # ---- v1 ----
    fd_v1 = build_fit_data(access, config, climate_artifact)
    diag_v1, draws_v1 = _fit_one(fd_v1, config, seed)
    meta_v1 = _artifact_meta(
        fd_v1,
        config,
        diag_v1,
        cfg=cfg,
        cfg_hash=cfg_hash,
        sha=sha,
        seed=seed,
        vintage_id=vintage_id,
        created_at=created_at,
        climate_artifact=climate_artifact,
        n_draws=int(draws_v1["alpha"].shape[0]),
    )
    artifact_path = out / ARTIFACT_FILENAME
    digest_v1 = save_artifact(
        artifact_path,
        draws=draws_v1,
        cov_mean=fd_v1.cov_mean,
        cov_sd=fd_v1.cov_sd,
        cycle_by_regime=fd_v1.cycle_by_regime,
        init_freqs=fd_v1.init_freqs,
        meta=meta_v1,
    )

    acceptance = simulated = None
    if run_acceptance:
        artifact = sm.load_artifact(artifact_path)
        hist = label_run_stats(fd_v1.labels)
        bands = bootstrap_label_bands(
            fd_v1.labels,
            n_boot=acc.n_boot,
            mean_block_months=acc.bootstrap_mean_block_months,
            seed=acc.bootstrap_seed,
            band_lo=acc.band_lo,
            band_hi=acc.band_hi,
        )
        simulated = simulated_label_stats(
            artifact,
            climate_artifact,
            n_decades=acc.sim_n_decades,
            months=acc.sim_months,
            seed=acc.sim_seed,
        )
        acceptance = acceptance_rows(hist, bands, simulated)

    report = _report(
        fd_v1,
        diag_v1,
        draws_v1,
        config=config,
        cfg_hash=cfg_hash,
        sha=sha,
        seed=seed,
        vintage_id=vintage_id,
        artifact_digest=digest_v1,
        acceptance=acceptance,
        simulated=simulated,
    )
    report_path = out / REPORT_FILENAME
    report_path.write_text(report, encoding="utf-8")
    if report_copy_path is not None:
        Path(report_copy_path).write_text(report, encoding="utf-8")

    # ---- v1b sensitivity ----
    diag_v1b = None
    agreement = None
    sensitivity_report_path: Path | None = None
    if run_sensitivity:
        thr_b = config.sensitivity.model_dump()
        fd_v1b = build_fit_data(access, config, climate_artifact, thr=thr_b)
        diag_v1b, draws_v1b = _fit_one(fd_v1b, config, seed + 1)
        meta_v1b = _artifact_meta(
            fd_v1b,
            config,
            diag_v1b,
            cfg=cfg,
            cfg_hash=cfg_hash,
            sha=sha,
            seed=seed + 1,
            vintage_id=vintage_id,
            created_at=created_at,
            climate_artifact=climate_artifact,
            n_draws=int(draws_v1b["alpha"].shape[0]),
        )
        v1b_path = out / SENSITIVITY_ARTIFACT_FILENAME
        save_artifact(
            v1b_path,
            draws=draws_v1b,
            cov_mean=fd_v1b.cov_mean,
            cov_sd=fd_v1b.cov_sd,
            cycle_by_regime=fd_v1b.cycle_by_regime,
            init_freqs=fd_v1b.init_freqs,
            meta=meta_v1b,
        )
        agreement = float(np.mean(fd_v1.labels == fd_v1b.labels))

        acceptance_v1b = simulated_v1b = None
        if run_acceptance:
            artifact_v1b = sm.load_artifact(v1b_path)
            hist_v1b = label_run_stats(fd_v1b.labels)
            bands_v1b = bootstrap_label_bands(
                fd_v1b.labels,
                n_boot=acc.n_boot,
                mean_block_months=acc.bootstrap_mean_block_months,
                seed=acc.bootstrap_seed,
                band_lo=acc.band_lo,
                band_hi=acc.band_hi,
            )
            simulated_v1b = simulated_label_stats(
                artifact_v1b,
                climate_artifact,
                n_decades=acc.sim_n_decades,
                months=acc.sim_months,
                seed=acc.sim_seed,
            )
            acceptance_v1b = acceptance_rows(hist_v1b, bands_v1b, simulated_v1b)

        sens_report = _sensitivity_report(
            fd_v1,
            fd_v1b,
            draws_v1,
            draws_v1b,
            diag_v1,
            diag_v1b,
            config=config,
            cfg_hash=cfg_hash,
            sha=sha,
            acceptance_v1b=acceptance_v1b,
            simulated_v1b=simulated_v1b,
        )
        sensitivity_report_path = out / SENSITIVITY_REPORT_FILENAME
        sensitivity_report_path.write_text(sens_report, encoding="utf-8")
        if sensitivity_report_copy_path is not None:
            Path(sensitivity_report_copy_path).write_text(sens_report, encoding="utf-8")

    # ---- experiment record ----
    store = ExperimentStore(out.parent)
    store.create(out.name, cfg, seed=seed, vintage_id=vintage_id, created_at=created_at)
    metrics: dict[str, Any] = {
        "max_rhat": diag_v1["max_rhat"],
        "min_ess": diag_v1["min_ess"],
        "divergences": diag_v1["divergences"],
        "artifact_sha256": digest_v1,
    }
    if acceptance is not None:
        judged = [r for r in acceptance if r["inside"] is not None]
        metrics["acceptance_inside"] = sum(1 for r in judged if r["inside"])
        metrics["acceptance_judged"] = len(judged)
    if agreement is not None:
        metrics["label_agreement_v1b"] = agreement
        assert diag_v1b is not None
        metrics["v1b_max_rhat"] = diag_v1b["max_rhat"]
        metrics["v1b_divergences"] = diag_v1b["divergences"]
    store.record_metrics(out.name, metrics)

    return FitResult(
        artifact_path=artifact_path,
        report_path=report_path,
        sensitivity_report_path=sensitivity_report_path,
        diagnostics=diag_v1,
        diagnostics_v1b=diag_v1b,
        acceptance=acceptance,
        label_agreement_v1b=agreement,
        config_hash=cfg_hash,
    )
