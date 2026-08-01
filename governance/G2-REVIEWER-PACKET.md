# G2 reviewer packet

**For:** the reviewer of record.
**Prepared:** 2026-07-31 — before the final test was run and before any verdict was calculated.
**Plain-language version.** Every claim here points to a file where it can be checked; see §8.

> ## OUTCOME — APPROVED, 2026-07-31
>
> Approved by the project owner as reviewer of record, before the holdout was opened and
> before any verdict was computed. Recorded as `S2-REVIEW-OUTCOME` in
> `governance/decision-register.md`.
>
> **The approval covers the three narrow questions in §9 and nothing else:** that the
> correction was genuine, that the benchmark's data disadvantage does not undermine the
> comparison, and that the one-shot test may be spent.
>
> **It is explicitly NOT a judgement that the results are good enough, and NOT an
> endorsement of model quality.** That question was settled in advance by the sealed rule;
> a reviewer deciding it on their own reading of the numbers — in either direction — would
> be doing the very thing the seal exists to prevent.
>
> The reviewer is not independent of the work. Both readings of the evidence stand together
> and both must be published: the challenger beats the benchmark on the pre-registered
> criterion, and neither generator is a convincing model of history.

---

## 1. Read this first

Before any model was built, this project wrote down exactly how it would judge the results —
every threshold, every rule, every definition — and sealed that rulebook cryptographically. The
point is simple: you cannot move the goalposts after seeing where the ball landed.

**A sentence in that sealed rulebook turned out to be wrong.** It was corrected. The correction
was made *after* the results were known, and by the person who benefits from it.

That is what you are being asked to weigh. Not whether the models are good — the sealed rule
decides that on its own. Just this: **was that correction legitimate, and may the project now
spend its one irreversible test?**

**Two things to be clear about before you start.**

You are the reviewer, and you are not independent of this work — you commissioned it. That is a
recorded decision, not an oversight, and the final evidence document is required to say so
plainly rather than let the phrase "independent reviewer" suggest an outside party. This review
is weaker than an external one. Saying so is the only honest mitigation available.

And nothing here argues for a promotion. If the new models lose, shipping the simple benchmark
with an honest write-up is a **successful** outcome of this stage. The project was built so that
either answer is publishable.

---

## 2. What went wrong

The rulebook defines which investment strategies the new models get compared on. It does this
twice: once as a **list** the software actually reads, and once as an **English sentence**
describing that list for a human reader.

The sentence described the list backwards. It named the strategies that were being *excluded*
as though they were the ones being *kept*, and vice versa.

## 3. Why that isn't a typo

Because the two readings give opposite verdicts.

- **Reading the list** (which is what the software has always done): the comparison runs on three
  strategies that have usable historical data. The contest happens. A challenger can win.
- **Reading the sentence literally**: the comparison runs on two strategies that have *no* usable
  historical data — and there is a rule saying that when data is missing, the challenger does not
  win that round. Applied here, no challenger could ever win any round, in any circumstance,
  no matter how good it was. **The benchmark would win automatically, forever, regardless of all
  evidence.**

So this is not a cosmetic fix. Left alone, it decides the outcome by itself.

## 4. The evidence that the list is right and the sentence was wrong

Three independent things point the same way:

1. **The software has always used the list**, never the sentence. No result produced so far was
   calculated under the wrong reading.
2. **Another passage in the same sealed document** — written on the same day, months before any
   model existed — describes the same two strategies as the unusable ones, agreeing with the list
   and contradicting the sentence.
3. **The measurements agree.** Across all eighteen experimental runs, the three strategies the
   list keeps produce real numbers; the two it excludes produce nothing, every time.

Points 1 and 2 were committed to the repository **before any model was trained**. Whatever else is
true, the reading now adopted was not invented after the fact to suit a result.

## 5. What actually changed — and the part that should worry you

**Changed:** one sentence of description, plus a note recording the correction beside it.

**Not changed:** not one threshold, limit, bound, cut-off, sample size, weighting or rule. No
software. The pass marks are exactly what they were.

**The part that should worry you.** The error was found while writing up the results — with those
results already in hand, and after it was already visible that the leading challenger was beating
the benchmark. So: *a correction that makes a promotion possible was made by the party who would
benefit from a promotion, at the moment it became clear a promotion was within reach.*

Nothing in this document disposes of that. It is recorded in full, undiluted, in the project's
amendment log, flagged as the first "made after results existed" entry in the project's history —
every previous one was made before any model was fitted. It is written down that way so you can
weigh it, rather than have it explained away.

## 6. Why no automated check caught it

