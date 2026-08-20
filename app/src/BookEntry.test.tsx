/**
 * The book entry screen (su-app-06).
 *
 * The screen validates SHAPE only. Every value that matters comes from the
 * server (DN-3 W5), so these tests assert on totals, sleeve names and the
 * touched/untouched book statement (`ranked-note` — worded around ranked
 * ELIGIBILITY before the app-open-02 park, and around the book's own
 * touched/untouched state since, per owner ruling 2026-08-16) — never on
 * NAV, coverage or alpha.
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
import type { DefaultBookResponse, Rung } from "./lib/session";

/**
 * ER-14 close-out (D-ER14-2, er14-04c Task A2): infrastructure's fifteen-rung
 * ladder (one rung per year of pm_infra's contractual life, ER-12's staggered
 * seeding), pulled from the real server payload
 * (`default_opening_book(GEN_START_TARGETS)`, this file's own regeneration
 * instruction) rather than invented — it is IDENTICAL under the toy and the
 * generated target sets below, because both carry the same infra target (5).
 */
const INFRA_RUNGS: Rung[] = [
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.032777048909130704,
      unfunded: 0.3418177957666488,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.032777048909130704,
      nav_reported: 0.032777048909130704,
      cumulative_distributions: 0.0,
    },
    identity: { vintage_year: 2019 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.1408533600855862,
      unfunded: 0.23374148459019325,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.14910648806185522,
      nav_reported: 0.14910648806185522,
      cumulative_distributions: 2.8724249691272705e-5,
    },
    identity: { vintage_year: 2018 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.21697711807949738,
      unfunded: 0.15761772659628207,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.24498884490806908,
      nav_reported: 0.24498884490806908,
      cumulative_distributions: 0.0004898262691950227,
    },
    identity: { vintage_year: 2017 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.25764449254763283,
      unfunded: 0.11695035212814664,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.3127451463190014,
      nav_reported: 0.3127451463190014,
      cumulative_distributions: 0.002534623111309532,
    },
    identity: { vintage_year: 2016 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.28304893000027403,
      unfunded: 0.09154591467550541,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.36849701753637376,
      nav_reported: 0.36849701753637376,
      cumulative_distributions: 0.008069527906904767,
    },
    identity: { vintage_year: 2015 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.29904901027817715,
      unfunded: 0.07554583439760228,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.41429392206647875,
      nav_reported: 0.41429392206647875,
      cumulative_distributions: 0.019731413947794086,
    },
    identity: { vintage_year: 2014 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.30975925351469247,
      unfunded: 0.06483559116108699,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.44996019269560344,
      nav_reported: 0.44996019269560344,
      cumulative_distributions: 0.04072218260872906,
    },
    identity: { vintage_year: 2013 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.3189510899310302,
      unfunded: 0.055643754744749224,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.4746544604069393,
      nav_reported: 0.4746544604069393,
      cumulative_distributions: 0.07458843335792985,
    },
    identity: { vintage_year: 2012 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.32683978627890165,
      unfunded: 0.04775505839687778,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.4839297571607243,
      nav_reported: 0.4839297571607243,
      cumulative_distributions: 0.12463508392782004,
    },
    identity: { vintage_year: 2011 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.33361009062834684,
      unfunded: 0.040984754047432584,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.47405114915217345,
      nav_reported: 0.47405114915217345,
      cumulative_distributions: 0.19296699636719997,
    },
    identity: { vintage_year: 2010 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.3394205590457913,
      unfunded: 0.035174285629988124,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.44316675750495577,
      nav_reported: 0.44316675750495577,
      cumulative_distributions: 0.27944478337173195,
    },
    identity: { vintage_year: 2009 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.34440726887263773,
      unfunded: 0.030187575803141683,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.3923962129870718,
      nav_reported: 0.3923962129870718,
      cumulative_distributions: 0.38084838801701226,
    },
    identity: { vintage_year: 2008 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.3486870055669306,
      unfunded: 0.025907839108848814,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.326357111989186,
      nav_reported: 0.326357111989186,
      cumulative_distributions: 0.4907005738453172,
    },
    identity: { vintage_year: 2007 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.3523599977418252,
      unfunded: 0.022234846933954243,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.2526810121028336,
      nav_reported: 0.2526810121028336,
      cumulative_distributions: 0.6001191265430497,
    },
    identity: { vintage_year: 2006 },
  },
  {
    commitment: {
      committed: 0.37459484467577947,
      paid_in: 0.35551226445365985,
      unfunded: 0.019082580222119578,
      recallable_balance: 0,
      cumulative_recycled: 0,
    },
    value: {
      nav_true: 0.1803948781996038,
      nav_reported: 0.1803948781996038,
      cumulative_distributions: 0.6997045780783809,
    },
    identity: { vintage_year: 2005 },
  },
];

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
 *
 * ER-14 close-out (er14-04c Task A2): regenerated against the real served
 * shape (`default_opening_book(GEN_START_TARGETS)`, this world's four-sleeve
 * generated target set) rather than hand-edited — infra joins at its real
 * carved target (5, the equity carve 41 -> 38 and the real estate carve
 * 7 -> 5 that funded it, `src/ah/port/adapter.py`'s `GEN_START_TARGETS`
 * comment, Task S4/A15).
 */
const DEFAULT_RESPONSE: DefaultBookResponse = {
  book: {
    state_version: "opening-book-0.3",
    liquid: { equity: 38, bonds: 12, hy: 5, commodities: 5 },
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
            committed: 1,
            paid_in: 0.5,
            unfunded: 0.5,
            recallable_balance: 0,
            cumulative_recycled: 0,
          },
          value: { nav_true: 5, nav_reported: 5, cumulative_distributions: 0 },
          identity: { vintage_year: 2019 },
        },
      ],
      infra: INFRA_RUNGS,
    },
    cash: 2,
    // the nine-sleeve SAA, equal to the values on the derived default
    // (38 + 12 + 5 + 5 + 20 + 8 + 5 + 5 = 98, + 2 cash = 100)
    targets: {
      equity: 38,
      bonds: 12,
      hy: 5,
      commodities: 5,
      pe: 20,
      pc: 8,
      re: 5,
      infra: 5,
    },
    // app-open-01 delta 1: +/-10% of each target above, one decimal place —
    // matches `default_band` exactly, not invented here.
    ranges: {
      equity: [34.2, 41.8],
      bonds: [10.8, 13.2],
      hy: [4.5, 5.5],
      commodities: [4.5, 5.5],
      pe: [18, 22],
      pc: [7.2, 8.8],
      re: [4.5, 5.5],
      infra: [4.5, 5.5],
    },
  },
  plan: {
    state_version: "commitment-plan-0.1",
    points: { pe: [3.6], pc: [1.44], re: [0.9], infra: [0.9] },
  },
  liquid_sleeves: ["equity", "bonds", "hy", "commodities"],
  book_digest: "a".repeat(64),
  plan_digest: "b".repeat(64),
  // branch-review I2: ah.play's own COMMIT_CAP_MULTIPLE / _ANNUAL_COMMITMENT_RATE
  // (2.0, 0.18) — mirrored here as the literal values, not re-imported,
  // because this file stands in for the served response.
  plan_cap: { multiple: 2.0, annual_rate: 0.18 },
};

