/**
 * Full, capitalized sleeve display names for the book entry screen
 * (app-open-01 delta 3, owner-dictated 2026-08-16): no ticker/lowercase
 * codes ("pe", "hy", "eq") visible to the player anywhere on this screen.
 *
 * The CODES stay the data layer's own identifiers — `Book.liquid` /
 * `Book.private` keys, `aria-label`s (which are accessibility/test hooks,
 * not text the player reads), and every server contract are UNCHANGED. This
 * is a display-only lookup: one map, reused everywhere a sleeve name renders
 * as visible text on this screen (row labels, ladder headings, reset
 * buttons, the commitment-plan table).
 *
 * The exact names below are the owner's own list (2026-08-16); "reits" is
 * not in that list (the owner's reference world carries no reits sleeve),
 * so its label is this screen's own reasonable completion, not a verbatim
 * instruction.
 */
export const SLEEVE_LABEL: Record<string, string> = {
  equity: "Equities",
  bonds: "Bonds",
  hy: "High Yield",
  commodities: "Commodities",
  reits: "REITs",
  pe: "Private Equity",
  pc: "Private Credit",
  re: "Real Estate",
  cash: "Cash",
};

/** The sleeve's full display name, or the code itself if this screen has
 * not been told a label for it — degrading to something visible rather
 * than to `undefined`, for a sleeve id no world served here carries yet. */
export function sleeveLabel(id: string): string {
  return SLEEVE_LABEL[id] ?? id;
}
