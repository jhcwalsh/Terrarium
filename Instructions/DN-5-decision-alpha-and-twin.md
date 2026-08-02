# DN-5 — Decision Alpha and the Counterfactual Twin

*Draft v0.2 · August 2026 · Closes the three sub-decisions left open by Documentation Register Amendment A2 §4, plus two that only become visible once the first is taken. Blocks D-03, the outcome-card renderer, the leaderboard sort and the post-game annotation screen.*

**Changes from v0.1.** The private sleeves have two decision levers, not zero — commitment pacing and voluntary secondary sale — and v0.1 wrongly fixed the twin's pacing schedule, which removed the main lever allocators actually pull. §2.1 is rewritten around both levers and the twin now flexes pacing under its own band. §3 is reframed: the twin is not *fooled* by smoothing — bands are the designed accommodation for stale marks — it is **systematically late in one direction**, which is a different and more defensible claim. §5.4 is new and covers the pacing-lag artefact in the decomposition.

---

## 1. What this note settles

Amendment A2 ratified that the counterfactual is inaction. That was the easy half. Four things remain undefined, and every player-facing surface consumes at least one of them:

| | Question | Ratified here |
|---|---|---|
| **A** | Does the twin rebalance? | **Policy twin, bands on public sleeves.** Drift retained as a computed third line |
| **B** | Rebalance off reported or true values? | **Reported** |
| **C** | Costs | **Net of a fixed turnover charge, applied symmetrically** |
| **D** | Decomposition | **Sequential chain-link.** Telescopes exactly to the terminal difference |
| **E** | What does the twin do about privates? | **Flexes commitment pacing to the policy private weight, under its own band. No voluntary secondary sales — those are discretionary and player-only** |

---

## 2. Decision A — the policy twin

Two twins are available and they measure different things.

| | **Drift twin** | **Policy twin** |
|---|---|---|
| Behaviour | No action of any kind | Policy weights maintained within bands; no discretionary action |
| 2022-shaped decade | Becomes overweight privates, faces its own forced sales | Trims public risk to restore weights, holds more cash |
| Difficulty to beat | Easier | Harder |
| Measures | The value of acting at all | The value of acting *differently from the policy* |
| Institutional realism | Low — no board runs zero rebalancing | High — the SAA with bands is the actual default |

**Ratified: the policy twin.** It is the thing that would genuinely have happened in the player's absence, which is the only defensible meaning of a counterfactual. It is also the harder benchmark, and a benchmark that is easy to beat makes a positive score meaningless.

**The drift path is still computed and stored.** It is the third line on the post-game analysis screen, and the divergence between drift and policy is the rebalancing lesson delivered for free — the player sees what maintaining a policy is worth before seeing what their own decisions were worth.

### 2.1 The two private levers

Privates cannot be rebalanced in the way public sleeves can, but the decision surface is not empty. There are exactly two levers, and they are very different instruments:

| Lever | Speed | Cost | Available to |
|---|---|---|---|
| **Commitment pacing** — how much new capital is committed each year | Slow. Bites 2–4 years out, through the call schedule | Free | Player **and** twin |
| **Voluntary secondary sale** — selling existing NAV before its natural life | Immediate | Discount to NAV | **Player only** |

**Pacing is a policy instrument; a secondary sale is a judgement call.** That distinction is what allocates them. A pacing plan exists to hold the private allocation near its policy weight over time — it is the SAA expressed in commitment terms, and an institution that kept committing on schedule while forty percent overweight would not be following its policy, it would be ignoring it. Selling privates at a discount, by contrast, is a discretionary act taken under pressure, and no policy document mandates it.

**Ratified: the policy twin flexes its pacing.** Annual commitments are scaled toward the policy private weight, subject to a pacing band, computed on reported values like everything else. The twin never sells privately in the secondary market voluntarily; it reaches the secondary market only through the WP3.9 forced-sale waterfall, on the same terms as the player.

```
target_commitment_t  =  base_pace × g( w_policy_priv − w_reported_priv,t )
```

