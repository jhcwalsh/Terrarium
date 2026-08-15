# Tail Register
## Every severity-producing mechanism, with its falsifier · 2026-08-14 · v0.1

*Created by amendment A7 of the stress-compiler design
(`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md` §12).
A severity programme multiplies the failure mode the exit-hysteresis episode
exemplified: mechanisms that manufacture severity can silently make an
acceptance test vacuous. This register exists so no such mechanism enters the
engine anonymously.*

**Admission rule: if a mechanism cannot name its own falsifier, it does not
enter the engine.** Every row carries seven fields — ID · layer · parameter ·
estimator · data source · acceptance test · ablation arm — and a row missing
its acceptance test or ablation arm is an open blocker, not a formality.

**Status legend:** LIVE (in the engine today) · PROPOSED (specified, not
built) · BLOCKED (may not proceed) · PRECEDENT (recorded failure that
motivates the register).

---

## TR-1 — Severity-percentile entry rule · PROPOSED

| field | value |
|---|---|
| Layer | Generator — `src/ah/gen/stress.py` (spec §4.2) |
| Parameter | `entry_percentile` per segment + severity `functional` (`equity` / `joint_risk` / `all_down`) |
| Estimator | None — **declared**, with precedent cited inline per scenario (spec §7). No fitting |
| Data source | Sealed panel, 1953-04→2020-12, via `campaign_source()` |
| Acceptance test | Spec §6.1: bit-exact real rows, whole-row blocks, determinism, coherence-vs-panel. Commit order (§7) proves the rule preceded any portfolio measurement |
| Ablation arm | Same seeds with `entry_percentile: 100` (unrestricted) on every segment — the severity contribution is the measured delta against that arm, per world |

## TR-2 — Persistence rule · PROPOSED · ⚑ D-SC-1

| field | value |
|---|---|
| Layer | Generator — same module, spec §4.3(d) |
| Parameter | Form P1 / P2 / P3 and its constants — **owner decision, not taken** (spec §11) |
| Estimator | None for P1/P2 (declared shape). P3's bound must be **precedent-derived** (Japan post-1990, UK 1973–75 real, US 1966–82 real) and committed before any portfolio measurement |
| Data source | Sealed panel; precedent episodes for the bound |
| Acceptance test | Realised stressed-state duration distribution reported against the cited precedent episodes; P3 additionally requires the rule-1 policing note in spec §4.3(d) satisfied (bound never adjusted against ladder readings) |
| Ablation arm | Persistence rule off, entry rule unchanged, same seeds — separates episode-depth from decade-length contributions |

## TR-3 — State-dependent secondary haircut · PROPOSED (today: fixed 0.19, LIVE)

| field | value |
|---|---|
| Layer | Institution — `src/ah/port/engine.py` `Policy.secondary_haircut` |
| Parameter | `h(state)` over the crisis→normal range **0.46→0.07** (today a constant 0.19, the 2022-H2 anchor) |
| Estimator | Fitted to the published secondary-discount range by market state |
| Data source | Nadauld et al., *JFE* (secondary-market discounts, crisis ≈46% to normal ≈7%) |
| Acceptance test | Fitted `h(state)` reproduces the published range at its endpoints; AND the Phase 0 invariance holds — incidence unchanged on worlds with zero events (`2026-08-14-stress-phase0-attribution.md` §4: the parameter prices distress, it must never create it) |
| Ablation arm | Fixed 0.19, same seeds — isolates the pricing effect on ladder severity readings from the incidence, which must not move |

## TR-4 — Split forced-sale definition · LIVE

| field | value |
|---|---|
| Layer | Institution — `src/ah/play.py` (`forced_sale_quarters` vs `forced_secondaries`) |
| Parameter | The definition itself: routine liquid funding is never reported as distress; only liquid-exhausted secondary sales count |
| Estimator | None — definitional |
| Data source | — |
| Acceptance test | `tests/test_play.py`'s schema-bound maximal world keeps the mechanic reachable and covered (forced secondaries on 10 of 11 seeds); the Reckoning card states the count it measured |
| Ablation arm | Not applicable to a definition; the falsifier is the maximal-world test failing (mechanic dead) or a surface conflating the two counts (caught by the play tests' naming discipline) |

## TR-5 — International pool · BLOCKED · ⚖ D-SC-4

| field | value |
|---|---|
| Layer | Data — a new panel source, upstream of the generator |
| Parameter | Which countries/spans enter the eligible pool (Japan post-1990, UK 1973–75 real, Germany, advanced-economy panel) |
| Estimator | — (blocked before design) |
| Data source | ⚖ **Unresolved.** The JST non-commercial correction of 2026-08-14 (`requirements.yaml`, CC BY-NC-SA 4.0) sits upstream of ALL international-panel work. **Counsel before any data enters the repo.** Pooled-disaster rationale: Barro & Ursúa; Barro & Jin |
| Acceptance test | To be written with the design — must include splice/proxy provenance per the Step-1 discipline |
| Ablation arm | US-only pool, same rule — the pool-widening contribution measured, never assumed |

## TR-6 — Exit hysteresis (`public-0.2-exit`) · PRECEDENT

The episode this register exists because of, as stated in the A7 directive: an
exit-hysteresis mechanism in a `public-0.2-exit` linkage was an undeclared
regime mechanism, and it made WP3.10 §8's "no regime term" acceptance test
("adding a crisis dummy adds no significant explanatory power") vacuous — the
regime behaviour lived in the hysteresis, where the dummy could not see it.

**Repo-state note, recorded rather than resolved:** the committed tree carries
`linkage_version public-0.1` only; no `public-0.2-exit` artifact exists in the
tree or its history as of v0.1 of this register. The precedent is recorded on
the owner's statement. If/when an exit-hysteresis linkage lands, it enters as a
full TR row — declared regime mechanism, its own estimator, an acceptance test
that can actually see it, and a hysteresis-off ablation arm — or it does not
enter.

## TR-7 — Severity/incidence separation · REGISTER-WIDE INVARIANT

- **Severity is estimated** — fitted, with bands, per the rows above.
- **Incidence** — how often the library serves a stressed world — is a
  **curation choice**, driven by DN-7 action spread and pedagogical value. It
  has no probabilistic content and must never acquire any by accident.
- **The two never merge.** If severity implies a low hazard and the library
  serves stressed worlds far more often without saying so, the product has
  attached an implied probability to a scenario — breaching "not a forecast"
  by accident rather than by decision.
- **Test:** the serving ratio is stamped in the RunRecord; the disclosure goes
  on the world card; a check compares the two and flags divergence. (Spec §8.)

---

*Rows are appended, never silently edited; a mechanism's row changes only with
a dated note. Companion to the stress-compiler design v0.2.*
