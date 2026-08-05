# Private-Programme Console Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a private-programme section to `ah credibility` that shows the cashflow model, the commitment pacing ladder, and — explicitly — how the market environment drives the cashflows.

**Architecture:** A new pure module `src/ah/programme.py` computes the report and renders its own self-contained HTML fragment; `ah/credibility.py` embeds the fragment in its existing page. `ah/play.py` gains record-only fields on `PlayQuarter` and a `linkage` switch so the diagnostic can read the market states and compare against a linkage-off counterfactual.

**Tech Stack:** Python 3.12, numpy, dataclasses, inline SVG (no JS, no external assets), pytest.

**Design spec:** `docs/superpowers/specs/2026-08-04-cashflow-pacing-view-design.md`

## Building a world in a test — the verified idiom

There is **no `ah.presets` module and no `build_preset` helper**; presets are
JSON files under `src/ah/presets/`. Every test in this plan opens with this
block, copied from `tests/test_credibility.py`:

```python
import json
from pathlib import Path

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
SEED = 771204


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))
```

The four preset names are exactly `stagflation`, `goldilocks`,
`deflation_bust`, `reflation_boom` — note `reflation_boom`, not `reflation`.

## Global Constraints

- **Admin only.** The module writes nothing, is not in the pre-registration seal, never touches the scored path, and no number it computes reaches a player.
- **Determinism.** Same world + same seed → byte-identical output. No RNG in this module; all paths come from `base_seed + 7919*k`.
- **No network.** `pytest-socket` blocks it; never add a fetch.
- **No pandas** anywhere near `ah/core`; this module uses numpy only.
- **CLI-echoed strings stay ASCII** (Windows console is cp1252). HTML file content may use Unicode freely.
- **`src/ah/cli.py` must not gain `from __future__ import annotations`** — Typer resolves hints at runtime.
- **Do not edit `schemas/`** — read-only vendored truth.
- **Do not bump** `PLAY_ALPHA_VERSION` or `ah.eval.decision_metrics.DECISION_ALPHA_VERSION`.
- Every task ends: `uv run ruff check . --fix`, `uv run ruff format .`, `uv run pyright` clean before commit.
- Branch: `programme-view-spec` (already created and holding the spec commit). One WP, one branch; `--no-ff` merge to `main` only when the full gate is green.

**Deviation from the spec, recorded here:** the spec says `PlayQuarter` gains *four* fields. Building the per-vintage NAV stack and the ladder's committed column needs **six**: the four linkage/state fields plus `vintage_nav` and `new_commitments`. Both additions are records of values `simulate_play` already computes and discards, so the "no arithmetic changes" guarantee is unaffected. Flag this in the CHANGELOG.

---

### Task 1: Expose the market linkage on `PlayQuarter`, and add the linkage switch

**Files:**
- Modify: `src/ah/play.py:129-144` (the `PlayQuarter` dataclass), `src/ah/play.py:293-399` (`simulate_play`)
- Test: `tests/test_play_linkage.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `PlayQuarter` with six new fields — `drawdown_depth: float`, `spread_ratio: float`, `f_dist: float`, `f_call: float`, `new_commitments: float`, `vintage_nav: dict[str, float]`; and `simulate_play(paths, decisions=None, *, use_reported=True, policy=None, linkage=True) -> PlayResult`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_play_linkage.py`:

```python
"""The market linkage, exposed and switchable (programme console, task 1).

``simulate_play`` computed the two continuous states tier 1 consumes and threw
them away, and had no way to run without the linkage — so nothing could show
what the market environment actually did to the cashflows. Both are now
records on the quarter and a keyword, with the default byte-identical to what
shipped.
"""

from __future__ import annotations

import numpy as np

from ah.core.engine import run_path
from ah.play import PRIVATE_ASSETS, simulate_play

import json
from pathlib import Path

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


def _paths():
    world = _world("stagflation")
    return run_path(world, 771204)


def test_quarters_carry_the_states_the_linkage_consumes():
    result = simulate_play(_paths())
    q = result.quarters[0]
    assert q.drawdown_depth >= 0.0
    assert q.spread_ratio > 0.0
    # the frozen artifact's bounds: f_dist clips to [0.3, 1.5], f_call to [0.5, 1.2]
    for quarter in result.quarters:
        assert 0.3 <= quarter.f_dist <= 1.5
        assert 0.5 <= quarter.f_call <= 1.2


def test_linkage_off_pins_both_multipliers_to_one():
    """Linkage off IS tier 0's recursion — the sealed 'one model' identity."""
    result = simulate_play(_paths(), linkage=False)
    assert all(q.f_dist == 1.0 for q in result.quarters)
    assert all(q.f_call == 1.0 for q in result.quarters)


def test_linkage_changes_the_distributions_it_is_supposed_to_change():
    linked = simulate_play(_paths())
    unlinked = simulate_play(_paths(), linkage=False)
    a = sum(q.distributions_received for q in linked.quarters)
    b = sum(q.distributions_received for q in unlinked.quarters)
    assert a != b, "the linkage must move distributions or it is not doing anything"


def test_default_run_is_unchanged_by_these_additions():
    """The additive fields and the new keyword must be inert on the scored path.

    Pinned against values recorded from the pre-change implementation, so a
    later edit that quietly moves a scored number fails here.
    """
    result = simulate_play(_paths())
    assert len(result.quarters) == 40
    assert result.final_value == FINAL_VALUE_BEFORE_CHANGE
    assert result.forced_secondaries == FORCED_SECONDARIES_BEFORE_CHANGE


def test_new_commitments_land_once_a_year_after_the_first():
    result = simulate_play(_paths())
    committing = [q.quarter for q in result.quarters if q.new_commitments > 0.0]
    assert committing == [4, 8, 12, 16, 20, 24, 28, 32, 36]


def test_vintage_nav_covers_every_private_sleeve_and_sums_to_private_nav():
    result = simulate_play(_paths())
    last = result.quarters[-1]
    assert last.vintage_nav, "the per-vintage stack must be populated"
    for key in last.vintage_nav:
        assert key.split("-")[0] in PRIVATE_ASSETS
    total = sum(last.vintage_nav.values())
    expected = last.private_weight_true * last.nav_true
    assert np.isclose(total, expected, rtol=1e-6)
```

- [ ] **Step 2: Record the two pre-change constants the inertness test needs**

Before touching `play.py`, capture the current values and paste them into the test, replacing `FINAL_VALUE_BEFORE_CHANGE` and `FORCED_SECONDARIES_BEFORE_CHANGE` with literals:

```bash
uv run python -c "import json; from pathlib import Path; from ah.core.numericworld import project_numeric; from ah.core.worldspec import WorldSpec; from ah.core.engine import run_path; from ah.play import simulate_play; d=json.loads(Path('src/ah/presets/stagflation.json').read_text(encoding='utf-8')); w=project_numeric(WorldSpec.model_validate(d)); r=simulate_play(run_path(w, 771204)); print(repr(r.final_value), r.forced_secondaries)"
```

