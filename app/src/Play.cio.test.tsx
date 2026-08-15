/**
 * Play's extracted pure seams, tested without mounting Play itself (mounting
 * needs a live/mocked session service plus a WorldBundle fixture, out of
 * scope for a scaffold toggle — see task-4-brief.md Step 1). Three seams so
 * far: `cioFetchKey` (when the CIO view must refetch), `cockpitClass` (the
 * vitrine's layout-mode class list), and `peerTabs` (cio-03 task 4: the
 * host-injected Peers tab factory).
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
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
//
// `seriesFor` is typed `(assetKey: string) => number[]` — the same accessor
// shape Play's `column` already is, resolving each asset (and, for private
// assets, the plane-selected source name) to its own series. There is no
// flat-array form: a single series applied to all eight charts would draw
// the same cone everywhere and make the plane switch inert (review finding
// I-1, cio-03 task 4 fix report).
describe("peer tab injection", () => {
  let root: Root | null = null;
  let host: HTMLElement | null = null;

  afterEach(() => {
    if (root) act(() => root!.unmount());
    host?.remove();
    root = null;
    host = null;
  });

  it("offers no peers tab without bands", () => {
    expect(peerTabs(null, () => [], 0)).toHaveLength(0);
  });

  it("offers exactly one peers tab when bands exist", () => {
    const bands = { equity: { p5: [1], p25: [1], p50: [1], p75: [1], p95: [1] } };
    const tabs = peerTabs(bands, () => [100, 101, 102], 3);
    expect(tabs).toHaveLength(1);
    expect(tabs[0].key).toBe("peers");
    expect(tabs[0].label).toBe("Peers");
  });

  // I-2: the eight moved FanCharts, actually rendered — covers the move,
  // not just the gating logic above.
  it("renders all eight moved fan charts", () => {
    const series = [1, 1.01, 1.02, 1.03];
    const bands = Object.fromEntries(
      ["equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re"].map((key) => [
        key,
        { p5: series, p25: series, p50: series, p75: series, p95: series },
      ]),
    );
    const tabs = peerTabs(bands, () => series, series.length);
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() => root!.render(tabs[0].render() as React.ReactElement));
    expect(host.querySelectorAll("figure.fan-chart")).toHaveLength(8);
  });
});
