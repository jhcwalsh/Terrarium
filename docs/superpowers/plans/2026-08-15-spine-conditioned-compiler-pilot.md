# Spine-Conditioned Compiler Pilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and measure the spine-conditioned stress compiler pilot: L1/L2 slow-state spines steer which real 6-month chunks the stress stitcher draws, with a state-dependent correction hazard and a state-severity table — then judge it against six pre-sealed bars (B1–B6).

**Architecture:** Three layers per the spec (`docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md`): Layer S samples premise-accepted L1/L2 spines (reusing `simulate_decades`/`simulate_regimes`/`policy_anchor`, the same one-pass/two-pass composition `joinery/assemble.py:476-516` uses); Layer H is an 8-cell empirical correction hazard calibrated to panel CRI-onset frequencies; Layer F extends `StressBootstrap` so entry pools are conditioned on the spine's state cell and joins must agree on inflation era. Routing rides the existing `bootstrap-stratified` dispatcher via a new `extensions.x_spine` block.

**Tech Stack:** Python 3.12, numpy, pydantic (existing worldspec pattern), the pinned L1/L2 artifacts (`ah.gen.systems._pinned_layers`), pytest. **No new dependencies. No training.**

## Global Constraints

- **Owner rulings (binding):** R1 — selection only, a drawn month's values are NEVER modified or scaled; R2 — correction timing comes from a state-dependent hazard, never a schedule; severity is never tuned to portfolio outcomes (rule 1); no policy→growth equation is added to L1.
- **`schemas/` is read-only.** `generator_id` gains no values — spine worlds declare `engine_defaults.generator_id: "bootstrap-stratified"` and route by extension block.
- **Sealed files:** `pre-registration.lock`, `pre-registration-g3.lock`, `pre-registration-g5.lock` — verified 2026-08-15 to cover none of the files this plan touches (only fixture worldspecs match). If any task finds itself editing a path listed in ANY of the three locks, STOP and report BLOCKED.
- **Determinism:** all randomness from `numpy.random.Generator(PCG64(seed))`; layer seed offsets `{"climate": 0, "regimes": 104729, "hazard": 224737}`; decade/path stride 7919; per-path streams via `.jumped(p)`. No `random`, no time-based defaults.
- **Bit-identity:** sealed 1.0.x bootstrap worlds AND stress worlds (703) must produce byte-identical ensembles after every task (Task 5 pins this with digests).
- **Commit-order-as-pre-registration:** Task 6's sealed thresholds must be committed BEFORE Task 7/8 draw any pilot ensemble.
- CLI-echoed strings ASCII only. `ruff check`, `ruff format --check`, `pyright` clean full-tree BEFORE the ~38-min gate (`scripts/run_gate.py`); merge to main only after `scripts/check_gate.py` stamps `.gate-ok` for HEAD.
- Branch: `spine-01-pilot`, one branch for the whole plan, merged `--no-ff` after the gate.
- Worktree: use a dedicated worktree (NOT the owner's primary tree); junction `data/` and `experiments/` into it before running anything (the pinned artifacts live under `experiments/`).

---

### Task 1: The `x_spine` contract — `SpineSpec` in worldspec, projected onto NumericWorld

**Files:**
- Modify: `src/ah/core/worldspec.py` (after `StressSpec`, ~line 184)
- Modify: `src/ah/core/numericworld.py`
- Test: `tests/test_gen_spine.py` (new)

**Interfaces:**
- Consumes: `StressSpec`/`_Base` patterns already in `worldspec.py`.
- Produces: `SpinePremise`, `SpineSeverityRow`, `SpineSpec` (worldspec), `NumericWorld.spine: SpineSpec | None` — Tasks 2–5 import these exact names.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gen_spine.py
"""Spine-conditioned compiler (pilot). Spec:
docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md"""

import pytest
from pydantic import ValidationError

from ah.core.worldspec import SpinePremise, SpineSeverityRow, SpineSpec


def _table():
    return [
        {"condition": "baseline", "stratum_shift": 0, "dwell_shift_quarters": 0},
        {"condition": "either", "stratum_shift": 1, "dwell_shift_quarters": 1},
        {"condition": "both", "stratum_shift": 2, "dwell_shift_quarters": 2},
    ]


def _spec(**over):
    doc = {
        "premise": {
            "shock": "supply",
            "arrives_quarter": 8,
            "backdrop": "inflation_above_trend",
            "recovery": "slow",
        },
        "severity_table": _table(),
        "join_yoy_max_pp": 2.5,
        "precedent": ["pilot precedent line"],
    }
    doc.update(over)
    return doc


def test_spine_spec_parses():
    spec = SpineSpec.model_validate(_spec())
    assert spec.premise.shock == "supply"
    assert spec.premise.arrives_quarter == 8
    assert [r.condition for r in spec.severity_table] == ["baseline", "either", "both"]


def test_severity_table_must_cover_all_three_conditions_once():
    rows = _table()
    rows[2]["condition"] = "either"  # both missing, either twice
    with pytest.raises(ValidationError, match="baseline, either, both"):
        SpineSpec.model_validate(_spec(severity_table=rows))


def test_arrival_quarter_needs_a_backdrop_window():
    bad = _spec()
    bad["premise"]["arrives_quarter"] = 0
    with pytest.raises(ValidationError):
        SpineSpec.model_validate(bad)


def test_numericworld_projects_x_spine():
    import json
    from pathlib import Path

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(
        Path("src/ah/presets/stress_1990.json").read_text(encoding="utf-8")
    )
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.spine is None  # a stress world has no spine
    doc["extensions"]["x_spine"] = _spec()
    nw2 = project_numeric(WorldSpec.model_validate(doc))
    assert nw2.spine is not None and nw2.spine.premise.recovery == "slow"
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_gen_spine.py -q`
Expected: FAIL — `ImportError: cannot import name 'SpinePremise'`.

- [ ] **Step 3: Implement the models**

In `src/ah/core/worldspec.py`, directly after `StressSpec` (keep its style — `_Base`, Field, model_validator):

```python
class SpinePremise(_Base):
    """The declared storyline a spine must realize (spec section 3.1; D-SP-3)."""

    shock: Literal["supply", "financial"]
    arrives_quarter: int = Field(ge=1, le=39)  # ge=1: the backdrop needs a window
    backdrop: Literal["inflation_above_trend", "benign"]
    recovery: Literal["slow", "normal"]


class SpineSeverityRow(_Base):
    """One row of the state-severity table (spec section 3.4; D-SP-1)."""

    condition: Literal["baseline", "either", "both"]
    stratum_shift: int = Field(ge=0, le=2)
    dwell_shift_quarters: int = Field(ge=0, le=2)


class SpineSpec(_Base):
    """A spine-conditioned scenario. Declared ALONGSIDE x_stress: the stress
    block still carries the baseline segments/functional/join_tolerance; this
    block adds the premise, the state-severity table and the era join bound."""

    premise: SpinePremise
    severity_table: list[SpineSeverityRow] = Field(min_length=3, max_length=3)
    join_yoy_max_pp: float = Field(gt=0.0, le=10.0)
    precedent: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _table_covers_conditions(self) -> SpineSpec:
        got = sorted(r.condition for r in self.severity_table)
        if got != ["baseline", "both", "either"]:
            raise ValueError(
                f"severity_table must contain each of baseline, either, both exactly once; got {got}"
            )
        return self
```

Note: `sorted(...)` yields `["baseline", "both", "either"]` (lexicographic) — the error string still names them in reading order; keep the match string in the test aligned with the message you write.

In `src/ah/core/numericworld.py`: add `SpineSpec` to the import from `ah.core.worldspec`, add field `spine: SpineSpec | None = None` to `NumericWorld`, and mirror `_stress_of`:

```python
def _spine_of(world: WorldSpec) -> SpineSpec | None:
    """Only `x_spine` is projected — same narrowness argument as `_stress_of`."""
    ext = world.extensions or {}
    raw = ext.get("x_spine")
    return None if raw is None else SpineSpec.model_validate(raw)
```

and pass `spine=_spine_of(world)` in `project_numeric`.

- [ ] **Step 4: Run to green, plus the neighbours**

Run: `uv run pytest tests/test_gen_spine.py tests/test_worldspec.py tests/test_gen_stress.py -q`
Expected: PASS (the stress suite proves the projection change is additive).

- [ ] **Step 5: Commit**

```bash
git add src/ah/core/worldspec.py src/ah/core/numericworld.py tests/test_gen_spine.py
git commit -m "feat(spine-01): x_spine contract - SpinePremise/SpineSeverityRow/SpineSpec, projected onto NumericWorld"
```

---

### Task 2: Layer S — the spine sampler with premise acceptance and refusal

**Files:**
- Create: `src/ah/gen/spine.py`
- Test: `tests/test_gen_spine.py` (append)

**Interfaces:**
- Consumes: `ah.gen.climate.simulate.simulate_decades / policy_anchor / ClimateArtifact`; `ah.gen.regimes.semimarkov.simulate_regimes / RegimesArtifact`; `ah.gen.systems._pinned_layers`; `ah.data.derive.REGIME_LABELS`; `SpinePremise` from Task 1.
- Produces: `SpinePaths` (frozen dataclass: `states (n,120,5)`, `labels (n,120)`, `cycle (n,120)`, `policy (n,120)`, `mu_pi (n,)`, `attempts: int`, `seed: int`), `sample_spine(...)`, `SpineRefusal`, constants `LAYER_OFFSETS`, `SEED_STRIDE`, `CONTRACTION_CODES`, `BACKDROP_MARGIN_PP = 0.5`, `ARRIVAL_LATE_SLACK_MONTHS = 6`, `SLOW_RECOVERY_MIN_MONTHS = 24`, `MAX_ATTEMPTS_PER_DECADE = 200`. Tasks 3–4 and 7 import these exact names.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_gen_spine.py`)

