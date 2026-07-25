*DESIGN NOTE DN-1.1 · JULY 2026 · FEEDS DECISIONS D2/D3 AND THE PHASE 1–2 BUILD · REV 1.1: FLOW MATCHING CO-PRIMARY, GUIDANCE CONDITIONING, SBI UPGRADE PATH*

# The Multi-Year Macro-Financial Generator

*How to simulate credible decades — the approach for the non-expert (Part I) and the technical design (Part II)*


## PART I — THE APPROACH, FOR THE NON-EXPERT


### The problem in one chart

Our platform must generate plausible *decades* — ten-year joint paths of rates, inflation, equities, credit and more. The difficulty is not a shortage of financial data; it is a shortage of **decades**. A century of monthly data contains over a thousand independent monthly observations — ample for a machine-learning model to learn how markets move month to month. But that same century contains only about ten non-overlapping ten-year periods, and it is precisely decade-scale phenomena — inflation eras, lost decades, long valuation cycles — that a multi-year simulator must capture. No AI model can genuinely *learn* ten-year dynamics from ten examples; one that appears to has merely memorized the twentieth century. Nor does the obvious workaround help: generating month 1, then month 2 from month 1, and so on ("rollout") lets tiny errors in each step compound over 120 steps into drift that the data can never discipline. This is why the research literature's honest verdict — echoed in our own review — is that one-shot long-horizon deep generation remains an open problem [1].


> *[Figure — gn_f1_samples.png]* Figure 1 — The heart of the matter: 103 years of monthly data (1,236 observations) collapses to roughly 10 independent samples at the ten-year horizon. Whatever governs decades must come mostly from economic structure and long-panel priors, not from pattern-learning.


### The idea: climate, seasons, weather — and careful joinery

Meteorologists faced the same dilemma and solved it with hierarchy: nobody forecasts the weather in 2035 hour by hour; instead, physics-based climate models project slow variables, and separate techniques "downscale" them into realistic local weather. We propose the same division of labor for markets, in four layers (Figure 2). **The climate**: a small set of slow economic states — trend inflation, the economy's neutral interest rate, an equity valuation level, a credit-cycle gauge — evolved by transparent economic equations (things drift back toward anchors; policy rates track inflation trends; expensive markets earn less over the long run), estimated statistically on more than a century of macro-financial history [2]. **The seasons**: a skeleton of economic regimes — expansions, recessions, crises, stagflations — whose likelihood and persistence depend on the climate (recessions are likelier when credit is stretched; stagflations persist when trend inflation is high). **The weather**: here, and only here, the modern AI enters. Generative models — the same family as today's image generators, adapted to financial series [3,4] — produce short blocks of a few months' joint market movements, conditioned on the current regime and climate. At this timescale the data are rich (thousands of examples per regime), and these models demonstrably excel at what statistics call the "stylized facts": fat tails, volatility that clusters, correlations that spike in crises [5,6]. **The joinery**: rather than chaining weather blocks forward and hoping, the climate and seasons first set *waypoints* — the year-by-year skeleton of each decade — and the AI fills in the monthly path *between* the waypoints, a task ("conditional infilling") at which diffusion models are naturally excellent. Errors cannot compound down the decade because the decade's spine is pinned by the interpretable layer (Figure 3).


> *[Figure — gn_f2_layers.png]* Figure 2 — The four-layer architecture. Reading down: structure gives way to learning exactly as the data become dense enough to support it.


> *[Figure — gn_f3_bridge.png]* Figure 3 — Why joinery beats rollout (illustrative simulation). Left: step-by-step generation lets small biases compound into decade-scale drift. Right: the same monthly randomness, bridged between structurally determined waypoints — realistic texture, disciplined destination.


### Why these particular choices — and the pedigree behind them

