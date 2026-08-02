"""Campaign-2 seed-0 PROBE (GPU) — timing + stability, NOT a promotion candidate.

Run:  uv run python -u scripts/campaign2_probe.py --device cuda --created-at <date>

NON-CRITERION-BEARING, by construction and by label: this trains one
hier-flow-v1 model on vintage 2026-08-02.4 with ONE data change — the
``hy_spread`` factor revived through the campaign-corrected
``hy_oas_pre1996`` splice (RFR-92), injected via a read-wrapper so no
sealed file is touched. What it measures: wall-clock per step, convergence
shape, and whether the +1-factor panel trains stably — calibration for the
real promotion runs, which happen only after the regime-persistence fix
and under the campaign seal. The FX factor is NOT here (needs the sealed
manifest's block_addition); the climate/regime layers ride the WP2.7 pins
unchanged, stated plainly.
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

from ah.data import derive  # noqa: E402
from ah.data import splice as sp  # noqa: E402
from ah.data.catalog import Catalog  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen.blocks import data as bd  # noqa: E402
from ah.gen.blocks.flow import FlowConfig  # noqa: E402
from ah.gen.blocks.train import train_blocks  # noqa: E402
from ah.gen.bootstrap import build_source  # noqa: E402
from ah.gen.climate.simulate import load_artifact as load_climate  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    DEFAULT_CLIMATE_ARTIFACT,
    PINNED_CLIMATE_SHA256,
)
from ah.gen.systems import train_seed_for  # noqa: E402
from ah.splits import DataAccess  # noqa: E402

PROBE_VINTAGE = "2026-08-02.4"
OUT_DIR = _REPO_ROOT / "experiments" / "campaign2-probe"


def spliced_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    """The probe's one intervention: reads of fred.HY_OAS return the
    campaign-corrected splice (1919-2026, is_proxy dropped to the panel's
    date/value shape). Everything else reads the vintage verbatim."""

    def base(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    hy = sp.splice(
        sp.PROXY_RULES["hy_oas_pre1996"],
        base("fred.HY_OAS"),
        derive.difference(base("fred.BAA"), base("fred.AAA")),
    ).frame[["date", "value"]]

    def reader(series_id: str) -> pd.DataFrame:
        if series_id == "fred.HY_OAS":
            return hy.copy()
        return base(series_id)

    return DataAccess(reader)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--max-steps", type=int, default=4000)
    parser.add_argument("--eval-every", type=int, default=250)
    parser.add_argument("--patience", type=int, default=8)
    args = parser.parse_args()

    manifest = load_manifest()
    with Catalog(_REPO_ROOT / "data") as catalog:
        access = spliced_access(catalog, PROBE_VINTAGE)
        source = build_source(access, manifest, vintage_id=PROBE_VINTAGE)
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact sha != WP2.7 pin; refusing")

    dataset = bd.build_dataset(source, climate)
    n_factors = dataset.blocks.shape[-1] if hasattr(dataset, "blocks") else "?"
    print(f"probe dataset: vintage {PROBE_VINTAGE}, factors dim = {n_factors}")

    config = FlowConfig()
    seed = train_seed_for("hier-flow-v1", 0)
    t0 = time.perf_counter()
    result = train_blocks(
        dataset,
        config,
        seed=seed,
        max_steps=args.max_steps,
        eval_every=args.eval_every,
        patience=args.patience,
        device=args.device,
        log=print,
    )
    wall = time.perf_counter() - t0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    steps = getattr(result, "steps_run", getattr(result, "steps", args.max_steps))
    record = {
        "non_criterion_bearing": True,
        "purpose": "campaign-2 seed-0 probe: timing + stability on the HY-revived panel",
        "vintage": PROBE_VINTAGE,
        "hy_spread": "revived via hy_oas_pre1996 (RFR-92 corrected overlap), read-wrapper injection",
        "fx": "absent (needs the campaign seal's block_addition)",
        "climate_regime_layers": "WP2.7 pins unchanged",
        "seed": seed,
        "max_steps": args.max_steps,
        "steps_run": int(steps) if isinstance(steps, (int, float)) else str(steps),
        "wall_clock_seconds": round(wall, 1),
        "best_score": getattr(result, "best_score", None),
        "created_at": args.created_at,
        "device": args.device,
    }
    (OUT_DIR / "probe-result.json").write_text(
        json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"PROBE DONE in {wall:.0f}s; record -> {OUT_DIR / 'probe-result.json'}")


if __name__ == "__main__":
    main()
