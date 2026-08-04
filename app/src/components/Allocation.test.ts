/**
 * Pins the target-replay mirror to ah.core.institution's semantics: the
 * expected numbers below are hand-derived from START_MIX and the shift
 * rules (proportional in-group split). If institution.py changes, these
 * break — which is the point of having them.
 */

import { describe, expect, it } from "vitest";
import { replayTargets } from "./Allocation";

describe("replayTargets (institution.py target mirror)", () => {
  it("no decisions -> the start mix, summing to 1", () => {
    const t = replayTargets({});
    expect(t.equity).toBeCloseTo(0.3, 12);
    expect(t.pe).toBeCloseTo(0.25, 12);
    expect(Object.values(t).reduce((s, v) => s + v, 0)).toBeCloseTo(1, 12);
  });

  it("derisk moves 10pts growth->defensive, split proportionally", () => {
    const t = replayTargets({ "11": "derisk" });
    // growth 55pts: equity gives 10*(30/55), pe gives 10*(25/55)
    expect(t.equity).toBeCloseTo(0.3 - 0.1 * (0.3 / 0.55), 12);
    expect(t.pe).toBeCloseTo(0.25 - 0.1 * (0.25 / 0.55), 12);
    // defensive 20pts split evenly: bonds and pc +5pts each
    expect(t.bonds).toBeCloseTo(0.15, 12);
    expect(t.pc).toBeCloseTo(0.15, 12);
    expect(Object.values(t).reduce((s, v) => s + v, 0)).toBeCloseTo(1, 12);
  });

  it("a leanin after a derisk does not round-trip exactly (proportions moved)", () => {
    const t = replayTargets({ "11": "derisk", "23": "leanin" });
    expect(Object.values(t).reduce((s, v) => s + v, 0)).toBeCloseTo(1, 12);
    // hy/commodities/reits/re never move under derisk/leanin
    expect(t.hy).toBeCloseTo(0.05, 12);
    expect(t.re).toBeCloseTo(0.1, 12);
  });

  it("secondary moves 8pts pe->bonds in targets", () => {
    const t = replayTargets({ "11": "secondary" });
    expect(t.pe).toBeCloseTo(0.17, 12);
    expect(t.bonds).toBeCloseTo(0.18, 12);
    expect(Object.values(t).reduce((s, v) => s + v, 0)).toBeCloseTo(1, 12);
  });

  it("decision months apply in numeric order, not object-key order", () => {
    const a = replayTargets({ "23": "leanin", "11": "derisk" });
    const b = replayTargets({ "11": "derisk", "23": "leanin" });
    for (const k of Object.keys(a)) expect(a[k]).toBeCloseTo(b[k], 12);
  });
});
