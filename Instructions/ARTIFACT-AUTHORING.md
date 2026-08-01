# Artifact Authoring Specification — Tier-2 Documents v1.0

*Companion to `world-bible-v1.0.schema.json`. Covers the first two Tier-2 artifact types — the fund manager quarterly letter and the paired research notes — plus the data-payload contracts and the consistency-gate rules (G-rules) that govern all Tier-2 output.*

> **Reconstruction status — v1.0-r, 1 August 2026.** This file was rebuilt from the 28 July session transcript after the original was found never to have been persisted to the project repository. §§1–6 are recovered essentially verbatim. Nothing has been added, silently corrected or extended; the only editorial change is this block. Two known gaps are recorded in `RECONSTRUCTION-NOTES.md` — read that before freezing anything against this file.

---

## 1. Principles (inherited, non-negotiable)

1. **Authors write from data, never ahead of it.** The prompt payload contains only information revealed at or before the artifact's dateline. Arc beats with `from_quarter` beyond the dateline are stripped before prompting.
2. **Interpretation is free; facts are gated.** Houses and managers may spin, hedge, and disagree. Every checkable numeric or event claim must match the tape/chronicle (rules G1–G3). Opinions are not gated; misstatements are.
3. **Entities are closed-world.** Only bible cast, research houses, media names, the institution, and the generic allowlist may be named (G4). No real firms below generic policy level; no real persons, ever.
4. **Every artifact is marked and recorded.** Rendered output carries the simulated-world marking (G8); the chronicle record stores payload hash, prompt version, model id, gate results (G9). Regeneration is versioned, never silent.
5. **Truth converges.** Artifacts flagged `fog:true` (early reports, rumors) may deviate from the tape within declared bounds but must be resolved by a correcting artifact within the declared window (G7). The chronicle converges to the tape; the fog is on the record.

## 2. Data-payload contracts

Payloads are built by deterministic code (never by an LLM) from the tape and chronicle. All figures pre-formatted to publication precision so the author copies rather than computes.

**P-LETTER (manager quarterly letter)** — for a cast entity with `held_by_institution` or GP/lender kind:

```
dateline, quarter_label                # e.g. "2028-Q4, published Feb 2029" (reporting lag applied)
entity: {name, kind, one_liner, signature_traits, voice, relationships}
arc_beats_to_date: [...]               # beats with from_quarter <= dateline quarter ONLY
fund_facts:
  reported_return_q, reported_return_ytd, reported_return_si
  nav_index, distributions_flag, calls_flag          # from cashflow layer when enabled
  gate_status, secondary_market_context              # e.g. "secondaries quoted low-80s vs NAV" iff in tape/chronicle
market_context:                        # same-quarter public comps, pre-formatted
  public_equity_q, hy_spread_now_bps, policy_rate_now, cpi_now
chronicle_extracts: last 6 wire items relevant to entity/asset class
checkable_claims_table: the exact figures above, listed — the author is told any number used MUST come from this table verbatim
```

**P-NOTE (research note; generated as a pair, one call per house)**:

```
dateline
house: {name, prior, voice, coverage}
subject: asset_class | cast_entity
data_panel: pre-formatted YTD/1Y returns, drawdown, spreads, rate, CPI, reported vs public-comp gap for privates
chronicle_extracts: last 8 relevant items incl. the OTHER house's prior published stance (for explicit disagreement)
constraint: recommendation vocabulary limited to {overweight, neutral, underweight, no_rating} + 12-month qualitative view
checkable_claims_table
```

## 3. Prompt templates

Placeholders in `{{...}}`. Prompt text is versioned (`author-prompt/letter@1.0`, `author-prompt/note@1.0`); any edit bumps the version and re-runs the authoring regression set (§5).

### T-LETTER v1.0 — Fund manager quarterly letter

```
You are ghost-writing an in-world fictional document for a market simulation.
Write the quarterly investor letter of {{entity.name}}, a {{entity.one_liner}}.

VOICE: {{entity.voice.register}}. Stylistic habits to honor: {{entity.voice.tics}}.
CHARACTER: honor these traits without naming them: {{entity.signature_traits}}.
CONTINUITY: your firm's story so far (do not contradict; do not foreshadow anything beyond it):
{{arc_beats_to_date}}

THE QUARTER'S FACTS (the only numbers you may use — copy them verbatim, never derive new ones):
{{checkable_claims_table}}
Recent relevant newsflow: {{chronicle_extracts}}

WRITE: 350–550 words. Structure: (1) brief market commentary in-voice; (2) portfolio/marks
discussion — you MUST address the quarter's reported return and, if the public-comp gap
exceeds 3pts, you MUST address the gap in your firm's characteristic way (defend, deflect,
or acknowledge, per voice/traits — but never misstate a number); (3) outlook consistent
with your character, hedged as a real GP hedges.

HARD RULES: Mention only these named entities: {{allowed_entities}}. No real firms or people.
No dates or events after {{dateline}}. No promises of returns. Do not mention that this is a
simulation. Output the letter body only, no headers.
```

