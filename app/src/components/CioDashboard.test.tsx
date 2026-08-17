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
import CioDashboard, {
  planWindowLabel,
  planWindowMonths,
  planWindowSlice,
} from "./CioDashboard";
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

  it("renders the CIO headline value in the $10bn display denomination (app-open-01 item 1)", () => {
    // view.plan.totalValue is 62.1323 (fixture) — the underlying scored
    // points are untouched; only the rendering (money.ts usd()) changed.
    // Two-decimal bn precision is review-round fix 3 ($10m granularity).
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    expect(host!.textContent).toContain("$6.21bn");
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
    // nulling increases its em-dash count. (cio-04: the fixture's Total plan
    // row used to carry one legitimate null — the unreached 10Y column —
    // before regeneration; the inherited decade now makes 10Y reachable, so
    // the baseline has zero dashes. The count comparison below still holds
    // either way, and still catches the failure mode a plain "contains a
    // dash" check would miss: any of the six nulled cells rendering as a
    // fabricated number instead of a dash.)
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
      // 733 points -> $73.30bn through usd()'s $10bn book denomination
      // (app-open-01 review round fix 1) — the distinctive VALUE (733) is
      // what proves this figure and no other, not its old $m rendering.
      expect(host!.textContent).toMatch(/\$73\.30bn/);
    });

    it("shows the current-quarter lapse alongside the running total, not only the total (I-2)", () => {
      // F2's closure required both halves: the release in the quarter it
      // happens, and the running total afterwards. The "Lapsed to date"
      // tile only ever showed the second half after cio-03b's restoration
      // — a monotonically-rising cumulative can't say which quarter moved,
      // which matters post-ER-12 (lapse is ~0.47-0.49/year spread across
      // many quarters, not one big event). Zero every row, then set ONLY
      // the as-of quarter (rows[histCount-1], what PrivateTab's `cur` and
      // the tile's sub text both read) non-zero, so a pass here can only be
      // explained by the current-quarter figure actually reaching the tile.
      const v: CioView = JSON.parse(JSON.stringify(view));
      const pcf = v.privateCashflows;
      const H = pcf.histCount;
      for (const rows of Object.values(pcf.series)) {
        for (const r of rows) r.expiredUndrawn = 0;
      }
      pcf.series.aggregate[H - 1].expiredUndrawn = 415;
      render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
      // 415 points -> $41.50bn through usd() (app-open-01 review round fix 1)
      expect(host!.textContent).toMatch(/\$41\.50bn this quarter/);
    });

    it("renders zero lapse as a muted $0, never the missing-data dash (M-1)", () => {
      // DN-8 s3: an em dash means UNAVAILABLE. A known, tracked zero must
      // not borrow it — this WAS the bug (`lapseCell` returned NA for
      // `v <= 0`), which made a class that genuinely never lapsed
      // indistinguishable from one where lapse isn't tracked in a table
      // where "—" also marks an unreached forecast column. Fixed by
      // rendering a muted zero instead: colour signals "don't worry about
      // this", the glyph stays reserved for "no data". The exact string is
      // now usd(0)'s bare "$0" (app-open-01 review round fix 1 routed
      // lapseCell through usd(), which deliberately renders exact zero as
      // "$0" rather than "$0m" — money.test.ts pins that) — the M-1
      // guarantee this test protects is "not the em dash", not the unit
      // suffix.
      //
      // The committed fixture is the wrong vehicle for this: every class's
      // and the aggregate's lapsed-to-date sum is already non-zero there
      // (0.54 / 1.35 / 0.47 / 2.37), so the zero branch is never reached
      // against it. Zero out expiredUndrawn on EVERY row of EVERY series so
      // the "By asset class" table's "Lapsed to date" column is genuinely
      // zero for every row, then check the actual lapse cells — not the
      // whole table's text, which legitimately prints other zero-ish money
      // figures elsewhere (Net LTM / Net next 4q for the quieter classes).
      const v: CioView = JSON.parse(JSON.stringify(view));
      for (const rows of Object.values(v.privateCashflows.series)) {
        for (const r of rows) r.expiredUndrawn = 0;
      }
      render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
      const lapseCells = [...host!.querySelectorAll(".lapse-value")];
      // one per row of the "By asset class" table (classes + aggregate)
      expect(lapseCells.length).toBeGreaterThan(0);
      for (const cell of lapseCells) {
        expect(cell.textContent).toBe("$0");
        expect(cell.textContent).not.toBe("—");
      }
    });

    it("renders exactly one bar per vintage rung (I-3: count, not order — order is pinned server-side in test_cioview.py)", () => {
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
      try {
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
      } finally {
        // try/finally: an earlier expect() throwing must not leave the spy
        // in place — this project sets neither restoreMocks nor
        // clearMocks, so a leaked mock would silently swallow
        // console.error (and mask NaN warnings) in every later test.
        warn.mockRestore();
      }
    });

    it("breaks a zero-span rate domain into a nonzero range instead of NaN", () => {
      // Every present call-rate reading exactly 0 (a real, reachable state
      // per cioview.py's callRateNav = calls / navOpen) collapses
      // rateDom to [0, 0] unless the domain guard also checks the span,
      // not just that the input array was nonempty.
      const v: CioView = JSON.parse(JSON.stringify(view));
      for (const rows of Object.values(v.privateCashflows.series)) {
        for (const r of rows) { r.callRateUnfunded = 0; r.callRateNav = 0; }
      }
      const warn = vi.spyOn(console, "error").mockImplementation(() => {});
      try {
        render(<CioDashboard view={v} onPlaneChange={() => {}} initialTab="private" />);
        const svgs = [...host!.querySelectorAll("svg")].map((s) => s.outerHTML);
        expect(svgs.join(" ")).not.toContain("NaN");
        const nanWarnings = warn.mock.calls.filter((args) =>
          args.some((a) => typeof a === "string" && a.includes("NaN")),
        );
        expect(nanWarnings).toEqual([]);
      } finally {
        warn.mockRestore();
      }
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

  // app-open-01 item 1's real precondition: the CIO must render at month 0
  // without errors. The server can now legitimately serve histCount === 0
  // (cio-05) — every private-cashflow row is forecast, nothing has closed.
  // `rows[histCount - 1]` is `rows[-1]` in JS (not "the last element" —
  // `undefined`), which crashed here before this WP.
  describe("app-open-01 (cio-05): private cashflows tab survives histCount === 0", () => {
    it("renders the tiles and the by-asset-class table without throwing, from the opening figures", () => {
      const monthZero: CioView = JSON.parse(JSON.stringify(view));
      monthZero.privateCashflows.histCount = 0;
      for (const key of Object.keys(monthZero.privateCashflows.series)) {
        monthZero.privateCashflows.series[key] = monthZero.privateCashflows.series[key]
          .slice(0, 4)
          .map((r) => ({ ...r, forecast: true }));
      }
      monthZero.privateCashflows.vintages = [];

      expect(() =>
        render(<CioDashboard view={monthZero} onPlaneChange={() => {}} initialTab="private" />),
      ).not.toThrow();
      expect(host!.textContent).toMatch(/NAV \(opening\)/i);
      expect(host!.textContent).toMatch(/Unfunded \(opening\)/i);
      expect(host!.querySelectorAll("table").length).toBeGreaterThan(0);
    });

    it("renders the empty state, not a crash, when every series is genuinely zero rows", () => {
      const empty: CioView = JSON.parse(JSON.stringify(view));
      empty.privateCashflows.histCount = 0;
      for (const key of Object.keys(empty.privateCashflows.series)) {
        empty.privateCashflows.series[key] = [];
      }
      empty.privateCashflows.vintages = [];

      expect(() =>
        render(<CioDashboard view={empty} onPlaneChange={() => {}} initialTab="private" />),
      ).not.toThrow();
      expect(host!.textContent).toMatch(/no private cashflow history/i);
    });
  });

  // app-open-01 item 2: plan growth and asset allocation side by side.
  describe("app-open-01 item 2: plan growth and asset allocation sit side by side", () => {
    it("renders both panels inside one two-panel row container", () => {
      render(<CioDashboard view={view} onPlaneChange={() => {}} />);
      const row = host!.querySelector(".cio-plan-row");
      expect(row).not.toBeNull();
      // exactly the two panels, in this order — a structural assert, not a
      // pixel-position one (jsdom does not lay out CSS grid); the CSS rule
      // itself (grid-template-columns: repeat(auto-fit, minmax(...))) is
      // trusted to do the actual side-by-side placement.
      const panelTitles = [...row!.children].map(
        (child) => child.querySelector("h2")?.textContent,
      );
      expect(panelTitles).toEqual(["Plan growth", "Asset allocation"]);
      // "Performance and allocation" stays OUTSIDE the row, full width,
      // unchanged — only the two named panels moved.
      expect(row!.querySelector("h2")?.textContent).not.toMatch(/Performance/i);
    });
  });

  // app-open-01 item 3: the plan-growth chart states its actual timeframe.
  describe("app-open-01 item 3: the plan-growth chart states its timeframe (ER-13 honesty)", () => {
    it("planWindowMonths never invents more than exists", () => {
      expect(planWindowMonths(180, "3y")).toBe(36);
      expect(planWindowMonths(24, "3y")).toBe(24); // capped, not padded
      expect(planWindowMonths(180, "full")).toBe(180);
    });

    it("planWindowSlice's worldStartIndex tracks the SAME point after slicing", () => {
      const values = Array.from({ length: 180 }, (_, i) => i);
      // worldStartIndex 150 sits INSIDE the trailing-36 window (from index
      // 144 on), so the slice keeps it, shifted by how much was cut off.
      const sliced = planWindowSlice(values, 150, "3y");
      expect(sliced.values).toHaveLength(36);
      expect(sliced.worldStartIndex).toBe(6); // 150 - (180 - 36)
      expect(sliced.values[sliced.worldStartIndex]).toBe(150);

      // worldStartIndex 120 sits BEFORE that window entirely — the world
      // began earlier than the visible 3 years, so it clamps to 0 rather
      // than going negative (everything shown is already the world's own).
      const clamped = planWindowSlice(values, 120, "3y");
      expect(clamped.worldStartIndex).toBe(0);
    });

    it("planWindowLabel reads the ACTUAL window, not a hardcoded string", () => {
      expect(planWindowLabel(36, 0, "3y")).toBe("PAST 3 YEARS");
      expect(planWindowLabel(24, 0, "3y")).toBe("PAST 2 YEARS"); // a younger world, not padded to "3"
      expect(planWindowLabel(180, 120, "full")).toBe("FULL RANGE — 15Y (PARTLY INHERITED)");
      // wholly inside the inherited decade (month 0, before any world
      // month exists) — the honesty marker the register demands (ER-13).
      expect(planWindowLabel(36, 36, "3y")).toBe("PAST 3 YEARS (INHERITED, SIMULATED)");
    });

    it("renders the timeframe label matching the default 3-year window actually plotted", () => {
      // the fixture: 180 months of history, worldStartIndex 120 (60 world
      // months revealed) — the trailing 3 years is entirely the world's own
      // data, so the label carries no inherited qualifier, and the chart
      // has no hatched region to disclose at THIS window (correctly: there
      // isn't one visible).
      render(<CioDashboard view={view} onPlaneChange={() => {}} />);
      const label = host!.querySelector(".plan-growth-timeframe");
      expect(label).not.toBeNull();
      expect(label!.textContent).toBe("PAST 3 YEARS");
      expect(host!.textContent).not.toContain("INHERITED DECADE (SIMULATED)");
    });

    it("switching to full range updates the label AND surfaces cio-04's existing disclosure, adjacent — never a second wording", () => {
      render(<CioDashboard view={view} onPlaneChange={() => {}} />);
      clickButton("Full range");
      const label = host!.querySelector(".plan-growth-timeframe");
      expect(label!.textContent).toBe("FULL RANGE — 15Y (PARTLY INHERITED)");
      // the full window now includes the hatched pre-history, so the
      // chart's own cio-04 disclosure (plan.preRunLabel) appears — same
      // wording as always, not a second one invented for this label.
      expect(host!.textContent).toContain("INHERITED DECADE (SIMULATED)");
    });

    it("offers no window toggle when the world is younger than 3 years — nothing to switch to", () => {
      const young: CioView = JSON.parse(JSON.stringify(view));
      young.plan.history = { values: young.plan.history.values.slice(-24), worldStartIndex: 0 };
      render(<CioDashboard view={young} onPlaneChange={() => {}} />);
      expect(host!.querySelector(".plan-growth-timeframe")!.textContent).toBe("PAST 2 YEARS");
      expect([...host!.querySelectorAll("button")].some((b) => b.textContent === "Full range")).toBe(
        false,
      );
    });
  });
});
