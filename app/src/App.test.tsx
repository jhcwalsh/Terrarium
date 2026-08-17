/**
 * app-open-02 park (owner ruling, D-SP-6 session, 2026-08-16): ranked
 * sessions are PARKED — the play surface is practice-only until further
 * notice. `App.tsx` bypasses the "setup" step (`RankedSetup`) entirely and
 * goes straight from book confirmation to play with a practice config
 * (`RANKED_PARKED` / `PRACTICE_CONFIG`).
 *
 * No prior test exercised the App-level flow (world -> book -> play) at
 * all — there was no App.test.tsx before this file, and no other test
 * renders <App>. This is the flow-level proof of the bypass: it drives the
 * REAL App component through opening a bundle, confirming the served
 * default book, and asserts (a) RankedSetup's own screen never mounts and
 * (b) the session the app opens is posted with `ranked: false` and no
 * participant — the exact shape RankedSetup's practice path would have
 * produced, per RankedSetup.test.tsx ("practice starts without a name").
 *
 * Idiom note: this project has neither @testing-library/react nor
 * jest-dom (BookEntry.test.tsx's task-7 correction) — createRoot + act,
 * raw DOM queries, fetch stubbed via vi.stubGlobal, matching
 * BookEntry.test.tsx / Play.overlay.test.tsx / RankedSetup.test.tsx.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { webcrypto } from "node:crypto";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { DefaultBookResponse } from "./lib/session";

if (!globalThis.crypto?.subtle) {
  // happy-dom leaves WebCrypto off the global; Node's implementation matches
  // (same fix as Play.overlay.test.tsx — parseBundle needs it for the seal).
  Object.defineProperty(globalThis, "crypto", { value: webcrypto });
}

const FIXTURE = resolve(process.cwd(), "fixtures", "toy.bundle.gz");
const BUNDLE_URL = "https://fixture.test/bundle.gz";

/** A minimal but VALID served default: one liquid sleeve, no private
 * sleeves, totalling 100 with cash — enough for BookEntry's "Play" button
 * to be enabled without exercising the private-ladder/plan machinery this
 * test has no stake in. */
const DEFAULT_RESPONSE: DefaultBookResponse = {
  book: {
    state_version: "opening-book-0.2",
    liquid: { equity: 98 },
    private: {},
    cash: 2,
    targets: { equity: 98 },
    ranges: null,
  },
  plan: { state_version: "commitment-plan-0.1", points: {} },
  liquid_sleeves: ["equity"],
  book_digest: "a".repeat(64),
  plan_digest: "b".repeat(64),
};

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, statusText: String(status), json: () => Promise.resolve(body) };
}

/** Routes by URL substring + method, first match wins, throws loudly on an
 * unstubbed call (matches BookEntry.test.tsx's `stubFetchRouted`). Captures
 * every call so the test can inspect what App actually POSTed. */
function stubFetchRouted() {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, init });
    const method = init?.method ?? "GET";

    if (url === "/worlds") {
      // sib-01: progressive enhancement — a missing /worlds just leaves the
      // picker empty; App.tsx catches this itself.
      return Promise.resolve(jsonResponse({ worlds: [] }, false, 404));
    }
    if (url === BUNDLE_URL) {
      const buf = readFileSync(FIXTURE);
      const bytes = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "200",
        arrayBuffer: () => Promise.resolve(bytes),
      });
    }
    if (url.includes("/book/default")) {
      return Promise.resolve(jsonResponse(DEFAULT_RESPONSE));
    }
    if (url === "/sessions" && method === "POST") {
      // deliberately refused: Play.tsx's `error && !session` branch is a
      // stable, distinctive render this test can assert on without also
      // having to stub the CIO-view fetch a successfully-opened session
      // would trigger next — this test's stake is the REQUEST App made,
      // not what the server would have done with it.
      return Promise.resolve(
        jsonResponse({ detail: "session service not stubbed for this test" }, false, 500),
      );
    }
    throw new Error(`App.test: unstubbed fetch ${method} ${url}`);
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

let root: Root | null = null;
let host: HTMLElement | null = null;

async function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(ui);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function flush(rounds = 5) {
  for (let i = 0; i < rounds; i++) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

function findButton(matcher: RegExp): HTMLButtonElement {
  const btn = [...host!.querySelectorAll("button")].find((b) => matcher.test(b.textContent ?? ""));
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
  root = null;
  host = null;
  vi.unstubAllGlobals();
});

/** Drives the real App from its initial screen through to an opened bundle
 * (mode "browse"), via the manual bundle-URL form — the same loader path
 * `WorldPicker` buttons use. */
async function openBundle() {
  await render(<App />);
  const urlInput = host!.querySelector<HTMLInputElement>('input[type="url"]')!;
  setValue(urlInput, BUNDLE_URL);
  const form = urlInput.closest("form")!;
  act(() => {
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  await flush();
}

describe("App (app-open-02 park)", () => {
  it("never mounts RankedSetup and opens the session as practice, not ranked", async () => {
    const calls = stubFetchRouted();
    await openBundle();

    // world -> book
    act(() => findButton(/play this world/i).click());
    await flush();

    // book -> (setup, bypassed) -> play
    act(() => findButton(/^play$/i).click());
    await flush();

    // RankedSetup's own screen never mounted: its heading and its arm
    // radios are absent from the tree at any point after this click.
    expect(host!.textContent).not.toMatch(/how do you want to play/i);
    expect(host!.querySelector('input[name="arm"]')).toBeNull();

    // Play DID mount (its own "session refused" branch is distinctive and
    // proves this, without this test needing to stub a live session).
    expect(host!.textContent).toMatch(/opening session|session service/i);

    // and the request App made to open it is the practice shape
    // RankedSetup's own practice path would have produced.
    const posted = calls.find((c) => c.url === "/sessions" && c.init?.method === "POST");
    expect(posted).toBeDefined();
    const body = JSON.parse(String(posted!.init!.body));
    expect(body.ranked).toBe(false);
    expect(body.participant).toBeUndefined();
    expect(body.basis).toBe("reported");
  });
});
