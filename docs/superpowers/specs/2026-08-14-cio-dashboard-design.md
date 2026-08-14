# CIO Dashboard — Design

*2026-08-14 · Approved design for integrating the `docs/CIO Dashboard.zip` drop (DN-8 v0.2,
`cioView.ts`, renderer v0.3) into the SU product surface. Companion to
`Instructions/DN-8-cio-dashboard-data-contract.md` once unpacked (WP cio-01).*

---

## 1. What this is

The CIO dashboard becomes **the play surface** of the allocator flight simulator. The
existing `Play.tsx` panels (Book, PrivateMarkets, AnalysisChart) retire after cutover; the
dashboard absorbs the contextual feed (wire digests, newspapers, central-bank statements,
quarterly statements, board packs) and the decision tools, and adds the Plan / Liquidity /
Private cashflows / Markets tabs from the drop.

DN-8's governing rule is adopted unchanged: **the dashboard is a pure renderer.** Every
number on screen arrives in a single `CioView` payload; the renderer's only arithmetic is
the exhaustive list in DN-8 §8. One correction to DN-8's architecture diagram: in this
codebase `buildCioView` lives **server-side in Python**, not in TypeScript. A RunRecord
here is a thin lineage pointer with no portfolio state; the established pattern is
`_mark_to_market()` in `ah/serve.py`, which replays the session server-side because "the
server is the authority for value" (DN-3 W5, a hard invariant). `cioView.ts` remains the
client's wire type and dev-mode validator. This satisfies DN-8 §1 more strictly than the
drop's own diagram.

## 2. Decisions taken (DN-8 open items)

Resolved with the owner on 2026-08-14. These are to be recorded in DN-8 itself when it is
unpacked into `Instructions/` (WP cio-01).

| Item | Decision |
|---|---|
| Surface placement | In-session player surface; **the dashboard becomes the play surface** (cockpit), not a second view and not a post-session debrief. |
| ⚑ O-1 pre-run history | **Option A — generate pre-history** (inherited plan + market history, hatched band, real long columns). Built as its own engine/generator WP with its own gate (cio-04). **Dashboard ships first** with `worldStartIndex: 0` and nulled long columns (option-B behaviour as a transitional state); the contract supports both, so nothing is thrown away when A lands. |
| ⚑ O-2 planes | `planesAvailable: ["reported", "true"]`. This tier plays a generic portfolio, so the institutional-tier auditor problem does not bite. The true plane is labelled **"engine true state"** — in this codebase it genuinely is the engine's true NAV (`nav_true`), not a de-smoothed estimate. |
| ⛔ O-3 macro state | **Observables only.** The Markets tab shows indexed returns, realised correlations, and level series already on the revealed tape (rates, spreads). `markets.conditions` (the latent L1/L2 regime state) is omitted entirely from the player build — consistent with the help agent's information wall. The player infers conditions from data and the feed's narration, as a real CIO does. |
| ⚑ O-4 liquidity tiers | Static class→tier policy mapping in v1, footnoted as such. Behavioural re-tiering deferred. |
| ⚑ O-5 goal mapping | Fixed taxonomy (growth / real return / income / diversifiers), shipped as a policy input alongside the world's policy spec. Not client-configurable. |
| ⚑ O-6 coverageDanger | Remains unset until P-B is filled; coverage renders against the 0.50 anchor only. Unchanged from DN-8. |
| ⚑ O-7 per-class privates | v1 private series = `aggregate` + **closed-end classes only**. The class × archetype crossed key is deferred with the cohort-model work. |
| ⚑ O-8 open-end vehicles | Open-end/evergreen sleeves are **explicitly excluded** from the private tab with a stated reason in the footnote — never rendered as `coverage: 0` / flat call rate. |
| ⚑ O-9 plane-transform sign | Dissolves in this codebase. Reported-vs-true divergence is whatever the engine's `_reported_marks` produced for this world state; the builder reports it and never picks a sign. The interpretation guide explains both directions. |
| ⚑ O-10 alert rules | v1 uses the `alertPolicy.watchFraction` fallback. Engine-supplied `alert` (persistence, direction of travel, private-class actionability) is deferred; the contract field already exists, so the upgrade is additive. |

