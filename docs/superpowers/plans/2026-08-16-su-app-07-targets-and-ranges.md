# Policy Targets and Reporting Ranges (su-app-07) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate the institution's policy targets from its opening values, and report per-sleeve band breaches without changing a single number the engine produces.

**Architecture:** `OpeningBook` gains two optional fields (`targets`, `ranges`). When `targets` is present it becomes the `start_targets` the engine paces against, while opening values continue to come from the book — so the commitment programme follows the SAA rather than the drifted actual. Ranges are inert: breach status is computed in the read layer from data `PlayQuarter` already records, and populates the `AlertLevel` contract `cioView.ts` already defines.

**Tech Stack:** Python 3.12, pydantic v2, FastAPI, SQLite, pytest; React 18 + TypeScript + Vite + vitest.

**Spec:** `docs/superpowers/specs/2026-08-16-targets-and-ranges-design.md` — read it first; it records what was verified in the engine and why the scope stops where it does.

## Global Constraints

- **Deletability.** `targets=None` and `ranges=None` must reproduce su-app-06's behaviour bit-for-bit. Existing suites are the fence and must stay green unchanged.
- **Ranges are inert.** They must not reach `simulate_play`, `_build_portfolio`, or any engine path. If a range can change a number, the design has been broken.
- **The server is the authority for value and scoring** (DN-3 W5). Band *status* is computed server-side; the client renders it.
- **The cap basis must agree at all three enforcement points** — `serve.py`'s decision door, `validate_plan`, and `play.py:621`. su-app-06 proved that fixing one converts a 422 into a 500.
- Determinism: no RNG, no time-based defaults, no network in tests.
- `schemas/` is read-only vendored truth. `filterwarnings = ["error"]` — output pristine.
- Never weaken, skip or xfail a test. If a session document gains a key and a frozen key-set test breaks, extend the constant — do not loosen the `==`.

## Known traps in this repo — all of these cost a fix round last time

1. **`tests/test_serve*.py` needs `pytestmark = pytest.mark.enable_socket`** — TestClient needs a loopback socketpair on Windows and pytest-socket blocks it by default. Without it every test in the file fails at setup.
2. **Use the real fixtures.** `tests/test_sessions.py`: `stored_run -> (db, rid)`. `tests/test_serve.py`: `service -> (client, db, run_id)` and `gen_service -> (client, db, rid)` for a generated world. Import them (`from test_serve import service`), do not move them into `conftest.py` (its docstring forbids side-effectful fixtures) and do not invent new ones.
3. **The app has no `@testing-library/react` and no jest-dom.** Component tests hand-roll a render helper with `createRoot` + `act` and query the host element. See `app/src/RankedSetup.test.tsx`. Do not add a test library.
4. **The full suite takes ~25 min and the gate ~40.** The controller runs both. Implementers run focused tests only, in the FOREGROUND — never backgrounded, never behind a monitor. Four agent turns died that way.
5. **A fresh worktree lacks `data/` and `experiments/`** (both gitignored). Junction them or `tests/test_genconsole.py` fails with `FileNotFoundError`.
6. **Never commit the gate log** — `/gate*.log` is gitignored at root, and committing anything after a gate run moves HEAD and invalidates `.gate-ok` against the commit it certifies.
7. **Assert on the decade, not the pre-fill.** su-app-06 shipped a plan that was displayed and never applied; every test passed because they all asserted on what was shown.
8. **Every guard test needs a bite-proof** — break the thing, watch that test and only that test fail, revert, watch it pass, both outputs in the report. This caught three bad guards, and still missed one that tested an unreachable state, so also ask: *can a user actually be in the state this test asserts?*

---

### Task 1: The contract gains targets and ranges

**Files:** Modify `src/ah/port/book.py`; Test `tests/test_book.py`

**Produces:** `OpeningBook.targets: dict[str, float] | None`, `OpeningBook.ranges: dict[str, tuple[float, float]] | None`, `state_version` accepting `"opening-book-0.1"` and `"opening-book-0.2"`, `OpeningBook.effective_targets() -> dict[str, float]`, and extended `validate_book`.

