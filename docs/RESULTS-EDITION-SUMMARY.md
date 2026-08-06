# Results edition — closing summary

*Task 2 + addendum, completed 2026-08-05 on branch `docs-results-edition`.
Companion to `docs/D-05-methodology-note.md` v0.3 and
`docs/P1-specified-world-models-preprint.md` v0.3. No battery was executed for
this work; every number is read from a recorded artifact.*

---

## 1. Slots filled

| Slot (D-05) | Filled with | Standing |
|---|---|---|
| §6 `[[G2 SLOT — the results table]]` | Five-gate enforce table with margins, both systems | pre-registered |
| §6 memorisation `[[nearest-neighbour floor]]` | `nn_distance_p05` 0.5541 ≥ 0.0279; `p50` 1.3918 ≥ 1.0371; `membership_inference_auc` 0.4237 ≤ 0.75 | pre-registered (report severity) |
| §6 benchmark `[[report outcome, either way]]` | PROMOTE, per-seed, all three seeds; pooled −0.3157 ± 0.0265 | pre-registered |
| §6 discriminability `[[against pre-registered ceiling]]` | 0.0310 — **no ceiling exists**; reported descriptive | descriptive |
| §6 TSTR `[[against limit]]` | `tstr_degradation` 1.0846, `predictive_score` 0.5302 — **no limit exists** | descriptive |
| Footer `[[x.y]]` / `[[range]]` / `[[id]]` | v0.3; WorldSpec 1.2.0–1.3.0; `eval-battery-0.1` + `battery-0.1` | — |

P1 gained §8 (five subsections), Figures 8–9, an abstract paragraph, and result
sentences in two §10 limitation entries. Sections 8–11 renumbered to 9–12.

## 2. Slots left open, and why

| Slot | Why it stays open |
|---|---|
| Six of seven Step-0 panel statistics — kurtosis, skewness, Hill index, `acf_abs_lag1`, drawdown median, correlation distance | Never observed. Rule 5 forbids a battery run while gates are `todo`. Carried in D-05 as *"awaiting post-ratification battery run; thresholds ratification recommended 2026-08-05"* |
| Tail backtest errors vs bounds (figure) | The 209 tail metrics are `report` severity against bootstrap bands, not errors against sealed bounds. There is no bound to plot against. Deferred per Ruling 5 |
| Stylised-fact panel vs real-data reference (figure) | Same reason as the six unobserved statistics |
| `[[link D-03]]`, `[[D-06]]`, `[[D-07]]`, `[[D-10]]`, TERRARIUM-Bench, literature map | Cross-references to documents not in this repository. Not results slots; D-05's header note was corrected to say so |

## 3. Per-gate pre-registration determination, with git evidence

Organised by the two-battery split (Ruling 1).

### Generator battery — pre-registered

| Gate | Determination | Evidence |
|---|---|---|
| Five enforce gates | pre-registered | `pre-registration.lock` first sealed `1b9e0ac` 2026-07-26 ("seal the pre-registration -- thresholds and the code that judges them"); operative seal `81f37ab` 2026-08-02 |
| Memorisation bounds | pre-registered | Same lock; bounds at `pre-registration.yaml:2824-2826` |
| Kill criterion | pre-registered | Rule sealed in `multi_seed_decision_rule`; verdict `artifacts/campaign2/promotion-verdict.json`, `created_at 2026-08-02` |
| Holdout | pre-registered | Spec sealed `AM-2026-08-02-006`; one generation, one token, one table |
| Episode 2022 (Step 3) | pre-registered | `G1-EVIDENCE.md`: "sealed at G3-pre BEFORE any of the judged code existed" |
| Step-5 decision metrics | pre-registered | `eval/decision_metrics.py` frozen at wp5-00; in `pre-registration-g5.lock` |
| `discriminative_score`, `predictive_score`, `tstr_degradation` | **no threshold** — descriptive | Sealed at `severity: report`, `band: null`. Recorded values carry `passed: null` |

