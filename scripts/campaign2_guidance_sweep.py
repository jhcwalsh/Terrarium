"""Campaign-2 B' sweep: guidance_scale vs the four acceptance statistics.

Run:  uv run python -u scripts/campaign2_guidance_sweep.py --created-at 2026-08-02

NON-CRITERION-BEARING measurement, no retraining: the promoted flow
checkpoint trained its null-conditioning branch (cond_dropout=0.2) but has
only ever sampled at guidance_scale=1.0. This sweep samples the SAME
checkpoint at guidance {1.0, 1.5, 2.0, 3.0} and scores each ensemble on
the four pre-stated acceptance statistics (campaign2-regime-fix-options
memo): long-inflation-era frequency (history 1.000), inflation
mean-reversion half-life (history 61.2), stagnant-decade frequency
(history ~0.00-0.05), equity drawdown median depth (history 0.069).
If a level recovers persistence, the campaign seal pre-states it; if none
does, the decided escalation to A' (residual parameterization) fires.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval.metrics.horizon import build_horizon_suite  # noqa: E402
from ah.eval.reference import compute_reference  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen import systems  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.splits import DataAccess  # noqa: E402

GUIDANCE_LEVELS = (1.0, 1.5, 2.0, 3.0)
TARGET_SUBSTRINGS = (
    "cpi.long_inflation_era",
    "cpi.mean_reversion_halflife",
    "lost_decade",
    "equity_mkt.drawdown_median_depth",
)
HISTORY_ANCHORS = {
    "long_inflation_era_frequency": 1.000,
    "inflation_half_life": 61.2,
    "stagnant_decade_frequency": "0.00-0.05",
    "equity_drawdown_median_depth": 0.069,
}
OUT_DIR = _REPO_ROOT / "experiments" / "campaign2-sweep"


def _patch_guidance(system, g: float) -> bool:
    """The live knob is FlowBlockSampler.guidance_scale — a plain float the
    sampler passes to flow_integrate on every call (flow.py:452); nfe_per_block
    doubles automatically when it != 1.0. The FlowConfig is frozen and is only
    the default; patching it would do nothing."""
    sampler = getattr(system, "_sampler", None)
    if sampler is not None and hasattr(sampler, "guidance_scale"):
        sampler.guidance_scale = float(g)
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-paths", type=int, default=512)
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--sample-seed", type=int, default=20260802)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()

    manifest = load_manifest()
    with Catalog(_REPO_ROOT / "data") as catalog:

        def reader(series_id: str) -> pd.DataFrame:
            try:
                return catalog.read_observations(CAMPAIGN_VINTAGE_ID, series_id)
            except Exception:
                return pd.DataFrame(
                    {"date": pd.Series([], dtype="datetime64[ns]"), "value": []}
                )

        access = DataAccess(reader)
        reference = compute_reference(access, manifest, vintage_id=CAMPAIGN_VINTAGE_ID, seed=20260802)

    suite = build_horizon_suite(manifest, reference)
    targets = [
        s for s in suite if any(sub in s.name for sub in TARGET_SUBSTRINGS)
    ]
    print(f"target metrics ({len(targets)}):", [s.name for s in targets])

    rows = []
    for g in GUIDANCE_LEVELS:
        t0 = time.time()
        system = systems.build("hier-flow-v1", seed_index=1)
        if not _patch_guidance(system, g):
            raise SystemExit("could not locate a FlowConfig to patch — refusing")
        ens = system.sample_months(args.months, args.n_paths, args.sample_seed)
        assemble_s = time.time() - t0
        row: dict[str, object] = {"guidance": g, "assemble_s": round(assemble_s, 1)}
        for spec in targets:
            try:
                row[spec.name] = float(spec.fn(ens))
            except Exception as exc:
                row[spec.name] = f"error: {type(exc).__name__}"
        rows.append(row)
        print(f"guidance {g}: {row}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "non_criterion_bearing": True,
        "purpose": "B' sweep: guidance vs the four acceptance statistics",
        "checkpoint": "promoted flow seed_index 1 (cond_dropout 0.2, trained null branch)",
        "history_anchors": HISTORY_ANCHORS,
        "n_paths": args.n_paths,
        "months": args.months,
        "sample_seed": args.sample_seed,
        "created_at": args.created_at,
        "rows": rows,
    }
    (OUT_DIR / "sweep-results.json").write_text(
        json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"SWEEP DONE -> {OUT_DIR / 'sweep-results.json'}")


if __name__ == "__main__":
    main()
