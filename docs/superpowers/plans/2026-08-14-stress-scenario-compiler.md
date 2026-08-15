# Stress-Scenario Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A generator (`bootstrap-stratified`) that compiles a declared stress scenario — regime shape plus a per-segment severity draw rule — into deterministic decades whose every month is a real historical month with real cross-asset co-movement.

**Architecture:** A stationary block bootstrap over the sealed 1953–2020 panel, differing from `bootstrap-v1` in one respect: which rows may *start* a block. Severity ranks rows by a declared functional; a block then runs forward through real history unfiltered, so autocorrelation is the real subsequent path rather than something modelled. Joins are restricted to rows whose level factors are near the current state, because nine of the fourteen factors are levels and splicing them teleports the credit spread.

**Tech Stack:** Python 3.12, numpy, pydantic, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md` — read §4 (mechanism) and §6 (acceptance) before Task 2.

## Global Constraints

- **`bootstrap-v1` is not modified, subclassed, or imported for its sampling logic.** `src/ah/gen/bootstrap.py` may be imported ONLY for `campaign_source` (panel loading) and `REGIME_LABELS`. If you find yourself importing `_draw_indices`, stop.
- **No sealed file is touched.** Before writing code, verify against all three locks: `grep -l "<file>" pre-registration.lock pre-registration-g3.lock pre-registration-g5.lock` must return nothing for every file you modify. This has cost the project twice.
- **Severity applies to block ENTRY only.** A row-by-row severity filter is forbidden — it destroys the autocorrelation the compiler exists to preserve.
- **Depth is emergent and must never be tuned to a portfolio outcome.** No parameter in this build may be chosen by looking at forced-secondary counts. Task 7 measures; it never calibrates.
- **Commit order is the pre-registration:** the scenario file (Task 5) lands in an earlier commit than the institutional measurement (Task 7). Do not reorder.
- Determinism: all randomness from `np.random.Generator(np.random.PCG64(seed))`. No global RNG, no clock.
- No network in tests (`pytest-socket`); ASCII in any CLI-echoed string.
- Branch `stress-01-scenario-compiler`; full gate to a log; log read as its own step; `scripts/check_gate.py` stamps `.gate-ok`; merge `--no-ff`; plain push.
- Definition of done per WP: acceptance tests pass, full suite green, ruff + pyright clean, `CHANGELOG.md` updated.

## File map

- Create: `src/ah/gen/stress.py` — the generator: severity ranking, join discipline, sampler, `StressBootstrap`
- Create: `tests/test_gen_stress.py` — all generator tests
- Modify: `src/ah/core/worldspec.py` — `StressSpec`/`StressSegment` models (with the other WorldSpec models)
- Modify: `src/ah/core/numericworld.py` — project `stress` onto `NumericWorld`
- Modify: `tests/test_worldspec.py` — projection tests
- Create: `src/ah/presets/stress_1974.json` — the first declared scenario
- Modify: `src/ah/gen/registry.py` — registration (or wherever `bootstrap-v1` registers; check first)
- Create: `scripts/stress_report.py` — emergent-depth and coherence reports
- Modify: `CHANGELOG.md`

---

### Task 1: The scenario contract, typed onto NumericWorld

**Files:**
- Modify: `src/ah/core/worldspec.py`
- Modify: `src/ah/core/numericworld.py`
- Test: `tests/test_worldspec.py`

**Interfaces:**
- Produces: `StressSpec(functional: str, segments: list[StressSegment], join_tolerance: dict[str, float], precedent: list[str])`; `StressSegment(from_quarter: int, to_quarter: int, entry_percentile: float, mean_block_months: int)`; `NumericWorld.stress: StressSpec | None`; `project_numeric` reads `world.extensions["x_stress"]`.

**Why typed rather than a raw dict:** `NumericWorld` is the narrative-blind projection — it structurally omits `narrative`. Projecting `extensions` wholesale would let any `x_` key reach the engine, including narrative text. A typed whitelist keeps the invariant crisp.

- [ ] **Step 1: Write the failing tests** in `tests/test_worldspec.py`:

```python
def test_stress_spec_projects_onto_numericworld():
    doc = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    doc["extensions"] = {
        **(doc.get("extensions") or {}),
        "x_stress": {
            "functional": "all_down",
            "segments": [
                {"from_quarter": 0, "to_quarter": 19, "entry_percentile": 35,
                 "mean_block_months": 18},
                {"from_quarter": 20, "to_quarter": 39, "entry_percentile": 100,
                 "mean_block_months": 12},
            ],
            "join_tolerance": {"hy_spread": 1.5},
            "precedent": ["2007-09 ran -50% over 17 months"],
        },
    }
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.stress is not None
    assert nw.stress.functional == "all_down"
    assert nw.stress.segments[0].entry_percentile == 35
    assert nw.stress.join_tolerance["hy_spread"] == 1.5


