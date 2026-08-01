"""WP2.5 fitting: mixed-frequency panel assembly, NUTS, diagnostics, artifact.

Data discipline (STEP2 SS6: leakage is the whole game):

- Every series is read through :meth:`ah.splits.DataAccess.train_val` -- the one
  sanctioned reference/normalization surface. No catalog reads, no ad-hoc paths.
- The CAPE demean (DN-1.1's ``v_t`` anchor) is computed HERE, on the TRAIN span
  only (``ah.splits.TRAIN``), never train+validation and never the full sample --
  the plan's explicit WP2.5 requirement. :func:`assert_train_only_normalization`
  re-derives the constant from the raw series and refuses a mismatch, so a fit
  fed full-sample-demeaned CAPE fails loudly (tested).
- Holdout rows cannot reach the fit: ``train_val`` clips them at the door
  (tested bit-for-bit in ``tests/test_climate_fit.py``).

The cycle proxy used for FITTING on history: ``c_t = 1 - 2*USREC`` (NBER
recession indicator; +1 expansion, -1 recession). Chosen because (a) it covers
the whole 1871-2020 fit span (USREC starts 1854; the Step-1 six-regime ruleset's
inputs only start 1919), (b) NBER dating is the canonical business-cycle
chronology and exactly what WP2.6's regime skeleton refines, and (c) it is
already registered Step-1 data (``fred.USREC``), read through the sanctioned
surface. WP2.6 swaps its own c_t in at SIMULATION time (same [-1, +1] scale)
without refitting -- see ``ah.gen.climate.simulate``'s module docstring.

Mixed-frequency mapping (recorded interface decisions):

- Annual JST observations land on the mid-year month (July): every JST channel
  observes a slow state (half-lives of years), so within-year variation is far
  below observation noise; the year's average is approximated by mid-year.
- Trend-growth measurement (JST ``gdp`` is an annual nominal level): the model
  observes ``100*(dlog gdp_y - dlog cpi_y)`` -- nominal growth deflated by JST
  CPI inflation -- as a noisy annual reading of ``g``.
- The valuation-predictability equation ``E[r_eq(10y)] = a - b*v`` is observed
  as overlapping 10-year forward windows of JST real total equity returns placed
  at the starting year-end. Overlap makes these observations serially dependent
  while the filter treats them as independent; posterior uncertainty on (a, b)
  is therefore somewhat understated. Recorded as a v1 limitation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jax
import numpy as np
import pandas as pd

from ah.experiment import ExperimentStore, config_hash, git_sha
from ah.gen.climate import model as cm
from ah.gen.climate.simulate import content_sha256
from ah.gen.severe import ExclusionSpan
from ah.splits import TRAIN, DataAccess

__all__ = [
    "FitData",
    "FitResult",
    "NormalizationLeakageError",
    "assert_train_only_normalization",
    "build_fit_data",
    "fit_climate",
    "save_artifact",
]

#: FFBS is vmapped in chunks: a full 1000-draw pass would materialize
#: (draws, T, 7, 7) filtered covariances (~0.7 GB at T=1800); 25 at a time is MBs.
_FFBS_CHUNK = 25

ARTIFACT_FILENAME = "climate-posterior.npz"
REPORT_FILENAME = "climate-fit-report.md"
ARTIFACT_SCHEMA_VERSION = "climate-artifact-v1"


class NormalizationLeakageError(RuntimeError):
    """Raised when the recorded CAPE demean is not the train-span constant."""


@dataclass(frozen=True)
class FitData:
    """The assembled mixed-frequency panel plus the normalization record."""

    dates: pd.DatetimeIndex
    kf: cm.KFData
    cape_demean_mean: float
    cape_demean_span: tuple[str, str]
    cape_demean_n: int
    channel_counts: dict[str, int]
    #: WP2.11 severe test: the span removed from the fitting sample, or None.
    exclusion: ExclusionSpan | None = None
    #: How many (month, channel) observations the exclusion unmasked. 0 without one.
    excluded_observations: int = 0
    #: Per-channel observations lost to the exclusion.
    excluded_channel_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class FitResult:
    artifact_path: Path
    report_path: Path
    diagnostics: dict[str, Any]
    config_hash: str


# --------------------------------------------------------------------------- #
# panel assembly
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


def _align(series: pd.Series | None, dates: pd.DatetimeIndex) -> np.ndarray:
    """Series values on the monthly grid; NaN where absent."""
    if series is None:
        return np.full(len(dates), np.nan)
    return series.reindex(dates).to_numpy(dtype=np.float64)


def build_fit_data(
    access: DataAccess,
    config: cm.ClimateConfig,
    *,
    exclude: ExclusionSpan | None = None,
) -> FitData:
    """Assemble the KF panel for the config span, train+validation only.

    ``exclude`` (WP2.11 severe test) removes a span from the FITTING SAMPLE by
    UNMASKING its observations rather than deleting its rows: the grid, and
    therefore the state path, is unchanged, and the filter simply learns nothing
    from those months (see :mod:`ah.gen.severe` for why masking, not deletion,
    is the right reading, and ``ah.gen.climate.model._filter_step`` for the
    mechanism). The CAPE demean constant is re-derived on the reduced sample,
    because it is part of the fit and not of the architecture.
    """
    dates = pd.date_range(config.span.start, config.span.end, freq="MS", inclusive="left")
    t_len = len(dates)
    ids = config.series

    y = np.zeros((t_len, cm.N_CHANNELS))
    mask = np.zeros((t_len, cm.N_CHANNELS))
    aux_pi = np.zeros((t_len, cm.N_CHANNELS))
    aux_c = np.zeros((t_len, cm.N_CHANNELS))
    ch = {name: i for i, name in enumerate(cm.CHANNELS)}

    def put(channel: str, rows: np.ndarray, values: np.ndarray) -> None:
        j = ch[channel]
        y[rows, j] = values
        mask[rows, j] = 1.0

    # --- monthly cycle proxy: c_t = 1 - 2*USREC (see module docstring) ---
    usrec = _tv_series(access, ids.usrec_monthly)
    cycle_series = None if usrec is None else (1.0 - 2.0 * usrec)
    cycle = np.nan_to_num(_align(cycle_series, dates), nan=0.0)

    # --- monthly CPI YoY (annualized log-diff, %) ---
    cpi = _tv_series(access, ids.cpi_monthly)
    yoy_series = None
    if cpi is not None:
        logc = np.log(cpi[cpi > 0])
        yoy_series = 100.0 * (logc - logc.shift(12)).dropna()
    yoy = _align(yoy_series, dates)
    rows = np.nonzero(np.isfinite(yoy))[0]
    put("m_infl", rows, yoy[rows])

    # --- monthly policy rate: the Taylor anchor needs actual inflation + cycle ---
    fed = _align(_tv_series(access, ids.policy_rate_monthly), dates)
    rows = np.nonzero(np.isfinite(fed) & np.isfinite(yoy))[0]
    put("m_policy", rows, fed[rows])
    aux_pi[rows, ch["m_policy"]] = yoy[rows]
    aux_c[rows, ch["m_policy"]] = cycle[rows]

    # --- monthly log CAPE, demeaned on the TRAIN span only ---
    cape = _tv_series(access, ids.cape_monthly)
    demean_mean, demean_n = _train_span_log_cape_mean(cape, config, exclude)
    if cape is not None:
        log_cape = np.log(cape[cape > 0]) - demean_mean
        vals = _align(log_cape, dates)
        rows = np.nonzero(np.isfinite(vals))[0]
        put("m_cape", rows, vals[rows])

    # --- quarterly BIS credit gap ---
    bis = _align(_tv_series(access, ids.bis_gap_quarterly), dates)
    rows = np.nonzero(np.isfinite(bis))[0]
    put("q_bis", rows, bis[rows])

    # --- annual JST channels, placed mid-year (July) ---
    jst_cpi = _tv_series(access, ids.jst_cpi)
    jst_infl = None
    if jst_cpi is not None:
        jl = np.log(jst_cpi[jst_cpi > 0])
        jst_infl = (100.0 * (jl - jl.shift(1))).dropna()

    def year_rows(values: pd.Series, month: int = 7) -> tuple[np.ndarray, np.ndarray]:
        """Map an annual (Jan-1-labelled) series onto grid rows at ``month``."""
        target = pd.DatetimeIndex(
            [pd.Timestamp(year=ts.year, month=month, day=1) for ts in values.index]
        )
        locs = dates.get_indexer(target)
        keep = locs >= 0
        return locs[keep], values.to_numpy(dtype=np.float64)[keep]

    if jst_infl is not None:
        rows, vals = year_rows(jst_infl)
        put("a_infl", rows, vals)

    jst_stir = _tv_series(access, ids.jst_stir)
    if jst_stir is not None and jst_infl is not None:
        both = pd.concat([jst_stir.rename("stir"), jst_infl.rename("infl")], axis=1).dropna()
        rows, vals = year_rows(both["stir"])
        put("a_stir", rows, vals)
        _, infl_vals = year_rows(both["infl"])
        aux_pi[rows, ch["a_stir"]] = infl_vals
        # annual mean of the monthly cycle proxy for the observation year
        if cycle_series is not None:
            cbar = cycle_series.groupby(cycle_series.index.year).mean()
            years = pd.DatetimeIndex(dates[rows]).year
            aux_c[rows, ch["a_stir"]] = cbar.reindex(years).fillna(0.0).to_numpy(dtype=np.float64)

    jst_lt = _tv_series(access, ids.jst_ltrate)
    if jst_lt is not None:
        rows, vals = year_rows(jst_lt)
        put("a_ltrate", rows, vals)

    # --- annual real growth: dlog nominal GDP minus JST CPI inflation ---
    jst_gdp = _tv_series(access, ids.jst_gdp)
    if jst_gdp is not None and jst_infl is not None:
        lg = np.log(jst_gdp[jst_gdp > 0])
        nom = (100.0 * (lg - lg.shift(1))).dropna()
        growth = (nom - jst_infl).dropna()
        rows, vals = year_rows(growth)
        put("a_growth", rows, vals)

    # --- annual credit ratio: 100*log(tloans/gdp) ~ tau + lam_cr * L ---
    jst_tloans = _tv_series(access, ids.jst_tloans)
    if jst_tloans is not None and jst_gdp is not None:
        ratio = (jst_tloans / jst_gdp).dropna()
        ratio = ratio[ratio > 0]
        credit = 100.0 * np.log(ratio)
        rows, vals = year_rows(credit)
        put("a_credit", rows, vals)

    # --- 10y forward real equity return at starting year-end (December) ---
    jst_eq = _tv_series(access, ids.jst_eq_tr)
    if jst_eq is not None and jst_infl is not None:
        eq_log = (100.0 * np.log1p(jst_eq[jst_eq > -1.0])).dropna()
        real = (eq_log - jst_infl).dropna()
        real_by_year = pd.Series(real.to_numpy(), index=real.index.year)
        r10_index = []
        r10_values = []
        for year in real_by_year.index:
            window = real_by_year.reindex(range(year + 1, year + 11))
            if not window.isna().any():
                r10_index.append(pd.Timestamp(year=year, month=1, day=1))
                r10_values.append(float(window.mean()))
        if r10_values:
            r10 = pd.Series(r10_values, index=pd.DatetimeIndex(r10_index))
            rows, vals = year_rows(r10, month=12)
            put("a_r10", rows, vals)

    # --- WP2.11 severe test: unmask the excluded span (the grid is untouched) ---
    excluded_counts: dict[str, int] = {}
    n_excluded = 0
    if exclude is not None:
        inside = exclude.contains(dates)
        excluded_counts = {name: int(mask[inside, i].sum()) for i, name in enumerate(cm.CHANNELS)}
        n_excluded = int(sum(excluded_counts.values()))
        mask[inside, :] = 0.0
        y[inside, :] = 0.0
        aux_pi[inside, :] = 0.0
        aux_c[inside, :] = 0.0

    m0, p0 = cm.init_state_moments(config)
    kf = cm.KFData(y=y, mask=mask, aux_pi=aux_pi, aux_c=aux_c, cycle=cycle, m0=m0, p0=p0)
    counts = {name: int(mask[:, i].sum()) for i, name in enumerate(cm.CHANNELS)}
    return FitData(
        dates=dates,
        kf=kf,
        cape_demean_mean=demean_mean,
        cape_demean_span=(config.span.start, TRAIN.end),
        cape_demean_n=demean_n,
        channel_counts=counts,
        exclusion=exclude,
        excluded_observations=n_excluded,
        excluded_channel_counts=excluded_counts,
    )


def _train_span_log_cape_mean(
    cape: pd.Series | None,
    config: cm.ClimateConfig,
    exclude: ExclusionSpan | None = None,
) -> tuple[float, int]:
    """Mean log CAPE over [span.start, TRAIN.end) minus ``exclude`` -- the demean.

    The demean constant is a FITTED normalization, so a severe-test fit must not
    see the excluded decade in it either (the same posture as L3's train-only
    standardization constants being re-derived on the reduced sample).
    """
    if cape is None:
        return 0.0, 0
    span = cape[(cape.index >= config.span.start) & (cape.index < TRAIN.end)]
    span = span[span > 0]
    if exclude is not None and not span.empty:
        span = span[~exclude.contains(pd.DatetimeIndex(span.index))]
    if span.empty:
        return 0.0, 0
    return float(np.log(span).mean()), len(span)


def assert_train_only_normalization(
    fit_data: FitData,
    access: DataAccess,
    config: cm.ClimateConfig,
    *,
    exclude: ExclusionSpan | None = None,
) -> None:
    """Refuse a FitData whose demean constant is not the train-span constant.

    This is the door the plan's full-sample-leakage test knocks on: recompute the
    train-span mean from the raw series and require an exact match. Under a
    severe-test ``exclude`` the expected constant is the REDUCED-sample one, so a
    severe-test fit carrying the primary (full-sample) constant is refused too.
    """
    if exclude is not None and fit_data.exclusion != exclude:
        raise NormalizationLeakageError(
            f"fit data records exclusion {fit_data.exclusion!r} but the guard was asked "
            f"to verify against {exclude!r}"
        )
    expected_mean, expected_n = _train_span_log_cape_mean(
        _tv_series(access, config.series.cape_monthly), config, exclude
    )
    if fit_data.cape_demean_span != (config.span.start, TRAIN.end):
        raise NormalizationLeakageError(
            f"CAPE demean span {fit_data.cape_demean_span} is not the train span "
            f"({config.span.start!r}, {TRAIN.end!r}); normalization must be train-only"
        )
    if fit_data.cape_demean_n != expected_n or not np.isclose(
        fit_data.cape_demean_mean, expected_mean, rtol=0.0, atol=1e-12
    ):
        raise NormalizationLeakageError(
            f"CAPE demean constant {fit_data.cape_demean_mean!r} (n={fit_data.cape_demean_n}) "
            f"does not equal the train-span constant {expected_mean!r} (n={expected_n}); "
            f"a full-sample (or otherwise contaminated) normalization is refused"
        )


# --------------------------------------------------------------------------- #
# NUTS + diagnostics
# --------------------------------------------------------------------------- #


def _run_nuts(fit_data: FitData, config: cm.ClimateConfig, seed: int):
    import numpyro
    from numpyro.infer import MCMC, NUTS, init_to_median

    kernel = NUTS(
        cm.numpyro_model,
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
    mcmc.run(jax.random.PRNGKey(seed), fit_data.kf, config, extra_fields=("diverging",))
    _ = numpyro  # keep the import local and explicit
    return mcmc


def _diagnostics(mcmc, fit_data: FitData, config: cm.ClimateConfig) -> dict[str, Any]:
    from numpyro.diagnostics import summary as numpyro_summary

    grouped = mcmc.get_samples(group_by_chain=True)
    stats = numpyro_summary(grouped)
    per_param: dict[str, dict[str, float]] = {}
    for name in cm.PARAM_NAMES:
        row = stats[name]
        per_param[name] = {
            "mean": float(row["mean"]),
            "sd": float(row["std"]),
            "q05": float(row["5.0%"]),
            "q95": float(row["95.0%"]),
            "n_eff": float(row["n_eff"]),
            "r_hat": float(row["r_hat"]),
        }
    diverging = np.asarray(mcmc.get_extra_fields()["diverging"])
    rhats = np.array([p["r_hat"] for p in per_param.values()])
    ess = np.array([p["n_eff"] for p in per_param.values()])
    finite_rhats = rhats[np.isfinite(rhats)]
    return {
        "per_param": per_param,
        "max_rhat": float(finite_rhats.max()) if finite_rhats.size else float("nan"),
        "min_ess": float(np.nanmin(ess)) if np.isfinite(ess).any() else float("nan"),
        "divergences": int(diverging.sum()),
        "n_chains": int(config.fit.chains),
        "n_samples": int(config.fit.samples),
        "n_warmup": int(config.fit.warmup),
        "channel_counts": dict(fit_data.channel_counts),
    }


def _thin_indices(total: int, keep: int) -> np.ndarray:
    keep = min(keep, total)
    return np.unique(np.round(np.linspace(0, total - 1, keep)).astype(np.int64))


def _ffbs_states(mcmc, fit_data: FitData, keep_idx: np.ndarray, seed: int) -> np.ndarray:
    """Smoothed KF-state draws for the retained posterior draws: (n_keep, T, 7)."""
    flat = mcmc.get_samples(group_by_chain=False)
    keys = jax.random.split(jax.random.PRNGKey(seed + 1), len(keep_idx))
    chunks: list[np.ndarray] = []
    ffbs = jax.jit(lambda ks, th: jax.vmap(lambda k, t: cm._ffbs_single(k, t, fit_data.kf))(ks, th))
    for lo in range(0, len(keep_idx), _FFBS_CHUNK):
        sel = keep_idx[lo : lo + _FFBS_CHUNK]
        theta_batch = {name: flat[name][sel] for name in cm.PARAM_NAMES}
        chunk_keys = keys[lo : lo + len(sel)]
        chunks.append(np.asarray(ffbs(chunk_keys, theta_batch)))
    return np.concatenate(chunks, axis=0)


def _ppc_coverage(
    kf_states: np.ndarray,
    flat_params: dict[str, np.ndarray],
    keep_idx: np.ndarray,
    fit_data: FitData,
    n_ppc: int,
    seed: int,
) -> dict[str, float]:
    """Fraction of observed cells inside the 90% posterior-predictive interval."""
    n_ppc = min(n_ppc, kf_states.shape[0])
    rng = np.random.Generator(np.random.PCG64(seed + 2))
    coverage: dict[str, float] = {}
    y, mask = fit_data.kf.y, fit_data.kf.mask
    for j, channel in enumerate(cm.CHANNELS):
        rows = np.nonzero(mask[:, j] == 1.0)[0]
        if rows.size == 0:
            continue
        reps = np.empty((n_ppc, rows.size))
        for d in range(n_ppc):
            theta = {name: float(flat_params[name][keep_idx[d]]) for name in cm.PARAM_NAMES}
            h = np.asarray(cm.observation_matrix(theta))[j]
            offs = np.asarray(cm.observation_offsets(theta, fit_data.kf.aux_pi, fit_data.kf.aux_c))[
                rows, j
            ]
            sd = float(np.asarray(cm.observation_noise_sd(theta))[j])
            mean = kf_states[d, rows, :] @ h + offs
            reps[d] = mean + sd * rng.standard_normal(rows.size)
        lo = np.quantile(reps, 0.05, axis=0)
        hi = np.quantile(reps, 0.95, axis=0)
        actual = y[rows, j]
        coverage[channel] = float(np.mean((actual >= lo) & (actual <= hi)))
    return coverage


# --------------------------------------------------------------------------- #
# artifact + report
# --------------------------------------------------------------------------- #


def save_artifact(
    path: Path,
    *,
    params: dict[str, np.ndarray],
    states: np.ndarray,
    dates: pd.DatetimeIndex,
    meta: dict[str, Any],
) -> str:
    """Write the posterior artifact; returns the canonical content SHA-256.

    The hash covers every array plus the meta JSON and is stored inside the file;
    :func:`ah.gen.climate.simulate.load_artifact` re-verifies it on every load.
    """
    arrays: dict[str, np.ndarray] = {
        f"param_{name}": np.asarray(draws, dtype=np.float64) for name, draws in params.items()
    }
    arrays["states"] = np.asarray(states, dtype=np.float64)
    arrays["dates"] = dates.to_numpy().astype("datetime64[M]").astype(np.int64)
    meta = dict(meta)
    meta.pop("content_sha256", None)
    meta_json = json.dumps(meta, sort_keys=True)
    arrays["meta_json"] = np.array(meta_json)
    digest = content_sha256(arrays, meta_json)
    # meta_json inside the file must match what was hashed; the hash itself is a
    # separate entry so verification can pop it and re-hash the rest (load_artifact
    # surfaces it as meta["content_sha256"]).
    np.savez(path, content_sha256=np.array(digest), **arrays)
    return digest


def _report(
    diagnostics: dict[str, Any],
    fit_data: FitData,
    config: cm.ClimateConfig,
    *,
    cfg_hash: str,
    sha: str,
    seed: int,
    vintage_id: str,
    artifact_digest: str,
    states: np.ndarray,
) -> str:
    """The generated climate-fit-report.md (ASCII only)."""
    lines: list[str] = []
    add = lines.append
    add("# Climate model fit report (WP2.5, Layer 1)")
    add("")
    add(f"- config_hash: `{cfg_hash}`")
    add(f"- git_sha: `{sha}`")
    add(f"- seed: {seed}")
    add(f"- vintage_id: `{vintage_id}`")
    add(f"- artifact content sha256: `{artifact_digest}`")
    add(
        f"- span: {config.span.start} .. {config.span.end} (exclusive); "
        f"{len(fit_data.dates)} months"
    )
    add(
        f"- NUTS: {diagnostics['n_chains']} chain(s) x {diagnostics['n_samples']} samples "
        f"({diagnostics['n_warmup']} warmup), target_accept {config.fit.target_accept}"
    )
    if fit_data.exclusion is not None:
        add(
            f"- **WP2.11 SEVERE TEST**: fitting sample EXCLUDES {fit_data.exclusion.label} "
            f"({fit_data.excluded_observations} observations unmasked; the monthly grid and "
            f"therefore the state path are unchanged)"
        )
    add("")
    add("## Train-only normalization")
    add("")
    add(
        f"v_t = log(CAPE) demeaned by the TRAIN-span constant {fit_data.cape_demean_mean:.6f} "
        f"(n={fit_data.cape_demean_n}, span {fit_data.cape_demean_span[0]} .. "
        f"{fit_data.cape_demean_span[1]}, exclusive). Never full-sample; enforced by "
        f"`assert_train_only_normalization` and tested."
    )
    add("")
    add("## Convergence (R-hat, ESS, Divergences)")
    add("")
    add(f"- Divergences: {diagnostics['divergences']}")
    add(f"- max R-hat: {diagnostics['max_rhat']:.4f}")
    add(f"- min ESS: {diagnostics['min_ess']:.0f}")
    add("")
    add("| parameter | mean | sd | 5% | 95% | ESS | R-hat |")
    add("|---|---|---|---|---|---|---|")
    for name in cm.PARAM_NAMES:
        p = diagnostics["per_param"][name]
        add(
            f"| {name} | {p['mean']:.4f} | {p['sd']:.4f} | {p['q05']:.4f} | "
            f"{p['q95']:.4f} | {p['n_eff']:.0f} | {p['r_hat']:.4f} |"
        )
    add("")
    add("## Observation channels")
    add("")
    add("| channel | observations |")
    add("|---|---|")
    for name, count in diagnostics["channel_counts"].items():
        add(f"| {name} | {count} |")
    add("")
    add("## Posterior predictive checks (90% interval coverage)")
    add("")
    add("| channel | coverage |")
    add("|---|---|")
    for name, frac in diagnostics.get("ppc_coverage_90", {}).items():
        add(f"| {name} | {frac:.3f} |")
    add("")
    add("## Slow states (posterior over the fit span)")
    add("")
    add("half-life posteriors (years) and smoothed state ranges:")
    add("")
    add("| state | half-life 5% | median | 95% | state min | mean | max |")
    add("|---|---|---|---|---|---|---|")
    hl_for_state = {
        "pi_star": "hl_pi",
        "r_star": "hl_r",
        "g": "hl_g",
        "v": "hl_v",
        "credit_gap": "hl_L",
    }
    for i, state in enumerate(cm.STATE_NAMES):
        p = diagnostics["per_param"][hl_for_state[state]]
        mean_path = states[:, :, i].mean(axis=0)
        add(
            f"| {state} | {p['q05']:.1f} | {(p['q05'] * p['q95']) ** 0.5:.1f} | "
            f"{p['q95']:.1f} | {mean_path.min():.2f} | {mean_path.mean():.2f} | "
            f"{mean_path.max():.2f} |"
        )
    add("")
    add(
        "Cycle proxy for fitting: c_t = 1 - 2*USREC (NBER). WP2.6 supplies its own "
        "c_t at simulation time on the same [-1, +1] scale; no refit required."
    )
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# the entry point
# --------------------------------------------------------------------------- #


def fit_climate(
    access: DataAccess,
    config: cm.ClimateConfig,
    *,
    seed: int,
    vintage_id: str,
    out_dir: str | Path,
    created_at: str,
    report_copy_path: str | Path | None = None,
    exclude: ExclusionSpan | None = None,
) -> FitResult:
    """Fit L1 on the panel behind ``access``; write artifact + report + exp record.

    ``out_dir`` becomes the experiment directory (``ah.experiment`` layout: its
    parent is the store root, its name the exp_id). ``exclude`` is the WP2.11
    severe-test fitting-sample exclusion; it is recorded in the artifact meta (and
    therefore in the artifact's content hash), so a severe-test posterior can
    never be mistaken for the primary one.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    fit_data = build_fit_data(access, config, exclude=exclude)
    assert_train_only_normalization(fit_data, access, config, exclude=exclude)

    cfg = cm.config_dict(config)
    cfg_hash = config_hash(cfg)
    mcmc = _run_nuts(fit_data, config, seed)
    diagnostics = _diagnostics(mcmc, fit_data, config)

    flat = mcmc.get_samples(group_by_chain=False)
    total = int(np.asarray(flat[cm.PARAM_NAMES[0]]).shape[0])
    keep_idx = _thin_indices(total, config.fit.artifact_draws)
    kf_states = _ffbs_states(mcmc, fit_data, keep_idx, seed)

    flat_np = {name: np.asarray(flat[name], dtype=np.float64) for name in cm.PARAM_NAMES}
    diagnostics["ppc_coverage_90"] = _ppc_coverage(
        kf_states, flat_np, keep_idx, fit_data, config.fit.ppc_draws, seed
    )

    params = {name: flat_np[name][keep_idx] for name in cm.PARAM_NAMES}
    states = kf_states[:, :, : cm.N_STATES]  # the five-state contract only

    sha = git_sha()
    meta: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "config": cfg,
        "config_hash": cfg_hash,
        "git_sha": sha,
        "seed": seed,
        "vintage_id": vintage_id,
        "created_at": created_at,
        "state_names": list(cm.STATE_NAMES),
        "param_names": list(cm.PARAM_NAMES),
        "n_draws": len(keep_idx),
        "cape_demean": {
            "mean": fit_data.cape_demean_mean,
            "n": fit_data.cape_demean_n,
            "span": list(fit_data.cape_demean_span),
        },
        "cycle_proxy": "1 - 2*USREC (NBER); WP2.6 supplies c_t at simulation time",
        "severe_test_exclusion": (
            None
            if exclude is None
            else {
                "span": exclude.label,
                "start": exclude.start,
                "end_exclusive": exclude.end_exclusive,
                "mechanism": "observations UNMASKED; grid and state path unchanged",
                "observations_removed": fit_data.excluded_observations,
                "by_channel": dict(fit_data.excluded_channel_counts),
            }
        ),
        "diagnostics": {
            "max_rhat": diagnostics["max_rhat"],
            "min_ess": diagnostics["min_ess"],
            "divergences": diagnostics["divergences"],
        },
    }
    artifact_path = out / ARTIFACT_FILENAME
    digest = save_artifact(
        artifact_path, params=params, states=states, dates=fit_data.dates, meta=meta
    )

    report = _report(
        diagnostics,
        fit_data,
        config,
        cfg_hash=cfg_hash,
        sha=sha,
        seed=seed,
        vintage_id=vintage_id,
        artifact_digest=digest,
        states=states,
    )
    report_path = out / REPORT_FILENAME
    report_path.write_text(report, encoding="utf-8")
    if report_copy_path is not None:
        Path(report_copy_path).write_text(report, encoding="utf-8")

    store = ExperimentStore(out.parent)
    store.create(out.name, cfg, seed=seed, vintage_id=vintage_id, created_at=created_at)
    store.record_metrics(
        out.name,
        {
            "max_rhat": diagnostics["max_rhat"],
            "min_ess": diagnostics["min_ess"],
            "divergences": diagnostics["divergences"],
            "artifact_sha256": digest,
            "ppc_coverage_90": diagnostics["ppc_coverage_90"],
        },
    )

    return FitResult(
        artifact_path=artifact_path,
        report_path=report_path,
        diagnostics=diagnostics,
        config_hash=cfg_hash,
    )
