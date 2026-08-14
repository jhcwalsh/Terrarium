# ER-10: Reported Marks Catch Up To Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `_reported_marks` so appraisal smoothing delays returns instead
of destroying them (the old code filtered only the quarter-end month's return,
discarding 2 of 3 months — reported PM cumulated ~1/3 of truth), with the
engine-version bump, world fences, fixture regeneration, a permanent
catch-up invariant test, and reported-plane checks in the credibility console.

**Architecture:** One engine change in `ah/core/engine.py::_reported_marks`
(quarter-end mark = `w × (quarter's compounded true return) + (1−w) × prev`).
Reported marks sit inside every run digest, so `TOY_ENGINE_VERSION` bumps to
`toy-v0.6`, all five presets move to fresh world_id blocks (toy 501–504 →
511–514; gen 602 → 603), both committed bundles regenerate, and every golden
that encodes the old numbers re-pins. Two permanent guards land with the fix:
a catch-up invariant test (the test the bug proved was missing) and a
reported-vs-true catch-up check in the credibility console.

**Tech Stack:** Python 3.12 / numpy; React app fixtures via
`scripts/gen_bundle_fixtures.py`; no new dependencies.

## Global Constraints

- **Sealed files are read-only.** `ah/core/engine.py` is NOT in any lock
  (verified: main lock covers battery/derive/splice/eval/factors/splits/
  strategies; G3/G5 add mappings + estimators). `ah/credibility.py`,
  `ah/play.py` display surfaces are unsealed. If any pre-registration lock
  digest moves during this WP, STOP — something sealed was touched.
- **`decision_alpha_version` / `GEN_PLAY_ALPHA_VERSION` do NOT bump** — the
  alpha *definition* is unchanged; engine-number changes are fenced by
  world_id moves (CLAUDE.md rule).
- **Never weaken a test.** Existing reported-marks tests (zero off
  quarter-ends; present at quarter-ends) must still pass unchanged. Every
  re-pinned golden's docstring gains: "re-pinned under toy-v0.6 (ER-10)".
- Re-pin sweep is derived MECHANICALLY (memory `artifact-repoint-consumer-sweep`):
  run the full suite, attribute every failure to the number change or STOP.
- Determinism; no network in tests; ASCII in CLI-echoed strings.
- Branch `er10-01-reported-marks`; gate log read as its own step;
  `scripts/check_gate.py` stamps `.gate-ok`; merge `--no-ff`; plain push.
- Commits end with the standard trailers (Co-Authored-By + Claude-Session).

## File map

- Modify: `src/ah/core/engine.py` (`_reported_marks`, `TOY_ENGINE_VERSION`)
- Modify: `tests/test_engine.py` (add catch-up invariant; re-pin hash goldens)
- Modify: `src/ah/presets/{stagflation,goldilocks,deflation_bust,reflation_boom}.json`
  (world_id 501/502/503/504 → 511/512/513/514) and
  `src/ah/presets/stagflation_1974.json` (602 → 603)
- Modify: `tests/test_gen_adapter.py` (gen catch-up test + 603 re-pin)
- Modify: `src/ah/credibility.py` + `tests/test_credibility.py` (catch-up check)
- Regenerate: `app/fixtures/toy.bundle.gz`, `app/fixtures/gen.bundle.gz`
- Re-pin: every suite the full run flags (expected: test_engine, test_digest,
  test_cli, test_bundle, test_play, test_play_linkage, test_serve,
  test_programme, test_institution-adjacent, test_credibility)
- Modify: `docs/engine-realism-register.md` (ER-10 entry), `CLAUDE.md`
  (register list line), `CHANGELOG.md`

---

### Task 1: The engine fix + the catch-up invariant, test-first

**Files:**
- Modify: `tests/test_engine.py` (new test), `tests/test_gen_adapter.py` (new test)
- Modify: `src/ah/core/engine.py:446-466` (`_reported_marks`), `:51` (version)

**Interfaces:**
- Produces: `_reported_marks` unchanged in signature; `TOY_ENGINE_VERSION = "toy-v0.6"`.
  Reported quarter-end values now carry FULL-quarter magnitudes (a quarterly
  return, not a monthly one) — downstream consumers already treat the series
  as "sum of the quarter's nonzero entries", so no consumer-side change.

- [ ] **Step 1: Write the failing catch-up tests.** In `tests/test_engine.py`:

