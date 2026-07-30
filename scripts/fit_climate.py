"""Fit the WP2.5 Layer-1 climate model on the real campaign panel (STEP2 Sec.WP2.5).

This is the PROVENANCE SCRIPT for the L1 posterior artifact: it reads the sealed
campaign vintage from the local catalog through the sanctioned split surface
(train+validation only, CAPE demean train-only), runs NUTS, and writes

- ``experiments/<exp_id>/climate-posterior.npz``  (hash-verified posterior artifact)
- ``experiments/<exp_id>/climate-fit-report.md``  (NUTS diagnostics + PPC + states)
- a repo-root copy of the report (``climate-fit-report.md``) for review

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/fit_climate.py --created-at 2026-07-26
    uv run python scripts/fit_climate.py --chains 4 --warmup 1000 --samples 1000

Determinism: NUTS is keyed by ``--seed`` (JAX PRNG), FFBS by seed+1, PPC noise by
seed+2 (numpy PCG64); the artifact records config hash, git SHA, seed, vintage.
The experiment id is derived from the config hash and seed, so re-running the
same configuration lands in the same experiment directory.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

# Parallel chains on CPU need the host device count set BEFORE jax initializes
# (numpyro does this via XLA_FLAGS; harmless when chain_method is sequential).
import numpyro  # noqa: E402

numpyro.set_host_device_count(4)

from ah.data.catalog import Catalog  # noqa: E402
from ah.experiment import config_hash  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.gen.climate import fit as cf  # noqa: E402
from ah.gen.climate import model as cm  # noqa: E402
from ah.gen.severe import SEVERE_TEST_EXCLUSION  # noqa: E402
from ah.splits import DataAccess  # noqa: E402


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    """A DataAccess over one pinned vintage; unknown series read as empty."""

    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260726)
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--catalog-root", default=str(_REPO_ROOT / "data"))
    parser.add_argument("--exp-root", default=str(_REPO_ROOT / "experiments"))
    parser.add_argument("--created-at", required=True, help="YYYY-MM-DD (recorded, not read)")
    parser.add_argument("--chains", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--config", default=None, help="alternate priors.yaml")
    parser.add_argument(
        "--severe-test",
        action="store_true",
        help=(
            "WP2.11 severe test: exclude the sealed 1970s span from the fitting sample by "
            "UNMASKING those months (grid and state path unchanged). Writes to a separate "
            "experiment directory and never touches the primary artifact."
        ),
    )
    args = parser.parse_args()

    exclude = SEVERE_TEST_EXCLUSION if args.severe_test else None

    config = cm.load_config(args.config)
    fit_updates = {}
    for field in ("chains", "warmup", "samples"):
        value = getattr(args, field)
        if value is not None:
            fit_updates[field] = value
    if fit_updates:
        config = config.model_copy(
            update={"fit": config.fit.model_copy(update=fit_updates)}, deep=True
        )

    cfg_hash = config_hash(cm.config_dict(config))
    # The exclusion is NOT folded into the config hash (the config -- priors, span,
    # fit settings -- is genuinely identical; only the DATA differ), so the severe
    # run is separated by an explicit id prefix instead. The artifact's own content
    # hash differs anyway, and meta records the exclusion.
    prefix = "climate-l1-severe" if exclude is not None else "climate-l1"
    exp_id = f"{prefix}-{cfg_hash.removeprefix('cfg:')[:12]}-s{args.seed}"
    out_dir = Path(args.exp_root) / exp_id

    if exclude is not None:
        print(f"[fit_climate] SEVERE TEST: excluding {exclude.label} from the fitting sample")
    print(f"[fit_climate] vintage {args.vintage}  config {cfg_hash}  seed {args.seed}")
    print(f"[fit_climate] exp dir: {out_dir}")
    print(
        f"[fit_climate] NUTS: {config.fit.chains} chain(s) x "
        f"{config.fit.warmup}+{config.fit.samples}"
    )

    catalog = Catalog(Path(args.catalog_root))
    try:
        access = catalog_access(catalog, args.vintage)
        t0 = time.perf_counter()
        result = cf.fit_climate(
            access,
            config,
            seed=args.seed,
            vintage_id=args.vintage,
            out_dir=out_dir,
            created_at=args.created_at,
            report_copy_path=(
                None if exclude is not None else _REPO_ROOT / "climate-fit-report.md"
            ),
            exclude=exclude,
        )
        elapsed = time.perf_counter() - t0
    finally:
        catalog.close()

    d = result.diagnostics
    print(f"[fit_climate] done in {elapsed / 60.0:.1f} min")
    print(
        f"[fit_climate] divergences={d['divergences']}  max_rhat={d['max_rhat']:.4f}  "
        f"min_ess={d['min_ess']:.0f}"
    )
    print(f"[fit_climate] artifact: {result.artifact_path}")
    copy_note = " (+ repo-root copy)" if exclude is None else " (no repo-root copy: severe run)"
    print(f"[fit_climate] report:   {result.report_path}{copy_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
