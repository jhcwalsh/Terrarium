"""Measure everything pre-registration-g3.yaml seals — the provenance script.

Run:  uv run python scripts/measure_g3_reference.py

Emits a YAML fragment (stdout + g3-reference-measured.yaml in the repo root,
gitignored-adjacent scratch: the sealed document QUOTES these numbers verbatim
and names this script as their provenance, the scripts/measure_seal_evidence.py
pattern from G2). Two sections:

1. Per-sleeve tail bands: ah.eval.sleevetails over the current vintage,
   train+validation only. Deterministic (fixed seeds inside sleevetails).
2. 2022 episode reference quantities, measured from the store:
   - public equity total-return drawdown over 2022 (french.mkt_rf + french.rf,
     cumulated 2021-12 base, peak-to-trough through 2023-12);
   - the observed REPORTED 2022-23 drawdown of each modeled HF sleeve's
     equal-weight composite (reported = as delivered, NOT de-smoothed: the
     mark-lag criterion is about what statements showed);
   - the 10y rate move and CPI YoY peak over 2022 (fred.DGS10, fred.CPI).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.eval import sleevetails as st
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _drawdown(cum: np.ndarray) -> float:
    peak = np.maximum.accumulate(cum)
    return float(np.min(cum / peak - 1.0))


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))

    lines: list[str] = [f"# measured by scripts/measure_g3_reference.py on vintage {vintage}"]

    # -- 1. per-sleeve tail bands ------------------------------------------- #
    lines.append("sleeve_tail_thresholds:")
    for sleeve_id, members in st.hf_sleeve_members().items():
        composite = st.reference_composite(access, members)
        lines.append(f"  {sleeve_id}:")
        lines.append(f"    members: [{', '.join(members)}]")
        lines.append(f"    train_val_months: {composite.size}")
        for band in st.sleeve_bands(sleeve_id, composite):
            lines.append(
                f"    {band.statistic}: {{point: {band.point:.6f}, "
                f"lo: {band.lo:.6f}, hi: {band.hi:.6f}, "
                f"min: {band.threshold_min:.6f}, max: {band.threshold_max:.6f}, "
                f"severity: {band.severity}}}"
            )

    # -- 2. episode reference quantities ------------------------------------ #
    def monthly(sid: str, start: str, end: str) -> pd.Series:
        frame = catalog.read_observations(vintage, sid)
        s = frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")["value"]
        return s.loc[start:end]

    mkt = monthly("french.mkt_rf", "2021-12-01", "2023-12-31")
    rf = monthly("french.rf", "2021-12-01", "2023-12-31")
    total = (1.0 + mkt.add(rf, fill_value=0.0)).cumprod()
    public_dd = _drawdown(total.to_numpy())

    dgs10 = monthly("fred.DGS10", "2021-12-01", "2022-12-31")
    cpi = monthly("fred.CPI", "2020-12-01", "2022-12-31")
    cpi_yoy_peak = float((cpi.pct_change(12).dropna()).max())

    lines.append("episode_2022_measured:")
    lines.append(f"  public_equity_drawdown: {public_dd:.4f}  # french.mkt_rf+rf TR, 2021-12 base")
    lines.append(f"  dgs10_move_2022_pp: {float(dgs10.iloc[-1] - dgs10.iloc[0]):.2f}")
    lines.append(f"  cpi_yoy_peak: {cpi_yoy_peak:.4f}")
    lines.append("  sleeve_reported_drawdown_2022_23:  # REPORTED composites, not de-smoothed")
    for sleeve_id, members in st.hf_sleeve_members().items():
        cols = []
        for sid in members:
            frame = catalog.read_observations(vintage, sid)
            s = frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")["value"]
            cols.append(s.loc["2021-12-01":"2023-12-31"])
        comp = pd.concat(cols, axis=1).mean(axis=1, skipna=True).sort_index()
        dd = _drawdown((1.0 + comp).cumprod().to_numpy())
        lines.append(f"    {sleeve_id}: {dd:.4f}")

    text = "\n".join(lines) + "\n"
    out = _REPO_ROOT / "g3-reference-measured.yaml"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"# wrote {out.name}")


if __name__ == "__main__":
    main()
