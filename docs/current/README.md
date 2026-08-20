# The documentation register

*What governs, what is a record, and where each document lives — as of
2026-08-15. This is the index; it holds no content of its own.*

**Start here:** `docs/current/METHOD.md` — what has been built and by what
method, as it stands today.

---

## How to read a status

| status | meaning |
|---|---|
| **GOVERNING** | Current and authoritative for its subject. |
| **CURRENT IN KIND** | Still the right document for its subject, but written against an older state of the repository. Carries an `AS OF` banner naming the specific drift. |
| **SUPERSEDED** | Its framing has been replaced. Kept, still served, still citable — a record of how things were understood, not current guidance. |
| **RECORD** | A frozen account of something that happened: gate evidence, a campaign verdict, a completed task. Never edited. |
| **GENERATED** | Written by a script from committed artifacts. **Do not edit by hand** — a test asserts reproducibility. |
| **DRAFT** | A write-up in progress, committed so it is versioned and reviewable. **Governs nothing, and is not citable outside this repository** until the owner has edited and released it. |

Every document that has moved or changed status carries a banner at the top of
the file. The banner, not this table, is what a reader arriving from a link or
from the tools hub will see; this register exists so the whole estate can be
read at once.

## `docs/current/` — the governing set

| Document | Status | What it is |
|---|---|---|
| `METHOD.md` | GOVERNING | What has been built and by what method, 2026-08-15. The entry point. |
| `stress-scenario-methodology.md` | GOVERNING | The stress method in full: the rules, the three measured scenarios, and the limits. Matches spec v0.2. |
| `tail-register.md` | GOVERNING | Every severity-producing mechanism with its falsifier (TR-1…TR-7). Admission rule: a mechanism that cannot name its own falsifier does not enter the engine. |
| `private-markets-and-inflation.md` | CURRENT IN KIND (AS OF 2026-08-18) | Written against the PRE-ER-14 engine; §2/§4 describe return equations `er14-02`/`er14-03`/`er14-05` have since changed. **ER-14 is now CLOSED** (`docs/engine-realism-register.md`'s close-out governs the post-fix account); this document is the supporting detail for the pre-fix finding, kept as the record, with a §4.5 post-fix summary added and a banner naming the drift. **Served by the hub** (`private-markets-inflation`), with a committed `.pdf` mirror rebuilt by `scripts/build_doc_pdf.py` — **not yet re-rendered against this edit** (a headless-Chrome step, not run in this WP; the served markdown and the register are current, the PDF mirror is one edit behind). |
| `alternate-histories-audited.md` | GOVERNING | The narrative account — where the work stands and what it has taught us. Last updated 2026-08-14. |
| `DROP-MANIFEST.md` | GOVERNING | The DN-9 narration drop: what goes where, and what is knowingly carried. Describes work not yet started. |
| `narration-dn9.zip` | — | The DN-9 drop itself. **Untracked** (see "Untracked files" below). |

## `docs/papers/` — drafts, not governing

Added 2026-08-19. Write-ups of the work, committed as **DRAFT** so they are
versioned and reviewable. **None of them governs anything**: where a paper and a
register disagree, the register wins, and nothing here should be quoted outside
the repository until the owner has edited and released it. Each file carries its
own DRAFT banner and points at its companions.

| Document | Status | What it is |
|---|---|---|
| `2026-08-19-economic-realism-engineering-quantity-DRAFT.md` | DRAFT | The academic write-up: economic realism as a sealed, falsifiable exam over generated decades, and the four campaigns judged against it. The successor in framing to `docs/P1-specified-world-models-preprint.md`, and the first answer to the "no current academic write-up" gap under **Outstanding** below. |
| `2026-08-19-twenty-decades-plain-DRAFT.md` | DRAFT | The plain-English companion: what was built, how it was tested, and what it got wrong. |
| `2026-08-19-decade-you-live-through-users-guide-DRAFT.md` | DRAFT | The player-facing guide: what a generated decade is, what the player controls, and what the engine refuses to do. |

## `docs/historic/` — sectioned off

| Document | Status | Why it is here |
|---|---|---|
| `RESULTS-EDITION-SUMMARY.md` | RECORD | A completed editing pass: which `[[slots]]` in D-05 and P1 were filled on 2026-08-05. Both parents are now SUPERSEDED, so this records a finished job rather than tracking a live one. |
| `CIO Dashboard.zip` | RECORD | Superseded by its own unpacking. DN-8 now lives at `Instructions/DN-8-cio-dashboard-data-contract.md` and the renderer at `docs/cio-dashboard/`. A binary nobody can diff should not remain the authority once unpacked. |
| `narration.zip` | RECORD | The pre-renumber narration drop, superseded by `docs/current/narration-dn9.zip` when DN-8 → DN-9 resolved the collision with the CIO dashboard contract. **Untracked.** |

## Superseded in place — banner added, file not moved

These carry a `SUPERSEDED` or `AS OF` banner but stay at their existing paths,
because **`src/ah/hub.py` serves them to readers from a hard-coded allowlist**.
Moving them would require a code change, and this exercise touches no code. The
banner is the stronger instrument in any case: it travels with the document to
every reader, including one arriving through the hub, which a directory move
would not.

| Document | Status | Note |
|---|---|---|
| `docs/METHODOLOGY.md` | SUPERSEDED | Describes the platform as a *predictive* system on the hierarchical generator, before the prescribe-not-predict turn. |
| `docs/D-05-methodology-note.md` | SUPERSEDED | The practitioner-facing account. **No current replacement exists** — see "Outstanding" below. |
| `docs/P1-specified-world-models-preprint.md` | SUPERSEDED | The working paper. Its §8 empirical results remain the sealed ones and are not withdrawn; the framing around them is what has moved. Its successor in framing is now **a draft**, `docs/papers/2026-08-19-economic-realism-engineering-quantity-DRAFT.md` — pending owner edits, so P1 remains the only *released* academic account. |
| `docs/BUILD-SUMMARY.md` | CURRENT IN KIND (2026-08-05) | Still the most detailed code inventory. Banner lists seven specific drifts. |
| `docs/USER-MANUAL.md` | CURRENT IN KIND (2026-08-05) | Commands and workflow shape still hold; recorded outputs are from an older repository state. |
| `docs/PLAIN-ENGLISH-USER-MANUAL.md` | CURRENT IN KIND (2026-08-07) | One statement in it is actively misleading and the banner corrects it: the generator that ships *is* playable — what stayed out of the product is the neural one. |
| `docs/interpretation-guide.md` | GOVERNING | Did not move: `tests/test_citations.py` pins its path in `LIVING_DOCS`. |
| `docs/engine-realism-register.md` | GOVERNING | Did not move: it is cited from `src/ah/battery/thresholds.yaml`, **which is inside the pre-registration seal**. Moving it would strand a wrong path in a sealed file, fixable only by a reseal event. |
| `docs/notes/desmoothing-coefficient.md` | GOVERNING | Served by the hub. |
| `docs/data/**` | GOVERNING | Source notes, licence registry, campaign and extension reports. Cited by the hub and by connector modules in `src/ah/data/`. |

## Generated reports — no banner, by design

These are written by scripts from committed artifacts and carry their own
"GENERATED … do not edit by hand" header. `tests/test_ablation_report.py`
asserts reproducibility from the stored grid, and the generators write to
hard-coded repo-root paths. **They are outputs, not prose** — neither current nor
historic, and adding a banner would break the reproducibility the header
promises.

`ABLATION.md` (campaign 2) · `CAMPAIGN3-ABLATION.md` (campaign 3) ·
`CAMPAIGN3-PROMOTION.md` · `DESMOOTHING.md` · `climate-fit-report.md` ·
`regime-fit-report.md` · `regime-sensitivity-report.md`

## Gate evidence — permanent record, at the repo root

Never moved, never edited. `G2-EVIDENCE.md` and `ABLATION.md` are additionally
citation-checked by `tests/test_seal_guards.py`'s `GOVERNANCE_DOCS`.

`G0-EVIDENCE.md` (Step 0) · `G1-EVIDENCE.md` (Step 3 — **an honest FAIL**) ·
`G2-EVIDENCE.md` (Step 2) · `CONSOLIDATION-EVIDENCE.md` (Step 2R) ·
`RESEARCH-EVIDENCE.md` (Step 5) · `governance/evidence/G4-EVIDENCE.md` (Step 4)

Each has a `.pdf` mirror alongside it, generated 2026-08-09.

## Unchanged homes

| Tree | What it holds |
|---|---|
| `Instructions/` | **The authoritative plans** — step plans and amendments, the KICKOFF wrappers, the DN design notes (DN-1…DN-8), and the specs and registers they vendor. CLAUDE.md is the map into it. Untouched by this exercise. |
| `governance/` | The decision register, amendment log, retrofit register, model inventory, prompt registry, EU AI Act mapping, `evidence/` and `proposed/`. Untouched. |
| `docs/superpowers/{specs,plans}` | 46 dated design specs and implementation plans, 2026-08-04 → 08-15. **Append-only working history**, left in place: roughly ten `src/` modules cite specific files here as provenance in their docstrings. Still governing: `2026-08-14-cio-dashboard-design.md`, `2026-08-14-stress-scenario-compiler-design.md`, and `2026-08-14-translation-layer-audit.md` (whose F5 is still open). Everything else in the tree is a dated record, not a live contract. |
| `docs/cio-dashboard/` | The vendored DN-8 renderer and `cioView.ts` — the CI authority for the contract, read by `src/ah/cioview.py`. |
| `docs/figures/`, `docs/*.svg` | Figures for the D-05 note, the P1 preprint and METHODOLOGY. They stay with the documents that reference them by relative filename. |
| `README.md`, `CLAUDE.md`, `NEXT-STEPS.md`, `CHANGELOG.md` | Repo root, live. |
| `STEP0-PLAN.md`, `STEP1-DATA-PLAN.md` | Repo root is their canonical home — cited by `README.md`, `src/ah/__init__.py`, `G0-EVIDENCE.md` and CLAUDE.md. The copies in `Instructions/` are byte-identical duplicates. |
| `README-console.md`, `MAPPINGS.md`, `MAPPINGS-v1.1.md` | Repo root, live. `MAPPINGS.md` is read at `_REPO_ROOT` by `tests/test_port_mapping.py`, and is only *partly* superseded: its PM rows are replaced by v1.1, its HF table still describes the live artifact. |

## Known duplications, recorded not resolved

- `STEP0-PLAN.md` and `STEP1-DATA-PLAN.md` exist identically at the repo root
  and in `Instructions/`.
- `docs/albourne-derived-measures-spec.md` and
  `docs/data-requirements-register.md` exist identically in `docs/` and in
  `Instructions/`. `STEP1-DATA-PLAN.md` directs that these two be vendored into
  `docs/`, and a spec cites the `docs/` path, so `docs/` is the copy to keep.
- `ABLATION.md` and `G2-EVIDENCE.md` exist identically at the repo root and
  under `governance/evidence/`.

None of these were collapsed here: deleting either side is a judgment about
which tree owns the document, and `Instructions/` and `governance/` were out of
scope for this pass.

## Citations left pointing at old paths, deliberately

Moving a file leaves every document that named it holding a stale path. Two
rules were applied:

- **Live documents were repointed.** `README-console.md`, `NEXT-STEPS.md`,
  `CLAUDE.md`, and the two `docs/superpowers/specs/` documents still listed as
  governing above (`2026-08-14-stress-scenario-compiler-design.md`,
  `2026-08-14-cio-dashboard-design.md`) now cite the new paths.
- **Dated records were not.** The plans and specs under `docs/superpowers/` that
  are records rather than live contracts still cite `docs/tail-register.md`,
  `docs/alternate-histories-audited.md` and `docs/CIO Dashboard.zip`. Those
  citations were correct on the date the document was written, and the tree is
  append-only. This is the same principle `tests/test_citations.py` states in
  its own docstring: historical documents describe the repo as it was and may
  cite files that legitimately no longer exist. Amendment and changelog rows
  *inside* otherwise-live documents were likewise left alone — a record of what
  an amendment did on a date is not a live citation.

The working reports under `.superpowers/sdd/` also reference the old paths and
were not touched; they are session records.

## Untracked files

`docs/current/narration-dn9.zip` and `docs/historic/narration.zip` are untracked
and were untracked before this pass. They are ~100KB binaries; whether to commit
them is an owner call, not a filing decision. `docs/current/DROP-MANIFEST.md`
**was** untracked and is now tracked, because it is the readable record of what
those binaries contain.

Local gate logs (`gate-*.log`) stay at the repo root. `.gitignore:214` is
`/gate*.log` — **root-anchored deliberately** — so filing them under `docs/`
would make them tracked and commit local run logs into the repository. They are
scratch artifacts, not documentation.

## Outstanding

Recorded here so the gaps are visible rather than discovered later.

1. **No current practitioner-facing account.** `D-05` is SUPERSEDED in framing
   and has no replacement at its depth. A rewrite is real work and is not
   scheduled.
2. **No *released* academic write-up.** The `P1` preprint predates both the
   third campaign's reversal and the prescribe-not-predict turn. Its sealed
   results stand; its argument needed re-making, and a re-making now exists as
   a DRAFT (`docs/papers/2026-08-19-economic-realism-engineering-quantity-DRAFT.md`,
   2026-08-19). The gap stays open until the owner edits and releases it.
3. **`docs/tier1-synthesis-and-decisions.md` is still missing** — named by Step
   2's vendoring list, allowlisted in `tests/test_citations.py`. The citation is
   the record of the gap.
4. **`BUILD-SUMMARY.md` and `USER-MANUAL.md` have not been re-verified** against
   the running repository since 2026-08-05. Their banners name the drift that is
   known; there may be more.