None of the components is exotic; the contribution is the assembly. The layered "cascade" is the modern descendant of Wilkie's 1984 actuarial model — the ancestor of every commercial economic scenario generator [7] — with its one great weakness repaired: where Wilkie bolted simple Gaussian noise onto his cascade, we attach a learned, regime-aware, tail-faithful generator. That such neural generators can operate at regulatory scale is no longer speculative: Flaig and Junike built a GAN-based generator spanning a full insurance investment universe with results comparable to supervisor-approved internal models [8]. Getting the *tails* right by construction comes from Cont and co-authors' Tail-GAN, which makes tail risk part of the training objective itself [5]; economic guardrails built into the network (no impossible prices, rates bounded below) follow the arbitrage-free neural-SDE line of Cohen, Reisinger and Wang [9]; the small-data variant follows Buehler et al.'s signature-based generator, designed for exactly our sparse quarterly segments [10]; and controllable generation — "produce paths *given* this regime" — is now demonstrated technology [4]. One deliberate act of currency: the newest sampler family, **flow matching** — faster and more stable than diffusion, with documented robustness in low-data settings — enters the design as a co-equal candidate rather than an afterthought, and the two will compete head-to-head in the Phase-2 bake-off [13–15]. The century-long climate estimation leans on the Jordà–Schularick–Taylor macrohistory panel, built by economists precisely to study rare, slow phenomena across many countries and regimes [2]. Even the joinery has official-statistics ancestry: reconciling high-frequency series to low-frequency benchmarks is a sixty-year-old discipline (temporal disaggregation) [11]. And the choice to keep the *interpretable* layer in charge of the long run is deliberate governance design: the component hardest to defend before a risk committee is the one a human can actually read.


### What could still go wrong — the limitations, stated plainly

First, structure is a bet. If our economic equations are wrong — if the neutral rate doesn't mean-revert the way we assume, if the policy-reaction anchor mis-describes future central banks — every generated decade inherits the error. Our mitigations are to estimate the equations Bayesianly and carry *parameter uncertainty into the ensemble* (the ten thousand decades disagree about the long-run parameters, not just the dice rolls), and to vary the structural assumptions as a formal robustness grid. Second, there is an irreducible floor: no architecture manufactures information about decades that ten historical decades do not contain; what this design does is place the scarce information where it is strongest and the abundant information where it is richest. Third, regimes are human categories — the labeling scheme is itself a modeling choice we must document and vary. Fourth, validation at the decade scale can never be sharp with n≈10–14; we therefore report decade-scale comparisons with wide, honestly computed uncertainty bands, and we lean on the one genuinely severe test available: hold out an era the factors did experience (the 1970s), regenerate it from its starting climate, and compare [12]. Passing that test is this design's central empirical claim; failing it would be decision-relevant information, obtained the honest way.


---


## PART II — TECHNICAL DESIGN


### II.1 Notation and layer contracts

Monthly time index t; decade horizon T=120. Factors F ≈ 10–14 per the D2 freeze. Layer outputs and interfaces:


| Layer | Output (interface to next layer) | Estimation data | Method |
|---|---|---|---|
| L1 Climate | s_t = slow-state vector, monthly, + parameter draw θ ~ posterior | JST macrohistory 1870– (annual) + monthly panel 1926– | Bayesian state-space (NUTS); economically specified SDEs |
| L2 Seasons | regime path R_t ∈ {EXP, SLOW, REC, CRI, STAG, REF}, durations | NBER + rule-based labels on 1926– panel; hazards on s_t | Semi-Markov: duration ~ NegBin(r,p(s)); hazards via logit links |
| L3 Weather | block generator G(x | c): L-month joint factor returns, L ∈ {3,…,12} | ~1,200 monthly obs → thousands of overlapping regime-labeled blocks | Conditional diffusion (EDM-style) + signature variant; tail auxiliary loss |
| L4 Joinery | full monthly decade X (F×120) consistent with waypoints w | — | Conditional infilling + Denton-style reconciliation |


### II.2 Layer 1 — the climate model

State vector s_t = (π*_t, r*_t, g_t, v_t, L_t): trend inflation, neutral real rate, trend growth, log equity valuation (CAPE-like, demeaned), credit/leverage gap. Dynamics (Euler-discretized monthly; W independent Brownians; all κ, σ, φ, λ estimated):

> `dπ*_t = κ_π(μ_π − π*_t)dt + σ_π dW_t¹   (slow mean reversion; μ_π itself given a diffuse prior — the target can drift)`

> `dr*_t = κ_r(μ_r − r*_t)dt + β_g dg_t + σ_r dW_t²   (neutral rate tied to trend growth)`

