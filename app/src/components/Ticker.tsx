/**
 * The wire tape (vitrine remodel): a scrolling one-line ticker of the most
 * recent revealed feed items. Pure derivation from the bundle feed — same
 * reveal rule as the wire panel (month < revealedMonths), compressed to
 * tag + fragment. Content is duplicated once so the CSS loop is seamless.
 *
 * The track scrolls inside its own clipping window so the WIRE label stays
 * put — without it the translate carries items straight over the label.
 */

import type { FeedArtifact } from "../lib/bundle";

const TAG: Record<string, string> = {
  cb_statement: "CB",
  release_page: "DATA",
  quarterly_statement: "BOOK",
  wire_digest: "WIRE",
  newspaper: "PRESS",
  forced_sale: "SALE",
};

function fragment(a: FeedArtifact): string {
  const p = a.payload;
  if (p.rows?.length) {
    const r = p.rows[0];
    return `${r.series} ${r.value} (prior ${r.prior})`;
  }
  const text = p.headline ?? p.lines?.[0] ?? p.title ?? a.type;
  return text.length > 80 ? `${text.slice(0, 77)}...` : text;
}

export function Ticker({
  artifacts,
  revealedMonths,
}: {
  artifacts: FeedArtifact[];
  revealedMonths: number;
}) {
  const items = artifacts
    .filter((a) => a.month < revealedMonths)
    .sort((a, b) => b.month - a.month)
    .slice(0, 8)
    .map((a) => ({ tag: TAG[a.type] ?? a.type.toUpperCase(), text: fragment(a) }));

  return (
    <div className="tape">
      <div className="lbl">WIRE</div>
      <div className="tapewin">
        {items.length === 0 ? (
          <div className="tapetrack" style={{ animation: "none" }}>
            <span>Awaiting the first releases — advance the tape.</span>
          </div>
        ) : (
          <div className="tapetrack">
            {[...items, ...items].map((it, i) => (
              <span key={i}>
                <b>{it.tag}</b> {it.text}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
