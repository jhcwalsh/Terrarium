/**
 * app-open-01: a live UX blocker in the vitrine overlay (Play.tsx, the
 * full-screen `.vitrine` — position:fixed, closed by the X button, exactly
 * what App.tsx mounts for mode==="play").
 *
 * The owner played "The Lost Decade" to the Y1 decision stop (server design:
 * a window at month m is decidable once the pointer sits at m+1; this
 * fixture's windows are bundle.summary.decision_months = [11, 23, ..., 107])
 * and could not find the decision controls; the screenshot also showed two
 * text/button elements overprinted in the footer's bottom-right corner.
 *
 * Root cause: `.vgrid .right` in styles.css still carried a THREE-row
 * `grid-template-rows` (`auto minmax(0, 1fr) auto`) left over from before
 * Book.tsx was deleted (Play.tsx's own comment on the stat rail notes the
 * deletion: "Deleting Book.tsx did not close the basis mismatch..."). The
 * column now renders only TWO children — `.wire-panel` then
 * `.decision-panel` — so CSS grid auto-placement mapped the wire to the
 * "auto" (uncapped, content-sized) track and the decision panel to the
 * "minmax(0, 1fr)" (freely-shrinkable) track: the exact inverse of the
 * documented intent ("the book and the decision keep their height, the wire
 * takes the slack"). Under a viewport too short for the wire's natural
 * content, the decision panel got squeezed toward zero height and its own
 * `overflow: hidden` clipped it — except CSS grid track sizing left it a
 * sliver of its natural box, which painted UNDER the app footer below it
 * (the footer has no background, only `color`), producing the observed
 * overprint of the decision panel's eyebrow ("Committee in session" /
 * "commit to continue") on top of the footer's own text ("RUN ... SEED ...
 * REPLAYABLE FROM SEED"). `.vgrid .right.deciding` carried the same stale
 * three-row template (its own comment even claimed "Book mode only: the
 * column still has 3 rows (book, wire, decision) here" — no longer true).
 * The cockpit-mode counterparts (`.cockpit .vgrid .right` /
 * `.cockpit .vgrid .right.deciding`) were correctly fixed to two rows at
 * cio-03 and never had this bug — only the book-mode rules were missed in
 * that sweep.
 *
 * Idiom note: this project has neither @testing-library/react nor
 * jest-dom (see BookEntry.test.tsx's task-7 correction) — createRoot + act,
 * raw DOM queries, fetch stubbed via vi.stubGlobal, matching
 * DecisionWindow.test.tsx / BookEntry.test.tsx / CioDashboard.test.tsx.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { webcrypto } from "node:crypto";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Play } from "./Play";
import { parseBundle } from "./lib/bundle";
import type { WorldBundle } from "./lib/bundle";
import type { CioView } from "./lib/cioView";
import type { Session } from "./lib/session";
import cioSample from "../fixtures/cio-sample.reported.json";

if (!globalThis.crypto?.subtle) {
  // happy-dom leaves WebCrypto off the global; Node's implementation matches
  Object.defineProperty(globalThis, "crypto", { value: webcrypto });
}

const FIXTURE = resolve(process.cwd(), "fixtures", "toy.bundle.gz");
const STYLES = resolve(process.cwd(), "src", "styles.css");

async function loadBundle(): Promise<WorldBundle> {
  const buf = readFileSync(FIXTURE);
  const bytes = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const { bundle } = await parseBundle(bytes);
  return bundle;
}

function makeSession(bundle: WorldBundle, overrides: Partial<Session> = {}): Session {
  return {
    session_id: "s1",
    run_id: bundle.meta.run_id,
    world_id: bundle.meta.world_id,
    months: bundle.meta.months,
    revealed_months: 0,
    basis: "reported",
    ranked: false,
    participant: null,
    decisions: {},
    window_log: [],
    status: "active",
    decision_windows: bundle.summary.decision_months,
    value: null,
    twin_value: null,
    forced_sales: [],
    next_plan_commitments: null,
    next_plan_basis: null,
    plan_pace: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, statusText: "200", json: () => Promise.resolve(body) };
}

function stubFetch(session: Session, cioView?: CioView) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";
      if (url === "/sessions" && method === "POST") {
        return Promise.resolve(jsonResponse(session));
      }
      if (cioView && /^\/sessions\/[^/]+\/cio\?/.test(url) && method === "GET") {
        return Promise.resolve(jsonResponse(cioView));
      }
      return Promise.reject(new Error(`Play.overlay.test: unstubbed fetch ${method} ${url}`));
    }),
  );
}

/** Splits a `grid-template-rows` value into its track list, respecting
 * parens (`minmax(0, 1fr)` is ONE track, not two, despite the comma). */
