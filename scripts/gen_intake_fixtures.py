"""Generate manual-intake fixtures — clean and deliberately corrupted (WP1.3).

Run:  uv run python scripts/gen_intake_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures" / "data" / "intake"


def _w(rel: str, text: str) -> None:
    p = FX / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build() -> None:
    # --- Albourne PM returns (grouped by strategy, quarterly) ---
    _w(
        "albourne/pm-returns_2026Q2.csv",
        "period,strategy,ret\n"
        "2026Q1,buyout,0.03\n2026Q2,buyout,-0.02\n"
        "2026Q1,dl,0.02\n2026Q2,dl,0.01\n",
    )
    _w(  # duplicate period within a strategy
        "albourne/pm-returns-dup_2026Q2.csv",
        "period,strategy,ret\n2026Q1,buyout,0.03\n2026Q1,buyout,0.04\n2026Q2,buyout,-0.02\n",
    )
    _w(  # out-of-bounds return
        "albourne/pm-returns-oob_2026Q2.csv",
        "period,strategy,ret\n2026Q1,buyout,0.03\n2026Q2,buyout,5.0\n",
    )
    _w(  # missing required column 'ret'
        "albourne/pm-returns-missing_2026Q2.csv",
        "period,strategy\n2026Q1,buyout\n2026Q2,buyout\n",
    )

    # --- Albourne derived cashflow: A lifecycle, B calendar (+gap) ---
    _w(
        "albourne/cf-lifecycle_2026Q2.csv",
        "strategy,fund_age,metric,mean,p25,p75\n"
        "buyout,1,call_rate,0.25,0.15,0.35\n"
        "buyout,2,call_rate,0.30,0.20,0.40\n",
    )
    _w(
        "albourne/cf-calendar_2026Q2.csv",
        "period,strategy,agg_call_rate,agg_dist_rate,net_cf_yield\n"
        "2026Q1,buyout,0.05,0.03,-0.02\n2026Q2,buyout,0.04,0.06,0.02\n",
    )
    _w(  # silent gap: Q1 then Q3 (Q2 missing)
        "albourne/cf-calendar-gap_2026Q2.csv",
        "period,strategy,agg_call_rate,agg_dist_rate,net_cf_yield\n"
        "2026Q1,buyout,0.05,0.03,-0.02\n2026Q3,buyout,0.04,0.06,0.02\n",
    )

    # --- Cliffwater CDLI (single series, quarterly) ---
    _w("cliffwater/cdli_2026Q2.csv", "period,ret\n2026Q1,0.025\n2026Q2,0.027\n")

    print(f"wrote intake fixtures under {FX}")


if __name__ == "__main__":
    build()
