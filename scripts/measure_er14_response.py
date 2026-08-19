"""ER-14 close-out: the post-fix measurement run (Task B2).

Re-uses ER-14's own probe verbatim (``docs/current/private-markets-and-inflation.md``
Sec.7) so the close-out's "after" table sits column-for-column against the
register's "before" table, and adds:

* the world-basis pair (``stagflation_1974`` vs ``goldilocks``) — Sec.4 of the
  design is honest only as a pair, not a single world's number;
* AT-13, the escalator-asymmetry disclosure: C1 explicitly defers escalator
  caps/floors, so this design inherits a SYMMETRIC escalator on infrastructure
  (and real estate) and overstates the deflation-side downside. Measured, not
  argued, by patching ``ah.core.engine.inflation_excess`` with a clipped
  wrapper (``np.maximum(x, 0.0)`` below the anchor) for the duration of one
  probe run — a MEASUREMENT AFFORDANCE, never a production flag. No shipped
  code gains a switch for this.

Deterministic, no network, ASCII stdout. Writes ``artifacts/er14/response.json``.

Usage:
  uv run python scripts/measure_er14_response.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np

import ah.core.engine as engine_mod
from ah.core.engine import ASSETS, run_ensemble, run_path
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.play import PRIVATE_ASSETS, START_TARGETS, simulate_play

_REPO_ROOT = Path(__file__).resolve().parents[1]
PRESETS = _REPO_ROOT / "src" / "ah" / "presets"
OUT_PATH = _REPO_ROOT / "artifacts" / "er14" / "response.json"

SEED = 12345
INFL_POINTS = (1.0, 2.0, 6.5, 12.0)


def _world(infl_pct: float, preset_doc: dict) -> Any:
    doc = copy.deepcopy(preset_doc)
    doc["factor_conditions"]["inflation"]["average_pct"] = infl_pct
    return project_numeric(load_worldspec(doc))


def _annualised(ens, asset: str) -> float:
    r = ens.returns[asset] / 100.0
    return float((np.prod(1 + r, axis=1).mean() ** (12 / r.shape[1]) - 1) * 100)


def measure_probe(preset_doc: dict) -> dict[str, dict[str, float]]:
    """Sec.4.3's probe, verbatim (stagflation preset, 200 paths, seed 12345,
    one field varied): annualised return by asset at each declared inflation."""
    probe: dict[str, dict[str, float]] = {a: {} for a in ASSETS}
    for infl in INFL_POINTS:
        ens = run_ensemble(_world(infl, preset_doc), 200, base_seed=SEED)
        for a in ASSETS:
            probe[a][f"{infl}"] = _annualised(ens, a)
    return probe


def measure_by_asset(probe: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for a, row in probe.items():
        lo, hi = row["1.0"], row["12.0"]
        out[a] = {"1pct": lo, "12pct": hi, "delta": hi - lo}
    return out


def measure_institution(preset_doc: dict) -> dict[str, Any]:
    """Sec.4.4's probe: the institution, with and without the commodity
    sleeve, at the same three inflation points."""
    targets_no_commod = dict(START_TARGETS)
    targets_no_commod["equity"] += targets_no_commod["commodities"]
    targets_no_commod["commodities"] = 0.0

    rows = []
    for infl in (1.0, 6.5, 12.0):
        tape = run_path(_world(infl, preset_doc), SEED)
        with_commod = simulate_play(tape, {}, start_targets=None)
        without_commod = simulate_play(tape, {}, start_targets=targets_no_commod)
        rows.append(
            {
                "infl_pct": infl,
                "final_nav": with_commod.final_value,
                "private_nav_with_commodities": sum(
                    with_commod.quarters[-1].private_true[a] for a in PRIVATE_ASSETS
                ),
                "private_nav_without_commodities": sum(
                    without_commod.quarters[-1].private_true[a] for a in PRIVATE_ASSETS
                ),
            }
        )
    return {"rows": rows}


def measure_world_basis_pair() -> dict[str, Any]:
    """Sec.4's own rule: a single world's number is not honest, a PAIR is.
    stagflation_1974 (the played, real-1970s-calibrated GENERATED world,
    generator_id bootstrap-v1) against goldilocks (the calm toy-v0 baseline)
    -- both AS AUTHORED, no field varied. The two run through different
    engines (run_gen_ensemble / run_ensemble), so the columns compared are
    exactly PM_SLEEVE_FOR_ASSET's four private assets, present on both."""
    from ah.port.adapter import run_gen_ensemble

    out: dict[str, Any] = {}

    doc_1974 = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    world_1974 = project_numeric(load_worldspec(doc_1974))
    ens_1974 = run_gen_ensemble(world_1974, 200, base_seed=SEED)
    out["stagflation_1974"] = {a: _annualised(ens_1974, a) for a in ens_1974.returns}

    doc_gold = json.loads((PRESETS / "goldilocks.json").read_text(encoding="utf-8"))
    world_gold = project_numeric(load_worldspec(doc_gold))
    ens_gold = run_ensemble(world_gold, 200, base_seed=SEED)
    out["goldilocks"] = {a: _annualised(ens_gold, a) for a in ASSETS}

    return out


