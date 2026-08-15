# Block-length coherence study — spec §10.1, generator-only

*2026-08-15. The owner's input for declaring the stress-segment block
length. **This study deliberately reports no depth, drawdown, or portfolio
statistic** — the chooser sees the coherence cost only, so the choice
cannot become a severity target in disguise (rule 1). Configuration: sealed
panel (813 rows, vintage 2026-08-10.1), stress_1990's declared shape
(35/10/35, no recovery), 1000 paths × 120 months, seed 199001, only
`mean_block_months` varied, uniformly across segments.*

## The numbers

| mean block (months) | ac1 generated | ac1 panel | joins per path | max level jump | distinct entry rows |
|---|---|---|---|---|---|
| 18 (declared today) | 0.0593 | 0.0611 | 6.1 | 1.494 | 284 |
| 12 | 0.0592 | 0.0611 | 9.2 | 1.494 | 284 |
| 9 | 0.0526 | 0.0611 | 12.3 | 1.494 | 284 |
| **6 (the sealed benchmark's own mean)** | 0.0544 | 0.0611 | 18.3 | 1.494 | 284 |
| 4 | 0.0503 | 0.0611 | 27.7 | 1.494 | 284 |

## The two readings, both stated

**The measured coherence cost of shorter blocks is small.** Lag-1
autocorrelation stays within 0.011 of the panel's own even at 4-month
blocks — far inside the acceptance test's 0.35 bound — because monthly
equity returns are nearly serially uncorrelated to begin with, and the
coherence that matters most lives in the LEVEL factors, which the join
tolerance protects identically at every arm: the largest level jump is
1.494 against the declared 1.5 at 6 joins per path and at 28. The entry
pool is fully spanned at every arm (284 distinct rows = the worst-35%
pool's entire size), so shorter blocks add no thin-material repetition.

**The unmeasured cost is textural, and the owner should weigh it.** Rule 2's
claim — "history writes the rest" — dilutes as blocks shorten: an 18-month
block carries a real episode's own aftermath; a 4-month block carries a
fragment, and the decade's persistence comes instead from the re-entry rule
chaining severe entries. The output remains real months, level-disciplined
joins, and a declared rule — but the balance shifts from *inherited*
autocorrelation toward *constructed* persistence. The statistics above say
this shift is invisible to the declared coherence measures; the sentence in
the methodology note ("blocks in stress segments run long, because every
join is a discontinuity") would need revising to match whatever is chosen.

## One observation that is not a recommendation

**6 months is the sealed benchmark's own mean block length**
(`bootstrap_v1`, `MEAN_BLOCK_MONTHS = 6`, inside the pre-registration
seal). Declaring 6 for stress segments would use the panel's own validated
variety setting rather than inventing a new number — a precedent argument
available without reference to any outcome.

## What happens after the owner declares

One commit re-declares the scenario with the chosen block length (rule +
precedent, pre-registered); the institution is measured once, after. Depth
was not consulted in producing this study and must not be consulted in
choosing from it.
