/**
 * The wire (su-app-03; register row E2): the world's feed, in-timeline.
 *
 * Items land as the pointer reveals their month — never as a lump, never
 * ahead of the tape. Newest first, because the player reads the wire the
 * way you read a terminal: what just happened is at the top.
 */

import type { FeedArtifact } from "../lib/bundle";

const TYPE_LABEL: Record<string, string> = {
  cb_statement: "CENTRAL BANK",
  release_page: "DATA RELEASE",
  quarterly_statement: "STATEMENT",
  wire_digest: "WIRE",
};

export function Feed({
  artifacts,
  revealedMonths,
}: {
  artifacts: FeedArtifact[];
  revealedMonths: number;
}) {
  const visible = artifacts
    .filter((a) => a.month < revealedMonths)
    .sort((a, b) => b.month - a.month);

  if (visible.length === 0) {
    return (
      <section className="feed" aria-label="the wire">
        <h2>The wire</h2>
        <p className="feed-empty">Nothing yet — advance time.</p>
      </section>
    );
  }

  return (
    <section className="feed" aria-label="the wire">
      <h2>The wire</h2>
      <ol>
        {visible.map((a, i) => (
          <li key={`${a.month}-${a.type}-${i}`} className={`feed-item feed-${a.type}`}>
            <header>
              <span className="feed-tag">{TYPE_LABEL[a.type] ?? a.type.toUpperCase()}</span>
              <span className="feed-dateline">{a.payload.dateline}</span>
            </header>
            {a.payload.title && <strong>{a.payload.title}</strong>}
            {a.payload.headline && <strong>{a.payload.headline}</strong>}
            {a.payload.release_name && (
              <table>
                <caption>{a.payload.release_name}</caption>
                <thead>
                  <tr>
                    <th>series</th>
                    <th>value</th>
                    <th>prior</th>
                  </tr>
                </thead>
                <tbody>
                  {(a.payload.rows ?? []).map((r) => (
                    <tr key={r.series}>
                      <td>{r.series}</td>
                      <td>{r.value}</td>
                      <td>{r.prior}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {(a.payload.lines ?? []).map((line, j) => (
              <p key={j}>{line}</p>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}