> `i_t = r*_t + π*_t + φ_π(π_t − π*_t) + φ_c c_t + ε_t   (policy anchor: Taylor-type reaction with cycle term c from L2)`

> `dv_t = −κ_v v_t dt + σ_v dW_t³ ;  E[r_equity(10y)] = a − b·v_t   (valuation mean reversion ⇒ long-horizon return predictability)`

> `dL_t = κ_L(L_bar(R_t) − L_t)dt + σ_L dW_t⁴   (credit gap drifts to regime-dependent norm; feeds L2 hazards)`

Estimation: joint Bayesian filtering on the annual JST panel (1870–) fused with the monthly panel (1926–) via a mixed-frequency observation equation; priors per the table below; posterior sampled by NUTS. Each generated decade draws (θ, s₀) from the posterior — parameter uncertainty is inside the ensemble by construction. Identification note: v_t anchored to observed CAPE/dividend-yield composites; r* identified à la Laubach–Williams-type smoothness priors rather than point estimation. **Upgrade path (recorded, not v1):** simulation-based inference / neural posterior estimation [16] would admit richer nonlinear climate dynamics if the linear-Gaussian-ish v1 proves restrictive; NUTS on a small interpretable model is the defensible starting point precisely because a validator can read it.


| Parameter | Prior (illustrative; frozen at D-workshop) | Rationale |
|---|---|---|
| κ_π half-life | LogNormal ⇒ 8–20 yr (90% CI) | Inflation eras persist ~decade scale (1966–82, 1995–2020) |
| μ_r (neutral real) | Normal(0.75%, 0.75%) | Secular-stagnation vs pre-2000 evidence both supported |
| φ_π (reaction) | Normal(0.5, 0.25), truncated > 0 | Taylor principle favored, not imposed |
| b (valuation slope) | Normal(consistent with 10y R² ≈ 0.2–0.4) | Matches long-horizon predictability evidence |
| σ's | Half-Cauchy, weakly informative | Let the century speak |


### II.3 Layer 2 — the regime skeleton

Semi-Markov chain over 6 states. Sojourn: D | R=k, s ~ NegBin(r_k, p_k(s)) with logit p_k = α_k + γ_k′ z(s), z(s) = (curve slope, L gap, π*−target, drawdown state). Transition matrix rows also logit-linked to s (crisis hazard rises with leverage and inversion; STAG self-transition rises with π*). Fitted on rule-based labels (documented ruleset, varied in the robustness grid) + NBER dates. WorldSpec binding: mode=sequence pins R_t; mode=transition_matrix samples it; unconditional bypasses L2. Layer-2 output additionally emits the cycle term c_t ∈ [−1,1] consumed by the L1 policy anchor and by L3 conditioning.


> *[Figure — gn_f4_decade.png]* Figure 4 — One generated decade, layers visible (illustrative): the Layer-2 regime skeleton (bands), Layer-1 slow states (trend inflation, policy anchor), and a Layer 3–4 equity path threading through them.


### II.4 Layer 3 — the block generator

Target: p(x | c), x ∈ ℝ^{L×F} standardized monthly factor returns, L=6 default. Conditioning vector c = [one-hot(R), s_t snapshot, h_t = summary of trailing 12 months (returns, realized vol, spread level), Δw = waypoint increments the block must be consistent with (see II.5)]. Co-primary architectures — the G2 bake-off includes both, behind one conditioning contract: (a) EDM-style continuous-time diffusion, temporal U-Net/transformer backbone, cross-attention on c (CoFinDiff pattern [4]); (b) **conditional flow matching / rectified flow** with the identical interface — the 2025–26 sampler frontier: deterministic few-step sampling, training stability, and state-of-the-art results on time-series benchmarks including low-data robustness [13,14,15]. Loss (applies to either sampler; score- or velocity-matching term respectively): L = L_gen + λ_tail · L_VaR/ES, the auxiliary term the Tail-GAN elicitability score on the frozen D4 benchmark-strategy set evaluated on generated batches [5]. Output map: hard constraints via transformed coordinates — rates and spreads generated in softplus space with floors (i ≥ −1%, spread ≥ 100bp), prices in log space [9]. Variant for sparse segments: signature-kernel MMD generator [10] with identical conditioning interface, so L3 implementations are swappable behind one contract. Baseline (kill criterion opponent): regime-stratified stationary bootstrap sampling L-month blocks from matching (R, s-bucket) history. Training set: all overlapping L-blocks 1926– with regime and s labels (≈10³–10⁴ effective examples per regime after overlap correction via subsampled epochs).


