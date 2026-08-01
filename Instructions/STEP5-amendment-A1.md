# STEP5-RESEARCH-PLAN — Amendment A1
## Deltas from the liquidity-spine session · July 2026

*Amends the Step 5 plan. Two additions, no removals. Both consume objects that now exist earlier in the build; neither adds engine work.*

---

## Delta 1 — RQ4: the practitioner discrimination study

The I2 blinded-decade exercise (MPP Amendment A1) is designed to publication standard from the outset: seed-selected stimuli, identical rendering across arms, pre-committed answer key by repo hash, confidence ratings, free-text failure reasons, W11 reviewer present.

Step 5 formalises it as a research question:

**RQ4 — Can experienced allocators distinguish generated decades from historical ones, and what betrays the generated ones?**

- **Contribution.** A human-discrimination benchmark for synthetic macro-financial paths. TimeGAN's discriminative score with practitioners as the classifier — a test no vendor in the MSCI/Burgiss class has published, and a natural component of TERRARIUM-Bench. The free-text failure taxonomy is arguably the more valuable output: it is a map of what current generative evaluation batteries do not measure.
- **Extension beyond the internal I2.** The pre-seal run uses one rater and diagnostic framing. The Step 5 version recruits 10–20 external practitioners (the CFA-adjacent network and consultant contacts are the natural pool), which converts a wide-interval anecdote into a reportable result and doubles as high-credibility marketing with the exact target audience.
- **Honesty requirement.** Report the confidence interval; pre-register the analysis; publish the rendering protocol so the blinding is auditable. If practitioners *can* reliably discriminate, that is a publishable negative result and a build input, and it must be reported rather than shelved.

## Delta 2 — RQ5: commitment policy as the decision-density instrument

WP3.9 v0.2 makes commitment policy a scored decision against a mechanical-pacing twin. This is a sharper research instrument than allocation decisions, for a structural reason: commitment errors compound over 5–7 year lags, so their cost is only observable at decade horizon — precisely the horizon that distinguishes this engine from every shorter simulator. The instrument and the platform's core claim are the same thing.

**RQ5 — Do simulated multi-decade experiences change commitment behaviour, and in which direction?**

- **Design.** Within-subject across worlds: measure pacing-plan adherence, flinch incidence (commitment cuts following drawdowns), and their measured cost, across a player's first N worlds. The behavioural signature of interest is whether flinch incidence falls with experience — and, critically, whether any reduction reflects *better* outcomes or merely *bolder* behaviour.
- **This is where the simulated-experience caveat is confronted, not just disclosed.** The existing literature measures increased risk-taking, not improved decisions. Commitment policy is unusually well suited to separating the two, because the engine prices both failure modes: under-commitment through a drawdown (the flinch) and over-commitment into one (the opposite error) both carry measurable decision-alpha costs against the same twin. A treatment that merely emboldens players will show up as reduced flinching *and* increased blow-ups from over-commitment; a treatment that improves decisions shows the first without the second. That asymmetry is the paper's identification, and it addresses the methodology gap the working paper has been advised to handle proactively.
- **Data.** The public product's ranked runs generate the panel at zero marginal cost, subject to the consent and analytics framing in the sharing spec §12 — add the research-use disclosure to the M4 counsel review list now rather than retrofitting consent later.

## Housekeeping

- The decision-density paper's methods section gains the twin-policy definition (mechanical t=0 pacing) with its D9 changelog reference — reviewers will ask why that counterfactual and not an adaptive one, and the answer ("it defines the cost of flinching, which is the behaviour under study") belongs in the paper, not in a rebuttal.
- Robinson–Sensoy joins the Step 5 bibliography; RQ5's flinch construct should cite finding 4.1 (the distribution-side mechanism) so the behavioural claim rests on the corrected mechanism, not the folk one.
- Both RQs consume the `--inspect` renderer (WP2R.4) for figures; no new figure pipeline.

---

*Not investment advice.*
