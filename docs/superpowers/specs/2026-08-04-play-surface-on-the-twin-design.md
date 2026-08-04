# Wiring the play surface onto the Step-3 twin

**Date:** 2026-08-04
**Register:** ER-3, second half (first half merged as `ah/play.py` at `0363368`)
**Status:** design approved, awaiting implementation plan

---

## Why

The play surface scores on `ah.core.institution` — Step 0's toy: eight asset
weights, rebalanced, no cash account. Nothing can be owed, so nothing can ever
be *needed*, so a secondary sale is a slider rather than a decision.

Step 3 built the real thing in `ah/port/` — cash account, commitment cohorts,
capital calls, distributions, spending off smoothed marks, and a forced-sale
waterfall — and the product never used it. `ah/play.py` (merged) drives that
waterfall from a toy-engine tape. This design wires the surfaces onto it.

## The constraint that shapes everything

`ah/pacing.py`'s ledger is **decision-independent**: derived from the tape
alone, which is why it could live in the pre-authored bundle (PD-4).
`ah.play`'s cashflows are **decision-dependent** — a secondary sale changes
later calls, NAV and distributions.

So the ledger cannot stay bundle-fed. The resolution splits on that seam:

- the **twin** never acts, so its ledger is decision-independent and stays
  pre-authorable in the bundle;
- **yours** depends on what you did, so it comes from the session service.

This is consistent with the bundle already carrying `summary.twin_final_value`.

## Decisions taken

| # | Decision | Choice |
|---|---|---|
| 1 | Cutover or side-by-side | **Clean cutover.** `ah.play` is the only product scoring path. |
| 2 | Screen budget | **Allocation panel becomes the book.** Real weights, cash, coverage, policy band. |
| 3 | Bundle contents | **The hold-course twin's ledger**, bumped to `world-bundle-0.4`. |

## Architecture

```
ah/play.py ──────────────► ah/serve.py      value, alpha, attribution, ledger
     │                          │
     │                          └──────────► app/  (session-fed: yours)
     └──────────────► ah/bundle.py           twin ledger (decision-independent)
                            │
                            └─────────────► app/  (bundle-fed: the twin's line)

ah/pacing.py            DELETED
ah/core/institution.py  retained, untouched, for Step-5 research only
ah/density.py           retained, untouched, for Step-5 research only
```

`ah.core.institution` and `ah.density` are not deleted: Step 5's research code
and its sealed protocol reference them. They simply stop being the product's
scoring path.

## Components

### `ah/play.py` — one addition

`window_contributions_play(paths, decisions, *, use_reported)` — DN-5's
sequential chain-link decomposition, ported from `ah/density.py` to run over
`simulate_play`. Same structure (the twin plus one run per decision prefix,
K+1 runs for K windows, exact and unsampled), same return shape.

Porting is not optional: attribution computed on the toy would not sum to the
alpha displayed beside it, which is a broken reckoning rather than an
approximate one. Cost is 10 simulations for 9 windows; the full run measured
well under a second.

`ah/density.py` keeps its `simulate_institution` version unchanged for
research.

### `ah/serve.py`

- `_mark_to_market` and `outcome` switch to `simulate_play` / `play_alpha`.
- Sessions stamp `PLAY_ALPHA_VERSION = "port-v1-cashflow"` rather than reading
  `decision_alpha_version` off the RunRecord. Old rows keep their old string,
  so boards separate without a migration and nothing already scored changes.
- The session payload gains: `cash`, `coverage_true`, `coverage_reported`,
  `private_weight_true`, `private_weight_reported`, the current quarter's
  flows (`calls_paid`, `distributions_received`, `spending_paid`,
  `forced_sale_total`), and the forced-sale log entries at or before the
  reveal pointer.
- Every added field is computed from **revealed months only**, so nothing
  leaks: the same simulation the outcome runs, truncated at the pointer.

### `ah/bundle.py`

`BUNDLE_VERSION` `world-bundle-0.3` → `world-bundle-0.4`. The `private` key is
replaced by `twin_ledger`, built from `simulate_play(paths, None)` and carrying
per-quarter calls, distributions, NAV, cash, unfunded and the twin's
private weight. `app/src/lib/bundle.ts` adds `0.4` to
`SUPPORTED_BUNDLE_VERSIONS` and types `twin_ledger`; `private` is removed from
the type.