**Ruling 2 resolution — the condition is met.** `prereg_verified` is a mechanical
content-address check, not a manual flag. `ah/eval/battery.py:910-915` sets it
`True` only after `prereg.verify(..., lock_path=...)` returns; `_verify_lock`
(`prereg.py:1283-1305`) resolves every path in the lock's `hashed_files`,
recomputes a SHA-256 over their contents read fresh from disk, and appends an
error if it differs from the stored digest. All six campaign-2 cells record:

```
prereg_digest    sha256:e50e18f300aba8ddff306a0811928c000edbb439931a0749d7fa4e6897f85d92
prereg_verified  true
criterion_bearing true
```

identical to `pre-registration.lock`'s `digest`. Campaign-2 therefore reports as
**pre-registered**, and both documents carry the footnote Ruling 2 requires,
including the same-date disclosure.

**One qualification, disclosed in both documents.** The cells carrying the digest
live under `experiments/`, which is gitignored (`.gitignore:42`). The linkage is
verifiable where the artifacts exist, not from the published tree.
`artifacts/campaign2/promotion-verdict.json` — which *is* committed — does not
itself embed the digest. Committing the six `battery.json` files would close
this, and is the single cheapest improvement to the evidence chain.

### Stylised panel — descriptive, gates open

| Gate | Determination | Evidence |
|---|---|---|
| All seven | **post-hoc / pending ratification** | `battery/thresholds.yaml` has exactly one commit, `4340dbc` 2026-07-24, never modified; all seven `status: todo`. File header: "placeholders documenting intent, not ratified thresholds" |
| `acf_r_lag1` specifically | observed **before** ratification | Band drafted 2026-07-24; statistic observed 2026-08-04 (`docs/engine-realism-register.md` §ER-5) |

**Recommendation (Ruling 4.2) — not executed, it is a human ratification act.**
Ratify the six unobserved statistics now. Only `acf_r_lag1` has ever been
observed; the other six are still blind, so pre-registration for six of seven is
preserved by acting and forfeited by waiting. Once ratified, a battery run
becomes permissible under rule 5 and the open slots close as genuine
pre-registered results.

## 4. Where the results sit uncomfortably with the documents' existing claims

The addendum asked specifically whether the `acf_r_lag1` miss, read alongside
RFR-66, places tension on any sentence in D-05 §6 or P1's abstract. It does, on
four. They are quoted.

**(i) P1 §6, on what pre-registration fixed — two of its six items were not fixed.**

> "numeric pass/fail thresholds can be fixed in advance: tail-index tolerance bands, autocorrelation profile distance for absolute returns, **discriminative-score ceilings, train-on-synthetic-test-on-real degradation limits**, value-at-risk and expected-shortfall backtest error bounds, and a memorisation floor."

Both emphasised items were sealed at `severity: report` with `band: null`. The
sentence is defensible as a claim about what specification *permits* — and that
is how §6 argues — but it reads as a list of thresholds that exist. Resolved in
v0.3 by a following sentence pointing at §8.4, which reports which were sealed
with a bound and which were not. The sentence itself is unchanged.

**(ii) D-05 §6, the same promise in practitioner register — this one was a plain overstatement.**

> "Discriminability | Can a trained classifier tell synthetic paths from real ones? [[G2: report score against pre-registered ceiling]]"
> "Train-synthetic, test-real | Does a model trained on synthetic data still work on real data? [[G2: report degradation against limit]]"

There is no ceiling and no limit. A reader filling these slots naively would
have invented two thresholds. v0.3 states this in bold in the results table
rather than quietly reporting the numbers.

**(iii) P1's abstract, on the battery's scope — true of one battery, not both.**

> "Three further properties follow: **pre-registered validation against a battery fixed before any model was trained**; contract versioning of every specification; and bit-for-bit replay of every run."

