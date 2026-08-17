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

/**
 * Render a points-of-100 figure (a book value, a value delta, an alpha) as
 * a compact dollar string.
 *
 * Two significant styles only, per the owner's ruling:
 *   - `$X.Ybn` for a billion or more (one decimal)
 *   - `$Xm` for anything smaller (no decimals)
 * Exactly zero renders as `"$0"` — neither `"$0m"` nor `"$0.0bn"` — so a
 * true zero never looks like a rounded-down small number.
 */
export function usd(points: number): string {
  if (!Number.isFinite(points)) return "—";
  if (points === 0) return "$0";
  const dollars = points * PER_POINT;
  const sign = dollars < 0 ? "-" : "";
  const abs = Math.abs(dollars);
  if (abs >= 1_000_000_000) {
    return `${sign}$${(abs / 1_000_000_000).toFixed(1)}bn`;
  }
  return `${sign}$${Math.round(abs / 1_000_000)}m`;
}
