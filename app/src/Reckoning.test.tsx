/**
 * su-app-04 acceptance: E7's three-slot layout and E8's annotation line.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { AnalysisChart, threeSeries } from "./components/AnalysisChart";
import { annotationLine, Reckoning } from "./Reckoning";
import type { Outcome } from "./lib/session";

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

describe("Reckoning wires decision-window markers onto a quarterly chart", () => {
  // Regression: outcome.series is one point per closed QUARTER, not per
  // month (a 10-year/120-month world -> 40-point series). Reckoning must
  // convert each window's raw month index to a quarter index before handing
  // it to AnalysisChart, whose x-scale divides by (series.length - 1).
  // Passing raw months through made the later markers compute x-coordinates
  // several times the chart's width — clipped off-canvas entirely.
  it("keeps every decision-window marker within the chart's plotted width", () => {
    const quarters = 40; // 120 months / 3
    const active = Array.from({ length: quarters }, (_, i) => 100 + i);
    const twin = Array.from({ length: quarters }, (_, i) => 100 + i * 0.5);
    const windowMonths = [11, 23, 35, 47, 59, 71, 83, 95, 107];
    const outcome: Outcome = {
      session_id: "s1",
      basis: "actual",
      ranked: false,
      decision_alpha_version: "v1",
      final_value: active[active.length - 1],
      twin_final_value: twin[twin.length - 1],
      alpha: active[active.length - 1] - twin[twin.length - 1],
      windows: windowMonths.map((month) => ({ month, action: "hold", contribution: 0 })),
      series: { active, twin, drift_twin: null },
      window_contributions: windowMonths.map(() => 0),
      forced_secondaries: 0,
    };

    render(<Reckoning outcome={outcome} onExit={() => {}} />);

    const width = 720; // AnalysisChart's default width
    const lines = host!.querySelectorAll(".analysis-window-line");
    expect(lines.length).toBe(windowMonths.length);
    for (const line of Array.from(lines)) {
      const x1 = Number(line.getAttribute("x1"));
      expect(x1).toBeGreaterThanOrEqual(0);
      expect(x1).toBeLessThanOrEqual(width);
    }
  });
});
