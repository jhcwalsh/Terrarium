/**
 * su-app-04 acceptance: E7's three-slot layout and E8's annotation line.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { AnalysisChart, threeSeries } from "./components/AnalysisChart";
import { annotationLine } from "./Reckoning";

let root: Root | null = null;
let host: HTMLElement | null = null;

function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(ui));
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

describe("annotationLine (E8)", () => {
  it("renders the register's exact shape: Year 4, de-risked: -2.1 points", () => {
    expect(annotationLine({ month: 47, action: "derisk", contribution: -2.1 })).toBe(
      "Year 4, de-risked: -2.1 points",
    );
    expect(annotationLine({ month: 11, action: "hold", contribution: 0 })).toBe(
      "Year 1, held course: +0.0 points",
    );
  });
});

describe("AnalysisChart (E7)", () => {
  it("carries three legend slots while rendering two series", () => {
    const series = threeSeries([100, 101, 102], [100, 100.5, 101], null);
    render(<AnalysisChart series={series} decisionMonths={[1]} />);
    const legend = host!.querySelectorAll(".analysis-legend span");
    expect(legend.length).toBe(3);
    expect(legend[2].textContent).toContain("pending");
    // two polylines drawn, the third awaits its data
    expect(host!.querySelectorAll("polyline").length).toBe(2);
  });
});
