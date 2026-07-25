# DN-3 · Web Experience Architecture for Terrarium

*Design note · July 2026 · Companion to DN-2 (Hybrid Deployment). Specifies how the browser experience is built and what crosses each boundary. Decisions W1–W10 ratify alongside D1–D10 and H1–H10.*

---

## 1. The decision

Terrarium's experience layer is a **browser application served from the client-plane server** inside the institution's own environment. No installed software; users need a browser and an SSO login, which is the easiest approval an institutional IT function will ever grant.

This sits naturally inside DN-2's three planes: the browser is a thin presentation layer over the **institution plane**, which holds their data and serves it; the **platform plane** supplies versioned world bundles and model artifacts that the client plane fetches and caches.

## 2. What runs where

| Layer | Location | Responsibility |
|---|---|---|
| Browser (SPA) | User's machine | Rendering, the live clock, decision UI, local interaction state |
| Client-plane server | Institution VPC | Session and chronicle authority, twin queries, portfolio engine, artifact rendering, exports, auth |
| Platform plane | Hosted | World bundle production (ensembles, artifacts, summaries), model registry, releases |

**Stack:** React + TypeScript SPA; FastAPI on the client-plane server (matching the Step-0 Python stack, so one language spans engine and service); world bundles as versioned static assets.

## 3. The world bundle — the payload contract (W2)

The browser never receives an ensemble. Ten thousand decades of factor paths is tens of megabytes and answers no question a user is asking. A **world bundle** contains four things, all precomputed once at world creation:

| Component | Content | Approx. size |
|---|---|---|
| Revealed path | 120 months × ~15 factors + derived series and states | ~40 KB JSON |
| Percentile bands | Fan-chart quantiles per series per month, from the full ensemble | ~100 KB |
| Summary statistics | Tail metrics, regime stats, episode markers, peer distribution | ~10 KB |
| Chronicle + world artifacts | Wire items, letters, research notes, timeline, bible cast | ~300 KB |

**A complete world is under a megabyte compressed.** That single fact is what makes the experience feel instant, makes offline viable, and makes world caching trivial. Institution-specific data (portfolio, cohorts, twin state) is computed by the client-plane server and streamed on demand — also small: a decade of quarterly cashflows across forty cohorts is a few thousand rows.

## 4. Live mode in the browser (W3)

Because reveal is precomputed, the live clock is a **pointer advancing over data the browser already holds**. No server round-trip per tick, no simulation service, no websocket for the single-player case. Consequences worth having deliberately:

- **Offline works** once a world is loaded — genuinely useful for demos, travel, and flaky client networks.
- **Refresh survives**, because the reveal position is a stored integer, not a running process.
- **Decisions require connectivity.** The chronicle is authoritative and server-held; a decision taken offline cannot be trusted to order correctly against others. Rule: offline is read-only experience; acting requires the server. This avoids an entire class of sync-conflict complexity for a feature nobody needs.

## 5. The interactivity budget (W5)

| Interaction | Target | How |
|---|---|---|
| Tick advance, chart redraw | <16 ms | Client-side, data already local |
| Open a decision window, render briefing | <100 ms | Local data + cached artifacts |
| Twin revaluation (hedge ratio, contribution change) | <500 ms | **LSMC proxy models** — this is why Step 3 builds them |
| Re-cone forward (conditional ensemble from current state) | 1–3 s, with progress | Server request against the generation plane |
| Build a new world | Minutes, asynchronous | Platform plane; notify on completion |

The proxy models are the load-bearing piece. Without them, moving a hedge-ratio slider triggers a batch job and the product is a report generator with a web skin. With them, a committee explores the funding-ratio distribution in real time — which is the entire experiential premise.

## 6. Multi-user and wargames (W4)

Single-player needs no coordination. **Shared-clock exercises** — several teams living the same world in sync — need one small mechanism: a server-held reveal pointer that clients poll or subscribe to, with each team's institution state kept separate. Teams share a world; they do not share an institution. Leaderboards and comparative scoring are server-side aggregations at the end, not live state.

## 7. Auth, roles, audit (W6)

OIDC/SAML against the institution's identity provider. Roles: **viewer** (experience worlds), **participant** (act as a committee member), **author** (create and edit worlds), **approver** (move a world to approved status), **administrator**. Every state-changing action — decision, approval, world creation, export — writes to the audit log and, where relevant, the chronicle. The governance question a validator will ask is not "is it secure" but "who could have changed this, and is it recorded."

## 8. Export and watermarking (W7)

All exports render **server-side**: board packs and artifacts to PDF, data to Excel, chronicle to CSV. Watermarking and simulated-world marking are applied in the server-side renderer, never as client-side decoration — a client-side watermark is a suggestion, not a control. Exported artifacts carry the RunRecord id so any printed number traces home.

## 9. Caching and offline (W8)

World bundles cache in **IndexedDB** (not localStorage — size limits bite immediately) with a service worker for the app shell. Bundles are immutable and versioned, so invalidation is trivial: a new world version is a new key. Cache policy: keep the last N worlds a user has opened, evict by recency, and let a user pin a world for offline use before travelling.

## 10. Browser support and accessibility (W9)

Target evergreen Chrome, Edge, Firefox, and Safari — but **check the client's browser estate early**, because parts of financial services still standardize on older builds, and discovering that after building on recent APIs is an expensive week. Accessibility is not optional in institutional procurement: keyboard navigation through decision windows, table alternatives for every chart, and colour-blind-safe palettes — which matters more than usual here, since the product leans on red/green risk framing. Target WCAG 2.1 AA.

## 11. Limitations

A browser can experience worlds; it cannot create them. Compilation, ensemble generation, and artifact authoring stay server-side, which means a **fully air-gapped deployment can live in worlds indefinitely but can only create new ones if the generation plane is also deployed inside the perimeter**. Worth stating before someone asks for a disconnected install. Secondly, very large comparative views (hundreds of paths rendered at once) will need canvas rather than SVG charting — plan the charting abstraction so that swap is possible without rewriting the views.

## 12. Decisions W1–W10

| # | Decision | Recommended default |
|---|---|---|
| **W1** | App placement and stack | React/TS SPA served from client-plane FastAPI server |
| **W2** | World bundle contract and size budget | Path + bands + summaries + artifacts; <1 MB compressed |
| **W3** | Live mode mechanics | Client-side reveal pointer; offline read-only; decisions require server |
| **W4** | Shared-clock coordination | Server-held pointer; shared world, separate institutions |
| **W5** | Interactivity budget | Per §5; proxy-backed twin under 500 ms |
| **W6** | Auth and roles | OIDC/SAML + five roles + full audit |
| **W7** | Export and watermarking | Server-side rendering only; RunRecord id on every export |
| **W8** | Caching and offline | IndexedDB + service worker; immutable versioned bundles; user-pinnable |
| **W9** | Browser matrix and accessibility | Evergreen browsers, WCAG 2.1 AA, estate check early |
| **W10** | Bundle versioning and invalidation | Immutable bundles keyed by world version; no in-place mutation |

## 13. What to do when

**Step 3:** define the world bundle contract formally (it is a schema like any other) and build the twin behind proxy-backed endpoints from the start — retrofitting interactivity is much harder than designing for it. **Step 4:** build the app properly against that contract; the existing prototypes become the design reference, not the codebase. **After G3:** auth integration, export pipeline, wargame coordination, accessibility audit. **Anytime, free:** ask the client's IT what browsers they standardize on.
