"""The spine v2 exam's SEALED judging code -- one pure judge per bar.

Spec: ``docs/superpowers/specs/2026-08-17-spine-v2-exam.md``. Thresholds are
sealed in ``docs/superpowers/specs/spine-v2-prereg.json`` and this module reads
them from there; **no threshold is written as a literal in this file**, following
``scripts/spine_pilot_report.py``'s own rule ("this script may build judges and
read thresholds from that file, but it may never write one back into the
thresholds themselves"). The two constants that do appear -- ``QUADRANTS``
ordering and the ``CLOCKWISE`` set -- are imported from the platform module that
owns them, not restated.

**Import-safe.** Importing this module reads no data, samples no ensemble, draws
no random number and writes no file, so the tests and the anti-test sweeps can
import the judges directly (the round-one precedent).

**What a judge is handed.** A :class:`Batch` of :class:`Decade` records, one per
generated decade, each carrying only raw per-month series: the
``regime_ruleset_v1`` labels, trailing 12-month CPI inflation, the tight-policy
flag, and three asset return series. **The judge does the classifying itself**,
through ``scripts/spine_v2_grader.py`` -- so the sealed mapping fix cannot be
bypassed by a caller that hands in its own season labels, and the anchor side and
the judged side run the same code.

**Every bar is judged on the POOLED batch**, never decade by decade: T1's lift
pools tight months and downturn onsets across the batch, O1 pools transitions,
D1-D4 pool completed spells, A1 and A2 pool months and rolling windows. That is
the owner's pre-seal ruling of 2026-08-17 for D1-D4 and the construct the power
calculation measures for all of them.

**Eligibility, stated once and applied identically on both sides.** A month is
eligible for an inflation-conditioned statistic only if its own trailing 12-month
inflation is defined (the decade's first 12 months are not); T1 additionally
requires a full 12-month lookahead inside the decade, leaving 96 eligible months
of 120; A2's rolling correlation windows are computed INSIDE the decade and the
first usable window ends at decade month 37, leaving 84; D1-D4 drop the spell a
decade opens with and the spell it closes with, the same completed-spell rule the
anchors apply to the panel's own windows.

**R1 and R2 are byte-frozen and IMPORTED, not re-implemented.** ``judge_r1``
delegates to ``scripts/spine_pilot_b3._judge`` and ``judge_r2`` to
``scripts/spine_pilot_report.judge_b2`` -- the same functions round two ran,
loaded from the same files, whose sha256 hashes are in the v2 seal. Import rather
than copy (the choice the spine02 precedent leaves open) because a copy can drift
under an editor and an import cannot: if either file changes, the seal's hash
check fails, which is the intended alarm.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ah.gen.spine import QUADRANTS

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_pilot_b3 import _judge as _judge_b3  # noqa: E402
from spine_pilot_report import judge_b2 as _judge_b2  # noqa: E402
from spine_v2_grader import clockwise_counts, completed_spells, season_cells  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SEALED_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-prereg.json"
SPINE02_SEAL_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine02-prereg.json"

#: The bar codes this module judges, in exam order.
BAR_CODES = ("T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2", "R1", "R2")
#: D-bar code -> season name, in ``ah.gen.spine.QUADRANTS`` order.
D_SEASONS = dict(zip(("D1", "D2", "D3", "D4"), QUADRANTS, strict=True))


# --------------------------------------------------------------------------- #
# the object a judge is handed
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Decade:
    """One generated decade's raw monthly series. 120 months in the campaign.

    ``labels`` are ``regime_ruleset_v1`` month labels; ``yoy`` is trailing
    12-month CPI inflation in percentage points, ``NaN`` for the decade's own
    warm-up; ``tight`` is the exam's tight-policy flag (the 10-year yield below
    the 2-year, computed identically on both sides); the three return series are
    monthly total returns as fractions (0.01 = +1%), ``NaN`` where undefined.
    """

    labels: np.ndarray
    yoy: np.ndarray
    tight: np.ndarray
    equities: np.ndarray
    bonds: np.ndarray
    commodities: np.ndarray

    def __post_init__(self) -> None:
        n = self.labels.shape[0]
        for name in ("yoy", "tight", "equities", "bonds", "commodities"):
            got = getattr(self, name).shape[0]
            if got != n:
                raise ValueError(f"Decade.{name} has {got} months, labels have {n}")

    @property
    def months(self) -> int:
        return int(self.labels.shape[0])


@dataclass(frozen=True)
class Batch:
    """The generated batch a verdict is taken over -- ``n_seeds`` decades."""

    decades: tuple[Decade, ...]

    @property
    def n_decades(self) -> int:
        return len(self.decades)


# --------------------------------------------------------------------------- #
# small pure helpers (no thresholds live here)
# --------------------------------------------------------------------------- #


def _cells(decade: Decade, sealed: dict[str, Any]) -> np.ndarray:
    """The decade's season per month, under the SEALED grader."""
    return season_cells(
        decade.labels,
        decade.yoy,
        float(sealed["parameters"]["era_threshold_pp"]),
        contracting_labels=tuple(sealed["parameters"]["contracting_labels"]),
    )