Accurate for the generator battery. The stylised panel was drafted before
training too — but never ratified, and its one observed statistic was observed
before any ratification could occur. The singular "a battery" conceals a split
where one side supports the claim and the other cannot. v0.3 extends the
abstract's final paragraph rather than altering this sentence.

**(iv) D-05 §1 and §6, on the tests as the reader's protection.**

> "The architecture is our proposal; **the tests are your protection.** Both are documented, and the tests were fixed before the models were trained (§6)."

The strongest sentence in the document, and the results qualify it in three
directions at once: the enforce surface is five statistics rather than the
battery's full breadth; the decade tier claims no pass and its negative control
does not fail; and two advertised tests have no threshold. The sentence is not
false — the five gates are real, sealed, and could have failed — but "your
protection" is narrower than a reader would assume. §6.1 now states the
narrowness directly. **This is the sentence to revisit if only one is revisited.**

### Two further tensions, outside the addendum's question

**(v) RFR-66 and the promotion, read together — and the re-run that answers it.**
The pre-registration records that the head-to-head is biased toward promotion,
and the promotion happened. Neither document previously mentioned it; both now
quote it wherever the kill-criterion outcome appears, framed per Ruling 3 as the
discipline catching its own thumb on the scale in advance.

*Correction made during this work.* An earlier draft of this summary asserted
that no re-run on the common window had been performed. That was wrong.
`G2-EVIDENCE.md` §3.3 carries exactly the re-run the seal binds it to, and the
result runs the other way from what the bias would predict:

| challenger | mean d (full sample) | mean d (restricted 1990–2020) | pooled beat, restricted |
|---|---|---|---|
| `hier-diffusion-v1` | −0.227085 | −0.266537 | yes |
| `hier-flow-v1` | −0.296723 | −0.363470 | yes |

The promotion survives the restriction and the margin widens, so the verdict is
not an artifact of the benchmark's data window. These are the G2-era numbers at
vintage `2026-07-26.1`, distinct from the campaign-2 figures reported in §8.3 of
the paper. Both documents now carry this alongside the RFR-66 disclosure —
reporting the bias without reporting the test that addresses it would have
overstated the problem in the opposite direction, which is the same failure
mode as flattering it.

**(vi) The engine the results describe is not the engine the product runs.**
Every number in §8 and §6 comes from `hier-flow-v1`. Every playable world runs
`toy-v0.3`, and `hier-flow-v1` is unreachable from any product path
(`docs/BUILD-SUMMARY.md` §5.1). Both documents describe one system. A reader of
D-05 §2's replay guarantee and §6's battery results could reasonably conclude
the validated generator produces the decades they play. It does not. Neither
document says so, and neither was asked to in this pass — but it is the largest
gap between what these documents describe and what the repository does.

## 5. Provenance for everything above

| | |
|---|---|
| Generator | `hier-flow-v1`, campaign-2 checkpoints, `c6addb5420723e59…512f9873` |
| Benchmark | `bootstrap-v1` |
| Vintage | `2026-08-02.4` |
| Seed | `20260727` (seed index 0 of three; per-seed table covers all three) |
| Ensemble | 1024 paths × 120 months |
| Battery | `eval-battery-0.1` (generator), `battery-0.1` (stylised panel) |
| Pre-registration digest | `sha256:e50e18f300aba8ddff306a0811928c000edbb439931a0749d7fa4e6897f85d92` |
| Sources | `experiments/campaign2/cells/{F-hier-flow-v1,B-bootstrap-v1}-s{0,1,2}/battery.json`; `artifacts/campaign2/promotion-verdict.json`; `G2-EVIDENCE.md`; `RESEARCH-EVIDENCE.md`; `G1-EVIDENCE.md`; `docs/engine-realism-register.md` §ER-5; `pre-registration.yaml` / `.lock` |
| Read | 2026-08-05 |
| Battery executions performed | **none** |
