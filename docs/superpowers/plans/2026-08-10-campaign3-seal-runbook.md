# Campaign-3 seal event — runbook (pre-flighted 2026-08-10 morning)

*Companion to `governance/proposed/campaign3-prereg-edit-blocks.md` (the
exact YAML) and `docs/superpowers/specs/2026-08-09-campaign3-design.md`
(the intent). This file records what the morning pre-flight verified and
the exact afternoon sequence, so the event is execution, not research.
The H.10 waiter (in-session) polls from 13:30 PT; a one-time Task
Scheduler fallback (`Terrarium H10 refresh fallback 2026-08-10`) fires
the bare refresh at 14:30 PT if the session died — DELETE IT once the
in-session refresh succeeds:
`Unregister-ScheduledTask 'Terrarium H10 refresh fallback 2026-08-10' -Confirm:$false`.*

## Pre-verified this morning (do not re-derive)

- **All three locks verify against the committed tree** — 171 seal/prereg
  tests green at `9b257a8`. The event starts from a clean baseline.
- **Pinned artifact shas match the edit blocks byte-for-byte:**
  `equity_vol_pinned_draw.json` = `53a378a4…f50178`,
  `equity-vol-backcast-provenance.json` = `f0535582…fc92` (recomputed,
  not trusted).
- **The two constant flips are where Block 11 says:**
  `scripts/compute_campaign_reference.py:41` and
  `src/ah/gen/bootstrap.py:204` (currently `CAMPAIGN2_VINTAGE_ID`).
  `measure_block_length_window.py`'s copy is a historical pin — never
  touch it.
- **`REFERENCE_SEED = 20260726` confirmed** in the reference script, with
  the RFR-61 bit-for-bit comparison comment intact.
- **`apply_block_addition` CANNOT carry the commodities thresholds**: it
  requires exactly one *newly-active block* (prereg.py:1784 docstring);
  commodities lands names in the existing `global` block. Use Block 3's
  fallback: fold the thresholds into the main `protocol_change` edit,
  keep the payload in the amendment as the audit record. (hy_spread's
  campaign-2 restoration went through the campaign-restart
  protocol_change, not block_addition — same footing.)
- **`pre-registration.yaml:18` stale prose is LIVE**: the header still
  says "block_draw_span is still 1990-2020 because equity_vol (VIX)
  binds it." The ratification did not amend it. Fix in this event
  (Block 10, first item — confirmed real, not precautionary).
- **`rationale.d4_commodities_consequence` (~line 500) and the D4 comment
  block (~line 305) both update**: hy_spread restored at campaign-2 +
  commodities sourced now → BOTH strategies computable, agreeing with
  Block 2's `uncomputable_d4_strategies: []`.
- **OWNER RULING 2026-08-10: commodities JOINS the factor set** —
  `bootstrap_v1.factor_set`, `bootstrap.FACTOR_SET`, hier-flow-v2's
  training list, all in the same amendment. Recorded with grounds in the
  edit-blocks doc, Block 11.

## The sequence (waiter fires ~13:30+ PT)

1. `uv run ah data refresh --live` → note `<C3_VINTAGE_ID>`; QC must pass
   and the pointer advance. On quarantine: read the QC report; if it is
   only DTWEXBGS still stale, FRED ingestion is lagging — wait for the
   next waiter poll, do not weaken anything.
2. Delete the Task Scheduler fallback (command in the header).
3. Flip the two constants to `<C3_VINTAGE_ID>`; run
   `uv run python scripts/compute_campaign_reference.py` →
   `reference-run.json`.
4. **Wiring-engagement check (abort rule):** expected coverage firsts —
   cape_v 1881-01, cpi 1913-01, ig/hy_spread 1919-01, hqm_curve 1919-01,
   equity_mkt/smb/hml 1926-07, commodities 1926-07, mom 1927-01,
   policy_rate 1934-01, funding_spread 1934-01, equity_vol/ust_2y/
   ust_10y/fx_usd 1953-04. Any bolded-in-the-blocks first coming back at
   its campaign-2 value = the extension did not engage = STOP, diagnose,
   no seal.
5. Apply Blocks 1–11; fill every `<ANGLE_BRACKET>` from the run; paste
   the superseded draw-span-bias clause text verbatim from the sealed
   file (Block 5's apply-time paste); Block 10 sweep including line 18.
6. Append `AM-<C3_AM_ID>` (`protocol_change`, post_hoc false) with the
   commodities threshold payload embedded; re-seal ALL THREE locks
   (main + G3 + G5 — factors.yaml is hashed by all three).
7. ONE commit with every edit + all three re-seals. Then the full gate in
   the background to a file; read the EXIT line and pass count
   (never the tail).
8. Merge `--no-ff`, plain push on green.
9. Training does NOT start — K4 (hardware) remains the owner's open call;
   S3-K4-HARDWARE-GATE ships OPEN.

## Known-good context for step 4's judgment calls

- Current vintage `2026-08-09.aqr1` already carries both AQR series
  (1,780 months each); the refresh carries them forward — commodities
  banding needs no second intake.
- On `2026-08-09.aqr1` the datalab Extensions page shows equity_vol
  degrading to the campaign-2 read (440 months, 1990→) because VXO and
  friends are not yet in store — correct and expected; the same view
  after step 1 should show the extended read (881 months, 1953-04→,
  pre-1986 flagged MODEL OUTPUT). datalab on 8795 is the fastest visual
  check that the wiring engaged.