`ah/pacing.py` and `tests/test_pacing.py` are deleted in the same commit as
the key they fed.

### `app/`

- `Allocation.tsx` → `Book.tsx`. Shows actual weights on both planes, cash,
  coverage, and the private-weight policy band with a breach flag, plus the
  reported-vs-true gap stated in words. The TS mirror of `institution.py`'s
  target bookkeeping is deleted with it — under the twin, targets are not the
  mechanic (private cohorts are not dials), so a mirror of them would be
  actively misleading.
- `PrivateMarkets.tsx` reads the session's ledger, falling back to the
  bundle's `twin_ledger` in browse mode and offline (W8 preserved).
- `DecisionWindow.tsx` copy: the secondary card names the real consequence —
  raises cash at the policy haircut — rather than describing a weight move.

### The wire

Forced sales land as feed events. `ah/artifacts/templates.py` already carries
`forced_sale_event` and `capital_call_event` from Amendment A1 Delta 2, written
at Step 4 and unused since. These are what they were written for. They are
emitted by the session service as the pointer passes them, not baked into the
bundle, because they are decision-dependent.

## Data flow

| Trigger | Server | App |
|---|---|---|
| advance | `simulate_play` over revealed quarters | render book + flows |
| decide | same; the action applies at the next quarter boundary | render, plus any forced sale on the wire |
| complete | `play_alpha` + `window_contributions_play` | reckoning, per-window attribution |

Ranked completion writes the leaderboard under `port-v1-cashflow`.

## Error handling

- Cash cannot go negative: the waterfall guarantees it and `test_play.py`
  asserts it. No endpoint needs to defend against it.
- A forced secondary is a **logged event with a cause**, never a silent
  number. The session surfaces the log; the wire prints it.
- If `simulate_play` raises on a stored session, the endpoint returns 500. It
  does **not** fall back to the toy institution: silently scoring a session
  under a different model is worse than an error, because it is invisible.
- Bundles below `0.4` still load (older versions stay supported); the app
  hides the private panel when no `twin_ledger` is present rather than
  erroring.

## Testing

| Area | Test |
|---|---|
| attribution | per-window contributions **sum to the alpha shown** — the property that made porting mandatory |
| scoring | serve's value/alpha tests re-pointed at `ah.play`; hold-course scores exactly 0.0 |
| leakage | added session fields are a function of revealed months only |
| contract | bundle `0.4` carries `twin_ledger`, one entry per quarter, no `private` key |
| cross-language | `app/fixtures/toy.bundle.gz` rebuilt; both suites verify the seal |
| app | `Book.tsx` renders weights/cash/coverage/band; a forced secondary surfaces on the wire |
| deletion | no module imports `ah.pacing` |

## Scope

**In:** the four components above, the bundle bump, the fixture rebuild, and
deleting `ah/pacing.py`.

**Out:** `hier-flow-v1` worlds; M4 first-run consent; register entries ER-2
(no meeting calendar) and ER-5 (crisis is a rectangular block).

## Consequences the owner has accepted

- **Any open session ends.** Mechanically: there is one code path, so a
  pre-cutover session reopened after the change is scored by the twin, and its
  numbers move. Sessions are not migrated and not refused — they are simply
  scored by the only simulator that exists. A ranked session that already
  COMPLETED wrote its leaderboard row under the old version string, and that
  row is immutable, so no existing score is corrupted or silently restated.
  A session in flight cannot be carried across coherently and should be
  abandoned.
- Numbers seen before the cutover will not reproduce — different institution,
  different alpha.
- Old leaderboard rows remain readable under their original alpha version and
  stop being added to.

## What this does not touch

`ah.eval.decision_metrics.DECISION_ALPHA_VERSION` names Step 5's research
definition and sits inside the **G5** seal (`step5-evaluation-protocol.yaml`,
`sealed: true`). It is not bumped. The product carries its own version string
precisely so that it need not be.
