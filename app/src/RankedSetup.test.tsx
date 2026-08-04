/**
 * su-app-05 acceptance: the arm-assignment affordances and the board client.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RankedSetup } from "./RankedSetup";
import { getLeaderboard } from "./lib/session";

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
  vi.unstubAllGlobals();
});

describe("RankedSetup", () => {
  it("practice starts without a name; ranked refuses until one is given", () => {
    const onStart = vi.fn();
    render(<RankedSetup onStart={onStart} onCancel={() => {}} />);
    const buttons = () => [...host!.querySelectorAll("button")];
    const start = () => buttons().find((b) => b.textContent?.startsWith("Play"))!;

    // practice: immediately ready
    expect(start().disabled).toBe(false);

    // switch to ranked: locked until a participant name exists
    const rankedRadio = host!.querySelectorAll<HTMLInputElement>('input[name="arm"]')[1];
    act(() => rankedRadio.click());
    expect(start().disabled).toBe(true);

    const name = host!.querySelector<HTMLInputElement>('input[type="text"]')!;
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(name, "james");
      name.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(start().disabled).toBe(false);
    act(() => start().click());
    expect(onStart).toHaveBeenCalledWith({
      ranked: true,
      participant: "james",
      basis: "reported",
    });
  });
});

describe("getLeaderboard", () => {
  it("sends the full triple key — never an unkeyed board", async () => {
    const fn = vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: "200",
      json: async () => ({ rows: [] }),
    }));
    vi.stubGlobal("fetch", fn);
    await getLeaderboard("w-1", 7, "dn5-v0.2-chainlink");
    const [path] = fn.mock.calls[0] as unknown as [string];
    expect(path).toContain("/leaderboard/w-1");
    expect(path).toContain("seed=7");
    expect(path).toContain("alpha_version=dn5-v0.2-chainlink");
  });
});