with `g` clipped to a floor and ceiling — the twin does not stop committing entirely, and it does not double up. The floor matters: a twin that cuts to zero in a drawdown reproduces the single most-criticised allocator behaviour of 2009 and would make the benchmark easier to beat for the wrong reason.

**The drift twin keeps the fixed nominal schedule.** That is now the substantive difference between the two twins on the private side, and it is a genuine lesson in its own right: the divergence between drift and policy pacing across a decade is the whole vintage-timing argument, delivered without anyone having to make it.

### 2.2 The twin still ends up overweight, and this is a feature

Neither lever is fast. Pacing bites years later; the twin cannot sell. So the policy twin *still* becomes overweight privates in a drawdown — it simply arrives there having sold liquid assets to slow the drift and having throttled new commitments that will not help for another three years.

That is not a modelling compromise. It is the actual position an institution running its policy faithfully found itself in, and it means the twin is not an escape from the liquidity story but a differently-positioned participant in it.

### 2.3 The twin carries a full parallel state

Not a weight vector. The twin runs its own WP3.9 spine: cash account, calls, distributions, spending off its own reported values, its own commitment schedule under §2.1, and its own forced sales when the waterfall fails. Forced-sale count for the twin is stored alongside the player's, because "you were forced to sell and the twin wasn't" is a more interesting sentence than either number alone.

---

## 3. Decision B — rebalance off reported values

**Ratified: reported.**

Institutions rebalance off the values in their books, and those books contain smoothed private marks. The same reasoning already governs the spending rule in WP3.9 §5, and it must govern this too.

A twin rebalancing off true values would be a portfolio no institution could actually run, and beating it would measure clairvoyance rather than judgement.

### 3.1 The twin is not fooled — it is systematically late

It would be wrong to say the policy twin is deceived by smoothing. Bands are the *designed* accommodation for stale marks: a policy that traded on every appraisal wobble would churn expensively and to no purpose, and the deadzone is there precisely because reported private values are known to be noisy and lagged.

The claim that survives is narrower and sharper. **A band is a symmetric deadzone, and it absorbs noise around a level. Appraisal smoothing in a drawdown is not noise — it is a persistent one-directional bias**: reported private weight understates true private weight for several consecutive quarters. A deadzone does not correct a bias, it delays the response to it.

So the twin is not deceived. It is *late, in one direction, for as long as the smoothing lasts, and exactly when lateness is expensive.* That is not a flaw in the twin — it is a faithful reproduction of what governance-as-designed actually delivered, which is what makes it the right benchmark.

⚑ *Note for D-03: this is what gives decision alpha something real to measure. A player who mentally de-smooths acts before the reported weight has moved enough to trip the band. Seeing through the reported plane earlier than the policy does is a skill, it is the skill the reported/true toggle exists to teach, and it should be named explicitly rather than left as an unexplained edge.*

---

## 4. Decision C — costs

**Ratified: net of a fixed turnover charge, applied symmetrically to player and twin.**

Gross scoring rewards churn, and churn is one of the behaviours the product exists to expose. Charging it makes the tradeoff real.

| Parameter | Default | Note |
|---|---|---|
| `cost_public_bps` | 10 bps of traded notional | Freeze in the model parameter register |
| `discount_forced_secondary` | WP3.9 forced-secondary haircut | Unchanged; applies to player and twin alike |
| `discount_voluntary_secondary` | **Shallower than the forced haircut** | New. A seller who is not under duress transacts better, and collapsing the two would make voluntary sale strictly dominated and therefore never chosen |
| `pacing_change_cost` | Zero | Changing commitment pace has no transaction cost. Its cost is entirely opportunity cost, and the decomposition already captures that |
| Applies to | Player rebalances, twin band rebalances, twin pacing changes, all forced and voluntary sales | Symmetric wherever both sides have the action |

Costs are disclosed in D-03 as a single sentence with the number in it. A player who cannot see the cost assumption cannot interpret a small negative alpha.

---

## 5. Decision D — the decomposition

The post-game annotation screen and the Step-5 decision-density work both consume a *per-window* contribution. Defining decision alpha terminally and decomposing afterwards does not work, so the decomposition is the definition.

