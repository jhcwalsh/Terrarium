# Product sequencing — owner direction, 2026-08-02

*Recorded verbatim in substance from the owner during the Step 4 close.
Governs DN-3 (web experience) scoping and release order. Engine-side
consequences noted per mode; none require engine changes today.*

## The three modes, in ship order

**1. Single-user — first, and multi-purpose.** Important for (a) testing
(the owner is the first cohort, D-K4-5), (b) demos, and (c) potentially a
standalone product in its own right. Same engine at n=1; the tutorial is
solo by construction. DN-3 builds this surface first.

**2. Synchronized real-time cohort (the "MMO" route) — a strong candidate,
fun-first.** Everyone starts on a common date and the world rolls forward
one world-day at a time over ~a month of wall-clock time. Engine note:
this is EXACTLY wp4-06's reveal machinery — `temporal_delivery.reveal`
with `cadence_days` and the t0-sealed tape; a cohort is N players on one
sealed world with a shared reveal pointer. Parallel-solitaire rules hold
(independent institutions, identical world/seed, comparative scoring);
market impact between players remains a non-goal.

**3. Facilitated multiplayer (wargame product) — ships LAST**, once
everything else is tested. Requires real-life support (facilitation,
onboarding, session operation) — a service component, not just software.
The wp4-07 wargame harness is its engine substrate.

## Standing constraints that travel with all three

- No client-facing actor claims until the WP4.9 human-cohort study
  completes (the study's first cohort is mode 1's owner testing).
- Tier-2 authoring ships only at the frozen >=95% first-pass bar.
- Identical worlds/seeds for any comparison (sealed rule); leaderboards
  scoped by (world_id, seed, decision_alpha_version).

---

*Not investment advice.*
