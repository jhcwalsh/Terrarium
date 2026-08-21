/**
 * app-open-04 Item A: dead local entries on the front page.
 *
 * The browser's IndexedDB cache outlives releases: a cached bundle whose
 * run the server no longer has (or whose world is server-retired) used to
 * render exactly like a live entry — its world view opened from cache, and
 * then every book/play call 404'd, which the owner read as "lost the
 * ability to progress". The front page now probes every cached run id
 * against the `/worlds` document it already fetches (`runStatus`, one batch
 * GET — no per-entry request) and renders dead entries muted, with a plain
 * one-liner and a REMOVE control that clears the LOCAL cache entry only.
 * Nothing is ever auto-deleted, and no server call is made for a removal.
 *
 * `./lib/idb` is module-mocked — these tests pin the front page's handling
 * of cache state, not IndexedDB itself (happy-dom has none anyway).
 *
 * Idiom note: no @testing-library/react in this project — createRoot + act,
 * raw DOM queries, fetch stubbed via vi.stubGlobal (App.test.tsx).
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { cacheDelete, cacheList } from "./lib/idb";
import type { WorldsDoc } from "./lib/worlds";

vi.mock("./lib/idb", () => ({
  cacheList: vi.fn(async (): Promise<string[]> => []),
  cacheGet: vi.fn(async () => null),
  cachePut: vi.fn(async () => {}),
  cacheDelete: vi.fn(async () => {}),
}));

const WORLDS: WorldsDoc = {
  worlds: [
    {
      world_id: "w-live",
      title: "The Long Squeeze",
      generator_id: "bootstrap-stratified",
      retired: false,
      runs: [{ run_id: "run-live", seed: 1, created_at: "2026-01-01T00:00:00Z" }],
    },
    {
      world_id: "w-retired",
      title: "The Gulf Decade (old)",
      generator_id: "bootstrap-stratified",
      retired: true,
      runs: [{ run_id: "run-retired", seed: 2, created_at: "2025-01-01T00:00:00Z" }],
    },
  ],
};

/** Stubs `/worlds` (ok or down) and rejects everything else loudly. Returns
 * the call list so tests can prove no other request was made. */
function stubFetch(worldsOk: boolean) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, init });
    if (url === "/worlds") {
      return Promise.resolve({
        ok: worldsOk,
        status: worldsOk ? 200 : 404,
        statusText: worldsOk ? "200" : "404",
        json: () => Promise.resolve(worldsOk ? WORLDS : { detail: "down" }),
      });
    }
    throw new Error(`App.cache.test: unstubbed fetch ${url}`);
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

let root: Root | null = null;
let host: HTMLElement | null = null;

async function render() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<App />);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  await flush();
}

async function flush(rounds = 3) {
  for (let i = 0; i < rounds; i++) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

function entryFor(runId: string): HTMLLIElement {
  const li = [...host!.querySelectorAll("li")].find((el) =>
    el.querySelector("button")?.textContent?.includes(runId),
  );
  if (!li) throw new Error(`no cached entry for ${runId}`);
  return li as HTMLLIElement;
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("App front page — dead local entries (app-open-04 Item A)", () => {
  it("a dead entry renders muted with the one-liner and a remove control", async () => {
    vi.mocked(cacheList).mockResolvedValue(["run-live", "run-retired", "run-dead"]);
    stubFetch(true);
    await render();

    for (const runId of ["run-retired", "run-dead"]) {
      const li = entryFor(runId);
      expect(li.className).toContain("cached-stale");
      expect(li.textContent).toContain("from an earlier release - view only");
      expect(li.querySelector(`[aria-label="remove ${runId} from this machine"]`)).not.toBeNull();
    }
  });

  it("a live entry stays exactly as today — no note, no remove control", async () => {
    vi.mocked(cacheList).mockResolvedValue(["run-live", "run-dead"]);
    stubFetch(true);
    await render();

    const li = entryFor("run-live");
    expect(li.className).not.toContain("cached-stale");
    expect(li.textContent).not.toContain("earlier release");
    expect(li.querySelectorAll("button").length).toBe(1);
  });

  it("remove clears ONLY the local cache entry — no server call of any kind", async () => {
    vi.mocked(cacheList)
      .mockResolvedValueOnce(["run-live", "run-dead"]) // mount
      .mockResolvedValue(["run-live"]); // after removal
    const calls = stubFetch(true);
    await render();
    const before = calls.length;

    const remove = entryFor("run-dead").querySelector<HTMLButtonElement>(
      '[aria-label="remove run-dead from this machine"]',
    )!;
    await act(async () => {
      remove.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await flush();

    expect(vi.mocked(cacheDelete)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(cacheDelete)).toHaveBeenCalledWith("run-dead");
    expect(calls.length).toBe(before); // not one byte to the server
    expect([...host!.querySelectorAll("li button")].map((b) => b.textContent)).not.toContain(
      "run-dead",
    );
    // the live entry survives the neighbour's removal untouched
    expect(entryFor("run-live")).toBeDefined();
  });

  it("with /worlds unreachable no entry is marked stale (unknown, not dead)", async () => {
    vi.mocked(cacheList).mockResolvedValue(["run-live", "run-dead"]);
    stubFetch(false);
    await render();

    for (const runId of ["run-live", "run-dead"]) {
      const li = entryFor(runId);
      expect(li.className).not.toContain("cached-stale");
      expect(li.querySelectorAll("button").length).toBe(1);
    }
  });
});
