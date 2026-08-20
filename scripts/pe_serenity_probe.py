"""PE-serenity probe (pe-serenity-01) -- does private equity ride through the
generated stress worlds too calmly, and if so, why?

READ-ONLY. Opens ``data/ah.db`` with ``mode=ro`` and never writes to it. No
run is created, nothing is stored. Everything past the store read is a pure,
deterministic recomputation from each world's own spec + seed -- the same
``ah.port.adapter.run_gen_path`` call ``ah/serve.py``'s ``_resolve_engine``
and ``ah/bundle.py``'s ``build_bundle`` make on every request. Re-running
reproduces byte-identical numbers.

WHAT IT MEASURES
----------------
A. The sealed ``pm_buyout`` row, echoed from ``mappings/sleeve-mappings-v1.2.yaml``
   through the same ``ah.port.mapping.load_artifact`` the adapter uses.
B. An EXACT term decomposition of one path's PE tape. ``_pm_true_monthly_path``
   builds PE as an additive sum in monthly return space:

       r_pe(t) = alpha_q/3
                 + beta_eq * equity_mkt(t)
                 + beta_dig * d_ig(t)
                 - b_infl * (cpi_trail_excess(t)/12)/100
                 + eps(t) * sigma_annual/sqrt(12)          [all x100 -> percent]

   The probe rebuilds those five terms independently and ASSERTS the sum is
   bit-identical to ``run_gen_path(...).returns["pe"]``. If that assertion
   ever fails the decomposition is wrong and the probe refuses to report.
C. Window betas. OLS of monthly PE true on monthly equity true over the full
   decade and over several stress sub-windows, plus separate down-month and
   up-month betas -- the direct test of whether the construction has any
   crisis convexity.
D. The reported (appraisal) plane: quarterly ACF(1) and max drawdown, true vs
   reported.
E. The seed distribution: N paths per world at the platform stride
   ``base_seed + 7919*k``, so the observed run's own tape is path k=0 and its
   percentile within its own world's implied distribution is measurable.
E2. Counterfactuals: the decade with the always-on intercept removed, with the
   residual removed, and with both removed; plus the "worst-year cushion" --
   what each term hands PE inside the worst rolling 12-month equity window.
F. Whether the WorldSpec's declared ``structural.private_equity`` fields
   (``leverage_turns``, whose SCHEMA text says it "scales the equity-factor
   beta in the mapping", and ``illiquidity_premium_annual_pct``) reach the
   generated PE row at all, varied across their full schema ranges.
G. The pooled convexity test: ~n*120 monthly observations fitted with a
   downside-beta kink, then refitted with the credit term removed -- the
   control that says whether any measured kink is credit or genuine equity
   convexity.

Usage:
    uv run python scripts/pe_serenity_probe.py --out <dir>/pe-serenity-data.json
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path

import numpy as np

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

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "ah.db"

# The three er14-06 stress worlds, with the seed each one's live RunRecord pins.
WORLDS = {
    "gulf_decade": ("00000000-0000-4000-9000-000000000712", 202608),
    "stress_1974_successor": ("00000000-0000-4000-9000-000000000711", 197400),
    "stress_1990_successor": ("00000000-0000-4000-9000-000000000713", 199001),
}
N_SEEDS = 200


# ----------------------------------------------------------------- helpers


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_world(world_id: str) -> dict:
    conn = _connect_ro(DB)
    try:
        row = conn.execute("SELECT json FROM worlds WHERE world_id = ?", (world_id,)).fetchone()
        if row is None:
            raise SystemExit(f"world {world_id} not found in {DB}")
        return json.loads(row["json"])
    finally:
        conn.close()


def compound_pct(monthly_pct: np.ndarray) -> float:
    """Total return in percent from a series of monthly percent returns."""
    return float(np.prod(1.0 + monthly_pct / 100.0) - 1.0) * 100.0


def index_of(monthly_pct: np.ndarray) -> np.ndarray:
    return 100.0 * np.cumprod(1.0 + monthly_pct / 100.0)


def max_drawdown(monthly_pct: np.ndarray) -> tuple[float, int]:
    idx = index_of(monthly_pct)
    running = np.maximum.accumulate(idx)
    dd = idx / running - 1.0
    t = int(np.argmin(dd))
    return float(dd[t]) * 100.0, t


def ols(y: np.ndarray, x: np.ndarray) -> dict:
    """Univariate OLS y = a + b x, returning slope, intercept, R2, n."""
    n = int(x.shape[0])
    if n < 3:
        return {"n": n, "beta": None, "alpha": None, "r2": None}
    xm, ym = float(x.mean()), float(y.mean())
    sxx = float(((x - xm) ** 2).sum())
    sxy = float(((x - xm) * (y - ym)).sum())
    beta = sxy / sxx
    alpha = ym - beta * xm
    resid = y - (alpha + beta * x)
    sst = float(((y - ym) ** 2).sum())
    r2 = 1.0 - float((resid**2).sum()) / sst if sst > 0 else None
    return {
        "n": n,
        "beta": round(beta, 6),
        "alpha_monthly_pct": round(alpha, 5),
        "r2": round(r2, 6) if r2 is not None else None,
    }


def to_quarterly(monthly_pct: np.ndarray) -> np.ndarray:
    """Compound monthly percent returns into quarterly percent returns."""
    m = monthly_pct.reshape(-1, 3)
    return (np.prod(1.0 + m / 100.0, axis=1) - 1.0) * 100.0


def acf1(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    denom = float((x * x).sum())
    if denom == 0:
        return float("nan")
    return float((x[:-1] * x[1:]).sum() / denom)


# --------------------------------------------------- B: term decomposition


def pe_terms(world_doc: dict, seed: int) -> dict[str, np.ndarray]:
    """The five additive terms of ``_pm_true_monthly_path``'s PE row, in
    monthly PERCENT, rebuilt independently and checked against the adapter."""
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    gen = registry.resolve_for_world(nw)
    ensemble = gen.sample(nw, 1, seed)
    rows = np.asarray(ensemble.row_indices)[0]
    series = _source_series(_source_of(gen), nw)
    artifact = load_artifact()
    spec = artifact["pm_sleeves"][PM_SLEEVE_FOR_ASSET["pe"]]

    reg = {
        "equity_mkt": ensemble.factor("equity_mkt")[0],
        "smb": ensemble.factor("smb")[0],
        "hml": ensemble.factor("hml")[0],
        "mom": ensemble.factor("mom")[0],
        "d_level": series["d_level"][rows],
        "d_slope": series["d_slope"][rows],
        "d_ig": series["d_ig"][rows],
    }

    months = ensemble.months
    terms: dict[str, np.ndarray] = {}
    terms["alpha"] = np.full(months, float(spec["alpha_quarterly"]) / 3.0) * 100.0
    for name, beta in spec["loadings"].items():
        if float(beta) != 0.0:
            terms[f"beta_{name}"] = float(beta) * reg[name] * 100.0
    pt = spec.get("inflation_passthrough")
    if pt:
        # PE takes the declared magnitude with the toy plane's NET sign (AT-10).
        terms["inflation"] = (
            -float(pt["b_infl"]) * (series["cpi_trail_excess"][rows] / 12.0) / 100.0 * 100.0
        )

    # residual: the adapter's own stated stream and correlated Student-t block
    rng = np.random.Generator(np.random.PCG64(seed + RESIDUAL_SEED_OFFSET))
    pmr = artifact.get("pm_residuals")
    if pmr is not None:
        df = float(pmr["df"])
        names = [PM_SLEEVE_FOR_ASSET[a] for a in _PM_ASSET_ORDER]
        corr = np.array([[float(pmr["block_correlation"][a][b]) for b in names] for a in names])
        chol = np.linalg.cholesky(corr)
        raw_t = rng.standard_t(df, size=(months, len(_PM_ASSET_ORDER)))
        raw_t = raw_t / math.sqrt(df / (df - 2.0))
        shocks = raw_t @ chol.T
    else:
        shocks = rng.standard_normal((months, len(_PM_ASSET_ORDER)))
    j = _PM_ASSET_ORDER.index("pe")
    sigma_m = float(spec["residual_sigma_annual"]) / np.sqrt(12.0)
    terms["residual"] = shocks[:, j] * sigma_m * 100.0

    # the assertion that makes this a decomposition and not a story
    rebuilt = np.sum(np.stack(list(terms.values())), axis=0)
    actual = run_gen_path(nw, seed).returns["pe"]
    if not np.allclose(rebuilt, actual, rtol=0, atol=1e-12):
        raise SystemExit(
            "term decomposition does not reproduce run_gen_path's PE row "
            f"(max abs diff {np.abs(rebuilt - actual).max()}) -- refusing to report"
        )
    return terms


def decompose(world_doc: dict, seed: int) -> dict:
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    paths = run_gen_path(nw, seed)
    pe = paths.returns["pe"]
    eq = paths.returns["equity"]
    terms = pe_terms(world_doc, seed)
    months = paths.months

    total_arith = float(pe.sum())
    per_term = {}
    for name, t in terms.items():
        arith = float(t.sum())
        per_term[name] = {
            "arith_sum_pct_over_decade": round(arith, 3),
            "share_of_arith_sum": round(arith / total_arith, 4) if total_arith else None,
            "mean_monthly_pct": round(float(t.mean()), 5),
            "compounded_alone_pct": round(compound_pct(t), 2),
            # leave-one-out: what the decade would compound to WITHOUT this term
            "leave_one_out_decade_pct": round(compound_pct(pe - t), 2),
        }

    # year 5 (months 48..59) -- the Gulf Decade's crash year
    year_blocks = {}
    for y in range(months // 12):
        m0, m1 = y * 12, y * 12 + 12
        year_blocks[y + 1] = {
            "pe_true_pct": round(compound_pct(pe[m0:m1]), 2),
            "equity_pct": round(compound_pct(eq[m0:m1]), 2),
            "terms": {n: round(compound_pct(t[m0:m1]), 2) for n, t in terms.items()},
        }

    dd_pe, t_pe = max_drawdown(pe)
    dd_eq, t_eq = max_drawdown(eq)
    return {
        "seed": seed,
        "months": months,
        "decade_pe_true_pct": round(compound_pct(pe), 2),
        "decade_equity_pct": round(compound_pct(eq), 2),
        "arith_sum_of_monthly_pe_pct": round(total_arith, 3),
        "terms": per_term,
        "years": year_blocks,
        "max_drawdown": {
            "pe_true_pct": round(dd_pe, 2),
            "pe_trough_month_index": t_pe,
            "equity_pct": round(dd_eq, 2),
            "equity_trough_month_index": t_eq,
            "ratio_pe_over_equity": round(dd_pe / dd_eq, 4) if dd_eq else None,
        },
    }


# ------------------------------------------------------- C: window betas


def declared_crisis_months(world_doc: dict, months: int) -> np.ndarray:
    mask = np.zeros(months, dtype=bool)
    for seg in world_doc["regimes"]["sequence"]:
        if seg["regime"] == "crisis":
            m0 = seg["from_quarter"] * 3
            m1 = (seg["to_quarter"] + 1) * 3
            mask[m0:m1] = True
    return mask


def window_betas(world_doc: dict, seed: int) -> dict:
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    paths = run_gen_path(nw, seed)
    pe, eq = paths.returns["pe"], paths.returns["equity"]
    months = paths.months

    eq_idx = index_of(eq)
    eq_dd = eq_idx / np.maximum.accumulate(eq_idx) - 1.0

    # worst rolling 12-month equity window
    logs = np.log1p(eq / 100.0)
    roll = np.array([logs[i : i + 12].sum() for i in range(months - 11)])
    w0 = int(np.argmin(roll))
    worst12 = np.zeros(months, dtype=bool)
    worst12[w0 : w0 + 12] = True

    windows = {
        "full_decade": np.ones(months, dtype=bool),
        "declared_crisis_quarters": declared_crisis_months(world_doc, months),
        "equity_bear_state_dd_lt_-10pct": eq_dd < -0.10,
        "equity_bear_state_dd_lt_-20pct": eq_dd < -0.20,
        "worst_rolling_12m_equity": worst12,
        "equity_down_months": eq < 0.0,
        "equity_up_months": eq >= 0.0,
        "equity_worst_decile_months": eq <= np.quantile(eq, 0.10),
    }
    out = {}
    for name, mask in windows.items():
        if mask.sum() < 3:
            out[name] = {"n": int(mask.sum()), "beta": None}
            continue
        res = ols(pe[mask], eq[mask])
        res["equity_compound_pct_in_window"] = round(compound_pct(eq[mask]), 2)
        res["pe_compound_pct_in_window"] = round(compound_pct(pe[mask]), 2)
        out[name] = res
    return out


# --------------------------------------------------- D: the reported plane


def reported_plane(world_doc: dict, seed: int) -> dict:
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    paths = run_gen_path(nw, seed)
    out = {}
    for asset in ("pe", "pc", "re", "infra"):
        true_m = paths.returns[asset]
        rep_m = paths.reported[asset]
        dd_t, tt = max_drawdown(true_m)
        dd_r, tr = max_drawdown(rep_m)
        out[asset] = {
            "decade_true_pct": round(compound_pct(true_m), 2),
            "decade_reported_pct": round(compound_pct(rep_m), 2),
            "quarterly_acf1_true": round(acf1(to_quarterly(true_m)), 4),
            "quarterly_acf1_reported": round(acf1(to_quarterly(rep_m)), 4),
            "quarterly_vol_pct_true": round(float(to_quarterly(true_m).std(ddof=1)), 3),
            "quarterly_vol_pct_reported": round(float(to_quarterly(rep_m).std(ddof=1)), 3),
            "max_drawdown_true_pct": round(dd_t, 2),
            "max_drawdown_true_trough_month": tt,
            "max_drawdown_reported_pct": round(dd_r, 2),
            "max_drawdown_reported_trough_month": tr,
            "worst_quarter_true_pct": round(float(to_quarterly(true_m).min()), 2),
            "worst_quarter_reported_pct": round(float(to_quarterly(rep_m).min()), 2),
        }
    eq_dd, _ = max_drawdown(paths.returns["equity"])
    out["_equity_max_drawdown_pct"] = round(eq_dd, 2)
    return out


# ------------------------------------------------------ E: seed distribution


def seed_distribution(world_doc: dict, base_seed: int, n: int) -> dict:
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    cum_pe, cum_eq, dd_pe, dd_eq, betas_down, betas_up = [], [], [], [], [], []
    worst_pe_q, worst_eq_q = [], []
    for k in range(n):
        p = run_gen_path(nw, base_seed + SEED_STRIDE * k)
        pe, eq = p.returns["pe"], p.returns["equity"]
        cum_pe.append(compound_pct(pe))
        cum_eq.append(compound_pct(eq))
        dd_pe.append(max_drawdown(pe)[0])
        dd_eq.append(max_drawdown(eq)[0])
        down = eq < 0.0
        betas_down.append(ols(pe[down], eq[down])["beta"])
        betas_up.append(ols(pe[~down], eq[~down])["beta"])
        worst_pe_q.append(float(to_quarterly(pe).min()))
        worst_eq_q.append(float(to_quarterly(eq).min()))

    def stats(v: list[float]) -> dict:
        a = np.asarray(v, dtype=float)
        return {
            "n": int(a.size),
            "min": round(float(a.min()), 2),
            "p05": round(float(np.quantile(a, 0.05)), 2),
            "p25": round(float(np.quantile(a, 0.25)), 2),
            "median": round(float(np.median(a)), 2),
            "p75": round(float(np.quantile(a, 0.75)), 2),
            "p95": round(float(np.quantile(a, 0.95)), 2),
            "max": round(float(a.max()), 2),
            "mean": round(float(a.mean()), 2),
        }

    obs = cum_pe[0]  # k=0 IS the live RunRecord's own path
    pct_rank = float((np.asarray(cum_pe) <= obs).mean())
    return {
        "n_paths": n,
        "base_seed": base_seed,
        "decade_pe_true_pct": stats(cum_pe),
        "decade_equity_pct": stats(cum_eq),
        "max_drawdown_pe_pct": stats(dd_pe),
        "max_drawdown_equity_pct": stats(dd_eq),
        "downside_beta": stats(betas_down),
        "upside_beta": stats(betas_up),
        "downside_minus_upside_beta": stats(
            [d - u for d, u in zip(betas_down, betas_up, strict=True)]
        ),
        "worst_quarter_pe_true_pct": stats(worst_pe_q),
        "worst_quarter_equity_pct": stats(worst_eq_q),
        "observed_path_k0": {
            "decade_pe_true_pct": round(obs, 2),
            "percentile_within_own_world": round(pct_rank, 4),
            "n_paths_with_negative_decade_pe": int((np.asarray(cum_pe) < 0).sum()),
        },
    }


# ------------------------------------------- E2: counterfactual terms


def counterfactuals(world_doc: dict, base_seed: int, n: int) -> dict:
    """Across n paths: what the decade compounds to with the always-on alpha
    removed, with the residual removed, and with both removed -- i.e. the pure
    factor tape (beta*equity + beta*d_ig + the inflation channel).

    Also the 'worst-year cushion': inside each path's worst rolling 12-month
    equity window, PE's own compound vs the compound of its beta*equity term
    alone. The difference is what the state-independent alpha (plus that
    window's residual) hands PE in the worst stretch of the decade.
    """
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    full, no_alpha, no_resid, factors_only, eq_cum = [], [], [], [], []
    cushion_alpha, cushion_resid, worst_pe, worst_beta_eq, worst_eq = [], [], [], [], []
    pe_beats_equity = 0
    for k in range(n):
        seed = base_seed + SEED_STRIDE * k
        terms = pe_terms(world_doc, seed)
        p = run_gen_path(nw, seed)
        pe, eq = p.returns["pe"], p.returns["equity"]
        full.append(compound_pct(pe))
        no_alpha.append(compound_pct(pe - terms["alpha"]))
        no_resid.append(compound_pct(pe - terms["residual"]))
        factors_only.append(compound_pct(pe - terms["alpha"] - terms["residual"]))
        eq_cum.append(compound_pct(eq))
        if compound_pct(pe) > compound_pct(eq):
            pe_beats_equity += 1

        logs = np.log1p(eq / 100.0)
        roll = np.array([logs[i : i + 12].sum() for i in range(p.months - 11)])
        w0 = int(np.argmin(roll))
        sl = slice(w0, w0 + 12)
        worst_pe.append(compound_pct(pe[sl]))
        worst_beta_eq.append(compound_pct(terms["beta_equity_mkt"][sl]))
        worst_eq.append(compound_pct(eq[sl]))
        cushion_alpha.append(compound_pct(terms["alpha"][sl]))
        cushion_resid.append(compound_pct(terms["residual"][sl]))

    def med(v: list[float]) -> dict:
        a = np.asarray(v, dtype=float)
        return {
            "median": round(float(np.median(a)), 2),
            "p05": round(float(np.quantile(a, 0.05)), 2),
            "p95": round(float(np.quantile(a, 0.95)), 2),
        }

    return {
        "n_paths": n,
        "decade_pe_full": med(full),
        "decade_pe_alpha_removed": med(no_alpha),
        "decade_pe_residual_removed": med(no_resid),
        "decade_pe_factors_only": med(factors_only),
        "decade_equity": med(eq_cum),
        "n_paths_pe_decade_beats_equity_decade": pe_beats_equity,
        "worst_rolling_12m_equity_window": {
            "equity": med(worst_eq),
            "pe_true": med(worst_pe),
            "pe_beta_equity_term_alone": med(worst_beta_eq),
            "alpha_term_in_window": med(cushion_alpha),
            "residual_term_in_window": med(cushion_resid),
        },
    }


# ------------------------- F: the declared PE structural fields, measured


def structural_field_inertness(world_doc: dict, seed: int) -> dict:
    """The WorldSpec's ``structural.private_equity`` block declares
    ``leverage_turns`` — whose SCHEMA description is "Net debt / EBITDA at
    entry; scales the equity-factor beta in the mapping" — and
    ``illiquidity_premium_annual_pct``. This measures whether either reaches
    the generated plane's PE row, by varying the field across its full
    schema-declared range and comparing the PE tape.
    """
    out = {"declared": dict(world_doc.get("structural", {}).get("private_equity", {}))}
    base = WorldSpec.model_validate(world_doc)
    base_pe = run_gen_path(project_numeric(base), seed).returns["pe"]

    for field, values in (
        ("leverage_turns", [2.0, 5.5, 8.0]),
        ("illiquidity_premium_annual_pct", [0.0, 2.0, 5.0]),
    ):
        diffs = []
        for v in values:
            doc = json.loads(json.dumps(world_doc))
            doc.setdefault("structural", {}).setdefault("private_equity", {})[field] = v
            pe = run_gen_path(project_numeric(WorldSpec.model_validate(doc)), seed).returns["pe"]
            diffs.append(float(np.abs(pe - base_pe).max()))
        out[field] = {
            "values_tried": values,
            "max_abs_diff_vs_stored_pe_tape_pct": diffs,
            "reaches_the_generated_pe_row": any(d > 0.0 for d in diffs),
        }
    return out


# -------------------------------- G: the pooled convexity test (the verdict)


def pooled_convexity(world_doc: dict, base_seed: int, n: int) -> dict:
    """Pool every month of n paths and fit

        r_pe = a + b*r_eq + c*r_eq*1{r_eq<0} + d*1{r_eq<0}

    ``c`` is the downside-beta KINK: real buyout portfolios are expected to
    show c > 0 (they fall MORE than their average beta predicts). A
    construction that is linear in the equity factor must produce c = 0 up to
    sampling noise. Reported with a heteroskedasticity-naive t-statistic over
    ~n*120 observations, which is enough to detect a kink of a few hundredths.
    """
    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    ys, xs, ys_no_dig = [], [], []
    for k in range(n):
        seed = base_seed + SEED_STRIDE * k
        p = run_gen_path(nw, seed)
        ys.append(p.returns["pe"])
        xs.append(p.returns["equity"])
        # the same tape with the CREDIT term removed -- the only other channel
        # that co-moves with equity down-months, so the control that says
        # whether any measured kink is credit or genuine equity convexity
        ys_no_dig.append(p.returns["pe"] - pe_terms(world_doc, seed)["beta_d_ig"])
    x = np.concatenate(xs)
    dn = (x < 0.0).astype(float)
    X = np.column_stack([np.ones_like(x), x, x * dn, dn])
    names = ["intercept_monthly_pct", "beta_up", "beta_kink_extra_on_down_months", "down_dummy"]

    def fit(y: np.ndarray) -> dict:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        dof = X.shape[0] - X.shape[1]
        s2 = float((resid**2).sum()) / dof
        se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
        return {
            "coefficients": {
                nm: {
                    "value": round(float(c), 6),
                    "se": round(float(s), 6),
                    "t": round(float(c / s), 3),
                }
                for nm, c, s in zip(names, coef, se, strict=True)
            },
            "implied_downside_beta": round(float(coef[1] + coef[2]), 6),
            "implied_upside_beta": round(float(coef[1]), 6),
        }

    return {
        "n_obs": int(X.shape[0]),
        "as_shipped": fit(np.concatenate(ys)),
        "credit_term_removed": fit(np.concatenate(ys_no_dig)),
        "declared_beta": float(
            load_artifact()["pm_sleeves"]["pm_buyout"]["loadings"]["equity_mkt"]
        ),
    }


# ---------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-seeds", type=int, default=N_SEEDS)
    args = ap.parse_args()

    artifact = load_artifact()
    row = artifact["pm_sleeves"]["pm_buyout"]
    a_q = float(row["alpha_quarterly"])
    sealed = {
        "mapping_version": artifact["mapping_version"],
        "pm_vintage_id": artifact.get("pm_vintage_id"),
        "desmoothing_method": artifact.get("desmoothing_method"),
        "pm_buyout": {
            "family": row["family"],
            "n_quarters": row["n_quarters"],
            "route": row["route"],
            "alpha_quarterly": a_q,
            "alpha_monthly_third": round(a_q / 3.0, 8),
            "alpha_annualised_from_quarterly_pct": round(((1 + a_q) ** 4 - 1) * 100, 4),
            "alpha_annualised_as_adapter_applies_it_pct": round(
                ((1 + a_q / 3.0) ** 12 - 1) * 100, 4
            ),
            "loadings": row["loadings"],
            "residual_sigma_annual": row["residual_sigma_annual"],
            "residual_sigma_monthly_pct": round(
                float(row["residual_sigma_annual"]) / math.sqrt(12) * 100, 4
            ),
            "r2_train_val": row["r2_train_val"],
            "inflation_passthrough": row.get("inflation_passthrough"),
            "prior_v10": row.get("prior_v10"),
        },
        "pm_residuals_df": artifact.get("pm_residuals", {}).get("df"),
        "structural_omissions": artifact.get("structural_omissions"),
    }

    out: dict = {"sealed_row": sealed, "worlds": {}}
    for name, (wid, seed) in WORLDS.items():
        doc = load_world(wid)
        out["worlds"][name] = {
            "world_id": wid,
            "run_seed": seed,
            "generator_id": doc["engine_defaults"]["generator_id"],
            "decomposition": decompose(doc, seed),
            "window_betas": window_betas(doc, seed),
            "reported_plane": reported_plane(doc, seed),
            "seed_distribution": seed_distribution(doc, seed, args.n_seeds),
            "counterfactuals": counterfactuals(doc, seed, args.n_seeds),
            "reporting_smoothing": doc.get("structural", {}).get("smoothing"),
            "structural_field_inertness": structural_field_inertness(doc, seed),
            "pooled_convexity": pooled_convexity(doc, seed, args.n_seeds),
        }

    # pooled window betas across all three worlds x the first 20 seeds each
    pooled: dict[str, list[float]] = {}
    for _name, (wid, seed) in WORLDS.items():
        doc = load_world(wid)
        for k in range(20):
            wb = window_betas(doc, seed + SEED_STRIDE * k)
            for wname, res in wb.items():
                if res.get("beta") is not None:
                    pooled.setdefault(wname, []).append(res["beta"])
    out["pooled_window_betas_3worlds_x_20seeds"] = {
        w: {
            "n": len(v),
            "mean": round(float(np.mean(v)), 6),
            "min": round(float(np.min(v)), 6),
            "max": round(float(np.max(v)), 6),
            "sd": round(float(np.std(v, ddof=1)), 6),
        }
        for w, v in pooled.items()
    }
    out["declared_equity_beta"] = float(row["loadings"]["equity_mkt"])

    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