/**
 * A world that DOES carry reits. The default fixture above is a five-sleeve
 * (generated) world (four liquid, ER-14's fourth private class), so "five
 * target rows, not six" [sic — see the tests below, which state the real
 * counts] is only a real claim about the server driving the sleeve set if
 * some other fixture produces a different count from the same component.
 * This is that fixture: 33 + 12 + 5 + 5 + 5 = 60 liquid, + 38 private, + 2
 * cash = 100, with targets equal to values — the real toy `START_TARGETS`
 * carve (reits 8 -> 5, re 7 -> 5, funding infra's 5; equity untouched at 33).
 */
const REITS_RESPONSE: DefaultBookResponse = {
  ...DEFAULT_RESPONSE,
  book: {
    ...DEFAULT_RESPONSE.book,
    liquid: { equity: 33, bonds: 12, hy: 5, commodities: 5, reits: 5 },
    targets: {
      equity: 33,
      bonds: 12,
      hy: 5,
      commodities: 5,
      reits: 5,
      pe: 20,
      pc: 8,
      re: 5,
      infra: 5,
    },
    // equity's own band moves with its own target (33, not 38); reits gets
    // its own +/-10% band at its real (carved) target; the rest are
    // unchanged from above.
    ranges: { ...DEFAULT_RESPONSE.book.ranges, equity: [29.7, 36.3], reits: [4.5, 5.5] },
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

/**
 * app-open-02: unlike `stubFetch`, which always answers the same body no
 * matter what URL is asked, the ladder-rebuild tests need `/book/default`
 * (fetched on mount) and `/book/ladder` (fetched on the Rebuild click) to
 * answer DIFFERENTLY — so this routes by a substring match on the URL,
 * first match wins, and throws loudly on an unstubbed URL rather than
 * silently returning the wrong body.
 */
function stubFetchRouted(
  routes: { match: string; ok: boolean; status?: number; body: unknown }[],
) {
  const fn = vi.fn((url: string) => {
    const route = routes.find((r) => String(url).includes(r.match));
    if (!route) throw new Error(`unstubbed fetch: ${url}`);
    const status = route.status ?? (route.ok ? 200 : 422);
    return Promise.resolve({
      ok: route.ok,
      status,
      statusText: String(status),
      json: () => Promise.resolve(route.body),
    });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
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
    expect(equity.value).toBe("38");
  });

  it("shows the running total and reports 100 for the default", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("book-total").textContent).toContain("100");
  });

  it("a value edit no longer blocks Play - weights derive and the posted book rescales (app-open-03)", async () => {
    // INVERTED 2026-08-19 (app-open-03, owner-reported): this test used to
    // pin `expect(findButton(/play/i).disabled).toBe(true)` at total 112 —
    // the exact deadlock the owner hit ("if it is increased the book doesn't
    // add to 100 so wont go forward, but there is no way to adjust the
    // weights"). Values are now free-scale and the WEIGHTS derive
    // (value/total, live, summing to 100 by construction); Play posts the
    // book rescaled to the contract's 100-point scale. The running total
    // still reads 112 — it is the typed number, not a gate.
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    const equity = byLabel<HTMLInputElement>("equity");
    setValue(equity, "50");
    expect(byTestId("book-total").textContent).toContain("112");
    expect(findButton(/play/i).disabled).toBe(false);
    // the weight column moved with the edit: 50/112 = 44.6%, and the
    // private cells re-derived against the same new denominator
    expect(byLabel<HTMLInputElement>("equity weight").value).toBe("44.6");
    expect(byTestId("weight-pe").textContent).toContain("17.9"); // 20/112
    act(() => findButton(/play/i).click());
    const posted = onReady.mock.calls[0][0];
    const postedTotal =
      Object.values(posted.liquid as Record<string, number>).reduce((a, b) => a + b, 0) +
      (Object.values(posted.private as Record<string, { value: { nav_true: number } }[]>)
        .flat()
        .reduce((a, r) => a + r.value.nav_true, 0) as number) +
      (posted.cash as number);
    expect(postedTotal).toBeCloseTo(100, 6);
    // the posted book preserves the typed weights exactly: equity holds
    // 50/112 of the rescaled book
    expect(posted.liquid.equity).toBeCloseTo((50 / 112) * 100, 6);
    // and the rescale kept the rung identity: paid_in + unfunded still
    // equals committed + recycled on every rung
    for (const rungs of Object.values(
      posted.private as Record<
        string,
        { commitment: Record<string, number> }[]
      >,
    )) {
      for (const r of rungs) {
        expect(r.commitment.paid_in + r.commitment.unfunded).toBeCloseTo(
          r.commitment.committed + r.commitment.cumulative_recycled,
          9,
        );
      }
    }
  });

  it("renders only the sleeves the world carries", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    // present: proves the default fixture actually rendered, not just an
    // absence that would also be true of a blank/broken screen
    expect(host!.querySelector('[aria-label="equity"]')).not.toBeNull();
    expect(host!.querySelector('[aria-label="reits"]')).toBeNull();
  });

  // Copy changed for the ranked PARK (owner ruling 2026-08-16, D-SP-6
  // session): the note used to state ranked ELIGIBILITY ("ranked is
  // available" / "practice only"), which is misleading now that ranked is
  // parked and every session runs as practice regardless. The three tests
  // below still pin the underlying touched-flag (`isDefault`) logic — an
  // untouched book and an edited one must still render DIFFERENT text —
  // only the strings they assert changed.

  it("says the book is the served default while it is untouched", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("ranked-note").textContent).toMatch(/is the served default book/i);
  });

  it("says the book has been edited once anything is changed", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const bonds = byLabel<HTMLInputElement>("bonds");
    setValue(bonds, "12.5");
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
  });

  it("the untouched statement comes back when an edit is reverted", async () => {
    // isDefault is a deep-equal against the served default, not a one-way
    // "touched" flag: putting a value back must restore the untouched
    // statement. A regression to a sticky boolean (set true on any
    // onChange, never re-checked against the server value) would pass
    // every OTHER test in this file while failing this one — see the fix
    // report's bite-proof. Unchanged by the park: only the copy moved.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const bonds = byLabel<HTMLInputElement>("bonds");
    setValue(bonds, "12.5");
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
    setValue(bonds, "12");
    expect(byTestId("ranked-note").textContent).toMatch(/is the served default book/i);
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
    act(() => findButton(/play/i).click());
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
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
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
    expect(findButton(/play/i).disabled).toBe(true);
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
    expect(findButton(/play/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/paid_in \+ unfunded/);
  });

  it("the default book satisfies every shape rule the screen enforces", async () => {
    // the other half of the two tests above: a gate that blocked everything
    // would pass them both and ship a screen nobody can leave.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    expect(findButton(/play/i).disabled).toBe(false);
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
    act(() => findButton(/play/i).click());
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
    // sleeve carries one, the four liquid AND every private class (ER-14
    // close-out: pe/pc/re/infra). app-open-01 delta 1: the bands are ALSO
    // the server's now, defaulted to +/-10% of the target (38 -> 34.2/41.8,
    // 20 -> 18/22) rather than left blank.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byLabel<HTMLInputElement>("equity target").value).toBe("38");
    expect(byLabel<HTMLInputElement>("commodities target").value).toBe("5");
    expect(byLabel<HTMLInputElement>("pe target").value).toBe("20");
    expect(byLabel<HTMLInputElement>("re target").value).toBe("5");
    expect(byLabel<HTMLInputElement>("infra target").value).toBe("5");
    expect(byLabel<HTMLInputElement>("equity range lo").value).toBe("34.2");
    expect(byLabel<HTMLInputElement>("equity range hi").value).toBe("41.8");
    expect(byLabel<HTMLInputElement>("pe range lo").value).toBe("18");
    expect(byLabel<HTMLInputElement>("pe range hi").value).toBe("22");
    expect(byLabel<HTMLInputElement>("infra range lo").value).toBe("4.5");
    expect(byLabel<HTMLInputElement>("infra range hi").value).toBe("5.5");
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
    expect(byTestId("ranked-note").textContent).toMatch(/is the served default book/i);
    act(() => findButton(/play/i).click());
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
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
    setValue(byLabel<HTMLInputElement>("equity target"), "38");
    expect(byTestId("ranked-note").textContent).toMatch(/is the served default book/i);
  });

  it("a band with lo at or above hi blocks the commit and names the reason", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "40");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "40");
    expect(findButton(/play/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/lo below hi/i);
    // and the other half: a WELL-FORMED band does not block, so this is not
    // "any band blocks" passing for the wrong reason.
    setValue(byLabel<HTMLInputElement>("equity range hi"), "45");
    expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    expect(findButton(/play/i).disabled).toBe(false);
  });

  it("a band entered on one side only blocks the commit", async () => {
    // app-open-01 delta 1: every band now arrives PRE-FILLED (both sides),
    // so "one side only" has to be produced by clearing the side the server
    // filled in, not by typing into a screen that started blank.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe range hi"), "");
    expect(findButton(/play/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/both lo and hi/i);
  });

  it("posts an edited band as [lo, hi], leaving every other sleeve at its own default", async () => {
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "30");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "45");
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
    act(() => findButton(/play/i).click());
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
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
    setValue(byLabel<HTMLInputElement>("equity range lo"), "34.2");
    setValue(byLabel<HTMLInputElement>("equity range hi"), "41.8");
    expect(byTestId("ranked-note").textContent).toMatch(/is the served default book/i);
    act(() => findButton(/play/i).click());
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
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
    act(() => findButton(/play/i).click());
    const { equity: _equity, ...rest } = DEFAULT_RESPONSE.book.ranges as Record<
      string,
      [number, number]
    >;
    expect(onReady.mock.calls[0][0].ranges).toEqual(rest);
    expect(onReady.mock.calls[0][2]).toBe(false);
  });

  describe("commitment plan pre-flight cap check (branch-review I2)", () => {
    // DEFAULT_RESPONSE: pe target 20, plan.points.pe = [3.6], plan_cap
    // {multiple: 2.0, annual_rate: 0.18} -> cap = 2.0 * target * 0.18.
    // At target 20 the cap is 7.2 (3.6 comfortably under it); dropping pe to
    // 5 drops the cap to 1.8, which 3.6 now exceeds. equity absorbs the
    // 15-point move so the targets still total 100 -- isolating the plan-cap
    // fault from the unrelated "targets do not total 100" one. Equity's own
    // base moved 41 -> 38 at ER-14's close-out (infra's carve), so the
    // absorbing figure is 38 + 15 = 53, not the old 56.
    function lowerPeBelowItsCap() {
      setValue(byLabel<HTMLInputElement>("equity target"), "53");
      setValue(byLabel<HTMLInputElement>("pe target"), "5");
    }

    it("lowering a private target below the plan's own cap blocks Play and names the sleeve and window", async () => {
      stubFetch();
      await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
      expect(findButton(/play/i).disabled).toBe(false);
      lowerPeBelowItsCap();
      expect(findButton(/play/i).disabled).toBe(true);
      const faults = byTestId("shape-faults").textContent ?? "";
      expect(faults).toMatch(/pe plan year 0/);
      expect(faults).toMatch(/exceeds the commitment cap for a 5\.0 target/);
    });

    it("restoring the target above the cap threshold clears the fault and re-enables Play", async () => {
      stubFetch();
      await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
      lowerPeBelowItsCap();
      expect(findButton(/play/i).disabled).toBe(true);
      setValue(byLabel<HTMLInputElement>("equity target"), "38");
      setValue(byLabel<HTMLInputElement>("pe target"), "20");
      expect(findButton(/play/i).disabled).toBe(false);
      expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    });

    it("does not fault a plan that is comfortably inside the cap at the served default", async () => {
      stubFetch();
      await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
      expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    });
  });

  it("shows the policy weight the target implies, not the number typed", async () => {
    // the drift readout. Typed targets are RELATIVE since app-open-03: 51
    // out of 111 typed target points, filling the 98% cash leaves, is
    // 45.0% — so a readout that merely echoed the typed number would print
    // "51.0" and fail here. That is the point: the implied weight is NOT
    // the number in the box, it is the target as it will be POSTED.
    // (History: this asserted 45.1 — target/(sum targets + cash) — until
    // app-open-03 made the readout the posted-target rule, whose sum with
    // cash is exactly 100 by construction; the old denominator's wasn't.)
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("target-weight-equity").textContent).toContain("38.0");
    setValue(byLabel<HTMLInputElement>("equity target"), "51");
    expect(byTestId("target-weight-equity").textContent).toContain("45.0");
    expect(byTestId("target-weight-equity").textContent).not.toContain("51");
  });

  it("shows the drift between the weight held and the weight targeted", async () => {
    // held 38.0 against a policy weight of 45.0 is -7.0 points of drift
    // (was -7.1 under the pre-app-open-03 denominator; see the test above).
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byTestId("target-drift-equity").textContent).toContain("+0.0");
    setValue(byLabel<HTMLInputElement>("equity target"), "51");
    expect(byTestId("target-drift-equity").textContent).toContain("-7.0");
  });

  it("renders one target row per tradeable sleeve this world carries — eight, not nine", async () => {
    // app-open-01 delta 2 + ER-14 close-out: the merged table follows the
    // SERVER's sleeve set across BOTH liquid and private — four liquid (no
    // reits) plus the four private classes (pe/pc/re/infra).
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelectorAll('.policy-grid [aria-label$=" target"]').length).toBe(8);
    expect(host!.querySelector('[aria-label="reits target"]')).toBeNull();
  });

  it("renders nine target rows for a world that does carry reits", async () => {
    // the other half of the claim above: the count follows the SERVER's
    // sleeve set. Without this, "eight, not nine" would also pass a
    // component that hardcoded eight. Was eight before ER-14's close-out;
    // infra is the ninth row.
    stubFetch(REITS_RESPONSE);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelectorAll('.policy-grid [aria-label$=" target"]').length).toBe(9);
    expect(byLabel<HTMLInputElement>("reits target").value).toBe("5");
    expect(byLabel<HTMLInputElement>("infra target").value).toBe("5");
  });

  it("renders a band row and a vintage ladder for infrastructure (ER-14 close-out)", async () => {
    stubFetch(REITS_RESPONSE);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(byLabel<HTMLInputElement>("infra range lo").value).toBe("4.5");
    expect(byLabel<HTMLInputElement>("infra range hi").value).toBe("5.5");
    const t = [...host!.querySelectorAll('[role="tab"]')].find((b) =>
      /historical vintages/i.test(b.textContent ?? ""),
    ) as HTMLButtonElement;
    act(() => t.click());
    expect(host!.querySelectorAll('[data-testid="vintage-chart"]').length).toBe(4);
  });

  it("the infrastructure ladder carries fifteen rungs — one per year of pm_infra's contractual life (ER-12)", async () => {
    stubFetch(REITS_RESPONSE);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const t = [...host!.querySelectorAll('[role="tab"]')].find((b) =>
      /historical vintages/i.test(b.textContent ?? ""),
    ) as HTMLButtonElement;
    act(() => t.click());
    expect(host!.querySelectorAll('[data-testid="rung-infra"]').length).toBe(15);
    // and the other three ladders are untouched at one rung each
    expect(host!.querySelectorAll('[data-testid="rung-pe"]').length).toBe(1);
  });

  it("the merged table has nine rows total: eight tradeable sleeves plus cash", async () => {
    // app-open-01 delta 2: private classes are ROWS of the same table, not a
    // separate strip — this is the bite-proof that they actually landed
    // there, on the world's default (no-reits) fixture. Was eight rows
    // before ER-14's close-out added infra.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(host!.querySelectorAll(".policy-grid .policy-row").length).toBe(9);
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
      "Infrastructure",
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

  it("pins the private value cell to the SUM of the ladder's rung NAVs, and editing a rung moves it", async () => {
    // Task 6 (verification, owner-dictated): the value cell must be the
    // ladder's own arithmetic, not a static echo of a served total — a
    // second rung on pe (nav_true 10, alongside the fixture's existing
    // rung 0 at 20) makes "20.0" only reachable by actually summing both
    // rows, and editing EITHER rung must move the cell by exactly the
    // typed delta. This is the client half of the tie-out task; the
    // server half is test_serve_book.py's
    // "test_cio_month_zero_private_value_ties_to_the_book_ladder" — both
    // assert on the same ladder-sum claim, which is the point of pinning
    // both rather than either alone (see that test's docstring).
    const twoRungPe = JSON.parse(JSON.stringify(DEFAULT_RESPONSE)) as DefaultBookResponse;
    twoRungPe.book.private.pe.push({
      commitment: {
        committed: 2,
        paid_in: 1,
        unfunded: 1,
        recallable_balance: 0,
        cumulative_recycled: 0,
      },
      value: { nav_true: 10, nav_reported: 10, cumulative_distributions: 0 },
      identity: { vintage_year: 2020 },
    });
    stubFetch(twoRungPe);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    // 20 (rung 0) + 10 (rung 1) — reachable only by summing both rows
    expect(byTestId("value-pe").textContent).toBe("30.0");
    setValue(byLabel<HTMLInputElement>("pe rung 1 nav_true"), "15");
    expect(byTestId("value-pe").textContent).toBe("35.0");
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_true"), "5");
    expect(byTestId("value-pe").textContent).toBe("20.0");
    // an edit on ONE sleeve's ladder must not move another sleeve's cell
    expect(byTestId("value-pc").textContent).toBe("8.0");
  });

  it("a target override on a private sleeve still works, exactly like a liquid one", async () => {
    // task requirement: an override still works once the classes are moved
    // into the merged table — same setter, same validation, same digest
    // consequence as any liquid sleeve's target edit.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe target"), "26");
    expect(byLabel<HTMLInputElement>("pe target").value).toBe("26");
    expect(byTestId("ranked-note").textContent).toMatch(/has been edited from the served default/i);
  });

  it("targets that do not total 100 with cash rescale on Play instead of blocking (app-open-03)", async () => {
    // INVERTED 2026-08-19 (app-open-03): this pinned the "targets do not
    // total 100" gate. That gate became a deadlock generator once values
    // went free-scale — a VALUE edit moves the cash weight, which moves the
    // required target total out from under correctly-entered targets, and
    // the analyst was left chasing decimals. Typed targets are RELATIVE
    // now: the posted document rescales them to fill exactly what the cash
    // weight leaves (the same identity `validate_book` enforces), so this
    // book plays, and its posted targets satisfy the identity by
    // construction.
    stubFetch();
    const onReady = vi.fn();
    await render(<BookEntry runId="r1" onReady={onReady} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity target"), "45");
    expect(byTestId("book-total").textContent).toContain("100");
    expect(findButton(/play/i).disabled).toBe(false);
    expect(host!.querySelector('[data-testid="shape-faults"]')).toBeNull();
    act(() => findButton(/play/i).click());
    const posted = onReady.mock.calls[0][0];
    const targetTotal = Object.values(posted.targets as Record<string, number>).reduce(
      (a, b) => a + b,
      0,
    );
    expect(targetTotal + posted.cash).toBeCloseTo(100, 6);
    // and the typed ratios survived the rescale: equity was typed at 45 of
    // 105 target points, filling the 98 points cash leaves
    expect(posted.targets.equity).toBeCloseTo((45 / 105) * 98, 6);
  });

  it("blocks the commit on a negative target even when the targets still total 100", async () => {
    // equity -1 and bonds 51 nets to the same 98 + 2 cash (equity+bonds was
    // 38+12=50; -1+51=50), so this cannot pass by way of the total check.
    // Bonds' figure moved 54 -> 51 when equity's own base moved 41 -> 38 at
    // ER-14's close-out.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity target"), "-1");
    setValue(byLabel<HTMLInputElement>("bonds target"), "51");
    expect(findButton(/play/i).disabled).toBe(true);
    expect(byTestId("shape-faults").textContent).toMatch(/target is negative/i);
    expect(byTestId("shape-faults").textContent).not.toMatch(/targets do not total 100/i);
  });
});

/**
 * app-open-02 (owner-dictated): a NEW total value for an illiquid asset
 * class, regenerated into a vintage ladder server-side (`GET /book/ladder`)
 * instead of hand-edited rung by rung. Never a client-side arithmetic
 * substitute — the returned rungs replace `book.private[sleeve]` wholesale,
 * exactly as a served reset does.
 */
describe("BookEntry — rebuild a private ladder to a new value", () => {
  const NEW_PE_RUNGS = [
    {
      commitment: {
        committed: 3,
        paid_in: 1.5,
        unfunded: 1.5,
        recallable_balance: 0,
        cumulative_recycled: 0,
      },
      value: { nav_true: 6, nav_reported: 6, cumulative_distributions: 0 },
      identity: { vintage_year: 2022 },
    },
    {
      commitment: {
        committed: 3,
        paid_in: 1.5,
        unfunded: 1.5,
        recallable_balance: 0,
        cumulative_recycled: 0,
      },
      value: { nav_true: 6, nav_reported: 6, cumulative_distributions: 0 },
      identity: { vintage_year: 2021 },
    },
  ];

  it("replaces only the rebuilt sleeve's rungs and moves its value cell to the new sum", async () => {
    stubFetchRouted([
      { match: "/book/default", ok: true, body: DEFAULT_RESPONSE },
      { match: "/book/ladder", ok: true, body: { rungs: NEW_PE_RUNGS } },
    ]);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rebuild value"), "12");
    act(() => byLabel<HTMLButtonElement>("pe rebuild ladder").click());
    await flush();
    // 6 + 6 = 12, reachable only from the server's own rungs, not a local echo
    expect(byTestId("value-pe").textContent).toBe("12.0");
    expect(byLabel<HTMLInputElement>("pe rung 1 nav_true").value).toBe("6");
    // the OTHER private sleeve's ladder is untouched
    expect(byTestId("value-pc").textContent).toBe("8.0");
    expect(byLabel<HTMLInputElement>("pc rung 0 nav_true").value).toBe("8");
  });

  it("sends the typed value, sleeve and run_id in the query string", async () => {
    const fn = stubFetchRouted([
      { match: "/book/default", ok: true, body: DEFAULT_RESPONSE },
      { match: "/book/ladder", ok: true, body: { rungs: [] } },
    ]);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pc rebuild value"), "9.5");
    act(() => byLabel<HTMLButtonElement>("pc rebuild ladder").click());
    await flush();
    const call = fn.mock.calls.find(([url]) => String(url).includes("/book/ladder"));
    expect(call).toBeDefined();
    const url = String(call![0]);
    expect(url).toContain("run_id=r1");
    expect(url).toContain("sleeve=pc");
    expect(url).toContain("value=9.5");
  });

  it("a refused rebuild shows the endpoint's detail and leaves the book unchanged", async () => {
    stubFetchRouted([
      { match: "/book/default", ok: true, body: DEFAULT_RESPONSE },
      {
        match: "/book/ladder",
        ok: false,
        status: 422,
        body: { detail: "value must be > 0, got -5.0" },
      },
    ]);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rebuild value"), "-5");
    act(() => byLabel<HTMLButtonElement>("pe rebuild ladder").click());
    await flush();
    expect(byTestId("ladder-error-pe").textContent).toMatch(/value must be > 0/);
    // never partially applied: pe's ladder still reads exactly as served
    expect(byTestId("value-pe").textContent).toBe("20.0");
    expect(byLabel<HTMLInputElement>("pe rung 0 nav_true").value).toBe("20");
  });

  it("a fresh rebuild attempt clears a previous error once it succeeds", async () => {
    let ladderCalls = 0;
    const fn = vi.fn((url: string) => {
      const u = String(url);
      if (u.includes("/book/default")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: "200",
          json: () => Promise.resolve(DEFAULT_RESPONSE),
        });
      }
      ladderCalls += 1;
      if (ladderCalls === 1) {
        return Promise.resolve({
          ok: false,
          status: 422,
          statusText: "422",
          json: () => Promise.resolve({ detail: "value must be > 0, got -5.0" }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "200",
        json: () => Promise.resolve({ rungs: NEW_PE_RUNGS }),
      });
    });
    vi.stubGlobal("fetch", fn);
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rebuild value"), "-5");
    act(() => byLabel<HTMLButtonElement>("pe rebuild ladder").click());
    await flush();
    expect(byTestId("ladder-error-pe").textContent).toMatch(/value must be > 0/);
    setValue(byLabel<HTMLInputElement>("pe rebuild value"), "12");
    act(() => byLabel<HTMLButtonElement>("pe rebuild ladder").click());
    await flush();
    expect(host!.querySelector('[data-testid="ladder-error-pe"]')).toBeNull();
    expect(byTestId("value-pe").textContent).toBe("12.0");
  });
});

/**
 * Task 8 (owner-dictated 2026-08-16): the screen becomes three tabs — Targets
 * and bands / Historical vintages / Cashflow projections — with a single
 * "Play" control at the top replacing the old bottom "Continue" button. Tabs
 * are display-only: all three panels stay mounted so typed state, the
 * derived book and faults survive a tab round-trip, and a fault raised on a
 * hidden tab still blocks Play and is still readable next to it.
 */
describe("BookEntry — tabs and Play (task 8)", () => {
  function tab(label: RegExp): HTMLButtonElement {
    const btn = [...host!.querySelectorAll('[role="tab"]')].find((b) =>
      label.test(b.textContent ?? ""),
    );
    if (!btn) throw new Error(`no tab matching ${label}`);
    return btn as HTMLButtonElement;
  }

  function panelFor(label: RegExp): HTMLElement {
    const controls = tab(label).getAttribute("aria-controls");
    if (!controls) throw new Error("tab has no aria-controls");
    const panel = host!.querySelector<HTMLElement>(`#${controls}`);
    if (!panel) throw new Error(`no panel #${controls}`);
    return panel;
  }

  it("defaults to Targets and bands; the other two panels are hidden", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    expect(tab(/targets and bands/i).getAttribute("aria-selected")).toBe("true");
    expect(panelFor(/targets and bands/i).hidden).toBe(false);
    expect(panelFor(/historical vintages/i).hidden).toBe(true);
    expect(panelFor(/cashflow projections/i).hidden).toBe(true);
    // and the asset-class table itself is the thing shown
    expect(host!.querySelector(".policy-grid")).not.toBeNull();
  });

  it("switching to Historical vintages shows the ladders and hides the others; typed edits survive the round-trip", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_true"), "25");
    setValue(byLabel<HTMLInputElement>("equity range lo"), "30");
    act(() => tab(/historical vintages/i).click());
    expect(tab(/historical vintages/i).getAttribute("aria-selected")).toBe("true");
    expect(panelFor(/historical vintages/i).hidden).toBe(false);
    expect(panelFor(/targets and bands/i).hidden).toBe(true);
    expect(panelFor(/cashflow projections/i).hidden).toBe(true);
    expect(byLabel<HTMLInputElement>("pe rung 0 nav_true").value).toBe("25");
    // and back — the edits made while another tab was showing survive too
    act(() => tab(/targets and bands/i).click());
    expect(byLabel<HTMLInputElement>("pe rung 0 nav_true").value).toBe("25");
    expect(byLabel<HTMLInputElement>("equity range lo").value).toBe("30");
  });

  it("switching to Cashflow projections shows the commitment plan and hides the others", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    act(() => tab(/cashflow projections/i).click());
    expect(panelFor(/cashflow projections/i).hidden).toBe(false);
    expect(panelFor(/targets and bands/i).hidden).toBe(true);
    expect(panelFor(/historical vintages/i).hidden).toBe(true);
    expect(host!.querySelector('[aria-label="pe plan year 0"]')).not.toBeNull();
  });

  it("a fault raised on the hidden vintages tab still blocks Play while Targets is shown, and reads next to Play", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    act(() => tab(/historical vintages/i).click());
    setValue(byLabel<HTMLInputElement>("pe rung 0 unfunded"), "3");
    act(() => tab(/targets and bands/i).click());
    expect(panelFor(/targets and bands/i).hidden).toBe(false);
    const play = findButton(/play/i);
    expect(play.disabled).toBe(true);
    const faults = byTestId("shape-faults");
    expect(faults.textContent).toMatch(/paid_in \+ unfunded/);
    // "adjacent to the top bar" — the fault text and Play share one container
    expect(play.parentElement).toBe(faults.parentElement);
  });

  it("there is exactly one commit control now, and it is not named Continue", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const buttons = [...host!.querySelectorAll("button")];
    expect(buttons.some((b) => /^continue$/i.test((b.textContent ?? "").trim()))).toBe(
      false,
    );
    expect(buttons.filter((b) => /^play$/i.test((b.textContent ?? "").trim())).length).toBe(
      1,
    );
  });

  it("renders the column head as Asset class, not sleeve", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const head = host!.querySelector(".policy-head")!;
    expect(head.textContent).toMatch(/Asset class/);
    expect(head.textContent ?? "").not.toMatch(/\bsleeve\b/i);
  });

  it("renames the private-value note to Private asset classes", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    const note = host!.querySelector(".book-liquid .book-note")!;
    expect(note.textContent).toMatch(/Private asset classes' value/);
    expect(note.textContent ?? "").not.toMatch(/Private sleeves'/);
  });
});

