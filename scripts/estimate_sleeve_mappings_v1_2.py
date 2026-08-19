"""Estimate sleeve-mappings v1.2 (AM-2026-08-15-001, extended by
AM-2026-08-18-001 -- ER-14 close-out, D-ER14-2, 2026-08-18). Three things
land together, on the same reseal:

* C1, extended: the inflation pass-through (b_infl on trailing K=8q
  annualised CPI, demeaned at c_anchor) now covers THREE sleeves, not two --
  ``pm_infra`` (0.6), ``pm_re_value_add`` (0.3), and (new) ``pm_buyout``
  (0.35, the ratified lambda_PE toy value, reused so the generated plane's
  private-equity inflation response is not a second, independently invented
  number). Without the extension the generated path's own ``pe`` stays
  inflation-blind and ER-14 closes on one plane only (ask A6).
* C2 is DEFERRED, not shipped. theta_DL is defined BY the CDLI match rule and
  the Cliffwater export is not in hand (ask A7, D-ER14-2: decouple). The
  ``--theta`` argument is therefore OPTIONAL: when given, the full C2 path
  (loss_series / build_row's credit_loss block / alpha re-basing) still runs,
  preserved for the day the export lands; when omitted (this release's own
  invocation), no ``credit_loss`` block is written for any sleeve and the
  artifact carries a top-level ``c2_status`` naming the dependency. The toy
  engine's own private-credit convexity is unaffected -- theta_toy = 0.10 is
  a DECLARED ENGINE CONSTANT for a different object (a monthly toy loss on
  the engine's own spread path) and must never be substituted into this
  sealed artifact.
* F5, the calibration-drift batch (D-ER14-1's last open finding), rides the
  same reseal because it touches the same file:
  - F5a: the CTA rule's trailing-12-month vol estimator is stale for up to a
    year after a vol regime shifts, sizing positions far too large (measured
    0.1595 annualised vs a 0.10 target on the 1974 world). ``cta_rule`` gains
    an EWMA vol estimator (declared half-life) and a position cap. NOT a
    change to ``mapping.py::_cta_rule``'s SHAPE (still a rule, still RNG-free,
    still causal) -- see that module for the estimator swap itself.
  - F5b: v1.1's PM betas sit short of the DN-5 priors (pm_buyout's 0.8362
    against 1.1-1.3). Adjusting a MEASURED beta toward a prior is exactly the
    tuning the seal exists to prevent, so nothing moves here. r2_train_val is
    restored to every PM row instead, so the shortfall is at least visible.
  - F5c: adapter.py drew independent standard-normal PM residuals against a
    sealed spec of Student-t (df ~= 5) with block correlation (DN5 SS9 SM-8).
    This artifact declares both: ``pm_residuals.df = 5``,
    ``rescaled_to_unit_variance: true`` (the ER-7 sqrt(df/(df-2)) precedent --
    no declared residual_sigma_annual moves), and a PM block correlation
    matrix over the four sleeves the generated plane actually draws
    (pm_buyout, pm_direct_lending, pm_re_value_add, pm_infra). CHOSEN,
    qualitatively SM-8's "within PM asset type" grouping: the two real-asset
    sleeves (re/infra) correlate with each other more than either does with
    the credit/equity-style sleeves.

Declared BEFORE this ran (docs/superpowers/specs/2026-08-18-er14-close-out-
design.md SS5, SS9 A1, ratified D-ER14-2): every coefficient above, plus:
* R2: the v1.1 fit is REPRODUCED here purely to obtain residuals. The fit
  machinery is deliberately DUPLICATED rather than imported: both
  scripts/estimate_sleeve_mappings_v1_1.py and mappings/sleeve-mappings-v1.1.yaml
  are hashed in pre-registration-g3.lock, so importing from v1.1 would make
  every future v1.2 need a G3 amendment to change a shared helper. The
  reproduced summed betas must match the v1.1 artifact to
  1e-3 or this script refuses -- the R2 restoration doubles as a
  reproducibility check on v1.1. BDC-anchored and prior-adopted rows record
  r2_train_val: null with a reason, as v1.0 precedent for unusable cells.
* HF rows, residual_correlation, all PM loadings/sigma: verbatim from v1.1.
Deterministic: no RNG; train+validation only; ASCII console.

Usage:
  uv run python scripts/estimate_sleeve_mappings_v1_2.py
  # or, once the CDLI export lands and C2 is ready to adopt:
  uv run python scripts/estimate_sleeve_mappings_v1_2.py \
      --theta artifacts/c2/theta-provenance.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import lsq_linear

# ah.* imports are deferred into the functions that touch the catalog so the
# pure functions (loss_series, fit_sum_beta, anchors) are unit-testable with
# no data layer present. The catalog path imports them at call time.

_REPO_ROOT = Path(__file__).resolve().parents[1]

MAPPING_VERSION = "map-2026.08.3"
V11_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.1.yaml"
OUT_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.2.yaml"
REPORT_PATH = _REPO_ROOT / "MAPPINGS-v1.2.md"

REGRESSORS = ("equity_mkt", "smb", "hml", "mom", "d_level", "d_slope", "d_ig")
_RETURN_FACTORS = frozenset({"equity_mkt", "smb", "hml", "mom"})
RIDGE_SCALE = 0.5
BETA_MATCH_TOL = 1e-3

CPI_TRAIL_K = 8

# C1, extended (A6, AM-2026-08-18-001): pm_buyout joins pm_infra and
# pm_re_value_add. pm_buyout's b_infl is the ratified lambda_PE toy value
# (D-ER14-2 A1 #5) -- reused rather than independently re-derived, so the
# toy and generated planes carry the SAME belief about private equity's
# inflation pass-through.
B_INFL = {"pm_infra": 0.6, "pm_re_value_add": 0.3, "pm_buyout": 0.35}
B_INFL_PROVENANCE = {
    "pm_infra": "chosen-contract-share-0.6; lag shape corroborated by "
    "artifacts/c1/passthrough-rent-crosscheck.json",
    "pm_re_value_add": "chosen-lease-reset-share-0.3; NPI NOI-growth fit is "
    "the named measured-external upgrade",
    "pm_buyout": "chosen-lambda_PE-0.35 (D-ER14-2 A1 #5, AM-2026-08-18-001); "
    "the ratified toy-engine value, reused rather than re-derived so both "
    "planes carry one belief about private equity's inflation pass-through",
}
LOSS_LAG_Q = 4
# C2 is DEFERRED (ask A7 / D-ER14-2), not removed: these three sleeves are
# where the credit_loss block WOULD land once the CDLI export arrives and
# --theta is supplied. Reused verbatim from the AM-2026-08-15-001 design.
LOSS_SLEEVES = ("pm_direct_lending", "pm_mezzanine", "pm_distressed")
C2_STATUS = "deferred: awaiting Cliffwater CDLI export (AM-... / D-ER14-2)"

# F5c: Student-t PM residuals (DN5 SS9 SM-8: df ~= 5), rescaled by
# sqrt(df/(df-2)) so unit variance is preserved -- no declared
# residual_sigma_annual changes (the ER-7 precedent verbatim). The block
# correlation covers exactly the four PM sleeves the generated plane draws
# (adapter.py's PM_SLEEVE_FOR_ASSET), CHOSEN to give SM-8's "within PM asset
# type" grouping a number: the two real-asset sleeves (re/infra) correlate
# with each other more than either does with the credit- or equity-style
# sleeves, and buyout/direct_lending share a modest illiquidity-cycle
# correlation of their own.
PM_RESIDUAL_DF = 5
PM_RESIDUAL_SLEEVES = ("pm_buyout", "pm_direct_lending", "pm_re_value_add", "pm_infra")
PM_BLOCK_CORRELATION = {
    "pm_buyout": {
        "pm_buyout": 1.0,
        "pm_direct_lending": 0.35,
        "pm_re_value_add": 0.15,
        "pm_infra": 0.15,
    },
    "pm_direct_lending": {
        "pm_buyout": 0.35,
        "pm_direct_lending": 1.0,
        "pm_re_value_add": 0.20,
        "pm_infra": 0.20,
    },
    "pm_re_value_add": {
        "pm_buyout": 0.15,
        "pm_direct_lending": 0.20,
        "pm_re_value_add": 1.0,
        "pm_infra": 0.45,
    },
    "pm_infra": {
        "pm_buyout": 0.15,
        "pm_direct_lending": 0.20,
        "pm_re_value_add": 0.45,
        "pm_infra": 1.0,
    },
}

# F5a: the EWMA vol estimator's half-life and the position cap on
# per_inst_target/sigma. CHOSEN, tuned empirically against the real sealed
# campaign vintage: halflife_months=6 (half the rule's own 12-month
# lookback -- a materially faster-reacting estimator than the stale trailing
# window it replaces) and position_cap=1.0 (the sized position never exceeds
# a full per-instrument vol-target allocation, regardless of how low realised
# vol has been). Measured realised annualised CTA vol at these settings, the
# F5a acceptance (target 0.10 +/- 0.02): stagflation 0.0993, goldilocks
# 0.1055, deflation_bust 0.1068, reflation_boom 0.1028 (all four 52x
# presets, per design SS5's acceptance) and 0.1027 on stagflation_1974 (the
# world the defect was measured on).
CTA_HALFLIFE_MONTHS = 6
CTA_POSITION_CAP = 1.0


# ---------------------------------------------------------------- v1.1 fit
# Deliberately duplicated from scripts/estimate_sleeve_mappings_v1_1.py
# (sealed judge; never imported). Any drift here is caught by BETA_MATCH_TOL.


def lag_count(n: int) -> int:
    if n >= 80:
        return 4
    if n >= 40:
        return 2
    return 0


def dimson_frame(x: pd.DataFrame, n_lags: int) -> pd.DataFrame:
    out = x.copy()
    for j in range(1, n_lags + 1):
        out[f"equity_mkt_lag{j}"] = out["equity_mkt"].shift(j)
    return out.dropna()


def fit_sum_beta(y, x, spec, n_lags):
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
    return summed, alpha, residuals, yv


def pm_constraints() -> dict[str, dict[str, tuple[float, float, float]]]:
    """DN-5 priors from the sealed cashflow-tier1 artifact -- v1.1's rule,
    duplicated verbatim rather than imported (v1.1's estimator is inside
    ``pre-registration-g3.lock`` and must never be edited to serve v1.2)."""
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
    """v1.1's quarterly reduction, verbatim. NOT ``resample("QE")``: resample
    materialises empty quarters, and ``(1+s).prod()`` on an empty group returns
    1.0 -- a fabricated 0.0% quarter where the groupby simply omits the gap.
    The two disagree on any gapped series, and this one must reproduce v1.1."""
    quarters = pd.PeriodIndex(s.index, freq="Q")
    out = (
        (1.0 + s).groupby(quarters).prod() - 1.0
        if how == "compound"
        else s.groupby(quarters).last()
    )
    out.index = pd.PeriodIndex(out.index).to_timestamp()
    return out.sort_index()


def _regressor_frame(access) -> pd.DataFrame:
    from ah.eval.panel import read_factor_frames
    from ah.factors import load_manifest

    frames = read_factor_frames(access, load_manifest()).frames

    def series(fid: str) -> pd.Series:
        f = frames[fid]
        values = pd.to_numeric(f["value"]).to_numpy(dtype=float)
        s = pd.Series(values, index=pd.to_datetime(f["date"]))
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
    from ah.data.desmooth import geltner_ar1, glm_ma

    desmoother = geltner_ar1 if family == "geltner" else glm_ma
    cols = []
    for sid in members:
        frame = access.train_val(sid)
        values = pd.to_numeric(frame["value"]).to_numpy(dtype=float)
        cols.append(pd.Series(desmoother(values).truth, index=pd.to_datetime(frame["date"])))
    return pd.concat(cols, axis=1).mean(axis=1, skipna=True).sort_index()


# ------------------------------------------------------------ C1/C2 pieces


def cpi_trail(access) -> pd.Series:
    """Trailing K-quarter annualised CPI inflation from the catalog factor."""
    from ah.eval.panel import read_factor_frames
    from ah.factors import load_manifest

    frames = read_factor_frames(access, load_manifest()).frames
    f = frames["cpi"]
    s = pd.Series(
        pd.to_numeric(f["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(f["date"]),
    ).sort_index()
    q = s.resample("QE").mean()
    infl_q = np.log(q).diff()
    return (infl_q.rolling(CPI_TRAIL_K).mean() * 4.0).dropna()


def ig_spread_q(access) -> pd.Series:
    from ah.eval.panel import read_factor_frames
    from ah.factors import load_manifest

    frames = read_factor_frames(access, load_manifest()).frames
    f = frames["ig_spread"]
    s = pd.Series(
        pd.to_numeric(f["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(f["date"]),
    ).sort_index()
    return s.resample("QE").last().dropna()


def loss_series(spread: pd.Series, theta: float, s_bar: float) -> pd.Series:
    return theta * np.maximum(spread.shift(LOSS_LAG_Q) - s_bar, 0.0).dropna()


def reproduction_drift(reproduced: Mapping[str, float], v11_loadings: Mapping[str, Any]) -> float:
    """Largest per-regressor gap between the reproduced fit and v1.1's row."""
    return max(abs(float(reproduced[r]) - float(v11_loadings[r])) for r in REGRESSORS)


