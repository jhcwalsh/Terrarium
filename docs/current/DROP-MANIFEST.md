# DN-9 Drop Manifest
## What goes where, and what is knowingly carried · August 2026

> **Renumbered DN-8 → DN-9, 2026-08-14, on the owner's instruction.** "DN-8"
> was already taken in the Terrarium repo by the CIO dashboard data contract
> (`Instructions/DN-8-cio-dashboard-data-contract.md`, vendored and cited by a
> merged plan), so this drop's note is **DN-9** throughout. Renaming is
> text-and-filenames only: 54 occurrences of the note's own number plus the
> eight figures; every reference to DN-1/2/3/5/6/7, every section number and
> the whole N-series are unchanged, verified by count. Files listed below use
> the new names.
>
> **Two build-readiness items were also checked against the live repo and
> should be read before issuing the tasks.** (1) §4.1's FOMC set-piece assumes
> L1's policy anchor with `ε_t` as the surprise — that anchor exists in the
> hierarchical generator and as an evaluation metric, but the world that ships
> (`stagflation_1974`) runs `bootstrap-v1` after SHIP-BENCHMARK, and a block
> bootstrap emits no `ε_t`. (2) §5 of this manifest says the CAPITAL slot is
> out of reach pending Step 3 — Step 3 is wired and live: calls, distributions,
> unfunded, forced sales, spending and expired commitment all reach the player
> today, and `GET /sessions/{sid}/cio` already serves liquidity and
> private-cashflow blocks. All four slots are buildable.

---

## 1. Files

| File | Suggested path | Status |
|---|---|---|
| `DN-9-the-wire-narration-architecture.md` | `docs/design-notes/` | v1.3. Design note |
| `dn9-fig1..8-*.svg` (8 files) | `docs/design-notes/` *(alongside the .md)* | Referenced by relative filename — keep together or the links break |
| `voices-golden-set-v0.md` | `docs/editorial/` | Quality control for the whole corpus |
| `narration-production-plan.md` | `docs/editorial/` | Sizing and ownership |
| `DN-9-build-readiness-2026-08.md` | `docs/design-notes/` | Package-by-package readiness |
| `documentation-register-A3-narration.md` | `docs/` *(with the other register amendments)* | Triages the 35 N-entries. **Read before the build starts** |
| `TASK-wp4.2-narration-workbench.md` | `tasks/` | The prompt |
| `TASK-wp4-rationale-field.md` | `tasks/` | Independent, do first |
| `voices.yaml` | repo root, or `config/` | 40 `UNRESOLVED` values. Keys mirror A3 bucket B exactly |
| `wire_proto.py` | **`spikes/`** | **Not the package path.** Carries a status header saying so |
| `wire_proto.html` | `spikes/` | Sample output |

---

## 2. Order

1. **`TASK-wp4-rationale-field`** — independent of everything, and a migration if it goes late.
2. **`TASK-wp4.2-narration-workbench`** — the main build. Needs a generated world with the §1 required series.
3. Read the `UNRESOLVED.md` it produces. That list is the point.

---

## 3. Known inconsistencies, carried deliberately

Recorded so they are not discovered later and mistaken for drift.

| # | Inconsistency | Resolution |
|---|---|---|
| 1 | **Work-package numbering.** DN-9 §12 lists WP4.2a–h as separate packages; the workbench TASK spans a, b, c, d and part of e in one build | The TASK is the build unit; DN-9 §12 is the logical decomposition. Reconcile in the register, not by re-cutting the task |
| 2 | **`DN-9-build-readiness-2026-08.md` says severity is undefined.** It now has a first draft in the spike | True when written. The draft is unratified, so the readiness verdict stands — but note the spike has a starting point |
| 3 | **Appendix G revised twice.** Original £ figures appear in earlier changelog entries | Changelog is a record, not a claim. G itself is USD and current |
| 4 | **A.8 vs the golden set.** A.8 has Vane doing work now assigned to Calloway | Golden set supersedes. Fix A.8 at the next DN-9 revision rather than now |

---

## 4. Not in the drop

- ~~The N-series is not in the decision register.~~ **Addressed by Amendment A3**, which triages the thirty-five entries into five buckets. Nine need ratifying; the rest are parameters, conventions, referrals or pre-registrations. A3 is in the drop.
- **No independent read has happened.** Four defects were found in this document by looking, three of them self-caught. The base rate argues for more.
- The Board, the peer survey, any LLM backend, all four leak-gate tests as gates.

---

## 5. What the workbench will and will not produce

**Will:** three of four slots on a chosen world (POLICY, DATA, MARKETS), forty slates, a diagnostics report, and — as a free by-product — a policy-path realism audit of the promoted generator (ε distribution, step-size histogram, reversal frequency).

**Will not:** the CAPITAL slot. It needs the portfolio and liquidity layers wired to a world, which is Step 3. The artifact says so rather than stubbing it.

---

*Companion to DN-9 v1.3.*
