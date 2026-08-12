"""Post-game annotations (sp-03; register row E4) — computed, never judged.

Two annotations, both computable from the session's own record with no new
state, per the experience-deltas register:

* **The flinch cost.** A commitment cut at a window is priced by re-running
  the SAME decision sequence with only that window's commitments restored to
  the plan: the difference in cumulative distributions received is what the
  cut cost by the decade's end. Fewer vintages can only pay fewer
  distributions — the number states itself.
* **The arithmetic warning.** A defensive action (de-risk, secondary) taken
  at a window where coverage had risen for the DENOMINATOR's reasons —
  reported value fell while obligations did not grow — priced by that
  window's own chain-link contribution when it was negative.

Tone (the style guide's rule, "without smugness"): state the number, never
gloat. No judgement words, no exclamation marks.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ah.core.engine import EnginePaths
from ah.play import (
    PRIVATE_ASSETS,
    plan_commitments,
    simulate_play,
    window_contributions_play,
)

__all__ = ["post_game_annotations"]


def _year(month: int) -> int:
    return (month + 1) // 12


def post_game_annotations(
    paths: EnginePaths,
    decisions: Mapping[int, str | Mapping[str, Any]] | None = None,
    *,
    use_reported: bool = True,
    start_targets: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    """The E4 annotations for one played decade, deterministic."""
    decisions = dict(decisions or {})
    active = simulate_play(paths, decisions, use_reported=use_reported, start_targets=start_targets)
    attribution = window_contributions_play(
        paths, decisions, use_reported=use_reported, start_targets=start_targets
    )
    contrib_by_month = dict(zip(attribution.months, attribution.contributions, strict=True))
    quarters = active.quarters

    notes: list[dict[str, Any]] = []
    for month, action in sorted(decisions.items()):
        name = action if isinstance(action, str) else str(action.get("action"))
        commit_pts = action.get("commitments") if isinstance(action, Mapping) else None
        qw = month // 3  # the window's own closing quarter
        if qw >= len(quarters):
            continue

        # -- the flinch cost -------------------------------------------------
        if commit_pts is not None:
            plan = plan_commitments(quarters[qw].private_weight_reported, start_targets)
            committed = sum(float(commit_pts.get(a, plan[a])) for a in PRIVATE_ASSETS)
            planned = sum(plan.values())
            cut = planned - committed
            if cut > 1e-9:
                counter: dict[int, str | Mapping[str, Any]] = dict(decisions)
                counter[month] = name if name != "commit" else "hold"
                restored = simulate_play(
                    paths, counter, use_reported=use_reported, start_targets=start_targets
                )
                shortfall = sum(q.distributions_received for q in restored.quarters) - sum(
                    q.distributions_received for q in quarters
                )
                notes.append(
                    {
                        "type": "flinch",
                        "month": month,
                        "distribution_shortfall": round(shortfall, 4),
                        "text": (
                            f"Year {_year(month)}: commitments cut from {planned:.1f} to "
                            f"{committed:.1f} points. By the decade's end, distributions "
                            f"were {shortfall:.1f} lower than holding to the plan."
                        ),
                    }
                )

        # -- the arithmetic warning ------------------------------------------
        if name in ("derisk", "secondary"):
            prev = quarters[max(0, qw - 4)]
            now = quarters[qw]
            nav_now = now.nav_reported if use_reported else now.nav_true
            nav_prev = prev.nav_reported if use_reported else prev.nav_true
            if nav_now <= 0 or nav_prev <= 0:
                continue
            cov_now = now.unfunded_total / nav_now
            cov_prev = prev.unfunded_total / nav_prev
            denominator_driven = (
                cov_now > cov_prev
                and nav_now < nav_prev
                and now.unfunded_total <= prev.unfunded_total + 1e-9
            )
            contribution = float(contrib_by_month.get(month, 0.0))
            if denominator_driven and contribution < 0.0:
                notes.append(
                    {
                        "type": "arithmetic_warning",
                        "month": month,
                        "cost": round(-contribution, 4),
                        "text": (
                            f"Year {_year(month)}: coverage had risen, but the rise was "
                            "the denominator - reported value fell while obligations did "
                            f"not grow. The {name} taken there cost "
                            f"{-contribution:.1f} points."
                        ),
                    }
                )
    return notes
