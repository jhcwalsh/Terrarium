# WorldSpec v1.0 — Specification and Governance

**Status:** Draft for adoption · **Companion file:** `worldspec-v1.0.schema.json` (normative) · **Example:** `example-long-stagflation.worldspec.json`

WorldSpec is the single contract of the Alternate Histories platform. The scenario compiler emits it, the validator stamps it, the world engine consumes it, and the experience layer displays it. Every component of the system may be replaced independently so long as it honors this document. The JSON Schema file is normative for structure and bounds; this document is normative for semantics, validator rules, and lifecycle.

---

## 1. Design principles

**One world, many runs.** A WorldSpec defines a *world* — an economic configuration. It does not record a simulation. Simulations are recorded in RunRecords (Section 5) that reference a world by `world_id` and pin the exact resolved engine version and seed. This separation is what makes "live it again" a first-class operation rather than a mutation, and what allows the same world to be re-rendered by a better engine next year without losing its identity or its audit trail.

**Narrative is display-only.** The compiler generates the story and the parameters together so they agree, but *no engine component may read the `narrative` object*. This rule is absolute. It guarantees that a world's simulated behavior is fully determined by its structured parameters — auditable, reproducible, and independent of prose — and it prevents the single worst failure mode of an LLM-fronted quant system: behavior that silently depends on wording.

**Everything the compiler did is on the record.** The verbatim user scenario, the model and prompt version that compiled it, every parameter the validator clamped (with submitted and applied values), and every coherence warning are retained in `provenance`. When someone asks, six months later, why a committee slide showed private credit losing 9% a year, the answer is recoverable from the WorldSpec alone.

**Immutability with lineage.** `world_id` is immutable. Any edit to an engine-consumed field creates a *new* world whose `provenance.source.parent_world_id` points to the original. Narrative-only edits (fixing a typo in a headline) may be made in place, precisely because narrative cannot affect the engine.

**Absence means "let the model decide."** Every field in `factor_conditions` is optional. An omitted condition is not a zero — it instructs the generator to use its learned, regime-conditional behavior. This is what separates a *conditioned* world ("inflation averages 6.5%") from an *authored* one, and it keeps compiled worlds parsimonious: the compiler should set only the conditions the scenario actually implies.

**Bounds live in the schema; coherence lives in the validator.** Single-field sanity (a loss rate between 0.2% and 10%) is enforced by JSON Schema and applied as clamps. Cross-field economic coherence (inflation at 9% with rates at 1%) cannot be expressed in a schema and is enforced by the validator rules in Section 3, which warn rather than block — the author may be describing financial repression deliberately, and the acknowledgment is recorded.

---

## 2. The layers, and who reads them

| Object | Written by | Read by | Never read by |
|---|---|---|---|
| `narrative` | Compiler (or author) | Experience layer | **Any engine component** |
| `horizon`, `regimes`, `factor_conditions` | Compiler (or author), clamped by validator | Factor generator | — |
| `structural` | Compiler (or author), clamped by validator | Factor-to-asset mapping layer | Factor generator |
| `engine_defaults` | Author / platform defaults | Run orchestrator | Compiler |
| `provenance` | Platform services only | Audit, experience layer | Compiler, engine |
| `extensions` | Anyone (namespaced `x_*`) | Opt-in consumers | Engines must ignore unknown keys |

Two structural notes on the parameter layers:

**`regimes` is the skeleton; `factor_conditions` is the flesh.** The regime layer supports three modes. `sequence` pins regimes to quarters and produces a deterministic macro backdrop — right for authored, pedagogical worlds ("crisis hits in year 2"). `transition_matrix` lets each simulated history draw its own regime sequence from a quarterly Markov chain — right for research use, where the ensemble should span macro uncertainty rather than condition it away. `unconditional` disables regime conditioning entirely and yields pure resampled history, the fidelity baseline. Factor conditions then constrain the generator *within* whatever regime skeleton applies.

**`structural.parameter_vintage` is the counterfactual switch.** This one field carries the central intellectual move of the whole platform. `historical_average` maps factor paths through the asset classes *as they were* over the calibration sample — the right setting for validation and for "what would the recorded history's PE have done in the 1970s." `current` maps through the asset classes *as they are* — today's leverage, entry multiples, market size — the right setting for forward-looking allocation. `custom` makes the sleeve-level dials authoritative for deliberate what-ifs ("PE at 7 turns of leverage with zero illiquidity premium"). A world's meaning changes materially with this switch, so the experience layer must always display it.

---

## 3. Validator rules (V-rules)

The validator runs on every compiled or edited world before it can reach `validated` status. Clamps are silent-but-recorded; warnings require display to the author and are retained with an acknowledgment flag. Rules are versioned with the validator; this list is v1.

