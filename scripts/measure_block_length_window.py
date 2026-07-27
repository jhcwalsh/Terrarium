"""Measure the bootstrap-v1 mean-block-length window on the campaign vintage.

This is the PROVENANCE SCRIPT for ``pre-registration.yaml``'s
``bootstrap_v1.block_length_derivation`` and ``bootstrap_v1.moment_gate_risk_measured``.
The first seal quoted those numbers from an ad-hoc prototype that was never committed,
so the claim "mean block 6 sits in the middle of the window" could not be reproduced by
a reader. It can now: this script builds the sealed ``factor_set`` panel from the frozen
campaign vintage, draws a Politis-Romano stationary bootstrap exactly as
``bootstrap_v1.form_statement`` defines it, and evaluates the three gates that bound the
choice from either side.

The gates, and which side each bounds (see the sealed derivation for the argument):

- ``dependence_band_exceedance_fraction`` (enforce, max 0.5) bounds L from BELOW -- short
  blocks destroy serial dependence.
- ``nn_distance_p05`` bounds L from ABOVE and is the binding one: a stationary bootstrap
  emits a verbatim ``MEMORIZATION_BLOCK_MONTHS``-month window whenever no restart falls
  inside it, with probability ``(1 - 1/L)**(MEMORIZATION_BLOCK_MONTHS - 1)``, and the
  5th-percentile nearest-neighbour distance collapses to 0.0 once that rate passes 5%.
- ``near_duplicate_fraction`` (enforce, max 0.5) is reported because the derivation
  claims it is NOT binding; that claim has to be checkable.

``moment_band_exceedance_fraction`` is reported at every L for
``moment_gate_risk_measured``'s era-mixing risk.

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/measure_block_length_window.py --out block-length-window.json

Determinism: every draw flows from ``--seed`` through ``numpy.random.Generator(PCG64)``,
one derived seed per (L, replicate) via the platform's ``base + 7919*k`` rule.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.eval.battery import MetricSpec
from ah.eval.metrics.memorization import build_memorization_suite
from ah.eval.metrics.monthly import build_monthly_suite
from ah.eval.panel import build_panel
from ah.eval.reference import ReferenceStats, compute_reference
from ah.factors import load_manifest
from ah.gen.base import Ensemble, EnsembleMeta
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Must match `pre-registration.yaml`'s `reference_run:` block; the reference the gates
# are judged against is the SAME object the bands come from.
CAMPAIGN_VINTAGE_ID = "2026-07-26.1"
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120
RESAMPLE_LENGTH = 120

# The mean block lengths measured. Spans both bounds so the window's EDGES are observed
# rather than interpolated.
BLOCK_LENGTHS = (3, 4, 5, 6, 8, 10, 12, 18, 24)

# The gates that bound the choice, plus the era-mixing risk gate.
GATE_NAMES = (
    "dependence_band_exceedance_fraction",
    "moment_band_exceedance_fraction",
    "tail_band_exceedance_fraction",
    "near_duplicate_fraction",
    "nn_distance_p05",
    "nn_distance_p50",
)

SEED_STRIDE = 7919  # the platform's ensemble seed rule


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    """A :class:`DataAccess` pinned to one campaign vintage; missing series read empty."""

    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def stationary_bootstrap(
    source: np.ndarray, *, n_paths: int, months: int, mean_block: int, seed: int
) -> np.ndarray:
    """Politis-Romano stationary bootstrap over a MULTIVARIATE panel.

    ``source`` is ``(T, n_factors)``: one shared row index across all factors, never
    per-factor resampling, exactly as ``bootstrap_v1.block_draw_span_rule`` requires.
    Restart probability ``p = 1/mean_block``; the index WRAPS circularly, which is part
    of bootstrap-v1's sealed definition and not an implementation convenience.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    n_rows = source.shape[0]
    p = 1.0 / float(mean_block)

    starts = rng.integers(0, n_rows, size=(n_paths, months))
    restart = rng.random((n_paths, months)) < p
    restart[:, 0] = True

    index = np.empty((n_paths, months), dtype=np.int64)
    index[:, 0] = starts[:, 0]
    for t in range(1, months):
        advanced = (index[:, t - 1] + 1) % n_rows
        index[:, t] = np.where(restart[:, t], starts[:, t], advanced)
    return source[index]


