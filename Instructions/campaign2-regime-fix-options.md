# Campaign-2 regime-persistence fix — the options, for owner decision

*The one genuine modeling decision in campaign-2. The severe test (WP2.11)
located the defect UPSTREAM of L3: retraining the flow model cannot fix
what the regime layer feeds it. Drafted 2026-08-02; the promotion training
runs wait on this choice; nothing else does.*

## The defect, from G2-EVIDENCE §7–8 (the acceptance targets, verbatim)

1. **Inflation persistence ~half its historical half-life** — simulated
   inflation eras resolve about twice as fast as history's.
2. **1966–84 called a "long inflation era" under half the time** against
   history's every window: the model can visit the regime but cannot stay.
3. **Stagnant decades invented at 0.29–0.75** against a historical
   0.00–0.05 — fake lost decades, an over-mixing signature.
4. Drawdowns understated ~2× (partly L3's, but persistence feeds it: short
   regimes truncate compounding stress).

Whatever option is chosen, THESE FOUR STATISTICS are the fix's acceptance
measures, evaluated by the same battery cells that measured them — no new
yardstick invented for the occasion.

## Option A — duration-explicit regimes (semi-Markov)

Replace the Markov exit (geometric durations, memoryless) with explicit
per-regime duration distributions (e.g. negative-binomial) fitted to the
labeled historical regimes. **For:** targets the defect exactly — the
memoryless exit IS the mathematical reason durations come out short and
eras fragment. **Against:** a structural change to L2's model class:
refit, new artifact, more surface for new defects; sampling code changes.
**Cost:** days (CPU refit + joinery updates + battery).

## Option B — sticky-transition priors (recommended first move)

Keep the architecture; re-fit L2 with strongly persistent self-transition
priors calibrated to NBER/labeled era durations (a hierarchical
persistence prior rather than a hand-set constant). **For:** minimal
change — same model class, same sampling path, one refit; directly
raises expected durations; measurable against the four targets within a
day. **Against:** fixes MEAN duration but may not reproduce the long-era
tail (a 15-year inflation era needs more than stickiness); if the
defect's root is memorylessness, B under-delivers and we escalate.
**Cost:** hours.

## Option C — era-scale coupling to the climate layer

Condition regime transitions on L1's slow states (pi_star, r_star, ...)
so long eras EMERGE from slow-moving fundamentals rather than being
memorized durations. **For:** the most economically honest account — eras
last because their causes last. **Against:** touches the L1/L2 joinery
contract and the waypoint layer; the largest blast radius and validation
burden; research-grade work inside a delivery campaign. **Cost:** a week+.

## Recommendation

**B now, A if B misses, C recorded for the research track.** Run B's
refit and score the four targets; if persistence and era-calling clear
but the long-era tail still fails, escalate to A (the refits share the
duration-fitting groundwork). Either path lands behind the campaign seal
with the four acceptance statistics pre-stated in it. C goes to the
research backlog with this memo as its record.

**DECISION (owner, 2026-08-02): B then A if needed** — verbatim 'B then A if needed'. Option B's refit proceeds immediately; the four acceptance statistics above are the escalation trigger; C stays on the research backlog with this memo as its record.

---

*Not investment advice.*


---

## DIAGNOSIS UPDATE (2026-08-02, post-decision, pre-implementation)

The mechanism is NOT where the options above located it. Traced:

1. **L1 is healthy**: trend inflation's fitted half-life is ~10 YEARS
   (climate-fit-report: hl_pi median 9.6y, 5%..95% = 5.9..15.5y). The slow
   state wanders on exactly the decade scale history demands.
2. **L2 is already semi-Markov** (NegBin sojourns, priors.yaml) — the
   memo's Option A mischaracterized the current architecture. Fitted
   sojourns at z=0 look plausible (EXP 14.7m, REC 8.5m).
3. **The defect is L3 CONDITIONING ATTENUATION**, measured at WP2.8
   (artifacts/wp28/ig-spread-diagnosis.md §4: "every channel damped") —
   the generated monthly factors under-respond to the L1/L2 conditioning
   and collapse toward the unconditional mean, so a 10-year pi* trend
   becomes a 30-month generated half-life. The flow arm's classifier-free
   guidance was built as the countermeasure, but the SEALED tuning
   criterion (gen + D4 aux) never rewarded era-scale persistence, so the
   search had no pressure to select strong guidance.

**The decided sequence (B then A) maps onto the true mechanism as:**

- **B' (cheap lever first)**: a GUIDANCE SWEEP on the incumbent
  checkpoint — sample at guidance_scale ∈ {1.0, 1.5, 2.0, 3.0}, score the
  four acceptance statistics per level. Sampling only, no retrain. If
  persistence recovers at some level, the campaign pre-states that level
  in its seal as a config choice (legitimate: chosen before the
  promotion seal, against pre-stated statistics).
- **A' (structural, if B' misses)**: residual parameterization — L3
  generates DEVIATIONS around the L1-implied factor means so trend
  tracking is structural rather than learned; retrain required (cheap:
  ~3.5 min/run per the probe).

The owner's B-then-A intent (cheap lever first, structural second) is
preserved exactly; only the mechanism's address changed. The four
acceptance statistics are unchanged and remain the only yardstick.
