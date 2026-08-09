# WP-DATA-FSEXT — scoping: extend `funding_spread` beyond TED's life

*Scoping draft, 2026-08-09, following the VOLEXT pattern (read → plan →
owner questions → decisions recorded → build). Nothing here is committed
work; the owner questions at the end gate the start.*

## The situation

`funding_spread` is `ah.data.derive.funding_stress(fred.TEDRATE)`: TED = 3m
LIBOR − 3m bill, observed **1986-01 .. 2022-01** and then *honestly
incomplete* — TEDRATE retired with LIBOR, and although the replacement legs
are already registered (`fred.CPF3M` = DCPF3M commercial paper, and
`fred.TB3M_SEC` = DTB3 secondary-market bills, both FREE), nothing wires
them: `factors.yaml`'s own notes call the post-2022 history incomplete.

So the factor has **two missing ends**, and the same instrument family fixes
both: the **CP − bill spread**, the standard funding-stress measure of the
pre-LIBOR literature and the de-facto successor construction after LIBOR's
death.

## The donor chain (all FREE, all on FRED)

| segment | donor pair | coverage |
|---|---|---|
| post-2022 (the known hole) | `DCPF3M` − `DTB3` | 1997-01 → live |
| pre-1986 backward extension | CP3M-family (discontinued AA nonfinancial CP) − `TB3MS` | ~1971 → 1997 |
| deep history | NBER macrohistory 3-month prime commercial paper (M13002…NNBR) − `TB3MS` | CP from 1857; **bills from 1934-01**, which is the floor |

Every segment is *observation*; the splice fits ride the generous overlaps
(CP−bill and TED coexist over 1986–2022, giving both a backward and a
forward overlap fit). Reaching past 1934 would need a bill proxy (Treasury
notes/certificates yields) and is best left out of scope.

## What it unlocks, and what binds next

With `equity_vol` extended (VOLEXT) and `funding_spread` reaching 1934, the
`block_draw_span` amendment could go to **1984-01, where `hqm_curve`
binds** — the next constraint, for which the Shiller GS10 + Moody's Aaa/Baa
reconstruction (1919+) is the candidate donor set, per the 2026-08-09
binding-chain discussion. `fx_usd` (1973) binds after that.

## Sealed surfaces

`factors.yaml` (the `funding_spread` inputs list) and `src/ah/data/derive.py`
(`funding_stress`) are both hashed by `pre-registration.lock`. Same posture
as VOLEXT: build in a new module consuming the splice framework read-only,
verify overlap fits on real data, propose the wiring as an amendment, apply
nothing. A test pins that nothing sealed learns the new rule.

## Definitional honesty (the thing to rule on before building)

TED measures unsecured *bank* funding stress (LIBOR leg); CP−bill measures
high-grade *corporate* funding stress. They co-move tightly in every stress
episode both observe, but not identically — 2008 TED peaked ~4.6% while
nonfinancial CP spreads peaked lower (financial CP froze outright). A splice
absorbs the average level/scale difference; the regime difference is a
disclosed caveat, exactly like VXO(S&P 100)→VIX(S&P 500) in VOLEXT stage 1.
Under the owner's D6 distinction this is *recreation from observed
contemporaneous instruments*, not modelling — but the instrument-identity
ruling is the owner's to make, not this document's.

## Owner rulings (2026-08-09: "go with your recommendations on all three")

1. **F1 — Identity ruling: ACCEPTED.** CP−bill is the funding-stress
   recreation for the eras LIBOR doesn't cover (pre-1986 and post-2022),
   instrument difference disclosed, per the D6 recreation-vs-modelling
   distinction.
2. **F2 — Scope: BOTH ENDS.** The post-2022 repair is in this WP: same rule
   family, one amendment, closes the known train+validation hole. Recorded
   deviation from the splice framework's backward-only shape; the
   never-overwrite-observed invariant is unchanged.
3. **F3 — Depth: 1934-01.** The bill leg's floor. 1929-33 stays out of
   reach; a pre-1934 bill proxy is its own future decision.

Built as `ah.data.funding_extend` (rule `PROXY-FUNDING-CPBILL-V1`);
verification on real data in `docs/data/FSEXT-REPORT.md`.
