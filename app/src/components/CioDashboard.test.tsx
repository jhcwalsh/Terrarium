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
  alertLevel,
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
    // view.plan.totalValue is 64.5205 (fixture, regenerated at er14-04b
    // Task S8 to carry the fourth private class) — the underlying scored
    // points are untouched; only the rendering (money.ts usd()) changed.
    // Two-decimal bn precision is review-round fix 3 ($10m granularity).
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    expect(host!.textContent).toContain("$6.45bn");
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

describe("alertLevel — app-open-02 task 2's asymmetric [lo, hi] port", () => {
  const policy = { watchFraction: 0.75 };

  it("serve.py's own worked example: lo=10, hi=20, target=30 (outside its own band), weight 15.0 is NOT watch", () => {
    // The old symmetric-band rule inverted on this exact shape (picked the
    // wrong edge to measure room against once the target sat outside the
    // band at all) — this is the probe serve.py's _alert_level docstring
    // records finding it backwards on. weight=15.0 sits mid-band, nowhere
    // near either edge, so it must read "ok".
    expect(alertLevel(15.0, 30, 10, 20, policy, undefined)).toBe("ok");
  });

  it("a weight exactly on the edge the target is approaching (hi=20) is watch, not ok", () => {
    // Same lo/hi/target as the worked example: clamped target t = hi = 20
    // (30 clamped into [10, 20]), so the upper watch zone collapses to the
    // edge itself (serve.py docstring's t == hi degenerate case) and 20.0
    // — sitting exactly on it — is watch.
    expect(alertLevel(20.0, 30, 10, 20, policy, undefined)).toBe("watch");
  });

  it("breach is unaffected by target position — outside [lo, hi] is always breach", () => {
    expect(alertLevel(21.0, 30, 10, 20, policy, undefined)).toBe("breach");
    expect(alertLevel(9.0, 30, 10, 20, policy, undefined)).toBe("breach");
  });

  it("an ordinary in-band case (target inside its own band) matches the old symmetric shape", () => {
    // lo=95, hi=105 around a target of 100 (a +/-5 band): 25% watch fraction
    // means the outer 1.25 points on each side are amber, same numbers the
    // old |dev| >= watchFraction * band rule produced.
    expect(alertLevel(100.0, 100, 95, 105, policy, undefined)).toBe("ok");
    expect(alertLevel(103.9, 100, 95, 105, policy, undefined)).toBe("watch");
    expect(alertLevel(104.5, 100, 95, 105, policy, undefined)).toBe("watch");
    expect(alertLevel(106.0, 100, 95, 105, policy, undefined)).toBe("breach");
  });

  it("the served alert word wins over the computed rule, unchanged precedence", () => {
    expect(alertLevel(15.0, 30, 10, 20, policy, "breach")).toBe("breach");
  });

  it("no watchFraction on the policy: only breach can fire, never watch", () => {
    expect(alertLevel(20.0, 30, 10, 20, undefined, undefined)).toBe("ok");
  });

  it("a degenerate lo >= hi band is treated as no band at all (ok)", () => {
    expect(alertLevel(15.0, 15, 20, 20, policy, undefined)).toBe("ok");
  });
});

