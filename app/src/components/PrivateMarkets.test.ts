/**
 * The ledger's reveal rule, pinned.
 *
 * A quarter's row exists for the player only once its closing month is on the
 * tape — the same in-timeline rule the wire follows (E2). Getting this wrong
 * leaks the future through a table instead of a chart, which is worse because
 * nobody would think to look for it there.
 */

import { describe, expect, it } from "vitest";
import { lastRevealedQuarter } from "./PrivateMarkets";

// quarters close on months 2, 5, 8, 11, ... (0-indexed), as ah.pacing emits
const QUARTERS = [2, 5, 8, 11, 14, 17];

describe("lastRevealedQuarter", () => {
  it("shows nothing before the first quarter closes", () => {
    expect(lastRevealedQuarter(QUARTERS, 0)).toBe(-1);
    expect(lastRevealedQuarter(QUARTERS, 2)).toBe(-1); // month index 2 not yet revealed
  });

  it("reveals a quarter the moment its closing month is on the tape", () => {
    expect(lastRevealedQuarter(QUARTERS, 3)).toBe(0);
    expect(lastRevealedQuarter(QUARTERS, 5)).toBe(0);
    expect(lastRevealedQuarter(QUARTERS, 6)).toBe(1);
    expect(lastRevealedQuarter(QUARTERS, 12)).toBe(3);
  });

  it("never runs past the last quarter it has", () => {
    expect(lastRevealedQuarter(QUARTERS, 120)).toBe(QUARTERS.length - 1);
  });

  it("is monotone in the pointer — the ledger cannot un-reveal", () => {
    let prev = -1;
    for (let m = 0; m <= 20; m++) {
      const q = lastRevealedQuarter(QUARTERS, m);
      expect(q).toBeGreaterThanOrEqual(prev);
      prev = q;
    }
  });
});
