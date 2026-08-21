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
  it("renders the register's shape with the D-QC-1 quarter label: Y4 Q4, de-risked: -2.1 points", () => {
    // app-open-01 item 2 (owner ruling 2026-08-16): the dollar equivalent
    // (money.ts usd()) now rides alongside the points figure, never
    // replacing it — the points half of this assertion is unchanged.
    // D-QC-1: "Year N" became "Y{n} Q{q}" (windowLabel) — every one of
    // these two months is a year-close (12k+11), which windowLabel always
    // renders as Q4, so the year number is unchanged from the old copy.
    expect(annotationLine({ month: 47, action: "derisk", contribution: -2.1 })).toBe(
      "Y4 Q4, de-risked: -2.1 points / -$210m",
    );
    expect(annotationLine({ month: 11, action: "hold", contribution: 0 })).toBe(
      "Y1 Q4, held course: +0.0 points / $0",
    );
  });

  it("labels a quarterly mid-year window (D-QC-1 acceptance criterion 6)", () => {
    // month 2 is Y1 Q1 -- a window no legacy annual session ever had.
    expect(annotationLine({ month: 2, action: "hold", contribution: 0.4 })).toBe(
      "Y1 Q1, held course: +0.4 points / $40m",
    );
    // month 14 is Y2 Q1 -- a mid-year quarterly window inside vintage year 2.
    expect(annotationLine({ month: 14, action: "leanin", contribution: 1.1 })).toBe(
      "Y2 Q1, leaned in: +1.1 points / $110m",
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