**Known gap:** DN-8 §1 and DN-5 both cite a "launch strategy" document that does not exist
in the repo. The design anchors to what does exist (DN-2's institution plane, DN-3, DN-5,
WP3.9/3.10's institutional-tier boundary). If the launch strategy document surfaces, drop
it into `Instructions/` and reconcile.

## 3. Architecture and data flow

```
session doc ──► simulate_play (truncated at reveal pointer)
                     │
                     ▼
        build_cio_view(state, plane, forecast_quarters)   ← ah/cioview.py, pure, no I/O
                     │
                     ▼
        GET /sessions/{sid}/cio?plane=reported|true  ──►  CioView JSON
                                                              │
                     app/: CockpitShell ──────────────────────┘
                       ├─ <CIODashboard view={…}/>   pure renderer (drop, converted to TSX)
                       ├─ WireRail                   feed items ≤ reveal pointer (bundle.feed)
                       ├─ DecisionWindow             carried over, posts /sessions/{sid}/decisions
                       └─ AdvanceBar                 as-of cursor, advance, plane toggle, provenance
```

- **Plane change is a refetch.** `onPlaneChange` triggers a new GET; the client transforms
  nothing.
- **Determinism.** Same session state + same options ⇒ byte-identical `CioView` JSON. No
  clocks, no locale, no unordered keys where order is displayed.
- **The feed and decision tools ride outside `CioView`.** They use the existing bundle
  `feed` section and the existing session endpoints unchanged, so the numeric contract
  stays pure. The dashboard renders numbers; the shell composes context and actions
  around it.
- Optional blocks degrade per DN-8 §2: absent `markets.conditions`, absent `benchmark`,
  absent `sourcing` render as omitted panels, never as empty frames or zeros.

## 4. The builder — `ah/cioview.py`

A pure function from replayed play state to `CioView`. Field provenance:

| CioView block | Source in this codebase |
|---|---|
| `meta` | RunRecord header + session. `linkageVersion` from the resolved cashflow mapping (`public-0.1`); `decisionAlphaVersion` from the engine dispatch (`PLAY_ALPHA_VERSION` / `GEN_PLAY_ALPHA_VERSION` — leaderboards never mix engines). |
| `plan.history` | **New:** monthly `nav_true` / `nav_reported` recorded in `ah/play.py`. The engine is monthly underneath (`PlayQuarter` is a quarterly aggregation); this is exposure of existing state, not new modelling. `worldStartIndex: 0` until cio-04. |
| `allocation` | Sleeve registries → asset classes; fixed goal taxonomy per O-5; targets/bands from the policy spec; `currentPct`/`value` plane-sensitive via `nav_true`/`nav_reported`. |
| `performance` | Monthly NAV series → period returns (1Q/YTD/1Y/3Y/5Y/10Y, annualised from the index the payload states); unreached periods are `null`, never 0. `benchmark` = the hold-course twin's path, already computed for alpha. |
| `liquidity.tiers` | Static class→tier mapping (O-4); tiers sum to plan total by construction; `classIds` populated for audit. |
| `liquidity.forecast12m` + forecast quarters | Tier-1 cashflow recursions (`f_dist`, `f_call`) rolled forward with the pacing schedule held fixed and current drawdown/spread state frozen. Every forward row carries `forecast: true` and the renderer's "ROLL-FORWARD, NOT A PROJECTION" caption — part of the contract, not decoration. `forecast_quarters: 0` suppresses the region entirely. |
| `privateCashflows` | `PlayQuarter` series + vintage ledger. v1: `aggregate` + closed-end classes (O-7); open-end/evergreen excluded with stated reason (O-8). Signs per DN-8: calls/distributions are positive magnitudes; `net = distributions − calls`. |
| `markets.returns` / `correlations` | Revealed tape only, indexed to 100 at window start; correlation window length stated in `correlationNote`. `conditions` omitted (O-3). |

Conventions enforced: percent as percentage points; `Ratio` fields as decimals; missing is
`null`, never 0, never a short array; arrays ordered as displayed with classes grouped in
goal order (the donut walks them sequentially).

## 5. Endpoint and session semantics

`GET /sessions/{sid}/cio?plane=reported|true&forecast_quarters=N` on `ah/serve.py`.

- Reveal-pointer-truncated like every session read; nothing beyond the pointer leaks.
- Read-only and idempotent: no new session state, no writes.
- Follows the `_mark_to_market` replay pattern; shares its truncated `simulate_play` state
  rather than recomputing divergently.
- `planesAvailable: ["reported", "true"]` per O-2.
- Localhost single-user, no auth (PD-3) — unchanged from the rest of the service.

## 6. The cockpit shell — `app/`

- **Conversion:** the 73KB JSX converts to TSX under `app/src/`, adopting `cioView.ts` as
  the wire type. The mock block at the foot of the file is deleted on wire-up (its own
  instruction). The client-side `validateCioView` runs in dev mode only; the Python port
  is the CI authority.
- **Restyle:** the drop's hard-coded palette/fonts are replaced by the app's vitrine CSS
  variables (`--glass`, `--panel`, `--ice`, `--brass`, `--jade`, `--clay`) and typefaces,
  so the app stays one visual system. Both codebases are hand-rolled SVG — **no new
  dependencies** (`react`/`react-dom` remain the only deps).
- **Layout:** dashboard tabs (Plan / Liquidity / Private cashflows / Markets) centre-stage.
  **WireRail** on the right: feed items up to the reveal pointer — FOMC/central-bank
  statements, newspapers, wire digests, quarterly statements — with **board packs as the
  entry point to decisions**. **DecisionWindow** carried over functionally unchanged,
  opening from the board pack during decision months, posting to the existing endpoint.
  **AdvanceBar** across the top: as-of label, advance control, plane toggle; run id / seed
  provenance in the footer per DN-8's traceability claim.
- **Carried over:** DecisionWindow, Feed (as WireRail), FanChart (into the Plan tab — the
  percentile cone against the revealed path is teaching material the CIO mockup lacks),
  Provenance, Ticker.
- **Deleted after cutover (cio-03):** Book, PrivateMarkets, AnalysisChart from the
  in-session surface. Reckoning keeps its own outcome charts. RankedSetup and Reckoning
  are untouched.
- The server remains the authority for value and scoring; the client mirrors target
  weights at most (simple bookkeeping, per the standing invariant).

## 7. Testing

1. **Python validator** — a port of `validateCioView` as the single source of truth for
   tolerances; runs in CI against a golden session built on the committed toy bundle. The
   TS validator runs dev-only.
2. **Determinism** — `build_cio_view` called twice with identical arguments produces
   byte-identical JSON, on both planes.
3. **Parity** — `coverage`, `private_weight`, `cash`, `value` in the CioView equal
   `_mark_to_market`'s fields for the same session at the same pointer. The two payloads
   can never disagree.
4. **DN-8 §8 acceptance items 1–9** as the component/builder test suite: forecast
   suppression at `forecast_quarters: 0`; omitted-blocks degradation (no empty frames);
   `worldStartIndex: 0` renders no hatched band; nulls render as em dashes, never `+0.0`;
   weights sum to 100 ± 0.1 on both planes; tiers sum to plan total ± 0.5%; aggregate
   private series equals the sum of class series; no-alert-policy payloads flag breaches
   only; every rendered figure traces to a `CioView` field (grep the component for
   arithmetic outside the permitted list).
5. **App suite** — vitest component tests colocated per existing convention; typecheck and
   build green.
6. **Console walk before merge** — the new numeric surface walks through the credibility
   console checks (standing practice; it has caught adapter defects the unit suite
   missed).
7. Standing gates: full pytest suite (no network), ruff, pyright, coverage ≥ 90 on
   `ah.core`, gate log validated by `scripts/check_gate.py` before any merge to main.

Seal note: `ah/play.py`, `ah/serve.py`, and the new `ah/cioview.py` are **not** in the
pre-registration seal's `hashed_files` (verified 2026-08-14). No seal amendment needed.

## 8. Work packages

| WP | Branch | Contents | Gate |
|---|---|---|---|
| cio-01 | `cio-01-view-builder` | Unpack DN-8 + `cioView.ts` into `Instructions/`; record §2 decisions in DN-8 and mark items resolved; monthly NAV recording in `play.py`; `ah/cioview.py`; `/sessions/{sid}/cio` endpoint; Python validator; golden + determinism + parity tests | full suite |
| cio-02 | `cio-02-renderer` | JSX→TSX conversion; vitrine restyle; `cioView.ts` adopted; mock block deleted; wired to the endpoint; ships **alongside** Play as a toggle (explicitly a scaffold state, not the end state) | app typecheck/test/build + full suite |
| cio-03 | `cio-03-cockpit` | WireRail + DecisionWindow + FanChart embedded; AdvanceBar; cutover; Book/PrivateMarkets/AnalysisChart deleted | full gate + manual session walk |
| cio-04 | `cio-04-prehistory` | Engine/generator pre-run pass; inherited-plan warm-up; V-rules applied to the pre-history; `worldStartIndex` goes live; long return columns populate | its own gate; **dashboard unchanged** — that is what the contract buys |

Sequencing: cio-01 → cio-02 → cio-03 strictly ordered; cio-04 independent after cio-01 and
may proceed in parallel with cio-03. One WP per branch, `--no-ff` merges, gate-log
discipline per the repo's working conventions.

## 9. Out of scope

- Engine-supplied alert levels (O-10) — contract-ready, deferred.
- Behavioural liquidity re-tiering (O-4 second half).
- Class × archetype private pooling (O-7 second half) and `coverageDanger` (O-6 / P-B).
- The institutional tier proper (a client's own portfolio, `panel-1.0` linkage, the O-2
  auditor question) — this design ships the generic-portfolio tier.
- New decision levers (the E1 commitment lever is its own track; the cockpit re-houses the
  existing decision tools unchanged).
- Any change to scoring, alpha definitions, or the leaderboard.

---

*Standing caveat carried forward: `hier-flow-v1` is not a convincing model of history
(G2-EVIDENCE §7–8), and the translation layer carries a recorded FAIL against the 2022
episode. The dashboard renders what the engine produces and inherits those caveats; it is
a product surface, not a decision-ready instrument.*
