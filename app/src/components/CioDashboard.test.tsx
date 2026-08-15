/**
 * cio-02: the CIO dashboard renderer, converted to typed TSX.
 *
 * Rendered with react-dom/client's createRoot + act, matching the codebase's
 * existing idiom (Book.test.tsx, DecisionWindow.test.tsx) — no
 * @testing-library/react dependency (not in app/package.json devDependencies,
 * and this task must not add one).
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import CioDashboard from "./CioDashboard";
import type { CioView } from "../lib/cioView";
import reported from "../../fixtures/cio-sample.reported.json";

const view = reported as unknown as CioView;

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

/** Finds a clickable element (button) by exact text and clicks it. */
function clickButton(text: string) {
  const btn = [...host!.querySelectorAll("button")].find(
    (b) => (b.textContent ?? "").trim() === text,
  );
  if (!btn) throw new Error(`no button with text "${text}"`);
  act(() => btn.click());
}

describe("CioDashboard", () => {
  it("renders the plan tab from a real payload", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    expect(host!.textContent).toContain("Stagflation");
    expect(host!.textContent).toMatch(/Plan growth/i);
    expect(host!.textContent).toMatch(/run fixture-stagflation/);
  });

  it("switches tabs and renders each", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    for (const label of ["Liquidity", "Private cashflows", "Markets", "Plan"]) {
      clickButton(label);
    }
    expect(host!.textContent).toMatch(/Plan growth/i);
  });

  it("plane buttons refetch via onPlaneChange, never transform locally", () => {
    const onPlane = vi.fn();
    render(<CioDashboard view={view} onPlaneChange={onPlane} />);
    clickButton("True");
    expect(onPlane).toHaveBeenCalledWith("true");
  });

  it("renders forecast caption when forecast rows exist", () => {
    render(
      <CioDashboard view={view} onPlaneChange={() => {}} initialTab="private" />,
    );
    expect(host!.textContent).toMatch(/ROLL-FORWARD, NOT A PROJECTION/i);
  });

  it("suppresses the outflow/cover tiles when the forecast is all zeros (fq=0)", () => {
    const noFcst: CioView = JSON.parse(JSON.stringify(view));
    noFcst.liquidity.forecast12m = {
      distributions: 0,
      income: 0,
      calls: 0,
      payout: 0,
      net: 0,
    };
    render(
      <CioDashboard view={noFcst} onPlaneChange={() => {}} initialTab="liquidity" />,
    );
    expect(host!.textContent).not.toMatch(/Cover of 12m outflow/i);
    expect(host!.textContent).not.toMatch(/Net outflow, 12m/i);
  });

  it("prints em dashes for null returns, never +0.0", () => {
    const nulled: CioView = JSON.parse(JSON.stringify(view));
    nulled.performance.total = nulled.performance.total.map(() => null);
    render(<CioDashboard view={nulled} onPlaneChange={() => {}} />);
    expect(host!.textContent).not.toContain("+0.0%");
  });

  it("prints em dashes for null call rates and coverage, never a fabricated 0.0%", () => {
    // Nullable<Ratio> means "denominator was zero" — a real state the
    // builder emits, not an absent field. Number(null) coercion must never
    // leak a fabricated "0.0%" for callRateUnfunded/callRateNav/coverage.
    const nulled: CioView = JSON.parse(JSON.stringify(view));
    for (const seriesId of ["aggregate", "pe"]) {
      for (const row of nulled.privateCashflows.series[seriesId]) {
        row.callRateUnfunded = null;
        row.callRateNav = null;
        row.coverage = null;
      }
    }
    render(
      <CioDashboard view={nulled} onPlaneChange={() => {}} initialTab="private" />,
    );
    expect(host!.textContent).not.toMatch(/0\.0%/);
  });
});