def _onset_flags(downturn: np.ndarray) -> np.ndarray:
    """``True`` where a downturn BEGINS. Row 0 counts if the decade opens in one.

    Same convention as ``scripts/spine_v2_anchors._onset_flags`` and the pilot's
    own ``_b6_onset_rates``; it never affects a verdict here, because the first
    eligible month is month 13 and looks only forward.
    """
    out = np.zeros(downturn.shape[0], dtype=bool)
    out[0] = bool(downturn[0])
    out[1:] = downturn[1:] & ~downturn[:-1]
    return out


def _lift_counts(
    decade: Decade, downturn_labels: tuple[str, ...], k_months: int
) -> tuple[int, int, int, int]:
    """``(eligible, tight, tight_and_followed, followed)`` for one decade."""
    downturn = np.isin(decade.labels, list(downturn_labels))
    onset = _onset_flags(downturn)
    n = decade.months
    followed = np.zeros(n, dtype=bool)
    for t in range(n - k_months):
        followed[t] = bool(onset[t + 1 : t + 1 + k_months].any())
    eligible = ~np.isnan(decade.yoy)
    eligible[max(n - k_months, 0) :] = False  # a full lookahead must be observable
    tight = np.asarray(decade.tight, dtype=bool) & eligible
    return (
        int(eligible.sum()),
        int(tight.sum()),
        int((tight & followed).sum()),
        int((eligible & followed).sum()),
    )


def _corr_from_sums(n: float, sx: float, sy: float, sxx: float, syy: float, sxy: float) -> float:
    """Pearson correlation from pooled sums; ``nan`` on a degenerate input."""
    if n < 2:
        return float("nan")
    cov = sxy - sx * sy / n
    vx = sxx - sx * sx / n
    vy = syy - sy * sy / n
    if vx <= 0.0 or vy <= 0.0:
        return float("nan")
    return float(cov / np.sqrt(vx * vy))


def _pooled_median(values: list[int]) -> float:
    return float(np.median(np.asarray(values, dtype=np.float64))) if values else float("nan")


def _inflation_masks(decade: Decade, line_pp: float) -> tuple[np.ndarray, np.ndarray]:
    defined = ~np.isnan(decade.yoy)
    high = defined & (decade.yoy >= line_pp)
    low = defined & (decade.yoy < line_pp)
    return high, low


# --------------------------------------------------------------------------- #
# the judges
# --------------------------------------------------------------------------- #


