/**
 * money.ts acceptance (app-open-01 item 1): the $10bn display denomination.
 * usd() is the ONLY place points become a dollar string; every consumer in
 * the app is expected to call it rather than re-deriving the scale.
 */

import { describe, expect, it } from "vitest";
import { BOOK_USD, DENOMINATION_NOTE, usd } from "./money";

describe("BOOK_USD", () => {
  it("is the $10bn constant the whole formatter is built on", () => {
    expect(BOOK_USD).toBe(10_000_000_000);
  });
});

describe("DENOMINATION_NOTE", () => {
  it("is the client-side replacement for the retired meta.unitLabel caption", () => {
    expect(DENOMINATION_NOTE).toBe("USD, $10bn book");
  });
});

describe("usd (app-open-01 item 1; review round fix 3 for bn precision)", () => {
  it("renders exactly zero as a bare $0, not $0m or $0.00bn", () => {
    expect(usd(0)).toBe("$0");
  });

  it("renders the full 100-point book as $10.00bn", () => {
    expect(usd(100)).toBe("$10.00bn");
  });

  it("renders a billion-plus figure to two decimals ($10m granularity)", () => {
    expect(usd(115.7)).toBe("$11.57bn");
  });

  it("renders a sub-billion figure in whole millions", () => {
    expect(usd(0.5)).toBe("$50m");
  });

  it("renders a negative sub-billion figure with the minus before the dollar sign", () => {
    expect(usd(-2.33)).toBe("-$233m");
  });

  it("renders a negative billion-plus figure the same way", () => {
    expect(usd(-15)).toBe("-$1.50bn");
  });

  it("is not a value that feeds back into anything scored — a non-finite input is NA, not 0", () => {
    expect(usd(NaN)).toBe("—");
    expect(usd(Infinity)).toBe("—");
  });

  it("treats null/undefined as NA, same as a non-finite input (review round fix 1: usd() now takes every CioDashboard money() call site, including optional fields)", () => {
    expect(usd(null)).toBe("—");
    expect(usd(undefined)).toBe("—");
  });

  it("rounds to the bn branch's own precision BEFORE choosing the branch, so a value that rounds up to a whole billion renders as bn, not as 4 digits of m (review round fix 3, the LOW boundary bug)", () => {
    expect(usd(9.9999)).toBe("$1.00bn");
  });
});
