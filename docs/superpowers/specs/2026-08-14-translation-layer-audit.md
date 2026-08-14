# Translation-Layer Audit — 2026-08-14

**Owner directive:** "make sure the second-stage elements, e.g. traditional
to private conversions, cashflow models etc work as designed." Three
independent read-only auditors verified behavior against the DESIGN
documents (not the test suite) on the 1974 world (`…603`, seed 197400,
engine toy-v0.6, mappings v1.1), each finding computed numerically —
hand-reconstructions against live code, ledger identities per quarter,
live sessions on the scored surface. Findings only; every fix is an owner
decision. Full working papers were produced in the session scratchpad;
this document carries the substance.

## Verdict in one paragraph

**The numeric spine is exact.** The factor→sleeve conversion matches a
hand reconstruction of the sealed v1.1 artifact bit-for-bit; the cash
ledger balances to exactly zero every quarter of all five played decades;
committed capital is conserved through the expiry ledger; the pacing law
reproduces to 0.0 difference at all nine commitment events; alpha equals
the sum of window contributions to 0.00e+00 on live sessions; the twins
are bit-identical across different decision scripts; and the flinch
annotation's price matches an independent recomputation to rounding. The
gaps are not arithmetic: they cluster into **dead design** (sealed
machinery that never runs on the live path), **computed-but-invisible**
(numbers the design wanted shown that never reach a surface), and
**calibration drift** (declared targets the realized behavior misses).

## What is exactly as designed (verified, with numbers)

| Check | Design says | Measured |
|---|---|---|
| Mapping application (A1) | v1.1 loadings + declared residual stream | bit-exact vs hand reconstruction, 0.0 diff, all sleeves/months |
| Call curve (B1) | ~90% called by year 10 (declared rc_curve, ER-6/D1) | 90.24% |
| Cash ledger (B4) | conservation | error exactly 0.000e+00, every quarter, 5 decades; unfunded never negative |
| Crisis linkage (B2) | calls near-flat, distributions cut in stress | worst quarter: f_call 0.9736 (=1−0.1·dd exactly), f_dist 0.7969 |
| Forced secondaries (B5) | register: 0/20 on this world class | 0/5 decades |
| Pacing law (C1) | target = base × g(w_policy − w_reported), sens 4.0, clip (0.5,1.5) | exact match at all 9 commit events; telescoping/null-player/drift-reduction all exact |
| Counter-cyclicality (C2) | policy leans in during troughs (ER-10 close-out) | multiplier 1.264 in the worst-drawdown year vs 0.91–0.98 calm; corr(mult, drawdown) +0.58 |
| Book identities (C3) | coverage = unfunded/NAV both bases; private NAV = weight×total | exact, 0.0 error |
| Alpha integrity (C4) | server-authoritative, telescoping | alpha − Σ contributions = 0.00e+00, two live sessions; twin + drift series bit-identical across scripts |
| Flinch pricing (C5) | state the number, never gloat (E4) | hand recompute 0.788881 vs served 0.7889 (1.9e-5) |
| DPI realism (B3, partial) | terminal DPI plausible | age-9 DPI 1.10 (path 0), 0.98 median — inside band |

## Findings

### F1 — Dead design: the sealed smoothing kernel and HF applier never run (A3/A4)

DN-5 SM-10 requires the reported plane to be "one model, two views": the
sealed smoothing-kernel estimate (`mappings/smoothing-kernel-v1.0.yaml`)
paired with the de-smoother that judged the mappings. Measured: the live
path (adapter → engine `_reported_marks`) uses the toy engine's uniform
filter instead; `ah/port/smoothing.py` and `ah.port.mapping.sleeve_returns`
(the sealed-artifact applier, incl. HF residual correlation and the CTA
rule) are exercised only by their own tests. The two smoothing models
disagree materially: quarterly reported autocorr 0.55 (live filter) vs
0.06 (sealed kernel) for pm_buyout. **And the unused kernel carries a real
bug**: its degenerate-theta branch (`ah/port/smoothing.py:169-176`)
inflates pm_direct_lending's reported cumulative return 4.47× (+1126% vs
+252% true) — harmless today only because the code is dead.
**Owner decision:** either (a) declare the engine filter the product's
smoothing model and retire/fix the port kernel explicitly (recording the
SM-10 deviation), or (b) route the sealed kernel live (a larger WP:
engine numbers change again). The bug gets fixed under either.

