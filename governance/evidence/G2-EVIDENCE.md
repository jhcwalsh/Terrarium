# G2-EVIDENCE.md — the Step 2 gate

**Verdict: PROMOTE `hier-flow-v1` over `bootstrap-v1`.**
Produced by executing the sealed `multi_seed_decision_rule` in `ah/eval/g2.py` on the
WP2.10 ablation grid. Date: 2026-07-31. Lock at the time of execution:
`sha256:99ab3f772be6a5af…`, 33 hashed files.

**Read §1 before §2.** The disclosures there are not caveats appended to a result; several
of them are reasons a reader might reasonably decline to accept it.

---

## 1. What a reader must know before reading the verdict

**1.1 The rule was corrected after the results existed, by the party who benefits.**
`AM-2026-07-29-001` corrected a sentence in the sealed decision rule that described a list
backwards — naming the strategies being *excluded* as though they were the ones kept. Read
literally, that sentence made **no challenger able to win, ever, regardless of evidence**:
an automatic SHIP-BENCHMARK independent of all data. It was found while writing up WP2.10,
with the results in hand, after it was visible that the leading challenger was winning. The
correction is in the direction that makes a promotion possible. Three things point the
other way and none of them disposes of it: the software always read the list, never the
sentence; another passage in the same sealed document has agreed with the list since
2026-07-26; and no number moved. It is the first `post_hoc: true` entry in this project.

**1.2 The reviewer of record is the project owner and is not independent of this work.**
There was no outside review. The approval (`S2-REVIEW-OUTCOME`) covers three narrow
questions — that the correction was genuine, that the benchmark's data disadvantage does
not undermine the comparison, and that the holdout could be spent — and **explicitly does
not** constitute a judgement that the results are good enough. That was settled in advance
by the sealed rule; a reviewer deciding it on their own reading of the numbers, in either
direction, would be doing what the seal exists to prevent.

**1.3 The head-to-head is biased *toward* promotion.** Sealed disclosure
`benchmark_draw_span_bias`: `bootstrap-v1` can only resample 1990-2020, while a challenger
fitted on the full span has seen 1929-33, 1937, 1973-74 and 1987 — and both are scored
against the same realizations, which include all of it. The benchmark is handicapped by its
data window, not its form. See §3.3 for the sealed restricted-window re-run.

**1.4 The one-shot holdout was NOT spent and remains unspent** (`AM-2026-07-31-002`). The
seal specified its span, its guard and its at-most-once budget, and **never specified what
the single permitted evaluation computes**. No clause of the rule reads it. Any procedure
run at WP2.11 would have been authored at WP2.11 with every other result visible. §6.

**1.5 The decade-scale tier is 73% structurally unavailable and always was.** 16 of 22
metrics are dead for want of inputs that were never built. **This document does not and may
not claim a `10yr` pass** (sealed `conventions.ten_year_tier_coverage`). §5.3.

**1.6 The seal had a hole for two days.** `ah/eval/ablation.py` — the code computing the
verdict arithmetic — was created outside the sealed set and went unhashed from 2026-07-29
to 2026-07-31 (`AM-2026-07-31-001`, RFR-82). It was verified unchanged across that window
(one commit ever touched it; the diff is empty), so the results rest on the bytes now
sealed. That is evidence after the fact where the seal exists to give design before it.

**1.7 Seven governance defects of one class were found in three days.** §7. The seventh is
the record of the fifth. This is the most important systemic finding in the document.

---

## 2. The verdict

`PROMOTE` requires **all four** clauses. Executed per challenger against `bootstrap-v1`,
three seeds each, on criterion-bearing runs only (1024×120, vintage `2026-07-26.1`).

| system | clause 1 tail | clause 2 enforce | clause 3 memorization | clause 4 constraints | **verdict** |
|---|---|---|---|---|---|
| A `abl-a-structure-only` | ✗ | ✓ | ✓ | ✓ | SHIP-BENCHMARK |
| B `abl-b-neural-rollout-flow` | ✗ | ✓ | ✓ | ✓ | SHIP-BENCHMARK |
| C `abl-c-neural-only-flow` | ✗ | ✗ | ✓ | ✓ | SHIP-BENCHMARK |
| D `hier-diffusion-v1` | ✗ | ✓ | ✓ | ✓ | SHIP-BENCHMARK |
| **D `hier-flow-v1`** | **✓** | **✓** | **✓** | **✓** | **PROMOTE** |

