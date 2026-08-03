"""The decision-density study machinery (WP5.5).

Which decision windows matter, how much, and under what conditions: across
many worlds and decision-makers, attribute each participant's terminal alpha
to individual decision windows and study where |contribution| concentrates.

**The attribution is DN-5 SS5's ratified decomposition** (decision D:
"Sequential chain-link. Telescopes exactly to the terminal difference"):

    V_j  = final value with the participant's actions at windows <= j applied
           and HOLD at every later window
    c_j  = V_j - V_{j-1}          (V_{-1} is the hold-course twin's final)
    sum_j c_j = V_full - V_twin   (exactly -- the telescoping identity,
                                   pinned by test, never approximated)

``c_j`` is the value of the j-th decision GIVEN everything decided before it
and mechanical policy after it -- the same sequential convention DN-5 chose
for the product's outcome card, so the research statistic and the player-
facing number cannot drift apart.

The expected finding this machinery exists to TEST rather than assume (the
plan's words): consequence concentrates at t0, at regime breaks, and in the
re-risking window after a trough, with quiet-period decisions carrying
delayed weight.
"""

from __future__ import annotations

from dataclasses import dataclass

from ah.core.engine import EnginePaths
from ah.core.institution import decision_months, simulate_institution

__all__ = ["WindowAttribution", "window_contributions"]


@dataclass(frozen=True)
class WindowAttribution:
    """One participant's chain-link decomposition on one world.

    ``contributions[j]`` is c_j for the j-th decision window (month
    ``months[j]``); ``total_alpha`` is the terminal difference the chain
    telescopes to, restated for the reader rather than recomputed by one.
    """

    months: tuple[int, ...]
    actions: tuple[str, ...]
    contributions: tuple[float, ...]
    twin_final: float
    final_value: float

    @property
    def total_alpha(self) -> float:
        return self.final_value - self.twin_final


def window_contributions(
    paths: EnginePaths,
    decisions: dict[int, str],
    *,
    use_reported: bool = False,
) -> WindowAttribution:
    """DN-5's sequential chain-link decomposition of one decision sequence.

    K+1 institution runs for K windows (the twin plus one per prefix) --
    exact, no sampling. Windows the participant left unmapped default to hold
    inside ``simulate_institution`` exactly as they did when the sequence was
    played, so a partial decision map decomposes correctly.
    """
    months_list = decision_months(paths.months)
    twin = simulate_institution(paths, None, use_reported=use_reported)
    prev_final = float(twin.final_value)

    contributions: list[float] = []
    actions: list[str] = []
    prefix: dict[int, str] = {}
    for month in months_list:
        action = decisions.get(month, "hold")
        prefix[month] = action
        run = simulate_institution(paths, dict(prefix), use_reported=use_reported)
        final = float(run.final_value)
        contributions.append(final - prev_final)
        actions.append(action)
        prev_final = final

    return WindowAttribution(
        months=tuple(months_list),
        actions=tuple(actions),
        contributions=tuple(contributions),
        twin_final=float(twin.final_value),
        final_value=prev_final,
    )
