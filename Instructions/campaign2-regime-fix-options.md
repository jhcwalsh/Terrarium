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

**Decision requested:** approve B-then-A-if-needed, or direct otherwise.

---

*Not investment advice.*
