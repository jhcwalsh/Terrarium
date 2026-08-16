# Policy Targets and Reporting Ranges — Design

*2026-08-16 · Approved design for `su-app-07`: separate the institution's
**policy targets** from its **opening values**, and report per-sleeve band
breaches. Successor to su-app-06 (opening book entry).*

---

## 1. What this is

su-app-06 let an analyst enter an opening book. But one number still does two
jobs: `start_targets` sets the opening sleeve values (`play.py:513` —
`sleeve.value = targets[asset]`) *and* is the basis the commitment programme
paces against. An institution cannot say "our SAA target for equity is 35, we
are actually at 33 today, and our band is 30–40."

This work package separates the two and adds bands that **report**.

**Verified before writing this.** `targets` is consumed in exactly four places:

| `play.py` | use |
|---|---|
| `:513`, `:519` | the opening values (the conflation this WP removes) |
| `:704` | `plan_amount = targets[asset] * _ANNUAL_COMMITMENT_RATE * multiplier` — the pacing |
| `:256` | the commitment cap bound |
| `:162` | `_policy_private_weight` — the SAA private share the pacing flex reads |

Nothing else reads it, and **nothing rebalances toward it**: `_rebalance` is
called from two places only (`play.py:675,677`), the *derisk* and *leanin*
actions. Weights drift freely for the whole decade. That is the pre-existing
behaviour and this WP does not change it (§7).

## 2. Decisions taken

Resolved with the owner on 2026-08-16.

| Item | Decision |
|---|---|
| Shape | **Option B** — targets become a separate entered field; opening values stay in the book. |
| Ranges | **Report breaches only.** No rebalancing, no forced trades, no effect on any number the engine produces. |
| Default | Targets absent ⇒ targets *are* the book's own weights, so every existing session is byte-identical. Ranges absent ⇒ no per-sleeve reporting. |
| Rebalancing to target | **Out of scope** — a release event (§7). |

## 3. The contract — additive on `OpeningBook`

```
OpeningBook  (state_version bumps to "opening-book-0.2")
  liquid:  {sleeve -> points}            # opening VALUES  (unchanged)
  private: {pe|pc|re -> [Rung, ...]}     # opening VALUES  (unchanged)
  cash:    float                         # unchanged
  targets: {sleeve -> points} | None     # NEW - the SAA. None => derive from values.
  ranges:  {sleeve -> [lo, hi]} | None   # NEW - reporting bands, in points. None => no bands.
```

Both new fields are optional, so a `0.1` document still validates and still
means exactly what it meant. `targets` covers **all eight sleeves** including
the privates; `ranges` may cover any subset — a sleeve with no range is simply
never flagged.

**Validation** (in `validate_book`, where the rest lives):
- `targets`, when present, names exactly the world's sleeve set and sums with
  cash to 100, on the same identity the values obey.
- `ranges`, when present, names only sleeves in that set, and each is
  `0 <= lo < hi <= 100`.
- A target outside its own range is **allowed and warned**, not refused — an
  institution can hold a policy it is currently out of compliance with, and
  refusing it would be the tool arguing with the analyst.

## 4. What separating them actually changes

When `targets` is present it becomes the dict passed as `start_targets`, while
the opening values come from the book. The consequence is real rather than
cosmetic: **the commitment programme paces off the policy target, not the
drifted actual.** An institution three points overweight equity keeps
committing to its SAA, which is what a pacing policy is for.

Two knock-ons, both deliberate:

- **The commitment cap basis follows the target.** su-app-06's fix wave rebased
  the cap onto the entered book's own NAV (`OpeningBook.target_nav()`), because
  at that point the book was the only statement of size. With an explicit
  target, the target is the better basis and the three enforcement points
  (`serve.py` door, `validate_plan`, `play.py:621`) must agree on it — all
  three, as that fix established, or a 422 becomes a 500.
- **`_policy_private_weight` becomes meaningful.** It reads
  `sum(private targets) / (sum(targets) + cash)` — with targets equal to values
  that is the actual weight; with a real SAA it is the policy weight, which is
  what DN-5 §2.1 intended.

## 5. Breach reporting is a read-layer feature — no engine change

`PlayQuarter` already records `liquid_values`, `private_true`,
`private_reported`, `nav_true`, `nav_reported` and `cash` (`play.py:278-330`).
Per-sleeve weights are therefore derivable from what is already captured, and
**no engine code changes for the reporting half of this WP.**

The vocabulary also already exists: `app/src/lib/cioView.ts:30-37` defines
`AlertLevel = "ok" | "watch" | "breach"` with exactly this meaning — *"Band
status for a weight against its target: ok inside; watch within the alert
threshold of the edge; breach outside."* This WP populates that contract rather
than inventing a parallel one.

Breaches are computed server-side (DN-3 W5) and served on the session document
per sleeve, per plane: the weight, its target, its band, and the `AlertLevel`.

## 6. The screen

`BookEntry.tsx` gains, on the liquid row and once per private sleeve: a
**target** input and a **lo/hi** pair, all pre-filled — target from the served
default (equal to the value), range left empty. A sleeve's row shows its
implied weight beside its target so the drift is visible while typing.

Client validates shape only: totals, signs, `lo < hi`. The band *status* is the
server's, not the client's.

## 7. Out of scope

- **Rebalancing to target, band-triggered or otherwise.** Adding it changes
  every decade's outcome, invalidates leaderboard comparability across the
  change, and needs `TOY_ENGINE_VERSION` and a play-alpha bump. That is a
  release event and an owner decision, not a line in this WP.
- **Fixing `DecisionWindow.tsx`'s claim that *hold* rebalances to target.** It
  does not (§1). The copy is wrong today, independently of this WP; it is
  recorded here and should be corrected, but correcting copy is not this
  design's business to bundle.
- Changing `Policy.private_weight_range`, the existing aggregate 15–40% band.
  Per-sleeve ranges sit alongside it; they do not replace it.

## 8. Tests

1. **Deletability.** `targets=None` and `ranges=None` reproduce su-app-06's
   behaviour bit-for-bit; the existing suites are the fence.
2. **Separation bites.** A book whose targets differ from its values produces a
   *different decade* from one where they are equal — because pacing follows
   the target. Assert on the decade, not the pre-fill. (su-app-06 shipped a
   defect that asserting on the pre-fill would have hidden.)
3. **Cap agreement.** A plan legal under the target passes all three
   enforcement points; one over it is refused at every one of them with the
   rule named — never a 500.
4. **Breach reporting.** A sleeve outside its band reports `breach`; inside but
   near the edge reports `watch`; comfortably inside reports `ok`. A sleeve with
   no range never reports at all.
5. **Reporting changes nothing.** The same session with and without `ranges`
   produces an identical decade — proof the bands are inert.
