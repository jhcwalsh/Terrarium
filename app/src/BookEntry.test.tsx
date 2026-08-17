/**
 * The book entry screen (su-app-06).
 *
 * The screen validates SHAPE only. Every value that matters comes from the
 * server (DN-3 W5), so these tests assert on totals, sleeve names and the
 * ranked-availability statement — never on NAV, coverage or alpha.
 *
 * Idiom note (task-7 CORRECTION, 2026-08-16): this project has neither
 * @testing-library/react nor jest-dom. Rendering uses createRoot + act
 * (react-dom/client), queries are raw DOM against the host element, and
 * fetch is stubbed via vi.stubGlobal — matching RankedSetup.test.tsx and
 * CioDashboard.test.tsx.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BookEntry } from "./BookEntry";
import type { DefaultBookResponse } from "./lib/session";

/**
 * su-app-07 Ruling D: the SERVER pre-fills `targets` (equal to the values on
 * the derived default). app-open-01 delta 1 (owner-dictated 2026-08-16)
 * changed what it fills `ranges` with: no longer `null`, but +/-10% of each
 * target (`default_band` in `src/ah/port/book.py`) — the fixture mirrors
 * that exactly, because the whole ranked-eligibility question is a digest
 * comparison against what the server sent. A fixture that omitted these keys
 * would let a client that invents targets or bands locally, or posts a
 * document the server would not have, pass every test in this file while
 * silently stripping RANKED from an untouched book on the real service.
 */
const DEFAULT_RESPONSE: DefaultBookResponse = {
  book: {
    state_version: "opening-book-0.2",
    liquid: { equity: 41, bonds: 12, hy: 5, commodities: 5 },
    private: {
      pe: [
        {
          commitment: {
            committed: 4,
            paid_in: 2,
            unfunded: 2,
            recallable_balance: 0,
            cumulative_recycled: 0,
          },
          value: { nav_true: 20, nav_reported: 20, cumulative_distributions: 0 },
          identity: { vintage_year: 2019 },
        },
      ],
      pc: [
        {
          commitment: {
            committed: 1.6,
            paid_in: 0.8,
            unfunded: 0.8,
            recallable_balance: 0,
            cumulative_recycled: 0,
          },
          value: { nav_true: 8, nav_reported: 8, cumulative_distributions: 0 },
          identity: { vintage_year: 2019 },
        },
      ],
      re: [
        {
          commitment: {
            committed: 1.4,
            paid_in: 0.7,
            unfunded: 0.7,
            recallable_balance: 0,
            cumulative_recycled: 0,
          },
          value: { nav_true: 7, nav_reported: 7, cumulative_distributions: 0 },
          identity: { vintage_year: 2019 },
        },
      ],
    },
    cash: 2,
    // the eight-sleeve SAA, equal to the values on the derived default
    // (41 + 12 + 5 + 5 + 20 + 8 + 7 = 98, + 2 cash = 100)
    targets: { equity: 41, bonds: 12, hy: 5, commodities: 5, pe: 20, pc: 8, re: 7 },
    // app-open-01 delta 1: +/-10% of each target above, one decimal place
    // (41 -> +/-4.1, 12 -> +/-1.2, 5 -> +/-0.5, 20 -> +/-2.0, 8 -> +/-0.8,
    // 7 -> +/-0.7) — matches `default_band` exactly, not invented here.
    ranges: {
      equity: [36.9, 45.1],
      bonds: [10.8, 13.2],
      hy: [4.5, 5.5],
      commodities: [4.5, 5.5],
      pe: [18, 22],
      pc: [7.2, 8.8],
      re: [6.3, 7.7],
    },
  },
  plan: { state_version: "commitment-plan-0.1", points: { pe: [3.6], pc: [1.44], re: [1.26] } },
  liquid_sleeves: ["equity", "bonds", "hy", "commodities"],
  book_digest: "a".repeat(64),
  plan_digest: "b".repeat(64),
};

/**
 * A world that DOES carry reits. The default fixture above is a four-sleeve
 * (generated) world, so "four target rows, not five" is only a real claim
 * about the server driving the sleeve set if some other fixture produces
 * five from the same component. This is that fixture: 33 + 12 + 5 + 5 + 8 =
 * 63 liquid, + 35 private, + 2 cash = 100, with targets equal to values.
 */