### T-NOTE v1.0 — Sell-side research note (issued as a disagreeing pair)

```
You are ghost-writing an in-world fictional research note for a market simulation.
House: {{house.name}}. Structural prior: {{house.prior}} — {{prior_gloss}}.
VOICE: {{house.voice.register}}; habits: {{house.voice.tics}}.

SUBJECT: {{subject}} as of {{dateline}}.
DATA PANEL (only numbers permitted, verbatim): {{checkable_claims_table}}
NEWSFLOW: {{chronicle_extracts}}
THE OTHER HOUSE most recently said: "{{rival_stance_summary}}" — you may engage with it.

WRITE: 220–350 words: title (≤12 words), rating from {overweight|neutral|underweight|no_rating},
2–4 paragraphs of argument READING THE SAME DATA THROUGH YOUR PRIOR, one explicitly stated
risk to your own view. Your interpretation should plausibly differ from the rival's;
your facts cannot.

HARD RULES: identical to T-LETTER (entities, dateline, no simulation references, body only).
```

*`prior_gloss` strings (fixed):* constructive → "growth and policy support resolve stress over time"; cautious → "fragilities compound and marks lag reality"; valuation → "everything mean-reverts; entry price is destiny"; flow → "price trend leads fundamentals; respect the tape."

## 4. Consistency-gate rules for Tier-2 (G-rules)

Run in order; G1–G5 and G8 are blocking (artifact returns to the author queue with the violation attached, max 2 retries, then falls back to a Tier-1 templated substitute).

- **G1 · Numeric fidelity.** Extract every number (regex + unit classifier). Each must match an entry in `checkable_claims_table` exactly as formatted, or be a pure verbal quantity ("mid-single-digit") consistent with the table within declared bands. Any derived arithmetic (sums, annualizations) is a violation even if correct — authors copy, code computes.
- **G2 · Event fidelity.** Named events (gatings, rate moves, defaults, bear markets) must exist in the chronicle at or before the dateline.
- **G3 · Dateline causality.** No reference, however oblique, to tape data, chronicle items, or arc beats after the dateline. Screened by a leak-checker prompt over the draft plus keyword rules on future quarter/year labels.
- **G4 · Closed entity world.** Every proper noun resolved against {cast ∪ research_houses ∪ media ∪ institution ∪ generic_allowlist}. Unknown proper nouns block. (This is also the real-name firewall.)
- **G5 · Vocabulary and compliance.** Ratings restricted to the fixed set; no performance promises; no advice-like imperatives to the reader; required hedging present in outlook sections.
- **G6 · Continuity.** Draft checked against the entity's own past published artifacts for direct contradictions of stated facts (opinions may evolve; facts may not). Advisory in v1 (warn), blocking from v1.1.
- **G7 · Fog convergence.** If `fog:true`: deviation must be within the declared band, the artifact must carry the in-world uncertainty marker ("unconfirmed", "people familiar"), and a resolver artifact must be scheduled within the declared window (default: 2 world-weeks). Unresolved fog blocks the next chapter's publication batch.
- **G8 · Marking.** Rendered output carries the simulated-world watermark and footer disclaimer; mastheads pass the trade-dress screen version recorded in the bible. Export paths re-apply marking (screenshot-resistant placement).
- **G9 · Record.** Chronicle entry stores: artifact id/type, dateline, payload hash, prompt version, model id, gate results, retry count. Absence of a complete record blocks publication.

## 5. Authoring regression set

Analogous to the compiler's 50-scenario set: ~30 frozen payloads (bull quarter, crash quarter, gate event, big comp-gap quarter, quiet quarter × entity/house types). Any prompt or model change re-runs the set; diffs reviewed by a human for voice drift, gate pass-rate, and disagreement quality (the pair must not converge). Target: ≥95% first-pass gate rate before a prompt version ships.

## 6. Scheduling defaults (artifact_calendar bindings)

Manager letters: 6 world-weeks after quarter-end, per `held_by_institution` entity. Research pair: each quarter-end +2 world-weeks per covered subject, plus event-triggered specials (bear-market entry, gate events). Both suppressed during the first world-quarter (no history to write about) and batched at chapter generation for live worlds.
