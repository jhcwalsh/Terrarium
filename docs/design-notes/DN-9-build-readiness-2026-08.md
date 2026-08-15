# DN-9 · Build Readiness
## What can go to code today, what cannot, and what closes the gap · v0.1 · August 2026

*Assessment against DN-9 v1.0. A design note and a build spec are different documents; this records how far apart they are, package by package.*

---

## 1. Verdict

**Two items are ready. Everything else is blocked on one missing definition, unassigned content, or an undecided parameter.**

The single largest gap is not conceptual. **`severity` appears throughout DN-9 — it drives slot contests, layout state, headline size and whether a SPECIAL edition fires — and is defined nowhere.** Every event threshold is a placeholder: `k·σ̂`, "beyond band", "crosses tier", "> threshold". WP4.2a cannot be written against that.

---

## 2. Package status

| WP | Package | Status | What is missing |
|---|---|---|---|
| — | **Rationale field** (`TASK-wp4-rationale-field.md`) | ✅ **Ready** | Nothing. Ship it |
| WP4.2e | Front-page compositor, layout states, share card | ✅ **Ready enough** | Figs 2, 3, 5 are effectively design specs. Layout-state *triggers* need §3 |
| WP4.2a | Event detection + event stream schema | ⛔ **Blocked** | **Severity function; all 22 class thresholds**; RunRecord contract shape |
| WP4.2b | Template renderer + variant banks | 🔶 Mechanism ready, content absent | Renderer buildable now. Banks are the production plan, owner unassigned |
| WP4.2c | FOMC module | 🔶 Partial | Statement/diff/dissent logic specified. Blocked on N-p (smoothed anchor ρ) and N-q ⛔ |
| WP4.2d | Release calendar + consensus generator | 🔶 Partial | Calendar trivial. Consensus dispersion undecided (N-e) |
| WP4.2f | Bible builder + plant-parity harness | ⛔ Blocked | Thread-class taxonomy undefined (N-a); parity tolerance unset |
| WP4.2g | Leak gate N-1…N-4 | 🔶 Split | N-1 and N-4 buildable today. **N-2 unspecified and must be sealed before Tier-2 exists** |
| WP4.2h | Rationale agent | ⛔ Blocked | Filter spec is Quant's (N-s); stickiness uncalibrated (N-t); bias register unratified (N-x) |
| WP4.9 | The Board | ⛔ Blocked | Whole mechanic. Scoring question sits at DN-5, not here (N-ag) |

---

## 3. The three gaps that actually block

### 3.1 Severity and thresholds ⛔ — the critical path

One focused session with Quant produces a parameter table: a severity function (recommend a normalised surprise/move magnitude mapped to 0–3 with class-specific scaling), plus 22 sets of trigger thresholds. **This single artifact unblocks WP4.2a, WP4.2b, WP4.2e's layout triggers and WP4.2d.**

It is also not a free choice. Severity determines how often a decade feels dramatic; set it loosely and every quarter is a crisis, tightly and nothing ever happens. It should be calibrated so that a *median* decade produces a target count of severity-3 events, checked against the ensemble — which makes it a Quant task, not an editorial one.

### 3.2 The unassigned editorial role ⚑

Per the production plan. The renderer can be built against placeholder strings, so this does not block engineering immediately — but it blocks M4, and it has a lead time that engineering does not.

### 3.3 The interface contract

DN-9 stamps `narration_version`, `template_pack_version`, `bible_id`, `event_stream_hash`, `artifact_set_hash` — but does not specify their shape against the WorldSpec/RunRecord contract that Step 2R owns. Narration must enter the versioned contract properly rather than being appended to it.

**One untested assertion:** §7 claims the bundle stays inside the DN-3 sub-megabyte target because templated text compresses well. Plausible, unchecked, and cheap to check. Do it before the bundle format freezes.

---

## 4. Two process steps that must precede code

**4.1 The N-series is not in the decision register.** Thirty-seven decisions were raised in this note and none is keyed into the D-series. Building against decisions that live only in a design note is exactly the drift the register exists to prevent.

**4.2 Four new tests must be pre-registered before they are built, not after.** N-2 (leak probe), rationale strain (N-v), plant parity (N-3), and the policy step/reversal diagnostic (N-q) are all tests with criteria. The project's standing discipline is that criteria are sealed before running. A test built first and thresholded afterwards is a description, not a test — which is the precise defect P2 §8 catalogues as "a sealed protocol pinning a procedure but no criterion."

**N-2 has a second condition**: it cannot be scored by whoever writes the template pack (N-l). That has staffing implications and should be settled while the role is still being filled.

---

## 5. The argument for a reader before a build ⚑

DN-9 went from nothing to twenty thousand words in a single session, written by one party, with no independent read.

**Three defects were caught during that session, all self-caught:** the Y6/Y8 forced-sale inconsistency, the policy anchor's missing inertia term, and the forty-versus-eighty meeting count. A fourth — undefined severity — surfaced only when the document was checked for build-readiness rather than read.

Four found by looking. The base rate argues that more remain, and it is the same pattern P2 §8 already names: *seven governance defects of one class found in three days, the last by the person cataloguing the other six.*

**Recommendation: one independent read of DN-9 before WP4.2a opens.** Half a day. The cheapest defect is the one found before it is code.

---

## 6. Recommended order

| | Action | Owner | Unblocks |
|---|---|---|---|
| 1 | Issue `TASK-wp4-rationale-field` | Eng | Board, DN-6 — and it is a migration if late |
| 2 | Severity function + 22 threshold sets | Quant | WP4.2a, b, d, e |
| 3 | Resolve the editorial role | You | M4 content, lead time |
| 4 | N-series into the decision register | You | Governance integrity |
| 5 | Independent read of DN-9 | Reviewer | Everything downstream |
| 6 | Seal N-2 and the strain criterion | Quant + Governance | Tier-2 build |

**Items 1 and 3 can start today and are independent of everything else.** Item 2 is the engineering critical path.

---

*Companion to DN-9 v1.0 and the narration production plan. Not investment advice.*
