"""WP2.7b re-measurement: the ig_spread band, OLD (pooled) vs NEW (regime-conditional).

Read-only with respect to the repository except for its own artifact. Measures, for
the reference itself and for BOTH block samplers on the SAME waypoints and seeds:

  * band-exit rate and mean excursion, per regime, under both band definitions;
  * the Denton reconciliation-adjustment distribution under both band definitions.

The comparison is EXACT rather than approximate. The band enters the assembled
path only through the reconciliation target: the raw (pre-reconciliation) block
stream is conditioned on the band's CENTRE (``monthly_targets``), which WP2.7b
does not change. So one assembly per sampler serves both band definitions, and
any difference reported here is the band change and nothing else.

Usage (offline; local catalog + fitted artifacts + trained checkpoint)::

    uv run python -u scripts/measure_spread_band.py --n-decades 256 \
        --block-batch 128 --device cuda
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.gen.blocks import diffusion as df  # noqa: E402
from ah.gen.bootstrap import campaign_source  # noqa: E402
from ah.gen.climate.simulate import load_artifact as load_climate  # noqa: E402
from ah.gen.joinery import bridge  # noqa: E402
from ah.gen.joinery import reconcile as rc  # noqa: E402
from ah.gen.joinery import waypoints as wp  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    DEFAULT_CLIMATE_ARTIFACT,
    DEFAULT_REGIMES_ARTIFACT,
    JoineryConfig,
    _DecadeFactory,
)
from ah.gen.regimes.semimarkov import REGIME_LABELS  # noqa: E402
from ah.gen.regimes.semimarkov import load_artifact as load_regimes  # noqa: E402

SEED = 20260727
MONTHS = 120


def q(x: np.ndarray, p: float) -> float:
    return float(np.quantile(x, p))


def band_stats(dev: np.ndarray, half: np.ndarray) -> dict:
    """Exit statistics for deviations ``dev`` from the centre against half-widths."""
    excursion = np.maximum(0.0, np.abs(dev) - half)
    exits = excursion > 0
    return {
        "n": int(dev.size),
        "dev_mean": float(dev.mean()) if dev.size else 0.0,
        "dev_sd": float(dev.std(ddof=1)) if dev.size > 1 else 0.0,
        "band_exit_rate": float(exits.mean()) if dev.size else 0.0,
        "mean_excursion": float(excursion.mean()) if dev.size else 0.0,
        "mean_half_width": float(half.mean()) if dev.size else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-decades", type=int, default=256)
    ap.add_argument("--block-batch", type=int, default=128)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    import torch

    torch.use_deterministic_algorithms(True)

    print("loading source + artifacts ...", flush=True)
    source = campaign_source()
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    stats = wp.source_stats(source, climate)
    names = list(source.factor_names)
    scol = names.index("ig_spread")

    pooled = float(stats.spread_resid_sd)
    new_half = np.asarray(stats.spread_band_half_width_by_regime, dtype=np.float64)
    old_half = np.full_like(new_half, pooled)

    report: dict = {
        "seed": SEED,
        "n_decades": int(args.n_decades),
        "months": MONTHS,
        "block_batch": int(args.block_batch),
        "device": str(args.device),
        "vintage_id": source.vintage_id,
        "band": {
            "old_pooled_half_width": pooled,
            "new_half_width_by_regime": {
                lab: float(v) for lab, v in zip(REGIME_LABELS, new_half, strict=True)
            },
            "estimator": stats.spread_band_diagnostics,
        },
    }

    # ------------------------------------------------------------------ #
    # A. the REFERENCE against its own band (the honest standard)
    # ------------------------------------------------------------------ #
    spread_hist = source.values[:, scol]
    codes = np.array([REGIME_LABELS.index(lab) for lab in source.labels])
    idx = climate.dates.get_indexer(source.dates)
    cg = climate.states.mean(axis=0)[idx, wp._STATE_CREDIT_GAP]
    center_hist = np.maximum(
        stats.spread_mean_by_regime[codes] + stats.spread_beta_credit_gap * cg,
        wp.SPREAD_FLOOR_PCT,
    )
    dev_hist = spread_hist - center_hist
    dec = np.array([d.month == 12 for d in source.dates])
    hist: dict = {}
    for tag, half in (("old", old_half), ("new", new_half)):
        hist[tag] = {
            "all_months": band_stats(dev_hist, half[codes]),
            "december": band_stats(dev_hist[dec], half[codes][dec]),
            "by_regime": {
                lab: band_stats(dev_hist[codes == c], half[codes][codes == c])
                for c, lab in enumerate(REGIME_LABELS)
                if (codes == c).any()
            },
        }
    report["historical"] = hist
    print("\nHISTORICAL (train+validation, in-sample) band-exit rate")
    for tag in ("old", "new"):
        a = hist[tag]["all_months"]
        d = hist[tag]["december"]
        print(
            f"  {tag:3s} all months {a['band_exit_rate']:.3f} (excursion "
            f"{a['mean_excursion']:.4f})   Decembers {d['band_exit_rate']:.3f}"
        )
        print(
            "      by regime "
            + "  ".join(
                f"{lab}={hist[tag]['by_regime'][lab]['band_exit_rate']:.3f}"
                for lab in hist[tag]["by_regime"]
            )
        )

    # ------------------------------------------------------------------ #
    # B. both samplers, same waypoints, both bands
    # ------------------------------------------------------------------ #
    model, std, meta = df.load_checkpoint(df.DEFAULT_CHECKPOINT)
    diff_sampler = df.DiffusionBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device=args.device,
        block_batch=args.block_batch,
    )
    boot_sampler = bridge.BootstrapBlockSampler(source, block_months=bridge.BLOCK_MONTHS)
    config = JoineryConfig(acceptance_filter=False)
    spans = wp.year_spans(MONTHS)
    yends = np.array([s.stop - 1 for s in spans])

    per_sampler: dict[str, dict] = {}
    for tag, sampler in (("bootstrap", boot_sampler), ("diffusion", diff_sampler)):
        print(f"\nassembling {args.n_decades} decades with {tag} ...", flush=True)
        factory = _DecadeFactory(
            climate=climate,
            regimes_artifact=regimes_artifact,
            source=source,
            stats=stats,
            support_ref=None,  # type: ignore[arg-type]  # prepare() never reads it
            sampler=sampler,
            config=config,
            months=MONTHS,
            seed=SEED,
            world=None,
            guidance=None,
        )
        preps = [factory.prepare(m) for m in range(args.n_decades)]
        outputs = bridge.assemble_decade_paths(
            months=MONTHS,
            decades=[
                bridge.DecadeAssembly(
                    waypoints=p.waypoints, targets=p.targets, states_row=p.sim.states[0], rng=p.rng
                )
                for p in preps
            ],
            sampler=sampler,
            stats=stats,
            stride=config.block_stride,
        )
        devs, labs = [], []
        adjust: dict[str, dict[str, list[float]]] = {
            band: {name: [] for name in rc.VARIANT_BY_FACTOR} for band in ("old", "new")
        }
        for prep, (raw, _conds) in zip(preps, outputs, strict=True):
            w = prep.waypoints
            z = raw[:, scol]
            devs.append(z[yends] - w.spread_center_pct)
            labs.append(w.labels[yends])
            for band, half in (("old", old_half), ("new", new_half)):
                h = half[w.labels[yends]]
                lo = np.maximum(w.spread_center_pct - h, wp.SPREAD_FLOOR_PCT)
                hi = np.maximum(w.spread_center_pct + h, lo + 1e-9)
                banded = dataclasses.replace(w, spread_lo_pct=lo, spread_hi_pct=hi)
                _, diag = rc.reconcile_decade(raw, tuple(names), banded, config.reconcile)
                for name in rc.VARIANT_BY_FACTOR:
                    adjust[band][name].append(float(diag.factors[name].adjustment_by_year.mean()))
        dev = np.concatenate(devs)
        rl = np.concatenate(labs)

        entry: dict = {"n_yearends": int(dev.size)}
        for band, half in (("old", old_half), ("new", new_half)):
            entry[band] = {
                "all_yearends": band_stats(dev, half[rl]),
                "by_regime": {
                    lab: band_stats(dev[rl == c], half[rl][rl == c])
                    for c, lab in enumerate(REGIME_LABELS)
                    if (rl == c).any()
                },
                "reconciliation": {
                    name: {
                        "p50": q(np.array(v), 0.50),
                        "p90": q(np.array(v), 0.90),
                        "max": float(np.max(v)),
                    }
                    for name, v in adjust[band].items()
                },
            }
        entry["regime_share"] = {
            lab: float((rl == c).mean()) for c, lab in enumerate(REGIME_LABELS) if (rl == c).any()
        }
        per_sampler[tag] = entry

        print(f"  {tag}: year-end band exit rate")
        for band in ("old", "new"):
            a = entry[band]["all_yearends"]
            print(
                f"    {band:3s} all {a['band_exit_rate']:.3f}  excursion "
                f"{a['mean_excursion']:.4f}  ig_spread recon p50 "
                f"{entry[band]['reconciliation']['ig_spread']['p50']:.5f}  p90 "
                f"{entry[band]['reconciliation']['ig_spread']['p90']:.5f}"
            )
            print(
                "        by regime "
                + "  ".join(
                    f"{lab}={entry[band]['by_regime'][lab]['band_exit_rate']:.3f}"
                    for lab in entry[band]["by_regime"]
                )
            )
    report["generated"] = per_sampler

    out_path = args.out or (_REPO_ROOT / "artifacts" / "wp27b" / "spread-band-remeasurement.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
