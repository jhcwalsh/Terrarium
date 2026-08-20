# The PE entry-multiple drift on the three er14-06 presets — finding

**Date:** 2026-08-19 · **Branch:** `pe-drift-01` (from `origin/main` `c54c373`)
**Verdict: INERT on the generated plane. REAL on the toy plane. The three
er14-06 worlds are numerically unaffected — 711/712/713 do NOT need a rebuild.**

## The suspicion

`D-ER14-2` (ratified 2026-08-18) zeroed the hand-authored
`structural.private_equity.entry_multiple_drift_annual_pct = -2.0` on the live
presets, because the ER-14 close-out's `mu_PE = 0.45` now produces multiple
compression endogenously — and `mu_PE` was anchored *on that very -2.0*
(`engine.py`: `_MU_PE = 0.45  # the shipped presets' own authored -2.0 drift at
4.5pp excess`). Carrying both would charge PE twice.

The three worlds created afterwards by `er14-06` — `gulf_decade` (712),
`stress_1974_successor` (711), `stress_1990_successor` (713) — were built by
copying the shape of the **retired** `stress_1974`/`stress_1990` records, which
are deliberately byte-frozen *with* their -2.0. The copy carried the -2.0 across
the zeroing line. Worlds 711/712/713 are already built and run in the live store.

## 1. The code trace

### The toy plane — the field IS consumed

`ah/core/engine.py`:

```
489:  pe_mult = _f(st.private_equity, "entry_multiple_drift_annual_pct", _DEF["pe_mult_drift"])
560:  pe = 1.4 * eq + (pe_illiq + pe_mult + (_LAMBDA_PE - _MU_PE) * x) / 12.0 + 2.0 * e_pe
```

Both terms sit inside the same bracket. `pe_mult = -2.0` is a flat
`-2.0/12 = -16.67 bp/month`; `(_LAMBDA_PE - _MU_PE) * x = -0.10 * x` is the
endogenous half, whose `mu_PE` component alone reproduces `-0.45 × 4.5 ≈ -2.0`
at the anchoring excess. Charging both is a genuine double charge. This is
exactly what `D-ER14-2`/A5 fixed on `stagflation` and `stagflation_1974`.

### The generated plane — the field is NOT consumed

Everything with `generator_id != "toy-v0"` dispatches to
`ah/port/adapter.py::run_gen_path` (`cli.py::run_cmd`, `serve.py`,
`bundle.py`, `programme.py`, `credibility.py`), which never calls
`engine.run_path`. Private-market returns come from
`adapter._pm_true_monthly_path`, whose PE row is built entirely from the sealed
v1.2 mapping artifact:

```
alpha_quarterly/3  +  Σ loadings·regressors  −  b_infl·(cpi_trail_excess/12)/100  +  residual
```

`_pm_true_monthly_path` takes `(ensemble, rows, series, seed)` — **the WorldSpec
is not one of its arguments**, so `world.structural` cannot reach it even in
principle. A repo-wide grep confirms `structural.private_equity` is read in
exactly two places: `engine.py:488-489` (toy `run_path`) and `validator.py:320`
(V5, a *warning* whose trigger is `pe <= -3`, which -2.0 does not reach).
`_reported_marks`, which the adapter does share with the toy engine, reads
`structural.reporting_smoothing.private_equity` — a different field.

Note that the generated plane is not simply "immune to double charges": the
adapter deliberately applies the artifact's `b_infl` with the toy plane's NET
sign for PE (`adapter.py:296-307`, AT-10), *because* the generated plane "has no
second authored term to net it against". The comment is a correct statement of
the design; this finding measures that it is also a correct statement of the
code.

## 2. The measured probe

Read-only, no shared-DB writes. Two independent measurements agree.

### (a) Per-path, in process — `run_gen_path` as-is vs. drift zeroed

| preset | world | seeds | PE true | PE reported | max abs diff |
|---|---|---|---|---|---|
| `gulf_decade` | 712 | 202608, 210527 | bit-identical | bit-identical | `0.0` |
| `stress_1974_successor` | 711 | 197400, 205319 | bit-identical | bit-identical | `0.0` |
| `stress_1990_successor` | 713 | 199001, 206920 | bit-identical | bit-identical | `0.0` |