const REITS_RESPONSE: DefaultBookResponse = {
  ...DEFAULT_RESPONSE,
  book: {
    ...DEFAULT_RESPONSE.book,
    liquid: { equity: 33, bonds: 12, hy: 5, commodities: 5, reits: 8 },
    targets: { equity: 33, bonds: 12, hy: 5, commodities: 5, reits: 8, pe: 20, pc: 8, re: 7 },
    // equity's own band moves with its own target (33, not 41); reits gets
    // its own +/-10% band (8 -> +/-0.8); the rest are unchanged from above.
    ranges: { ...DEFAULT_RESPONSE.book.ranges, equity: [29.7, 36.3], reits: [7.2, 8.8] },
  },
  liquid_sleeves: ["equity", "bonds", "hy", "commodities", "reits"],
};

let root: Root | null = null;
let host: HTMLElement | null = null;

async function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  // the component fetches on mount; flush a macrotask so the stubbed
  // fetch()'s promise chain (fetch -> res.json() -> the effect's .then())
  // fully settles before assertions run, without hand-counting microticks.
  await act(async () => {
    root!.render(ui);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function stubFetch(response: unknown = DEFAULT_RESPONSE) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: "200",
        json: () => Promise.resolve(response),
      }),
    ),
  );
}

function byLabel<T extends HTMLElement = HTMLElement>(label: string): T {
  const el = host!.querySelector<T>(`[aria-label="${label}"]`);
  if (!el) throw new Error(`no element with aria-label "${label}"`);
  return el;
}

function byTestId(id: string): HTMLElement {
  const el = host!.querySelector<HTMLElement>(`[data-testid="${id}"]`);
  if (!el) throw new Error(`no element with data-testid "${id}"`);
  return el;
}

function findButton(matcher: RegExp): HTMLButtonElement {
  const btn = [...host!.querySelectorAll("button")].find((b) =>
    matcher.test(b.textContent ?? ""),
  );
  if (!btn) throw new Error(`no button matching ${matcher}`);
  return btn as HTMLButtonElement;
}

function setValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!
    .set!;
  act(() => {
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.unstubAllGlobals();
});

