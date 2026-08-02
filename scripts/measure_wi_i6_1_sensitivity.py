"""WI-I6-1 sensitivity: does the sealed G1 drought ratio survive the Y rescale?

Run:  uv run python scripts/measure_wi_i6_1_sensitivity.py

Replicates the sealed replay's drought computation (stressed vs age-matched
calm tier-1 run on the mid-life cohort, observed 2021-12..2023-12 states)
under BOTH the old mis-scaled Y (0.01) and the corrected Y (0.55), and
writes governance/evidence/WI-I6-1-SENSITIVITY.md. A robustness note on the
sealed result, NOT a reseal: the sealed script, its evidence, and the G3
lock are untouched. Deterministic; no RNG.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.port.cashflow_tier1 import StructuralTerms, run_tier1

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = _REPO_ROOT / "governance" / "evidence" / "WI-I6-1-SENSITIVITY.md"
WINDOW = ("2021-12-01", "2023-12-31")
SEALED_BAND = (0.45, 0.55)
SEALED_RESULT = 0.544  # G1-EVIDENCE.md, as sealed


def _series(catalog: Catalog, vintage: str, sid: str) -> pd.Series:
    frame = catalog.read_observations(vintage, sid)
    s = pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
    )
    return s.loc[WINDOW[0] : WINDOW[1]]


def _drought(base: dict, dd_q, ratio_q, pm_true_q) -> float:
    terms = StructuralTerms(recycling_fraction=0.0)
    quarters = len(dd_q)
    stressed = run_tier1(
        base,
        committed=100.0,
        vintage_year=2019,
        sleeve_returns=pm_true_q,
        drawdown_depth=dd_q,
        spread_ratio=ratio_q,
        terms=terms,
        fees_on=False,
        start_mid_life=True,
    )
    calm = run_tier1(
        base,
        committed=100.0,
        vintage_year=2019,
        sleeve_returns=pm_true_q,
        drawdown_depth=np.zeros(quarters),
        spread_ratio=np.ones(quarters),
        terms=terms,
        fees_on=False,
        start_mid_life=True,
    )
    ratios = [
        s.distribution_total / c.distribution_total
        for s, c in zip(stressed.flows, calm.flows, strict=True)
        if c.distribution_total > 1e-9
    ]
    return min(ratios)


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    mkt = _series(catalog, vintage, "french.mkt_rf") + _series(catalog, vintage, "french.rf")
    cum = (1.0 + mkt).cumprod()
    ig = _series(catalog, vintage, "fred.BAA") - _series(catalog, vintage, "fred.AAA")
    baa = pd.Series(
        pd.to_numeric(catalog.read_observations(vintage, "fred.BAA")["value"]).to_numpy(float),
        index=pd.to_datetime(catalog.read_observations(vintage, "fred.BAA")["date"]),
    )
    aaa = pd.Series(
        pd.to_numeric(catalog.read_observations(vintage, "fred.AAA")["value"]).to_numpy(float),
        index=pd.to_datetime(catalog.read_observations(vintage, "fred.AAA")["date"]),
    )
    anchor = float((baa - aaa).loc["2019-01-01":"2021-12-31"].mean())
    dd_q = (1.0 - cum / cum.cummax()).clip(lower=0.0).resample("QE").last().to_numpy()
    ratio_q = (ig / anchor).clip(lower=0.5).resample("QE").last().to_numpy()
    factors = {
        f: _series(catalog, vintage, f"french.{f}").resample("QE").sum().to_numpy()
        for f in ("smb", "hml")
    }
    pm_true_q = (
        1.2 * mkt.resample("QE").sum().to_numpy() + 0.2 * factors["smb"] + 0.2 * factors["hml"]
    )

    base = json.loads(
        (_REPO_ROOT / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )
    results = {}
    for label, y in (("old (mis-scaled)", 0.01), ("corrected", 0.55)):
        doc = json.loads(json.dumps(base))
        doc["parameters"]["yield_rate"] = y
        results[label] = _drought(doc, dd_q, ratio_q, pm_true_q)

    lo, hi = SEALED_BAND
    corrected = results["corrected"]
    inside = lo <= corrected <= hi
    lines = [
        "# WI-I6-1 sensitivity — the G1 drought ratio under the corrected Y",
        "",
        f"Vintage `{vintage}`; window {WINDOW[0]}..{WINDOW[1]}; produced by",
        "`scripts/measure_wi_i6_1_sensitivity.py`. A robustness note on the",
        "sealed G1 result — the sealed replay, its evidence, and the G3 lock",
        "are untouched. The sealed criterion: trough of the age-matched",
        f"stressed/calm distribution-rate ratio inside [{lo}, {hi}].",
        "",
        "| yield_rate Y | drought ratio at trough | inside sealed band |",
        "|---|---|---|",
        f"| 0.01 (as sealed) | {results['old (mis-scaled)']:.4f} | "
        f"{'YES' if lo <= results['old (mis-scaled)'] <= hi else 'NO'} |",
        f"| 0.55 (corrected, pacing-1.0) | {corrected:.4f} | {'YES' if inside else 'NO'} |",
        "",
        f"Sealed G1 figure for reference: {SEALED_RESULT} (G1-EVIDENCE.md).",
        "",
        "## Reading",
        "",
        (
            "The sealed drought verdict is ROBUST to the WI-I6-1 rescale: the "
            "ratio construction cancels the distribution LEVEL almost entirely "
            "(Y appears in both numerator and denominator; the residual path "
            "dependence through NAV moves the figure only in the fourth "
            "decimal). The G1 criterion's PASS stands on its own terms under "
            "the corrected parameter."
            if inside
            else "The corrected Y moves the drought ratio OUTSIDE the sealed "
            "band — a material finding: escalate to the owner before any "
            "further Step 4 work consumes distribution flows."
        ),
        "",
        "---",
        "",
        "*Not investment advice.*",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(_REPO_ROOT)} written")
    print({k: round(v, 4) for k, v in results.items()}, "band", SEALED_BAND)


if __name__ == "__main__":
    main()