```python
import numpy as np
import pytest


@pytest.fixture(scope="module")
def layers():
    from ah.gen.systems import _pinned_layers

    return _pinned_layers()


def _premise(**over):
    from ah.core.worldspec import SpinePremise

    doc = {
        "shock": "supply",
        "arrives_quarter": 8,
        "backdrop": "inflation_above_trend",
        "recovery": "slow",
    }
    doc.update(over)
    return SpinePremise.model_validate(doc)


def test_sample_spine_shapes_and_determinism(layers):
    from ah.gen.spine import sample_spine

    climate, regimes = layers
    a = sample_spine(climate, regimes, _premise(), n_decades=2, seed=41, months=120)
    b = sample_spine(climate, regimes, _premise(), n_decades=2, seed=41, months=120)
    assert a.states.shape == (2, 120, 5) and a.policy.shape == (2, 120)
    assert np.array_equal(a.states, b.states) and np.array_equal(a.labels, b.labels)


def test_accepted_spines_satisfy_the_premise(layers):
    from ah.gen.spine import (
        BACKDROP_MARGIN_PP,
        CONTRACTION_CODES,
        sample_spine,
    )

    climate, regimes = layers
    p = _premise()
    sp = sample_spine(climate, regimes, p, n_decades=3, seed=7, months=120)
    arrive = 3 * p.arrives_quarter
    for k in range(3):
        pi_pre = sp.states[k, :arrive, 0].mean()  # STATE_NAMES[0] == pi_star
        assert pi_pre > sp.mu_pi[k] + BACKDROP_MARGIN_PP
        in_c = np.isin(sp.labels[k], list(CONTRACTION_CODES))
        starts = np.flatnonzero(in_c & ~np.roll(in_c, 1))
        if in_c[0]:
            starts = np.unique(np.concatenate([[0], starts]))
        window = (starts >= arrive - 3) & (starts <= arrive + 6)
        assert window.any(), f"decade {k}: no contraction onset near quarter {p.arrives_quarter}"
        assert in_c.sum() >= 24  # recovery == slow


def test_unfillable_premise_refuses_with_a_named_reason(layers):
    from ah.gen.spine import SpineRefusal, sample_spine

    climate, regimes = layers
    # a backdrop essentially impossible under the fitted posterior: benign
    # inflation AND an immediate crash AND a slow decade is rare enough at a
    # tiny attempt budget to refuse deterministically.
    p = _premise(backdrop="benign", arrives_quarter=1)
    with pytest.raises(SpineRefusal, match="premise unfillable"):
        sample_spine(
            climate, regimes, p, n_decades=50, seed=11, months=120, max_attempts_per_decade=1
        )
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_gen_spine.py -q -k "spine_shapes or satisfy or refuses"`
Expected: FAIL — `ModuleNotFoundError: ah.gen.spine`.