/**
 * Task 10 (owner-dictated 2026-08-16): each private ladder's section on the
 * Historical vintages tab gets a VintageChart above its table
 * (components/VintageChart.tsx — its own geometry is pinned in
 * VintageChart.test.tsx). This is the integration half: BookEntry passes
 * `book.private[sleeve]` — the LIVE typed state — as the `rungs` prop, not
 * a snapshot, so a hand-edited rung input has to move the chart on the very
 * next render. A component that captured the prop once (or memoized it
 * away) would pass every VintageChart.test.tsx test while failing only
 * this one.
 */
describe("BookEntry — the vintage chart tracks live rung edits (task 10)", () => {
  function openVintagesTab() {
    const t = [...host!.querySelectorAll('[role="tab"]')].find((b) =>
      /historical vintages/i.test(b.textContent ?? ""),
    ) as HTMLButtonElement;
    act(() => t.click());
  }

  it("renders a chart above each sleeve's ladder table, one per private sleeve", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    openVintagesTab();
    const sections = [...host!.querySelectorAll(".book-ladder")];
    expect(sections.length).toBe(4); // pe, pc, re, infra (ER-14 close-out)
    sections.forEach((section) => {
      const chart = section.querySelector('[data-testid="vintage-chart"]');
      expect(chart).not.toBeNull();
      // the chart sits ABOVE the table within the same section (task
      // requirement: "above each sleeve's table (inside the same section)")
      const table = section.querySelector("table");
      expect(table).not.toBeNull();
      expect(
        chart!.compareDocumentPosition(table!) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    });
  });

  it("editing a rung's NAV input moves that vintage's chart marker", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    openVintagesTab();
    // pe is the first private sleeve served (fixture insertion order), so
    // its ladder section is the first .book-ladder on the tab.
    const peSection = host!.querySelectorAll(".book-ladder")[0];
    const marker = () => peSection.querySelector('[data-testid="vintage-nav-0"]')!;
    const before = marker().getAttribute("cy");
    expect(before).not.toBeNull();

    // The fixture's single pe rung has nav_true=20 against paid_in+unfunded
    // of only 4, so nav_true is already the term that SETS the chart's own
    // scale (maxVal = 1.05 * nav_true) — increasing it further keeps its
    // own y ratio invariant (nav/maxVal stays 1/1.05), which would make this
    // assertion pass by accident for the WRONG reason on a single-rung
    // ladder. Editing it down BELOW paid_in+unfunded (here, to 1) hands the
    // scale to the fixed paid_in+unfunded=4 term instead, so the marker's
    // position actually has to move — the real bite-proof for "moves with
    // the live prop", not an artifact of self-scaling.
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_true"), "1");

    const after = marker().getAttribute("cy");
    expect(after).not.toBeNull();
    expect(after).not.toBe(before);

    // and the OTHER sleeve's chart is untouched by pe's edit
    const pcSection = host!.querySelectorAll(".book-ladder")[1];
    const pcBefore = pcSection.querySelector('[data-testid="vintage-nav-0"]')!.getAttribute("cy");
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_true"), "60");
    expect(
      pcSection.querySelector('[data-testid="vintage-nav-0"]')!.getAttribute("cy"),
    ).toBe(pcBefore);
  });
});

