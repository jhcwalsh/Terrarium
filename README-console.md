# README-console.md — the internal QA inspection console

An operator instrument for eyeball-testing what the engine actually produces,
world by world. **Not the player product.** Information density over polish;
truth over charm.

Every page renders real generated output or an explicit empty state naming the
command that would produce it. Nothing is mocked — enforced by
`tests/test_console_guard.py`, which fails if the module imports a fixture.

---

## Launch

```bash
uv run uvicorn ah.console:app --port 8799
```

Then open <http://127.0.0.1:8799/worlds>. That is the whole bootstrap; the
console reads the repo's default store at `data/ah.db`.

To point it at another store — a scratch QA database, say:

```bash
uv run python -c "import uvicorn; from ah.console import create_app; \
uvicorn.run(create_app('/path/to/qa.db'), port=8799)"
```

### Stack, and why this one

FastAPI serving HTML built in pure Python. FastAPI is already a dependency
(`ah/serve.py`); the HTML technique is the repo's established pattern for
inspection surfaces — `ah/inspect.py`, `ah/credibility.py` and
`ah/programme.py` all render self-contained HTML with inline SVG and no
template engine. Streamlit, Jinja or a JS build step would each add a
dependency the repo's conventions require justifying, to produce a page the
existing technique already produces. **Zero new dependencies.**

### Read-only, structurally

The store is opened `file:...?mode=ro` — a write is refused by the SQLite
driver, not by discipline (`tests/test_console_guard.py::TestReadOnly`). The
module imports no writer; an import-graph test asserts it cannot reach
`save_world`, `save_run_record`, `chronicle.append`, `ah.serve`, the session
store or the leaderboard. The replay check copies the database to a temporary
directory and verifies there. The console writes nothing anywhere.

---

## The pages, and what each one proves

| Page | What it proves |
|---|---|
| `/worlds` | **What exists.** Every world on disk with its spec version, generator, seeds actually run, and coherence-gate result (V1–V12, recomputed live). If a world is here, it was built and stored; if the gate column is red, it should not be played. |
| `/world/<id>/path` | **The decade is well-formed.** Factor paths against the regime spine, crisis markers, the two-plane view, and the sanity strip. A red strip row is a generator defect surfaced — the console earning its keep. |
| `/world/<id>/ensemble` | **The distribution is the right shape.** Fan charts per asset, terminal and drawdown distributions, forced-sale incidence, distribution-drought counts. Flags when `n` is below the world's declared ensemble size. |
| `/world/<id>/cashflows` | **The institution's arithmetic closes.** Per-quarter calls, distributions, spending, NAV on both planes, unfunded, private weight; forced-sale events with their haircut; and a reconciliation footer recomputing the cash identity from the displayed numbers. |
| `/run/<run_id>` | **The record reproduces.** Stored engine/validator/battery versions, the decision list as stored, and a replay check that re-executes in a scratch copy and reports bit-identity. |
| `/battery/<report_id>` | **What the battery actually said.** Per gate: statistic, band, margin, verdict, and ratification status. Deliberately **no aggregate pass/fail badge** — the per-gate table is the truth, and a summary badge invites exactly the spin the evidence discipline forbids. |
| `/diff` | **Unbuilt.** Descoped so the six core pages could be finished and verified. The page says so rather than faking a comparison. |

Every number carries provenance: the italic line under each heading names the
store, table or function that produced it, and the *how these numbers were
produced* disclosures expand to the exact call.

Every page carries the watermark **INTERNAL QA CONSOLE — simulated data — not
investment advice**. Screenshots travel; the DN-2 §8 discipline applies
internally too.

---

## The ten-minute acceptance walk

The ordered sequence an operator visits to convince themselves a freshly
generated world is sound. Timings are from a real walk on the four presets.

**Before you start** (≈2 min) — generate a world and a run if you have none:

```bash
uv run ah --db /tmp/qa.db world build --preset stagflation
uv run ah --db /tmp/qa.db run --paths 120
```

**1. Shelf** (30 s) — `/worlds`.
Confirm the world is listed, `status` is `validated`, the generator is what you
expect, and the coherence column reads **V1–V12 clear**. A blocking count here
stops the walk: fix the spec first.

**2. Path sanity strip** (2 min) — `/world/<id>/path`.
Go straight to the sanity strip, above the charts. Every row should read `ok`.
The header states the count: *no structural breach*. A red row names the series
and the constraint — policy rate below its floor, spread below its floor, or a
non-positive cumulative growth (a negative price). **A breach here is a
generator bug, not a display bug.**

**3. Two-plane gap** (2 min) — same page, *The two planes* section.
For each of `pe`, `pc`, `re`, the reported line should lag the true line with a
visible filled gap between them. The caption gives terminal true vs reported and
their difference. A gap of zero means the smoothing weights are not being
applied and the product's central claim is not being simulated.

**4. Cashflow reconciliation** (2 min) — `/world/<id>/cashflows`.
Scroll to the reconciliation footer. It should read *cash identity holds on all
40 quarters*. Then scan the ledger for forced-sale rows and check the
forced-sale table beneath — a `forced_secondary` row is distress and should be
rare; `liquid_pro_rata` is ordinary funding. On the four presets,
`deflation_bust` is the one that produces a forced secondary.

**5. Ensemble shape** (2 min) — `/world/<id>/ensemble?paths=120`.
Check the fan charts widen with horizon rather than collapsing or exploding,
the terminal-growth histogram is not degenerate, and the header does not warn
that `n` is below the declared ensemble size. Forced-sale incidence across
sampled paths is printed under the histograms.

