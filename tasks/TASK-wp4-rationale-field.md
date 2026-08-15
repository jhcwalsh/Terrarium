# TASK — WP4 rationale field on decision windows (DN-9 N-af)

## Context

DN-9 Appendix E specifies a Board that holds the player to positions they previously stated. That requires the player's stated rationale to exist in the RunRecord. It does not exist today.

**This task changes shape only — no Board, no minutes, no behaviour, no scoring.** The goal is that a RunRecord written after this change carries the field, so that when the Board lands there is no migration and no version break, and so that runs recorded in the interim are usable.

Two independent consumers want this data and neither is the Board:
- DN-6 §4 wants stated reasoning as a research covariate
- The post-game annotation screen can show the player their own reasoning against the outcome

Companion to `TASK-wp4-schema-shaping.md`, which established the `DecisionWindow` / `Action` shape this extends.

---

## Scope — three changes

### 1. Rationale on the decision window

```
DecisionWindow
  window_id            int, 1..K
  actions              list[Action]          # unchanged
  rationale            Rationale | null      # NEW
  submitted_at         server timestamp
  status               reached | not_reached

Rationale
  free_text            str, 0..600 chars, optional
  tags                 list[enum], 0..3, optional
  recorded_at          server timestamp
```

Requirements:

- **Optional at every level.** A window with `actions: []` and `rationale: null` is valid and meaningful — the player did nothing and said nothing. Do not require rationale to submit a decision.
- `rationale` attaches to the **window**, not to individual actions. A player gives one reason for what they did that year, which is how a committee works.
- `free_text` is stored verbatim, never parsed, never scored, never shown to another player.
- `tags` is a **closed enum**, frozen in this task, extensible only by version bump:

```
valuation | liquidity | policy_outlook | peer_positioning | risk_reduction
| risk_addition | rebalancing_discipline | pacing | governance | other
```

Free text is for humans; tags are for DN-6. Do not attempt to derive tags from free text.

### 2. Version stamp

```
rationale_schema_version    "1.0"
```

Inert. No logic reads it. It exists so a run can state what produced it.

### 3. Retention and privacy

- `free_text` is player-authored content and is **pseudonymous personal data**. It inherits the privacy policy and the DN-6 §5 logging rules.
- It must **never** appear on a share card, an outcome card, a leaderboard, or any surface visible to another player. Assert this in the renderer, not only in policy.
- Export must include it in a player's own data export.

⚖ *Confirm with Counsel that free-text capture is covered by the existing privacy policy before the field is exposed in the UI. Storing the field is safe; collecting it may need a line.*

---

## Non-goals — do not build these

- The Board, board state, personas, pressure, or constraints
- Minutes, minute rendering, or consistency checking against prior rationale
- Any use of `rationale` in scoring, decision alpha, or the twin
- NLP over `free_text` of any kind
- UI beyond a plain optional text area and an optional tag selector

If a change appears to require touching engine behaviour or scoring, stop and flag rather than proceeding.

---

## Acceptance

1. Existing WP3/WP4 suites pass unchanged.
2. A run with `rationale: null` at every window produces a RunRecord byte-identical to the pre-change format except for `rationale_schema_version`.
3. A window with `rationale` present round-trips exactly, including unicode and newlines in `free_text`.
4. A payload with a tag outside the enum is rejected with an explicit error, not coerced or dropped.
5. A payload with `free_text` over 600 chars is rejected, not truncated silently.
6. `free_text` appears in no share-card, outcome-card or leaderboard code path. **Add a test that asserts this**, not a code review comment.
7. Replay of a run containing rationale is bit-for-bit identical.

---

## Output

Summarise: files changed, the schema diff, and any place where an existing surface would have serialised the whole `DecisionWindow` into a player-visible payload. That last one is the finding worth having — a window object that was already being shipped wholesale to a share renderer is a leak waiting for a field to leak.

---

*Blocks: DN-9 Appendix E (the Board), DN-6 §4 covariates. Do this before runs accumulate — retrofitting is a migration.*
