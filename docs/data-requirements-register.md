# Data Requirements Register — Alternate Histories Platform

*WS-A reference · v1.1 · July 2026 (v1.1: Albourne confirmed as primary source for private-markets and hedge-fund strategy-level returns; layer 2 and procurement updated). Priority: **P0** = needed for Phase 0–1 (defensible engine); **P1** = Phase 2–3 (generative pilot, twin, research program); **P2** = stretch/Phase 4. License tiers: FREE, REG (free with registration/membership), COMM (commercial license — budget line). Start procurement on all COMM items in week 1; interim development may use the listed fallbacks with placeholder-calibration labels.*

---

## 1. Public-market factor layer (WS-B · decisions D2/D3)

Monthly unless noted; daily retained where cheap (vol-state construction). Long history is the point — this layer must span regimes the alternatives never saw.

| Series | Frequency | History | Primary source | Fallback / notes | Tier | Priority |
|---|---|---|---|---|---|---|
| US equity total return (S&P 500 TR) | Monthly (daily avail.) | 1926– | Ken French library / Shiller data | CRSP via WRDS if subscribed | FREE | P0 |
| Global/developed equity TR (MSCI World) | Monthly | 1970– | MSCI (licensed) | Ken French "Developed" factors as proxy | COMM | P1 |
| Size & value factors (SMB, HML; mom.) | Monthly | 1926– | Ken French library | — | FREE | P0 |
| Treasury yields & curve (level, slope) | Monthly (daily) | 1953– (GSW 1961–) | FRED (DGS/GS series); Fed GSW dataset | Shiller long rate extends to 1871 | FREE | P0 |
| Long Treasury total return | Monthly | 1926– | Ibbotson SBBI via Ken French/lit; SBBI (COMM) | Construct from yields pre-1973 | FREE/COMM | P0 |
| IG credit spread (Baa–Aaa / Baa–Tsy) | Monthly | 1919– | FRED (Moody's Baa/Aaa) | — | FREE | P0 |
| HY OAS spread | Daily/monthly | 1996– | FRED (ICE BofA HY OAS) | Extend pre-1996 with Baa proxy mapping | FREE | P0 |
| HY total return index | Monthly | 1986– | ICE BofA (licensed); FRED partial | Bloomberg HY if terminal exists | COMM/FREE | P0 |
| CPI (headline & core) | Monthly | 1913– | BLS via FRED | — | FREE | P0 |
| Inflation breakevens (5y, 10y) | Daily/monthly | 2003– | FRED | Survey-based expectations (SPF) pre-2003 | FREE | P1 |
| Commodities index TR | Monthly | 1960–/1991– | S&P GSCI or BCOM (licensed) | Equal-weight spot from academic datasets | COMM | P0 (fallback), P1 (licensed) |
| REIT total return (FTSE Nareit) | Monthly | 1972– | Nareit (research registration) | — | REG | P0 |
| Cash / 3m T-bill | Monthly | 1934– | FRED | — | FREE | P0 |
| Equity vol state (VIX + realized) | Daily→monthly | 1990– (realized 1926–) | Cboe (free); realized derived from returns | — | FREE | P0 |
| Funding/liquidity spread (TED/OIS basis) | Daily→monthly | 1986– | FRED | — | FREE | P1 |
| Deep-history macro-financial panel | Annual | 1870– | Jordà–Schularick–Taylor Macrohistory DB | For held-out-regime backtests (RQ2) | FREE | P1 |
| Very-long daily/monthly extensions | Mixed | 1800s– | Global Financial Data | Optional; only if RQ2 wants pre-1926 depth | COMM | P2 |

## 2. Alternatives calibration layer (WS-C · decisions D1/D7)

**Primary source: Albourne (existing relationship).** Albourne provides strategy-level return series for both private markets and hedge funds, which upgrades the design in two ways: sleeves can be modeled at *strategy* granularity rather than broad asset-class composites, and de-smoothing parameters and factor mappings can be estimated per strategy. Everything here still passes through de-smoothing before use — strategy-level series remain built from reported NAVs/manager returns and carry the same smoothing and selection characteristics as any composite. Public indices are retained as independent cross-checks (a second source materially strengthens the validation record) and as fallbacks.

| Series | Frequency | History | Primary source | Cross-check / fallback | Tier | Priority |
|---|---|---|---|---|---|---|
| Private markets strategy-level returns — buyout, growth, VC, secondaries; private credit sub-strategies (direct lending, mezz/opportunistic, distressed); RE value-add/opportunistic; infrastructure | Quarterly | Confirm per strategy (typ. 1990s–/2000s–) | **Albourne** | Burgiss/Cambridge composites; listed proxies (LPX, S&P Listed PE) | Existing relationship — confirm scope | P0 |
| Hedge fund strategy-level returns — equity L/S, macro, relative value, event-driven, credit, CTA, multi-strat | Monthly | Confirm (typ. 1990s–) | **Albourne** | HFRI / Credit Suisse composites | Existing relationship — confirm scope | P0 |
| Core private real estate (NPI / ODCE) | Quarterly | 1978– | NCREIF (membership) | Albourne RE strategy series; REIT de-levered proxy | COMM (membership) | P1 (longest RE history for de-smoothing calibration) |
| Private credit market-level index | Quarterly | 2004– | Cliffwater CDLI (registration) | Albourne PC strategy series (cross-check) | REG | P0 |
| Derived cashflow measures (in lieu of fund-level data): lifecycle call/distribution-rate profiles with dispersion, quarterly aggregate call/dist rate time series, age×calendar rate matrices, vintage TVPI/DPI/IRR quartiles, episode cuts — full specification in `albourne-derived-measures-spec.md` | Quarterly (profiles by fund age) | Confirm per strategy | **Albourne** (derived measures confirmed available; raw fund-level cashflows not immediately available) | Burgiss/Preqin cashflow module remains the P2 fallback if matrices (item C) prove out of scope | Existing relationship | P0 (subset B+A) / P1 (C–E) |

*Documentation requirements for the Albourne series (needed for Gate G1 evidence and D1 calibration): construction methodology, universe and survivorship treatment, backfill policy, and any smoothing already applied — obtain the methodology notes alongside the data.*

## 3. Structural covariates (WS-C/D · decisions D2/D7 — the "asset class as it is" dials)

Mostly annual, some quarterly; modest volumes, awkward formats (report PDFs). Budget analyst time, not just licenses.

| Series | Frequency | History | Primary source | Notes | Tier | Priority |
|---|---|---|---|---|---|---|
| Buyout entry EV/EBITDA multiples | Annual (qtrly avail.) | ~1997– | PitchBook/LCD; Bain Global PE Report (summary) | Bain/consultant PDFs free for headline series | COMM/FREE | P0 |
| Buyout leverage (debt/EBITDA at entry) | Annual | ~1997– | PitchBook/LCD | Same | COMM/FREE | P0 |
| Dry powder & fundraising by strategy | Quarterly/annual | 2000– | Preqin or PitchBook | Consultant summaries as fallback | COMM | P1 |
| Direct-lending new-issue spreads & market size | Quarterly | 2010– | Cliffwater reports; LSTA/PitchBook LCD | — | REG/COMM | P1 |
| Cap rates (by sector) | Quarterly | 1978– (NCREIF) | NCREIF; Green Street (COMM) for transaction-based | — | COMM | P1 |
| Secondary market pricing (% of NAV by strategy) | Semi-annual | 2003– | Jefferies / Campbell-style secondary reports (public PDFs) | Anchors the 2022 validation episode & secondary-sale mechanics | FREE | P0 |
| PE distribution/call rates (industry aggregate) | Quarterly | 2000– | Burgiss/Preqin aggregates; consultant pacing notes | Feeds market-sensitive TA calibration | COMM/FREE | P1 |
| Recession/regime labels | Monthly | 1854– | NBER (free) + derived Markov states | D2 decision determines final regime variable | FREE | P0 |

## 4. Institution & liability layer (WS-D · decision D8)

| Series | Frequency | History | Primary source | Notes | Tier | Priority |
|---|---|---|---|---|---|---|
| Mortality tables + improvement scales | Static/annual updates | Current | SOA (Pri-2012, MP scales); national tables | FREE | FREE | P1 |
| Pension discount curves (AA corporate / HQM) | Monthly | 1984– (HQM) | US Treasury HQM via FRED; FTSE pension curve | Liability PV under rate states | FREE | P1 |
| Representative DB plan demographics & benefit rules | Static | — | Public plan actuarial valuations/CAFRs; else synthetic cohort | Synthetic default keeps privacy trivial | FREE | P1 |
| Peer allocation norms (endowment/pension mixes) | Annual | 2000– | NACUBO, public plan reports, Global SWF/Thinking Ahead | Calibrates default mixes & peer letters | FREE | P1 |

## 5. Validation & episode data (WS-G · decisions D6/D9)

| Item | Frequency | Source | Purpose | Tier | Priority |
|---|---|---|---|---|---|
| 2022 episode pack: drawdowns, distribution drought, secondaries ≈81% NAV, denominator-effect documentation | One-time compilation | Public consultant/CFA Institute/secondary reports + layer-1/2 series above | Gate G1 end-to-end reproduction test | FREE | P0 |
| Held-out-regime panels (1970s stagflation; 1930s deflation) | Monthly/annual | Layers 1 + JST | RQ2 counterfactual-validity backtests | FREE | P1 |
| Stylized-fact reference statistics | Derived | Computed from layer 1 | D6 pre-registered thresholds | FREE | P0 |

## 6. Live world & artifact layer

No external market data required — the wire, letters, and notes are generated from the tape. Two small static inputs: a **release-calendar template** (which world-day CPI, policy decisions, marks land — authored in-house, modeled on public statistical calendars) and the **real-entity name screen** for the World Bible (GLEIF LEI list + SEC IAPD extracts, both FREE, refreshed at bible creation).

---

## Procurement summary & sequencing

**Week 1 (confirmations and COMM procurement):** (a) **Albourne scope confirmation — now the top action**: inventory the strategy-level series available under the existing relationship (strategies covered, start dates, frequency, methodology notes, survivorship/backfill policy), confirm whether fund-level cashflow data is included, and — critically — confirm the license terms permit use for model calibration within this platform (consultant data agreements often cover internal analysis; calibration of a simulation product may require an amended permission). (b) Remaining COMM items, now a shorter list: NCREIF membership (longest RE history for de-smoothing calibration), commodities index license, HY total-return license (or confirm terminal coverage), PitchBook/LCD or equivalent for multiples/leverage. Burgiss/Cambridge drop from "required" to "optional cross-validation source," to be revisited only if the validator wants a second independent alternatives series at Gate G2. **Immediately usable:** everything FREE/REG in layers 1, 3, 5 plus the Albourne series on confirmation — Phase 0–1 can begin at strategy-level fidelity rather than proxy fidelity. **Explicit gaps to accept and label:** pre-1996 HY spreads (proxy-mapped), infrastructure before ~2000, strategies whose Albourne history starts late (extend via mapped listed proxies, labeled), and fund-level analysis pending the scope confirmation. **Named decisions for the workshop agenda:** the strategy taxonomy for D2/D7 sleeves (which Albourne strategies become modeled sleeves vs aggregates — recommend starting with 6–8 private-market and 4–5 hedge-fund strategies), and licensed commodities index vs academic equal-weight for the frozen D2 factor list.

*Total COMM budget drivers, in order (post-Albourne): fund-level cashflow module if outside Albourne scope (P2, largest single item — defer to Phase 3 gate), NCREIF membership, structural covariates platform (PitchBook/Preqin), benchmark licenses (MSCI/commodities/HY). The alternatives-index line — previously the largest near-term item — is now covered by the existing Albourne relationship. Everything else on this register is free.*