```python
def test_reported_marks_catch_up_to_truth_er10() -> None:
    """ER-10 (found 2026-08-12): the old _reported_marks filtered only the
    quarter-end MONTH's return, silently discarding the other two months —
    reported PM cumulated ~1/3 of truth (stagflation pc: 23% reported vs
    77% true over the decade). Appraisal smoothing must DELAY returns, not
    destroy them: over a long horizon, cumulative reported must land near
    cumulative true. The old code fails this at ratio ~0.30."""
    for preset in ("stagflation", "goldilocks"):
        ws = load_worldspec(_PRESET_DIR / f"{preset}.json")
        p = run_path(project_numeric(ws), ws.engine_defaults.base_seed or 0)
        for sleeve in REPORTED_SLEEVES:
            true_sum = float(p.returns[sleeve].sum())
            rep_sum = float(p.reported[sleeve].sum())
            assert true_sum > 20.0, f"{preset}/{sleeve}: fixture drifted"
            ratio = rep_sum / true_sum
            assert 0.80 < ratio < 1.20, (
                f"{preset}/{sleeve}: cumulative reported/true = {ratio:.2f} "
                "- smoothing is destroying or inventing return (ER-10)"
            )
```

(Reuse the file's existing imports/helpers for preset loading — mirror how
its other preset-driven tests locate `src/ah/presets`; add only what is
missing.) In `tests/test_gen_adapter.py`, the same invariant through the
adapter (reuse its existing 1974-preset harness/fixtures):

```python
def test_gen_reported_marks_catch_up_to_truth_er10() -> None:
    """ER-10 on the generated path: the adapter shares _reported_marks, so
    the 1974 world inherited the same 1/3-of-truth defect (pe: 27% reported
    vs 125% true)."""
    ws = load_worldspec(PRESET_1974)
    p = run_gen_path(project_numeric(ws), ws.engine_defaults.base_seed)
    for sleeve in ("pe", "pc", "re"):
        ratio = float(p.reported[sleeve].sum()) / float(p.returns[sleeve].sum())
        assert 0.80 < ratio < 1.20, f"{sleeve}: reported/true {ratio:.2f}"
```

- [ ] **Step 2: Run both; verify they FAIL with ratios ~0.25-0.40**

Run: `uv run pytest tests/test_engine.py -k catch_up -q; uv run pytest tests/test_gen_adapter.py -k catch_up -q`
Expected: FAIL, assertion message showing ratio ≈ 0.3.

- [ ] **Step 3: Fix `_reported_marks`** (engine.py:446-466) — replace the loop body:

```python
def _reported_marks(world: NumericWorld, returns: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Appraisal-smoothed marks for pe/pc/re: nonzero only at quarter-ends.

    The quarter-end mark filters the WHOLE quarter's compounded true return:
    ``rep_q = w * q_true + (1 - w) * rep_{q-1}`` (Geltner partial
    adjustment, unit DC gain, so cumulative reported catches up to
    cumulative true). History: until toy-v0.6 this filtered only the
    closing MONTH's return, discarding the quarter's other two months —
    reported PM cumulated ~1/3 of truth (ER-10, found 2026-08-12 by the
    owner reading a chart)."""
    smoothing = world.structural.smoothing
    weights_model = smoothing.weights_on_truth if smoothing else None
    weights = {
        "pe": _f(weights_model, "private_equity", _DEF["smooth_pe"]),
        "pc": _f(weights_model, "private_credit", _DEF["smooth_pc"]),
        "re": _f(weights_model, "real_estate", _DEF["smooth_re"]),
    }
    out: dict[str, np.ndarray] = {}
    for sleeve in REPORTED_SLEEVES:
        w = weights[sleeve]
        true = returns[sleeve]
        rep = np.zeros(len(true))
        prev = 0.0
        for m in range(len(true)):
            if (m + 1) % 3 == 0:  # quarter-end month
                q_true = (
                    (1.0 + true[m - 2] / 100.0)
                    * (1.0 + true[m - 1] / 100.0)
                    * (1.0 + true[m] / 100.0)
                    - 1.0
                ) * 100.0
                prev = w * q_true + (1.0 - w) * prev
                rep[m] = prev
        out[sleeve] = rep
    return out
```

- [ ] **Step 4: Bump the version** — engine.py:51: `TOY_ENGINE_VERSION = "toy-v0.6"`.

- [ ] **Step 5: Run the two catch-up tests → PASS; run the neighboring
  reported tests unchanged → PASS**

Run: `uv run pytest tests/test_engine.py -k "catch_up or reported" -q; uv run pytest tests/test_gen_adapter.py -k catch_up -q`
(The file-level hash-pin tests will fail — that is Task 3's job, not a
reason to touch them now.)

- [ ] **Step 6: Commit** (tests + engine only)

