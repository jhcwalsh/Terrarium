# Opening Book Entry — Design

*2026-08-15 · Approved design for `su-app-06`: an entry screen for a real
institution's opening book — sleeve weights and the private vintage ladder —
plus an editable kickoff commitment plan. Branch `su-app-06-allocation-entry`.*

---

## 1. What this is

Today nobody chooses the opening allocation. `simulate_play` is called with
`start_targets` resolved from the engine adapter (`START_TARGETS` for `toy-v0`,
`GEN_START_TARGETS` for generated worlds), and the private book is *derived*:
`_seed_ladder` warms a fresh commitment forward to each of ten ages at a flat
`_WARMUP_QUARTERLY_RETURN`, then scales the ten rungs together to hit the
sleeve's target NAV. The player then pulls four fixed levers from that fixed
start.

This work package lets an analyst enter **their own book** — the liquid
weights *and* the vintage ladder, rung by rung — and play the decade from it.
The entered book is the book of record for the session: it is what the player
plays, what the twin mirrors, and what is stored so the session replays.

It also introduces the **kickoff commitment plan**: a ten-year × three-sleeve
schedule of intended commitments, generated from the entered book, editable
before the decade starts, and thereafter the baseline the annual lever measures
deviation against.

The default the screen opens with is *literally today's derived book and
today's pacing rate*. An untouched screen is the current product, byte for
byte. That is both the usability answer (nobody types 210 numbers from blank)
and the correctness answer (§8's round-trip test).

## 2. Decisions taken

Resolved with the owner on 2026-08-15.

| Item | Decision |
|---|---|
| Purpose | An **analyst surface** — enter a real institution's book — but **not** a one-shot report. The entered book is the starting point and remains the book of record as the environment is played. |
| Default | The screen is **pre-filled**, never blank. The default is the server's derived book (`_seed_ladder` output) and the flat fixed-rule commitment plan. |
| Twin's book | The twin **mirrors your book**. It starts from the same entered state and holds course, so decision alpha continues to isolate *decisions* and the allocation choice stays out of the comparison. |
| Field set | **Full book, ladder included** — liquid weights plus per-sleeve vintage rungs, overriding `_seed_ladder`'s derived shape. |
| Ranked | **Custom book ⇒ practice only.** Ranked play requires the default book and default plan. Any edit demotes the session. Existing leaderboard rows keep their exact present meaning; no key migration. |
| Commitment plan | **Editable at kickoff.** The lever shows deviation from *your* plan, not from the model's. |
| Pacing flex | On a session carrying a plan, an untouched lever commits **the plan's number for that year**, exactly. The policy pacing flex no longer acts silently; it is shown beside the plan number as a comparison. Sessions without a plan keep today's behaviour unchanged. (See §4.3 — this is a behavioural change and is deliberately scoped.) |
| Fitted-shape gap | Recorded as **ER-14** in `docs/engine-realism-register.md`, not hidden and not fixed. |

**Seal check:** `ah/play.py`, `ah/port/`, `ah/serve.py` and `ah/store/` are
outside the main / G3 / G5 pre-registration locks (`hashed_files` covers
`battery/*`, `data/derive.py`, `data/splice.py`, `eval/*`, `factors.py`,
`splits.py`, `strategies.py`). Nothing in this design touches a sealed file.

## 3. The contract — `ah/port/book.py`

A new module, pydantic, no pandas, mirroring the Step-3 state-contract style.

```
OpeningBook
  state_version: "opening-book-0.1"
  liquid:  {sleeve -> points}          # the world's liquid sleeve set (§3.1)
  private: {pe|pc|re -> [Rung, ...]}   # 10 rungs each, one per year of life
  cash:    float                       # default START_CASH = 2.0

Rung  (a serialized ClosedEndCohort document)
  vintage_year, committed, paid_in, unfunded,
  recallable_balance, cumulative_recycled,
  nav_true, nav_reported, cumulative_distributions

CommitmentPlan
  state_version: "commitment-plan-0.1"
  points: {pe|pc|re -> [float x 9]}    # one entry per DECISION WINDOW
```

**Nine entries, not ten.** Corrected 2026-08-16 against the engine. A 120-month
decade has nine decision windows (months 11, 23, … 107) and the engine fires
exactly nine commitments — `q > 0 and q % 4 == 0` gives quarters 4, 8, … 36,
vintage years 1…9. There is no commitment at q=0, because the opening book at
t0 *is* the entered ladder rather than something committed. Plan index `k` is
the k-th window and drives vintage year `k+1`; a tenth entry would be dead.

**The books total 98, not 100.** Both `START_TARGETS` and `GEN_START_TARGETS`
sum to 98.0 points; `START_CASH = 2.0` is the balance. Cash is therefore a
first-class entered field, not a constant, and the identity the validator and
the screen enforce is `sum(liquid) + sum(private) + cash = 100`.

Rungs are **not a new cohort model**. Each is exactly the document shape
`ClosedEndCohort.to_document()` emits, so entered rungs are instantiated with
`ClosedEndCohort.from_document` and re-validated by the existing Step-3 state
contract. Serialization is the contract, as it already is for `_scaled_cohort`.

Both objects carry a **digest** — SHA-256 over canonical JSON via
`ah/core/digest.py`. The book digest is what §5's ranked check compares against
the default book's digest; equality of digests, not of floats, is the test.

### 3.1 The sleeve set depends on the world's engine

`START_TARGETS` (toy-v0) has **five** liquid sleeves including `reits` at 8
points. `GEN_START_TARGETS` (generated worlds) has **four** — reits' 8 points
are folded into equity, giving equity 41. The entry screen must render the
sleeve set for the world being played, and `OpeningBook` validation must reject
a sleeve the world's engine does not carry. This is not cosmetic: entering a
reits weight against a generated world would silently create a sleeve the tape
has no returns for.

## 4. The numeric override

### 4.1 One parameter, deletable

```python
_build_portfolio(policy, targets, liquid, book: OpeningBook | None = None)
simulate_play(..., opening_book: OpeningBook | None = None)
```

`book=None` is today's path, untouched: `_seed_ladder` per private sleeve,
liquid sleeves set to `targets[asset]`, cash at `START_CASH`. When a book is
present, liquid sleeve values and cash come from it, and each private sleeve's
cohorts are built from its rungs via `from_document` instead of being derived.
Everything downstream — the waterfall, the appraisal filter, the linkage, the
forced-sale logic — is unchanged and unaware.

The whole feature is therefore one optional parameter threaded through two
functions, and §8's first test proves that removing it restores present
behaviour exactly.

### 4.2 The twin

`_mark_to_market` makes two `simulate_play` calls — the active session and the
twin. Both receive the **same** `opening_book`. The twin's only difference
remains `decisions=None`.

### 4.3 The plan replaces the flex, on plan-carrying sessions only

Today the lever's pre-fill is `plan_commitments(private_weight_reported,
targets)` — recomputed from the realized reported weight, which is why
`serve.py` must declare the audit-F4 caveat that the pre-fill is a quarter
stale, and why an untouched lever is *recomputed* at the commitment quarter
rather than sent.

With a stored `CommitmentPlan`, the pre-fill for year *k* is
`plan.points[sleeve][k]` — a number the analyst chose, not a function of a
weight that cannot be known without leaking the tape. An untouched lever
commits that number exactly. The F4 staleness caveat does not apply to a
plan-carrying session, because nothing is being approximated.

The policy pacing multiplier does not vanish; it stops being invisible. The
window shows, beside each plan number, what `plan_commitments` at the current
reported weight would have paced — labelled as the pacing rule's view, not as a
default that gets applied. The player may match it or ignore it.

**Scope fence:** this applies only to sessions carrying a plan. A session
created without `book`/`plan` — every session that exists today, and every
ranked session — keeps `plan_commitments` and the F4 caveat verbatim.

## 5. Server and session record

**`GET /book/default?run_id=…`** returns the derived `OpeningBook`, the default
`CommitmentPlan`, the world's sleeve set, and both digests. It is computed by
the same `_seed_ladder`/`plan_commitments` code the engine uses — never a
second implementation, or the round-trip test in §8 would be testing two
copies of the same mistake.

**`POST /sessions`** gains optional `book` and `plan`. Validation is
server-side and returns 422 with the failing rule named. `ranked` is forced to
`false` when either digest differs from the default's — enforced in
`create_session`, not in the app, because the app is not the authority.

**Storage.** Two additive columns on `sessions`, following the existing
`_SESSION_STAMPS` pattern in `store/db.py` (ALTER TABLE only when absent, old
rows read back NULL):

```
opening_book    TEXT   -- canonical JSON, NULL = derived default
commitment_plan TEXT   -- canonical JSON, NULL = fixed-rule default
```

NULL is the current product. No version break, no rewrite of existing rows,
and every session written before this WP replays exactly as it did.

**`_mark_to_market`** deserializes the book once per request, passes it to both
`simulate_play` calls, and reads the lever pre-fill from the stored plan when
present.

## 6. The screen — `app/src/BookEntry.tsx`

A new `mode` in `App.tsx`'s state machine, between world selection and
`RankedSetup` (the ranked choice comes after the book, because whether ranked is
*available* depends on whether the book was edited).

Layout, top to bottom:

- **Liquid weights and cash** — one row per sleeve in the world's set, plus
  cash, with a running total that must reach 100 (the default books are
  98 + 2 cash).
- **Private ladders** — one collapsible table per sleeve, ten rungs × seven
  editable fields (`vintage_year`, `committed`, `paid_in`, `unfunded`,
  `nav_true`, `nav_reported`, `cumulative_distributions`), with *reset this
  sleeve to the derived ladder* per table. `recallable_balance` and
  `cumulative_recycled` are in the contract but carried from the default —
  they are recycling mechanics, not allocation, and exposing them earns
  nothing on this screen.
- **Commitment plan** — a 10 × 3 grid, pre-filled flat at
  `target × _ANNUAL_COMMITMENT_RATE`, with reset-to-default.
- **Validity panel** — live: weights total, private weight against the
  15–40 % policy band, unfunded-to-NAV coverage, and a plain statement of
  whether this book is still the default (i.e. whether ranked is available).

The client validates **shape only** — totals, signs, the
`paid_in + unfunded = committed` identity. It computes no value, no NAV, no
coverage that feeds a decision; those come from the server (DN-3 W5, hard
invariant). The existing narrative-blindness and no-client-side-value tests
extend to cover the new component.

Usability rests entirely on the pre-fill and the per-sleeve resets: 3 sleeves ×
10 rungs × 7 fields is 210 inputs, and no one fills that from blank. The
expected interaction is "load the default, change the six numbers that differ
from my real book."

## 7. Guardrails and ER-14

**Refused** (422 / disabled commit): negative anything; `sum(liquid) +
sum(private) + cash ≠ 100`; a rung breaking the recycling identity
`paid_in + unfunded = committed + cumulative_recycled` (verified to 4e-16
across all thirty seeded rungs — note it is *not* the simpler
`paid_in + unfunded = committed`, which recycling can legitimately break, and
`_check()` enforces only `paid_in <= committed`); a sleeve
outside the world's set; a
plan year outside `[0, COMMIT_CAP_MULTIPLE × target × _ANNUAL_COMMITMENT_RATE]`
(the existing declared lever bound, reused via `validate_commitments`).

**Warned, not refused**: private weight outside the 15–40 % policy band. A real
book can be out of band — that is precisely the case an analyst wants to run —
and the play surface already models a band breach as a consequence rather than
an impossibility.

**ER-14** (new entry in `docs/engine-realism-register.md`, open):

> An entered ladder can sit arbitrarily far from the staircase `_seed_ladder`
> produces, and that staircase is the shape against which the pacing model, the
> call/distribution linkage and the ER-6 close-out were checked. An entered book
> can also open in a state the derived book can never reach — `nav_reported ≠
> nav_true` at t0, i.e. an appraisal filter that starts un-converged, where the
> seed ladder converges by construction (`cohort.report(cohort.nav_true)` at the
> end of warm-up). Nothing downstream is wrong; the calibration evidence simply
> does not extend to books shaped unlike the seeded one. A fix would mean
> re-fitting the pacing and linkage over a family of ladder shapes, which
> invalidates the sealed pacing figures in DN-5 §2.1.

## 8. Testing (TDD, in this order)

1. **Contract round-trip.** `OpeningBook` → document → `OpeningBook` is
   identity; digest is stable across the round trip and across key order.
2. **Deletability.** `simulate_play(opening_book=None)` reproduces the present
   opening book bit-for-bit — per-sleeve NAV, unfunded, cash, and the full
   decade's `PlayQuarter` sequence. This is the regression fence for every
   existing session.
3. **Round-trip equivalence** *(the load-bearing one)*. Fetch
   `GET /book/default`, submit it back as a custom `book`, and get a decade
   identical to the `book=None` decade. This proves the entry path and the
   derived path agree — a bug in serialization, scaling or reconstruction shows
   up here and nowhere else.
4. **Ranked demotion.** A book differing in one rung ⇒ `ranked=false` on the
   stored row and no leaderboard write, even when the request asks for ranked.
5. **Plan semantics.** An untouched plan commits the fixed-rule points; an
   edited plan drives the commitment for that year; a year over the 2× cap is
   refused with the bound named; a session with no plan still recomputes via
   `plan_commitments` (the §4.3 scope fence, tested explicitly).
6. **Determinism.** Same book + seed + decisions ⇒ identical digest; a session
   with a stored book replays identically after a service restart.
7. **Guardrails.** Each refused rule returns 422 naming the rule; the out-of-band
   private weight warns and proceeds.
8. **App.** `BookEntry` validation, reset-to-derived, the ranked-availability
   statement, and the no-client-side-value scan.

## 9. Work packages

| WP | Scope |
|---|---|
| `su-app-06a` | `ah/port/book.py` — contracts, digests, validation. Tests 1. |
| `su-app-06b` | The numeric override in `play.py`. Tests 2, 3 (engine half), 6. |
| `su-app-06c` | Server: `GET /book/default`, `POST /sessions` fields, store migration, ranked demotion, plan-driven pre-fill. Tests 3 (service half), 4, 5, 7. |
| `su-app-06d` | `BookEntry.tsx` and the `App.tsx` flow. Test 8. |
| `su-app-06e` | ER-14, `CHANGELOG.md`, `docs/current/README.md` register touch if needed. |

Each merges only on a green `scripts/run_gate.py` log per the standing
convention.

## 10. Out of scope

- **A non-flat commitment schedule** derived from default settings and the
  current portfolio — explicitly wanted by the owner, explicitly *later*. The
  flat fixed-rule path is the kickoff default for this WP, and
  `CommitmentPlan`'s shape (per-year points) already carries a non-flat
  schedule without a contract change.
- **File import** of a book (JSON/CSV from a spreadsheet, which is where real
  books live). Additive later: same `OpeningBook` document, a different way in.
- **Ranked custom books.** Deliberately closed off by §2's decision; reopening
  it means a book digest in the leaderboard key.
- **Policy fields** (spending rate, haircut, band) as entered values. The book
  is the allocation and the ladder; `Policy` stays at its defaults.
- **Re-fitting pacing or linkage** to arbitrary ladder shapes. That is ER-14's
  fix, an owner-level release event, not part of this WP.
