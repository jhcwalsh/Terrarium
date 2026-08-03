"""WP5.6: the one-shot holdout evaluation -- exactly the sealed spec, once.

The specification is `Instructions/holdout-evaluation-spec.md` (owner-approved,
sealed into the G5 lock by AM-2026-08-02-006 BEFORE the campaign promotion
seal existed). The spend was authorized by the owner's explicit word
("Go", 2026-08-03) after every other Step 5 metric run was final. This script
implements the recipe verbatim and nothing else:

    generate:  uv run python -u scripts/run_holdout_evaluation.py --phase generate
    score:     uv run python -u scripts/run_holdout_evaluation.py --phase score --created-at DATE

- GENERATE touches no holdout data: 1024 paths from the campaign-2 PROMOTED
  generator, horizon 67 months (2021-01..2026-07, the full holdout span),
  conditioned on the world as of 2021-01 from train+validation ONLY -- the
  L1 posterior state at the artifact's last fitted month (2020-12, the
  default s0) and the regime state at the boundary (the last train+val
  ruleset label, pinned via JoineryConfig.initial_regime). base_seed
  20260000, SINGLE DRAW. The ensemble is saved so the scoring phase never
  regenerates (no second draw, structurally).
- SCORE is the spend: the realized holdout read ONCE through the
  FinalEvaluationToken path, every series read logged in the artifact;
  primary drawdown_surprise; the three pre-stated secondaries as a table,
  no aggregation into a verdict number. THE SCRIPT REFUSES TO SCORE TWICE:
  an existing artifact is a hard stop, not an overwrite.

The result publishes verbatim in RESEARCH-EVIDENCE.md RQ2, whichever way it
falls, with the single-realization caveat and nothing else.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import numpy as np  # noqa: E402
from run_ablation_grid import catalog_access  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval.decision_metrics import drawdown_surprise, max_drawdown  # noqa: E402
from ah.eval.panel import read_factor_frames  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID, campaign_source  # noqa: E402
from ah.gen.regimes.semimarkov import REGIME_LABELS  # noqa: E402

ENSEMBLE_PATH = _REPO_ROOT / "experiments" / "wp56" / "holdout-ensemble.npz"
OUT_JSON = _REPO_ROOT / "artifacts" / "wp56" / "holdout-evaluation.json"
BASE_SEED = 20260000  # sealed: stated in the spec so no seed shopping is possible
N_PATHS = 1024  # sealed S2-ENSEMBLE-SIZE
HORIZON = 67  # 2021-01 .. 2026-07 inclusive, monthly
BAND = (5.0, 95.0)  # the sealed band level (0.9), coverage quantiles


def phase_generate() -> None:
    """The conditioned ensemble -- no holdout data anywhere in this phase."""
    from ah.gen.blocks import flow as fl
    from ah.gen.blocks.flow import FlowBlockSampler, HierFlowV1, load_checkpoint
    from ah.gen.climate.simulate import load_artifact as load_climate
    from ah.gen.joinery.assemble import (
        DEFAULT_CLIMATE_ARTIFACT,
        DEFAULT_REGIMES_ARTIFACT,
        PINNED_CLIMATE_SHA256,
        PINNED_REGIMES_SHA256,
        JoineryConfig,
    )
    from ah.gen.regimes.semimarkov import load_artifact as load_regimes

    if ENSEMBLE_PATH.exists():
        print(f"[skip] ensemble already generated at {ENSEMBLE_PATH} (single draw)")
        return

    source = campaign_source()
    boundary_label = str(source.labels[-1])  # the last train+val month's ruleset label
    initial_regime = REGIME_LABELS.index(boundary_label)
    print(f"boundary (2020-12) regime label: {boundary_label} (index {initial_regime})")

    model, std, meta = load_checkpoint(fl.DEFAULT_CHECKPOINT)
    if meta["checkpoint_hash"] != fl.PINNED_CHECKPOINT_SHA256:
        raise SystemExit("checkpoint != the promoted pin; refusing")
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact != WP2.7 pin")
    if regimes.meta["content_sha256"] != PINNED_REGIMES_SHA256:
        raise SystemExit("regimes artifact != WP2.7 pin")

    sampler = FlowBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device="cuda",
        block_batch=128,
    )
    # s0_date=None IS the 2021-01 boundary state (the artifact's last fitted
    # month is 2020-12); initial_regime pins the boundary's running label.
    config = JoineryConfig(initial_regime=initial_regime)
    system = HierFlowV1(climate, regimes, source, sampler, config)
    system.checkpoint_hash = meta["checkpoint_hash"]

    print(f"generating {N_PATHS} x {HORIZON} months, base_seed {BASE_SEED}...", flush=True)
    ens = system.sample_months(HORIZON, N_PATHS, BASE_SEED)
    ENSEMBLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        ENSEMBLE_PATH,
        paths=ens.paths,
        factor_names=np.array(list(ens.factor_names)),
        checkpoint_hash=np.array([meta["checkpoint_hash"]]),
        base_seed=np.array([BASE_SEED]),
        initial_regime=np.array([initial_regime]),
    )
    print(f"saved {ENSEMBLE_PATH} shape {ens.paths.shape}")


def _read_realized(split_reader) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Resolve every factor's realized series through ``split_reader``, per factor.

    Per-factor isolation: a factor whose resolution cannot work on a
    span-restricted read is recorded with its reason instead of crashing the
    spend. The one principled fallback: ``fx_usd``'s splice FITS on the
    2006-2019 overlap (invisible to a holdout-only reader), but the splice
    only extends BACKWARD of 2006 -- realized fx in any modern span IS
    ``fred.DTWEXBGS`` verbatim, so the fallback reads the series directly and
    says so in the log.
    """
    manifest = load_manifest()
    realized: dict[str, np.ndarray] = {}
    log: dict[str, str] = {}
    with Catalog(_REPO_ROOT / "data") as catalog:
        access = catalog_access(catalog, CAMPAIGN_VINTAGE_ID)
        for factor in manifest.active_factors():
            try:
                frames = read_factor_frames(
                    access, _single_factor_manifest(manifest, factor), split_reader=split_reader
                )
                if factor in frames.frames:
                    fr = frames.frames[factor].sort_values("date")
                    realized[factor] = fr["value"].to_numpy(dtype=np.float64)[:HORIZON]
                    log[factor] = "manifest resolution"
                else:
                    log[factor] = "no data in span"
            except Exception as exc:
                if factor == "fx_usd":
                    fr = split_reader(access, "fred.DTWEXBGS").sort_values("date")
                    if len(fr):
                        realized[factor] = fr["value"].to_numpy(dtype=np.float64)[:HORIZON]
                        log[factor] = (
                            "fred.DTWEXBGS actuals (splice fit window lies outside the "
                            "read span; the splice only extends pre-2006 history)"
                        )
                        continue
                log[factor] = f"unreadable in span: {type(exc).__name__}"
    return realized, log


