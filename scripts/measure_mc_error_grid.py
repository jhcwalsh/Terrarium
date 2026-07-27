"""Measure the ensemble-size / Monte-Carlo-error grid that ``ensemble_size`` is sealed on.

This is the PROVENANCE SCRIPT for ``pre-registration.yaml``'s
``ensemble_size.mc_error_grid``. STEP2-GENERATOR-PLAN Sec.WP2.2's sizing rule is "MC
error << band width", and ``ensemble_size.n_paths`` is the number at which that holds
with margin. Before the WP2.3 re-seal the grid lived in the UNSEALED
``governance/decision-register.md`` -- editable with no amendment and no lock violation,
which is exactly the wrong home for the evidence a sealed value rests on. It now lives
inside the sealed document, and this script is how a reader reproduces it.

WHAT IS MEASURED. A ``bootstrap-v1``-shaped prototype (the sealed stationary form at the
sealed ``mean_block_months``, drawn from the sealed ``block_draw_span``) is generated at
each candidate ``n_paths``, and for each representative metric the batch-means
Monte-Carlo standard error is computed with the battery's own
``ah.eval.battery.mc_error`` -- the same estimator the battery records on every report,
not a private reimplementation.

ONLY BAND-JUDGED PER-NAME STATISTICS ARE MEASURED, and the omission is deliberate. The
scale that matters for such a statistic is its acceptance band's own width, so the
reported ratio is ``mc_error / (band.hi - band.lo)``: a ratio of 0.04 means the
Monte-Carlo noise is 4% of the interval the value is judged against.

THE THREE ``*_band_exceedance_fraction`` GATES ARE NOT MEASURED HERE. The sealed file
states, in ``limitations.band_exceedance_gate_mc_error_is_not_trustworthy_for_sizing``
(governance/retrofit-register.md RFR-44), that the batch-means estimator is *not* an
estimate of the right quantity for them: a gate is a fraction over a FIXED family of
comparisons, and subsampling paths changes the metric values the fraction is computed
from, so the subsample estimate is not an estimate of the same quantity at full path
count. Putting a gate column in a table whose whole purpose is to size the ensemble
would seal a number the same document says must not be used for sizing. The first seal's
grid carried such a column; this one does not, and says why. The sizing decision rests
entirely on the rows below.

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/measure_mc_error_grid.py --out mc-error-grid.json

Determinism: every draw flows from ``--seed`` through ``numpy.random.Generator(PCG64)``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compute_campaign_reference import (  # noqa: E402
    BLOCK_LENGTH,
    CAMPAIGN_VINTAGE_ID,
    LEVEL,
    N_RESAMPLES,
    REFERENCE_SEED,
    RESAMPLE_LENGTH,
    catalog_access,
)
from measure_block_length_window import (  # noqa: E402
    SEED_STRIDE,
    draw_span,
    stationary_bootstrap,
)

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval.battery import band_is_usable, mc_error  # noqa: E402
from ah.eval.metrics.monthly import build_monthly_suite  # noqa: E402
from ah.eval.panel import build_panel  # noqa: E402
from ah.eval.reference import compute_reference  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen.base import Ensemble, EnsembleMeta  # noqa: E402

# The candidate ensemble sizes. Powers of two, because that is what the grid is
# actually measured at and the sealed `n_paths` must be a size that was MEASURED rather
# than a round number interpolated between two that were.
N_PATHS_GRID = (64, 256, 1024)

# The sealed generator spec the prototype is drawn at.
MEAN_BLOCK_MONTHS = 6
MONTHS = 120
N_SUBSAMPLES = 20  # ah.eval.battery's own default for mc_error

# Representative per-name statistics: one location/shape statistic, two tail statistics,
# two dependence statistics -- chosen to span the band widths in the file, INCLUDING the
# tightest one in it (`ust_10y.acf_r_lag1`), which is what the sizing decision turns on.
BAND_JUDGED_METRICS = (
    "equity_mkt.skew",
    "equity_mkt.excess_kurtosis",
    "equity_mkt.acf_abs_sum",
    "equity_mkt.hill_tail_index_5pct",
    "ust_10y.acf_r_lag1",
)
# Deliberately NOT measured: the three `*_band_exceedance_fraction` gates. See the
# module docstring -- the batch-means estimator does not estimate the right quantity for
# them, and the sealed file says so in
# `limitations.band_exceedance_gate_mc_error_is_not_trustworthy_for_sizing`.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--seed", type=int, default=REFERENCE_SEED)
    parser.add_argument("--mean-block", type=int, default=MEAN_BLOCK_MONTHS)
    args = parser.parse_args()

    manifest = load_manifest()
    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        reference = compute_reference(
            access,
            manifest,
            vintage_id=args.vintage,
            seed=args.seed,
            n_resamples=N_RESAMPLES,
            level=LEVEL,
            block_length=BLOCK_LENGTH,
            resample_length=RESAMPLE_LENGTH,
        )
        panel = build_panel(access, manifest)

    factors = sorted(f for f in manifest.active_factors() if f not in reference.missing_factors)
    span, span_meta = draw_span(panel.frame, factors)
    source = span[factors].to_numpy(dtype=np.float64)
    print(f"factor_set ({len(factors)}): {factors}")
    print(f"block_draw_span: {span_meta}")

    specs = {s.name: s for s in build_monthly_suite(manifest, reference)}

    band_widths: dict[str, float] = {}
    for name in BAND_JUDGED_METRICS:
        band = None
        for block_ref in reference.blocks.values():
            if name in block_ref.stats:
                band = block_ref.stats[name]
                break
        if band is None or not band_is_usable(band):
            raise SystemExit(f"{name}: no usable reference band")
        band_widths[name] = float(band.hi - band.lo)

    results: dict[str, Any] = {}
    for n_paths in N_PATHS_GRID:
        paths = stationary_bootstrap(
            source, n_paths=n_paths, months=MONTHS, mean_block=args.mean_block, seed=args.seed
        )
        ensemble = Ensemble(
            paths=paths,
            factor_names=list(factors),
            meta=EnsembleMeta(
                generator_id="bootstrap-v1-prototype",
                vintage_id=args.vintage,
                seed=args.seed,
                n_paths=n_paths,
                months=MONTHS,
                active_blocks=manifest.active_blocks,
            ),
        )
        row: dict[str, Any] = {}
        for name in BAND_JUDGED_METRICS:
            spec = specs[name]
            err = mc_error(
                spec.fn, ensemble, seed=args.seed + SEED_STRIDE, n_subsamples=N_SUBSAMPLES
            )
            scale = band_widths[name]
            row[name] = {
                "value": float(spec.fn(ensemble)),
                "mc_error": float(err),
                "band_width": scale,
                "ratio": float(err / scale),
            }
        results[str(n_paths)] = row
        print(
            f"  n_paths={n_paths:>5}: "
            + ", ".join(f"{n}={row[n]['ratio']:.4f}" for n in BAND_JUDGED_METRICS)
        )

    payload = {
        "vintage_id": args.vintage,
        "seed": args.seed,
        "mean_block_months": args.mean_block,
        "months": MONTHS,
        "n_subsamples": N_SUBSAMPLES,
        "factor_set": factors,
        "block_draw_span": span_meta,
        "band_widths": band_widths,
        "results": results,
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
