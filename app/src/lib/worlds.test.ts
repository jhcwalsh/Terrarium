/**
 * sib-01 acceptance: the decade picker's data contract and its render.
 *
 * fetch is mocked following session.test.ts's convention — the CONTRACT
 * (the /worlds shape, malformed-doc rejection) is what these tests pin; the
 * server's own behavior is pinned by the Python suite (tests/test_serve.py).
 * The render test follows the Provenance.test.tsx precedent
 * (renderToStaticMarkup, no test-only rendering dependency) but stays a
 * plain `.ts` file by calling `WorldPicker` as a function rather than via
 * JSX — the same split FanChart.tsx / FanChart.test.ts already uses.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  bundleUrlFor,
  fetchWorlds,
  HIDDEN_WORLD_IDS,
  selectShownWorlds,
  SHOWN_GENERATOR_IDS,
  WorldPicker,
  WorldsFormatError,
  type WorldsDoc,
} from "./worlds";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn(async () => ({
    ok: status < 400,
    status,
    statusText: String(status),
    json: async () => body,
  }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

const DOC: WorldsDoc = {
  worlds: [
    {
      world_id: "w1",
      title: "Stagflation 1979",
      generator_id: "toy-v0",
      runs: [
        { run_id: "r2", seed: 43, created_at: "2026-02-01T00:00:00Z" },
        { run_id: "r1", seed: 42, created_at: "2026-01-01T00:00:00Z" },
      ],
    },
    {
      world_id: "w2",
      title: null,
      generator_id: "hier-flow-v1",
      runs: [{ run_id: "r3", seed: 7, created_at: "2026-03-01T00:00:00Z" }],
    },
  ],
};

describe("fetchWorlds", () => {
  it("parses a well-formed /worlds document", async () => {
    mockFetch(200, DOC);
    await expect(fetchWorlds()).resolves.toEqual(DOC);
  });

  it("requests the /worlds path", async () => {
    const fn = mockFetch(200, DOC);
    await fetchWorlds();
    const [path] = fn.mock.calls[0] as unknown as [string];
    expect(path).toBe("/worlds");
  });

  it("rejects a document missing runs on an entry", async () => {
    mockFetch(200, { worlds: [{ world_id: "w1", title: "x", generator_id: null }] });
    await expect(fetchWorlds()).rejects.toBeInstanceOf(WorldsFormatError);
  });

  it("rejects a document whose run is missing a seed", async () => {
    mockFetch(200, {
      worlds: [
        {
          world_id: "w1",
          title: "x",
          generator_id: null,
          runs: [{ run_id: "r1", created_at: "2026-01-01T00:00:00Z" }],
        },
      ],
    });
    await expect(fetchWorlds()).rejects.toBeInstanceOf(WorldsFormatError);
  });

  it("rejects a non-object body", async () => {
    mockFetch(200, "not a doc");
    await expect(fetchWorlds()).rejects.toBeInstanceOf(WorldsFormatError);
  });

  it("rejects on a non-ok response, service down or not deployed", async () => {
    mockFetch(404, {});
    await expect(fetchWorlds()).rejects.toBeInstanceOf(WorldsFormatError);
  });
});

describe("bundleUrlFor", () => {
  it("points at the run's bundle endpoint", () => {
    expect(bundleUrlFor("abc123")).toBe("/runs/abc123/bundle");
  });
});

/**
 * app-open-01 (owner ruling, 2026-08-16): the opening picker shows only the
 * declared-stress generation (`bootstrap-stratified`) — toy-engine
 * ("The Long Stagflation") and plain-bootstrap ("Nineteen Seventy-Four")
 * worlds stay in the store but are hidden here.
 */
const MULTI_GEN_DOC: WorldsDoc = {
  worlds: [
    {
      world_id: "toy-1979",
      title: "The Long Stagflation",
      generator_id: "toy-v0",
      runs: [{ run_id: "toy-r1", seed: 1, created_at: "2026-01-01T00:00:00Z" }],
    },
    {
      world_id: "plain-1974",
      title: "Nineteen Seventy-Four",
      generator_id: "bootstrap-v1",
      runs: [{ run_id: "plain-r1", seed: 2, created_at: "2026-01-02T00:00:00Z" }],
    },
    {
      world_id: "00000000-0000-4000-9000-000000000701",
      title: "The Long Squeeze",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "squeeze-r1", seed: 3, created_at: "2026-01-03T00:00:00Z" }],
    },
  ],
};

/**
 * app-open-01 review round fix 2 (owner ruling 2026-08-16): the REAL
 * `/worlds` shape behind the reported symptom — THREE DISTINCT world_ids,
 * not a repeat. 702 (The Lost Decade at 18-month blocks) and 703 (the
 * 2026-08-15 declaration, 6-month blocks) share the display title "The
 * Lost Decade" because 703 supersedes 702's methodology; it is not a
 * second run of the same world. `HIDDEN_WORLD_IDS` fences 702 out.
 */
