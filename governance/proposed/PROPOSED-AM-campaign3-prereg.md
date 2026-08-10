# PROPOSED — the campaign-3 pre-registration (seal event draft)

*Status: DRAFT for owner review. Drafted 2026-08-09 from
`docs/superpowers/specs/2026-08-09-campaign3-design.md` (rulings K1–K4) after
the wiring WP (AM-2026-08-09-003) put the extension families on the sealed
read path. Nothing here is in force until the owner ratifies it as ONE sealed
event: amendment appended + `pre-registration.yaml` edited + lock re-sealed,
in the same commit, after the reference bands derive. No training runs before
that seal.*

## Preconditions (state at drafting)

- **Wired:** the seven extension families are on the read path and hashed
  (lock digest `sha256:6061fd73…`). The pinned HAR draw is materialized
  (seed 20260809, 393 months, sha256
  `53a378a49bfa58f9457698473457f526298efe5454ca9187ff2c35ca3fb50178`).
- **Blocked, external:** the campaign-3 vintage. The 2026-08-09 (Sunday)
  refresh QUARANTINED on `fred.DTWEXBGS` staleness (9d vs 7d SLA) — correct
  behaviour, not an obstacle. Re-run after FRED's H.10 release (Monday
  afternoon ET); the first clean vintage carrying the donor series (VXO,
  CPF3M, CP3M, CP3M_NBER, TB3M_SEC, GS1, GS3) becomes the campaign vintage.
- Until this event seals, campaign-3 training is BLOCKED twice over: bands
  underived, and the K4 hardware call unmade.

## The sealed event, section by section (edits to `pre-registration.yaml`)

1. **`campaign_vintage_id`** → the clean weekday vintage id (unknown until
   the refresh lands; never guessed in advance).
2. **`reference_run`** — every band re-derived on the extended
   train+validation panel via the UNCHANGED
   `scripts/compute_campaign_reference.py` machinery (its module constants
   move with the sealed block, as the existing test enforces). Proposed
   parameters, each an explicit choice, not a habit:
   - `seed: 20260726` — KEPT, so any factor whose data is genuinely
     unchanged reproduces its campaign-2 band bit-for-bit and every band
     that moves is attributable to the data, not the draw.
   - `n_resamples: 1000`, `level: 0.9`, `block_length: 120`,
     `resample_length: 120` — KEPT; the extended span changes the sample,
     not the estimator conventions.
   - The campaign-2 bands are dead letters: nothing is carried over by
     value. Any band that must be pinned rather than re-derived is an
     argued exception listed in the amendment payload.
3. **`thresholds`** — recomputed from the new reference run under the same
   sealed estimator definitions. The four-clause G2 decision-rule shape is
   restated with ONE structural change: the draw-span bias clause DIES (the
   handicap it disclosed is gone) and is REPLACED by the proxy-share
   disclosure clause: **every verdict table over the extended span reports
   the per-factor proxy share of the months that produced it** (the
   AM-2026-08-09-002 disclosure, promoted from amendment prose to a sealed
   reporting requirement).
4. **K1 — the future-accruing holdout**, sealed as protocol: data first
   published after 2026-08 is untouchable until 2029-01 at the earliest;
   ONE read, ever; the evaluation spec is sealed before the read; results
   publish both ways; nothing re-runs. (WP5.6's protocol shape — the past
   holdout is spent and no past data can be un-seen; the future is the only
   place a holdout can still come from.)
5. **K2 — commodities activation**: `governance/proposed/`
   `PROPOSED-AM-commodities-close.md` ratifies IN THIS EVENT as its own
   `block_addition` (aqr.cmdty_ew_tr; thresholds derived on the extended
   reference; REG licence attribution rides every artifact; raw AQR values
   never committed). `factor_sources.commodities` flips from `unavailable`.
6. **K3 — the masked-HAR ablation cell**: the ablation grid gains a variant
   with equity_vol treated as MISSING before 1986-01, so the
   learning-from-our-own-reconstruction effect is a measured number in the
   campaign evidence. **Pre-stated demotion criterion (proposal, owner may
   tighten):** the HAR-included variant is demoted to report-only if
   (a) masking flips ANY enforce-tier clause of the sealed decision rule,
   or (b) the pooled decision-alpha difference between included and masked
   cells exceeds half the sealed beats-margin. Sealed as numbers in the
   YAML, not prose.
7. **Severe test** — exclude the 1970s, regenerate from the 1965-12 state,
   compare 1966-84, POSABLE FOR BOTH SIDES for the first time
   (`bootstrap.SEVERE_TEST_POSABLE`). **Pre-stated decision criterion
   (proposal):** the severe leg PASSES for a system iff the excluded-decade
   regeneration keeps every enforce-tier severe statistic inside its sealed
   band; a system that cannot pose the leg at all FAILS it (no
   benchmark_exception this time — the exception's stated reason is gone
   with the extended span). RFR-77's lesson: the criterion seals with the
   procedure.
8. **The race**: `bootstrap-v1` (extended span) vs `hier-flow-v2`
   (retrained) plus the ablation family incl. the K3 masked cell.
   **Proposal: `hier-diffusion` does NOT race** (the flow family was the
   promoted line; diffusion retraining spends the K4 budget without a
   decision it would change) — the prereg states this in `ablation_systems`
   either way, per the design spec's requirement that it say whether
   diffusion races.
9. **The pinned draw** — `equity_vol_pinned_draw.json`'s sha256 (above) is
   recorded in the sealed YAML beside the provenance artifact sha, so the
   one panel history is named by the document that judges it, not only by
   the lock.
10. **K4 — hardware**: training starts only after the owner picks the host.
    Measured CPU cost ~2.2h per flow cell; the campaign-2 grid shape
    (5 systems × 3 seeds) puts a CPU campaign at multiple days wall-clock.
    The seal does not wait for this call — only training does.

## Order of operations at ratification

1. Clean weekday refresh → campaign-3 vintage id.
2. Update `scripts/compute_campaign_reference.py` constants → run → bands.
3. Edit `pre-registration.yaml` per §§1–9; update the script-constants test
   expectations in the same commit.
4. Append the campaign-3 amendment (payload: vintage id, parameters, the
   K-clauses as sealed text, the two artifact shas, the superseded lock
   digest) via `ah.eval.prereg.append_amendment`.
5. Re-seal; commit everything together; full gate; merge on green.
6. Owner makes the K4 call; training begins; battery → race → verdict on
   the G2 machinery end to end.

## Standing caveats carried into the seal

Backcast equity_vol months are MODEL OUTPUT and say so at every surface;
proxy months are flagged at source and disclosed per-factor in every table;
the campaign-2 record is untouched (its live-tree re-derivation ended at
AM-2026-08-09-003, disclosed there); and `hier-flow-v1`'s standing caveat —
sealed-criterion winner, not a convincing model of history — transfers to
any successor until the campaign-3 evidence says otherwise.
