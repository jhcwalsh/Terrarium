/**
 * The chart's units, pinned.
 *
 * The owner's note on the first vitrine build was blunt: "what does x1.29 on
 * equities mean - just use annualized returns like investors". These two
 * helpers are the whole of that change, so they get the tests: growth-of-1 in,
 * the units an allocator quotes out.
 */

import { describe, expect, it } from "vitest";
import { annualized, cumulativeGrowth, fmtCumulative } from "./FanChart";

describe("fmtCumulative", () => {
  it("reads growth-of-1 as a signed cumulative return", () => {
    expect(fmtCumulative(1.29)).toBe("+29%");
    expect(fmtCumulative(0.66)).toBe("−34%");
    expect(fmtCumulative(1)).toBe("+0%");
  });

  it("keeps the requested precision", () => {
    expect(fmtCumulative(1.0234, 1)).toBe("+2.3%");
    expect(fmtCumulative(0.9812, 1)).toBe("−1.9%");
  });
});

describe("annualized", () => {
  it("undoes compounding over the months actually revealed", () => {
    // exactly one year: annualized == cumulative
    expect(annualized(1.29, 12)!).toBeCloseTo(0.29, 10);
    // ten years of +29% total is a much smaller annual figure
    expect(annualized(1.29, 120)!).toBeCloseTo(1.29 ** 0.1 - 1, 10);
    // and it is signed the way a loss should read
    expect(annualized(0.5, 120)!).toBeLessThan(0);
  });

  it("refuses inputs with no annual meaning", () => {
    expect(annualized(1.1, 0)).toBeNull();
    expect(annualized(0, 12)).toBeNull();
  });

  it("round-trips against the compounding the chart draws", () => {
    const monthlyPct = new Array(24).fill(0.5); // +0.5% a month
    const growth = cumulativeGrowth(monthlyPct);
    const ann = annualized(growth[23], 24)!;
    expect(ann).toBeCloseTo(1.005 ** 12 - 1, 10);
  });
});
