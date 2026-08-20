"""Chosen-PE release evidence (pe-chosen-01, Task 3) -- what the D-ER16-1
equation actually does on the four successor worlds 721/722/723/724.

READ-ONLY ON THE STORE -- in fact it never opens ``data/ah.db`` at all: every
spec is loaded from ``src/ah/presets/*.json`` directly (the byte source the
store builds from), so this can run before, after, or without the authorized
store builds. Nothing is written anywhere except the ``--out`` JSON.

Deterministic: the same ``ah.port.adapter.run_gen_path`` call ``ah/serve.py``
and ``ah/bundle.py`` make, at the preset's own ``base_seed`` plus the 200-path
platform stride ``base_seed + 7919*k`` -- the serenity probe's convention
(``scripts/pe_serenity_probe.py``), so path k=0 IS the live tape a 1000-path
run at the preset defaults pins as its own first path.

WHAT IT MEASURES, per successor world:
- live-tape decade PE true return; the 200-path median / p05 / p95
- median PE max drawdown vs median equity max drawdown
- paths where PE's decade beats equity's (n/200)
- the crash window: each path's worst rolling-12-month equity window --
  median equity vs median PE compounded inside it (the "does PE now fall
  harder than equity" number)
- the alpha term's annual rate, DERIVED from the live artifact row through
  the same ``ah.port.mapping.load_artifact`` accessor the adapter uses --
  a checksum of the adoption (the script refuses to report if it is not
  3.00%/yr to two decimals), never hardcoded.
- world 722 (the Gulf successor) additionally: year 5 (months 48-59, the
  crash year) PE vs equity on the live tape, and the EXACT five-term
  decomposition of the live tape's decade (alpha / beta*equity / residual /
  credit / inflation -- the serenity finding's method). The decomposition
  is rebuilt independently of ``_pm_true_monthly_path`` and ASSERTED
  bit-identical (atol 1e-12) to ``run_gen_path(...).returns["pe"]`` before
  anything is reported.

Usage:
    uv run python scripts/pe_chosen_release_evidence.py --out <dir>/pe-chosen-evidence.json
"""

from __future__ import annotations

import argparse
import json
import math
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
PRESETS = REPO / "src" / "ah" / "presets"

# The four chosen-PE successors (D-ER16-1), preset file -> expected world_id.
# The id is asserted against the loaded file so this script cannot silently
# measure a renumbered preset under an old label.
WORLDS: dict[str, str] = {
    "stress_1974_successor": "00000000-0000-4000-9000-000000000721",
    "gulf_decade": "00000000-0000-4000-9000-000000000722",
    "stress_1990_successor": "00000000-0000-4000-9000-000000000723",
    "stagflation_1974": "00000000-0000-4000-9000-000000000724",
}
N_SEEDS = 200
CRASH_YEAR = slice(48, 60)  # year 5, months 48-59 -- the Gulf crash year


# ----------------------------------------------------------------- helpers


def compound_pct(monthly_pct: np.ndarray) -> float:
    """Total return in percent from a series of monthly percent returns."""
    return float(np.prod(1.0 + monthly_pct / 100.0) - 1.0) * 100.0


def max_drawdown_pct(monthly_pct: np.ndarray) -> float:
    idx = 100.0 * np.cumprod(1.0 + monthly_pct / 100.0)
    dd = idx / np.maximum.accumulate(idx) - 1.0
    return float(dd.min()) * 100.0


def worst_rolling_12m_window(eq_monthly_pct: np.ndarray) -> slice:
    """The worst rolling 12-month equity window, by log-sum (the probe's rule)."""
    logs = np.log1p(eq_monthly_pct / 100.0)
    roll = np.array([logs[i : i + 12].sum() for i in range(eq_monthly_pct.shape[0] - 11)])
    w0 = int(np.argmin(roll))
    return slice(w0, w0 + 12)


def stats(v: list[float]) -> dict:
    a = np.asarray(v, dtype=float)
    return {
        "n": int(a.size),
        "min": round(float(a.min()), 2),
        "p05": round(float(np.quantile(a, 0.05)), 2),
        "median": round(float(np.median(a)), 2),
        "p95": round(float(np.quantile(a, 0.95)), 2),
        "max": round(float(a.max()), 2),
        "mean": round(float(a.mean()), 2),
    }


def load_preset(name: str) -> dict:
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    expected = WORLDS[name]
    if doc["world_id"] != expected:
        raise SystemExit(
            f"{name}.json carries world_id {doc['world_id']}, expected {expected} "
            "-- the preset moved; refusing to measure under a stale label"
        )
    return doc


# ------------------------- the five-term decomposition (the probe's method)


def pe_terms(world_doc: dict, seed: int) -> dict[str, np.ndarray]:
    """The five additive terms of ``_pm_true_monthly_path``'s PE row, in
    monthly PERCENT, rebuilt independently and ASSERTED against the adapter
    (bit-identical, atol 1e-12) -- copied from the serenity probe so the
    before/after tables are the same construction on both sides."""
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


# ---------------------------------------------------------------- measures


