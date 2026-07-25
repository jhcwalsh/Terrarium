# DN-2 · Hybrid Deployment for Terrarium

*Design note · July 2026 · Companion to the Master Roadmap. Specifies the hosting split, the boundaries that make it defensible, and decisions H1–H10 to be ratified alongside D1–D10.*

---

## 1. The decision

Terrarium runs as a **hybrid**: a hosted platform plane that owns models, worlds, and generation, and a client-resident institution plane that owns the balance sheet, the portfolio, and the decisions. Sensitive institutional data never leaves the client perimeter; generic model artifacts never need to.

This is chosen over full SaaS (fails institutional security review for member and position data), full client-side deployment (you lose the ability to improve models continuously, and licensed calibration data may not be shippable), and single-tenant managed hosting (all of SaaS's objections, at higher cost).

The split is already latent in the architecture: **WorldSpec in, ensemble out** is a clean interface, and the generator was deliberately built to stop at factors. Hybrid deployment is that boundary made physical.

## 2. Three planes

| Plane | Contents | Location | Why |
|---|---|---|---|
| **Control** | Model registry, world library, taxonomy and schema versions, battery and evidence packs, release catalogue | Platform | Generic; the asset you improve continuously |
| **Generation** | Climate/regime posteriors, block generator checkpoints, ensemble production, public factor panel | Platform (default) — client-side only if licensing forces it | Compute-shaped, data-generic once calibrated |
| **Institution** | Portfolio and sleeve state, cohort cashflows, twin and liabilities, member data, decisions, chronicle of their runs | **Client, always** | The material a security review actually cares about |

**What crosses the boundary.** Outbound to client: WorldSpec documents, generated ensembles (factor paths + states + provenance), model parameter bundles, world artifacts, release images. Inbound to platform: nothing by default — optional, opt-in, aggregated telemetry only (H9).

## 3. The artifact and LLM boundary — the part that makes security review easy

Split artifacts by what they depend on:

- **World artifacts** (wire items, research notes, manager letters, feature pieces) depend only on the world's tape and the World Bible. They are LLM-authored **on the platform plane, at world creation**, gated, and shipped *with* the world as static content.
- **Institution artifacts** (board packs, statements, funding updates, peer rankings) depend on client data — and are **all Tier-1 deterministic templates**. They render client-side with no external call.

Consequence, worth stating plainly to any CISO: **in the default configuration, no client data is ever sent to a language model.** The LLM sits entirely on the world-authoring side of the boundary.

The one exception is the **AI committee**, which by design reads a briefing containing institution state. Therefore: AI actors are opt-in per deployment; they call an LLM endpoint of the client's choosing (their own cloud model service, their own key); and every briefing sent is written to the client-side chronicle so they can audit exactly what left their perimeter. In restricted deployments the feature is simply off, and human committees plus the heuristic ablation still work.

## 4. Workload shapes

| Workload | Profile | Placement | Infrastructure |
|---|---|---|---|
| L1 Bayesian fitting | Hours, CPU, occasional | Platform | Batch, spot-tolerant |
| L3 training (per seed) | GPU-days, occasional | Platform | Spot GPU with checkpointing |
| Ensemble generation | Minutes, parallel, bursty | Either | Ephemeral scale-out |
| Interactive serving / live mode | Long sessions, low compute | Client | Small always-on; reveal is a read, not a simulation |
| World artifact authoring | Batch at world creation | Platform | Queued, cached |

Live mode is cheap precisely because you chose precomputed reveal: the server exposes a stored decade rather than simulating per tick. Chaptered generation is the expensive variant and stays behind its flag.

## 5. Licensed data — the binding constraint (H2)

Before any of this is final, three questions to Albourne and the other vendors:

1. May licensed series be processed in your cloud environment, and in which region, with which sub-processors?
2. May **derived parameters** — de-smoothing weights, factor betas, TA profiles — travel and be embedded in software delivered to clients, given they are not the data?
3. Does a client with their own entitlement change the answer for their instance?

If derived parameters may travel, the architecture is clean: **calibration happens once, in a controlled environment; the parameter bundle deploys anywhere.** If they may not, calibration moves client-side for affected sleeves and the platform ships code plus method rather than fitted values — workable, but it fragments calibration and weakens the "one validated model" story. Get this answered before Step 3 hardens the parameter pipeline.

## 6. Reproducibility across the boundary (H4)

The bit-identical replay promise now has to survive different machines. Two changes:

**Runtime fingerprint in the RunRecord**: container image digest, CPU architecture and relevant feature flags, BLAS/numpy/CUDA versions, GPU model where used. This is part of the model version, not metadata trivia.

**Reproduction classes**: define equivalence classes of environment within which digests must match exactly, and across which a documented numerical tolerance applies. Test both — a cross-class replay test belongs in CI. Claiming universal bit-identity across heterogeneous hardware would be a promise you cannot keep; claiming *class-identical replay with a stated tolerance across classes*, tested, is both true and defensible.

**Archive discipline**: every released image is archived, not merely tagged, alongside the checkpoints and vintages it depends on. A validator asking in 2030 to reproduce a 2027 figure needs code, artifacts, **and environment**.

## 7. Storage versus regeneration (H5)

Because every run is reproducible from seed + checkpoint + vintage + runtime, path arrays are a cache, not a record. Store the digest; regenerate on demand; cache what is hot. This converts an unbounded storage curve into a compute cost you control.

**Kept immutably, both planes:** data vintages, model checkpoints, RunRecords, chronicles, evidence packs, release images. **Retention:** set explicitly per class (recommend: evidence and RunRecords indefinite; ensembles cached 90 days; artifacts with their world).

## 8. Tenancy, security, environments

**Hosted plane:** tenant isolation at the world-library and key level; secrets management for vendor credentials and any platform-side LLM keys; prompt-injection surface reviewed anywhere authoring ingests text not authored by you; watermark enforcement on every export path — a fictional front page escaping unmarked is the genuine reputational risk, and it is an export-path property, not a style guide one.

**Client plane:** ships as a versioned release bundle, not continuous deployment (H6). Support matrix and upgrade path defined up front; upgrades must preserve replay of runs created under older versions, which is what the image archive is for.

**Environment topology (H8):** dev / staging / prod mapping to the gate structure, with model promotion and pre-registration sealing as *controlled actions* with named authority and audit logging. The person who can quietly promote a generator is the person a validator will ask about.

## 9. Enforcing the boundary in code — reuse a pattern you already have

Step 2 enforces the holdout guard with an **import-graph test**. Use exactly the same mechanism for the deployment boundary: institution-plane modules may import from generation-plane modules, never the reverse; artifact authoring that touches client state may not import the LLM client. The boundary then fails at CI rather than at a security review. Add this in Step 2R and it stays cheap forever; add it in Step 6 and it is an archaeology project.

## 10. Cost shape

Training is occasional and spot-friendly. Ensembles are minutes of CPU. Serving is trivial. **LLM spend scales with worlds, not users** — batch at world creation, cache, and the marginal cost of an additional user experiencing an existing world is near zero. This favours a product design where worlds are shared, versioned artifacts rather than per-user generations, which is also the design that makes cohort exercises and wargames work.

## 11. Honest limitations

Hybrid doubles the deployment surface — two targets, two release processes, version skew between them. You cannot observe client-side failures directly, so client-plane diagnostics must be self-contained and exportable by the client (H9). Restricted deployments lose AI actors, so that feature can never be load-bearing in the product story. And if licensing forbids parameter travel (§5), the clean split degrades and calibration fragments — the single largest external dependency on this design.

## 12. Decision register H1–H10

| # | Decision | Recommended default | Blocks |
|---|---|---|---|
| **H1** | Deployment model and component placement | Hybrid per §2 | Packaging design |
| **H2** | Licensed-data locus; may derived parameters travel? | Confirm with vendors now | Step 3 parameter pipeline |
| **H3** | LLM boundary | No client data to LLMs by default; AI actors opt-in on client-side endpoints with logged briefings | Step 4 design |
| **H4** | Runtime pinning and reproduction classes | Fingerprint in RunRecord; class-exact, cross-class tolerance, both tested | Step 2R |
| **H5** | Storage vs regeneration; retention | Regenerate paths; retain evidence/records indefinitely | Step 2R |
| **H6** | Client-plane release model and support matrix | Versioned bundles, N-2 support, archived images | Step 3+ |
| **H7** | Tenancy and isolation for the hosted plane | Per-tenant isolation at library and key level | Hosted build |
| **H8** | Environment topology and promotion authority | Dev/staging/prod on gates; named authority; audited | Governance pack |
| **H9** | Telemetry and support access | Opt-in, aggregated, client-exportable diagnostics | Client plane |
| **H10** | Archive policy for long-horizon reproducibility | Images + checkpoints + vintages archived with evidence | Governance pack |

## 13. What to do when

**Now (Step 2R):** H4 runtime fingerprint into the RunRecord; the import-graph boundary test; H2 vendor questions sent. **Step 3:** keep the institution plane structurally separable — every module placed on the correct side of the boundary from its first commit. **Step 4:** implement the artifact split (§3) as designed rather than discovered. **After G3:** packaging, release process, tenancy build. Nothing here requires infrastructure work today; it requires the boundary to be respected in code today, which is free.
