"""Route-C de-smoothing MEASUREMENT for pm_buyout (pe-desmooth-01).

MEASUREMENT ONLY -- nothing sealed changes. This script decides whether an
amendment to the sealed pm_buyout mapping row is even supportable, by:

  Step 0  Reproducing the sealed pm_buyout row (alpha 0.019441, equity_mkt
          0.8362, d_ig -0.0279, sigma 0.1225, r2 0.269) from the current
          unconditional de-smoother, using the SAME fit function the sealed
          row came from (scripts/estimate_sleeve_mappings_v1_2.py, loaded via
          importlib so nothing is copied). This is a calibration gate: the
          script REFUSES to continue if it fails.
  Step 1  Fitting a state-dependent glm_ma de-smoother for buyout: theta on
          calm quarters vs NBER-stress quarters (fred.USREC, the house
          _stress_split method), with identification honesty (n, k,
          boundary/fallback, splice count, leave-one-episode-out).
  Step 2  A transferred variant: the sealed geltner-family stickiness 0.4508
          (ASSUMED for buyout -- pooled over pm_infra + pm_re_value_add, NOT
          buyout) applied to buyout's full-sample theta0.
  Step 3  Reconstructing the "true" series under each variant with a
          time-varying inverse of obs_t = sum_j theta_j(state_t)*truth_{t-j},
          self-tested against ah.data.desmooth._recover_truth in the
          constant-theta case.
  Step 4  Refitting the mapping row on each reconstruction (same fit
          function, only the sleeve truth series changes).
  Step 5  The D-preview: the asymmetric downside-kink regression on each
          reconstruction.
  Step 6  A what-if on The Gulf Decade (world ...712, seed 202608, 200 paths
          at the platform stride): the PE tape under the sealed row vs the
          two refit rows, rebuilt term-by-term and asserted bit-identical to
          ah.port.adapter.run_gen_path for the sealed case.

READ-ONLY guarantees: data/ is the shared live store; the catalog is read
through Catalog/DataAccess exactly as scripts/estimate_smoothing_kernel.py
does; data/ah.db is opened sqlite mode=ro; all series access goes through
DataAccess.train_val (the holdout is untouched). The only file written is the
JSON sidecar under docs/superpowers/specs/. Deterministic: the only RNG is
the platform-stride residual stream the adapter itself uses.

Run:  uv run python scripts/pe_desmooth_c_estimation.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.data.desmooth import _fit_ma_k, _recover_truth, glm_ma
from ah.eval.sleevetails import pm_sleeve_members
from ah.splits import DataAccess

REPO = Path(__file__).resolve().parents[1]
RUN_DATE = "2026-08-19"
OUT_JSON = REPO / "docs" / "superpowers" / "specs" / "2026-08-19-pe-desmooth-c-measurement.json"

# The sealed pm_buyout row (mappings/sleeve-mappings-v1.2.yaml), the Step-0 target.
SEALED = {
    "alpha_quarterly": 0.019441,
    "equity_mkt": 0.8362,
    "d_ig": -0.0279,
    "residual_sigma_annual": 0.1225,
    "r2_train_val": 0.269,
}
# ASSUMED (Variant 2 only): the sealed geltner-family stickiness, pooled over
# pm_infra + pm_re_value_add (mappings/smoothing-kernel-v1.0.yaml). Buyout is
# NOT in that pool; carrying it to buyout is a transfer assumption, not a
# measurement, and every number downstream of it inherits the label ASSUMED.
GELTNER_STICKINESS = 0.4508
FULL_SAMPLE_THETA = [0.85, 0.15]  # the sealed unconditional buyout kernel (glm_ma, k=1)

# Step 6: The Gulf Decade, per scripts/pe_serenity_probe.py (pe-serenity-01).
GULF_WORLD_ID = "00000000-0000-4000-9000-000000000712"
GULF_SEED = 202608
N_PATHS = 200
CRASH_MONTHS = slice(48, 60)  # year 5, months 48-59

# Episode windows for peak-to-trough drawdowns on the quarterly truth series.
# Windows deliberately span peak-before to recovery-after so the peak-to-trough
# is not clipped by the window edge.
EPISODE_WINDOWS = {
    "1990-91": ("1989-10-01", "1992-12-31"),
    "2001": ("2000-01-01", "2003-12-31"),
    "2008-09": ("2007-01-01", "2010-12-31"),
    "2020": ("2019-10-01", "2020-12-31"),
}


# ------------------------------------------------------------------ helpers


def load_v12_module():
    """Load the sealed-row estimator via importlib (no code copied, no edit)."""
    path = REPO / "scripts" / "estimate_sleeve_mappings_v1_2.py"
    spec = importlib.util.spec_from_file_location("emv12", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def raw_composite(access: DataAccess, members: tuple[str, ...]) -> pd.Series:
    """The _raw_composite pattern from scripts/estimate_smoothing_kernel.py."""
    cols = []
    for sid in members:
        frame = access.train_val(sid)
        cols.append(
            pd.Series(
                pd.to_numeric(frame["value"]).to_numpy(dtype=float),
                index=pd.to_datetime(frame["date"]),
            )
        )
    return pd.concat(cols, axis=1, sort=True).mean(axis=1, skipna=True).sort_index()


def fit_mapping_row(mod, y: pd.Series, xq: pd.DataFrame, spec) -> dict:
    """The sealed fit, via the loaded v1.2 module. Only the truth series varies."""
    n_obs = len(pd.concat([y.rename("y"), xq], axis=1, sort=True).dropna())
    lags = mod.lag_count(n_obs)
    summed, alpha, resid, yv = mod.fit_sum_beta(y, xq, spec, lags)
    sigma = float(resid.std(ddof=1) * np.sqrt(4.0))  # v1.1's _sigma_annual, quarterly
    r2 = float(1.0 - resid.to_numpy().var() / yv.var())  # v1.2's own r2 formula
    loadings = {r: float(b) for r, b in zip(mod.REGRESSORS, summed, strict=True)}
    a_q = float(alpha)
    return {
        "n_quarters": int(n_obs),
        "dimson_lags": int(lags),
        "alpha_quarterly": a_q,
        "alpha_annualised_as_adapter_applies_it_pct": ((1 + a_q / 3.0) ** 12 - 1) * 100.0,
        "alpha_annualised_from_quarterly_pct": ((1 + a_q) ** 4 - 1) * 100.0,
        "loadings": loadings,
        "residual_sigma_annual": sigma,
        "r2_train_val": r2,
        "dimson_per_lag_note": (
            "the v1.2 fit function returns only the summed beta; "
            "per-lag decomposition is not reported by it"
        ),
    }


def stress_mask_for(access: DataAccess, index: pd.DatetimeIndex) -> pd.Series:
    """fred.USREC reindexed to the composite's quarterly index, ffill -- the
    house _stress_split method (scripts/estimate_smoothing_kernel.py)."""
    frame = access.train_val("fred.USREC")
    usrec = pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float) > 0.5,
        index=pd.to_datetime(frame["date"]),
    )
    return usrec.reindex(index).ffill().fillna(False).astype(bool)


def contiguous_episodes(index: pd.DatetimeIndex, mask: np.ndarray) -> list[list[str]]:
    """Runs of consecutive stress quarters (positional adjacency)."""
    episodes: list[list[str]] = []
    current: list[str] = []
    for i, flag in enumerate(mask):
        if flag:
            current.append(str(index[i].date()))
        else:
            if current:
                episodes.append(current)
                current = []
    if current:
        episodes.append(current)
    return episodes


def count_splices(mask: np.ndarray) -> int:
    """How many adjacent pairs in the concatenated subsample were NOT adjacent
    in the full series -- each is a fabricated seam the ACF estimator sees."""
    positions = np.flatnonzero(mask)
    if positions.size < 2:
        return 0
    return int((np.diff(positions) > 1).sum())


def theta_summary(fit) -> dict:
    return {
        "method": fit.method,
        "k": int(fit.k),
        "theta": [float(t) for t in fit.theta],
        "fell_back_to_geltner": bool(fit.fell_back),
        "warnings": list(fit.warnings),
    }


def prefallback_theta(obs: np.ndarray, kmax: int = 3, default_k: int = 2) -> dict:
    """glm_ma's own AIC selection BEFORE the boundary check -- what the MA
    family actually estimated when the public function refused to fabricate
    precision and fell back. Read-only reuse of desmooth._fit_ma_k."""
    fits = {k: _fit_ma_k(obs, k) for k in range(1, kmax + 1)}

    def score(k: int) -> float:
        return fits[k][1] + (0.0 if k == default_k else 1e-6)

    k = min(fits, key=score)
    theta, _aic = fits[k]
    return {"k": int(k), "theta": [float(t) for t in theta]}


def recover_truth_tv(
    obs: np.ndarray, theta_calm: list[float], theta_stress: list[float], stress: np.ndarray
) -> np.ndarray:
    """Time-varying inverse of obs_t = sum_j theta_j(state_t) * truth_{t-j}.

    Generalises ah.data.desmooth._recover_truth to per-period theta; the
    constant-theta case is asserted allclose against the original in main().
    """
    kmax = max(len(theta_calm), len(theta_stress)) - 1
    tc = np.zeros(kmax + 1)
    tc[: len(theta_calm)] = theta_calm
    ts = np.zeros(kmax + 1)
    ts[: len(theta_stress)] = theta_stress
    truth = np.zeros(len(obs), dtype=float)
    for t in range(len(obs)):
        th = ts if stress[t] else tc
        acc = obs[t]
        for j in range(1, kmax + 1):
            if t - j >= 0:
                acc -= th[j] * truth[t - j]
        truth[t] = acc / th[0]
    return truth


def acf1(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    denom = float((x * x).sum())
    return float((x[:-1] * x[1:]).sum() / denom) if denom else float("nan")


def window_drawdown(r: pd.Series, lo: str, hi: str) -> dict:
    """Peak-to-trough drawdown of the compounded index inside [lo, hi]."""
    w = r.loc[(r.index >= pd.Timestamp(lo)) & (r.index <= pd.Timestamp(hi))]
    idx = (1.0 + w).cumprod()
    running = idx.cummax()
    dd = idx / running - 1.0
    t = dd.idxmin()
    return {
        "peak_to_trough_pct": round(float(dd.min()) * 100.0, 2),
        "trough_quarter": str(t.date()),
        "n_quarters_in_window": len(w),
    }


def series_stats(r: pd.Series) -> dict:
    v = r.to_numpy(dtype=float)
    worst_i = int(np.argmin(v))
    return {
        "quarterly_sigma_pct": round(float(np.std(v, ddof=1)) * 100.0, 3),
        "acf1": round(acf1(v), 4),
        "worst_quarter_pct": round(float(v[worst_i]) * 100.0, 2),
        "worst_quarter_date": str(r.index[worst_i].date()),
        "mean_quarterly_pct": round(float(v.mean()) * 100.0, 4),
        "episode_drawdowns": {
            name: window_drawdown(r, lo, hi) for name, (lo, hi) in EPISODE_WINDOWS.items()
        },
    }


def asym_fit(y: np.ndarray, x: np.ndarray) -> dict:
    """r_pe = a + b*r_eq + c*r_eq*1{r_eq<0} + d*1{r_eq<0} -- the serenity
    probe's D-preview regression, on quarterly observations."""
    dn = (x < 0.0).astype(float)
    design = np.column_stack([np.ones_like(x), x, x * dn, dn])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    dof = design.shape[0] - design.shape[1]
    s2 = float((resid**2).sum()) / dof
    se = np.sqrt(np.diag(s2 * np.linalg.inv(design.T @ design)))
    names = ["a_intercept", "b_beta_up", "c_downside_kink", "d_down_dummy"]
    return {
        "n": int(design.shape[0]),
        "coefficients": {
            nm: {"value": round(float(c), 4), "t": round(float(c / s), 2)}
            for nm, c, s in zip(names, coef, se, strict=True)
        },
        "implied_downside_beta": round(float(coef[1] + coef[2]), 4),
    }