describe("BookEntry", () => {
  it("opens pre-filled with the served default, never blank", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const equity = byLabel<HTMLInputElement>("equity");
    expect(equity.value).toBe("41");
  });

  it("shows the running total and reports 100 for the default", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("book-total").textContent).toContain("100");
  });

  it("blocks the commit when the total is not 100", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const equity = byLabel<HTMLInputElement>("equity");
    setValue(equity, "50");
    expect(byTestId("book-total").textContent).toContain("109");
    expect(findButton(/continue/i).disabled).toBe(true);
  });

  it("renders only the sleeves the world carries", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    // present: proves the default fixture actually rendered, not just an
    // absence that would also be true of a blank/broken screen
    expect(host!.querySelector('[aria-label="equity"]')).not.toBeNull();
    expect(host!.querySelector('[aria-label="reits"]')).toBeNull();
  });

  it("says ranked is available while the book is untouched", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("ranked-note").textContent).toMatch(/ranked is available/i);
  });

  it("says ranked is lost once anything is edited", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const bonds = byLabel<HTMLInputElement>("bonds");
    setValue(bonds, "12.5");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
  });

  it("ranked comes back when an edit is reverted", async () => {
    // isDefault is a deep-equal against the served default, not a one-way
    // "touched" flag: putting a value back must restore ranked eligibility.
    // A regression to a sticky boolean (set true on any onChange, never
    // re-checked against the server value) would pass every OTHER test in
    // this file while failing this one — see the fix report's bite-proof.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const bonds = byLabel<HTMLInputElement>("bonds");
    setValue(bonds, "12.5");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
    setValue(bonds, "12");
    expect(byTestId("ranked-note").textContent).toMatch(/ranked is available/i);
  });

  it("restores only the targeted sleeve's ladder with reset", async () => {
    // Edit BOTH pe and pc, then reset only pc. "pe" is the FIRST private
    // sleeve served (fixture insertion order), so a broken implementation
    // that always resets "whichever sleeve is first" would pass a test that
    // only ever clicked "Reset Private Equity" — clicking "Reset Private
    // Credit" here and asserting pe's edit survives is what actually pins
    // the button to its own sleeve.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_true"), "25");
    setValue(byLabel<HTMLInputElement>("pc rung 0 nav_true"), "99");
    act(() => findButton(/reset private credit/i).click());
    expect(byLabel<HTMLInputElement>("pc rung 0 nav_true").value).toBe("8");
    expect(byLabel<HTMLInputElement>("pe rung 0 nav_true").value).toBe("25");
  });

  it("hands back isDefault=true for an untouched book", async () => {
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    act(() => findButton(/continue/i).click());
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady.mock.calls[0][2]).toBe(true);
  });

  it("reopens on what was typed, not on the server default", async () => {
    /**
     * su-app-06 (I3). `POST /sessions` happens two screens later, so a 422
     * there dropped the analyst back here with the screen re-seeded from
     * `GET /book/default` — up to 210 entered fields gone. `initialBook`
     * carries the retained entry back in. The DEFAULT is still fetched (it is
     * what `isDefault` and the per-sleeve resets compare against), so this
     * cannot be satisfied by skipping the fetch.
     */
    stubFetch();
    const typed = JSON.parse(JSON.stringify(DEFAULT_RESPONSE.book));
    typed.liquid.equity = 36;
    typed.liquid.bonds = 17;
    await render(
      <BookEntry
        runId="r1"
        initialBook={typed}
        initialPlan={DEFAULT_RESPONSE.plan}
        onReady={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(byLabel<HTMLInputElement>("equity").value).toBe("36");
    expect(byLabel<HTMLInputElement>("bonds").value).toBe("17");
    // and it is still measured against the SERVER's default, not against
    // itself: a retained edit is still an edit.
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
    // the per-sleeve reset still restores the server's ladder
    act(() => findButton(/reset private equity/i).click());
    expect(byLabel<HTMLInputElement>("pe rung 0 nav_true").value).toBe("20");
  });

  it("blocks the commit on a negative field even when the total still reaches 100", async () => {
    // spec section 7's "negative anything". Netting -1 against +1 keeps the
    // total at 100, so this cannot pass by way of the total check.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("hy"), "-1");
    setValue(byLabel<HTMLInputElement>("bonds"), "18");
    expect(byTestId("book-total").textContent).toContain("100");
    expect(findButton(/continue/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/negative/i);
  });

  it("blocks the commit when a rung breaks the recycling identity", async () => {
    // paid_in + unfunded = committed + cumulative_recycled (NOT the simpler
    // = committed, which recycling can legitimately break). nav_true is
    // untouched, so the total stays at 100 and only this rule is under test.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rung 0 unfunded"), "3");
    expect(byTestId("book-total").textContent).toContain("100");
    expect(findButton(/continue/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/paid_in \+ unfunded/);
  });

  it("the default book satisfies every shape rule the screen enforces", async () => {
    // the other half of the two tests above: a gate that blocked everything
    // would pass them both and ship a screen nobody can leave.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    expect(findButton(/continue/i).disabled).toBe(false);
  });

  it("hands back isDefault=false once the book has been edited", async () => {
    // The untouched case alone could pass a component that always returns
    // true; this is the other half of that same claim.
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    // hy +1, bonds -1: net zero, so the total STAYS at 100 and continue
    // stays enabled — isolates isDefault from the total-blocking behaviour
    // covered by the earlier test, rather than confounding the two.
    const hy = byLabel<HTMLInputElement>("hy");
    setValue(hy, "6");
    const bonds = byLabel<HTMLInputElement>("bonds");
    setValue(bonds, "11");
    expect(byTestId("book-total").textContent).toContain("100");
    act(() => findButton(/continue/i).click());
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady.mock.calls[0][2]).toBe(false);
  });
});

/**
 * su-app-07 section 6: the screen separates the institution's POLICY TARGETS
 * from its opening VALUES, and takes reporting bands.
 *
 * Two things these tests deliberately do NOT assert, because the screen must
 * not do them: no band STATUS (ok/watch/breach) is computed here — that is
 * the server's `band_report` (DN-3 W5) — and no NAV, coverage or alpha. The
 * only arithmetic under test is shape: totals, signs, `lo < hi`, and the
 * implied weight readout.
 */
describe("BookEntry — policy targets and reporting bands", () => {
  it("pre-fills every target from the served book, and every band at its default", async () => {
    // Ruling D: the targets are the SERVER's, not synthesized here — every
    // sleeve carries one, the four liquid AND pe/pc/re. app-open-01 delta 1:
    // the bands are ALSO the server's now, defaulted to +/-10% of the
    // target (41 -> 36.9/45.1, 20 -> 18/22) rather than left blank.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byLabel<HTMLInputElement>("equity target").value).toBe("41");
    expect(byLabel<HTMLInputElement>("commodities target").value).toBe("5");
    expect(byLabel<HTMLInputElement>("pe target").value).toBe("20");
    expect(byLabel<HTMLInputElement>("re target").value).toBe("7");
    expect(byLabel<HTMLInputElement>("equity range lo").value).toBe("36.9");
    expect(byLabel<HTMLInputElement>("equity range hi").value).toBe("45.1");
    expect(byLabel<HTMLInputElement>("pe range lo").value).toBe("18");
    expect(byLabel<HTMLInputElement>("pe range hi").value).toBe("22");
  });

  it("an untouched pre-fill is still the default book, so ranked survives", async () => {
    // THE ruling-D test. `serve.py` demotes a session to practice-only when
    // the posted book's digest differs from the served default's, so a screen
    // that invented its own targets or bands — or altered what the server
    // sent in any way — would strip RANKED from a book nobody edited,
    // silently. app-open-01 delta 1 changed WHAT the default `ranges` is
    // (no longer `null`); this test still pins that whatever it is, it is
    // posted back verbatim.
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    expect(byTestId("ranked-note").textContent).toMatch(/ranked is available/i);
    act(() => findButton(/continue/i).click());
    expect(onReady.mock.calls[0][2]).toBe(true);
    const posted = onReady.mock.calls[0][0];
    expect(posted.targets).toEqual(DEFAULT_RESPONSE.book.targets);
    expect(posted.ranges).toEqual(DEFAULT_RESPONSE.book.ranges);
    // and the whole document is byte-for-byte what was served
    expect(JSON.stringify(posted)).toBe(JSON.stringify(DEFAULT_RESPONSE.book));
  });

  it("editing a target flips the ranked note to practice-only, and reverting restores it", async () => {
    // a target is part of the book's digest, exactly like a value — so it
    // behaves exactly like the weight edit the su-app-06 tests pin. The
    // revert half proves this is measured against the SERVER's default and
    // not a sticky "touched" flag.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity target"), "35");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
    setValue(byLabel<HTMLInputElement>("equity target"), "41");
    expect(byTestId("ranked-note").textContent).toMatch(/ranked is available/i);
  });

  it("a band with lo at or above hi blocks the commit and names the reason", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "40");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "40");
    expect(findButton(/continue/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/lo below hi/i);
    // and the other half: a WELL-FORMED band does not block, so this is not
    // "any band blocks" passing for the wrong reason.
    setValue(byLabel<HTMLInputElement>("equity range hi"), "45");
    expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    expect(findButton(/continue/i).disabled).toBe(false);
  });

  it("a band entered on one side only blocks the commit", async () => {
    // app-open-01 delta 1: every band now arrives PRE-FILLED (both sides),
    // so "one side only" has to be produced by clearing the side the server
    // filled in, not by typing into a screen that started blank.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe range hi"), "");
    expect(findButton(/continue/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/both lo and hi/i);
  });

  it("posts an edited band as [lo, hi], leaving every other sleeve at its own default", async () => {
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "30");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "45");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
    act(() => findButton(/continue/i).click());
    expect(onReady.mock.calls[0][0].ranges).toEqual({
      ...DEFAULT_RESPONSE.book.ranges,
      equity: [30, 45],
    });
  });

  it("retyping the served default band exactly restores ranked eligibility", async () => {
    // the deletability half of delta 1: moving a band away from the default
    // costs ranked, and typing the SAME default value back — not clearing
    // it, since the default is no longer empty — restores it.
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "30");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "45");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "36.9");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "45.1");
    expect(byTestId("ranked-note").textContent).toMatch(/ranked is available/i);
    act(() => findButton(/continue/i).click());
    expect(onReady.mock.calls[0][0].ranges).toEqual(DEFAULT_RESPONSE.book.ranges);
    expect(onReady.mock.calls[0][2]).toBe(true);
  });

  it("clearing a sleeve's band demotes to practice and drops only that sleeve", async () => {
    // the other half: since the default is no longer empty, clearing a
    // band is itself an edit now (it no longer reproduces `null`) — the
    // posted `ranges` keeps every OTHER sleeve's default and omits only the
    // one cleared.
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
    act(() => findButton(/continue/i).click());
    const { equity: _equity, ...rest } = DEFAULT_RESPONSE.book.ranges as Record<
      string,
      [number, number]
    >;
    expect(onReady.mock.calls[0][0].ranges).toEqual(rest);
    expect(onReady.mock.calls[0][2]).toBe(false);
  });

  it("shows the policy weight the target implies, not the number typed", async () => {
    // the drift readout. 51 out of (108 targets + 2 cash) is 46.4% — so a
    // readout that merely echoed the typed number would print "51.0" and
    // fail here. That is the point: while the targets are mid-edit and do
    // not yet total 100, the implied weight is NOT the number in the box.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("target-weight-equity").textContent).toContain("41.0");
    setValue(byLabel<HTMLInputElement>("equity target"), "51");
    expect(byTestId("target-weight-equity").textContent).toContain("46.4");
    expect(byTestId("target-weight-equity").textContent).not.toContain("51");
  });

  it("shows the drift between the weight held and the weight targeted", async () => {
    // held 41.0 against a policy weight of 46.4 is -5.4 points of drift.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("target-drift-equity").textContent).toContain("+0.0");
    setValue(byLabel<HTMLInputElement>("equity target"), "51");
    expect(byTestId("target-drift-equity").textContent).toContain("-5.4");
  });

  it("renders one target row per tradeable sleeve this world carries — seven, not eight", async () => {
    // app-open-01 delta 2: the merged table follows the SERVER's sleeve set
    // across BOTH liquid and private — four liquid (no reits) plus pe/pc/re.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelectorAll('.policy-grid [aria-label$=" target"]').length).toBe(7);
    expect(host!.querySelector('[aria-label="reits target"]')).toBeNull();
  });

  it("renders eight target rows for a world that does carry reits", async () => {
    // the other half of the claim above: the count follows the SERVER's
    // sleeve set. Without this, "seven, not eight" would also pass a
    // component that hardcoded seven.
    stubFetch(REITS_RESPONSE);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelectorAll('.policy-grid [aria-label$=" target"]').length).toBe(8);
    expect(byLabel<HTMLInputElement>("reits target").value).toBe("8");
  });

  it("the merged table has eight rows total: seven tradeable sleeves plus cash", async () => {
    // app-open-01 delta 2: private classes are ROWS of the same table, not a
    // separate strip — this is the bite-proof that they actually landed
    // there, on the world's default (no-reits) fixture.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelectorAll(".policy-grid .policy-row").length).toBe(8);
  });

  it("shows every sleeve's full, capitalized name — never a lowercase code", async () => {
    // app-open-01 delta 3, pinned on the same merged table delta 2 built.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const names = [...host!.querySelectorAll(".policy-grid .policy-name")].map(
      (n) => n.textContent,
    );
    expect(names).toEqual([
      "Equities",
      "Bonds",
      "High Yield",
      "Commodities",
      "Private Equity",
      "Private Credit",
      "Real Estate",
      "Cash",
    ]);
  });

  it("shows a private sleeve's held value as the ladder's own total, read-only", async () => {
    // app-open-01 delta 2: the private row's "value" cell is not a second,
    // editable copy of the ladder's total — it displays the same
    // `nav_true` sum the ladder table computes, and there is no input to
    // set it from this row.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("value-pe").textContent).toBe("20.0");
    expect(host!.querySelector('.policy-grid input[aria-label="pe"]')).toBeNull();
  });

  it("a target override on a private sleeve still works, exactly like a liquid one", async () => {
    // task requirement: an override still works once the classes are moved
    // into the merged table — same setter, same validation, same digest
    // consequence as any liquid sleeve's target edit.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe target"), "26");
    expect(byLabel<HTMLInputElement>("pe target").value).toBe("26");
    expect(byTestId("ranked-note").textContent).toMatch(/practice only/i);
  });

  it("blocks the commit when the targets do not total 100 with cash", async () => {
    // the VALUES still total 100 — only the targets are off — so the fault
    // named must be the targets' own, not the book total's.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity target"), "45");
    expect(byTestId("book-total").textContent).toContain("100");
    expect(findButton(/continue/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/targets do not total 100/i);
  });

  it("blocks the commit on a negative target even when the targets still total 100", async () => {
    // equity -1 and bonds 54 nets to the same 98 + 2 cash, so this cannot
    // pass by way of the total check.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity target"), "-1");
    setValue(byLabel<HTMLInputElement>("bonds target"), "54");
    expect(findButton(/continue/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/target is negative/i);
    expect(byTestId("shape-faults").textContent).not.toMatch(/targets do not total 100/i);
  });
});
