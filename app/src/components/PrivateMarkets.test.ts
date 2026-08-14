import { describe, expect, it } from "vitest";
import { expiredCommitment, lastRevealedQuarter, pickLedgerRow } from "./PrivateMarkets";

const QUARTERS = [2, 5, 8, 11, 14, 17];

describe("lastRevealedQuarter", () => {
  it("shows nothing before the first quarter closes", () => {
    expect(lastRevealedQuarter(QUARTERS, 0)).toBe(-1);
    expect(lastRevealedQuarter(QUARTERS, 2)).toBe(-1);
  });

  it("reveals a quarter the moment its closing month is on the tape", () => {
    expect(lastRevealedQuarter(QUARTERS, 3)).toBe(0);
    expect(lastRevealedQuarter(QUARTERS, 12)).toBe(3);
  });

  it("never runs past the last quarter it has", () => {
    expect(lastRevealedQuarter(QUARTERS, 120)).toBe(QUARTERS.length - 1);
  });
});

describe("pickLedgerRow", () => {
  const twin = { calls: [1, 2, 3], distributions: [4, 5, 6] };

  it("prefers the session's own numbers", () => {
    const row = pickLedgerRow(twin, { calls_paid: 9, distributions_received: 8 }, 1);
    expect(row).toEqual({ calls: 9, distributions: 8, source: "yours" });
  });

  it("falls back to the twin when there is no session — browse and offline", () => {
    const row = pickLedgerRow(twin, null, 1);
    expect(row).toEqual({ calls: 2, distributions: 5, source: "twin" });
  });

  it("returns nothing when neither is available", () => {
    expect(pickLedgerRow(undefined, null, 1)).toBeNull();
  });
});

describe("expiredCommitment", () => {
  // ER-6's terminal lapse (audit F2): undrawn capital CANCELLED at the end of
  // a fund's life. It fires in one quarter of a decade, so the running total
  // is what keeps it on the page afterwards. The twin bundle carries no such
  // series, so this is a session-only line — browse mode shows nothing rather
  // than showing the twin's as if it were yours.
  it("is nothing without a session", () => {
    expect(expiredCommitment(null)).toBeNull();
  });

  it("is nothing when no commitment has ever expired", () => {
    expect(expiredCommitment({ expired_undrawn: 0, expired_undrawn_to_date: 0 })).toBeNull();
  });

  it("shows the quarter's own release when it happens", () => {
    expect(expiredCommitment({ expired_undrawn: 9.02, expired_undrawn_to_date: 9.02 })).toEqual({
      quarter: 9.02,
      toDate: 9.02,
      justHappened: true,
    });
  });

  it("stays visible in later quarters, as a running total", () => {
    expect(expiredCommitment({ expired_undrawn: 0, expired_undrawn_to_date: 9.02 })).toEqual({
      quarter: 0,
      toDate: 9.02,
      justHappened: false,
    });
  });

  it("treats the unrevealed nulls as nothing to show", () => {
    expect(expiredCommitment({ expired_undrawn: null, expired_undrawn_to_date: null })).toBeNull();
  });
});