- [ ] **Step 3: Implement `src/ah/gen/spine.py`**

```python
"""The spine-conditioned compiler (pilot), Layer S + H + F.

Spec: docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md.
Layer S here; Layers H and F arrive in the same module (Tasks 3-4).

Seed hygiene: three consumers, three disjoint streams per decade/path --
climate (offset 0), regimes (offset 104729), hazard (offset 224737); the
block-draw stream stays PCG64(seed).jumped(p) exactly as StressBootstrap.
An attempt counter, not the accepted-decade index, advances the S streams,
so acceptance filtering never re-uses an attempt's randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ah.core.worldspec import SpinePremise
from ah.data.derive import REGIME_LABELS
from ah.gen.climate.simulate import (
    ClimateArtifact,
    SimulatedClimate,
    policy_anchor,
    simulate_decades,
)
from ah.gen.regimes.semimarkov import RegimesArtifact, simulate_regimes

SEED_STRIDE = 7919
LAYER_OFFSETS = {"climate": 0, "regimes": 104729, "hazard": 224737}
CONTRACTION_CODES = frozenset(
    {REGIME_LABELS.index("REC"), REGIME_LABELS.index("CRI")}
)
BACKDROP_MARGIN_PP = 0.5
ARRIVAL_LATE_SLACK_MONTHS = 6
SLOW_RECOVERY_MIN_MONTHS = 24
MAX_ATTEMPTS_PER_DECADE = 200


class SpineRefusal(RuntimeError):
    """A premise the pinned posterior would not realize at the attempt budget."""


@dataclass(frozen=True)
class SpinePaths:
    states: np.ndarray  # (n, months, 5) STATE_NAMES order
    labels: np.ndarray  # (n, months) int codes into REGIME_LABELS
    cycle: np.ndarray  # (n, months)
    policy: np.ndarray  # (n, months) Taylor anchor, noise-free
    mu_pi: np.ndarray  # (n,) each decade's own posterior-draw mu_pi
    attempts: int
    seed: int


def _reject_reason(
    premise: SpinePremise, states: np.ndarray, labels: np.ndarray, mu_pi: float
) -> str | None:
    """None if the decade realizes the premise, else the failed clause's name."""
    arrive = 3 * premise.arrives_quarter
    pi_pre = float(states[:arrive, 0].mean())  # pi_star is STATE_NAMES[0]
    if premise.backdrop == "inflation_above_trend":
        if not pi_pre > mu_pi + BACKDROP_MARGIN_PP:
            return "backdrop:inflation_above_trend"
    else:
        if pi_pre > mu_pi + BACKDROP_MARGIN_PP:
            return "backdrop:benign"
    in_c = np.isin(labels, list(CONTRACTION_CODES))
    starts = np.flatnonzero(in_c & ~np.roll(in_c, 1))
    if in_c[0]:
        starts = np.unique(np.concatenate([[0], starts]))
    lo, hi = arrive - 3, arrive + ARRIVAL_LATE_SLACK_MONTHS
    if not ((starts >= lo) & (starts <= hi)).any():
        return "arrival"
    months_c = int(in_c.sum())
    if premise.recovery == "slow" and months_c < SLOW_RECOVERY_MIN_MONTHS:
        return "recovery:slow"
    if premise.recovery == "normal" and months_c >= SLOW_RECOVERY_MIN_MONTHS:
        return "recovery:normal"
    return None


def sample_spine(
    climate: ClimateArtifact,
    regimes_artifact: RegimesArtifact,
    premise: SpinePremise,
    *,
    n_decades: int,
    seed: int,
    months: int = 120,
    max_attempts_per_decade: int = MAX_ATTEMPTS_PER_DECADE,
) -> SpinePaths:
    """Premise-accepted spines, one-pass L2 on one-pass L1, then the two-pass
    L1 re-run under the regime cycle (the joinery/assemble composition)."""
    if n_decades < 1:
        raise ValueError("n_decades must be >= 1")
    budget = max_attempts_per_decade * n_decades
    kept_s: list[np.ndarray] = []
    kept_l: list[np.ndarray] = []
    kept_c: list[np.ndarray] = []
    kept_p: list[np.ndarray] = []
    kept_mu: list[float] = []
    tally: dict[str, int] = {}
    attempt = 0
    while len(kept_s) < n_decades and attempt < budget:
        l1_seed = seed + LAYER_OFFSETS["climate"] + SEED_STRIDE * attempt
        l2_seed = seed + LAYER_OFFSETS["regimes"] + SEED_STRIDE * attempt
        sim1 = simulate_decades(climate, 1, seed=l1_seed, months=months)
        reg = simulate_regimes(regimes_artifact, sim1.states, seed=l2_seed)
        # two-pass: same seed -> same theta/s0/innovations; only the credit
        # norm's cycle forcing changes (assemble.py's documented pattern).
        sim2 = simulate_decades(
            climate, 1, seed=l1_seed, months=months, cycle=reg.cycle
        )
        pol = policy_anchor(sim2, cycle=reg.cycle)
        mu_pi = float(sim2.params["mu_pi"][0])
        reason = _reject_reason(premise, sim2.states[0], reg.labels[0], mu_pi)
        attempt += 1
        if reason is None:
            kept_s.append(sim2.states[0])
            kept_l.append(reg.labels[0])
            kept_c.append(reg.cycle[0])
            kept_p.append(pol[0])
            kept_mu.append(mu_pi)
        else:
            tally[reason] = tally.get(reason, 0) + 1
    if len(kept_s) < n_decades:
        raise SpineRefusal(
            f"premise unfillable at budget {budget}: accepted {len(kept_s)}/{n_decades}; "
            f"rejections {dict(sorted(tally.items()))}"
        )
    return SpinePaths(
        states=np.stack(kept_s),
        labels=np.stack(kept_l),
        cycle=np.stack(kept_c),
        policy=np.stack(kept_p),
        mu_pi=np.asarray(kept_mu, dtype=np.float64),
        attempts=attempt,
        seed=int(seed),
    )
```

- [ ] **Step 4: Run to green**

