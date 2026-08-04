/**
 * su-app-02 acceptance: the session client surfaces the server's authority.
 *
 * fetch is mocked — the endpoint CONTRACT (paths, bodies, error mapping) is
 * what these tests pin; the server's own behavior is pinned by the Python
 * suite (tests/test_serve.py), and the two meet at these request shapes.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { advance, createSession, decide, SessionApiError } from "./session";

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

describe("session client", () => {
  it("creates a session with the documented body", async () => {
    const fn = mockFetch(201, { session_id: "s1", months: 120 });
    await createSession({ run_id: "r1", basis: "reported" });
    const [path, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/sessions");
    expect(JSON.parse(String(init.body))).toEqual({ run_id: "r1", basis: "reported" });
  });

  it("sends decisions with DN-6 client telemetry riding along", async () => {
    const fn = mockFetch(200, { session_id: "s1" });
    await decide("s1", 11, "derisk", { time_on_window_ms: 4200 });
    const [path, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/sessions/s1/decisions");
    expect(JSON.parse(String(init.body))).toEqual({
      month: 11,
      action: "derisk",
      client_log: { time_on_window_ms: 4200 },
    });
  });

  it("surfaces the server's refusal detail as SessionApiError", async () => {
    mockFetch(409, { detail: "windows are decided in order" });
    const err = await advance("s1", 60).catch((e) => e);
    expect(err).toBeInstanceOf(SessionApiError);
    expect(err.status).toBe(409);
    expect(err.message).toBe("windows are decided in order");
  });
});
