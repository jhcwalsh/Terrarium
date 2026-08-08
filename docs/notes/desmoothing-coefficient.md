# The de-smoothing coefficient, in normal and stressed markets

*A short note. Measured on vintage 2026-08-08.1; regenerate the numbers with
`uv run python scripts/validate_desmoothing.py`.*

## The problem it solves

A private fund's real estate does not get a price every day. It gets an
appraisal — every quarter, from a valuer who has just seen last quarter's
appraisal and a handful of comparable sales. So the reported value moves
towards the truth rather than jumping to it.

That makes private assets look calmer than they are. Their reported returns
are a *smoothed* version of their economic returns: less volatile, more
autocorrelated, and — the part that matters — slower to fall.

De-smoothing undoes that transformation to recover what the asset was
plausibly worth, as opposed to what it was written down as.

## The coefficient

For appraisal-marked assets (real estate, infrastructure) we use a partial
adjustment model. In words:

> this quarter's appraisal = **a** × (this quarter's truth) + (1 − **a**) ×
> (last quarter's appraisal)

**`a` is the fraction of the truth that makes it into the reported number.**
Its complement, **`phi` = 1 − a**, is the fraction inherited from last
quarter — the *stickiness*.

- **a = 1.0** — the appraisal is the truth. No smoothing, nothing to undo.
- **a = 0.5** — the appraisal is half truth, half last quarter's number.
- **a → 0** — the mark barely moves at all, however the world changes.

Recovering the truth is just that equation rearranged, which is what
`ah.data.desmooth.geltner_ar1` computes.

For hedge-fund-style sleeves we use a different model — a moving average of
recent true returns — because the mechanism there is return smoothing rather
than an appraisal calendar. Same intent, different shape.

## What we measure: it is not one number

The important finding is that **`a` is not a constant. It falls sharply in
stressed markets.**

Fitted separately on calm quarters and on NBER-recession quarters, pooled
across the two appraisal-marked private sleeves:

| state | `a` (truth admitted) | `phi` (inherited) |
|---|---|---|
| calm quarters | **0.96** | 0.04 |
| stressed quarters | **0.53** | 0.47 |

In normal times appraisals track reality almost fully — 96% of the move gets
through, and there is very little to undo. In a downturn barely half gets
through, and marks lean on the previous quarter instead.

We summarise the difference as a single **stickiness** parameter:

> stickiness = 1 − (a in stress ÷ a in calm) = 1 − (0.53 ÷ 0.96) = **0.45**

Zero would mean appraisals behave identically in booms and crashes. **0.45
means marks become roughly twice as sticky when markets fall.**

For comparison, the same calculation on the monthly hedge-fund sleeves gives
**0.00** — their smoothing does not change with the state of the world. Two
mechanisms, two behaviours, which is why the platform fits them separately.

## Why it matters

Appraisers anchor hardest exactly when values are falling: comparable sales
dry up, and nobody wants to be the first to mark down. So the gap between
reported and true value is *widest in the drawdown* — precisely when an
investor is deciding whether they can meet capital calls.

This is the mechanism behind the denominator effect. If your private assets
are still carried near last year's value while public markets have fallen,
privates look like a larger share of your portfolio than they are, and your
liquidity looks better than it is. A model using one constant smoothing
coefficient understates that, because it averages the sticky crisis quarters
in with the honest calm ones.

## What this is not

It is a **statistical correction, not an observation.** Nobody saw the
de-smoothed number. It is our best estimate of what the reported number was
lagging.

It also cannot find smoothing that does not show up as autocorrelation. On
the direct-lending series the estimate came back as *no correction at all* —
the series' quarter-to-quarter correlation is slightly negative, so the model
has nothing to work with. That is reported openly in the de-smoothing
validation exhibit rather than hidden behind a coefficient near 1.0.

**Related:** the *De-smoothing validation* exhibit on this console shows, per
sleeve, how much volatility the correction recovered and where a
market-priced comparator suggests it is too small.
