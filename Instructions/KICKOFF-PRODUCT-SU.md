# KICKOFF — the single-user product build (decisions RESOLVED)

*Drafted 2026-08-03, at Step 5's close. Governs mode 1 of
`product-sequencing-note.md` ("single-user — first, and multi-purpose:
testing, demos, potentially a standalone product"). Consumes DN-3 (the
ratified W1–W10 architecture), the experience-deltas register (E1–E8,
which this build exists to close), DN-5 (the outcome measure), and
DN-6 §8 (the logging schema needed from the first ranked run). The
owner is the first cohort (D-K4-5); no external release before I5 and
the M4 consent clause.*

## 1. What already exists (the build consumes, not reinvents)

| DN-3 need | Engine status |
|---|---|
| World + revealed path + RunRecord lineage | Steps 0–2; `verify_run` regeneration discipline |
| Sealed reveal tape + pointer + information wall | WP4.6 (`ah.artifacts.live`) — exactly W3's mechanics |
| Decision windows incl. event-triggered | WP4.7 (`ah.artifacts.windows/decisions`) |
| Artifacts (wire, letters, notes, board pack) at the shipped ≥95% bar | WP4.2–4.10; authoring pipeline v2 |
| Institutional twin + pacing + forced-sale waterfall | Step 3 (`ah.port`); DN-5's policy twin ratified |
| <500 ms twin interactivity | WP3.9 LSMC proxies (`ah.port.proxy`) — W5's load-bearing piece, built |
| Re-cone ("what could still happen from here") | wp5-03, exact — W5's 1–3 s server call |
| Per-window annotation numbers (E8) | wp5-05 `window_contributions` — DN-5's chain-link, the exact number |
| Outcome-card inputs (E3) | Engine side done (coverage both bases, forced-sale count) |
| Leaderboard, triple-key | Retrofit R-1 + wp5-04 |
| Figure rendering precedent | wp5-02 inspect (self-contained HTML/SVG) |

Genuinely missing: the **world-bundle builder** (W2's contract as a schema +
producer), the **client-plane server** (FastAPI session/decision/export
service), the **SPA itself**, and the **DN-6 §8 logging schema**.

## 2. The vertical slice (what "first playable" means)

Open the app → pick a world → the decade plays at a chosen cadence
(instant / daily-tick demo) → annual decision windows open with the
committee briefing, the four public actions plus the commitment lever
(E1) → the wire and letters arrive in-feed (E2) → the reported-vs-true
toggle works everywhere (I4's surface) → the decade ends on the outcome
card vs the policy twin (E3, DN-5) → the post-game review renders three
series (E7), per-window annotations (E8), the flinch cost and the
arithmetic warning (E4). Owner plays it end to end. That is the slice.

## 3. Work packages

**Engine-side (this repo):**
- `su-eng-01 — the world bundle`: W2's contract as a schema
  (`schemas/`-adjacent, versioned) + `ah bundle build RUN_ID` producing
  path/bands/summaries/artifacts under 1 MB; immutable, keyed by world
  version (W10).
- `su-eng-02 — the session service`: FastAPI app (`ah.serve` or
  app-repo-side, per PD-1) — session + chronicle authority, decision
  endpoints writing the RunRecord/chronicle, twin queries via proxies,
  re-cone endpoint, server-side export with RunRecord id (W7); the DN-6
  §8 log fields from day one (toggle state, time-on-window, arm slot).

**App-side (per PD-1):**
- `su-app-01 — scaffold`: React/TS SPA, local serving, bundle loader,
  IndexedDB cache (W8), fan charts + reveal pointer (W3).
- `su-app-02 — the decision surface`: windows, briefing, actions,
  commitment screen with "holding to plan" affordance (E1).
- `su-app-03 — the feed`: wire/letters/notes render; artifact provenance
  visible (payload hash, world id).
- `su-app-04 — the reckoning`: outcome card (D-03), three-series
  analysis (E7), per-window annotation line (E8), post-game review
  (E4) — closes the register's core rows.
- `su-app-05 — ranked & logging`: practice vs ranked, leaderboard,
  DN-6 §8 fields captured from the first ranked run.
- Later, existing-numbered milestones: help agent (E5, M5); I5
  first-run observation + consent (M4) before ANY external user.

## 4. Decisions (owner, 2026-08-03 — verbatim "1 use app/ folder, 2 through 5 as recommended")

| # | Decision | RESOLVED |
|---|---|---|
| PD-1 | Where the app lives | **`app/` folder in THIS repo** (owner's call, superseding D-K4-2's engine-only boundary — that decision's condition was that the deltas not be lost, and the register stays home; no copy needed) |
| PD-2 | First playable's worlds | **Toy-v0 preset worlds**; generated worlds follow once the bundle carries them |
| PD-3 | v0.1 auth | **None; localhost only** (owner is the cohort) |
| PD-4 | Artifact authoring | **Pre-authored at world build into the bundle** (tier-1 deterministic always; tier-2 letters when a key is present at build, recorded in the bundle either way) |
| PD-5 | Reveal cadence v0.1 | **Player-controlled advance**, daily-tick as a demo toggle |

## 5. Standing constraints (travel with every WP)

Identical worlds/seeds for any comparison; tier-2 authoring only at the
frozen bar; no client-facing actor claims before WP4.9's study; no
external users before I5 + M4 consent; every export carries the
RunRecord id; the deltas register rows close with pointers, never
deletions.

---

*Not investment advice.*
