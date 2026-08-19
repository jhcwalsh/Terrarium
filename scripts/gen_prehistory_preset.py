"""Generate the inherited-decade preset (cio-04 Task 1, DN-8 O-1 option A).

Run from the repo root:  uv run python scripts/gen_prehistory_preset.py

Writes src/ah/presets/prehistory.json — a validated draft WorldSpec that is
NOT a playable world in its own right. It is the calm structural past every
world inherits: a 40-quarter, single-regime, crisis-free decade run through
the same toy-v0 engine (Task 2 offsets its seed per world). Follows the same
idiom as scripts/gen_presets.py (same key layout via sort_keys, same
newline="\n" discipline) but is standalone rather than importing it, since
this preset's shape (no crisis window, one benign regime, pre-history
narrative) is a deliberate one-off rather than a member of the four-preset
family that script builds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "ah" / "presets"

# World ids: see scripts/gen_presets.py's block-convention comment. The 52x
# sub-block is toy-v0.7 (ER-14 close-out, D-ER14-2); 521-524 are already
# taken by the four playable presets, so this one is 525 -- same engine
# generation, its own id.
WORLD_ID = "00000000-0000-4000-9000-000000000525"


def build_prehistory_preset() -> dict[str, Any]:
    title = "The Inherited Decade"
    return {
        "spec_version": "1.2.0",
        "world_id": WORLD_ID,
        "status": "draft",
        "provenance": {
            "created_at": "2026-08-14T00:00:00Z",
            "author": "sso:preset",
            "source": {"kind": "preset"},
        },
        "narrative": {
            "language": "en",
            "title": title,
            "tagline": "Ten quiet years, on purpose.",
            "summary": (
                f"{title}: the plan's own past, not a playable world. A "
                "deliberately unremarkable decade the toy engine renders "
                "before any world begins, so the plan chart has somewhere "
                "to come from."
            ),
            "lesson": (
                "This decade is display-only pre-history for cio-04 -- it "
                "establishes the calm structure every world inherits, "
                "scaled to terminate at that world's own opening book."
            ),
            "dispatches": [
                {"date": "2017", "headline": f"{title} — a quiet start"},
                {"date": "2021", "headline": f"{title} — steady as she goes"},
                {"date": "2025", "headline": f"{title} — right on schedule"},
            ],
        },
        # Starts a decade before the four playable presets' own 2027-Q1 start,
        # so it reads plainly as "before": 40 quarters = 2017-Q1..2026-Q4.
        "horizon": {"start": "2017-Q1", "quarters": 40},
        "regimes": {
            "mode": "sequence",
            "sequence": [{"regime": "expansion", "from_quarter": 0, "to_quarter": 39}],
        },
        "factor_conditions": {
            "policy_rate": {"start_pct": 3.0, "end_pct": 3.0},
            "inflation": {"average_pct": 2.0, "peak_pct": 4.0, "peak_quarter": 6},
            "equity": {"drift_annual_pct": 7.0, "vol_annual_pct": 14.0},
            "credit": {
                "hy_spread_start_bps": 350.0,
                "hy_spread_peak_bps": 550.0,
                "peak_quarter": 12,
            },
            "commodities": {"drift_annual_pct": 2.0},
            "correlation": {"equity_bond_regime": "inflation_conditional"},
            # No crisis_windows key: the inherited decade carries no crisis
            # by construction (task-1-brief.md Step 3).
        },
        "structural": {"parameter_vintage": "current"},
        "engine_defaults": {
            "generator_id": "toy-v0",
            "n_paths": 1000,
            # Left as goldilocks's own base_seed -- Task 2 overrides the seed
            # per world via PREHISTORY_SEED_OFFSET; this default is never
            # read for that purpose.
            "base_seed": 42,
        },
        "extensions": {},
    }


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = build_prehistory_preset()
    (OUT / "prehistory.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote prehistory preset to {OUT / 'prehistory.json'}")


if __name__ == "__main__":
    build()
