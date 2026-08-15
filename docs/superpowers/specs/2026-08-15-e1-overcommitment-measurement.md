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

## Results

*(appended after the declaration commit)*
