/**
 * Ranked setup (su-app-05): the arm assignment screen.
 *
 * Practice or ranked is chosen BEFORE the decade begins and is immutable for
 * the session — it is DN-6 §8's arm assignment, recorded server-side with
 * every decision. Ranked requires a participant name (the leaderboard's key
 * needs one); practice never touches the board. Basis (reported vs actual
 * marks) is part of the arm and recorded the same way.
 *
 * M4 boundary, stated: ranked is self-declared and local. No accounts, no
 * external users until the I5 observation study and consent clause land
 * (PD-3 stands).
 */

import { useState } from "react";

export interface PlayConfig {
  ranked: boolean;
  participant?: string;
  basis: "reported" | "actual";
}

export function RankedSetup({
  onStart,
  onCancel,
}: {
  onStart: (config: PlayConfig) => void;
  onCancel: () => void;
}) {
  const [ranked, setRanked] = useState(false);
  const [participant, setParticipant] = useState("");
  const [basis, setBasis] = useState<"reported" | "actual">("reported");

  const ready = !ranked || participant.trim().length > 0;

  return (
    <main className="shell">
      <h1>How do you want to play?</h1>
      <section className="setup">
        <label className="setup-row">
          <input
            type="radio"
            name="arm"
            checked={!ranked}
            onChange={() => setRanked(false)}
          />
          <span>
            <strong>Practice</strong> — no leaderboard, no pressure, same world.
          </span>
        </label>
        <label className="setup-row">
          <input type="radio" name="arm" checked={ranked} onChange={() => setRanked(true)} />
          <span>
            <strong>Ranked</strong> — your score joins the board for this exact
            world, seed, and scoring version. First play stands.
          </span>
        </label>
        {ranked && (
          <label className="setup-row">
            <span>Name for the board</span>
            <input
              type="text"
              value={participant}
              maxLength={40}
              onChange={(e) => setParticipant(e.target.value)}
              placeholder="who is playing?"
            />
          </label>
        )}
        <label className="setup-row">
          <span>Marks</span>
          <select
            value={basis}
            onChange={(e) => setBasis(e.target.value as "reported" | "actual")}
          >
            <option value="reported">reported (smoothed, as the sleeves report)</option>
            <option value="actual">actual (true marks)</option>
          </select>
        </label>
      </section>
      <button
        disabled={!ready}
        onClick={() =>
          onStart({
            ranked,
            participant: ranked ? participant.trim() : undefined,
            basis,
          })
        }
      >
        {ranked ? "Play ranked" : "Play practice"}
      </button>
      <button onClick={onCancel}>back</button>
    </main>
  );
}