def measure_world(name: str, doc: dict, n_seeds: int) -> dict:
    ws = WorldSpec.model_validate(doc)
    nw = project_numeric(ws)
    base_seed = int(doc["engine_defaults"]["base_seed"])

    decade_pe: list[float] = []
    decade_eq: list[float] = []
    dd_pe: list[float] = []
    dd_eq: list[float] = []
    crash_eq: list[float] = []
    crash_pe: list[float] = []
    beats = 0
    for k in range(n_seeds):
        p = run_gen_path(nw, base_seed + SEED_STRIDE * k)
        pe, eq = p.returns["pe"], p.returns["equity"]
        d_pe, d_eq = compound_pct(pe), compound_pct(eq)
        decade_pe.append(d_pe)
        decade_eq.append(d_eq)
        dd_pe.append(max_drawdown_pct(pe))
        dd_eq.append(max_drawdown_pct(eq))
        if d_pe > d_eq:
            beats += 1
        w = worst_rolling_12m_window(eq)
        crash_eq.append(compound_pct(eq[w]))
        crash_pe.append(compound_pct(pe[w]))

    return {
        "world_id": doc["world_id"],
        "generator_id": doc["engine_defaults"]["generator_id"],
        "base_seed": base_seed,
        "n_paths": n_seeds,
        "live_tape_decade_pe_true_pct": round(decade_pe[0], 2),
        "live_tape_decade_equity_pct": round(decade_eq[0], 2),
        "decade_pe_true_pct": stats(decade_pe),
        "decade_equity_pct": stats(decade_eq),
        "max_drawdown_pe_pct": stats(dd_pe),
        "max_drawdown_equity_pct": stats(dd_eq),
        "n_paths_pe_decade_beats_equity_decade": beats,
        "worst_rolling_12m_equity_window": {
            "equity_compound_pct": stats(crash_eq),
            "pe_true_compound_pct": stats(crash_pe),
            "median_pe_minus_median_equity_pp": round(
                float(np.median(crash_pe) - np.median(crash_eq)), 2
            ),
        },
    }


def gulf_extras(doc: dict) -> dict:
    """World 722 only: year-5 live-tape PE vs equity and the exact five-term
    decomposition of the live tape's decade."""
    ws = WorldSpec.model_validate(doc)
    nw = project_numeric(ws)
    seed = int(doc["engine_defaults"]["base_seed"])
    p = run_gen_path(nw, seed)
    pe, eq = p.returns["pe"], p.returns["equity"]
    terms = pe_terms(doc, seed)  # asserts bit-identity before returning

    total_arith = float(pe.sum())
    per_term = {}
    for tname, t in terms.items():
        arith = float(t.sum())
        per_term[tname] = {
            "arith_sum_pp_over_decade": round(arith, 3),
            "share_of_arith_sum": round(arith / total_arith, 4) if total_arith else None,
            "arith_sum_pp_year5": round(float(t[CRASH_YEAR].sum()), 3),
            "compounded_alone_pct": round(compound_pct(t), 2),
        }
    return {
        "seed": seed,
        "year5_months_48_59": {
            "pe_true_pct": round(compound_pct(pe[CRASH_YEAR]), 2),
            "equity_pct": round(compound_pct(eq[CRASH_YEAR]), 2),
        },
        "live_tape_decade_decomposition": {
            "arith_sum_of_monthly_pe_pp": round(total_arith, 3),
            "decade_pe_true_pct": round(compound_pct(pe), 2),
            "decade_equity_pct": round(compound_pct(eq), 2),
            "terms": per_term,
        },
    }


# -------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-seeds", type=int, default=N_SEEDS)
    args = ap.parse_args()

    # The adoption checksum, derived from the LIVE row through the accessor.
    artifact = load_artifact()
    row = artifact["pm_sleeves"]["pm_buyout"]
    a_q = float(row["alpha_quarterly"])
    alpha_annual_pct = ((1.0 + a_q / 3.0) ** 12 - 1.0) * 100.0
    if round(alpha_annual_pct, 2) != 3.00:
        raise SystemExit(
            f"adoption checksum FAILED: the live pm_buyout row annualises to "
            f"{alpha_annual_pct:.4f}%/yr, not 3.00%/yr -- is the accessor "
            "still pointing at the chosen v1.3 artifact?"
        )
    sealed = {
        "mapping_version": artifact["mapping_version"],
        "alpha_quarterly": a_q,
        "alpha_annualised_as_adapter_applies_it_pct": round(alpha_annual_pct, 4),
        "equity_beta": float(row["loadings"]["equity_mkt"]),
        "replaced": row.get("chosen", {}).get("replaced"),
    }
    print(f"live row: {artifact['mapping_version']} pm_buyout")
    print(f"  alpha (annualised, adapter convention): {alpha_annual_pct:.2f}%/yr  [checksum OK]")
    print(f"  equity beta: {sealed['equity_beta']}")

    out: dict = {"live_row": sealed, "n_seeds": args.n_seeds, "worlds": {}}
    for name, wid in WORLDS.items():
        doc = load_preset(name)
        m = measure_world(name, doc, args.n_seeds)
        if wid.endswith("722"):
            m["gulf_extras"] = gulf_extras(doc)
        out["worlds"][name] = m
        cw = m["worst_rolling_12m_equity_window"]
        print(
            f"{name} ({wid[-3:]}): live decade PE {m['live_tape_decade_pe_true_pct']}% | "
            f"median {m['decade_pe_true_pct']['median']}% "
            f"[p05 {m['decade_pe_true_pct']['p05']}, p95 {m['decade_pe_true_pct']['p95']}] | "
            f"maxDD med PE {m['max_drawdown_pe_pct']['median']}% "
            f"vs eq {m['max_drawdown_equity_pct']['median']}% | "
            f"beats-eq {m['n_paths_pe_decade_beats_equity_decade']}/{args.n_seeds} | "
            f"crash-12m med eq {cw['equity_compound_pct']['median']}% "
            f"vs PE {cw['pe_true_compound_pct']['median']}%"
        )

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