**`hier-flow-v1` becomes the default `generator_id`.** `hier-diffusion-v1` remains
registered and reachable but is not the default, per `S2-DEFAULT-GENERATOR` — a decision
taken *blind*, before clauses (2)–(4) were adjudicated, resolving the sealed rule's silence
on a both-pass outcome by awarding the default to whichever system clears clause (1) on the
stricter route.

**A SHIP-BENCHMARK verdict would have been a successful outcome of Step 2**, by the plan's
design and the seal's own words. It is stated here because four of five systems earned one.

---

## 3. Clause (1): tail superiority

### 3.1 The arithmetic, full sample

`d_s` = (challenger − benchmark) mean `elicitability_score` over the comparison set
{`sixty_forty`, `momentum`, `carry`} at seed `s`. Lower is better; more negative `d` is a
larger win.

| challenger | d(s0) | d(s1) | d(s2) | mean | sd (ddof=1) | every seed | pooled route |
|---|---|---|---|---|---|---|---|
| `abl-a-structure-only` | 0.412119 | 0.412229 | 0.412796 | 0.412381 | 0.000363 | no | no |
| `abl-b-neural-rollout-flow` | −0.243710 | 0.405117 | −0.206384 | −0.014992 | 0.364304 | no | no |
| `abl-c-neural-only-flow` | 0.128121 | 53.100376 | 0.387810 | 17.872102 | 30.508856 | no | no |
| `hier-diffusion-v1` | −0.239116 | −0.217233 | −0.224907 | −0.227085 | 0.011103 | no | **no** — see 3.2 |
| **`hier-flow-v1`** | **−0.277918** | **−0.304350** | **−0.307900** | **−0.296723** | **0.016381** | **yes** | **yes** |

`hier-flow-v1` carries clause (1) on **both** routes: it beats the benchmark in every seed
*and* pooled by more than the cross-seed dispersion. Cross-seed consistency is tight — the
three differences span 0.03 against a mean of −0.30.

### 3.2 Where this document and `ABLATION.md` appear to disagree, and why they do not

`ABLATION.md` §6 reports `hier-diffusion-v1` as a pooled beat. This document reports its
pooled route as failing. **Both are correct.** That table reports "pooled beat" and "clause
(ii) every seed" as independent columns; the sealed `beats_definition` combines them:
*"Clause (ii) must still hold in every seed for the pooled route — the pooled arm relaxes
the objective, not the band-regression check."* `hier-diffusion-v1` fails clause (ii) in
every seed, so its pooled route fails. The executor implements the sentence, which is why
it was composed from the sealed words rather than from the generated table.

### 3.3 The restricted-window re-run the seal requires

`benchmark_draw_span_bias` binds this document to report the comparison restricted to the
1990-2020 realizations both generators' scores are computed against.

| challenger | mean d (full) | mean d (restricted 1990-2020) | pooled beat, restricted |
|---|---|---|---|
| `hier-diffusion-v1` | −0.227085 | −0.266537 | yes |
| **`hier-flow-v1`** | **−0.296723** | **−0.363470** | **yes** |

**The promotion survives, and the margin widens.** It is therefore not a promotion of a
data window. Neither number gates — the sealed rule is the sealed rule — but the bias was
weighed, not merely noted.

---

## 4. Clauses (2)–(4)

- **(2) No enforce-tier regression** on the `monthly` and `1_5yr` tiers relative to
  `bootstrap-v1`. The sealed sentence admits a by-count and a by-metric reading; both are
  computed, and `holds` is their conjunction (the stricter). **They agree on every cell of
  the grid**, so nothing turns on the ambiguity here. Narrowing it belongs in a dated
  amendment taken before results exist, not in this work package.
- **(3) Memorization below floor** — every memorization-tier enforce threshold passes in
  every seed, for `hier-flow-v1`. Absolute, not relative: the benchmark resamples history
  verbatim and is not the standard.
- **(4) Zero constraint violations** — `money_pump_violations` and `floor_violations` are
  exactly 0 in every judged seed.

**Negative controls.** The battery's ability to detect badness at all is evidenced by
`ah/eval/negative_controls.py` and its sealed table. One exemption is sealed and narrow:
NC5 is not caught at enforce in its designated conditional tier (`S2-NC5-EXEMPTION`) but is
still blocked, by `near_duplicate_fraction`. **The `10yr` tier caught nothing** — see §5.3.

