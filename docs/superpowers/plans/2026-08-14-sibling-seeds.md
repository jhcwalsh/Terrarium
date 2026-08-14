# Sibling Seeds of 1974 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface sibling seeds of the 1974 world (`…603`) as selectable
decades in the app — same scenario, different draws — with every shipped
sibling walked through the credibility console first.

**Architecture:** The server (already the authority for anything that
scores) gains two read-only endpoints: `GET /worlds` (the distinct worlds
+ runs in the store, newest first) and `GET /runs/{run_id}/bundle` (the
world bundle for that run, built by the existing `ah.bundle.build_bundle`
machinery, cached in-process, served as gzip bytes). The app's landing
view gains a "choose your decade" list driven by `/worlds`, falling back
silently to the existing picker/URL flow when the service is absent.
Sibling runs are generated locally at the platform seed stride
(`base_seed + 7919·k`), each must print replay MATCH, and each is
console-walked before being called shippable. No new alpha version, no
engine change, no sealed file.

**Tech Stack:** FastAPI (existing serve), React/TS (existing app), no new
dependencies either side.

## Global Constraints

- **The server stays the sole authority for value/scoring.** The new
  endpoints are read-only conveniences; nothing scoring-related moves
  client-side.
- **No sealed file touched.** `ah/serve.py`, `ah/bundle.py` callers, and
  the app are all unsealed. If any lock digest moves, STOP.
- Bundle bytes served must be IDENTICAL to what `ah bundle RUN_ID` writes
  (same contract `world-bundle-0.5`, mtime=0 determinism) — the app's
  existing seal-verification path must pass on served bundles unchanged.
- Sibling seeds follow the platform stride: seed_k = 197400 + 7919·k.
- **Console walk before merge** for every sibling that ships (memory:
  `console-walk-before-merge`): catch-up rows in (0.8, 1.2), no new flag
  class vs the base seed's walk, tail bands inside the declared bounds.
  A sibling that flags is EXCLUDED and recorded, not tuned.
- Determinism; no network in tests (pytest-socket; FastAPI TestClient is
  in-process and fine); ASCII in CLI echoes; never weaken a test.
- Branch `sib-01-choose-your-decade`; full gate to a log; log read as its
  own step; `scripts/check_gate.py` stamps; merge `--no-ff`; plain push.
- Commits end with the standard trailers.

## File map

- Modify: `src/ah/serve.py` (two endpoints + an in-process bundle cache)
- Test: `tests/test_serve.py` (new TestWorldsAndBundles class)
- Modify: `app/src/App.tsx` (landing list), `app/src/lib/session.ts` or a
  new `app/src/lib/worlds.ts` (fetch helpers + types)
- Test: `app/src/lib/worlds.test.ts`
- Modify: `app/vite.config.ts` (proxy `/worlds` and `/runs` → 8787)
- Modify: `CHANGELOG.md`
- No preset changes; no fixture changes (the committed gen.bundle.gz
  remains the offline test fixture).

---

### Task 1: The two serve endpoints, test-first

**Files:**
- Test: `tests/test_serve.py` (append a class; follow the file's existing
  TestClient + store-fixture conventions — read its setup first)
- Modify: `src/ah/serve.py`

**Interfaces:**
- Produces: `GET /worlds` → `{"worlds": [{"world_id", "title",
  "generator_id", "runs": [{"run_id", "seed", "created_at"}]}]}` —
  distinct worlds from the RunRecords store, runs newest-first; toy AND
  generated worlds both listed (the store is the truth; no filtering).
- Produces: `GET /runs/{run_id}/bundle` → gzip bytes
  (`media_type="application/gzip"`), 404 on unknown run_id. Bytes come
  from the same builder the CLI uses, cached per run_id in a dict on the
  app state (bundles are immutable per run — cache never invalidates).

- [ ] **Step 1: Write the failing tests.** In the new class (adapting to
  the file's real fixture helpers — it already builds worlds/runs in a tmp
  store for TestGeneratedSessions; reuse that):

```python
class TestWorldsAndBundles:
    def test_worlds_lists_the_run_with_its_seed(self, client_with_gen_run):
        client, run_id, world_id, seed = client_with_gen_run
        doc = client.get("/worlds").json()
        world = next(w for w in doc["worlds"] if w["world_id"] == world_id)
        run = next(r for r in world["runs"] if r["run_id"] == run_id)
        assert run["seed"] == seed

    def test_bundle_bytes_match_the_cli_builder_exactly(self, client_with_gen_run, tmp_path):
        client, run_id, _, _ = client_with_gen_run
        served = client.get(f"/runs/{run_id}/bundle")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("application/gzip")
        # authority check: identical bytes to the library builder
        from ah.bundle import build_bundle
        out = tmp_path / "w.bundle.gz"
        build_bundle(run_id, out)          # adapt signature to the real one
        assert served.content == out.read_bytes()

    def test_unknown_run_is_404(self, client_with_gen_run):
        client, *_ = client_with_gen_run
        assert client.get("/runs/no-such-run/bundle").status_code == 404

    def test_bundle_is_cached_not_rebuilt(self, client_with_gen_run, monkeypatch):
        client, run_id, _, _ = client_with_gen_run
        first = client.get(f"/runs/{run_id}/bundle").content
        calls = {"n": 0}
        # adapt the patch target to wherever serve imports the builder
        import ah.serve as serve_mod
        real = serve_mod._build_bundle_bytes
        monkeypatch.setattr(serve_mod, "_build_bundle_bytes",
                            lambda rid: (calls.__setitem__("n", calls["n"] + 1), real(rid))[1])
        second = client.get(f"/runs/{run_id}/bundle").content
        assert second == first and calls["n"] == 0
```

