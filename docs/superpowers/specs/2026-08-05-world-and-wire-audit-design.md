# The world register and wire audit — `ah audit`

**Date:** 2026-08-05
**Owner ask:** "a dashboard that allows us to review the worlds that have been
created and check consistency ... also check the news wire that is being
created. Getting under the hood and validation. No need to duplicate effort
from prior dashboards."
**Status:** design approved, awaiting implementation plan

---

## Why

Two things nobody can currently see.

**There is no way to list the worlds that exist.** `src/ah/store/worlds.py`
has exactly `get_world` and `save_world` — no listing helper anywhere in the
repo. `ah credibility` and `ah inspect` both require a world or run id you
already know. The store today holds two worlds, *both* titled "The Long
Stagflation" (the `001` G0 block and the `301` toy-v0.3 block), and the four
presets the app actually plays live as JSON files outside the store entirely.
Nothing shows that population as one thing.

**The wire has no inspection surface at all.** `ah/feed.py` builds the tier-1
artifacts at bundle time and only the React app ever renders them, revealed
behind the pointer. Nothing reconciles a wire item against the tape it claims
to describe. ER-2 — central-bank statements announcing decisions no committee
took — was found by *playing the game*, and the toy-v0 percent/decimal unit
bug the same way. Both were rendering-layer failures in exactly this surface.

## The constraint that shapes everything

**Every artifact template renders its numbers into prose.** This is not a
stylistic observation; it determines the whole design of pane B:

- `central_bank_statement` returns `lines: [str, str]` — the rate exists only
  inside `"The policy rate stands at 5.74%, little changed over the quarter."`
  There is no numeric field to check.
- `release_page` rows carry `value` and `prior` as pre-formatted strings
  (`"5.7%"`, `"626bp"`).
- `quarterly_statement` returns `lines: [str, ...]` with the return, YTD,
  total value and net flow formatted into sentences.
- `newspaper_front_page` returns a lead and stories as strings.

Not one payload carries a raw float. So the audit **re-parses the rendered
text** and compares it to the tape. That is forced by the data, and it is also
the check worth having: the inputs to the templates are trivially correct
(they are read straight off `EnginePaths`), and every real defect found so far
lived in the formatting — the unit convention, the phantom decision. Checking
the inputs would have caught neither.

## Decisions taken

| # | Decision | Choice |
|---|---|---|
| 1 | What it catches | **Wire items that misreport their tape**, and **worlds that are not what they claim relative to each other**. Re-validation drift and reproduction drift were considered and explicitly declined by the owner. |
| 2 | World population | **Both** — store rows and `src/ah/presets/*.json`, unified in one register with the source tagged. |
| 3 | Delivery | **A generated static HTML page** from a new CLI command, matching `ah inspect` and `ah credibility`. Deterministic and byte-diffable. |
| 4 | Reference for each pane | Worlds are checked against **their own declarations**; wire items against **their own tape**. Neither is the reference any existing surface uses. |

## What this deliberately does not duplicate

