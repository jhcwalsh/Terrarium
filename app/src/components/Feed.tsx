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
  // the bundle's statement is the HOLD-COURSE book (pre-authored at build
  // time, so it cannot know the player's deviations) — label it as such
  quarterly_statement: "BENCHMARK BOOK",
  wire_digest: "WIRE",
  newspaper: "THE MARKET RECORD",
  forced_sale: "FORCED SALE",
  board_pack: "BOARD PACK",
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
        {visible.map((a, i) => {
          // a front page leads with its lead story, not with its masthead —
          // the masthead is the tag at the foot of the item
          const paper = a.type === "newspaper";
          const lines = a.payload.lines ?? [];
          const body = paper ? lines.slice(1) : lines;
          return (
          <li key={`${a.month}-${a.type}-${i}`} className={`feed-item feed-${a.type}`}>
            <span className="feed-dateline">{a.payload.dateline}</span>
            <div className="feed-body">
              {paper && lines.length > 0 && <strong>{lines[0]}</strong>}
              {!paper && a.payload.title && <strong>{a.payload.title}</strong>}
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
              {body.map((line, j) => (
                <p key={j}>{line}</p>
              ))}
              {(a.payload.sections ?? []).map((s) => (
                <div key={s.title} className="feed-pack-section">
                  <strong>{s.title}</strong>
                  {s.lines.map((line, j) => (
                    <p key={j}>{line}</p>
                  ))}
                </div>
              ))}
              <span className="feed-tag">{TYPE_LABEL[a.type] ?? a.type.toUpperCase()}</span>
            </div>
          </li>
          );
        })}
      </ol>
    </section>
  );
}