- **V1 — Rate–inflation coherence.** If `inflation.average_pct ≥ 5` and `policy_rate.end_pct ≤ 2`: warn "Deeply negative real rates throughout — financial repression. Confirm this is intended."
- **V2 — Windows inside the horizon.** Every `crisis_windows` entry and every `peak_quarter` must satisfy `start_quarter + length ≤ horizon.quarters`. Violation: clamp to horizon end.
- **V3 — Spread geometry.** `hy_spread_peak_bps ≥ hy_spread_start_bps`. Violation: swap and warn.
- **V4 — Regime–condition agreement.** A `stagflation` regime segment with `inflation.average_pct < 4`, or a `deflation_boom` segment with `inflation.average_pct > 2`, draws a warning naming the mismatch.
- **V5 — Extreme divergence.** If `equity.drift_annual_pct ≥ 8` while `private_equity.entry_multiple_drift_annual_pct ≤ -3` (or the reverse pattern): warn "PE valuation trend runs strongly against public equity trend — plausible but unusual; confirm."
- **V6 — Crisis without stress.** A `crisis_windows` entry with `severity ≥ 0.5` while `hy_spread_peak_bps < hy_spread_start_bps + 150`: warn "Severe crisis with no credit-spread response."
- **V7 — Narrative dates inside the horizon.** Every dispatch date must fall within the horizon's calendar span. Violation: warn (narrative-only, never clamped).
- **V8 — Dispatch hygiene.** 3–10 dispatches, non-empty headlines, dates non-decreasing. Violation: warn.
- **V9 — Bounds clamps.** Any schema-bounds violation from the compiler is clamped to the nearest bound and recorded in `provenance.validation.clamps`. More than three clamps on one world: additionally warn "Compiler output required heavy clamping — review scenario interpretation."
- **V10 — Sequence tiling.** In `sequence` mode, segments must tile `[0, quarters-1]` with no gaps or overlaps. Violation: reject (this one blocks — an untiled sequence has no defined semantics).
- **V11 — Stochastic matrix.** In `transition_matrix` mode, each row must sum to 1 ± 1e-6 and the matrix must be square on `states`. Violation: reject.
- **V12 — Vintage consistency.** If `parameter_vintage` is `historical_average` or `current`, sleeve-level structural overrides present in the document draw a warning that they will be ignored; if `custom`, at least one sleeve object must be present or the world is rejected.

---

## 4. Lifecycle

`draft → validated → approved → archived`

A world is `draft` on creation, `validated` when the validator passes it (clamps applied, warnings recorded), and `approved` only after a human with the approver role signs off. Approval is required before a world may appear in the shared library, be referenced in exported material, or be run with `n_paths > 10,000`. Archived worlds remain queryable forever (RunRecords reference them) but cannot start new runs. Deletion does not exist.

---

## 5. RunRecord

The reproducibility anchor. Written by the run orchestrator; immutable.

```json
{
  "run_id": "uuid",
  "world_id": "uuid",
  "world_spec_version": "1.0.0",
  "requested_by": "sso:jwalsh",
  "created_at": "2026-07-22T18:40:11Z",
  "resolved_engine": {
    "generator_id": "conditional-diffusion",
    "generator_version": "2.3.1",
    "generator_checkpoint_sha": "b41c…",
    "mapping_version": "map-2026.2",
    "desmoothing_method": "glm_ma",
    "validator_version": "1.4.0"
  },
  "seed": 771204,
  "n_paths": 10000,
  "overrides": { "n_paths": 10000 },
  "outputs_digest": "sha256:…",
  "summary_stats": {
    "endowment_median_growth_of_100": 173.4,
    "endowment_p10_p90": [121.7, 244.9],
    "pct_histories_endowment_beats_6040": 61.5
  }
}
```

`resolved_engine` pins what actually ran, down to the checkpoint hash; `overrides` records any departure from the world's `engine_defaults`; `outputs_digest` hashes the path tensor so any retained output can be verified against the run that claims to have produced it. WorldSpec + RunRecord together regenerate any result bit-for-bit (given the same engine build) or — after an engine upgrade — regenerate the *world* under the new engine with the lineage explicit.

---

## 6. Versioning and compatibility policy

WorldSpec follows semver. **Patch** (1.0.x): documentation and validator-rule text only; no structural change. **Minor** (1.x.0): additive and optional only — new optional fields, new enum members, promotion of an `x_*` extension; every valid 1.0 document remains valid. **Major** (2.0.0): anything breaking — renamed fields, tightened bounds, new required fields — and ships with a lossless-where-possible migration function in the platform repo, applied lazily when an old world is next opened for editing (never silently to stored documents).

Engines declare a supported range (e.g. `>=1.0 <2.0`) and must refuse, with a clear error, documents outside it. Engines must ignore unknown `x_*` extensions (forward tolerance) and must never infer behavior from narrative (the display-only rule survives every version).

Compiler prompts are versioned in lockstep: any prompt change bumps `compiler_prompt_version` and must pass the ~50-scenario regression set before deployment, with diffs in compiled parameters reviewed by a human.

---

## 7. What is deliberately *not* in WorldSpec

**Portfolio definitions.** Allocations under evaluation are user/session state, not world state — the same world must be viewable through any portfolio. **Simulation outputs.** Paths and statistics belong to RunRecords and result stores; embedding them in the world document would break immutability. **Engine internals.** Network architectures, training data hashes, and hyperparameters live in the model registry, referenced by version; WorldSpec names *which* engine, not *how* it works. **Market data.** Calibration data is referenced implicitly through `mapping_version` and generator version — a world is portable across data refreshes precisely because it does not embed data.
