"""D-SP-12 -- the polish round's engine, compiled and audited.

Charter: ``governance/decision-register.md`` **D-SP-12** (owner ruling
2026-08-19). This is the round's **run entry point**: the one place where the
polish engine is configured, so that "which engine was measured" is a single
readable object rather than a set of arguments repeated at call sites.

The engine, stated once:

* **reach design** -- :data:`stage2_polish.POLISH_REACH`, i.e.
  ``stage2_worlds.ERA_CONDITIONAL_REACH``: D-SP-10's path-matched entries, the
  mid-block divergence break and the anticipating re-entry, **plus the
  conditional era-crossing rule, which this round ADOPTS** (change 2);
* **join selection** -- :data:`stage2_polish.SELECTION_MIN_GAP`: among the
  era-safe candidates, the smallest inflation gap at the seam wins, earliest
  panel row breaking ties (change 1);
* **slow climate** -- the L1 recalibration (change 3), once
  ``scripts/stage2_polish_calibrate.py`` has derived it.

The licence audit is live on every arm this script compiles and it is a **stop**:
every bucket-changing seam is re-derived from the compiled row tape by the
sealed ``stage2_rulers.era_crossing_audit`` and an unlicensed crossing raises.
The join-selection change alters which candidate is taken at a crossing month,
so D-SP-11's 104-of-104 reading is **not** inherited -- it is retaken here.

Run (from the worktree root, no network):

    uv run python scripts/stage2_polish_run.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_fit as weeka  # noqa: E402
import stage2_polish as polish  # noqa: E402
import stage2_reach as reach  # noqa: E402
import stage2_rulers as rulers  # noqa: E402
import stage2_worlds as worlds  # noqa: E402

from ah.gen.spine import fit_hazard, panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"

#: The lineage, oldest first. Named at every call site rather than left to a
#: module default, because the default has moved twice already.
DSP10 = worlds.ADOPTED_REACH
DSP11 = worlds.ERA_CONDITIONAL_REACH
POLISH = polish.POLISH_REACH


def panel_era_bucket(source: Any) -> np.ndarray:
    """The panel's era bucket, exactly as ``SpineBootstrap.sample_months`` cuts it."""
    yoy = panel_yoy(source)
    hazard = fit_hazard(source)
    return np.where(np.isnan(yoy), -1, (yoy > hazard.era_threshold_pp).astype(np.int64))


def compile_and_audit(
    fx: Any,
    design: Any,
    seed: int,
    era_bucket: np.ndarray,
    *,
    arm: str,
    selection: str = polish.SELECTION_MIN_GAP,
    calibration: Any | None = None,
) -> dict[str, Any]:
    """One arm of the polish engine, compiled and licence-audited.

    ``calibration`` is accepted here so the run entry point's shape is fixed
    before change 3 arrives; ``None`` is the unrecalibrated slow climate.
    """
    del calibration  # change 3 installs it; the parameter pins the call shape
    with polish.join_selection(selection):
        armed = reach.compile_arm(fx, design, seed)
    seasons = np.stack([np.asarray(d.season, dtype=np.int64) for d in armed["decades"]])
    audit = rulers.era_crossing_audit(
        armed["rows"], seasons, era_bucket, n_panel_rows=fx.source.n_rows
    )
    armed["era_crossing_audit"] = polish.assert_licensed_crossings(audit, arm=arm)
    armed["selection"] = selection
    return armed


def main() -> int:
    fx = reach._Fixtures()
    seed = int(weeka.STAGE2_VERIFY_SEED)
    era_bucket = panel_era_bucket(fx.source)

    print(f"D-SP-12 -- the polish engine. reach design: {POLISH.name}")
    print(f"  era_conditional_crossing = {POLISH.era_conditional_crossing}  (ADOPTED, change 2)")
    for label, design, selection in (
        ("D-SP-11 (era rule, platform selection)", DSP11, polish.SELECTION_PLATFORM),
        ("polish (era rule + min-gap joins)", POLISH, polish.SELECTION_MIN_GAP),
    ):
        arm = compile_and_audit(fx, design, seed, era_bucket, arm=label, selection=selection)
        audit = arm["era_crossing_audit"]
        print(
            f"  {label:40s} reach {arm['reach']['conditioning_reach']:.4f}  "
            f"crossing seams {audit['crossing_seams']:4d}  "
            f"unlicensed {audit['unlicensed_crossing_seams']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
