# E1 over-commitment measurement — declaration

*2026-08-15. Owner-directed ("run the E1 over-committed measurement").
This section is committed BEFORE any arm is run; the results section is
appended in a later commit. The grid is derived from declared policy and
public precedent, not from searching for breakage.*

## The question

The stress arc established (methodology note, third measurement) that the
default hold-course book survives any precedented decade: the forced
secondary is hypothesised to be the *over-committed* book's event — the E1
commitment lever's story. This measurement tests that hypothesis on the
Lost Decade (world `…703`, 6-month blocks, the deepest declared scenario).

## The declared grid

Opening private allocation, as points of the 100-point book (cash fixed at
2; private sleeves scaled proportionally from the default 20/8/7; liquid
sleeves scaled proportionally from 41/12/5/5 to absorb the difference).
The pacing law then chases each book's own target weight, so a higher
opening allocation also commits harder throughout — which is the lever.

| arm | private points | anchor — stated before any outcome |
|---|---|---|
| floor | 15 | the declared `Policy.private_weight_range` minimum (0.15) |
| default | 35 | the shipped book, already measured (0/20 on this world) |
| ceiling | 40 | the declared `Policy.private_weight_range` maximum (0.40) |
| breach | 55 | beyond the declared policy — the committee that ignored its own range. Anchored on the public endowment-model precedent of ~50–60% illiquid/alternative allocations at large US endowments in the 2000s–2010s |

## Protocol

The standing ladder harness, unchanged: 20 seeds (`771204 + 7919·k`) on
world `…703`'s tape via `run_gen_path`, `simulate_play` hold-course with
`start_targets` per arm. Statistics per arm, definitions unchanged from
the stress-01 measurement: coverage breach (unfunded/liquid ever ≥ 1.0),
forced-secondary incidence and events, worst coverage, final-value
distribution. **One run per arm; whatever it says is the record.**

## Results — run once, 2026-08-15, recorded as found

| arm | private points | coverage breach (≥1.0 ever) | forced secondaries | worst coverage med · max | final min · med | seeds below 100/75/50 |
|---|---|---|---|---|---|---|
| floor | 15 | 0/20 | 0/20 | 0.103 · 0.164 | 86.6 · 145.0 | 2/0/0 |
| default | 35 | 0/20 | 0/20 | 0.309 · 0.540 | 94.2 · 154.1 | 2/0/0 |
| ceiling | 40 | 0/20 | 0/20 | 0.382 · 0.694 | 95.1 · 156.6 | 2/0/0 |
| breach | 55 | **1/20** | **0/20** | 0.719 · **1.571** | 93.4 · 161.9 | 2/0/0 |

## Reading, stated plainly

1. **The lever is real and beautifully legible.** Worst coverage is
   monotone in allocation across a 15× range (0.10 → 1.57), and the breach
   book produces the programme's first coverage breach anywhere in the
   measured space. Allocation is the variable that moves liquidity risk;
   the market tape, at the edge of precedent, is not.
2. **The hypothesis is only half-confirmed.** Over-commitment reaches the
   coverage *warning* line; it does not reach the forced *sale*. Even a
   book that ignores its own policy range keeps enough liquid assets
   (43 points) to fund calls and spending through the deepest declared
   decade on 19 of 20 seeds, and never exhausts them outright.
3. **The reference ladder shape is a drafting artifact.** "20/20 breached,
   4–8/20 forced secondary" is unreachable anywhere in the space of
   precedented markets × declared-or-precedented allocations. The forced
   secondary as built requires conditions outside both — it fires only in
   the schema-bound maximal test world. It should be treated as the
   catastrophic-tail event that honest robustness makes rare, not as a
   target incidence.
4. **Product implication (owner's to take up):** the teachable,
   allocation-sensitive signal this measurement surfaces is the coverage
   ratio and its breach line — monotone, legible, and it moves with the
   player's own lever. The forced secondary remains the endgame beyond it.
5. **A curiosity recorded without interpretation:** median final value
   *rises* with allocation (145 → 162) even in the Lost Decade — the
   private sleeves out-compound the liquid ones on this tape. Risk here is
   a liquidity phenomenon, not a return phenomenon, which is exactly the
   lesson the institutional model exists to teach.
