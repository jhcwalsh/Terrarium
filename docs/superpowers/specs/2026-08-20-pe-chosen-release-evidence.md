# Chosen-PE release evidence — what the new buyout equation actually does

**Date:** 2026-08-20 · **Branch:** `pe-chosen-01` (Task 3 of the chosen-PE release)
**Script:** `scripts/pe_chosen_release_evidence.py` (deterministic; never opens the
store — specs read from `src/ah/presets/*.json`, the byte source the store builds from)
**Sidecar:** `2026-08-20-pe-chosen-release-evidence.json` (every number below, unrounded)
**Decision this evidences:** D-ER16-1 (`governance/decision-register.md`) — the generated
plane's `pm_buyout` row moved from measured-but-known-wrong coefficients (beta 0.8362,
alpha 8.06%/yr, fitted on an appraisal index whose GFC was never recorded) to CHOSEN
coefficients (beta **1.2**, alpha **3%/yr**), sealed as `sleeve-mappings-v1.3.yaml`.

**How to read the labels.** *Measured* = computed by the script from the shipped
equation on the named seeds. *Derived* = arithmetic on measured numbers or on the
artifact's own declared values. *Before* numbers are quoted from the sealed-era
measurement (`2026-08-19-pe-serenity-finding.md`, worlds 711/712/713 under v1.2);
they were not re-run — the retired worlds still hold them.

