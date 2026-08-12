/**
 * su-gen-03: the provenance panel renders the audit trail for generated
 * bundles and nothing at all for toy bundles.
 *
 * Rendered with react-dom/server's static markup — no test-only rendering
 * dependency ("every dependency is one someone must justify deleting later").
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { parseBundle } from "../lib/bundle";
import Provenance from "./Provenance";

function bytesOf(name: string): ArrayBuffer {
  const buf = readFileSync(resolve(process.cwd(), "fixtures", name));
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
}

describe("Provenance", () => {
  it("renders the verdict line and proxy disclosure for a generated bundle", async () => {
    const { bundle } = await parseBundle(bytesOf("gen.bundle.gz"));
    const html = renderToStaticMarkup(<Provenance bundle={bundle} />);
    expect(html).toContain("SHIP-BENCHMARK");
    expect(html).toContain("only the sequence is new");
    expect(html.toLowerCase()).toContain("reconstructed");
    // at least one factor discloses its reconstruction rule id
    expect(html).toMatch(/PROXY-/);
  });

  it("renders nothing for a toy bundle", async () => {
    const { bundle } = await parseBundle(bytesOf("toy.bundle.gz"));
    expect(renderToStaticMarkup(<Provenance bundle={bundle} />)).toBe("");
  });
});