def test_a_world_without_x_stress_projects_none():
    """Every existing world must keep working: stress is optional."""
    doc = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.stress is None


def test_stress_segments_must_tile_the_horizon_exactly():
    """A gap would leave months with no declared severity; an overlap would make
    the draw rule ambiguous. Both are author errors and must fail loudly."""
    base = {"functional": "all_down", "join_tolerance": {}, "precedent": ["x"]}
    gap = {**base, "segments": [
        {"from_quarter": 0, "to_quarter": 10, "entry_percentile": 35, "mean_block_months": 18},
        {"from_quarter": 12, "to_quarter": 39, "entry_percentile": 100, "mean_block_months": 12},
    ]}
    with pytest.raises(ValidationError, match="tile"):
        StressSpec.model_validate(gap)

    overlap = {**base, "segments": [
        {"from_quarter": 0, "to_quarter": 20, "entry_percentile": 35, "mean_block_months": 18},
        {"from_quarter": 20, "to_quarter": 39, "entry_percentile": 100, "mean_block_months": 12},
    ]}
    with pytest.raises(ValidationError, match="tile"):
        StressSpec.model_validate(overlap)


def test_unknown_severity_functional_is_refused():
    spec = {"functional": "vibes", "join_tolerance": {}, "precedent": ["x"],
            "segments": [{"from_quarter": 0, "to_quarter": 39,
                          "entry_percentile": 10, "mean_block_months": 18}]}
    with pytest.raises(ValidationError):
        StressSpec.model_validate(spec)
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `uv run pytest tests/test_worldspec.py -k stress -q`
Expected: FAIL — `StressSpec` is not defined.

- [ ] **Step 3: Implement the models** in `src/ah/core/worldspec.py`, next to `Regimes`:

```python
SeverityFunctional = Literal["equity", "joint_risk", "all_down"]


class StressSegment(_Base):
    """One segment of a declared stress scenario.

    ``entry_percentile`` restricts which rows may START a block during this
    segment: 10 means "the worst decile by the declared functional", 100 means
    unrestricted. It is NOT a filter on every month — see the design note §4.3.
    """

    from_quarter: int = Field(ge=0)
    to_quarter: int = Field(ge=0)
    entry_percentile: float = Field(gt=0.0, le=100.0)
    mean_block_months: int = Field(ge=1, le=120)


class StressSpec(_Base):
    """A declared stress scenario: severity by segment, and its precedent."""

    functional: SeverityFunctional
    segments: list[StressSegment] = Field(min_length=1)
    join_tolerance: dict[str, float] = Field(default_factory=dict)
    precedent: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _segments_tile(self) -> StressSpec:
        ordered = sorted(self.segments, key=lambda s: s.from_quarter)
        for seg in ordered:
            if seg.to_quarter < seg.from_quarter:
                raise ValueError(f"segment {seg.from_quarter}-{seg.to_quarter} runs backwards")
        for prev, nxt in zip(ordered, ordered[1:], strict=False):
            if nxt.from_quarter != prev.to_quarter + 1:
                raise ValueError(
                    "stress segments must tile the horizon with no gap or overlap; "
                    f"{prev.to_quarter} is followed by {nxt.from_quarter}"
                )
        if ordered[0].from_quarter != 0:
            raise ValueError("stress segments must tile the horizon from quarter 0")
        return self
```

- [ ] **Step 4: Project it** in `src/ah/core/numericworld.py` — add the field to the dataclass and read it in `project_numeric`:

```python
    stress: StressSpec | None = None
```

```python
def _stress_of(world: WorldSpec) -> StressSpec | None:
    """The declared stress scenario, or None.

    Only `x_stress` is projected — NOT the whole extensions dict. NumericWorld
    is the narrative-blind projection, and a free-form dict would be a channel
    for narrative to reach the engine.
    """
    ext = world.extensions or {}
    raw = ext.get("x_stress")
    return None if raw is None else StressSpec.model_validate(raw)
```

- [ ] **Step 5: Green, then the whole worldspec + narrative-blindness suites.**

