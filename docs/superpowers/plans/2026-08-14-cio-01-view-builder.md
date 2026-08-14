# CIO-01: View Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A server-side `build_cio_view()` and `GET /sessions/{sid}/cio` endpoint producing a validated, deterministic `CioView` payload — the data layer the CIO dashboard renderer (cio-02) will consume.

**Architecture:** A pure Python builder (`ah/cioview.py`) over the replayed session state, following the `_mark_to_market` precedent in `ah/serve.py` — the server is the authority for value (DN-3 W5). History AND mechanical forecast come from one `simulate_play` run over a "frozen tape" (revealed months verbatim + flat appended months), so the forecast is DN-8's roll-forward by construction. A Python port of `validateCioView` is the CI authority for the contract.

**Tech Stack:** Python 3.12, FastAPI, numpy, pytest (existing stack — no new dependencies).

**Spec:** `docs/superpowers/specs/2026-08-14-cio-dashboard-design.md` (read it first; DN-8 in `docs/CIO Dashboard.zip` is the contract it implements).

## Global Constraints

- One WP per branch: everything here lands on `cio-01-view-builder`, merged `--no-ff` into `main` only after the full gate is green and `scripts/check_gate.py` has stamped `.gate-ok`.
- Determinism: no clocks, no locale, no `random`; same inputs ⇒ byte-identical JSON. All floats rounded with `round(float(x), 4)` at the payload boundary.
- No network in tests; HTTP tests use `pytest.mark.enable_socket` + FastAPI `TestClient` (in-process, sanctioned loopback — copy `tests/test_serve.py`'s pattern).
- Files in the pre-registration seal are NOT touched: `ah/play.py`, `ah/serve.py`, `ah/cioview.py` are all outside `hashed_files` (verified 2026-08-14).
- DN-8 conventions are law: percent as percentage points (26.1), `Ratio` as decimals (0.51), missing is `null` never 0, positive-magnitude flows, arrays in display order, classes grouped in goal order.
- `markets.conditions` is NEVER emitted (spec O-3). `worldStartIndex` is 0 until cio-04.
- ASCII only in any string that could reach a console; the payload itself is JSON (safe).
- Task 2 records extra state via pure reads only — quarterly numerics must be byte-identical before/after (existing `tests/test_play.py` golden assertions are the proof).

---

### Task 1: Branch and vendor the drop

**Files:**
- Create: `Instructions/DN-8-cio-dashboard-data-contract.md` (from the zip)
- Create: `docs/cio-dashboard/cioView.ts`, `docs/cio-dashboard/terrarium-cio-dashboard.jsx` (vendored for cio-02)

**Interfaces:**
- Consumes: `docs/CIO Dashboard.zip`
- Produces: the ratified contract document later tasks cite.

- [ ] **Step 1: Create the branch off main**

```bash
git switch main && git switch -c cio-01-view-builder
```

- [ ] **Step 2: Unpack the zip**

```powershell
Expand-Archive -Path "docs\CIO Dashboard.zip" -DestinationPath "docs\cio-dashboard" -Force
Move-Item "docs\cio-dashboard\DN-8-cio-dashboard-data-contract.md" "Instructions\DN-8-cio-dashboard-data-contract.md"
```

- [ ] **Step 3: Record the resolutions in DN-8**

Append to `Instructions/DN-8-cio-dashboard-data-contract.md` (before the Changelog section) a new section:

```markdown
## Resolutions — 2026-08-14 (owner decisions, spec §2)

Ratified against `docs/superpowers/specs/2026-08-14-cio-dashboard-design.md`.
The dashboard is the in-session play surface (the cockpit).

| Item | Resolution |
|---|---|
| ⚑ O-1 | **Option A**, built as its own WP (cio-04). Dashboard ships first with `worldStartIndex: 0` and nulled long columns (B behaviour as a transitional state). |
| ⚑ O-2 | `planesAvailable: ["reported","true"]`. Generic-portfolio tier; true plane labelled "engine true state". |
| ⛔ O-3 | **Observables only.** `markets.conditions` is never emitted to a player build. |
| ⚑ O-4 | Static class→tier mapping, footnoted. Behavioural re-tiering deferred. |
| ⚑ O-5 | Fixed goal taxonomy, shipped as a policy constant in `ah/cioview.py`. |
| ⚑ O-6 | `coverageDanger` stays unset until P-B is filled. |
| ⚑ O-7 | v1 series = `aggregate` + closed-end classes only. |
| ⚑ O-8 | Open-end/evergreen sleeves excluded from the private tab with a stated footnote. |
| ⚑ O-9 | Dissolves: reported-vs-true is the engine's `_reported_marks` output; the builder reports it, never picks a sign. |
| ⚑ O-10 | v1 uses `alertPolicy.watchFraction = 0.75`; engine-supplied `alert` deferred (additive upgrade). |
```

Also update the Status line at the top of DN-8 from "unratified" to:
`*Status: **ratified 2026-08-14** for the generic-portfolio tier — see Resolutions section. ⛔ O-3 resolved: conditions never ship.*`

- [ ] **Step 4: Commit**

```bash
git add Instructions/DN-8-cio-dashboard-data-contract.md docs/cio-dashboard/
git commit -m "docs(cio-01): vendor DN-8 + renderer drop; record the 2026-08-14 resolutions"
```

---

### Task 2: Per-asset and monthly state on the play book

**Files:**
- Modify: `src/ah/play.py` (`PlayQuarter`, `PlayResult`, `simulate_play`)
- Test: `tests/test_cioview.py` (new file — houses all cio-01 tests)

**Interfaces:**
- Consumes: existing `simulate_play(paths, decisions, *, use_reported, start_targets, ...) -> PlayResult`.
- Produces (later tasks rely on these exact names):
  - `PlayQuarter.liquid_values: dict[str, float]` — per liquid asset, quarter close (post-waterfall)
  - `PlayQuarter.private_true: dict[str, float]`, `PlayQuarter.private_reported: dict[str, float]` — per private asset NAV at close
  - `PlayQuarter.private_calls: dict[str, float]`, `PlayQuarter.private_distributions: dict[str, float]`, `PlayQuarter.private_unfunded: dict[str, float]`
  - `PlayQuarter.nav_true_months: tuple[float, ...]`, `PlayQuarter.nav_reported_months: tuple[float, ...]` — 3 monthly marks; index 2 equals the quarter-close NAV exactly
  - `PlayResult.opening: dict[str, Any]` — keys: `"nav_true"`, `"nav_reported"`, `"cash"`, `"liquid_values"` (dict), `"private_true"` (dict), `"private_reported"` (dict), `"private_unfunded"` (dict)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cioview.py`:

```python
"""cio-01: the CIO view builder and the play-state exposure it rides on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import PRIVATE_ASSETS, simulate_play

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


def test_per_asset_private_flows_sum_to_totals():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert abs(sum(q.private_calls.values()) - q.calls_paid) < 1e-9
        assert abs(sum(q.private_distributions.values()) - q.distributions_received) < 1e-9
        assert abs(sum(q.private_unfunded.values()) - q.unfunded_total) < 1e-9
        assert set(q.private_calls) == set(PRIVATE_ASSETS)


def test_per_asset_values_close_against_the_book():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        total = q.cash + sum(q.liquid_values.values()) + sum(q.private_true.values())
        assert abs(total - q.nav_true) < 1e-9
        total_rep = q.cash + sum(q.liquid_values.values()) + sum(q.private_reported.values())
        assert abs(total_rep - q.nav_reported) < 1e-9


def test_monthly_marks_close_on_the_quarter():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert len(q.nav_true_months) == 3
        assert len(q.nav_reported_months) == 3
        assert abs(q.nav_true_months[2] - q.nav_true) < 1e-9
        assert abs(q.nav_reported_months[2] - q.nav_reported) < 1e-9
        assert all(v > 0 for v in q.nav_true_months)


def test_opening_book_recorded():
    result = simulate_play(_paths(), None)
    op = result.opening
    total = op["cash"] + sum(op["liquid_values"].values()) + sum(op["private_true"].values())
    assert abs(total - op["nav_true"]) < 1e-9
    assert set(op["private_unfunded"]) == set(PRIVATE_ASSETS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cioview.py -v`
Expected: FAIL — `AttributeError` on the new fields.

- [ ] **Step 3: Implement in `src/ah/play.py`**

3a. Extend `PlayQuarter` (after `vintage_nav`, all defaulted so the frozen dataclass stays backward-constructible):

```python
    #: cio-01: per-asset state the CIO view renders. Pure reads of the same
    #: book — recording them must not change a single quarterly numeric.
    liquid_values: dict[str, float] = field(default_factory=dict)
    private_true: dict[str, float] = field(default_factory=dict)
    private_reported: dict[str, float] = field(default_factory=dict)
    private_calls: dict[str, float] = field(default_factory=dict)
    private_distributions: dict[str, float] = field(default_factory=dict)
    private_unfunded: dict[str, float] = field(default_factory=dict)
    #: Three monthly NAV marks for the quarter. Months 0 and 1 mark the
    #: opening sleeves to the tape's monthly returns with flows pending;
    #: month 2 IS the post-waterfall quarter close, exactly.
    nav_true_months: tuple[float, ...] = ()
    nav_reported_months: tuple[float, ...] = ()
```

3b. Extend `PlayResult` with the opening book (after `sale_log`):

```python
    opening: dict[str, Any] = field(default_factory=dict)
```

3c. In `simulate_play`, after `engine = PortfolioEngine(portfolio, policy)` record the opening book:

```python
    def _liquid_snapshot() -> dict[str, float]:
        return {a: float(portfolio.liquid[a].value) for a in liquid}

    def _private_snapshot(reported: bool) -> dict[str, float]:
        return {
            a: float(sum((c.nav_reported if reported else c.nav_true) for c in ladders[a]))
            for a in PRIVATE_ASSETS
        }

    def _unfunded_snapshot() -> dict[str, float]:
        return {a: float(sum(c.unfunded for c in ladders[a])) for a in PRIVATE_ASSETS}
```

(place these AFTER `ladders` is bound), then:

```python
    opening = {
        "nav_true": float(portfolio.nav_true()),
        "nav_reported": float(portfolio.nav_reported()),
        "cash": float(portfolio.cash),
        "liquid_values": _liquid_snapshot(),
        "private_true": _private_snapshot(False),
        "private_reported": _private_snapshot(True),
        "private_unfunded": _unfunded_snapshot(),
    }
```

3d. Inside the quarter loop: snapshot openings for the monthly marks. After the decision block and BEFORE `for asset in liquid: ... apply_return`:

```python
        liq_open = _liquid_snapshot()
        cash_open = float(portfolio.cash)
```

After the commitment block and BEFORE the cohort-step loop:

```python
        priv_true_open = _private_snapshot(False)
        priv_rep_open = _private_snapshot(True)
```

3e. Accumulate per-asset flows in the cohort loop. Replace the plain `calls += step.call` accumulation with per-asset dicts (keep the totals — they feed `run_quarter`):

```python
        calls_by: dict[str, float] = {a: 0.0 for a in PRIVATE_ASSETS}
        dists_by: dict[str, float] = {a: 0.0 for a in PRIVATE_ASSETS}
```

(declare just before the `for asset in PRIVATE_ASSETS:` cohort loop) and inside it, next to the existing accumulations:

```python
                calls_by[asset] += step.call
                dists_by[asset] += step.distribution_total
```

3f. Monthly marks, computed after `report = engine.run_quarter(...)` (pure reads of the tape + the snapshots; `m` marks use returns for months `3q .. 3q+m`):

```python
        def _mark(month_in_q: int, reported: bool) -> float:
            liq = sum(
                liq_open[a]
                * float(
                    np.prod(
                        1.0 + paths.returns[a][q * 3 : q * 3 + month_in_q + 1] / 100.0
                    )
                )
                for a in liquid
            )
            tape = paths.reported if reported else paths.returns
            opens = priv_rep_open if reported else priv_true_open
            priv = sum(
                opens[a]
                * float(np.prod(1.0 + tape[a][q * 3 : q * 3 + month_in_q + 1] / 100.0))
                for a in PRIVATE_ASSETS
            )
            return liq + priv + cash_open

        nav_true_months = (_mark(0, False), _mark(1, False), float(portfolio.nav_true()))
        nav_reported_months = (
            _mark(0, True),
            _mark(1, True),
            float(portfolio.nav_reported()),
        )
```

3g. Pass everything into the `PlayQuarter(...)` constructor call:

```python
                liquid_values=_liquid_snapshot(),
                private_true=_private_snapshot(False),
                private_reported=_private_snapshot(True),
                private_calls=calls_by,
                private_distributions=dists_by,
                private_unfunded=_unfunded_snapshot(),
                nav_true_months=nav_true_months,
                nav_reported_months=nav_reported_months,
```

3h. Add `opening=opening` to the `PlayResult(...)` constructor call.

- [ ] **Step 4: Run the new tests and the play suite**

Run: `uv run pytest tests/test_cioview.py tests/test_play.py tests/test_play_linkage.py tests/test_serve.py -v`
Expected: ALL PASS — the play goldens prove the quarterly numerics are unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/ah/play.py tests/test_cioview.py
git commit -m "feat(cio-01): expose per-asset and monthly book state on PlayQuarter (pure reads)"
```

---

### Task 3: `ah/cioview.py` — policy constants and the validator port

**Files:**
- Create: `src/ah/cioview.py`
- Test: `tests/test_cioview.py` (extend)

**Interfaces:**
- Produces (exact names later tasks use):
  - `PLANES: tuple[str, str] = ("reported", "true")`
  - `LINKAGE_VERSION = "public-0.1"`, `WATCH_FRACTION = 0.75`, `COVERAGE_ANCHOR = 0.5`
  - `GOALS`, `GOAL_OF`, `BAND_PCT`, `GOAL_TOLERANCE_PCT`, `TIER1_CLASSES`, `TIER2_CLASSES`
  - `validate_cio_view(view: dict) -> list[str]` — empty list means valid

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cioview.py`)

```python
from ah.cioview import validate_cio_view


def _minimal_view() -> dict[str, Any]:
    """Smallest payload that passes every check — the seed for defect tests."""
    return {
        "meta": {
            "runId": "r1", "seed": "42", "worldTitle": "t", "worldVersion": "toy-v0.6",
            "linkageVersion": "public-0.1", "decisionAlphaVersion": "port-v4-ladder",
            "asOfLabel": "Y1 Q1", "asOfMonth": 2, "plane": "reported",
            "planesAvailable": ["reported", "true"], "unitLabel": "$m",
            "unitSuffix": "m", "currency": "USD", "watermark": "w", "disclaimer": "d",
        },
        "plan": {
            "totalValue": 100.0, "growthPct": None, "netOfFlows": None,
            "windowLabel": "Since inception",
            "history": {"values": [100.0, 100.5, 100.0 + 1e-9], "worldStartIndex": 0},
        },
        "allocation": {
            "goals": [{"id": "growth", "label": "Growth", "tolerancePct": 5.0}],
            "classes": [{
                "id": "equity", "label": "Equity", "goalId": "growth",
                "targetPct": 100.0, "bandPct": 5.0, "currentPct": 100.0,
                "value": 100.0, "returns": [1.0],
            }],
            "alertPolicy": {"watchFraction": 0.75},
        },
        "performance": {
            "periods": ["1Q"], "annualisedFromIndex": 1,
            "total": [1.2], "benchmark": [1.1],
        },
        "liquidity": {
            "tiers": [{"id": "t1", "tier": 1, "label": "T1", "note": "", "value": 100.0}],
            "forecast12m": {
                "distributions": 2.0, "income": 0.0, "calls": 3.0,
                "payout": 1.0, "net": -2.0,
            },
        },
        "privateCashflows": {
            "histCount": 1,
            "classes": [{"id": "pe", "label": "PE"}],
            "series": {
                "aggregate": [_pq("Y1Q1", False)],
                "pe": [_pq("Y1Q1", False)],
            },
        },
    }


def _pq(label: str, forecast: bool) -> dict[str, Any]:
    return {
        "label": label, "forecast": forecast, "calls": 1.0, "distributions": 1.5,
        "net": 0.5, "navOpen": 30.0, "navClose": 30.5, "unfundedOpen": 15.0,
        "unfundedClose": 14.0, "callRateUnfunded": 0.0667, "callRateNav": 0.0333,
        "coverage": 0.459,
    }


def test_validator_passes_a_well_formed_view():
    assert validate_cio_view(_minimal_view()) == []


def test_validator_catches_unbalanced_weights():
    v = _minimal_view()
    v["allocation"]["classes"][0]["currentPct"] = 90.0
    assert any("currentPct sums" in e for e in validate_cio_view(v))


def test_validator_catches_forecast_flag_mismatch():
    v = _minimal_view()
    v["privateCashflows"]["series"]["pe"][0]["forecast"] = True
    assert any("forecast flag" in e for e in validate_cio_view(v))


def test_validator_catches_net_identity_break():
    v = _minimal_view()
    v["liquidity"]["forecast12m"]["net"] = 5.0
    assert any("components imply" in e for e in validate_cio_view(v))


def test_validator_catches_plane_not_available():
    v = _minimal_view()
    v["meta"]["plane"] = "true"
    v["meta"]["planesAvailable"] = ["reported"]
    assert any("planesAvailable" in e for e in validate_cio_view(v))
```

(Note `_pq` is used inside `_minimal_view` — define `_pq` above `_minimal_view` in the file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cioview.py -k validator -v`
Expected: FAIL with `ModuleNotFoundError: ah.cioview`.

- [ ] **Step 3: Create `src/ah/cioview.py`** with the constants and the validator (a faithful port of `validateCioView` in `docs/cio-dashboard/cioView.ts` — keep the message texts recognisably close):

```python
"""The CIO view builder (cio-01) — DN-8's engine side.

``build_cio_view`` is a pure function from replayed play state to the
``CioView`` payload the dashboard renders. The renderer computes nothing
(DN-8 section 1); everything on screen originates here, server-side, because
the server is the authority for value (DN-3 W5).

``validate_cio_view`` is the Python port of ``validateCioView`` from
``docs/cio-dashboard/cioView.ts`` and is the CI authority for the contract;
the TS validator runs dev-side only.
"""

from __future__ import annotations

from typing import Any

PLANES: tuple[str, str] = ("reported", "true")
LINKAGE_VERSION = "public-0.1"
WATCH_FRACTION = 0.75          # DN-8 section 3: amber inside the last quarter of the band
COVERAGE_ANCHOR = 0.5          # WP3.10 section 5 steady-state anchor
UNIT_LABEL, UNIT_SUFFIX, CURRENCY = "$m", "m", "USD"   # 1 point = $1m, declared
WATERMARK = "TERRARIUM - SIMULATED WORLD"
DISCLAIMER = (
    "Simulated world; generic parameters. Not investment advice and not "
    "representative of any institution's policy portfolio."
)
TRUE_PLANE_LABEL = "engine true state"   # O-2: never "true value"

#: O-5: the fixed goal taxonomy. Display order is the declaration order.
GOALS: tuple[tuple[str, str], ...] = (
    ("growth", "Growth"),
    ("real", "Real return"),
    ("income", "Income"),
    ("diversifier", "Diversifiers"),
)
GOAL_OF: dict[str, str] = {
    "equity": "growth", "pe": "growth",
    "commodities": "real", "reits": "real", "re": "real",
    "bonds": "income", "hy": "income", "pc": "income",
    "cash": "diversifier",
}
CLASS_LABEL: dict[str, str] = {
    "equity": "Public equity", "bonds": "Core bonds", "hy": "High yield",
    "commodities": "Commodities", "reits": "REITs", "pe": "Private equity",
    "pc": "Private credit", "re": "Real estate", "cash": "Cash",
}
#: Band half-widths in points, a declared display-policy input (O-5 kin).
BAND_PCT: dict[str, float] = {
    "equity": 5.0, "bonds": 3.0, "hy": 2.0, "commodities": 2.0, "reits": 2.0,
    "pe": 4.0, "pc": 2.0, "re": 2.0, "cash": 2.0,
}
GOAL_TOLERANCE_PCT = 5.0

#: O-4: static class->tier mapping, footnoted on the surface.
TIER1_CLASSES: tuple[str, ...] = ("cash", "bonds")
TIER2_CLASSES: tuple[str, ...] = ("equity", "hy", "commodities", "reits")
# everything in PRIVATE_ASSETS is the illiquid remainder (liquid: False)


def validate_cio_view(v: dict[str, Any]) -> list[str]:
    """Port of ``validateCioView`` — empty list means the payload is valid."""
    e: list[str] = []

    def near(a: float, b: float, tol: float = 0.1) -> bool:
        return abs(a - b) <= tol

    meta = v.get("meta") or {}
    if not meta.get("runId"):
        e.append("meta.runId is required")
    if not meta.get("linkageVersion"):
        e.append("meta.linkageVersion is required and is disclosed on screen")
    if meta.get("plane") not in (meta.get("planesAvailable") or []):
        e.append("meta.plane is not in meta.planesAvailable")

    alloc = v.get("allocation") or {}
    classes = alloc.get("classes") or []
    goals = alloc.get("goals") or []
    cur = sum(c.get("currentPct") or 0.0 for c in classes)
    tgt = sum(c["targetPct"] for c in classes)
    if not near(cur, 100.0):
        e.append(f"allocation.classes currentPct sums to {cur:.2f}, expected 100")
    if not near(tgt, 100.0):
        e.append(f"allocation.classes targetPct sums to {tgt:.2f}, expected 100")

    goal_ids = {g["id"] for g in goals}
    periods = (v.get("performance") or {}).get("periods") or []
    for c in classes:
        if c["goalId"] not in goal_ids:
            e.append(f"class {c['id']} references unknown goal {c['goalId']}")
        if c.get("returns") is not None and len(c["returns"]) != len(periods):
            e.append(f"class {c['id']} has {len(c['returns'])} returns, expected {len(periods)}")
        if c["bandPct"] < 0:
            e.append(f"class {c['id']} has a negative band")

    ap = alloc.get("alertPolicy")
    wf = ap.get("watchFraction") if ap else None
    if ap and wf is not None and not (0.0 < wf < 1.0):
        e.append(f"allocation.alertPolicy.watchFraction is {wf}, expected between 0 and 1 exclusive")
    if wf is None and not any(c.get("alert") for c in classes):
        e.append("no alertPolicy.watchFraction and no explicit class.alert - amber will never fire")
    explicit = sum(1 for c in classes if c.get("alert"))
    if 0 < explicit < len(classes):
        e.append(f"{explicit} of {len(classes)} classes carry an explicit alert - all or none")
    for g in goals:
        tol = g.get("tolerancePct")
        if tol is not None and tol <= 0:
            e.append(f"goal {g['id']} has a non-positive tolerancePct")
        if tol is None and not g.get("alert"):
            e.append(f"goal {g['id']} has neither tolerancePct nor alert - it will never flag")

    order = [next((i for i, g in enumerate(goals) if g["id"] == c["goalId"]), -1) for c in classes]
    if any(order[i] < order[i - 1] for i in range(1, len(order))):
        e.append("allocation.classes are not grouped in goal order")

    perf = v.get("performance") or {}
    if len(perf.get("total") or []) != len(periods):
        e.append("performance.total length != periods length")
    if perf.get("benchmark") is not None and len(perf["benchmark"]) != len(periods):
        e.append("performance.benchmark length != periods length")

    liq = v.get("liquidity") or {}
    plan_total = (v.get("plan") or {}).get("totalValue") or 0.0
    tier_sum = sum(t["value"] for t in liq.get("tiers") or [])
    if not near(tier_sum, plan_total, max(0.1, plan_total * 0.005)):
        e.append(f"liquidity tiers sum to {tier_sum:.1f}, plan total is {plan_total:.1f}")
    f = liq.get("forecast12m")
    if f:
        for k in ("distributions", "income", "calls", "payout"):
            if isinstance(f.get(k), (int, float)) and f[k] < 0:
                e.append(f"liquidity.forecast12m.{k} must be a positive magnitude")
        net = f["distributions"] + f["income"] - f["calls"] - f["payout"]
        if not near(net, f["net"], 1.0):
            e.append(f"liquidity.forecast12m.net is {f['net']}, components imply {net:.1f}")

    pcf = v.get("privateCashflows")
    if pcf:
        agg = (pcf.get("series") or {}).get("aggregate")
        if not agg:
            e.append("privateCashflows.series.aggregate is required")
        n = len(agg or [])
        if pcf["histCount"] > n:
            e.append("privateCashflows.histCount exceeds series length")
        for key, rows in (pcf.get("series") or {}).items():
            if len(rows) != n:
                e.append(f"private series {key} has length {len(rows)}, aggregate has {n}")
            for i, r in enumerate(rows):
                if r["calls"] < 0 or r["distributions"] < 0:
                    e.append(f"{key} {r['label']}: calls and distributions must be positive magnitudes")
                if not near(r["net"], r["distributions"] - r["calls"], 0.5):
                    e.append(f"{key} {r['label']}: net != distributions - calls")
                if agg and i < n and rows[i]["label"] != agg[i]["label"]:
                    e.append(f"{key} quarter {i} label does not match aggregate")
                if (i >= pcf["histCount"]) != r["forecast"]:
                    e.append(f"{key} {r['label']}: forecast flag disagrees with histCount")
        if agg:
            class_ids = [c["id"] for c in pcf.get("classes") or []]
            for i, r in enumerate(agg):
                s = sum(
                    (pcf["series"].get(cid) or [{}] * n)[i].get("calls", 0.0)
                    for cid in class_ids
                )
                if not near(s, r["calls"], max(0.5, r["calls"] * 0.001)):
                    e.append(f"aggregate calls at {r['label']} != sum of classes")

    h_len = len(((v.get("plan") or {}).get("history") or {}).get("values") or [])
    mk = v.get("markets") or {}
    for s in (mk.get("returns") or []) + (mk.get("conditions") or []):
        if len(s["path"]) != h_len:
            e.append(f"market series {s['id']} has {len(s['path'])} points, plan history has {h_len}")

    for where in ("total", "benchmark"):
        arr = perf.get(where)
        if arr:
            for i, x in enumerate(arr):
                if x == 0:
                    e.append(f"performance.{where}[{i}] is exactly 0 - confirm real zero vs unreached")

    return e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cioview.py -k validator -v`
Expected: PASS (all five).

- [ ] **Step 5: Commit**

```bash
git add src/ah/cioview.py tests/test_cioview.py
git commit -m "feat(cio-01): cioview policy constants + Python port of validateCioView"
```

---

### Task 4: The frozen tape and the builder core (meta, plan, allocation, performance)

**Files:**
- Modify: `src/ah/cioview.py`
- Test: `tests/test_cioview.py` (extend)

**Interfaces:**
- Consumes: Task 2's `PlayQuarter`/`PlayResult` fields; `ah.core.engine.EnginePaths` (fields: `months`, `seed`, `rate`, `spread`, `inflation`, `crisis`, `returns`, `reported`, `asset_order`); `ah.play.simulate_play`, `ah.play.PRIVATE_ASSETS`, `ah.play.START_TARGETS`, `ah.play.START_CASH`.
- Produces:
  - `_frozen_paths(paths: EnginePaths, hist_months: int, extra_quarters: int) -> EnginePaths`
  - `build_cio_view(paths, decisions, *, run_id, seed, world_title, world_version, alpha_version, start_targets, plane, revealed_months, forecast_quarters=4) -> dict[str, Any]` — the complete payload (liquidity/private/markets blocks filled by Task 5; this task returns them as `{}` placeholders is NOT allowed — Task 4 emits `meta`, `plan`, `allocation`, `performance` plus minimal passing `liquidity`/`privateCashflows` stubs built from the same state, and Task 5 replaces the stubs with the full blocks; the validator runs green after BOTH tasks).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cioview.py`)

```python
from ah.cioview import build_cio_view


def _view(plane: str = "reported", revealed: int = 60, fq: int = 4, preset: str = "stagflation"):
    return build_cio_view(
        _paths(preset), {},
        run_id="r-test", seed=42, world_title="Stagflation", world_version="toy-v0.6",
        alpha_version="port-v4-ladder", start_targets=None,
        plane=plane, revealed_months=revealed, forecast_quarters=fq,
    )


def test_view_validates_clean_on_both_planes():
    for plane in ("reported", "true"):
        assert validate_cio_view(_view(plane)) == []


def test_plan_history_is_monthly_and_truncated_at_the_pointer():
    v = _view(revealed=60)
    assert len(v["plan"]["history"]["values"]) == 60  # 20 closed quarters * 3
    assert v["plan"]["history"]["worldStartIndex"] == 0
    assert v["meta"]["asOfLabel"] == "Y5 Q4"


def test_planes_disagree_where_smoothing_bites():
    rep, tru = _view("reported"), _view("true")
    assert rep["plan"]["totalValue"] != tru["plan"]["totalValue"]
    # plane-invariant: the cash account has no planes (DN-8 section 4)
    rep_cash = next(t for t in rep["liquidity"]["tiers"] if "cash" in t["classIds"])
    tru_cash = next(t for t in tru["liquidity"]["tiers"] if "cash" in t["classIds"])
    assert rep_cash["value"] == tru_cash["value"]


def test_unreached_windows_are_null_not_zero():
    v = _view(revealed=15)  # 5 closed quarters: 3Y/5Y/10Y unreachable
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    for p in ("3Y", "5Y", "10Y"):
        assert v["performance"]["total"][idx[p]] is None
    for p in ("1Q", "1Y"):
        assert v["performance"]["total"][idx[p]] is not None


def test_benchmark_is_the_twin():
    v = _view()
    assert v["performance"]["benchmarkLabel"] == "Policy twin (hold course)"
    assert v["performance"]["benchmark"][0] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cioview.py -k "view or plan or planes or windows or benchmark" -v`
Expected: FAIL with `ImportError: cannot import name 'build_cio_view'`.

- [ ] **Step 3: Implement the frozen tape and the builder core** in `src/ah/cioview.py`.

Imports to add at the top:

```python
from collections.abc import Mapping
from dataclasses import replace

import numpy as np

from ah.core.engine import EnginePaths
from ah.play import PRIVATE_ASSETS, START_CASH, START_TARGETS, PlayResult, simulate_play
```

The frozen tape — revealed months verbatim, then flat months (0% returns on both tapes, rate/spread/inflation held at the last revealed value, crisis 0). Because drawdown depth is a running-peak function of the PAST, the historical quarters of the frozen run are identical to the live run, and the appended quarters are DN-8's mechanical roll-forward (pacing schedule continues, linkage held at current state):

```python
def _frozen_paths(paths: EnginePaths, hist_months: int, extra_quarters: int) -> EnginePaths:
    """The revealed tape verbatim plus flat forecast months."""
    n, extra = hist_months, extra_quarters * 3
    hold = lambda a: np.concatenate([a[:n], np.full(extra, float(a[n - 1]))])  # noqa: E731
    flat = lambda d: {k: np.concatenate([v[:n], np.zeros(extra)]) for k, v in d.items()}  # noqa: E731
    return replace(
        paths,
        months=n + extra,
        rate=hold(paths.rate),
        spread=hold(paths.spread),
        inflation=hold(paths.inflation),
        crisis=np.concatenate([paths.crisis[:n], np.zeros(extra)]),
        returns=flat(paths.returns),
        reported=flat(paths.reported),
    )
```

Period-return machinery over quarterly total returns (spending added back — the payout is the only external flow, so this is the time-weighted return of the plan):

```python
PERIODS = ("1Q", "YTD", "1Y", "3Y", "5Y", "10Y")
ANNUALISED_FROM = 3  # 3Y onward annualised
_WINDOW_QUARTERS = {"1Q": 1, "1Y": 4, "3Y": 12, "5Y": 20, "10Y": 40}


def _quarterly_returns(result: PlayResult, plane: str, n_quarters: int) -> list[float]:
    key = "nav_reported" if plane == "reported" else "nav_true"
    navs = [result.opening[key]] + [
        getattr(q, key) for q in result.quarters[:n_quarters]
    ]
    return [
        (navs[i + 1] + result.quarters[i].spending_paid) / navs[i] - 1.0
        for i in range(n_quarters)
    ]


def _window_return(q_rets: list[float], n: int, annualise: bool) -> float | None:
    if n > len(q_rets):
        return None
    growth = float(np.prod([1.0 + r for r in q_rets[-n:]]))
    if annualise:
        return round((growth ** (4.0 / n) - 1.0) * 100.0, 4)
    return round((growth - 1.0) * 100.0, 4)


def _period_row(q_rets: list[float], last_q: int) -> list[float | None]:
    out: list[float | None] = []
    for i, p in enumerate(PERIODS):
        n = (last_q % 4) + 1 if p == "YTD" else _WINDOW_QUARTERS[p]
        out.append(_window_return(q_rets, n, i >= ANNUALISED_FROM))
    return out
```

The builder core (`build_cio_view`). Skeleton — every helper it calls is defined in this task or Task 5:

```python
def build_cio_view(
    paths: EnginePaths,
    decisions: Mapping[int, Any],
    *,
    run_id: str,
    seed: int,
    world_title: str,
    world_version: str,
    alpha_version: str,
    start_targets: Mapping[str, float] | None,
    plane: str,
    revealed_months: int,
    forecast_quarters: int = 4,
) -> dict[str, Any]:
    if plane not in PLANES:
        raise ValueError(f"plane must be one of {PLANES}, got {plane!r}")
    n_q = revealed_months // 3
    if n_q < 1:
        raise ValueError("no closed quarter inside the revealed window")
    hist_months = n_q * 3
    frozen = _frozen_paths(paths, hist_months, forecast_quarters)
    active = simulate_play(frozen, dict(decisions), start_targets=start_targets)
    twin = simulate_play(frozen, None, start_targets=start_targets)
    targets = dict(start_targets) if start_targets is not None else dict(START_TARGETS)
    last = active.quarters[n_q - 1]
    q_rets = _quarterly_returns(active, plane, n_q)
    twin_rets = _quarterly_returns(twin, plane, n_q)

    nav_attr = "nav_reported_months" if plane == "reported" else "nav_true_months"
    history = [round(m, 4) for q in active.quarters[:n_q] for m in getattr(q, nav_attr)]
    total = last.nav_reported if plane == "reported" else last.nav_true
    opening_nav = active.opening["nav_reported" if plane == "reported" else "nav_true"]
    spend_total = sum(q.spending_paid for q in active.quarters[:n_q])

    view: dict[str, Any] = {
        "meta": {
            "runId": run_id,
            "seed": str(seed),
            "worldTitle": world_title,
            "worldVersion": world_version,
            "linkageVersion": LINKAGE_VERSION,
            "decisionAlphaVersion": alpha_version,
            "asOfLabel": f"Y{(n_q - 1) // 4 + 1} Q{(n_q - 1) % 4 + 1}",
            "asOfMonth": hist_months - 1,
            "plane": plane,
            "planesAvailable": list(PLANES),
            "unitLabel": UNIT_LABEL,
            "unitSuffix": UNIT_SUFFIX,
            "currency": CURRENCY,
            "watermark": WATERMARK,
            "disclaimer": DISCLAIMER,
        },
        "plan": {
            "totalValue": round(total, 4),
            "growthPct": round((total / opening_nav - 1.0) * 100.0, 4),
            "netOfFlows": round(total - opening_nav + spend_total, 4),
            "windowLabel": "Since inception",
            "history": {"values": history, "worldStartIndex": 0},
        },
        "allocation": _allocation(
            active,
            targets,
            plane,
            n_q,
            frozen.reported if plane == "reported" else frozen.returns,
        ),
        "performance": {
            "periods": list(PERIODS),
            "annualisedFromIndex": ANNUALISED_FROM,
            "total": _period_row(q_rets, n_q - 1),
            "benchmark": _period_row(twin_rets, n_q - 1),
            "benchmarkLabel": "Policy twin (hold course)",
            "footnote": "Payout added back; time-weighted. Twin holds the t0 plan.",
        },
        "liquidity": _liquidity(active, targets, plane, n_q, forecast_quarters),
        "privateCashflows": _private_cashflows(active, n_q, forecast_quarters, plane),
    }
    markets = _markets(paths, hist_months, plane)
    if markets is not None:
        view["markets"] = markets
    return view
```

The allocation block (classes grouped in `GOALS` order; per-class returns from the tape on the requested plane):

```python
def _allocation(
    active: PlayResult,
    targets: Mapping[str, float],
    plane: str,
    n_q: int,
    tape: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    last = active.quarters[n_q - 1]
    total = last.nav_reported if plane == "reported" else last.nav_true
    target_total = sum(targets.values()) + START_CASH
    private = last.private_reported if plane == "reported" else last.private_true

    def value_of(cid: str) -> float:
        if cid == "cash":
            return last.cash
        if cid in PRIVATE_ASSETS:
            return private[cid]
        return last.liquid_values[cid]

    ids = [*targets.keys(), "cash"]
    ordered = [cid for gid, _ in GOALS for cid in ids if GOAL_OF[cid] == gid]
    classes = []
    for cid in ordered:
        points = START_CASH if cid == "cash" else targets[cid]
        classes.append({
            "id": cid,
            "label": CLASS_LABEL[cid],
            "goalId": GOAL_OF[cid],
            "targetPct": round(points / target_total * 100.0, 4),
            "bandPct": BAND_PCT[cid],
            "currentPct": round(value_of(cid) / total * 100.0, 4),
            "value": round(value_of(cid), 4),
            "returns": _class_returns(tape, cid, n_q),
            **({"isPrivate": True} if cid in PRIVATE_ASSETS else {}),
        })
    goal_ids = {c["goalId"] for c in classes}
    return {
        "goals": [
            {"id": gid, "label": label, "tolerancePct": GOAL_TOLERANCE_PCT}
            for gid, label in GOALS
            if gid in goal_ids
        ],
        "classes": classes,
        "alertPolicy": {
            "watchFraction": WATCH_FRACTION,
            "label": "amber inside the last quarter of the band",
        },
    }


def _class_returns(
    tape: Mapping[str, np.ndarray], cid: str, n_q: int
) -> list[float | None]:
    """Per-class period returns from the sleeve tape (cash has none -> nulls)."""
    if cid not in tape:  # cash has no tape
        return [None] * len(PERIODS)
    monthly = tape[cid][: n_q * 3]
    q_rets = [
        float(np.prod(1.0 + monthly[i * 3 : i * 3 + 3] / 100.0)) - 1.0 for i in range(n_q)
    ]
    return _period_row(q_rets, n_q - 1)
```

For this task, implement `_liquidity`, `_private_cashflows`, and `_markets` as the REAL functions specified in Task 5 — Task 4 and Task 5 are split for review granularity, not for stubbing: if implementing strictly in order, write Task 5's three functions as part of making this task's `test_view_validates_clean_on_both_planes` pass, then Task 5's steps add their dedicated tests.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_cioview.py -v`
Expected: Task 4's five new tests PASS (requires Task 5's block functions — see note above; if deferring them, only `test_plan_history_is_monthly_and_truncated_at_the_pointer`, `test_unreached_windows_are_null_not_zero`, `test_benchmark_is_the_twin` can pass — run those and proceed to Task 5 before committing the full-validation test).

- [ ] **Step 5: Commit**

```bash
git add src/ah/cioview.py tests/test_cioview.py
git commit -m "feat(cio-01): frozen-tape roll-forward + builder core (meta/plan/allocation/performance)"
```

---

### Task 5: Liquidity, private cashflows and markets blocks

**Files:**
- Modify: `src/ah/cioview.py`
- Test: `tests/test_cioview.py` (extend)

**Interfaces:**
- Consumes: Task 4's `build_cio_view` internals; Task 2's per-asset fields.
- Produces: `_liquidity(active, targets, plane, n_q, forecast_quarters) -> dict`, `_private_cashflows(active, n_q, forecast_quarters, plane) -> dict`, `_markets(paths, hist_months, plane) -> dict | None`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cioview.py`)

```python
def test_forecast_rows_are_flagged_and_suppressable():
    v = _view(fq=4)
    pcf = v["privateCashflows"]
    n_hist = pcf["histCount"]
    for key, rows in pcf["series"].items():
        assert len(rows) == n_hist + 4
        assert all(r["forecast"] is (i >= n_hist) for i, r in enumerate(rows))
    v0 = _view(fq=0)
    assert all(
        not r["forecast"] for rows in v0["privateCashflows"]["series"].values() for r in rows
    )
    assert len(v0["privateCashflows"]["series"]["aggregate"]) == v0["privateCashflows"]["histCount"]


def test_aggregate_private_series_is_the_sum_of_classes():
    v = _view()
    pcf = v["privateCashflows"]
    ids = [c["id"] for c in pcf["classes"]]
    for i, agg in enumerate(pcf["series"]["aggregate"]):
        for field_name in ("calls", "distributions", "navClose", "unfundedClose"):
            s = sum(pcf["series"][cid][i][field_name] for cid in ids)
            assert abs(s - agg[field_name]) < 0.51, (i, field_name)


def test_forecast12m_net_identity_and_signs():
    v = _view()
    f = v["liquidity"]["forecast12m"]
    for k in ("distributions", "income", "calls", "payout"):
        assert f[k] >= 0.0
    assert abs(f["net"] - (f["distributions"] + f["income"] - f["calls"] - f["payout"])) < 1.0


def test_tiers_close_on_plan_total_and_privates_are_illiquid():
    v = _view()
    tiers = v["liquidity"]["tiers"]
    assert abs(sum(t["value"] for t in tiers) - v["plan"]["totalValue"]) < v["plan"]["totalValue"] * 0.005
    illiquid = [t for t in tiers if t.get("liquid") is False]
    assert illiquid and set(illiquid[0]["classIds"]) == set(PRIVATE_ASSETS)


def test_markets_has_no_conditions_and_paths_match_history():
    v = _view()
    assert "conditions" not in v.get("markets", {})
    h = len(v["plan"]["history"]["values"])
    for s in v["markets"]["returns"]:
        assert len(s["path"]) == h
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cioview.py -k "forecast or aggregate or tiers or conditions" -v`
Expected: FAIL (functions absent or stubbed).

- [ ] **Step 3: Implement the three blocks** in `src/ah/cioview.py`:

```python
def _liquidity(
    active: PlayResult,
    targets: Mapping[str, float],
    plane: str,
    n_q: int,
    forecast_quarters: int,
) -> dict[str, Any]:
    last = active.quarters[n_q - 1]
    total = last.nav_reported if plane == "reported" else last.nav_true
    private = last.private_reported if plane == "reported" else last.private_true
    liquid_ids = [a for a in targets if a not in PRIVATE_ASSETS]
    t1_ids = ["cash"] + [a for a in TIER1_CLASSES if a in liquid_ids]
    t2_ids = [a for a in TIER2_CLASSES if a in liquid_ids]
    t1 = last.cash + sum(last.liquid_values[a] for a in t1_ids if a != "cash")
    t2 = sum(last.liquid_values[a] for a in t2_ids)
    illiquid = sum(private.values())
    fwd = active.quarters[n_q : n_q + forecast_quarters]
    dist = sum(q.distributions_received for q in fwd)
    calls = sum(q.calls_paid for q in fwd)
    payout = sum(q.spending_paid for q in fwd)
    return {
        "tiers": [
            {"id": "t1", "tier": 1, "label": "Tier 1", "note": "cash + core bonds",
             "value": round(t1, 4), "classIds": t1_ids},
            {"id": "t2", "tier": 2, "label": "Tier 2", "note": "listed markets",
             "value": round(t2, 4), "classIds": t2_ids},
            {"id": "illiquid", "label": "Illiquid", "note": "closed-end private sleeves",
             "value": round(illiquid, 4), "liquid": False,
             "classIds": list(PRIVATE_ASSETS)},
        ],
        "forecast12m": {
            "distributions": round(dist, 4),
            "income": 0.0,
            "calls": round(calls, 4),
            "payout": round(payout, 4),
            "net": round(dist + 0.0 - calls - payout, 4),
        },
        "payoutLabel": "spending",
        "unfundedToNav": round(last.unfunded_total / total, 4) if total > 0 else None,
        "coverageAnchor": COVERAGE_ANCHOR,
        "tierFootnote": "Static class-to-tier mapping (DN-8 O-4); behavioural re-tiering deferred.",
        "flowFootnote": (
            "Roll-forward at the current market state; the model has no income "
            "line, so income is a true zero, not a gap."
        ),
    }


def _private_cashflows(
    active: PlayResult, n_q: int, forecast_quarters: int, plane: str
) -> dict[str, Any]:
    total_q = n_q + forecast_quarters
    nav_key = "private_reported" if plane == "reported" else "private_true"

    def row(asset_ids: list[str], i: int) -> dict[str, Any]:
        q = active.quarters[i]
        prev_nav = (
            {a: active.opening[nav_key][a] for a in asset_ids}
            if i == 0
            else {a: getattr(active.quarters[i - 1], nav_key)[a] for a in asset_ids}
        )
        prev_unf = (
            {a: active.opening["private_unfunded"][a] for a in asset_ids}
            if i == 0
            else {a: active.quarters[i - 1].private_unfunded[a] for a in asset_ids}
        )
        calls = sum(q.private_calls[a] for a in asset_ids)
        dists = sum(q.private_distributions[a] for a in asset_ids)
        nav_open, nav_close = sum(prev_nav.values()), sum(getattr(q, nav_key)[a] for a in asset_ids)
        unf_open, unf_close = sum(prev_unf.values()), sum(q.private_unfunded[a] for a in asset_ids)
        return {
            "label": f"Y{i // 4 + 1}Q{i % 4 + 1}",
            "forecast": i >= n_q,
            "calls": round(calls, 4),
            "distributions": round(dists, 4),
            "net": round(dists - calls, 4),
            "navOpen": round(nav_open, 4),
            "navClose": round(nav_close, 4),
            "unfundedOpen": round(unf_open, 4),
            "unfundedClose": round(unf_close, 4),
            "callRateUnfunded": round(calls / unf_open, 4) if unf_open > 0 else None,
            "callRateNav": round(calls / nav_open, 4) if nav_open > 0 else None,
            "coverage": round(unf_close / nav_close, 4) if nav_close > 0 else None,
        }

    series = {"aggregate": [row(list(PRIVATE_ASSETS), i) for i in range(total_q)]}
    for a in PRIVATE_ASSETS:
        series[a] = [row([a], i) for i in range(total_q)]
    return {
        "histCount": n_q,
        "classes": [{"id": a, "label": CLASS_LABEL[a]} for a in PRIVATE_ASSETS],
        "aggregateLabel": "All private sleeves",
        "series": series,
        "footnote": (
            "Closed-end cohorts only; the model holds no open-end or evergreen "
            "vehicles in this book (DN-8 O-8). Forecast rows are a mechanical "
            "roll-forward at the current market state, not a projection."
        ),
    }


_MARKET_COLOURS = {
    "equity": "#F0C46A", "bonds": "#6E9BD1", "hy": "#D9705A",
    "commodities": "#58B49E", "reits": "#A88BC4",
}


def _markets(paths: EnginePaths, hist_months: int, plane: str) -> dict[str, Any] | None:
    if hist_months < 2:
        return None
    liquid = [a for a in paths.asset_order if a not in PRIVATE_ASSETS]
    out: dict[str, Any] = {
        "tiles": [
            {"label": "Policy rate", "value": f"{float(paths.rate[hist_months - 1]):.2f}%"},
            {"label": "HY spread", "value": f"{float(paths.spread[hist_months - 1]):.0f}bps"},
            {"label": "Inflation", "value": f"{float(paths.inflation[hist_months - 1]):.1f}%"},
        ],
        "returns": [],
        "returnsFootnote": "Indexed to 100 at world start; revealed tape only.",
    }
    for i, a in enumerate(liquid):
        monthly = paths.returns[a][:hist_months]
        path = 100.0 * np.cumprod(1.0 + monthly / 100.0)
        out["returns"].append({
            "id": a, "label": CLASS_LABEL[a],
            "colour": _MARKET_COLOURS.get(a, "#8FA2BE"),
            "path": [round(float(x), 2) for x in path],
        })
    if hist_months >= 24:
        eq = paths.returns["equity"][:hist_months]
        corrs = []
        for a in liquid:
            if a == "equity":
                continue
            s = paths.returns[a][:hist_months]
            corrs.append({
                "id": a, "label": CLASS_LABEL[a],
                "current": round(float(np.corrcoef(eq[-12:], s[-12:])[0, 1]), 2),
                "baseline": round(float(np.corrcoef(eq, s)[0, 1]), 2),
            })
        out["correlations"] = corrs
        out["correlationNote"] = "current: trailing 12m; baseline: full revealed window"
    return out
```

Note: NO `conditions` key, ever (O-3). The `path` arrays deliberately use `paths.returns` (true tape) on both planes — public market prices are observable and have no reporting plane.

- [ ] **Step 4: Run the whole cioview test file**

Run: `uv run pytest tests/test_cioview.py -v`
Expected: ALL PASS, including `test_view_validates_clean_on_both_planes` from Task 4.

- [ ] **Step 5: Commit**

```bash
git add src/ah/cioview.py tests/test_cioview.py
git commit -m "feat(cio-01): liquidity, private-cashflow and markets blocks (observables only)"
```

---

### Task 6: Endpoint, parity, determinism, gate

**Files:**
- Modify: `src/ah/serve.py`
- Modify: `CHANGELOG.md`
- Test: `tests/test_serve.py` (extend), `tests/test_cioview.py` (extend)

**Interfaces:**
- Consumes: `build_cio_view` (Task 4/5), existing serve internals (`_resolve_engine`, `_get`, session store).
- Produces: `GET /sessions/{sid}/cio?plane=reported|true&forecast_quarters=0..8`.

- [ ] **Step 1: Write the failing endpoint tests** (append to `tests/test_serve.py`, reusing the module `service` fixture)

```python
def test_cio_view_endpoint(service):
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
    r = client.get(f"/sessions/{sid}/cio")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["meta"]["plane"] == "reported"
    assert v["meta"]["planesAvailable"] == ["reported", "true"]
    assert len(v["plan"]["history"]["values"]) == 12
    r_true = client.get(f"/sessions/{sid}/cio", params={"plane": "true"})
    assert r_true.status_code == 200
    assert r_true.json()["meta"]["plane"] == "true"
    assert r_true.json()["plan"]["totalValue"] != v["plan"]["totalValue"]


def test_cio_view_rejects_bad_params(service):
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 6}).status_code == 200
    assert client.get(f"/sessions/{sid}/cio", params={"plane": "both"}).status_code == 422
    assert client.get(f"/sessions/{sid}/cio", params={"forecast_quarters": 9}).status_code == 422
    assert client.get("/sessions/nope/cio").status_code == 404


def test_cio_view_needs_a_closed_quarter(service):
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.get(f"/sessions/{sid}/cio").status_code == 409


def test_cio_view_parity_with_mark_to_market(service):
    """The two payloads can never disagree on the book (spec section 5)."""
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 24}).status_code == 200
    doc = client.get(f"/sessions/{sid}").json()
    v = client.get(f"/sessions/{sid}/cio").json()
    assert abs(v["plan"]["totalValue"] - doc["value"]) < 1e-6
    cash_class = next(c for c in v["allocation"]["classes"] if c["id"] == "cash")
    assert abs(cash_class["value"] - doc["cash"]) < 1e-6
    priv = sum(
        c["value"] for c in v["allocation"]["classes"] if c.get("isPrivate")
    )
    assert abs(priv / v["plan"]["totalValue"] - doc["private_weight_reported"]) < 1e-6
```

And the determinism + golden-validation tests (append to `tests/test_cioview.py`):

```python
def test_view_is_byte_deterministic():
    a = json.dumps(_view(), sort_keys=True, separators=(",", ":"))
    b = json.dumps(_view(), sort_keys=True, separators=(",", ":"))
    assert a == b


def test_golden_views_validate_on_every_preset():
    for preset in ("stagflation", "goldilocks"):
        for plane in ("reported", "true"):
            for revealed in (12, 60, 120):
                errors = validate_cio_view(_view(plane, revealed, preset=preset))
                assert errors == [], (preset, plane, revealed, errors)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_serve.py -k cio tests/test_cioview.py -k "deterministic or golden" -v`
Expected: endpoint tests FAIL 404 (route absent); determinism tests PASS already (fine — they gate regressions).

- [ ] **Step 3: Add the endpoint** to `create_app` in `src/ah/serve.py` (after the `get_session` route). Import at the top: `from ah.cioview import PLANES, build_cio_view`.

```python
    @app.get("/sessions/{sid}/cio")
    def cio_view(
        sid: str,
        plane: str = "reported",
        forecast_quarters: int = 4,
        conn: sqlite3.Connection = Depends(db),
    ):
        """cio-01: the CIO dashboard's payload — DN-8's CioView, built
        server-side from the same truncated replay `_mark_to_market` uses.
        The renderer computes nothing; plane change is a refetch."""
        if plane not in PLANES:
            raise HTTPException(status_code=422, detail=f"plane must be one of {PLANES}")
        if not 0 <= forecast_quarters <= 8:
            raise HTTPException(status_code=422, detail="forecast_quarters must be 0..8")
        doc = _get(conn, sid)
        revealed = int(doc.get("revealed_months") or 0)
        if revealed < 3:
            raise HTTPException(status_code=409, detail="no closed quarter yet")
        rec = get_run_record(conn, doc["run_id"])
        assert rec is not None  # FK'd at creation
        world = get_world(conn, rec["world_id"])
        assert world is not None
        ws = WorldSpec.model_validate(world)
        nw = project_numeric(ws)
        paths, targets, alpha_version = _resolve_engine(ws, nw, rec["seed"])
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        resolved = rec.get("resolved_engine") or {}
        if isinstance(resolved, str):
            resolved = json.loads(resolved)
        return build_cio_view(
            paths,
            decisions,
            run_id=doc["run_id"],
            seed=rec["seed"],
            world_title=str((world.get("narrative") or {}).get("title") or doc["run_id"]),
            world_version=str(resolved.get("generator_version") or ""),
            alpha_version=alpha_version,
            start_targets=targets,
            plane=plane,
            revealed_months=revealed,
            forecast_quarters=forecast_quarters,
        )
```

(If `get_run_record` already returns `resolved_engine` as a dict, drop the `json.loads` branch — check `src/ah/store/runrecords.py` while implementing and keep whichever branch is real; leaving both is harmless.)

- [ ] **Step 4: Run the serve + cioview suites**

Run: `uv run pytest tests/test_serve.py tests/test_cioview.py -v`
Expected: ALL PASS.

- [ ] **Step 5: CHANGELOG**

Add under `## [Unreleased]` → `### Added` (create the subsection at the top if the current top subsection is `### Changed`):

```markdown
- **The CIO view builder (cio-01), 2026-08-14.** `ah/cioview.py` builds
  DN-8's `CioView` server-side — the pure-renderer contract's engine half —
  from the same truncated replay `_mark_to_market` uses, plus a frozen-tape
  roll-forward for the 12-month liquidity forecast and forecast quarters
  (pacing schedule held, linkage at the current market state, `forecast:
  true` on every forward row). New endpoint `GET /sessions/{sid}/cio`
  (plane is a refetch; `markets.conditions` never emitted per O-3).
  `PlayQuarter` gains per-asset and monthly book state as pure reads;
  quarterly numerics byte-identical. DN-8 vendored to `Instructions/` with
  the 2026-08-14 resolutions recorded.
```

- [ ] **Step 6: Lint, types, full gate**

```bash
uv run ruff check . --fix && uv run ruff format .
uv run pyright
```

Expected: clean. Then the gate, in the background, output to a file:

```bash
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90 > gate-cio-01.log 2>&1; echo "EXIT: $?" >> gate-cio-01.log
```

(run via `run_in_background`, ~26 min). Then READ the log — the `EXIT:` line and the pass count — never `tail`-chain:

```bash
uv run python scripts/check_gate.py gate-cio-01.log
```

Expected: `.gate-ok` stamped for the branch head. Also run the battery check the CI gate names: `uv run python -m ah.battery.report` (expected green).

- [ ] **Step 7: Commit, merge, push**

```bash
git add src/ah/serve.py tests/test_serve.py tests/test_cioview.py CHANGELOG.md
git commit -m "feat(cio-01): GET /sessions/{sid}/cio - the CioView endpoint

(a) Built: server-side build_cio_view over the truncated replay, frozen-tape
roll-forward for forecasts, Python validateCioView port as CI authority,
parity tests against _mark_to_market, DN-8 vendored + resolutions recorded.
(b) Deviations: [state any, with reasons — e.g. monthly marks are tape-marked
intra-quarter with exact quarter closes, recorded in the field docstring].
(c) For later WPs: cio-02 consumes this payload verbatim; forecast12m.income
is a true zero until an income line exists; worldStartIndex stays 0 until
cio-04."
git switch main && git merge --no-ff cio-01-view-builder
git push origin main
```

(Fill (b) honestly at merge time. Standing authorization covers the plain push after a green `--no-ff` merge.)

---

## Self-review notes (already applied)

- Spec §4 mapping table → Tasks 4–5; §5 endpoint → Task 6; §7 testing items 1–5 → Tasks 3–6 (item 6, the console walk, is a manual pre-merge step: run `uv run ah credibility --preset stagflation --out credibility.html` and eyeball the book panels against the CIO numbers for the same preset).
- Task 4/5 split is for review granularity; `test_view_validates_clean_on_both_planes` only passes once Task 5's blocks exist. The Task 4 commit may carry the three block functions if implemented together — note it in the commit body.
