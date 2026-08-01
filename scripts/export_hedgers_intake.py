"""Export the HedgeRS AW panel from the HFModelling cache as an Albourne intake drop.

Run:  uv run python scripts/export_hedgers_intake.py
      [--hf-root C:/Users/james/PycharmProjects/HFModelling] [--out data/intake/albourne]

Reads the licensed HedgeRS caches (hedgers_aw_indices.csv + the MS Diversified
column of hedgers_multistrat_indices.csv), translates index names to the
platform's intake codes (WP2R.2: the code IS the registered series-id fragment,
so the applied series land under exactly the requirements.yaml ids), and writes
one long-form drop  data/intake/albourne/hf-returns_<asof>.csv  with columns
period,strategy,ret. The output lives under gitignored data/ — the panel is
COMM-licensed and never committed.

Deterministic: same inputs -> byte-identical drop (sorted, fixed formatting).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

#: HedgeRS index name -> intake code (== registered id fragment). The vendor
#: names also appear in taxonomy/albourne_mapping.yaml codes.hedgers with their
#: index ids; this table is the bridge's own spelling of the same inventory.
AW_NAME_TO_CODE: dict[str, str] = {
    "HedgeRS AW Asia Pacific L/S": "hf_asia_ls_ret_m",
    "HedgeRS AW EM L/S": "hf_em_ls_ret_m",
    "HedgeRS AW Japan L/S": "hf_japan_ls_ret_m",
    "HedgeRS AW US L/S": "hf_us_ls_ret_m",
    "HedgeRS AW European L/S": "hf_europe_ls_ret_m",
    "HedgeRS AW Activist": "hf_activist_ret_m",
    "HedgeRS AW Distressed / Restructuring": "hf_distressed_ret_m",
    "HedgeRS AW Emerging Market FI": "hf_em_fi_ret_m",
    "HedgeRS AW Risk Arbitrage": "hf_risk_arb_ret_m",
    "HedgeRS AW Fundamental Equity MN": "hf_fund_emn_ret_m",
    "HedgeRS AW Statistical Arbitrage": "hf_stat_arb_ret_m",
    "HedgeRS AW Quantitative Equity MN": "hf_quant_emn_ret_m",
    "HedgeRS AW Fixed Income Arbitrage": "hf_fi_arb_ret_m",
    "HedgeRS AW CB Arbitrage": "hf_cb_arb_ret_m",
    "HedgeRS AW Relative Value Credit": "hf_rv_credit_ret_m",
    "HedgeRS AW Structured Credit": "hf_structured_credit_ret_m",
    "HedgeRS AW Global Macro": "hf_global_macro_ret_m",
    "HedgeRS AW CTA": "hf_cta_ret_m",
    "HedgeRS AW Global Asset Allocation": "hf_gaa_ret_m",
    "HedgeRS AW Insurance": "hf_insurance_ret_m",
}
MS_NAME_TO_CODE: dict[str, str] = {
    "HedgeRS AW MS Diversified": "hf_ms_diversified_ret_m",
}


def build_drop(hf_root: Path) -> pd.DataFrame:
    frames = []
    for csv, table in (
        (hf_root / "data" / "hedgers_aw_indices.csv", AW_NAME_TO_CODE),
        (hf_root / "data" / "hedgers_multistrat_indices.csv", MS_NAME_TO_CODE),
    ):
        panel = pd.read_csv(csv, index_col=0, parse_dates=True)
        missing = sorted(set(table) - set(panel.columns))
        if missing:
            raise SystemExit(f"{csv.name}: expected columns absent: {missing}")
        for name, code in table.items():
            series = panel[name].dropna()
            frames.append(
                pd.DataFrame(
                    {
                        "period": series.index.to_period("M").astype(str),
                        "strategy": code,
                        "ret": series.to_numpy(),
                    }
                )
            )
    drop = pd.concat(frames, ignore_index=True).sort_values(
        ["strategy", "period"], ignore_index=True
    )
    return drop


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hf-root", type=Path, default=Path("C:/Users/james/PycharmProjects/HFModelling")
    )
    parser.add_argument("--out", type=Path, default=Path("data/intake/albourne"))
    args = parser.parse_args()

    drop = build_drop(args.hf_root)
    asof = max(drop["period"])
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"hf-returns_{asof}.csv"
    drop.to_csv(path, index=False, float_format="%.12g")
    print(
        f"wrote {path}  ({len(drop)} rows, {drop['strategy'].nunique()} series, "
        f"{drop['period'].min()} -> {asof})"
    )


if __name__ == "__main__":
    main()
