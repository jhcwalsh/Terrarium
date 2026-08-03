"""Compute the WP2.3 campaign reference statistics from the frozen campaign vintage.

This is the *provenance script* for every band sealed in ``pre-registration.yaml``.
Every ``min``/``max`` under ``thresholds:`` that is derived from history is derived
from ONE run of this script, whose parameters are themselves sealed in
``pre-registration.yaml``'s ``reference_run:`` block. Re-running it with those
parameters against the same vintage reproduces the same numbers bit-for-bit (the
bootstrap draw flows from a single integer seed through ``numpy.random.Generator``).

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/compute_campaign_reference.py --out reference-run.json

``data/`` is gitignored, so the JSON output is the auditable artifact a reader without
the catalog can check the sealed bands against. It is written wherever ``--out`` says
and is not itself committed (it is large); the sealed file records the run's digest
inputs -- vintage id, seed, ``n_resamples``, ``level``, ``block_length``,
``resample_length`` -- which is what makes the run identifiable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ah.data.catalog import Catalog
from ah.eval.reference import compute_reference
from ah.factors import load_manifest
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The sealed reference-run parameters. These MUST match `pre-registration.yaml`'s
# `reference_run:` block; `tests/test_prereg.py` asserts they do, so the script that
# produced the bands and the file that seals them cannot silently diverge.
# Campaign-2 (AM-2026-08-02-009): vintage moved with the reference_run block; the
# seed stays 20260726 so pre-existing factors' bands compare bit-for-bit (RFR-61).
CAMPAIGN_VINTAGE_ID = "2026-08-02.4"
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120
RESAMPLE_LENGTH = 120  # = the sealed ensemble path length (`ensemble_size.months`)


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    """A :class:`DataAccess` reading one pinned vintage out of the local catalog.

    Missing series return an EMPTY frame rather than raising: a series registered in
    ``requirements.yaml`` but absent from the frozen campaign vintage is a data gap
    (``ah.eval.panel`` records it in ``missing_no_data``), not a programming error, and
    WP2.3's whole point is that such a gap must be visible in the sealed file rather
    than crashing the run that would have revealed it.
    """

    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--seed", type=int, default=REFERENCE_SEED)
    parser.add_argument("--n-resamples", type=int, default=N_RESAMPLES)
    parser.add_argument("--level", type=float, default=LEVEL)
    parser.add_argument("--block-length", type=int, default=BLOCK_LENGTH)
    parser.add_argument("--resample-length", type=int, default=RESAMPLE_LENGTH)
    args = parser.parse_args()

    manifest = load_manifest()
    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        reference = compute_reference(
            access,
            manifest,
            vintage_id=args.vintage,
            seed=args.seed,
            n_resamples=args.n_resamples,
            level=args.level,
            block_length=args.block_length,
            resample_length=args.resample_length,
        )

    payload = reference.to_dict()
    payload["reference_run"] = {
        "vintage_id": args.vintage,
        "seed": args.seed,
        "n_resamples": args.n_resamples,
        "level": args.level,
        "block_length": args.block_length,
        "resample_length": args.resample_length,
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"missing_declared: {list(reference.missing_declared)}")
    print(f"missing_no_data:  {list(reference.missing_no_data)}")


if __name__ == "__main__":
    main()
