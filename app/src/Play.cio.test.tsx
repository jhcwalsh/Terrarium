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
import { BandPanel, bookLabel, cioFetchKey, cockpitClass, peerTabs } from "./Play";
import type { AlertLevel } from "./lib/cioView";
import type { BandSleeve, Session } from "./lib/session";

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

// I-4: the stat rail's "Your book" label must name the session's actual
// FIXED scoring basis (session.basis: "reported" | "actual", see
// lib/session.ts), never a hardcoded string — a hardcode would silently
// mislabel the figure the instant a player's session used the other basis.
// Both real values are asserted so a constant return value cannot pass.
describe("book label names the real scoring basis (I-4)", () => {
  it("names the reported basis", () => {
    expect(bookLabel("reported")).toBe("Your book · reported basis");
  });
  it("names the actual basis, not a hardcoded 'reported'", () => {
    expect(bookLabel("actual")).toBe("Your book · actual basis");
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
/**
 * su-app-07 task 4b: the band report, rendered.
 *
 * `BandPanel` is a pure function of the session document (no fetch, no
 * bundle), so it mounts on its own here rather than through `Play` — the
 * same reason the seams above are tested directly.
 *
 * Everything asserted is something the SERVER said. The panel must never
 * re-derive an `alert` (DN-3 W5, and `serve.py::_band_report`'s docstring:
 * the alert is computed on unrounded weights while rounded ones are served,
 * so a client re-running the rule can legitimately disagree at a band edge).
 * The "verbatim" test below is the one that bites if anyone adds a local
 * rule: it serves a weight sitting comfortably inside its band with an
 * alert of `breach`, which no client-side rule would ever produce.
 */
function bandSleeve(
  sleeve: string,
  opts: {
    target?: number;
    lo?: number;
    hi?: number;
    trueWeight: number;
    trueAlert: AlertLevel;
    reportedWeight: number;
    reportedAlert: AlertLevel;
  },
): BandSleeve {
  return {
    sleeve,
    target: opts.target ?? 35,
    lo: opts.lo ?? 30,
    hi: opts.hi ?? 40,
    true: { weight: opts.trueWeight, alert: opts.trueAlert },
    reported: { weight: opts.reportedWeight, alert: opts.reportedAlert },
  };
}

/** a sleeve whose two planes agree — for the tests that are not about planes */
function flatSleeve(sleeve: string, weight: number, alert: AlertLevel): BandSleeve {
  return bandSleeve(sleeve, {
    trueWeight: weight,
    trueAlert: alert,
    reportedWeight: weight,
    reportedAlert: alert,
  });
}

function sessionWith(
  basis: Session["basis"],
  bandReport: Session["band_report"],
): Session {
  return {
    session_id: "s1",
    run_id: "r1",
    world_id: "w1",
    months: 120,
    revealed_months: 12,
    basis,
    ranked: false,
    participant: null,
    decisions: {},
    window_log: [],
    status: "active",
    // D-QC-1: decision_windows is now REQUIRED on Session; BandPanel/peer-tab
    // tests here don't exercise the window grid at all, so an empty array
    // satisfies the type without claiming any particular cadence.
    decision_windows: [],
    band_report: bandReport,
  };
}

describe("policy band panel (su-app-07 task 4b)", () => {
  let root: Root | null = null;
  let host: HTMLElement | null = null;

  const mount = (session: Session): HTMLElement => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() => root!.render(<BandPanel session={session} />));
    return host;
  };

  afterEach(() => {
    if (root) act(() => root!.unmount());
    host?.remove();
    root = null;
    host = null;
  });

  it("renders nothing at all when the session carries no band report", () => {
    const el = mount(sessionWith("reported", null));
    expect(el.querySelector(".band-panel")).toBeNull();
    expect(el.innerHTML).toBe("");
  });

  it("renders nothing at all when the served sleeve list is empty", () => {
    const el = mount(sessionWith("reported", { watch_fraction: 0.8, sleeves: [] }));
    expect(el.querySelector(".band-panel")).toBeNull();
    expect(el.innerHTML).toBe("");
  });

  it("renders one row per served sleeve, in the served order", () => {
    // deliberately neither alphabetical nor ASSET_LABELS order: a renderer
    // that sorted (by key, by label, or by severity) would reorder this.
    const el = mount(
      sessionWith("reported", {
        watch_fraction: 0.8,
        sleeves: [
          flatSleeve("re", 8, "ok"),
          flatSleeve("equity", 41, "breach"),
          flatSleeve("bonds", 12, "watch"),
        ],
      }),
    );
    const rows = Array.from(el.querySelectorAll(".band-cell"));
    expect(rows).toHaveLength(3);
    expect(rows.map((r) => r.getAttribute("data-sleeve"))).toEqual(["re", "equity", "bonds"]);
  });

  it("visibly distinguishes a breach row from an ok row", () => {
    const el = mount(
      sessionWith("reported", {
        watch_fraction: 0.8,
        sleeves: [flatSleeve("equity", 44, "breach"), flatSleeve("bonds", 12, "ok")],
      }),
    );
    const [breach, ok] = Array.from(el.querySelectorAll(".band-cell"));
    expect(breach.className).toContain("alert-breach");
    expect(breach.className).not.toContain("alert-ok");
    expect(ok.className).toContain("alert-ok");
    expect(breach.querySelector(".band-badge")?.textContent).toBe("breach");
    expect(ok.querySelector(".band-badge")?.textContent).toBe("ok");
  });

  // THE PLANE BITE. `planeForBasis` maps a session's basis ("reported" |
  // "actual") onto the report's plane ("reported" | "true") — the two
  // vocabularies differ, and reading `sleeves[i][session.basis]` directly
  // gives `undefined` on an actual-basis session. The two planes here carry
  // DIFFERENT weights AND different alerts, so a panel wired to the wrong
  // plane cannot pass by coincidence.
  it("reads the TRUE plane on an actual-basis session, never the reported one", () => {
    const el = mount(
      sessionWith("actual", {
        watch_fraction: 0.8,
        sleeves: [
          bandSleeve("equity", {
            trueWeight: 44.4,
            trueAlert: "breach",
            reportedWeight: 33.3,
            reportedAlert: "ok",
          }),
        ],
      }),
    );
    const row = el.querySelector(".band-cell")!;
    expect(row.querySelector(".band-badge")?.textContent).toBe("breach");
    expect(row.className).toContain("alert-breach");
    expect(el.textContent).toContain("44.4");
    expect(el.textContent).not.toContain("33.3");
  });

  it("reads the REPORTED plane on a reported-basis session", () => {
    const el = mount(
      sessionWith("reported", {
        watch_fraction: 0.8,
        sleeves: [
          bandSleeve("equity", {
            trueWeight: 44.4,
            trueAlert: "breach",
            reportedWeight: 33.3,
            reportedAlert: "ok",
          }),
        ],
      }),
    );
    const row = el.querySelector(".band-cell")!;
    expect(row.querySelector(".band-badge")?.textContent).toBe("ok");
    expect(el.textContent).toContain("33.3");
    expect(el.textContent).not.toContain("44.4");
  });

  it("never invents a row for a sleeve the server left out", () => {
    // the server omits an un-banded sleeve entirely rather than sending nulls;
    // the panel must not backfill the world's other sleeves.
    const el = mount(
      sessionWith("reported", {
        watch_fraction: 0.8,
        sleeves: [flatSleeve("equity", 41, "ok")],
      }),
    );
    expect(el.querySelectorAll(".band-cell")).toHaveLength(1);
    expect(el.querySelector('[data-sleeve="bonds"]')).toBeNull();
    expect(el.textContent).not.toContain("Bonds");
  });

  it("renders the served alert verbatim, never a re-derived one", () => {
    // 35.0 is dead on target and well inside 30–40; no client-side rule would
    // call it a breach. The server did, so the panel says breach.
    const el = mount(
      sessionWith("reported", {
        watch_fraction: 0.8,
        sleeves: [flatSleeve("equity", 35, "breach")],
      }),
    );
    const row = el.querySelector(".band-cell")!;
    expect(row.querySelector(".band-badge")?.textContent).toBe("breach");
    expect(row.className).toContain("alert-breach");
  });

  it("shows each row's target and band as served", () => {
    const el = mount(
      sessionWith("reported", {
        watch_fraction: 0.8,
        sleeves: [
          bandSleeve("equity", {
            target: 35,
            lo: 31.5,
            hi: 38.5,
            trueWeight: 41.2,
            trueAlert: "breach",
            reportedWeight: 41.2,
            reportedAlert: "breach",
          }),
        ],
      }),
    );
    const text = el.querySelector(".band-cell")!.textContent ?? "";
    expect(text).toContain("35.0");
    expect(text).toContain("31.5");
    expect(text).toContain("38.5");
    expect(text).toContain("41.2");
  });
});

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

  // I-2: the nine moved FanCharts, actually rendered — covers the move,
  // not just the gating logic above. Was eight before ER-14's close-out
  // (D-ER14-2, 2026-08-18) added infra as the fourth private class.
  it("renders all nine moved fan charts", () => {
    const series = [1, 1.01, 1.02, 1.03];
    const bands = Object.fromEntries(
      ["equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re", "infra"].map(
        (key) => [key, { p5: series, p25: series, p50: series, p75: series, p95: series }],
      ),
    );
    const tabs = peerTabs(bands, () => series, series.length);
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() => root!.render(tabs[0].render() as React.ReactElement));
    expect(host.querySelectorAll("figure.fan-chart")).toHaveLength(9);
  });
});
