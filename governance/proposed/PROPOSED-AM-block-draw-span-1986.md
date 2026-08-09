# PROPOSED amendment — move `bootstrap_v1.block_draw_span` to 1986-01

> **Addendum 2026-08-09 (post-FSEXT):** with `funding_spread` now extended
> both ways on CP-bill (`ah.data.funding_extend`, verified in
> `docs/data/FSEXT-REPORT.md`: TED-overlap corr 0.965 on 433 months, filled
> 1934-01 backward and post-2022 forward), the ratifiable floor is no longer
> 1986-01 but **1984-01, where `hqm_curve` binds**. At ratification the owner
> chooses the target (1986 on the original text, or 1984 with the
> funding_spread proxy months included under the same disclosure discipline
> and the D6/F1 recreation rulings). The entry below is written for 1986;
> a 1984 ratification updates `to:`, the binding factor (-> hqm_curve), and
> the disclosure to name both proxy families.

**Status: DRAFT — awaiting owner ratification. Nothing in this file is in
force, and Stage 1 shipping does NOT apply it.** The authority is
`governance/amendment-log.yaml`; this draft never enters it until the owner
says so. There is no deadline: both stages of WP-DATA-VOLEXT build and
validate without this change, and the owner may reasonably want Stage-1
overlap evidence, Stage-2 held-out results, or neither, before signing — or
may choose to leave the span where it is permanently.

**What ratification triggers (all of it, not a subset):**

1. The entry below appended to `governance/amendment-log.yaml`.
2. `pre-registration.yaml` edits: `block_draw_span` start 1990-01 → 1986-01,
   `block_draw_span_binding_factor` equity_vol → funding_spread, and the
   `block_draw_span_consequence` prose updated to state the new binding
   chain (funding_spread/TED 1986-01, then hqm_curve 1984-01) and the
   proxy-share disclosure below.
3. The VXO rule moves from `ah.data.vol_extend` into the sealed
   `ah.data.splice.PROXY_RULES` registry (with the log-log transform), and
   `ah.data.derive` wires `equity_vol` to the extended series on the factor
   read path.
4. A **re-seal**: splice.py and derive.py are hashed files, so
   `ah.eval.prereg.verify()` fails by design until the pre-registration is
   re-sealed at the new hashes.

## The entry, ready for `append_amendment`

```yaml
amendment_id: AM-<date>-<seq>          # assigned at ratification
type: protocol_change
date: <ratification date>
post_hoc: false
rationale: >-
  Extends bootstrap_v1.block_draw_span from 1990-01..2020-12 to
  1986-01..2020-12 on the strength of the stage-1 VXO extension of
  equity_vol (rule PROXY-EQUITY-VOL-VXO-V1): fred.VXO is an OBSERVED
  implied-vol index from 1986-01, spliced onto fred.VIX by log-log
  regression on the 1990+ overlap, with the overlap fit reported in
  docs/data/ before this amendment was ratified. funding_spread (TED,
  1986-01) becomes the binding factor; reaching further back requires
  extending it and then hqm_curve (1984-01), separate work packages.
payload:
  sealed_field: bootstrap_v1.block_draw_span
  from: {start: "1990-01-01", end: "2020-12-01", months: 372}
  to: {start: "1986-01-01", end: "2020-12-01", months: 420}
  binding_factor_from: equity_vol
  binding_factor_to: funding_spread
  disclosure: >-
    1986-89 equity_vol blocks contain PROXY months (observation-derived: a
    deterministic transform of observed VXO, flagged is_proxy with rule
    PROXY-EQUITY-VOL-VXO-V1). Any benchmark statistic over the extended
    span must disclose the proxy share. Pre-1986 remains unreachable by
    the benchmark; if the stage-2 model backcast is ever admitted, the
    bootstrap would resample MODEL OUTPUT there, which is a WEAKER
    benchmark posture than the current restricted-window disclosure, not
    a stronger one.
```

## What this amendment does NOT claim

- It does not make `bootstrap-v1` a fair comparator over pre-1990 episodes
  (the task file's own out-of-scope list, carried here verbatim in spirit):
  1986-89 becomes reachable on observation-derived proxy data; nothing
  before 1986 changes.
- It does not retroactively touch any sealed G2 verdict. The sealed
  campaign record stands; the extended span defines the benchmark only for
  future campaigns, which would say so in their own pre-registrations.
- It does not, BY ITSELF, admit the stage-2 model backcast into the span.
  **Owner ruling D6 (2026-08-09, recorded in
  `docs/superpowers/specs/2026-08-09-volext-decisions.md`): the backcast IS
  admissible** — recreating a series from the era's own observed daily
  returns through a held-out-audited mapping is reconstruction, not the
  platform modelling its own null. This superseded the earlier draft of this
  file, which argued against admission; that argument (a partly-fitted
  benchmark is a weaker null pre-1986) remains on the record as the
  counterposition, not as the ruling. Admission still requires its own
  ratified amendment naming the HAR months span-bearing, and is MOOT until
  `funding_spread` and its successors extend: the joint panel, not
  equity_vol, is what binds below 1986.
