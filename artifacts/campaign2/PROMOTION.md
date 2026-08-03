# CAMPAIGN-2 PROMOTION — verdict and evidence

*Generated from `artifacts/campaign2/promotion-verdict.json`,
`configs/campaign2-checkpoints.json` and the six criterion cell artifacts
under `experiments/campaign2/cells/`. 2026-08-03.*

## Verdict

**PROMOTE** — per-seed route of the sealed `multi_seed_decision_rule`
(pre-registration.yaml; hashed into `pre-registration.lock`
`sha256:e50e18f3...`). The challenger (`hier-flow-v1`, campaign-2
checkpoints, fifteen sealed factors, vintage `2026-08-02.4`) beats
`bootstrap-v1` in EVERY seed on both clauses, and the pooled route concurs.

| seed | challenger elicit. | benchmark elicit. | d | C band exceed. | B band exceed. | beats |
|---|---|---|---|---|---|---|
| 0 | -2.5591 | -2.2131 | -0.3461 | 12 | 13 | yes |
| 1 | -2.5163 | -2.2132 | -0.3031 | 5 | 11 | yes |
| 2 | -2.5116 | -2.2139 | -0.2978 | 8 | 12 | yes |

Pooled: mean_d = -0.315650, sd(ddof=1) = 0.026473 —
mean negative and |mean| > sd, so the pooled arm is ALSO satisfied
(clause (ii) holds in every seed, as the pooled route requires).

Comparison set (sealed): sixty_forty, momentum, carry (clause i);
cross-block tail-dependence bands (clause ii). Every cell is
criterion-bearing: sealed size 1024 x 120, sealed vintage, pre-registration
verified at the campaign-2 digest.

**Both sides pass their full batteries clean** (`passed_unfiltered=True`,
zero enforce failures, all six cells) — the promotion is a comparison of
two passing generators, not a rescue.

## Checkpoints (configs/campaign2-checkpoints.json)

| key | weights sha256 | train seed | best step | best S | wall |
|---|---|---|---|---|---|
| flow:0 | `c6addb5420723e59...` | 20260728 | 4000 | -1.752265 | 775s |
| flow:1 | `2362a5e8f1862631...` | 20268647 | 4000 | -1.717820 | 796s |
| flow:2 | `3fa5471fb48ebf27...` | 20276566 | 4000 | -1.745029 | 785s |

Config: the sealed WP2.9 flow selection, `n_factors` following the sealed
campaign-2 factor set (a geometry fact, not a searched knob — the
`train_ablation_seeds.py` no-retuning discipline). Per decision C3:
`residual_drift` off, guidance 1.0. The registry pin
(`ah.gen.blocks.flow.PINNED_CHECKPOINT_SHA256` / `DEFAULT_CHECKPOINT`)
moves to `flow:0`; the G2-era artifact remains the generator of record for
G2's claims on vintage `2026-07-26.1` — superseded, not invalidated.

## Disclosures

1. **`benchmark_draw_span_bias` applies verbatim** (sealed text): the
   benchmark can only resample 1990-2020 while the challenger fitted the
   full train+validation span, and the bias direction favors promotion.
   Read the verdict with that paragraph in hand.
2. **The first battery run was INVALID and is superseded**: its reference
   omitted `resample_length=120`, drawing full-sample-length bands where
   the sealed battery is length-matched — both sides' band-exceedance
   gates exploded against bands measuring a different quantity
   (`bootstrap-v1` "failing" dependence at 0.91 was the tell). All six
   cells were rerun at the sealed parameters; only the corrected cells
   are in `experiments/campaign2/cells/` and only they feed the verdict.
3. **`criterion_bearing` does not check reference parameters**
   (RFR-96): it verifies ensemble size, vintage and the prereg digest,
   but not that the reference bands were drawn at the sealed
   `n_resamples`/`level`/`block_length`/`resample_length`. The invalid
   run above sailed through it. Closing this is a small
   `ah.eval.ablation`/battery-lineage change, registered for the next
   evaluation-layer work package.
4. The accepted 10yr-tier limits (decision C3) carry
   `Instructions/campaign2-regime-fix-options.md` as their mechanism
   trace; nothing in this promotion re-litigates them.

*Not investment advice.*
