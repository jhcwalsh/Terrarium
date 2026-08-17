"""``grader_v2`` -- the season classifier the spine v2 exam is sealed against.

**Why this file exists at all.** The incumbent classifier is
``ah.gen.spine.panel_quadrant``. It sorts a month onto the growth axis by asking
whether the month's ``regime_ruleset_v1`` label is ``REC`` or ``CRI``, and
nothing else -- so a month the ruleset labels ``STAG`` (its own stagflation
label: trailing CPI at or above ``cpi_high`` = 4.0 pp AND trailing industrial
production growth at or below ``growth_weak`` = 0.0 %/yr) is treated as
**expanding**. The spine v2 exam's §11.1 found that quirk and §11.5 found it
biting on real months: the whole of 1975-04 -> 1975-12 -- industrial production
-11% year on year, unemployment up 3.7 pp, a 15-25% equity drawdown, inflation
near 10% -- is classified as *expansion* by the incumbent dial.

Owner ruling, 2026-08-17 ("Seal it"): for **transition/ordering purposes** a
stagflation month sits on the **non-expanding** side, per the owner's own
definition of the season -- growth stalling while inflation is high. That is the
only change. ``grader_v2`` is the incumbent two-dial classification with
``STAG`` moved from the expanding set to the contracting set:

    contracting  <-  label in {REC, CRI, STAG}      (incumbent: {REC, CRI})
    hot          <-  trailing 12-month CPI YoY > era_threshold_pp   (unchanged)
    season       <-  ah.gen.spine.QUADRANTS[(expanding << 1) | hot] (unchanged)

**What this file deliberately does NOT do.**

- It does not edit ``src/ah/gen/spine.py``. The pilot's code and its two frozen
  seals (``spine-pilot-prereg.json``, ``spine02-prereg.json``) stay untouched, so
  round one's and round two's records remain exactly what they were. This module
  is judge-side code, hashed into the v2 seal, and nothing in ``src/`` imports it.
- It does not touch T1's downturn definition. T1 counts a downturn as a month
  whose label turns to ``REC`` or ``CRI``, on both sides, and that union is
  carried into the v2 exam **unchanged** -- its band was measured on it. A
  ``STAG`` month is therefore contracting for the clock and is still not a
  downturn onset for T1. The asymmetry is deliberate and is declared as a
  limitation in the exam document; folding ``STAG`` into T1 would mean
  re-measuring T1's anchor, which is not what the owner ruled.
- It adds no threshold of its own. The era threshold arrives from the caller
  (``ah.gen.spine.fit_hazard(source).era_threshold_pp`` on the panel side, the
  sealed value on the judged side), so there is no second copy to drift.

Every ``STAG`` month in the campaign panel is hot by construction: the ruleset
fires ``STAG`` only at or above 4.0 pp trailing CPI and the era threshold is
3.351323828920571 pp, so 4.0 > 3.3513 always. The panel check bears that out --
31 ``STAG`` months, 31 of them hot -- so on this vintage the mapping fix moves
months from *expansion* to *stagflation* and nowhere else. The classifier does
not assume it: a cool ``STAG`` month, if one ever existed, would land in
*recession*, which is the right cell for "contracting, inflation cool".

Import-safe: importing this module reads no data, draws no random number and
writes no file.
"""

from __future__ import annotations

import numpy as np

from ah.gen.regimes.semimarkov import spells_from_labels
from ah.gen.spine import CLOCKWISE, QUADRANTS

__all__ = [
    "CONTRACTING_LABELS",
    "INCUMBENT_CONTRACTING_LABELS",
    "clockwise_counts",
    "completed_spells",
    "season_cells",
]

#: The contracting side under ``grader_v2``. ``STAG`` is the addition; the owner
#: ruling of 2026-08-17 is the authority for it.
CONTRACTING_LABELS: tuple[str, ...] = ("REC", "CRI", "STAG")

#: What ``ah.gen.spine.panel_quadrant`` uses, kept here so a test can state the
#: difference between the two graders as data rather than as prose.
INCUMBENT_CONTRACTING_LABELS: tuple[str, ...] = ("REC", "CRI")


def season_cells(
    labels: np.ndarray | list[str],
    yoy: np.ndarray,
    era_threshold_pp: float,
    *,
    contracting_labels: tuple[str, ...] = CONTRACTING_LABELS,
) -> np.ndarray:
    """The four-season cell per month; ``-1`` where trailing inflation is undefined.

    ``labels`` are ``regime_ruleset_v1`` month labels, ``yoy`` is trailing
    12-month CPI inflation in percentage points (``NaN`` during a series' own
    12-month warm-up), and the returned codes index ``ah.gen.spine.QUADRANTS``
    -- ``(expanding << 1) | hot``, the incumbent encoding, unchanged.

    ``contracting_labels`` exists so the SAME code can produce the incumbent
    classification (pass ``INCUMBENT_CONTRACTING_LABELS``) for a side-by-side
    comparison. The judges never pass it: they take the default, which is
    ``grader_v2``.
    """
    labels_arr = np.asarray(labels)
    yoy_arr = np.asarray(yoy, dtype=np.float64)
    if labels_arr.shape != yoy_arr.shape:
        raise ValueError(
            f"labels {labels_arr.shape} and yoy {yoy_arr.shape} must be the same shape"
        )
    contracting = np.isin(labels_arr, list(contracting_labels))
    cells = np.full(yoy_arr.size, -1, dtype=np.int8)
    ok = ~np.isnan(yoy_arr)
    hot = (yoy_arr > era_threshold_pp).astype(np.int8)
    expanding = (~contracting).astype(np.int8)
    cells[ok] = (expanding[ok] << 1) | hot[ok]
    return cells


def completed_spells(cells: np.ndarray) -> list[list[int]]:
    """Completed spell lengths per season, in ``QUADRANTS`` order.

    The exam's completed-spell rule (§3), applied to one window of months: a run
    that opens the window, closes it, or touches a stretch of months with no
    defined season has an unknown true length and is dropped. This is the same
    decomposition ``scripts/spine_v2_anchors.py`` applies to the panel and to
    each simulated decade, kept in one place so the judged side and the anchor
    side cannot use two different rules.
    """
    runs = spells_from_labels(np.asarray(cells, dtype=np.int8))
    out: list[list[int]] = [[] for _ in QUADRANTS]
    n_runs = len(runs)
    for position, (state, _start, length) in enumerate(runs):
        if state < 0 or position == 0 or position == n_runs - 1:
            continue
        if runs[position - 1][0] < 0 or runs[position + 1][0] < 0:
            continue
        out[int(state)].append(int(length))
    return out


def clockwise_counts(cells: np.ndarray) -> tuple[int, int]:
    """``(transitions, clockwise transitions)`` over consecutive month pairs.

    A pair counts only if both months have a defined season and the two differ;
    it is clockwise if it is in ``ah.gen.spine.CLOCKWISE`` (recovery ->
    expansion -> stagflation -> recession -> recovery). This is the transition
    rule of ``scripts/spine_pilot_seal._b4_clockwise_fraction``, unchanged.
    """
    arr = np.asarray(cells, dtype=np.int64)
    total = 0
    clockwise = 0
    for t in range(1, arr.size):
        a, b = int(arr[t - 1]), int(arr[t])
        if a >= 0 and b >= 0 and a != b:
            total += 1
            if (a, b) in CLOCKWISE:
                clockwise += 1
    return total, clockwise
