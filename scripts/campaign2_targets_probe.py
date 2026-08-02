"""Campaign-2 diagnosis probe: score the L1-IMPLIED TARGET CURVES themselves.

Run:  uv run python -u scripts/campaign2_targets_probe.py

The A' result (residual parameterization moved none of the four acceptance
statistics) implies the generated paths already track the L1-implied targets.
This probe removes L3 entirely: it simulates L1+L2 exactly as ensemble assembly
does (same seed structure, same defaults), builds each decade's monthly target
curves, and scores the era statistic ON THE TARGETS. If the targets themselves
score ~0.4, the persistence gap lives in the upstream simulation (or in the
anchor's comparability), not in the block generator. NON-CRITERION-BEARING.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import numpy as np  # noqa: E402

from ah.eval.reference import long_inflation_era_frequency  # noqa: E402
from ah.gen.bootstrap import campaign_source  # noqa: E402
from ah.gen.climate.simulate import load_artifact as load_climate  # noqa: E402
from ah.gen.climate.simulate import simulate_decades  # noqa: E402
from ah.gen.joinery import waypoints as wp  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    DEFAULT_CLIMATE_ARTIFACT,
    DEFAULT_REGIMES_ARTIFACT,
    LAYER_SEED_OFFSETS,
    SEED_STRIDE,
)
from ah.gen.regimes.semimarkov import load_artifact as load_regimes  # noqa: E402
from ah.gen.regimes.semimarkov import simulate_regimes  # noqa: E402

N_DECADES = 512
MONTHS = 120
BASE_SEED = 20260802  # the acceptance runs' sampling seed


def main() -> None:
    historical_starts = "--historical-starts" in sys.argv
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    source = campaign_source()
    stats = wp.source_stats(source, climate)

    # Mechanism test: instead of every decade launching from the artifact's
    # last fitted month (the production default — the 2020-12 posterior state),
    # draw each decade's s0 from a RANDOM fitted month, approximating the
    # unconditional state distribution the history anchors implicitly pool over.
    s0_dates = [None] * N_DECADES
    if historical_starts:
        date_rng = np.random.Generator(np.random.PCG64(BASE_SEED + 555))
        picks = date_rng.integers(0, len(climate.dates), size=N_DECADES)
        s0_dates = [climate.dates[int(i)] for i in picks]

    era = np.zeros(N_DECADES)
    pi_star_max = np.zeros(N_DECADES)
    pi_star_mean = np.zeros(N_DECADES)
    yoy_max_run = np.zeros(N_DECADES, dtype=np.int64)
    eq_decade_log = np.zeros(N_DECADES)
    pi_names = None
    for m in range(N_DECADES):
        l1_seed = BASE_SEED + LAYER_SEED_OFFSETS["climate"] + SEED_STRIDE * m
        l2_seed = BASE_SEED + LAYER_SEED_OFFSETS["regimes"] + SEED_STRIDE * m
        sim = simulate_decades(climate, 1, seed=l1_seed, months=MONTHS, s0_date=s0_dates[m])
        regime_paths = simulate_regimes(regimes_artifact, sim.states, seed=l2_seed)
        waypoints = wp.build_waypoints(sim, regime_paths, stats)[0]
        targets = wp.monthly_targets(waypoints, MONTHS)

        cpi_level = 100.0 * np.exp(targets.log_cpi)
        era[m] = long_inflation_era_frequency(cpi_level)
        yoy = (cpi_level[12:] / cpi_level[:-12] - 1.0) * 100.0
        above = yoy >= 4.0
        run = best = 0
        for a in above:
            run = run + 1 if a else 0
            best = max(best, run)
        yoy_max_run[m] = best
        if pi_names is None:
            pi_names = list(sim.state_names) if hasattr(sim, "state_names") else None
        pi_col = pi_names.index("pi_star") if pi_names else 0
        pi = sim.states[0][:, pi_col]
        pi_star_max[m] = float(pi.max())
        pi_star_mean[m] = float(pi.mean())
        eq_decade_log[m] = float(targets.equity_cum_log[-1] - targets.equity_cum_log[0])
        if (m + 1) % 128 == 0:
            print(f"{m + 1}/{N_DECADES} decades", flush=True)

    record = {
        "non_criterion_bearing": True,
        "purpose": "score the L1-implied target curves themselves (no L3 anywhere)",
        "s0": "random fitted months" if historical_starts else "last fitted month (production)",
        "n_decades": N_DECADES,
        "months": MONTHS,
        "base_seed": BASE_SEED,
        "targets_long_inflation_era_frequency": float(np.mean(era)),
        "acceptance_run_value_for_comparison": 0.410,
        "history_anchor": 1.000,
        "yoy_ge_4pct_max_run_months": {
            "p50": float(np.percentile(yoy_max_run, 50)),
            "p90": float(np.percentile(yoy_max_run, 90)),
            "ge_24m_fraction": float(np.mean(yoy_max_run >= 24)),
        },
        "pi_star_pct": {
            "mean_of_decade_means": float(np.mean(pi_star_mean)),
            "p50_decade_max": float(np.percentile(pi_star_max, 50)),
            "p90_decade_max": float(np.percentile(pi_star_max, 90)),
        },
        "equity_decade_log_return": {
            "p10": float(np.percentile(eq_decade_log, 10)),
            "p50": float(np.percentile(eq_decade_log, 50)),
            "negative_fraction": float(np.mean(eq_decade_log < 0.0)),
        },
    }
    name = "targets-probe-historical-starts.json" if historical_starts else "targets-probe.json"
    out = _REPO_ROOT / "artifacts" / "campaign2" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(record, indent=1), flush=True)
    print(f"TARGETS PROBE DONE -> {out}", flush=True)


if __name__ == "__main__":
    main()