Run: `uv run pytest tests/test_gen_spine.py -q`
Expected: PASS. If `test_accepted_spines_satisfy_the_premise` is slow (>~2 min), reduce its `n_decades` to 2 — do NOT loosen the assertions.

- [ ] **Step 5: Commit**

```bash
git add src/ah/gen/spine.py tests/test_gen_spine.py
git commit -m "feat(spine-01): Layer S - premise-accepted L1/L2 spine sampler with named refusal"
```

---

### Task 3: Layer H — state cells and the empirical correction hazard

**Files:**
- Modify: `src/ah/gen/spine.py` (append)
- Test: `tests/test_gen_spine.py` (append)

**Interfaces:**
- Consumes: `BootstrapSource` (`ah.gen.bootstrap.campaign_source`) — fields `values`, `factor_names`, `labels`, `n_rows`; `SpinePaths` from Task 2.
- Produces: `panel_yoy(source) -> np.ndarray` (len n_rows, NaN where <12 months of contiguous panel history), `panel_cell(source, yoy, era_thr) -> np.ndarray` (int8 in [-1, 7]; -1 where yoy is NaN), `spine_cell(states_m, label_m, mu_pi, policy_m) -> int` (0..7), `HazardTable` (dataclass: `rates (8,)`, `era_threshold_pp: float`, `cell_months (8,)`, `fallback_rate: float`), `fit_hazard(source) -> HazardTable`. Cell encoding — bit 0: inflation era high; bit 1: growth contraction; bit 2: policy tight. `MIN_CELL_MONTHS = 24`.

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_panel_cells_and_hazard_calibration():
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import MIN_CELL_MONTHS, fit_hazard, panel_cell, panel_yoy

    src = campaign_source()
    yoy = panel_yoy(src)
    assert yoy.shape == (src.n_rows,)
    assert np.isnan(yoy[:12]).all()  # no 12-month lookback at the panel's start
    table = fit_hazard(src)
    assert table.rates.shape == (8,)
    assert np.all((table.rates >= 0.0) & (table.rates <= 1.0))
    # cells with enough months carry their own rate; starved cells the fallback
    for c in range(8):
        if table.cell_months[c] < MIN_CELL_MONTHS:
            assert table.rates[c] == table.fallback_rate
    # the loaded-dice property the design promises: conditional on enough data,
    # the all-preconditions cell (era high + contraction + tight) must not be
    # QUIETER than the no-preconditions cell.
    if table.cell_months[7] >= MIN_CELL_MONTHS and table.cell_months[0] >= MIN_CELL_MONTHS:
        assert table.rates[7] >= table.rates[0]


def test_spine_cell_encoding():
    import numpy as np

    from ah.gen.spine import CONTRACTION_CODES, spine_cell

    states = np.array([3.5, 1.0, 1.5, 0.0, 1.2])  # pi*, r*, g, v, L
    rec = next(iter(CONTRACTION_CODES))
    # pi gap = 3.5 - 2.0 > 0.5 -> era bit; contraction bit; policy 6.0 > r*+pi* -> tight
    assert spine_cell(states, rec, mu_pi=2.0, policy_m=6.0) == 0b111
    assert spine_cell(states, 0, mu_pi=2.0, policy_m=6.0) == 0b101  # EXP: no growth bit
    assert spine_cell(states, 0, mu_pi=4.0, policy_m=0.0) == 0b000
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_gen_spine.py -q -k "hazard or cell_encoding"`
Expected: FAIL — names not defined.

- [ ] **Step 3: Implement** (append to `spine.py`)

```python
MIN_CELL_MONTHS = 24


def panel_yoy(source) -> np.ndarray:
    """Trailing CPI YoY per panel row, %; NaN where the 12-month lookback is
    unavailable. The panel's cpi factor is a LEVEL (the 2026-08-15 finding):
    YoY is only computed against the row 12 places earlier IN THE PANEL, which
    is contiguous by construction within the panel's own ordering."""
    ci = list(source.factor_names).index("cpi")
    level = np.asarray(source.values)[:, ci].astype(np.float64)
    out = np.full(source.n_rows, np.nan)
    out[12:] = (level[12:] / level[:-12] - 1.0) * 100.0
    return out


def panel_cell(source, yoy: np.ndarray, era_threshold_pp: float) -> np.ndarray:
    """Cell code per panel row; -1 where yoy is NaN. Panel-space proxies
    (spec 3.2 disclosure): era from trailing YoY vs threshold, growth from the
    row's own regime label, policy tightness from curve inversion."""
    names = list(source.factor_names)
    y10 = np.asarray(source.values)[:, names.index("ust_10y")]
    y2 = np.asarray(source.values)[:, names.index("ust_2y")]
    contraction = np.isin(
        np.asarray(source.labels), ["REC", "CRI"]
    )
    cells = np.full(source.n_rows, -1, dtype=np.int8)
    ok = ~np.isnan(yoy)
    era = (yoy > era_threshold_pp).astype(np.int8)
    tight = (y10 - y2 < 0.0).astype(np.int8)
    cells[ok] = era[ok] | (contraction[ok].astype(np.int8) << 1) | (tight[ok] << 2)
    return cells


def spine_cell(states_m: np.ndarray, label_m: int, *, mu_pi: float, policy_m: float) -> int:
    """Spine-space cell for one month. states_m is one row in STATE_NAMES order."""
    era = int(states_m[0] - mu_pi > BACKDROP_MARGIN_PP)
    contraction = int(int(label_m) in CONTRACTION_CODES)
    tight = int(policy_m - (states_m[1] + states_m[0]) > 0.0)
    return era | (contraction << 1) | (tight << 2)


@dataclass(frozen=True)
class HazardTable:
    rates: np.ndarray  # (8,) monthly correction-onset probability per cell
    era_threshold_pp: float
    cell_months: np.ndarray  # (8,) panel months per cell
    fallback_rate: float


