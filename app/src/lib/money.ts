/**
 * money.ts — the $10bn display denomination (app-open-01 item 1, owner
 * ruling 2026-08-16, worktree app-open-01-fixes).
 *
 * THE RULE: the server keeps scoring in points-of-100 — sealed alpha
 * definitions, leaderboard rows and session contracts are UNTOUCHED by
 * this file and never will be. Dollars are a DISPLAY DENOMINATION,
 * computed client-side only: the book is presented to the player as a
 * $10bn institution, so one scored point = $100m (BOOK_USD / 100).
 * `usd()` renders that mapping; it never feeds a value back into
 * anything that scores, ranks, or gets stored.
 */

/** The book's display size. A single constant: changing it rescales every
 * dollar figure on screen without touching a single scored number. */
export const BOOK_USD = 10_000_000_000; // $10bn, i.e. 1 point = $100m

const PER_POINT = BOOK_USD / 100;

/** app-open-01 review round, fix 1: the CIO dashboard used to caption its
 * money figures with the served `meta.unitLabel` ("$m"). That figure is
 * now rendered through `usd()` below instead, so the caption is retired —
 * this is the client-side replacement text, not a value derived from the
 * server. `cioview.py`'s `UNIT_LABEL` constant and the served field are
 * untouched; the client simply stops echoing it. */
export const DENOMINATION_NOTE = "USD, $10bn book";

/**
 * Render a points-of-100 figure (a book value, a value delta, an alpha) as
 * a compact dollar string.
 *
 * Two significant styles only, per the owner's ruling:
 *   - `$X.YYbn` for a billion or more (two decimals — $10m granularity,
 *     app-open-01 review round fix 3)
 *   - `$Xm` for anything smaller (no decimals)
 * Exactly zero renders as `"$0"` — neither `"$0m"` nor `"$0.00bn"` — so a
 * true zero never looks like a rounded-down small number.
 *
 * The bn/m boundary is decided AFTER rounding to the bn branch's own
 * precision ($10m), not before: `usd(9.9999)` is $999.99m before rounding,
 * which the old before-bucket-choice logic printed as `"$1000m"` — visibly
 * wrong once it rounds up to a whole billion. Rounding first makes it
 * `"$1.00bn"` (app-open-01 review round fix 3, the LOW boundary bug).
 */
export function usd(points: number | null | undefined): string {
  if (points == null || !Number.isFinite(points)) return "—";
  if (points === 0) return "$0";
  const dollars = points * PER_POINT;
  const sign = dollars < 0 ? "-" : "";
  const abs = Math.abs(dollars);
  const roundedTo10m = Math.round(abs / 1e7) * 1e7;
  if (roundedTo10m >= 1_000_000_000) {
    return `${sign}$${(roundedTo10m / 1_000_000_000).toFixed(2)}bn`;
  }
  return `${sign}$${Math.round(abs / 1_000_000)}m`;
}
