# STEP4-EXPERIENCE-PLAN — Amendment A1
## Deltas from the liquidity-spine session · July 2026

*Amends the Step 4 plan. Does not restate it. Carries the experience-layer consequences of WP3.9 v0.2 (commitment as a decision variable, vintage cohorts, market-linked cashflows) and Amendment A1 to the master plan (inspection points).*

---

## Delta 1 — A second decision surface: the commitment window

Live mode currently exposes one decision type: allocation. WP3.9 v0.2 adds a second: **per-sleeve annual commitments**. This is a new UI surface, not a variant of the existing one, and it is the more consequential of the two — it is where the product's central lesson now lives.

Requirements:

- **Annual cadence, at the decision window.** The player sets next year's commitment per private sleeve. Constraints from WP3.9 §5 (non-negative, capped well past comfortable).
- **The information shown at the moment of decision matters more than the control.** The window must display: current coverage on both bases, the vintage stack by age, trailing distributions, and the t=0 pacing plan the twin is following. The decision is only meaningful against that context, and the context is the teaching.
- **Default = the pacing plan.** Doing nothing at the window is a decision to stay on plan — identical to the twin. This must be explicit in the UI ("holding to plan"), because the scoring depends on the distinction between an active hold and an unvisited screen.
- **Tutorial world extension.** The scripted tutorial gains one commitment decision with an unmissable consequence. This lengthens the tutorial; the trade-off is accepted because a player who never touches the commitment surface has not met the product.

## Delta 2 — The wire and Tier-1 templates gain cashflow events

WP4.2's template library extends with event classes the engine now emits: **capital call arrived**, **distribution received**, **coverage band crossed**, **forced sale executed** (with cause and sleeves sold), **secondary sale at discount**. The forced-sale template is the loudest artifact in the product and should read like the distress event it is.

One editorial rule: cashflow events report the **cash account**, not the reported plane. The wire already distinguishes reported and true marks; the cash account is the third voice, and per WP3.9 §7 it is the honest one. The style guide should say so.

## Delta 3 — The outcome card and interpretation guide

- **Forced-sale count now has a mechanism.** The sharing-spec inconsistency is closed; no card or leaderboard change needed, only the note that the metric is live from Phase A.
- **Coverage on both bases joins the interpretation guide** as the toggle's second act: the same divergence, arriving in the number an IC actually watches.
- Consider (not commit): coverage-at-worst as a secondary card metric. Decision deferred to after I5 — the card is already dense.

## Delta 4 — Post-game annotation: the two new lessons

The chess-style review screen gains the two annotations the cohort stack makes possible:

1. **The flinch cost.** "Year 4: cut commitments 60%. Consequence: distribution shortfall years 8–10, −x.x points vs plan." This is the product's sharpest single teaching and the direct visualisation of WP3.9's flinch test.
2. **The arithmetic warning.** Where a player reacted to coverage deterioration that was purely denominator-driven, the annotation says so: "Coverage rose because NAV fell, not because obligations grew. The de-risking that followed cost −x.x points." Delivered without smugness; the style guide owns the tone.

Both annotations must be computable from the RunRecord alone — no new state.

## Delta 5 — Help agent scope extension (M5)

Three question families join the grounded corpus: commitment mechanics ("what does unfunded mean?"), coverage ("why did my coverage rise when I did nothing?"), and forced sales ("why was I forced to sell equities?"). All answerable from the glossary, the interpretation guide, and revealed state; the never-advice rule is untouched — the agent explains why coverage rose, it never suggests what commitment to set.

## Delta 6 — Inspection points I4–I6 land in this step's schedule

I4 (toggle inspection) and I6 (liquidity inspection) run on WP3.3/WP3.9 outputs before the experience slice consumes them; I5 (first-run observation) gates M4. All three are already specified in MPP Amendment A1 and WP3.9 §12; this delta only places them in Step 4's sequence so they cannot be skipped by a schedule that doesn't know about them.

---

*Not investment advice.*
