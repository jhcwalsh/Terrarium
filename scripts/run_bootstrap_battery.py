"""Run the full validation battery against ``bootstrap-v1`` (STEP2 Sec.WP2.4).

This is the PROVENANCE SCRIPT for WP2.4's battery numbers, the same role
``scripts/compute_campaign_reference.py`` plays for the sealed bands and
``scripts/measure_block_length_window.py`` plays for the sealed mean block length.
Nothing here judges anything: it assembles the sealed campaign vintage, samples the
benchmark at the sealed criterion size, and hands the ensemble to
``ah.eval.battery.run_full_battery``, which verifies the pre-registration and its lock
before evaluating a single metric.

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/run_bootstrap_battery.py --out-dir artifacts/wp24

Determinism: the ensemble seed is ``--seed``, sampling seed ``k`` is
``seed + 7919*k`` (the platform rule), and the reference bootstrap draw uses the sealed
``reference_run.seed`` so the bands this run is judged against are the sealed ones.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from ah.data.catalog import Catalog
from ah.eval import prereg as prereg_mod
from ah.eval.battery import run_full_battery
from ah.factors import load_manifest
from ah.gen.bootstrap import (
    BLOCK_DRAW_SPAN_START,
    CAMPAIGN_VINTAGE_ID,
    CRITERION_MONTHS,
    CRITERION_N_PATHS,
    SEED_STRIDE,
    SEVERE_TEST_POSABLE,
    BootstrapV1,
    build_source,
)
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The sealed reference-run parameters (pre-registration.yaml's `reference_run:` block).
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


# The five numbers `pre-registration.yaml`'s `bootstrap_v1.what_wp24_must_report` says
# this work package must supply and the sealed document cannot. Reported for every run,
# whatever they say.
_WP24_REPORTABLE: tuple[str, ...] = (
    # (2) the three band-exceedance gates at the sealed criterion size
    "moment_band_exceedance_fraction",
    "dependence_band_exceedance_fraction",
    "tail_band_exceedance_fraction",
    # (3) the memorization surface that bounds mean_block_months from above
    "near_duplicate_fraction",
    "nn_distance_p05",
    "nn_distance_p50",
    "membership_inference_auc",
    # (4) elicitability for every computable D4 strategy
    "eqw_factors.elicitability_score",
    "sixty_forty.elicitability_score",
    "endowment_proxy.elicitability_score",
    "momentum.elicitability_score",
    "carry.elicitability_score",
    # (5) the two economics statistics the vintage move made computable
    "term_premium",
    "equity_risk_premium",
    "policy_anchor_deviation",
)


def _results(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Every unfiltered metric result of a :meth:`BatteryReport.to_dict` document."""
    return [row for tier in doc["unfiltered"]["tiers"].values() for row in tier]


def _band_exceedance_census(doc: dict[str, Any]) -> dict[str, Any]:
    """The per-comparison band exceedance rate over EVERY usable banded comparison.

    ``pre-registration.yaml``'s ``bootstrap_v1.what_wp24_must_report`` item (1): the
    first empirical observation of the null that
    ``limitations.null_exceedance_rate_is_unverified`` says the three band-exceedance
    gates' 0.10 premise assumes. A 90% reference band should, under that premise, be
    exceeded by a well-behaved generator about 10% of the time -- and until this run
    nothing had ever measured it.

    Degenerate (zero-width) and non-finite bands are excluded from the denominator, for
    the same reason :func:`ah.eval.battery.band_is_usable` excludes them from gating: a
    band that cannot be satisfied is not a comparison. Both are counted separately so
    the exclusion is visible rather than silent.
    """
    total = outside = degenerate = unusable = 0
    offenders: list[dict[str, Any]] = []
    for result in _results(doc):
        band = result["band"]
        if band is None:
            continue
        if band["band_degenerate"]:
            degenerate += 1
            continue
        if not (math.isfinite(band["lo"]) and math.isfinite(band["hi"])):
            unusable += 1
            continue
        total += 1
        if band["band_outside"]:
            outside += 1
            offenders.append(
                {
                    "name": result["name"],
                    "suite": result["suite"],
                    "value": result["value"],
                    "lo": band["lo"],
                    "hi": band["hi"],
                }
            )
    return {
        "usable_banded_comparisons": total,
        "outside": outside,
        "rate": (outside / total) if total else None,
        "nominal_rate_the_gates_assume": 0.10,
        "excluded_degenerate_bands": degenerate,
        "excluded_non_finite_bands": unusable,
        "outside_by_suite": {
            suite: sum(1 for o in offenders if o["suite"] == suite)
            for suite in sorted({o["suite"] for o in offenders})
        },
        "outside_comparisons": offenders,
    }


