# G2 reviewer packet

**For:** the reviewer of record (decision `S2-REVIEWER-OF-RECORD`).
**Prepared:** 2026-07-31, before any holdout evaluation and before any verdict is computed.
**Status of the work:** the one-shot holdout has **not** been touched. No `FinalEvaluationToken`
has been minted, nothing imports `ah.eval.g2`, and every read to date goes through
`DataAccess.train_val` on campaign vintage `2026-07-26.1`.

---

## 0. Read this part first

You are the reviewer of record, and **you are not independent of this work**. That is a
recorded decision, not an oversight (`S2-REVIEWER-OF-RECORD`), and `G2-EVIDENCE.md` is
required to state it plainly rather than let the phrase "independent reviewer" imply an
outside party. The review below is therefore weaker than an external one. It is what is
available, and disclosing its weakness is the mitigation.

**What you are being asked to do:** weigh one post-hoc amendment against the results it
makes adjudicable, and say whether the promotion it enables may proceed to the holdout.
This gates everything downstream — the holdout is spent once and never again.

**The conflict, stated before the evidence rather than after it.** The amendment corrects a
defect that, uncorrected, would have forced an automatic SHIP-BENCHMARK verdict regardless
of any evidence. It was found *after* the results existed, and it was found by the party
who benefits from the correction, at a moment when it was already visible that the
challenger was winning. Nothing in this packet disposes of that. It is the thing you are
being asked to weigh.

---

## 1. The amendment: `AM-2026-07-29-001`

*Full text: `governance/amendment-log.yaml`. Defect-class record: `governance/retrofit-register.md` RFR-76.*

### The defect

The sealed `multi_seed_decision_rule.tail_tier_definition` defined the comparison set as

> the five `d4_strategies` minus `reference_run.uncomputable_d4_strategies`, **which on this
> vintage is `sixty_forty`, `momentum` and `carry`**

The field it glosses, `reference_run.uncomputable_d4_strategies`, is
`[eqw_factors, endowment_proxy]`. **The gloss named the complement of the field it glossed.**

### Why it is not inert

| | comparison set | consequence |
|---|---|---|
| **Reading the FIELD** (what the code does) | `{sixty_forty, momentum, carry}` — all computable | the rule executes and a challenger can win |
| **Reading the GLOSS literally** | `{eqw_factors, endowment_proxy}` — both NaN in all 18 cells | `beats_definition`'s NaN rule makes **no seed a beat for any system, ever**: an automatic SHIP-BENCHMARK independent of all evidence, for all time |

The amendment adopts the field's reading.

### Three confirmations that the field is right

1. The sealed field itself reads `[eqw_factors, endowment_proxy]`, and it is the field — never
   this prose — that `ah/eval/ablation.py`'s `comparison_set()` reads.
2. The same sealed document, `rationale.d4_commodities_consequence`, has said since 2026-07-26
   that `eqw_factors` and `endowment_proxy` are the two uncomputable strategies and that the
   other three are where every sealed `thresholds.strategies` entry lives.
3. WP2.10's measurements: in all 18 grid cells, `sixty_forty`, `momentum` and `carry` carry
   finite `elicitability_score` values; `eqw_factors` and `endowment_proxy` are NaN in every one.

Points 1 and 2 were committed **before any generator existed**, so the adopted reading was not
invented after the fact.

### What moved, and what did not

One clause of prose, plus an in-document record of the correction beside it. **No threshold,
band, gate, floor, split, ensemble size, severity, selection weight or rule text moved. No code
changed.** The lock moved `sha256:2531904623db…` → `sha256:e5a669cf156a…` only because
`pre-registration.yaml` is itself hashed; the hashed file set is unchanged at 32 files.

### What the standing checks missed

`tests/test_prereg.py::test_the_sealed_tail_tier_definition_matches_the_registered_statistics`
— the machine check the sealed sentence itself points at — **could not have caught this**. It
asserts that the definition names the eleven per-strategy and two per-pair statistics, that
`uncomputable_d4_strategies` is a proper subset of `d4_strategies`, and that the subtraction is
non-empty. It never compares the prose's *enumeration* against the field's *value*, and all five
strategy ids appear elsewhere in the same folded block. The `claims_with_tests` registry does not
reach the clause either: it carries none of the sealed trigger phrases.

---

## 2. What the correction makes adjudicable

*Source: `ABLATION.md` §6, generated from the 18-cell grid. Reported, not adjudicated — `ah/eval/g2.py` executes the rule at WP2.11.*