# --------------------------------------------------------- step 6 machinery


def load_world(world_id: str) -> dict:
    conn = sqlite3.connect(f"file:{(REPO / 'data' / 'ah.db').as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT json FROM worlds WHERE world_id = ?", (world_id,)).fetchone()
        if row is None:
            raise SystemExit(f"world {world_id} not found in data/ah.db")
        return json.loads(row["json"])
    finally:
        conn.close()


def compound_pct(monthly_pct: np.ndarray) -> float:
    return float(np.prod(1.0 + monthly_pct / 100.0) - 1.0) * 100.0


def max_drawdown_pct(monthly_pct: np.ndarray) -> float:
    idx = 100.0 * np.cumprod(1.0 + monthly_pct / 100.0)
    running = np.maximum.accumulate(idx)
    return float((idx / running - 1.0).min()) * 100.0


def gulf_what_if(rows_by_case: dict[str, dict]) -> dict:
    """The Gulf Decade under each candidate pm_buyout row, 200 paths.

    Per path the ensemble is sampled ONCE and the PE tape is assembled
    term-by-term per case (the serenity probe's pe_terms construction); the
    sealed case is asserted bit-identical to run_gen_path on three paths.
    NOTE: the brief suggested passing a modified row into
    adapter._pm_true_monthly_path via its ``rows`` argument, but that argument
    is the ensemble's source-row indices, not the mapping row -- the function
    reads the artifact internally. The term-by-term rebuild (validated against
    run_gen_path exactly) is the correct no-edit route.
    """
    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec
    from ah.gen import registry
    from ah.port.adapter import (
        _PM_ASSET_ORDER,
        PM_SLEEVE_FOR_ASSET,
        RESIDUAL_SEED_OFFSET,
        SEED_STRIDE,
        _source_of,
        _source_series,
        run_gen_path,
    )
    from ah.port.mapping import load_artifact

    doc = load_world(GULF_WORLD_ID)
    ws = WorldSpec.model_validate(doc)
    nw = project_numeric(ws)
    gen = registry.resolve_for_world(nw)
    series = _source_series(_source_of(gen), nw)
    artifact = load_artifact()
    pmr = artifact["pm_residuals"]
    df = float(pmr["df"])
    names = [PM_SLEEVE_FOR_ASSET[a] for a in _PM_ASSET_ORDER]
    corr = np.array([[float(pmr["block_correlation"][a][b]) for b in names] for a in names])
    chol = np.linalg.cholesky(corr)
    j_pe = _PM_ASSET_ORDER.index("pe")
    b_infl = float(artifact["pm_sleeves"]["pm_buyout"]["inflation_passthrough"]["b_infl"])

    per_case: dict[str, dict[str, list[float]]] = {
        c: {"decade": [], "maxdd": [], "beats_eq": [], "crash_year": []} for c in rows_by_case
    }
    eq_decade: list[float] = []
    assert_seeds = {GULF_SEED, GULF_SEED + SEED_STRIDE, GULF_SEED + SEED_STRIDE * (N_PATHS - 1)}

    for k in range(N_PATHS):
        seed = GULF_SEED + SEED_STRIDE * k
        ensemble = gen.sample(nw, 1, seed)
        rows = np.asarray(ensemble.row_indices)[0]
        months = ensemble.months
        reg = {
            "equity_mkt": ensemble.factor("equity_mkt")[0],
            "smb": ensemble.factor("smb")[0],
            "hml": ensemble.factor("hml")[0],
            "mom": ensemble.factor("mom")[0],
            "d_level": series["d_level"][rows],
            "d_slope": series["d_slope"][rows],
            "d_ig": series["d_ig"][rows],
        }
        # the adapter's own residual stream, verbatim
        rng = np.random.Generator(np.random.PCG64(seed + RESIDUAL_SEED_OFFSET))
        raw_t = rng.standard_t(df, size=(months, len(_PM_ASSET_ORDER)))
        raw_t = raw_t / math.sqrt(df / (df - 2.0))
        shocks_pe = (raw_t @ chol.T)[:, j_pe]
        # the C1 inflation term (b_infl is CHOSEN, not fitted; identical in
        # every case -- a refit of the measured row does not move it)
        infl_term = -b_infl * (series["cpi_trail_excess"][rows] / 12.0) / 100.0
        eq_pct = reg["equity_mkt"] * 100.0
        eq_dec = compound_pct(eq_pct)
        eq_decade.append(eq_dec)

        for case, row in rows_by_case.items():
            r = np.full(months, float(row["alpha_quarterly"]) / 3.0)
            for name, beta in row["loadings"].items():
                if float(beta) != 0.0:
                    r = r + float(beta) * reg[name]
            r = r + infl_term
            sigma_m = float(row["residual_sigma_annual"]) / np.sqrt(12.0)
            pe = (r + shocks_pe * sigma_m) * 100.0
            if case == "sealed" and seed in assert_seeds:
                actual = run_gen_path(nw, seed).returns["pe"]
                if not np.allclose(pe, actual, rtol=0, atol=1e-12):
                    raise SystemExit(
                        "sealed-row rebuild does not reproduce run_gen_path "
                        f"(seed {seed}, max abs diff {np.abs(pe - actual).max()}) "
                        "-- refusing to report the what-if"
                    )
            per_case[case]["decade"].append(compound_pct(pe))
            per_case[case]["maxdd"].append(max_drawdown_pct(pe))
            per_case[case]["beats_eq"].append(1.0 if compound_pct(pe) > eq_dec else 0.0)
            per_case[case]["crash_year"].append(compound_pct(pe[CRASH_MONTHS]))

    out: dict = {
        "world_id": GULF_WORLD_ID,
        "base_seed": GULF_SEED,
        "n_paths": N_PATHS,
        "seed_stride": SEED_STRIDE,
        "equity": {
            "live_tape_decade_pct": round(eq_decade[0], 2),
            "median_decade_pct": round(float(np.median(eq_decade)), 2),
        },
        "cases": {},
    }
    for case, m in per_case.items():
        a_q = float(rows_by_case[case]["alpha_quarterly"])
        out["cases"][case] = {
            "live_tape_decade_pe_pct": round(m["decade"][0], 2),
            "median_decade_pe_pct": round(float(np.median(m["decade"])), 2),
            "median_pe_max_drawdown_pct": round(float(np.median(m["maxdd"])), 2),
            "n_paths_pe_beats_equity": int(sum(m["beats_eq"])),
            "live_tape_crash_year_pe_pct": round(m["crash_year"][0], 2),
            "median_crash_year_pe_pct": round(float(np.median(m["crash_year"])), 2),
            "alpha_annual_rate_pct": round(((1 + a_q / 3.0) ** 12 - 1) * 100.0, 2),
        }
    return out