const REVIEW_ROUND_DOC: WorldsDoc = {
  worlds: [
    {
      world_id: "00000000-0000-4000-9000-000000000701",
      title: "The Long Squeeze",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "squeeze-r1", seed: 3, created_at: "2026-01-03T00:00:00Z" }],
    },
    {
      world_id: "00000000-0000-4000-9000-000000000702",
      title: "The Lost Decade",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "lost-702-r1", seed: 4, created_at: "2026-08-10T00:00:00Z" }],
    },
    {
      world_id: "00000000-0000-4000-9000-000000000703",
      title: "The Lost Decade",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "lost-703-r1", seed: 5, created_at: "2026-08-16T00:00:00Z" }],
    },
  ],
};

describe("selectShownWorlds", () => {
  it("keeps only SHOWN_GENERATOR_IDS worlds", () => {
    const shown = selectShownWorlds(MULTI_GEN_DOC.worlds);
    expect(shown.every((w) => SHOWN_GENERATOR_IDS.includes(w.generator_id ?? ""))).toBe(true);
    expect(shown.some((w) => w.world_id === "toy-1979")).toBe(false);
    expect(shown.some((w) => w.world_id === "plain-1974")).toBe(false);
  });

  it("HIDDEN_WORLD_IDS names exactly 702", () => {
    expect(HIDDEN_WORLD_IDS).toEqual(["00000000-0000-4000-9000-000000000702"]);
  });

  it("hides 702 (retired methodology) and keeps 703 and the Long Squeeze — three distinct world_ids, not a same-world_id repeat", () => {
    const shown = selectShownWorlds(REVIEW_ROUND_DOC.worlds);
    expect(shown.map((w) => w.world_id).sort()).toEqual([
      "00000000-0000-4000-9000-000000000701",
      "00000000-0000-4000-9000-000000000703",
    ]);
    expect(shown.some((w) => w.world_id === "00000000-0000-4000-9000-000000000702")).toBe(false);
  });
});

describe("WorldPicker", () => {
  it("renders one button per shown world_id — 703's Lost Decade, not 702's", () => {
    const html = renderToStaticMarkup(WorldPicker({ doc: REVIEW_ROUND_DOC, onOpen: () => {} }));
    expect(html).toContain("Choose your decade");
    expect(html).toContain("The Long Squeeze");
    expect(html).toContain("The Lost Decade");
    // one <li> for the Long Squeeze, one for 703 — 702 fenced out, so
    // "The Lost Decade" appears exactly once despite two worlds sharing
    // the title.
    expect((html.match(/<li/g) ?? []).length).toBe(2);
    expect((html.match(/The Lost Decade/g) ?? []).length).toBe(1);
  });

  it("wires the shown Lost Decade button to 703's run — 702 is hidden, never reachable", () => {
    let opened: string | null = null;
    let root: Root | null = null;
    const host = document.createElement("div");
    document.body.appendChild(host);
    try {
      root = createRoot(host);
      act(() => {
        root!.render(WorldPicker({ doc: REVIEW_ROUND_DOC, onOpen: (url) => (opened = url) }));
      });
      const buttons = [...host.querySelectorAll("button")];
      const lostButton = buttons.find((b) => b.textContent?.includes("The Lost Decade"))!;
      act(() => lostButton.click());
      expect(opened).toBe(bundleUrlFor("lost-703-r1"));
      expect(opened).not.toBe(bundleUrlFor("lost-702-r1"));
    } finally {
      act(() => root?.unmount());
      host.remove();
    }
  });

  it("renders only the declared-stress worlds", () => {
    const html = renderToStaticMarkup(WorldPicker({ doc: MULTI_GEN_DOC, onOpen: () => {} }));
    expect(html).toContain("The Long Squeeze");
    expect(html).not.toContain("The Long Stagflation");
    expect(html).not.toContain("Nineteen Seventy-Four");
  });

  it("falls back to world_id when a shown world has no title", () => {
    const doc: WorldsDoc = {
      worlds: [
        {
          world_id: "w9",
          title: null,
          generator_id: "bootstrap-stratified",
          runs: [{ run_id: "r9", seed: 9, created_at: "2026-01-01T00:00:00Z" }],
        },
      ],
    };
    const html = renderToStaticMarkup(WorldPicker({ doc, onOpen: () => {} }));
    expect(html).toContain("w9");
    expect(html).toContain("seed 9");
  });

  it("renders nothing for a null doc — the fallback path when /worlds fails", () => {
    expect(renderToStaticMarkup(WorldPicker({ doc: null, onOpen: () => {} }))).toBe("");
  });

  it("renders nothing when the store has no worlds", () => {
    expect(renderToStaticMarkup(WorldPicker({ doc: { worlds: [] }, onOpen: () => {} }))).toBe("");
  });

  it("renders nothing when no world matches SHOWN_GENERATOR_IDS", () => {
    const doc: WorldsDoc = {
      worlds: [
        {
          world_id: "toy-1979",
          title: "The Long Stagflation",
          generator_id: "toy-v0",
          runs: [{ run_id: "toy-r1", seed: 1, created_at: "2026-01-01T00:00:00Z" }],
        },
      ],
    };
    expect(renderToStaticMarkup(WorldPicker({ doc, onOpen: () => {} }))).toBe("");
  });
});