| Existing surface | Its reference | Why this is different |
|---|---|---|
| `ah credibility` | declared *priors* (one allocator's plausible bands) | this checks a world against **its own spec**, not against a prior |
| `ah inspect` | one run, rendered as figures | this is cross-world, and reconciles text rather than drawing paths |
| `ah battery` | sealed stylized-fact thresholds | this is not sealed, cannot fail a build, and judges no stylized facts |
| `ah chronicle` | the append-only event log | this reads generated artifacts, not events |

## Architecture

A package from the start. `credibility.py` reached ~450 lines and
`programme.py` ~1,000; two more panes in a flat module would repeat that.

```
src/ah/audit/__init__.py     public API: build_audit, render_audit_page
src/ah/audit/register.py     world discovery, declared-vs-realized, distinguishability
src/ah/audit/wire.py         per-item tape reconciliation
src/ah/audit/page.py         assembly, CSS, self-contained HTML
```

One read-only addition elsewhere: **`list_worlds(conn)`** in
`src/ah/store/worlds.py`, returning `world_id`, `spec_version`, `status`,
`created_at` and the parsed document, ordered by `created_at`. It does not
exist today and both panes need it.

Dependencies point downward as the repo requires: `ah.audit` imports
`ah.core`, `ah.feed`, `ah.artifacts`, `ah.store` (read helpers only), `ah.play`.
Nothing imports `ah.audit` except the CLI and its tests.

## Components

### Pane A — the world register (`register.py`)

**Discovery.** Store rows via `list_worlds`, plus every `src/ah/presets/*.json`
validated through `WorldSpec` and projected with `project_numeric`. Each row
carries its source (`store` / `preset`), world id, title, status, spec version,
created-at, `engine_defaults.generator_id` and the resolved generator version,
horizon, and regime mode.

**Declared versus realized.** The spec declares a regime sequence — segments of
`{regime, from_quarter, to_quarter}`, inclusive, tiling the horizon under V10.
The tape realizes something. For each declared segment, report what the tape
actually did over those months (mean inflation, mean policy rate, mean spread,
crisis months) and whether it is consistent with the segment's own label.

**This check applies only in `regimes.mode == "sequence"`.** In
`transition_matrix` mode every path draws its own regime sequence, so there is
no single declared assignment to compare against; in `unconditional` mode
there are no regimes at all. Those worlds render the row with a stated reason
rather than a silent blank.

**Distinguishability.** A per-world vector of decade statistics — mean
inflation, terminal policy rate, mean spread, crisis months, worst equity
drawdown, annualized equity return — with each component divided by a
**declared scale** (in the statistic's own units) rather than z-scored across
the population. Six worlds is far too small a population for z-scores to mean
anything, and a declared scale keeps the distance interpretable and stable as
worlds are added. Pairwise distances below a declared threshold are flagged.

Scales and threshold are declared priors in the module, editable, in the same
idiom as `credibility.PLAUSIBLE` and `programme.PROGRAMME_PLAUSIBLE` — a flag
is an invitation to look and cannot fail a build.

**Expected duplicates are not findings.** Two worlds that share a narrative
title across engine-version id blocks (the `001`/`301` pair) or that name each
other through `provenance.source.parent_world_id` are labelled as an expected
lineage pair rather than reported as drift. A register that cried wolf about
its own versioning convention would be ignored within a week.

### Pane B — the wire audit (`wire.py`)

For each world, build the tier-1 feed via `ah.feed.build_tier1_feed` and check
every item against the tape. Each check yields PASS or FAIL, and a FAIL carries
the parsed value, the expected value, and the item's month.

| item type | reconciled against |
|---|---|
| `release_page` | CPI row parses to `paths.inflation[m]`; its prior to `[m-1]`; the HY spread row to `paths.spread[m]` in bp and its prior to `[m-1]` |
| `cb_statement` | the rate parsed out of `lines[0]` equals `paths.rate[m]` **under the percent/decimal convention** — the template divides by 100 on the way in, and this is precisely where the unit bug lived; the stated move in bp equals the change from `[m-3]`, and the "little changed" wording appears if and only if that move is under 5bp |
| `quarterly_statement` | quarter return equals `total[m]/total[m-3] - 1` for the **hold-course institution `ah.feed` itself uses** (`simulate_institution(paths, None)` — the same object, re-derived, so the audit checks the rendering rather than re-deriving a different twin); YTD against the year-start; total value against `total[m]`; peer bands ordered `p25 <= p50 <= p75`; the percentile phrase consistent with the bands it was computed from |
| `wire_digest` (crisis onset) | an item exists at month `m` if and only if `paths.crisis` transitions 0 → 1 at `m` |
| `newspaper` | every story traceable to an earned `headline_events` trigger at that month — no story without a cause, no cause without a story |
| the feed as a whole | every month inside the horizon; monthly items present for every month; quarterly items only on quarter-closing months; sorted by `(month, type)`; **byte-identical on a second build** |

Parsing tolerance follows the formatting: a value printed to one decimal place
is compared at that precision, not at float equality. The tolerance is derived
from the format string rather than hardcoded, so a change to the formatter
cannot silently loosen the check.

### The CLI surface

```
ah audit [--seed N] [--peer-paths N] [--no-wire] [--out PATH]
```

- `--seed` (default `771204`, the seed the presets and the credibility console
  already use): the tape seed for any world with no run record. A world that
  *has* run records uses the seed of its most recent one, so the audit reads
  the tape that was actually played; the register states which seed each row
  used, because a reconciliation is only meaningful against a named tape.
- `--peer-paths` (default to be set after measurement, see *Consequences*):
  passed to `build_tier1_feed` as `n_peer_paths`. The peer bands only need to
  be internally ordered for the audit's purposes, so this can be far smaller
  than the bundle's production value.
- `--no-wire`: register only, skipping pane B — the fast path when you want
  the population and not the reconciliation.
- `--out` (default `audit.html`), written with `newline="\n"` for byte
  stability, matching `credibility_cmd`.

Every string echoed to the console stays ASCII (Windows cp1252); the HTML file
may use Unicode freely.

### Page assembly (`page.py`)

One self-contained document: no external stylesheet, no CDN, no `<script>`, no
`src=`. Reuses the console's existing palette variables so the three admin
surfaces look like one system. A summary band at the top states the counts —
worlds registered, wire items checked, failures — so the answer to "is anything
wrong" does not require scrolling.

## Data flow

```
list_worlds(conn) + presets/*.json
  -> WorldSpec.model_validate -> project_numeric        (one NumericWorld per row)
  -> run_path(world, seed)                              (the tape)
      -> register: declared-vs-realized, distinguishability
      -> build_tier1_feed(...) -> wire: per-item reconciliation
  -> render_audit_page() -> one HTML file
```

Deterministic throughout: the seed comes from the world's most recent run
record where one exists and from `--seed` (default `771204`) otherwise, and no
RNG is drawn in this package. Every register row states the seed it used.

## Error handling

- A preset file that fails `WorldSpec` validation is **listed with its error**
  rather than crashing the page — a malformed world is exactly the thing the
  register exists to show.
- A world whose horizon is too short to build a feed renders the register row
  and a stated "no wire" note.
- An unparseable wire string is a **FAIL, not a skip**. If the audit cannot
  read a rendered number, that is a finding about the rendering, and silently
  passing it would defeat the pane.
- A store that cannot be opened is a hard error: the register cannot be honest
  about a population it could not read.

## Testing

**Mutation-first, which is the lesson of the last six tasks.** Every
reconciliation check must be proven to fail against a deliberately corrupted
item, not merely to pass against a good one:

- a `cb_statement` whose rate is off by 25bp
- a `cb_statement` that says "little changed" across a 40bp move
- a `release_page` carrying the previous month's value as the current one
- a crisis digest emitted on a calm month, and a crisis onset with no digest
- a `quarterly_statement` with peer bands out of order
- a rate rendered in percent where the tape is decimal (the historical bug)

Plus: determinism (same worlds and seed → byte-identical page), the
self-containment assertion applied to the whole page rather than one block,
`list_worlds` ordering, and an import-graph guard that `ah.audit` imports no
writer — the same AST test pattern as `tests/test_programme_guard.py`.

## Scope

**In:** `src/ah/audit/` (four modules), `list_worlds` in `src/ah/store/worlds.py`,
an `ah audit` CLI command, tests as above, `CHANGELOG.md`.

**Out:** re-validation drift and reproduction/digest drift (declined by the
owner); any change to how the wire is generated; any change to a template;
tier-2 authored artifacts; anything the player sees; any write path.

## Consequences

- Building a feed runs peer paths per world, which is the expensive part.
  **Timing will be measured before a default is chosen**, not discovered at
  gate time.
- The register will very likely flag the `001`/`301` pair on first run. That is
  correct behaviour and is why the expected-lineage rule above exists.
- Declared scales and the distinguishability threshold are one person's priors.
  They will be wrong somewhere on first contact, and that is the same bargain
  the credibility console already makes.

## What this does not touch

- **No write path.** The package reads; an import-graph test enforces it.
- **Not in the pre-registration seal**, and it judges nothing that is.
- **No scored-path arithmetic**, no `PLAY_ALPHA_VERSION` or
  `DECISION_ALPHA_VERSION` bump.
- **Nothing under `schemas/` or `mappings/`** — read-only vendored and sealed truth.
- **No template changes.** If a reconciliation fails, the finding is recorded;
  fixing the template is a separate, owner-decided change.

---

*Not investment advice.*
