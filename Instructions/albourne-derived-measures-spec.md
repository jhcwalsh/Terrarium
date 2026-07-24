# Albourne Derived-Measures Request — Cashflow Layer Specification v1.0

*Companion to the Data Requirements Register v1.1. Purpose: fund-level cashflow data is not immediately available; this specifies the derived measures that substitute for it. The design principle: everything the cashflow layer needs can be expressed as rates, profiles, and dispersions — fund identities are never required. Requested per private-market strategy (buyout, growth, VC, secondaries, direct lending, mezz/opportunistic credit, distressed, value-add/opportunistic RE, infrastructure), quarterly, longest available history.*

---

## A. Lifecycle profiles (by fund age, years 1–15)

For each strategy, the age-indexed curves that parameterize and bound the Takahashi–Alexander tier:

1. **Call rate on unfunded** — contributions in year *t* ÷ beginning unfunded commitment — mean and p25/p75 across funds.
2. **Distribution rate on NAV** — distributions in year *t* ÷ beginning NAV — mean and p25/p75. (This *is* the empirical "bow.")
3. **Unfunded commitment decay** — unfunded ÷ original commitment by age.
4. **NAV as % of commitment** by age (mean, p25/p75) — peak NAV and its timing drive pacing formulas.
5. **Cumulative net cashflow to LP** (DPI − PIC equivalents) by age — median, p10/p25/p75/p90 — the J-curve family, including **time-to-breakeven distribution**.
6. **Cumulative DPI by age** (median + quartiles).

*Unlocks: D7 baseline TA parameterization per strategy; stochastic TA (dispersion bands replace Buchner-style fund-level estimation); pacing simulator curves; peer-quartile artifacts.*

## B. Calendar time series (quarterly, per strategy, longest history)

The market-linkage panel — the single most important request:

7. **Aggregate quarterly call rate** — total calls ÷ beginning aggregate unfunded.
8. **Aggregate quarterly distribution rate** — total distributions ÷ beginning aggregate NAV.
9. **Aggregate net cashflow yield** — (distributions − calls) ÷ beginning NAV.
10. **Aggregate NAV growth decomposition** where available: return component vs net-flow component.

*Unlocks: the D7 regressions linking call/distribution rates to lagged public-market states (equity path, drawdown state, HY spreads, exit-market indicators); the Gate G1 2022-episode reproduction test (distribution drought + call behavior); regime-conditional cashflow behavior.*

## C. Age × calendar matrices (the full cross; the priority-2 "gold" request)

11. **Call rate by (fund age, calendar quarter)** and **distribution rate by (fund age, calendar quarter)** — the Lexis-style panels — with **fund count per cell** for weighting and reliability.

*Unlocks: the Phase-3 neural cashflow tier without any fund-level data (the age×calendar rate surface is exactly the training target a macro-conditioned sequence model needs); separates lifecycle effects from market effects cleanly rather than by assumption; enables HBS-style historical simulation at the rate level.*

## D. Vintage-year summaries (per strategy, per vintage)

12. **TVPI / DPI / IRR quartiles** at latest observation and at standardized ages (year 5, 8, 10, 12).
13. **Vintage dispersion** (interquartile ranges) and **vintage fund counts**.

*Unlocks: vintage-risk and selection-dispersion in the pacing simulator; calibration of the "fund picking" noise term; peer-ranking and manager-letter artifacts grounded in realistic dispersion.*

## E. Episode cuts (flagged extracts of B)

14. Quarterly call and distribution rates through **2008Q3–2010Q4**, **2020Q1–2020Q4**, **2022Q1–2023Q4**, per strategy — with any universe-composition notes specific to those windows.

*Unlocks: pre-registered episode validation (D6/G1); stress multipliers for the exit-market state in D7.*

## F. Hedge funds (lighter ask; P2)

15. Strategy-level **asset-weighted net flows** (subscriptions − redemptions ÷ AUM), monthly or quarterly, if derivable.
16. **Incidence of gates/suspensions/side-pockets** by strategy in stress windows (even as counts or shares).

*Unlocks: liquidity realism for HF sleeves in the institutional twin; wire/artifact events (gating) grounded in base rates rather than invention.*

## G. Required metadata (per delivered series)

Definitions (are recallable distributions netted? fees in calls? gross vs net of carry), currency and FX treatment, weighting scheme (equal vs size), universe construction, survivorship and backfill policy, minimum fund counts, and revision policy. *These are Gate G1 evidence, not nice-to-haves.*

---

## Minimum viable subset (if the full request must be staged)

**B (items 7–9) + A means-only (items 1–2, 5-median)** is sufficient to build and validate the market-sensitive TA tier and pass the 2022 episode test — request these first. **C** is the highest-value second tranche (it substitutes for fund-level data in the neural tier). **D–E** complete the research program; **F** is opportunistic.

## Traceability

| Request | Feeds | Decision/Gate |
|---|---|---|
| A | TA parameters, stochastic bands, pacing curves | D7 |
| B | Market-linkage regressions, episode test | D7, D6, G1 |
| C | Neural cashflow tier, historical simulation | D7 (Phase 3), G2-adjacent |
| D | Vintage/selection dispersion, artifacts | D8-adjacent, artifact layer |
| E | Stress multipliers, pre-registered validation | D6, G1 |
| F | Twin liquidity realism, artifact base rates | WS-D/WS-F |
| G | Methodology documentation | G1 evidence pack |