---

## 5. Diagnostics, reported and non-gating

### 5.1 Support

`hier-flow-v1`, judged cells: extrapolation share 0.876–0.883; 1006–1009 of 1024 decades
flagged off-support. **This is high and is disclosed rather than explained away.** The
support diagnostic is the sealed tripwire for off-support conditioning, and a reader should
weigh clause (1) knowing the generated decades sit largely outside the conditioning support
seen in training. `bootstrap-v1` has no comparable figure — it does not condition.

### 5.2 Conditional tier

Reported, **not gating**, per the sealed `conditional_tier_is_not_gating`, whose rationale
is that the platform's purpose weighs conditioning but historical tail fidelity remains the
falsifiable criterion at G2. Revisit at G3.

### 5.3 The `10yr` tier — unavailable, not passed

16 of 22 metrics are `STRUCTURALLY_UNAVAILABLE` for every generator: 14 `ergodicity_gap`
(no generator emits a path longer than its horizon) and both
`ten_year_return_vs_valuation_*` (no valuation factor is mapped). A third cause, the
regime-duration inputs, is unverified. **`nc2-shuffled`, whose time ordering is destroyed
outright and which is designated to this tier, produces zero substantive failures in it.**
A generator whose decade-scale behaviour was wrong while its monthly behaviour was right
would not be caught anywhere. This document claims no `10yr` pass.

**Discovered 2026-07-31 (RFR-81):** the sealed text says closing the valuation gap needs a
new data series. It does not — `shiller.cape` has been registered since Step 1. Only the
*factor mapping* is missing, which needs an amendment plus a full retrain.
`S2-VALUATION-FACTOR` completes this gate on the sealed 14 factors and defers that to the
next campaign.

---

## 6. The severe test — INCONCLUSIVE, in both families

Protocol: exclude 1970-01-01..1979-12-31 from the fitting sample, refit L1 and L2, retrain
L3 at frozen architecture and hyperparameters, regenerate from the 1965 climate state,
compare 1966-1984. Six criterion-bearing cells per family, three training seeds, both arms.

| | `hier-flow-v1` | `hier-diffusion-v1` |
|---|---|---|
| severe closer to history on | 18 of 35 | 17 of 35 |
| median contrast / pre-existing gap | 6.4% | 7.9% |
| long inflation era frequency (severe / primary) | 0.441 / 0.424 | 0.413 / 0.380 |
| inflation mean-reversion half-life | 30.0 / 29.7 | 27.7 / 26.8 |
| equity drawdown median depth | 0.034 / 0.034 | 0.042 / 0.044 |

History: long inflation era frequency **1.000** — every 120-month window of 1966-84 *was*
one. Half-life **61.2**. Drawdown depth **0.069**.

**Not a pass:** neither arm reproduces the era, in either family. **Not a fail:** the severe
arm is not materially worse than the primary — a coin flip. **Inconclusive:** the contrast
the test exists to expose is ~6–8% of a gap that is already there with the decade *in* the
sample.

**This reading is a human judgement, not a computed outcome** (`S2-SEVERE-GATING`, RFR-77):
the sealed protocol pins no decision threshold, so no rule produced it. The severe test
enters this document as evidence, **not as a gate**.

**Three findings from it that do not depend on the judgement:**

1. **The L3 leg is structurally vacuous — 0 blocks dropped, in both families.** The L3
   training panel *is* the sealed block draw span 1990-2020, which never reaches the 1970s.
   The test asks whether a slightly different L1 posterior changes what the block model
   learns, **not** whether removing the 1970s changes the blocks. The blocks are the same
   blocks.
2. **The exclusion's one robust footprint is identical across both families to four
   decimals.** Regime-frequency TV distance: primary 0.3267 / 0.3266 / 0.3265, severe
   0.3407 / 0.3405 / 0.3401, in *both* flow and diffusion. Two entirely different L3 models
   producing the same number six times over is only possible if the quantity is generated
   wholly upstream of L3 — which demonstrates, rather than infers, that the footprint comes
   from the regime layer losing 17 of its 129 sojourns. Extrapolation shares, an L3-level
   property, *do* differ between families, exactly as the architecture predicts.