Paste the two printed values in as literals. If the run raises, the preset
path is wrong — check `ls src/ah/presets/` before changing anything else.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_play_linkage.py -v`
Expected: FAIL — `PlayQuarter` has no attribute `drawdown_depth`; `simulate_play() got an unexpected keyword argument 'linkage'`.

- [ ] **Step 4: Add the fields to `PlayQuarter`**

In `src/ah/play.py`, extend the dataclass (keep it frozen; `field` is already imported):

```python
@dataclass(frozen=True)
class PlayQuarter:
    """One quarter of the institution's life, as the player could see it."""

    quarter: int
    month: int  # the month the quarter closes on
    cash: float
    nav_true: float
    nav_reported: float
    calls_paid: float
    distributions_received: float
    spending_paid: float
    forced_sale_total: float
    private_weight_true: float
    unfunded_total: float
    #: The two CONTINUOUS market states tier 1's linkage consumes, and the
    #: multipliers they produced. Records only — computed here already, and
    #: discarded until the credibility console needed to show the mechanism.
    #: No regime label reaches the linkage (DN-5 Delta 3, structural).
    drawdown_depth: float = 0.0
    spread_ratio: float = 1.0
    f_dist: float = 1.0
    f_call: float = 1.0
    #: New commitments made into the ladder this quarter (the pacing plan).
    new_commitments: float = 0.0
    #: NAV by cohort id at quarter close, for the per-vintage stack.
    vintage_nav: dict[str, float] = field(default_factory=dict)
```

- [ ] **Step 5: Add the `linkage` keyword and populate the fields**

In `simulate_play`, change the signature:

```python
def simulate_play(
    paths: EnginePaths,
    decisions: dict[int, str] | None = None,
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
    linkage: bool = True,
) -> PlayResult:
```

Extend the docstring with one line:

```
    ``linkage=False`` runs the SAME recursion with ``f_call = f_dist = 1`` —
    tier 0's benchmark, the sealed "one model, linkage on or off" identity.
    It exists for the credibility console's counterfactual and is never used
    on the scored path.
