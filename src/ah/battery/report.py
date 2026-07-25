"""Run the stylized-fact battery on a toy ensemble and report (STEP0-PLAN §WP0.8).

Produces a markdown + JSON report and exits non-zero only on ``enforce`` failures.
``python -m ah.battery.report`` runs it on the stagflation preset (the CI job).
The battery version string is recorded into RunRecords by the CLI (WP0.9).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ah.battery.stylized import (
    acf,
    acf_abs,
    corr_matrix_distance,
    cross_correlation_matrix,
    excess_kurtosis,
    hill_tail_index,
    max_drawdown_distribution,
    skewness,
)
from ah.core.engine import ASSETS, EnsembleResult, run_ensemble
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.factors import FactorManifest, load_manifest

BATTERY_VERSION = "battery-0.1"
_THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"
_ACF_R_LAGS = [1, 2, 3, 4, 5]
_ACF_ABS_LAGS = list(range(1, 13))


@dataclass
class Check:
    metric: str
    value: float
    min: float | None
    max: float | None
    status: str
    ok: bool


@dataclass
class BatteryReport:
    version: str
    scalars: dict[str, float]
    details: dict[str, Any]
    checks: list[Check]
    active_blocks: tuple[str, ...] = ()

    @property
    def enforce_failures(self) -> list[Check]:
        return [c for c in self.checks if c.status == "enforce" and not c.ok]

    @property
    def passed(self) -> bool:
        return not self.enforce_failures


def load_thresholds(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    p = Path(path) if path is not None else _THRESHOLDS_PATH
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def compute_panel(ensemble: EnsembleResult) -> tuple[dict[str, float], dict[str, Any]]:
    """Scalar metrics (thresholded) + details (arrays) for one ensemble."""
    eq = ensemble.returns["equity"]
    pooled = eq.reshape(-1)
    mean_path = eq.mean(axis=0)

    asset_matrix = np.column_stack([ensemble.returns[a].mean(axis=0) for a in ASSETS])
    corr = cross_correlation_matrix(asset_matrix)
    reference = np.eye(len(ASSETS))
    dd = max_drawdown_distribution(eq)

    acf_r = acf(mean_path, _ACF_R_LAGS)
    acf_a = acf_abs(mean_path, _ACF_ABS_LAGS)

    scalars = {
        "excess_kurtosis": excess_kurtosis(pooled),
        "skewness": skewness(pooled),
        "hill_tail_index": hill_tail_index(pooled),
        "acf_r_lag1": acf_r[0],
        "acf_abs_lag1": acf_a[0],
        "max_drawdown_median": float(np.median(dd)),
        "corr_distance": corr_matrix_distance(corr, reference),
    }
    details = {
        "acf_r": acf_r,
        "acf_abs": acf_a,
        "corr_matrix": corr.tolist(),
        "assets": list(ASSETS),
        "n_paths": ensemble.n_paths,
        "months": ensemble.months,
    }
    return scalars, details


def evaluate(scalars: dict[str, float], thresholds: dict[str, dict[str, Any]]) -> list[Check]:
    checks: list[Check] = []
    for metric, value in scalars.items():
        spec = thresholds.get(metric)
        if spec is None:
            continue
        lo = spec.get("min")
        hi = spec.get("max")
        status = spec.get("status", "todo")
        ok = True
        if not np.isnan(value):
            if lo is not None and value < lo:
                ok = False
            if hi is not None and value > hi:
                ok = False
        checks.append(Check(metric, value, lo, hi, status, ok))
    return checks


def run_battery(
    ensemble: EnsembleResult,
    thresholds: dict[str, dict[str, Any]] | None = None,
    manifest: FactorManifest | None = None,
) -> BatteryReport:
    """Run the battery. ``manifest`` defaults to the repo-root ``factors.yaml``
    (``ah.factors.load_manifest()``); inject a synthetic one (e.g. built from a
    ``tmp_path`` fixture) to exercise the battery against a block configuration other
    than the real campaign's (WP2.1b Item 2 acceptance: "a synthetic two-block
    configuration passes the battery")."""
    if thresholds is None:
        thresholds = load_thresholds()
    if manifest is None:
        manifest = load_manifest()
    scalars, details = compute_panel(ensemble)
    checks = evaluate(scalars, thresholds)
    return BatteryReport(BATTERY_VERSION, scalars, details, checks, manifest.active_blocks)


def render_markdown(report: BatteryReport) -> str:
    lines = [
        f"# Validation battery report ({report.version})",
        "",
        f"- paths: {report.details['n_paths']} x {report.details['months']} months",
        f"- active_blocks: {', '.join(report.active_blocks)}",
        "",
        "| metric | value | min | max | status | ok |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in report.checks:
        lines.append(
            f"| {c.metric} | {c.value:.4g} | {c.min if c.min is not None else ''} "
            f"| {c.max if c.max is not None else ''} | {c.status} | "
            f"{'yes' if c.ok else 'NO'} |"
        )
    failures = report.enforce_failures
    lines += ["", f"**enforce failures: {len(failures)}**"]
    return "\n".join(lines) + "\n"


def render_json(report: BatteryReport) -> str:
    payload = {
        "version": report.version,
        "scalars": report.scalars,
        "details": report.details,
        "checks": [asdict(c) for c in report.checks],
        "passed": report.passed,
        "active_blocks": list(report.active_blocks),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _stagflation_ensemble(n_paths: int = 64) -> EnsembleResult:
    root = Path(__file__).resolve().parents[3]
    doc = json.loads(
        (root / "schemas" / "example-long-stagflation.worldspec.json").read_text("utf-8")
    )
    doc["engine_defaults"]["generator_id"] = "toy-v0"
    nw = project_numeric(load_worldspec(doc))
    return run_ensemble(nw, n_paths, base_seed=42)


def main(argv: list[str] | None = None) -> int:
    report = run_battery(_stagflation_ensemble())
    sys.stdout.write(render_markdown(report))
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
