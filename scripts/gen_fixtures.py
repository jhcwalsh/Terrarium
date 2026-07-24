"""Generate the 50-scenario compiler regression fixtures (STEP0-PLAN §WP0.7).

Run from the repo root:  uv run python scripts/gen_fixtures.py

Emits fixtures/compiler/{slug}.json for each scenario plus _manifest.json listing
{slug, scenario, kind}. 40 are valid, 5 are "clamp" (out-of-bounds numbers the
validator must clamp), 5 are "reject" (missing field or blocking V-rule). The
fixtures are the checked-in regression set; this generator documents how they were
authored and lets them be regenerated deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.compiler.fixture_adapter import slugify

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "compiler"

_INFL = [1.0, 2.5, 4.0, 6.5, -1.0]
_RATES = [(2.0, 5.0), (5.0, 2.0), (3.0, 3.0)]
_EQ_DRIFT = [6.0, 3.0, 8.0, -2.0]
_QUARTERS = [40, 24, 60, 16]
_VINTAGE = ["current", "historical_average", "custom"]


def _wid(i: int) -> str:
    return f"00000000-0000-4000-8000-{i:012d}"


def _regime_for(infl: float) -> str:
    if infl >= 4:
        return "stagflation"
    if infl < 0:
        return "deflation_boom"
    return "expansion"


def valid_world(i: int, scenario: str) -> dict[str, Any]:
    infl = _INFL[i % 5]
    rs, re = _RATES[i % 3]
    eq_drift = _EQ_DRIFT[i % 4]
    quarters = _QUARTERS[i % 4]
    vintage = _VINTAGE[i % 3]
    has_crisis = i % 4 == 0 and quarters >= 16

    fc: dict[str, Any] = {
        "policy_rate": {"start_pct": rs, "end_pct": re},
        "inflation": {
            "average_pct": infl,
            "peak_pct": infl + 2.0,
            "peak_quarter": min(6, quarters - 1),
        },
        "equity": {"drift_annual_pct": eq_drift, "vol_annual_pct": 18.0},
        "credit": {
            "hy_spread_start_bps": 400.0,
            "hy_spread_peak_bps": 700.0,
            "peak_quarter": min(8, quarters - 1),
        },
        "commodities": {"drift_annual_pct": 3.0},
        "correlation": {"equity_bond_regime": "inflation_conditional"},
    }
    if has_crisis:
        fc["crisis_windows"] = [{"start_quarter": 4, "length_quarters": 4, "severity": 0.6}]

    structural: dict[str, Any] = {"parameter_vintage": vintage}
    if vintage == "custom":
        structural["private_equity"] = {
            "entry_multiple_drift_annual_pct": -1.0,
            "leverage_turns": 5.0,
            "illiquidity_premium_annual_pct": 2.0,
        }

    return {
        "spec_version": "1.0.0",
        "world_id": _wid(i),
        "status": "draft",
        "provenance": {
            "created_at": "2026-07-24T00:00:00Z",
            "author": "sso:fixture",
            "source": {
                "kind": "compiler",
                "user_scenario_text": scenario,
                "compiler_model": "claude-sonnet-4-6",
                "compiler_prompt_version": "compile-world-v1.0",
            },
        },
        "narrative": {
            "language": "en",
            "title": f"Fixture {i}",
            "tagline": "A regression fixture world.",
            "summary": "A generated scenario for the compiler regression harness.",
            "lesson": "Fixtures keep the compile->validate->run loop honest.",
            "dispatches": [
                {"date": "2027", "headline": f"Fixture {i} dispatch one"},
                {"date": "2028", "headline": f"Fixture {i} dispatch two"},
                {"date": "2029", "headline": f"Fixture {i} dispatch three"},
            ],
        },
        "horizon": {"start": "2027-Q1", "quarters": quarters},
        "regimes": {
            "mode": "sequence",
            "sequence": [
                {"regime": _regime_for(infl), "from_quarter": 0, "to_quarter": quarters - 1}
            ],
        },
        "factor_conditions": fc,
        "structural": structural,
        "engine_defaults": {
            "generator_id": "toy-v0",
            "n_paths": 200,
            "base_seed": 1000 + i,
        },
        "extensions": {},
    }


def build() -> list[dict[str, str]]:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []

    # 40 valid
    for i in range(40):
        scenario = (
            f"Valid scenario {i:02d}: inflation regime {i % 5}, rates path {i % 3}, "
            f"vintage {_VINTAGE[i % 3]}."
        )
        manifest.append({"slug": slugify(scenario), "scenario": scenario, "kind": "valid"})
        _write(scenario, valid_world(i, scenario))

    # 5 clamp (out-of-bounds numbers the validator must clamp)
    clamp_specs = [
        ("policy_rate", "end_pct", 50.0),
        ("equity", "vol_annual_pct", 99.0),
        ("credit", "hy_spread_peak_bps", 5000.0),
        ("inflation", "average_pct", 40.0),
        ("commodities", "drift_annual_pct", 99.0),
    ]
    for j, (section, field, bad) in enumerate(clamp_specs):
        i = 100 + j
        scenario = f"Adversarial clamp {j}: {section}.{field} out of bounds."
        w = valid_world(i, scenario)
        w["factor_conditions"][section][field] = bad
        # a second out-of-bounds field to trigger the >3-clamp path on some
        w["factor_conditions"]["policy_rate"]["start_pct"] = 30.0
        manifest.append({"slug": slugify(scenario), "scenario": scenario, "kind": "clamp"})
        _write(scenario, w)

    # 5 reject (missing field or blocking V-rule)
    # r0: missing horizon (structural rejection)
    s = "Adversarial reject 0: missing horizon."
    w = valid_world(200, s)
    del w["horizon"]
    _write(s, w)
    manifest.append({"slug": slugify(s), "scenario": s, "kind": "reject"})

    # r1: missing engine_defaults.generator_id
    s = "Adversarial reject 1: missing generator_id."
    w = valid_world(201, s)
    del w["engine_defaults"]["generator_id"]
    _write(s, w)
    manifest.append({"slug": slugify(s), "scenario": s, "kind": "reject"})

    # r2: untiled sequence (blocking V10)
    s = "Adversarial reject 2: untiled regime sequence."
    w = valid_world(202, s)
    w["regimes"]["sequence"] = [
        {"regime": "expansion", "from_quarter": 0, "to_quarter": 5}
    ]  # leaves a gap to quarters-1
    _write(s, w)
    manifest.append({"slug": slugify(s), "scenario": s, "kind": "reject"})

    # r3: custom vintage without any sleeve (blocking V12)
    s = "Adversarial reject 3: custom vintage without sleeves."
    w = valid_world(203, s)
    w["structural"] = {"parameter_vintage": "custom"}
    _write(s, w)
    manifest.append({"slug": slugify(s), "scenario": s, "kind": "reject"})

    # r4: transition matrix with a non-stochastic row (blocking V11)
    s = "Adversarial reject 4: non-stochastic transition matrix."
    w = valid_world(204, s)
    w["regimes"] = {
        "mode": "transition_matrix",
        "transition_matrix": {
            "states": ["expansion", "recession"],
            "matrix": [[0.5, 0.5], [0.3, 0.3]],
            "initial_state": "expansion",
        },
    }
    _write(s, w)
    manifest.append({"slug": slugify(s), "scenario": s, "kind": "reject"})

    (OUT / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _write(scenario: str, world: dict[str, Any]) -> None:
    (OUT / f"{slugify(scenario)}.json").write_text(
        json.dumps(world, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    m = build()
    print(f"wrote {len(m)} fixtures to {OUT}")
