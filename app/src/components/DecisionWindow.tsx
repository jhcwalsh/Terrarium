/**
 * The decision surface (su-app-02; register row E1).
 *
 * At each window the decade STOPS: the player sees the briefing (where they
 * stand, what the four actions do) and must commit before time resumes.
 * E1's core requirement is that HOLD is an explicit commitment with the same
 * weight as acting — the commit button is disabled until an action is
 * chosen, and "hold course" is a choice, never a default that happens by
 * clicking through.
 *
 * D-QC-1 (2026-08-20): the clock is quarterly — a window at EVERY
 * quarter-close, not just the year-close nine. The stance chosen here
 * governs the coming quarter; the commitment figure is per VINTAGE YEAR,
 * editable at each of the year's windows (per-sleeve last-edit-wins) and
 * locking at the year-close. `month`/`nextStop` come from the session's
 * own `decision_windows` (Play.tsx), so this component never assumes an
 * annual grid — a legacy session's window is a year-close by construction
 * and reads correctly with no special-casing here.
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
import { usd } from "../lib/money";
import {
  ACTIONS,
  isYearClose,
  lockMonth,
  planeForBasis,
  windowLabel,
  type Action,
  type BandReport,
  type Session,
} from "../lib/session";
import { BandRow } from "./BandRow";

// app-open-01 item 2 (owner ruling 2026-08-16): each lever's point-impact
// gains its dollar rendering via the same usd() the rest of the app uses —
// no new data, just the $10bn display denomination applied to the fixed
// 10pt rebalance size the copy already states. Percentages (the secondary
// sale's discount rate) stay percentages, per the ruling.
const ACTION_COPY: Record<Action, { title: string; detail: string; k: string }> = {
  hold: {
    title: "Hold course",
    detail: "Rebalance to the current target mix and carry on. A commitment, not a shrug.",
    k: "NO TRADE",
  },
  derisk: {
    title: "De-risk",
    detail: "Move 10pts from equities and private equity into bonds and private credit.",
    k: `10PTS / ${usd(10)} → BONDS/PC`,
  },
  leanin: {
    title: "Lean in",
    detail:
      "Move 10pts from bonds and private credit into equities and private equity. Conviction has a price either way.",
    k: `10PTS / ${usd(10)} → EQ/PE`,
  },
  secondary: {
    title: "Secondary sale",
    detail:
      "Sell up to 8pts of private equity at an 18% discount for immediate liquidity; the proceeds move to bonds.",
    k: "−18% DISCOUNT",
  },
};

const PRIVATE_SLEEVES: ReadonlyArray<readonly [string, string]> = [
  ["pe", "Private equity"],
  ["pc", "Private credit"],
  ["re", "Real estate"],
  ["infra", "Infrastructure"],
];

interface DecisionWindowProps {
  /** true when the pointer is stopped at a window and a commit is required */
  open: boolean;
  month: number;
  /** D-QC-1: the label (windowLabel) of the next stop, when this one is
   * closed — e.g. "Y2 Q1" on a quarterly session, "Y2 Q4" on a legacy
   * annual one. The `year` prop this replaced is gone: every header/aria
   * label below computes its own label from `month` via `windowLabel`. */
  nextStop?: string | null;
  onCommit: (
    action: Action,
    timeOnWindowMs: number,
    commitments: Record<string, number> | null,
  ) => void;
  busy?: boolean;
  /** sp-02 (E1): the plan's next per-sleeve points, server-computed —
   * the lever's pre-fill. Committing it unchanged IS holding to plan. */
  planCommitments?: Record<string, number> | null;
  /** Audit F4: the state that pre-fill was computed from. It is the plan at
   * the last CLOSED quarter; the engine commits on the weight at the
   * commitment quarter, which cannot be known here without revealing that
   * quarter's returns. Declared rather than silently approximate. */
  planBasis?: {
    as_of_quarter: number;
    as_of_month: number;
    private_weight_reported: number;
  } | null;
  /** su-app-06 section 4.3: what the POLICY pacing rule would have paced at
   * the current reported weight, on a session carrying the analyst's own
   * kickoff plan. Shown BESIDE each plan figure as a labelled comparison and
   * never applied — the plan is what an untouched lever commits. Its
   * presence is what distinguishes a plan-carrying session here, and it is
   * also what replaces the F4 staleness caveat (`planBasis`), which the
   * server suppresses for these sessions because nothing is approximated. */
  planPace?: Record<string, number> | null;
  /** app-open-02: `session.band_report` — per-sleeve policy-band status at
   * the last CLOSED quarter, SERVER-judged. Rendered as a compact strip
   * ABOVE the four action cards while the window is open, so "which band am
   * I about to fix or break" is visible at the moment of the decision, not
   * only between windows (BandPanel, Play.tsx). Null (no book, no ranges,
   * or no closed quarter yet) or an empty sleeve list renders nothing here —
   * the window is otherwise unchanged. */
  bandReport?: BandReport | null;
  /** the session's scoring basis, mapped to the report's plane via
   * `planeForBasis` — the ONE mapping (lib/session.ts), same as BandPanel.
   * Never picked by hand. */
  basis?: Session["basis"];
}