**6. Replay tick** (1 min) — `/run/<run_id>`, then click **Run replay check**.
Green tick, "bit-identical", with the stored and recomputed digests shown side
by side. A mismatch means the record cannot reproduce under the current engine —
see the defect note below, because that is not hypothetical.

Total: **under ten minutes** on a real world.

---

## Acceptance evidence

**1. One command against existing output.** `uv run uvicorn ah.console:app
--port 8799` — verified against the repo store (2 worlds, 5 runs) and a scratch
store (4 preset worlds, 4 runs).

**2. Zero mocked content.** `tests/test_console_guard.py::TestReadOnly::test_no_fixture_is_imported`
parses the module's import graph and fails on any fixture/mock import. Empty
states are real: pointing the console at a non-existent database renders *Not
available … Produce it with `ah world build --preset stagflation`*.

**3. The checks recompute.** Both are pure functions — `ah.console.sanity_rows`
and `ah.console.cash_identity` — precisely so a corrupted copy can be driven
through the same code path the pages use:

```bash
uv run python scripts/console_corruption_demo.py /tmp/qa.db
```

Real output from that script:

```
SANITY STRIP, clean world
  10 series checked, 0 breach(es)

  spec-level corruption (vol_annual_pct 400): refused by the contract (ValidationError)

SANITY STRIP, corrupted COPY of EnginePaths (equity m12 = -150%, rate m5 = 0.05)
  10 series checked, 2 breach(es)
    ! policy rate (%): min 0.050000 -> below floor 0.1
    ! equity growth: min -0.696418 -> negative price (cumulative growth <= 0)

CASH IDENTITY, clean ledger
  40 quarters, worst residual 0.000e+00

CASH IDENTITY, corrupted COPY (+0.25 to Q21 cash)
  quarters flagged: [20, 21]
    ! Q21 residual +0.2500
    ! Q22 residual -0.2500

--- acceptance #3 ---
  sanity strip recomputes : PROVED
  cash identity recomputes: PROVED
```

Both corruptions are applied to in-memory copies; no record is touched. Note the
middle line — corrupting the *WorldSpec* does not work, because the contract
bounds `equity.vol_annual_pct` at 45 and refuses the document before the engine
runs. That is the schema doing its job, and it is why the demo corrupts the
`EnginePaths` the strip actually consumes.

**4. Replay green on three or more real runs.** On a scratch store built from
the four presets: **4 of 4 green.** On the repo's own store: **1 of 5** — see
the defect note below.

**5. The walk completes in under ten minutes.** Verified on
`00000000-0000-4000-9000-000000000301` (stagflation) in the scratch store.

---

## What the console found on day one

The point of the instrument. All three were surfaced by building and running it.

**1. Four of five stored RunRecords do not reproduce under the current engine.**
Replaying the repo's own store gives 1 green and 4 mismatches. The cause is
visible in the records themselves:

| run | world | engine stamped | current | replay |
|---|---|---|---|---|
| `8c89a09c` | …000001 | `toy-v0` | `toy-v0.3` | mismatch |
| `9b840e46` | …000001 | `toy-v0` | `toy-v0.3` | mismatch |
| `8f09a129` | …000001 | `toy-v0` | `toy-v0.3` | mismatch |
| `5ff91028` | …000001 | `toy-v0` | `toy-v0.3` | mismatch |
| `694a716f` | …000301 | `toy-v0.3` | `toy-v0.3` | **green** |

Two distinct problems. The four stale records were written before `cli.py:216`
began stamping `TOY_ENGINE_VERSION`, so they record the generator *family*
(`toy-v0`) where the current code records the resolved *version* — the stamp
cannot distinguish the engine that made them. And they sit under world
`…000001` alongside nothing newer, while `CLAUDE.md`'s convention is that when
the engine's numbers change the presets move to a **new `world_id` block**, "so
scores from two engines cannot share a leaderboard row". Here one `world_id`
carries records from two engine generations, and only the console makes that
visible. Neither the CLI nor the store refuses it.

**2. The engine's structural constraints hold on all four presets.** Sanity
strips clean, 10 series each: no rate below floor, no spread below floor, no
non-positive cumulative growth. Reported as a negative finding because it is
one — the check ran and found nothing.

**3. The cash identity closes exactly on all four presets** — worst residual
`0.000e+00` over 40 quarters, not merely within tolerance. The waterfall and the
ledger display agree bit for bit.

---

## Known limits of this console

- **`/diff` is unbuilt.** Descoped, not stubbed.
- **The three series on `/run/<id>` are not shown.** Player, policy twin and
  drift twin are computed by the session service at outcome time and are not
  stored on the RunRecord; the drift twin is `null` by contract in `ah.serve`.
  The page says so and names the endpoint that would produce them, rather than
  inventing a chart.
- **`cost_charged` and per-window `c_j` annotations are not on the record.** The
  sessions table stores `{month: verb}` and a `window_log`; no cost or
  contribution is persisted. The decision table says so per row.
- **Ensemble forced-sale incidence is bounded to the first 40 seeds** for page
  responsiveness. The page states the bound rather than silently truncating.
- **The battery viewer reads report metadata, not git history.** Ratification
  status is derived from each metric's `severity` (`enforce` → pre-registered
  gate; `report` → descriptive) and `status`. The per-gate git determination
  lives in `docs/RESULTS-EDITION-SUMMARY.md`; the console does not duplicate it.
- **Battery reports under `experiments/` are gitignored.** The viewer scans both
  `artifacts/` and `experiments/`, so on a clean clone the campaign-2 cells that
  carry the sealed digest will not be listed.
