/**
 * su-app-02 acceptance: the session client surfaces the server's authority.
 *
 * fetch is mocked — the endpoint CONTRACT (paths, bodies, error mapping) is
 * what these tests pin; the server's own behavior is pinned by the Python
 * suite (tests/test_serve.py), and the two meet at these request shapes.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  advance,
  createSession,
  decide,
  getCioView,
  planeForBasis,
  renderDetail,
  SessionApiError,
} from "./session";
import type { BandReport, Session } from "./session";

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

describe("planeForBasis (su-app-07)", () => {
  /**
   * The two vocabularies do not match: a session's `basis` is
   * `"reported" | "actual"`; the band report's planes are
   * `"reported" | "true"`. Carried finding from task 3.
   */
  it("maps a session's basis onto the band report's plane name", () => {
    expect(planeForBasis("actual")).toBe("true");
    expect(planeForBasis("reported")).toBe("reported");
  });

  it("does not pass 'actual' through as a plane name", () => {
    // the failure this exists to catch is the NAIVE equation of the two
    // vocabularies. `basis` used directly as a key reads `undefined` off the
    // band report — or falls back to the reported plane and shows a breach
    // from a plane the player is not on.
    const basis: Session["basis"] = "actual";
    expect(planeForBasis(basis)).not.toBe(basis);
    const report: BandReport = {
      watch_fraction: 0.75,
      sleeves: [
        {
          sleeve: "equity",
          target: 41,
          lo: 30,
          hi: 40,
          true: { weight: 44, alert: "breach" },
          reported: { weight: 38, alert: "watch" },
        },
      ],
    };
    const row = report.sleeves[0];
    expect(row[planeForBasis(basis)].alert).toBe("breach");
    // and the naive read finds nothing at all
    expect((row as unknown as Record<string, unknown>)[basis]).toBeUndefined();
  });
});

describe("renderDetail (su-app-06 I3)", () => {
  /**
   * FastAPI answers with `detail` as a STRING for our own HTTPExceptions and
   * as a LIST of `{loc, msg, type}` objects for pydantic-level failures.
   * `String(...)` on the second gives "[object Object]", so roughly half of
   * the refusals the book entry screen can provoke rendered as nothing the
   * analyst could act on.
   */
  it("passes a string detail through unchanged", () => {
    expect(renderDetail("book totals 103, must total 100", "422")).toBe(
      "book totals 103, must total 100",
    );
  });

  it("renders a pydantic-shaped list readably, never as [object Object]", () => {
    const detail = [
      { loc: ["body", "book", "private", "pe", 0, "commitment", "paid_in"], msg: "not a number" },
      { loc: ["body", "book", "cash"], msg: "Input should be a valid number" },
    ];
    const out = renderDetail(detail, "422");
    expect(out).not.toContain("[object Object]");
    expect(out).toContain("not a number");
    expect(out).toContain("body.book.private.pe.0.commitment.paid_in");
    expect(out).toContain("Input should be a valid number");
  });

  it("falls back rather than inventing text when there is no detail", () => {
    expect(renderDetail(undefined, "Unprocessable Entity")).toBe("Unprocessable Entity");
    expect(renderDetail([], "Unprocessable Entity")).toBe("Unprocessable Entity");
  });

  it("the error thrown by request() carries the rendered list", async () => {
    // the seam is only worth having if request() actually routes through it
    mockFetch(422, { detail: [{ loc: ["body", "cash"], msg: "Input should be >= 0" }] });
    const err = await createSession({ run_id: "r1" }).catch((e) => e);
    expect(err).toBeInstanceOf(SessionApiError);
    expect(err.message).toBe("body.cash: Input should be >= 0");
  });
});

describe("getCioView", () => {
  it("requests the plane and forecast quarters it was given", async () => {
    const fn = mockFetch(200, { meta: { plane: "true" } });
    const v = await getCioView("s-1", "true", 0);
    expect(fn).toHaveBeenCalledWith(
      "/sessions/s-1/cio?plane=true&forecast_quarters=0",
      expect.anything(),
    );
    expect(v.meta.plane).toBe("true");
  });

  it("defaults forecast quarters to the server default (omits the param)", async () => {
    const fn = mockFetch(200, { meta: { plane: "reported" } });
    await getCioView("s-1", "reported");
    expect(fn).toHaveBeenCalledWith(
      "/sessions/s-1/cio?plane=reported",
      expect.anything(),
    );
  });
});
