# WP1.12 — UK Data Connectors (BoE, ONS, PPF)
## Work package for Claude Code · extends Step 1 · **independent of the Step-2 seal**

**Why now:** the UK factor block is CLOSED-deferred (J3), but the data is free and the connectors are on the critical path for any future block addition. Landing the data now converts a later "data project plus amendment" into just an amendment.

**Branch independently.** This does not touch Step 2 and must not block it. Merge whenever it is ready.

---

## The hard constraint (read first)

Every series added here enters the catalog as **registered and available, but inactive**:

- It must **not** enter `panel/factors_monthly.parquet` for the active block set.
- It must **not** enter `eval/reference.py` inputs or any threshold computation.
- Adding it must **not** change any existing digest.

A UK series leaking into the sealed panel would contaminate the reference statistics and therefore the pre-registered thresholds — the one error in this build that cannot be quietly fixed later. **Add a test that asserts the active-block panel contains no series from an inactive block.**

## Manifest entries

Add to `requirements.yaml` under a `uk` block, with `active: false`:

| series_id | Source | Freq | History | Notes |
|---|---|---|---|---|
| `boe.bank_rate` | Bank of England | M | long | Official Bank Rate history |
| `boe.glc_nominal_{1y,5y,10y,20y}` | BoE yield curve statistics | D→M | 1970– | Government liability curve, nominal spot |
| `boe.glc_real_{5y,10y,20y}` | BoE | D→M | 1985– | Real (index-linked) spot curve — **the UK discount basis** |
| `boe.glc_inflation_{5y,10y}` | BoE | D→M | 1985– | Implied inflation, derived from the two above |
| `ons.rpi` | ONS | M | 1947– | Series CHAW; still the dominant indexation basis in legacy benefits |
| `ons.cpi` | ONS | M | 1988– | Series D7BT |
| `ons.cpih` | ONS | M | 2005– | Series L55O |
| `ppf.7800_funding_ratio` | Pension Protection Fund | M | 2003– | **Validation series, not a factor** — aggregate s179 funding ratio of the UK DB universe |

Mark `ppf.7800_funding_ratio` explicitly as `role: validation` so it can never be mistaken for a model input.

## Connectors

**`connectors/boe.py`** — the BoE publishes its yield-curve data as large multi-sheet Excel workbooks (nominal, real, implied inflation, each split across historic and recent files). Expect the same defensive parsing discipline as the Shiller connector: assert on header content rather than indexing by position, handle the historic/current file split, and snapshot-test the parse. Daily→monthly aggregation follows the existing rule for rates (monthly mean), stated in the source doc.

**`connectors/ons.py`** — ONS exposes a JSON time-series API; prefer it to CSV scraping. Series are identified by dataset plus four-character series id (CHAW, D7BT, L55O). Index values, not rates — compute year-over-year in `derive.py`, not in the connector.

**`connectors/ppf.py`** — monthly index published as a spreadsheet; small and simple. Treat as manual-intake if the publication URL proves unstable.

**Verify every URL at build time.** If an endpoint has moved, fix the connector and note it in `docs/data/<source>.md` — do not hardcode a workaround silently.

## QC and documentation

Standard rules apply: bounds by units class (real yields legitimately go negative — set the floor accordingly, and do not let the existing rate bounds reject them), monotonic dates, staleness SLAs, revision diffs. Add one cross-series identity check: implied inflation ≈ nominal − real, within tolerance, on the overlap.

`docs/data/boe.md`, `docs/data/ons.md`, `docs/data/ppf.md`: exact URLs, licence position (all three are freely reusable under their published terms — record the specific terms), release calendars, and known quirks.

## A design note worth recording

For a UK **liability-side** twin, the block needs rates and inflation only. UK equity indices (FTSE All-Share, FTSE Actuaries gilt indices) are licensed and not free — but they are also not strictly necessary: UK equity exposure can be carried by the global equity block once FX exists. Record this in the source docs so a future block activation does not stall waiting for an index licence it does not need.

## Definition of done

1. All series fetch, parse, QC, and land in the catalog as `active: false`.
2. The inactive-block isolation test passes; no existing digest changes.
3. Source docs written; URLs verified; fixtures recorded for offline tests.
4. `GAPS.md` shows the UK block as registered-and-sourced, awaiting activation.
5. CI green.

**Not in scope:** activating the block, computing UK reference statistics, panel assembly changes, CMI mortality tables (an actuarial-membership item, not a connector), any FX series.
