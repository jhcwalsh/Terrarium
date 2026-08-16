"""Seal the spine-pilot bars (spec section 5). Run ONCE; commit the JSON in the
SAME commit as this script; any re-run that changes the JSON is an amendment
and needs an owner-visible commit message saying so. Exception (planned): the
Task-7 re-run that fills the report-script hash is part of the pre-registration
IF AND ONLY IF the thresholds block is byte-identical.

Writes docs/superpowers/specs/spine-pilot-prereg.json from the campaign panel
(``ah.gen.bootstrap.campaign_source``) and the built ``ah.gen.spine`` module.
Deterministic; no randomness is drawn (the panel-derived quantities are plain
statistics over the fitted historical panel, not a sampled ensemble); no
network (the catalog read is local, per CLAUDE.md's no-network rule).

Formulas (frozen by docs/superpowers/specs/2026-08-15-spine-conditioned-
compiler-design.md section 5; this script only fixes the numbers):

- B2 ``panel_p95_adjacent_yoy_pp``: the 95th percentile of
  ``|yoy[t] - yoy[t-1]|`` over panel rows where BOTH t and t-1 have a defined
  (non-NaN) trailing CPI YoY.
- B4 ``panel_dwell_medians``: the median spell length (months), per quadrant,
  of ``panel_quadrant``'s output -- spells computed with
  ``ah.gen.regimes.semimarkov.spells_from_labels`` over the WHOLE cell
  sequence (which already splits a spell at every value change, so a -1
  ["no defined quadrant"] row can never be absorbed into an adjacent
  quadrant's spell); -1 spells are then dropped. Index order matches
  ``ah.gen.spine.QUADRANTS``.
- B4 ``panel_clockwise_fraction``: over consecutive panel rows where both
  quadrants are >= 0 and DIFFER, the fraction of (q_prev, q_next) pairs in
  ``ah.gen.spine.CLOCKWISE``.
- B5 ``panel_rates`` / ``panel_cell_months``: ``fit_hazard(source)`` verbatim.
- B6: the panel-side proxy for "policy gap above its sealed threshold" is
  yield-curve inversion (``ust_10y - ust_2y < 0``) -- the spine side's own
  threshold is frozen at 0.0pp (tight = the r*/pi* anchor exceeded) since the
  panel carries no r*/pi* series to compare against directly. An onset is
  credited to the month the CRI label turns on (``is_cri[j] & ~is_cri[j-1]``,
  row 0 counts if it opens inside CRI). Only rows with a FULL k-month lookahead
  available (``t + k <= n_rows - 1``) are counted, matching ``fit_hazard``'s
  own edge discipline (excluding the panel's last row from "at risk") --
  otherwise a right-truncated tail would understate every rate near the
  panel's end. Both the conditional and unconditional rates are taken over the
  same yoy-defined population, so the two numbers differ only by the
  inversion filter.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from ah.gen.bootstrap import campaign_source
from ah.gen.regimes.semimarkov import spells_from_labels
from ah.gen.spine import (
    CLOCKWISE,
    MIN_CELL_MONTHS,
    QUADRANTS,
    fit_hazard,
    panel_quadrant,
    panel_yoy,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-pilot-prereg.json"
K_MONTHS = 12


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _b2_panel_p95_adjacent_yoy_pp(yoy: np.ndarray) -> float:
    diffs = []
    for t in range(1, yoy.size):
        if not np.isnan(yoy[t]) and not np.isnan(yoy[t - 1]):
            diffs.append(abs(float(yoy[t]) - float(yoy[t - 1])))
    return float(np.percentile(np.asarray(diffs), 95))


def _b4_dwell_medians(cells: np.ndarray) -> list[float | None]:
    durations: dict[int, list[int]] = {i: [] for i in range(len(QUADRANTS))}
    for state, _start, length in spells_from_labels(cells):
        if state in durations:
            durations[state].append(length)
    return [float(np.median(durations[i])) if durations[i] else None for i in range(len(QUADRANTS))]


def _b4_clockwise_fraction(cells: np.ndarray) -> float:
    total = 0
    clockwise = 0
    for t in range(1, cells.size):
        a, b = int(cells[t - 1]), int(cells[t])
        if a >= 0 and b >= 0 and a != b:
            total += 1
            if (a, b) in CLOCKWISE:
                clockwise += 1
    return float(clockwise) / total if total else float("nan")


def _b6_onset_rates(source, yoy: np.ndarray, *, k: int = K_MONTHS) -> tuple[float, float]:
    n = source.n_rows
    labels = np.asarray(source.labels)
    is_cri = labels == "CRI"
    onset_at = np.zeros(n, dtype=bool)
    onset_at[0] = bool(is_cri[0])
    onset_at[1:] = is_cri[1:] & ~is_cri[:-1]

    factor_names = list(source.factor_names)
    ci10, ci2 = factor_names.index("ust_10y"), factor_names.index("ust_2y")
    vals = np.asarray(source.values)
    inverted = (vals[:, ci10] - vals[:, ci2]) < 0.0

    yoy_defined = ~np.isnan(yoy)
    eligible = yoy_defined.copy()
    eligible[max(n - k, 0) :] = False  # a full k-month lookahead must be observable

    def _onset_within(t: int | np.integer) -> bool:
        t = int(t)
        return bool(onset_at[t + 1 : t + 1 + k].any())

    idx = np.flatnonzero(eligible)
    unconditional = (
        float(sum(_onset_within(t) for t in idx)) / idx.size if idx.size else float("nan")
    )
    cond_idx = idx[inverted[idx]]
    conditional = (
        float(sum(_onset_within(t) for t in cond_idx)) / cond_idx.size
        if cond_idx.size
        else float("nan")
    )
    return conditional, unconditional


def main() -> None:
    source = campaign_source()
    yoy = panel_yoy(source)
    hazard = fit_hazard(source)
    cells = panel_quadrant(source, yoy, hazard.era_threshold_pp)

    dwell_medians = _b4_dwell_medians(cells)
    clockwise_fraction = _b4_clockwise_fraction(cells)
    p95_adjacent = _b2_panel_p95_adjacent_yoy_pp(yoy)
    cond_rate, uncond_rate = _b6_onset_rates(source, yoy, k=K_MONTHS)

    committer_date = _git("log", "-1", "--format=%cI")
    head_sha = _git("rev-parse", "HEAD")

    report_script = _REPO_ROOT / "scripts" / "spine_pilot_report.py"
    seal_script = Path(__file__)
    preset_path = _REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json"
    spine_module = _REPO_ROOT / "src" / "ah" / "gen" / "spine.py"
    stress_module = _REPO_ROOT / "src" / "ah" / "gen" / "stress.py"
    bootstrap_module = _REPO_ROOT / "src" / "ah" / "gen" / "bootstrap.py"
    semimarkov_module = _REPO_ROOT / "src" / "ah" / "gen" / "regimes" / "semimarkov.py"
    climate_model_module = _REPO_ROOT / "src" / "ah" / "gen" / "climate" / "model.py"
    climate_simulate_module = _REPO_ROOT / "src" / "ah" / "gen" / "climate" / "simulate.py"

    sealed = {
        "sealed_at_utc": f"{committer_date} (as of HEAD commit {head_sha})",
        "b1": {
            "min_sign_fraction": 0.90,
            "lag_months": [3, 12],
        },
        "b2": {
            "join_yoy_max_pp": 2.5,
            "p95_ratio_max": 1.25,
            "panel_p95_adjacent_yoy_pp": p95_adjacent,
        },
        "b3": {
            "grid_private_pct": [15, 35, 40, 55],
            "min_breach_seeds_at_55": 1,
            "n_seeds": 20,
            "coverage_must_be_monotone": True,
        },
        "b4": {
            "dwell_median_ratio_band": [0.6, 1.4],
            "quadrants": list(QUADRANTS),
            "panel_dwell_medians": dwell_medians,
            "clockwise_fraction_tolerance": 0.15,
            "panel_clockwise_fraction": clockwise_fraction,
            "power_disclosure": (
                "stagflation's dwell median rests on 12 spells and the clockwise anchor "
                "on 68 transitions (SE ~0.059); tolerances are near the anchors' own "
                "sampling noise - a marginal B4 result must be read accordingly; "
                "tolerances must NOT be widened after measurement"
            ),
        },
        "b5": {
            "rel_tolerance": 0.5,
            "panel_rates": [float(x) for x in hazard.rates],
            "panel_cell_months": [int(x) for x in hazard.cell_months],
            "era_threshold_pp": float(hazard.era_threshold_pp),
            "fallback_rate": float(hazard.fallback_rate),
            "min_cell_months": MIN_CELL_MONTHS,
            "zero_rate_convention": (
                "a panel rate of exactly 0 passes iff the realized rate is exactly 0; "
                "note the recovery cell is tautological (the sampler cannot fire at rate "
                "0), so a PASS there is a plumbing assertion, not evidence about the model"
            ),
            "numerator_disclosure": (
                "the table rests on 6 panel CRI onsets (1970-01, 1970-04, 1974-03, "
                "2001-06, 2008-09, 2020-03); 1970 is one episode counted as two onsets "
                "and expansion's rate rests on the 1970-01 orphan blip; B5 tests the "
                "wiring, not the hazard model"
            ),
        },
        "b6": {
            "k_months": K_MONTHS,
            "spine_policy_gap_threshold_pp": 0.0,
            "panel_conditional_onset_rate": cond_rate,
            "panel_unconditional_onset_rate": uncond_rate,
            "rel_tolerance": 0.5,
            "base_rate_disclosure": (
                "panel conditioning (curve inversion) covers 149/813 months; the "
                "spine-side conditioning fraction is unpinned; the Task-7 report MUST "
                "print both base rates, and a B6 FAIL with base rates differing by more "
                "than 2x is recorded as INCONCLUSIVE (construct mismatch), not a "
                "compiler defect"
            ),
        },
        "severity_table_disclosure": (
            "the either/both inflation condition equals the quadrant hot bit; "
            "discrimination in practice is on credit_gap (owner ruling "
            "2026-08-16: keep for pilot, revisit at D-SP-1)"
        ),
        "sensitivity_seeds": [199002 + 1000003 * j for j in range(5)],
        "hashes": {
            "src/ah/gen/spine.py": _sha256(spine_module),
            "src/ah/gen/stress.py": _sha256(stress_module),
            "src/ah/gen/bootstrap.py": _sha256(bootstrap_module),
            "src/ah/gen/regimes/semimarkov.py": _sha256(semimarkov_module),
            "src/ah/gen/climate/model.py": _sha256(climate_model_module),
            "src/ah/gen/climate/simulate.py": _sha256(climate_simulate_module),
            "scripts/spine_pilot_report.py": (
                _sha256(report_script) if report_script.exists() else "unbuilt"
            ),
            "scripts/spine_pilot_seal.py": _sha256(seal_script),
            "src/ah/presets/spine_pilot.json": _sha256(preset_path),
        },
    }

    # sanity: MIN_CELL_MONTHS must equal the frozen constant we quote below
    assert MIN_CELL_MONTHS == 24, (
        "MIN_CELL_MONTHS drifted from the frozen bar; amend, do not silently reseal"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"panel_p95_adjacent_yoy_pp = {p95_adjacent:.4f} (bound {2.5})")
    print(f"panel_dwell_medians ({', '.join(QUADRANTS)}) = {dwell_medians}")
    print(f"panel_clockwise_fraction = {clockwise_fraction:.4f}")
    print(f"b6 conditional = {cond_rate:.4f}, unconditional = {uncond_rate:.4f}")


if __name__ == "__main__":
    main()
