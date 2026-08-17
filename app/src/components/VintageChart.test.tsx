/**
 * VintageChart.tsx (app-open-02 task 10): a bar per vintage — paid-in and
 * unfunded stacked, paid-in at the bottom — with a NAV line/marker per
 * vintage, all on ONE y axis (house dataviz rule: everything here is
 * allocation points, the same unit the book-entry screen totals to 100).
 *
 * Idiom note: createRoot + act, raw DOM queries — matching
 * BookEntry.test.tsx / CioDashboard.test.tsx, since these assertions read
 * actual SVG geometry attributes off the rendered markup.
 *
 * Every expected geometry number below is DERIVED here from the fixture's
 * own paid_in/unfunded/nav_true, via the SAME scale VintageChart.tsx
 * documents (viewBox 900x190, plot margins L40/R14/T14/B26, so plotH=150;
 * y(v) = T + (1 - v/maxVal) * plotH; maxVal = 1.05 * max across rungs of
 * max(paid_in+unfunded, nav_true)) — never copied off a rendered/run
 * output, so a defect in the component's own formula would fail these,
 * not just restate it.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { VintageChart } from "./VintageChart";
import type { Rung } from "../lib/session";

function rung(vintageYear: number, paidIn: number, unfunded: number, navTrue: number): Rung {
  return {
    identity: { vintage_year: vintageYear },
    commitment: {
      committed: paidIn + unfunded,
      paid_in: paidIn,
      unfunded,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: { nav_true: navTrue, nav_reported: navTrue, cumulative_distributions: 0 },
  };
}

// the three-rung fixture the geometry tests are hand-derived against.
const THREE_RUNGS: Rung[] = [
  rung(2019, 10, 6, 12),
  rung(2020, 4, 2, 5),
  rung(2021, 8, 0, 8),
];

// the scale VintageChart.tsx documents, reproduced independently here from
// the fixture's inputs — not read off the component's own output.
const T = 14;
const B = 26;
const H = 190;
const PLOT_H = H - T - B; // 150
const GAP = 2;

function expectedMaxVal(rungs: Rung[]): number {
  const rawMax = Math.max(
    0,
    ...rungs.map((r) =>
      Math.max(r.commitment.paid_in + r.commitment.unfunded, r.value.nav_true),
    ),
  );
  return rawMax > 0 ? rawMax * 1.05 : 1;
}

function scaleY(v: number, maxVal: number): number {
  return T + (1 - Math.max(0, v) / maxVal) * PLOT_H;
}

let root: Root | null = null;
let host: HTMLElement | null = null;

async function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(ui);
  });
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

function num(el: Element | null, attr: string): number {
  if (!el) throw new Error("element not found");
  const v = el.getAttribute(attr);
  if (v === null) throw new Error(`missing attribute ${attr}`);
  return Number(v);
}

describe("VintageChart", () => {
  it("sizes each stacked bar's paid-in and unfunded segments to the fixture, paid-in at the bottom", async () => {
    await render(<VintageChart rungs={THREE_RUNGS} />);
    const maxVal = expectedMaxVal(THREE_RUNGS); // 16.8
    const baseline = scaleY(0, maxVal);

    // rung 0: paid_in=10, unfunded=6 -> stack top at 16
    const paid0 = host!.querySelector('[data-testid="vintage-bar-paid-0"]');
    const unfunded0 = host!.querySelector('[data-testid="vintage-bar-unfunded-0"]');
    const paidTop0 = scaleY(10, maxVal);
    const paidHeight0 = baseline - paidTop0;
    const unfundedTop0 = scaleY(16, maxVal);
    const unfundedHeight0 = paidTop0 - GAP - unfundedTop0;

    expect(num(paid0, "y")).toBeCloseTo(paidTop0, 5);
    expect(num(paid0, "height")).toBeCloseTo(paidHeight0, 5);
    expect(num(unfunded0, "y")).toBeCloseTo(unfundedTop0, 5);
    expect(num(unfunded0, "height")).toBeCloseTo(unfundedHeight0, 5);

    // rung 1: paid_in=4, unfunded=2 -> stack top at 6
    const paid1 = host!.querySelector('[data-testid="vintage-bar-paid-1"]');
    const unfunded1 = host!.querySelector('[data-testid="vintage-bar-unfunded-1"]');
    const paidTop1 = scaleY(4, maxVal);
    const paidHeight1 = baseline - paidTop1;
    const unfundedTop1 = scaleY(6, maxVal);
    const unfundedHeight1 = paidTop1 - GAP - unfundedTop1;

    expect(num(paid1, "y")).toBeCloseTo(paidTop1, 5);
    expect(num(paid1, "height")).toBeCloseTo(paidHeight1, 5);
    expect(num(unfunded1, "y")).toBeCloseTo(unfundedTop1, 5);
    expect(num(unfunded1, "height")).toBeCloseTo(unfundedHeight1, 5);
  });

  it("stacks paid-in at the bottom (larger y, nearer the baseline) with unfunded above it, gapped by SEGMENT_GAP", async () => {
    await render(<VintageChart rungs={THREE_RUNGS} />);
    const paid0 = host!.querySelector('[data-testid="vintage-bar-paid-0"]')!;
    const unfunded0 = host!.querySelector('[data-testid="vintage-bar-unfunded-0"]')!;
    const paidTop = num(paid0, "y");
    const unfundedBottom = num(unfunded0, "y") + num(unfunded0, "height");
    // SVG y grows downward, so "paid-in at the bottom" means its own y is
    // the LARGER (lower-on-screen) one, and the unfunded segment's bottom
    // edge sits a fixed gap above (smaller y than) paid-in's top edge.
    expect(paidTop).toBeGreaterThan(unfundedBottom);
    expect(paidTop - unfundedBottom).toBeCloseTo(GAP, 5);
  });

  it("puts the NAV line's markers exactly at each vintage's NAV value on the same scale", async () => {
    await render(<VintageChart rungs={THREE_RUNGS} />);
    const maxVal = expectedMaxVal(THREE_RUNGS);
    const expected = [12, 5, 8].map((nav) => scaleY(nav, maxVal));
    expected.forEach((y, i) => {
      const marker = host!.querySelector(`[data-testid="vintage-nav-${i}"]`);
      expect(num(marker, "cy")).toBeCloseTo(y, 5);
    });
  });

  it("renders a zero-height bar and a baseline NAV marker for an all-zero rung, with no NaN or negative geometry", async () => {
    const zero: Rung[] = [rung(2022, 0, 0, 0)];
    await render(<VintageChart rungs={zero} />);
    const paid = host!.querySelector('[data-testid="vintage-bar-paid-0"]')!;
    const unfunded = host!.querySelector('[data-testid="vintage-bar-unfunded-0"]')!;
    const marker = host!.querySelector('[data-testid="vintage-nav-0"]')!;

    for (const [el, attr] of [
      [paid, "y"],
      [paid, "height"],
      [unfunded, "y"],
      [unfunded, "height"],
      [marker, "cy"],
    ] as const) {
      const v = num(el, attr);
      expect(Number.isFinite(v)).toBe(true);
      expect(v).not.toBeNaN();
    }
    expect(num(paid, "height")).toBeGreaterThanOrEqual(0);
    expect(num(unfunded, "height")).toBeGreaterThanOrEqual(0);
    expect(num(paid, "width")).toBeGreaterThan(0);
  });

  it("renders nothing for an empty rung array", async () => {
    await render(<VintageChart rungs={[]} />);
    expect(host!.querySelector('[data-testid="vintage-chart"]')).toBeNull();
    expect(host!.innerHTML).toBe("");
  });

  it("shows dollar figures via usd() in per-bar and per-marker titles, not as a second axis", async () => {
    await render(<VintageChart rungs={THREE_RUNGS} />);
    const paid0 = host!.querySelector('[data-testid="vintage-bar-paid-0"]')!;
    const title = paid0.querySelector("title");
    expect(title).not.toBeNull();
    // paid_in=10 points = $1.00bn on the $10bn book (money.ts's usd())
    expect(title!.textContent).toMatch(/\$1\.00bn/);
    // only one y axis: no second set of numeric tick labels anywhere
    expect(host!.querySelectorAll(".vintage-axis-label").length).toBe(2);
  });

  it("labels the legend with Paid in / Unfunded / NAV", async () => {
    await render(<VintageChart rungs={THREE_RUNGS} />);
    const legend = host!.querySelector(".vintage-chart-legend")!;
    expect(legend.textContent).toContain("Paid in");
    expect(legend.textContent).toContain("Unfunded");
    expect(legend.textContent).toContain("NAV");
  });
});