### 5.1 Construction

Fix world *w* and seed *s*; the revealed path is identical for every evaluation below. Let decision windows be *k = 1…K*, the player's action vector **a** = (a₁…a_K), and π the policy.

Define the **hybrid terminal value**

```
H_j  =  V( a_1 … a_j ,  π_{j+1} … π_K )
```

— the player's actual decisions through window *j*, the policy thereafter. Then

```
H_0  =  twin terminal value          (policy throughout)
H_K  =  player terminal value        (player throughout)
```

Decision alpha and its window contributions are

```
A    =  ( H_K − H_0 ) / H_0
c_j  =  ( H_j − H_{j−1} ) / H_0
```

and because *H₀* is a constant divisor,

```
Σ_{j=1..K} c_j  =  A     exactly
```

The telescoping identity is the reconciliation requirement from A2 §4.3, satisfied by construction rather than by adjustment. No residual term, no unexplained remainder on the annotation screen.

### 5.2 Compute cost

*K + 1* evaluations of the same seed. Two already exist — *H_K* is the completed run, *H₀* is the twin — so a ten-window decade needs **nine additional deterministic replays** at run completion.

Each replay is the full engine including the WP3.9 spine, and it is cheap because nothing is generated: the path is fixed, only the portfolio and cashflow recursions re-run. But it is a server-side compute line for ranked mode that is not currently in any estimate, and it should enter the cost model in the launch strategy §8 before beta.

### 5.3 Order dependence — disclose, do not fix

The construction attributes any interaction between window 3 and window 7 to the earlier window. Shapley values remove the arbitrariness at 2^K cost, which is unaffordable and would in any case produce contributions that do not correspond to any path the player could have taken.

Sequential attribution has the compensating virtue of matching how the player experienced the decade: each contribution answers *"what did this decision add, given everything I had already done?"* — which is the question the annotation screen is actually asking.

**This goes in D-03 in one plain sentence.** An interaction effect discovered by a sceptic is a problem; one stated in the interpretation guide is a methodological choice.

### 5.4 The pacing-lag artefact — true, but it will look like a bug

Pacing is a slow steering wheel. Cutting commitments in year 4 barely moves NAV in year 5; it changes capital calls two to four years out and its effect on terminal value accumulates from there. In a ten-year decade, a pacing change made in year 8 has almost no room to act before the run ends.

The decomposition will therefore report something like `Year 8, cut pacing 40%: +0.1 points`. That number is **correct**. But a player who took a deliberate, well-reasoned action and got approximately zero back will conclude the engine ignored them, and will be more likely to conclude it than to conclude that late pacing changes do not work.

Three responses, all cheap:

1. **Name it in D-03** as its own line, not a footnote to the decomposition. *"Pacing decisions taken late in a decade will score near zero. This is the finding, not a failure to measure it."*
2. **Annotate it in the post-game screen** where a pacing action scores below a threshold: a short note that the action's effect falls mostly outside the simulated horizon.
3. **Let the help agent answer it directly.** This is exactly the class of question the agent exists for, and the *c_j* series plus a lag explanation produces a genuinely instructive answer.

Worth stating plainly: this artefact is one of the more valuable lessons in the product. The gap between when a pacing decision is made and when it does anything is the single most under-appreciated feature of private-markets allocation, and a decade-length simulation makes it visible in a way a spreadsheet does not.

---

## 6. Bindings

Versioned in WorldSpec/engine config and disclosed in every RunRecord, so any published score records what produced it:

```
twin_definition            policy | drift
twin_bands                 per-sleeve tolerance, e.g. ±3pp absolute
twin_rebalance_basis       reported | true
twin_tradeable_sleeves     public only
twin_pacing_rule           flex | fixed
twin_pacing_band           deadzone on the private weight gap before pacing responds
twin_pacing_floor_ceiling  clip on the commitment multiplier, e.g. [0.25, 1.75]
twin_voluntary_secondary   false
cost_basis                 cost_public_bps,
                           discount_forced_secondary,
                           discount_voluntary_secondary,
                           pacing_change_cost
decomposition_method       sequential_chain_link
decision_alpha_version     1.0
```

