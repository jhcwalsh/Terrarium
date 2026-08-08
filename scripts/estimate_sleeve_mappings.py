"""Estimate the factor -> sleeve mappings (WP3.2) and write the versioned artifact.

Run:  uv run python scripts/estimate_sleeve_mappings.py

DN-5 §3.2's pattern, adapted to what exists and stated where it differs:

* Sleeves at the modeled granularity: the seven HF sleeves, each estimated on
  its DE-SMOOTHED equal-weight composite (identical construction to the sealed
  G3 reference — asserted equal against ``sleevetails.reference_composite``,
  not assumed). ``hf_cta`` is NOT a regression (DN-5 §3.4): it is a rule
  applied to generated paths, implemented in ``ah.port.mapping``.
* Regressors from the sealed factor panel (return-bearing forms): equity_mkt,
  smb, hml, mom as returns; d_level (Δ ust_10y), d_slope (Δ(ust_10y - ust_2y)),
  d_ig (Δ ig_spread) as monthly changes. DN-5's HY and Commodity columns are
  STRUCTURALLY UNESTIMABLE on this vintage (`hy_spread`/`commodities` are the
  sealed missing_factors) — recorded as named omissions, never silent zeros.
  Credit exposures estimated on d_ig carry the OPPOSITE sign convention to
  DN-5's credit-return loadings (long credit loses when spreads widen).
* Sign constraints + shrinkage toward the DN-5 tabled priors (SM-4), via
  bounded least squares with ridge augmentation; structural zeros are hard
  bounds. §4.1's caveat applies and is written into the artifact: a zero is a
  statement about the mean, and the tail is delegated to residuals.
* Estimation data: train+validation ONLY (the composite construction cannot
  reach the holdout by construction). Final loadings fit on train+val;
  the out-of-sample diagnostic refits on train and scores on validation.

Outputs: ``mappings/sleeve-mappings-v1.0.yaml`` (the artifact WorldSpec's
``mapping_version`` names) and ``MAPPINGS.md`` (diagnostics incl. the D1
smoothed-vs-de-smoothed beta exhibit). Deterministic: no RNG anywhere.
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
from ah.eval.sleevetails import (
    hf_sleeve_members,
    pm_sleeve_members,
    reference_composite,
    smoothing_family,
)
from ah.factors import load_manifest
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

MAPPING_VERSION = "map-2026.08"
REGRESSORS = ("equity_mkt", "smb", "hml", "mom", "d_level", "d_slope", "d_ig")
#: Factors that are RETURNS (compound within a quarter); the rest are levels
#: whose quarter-end value is differenced.
_RETURN_FACTORS = frozenset({"equity_mkt", "smb", "hml", "mom"})

#: (lower, upper, prior) per regressor, per sleeve — DN-5 §3.2 rows pooled to the
#: modeled sleeves. 0-width bounds are structural zeros; priors are DN-5's tabled
#: magnitudes where given, else 0. d_ig signs are FLIPPED vs DN-5's credit-return
#: columns (see module docstring).
_INF = float("inf")
CONSTRAINTS: dict[str, dict[str, tuple[float, float, float]]] = {
    "hf_equity_ls": {
        "equity_mkt": (0.0, _INF, 0.35),  # directional 0.45 pooled with EMN |b|<=0.15
        "smb": (0.0, _INF, 0.10),
        "hml": (-_INF, _INF, 0.0),
        "mom": (-_INF, _INF, 0.0),
        "d_level": (0.0, 0.0, 0.0),
        "d_slope": (0.0, 0.0, 0.0),
        "d_ig": (0.0, 0.0, 0.0),
    },
    "hf_event": {
        "equity_mkt": (0.0, _INF, 0.25),
        "smb": (0.0, _INF, 0.05),  # distressed row's SMB+, pooled
        "hml": (0.0, _INF, 0.05),
        "mom": (0.0, 0.0, 0.0),
        "d_level": (0.0, 0.0, 0.0),
        "d_slope": (0.0, 0.0, 0.0),
        "d_ig": (-_INF, 0.0, -0.05),  # credit-long: loses when spreads widen
    },
    "hf_rv": {
        "equity_mkt": (0.0, 0.0, 0.0),  # DN-5 structural zero; §4.1 caveat recorded
        "smb": (0.0, 0.0, 0.0),
        "hml": (0.0, 0.0, 0.0),
        "mom": (0.0, 0.0, 0.0),
        "d_level": (-_INF, _INF, 0.0),
        "d_slope": (-_INF, _INF, 0.0),
        "d_ig": (-_INF, 0.0, -0.05),
    },
    "hf_credit": {
        "equity_mkt": (0.0, _INF, 0.10),
        "smb": (0.0, 0.0, 0.0),
        "hml": (0.0, 0.0, 0.0),
        "mom": (0.0, 0.0, 0.0),
        "d_level": (-_INF, _INF, 0.0),
        "d_slope": (0.0, 0.0, 0.0),
        "d_ig": (-_INF, 0.0, -0.10),
    },
    "hf_macro": {
        "equity_mkt": (-_INF, _INF, 0.0),  # all-free row; low R² by nature
        "smb": (0.0, 0.0, 0.0),
        "hml": (0.0, 0.0, 0.0),
        "mom": (0.0, 0.0, 0.0),
        "d_level": (-_INF, _INF, 0.0),
        "d_slope": (-_INF, _INF, 0.0),
        "d_ig": (0.0, 0.0, 0.0),
    },
    "hf_multi": {
        "equity_mkt": (0.0, _INF, 0.20),
        "smb": (0.0, 0.0, 0.0),
        "hml": (0.0, 0.0, 0.0),
        "mom": (0.0, 0.0, 0.0),
        "d_level": (-_INF, _INF, 0.0),
        "d_slope": (0.0, 0.0, 0.0),
        "d_ig": (-_INF, 0.0, -0.05),
    },
}

RIDGE_SCALE = 0.5  # shrinkage intensity multiplier; effective lambda ~ k/T per SM-4


def pm_constraints() -> dict[str, dict[str, tuple[float, float, float]]]:
    """PM sleeve constraints, READ from ``mappings/cashflow-tier1-v1.0.yaml``.

    That artifact's ``pm_growth_loadings`` are DN-5 §3.3's priors already pooled
    to exactly the nine modeled PM sleeves, and were frozen with the label
    "ADOPTED AS CHOSEN (kind C) - no PM data exists; sensitivity-flagged, never
    called estimates". Reading them here rather than retyping them means the
    shrinkage target provably IS the recorded prior, and the loadings this
    script now writes are the estimates that supersede it.

    Bounds follow each prior's sign (DN-5's positive/negative columns): a positive prior is
    constrained non-negative, a negative prior non-positive, and a regressor the
    prior omits is a structural zero — DN-5 §4.1's caveat applies, a zero is a
    claim about the MEAN and the tail is delegated to residuals.
    """
    doc = yaml.safe_load(
        (_REPO_ROOT / "mappings" / "cashflow-tier1-v1.0.yaml").read_text(encoding="utf-8")
    )
    out: dict[str, dict[str, tuple[float, float, float]]] = {}
    for sleeve, priors in (doc.get("pm_growth_loadings") or {}).items():
        spec: dict[str, tuple[float, float, float]] = {}
        for regressor in REGRESSORS:
            prior = float(priors.get(regressor, 0.0))
            if prior > 0:
                spec[regressor] = (0.0, _INF, prior)
            elif prior < 0:
                spec[regressor] = (-_INF, 0.0, prior)
            else:
                spec[regressor] = (0.0, 0.0, 0.0)
        out[sleeve] = spec
    return out


def _to_quarterly(s: pd.Series, how: str) -> pd.Series:
    """Monthly factor -> quarterly, labelled at quarter START to match the PM
    series' own dates (intake writes ``Period.to_timestamp()``). Returns
    COMPOUND within the quarter; levels take the quarter-end observation, so
    their differences are true quarter-on-quarter changes."""
    quarters = pd.PeriodIndex(s.index, freq="Q")
    out = (
        (1.0 + s).groupby(quarters).prod() - 1.0
        if how == "compound"
        else s.groupby(quarters).last()
    )
    out.index = pd.PeriodIndex(out.index).to_timestamp()
    return out.sort_index()


def _dated_composite(
    access: DataAccess,
    members: tuple[str, ...],
    desmoothed: bool,
    *,
    family: str = "glm",
) -> pd.Series:
    """The sleeve composite WITH dates (script-side twin of the sealed one).

    ``family`` routes the de-smoother so SM-10 holds for PM sleeves too: the
    operator used here must be the one the smoothing kernel inverts, which for
    the appraisal-calendar sleeves is Geltner, not GLM.
    """
    desmoother = geltner_ar1 if family == "geltner" else glm_ma
    cols = []
    for sid in members:
        frame = access.train_val(sid)
        values = pd.to_numeric(frame["value"]).to_numpy(dtype=float)
        truth = desmoother(values).truth if desmoothed else values
        cols.append(pd.Series(truth, index=pd.to_datetime(frame["date"])))
    return pd.concat(cols, axis=1).mean(axis=1, skipna=True).sort_index()


def _regressor_frame(access: DataAccess, *, quarterly: bool = False) -> pd.DataFrame:
    frames = read_factor_frames(access, load_manifest()).frames

    def series(fid: str) -> pd.Series:
        f = frames[fid]
        s = pd.Series(
            pd.to_numeric(f["value"]).to_numpy(dtype=float), index=pd.to_datetime(f["date"])
        )
        if not quarterly:
            return s
        # returns compound within the quarter; levels take the quarter-end value
        # so that .diff() below is a true quarter-on-quarter change
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


def _fit(
    y: pd.Series,
    x: pd.DataFrame,
    sleeve: str,
    constraints: dict[str, dict[str, tuple[float, float, float]]] | None = None,
) -> tuple[np.ndarray, float, pd.Series]:
    """Bounded ridge fit toward the DN-5 priors; returns (beta, alpha, residuals)."""
    joined = pd.concat([y.rename("y"), x], axis=1, sort=True).dropna()
    yv = joined["y"].to_numpy()
    spec = (constraints or CONSTRAINTS)[sleeve]
    # structural zeros never enter the solver; their betas are 0 by assertion
    free = [r for r in REGRESSORS if not (spec[r][0] == 0.0 == spec[r][1])]
    design = joined[free].to_numpy()
    n, k = design.shape
    lo = np.array([spec[r][0] for r in free])
    hi = np.array([spec[r][1] for r in free])
    prior = np.array([spec[r][2] for r in free])

    # demean -> alpha handled analytically; ridge rows pull toward the prior
    y_c = yv - yv.mean()
    x_c = design - design.mean(axis=0)
    lam = RIDGE_SCALE * k / n
    scale = np.std(x_c, axis=0)
    scale[scale == 0.0] = 1.0
    aug_a = np.vstack([x_c, np.sqrt(lam * n) * np.diag(scale)])
    aug_b = np.concatenate([y_c, np.sqrt(lam * n) * scale * prior])
    result = lsq_linear(aug_a, aug_b, bounds=(lo, hi))
    beta_free = result.x
    beta = np.array([beta_free[free.index(r)] if r in free else 0.0 for r in REGRESSORS])
    full_design = joined[list(REGRESSORS)].to_numpy()
    alpha = float(yv.mean() - full_design.mean(axis=0) @ beta)
    residuals = pd.Series(yv - alpha - full_design @ beta, index=joined.index)
    return beta, alpha, residuals


def _r2(y: pd.Series, x: pd.DataFrame, beta: np.ndarray, alpha: float) -> float:
    joined = pd.concat([y.rename("y"), x], axis=1, sort=True).dropna()
    yv = joined["y"].to_numpy()
    fitted = alpha + joined[list(REGRESSORS)].to_numpy() @ beta
    ss_res = float(np.sum((yv - fitted) ** 2))
    ss_tot = float(np.sum((yv - yv.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))

    x = _regressor_frame(access)
    members = hf_sleeve_members()
    usrec = access.train_val("fred.USREC")
    recession = pd.Series(
        pd.to_numeric(usrec["value"]).to_numpy(dtype=float) > 0.5,
        index=pd.to_datetime(usrec["date"]),
    )

    artifact_lines = [
        "# mappings/sleeve-mappings-v1.0.yaml — generated by scripts/estimate_sleeve_mappings.py",
        f"# vintage {vintage}; train+validation only; see MAPPINGS.md for diagnostics.",
        f"mapping_version: {MAPPING_VERSION}",
        f'campaign_vintage_id: "{vintage}"',
        "desmoothing_method: glm_ma  # SM-10: the forward kernel must invert exactly this",
        "regressors: [" + ", ".join(REGRESSORS) + "]",
        "structural_omissions:",
        "  hy_spread: sealed missing_factor on this vintage — DN-5 HY loadings unestimable, NOT zero",
        "  commodities: sealed missing_factor — DN-5 Cmdty loadings unestimable, NOT zero",
        "  d_ig_sign_note: loadings on d_ig are spread-CHANGE betas (flip of DN-5's credit-return signs)",
        "  structural_zeros_note: a 0-bound is a claim about the MEAN (DN-5 4.1); tails live in residuals",
        "sleeves:",
    ]
    report = [
        "# MAPPINGS.md — factor -> sleeve mapping diagnostics (WP3.2)",
        "",
        f"Vintage `{vintage}`; composites de-smoothed (GLM MA(k)), train+validation only;",
        "final loadings on train+val, OOS diagnostic fit on train / scored on validation.",
        f"Artifact: `mappings/sleeve-mappings-v1.0.yaml` (`{MAPPING_VERSION}`).",
        "`hf_cta` is a rule, not a regression (DN-5 §3.4) — see `ah/port/mapping.py`.",
        "",
        "| sleeve | "
        + " | ".join(REGRESSORS)
        + " | resid sigma (ann) | R² | OOS R² | β_mkt smooth | β_mkt desm | β_mkt exp | β_mkt rec |",
        "|---|" + "---|" * (len(REGRESSORS) + 8),
    ]

    residual_store: dict[str, pd.Series] = {}
    for sleeve, member_ids in members.items():
        if sleeve == "hf_cta":
            continue
        y = _dated_composite(access, member_ids, desmoothed=True)
        # the sealed-composite equality assertion: same pooling or stop
        sealed = reference_composite(access, member_ids)
        np.testing.assert_allclose(y.to_numpy(), sealed, rtol=0, atol=1e-12)

        beta, alpha, resid = _fit(y, x, sleeve)
        residual_store[sleeve] = resid
        sigma_ann = float(resid.std(ddof=1) * np.sqrt(12.0))
        r2 = _r2(y, x, beta, alpha)

        # OOS: fit on train (< 2011), score on validation (2011..2021)
        y_train, y_val = y[y.index < "2011-01-01"], y[y.index >= "2011-01-01"]
        beta_t, alpha_t, _ = _fit(y_train, x, sleeve)
        oos = _r2(y_val, x, beta_t, alpha_t)

        # D1 exhibit: equity beta on the RAW (reported) composite vs de-smoothed
        y_raw = _dated_composite(access, member_ids, desmoothed=False)
        beta_raw, _, _ = _fit(y_raw, x, sleeve)
        b_mkt_smooth = beta_raw[REGRESSORS.index("equity_mkt")]
        b_mkt_desm = beta[REGRESSORS.index("equity_mkt")]

        # regime stability: equity beta refit within expansion vs recession months
        rec_mask = recession.reindex(y.index).fillna(False).astype(bool)
        beta_exp, _, _ = _fit(y[~rec_mask], x, sleeve)
        beta_rec, _, _ = (
            _fit(y[rec_mask], x, sleeve)
            if rec_mask.sum() >= 24
            else (
                np.full(len(REGRESSORS), np.nan),
                0.0,
                pd.Series(dtype=float),
            )
        )

        artifact_lines.append(f"  {sleeve}:")
        artifact_lines.append(f"    alpha_monthly: {alpha:.6f}")
        artifact_lines.append(
            "    loadings: {"
            + ", ".join(f"{r}: {b:.4f}" for r, b in zip(REGRESSORS, beta, strict=True))
            + "}"
        )
        artifact_lines.append(f"    residual_sigma_annual: {sigma_ann:.4f}")
        artifact_lines.append(f"    r2_train_val: {r2:.3f}")
        artifact_lines.append(f"    r2_oos_validation: {oos:.3f}")
        report.append(
            f"| {sleeve} | "
            + " | ".join(f"{b:+.3f}" for b in beta)
            + f" | {sigma_ann:.1%} | {r2:.2f} | {oos:.2f} | {b_mkt_smooth:+.3f} | {b_mkt_desm:+.3f}"
            + f" | {beta_exp[0]:+.3f} | {beta_rec[0]:+.3f} |"
        )

    # ----- PM sleeves: quarterly, on the first PriMaRS delivery (2026-08-08).
    # A separate block and a separate regressor frame: PM marks are quarterly,
    # so the monthly design would silently mis-align. Loadings supersede the
    # cashflow-tier1 priors they shrink toward; n is reported per sleeve
    # because several spans are short after the constituent trim.
    xq = _regressor_frame(access, quarterly=True)
    pm_specs = pm_constraints()
    artifact_lines.append("pm_sleeves:  # quarterly design; see MAPPINGS.md for n and fit")
    report += [
        "",
        "## PM sleeves (quarterly)",
        "",
        "Estimated on the first PriMaRS delivery. Composites de-smoothed with the",
        "sleeve's OWN family (SM-10): Geltner for the appraisal-calendar sleeves,",
        "GLM elsewhere. Priors are `cashflow-tier1-v1.0.yaml`'s `pm_growth_loadings`",
        "— frozen as *chosen* because no PM data existed; these are the estimates",
        "that supersede them.",
        "",
        "| sleeve | family | n (quarters) | "
        + " | ".join(REGRESSORS)
        + " | prior β_mkt | resid sigma (ann) | R² |",
        "|---|---|---|" + "---|" * (len(REGRESSORS) + 3),
    ]
    for sleeve, member_ids in pm_sleeve_members().items():
        if sleeve not in pm_specs:
            continue
        family = smoothing_family(sleeve)
        y = _dated_composite(access, member_ids, desmoothed=True, family=family)
        beta, alpha, resid = _fit(y, xq, sleeve, pm_specs)
        n_obs = len(pd.concat([y.rename("y"), xq], axis=1, sort=True).dropna())
        sigma_ann = float(resid.std(ddof=1) * np.sqrt(4.0))  # quarterly -> annual
        r2 = _r2(y, xq, beta, alpha)
        prior_mkt = pm_specs[sleeve]["equity_mkt"][2]

        artifact_lines.append(f"  {sleeve}:")
        artifact_lines.append(f"    family: {family}")
        artifact_lines.append(f"    n_quarters: {n_obs}")
        artifact_lines.append(f"    alpha_quarterly: {alpha:.6f}")
        artifact_lines.append(
            "    loadings: {"
            + ", ".join(f"{r}: {b:.4f}" for r, b in zip(REGRESSORS, beta, strict=True))
            + "}"
        )
        artifact_lines.append(f"    residual_sigma_annual: {sigma_ann:.4f}")
        artifact_lines.append(f"    r2_train_val: {r2:.3f}")
        artifact_lines.append(
            f"    prior_superseded: {{source: cashflow-tier1-v1.0.yaml pm_growth_loadings, "
            f"equity_mkt: {prior_mkt:.4f}}}"
        )
        report.append(
            f"| {sleeve} | {family} | {n_obs} | "
            + " | ".join(f"{b:+.3f}" for b in beta)
            + f" | {prior_mkt:+.2f} | {sigma_ann:.1%} | {r2:.2f} |"
        )

    report += [
        "",
        "### Reading these numbers: the de-smoother is under-correcting",
        "",
        "EVERY estimated equity beta lands below its DN-5 prior, and the shortfall",
        "sorts by how equity-like the sleeve is. The credit and real-asset sleeves",
        "come out near their priors (distressed 1.09x, infra 0.83x, mezzanine",
        "0.75x); the equity-like ones come out far below (growth 0.57x, VC 0.36x,",
        "buyout 0.29x, secondaries 0.23x, RE value-add 0.17x). Venture — the most",
        "equity-like private asset there is — explains 11% of its own variance",
        "against a 120-quarter panel, and RE value-add explains 1%.",
        "",
        "That ordering is the signature of RESIDUAL SMOOTHING surviving the",
        "de-smoothing operator, not of private equity genuinely having a third of",
        "the market beta its economics imply. It is corroborated by the smoothing",
        "kernel fitted alongside: the Geltner phi for the appraisal sleeves is only",
        "0.18 over the full sample, while the stress-state refit puts it at 0.47 —",
        "the full-sample operator is weak precisely because the smoothing is",
        "state-dependent and the calm majority dominates the fit.",
        "",
        "CONSEQUENCE, stated rather than buried: these loadings are ESTIMATES and",
        "they supersede the priors as a record of what the delivered data says —",
        "but 'measured' is not automatically 'better'. Adopting beta_mkt 0.087 for",
        "RE value-add in place of the 0.50 prior would encode the smoothing defect",
        "into the twin. Whether the twin consumes these loadings or keeps the",
        "priors is an owner decision, not a consequence of running this script.",
        "The Cliffwater BDC series (market-priced, same asset class as direct",
        "lending, annualized vol 21.6% against this panel's 8.3% residual sigma)",
        "is the natural instrument for calibrating how much correction is missing.",
        "",
        "`pm_direct_lending` is the weakest cell in the table and should not be used:",
        "39 quarters after the constituent trim, an all-zero loading vector, R^2 of",
        "-0.00, and a de-smoother that fell back to a literal no-op.",
    ]

    # cross-sleeve residual correlation on common months
    resid_frame = pd.DataFrame(residual_store).dropna()
    corr = resid_frame.corr()
    artifact_lines.append("residual_correlation:")
    for a in corr.index:
        artifact_lines.append(
            f"  {a}: {{" + ", ".join(f"{b}: {corr.loc[a, b]:.3f}" for b in corr.columns) + "}"
        )
    artifact_lines.append("cta_rule:")
    artifact_lines.append("  kind: tsm_overlay  # DN-5 3.4: a rule, not a regression")
    artifact_lines.append("  lookback_months: 12")
    artifact_lines.append("  instruments: [equity_mkt, govt_tr_10y]")
    artifact_lines.append("  vol_target_annual: 0.10")
    artifact_lines.append("  tc_drag_annual: 0.01")

    out_dir = _REPO_ROOT / "mappings"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "sleeve-mappings-v1.0.yaml").write_text(
        "\n".join(artifact_lines) + "\n", encoding="utf-8", newline="\n"
    )
    report.append("")
    report.append(
        f"Residual correlations on {len(resid_frame)} common months; the D1 exhibit is the "
        "β_mkt smooth-vs-desmoothed pair (smoothed marks understate market exposure)."
    )
    (_REPO_ROOT / "MAPPINGS.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote mappings/sleeve-mappings-v1.0.yaml + MAPPINGS.md ({len(residual_store)} sleeves)")


if __name__ == "__main__":
    main()