describe("CioDashboard — allocation table Band column (app-open-02 task 2)", () => {
  it("renders the class's own lo-hi band with an en dash, one decimal each", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    // the reported fixture's equity class: bandLoPct 28.0, bandHiPct 38.0
    expect(host!.textContent).toContain("28.0–38.0");
  });

  it("renders an em dash for cash, which carries no band", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const rows = [...host!.querySelectorAll("tr")];
    const cashRow = rows.find((r) => (r.textContent ?? "").includes("Cash"));
    expect(cashRow).toBeTruthy();
    // Band column is the 6th <td> in a class row (Asset class, Weight v
    // target bar, !, Weight, Target, Band, Deviation, ...periods) — cell index 5.
    const cells = [...cashRow!.querySelectorAll("td")];
    expect(cells[5]?.textContent).toBe("—");
  });

  it("renders an em dash for a NON-cash class the book carries no range for (branch-review I1)", () => {
    // The renderer already tolerates null bandLoPct/bandHiPct generically
    // (isNum checks, not a cid === "cash" special case) — this pins that a
    // book-silent sleeve (not just cash) reads as "no band", not as the
    // old hardcoded BAND_PCT fallback.
    const v: CioView = JSON.parse(JSON.stringify(view));
    const commodities = v.allocation.classes.find((c) => c.id === "commodities")!;
    commodities.bandLoPct = null;
    commodities.bandHiPct = null;
    render(<CioDashboard view={v} onPlaneChange={() => {}} />);
    const rows = [...host!.querySelectorAll("tr")];
    const row = rows.find((r) => (r.textContent ?? "").includes("Commodities"));
    expect(row).toBeTruthy();
    const cells = [...row!.querySelectorAll("td")];
    expect(cells[5]?.textContent).toBe("—");
  });
});

describe("CioDashboard — table & panel labels spelled out (app-open-02 task 5)", () => {
  it("renders Weight, Target and Deviation as header text, not the Wt/Tgt/Dev abbreviations", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const headerCells = [...host!.querySelectorAll("th")].map((th) => th.textContent?.trim());
    expect(headerCells).toContain("Weight");
    expect(headerCells).toContain("Target");
    expect(headerCells).toContain("Deviation");
    expect(headerCells).not.toContain("Wt");
    expect(headerCells).not.toContain("Tgt");
    expect(headerCells).not.toContain("Dev");
  });

  it('renders "Current" and "Deviation" on the allocation panel legend, not the old "NOW"/"DEV" abbreviations', () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const panel = [...host!.querySelectorAll("section")].find(
      (s) => s.querySelector("h2")?.textContent === "Asset allocation",
    );
    expect(panel).toBeTruthy();
    const spans = [...panel!.querySelectorAll("span")].map((s) => s.textContent?.trim());
    expect(spans).toContain("Current");
    expect(spans).toContain("Deviation");
    expect(spans).not.toContain("NOW");
    expect(spans).not.toContain("DEV");
  });
});

