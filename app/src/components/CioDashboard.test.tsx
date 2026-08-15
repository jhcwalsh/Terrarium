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
import decided from "../../fixtures/cio-sample.decided.json";

const view = reported as unknown as CioView;
const decidedView = decided as unknown as CioView;

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

  it("prints em dashes for null returns, never a fabricated number", () => {
    // The old form of this test (`not.toContain("+0.0%")`) was vacuous:
    // sgn() — which renders every performance cell — never appends "%" (see
    // CioDashboard.tsx's `sgn`), so that string can never appear regardless
    // of what nulling did. A plain `not.toContain("+0.0")` would also have
    // been wrong the other way: the fixture's Excess row legitimately prints
    // "+0.0" where total and benchmark tie, so it would false-fail on
    // correct output.
    //
    // Instead: scope to the "Total plan" row (exactly what
    // performance.total feeds, per CioDashboard.tsx's PerfTable) and prove
    // nulling increases its em-dash count. The fixture's Total plan row
    // already carries one legitimate null (the unreached 10Y column), so
    // "contains a dash" alone would pass by accident even if the OTHER five
    // nulled cells rendered as fabricated numbers — the count comparison is
    // what actually catches that.
    const totalPlanRowDashes = (h: HTMLElement) => {
      const row = [...h.querySelectorAll("tr")].find(
        (tr) => tr.querySelector("td")?.textContent?.trim() === "Total plan",
      );
      if (!row) throw new Error('no "Total plan" row found');
      return (row.textContent?.match(/—/g) ?? []).length;
    };

    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const baselineHost = host!;
    const baselineDashes = totalPlanRowDashes(baselineHost);
    act(() => root!.unmount());
    baselineHost.remove();

    const nulled: CioView = JSON.parse(JSON.stringify(view));
    nulled.performance.total = nulled.performance.total.map(() => null);
    render(<CioDashboard view={nulled} onPlaneChange={() => {}} />);
    const nulledDashes = totalPlanRowDashes(host!);

    expect(nulledDashes).toBeGreaterThan(baselineDashes);
    expect(nulledDashes).toBe(nulled.performance.total.length);
  });

  it("prints em dashes for null call rates and coverage, never a fabricated 0.0%", () => {
    // Nullable<Ratio> means "denominator was zero" — a real state the
    // builder emits, not an absent field. Number(null) coercion must never
    // leak a fabricated "0.0%" for callRateUnfunded/callRateNav/coverage.
    //
    // Only the LAST HISTORICAL row (index histCount-1 — the exact row
    // PrivateTab's `cur` and the "By asset class" table's `c` both read,
    // rows[H-1]) is nulled, and only on the aggregate and pe series.
    // Nulling every row of a whole series instead empties RatioChart's
    // covVals/rateVals, which trips a SEPARATE, out-of-scope vendored bug
    // (Math.min(...[]) -> Infinity domains -> NaN SVG coordinates -> React
    // console warnings on every run) that this test must not exercise.
    const nulled: CioView = JSON.parse(JSON.stringify(view));
    const lastHistorical = nulled.privateCashflows.histCount - 1;
    for (const seriesId of ["aggregate", "pe"]) {
      const row = nulled.privateCashflows.series[seriesId][lastHistorical];
      row.callRateUnfunded = null;
      row.callRateNav = null;
      row.coverage = null;
    }
    render(
      <CioDashboard view={nulled} onPlaneChange={() => {}} initialTab="private" />,
    );
    expect(host!.textContent).not.toMatch(/0\.0%/);
  });

  it("embedded chrome hides the dashboard's own plane control and footer", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} chrome="embedded" />);
    // the host owns these in cockpit mode
    expect(host!.querySelector(".ciodash-planes")).toBeNull();
    expect(host!.querySelector(".ciodash-footer")).toBeNull();
    // the payload itself still renders
    expect(host!.textContent).toContain("Stagflation");
  });

  it("full chrome (the default) keeps them", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    expect(host!.querySelector(".ciodash-planes")).not.toBeNull();
    expect(host!.querySelector(".ciodash-footer")).not.toBeNull();
  });

  it("renders host-supplied extra tabs and calls their render only when selected", () => {
    let renders = 0;
    const extraTabs = [
      { key: "peers", label: "Peers", render: () => { renders++; return <p>peer content</p>; } },
    ];
    render(<CioDashboard view={view} onPlaneChange={() => {}} extraTabs={extraTabs} />);
    expect(renders).toBe(0);
    expect(host!.textContent).toContain("Peers");
    const tab = [...host!.querySelectorAll("button")].find((b) => b.textContent === "Peers");
    act(() => { tab!.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    expect(host!.textContent).toContain("peer content");
    expect(renders).toBeGreaterThan(0);
  });

  it("carries the class hooks the cockpit CSS needs", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} chrome="embedded" />);
    const root = host!.querySelector(".ciodash");
    expect(root).not.toBeNull();
    expect(root!.classList.contains("ciodash-embedded")).toBe(true);
  });

  describe("cio-03b: ER-6's lapse and the vintage ladder", () => {
    it("renders a lapse column in the by-asset-class table", () => {
      render(<CioDashboard view={view} onPlaneChange={() => {}} initialTab="private" />);
      expect(host!.textContent).toMatch(/Lapsed/i);
    });

    it("shows a non-zero lapsed figure when a historical row carries one", () => {
      const v: CioView = JSON.parse(JSON.stringify(view));
      const pcf = v.privateCashflows;
      // start from a clean slate so the injected figure is exact, then
      // place one real lapse deep in history so it survives an LTM-only
      // rollup; a distinctive value so it can't collide with another figure
      for (const rows of Object.values(pcf.series)) {
        for (const r of rows) r.expiredUndrawn = 0;
      }
      pcf.series.aggregate[0].expiredUndrawn = 733;
      pcf.series.pe[0].expiredUndrawn = 733;
      render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
      expect(host!.textContent).toMatch(/\$733m/);
    });

    it("renders zero lapse as a dash, never a bare $0m, when every row is genuinely zero", () => {
      // The committed fixture is the wrong vehicle for this: every class's
      // and the aggregate's lapsed-to-date sum is already non-zero there
      // (0.54 / 1.35 / 0.47 / 2.37), so the zero branch is never reached
      // against it. Zero out expiredUndrawn on EVERY row of EVERY series so
      // the "By asset class" table's "Lapsed to date" column is genuinely
      // zero for every row, then check the actual lapse cells — not the
      // whole table's text, which legitimately prints "$0m" elsewhere
      // (Net LTM / Net next 4q for the quieter classes).
      const v: CioView = JSON.parse(JSON.stringify(view));
      for (const rows of Object.values(v.privateCashflows.series)) {
        for (const r of rows) r.expiredUndrawn = 0;
      }
      render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
      const lapseCells = [...host!.querySelectorAll(".lapse-value")];
      // one per row of the "By asset class" table (classes + aggregate)
      expect(lapseCells.length).toBeGreaterThan(0);
      for (const cell of lapseCells) {
        expect(cell.textContent).toBe("—");
      }
    });

    it("renders one bar per vintage rung, oldest first", () => {
      render(<CioDashboard view={view} onPlaneChange={() => {}} initialTab="private" />);
      const bars = host!.querySelectorAll(".vintage-rung");
      expect(bars.length).toBe(view.privateCashflows.vintages?.length ?? 0);
      expect(bars.length).toBeGreaterThan(0);
    });

    it("degrades cleanly when the payload omits vintages and expiredUndrawn (older fixtures)", () => {
      const v: CioView = JSON.parse(JSON.stringify(view));
      delete v.privateCashflows.vintages;
      for (const rows of Object.values(v.privateCashflows.series)) {
        for (const r of rows) {
          // @ts-expect-error simulating a payload built before cio-03b
          delete r.expiredUndrawn;
        }
      }
      expect(() =>
        render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />),
      ).not.toThrow();
      expect(host!.querySelectorAll(".vintage-rung").length).toBe(0);
    });
  });

  describe("cio-03: RatioChart robustness", () => {
    it("breaks the ratio line at nulls instead of plotting them at the floor", () => {
      const v: CioView = JSON.parse(JSON.stringify(view));
      const rows = v.privateCashflows.series.aggregate;
      rows[2].coverage = null;
      render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
      const paths = [...host!.querySelectorAll("path")].map((p) => p.getAttribute("d") ?? "");
      expect(paths.join(" ")).not.toContain("NaN");
      // a gap means the path restarts: more than one "M" command in some path
      expect(paths.some((d) => (d.match(/M/g) ?? []).length > 1)).toBe(true);
    });

    it("renders no ratio chart at all when a series is entirely null", () => {
      const v: CioView = JSON.parse(JSON.stringify(view));
      for (const rows of Object.values(v.privateCashflows.series)) {
        for (const r of rows) { r.coverage = null; r.callRateUnfunded = null; r.callRateNav = null; }
      }
      const warn = vi.spyOn(console, "error").mockImplementation(() => {});
      render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
      const paths = [...host!.querySelectorAll("path")].map((p) => p.getAttribute("d") ?? "");
      expect(paths.join(" ")).not.toContain("NaN");
      // Scoped to "Received NaN" specifically, not "console.error was never
      // called": this environment (happy-dom, no IS_REACT_ACT_ENVIRONMENT)
      // unconditionally logs a "not configured to support act(...)" warning
      // on every render, in every test in this file, regardless of this
      // defect — asserting zero calls would false-fail on correct code.
      const nanWarnings = warn.mock.calls.filter((args) =>
        args.some((a) => typeof a === "string" && a.includes("NaN")),
      );
      expect(nanWarnings).toEqual([]);
      warn.mockRestore();
    });
  });

  describe("cio-03: a decisions-bearing fixture", () => {
    it("shows a non-zero Excess value against a fixture built from a session that made decisions", () => {
      // cio-sample.decided.json (scripts/gen_cio_fixture.py) plays derisk /
      // leanin at real decision months instead of the degenerate {} (all
      // hold) map the other two fixtures use, so performance.total should
      // genuinely differ from performance.benchmark (the twin) somewhere.
      render(<CioDashboard view={decidedView} onPlaneChange={() => {}} />);
      const row = [...host!.querySelectorAll("tr")].find(
        (tr) => tr.querySelector("td")?.textContent?.trim() === "Excess",
      );
      if (!row) throw new Error('no "Excess" row found');
      const cells = [...row.querySelectorAll("td")]
        .slice(1)
        .map((td) => td.textContent?.trim() ?? "");
      // "" (an empty spacer <td/>) and "—" (sgn()'s NA marker for an
      // unreached/incomparable period) are both non-signals, not evidence
      // of divergence — only a printed +/- figure other than "+0.0" counts.
      expect(cells.some((c) => c !== "" && c !== "—" && c !== "+0.0")).toBe(true);
    });
  });
});
