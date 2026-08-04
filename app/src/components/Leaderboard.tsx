/**
 * The leaderboard (su-app-05; DN-5 R-1).
 *
 * One board per (world_id, seed, decision_alpha_version) — the triple key is
 * in the fetch, not optional, so scores produced under different alpha
 * definitions or different histories can never share a table. The server
 * enforces this write-side (UNIQUE) and read-side (query params required);
 * this component just refuses to render without all three.
 */

import { useEffect, useState } from "react";
import { getLeaderboard, type LeaderboardRow } from "../lib/session";

export function Leaderboard({
  worldId,
  seed,
  alphaVersion,
  highlight,
}: {
  worldId: string;
  seed: number;
  alphaVersion: string;
  highlight?: string;
}) {
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLeaderboard(worldId, seed, alphaVersion)
      .then((b) => setRows(b.rows))
      .catch((e) => setError(String(e)));
  }, [worldId, seed, alphaVersion]);

  if (error) return <p className="error">{error}</p>;
  if (rows === null) return <p>loading the board…</p>;

  return (
    <section className="leaderboard" aria-label="leaderboard">
      <h2>The board</h2>
      <p className="board-key">
        world <code>{worldId.slice(0, 8)}</code> · seed {seed} · scoring{" "}
        <code>{alphaVersion}</code>
      </p>
      {rows.length === 0 ? (
        <p>No ranked scores yet for this exact world and scoring version.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>participant</th>
              <th>alpha</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.participant} className={r.participant === highlight ? "selected" : ""}>
                <td>{i + 1}</td>
                <td>{r.participant}</td>
                <td>
                  {r.score >= 0 ? "+" : ""}
                  {r.score.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
