"""WP2.8 DIAGNOSIS (read-only): why the ig_spread Denton adjustment grew ~8x.

Measures, on the SAME waypoints, for both block samplers:

  * the signed year-end deviation of the raw (pre-reconciliation) ig_spread path
    from its waypoint band CENTER, and the band-EXIT rate;
  * the same split by year index (a drifting, unanchored level shows up as a
    deviation sd that grows with the year index) and by year-end regime;
  * the conditioning RESPONSE of the trained sampler: regime one-hot,
    h_spread_level_pct, dw_spread_center_pct and the credit-gap state are each
    swept with everything else and the sampling noise held fixed.

Also reports the historical (in-sample, caveated) band-exit rate of the real
1990-2020 spread against its own band.

SUPERSEDED IN PART BY WP2.7b. The committed
``artifacts/wp28/ig-spread-diagnosis.{json,md}`` were produced when the band
half-width was a single pooled ``sigma_resid``; WP2.7b made it regime-conditional,
so re-running this script no longer reproduces those files. The script now reads
the band from ``stats.spread_band_half_width_by_regime`` (i.e. it measures the
CURRENT band) and additionally reports the old pooled band alongside it. The
old-vs-new comparison proper lives in ``scripts/measure_spread_band.py``.

Nothing here writes to the repo, changes generator behaviour, or touches a
sealed judged source. Usage::

    uv run python -u scripts/diagnose_ig_spread.py --n-decades 256 \
        --block-batch 128 --device cuda
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.gen.blocks import constraints as ct  # noqa: E402
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


def describe(tag: str, dev: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> dict:
    """Signed deviation from centre + band-exit statistics."""
    center = (lo + hi) / 2.0
    excursion = np.maximum(0.0, np.maximum(dev - (hi - center), (lo - center) - dev))
    exits = excursion > 0
    above = (dev > (hi - center)) & exits
    out = {
        "tag": tag,
        "n": int(dev.size),
        "dev_mean": float(dev.mean()),
        "dev_sd": float(dev.std(ddof=1)),
        "dev_p10": q(dev, 0.10),
        "dev_p50": q(dev, 0.50),
        "dev_p90": q(dev, 0.90),
        "band_exit_rate": float(exits.mean()),
        "exit_above_share": float(above.sum() / max(1, exits.sum())),
        "mean_excursion": float(excursion.mean()),
        "mean_excursion_given_exit": float(excursion[exits].mean()) if exits.any() else 0.0,
        "mean_half_width": float((hi - center).mean()),
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-decades", type=int, default=256)
    ap.add_argument("--block-batch", type=int, default=128)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    import torch

    torch.use_deterministic_algorithms(True)

    print("loading source + artifacts...")
    source = campaign_source()
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    stats = wp.source_stats(source, climate)
    names = list(source.factor_names)
    scol = names.index("ig_spread")

    report: dict = {}

    # ------------------------------------------------------------------ #
    # A. the band's own constants + the historical (in-sample) exit rate
    # ------------------------------------------------------------------ #
    spread_hist = source.values[:, scol]
    codes = np.array([REGIME_LABELS.index(lab) for lab in source.labels])
    idx = climate.dates.get_indexer(source.dates)
    cg = climate.states.mean(axis=0)[idx, wp._STATE_CREDIT_GAP]
    center_hist = np.maximum(
        stats.spread_mean_by_regime[codes] + stats.spread_beta_credit_gap * cg,
        wp.SPREAD_FLOOR_PCT,
    )
    half_hist = stats.spread_band_half_width_by_regime[codes]  # WP2.7b: per regime
    lo_h = np.maximum(center_hist - half_hist, wp.SPREAD_FLOOR_PCT)
    hi_h = np.maximum(center_hist + half_hist, lo_h + 1e-9)

    report["band_constants"] = {
        "band_half_width_by_regime": {
            lab: float(v)
            for lab, v in zip(REGIME_LABELS, stats.spread_band_half_width_by_regime, strict=True)
        },
        "band_estimator": stats.spread_band_diagnostics,
        "spread_mean_by_regime": {
            lab: float(v) for lab, v in zip(REGIME_LABELS, stats.spread_mean_by_regime, strict=True)
        },
        "regime_month_counts": {
            lab: int((codes == i).sum()) for i, lab in enumerate(REGIME_LABELS)
        },
        "beta_credit_gap": float(stats.spread_beta_credit_gap),
        # the OLD (pre-WP2.7b) pooled half-width, kept for comparison only
        "pooled_resid_sd_superseded": float(stats.spread_resid_sd),
        "hist_spread_mean": float(spread_hist.mean()),
        "hist_spread_sd": float(spread_hist.std(ddof=1)),
        "hist_spread_acf1": float(np.corrcoef(spread_hist[:-1], spread_hist[1:])[0, 1]),
        "absent_regimes": list(stats.absent_regimes),
        "h0_spread_level": float(stats.h0_spread_level),
    }
    # every month, and calendar year-ends only (Dec of each panel year)
    dec = np.array([d.month == 12 for d in source.dates])
    report["historical_band"] = [
        describe("hist_all_months", spread_hist - center_hist, lo_h, hi_h),
        describe("hist_december", (spread_hist - center_hist)[dec], lo_h[dec], hi_h[dec]),
    ]
    print(json.dumps(report["band_constants"], indent=2))
    for row in report["historical_band"]:
        print(row)

    # ------------------------------------------------------------------ #
    # B. generation: same waypoints, two samplers
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
    for tag, sampler in (("diffusion", diff_sampler), ("bootstrap", boot_sampler)):
        print(f"\nassembling {args.n_decades} decades with {tag}...")
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
        devs, los, his, yidx, rlab, adjust = [], [], [], [], [], []
        raw_sd_within, raw_level = [], []
        for prep, (raw, _conds) in zip(preps, outputs, strict=True):
            w = prep.waypoints
            z = raw[:, scol]
            center = (w.spread_lo_pct + w.spread_hi_pct) / 2.0
            devs.append(z[yends] - center)
            los.append(w.spread_lo_pct)
            his.append(w.spread_hi_pct)
            yidx.append(np.arange(len(spans)))
            rlab.append(w.labels[yends])
            raw_sd_within.append(z.std(ddof=1))
            raw_level.append(z.mean())
            _, diag = rc.reconcile_decade(raw, tuple(names), w, config.reconcile)
            adjust.append(float(diag.factors["ig_spread"].adjustment_by_year.mean()))
        dev = np.concatenate(devs)
        lo = np.concatenate(los)
        hi = np.concatenate(his)
        yi = np.concatenate(yidx)
        rl = np.concatenate(rlab)
        adj = np.array(adjust)
        rows = [describe(f"{tag}_all_yearends", dev, lo, hi)]
        rows += [
            describe(f"{tag}_year{y}", dev[yi == y], lo[yi == y], hi[yi == y])
            for y in range(len(spans))
        ]
        rows += [
            describe(f"{tag}_regime_{lab}", dev[rl == i], lo[rl == i], hi[rl == i])
            for i, lab in enumerate(REGIME_LABELS)
            if (rl == i).any()
        ]
        per_sampler[tag] = {
            "recon_adjustment_p50": q(adj, 0.50),
            "recon_adjustment_p90": q(adj, 0.90),
            "recon_adjustment_max": float(adj.max()),
            "raw_path_level_mean": float(np.mean(raw_level)),
            "raw_within_decade_sd_mean": float(np.mean(raw_sd_within)),
            "rows": rows,
        }
        print(f"  recon p50 {q(adj, 0.50):.5f}  p90 {q(adj, 0.90):.5f}")
        for r in rows[: 1 + len(spans)]:
            print("  ", r)
        for r in rows[1 + len(spans) :]:
            print("  ", r)
    report["generated"] = per_sampler

    # ------------------------------------------------------------------ #
    # B2. is the miss a CENTRE miss or dispersion? regress dev on the centre
    # ------------------------------------------------------------------ #
    decomp: dict = {}
    for tag in ("diffusion", "bootstrap"):
        rows = per_sampler[tag]["rows"]
        reg_rows = [r for r in rows if r["tag"].startswith(f"{tag}_regime_")]
        n_tot = sum(r["n"] for r in reg_rows)
        grand = sum(r["n"] * r["dev_mean"] for r in reg_rows) / n_tot
        between = sum(r["n"] * (r["dev_mean"] - grand) ** 2 for r in reg_rows) / n_tot
        within = sum(r["n"] * r["dev_sd"] ** 2 for r in reg_rows) / n_tot
        decomp[tag] = {
            "grand_dev_mean": grand,
            "between_regime_var": between,
            "within_regime_var": within,
            "between_share": between / (between + within),
            "within_regime_sd_rms": float(np.sqrt(within)),
            "mean_band_half_width": float(stats.spread_band_half_width_by_regime[codes].mean()),
        }
    report["variance_decomposition"] = decomp
    print("\nvariance decomposition of the year-end deviation:")
    print(json.dumps(decomp, indent=2))

    # ------------------------------------------------------------------ #
    # C. conditioning response of the trained sampler (H5)
    # ------------------------------------------------------------------ #
    print("\nconditioning sweeps (fixed noise, one component moved at a time)...")
    rng = np.random.Generator(np.random.PCG64(4242))
    n_probe = 256
    # a realistic base slate: historical training conditioning vectors
    from ah.gen.blocks.data import build_dataset

    ds = build_dataset(source, climate)
    base = ds.cond[rng.choice(ds.cond.shape[0], size=n_probe, replace=True)].copy()
    noise = rng.standard_normal((n_probe, bridge.BLOCK_MONTHS, len(names)))

    def mean_spread(vectors: np.ndarray) -> float:
        blocks = diff_sampler.sample_batch(vectors, noise)
        return float(blocks[:, :, scol].mean())

    # -- C0: all four Dw channels, model response vs the historical relation -- #
    pcol, ccol, ecol = names.index("policy_rate"), names.index("cpi"), names.index("equity_mkt")

    def block_features(blocks: np.ndarray) -> dict[str, np.ndarray]:
        """The four quantities the four Dw components are supposed to steer."""
        return {
            "policy_mean_pct": blocks[:, :, pcol].mean(axis=1),
            "cpi_within_block_log": np.log(blocks[:, -1, ccol] / blocks[:, 0, ccol]),
            "equity_cum_log": np.log1p(blocks[:, :, ecol]).sum(axis=1),
            "spread_mean_pct": blocks[:, :, scol].mean(axis=1),
            "spread_within_block_change": blocks[:, -1, scol] - blocks[:, 0, scol],
        }

    def ols(y: np.ndarray, x: np.ndarray) -> float:
        x = x - x.mean()
        return float(x @ (y - y.mean()) / (x @ x)) if float(x @ x) > 0 else float("nan")

    # historical relation: on the training blocks themselves
    hist_blocks = ct.panel_to_constrained(ds.x, ds.factor_names)
    # ds.x has cpi rebased to the block start, so panel_to_constrained gives a
    # cpi column that is the RELATIVE level (1.0 at month 0) -- exactly what the
    # cpi feature wants.
    hf = block_features(hist_blocks)
    hcond = ds.cond
    hist_slopes = {
        "dw_policy_rate_pct -> policy_mean_pct": ols(hf["policy_mean_pct"], hcond[:, 14]),
        "dw_log_cpi -> cpi_within_block_log": ols(hf["cpi_within_block_log"], hcond[:, 15]),
        "dw_equity_cum_log -> equity_cum_log": ols(hf["equity_cum_log"], hcond[:, 16]),
        "dw_spread_center_pct -> spread_within_block_change": ols(
            hf["spread_within_block_change"], hcond[:, 17]
        ),
        "dw_spread_center_pct -> spread_mean_pct": ols(hf["spread_mean_pct"], hcond[:, 17]),
        "h_spread_level_pct -> spread_mean_pct": ols(hf["spread_mean_pct"], hcond[:, 13]),
        "state_pi_star -> policy_mean_pct": ols(hf["policy_mean_pct"], hcond[:, 6]),
    }

    def model_slope(component: int, feature: str, lo: float, hi: float) -> float:
        vals, ys = [], []
        for val in (lo, hi):
            v = base.copy()
            v[:, component] = val
            ys.append(float(block_features(diff_sampler.sample_batch(v, noise))[feature].mean()))
            vals.append(val)
        return (ys[1] - ys[0]) / (vals[1] - vals[0])

    sd = {i: float(std.c_std[i - 6]) for i in (13, 14, 15, 16, 17, 6)}
    model_slopes = {
        "dw_policy_rate_pct -> policy_mean_pct": model_slope(14, "policy_mean_pct", -1.0, 1.0),
        "dw_log_cpi -> cpi_within_block_log": model_slope(15, "cpi_within_block_log", -0.02, 0.02),
        "dw_equity_cum_log -> equity_cum_log": model_slope(16, "equity_cum_log", -0.10, 0.10),
        "dw_spread_center_pct -> spread_within_block_change": model_slope(
            17, "spread_within_block_change", -0.5, 0.5
        ),
        "dw_spread_center_pct -> spread_mean_pct": model_slope(17, "spread_mean_pct", -0.5, 0.5),
        "h_spread_level_pct -> spread_mean_pct": model_slope(13, "spread_mean_pct", 0.5, 1.5),
        "state_pi_star -> policy_mean_pct": model_slope(6, "policy_mean_pct", 0.0, 4.0),
    }
    report["channel_slopes"] = {
        "historical_ols_on_training_blocks": hist_slopes,
        "model_finite_difference": model_slopes,
        "c_std_by_component": sd,
    }
    print("\nchannel slopes (historical OLS vs model finite-difference):")
    for k in hist_slopes:
        print(f"  {k:52s} hist {hist_slopes[k]:+.4f}   model {model_slopes[k]:+.4f}")

    sweeps: dict = {}
    # C1 regime one-hot
    regime_resp = {}
    for i, lab in enumerate(REGIME_LABELS):
        v = base.copy()
        v[:, 0:6] = 0.0
        v[:, i] = 1.0
        regime_resp[lab] = mean_spread(v)
    sweeps["regime_onehot"] = {
        "generated_mean_spread": regime_resp,
        "band_center_by_regime": {
            lab: float(x) for lab, x in zip(REGIME_LABELS, stats.spread_mean_by_regime, strict=True)
        },
    }
    # C2 h_spread_level_pct (index 13)
    h_levels = [0.5, 0.8, 1.0, 1.3, 1.8, 2.5]
    sweeps["h_spread_level_pct"] = {}
    for val in h_levels:
        v = base.copy()
        v[:, 13] = val
        sweeps["h_spread_level_pct"][str(val)] = mean_spread(v)
    # C3 dw_spread_center_pct (index 17)
    dw_vals = [-1.0, -0.5, -0.2, 0.0, 0.2, 0.5, 1.0]
    sweeps["dw_spread_center_pct"] = {}
    for val in dw_vals:
        v = base.copy()
        v[:, 17] = val
        sweeps["dw_spread_center_pct"][str(val)] = mean_spread(v)
    # C4 credit_gap state (index 6 + 4 = 10) for scale reference
    cg_vals = [-2.0, -1.0, 0.0, 1.0, 2.0]
    sweeps["state_credit_gap"] = {}
    for val in cg_vals:
        v = base.copy()
        v[:, 10] = val
        sweeps["state_credit_gap"][str(val)] = mean_spread(v)
    # C5 what the standardization does to each swept component
    sweeps["c_std_at_components"] = {
        "h_spread_level_pct": float(std.c_std[13 - 6]),
        "dw_spread_center_pct": float(std.c_std[17 - 6]),
        "state_credit_gap": float(std.c_std[10 - 6]),
        "c_mean_h_spread_level_pct": float(std.c_mean[13 - 6]),
        "c_mean_dw_spread_center_pct": float(std.c_mean[17 - 6]),
    }
    report["sweeps"] = sweeps
    print(json.dumps(sweeps, indent=2))

    # ------------------------------------------------------------------ #
    # D. within-block vs across-block structure of the generated level
    # ------------------------------------------------------------------ #
    out_path = args.out or (_REPO_ROOT / "artifacts" / "wp28" / "ig-spread-diagnosis.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
