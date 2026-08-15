/**
 * cio-02 task 4: the CIO view fetch policy inside Play.
 *
 * Play itself has no existing test file (mounting it needs a live/mocked
 * session service plus a WorldBundle fixture, which is out of scope for
 * this scaffold toggle — see task-4-brief.md Step 1). This file tests the
 * one extracted, pure seam: the fetch key that decides when the CIO view
 * must be refetched.
 */

import { describe, expect, it } from "vitest";
import { cioFetchKey, cockpitClass, peerTabs } from "./Play";

describe("cio view fetch policy", () => {
  it("refetches when the reveal pointer moves", () => {
    expect(cioFetchKey("s", 12, "reported", 0)).not.toBe(cioFetchKey("s", 15, "reported", 0));
  });

  it("refetches when the plane changes, same pointer", () => {
    expect(cioFetchKey("s", 12, "reported", 0)).not.toBe(cioFetchKey("s", 12, "true", 0));
  });

  it("is stable when nothing moved", () => {
    expect(cioFetchKey("s", 12, "true", 2)).toBe(cioFetchKey("s", 12, "true", 2));
  });

  // I-1: deciding a window updates session.decisions without moving
  // revealed_months (the pointer only advances on advance()), so the CIO
  // dashboard must refetch on decisionCount alone, same pointer and plane.
  it("refetches when a decision lands, same pointer and plane", () => {
    expect(cioFetchKey("s", 12, "reported", 1)).not.toBe(cioFetchKey("s", 12, "reported", 2));
  });
});

describe("cockpit layout mode", () => {
  it("marks the vitrine as a cockpit only in cio mode", () => {
    expect(cockpitClass("cio", "reported")).toContain("cockpit");
    expect(cockpitClass("book", "reported")).not.toContain("cockpit");
  });
  it("keeps the plane class in both modes", () => {
    expect(cockpitClass("cio", "true")).toContain("plane-true");
    expect(cockpitClass("book", "true")).toContain("plane-true");
  });
});

// cio-03 task 4: the peer-cone fan-chart grid rides into the dashboard as a
// host-injected tab (DN-8 §1 - the dashboard renders one CioView and nothing
// else, so the bundle-owned peer cone cannot move inside it).
describe("peer tab injection", () => {
  it("offers no peers tab without bands", () => {
    expect(peerTabs(null, [], 0)).toHaveLength(0);
  });
  it("offers exactly one peers tab when bands exist", () => {
    const bands = { equity: [1, 2, 3] };
    const tabs = peerTabs(bands as never, [100, 101, 102], 3);
    expect(tabs).toHaveLength(1);
    expect(tabs[0].key).toBe("peers");
    expect(tabs[0].label).toBe("Peers");
  });
});
