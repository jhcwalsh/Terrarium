"""Tier 0 — the transparent cashflow benchmark (WP3.5).

The register's classic constant-G Takahashi-Alexander, run through the SAME
cohort recursion tier 1 will use with the linkage OFF: ``f_call = f_dist = 1``
and NAV growth constant at the frozen ``g_annual``. One model with the linkage
on or off — never two models that can disagree about anything except the
linkage. The spec (including measured G and the recorded unavailability of the
historical-simulation leg) is frozen in ``mappings/cashflow-tier0-v1.0.yaml``,
sealed before any tier-1 code existed.

This is what tier 1 must BEAT under the sealed ``tier0_beats_rule``, scored by
the identical sealed episode formulas — and if it does not, tier 0 ships and
G3 says so.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ah.port.cohort import ClosedEndCohort, CohortStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = _REPO_ROOT / "mappings" / "cashflow-tier0-v1.0.yaml"


class Tier0Error(ValueError):
    """A tier-0 spec or run that violates the frozen benchmark contract."""


@lru_cache(maxsize=1)
def load_spec(path: Path | None = None) -> dict[str, Any]:
    p = path or SPEC_PATH
    if not p.exists():
        raise Tier0Error(f"{p}: tier-0 spec not found — run scripts/freeze_tier0_spec.py")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if "g_annual" not in doc:
        raise Tier0Error("tier-0 spec missing g_annual")
    return doc


def run_tier0(
    base_document: dict[str, Any],
    *,
    committed: float,
    vintage_year: int,
    quarters: int,
    spec_path: Path | None = None,
) -> list[CohortStep]:
    """A fresh cohort's full constant-G cashflow path, quarterly.

    Deterministic: the same inputs give the same flows, always — the benchmark
    has no randomness to hide behind.
    """
    if quarters < 1:
        raise Tier0Error("quarters must be >= 1")
    spec = load_spec(spec_path)
    g_quarterly = (1.0 + float(spec["g_annual"])) ** 0.25 - 1.0
    cohort = ClosedEndCohort.new_commitment(
        base_document,
        committed=committed,
        vintage_year=vintage_year,
        cohort_id=f"tier0-{vintage_year}",
    )
    return [cohort.step(g_quarterly) for _ in range(quarters)]