**Measured PE delta on the generated plane: 0.00 pp. Exactly zero, not small.**

Toy-plane control, `stagflation` with the drift forced back to -2.0 (so the
probe is proven able to detect the field on the plane that does consume it):

| seed | cum PE @ -2.0 | cum PE @ 0.0 | delta |
|---|---|---|---|
| 771204 | 43.56% | 75.37% | **+31.81 pp** |
| 779123 | 231.26% | 304.01% | **+72.75 pp** |

### (b) End-to-end through the CLI — full ensemble + twin + digest

`ah --db <scratch>/probe.db world build --preset gulf_decade` + `run --paths 40`,
then the same into a second scratch DB after zeroing the preset:

```
probe.db   sha256:32efd1d723aabb67d0e11160d2933612383d3df38a91499092b23b1ba5ad5755
probe2.db  sha256:32efd1d723aabb67d0e11160d2933612383d3df38a91499092b23b1ba5ad5755
```

Identical `outputs_digest` over 40 paths, identical `summary_stats`. The
RunRecords already in the live store for 711/712/713 are the numbers the zeroed
presets produce.

## 3. The fix

- The three live successor presets set the field to `0.0`, matching the
  `D-ER14-2`/A5 treatment of `stagflation`/`stagflation_1974`. Hygiene and
  consistency, not a numeric correction.
- The four **retired** records (`stress_1974` 701, `stress_1990` 703,
  `narration_1974` 801, `spine_pilot` 802) keep their -2.0 and are untouched —
  `tests/test_cli.py::test_the_retired_presets_are_still_readable_and_byte_unchanged`
  pins that, and the D-ER14-2 close-out note names the same scope deviation
  ("R-6's preset scope").
- Each successor preset's `x_stress.precedent` records *why* this one structural
  value does not carry over from its parent.
- `tests/test_gen_adapter.py::TestEntryMultipleDriftIsToyPlaneOnly` pins all
  three halves: the generated plane is bit-identical across the schema's full
  declared range (-6 to +4) on every asset; the toy plane moves by exactly
  `drift/12` per month; the three live presets read `0.0`.

The inertness test was break-and-revert proved: patching
`_pm_true_monthly_path` to read the field makes it fail with a max absolute
difference of `0.83333` (= 10.0/12, the -6→+4 span), and the patch was reverted.

## 4. Consequences for the live store — no rebuild needed, but read this

**Worlds 711/712/713 need no rebuild.** Their stored RunRecords are numerically
identical to what the corrected presets produce, proven by the digest match
above. Do not spend a rebuild on this.

There is one non-numeric consequence to be aware of. `structural` is an
engine-consumed field under `store/worlds.py::ENGINE_FIELDS`, so re-running
`ah world build --preset gulf_decade` against a store that already holds 712
now raises:

```
ImmutableWorldError: engine-consumed field 'structural' changed for
world_id=00000000-0000-4000-9000-000000000712; create a new world_id with
provenance.source.parent_world_id set.
```

(measured, against the scratch DB). So the **stored spec text** for 711/712/713
now differs from the preset files by this one field, and the store will refuse
to reconcile them in place. Given the numbers are identical, the right move is
to leave the store alone and let the divergence stand as recorded here — minting
new world_ids to change a field that provably does nothing would cost the
leaderboard and the sessions for no gain. If a future release rebuilds the store
from scratch for other reasons, the drift resolves itself.

## 5. Loose end for the owner

`narration_1974` (801, `hier-flow-v1`) and `spine_pilot` (802,
`bootstrap-stratified`) also carry `-2.0`. Both are **retired** and correctly
untouched. But no live preset now exercises a non-zero
`entry_multiple_drift_annual_pct` on the toy plane, which means the field's
surviving meaning — *non-inflation* multiple drift, secular dry powder, sector
re-rating — is currently unexercised by anything shipped. That is fine as a
state of affairs; it is worth knowing that the toy plane's only remaining
multiple-compression channel is `mu_PE`.