def _single_factor_manifest(manifest, factor: str):
    """A one-active-factor view so per-factor isolation cannot be broken by a
    sibling's failure inside read_factor_frames."""
    from ah.factors import FactorManifest

    block = manifest.block_of(factor)
    return FactorManifest(
        blocks={block: (factor,)},
        active_blocks=(block,),
        sources={factor: manifest.sources[factor]},
    )


def phase_rehearse() -> None:
    """The IDENTICAL scoring code path against sanctioned validation-span data
    (no token, scratch output) -- run before the spend so the spend cannot
    crash after the token is minted. Touches no holdout data."""
    if not ENSEMBLE_PATH.exists():
        raise SystemExit("generate phase has not run")

    def validation_reader(a, series_id: str):
        return a.frame(series_id, "validation")

    realized, log = _read_realized(validation_reader)
    saved = np.load(ENSEMBLE_PATH, allow_pickle=False)
    paths = saved["paths"]
    factor_names = [str(x) for x in saved["factor_names"]]
    table = _score_table(paths, factor_names, realized)
    print(json.dumps({"read_log": log, "primary": table["primary_drawdown_surprise"]}, indent=1))
    print("REHEARSAL OK (validation-span stand-in; no token, nothing spent)")


def _score_table(paths, factor_names, realized) -> dict:
    eq_idx = factor_names.index("equity_mkt")
    eq_real = realized["equity_mkt"]
    eq_ens = paths[:, : len(eq_real), eq_idx]
    primary = float(drawdown_surprise(eq_real, eq_ens))
    realized_dd = float(max_drawdown(eq_real))
    p95_dd = float(np.percentile([max_drawdown(p) for p in eq_ens], 95.0))

    coverage = {}
    for f, r in sorted(realized.items()):
        if f not in factor_names or len(r) == 0:
            continue
        j = factor_names.index(f)
        ens = paths[:, : len(r), j]
        lo = np.percentile(ens, BAND[0], axis=0)
        hi = np.percentile(ens, BAND[1], axis=0)
        coverage[f] = {
            "months": len(r),
            "coverage_5_95": float(np.mean((r >= lo) & (r <= hi))),
        }

    real_terminal = float(np.prod(1.0 + eq_real))
    ens_terminal = np.prod(1.0 + eq_ens, axis=1)
    terminal_pct = float(np.mean(ens_terminal <= real_terminal))
    sign_of_mean_error = {
        f: int(np.sign(np.mean(r - paths[:, : len(r), factor_names.index(f)].mean(axis=0))))
        for f, r in sorted(realized.items())
        if f in factor_names and len(r)
    }
    return {
        "primary_drawdown_surprise": {
            "value": primary,
            "realized_max_drawdown": realized_dd,
            "ensemble_p95_drawdown": p95_dd,
            "reading": (
                "negative = reality stayed inside the p95 warning; "
                "positive = the world hurt more than warned"
            ),
        },
        "secondary_band_coverage_5_95": coverage,
        "secondary_terminal_wealth_percentile": terminal_pct,
        "secondary_sign_of_mean_error": sign_of_mean_error,
    }


