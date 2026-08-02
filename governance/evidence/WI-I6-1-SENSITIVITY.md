# WI-I6-1 sensitivity — the G1 drought ratio under the corrected Y

Vintage `2026-08-01.2`; window 2021-12-01..2023-12-31; produced by
`scripts/measure_wi_i6_1_sensitivity.py`. A robustness note on the
sealed G1 result — the sealed replay, its evidence, and the G3 lock
are untouched. The sealed criterion: trough of the age-matched
stressed/calm distribution-rate ratio inside [0.45, 0.55].

| yield_rate Y | drought ratio at trough | inside sealed band |
|---|---|---|
| 0.01 (as sealed) | 0.5442 | YES |
| 0.55 (corrected, pacing-1.0) | 0.5433 | YES |

Sealed G1 figure for reference: 0.544 (G1-EVIDENCE.md).

## Reading

The sealed drought verdict is ROBUST to the WI-I6-1 rescale: the ratio construction cancels the distribution LEVEL almost entirely (Y appears in both numerator and denominator; the residual path dependence through NAV moves the figure only in the fourth decimal). The G1 criterion's PASS stands on its own terms under the corrected parameter.

---

*Not investment advice.*
