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

import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { bundleUrlFor, fetchWorlds, WorldPicker, WorldsFormatError, type WorldsDoc } from "./worlds";

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

describe("WorldPicker", () => {
  it("lists each run as a title + seed button, newest-first order preserved", () => {
    const html = renderToStaticMarkup(WorldPicker({ doc: DOC, onOpen: () => {} }));
    expect(html).toContain("Choose your decade");
    expect(html).toContain("Stagflation 1979");
    expect(html).toContain("seed 43");
    expect(html).toContain("seed 42");
    // a titleless world falls back to its world_id
    expect(html).toContain("w2");
  });

  it("renders nothing for a null doc — the fallback path when /worlds fails", () => {
    expect(renderToStaticMarkup(WorldPicker({ doc: null, onOpen: () => {} }))).toBe("");
  });

  it("renders nothing when the store has no worlds", () => {
    expect(renderToStaticMarkup(WorldPicker({ doc: { worlds: [] }, onOpen: () => {} }))).toBe("");
  });
});