def measure_at13(preset_doc: dict) -> dict[str, Any]:
    """AT-13: the escalator asymmetry, measured not argued. A DISCLOSURE with
    no threshold: the floored variant is computed by patching
    ``inflation_excess`` for the duration of one probe run, never a shipped
    switch."""
    original = engine_mod.inflation_excess

    def _floored(
        inflation, *, k=engine_mod.INFLATION_TRAIL_MONTHS, anchor=engine_mod.INFLATION_ANCHOR_PCT
    ):
        return np.maximum(original(inflation, k=k, anchor=anchor), 0.0)

    symmetric_infra = _annualised(
        run_ensemble(_world(1.0, preset_doc), 200, base_seed=SEED), "infra"
    )
    symmetric_re = _annualised(run_ensemble(_world(1.0, preset_doc), 200, base_seed=SEED), "re")

    engine_mod.inflation_excess = _floored
    try:
        floored_infra = _annualised(
            run_ensemble(_world(1.0, preset_doc), 200, base_seed=SEED), "infra"
        )
        floored_re = _annualised(run_ensemble(_world(1.0, preset_doc), 200, base_seed=SEED), "re")
    finally:
        engine_mod.inflation_excess = original

    return {
        "probe_infl_pct": 1.0,
        "symmetric_infra_pp": symmetric_infra,
        "floored_variant_infra_pp": floored_infra,
        "floored_variant_delta_pp": floored_infra - symmetric_infra,
        "symmetric_re_pp": symmetric_re,
        "floored_variant_re_pp": floored_re,
        "floored_variant_re_delta_pp": floored_re - symmetric_re,
        "note": (
            "C1 explicitly defers escalator caps/floors ('documented asymmetry, "
            "deferred'), so the shipped design inherits a SYMMETRIC escalator: "
            "leases/contracts fall as well as rise with inflation below the "
            "anchor. The floored variant removes the downside leg (a MEASUREMENT "
            "affordance patching inflation_excess for one probe run, never a "
            "production flag). The delta is how much of infra's/re's measured "
            "deflation-side response is this deferred asymmetry, not a fix."
        ),
    }


def main() -> None:
    base = json.loads((PRESETS / "stagflation.json").read_text(encoding="utf-8"))

    probe = measure_probe(base)
    by_asset = measure_by_asset(probe)
    institution = measure_institution(base)
    world_basis = measure_world_basis_pair()
    at13 = measure_at13(base)

    doc = {
        "probe": probe,
        "by_asset": by_asset,
        "institution": institution,
        "world_basis_pair": world_basis,
        "at13": at13,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"wrote {OUT_PATH}")
    print("by_asset (1pct -> 12pct -> delta, pp/yr):")
    for a in ("pe", "pc", "re", "infra"):
        row = by_asset[a]
        print(f"  {a:6s} {row['1pct']:+.3f} -> {row['12pct']:+.3f}  (delta {row['delta']:+.3f})")
    print(f"AT-13 floored_variant_delta_pp (infra): {at13['floored_variant_delta_pp']:+.3f}")


if __name__ == "__main__":
    main()