3. **One enforce failure in twelve cells.** `severe-diffusion-s1` returned 8
   `money_pump_violations`; every other cell in both families returned 0, and its
   full-sample control at the same training seed is clean. **One seed in three** — at that
   count, "the exclusion makes violations more likely" and "that checkpoint was bad" are
   indistinguishable. Reported as suggestive, not conclusive.

**`bootstrap-v1`'s row on this protocol is NOT ANSWERABLE, not "not run".** Its draw span
contains neither the excluded decade nor the 1965 start state, so the question cannot be
posed of it.

**The holdout was not spent** (§1.4). What a later gate must do to spend it: write the
evaluation down first — what is generated, at what size, from what conditioning state,
scored on which metrics against which realizations, with what consequence — seal that
specification *before* the campaign it judges, then mint the token.

---

## 7. Limitations and open defects

**A defect class found seven times in three days: the seal asserts or assumes something
nothing mechanically verifies.**

| id | finding | status |
|---|---|---|
| RFR-76 | sealed gloss naming the complement of the sealed field it glossed | fixed (`AM-2026-07-29-001`); general check unowned |
| RFR-77 | sealed protocol pinning a procedure but no criterion | unowned |
| RFR-78 | sealed prose naming a tier the code does not define (110 vs 113 metrics; both reported) | unowned |
| RFR-81 | sealed prose misdescribing the repository's own data layer | unowned |
| RFR-82 | **a hole in the seal itself** — the verdict arithmetic unhashed for two days | fixed (`AM-2026-07-31-001`); class unowned |
| RFR-83 | a sealed guard with no sealed test behind it (the holdout) | unowned |
| RFR-84 | RFR-82's own record contained two false statements, both of this class | corrected; class unowned |

The cheapest fixes are known and mechanical: an import-graph test that every module
reachable from the judging entry points is sealed or explicitly excluded; a resolver for
every tier, suite, metric, series and factor name appearing in sealed prose; and a citation
checker over `governance/*.md` extended to bare filenames as well as `file::test` pairs.
**None is owned.** Seven instances in three days, the last written by the person cataloguing
the other six, is evidence that this is not a discipline problem.

**Carried forward from earlier work packages:** `commodities` unsourced and two D4
strategies therefore uncomputable (RFR-8); uncommitted-capital numeraire bias in three D4
strategies (RFR-12); pooled-statistic band length mismatch (RFR-15); `run_battery` reference
desync undetected on the low-level path (RFR-16); the `10yr` tier (RFR-42, §5.3).

**Process deviations, recorded:** WP2.10 and WP2.11 share a branch against the
one-work-package-per-branch convention (`S2-BRANCH-DEVIATION`) — not split, because a
committed governance record cites a commit by hash and rewriting published history would
strand it.

---

## 8. What this verdict does and does not mean

**Does:** `hier-flow-v1` becomes the default `generator_id` for Step 3's work, having beaten
the pre-registered benchmark on the pre-registered criterion, in every seed, on both routes,
surviving the sealed correction for the benchmark's data disadvantage.

**Does not:** assert that the platform is fit for real decisions. Neither generator is a
convincing model of history. Both call 1966-84 a long inflation era under half the time when
every window of it was one; both understate drawdowns roughly twofold; both invent stagnant
decades at 0.29–0.75 against a historical 0.00–0.05; and the tier that would catch
decade-scale error is three-quarters dead. Fitness for decisions is Step 5's question.

---

## 9. Reproduction

| artefact | path |
|---|---|
| the sealed rule, in words | `pre-registration.yaml` → `multi_seed_decision_rule` |
| its executable form | `src/ah/eval/g2.py` (hashed) |
| the arithmetic | `src/ah/eval/ablation.py` (hashed since `AM-2026-07-31-001`) |
| the grid and its tables | `ABLATION.md`, `artifacts/wp210/` |
| both severe arms | `artifacts/wp211/SEVERE-TEST.md`, `SEVERE-TEST-DIFFUSION.md` |
| every amendment, dated | `governance/amendment-log.yaml` |
| every decision, dated | `governance/decision-register.md` |
| every deferred defect | `governance/retrofit-register.md` |
| the reviewer packet | `governance/G2-REVIEWER-PACKET.md` |
| model cards | `governance/model-inventory.yaml` |

Lock at execution: `sha256:99ab3f772be6a5afc665c8e51364dc477c34c2cd0b5cf959f3446e401b21d832`,
33 hashed files, sealed 2026-07-31.
