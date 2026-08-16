"""C2 theta calibration from the Cliffwater CDLI realised-loss series
(AM-2026-08-15-001, declared match rule in the design note SS4.1).

Declared BEFORE any CDLI data was seen:
* theta_DL solves  mean over train+val of  theta * max(ig_spread_{t-4} - s_bar, 0)
  == CDLI mean annualised net realised-loss rate / 4.
* s_bar = median ig_spread over train+validation (catalog factor, pp).
* Acceptance (never calibration): cumulative modelled DL loss 2008Q1-2010Q4
  within +/-30% of CDLI cumulative for the same window; a miss is written up
  as a functional-form failure, not tuned away.
* mezzanine theta = 1.5 x DL; distressed theta = 0.5 x DL (deliberate,
  stated asymmetry -- see the note).
* Deterministic; ASCII console; input CSV hashed into provenance.

Input CSV: columns  date, loss_rate  (annualised net realised-loss rate,
decimal, quarterly observations), exported from the Cliffwater CDLI
workbook (registration-tier; NOT committed -- hash only).

Usage:
  uv run python scripts/fit_credit_loss_theta.py \
      --cdli cdli_losses.csv --out artifacts/c2/theta-provenance.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# ah.* imports deferred to call time (unit-testable without the data layer)

_REPO_ROOT = Path(__file__).resolve().parents[1]

TRAIN_VAL_END = "2020-12-31"
LOSS_LAG_Q = 4
GFC_WINDOW = ("2008-01-01", "2010-12-31")
GFC_TOLERANCE = 0.30
THETA_MULT = {"pm_direct_lending": 1.0, "pm_mezzanine": 1.5, "pm_distressed": 0.5}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ig_spread_quarterly(access) -> pd.Series:
    """ig_spread (pp) from the catalog, quarterly-last -- the panel convention."""
    frame = access.train_val("ig_spread")
    s = pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
    ).sort_index()
    return s.resample("QE").last().dropna()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cdli", required=True, help="CDLI CSV: date,loss_rate")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    cdli = pd.read_csv(args.cdli)
    cdli.columns = [c.strip().lower() for c in cdli.columns]
    loss = pd.Series(
        pd.to_numeric(cdli["loss_rate"]).to_numpy(dtype=float),
        index=pd.to_datetime(cdli["date"]),
    ).sort_index()
    loss_tv = loss.loc[:TRAIN_VAL_END]
    target_mean_q = float(loss_tv.mean()) / 4.0  # annualised -> quarterly

    from ah.data.catalog import Catalog
    from ah.splits import DataAccess

    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))
    spread = ig_spread_quarterly(access).loc[:TRAIN_VAL_END]
    s_bar = float(spread.median())
    excess = np.maximum(spread.shift(LOSS_LAG_Q) - s_bar, 0.0).dropna()

    mean_excess = float(excess.mean())
    if mean_excess <= 0.0:
        raise SystemExit("mean lagged excess spread is zero; match rule undefined")
    theta_dl = target_mean_q / mean_excess

    # acceptance: GFC cumulative, model vs CDLI (never a calibration input)
    gfc = slice(*GFC_WINDOW)
    model_gfc = float((theta_dl * excess.loc[gfc]).sum())
    cdli_gfc = float((loss.loc[gfc] / 4.0).sum())
    rel_err = abs(model_gfc - cdli_gfc) / cdli_gfc if cdli_gfc else float("nan")
    verdict = "PASS" if rel_err <= GFC_TOLERANCE else "FAIL"

    out = {
        "amendment": "AM-2026-08-15-001",
        "run_date": date.today().isoformat(),
        "cdli_file": args.cdli,
        "cdli_sha256": sha256(args.cdli),
        "vintage": vintage,
        "train_val_end": TRAIN_VAL_END,
        "declared": {
            "loss_lag_q": LOSS_LAG_Q,
            "gfc_window": list(GFC_WINDOW),
            "gfc_tolerance": GFC_TOLERANCE,
            "theta_multipliers": THETA_MULT,
        },
        "s_bar_pp": round(s_bar, 4),
        "cdli_mean_loss_annual": round(float(loss_tv.mean()), 5),
        "theta": {k: round(theta_dl * m, 6) for k, m in THETA_MULT.items()},
        "acceptance_gfc": {
            "model_cumulative": round(model_gfc, 5),
            "cdli_cumulative": round(cdli_gfc, 5),
            "relative_error": round(rel_err, 3),
            "verdict": verdict,
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(
        f"theta_DL={theta_dl:.5f}/pp-quarter  s_bar={s_bar:.2f}pp  "
        f"GFC check: model {model_gfc:.3f} vs CDLI {cdli_gfc:.3f} "
        f"(err {rel_err:.0%}) -> {verdict}"
    )
    if verdict == "FAIL":
        print(
            "ACCEPTANCE FAILED: functional form written up as wrong per the "
            "note; theta is NOT tuned to pass."
        )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
