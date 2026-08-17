"""The spine v2 exam's judges, tested on hand-built batches.

Self-contained by design: nothing here reads the catalog, draws an ensemble or
touches the network, and the only repository files it opens are the two
committed JSONs the threshold block is assembled from. The judges themselves are
loaded from ``scripts/spine_v2_report.py`` by file path, the
``tests/test_gen_spine.py`` fixture pattern (``importlib`` rather than
``sys.path`` + ``import``, which pyright's static resolver cannot see).

Every expected value below is computed by hand from the exam's stated definition
and written as a literal -- never re-derived from the implementation -- so a
judge that silently changed its formula would fail here rather than agree with
itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> Any:
    path = _REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: ``spine_v2_report`` uses ``from __future__ import
    # annotations`` on a dataclass, and dataclasses resolve a string annotation
    # through ``sys.modules[cls.__module__]`` -- which fails with a bare
    # AttributeError if the module was never registered.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report() -> Any:
    return _load("spine_v2_report")


@pytest.fixture(scope="module")
def grader() -> Any:
    return _load("spine_v2_grader")


@pytest.fixture(scope="module")
def sealed(report: Any) -> dict[str, Any]:
    return report.sealed_from_anchors()


# --------------------------------------------------------------------------- #
# grader_v2 -- the mapping fix
# --------------------------------------------------------------------------- #


def test_grader_v2_differs_from_the_incumbent_only_on_stag(grader: Any) -> None:
    """The owner's ruling is one cell wide. A month labelled STAG moves onto the
    contracting side; every other label classifies exactly as
    ``ah.gen.spine.panel_quadrant`` classifies it."""
    from ah.gen.spine import QUADRANTS

    labels = np.array(["EXP", "REC", "CRI", "STAG", "SLOW", "REF", "STAG"], dtype=object)
    yoy = np.array([5.0, 1.0, 5.0, 5.0, 1.0, 5.0, 1.0])
    threshold = 3.0

    v2 = grader.season_cells(labels, yoy, threshold)
    incumbent = grader.season_cells(
        labels, yoy, threshold, contracting_labels=grader.INCUMBENT_CONTRACTING_LABELS
    )

    # hand-computed: (expanding << 1) | hot, QUADRANTS =
    # (recession, stagflation, recovery, expansion)
    assert [QUADRANTS[c] for c in v2] == [
        "expansion",  # EXP, hot
        "recession",  # REC, cool
        "stagflation",  # CRI, hot
        "stagflation",  # STAG, hot -- the fix
        "recovery",  # SLOW, cool
        "expansion",  # REF, hot
        "recession",  # STAG, cool -- the cell a cool STAG month would land in
    ]
    differs = [i for i in range(labels.size) if v2[i] != incumbent[i]]
    assert differs == [3, 6]
    assert all(labels[i] == "STAG" for i in differs)


def test_completed_spells_drops_the_opening_and_closing_runs(grader: Any) -> None:
    """The censoring rule: a run that opens or closes the window has an unknown
    true length. Here recession runs 3 months at the open (dropped), 2 in the
    middle (kept) and 4 at the close (dropped)."""
    cells = np.array([0, 0, 0, 2, 2, 0, 0, 2, 0, 0, 0, 0], dtype=np.int8)
    spells = grader.completed_spells(cells)
    assert spells[0] == [2]  # recession: only the interior run
    assert spells[2] == [2, 1]  # recovery: both its runs are interior


def test_clockwise_counts_uses_the_sealed_ordering(grader: Any) -> None:
    """recovery -> expansion -> stagflation -> recession -> recovery is clockwise;
    anything else is not. Codes: recession 0, stagflation 1, recovery 2,
    expansion 3."""
    cells = np.array([2, 3, 1, 0, 2, 1], dtype=np.int8)
    total, clockwise = grader.clockwise_counts(cells)
    assert (total, clockwise) == (5, 4)  # only 2 -> 1 (recovery -> stagflation) is not


# --------------------------------------------------------------------------- #
# batch builders for the judges
# --------------------------------------------------------------------------- #


def _decade(report: Any, *, labels, yoy, tight=None, eq=None, bd=None, cm=None) -> Any:
    n = len(labels)
    zeros = np.zeros(n)
    return report.Decade(
        labels=np.asarray(labels, dtype=object),
        yoy=np.asarray(yoy, dtype=np.float64),
        tight=np.zeros(n, dtype=bool) if tight is None else np.asarray(tight, dtype=bool),
        equities=zeros if eq is None else np.asarray(eq, dtype=np.float64),
        bonds=zeros if bd is None else np.asarray(bd, dtype=np.float64),
        commodities=zeros if cm is None else np.asarray(cm, dtype=np.float64),
    )


def _seasoned_decade(report: Any, sealed: dict[str, Any], seasons: list[int]) -> Any:
    """A decade whose season per month is exactly ``seasons`` -- built by choosing
    a label and an inflation reading that land the month in that cell."""
    era = float(sealed["parameters"]["era_threshold_pp"])
    label_for = {0: "REC", 1: "STAG", 2: "EXP", 3: "EXP"}
    hot_for = {0: False, 1: True, 2: False, 3: True}
    labels = [label_for[s] for s in seasons]
    yoy = [era + 2.0 if hot_for[s] else era - 2.0 for s in seasons]
    return _decade(report, labels=labels, yoy=yoy)


# --------------------------------------------------------------------------- #
# the judges
# --------------------------------------------------------------------------- #


def test_judge_d_pools_the_batch_rather_than_averaging_decade_medians(
    report: Any, sealed: dict[str, Any]
) -> None:
    """The owner's pooled-spells ruling, as a bite-proof.

    Two decades carry three 2-month recoveries each and a third carries seven
    9-month ones, so the per-decade recovery medians are 2, 2 and 9 -- their
    median is 2 and their mean 4.33 -- while the pooled multiset is
    [2]x6 + [9]x7, whose median is 9. Only a judge that actually pools the batch
    reports 9, and only that answer makes the verdict a FAIL against D3's [2, 8]
    band. A judge that averaged decade medians would pass this batch.
    """

    def decade(spell_len: int, n_spells: int) -> Any:
        seasons: list[int] = [2] * 0
        seasons.extend([3] * 2)  # an opening spell, censored by the rule
        for _ in range(n_spells):
            seasons.extend([2] * spell_len)
            seasons.extend([3] * 2)
        seasons.extend([3] * 2)  # a closing spell, censored
        return _seasoned_decade(report, sealed, seasons)

    batch = report.Batch((decade(2, 3), decade(2, 3), decade(9, 7)))
    verdict = report.judge_d(batch, sealed, "D3")

    assert verdict["n_pooled_spells"] == 13
    assert verdict["value"] == 9.0  # pooled median; a median-of-medians would be 2
    assert verdict["pass"] is False  # D3's band is [2, 8]


def test_judge_o1_pools_transitions_and_never_crosses_a_decade_edge(
    report: Any, sealed: dict[str, Any]
) -> None:
    """Two decades, each ending in recession and beginning in recovery. The
    pooled count must be the sum of the within-decade transitions -- a judge that
    concatenated the batch would invent one extra transition per join."""
    seasons = [2, 2, 3, 3, 1, 1, 0, 0]  # recovery -> expansion -> stagflation -> recession
    batch = report.Batch(
        (_seasoned_decade(report, sealed, seasons), _seasoned_decade(report, sealed, seasons))
    )
    verdict = report.judge_o1(batch, sealed)
    assert verdict["n_transitions"] == 6  # 3 per decade, no cross-decade pair
    assert verdict["n_clockwise"] == 6
    assert verdict["value"] == 1.0
    assert verdict["pass"] is True


def test_judge_t1_lift_arithmetic(report: Any, sealed: dict[str, Any]) -> None:
    """A 40-month decade with a hand-countable answer.

    Months 0-11 have no trailing inflation (the warm-up) and months 28-39 have no
    full 12-month lookahead, so the eligible set is months 12-27: sixteen months.
    Four of them (12-15) are tight. A single downturn onset sits at month 20, so
    every eligible month in 8..19 is "followed" -- inside the eligible set that is
    months 12-19, eight of sixteen. All four tight months are among them.
    lift = (4/4) / (8/16) = 2.0.
    """
    n = 40
    labels = ["EXP"] * n
    labels[20] = "REC"
    labels[21] = "REC"
    yoy = [float("nan")] * 12 + [1.0] * (n - 12)
    tight = [False] * n
    for t in range(12, 16):
        tight[t] = True
    batch = report.Batch((_decade(report, labels=labels, yoy=yoy, tight=tight),))
    verdict = report.judge_t1(batch, sealed)

    assert verdict["eligible_months"] == 16
    assert verdict["tight_months"] == 4
    assert verdict["conditional_rate"] == 1.0
    assert verdict["unconditional_rate"] == 0.5
    assert verdict["value"] == 2.0
    assert verdict["pass"] is True  # inside the sealed band [1.7753, 3.3474]


def test_judge_a1_is_directional_and_reports_both_spreads(
    report: Any, sealed: dict[str, Any]
) -> None:
    """Twelve warm-up months, then twelve high-inflation and twelve low-inflation
    months. Commodities beat bonds by 1%/month when inflation is high and by
    0.1%/month when it is not: 12 pp vs 1.2 pp annualised."""
    n = 36
    yoy = [float("nan")] * 12 + [5.0] * 12 + [1.0] * 12
    cm = [0.0] * 12 + [0.01] * 12 + [0.001] * 12
    bd = [0.0] * n
    batch = report.Batch((_decade(report, labels=["EXP"] * n, yoy=yoy, cm=cm, bd=bd),))
    verdict = report.judge_a1(batch, sealed)

    assert verdict["months_high"] == 12
    assert verdict["months_low"] == 12
    assert verdict["spread_high_pp"] == pytest.approx(12.0)
    assert verdict["spread_low_pp"] == pytest.approx(1.2)
    assert verdict["directional_pass"] is True
    assert verdict["containment_pass"] is True
    assert verdict["pass"] is True

    # the same decade with the sign of the effect reversed must fail
    flipped = _decade(
        report, labels=["EXP"] * n, yoy=yoy, cm=[0.0] * 12 + [0.001] * 12 + [0.01] * 12, bd=bd
    )
    assert report.judge_a1(report.Batch((flipped,)), sealed)["pass"] is False


def test_judge_a2_reports_the_dropped_ceiling_without_judging_it(
    report: Any, sealed: dict[str, Any]
) -> None:
    """The owner dropped A2's low-inflation share ceiling. The statistic must
    still be computed and reported, and it must not enter the verdict."""
    rng = np.random.Generator(np.random.PCG64(4242))
    n = 240
    yoy = np.concatenate([np.full(12, np.nan), np.full(114, 1.0), np.full(114, 6.0)])
    eq = rng.normal(0.0, 0.04, n)
    noise = rng.normal(0.0, 0.02, n)
    high = yoy >= 4.0
    bonds = np.where(high, 0.9 * (eq * 0.5) + 0.1 * noise, -0.9 * (eq * 0.5) + 0.1 * noise)
    batch = report.Batch((_decade(report, labels=["EXP"] * n, yoy=yoy, eq=eq, bd=bonds),))
    verdict = report.judge_a2(batch, sealed)

    assert verdict["correlation_high"] > 0.0
    assert verdict["correlation_low"] < 0.0
    assert verdict["pass"] is True
    disclosure = verdict["dropped_ceiling_disclosure"]
    assert disclosure["judged"] is False
    assert disclosure["would_have_been_judged_at"] == 0.65
    assert disclosure["share_positive_low"] == verdict["share_positive_low"]


def test_the_sealed_block_carries_no_low_inflation_ceiling(sealed: dict[str, Any]) -> None:
    assert sealed["bars"]["A2_share_low_ceiling"] is None
    assert sealed["bars"]["A2_share_low_ceiling_dropped_value"] == 0.65


def test_r1_and_r2_are_the_frozen_round_two_functions(report: Any) -> None:
    """R1 and R2 must BE the prior round's judges, not copies of them: the exam
    attributes any change in their verdicts to the engine, which only holds if
    the code is identical. Identity, not equality of behaviour, is the check."""
    pilot_report = _load("spine_pilot_report")
    pilot_b3 = _load("spine_pilot_b3")
    # loaded twice by path, so compare by qualified name and source file rather
    # than by object identity across two module instances
    assert report._judge_b2.__qualname__ == pilot_report.judge_b2.__qualname__
    assert report._judge_b2.__code__.co_code == pilot_report.judge_b2.__code__.co_code
    assert report._judge_b3.__code__.co_code == pilot_b3._judge.__code__.co_code


def test_r1_and_r2_read_their_bars_from_the_round_two_seal(
    report: Any, sealed: dict[str, Any]
) -> None:
    import json

    spine02 = json.loads(
        (_REPO_ROOT / "docs" / "superpowers" / "specs" / "spine02-prereg.json").read_text(
            encoding="utf-8"
        )
    )
    assert sealed["carried"]["b2"] == spine02["b2"]
    assert sealed["carried"]["b3"] == spine02["b3"]
    assert sealed["carried"]["b2"]["join_yoy_max_pp"] == 2.5
    assert sealed["carried"]["b3"]["n_seeds"] == 20