# ---------------------------------------------------------------------- main


def main() -> None:
    mod = load_v12_module()

    catalog = Catalog(REPO / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage in the shared catalog -- stopping (read-only rule)")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))

    members = pm_sleeve_members()["pm_buyout"]
    composite = raw_composite(access, members)
    obs = composite.to_numpy(dtype=float)
    xq = mod._regressor_frame(access)
    spec = mod.pm_constraints()["pm_buyout"]

    # ---------------- Step 0: the calibration gate (silent until it passes)
    full_fit = glm_ma(obs)
    baseline = fit_mapping_row(mod, pd.Series(full_fit.truth, index=composite.index), xq, spec)
    checks = {
        "alpha_quarterly": round(baseline["alpha_quarterly"], 6),
        "equity_mkt": round(baseline["loadings"]["equity_mkt"], 4),
        "d_ig": round(baseline["loadings"]["d_ig"], 4),
        "residual_sigma_annual": round(baseline["residual_sigma_annual"], 4),
        "r2_train_val": round(baseline["r2_train_val"], 3),
    }
    theta_ok = full_fit.k == 1 and np.allclose(full_fit.theta, FULL_SAMPLE_THETA, atol=5e-5)
    mismatches = {k: (checks[k], SEALED[k]) for k in SEALED if checks[k] != SEALED[k]}
    if mismatches or not theta_ok:
        raise SystemExit(
            "STEP 0 CALIBRATION FAILED -- every downstream number would be "
            f"meaningless. theta_ok={theta_ok} (got k={full_fit.k}, "
            f"theta={[round(t, 4) for t in full_fit.theta]}); "
            f"row mismatches (got, sealed): {mismatches}; vintage={vintage}"
        )
    print(f"STEP 0 PASS: sealed pm_buyout row reproduced exactly (vintage {vintage})")
    print(f"  theta full-sample: k={full_fit.k}, theta={[float(t) for t in full_fit.theta]}")
    print(f"  row: {checks}")

    # ---------------- Step 1: buyout's own calm/stress split (Variant 1)
    mask_s = stress_mask_for(access, composite.index)
    mask = mask_s.to_numpy()
    stress_quarters = [str(d.date()) for d in composite.index[mask]]
    episodes = contiguous_episodes(composite.index, mask)
    calm_fit = glm_ma(obs[~mask])
    stress_fit = glm_ma(obs[mask])
    calm_prefall = prefallback_theta(obs[~mask])
    stress_prefall = prefallback_theta(obs[mask])
    print(f"STEP 1: stress quarters n={int(mask.sum())}, calm n={int((~mask).sum())}")
    print(f"  calm theta: {theta_summary(calm_fit)} (pre-fallback grid: {calm_prefall})")
    print(f"  stress theta: {theta_summary(stress_fit)} (pre-fallback grid: {stress_prefall})")

    # leave-one-episode-out on the stress side
    loo: dict[str, dict] = {}
    for ep in episodes:
        label = f"{ep[0][:4]}" if ep[0][:4] == ep[-1][:4] else f"{ep[0][:4]}-{ep[-1][2:4]}"
        keep = mask.copy()
        for d in ep:
            keep[composite.index.get_loc(pd.Timestamp(d))] = False
        sub = glm_ma(obs[keep])
        loo[label] = {"n_stress_left": int(keep.sum()), **theta_summary(sub)}
    loo_theta0 = [v["theta"][0] for v in loo.values()]
    loo_range = (min(loo_theta0), max(loo_theta0))
    print(f"  leave-one-episode-out stress theta0 range: {loo_range}")

    step1 = {
        "stress_indicator": "fred.USREC via DataAccess.train_val, reindex+ffill (_stress_split)",
        "n_stress_quarters": int(mask.sum()),
        "n_calm_quarters": int((~mask).sum()),
        "stress_quarter_list": stress_quarters,
        "episodes": [{"quarters": ep} for ep in episodes],
        "splices_in_stress_subsample": count_splices(mask),
        "splices_in_calm_subsample": count_splices(~mask),
        "splice_caveat": (
            "the house _stress_split concatenates non-contiguous quarters; each "
            "splice fabricates one adjacent pair the ACF objective treats as real, "
            "biasing theta on both sides -- worst for the stress side, whose "
            "sample is mostly seams"
        ),
        "calm_fit": theta_summary(calm_fit),
        "calm_fit_prefallback_grid": calm_prefall,
        "stress_fit": theta_summary(stress_fit),
        "stress_fit_prefallback_grid": stress_prefall,
        "leave_one_episode_out_stress": loo,
        "loo_stress_theta0_range": [round(loo_range[0], 4), round(loo_range[1], 4)],
    }

    # ---------------- Step 2: the transferred stickiness (Variant 2, ASSUMED)
    t0_calm_v2 = FULL_SAMPLE_THETA[0]
    t0_stress_v2 = t0_calm_v2 * (1.0 - GELTNER_STICKINESS)
    v2_theta_stress = [t0_stress_v2, 1.0 - t0_stress_v2]
    t0_calm_split = float(calm_fit.theta[0])
    t0_stress_alt = t0_calm_split * (1.0 - GELTNER_STICKINESS)
    step2 = {
        "stickiness_transferred": GELTNER_STICKINESS,
        "stickiness_label": "ASSUMED (pooled over pm_infra+pm_re_value_add; buyout NOT in pool)",
        "theta_calm": FULL_SAMPLE_THETA,
        "theta_stress": [round(t, 6) for t in v2_theta_stress],
        "alternative_calm_value": {
            "calm_split_theta0": round(t0_calm_split, 4),
            "implied_stress_theta0": round(t0_stress_alt, 6),
            "materially_different": bool(abs(t0_calm_split - t0_calm_v2) > 0.05),
        },
    }
    print(
        f"STEP 2: transferred theta_stress = {[round(t, 4) for t in v2_theta_stress]} "
        f"(stickiness 0.4508 ASSUMED)"
    )

    # ---------------- Step 3: reconstructions
    # self-test: the time-varying inverse must equal _recover_truth when both
    # states carry the same theta
    test_theta = np.array([0.7, 0.2, 0.1])
    ref = _recover_truth(obs, test_theta)
    tv = recover_truth_tv(obs, list(test_theta), list(test_theta), mask)
    assert np.allclose(ref, tv, rtol=0, atol=1e-12), "time-varying inverse fails constant case"

    truth_current = pd.Series(full_fit.truth, index=composite.index)
    if stress_fit.fell_back:
        # the stress side saying "no smoothing" would mean C is unsupported
        # from inside this repo; the MA reconstruction is then undefined and
        # THAT is the report. (The calm side is handled below.)
        raise SystemExit(
            "STRESS-side fit fell back to Geltner (no smoothing detected in "
            "stress quarters) -- Variant 1 is unidentifiable; this IS the finding"
        )
    v1_theta_stress = [float(t) for t in stress_fit.theta]
    # The CALM side fell back at the boundary (theta_0 ~ 1): the estimator's
    # own verdict is "no smoothing detectable in calm quarters". The honest MA
    # representation of that verdict is the identity theta [1, 0]; a Geltner
    # [a, phi] pair is a different recursion (obs lag, not truth lag) and
    # cannot be mixed into an MA reconstruction. Sensitivity: treat the
    # near-identity Geltner pair as MA(1) weights anyway and report the gap.
    if calm_fit.fell_back:
        v1_theta_calm = [1.0, 0.0]
        v1_calm_note = (
            "calm fit hit the boundary (theta_0 ~ 1, no smoothing detected) and "
            "fell back to Geltner; identity [1, 0] used for the calm state"
        )
        sens_calm = [float(calm_fit.theta[0]), float(calm_fit.theta[1])]
    else:
        v1_theta_calm = [float(t) for t in calm_fit.theta]
        v1_calm_note = "calm fit identified MA weights directly"
        sens_calm = v1_theta_calm
    truth_v1 = pd.Series(
        recover_truth_tv(obs, v1_theta_calm, v1_theta_stress, mask), index=composite.index
    )
    truth_v1_sens = pd.Series(
        recover_truth_tv(obs, sens_calm, v1_theta_stress, mask), index=composite.index
    )
    truth_v2 = pd.Series(
        recover_truth_tv(obs, FULL_SAMPLE_THETA, v2_theta_stress, mask), index=composite.index
    )
    step3 = {
        "self_test": "recover_truth_tv == desmooth._recover_truth in the constant case (1e-12)",
        "variant1_theta_used": {
            "calm": v1_theta_calm,
            "stress": v1_theta_stress,
            "calm_note": v1_calm_note,
            "calm_sensitivity_theta": sens_calm,
            "max_abs_diff_identity_vs_geltner_as_ma_pct": round(
                float(np.abs(truth_v1.to_numpy() - truth_v1_sens.to_numpy()).max()) * 100.0, 4
            ),
        },
        "variant2_theta_used_ASSUMED": {"calm": FULL_SAMPLE_THETA, "stress": v2_theta_stress},
        "observed_raw": series_stats(composite),
        "current_unconditional": series_stats(truth_current),
        "variant1_state_dependent_fitted": series_stats(truth_v1),
        "variant1_calm_sensitivity": series_stats(truth_v1_sens),
        "variant2_transferred_stickiness_ASSUMED": series_stats(truth_v2),
    }
    for label in (
        "observed_raw",
        "current_unconditional",
        "variant1_state_dependent_fitted",
        "variant2_transferred_stickiness_ASSUMED",
    ):
        st = step3[label]
        gfc = st["episode_drawdowns"]["2008-09"]["peak_to_trough_pct"]
        print(f"STEP 3 {label}: sigma_q={st['quarterly_sigma_pct']}% GFC dd={gfc}%")

    # ---------------- Step 4: refit the mapping row on each reconstruction
    row_v1 = fit_mapping_row(mod, truth_v1, xq, spec)
    row_v2 = fit_mapping_row(mod, truth_v2, xq, spec)
    step4 = {"sealed_baseline_reproduced": baseline, "variant1": row_v1, "variant2_ASSUMED": row_v2}
    for name, row in (("V1", row_v1), ("V2", row_v2)):
        print(
            f"STEP 4 {name}: alpha_q={row['alpha_quarterly']:.6f} "
            f"beta_eq={row['loadings']['equity_mkt']:.4f} "
            f"d_ig={row['loadings']['d_ig']:.4f} sigma={row['residual_sigma_annual']:.4f} "
            f"r2={row['r2_train_val']:.3f}"
        )

    # ---------------- Step 5: the D-preview (downside kink on reconstructions)
    def aligned(y: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        joined = pd.concat(
            [y.rename("y"), xq["equity_mkt"].rename("x")], axis=1, sort=True
        ).dropna()
        return joined["y"].to_numpy(), joined["x"].to_numpy()

    step5 = {}
    for label, series_y in (
        ("current_unconditional", truth_current),
        ("variant1", truth_v1),
        ("variant2_ASSUMED", truth_v2),
    ):
        y_arr, x_arr = aligned(series_y)
        step5[label] = asym_fit(y_arr, x_arr)
        c = step5[label]["coefficients"]["c_downside_kink"]
        print(f"STEP 5 {label}: c={c['value']} t={c['t']}")

    # ---------------- Step 6: The Gulf Decade what-if
    sealed_row = {
        "alpha_quarterly": SEALED["alpha_quarterly"],
        "loadings": {"equity_mkt": SEALED["equity_mkt"], "d_ig": SEALED["d_ig"]},
        "residual_sigma_annual": SEALED["residual_sigma_annual"],
    }

    def as_case(row: dict) -> dict:
        return {
            "alpha_quarterly": row["alpha_quarterly"],
            "loadings": {k: v for k, v in row["loadings"].items() if v != 0.0},
            "residual_sigma_annual": row["residual_sigma_annual"],
        }

    print("STEP 6: sampling 200 Gulf Decade paths (three cases per path)...")
    step6 = gulf_what_if(
        {"sealed": sealed_row, "variant1": as_case(row_v1), "variant2_ASSUMED": as_case(row_v2)}
    )
    for case, m in step6["cases"].items():
        print(
            f"  {case}: live decade {m['live_tape_decade_pe_pct']}% "
            f"median {m['median_decade_pe_pct']}% "
            f"median maxDD {m['median_pe_max_drawdown_pct']}% "
            f"beats-eq {m['n_paths_pe_beats_equity']}/200 "
            f"crash-year(live) {m['live_tape_crash_year_pe_pct']}%"
        )

    # ---------------- derived headline numbers (arithmetic on measured values)
    t0_calm_used = v1_theta_calm[0]
    t0_stress_used = v1_theta_stress[0]
    loo_no_gfc_t0 = loo["2008-09"]["theta"][0]
    raw_gfc = step3["observed_raw"]["episode_drawdowns"]["2008-09"]["peak_to_trough_pct"]
    cur_gfc = step3["current_unconditional"]["episode_drawdowns"]["2008-09"]["peak_to_trough_pct"]
    v1_gfc = step3["variant1_state_dependent_fitted"]["episode_drawdowns"]["2008-09"][
        "peak_to_trough_pct"
    ]
    v2_gfc = step3["variant2_transferred_stickiness_ASSUMED"]["episode_drawdowns"]["2008-09"][
        "peak_to_trough_pct"
    ]
    # The one external anchor: secondaries clearing at 0.60 of NAV in 2009-H1
    # (docs/data/secondaries.md, flagged ILLUSTRATIVE). If reported NAV sat at
    # (1 + raw_gfc) of peak at the trough and the market cleared claims at 0.60
    # of that reported NAV, the market-implied TRUE peak-to-trough is
    # 1 - 0.60*(1 + raw_gfc). DERIVED from an assumed-illustrative anchor, and
    # clearing prices embed a liquidity discount as well as a NAV opinion --
    # this is an upper bound on the implied crash, stated as such.
    secondaries_implied = (1.0 - 0.60 * (1.0 + raw_gfc / 100.0)) * -100.0
    derived = {
        "implied_buyout_own_stickiness": round(1.0 - t0_stress_used / t0_calm_used, 4),
        "geltner_pool_stickiness_for_comparison_ASSUMED_elsewhere": GELTNER_STICKINESS,
        "implied_stickiness_without_gfc_episode": round(1.0 - loo_no_gfc_t0 / t0_calm_used, 4),
        "gfc_peak_to_trough_pct": {
            "raw_reported_index": raw_gfc,
            "current_unconditional_truth": cur_gfc,
            "variant1": v1_gfc,
            "variant2_ASSUMED": v2_gfc,
            "v1_minus_current_pp": round(v1_gfc - cur_gfc, 2),
        },
        "secondaries_2009H1_implied_true_peak_to_trough_pct": round(secondaries_implied, 1),
        "secondaries_anchor_label": (
            "DERIVED from the 0.60-of-NAV 2009-H1 clearing price in "
            "docs/data/secondaries.md, itself flagged 'illustrative'; includes "
            "whatever liquidity discount the seller ate, so it bounds the "
            "market-implied crash from above"
        ),
        "alpha_annual_pct": {
            "sealed": round(baseline["alpha_annualised_as_adapter_applies_it_pct"], 2),
            "variant1": round(row_v1["alpha_annualised_as_adapter_applies_it_pct"], 2),
            "variant2_ASSUMED": round(row_v2["alpha_annualised_as_adapter_applies_it_pct"], 2),
        },
        "beta_eq": {
            "sealed": round(baseline["loadings"]["equity_mkt"], 4),
            "variant1": round(row_v1["loadings"]["equity_mkt"], 4),
            "variant2_ASSUMED": round(row_v2["loadings"]["equity_mkt"], 4),
        },
    }

    # ---------------- write the sidecar
    out = {
        "run_date": RUN_DATE,
        "branch": "pe-desmooth-01",
        "campaign_vintage_id": str(vintage),
        "measurement_only": True,
        "labels": {
            "measured": "fitted on train_val data by this script or the sealed estimator",
            "derived": "arithmetic on measured values",
            "assumed": "the 0.4508 stickiness transfer (Variant 2) and everything downstream",
        },
        "sealed_target_row": SEALED,
        "step0_calibration": {
            "pass": True,
            "reproduced": checks,
            "full_sample_theta": theta_summary(full_fit),
            "n_quarters": baseline["n_quarters"],
            "window": [str(composite.index[0].date()), str(composite.index[-1].date())],
        },
        "step1_variant1_fit": step1,
        "step2_variant2_transfer": step2,
        "step3_reconstructions": step3,
        "step4_refit_rows": step4,
        "step5_d_preview": step5,
        "step6_gulf_decade_what_if": step6,
        "derived_headlines": derived,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_JSON.relative_to(REPO)}")
    catalog.close()


if __name__ == "__main__":
    main()