(The exact fixture name and builder signature are adapted to the file —
the REQUIREMENTS are: seed surfaced per run; byte-identity with the CLI
builder; 404; cache hit on second request.)

- [ ] **Step 2: Watch them fail** (`uv run pytest tests/test_serve.py -k "Worlds" -q`).
- [ ] **Step 3: Implement** — `GET /worlds` reads the stores the session
  service already opens (worlds + RunRecords); `_build_bundle_bytes(run_id)`
  calls the same code path as the `ah bundle` CLI into an in-memory
  buffer; `app.state.bundle_cache: dict[str, bytes]`.
- [ ] **Step 4: Green + the WHOLE serve suite green; ruff + pyright; commit.**

```bash
git add tests/test_serve.py src/ah/serve.py
git commit -m "feat(sib-01): /worlds and /runs/{id}/bundle - server-listed decades, CLI-identical bytes (TDD)"
```

---

### Task 2: The app's "choose your decade" landing, test-first

**Files:**
- Create: `app/src/lib/worlds.ts` + `app/src/lib/worlds.test.ts`
- Modify: `app/src/App.tsx`, `app/vite.config.ts`

**Interfaces:**
- Consumes: Task 1's `/worlds` JSON and `/runs/{run_id}/bundle` bytes.
- Produces: `fetchWorlds(): Promise<WorldsDoc>` and
  `bundleUrlFor(runId: string): string` in `worlds.ts`; the landing view
  lists each world's runs as "<title> — seed <seed>" buttons that feed the
  EXISTING `fetchBundle(url)` path (so seal verification and caching are
  untouched). If `/worlds` fails (service down / static hosting), the
  landing renders exactly what it renders today — the picker/URL flow —
  with no error banner (progressive enhancement, not a dependency).

- [ ] **Step 1: Failing tests** in `worlds.test.ts` (vitest, follow
  `session.test.ts` mocking conventions): `fetchWorlds` parses the doc and
  rejects a malformed one; `bundleUrlFor` returns `/runs/<id>/bundle`; a
  render test (renderToStaticMarkup, the Provenance.test precedent — no
  new deps) that the run list shows title + seed and the fallback renders
  without `/worlds`.
- [ ] **Step 2: Watch them fail; implement; watch them pass.**
- [ ] **Step 3: Vite proxy** — add `/worlds` and `/runs` to the existing
  8787 proxy block.
- [ ] **Step 4:** `cd app && npm run typecheck && npm run test && npm run build` all green; commit.

```bash
git add app/src app/vite.config.ts
git commit -m "feat(sib-01): choose-your-decade landing over /worlds; URL flow unchanged as fallback"
```

---

### Task 3: Generate + walk the sibling seeds (the shipping gate)

**Files:** none committed except the walk record in the commit body /
CHANGELOG; runs live in the local store by design (OD-4).

- [ ] **Step 1:** Build the world (`uv run ah world build --preset
  stagflation_1974` — world `…603` exists; idempotent). Generate FOUR
  sibling runs at seeds 205319, 213238, 221157, 229076 (base 197400 +
  7919·k, k=1..4; check `uv run ah run --help` for the seed flag). Each
  must print replay MATCH via `uv run ah replay`.
- [ ] **Step 2: Console-walk all four** (`uv run ah credibility` with the
  preset/world flags — read `--help`; the walk covers the ensemble, and
  the per-run check is the bundle's own credibility section): for each
  sibling record — total flags vs the base seed's 5, catch-up ratios,
  worst drawdowns vs the tail bands. EXCLUDE any sibling with a new flag
  class or an out-of-band tail; record exclusions with numbers.
- [ ] **Step 3: Live end-to-end:** start serve on 8787 (kill any listener
  first — port 8787, never 8000; restart after any serve.py change), open
  the app dev server, confirm the landing lists the base + surviving
  siblings, pick a sibling, verify the seal check passes and a session
  opens; play at least one decision window. Kill the server.
- [ ] **Step 4:** Record the walk table (seed → flags, catch-up, verdict)
  in the Task-3 report and the merge commit body.

---

### Task 4: Changelog, gate, merge, push

- [ ] **Step 1:** CHANGELOG entry (the two endpoints, the landing, the
  walked seeds table, any exclusions).
- [ ] **Step 2:** Full gate to `gate.log` in the background; READ the log
  as its own step (EXIT + pass count).
- [ ] **Step 3:** `uv run python scripts/check_gate.py gate.log`; merge
  `--no-ff sib-01-choose-your-decade`; push.

---

## Self-review notes

- The server-authority invariant is enforced by the byte-identity test
  (served bundle == CLI bundle), not by convention.
- The app change is additive: the URL/file-picker flow is the fallback
  and stays tested; static hosting keeps working.
- The walk is the gate for WHICH siblings ship; the code ships regardless
  (an empty sibling list is a valid, honest outcome — the landing then
  shows only the base decade).
- Risks: (a) `build_bundle`'s signature/CLI wrapper may differ from the
  sketch — tests adapt, requirements don't; (b) `GET /worlds` must not
  assume every stored world has runs (empty runs list is fine); (c) the
  vite proxy addition must not break `npm run build` (build ignores the
  dev proxy).
