"""Fit the WP2.6 Layer-2 regime skeleton on the real campaign panel (STEP2 Sec.WP2.6).

This is the PROVENANCE SCRIPT for the L2 posterior artifact: it reads the sealed
campaign vintage from the local catalog through the sanctioned split surface
(train+validation only), loads the pinned WP2.5 climate artifact (content-hash
verified; its SHA-256 is recorded in the L2 artifact), runs NUTS on the
regime_ruleset_v1 labels, generates the acceptance-band evidence, refits under
the regime_ruleset_v1b sensitivity variant, and writes

- ``experiments/<exp_id>/regimes-posterior.npz``       (hash-verified artifact, v1)
- ``experiments/<exp_id>/regimes-posterior-v1b.npz``   (sensitivity refit)
- ``experiments/<exp_id>/regime-fit-report.md``        (+ repo-root copy)
- ``experiments/<exp_id>/regime-sensitivity-report.md`` (+ repo-root copy)

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/fit_regimes.py --created-at 2026-07-27
    uv run python scripts/fit_regimes.py --chains 4 --warmup 1000 --samples 1000

Determinism: NUTS is keyed by ``--seed`` (JAX PRNG; the v1b refit uses seed+1);
the acceptance bootstrap and simulation seeds live in the config and are hashed
with it. The experiment id derives from the config hash and seed, so re-running
the same configuration lands in the same experiment directory.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

# Parallel chains on CPU need the host device count set BEFORE jax initializes.
import numpyro  # noqa: E402

numpyro.set_host_device_count(4)

from ah.data.catalog import Catalog  # noqa: E402
from ah.experiment import config_hash  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.gen.climate.simulate import load_artifact as load_climate_artifact  # noqa: E402
from ah.gen.regimes import fit as rfit  # noqa: E402
from ah.gen.regimes import semimarkov as sm  # noqa: E402
from ah.gen.severe import SEVERE_TEST_EXCLUSION  # noqa: E402
from ah.splits import DataAccess  # noqa: E402

_DEFAULT_CLIMATE_ARTIFACT = (
    _REPO_ROOT / "experiments" / "climate-l1-f7d4119c7101-s20260726" / "climate-posterior.npz"
)


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
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--catalog-root", default=str(_REPO_ROOT / "data"))
    parser.add_argument("--exp-root", default=str(_REPO_ROOT / "experiments"))
    parser.add_argument("--created-at", required=True, help="YYYY-MM-DD (recorded, not read)")
    parser.add_argument("--climate-artifact", default=str(_DEFAULT_CLIMATE_ARTIFACT))
    parser.add_argument("--chains", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--config", default=None, help="alternate priors.yaml")
    parser.add_argument("--no-sensitivity", action="store_true")
    parser.add_argument("--no-acceptance", action="store_true")
    parser.add_argument(
        "--severe-test",
        action="store_true",
        help=(
            "WP2.11 severe test: exclude the sealed 1970s span from the fitting sample. "
            "The label history splits into observed segments; see "
            "ah.gen.regimes.fit.segmented_spell_observations for the straddling-spell rule. "
            "Writes to a separate experiment directory and never touches the primary artifact."
        ),
    )
    args = parser.parse_args()

    exclude = SEVERE_TEST_EXCLUSION if args.severe_test else None

    config = sm.load_config(args.config)
    fit_updates = {}
    for field in ("chains", "warmup", "samples"):
        value = getattr(args, field)
        if value is not None:
            fit_updates[field] = value
    if fit_updates:
        config = config.model_copy(
            update={"fit": config.fit.model_copy(update=fit_updates)}, deep=True
        )

    cfg_hash = config_hash(sm.config_dict(config))
    prefix = "regimes-l2-severe" if exclude is not None else "regimes-l2"
    exp_id = f"{prefix}-{cfg_hash.removeprefix('cfg:')[:12]}-s{args.seed}"
    out_dir = Path(args.exp_root) / exp_id

    climate_artifact = load_climate_artifact(args.climate_artifact)
    print(f"[fit_regimes] vintage {args.vintage}  config {cfg_hash}  seed {args.seed}")
    print(f"[fit_regimes] exp dir: {out_dir}")
    print(
        f"[fit_regimes] L1 artifact: {args.climate_artifact} "
        f"(sha {climate_artifact.meta['content_sha256'][:16]}...)"
    )
    print(
        f"[fit_regimes] NUTS: {config.fit.chains} chain(s) x "
        f"{config.fit.warmup}+{config.fit.samples}"
    )

    catalog = Catalog(Path(args.catalog_root))
    try:
        access = catalog_access(catalog, args.vintage)
        t0 = time.perf_counter()
        result = rfit.fit_regimes(
            access,
            config,
            climate_artifact=climate_artifact,
            seed=args.seed,
            vintage_id=args.vintage,
            out_dir=out_dir,
            created_at=args.created_at,
            report_copy_path=(None if exclude is not None else _REPO_ROOT / rfit.REPORT_FILENAME),
            sensitivity_report_copy_path=(
                None if exclude is not None else _REPO_ROOT / rfit.SENSITIVITY_REPORT_FILENAME
            ),
            run_acceptance=not args.no_acceptance,
            run_sensitivity=not args.no_sensitivity,
            exclude=exclude,
        )
        elapsed = time.perf_counter() - t0
    finally:
        catalog.close()

    d = result.diagnostics
    print(f"[fit_regimes] done in {elapsed / 60.0:.1f} min")
    print(
        f"[fit_regimes] v1: divergences={d['divergences']}  max_rhat={d['max_rhat']:.4f}  "
        f"min_ess={d['min_ess']:.0f}"
    )
    if result.diagnostics_v1b is not None:
        db = result.diagnostics_v1b
        print(
            f"[fit_regimes] v1b: divergences={db['divergences']}  "
            f"max_rhat={db['max_rhat']:.4f}  min_ess={db['min_ess']:.0f}  "
            f"label_agreement={result.label_agreement_v1b:.4f}"
        )
    if result.acceptance is not None:
        judged = [r for r in result.acceptance if r["inside"] is not None]
        inside = sum(1 for r in judged if r["inside"])
        print(f"[fit_regimes] acceptance: {inside}/{len(judged)} judged bands inside")
    print(f"[fit_regimes] artifact: {result.artifact_path}")
    copy_note = " (+ repo-root copy)" if exclude is None else " (no repo-root copy: severe run)"
    print(f"[fit_regimes] report:   {result.report_path}{copy_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