`d_s` is (challenger − benchmark) mean elicitability difference at seed `s`; more negative is
better. The pooled route is a beat iff `mean_s(d_s) < 0` **and** `|mean_s(d_s)| > sd_s(d_s)`.

| challenger | d(s0) | d(s1) | d(s2) | mean | sd | pooled beat | beats every seed | clause (ii) every seed |
|---|---|---|---|---|---|---|---|---|
| `abl-a-structure-only` | 0.4121 | 0.4122 | 0.4128 | 0.4124 | 0.0004 | **no** | **no** | yes |
| `abl-b-neural-rollout-flow` | −0.2437 | 0.4051 | −0.2064 | −0.0150 | 0.3643 | **no** | **no** | **no** |
| `abl-c-neural-only-flow` | 0.1281 | 53.1004 | 0.3878 | 17.8721 | 30.5089 | **no** | **no** | **no** |
| `hier-diffusion-v1` | −0.2391 | −0.2172 | −0.2249 | −0.2271 | 0.0111 | yes | **no** | **no** |
| **`hier-flow-v1`** | **−0.2779** | **−0.3044** | **−0.3079** | **−0.2967** | **0.0164** | **yes** | **yes** | **yes** |

**The sealed disclosure that cuts the other way.** `bootstrap-v1` can only resample 1990–2020,
while a challenger fitted on the full train+validation span has seen 1929–33, 1937, 1973–74 and
1987 — and both are scored against the same realizations. The head-to-head is therefore **biased
toward promotion** by a mechanism unrelated to generator quality. The seal binds the evidence
document to report the comparison restricted to the common window:

| challenger | mean d (restricted 1990–2020) | pooled beat |
|---|---|---|
| `hier-diffusion-v1` | −0.2665 | yes |
| **`hier-flow-v1`** | **−0.3635** | **yes** |

The promotion **survives the restriction** — it does not depend on the wider data window.

---

## 3. What has happened since the amendment, that a reviewer should know

- **`RFR-80`** — a governance row I wrote overclaimed that two of the decade-tier's three
  blocking causes were "discharged by the work". Not established, and for one of them
  contradicted by the tree. Corrected by appending, same day.
- **`RFR-81`** — the sealed disclosure itself misdescribes the repository's data layer: it says
  closing the valuation gap needs "a new `requirements.yaml` series", but `shiller.cape` has been
  registered since Step 1. Only the *factor mapping* is missing, and that needs an amendment plus
  a full retrain. Decision `S2-VALUATION-FACTOR` completes G2 on the sealed 14 factors.
- **Three findings of the same shape in a row** — a sealed gloss misstating a sealed field
  (RFR-76), a register row misquoting a sealed modality (RFR-80), a sealed sentence misdescribing
  the data layer (RFR-81). None was catchable by `claims_with_tests`, which verifies that a named
  *test* exists, not that a stated *fact* is true. **This is the most important systemic finding
  in the packet**, and its fix is unowned.
- **The severe test on `hier-diffusion-v1`** (running now) has produced a real signal:
  `severe:s1` returns **8 `money_pump_violations`** where its full-sample control at the same
  training seed returns 0. One seed of three so far. It does not touch the verdict — the severe
  test is evidence, not a gate (`S2-SEVERE-GATING`) — but it is a genuine robustness finding, and
  it emerged from an arm I predicted would be uninformative.

---

## 4. The questions actually being put to you

1. **Is the field's reading the correct one?** If yes, the amendment is a correction. If you think
   the gloss should have governed, the verdict is SHIP-BENCHMARK regardless of evidence, and that
   is a defensible position — it is what the sealed document literally said.
2. **Does the timing invalidate it?** The correction was made by the beneficiary, after the benefit
   was visible. Weigh that against: the field and its supporting rationale were committed before
   any generator existed, and no number moved.
3. **Does the draw-span bias change your answer?** The promotion survives the restricted window,
   but the seal requires the bias to be weighed, not just reported.
4. **May the holdout be spent?** It is spent once. Everything downstream is irreversible.

## 5. What happens on approval

The diffusion severe arm finishes → the one-shot holdout is evaluated through the explicit-purpose
path, once, logged → `ah/eval/g2.py` executes the sealed rule → `G2-EVIDENCE.md` is generated with
this packet's disclosures included → model cards → `v0.2.0-g2`.

**A SHIP-BENCHMARK verdict remains a successful outcome of Step 2**, by the plan's own design and
by the seal's own words. Nothing in this packet should be read as arguing for a promotion.
