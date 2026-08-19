"""Generate the four preset worlds (STEP0-PLAN §WP0.9).

Run from the repo root:  uv run python scripts/gen_presets.py

Writes src/ah/presets/{name}.json — full WorldSpec drafts (status=draft,
generator_id=toy-v0) that pass the validator with no blocking findings. The
`stagflation` preset mirrors the canonical example. These are committed and loaded
by `ah world build --preset <name>`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "ah" / "presets"


def _regime(infl: float) -> str:
    if infl >= 4:
        return "stagflation"
    if infl < 0:
        return "deflation_boom"
    return "expansion"


def preset(
    *,
    world_id: str,
    title: str,
    tagline: str,
    infl: float,
    rate_start: float,
    rate_end: float,
    eq_drift: float,
    eq_vol: float,
    commod: float,
    hy_start: float,
    hy_peak: float,
    crisis: tuple[int, int, float] | None,
    vintage: str,
    quarters: int = 40,
    base_seed: int = 42,
    pe_mult_drift: float = -2.0,
) -> dict[str, Any]:
    fc: dict[str, Any] = {
        "policy_rate": {"start_pct": rate_start, "end_pct": rate_end},
        "inflation": {"average_pct": infl, "peak_pct": infl + 2.0, "peak_quarter": 6},
        "equity": {"drift_annual_pct": eq_drift, "vol_annual_pct": eq_vol},
        "credit": {
            "hy_spread_start_bps": hy_start,
            "hy_spread_peak_bps": hy_peak,
            "peak_quarter": 12,
        },
        "commodities": {"drift_annual_pct": commod},
        "correlation": {"equity_bond_regime": "inflation_conditional"},
    }
    if crisis is not None:
        fc["crisis_windows"] = [
            {"start_quarter": crisis[0], "length_quarters": crisis[1], "severity": crisis[2]}
        ]
    structural: dict[str, Any] = {"parameter_vintage": vintage}
    if vintage == "custom":
        structural["private_equity"] = {
            # ER-14 close-out (D-ER14-2): mu_PE makes multiple compression
            # respond to inflation_excess endogenously; a hand-authored
            # negative drift here would charge the same effect twice. Default
            # -2.0 preserves every existing preset; only stagflation is zeroed
            # (Task M5), so no other preset's number moves.
            "entry_multiple_drift_annual_pct": pe_mult_drift,
            "leverage_turns": 5.5,
            "illiquidity_premium_annual_pct": 2.0,
        }
    return {
        "spec_version": "1.2.0",
        "world_id": world_id,
        "status": "draft",
        "provenance": {
            "created_at": "2026-07-24T00:00:00Z",
            "author": "sso:preset",
            "source": {"kind": "preset"},
        },
        "narrative": {
            "language": "en",
            "title": title,
            "tagline": tagline,
            "summary": f"{title}: a preset world for the Step-0 loop.",
            "lesson": "Presets exercise the compile->validate->run->replay rails.",
            "dispatches": [
                {"date": "2027", "headline": f"{title} — year one"},
                {"date": "2030", "headline": f"{title} — mid-horizon"},
                {"date": "2034", "headline": f"{title} — late cycle"},
            ],
        },
        "horizon": {"start": "2027-Q1", "quarters": quarters},
        "regimes": {
            "mode": "sequence",
            "sequence": [{"regime": _regime(infl), "from_quarter": 0, "to_quarter": quarters - 1}],
        },
        "factor_conditions": fc,
        "structural": structural,
        "engine_defaults": {
            "generator_id": "toy-v0",
            "n_paths": 1000,
            "base_seed": base_seed,
        },
        "extensions": {},
    }


# World ids carry the ENGINE GENERATION in their last block: the 3xx series was
# toy-v0.3 (register ER-1 + ER-4); the 4xx series was toy-v0.4 (Student-t
# tails), which NEVER MERGED — its gate exposed the missing limited-liability
# floor; the 50x sub-block is toy-v0.5 (ER-7 closed: tails + the -99% monthly
# floor); the 51x sub-block is toy-v0.6 (ER-10 closed: reported marks catch
# up to true marks); the 52x sub-block is toy-v0.7 (ER-14 close-out,
# D-ER14-2, 2026-08-18: four inflation channels + the infra sleeve). The
# engine is not part of a WorldSpec, so
# nothing would otherwise stop scores made under two different engines sharing
# a leaderboard row — the board is keyed (world_id, seed, decision_alpha_version),
# and the alpha DEFINITION is unchanged, so world identity is the only place
# the difference can live. G0-EVIDENCE.md keeps citing the 001 world: that is a
# record of what G0 actually ran, and must not be rewritten.
PRESETS = {
    "stagflation": preset(
        world_id="00000000-0000-4000-9000-000000000521",
        title="The Long Stagflation",
        tagline="A decade prices refused to behave.",
        infl=6.5,
        rate_start=5.5,
        rate_end=7.5,
        eq_drift=3.0,
        eq_vol=22.0,
        commod=11.0,
        hy_start=400.0,
        hy_peak=2200.0,
        crisis=(8, 6, 0.55),
        vintage="custom",
        base_seed=771204,
        # ER-14 close-out (D-ER14-2, Task M5): mu_PE now makes multiple
        # compression respond to inflation_excess; zeroed here so the -2.0
        # authored drift is not double-charged. R-6: only the LIVE presets
        # are zeroed - stagflation_1974 is hand-edited separately (it is not
        # generated by this script); the four retired 7xx/8xx/601-block
        # worlds are untouched records.
        pe_mult_drift=0.0,
    ),
    "goldilocks": preset(
        world_id="00000000-0000-4000-9000-000000000522",
        title="Goldilocks",
        tagline="Steady growth, tame inflation, calm credit.",
        infl=2.0,
        rate_start=3.0,
        rate_end=3.0,
        eq_drift=7.0,
        eq_vol=14.0,
        commod=2.0,
        hy_start=350.0,
        hy_peak=550.0,
        crisis=None,
        vintage="current",
        base_seed=42,
    ),
    "deflation_bust": preset(
        world_id="00000000-0000-4000-9000-000000000523",
        title="Deflation Bust",
        tagline="Falling prices, a hard credit crunch.",
        infl=-1.0,
        rate_start=4.0,
        rate_end=1.0,
        eq_drift=-3.0,
        eq_vol=26.0,
        commod=-4.0,
        hy_start=500.0,
        hy_peak=1800.0,
        crisis=(6, 6, 0.8),
        vintage="current",
        base_seed=1848,
    ),
    "reflation_boom": preset(
        world_id="00000000-0000-4000-9000-000000000524",
        title="Reflation Boom",
        tagline="Rates rise into a booming real economy.",
        infl=3.5,
        rate_start=1.0,
        rate_end=4.0,
        eq_drift=9.0,
        eq_vol=18.0,
        commod=6.0,
        hy_start=380.0,
        hy_peak=700.0,
        crisis=None,
        vintage="current",
        base_seed=2021,
    ),
}


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, world in PRESETS.items():
        (OUT / f"{name}.json").write_text(
            json.dumps(world, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(f"wrote {len(PRESETS)} presets to {OUT}")


if __name__ == "__main__":
    build()