def fit_hazard(source) -> HazardTable:
    """Empirical CRI-onset frequency per panel cell (spec 3.2). Saturated over
    3 binary covariates, so 'fit' IS the per-cell frequency table -- portfolio
    outcomes never enter (rule 1). Starved cells (< MIN_CELL_MONTHS) take the
    marginal onset rate."""
    yoy = panel_yoy(source)
    era_thr = float(np.nanmedian(yoy) + BACKDROP_MARGIN_PP)
    cells = panel_cell(source, yoy, era_thr)
    labels = np.asarray(source.labels)
    is_cri = labels == "CRI"
    onset = is_cri & ~np.roll(is_cri, 1)
    onset[0] = is_cri[0]
    ok = cells >= 0
    fallback = float(onset[ok].sum() / max(int(ok.sum()), 1))
    rates = np.full(8, fallback)
    months = np.zeros(8, dtype=np.int64)
    for c in range(8):
        mask = cells == c
        months[c] = int(mask.sum())
        if months[c] >= MIN_CELL_MONTHS:
            rates[c] = float(onset[mask].sum() / months[c])
    return HazardTable(
        rates=rates, era_threshold_pp=era_thr, cell_months=months, fallback_rate=fallback
    )
```

- [ ] **Step 4: Run to green**

Run: `uv run pytest tests/test_gen_spine.py -q`
Expected: PASS. If `rates[7] >= rates[0]` fails with both cells populated, STOP — that is a real finding about the panel (the preconditions do not load the dice) and goes to the human partner before proceeding; do not weaken the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/ah/gen/spine.py tests/test_gen_spine.py
git commit -m "feat(spine-01): Layer H - 8-cell empirical correction hazard from panel CRI onsets"
```

---

### Task 4: Layer F — `SpineBootstrap`: cell-conditioned pools, the hazard's corrections, era-safe joins

**Files:**
- Modify: `src/ah/gen/spine.py` (append)
- Test: `tests/test_gen_spine.py` (append)

**Interfaces:**
- Consumes: `StressBootstrap` internals as PATTERN (do not subclass — copy the draw loop and modify; the two samplers must stay independently readable): `severity_score`, `eligible_rows`, `join_candidates`, `_segment_for` from `ah.gen.stress`; `Ensemble`/`EnsembleMeta`/`RegimeRecord` from `ah.gen.base` and the slow-state record class the hier ensembles carry (follow the import in `ah/gen/blocks/flow.py` — the same class, so the narration workbench consumes spine worlds unchanged); Tasks 2–3 symbols.
- Produces: `SpineBootstrap` with `generator_id = "bootstrap-stratified"`, `.source` property, `fit(BootstrapSource)`, `sample(world, n_paths, seed)` requiring BOTH `world.stress` and `world.spine`. `BASE_DWELL_QUARTERS = 2`, `STRATUM_FLOOR_PCT = 5.0`, `percentile_for(base, shift) = max(STRATUM_FLOOR_PCT, base * 0.5**shift)`.

Behaviour to implement, exactly:

1. Spines: `sample_spine(climate, regimes, world.spine.premise, n_decades=n_paths, seed=seed, months=months)` — pinned layers loaded once in `__init__` via `ah.gen.systems._pinned_layers()`.
2. Hazard: `fit_hazard(source)` once per `sample`. Per path p, stream `np.random.Generator(np.random.PCG64(seed + LAYER_OFFSETS["hazard"]).jumped(p))`. Walking months: if not in a correction and `rng_h.random() < rates[spine_cell(...)]` → a correction starts: dwell = `(BASE_DWELL_QUARTERS + dwell_shift) * 3` months, stratum shift per the severity row selected by the FIRING month's conditions (`infl = pi_gap > BACKDROP_MARGIN_PP`, `credit = credit_gap > 0`; both→"both", one→"either", none→"baseline").
3. Pools: for each (segment, era, growth) — era/growth from the SPINE month — the entry pool is `eligible_rows(scores, pct) ∩ {rows: panel era bucket == spine era bucket AND panel contraction == spine contraction}` where `pct` is the segment's declared percentile outside corrections and `percentile_for(declared, stratum_shift)` inside one. Panel rows with NaN yoy are never pool members. **An empty pool raises** `SpineRefusal` naming `(segment.from_quarter, era, growth, pct)` — refusal, never substitution.
4. Joins: after `join_candidates` (the level-factor tolerance from `world.stress.join_tolerance`), apply two more filters: candidate's panel era bucket equals the previous row's, and `abs(yoy[cand] - yoy[prev]) <= world.spine.join_yoy_max_pp`. NaN-yoy rows were already excluded. Empty after filtering → the block continues (`advanced`), same as stress.
5. The block-restart trigger stream stays `PCG64(seed).jumped(p)` — the hazard stream and the block stream must be DIFFERENT generators (a test asserts drawing from one does not perturb the other).
6. Ensemble: `row_indices` carried; `regimes` = realized source labels (as stress does) with `mode="realized-spine-conditioned"`; **slow_states = the spine's five states** via the hier-flow record class; conditioning dict extends the stress stamp with `mode="spine-conditioned-stress"`, the premise dump, the severity table, `hazard: {rates, cell_months, era_threshold_pp, fallback_rate}` (as lists/floats), `corrections: {per_path_onsets: list[int], per_cell_onsets: [8 ints], per_cell_months: [8 ints]}` (aggregated over paths, ints only), `spine_attempts`, and `pool_occupancy: {"<seg>/<era>/<growth>": int}` for every pool actually built.