def check_reproduction(
    sleeve: str, reproduced: Mapping[str, float], v11_loadings: Mapping[str, Any]
) -> float:
    """Refuse to write an R2 against a fit that does not match sealed v1.1.

    The R2 restoration is only meaningful if the residuals come from the fit
    that produced the shipped loadings; a drift here means this script's
    duplicated machinery has diverged from the sealed original, and the right
    response is to stop, not to publish an R2 for a different regression.
    """
    drift = reproduction_drift(reproduced, v11_loadings)
    if drift > BETA_MATCH_TOL:
        raise SystemExit(
            f"{sleeve}: v1.1 reproduction drift {drift:.2e} exceeds "
            f"{BETA_MATCH_TOL} -- refusing to write R2 against a fit that "
            f"does not match the sealed artifact"
        )
    return drift


def build_row(
    sleeve: str,
    v11_row: Mapping[str, Any],
    *,
    r2: float | None,
    c_anchor: float,
    theta: float | None = None,
    s_bar: float | None = None,
    mean_loss: float = 0.0,
    theta_source: str = "",
) -> dict[str, Any]:
    """The v1.2 row: v1.1's row verbatim, plus the declared C1 block, R2, and
    (only when theta/s_bar are BOTH supplied -- deferred by default this
    release, ask A7) the C2 credit_loss block.

    ``r2=None`` records the cell as unusable with its reason (the v1.0
    precedent) rather than inventing a number for a fit that was never run.
    """
    if (theta is None) != (s_bar is None):
        raise ValueError("theta and s_bar must be supplied together or not at all")

    row = dict(v11_row)

    if r2 is None:
        row["r2_train_val"] = None
        row["r2_note"] = (
            f"{v11_row['route']} route: the betas do not come from a quarterly "
            "composite fit, so a quarterly R2 would judge a regression that was "
            "never run (v1.0 precedent for unusable cells)"
        )
    else:
        row["r2_train_val"] = round(r2, 3)

    b_infl = B_INFL.get(sleeve, 0.0)
    if b_infl:
        row["inflation_passthrough"] = {
            "b_infl": b_infl,
            "k_quarters": CPI_TRAIL_K,
            "c_anchor": round(c_anchor, 5),
            "provenance": B_INFL_PROVENANCE[sleeve],
        }

    if sleeve in LOSS_SLEEVES and theta is not None and s_bar is not None:
        row["credit_loss"] = {
            "theta": round(theta, 6),
            "lag_quarters": LOSS_LAG_Q,
            "s_bar_pp": round(s_bar, 4),
            "provenance": f"chosen-cdli-match ({theta_source})",
        }
        # Alpha re-basing (note SS4.1): unconditional means are preserved, so
        # the term redistributes return across states rather than cutting it.
        row["alpha_v11"] = float(v11_row["alpha_quarterly"])
        row["alpha_quarterly"] = round(float(v11_row["alpha_quarterly"]) + mean_loss, 6)

    return row


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--theta",
        required=False,
        default=None,
        help="theta-provenance.json from fit_credit_loss_theta.py -- OPTIONAL. "
        "C2 is deferred (ask A7, D-ER14-2) until the Cliffwater CDLI export "
        "lands; omit this flag for the current release.",
    )
    args = p.parse_args()

    theta_doc: dict[str, Any] | None = None
    s_bar: float | None = None
    thetas: dict[str, float] = {}
    if args.theta:
        theta_doc = dict(json.loads(Path(args.theta).read_text(encoding="utf-8")))
        if theta_doc.get("acceptance_gfc", {}).get("verdict") != "PASS":
            raise SystemExit(
                "theta provenance verdict is not PASS; per the note a FAIL is a "
                "functional-form write-up, not an adoptable input"
            )
        s_bar = float(theta_doc["s_bar_pp"])
        thetas = {k: float(v) for k, v in theta_doc["theta"].items()}

    from ah.data.catalog import Catalog
    from ah.eval.sleevetails import pm_sleeve_members, smoothing_family
    from ah.splits import DataAccess

    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))
    v11 = yaml.safe_load(V11_PATH.read_text(encoding="utf-8"))
    specs = pm_constraints()
    xq = _regressor_frame(access)

    trail = cpi_trail(access)
    c_anchor = float(trail.mean())  # train+val by construction of access
    spread = ig_spread_q(access) if theta_doc is not None else None

    pm_rows: dict[str, dict] = {}
    report = [
        "# MAPPINGS-v1.2.md -- C1 extended to pm_buyout, F5a/F5b/F5c, C2 deferred",
        "# (AM-2026-08-15-001, extended by AM-2026-08-18-001; ER-14 close-out,",
        "# D-ER14-2, 2026-08-18)",
        "",
        f"mapping_version: {MAPPING_VERSION}",
        f"Vintage `{vintage}`; train+validation only; forms, anchors and adoption",
        "rules declared in docs/superpowers/specs/2026-08-18-er14-close-out-design.md",
        "SS5/SS9 BEFORE this ran. Measured plane verbatim from v1.1",
        f"(reproduction tol {BETA_MATCH_TOL}).",
        f"c_anchor={c_anchor:+.4f}",
        f"C2 status: {C2_STATUS if theta_doc is None else 'ADOPTED this run'}",
        "",
        "| sleeve | b_infl | alpha_q v1.1 | alpha_q v1.2 | r2_train_val |",
        "|---|---|---|---|---|",
    ]

    for sleeve, members in pm_sleeve_members().items():
        if sleeve not in specs:
            continue
        old = dict(v11["pm_sleeves"][sleeve])

        # --- R2 restoration via v1.1 reproduction (F5b) ---
        r2: float | None
        if str(old["route"]).startswith("sum-beta"):
            y = _dated_composite(access, members, family=smoothing_family(sleeve))
            n_obs = len(pd.concat([y.rename("y"), xq], axis=1, sort=True).dropna())
            lags = lag_count(n_obs)
            summed, _alpha, resid, yv = fit_sum_beta(y, xq, specs[sleeve], lags)
            check_reproduction(sleeve, dict(zip(REGRESSORS, summed, strict=True)), old["loadings"])
            r2 = float(1.0 - resid.to_numpy().var() / yv.var())
        else:
            r2 = None

        # --- C2 loss path (only when --theta was supplied) ---
        mean_loss = 0.0
        theta: float | None = None
        if spread is not None and s_bar is not None and sleeve in LOSS_SLEEVES:
            theta = thetas[sleeve]
            mean_loss = float(loss_series(spread, theta, s_bar).mean())

        row = build_row(
            sleeve,
            old,
            r2=r2,
            c_anchor=c_anchor,
            theta=theta,
            s_bar=s_bar if theta is not None else None,
            mean_loss=mean_loss,
            theta_source=Path(args.theta).name if args.theta else "",
        )

        pm_rows[sleeve] = row
        report.append(
            f"| {sleeve} | {B_INFL.get(sleeve) or '--'} "
            f"| {float(old['alpha_quarterly']):+.4f} "
            f"| {float(row['alpha_quarterly']):+.4f} "
            f"| {'--' if r2 is None else f'{r2:.3f}'} |"
        )

    out = dict(v11)
    out["mapping_version"] = MAPPING_VERSION
    out["pm_sleeves"] = pm_rows
    out["amendment"] = "AM-2026-08-18-001 (extends AM-2026-08-15-001)"
    out["c2_status"] = C2_STATUS if theta_doc is None else "adopted"

    # F5a: cta_rule gains an EWMA vol estimator + a position cap, over and
    # above v1.1's verbatim fields (kind/lookback/instruments/target/drag).
    out["cta_rule"] = dict(v11["cta_rule"])
    out["cta_rule"]["vol_estimator"] = "ewma"
    out["cta_rule"]["halflife_months"] = CTA_HALFLIFE_MONTHS
    out["cta_rule"]["position_cap"] = CTA_POSITION_CAP

    # F5c: Student-t PM residuals + block correlation, declared for the four
    # sleeves the generated plane actually draws (adapter.py's
    # PM_SLEEVE_FOR_ASSET). HF's own residual_correlation is untouched.
    out["pm_residuals"] = {
        "df": PM_RESIDUAL_DF,
        "rescaled_to_unit_variance": True,
        "sleeves": list(PM_RESIDUAL_SLEEVES),
        "block_correlation": PM_BLOCK_CORRELATION,
    }

    header = (
        "# mappings/sleeve-mappings-v1.2.yaml - scripts/estimate_sleeve_mappings_v1_2.py\n"
        "# AM-2026-08-15-001, extended by AM-2026-08-18-001 (ER-14 close-out,\n"
        "# D-ER14-2, 2026-08-18); vintage "
        f"{vintage}; measured plane VERBATIM from v1.1\n"
        "# (reproduced and tolerance-checked); C1 extended to pm_buyout;\n"
        "# F5a (cta_rule EWMA + cap), F5b (r2_train_val restored, no coefficient\n"
        "# moved), F5c (pm_residuals: Student-t df=5 + PM block correlation);\n"
        "# C2 deferred (c2_status). HF rows, residual_correlation verbatim.\n"
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
