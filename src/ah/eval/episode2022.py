"""The 2022 episode scorer (WP3.11) — the sealed criteria, executable.

Scores the replay against ``pre-registration-g3.yaml``'s
``episode_2022_criteria``, each function carrying its sealed formula. PURE:
this module consumes computed quantities (paths, troughs, rates, prices) and
compares them to the sealed numbers — it never imports the engine it judges
(the judge/defendant boundary the G3 guards enforce). The driver
(``scripts/run_2022_replay.py``) runs the chain and hands the numbers over.

Joins ``pre-registration-g3.lock`` by dated amendment in the commit that
creates it, exactly as the sealed document announced. A NaN in any criterion's
computed value is a FAIL for that criterion — never a pass, never an
exclusion (the sealed gate_rule, verbatim).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
G3_PREREG_PATH = _REPO_ROOT / "pre-registration-g3.yaml"

#: The sealed gate rule's two clauses, by criterion name.
MUST_PASS = ("public_equity_drawdown", "mark_lag", "distribution_shortfall", "secondary_pricing")
MAY_FAIL_NAMED = ("private_weight_breach", "coverage_warning")


class EpisodeScoreError(RuntimeError):
    """Inputs the sealed formulas cannot honestly score."""


@dataclass(frozen=True)
class CriterionResult:
    name: str
    value: float
    passed: bool
    detail: str

    @property
    def value_is_finite(self) -> bool:
        return bool(np.isfinite(self.value))


def _sealed() -> dict[str, Any]:
    return yaml.safe_load(G3_PREREG_PATH.read_text(encoding="utf-8"))["episode_2022_criteria"]


def score_public_equity_drawdown(replay_drawdown: float) -> CriterionResult:
    """Sealed: within +/- 0.05 absolute of the -0.2484 reference."""
    spec = _sealed()["public_equity_drawdown"]
    reference = float(spec["reference"])
    ok = np.isfinite(replay_drawdown) and abs(replay_drawdown - reference) <= 0.05
    return CriterionResult(
        "public_equity_drawdown",
        float(replay_drawdown),
        bool(ok),
        f"replay {replay_drawdown:.4f} vs sealed reference {reference:.4f} (+/- 0.05)",
    )


def score_mark_lag(pm_lag_months: float, hf_lag_months: float) -> CriterionResult:
    """Sealed: PM cohort aggregate lag in [1, 6] months; HF aggregate in [0, 3]."""
    ok = (
        np.isfinite(pm_lag_months)
        and np.isfinite(hf_lag_months)
        and 1.0 <= pm_lag_months <= 6.0
        and 0.0 <= hf_lag_months <= 3.0
    )
    return CriterionResult(
        "mark_lag",
        float(pm_lag_months),
        bool(ok),
        f"PM lag {pm_lag_months:.1f}m (sealed [1,6]), HF lag {hf_lag_months:.1f}m (sealed [0,3])",
    )


def score_distribution_shortfall(trough_rate: float, normal_rate: float) -> CriterionResult:
    """Sealed: trough aggregate distribution rate / normal in [0.45, 0.55]."""
    if normal_rate <= 0.0 or not np.isfinite(normal_rate):
        return CriterionResult(
            "distribution_shortfall", float("nan"), False, "normal rate not positive/finite"
        )
    depth = trough_rate / normal_rate
    ok = np.isfinite(depth) and 0.45 <= depth <= 0.55
    return CriterionResult(
        "distribution_shortfall",
        float(depth),
        bool(ok),
        f"depth {depth:.3f} of normal (sealed [0.45, 0.55], the P-A calibration)",
    )


def score_secondary_pricing(price_of_nav: float) -> CriterionResult:
    """Sealed: the engine's 2022-H2 secondary price in [0.76, 0.86] of NAV."""
    ok = np.isfinite(price_of_nav) and 0.76 <= price_of_nav <= 0.86
    return CriterionResult(
        "secondary_pricing",
        float(price_of_nav),
        bool(ok),
        f"price {price_of_nav:.3f} of NAV (sealed [0.76, 0.86], anchor 0.81)",
    )


def score_private_weight_breach(
    breach_month_offset_from_trough: float, breach_size: float
) -> CriterionResult:
    """Sealed: breach within 3 months of the public trough; size >= 0.02."""
    ok = (
        np.isfinite(breach_month_offset_from_trough)
        and np.isfinite(breach_size)
        and abs(breach_month_offset_from_trough) <= 3.0
        and breach_size >= 0.02
    )
    return CriterionResult(
        "private_weight_breach",
        float(breach_size),
        bool(ok),
        f"breach at trough{breach_month_offset_from_trough:+.0f}m, size {breach_size:.3f} "
        "(sealed: within 3m, >= 0.02)",
    )


def score_coverage_warning(has_unfunded_nav: bool, has_unfunded_liquid: bool) -> CriterionResult:
    """Sealed presence criterion: both ratios emitted by the replay."""
    ok = bool(has_unfunded_nav and has_unfunded_liquid)
    return CriterionResult(
        "coverage_warning",
        1.0 if ok else 0.0,
        ok,
        f"unfunded/NAV present: {has_unfunded_nav}; unfunded/liquid present: {has_unfunded_liquid}",
    )


@dataclass(frozen=True)
class EpisodeVerdict:
    results: tuple[CriterionResult, ...]
    passed: bool
    named_failures: tuple[str, ...]

    def score(self) -> int:
        """The tier0_beats_rule's episode score: the count of failed criteria."""
        return sum(1 for r in self.results if not r.passed)


def apply_gate_rule(results: list[CriterionResult]) -> EpisodeVerdict:
    """The sealed gate_rule, verbatim: the four MUST_PASS criteria all pass;
    the two MAY_FAIL_NAMED either pass or fail WITH the failure named (the
    naming is enforced by G1-EVIDENCE.md's generator, which refuses to omit
    them)."""
    by_name = {r.name: r for r in results}
    missing = [n for n in (*MUST_PASS, *MAY_FAIL_NAMED) if n not in by_name]
    if missing:
        raise EpisodeScoreError(f"gate rule needs every criterion scored; missing {missing}")
    must_ok = all(by_name[n].passed for n in MUST_PASS)
    named = tuple(n for n in MAY_FAIL_NAMED if not by_name[n].passed)
    return EpisodeVerdict(
        results=tuple(by_name[n] for n in (*MUST_PASS, *MAY_FAIL_NAMED)),
        passed=bool(must_ok),
        named_failures=named,
    )