`twin_pacing_rule = fixed` reduces the policy twin's private behaviour to the drift twin's, which is what makes the reduction test in §7 meaningful.

Any change to any of these is a changelog entry against A2 §4 and invalidates leaderboard comparability across the boundary. Leaderboards are already scoped to `(world, challenge_seed)`; they must additionally be scoped to `decision_alpha_version`.

---

## 7. Acceptance tests

| Test | Expectation |
|---|---|
| **Telescoping** | Σ c_j = A to floating-point tolerance, every run |
| **Null player** | A player taking no action in any window scores exactly 0.0, and every c_j is exactly 0.0 |
| **Drift reduction** | Bands set to infinity, `twin_pacing_rule = fixed`, costs zero → policy twin reproduces the drift twin bit-for-bit |
| **Pacing convergence** | Under a flat market with no player action, twin pacing converges to a stable commitment level holding the private weight at policy |
| **Pacing floor** | The commitment multiplier never leaves `twin_pacing_floor_ceiling`, including in the deepest scripted drawdown |
| **Pacing lag** | A pacing cut in the final two windows produces a *c_j* near zero, per §5.4 — asserted as expected behaviour, so a future change that makes it large fails the test rather than passing silently |
| **Secondary ordering** | `discount_voluntary_secondary` is strictly shallower than `discount_forced_secondary`; a run in which voluntary sale is never advantageous under any scripted world flags a parameter error |
| **Determinism** | Same seed, same actions → identical contributions across replays |
| **Symmetry** | Twin band rebalances incur the same bps as player rebalances; verified by an audit of the cost ledger |
| **Sign sanity** | In a scripted world with a known drawdown, de-risking in the preceding window yields a positive c_j |
| **Spine consistency** | The twin's cashflow path satisfies every WP3.9 §10 invariant independently |
| **WP3.7 reconciliation** | Zero commitments, zero spending, zero costs → contributions match a pure return-path calculation |

The null-player test is the one that catches most implementation errors, and it should run on every build.

---

## 8. Open — does not block D-03

**Policy extraction for the private leaderboard.** The Kaggle-style private score (plan §11.2) evaluates a policy across many draws of the same world. But the player's decisions were *conditioned on the path they saw* — "de-risk in year 4" is a date-stamped action, not a rule, and replaying it against a different draw is not well defined.

Two candidate resolutions, neither taken here:

1. **Date replay.** Apply the same actions at the same dates regardless of what happens. Simple, defensible, and unfair in a way players will notice.
2. **State-triggered extraction.** Infer the trigger conditions from the observed decision and re-apply them. Better, and considerably harder.

This blocks the private leaderboard, not the public one, and can be decided during Phase B. It should be flagged in the interpretation guide as a known limitation of the private score rather than resolved silently.

**Pacing parameter defaults.** The functional form of `g`, the pacing band width, and the floor/ceiling clip are not set here. They should be calibrated so that the twin's steady-state coverage lands near the WP3.10 §5 anchor of unfunded/NAV ≈ 0.5, and the calibration is a WP3.9 parameter-register exercise rather than a design decision. **Owner: Quant, alongside the §4 cost defaults.**

---

## 9. What this produces on each surface

| Surface | Consumes |
|---|---|
| Outcome card | *A*, expressed in points, with mode badge and `decision_alpha_version` |
| Leaderboard | *A*, sorted; scoped to `(world, seed, decision_alpha_version)` |
| Post-game annotation | *c_j* per window, chess-style: *"Year 4, de-risked: −2.1 points"*, with the §5.4 lag note on late pacing actions |
| Analysis screen | Three lines: player, policy twin, drift twin |
| Help agent | Answers *"why did I underperform the twin?"* by reading the *c_j* series — the single best explanatory moment in the product, and it exists only because the decomposition is the definition |
| Step 5 research | *c_j* across players and worlds is the decision-density dataset |

---

*Not investment advice. Generic parameters; not representative of any institution's policy portfolio, rebalancing discipline or cost experience.*
