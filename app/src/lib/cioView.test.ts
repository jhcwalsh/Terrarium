/**
 * cov-01: unit tests for validateCioView's coverage-line fields
 * (unfundedToLiquid, breachLine, worstUnfundedToLiquid). These are new,
 * optional Liquidity fields (the same optionality as the existing
 * unfundedToNav/coverageAnchor) — before this file, validateCioView had
 * no dedicated unit test in TS at all; this establishes one, mirroring
 * tests/test_cioview.py's `_minimal_view` pattern on the Python side.
 */

import { describe, expect, it } from "vitest";
import type { CioView, PrivateQuarter } from "./cioView";
import { validateCioView } from "./cioView";

function pq(label: string, forecast: boolean): PrivateQuarter {
  return {
    label,
    forecast,
    calls: 1.0,
    distributions: 1.5,
    net: 0.5,
    navOpen: 30.0,
    navClose: 30.5,
    unfundedOpen: 15.0,
    unfundedClose: 14.0,
    callRateUnfunded: 0.0667,
    callRateNav: 0.0333,
    coverage: 0.459,
    expiredUndrawn: 0.0,
  };
}

/** Smallest payload that passes every check — the seed for defect tests. */
function minimalView(): CioView {
  return {
    meta: {
      runId: "r1",
      seed: "42",
      worldTitle: "t",
      worldVersion: "toy-v0.6",
      linkageVersion: "public-0.1",
      decisionAlphaVersion: "port-v4-ladder",
      asOfLabel: "Y1 Q1",
      asOfMonth: 2,
      plane: "reported",
      planesAvailable: ["reported", "true"],
      unitLabel: "$m",
      unitSuffix: "m",
      currency: "USD",
      watermark: "w",
      disclaimer: "d",
    },
    plan: {
      totalValue: 100.0,
      growthPct: null,
      netOfFlows: null,
      windowLabel: "Since inception",
      history: { values: [100.0, 100.5, 100.0 + 1e-9], worldStartIndex: 0 },
    },
    allocation: {
      goals: [{ id: "growth", label: "Growth", tolerancePct: 5.0 }],
      classes: [
        {
          id: "equity",
          label: "Equity",
          goalId: "growth",
          targetPct: 100.0,
          bandLoPct: 95.0,
          bandHiPct: 100.0,
          currentPct: 100.0,
          value: 100.0,
          returns: [1.0],
        },
      ],
      alertPolicy: { watchFraction: 0.75 },
    },
    performance: {
      periods: ["1Q"],
      annualisedFromIndex: 1,
      total: [1.2],
      benchmark: [1.1],
    },
    liquidity: {
      tiers: [{ id: "t1", tier: 1, label: "T1", note: "", value: 100.0 }],
      forecast12m: { distributions: 2.0, income: 0.0, calls: 3.0, payout: 1.0, net: -2.0 },
    },
    privateCashflows: {
      histCount: 1,
      classes: [{ id: "pe", label: "PE" }],
      series: { aggregate: [pq("Y1Q1", false)], pe: [pq("Y1Q1", false)] },
    },
  };
}

describe("validateCioView — coverage line (cov-01)", () => {
  it("passes a well-formed view with no coverage fields set (optional, like coverageAnchor)", () => {
    expect(validateCioView(minimalView())).toEqual([]);
  });

  it("passes when unfundedToLiquid/breachLine/worstUnfundedToLiquid are present and valid", () => {
    const v = minimalView();
    v.liquidity.unfundedToLiquid = 0.4;
    v.liquidity.breachLine = 1.0;
    v.liquidity.worstUnfundedToLiquid = 0.55;
    expect(validateCioView(v)).toEqual([]);
  });

  it("rejects a negative unfundedToLiquid", () => {
    const v = minimalView();
    v.liquidity.unfundedToLiquid = -0.1;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("unfundedToLiquid"))).toBe(true);
  });

  it("rejects a negative worstUnfundedToLiquid", () => {
    const v = minimalView();
    v.liquidity.worstUnfundedToLiquid = -0.1;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("worstUnfundedToLiquid"))).toBe(true);
  });

  it("rejects a breachLine that is not exactly 1.0", () => {
    const v = minimalView();
    v.liquidity.breachLine = 0.9;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("breachLine"))).toBe(true);
  });
});

describe("validateCioView — bandLoPct/bandHiPct (app-open-02 task 2)", () => {
  it("rejects lo === hi", () => {
    const v = minimalView();
    v.allocation.classes[0].bandLoPct = 50.0;
    v.allocation.classes[0].bandHiPct = 50.0;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("band"))).toBe(true);
  });

  it("rejects lo > hi", () => {
    const v = minimalView();
    v.allocation.classes[0].bandLoPct = 60.0;
    v.allocation.classes[0].bandHiPct = 40.0;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("band"))).toBe(true);
  });

  it("rejects a band on a cash class", () => {
    const v = minimalView();
    v.allocation.classes[0].id = "cash";
    v.allocation.classes[0].bandLoPct = 0.0;
    v.allocation.classes[0].bandHiPct = 10.0;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("cash") && e.includes("band"))).toBe(true);
  });

  it("passes an asymmetric band, not centred on the target, with the target outside it", () => {
    // minimalView's lone class must keep currentPct/targetPct summing to
    // 100 (the allocation-closes check) — the band itself is what's under
    // test here, and validateCioView never requires the target to sit
    // inside its own band (serve.py's _alert_level docstring: it may
    // legally sit outside).
    const v = minimalView();
    v.allocation.classes[0].bandLoPct = 10.0;
    v.allocation.classes[0].bandHiPct = 20.0;
    expect(validateCioView(v)).toEqual([]);
  });

  it("allows a null band on a non-cash class (branch-review I1: a book-silent sleeve carries no band)", () => {
    const v = minimalView();
    v.allocation.classes[0].bandLoPct = null;
    v.allocation.classes[0].bandHiPct = null;
    expect(validateCioView(v)).toEqual([]);
  });

  it("rejects a partial (one-sided) null band on a non-cash class", () => {
    const v = minimalView();
    v.allocation.classes[0].bandLoPct = 10.0;
    v.allocation.classes[0].bandHiPct = null;
    const errors = validateCioView(v);
    expect(errors.some((e) => e.includes("missing bandLoPct/bandHiPct"))).toBe(true);
  });
});
