"""Estimate sleeve-mappings v1.1 (AM-2026-08-12-001): PM sleeves re-fit with
a lagged (Dimson sum-beta) equity component; HF rows verbatim from v1.0.

Run:  uv run python scripts/estimate_sleeve_mappings_v1_1.py

Declared BEFORE this ran (design note 2026-08-12-pm-remap-design.md):
* Lags on equity_mkt only. n>=80 quarters -> 4 lags; 40<=n<80 -> 2; n<40 ->
  estimation refused, the DN-5 prior row is adopted verbatim and recorded.
* The artifact loading is the SUM of contemporaneous+lag betas: runtime
  applies loadings to TRUE factors, where the appraisal lag does not belong.
* pm_direct_lending is anchored to cliffwater.bdc_ret_m (monthly, listed,
  marked to market): betas and residual sigma estimated there, then
  multiplied by BDC_DELEVER = 0.5 (declared; listed BDCs run ~1x leverage);
  alpha comes from the albourne DL composite mean net of those betas.
* De-smoothing, residual_correlation, cta_rule, HF sleeves: v1.0 verbatim.
Deterministic: no RNG anywhere; train+validation only.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import lsq_linear

from ah.data.catalog import Catalog
from ah.data.desmooth import geltner_ar1, glm_ma
from ah.eval.panel import read_factor_frames
from ah.eval.sleevetails import pm_sleeve_members, smoothing_family
from ah.factors import load_manifest
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

MAPPING_VERSION = "map-2026.08.2"
V10_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.0.yaml"
OUT_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.1.yaml"
REPORT_PATH = _REPO_ROOT / "MAPPINGS-v1.1.md"

REGRESSORS = ("equity_mkt", "smb", "hml", "mom", "d_level", "d_slope", "d_ig")
_RETURN_FACTORS = frozenset({"equity_mkt", "smb", "hml", "mom"})
RIDGE_SCALE = 0.5

BDC_SERIES = "cliffwater.bdc_ret_m"
BDC_DELEVER = 0.5
BDC_SLEEVE = "pm_direct_lending"


def lag_count(n: int) -> int:
    """The declared lag rule. 0 means: estimation refused, prior adopted."""
    if n >= 80:
        return 4
    if n >= 40:
        return 2
    return 0


def dimson_frame(x: pd.DataFrame, n_lags: int) -> pd.DataFrame:
    """Append equity_mkt lag columns; drop rows without a full lag history."""
    out = x.copy()
    for j in range(1, n_lags + 1):
        out[f"equity_mkt_lag{j}"] = out["equity_mkt"].shift(j)
    return out.dropna()


def fit_sum_beta(
    y: pd.Series,
    x: pd.DataFrame,
    spec: dict[str, tuple[float, float, float]],
    n_lags: int,
) -> tuple[np.ndarray, float, pd.Series, np.ndarray]:
    """Bounded ridge fit (v1.0's machinery) over the Dimson design.

    Returns (summed_betas_over_REGRESSORS, alpha, residuals, per_lag_betas).
    summed_betas[i] is the REGRESSORS[i] beta, with equity_mkt as the Dimson
    sum of the contemporaneous and all lag coefficients. Lags are bounded
    [0, inf) with ridge prior 0 — shrinkage never invents lag beta.
    """
    design_frame = dimson_frame(x, n_lags)
    joined = pd.concat([y.rename("y"), design_frame], axis=1, sort=True).dropna()
    yv = joined["y"].to_numpy()

    lag_cols = [f"equity_mkt_lag{j}" for j in range(1, n_lags + 1)]
    full_spec = dict(spec)
    for c in lag_cols:
        full_spec[c] = (0.0, float("inf"), 0.0)
    cols = list(REGRESSORS) + lag_cols
    free = [c for c in cols if not (full_spec[c][0] == 0.0 == full_spec[c][1])]

    design = joined[free].to_numpy()
    n, k = design.shape
    lo = np.array([full_spec[c][0] for c in free])
    hi = np.array([full_spec[c][1] for c in free])
    prior = np.array([full_spec[c][2] for c in free])

    y_c = yv - yv.mean()
    x_c = design - design.mean(axis=0)
    lam = RIDGE_SCALE * k / n
    scale = np.std(x_c, axis=0)
    scale[scale == 0.0] = 1.0
    aug_a = np.vstack([x_c, np.sqrt(lam * n) * np.diag(scale)])
    aug_b = np.concatenate([y_c, np.sqrt(lam * n) * scale * prior])
    result = lsq_linear(aug_a, aug_b, bounds=(lo, hi))

    beta_all = np.array([result.x[free.index(c)] if c in free else 0.0 for c in cols])
    full_design = joined[cols].to_numpy()
    alpha = float(yv.mean() - full_design.mean(axis=0) @ beta_all)
    residuals = pd.Series(yv - alpha - full_design @ beta_all, index=joined.index)

    per_lag = beta_all[len(REGRESSORS) :]
    summed = beta_all[: len(REGRESSORS)].copy()
    summed[REGRESSORS.index("equity_mkt")] += float(per_lag.sum())
    return summed, alpha, residuals, per_lag


def delever(loadings: dict[str, float], sigma: float, factor: float):
    """Scale betas and residual sigma by the declared leverage factor."""
    return {k: v * factor for k, v in loadings.items()}, sigma * factor


def merge_artifact(v10_doc: dict, pm_rows: dict) -> dict:
    """v1.1 = v1.0 with pm_sleeves replaced; everything else verbatim."""
    out = dict(v10_doc)
    out["mapping_version"] = MAPPING_VERSION
    out["pm_sleeves"] = pm_rows
    return out


def pm_constraints() -> dict[str, dict[str, tuple[float, float, float]]]:
    """DN-5 priors from the sealed cashflow-tier1 artifact (v1.0's rule)."""
    doc = yaml.safe_load(
        (_REPO_ROOT / "mappings" / "cashflow-tier1-v1.0.yaml").read_text(encoding="utf-8")
    )
    inf = float("inf")
    out: dict[str, dict[str, tuple[float, float, float]]] = {}
    for sleeve, priors in (doc.get("pm_growth_loadings") or {}).items():
        spec: dict[str, tuple[float, float, float]] = {}
        for regressor in REGRESSORS:
            prior = float(priors.get(regressor, 0.0))
            if prior > 0:
                spec[regressor] = (0.0, inf, prior)
            elif prior < 0:
                spec[regressor] = (-inf, 0.0, prior)
            else:
                spec[regressor] = (0.0, 0.0, 0.0)
        out[sleeve] = spec
    return out


def _to_quarterly(s: pd.Series, how: str) -> pd.Series:
    quarters = pd.PeriodIndex(s.index, freq="Q")
    out = (
        (1.0 + s).groupby(quarters).prod() - 1.0
        if how == "compound"
        else s.groupby(quarters).last()
    )
    out.index = pd.PeriodIndex(out.index).to_timestamp()
    return out.sort_index()


def _regressor_frame(access: DataAccess, *, quarterly: bool) -> pd.DataFrame:
    frames = read_factor_frames(access, load_manifest()).frames

    def series(fid: str) -> pd.Series:
        f = frames[fid]
        numeric = pd.to_numeric(f["value"])
        values: np.ndarray = numeric.to_numpy(dtype=float)  # type: ignore[reportAttributeAccessIssue,reportArgumentType]
        s = pd.Series(values, index=pd.to_datetime(f["date"]))
        if not quarterly:
            return s
        return _to_quarterly(s, "compound" if fid in _RETURN_FACTORS else "last")

    x = pd.DataFrame(
        {
            "equity_mkt": series("equity_mkt"),
            "smb": series("smb"),
            "hml": series("hml"),
            "mom": series("mom"),
            "d_level": series("ust_10y").diff(),
            "d_slope": (series("ust_10y") - series("ust_2y")).diff(),
            "d_ig": series("ig_spread").diff(),
        }
    )
    return x.dropna()


def _dated_composite(access, members, *, family: str) -> pd.Series:
    desmoother = geltner_ar1 if family == "geltner" else glm_ma
    cols = []
    for sid in members:
        frame = access.train_val(sid)
        numeric = pd.to_numeric(frame["value"])
        values: np.ndarray = numeric.to_numpy(dtype=float)  # type: ignore[reportAttributeAccessIssue,reportArgumentType]
        cols.append(pd.Series(desmoother(values).truth, index=pd.to_datetime(frame["date"])))
    return pd.concat(cols, axis=1).mean(axis=1, skipna=True).sort_index()


def _sigma_annual(resid: pd.Series, periods_per_year: float) -> float:
    return float(resid.std(ddof=1) * np.sqrt(periods_per_year))


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))
    v10 = yaml.safe_load(V10_PATH.read_text(encoding="utf-8"))
    specs = pm_constraints()
    xq = _regressor_frame(access, quarterly=True)
    xm = _regressor_frame(access, quarterly=False)

    pm_rows: dict[str, dict] = {}
    report = [
        "# MAPPINGS-v1.1.md — PM sum-beta re-estimation (AM-2026-08-12-001)",
        "",
        f"Vintage `{vintage}`; train+validation only; lag rule and BDC anchor",
        "declared in docs/superpowers/specs/2026-08-12-pm-remap-design.md",
        "BEFORE this ran. HF sleeves verbatim from v1.0.",
        "",
        "| sleeve | route | n | lags | b_mkt v1.0 | b_mkt v1.1 | per-lag | alpha_q v1.0 | alpha_q v1.1 | sigma_ann |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for sleeve, members in pm_sleeve_members().items():
        if sleeve not in specs:
            continue
        old = v10["pm_sleeves"][sleeve]
        prior_row = specs[sleeve]

        if sleeve == BDC_SLEEVE:
            # market-priced anchor: monthly regression on the listed BDC index
            frame = access.train_val(BDC_SERIES)
            bdc_numeric = pd.to_numeric(frame["value"])
            bdc_values: np.ndarray = bdc_numeric.to_numpy(dtype=float)  # type: ignore[reportAttributeAccessIssue,reportArgumentType]
            y_bdc = pd.Series(bdc_values, index=pd.to_datetime(frame["date"]))
            inf = float("inf")
            bdc_spec = {r: (-inf, inf, 0.0) for r in REGRESSORS}
            summed, _a, resid, per_lag = fit_sum_beta(y_bdc, xm, bdc_spec, n_lags=0)
            loadings: dict[str, float] = dict(zip(REGRESSORS, summed, strict=True))
            loadings, sigma = delever(loadings, _sigma_annual(resid, 12.0), BDC_DELEVER)
            # alpha from the asset-level composite, net of the anchored betas
            y_dl = _dated_composite(access, members, family=smoothing_family(sleeve))
            joined = pd.concat([y_dl.rename("y"), xq], axis=1, sort=True).dropna()
            beta_vec = np.array([loadings[r] for r in REGRESSORS])
            alpha = float(
                joined["y"].to_numpy().mean()
                - joined[list(REGRESSORS)].to_numpy().mean(axis=0) @ beta_vec
            )
            n_obs, lags, route = len(y_bdc), 0, "bdc-anchor*0.5"
        else:
            y = _dated_composite(access, members, family=smoothing_family(sleeve))
            n_obs = len(pd.concat([y.rename("y"), xq], axis=1, sort=True).dropna())
            lags = lag_count(n_obs)
            if lags == 0:
                # refused: DN-5 prior adopted verbatim, recorded as such
                loadings = {r: prior_row[r][2] for r in REGRESSORS}
                alpha = float(old["alpha_quarterly"])
                sigma = float(old["residual_sigma_annual"])
                per_lag, route = np.array([]), "prior-adopted"
            else:
                summed, alpha, resid, per_lag = fit_sum_beta(y, xq, prior_row, lags)
                loadings = dict(zip(REGRESSORS, summed, strict=True))
                sigma = _sigma_annual(resid, 4.0)
                route = f"sum-beta({lags})"

        pm_rows[sleeve] = {
            "family": smoothing_family(sleeve),
            "n_quarters": int(n_obs),
            "route": route,
            "alpha_quarterly": round(float(alpha), 6),
            "loadings": {r: round(float(loadings[r]), 4) for r in REGRESSORS},
            "residual_sigma_annual": round(float(sigma), 4),
            "prior_v10": {
                "source": "sleeve-mappings-v1.0.yaml",
                "equity_mkt": float(old["loadings"]["equity_mkt"]),
                "alpha_quarterly": float(old["alpha_quarterly"]),
            },
        }
        report.append(
            f"| {sleeve} | {route} | {n_obs} | {lags} "
            f"| {float(old['loadings']['equity_mkt']):+.3f} "
            f"| {loadings['equity_mkt']:+.3f} "
            f"| {np.array2string(np.round(per_lag, 3))} "
            f"| {float(old['alpha_quarterly']):+.4f} | {alpha:+.4f} | {sigma:.1%} |"
        )

    out = merge_artifact(v10, pm_rows)
    header = (
        "# mappings/sleeve-mappings-v1.1.yaml - scripts/estimate_sleeve_mappings_v1_1.py\n"
        f"# AM-2026-08-12-001; vintage {vintage}; PM rows re-estimated (Dimson\n"
        "# sum-beta / BDC anchor / prior-adopted, per-row 'route'); HF rows,\n"
        "# residual_correlation and cta_rule verbatim from v1.0.\n"
    )
    OUT_PATH.write_text(
        header + yaml.safe_dump(out, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
        newline="\n",
    )
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH.name} + {REPORT_PATH.name} ({len(pm_rows)} PM sleeves)")


if __name__ == "__main__":
    main()