**Convention** (the serenity probe's, unchanged): each successor world is run through
`ah.port.adapter.run_gen_path` — the exact call `ah/serve.py` and `ah/bundle.py` make —
at its preset's own `base_seed` plus 200 paths at the platform stride
`base_seed + 7919*k`. Path k=0 IS the live tape a default 1000-path run pins as its
own first path. "Crash window" = each path's worst rolling 12-month equity window.

---

## The headline: before/after for The Gulf Decade (712 → 722)

Same declared scenario, same seed (202608), same months of real history resampled the
same way — only the buyout translation changed.

| | **before** (712, v1.2, measured 2026-08-19) | **after** (722, v1.3, measured) |
|---|---:|---:|
| live-tape decade PE true | +532.15% | **+385.91%** |
| decade PE, median of 200 paths | +257.66% | **+191.64%** |
| decade PE, p05 / p95 | +39.89 / +792.86% | **-13.61 / +779.29%** |
| decade equity, median (unchanged — checksum) | +149.91% | +149.91% |
| paths where PE's decade beats equity's | 169 / 200 | **136 / 200** |
| median PE max drawdown | -31.52% | **-42.20%** |
| median equity max drawdown (unchanged) | -32.11% | -32.11% |
| crash window: median equity inside it | -26.22% | -26.22% |
| crash window: median PE inside it | **-19.00%** | **-32.10%** |
| year 5 (the crash year), live tape: PE vs equity | -30.09% vs -45.54% | **-47.55% vs -45.54%** |
| the alpha term's annual rate (derived from the live row; script checksum) | 8.06%/yr | **3.00%/yr** |

In plain language: before the change, private equity in this stress world fell *less*
than the stock market in the crash window (-19% against -26%) while being paid 8% a
year for showing up; it beat equities on 85% of severe paths. After the change it falls
**harder** than the stock market in the crash window (-32% against -26%, the levered-beta
shape DN-5's own prior always said to expect), its crash year is now slightly *worse*
than equity's (-47.6% vs -45.5%), it can lose money over a severe decade (p05 is now
below zero), and it beats equities on 68% of paths instead of 85% — still most of the
time, which is what a 1.2 beta plus 3%/yr does in a decade where the median equity
path makes +150%.

## Term by term: the live tape's decade, exactly decomposed (world 722, seed 202608)

The five terms are additive in monthly return space; the script rebuilds them
independently and **asserts** the sum is bit-identical (atol 1e-12) to the shipped PE
row before reporting — same method, same seed as the serenity finding, so the columns
compare exactly. All measured.

| term | before: Σ monthly (pp), 712 | after: Σ monthly (pp), 722 | what moved |
|---|---:|---:|---|
| alpha (intercept) | +77.764 (38.9% of sum) | **+29.596** (16.1%) | the chosen 3%/yr |
| beta × equity_mkt | +73.703 | **+105.768** (57.5%) | the chosen 1.2 (×1.435 = 1.2/0.8362, exactly) |
| residual (this seed's luck) | +63.330 | +63.330 | **bit-identical** — σ and the seed stream untouched |
| beta × d_ig (credit) | +6.278 | +6.278 | **bit-identical** — loading untouched |
| inflation channel (C1) | -21.000 | -21.000 | **bit-identical** — block untouched |
| **total (arith sum)** | **+200.074** | **+183.972** | |
| decade, compounded | +532.15% | +385.91% | |

Year 5, the crash year, on the live tape (Σ monthly pp, measured): beta×equity
**-67.620** (was -47.120 — the 1.435 ratio again, derived), alpha **+2.960** (was
+7.776), residual +8.742 and inflation -2.100 and credit -0.474 all unchanged.
Realised year-5 PE: **-47.55%** against equity's -45.54%. Before, the same year
compounded to -30.09%: a -39.4% beta hit cushioned by 8pp of intercept. Now the
beta hit is **-52.4%** compounded alone (measured) and the intercept hands back
3.0pp, not 8.1.

The three unchanged rows are the adoption's own audit: the release claimed to move
exactly two coefficients, and the decomposition shows every other term of the same
seed's tape to the last bit.

## All four successors under the adopted equation (measured, 200 paths each)

| world | live-tape decade PE | median / p05 / p95 | med PE maxDD vs med eq maxDD | PE beats eq | crash window: med eq vs med PE |
|---|---:|---:|---:|---:|---:|
| 721 stress_1974_successor | +322.65% | +274.55 / +4.91 / +964.21% | **-38.07%** vs -29.85% | 146/200 | -20.87% vs **-27.15%** |
| 722 gulf_decade | +385.91% | +191.64 / -13.61 / +779.29% | **-42.20%** vs -32.11% | 136/200 | -26.22% vs **-32.10%** |
| 723 stress_1990_successor | +59.10% | +124.48 / -53.73 / +764.83% | **-46.90%** vs -36.16% | 134/200 | -28.35% vs **-34.65%** |
| 724 stagflation_1974 | +310.33% | +296.73 / +54.48 / +1090.89% | **-33.11%** vs -22.71% | 150/200 | -17.31% vs **-23.71%** |

On every world, on the median severe path, PE now draws down deeper than the equity
market and falls harder inside the worst twelve equity months — the sign the sealed-era
equation could not produce. For 711→721 and 713→723 the sealed-era medians were
+337.13% / +203.29% (decade), -27.73% / -33.41% (maxDD), 169 / 180 beats-eq, and
crash-window PE of -17.20% / -22.16% against the same equity — every column moved the
same direction as the Gulf pair. World 724's parent (604, `stagflation_1974` under
v1.2) was never measured pre-adoption — the serenity finding covered the three stress
worlds only — so its column has no "before" to quote; its after-numbers are listed so
the played generated preset is evidenced alongside the stress family.

Note on 723's live tape (+59.10%, well under its own median): the live seed's residual
draw is unlucky for PE in that world; the distribution columns are the representative
numbers. And 722's live tape (+385.91% vs median +191.64%) remains a lucky draw for the
same reason it was before — the +63.33pp residual carried over bit-identically.

## The checksum, stated

The script derives the alpha term's annual rate from the live artifact row through the
same accessor the adapter uses — `(1 + alpha_quarterly/3)^12 - 1` = **3.00%/yr**
(`alpha_quarterly` 0.007399, `map-2026.08.4`) — and refuses to report if it is not
3.00 to two decimals. It printed 3.00 [checksum OK], alongside the row's equity beta
of 1.2. Derived from the row, not hardcoded.

## What did NOT change — read this before celebrating

- **The row is still a straight line.** `r_pe` is the same affine function of the
  factor path it always was; there is still no regime term, no downside kink, no
  leverage scaling. The crisis beta equals the calm beta **at 1.2** exactly as it
  used to equal it at 0.8362. PE now falls harder than equity because 1.2 > 1, not
  because the model knows a crisis is happening. **ER-16 stays open on the missing
  convexity** — this release fixed the level and the crash magnitude, not the shape.
- **Everything else in the row**: `d_ig` -0.0279, `residual_sigma_annual` 0.1225,
  the C1 inflation block — bit-identical, proven term-by-term above.
- **Equity, and every non-buyout sleeve**: the median equity decade and maxDD columns
  reproduce the sealed-era values exactly (measured).
- **The reported plane's filter** (ER-11, w=0.35, unconditional) still applies on top
  of true; reported PE still lags and shallows true PE in a drawdown.
- **The anchor gap**: 1.2 and 3%/yr are CHOSEN against external anchors (DN-5's prior,
  the PME literature), not fitted — the repo still holds no empirical crisis-PE series,
  and nothing here changes the standing caveat that none of this is decision-ready.
