"""Pin the ANNUAL-ERA play tapes before the quarterly clock lands (D-QC-1).

Generated from the pre-change code (parent of the first qc-02-server
implementation commit) and NEVER regenerated afterward: the committed
digests are what the quarterly release must reproduce bit-identically on
(a) the no-decision flat play and (b) a scripted annual decision map --
spec acceptance criterion 3 and the replay half of criterion 4.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import simulate_play

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
OUT = ROOT / "tests" / "fixtures" / "qc" / "annual-era-baseline.json"

#: The four live toy presets (the shipped decade worlds).
WORLDS = ("stagflation", "goldilocks", "deflation_bust", "reflation_boom")

#: A representative annual-era decision map: one of each action, plus a
#: commitment override at a year-close window, all on the annual grid.
ANNUAL_DECISIONS = {
    11: "derisk",
    23: {"action": "leanin", "commitments": {"pe": 5.0, "infra": 1.0}},
    35: "secondary",
    47: {"action": "commit", "commitments": {"pc": 0.0}},
    59: "hold",
}


def _paths(preset: str):
    doc = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


def quarter_doc(q) -> dict:
    """Every numeric field a PlayQuarter carries (play.py:415-485), plus
    the per-sleeve maps.

    repr-float canonical JSON: any bit-level drift in any field changes
    the digest.
    """
    return {
        "quarter": q.quarter,
        "month": q.month,
        "cash": q.cash,
        "nav_true": q.nav_true,
        "nav_reported": q.nav_reported,
        "calls_paid": q.calls_paid,
        "distributions_received": q.distributions_received,
        "spending_paid": q.spending_paid,
        "forced_sale_total": q.forced_sale_total,
        "private_weight_true": q.private_weight_true,
        "private_weight_reported": q.private_weight_reported,
        "unfunded_total": q.unfunded_total,
        "drawdown_depth": q.drawdown_depth,
        "spread_ratio": q.spread_ratio,
        "f_dist": q.f_dist,
        "f_call": q.f_call,
        "new_commitments": q.new_commitments,
        "spending_basis": q.spending_basis,
        "spending_rate_annual": q.spending_rate_annual,
        "expired_undrawn": q.expired_undrawn,
        "terminal_distributions": q.terminal_distributions,
        "vintage_nav": dict(q.vintage_nav),
        "liquid_values": dict(q.liquid_values),
        "private_true": dict(q.private_true),
        "private_reported": dict(q.private_reported),
        "private_calls": dict(q.private_calls),
        "private_distributions": dict(q.private_distributions),
        "private_unfunded": dict(q.private_unfunded),
        "private_expired": dict(q.private_expired),
        "nav_true_months": list(q.nav_true_months),
        "nav_reported_months": list(q.nav_reported_months),
    }


def tape_digest(result) -> str:
    doc = {
        "quarters": [quarter_doc(q) for q in result.quarters],
        "final_value": result.final_value,
        "forced_sale_quarters": result.forced_sale_quarters,
        "total_forced_sales": result.total_forced_sales,
        "forced_secondaries": result.forced_secondaries,
    }
    blob = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("ascii")).hexdigest()


def main() -> None:
    out: dict[str, dict[str, str]] = {}
    for preset in WORLDS:
        paths = _paths(preset)
        out[preset] = {
            "flat_play": tape_digest(simulate_play(paths, None)),
            "flat_play_true_basis": tape_digest(simulate_play(paths, None, use_reported=False)),
            "annual_decisions": tape_digest(simulate_play(paths, ANNUAL_DECISIONS)),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