- [ ] **Step 1: Write the failing tests** in `tests/test_book.py`, following the file's existing `_book()` / `_rung()` helpers:
  - a `0.1` document (no `targets`, no `ranges`) still validates — the deletability fence at the contract level;
  - `effective_targets()` returns the book's own weights when `targets is None`, and the entered targets when present;
  - targets that do not sum with cash to 100 are refused, naming the rule;
  - targets naming a sleeve outside the world's set are refused;
  - a range with `lo >= hi` is refused; a range on an unknown sleeve is refused;
  - a target outside its own range is **accepted** (the spec's deliberate choice), and `validate_book` surfaces it as a warning rather than raising.
- [ ] **Step 2: Run and confirm RED.** `uv run pytest tests/test_book.py -v`
- [ ] **Step 3: Implement.** Both fields optional and defaulted to `None`. `effective_targets()` is the single place that resolves "targets or the book's own weights" — every consumer calls it rather than re-deriving, so the fallback cannot drift. Keep semantic checks in `validate_book`, not in pydantic validators, for the same 422-readability reason as su-app-06.
- [ ] **Step 4: Confirm GREEN**, then `uv run ruff check . --fix && uv run ruff format . && uv run pyright`.
- [ ] **Step 5: Commit.**

---

### Task 2: Targets reach the engine; the cap follows them

**Files:** Modify `src/ah/play.py`, `src/ah/serve.py`; Test `tests/test_book_override.py`

**Consumes:** Task 1's `effective_targets()`.

The opening values keep coming from the book. What changes is the dict handed to `simulate_play` as `start_targets`, and the basis of the commitment cap.

- [ ] **Step 1: Write the failing tests.**
  - **The separation bites** *(the load-bearing test)*: a book whose `targets` differ from its values produces a **different decade** from one where they are equal. Assert on the full `PlayResult`, not on a pre-fill. It must fail if `effective_targets()` is ignored.
  - A book with `targets=None` produces a decade identical to su-app-06's.
  - The three enforcement points agree: a plan legal under the *target* passes the decision door, `validate_plan`, and `simulate_play`; one over it is refused at each with the rule named and never a 500.
- [ ] **Step 2: Run and confirm RED.**
- [ ] **Step 3: Implement.** In `serve.py`, resolve `start_targets` from the stored book's `effective_targets()`. Re-point the cap basis from `OpeningBook.target_nav()` to `effective_targets()` at all three sites. `_policy_private_weight` picks this up for free.
- [ ] **Step 4: Bite-proof.** Temporarily make `effective_targets()` return the book's values unconditionally; confirm the separation test fails and only it; revert; confirm green. Both outputs in the report.
- [ ] **Step 5: Confirm GREEN**, lint, types, commit.

---

### Task 3: Breach reporting — read layer only

**Files:** Modify `src/ah/serve.py` (and `src/ah/cioview.py` for the dashboard); Test `tests/test_serve_book.py`

**No engine file may change in this task.** If you find yourself editing `play.py`, stop and report — the design is that bands are inert.

Per-sleeve weights come from what `PlayQuarter` already records: `liquid_values`, `private_true`, `private_reported`, `nav_true`, `nav_reported`, `cash`.

- [ ] **Step 1: Write the failing tests** in `tests/test_serve_book.py` (it has the fixtures and the `enable_socket` marker):
  - a sleeve outside its band reports `breach`; within the alert threshold of an edge reports `watch`; comfortably inside reports `ok`;
  - a sleeve with no range never appears in the report at all;
  - **the inertness test**: the same session with and without `ranges` produces an identical decade and identical `/outcome`. This is what proves reporting cannot move a number.
  - both planes are reported (`true` and `reported`) — a private sleeve can breach on one and not the other, which is the interesting case.
- [ ] **Step 2: Run and confirm RED.**
- [ ] **Step 3: Implement.** Serve per sleeve: current weight, target, band, and `AlertLevel`, matching `app/src/lib/cioView.ts:30-37`'s existing definition exactly — populate that contract, do not invent a parallel one. Compute in one helper so `/sessions/{sid}` and `/cio` cannot disagree.
- [ ] **Step 4: Confirm GREEN**, lint, types, commit.

---

### Task 4: The entry screen takes targets and ranges

**Files:** Modify `app/src/BookEntry.tsx`, `app/src/lib/session.ts`, `app/src/styles.css`; Test `app/src/BookEntry.test.tsx`

- [ ] **Step 1: Write the failing tests**, in the project's hand-rolled idiom (trap 3):
  - target inputs render pre-filled equal to each sleeve's value, and range inputs render empty;
  - editing a target flips the ranked note to practice-only, exactly as editing a weight does — it is part of the book's digest;
  - `lo >= hi` disables Continue with the reason shown;
  - the row shows the implied weight beside the target so drift is visible;
  - **the sleeve set is still server-driven** — a generated-world fixture (four sleeves, no `reits`) renders four target rows, not five.
- [ ] **Step 2: Run and confirm RED.** `cd app && npm run test -- --run BookEntry`
- [ ] **Step 3: Implement.** Client validates shape only — totals, signs, `lo < hi`. Band *status* is never computed client-side; it is read from the server.
- [ ] **Step 4:** `npm run typecheck && npm run test -- --run && npm run build`, all foreground. Commit.

---

### Task 5: Documentation

**Files:** Modify `CHANGELOG.md`, `docs/current/README.md` if the register needs it

- [ ] **Step 1:** CHANGELOG entry naming the contract bump (`opening-book-0.2`), the separation, and — stated plainly — that **ranges report and do not rebalance**, so nobody later reads breach reporting as risk control.
- [ ] **Step 2:** Record the two things this WP deliberately did not do: rebalancing to target (a release event needing engine and alpha version bumps), and `DecisionWindow.tsx`'s incorrect claim that *hold* rebalances to target — true before this WP and still true after.
- [ ] **Step 3:** `uv run ruff check . --fix && uv run ruff format . && uv run pyright`. Commit. **Do not run the gate** — the controller does, on the final commit, and does not commit the log.

---

## Self-Review

**Spec coverage:** §3 contract → Task 1; §4 separation and cap basis → Task 2; §5 read-layer reporting → Task 3; §6 screen → Task 4; §7 out-of-scope recorded → Task 5; §8 tests 1–5 → Tasks 1–3.

**Deliberate omission:** the spec's warning for a target outside its own range is surfaced by `validate_book` but has no UI treatment in Task 4 beyond rendering the values. If the owner wants it visible on the screen, that is a small addition to Task 4, not a new task.

**Type consistency:** `effective_targets()` (Task 1) is the only resolver of the targets fallback and is called by Task 2 in both `serve.py` and the cap sites. `AlertLevel` (Task 3) is the existing TS union, not a new one. `targets`/`ranges` on the TS `Book` type (Task 4) mirror the Python `model_dump()` shape from Task 1.