function tokenizeTracks(value: string): string[] {
  const tokens: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of value.trim()) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === " " && depth === 0) {
      if (cur) tokens.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  if (cur) tokens.push(cur);
  return tokens;
}

/** Finds a CSS rule by its EXACT selector (after splitting comma-grouped
 * selectors and trimming) and returns its body. Comment-stripped first so
 * prose that merely mentions a selector (this file's stylesheet has plenty)
 * can never match. */
function ruleBody(css: string, selector: string): string {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const re = /([^{}]+)\{([^}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(stripped))) {
    const selectors = m[1].split(",").map((s) => s.trim());
    if (selectors.includes(selector)) return m[2];
  }
  throw new Error(`rule not found in styles.css: ${selector}`);
}

function gridTemplateRowsTracks(css: string, selector: string): string[] {
  const body = ruleBody(css, selector);
  const m = /grid-template-rows:\s*([^;]+);/.exec(body);
  if (!m) throw new Error(`${selector} has no grid-template-rows`);
  return tokenizeTracks(m[1]);
}

let root: Root | null = null;
let host: HTMLElement | null = null;

async function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  // Play's session opens via a fetch effect; flush a macrotask so the
  // stubbed fetch -> res.json() -> the effect's .then() fully settles
  // before assertions run (matches BookEntry.test.tsx's render()).
  await act(async () => {
    root!.render(ui);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.unstubAllGlobals();
});