def draw_span(panel: pd.DataFrame, factors: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The maximal span over which EVERY factor in ``factors`` is simultaneously observed."""
    sub = panel[["date", *factors]].dropna().reset_index(drop=True)
    meta = {
        "start": str(pd.Timestamp(sub["date"].iloc[0]).date()),
        "end": str(pd.Timestamp(sub["date"].iloc[-1]).date()),
        "months": len(sub),
        "binding_factors": sorted(
            f for f in factors if panel[["date", f]].dropna()["date"].iloc[0] == sub["date"].iloc[0]
        ),
    }
    return sub, meta


def _evaluate(specs: tuple[MetricSpec, ...], ensemble: Ensemble) -> dict[str, float]:
    out: dict[str, float] = {}
    for spec in specs:
        if spec.name in GATE_NAMES:
            out[spec.name] = float(spec.fn(ensemble))
    return out


def measure(
    reference: ReferenceStats,
    manifest: Any,
    source: np.ndarray,
    factors: list[str],
    *,
    n_paths: int,
    months: int,
    seeds: int,
    base_seed: int,
    vintage_id: str,
) -> dict[int, dict[str, Any]]:
    specs = (
        *build_monthly_suite(manifest, reference),
        *build_memorization_suite(manifest, reference),
    )
    results: dict[int, dict[str, Any]] = {}
    for mean_block in BLOCK_LENGTHS:
        per_seed: list[dict[str, float]] = []
        for k in range(seeds):
            seed = base_seed + SEED_STRIDE * k
            paths = stationary_bootstrap(
                source, n_paths=n_paths, months=months, mean_block=mean_block, seed=seed
            )
            ensemble = Ensemble(
                paths=paths,
                factor_names=list(factors),
                meta=EnsembleMeta(
                    generator_id="bootstrap-v1-prototype",
                    vintage_id=vintage_id,
                    seed=seed,
                    n_paths=n_paths,
                    months=months,
                    active_blocks=manifest.active_blocks,
                ),
            )
            per_seed.append(_evaluate(specs, ensemble))
        summary: dict[str, Any] = {
            "verbatim_window_probability": float((1.0 - 1.0 / mean_block) ** 23),
            "per_seed": per_seed,
        }
        for name in GATE_NAMES:
            values = [s[name] for s in per_seed if name in s]
            if values:
                summary[name] = {
                    "mean": float(np.mean(values)),
                    "worst": float(np.max(values)),
                    "best": float(np.min(values)),
                }
        results[mean_block] = summary
        print(
            f"  L={mean_block:>2}: "
            + ", ".join(f"{n}={summary[n]['mean']:.4f}" for n in GATE_NAMES if n in summary)
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--seed", type=int, default=REFERENCE_SEED)
    parser.add_argument("--n-paths", type=int, default=200)
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--seeds", type=int, default=3)
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

    # factor_set = every active factor with train+validation data on this vintage.
    factors = sorted(f for f in manifest.active_factors() if f not in reference.missing_factors)
    span, span_meta = draw_span(panel.frame, factors)
    print(f"factor_set ({len(factors)}): {factors}")
    print(f"block_draw_span: {span_meta}")

    source = span[factors].to_numpy(dtype=np.float64)
    results = measure(
        reference,
        manifest,
        source,
        factors,
        n_paths=args.n_paths,
        months=args.months,
        seeds=args.seeds,
        base_seed=args.seed,
        vintage_id=args.vintage,
    )

    payload = {
        "vintage_id": args.vintage,
        "seed": args.seed,
        "n_paths": args.n_paths,
        "months": args.months,
        "seeds": args.seeds,
        "factor_set": factors,
        "block_draw_span": span_meta,
        "missing_factors": list(reference.missing_factors),
        "results": {str(k): v for k, v in results.items()},
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
