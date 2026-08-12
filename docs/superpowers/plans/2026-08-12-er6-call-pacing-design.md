# ER-6 close-out — the call-pacing curve, fitted or declared (DRAFT for owner review)

> **Status: APPROVED — D1 ratified by the owner 2026-08-12: "A plus C"**
> (the declared mid-band curve, plus the expiry-undrawn ledger line).
> A release event per the realism register. Prepared after the
> su-generated-worlds plan closed: generated worlds inherit ER-6 whole
> (survey S3: the arithmetic is age-driven, generator-independent), and
> ER-6 is the named prerequisite for the commitment lever (E1), the game's
> most distinctive decision.

## The defect, restated

`rc_curve = [0.25, 0.30, 0.20, 0.12, 0.08, 0.05]` — annual call rates on the
*remaining unfunded* balance, indexed by cohort age and clamped to the last
entry — was always a placeholder: register kind E, sourced from an ALB-A
delivery that never arrived. A declining rate on a shrinking balance
compounds to **~29% of every commitment never called by year 10** (26.3% is
the pure-curve number; tier-1's near-flat `f_call` drag adds the rest)
against a practitioner expectation of **85–95% called**. Downstream,
`peak_unfunded_ratio` reads 2.4–3.3 against a declared band of 0.25–0.75 and
flags on every world, the J-curve crossover lands late or never, and the
commitment lever would teach against a counterfactual that does not behave
like a real programme.

## What a fix invalidates — smaller than the register feared

The pacing arithmetic lives in `ah/port/cohort.py` + the parameters file,
consumed only by the PLAY layer (`simulate_play`) and the programme console.
It is **downstream of the engine tensors**: `outputs_digest`, RunRecords,
replay MATCH, world ids, and every seal are untouched. What actually moves:

- `PLAY_ALPHA_VERSION` and `GEN_PLAY_ALPHA_VERSION` both bump (every book's
  numbers change) — leaderboards restart under the new stamps, old rows
  remain readable under the old ones.
- Both committed fixtures regenerate (`scripts/gen_bundle_fixtures.py`);
  play/bundle/serve goldens move.
- The credibility programme section re-reads: `peak_unfunded_ratio` should
  come INTO its declared band — the register flag clearing is the
  acceptance signal, not a tuned target.
- NOT touched: `schemas/`, `mappings/`, any pre-registration lock,
  `ah/core/engine.py`.

**ER-8 interplay, a likely free win:** faster calls strain the cash account
harder, which is the exact mechanism ER-8 says died (no shipped world can
force a sale). The fix must re-measure `forced_secondaries` across the seed
battery — if it revives, ER-8 partially closes for free; if not, that stays
honest and open.

## D1 — the owner decision: where the curve comes from

ALB-A never arrived, so the curve is either declared or taken from a public
methodology. Three options, one recommendation:

**Option A — declared curve, PLAUSIBLE-band style (recommended).**
Declare `rc_curve = [0.35, 0.40, 0.30, 0.25, 0.20, 0.15]` — "one
allocator's view, written down so disagreement is about a number." Pure-curve
arithmetic: 92.7% called by year 10 (0.65·0.60·0.70·0.75·0.80·0.85·0.85⁴ =
7.3% uncalled), landing ~90–91% after the `f_call` drag — mid-band, with the
early years front-loaded the way real capital deployment is. Same shape
convention as today (declining, clamped tail), so only the six numbers
change. Honest posture: the parameters file records `source: declared
(practitioner band 85-95% by year 10); supersedes the ALB-A placeholder`.

**Option B — Takahashi–Alexander (2002) rates.** The published Yale pacing
model's contribution schedule (25%, 33%, then 50% of remaining) is citable
and public, but reaches ~97% called by year 6 — the hot edge of the band,
and a much sharper J-curve than the mid-life-cohort opening the play book
assumes. A real option if citability outweighs fit.

**Option C — Option A plus expiry-at-term semantics.** Also make the
residual unfunded at cohort lapse an explicit, ledgered event ("commitment
expired undrawn: X") rather than silent disappearance. Costs a schema-free
ledger line; makes the residual honest at any curve. Can ride along with A.

**Recommendation: A + C's ledger line.** Declared, mid-band, auditable, and
the expiry event makes whatever tail remains visible instead of silent.

## Work plan (one WP, `er6-call-pacing`, after sign-off)

1. RED: tests asserting cumulative called fraction at year 10 in [0.85,
   0.95] on a flat tape; the expiry ledger line appears at lapse; the
   programme stats' `peak_unfunded_ratio` median lands inside 0.25–0.75 on
   the stagflation preset.
2. Update `mappings/pacing-parameters-v1.0.yaml` + the example cohort
   fixture + `cohort.py` if C's ledger line needs a hook (parameters file is
   NOT in any lock — verified in the tail-bands WP).
3. Bump both alpha stamps; regenerate fixtures; console walk before merge
   (the standing memory: the console catches what unit tests cannot).
4. Re-measure ER-8's `forced_secondaries` across 20 seeds of every preset +
   the 1974 world; update the register entries for ER-6 (closed) and ER-8
   (whatever the measurement says).
5. Full gate; merge `--no-ff`; CHANGELOG; register + CLAUDE.md updated.
