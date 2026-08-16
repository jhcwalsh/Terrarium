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
  bookIsDefault = true,
}: {
  onStart: (config: PlayConfig) => void;
  onCancel: () => void;
  /** su-app-06: ranked requires the served default book AND plan, untouched.
   * Defaults true so callers that predate the book-entry screen (and every
   * existing test here) see the prior behaviour unchanged. */
  bookIsDefault?: boolean;
}) {
  const [ranked, setRanked] = useState(false);
  const [participant, setParticipant] = useState("");
  const [basis, setBasis] = useState<"reported" | "actual">("reported");

  const ready = !ranked || (bookIsDefault && participant.trim().length > 0);

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
          <input
            type="radio"
            name="arm"
            checked={ranked}
            disabled={!bookIsDefault}
            onChange={() => bookIsDefault && setRanked(true)}
          />
          <span>
            <strong>Ranked</strong> — your score joins the board for this exact
            world, seed, and scoring version. First play stands.
            {!bookIsDefault && (
              <em className="ranked-locked">
                {" "}
                Locked — you edited the opening book, so this session is
                practice only.
              </em>
            )}
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
            <option value="reported">as reported (appraisal-smoothed marks)</option>
            <option value="actual">actual (true marks)</option>
          </select>
        </label>
      </section>
      <section className="commit-primer" aria-label="one thing to know">
        {/* sp-05: E1's tutorial obligation — ONE unmissable commitment
            consequence, shown to every player before every decade. */}
        <h2>One thing to know before the decade starts</h2>
        <p>
          Each year you may set the next year&apos;s private commitments — or
          hold to the plan. The consequence that catches people: a commitment
          you cut pays nothing, forever. The vintage you skip in a bad year is
          the one that would have paid distributions in the good ones, and the
          post-game review will price exactly what the cut cost you.
        </p>
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