Run: `uv run pytest tests/test_worldspec.py tests/test_narrative_blindness.py -q`
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add src/ah/core/worldspec.py src/ah/core/numericworld.py tests/test_worldspec.py
git commit -m "feat(stress-01): typed x_stress scenario contract projected onto NumericWorld"
```

---

### Task 2: Severity ranking

**Files:**
- Create: `src/ah/gen/stress.py`
- Test: `tests/test_gen_stress.py`

**Interfaces:**
- Consumes: nothing from Task 1 (pure numpy).
- Produces: `severity_score(values: np.ndarray, factor_names: Sequence[str], functional: str) -> np.ndarray` — one score per row, **lower is more severe**; `eligible_rows(scores: np.ndarray, percentile: float) -> np.ndarray` — sorted row indices at or below the percentile.

The three functionals, and why `all_down` is the default: ranking by equity alone would draw October 2008, when Treasuries rallied hard and handed the institution a liquid leg to sell. Flight-to-quality is the escape valve a stress test must be able to close.

- [ ] **Step 1: Write the failing tests:**

```python
"""The stress-scenario compiler (bootstrap-stratified)."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.stress import eligible_rows, severity_score

NAMES = ["equity_mkt", "hy_spread", "ust_10y", "cpi"]


def _panel() -> np.ndarray:
    """Four hand-built months. Row 0 calm; row 1 equity crash WITH a bond rally
    (2008-shaped); row 2 everything down together (2022-shaped); row 3 mild."""
    return np.array([
        [+0.01, 3.0, 4.0, 100.0],   # calm
        [-0.15, 9.0, 2.0, 100.0],   # equity -15%, spreads wide, yields FALL (rally)
        [-0.08, 7.0, 6.0, 100.0],   # equity -8%, spreads wide, yields RISE (no bid)
        [-0.01, 3.5, 4.1, 100.0],   # mild
    ])


def test_equity_functional_ranks_the_deepest_equity_month_worst():
    s = severity_score(_panel(), NAMES, "equity")
    assert int(np.argmin(s)) == 1  # -15% is the worst equity month


def test_all_down_prefers_the_month_with_no_flight_to_quality_bid():
    """The point of the default. Row 1 is a deeper equity fall, but bonds
    rallied, so the institution can still sell its liquid leg. Row 2 is
    shallower and has no hiding place, which is what breaks an illiquid book."""
    s = severity_score(_panel(), NAMES, "all_down")
    assert int(np.argmin(s)) == 2
    assert s[2] < s[1]


def test_joint_risk_uses_equity_and_credit_only_and_ignores_the_bond_leg():
    s = severity_score(_panel(), NAMES, "joint_risk")
    assert int(np.argmin(s)) == 1  # deepest equity + widest spread


def test_severity_is_deterministic():
    a = severity_score(_panel(), NAMES, "all_down")
    b = severity_score(_panel(), NAMES, "all_down")
    np.testing.assert_array_equal(a, b)


def test_eligible_rows_are_the_worst_share_and_100_is_unrestricted():
    scores = np.array([5.0, 1.0, 3.0, 4.0, 2.0])
    assert eligible_rows(scores, 40.0).tolist() == [1, 4]     # worst two of five
    assert eligible_rows(scores, 100.0).tolist() == [0, 1, 2, 3, 4]


def test_eligible_rows_never_returns_an_empty_pool():
    """A percentile so tight it selects nothing would make the segment
    unsamplable. The floor is one row — the single worst."""
    scores = np.array([5.0, 1.0, 3.0])
    assert eligible_rows(scores, 0.001).tolist() == [1]


def test_unknown_functional_is_refused_by_name():
    with pytest.raises(ValueError, match="vibes"):
        severity_score(_panel(), NAMES, "vibes")
```

- [ ] **Step 2: Watch them fail.**

Run: `uv run pytest tests/test_gen_stress.py -q`
Expected: FAIL — no module `ah.gen.stress`.

- [ ] **Step 3: Implement.** Scores are z-scored per factor so units don't dominate; lower is more severe.

```python
def _z(column: np.ndarray) -> np.ndarray:
    sd = float(column.std())
    if sd == 0.0:
        return np.zeros_like(column)
    return (column - float(column.mean())) / sd


def severity_score(
    values: np.ndarray, factor_names: Sequence[str], functional: str
) -> np.ndarray:
    """One severity score per row; LOWER IS MORE SEVERE.

    Components are z-scored so a spread in percentage points cannot dominate a
    return in decimals. Credit and yields enter NEGATED: a wide spread and a
    rising yield are both adverse, so negating them puts "bad" at the bottom
    alongside a negative equity return.
    """
    names = list(factor_names)
    x = np.asarray(values, dtype=np.float64)

    def col(name: str) -> np.ndarray:
        if name not in names:
            raise ValueError(f"panel has no factor '{name}'; available: {names}")
        return x[:, names.index(name)]

    equity = _z(col("equity_mkt"))
    if functional == "equity":
        return equity
    credit = -_z(col("hy_spread"))
    if functional == "joint_risk":
        return equity + credit
    if functional == "all_down":
        # a RISING long yield is adverse (no flight-to-quality bid), so the
        # bond leg enters negated exactly as credit does
        return equity + credit + -_z(col("ust_10y"))
    raise ValueError(
        f"unknown severity functional '{functional}'; known: equity, joint_risk, all_down"
    )


def eligible_rows(scores: np.ndarray, percentile: float) -> np.ndarray:
    """Row indices whose severity is at or below ``percentile`` (100 = all).

    Never empty: a percentile tight enough to select nothing would make its
    segment unsamplable, so the single worst row is the floor.
    """
    s = np.asarray(scores, dtype=np.float64)
    if percentile >= 100.0:
        return np.arange(s.size, dtype=np.int64)
    keep = max(1, int(np.floor(s.size * percentile / 100.0)))
    return np.sort(np.argsort(s, kind="stable")[:keep]).astype(np.int64)
```

- [ ] **Step 4: Green.**

Run: `uv run pytest tests/test_gen_stress.py -q`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/ah/gen/stress.py tests/test_gen_stress.py
git commit -m "feat(stress-01): severity functionals - equity, joint_risk, all_down (TDD)"
```

---

### Task 3: Join discipline

**Files:**
- Modify: `src/ah/gen/stress.py`
- Test: `tests/test_gen_stress.py`

**Interfaces:**
- Produces: `LEVEL_FACTORS: tuple[str, ...]`; `join_candidates(values, factor_names, current_row: int, tolerance: Mapping[str, float], pool: np.ndarray) -> np.ndarray`.

Nine of the sealed fourteen factors are levels: `equity_vol`, `ig_spread`, `hy_spread`, `policy_rate`, `ust_2y`, `ust_10y`, `cpi`, `hqm_curve`, `funding_spread`. Splicing returns is harmless; splicing levels teleports the credit spread from 300bp to 1400bp in one month.

- [ ] **Step 1: Write the failing tests:**

```python
def test_join_candidates_exclude_a_spread_teleport():
    """From a 3.0 spread with a 1.5 tolerance, a 9.0 row is unreachable."""
    values, names = _panel(), NAMES
    pool = np.array([0, 1, 2, 3], dtype=np.int64)
    got = join_candidates(values, names, current_row=0, tolerance={"hy_spread": 1.5}, pool=pool)
    assert 1 not in got.tolist()   # 9.0 vs 3.0 is a 6.0 jump
    assert 3 in got.tolist()       # 3.5 vs 3.0 is within tolerance


def test_join_candidates_apply_every_named_factor():
    values, names = _panel(), NAMES
    pool = np.array([0, 1, 2, 3], dtype=np.int64)
    loose = join_candidates(values, names, 0, {"hy_spread": 10.0}, pool)
    tight = join_candidates(values, names, 0, {"hy_spread": 10.0, "ust_10y": 0.5}, pool)
    assert set(tight.tolist()) < set(loose.tolist())


def test_an_untoleranced_factor_does_not_constrain():
    values, names = _panel(), NAMES
    pool = np.array([0, 1, 2, 3], dtype=np.int64)
    got = join_candidates(values, names, 0, {}, pool)
    np.testing.assert_array_equal(got, pool)


def test_join_candidates_may_be_empty_and_the_caller_decides():
    """An empty candidate set is a real state: nothing severe is reachable from
    here without teleporting. The sampler CONTINUES the block rather than
    jumping (Task 4) — severity is a preference over entries, never a licence
    to teleport."""
    values, names = _panel(), NAMES
    pool = np.array([1], dtype=np.int64)
    got = join_candidates(values, names, 0, {"hy_spread": 0.1}, pool)
    assert got.size == 0
```

- [ ] **Step 2: Watch them fail.** Run: `uv run pytest tests/test_gen_stress.py -k join -q`

- [ ] **Step 3: Implement:**

```python
#: Of the sealed 14-factor panel, these nine are LEVELS rather than increments.
#: Splicing a level at a block join teleports it; splicing a return does not.
LEVEL_FACTORS: tuple[str, ...] = (
    "equity_vol", "ig_spread", "hy_spread", "policy_rate",
    "ust_2y", "ust_10y", "cpi", "hqm_curve", "funding_spread",
)


def join_candidates(
    values: np.ndarray,
    factor_names: Sequence[str],
    current_row: int,
    tolerance: Mapping[str, float],
    pool: np.ndarray,
) -> np.ndarray:
    """Rows in ``pool`` reachable from ``current_row`` without a level teleport.

    A factor with no declared tolerance does not constrain. May return an empty
    array; the caller decides what to do (the sampler continues the block).
    """
    names = list(factor_names)
    x = np.asarray(values, dtype=np.float64)
    keep = np.ones(pool.size, dtype=bool)
    for factor, tol in tolerance.items():
        if factor not in names:
            raise ValueError(f"join tolerance names unknown factor '{factor}'")
        column = x[:, names.index(factor)]
        keep &= np.abs(column[pool] - column[int(current_row)]) <= float(tol)
    return pool[keep]
```

- [ ] **Step 4: Green.** Run: `uv run pytest tests/test_gen_stress.py -q`

- [ ] **Step 5: Commit.**

```bash
git add src/ah/gen/stress.py tests/test_gen_stress.py
git commit -m "feat(stress-01): join discipline - no level teleports across block seams"
```

---

### Task 4: The sampler and the generator

**Files:**
- Modify: `src/ah/gen/stress.py`
- Test: `tests/test_gen_stress.py`

**Interfaces:**
- Consumes: `StressSpec` (Task 1), `severity_score`/`eligible_rows` (Task 2), `join_candidates` (Task 3), `ah.gen.bootstrap.campaign_source` and `REGIME_LABELS` (panel loading only).
- Produces: `class StressBootstrap` with `generator_id = "bootstrap-stratified"`, `fit(source)`, `sample(world, n_paths, seed) -> Ensemble`, `sample_months(months, n_paths, seed, *, world)`.

- [ ] **Step 1: Write the failing tests.** These four carry the spec's central claims (§6.1):

```python
def _tiny_source():
    """A BootstrapSource whose every column is injective in the row index, so
    'this month IS that historical month' can be checked exactly rather than
    statistically — the technique tests/test_bootstrap.py uses."""
    import pandas as pd
    from ah.gen.bootstrap import BootstrapSource

    n = 60
    rows = np.arange(n, dtype=np.float64)
    values = np.column_stack([rows, rows + 1000.0, rows + 2000.0, rows + 3000.0])
    return BootstrapSource(
        factor_names=("equity_mkt", "hy_spread", "ust_10y", "cpi"),
        dates=pd.date_range("1960-01-31", periods=n, freq="ME"),
        values=values,
        labels=tuple(["EXP"] * n),
        ruleset_version="test",
        vintage_id="test-vintage",
        active_blocks=("global",),
    )


def _spec(entry_percentile=100.0, mean_block_months=6, tolerance=None):
    from ah.core.worldspec import StressSegment, StressSpec

    return StressSpec(
        functional="all_down",
        segments=[StressSegment(from_quarter=0, to_quarter=39,
                                entry_percentile=entry_percentile,
                                mean_block_months=mean_block_months)],
        join_tolerance=tolerance or {},
        precedent=["test"],
    )


def test_every_emitted_month_is_a_real_panel_row():
    """THE claim. Bit-exact on the whole factor vector, not approximately."""
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(120, 8, seed=11, stress=_spec())
    src = gen.source.values
    for p in range(ens.n_paths):
        for m in range(ens.months):
            row = int(ens.row_indices[p, m])
            np.testing.assert_array_equal(ens.paths[p, m, :], src[row, :])


def test_blocks_are_contiguous_runs_of_whole_rows():
    """Co-movement is real because a block is ONE shared row index across every
    factor, advancing by one month at a time."""
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(120, 8, seed=11, stress=_spec())
    idx = ens.row_indices
    n = gen.source.n_rows
    steps = (idx[:, 1:] - idx[:, :-1]) % n
    continued = steps == 1
    assert continued.mean() > 0.5, "most months must continue a block, not restart it"


def test_same_seed_same_tape():
    gen = StressBootstrap(_tiny_source())
    a = gen.sample_months(60, 4, seed=7, stress=_spec())
    b = gen.sample_months(60, 4, seed=7, stress=_spec())
    np.testing.assert_array_equal(a.paths, b.paths)
    c = gen.sample_months(60, 4, seed=8, stress=_spec())
    assert not np.array_equal(a.paths, c.paths)


def test_restarts_land_in_the_severity_pool():
    """Severity binds where it is supposed to: on ENTRY. Every restart row must
    be in the declared pool; continuation rows need not be."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    spec = _spec(entry_percentile=20.0)
    ens = gen.sample_months(120, 8, seed=3, stress=spec)
    pool = set(eligible_rows(
        severity_score(source.values, source.factor_names, "all_down"), 20.0).tolist())
    idx = ens.row_indices
    n = source.n_rows
    for p in range(idx.shape[0]):
        assert int(idx[p, 0]) in pool
        for m in range(1, idx.shape[1]):
            if (int(idx[p, m]) - int(idx[p, m - 1])) % n != 1:
                assert int(idx[p, m]) in pool, "a restart landed outside the severity pool"