def judge_t1(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    """T1 -- does tightening cause downturns? (the transmission bar)

    Pooled lift: the chance a downturn onset falls in the next ``k`` months
    measured over tight months only, divided by the same chance over all
    eligible months. Both sides of the ratio are taken over the SAME eligible
    population, so they differ only by the tightness filter.
    """
    params = sealed["parameters"]
    k = int(params["k_months"])
    downturn_labels = tuple(params["downturn_labels"])
    band = [float(x) for x in sealed["bars"]["T1_lift_band"]]

    totals = np.zeros(4, dtype=np.int64)
    for decade in batch.decades:
        totals += np.asarray(_lift_counts(decade, downturn_labels, k), dtype=np.int64)
    eligible, tight, tight_hit, hit = (int(x) for x in totals)

    conditional = tight_hit / tight if tight else float("nan")
    unconditional = hit / eligible if eligible else float("nan")
    lift = conditional / unconditional if unconditional else float("nan")

    # The crisis-only figure is a DISCLOSURE, never a bar: it rests on six panel
    # events and its historical interval contains 1.0 (exam section 2).
    crisis_labels = tuple(params["crisis_only_labels"])
    ctotals = np.zeros(4, dtype=np.int64)
    for decade in batch.decades:
        ctotals += np.asarray(_lift_counts(decade, crisis_labels, k), dtype=np.int64)
    c_elig, c_tight, c_tight_hit, c_hit = (int(x) for x in ctotals)
    c_cond = c_tight_hit / c_tight if c_tight else float("nan")
    c_uncond = c_hit / c_elig if c_elig else float("nan")

    return {
        "bar": "T1",
        "pass": bool(band[0] <= lift <= band[1]),
        "value": lift,
        "band": band,
        "eligible_months": eligible,
        "tight_months": tight,
        "tight_base_rate": tight / eligible if eligible else float("nan"),
        "conditional_rate": conditional,
        "unconditional_rate": unconditional,
        "n_decades": batch.n_decades,
        "crisis_only_disclosure": {
            "lift": (c_cond / c_uncond) if c_uncond else float("nan"),
            "conditional_rate": c_cond,
            "unconditional_rate": c_uncond,
            "judged": False,
        },
    }


def judge_o1(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    """O1 -- do the seasons turn the right way round? (the ordering bar)

    Pooled clockwise fraction over transitions counted INSIDE each decade; a
    transition across two decades does not exist and is never invented.
    """
    minimum = float(sealed["bars"]["O1_clockwise_min"])
    total = 0
    clockwise = 0
    for decade in batch.decades:
        t, c = clockwise_counts(_cells(decade, sealed))
        total += t
        clockwise += c
    fraction = clockwise / total if total else float("nan")
    return {
        "bar": "O1",
        "pass": bool(fraction >= minimum),
        "value": fraction,
        "threshold": minimum,
        "n_transitions": total,
        "n_clockwise": clockwise,
        "n_decades": batch.n_decades,
    }


def judge_d(batch: Batch, sealed: dict[str, Any], code: str) -> dict[str, Any]:
    """D1-D4 -- how long a season lasts (the persistence bars).

    The median of every COMPLETED spell in the batch, pooled into one
    distribution, against the panel's own decade-pooled median plus or minus one
    quarter. Both sides are measured on 120-month windows with the same warm-up
    and the same completed-spell rule -- the owner's pre-seal ruling of
    2026-08-17, and the reason a D verdict is about the engine rather than about
    where a decade's edges happened to fall.
    """
    if code not in D_SEASONS:
        raise KeyError(f"{code} is not a D bar; expected one of {sorted(D_SEASONS)}")
    season = D_SEASONS[code]
    index = QUADRANTS.index(season)
    band = [float(x) for x in sealed["bars"]["D_median_bands_months"][season]]

    pooled: list[int] = []
    per_decade: list[int] = []
    for decade in batch.decades:
        lengths = completed_spells(_cells(decade, sealed))[index]
        pooled.extend(lengths)
        per_decade.append(len(lengths))
    median = _pooled_median(pooled)
    lo, hi = band
    return {
        "bar": code,
        "season": season,
        "pass": bool(lo <= median <= hi),
        "value": median,
        "band": band,
        "anchor_months": float(sealed["bars"]["D_anchor_medians_months"][season]),
        "n_pooled_spells": len(pooled),
        "spells_per_decade": (float(np.mean(per_decade)) if per_decade else float("nan")),
        "quartiles_months": (
            [float(x) for x in np.percentile(np.asarray(pooled, dtype=np.float64), [25, 75])]
            if pooled
            else [float("nan"), float("nan")]
        ),
        "n_decades": batch.n_decades,
        "reading_note": (
            "a FAIL that misses by one quarter is inside the anchor's own sampling noise "
            "and is not evidence about the engine (exam section 3)"
        ),
    }


def judge_d1(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    return judge_d(batch, sealed, "D1")


def judge_d2(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    return judge_d(batch, sealed, "D2")


def judge_d3(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    return judge_d(batch, sealed, "D3")


def judge_d4(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    return judge_d(batch, sealed, "D4")


def judge_a1(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    """A1 -- does the inflation hedge pay when inflation is high? (the spread bar)

    Commodities minus bonds, annualised arithmetically (12 x the mean monthly
    return, in percentage points) over the pooled high-inflation months and over
    the pooled low-inflation months. The directional condition is the test; the
    containment range is a plausibility check whose value under selection-only
    compilation is closer to a plumbing assertion (exam section 4).
    """
    params = sealed["parameters"]
    line = float(params["inflation_high_line_pp"])
    containment = [float(x) for x in sealed["bars"]["A1_containment_pp"]]

    sums = {"high": np.zeros(3), "low": np.zeros(3)}
    for decade in batch.decades:
        high, low = _inflation_masks(decade, line)
        for key, mask in (("high", high), ("low", low)):
            usable = mask & ~np.isnan(decade.commodities) & ~np.isnan(decade.bonds)
            sums[key] += np.asarray(
                [
                    float(usable.sum()),
                    float(np.nansum(decade.commodities[usable])),
                    float(np.nansum(decade.bonds[usable])),
                ]
            )

    def _spread(key: str) -> float:
        n, c, b = sums[key]
        return 1200.0 * (c / n - b / n) if n else float("nan")

    spread_high, spread_low = _spread("high"), _spread("low")
    directional = bool(spread_high > spread_low)
    contained = bool(containment[0] <= spread_high <= containment[1])
    return {
        "bar": "A1",
        "pass": bool(directional and contained),
        "value": spread_high - spread_low,
        "directional_pass": directional,
        "containment_pass": contained,
        "spread_high_pp": spread_high,
        "spread_low_pp": spread_low,
        "difference_pp": spread_high - spread_low,
        "containment_pp": containment,
        "months_high": int(sums["high"][0]),
        "months_low": int(sums["low"][0]),
        "inflation_line_pp": line,
        "n_decades": batch.n_decades,
    }


def judge_a2(batch: Batch, sealed: dict[str, Any]) -> dict[str, Any]:
    """A2 -- do stocks and bonds fall together when inflation is high?

    Three conditions, all pooled: the high-inflation stock-bond correlation is
    positive; it exceeds the low-inflation one by at least the sealed margin;
    and at least the sealed share of 36-month windows ending in a high-inflation
    month is positive. **The low-inflation share ceiling was dropped by owner
    ruling (2026-08-17)** -- ``A2_share_low_ceiling`` is ``null`` -- and the
    statistic is still computed and reported here against the value it would
    have been judged at, so dropping it hides nothing.
    """
    params = sealed["parameters"]
    line = float(params["inflation_high_line_pp"])
    win = int(params["rolling_window_months"])
    bars = sealed["bars"]
    margin = float(bars["A2_correlation_margin"])
    share_floor = float(bars["A2_share_high_floor"])
    ceiling = bars["A2_share_low_ceiling"]  # None == dropped
    dropped_at = bars.get("A2_share_low_ceiling_dropped_value")

    acc = {"high": np.zeros(6), "low": np.zeros(6)}
    windows = {"high": [0, 0], "low": [0, 0]}
    for decade in batch.decades:
        high, low = _inflation_masks(decade, line)
        eq, bd = decade.equities, decade.bonds
        for key, mask in (("high", high), ("low", low)):
            usable = mask & ~np.isnan(eq) & ~np.isnan(bd)
            e, b = eq[usable], bd[usable]
            acc[key] += np.asarray(
                [
                    float(e.size),
                    float(e.sum()),
                    float(b.sum()),
                    float((e * e).sum()),
                    float((b * b).sum()),
                    float((e * b).sum()),
                ]
            )
        # rolling windows computed INSIDE the decade; the first usable window
        # ends at month `win` (0-based), which also steps over a first month
        # whose bond return may be undefined -- the same edge the anchors' own
        # rolling series applies.
        for t in range(win, decade.months):
            lo = t - win + 1
            e, b = eq[lo : t + 1], bd[lo : t + 1]
            if np.isnan(e).any() or np.isnan(b).any():
                continue
            if float(np.std(e)) == 0.0 or float(np.std(b)) == 0.0:
                continue
            key = "high" if high[t] else ("low" if low[t] else None)
            if key is None:
                continue
            windows[key][0] += 1
            if float(np.corrcoef(e, b)[0, 1]) > 0.0:
                windows[key][1] += 1

    corr = {k: _corr_from_sums(*acc[k]) for k in ("high", "low")}
    share = {
        k: (windows[k][1] / windows[k][0] if windows[k][0] else float("nan"))
        for k in ("high", "low")
    }
    level_positive = bool(corr["high"] > 0.0)
    margin_pass = bool((corr["high"] - corr["low"]) >= margin)
    share_pass = bool(share["high"] >= share_floor)
    return {
        "bar": "A2",
        "pass": bool(level_positive and margin_pass and share_pass),
        "value": corr["high"] - corr["low"],
        "level_positive": level_positive,
        "margin_pass": margin_pass,
        "share_high_pass": share_pass,
        "correlation_high": corr["high"],
        "correlation_low": corr["low"],
        "correlation_difference": corr["high"] - corr["low"],
        "margin": margin,
        "share_positive_high": share["high"],
        "share_positive_low": share["low"],
        "share_high_floor": share_floor,
        "months_high": int(acc["high"][0]),
        "months_low": int(acc["low"][0]),
        "windows_high": windows["high"][0],
        "windows_low": windows["low"][0],
        "dropped_ceiling_disclosure": {
            "judged": ceiling is not None,
            "would_have_been_judged_at": dropped_at,
            "share_positive_low": share["low"],
            "would_have_passed": (
                None if dropped_at is None else bool(share["low"] <= float(dropped_at))
            ),
        },
        "n_decades": batch.n_decades,
    }


# --------------------------------------------------------------------------- #
# R1 and R2 -- byte-frozen, imported from the round-two judge files
# --------------------------------------------------------------------------- #


def judge_r1(sealed: dict[str, Any], grid: list[float], run: dict[str, Any]) -> dict[str, Any]:
    """R1 -- severity still bites the book (the b3 over-commitment grid).

    Delegates to ``scripts/spine_pilot_b3._judge`` with the b3 block carried
    byte-verbatim from ``spine02-prereg.json``. Nothing is re-implemented and no
    threshold is re-derived: this wrapper only locates the frozen bar block.
    """
    return _judge_b3(sealed["carried"]["b3"], grid, run)


def judge_r2(ens: Any, source: Any, sealed: dict[str, Any]) -> dict[str, Any]:
    """R2 -- eras don't teleport at the seams (the b2 era-coherence bar).

    Delegates to ``scripts/spine_pilot_report.judge_b2`` with the b2 block
    carried byte-verbatim from ``spine02-prereg.json``.
    """
    return _judge_b2(ens, source, sealed["carried"]["b2"])


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #


ANCHORS_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-anchors.json"


def sealed_from_anchors(
    anchors_path: Path | None = None, spine02_path: Path | None = None
) -> dict[str, Any]:
    """Assemble the judge-readable threshold block from its two sources.

    There is exactly ONE assembly path and this is it: the seal script calls
    this function to build what it writes, and the anti-test sweeps call it to
    build what they judge with, so a sweep can never be run against a different
    set of numbers from the ones that get sealed. Nothing is retyped -- the bars
    and parameters are loaded whole from the anchors file (where each threshold
    is derived from the measurement it is cut from), and R1/R2's bars are loaded
    whole from the round-two seal.
    """
    anchors = json.loads((anchors_path or ANCHORS_PATH).read_text(encoding="utf-8"))
    spine02 = json.loads((spine02_path or SPINE02_SEAL_PATH).read_text(encoding="utf-8"))
    return {
        "bars": anchors["exam_bars"],
        "parameters": anchors["judge_parameters"],
        "carried": {"b2": spine02["b2"], "b3": spine02["b3"]},
    }


def load_sealed(path: Path | None = None) -> dict[str, Any]:
    """The sealed pre-registration. Read-only; nothing here ever writes it."""
    return json.loads((path or SEALED_PATH).read_text(encoding="utf-8"))


def judge_all(batch: Batch, sealed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every bar this module can judge from a generated batch alone.

    R1 and R2 are NOT included: they need an ensemble and the panel source
    rather than a batch of decades, and their callers hand those in directly.
    """
    return {
        "T1": judge_t1(batch, sealed),
        "O1": judge_o1(batch, sealed),
        "D1": judge_d1(batch, sealed),
        "D2": judge_d2(batch, sealed),
        "D3": judge_d3(batch, sealed),
        "D4": judge_d4(batch, sealed),
        "A1": judge_a1(batch, sealed),
        "A2": judge_a2(batch, sealed),
    }
