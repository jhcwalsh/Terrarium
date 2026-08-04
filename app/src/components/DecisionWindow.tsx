/**
 * The decision surface (su-app-02; register row E1).
 *
 * At each annual window the decade STOPS: the player sees the briefing
 * (where they stand, what the four actions do) and must commit before time
 * resumes. E1's core requirement is that HOLD is an explicit commitment
 * with the same weight as acting — the commit button is disabled until an
 * action is chosen, and "hold course" is a choice, never a default that
 * happens by clicking through.
 *
 * Telemetry (DN-6 §8): time-on-window runs from mount to commit and rides
 * along with the decision as client telemetry; the server's timestamp is
 * the authoritative one.
 */

import { useEffect, useRef, useState } from "react";
import { ACTIONS, type Action } from "../lib/session";

const ACTION_COPY: Record<Action, { title: string; detail: string; k: string }> = {
  hold: {
    title: "Hold course",
    detail: "Rebalance to the current target mix and carry on. A commitment, not a shrug.",
    k: "NO TRADE",
  },
  derisk: {
    title: "De-risk",
    detail: "Shift 10pts from growth (equity, PE) into defensive (bonds, PC).",
    k: "10PTS G→D",
  },
  leanin: {
    title: "Lean in",
    detail: "Shift 10pts from defensive into growth. Conviction has a price either way.",
    k: "10PTS D→G",
  },
  secondary: {
    title: "Secondary sale",
    detail:
      "Sell up to 8pts of PE at an 18% discount for immediate liquidity; targets move PE to bonds.",
    k: "−18% HAIRCUT",
  },
};

interface DecisionWindowProps {
  month: number;
  year: number;
  onCommit: (action: Action, timeOnWindowMs: number) => void;
  busy?: boolean;
}

export function DecisionWindow({ month, year, onCommit, busy }: DecisionWindowProps) {
  const [selected, setSelected] = useState<Action | null>(null);
  const openedAt = useRef<number>(performance.now());

  useEffect(() => {
    openedAt.current = performance.now();
    setSelected(null);
  }, [month]);

  return (
    <section className="decision-window" aria-label={`decision window year ${year}`}>
      <header>
        <h2>Year {year} — the window is open</h2>
        <p>
          Time is stopped at month {month}. The decade does not continue until you
          commit.
        </p>
      </header>
      <div className="actions" role="radiogroup" aria-label="actions">
        {ACTIONS.map((action) => (
          <label
            key={action}
            className={`action-card${selected === action ? " selected" : ""}`}
          >
            <input
              type="radio"
              name={`decision-${month}`}
              checked={selected === action}
              onChange={() => setSelected(action)}
            />
            <strong>{ACTION_COPY[action].title}</strong>
            <span className="k">{ACTION_COPY[action].k}</span>
            <span className="detail">{ACTION_COPY[action].detail}</span>
          </label>
        ))}
      </div>
      <footer>
        <button
          className="commit"
          disabled={selected === null || busy}
          onClick={() => {
            if (selected !== null) {
              onCommit(selected, Math.round(performance.now() - openedAt.current));
            }
          }}
        >
          {selected === null
            ? "Choose an action to commit"
            : `Commit: ${ACTION_COPY[selected].title}`}
        </button>
        <p className="commit-note">Decisions are final. The server will hold you to this.</p>
      </footer>
    </section>
  );
}
