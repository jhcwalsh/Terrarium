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
 * worlds stay in the store but are hidden here. This payload spans all
 * three generations, plus the reported symptom: "The Lost Decade"
 * (`world_id: "lost-decade"`) appearing as two separate entries because two
 * runs exist for it.
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
      world_id: "squeeze",
      title: "The Long Squeeze",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "squeeze-r1", seed: 3, created_at: "2026-01-03T00:00:00Z" }],
    },
    {
      world_id: "lost-decade",
      title: "The Lost Decade",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "lost-r-old", seed: 4, created_at: "2026-01-04T00:00:00Z" }],
    },
    {
      world_id: "lost-decade",
      title: "The Lost Decade",
      generator_id: "bootstrap-stratified",
      runs: [{ run_id: "lost-r-new", seed: 5, created_at: "2026-01-05T00:00:00Z" }],
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

  it("collapses a duplicated world_id, keeping the entry with the newest run", () => {
    const shown = selectShownWorlds(MULTI_GEN_DOC.worlds);
    const lost = shown.filter((w) => w.world_id === "lost-decade");
    expect(lost).toHaveLength(1);
    expect(lost[0].runs.map((r) => r.run_id)).toEqual(["lost-r-new"]);
  });

  it("returns one entry per world_id, squeeze plus the deduped lost-decade", () => {
    const shown = selectShownWorlds(MULTI_GEN_DOC.worlds);
    expect(shown.map((w) => w.world_id).sort()).toEqual(["lost-decade", "squeeze"]);
  });
});

describe("WorldPicker", () => {
  it("renders only the declared-stress worlds, one button per world_id", () => {
    const html = renderToStaticMarkup(WorldPicker({ doc: MULTI_GEN_DOC, onOpen: () => {} }));
    expect(html).toContain("Choose your decade");
    expect(html).toContain("The Long Squeeze");
    expect(html).toContain("The Lost Decade");
    expect(html).not.toContain("The Long Stagflation");
    expect(html).not.toContain("Nineteen Seventy-Four");
    // one <li> for squeeze, one for the deduped lost-decade — not two.
    expect((html.match(/<li/g) ?? []).length).toBe(2);
  });

  it("wires the kept lost-decade button to its newest run — same load path as before", () => {
    let opened: string | null = null;
    let root: Root | null = null;
    const host = document.createElement("div");
    document.body.appendChild(host);
    try {
      root = createRoot(host);
      act(() => {
        root!.render(WorldPicker({ doc: MULTI_GEN_DOC, onOpen: (url) => (opened = url) }));
      });
      const buttons = [...host.querySelectorAll("button")];
      const lostButton = buttons.find((b) => b.textContent?.includes("The Lost Decade"))!;
      act(() => lostButton.click());
      expect(opened).toBe(bundleUrlFor("lost-r-new"));
    } finally {
      act(() => root?.unmount());
      host.remove();
    }
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
