"""WP5.7 (executing WP5.1's final clause): the walk-forward run on real data,
with the frozen primary metric scored against the PROMOTED generator.

Run:  uv run python -u scripts/run_walkforward_final.py --created-at DATE

The harness is the sealed one (`ah.eval.walkforward`, G5-locked protocol,
AM-2026-08-02-005 folds); this script only feeds it: the campaign-vintage
panel resolved to the policy universe through the SEALED transform code path
(`ah.eval.metrics.tails._resolve_series` over a single-path historical
Ensemble -- the same sealed-private-helper reuse `measure_seal_evidence.py`
records, for the same reason: a re-derivation would measure a different
quantity), and the frozen primary `drawdown_surprise` scored per fold against
the promoted `hier-flow-v1` cone.

STATED LIMITS, in the artifact as in this docstring:
- `static_endowment_mix` is UNCOMPUTABLE (its commodities leg is the standing
  RFR-8 gap) -- reported as such, never faked. Five of six policies run.
- The generator cone is UNCONDITIONAL year-one windows of promoted decades:
  one cone for all folds. A per-fold conditional cone is the re-cone
  machinery's job and a different (harder) claim; this is the battery-
  consistent calibration read.
- MODEL-LEVEL LOOK-AHEAD: the promoted generator trained on 1990-2020 while
  the folds test 2011-2020, so the cone has seen the test years' data in
  fitting. The BENCHMARK policies see trailing data only. Stated plainly;
  a per-fold-retrained generator variant is named future work, not smuggled.
- The kickoff's deepest-pitfall caveat, verbatim: "a policy that wins in the
  ensemble has been tested against the policy AND the generator together --
  say so plainly."
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from run_ablation_grid import catalog_access  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval import walkforward as wf  # noqa: E402
from ah.eval.decision_metrics import drawdown_surprise  # noqa: E402
from ah.eval.metrics.tails import _resolve_series  # noqa: E402
from ah.eval.panel import read_factor_frames  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen.base import Ensemble, EnsembleMeta  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.strategies import load_derived_series  # noqa: E402

OUT_DIR = _REPO_ROOT / "artifacts" / "wp57"
CONE_SEED = 20260804
CONE_PATHS = 256

#: asset column -> the resolved series that carries it (factor or derived id)
UNIVERSE = {
    "equity": "equity_mkt",
    "bonds": "govt_tr_10y",
    "credit": "credit_xs_hy",
}
RUNNABLE_POLICIES = tuple(p for p in wf.BENCHMARK_POLICIES if p != "static_endowment_mix")

PITFALL_CAVEAT = (
    "a policy that wins in the ensemble has been tested against the policy "
    "AND the generator together -- say so plainly."
)


def _asset_returns() -> pd.DataFrame:
    manifest = load_manifest()
    derived = load_derived_series()
    with Catalog(_REPO_ROOT / "data") as catalog:
        access = catalog_access(catalog, CAMPAIGN_VINTAGE_ID)
        frames = read_factor_frames(access, manifest)

    def single_path(factor: str) -> tuple[pd.DatetimeIndex, Ensemble]:
        frame = frames.frames[factor].sort_values("date")
        idx = pd.DatetimeIndex(frame["date"])
        values = frame["value"].to_numpy(dtype=np.float64)[None, :, None]
        ens = Ensemble(
            paths=values,
            factor_names=[factor],
            meta=EnsembleMeta("historical-train-val", CAMPAIGN_VINTAGE_ID, 0, 1, len(idx)),
        )
        return idx, ens

    columns = {}
    for asset, series in UNIVERSE.items():
        factor = derived[series].source_factor if series in derived else series
        idx, ens = single_path(factor)
        returns = _resolve_series(ens, series, derived)[0]
        columns[asset] = pd.Series(returns, index=idx)
    return pd.DataFrame(columns).dropna()


def _generator_cone() -> tuple[np.ndarray, str | None]:
    """Year-one equity windows of the PROMOTED hier-flow-v1 (registry pin)."""
    from ah.gen import registry
    from ah.gen.blocks import flow as fl

    fl.DEFAULT_BLOCK_BATCH = 128
    fl.DEFAULT_SAMPLER_DEVICE = "cuda"
    system: Any = registry.resolve("hier-flow-v1")
    ens = system.sample_months(120, CONE_PATHS, CONE_SEED)
    eq = ens.factor("equity_mkt")  # (paths, 120)
    return np.asarray(eq[:, :12], dtype=np.float64), getattr(system, "checkpoint_hash", None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    returns = _asset_returns()
    print(
        f"universe: {list(returns.columns)}; "
        f"{returns.index[0]!s:.10}..{returns.index[-1]!s:.10} ({len(returns)} months)",
        flush=True,
    )

    t0 = time.time()
    result = wf.run_walkforward(returns, policies=RUNNABLE_POLICIES, base_seed=20260804)
    print(f"walk-forward: {len(result.fold_results)} fold-policy cells in {time.time() - t0:.1f}s")

    wealth = result.per_policy("terminal_log_wealth")
    drawdown = result.per_policy("max_drawdown")
    baseline = wealth["static_60_40"]
    stats_vs_6040 = {
        policy: wf.wilcoxon_with_effect(wealth[policy], baseline)
        for policy in RUNNABLE_POLICIES
        if policy != "static_60_40"
    }

    print("sampling the promoted generator cone...", flush=True)
    t0 = time.time()
    cone, checkpoint_hash = _generator_cone()
    print(f"cone: {cone.shape[0]} year-one windows in {time.time() - t0:.1f}s", flush=True)

    equity = returns["equity"]
    surprises = {}
    for fold in wf.folds():
        year = equity.loc[fold.test_start : fold.test_end].iloc[:-1]
        if len(year) == 0:
            continue
        surprises[fold.fold_id] = float(drawdown_surprise(year.to_numpy(), cone))
    surprise_values = np.array(list(surprises.values()))

    doc = {
        "kind": "walkforward-final",
        "created_at": args.created_at,
        "protocol_version": result.protocol_version,
        "vintage_id": CAMPAIGN_VINTAGE_ID,
        "universe": UNIVERSE,
        "policies_run": list(RUNNABLE_POLICIES),
        "uncomputable_policies": {
            "static_endowment_mix": "commodities leg unsourced (RFR-8); reported, not faked"
        },
        "per_policy": {
            p: {
                "terminal_log_wealth_by_fold": [round(float(v), 6) for v in wealth[p]],
                "max_drawdown_by_fold": [round(float(v), 6) for v in drawdown[p]],
                "mean_terminal_log_wealth": float(np.mean(wealth[p])),
            }
            for p in RUNNABLE_POLICIES
        },
        "wilcoxon_vs_static_60_40": stats_vs_6040,
        "drawdown_surprise": {
            "definition": "frozen primary; realized fold-year equity max drawdown minus cone p95",
            "cone": {
                "generator": "hier-flow-v1 (promoted campaign-2 pin)",
                "checkpoint_hash": checkpoint_hash,
                "n_paths": CONE_PATHS,
                "windows": "year-one months of unconditional decades",
                "seed": CONE_SEED,
            },
            "by_fold": {str(k): round(v, 6) for k, v in sorted(surprises.items())},
            "mean": float(surprise_values.mean()),
            "max": float(surprise_values.max()),
            "n_folds_reality_exceeded_warning": int(np.sum(surprise_values > 0)),
        },
        "stated_limits": {
            "model_level_look_ahead": (
                "the promoted generator trained on 1990-2020; folds test 2011-2020. "
                "The cone has seen the test years in fitting; benchmark policies see "
                "trailing data only. A per-fold-retrained generator variant is future "
                "work, named here."
            ),
            "pitfall_caveat_verbatim": PITFALL_CAVEAT,
        },
    }
    (OUT_DIR / "walkforward-final.json").write_text(
        json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(doc["drawdown_surprise"], indent=1)[:600])
    print(f"wrote {OUT_DIR / 'walkforward-final.json'}")


if __name__ == "__main__":
    main()