### II.5 Layer 4 — waypoints, bridging, reconciliation

Waypoints w: per calendar year y of the decade, L1–L2 emit (i) annual means of i_t, π_t; (ii) cumulative log equity drift implied by valuation dynamics + regime path; (iii) year-end spread level band; (iv) regime path R_t itself. Generation of a decade:


| Step | Operation |
|---|---|
| 1 | Draw (θ, s₀) from L1 posterior; simulate s_t monthly for T=120. |
| 2 | Sample regime path R_t from L2 given s (or accept WorldSpec sequence). |
| 3 | Compute waypoints w(s, R) per year; apply WorldSpec factor_conditions as overrides/tilts on w (this is where authored worlds bind). |
| 4 | For each block b (length L, overlapping stride L/2): sample x_b ~ G(·| c_b) with Δw in the conditioning; blend overlaps (linear cross-fade in state space). |
| 5 | Reconcile: Denton proportional benchmarking of each factor's monthly path to its annual waypoint aggregates [11] — exact low-frequency consistency, minimal high-frequency distortion; re-apply hard floors. |
| 6 | Score the candidate decade against the fast subset of the battery (tail panel, ACF panel); reject-and-resample worst decile (importance-style acceptance, logged). |
| 7 | Map factors → strategy returns (WS-C mappings), emit RunRecord. |

Two design notes. (a) Conditioning-plus-reconciliation is belt and braces: conditioning teaches the generator to *aim* at waypoints; training-free guidance (posterior-sampling / inverse-problem style [13]) can sharpen that aim at inference time and will be evaluated as an option; Denton guarantees the books balance; the reconciliation adjustment size is itself a monitored diagnostic (large adjustments ⇒ generator and structure disagree ⇒ investigate). (b) Step 6's acceptance filter is deliberately mild (≤10%) and fully logged to avoid silent distribution-shaping.


### II.6 Horizon-stratified validation battery (extends D6)


| Horizon | Metric | Target / test | Reference data |
|---|---|---|---|
| Monthly | Stylized-fact panel: tail index, ACF |r|, skew, corr matrix; VaR/ES elicitability on D4 strategies | Pre-registered bands (D6); beats bootstrap (G2) | 1926– panel |
| 1–5 yr | Variance ratios; mean-reversion half-lives; regime duration distributions; drawdown depth/duration joint dist. | Within block-bootstrap 90% bands of history | 1926– panel, bootstrap CIs |
| 10 yr | Lost-decade frequency; long-inflation-era frequency; 10y return vs starting v (predictability slope & R²); ergodicity (long-path vs ensemble stats) | Wide-band consistency, honestly reported (n≈14) | JST + 1926– panel |
| Economic | Implied Sharpe ratios, term premium, ERP by regime; no-money-pump audit; policy-anchor sanity | Defensible ranges, documented | Literature ranges |
| Severe | Held-out-regime: train ex-1970s, regenerate from 1965 climate, compare 1966–84 factor behavior | Primary empirical claim; pass/fail written up either way | Excluded era |


### II.7 Ablation design (the publishable experiment)


| System | Composition | Question it answers |
|---|---|---|
| A Structure-only | L1+L2 + Gaussian residuals (modern Wilkie) | How far does interpretable structure alone go? |
| B Neural-rollout | L3 chained autoregressively, no waypoints | Does rollout drift as predicted? |
| C Neural-only | L3 blocks + naive chaining under sampled regimes, no L1 | Is the climate layer necessary? |
| D Full hierarchy | L1+L2+L3+L4 as specified | The proposed system |
| E Bootstrap | Regime-stratified block bootstrap end-to-end | The transparent benchmark (G2 opponent) |