- [ ] **Step 1: Write the failing tests** (append; build one small spine world dict helper `_spine_world()` returning a `NumericWorld` from the 703 preset doc plus `x_spine` from Task 1's `_spec()`, `n_paths=3`, `seed=90210`)

```python
@pytest.fixture(scope="module")
def spine_world():
    import json
    from pathlib import Path

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(Path("src/ah/presets/stress_1990.json").read_text(encoding="utf-8"))
    doc["extensions"]["x_spine"] = _spec()
    return project_numeric(WorldSpec.model_validate(doc))


def test_spine_bootstrap_sample_contract(spine_world):
    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import SpineBootstrap

    gen = SpineBootstrap()
    gen.fit(campaign_source())
    ens = gen.sample(spine_world, 3, 90210)
    assert ens.paths.shape[0] == 3 and ens.row_indices is not None
    cond = ens.meta.conditioning
    assert cond["mode"] == "spine-conditioned-stress"
    assert len(cond["hazard"]["rates"]) == 8
    assert ens.slow_states is not None and not hasattr(ens.slow_states, "reason")


def test_every_month_is_verbatim_history(spine_world):
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import SpineBootstrap

    src = campaign_source()
    gen = SpineBootstrap()
    gen.fit(src)
    ens = gen.sample(spine_world, 2, 90210)
    assert np.array_equal(ens.paths, np.asarray(src.values)[ens.row_indices])  # R1


def test_no_era_teleports_at_joins(spine_world):
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import SpineBootstrap, panel_yoy

    src = campaign_source()
    gen = SpineBootstrap()
    gen.fit(src)
    ens = gen.sample(spine_world, 3, 90210)
    yoy = panel_yoy(src)
    bound = spine_world.spine.join_yoy_max_pp
    rows = np.asarray(ens.row_indices)
    for p in range(rows.shape[0]):
        for m in range(1, rows.shape[1]):
            if rows[p, m] != rows[p, m - 1] + 1:  # a join
                assert abs(yoy[rows[p, m]] - yoy[rows[p, m - 1]]) <= bound


def test_hazard_and_block_streams_are_independent(spine_world):
    """Path 0's tape must not change when the hazard stream is consumed more
    (a different premise-month firing pattern) -- proven by construction:
    the two Generators are seeded from different offsets. Assert the offsets
    differ and that a re-sample is bit-identical (stream discipline holds)."""
    import numpy as np

    from ah.gen.bootstrap import campaign_source
    from ah.gen.spine import LAYER_OFFSETS, SpineBootstrap

    assert LAYER_OFFSETS["hazard"] != 0
    gen = SpineBootstrap()
    gen.fit(campaign_source())
    a = gen.sample(spine_world, 2, 4242)
    b = gen.sample(spine_world, 2, 4242)
    assert np.array_equal(a.row_indices, b.row_indices)
```

- [ ] **Step 2: Run and watch them fail** — `uv run pytest tests/test_gen_spine.py -q -k "bootstrap or verbatim or teleport or independent"` → FAIL (`SpineBootstrap` undefined).

- [ ] **Step 3: Implement `SpineBootstrap`** per the six numbered behaviours above. Copy `StressBootstrap._draw`'s loop as the base of the month walk (same restart trigger, same self-join exclusion, same "severity is a preference, never a licence to teleport" continuation rule) and add: the correction state machine (behaviour 2), per-cell pools (behaviour 3), the two join filters (behaviour 4). Keep the whole class under ~200 lines; factor `_build_pools` and `_severity_row_for` as module-level helpers so each is unit-readable.

- [ ] **Step 4: Run to green** — `uv run pytest tests/test_gen_spine.py -q` → PASS, then `uv run pytest tests/test_gen_stress.py -q` → PASS (stress untouched).

- [ ] **Step 5: Commit**

```bash
git add src/ah/gen/spine.py tests/test_gen_spine.py
git commit -m "feat(spine-01): Layer F - SpineBootstrap: cell-conditioned pools, hazard corrections, era-safe joins"
```

---

### Task 5: Dispatcher routing and bit-identity guards

**Files:**
- Modify: `src/ah/gen/stress.py` (`_StressOrLegacyDispatch.sample`, ~line 342)
- Modify: `src/ah/gen/__init__.py` only if import order needs it (it should not)
- Test: `tests/test_gen_spine.py` (append)

**Interfaces:**
- Consumes: `NumericWorld.spine` (Task 1), `SpineBootstrap` (Task 4).
- Produces: routing — `world.spine is not None` → `SpineBootstrap`; else `world.stress is not None` → `StressBootstrap`; else legacy factory. Import `SpineBootstrap` INSIDE the branch (keep `stress.py` import-light and cycle-free).

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_dispatcher_routes_spine_worlds(spine_world):
    from ah.gen import registry

    gen = registry.resolve_for_world(spine_world)
    ens = gen.sample(spine_world, 1, 5150)
    assert ens.meta.conditioning["mode"] == "spine-conditioned-stress"


def test_dispatcher_still_routes_stress_and_legacy_bit_identically():
    import json
    from pathlib import Path

    import numpy as np

    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec
    from ah.gen import registry
    from ah.gen.bootstrap import bootstrap_v1_factory, campaign_source
    from ah.gen.stress import StressBootstrap

    doc = json.loads(Path("src/ah/presets/stress_1990.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    via_dispatch = registry.resolve_for_world(nw).sample(nw, 2, 199001)
    direct = StressBootstrap()
    direct.fit(campaign_source())
    assert np.array_equal(
        via_dispatch.row_indices, direct.sample(nw, 2, 199001).row_indices
    )
```

(The legacy-world half of the guard already exists in `tests/test_gen_stress.py` — re-run it, do not duplicate it.)

- [ ] **Step 2: Watch the first test fail** (dispatch reaches `StressBootstrap`, which raises on the missing... no — it samples WITHOUT spine conditioning; the assertion on `mode` fails). Run: `uv run pytest tests/test_gen_spine.py -q -k dispatcher`.

- [ ] **Step 3: Implement** — in `_StressOrLegacyDispatch.sample`, before the stress branch:

```python
if getattr(world, "spine", None) is not None:
    from ah.gen.spine import SpineBootstrap

    gen = SpineBootstrap()
    gen.fit(self.source)
    return gen.sample(world, n_paths, seed)
```

(`self.source` is the dispatcher's fitted panel — `SpineBootstrap.fit` accepts the same `BootstrapSource`.)

- [ ] **Step 4: Run to green + the whole neighbourhood** — `uv run pytest tests/test_gen_spine.py tests/test_gen_stress.py tests/test_gen_registry.py tests/test_seal_guards.py -q` → PASS. If `test_seal_guards` flags `ah.gen.spine` as seal-reachable, classify it in `EXCLUDED_FROM_SEAL` with the same "judged, not judge" argument recorded for `ah.gen.stress` (stress-01) — cite that precedent in the entry's comment.

- [ ] **Step 5: Commit**

```bash
git add src/ah/gen/stress.py tests/test_gen_spine.py tests/test_seal_guards.py
git commit -m "feat(spine-01): dispatcher routes x_spine worlds to SpineBootstrap; stress/legacy pinned bit-identical"
```

---

### Task 6: The pilot world, and the sealed bars (COMMIT BEFORE ANY MEASUREMENT)

**Files:**
- Create: `src/ah/presets/spine_pilot.json` (world `00000000-0000-4000-9000-000000000802`)
- Create: `scripts/spine_pilot_seal.py`
- Create: `docs/superpowers/specs/spine-pilot-prereg.json` (WRITTEN BY the seal script, committed)
- Test: `tests/test_gen_spine.py` (append)

**The world** — copy `stress_1990.json` and change: `world_id` `...802`, title `"The Hard Landing"`, `base_seed` 199002, keep its `x_stress` block verbatim (the baseline strata ARE the declared severity), add `x_spine`:

```json
{
  "premise": {"shock": "supply", "arrives_quarter": 8, "backdrop": "inflation_above_trend", "recovery": "slow"},
  "severity_table": [
    {"condition": "baseline", "stratum_shift": 0, "dwell_shift_quarters": 0},
    {"condition": "either", "stratum_shift": 1, "dwell_shift_quarters": 1},
    {"condition": "both", "stratum_shift": 2, "dwell_shift_quarters": 2}
  ],
  "join_yoy_max_pp": 2.5,
  "precedent": [
    "Spine: L1/L2 pinned posteriors (campaign-3 pins, AM-2026-08-10-001); premise realized by rejection, refusal on unfillable.",
    "Flesh: verbatim panel months, 6-month mean blocks, entry severity per x_stress; joins bounded on 9 level factors + inflation era (<=2.5pp YoY).",
    "Corrections: hazard = panel CRI-onset frequency per 8 state cells; timing random by construction (D-SP rulings 2026-08-15).",
    "The severity table's values are pre-registration candidates pending D-SP-1."
  ],
  "narrative_note": "spine-conditioned pilot world; NOT ranked; see spine-pilot-prereg.json"
}
```

(Adjust the last key to whatever the schema's extension rules allow — extensions are free-form; the narrative caveat can live in the world's `narrative` block instead if `x_spine` extra keys are rejected by `_Base`'s config. `SpineSpec` forbids extras, so put the note in `narrative`.)

**The seal script** — `scripts/spine_pilot_seal.py` (ASCII output only): computes every *(cand.)* value from the panel + pinned artifacts, then writes `docs/superpowers/specs/spine-pilot-prereg.json`:

```python
"""Seal the spine-pilot bars (spec section 5). Run ONCE; commit the JSON in the
SAME commit as this script; any re-run that changes the JSON is an amendment
and needs an owner-visible commit message saying so."""
```

Sealed content (formulas fixed by the spec; this script freezes the numbers):

- `b1`: `{min_sign_fraction: 0.90, lag_months: [3, 12]}`
- `b2`: `{join_yoy_max_pp: 2.5, p95_ratio_max: 1.25, panel_p95_adjacent_yoy_pp: <computed: 95th pct of |yoy[t]-yoy[t-1]| over contiguous panel months>}`
- `b3`: `{grid_private_pct: [15, 35, 40, 55], min_breach_seeds_at_55: 1, n_seeds: 20, coverage_must_be_monotone: true}`
- `b4`: `{sojourn_median_ratio_band: [0.6, 1.4], regimes: ["EXP","SLOW","REC","CRI","STAG","REF"], panel_medians: <computed from panel label spells>}`
- `b5`: `{rel_tolerance: 0.5, panel_rates: <the fit_hazard table>, min_cell_months: 24}`
- `b6`: `{k_months: 12, policy_gap_threshold_pp: <computed: panel 75th pct of (policy_rate - ust_10y)... NO — spine-side gap needs r*+pi*; freeze the SPINE-side threshold as 0.0 (tight = anchor exceeded) and the PANEL-side conditional via curve inversion>, panel_conditional_onset_rate: <computed: P(CRI onset within 12 months | curve inverted)>, panel_unconditional_onset_rate: <computed>, rel_tolerance: 0.5}`
- `hashes`: sha256 of `src/ah/gen/spine.py`, `scripts/spine_pilot_report.py` if present else `"unbuilt"`, this script itself, and `src/ah/presets/spine_pilot.json`.

Test (append): the JSON exists, parses, covers keys `b1..b6`, and its recorded `spine.py` hash matches the working tree (recompute in the test — this is the pilot's cheap seal-integrity check; skip-with-reason is FORBIDDEN, a mismatch after Task 7 edits means re-run the seal script and record the amendment).

**Note on hash churn:** Task 7 creates `spine_pilot_report.py` AFTER the seal. The seal script therefore must be re-run at the END of Task 7 step 3 (before any ensemble is drawn by the report) to fill the report hash — that re-run is part of the pre-registration, not an amendment, and its commit message says exactly that. Thresholds must be byte-identical across the two runs; the test asserts the thresholds block of the JSON is unchanged by comparing against the values captured in the Task 6 commit (store them in the test as literals copied from the first sealed JSON).

- [ ] **Step 1:** write the preset + seal script + tests; run the seal script; eyeball the JSON's computed numbers against the panel (sanity: `panel_p95_adjacent_yoy_pp` should be well under 2.5).
- [ ] **Step 2:** `uv run pytest tests/test_gen_spine.py -q` → PASS.
- [ ] **Step 3: Commit — this commit IS the pre-registration:**

```bash
git add src/ah/presets/spine_pilot.json scripts/spine_pilot_seal.py docs/superpowers/specs/spine-pilot-prereg.json tests/test_gen_spine.py
git commit -m "feat(spine-01): PRE-REGISTRATION - world 802 + sealed B1-B6 bars; measurement not yet run"
```

---

### Task 7: The pilot report — B1, B2, B4, B5, B6, occupancy, sensitivity

**Files:**
- Create: `scripts/spine_pilot_report.py`
- Test: `tests/test_gen_spine.py` (append: the report's pure judging functions only — the full run is a script, not a test)

**Interfaces:**
- Consumes: everything above; `docs/superpowers/specs/spine-pilot-prereg.json`.
- Produces: `judge_b1(spine: SpinePaths, sealed) -> dict`, `judge_b2(ens, source, sealed) -> dict`, `judge_b4(spine, sealed) -> dict`, `judge_b5(ens_conditioning, sealed) -> dict`, `judge_b6(spine, sealed) -> dict` — each returns `{"pass": bool, "value": ..., "threshold": ...}`; `main()` prints an ASCII table and writes `docs/superpowers/specs/2026-08-15-spine-pilot-results.md`.

Judging formulas (fixed here, thresholds from the sealed JSON):

- **B1:** per decade, `dpol = np.diff(policy)`, `gap = (pi_star - mu_pi)[:-1]`; correlate `dpol[lag:]` with `gap[:-lag]` for lag in sealed `lag_months` range; decade passes if the max-|corr| lag has corr > 0. Fraction of decades passing >= `min_sign_fraction`.
- **B2:** joins from `row_indices` discontinuities; max |yoy jump| across all joins <= `join_yoy_max_pp` AND p95 of adjacent |Δyoy| (path-space, source-space yoy) <= `p95_ratio_max * panel_p95_adjacent_yoy_pp`.
- **B4:** spell lengths per regime from spine labels (reuse `ah.gen.regimes.semimarkov.spells_from_labels`); per-regime median ratio to sealed `panel_medians` inside the band; regimes the spine never visits with panel median > 0 count as FAIL rows (absence is an answer).
- **B5:** from the ensemble conditioning stamp: per-cell realized onset rate = `per_cell_onsets / per_cell_months` vs sealed `panel_rates`, relative error <= `rel_tolerance` for every cell with sealed `cell_months >= min_cell_months`.
- **B6:** spine-side: months with `policy - (r_star + pi_star) > 0` (the sealed spine threshold 0.0); of those, fraction followed by a contraction onset within `k_months`; compare to sealed `panel_conditional_onset_rate` within `rel_tolerance` — AND the conditional must exceed the sealed unconditional (the sign of transmission, not just its size).
- **Occupancy:** print `pool_occupancy` and every starved hazard cell — no silent caps.
- **Sensitivity:** re-run the world at 5 seeds `{199002 + 7919*j}`; every bar judged per seed; the report table shows per-seed verdicts and the ALL-seed conjunction. (This stands in for posterior-pin sensitivity at pilot price: each seed draws fresh posterior indices per decade by construction of `simulate_decades`.)

The run itself: `uv run python scripts/spine_pilot_report.py` (n_paths=20 per seed; ~minutes-scale, it is Euler simulation plus resampling — no training). Re-run the seal script FIRST to stamp the report hash (see Task 6's note), commit that, THEN run the report.

- [ ] **Step 1:** tests for `judge_b1` and `judge_b4` on constructed toy `SpinePaths` (a hand-built spine where policy visibly lags inflation by 6 months → B1 pass; a spine with 2-month spells vs panel medians ~8 → B4 fail). Watch them fail; implement; green.
- [ ] **Step 2:** implement the script; `ruff` + `pyright` clean.
- [ ] **Step 3:** re-run `scripts/spine_pilot_seal.py`; verify thresholds unchanged; commit `"feat(spine-01): seal report hash - pre-registration complete"`.
- [ ] **Step 4:** run the report; commit the results doc VERBATIM whatever it says: `"feat(spine-01): pilot measurement - B1..B6 verdicts as sealed"`.

---

### Task 8: B3 — the over-commitment grid under spine worlds

**Files:**
- Create: `scripts/spine_pilot_b3.py`
- Modify: `docs/superpowers/specs/2026-08-15-spine-pilot-results.md` (append the B3 section)

**Requirements source:** port the measurement method VERBATIM from the committed E1 declaration, `docs/superpowers/specs/2026-08-15-e1-overcommitment-measurement.md` — same four allocation arms (15/35/40/55 private), same 20 seeds, same coverage statistic (worst `unfunded/liquid`, breach line 1.0 from `ah.eval.decision_metrics` / the cov-01 constant), swapping only the world: 802 instead of the E1 doc's stress worlds. That document is the brief for this task; read it first. Judge with sealed `b3`: monotone coverage in allocation, >= 1/20 breach seeds at 55, hold-course depth inside the world's declared band (the `x_stress` segments' measured band from the stress-03 method).

- [ ] **Step 1:** write the script from the E1 doc's method; `ruff`/`pyright` clean.
- [ ] **Step 2:** run; append the B3 table + verdict to the results doc; commit verbatim.

---

### Task 9: Close-out — changelog, gate, verdict

- [ ] **Step 1:** `CHANGELOG.md`: the spine-01 entry — what was built, the six verdicts AS MEASURED, deviations from the spec with reasons (expected: pool conditioning on 2 of 3 cell dimensions if occupancy forced it — record it; the B6 spine-side threshold freeze).
- [ ] **Step 2:** full-tree `uv run ruff check . && uv run ruff format --check . && uv run pyright` — fix everything BEFORE the gate (the lint-before-the-long-gate rule).
- [ ] **Step 3:** `uv run python scripts/run_gate.py gate-spine-01.log` in the background; read the EXIT line and pass count from the file; `uv run python scripts/check_gate.py gate-spine-01.log`.
- [ ] **Step 4:** re-verify HEAD == the stamped commit (the owner merges onto branches mid-gate); merge `--no-ff` to main with a body reporting the verdicts; plain push.
- [ ] **Step 5:** report to the owner: the six verdicts, the occupancy table, and the D-SP-1..4 decisions now ready to take. **A FAIL on any bar is a successful pilot outcome** — say which layer failed and what the spec names as the repair. Do not propose weakening a bar.

---

## Self-review notes (writing-plans checklist, run 2026-08-15)

- Spec coverage: S→Task 2, H→Task 3, F→Task 4, dispatcher/contract→Tasks 1+5, seal §5→Task 6, B1/B2/B4/B5/B6→Task 7, B3→Task 8, refusal/occupancy §6→Tasks 2,4,7. Premise vocabulary kept to D-SP-3's minimum.
- Known deliberate narrowings (record, do not silently widen): pool conditioning uses era×growth (4 cells), hazard uses all 8 — spec §3.3 named eight for conditioning; occupancy measurement in Task 7 is the check that decides if this narrowing was right. `arrives_quarter` ge=1 (not ge=0) because the backdrop clause needs a pre-arrival window.
- Type consistency: `SpinePaths`, `HazardTable`, `SpineBootstrap`, `LAYER_OFFSETS`, `panel_yoy`, `spine_cell` names match across Tasks 2–7. `world.spine` / `world.stress` both required by `SpineBootstrap.sample`.
- The one interface the implementer must verify in-tree (named, not guessed): the slow-state record class carried by hier ensembles — follow `ah/gen/blocks/flow.py`'s import (Task 4).