def _summarise(doc: dict[str, Any]) -> dict[str, Any]:
    """The verdict, the WP2.4 reportables, and every enforce comparison, pass or fail.

    Takes the report's own JSON document rather than the :class:`BatteryReport`, so
    ``--analyse-only`` can re-derive every number in this summary from the committed
    ``battery-seed*.json`` evidence with no catalog and no re-run.
    """
    results = _results(doc)
    enforce = [r for r in results if r["severity"] == "enforce"]
    by_name = {r["name"]: r for r in results}
    return {
        "band_exceedance_census": _band_exceedance_census(doc),
        "wp24_reportable": {
            name: {
                "value": by_name[name]["value"],
                "mc_error": by_name[name]["mc_error"],
                "severity": by_name[name]["severity"],
                "passed": by_name[name]["passed"],
            }
            for name in _WP24_REPORTABLE
            if name in by_name
        },
        "report_severity_failures": [
            {"name": r["name"], "suite": r["suite"], "value": r["value"]}
            for r in results
            if r["severity"] == "report" and r["passed"] is False
        ],
        "conditional_suite": {
            r["name"]: {"value": r["value"], "mc_error": r["mc_error"]}
            for r in sorted(results, key=lambda r: r["name"])
            if r["suite"] == "conditional"
        },
        "passed": doc["passed"],
        "criterion_bearing": doc["criterion_bearing"],
        "prereg_verified": doc["prereg_verified"],
        "prereg_digest": doc["prereg_digest"],
        "seed": doc["seed"],
        "n_metrics": len(results),
        "n_enforce": len(enforce),
        "enforce_failures": [
            {
                "name": r["name"],
                "suite": r["suite"],
                "tier": r["tier"],
                "value": r["value"],
                "mc_error": r["mc_error"],
                "band": None
                if r["band"] is None
                else {"lo": r["band"]["lo"], "hi": r["band"]["hi"]},
            }
            for r in enforce
            if r["passed"] is False
        ],
        "enforce_results": [
            {
                "name": r["name"],
                "suite": r["suite"],
                "tier": r["tier"],
                "value": r["value"],
                "mc_error": r["mc_error"],
                "passed": r["passed"],
                "status": r["status"],
            }
            for r in sorted(enforce, key=lambda r: (r["suite"], r["name"]))
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=_REPO_ROOT / "artifacts" / "wp24")
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--seed", type=int, default=REFERENCE_SEED)
    parser.add_argument("--n-paths", type=int, default=CRITERION_N_PATHS)
    parser.add_argument("--months", type=int, default=CRITERION_MONTHS)
    parser.add_argument("--seeds", type=int, default=1, help="how many sampling seeds to run")
    parser.add_argument(
        "--analyse-only",
        action="store_true",
        help="re-derive summary.json from the battery-seed*.json already in --out-dir "
        "(no catalog, no re-run): the WP2.4 numbers from the committed evidence",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.analyse_only:
        docs = [
            json.loads(path.read_text("utf-8"))
            for path in sorted(args.out_dir.glob("battery-seed*.json"))
        ]
        if not docs:
            raise SystemExit(f"no battery-seed*.json in {args.out_dir}")
        summaries = [_summarise(doc) for doc in docs]
        _write_summary(args, summaries, source=None)
        return

    manifest = load_manifest()
    prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")

    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        source = build_source(access, manifest, vintage_id=args.vintage)
        print(f"draw span: {source.dates[0].date()}..{source.dates[-1].date()} ({source.n_rows} m)")
        print(f"factor_set ({source.n_factors}): {list(source.factor_names)}")
        print(f"regime frequencies: {dict(sorted(source.label_frequencies.items()))}")
        print(f"severe test posable: {SEVERE_TEST_POSABLE} (span starts {BLOCK_DRAW_SPAN_START})")

        generator = BootstrapV1(source)
        summaries: list[dict[str, Any]] = []
        for k in range(args.seeds):
            seed = args.seed + SEED_STRIDE * k
            ensemble = generator.sample_months(args.months, args.n_paths, seed)
            report = run_full_battery(
                ensemble,
                access=access,
                manifest=manifest,
                prereg=prereg,
                seed=seed,
                reference_seed=REFERENCE_SEED,
                n_resamples=N_RESAMPLES,
                level=LEVEL,
                block_length=BLOCK_LENGTH,
            )
            (args.out_dir / f"battery-seed{seed}.json").write_text(report.to_json(), "utf-8")
            (args.out_dir / f"battery-seed{seed}.md").write_text(report.to_markdown(), "utf-8")
            summary = _summarise(report.to_dict())
            summaries.append(summary)
            verdict = "PASS" if summary["passed"] else "FAIL"
            print(
                f"seed {seed}: {verdict} -- {len(summary['enforce_failures'])} enforce "
                f"failure(s) of {summary['n_enforce']} enforce comparisons"
            )
            for failure in summary["enforce_failures"]:
                print(f"    FAIL {failure['name']} = {failure['value']:.6g}")
            census = summary["band_exceedance_census"]
            print(
                f"    per-comparison band exceedance: {census['outside']}/"
                f"{census['usable_banded_comparisons']} = {census['rate']:.4f} "
                f"(the gates' premise assumes {census['nominal_rate_the_gates_assume']})"
            )
            for name, entry in summary["wp24_reportable"].items():
                print(f"    {name:42s} {entry['value']:.6g}")

    _write_summary(args, summaries, source=source)


# The three source-derived provenance fields a run records and `--analyse-only` cannot
# recompute (they come from the catalog, which that mode deliberately does not open).
_SOURCE_PROVENANCE: tuple[str, ...] = ("factor_set", "block_draw_span", "regime_frequencies")


def _write_summary(
    args: argparse.Namespace, summaries: list[dict[str, Any]], *, source: Any | None
) -> None:
    out = args.out_dir / "summary.json"
    payload: dict[str, Any] = {
        "vintage_id": args.vintage,
        "n_paths": args.n_paths,
        "months": args.months,
        "base_seed": args.seed,
        "reference_seed": REFERENCE_SEED,
        "severe_test_posable": SEVERE_TEST_POSABLE,
        "runs": summaries,
    }
    if source is not None:
        payload |= {
            "factor_set": list(source.factor_names),
            "block_draw_span": {
                "start": str(source.dates[0].date()),
                "end": str(source.dates[-1].date()),
                "months": source.n_rows,
            },
            "regime_frequencies": dict(sorted(source.label_frequencies.items())),
        }
    elif out.exists():
        # `--analyse-only` re-derives the ANALYSIS, not the run: the draw span, factor
        # set and regime frequencies are facts about the catalog this mode does not open,
        # so they are carried forward from the run that produced them rather than dropped
        # (which would silently shrink the committed artifact) or recomputed from a
        # vintage that may no longer be the one the reports came from.
        previous = json.loads(out.read_text("utf-8"))
        payload |= {key: previous[key] for key in _SOURCE_PROVENANCE if key in previous}
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