describe("the vitrine overlay at a decision stop (app-open-01)", () => {
  it("surfaces the decision window's open controls directly — book mode", async () => {
    const bundle = await loadBundle();
    const firstWindow = bundle.summary.decision_months[0];
    // the server design: a window at month m is decidable once the pointer
    // sits at m+1, and the server refuses to advance past it undecided —
    // this is the observed state, "0/9 decision windows decided".
    const session = makeSession(bundle, {
      revealed_months: firstWindow + 1,
      decisions: {},
    });
    stubFetch(session);
    await render(<Play bundle={bundle} onExit={() => {}} />);

    const panel = host!.querySelector(".decision-panel");
    expect(panel).not.toBeNull();
    expect(panel!.querySelector(".eyebrow")!.textContent).toMatch(/committee in session/i);

    const dw = panel!.querySelector(".decision-window")!;
    expect(dw.className).not.toContain("closed");
    expect(dw.textContent).toMatch(/the window is open/i);

    // the four levers are selectable and a commit button exists — a player
    // landing here has something to click, not a blank or crushed panel
    expect(dw.querySelectorAll('input[type="radio"]').length).toBe(4);
    const commit = dw.querySelector("button.commit");
    expect(commit).not.toBeNull();
    expect(commit!.textContent).toMatch(/choose an action to commit/i);
  });

  it("stays reachable in book mode too — the decision panel is not CIO-mode-only", async () => {
    // Was: "stays reachable after switching into CIO view" — book mode was
    // the default and this test switched INTO cio to prove the panel
    // survived. app-open-01 item 1 made cio the default (the front door);
    // inverted rather than deleted (CLAUDE.md) to prove the same claim in
    // the other direction — the panel survives switching OUT of the new
    // default and into book.
    const bundle = await loadBundle();
    const firstWindow = bundle.summary.decision_months[0];
    const session = makeSession(bundle, {
      revealed_months: firstWindow + 1,
      decisions: {},
    });
    stubFetch(session, cioSample as unknown as CioView);
    await render(<Play bundle={bundle} onExit={() => {}} />);

    const modeswitch = host!.querySelector<HTMLButtonElement>("button.modeswitch")!;
    expect(modeswitch.textContent).toMatch(/book view/i);
    await act(async () => {
      modeswitch.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const panel = host!.querySelector(".decision-panel");
    expect(panel).not.toBeNull();
    const dw = panel!.querySelector(".decision-window")!;
    expect(dw.className).not.toContain("closed");
    expect(dw.querySelector("button.commit")).not.toBeNull();
  });

  it("the footer and the decision panel are distinct, non-nested containers, and the right column's CSS grid tracks match its actual children (the mismatch that let them overprint)", async () => {
    const bundle = await loadBundle();
    const firstWindow = bundle.summary.decision_months[0];
    const session = makeSession(bundle, {
      revealed_months: firstWindow + 1,
      decisions: {},
    });
    stubFetch(session);
    await render(<Play bundle={bundle} onExit={() => {}} />);

    // Two <footer> elements legitimately exist (HTML5 sectioning): the
    // app-chrome one direct under .vitrine, and DecisionWindow's own
    // commit-button footer nested inside .decision-panel when a window is
    // open. The overlap this bug produced was the APP footer being bled
    // into by the decision panel's content above it — so the outer,
    // direct-child footer is the one that matters here.
    const footer = host!.querySelector<HTMLElement>("main.vitrine > footer")!;
    expect(footer).not.toBeNull();
    const decisionPanel = host!.querySelector(".decision-panel")!;
    // structurally distinct: neither contains the other
    expect(footer.contains(decisionPanel)).toBe(false);
    expect(decisionPanel.contains(footer)).toBe(false);

    // the actual DOM shape this bug depended on: exactly two children under
    // .vgrid .right (wire-panel, decision-panel — Book.tsx is gone)
    const rightChildren = host!.querySelectorAll(".vgrid .right > section");
    expect(rightChildren.length).toBe(2);
    expect([...rightChildren].map((el) => el.className)).toEqual([
      "wire-panel",
      "decision-panel",
    ]);

    // the CSS must declare exactly as many row tracks as there are children.
    // Fewer tracks than children silently drops the extras onto whatever
    // track is left; MORE tracks than children (the actual bug: three tracks
    // for two children) mis-maps which child gets which sizing rule, which
    // is what let the decision panel be squeezed to a sliver that painted
    // under the footer below it.
    const css = readFileSync(STYLES, "utf8");
    const rightTracks = gridTemplateRowsTracks(css, ".vgrid .right");
    expect(rightTracks.length).toBe(rightChildren.length);

    // atWindow !== null adds the "deciding" class (Play.tsx), which swaps in
    // a second grid-template-rows — same two children, same requirement.
    expect(host!.querySelector(".vgrid .right")!.className).toContain("deciding");
    const decidingTracks = gridTemplateRowsTracks(css, ".vgrid .right.deciding");
    expect(decidingTracks.length).toBe(rightChildren.length);
  });
});

describe("the CIO is the front door (app-open-01 item 1)", () => {
  it("renders the CIO, populated, immediately after a session opens — no click required", async () => {
    // A freshly opened session (revealed_months: 0) is exactly the state
    // right after the opening book is confirmed and RankedSetup hands off
    // to Play — the server now serves a real CioView here (cio-05), and
    // the front door is the dashboard, not the timeline.
    const bundle = await loadBundle();
    const session = makeSession(bundle, { revealed_months: 0, decisions: {} });
    stubFetch(session, cioSample as unknown as CioView);
    await render(<Play bundle={bundle} onExit={() => {}} />);

    // the modeswitch already reads "Book view" — proof CIO is the CURRENT
    // mode, not something reached by a click.
    const modeswitch = host!.querySelector<HTMLButtonElement>("button.modeswitch")!;
    expect(modeswitch.textContent).toMatch(/book view/i);
    expect(host!.querySelector("main")!.className).toContain("cockpit");

    // populated with STARTING values from the served payload — not the
    // loading placeholder, not the "no closed quarter" error the old
    // default (revealed_months 409ing at month 0) used to force.
    const pane = host!.querySelector(".cockpit-pane")!;
    expect(pane).not.toBeNull();
    expect(pane.textContent).not.toMatch(/loading the cio view/i);
    expect(pane.textContent).not.toMatch(/no closed quarter/i);
    expect(pane.textContent).toContain("Stagflation"); // meta.worldTitle
    expect(pane.textContent).toMatch(/Plan growth/i);
    // app-open-01 item 1 (owner ruling 2026-08-16): the CIO headline is the
    // $10bn display denomination now — 64.5205 points -> usd() -> $6.45bn
    // (two-decimal bn precision is review round fix 3), not the raw
    // meta.unitLabel figure this used to assert. The figure moved off
    // 62.1323/$6.21bn at er14-04b Task S8, when the fixture was regenerated
    // to carry the fourth private class (infra); re-pinned here (er14-04c).
    expect(pane.textContent).toContain("$6.45bn"); // plan.totalValue via usd()

    // the timeline is reached FROM here, not removed — every existing
    // route stays reachable (constraint: reordering, not removal).
    await act(async () => {
      modeswitch.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(host!.querySelector(".chart-grid")).not.toBeNull();
    expect(
      host!.querySelector<HTMLButtonElement>("button.modeswitch")!.textContent,
    ).toMatch(/cio view/i);
  });
});
