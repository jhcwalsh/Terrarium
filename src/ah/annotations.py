"""Post-game annotations (sp-03; register row E4) — computed, never judged.

Two annotations, both computable from the session's own record with no new
state, per the experience-deltas register:

* **The flinch cost.** A commitment cut at a LOCK (year-close) window is
  priced by re-running the SAME decision sequence with that vintage year's
  commitments restored to the plan (D-QC-1: every window of the forming
  year, not just the lock month's own entry -- a same-year earlier edit
  would otherwise survive the "restore" under the per-sleeve last-edit-wins
  merge): the difference in cumulative distributions received is what the
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

from collections.abc import Mapping, Sequence
from typing import Any

from ah.core.engine import EnginePaths
from ah.play import (
    PRIVATE_ASSETS,
    START_CASH,
    plan_commitments,
    simulate_play,
    window_contributions_play,
)
from ah.port.book import CommitmentPlan, OpeningBook

__all__ = ["post_game_annotations"]


def _year(month: int) -> int:
    return (month + 1) // 12


def post_game_annotations(
    paths: EnginePaths,
    decisions: Mapping[int, str | Mapping[str, Any]] | None = None,
    *,
    use_reported: bool = True,
    start_targets: Mapping[str, float] | None = None,
    opening_book: OpeningBook | None = None,
    commitment_plan: CommitmentPlan | None = None,
    windows: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """The E4 annotations for one played decade, deterministic.

    ``opening_book`` (su-app-06) rides along on every replay here — the
    active run, the attribution, and the flinch-cost restoration — so the
    annotations describe the book the player actually held.

    ``commitment_plan`` (su-app-06, spec section 2: "the lever shows deviation
    from *your* plan, not from the model's") is the analyst's own kickoff
    schedule. When it is given, the flinch cost measures a cut against the
    plan's entry for that window and restores the counterfactual to that same
    entry. ``None`` keeps the model's pacing rule as the baseline, which is
    what every session without a stored plan has always been measured against.

    ``windows`` (D-QC-1) is the session's own window grid, forwarded to the
    chain-link attribution; ``None`` keeps the annual definition for callers
    that predate the quarterly clock. The flinch cost prices the LOCKED
    vintage-year figure, so it fires only at year-close windows — a
    quarterly mid-year revision is not a lock and produces no flinch note of
    its own; its effect appears in the locked figure and the window
    attribution.
    """
    decisions = dict(decisions or {})
    active = simulate_play(
        paths,
        decisions,
        use_reported=use_reported,
        start_targets=start_targets,
        opening_book=opening_book,
    )
    attribution = window_contributions_play(
        paths,
        decisions,
        use_reported=use_reported,
        start_targets=start_targets,
        opening_book=opening_book,
        windows=windows,
    )
    contrib_by_month = dict(zip(attribution.months, attribution.contributions, strict=True))
    quarters = active.quarters
    # su-app-07: when the session carries a book, the pacing-rule baseline
    # below has to be the SAME policy basis `simulate_play` just paced off —
    # the book's own targets and its own cash — or the flinch cost is priced
    # against a plan the engine never ran.
    plan_targets: Mapping[str, float] | None = start_targets
    plan_cash = START_CASH
    if opening_book is not None:
        plan_targets, plan_cash = opening_book.effective_targets(), opening_book.cash

    notes: list[dict[str, Any]] = []
    for month, action in sorted(decisions.items()):
        name = action if isinstance(action, str) else str(action.get("action"))
        commit_pts = action.get("commitments") if isinstance(action, Mapping) else None
        qw = month // 3  # the window's own closing quarter
        if qw >= len(quarters):
            continue

        # -- the flinch cost -------------------------------------------------
        # D-QC-1: the flinch cost prices the LOCKED vintage-year figure, so
        # it fires only at year-close windows (months 12k+11 -- every
        # annual-era window was one, so the legacy behaviour is unchanged; a
        # quarterly mid-year revision is not a lock and produces no flinch
        # note). The plan index is the vintage ordinal month // 12 --
        # identical to the old windows.index(month) on the annual grid.
        if commit_pts is not None and month % 12 == 11:
            # su-app-06: the baseline a cut is measured against is the
            # player's OWN plan entry for this window when the session
            # carries one — indexed by the vintage ordinal, the same
            # definition `ah.serve` fills the lever from. Without a plan it
            # stays the model's pacing rule.
            window = month // 12
            plan = (
                {a: float(commitment_plan.points[a][window]) for a in PRIVATE_ASSETS}
                if commitment_plan is not None
                and all(window < len(commitment_plan.points[a]) for a in PRIVATE_ASSETS)
                else plan_commitments(
                    quarters[qw].private_weight_reported, plan_targets, cash=plan_cash
                )
            )
            committed = sum(float(commit_pts.get(a, plan[a])) for a in PRIVATE_ASSETS)
            planned = sum(plan.values())
            cut = planned - committed
            if cut > 1e-9:
                counter: dict[int, str | Mapping[str, Any]] = dict(decisions)
                # "restored to the plan" has to mean the plan that was cut.
                # Dropping the commitments map instead would restore the
                # model's pacing rule, which on a plan-carrying session is a
                # third number neither the player nor the note ever names.
                if commitment_plan is not None:
                    counter[month] = {"action": name, "commitments": dict(plan)}
                else:
                    # D-QC-1 fix (S4 review IMPORTANT-1): a same-year EARLIER
                    # window's commitments must also be stripped, not just
                    # the lock month's own entry. simulate_play's per-sleeve
                    # last-edit-wins merge (Task S4) reads every window of
                    # the forming vintage year, so restoring only `month`
                    # left an earlier mid-year cut in place -- the "restored"
                    # counterfactual still carried the cut and the flinch
                    # cost silently understated to ~0 (probed:
                    # {14: full-cut, 23: full-cut} priced 0.0 instead of the
                    # correct value a lock-only cut of the same size prices).
                    # Every window of THIS vintage year is stripped to a bare
                    # stance so the lock is priced against a genuinely
                    # commitment-free year.
                    year = month // 12
                    for m, act in list(counter.items()):
                        if m // 12 != year:
                            continue
                        m_name = act if isinstance(act, str) else str(act.get("action"))
                        counter[m] = m_name if m_name != "commit" else "hold"
                restored = simulate_play(
                    paths,
                    counter,
                    use_reported=use_reported,
                    start_targets=start_targets,
                    opening_book=opening_book,
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