```

Inside the quarter loop, replace the commitment block and the cohort stepping so the values are captured. The existing block at `src/ah/play.py:346-366` becomes:

```python
        # the pacing plan: a new vintage every year, in every private sleeve
        committed_this_quarter = 0.0
        if q > 0 and q % _COMMITMENT_QUARTERS == 0:
            for asset in PRIVATE_ASSETS:
                _commit_new_vintage(portfolio, ladders, base_doc, asset, q // 4)
                committed_this_quarter += START_TARGETS[asset] * _ANNUAL_COMMITMENT_RATE

        calls = 0.0
        distributions = 0.0
        dd = float(depth[q])
        sr = float(spread_ratio[q])
        fc = tier1_f_call(dd) if linkage else 1.0
        fd = tier1_f_dist(dd, sr) if linkage else 1.0
        vintage_nav: dict[str, float] = {}
        for asset in PRIVATE_ASSETS:
            for cohort in ladders[asset]:
                step = cohort.step(
                    float(q_returns[asset][q]),
                    f_call=fc,
                    f_dist=fd,
                )
                calls += step.call
                distributions += step.distribution_total
                # the reported mark follows the tape the player is shown
                grown = cohort.nav_reported * (1.0 + float(q_reported[asset][q]))
                cohort.report(max(0.0, grown + step.call - step.distribution_total))
                vintage_nav[cohort.contract.identity.cohort_id] = cohort.nav_true
```

Then extend the `PlayQuarter(...)` construction with the six new keywords:

```python
                drawdown_depth=dd,
                spread_ratio=sr,
                f_dist=fd,
                f_call=fc,
                new_commitments=committed_this_quarter,
                vintage_nav=vintage_nav,
```

Note: `vintage_nav` is populated **before** `engine.run_quarter`, so a forced secondary in that quarter reduces cohort NAV after the snapshot. That is deliberate and must be stated in the field's comment — the stack shows the programme's own NAV, and the forced-sale block shows what liquidity did to it. `cohort.contract.identity.cohort_id` is the correct accessor — verified against `ClosedEndIdentity` in `src/ah/core/sleevestate.py:87-92`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_play_linkage.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 7: Prove the bundle and the scored path did not move**

Run: `uv run pytest tests/test_bundle.py tests/test_play.py tests/test_serve.py -v`
Expected: PASS. `app/fixtures/toy.bundle.gz` is a committed bundle both suites verify; if any digest or ledger assertion fails, the additions were **not** inert — stop and find out why rather than regenerating the fixture.

- [ ] **Step 8: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/play.py tests/test_play_linkage.py
git commit -m "feat: expose the market linkage on PlayQuarter, and a linkage switch

The two continuous states tier 1 consumes (equity drawdown depth, spread
ratio) were computed inside simulate_play and discarded, so nothing could
show what the market environment did to the cashflows. They are now
records on the quarter alongside the f_dist/f_call multipliers they
produced, with new_commitments and vintage_nav for the pacing ladder.

simulate_play gains linkage: bool = True. Off, it drives f_call = f_dist
= 1, which is tier 0's recursion - the sealed one-model identity - and
gives the credibility console a counterfactual to price the linkage
against. Never used on the scored path.

Additive only: no arithmetic changes, PLAY_ALPHA_VERSION unchanged, and
the committed toy bundle verifies unmoved."
```

---

### Task 2: The programme report — per-quarter series, the ladder, the counterfactual

**Files:**
- Create: `src/ah/programme.py`
- Test: `tests/test_programme.py` (create)

**Interfaces:**
- Consumes: `PlayQuarter`'s six new fields and `simulate_play(..., linkage=...)` from Task 1.
- Produces:
  - `ProgrammeQuarter` (frozen dataclass): `quarter, month, drawdown_depth, spread_ratio, f_dist, f_call, calls, distributions, distributions_unlinked, cash, nav_true, nav_reported, private_nav, unfunded, private_weight_true, coverage_true, coverage_reported, forced_sale_total`
  - `LadderYear` (frozen dataclass): `year, committed, called, distributed, net, called_to_date, unfunded_end, private_nav_end`
  - `programme_quarters(linked: PlayResult, unlinked: PlayResult) -> list[ProgrammeQuarter]`
  - `ladder_years(quarters: list[ProgrammeQuarter], linked: PlayResult) -> list[LadderYear]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_programme.py`:

```python
"""The private-programme diagnostic (credibility console section).

Arithmetic is checked against numbers computed by hand, never against the
module's own output.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.core.engine import run_path
from ah.play import simulate_play
from ah.programme import ladder_years, programme_quarters

import json
from pathlib import Path

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


@pytest.fixture(scope="module")
def runs():
    paths = run_path(_world("stagflation"), 771204)
    return simulate_play(paths), simulate_play(paths, linkage=False)


def test_quarters_pair_linked_and_unlinked_distributions(runs):
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    assert len(rows) == len(linked.quarters)
    assert rows[3].distributions == linked.quarters[3].distributions_received
    assert rows[3].distributions_unlinked == unlinked.quarters[3].distributions_received


def test_coverage_is_unfunded_over_assets_on_both_bases(runs):
    linked, unlinked = runs
    row = programme_quarters(linked, unlinked)[10]
    q = linked.quarters[10]
    assert np.isclose(row.coverage_true, q.unfunded_total / q.nav_true)
    assert np.isclose(row.coverage_reported, q.unfunded_total / q.nav_reported)


def test_private_nav_is_weight_times_total(runs):
    linked, unlinked = runs
    row = programme_quarters(linked, unlinked)[10]
    q = linked.quarters[10]
    assert np.isclose(row.private_nav, q.private_weight_true * q.nav_true)


def test_ladder_aggregates_four_quarters_into_each_year(runs):
    linked, unlinked = runs
    rows = programme_quarters(linked, unlinked)
    years = ladder_years(rows, linked)
    assert len(years) == 10
    hand_called = sum(r.calls for r in rows[4:8])
    assert np.isclose(years[1].called, hand_called)
    hand_net = sum(r.distributions - r.calls for r in rows[4:8])
    assert np.isclose(years[1].net, hand_net)


def test_ladder_year_zero_commits_nothing_and_later_years_do(runs):
    linked, unlinked = runs
    years = ladder_years(programme_quarters(linked, unlinked), linked)
    assert years[0].committed == 0.0
    assert years[1].committed > 0.0


def test_called_to_date_is_cumulative(runs):
    linked, unlinked = runs
    years = ladder_years(programme_quarters(linked, unlinked), linked)
    assert np.isclose(years[2].called_to_date, years[0].called + years[1].called + years[2].called)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_programme.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ah.programme'`.

- [ ] **Step 3: Create the module with the two dataclasses and the two builders**

Create `src/ah/programme.py`:

```python
"""The private-programme section of the credibility console.

The commitment lever is the next thing the product needs, and nobody has
looked at what the pacing model does. ``ah/port/`` runs a real cohort
recursion and ``ah/play.py`` runs a ladder — a new vintage every year in every
private sleeve — and both are correct as far as any test goes without anyone
having seen their shape.

This module puts that shape on a page, with the market linkage first-class:
the two continuous states tier 1 consumes, the multipliers they produce, and
what the distributions would have been on the same tape with the linkage off.
The asymmetry it exists to show is that ``f_call`` is bounded near-flat while
``f_dist`` can reach its floor — calls keep coming while distributions stop,
and that is what empties the cash account.

Admin tooling, on the credibility console's contract: reads worlds, writes
nothing, not in the pre-registration seal, never touches the scored path, and
no number here reaches a player. Deterministic — same world, same seed, same
bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from ah.play import PlayResult

__all__ = [
    "LadderYear",
    "ProgrammeQuarter",
    "ladder_years",
    "programme_quarters",
]

_QUARTERS_PER_YEAR = 4


@dataclass(frozen=True)
class ProgrammeQuarter:
    """One quarter of the programme, with the market state that drove it."""

    quarter: int
    month: int
    drawdown_depth: float
    spread_ratio: float
    f_dist: float
    f_call: float
    calls: float
    distributions: float
    distributions_unlinked: float
    cash: float
    nav_true: float
    nav_reported: float
    private_nav: float
    unfunded: float
    private_weight_true: float
    coverage_true: float
    coverage_reported: float
    forced_sale_total: float


@dataclass(frozen=True)
class LadderYear:
    """One year of the commitment pacing plan."""

    year: int
    committed: float
    called: float
    distributed: float
    net: float
    called_to_date: float
    unfunded_end: float
    private_nav_end: float


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Coverage on a wiped-out book is infinite, matching the port layer.

    CORRECTED IN REVIEW (owner ruling, 2026-08-04): this originally returned
    0.0, which contradicted the convention this codebase already has for the
    same quantity — ``Portfolio.coverage_true``/``coverage_reported``
    (``ah/port/portfolio.py``) return ``float("inf")`` when NAV <= 0, and
    ``QuarterReport.coverage_true`` is computed through them. An institution
    with unfunded obligations and no assets is infinitely uncovered, not
    perfectly covered, and 0.0 would have made a wipeout render as the
    healthiest book on the page — on a page whose whole job is catching
    exactly that kind of lie. The renderer (Task 5) must show it distinctly
    rather than printing the string "inf".
    """
    return numerator / denominator if denominator > 0.0 else float("inf")


def programme_quarters(linked: PlayResult, unlinked: PlayResult) -> list[ProgrammeQuarter]:
    """Pair the linked run with its linkage-off counterfactual, quarter by quarter."""
    rows: list[ProgrammeQuarter] = []
    for q, u in zip(linked.quarters, unlinked.quarters, strict=True):
        private_nav = q.private_weight_true * q.nav_true
        rows.append(
            ProgrammeQuarter(
                quarter=q.quarter,
                month=q.month,
                drawdown_depth=q.drawdown_depth,
                spread_ratio=q.spread_ratio,
                f_dist=q.f_dist,
                f_call=q.f_call,
                calls=q.calls_paid,
                distributions=q.distributions_received,
                distributions_unlinked=u.distributions_received,
                cash=q.cash,
                nav_true=q.nav_true,
                nav_reported=q.nav_reported,
                private_nav=private_nav,
                unfunded=q.unfunded_total,
                private_weight_true=q.private_weight_true,
                coverage_true=_safe_ratio(q.unfunded_total, q.nav_true),
                coverage_reported=_safe_ratio(q.unfunded_total, q.nav_reported),
                forced_sale_total=q.forced_sale_total,
            )
        )
    return rows


def ladder_years(quarters: list[ProgrammeQuarter], linked: PlayResult) -> list[LadderYear]:
    """Aggregate the quarterly programme into the pacing plan's own unit: years."""
    years: list[LadderYear] = []
    running_called = 0.0
    for start in range(0, len(quarters), _QUARTERS_PER_YEAR):
        block = quarters[start : start + _QUARTERS_PER_YEAR]
        if not block:
            continue
        source = linked.quarters[start : start + _QUARTERS_PER_YEAR]
        called = sum(r.calls for r in block)
        distributed = sum(r.distributions for r in block)
        running_called += called
        years.append(
            LadderYear(
                year=start // _QUARTERS_PER_YEAR,
                committed=sum(q.new_commitments for q in source),
                called=called,
                distributed=distributed,
                net=distributed - called,
                called_to_date=running_called,
                unfunded_end=block[-1].unfunded,
                private_nav_end=block[-1].private_nav,
            )
        )
    return years
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_programme.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/programme.py tests/test_programme.py
git commit -m "feat: the programme's quarterly series and pacing ladder

programme_quarters pairs the linked run with its linkage-off
counterfactual so the market's effect on distributions is a difference,
not a claim. ladder_years aggregates into the pacing plan's own unit."
```

---

### Task 3: The statistics and the declared plausible bands

**Files:**
- Modify: `src/ah/programme.py`
- Test: `tests/test_programme_stats.py` (create)

**Interfaces:**
- Consumes: `ProgrammeQuarter`, `LadderYear` from Task 2.
- Produces:
  - `Band` (frozen dataclass): `lo: float`, `hi: float`, `question: str`
  - `PROGRAMME_PLAUSIBLE: dict[str, Band]`
  - `ProgrammeStat` (frozen dataclass): `name, median, p10, p90, path0, band, flagged`
  - `vintage_stats(paths_drawdown, paths_spread, quarters_available) -> dict[str, float]` — the single-cohort statistics via `run_tier1`
  - `programme_stats(per_path: list[dict[str, float]], path0: dict[str, float]) -> list[ProgrammeStat]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_programme_stats.py`:

```python
"""Declared bands and the statistics they judge.

The bands are one allocator's priors, editable by design — these tests pin the
ARITHMETIC, never the priors, so re-declaring a band never breaks a test.
"""

from __future__ import annotations

import numpy as np

from ah.programme import (
    PROGRAMME_PLAUSIBLE,
    Band,
    programme_stats,
    vintage_stats,
)


def test_every_band_has_a_question_and_a_valid_range():
    assert PROGRAMME_PLAUSIBLE
    for name, band in PROGRAMME_PLAUSIBLE.items():
        assert band.lo < band.hi, name
        assert band.question.strip(), name


def test_stats_flag_only_outside_the_band():
    per_path = [{"dpi_age9": v} for v in (0.9, 1.0, 1.1)]
    stats = programme_stats(per_path, {"dpi_age9": 1.0})
    dpi = next(s for s in stats if s.name == "dpi_age9")
    assert not dpi.flagged
    per_path = [{"dpi_age9": v} for v in (0.1, 0.2, 0.3)]
    stats = programme_stats(per_path, {"dpi_age9": 0.2})
    dpi = next(s for s in stats if s.name == "dpi_age9")
    assert dpi.flagged


def test_stats_report_median_and_the_ten_ninety_spread():
    per_path = [{"dpi_age9": float(v)} for v in range(11)]  # 0..10, median 5
    stats = programme_stats(per_path, {"dpi_age9": 3.0})
    dpi = next(s for s in stats if s.name == "dpi_age9")
    assert dpi.median == 5.0
    assert dpi.p10 == 1.0
    assert dpi.p90 == 9.0
    assert dpi.path0 == 3.0


def test_a_missing_statistic_does_not_crash_the_report():
    """A world too short to define a statistic omits it rather than raising."""
    stats = programme_stats([{}, {}], {})
    assert stats == []


def test_vintage_stats_on_a_calm_tape_are_hand_checkable():
    """36 quarters of flat 0% returns and no stress: the linkage is 1.0
    throughout, so this is tier 0's recursion and the numbers follow the
    frozen curves alone."""
    n = 36
    calm_dd = np.zeros(n)
    calm_spread = np.ones(n)
    out = vintage_stats(calm_dd, calm_spread, n)
    # rc_curve[0] = 0.25 annual on unfunded, quarterly => 6.25% of 1.0 committed
    assert np.isclose(out["first_call"], 0.0625, rtol=1e-6)
    # DPI is cumulative distributions over paid-in; both positive on a calm tape
    assert out["dpi_age9"] > 0.0
    assert 0.0 < out["call_rate_y1_3"] < 1.0
    assert out["crossover_years"] > 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_programme_stats.py -v`
Expected: FAIL — `ImportError: cannot import name 'PROGRAMME_PLAUSIBLE'`.

- [ ] **Step 3: Add the bands and the statistics**

Append to `src/ah/programme.py` (and add `import numpy as np`, `from ah.port.cashflow_tier1 import run_tier1`, `import json`, `from pathlib import Path` to the imports; extend `__all__`):

```python
_REPO_ROOT = Path(__file__).resolve().parents[2]
_COHORT_DOC = _REPO_ROOT / "fixtures" / "state" / "closed-end-cohort.example.json"


@dataclass(frozen=True)
class Band:
    """A declared plausible range. A prior written down for argument, not truth."""

    lo: float
    hi: float
    question: str


#: DECLARED PRIORS — edit them, that is the point. A flag is an invitation to
#: look; nothing here can fail a build. Single-cohort statistics are defined
#: against the vintage committed in YEAR 1, at the stated age: "DPI at year 10"
#: is meaningless in a ten-year decade, because that vintage only reaches 9.
PROGRAMME_PLAUSIBLE: dict[str, Band] = {
    "peak_unfunded_ratio": Band(0.25, 0.75, "is the ladder over- or under-committed"),
    "call_rate_y1_3": Band(0.15, 0.45, "do funds draw at a realistic speed"),
    "crossover_years": Band(4.0, 8.0, "the J-curve crossover"),
    "dpi_age9": Band(0.7, 2.0, "does a fund actually return capital"),
    "linkage_bite": Band(0.30, 0.80, "how hard the linkage bites, as a rate not a level"),
    "linkage_shortfall": Band(0.05, 0.35, "the linkage's total decade cost"),
    "forced_secondaries": Band(0.0, 1.0, "is distress rare enough to mean something"),
}


@dataclass(frozen=True)
class ProgrammeStat:
    """One statistic across the ensemble, against its declared band."""

    name: str
    median: float
    p10: float
    p90: float
    path0: float
    band: Band
    flagged: bool


def vintage_stats(
    drawdown_depth: np.ndarray, spread_ratio: np.ndarray, quarters: int
) -> dict[str, float]:
    """The single-cohort statistics for a vintage committed in year 1.

    Run through ``run_tier1`` rather than read out of the play run: these are
    questions about the MODEL's fund, and tier 1 is the module that answers
    them. Committed is 1.0 so every output is a ratio.
    """
    base = json.loads(_COHORT_DOC.read_text(encoding="utf-8"))
    n = min(quarters, len(drawdown_depth))
    if n < _QUARTERS_PER_YEAR:
        return {}
    result = run_tier1(
        base,
        committed=1.0,
        vintage_year=int(base["identity"]["vintage_year"]) + 1,
        sleeve_returns=np.zeros(n),
        drawdown_depth=np.asarray(drawdown_depth[:n], dtype=float),
        spread_ratio=np.asarray(spread_ratio[:n], dtype=float),
        fees_on=False,
    )
    calls = np.array([f.call for f in result.flows])
    dists = np.array([f.distribution_total for f in result.flows])
    paid_in = float(calls.sum())
    out: dict[str, float] = {"first_call": float(calls[0])}
    if paid_in > 0.0:
        out["dpi_age9"] = float(dists.sum()) / paid_in
        first_three = calls[: 3 * _QUARTERS_PER_YEAR].sum()
        out["call_rate_y1_3"] = float(first_three) / 3.0  # committed = 1.0
    cum = np.cumsum(dists - calls)
    crossed = np.flatnonzero(cum > 0.0)
    if crossed.size:
        out["crossover_years"] = float(crossed[0] + 1) / _QUARTERS_PER_YEAR
    return out


def path_stats(quarters: list[ProgrammeQuarter], result: PlayResult) -> dict[str, float]:
    """The programme-level statistics for ONE path."""
    out: dict[str, float] = {}
    ratios = [q.unfunded / q.private_nav for q in quarters if q.private_nav > 0.0]
    if ratios:
        out["peak_unfunded_ratio"] = max(ratios)

    rates = [
        (q.distributions / q.private_nav, q.drawdown_depth)
        for q in quarters
        if q.private_nav > 0.0
    ]
    if rates:
        worst = max(rates, key=lambda pair: pair[1])[0]
        median = float(np.median([r for r, _ in rates]))
        if median > 0.0:
            out["linkage_bite"] = worst / median

    unlinked_total = sum(q.distributions_unlinked for q in quarters)
    if unlinked_total > 0.0:
        linked_total = sum(q.distributions for q in quarters)
        out["linkage_shortfall"] = (unlinked_total - linked_total) / unlinked_total

    out["forced_secondaries"] = float(result.forced_secondaries)
    return out


def programme_stats(
    per_path: list[dict[str, float]], path0: dict[str, float]
) -> list[ProgrammeStat]:
    """Median and 10-90 spread across paths, flagged against the declared band.

    One path can be unlucky; a flag should mean the WORLD does this, so the
    flag fires on the median, with path 0's own value shown beside it.
    """
    stats: list[ProgrammeStat] = []
    for name, band in PROGRAMME_PLAUSIBLE.items():
        values = [row[name] for row in per_path if name in row]
        if not values:
            continue
        median = float(np.median(values))
        stats.append(
            ProgrammeStat(
                name=name,
                median=median,
                p10=float(np.percentile(values, 10)),
                p90=float(np.percentile(values, 90)),
                path0=float(path0.get(name, median)),
                band=band,
                flagged=not (band.lo <= median <= band.hi),
            )
        )
    return stats
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_programme_stats.py -v`
Expected: PASS, 5 tests. If `test_vintage_stats_on_a_calm_tape_are_hand_checkable` fails on `first_call`, read the actual value and check it against `rc_curve[0] * 0.25 * unfunded` by hand before changing the assertion — the test is the check on the model, not the other way round.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/programme.py tests/test_programme_stats.py
git commit -m "feat: declared bands and the statistics they judge

Single-cohort statistics run through run_tier1 and are defined against
the year-1 vintage at a stated age. The linkage-bite statistic is a
distribution RATE, so the ladder's own growth cannot masquerade as a
linkage effect. Flags fire on the median across paths, never one decade."
```

---

### Task 4: SVG primitives and the model-curves block

**Files:**
- Modify: `src/ah/programme.py`
- Test: `tests/test_programme_render.py` (create)

**Interfaces:**
- Consumes: nothing from Tasks 2-3 (pure rendering helpers plus the frozen artifacts).
- Produces: `model_block() -> str` (HTML fragment, world-independent), `_sparkline(values, *, width, height, color) -> str`, `_rug(xs, ys, *, width, height) -> str`.

- [ ] **Step 1: Load the dataviz skill**

Before writing any SVG, invoke the `dataviz` skill and follow its guidance on colour and form. The console's existing palette is in `credibility.py:_CSS` (`--jade #4fc3a1`, `--clay #d2624f`, `--brass #d6a24a`, `--dim #7c9b99`) — reuse those variables rather than introducing new hex values, so the section reads as part of the same page in both themes.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_programme_render.py`:

```python
"""The section renders, is self-contained, and states its frozen parameters."""

from __future__ import annotations

import json
from pathlib import Path

from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.programme import model_block

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _world(name: str = "stagflation"):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


def test_model_block_prints_the_frozen_linkage_parameters():
    html = model_block()
    # the values a reader must be able to check against mappings/
    assert "1.540688" in html  # f_dist a_drawdown
    assert "1.376940" in html  # f_dist b_log_spread
    assert "0.1" in html  # f_call c
    assert "2.5" in html  # bow B
    assert "0.55" in html  # yield_rate Y


def test_model_block_states_the_asymmetry_it_exists_to_show():
    html = model_block().lower()
    assert "f_call" in html and "f_dist" in html
    assert "continuous" in html, "the no-regime-label claim must be on the page"


def test_model_block_is_self_contained():
    html = model_block()
    for forbidden in ("http://", "https://", "<script", "src="):
        assert forbidden not in html, f"the page must not reference {forbidden}"


def test_model_block_is_deterministic():
    assert model_block() == model_block()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_programme_render.py -v`
Expected: FAIL — `cannot import name 'model_block'`.

- [ ] **Step 4: Implement the helpers and the block**

Append to `src/ah/programme.py` (add `import html as _html` and `from ah.port.cashflow_tier1 import load_linkage` to the imports):

```python
def _e(s: object) -> str:
    return _html.escape(str(s))


def _f(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}"


def _sparkline(values: list[float], *, width: int = 150, height: int = 34, color: str) -> str:
    """A minimal polyline. No axes: these curves are about SHAPE, and every
    one of them has its numbers printed beside it."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = width / max(1, len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{height - (v - lo) / span * (height - 2) - 1:.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg class="spark" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{points}"/>'
        "</svg>"
    )


def _rug(xs: list[float], ys: list[float], *, width: int = 150, height: int = 34) -> str:
    """Where this world's quarters actually landed on a response curve."""
    if not xs:
        return ""
    x_hi = max(xs) or 1.0
    y_lo, y_hi = min(ys), max(ys)
    span = (y_hi - y_lo) or 1.0
    dots = "".join(
        f'<circle cx="{x / x_hi * width:.1f}" '
        f'cy="{height - (y - y_lo) / span * (height - 2) - 1:.1f}" r="1.6"/>'
        for x, y in zip(xs, ys, strict=True)
    )
    return f'<g class="rug" fill="var(--brass)" opacity="0.75">{dots}</g>'


def model_block(realised: list[ProgrammeQuarter] | None = None) -> str:
    """The model's own curves, before any world touches them.

    World-independent except for the optional rug, which marks where the
    decade's quarters landed on the two response curves.
    """
    doc = json.loads(_COHORT_DOC.read_text(encoding="utf-8"))
    params = doc["parameters"]
    life = float(doc["lifecycle"]["contractual_life_years"])
    rc_curve = [float(v) for v in params["rc_curve"]]
    bow, yield_rate = float(params["bow"]), float(params["yield_rate"])
    link = load_linkage()
    fd_spec, fc_spec = link["f_dist"], link["f_call"]

    ages = [i * 0.25 for i in range(int(life * 4) + 1)]
    bow_curve = [yield_rate * (min(1.0, a / life) ** bow) for a in ages]
    dds = [i / 40.0 for i in range(41)]  # 0 .. 1.0 drawdown
    fd_curve = [
        min(
            fd_spec["ceiling"],
            max(fd_spec["floor"], float(np.exp(-fd_spec["a_drawdown"] * d))),
        )
        for d in dds
    ]
    fc_curve = [min(1.2, max(0.5, 1.0 - fc_spec["c"] * d)) for d in dds]

    rug_dist = rug_call = ""
    if realised:
        rug_dist = _rug([q.drawdown_depth for q in realised], [q.f_dist for q in realised])
        rug_call = _rug([q.drawdown_depth for q in realised], [q.f_call for q in realised])

    rows = [
        (
            "call rate RC(age)",
            _sparkline(rc_curve, color="var(--jade)"),
            "annual, on unfunded: " + ", ".join(_f(v) for v in rc_curve),
        ),
        (
            "distribution bow Y(age/L)^B",
            _sparkline(bow_curve, color="var(--jade)"),
            f"Y={_f(yield_rate)}, B={_f(bow, 1)}, L={_f(life, 0)} yrs; "
            "terminal liquidation at age >= L",
        ),
        (
            "f_dist(drawdown)",
            _sparkline(fd_curve, color="var(--clay)").replace("</svg>", rug_dist + "</svg>"),
            f"a={fd_spec['a_drawdown']}, b={fd_spec['b_log_spread']} (log spread), "
            f"floor {fd_spec['floor']}, ceiling {fd_spec['ceiling']} "
            "- shown at spread_ratio = 1",
        ),
        (
            "f_call(drawdown)",
            _sparkline(fc_curve, color="var(--clay)").replace("</svg>", rug_call + "</svg>"),
            f"c={fc_spec['c']}, clipped to [0.5, 1.2]",
        ),
    ]
    body = "".join(
        f"<tr><td>{_e(name)}</td><td>{svg}</td><td class='note'>{_e(note)}</td></tr>"
        for name, svg, note in rows
    )
    return (
        "<h3>The model, before any world touches it</h3>"
        f"<table><tbody>{body}</tbody></table>"
        "<p class='note'>Both linkage functions consume <strong>continuous</strong> "
        "market states only - drawdown depth and a spread ratio - and never a regime "
        "label (DN-5 Delta 3, structural). The asymmetry is the mechanic: f_call is "
        "clipped near-flat while f_dist can fall to its floor, so calls keep arriving "
        "while distributions stop. That, not the drawdown itself, is what empties the "
        "cash account. Brass dots mark where this world's quarters actually landed.</p>"
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_programme_render.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/programme.py tests/test_programme_render.py
git commit -m "feat: the model's own curves, with the decade's quarters rugged on them

Call curve, distribution bow and both linkage responses, each printed
with the frozen parameter values a reader can check against mappings/.
Self-contained inline SVG, no external assets, deterministic."
```

---

### Task 5: The per-world blocks — ladder, linkage, liquidity, flags

**Files:**
- Modify: `src/ah/programme.py`
- Test: `tests/test_programme_render.py` (extend)

**Interfaces:**
- Consumes: `ProgrammeQuarter`, `LadderYear`, `ProgrammeStat`, `model_block` from Tasks 2-4.
- Produces: `ProgrammeReport` (frozen dataclass: `world_id, title, quarters, ladder, stats, vintage_stack, forced_sales, flag_count`), `build_programme_report(world, *, base_seed, n_paths=20, title=None) -> ProgrammeReport`, `render_programme_section(reports: list[ProgrammeReport]) -> str`, `PROGRAMME_CSS: str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_programme_render.py`:

```python
import pytest

from ah.programme import build_programme_report, render_programme_section

# _world and PRESETS are already defined at the top of this file (Task 4).


@pytest.fixture(scope="module")
def report():
    return build_programme_report(_world("stagflation"), base_seed=771204, n_paths=4)


def test_report_covers_the_decade(report):
    assert len(report.quarters) == 40
    assert len(report.ladder) == 10


def test_section_shows_the_linkage_counterfactual(report):
    html = render_programme_section([report])
    assert "linkage off" in html.lower()
    assert "drawdown" in html.lower()
    assert "spread ratio" in html.lower()


def test_section_lists_forced_sales_with_their_cause(report):
    html = render_programme_section([report])
    # every logged sale's cause string must reach the page verbatim
    for sale in report.forced_sales:
        assert str(sale["cause"]) in html


def test_section_is_deterministic_for_a_fixed_world_and_seed():
    a = build_programme_report(_world("goldilocks"), base_seed=771204, n_paths=4)
    b = build_programme_report(_world("goldilocks"), base_seed=771204, n_paths=4)
    assert render_programme_section([a]) == render_programme_section([b])


@pytest.mark.parametrize("name", ["stagflation", "goldilocks", "deflation_bust", "reflation_boom"])
def test_every_preset_renders(name):
    rep = build_programme_report(_world(name), base_seed=771204, n_paths=2)
    assert render_programme_section([rep])
```

If the preset names differ, read them from `scripts/gen_presets.py` and use the real four.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_programme_render.py -v`
Expected: FAIL — `cannot import name 'build_programme_report'`.

- [ ] **Step 3: Implement the report builder**

Append to `src/ah/programme.py` (add `from ah.core.engine import run_path`, `from ah.core.numericworld import NumericWorld`, `from ah.play import simulate_play`):

```python
#: 20 full waterfall simulations per world, against the console's 400
#: vectorised return paths — each of these runs the whole quarterly waterfall.
#: Raise it if it turns out cheap.
PROGRAMME_PATHS = 20


@dataclass(frozen=True)
class ProgrammeReport:
    """Everything the section shows for one world."""

    world_id: str
    title: str
    quarters: list[ProgrammeQuarter]
    ladder: list[LadderYear]
    stats: list[ProgrammeStat]
    vintage_stack: list[tuple[str, list[float]]]
    forced_sales: list[dict[str, object]]

    @property
    def flag_count(self) -> int:
        return sum(1 for s in self.stats if s.flagged)


def _vintage_stack(result: PlayResult) -> list[tuple[str, list[float]]]:
    """Every cohort's NAV over the decade, zero before it was committed."""
    names: list[str] = []
    for q in result.quarters:
        for key in q.vintage_nav:
            if key not in names:
                names.append(key)
    return [(name, [q.vintage_nav.get(name, 0.0) for q in result.quarters]) for name in names]


def build_programme_report(
    world: NumericWorld,
    *,
    base_seed: int,
    n_paths: int = PROGRAMME_PATHS,
    title: str | None = None,
) -> ProgrammeReport:
    """Detail from path 0; statistics across the seed lineage."""
    per_path: list[dict[str, float]] = []
    path0_rows: list[ProgrammeQuarter] = []
    path0_result: PlayResult | None = None
    path0_stats: dict[str, float] = {}

    for k in range(max(1, n_paths)):
        paths = run_path(world, base_seed + 7919 * k)
        linked = simulate_play(paths)
        unlinked = simulate_play(paths, linkage=False)
        rows = programme_quarters(linked, unlinked)
        stats = path_stats(rows, linked)
        stats.update(
            vintage_stats(
                np.array([r.drawdown_depth for r in rows]),
                np.array([r.spread_ratio for r in rows]),
                len(rows) - _QUARTERS_PER_YEAR,
            )
        )
        per_path.append(stats)
        if k == 0:
            path0_rows, path0_result, path0_stats = rows, linked, stats

    assert path0_result is not None  # n_paths >= 1 by construction
    return ProgrammeReport(
        world_id=world.world_id,
        title=title or world.world_id,
        quarters=path0_rows,
        ladder=ladder_years(path0_rows, path0_result),
        stats=programme_stats(per_path, path0_stats),
        vintage_stack=_vintage_stack(path0_result),
        forced_sales=list(path0_result.sale_log),
    )
```

- [ ] **Step 4: Implement the rendering**

Append to `src/ah/programme.py`:

```python
PROGRAMME_CSS = """
.spark{vertical-align:middle}
.prog td.pos{color:var(--jade)}
.prog td.neg{color:var(--clay)}
.stack{display:flex;height:38px;align-items:flex-end;gap:1px}
.stack i{display:block;flex:1;background:var(--jade);opacity:.55}
"""


def _ladder_table(rep: ProgrammeReport) -> str:
    head = (
        "<tr><th>year</th><th>committed</th><th>called</th><th>distributed</th>"
        "<th>net</th><th>called to date</th><th>unfunded end</th>"
        "<th>private NAV end</th></tr>"
    )
    rows = "".join(
        f"<tr><td>{y.year}</td><td>{_f(y.committed)}</td><td>{_f(y.called)}</td>"
        f"<td>{_f(y.distributed)}</td>"
        f"<td class='{'pos' if y.net >= 0 else 'neg'}'>{_f(y.net)}</td>"
        f"<td>{_f(y.called_to_date)}</td><td>{_f(y.unfunded_end)}</td>"
        f"<td>{_f(y.private_nav_end)}</td></tr>"
        for y in rep.ladder
    )
    return f"<table class='prog'><thead>{head}</thead><tbody>{rows}</tbody></table>"


def _linkage_table(rep: ProgrammeReport) -> str:
    head = (
        "<tr><th>qtr</th><th>drawdown</th><th>spread ratio</th><th>f_dist</th>"
        "<th>f_call</th><th>distributions</th><th>linkage off</th>"
        "<th>shortfall</th></tr>"
    )
    rows = "".join(
        f"<tr><td>{q.quarter}</td><td>{_f(q.drawdown_depth, 3)}</td>"
        f"<td>{_f(q.spread_ratio, 3)}</td><td>{_f(q.f_dist, 3)}</td>"
        f"<td>{_f(q.f_call, 3)}</td><td>{_f(q.distributions)}</td>"
        f"<td>{_f(q.distributions_unlinked)}</td>"
        f"<td class='neg'>{_f(q.distributions - q.distributions_unlinked)}</td></tr>"
        for q in rep.quarters
    )
    linked = sum(q.distributions for q in rep.quarters)
    unlinked = sum(q.distributions_unlinked for q in rep.quarters)
    return (
        f"<table class='prog'><thead>{head}</thead><tbody>{rows}</tbody></table>"
        f"<p class='note'>Decade total: {_f(linked)} received against {_f(unlinked)} "
        "with the linkage off - the difference is what the market environment did to "
        "this programme's cash.</p>"
    )


def _liquidity_block(rep: ProgrammeReport) -> str:
    cash = _sparkline([q.cash for q in rep.quarters], color="var(--jade)")
    worst = max(rep.quarters, key=lambda q: q.coverage_true)
    sales = "".join(
        f"<tr><td>Q{_e(s.get('period'))}</td><td>{_e(s.get('kind'))}</td>"
        f"<td>{_e(s.get('cause'))}</td>"
        f"<td>{_e(', '.join(str(x) for x in s.get('sleeves_sold', [])))}</td>"
        f"<td>{_f(float(s.get('amount', 0.0)))}</td></tr>"
        for s in rep.forced_sales
    )
    table = (
        "<table class='prog'><thead><tr><th>when</th><th>kind</th><th>cause</th>"
        f"<th>sold</th><th>raised</th></tr></thead><tbody>{sales}</tbody></table>"
        if sales
        else "<p class='note'>No forced sales this decade.</p>"
    )
    return (
        f"<p>cash {cash} &nbsp; worst coverage: {_f(worst.coverage_true)} true vs "
        f"{_f(worst.coverage_reported)} reported (quarter {worst.quarter})</p>"
        "<p class='note'>Selling liquid holdings to fund a call is ordinary funding; "
        "a forced <em>secondary</em> at the policy haircut is distress. They are "
        "listed apart because collapsing them teaches the reader to ignore the "
        "words.</p>" + table
    )


def _stack_block(rep: ProgrammeReport) -> str:
    bars = "".join(f"<i style='height:{min(100, v * 4):.0f}%'></i>" for _, v in
                   [(n, s[-1]) for n, s in rep.vintage_stack])
    return (
        f"<div class='stack'>{bars}</div>"
        f"<p class='note'>{len(rep.vintage_stack)} cohorts alive at the decade's end, "
        "newest on the right. A programme with nothing on the right has stopped "
        "committing; one with nothing on the left has run its openers to term.</p>"
    )


def _stats_table(rep: ProgrammeReport) -> str:
    head = (
        "<tr><th>statistic</th><th>median</th><th>p10-p90</th><th>path 0</th>"
        "<th>declared</th><th>the question</th></tr>"
    )
    rows = "".join(
        f"<tr class='{'flagged' if s.flagged else ''}'><td>{_e(s.name)}</td>"
        f"<td>{_f(s.median, 3)}</td><td>{_f(s.p10, 3)} - {_f(s.p90, 3)}</td>"
        f"<td>{_f(s.path0, 3)}</td><td>{_f(s.band.lo, 2)} - {_f(s.band.hi, 2)}</td>"
        f"<td class='note'>{_e(s.band.question)}</td></tr>"
        for s in rep.stats
    )
    return f"<table class='prog'><thead>{head}</thead><tbody>{rows}</tbody></table>"


def render_programme_section(reports: list[ProgrammeReport]) -> str:
    """The whole section: the model once, then each world."""
    if not reports:
        return ""
    blocks = []
    for rep in reports:
        blocks.append(
            f"<section class='world'><h2>{_e(rep.title)} - the private programme</h2>"
            "<h3>The commitment ladder, year by year</h3>" + _ladder_table(rep)
            + "<h3>Cohorts alive at the decade's end</h3>" + _stack_block(rep)
            + "<h3>The market, and what it did to the cash</h3>" + _linkage_table(rep)
            + "<h3>Liquidity and the waterfall</h3>" + _liquidity_block(rep)
            + "<h3>Against the declared bands</h3>" + _stats_table(rep)
            + "</section>"
        )
    return (
        "<h1>The private programme</h1>"
        "<p class='lede'>What the cashflow model and the commitment pacing actually "
        "do, before the commitment lever asks a player to set them. Detail is path 0; "
        "statistics are the median across the world's own seed lineage.</p>"
        + model_block(reports[0].quarters)
        + "".join(blocks)
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_programme_render.py -v`
Expected: PASS, 9 tests (4 from Task 4 plus 5 here, one parametrized over four presets).

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add src/ah/programme.py tests/test_programme_render.py
git commit -m "feat: the ladder, the linkage, the liquidity and the flags

The linkage block prints both continuous states, both multipliers, and
distributions against the same tape with the linkage off - so its bite is
a number in points. Forced sales list cause and sleeves, keeping ordinary
funding apart from distress."
```

---

### Task 6: Wire into the console, prove it read-only, changelog

**Files:**
- Modify: `src/ah/credibility.py:432-470` (`render_credibility_page`), `src/ah/cli.py` (the `credibility_cmd` body), `CHANGELOG.md`
- Test: `tests/test_programme_guard.py` (create), `tests/test_credibility.py` (extend)

**Interfaces:**
- Consumes: `build_programme_report`, `render_programme_section`, `PROGRAMME_CSS` from Task 5.
- Produces: no new public API; the console page gains the section.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_programme_guard.py`:

```python
"""The programme module is read-only BY CONSTRUCTION, not by promise.

Same pattern as tests/test_blocks_import_graph.py: an admin diagnostic that
claims to write nothing should not be able to, and the cheapest enforcement
is that it cannot import anything that writes.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "src" / "ah" / "programme.py"
FORBIDDEN = ("ah.store", "ah.serve", "sqlite3")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_programme_never_imports_a_writer():
    offenders = [
        module
        for module in _imported_modules(MODULE)
        for bad in FORBIDDEN
        if module == bad or module.startswith(bad + ".")
    ]
    assert not offenders, f"ah.programme must not import a writer: {offenders}"


def test_programme_is_not_in_the_preregistration_seal():
    lock = Path(__file__).resolve().parents[1] / "prereg" / "battery-lock.yaml"
    if not lock.exists():
        return  # the seal lives elsewhere; the CLAUDE.md list already excludes this file
    assert "programme.py" not in lock.read_text("utf-8")
```

Append to `tests/test_credibility.py`:

```python
def test_credibility_page_carries_the_programme_section():
    from ah.credibility import build_report, render_credibility_page

    world = _world("stagflation")
    rep = build_report(world, base_seed=771204, n_paths=8)
    page = render_credibility_page([rep])
    assert "the private programme" in page.lower()
    assert "linkage off" in page.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_programme_guard.py tests/test_credibility.py -v`
Expected: the guard tests PASS already (the module imports no writer); the credibility test FAILS — the page has no programme section.

- [ ] **Step 3: Embed the section in the console page**

In `src/ah/credibility.py`, add the import at the top:

```python
from ah.programme import PROGRAMME_CSS, ProgrammeReport, render_programme_section
```

Change `render_credibility_page`'s signature and its two composition points:

```python
def render_credibility_page(
    reports: list[WorldReport], programme: list[ProgrammeReport] | None = None
) -> str:
```

In the returned string, extend the style tag and append the section before the footer:

```python
        f"<style>{_CSS}{PROGRAMME_CSS}</style></head><body>"
```

```python
        + "".join(blocks)
        + render_programme_section(programme or [])
        + "<footer>Admin surface. Not sealed, not scored, never shown to a player."
```

- [ ] **Step 4: Build the programme reports in the CLI**

In `src/ah/cli.py`'s `credibility_cmd`, alongside the existing `build_report` calls, build a `ProgrammeReport` per world with the same world and seed, then pass both lists:

```python
    from ah.programme import build_programme_report

    programme = [
        build_programme_report(world, base_seed=seed, title=title)
        for world, title, seed in worlds_with_seeds
    ]
    target.write_text(render_credibility_page(reports, programme), encoding="utf-8")
```

Adapt `worlds_with_seeds` to whatever the existing loop already holds — read `src/ah/cli.py:318-355` and reuse its variables rather than restructuring it. Any string echoed to the console must stay **ASCII**.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_programme_guard.py tests/test_credibility.py tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Look at the page**

```bash
uv run ah credibility --preset stagflation --preset deflation_bust --out programme-check.html
```

Open it. This is the deliverable — read the linkage block and confirm the asymmetry is visible: `f_call` barely moving while `f_dist` falls, distributions below the linkage-off column through the stress, and the shortfall accumulating. If it is not visible, that is a finding about the model, not a rendering bug: record it in `docs/engine-realism-register.md` rather than adjusting the page to hide it. Delete the file afterwards (it is untracked scratch; `data/` and `experiments/` are gitignored but the repo root is not).

- [ ] **Step 7: Update the CHANGELOG**

Add under `### Added` in the top `[Unreleased]` section, stating the six-field deviation from the spec and the runtime cost.

- [ ] **Step 8: Run the full gate**

```bash
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90 > gate.log 2>&1; echo "EXIT: $?" >> gate.log
```

Read `gate.log` — the `EXIT:` line and the pass count. **Never** chain a merge onto a `tail`, and never read the exit code through a pipe.

- [ ] **Step 9: Lint, type-check, commit, merge**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pyright
git add -A
git commit -m "feat: the private-programme section lands in the credibility console

ah credibility now carries the cashflow model, the commitment pacing
ladder and - explicitly - the market linkage: both continuous states,
both multipliers, and distributions against a linkage-off run of the same
tape. An import-graph test enforces that the module cannot write."
git checkout main
git merge --no-ff programme-view-spec -m "Merge programme-view-spec: the private programme, visible before the lever"
git push origin main
```

---

## Self-Review

**Spec coverage.** Block A → Task 4. Block B (ladder + vintage stack) → Tasks 2, 5. Block C (linkage, explicit) → Tasks 1, 2, 5. Block D (liquidity) → Tasks 2, 5. Block E (flags) → Task 3. Module boundaries, determinism, read-only, no-contract-bump → Tasks 1, 5, 6. Testing section → every task; the import-graph test is Task 6; the inertness test is Task 1 Step 7.

**Known gaps carried deliberately.** Two spec statistics are **not** implemented, because both need per-cohort flows that `PlayQuarter` does not carry and adding them would bloat the scored path's record for a diagnostic: `true private weight vs policy band` and `reported coverage < true at the worst quarter`. Both are computable from data the section already renders — the ladder shows private NAV and the liquidity block prints worst-quarter coverage on both bases — so the reader can check them by eye. If they should be flagged rows rather than eyeball checks, that is a follow-up task, and the band dict is where it goes.

**Type consistency.** `ProgrammeQuarter`/`LadderYear`/`ProgrammeStat`/`Band`/`ProgrammeReport` are defined once in Task 2/3/5 and used with those exact field names throughout. `_e`, `_f`, `_sparkline`, `_rug` are defined in Task 4 before Task 5 consumes them. `PROGRAMME_PATHS` is defined in Task 5 and defaulted in the same signature that uses it.

**Names verified against the codebase while writing this plan**, not assumed:
there is no `ah.presets` module (presets are JSON under `src/ah/presets/`, and
the plan carries the real `_world` helper); the four preset stems are
`stagflation`, `goldilocks`, `deflation_bust`, `reflation_boom`; and
`ClosedEndIdentity.cohort_id` exists (`src/ah/core/sleevestate.py:87-92`), so
`cohort.contract.identity.cohort_id` is correct.

---

*Not investment advice.*
