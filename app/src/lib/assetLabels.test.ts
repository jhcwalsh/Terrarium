/**
 * ER-14 close-out (D-ER14-2, er14-04c Task A1): the fourth private asset
 * class (infrastructure) joins ASSET_LABELS in the engine's own contract
 * order, and gets the owner's full capitalized name (app-open-01 delta 3).
 */

import { describe, expect, it } from "vitest";
import { ASSET_LABELS, labelFor } from "./assetLabels";

describe("ASSET_LABELS", () => {
  it("labels every asset the engine ships, in the engine's own contract order", () => {
    expect(ASSET_LABELS.map(([k]) => k)).toEqual([
      "equity",
      "bonds",
      "hy",
      "commodities",
      "reits",
      "pe",
      "pc",
      "re",
      "infra",
    ]);
    expect(labelFor("infra")).toBe("Infrastructure");
  });

  it("falls back to the raw key for anything not on the list", () => {
    expect(labelFor("cash")).toBe("cash");
  });
});