There is a test that guards this exact sentence. It checks that the sentence mentions the right
statistics, and that the excluded list is a genuine subset of the full list, and that something
remains after the subtraction. **All of that was true.** What it never does is compare the names
the sentence *recites* against the names the list *contains* — and since all five strategy names
appear elsewhere in the same passage, no simple text search would have separated them either.

This is the third finding of the same shape in this project: **sealed prose asserting something
that nothing verifies against reality.** The other two were found in the last two days — a
governance note that overstated what had been delivered, and a sealed sentence that misdescribes
the project's own data holdings. The general fix is known, cheap, and currently **nobody's job**.
In my view that is the most important systemic issue in this packet, more than the amendment
itself.

---

## 7. What the correction makes judgeable

With the comparison restored, here is how the five systems did against the benchmark. Lower is
better; the test is whether a challenger beats the benchmark reliably rather than luckily, so it
must win either in *every* repeat run or by a margin clearly larger than the run-to-run noise.

| system | result |
|---|---|
| structure-only (no neural component) | **loses** — worse than the benchmark |
| neural, no assembly stage | **inconclusive** — wildly inconsistent between runs |
| neural, no climate stage | **loses badly** — one run was catastrophic |
| full hierarchy, diffusion | **wins on the looser test**, fails the stricter one |
| **full hierarchy, flow matching** | **wins on every test, in every repeat run** |

**The catch that cuts the other way, and it is a real one.** The benchmark can only reshuffle data
from 1990–2020. The challengers were fitted on history going back to 1929, so they have seen the
Depression, 1937, the 1973–74 crash and 1987 — and both are then marked against the full record
including all of it. That advantage has nothing to do with which model is better. The sealed
rulebook anticipated this and requires the comparison to be re-run on the common 1990–2020 window
only.

**The result survives that restriction** — the leading challenger's margin actually widens. So the
win does not depend on the unfair data advantage. It still needs to be weighed, not just noted.

## 8. Other things you should know before deciding

- **A stress test found something real.** We hid the 1970s from the models entirely, retrained,
  and asked whether they could still produce 1970s-like decades. For the flow model, the answer
  was inconclusive — the test couldn't tell the trained-with from the trained-without apart. For
  the diffusion model, one of three runs produced **eight internal-consistency violations**
  (paths that would allow a riskless profit — something that should never occur), where the
  identical model trained on the full history produced none. That is a genuine robustness
  finding. It does not affect the verdict, which is computed only on the main experiments. One
  further run is still in progress and will show whether it is systematic or a fluke.
- **The decade-scale measurements are unusable and always were.** Sixteen of twenty-two are dead
  for want of inputs that were never built. This is declared in the sealed rulebook, and the
  evidence document is forbidden from claiming a pass there.
- **A related discovery this week:** the sealed rulebook says closing that gap needs new data.
  It doesn't — the data has been in the repository since the first stage. What's missing is
  wiring it into the models, which needs a rule amendment and a complete retraining. You've
  already decided to finish this gate on the current setup and do that next time round.

## 9. The questions actually being put to you

1. **Was the list the right reading?** If yes, this was a correction. If you think the sentence
   should have governed as written, then the benchmark wins automatically and that is the verdict —
   a defensible position, since it is what the sealed document literally said.
2. **Does the timing spoil it?** It was corrected by the beneficiary, after the benefit was
   visible. Weigh that against: the supporting evidence predates every model, and no number moved.
3. **Does the benchmark's data disadvantage change your answer?** The win survives correcting for
   it, but the rulebook asks you to weigh the bias, not merely note it.
4. **May the final test be spent?** It runs once, ever. Everything after it is irreversible.

## 10. What happens if you approve

The stress test finishes → the held-back data is opened and evaluated, once, logged → the sealed
rule computes the verdict → the evidence document is generated, carrying every disclosure in this
packet → model records are written → the release is tagged.

**If the answer comes back "keep the benchmark", that is a successful outcome**, by the plan's own
design and the rulebook's own words.

---

## 11. Where to verify any of this

| claim | file |
|---|---|
| The amendment, in full, with the timing recorded | `governance/amendment-log.yaml` — `AM-2026-07-29-001` |
| Why the guarding test could not catch it | `governance/retrofit-register.md` — RFR-76 |
| The other two findings of the same shape | `governance/retrofit-register.md` — RFR-80, RFR-81 |
| The full results table and the restricted re-run | `ABLATION.md` §6 and §7 |
| Every decision taken, with dates and reasoning | `governance/decision-register.md` |
| The stress test and its inconclusive reading | `artifacts/wp211/SEVERE-TEST.md` |
| The sealed rulebook itself | `pre-registration.yaml` |

**Status of the irreversible step:** untouched. The held-back data has not been opened, no access
token has been created, and every calculation so far has run on the training and validation data
only.