def test_a_block_continues_rather_than_teleporting_when_no_join_is_reachable():
    """With an impossibly tight tolerance nothing is reachable, so the sampler
    must keep advancing through real history rather than jumping."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    ens = gen.sample_months(60, 4, seed=5,
                            stress=_spec(entry_percentile=20.0, tolerance={"hy_spread": 0.0}))
    idx = ens.row_indices
    n = source.n_rows
    steps = (idx[:, 1:] - idx[:, :-1]) % n
    assert bool(np.all(steps == 1)), "no join was reachable; every month must continue"


def test_the_ensemble_stamps_the_scenario_for_audit():
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(60, 4, seed=5, stress=_spec(entry_percentile=15.0))
    c = ens.meta.conditioning
    assert ens.meta.generator_id == "bootstrap-stratified"
    assert c["functional"] == "all_down"
    assert c["segments"][0]["entry_percentile"] == 15.0
    assert c["pool_sizes"][0] > 0
    assert c["factor_conditions_honoured"] is False
```

- [ ] **Step 2: Watch them fail.** Run: `uv run pytest tests/test_gen_stress.py -q`

- [ ] **Step 3: Implement the sampler.** The restart rule mirrors the stationary block bootstrap — fresh start at month 0, thereafter with probability `1/mean_block_months`, otherwise `(previous + 1) mod T`. The circular wrap is deliberate. What differs from `bootstrap-v1` is only *which rows a fresh start may land on*:

```python
class StressBootstrap:
    """The stress-scenario compiler. Implements ah.gen.base.Generator."""

    generator_id = "bootstrap-stratified"

    def __init__(self, source: BootstrapSource | None = None) -> None:
        self._source = source

    @property
    def source(self) -> BootstrapSource:
        if self._source is None:
            raise StressError("bootstrap-stratified is not fitted; call fit(campaign_source())")
        return self._source

    def fit(self, data: Any) -> None:
        if not isinstance(data, BootstrapSource):
            raise StressError(
                f"fit expects a BootstrapSource (see ah.gen.bootstrap.campaign_source); "
                f"got {type(data).__name__}"
            )
        self._source = data

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        if world.stress is None:
            raise StressError(
                f"world '{world.world_id}' selects bootstrap-stratified but declares no "
                "extensions.x_stress; a stress world must declare its severity rule"
            )
        months = int(world.horizon.quarters) * 3
        return self.sample_months(months, n_paths, seed, world=world, stress=world.stress)

    def sample_months(self, months, n_paths, seed, *, world=None, stress=None) -> Ensemble:
        source = self.source
        if stress is None:
            raise StressError("bootstrap-stratified requires a StressSpec")
        months, n_paths = int(months), int(n_paths)
        if months < 1 or n_paths < 1:
            raise StressError(f"months and n_paths must be >= 1; got {months}, {n_paths}")

        scores = severity_score(source.values, source.factor_names, stress.functional)
        # month -> (pool, restart probability) from the segment covering it
        pools: list[np.ndarray] = []
        probs: list[float] = []
        per_segment_pool: dict[int, np.ndarray] = {}
        for m in range(months):
            quarter = m // 3
            seg = _segment_for(stress, quarter)
            key = seg.from_quarter
            if key not in per_segment_pool:
                per_segment_pool[key] = eligible_rows(scores, seg.entry_percentile)
            pools.append(per_segment_pool[key])
            probs.append(1.0 / float(seg.mean_block_months))

        index = self._draw(source, months, n_paths, seed, pools, probs, stress.join_tolerance)
        paths = source.values[index]

        label_codes = {label: i for i, label in enumerate(REGIME_LABELS)}
        source_codes = np.array([label_codes[l] for l in source.labels], dtype=np.int64)

        conditioning = {
            "mode": "declared-stress-scenario",
            "functional": stress.functional,
            "segments": [
                {"from_quarter": s.from_quarter, "to_quarter": s.to_quarter,
                 "entry_percentile": s.entry_percentile,
                 "mean_block_months": s.mean_block_months}
                for s in stress.segments
            ],
            "pool_sizes": [int(per_segment_pool[s.from_quarter].size) for s in stress.segments],
            "join_tolerance": dict(stress.join_tolerance),
            "precedent": list(stress.precedent),
            "ruleset_version": source.ruleset_version,
            "block_draw_span": {
                "start": str(source.dates[0].date()),
                "end": str(source.dates[-1].date()),
                "months": source.n_rows,
            },
            # This generator honours no factor_conditions either: severity is
            # declared through x_stress, not through an inflation average.
            "factor_conditions_honoured": False,
        }
        meta = EnsembleMeta(
            generator_id=self.generator_id, vintage_id=source.vintage_id, seed=int(seed),
            n_paths=n_paths, months=months, conditioning=conditioning,
            active_blocks=tuple(source.active_blocks),
        )
        return Ensemble(
            paths=paths, factor_names=list(source.factor_names), meta=meta, row_indices=index,
            regimes=RegimeRecord(labels=source_codes[index], legend=REGIME_LABELS,
                                 mode="realized-declared-stress",
                                 ruleset_version=source.ruleset_version),
            slow_states=AbsentLayer(reason="a resampler has no slow-state layer"),
        )

    def _draw(self, source, months, n_paths, seed, pools, probs, tolerance) -> np.ndarray:
        rng = np.random.Generator(np.random.PCG64(int(seed)))
        n = source.n_rows
        index = np.empty((n_paths, months), dtype=np.int64)

        first = pools[0]
        index[:, 0] = first[rng.integers(0, first.size, size=n_paths)]
        draws = rng.random((n_paths, months))
        for m in range(1, months):
            pool = pools[m]
            for p in range(n_paths):
                previous = int(index[p, m - 1])
                advanced = (previous + 1) % n
                if draws[p, m] >= probs[m]:
                    index[p, m] = advanced
                    continue
                candidates = join_candidates(
                    source.values, source.factor_names, previous, tolerance, pool
                )
                # Severity is a preference over entries, never a licence to
                # teleport: with nothing reachable the block simply continues.
                index[p, m] = (
                    advanced if candidates.size == 0
                    else int(candidates[rng.integers(0, candidates.size)])
                )
        return index
```

Add `_segment_for(stress, quarter)` returning the covering segment, and a `StressError(ValueError)`.

- [ ] **Step 4: Green, and check the RNG draw is shape-stable** (the per-path loop must consume `draws` positionally so a path's tape does not depend on `n_paths`).

Run: `uv run pytest tests/test_gen_stress.py -q`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/ah/gen/stress.py tests/test_gen_stress.py
git commit -m "feat(stress-01): the sampler - severity on entry, real history forward, no teleports"
```

---

### Task 5: Registration and the first declared scenario

**Files:**
- Modify: `src/ah/gen/registry.py` (or wherever `bootstrap-v1` registers — `grep -rn "register(\"bootstrap-v1\"" src/` first)
- Create: `src/ah/presets/stress_1974.json`
- Test: `tests/test_gen_stress.py`

**This is the commit that pre-registers the scenario. Task 7's measurement must land in a later commit.**

- [ ] **Step 1: Create the preset** by copying `stagflation_1974.json` and changing exactly three things — `world_id` to a new block so leaderboards fence, `generator_id` to `bootstrap-stratified`, and the added `extensions.x_stress`:

```json
"x_stress": {
  "functional": "all_down",
  "segments": [
    {"from_quarter": 0,  "to_quarter": 15, "entry_percentile": 35, "mean_block_months": 18},
    {"from_quarter": 16, "to_quarter": 19, "entry_percentile": 10, "mean_block_months": 18},
    {"from_quarter": 20, "to_quarter": 31, "entry_percentile": 35, "mean_block_months": 18},
    {"from_quarter": 32, "to_quarter": 39, "entry_percentile": 100, "mean_block_months": 12}
  ],
  "join_tolerance": {"hy_spread": 1.5, "policy_rate": 1.0},
  "precedent": [
    "crisis entry at the worst decile: 2007-09 ran -50% over 17 months",
    "1973-74 ran -48% over 21 months with inflation above 10%",
    "all_down: 2022 ran equities and bonds down together, with no flight-to-quality bid",
    "stagflation entry at the worst third: 1973-82 spent most of a decade below trend"
  ]
}
```

- [ ] **Step 2: Test that the world builds, samples and replays:**

```python
def test_the_stress_preset_builds_samples_and_replays(tmp_path):
    doc = json.loads((PRESETS / "stress_1974.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    assert nw.engine_defaults.generator_id == "bootstrap-stratified"
    assert nw.stress is not None and nw.stress.functional == "all_down"
    gen = StressBootstrap(_tiny_source())
    a = gen.sample(nw, n_paths=4, seed=197400)
    b = gen.sample(nw, n_paths=4, seed=197400)
    np.testing.assert_array_equal(a.paths, b.paths)


def test_a_stress_world_without_a_declared_rule_is_refused():
    doc = json.loads((PRESETS / "stagflation_1974.json").read_text(encoding="utf-8"))
    doc["engine_defaults"]["generator_id"] = "bootstrap-stratified"
    nw = project_numeric(WorldSpec.model_validate(doc))
    with pytest.raises(StressError, match="x_stress"):
        StressBootstrap(_tiny_source()).sample(nw, n_paths=2, seed=1)
```

- [ ] **Step 3: Register** the factory alongside `bootstrap-v1`'s, resolving the source through `campaign_source()`.

- [ ] **Step 4: Green; ruff + pyright clean.**

- [ ] **Step 5: Commit — the scenario and its precedent, and NOTHING measured on it.**

```bash
git add src/ah/presets/stress_1974.json src/ah/gen/registry.py tests/test_gen_stress.py
git commit -m "feat(stress-01): declare the stress_1974 scenario - rule and precedent, unmeasured

Commit order IS the pre-registration (design note S7): this commit declares the
severity rule and the historical precedent cited for it. Nothing has been run
through the institution yet. The measurement lands in a later commit so the
record shows the rule was not chosen by looking at the answer."
```

---

### Task 6: The reports — emergent depth and coherence

**Files:**
- Create: `scripts/stress_report.py`
- Test: `tests/test_gen_stress.py`

**Interfaces:**
- Produces: `depth_report(ensemble) -> dict` with `median_peak_to_trough`, `median_drawdown_months`, `hy_spread_peak`; `coherence_report(ensemble, source) -> dict` with `ac1_generated`, `ac1_panel`, `join_count`, `max_level_jump`.

These are measurements printed for argument, not thresholds that gate. §6.2.

- [ ] **Step 1: Write the failing tests:**

```python
def test_depth_report_reads_the_ensemble_it_is_given():
    gen = StressBootstrap(_tiny_source())
    ens = gen.sample_months(120, 8, seed=2, stress=_spec())
    d = depth_report(ens)
    assert set(d) >= {"median_peak_to_trough", "median_drawdown_months", "hy_spread_peak"}
    assert d["median_peak_to_trough"] <= 0.0


def test_coherence_report_compares_autocorrelation_against_the_panel():
    """A shuffle of the same months would score far below the panel; a block
    resample should land near it. This is the test that catches (a)/(b) of the
    design note breaking."""
    source = _tiny_source()
    gen = StressBootstrap(source)
    ens = gen.sample_months(120, 8, seed=2, stress=_spec(mean_block_months=24))
    c = coherence_report(ens, source)
    assert c["join_count"] >= 0
    assert abs(c["ac1_generated"] - c["ac1_panel"]) < 0.35
```

- [ ] **Step 2: Watch fail. Step 3: Implement** — lag-1 autocorrelation of `equity_mkt` pooled across paths for `ac1_generated`, the same statistic on `source.values` for `ac1_panel`, `join_count` from `row_indices` steps not equal to 1, `max_level_jump` the largest `hy_spread` change at a join.

- [ ] **Step 4: Green. Step 5: Commit.**

```bash
git add scripts/stress_report.py tests/test_gen_stress.py
git commit -m "feat(stress-01): emergent-depth and coherence reports (measurements, not gates)"
```

---

### Task 7: Measure the institution — after the rule is committed

**Files:** none committed except the recorded numbers in `CHANGELOG.md` and the commit body.

**This task MUST land in a later commit than Task 5. That ordering is the whole honesty mechanism.**

- [ ] **Step 1: Build and run the world.** `uv run ah world build --preset stress_1974`, then `uv run ah run --paths 1000`, then `uv run ah replay` (must print MATCH).
- [ ] **Step 2: Report emergent depth** via `scripts/stress_report.py` — median peak-to-trough, duration, spread peak — and write them beside the precedent claims from the preset. State whether the produced depth is consistent with the episodes cited.
- [ ] **Step 3: Console walk.** `uv run ah credibility --preset stress_1974 --out stress.html`. Record every flagged statistic and its value.
- [ ] **Step 4: Measure the adequacy ladder, once.** Coverage breaches, forced secondaries, ruinous seeds across 20 seeds. Reference shape: 20/20 coverage breached, 4–8/20 forced secondary, 1+ ruinous.
- [ ] **Step 5: Record the result — and DO NOT TUNE.**

If the ladder disappoints, the only permitted response is to re-examine the severity rule against historical precedent and, if the rule is genuinely milder than the episodes cited, amend the rule *with its precedent* in a fresh commit and re-measure. **Changing a percentile because the forced-secondary count was disappointing is the circularity this design exists to prevent, and it is forbidden.** A 0/20 reading is a finding with two honest readings — the rule is milder than its precedent, or the institution is genuinely robust — and both go in the record.

---

### Task 8: Disclosure, changelog, gate, merge

- [ ] **Step 1: Disclosure** — add a section to the methodology note stating that these worlds are prescribed and severe rather than predicted; that severity is a declared sampling rule; that depth is emergent and reported after the fact; and that the compiler has no reaction function and explains nothing causally.
- [ ] **Step 2: CHANGELOG** — the generator, the scenario, the measured depth, the ladder result, and the commit-order discipline.
- [ ] **Step 3: Full gate to `gate-stress-01.log` in the background; READ the log as its own step** (`EXIT:` line and pass count).
- [ ] **Step 4:** `uv run python scripts/check_gate.py gate-stress-01.log`; verify `git rev-parse HEAD` matches the stamp; merge `--no-ff`; push.

---

## Self-review notes

- **Spec coverage:** §1 object → Tasks 4/5 (`factor_conditions_honoured: False`, disclosure in 8); §2 defect → the whole build; §4.1 shape → Task 1 segments; §4.2 severity → Task 2; §4.3 coherence → Tasks 3, 4 and the coherence report in 6; §5 contracts → Tasks 1, 4, 5; §6.1 properties → Task 4's four tests; §6.2 reports → Task 6; §7 commit order → Tasks 5 and 7 and their ordering constraint; §8 disclosure → Task 8; §9 out of scope → nothing here touches the draw span, `bootstrap-v1`, or JST.
- **One spec item deliberately deferred:** §10's open questions on block length and join tolerance are settled empirically in Task 7's report rather than guessed here — the plan starts them at 18 months and `{hy_spread: 1.5, policy_rate: 1.0}` and measures.
- **Risks:** (a) the per-path Python loop in `_draw` is O(paths × months) with a `join_candidates` call per restart — if 1000 paths × 120 months is slow, vectorise by precomputing a reachability matrix per pool, but only after the tests pass; (b) `campaign_source()` requires the local catalog, so the registered factory must fail clearly when `data/` is absent, as `bootstrap-v1`'s does; (c) if the severity pool for a tight percentile is smaller than the number of paths, many paths share a start row — expected and not a defect, but worth noting in the depth report.