/**
 * app-open-03 (owner-reported defects, 2026-08-19): values are the source of
 * truth and weights derive from them live; weights are editable symmetrically
 * (total held fixed, other liquid classes and cash absorb proportionally);
 * no positive-total book can deadlock; and the commitment plan FOLLOWS the
 * book — every book edit re-posts the current (as-posted) book to
 * `POST /book/plan` and replaces the plan grid with the server's answer.
 * The derivation itself lives server-side (`book_commitment_plan`,
 * ah/play.py) — these tests stub the endpoint and assert the round-trip,
 * never plan arithmetic.
 */
describe("BookEntry — weights derive and edit; the plan follows the book (app-open-03)", () => {
  const NEW_PLAN = {
    state_version: "commitment-plan-0.1",
    points: { pe: [2.5], pc: [1.0], re: [0.6], infra: [0.6] },
  };

  function routedWithPlan(
    extra: { match: string; ok: boolean; status?: number; body: unknown }[] = [],
  ) {
    return stubFetchRouted([
      { match: "/book/default", ok: true, body: DEFAULT_RESPONSE },
      ...extra,
      { match: "/book/plan", ok: true, body: { plan: NEW_PLAN, plan_digest: "c".repeat(64) } },
    ]);
  }

  function planCallBodies(fn: ReturnType<typeof stubFetchRouted>) {
    // the route stub's vi.fn is typed on `url` alone, but fetch passes
    // (url, init) — read the recorded init via the untyped call tuple.
    return (fn.mock.calls as unknown as [string, RequestInit][])
      .filter(([url]) => String(url).includes("/book/plan"))
      .map(([, init]) => JSON.parse(init.body as string));
  }

  it("editing a value re-derives every weight, live, summing to 100", async () => {
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    // untouched: equity holds 38 of 100
    expect(byLabel<HTMLInputElement>("equity weight").value).toBe("38");
    setValue(byLabel<HTMLInputElement>("equity"), "88");
    // total is now 150; every weight re-derived against it
    expect(byLabel<HTMLInputElement>("equity weight").value).toBe("58.7"); // 88/150
    expect(byLabel<HTMLInputElement>("bonds weight").value).toBe("8"); // 12/150
    expect(byTestId("weight-pe").textContent).toContain("13.3"); // 20/150
    // and the displayed weights sum to 100 (to display rounding)
    const inputs = ["equity", "bonds", "hy", "commodities", "cash"].map((s) =>
      Number(byLabel<HTMLInputElement>(s + " weight").value),
    );
    const spans = ["pe", "pc", "re", "infra"].map((s) =>
      parseFloat(byTestId("weight-" + s).textContent ?? ""),
    );
    const sum = [...inputs, ...spans].reduce((a, b) => a + b, 0);
    expect(Math.abs(sum - 100)).toBeLessThan(0.5);
  });

  it("editing a weight holds the total fixed and scales the other liquid classes and cash proportionally", async () => {
    // THE rule (stated in the screen's copy): equity to 50% of the unchanged
    // 100-point total -> equity value 50; the absorbers (bonds 12, hy 5,
    // commodities 5, cash 2 = 24) must now hold 12, so each halves; the
    // private ladders are NOT touched from this row.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity weight"), "50");
    expect(byTestId("book-total").textContent).toContain("100");
    expect(byLabel<HTMLInputElement>("equity").value).toBe("50");
    expect(byLabel<HTMLInputElement>("bonds").value).toBe("6");
    expect(byLabel<HTMLInputElement>("hy").value).toBe("2.5");
    expect(byLabel<HTMLInputElement>("cash").value).toBe("1");
    expect(byTestId("value-pe").textContent).toBe("20.0");
    expect(byLabel<HTMLInputElement>("pe rung 0 nav_true").value).toBe("20");
    // whichever field was last edited wins, with no mode toggle: the value
    // input now takes the same class back
    setValue(byLabel<HTMLInputElement>("equity"), "38");
    expect(byLabel<HTMLInputElement>("equity weight").value).toBe("43.2"); // 38/88
  });

  it("no positive-total book can deadlock Play", async () => {
    // the app-open-03 property, straight from the owner's report: whatever
    // the values say, a finite non-negative book with a positive total can
    // proceed. Sweep a few shapes that used to jam the old total gate.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    for (const [sleeve, value] of [
      ["equity", "200"],
      ["cash", "50"],
      ["bonds", "0"],
    ] as const) {
      setValue(byLabel<HTMLInputElement>(sleeve), value);
      expect(findButton(/play/i).disabled).toBe(false);
    }
    for (const s of ["equity", "cash", "hy", "commodities"] as const) {
      setValue(byLabel<HTMLInputElement>(s), "0");
    }
    // privates still hold NAV, so the total is positive and Play stays live
    expect(findButton(/play/i).disabled).toBe(false);
  });

  it("a broken recycling identity names the sleeve, the rung and its vintage, and where to fix it", async () => {
    // review fix round 1 (app-open-03): the identity fault used to say only
    // "a rung breaks paid_in + unfunded = committed + recycled" — the one
    // blocker left below contract C's bar. It must name the offender the way
    // the blank/negative faults do, and say where the fix lives.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("pe rung 0 unfunded"), "3");
    const faults = byTestId("shape-faults").textContent ?? "";
    expect(faults).toMatch(/paid_in \+ unfunded/); // the identity itself, still stated
    expect(faults).toMatch(/pe rung 0 \(vintage 2019\)/); // the offender, named
    expect(faults).toMatch(/historical vintages tab/i); // and where to act
    expect(findButton(/play/i).disabled).toBe(true);
  });

  it("a weight typed beyond what liquid and cash can supply is capped, and the cap says so beside the field", async () => {
    // review fix round 1 (app-open-03): the clamp used to fire silently.
    // Private NAV is 38 of the default 100, so liquid+cash can supply at
    // most 62% — typing 90 applies 62 and must SAY it did, with the number
    // and the reason, next to the weight field.
    stubFetch();
    await render(<BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} />);
    setValue(byLabel<HTMLInputElement>("equity weight"), "90");
    expect(byLabel<HTMLInputElement>("equity").value).toBe("62");
    const note = byTestId("weight-cap-equity").textContent ?? "";
    expect(note).toMatch(/capped at 62(\.0)?%/i);
    expect(note).toMatch(/ladder/i); // the reason: private values move there
    // an un-capped edit clears the note
    setValue(byLabel<HTMLInputElement>("equity weight"), "30");
    expect(host!.querySelector('[data-testid="weight-cap-equity"]')).toBeNull();
  });

  it("a vintage edit re-posts the book and the plan grid follows the server's answer", async () => {
    // symptom 2's core walk: edit a HISTORICAL VINTAGE field -> the plan tab
    // changes. The edit here is a reported mark, which is what the server's
    // pacing flex actually reads (`book_commitment_plan`'s docstring).
    const fn = routedWithPlan();
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("3.6");
    setValue(byLabel<HTMLInputElement>("pe rung 0 nav_reported"), "15");
    await flush();
    await flush();
    const bodies = planCallBodies(fn);
    expect(bodies.length).toBeGreaterThan(0);
    // nav_true was untouched, so the book still totals 100 and is posted
    // VERBATIM — the endpoint sees exactly the typed document
    expect(bodies.at(-1).run_id).toBe("r1");
    expect(bodies.at(-1).book.private.pe[0].value.nav_reported).toBe(15);
    // and the grid is now the SERVER's answer, not a local recompute
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("2.5");
    expect(byLabel<HTMLInputElement>("infra plan year 0").value).toBe("0.6");
  });

  it("a value edit re-posts the book AS IT WOULD BE POSTED - rescaled to 100", async () => {
    const fn = routedWithPlan();
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    setValue(byLabel<HTMLInputElement>("equity"), "88"); // total 150
    await flush();
    await flush();
    const body = planCallBodies(fn).at(-1);
    expect(body).toBeDefined();
    const liquidSum = (Object.values(body.book.liquid) as number[]).reduce((a, b) => a + b, 0);
    const rungs = (Object.values(body.book.private) as { value: { nav_true: number } }[][]).flat();
    const privateSum = rungs.reduce((a, r) => a + r.value.nav_true, 0);
    expect(liquidSum + privateSum + body.book.cash).toBeCloseTo(100, 6);
    expect(body.book.liquid.equity).toBeCloseTo((88 / 150) * 100, 6);
  });

  it("a target edit re-posts the book and carries the posted targets", async () => {
    const fn = routedWithPlan();
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    setValue(byLabel<HTMLInputElement>("pe target"), "10");
    setValue(byLabel<HTMLInputElement>("equity target"), "48");
    await flush();
    await flush();
    const body = planCallBodies(fn).at(-1);
    expect(body).toBeDefined();
    // 48 + 12 + 5 + 5 + 10 + 8 + 5 + 5 = 98 with cash 2: consistent, so the
    // typed targets go through verbatim
    expect(body.book.targets.pe).toBe(10);
    expect(body.book.targets.equity).toBe(48);
  });

  it("a rebuilt ladder re-posts the book and the plan follows", async () => {
    const fn = routedWithPlan([
      {
        match: "/book/ladder",
        ok: true,
        body: {
          rungs: [
            {
              commitment: {
                committed: 3,
                paid_in: 1.5,
                unfunded: 1.5,
                recallable_balance: 0,
                cumulative_recycled: 0,
              },
              value: { nav_true: 12, nav_reported: 12, cumulative_distributions: 0 },
              identity: { vintage_year: 2022 },
            },
          ],
        },
      },
    ]);
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    setValue(byLabel<HTMLInputElement>("pe rebuild value"), "12");
    act(() => byLabel<HTMLButtonElement>("pe rebuild ladder").click());
    await flush();
    await flush();
    expect(byTestId("value-pe").textContent).toBe("12.0");
    expect(planCallBodies(fn).length).toBeGreaterThan(0);
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("2.5");
  });

  it("a hand-edited plan is the analyst's: it stops following book edits until Reset plan", async () => {
    const fn = routedWithPlan();
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    expect(byTestId("plan-note").textContent).toMatch(/derived by the server/i);
    setValue(byLabel<HTMLInputElement>("pe plan year 0"), "5");
    expect(byTestId("plan-note").textContent).toMatch(/taken this plan over by hand/i);
    setValue(byLabel<HTMLInputElement>("equity"), "88");
    await flush();
    await flush();
    // the typed cell survives; the endpoint was never asked
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("5");
    expect(planCallBodies(fn).length).toBe(0);
    // Reset plan hands it back to the server's derivation for the CURRENT book
    act(() => findButton(/^reset plan$/i).click());
    await flush();
    await flush();
    expect(planCallBodies(fn).length).toBeGreaterThan(0);
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("2.5");
    expect(byTestId("plan-note").textContent).toMatch(/derived by the server/i);
  });

  it("a refused recompute shows the server's own message on the tab and does not gate Play", async () => {
    const fn = stubFetchRouted([
      { match: "/book/default", ok: true, body: DEFAULT_RESPONSE },
      {
        match: "/book/plan",
        ok: false,
        status: 422,
        body: { detail: "book totals 150, must total 100" },
      },
    ]);
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    setValue(byLabel<HTMLInputElement>("equity"), "88");
    await flush();
    await flush();
    expect(fn.mock.calls.some(([url]) => String(url).includes("/book/plan"))).toBe(true);
    expect(byTestId("plan-error").textContent).toMatch(/must total 100/);
    // the cap pre-flight and POST /sessions still guard the contract; a
    // display-refresh failure is not a deadlock
    expect(findButton(/play/i).disabled).toBe(false);
  });

  it("an untouched book never asks for a recompute and keeps the served plan verbatim", async () => {
    const fn = routedWithPlan();
    await render(
      <BookEntry runId="r1" onReady={vi.fn()} onCancel={vi.fn()} planRecomputeDelayMs={0} />,
    );
    await flush();
    await flush();
    expect(planCallBodies(fn).length).toBe(0);
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("3.6");
    // and reverting an edit restores the served plan without a round-trip
    setValue(byLabel<HTMLInputElement>("bonds"), "13");
    await flush();
    await flush();
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("2.5"); // followed the edit
    setValue(byLabel<HTMLInputElement>("bonds"), "12");
    await flush();
    expect(byLabel<HTMLInputElement>("pe plan year 0").value).toBe("3.6"); // served again
    expect(byTestId("ranked-note").textContent).toMatch(/is the served default book/i);
  });
});
