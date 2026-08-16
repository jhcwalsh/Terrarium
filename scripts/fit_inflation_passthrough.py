"""Inflation pass-through fit for real-asset sleeves (AM-2026-08-15-001, C1).

Fits the declared distributed-lag pass-through of a real-asset income series
on trailing CPI inflation, per docs/superpowers/specs/
2026-08-15-inflation-passthrough-credit-loss-design.md. Declared BEFORE any
NCREIF data was seen:

* Primary regressor form: trailing K=8-quarter realised CPI inflation.
  K=4 and K=12 are recorded as sensitivities, never adopted.
* Diagnostic form: unrestricted distributed lag, J=12 quarters, Newey-West
  HAC (lag 8) standard errors. The cumulative-pass-through profile is the
  evidence for K; the trailing-K coefficient is what the artifact adopts.
* Sample: fit window ends 2020-12-31 (the sealed train+validation boundary);
  the 2021-24 rows, if present in the input, are NEVER used in fitting and
  are written to the provenance block for the one-shot Ruling-A check only.
* CPI: FRED CPIAUCSL unless --cpi-csv is supplied. External series; no
  catalog read anywhere in this script.
* Deterministic: no RNG. ASCII-only console output.

Input CSV: columns  date, value   (quarterly; value in decimal per quarter).
Intended targets, in priority order per the design note:
  1. NPI NOI growth        (escalation lives here; not appraised)
  2. NPI income return     (declared continuity target; yield-denominator
                            caveat disclosed in the design note)

Usage:
  python fit_inflation_passthrough.py --target npi_noi_growth.csv \
      --label npi_noi_growth --out passthrough-npi.json

REGENERATING THE COMMITTED RENT CROSS-CHECK (artifacts/c1/
passthrough-rent-crosscheck.json). Its input `rent_q.csv` is NOT committed --
only its sha256 travels in the provenance -- because it rebuilds from one
public FRED fetch. The target is CPI rent of primary residence, CUUR0000SEHA,
as quarterly log-differences:

  python -c "import pandas as pd, numpy as np; \
s=pd.read_csv('https://fred.stlouisfed.org/graph/fredgraph.csv?id=CUUR0000SEHA', \
index_col=0, parse_dates=True).iloc[:,0].resample('QE').mean(); \
np.log(s).diff().dropna().rename('value').to_csv('rent_q.csv', \
index_label='date')"
  python scripts/fit_inflation_passthrough.py --target rent_q.csv \
      --label cpi_rent_crosscheck --out artifacts/c1/passthrough-rent-crosscheck.json

A rebuild reproduces the committed numbers only if FRED has not revised
CUUR0000SEHA or CPIAUCSL since; the `target_sha256` in the artifact is what
detects that, and a mismatch is a disclosure, not a failure.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

FRED_CPI = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"
TRAIN_VAL_END = "2020-12-31"  # sealed boundary; splits.py is normative
K_PRIMARY = 8
K_SENS = (4, 12)
J_DIAG = 12
NW_LAG = 8


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_quarterly_csv(path: str) -> pd.Series:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "date" not in df.columns or "value" not in df.columns:
        raise SystemExit(f"{path}: need columns date,value")
    s = pd.Series(
        pd.to_numeric(df["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(df["date"]),
    ).sort_index()
    return s.resample("QE").last().dropna()


def fetch_cpi(cpi_csv: str | None) -> pd.Series:
    if cpi_csv:
        raw = Path(cpi_csv).read_bytes()
    else:
        raw = urllib.request.urlopen(FRED_CPI, timeout=60).read()
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = ["date", "v"]
    s = pd.Series(
        pd.to_numeric(df["v"], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(df["date"]),
    ).dropna()
    q = s.resample("QE").mean()
    return np.log(q).diff().dropna()  # quarterly CPI inflation, log-diff


def nw_se(a: np.ndarray, resid: np.ndarray, lag: int) -> np.ndarray:
    u = resid[:, None] * a
    s = u.T @ u
    for ell in range(1, lag + 1):
        g = u[ell:].T @ u[:-ell]
        s += (1.0 - ell / (lag + 1)) * (g + g.T)
    ainv = np.linalg.inv(a.T @ a)
    return np.sqrt(np.diag(ainv @ s @ ainv))


def dist_lag_fit(y: pd.Series, x: pd.Series, j_max: int) -> dict:
    xl = pd.DataFrame({f"x{j}": x.shift(j) for j in range(j_max + 1)})
    df = pd.concat([y.rename("y"), xl], axis=1, sort=True).dropna()
    a = np.column_stack([np.ones(len(df)), df[[f"x{j}" for j in range(j_max + 1)]].values])
    beta, *_ = np.linalg.lstsq(a, df["y"].values, rcond=None)
    resid = df["y"].values - a @ beta
    se = nw_se(a, resid, NW_LAG)
    b, sb = beta[1:], se[1:]
    r2 = 1.0 - resid.var() / df["y"].values.var()
    return {
        "n": len(df),
        "b": [round(float(v), 4) for v in b],
        "t": [round(float(bi / si), 2) for bi, si in zip(b, sb, strict=True)],
        "cum": [round(float(v), 4) for v in np.cumsum(b)],
        "long_run": round(float(b.sum()), 4),
        "r2": round(float(r2), 3),
    }


def trailing_k_fit(y: pd.Series, x: pd.Series, k: int) -> dict:
    trail = x.rolling(k).mean() * 4.0  # annualised trailing-K inflation
    anchor = float(trail.loc[:TRAIN_VAL_END].mean())
    df = pd.concat([y.rename("y"), (trail - anchor).rename("z")], axis=1, sort=True).dropna()
    a = np.column_stack([np.ones(len(df)), df["z"].values])
    beta, *_ = np.linalg.lstsq(a, df["y"].values, rcond=None)
    resid = df["y"].values - a @ beta
    se = nw_se(a, resid, NW_LAG)
    return {
        "k": k,
        "n": len(df),
        "c_anchor": round(anchor, 5),
        "alpha": round(float(beta[0]), 5),
        "b_infl": round(float(beta[1]), 4),
        "t": round(float(beta[1] / se[1]), 2),
        "r2": round(float(1.0 - resid.var() / df["y"].values.var()), 3),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, help="quarterly CSV: date,value")
    p.add_argument("--label", required=True)
    p.add_argument("--cpi-csv", default=None)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    y_full = read_quarterly_csv(args.target)
    x = fetch_cpi(args.cpi_csv)

    y = y_full.loc[:TRAIN_VAL_END]
    held_out = y_full.loc[TRAIN_VAL_END:]
    if len(held_out) > 1:
        print(
            f"NOTE: {len(held_out) - 1} post-boundary rows EXCLUDED from fit (Ruling-A check only)"
        )

    diag = dist_lag_fit(y, x, J_DIAG)
    primary = trailing_k_fit(y, x, K_PRIMARY)
    sens = [trailing_k_fit(y, x, k) for k in K_SENS]

    out = {
        "amendment": "AM-2026-08-15-001",
        "run_date": date.today().isoformat(),
        "target_file": args.target,
        "target_sha256": sha256(args.target),
        "target_label": args.label,
        "cpi_source": args.cpi_csv or "fred.CPIAUCSL (fetched)",
        "train_val_end": TRAIN_VAL_END,
        "declared": {
            "k_primary": K_PRIMARY,
            "k_sensitivities": list(K_SENS),
            "j_diagnostic": J_DIAG,
            "nw_lag": NW_LAG,
        },
        "primary_trailing_k": primary,
        "sensitivities_recorded_not_adopted": sens,
        "distributed_lag_diagnostic": diag,
        "post_boundary_rows_held_for_ruling_a_check": {
            str(d.date()): round(float(v), 5) for d, v in held_out.items()
        },
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(
        f"label={args.label}  n={primary['n']}  "
        f"b_infl(K={K_PRIMARY})={primary['b_infl']:+.3f} (t={primary['t']})  "
        f"LR pass-through={diag['long_run']:+.2f}  diag R2={diag['r2']}"
    )
    cum = diag["cum"]
    lr = diag["long_run"] if diag["long_run"] != 0 else 1.0
    print(
        f"cum PT: K=4 {cum[3]:+.2f} ({cum[3] / lr:.0%})  "
        f"K=8 {cum[7]:+.2f} ({cum[7] / lr:.0%})  "
        f"K=12 {cum[11]:+.2f} ({cum[11] / lr:.0%})"
    )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
