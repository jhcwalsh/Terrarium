# Narration Production Plan
## Sizing and owning the editorial work behind DN-9 · v0.1 · August 2026 · W4

*Answers item 4 of DN-9 Appendix F. Everything in DN-9 is buildable; the likeliest failure mode is that a large body of editorial work has been specified in detail and assigned to nobody. This document exists to make that impossible to do accidentally.*

---

## 1. The finding first

**This is roughly 100 hours of skilled writing if done conventionally, and roughly 40 if bootstrapped correctly.** The difference is not effort, it is method — and the method that halves it is available precisely because these are *build-time* templates rather than play-time generation.

The person who can do this work is unusual: they must write well and understand markets. That combination is the scarce input, not the hours.

---

## 2. Inventory

| # | Asset | Unit | Volume | Notes |
|---|---|---|---|---|
| 1 | **Editorial style guide** | document | 1 | Register, tense, headline conventions, banned constructions (N-4). **Blocks everything else** |
| 2 | Tier-1 headline/standfirst/body variants | strings | ~790 | 22 event classes × ~3 severity bands × 12 variants |
| 3 | FOMC statement clause bank | clauses | ~120 | Growth, inflation, balance-of-risks, guidance, per stance |
| 4 | Balance-of-risks sentence bank | sentences | ~30 | Tracked as a series (D.13) — small bank, high visibility |
| 5 | Dissent and presser lines | strings | ~60 | Hawkish/dovish × severity |
| 6 | Verdict chip copy | strings | ~24 | Trivial, but must be exact |
| 7 | Layout state definitions | specs | 4 | Design, not copy (§5.2) |
| 8 | Board minute and question templates | strings | ~150 | 2 personas × mood × consistency flag |
| 9 | Bible archetype patterns | patterns | ~40 | Institutions, committee members, columnists |
| 10 | Columnist voice cards | cards | 5 | Prior, register, characteristic error |
| 11 | Derived-observable register entries | entries | 3 | Unemployment, payrolls, CPI (§3.4) |
| 12 | Curated-world editorial checklist | document | 1 | Gates the Verified shelf |
| 13 | **15–20 curated worlds** | worlds | 15–20 | Scenario briefs + review, not writing |

**Assets 1, 3, 4, 10 and 12 are irreducibly hand-written.** Assets 2, 5 and 8 — the ~1,000-string bulk — are not.

---

## 3. The method that halves it

**Write a golden set by hand; bootstrap the banks from it; review everything.**

```
1. Style guide + banned constructions          hand      ~15h
2. Golden set: ~150 strings across every
   class, severity and voice                   hand      ~20h
3. Bank expansion to ~1,000 strings, generated
   against the golden set                      machine   ~£20
4. Human review, cull and rewrite ~30%         hand      ~25h
5. FOMC clause bank, balance-of-risks,
   columnist cards                             hand      ~18h
6. Curated-world briefs and review             hand      ~20h
                                                        ~98h → ~78h
```

This is legitimate where play-time generation would not be, for a specific reason worth stating: **these are Tier-1 artifacts, frozen at build, deterministic on replay, and reviewed by a human before they ship.** Machine assistance in *authoring a template* is a writing tool. Machine generation *at play time* is the thing §7 forbids. The distinction is the review gate, and it must not blur.

⚑ *The golden set is the quality control for the entire corpus. Under-invest there and 1,000 mediocre strings follow. It should be written by the strongest available writer, and it should be the last thing rushed.*

---

## 4. Sequence and dependencies

| Order | Asset | Blocks |
|---|---|---|
| 1 | Style guide (1) | Everything |
| 2 | Golden set (2 partial) | Bank expansion; sets the voice |
| 3 | FOMC bank (3, 4, 5) | The M4 showpiece — statement diff |
| 4 | Bank expansion + review (2, 8) | Slate rendering |
| 5 | Bible archetypes, columnists (9, 10) | Tier-2 and world compilation |
| 6 | Curated worlds (13) | M4 launch content |
| 7 | Checklist (12) | Verified shelf, M5 |

**The FOMC bank should come third, ahead of the bulk.** It is the highest-visibility artifact in the product, it is the thing a practitioner judges the whole simulator by in ninety seconds, and it is small enough to finish. Finishing it early also stress-tests the style guide against the hardest case before a thousand strings are written to it.

---

## 5. What lands at M4 versus later

| M4 — required | M5 — deferred |
|---|---|
| Style guide, golden set, full Tier-1 banks | Columnist voice cards and their copy |
| FOMC clause bank, balance-of-risks, dissents | Presser Q&A (Tier-2) |
| Verdict chip copy, layout states | Board minutes and questions |
| Derived-observable register | Bible archetypes for user compilation |
| 15–20 curated worlds | Curated-world checklist |

Board copy (asset 8) follows the Board itself and is not M4 (DN-9 E.8).

---

## 6. Ownership ⚑ — the actual point of this document

| Asset | Owner | Status |
|---|---|---|
| Style guide, golden set, FOMC bank | **⚑ UNASSIGNED** | The scarce role. Writer who understands markets |
| Bank expansion and review | ⚑ UNASSIGNED | Can be the same person; can be a second reviewer |
| Curated-world briefs | You | Domain judgement, not writing |
| Layout states | Design | With the front-page compositor, WP4.2e |
| Derived-observable register | Quant | Sits in the model parameter register |
| Editorial checklist | Product | M5 |

**Two roles are unassigned and one of them is on the M4 critical path.** Nothing else in this plan matters until that is resolved, and it is a hiring or contracting decision rather than an engineering one — which is exactly why it will not surface in a build review.

⚑ *Recommend resolving before the next milestone review. A contractor is viable for the bulk; the style guide and golden set are not safely contractable to someone who does not know the domain, because the failure is invisible until a practitioner reads it.*

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| **Voice drifts across 1,000 strings** | Golden set as the reference; review pass reads for voice, not correctness |
| **Rare-regime banks are thin** (F item 8) | STAG and CRI get *deliberate over-allocation* in the golden set — a world spends years there and history gives few models |
| Bulk expansion reads generated | 30% cull budgeted, not aspirational. If the cull rate comes in under 20%, the reviewer is not reviewing |
| Style guide written after the copy | Sequence above; it is asset 1 for a reason |
| Curated worlds become a writing project | They are scenario briefs and review, not prose. Hold that line |

---

*Companion to DN-9 v1.0. Not investment advice.*