All five run the full horizon-stratified battery and the held-out-regime test; decision-level evaluation (D9 walk-forward, drawdown surprise) on A, D, E at minimum. Where credibility comes from — structure, learning, or the joinery — becomes an empirical result.


### II.8 Bindings, staging, compute

WorldSpec: L1 posterior version and L2 ruleset version recorded in engine metadata; regimes.mode maps to L2 as in II.3; factor_conditions apply as waypoint overrides (II.5 step 3) — authored worlds and research worlds share one code path. Staging per the project plan: L1+L2 in Phase 1 (upgrading the calibrated factor model; independently shippable as a modern Bayesian ESG); L3 as the Phase 2 pilot with the G2 kill criterion now stated block-wise; L4 bridging Phase 2–3; ablation and held-out-regime study Phase 3 (RQ2). Compute: L1 NUTS hours on CPU; L3 single-GPU days; a full 10,000-decade ensemble minutes once trained. Decisions this note feeds: D2 (state vector + regime ruleset now part of the freeze), D3 (generator job = conditional block generation; sampler family — diffusion vs flow matching — explicitly deferred to the G2 bake-off), D5 (floors as II.4 coordinates), D6 (battery extended per II.6).


### References

[1] STORM review, §2 and §8 (this project, July 2026): one-shot long-horizon deep generation as an open problem; conditional chaining as current practice.  
[2] Jordà, Ò., Schularick, M., Taylor, A.M. — Macrofinancial History and the New Business Cycle Facts (JST Macrohistory Database, 1870–).  
[3] Wiese, M. et al. — Quant GANs: Deep Generation of Financial Time Series. Quantitative Finance 20(9), 2020.  
[4] Tanaka, Y. et al. — CoFinDiff: Controllable Financial Diffusion Model for Time Series Generation. IJCAI 2025.  
[5] Cont, R., Cucuringu, M., Xu, R., Zhang, C. — Tail-GAN: Learning to Simulate Tail Risk Scenarios. Management Science, 2025.  
[6] Cont, R. — Empirical Properties of Asset Returns: Stylized Facts and Statistical Issues. Quantitative Finance 1, 2001.  
[7] Wilkie, A.D. — A Stochastic Investment Model for Actuarial Use. TFA 39, 1984; and successors (Ahlgrim et al., CAS).  
[8] Flaig, S., Junike, G. — Scenario Generation for Market Risk Models Using Generative Neural Networks. Risks 10(11), 2022; validation companion arXiv:2301.12719.  
[9] Cohen, S.N., Reisinger, C., Wang, S. — Arbitrage-Free Neural-SDE Market Models. Applied Mathematical Finance, 2023.  
[10] Buehler, H., Horvath, B., Lyons, T., Perez Arribas, I., Wood, B. — A Data-Driven Market Simulator for Small Data Environments. SSRN 3657366, 2020.  
[11] Denton, F.T. — Adjustment of Monthly or Quarterly Series to Annual Totals. JASA 66, 1971 (temporal disaggregation / benchmarking tradition).  
[12] Research Design v1 (this project): held-out-regime backtesting protocol (RQ2).  
[13] Lipman, Y., Chen, R.T.Q., Ben-Hamu, H., Nickel, M., Le, M. — Flow Matching for Generative Modeling. ICLR 2023 (arXiv:2210.02747); incl. guidance/inverse-problem conditioning lineage.  
[14] Liu, X., Gong, C., Liu, Q. — Rectified Flow: Straight and Fast Generation. arXiv:2209.03003; FlowTS and successors for time series (arXiv:2411.07506).  
[15] PrismFlow — Residual Dynamics for Flow Matching in Time-Series Generation (arXiv:2605.28867, May 2026): current SOTA claims incl. low-data robustness; TimeFlow (SDE-aware FM) as the stochasticity-aware variant.  
[16] Cranmer, K., Brehmer, J., Louppe, G. — The Frontier of Simulation-Based Inference. PNAS 117(48), 2020 (neural posterior estimation lineage).  

---

*Markdown rendition of DN-1.1. The PDF version contains four figures (effective-sample-size chart, four-layer architecture, rollout-vs-bridging comparison, generated-decade layers) which are referenced here as figure callouts.*