```bash
git add tests/test_engine.py tests/test_gen_adapter.py src/ah/core/engine.py
git commit -m "fix(ER-10): reported marks filter the whole quarter; toy-v0.6; catch-up invariant (TDD)"
```

---

### Task 2: World fences + fixture regeneration

**Files:**
- Modify: the five preset JSONs (world_ids per the file map)
- Regenerate: `app/fixtures/toy.bundle.gz`, `app/fixtures/gen.bundle.gz`

- [ ] **Step 1: Move the fences.** In each preset JSON change ONLY the
  world_id tail: stagflation `…501→…511`, goldilocks `…502→…512`,
  deflation_bust `…503→…513`, reflation_boom `…504→…514`,
  stagflation_1974 `…602→…603`. Grep the repo for each old id
  (`000000000501` etc.) — code/tests/fixtures update; historical
  docs/evidence stay.

- [ ] **Step 2: Regenerate both bundles**

Run: `uv run python scripts/gen_bundle_fixtures.py`
Expected: BOTH bundles rewritten (this time the toy bundle legitimately
changes — the engine's reported numbers moved). Decode both and assert the
world_ids inside are `…511` (toy) and `…603` (gen).

- [ ] **Step 3: Regenerate any other engine-derived committed fixture** —
  check `scripts/gen_presets.py --help`/source: if it stamps built worlds or
  digests, re-run it; `scripts/gen_fixtures.py` (compiler fixtures) is
  validator-level and should NOT change — if it does, STOP.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(ER-10): world fences 501-504->511-514, 602->603; bundles regenerated under toy-v0.6"
```

---

### Task 3: The mechanical re-pin sweep

**Files:**
- Modify: every test the full suite flags (expected list in the file map).

- [ ] **Step 1: Run the FULL suite to a log**

Run: `uv run pytest -q > sweep.log 2>&1; echo "EXIT: $?" >> sweep.log`
Then READ sweep.log (own step, never tail-chained).

- [ ] **Step 2: For each failure, attribute it** to one of exactly three
  causes: (a) a digest/value golden encoding toy-v0.5 numbers, (b) a
  world_id pin encoding the old fence, (c) anything else → STOP and report
  BLOCKED with the failure (an unattributable failure means the fix touched
  something it should not have).

- [ ] **Step 3: Re-pin (a) and (b)** — exact-value swaps only, each
  docstring gaining "re-pinned under toy-v0.6 (ER-10)". The
  `test_play_linkage` golden (86.32350859293307) will move: record old→new
  in the commit body. Hypothesis/property tests should pass untouched — if
  one fails, that is a (c).

- [ ] **Step 4: Full suite again → green; ruff + pyright → clean; app suite**

Run: `uv run pytest -q > sweep2.log 2>&1; echo "EXIT: $?" >> sweep2.log` (read it);
`cd app && npm run typecheck && npm run test` (bundle contract unchanged;
fixtures already regenerated).

- [ ] **Step 5: Commit** with every re-pin listed old→new in the body.

```bash
git add -A
git commit -m "test(ER-10): re-pin goldens under toy-v0.6 (list in body)"
```

---

### Task 4: Console reported-plane check, test-first

**Files:**
- Modify: `tests/test_credibility.py`, `src/ah/credibility.py`

**Interfaces:**
- Produces: each private sleeve's world report carries
  `catchup_ratio: float` (cumulative reported / cumulative true on the base
  path) flagged outside `(0.8, 1.2)`; rendered in the console's per-sleeve
  details with the existing flag styling.

- [ ] **Step 1: Failing test** (follow test_credibility.py's existing
  build_report harness conventions — toy preset + the gen walk):

```python
def test_console_carries_reported_catchup_ratio_er10():
    """ER-10 follow-through: the console now audits the REPORTED plane.
    The 2026-08-12 defect (reported ~1/3 of truth) was invisible because
    the console only checked true series."""
    report = build_report([_STAGFLATION])  # reuse the file's fixture path
    world = report["worlds"][0]
    for sleeve in ("pe", "pc", "re"):
        entry = world["sleeves"][sleeve]
        assert 0.8 < entry["catchup_ratio"] < 1.2
        assert entry["catchup_flagged"] is False
```

(Adapt the two lookup lines to build_report's actual payload shape — read
the file's existing assertions first; the REQUIREMENT is the two fields per
private sleeve, flag boundaries (0.8, 1.2), and rendering.)

- [ ] **Step 2: Watch it fail** (KeyError on the new fields).

- [ ] **Step 3: Implement** in credibility.py where per-sleeve stats are
  computed: `catchup_ratio = rep.sum() / true.sum()` guarded for
  `abs(true.sum()) < 5.0` (ratio meaningless near zero → ratio `None`,
  never flagged, rendered as "n/a"); `catchup_flagged = not (0.8 < r < 1.2)`
  when computed. Render one row in the sleeve details table ("reported
  catch-up: 0.97x") with the standard flag class when flagged.

- [ ] **Step 4: Test passes; whole credibility suite green; commit**

```bash
uv run pytest tests/test_credibility.py -q
git add tests/test_credibility.py src/ah/credibility.py
git commit -m "feat(ER-10): console audits the reported plane (catch-up ratio + flag)"
```

---

### Task 5: Register + docs

**Files:**
- Modify: `docs/engine-realism-register.md`, `CLAUDE.md`, `CHANGELOG.md`

- [ ] **Step 1: ER-10 entry** in the register, matching its house format:
  found 2026-08-12 (owner, reading the 1974 fan charts); mechanism (old
  code's single-month filter); magnitude (reported ≈ 1/3 of true; stagflation
  pc 23% vs 77%, 1974 pe 27% vs 125%); status **CLOSED 2026-08-13,
  toy-v0.6**; what the fix invalidated (every run digest; preset world
  blocks 501–504→511–514 and 602→603; both committed bundles; the play
  goldens; leaderboard rows under old world_ids are fenced, not deleted);
  the two guards that make recurrence impossible (catch-up invariant test,
  console reported-plane check). Note reported marks feed DISPLAY and the
  reported-basis session value; alpha is player-minus-twin so the bias
  largely cancelled — levels were wrong, rankings mostly weren't.
- [ ] **Step 2: CLAUDE.md** — update the register summary line (ER-10
  closed; ER-1/3/4/6/7 closed; ER-2/5/8/9 family unchanged) and the
  `toy-v0.5` mention if the text pins the version.
- [ ] **Step 3: CHANGELOG** entry under 2026-08-13, same facts in three
  lines.
- [ ] **Step 4: Commit**

```bash
git add docs/engine-realism-register.md CLAUDE.md CHANGELOG.md
git commit -m "docs(ER-10): register entry CLOSED, CLAUDE.md register line, changelog"
```

---

### Task 6: Console walk + play spot-check (the merge gate)

**Files:** none — verification, findings recorded for the merge commit body.

- [ ] **Step 1:** `uv run ah credibility --preset stagflation --preset stagflation_1974 --out credibility-er10.html`
  (adjust flags per `--help`). READ it: catch-up rows present and ~1.0x for
  every private sleeve in both worlds; no new flag class; record the values.
- [ ] **Step 2:** Serve on 8787 (kill any listener first), fresh run of
  world `…603`, play a decade via the scratchpad script (fix RID; 9
  windows); confirm: session opens, decade completes, alpha prints,
  telescoping ~0, and — the point of this WP — the reported private lines
  in the outcome/fan payload now GROW across the decade instead of
  flatlining (record cumulative reported vs true for pe). Kill the server.
- [ ] **Step 3:** Anything anomalous → STOP before merge.

---

### Task 7: Gate, merge, push

- [ ] **Step 1:** Full gate to `gate.log` in the background; READ the log as
  its own step (EXIT line + pass count).
- [ ] **Step 2:** `uv run python scripts/check_gate.py gate.log` → `.gate-ok`.
- [ ] **Step 3:** `git checkout main && git merge --no-ff er10-01-reported-marks`
  (body: the fix, the fences, console-walk numbers, re-pin count) and
  `git push origin main`.

---

## Self-review notes

- **Coverage:** engine fix + invariant (T1), fences + fixtures (T2), re-pin
  sweep (T3), console guard (T4), register/docs (T5), walk (T6), discipline
  (T7). The three-part package promised to the owner (fix, invariant test,
  console check) all land.
- **Consumer sweep is mechanical** (full suite, attribute-or-stop), applying
  the `artifact-repoint-consumer-sweep` lesson from yesterday's red gate.
- **Type consistency:** `_reported_marks` signature unchanged; new console
  fields named `catchup_ratio`/`catchup_flagged` in both test and impl.
- **Known risks:** (a) serve's reported-basis session values shift upward —
  expected, world-fenced, and covered by T3's attribution rule; (b) the
  exact payload shape in T4's test needs adapting to build_report's real
  structure — the requirement (two fields, boundaries, render) is fixed even
  where the lookup path is not; (c) `scripts/gen_presets.py` may or may not
  need re-running — T2 Step 3 decides by reading it, with a STOP if compiler
  fixtures move.
