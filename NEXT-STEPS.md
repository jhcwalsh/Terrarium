# NEXT-STEPS.md — after the su-generated-worlds plan (2026-08-12)

## Where the last two days left us

- **The su-generated-worlds plan (PD-2 phase 2) is COMPLETE** — merges
  `ffd05f9` (adapter + stagflation_1974, replay MATCH), `08eb59c`
  (world-bundle-0.5 with factor lineage), `63ba0cb` (sessions under
  `port-v1-cashflow-gen`; the player-facing provenance panel), `5dd7e40`
  (the wire pinned). The playable app now runs a world spliced from real
  1953–2020 months with its audit trail on screen. Tagline: "An alternate
  history, relived."
- **Register ER-9 opened and made moot for generated worlds** in the same
  arc: the credibility console gained declared tail bands (merge `3bd9b41`)
  which then caught the adapter's block-seam fabrications pre-merge —
  source-space derivations fixed the class. The console also gained
  scenario tabs + charts (console v2, merge `2c70999`).
- Everything is committed and pushed; the vintage store and campaign
  artifacts under `data/`/`experiments/` are local-only by design (OD-4).

## 1. The next release event — ER-6, designed and awaiting D1

`docs/superpowers/plans/2026-08-12-er6-call-pacing-design.md` (DRAFT).
The call-pacing fix is play-layer only (no digests, no seals, both alpha
stamps bump), unblocks the commitment lever (E1), and may revive ER-8's
forced-sale mechanic for free. **Needs the owner's D1 call** (recommended:
declared mid-band curve + an expiry-undrawn ledger line).

## 2. Cheap research probes (gaps, not instead)

- **Seed-committee diagnostic** (~a day): pool the three v2 checkpoints,
  re-judge; was campaign-3's neural loss variance or capability?
- **JST cross-country scoping note** (no compute): 18 countries × ~150y as
  REAL training data — the honest multiplier the K3 lesson demands.

## 3. Campaign-4 — the case has sharpened

The stagflation-tilt finding (1974's equity median +11.5%/yr; regime
conditioning pins block STARTS only) is the conditional-capability argument
in product form. Preconditions unchanged: the two probes above, the
re-aimed criterion, real-months-only training sealed as a rule.

## 4. Standing owner questions

- **D1 (ER-6 curve source)** — see §1.
- **PE sealed alpha**: generated-world PE flags at Sharpe 1.30, tracing to
  the sealed `alpha_quarterly` 0.0332 — disclosure line or a G3 amendment
  (which would also add the commodities/hy_spread regressors the sealed PM
  loadings omit on vintage 2026-08-07.5).
- **Do toy presets stay player-facing?** Decides how much the ER-5/ER-8
  engine-family fix matters now that generated worlds play.
- **K1 holdout**: post-2026-08 data accrues untouched; first read 2029-01.

## 5. Small successors recorded in the closed plan

`summary.episodes` still carries the authored sequence (realized regimes
per path exist on the RegimeRecord, uncarried); `board_pack` has no
producer; the programme walk shows a pending note for generated worlds.

## 6. To relaunch the surfaces

- Session service: `uv run uvicorn ah.serve:app --port 8787` (restart after
  any serve.py change — the stale-listener trap).
- App: `cd app && npm run dev` (5173, proxies /sessions → 8787); load
  `stagflation-1974.bundle.gz` from the repo root.
- Console: `uv run ah credibility --preset stagflation --preset goldilocks
  --preset reflation_boom --preset deflation_bust --preset stagflation_1974
  --out credibility.html`
