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

const DEFAULT_RESPONSE: DefaultBookResponse = {
  book: {
    state_version: "opening-book-0.1",
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
  },
  plan: { state_version: "commitment-plan-0.1", points: { pe: [3.6], pc: [1.44], re: [1.26] } },
  liquid_sleeves: ["equity", "bonds", "hy", "commodities"],
  book_digest: "a".repeat(64),
  plan_digest: "b".repeat(64),
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

  it("restores only the targeted sleeve's ladder with reset", async () => {
    // Edit BOTH pe and pc, then reset only pc. "pe" is the FIRST private
    // sleeve served (fixture insertion order), so a broken implementation
    // that always resets "whichever sleeve is first" would pass a test that
    // only ever clicked "Reset pe" — clicking "Reset pc" here and asserting
    // pe's edit survives is what actually pins the button to its own sleeve.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_true"), "25");
    setValue(byLabel<HTMLInputElement>("pc rung 0 nav_true"), "99");
    act(() => findButton(/reset pc/i).click());
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