export function DecisionWindow({
  open,
  month,
  nextStop,
  onCommit,
  busy,
  planCommitments,
  planBasis,
  planPace,
  bandReport,
  basis,
}: DecisionWindowProps) {
  const [selected, setSelected] = useState<Action | null>(null);
  const [commitments, setCommitments] = useState<Record<string, number> | null>(null);
  const openedAt = useRef<number>(performance.now());

  useEffect(() => {
    openedAt.current = performance.now();
    setSelected(null);
    setCommitments(null); // untouched lever => hold to the plan, silently
  }, [month, open]);

  // `commitments` holds ONLY the sleeves the player has actually edited
  // (audit F4). Anything absent is sent as nothing, and the server recomputes
  // the plan for it at the commitment quarter — which is the exact plan,
  // where the pre-fill shown here is a quarter stale.
  const shown = (key: string) => commitments?.[key] ?? planCommitments?.[key] ?? 0;

  return (
    <section
      className={`decision-window${open ? "" : " closed"}`}
      aria-label={
        open ? `decision window ${windowLabel(month)}` : "actions available at the next window"
      }
    >
      <header>
        {open ? (
          <>
            <h2>{windowLabel(month)} — the window is open</h2>
            <p>Time is stopped at month {month}. Nothing moves until you commit.</p>
          </>
        ) : (
          <>
            <h2>Your four levers</h2>
            <p>
              {nextStop
                ? `Advance the tape (» a quarter, ▶ to the stop). The decade halts at ${nextStop}, and one of these is committed there.`
                : "All windows are decided. Play out the decade to face the reckoning."}
            </p>
          </>
        )}
      </header>
      {open && bandReport && bandReport.sleeves.length > 0 && (
        <ul className="band-cells band-strip" aria-label="policy bands">
          {bandReport.sleeves.map((row) => (
            <BandRow
              key={row.sleeve}
              row={row}
              plane={planeForBasis(basis ?? "reported")}
              compact
            />
          ))}
        </ul>
      )}
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
      {open && planCommitments && (
        <div className="commit-lever" aria-label="commitment lever">
          <h3>This year&apos;s commitments</h3>
          <p className="lever-lock">
            {isYearClose(month)
              ? "This year's commitment locks now."
              : `This year's commitment locks at Q4 (month ${lockMonth(month)}); until then you can revise it.`}
          </p>
          <p className="lever-note">
            The plan paces these automatically. Change them and the change is
            yours — cuts starve distributions years out, raises call capital
            you must fund.
          </p>
          {PRIVATE_SLEEVES.map(([key, label]) => (
            <label key={key} className="lever-row">
              <span>{label}</span>
              <input
                type="number"
                min={0}
                step={0.1}
                aria-label={`${label} commitment`}
                value={shown(key).toFixed(2)}
                onChange={(e) =>
                  setCommitments({
                    ...(commitments ?? {}),
                    [key]: Math.max(0, Number(e.target.value)),
                  })
                }
              />
              <span className="lever-plan">plan {planCommitments[key]?.toFixed(2)}</span>
              {planPace?.[key] !== undefined && (
                <span className="lever-pace">
                  pacing rule {planPace[key].toFixed(2)}
                </span>
              )}
            </label>
          ))}
          {planPace && (
            <p className="lever-plan-note">
              These are your own kickoff plan&apos;s numbers for this window. A
              sleeve you leave alone commits exactly what is shown — nothing is
              re-paced behind you. Beside each is what the pacing rule would
              have committed at the book&apos;s current reported weight: a
              comparison, not a default.
            </p>
          )}
          {planBasis && (
            <p className="lever-basis">
              Plan figures are as at month {planBasis.as_of_month} (the last quarter
              closed), when the private book was{" "}
              {(planBasis.private_weight_reported * 100).toFixed(1)}% on reported marks.
              A sleeve you leave alone is paced fresh at the moment of commitment, so
              it holds to plan exactly; a sleeve you edit is yours at the number shown.
            </p>
          )}
          {commitments !== null && (
            <button className="lever-reset" onClick={() => setCommitments(null)}>
              back to plan
            </button>
          )}
        </div>
      )}
      {open && (
        <footer>
          <button
            className="commit"
            disabled={selected === null || busy}
            onClick={() => {
              if (selected !== null) {
                onCommit(
                  selected,
                  Math.round(performance.now() - openedAt.current),
                  commitments,
                );
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