// app-open-02 task 3: band zones on the front-page allocation panel
// (AllocationDonut, "Asset allocation" beside "Plan growth"). The
// coordinator's ruling (2026-08-16, superseding the by-goal reading in
// app-open-01): rows become MEMBER-CLASS rows grouped under goal headers —
// the same heading-then-members idiom the lower table (PerfTable) already
// uses — each class row drawing its OWN real bandLoPct-bandHiPct zone, not
// an invented sum-of-members band on the goal header (that would show the
// player numbers they never set — the exact BAND_PCT sin task 2 removed).
describe("CioDashboard — allocation panel band zones (app-open-02 task 3)", () => {
  // BandBar's muted band-zone underlay is drawn as this exact literal
  // (CioDashboard.tsx's BandBar, already shipped by task 2's PerfTable
  // wiring) — happy-dom renders inline rgba with a space after each comma,
  // confirmed against the already-shipped PerfTable row before writing this
  // selector. It is the ONLY element in a class row painted with this
  // colour (the watch zones use amber, the fill uses the alert/level
  // colour), so filtering on it picks the band zone uniquely.
  const BAND_ZONE_BG = "rgba(88, 180, 158, 0.13)";

  function allocationPanel(): HTMLElement {
    const panel = [...host!.querySelectorAll("section")].find(
      (s) => s.querySelector("h2")?.textContent === "Asset allocation",
    );
    if (!panel) throw new Error('no "Asset allocation" panel found');
    return panel as HTMLElement;
  }

  function bandZonesIn(container: Element): HTMLElement[] {
    return [...container.querySelectorAll("div")].filter(
      (d) => (d as HTMLElement).style.backgroundColor === BAND_ZONE_BG,
    ) as HTMLElement[];
  }

  it("a member class's band zone sits at lo/hi on the row's own max scale", () => {
    // A single-goal, single-class view keeps the row's max (the same
    // Math.max(cur, target, bandHi) * 1.05 headroom pattern as PerfTable's
    // `max`, computed independently here, not imported from the component)
    // fully predictable: max = 45.1 * 1.05 = 47.355.
    const v: CioView = JSON.parse(JSON.stringify(view));
    v.allocation.goals = [{ id: "g1", label: "Solo goal" }];
    v.allocation.classes = [
      {
        id: "c1",
        label: "Solo class",
        goalId: "g1",
        targetPct: 41,
        bandLoPct: 36.9,
        bandHiPct: 45.1,
        currentPct: 40,
        value: 1,
        returns: [],
      },
    ];
    render(<CioDashboard view={v} onPlaneChange={() => {}} />);
    const zones = bandZonesIn(allocationPanel());
    expect(zones.length).toBe(1);
    const max = Math.max(40, 41, 45.1) * 1.05;
    expect(parseFloat(zones[0].style.left)).toBeCloseTo((36.9 / max) * 100, 1);
    expect(parseFloat(zones[0].style.width)).toBeCloseTo(((45.1 - 36.9) / max) * 100, 1);
  });

  it("cash (a null band) renders no zone", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const panel = allocationPanel();
    const cashRow = [...panel.querySelectorAll("div")].find(
      (d) => (d.textContent ?? "").trim().startsWith("Cash") && d.querySelector("span"),
    );
    expect(cashRow).toBeTruthy();
    expect(bandZonesIn(cashRow as Element).length).toBe(0);
  });

  it("a non-cash class with a null band (branch-review I1: book-silent sleeve) renders no zone either", () => {
    const v: CioView = JSON.parse(JSON.stringify(view));
    const commodities = v.allocation.classes.find((c) => c.id === "commodities")!;
    commodities.bandLoPct = null;
    commodities.bandHiPct = null;
    render(<CioDashboard view={v} onPlaneChange={() => {}} />);
    const panel = allocationPanel();
    const commoditiesRow = [...panel.querySelectorAll("div")].find(
      (d) => (d.textContent ?? "").trim().startsWith("Commodities") && d.querySelector("span"),
    );
    expect(commoditiesRow).toBeTruthy();
    expect(bandZonesIn(commoditiesRow as Element).length).toBe(0);
  });

  it("renders one band zone per class that carries a band — 9 of the fixture's 10 classes (cash excluded)", () => {
    // was 8 of 9 before the fourth private class (infra) joined the fixture
    // at er14-04b Task S8.
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    expect(bandZonesIn(allocationPanel()).length).toBe(9);
  });

  it("goal headers show no band zone of their own — only member-class rows draw one", () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const panel = allocationPanel();
    // the fixture's own goal labels (cioView.ts's Goal.label, as authored
    // by cio-sample.reported.json) — CSS text-transform: uppercase is a
    // paint-time effect and never changes textContent, so this asserts the
    // actual DOM text, not the rendered casing.
    for (const label of ["Growth", "Real return", "Income", "Diversifiers"]) {
      const header = [...panel.querySelectorAll("span")].find((s) => s.textContent === label);
      expect(header).toBeTruthy();
      // the header's own line (its parent) carries no band zone — the zones
      // that exist for this goal live on its member-class rows, siblings of
      // this header line, not on the heading line itself.
      expect(bandZonesIn(header!.parentElement as Element).length).toBe(0);
    }
  });

  it('legend renders "Target", not the old "TGT" abbreviation, and gains a band swatch', () => {
    render(<CioDashboard view={view} onPlaneChange={() => {}} />);
    const panel = allocationPanel();
    expect(panel.textContent).toContain("Target");
    expect([...panel.querySelectorAll("span")].some((s) => s.textContent?.trim() === "TGT")).toBe(false);
    // the swatch is a small block painted the same muted band colour as the
    // zones themselves, so the legend and the rows read as one language.
    const swatches = [...panel.querySelectorAll("span")].filter(
      (s) => (s as HTMLElement).style.backgroundColor === BAND_ZONE_BG,
    );
    expect(swatches.length).toBeGreaterThan(0);
  });
});
