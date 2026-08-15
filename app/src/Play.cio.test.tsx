/**
 * cio-02 task 4: the CIO view fetch policy inside Play.
 *
 * Play itself has no existing test file (mounting it needs a live/mocked
 * session service plus a WorldBundle fixture, which is out of scope for
 * this scaffold toggle — see task-4-brief.md Step 1). This file tests the
 * one extracted, pure seam: the fetch key that decides when the CIO view
 * must be refetched.
 */

import { describe, expect, it } from "vitest";
import { cioFetchKey } from "./Play";

describe("cio view fetch policy", () => {
  it("refetches when the reveal pointer moves", () => {
    expect(cioFetchKey("s", 12, "reported")).not.toBe(cioFetchKey("s", 15, "reported"));
  });

  it("refetches when the plane changes, same pointer", () => {
    expect(cioFetchKey("s", 12, "reported")).not.toBe(cioFetchKey("s", 12, "true"));
  });

  it("is stable when nothing moved", () => {
    expect(cioFetchKey("s", 12, "true")).toBe(cioFetchKey("s", 12, "true"));
  });
});
