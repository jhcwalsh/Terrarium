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
 * The four actions are on the main screen at ALL times (owner: "need to make
 * sure the actions are visible on the main page"). Between windows they are
 * shown but inert — you can read exactly what each lever does while you play
 * the quarters into the window. `open=false` is a display state, not a
 * disabled form: there is no selection and no commit button, so there is
 * nothing to click through by accident.
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
    detail: "Move 10pts from equities and private equity into bonds and private credit.",
    k: "10PTS → BONDS/PC",
  },
  leanin: {
    title: "Lean in",
    detail:
      "Move 10pts from bonds and private credit into equities and private equity. Conviction has a price either way.",
    k: "10PTS → EQ/PE",
  },
  secondary: {
    title: "Secondary sale",
    detail:
      "Sell up to 8pts of private equity at an 18% discount for immediate liquidity; the proceeds move to bonds.",
    k: "−18% DISCOUNT",
  },
};

interface DecisionWindowProps {
  /** true when the pointer is stopped at a window and a commit is required */
  open: boolean;
  month: number;
  year: number;
  /** the year the next window opens, when this one is closed */
  nextYear?: number | null;
  onCommit: (action: Action, timeOnWindowMs: number) => void;
  busy?: boolean;
}

export function DecisionWindow({
  open,
  month,
  year,
  nextYear,
  onCommit,
  busy,
}: DecisionWindowProps) {
  const [selected, setSelected] = useState<Action | null>(null);
  const openedAt = useRef<number>(performance.now());

  useEffect(() => {
    openedAt.current = performance.now();
    setSelected(null);
  }, [month, open]);

  return (
    <section
      className={`decision-window${open ? "" : " closed"}`}
      aria-label={open ? `decision window year ${year}` : "actions available at the next window"}
    >
      <header>
        {open ? (
          <>
            <h2>Year {year} — the window is open</h2>
            <p>Time is stopped at month {month}. Nothing moves until you commit.</p>
          </>
        ) : (
          <>
            <h2>Your four levers</h2>
            <p>
              {nextYear
                ? `Advance the tape (» a quarter, ▶ to the stop). The decade halts at year ${nextYear}, and one of these is committed there.`
                : "All windows are decided. Play out the decade to face the reckoning."}
            </p>
          </>
        )}
      </header>
      <div className="actions" role={open ? "radiogroup" : "list"} aria-label="actions">
        {ACTIONS.map((action) => {
          const card = (
            <>
              <strong>{ACTION_COPY[action].title}</strong>
              <span className="k">{ACTION_COPY[action].k}</span>
              <span className="detail">{ACTION_COPY[action].detail}</span>
            </>
          );
          return open ? (
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
              {card}
            </label>
          ) : (
            <div key={action} className="action-card inert" role="listitem">
              {card}
            </div>
          );
        })}
      </div>
      {open && (
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
      )}
    </section>
  );
}
