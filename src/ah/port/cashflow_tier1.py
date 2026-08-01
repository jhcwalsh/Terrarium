"""Tier 1 — the market-sensitive cashflow engine (WP3.4, linkage_version public-0.1).

The same cohort recursion as tier 0 with the linkage ON, plus the structural
fund mechanics the plan names: management fees with the basis change, European
carry with hurdle and catch-up, recycling (through the cohort's recallable
machinery), subscription-line call deferral, and extension behavior. Linkage
parameters come frozen from ``mappings/cashflow-tier1-v1.0.yaml`` (sealed
before any replay existed); structural parameters ride the cohort's own frozen
fee/TA contract. One model throughout: **tier 1 with the linkage off and fees
off IS tier 0**, asserted by test, never assumed.

Both linkage functions consume CONTINUOUS market states only — no regime
label, no recession dummy reaches this module's API (Delta 3, structural).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ah.port.cohort import ClosedEndCohort, CohortStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
LINKAGE_PATH = _REPO_ROOT / "mappings" / "cashflow-tier1-v1.0.yaml"


class Tier1Error(ValueError):
    """A linkage artifact or run that violates the tier-1 contract."""


@lru_cache(maxsize=1)
def load_linkage(path: Path | None = None) -> dict[str, Any]:
    p = path or LINKAGE_PATH
    if not p.exists():
        raise Tier1Error(f"{p}: linkage artifact not found — run scripts/freeze_tier1_linkage.py")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    for key in ("f_dist", "f_call", "pm_growth_loadings"):
        if key not in doc:
            raise Tier1Error(f"linkage artifact missing '{key}'")
    return doc


def f_dist(dd: float, spread_ratio: float, *, artifact_path: Path | None = None) -> float:
    """The distribution response — bounded, monotone-decreasing in stress.

    ``dd`` is equity drawdown depth (>= 0); ``spread_ratio`` the IG spread
    level over its trailing anchor (> 0). Continuous states only.
    """
    if dd < 0.0 or spread_ratio <= 0.0:
        raise Tier1Error("dd must be >= 0 and spread_ratio > 0")
    spec = load_linkage(artifact_path)["f_dist"]
    raw = float(np.exp(-spec["a_drawdown"] * dd - spec["b_log_spread"] * np.log(spread_ratio)))
    return float(np.clip(raw, spec["floor"], spec["ceiling"]))


def f_call(dd: float, *, artifact_path: Path | None = None) -> float:
    """The call response — near-flat (Delta 3): deployment barely slows in stress."""
    if dd < 0.0:
        raise Tier1Error("dd must be >= 0")
    spec = load_linkage(artifact_path)["f_call"]
    return float(np.clip(1.0 - spec["c"] * dd, 0.5, 1.2))


@dataclass(frozen=True)
class StructuralTerms:
    """The plan's structural mechanics, all register kind C (chosen, stated)."""

    investment_period_years: float = 5.0  # fee basis flips committed -> NAV here
    recycling_fraction: float = 0.10  # share of early distributions marked recallable
    recycling_window_years: float = 3.0
    sub_line_deferral_quarters: int = 0  # 0 = no subscription line
    extension_nav_threshold: float = 0.10  # extend at L if NAV/committed above this
    extension_years: float = 2.0


@dataclass
class Tier1Result:
    flows: list[CohortStep]
    fees_paid: list[float]
    carry_crystallized: float
    net_distributions: list[float]
    extended: bool


def run_tier1(
    base_document: dict[str, Any],
    *,
    committed: float,
    vintage_year: int,
    sleeve_returns: np.ndarray,
    drawdown_depth: np.ndarray,
    spread_ratio: np.ndarray,
    terms: StructuralTerms | None = None,
    fees_on: bool = True,
    linkage_on: bool = True,
    artifact_path: Path | None = None,
) -> Tier1Result:
    """One cohort's market-sensitive path over ``len(sleeve_returns)`` quarters.

    ``sleeve_returns`` are the cohort's TRUE quarterly returns (from the PM
    growth loadings applied upstream); ``drawdown_depth``/``spread_ratio`` are
    the continuous market states per quarter. With ``linkage_on=False`` and
    ``fees_on=False`` this is EXACTLY tier 0's recursion — one model.
    """
    n = len(sleeve_returns)
    if not (len(drawdown_depth) == len(spread_ratio) == n):
        raise Tier1Error("returns and state arrays must share a length")
    terms = terms or StructuralTerms()

    cohort = ClosedEndCohort.new_commitment(
        base_document,
        committed=committed,
        vintage_year=vintage_year,
        cohort_id=f"tier1-{vintage_year}",
    )
    fee_spec = cohort.contract.fees
    life = cohort.contract.lifecycle.contractual_life_years

    deferred: list[float] = []  # subscription-line queue (amounts still to call)
    flows: list[CohortStep] = []
    fees_paid: list[float] = []
    net_dists: list[float] = []
    extended = False

    for t in range(n):
        # extension decision exactly at end of life
        if (
            not extended
            and cohort.age_years >= life
            and cohort.nav_true / committed > terms.extension_nav_threshold
        ):
            cohort.extension_status = "extended"
            extended = True
        if extended and cohort.age_years >= life + terms.extension_years:
            cohort.extension_status = "expired"  # terminal liquidation resumes

        fc = f_call(float(drawdown_depth[t]), artifact_path=artifact_path) if linkage_on else 1.0
        fd = (
            f_dist(
                float(drawdown_depth[t]),
                float(spread_ratio[t]),
                artifact_path=artifact_path,
            )
            if linkage_on
            else 1.0
        )
        step = cohort.step(float(sleeve_returns[t]), f_call=fc, f_dist=fd)

        # subscription line: the LP cash call is deferred, the fund invests now.
        call_for_lp = step.call
        if terms.sub_line_deferral_quarters > 0:
            deferred.append(step.call)
            call_for_lp = 0.0
            if len(deferred) > terms.sub_line_deferral_quarters:
                call_for_lp = deferred.pop(0)

        # recycling: early distributions partially recallable (R14 machinery)
        if cohort.age_years <= terms.recycling_window_years and step.distribution_total > 0:
            cohort.mark_recallable(terms.recycling_fraction * step.distribution_total)

        # management fee: committed basis in the investment period, NAV after
        if fees_on:
            basis = (
                committed
                if cohort.age_years <= terms.investment_period_years
                else (cohort.nav_true)
            )
            fee = fee_spec.mgmt_fee_rate * 0.25 * basis
        else:
            fee = 0.0
        fees_paid.append(fee)
        flows.append(
            CohortStep(
                call=call_for_lp,
                distribution_income=step.distribution_income,
                distribution_capital=step.distribution_capital,
                nav_growth=step.nav_growth,
                fees_paid=fee,
                carry_crystallized=0.0,
            )
        )
        net_dists.append(step.distribution_total - fee)

    # European carry: crystallizes once, at the end, on whole-fund profit
    carry = 0.0
    if fees_on:
        paid_in = sum(f.call for f in flows) + sum(deferred)
        total_dist = sum(f.distribution_total for f in flows) + cohort.nav_true
        preferred = paid_in * (1.0 + fee_spec.hurdle) ** max(1.0, cohort.age_years)
        profit_above_hurdle = max(0.0, total_dist - preferred)
        carry = fee_spec.carry_rate * profit_above_hurdle

    return Tier1Result(
        flows=flows,
        fees_paid=fees_paid,
        carry_crystallized=carry,
        net_distributions=net_dists,
        extended=extended,
    )
