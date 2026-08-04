/**
 * World-bundle loading + verification (su-app-01; DN-3 W2/W3).
 *
 * The bundle is the ONLY payload the browser consumes (never an ensemble).
 * Loading is three steps, all client-side:
 *   1. fetch the .bundle.gz and gunzip it (DecompressionStream — no deps)
 *   2. parse and shape-check the W2 contract sections
 *   3. re-seal the revealed tape locally and compare with `tape_seal` —
 *      the client PROVES nobody rewrote history, it does not take it on faith.
 *
 * The seal algorithm mirrors ah.core.digest.sha256_of_arrays: SHA-256 over
 * the row-major float64 bytes of the (months x series) tape, little-endian.
 * The server rounds to 6dp before sealing, so the JSON numbers we received
 * ARE the sealed values — reconstructing a Float64Array from them and
 * hashing reproduces the seal exactly.
 */

export const SUPPORTED_BUNDLE_VERSIONS = [
  "world-bundle-0.1",
  "world-bundle-0.2",
  // 0.3 adds `private`: the display-only pacing ledger. Older bundles still
  // load — the panel simply has nothing to draw.
  "world-bundle-0.3",
];

export interface BundleMeta {
  world_id: string;
  run_id: string;
  seed: number;
  n_paths: number;
  months: number;
  created_at: string;
  digest_verified: boolean;
  outputs_digest: string;
  artifact_tier: string;
  title: string | null;
  tagline: string | null;
  decision_stamps: Record<string, string | null>;
  resolved_engine: Record<string, string>;
}

/** One tier-1 wire item (bundle v0.2); revealed with the pointer (E2). */
export interface FeedArtifact {
  month: number;
  type: string;
  payload: {
    dateline: string;
    title?: string;
    headline?: string;
    lines?: string[];
    release_name?: string;
    rows?: { series: string; value: string; prior: string; revision: string }[];
  };
}

/** One private-market programme's pacing ledger, quarter by quarter. */
export interface PrivateLedger {
  commitment: number;
  quarter_months: number[];
  called: number[];
  distributed: number[];
  unfunded: number[];
  nav: number[];
  dpi: number[];
  tvpi: number[];
}

export interface WorldBundle {
  bundle_version: string;
  meta: BundleMeta;
  revealed: { series_order: string[]; tape: number[][]; tape_seal: string };
  bands: Record<string, Record<string, number[]>>;
  /** present from world-bundle-0.3; absent in older bundles */
  private?: Record<string, PrivateLedger>;
  summary: {
    twin_final_value: number;
    decision_months: number[];
    episodes: unknown[];
    summary_stats: Record<string, number>;
  };
  feed: { artifacts?: FeedArtifact[]; dispatches: unknown[]; chronicle: unknown[] };
}

export class BundleFormatError extends Error {}

/** SHA-256 over the tape's row-major float64 bytes — the seal's exact recipe. */
export async function sealTape(tape: number[][]): Promise<string> {
  const rows = tape.length;
  const cols = rows > 0 ? tape[0].length : 0;
  const flat = new Float64Array(rows * cols);
  for (let r = 0; r < rows; r++) {
    const row = tape[r];
    if (row.length !== cols) throw new BundleFormatError("ragged tape");
    for (let c = 0; c < cols; c++) flat[r * cols + c] = row[c];
  }
  const digest = await crypto.subtle.digest("SHA-256", flat.buffer as ArrayBuffer);
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `sha256:${hex}`;
}

function shapeCheck(doc: WorldBundle): void {
  if (!SUPPORTED_BUNDLE_VERSIONS.includes(doc.bundle_version)) {
    throw new BundleFormatError(
      `unsupported bundle_version ${doc.bundle_version} (want one of ${SUPPORTED_BUNDLE_VERSIONS.join(", ")})`,
    );
  }
  for (const section of ["meta", "revealed", "bands", "summary", "feed"] as const) {
    if (!(section in doc)) throw new BundleFormatError(`missing section ${section}`);
  }
  const { months } = doc.meta;
  if (doc.revealed.tape.length !== months) {
    throw new BundleFormatError(
      `tape has ${doc.revealed.tape.length} months, meta says ${months}`,
    );
  }
}

export interface LoadedBundle {
  bundle: WorldBundle;
  /** The client's own re-seal matched the shipped seal. */
  sealVerified: boolean;
}

export async function parseBundle(gzBytes: ArrayBuffer): Promise<LoadedBundle> {
  const stream = new Blob([gzBytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  const json = await new Response(stream).text();
  const bundle = JSON.parse(json) as WorldBundle;
  shapeCheck(bundle);
  const sealVerified = (await sealTape(bundle.revealed.tape)) === bundle.revealed.tape_seal;
  return { bundle, sealVerified };
}

export async function fetchBundle(url: string): Promise<LoadedBundle> {
  const res = await fetch(url);
  if (!res.ok) throw new BundleFormatError(`fetch ${url}: ${res.status}`);
  return parseBundle(await res.arrayBuffer());
}
