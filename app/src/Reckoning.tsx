/**
 * The reckoning (su-app-04): outcome card, three-series analysis, and the
 * chess-style post-game review.
 *
 * - Outcome card (E3): the headline numbers plus the interpretation guide's
 *   framing. Toy-plane scope stated in the card: forced-sale counts and
 *   coverage-on-both-bases join when Step-3 engine paths power the product
 *   plane (the register row's engine side is done; this surface reserves
 *   the slots).
 * - Analysis (E7): the three-series chart — player, policy twin, drift twin
 *   (slot reserved, data pending).
 * - Review (E4/E8): step through the decade window by window; each window
 *   carries its one-line annotation from the chain-link decomposition
 *   (`Year 4, de-risked: -2.1 points`) — the tone rule is the style
 *   guide's: state the number, never gloat.
 */

import { useState } from "react";
import { AnalysisChart, threeSeries } from "./components/AnalysisChart";
import type { Outcome } from "./lib/session";

const ACTION_PHRASE: Record<string, string> = {
  hold: "held course",
  derisk: "de-risked",
  leanin: "leaned in",
  secondary: "sold a secondary",
};

export function annotationLine(w: { month: number; action: string; contribution: number }) {
  const year = Math.floor((w.month + 1) / 12);
  const phrase = ACTION_PHRASE[w.action] ?? w.action;
  const pts = `${w.contribution >= 0 ? "+" : ""}${w.contribution.toFixed(1)} points`;
  return `Year ${year}, ${phrase}: ${pts}`;
}

export function Reckoning({
  outcome,
  onExit,
  board,
}: {
  outcome: Outcome;
  onExit: () => void;
  board?: React.ReactNode;
}) {
  const [reviewIdx, setReviewIdx] = useState<number | null>(null);
  const series = outcome.series
    ? threeSeries(outcome.series.active, outcome.series.twin, outcome.series.drift_twin)
    : null;

  return (
    <main className="shell">
      <section className="outcome-card">
        <h1>The reckoning</h1>
        <div className="outcome-headline">
          <div>
            <span className="outcome-label">you</span>
            <strong>{outcome.final_value.toFixed(2)}</strong>
          </div>
          <div>
            <span className="outcome-label">policy twin</span>
            <strong>{outcome.twin_final_value.toFixed(2)}</strong>
          </div>
          <div>
            <span className="outcome-label">decision alpha</span>
            <strong className={outcome.alpha >= 0 ? "ok" : "bad"}>
              {outcome.alpha >= 0 ? "+" : ""}
              {outcome.alpha.toFixed(2)}
            </strong>
          </div>
        </div>
        <p className="outcome-note">
          Alpha is your final value minus the twin that rebalanced to plan every
          year and never deviated — same world, same shocks, only the decisions
          differ. Forced-sale and coverage metrics join with the
          institutional plane.
        </p>
      </section>

      {series && (
        <AnalysisChart
          series={series}
          decisionMonths={outcome.windows.map((w) => w.month)}
        />
      )}

      <section className="review" aria-label="post-game review">
        <h2>The review</h2>
        <ol className="review-lines">
          {outcome.windows.map((w, i) => (
            <li
              key={w.month}
              className={reviewIdx === i ? "selected" : ""}
              onClick={() => setReviewIdx(i)}
            >
              {annotationLine(w)}
            </li>
          ))}
        </ol>
        {reviewIdx !== null && (
          <p className="review-detail">
            {annotationLine(outcome.windows[reviewIdx])} — this is the value of the
            decision given everything decided before it and mechanical policy
            after it (the chain-link convention; the lines sum exactly to your
            alpha).
          </p>
        )}
      </section>

      {board}

      <button onClick={onExit}>back to browse</button>
    </main>
  );
}
