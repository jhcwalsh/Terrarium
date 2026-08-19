# ER-14 red ledger — transient, deleted in `er14-05`

The suite is legitimately red between the first mechanism commit
(`er14-02` Task M2) and the golden re-pin sweep (`er14-05` Task R4).
Changing return equations invalidates value goldens, run digests and
committed bundles across every world.

**Rules** (`docs/superpowers/plans/2026-08-18-er14-implementation.md`,
branch-strategy section):

- A failure **not** on this ledger is a **STOP** — diagnose before proceeding.
- Every WP close-out task appends its new expected-red entries and re-runs
  the full suite to confirm the failing set equals this ledger exactly.
- `er14-05` Task R4 drives the ledger to empty and **deletes this file** in
  that commit. The ledger never reaches `main`.

## Entries

| test id | cause | cleared by |
|---|---|---|
| _(none yet — opened clean at Task M1, before any mechanism edit)_ | | |
