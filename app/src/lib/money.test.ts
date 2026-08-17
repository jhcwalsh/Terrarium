/**
 * money.ts acceptance (app-open-01 item 1): the $10bn display denomination.
 * usd() is the ONLY place points become a dollar string; every consumer in
 * the app is expected to call it rather than re-deriving the scale.
 */

import { describe, expect, it } from "vitest";
import { BOOK_USD, usd } from "./money";

describe("BOOK_USD", () => {
  it("is the $10bn constant the whole formatter is built on", () => {
    expect(BOOK_USD).toBe(10_000_000_000);
  });
});

describe("usd (app-open-01 item 1)", () => {
  it("renders exactly zero as a bare $0, not $0m or $0.0bn", () => {
    expect(usd(0)).toBe("$0");
  });

  it("renders the full 100-point book as $10.0bn", () => {
    expect(usd(100)).toBe("$10.0bn");
  });

  it("renders a billion-plus figure to one decimal", () => {
    expect(usd(115.7)).toBe("$11.6bn");
  });

  it("renders a sub-billion figure in whole millions", () => {
    expect(usd(0.5)).toBe("$50m");
  });

  it("renders a negative sub-billion figure with the minus before the dollar sign", () => {
    expect(usd(-2.33)).toBe("-$233m");
  });

  it("renders a negative billion-plus figure the same way", () => {
    expect(usd(-15)).toBe("-$1.5bn");
  });

  it("is not a value that feeds back into anything scored — a non-finite input is NA, not 0", () => {
    expect(usd(NaN)).toBe("—");
    expect(usd(Infinity)).toBe("—");
  });
});