> **RESOLVED 2026-08-14 — route (a).** The owner declared the engine
> filter the product's smoothing model; the SM-10 divergence is recorded
> as `docs/engine-realism-register.md` **ER-11** (what the shipped path
> forgoes; reopening scoped at ~3 working days) and in
> `governance/decision-register.md`. The 4.47x bug is FIXED
> (`f1-01-smoothing-degenerate-theta`) with a guard that refuses any
> weight vector not spanning the lag window. Exposure was checked consumer
> by consumer and is nil: no `ah/eval/` module imports the kernel;
> `scripts/run_2022_replay.py` used the non-degenerate `hf_event` theta;
> and the only committed artifact that ran the branch
> (`docs/data/CAMPAIGN-R1-TRANSLATION.md`'s PM plane) carried an all-zero
> direct-lending series. No shipped or committed number changes.

### F2 — Computed but invisible: the ER-6 expiry line never reaches a surface (B1)

`ClosedEndCohort.step` produces `expired_undrawn` exactly as the ER-6
close-out designed ("expires visibly instead of haunting the books") and
conservation holds — but `ah/play.py`'s loop drops the field: it never
reaches PlayQuarter, the programme console, or the player. The design's
stated purpose was visibility. **Owner decision:** small WP to surface it
(ledger line + programme table), or record the deviation.

> **RESOLVED 2026-08-14 — surfaced** (`f2-01-surface-expired-undrawn`).
> `PlayQuarter.expired_undrawn` carries it; the programme console's ladder
> gains an `expired` column with the note explaining the unfunded drop that
> `called` cannot; the session service serves the quarter's release AND a
> running total (`expired_undrawn_to_date` — the event fires once per decade,
> so it must outlive the quarter it happened in); the app's private-markets
> ledger shows it. **Measured on the shipped presets: 9.02 (stagflation) /
> 8.86 (goldilocks) expires in quarter 19 — 17% and 14% of everything called
> that decade**, in a single quarter, previously invisible on every surface.
> All three seed cohorts open at age 5.25 against a 10-year life, so they
> lapse together. Scope note: the bundle's `TwinLedger` was NOT extended
> (that is a contract-version change), so the line is session-only and browse
> mode shows nothing rather than showing the twin's release as the player's.

### F3 — Distributions run slow: crossover misses its band (B3)

Declared band for calls/distributions crossover: years 4–8. Measured on
the 1974 decades: median 8.875, and 3 of 5 seeds never cross within the
decade. Age-9 DPI is inside its band, so the money arrives — late. Likely
interaction of the tier-1 stress linkage with the 1974 decade's long
stagflation (distributions throttle in stress by design). **Owner
decision:** accept-and-record (a stagflation decade SHOULD distribute
late; the band was drafted for average conditions) or a design review of
the distribution pace.

> **RESOLVED 2026-08-14 — ACCEPTED AND RECORDED**, no code. Full entry with
> the reasoning and the cost in `governance/decision-register.md`. Confirmed
> beyond the 1974 decades before accepting: stagflation reads 8.75 with 8 of
> 20 seeds outside the band, so this is the world class, not one preset. The
> band value is deliberately LEFT UNCHANGED so the flag keeps firing —
> widening it to stop the flag would destroy the only signal it still
> carries. What the acceptance gives up: a world that distributes late for
> some other reason will look identical on this surface.

### F4 — Scored-surface opacities (C1/C3)

Two transparency gaps, neither a math error: the "next plan" pre-fill the
player sees is up to 7.9% stale (one-quarter timing lag; the engine
recomputes fresh on an untouched lever, so scores are unaffected — but
the displayed number is not exactly the plan); and spending follows the
reported trailing average correctly (4.4e-16 internally) but no exposed
series lets an outside party rederive it (a pre/post-waterfall NAV
distinction is invisible downstream, ~1–3% mismatch if attempted).
**Owner decision:** batch both into one small display/API WP, or record.

> **RESOLVED 2026-08-14 — batched and fixed** (`f4-01-scored-surface-auditability`),
> ahead of E1 at the owner's direction, since the lever is built on the pre-fill.
>
> **The pre-fill cannot be made exact, and that is the finding.** It is
> computed at the last CLOSED quarter; the engine paces on the weight at the
> commitment quarter, whose returns are unrevealed at decision time —
> computing the pre-fill from them would leak the tape. So it is now
> DECLARED: `next_plan_basis` (as-of quarter, as-of month, and the reported
> weight it used) is served and the lever states it on the page.
>
> **A sharper defect was found underneath it.** The app merged the whole
> pre-fill into its state as soon as ONE sleeve was edited, then sent all
> three — so touching `pe` silently froze `pc` and `re` at stale numbers the
> player believed were "the plan". The engine already supports partial
> commitments (per-asset fallback to `plan_amount`), so the lever now sends
> only the sleeves actually touched: an untouched sleeve is paced fresh
> server-side and holds to plan EXACTLY, rather than being committed at a
> quarter-stale approximation of it.
>
> **Spending is rederivable.** `spending_basis` and `spending_rate_annual`
> are served, so `spending_paid == rate / 4 * spending_basis` closes on the
> API alone (pinned to `rel=1e-12` across a full decade walk). The basis is
> the trailing mean sampled INSIDE the waterfall — after calls, before
> spending and any forced sale — which is why quarter-end `nav_reported`
> never reproduced it.

### F5 — Calibration drift (A2/A3)

- CTA rule realizes 0.1595 vol vs its declared 0.10 target on this world
  (trailing-vol estimator lags the regime shock) — HF-only, not
  player-facing today.
- v1.1 PM betas moved toward the DN-5 priors but stopped short (buyout
  0.84 vs 1.1–1.3 prior); recorded at estimation, restated here.
- PM residuals are independent Gaussian; DN-5 SM-8 seals a
  fatter-tailed/block-correlated residual model. A known thin-mapping
  choice — restated so it is on this audit's record.
**Owner decision:** none urgent; candidates for the next amendment cycle.

## Suggested priority (if the owner wants fixes)

1. F1's bug fix (the 4.47× branch) — small, honest regardless of the
   route chosen; the F1 route decision itself can wait.
2. F2 (surface the expiry line) — small WP, completing the ER-6 design
   intent.
3. F4 (display staleness + spending series) — small, improves auditability
   of the scored surface.
4. F3/F5 — decisions to record rather than code to write.
