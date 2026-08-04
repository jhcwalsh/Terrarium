# Play Surface on the Step-3 Twin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the player's institution the real one — capital calls that must be funded, forced sales when they can't be — by wiring `serve.py`, `bundle.py` and `app/` onto `ah.play`, and deleting `ah/pacing.py`.

**Architecture:** `ah.play` (already merged) becomes the single product scoring path. Decision-*dependent* state (your ledger, your forced sales) is served per-session; decision-*independent* state (the hold-course twin's ledger) stays pre-authored in the bundle, which keeps browse mode and offline replay working. `ah.core.institution` and `ah.density` survive untouched for Step-5 research only.

**Tech Stack:** Python 3.12, FastAPI, pydantic, numpy, SQLite; React 18 + TypeScript + Vite, vitest, hand-rolled SVG.

**Spec:** `docs/superpowers/specs/2026-08-04-play-surface-on-the-twin-design.md`

## Global Constraints

- **Determinism.** All randomness flows from one integer seed via `numpy.random.Generator(PCG64(seed))`. No global RNG, no `random`, no time-based defaults.
- **The server is the authority for value and scoring** (DN-3 W5). The app may mirror target weights; it must never compute value or alpha client-side.
- **Leakage.** Every session field must be a function of *revealed months only*.
- **Do NOT touch** `ah/eval/decision_metrics.py` (`DECISION_ALPHA_VERSION`) — it is inside the G5 seal (`step5-evaluation-protocol.yaml`, `sealed: true`).
- **Do NOT edit** `schemas/` — read-only vendored truth.
- **Never weaken a test to make it pass.** If a test written to catch a defect fails because the defect is fixed, invert it and keep the history in the docstring.
- **CLI-echoed strings stay ASCII** (Windows console is cp1252). Markdown may use Unicode.
- **`src/ah/cli.py` must not use** `from __future__ import annotations` (Typer resolves hints at runtime).
- Gate before merge: `uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90` — run in background to a log, read the `EXIT:` line and pass count as data. ~25 minutes.
- Branch `wire-play-surface`, merge `--no-ff` into `main` only on a green gate, then plain push.

---

### Task 1: Port the chain-link decomposition to the twin

DN-5's decomposition currently runs on `simulate_institution`. Attribution computed on the toy would not sum to the alpha displayed beside it — a broken reckoning, not an approximate one.

**Files:**
- Modify: `src/ah/play.py` (append; add `PlayAttribution`, `window_contributions_play` to `__all__`)
- Test: `tests/test_play.py` (append a `TestAttribution` class)

**Interfaces:**
- Consumes: `simulate_play(paths, decisions, *, use_reported, policy) -> PlayResult`, `ah.core.institution.decision_months(months) -> list[int]`
- Produces: `PlayAttribution(months: tuple[int,...], actions: tuple[str,...], contributions: tuple[float,...], twin_final: float, final_value: float)` with property `total_alpha`; `window_contributions_play(paths, decisions, *, use_reported=True, policy=None) -> PlayAttribution`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_play.py`:

```python
class TestAttribution:
    def test_contributions_sum_to_the_alpha_shown(self, stagflation):
        """The property that made porting mandatory: what the reckoning
        attributes to each window must add up to the alpha beside it."""
        from ah.play import window_contributions_play

        windows = decision_months(stagflation.months)
        decisions = {windows[0]: "derisk", windows[3]: "secondary", windows[5]: "leanin"}
        attr = window_contributions_play(stagflation, decisions)
        assert sum(attr.contributions) == pytest.approx(attr.total_alpha, abs=1e-9)
        assert attr.total_alpha == pytest.approx(
            play_alpha(stagflation, decisions), abs=1e-9
        )

    def test_one_contribution_per_window_in_order(self, stagflation):
        from ah.play import window_contributions_play

        windows = decision_months(stagflation.months)
        attr = window_contributions_play(stagflation, {windows[0]: "derisk"})
        assert attr.months == tuple(windows)
        assert len(attr.contributions) == len(windows)
        assert attr.actions[0] == "derisk"
        assert all(a == "hold" for a in attr.actions[1:])

    def test_holding_throughout_attributes_nothing(self, stagflation):
        from ah.play import window_contributions_play

        attr = window_contributions_play(stagflation, {})
        assert attr.contributions == tuple(0.0 for _ in attr.months)
        assert attr.total_alpha == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_play.py::TestAttribution -q`
Expected: FAIL with `ImportError: cannot import name 'window_contributions_play'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/ah/play.py`, and add both names to `__all__`:

```python
@dataclass(frozen=True)
class PlayAttribution:
    """DN-5's chain-link decomposition, on the real twin.

    ``contributions[j]`` is the j-th window's marginal effect: the value of
    playing the decision prefix up to and including window j, minus the value
    of the prefix before it. The chain telescopes to the terminal difference,
    so the parts sum to the whole by construction rather than by luck.
    """

    months: tuple[int, ...]
    actions: tuple[str, ...]
    contributions: tuple[float, ...]
    twin_final: float
    final_value: float

    @property
    def total_alpha(self) -> float:
        return self.final_value - self.twin_final


def window_contributions_play(
    paths: EnginePaths,
    decisions: dict[int, str],
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
) -> PlayAttribution:
    """K+1 runs for K windows — exact, no sampling.

    Windows the participant left unmapped default to hold inside
    :func:`simulate_play` exactly as they did when the sequence was played, so
    a partial decision map still decomposes correctly.
    """
    months_list = decision_months(paths.months)
    twin = simulate_play(paths, None, use_reported=use_reported, policy=policy)
    prev_final = float(twin.final_value)

    contributions: list[float] = []
    actions: list[str] = []
    prefix: dict[int, str] = {}
    for month in months_list:
        action = decisions.get(month, "hold")
        prefix[month] = action
        run = simulate_play(paths, dict(prefix), use_reported=use_reported, policy=policy)
        final = float(run.final_value)
        contributions.append(final - prev_final)
        actions.append(action)
        prev_final = final

    return PlayAttribution(
        months=tuple(months_list),
        actions=tuple(actions),
        contributions=tuple(contributions),
        twin_final=float(twin.final_value),
        final_value=prev_final,
    )
```

Add the import at the top of `src/ah/play.py` (it does not yet import `decision_months`):

```python
from ah.core.institution import decision_months
```

> Note: `tests/test_play.py::TestScoringIdentity::test_play_does_not_import_the_toy_institution` asserts `ah.core.institution` is **not** imported. That test was written to stop the *simulator* being wrapped; importing the window calendar is a different thing. Widen the test rather than deleting it — see Step 4.

- [ ] **Step 4: Widen the import guard rather than deleting it**

Replace the body of `test_play_does_not_import_the_toy_institution` in `tests/test_play.py`:

```python
    def test_play_does_not_use_the_toy_simulator(self):
        """It replaces ah.core.institution for SCORING rather than wrapping it.

        The window calendar (`decision_months`) is shared on purpose — the
        windows are the same windows. What must not be imported is the toy
        simulator, because two value models in one scoring path is exactly the
        drift this guard exists to prevent.
        """
        import ast

        import ah.play as play_module

        tree = ast.parse(Path(play_module.__file__).read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
        assert "ah.core.institution.simulate_institution" not in names
        assert "ah.core.institution.hold_course_twin" not in names
        assert "ah.core.institution.decision_months" in names
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_play.py -q`
Expected: PASS, 18 tests

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff format src/ah/play.py tests/test_play.py
uv run ruff check src/ah/play.py tests/test_play.py
uv run pyright src/ah/play.py
git add src/ah/play.py tests/test_play.py
git commit -m "feat: port DN-5's chain-link decomposition onto the real twin"
```

---

### Task 2: Score sessions on the twin

**Files:**
- Modify: `src/ah/serve.py` — `_mark_to_market` (replace body), `outcome` (replace the simulate/attribute block), `_ALPHA_VERSION_FALLBACK` (delete)
- Test: `tests/test_serve.py`

**Interfaces:**
- Consumes: `simulate_play`, `play_alpha`, `window_contributions_play`, `PLAY_ALPHA_VERSION` from Task 1 and `ah.play`
- Produces: session JSON gains `cash`, `coverage_true`, `coverage_reported`, `private_weight_true`, `calls_paid`, `distributions_received`, `spending_paid`, `forced_sale_total`, `forced_sales` (list); outcome JSON's `decision_alpha_version` becomes `PLAY_ALPHA_VERSION`

- [ ] **Step 1: Write the failing test**

Replace `test_book_is_marked_to_market_at_the_pointer` in `tests/test_serve.py` and add:

```python
    def test_book_is_marked_to_market_on_the_real_twin(self, service):
        """The rail's headline number, now with a cash account behind it."""
        from ah.core.engine import run_path
        from ah.core.numericworld import project_numeric
        from ah.core.worldspec import WorldSpec
        from ah.play import simulate_play
        from ah.store.db import connect
        from ah.store.runrecords import get_run_record
        from ah.store.worlds import get_world

        client, db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.get(f"/sessions/{sid}").json()["value"] is None

        doc = client.post(f"/sessions/{sid}/advance", json={"to_month": 6}).json()
        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        world = get_world(conn, rec["world_id"])
        assert world is not None
        paths = run_path(project_numeric(WorldSpec.model_validate(world)), rec["seed"])
        twin = simulate_play(paths, None, use_reported=True)
        # month 6 revealed -> quarter index 1 closed (months 3,4,5)
        assert doc["value"] == pytest.approx(twin.quarters[1].nav_reported)
        assert doc["cash"] == pytest.approx(twin.quarters[1].cash)
        assert doc["calls_paid"] >= 0.0
        assert 0.0 <= doc["private_weight_true"] <= 1.0

    def test_session_carries_the_product_alpha_version(self, service):
        from ah.play import PLAY_ALPHA_VERSION

        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        for month in decision_months(120):
            client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1})
            client.post(f"/sessions/{sid}/decisions", json={"month": month, "action": "hold"})
        client.post(f"/sessions/{sid}/advance", json={"to_month": 120})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert out["decision_alpha_version"] == PLAY_ALPHA_VERSION
        assert out["alpha"] == pytest.approx(0.0, abs=1e-9)

    def test_attribution_sums_to_the_alpha_reported(self, service):
        """The reckoning must add up on the surface, not just in the library."""
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        windows = decision_months(120)
        for i, month in enumerate(windows):
            client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1})
            action = "derisk" if i == 0 else "hold"
            client.post(f"/sessions/{sid}/decisions", json={"month": month, "action": action})
        client.post(f"/sessions/{sid}/advance", json={"to_month": 120})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert sum(out["window_contributions"]) == pytest.approx(out["alpha"], abs=1e-9)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_serve.py -q -k "twin or alpha_version or attribution"`
Expected: FAIL — `KeyError: 'cash'` / assertion on `decision_alpha_version`

- [ ] **Step 3: Rewrite `_mark_to_market`**

In `src/ah/serve.py`, replace the whole `_mark_to_market` function body below its docstring with:

```python
        revealed = int(doc.get("revealed_months") or 0)
        for key in (
            "value", "twin_value", "cash", "coverage_true", "coverage_reported",
            "private_weight_true", "calls_paid", "distributions_received",
            "spending_paid", "forced_sale_total",
        ):
            doc[key] = None
        doc["forced_sales"] = []
        if revealed < 3:  # nothing closes before the first quarter ends
            return doc
        rec = get_run_record(conn, doc["run_id"])
        if rec is None:  # pragma: no cover - FK'd at creation
            return doc
        world = get_world(conn, rec["world_id"])
        if world is None:  # pragma: no cover - FK'd at creation
            return doc
        nw = project_numeric(WorldSpec.model_validate(world))
        paths = run_path(nw, rec["seed"])
        use_reported = doc["basis"] == "reported"
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        active = simulate_play(paths, decisions, use_reported=use_reported)
        twin = simulate_play(paths, None, use_reported=use_reported)
        # only quarters that have CLOSED inside the revealed window
        q = min(revealed // 3, len(active.quarters)) - 1
        here, twin_here = active.quarters[q], twin.quarters[q]
        doc["value"] = here.nav_reported if use_reported else here.nav_true
        doc["twin_value"] = twin_here.nav_reported if use_reported else twin_here.nav_true
        doc["cash"] = here.cash
        doc["coverage_true"] = here.unfunded_total / here.nav_true if here.nav_true > 0 else None
        doc["coverage_reported"] = (
            here.unfunded_total / here.nav_reported if here.nav_reported > 0 else None
        )
        doc["private_weight_true"] = here.private_weight_true
        doc["calls_paid"] = here.calls_paid
        doc["distributions_received"] = here.distributions_received
        doc["spending_paid"] = here.spending_paid
        doc["forced_sale_total"] = here.forced_sale_total
        doc["forced_sales"] = [e for e in active.sale_log if int(e["period"]) <= q + 1]
        return doc
```

- [ ] **Step 4: Rewrite the outcome block**

In `outcome`, replace the four lines computing `active`, `twin`, `attribution` and `alpha_version` with:

```python
        active = simulate_play(paths, decisions, use_reported=use_reported)
        twin = simulate_play(paths, None, use_reported=use_reported)
        attribution = window_contributions_play(paths, decisions, use_reported=use_reported)

        alpha = active.final_value - twin.final_value
        alpha_version = PLAY_ALPHA_VERSION
```

Add `"window_contributions": list(attribution.contributions)` and `"forced_secondaries": active.forced_secondaries` to the returned dict. Delete the `_ALPHA_VERSION_FALLBACK` constant and its comment. Update imports:

```python
from ah.play import (
    PLAY_ALPHA_VERSION,
    play_alpha,
    simulate_play,
    window_contributions_play,
)
```

Remove the now-unused `from ah.core.institution import decision_months, simulate_institution` — keep `decision_months`, drop `simulate_institution` — and remove `from ah.density import window_contributions`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_serve.py -q`
Expected: PASS

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff format src/ah/serve.py tests/test_serve.py
uv run ruff check src/ah/serve.py tests/test_serve.py
uv run pyright src/ah/serve.py
git add src/ah/serve.py tests/test_serve.py
git commit -m "feat: score sessions on the Step-3 twin, with attribution that sums"
```

---

### Task 3: Bundle 0.4 carries the twin's ledger; delete `ah/pacing.py`

**Files:**
- Modify: `src/ah/bundle.py:55` (`BUNDLE_VERSION`), the `"private"` block, imports
- Delete: `src/ah/pacing.py`, `tests/test_pacing.py`
- Modify: `tests/test_bundle.py` (version assertion + ledger test)

**Interfaces:**
- Consumes: `simulate_play` from `ah.play`
- Produces: bundle key `twin_ledger: {quarter_months: int[], calls: float[], distributions: float[], nav_true: float[], nav_reported: float[], cash: float[], unfunded: float[], private_weight_true: float[]}`

- [ ] **Step 1: Write the failing test**

In `tests/test_bundle.py`, change the version assertion to `"world-bundle-0.4"` and replace `test_private_ledger_rides_along` with:

```python
    def test_twin_ledger_rides_along(self, stored_run):
        """0.4 carries the HOLD-COURSE TWIN's cashflows, not the player's.

        The twin never acts, so its ledger is decision-independent and stays
        honestly pre-authorable (PD-4). The player's own ledger depends on what
        they did and comes from the session service instead.
        """
        db, rid = stored_run
        doc = build_bundle(connect(db), rid)
        assert "private" not in doc
        led = doc["twin_ledger"]
        n = len(led["quarter_months"])
        assert n == doc["meta"]["months"] // 3
        for key in (
            "calls", "distributions", "nav_true", "nav_reported",
            "cash", "unfunded", "private_weight_true",
        ):
            assert len(led[key]) == n, key
        assert led["quarter_months"] == [q * 3 + 2 for q in range(n)]
        assert all(c >= 0.0 for c in led["cash"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bundle.py -q`
Expected: FAIL on the version assertion

- [ ] **Step 3: Implement**

In `src/ah/bundle.py`: set `BUNDLE_VERSION = "world-bundle-0.4"  # 0.4: the twin's ledger replaces the pacing preview`. Replace `from ah.pacing import build_ledgers` with `from ah.play import simulate_play`. Replace the whole `"private": {...}` block with:

```python
        # The HOLD-COURSE TWIN's cashflows. Decision-independent by
        # construction — the twin never acts — so it stays pre-authorable at
        # build time (PD-4). The player's own ledger depends on their
        # decisions and is served per-session instead.
        "twin_ledger": _twin_ledger(revealed),
```

And add above `build_bundle`:

```python
def _twin_ledger(revealed: EnginePaths) -> dict[str, list[float] | list[int]]:
    """The hold-course institution's quarterly cashflows, for the bundle."""
    result = simulate_play(revealed, None)
    return {
        "quarter_months": [q.month for q in result.quarters],
        "calls": _round(np.array([q.calls_paid for q in result.quarters])),
        "distributions": _round(np.array([q.distributions_received for q in result.quarters])),
        "nav_true": _round(np.array([q.nav_true for q in result.quarters])),
        "nav_reported": _round(np.array([q.nav_reported for q in result.quarters])),
        "cash": _round(np.array([q.cash for q in result.quarters])),
        "unfunded": _round(np.array([q.unfunded_total for q in result.quarters])),
        "private_weight_true": _round(
            np.array([q.private_weight_true for q in result.quarters])
        ),
    }
```

Add `from ah.core.engine import EnginePaths` to the imports if not present.

- [ ] **Step 4: Delete the retired module**

```bash
git rm src/ah/pacing.py tests/test_pacing.py
```

- [ ] **Step 5: Add the deletion guard**

Append to `tests/test_bundle.py`:

```python
def test_nothing_imports_the_retired_pacing_shim():
    """ah.pacing was a display-only miniature of what ah.play now does
    properly. Two ledgers computed different ways is the drift this deletion
    exists to prevent."""
    import subprocess

    root = Path(__file__).resolve().parents[1]
    hits = subprocess.run(
        ["git", "grep", "-l", "ah.pacing", "--", "src", "tests", "app/src"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert hits.stdout.strip() == "", hits.stdout
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_bundle.py -q`
Expected: PASS

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff format src/ah/bundle.py tests/test_bundle.py
uv run ruff check src/ah/bundle.py tests/test_bundle.py
uv run pyright src/ah/bundle.py
git add -A src/ah tests
git commit -m "feat: bundle 0.4 carries the twin's ledger; retire ah/pacing.py"
```

---

### Task 4: App types and the book panel

**Files:**
- Modify: `app/src/lib/bundle.ts` (versions, types), `app/src/lib/session.ts` (Session fields)
- Create: `app/src/components/Book.tsx`, `app/src/components/Book.test.tsx`
- Delete: `app/src/components/Allocation.tsx`, `app/src/components/Allocation.test.ts`
- Modify: `app/src/Play.tsx` (swap the panel), `app/src/styles.css`

**Interfaces:**
- Consumes: session fields from Task 2, `twin_ledger` from Task 3
- Produces: `<Book session={session} />`

- [ ] **Step 1: Update the contract types**

In `app/src/lib/bundle.ts`: add `"world-bundle-0.4"` to `SUPPORTED_BUNDLE_VERSIONS`; replace `PrivateLedger` with:

```ts
/** The hold-course twin's quarterly cashflows, carried in the bundle.
 *  Decision-independent by construction, which is why it can be
 *  pre-authored; the player's own ledger comes from the session. */
export interface TwinLedger {
  quarter_months: number[];
  calls: number[];
  distributions: number[];
  nav_true: number[];
  nav_reported: number[];
  cash: number[];
  unfunded: number[];
  private_weight_true: number[];
}
```

and on `WorldBundle` replace `private?: ...` with `twin_ledger?: TwinLedger;`.

In `app/src/lib/session.ts`, extend `Session`:

```ts
  value?: number | null;
  twin_value?: number | null;
  cash?: number | null;
  coverage_true?: number | null;
  coverage_reported?: number | null;
  private_weight_true?: number | null;
  calls_paid?: number | null;
  distributions_received?: number | null;
  spending_paid?: number | null;
  forced_sale_total?: number | null;
  forced_sales?: { period: number; amount: number; cause: string; kind: string }[];
```

- [ ] **Step 2: Write the failing test**

Create `app/src/components/Book.test.tsx`:

```tsx
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { Book, PRIVATE_BAND } from "./Book";
import type { Session } from "../lib/session";

let root: Root | null = null;
let host: HTMLElement | null = null;

function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(ui));
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

const base: Session = {
  session_id: "s", run_id: "r", world_id: "w", months: 120, revealed_months: 24,
  basis: "reported", ranked: false, participant: null, decisions: {},
  window_log: [], status: "active",
  value: 96.2, twin_value: 95.1, cash: 2.4, coverage_true: 0.31,
  coverage_reported: 0.29, private_weight_true: 0.36,
};

describe("Book", () => {
  it("shows cash and the book's value", () => {
    render(<Book session={base} />);
    expect(host!.textContent).toContain("2.4");
    expect(host!.textContent).toContain("96.2");
  });

  it("flags a private-weight breach, and does not cry wolf inside the band", () => {
    render(<Book session={base} />);
    expect(host!.querySelector(".band-breach")).toBeNull();

    act(() => root!.render(<Book session={{ ...base, private_weight_true: 0.44 }} />));
    expect(host!.querySelector(".band-breach")).not.toBeNull();
    expect(PRIVATE_BAND).toEqual([0.15, 0.4]);
  });

  it("states the reported-vs-true gap rather than hiding it", () => {
    render(<Book session={{ ...base, coverage_true: 0.31, coverage_reported: 0.29 }} />);
    expect(host!.textContent).toMatch(/reported/i);
    expect(host!.textContent).toMatch(/true/i);
  });

  it("renders before the first quarter closes without throwing", () => {
    render(<Book session={{ ...base, revealed_months: 1, value: null, cash: null }} />);
    expect(host!.textContent).toBeTruthy();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd app && npx vitest run src/components/Book.test.tsx`
Expected: FAIL — cannot resolve `./Book`

- [ ] **Step 4: Implement `Book.tsx`**

Create `app/src/components/Book.tsx`:

```tsx
/**
 * The book — what the institution actually holds, on the real twin.
 *
 * Replaces the target-mix table. Under ah.play, targets are not the mechanic:
 * private cohorts are not dials, so a mirror of "targets" would describe a
 * machine that no longer exists. What matters now is the book itself — cash,
 * coverage, and whether the private weight is inside the policy band.
 *
 * Every number here is computed SERVER-SIDE (DN-3 W5). This renders; it does
 * not calculate.
 */

import type { Session } from "../lib/session";

/** ah.port.engine.Policy.private_weight_range, mirrored for display only. */
export const PRIVATE_BAND: [number, number] = [0.15, 0.4];

const pct = (v: number | null | undefined, dp = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(dp)}%`;
const num = (v: number | null | undefined, dp = 1) =>
  v == null ? "—" : v.toFixed(dp);

export function Book({ session }: { session: Session }) {
  const pw = session.private_weight_true;
  const [lo, hi] = PRIVATE_BAND;
  const breached = pw != null && (pw < lo || pw > hi);

  return (
    <div className="book" aria-label="the book">
      <div className="book-rail">
        <div>
          <span className="k">Value</span>
          <span className="v">{num(session.value)}</span>
        </div>
        <div>
          <span className="k">Cash</span>
          <span className={`v${session.cash != null && session.cash <= 0.01 ? " tight" : ""}`}>
            {num(session.cash, 2)}
          </span>
        </div>
        <div>
          <span className="k">Coverage</span>
          <span className="v">{pct(session.coverage_true)}</span>
        </div>
      </div>

      <table>
        <tbody>
          <tr>
            <td>Private weight</td>
            <td>{pct(pw)}</td>
            <td className={breached ? "band-breach" : "band-ok"}>
              {breached ? "outside" : "inside"} {pct(lo, 0)}–{pct(hi, 0)}
            </td>
          </tr>
          <tr>
            <td>Called this quarter</td>
            <td>{num(session.calls_paid, 2)}</td>
            <td />
          </tr>
          <tr>
            <td>Distributions</td>
            <td>{num(session.distributions_received, 2)}</td>
            <td />
          </tr>
          <tr>
            <td>Spending</td>
            <td>{num(session.spending_paid, 2)}</td>
            <td />
          </tr>
        </tbody>
      </table>

      <p className="book-note">
        Coverage is unfunded commitments over assets. On reported marks it reads{" "}
        {pct(session.coverage_reported)} against {pct(session.coverage_true)} true —
        the denominator gap that makes a book look healthiest exactly when it is
        not.
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Swap the panel in and delete the mirror**

In `app/src/Play.tsx`: replace `import { Allocation } from "./components/Allocation";` with `import { Book } from "./components/Book";`, and replace `<Allocation decisions={session.decisions} />` with `<Book session={session} />`. Change the eyebrow text from `Allocation` / `targets, rebalanced at each window` to `The book` / `cash, coverage, policy band`.

```bash
git rm app/src/components/Allocation.tsx app/src/components/Allocation.test.ts
```

In `app/src/styles.css`, rename the `.allocation`-prefixed rules to `.book` equivalents and add:

```css
.book-rail { display: flex; gap: 18px; margin-bottom: 10px; }
.book-rail .k { display: block; font-size: 11px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--dim); }
.book-rail .v { font-family: "IBM Plex Mono", monospace; font-size: 20px; }
.book-rail .v.tight { color: var(--clay); }
.band-breach { color: var(--clay); }
.band-ok { color: var(--dim); }
.book-note { font-size: 11px; color: var(--dim); line-height: 1.45; margin: 8px 0 0; }
```

- [ ] **Step 6: Run tests and build**

Run: `cd app && npm run typecheck && npm run test && npm run build`
Expected: typecheck clean, all vitest pass, build clean

- [ ] **Step 7: Commit**

```bash
git add -A app/src
git commit -m "feat: the allocation panel becomes the book"
```

---

### Task 5: Session-fed ledger and forced sales on the wire

**Files:**
- Modify: `app/src/components/PrivateMarkets.tsx`, `app/src/components/PrivateMarkets.test.ts`
- Modify: `app/src/Play.tsx` (pass session; merge forced sales into the feed)
- Modify: `app/src/components/Feed.tsx` (render a `forced_sale` item)

**Interfaces:**
- Consumes: `session.forced_sales`, `bundle.twin_ledger`
- Produces: `<PrivateMarkets ledger={twinLedger} session={session} revealedMonths={n} />`

- [ ] **Step 1: Write the failing test**

Replace `app/src/components/PrivateMarkets.test.ts` contents with a test that the twin ledger is used as the fallback and the session's own numbers win:

```ts
import { describe, expect, it } from "vitest";
import { lastRevealedQuarter, pickLedgerRow } from "./PrivateMarkets";

const QUARTERS = [2, 5, 8, 11, 14, 17];

describe("lastRevealedQuarter", () => {
  it("shows nothing before the first quarter closes", () => {
    expect(lastRevealedQuarter(QUARTERS, 0)).toBe(-1);
    expect(lastRevealedQuarter(QUARTERS, 2)).toBe(-1);
  });

  it("reveals a quarter the moment its closing month is on the tape", () => {
    expect(lastRevealedQuarter(QUARTERS, 3)).toBe(0);
    expect(lastRevealedQuarter(QUARTERS, 12)).toBe(3);
  });

  it("never runs past the last quarter it has", () => {
    expect(lastRevealedQuarter(QUARTERS, 120)).toBe(QUARTERS.length - 1);
  });
});

describe("pickLedgerRow", () => {
  const twin = { calls: [1, 2, 3], distributions: [4, 5, 6] };

  it("prefers the session's own numbers", () => {
    const row = pickLedgerRow(twin, { calls_paid: 9, distributions_received: 8 }, 1);
    expect(row).toEqual({ calls: 9, distributions: 8, source: "yours" });
  });

  it("falls back to the twin when there is no session — browse and offline", () => {
    const row = pickLedgerRow(twin, null, 1);
    expect(row).toEqual({ calls: 2, distributions: 5, source: "twin" });
  });

  it("returns nothing when neither is available", () => {
    expect(pickLedgerRow(undefined, null, 1)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && npx vitest run src/components/PrivateMarkets.test.ts`
Expected: FAIL — `pickLedgerRow` is not exported

- [ ] **Step 3: Implement `pickLedgerRow` and rewire the component**

In `app/src/components/PrivateMarkets.tsx`, add:

```tsx
interface LedgerRow {
  calls: number;
  distributions: number;
  source: "yours" | "twin";
}

/** The player's own numbers when a session exists; the twin's otherwise.
 *  Browse mode and offline replay (W8) both land on the twin, which is the
 *  honest thing to show when nobody has made a decision yet. */
export function pickLedgerRow(
  twin: { calls: number[]; distributions: number[] } | undefined,
  session: { calls_paid?: number | null; distributions_received?: number | null } | null,
  quarter: number,
): LedgerRow | null {
  if (session && session.calls_paid != null && session.distributions_received != null) {
    return {
      calls: session.calls_paid,
      distributions: session.distributions_received,
      source: "yours",
    };
  }
  if (twin && quarter >= 0 && quarter < twin.calls.length) {
    return {
      calls: twin.calls[quarter],
      distributions: twin.distributions[quarter],
      source: "twin",
    };
  }
  return null;
}
```

Change the component signature to `({ ledger, session, revealedMonths }: { ledger?: TwinLedger; session: Session | null; revealedMonths: number })`, drive the table off `pickLedgerRow`, and label the source (`your book` / `hold-course twin`) so the player is never shown the twin's numbers as their own.

- [ ] **Step 4: Render forced sales on the wire**

In `app/src/components/Feed.tsx`, add to `TYPE_LABEL`:

```ts
  forced_sale: "FORCED SALE",
```

and in `app/src/Play.tsx`, merge the session's forced sales into the feed before rendering:

```tsx
  const forcedItems = (session.forced_sales ?? []).map((e) => ({
    month: e.period * 3 - 1,
    type: "forced_sale",
    payload: {
      dateline: `Y${Math.floor((e.period * 3 - 1) / 12) + 1}M${(((e.period * 3 - 1) % 12) + 1)}`,
      headline:
        e.kind === "forced_secondary"
          ? `FORCED SALE: ${e.amount.toFixed(1)} raised at a discount — ${e.cause}`
          : `Holdings sold to cover the shortfall: ${e.amount.toFixed(1)}`,
    },
  }));
  const wire = [...(bundle.feed.artifacts ?? []), ...forcedItems];
```

Pass `wire` to `<Feed artifacts={wire} …>` and `<Ticker artifacts={wire} …>`.

In `app/src/styles.css`, add `.feed-forced_sale .feed-body strong { color: var(--clay); }`.

- [ ] **Step 5: Run tests and build**

Run: `cd app && npm run typecheck && npm run test && npm run build`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add -A app/src
git commit -m "feat: session-fed ledger with a twin fallback; forced sales on the wire"
```

---

### Task 6: Rebuild fixtures, gate, merge

**Files:**
- Modify: `app/fixtures/toy.bundle.gz`, `CHANGELOG.md`, `docs/engine-realism-register.md` (close ER-3)

- [ ] **Step 1: Rebuild the cross-language fixture**

```bash
SCR="C:/Users/james/AppData/Local/Temp/claude/C--Users-james-PycharmProjects-Terrarium/d5645701-42a6-46c5-926a-5a164d1f95ce/scratchpad"
uv run ah --db "$SCR/fixture2.db" bundle --out app/fixtures/toy.bundle.gz
cd app && npm run test
```

Expected: the fixture's `bundle_version` assertion passes at `0.4`; all vitest pass.

- [ ] **Step 2: Update the fixture's version assertion**

In `app/src/lib/bundle.test.ts`, change `"world-bundle-0.3"` to `"world-bundle-0.4"` and replace the `v0.3 carries the private-markets ledger` test with one asserting `twin_ledger` shape (arrays equal length, `quarter_months[i] === i * 3 + 2`).

- [ ] **Step 3: Close ER-3 in the register**

In `docs/engine-realism-register.md`, change ER-3's status to `CLOSED in the play surface (wire-play-surface branch)` and add a "What shipped" paragraph: the play surface now scores on `ah.port` through `ah.play`; calls must be funded; forced sales are logged events on the wire; `ah/pacing.py` is deleted. Note what remains open — the toy engine still has no cashflow of its own; this is the *institution* consuming it.

- [ ] **Step 4: Update `CHANGELOG.md`**

Add a "Changed" entry covering: the clean cutover, bundle `0.4`'s `twin_ledger`, the book panel, forced sales on the wire, the retired shim, and the two consequences — pre-cutover sessions re-score under the twin, completed ranked rows are immutable under their old version string.

- [ ] **Step 5: Lint, typecheck, full gate**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90 > gate-wire.log 2>&1; echo "EXIT:$?" >> gate-wire.log
```

Read `gate-wire.log`: confirm the `EXIT:0` line and the pass count **before** claiming anything.

- [ ] **Step 6: Merge and push**

```bash
git add -A && git commit -m "feat: wire the play surface onto the twin (ER-3 closed)"
git checkout main
git merge --no-ff wire-play-surface -m "Merge wire-play-surface: the player's institution is the real one"
git push origin main
```

- [ ] **Step 7: Verify live**

Restart the session service on **8787** (`Get-NetTCPConnection -LocalPort 8787` → `Stop-Process`, then `uv run uvicorn ah.serve:app --port 8787`), rebuild the play bundle, and confirm in the browser: the book shows cash and coverage, a `deflation_bust` world produces a forced sale on the wire, and the page still does not scroll.

---

## Self-Review

**Spec coverage.** `window_contributions_play` → Task 1. serve scoring + fields → Task 2. Bundle 0.4 + `pacing.py` deletion → Task 3. Book panel + type changes → Task 4. Session-fed ledger, twin fallback, forced sales on the wire → Task 5. Fixture, register, changelog, gate → Task 6. Error handling: the 500-not-fallback rule is inherent — Task 2 leaves no toy path to fall back to. Leakage: Task 2 slices at `revealed // 3`. Every spec section maps to a task.

**Placeholder scan.** No TBD/TODO. Every code step carries real code. Task 6 Step 3 and Step 4 describe prose content rather than showing it, which is correct for a changelog and register entry — the *content* is specified (what must be said), not deferred.

**Type consistency.** `PlayAttribution.contributions` (Task 1) → `out["window_contributions"]` (Task 2) → summed in the serve test. `TwinLedger` (Task 4) matches `_twin_ledger`'s keys (Task 3) exactly: `quarter_months, calls, distributions, nav_true, nav_reported, cash, unfunded, private_weight_true`. `pickLedgerRow` (Task 5) consumes `{calls, distributions}` — a structural subset of `TwinLedger`, which type-checks.

**One risk called out.** Task 1 introduces an import of `ah.core.institution.decision_months` into `ah/play.py`, which an existing test forbids. Step 4 widens that guard deliberately rather than deleting it, and says why in the docstring — the window calendar is shared on purpose; the *simulator* is what must not be.
