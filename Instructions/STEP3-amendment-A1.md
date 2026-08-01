# STEP3-TRANSLATION-PLAN — Amendment A1
## Deltas from the liquidity-spine session · July 2026

*Amends STEP3-TRANSLATION-PLAN.md (v1.0). Does not restate it. Each delta names the section it changes and the document that carries the detail.*

---

## Why this amendment exists

WP3.9 (liquidity spine v0.2) and WP3.10 (linkage estimation) moved a substantial part of Step 3's cashflow content into Phase A, changed its calibration source, and imported empirical findings that alter WP3.4's design. Left unrecorded, Step 3 would be executed against a plan that no longer describes the build.

---

## Delta 1 — WP3.4's perimeter shrinks; its calibration splits

**Was:** WP3.4 owned the entire market-sensitive TA tier, calibrated on ALB-A/ALB-B.

**Now:** WP3.9 v0.2 (Phase A) owns cohort stack, per-sleeve commitment decisions, market-linked `f_call`/`f_dist`, coverage metrics, spending, waterfall, forced sales. WP3.4 retains what WP3.9 §9 lists as institutional: **your** vintage stack as the starting position, recycling/recallables, subscription-line deferral, extension behaviour, fee waterfall with carry mechanics, income-vs-capital distribution split, secondary pricing as a function of liquidity state.

**Calibration split (the substantive change):** the public engine calibrates on public sources per WP3.10 §5 (`linkage_version = public-0.1`); ALB-A/ALB-B calibration becomes the institutional recalibration (`panel-1.0`), client-resident under Path A governance. WP3.4's data-dependency section should now cite WP3.10 §7 as the interface. **This resolves H2 for M4 by construction** — the third-time-flagged licence question no longer sits on the public launch's critical path.

## Delta 2 — WP3.1 partially pulls forward

The closed-end cohort object and its property tests (unfunded never negative, PIC ≤ commitment, recallable balance bounded) are needed by WP3.9 in Phase A. WP3.1 in Step 3 extends the same objects — evergreen vehicles, institution state — rather than implementing them. Same subset discipline as everywhere else: extend, never re-implement.

## Delta 3 — WP3.4 design changes from the Robinson–Sensoy findings

Three findings from WP3.10 §4 bind Step 3, not just Phase A:

1. **No crisis-regime override.** Smooth monotone functions of the D2 equity and credit states suffice; the crisis dummy adds nothing once fundamentals are in. Any regime-switch machinery in WP3.4's spec should be deleted, and the "no regime term" acceptance test adopted.
2. **`f_call` is near-flat for buyout in stress; venture calls rise.** The self-funding breakdown is a distribution-side phenomenon. WP3.4's episode narrative ("pacing stress") remains correct but its mechanism attribution should be corrected.
3. **Age dominates macro by an order of magnitude** — the vintage stack carries the structure; the linkage is a tilt. This belongs in the model card before a reviewer computes the R² themselves.

## Delta 4 — G3 definition-of-done, two edits

**DoD item 2 (2022 end-to-end reproduction):** unchanged in substance, but the chain now runs through objects that shipped in Phase A. The G3 test is therefore a *recalibration* test — does the panel-calibrated engine reproduce the episode better than the public-calibrated one — not a first-light test. State it that way, or G3 quietly re-certifies what Phase A already demonstrated.

**DoD item 3 (tier-1 beats tier-0):** the comparison must specify which `linkage_version` is under test. Public-0.1 beating the transparent benchmark and panel-1.0 beating it are different claims with different audiences; the evidence pack should carry both.

## Delta 5 — the twin's commitment policy lands in D9's ledger

The hold-course twin now follows the t=0 pacing plan mechanically (WP3.9 §5.1). This extends the decision-alpha definition and was recorded against D9 in the WP3.9 changelog. Step 3's twin (WP3.6/3.7 territory) inherits it; the institutional twin's counterfactual is the client's *own* stated pacing plan, which is a sharper and more confronting comparison than the generic one — worth naming in the institutional demo script.

## Delta 6 — a gate Step 3 didn't have

The sleeve-level tail battery (DN-5 §7, option 1) is pre-registered before WP3.2 estimation begins, on G2 terms, with the W11 reviewer attached. It has no gate letter because WP3.2 runs ahead of Step 3's formal gate — which is exactly why it must be scheduled explicitly. Add it to Step 3's gate table as **G3-pre: sleeve-tail pre-registration**, date-stamped before estimation.

---

## Housekeeping

- Add Robinson & Sensoy (2016) to the literature-to-build map against D7, alongside Takahashi–Alexander; add to Zotero as Tier-1.
- Register `linkage_version` in WorldSpec bindings next to `sleeve_mapping_version`.
- The R5/SM-13 FX judgment call from 2R remains open and is unaffected by this amendment — but note it is now flagged in two documents and should be taken at the 2R session, not discovered a third time.
- Capture the recallable-distribution field in the §7 Albourne interface now even though modelling is deferred (WP3.10 §7.3) — it is not recoverable later.

---

*Not investment advice.*