def phase_score(created_at: str) -> None:
    """THE SPEND: one token, one read, one table. Refuses to run twice."""
    if OUT_JSON.exists():
        raise SystemExit(
            f"REFUSED: {OUT_JSON} already exists -- the holdout is spent once. "
            "There is no overwrite path by construction."
        )
    if not ENSEMBLE_PATH.exists():
        raise SystemExit("generate phase has not run; nothing to score against")

    saved = np.load(ENSEMBLE_PATH, allow_pickle=False)
    paths = saved["paths"]  # (1024, 67, F)
    factor_names = [str(x) for x in saved["factor_names"]]

    from ah.eval.g2 import final_evaluation_token

    token = final_evaluation_token()

    def holdout_reader(a, series_id: str):
        return a.frame(series_id, "holdout", token=token)

    realized, read_log = _read_realized(holdout_reader)
    table = _score_table(paths, factor_names, realized)

    doc = {
        "kind": "holdout-evaluation",
        "spec": "Instructions/holdout-evaluation-spec.md (sealed AM-2026-08-02-006)",
        "authorization": "owner, verbatim 'Go', 2026-08-03",
        "created_at": created_at,
        "token_purpose": token.purpose,
        "per_factor_read_log": read_log,
        "generator": {
            "id": "hier-flow-v1 (campaign-2 promoted pin)",
            "checkpoint_hash": str(saved["checkpoint_hash"][0]),
            "n_paths": int(paths.shape[0]),
            "horizon_months": int(paths.shape[1]),
            "base_seed": int(saved["base_seed"][0]),
            "boundary_initial_regime": REGIME_LABELS[int(saved["initial_regime"][0])],
        },
        **table,
        "single_realization_caveat": (
            "n=1 decade; whichever way any number falls, this is one realized "
            "path against a distribution -- confirmation or divergence, not proof"
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(doc["primary_drawdown_surprise"], indent=1))
    print(f"terminal wealth percentile: {doc['secondary_terminal_wealth_percentile']:.3f}")
    print(f"THE HOLDOUT IS SPENT -> {OUT_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("generate", "rehearse", "score"))
    parser.add_argument("--created-at", default=None)
    args = parser.parse_args()
    if args.phase == "generate":
        phase_generate()
    elif args.phase == "rehearse":
        phase_rehearse()
    else:
        if not args.created_at:
            raise SystemExit("--created-at is required for the scoring phase (the log)")
        phase_score(args.created_at)


if __name__ == "__main__":
    main()
