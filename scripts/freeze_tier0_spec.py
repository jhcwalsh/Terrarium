"""Freeze the tier-0 cashflow benchmark spec (WP3.5) — before tier 1 exists.

Run:  uv run python scripts/freeze_tier0_spec.py

The standing rule (STEP3 plan, G3-pre's tier0_beats_rule): the transparent
benchmark's specification freezes BEFORE the market-sensitive tier is tuned.
Tier 0 is the register's classic constant-G Takahashi-Alexander, run through
the SAME cohort recursion tier 1 uses with the linkage OFF (f_call = f_dist =
1) and NAV growth fixed at a constant G.

G is MEASURED, not assumed: the annualized mean monthly public total return
(french.mkt_rf + french.rf) over train+validation — the PME-neutral choice (a
cohort growing at the public rate has PME ~ 1 by construction, so tier 0
embodies "private assets are public assets with a J-curve", exactly the
assumption-free strawman tier 1 must beat). The historical-simulation leg the
plan names (replay of observed rate profiles from ALB-A/C) is UNPARAMETERIZABLE
— those series were never delivered — and is recorded as such with its
trigger, not silently dropped.

Output: ``mappings/cashflow-tier0-v1.0.yaml``. Deterministic, no RNG.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ah.data.catalog import Catalog
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]
TIER0_VERSION = "tier0-2026.08"


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))

    def monthly(sid: str) -> pd.Series:
        frame = access.train_val(sid)
        return pd.Series(
            pd.to_numeric(frame["value"]).to_numpy(dtype=float),
            index=pd.to_datetime(frame["date"]),
        )

    total = (monthly("french.mkt_rf") + monthly("french.rf")).dropna()
    g_annual = float((1.0 + total.mean()) ** 12 - 1.0)

    out = _REPO_ROOT / "mappings" / "cashflow-tier0-v1.0.yaml"
    out.write_text(
        "\n".join(
            [
                "# mappings/cashflow-tier0-v1.0.yaml — scripts/freeze_tier0_spec.py",
                f"# vintage {vintage}; train+validation only. FROZEN BEFORE TIER 1 EXISTS",
                "# (the standing benchmark-first rule; G3-pre's tier0_beats_rule is the judge).",
                f"tier0_version: {TIER0_VERSION}",
                f'campaign_vintage_id: "{vintage}"',
                "form: >-",
                "  The model-parameter-register section 1 classic TA, run through the SAME",
                "  cohort recursion tier 1 uses with the linkage OFF: f_call = f_dist = 1,",
                "  NAV growth constant at g_annual. Terminal liquidation at age >= L",
                "  (extensions excluded). One model, linkage on or off - never two models.",
                f"g_annual: {g_annual:.6f}",
                "g_source: >-",
                "  Annualized mean monthly public total return (french.mkt_rf + french.rf),",
                f"  {len(total)} train+validation months. PME-neutral by construction: tier 0",
                "  embodies 'private assets are public assets with a J-curve', the",
                "  assumption-free strawman the market-sensitive tier must beat.",
                "historical_simulation_leg: >-",
                "  UNPARAMETERIZABLE - the plan's replay-observed-rate-profiles leg needs",
                "  ALB-A/C, never delivered (the sealed PM unavailability). Recorded with",
                "  its trigger (first ALB-A/C delivery -> parameterize by amendment), not",
                "  silently dropped. Until then tier 0 is the constant-G TA alone and every",
                "  tier-0 claim says so.",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out.name}: g_annual = {g_annual:.4%} over {len(total)} months")


if __name__ == "__main__":
    main()
